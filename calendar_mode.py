"""
Calendar mode: just the calendar and reminders, in one small window, using very little of the PC.

What it skips compared with full Jarvis: the microphone, speech recognition models, his voice models, the AI brain
(except an optional quick lookup when typed text can't be understood), Discord, email, telemetry, the animated
HUD and background canvas. What's left: the calendar files, connected calendars syncing every 15 minutes,
alerts (a Windows notification + a chime, and optionally Windows' own built-in voice), and the window.

Start it with Jarvis.exe --calendar, "calendar mode" (voice), the Calendar mode button, or Settings > Calendar >
Start in. "Full Jarvis" in the window switches back (a restart, about 10 seconds).
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta

import cal_store as cs
import config

COLORS = {"jarvis": "c", "google": "g", "outlook": "o", "outlook_work": "o", "windows": "o", "caldav": "d", "other": "x"}


def notify(title, body):
    """A Windows notification (no extra libraries: PowerShell talks to Windows' notification system)."""
    if sys.platform != "win32":
        return
    aumid = "velopack.JarvisAssistant" if config.FROZEN else \
        r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
    esc = lambda x: str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "''")
    xml = (f"<toast scenario='reminder'><visual><binding template='ToastGeneric'><text>{esc(title)}</text>"
           f"<text>{esc(body)}</text></binding></visual><actions><action content='OK' arguments='ok' "
           f"activationType='system'/></actions><audio src='ms-winsoundevent:Notification.Reminder'/></toast>")
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
          "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
          f"$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml('{xml}');"
          f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{aumid}').Show("
          "[Windows.UI.Notifications.ToastNotification]::new($x))")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        print(f"[calendar] notification failed: {e}")


def _say(text):
    """Windows' built-in voice (SAPI): already on every PC, almost no memory. Off with Settings > Calendar."""
    if (os.environ.get("JARVIS_CAL_SPEAK") or "true").lower() == "false" or sys.platform != "win32":
        return

    def go():
        try:
            import pyttsx3
            e = pyttsx3.init()
            e.setProperty("rate", 175)
            e.say(text)
            e.runAndWait()
        except Exception as ex:
            print(f"[calendar] couldn't speak: {ex}")
    threading.Thread(target=go, daemon=True, name="cal-say").start()


def _chime():
    try:
        import winsound
        winsound.MessageBeep(0x40)                      # the "asterisk" sound
    except Exception:
        pass


