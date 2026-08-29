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
    """Ollama needs the tag; the UI shows the bare name, as the baseline data does."""
    return model if ":" in model else f"{model}:latest"


async def _one_case(cl, run_id, task, model, variant, repeat_idx, sys_prompt, params):
    messages = []
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt})
    messages.append({"role": "user", "content": task["prompt"]})
    body = {"model": await _resolve(model), "messages": messages, "stream": False,
            "options": {"temperature": params.get("temperature", 0.2),
                        "num_predict": params.get("max_tokens", 512)}}

    t0 = time.monotonic()
    try:
        r = await cl.post(f"{OLLAMA_BASE}/v1/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()
        out = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage") or {}
        case_id = db.record_case(
            run_id, task["id"], model, variant, repeat_idx, "ok", body, output=out,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_s=round(time.monotonic() - t0, 3))
        if case_id:
            db.record_grades(case_id, checks.run_checks(out, task))
    except Exception as e:                              # a dead model is data, not a crash
        db.record_case(run_id, task["id"], model, variant, repeat_idx, "error", body,
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
    t0 = time.monotonic()
    machine = await pool.acquire()
    try:
        request["vm"] = machine.name

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
        pool.release(machine)


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
            db.finish_run(run_id, "aborted" if run_id in _stopping else "done",
                          "stopped by operator - partial matrix kept"
                          if run_id in _stopping else None)
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
    async with httpx.AsyncClient(timeout=TIMEOUT) as cl:
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
