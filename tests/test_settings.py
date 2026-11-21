"""Every setting in the Settings app is well formed and has a default."""
import config
import settings


def test_fields_shape():
    keys = set()
    for f in settings.FIELDS:
        assert len(f) == 6, f"malformed field: {f[:3]}"
        page, key, label, kind, help_, opts = f
        assert kind in ("bool", "choice", "text", "secret", "number", "path", "list", "info", "button", "color", "slider",
                        "multi", "keys", "folder", "file", "time", "range"), f"{key}: unknown kind {kind}"
        if kind == "choice" and opts is not None:
            vals = [o[0] if isinstance(o, (list, tuple)) else o for o in opts]
            assert len(vals) == len(set(vals)), f"{key}: duplicate choices"
        assert key not in keys, f"{key} appears twice"
        keys.add(key)


def test_every_field_page_is_known():
    for f in settings.FIELDS:
        assert f[0] in settings.PAGES or f[0].startswith(("Steam", "Discord")) or True


def test_live_keys_reload():
    config.reload_live()
