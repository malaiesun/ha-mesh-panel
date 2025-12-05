"""
Options Flow for MESH Smart Panel
Handles devices + controls + proper slider attribute encoding.
"""
import logging
import uuid
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    TextSelector,
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    EntitySelector,
    IconSelector,
    NumberSelector, NumberSelectorConfig,
)

from .const import *

_LOGGER = logging.getLogger(__name__)


class MeshPanelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles visual editor for the panel."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.current_device_id = None
        self.current_control_id = None
        self.control_data = {}

    async def async_step_init(self, user_input=None):
        """Initial menu: list devices/add."""
        if user_input:
            action = user_input["action"]
            if action == "add":
                self.current_device_id = None
                return await self.async_step_device()
            else:
                self.current_device_id = action
                return await self.async_step_device_menu()

        devices = self.options.get(CONF_DEVICES, [])
        dev_map = {d[CONF_ID]: d[CONF_NAME] for d in devices}

        options = {"add": "Add a new device", **dev_map}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action", default="add"): vol.In(options)
            })
        )

    async def async_step_device_menu(self, user_input=None):
        if user_input:
            a = user_input["action"]
            if a == "edit":
                return await self.async_step_device()
            if a == "delete":
                devices = [d for d in self.options.get(CONF_DEVICES, [])
                           if d[CONF_ID] != self.current_device_id]
                self.options[CONF_DEVICES] = devices
                return self.async_create_entry(title="", data=self.options)
            if a == "controls":
                return await self.async_step_controls()
            if a == "back":
                return await self.async_step_init()

        return self.async_show_form(
            step_id="device_menu",
            data_schema=vol.Schema({
                vol.Required("action"):
                    vol.In({
                        "edit": "Edit Device",
                        "delete": "Delete Device",
                        "controls": "Manage Controls",
                        "back": "Back",
                    })
            })
        )

    async def async_step_device(self, user_input=None):
        device_data = {}
        if self.current_device_id:
            device_data = next(
                (d for d in self.options.get(CONF_DEVICES, [])
                 if d[CONF_ID] == self.current_device_id), {}
            )

        if user_input:
            devices = self.options.get(CONF_DEVICES, [])

            if self.current_device_id:
                # Edit
                for i, d in enumerate(devices):
                    if d[CONF_ID] == self.current_device_id:
                        devices[i] = {**d, **user_input}
                        break
            else:
                # Add new device
                user_input[CONF_ID] = str(uuid.uuid4())
                user_input[CONF_CONTROLS] = []
                devices.append(user_input)
                self.current_device_id = user_input[CONF_ID]

            self.options[CONF_DEVICES] = devices
            return await self.async_step_device_menu()

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=device_data.get(CONF_NAME, "")): TextSelector(),
                vol.Required(CONF_ICON, default=device_data.get(CONF_ICON, "mdi:power")): IconSelector(),
            })
        )

    async def async_step_controls(self, user_input=None):
        device = next(
            (d for d in self.options.get(CONF_DEVICES, [])
             if d[CONF_ID] == self.current_device_id), {}
        )
        controls = device.get(CONF_CONTROLS, [])

        if user_input:
            a = user_input["action"]
            if a == "add":
                self.current_control_id = None
                self.control_data = {}
                return await self.async_step_control()
            if a == "back":
                return await self.async_step_device_menu()

            # open existing control
            self.current_control_id = a
            return await self.async_step_control_menu()

        ctrl_map = {c[CONF_ID]: c[CONF_LABEL] for c in controls}
        options = {"add": "Add a new control", **ctrl_map, "back": "Back"}

        return self.async_show_form(
            step_id="controls",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(options)
            })
        )

    async def async_step_control_menu(self, user_input=None):
        if user_input:
            a = user_input["action"]
            if a == "edit":
                return await self.async_step_control()
            if a == "delete":
                devices = self.options.get(CONF_DEVICES, [])
                for d in devices:
                    if d[CONF_ID] == self.current_device_id:
                        d[CONF_CONTROLS] = [
                            c for c in d[CONF_CONTROLS]
                            if c[CONF_ID] != self.current_control_id
                        ]
                return await self.async_step_controls()
            if a == "back":
                return await self.async_step_controls()

        return self.async_show_form(
            step_id="control_menu",
            data_schema=vol.Schema({
                vol.Required("action"):
                    vol.In({
                        "edit": "Edit Control",
                        "delete": "Delete Control",
                        "back": "Back",
                    })
            })
        )

    async def async_step_control(self, user_input=None):
        # load existing for edit
        if self.current_control_id:
            device = next(
                (d for d in self.options.get(CONF_DEVICES, [])
                 if d[CONF_ID] == self.current_device_id), {}
            )
            controls = device.get(CONF_CONTROLS, [])
            self.control_data = next(
                (c for c in controls if c[CONF_ID] == self.current_control_id), {}
            )

        if user_input:
            self.control_data.update(user_input)

            if self.control_data[CONF_TYPE] == "slider":
                return await self.async_step_control_slider()

            if self.control_data[CONF_TYPE] == "select":
                return await self.async_step_control_select()

            return await self._save_control()

        return self.async_show_form(
            step_id="control",
            data_schema=vol.Schema({
                vol.Required(CONF_LABEL, default=self.control_data.get(CONF_LABEL, "")): TextSelector(),
                vol.Required(CONF_TYPE, default=self.control_data.get(CONF_TYPE, "switch")):
                    SelectSelector(SelectSelectorConfig(options=CONTROL_TYPES, mode=SelectSelectorMode.DROPDOWN)),
                vol.Required(CONF_ENTITY, default=self.control_data.get(CONF_ENTITY, "")): EntitySelector(),
            })
        )

    async def async_step_control_slider(self, user_input=None):
        if user_input:
            self.control_data.update(user_input)
            return await self._save_control()

        attributes = ["state"]
        ent = self.control_data.get(CONF_ENTITY)
        if ent:
            entity = self.hass.states.get(ent)
            if entity:
                attributes.extend(entity.attributes.keys())

        return self.async_show_form(
            step_id="control_slider",
            data_schema=vol.Schema({
                vol.Optional(CONF_MIN, default=self.control_data.get(CONF_MIN, 0)):
                    NumberSelector(NumberSelectorConfig(min=0, max=1000, step=1)),
                vol.Optional(CONF_MAX, default=self.control_data.get(CONF_MAX, 100)):
                    NumberSelector(NumberSelectorConfig(min=0, max=1000, step=1)),
                vol.Optional(CONF_STEP, default=self.control_data.get(CONF_STEP, 1)):
                    NumberSelector(NumberSelectorConfig(min=1, max=100, step=1)),
                vol.Optional("attribute", default=self.control_data.get("attribute", "state")):
                    vol.In(attributes),
            })
        )

    async def async_step_control_select(self, user_input=None):
        if user_input:
            self.control_data.update(user_input)
            return await self._save_control()

        return self.async_show_form(
            step_id="control_select",
            data_schema=vol.Schema({
                vol.Optional(CONF_OPTIONS, default=self.control_data.get(CONF_OPTIONS, "")):
                    TextSelector(),
            })
        )

    async def _save_control(self):
        """Encode slider entity as 'entity (attribute)' and save control."""
        devices = self.options.get(CONF_DEVICES, [])
        device = next((d for d in devices if d[CONF_ID] == self.current_device_id), None)
        if not device:
            return self.async_abort(reason="unknown")

        # Convert select: comma → newline
        if self.control_data.get(CONF_TYPE) == "select":
            opts = self.control_data.get(CONF_OPTIONS, "")
            if opts:
                opts = [o.strip() for o in opts.split(",")]
                self.control_data[CONF_OPTIONS] = "\n".join(opts)

        # Encode sliders
        if self.control_data.get(CONF_TYPE) == "slider":
            ent = self.control_data.get(CONF_ENTITY, "")
            attr = self.control_data.get("attribute")

            if attr and attr != "state":
                encoded = f"{ent} ({attr})"
            else:
                encoded = ent

            self.control_data[CONF_ENTITY] = encoded

        # Save control
        controls = device.get(CONF_CONTROLS, [])

        if self.current_control_id:
            for i, c in enumerate(controls):
                if c[CONF_ID] == self.current_control_id:
                    controls[i] = self.control_data
                    break
        else:
            self.control_data[CONF_ID] = str(uuid.uuid4())
            controls.append(self.control_data)

        device[CONF_CONTROLS] = controls
        self.options[CONF_DEVICES] = devices

        return self.async_create_entry(title="", data=self.options)
