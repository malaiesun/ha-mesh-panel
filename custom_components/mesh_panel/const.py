"""Constants for the Mesh Panel integration."""

DOMAIN = "mesh_panel"
CONF_PANEL_ID = "panel_id"
CONF_LAYOUT = "layout_config"   # JSON string (but YAML still accepted for back-compat)

# A tiny starter layout (still valid if user never opens builder yet)
DEFAULT_LAYOUT = """
{
  "devices": [
    {
      "name": "Living Room",
      "icon": "sofa",
      "state_entity": "sensor.living_room_temperature",
      "controls": [
        { "label": "Main Light", "type": "switch", "entity": "light.living_room_main" },
        { "label": "Brightness", "type": "slider", "entity": "light.living_room_main", "min": 0, "max": 255, "step": 1 },
        { "label": "Color", "type": "color", "entity": "light.living_room_main" }
      ]
    }
  ]
}
"""
