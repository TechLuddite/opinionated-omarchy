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

A bench declares a LANE. `lane: chat` (the default) prompts a model and grades the
reply. `lane: agentic` runs a real agent harness on a test VM and grades the machine
afterwards, via each task's `post:` block. The field lives inside the yaml, so the lane
is covered by spec_sha like everything else: changing it starts a new series rather
than quietly redefining an existing one.
"""
import hashlib
import os
import re

import yaml

NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")  # no '/', no '+', no leading dot
LANES = {"chat", "agentic"}

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

    lane = spec.get("lane", "chat")
    if lane not in LANES:
        raise SpecError(f"bench {name!r} declares lane={lane!r}; want one of {sorted(LANES)}")

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
        # A task id becomes a tmux window name and a directory under /tmp on the VM.
        if lane == "agentic" and not NAME_RE.match(tid):
            raise SpecError(f"bench {name!r} task id {tid!r} is not usable as a VM path")

    # An agentic bench that asserts nothing about the machine is a chat bench wearing a
    # costume: it would run an agent for minutes and grade only its prose. Refuse it,
    # because the whole claim of this lane is that it measures what the agent DID.
    if lane == "agentic" and not any(t.get("post") for t in spec["tasks"]):
        raise SpecError(f"bench {name!r} is agentic but no task has a `post:` block")

    spec["spec_sha"] = _sha(raw)
    spec["lane"] = lane
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


def skill_files_for(variant):
    """-> ([(filename, raw_text), ...], {skill: sha}) for the agentic lane.

    Deliberately NOT the same bytes as system_prompt_for(). There, a skill is a system
    prompt and the frontmatter is stripped, because in a real harness the frontmatter is
    triggering metadata the harness consumes rather than prompt text. Here pi IS that
    harness: it reads the frontmatter itself, so the files go over intact.

    The recorded sha is still the stripped-body one from load_skill(), so a skill has a
    single identity across both lanes and the resume guard keeps working unchanged. Any
    edit to a file changes the stripped body too, so nothing escapes the pin.
    """
    names = parse_variant(variant)
    files, revs = [], {}
    for n in names:
        _, sha, used = load_skill(n)
        revs[n] = sha
        root = _manifest()[n]["root"]
        for fn in used:
            with open(os.path.join(root, fn), encoding="utf-8") as fh:
                # Prefix with the skill name so two bundles in one variant cannot
                # collide on a shared filename (both ship a SKILL.md).
                files.append((f"{n}/{fn}" if len(names) > 1 else fn, fh.read()))
    return files, revs


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
