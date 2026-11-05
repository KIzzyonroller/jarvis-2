"""
PC doctor: "why is my PC slow?" and friends. Everything here only looks, except turning a startup app off or back
on, which always asks first.

  slow      what's eating CPU / memory right now, disk space, how long since a restart, graphics card load and heat,
            how many apps launch at startup
  updates   apps with updates waiting (winget), the graphics driver's version and age, Windows updates waiting.
            Report only: she never installs drivers or updates by herself
  disk      what's filling your drives: biggest folders in your user folder, caches that are safe to clear
            (temp files, shader caches), installed Steam games and when you last played them
  crashes   recent app crashes, hangs and unexpected shutdowns from the Windows event log, for her to explain
  startup   what launches when Windows starts, and turning one off / on (asks first; some are never touched)
  network   is it your Wi-Fi, your internet or the game: pings to your router and the internet, packet loss, Wi-Fi
            signal, and (only when asked) a quick download speed test

CPU temperature isn't included: Windows only gives that to programs running as administrator.
"""
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import config

NO_WINDOW = 0x08000000
PROTECTED = re.compile(r"security|defender|realtek|rtkaud|audio|nvidia|amd|radeon|intel|easyanticheat|battleye|"
                       r"vanguard|vgtray|faceit|riot|driver|synaptics|bluetooth|onedrive sync|ctfmon", re.I)


