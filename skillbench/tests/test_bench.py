"""Unit tests for the graders, the loader and variant parsing.

The lab bench this descends from had tests only for its UI JavaScript; its own audit
logged "the Python graders/spec parser have no tests" as an open finding. These are the
parts where a silent bug corrupts every number the bench produces, so they get tests here.
"""
import asyncio
import os
import sys

import pytest
import yaml

sys.path.insert(0, "/app")
from app import checks, spec, vm as vmmod  # noqa: E402


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
    """Pinned deliberately. The controls are the evidence that a lift is skill efficacy
    and not 'more context makes a model try harder', so this test fails if one is
    deleted to tidy the suite -- and equally if one is added without a deliberate edit."""
    controls = {b["name"] for b in spec.list_benches() if b.get("control")}
    assert controls == {"linux-disk-full", "linux-runaway-process",
                        "linux-boot-partition-full", "linux-pacman-keyring",
                        # the agentic lane's own null case
                        "linux-agentic-triage",
                        # ...which saturates at 0.950 bare, so it cannot show a large lift
                        # and the difference-in-differences against an Omarchy bench is weak
                        # in both directions. This one is hard general Linux, built to the
                        # same shape as the trap bench, to give the DiD something to work
                        # with. Added deliberately 2026-09-03.
                        "linux-agentic-deep-triage"}


def test_each_lane_has_at_least_one_control():
    """A lane with no control can produce a lift nobody can interpret."""
    by_lane = {}
    for b in spec.list_benches():
        by_lane.setdefault(b.get("lane", "chat"), []).append(b)
    for lane, benches in by_lane.items():
        assert any(b.get("control") for b in benches), f"lane {lane!r} has no control bench"


# ----------------------------------------------------------------- agentic lane

def test_lane_defaults_to_chat_and_is_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(spec, "BENCH_DIR", str(tmp_path))
    (tmp_path / "c.yaml").write_text(yaml.safe_dump(
        {"name": "c", "tasks": [{"id": "t", "prompt": "p"}]}), encoding="utf-8")
    assert spec.load_bench("c")["lane"] == "chat"

    (tmp_path / "b.yaml").write_text(yaml.safe_dump(
        {"name": "b", "lane": "telepathy", "tasks": [{"id": "t", "prompt": "p"}]}),
        encoding="utf-8")
    with pytest.raises(spec.SpecError, match="lane"):
        spec.load_bench("b")


def test_agentic_bench_without_post_is_rejected(tmp_path, monkeypatch):
    """An agentic bench that asserts nothing about the VM is a chat bench in disguise:
    it would spend minutes driving an agent and then grade only its prose."""
    monkeypatch.setattr(spec, "BENCH_DIR", str(tmp_path))
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(
        {"name": "a", "lane": "agentic", "tasks": [{"id": "t", "prompt": "p"}]}),
        encoding="utf-8")
    with pytest.raises(spec.SpecError, match="post"):
        spec.load_bench("a")

    (tmp_path / "a.yaml").write_text(yaml.safe_dump(
        {"name": "a", "lane": "agentic",
         "tasks": [{"id": "t", "prompt": "p",
                    "post": [{"type": "file_exists", "path": "~/x"}]}]}), encoding="utf-8")
    assert spec.load_bench("a")["lane"] == "agentic"


def test_agentic_task_ids_must_be_usable_as_vm_paths(tmp_path, monkeypatch):
    """A task id becomes a tmux window name and a directory under /tmp on the VM."""
    monkeypatch.setattr(spec, "BENCH_DIR", str(tmp_path))
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(
        {"name": "a", "lane": "agentic",
         "tasks": [{"id": "../escape", "prompt": "p",
                    "post": [{"type": "file_exists", "path": "~/x"}]}]}), encoding="utf-8")
    with pytest.raises(spec.SpecError, match="VM path"):
        spec.load_bench("a")


