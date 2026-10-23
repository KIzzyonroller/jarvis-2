"""Startup checks for installs that break silently (so he can tell you instead of just going deaf)."""


def onnx_problems():
    """ONNX Runtime runs his speech detection, voice and Whisper's silence trimming. pip can end up with
    two versions on top of each other (e.g. after a GPU experiment), which breaks all of them at once."""
    problems = []
    try:
        from importlib import metadata
        names = sorted({(d.metadata["Name"] or "").lower() for d in metadata.distributions()
                        if (d.metadata["Name"] or "").lower().startswith("onnxruntime")})
        if len(names) > 1:
            problems.append("several ONNX Runtime versions are installed on top of each other (" + ", ".join(names) + ")")
        elif names and names[0] != "onnxruntime":
            problems.append(f"a GPU build of ONNX Runtime ({names[0]}) is installed from an old GPU experiment; "
                            "he forces the CPU so it still works, but it's worth cleaning up")
    except Exception:
        pass
    try:
        import onnxruntime
        onnxruntime.get_available_providers()
    except Exception as e:
        problems.append(f"ONNX Runtime won't load ({type(e).__name__}: {str(e)[:120]})")
    return problems
