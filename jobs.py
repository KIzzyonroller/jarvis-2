"""
Background jobs: longer tasks that run while you keep talking to him.

"Jarvis, in the background, research budget USB mics under 100 dollars and make me a shortlist."
He starts it, says so, and you carry on. The job works step by step on its own (searching, reading
files, running read-only commands, writing a file), and when it's done he tells you the one-line result
and saves the full write-up to Documents\\Jarvis\\Jobs. The System panel shows what each job is doing.

Limits, on purpose:
  * No mouse, keyboard, window or screen tools: a job never takes over your PC while you're using it.
  * Anything risky still shows the normal approval card (labelled as coming from the background job).
  * At most two at once, up to 40 steps each, and they stop if the daily spending limit is reached.
"""
import re
import threading
import time
from datetime import datetime

import config

ALLOWED = {"web_search", "files", "run_command", "system_info", "memory", "reminders", "history", "discord",
           "blender_expert", "unreal_expert", "connectors"}
MAX_RUNNING = 2
MAX_STEPS = 40
JOB_PROMPT = """[BACKGROUND JOB. You're working on this on your own while the user does other things; they can't
answer questions right now, so make sensible assumptions and note them. Work step by step with your tools
(web_search for research; files to read or save). Be thorough but don't pad.
When you're completely done, reply in exactly this shape:
SUMMARY: one or two spoken sentences saying what you found or did (this is read out loud).
Then the full result in markdown (lists, links, details) below it.]

The job: {goal}"""


class Job:
    def __init__(self, jid, goal, persona):
        self.id, self.goal, self.persona = jid, goal.strip(), persona
        self.status = "running"            # running, done, failed, cancelled
        self.started, self.finished = time.time(), None
        self.steps = []
        self.summary = ""
        self.path = None
        self.cancel = threading.Event()

    def view(self):
        return {"id": self.id, "goal": self.goal[:140], "status": self.status, "step": (self.steps[-1] if self.steps else "Starting"),
                "steps": len(self.steps), "secs": round((self.finished or time.time()) - self.started),
                "summary": self.summary, "path": str(self.path) if self.path else None}


class Jobs:
    def __init__(self, make_brain, on_change=None, on_done=None, log=print):
        self.make_brain = make_brain        # persona -> a fresh Brain
        self.on_change = on_change or (lambda: None)
        self.on_done = on_done or (lambda job: None)
        self.log = log
        self.jobs = {}
        self.lock = threading.Lock()
        self._n = 0

    def running(self):
        return [j for j in self.jobs.values() if j.status == "running"]

    def start(self, goal, persona="jarvis"):
        if not (goal or "").strip():
            return None, "What should the job be?"
        with self.lock:
            if len(self.running()) >= MAX_RUNNING:
                return None, f"Two jobs are already running ({'; '.join(j.goal[:40] for j in self.running())}). Wait for one or cancel it."
            self._n += 1
            job = Job(self._n, goal, persona)
            self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True, name=f"job-{job.id}").start()
        self.on_change()
        return job, f"Started background job {job.id}: {job.goal[:80]}"

    def cancel(self, jid=None):
        hit = [j for j in self.running() if jid in (None, j.id)]
        for j in hit:
            j.cancel.set()
        return hit

    def _run(self, job):
        import brain as brain_mod
        import tools
        tools._CTX.job = job.id                     # approvals from this thread are labelled as the job's
        try:
            b = self.make_brain(job.persona)
            b.allowed = set(ALLOWED)
            b.max_rounds = MAX_STEPS

            def on_event(kind, data):
                if kind == "tool_start" and isinstance(data, dict):
                    args = data.get("args") or {}
                    det = args.get("query") or args.get("command") or args.get("path") or args.get("action") or ""
                    job.steps.append(f"{data.get('name', '').replace('_', ' ')}: {str(det)[:80]}".rstrip(": "))
                    self.on_change()
            reply = b.ask(JOB_PROMPT.format(goal=job.goal), on_text=lambda d: None, on_event=on_event, cancel=job.cancel)
            if job.cancel.is_set() or reply is None:
                job.status = "cancelled"
                return
            m = re.search(r"SUMMARY:\s*(.+?)(?:\n\s*\n|\n(?=#)|$)", reply, re.S)
            job.summary = (m.group(1).strip() if m else reply.strip().split("\n")[0])[:400]
            body = reply[m.end():].strip() if m else reply.strip()
            job.path = self._save(job, body)
            job.status = "done"
        except brain_mod.Interrupted:
            job.status = "cancelled"
        except Exception as e:
            job.status = "failed"
            job.summary = f"The job failed: {type(e).__name__}: {e}"[:300]
            self.log(f"[jobs] job {job.id} failed: {e}")
        finally:
            job.finished = time.time()
            self.on_change()
            if job.status in ("done", "failed"):
                try:
                    self.on_done(job)
                except Exception as e:
                    self.log(f"[jobs] announce failed: {e}")

    def _save(self, job, body):
        folder = config.JARVIS_DIR / "Jobs"
        folder.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", job.goal.lower())[:50].strip("-") or "job"
        path = folder / f"{datetime.now():%Y-%m-%d %H%M} {slug}.md"
        steps = "\n".join(f"- {s}" for s in job.steps) or "- (no tools needed)"
        path.write_text(f"# {job.goal}\n\n_{datetime.now():%A %B %d, %Y %H:%M} · background job {job.id}_\n\n"
                        f"**Summary:** {job.summary}\n\n{body}\n\n---\n<details><summary>Steps taken</summary>\n\n{steps}\n</details>\n",
                        encoding="utf-8")
        return path

    def views(self):
        return [j.view() for j in sorted(self.jobs.values(), key=lambda j: -j.started)][:8]

    def spoken_status(self):
        run = self.running()
        if not run:
            done = [j for j in self.jobs.values() if j.status == "done"]
            return ("Nothing running in the background." + (f" The last job finished: {done[-1].summary}" if done else ""))
        return " ".join(f"Job {j.id}, {j.goal[:60]}: {len(j.steps)} steps in, currently {j.steps[-1] if j.steps else 'starting'}."
                        for j in run)
