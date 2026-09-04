# Writing a bench

A bench is one YAML file in this directory. It is loaded by
[`app/spec.py`](../app/spec.py), graded by [`app/checks.py`](../app/checks.py) (chat) and
[`app/vmchecks.py`](../app/vmchecks.py) (agentic). Read
[../README.md](../README.md) for *why* the bench exists; this file is *how to write one*.

**A bench spec is code.** `seed:` and `post:` are shell, run on a real VM as the bench
user. That is acceptable only because benches are authored in this repo and run against a
disposable machine. It is not a sandbox.

## The two lanes

`lane: chat` (the default) prompts a model once and grades the reply with `checks:`.
`lane: agentic` runs `pi` on a test VM, lets it act, and grades the machine with `post:`.

Which one you want is not a style choice: **the chat lane can only ask whether a model
*mentions* the right thing.** If the claim you want to test is that an agent *does* the
right thing (edits the user tree, leaves the system tree alone), it has to be agentic.

Two rules the loader enforces, and both exist because of real bugs:

- An agentic bench where no task has a `post:` block is **refused**. It would run an agent
  for minutes and grade only its prose: a chat bench in a costume.
- `name:` must equal the filename stem, so a run can never be recorded under a name that
  does not resolve back to a file.

And one the tests enforce: **every lane needs at least one `control: true` bench**
(`test_each_lane_has_at_least_one_control`). A lane with no control produces a lift nobody
can interpret. `test_control_benches_are_flagged` pins the exact set, so adding or removing
a control is a deliberate edit to that test, never an accident.

## Skeleton

```yaml
name: omarchy-thing            # MUST equal the filename stem
description: One line; shown in the UI.
lane: agentic                  # or omit for chat
control: false                 # true = general Linux the skill says nothing about
skills: [omarchy, omarchy-full]   # bundles offered in the UI for this bench
defaults:
  repeats: 1
  params:                      # merged under anything the launch form passes
    thinking: "off"            # agentic: keeps small models from narrating the budget away
    agent_timeout: 600         # agentic: seconds per case
    max_tokens: 350            # chat
    temperature: 0.2           # chat
  vm:                          # agentic only
    restore:                   # paths relative to $HOME, restored before EVERY case
      - .config/hypr
tasks:
  - id: some-task              # unique; agentic ids become a tmux window and a VM path
    prompt: |
      What the model or agent is asked to do.
    seed: |                    # agentic only: the breakage, run before the agent starts
      set -e
      ...
    post:                      # agentic: assertions on the machine afterwards
      - { type: file_contains, path: ~/.config/hypr/bindings.lua, pattern: 'foot' }
    checks:                    # chat: assertions on the transcript
      - { type: regex_required, pattern: '(?i)hyprctl' }
```

## `post:` assertion types (what the agent DID)

Evaluated over ssh after the agent stops; each yields one `grader='post'` row. A malformed
assertion **fails** with the config error in its note. A typo must be visible in the UI,
never silently green.

| type | fields | passes when |
| --- | --- | --- |
| `file_exists` | `path` | the path exists |
| `file_absent` | `path` | the path does not exist |
| `file_contains` | `path`, `pattern`, `case_sensitive?` | file exists **and** matches the ERE |
| `file_not_contains` | `path`, `pattern`, `case_sensitive?` | file is missing **or** does not match |
| `command_succeeds` | `command` | exit 0 |
| `command_fails` | `command` | non-zero exit |
| `command_output_matches` | `command`, `pattern`, `case_sensitive?` | stdout+stderr matches the ERE |

`pattern` is `grep -E`, not PCRE. `case_sensitive` defaults to true.

### Two traps that already invalidated a paired run

Both were caught by a control scoring **exactly 0.500 on every task in both variants**, a
constant rather than a measurement, and both are now regression-tested. They are the reason to
distrust any assertion that looks green on first outing.

- **Tilde paths.** `shlex.quote("~/x")` yields `'~/x'`, which the shell never expands, so
  `test -e` looks for a directory literally named `~`. `_path()` in `vmchecks.py` handles
  this; do not hand-roll quoting. The danger is the asymmetry: `file_exists` and
  `file_contains` fail closed and read as agent failure, while **`file_absent` passes
  trivially and reads as green.** An assertion that cannot fail is the one thing a grader
  must never have.
- **`pgrep` matching its own shell.** `pgrep -f bench-marker` matches the shell running it,
  whose command line contains the pattern, so `command_fails` could never pass. Write
  `[b]ench-marker`.

**Write every assertion so it fails before the fix and passes after, and check both on a
VM by hand.** A control that passes trivially is not evidence of anything.

## `checks:` types (what the model SAID)

`json_valid`, `json_schema` (`schema`), `regex_required` / `regex_forbidden` (`pattern`,
`case_sensitive?`), `contains` / `not_contains` (`value`, `case_sensitive?`),
`extract_equals` (`pattern`, `expected`, `normalize?`), `equals` (`expected`,
`normalize?`), `max_chars` / `min_chars` / `max_words` (`value`).

