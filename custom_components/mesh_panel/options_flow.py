"""Options flow for MESH Smart Home Panel (visual + raw YAML/JSON, kept in sync)."""
import logging
import uuid
import json
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    EntitySelector,
    IconSelector,
    NumberSelector, NumberSelectorConfig,
    TextSelector, TextSelectorConfig,  # keep available if you use elsewhere
)

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_RAW_YAML, CONF_RAW_JSON,
    CONF_ID, CONF_NAME, CONF_ICON, CONF_CONTROLS,
    CONF_LABEL, CONF_TYPE, CONF_ENTITY,
    CONF_MIN, CONF_MAX, CONF_STEP, CONF_OPTIONS, CONF_ATTRIBUTE,
    CONTROL_TYPES,
)

_LOGGER = logging.getLogger(__name__)

try:
    import yaml  # Home Assistant bundles PyYAML
except Exception:  # pragma: no cover
    yaml = None


def _pretty_json(devices: list) -> str:
    return json.dumps({"devices": devices or []}, indent=2, ensure_ascii=False)


def _pretty_yaml(devices: list) -> str:
    if not yaml:
        return "devices: []\n" if not devices else _pretty_json(devices)
    return yaml.safe_dump({"devices": devices or []}, sort_keys=False)


def _ensure_ids(devices: list) -> list:
    """Ensure every device and control has a stable UUID."""
    for d in devices or []:
        d.setdefault(CONF_ID, str(uuid.uuid4()))
        d.setdefault(CONF_CONTROLS, [])
        for c in d[CONF_CONTROLS]:
            c.setdefault(CONF_ID, str(uuid.uuid4()))
    return devices


def _validate_devices(devices: list):
    """Validate minimal structure; raise ValueError on problems."""
    if not isinstance(devices, list):
        raise ValueError("devices must be a list")
    for d in devices:
        if not isinstance(d, dict):
            raise ValueError("device must be an object")
        for key in (CONF_NAME, CONF_ICON, CONF_CONTROLS, CONF_ID):
            if key not in d:
                raise ValueError(f"device missing key: {key}")
        if not isinstance(d[CONF_CONTROLS], list):
            raise ValueError("controls must be a list")
        for c in d[CONF_CONTROLS]:
            if not isinstance(c, dict):
                raise ValueError("control must be an object")
            for key in (CONF_ID, CONF_LABEL, CONF_TYPE, CONF_ENTITY):
                if key not in c:
                    raise ValueError(f"control missing key: {key}")


def _parse_raw_to_devices(raw: str) -> list:
    """Accept YAML or JSON; return devices list or raise ValueError."""
    raw = (raw or "").strip()
    if not raw:
        return []
    data = None
    # Try JSON first
    try:
        data = json.loads(raw)
    except Exception:
        # Try YAML
        if yaml:
            try:
                data = yaml.safe_load(raw)
            except Exception as e:
                raise ValueError(f"Invalid YAML/JSON: {e}") from e
        else:
            raise ValueError("Invalid JSON (YAML not available)")
    if not isinstance(data, dict) or "devices" not in data:
        raise ValueError("Root must be an object with a 'devices' key")
    devices = data.get("devices") or []
    devices = _ensure_ids(devices)
    _validate_devices(devices)
    return devices


class MeshPanelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for MESH Panel with visual + raw editors."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry
        # Work on a copy; persist only on Done or raw editor submit
        self.options = dict(config_entry.options)
        self.options.setdefault(CONF_DEVICES, [])
        self.options.setdefault(CONF_RAW_YAML, _pretty_yaml(self.options.get(CONF_DEVICES, [])))
        self.options.setdefault(CONF_RAW_JSON, _pretty_json(self.options.get(CONF_DEVICES, [])))

        self.current_device_id = None
        self.current_control_id = None
        self.control_data = {}

    # ----------------- TOP MENU -----------------
    async def async_step_init(self, user_input=None):
        """Top menu: Visual / YAML / JSON only."""
        self._sync_raw_from_devices()

        if user_input is not None:
            action = user_input["action"]
            if action == "visual":
                return await self.async_step_visual()
            if action == "yaml":
                return await self.async_step_yaml_editor()
            if action == "json":
                return await self.async_step_json_editor()

        options = [
            {"label": "Visual Editor", "value": "visual"},
            {"label": "YAML Editor", "value": "yaml"},
            {"label": "JSON Editor", "value": "json"},
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            })
        )

    # ----------------- VISUAL EDITOR MENU -----------------
    async def async_step_visual(self, user_input=None):
        """Visual editor main menu: Add device / list devices / Done."""
        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                self.current_device_id = None
                return await self.async_step_device()
            if action == "done":
                # Persist changes
                self._sync_raw_from_devices()
                return self.async_create_entry(title="", data=self.options)
            # clicked a device id -> device menu
            self.current_device_id = action
            return await self.async_step_device_menu()

        devices = self.options.get(CONF_DEVICES, []) or []
        device_map = {d[CONF_ID]: d[CONF_NAME] for d in devices}

        options = [{"label": "Add Device", "value": "add"}]
        options += [{"label": name, "value": dev_id} for dev_id, name in device_map.items()]
        options += [{"label": "Done", "value": "done"}]

        return self.async_show_form(
            step_id="visual",
            data_schema=vol.Schema({
                vol.Required("action", default="add"): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            })
        )

    # ----------------- DEVICE MENU -----------------
    async def async_step_device_menu(self, user_input=None):
        if user_input is not None:
            action = user_input["action"]
            if action == "edit":
                return await self.async_step_device()
            if action == "delete":
                devices = [d for d in self.options.get(CONF_DEVICES, []) if d[CONF_ID] != self.current_device_id]
                self.options[CONF_DEVICES] = devices
                # Stay in visual editor; don't persist yet
                return await self.async_step_visual()
            if action == "controls":
                return await self.async_step_controls()
            if action == "back":
                return await self.async_step_visual()

        options = [
            {"label": "Edit Device", "value": "edit"},
            {"label": "Delete Device", "value": "delete"},
            {"label": "Manage Controls", "value": "controls"},
            {"label": "Back", "value": "back"},
        ]

        return self.async_show_form(
            step_id="device_menu",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(SelectSelectorConfig(options=options))
            })
        )

    # ----------------- ADD / EDIT DEVICE -----------------
    async def async_step_device(self, user_input=None):
        """Add or edit a device. New device -> go straight to controls. Edit -> back to device menu."""
        errors = {}
        device_data = {}
        is_edit = self.current_device_id is not None

        if is_edit:
            device_data = next(
                (d for d in self.options.get(CONF_DEVICES, []) if d[CONF_ID] == self.current_device_id),
                {}
            )

        if user_input is not None:
            devices = self.options.get(CONF_DEVICES, [])
            if is_edit:
                for i, d in enumerate(devices):
                    if d[CONF_ID] == self.current_device_id:
                        devices[i] = {**d, **user_input}
                        break
                self.options[CONF_DEVICES] = _ensure_ids(devices)
                # Don’t persist; return to device menu
                return await self.async_step_device_menu()
            else:
                # New device → assign id + empty controls, then go to controls for this device
                user_input.setdefault(CONF_ID, str(uuid.uuid4()))
                user_input.setdefault(CONF_CONTROLS, [])
                devices.append(user_input)
                self.options[CONF_DEVICES] = _ensure_ids(devices)
                self.current_device_id = user_input[CONF_ID]
                # Go immediately to controls for this new device
                return await self.async_step_controls()

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=device_data.get(CONF_NAME, "")): str,
                vol.Required(CONF_ICON, default=device_data.get(CONF_ICON, "mdi:power")): IconSelector(),
            }),
            errors=errors
        )

    # ----------------- CONTROLS LIST -----------------
    async def async_step_controls(self, user_input=None):
        """List controls for current device; allow add/edit/delete/back."""
        device = next((d for d in self.options.get(CONF_DEVICES, []) if d[CONF_ID] == self.current_device_id), {})
        controls = device.get(CONF_CONTROLS, [])

        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                self.current_control_id = None
                self.control_data = {}
                return await self.async_step_control()
            if action == "back":
                return await self.async_step_device_menu()
            # action is control id → control menu
            self.current_control_id = action
            return await self.async_step_control_menu()

        control_map = {c[CONF_ID]: c[CONF_LABEL] for c in controls}
        options = [{"label": "Add Control", "value": "add"}]
        options += [{"label": v, "value": k} for k, v in control_map.items()]
        options += [{"label": "Back", "value": "back"}]

        return self.async_show_form(
            step_id="controls",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(SelectSelectorConfig(options=options))
            })
        )

    # ----------------- CONTROL MENU -----------------
    async def async_step_control_menu(self, user_input=None):
        if user_input is not None:
            action = user_input["action"]
            if action == "edit":
                return await self.async_step_control()
            if action == "delete":
                devices = self.options.get(CONF_DEVICES, [])
                for i, d in enumerate(devices):
                    if d[CONF_ID] == self.current_device_id:
                        controls = [c for c in d.get(CONF_CONTROLS, []) if c[CONF_ID] != self.current_control_id]
                        devices[i][CONF_CONTROLS] = controls
                        break
                self.options[CONF_DEVICES] = devices
                # Stay in controls list
                return await self.async_step_controls()
            if action == "back":
                return await self.async_step_controls()

        options = [
            {"label": "Edit Control", "value": "edit"},
            {"label": "Delete Control", "value": "delete"},
            {"label": "Back", "value": "back"},
        ]

        return self.async_show_form(
            step_id="control_menu",
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(SelectSelectorConfig(options=options))
            })
        )

    # ----------------- ADD / EDIT CONTROL -----------------
    async def async_step_control(self, user_input=None):
        errors = {}
        if self.current_control_id:
            device = next((d for d in self.options.get(CONF_DEVICES, []) if d[CONF_ID] == self.current_device_id), {})
            controls = device.get(CONF_CONTROLS, [])
            self.control_data = next((c for c in controls if c[CONF_ID] == self.current_control_id), {})

        if user_input is not None:
            self.control_data.update(user_input)
            if self.control_data[CONF_TYPE] == "slider":
                return await self.async_step_control_slider()
            if self.control_data[CONF_TYPE] == "select":
                return await self.async_step_control_select()
            # Save simple control and return to controls list
            return await self._save_control_and_back_to_controls()

        return self.async_show_form(
            step_id="control",
            data_schema=vol.Schema({
                vol.Required(CONF_LABEL, default=self.control_data.get(CONF_LABEL, "")): str,
                vol.Required(CONF_TYPE, default=self.control_data.get(CONF_TYPE, "switch")):
                    SelectSelector(SelectSelectorConfig(options=CONTROL_TYPES, mode=SelectSelectorMode.DROPDOWN)),
                vol.Required(CONF_ENTITY, default=self.control_data.get(CONF_ENTITY, "")): EntitySelector(),
            }),
            errors=errors
        )

    async def async_step_control_slider(self, user_input=None):
        if user_input is not None:
            self.control_data.update(user_input)
            return await self._save_control_and_back_to_controls()

        attributes = ["state"]
        if self.control_data.get(CONF_ENTITY):
            entity = self.hass.states.get(self.control_data[CONF_ENTITY])
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
                vol.Optional(CONF_ATTRIBUTE, default=self.control_data.get(CONF_ATTRIBUTE, "state")):
                    vol.In(attributes),
            })
        )

    async def async_step_control_select(self, user_input=None):
        if user_input is not None:
            self.control_data.update(user_input)
            return await self._save_control_and_back_to_controls()

        return self.async_show_form(
            step_id="control_select",
            data_schema=vol.Schema({
                # Use plain str to avoid selector crashes on long multiline values
                vol.Optional(CONF_OPTIONS, default=self.control_data.get(CONF_OPTIONS, "")): str,
            }),
            description="Enter one option per line (or comma-separated)."
        )

    # ----------------- HELPERS -----------------
    async def _save_control_and_back_to_controls(self):
        """Save/merge current control; do NOT persist entry yet; go back to controls list."""
        devices = self.options.get(CONF_DEVICES, [])
        device = next((d for d in devices if d[CONF_ID] == self.current_device_id), None)
        if not device:
            # Nothing to do; return to visual to avoid dead-end
            return await self.async_step_visual()

        # Normalize select options: accept commas, store newline-joined
        if self.control_data.get(CONF_TYPE) == "select":
            opts = self.control_data.get(CONF_OPTIONS)
            if isinstance(opts, str) and "," in opts and "\n" not in opts:
                opts = "\n".join([o.strip() for o in opts.split(",") if o.strip()])
            if isinstance(opts, str):
                self.control_data[CONF_OPTIONS] = opts

        controls = device.get(CONF_CONTROLS, [])
        if self.current_control_id:  # edit existing
            for i, c in enumerate(controls):
                if c[CONF_ID] == self.current_control_id:
                    controls[i] = {**c, **self.control_data}
                    break
        else:  # add new
            self.control_data.setdefault(CONF_ID, str(uuid.uuid4()))
            controls.append(self.control_data)

        device[CONF_CONTROLS] = controls
        self.options[CONF_DEVICES] = _ensure_ids(devices)
        # Do not persist now; user will hit Done in visual menu
        return await self.async_step_controls()

    def _sync_raw_from_devices(self):
        """Regenerate raw YAML and JSON from current devices."""
        devices = _ensure_ids(self.options.get(CONF_DEVICES, []))
        try:
            self.options[CONF_RAW_YAML] = _pretty_yaml(devices)
        except Exception as e:  # pragma: no cover
            _LOGGER.debug("YAML dump failed: %s", e)
            self.options[CONF_RAW_YAML] = "devices: []\n" if not devices else _pretty_json(devices)
        self.options[CONF_RAW_JSON] = _pretty_json(devices)

    # ----------------- RAW YAML / JSON EDITORS -----------------
    async def async_step_yaml_editor(self, user_input=None):
        """Raw YAML editor: validate and SAVE immediately on submit."""
        errors = {}
        if user_input is not None:
            raw_text = user_input.get("yaml_text", "")
            try:
                devices = _parse_raw_to_devices(raw_text)
                self.options[CONF_DEVICES] = devices
                self._sync_raw_from_devices()
                return self.async_create_entry(title="", data=self.options)
            except ValueError:
                # Use a standard key so HA shows a proper message
                errors["base"] = "invalid"

        # Use plain str field; HA renders textarea for multiline
        return self.async_show_form(
            step_id="yaml_editor",
            data_schema=vol.Schema({
                vol.Required("yaml_text", default=self.options.get(CONF_RAW_YAML, "")): str
            }),
            errors=errors,
            description="Edit the full configuration in YAML. Saving will validate and update the visual editor."
        )

    async def async_step_json_editor(self, user_input=None):
        """Raw JSON editor: validate and SAVE immediately on submit."""
        errors = {}
        if user_input is not None:
            raw_text = user_input.get("json_text", "")
            try:
                devices = _parse_raw_to_devices(raw_text)
                self.options[CONF_DEVICES] = devices
                self._sync_raw_from_devices()
                return self.async_create_entry(title="", data=self.options)
            except ValueError:
                errors["base"] = "invalid"

        return self.async_show_form(
            step_id="json_editor",
            data_schema=vol.Schema({
                vol.Required("json_text", default=self.options.get(CONF_RAW_JSON, "")): str
            }),
            errors=errors,
            description="Edit the full configuration in JSON. Saving will validate and update the visual editor."
        )
