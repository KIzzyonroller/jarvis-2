"""
Keeps keys and passwords in the settings file encrypted with Windows' own per-user protection (DPAPI, the
same thing browsers use for saved passwords). The file then holds "dpapi:..." gibberish instead of your key:
someone who copies the file to another PC, or another Windows user, can't read it. Programs running as YOU on
this PC still can (that's true of every password manager without a master password), so it protects against
the file leaking, not against malware already on your PC.

Off Windows (or if DPAPI fails) values are stored as they are, so nothing ever gets lost.
"""
import base64
import sys

PREFIX = "dpapi:"


def _api():
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob), ctypes.c_void_p,
                                       ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(Blob),
                                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    return ctypes, Blob, crypt, kernel


def _run(fn_name, data):
    ctypes, Blob, crypt, kernel = _api()
    buf = ctypes.create_string_buffer(data, len(data))
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    fn = getattr(crypt, fn_name)
    if fn_name == "CryptProtectData":
        ok = fn(ctypes.byref(src), "Jarvis", None, None, None, 0x1, ctypes.byref(out))       # 0x1: never show UI
    else:
        ok = fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError(f"{fn_name} failed ({ctypes.get_last_error()})")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel.LocalFree(out.pbData)


def protect(value):
    if sys.platform != "win32" or not value or value.startswith(PREFIX):
        return value
    try:
        return PREFIX + base64.b64encode(_run("CryptProtectData", value.encode("utf-8"))).decode("ascii")
    except Exception:
        return value


def unprotect(value):
    """Returns the plain value, or "" if it was encrypted for another Windows user / PC."""
    if not value or not value.startswith(PREFIX):
        return value
    if sys.platform != "win32":
        return ""
    try:
        return _run("CryptUnprotectData", base64.b64decode(value[len(PREFIX):])).decode("utf-8")
    except Exception:
        return ""
