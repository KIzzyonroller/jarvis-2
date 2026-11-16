"""
"Anything weird on my network?": a sweep of your home network. Pings every address on your subnet (a /24 like
192.168.1.x), reads Windows' address table for the hardware (MAC) addresses, asks the network for names, and
compares with the devices seen before (netsweep.json) so new ones stand out. The first sweep just learns what's
normal. Read-only: it never connects to the devices, logs in, or changes anything.
"""
import ipaddress
import json
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import config

STATE = "netsweep.json"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _load():
    try:
        return json.loads((config.JARVIS_DIR / STATE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(st):
    try:
        (config.JARVIS_DIR / STATE).write_text(json.dumps(st), encoding="utf-8")
    except Exception as e:
        print(f"[net] {e}")


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))            # no packet is sent; it just picks the outgoing interface
        return s.getsockname()[0]
    finally:
        s.close()


def gateway():
    try:
        r = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=8, creationflags=NOWIN)
        for m in re.finditer(r"(?:Default Gateway|Puerta de enlace predeterminada|Standardgateway|Passerelle par d.faut)[ .]*:\s*([\d.]+)", r.stdout):
            return m.group(1)
    except Exception:
        pass
    return None


def _ping(ip):
    try:
        r = subprocess.run(["ping", "-n", "1", "-w", "350", ip], capture_output=True, text=True, timeout=3, creationflags=NOWIN)
        return ip if ("TTL=" in r.stdout.upper()) else None
    except Exception:
        return None


def _arp():
    out = {}
    try:
        r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=8, creationflags=NOWIN)
        for m in re.finditer(r"([\d.]+)\s+([0-9a-f]{2}(?:-[0-9a-f]{2}){5})\s+(\w+)", r.stdout, re.I):
            ip, mac = m.group(1), m.group(2).lower().replace("-", ":")
            if not mac.startswith(("ff:ff", "01:00:5e")):
                out[ip] = mac
    except Exception:
        pass
    return out


def _name(ip):
    try:
        n = socket.gethostbyaddr(ip)[0]
        return n.split(".")[0] if n and not n.startswith(ip) else ""
    except Exception:
        return ""


def sweep():
    me = local_ip()
    net = ipaddress.ip_network(me + "/24", strict=False)
    gw = gateway()
    with ThreadPoolExecutor(64) as ex:
        alive = {ip for ip in ex.map(_ping, [str(h) for h in net.hosts()]) if ip}
    macs = _arp()
    ips = sorted(alive | {ip for ip in macs if ipaddress.ip_address(ip) in net} | {me}, key=lambda s: ipaddress.ip_address(s))
    with ThreadPoolExecutor(16) as ex:
        names = dict(zip(ips, ex.map(_name, ips)))
    st = _load()
    known = st.get("known", {})
    first = not known
    devs = []
    for ip in ips:
        mac = macs.get(ip, "")
        key = mac or ip
        d = {"ip": ip, "mac": mac, "name": names.get(ip, ""), "me": ip == me, "gateway": ip == gw}
        if mac and int(mac.split(":")[0], 16) & 2:
            d["vendor"] = "private address"            # phones and laptops randomise their MAC per network
        d["new"] = not first and key not in known and not d["me"]
        known.setdefault(key, {"first": time.time(), "name": d["name"], "ip": ip})
        known[key]["last"] = time.time()
        devs.append(d)
    st.update(known=known, last=time.time())
    _save(st)
    return {"subnet": str(net), "devices": devs, "first": first}


def watch(state, subnet):
    """While the map is up: anything that starts talking on the network shows up within ~15 seconds."""
    net = ipaddress.ip_network(subnet)
    have = {d["ip"] for d in state["devices"]}
    st = _load()
    known = st.get("known", {})
    changed = False
    for ip, mac in _arp().items():
        if ip in have or ipaddress.ip_address(ip) not in net:
            continue
        d = {"ip": ip, "mac": mac, "name": _name(ip), "me": False, "gateway": False,
             "new": (mac or ip) not in known, "joined": time.strftime("%H:%M")}
        known.setdefault(mac or ip, {"first": time.time(), "name": d["name"], "ip": ip})
        state["devices"].append(d)
        changed = True
    if changed:
        st["known"] = known
        _save(st)
    return {"subnet": subnet, "devices": state["devices"], "watching": True}


def report(focus_it=False):
    try:
        r = sweep()
    except Exception as e:
        return f"Couldn't sweep the network ({type(e).__name__}: {e})."
    import pulls
    if pulls.pull("network", r, id="network", title="Network", ttl=600, focus=focus_it, where="right", live=True, auto=False):
        state = {"devices": r["devices"]}
        pulls.keep_live("network", lambda: watch(state, r["subnet"]), every=15, for_secs=600, ttl=600)
    new = [d for d in r["devices"] if d["new"]]
    named = [d["name"] for d in r["devices"] if d["name"] and not d["me"]][:8]
    head = f"{len(r['devices'])} devices on {r['subnet']}."
    if r["first"]:
        return head + " First sweep, so this is the baseline: next time anything new will stand out. Names seen: " + (", ".join(named) or "none") + "."
    if new:
        return head + " NEW since last time: " + "; ".join(f"{d['name'] or 'unnamed'} at {d['ip']}" + (f" ({d['mac']})" if d["mac"] else "") for d in new) + \
            ". A new device is usually a guest's phone or something just plugged in; if nobody recognises it, changing the Wi-Fi password kicks it off."
    return head + " Nothing new since the last sweep. Names seen: " + (", ".join(named) or "none") + "."
