"""Deterministic graders.

Each check on a task yields one grade row (grader='check', score 0/1). These never
raise on model output: a broken output is a failed check, not a crashed run. A broken
CHECK SPEC also yields a failed grade, with the config error in the note, so a typo in
a bench is visible in the UI instead of silently passing everything.

JSON checks strip a ```json fence first (models love fences); `strict_json: true` on a
check disables that. `json_schema` supports a pragmatic subset (type, properties,
required, items, enum, nested), not full JSON Schema.

Ported from the nexus1 lab's Skill Bench (FR-011) with the semantics unchanged, so
results here stay comparable with the baseline in research/bench/.
"""
import json
import re


def _strip_fences(text):
    m = re.search(r"```(?:json|JSON)?\s*\n(.*?)```", text, re.S)
    return m.group(1).strip() if m else text.strip()


def _json_of(text, check):
    raw = text.strip() if check.get("strict_json") else _strip_fences(text)
    return json.loads(raw)


def _norm(s, normalize=True):
    s = str(s)
    return re.sub(r"\s+", " ", s).strip().lower() if normalize else s


def _schema_errors(value, schema, path="$"):
    """Minimal JSON-schema subset validator; returns a list of error strings."""
    errs = []
    typ = schema.get("type")
    TYPES = {"object": dict, "array": list, "string": str, "number": (int, float),
             "integer": int, "boolean": bool, "null": type(None)}

    def _is(t):
        py = TYPES.get(t)
        if py is None:
            return True
        if t in ("number", "integer") and isinstance(value, bool):
            return False
        return isinstance(value, py)

    if typ:
        allowed = typ if isinstance(typ, list) else [typ]
        if not any(_is(t) for t in allowed):
            return [f"{path}: expected {'|'.join(map(str, allowed))}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in enum")
    if isinstance(value, dict):
        for k in schema.get("required") or []:
            if k not in value:
                errs.append(f"{path}.{k}: required key missing")
        for k, sub in (schema.get("properties") or {}).items():
            if k in value:
                errs.extend(_schema_errors(value[k], sub, f"{path}.{k}"))
    if isinstance(value, list) and schema.get("items"):
        for i, v in enumerate(value):
            errs.extend(_schema_errors(v, schema["items"], f"{path}[{i}]"))
    return errs


def _check_one(output, check):
    """-> (passed: bool, note: str|None)"""
    t = check["type"]
    if t == "json_valid":
        try:
            _json_of(output, check)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"invalid JSON: {e}"
    if t == "json_schema":
        try:
            val = _json_of(output, check)
        except json.JSONDecodeError as e:
            return False, f"invalid JSON: {e}"
        errs = _schema_errors(val, check.get("schema") or {})
        return (False, "; ".join(errs[:4])) if errs else (True, None)
    if t in ("regex_required", "regex_forbidden"):
        flags = re.S | (0 if check.get("case_sensitive", True) else re.I)
        hit = re.search(check.get("pattern", ""), output, flags)
        if t == "regex_required":
            return (True, None) if hit else (False, f"pattern not found: {check.get('pattern')!r}")
        return (False, f"forbidden pattern matched: {hit.group(0)[:80]!r}") if hit else (True, None)
    if t in ("contains", "not_contains"):
        hay, needle = output, str(check.get("value", ""))
        if not check.get("case_sensitive", False):
            hay, needle = hay.lower(), needle.lower()
        found = needle in hay
        if t == "contains":
            return (True, None) if found else (False, f"missing: {check.get('value')!r}")
        return (False, f"present: {check.get('value')!r}") if found else (True, None)
    if t == "extract_equals":
        m = re.search(check.get("pattern", ""), output, re.S)
        if not m:
            return False, f"extract pattern not found: {check.get('pattern')!r}"
        got = m.group(1) if m.groups() else m.group(0)
        norm = check.get("normalize", True)
        if _norm(got, norm) == _norm(check.get("expected", ""), norm):
            return True, None
        return False, f"extracted {got!r} != expected {check.get('expected')!r}"
    if t == "equals":
        norm = check.get("normalize", True)
        body = output.strip() if check.get("strict_json") else _strip_fences(output)
        if _norm(body, norm) == _norm(check.get("expected", ""), norm):
            return True, None
        return False, f"output != expected {str(check.get('expected'))[:80]!r}"
    if t in ("max_chars", "min_chars", "max_words"):
        n = len(output) if t.endswith("chars") else len(output.split())
        lim = int(check.get("value", 0))
        ok = n <= lim if t.startswith("max") else n >= lim
        return (True, None) if ok else (False, f"{t}={lim}, got {n}")
    return False, f"unknown check type {t!r}"


def run_checks(output, task):
    """-> list of grade dicts for one case output. Never raises."""
    grades = []
    counts = {}
    for check in task.get("checks") or []:
        t = check.get("type", "?")
        counts[t] = counts.get(t, 0) + 1
        criterion = t if counts[t] == 1 else f"{t}#{counts[t]}"
        try:
            passed, note = _check_one(output or "", check)
        except re.error as e:
            passed, note = False, f"bad check config (regex): {e}"
        except Exception as e:  # a broken check spec must be visible, not fatal
            passed, note = False, f"bad check config: {e}"
        grades.append({"criterion": criterion, "score": 1.0 if passed else 0.0,
                       "passed": passed, "note": note})
    return grades
