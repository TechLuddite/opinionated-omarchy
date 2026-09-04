"""Matrix runner: {task x model x variant x repeat}, in one of two lanes.

THE CHAT LANE prompts Ollama and grades the reply. It is the original bench and the one
the nexus1 baseline is comparable with.

THE AGENTIC LANE runs a real agent harness (`pi`) on a real Omarchy VM, lets it act on
the machine, and grades the machine afterwards. It answers the question the chat lane
structurally cannot: not "did the model name hyprctl" but "is the display configured".

Three things differ in the agentic lane and all three are deliberate:

  * CONCURRENCY IS THE VM POOL, not SB_CONCURRENCY. Two cases cannot share a machine
    when each one is allowed to edit that machine's files.
  * A CASE IS ISOLATED BY RESTORING DECLARED PATHS, not by rolling back the disk. See
    vm.py for why the container must not drive libvirt. The bench declares what to
    restore; anything it does not declare persists, and that is a real limit.
  * SKILLS ARE FILES, not a system prompt. pi loads a directory the way the real
    harness does, so a topic guide can matter here in a way it cannot in a prompt.

MODEL AFFINITY is not an optimisation here, it is required. Ollama on this box runs
with OLLAMA_MAX_LOADED_MODELS=1, so interleaving models would evict and reload weights
between every single case. The runner therefore finishes the whole suite on one model
before touching the next, and SB_CONCURRENCY is parallelism WITHIN the current model
(same weights already resident, so it is free).

There is no budget guard and no cost column. Everything runs against local Ollama, so
every case costs nothing; what the skill actually costs shows up as prompt tokens,
which is the number worth watching.
"""
import asyncio
import json
import os
import shlex
import time

import httpx

from . import checks, db, spec, vm, vmchecks

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://host.docker.internal:11434")
# Where the CHAT lane posts. Defaults to Ollama so nothing changes for a local run; point
# it at an OpenAI-compatible gateway (https://opencode.ai/zen for Zen) to bench cloud
# models. The agentic lane is separate: it drives `pi` on a VM and is not affected.
# `or` rather than a get() default: compose interpolates an unset variable to the EMPTY
# STRING, and os.environ.get returns that empty string rather than falling back, which
# would post to a URL with no host.
CHAT_BASE = os.environ.get("SB_CHAT_BASE") or OLLAMA_BASE
# Bearer token for CHAT_BASE, when it needs one. Read from the environment only, never
# from a spec or an argument, so it cannot reach a bench file, the results database or
# the process table.
CHAT_API_KEY = os.environ.get("SB_CHAT_API_KEY", "")
CONCURRENCY = int(os.environ.get("SB_CONCURRENCY", "2"))
TIMEOUT = float(os.environ.get("SB_TIMEOUT", "300"))

# An agentic case is a whole agent session on a 4-vCPU VM talking to a local model. It
# is minutes, not seconds, and a hung one must not hold a VM for the rest of the run.
AGENT_TIMEOUT = float(os.environ.get("SB_AGENT_TIMEOUT", "600"))
# The Ollama host as the VM sees it: the libvirt bridge, not host.docker.internal.
VM_OLLAMA_HOST = os.environ.get("SB_VM_OLLAMA_HOST", "192.168.122.1")

_running = {}   # run_id -> asyncio.Task
_stopping = set()


class RunError(RuntimeError):
    pass


async def list_models():
    """Chat-capable local models. Embedding models are filtered out: they are served by
    the same Ollama and appear in /api/tags, but they cannot answer a bench task."""
    async with httpx.AsyncClient(timeout=10) as cl:
        r = await cl.get(f"{OLLAMA_BASE}/api/tags")
        r.raise_for_status()
        names = (m["name"].replace(":latest", "") for m in r.json().get("models", []))
        return sorted(n for n in names if "embed" not in n.lower())


async def _resolve(model):
    """Ollama needs the tag; the UI shows the bare name, as the baseline data does.

    Ollama ONLY. A gateway model id is a plain string with no tag (`glm-5.2`,
    `deepseek-v4-flash`), and appending `:latest` to one produces a model that does not
    exist. The agentic lane still resolves against Ollama because `pi` runs on a VM
    talking to the local server, so this is keyed on the chat base rather than on a
    global switch.
    """
    if CHAT_BASE != OLLAMA_BASE:
        return model
    return model if ":" in model else f"{model}:latest"


