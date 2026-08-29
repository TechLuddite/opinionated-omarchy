"""Matrix runner: {task x model x variant x repeat} through Ollama.

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
import time

import httpx

from . import checks, db, spec

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://host.docker.internal:11434")
CONCURRENCY = int(os.environ.get("SB_CONCURRENCY", "2"))
TIMEOUT = float(os.environ.get("SB_TIMEOUT", "300"))

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


async def _execute(run_id, bench, models, variants, repeats, params, resume):
    done = db.existing_cells(run_id) if resume else set()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as cl:
            for model in models:                        # <- the affinity barrier
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

        db.finish_run(run_id, "aborted" if run_id in _stopping else "done",
                      "stopped by operator - partial matrix kept" if run_id in _stopping else None)
    except Exception as e:
        db.finish_run(run_id, "error", f"{type(e).__name__}: {e}"[:500])
    finally:
        _running.pop(run_id, None)
        _stopping.discard(run_id)


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
        if task:
            db.record_grades(case["id"], checks.run_checks(case["output"] or "", task))
            n += 1
    return n


def is_running(run_id):
    return run_id in _running
