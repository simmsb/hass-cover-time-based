"""Cover support for switch entities."""

from __future__ import annotations

import logging
import asyncio

from homeassistant.components.button import ButtonEntity
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

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

    cover_id = generate_unique_id(config_entry.title)
    button = CalibrateButton(
        generate_button_unique_id(config_entry.title),
        cover_id,
    )

    async_add_entities([button])

class CalibrateButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        unique_id,
        cover_id,
    ):
        self._name = "Calibrate"
        self._attr_unique_id = unique_id
        self.cover_id = cover_id

    async def async_press(self):
        """Use the open entity for a while then assume the cover is fully open."""
        _LOGGER.debug("do_calibrate press")

        self.hass.bus.async_fire("cover_time_based_calibrate", {
            ATTR_ENTITY_ID: self.cover_id
        })
