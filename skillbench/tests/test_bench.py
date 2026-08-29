"""Unit tests for the graders, the loader and variant parsing.

The lab bench this descends from had tests only for its UI JavaScript; its own audit
logged "the Python graders/spec parser have no tests" as an open finding. These are the
parts where a silent bug corrupts every number the bench produces, so they get tests here.
"""
import os
import sys

import pytest
import yaml

sys.path.insert(0, "/app")
from app import checks, spec  # noqa: E402


# ----------------------------------------------------------------- graders

def grade(output, *checkspecs):
    return checks.run_checks(output, {"checks": list(checkspecs)})


def test_regex_required_and_forbidden():
    g = grade("run hyprctl monitors",
              {"type": "regex_required", "pattern": "(?i)hyprctl"},
              {"type": "regex_forbidden", "pattern": r"(?i)\bxrandr\s+--"})
    assert [x["passed"] for x in g] == [True, True]


def test_forbidden_pattern_that_matches_fails():
    g = grade("xrandr --output HDMI-1 --auto",
              {"type": "regex_forbidden", "pattern": r"(?i)\bxrandr\s+--"})
    assert g[0]["passed"] is False
    assert "forbidden" in g[0]["note"]


def test_repeated_check_type_gets_a_distinct_criterion():
    """Two regex_required checks must not collapse into one grade row."""
    g = grade("alpha beta",
              {"type": "regex_required", "pattern": "alpha"},
              {"type": "regex_required", "pattern": "beta"})
    assert [x["criterion"] for x in g] == ["regex_required", "regex_required#2"]


def test_a_broken_check_spec_fails_visibly_rather_than_passing():
    g = grade("anything", {"type": "regex_required", "pattern": "([unclosed"})
    assert g[0]["passed"] is False
    assert "bad check config" in g[0]["note"]


def test_unknown_check_type_fails_rather_than_passing():
    assert grade("x", {"type": "no_such_check"})[0]["passed"] is False


def test_empty_output_never_raises():
    g = grade(None, {"type": "regex_required", "pattern": "x"},
              {"type": "json_valid"}, {"type": "max_words", "value": 5})
    assert [x["passed"] for x in g] == [False, False, True]


def test_json_valid_strips_a_fence_by_default():
    assert grade('```json\n{"a": 1}\n```', {"type": "json_valid"})[0]["passed"] is True
    assert grade('```json\n{"a": 1}\n```',
                 {"type": "json_valid", "strict_json": True})[0]["passed"] is False


def test_json_schema_subset():
    out = '{"name": "x", "n": 2}'
    ok = {"type": "json_schema", "schema": {"type": "object", "required": ["name"],
                                            "properties": {"n": {"type": "integer"}}}}
    assert grade(out, ok)[0]["passed"] is True
    bad = {"type": "json_schema", "schema": {"type": "object", "required": ["missing"]}}
    assert grade(out, bad)[0]["passed"] is False


def test_bool_is_not_an_integer():
    assert grade('{"n": true}', {"type": "json_schema",
                 "schema": {"properties": {"n": {"type": "integer"}}}})[0]["passed"] is False


def test_word_and_char_limits():
    assert grade("one two three", {"type": "max_words", "value": 3})[0]["passed"] is True
    assert grade("one two three", {"type": "max_words", "value": 2})[0]["passed"] is False
    assert grade("abc", {"type": "min_chars", "value": 3})[0]["passed"] is True


def test_contains_is_case_insensitive_by_default_and_extract_equals_normalises():
    assert grade("Shell.JSON", {"type": "contains", "value": "shell.json"})[0]["passed"] is True
    assert grade("answer:  HYPRCTL ",
                 {"type": "extract_equals", "pattern": r"answer:\s*(\S+)",
                  "expected": "hyprctl"})[0]["passed"] is True


# ----------------------------------------------------------------- variants

def test_variant_parsing_and_order_significance():
    assert spec.parse_variant("none") == []
    assert spec.parse_variant("skill:omarchy") == ["omarchy"]
    assert spec.parse_variant("skill:a+b") == ["a", "b"]
    assert spec.parse_variant("skill:b+a") == ["b", "a"]      # order is significant


@pytest.mark.parametrize("bad", ["", "omarchy", "skill:", "skill:a+a", "skill:../etc",
                                 "skill:a/b"])
def test_malformed_variants_are_rejected(bad):
    with pytest.raises(spec.SpecError):
        spec.parse_variant(bad)


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b", ".hidden", ""])
def test_bench_and_skill_names_cannot_traverse(bad):
    with pytest.raises(spec.SpecError):
        spec.load_bench(bad)
    with pytest.raises(spec.SpecError):
        spec.load_skill(bad)


# ----------------------------------------------------------------- loading

def test_frontmatter_is_stripped():
    body = spec._strip_frontmatter("---\nname: x\n---\n\n# Heading\ntext\n")
    assert body.startswith("# Heading")
    assert "name: x" not in body
    assert spec._strip_frontmatter("# No frontmatter\n").startswith("# No")


def test_every_shipped_bench_loads_and_its_checks_compile():
    """A bench whose regexes do not compile would score zero forever, silently."""
    benches = spec.list_benches()
    assert len(benches) >= 12
    for b in benches:
        for task in b["tasks"]:
            g = checks.run_checks("probe output", task)
            bad = [x for x in g if x["note"] and "bad check config" in x["note"]]
            assert not bad, f"{b['name']}/{task['id']}: {bad}"


def test_bench_name_must_equal_its_filename(tmp_path):
    p = tmp_path / "mismatch.yaml"
    p.write_text(yaml.safe_dump({"name": "other", "tasks": [{"id": "t", "prompt": "p"}]}),
                 encoding="utf-8")
    old = spec.BENCH_DIR
    spec.BENCH_DIR = str(tmp_path)
    try:
        with pytest.raises(spec.SpecError):
            spec.load_bench("mismatch")
    finally:
        spec.BENCH_DIR = old


def test_skill_bundles_concatenate_in_manifest_order():
    body_only, sha_only, files_only = spec.load_skill("omarchy")
    full, sha_full, files_full = spec.load_skill("omarchy-full")
    assert files_only == ["SKILL.md"]
    assert len(files_full) == 7
    assert full.startswith(body_only[:200])      # SKILL.md leads the bundle
    assert len(full) > len(body_only)
    assert sha_only != sha_full                  # and they are tracked as different content


def test_control_benches_are_flagged():
    controls = {b["name"] for b in spec.list_benches() if b.get("control")}
    assert controls == {"linux-disk-full", "linux-runaway-process",
                        "linux-boot-partition-full", "linux-pacman-keyring"}
