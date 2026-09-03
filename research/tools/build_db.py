#!/usr/bin/env python3
"""Build the searchable troubleshooting DB from the JSONL corpus.

    python3 tools/build_db.py

Reads   data/problems.jsonl   (source of truth, git-diffable)
Writes  data/problems.db      (derived FTS5 index; safe to delete and rebuild)
        docs/<category>.md    (derived human/agent-readable pages)

The DB and the markdown are both disposable. Edit the JSONL, re-run this.
"""

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSONL = ROOT / "data" / "problems.jsonl"
DB = ROOT / "data" / "problems.db"
SCHEMA = ROOT / "tools" / "schema.sql"
DOCS = ROOT / "docs"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
FREQUENCY_ORDER = {"very-common": 0, "common": 1, "occasional": 2, "rare": 3}

# Constrained columns: anything outside the CHECK sets becomes NULL rather than
# aborting the whole build, so one malformed harvested record can't cost us the
# other few hundred. Coercions are counted and reported at the end.
VALID = {
    "severity": set(SEVERITY_ORDER),
    "frequency": set(FREQUENCY_ORDER),
    "audit_status": {"ok", "corrected", "unaudited", "gapfill-unaudited"},
    "audit_confidence": {"high", "medium", "low"},
}


def load(path):
    """Read JSONL, skipping blank lines. Returns (records, parse_errors)."""
    records, errors = [], []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"line {n}: {exc}")
    return records, errors


def norm(rec, coercions):
    """Coerce one raw record into the column set, tracking dropped values."""
    out = {}
    for col, valid in VALID.items():
        raw = (rec.get(col) or "").strip().lower()
        if raw and raw not in valid:
            coercions[f"{col}={raw!r}"] += 1
            raw = ""
        out[col] = raw or None

    tags = rec.get("applies_to") or []
    if isinstance(tags, str):
        tags = [tags]
    # Tags come from a dozen independent agents, so normalise aggressively:
    # lowercase, collapse whitespace/underscores to hyphens, dedupe.
    clean_tags = []
    for t in tags:
        t = re.sub(r"[\s_]+", "-", str(t).strip().lower()).strip("-")
        if t and t not in clean_tags:
            clean_tags.append(t)

    sources = rec.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    clean_sources, seen_src = [], set()
    for s in sources:
        s = str(s).strip()
        # Drop anything that isn't a real fetchable URL — agents occasionally
        # emit a bare page title or "ArchWiki" where a citation belongs.
        if s.startswith(("http://", "https://")) and s not in seen_src:
            seen_src.add(s)
            clean_sources.append(s)

    out.update(
        slug=str(rec.get("slug") or "").strip(),
        title=(rec.get("title") or "").strip() or None,
        category=(rec.get("category") or "").strip() or None,
        symptom=(rec.get("symptom") or "").strip(),
        cause=(rec.get("cause") or "").strip() or None,
        fix=(rec.get("fix") or "").strip(),
        verify=(rec.get("verify") or "").strip() or None,
        danger=(rec.get("danger") or "").strip() or None,
        audit_note=(rec.get("audit_note") or "").strip() or None,
        cause_reconciled=(rec.get("cause_reconciled") or "").strip() or None,
        tags=clean_tags,
        sources=clean_sources,
    )
    return out


