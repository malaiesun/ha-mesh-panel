import logging
import json
import yaml
from homeassistant.core import HomeAssistant, callback, Context
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType
from homeassistant.components import mqtt
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR
from homeassistant.const import (
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    ATTR_ENTITY_ID,
)

from .const import CONF_PANEL_ID, CONF_LAYOUT, DEFAULT_LAYOUT

_LOGGER = logging.getLogger(__name__)

def _coerce_layout(layout_str: str) -> dict:
    """Accept JSON or YAML, return dict with {'devices': [...]}."""
    if not layout_str or not layout_str.strip():
        layout_str = DEFAULT_LAYOUT
    try:
        # Try JSON first
        data = json.loads(layout_str)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    try:
        data = yaml.safe_load(layout_str)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"devices": []}

class MeshPanelManager:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.panel_id = entry.data[CONF_PANEL_ID]
        self.layout_raw = entry.options.get(CONF_LAYOUT, DEFAULT_LAYOUT)
        self.entities_to_watch = set()
        self._unsub = []
        self._mqtt_unsub = None

    async def async_setup(self):
        cfg = _coerce_layout(self.layout_raw)
        devices = cfg.get("devices", [])

        # collect entities to watch
        self.entities_to_watch.clear()
        for dev in devices:
            se = dev.get("state_entity")
            if se:
                self.entities_to_watch.add(se)
            for c in dev.get("controls", []):
                ent = c.get("entity")
                if ent:
                    self.entities_to_watch.add(ent)

        # subscribe to actions
        topic = f"smartpanel/{self.panel_id}/action"
        self._mqtt_unsub = await mqtt.async_subscribe(self.hass, topic, self._handle_action)

        # listen entity state changes
        if self.entities_to_watch:
            self._unsub.append(
                async_track_state_change_event(
                    self.hass, list(self.entities_to_watch), self._handle_state_event
                )
            )

        # publish UI (retain)
        await mqtt.async_publish(self.hass, f"smartpanel/{self.panel_id}/ui", json.dumps(cfg), retain=True)

        # push current state for all entities
        for ent in self.entities_to_watch:
            s = self.hass.states.get(ent)
            if s:
                await self._push_state(ent, s.state, s.attributes)

    async def async_unload(self):
        if self._mqtt_unsub:
            self._mqtt_unsub()
        for u in self._unsub:
            try:
                u()
            except Exception:
                pass
        self._unsub.clear()

    # ---------- inbound actions from panel ----------
    async def _handle_action(self, msg):
        try:
            data = json.loads(msg.payload or "{}")
        except Exception:
            return

        entity_id = data.get("id")
        if not entity_id:
            return

        domain = entity_id.split(".", 1)[0]
        service = None
        service_data = {ATTR_ENTITY_ID: entity_id}

        if "state" in data:
            service = SERVICE_TURN_ON if str(data["state"]).lower() == "on" else SERVICE_TURN_OFF

        elif "value" in data:
            val = int(data["value"])
            if domain == "light":
                service = SERVICE_TURN_ON
                service_data[ATTR_BRIGHTNESS] = val
            elif domain == "fan":
                # Prefer percentage/oscillation if available, fall back to turn_on
                service = SERVICE_TURN_ON
                service_data["percentage"] = val
            elif domain == "cover":
                service = "set_cover_position"
                service_data["position"] = val
            elif domain in ("number", "input_number"):
                service = "set_value"
                service_data["value"] = val
            elif domain == "media_player":
                service = "volume_set"
                service_data["volume_level"] = val / 100.0

        elif "rgb_color" in data:
            if domain == "light":
                service = SERVICE_TURN_ON
                service_data[ATTR_RGB_COLOR] = data["rgb_color"]

        elif "option" in data:
            if domain in ("select", "input_select"):
                service = "select_option"
                service_data["option"] = data["option"]
            elif domain == "media_player":
                service = "select_source"
                service_data = {"entity_id": entity_id, "source": data["option"]}

        if service:
            await self.hass.services.async_call(domain, service, service_data, blocking=False, context=Context())

    # ---------- push updates to panel ----------
    @callback
    async def _handle_state_event(self, event):
        s = event.data.get("new_state")
        if not s:
            return
        await self._push_state(event.data["entity_id"], s.state, s.attributes)

    async def _push_state(self, entity_id: str, state: StateType, attrs: dict):
        topic = f"smartpanel/{self.panel_id}/state"
        payload = {"entity": entity_id, "state": state}

        if ATTR_BRIGHTNESS in attrs:
            payload["value"] = int(attrs[ATTR_BRIGHTNESS])
        elif "current_position" in attrs:
            payload["value"] = int(attrs["current_position"])
        elif "volume_level" in attrs:
            try:
                payload["value"] = int(float(attrs["volume_level"]) * 100)
            except Exception:
                pass

        # color
        if ATTR_RGB_COLOR in attrs:
            try:
                r, g, b = attrs[ATTR_RGB_COLOR]
                payload["rgb_color"] = [int(r), int(g), int(b)]
            except Exception:
                pass

        await mqtt.async_publish(self.hass, topic, json.dumps(payload))