def _answer_of(data):
    """The model's answer, and where it was found.

    Reasoning models put their output in `message.reasoning` and leave `content` null or
    empty. Reading content alone records those as "said nothing" with status ok, which is
    a silent zero rather than a measurement, and it is not rare: of 18 reachable Zen
    models, 12 returned null or empty content on a short prompt. Confirmed on kimi-k3 and
    the whole MiniMax family.

    The source is recorded rather than hidden, because grading a reasoning trace is not
    the same as grading an answer. A trace may consider and reject the trap before
    settling on the right command, so a forbidden-string check can fire on a model that
    got it right. Anything comparing the two must be able to see which is which.
    """
    msg = ((data.get("choices") or [{}])[0] or {}).get("message") or {}
    content = msg.get("content") or ""
    if content.strip():
        return content, "content"
    reasoning = msg.get("reasoning") or ""
    if reasoning.strip():
        return reasoning, "reasoning"
    return "", "empty"


def _status_of(exc):
    """A provider 5xx is a configuration problem, not a model result.

    Zen returns a bare 500 "Internal server error" for any model the account cannot
    reach, which is indistinguishable from a real outage: 38 of 59 models returned it
    during probing. Recording that as a normal case error would let an unconfigured
    model look exactly like one that failed the task. Filter `unavailable` out before
    scoring rather than reading it as a result.
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return "unavailable"
    return "error"


async def _one_case(cl, run_id, task, model, variant, repeat_idx, sys_prompt, params):
    messages = []
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt})
    messages.append({"role": "user", "content": task["prompt"]})
    # Generation parameters go TOP LEVEL. They used to sit in an Ollama-native `options`
    # object, which the OpenAI-compatible /v1 endpoint ignores. Measured on both servers:
    # `options.num_predict = 8` returned 80 completion tokens from Ollama and 172 from
    # Zen. So no chat-lane run has ever applied the temperature its spec asked for,
    # including the +29.3 pt baseline; every one used the server default. Both arms of a
    # paired run were equally affected, so past comparisons stand, but a run made after
    # this change is not comparable to one made before it.
    body = {"model": await _resolve(model), "messages": messages, "stream": False,
            "temperature": params.get("temperature", 0.2)}
    # max_tokens is sent ONLY when a spec asks for one. The old nominal 512 was never in
    # force, so emitting it here would impose a brand new cap while looking like a
    # portability fix. The right value is an open question rather than an oversight:
    # several models spend 500+ tokens reasoning before producing any content, and under
    # a request-metered plan a truncated answer costs a whole request and returns nothing.
    if params.get("max_tokens"):
        body["max_tokens"] = params["max_tokens"]

    t0 = time.monotonic()
    try:
        r = await cl.post(f"{CHAT_BASE}/v1/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()
        out, source = _answer_of(data)
        usage = data.get("usage") or {}
        case_id = db.record_case(
            run_id, task["id"], model, variant, repeat_idx, "ok", body, output=out,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_s=round(time.monotonic() - t0, 3), output_source=source)
        if case_id:
            db.record_grades(case_id, checks.run_checks(out, task))
    except Exception as e:                              # a dead model is data, not a crash
        db.record_case(run_id, task["id"], model, variant, repeat_idx, _status_of(e), body,
                       error=f"{type(e).__name__}: {e}"[:500],
                       latency_s=round(time.monotonic() - t0, 3))


# ------------------------------------------------------------------ agentic lane

def _pi_command(model, skill_dir, prompt_path, params):
    """The pi invocation for one case.

    --print          non-interactive: run the prompt and exit.
    --no-session     no session file, so a case cannot inherit an earlier one's memory.
    --skill <dir>    the real bundle-loading path, frontmatter and all.
    @<file>          the prompt is passed as a FILE, never on the command line: bench
                     prompts contain quotes, newlines and $, and argv is where a spec
                     silently becomes a different spec.
    """
    argv = ["pi", "--print", "--no-session", "--provider", "ollama",
            "--model", shlex.quote(model),
            "--thinking", shlex.quote(str(params.get("thinking", "off")))]
    if skill_dir:
        argv += ["--skill", shlex.quote(skill_dir)]
    else:
        # Without this pi would discover any skill already installed on the VM, and the
        # 'none' variant would silently stop being a control.
        argv += ["--no-skills"]
    argv += ["--", f"@{shlex.quote(prompt_path)}"]
    return " ".join(argv)


async def _one_agentic_case(pool, run_id, bench, task, model, variant, repeat_idx,
                            skill_files, params):
    """Reset a VM, run an agent on it, then grade the transcript AND the machine."""
    window = f"{task['id']}-{repeat_idx}"
    restore_paths = ((bench.get("defaults") or {}).get("vm") or {}).get("restore") or []
    request = {"lane": "agentic", "model": model, "variant": variant,
               "task": task["id"], "prompt": task["prompt"]}
    # Start the clock AFTER the VM is in hand. Concurrency here is the VM pool, so a case
    # launched 12th waits for a machine, and timing from before `acquire()` folds that queue
    # into `latency_s` -- which then reads as "this variant was slower" purely because it ran
    # second. Runs up to and including 24 carry the old semantics; do not compare their
    # agentic latencies against later ones, or use them as a cost figure at all.
    queued_at = time.monotonic()
    machine = await pool.acquire()
    t0 = time.monotonic()
    try:
        request["vm"] = machine.name
        request["queue_wait_s"] = round(t0 - queued_at, 3)

        # 1. Put the machine back to the state every case starts from, then apply this
        #    task's seed -- the breakage the agent is being asked to fix.
        await machine.restore(restore_paths)
        seed = task.get("seed")
        if seed:
            await machine.put(f"{vm.REMOTE_ROOT}/{window}/seed.sh",
                              "#!/usr/bin/env bash\nset -euo pipefail\n" + seed, mode="755")
            rc, out = await machine.run(f"bash {vm.REMOTE_ROOT}/{window}/seed.sh", timeout=180)
            if rc != 0:
                # A seed that did not apply means the case never posed its question. That
                # is an error, not a zero score: scoring it would poison the average with
                # a case the agent never actually faced.
                raise vm.VMError(f"seed failed (exit {rc}): {out.strip()[:300]}")

        # 2. Deliver the skill bundle and the prompt, then run the agent in a tmux
        #    window so the VM's console mirrors it live.
        skill_dir = await machine.deliver_skill(variant, skill_files)
        prompt_path = f"{vm.REMOTE_ROOT}/{window}/prompt.txt"
        await machine.put(prompt_path, task["prompt"])
        # The UI carries bare names ('qwen2.5') because the baseline data does; pi needs
        # the tag its models.json declares, and `--model` is a fuzzy pattern there, so a
        # bare name could match a different model entirely ('qwen2.5' -> qwen2.5-coder).
        command = _pi_command(await _resolve(model), skill_dir, prompt_path, params)
        rc, output, timed_out = await machine.run_in_tmux(
            window, command, timeout=params.get("agent_timeout") or AGENT_TIMEOUT)

        # 3. Grade the machine even when the agent errored or timed out. A run that
        #    fixed the display and then crashed still fixed the display, and recording
        #    that is more honest than throwing the case away.
        post = await vmchecks.run_post(machine, task)

        status = "ok" if rc == 0 and not timed_out else "error"
        error = None
        if timed_out:
            error = f"agent exceeded {params.get('agent_timeout') or AGENT_TIMEOUT:.0f}s"
        elif rc != 0:
            error = f"pi exited {rc}"

        case_id = db.record_case(
            run_id, task["id"], model, variant, repeat_idx, status, request,
            output=output, error=error, latency_s=round(time.monotonic() - t0, 3))
        if case_id:
            grades = checks.run_checks(output or "", task)
            db.record_grades(case_id, grades, post_grades=post)
    except Exception as e:
        db.record_case(run_id, task["id"], model, variant, repeat_idx, "error", request,
                       error=f"{type(e).__name__}: {e}"[:500],
                       latency_s=round(time.monotonic() - t0, 3))
    finally:
        # Only hand back a machine that is still answering. A case can leave its VM
        # unreachable -- rebooted, networking broken, session gone -- and releasing it blind
        # feeds every subsequent case to a dead host.
        if await machine.ready():
            pool.release(machine)
        else:
            # Do NOT record a case here: this runs on the success path too, and the case
            # that just scored already has its row. The loss is reported on the RUN, below,
            # because a run that quietly finished on half its machines is the thing that
            # produced a fake 5.5 point regression in run 29.
            pool.drain(machine)


async def _execute_agentic(run_id, bench, models, variants, repeats, params, resume):
    pool = vm.POOL
    if not len(pool):
        raise RunError("no VMs configured; set SB_VMS (name=host,...) in compose.yaml")

    done = db.existing_cells(run_id) if resume else set()
    restore_paths = ((bench.get("defaults") or {}).get("vm") or {}).get("restore") or []

    # The baseline is taken ONCE, from the machines as they are now. Every case in this
    # run is restored to it, so cases cannot contaminate each other through the declared
    # paths -- and a run is reproducible against a VM someone has since poked at.
    for machine in pool.vms:
        if not await machine.ready():
            raise RunError(f"VM {machine.name} ({machine.host}) is not reachable over ssh")
        await machine.snapshot(restore_paths)

    files_by_variant = {v: spec.skill_files_for(v)[0] for v in variants}

    for model in models:                                # the same affinity barrier
        if run_id in _stopping:
            break
        cells = [(t, v, i) for v in variants for t in bench["tasks"]
                 for i in range(repeats)
                 if (t["id"], model, v, i) not in done]

        async def guarded(task, variant, idx):
            if run_id in _stopping:
                return
            await _one_agentic_case(pool, run_id, bench, task, model, variant, idx,
                                    files_by_variant[variant], params)

        # No semaphore: the VM pool IS the concurrency limit, because a case owns a
        # whole machine for its duration.
        await asyncio.gather(*(guarded(t, v, i) for t, v, i in cells))


async def _execute(run_id, bench, models, variants, repeats, params, resume):
    try:
        if bench.get("lane") == "agentic":
            await _execute_agentic(run_id, bench, models, variants, repeats, params, resume)
            note = ("stopped by operator - partial matrix kept"
                    if run_id in _stopping else None)
            drained = getattr(vm.POOL, "drained", [])
            if drained:
                # A run finished on fewer machines than it started with. Say so on the run
                # itself: the cases lost are not distributed evenly across variants, because
                # variants run in order, so the arithmetic is biased and not merely thinner.
                lost = ", ".join(f"{v.name} ({v.host})" for v in drained)
                note = ((note + " | ") if note else "") + (
                    f"DEGRADED: {len(drained)} VM(s) drained mid-run after a case left them "
                    f"unreachable ({lost}). Cases lost are variant-correlated; treat any "
                    f"comparison from this run as unsafe.")
            db.finish_run(run_id, "aborted" if run_id in _stopping else "done", note)
            return
        await _execute_chat(run_id, bench, models, variants, repeats, params, resume)
        db.finish_run(run_id, "aborted" if run_id in _stopping else "done",
                      "stopped by operator - partial matrix kept" if run_id in _stopping else None)
    except Exception as e:
        db.finish_run(run_id, "error", f"{type(e).__name__}: {e}"[:500])
    finally:
        _running.pop(run_id, None)
        _stopping.discard(run_id)


async def _execute_chat(run_id, bench, models, variants, repeats, params, resume):
    done = db.existing_cells(run_id) if resume else set()
    headers = {"Authorization": f"Bearer {CHAT_API_KEY}"} if CHAT_API_KEY else {}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as cl:
        for model in models:                            # <- the affinity barrier
            if run_id in _stopping:
                break
            cells = [(t, v, i) for v in variants for t in bench["tasks"]
                     for i in range(repeats)
                     if (t["id"], model, v, i) not in done]
            sem = asyncio.Semaphore(CONCURRENCY)

            async def guarded(task, variant, idx):
                if run_id in _stopping:
                    return
                async with sem:
                    sys_prompt, _ = spec.system_prompt_for(variant)
                    await _one_case(cl, run_id, task, model, variant, idx,
                                    sys_prompt, params)

            await asyncio.gather(*(guarded(t, v, i) for t, v, i in cells))


def launch(bench_name, models, variants, repeats, params=None):
    bench = spec.load_bench(bench_name)
    if not models:
        raise RunError("pick at least one model")
    if len(variants) < 1:
        raise RunError("pick at least one variant")
    if len(set(variants)) != len(variants):
        raise RunError("variants must differ")

    skill_revs = {}
    for v in variants:
        _, revs = spec.system_prompt_for(v)             # validates, and pins content
        skill_revs.update(revs)

    # Fail at launch, not four cases in. An agentic run with no reachable VM would
    # otherwise record a wall of identical errors and look like a model problem.
    if bench.get("lane") == "agentic":
        if not len(vm.POOL):
            raise RunError("this bench is agentic but no VMs are configured;"
                           " set SB_VMS (name=host,...) in compose.yaml")

    params = {**(bench.get("defaults") or {}).get("params", {}), **(params or {})}
    repeats = repeats or (bench.get("defaults") or {}).get("repeats", 1)
    run_id = db.create_run(bench, bench, models, variants, repeats, params, skill_revs)
    _running[run_id] = asyncio.create_task(
        _execute(run_id, bench, models, variants, repeats, params, resume=False))
    return run_id


def resume(run_id):
    c = db.conn()
    row = c.execute("SELECT * FROM bench_run WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise RunError(f"no run {run_id}")
    if run_id in _running:
        raise RunError(f"run {run_id} is already running")

    bench = json.loads(row["spec"])
    live = spec.load_bench(bench["name"])
    if live["spec_sha"] != row["spec_sha"]:
        raise RunError("the bench has been edited since this run started - launch a new run")
    for name, sha in json.loads(row["skill_revs"]).items():
        if spec.load_skill(name)[1] != sha:
            raise RunError(f"skill {name!r} has been edited since this run - launch a new run")

    c.execute("UPDATE bench_run SET status='running', error=NULL, finished_at=NULL WHERE id=?",
              (run_id,))
    c.commit()
    _running[run_id] = asyncio.create_task(
        _execute(run_id, bench, json.loads(row["models"]), json.loads(row["variants"]),
                 row["repeats"], json.loads(row["params"]), resume=True))
    return run_id


def stop(run_id):
    if run_id not in _running:
        raise RunError(f"run {run_id} is not running")
    _stopping.add(run_id)


def regrade(run_id):
    """Re-run every check from stored output. Zero model calls."""
    c = db.conn()
    row = c.execute("SELECT spec FROM bench_run WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise RunError(f"no run {run_id}")
    tasks = {t["id"]: t for t in json.loads(row["spec"])["tasks"]}
    live = {t["id"]: t for t in spec.load_bench(json.loads(row["spec"])["name"])["tasks"]}
    tasks.update(live)                                  # regrade against the CURRENT checks
    n = 0
    for case in c.execute("SELECT id, task_id, output FROM case_result"
                          " WHERE run_id=? AND status='ok'", (run_id,)).fetchall():
        task = tasks.get(case["task_id"])
        if not task:
            continue
        # Post assertions were evaluated against a VM that has since moved on, so they
        # cannot be recomputed from stored output the way checks can. Carry them across
        # verbatim -- record_grades clears the case's rows, so not doing this would make
        # regrade silently delete every state assertion in the run.
        kept = [{"criterion": g["criterion"], "score": g["score"],
                 "passed": bool(g["passed"]), "note": g["note"]}
                for g in c.execute("SELECT criterion, score, passed, note FROM grade"
                                   " WHERE case_id=? AND grader='post' ORDER BY id",
                                   (case["id"],))]
        db.record_grades(case["id"], checks.run_checks(case["output"] or "", task),
                         post_grades=kept)
        n += 1
    return n


def is_running(run_id):
    return run_id in _running
