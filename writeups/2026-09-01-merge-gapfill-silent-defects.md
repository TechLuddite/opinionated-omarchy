# Two silent defects in `merge_gapfill.py`

**Date:** 2026-09-01
**Found while:** closing JOURNAL.md "What's left" item 2 — auditing the last 28
`gapfill-unaudited` records.
**Status:** both fixed and verified. Nothing was lost, because neither ever ran.

This is written up separately from [JOURNAL.md](../JOURNAL.md) because the failure mode
generalises: both defects were **silent, and both destroyed evidence of honesty rather
than data**. A corpus whose whole value proposition is "we tell you how much scrutiny each
record survived" has a specific class of bug it cannot afford, and this is that class.

---

## Symptoms as originally observed

**There were none.** That is the point, and the reason this is worth keeping.

`merge_gapfill.py` had been run successfully before — the 2026-08-29 gap-fill pass used it
to merge 143 records. It exits 0, prints a plausible summary, and produces a corpus that
loads, builds, searches and renders correctly. Nothing in `build_db.py`, `ask.py`, the
schema, or the 43-test suite would have flagged either defect.

The only reason they surfaced is that the merge step was **dry-run against a copy of the
corpus before being pointed at the real one**, specifically to check what it did to the
`cause_reconciled` field added the previous session.

## Root cause

### Defect 1 — the writer silently dropped `cause_reconciled`

`merge_gapfill.py` does not write records back as it read them. It projects each one onto
an explicit allowlist:

```python
FIELDS = ["slug", "title", "category", "symptom", "cause", "fix", "verify",
          "applies_to", "severity", "frequency", "danger",
          "audit_status", "audit_confidence", "audit_note", "sources"]
...
fh.write(json.dumps({k: r.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")
```

On 2026-08-30 a new field, `cause_reconciled`, was added to the schema to distinguish
"this record's cause was checked and rewritten to match its audit note" from "this
record's cause was never revisited". 22 records were stamped with it.

`schema.sql`, `build_db.py` and `ask.py` were all updated. **`merge_gapfill.py` was not**,
because it is not part of the build path and nothing exercised it that day.

`{k: r.get(k) for k in FIELDS}` does not fail on an unknown field — it just doesn't copy
it. So the next merge would have written all 456 records back **without the field**, and
`r.get(k)` would have supplied `None` for anything else missing. All 22 stamps gone, with
a summary line reporting success.

**Why an allowlist and not `dict(r)`:** the projection is deliberate and worth keeping —
it guarantees field order and stops a harvester's stray keys entering the corpus. The bug
is not the allowlist; it is that adding a schema field had no single place that forced
every consumer to be updated.

### Defect 2 — it rewrote causes without stamping them

`apply_verdict()` honours an auditor's `corrected_cause`:

```python
if v.get("corrected_cause"):
    rec["cause"] = v["corrected_cause"]
    stats["cause-corrected"] += 1
```

It replaces the cause and never sets `cause_reconciled`. That matters because the
disclaimer printed under an audit note is **conditional on that field** in both renderers
— `build_db.py:221-231` and `ask.py:97-105`:

```python
if r["cause_reconciled"]:
    out.append("> *The Cause above was rewritten on "
               f"{r['cause_reconciled']} to match this note. ...*")
else:
    out.append("> *The Cause above was not rewritten and may still "
               "contain the error described. ...*")
```

So a merge that corrected a cause would then render, under that very record:

> *The Cause above was not rewritten and may still contain the error described.*

A false statement, generated automatically, about a cause the same script had just
replaced. This is the identical failure the 2026-08-30 session fixed at the other end: a
blanket disclaimer that is wrong for part of its audience stops carrying information. Here
it would have been reintroduced by the tooling rather than by a human.

### Why the two compound

Together they are worse than separately. Defect 2 creates records needing the stamp;
defect 1 guarantees the stamp cannot persist. A reader would have seen a corpus asserting
that **no** cause had ever been reconciled — quietly erasing the distinction the field was
added to protect, while looking completely healthy.

