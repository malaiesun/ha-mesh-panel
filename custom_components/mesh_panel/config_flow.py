import logging
import json
import voluptuous as vol
import yaml
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, CONF_PANEL_ID, CONF_LAYOUT, DEFAULT_LAYOUT

_LOGGER = logging.getLogger(__name__)

class MeshPanelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mesh Panel."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step (Manual Add)."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PANEL_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input["name"], 
                data={CONF_PANEL_ID: user_input[CONF_PANEL_ID]},
                options={CONF_LAYOUT: DEFAULT_LAYOUT}
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required(CONF_PANEL_ID): str,
            }),
            errors=errors,
        )

    async def async_step_discovery(self, discovery_info):
        """Handle auto-discovery from MQTT announce."""
        panel_id = discovery_info["panel_id"]
        ip_address = discovery_info.get("ip", "Unknown")
        
        await self.async_set_unique_id(panel_id)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": f"Panel {panel_id}"}
        
        # Determine the name automatically
        return self.async_create_entry(
            title=f"Mesh Panel ({panel_id})",
            data={CONF_PANEL_ID: panel_id},
            options={CONF_LAYOUT: DEFAULT_LAYOUT}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MeshPanelOptionsFlowHandler(config_entry)


class MeshPanelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow to configure the UI layout."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Validate YAML
            try:
                yaml.safe_load(user_input[CONF_LAYOUT])
                return self.async_create_entry(title="", data=user_input)
            except yaml.YAMLError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_schema(user_input),
                    errors={"base": "invalid_yaml"}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_schema(self.config_entry.options)
        )

    def _get_schema(self, defaults):
        default_layout = defaults.get(CONF_LAYOUT, DEFAULT_LAYOUT)
        return vol.Schema({
            vol.Required(CONF_LAYOUT, default=default_layout): TextSelector(
                TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
            )
        })