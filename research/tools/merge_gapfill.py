#!/usr/bin/env python3
"""Merge a gapfill-workflow result back into the JSONL corpus.

    python3 tools/merge_gapfill.py raw/gapfill-result.json

Does two things:
  1. Applies the apps-services audit verdicts to records already in the corpus
     (those 26 were harvested but never reviewed).
  2. Appends the newly harvested gap-fill records, with their own audit applied.

Unlike the first harvest, this honours `corrected_cause`: where the auditor
disproved the cause as well as the fix, the cause is replaced rather than left
standing. Records whose cause was NOT corrected keep the audit note so a reader
can still see what was disputed. `corrected_symptom`, `corrected_danger` and `corrected_verify`
are honoured the same way, as are `corrected_severity` and `corrected_frequency`, and any
`sources` on a verdict are appended to the record while any `sources_remove` are dropped
from it.

Rewrites data/problems.jsonl in place. Re-run tools/build_db.py afterwards.
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from corpus import read_jsonl, write_jsonl

# Closed vocabularies, from research/README.md's record schema. A verdict that corrects
# one of these has to land inside them.
SEVERITIES = ("critical", "high", "medium", "low")
FREQUENCIES = ("very-common", "common", "occasional", "rare")

ROOT = Path(__file__).resolve().parent.parent
JSONL = ROOT / "data" / "problems.jsonl"


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
        # place on 130 records. Replace the cause when the auditor supplied one,
        # and stamp it: the disclaimer in build_db.py and ask.py is conditional on
        # `cause_reconciled`, so an unstamped rewrite makes both tell the reader
        # the cause "was not rewritten" about a cause this pass just replaced.
        if v.get("corrected_cause"):
            rec["cause"] = v["corrected_cause"]
            rec["cause_reconciled"] = date.today().isoformat()
            stats["cause-corrected"] += 1
        # Live exercise on a VM (research/validation/) turned up defects in a
        # symptom and a danger, neither of which the first two verdict shapes
        # could carry, and the boot-kernel re-audit needed verify too. Same rule as fix:
        # replace wholesale, never patch.
        for field in ("symptom", "danger", "verify"):
            if v.get(f"corrected_{field}"):
                rec[field] = v[f"corrected_{field}"]
                stats[f"{field}-corrected"] += 1
        # The 2026-09-11 audit of the issue harvest found this gap the hard way: an
        # auditor judged a severity too low for a defect that silently costs a machine
        # its lock screen, had nowhere to put it, and the change had to be applied by
        # hand after the merge. Both fields are closed vocabularies, so an unknown value
        # is a defect in the verdict rather than something to write into the corpus.
        for field, allowed in (("severity", SEVERITIES), ("frequency", FREQUENCIES)):
            value = v.get(f"corrected_{field}")
            if not value:
                continue
            if value not in allowed:
                sys.exit(f"verdict for {rec['slug']!r} sets {field}={value!r}, "
                         f"which is not one of {sorted(allowed)}")
            rec[field] = value
            stats[f"{field}-corrected"] += 1
        rec["audit_status"] = "corrected"
        stats["corrected"] += 1
    else:
        rec["audit_status"] = "ok"
        stats["ok"] += 1
    # A verdict may cite pages the record did not. Keep them: a corrected fix
    # that rests on a source the record never listed is unverifiable otherwise.
    for url in v.get("sources") or []:
        if url.startswith(("http://", "https://")) and url not in (rec.get("sources") or []):
            rec.setdefault("sources", []).append(url)
    # The other half of that gap, found the same day: an auditor caught a cited GitHub
    # issue number that is really a discussion, so the issue URL only redirects, and
    # could say so only in prose because appending was the sole way to touch sources.
    # Removal runs after the append so a verdict can replace a URL in one verdict.
    for url in v.get("sources_remove") or []:
        if url in (rec.get("sources") or []):
            rec["sources"].remove(url)
            stats["source-removed"] += 1
    if not rec.get("sources"):
        sys.exit(f"verdict for {rec['slug']!r} removed its last source; a record with no "
                 f"source cannot be checked by anyone")
    return rec


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    results = payload.get("results") or []
    if not results:
        sys.exit("no results in payload; inspect the workflow journal before rerunning")

    existing = read_jsonl(JSONL)
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
    write_jsonl(JSONL, merged)

    print(f"corpus: {len(existing) + len(dropped)} -> {len(merged)} records "
          f"(+{len(added)} new, -{len(dropped)} rejected)")
    print("  verdicts applied: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    still = Counter(r.get("audit_status") for r in merged)
    print("  audit status now: " + ", ".join(f"{k}={v}" for k, v in sorted(still.items(), key=lambda x: str(x[0]))))
    print("\nnext: python3 tools/build_db.py")


if __name__ == "__main__":
    main()
