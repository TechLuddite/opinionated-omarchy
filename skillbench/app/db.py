"""SQLite storage. Schema applied idempotently at startup.

nexus1 put this in a shared Postgres because it lived alongside a dozen other stacks.
Here the bench is self-contained and single-writer, so SQLite is the honest choice: no
second container, no password, one file you can copy or delete.

Shape is unchanged from the original so results stay comparable:
    bench -> bench_run -> case_result -> grade

Raw output is kept on every case, which is what makes REGRADE free: re-running checks
after fixing a bad pattern costs zero model calls.
"""
import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get("SB_DB", "/data/skillbench.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bench (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  description TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS bench_run (
  id          INTEGER PRIMARY KEY,
  bench_id    INTEGER NOT NULL REFERENCES bench(id),
  spec        TEXT NOT NULL,
  spec_sha    TEXT NOT NULL,
  models      TEXT NOT NULL,
  variants    TEXT NOT NULL,
  skill_revs  TEXT NOT NULL DEFAULT '{}',
  params      TEXT NOT NULL DEFAULT '{}',
  repeats     INTEGER NOT NULL DEFAULT 1,
  status      TEXT NOT NULL DEFAULT 'running',
  error       TEXT,
  started_at  TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS case_result (
  id                INTEGER PRIMARY KEY,
  run_id            INTEGER NOT NULL REFERENCES bench_run(id) ON DELETE CASCADE,
  task_id           TEXT NOT NULL,
  model             TEXT NOT NULL,
  variant           TEXT NOT NULL,
  repeat_idx        INTEGER NOT NULL DEFAULT 0,
  status            TEXT NOT NULL,
  request           TEXT NOT NULL,
  output            TEXT,
  error             TEXT,
  prompt_tokens     INTEGER,
  completion_tokens INTEGER,
  latency_s         REAL,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (run_id, task_id, model, variant, repeat_idx)
);
CREATE INDEX IF NOT EXISTS case_result_run_idx ON case_result(run_id);
CREATE TABLE IF NOT EXISTS grade (
  id        INTEGER PRIMARY KEY,
  case_id   INTEGER NOT NULL REFERENCES case_result(id) ON DELETE CASCADE,
  grader    TEXT NOT NULL DEFAULT 'check',
  criterion TEXT NOT NULL,
  score     REAL NOT NULL,
  passed    INTEGER NOT NULL,
  note      TEXT
);
CREATE INDEX IF NOT EXISTS grade_case_idx ON grade(case_id);
"""

_local = threading.local()


def conn():
    c = getattr(_local, "conn", None)
    if c is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        _local.conn = c
    return c


def init():
    c = conn()
    c.executescript(SCHEMA)
    c.commit()
    return reconcile_orphans()


def reconcile_orphans():
    """Mark runs that a restart abandoned.

    The runner holds its tasks in memory, so a container restart mid-run leaves rows
    behind with no task to finish them. The nexus1 audit flagged exactly this as an
    open finding; it costs four lines to close, and the partial matrix stays valid --
    Resume fills only the missing cells.
    """
    c = conn()
    cur = c.execute(
        "UPDATE bench_run SET status='aborted', finished_at=datetime('now'),"
        " error='orphaned by a restart - resume to continue' WHERE status='running'")
    c.commit()
    return cur.rowcount


def bench_id(name, description=None):
    c = conn()
    row = c.execute("SELECT id FROM bench WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = c.execute("INSERT INTO bench (name, description) VALUES (?,?)", (name, description))
    c.commit()
    return cur.lastrowid


def create_run(bench, spec, models, variants, repeats, params, skill_revs):
    c = conn()
    cur = c.execute(
        "INSERT INTO bench_run (bench_id, spec, spec_sha, models, variants, skill_revs,"
        " params, repeats) VALUES (?,?,?,?,?,?,?,?)",
        (bench_id(bench["name"], bench.get("description")), json.dumps(spec), spec["spec_sha"],
         json.dumps(models), json.dumps(variants), json.dumps(skill_revs),
         json.dumps(params), repeats))
    c.commit()
    return cur.lastrowid


def finish_run(run_id, status, error=None):
    c = conn()
    c.execute("UPDATE bench_run SET status=?, error=?, finished_at=datetime('now') WHERE id=?",
              (status, error, run_id))
    c.commit()


def record_case(run_id, task_id, model, variant, repeat_idx, status, request,
                output=None, error=None, prompt_tokens=None, completion_tokens=None,
                latency_s=None):
    c = conn()
    cur = c.execute(
        "INSERT OR IGNORE INTO case_result (run_id, task_id, model, variant, repeat_idx,"
        " status, request, output, error, prompt_tokens, completion_tokens, latency_s)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, task_id, model, variant, repeat_idx, status, json.dumps(request),
         output, error, prompt_tokens, completion_tokens, latency_s))
    c.commit()
    return cur.lastrowid


def record_grades(case_id, grades):
    c = conn()
    c.execute("DELETE FROM grade WHERE case_id=?", (case_id,))
    c.executemany(
        "INSERT INTO grade (case_id, grader, criterion, score, passed, note)"
        " VALUES (?,'check',?,?,?,?)",
        [(case_id, g["criterion"], g["score"], 1 if g["passed"] else 0, g["note"]) for g in grades])
    c.commit()


def existing_cells(run_id):
    return {(r["task_id"], r["model"], r["variant"], r["repeat_idx"])
            for r in conn().execute(
                "SELECT task_id, model, variant, repeat_idx FROM case_result WHERE run_id=?",
                (run_id,))}
