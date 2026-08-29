"""Bench and skill loading, with content pinning.

A BENCH is benches/<name>.yaml; its `name:` must equal the filename stem, so a bench
can never be recorded under a name that does not resolve back to a file.

A SKILL is a bundle: one or more files under a root directory, concatenated in the
order the manifest declares. This is the deliberate difference from the nexus1 bench,
which could only inject a single SKILL.md and therefore measured a floor rather than
the real number -- a marker living only in a topic guide could never lift a score.

Everything is content-pinned by sha. A run records the bench's spec_sha and the sha of
every skill it used, so an edited bench starts a new series instead of silently
polluting the old one, and an edited skill makes resume refuse.

Tasks may carry a `post:` block. It is loaded, pinned and ignored: it is where VM
state assertions will live when the agentic lane lands, and reserving it now means
that lane needs no schema migration.
"""
import hashlib
import os
import re

import yaml

NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")  # no '/', no '+', no leading dot

BENCH_DIR = os.environ.get("SB_BENCHES", "/benches")
SKILL_MANIFEST = os.environ.get("SB_SKILLS", "/app/skills.yaml")


class SpecError(ValueError):
    pass


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _safe(name, kind):
    if not NAME_RE.match(name or ""):
        raise SpecError(f"invalid {kind} name {name!r}")
    return name


def _strip_frontmatter(text):
    """Drop a leading YAML frontmatter block.

    Skill Bench injects the file as a system-prompt prefix, and only the body is
    prompt text in the real harness too -- the frontmatter is triggering metadata the
    harness consumes itself. Stripping it also keeps our shas comparable with the
    nexus1 baseline, which stripped it the same way.
    """
    if not text.startswith("---"):
        return text
    end = re.search(r"^---\s*$", text[3:], re.M)
    return text[3 + end.end():].lstrip("\n") if end else text


# ---------------------------------------------------------------- benches

def list_benches():
    out = []
    for fn in sorted(os.listdir(BENCH_DIR)):
        if fn.endswith((".yaml", ".yml")):
            try:
                out.append(load_bench(fn.rsplit(".", 1)[0]))
            except SpecError:
                continue
    return out


def load_bench(name):
    _safe(name, "bench")
    for ext in (".yaml", ".yml"):
        path = os.path.join(BENCH_DIR, name + ext)
        if os.path.exists(path):
            break
    else:
        raise SpecError(f"no such bench {name!r}")

    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    spec = yaml.safe_load(raw) or {}
    if spec.get("name") != name:
        raise SpecError(f"bench {name!r} declares name={spec.get('name')!r}; they must match")
    if not spec.get("tasks"):
        raise SpecError(f"bench {name!r} has no tasks")

    seen = set()
    for task in spec["tasks"]:
        tid = task.get("id")
        if not tid:
            raise SpecError(f"bench {name!r} has a task with no id")
        if tid in seen:
            raise SpecError(f"bench {name!r} repeats task id {tid!r}")
        seen.add(tid)
        if not task.get("prompt"):
            raise SpecError(f"bench {name!r} task {tid!r} has no prompt")

    spec["spec_sha"] = _sha(raw)
    spec.setdefault("defaults", {})
    spec.setdefault("skills", [])
    spec.setdefault("control", False)
    return spec


# ---------------------------------------------------------------- skills

_manifest_cache = None


def _manifest():
    global _manifest_cache
    if _manifest_cache is None:
        with open(SKILL_MANIFEST, encoding="utf-8") as fh:
            _manifest_cache = (yaml.safe_load(fh) or {}).get("skills") or {}
    return _manifest_cache


def list_skills():
    out = []
    for name in sorted(_manifest()):
        try:
            body, sha, files = load_skill(name)
        except SpecError:
            continue
        out.append({"name": name, "sha": sha, "chars": len(body), "files": files})
    return out


def load_skill(name):
    """-> (body, sha, [filenames]). Files are concatenated in manifest order."""
    _safe(name, "skill")
    entry = _manifest().get(name)
    if not entry:
        raise SpecError(f"no such skill {name!r}")
    root = entry["root"]
    parts, used = [], []
    for fn in entry.get("files") or ["SKILL.md"]:
        if "/" in fn or fn.startswith("."):
            raise SpecError(f"skill {name!r} declares unsafe file {fn!r}")
        path = os.path.join(root, fn)
        if not os.path.exists(path):
            raise SpecError(f"skill {name!r} is missing {fn!r}")
        with open(path, encoding="utf-8") as fh:
            parts.append(_strip_frontmatter(fh.read()).strip())
        used.append(fn)
    body = "\n\n".join(parts)
    return body, _sha(body), used


# ---------------------------------------------------------------- variants

def parse_variant(variant):
    """'none' -> []; 'skill:a' -> ['a']; 'skill:a+b' -> ['a','b'] (order significant)."""
    if variant == "none":
        return []
    if not variant.startswith("skill:"):
        raise SpecError(f"malformed variant {variant!r}")
    names = [n for n in variant[len("skill:"):].split("+") if n]
    if not names:
        raise SpecError(f"malformed variant {variant!r}")
    if len(set(names)) != len(names):
        raise SpecError(f"variant {variant!r} repeats a skill")
    for n in names:
        _safe(n, "skill")
    return names


def system_prompt_for(variant):
    """-> (system_prompt_or_None, {skill: sha})."""
    names = parse_variant(variant)
    if not names:
        return None, {}
    bodies, revs = [], {}
    for n in names:
        body, sha, _ = load_skill(n)
        bodies.append(body)
        revs[n] = sha
    return "\n\n".join(bodies), revs
