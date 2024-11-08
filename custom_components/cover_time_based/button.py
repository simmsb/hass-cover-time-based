"""Cover support for switch entities."""

from __future__ import annotations

import logging
import asyncio

from homeassistant.components.button import ButtonEntity
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_OPEN_COVER
from homeassistant.const import SERVICE_STOP_COVER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import CONF_TIME_OPEN

_LOGGER = logging.getLogger(__name__)


def generate_unique_id(name: str) -> str:
    entity = f"{COVER_DOMAIN}.time_based_{name}".lower()
    unique_id = slugify(entity)
    return unique_id

def generate_button_unique_id(name: str) -> str:
    entity = f"{COVER_DOMAIN}.time_based_{name}_button".lower()
    unique_id = slugify(entity)
    return unique_id


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Cover Switch calibrate config entry."""
    registry = er.async_get(hass)

    cover_id = generate_unique_id(config_entry.title)

    cover = er.async_validate_entity_id(
        registry, cover_id
    )
    button = CalibrateButton(
        generate_button_unique_id(config_entry.title),
        f"{config_entry.title} calibrate",
        config_entry.options[CONF_TIME_OPEN],
        cover,
    )

    async_add_entities([button])

class CalibrateButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        unique_id,
        name,
        travel_time_up,
        cover,
    ):
        self._name = name
        self._attr_unique_id = unique_id
        self._travel_time_up = travel_time_up
        self.cover = cover

    async def async_press(self):
        """Use the open entity for a while then assume the cover is fully open."""
        _LOGGER.debug("do_calibrate")
        await self.cover.check_availability()
        if not self.cover.available:
            return
        self.cover.stop_auto_updater()
        await self.cover._async_handle_command(SERVICE_OPEN_COVER)

        await asyncio.sleep(self._travel_time_up)
        self.cover.tc.set_position(self.cover.tc.position_open)

        await self.cover._async_handle_command(SERVICE_STOP_COVER)