def test_skill_files_keep_frontmatter_unlike_the_prompt_form():
    """The two lanes deliver a skill differently on purpose: the chat lane injects a
    system prompt with frontmatter stripped, the agentic lane hands pi real files
    because pi's own discovery reads that frontmatter."""
    files, revs = spec.skill_files_for("skill:omarchy")
    assert [n for n, _ in files] == ["SKILL.md"]
    assert files[0][1].startswith("---")
    body, sha, _ = spec.load_skill("omarchy")
    assert not body.startswith("---")
    # One identity across both lanes, so the resume guard keeps working unchanged.
    assert revs["omarchy"] == sha


def test_skill_files_namespace_bundles_that_share_a_filename():
    """Two bundles in one variant both ship a SKILL.md; they must not collide."""
    files, _ = spec.skill_files_for("skill:omarchy+diagnose-crash")
    names = [n for n, _ in files]
    assert len(names) == len(set(names))
    assert "omarchy/SKILL.md" in names and "diagnose-crash/SKILL.md" in names


# ----------------------------------------------------------------- post assertions

def test_post_assertion_commands_quote_their_arguments():
    """Patterns and paths are quoted so spaces and quotes cannot split the command --
    but a leading ~ must still reach the shell as $HOME. See the tilde tests below."""
    from app import vmchecks
    cmd, _ = vmchecks._command_for(
        {"type": "file_contains", "path": "~/a b/c.lua", "pattern": "x'y"})
    assert '"$HOME"/' in cmd and "'a b/c.lua'" in cmd
    assert "'x'\"'\"'y'" in cmd


def test_unknown_post_assertion_is_a_visible_failure_not_a_pass():
    from app import vmchecks
    with pytest.raises(ValueError, match="unknown post assertion"):
        vmchecks._command_for({"type": "wishful_thinking"})


@pytest.mark.parametrize("bad,msg", [
    ({"type": "file_contains", "path": "~/a"}, "pattern"),
    ({"type": "command_succeeds"}, "command"),
])
def test_malformed_post_assertions_name_the_missing_field(bad, msg):
    from app import vmchecks
    with pytest.raises(KeyError):
        vmchecks._command_for(bad)


def test_vm_target_parsing():
    from app import vm
    assert [(v.name, v.host) for v in vm.Pool("a=1.2.3.4, b=5.6.7.8").vms] == \
        [("a", "1.2.3.4"), ("b", "5.6.7.8")]
    assert len(vm.Pool("").vms) == 0
    with pytest.raises(vm.VMError):
        vm.Pool("no-host-here")


def test_pi_command_never_puts_the_prompt_on_the_command_line():
    """Bench prompts contain quotes, newlines and $; argv is where a spec silently
    becomes a different spec."""
    from app import runner
    cmd = runner._pi_command("qwen2.5:latest", "/tmp/skills/x", "/tmp/case/prompt.txt", {})
    assert "@/tmp/case/prompt.txt" in cmd
    assert "--print" in cmd and "--no-session" in cmd
    assert "--skill /tmp/skills/x" in cmd
    # And anything needing quoting gets it, rather than splitting into extra argv words.
    odd = runner._pi_command("m", "/tmp/sk ills", "/tmp/p p.txt", {})
    assert "--skill '/tmp/sk ills'" in odd and "@'/tmp/p p.txt'" in odd


def test_pi_command_disables_skill_discovery_for_the_none_variant():
    """Otherwise a skill already installed on the VM would leak into the control."""
    from app import runner
    assert "--no-skills" in runner._pi_command("m", None, "/tmp/p.txt", {})


