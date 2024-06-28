"""Cover support for switch entities."""

from __future__ import annotations

from typing import Any
import logging

from datetime import timedelta

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverEntity,
    CoverEntityFeature,
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    PLATFORM_SCHEMA,

)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import (
    CONF_NAME,
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_track_utc_time_change, async_track_time_interval
from homeassistant.util import slugify
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENTITY_UP, CONF_ENTITY_DOWN, CONF_TIME_OPEN, CONF_TIME_CLOSE
from .travelcalculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

async def async_get_device_entry_from_entity_id(
    hass: HomeAssistant, entity_id: str
) -> DeviceEntry:
    """ Get DeviceEntry from an entity ID. """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if (
        entity_entry is None
        or entity_entry.device_id is None
        or entity_entry.platform != DOMAIN
    ):
        return False

    device_id = entity_entry.device_id

    device_reg = dr.async_get(hass)
    device = device_reg.async_get(device_id)

    return device


def generate_unique_id(name: str) -> str:
    entity = f"{COVER_DOMAIN}.time_based_{name}".lower()
    unique_id = slugify(entity)
    return unique_id


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Cover Switch config entry."""
    registry = er.async_get(hass)

    entity_up = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_UP]
    )
    entity_down = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_DOWN]
    )

    async_add_entities(
        [
            CoverTimeBased(
                generate_unique_id(config_entry.title),
                config_entry.title,
                config_entry.options.get(CONF_TIME_CLOSE),
                config_entry.options[CONF_TIME_OPEN],
                entity_up,
                entity_down,
            )
        ]
    )


class CoverTimeBased(CoverEntity, RestoreEntity):

    def __init__(self, unique_id, name, travel_time_down, travel_time_up, open_switch_entity_id, close_switch_entity_id):
        """Initialize the cover."""
        if not travel_time_down:
            travel_time_down = travel_time_up
        self._travel_time_down = travel_time_down
        self._travel_time_up = travel_time_up
        self._open_switch_entity_id = open_switch_entity_id
        self._close_switch_entity_id = close_switch_entity_id
        self._name = name
        self._attr_unique_id = unique_id

        self._unsubscribe_auto_updater = None

        self.tc = TravelCalculator(self._travel_time_down, self._travel_time_up)

    async def async_added_to_hass(self):
        """ Only cover's position matters.             """
        """ The rest is calculated from this attribute."""
        old_state = await self.async_get_last_state()
        _LOGGER.debug('async_added_to_hass :: oldState %s', old_state)
        if (
                old_state is not None and
                self.tc is not None and
                old_state.attributes.get(ATTR_CURRENT_POSITION) is not None):
            self.tc.set_position(int(
                old_state.attributes.get(ATTR_CURRENT_POSITION)))

    def _handle_my_button(self):
        """Handle the MY button press"""
        if self.tc.is_traveling():
            _LOGGER.debug('_handle_my_button :: button stops cover')
            self.tc.stop()
            self.stop_auto_updater()

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        if self._travel_time_down is not None:
            attr[CONF_TIME_CLOSE] = self._travel_time_down
        if self._travel_time_up is not None:
            attr[CONF_TIME_OPEN] = self._travel_time_up
        return attr

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.tc.current_position()

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self.tc.is_traveling() and \
               self.tc.travel_direction == TravelStatus.DIRECTION_DOWN

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self.tc.is_traveling() and \
               self.tc.travel_direction == TravelStatus.DIRECTION_UP

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.current_cover_position is None or \
               self.current_cover_position <= 10

    @property
    def assumed_state(self):
        """Return True because covers can be stopped midway."""
        return True

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug('async_set_cover_position: %d', position)
            await self.set_position(position)

    async def async_close_cover(self, **kwargs):
        """Turn the device close."""
        _LOGGER.debug('async_close_cover')
        await self._async_handle_command(SERVICE_CLOSE_COVER)
        self.tc.start_travel_up()
        self.start_auto_updater()

    async def async_open_cover(self, **kwargs):
        """Turn the device open."""
        _LOGGER.debug('async_open_cover')
        await self._async_handle_command(SERVICE_OPEN_COVER)
        self.tc.start_travel_down()
        self.start_auto_updater()

    async def async_stop_cover(self, **kwargs):
        """Turn the device stop."""
        _LOGGER.debug('async_stop_cover')
        await self._async_handle_command(SERVICE_STOP_COVER)
        self._handle_my_button()

    async def set_position(self, position):
        _LOGGER.debug('set_position')
        """Move cover to a designated position."""
        current_position = self.tc.current_position()
        _LOGGER.debug('set_position :: current_position: %d, new_position: %d',
                      current_position, position)
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        if command is not None:
            await self._async_handle_command(command)
            self.start_auto_updater()
            self.tc.start_travel(position)
            _LOGGER.debug('set_position :: command %s', command)
        return

    def start_auto_updater(self):
        """Start the autoupdater to update HASS while cover is moving."""
        _LOGGER.debug('start_auto_updater')
        if self._unsubscribe_auto_updater is None:
            _LOGGER.debug('init _unsubscribe_auto_updater')
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval)

    @callback
    def auto_updater_hook(self, now):
        """Call for the autoupdater."""
        _LOGGER.debug('auto_updater_hook')
        self.async_schedule_update_ha_state()
        if self.position_reached():
            _LOGGER.debug('auto_updater_hook :: position_reached')
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self):
        """Stop the autoupdater."""
        _LOGGER.debug('stop_auto_updater')
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def position_reached(self):
        """Return if cover has reached its final position."""
        return self.tc.position_reached()

    async def auto_stop_if_necessary(self):
        """Do auto stop if necessary."""
        if self.position_reached():
            _LOGGER.debug('auto_stop_if_necessary :: calling stop command')
            await self._async_handle_command(SERVICE_STOP_COVER)
            self.tc.stop()


    async def _async_handle_command(self, command, *args):
        if command == "close_cover":
            cmd = "DOWN"
            self._state = False
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._open_switch_entity_id}, False)
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._close_switch_entity_id}, False)

        elif command == "open_cover":
            cmd = "UP"
            self._state = True
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._close_switch_entity_id}, False)
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._open_switch_entity_id}, False)

        elif command == "stop_cover":
            cmd = "STOP"
            self._state = True
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._close_switch_entity_id}, False)
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._open_switch_entity_id}, False)

        _LOGGER.debug('_async_handle_command :: %s', cmd)

        # Update state of entity
        self.async_write_ha_state()
