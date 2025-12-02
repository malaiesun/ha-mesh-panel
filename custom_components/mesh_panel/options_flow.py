import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    EntitySelector, EntitySelectorConfig,
    IconSelector,
    NumberSelector, NumberSelectorConfig
)
from .const import DOMAIN, CONF_DEVICES

CONF_NAME = "name"
CONF_ICON = "icon"
CONF_CONTROLS = "controls"
CONF_ID = "id"

CONF_LABEL = "label"
CONF_TYPE = "type"
CONF_ENTITY = "entity"
CONF_MIN = "min"
CONF_MAX = "max"
CONF_STEP = "step"
CONF_OPTIONS = "options"


CONTROL_TYPES = [
    {"value": "switch", "label": "Switch (On/Off)"},
    {"value": "slider", "label": "Slider (Brightness/Volume)"},
    {"value": "color", "label": "Color Wheel"},
    {"value": "select", "label": "Dropdown Selection"},
]

class MeshPanelOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.devices = self.options.get(CONF_DEVICES, [])
        self.current_device_id = None
        self.current_control_id = None

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            if user_input["action"] == "add":
                self.current_device_id = None
                return await self.async_step_device()
            
            self.current_device_id = user_input["action"]
            return await self.async_step_device_menu()

        device_options = {"add": "Add a new device"}
        for device in self.devices:
            device_options[device[CONF_ID]] = device[CONF_NAME]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(SelectSelectorConfig(options=list(device_options.keys()), custom_value=False, mode=SelectSelectorMode.DROPDOWN, translation_key=device_options)),
            }),
            last_step=False,
        )

    async def async_step_device_menu(self, user_input=None):
        if user_input is not None:
            if user_input["action"] == "edit":
                return await self.async_step_device()
            if user_input["action"] == "delete":
                self.devices = [d for d in self.devices if d[CONF_ID] != self.current_device_id]
                self.options[CONF_DEVICES] = self.devices
                return self.async_create_entry(title="", data=self.options)
            if user_input["action"] == "controls":
                return await self.async_step_controls()

        return self.async_show_form(
            step_id="device_menu",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(SelectSelectorConfig(options=["edit", "delete", "controls"], custom_value=False, mode=SelectSelectorMode.DROPDOWN, translation_key={"edit": "Edit Device", "delete": "Delete Device", "controls": "Manage Controls"})),
            }),
            last_step=False
        )

    async def async_step_device(self, user_input=None):
        errors = {}
        device_data = {}
        if self.current_device_id:
            device_data = next((d for d in self.devices if d[CONF_ID] == self.current_device_id), {})

        if user_input is not None:
            device_data[CONF_NAME] = user_input[CONF_NAME]
            device_data[CONF_ICON] = user_input[CONF_ICON]
            if not self.current_device_id:
                device_data[CONF_ID] = str(uuid.uuid4())
                device_data[CONF_CONTROLS] = []
                self.devices.append(device_data)
            
            self.options[CONF_DEVICES] = self.devices
            self.current_device_id = device_data[CONF_ID]
            return await self.async_step_controls()

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=device_data.get(CONF_NAME, "")): TextSelector(),
                vol.Required(CONF_ICON, default=device_data.get(CONF_ICON, "mdi:power")): IconSelector(),
            }),
            errors=errors,
            last_step=False,
        )

    async def async_step_controls(self, user_input=None):
        device_data = next((d for d in self.devices if d[CONF_ID] == self.current_device_id), {})
        controls = device_data.get(CONF_CONTROLS, [])

        if user_input is not None:
            if user_input["action"] == "add":
                self.current_control_id = None
                return await self.async_step_control()
            if user_input["action"] == "back":
                self.current_device_id = None
                return await self.async_step_init()
            
            self.current_control_id = user_input["action"]
            return await self.async_step_control_menu()

        control_options = {"add": "Add a new control", "back": "Back to devices"}
        for control in controls:
            control_options[control[CONF_ID]] = control[CONF_LABEL]

        return self.async_show_form(
            step_id="controls",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(SelectSelectorConfig(options=list(control_options.keys()), custom_value=False, mode=SelectSelectorMode.DROPDOWN, translation_key=control_options)),
            }),
            last_step=False,
        )
    
    async def async_step_control_menu(self, user_input=None):
        if user_input is not None:
            if user_input["action"] == "edit":
                return await self.async_step_control()
            if user_input["action"] == "delete":
                device_data = next((d for d in self.devices if d[CONF_ID] == self.current_device_id), {})
                controls = device_data.get(CONF_CONTROLS, [])
                device_data[CONF_CONTROLS] = [c for c in controls if c[CONF_ID] != self.current_control_id]
                self.options[CONF_DEVICES] = self.devices
                return await self.async_step_controls()

        return self.async_show_form(
            step_id="control_menu",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(SelectSelectorConfig(options=["edit", "delete"], custom_value=False, mode=SelectSelectorMode.DROPDOWN, translation_key={"edit": "Edit Control", "delete": "Delete Control"})),
            }),
            last_step=False,
        )

    async def async_step_control(self, user_input=None):
        errors = {}
        device_data = next((d for d in self.devices if d[CONF_ID] == self.current_device_id), {})
        controls = device_data.get(CONF_CONTROLS, [])
        control_data = {}
        if self.current_control_id:
            control_data = next((c for c in controls if c[CONF_ID] == self.current_control_id), {})

        if user_input is not None:
            control_data[CONF_LABEL] = user_input[CONF_LABEL]
            control_data[CONF_TYPE] = user_input[CONF_TYPE]
            control_data[CONF_ENTITY] = user_input[CONF_ENTITY]
            control_data[CONF_MIN] = user_input.get(CONF_MIN)
            control_data[CONF_MAX] = user_input.get(CONF_MAX)
            control_data[CONF_STEP] = user_input.get(CONF_STEP)
            control_data[CONF_OPTIONS] = user_input.get(CONF_OPTIONS)

            if not self.current_control_id:
                control_data[CONF_ID] = str(uuid.uuid4())
                controls.append(control_data)
            
            device_data[CONF_CONTROLS] = controls
            self.options[CONF_DEVICES] = self.devices
            self.current_control_id = None
            return await self.async_step_controls()

        return self.async_show_form(
            step_id="control",
            data_schema=vol.Schema({
                vol.Required(CONF_LABEL, default=control_data.get(CONF_LABEL, "")): TextSelector(),
                vol.Required(CONF_TYPE, default=control_data.get(CONF_TYPE, "switch")): SelectSelector(
                    SelectSelectorConfig(options=CONTROL_TYPES, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(CONF_ENTITY, default=control_data.get(CONF_ENTITY, "")): EntitySelector(),
                vol.Optional(CONF_MIN, default=control_data.get(CONF_MIN, 0)): NumberSelector(NumberSelectorConfig(min=0, max=1000, step=1, mode="slider")),
                vol.Optional(CONF_MAX, default=control_data.get(CONF_MAX, 100)): NumberSelector(NumberSelectorConfig(min=0, max=1000, step=1, mode="slider")),
                vol.Optional(CONF_STEP, default=control_data.get(CONF_STEP, 1)): NumberSelector(NumberSelectorConfig(min=1, max=100, step=1, mode="slider")),
                vol.Optional(CONF_OPTIONS, default=control_data.get(CONF_OPTIONS, "")): TextSelector(),
            }),
            errors=errors,
        )