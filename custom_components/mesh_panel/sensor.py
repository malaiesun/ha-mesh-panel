"""Sensor platform for mesh_panel."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo


from .const import DOMAIN, SIGNAL_MQTT_PAYLOAD, CONF_PANEL_ID


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    panel_id = entry.data[CONF_PANEL_ID]
    async_add_entities([MqttPayloadSensor(hass, entry, panel_id)])


class MqttPayloadSensor(SensorEntity):
    """Mqtt Payload Sensor class."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, panel_id: str) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._panel_id = panel_id
        self._attr_name = "Mesh Panel MQTT Payload"
        self._attr_unique_id = f"{entry.entry_id}_mqtt_payload"
        self._attr_should_poll = False
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._panel_id)},
            name=f"MESH Panel ({self._panel_id})",
            manufacturer="MESH",
            model="Smart Panel",
            sw_version="1.0",
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, SIGNAL_MQTT_PAYLOAD, self._async_update_payload
            )
        )

    @callback
    def _async_update_payload(self, payload: str) -> None:
        """Update the payload."""
        self._attr_native_value = payload
        self.async_write_ha_state()