## What was changed

All in [`research/tools/merge_gapfill.py`](../research/tools/merge_gapfill.py):

| Line | Change |
| --- | --- |
| `22` | `from datetime import date` |
| `27-30` | `cause_reconciled` added to `FIELDS`, before `sources` |
| `52-58` | `apply_verdict()` stamps `rec["cause_reconciled"] = date.today().isoformat()` whenever it applies a `corrected_cause`, with a comment naming the two renderers that depend on it |

One unrelated fix in the same path,
[`research/tools/gapfill-workflow.js:15`](../research/tools/gapfill-workflow.js): `ROOT`
still pointed at `c:/Projects/Personal/skills/omarchy/research`, left over from before the
repo was converted off Windows. Agents read the corpus off disk by absolute path, so every
gap-fill and audit agent would have failed on the read. This one *would* have failed
loudly — it is listed here only because it sat in the same five lines of the same task.

## How it was verified

Before the real merge, against a `tempfile` copy of `data/problems.jsonl`, with
`merge_gapfill.JSONL` monkeypatched at the module global — the real corpus was never
touched. Synthetic verdicts covered one of each verdict shape: `ok`, `corrected` with
`corrected_fix` only, `corrected` with `corrected_cause`, and `reject`.

```
[PASS] 22 cause_reconciled stamps preserved
[PASS] rejected record dropped from corpus
[PASS] ok verdict -> audit_status ok
[PASS] corrected(fix only) -> no stamp
[PASS] corrected(+cause) -> cause replaced AND stamped   (stamp = 2026-09-01)
[PASS] 33 un-verdicted wayland-compat records unchanged
[PASS] all 22 pre-existing stamps survived
```

Then confirmed on the real run: 29 stamps across two dates (`2026-08-30`: 22,
`2026-09-01`: 7), and the conditional disclaimer rendering the *rewritten* branch exactly
7 times in the generated docs — 4 in `network.md`, 3 in `wayland-compat.md` — matching
`cause-corrected=7`.

### The property that dry run also exposed

Worth stating on its own, because it is not obvious from reading the script and it is the
thing that makes this merge safe:

**Stage 1 iterates every record in an audited category, not only the records you meant to
audit.**

```python
for rec in existing:
    if rec.get("category") != cat:
        continue
    updated = apply_verdict(rec, verdicts.get(rec["slug"]), stats)
```

Records with no verdict fall into the `v is None` branch and keep their existing status, so
this is safe — *provided the verdict set is scoped*. A stray or hallucinated slug from an
auditor would silently overwrite an already-audited record's `audit_status`. In this run,
34 already-audited `network` and `wayland-compat` records sat in that blast radius.

That is why the audit workflow filters each batch's verdicts against the slugs it was
assigned before returning them, and why the dry run asserts the un-verdicted records are
byte-identical afterwards rather than merely present.

## Outstanding / worth knowing next time

- **`merge_gapfill.py` is not covered by any test.** `skillbench/tests/` covers the bench;
  nothing covers the corpus tooling. The dry-run script used here was thrown away — a
  cheap first test would be to keep it, as a fixture-based round-trip asserting that every
  schema field survives a merge.
- **Adding a schema field still has no checklist.** The four consumers are `schema.sql`,
  `build_db.py`, `ask.py` and `merge_gapfill.py`. Three were updated on 2026-08-30 and one
  was missed, with no mechanism to notice. A test that round-trips a record carrying every
  field would have caught it.
- **`ingest.py` was not audited for the same defect.** It is the *replace* path rather than
  the *extend* path and was out of scope here, but it writes the corpus too and deserves
  the same read before it is next run.
- The `gapfill-unaudited` status now applies to **zero** records, but remains reachable:
  `merge_gapfill.py` still assigns it when an audit agent dies. It is documented as such
  rather than removed.