def test_tilde_paths_expand_rather_than_being_quoted_literal():
    """shlex.quote('~/x') gives '~/x', which the shell never expands -- so `test -e`
    looks for a directory literally named "~". The asymmetry is what makes it dangerous:
    file_exists fails closed and looks like the agent did nothing, while file_absent
    passes TRIVIALLY and reads as green. This cost a whole paired run."""
    from app import vmchecks
    cmd, _ = vmchecks._command_for({"type": "file_exists", "path": "~/.config/hypr/x.lua"})
    assert "'~/" not in cmd
    assert '"$HOME"/' in cmd

    absent, _ = vmchecks._command_for({"type": "file_absent", "path": "~/gone"})
    assert '"$HOME"/' in absent and "'~/" not in absent

    # A path with no tilde is still quoted normally.
    plain, _ = vmchecks._command_for({"type": "file_exists", "path": "/etc/some file"})
    assert "'/etc/some file'" in plain


def test_tilde_expansion_survives_a_path_needing_quotes():
    from app import vmchecks
    cmd, _ = vmchecks._command_for({"type": "file_contains", "path": "~/a b/c.lua",
                                    "pattern": "x"})
    assert '"$HOME"/' in cmd and "'a b/c.lua'" in cmd


def test_no_shipped_post_assertion_can_pass_trivially():
    """Guards the class of bug above across every bench: a file_absent whose path cannot
    resolve is green no matter what the agent did."""
    for b in spec.list_benches():
        for t in b["tasks"]:
            for a in t.get("post") or []:
                path = a.get("path")
                if path:
                    assert path.startswith(("~/", "/")), \
                        f"{b['name']}/{t['id']}: post path {path!r} is not absolute"


# ------------------------------------------------------- the VM pool after a bad case

def test_a_drained_vm_leaves_the_pool_and_the_rest_keep_working():
    """Run 29 is why this exists.

    A case left test1 with no session and no IP. The runner's `finally` handed it straight
    back to the pool, and the next ELEVEN cases failed on it with `No route to host`. Every
    one was `skill:omarchy`, because variants run in order, so an infrastructure failure
    arrived looking exactly like a 5.5 point regression caused by the skill.
    """
    pool = vmmod.Pool(targets="a=10.0.0.1,b=10.0.0.2")
    assert len(pool) == 2
    dead = pool.vms[0]
    pool.drain(dead)
    assert len(pool) == 1
    assert dead not in pool.vms
    assert dead in pool.drained
    pool.drain(dead)                      # draining twice must not double-count
    assert len(pool.drained) == 1


def test_acquiring_from_a_fully_drained_pool_raises_rather_than_hangs():
    """An empty queue blocks forever, which reads as a slow run rather than a failed one.

    Driven with asyncio.run rather than pytest.mark.asyncio: the test image installs plain
    pytest, so an async test would be collected, skipped, and quietly prove nothing.
    """
    pool = vmmod.Pool(targets="a=10.0.0.1")
    pool.drain(pool.vms[0])
    with pytest.raises(vmmod.VMError) as e:
        asyncio.run(pool.acquire())
    assert "drained" in str(e.value)
    assert "10.0.0.1" in str(e.value)     # says WHICH machine, so it can be reset


# ----------------------------------------------------------- gateway portability
#
# The chat lane can post to an OpenAI-compatible gateway as well as to Ollama. Four things
# behaved differently enough there to corrupt a run silently, and each is pinned below.

def test_reasoning_is_used_when_content_is_null():
    """Reasoning models leave `content` null and put the answer in `reasoning`.

    Of 18 reachable Zen models, 12 returned null or empty content on a short prompt.
    Reading content alone recorded those as "said nothing" with status ok, which grades as
    a zero rather than as a measurement.
    """
    from app import runner
    out, src = runner._answer_of(
        {"choices": [{"message": {"content": None, "reasoning": "use omarchy update"}}]})
    assert (out, src) == ("use omarchy update", "reasoning")