class Api:
    """What calendar.html calls (window.pywebview.api.*). Underscore names aren't exposed."""

    def __init__(self, emit):
        self._emit = emit
        self._window = None
        self._asks = {}
        self._reminders = cs.ReminderManager(config.REMINDERS_FILE)
        import calendar_service
        self._svc = calendar_service.CalendarService(self._reminders, on_alert=self._alert, confirm=self._confirm,
                                                     on_change=lambda: self._emit({"type": "changed"}))

    # ---------------------------------------------------------------- start / stop
    def _start(self):
        self._svc.start()
        self._reminders.start(on_due=lambda msg, late: self._alert(
            f"Reminder: {msg}" if late < 2 else f"Missed reminder ({round(late)} min ago): {msg}", "reminder", {}))

    def _stop(self):
        self._svc.stop()
        self._reminders.stop()

    def _alert(self, text, kind, data):
        print(f"[calendar] alert: {text}")
        self._emit({"type": "alert", "text": text, "kind": kind})
        notify("Jarvis Calendar" if kind == "event" else "Reminder", text)
        _chime()
        _say(text)
        if kind == "reminder":
            self._emit({"type": "changed"})

    def _confirm(self, title, detail="", category=None):
        """Adding to Google / Outlook / CalDAV asks first, in the window."""
        import permissions
        if category and permissions.allowed(category):
            return True
        aid = uuid.uuid4().hex[:8]
        ev = threading.Event()
        self._asks[aid] = {"ev": ev, "ok": False, "always": False}
        self._emit({"type": "confirm", "id": aid, "title": title, "detail": detail, "can_always": bool(category)})
        ev.wait(120)
        a = self._asks.pop(aid, {})
        if a.get("ok") and a.get("always") and category:
            permissions.set_always(category, True)
        return bool(a.get("ok"))

    # ---------------------------------------------------------------- the page calls these
    def ready(self):
        import calendar_service
        try:
            self._emit.mark_ready()                      # the page is up: events can flow
        except AttributeError:
            pass
        return {"today": date.today().isoformat(), "default": calendar_service.default_target(),
                "targets": self._targets(), "alert": calendar_service.alert_minutes(),
                "status": self._svc.status(), "version": _version()}

    def _targets(self):
        import calendar_service
        out = [{"value": "jarvis", "label": "Jarvis's calendar"}]
        if self._svc.sources.caldav_set():
            out.append({"value": "caldav", "label": self._svc.sources.caldav_label()})
        out += [{"value": k, "label": v} for k, v in calendar_service.TARGETS.items()
                if k in ("google", "outlook", "outlook_work", "windows")]
        return out

    def range(self, start, end):
        """Every occurrence between two dates (the month grid asks for six weeks at a time)."""
        a, b = cs.to_dt(start), cs.to_dt(end)
        out = []
        for ev, s in self._svc.between(a, b):
            dur = cs.to_dt(ev["end"]) - cs.to_dt(ev["start"])
            src = ev.get("calendar") or "jarvis"
            key = ev.get("pushed_to") or ("jarvis" if src == "local" else re.sub(r"\d+$", "", src))
            out.append({"id": ev["id"], "title": ev["title"], "start": cs.iso(s, ev.get("all_day")),
                        "end": cs.iso(s + dur, ev.get("all_day")), "all_day": bool(ev.get("all_day")),
                        "location": ev.get("location") or "", "notes": ev.get("notes") or "",
                        "repeat": ev.get("repeat"), "repeat_text": cs.repeat_words(ev.get("repeat")),
                        "remind": ev.get("remind"), "cal": self._svc.label(ev), "color": COLORS.get(key, "x"),
                        "readonly": bool(ev.get("readonly")), "time": "" if ev.get("all_day") else cs.nice_time(s),
                        "end_time": "" if ev.get("all_day") else cs.nice_time(s + dur)})
        return out

    def parse(self, text):
        p = cs.parse(text)
        if p is None:
            return {"ok": False, "why": "No day or time in that. Try “dentist Tuesday 3pm”."}
        p["ok"] = True
        p["preview"] = cs.describe(p) + ("" if p.get("remind") is None else
                                        (" (no alert)" if p["remind"] == [] else f" (alert {p['remind'][0]} min before)"))
        return p

    def quick_add(self, text, calendar=None):
        p = cs.parse(text)
        if p is None:
            p = _ask_ai(text)
            if p is None:
                return {"ok": False, "msg": "I couldn't find a day or time in that. Try “dentist Tuesday 3pm”."}
        out = self._svc.add(p["title"], p["start"], p["end"], None, p["all_day"], "", "", p.get("repeat"),
                            p.get("remind"), calendar)
        return {"ok": out not in ("DENIED",) and not out.startswith(("I don't know", "No CalDAV")),
                "msg": "Not added." if out == "DENIED" else out, "start": p["start"]}

    def save(self, fields):
        f = dict(fields or {})
        rep = f.get("repeat")
        if isinstance(rep, str):
            rep = cs.parse_repeat(rep) if rep not in ("", "none") else None
        if rep and f.get("until"):
            rep["until"] = f["until"]
        remind = f.get("remind")
        remind = None if remind in ("", "default", None) else ([] if remind == "none" else [int(remind)])
        try:
            if f.get("id"):
                out = self._svc.edit(f["id"], title=f.get("title"), start=f.get("start"), end=f.get("end"),
                                     all_day=bool(f.get("all_day")), location=f.get("location", ""),
                                     notes=f.get("notes", ""), repeat=rep if rep else {}, remind=remind)
            else:
                out = self._svc.add(f.get("title") or "Event", f["start"], f.get("end"), None, bool(f.get("all_day")),
                                    f.get("location", ""), f.get("notes", ""), rep, remind, f.get("calendar"))
        except (ValueError, KeyError) as e:
            return {"ok": False, "msg": f"Check the date and time ({e})."}
        ok = out != "DENIED" and not out.startswith(("No event", "That one's", "I don't know", "No CalDAV"))
        return {"ok": ok, "msg": "Not saved." if out == "DENIED" else out}

    def delete(self, eid, only=None):
        out = self._svc.delete(eid, only=only or None)
        return {"ok": out != "DENIED" and not out.startswith(("No event", "That one's")), "msg": out}

    def reminders(self):
        self._reminders.reload()
        return [{"id": r["id"], "message": r["message"], "due": r["due"]} for r in self._reminders.items]

    def add_reminder(self, text):
        t = re.sub(r"(?i)^\s*remind me (?:to |about )?", "", str(text or "")).strip()
        p = cs.parse(t)
        if p is None or p["all_day"]:
            return {"ok": False, "msg": "When? Try “call mom at 5” or “stretch in 30 minutes”."}
        due = cs.to_dt(p["start"])
        if due <= datetime.now():
            return {"ok": False, "msg": "That time has already gone by."}
        msg = p["title"] if p["title"] != "Event" else t
        r = self._reminders.add(msg, due)
        return {"ok": True, "msg": f"Reminder: {msg}, {cs.nice_day(due)} at {cs.nice_time(due)}.", "id": r["id"]}

    def cancel_reminder(self, rid):
        gone = self._reminders.cancel(rid)
        return {"ok": bool(gone)}

    def answer(self, aid, ok, always=False):
        a = self._asks.get(aid)
        if a:
            a["ok"], a["always"] = bool(ok), bool(always)
            a["ev"].set()

    def sync(self):
        self._svc.sources.refresh(force=True)
        return self._svc.status()

    def full_mode(self):
        """Back to the whole Jarvis (a restart)."""
        import autostart
        import updater
        updater.NEXT_ARGS = ["--full"]
        updater.RESTARTING = True
        try:
            updater.spawn_restart()
        except Exception as e:
            updater.RESTARTING = False
            return {"ok": False, "msg": f"Couldn't start full Jarvis: {e}"}
        autostart.release()
        threading.Timer(0.8, self._close).start()
        threading.Timer(10, lambda: os._exit(0)).start()
        return {"ok": True}

    def _close(self):
        try:
            self._window.destroy()
        except Exception:
            os._exit(0)


