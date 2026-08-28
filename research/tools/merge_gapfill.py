#!/usr/bin/env python3
"""Merge a gapfill-workflow result back into the JSONL corpus.

    python tools/merge_gapfill.py raw/gapfill-result.json

Does two things:
  1. Applies the apps-services audit verdicts to records already in the corpus
     (those 26 were harvested but never reviewed).
  2. Appends the newly harvested gap-fill records, with their own audit applied.

Unlike the first harvest, this honours `corrected_cause`: where the auditor
disproved the cause as well as the fix, the cause is replaced rather than left
standing. Records whose cause was NOT corrected keep the audit note so a reader
can still see what was disputed.

Rewrites data/problems.jsonl in place. Re-run tools/build_db.py afterwards.
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSONL = ROOT / "data" / "problems.jsonl"
FIELDS = ["slug", "title", "category", "symptom", "cause", "fix", "verify",
          "applies_to", "severity", "frequency", "danger",
          "audit_status", "audit_confidence", "audit_note", "sources"]


def apply_verdict(rec, v, stats):
    """Return the record with one audit verdict applied, or None to drop it."""
    if v is None:
        # No verdict came back for this slug — keep it, but say so honestly.
        rec["audit_status"] = rec.get("audit_status") or "unaudited"
        rec["audit_confidence"] = rec.get("audit_confidence") or "low"
        stats["no-verdict"] += 1
        return rec
    if v.get("status") == "reject":
        stats["rejected"] += 1
        return None

    rec["audit_confidence"] = v.get("confidence") or "medium"
    rec["audit_note"] = v.get("reason") or None
    if v.get("status") == "corrected":
        if v.get("corrected_fix"):
            rec["fix"] = v["corrected_fix"]
        # The first harvest could not do this, which left disproved causes in
        # place on 130 records. Replace the cause when the auditor supplied one.
        if v.get("corrected_cause"):
            rec["cause"] = v["corrected_cause"]
            stats["cause-corrected"] += 1
        rec["audit_status"] = "corrected"
        stats["corrected"] += 1
    else:
        rec["audit_status"] = "ok"
        stats["ok"] += 1
    return rec


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    results = payload.get("results") or []
    if not results:
        sys.exit("no results in payload — inspect the workflow journal before rerunning")

    existing = [json.loads(l) for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_slug = {r["slug"]: r for r in existing}
    stats = Counter()

    # ── 1. Apply the apps-services audit to records already in the corpus ──
    dropped = set()
    for res in results:
        audit = res.get("audit")
        if not audit:
            continue
        verdicts = {v["slug"]: v for v in audit.get("verdicts", [])}
        cat = res.get("category")
        for rec in existing:
            if rec.get("category") != cat:
                continue
            updated = apply_verdict(rec, verdicts.get(rec["slug"]), stats)
            if updated is None:
                dropped.add(rec["slug"])
    existing = [r for r in existing if r["slug"] not in dropped]

    # ── 2. Append the new gap-fill records, audited ──
    added = []
    for res in results:
        gf = res.get("gapfill")
        if not gf or not gf.get("problems"):
            continue
        cat = res.get("category")
        ga = res.get("gapfillAudit")
        verdicts = {v["slug"]: v for v in (ga or {}).get("verdicts", [])}
        for p in gf["problems"]:
            p["category"] = cat
            if ga is None:
                # Audit agent died; the record is still useful but must not
                # masquerade as reviewed.
                p["audit_status"] = "gapfill-unaudited"
                p["audit_confidence"] = "low"
                stats["gapfill-unaudited"] += 1
            else:
                if apply_verdict(p, verdicts.get(p["slug"]), stats) is None:
                    continue
            # Slug collisions against the existing corpus: suffix rather than
            # drop, so a genuinely distinct problem is never silently lost.
            base = p["slug"]
            n = 2
            while p["slug"] in by_slug:
                p["slug"] = f"{base}-{n}"
                n += 1
            by_slug[p["slug"]] = p
            added.append(p)

    merged = existing + added
    with JSONL.open("w", encoding="utf-8", newline="\n") as fh:
        for r in merged:
            fh.write(json.dumps({k: r.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")

    print(f"corpus: {len(existing) + len(dropped)} -> {len(merged)} records "
          f"(+{len(added)} new, -{len(dropped)} rejected)")
    print("  verdicts applied: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    still = Counter(r.get("audit_status") for r in merged)
    print("  audit status now: " + ", ".join(f"{k}={v}" for k, v in sorted(still.items(), key=lambda x: str(x[0]))))
    print("\nnext: python tools/build_db.py")


if __name__ == "__main__":
    main()
