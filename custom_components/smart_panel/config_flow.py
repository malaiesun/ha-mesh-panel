import voluptuous as vol
import yaml
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_TOPIC, CONF_MANUAL_CONFIG, DEFAULT_TOPIC

# Default template to help the user start
DEFAULT_YAML_TEMPLATE = """
# Define your devices here.
# Example:
- name: Gaming Setup
  icon: mdi:controller
  state_entity: light.gaming_pc
  controls:
    - label: System Power
      type: switch
      entity: switch.pc_plug
    - label: Desk Glow
      type: color
      entity: light.desk_strip
    - label: Volume
      type: slider
      entity: number.pc_volume
      min: 0
      max: 100
      step: 2

- name: Living Fan
  icon: mdi:fan
  state_entity: fan.living
  controls:
    - label: Fan
      type: switch
      entity: fan.living
    - label: Speed
      type: slider
      entity: number.fan_speed
"""

class SmartPanelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_TOPIC], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_TOPIC, default=DEFAULT_TOPIC): str,
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartPanelOptionsFlow(config_entry)

class SmartPanelOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        
        # Pre-fill with existing config or default template
        current_yaml = self.config_entry.options.get(CONF_MANUAL_CONFIG, DEFAULT_YAML_TEMPLATE)

        if user_input is not None:
            try:
                # Validate YAML format
                parsed = yaml.safe_load(user_input[CONF_MANUAL_CONFIG])
                if not isinstance(parsed, list):
                    raise ValueError("Config must be a list of devices")
                
                # Save data
                return self.async_create_entry(title="", data=user_input)
            except Exception:
                errors["base"] = "invalid_yaml"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_MANUAL_CONFIG, default=current_yaml): str,
            }),
            errors=errors,
            description_placeholders={"error_info": "Check YAML syntax"}
        )