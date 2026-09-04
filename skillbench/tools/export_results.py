#!/usr/bin/env python3
"""Export the results database to tracked JSONL, so the evidence outlives one disk.

    python3 skillbench/tools/export_results.py

WHY THIS EXISTS. `skillbench/data/` is gitignored, and correctly so by the repo's usual
rule: derived artefacts are rebuilt, not committed. But that rule assumes the artefact CAN
be rebuilt. `research/data/problems.db` regenerates from the JSONL in 0.2 s. This database
does not regenerate from anything. It is the record of many hours of GPU time across 31
runs, and every number in JOURNAL.md and MODELS.md traces back to it. One disk failure and
the project's entire measured history becomes a set of claims with no evidence behind it.

So this writes the parts that matter into `skillbench/results/`, which IS tracked:

    runs.jsonl    one line per run: metadata, plus the per-variant and per-task aggregates
                  computed exactly as app/main.py:_agg does, so a reader can check a
                  journal figure without writing SQL or running the container
    cases.jsonl   one line per case: status, timings, and the grade tallies lift_test.py
                  needs, so every significance test in the journal is re-derivable
    grades.jsonl  one line per assertion: which check failed is the actual diagnostic, and
                  it is the thing no summary can reconstruct
    specs/        the distinct bench specs, keyed by spec_sha, as pretty-printed JSON.
                  NOT the original YAML and not sha-verifiable against it: spec_sha is
                  sha256 of the raw YAML file, while the database stores a re-serialised
                  parse of it. So the sha identifies which spec ran; the file says what
                  that spec contained. Reformatting therefore costs nothing that was not
                  already lost, and buys a file a human can read

WHAT IS DELIBERATELY DROPPED. `case_result.request` is 4.87 MB of the ~5.7 MB database: the
full prompt re-recorded for every case. It is derivable from the spec, which is exported
beside it, so carrying it would multiply the tracked size by ten to preserve nothing. The
non-prompt keys inside it (lane, vm, queue_wait_s) ARE kept, because those are per-case
facts that exist nowhere else.

This is an export, not a source of truth. The database stays authoritative while it exists;
re-run this after any run that the journal is going to cite.
"""
import json
import shutil
import sqlite3
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DB = REPO / "skillbench" / "data" / "skillbench.db"
OUT = REPO / "skillbench" / "results"

# Keys inside case_result.request worth keeping. The prompt is not one of them; see above.
REQUEST_KEYS = ("lane", "vm", "queue_wait_s")


def summarise(bucket):
    """Byte-for-byte the aggregation in app/main.py:_agg.

    Kept as a copy rather than an import on purpose: app/ pulls in FastAPI, and this has to
    run from a bare clone with nothing installed. If _agg ever changes, change it here too,
    or the tracked numbers quietly stop matching the ones the UI shows.
    """
    cases = len(bucket)
    errs = sum(1 for r in bucket if r["status"] != "ok")
    checks = sum(r["n_checks"] for r in bucket)
    passed = sum(r["n_passed"] for r in bucket)
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


def write_jsonl(path, records):
    """LF and UTF-8 pinned, one compact record per line, as research/tools/corpus.py does.

    Compact separators and a stable key order matter here: this file is regenerated whole on
    every export, so anything that reorders keys turns a one-run append into a whole-file
    diff that hides the run actually added.
    """
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(records)


def main():
    if not DB.exists():
        raise SystemExit(f"no results database at {DB}")
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    # Clear the GENERATED files only. An rmtree here would take README.md with it on every
    # export, which is the kind of thing that is noticed one commit too late.
    if (OUT / "specs").exists():
        shutil.rmtree(OUT / "specs")
    for stale in OUT.glob("*.jsonl"):
        stale.unlink()
    (OUT / "specs").mkdir(parents=True)

    # ---- per-case rows, and the tallies every aggregate is built from ------------------
    cases = c.execute("""
        SELECT c.id, c.run_id, c.task_id, c.model, c.variant, c.repeat_idx, c.status,
               c.error, c.output, c.prompt_tokens, c.completion_tokens, c.latency_s,
               c.created_at, c.request, c.output_source,
               (SELECT count(*) FROM grade g WHERE g.case_id=c.id) AS n_checks,
               (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.passed=1) AS n_passed,
               (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='post')
                 AS n_post,
               (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='post'
                 AND g.passed=1) AS n_post_passed
        FROM case_result c ORDER BY c.id""").fetchall()

    by_run, case_rows = {}, []
    for r in cases:
        by_run.setdefault(r["run_id"], []).append(r)
        try:
            req = json.loads(r["request"])
        except (ValueError, TypeError):
            req = {}
        row = {k: r[k] for k in (
            "id", "run_id", "task_id", "model", "variant", "repeat_idx", "status",
            "error", "output", "prompt_tokens", "completion_tokens", "latency_s",
            "created_at", "output_source", "n_checks", "n_passed", "n_post",
            "n_post_passed")}
        row.update({k: req[k] for k in REQUEST_KEYS if k in req})
        case_rows.append(row)

    # ---- per-run metadata + aggregates -------------------------------------------------
    runs, seen_spec = [], {}
    for r in c.execute("""
            SELECT r.*, b.name AS bench FROM bench_run r
            JOIN bench b ON b.id = r.bench_id ORDER BY r.id"""):
        bucket = by_run.get(r["id"], [])
        by_mv, by_mvt = {}, {}
        for cr in bucket:
            by_mv.setdefault((cr["model"], cr["variant"]), []).append(cr)
            by_mvt.setdefault((cr["model"], cr["variant"], cr["task_id"]), []).append(cr)
        runs.append({
            "id": r["id"], "bench": r["bench"], "spec_sha": r["spec_sha"],
            "models": json.loads(r["models"]), "variants": json.loads(r["variants"]),
            "skill_revs": json.loads(r["skill_revs"]), "params": json.loads(r["params"]),
            "repeats": r["repeats"], "status": r["status"], "error": r["error"],
            "started_at": r["started_at"], "finished_at": r["finished_at"],
            "results": [dict(model=m, variant=v, **summarise(b))
                        for (m, v), b in sorted(by_mv.items())],
            "per_task": [dict(model=m, variant=v, task_id=t, **summarise(b))
                         for (m, v, t), b in sorted(by_mvt.items())],
        })
        seen_spec.setdefault(r["spec_sha"], r["spec"])

    # ---- per-assertion rows: which check failed is the part no summary can rebuild ------
    grades = [dict(row) for row in c.execute("""
        SELECT g.case_id, c.run_id, g.grader, g.criterion, g.score, g.passed, g.note
        FROM grade g JOIN case_result c ON c.id = g.case_id
        ORDER BY g.case_id, g.id""")]

    n_runs = write_jsonl(OUT / "runs.jsonl", runs)
    n_cases = write_jsonl(OUT / "cases.jsonl", case_rows)
    n_grades = write_jsonl(OUT / "grades.jsonl", grades)
    for sha, spec in sorted(seen_spec.items()):
        # Stored as one line of JSON by db.py. Pretty-print it: a 6 KB single-line file is
        # not an archive anyone can read, and the sha does not depend on these bytes.
        try:
            text = json.dumps(json.loads(spec), ensure_ascii=False, indent=2) + "\n"
        except ValueError:
            text = spec
        (OUT / "specs" / f"{sha}.json").write_text(text, encoding="utf-8", newline="\n")

    kb = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1024
    print(f"exported to {OUT.relative_to(REPO)}: {n_runs} runs, {n_cases} cases, "
          f"{n_grades} grades, {len(seen_spec)} specs, {kb:.0f} KB")


if __name__ == "__main__":
    main()
