"""
His worlds, as one list: what each desktop scene is called, and the colour your lights take when you switch to it
(Settings > His desktop > Lights match his world).

The light colours are the warm or bright colour each scene is built around (the lamp, the stars, the scope), picked
so a room still looks like a room. They match the scene's accent in ui/scenes/scenes.js; a test checks that.

What can't be matched: Discord (an app's theme isn't something another program can set), and the main HUD, whose
colours belong to the persona you picked.
"""
import threading

import config

WORLDS = {
    "bench": ("the drafting bench", "#ffb347"),       # the lamp over his drawings
    "station": ("the orbital station", "#7fe7ff"),    # starlight off the window
    "archive": ("the archive", "#7fd6ff"),            # moonlight through the tall windows
    "signal": ("the listening post", "#ffcf5d"),      # the amber of the meters
    "chart": ("the cartographer's map", "#ff9f5a"),   # the route inked across the sea
    "greenhouse": ("the greenhouse", "#ffc46b"),      # the bulbs strung under the glass
}

_last = {"scene": None}


def light_colour(scene):
    return WORLDS.get(scene, WORLDS["bench"])[1]


def match_lights(scene, wait=False):
    """Put the RGB and smart lights in the world's colour. Quiet when there's nothing to set; never raises."""
    if not config.WORLD_LIGHTS or scene not in WORLDS:
        return None
    _last["scene"] = scene
    col = light_colour(scene)
    said = []

    def go():
        try:
            import rgb
            names, _ = rgb._pick("auto")
            if names:
                said.append(rgb.control("color", color=col))
        except Exception as e:
            print(f"[worlds] rgb: {type(e).__name__}: {e}")
        try:
            import smarthome
            av = smarthome.available()
            if av.get("hue") or av.get("ha"):
                said.append(smarthome.control("color", config.LIGHTS_SYNC_TARGET or "all", color=col))
        except Exception as e:
            print(f"[worlds] lights: {type(e).__name__}: {e}")
    if wait:
        go()
        return said
    threading.Thread(target=go, daemon=True, name="world-lights").start()
    return None