def _version():
    try:
        return (config.RES_DIR / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _ask_ai(text):
    """Only when the typed text can't be understood locally: one tiny request to the fast model (if a key is set)."""
    key = getattr(config, "ANTHROPIC_API_KEY", "") or ""
    if not key or "paste-yours" in key:
        return None
    try:
        import anthropic
        now = datetime.now()
        msg = anthropic.Anthropic(api_key=key, timeout=15).messages.create(
            model=config.FAST_MODEL, max_tokens=200,
            messages=[{"role": "user", "content":
                       f"Now is {now:%A %Y-%m-%d %H:%M}. Turn this into a calendar event. Reply with JSON only: "
                       '{"title": str, "start": "YYYY-MM-DDTHH:MM" or "YYYY-MM-DD" if all day, "end": same format, '
                       '"all_day": bool, "repeat": null or "daily|weekdays|weekly|monthly|yearly"}. '
                       f"If there's no event in it, reply null.\n\n{text}"}])
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        raw = raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw else "null"
        d = json.loads(raw)
        if not d or not d.get("start"):
            return None
        d["repeat"] = cs.parse_repeat(d["repeat"]) if isinstance(d.get("repeat"), str) else None
        d.setdefault("end", None)
        d.setdefault("all_day", len(str(d["start"])) == 10)
        d["remind"] = None
        return d
    except Exception as e:
        print(f"[calendar] AI fallback failed: {e}")
        return None


def run(start_hidden=False, show_hook=None):
    import webview
    from jarvis import Emitter
    emitter = Emitter()
    api = Api(emitter)
    page = config.RES_DIR / "ui" / "calendar.html"
    window = webview.create_window("Jarvis Calendar", url=str(page), js_api=api, width=1060, height=740,
                                   min_size=(380, 560), background_color="#02060b", hidden=bool(start_hidden))
    api._window = window
    emitter.window = window

    def show():
        try:
            window.show()
            window.restore()
        except Exception:
            pass
    if show_hook is not None:
        show_hook["fn"] = show

    def on_closing():
        emitter.close()
        api._stop()
    window.events.closing += on_closing
    print("[calendar] calendar mode starting")
    api._start()
    webview.start()
