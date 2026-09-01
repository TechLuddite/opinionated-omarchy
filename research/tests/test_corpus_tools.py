#!/usr/bin/env python3
"""Tests for the corpus writers -- the paths that can destroy provenance silently.

Why these exist. On 2026-08-30 `cause_reconciled` was added to the record schema and
to three of its four consumers. The fourth, `ingest.py`, kept a private `FIELDS`
allowlist that never learned about it, so the REPLACE path would have projected the
field away with no error and no warning. Nothing in the repo could have caught that:
`skillbench/tests/` covers the bench, and the corpus tooling had no tests at all.

The class of bug is what these tests target, not the one instance. A writer that
projects records onto a list which must be kept in sync by hand will drift again, so
the assertions are about the INVARIANT -- FIELDS agrees with schema.sql, FIELDS
agrees with the corpus on disk, and a record carrying every field survives a
round-trip through both writers unchanged.

Stdlib `unittest`, deliberately: CLAUDE.md keeps the corpus tooling dependency-free
so it runs on a bare container, and a test suite that needed pytest installed would
be the first thing to break that.

    python3 -m unittest discover -s tests -v      (from research/)
"""

import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import corpus            # noqa: E402
import ingest            # noqa: E402
import merge_gapfill     # noqa: E402


def a_full_record(slug="fixture-every-field"):
    """A record carrying every field in the schema, each with a distinctive value.

    Distinctive matters: a field that survives as None looks identical to a field
    that was dropped and re-added as None by the projection, so every value here is
    something that can only be present if it was actually carried through.
    """
    return {
        "slug": slug,
        "title": "Fixture: every field populated",
        "category": "omarchy-core",
        "symptom": "FIXTURE_SYMPTOM the screen shows → an arrow and  a glyph",
        "cause": "FIXTURE_CAUSE",
        "fix": "FIXTURE_FIX\n\n```sh\nomarchy update\n```",
        "verify": "FIXTURE_VERIFY",
        "applies_to": ["omarchy", "arch", "fixture-tag"],
        "severity": "high",
        "frequency": "common",
        "danger": "FIXTURE_DANGER can break boot",
        "audit_status": "corrected",
        "audit_confidence": "high",
        "audit_note": "FIXTURE_NOTE",
        "cause_reconciled": "2026-08-30",
        "sources": ["https://example.invalid/fixture"],
    }


# ------------------------------------------------------- the schema invariants

class TestFieldsAgreesWithItsConsumers(unittest.TestCase):
    """FIELDS is one of four consumers of the record schema. Pin it to the others."""

    def test_fields_covers_every_column_in_schema_sql(self):
        """A column added to schema.sql but not to FIELDS is dropped on write.

        This is the assertion that would have failed on 2026-08-30, when
        `cause_reconciled` reached schema.sql and ingest.py's list never heard of it.
        """
        sql = (ROOT / "tools" / "schema.sql").read_text(encoding="utf-8")
        body = re.search(r"CREATE TABLE problems \((.*?)\n\);", sql, re.S).group(1)
        columns = set()
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            m = re.match(r"([a-z_]+)\s+(TEXT|INTEGER)", line)
            if m:
                columns.add(m.group(1))
        columns.discard("id")  # synthetic primary key, not a record field
        missing = columns - set(corpus.FIELDS)
        self.assertEqual(missing, set(),
                         f"schema.sql has columns corpus.FIELDS does not name: {sorted(missing)}")

    def test_fields_covers_every_key_in_the_live_corpus(self):
        """Drift in the other direction: a key on disk that the next write would drop."""
        records = corpus.read_jsonl(ROOT / "data" / "problems.jsonl")
        self.assertTrue(records, "corpus is empty -- the test is not testing anything")
        seen = {k for r in records for k in r}
        missing = seen - set(corpus.FIELDS)
        self.assertEqual(missing, set(),
                         f"records on disk carry keys corpus.FIELDS does not name: {sorted(missing)}")

    def test_field_order_matches_the_corpus_on_disk(self):
        """Reordering FIELDS rewrites all 456 lines and hides the real diff."""
        first = next(iter(corpus.read_jsonl(ROOT / "data" / "problems.jsonl")))
        self.assertEqual(list(first.keys()), corpus.FIELDS)

    def test_neither_writer_keeps_a_private_field_list(self):
        """Two copies of this list is the original defect. There must be one."""
        for mod in (ingest, merge_gapfill):
            self.assertFalse(
                "FIELDS" in vars(mod) and vars(mod)["FIELDS"] is not corpus.FIELDS,
                f"{mod.__name__} defines its own FIELDS again -- import corpus.FIELDS",
            )


# ------------------------------------------------------------- the round trips

