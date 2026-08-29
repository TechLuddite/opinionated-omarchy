"""Skill Bench for Omarchy -- HTTP API + UI.

Local only, no auth, plain HTTP. That is a deliberate posture, not an oversight: the
server binds to 127.0.0.1 on the developer's own machine and talks to an Ollama on the
same host. Nothing here holds a credential, so there is nothing for TLS to protect in
transit. See README 'Security posture' before exposing it anywhere else.
"""
import json
import statistics

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from . import db, runner, spec, theme, ui, vm

app = FastAPI(title="Omarchy Skill Bench", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup():
    n = db.init()
    if n:
        print(f"reconciled {n} run(s) orphaned by a restart", flush=True)


# ------------------------------------------------------------------ health

@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
async def readyz():
    """Real readiness: the DB answers and Ollama answers.

    A liveness probe that only proves the HTTP process is up was an open finding
    against the bench this one is descended from -- it stays green while the thing
    underneath is dead.
    """
    out = {"db": False, "ollama": False}
    try:
        db.conn().execute("SELECT 1").fetchone()
        out["db"] = True
    except Exception as e:
        out["db_error"] = str(e)[:200]
    try:
        async with httpx.AsyncClient(timeout=5) as cl:
            r = await cl.get(f"{runner.OLLAMA_BASE}/api/tags")
            out["ollama"] = r.status_code == 200
    except Exception as e:
        out["ollama_error"] = str(e)[:200]
    # VMs are reported but never gate readiness: the chat lane is fully usable with
    # both test VMs powered off, and a 503 there would be a lie about the whole bench.
    if len(vm.POOL):
        try:
            out["vms"] = await vm.POOL.status()
        except Exception as e:
            out["vms_error"] = str(e)[:200]
    ok = out["db"] and out["ollama"]
    return JSONResponse(out, status_code=200 if ok else 503)


# ------------------------------------------------------------------ catalogue

@app.get("/api/models")
async def api_models():
    try:
        return {"models": await runner.list_models()}
    except Exception as e:
        raise HTTPException(503, f"ollama unreachable at {runner.OLLAMA_BASE}: {e}")


@app.get("/api/benches")
def api_benches():
    return {"benches": [
        {"name": b["name"], "description": b.get("description", ""), "spec_sha": b["spec_sha"],
         "tasks": [t["id"] for t in b["tasks"]], "skills": b.get("skills", []),
         "control": bool(b.get("control")),
         "lane": b.get("lane", "chat"),
         "defaults": b.get("defaults", {})}
        for b in spec.list_benches()]}


@app.get("/api/skills")
def api_skills():
    return {"skills": spec.list_skills()}


@app.get("/api/vms")
async def api_vms():
    """The agentic lane's targets, and whether each is actually usable right now."""
    if not len(vm.POOL):
        return {"vms": [], "configured": False}
    try:
        return {"vms": await vm.POOL.status(), "configured": True}
    except Exception as e:
        raise HTTPException(503, f"cannot probe VMs: {e}")


@app.get("/api/themes")
def api_themes():
    return {"themes": theme.list_themes()}


# ------------------------------------------------------------------ runs

@app.post("/api/runs")
async def api_launch(payload: dict):
    try:
        return {"run_id": runner.launch(
            payload["bench"], payload.get("models") or [], payload.get("variants") or [],
            int(payload.get("repeats") or 0) or None, payload.get("params"))}
    except (runner.RunError, spec.SpecError) as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(400, f"missing field {e}")


@app.get("/api/runs")
def api_runs():
    rows = db.conn().execute(
        "SELECT r.id, b.name AS bench, r.spec_sha, r.status, r.models, r.variants,"
        "       r.repeats, r.started_at, r.finished_at, r.error,"
        "       (SELECT count(*) FROM case_result c WHERE c.run_id=r.id) AS cases"
        " FROM bench_run r JOIN bench b ON b.id=r.bench_id ORDER BY r.id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["models"] = json.loads(d["models"])
        d["variants"] = json.loads(d["variants"])
        d["running"] = runner.is_running(d["id"])
        out.append(d)
    return {"runs": out}


def _agg(run_ids):
    """Per model x variant, and per model x variant x task. One query path for both."""
    marks = ",".join("?" * len(run_ids))
    rows = db.conn().execute(
        f"SELECT c.id, c.model, c.variant, c.task_id, c.status, c.prompt_tokens,"
        f"       c.completion_tokens, c.latency_s,"
        f"       (SELECT count(*) FROM grade g WHERE g.case_id=c.id) AS n_checks,"
        f"       (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.passed=1) AS n_passed,"
        f"       (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='post')"
        f"         AS n_post,"
        f"       (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='post'"
        f"         AND g.passed=1) AS n_post_passed"
        f" FROM case_result c WHERE c.run_id IN ({marks})", run_ids).fetchall()

    def summarise(bucket):
        cases = len(bucket)
        errs = sum(1 for r in bucket if r["status"] != "ok")
        checks = sum(r["n_checks"] for r in bucket)
        passed = sum(r["n_passed"] for r in bucket)
        # State assertions are also counted inside `quality`; `state` isolates them, so
        # "said the right thing" and "left the machine fixed" can be read apart.
        post = sum(r["n_post"] for r in bucket)
        post_passed = sum(r["n_post_passed"] for r in bucket)
        lat = [r["latency_s"] for r in bucket if r["latency_s"] is not None]
        pin = [r["prompt_tokens"] for r in bucket if r["prompt_tokens"] is not None]
        pout = [r["completion_tokens"] for r in bucket if r["completion_tokens"] is not None]
        return {
            "cases": cases, "errors": errs,
            "checks": checks, "passed": passed,
            "quality": round(passed / checks, 4) if checks else None,
            "post": post, "post_passed": post_passed,
            "state": round(post_passed / post, 4) if post else None,
            "success": round((cases - errs) / cases, 4) if cases else None,
            "tokens_in": round(statistics.mean(pin)) if pin else None,
            "tokens_out": round(statistics.mean(pout)) if pout else None,
            "latency_mean": round(statistics.mean(lat), 2) if lat else None,
            "latency_p95": round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 2) if lat else None,
        }

    by_mv, by_mvt = {}, {}
    for r in rows:
        by_mv.setdefault((r["model"], r["variant"]), []).append(r)
        by_mvt.setdefault((r["model"], r["variant"], r["task_id"]), []).append(r)
    return (
        [{"model": m, "variant": v, **summarise(b)} for (m, v), b in sorted(by_mv.items())],
        [{"model": m, "variant": v, "task_id": t, **summarise(b)}
         for (m, v, t), b in sorted(by_mvt.items())],
    )


@app.get("/api/runs/{run_id}")
def api_run(run_id: int):
    row = db.conn().execute(
        "SELECT r.*, b.name AS bench FROM bench_run r JOIN bench b ON b.id=r.bench_id"
        " WHERE r.id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"no run {run_id}")
    results, per_task = _agg([run_id])
    return {
        "run": {"id": row["id"], "bench": row["bench"], "spec_sha": row["spec_sha"],
                "status": row["status"], "error": row["error"], "repeats": row["repeats"],
                "models": json.loads(row["models"]), "variants": json.loads(row["variants"]),
                "skill_revs": json.loads(row["skill_revs"]), "params": json.loads(row["params"]),
                "started_at": row["started_at"], "finished_at": row["finished_at"],
                "running": runner.is_running(run_id)},
        "results": results, "per_task": per_task,
    }


@app.get("/api/runs/{run_id}/cases")
def api_cases(run_id: int, task: str = Query(None), variant: str = Query(None),
              model: str = Query(None)):
    sql = ("SELECT id, task_id, model, variant, repeat_idx, status, output, error,"
           " prompt_tokens, completion_tokens, latency_s FROM case_result WHERE run_id=?")
    args = [run_id]
    for col, val in (("task_id", task), ("variant", variant), ("model", model)):
        if val:
            sql += f" AND {col}=?"
            args.append(val)
    cases = []
    for c in db.conn().execute(sql + " ORDER BY task_id, variant, model, repeat_idx", args):
        d = dict(c)
        d["checks"] = [dict(g) for g in db.conn().execute(
            "SELECT criterion, passed, note FROM grade WHERE case_id=? ORDER BY id", (c["id"],))]
        cases.append(d)
    return {"cases": cases}


@app.post("/api/runs/{run_id}/stop")
def api_stop(run_id: int):
    try:
        runner.stop(run_id)
    except runner.RunError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/runs/{run_id}/resume")
async def api_resume(run_id: int):
    try:
        return {"run_id": runner.resume(run_id)}
    except (runner.RunError, spec.SpecError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/runs/{run_id}/regrade")
def api_regrade(run_id: int):
    try:
        return {"regraded": runner.regrade(run_id)}
    except (runner.RunError, spec.SpecError) as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ ui

@app.get("/", response_class=HTMLResponse)
def index(theme_name: str = Query(None, alias="theme")):
    return ui.page(theme.load(theme_name), theme.list_themes())
