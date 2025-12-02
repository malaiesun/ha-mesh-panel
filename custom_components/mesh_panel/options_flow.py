import json
import yaml
import voluptuous as vol
from typing import Any, Dict, List, Optional

from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    selector,               # generic
    TextSelector, TextSelectorConfig, TextSelectorType,
)

from .const import DOMAIN, CONF_LAYOUT, DEFAULT_LAYOUT

# ---------- helpers ----------
def _coerce_layout(layout_str: str) -> dict:
    if not layout_str or not layout_str.strip():
        layout_str = DEFAULT_LAYOUT
    try:
        return json.loads(layout_str)
    except Exception:
        pass
    try:
        return yaml.safe_load(layout_str)
    except Exception:
        pass
    return {"devices": []}

def _dump_json_compact(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2)

def _auto_controls_for_entity(hass: HomeAssistant, entity_id: str) -> List[Dict[str, Any]]:
    """Generate sensible controls for common domains."""
    domain = entity_id.split(".", 1)[0]
    st = hass.states.get(entity_id)
    attrs = st.attributes if st else {}

    out: List[Dict[str, Any]] = []

    # Base switch for on/off domains
    if domain in ("light", "switch", "fan", "media_player", "climate", "cover"):
        out.append({"label": "Power", "type": "switch", "entity": entity_id})

    # Light brightness/color
    if domain == "light":
        if "brightness" in attrs or "max_mireds" in attrs or "supported_color_modes" in attrs:
            out.append({"label": "Brightness", "type": "slider", "entity": entity_id, "min": 0, "max": 255, "step": 1})
        # Color if RGB/HS is supported
        scm = attrs.get("supported_color_modes", set())
        if ("hs" in scm) or ("rgb" in scm) or ("xy" in scm) or ("color_temp" in scm) or ("hs_color" in attrs) or ("rgb_color" in attrs):
            out.append({"label": "Color", "type": "color", "entity": entity_id})

    # Fan speed percentage
    if domain == "fan":
        # Many fans expose percentage in attributes (or via set_percentage service)
        out.append({"label": "Speed", "type": "slider", "entity": entity_id, "min": 0, "max": 100, "step": 1})

    # Cover position
    if domain == "cover":
        out.append({"label": "Position", "type": "slider", "entity": entity_id, "min": 0, "max": 100, "step": 1})

    # Media player volume + source
    if domain == "media_player":
        out.append({"label": "Volume", "type": "slider", "entity": entity_id, "min": 0, "max": 100, "step": 1})
        sources = attrs.get("source_list")
        if isinstance(sources, list) and sources:
            out.append({"label": "Source", "type": "select", "entity": entity_id, "options": "\n".join(map(str, sources))})

    # Number/select direct mapping convenience (for “Gaming Setup” etc.)
    if domain in ("number", "input_number"):
        out.append({"label": st.name if st else "Value", "type": "slider", "entity": entity_id, "min": 0, "max": 100, "step": 1})
    if domain in ("select", "input_select"):
        opts = st.attributes.get("options", [])
        if opts:
            out.append({"label": st.name if st else "Mode", "type": "select", "entity": entity_id, "options": "\n".join(map(str, opts))})

    return out

