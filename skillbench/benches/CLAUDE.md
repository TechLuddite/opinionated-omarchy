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
right thing — edits the user tree, leaves the system tree alone — it has to be agentic.

Two rules the loader enforces, and both exist because of real bugs:

- An agentic bench where no task has a `post:` block is **refused**. It would run an agent
  for minutes and grade only its prose — a chat bench in a costume.
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

## `post:` assertion types — what the agent DID

Evaluated over ssh after the agent stops; each yields one `grader='post'` row. A malformed
assertion **fails** with the config error in its note — a typo must be visible in the UI,
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

Both were caught by a control scoring **exactly 0.500 on every task in both variants** — a
constant, not a measurement — and both are now regression-tested. They are the reason to
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

## `checks:` types — what the model SAID

`json_valid`, `json_schema` (`schema`), `regex_required` / `regex_forbidden` (`pattern`,
`case_sensitive?`), `contains` / `not_contains` (`value`, `case_sensitive?`),
`extract_equals` (`pattern`, `expected`, `normalize?`), `equals` (`expected`,
`normalize?`), `max_chars` / `min_chars` / `max_words` (`value`).

JSON checks strip a ```` ```json ```` fence first unless `strict_json: true`.

**Do not put `checks:` on an agentic bench.** The first agentic run taught this:
`devstral-small-2` scored 3/3 on the monitor task while its entire transcript was *"Task
completed."* Prose checks were scoring **verbosity** and marking the best-performing agent
down for being terse — and forbidden-pattern checks are worse, because a silent agent
passes them all and reads as 100%. In this lane the machine is the measurement.

## Isolation, and its honest limit

Before every agentic case the VM is restored from a tar of the paths in
`defaults.vm.restore`, taken once at run start. **Anything outside those paths persists.**
This is deliberate, not an oversight: the container runs `cap_drop: ALL` with no libvirt
socket, and handing it the hypervisor to get true disk rollback would trade a real security
property for convenience. Declare every path your seed or the agent might touch. Disk reset
between runs is an operator action (`tools/golden-test-vm.sh`).

## Before you commit a bench

- `./tests/run.sh`. Three tests cover every shipped bench, so a broken spec is caught
  here rather than in a run: `test_every_shipped_bench_loads_and_its_checks_compile`,
  `test_no_shipped_post_assertion_can_pass_trivially` (every `post:` path must be
  absolute or `~/`-rooted — a path that cannot resolve makes `file_absent` green no
  matter what the agent did), and `test_control_benches_are_flagged`.
- Editing a bench changes its `spec_sha`, which **starts a new run series**. That is the
  intended behaviour: it stops an edit from quietly polluting old results. Do not edit a
  bench to "fix" a run you have already taken.

## The open problem, if you are here to write tasks

`omarchy-agentic-config` is **saturated** — `devstral-small-2:24b` scores 24/24 bare, so
there is no headroom for a skill to show up in. What is needed is tasks a capable agent gets
**wrong without the skill**. The productive seam is the Omarchy 3 → 4 tree split, which is
what `pacman -Qkk omarchy` (0 altered files) already tests: stale advice sends an agent to
edit `/usr/share/omarchy`, where the change is both wrong and destroyed by the next update.
The current three tasks are simply too easy. See [../../JOURNAL.md](../../JOURNAL.md).