def test_content_wins_over_reasoning_and_the_source_is_recorded():
    from app import runner
    assert runner._answer_of(
        {"choices": [{"message": {"content": "answer", "reasoning": "thinking"}}]}
    ) == ("answer", "content")
    # Whitespace-only content is not an answer; fall through rather than grading "  ".
    assert runner._answer_of(
        {"choices": [{"message": {"content": "   ", "reasoning": "r"}}]}) == ("r", "reasoning")
    assert runner._answer_of({"choices": [{"message": {}}]}) == ("", "empty")
    assert runner._answer_of({}) == ("", "empty")


def test_provider_5xx_is_unavailable_rather_than_a_model_result():
    """Zen returns a bare 500 for any model the account cannot reach.

    38 of 59 probed models returned it. Recording that as a normal case error lets an
    unconfigured model look exactly like one that failed the task.
    """
    import httpx
    from app import runner
    req = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    five = httpx.HTTPStatusError("boom", request=req, response=httpx.Response(500, request=req))
    four = httpx.HTTPStatusError("nope", request=req, response=httpx.Response(400, request=req))
    assert runner._status_of(five) == "unavailable"
    assert runner._status_of(four) == "error"
    assert runner._status_of(TimeoutError("slow")) == "error"


def test_gateway_model_ids_do_not_get_an_ollama_tag(monkeypatch):
    """`glm-5.2:latest` is not a model. The tag is an Ollama convention only."""
    from app import runner
    monkeypatch.setattr(runner, "CHAT_BASE", "https://opencode.ai/zen")
    monkeypatch.setattr(runner, "OLLAMA_BASE", "http://host.docker.internal:11434")
    assert asyncio.run(runner._resolve("glm-5.2")) == "glm-5.2"
    monkeypatch.setattr(runner, "CHAT_BASE", runner.OLLAMA_BASE)
    assert asyncio.run(runner._resolve("llama3.1")) == "llama3.1:latest"


def test_migrations_are_idempotent_and_additive():
    """init() runs on every start, so a migration must survive being applied twice."""
    import sqlite3
    from app import db
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(db.SCHEMA)
    for table, column, _ in db.MIGRATIONS:
        cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
        assert column in cols, f"{table}.{column} missing from SCHEMA; a fresh DB would lack it"


def test_empty_chat_base_falls_back_to_ollama(monkeypatch):
    """compose interpolates an unset variable to "", not to absent.

    os.environ.get("SB_CHAT_BASE", OLLAMA_BASE) returns that empty string rather than the
    default, so the chat lane would post to a URL with no host.
    """
    import importlib
    monkeypatch.setenv("OLLAMA_BASE", "http://127.0.0.1:11434")
    monkeypatch.setenv("SB_CHAT_BASE", "")
    from app import runner
    importlib.reload(runner)
    assert runner.CHAT_BASE == "http://127.0.0.1:11434"
    monkeypatch.setenv("SB_CHAT_BASE", "https://opencode.ai/zen")
    importlib.reload(runner)
    assert runner.CHAT_BASE == "https://opencode.ai/zen"


def test_model_catalogue_follows_the_chat_base(monkeypatch):
    """Ollama answers /api/tags; a gateway answers /v1/models. They do not share a shape."""
    import importlib
    monkeypatch.setenv("OLLAMA_BASE", "http://127.0.0.1:11434")
    monkeypatch.setenv("SB_CHAT_BASE", "https://gw.invalid")
    from app import runner
    importlib.reload(runner)
    seen = {}

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            seen["url"] = url
            return FakeResp({"data": [{"id": "glm-5.2"}, {"id": "kimi-k3"}]})

    monkeypatch.setattr(runner.httpx, "AsyncClient", FakeClient)
    assert asyncio.run(runner.list_models()) == ["glm-5.2", "kimi-k3"]
    assert seen["url"] == "https://gw.invalid/v1/models"


# ------------------------------------------------------------------ opencode backend

