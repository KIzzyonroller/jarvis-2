"""
Phone remote: talk to Jarvis/Ultron by typing on your phone, from anywhere in
the house. Off by default; turn on with JARVIS_PHONE=true in .env.

How it stays private:
  * It only answers devices on your home network (private IP addresses), never the internet.
  * Every request needs a secret key that's in the link (Documents/Jarvis/phone_token.txt).
    Anyone without the link gets nothing. Delete that file to make a new link.
  * Plain HTTP on your LAN: fine at home, don't turn it on when your PC is on public Wi-Fi.
Approvals (PowerShell, deleting...) show up on the phone too, because the phone is you.
"""
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import config

KEEP = {"msg", "turn_start", "reply_delta", "turn_end", "persona", "state", "confirm", "confirm_done", "toast",
        "alert", "duo", "mic"}


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))           # no packet is sent; just picks the LAN interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _token():
    p = config.JARVIS_DIR / "phone_token.txt"
    try:
        t = p.read_text(encoding="utf-8").strip()
        if len(t) >= 20:
            return t
    except Exception:
        pass
    t = secrets.token_urlsafe(18)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")
    return t


class PhoneHub:
    def __init__(self, core):
        self.core = core
        self.token = _token()
        self.log = deque(maxlen=400)
        self.seq = 0
        self.cv = threading.Condition()
        self.snap = {}
        self.url = f"http://{_lan_ip()}:{config.PHONE_PORT}/?t={self.token}"
        self.srv = None

    # ------------------------------------------------------------------ events from the core
    def feed(self, ev):
        t = ev.get("type")
        if t not in KEEP:
            return
        if t in ("persona", "state", "duo", "mic"):
            self.snap[t] = ev
        if t == "confirm":
            self.snap["confirm"] = ev
        if t == "confirm_done":
            self.snap.pop("confirm", None)
        with self.cv:
            self.seq += 1
            self.log.append((self.seq, ev))
            self.cv.notify_all()

    def events_since(self, since, wait=20.0):
        end = time.time() + wait
        with self.cv:
            while self.seq <= since and time.time() < end:
                self.cv.wait(timeout=max(0.1, end - time.time()))
            evs = [e for (n, e) in self.log if n > since]
            return evs, self.seq

    # ------------------------------------------------------------------ server
    def start(self):
        hub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _allowed(self):
                try:
                    ip = ipaddress.ip_address(self.client_address[0])
                except ValueError:
                    return False
                return ip.is_private or ip.is_loopback or ip.is_link_local

            def _authed(self):
                tok = self.headers.get("X-Token") or parse_qs(urlparse(self.path).query).get("t", [""])[0]
                return hmac.compare_digest(tok.encode(), hub.token.encode())

            def _send(self, code, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype + ("; charset=utf-8" if "text" in ctype or "json" in ctype else ""))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if not self._allowed():
                    return self._send(403, {"error": "local network only"})
                u = urlparse(self.path)
                if not self._authed():
                    return self._send(403, "<h3 style='font-family:sans-serif'>Wrong or old link. Get the current one "
                                           "from the Jarvis app.</h3>", "text/html")
                if u.path == "/":
                    return self._send(200, PAGE.replace("__TOKEN__", hub.token), "text/html")
                if u.path == "/api/events":
                    since = int(parse_qs(u.query).get("since", ["0"])[0])
                    if since == 0:
                        recent = [e for (n, e) in list(hub.log)[-60:] if e.get("type") in ("msg", "turn_end", "turn_start")]
                        return self._send(200, {"events": list(hub.snap.values()) + recent, "next": hub.seq})
                    evs, nxt = hub.events_since(since)
                    return self._send(200, {"events": evs, "next": nxt})
                return self._send(404, {"error": "not found"})

            def do_POST(self):
                if not self._allowed() or not self._authed():
                    return self._send(403, {"error": "forbidden"})
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(min(n, 20000)) or b"{}")
                except ValueError:
                    return self._send(400, {"error": "bad json"})
                path = urlparse(self.path).path
                c = hub.core
                if path == "/api/send":
                    text = str(body.get("text", "")).strip()[:2000]
                    if text:
                        c.submit(text, "phone")
                    return self._send(200, {"ok": True})
                if path == "/api/confirm":
                    c.resolve_confirm(str(body.get("id", "")), bool(body.get("approved")), always=bool(body.get("always")))
                    return self._send(200, {"ok": True})
                if path == "/api/action":
                    a = body.get("name")
                    if a == "stop":
                        c.stop_speaking()
                    elif a == "mute":
                        threading.Thread(target=c.toggle_mute, daemon=True).start()
                    elif a in ("play_pause", "next", "previous"):
                        import tools
                        tools.media_control(a)
                    elif a == "switch":
                        c.switch_persona(body.get("key"))
                    return self._send(200, {"ok": True})
                return self._send(404, {"error": "not found"})

        try:
            self.srv = ThreadingHTTPServer(("0.0.0.0", config.PHONE_PORT), H)
        except OSError as e:
            return f"Phone remote couldn't start: port {config.PHONE_PORT} is busy ({e})."
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True, name="phone").start()
        return None

    def stop(self):
        if self.srv:
            self.srv.shutdown()


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#03070c"><title>Jarvis</title>
<style>
:root{--bg:#02060b;--arc:#7fe7ff;--rgb:127,231,255;--ice:#dff6ff;--steel:#6f8f9f;--amber:#ffc46b;--alarm:#ff9d2e;--line:rgba(127,231,255,.18)}
:root[data-ai=ultron]{--bg:#080203;--arc:#ff3046;--rgb:255,48,70;--ice:#f4e9e4;--steel:#9a767d;--amber:#ff8a3d;--alarm:#ffd34d;--line:rgba(255,48,70,.28)}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%;background:var(--bg);color:var(--ice);font:16px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
body{display:flex;flex-direction:column;height:100dvh}
header{display:flex;align-items:center;gap:10px;padding:14px 16px 12px;border-bottom:1px solid var(--line)}
.dot{width:10px;height:10px;border-radius:50%;background:var(--steel)}
body.st-speaking .dot,body.st-listening .dot{background:var(--arc);box-shadow:0 0 10px var(--arc)}
body.st-thinking .dot{background:var(--amber);animation:p 1s infinite}@keyframes p{50%{opacity:.3}}
.wm{font-weight:700;letter-spacing:.2em;color:var(--arc);font-size:15px}
.st{color:var(--steel);font-size:13px;text-transform:uppercase;letter-spacing:.08em;margin-left:auto}
#log{flex:1;overflow-y:auto;padding:14px 16px 8px;display:flex;flex-direction:column;gap:10px}
.m{max-width:86%;padding:9px 12px;border:1px solid var(--line);font-size:15px;white-space:pre-wrap;word-wrap:break-word}
.m.user{align-self:flex-end;background:rgba(var(--rgb),.14);border-color:rgba(var(--rgb),.35)}
.m.ai{align-self:flex-start}.m.ai b{display:block;font-size:11px;letter-spacing:.14em;color:var(--arc);margin-bottom:2px}
.m.ai b.ultron{color:#ff3046}.m.ai b.jarvis{color:#7fe7ff}
.m.sys{align-self:center;border:0;color:var(--steel);font-size:13px;text-align:center}
.card{border:1px solid var(--alarm);padding:12px;margin:0 16px 10px;display:none}
.card.on{display:block}.card h4{color:var(--alarm);font-size:13px;margin-bottom:6px}
#always{display:none}.card.can #always{display:block}
.card code{display:block;color:var(--steel);font-size:13px;margin:6px 0 10px;word-break:break-all}
.row{display:flex;gap:8px}
button{font:inherit;border:1px solid var(--line);background:transparent;color:var(--ice);padding:10px 12px;flex:1}
button:active{background:rgba(var(--rgb),.2)}
.yes{border-color:var(--alarm);background:var(--alarm);color:#140a00;font-weight:600}
#always{border-color:var(--alarm);color:var(--alarm)}
.quick{display:flex;gap:6px;padding:0 16px 8px}.quick button{padding:8px 4px;font-size:13px;color:var(--steel)}
form{display:flex;gap:8px;padding:8px 16px calc(12px + env(safe-area-inset-bottom));border-top:1px solid var(--line)}
input{flex:1;font:inherit;font-size:16px;background:rgba(var(--rgb),.06);border:1px solid var(--line);color:var(--ice);padding:12px}
input:focus{outline:none;border-color:var(--arc)}
form button{flex:none;background:var(--arc);color:var(--bg);font-weight:700;border:0;padding:0 18px}
</style></head><body class="st-idle">
<header><i class="dot"></i><span class="wm" id="wm">J.A.R.V.I.S.</span><span class="st" id="st">Standby</span></header>
<div id="log"></div>
<div class="card" id="card"><h4>Needs your OK</h4><div id="ct"></div><code id="cd"></code>
<div class="row"><button id="no">Deny</button><button id="always">Always allow</button><button class="yes" id="yes">Allow</button></div></div>
<div class="quick"><button data-a="stop">Stop</button><button data-a="play_pause">Pause</button>
<button data-a="next">Next</button><button data-a="mute">Mic</button><button data-a="switch">Switch</button></div>
<form id="f"><input id="i" placeholder="Tell him something" autocomplete="off" enterkeyhint="send"><button>Send</button></form>
<script>
const T="__TOKEN__", $=s=>document.querySelector(s), log=$("#log");
const LABEL={idle:"Standby",listening:"Listening",thinking:"Thinking",speaking:"Speaking",awaiting:"Approval",dictating:"Dictating",booting:"Starting"};
let next=0, cid=null, live={}, ai="jarvis";
const api=(p,b)=>fetch(p,{method:b?"POST":"GET",headers:{"X-Token":T,"Content-Type":"application/json"},body:b?JSON.stringify(b):undefined}).then(r=>r.json());
function add(cls,text,who){const d=document.createElement("div");d.className="m "+cls;
  if(who){const b=document.createElement("b");b.textContent=who.toUpperCase();b.className=who.toLowerCase();d.appendChild(b)}
  const s=document.createElement("span");s.textContent=text;d.appendChild(s);log.appendChild(d);log.scrollTop=log.scrollHeight;return s}
function on(e){switch(e.type){
  case"persona":ai=e.key;document.documentElement.dataset.ai=e.key;$("#wm").textContent=e.wordmark;break;
  case"state":document.body.className="st-"+e.state;$("#st").textContent=LABEL[e.state]||e.state;break;
  case"msg":if(e.role==="user")add("user",e.text);else if(e.role==="system")add("sys",e.text);else add("ai",e.text,ai==="ultron"?"Ultron":"Jarvis");break;
  case"turn_start":live[e.id]={who:e.who||"Jarvis",el:null,text:""};break;
  case"reply_delta":{const t=live[e.id];if(!t)break;t.text+=e.text;if(!t.el)t.el=add("ai","",t.who);t.el.textContent=t.text;log.scrollTop=log.scrollHeight;break}
  case"turn_end":{const t=live[e.id];if(t&&!t.el&&e.text)add("ai",e.text,t.who);else if(!t&&e.text)add("ai",e.text,"");delete live[e.id];break}
  case"confirm":cid=e.id;$("#ct").textContent=e.title;$("#cd").textContent=e.detail||"";$("#card").classList.add("on");$("#card").classList.toggle("can",!!e.can_always);$("#always").textContent=e.always_label?"Always: "+e.always_label:"Always allow";break;
  case"confirm_done":if(e.id===cid){cid=null;$("#card").classList.remove("on")}break;
  case"toast":case"alert":add("sys",e.text);break;}}
async function poll(){for(;;){try{const r=await api("/api/events?since="+next);r.events.forEach(on);next=r.next}catch(e){await new Promise(r=>setTimeout(r,2000))}}}
$("#f").onsubmit=e=>{e.preventDefault();const t=$("#i").value.trim();if(!t)return;$("#i").value="";api("/api/send",{text:t})};
$("#yes").onclick=()=>cid&&api("/api/confirm",{id:cid,approved:true});$("#no").onclick=()=>cid&&api("/api/confirm",{id:cid,approved:false});$("#always").onclick=()=>cid&&api("/api/confirm",{id:cid,approved:true,always:true});
document.querySelectorAll(".quick button").forEach(b=>b.onclick=()=>api("/api/action",{name:b.dataset.a}));
poll();
</script></body></html>"""
