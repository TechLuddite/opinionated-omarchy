#!/usr/bin/env python3
"""Turn raw harvest-workflow output into the JSONL corpus.

    python3 tools/ingest.py raw/harvest-result.json

Writes  data/problems.jsonl     one record per line (source of truth)
        data/categories.json     category key -> display label
        raw/harvest-rejected.json  what the audit threw out, and why
        raw/harvest-stats.json     per-category harvest/audit counts

Reports likely cross-category duplicates but does NOT drop them: the same
underlying failure legitimately shows up under two categories with different
framing, and silently collapsing those loses a fix. Review and merge by hand.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["slug", "title", "category", "symptom", "cause", "fix", "verify",
          "applies_to", "severity", "frequency", "danger",
          "audit_status", "audit_confidence", "audit_note", "sources"]

STOP = {"the", "a", "an", "is", "to", "in", "on", "of", "and", "or", "not",
        "with", "after", "when", "my", "it", "but", "for", "at", "from"}


def fingerprint(rec):
    """Content-based key for duplicate detection: the rare words in the symptom."""
    words = re.findall(r"[a-z0-9-]{3,}", (rec.get("symptom") or "").lower())
    return frozenset(w for w in words if w not in STOP)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    problems = payload.get("problems") or []
    if not problems:
        sys.exit("no problems in payload — check the workflow journal before rerunning")

    data = ROOT / "data"
    raw = ROOT / "raw"
    data.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)

    with (data / "problems.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for p in problems:
            fh.write(json.dumps({k: p.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")

    cats = {c["key"]: c["label"] for c in payload.get("categories", [])}
    # Any category that appears on a record but not in the declared list still
    # needs a label, or build_db.py emits a page with a bare key as its title.
    for p in problems:
        cats.setdefault(p.get("category") or "uncategorized", p.get("category") or "uncategorized")
    (data / "categories.json").write_text(
        json.dumps(cats, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")

    (raw / "harvest-rejected.json").write_text(
        json.dumps(payload.get("rejected", []), indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    (raw / "harvest-stats.json").write_text(
        json.dumps(payload.get("stats", []), indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")

    by_cat = Counter(p.get("category") or "uncategorized" for p in problems)
    by_audit = Counter(p.get("audit_status") or "unknown" for p in problems)

    print(f"wrote {len(problems)} records -> data/problems.jsonl")
    for c, n in sorted(by_cat.items()):
        print(f"    {c:<20} {n:>4}")
    print("  audit status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_audit.items())))
    print(f"  rejected by audit: {len(payload.get('rejected', []))}")

    # Duplicate detection: high Jaccard overlap on distinctive symptom words.
    groups = defaultdict(list)
    for p in problems:
        groups[p.get("category")].append(p)
    dupes = []
    seen = [(fingerprint(p), p) for p in problems]
    for i, (fa, pa) in enumerate(seen):
        for fb, pb in seen[i + 1:]:
            if pa.get("category") == pb.get("category") or not fa or not fb:
                continue
            overlap = len(fa & fb) / len(fa | fb)
            if overlap > 0.55:
                dupes.append((round(overlap, 2), pa["slug"], pb["slug"]))
    if dupes:
        print(f"  NOTE: {len(dupes)} likely cross-category duplicate pairs (not removed):")
        for score, a, b in sorted(dupes, reverse=True)[:10]:
            print(f"    {score}  {a}  <->  {b}")


if __name__ == "__main__":
    main()
