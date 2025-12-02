import json
import logging
import yaml
from homeassistant.const import (
    SERVICE_TURN_ON, SERVICE_TURN_OFF, 
    ATTR_ENTITY_ID, ATTR_BRIGHTNESS, ATTR_RGB_COLOR
)
from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, CONF_TOPIC, CONF_MANUAL_CONFIG, DEFAULT_TOPIC

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    topic_base = entry.data.get(CONF_TOPIC, DEFAULT_TOPIC)
    
    # Load manual config from options, or fallback to empty
    manual_config_str = entry.options.get(CONF_MANUAL_CONFIG, "")
    devices_data = []
    if manual_config_str:
        try:
            devices_data = yaml.safe_load(manual_config_str)
        except Exception as e:
            _LOGGER.error(f"Failed to parse Smart Panel config: {e}")

    controller = SmartPanelController(hass, topic_base, devices_data)
    await controller.start()
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return True

class SmartPanelController:
    def __init__(self, hass, topic, devices_config):
        self.hass = hass
        self.topic_ui = f"{topic}/ui"
        self.topic_state = f"{topic}/state"
        self.topic_action = f"{topic}/action"
        self.devices_config = devices_config
        self.watched_entities = set()

    async def start(self):
        # 1. Listen for clicks
        await mqtt.async_subscribe(self.hass, self.topic_action, self.handle_action)
        await self.register_services()
        # 2. Collect all entities to watch for state changes
        if self.devices_config:
            for dev in self.devices_config:
                if "state_entity" in dev:
                    self.watched_entities.add(dev["state_entity"])
                for c in dev.get("controls", []):
                    if "entity" in c:
                        self.watched_entities.add(c["entity"])

            # 3. Subscribe to HA State Machine
            if self.watched_entities:
                async_track_state_change_event(
                    self.hass, list(self.watched_entities), self.handle_ha_state_change
                )

            # 4. Push initial UI
            await self.publish_ui()

    async def publish_ui(self):
        # Convert YAML config style to ESP32 JSON style
        # (They are nearly identical, just need to ensure keys match)
        payload = {"devices": self.devices_config}
        await mqtt.async_publish(self.hass, self.topic_ui, json.dumps(payload), retain=True)

    async def handle_action(self, msg):
        try:
            data = json.loads(msg.payload)
            entity_id = data.get("id")
            domain = entity_id.split('.')[0]
            service_data = {ATTR_ENTITY_ID: entity_id}
            service = None

            # SWITCH
            if "state" in data:
                service = SERVICE_TURN_ON if data["state"] == "on" else SERVICE_TURN_OFF
            
            # SLIDER (Brightness/Volume/Number)
            elif "value" in data:
                val = int(data["value"])
                if domain == "light":
                    service = SERVICE_TURN_ON
                    service_data[ATTR_BRIGHTNESS] = val
                elif domain == "fan":
                    service = SERVICE_TURN_ON
                    service_data["percentage"] = val
                elif domain == "number" or domain == "input_number":
                    service = "set_value"
                    service_data["value"] = val
                elif domain == "media_player":
                    service = "volume_set"
                    service_data["volume_level"] = val / 100.0 if val > 1 else val
                elif domain == "cover":
                    service = "set_cover_position"
                    service_data["position"] = val
                elif domain == "climate":
                    service = "set_temperature"
                    service_data["temperature"] = val

            # COLOR
            elif "rgb_color" in data:
                service = SERVICE_TURN_ON
                service_data[ATTR_RGB_COLOR] = data["rgb_color"]

            # DROPDOWN
            elif "option" in data:
                opt = data["option"]
                if domain == "select" or domain == "input_select":
                    service = "select_option"
                    service_data["option"] = opt
                elif domain == "media_player":
                    service = "select_source"
                    service_data["source"] = opt
                elif domain == "climate":
                    service = "set_hvac_mode"
                    service_data["hvac_mode"] = opt

            if service:
                await self.hass.services.async_call(domain, service, service_data)

        except Exception as e:
            _LOGGER.error(f"ESP32 Panel Action Error: {e}")

    @callback
    async def handle_ha_state_change(self, event):
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        if not new_state: return

        # 1. Basic State
        payload = {"entity": entity_id, "state": new_state.state}
        await mqtt.async_publish(self.hass, self.topic_state, json.dumps(payload))

        # 2. Attributes (Sync Slider/Color)
        attributes = new_state.attributes
        
        # Brightness
        if "brightness" in attributes:
            p = {"entity": entity_id, "value": attributes["brightness"]}
            await mqtt.async_publish(self.hass, self.topic_state, json.dumps(p))
        
        # Volume
        if "volume_level" in attributes:
            vol = int(attributes["volume_level"] * 100)
            p = {"entity": entity_id, "value": vol}
            await mqtt.async_publish(self.hass, self.topic_state, json.dumps(p))

        # Fan Speed
        if "percentage" in attributes:
            p = {"entity": entity_id, "value": attributes["percentage"]}
            await mqtt.async_publish(self.hass, self.topic_state, json.dumps(p))

        # Cover Position
        if "current_position" in attributes:
            p = {"entity": entity_id, "value": attributes["current_position"]}
            await mqtt.async_publish(self.hass, self.topic_state, json.dumps(p))

        # RGB
        if "rgb_color" in attributes:
            p = {"entity": entity_id, "rgb_color": attributes["rgb_color"]}
            await mqtt.async_publish(self.hass, self.topic_state, json.dumps(p))
            
    async def register_services(self):
        """Register custom services."""
        async def handle_send_notification(call):
            title = call.data.get("title")
            message = call.data.get("message")
            duration = call.data.get("duration", 5000)
            
            payload = {
                "title": title,
                "message": message,
                "duration": duration
            }
            await mqtt.async_publish(self.hass, self.topic_notify, json.dumps(payload))

        self.hass.services.async_register(DOMAIN, "send_notification", handle_send_notification)