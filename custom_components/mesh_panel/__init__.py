import logging
import json
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import mqtt

from .const import DOMAIN
from .panel_manager import MeshPanelManager

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Mesh Panel component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Mesh Panel from a config entry."""
    manager = MeshPanelManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = manager
    
    await manager.async_setup()
    
    # Listen for config updates (when user changes YAML layout)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    manager = hass.data[DOMAIN].pop(entry.entry_id)
    await manager.async_unload()
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

# ================= AUTO DISCOVERY LOGIC =================
async def async_setup_discovery(hass: HomeAssistant):
    """Listen for discovery messages."""
    
    async def message_received(msg):
        try:
            payload = json.loads(msg.payload)
            panel_id = payload.get("panel_id")
            if not panel_id:
                return
            
            # Check if already exists
            current_entries = hass.config_entries.async_entries(DOMAIN)
            for entry in current_entries:
                if entry.unique_id == panel_id:
                    return # Already configured

            # Trigger Config Flow
            await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "discovery"},
                data={"panel_id": panel_id, "ip": payload.get("ip")}
            )
        except Exception as e:
            _LOGGER.error(f"Error processing discovery: {e}")

    await mqtt.async_subscribe(hass, "smartpanel/announce", message_received)

# Hook discovery start into Home Assistant startup
async def async_setup_global_discovery(hass, config):
    await async_setup_discovery(hass)
    return True