def build(records, categories):
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()  # full rebuild; the DB is derived, never authoritative
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    conn.executemany(
        "INSERT OR REPLACE INTO categories (key, label) VALUES (?, ?)",
        sorted(categories.items()),
    )

    skipped, coercions = [], Counter()
    pid = 0
    for rec in records:
        r = norm(rec, coercions)
        # A record with no symptom or no fix is not actionable — it would be
        # noise in every search result, so refuse it loudly instead of storing it.
        if not r["slug"] or not r["symptom"] or not r["fix"]:
            skipped.append(r.get("slug") or "<no slug>")
            continue
        pid += 1
        conn.execute(
            """INSERT INTO problems
               (id, slug, title, category, symptom, cause, fix, verify,
                severity, frequency, danger, audit_status, audit_confidence, audit_note,
                cause_reconciled)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, r["slug"], r["title"], r["category"], r["symptom"], r["cause"],
             r["fix"], r["verify"], r["severity"], r["frequency"], r["danger"],
             r["audit_status"], r["audit_confidence"], r["audit_note"],
             r["cause_reconciled"]),
        )
        conn.executemany(
            "INSERT OR IGNORE INTO problem_tags (problem_id, tag) VALUES (?, ?)",
            [(pid, t) for t in r["tags"]],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO problem_sources (problem_id, url) VALUES (?, ?)",
            [(pid, u) for u in r["sources"]],
        )
        conn.execute(
            """INSERT INTO problems_fts (symptom, title, cause, fix, tags, problem_id)
               VALUES (?,?,?,?,?,?)""",
            (r["symptom"], r["title"] or "", r["cause"] or "", r["fix"],
             " ".join(r["tags"]), pid),
        )

    conn.commit()
    conn.execute("INSERT INTO problems_fts(problems_fts) VALUES('optimize')")
    conn.commit()
    return conn, skipped, coercions


def sort_key(row):
    return (SEVERITY_ORDER.get(row["severity"], 9),
            FREQUENCY_ORDER.get(row["frequency"], 9),
            row["slug"])


def write_docs(conn, categories):
    """Emit one markdown page per category, plus an index.

    These are what an agent or a human actually reads; the DB is for search.
    """
    DOCS.mkdir(parents=True, exist_ok=True)
    for old in DOCS.glob("*.md"):
        old.unlink()

    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM problems")]
    tags = defaultdict(list)
    for pid, tag in conn.execute("SELECT problem_id, tag FROM problem_tags ORDER BY tag"):
        tags[pid].append(tag)
    srcs = defaultdict(list)
    for pid, url in conn.execute("SELECT problem_id, url FROM problem_sources"):
        srcs[pid].append(url)

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"] or "uncategorized"].append(r)

    index = ["# Omarchy / Arch troubleshooting corpus", "",
             f"{len(rows)} problems across {len(by_cat)} categories. "
             "Generated by `tools/build_db.py`. Do not edit these files by hand.", ""]

    for cat in sorted(by_cat):
        entries = sorted(by_cat[cat], key=sort_key)
        label = categories.get(cat, cat)
        index.append(f"- [{label}]({cat}.md): {len(entries)} problems")

        out = [f"# {label}", "",
               f"{len(entries)} problems. Sorted by severity, then by how often users hit it.", ""]
        for r in entries:
            out.append(f"## {r['title'] or r['slug']}")
            out.append("")
            meta = [f"`{r['slug']}`"]
            if r["severity"]:
                meta.append(f"severity: **{r['severity']}**")
            if r["frequency"]:
                meta.append(f"frequency: **{r['frequency']}**")
            if tags[r["id"]]:
                meta.append("applies to: " + ", ".join(f"`{t}`" for t in tags[r["id"]]))
            out.append(" · ".join(meta))
            out.append("")
            out.append(f"**Symptom.** {r['symptom']}")
            out.append("")
            if r["cause"]:
                out.append(f"**Cause.** {r['cause']}")
                out.append("")
            # Put the note above the fix, so the reader sees the dispute before
            # trusting the cause. Which disclaimer follows it is load-bearing: the
            # first harvest's auditors could rewrite only `fix`, so those records
            # can still carry a cause the note disproves. `cause_reconciled` marks
            # the ones whose cause has since been brought into line with the note.
            if r["audit_status"] == "corrected" and r["audit_note"]:
                out.append(f"> **Audit corrected this record.** {r['audit_note']}")
                out.append(">")
                if r["cause_reconciled"]:
                    out.append("> *The Cause above was rewritten on "
                               f"{r['cause_reconciled']} to match this note. The Fix "
                               "was corrected by the audit itself.*")
                else:
                    out.append("> *The Cause above was not rewritten and may still "
                               "contain the error described. The Fix below is the "
                               "corrected version.*")
                out.append("")
            if r["danger"]:
                out.append(f"> ⚠️ **Risk.** {r['danger']}")
                out.append("")
            out.append("**Fix.**")
            out.append("")
            out.append(r["fix"])
            out.append("")
            if r["verify"]:
                out.append(f"**Verify.** {r['verify']}")
                out.append("")
            if r["audit_status"] in ("unaudited", "gapfill-unaudited"):
                out.append("> *Not independently audited: verify before running.*")
                out.append("")
            if srcs[r["id"]]:
                out.append("Sources: " + " · ".join(f"<{u}>" for u in srcs[r["id"]]))
                out.append("")
            out.append("---")
            out.append("")
        (DOCS / f"{cat}.md").write_text("\n".join(out), encoding="utf-8", newline="\n")

    (DOCS / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")
    return by_cat


def main():
    if not JSONL.exists():
        sys.exit(f"missing corpus: {JSONL}\nRun the harvest workflow first.")

    records, parse_errors = load(JSONL)
    cat_path = ROOT / "data" / "categories.json"
    categories = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else {}

    conn, skipped, coercions = build(records, categories)
    by_cat = write_docs(conn, categories)

    n = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    n_tags = conn.execute("SELECT COUNT(DISTINCT tag) FROM problem_tags").fetchone()[0]
    n_src = conn.execute("SELECT COUNT(DISTINCT url) FROM problem_sources").fetchone()[0]
    no_src = conn.execute(
        "SELECT COUNT(*) FROM problems p "
        "WHERE NOT EXISTS (SELECT 1 FROM problem_sources s WHERE s.problem_id = p.id)"
    ).fetchone()[0]

    print(f"built {DB.relative_to(ROOT)}")
    # This summary is plain ASCII so it stays legible in a bare console or a
    # CI log. The generated markdown is written UTF-8 and keeps its typography.
    print(f"  {n} problems | {n_tags} distinct tags | {n_src} distinct sources")
    for cat in sorted(by_cat):
        print(f"    {cat:<20} {len(by_cat[cat]):>4}")
    if no_src:
        print(f"  WARNING: {no_src} problems have no usable source URL")
    if skipped:
        print(f"  WARNING: skipped {len(skipped)} records missing slug/symptom/fix: "
              + ", ".join(skipped[:8]) + (" ..." if len(skipped) > 8 else ""))
    if coercions:
        print("  NOTE: nulled out-of-range values: "
              + ", ".join(f"{k} x{v}" for k, v in coercions.most_common(8)))
    if parse_errors:
        print(f"  WARNING: {len(parse_errors)} unparseable JSONL lines: {parse_errors[:3]}")
    conn.close()


if __name__ == "__main__":
    main()
