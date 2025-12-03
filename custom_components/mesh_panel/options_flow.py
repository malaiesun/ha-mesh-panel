"""
Options flow for MESH Smart Home Panel."""
import logging
import voluptuous as vol
import yaml
import uuid
from homeassistant import config_entries
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig
from .const import *

_LOGGER = logging.getLogger(__name__)

class MeshPanelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for MESH Panel."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                devices = yaml.safe_load(user_input[CONF_DEVICES])
                if devices is None:
                    devices = []
                if not isinstance(devices, list):
                    raise ValueError("YAML must be a list of devices")
                
                # Basic validation and add IDs
                for device in devices:
                    if not isinstance(device, dict) or not device.get("name") or not isinstance(device.get("controls"), list):
                        raise ValueError("Invalid device structure in YAML")
                    if "id" not in device or not device.get("id"):
                        device["id"] = str(uuid.uuid4())
                    for control in device.get("controls", []):
                        if not isinstance(control, dict) or not control.get("label"):
                            raise ValueError("Invalid control structure in YAML")
                        if "id" not in control or not control.get("id"):
                            control["id"] = str(uuid.uuid4())

                self.options[CONF_DEVICES] = devices
                return self.async_create_entry(title="", data=self.options)
            except (yaml.YAMLError, ValueError) as e:
                _LOGGER.error("YAML parsing error: %s", e)
                errors["base"] = "invalid_yaml"

        current_devices = self.options.get(CONF_DEVICES, [])
        current_yaml = ""
        if current_devices:
            try:
                current_yaml = yaml.dump(current_devices)
            except Exception as e:
                _LOGGER.error("Error dumping current config to YAML: %s", e)
                errors["base"] = "yaml_dump_error"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_DEVICES, default=current_yaml): TextSelector(TextSelectorConfig(multiline=True))
            }),
            errors=errors,
            description_placeholders={"description": "Configure devices using YAML."}
        )