# ---------- Options Flow ----------
class MeshPanelOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry
        self._layout: dict = _coerce_layout(entry.options.get(CONF_LAYOUT, DEFAULT_LAYOUT))
        self._devices: List[dict] = list(self._layout.get("devices", []))
        self._editing_index: Optional[int] = None

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            if user_input["mode"] == "builder":
                return await self.async_step_devices()
            else:
                # raw editor
                return await self.async_step_raw()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("mode", default="builder"): selector({
                    "select": {
                        "options": [
                            {"label": "Visual Builder (Hybrid)", "value": "builder"},
                            {"label": "Raw YAML/JSON", "value": "raw"},
                        ]
                    }
                })
            })
        )

    # ---- Raw editor (for power users / back-compat) ----
    async def async_step_raw(self, user_input=None):
        if user_input is not None:
            # validate
            try:
                _coerce_layout(user_input[CONF_LAYOUT])  # raises if invalid
            except Exception:
                return self.async_show_form(
                    step_id="raw",
                    data_schema=vol.Schema({
                        vol.Required(CONF_LAYOUT, default=user_input[CONF_LAYOUT]): TextSelector(TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT))
                    }),
                    errors={"base": "invalid_yaml_json"}
                )
            return self.async_create_entry(title="", data={CONF_LAYOUT: user_input[CONF_LAYOUT]})

        return self.async_show_form(
            step_id="raw",
            data_schema=vol.Schema({
                vol.Required(CONF_LAYOUT, default=_dump_json_compact({"devices": self._devices})): TextSelector(
                    TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
                )
            })
        )

    # ---- Builder: device list ----
    async def async_step_devices(self, user_input=None):
        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                return await self.async_step_device_add()
            idx = user_input.get("device_index")
            if action == "edit" and idx is not None and 0 <= idx < len(self._devices):
                self._editing_index = idx
                return await self.async_step_device_edit()
            if action == "delete" and idx is not None and 0 <= idx < len(self._devices):
                self._devices.pop(idx)

            if action == "save":
                layout = {"devices": self._devices}
                return self.async_create_entry(title="", data={CONF_LAYOUT: _dump_json_compact(layout)})

        # Build choices
        labels = [f'{i}. {d.get("name","(unnamed)")}  [{len(d.get("controls",[]))} controls]' for i, d in enumerate(self._devices)]
        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema({
                vol.Optional("device_index"): selector({"select": {"options": [str(i) for i in range(len(self._devices))]}}) if self._devices else str,
                vol.Required("action", default="save"): selector({"select": {"options": [
                    {"label": "Save & Apply", "value": "save"},
                    {"label": "Add Device", "value": "add"},
                    {"label": "Edit Selected", "value": "edit"},
                    {"label": "Delete Selected", "value": "delete"},
                ]}}),
            }),
            description_placeholders={
                "devices": "\n".join(labels) if labels else "No devices yet. Add one!"
            }
        )

    # ---- Builder: add device ----
    async def async_step_device_add(self, user_input=None):
        if user_input is not None:
            name = user_input["name"].strip()
            icon = user_input.get("icon", "").strip() or "settings"
            state_entity = user_input.get("state_entity") or ""
            dev = {"name": name, "icon": icon, "state_entity": state_entity, "controls": []}
            self._devices.append(dev)
            self._editing_index = len(self._devices) - 1
            return await self.async_step_device_edit()

        return self.async_show_form(
            step_id="device_add",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Optional("icon", default="settings"): str,
                vol.Optional("state_entity"): selector({"entity": {}}),  # any domain allowed
            })
        )

    # ---- Builder: edit device (add auto/manual controls) ----
    async def async_step_device_edit(self, user_input=None):
        dev = self._devices[self._editing_index]

        if user_input is not None:
            act = user_input["action"]
            if act == "auto":
                entity_id = user_input["entity_auto"]
                dev["controls"].extend(_auto_controls_for_entity(self.hass, entity_id))
            elif act == "manual":
                ctrl = {
                    "label": user_input["label"],
                    "type": user_input["type"],
                    "entity": user_input["entity_manual"],
                }
                if ctrl["type"] == "slider":
                    ctrl["min"] = int(user_input.get("min", 0))
                    ctrl["max"] = int(user_input.get("max", 100))
                    ctrl["step"] = int(user_input.get("step", 1))
                if ctrl["type"] == "select":
                    ctrl["options"] = user_input.get("options", "")
                dev["controls"].append(ctrl)
            elif act == "done":
                return await self.async_step_devices()

        # UI
        return self.async_show_form(
            step_id="device_edit",
            data_schema=vol.Schema({
                vol.Required("action", default="auto"): selector({"select": {"options": [
                    {"label": "Add Auto-Generated Controls from Entity", "value": "auto"},
                    {"label": "Add Manual Control", "value": "manual"},
                    {"label": "Done", "value": "done"},
                ]}}),

                # Auto section
                vol.Optional("entity_auto"): selector({"entity": {}}),

                # Manual section
                vol.Optional("label"): str,
                vol.Optional("type"): selector({"select": {"options": [
                    {"label": "Switch", "value": "switch"},
                    {"label": "Slider", "value": "slider"},
                    {"label": "Color",  "value": "color"},
                    {"label": "Select", "value": "select"},
                ]}}),
                vol.Optional("entity_manual"): selector({"entity": {}}),
                vol.Optional("min", default=0): int,
                vol.Optional("max", default=100): int,
                vol.Optional("step", default=1): int,
                vol.Optional("options", default=""): TextSelector(TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)),
            }),
            description_placeholders={
                "device": f'{dev.get("name")} ({dev.get("icon")})',
                "controls": _dump_json_compact({"controls": dev.get("controls", [])})
            }
        )
