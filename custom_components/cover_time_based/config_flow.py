"""Config flow for Cover Time-based integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, Platform
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    wrapped_entity_config_entry_title,
)

from .const import CONF_ENTITY_UP, CONF_ENTITY_DOWN, CONF_INVERT, CONF_TARGET_DEVICE_CLASS, CONF_TIME_OPEN, CONF_TIME_CLOSE, DOMAIN

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_ENTITY_UP): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[Platform.SWITCH, Platform.LIGHT])
                ),
                vol.Required(CONF_ENTITY_DOWN): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[Platform.SWITCH, Platform.LIGHT])
                ),
                vol.Required(CONF_TIME_OPEN, default=25): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX, min=2,
                        max=120,
                        step="any",
                        unit_of_measurement="sec"
                    )
                ),
                vol.Optional(CONF_TIME_CLOSE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX,
                        max=120,
                        step="any",
                        unit_of_measurement="sec"
                    )
                ),
            }
        )
    )
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        vol.Schema({
            vol.Required(CONF_TIME_OPEN): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, min=2,
                    max=120,
                    step="any",
                    unit_of_measurement="sec"
                )
            ),
            vol.Optional(CONF_TIME_CLOSE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    max=120,
                    step="any",
                    unit_of_measurement="sec"
                )
            ),
        })
    ),
}


class CoverTimeBasedConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Cover Time-based."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    VERSION = 1
    MINOR_VERSION = 2

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title and hide the wrapped entity if registered."""
        # Hide the wrapped entry if registered
        registry = er.async_get(self.hass)

        for entity in [CONF_ENTITY_UP, CONF_ENTITY_DOWN]:
            entity_entry = registry.async_get(options[entity])
            if entity_entry is not None and not entity_entry.hidden:
                registry.async_update_entity(
                    options[entity], hidden_by=er.RegistryEntryHider.INTEGRATION
                )

        return options[CONF_NAME]
