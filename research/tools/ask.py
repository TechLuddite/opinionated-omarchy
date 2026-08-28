#!/usr/bin/env python3
"""Search the troubleshooting corpus the way a user would describe the problem.

    python3 tools/ask.py "screen share is a black window in zoom"
    python3 tools/ask.py "wifi keeps dropping" --tag laptop --limit 3
    python3 tools/ask.py --tag omarchy --list
    python3 tools/ask.py --slug nvidia-black-screen-after-suspend

This is the point of keeping a database rather than only markdown: symptom text
is matched with FTS5 + bm25 ranking, so a user's own wording finds the record.
"""

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "problems.db"

def _colour_enabled():
    """ANSI only when stdout is a terminal and the user has not opted out.

    Redirecting to a file or piping into a pager should produce clean text. The
    `!!` and `~~` prefixes below carry the same meaning as the colours, so a
    stripped-down render loses emphasis but never a warning.
    """
    if os.environ.get("NO_COLOR"):          # https://no-color.org
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


_C = _colour_enabled()
BOLD = "\033[1m" if _C else ""
CYAN = "\033[36m" if _C else ""
YELLOW = "\033[33m" if _C else ""
RESET = "\033[0m" if _C else ""


# bm25 weights, positional against the FTS column order in schema.sql:
# symptom, title, cause, fix, tags. Symptom dominates because that is what the
# user types; `fix` is damped so a record that merely mentions a term in a long
# command block doesn't outrank one that is actually about the symptom.
WEIGHTS = (10.0, 6.0, 3.0, 0.7, 2.0)


def connect():
    if not DB.exists():
        sys.exit(f"no database at {DB}\nRun: python3 tools/build_db.py")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fts_query(text):
    """Turn free-form user text into a safe FTS5 OR-query.

    Every token is quoted, so FTS5 operators a user might type (NOT, *, ^, ")
    are treated as literal words instead of being parsed as syntax or raising
    a syntax error mid-search.
    """
    tokens = [t for t in re.findall(r"[A-Za-z0-9_./-]+", text) if len(t) > 1]
    if not tokens:
        return None
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def fetch_related(conn, pid):
    tags = [r[0] for r in conn.execute(
        "SELECT tag FROM problem_tags WHERE problem_id = ? ORDER BY tag", (pid,))]
    srcs = [r[0] for r in conn.execute(
        "SELECT url FROM problem_sources WHERE problem_id = ?", (pid,))]
    return tags, srcs


def show(conn, row, verbose):
    tags, srcs = fetch_related(conn, row["id"])
    head = row["title"] or row["slug"]
    bits = [b for b in (row["severity"], row["frequency"], row["category"]) if b]
    print(f"\n{BOLD}{head}{RESET}")
    # The framing this script adds (labels, separators) is plain ASCII so the
    # record's own text is the only thing that varies. Record text is printed
    # verbatim and does contain typography and glyphs; the terminal is UTF-8.
    print(f"  {row['slug']}" + (f"  [{' | '.join(bits)}]" if bits else ""))
    if tags:
        print(f"  applies to: {', '.join(tags)}")
    print(f"\n  SYMPTOM  {row['symptom']}")
    if row["cause"]:
        print(f"  CAUSE    {row['cause']}")
    # The audit rewrote `fix` only, so a corrected record's `cause` may still be
    # wrong in exactly the way the note describes. Show it right beside the cause.
    if row["audit_status"] == "corrected" and row["audit_note"]:
        print(f"  {CYAN}~~ AUDIT  {row['audit_note']}{RESET}")
        print(f"  {CYAN}          (CAUSE above was not rewritten; FIX below is corrected){RESET}")
    if row["danger"]:
        print(f"  {YELLOW}!! RISK  {row['danger']}{RESET}")
    if row["audit_status"] in ("unaudited", "gapfill-unaudited"):
        print(f"  {YELLOW}!! NOT INDEPENDENTLY AUDITED — verify before running{RESET}")
    print("\n  FIX")
    for line in (row["fix"] or "").splitlines():
        print(f"    {line}")
    if verbose:
        if row["verify"]:
            print(f"\n  VERIFY   {row['verify']}")
        for u in srcs:
            print(f"  source:  {u}")
    print("  " + "-" * 68)


def main():
    ap = argparse.ArgumentParser(description="Search the Omarchy/Arch troubleshooting corpus.")
    ap.add_argument("query", nargs="*", help="describe the symptom in plain words")
    ap.add_argument("--tag", action="append", default=[],
                    help="restrict to a tag (repeatable, ANDed): omarchy, nvidia, laptop ...")
    ap.add_argument("--category", help="restrict to one category key")
    ap.add_argument("--slug", help="show one record by exact slug")
    ap.add_argument("--list", action="store_true", help="list matches instead of full records")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("-v", "--verbose", action="store_true", help="include verify steps and sources")
    args = ap.parse_args()

    conn = connect()

    if args.slug:
        row = conn.execute("SELECT * FROM problems WHERE slug = ?", (args.slug,)).fetchone()
        if not row:
            sys.exit(f"no such slug: {args.slug}")
        show(conn, row, True)
        return

    where, params = [], []
    query = " ".join(args.query).strip()

    if query:
        match = fts_query(query)
        if not match:
            sys.exit("query had no searchable terms")
        sql = (f"SELECT p.*, bm25(problems_fts, {','.join(str(w) for w in WEIGHTS)}) AS rank "
               "FROM problems_fts f JOIN problems p ON p.id = f.problem_id "
               "WHERE problems_fts MATCH ?")
        params.append(match)
        order = "ORDER BY rank"          # bm25 returns negative; lower is better
    else:
        sql = "SELECT p.*, 0 AS rank FROM problems p"
        order = ("ORDER BY CASE p.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
                 "WHEN 'medium' THEN 2 ELSE 3 END, p.slug")

    if args.category:
        where.append("p.category = ?")
        params.append(args.category)
    for t in args.tag:
        where.append("EXISTS (SELECT 1 FROM problem_tags t WHERE t.problem_id = p.id AND t.tag = ?)")
        params.append(t.lower())

    if where:
        sql += (" AND " if query else " WHERE ") + " AND ".join(where)
    sql += f" {order} LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("no matches. Try fewer words, or drop --tag/--category.")
        return

    if args.list:
        for r in rows:
            sev = f"[{r['severity']}]" if r["severity"] else ""
            print(f"{r['slug']:<48} {sev:<11} {(r['title'] or r['symptom'])[:60]}")
    else:
        for r in rows:
            show(conn, r, args.verbose)


if __name__ == "__main__":
    main()
