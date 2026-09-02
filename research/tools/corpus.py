#!/usr/bin/env python3
"""The record schema, and the only two functions that may read or write the corpus.

This module exists because of a real defect. `cause_reconciled` was added to the
schema on 2026-08-30 and to three of its four consumers; `ingest.py` was missed.
Both writers projected records onto a private `FIELDS` allowlist, so a field absent
from that list is dropped **silently** -- no error, no warning, just a column of
provenance gone from the JSONL. Two copies of a list that must never diverge is the
bug; one copy, imported, is the fix.

See writeups/2026-09-01-merge-gapfill-silent-defects.md.

Two conventions from CLAUDE.md are enforced here rather than at each call site,
because both are load-bearing and both are easy to omit:

  * **LF, explicitly.** `research/docs/` is tracked and fully regenerated on every
    build, so a writer that emits native line endings turns a rebuild into a
    ~1.5 MB whitespace-only diff.
  * **UTF-8, explicitly.** The corpus carries typography, box drawing, arrows and a
    Nerd Font glyph. A build that depends on the ambient `LANG` is reproducible
    only by accident.
"""

import json

# The canonical record schema, in the order records are written.
#
# ORDER IS LOAD-BEARING: it is the key order of every one of the 456 records in
# data/problems.jsonl. Reordering this list rewrites all 456 lines, turning the
# next merge into a whole-corpus diff that hides the records actually touched.
# Append new fields; do not reorder existing ones.
#
# Adding a field here is necessary but NOT sufficient -- it has four consumers:
# schema.sql, build_db.py, ask.py, and this list. tests/test_corpus_tools.py
# asserts this list against schema.sql and against the live corpus, so a field
# added to one and forgotten in the other fails loudly instead of vanishing.
FIELDS = ["slug", "title", "category", "symptom", "cause", "fix", "verify",
          "applies_to", "severity", "frequency", "danger",
          "audit_status", "audit_confidence", "audit_note", "cause_reconciled",
          "sources"]


# Keys the harvest and gap-fill workflows put on records that are deliberately NOT
# corpus fields: an auditor's working notes, kept in raw/ for provenance and dropped
# on the way in. Enumerated from the raw payloads rather than guessed, so that a key
# appearing here is a decision someone made and not an oversight.
WORKFLOW_ONLY = {"cause_note", "cause_extra", "verify_note"}


def read_jsonl(path):
    """Read the corpus. Blank lines are skipped; nothing else is tolerated."""
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path, records):
    """Write the corpus, projecting every record onto FIELDS.

    The projection makes every record's shape uniform, and dropping the workflow
    chaff in WORKFLOW_ONLY is the point of it. What is NOT acceptable is dropping
    a field nobody has classified either way -- that is what happened to
    `cause_reconciled`, and it happened silently. So an unrecognised key is an
    unfinished schema change and raises here, rather than disappearing.
    """
    accounted = set(FIELDS) | WORKFLOW_ONLY
    for rec in records:
        unknown = set(rec) - accounted
        if unknown:
            raise ValueError(
                f"record {rec.get('slug')!r} carries unrecognised {sorted(unknown)}.\n"
                f"Either it is a corpus field -- add it to corpus.FIELDS *and* to "
                f"schema.sql, build_db.py and ask.py --\nor it is workflow output the "
                f"corpus does not keep, in which case add it to corpus.WORKFLOW_ONLY."
            )
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps({k: rec.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")