class TestEveryFieldSurvivesAWrite(unittest.TestCase):

    def test_write_then_read_preserves_every_field(self):
        rec = a_full_record()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "problems.jsonl"
            corpus.write_jsonl(path, [rec])
            back = corpus.read_jsonl(path)
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0], rec)

    def test_written_bytes_are_lf_and_utf8(self):
        """CLAUDE.md calls both load-bearing: docs/ is tracked and fully regenerated."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "problems.jsonl"
            corpus.write_jsonl(path, [a_full_record()])
            raw = path.read_bytes()
        self.assertNotIn(b"\r\n", raw)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertIn("→".encode("utf-8"), raw)   # arrow survived as UTF-8
        self.assertIn("".encode("utf-8"), raw)   # Nerd Font glyph survived

    def test_workflow_only_keys_are_dropped_without_complaint(self):
        """The projection's real job: auditor working notes stay in raw/, not the corpus."""
        rec = a_full_record()
        rec["cause_note"] = "auditor scratch"
        rec["verify_note"] = "auditor scratch"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "problems.jsonl"
            corpus.write_jsonl(path, [rec])
            back = corpus.read_jsonl(path)[0]
        self.assertNotIn("cause_note", back)
        self.assertEqual(back["cause_reconciled"], "2026-08-30")

    def test_an_unclassified_key_raises_instead_of_vanishing(self):
        """The whole point: a field nobody classified must not disappear quietly."""
        rec = a_full_record()
        rec["some_new_provenance_field"] = "2026-09-02"
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError) as cm:
                corpus.write_jsonl(Path(td) / "problems.jsonl", [rec])
        self.assertIn("some_new_provenance_field", str(cm.exception))


class TestIngestReplacePath(unittest.TestCase):
    """ingest.py REPLACES the corpus. This is the path that carried the live defect."""

    def _run(self, problems, td):
        payload = {"problems": problems,
                   "categories": [{"key": "omarchy-core", "label": "Omarchy Core"}],
                   "rejected": [], "stats": []}
        pay = Path(td) / "payload.json"
        pay.write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch.object(ingest, "ROOT", Path(td)), \
             mock.patch.object(sys, "argv", ["ingest.py", str(pay)]), \
             mock.patch("sys.stdout"):
            ingest.main()
        return corpus.read_jsonl(Path(td) / "data" / "problems.jsonl")

    def test_cause_reconciled_survives_an_ingest(self):
        """The regression test. Fails against the pre-2026-09-02 FIELDS list."""
        with tempfile.TemporaryDirectory() as td:
            back = self._run([a_full_record()], td)
        self.assertEqual(back[0]["cause_reconciled"], "2026-08-30")

    def test_every_field_survives_an_ingest(self):
        rec = a_full_record()
        with tempfile.TemporaryDirectory() as td:
            back = self._run([dict(rec)], td)
        self.assertEqual(back[0], rec)


class TestMergeExtendPath(unittest.TestCase):
    """merge_gapfill.py EXTENDS the corpus in place, and applies audit verdicts."""

    def _run(self, existing, payload, td):
        jsonl = Path(td) / "problems.jsonl"
        corpus.write_jsonl(jsonl, existing)
        pay = Path(td) / "payload.json"
        pay.write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch.object(merge_gapfill, "JSONL", jsonl), \
             mock.patch.object(sys, "argv", ["merge_gapfill.py", str(pay)]), \
             mock.patch("sys.stdout"):
            merge_gapfill.main()
        return {r["slug"]: r for r in corpus.read_jsonl(jsonl)}

    def test_an_untouched_record_keeps_every_field_through_a_merge(self):
        """A record in a category the merge does not audit must come out byte-identical."""
        keep = a_full_record("untouched-record")
        keep["category"] = "pacman-aur"
        payload = {"results": [{"category": "omarchy-core",
                                "gapfill": {"problems": [a_full_record("brand-new")]},
                                "gapfillAudit": {"verdicts": [
                                    {"slug": "brand-new", "status": "ok", "confidence": "high"}]}}]}
        with tempfile.TemporaryDirectory() as td:
            back = self._run([keep], payload, td)
        self.assertEqual(back["untouched-record"], keep)

    def test_a_corrected_cause_is_stamped_with_cause_reconciled(self):
        """The second silent defect from the writeup: rewriting a cause unstamped makes
        the disclaimer in ask.py and the docs tell the reader it was never rewritten."""
        rec = a_full_record("gets-corrected")
        del rec["cause_reconciled"]
        rec["audit_status"] = "unaudited"
        payload = {"results": [{"category": "omarchy-core",
                                "audit": {"verdicts": [
                                    {"slug": "gets-corrected", "status": "corrected",
                                     "confidence": "high", "reason": "cause was wrong",
                                     "corrected_cause": "THE REAL CAUSE"}]}}]}
        with tempfile.TemporaryDirectory() as td:
            back = self._run([rec], payload, td)
        got = back["gets-corrected"]
        self.assertEqual(got["cause"], "THE REAL CAUSE")
        self.assertEqual(got["cause_reconciled"], date.today().isoformat())

    def test_a_corrected_fix_alone_does_not_stamp_the_cause(self):
        """The stamp must mean 'cause reconciled', not 'record touched' -- otherwise it
        stops distinguishing checked-and-correct from never-revisited."""
        rec = a_full_record("fix-only")
        del rec["cause_reconciled"]
        payload = {"results": [{"category": "omarchy-core",
                                "audit": {"verdicts": [
                                    {"slug": "fix-only", "status": "corrected",
                                     "confidence": "high", "reason": "fix was wrong",
                                     "corrected_fix": "THE REAL FIX"}]}}]}
        with tempfile.TemporaryDirectory() as td:
            back = self._run([rec], payload, td)
        got = back["fix-only"]
        self.assertEqual(got["fix"], "THE REAL FIX")
        self.assertEqual(got["cause"], "FIXTURE_CAUSE")
        self.assertIsNone(got["cause_reconciled"])


if __name__ == "__main__":
    unittest.main()