def _ps(script, timeout=60):
    """Run PowerShell, return stdout (empty on failure)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                           capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip()
    except Exception as e:
        print(f"[doctor] powershell: {e}")
        return ""


def _run(args, timeout=60):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW,
                           encoding="utf-8", errors="replace")
        return r.stdout
    except Exception as e:
        print(f"[doctor] {args[0]}: {e}")
        return ""


def gb(n):
    return f"{n / 2**30:.1f} GB"


# ------------------------------------------------------------------ slow
def slow():
    import psutil
    procs = list(psutil.process_iter(["name", "memory_info"]))
    for p in procs:
        try:
            p.cpu_percent(None)
        except Exception:
            pass
    time.sleep(1.5)
    ncpu = psutil.cpu_count() or 1
    cpu, mem = {}, {}
    for p in procs:
        try:
            n = p.info["name"] or "?"
            cpu[n] = cpu.get(n, 0) + p.cpu_percent(None) / ncpu
            mem[n] = mem.get(n, 0) + (p.info["memory_info"].rss if p.info["memory_info"] else 0)
        except Exception:
            pass
    cpu.pop("System Idle Process", None)
    vm = psutil.virtual_memory()
    total_cpu = psutil.cpu_percent(interval=0.5)
    lines, flags = [], []
    top_cpu = sorted(cpu.items(), key=lambda kv: -kv[1])[:5]
    top_mem = sorted(mem.items(), key=lambda kv: -kv[1])[:5]
    lines.append(f"Processor {total_cpu:.0f}% busy. Top: " + ", ".join(f"{n} {v:.0f}%" for n, v in top_cpu if v >= 1))
    lines.append(f"Memory {vm.percent:.0f}% used ({gb(vm.used)} of {gb(vm.total)}). Top: " +
                 ", ".join(f"{n} {gb(v)}" for n, v in top_mem))
    if total_cpu > 85:
        flags.append(f"the processor is maxed out, mostly by {top_cpu[0][0]}")
    if vm.percent > 88:
        flags.append(f"memory is nearly full; {top_mem[0][0]} uses the most")
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue
        free = u.total - u.used
        lines.append(f"Drive {part.device} {u.percent:.0f}% full ({gb(free)} free)")
        if part.mountpoint.upper().startswith("C") and (u.percent > 92 or free < 15 * 2**30):
            flags.append(f"the C drive is nearly full ({gb(free)} free), which slows Windows down")
    up = time.time() - psutil.boot_time()
    lines.append(f"Last restart {up / 86400:.1f} days ago")
    if up > 7 * 86400:
        flags.append(f"it hasn't restarted in {up / 86400:.0f} days; a restart often clears slowness")
    try:
        import glass_kinds
        g = glass_kinds.gpu()
        if g:
            lines.append(f"Graphics card {g['gpu']}% busy, {g['gpu_temp']}°C, video memory {g['vram']}/{g['vram_total']} GB")
            if g["gpu_temp"] >= 85:
                flags.append(f"the graphics card is hot ({g['gpu_temp']}°C): check fans and dust")
    except Exception:
        pass
    try:
        n = len([s for s in startup_items() if s["enabled"]])
        lines.append(f"{n} apps start with Windows")
        if n > 15:
            flags.append(f"{n} apps launch at startup; turning some off helps boot time")
    except Exception:
        pass
    head = ("Likely causes: " + "; ".join(flags) + ".") if flags else "Nothing obviously wrong right now."
    return head + "\n" + "\n".join(lines)


# ------------------------------------------------------------------ updates
def updates():
    out = []
    raw = _run(["winget", "upgrade", "--include-unknown", "--accept-source-agreements", "--disable-interactivity"], 90)
    apps = []
    if raw:
        rows = [l.rstrip() for l in raw.replace("\r", "").splitlines()]
        dash = next((i for i, l in enumerate(rows) if re.fullmatch(r"-{20,}", l.strip())), None)
        if dash:                                  # column starts from the header row (works in any language)
            h = rows[dash - 1]
            starts = [m.start() for m in re.finditer(r"(?:^|(?<=\s))\S", h)]
            if len(starts) >= 4:
                c_ver, c_av = starts[2], starts[3]
                c_src = starts[4] if len(starts) > 4 else None
                for l in rows[dash + 1:]:
                    if len(l) <= c_av or not l[:starts[1]].strip():
                        continue
                    name = l[:starts[1]].strip()
                    cur = l[c_ver:c_av].strip()
                    new = (l[c_av:c_src] if c_src else l[c_av:]).strip().split(" ")[0]
                    if name and new and re.search(r"\d", new):
                        apps.append(f"{name} {cur} -> {new}")
    if apps:
        out.append(f"{len(apps)} apps have updates: " + "; ".join(apps[:15]) + ("; ..." if len(apps) > 15 else ""))
    elif raw:
        out.append("Every app winget knows about is up to date.")
    else:
        out.append("Couldn't check apps (winget isn't available).")
    drv = _ps("Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,"
              "@{n='Date';e={$_.DriverDate.ToString('yyyy-MM-dd')}} | ConvertTo-Json -Compress", 30)
    try:
        cards = json.loads(drv) if drv else []
        cards = cards if isinstance(cards, list) else [cards]
        for c in cards:
            if "Microsoft Basic" in (c.get("Name") or ""):
                continue
            age = ""
            try:
                days = (datetime.now() - datetime.strptime(c["Date"], "%Y-%m-%d")).days
                age = f", {days // 30} months old" if days > 60 else ", recent"
            except Exception:
                pass
            nv = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], 10).strip() if "NVIDIA" in (c.get("Name") or "") else ""
            out.append(f"Graphics driver: {c.get('Name')} version {nv or c.get('DriverVersion')} from {c.get('Date')}{age}.")
    except Exception:
        pass
    wu = _ps("try { $s = New-Object -ComObject Microsoft.Update.Session; $r = $s.CreateUpdateSearcher().Search("
             "\"IsInstalled=0 and IsHidden=0 and Type='Software'\"); ($r.Updates | ForEach-Object { $_.Title }) -join '|' }"
             " catch { 'ERR' }", 120)
    if wu == "ERR" or wu is None:
        out.append("Couldn't check Windows Update.")
    elif wu:
        titles = [t for t in wu.split("|") if t]
        out.append(f"{len(titles)} Windows updates waiting: " + "; ".join(titles[:6]))
    else:
        out.append("Windows is up to date.")
    out.append("(Report only. Install them yourself from the apps, Windows Update, or the NVIDIA/AMD app.)")
    return "\n".join(out)


# ------------------------------------------------------------------ disk
def _size(path, budget):
    total, stack = 0, [str(path)]
    while stack and time.time() < budget:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total, not stack


def disk():
    import psutil
    budget = time.time() + 45
    out = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
            out.append(f"{part.device} {gb(u.used)} used, {gb(u.total - u.used)} free")
        except Exception:
            pass
    home = config.HOME
    sizes = []
    for name in ("Downloads", "Documents", "Videos", "Pictures", "Desktop", "Music", "OneDrive"):
        p = home / name
        if p.is_dir():
            s, full = _size(p, min(budget, time.time() + 8))
            sizes.append((name, s, full))
    sizes.sort(key=lambda x: -x[1])
    out.append("Your folders: " + ", ".join(f"{n} {gb(s)}{'' if full else '+'}" for n, s, full in sizes if s > 2**28))
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    caches = [("Temp files", Path(os.environ.get("TEMP", local / "Temp"))),
              ("NVIDIA shader cache", local / "NVIDIA" / "DXCache"), ("NVIDIA GL cache", local / "NVIDIA" / "GLCache"),
              ("DirectX shader cache", local / "D3DSCache"), ("AMD shader cache", local / "AMD" / "DxCache")]
    found = []
    for n, p in caches:
        if p.is_dir():
            s, _ = _size(p, min(budget, time.time() + 6))
            if s > 2**27:
                found.append(f"{n} {gb(s)}")
    if found:
        out.append("Safe to clear (Windows' Disk Cleanup or the driver app does it properly): " + ", ".join(found))
    try:
        import steam
        games = steam.installed_games()
        if games:
            games.sort(key=lambda g: -g["size"])
            def last(g):
                if not g["last_played"]:
                    return "never played"
                d = (time.time() - g["last_played"]) / 86400
                return "played today" if d < 1 else f"last played {d:.0f} days ago"
            out.append("Biggest Steam games: " + "; ".join(f"{g['name']} {gb(g['size'])} ({last(g)})" for g in games[:8]))
            stale = [g for g in games if g["size"] > 10 * 2**30 and (not g["last_played"] or time.time() - g["last_played"] > 180 * 86400)]
            if stale:
                out.append(f"Not played in 6+ months: {', '.join(g['name'] for g in stale[:6])} "
                           f"({gb(sum(g['size'] for g in stale))} you could uninstall through Steam).")
    except Exception as e:
        print(f"[doctor] steam games: {e}")
    return "\n".join(out)


# ------------------------------------------------------------------ crashes
def crashes(hours=48):
    hours = max(1, min(int(hours or 48), 24 * 14))
    script = (
        f"$since=(Get-Date).AddHours(-{hours}); $o=@();"
        "$o+=Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000,1002;StartTime=$since} -MaxEvents 40 -ErrorAction SilentlyContinue |"
        " Select-Object @{n='t';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm')}},Id,@{n='msg';e={($_.Message -split \"`n\")[0..3] -join ' '}};"
        "$o+=Get-WinEvent -FilterHashtable @{LogName='System';Id=41,6008,1001;StartTime=$since} -MaxEvents 10 -ErrorAction SilentlyContinue |"
        " Select-Object @{n='t';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm')}},Id,@{n='msg';e={($_.Message -split \"`n\")[0..2] -join ' '}};"
        "$o | ConvertTo-Json -Compress")
    raw = _ps(script, 60)
    try:
        evs = json.loads(raw) if raw else []
        evs = evs if isinstance(evs, list) else [evs]
    except ValueError:
        evs = []
    if not evs:
        return f"No app crashes, hangs or unexpected shutdowns in the last {hours} hours."
    kind = {1000: "crash", 1002: "hang", 41: "unexpected shutdown/restart", 6008: "unexpected shutdown", 1001: "blue screen or crash report"}
    lines = []
    for e in sorted(evs, key=lambda e: e.get("t", ""), reverse=True)[:25]:
        msg = re.sub(r"\s+", " ", e.get("msg") or "")[:260]
        lines.append(f"{e.get('t')} {kind.get(e.get('Id'), e.get('Id'))}: {msg}")
    return (f"Windows logged these in the last {hours} hours (newest first). Explain them in plain words; the "
            "'faulting module' is usually the clue, and some can't be pinned down:\n" + "\n".join(lines))


# ------------------------------------------------------------------ startup apps
def startup_items():
    """[{name, command, where, enabled, can_change}] from the Run keys and Startup folders."""
    import winreg
    items = []
    approved = {}
    for root, rootname in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
        for sub in ("Run", "Run32", "StartupFolder"):
            try:
                k = winreg.OpenKey(root, r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved" + "\\" + sub)
                i = 0
                while True:
                    try:
                        n, v, _ = winreg.EnumValue(k, i)
                        approved[(rootname, n.lower())] = bool(v) and v[0] in (2, 6)
                        i += 1
                    except OSError:
                        break
            except OSError:
                pass
        for path in (r"Software\Microsoft\Windows\CurrentVersion\Run", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"):
            try:
                k = winreg.OpenKey(root, path)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    n, v, _ = winreg.EnumValue(k, i)
                    i += 1
                except OSError:
                    break
                items.append({"name": n, "command": str(v)[:160], "where": rootname,
                              "enabled": approved.get((rootname, n.lower()), True),
                              "can_change": rootname == "HKCU" and not PROTECTED.search(n + " " + str(v))})
    folder = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    if folder.is_dir():
        for f in folder.iterdir():
            if f.suffix.lower() in (".lnk", ".url", ".exe", ".bat"):
                items.append({"name": f.name, "command": str(f), "where": "HKCU", "folder": True,
                              "enabled": approved.get(("HKCU", f.name.lower()), True),
                              "can_change": not PROTECTED.search(f.name)})
    return items


def startup_list():
    items = startup_items()
    if not items:
        return "Nothing launches at startup from the usual places."
    on = [i for i in items if i["enabled"]]
    off = [i for i in items if not i["enabled"]]
    out = [f"{len(on)} apps start with Windows:"]
    out += [f"- {i['name']}" + ("" if i["can_change"] else " (I won't touch this one: system, driver or anti-cheat, "
                                "or needs admin)") for i in on]
    if off:
        out.append("Already turned off: " + ", ".join(i["name"] for i in off))
    return "\n".join(out)


def startup_set(name, enable, confirm):
    import winreg
    n = (name or "").lower().strip()
    hits = [i for i in startup_items() if n and n in i["name"].lower()]
    if not hits:
        return f"No startup app called '{name}'."
    it = hits[0]
    if not it["can_change"]:
        return f"I won't change {it['name']}: it's a system, driver or anti-cheat entry, or needs admin rights."
    if confirm and not confirm(f"{'Turn on' if enable else 'Turn off'} {it['name']} at startup",
                               f"{it['command']}\n\nSame as the switch in Task Manager > Startup apps. You can flip it back any time."):
        return "Okay, left it."
    sub = "StartupFolder" if it.get("folder") else "Run"
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved" + "\\" + sub)
    val = bytes([2] + [0] * 11) if enable else bytes([3] + [0] * 3) + int(time.time() * 10**7 + 116444736000000000).to_bytes(8, "little")
    winreg.SetValueEx(k, it["name"], 0, winreg.REG_BINARY, val)
    return f"{it['name']} will {'start' if enable else 'no longer start'} with Windows."


# ------------------------------------------------------------------ network
def _ping(host, n=10):
    out = _run(["ping", "-n", str(n), "-w", "1000", host], 30)
    loss = re.search(r"\((\d+)\s*%", out)                       # works in any Windows language
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    ms = re.findall(r"=\s*(\d+)\s*ms", tail)                     # min, max, average: the last one is the average
    return (int(loss.group(1)) if loss else 100), (int(ms[-1]) if ms else None)


def network(speedtest=False):
    gw = _ps("(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).NextHop", 15)
    out, flags = [], []
    if gw:
        loss, avg = _ping(gw)
        out.append(f"Router ({gw}): {avg if avg is not None else '?'} ms, {loss}% lost")
        if loss > 2 or (avg or 0) > 20:
            flags.append("the connection to your router itself is shaky (Wi-Fi or cable)")
    for host, label in (("1.1.1.1", "Cloudflare"), ("8.8.8.8", "Google")):
        loss, avg = _ping(host)
        out.append(f"Internet ({label}): {avg if avg is not None else '?'} ms, {loss}% lost")
        if loss > 2:
            flags.append(f"packets are getting lost on the way to the internet ({loss}%)")
        elif (avg or 0) > 80:
            flags.append(f"internet ping is high ({avg} ms)")
    wl = _run(["netsh", "wlan", "show", "interfaces"], 10)
    sig = re.search(r"Signal\s*:\s*(\d+)%", wl)
    if sig:
        out.append(f"Wi-Fi signal {sig.group(1)}%")
        if int(sig.group(1)) < 60:
            flags.append(f"Wi-Fi signal is weak ({sig.group(1)}%): closer to the router or a cable would help")
    else:
        out.append("Wired connection (or Wi-Fi is off)")
    if speedtest:
        try:
            import requests
            t = time.time()
            r = requests.get("https://speed.cloudflare.com/__down?bytes=25000000", timeout=40, stream=True)
            got = sum(len(c) for c in r.iter_content(65536))
            mbps = got * 8 / (time.time() - t) / 1e6
            out.append(f"Download speed about {mbps:.0f} Mbps (25 MB test)")
        except Exception as e:
            out.append(f"Speed test failed: {e}")
    head = ("Looks like: " + "; ".join(flags) + ".") if flags else "Network looks healthy from here; if a game lags, it's likely the game's servers."
    return head + "\n" + "\n".join(out)