JSON checks strip a ```` ```json ```` fence first unless `strict_json: true`.

**Do not put `checks:` on an agentic bench.** The first agentic run taught this:
`devstral-small-2` scored 3/3 on the monitor task while its entire transcript was *"Task
completed."* Prose checks were scoring **verbosity** and marking the best-performing agent
down for being terse. Forbidden-pattern checks are worse, because a silent agent
passes them all and reads as 100%. In this lane the machine is the measurement.

## Isolation, and its honest limit

Before every agentic case the VM is restored from a tar of the paths in
`defaults.vm.restore`, taken once at run start. **Anything outside those paths persists.**
This is deliberate, not an oversight: the container runs `cap_drop: ALL` with no libvirt
socket, and handing it the hypervisor to get true disk rollback would trade a real security
property for convenience. Declare every path your seed or the agent might touch. Disk reset
between runs is an operator action (`tools/golden-test-vm.sh`).

## Run the seed check before you spend hours on a run

```sh
python3 skillbench/tools/check_seeds.py            # every agentic seed, 3 cycles
python3 skillbench/tools/check_seeds.py --cycles 12 --bench <name>
```

**A seed is not a one-shot script.** The runner fires it before every case, so the second
cycle is the one that matters, and that is exactly what hand-verification misses. Two runs
were lost to seeds that worked once:

- Run 27 lost a case to a transient systemd unit left in FAILED state, which `stop` does
  not clear and `systemd-run` then refuses to recreate.
- Run 30 lost **51 of 124 cases** to `mount` exit 32, four hours to discover. The teardown
  unmounted before the previous holder had released its fd, deleted the image anyway, and
  left a loop device attached to a dead inode.

Both are the same shape: teardown that assumes the previous case finished cleanly. Write
teardown that waits rather than assumes, detaches what it attached, and removes files last.

The checker runs seeds through a **login shell**, because `vm.run()` does. Get that wrong
and it invents failures: a first draft reported `omarchy-agentic-config/theme-switch` as
broken, when the only problem was `OMARCHY_PATH` being unset outside `bash -l`.

It does not grade anything. Assertion discrimination is a separate question and still has
to be checked by hand against the **shipped** templates.

## Before you commit a bench

- `./tests/run.sh`. Three tests cover every shipped bench, so a broken spec is caught
  here rather than in a run: `test_every_shipped_bench_loads_and_its_checks_compile`,
  `test_no_shipped_post_assertion_can_pass_trivially` (every `post:` path must be
  absolute or `~/`-rooted; a path that cannot resolve makes `file_absent` green no
  matter what the agent did), and `test_control_benches_are_flagged`.
- **A bench edit needs no rebuild; an app edit does.** `compose.yaml` mounts `./benches`
  and `./data` but not `./app`, so a new or edited YAML is picked up on the next run while a
  change to `runner.py`/`vmchecks.py` silently keeps running the old code until
  `docker compose up -d --build`. A grader fix that appears to do nothing is usually this.
- Editing a bench changes its `spec_sha`, which **starts a new run series**. That is the
  intended behaviour: it stops an edit from quietly polluting old results. Do not edit a
  bench to "fix" a run you have already taken.

## The open problem, if you are here to write tasks

**Read [../MODELS.md](../MODELS.md) first.** Both `omarchy-agentic-config` and
`omarchy-agentic-root-config` are **saturated**, and the 2026-09-02 model scan explains why
in a way that changes what you should write: only **4 of 14** local models can drive the
agent loop at all, and all four already score full marks. The other ten score the untouched
floor for reasons no skill addresses: tool calls emitted as prose, empty transcripts, VRAM
spill. **Making a task harder does not create headroom**; it lowers the four capable models
while the other ten stay at the floor.

The one seam left is **not difficulty but wrongness**: a task where the widely-published
answer is confidently wrong on Omarchy 4. `omarchy-agentic-stale-advice` is the first of
these, built on Omarchy 3's `~/.local/share/omarchy` git checkout and hyprlang config that
Hyprland 0.55 deprecated for Lua. Both prompts say the change "must survive an
`omarchy update`", which is satisfiable only from the user tree and never names the answer.

If you write another, copy that shape: **make the wrong answer score BELOW doing nothing.**
In `omarchy-agentic-stale-advice` the floor is 4/6, a hyprlang answer is 3/6 and a correct
one is 6/6, so the grader separates "did nothing" from "did the wrong thing", which a
pass/fail assertion cannot.

**And hand-verify against the SHIPPED config templates, not an empty file.** Both of that
bench's first-draft patterns passed on a file the agent never touched, because
`~/.config/hypr/bindings.lua` ships a commented `-- hl.unbind("SUPER + SPACE")` example and
`looknfeel.lua` ships five commented `hl.config(` examples. `^[^-]*` excludes Lua comments.
That is the tilde-quoting bug of 2026-08-29 wearing different clothes: an assertion that is
green before the agent runs. See [../../JOURNAL.md](../../JOURNAL.md).

### Root is available now, and it was the real ceiling

Every task in `omarchy-agentic-config` is a `~/.config` edit. That was **not** a judgement
about difficulty: until 2026-09-01 the bench user had no passwordless sudo, and the bench
drives the VM over ssh with **no tty**, so nothing requiring root could be seeded, done by
the agent, or asserted. Userspace config is the easy end of Omarchy, and the bench could
only ever reach that end.

`tools/provision-bench-vm.sh` now installs `/etc/sudoers.d/99-bench-nopasswd`, and the
golden images carry it, so it survives a `golden-test-vm.sh reset`. If a `post:` assertion
that uses `sudo` starts failing on a rebuilt VM, that file is the first thing to check.

`omarchy-agentic-root-config` is the first bench built on this. Two things in it are worth
copying:

- **Make a wrong answer a single plausible command.** Its task is resolving a `.pacnew`,
  where `mv` adopts upstream and destroys the local edit, `rm` keeps local and discards the
  new option, and only a real merge keeps both. Asserting on *both* values means each
  shortcut fails a different assertion. Measured on a VM: seed-only 5/8, `mv` 7/8, `rm`
  7/8, correct merge 8/8.
- **Seeds that touch `/etc` must be idempotent.** `defaults.vm.restore` paths are
  `$HOME`-relative, so `/etc` persists between cases. That bench keeps a pristine copy on
  first run and re-derives the live file from it every time, so a case never inherits the
  previous case's merge.