def test_opencode_none_arm_cannot_see_a_skill():
    """The control arm must not inherit Omarchy's own skills.

    opencode discovers from $HOME/.agents/skills, and Omarchy symlinks `omarchy` and
    `diagnose-crash` there on every install, host and VM alike. Without clearing it the
    `none` variant silently carries the skill it exists to control for.
    """
    from app import runner
    cmd = runner._opencode_command("opencode-go/glm-5.3", None, "/r/w/prompt.txt", "none")
    assert "rm -rf ~/.agents/skills" in cmd
    assert "mkdir -p ~/.agents/skills" in cmd
    assert "ln -sfn" not in cmd


def test_opencode_does_not_relocate_home():
    """Relocating HOME controls skills and breaks the task.

    These benches edit ~/.config/hypr/..., so an empty HOME means the agent finds no
    config, writes edits where the post assertions do not look, and BOTH arms score the
    do-nothing floor for reasons unrelated to the skill. Run 39 did exactly that and read
    as a capability failure. Only ~/.agents/skills may be touched.
    """
    from app import runner
    for variant, sd in (("none", None), ("skill:omarchy", "/r/skills/omarchy")):
        cmd = runner._opencode_command("opencode-go/glm-5.3", sd, "/r/w/p.txt", variant)
        assert "HOME=" not in cmd, "HOME must not be overridden"


def test_opencode_skill_arm_links_exactly_one_skill():
    from app import runner
    cmd = runner._opencode_command("opencode-go/glm-5.3", "/r/skills/skill_omarchy",
                                   "/r/w/prompt.txt", "skill:omarchy")
    assert cmd.count("ln -sfn") == 1
    assert "/r/skills/skill_omarchy" in cmd
    assert "~/.agents/skills/omarchy" in cmd
    # Omarchy's own diagnose-crash is removed by the rm, not linked back.
    assert "diagnose-crash" not in cmd


def test_opencode_skill_name_comes_from_the_variant():
    from app import runner
    cmd = runner._opencode_command("m", "/r/s", "/r/p", "skill:omarchy-full")
    assert "~/.agents/skills/omarchy" in cmd


def test_opencode_asks_for_json_and_never_puts_the_prompt_in_argv():
    """Same rule as the pi command: a prompt carries quotes, newlines and $, and argv is
    where a spec silently becomes a different spec. It is read from the file at run time."""
    from app import runner
    cmd = runner._opencode_command("opencode-go/glm-5.3", None, "/r/w/prompt.txt", "none")
    assert "--format json" in cmd
    assert "$(cat '/r/w/prompt.txt')" in cmd or "$(cat /r/w/prompt.txt)" in cmd


def test_opencode_command_carries_no_credential():
    """The token is provisioned into the VM's profile by tools/install-agent-key.sh, never
    passed through a command, where it would sit in the VM's process table."""
    from app import runner
    cmd = runner._opencode_command("opencode-go/glm-5.3", "/r/s", "/r/w/p.txt", "skill:omarchy")
    for marker in ("API_KEY", "sk-", "Bearer", "token"):
        assert marker not in cmd


def test_opencode_model_ids_keep_their_provider_prefix():
    """opencode ids are provider/name with no tag; _resolve would append Ollama's :latest."""
    from app import runner
    cmd = runner._opencode_command("opencode-go/qwen3.8-flash", None, "/r/w/p.txt", "none")
    assert "opencode-go/qwen3.8-flash" in cmd
    assert ":latest" not in cmd


def test_opencode_runs_with_home_as_its_working_directory():
    """Without --dir "$HOME" the agent cannot edit anything it is asked to edit.

    opencode requires approval for writes outside its working directory, and `run` is
    non-interactive, so the call returns "The user rejected permission to use this specific
    tool call" and the agent continues as though it chose not to act. Runs 39, 40 and 41
    all floored that way, on two models, while reading exactly the right files.
    """
    from app import runner
    cmd = runner._opencode_command("opencode-go/glm-5.3", None, "/r/w/p.txt", "none")
    assert '--dir "$HOME"' in cmd
