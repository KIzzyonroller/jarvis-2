"""
His own pointer (the "His own pointer" option). Windows has exactly one mouse pointer, so a truly separate one
isn't possible; this gets as close as it can:

  1. Ask the app itself. Most buttons, links, menu items, tabs and checkboxes can be pressed through Windows' UI
     Automation without touching the mouse at all. Then your pointer doesn't move, even for a moment.
  2. Borrow and give back. When the app won't take that (games, canvases, right-clicks, drags), he waits until
     you're not moving the mouse, jumps it there, clicks, and puts it back exactly where it was, all in a few
     hundredths of a second.

With the desktop characters out, a small glowing pointer of his own glides to the spot and ripples as he clicks,
so you can see what he's doing.
"""
import ctypes
import sys
import time

IS_WINDOWS = sys.platform == "win32"
_SHOW = {"fn": None}          # buddies.Host.pointer(x, y, kind)


def set_display(fn):
    _SHOW["fn"] = fn


def _show(x, y, kind):
    fn = _SHOW["fn"]
    if fn:
        try:
            fn(x, y, kind)
        except Exception:
            pass


def _cursor():
    from ctypes import wintypes as wt
    p = wt.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def _wait_still(max_wait=1.5):
    """Don't yank the mouse out of your hand: wait (briefly) until it's been still for a moment."""
    end = time.time() + max_wait
    last = _cursor()
    still_since = time.time()
    while time.time() < end:
        time.sleep(0.05)
        now = _cursor()
        if now != last:
            last, still_since = now, time.time()
        elif time.time() - still_since > 0.25:
            return


_PRESSABLE = {"ButtonControl", "HyperlinkControl", "MenuItemControl", "TabItemControl", "CheckBoxControl",
              "RadioButtonControl", "ListItemControl", "TreeItemControl", "SplitButtonControl"}


def _invoke_at(x, y):
    """Press whatever's at (x, y) through UI Automation. Returns a description, or None if it can't."""
    try:
        import uiautomation as auto
    except Exception:
        return None
    try:
        c = auto.ControlFromPoint(int(x), int(y))
    except Exception:
        return None
    for _ in range(2):                     # the exact element, or its parent (a label inside a button)
        if c is None:
            return None
        name = (c.Name or c.ControlTypeName or "it").strip()[:60]
        if c.ControlTypeName not in _PRESSABLE:      # text boxes, canvases, panes...: a real click is needed
            try:
                c = c.GetParentControl()
            except Exception:
                return None
            continue
        try:
            p = c.GetPattern(auto.PatternId.InvokePattern)
            if p:
                p.Invoke()
                return f"pressed {name}"
            p = c.GetPattern(auto.PatternId.TogglePattern)
            if p:
                p.Toggle()
                return f"toggled {name}"
            p = c.GetPattern(auto.PatternId.SelectionItemPattern)
            if p:
                p.Select()
                return f"selected {name}"
            p = c.GetPattern(auto.PatternId.ExpandCollapsePattern)
            if p:
                st = p.ExpandCollapseState
                (p.Collapse if st == 1 else p.Expand)()
                return f"{'collapsed' if st == 1 else 'expanded'} {name}"
        except Exception:
            pass
        try:
            c = c.GetParentControl()
        except Exception:
            return None
    return None


def _borrow(x, y, action, to=None, amount=0):
    import pyautogui
    _wait_still()
    home = _cursor()
    u = ctypes.windll.user32
    try:
        u.SetCursorPos(int(x), int(y))
        time.sleep(0.02)
        if action == "click":
            pyautogui.click(_pause=False)
        elif action == "double_click":
            pyautogui.doubleClick(_pause=False)
        elif action == "right_click":
            pyautogui.click(button="right", _pause=False)
        elif action == "middle_click":
            pyautogui.click(button="middle", _pause=False)
        elif action == "drag" and to:
            pyautogui.mouseDown(_pause=False)
            pyautogui.moveTo(to[0], to[1], duration=0.25, _pause=False)
            pyautogui.mouseUp(_pause=False)
        elif action == "scroll":
            pyautogui.scroll(int(amount) * 120, _pause=False)
        time.sleep(0.03)
    finally:
        u.SetCursorPos(*home)              # yours, back where it was


def act(action, x, y, to=None, amount=0):
    """Does the mouse action at screen pixel (x, y) with as little disturbance as possible. Returns a short note."""
    if not IS_WINDOWS:
        return "Windows only."
    _show(x, y, action)
    if action == "click":
        done = _invoke_at(x, y)
        if done:
            return f"(without moving your pointer: {done})"
    if action == "move":
        return "(his pointer is there; yours didn't move)"
    _borrow(x, y, action, to=to, amount=amount)
    return "(borrowed your pointer for a moment and put it back)"
