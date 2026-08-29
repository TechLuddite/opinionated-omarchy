# Omarchy Skill Bench

Does the Omarchy skill measurably improve a model's answers on Omarchy problems, by how
much, and what does it cost in context? This turns that from an impression into a number.

One container, local Ollama, no accounts, no keys, no cloud. `http://127.0.0.1:8878`.

```bash
cd skillbench
docker compose up -d --build
xdg-open http://127.0.0.1:8878
```

## What it does

A **bench** (`benches/<name>.yaml`) is a set of tasks: a prompt plus deterministic checks
— required and forbidden patterns, required strings, length caps. A **skill** is a bundle
of markdown files injected as a system-prompt prefix. A **variant** is an ordered stack of
skills (`none`, `skill:omarchy`, `skill:omarchy+diagnose-crash`). A **run** executes the
{task × model × variant × repeat} matrix and grades every answer.

You pick a bench, some local models, and two variants — typically `none` versus
`skill:omarchy` — and get back a pass rate for each side, per model and per task, with the
context cost attached.

## The methodology, and its limits

There are **two lanes**, and a bench declares which one it is in with `lane:`.

**The chat lane grades what a model says.** Tasks ask for commands; checks look for the
right tool, the right path, the trap avoided. A model that correctly names `hyprctl` and
would then fumble the edit scores identically to one that would not. That ceiling is
inherent to prompting a model and reading its reply.

**The agentic lane grades what an agent does.** It runs `pi` on a real Omarchy VM, lets
it act on the machine, and then asserts on the machine — see "The agentic lane" below.
The first run of it produced exactly the gap the chat lane cannot see: on `theme-switch`,
both variants talked sensibly about Omarchy theming, and only the one with the skill
actually left the system on the requested theme.

Three things keep the numbers honest:

- **Control benches.** Four of the twelve (`linux-disk-full`, `linux-runaway-process`,
  `linux-boot-partition-full`, `linux-pacman-keyring`) are general Linux that the skill
  says nothing about. A bare model should already score well and the skill should barely
  move them. They are flagged `control: true` and labelled in the UI. If a change lifts
  the controls as much as the Omarchy benches, it is not measuring skill efficacy — it is
  measuring answer length. In the baseline this separation is stark: **+29.3 pt mean on
  Omarchy tasks, −2.3 pt on controls.**
- **Symmetric comparison.** A run compares its own variants against each other. Better is
  green and worse is orange on both rows; red is reserved for errors. There is no "grade
  against a base" framing.
- **Content pinning.** Every run records the bench's `spec_sha` and each skill's sha. Edit
  a bench and the next run is a new series rather than a quiet extension of the old one.
  Edit a skill and resume refuses — start a fresh run instead.

### The one input that cannot be pinned

Benches and skills are sha-pinned. **Model weights are not.** `qwen2.5` is a moving tag:
re-pull it and the same bench, same skill, same checks can produce different absolute
scores with nothing in the run record to show why.

This is not hypothetical. Replicating nexus1's ten-model run of `omarchy-monitor-config`
here gave `0.729 → 0.971` where the lab measured `0.529 → 0.800`. The **lift** reproduced
closely — **+24.3 pt against +27.1 pt**, with every model improving or tying in both — but
both absolute levels landed higher, most likely from the serving path (direct Ollama here,
LiteLLM there) and possible weight updates in between.

The practical rule: **trust the delta within a run, distrust absolute scores across runs
separated by time.** A run compares its own variants against each other under identical
conditions, which is exactly why the bench is built that way.

Full baseline and prior art: [`research/bench/`](../research/bench/).

## Skills are bundles, not files

`skills.yaml` declares each skill as a list of files concatenated in order, with YAML
frontmatter stripped. This is the deliberate difference from the lab bench this descends
from, which could inject only a single `SKILL.md` — so an instruction living in a topic
guide could never lift a score, and its own backlog recorded every measured lift as *"a
floor, not the real-harness number."*

Both forms ship, so the difference is measurable:

| Variant | What it injects |
| --- | --- |
| `skill:omarchy` | `SKILL.md` only — comparable with the nexus1 baseline |
| `skill:omarchy-full` | `SKILL.md` + all six topic guides |

Running one against the other answers "what are the topic guides actually worth?"

The bundles are mounted read-only from this repo — `../omarchy` and `../diagnose-crash`,
the real skills, not copies. Editing them changes the next run.

## Checks

`json_valid`, `json_schema` (pragmatic subset), `regex_required`, `regex_forbidden`,
`contains`, `not_contains`, `extract_equals`, `equals`, `max_chars`, `min_chars`,
`max_words`.

A broken output is a failed check, never a crashed run. A broken *check spec* is also a
failed check with the config error in the note, so a typo in a bench is visible in the UI
instead of silently passing everything.

**Regrade re-runs every check from stored output with zero model calls**, which is what
makes check authoring cheap: fix a pattern, hit Regrade, see the corrected numbers in a
second. Raw output is kept on every case precisely so this is possible.

## Run control

- **Stop** keeps a valid partial matrix.
- **Resume** fills only the missing cells, and refuses if the bench or a skill changed.
- **Regrade** re-scores from stored outputs.
- A container restart mid-run marks the run `aborted` at startup rather than leaving it
  wedged at `running` forever; Resume then picks it up.

## Model affinity is mandatory here

Ollama on this workstation runs `OLLAMA_MAX_LOADED_MODELS=1`. The runner therefore
finishes a model's entire suite before touching the next one — otherwise a multi-model run
would evict and reload 18 GB of weights between individual cases. `SB_CONCURRENCY` (2) is
parallelism *within* the current model, where the weights are already resident.

There is no cost column and no budget guard, because every model is local and free. What a
skill costs shows up as **prompt tokens**, which is the number worth watching: the baseline
skill adds ~3.2k tokens of context to every single call.

## Why this runs on the host network

`compose.yaml` sets `network_mode: host`, and the agentic lane is the reason.

libvirt's own forward chain rejects every **new** connection into `192.168.122.0/24` that
does not come from `virbr0`:

```
oif "virbr0" ... ct state established,related   accept
oif "virbr0"                                    reject
```

No rule elsewhere can undo that. In nftables an `accept` in one base chain does not stop
another base chain at the same hook from rejecting, and only `reject`/`drop` are terminal —
so a bridged container cannot reach the test VMs at all, and gets `Connection refused`.
Traffic originating in the host namespace never passes the forward hook, so it simply works.

This **removed** a trap rather than adding one. On the host network the bench reaches Ollama
at `127.0.0.1`, so the ufw rule that bridged networking needed (`ufw allow from 172.28.7.0/24
to any port 11434`) is no longer part of the story at all — one less invisible host-level
dependency of the kind that has already bitten twice here (see the `virbr0` DHCP gap in
[CLAUDE.md](../CLAUDE.md)). That rule can be deleted if nothing else uses it.

Exposure is unchanged: the app binds `127.0.0.1:8878` itself (`SB_HOST`/`SB_PORT`) instead
of relying on a loopback port publish.

## Security posture

Plain HTTP, no authentication, and that is deliberate for what this is:

- The app binds **127.0.0.1 only** (`SB_HOST`). Nothing on the LAN can reach it. That
  binding, not TLS, is what actually contains this service — if you ever change it to
  `0.0.0.0`, you are publishing an unauthenticated remote-code-adjacent surface on your
  network, and TLS would not help. On host networking this is the *only* thing containing
  it, since there is no port publish to fall back on.
- **It holds one credential, and only for the agentic lane.** `secrets/bench_ed25519` is
  an ssh key generated by `tools/install-bench-key.sh`, mounted read-only, and accepted by
  nothing but the two disposable test VMs. It is deliberately **not** the operator's own
  key, and it is gitignored. No API keys, no tokens — local Ollama needs none.
- The container drops all capabilities, sets `no-new-privileges`, and has memory and pid
  limits. It writes only to `./data`.

Two things to be aware of, both consequences of the agentic lane:

- **Host networking means no network namespace isolation.** The container shares the host's
  stack. Capabilities are still dropped and `no-new-privileges` is still set.
- **A bench spec is code.** `seed:` scripts and `post:` assertions are shell, run on a VM
  as the bench user. That is fine for specs authored in this repo against disposable
  machines, and it is not a sandbox — a bench is not the place to run something you would
  not run by hand.

## Layout

```
app/
  main.py     FastAPI routes, aggregation, startup reconciliation
  runner.py   matrix runner: the chat lane and the agentic lane
  spec.py     bench + skill bundle loading, sha pinning, variant parsing, lanes
  checks.py   deterministic graders  -- what the agent SAID
  vmchecks.py post assertions        -- what the agent DID
  vm.py       test-VM targets: ssh, tmux mirror, isolation, skill delivery
  db.py       SQLite schema and helpers
  theme.py    Omarchy colors.toml -> UI palette
  ui.py       the page
benches/      13 bench specs (6 Omarchy chat, 4 controls, gauntlet, crash, 1 agentic)
skills.yaml   skill bundle manifest
secrets/      the agentic lane's ssh keypair - generated, gitignored
data/         SQLite results DB - derived, gitignored, delete it to start over
tests/        run with tests/run.sh
```

## The UI

Dropdowns, chips, buttons, tables and bar charts — nothing bespoke. The 8-bit look comes
from geometry (hard corners, 3px edges, offset shadows, segmented meters) rather than a
downloaded font, so it renders identically offline.

Chrome colors are read live from `/usr/share/omarchy/themes/<name>/colors.toml`; the theme
dropdown switches the whole UI and 22 themes are available.

**Chart series colors are deliberately *not* theme-derived.** A theme's `colors.toml` is a
terminal palette — its colors are chosen to be legible as text on that background, not to
be distinguishable from each other as adjacent bars, and several themes have pairs that
collapse under color-vision deficiency. The categorical slots are a fixed set validated
against the extreme surfaces on this machine (`#000000` and `#ffffff`) for lightness band,
chroma floor, CVD separation and contrast.

## The agentic lane

A bench with `lane: agentic` does not prompt a model. It runs **`pi` on a real Omarchy
test VM**, lets the agent use its own tools on the machine, and then grades the machine.

```
acquire a VM  ->  restore declared paths  ->  run seed:  ->  pi --print --skill <bundle>
                                                              (in a tmux window)
              ->  evaluate post: over ssh  ->  release the VM
```

**What it measures that the chat lane cannot.** `omarchy-agentic-config` asks an agent to
add a keybinding, switch a theme, and configure a monitor. Every task also asserts
`pacman -Qkk omarchy` reports **0 altered files** — a hard statement that the agent stayed
out of `/usr/share/omarchy`, which is where Omarchy-3-era advice sends it. A chat bench can
only ask whether a model *mentions* the right directory; this asks whether it stayed out of
the wrong one while actually doing the work.

Grades come from two graders and the UI keeps them apart:

| grader | grades | shown as |
| --- | --- | --- |
| `check` | the agent's transcript | QUALITY |
| `post` | the VM afterwards | STATE |

That separation is the point. A model can describe the right edit and still not make it,
and collapsing both into one number would hide exactly the thing worth seeing.

### Setting it up

```sh
tools/install-bench-key.sh 1 2     # dedicated ssh key -> both VMs
tools/provision-bench-vm.sh 1 2    # autologin, no idle lock, tmux mirror, pi -> Ollama
```

Then point `SB_VMS` at them in `compose.yaml` (`name=host,...`; addresses come from
`sudo virsh net-dhcp-leases default` and move after a rebuild). `/readyz` reports each VM's
`ready` and `tmux` state, and the launch panel refuses to start an agentic run when no VM
is usable.

### Watching it happen

Each case runs as its own **tmux window** in a long-lived session, and each VM's console has
a terminal attached to that session **read-only**. Put the two VNC windows on screen
(`tools/view-test-vms.sh`) and you watch the agent work in real time, on the machine it is
working on, with no second copy of anything.

Read-only is load-bearing in both directions: a watcher cannot type into a running case, and
the runner therefore must never use `tmux send-keys` — tmux refuses it outright while a
read-only client is attached. Launching each case *as* a window is the supported path.

### Isolation, and its honest limit

Before every case the VM is restored to a tar taken once at run start, of the paths the
bench declares under `defaults.vm.restore`. **Anything outside those paths persists.**

It is not a disk rollback, and that is a deliberate trade. A rollback would be stronger and
on btrfs costs about a second (`tools/golden-test-vm.sh`), but the container would have to
drive libvirt — and it runs with `cap_drop: ALL`, `no-new-privileges` and no libvirt socket.
Handing it the host's hypervisor would trade a real security property for convenience. The
disk-level reset stays an operator action between runs:

```sh
tools/golden-test-vm.sh save 1     # once, from a known-good VM
tools/golden-test-vm.sh reset 1    # ~1s, VM must be shut off
```

### Things that will bite

- **Everything runs in a login shell.** Omarchy exports `OMARCHY_PATH` from `~/.bashrc`, so
  a plain `ssh host omarchy ...` runs with it unset and every omarchy subcommand fails with
  `find: '/themes/': No such file or directory`. It matters twice: a tmux window inherits
  the *tmux server's* environment, and that server is started by a systemd user unit with no
  profile sourced at all — so without `bash -l` the **agent** is the thing running without
  `OMARCHY_PATH`.
- **The console locks itself if you let it.** Omarchy 4's lock is an `ext-session-lock`
  surface owned by `omarchy-shell`; it exposes `lock()` but deliberately no `unlock()`, and
  it survives its client's death. A locked headless VM cannot be unlocked — only prevention
  works, which is what `provision-bench-vm.sh` does. Do not `pkill` the lock client.
- **A case is minutes, not seconds**, and concurrency is the size of the VM pool, not
  `SB_CONCURRENCY`: a case owns the machine it runs on. Agentic runs must be narrow by
  design.

## Provenance

The bench specs, the check vocabulary and the run/resume/regrade semantics are ported from
the OpsVibe lab's Skill Bench (FR-011) on `nexus1`, with the grading semantics unchanged so
results stay comparable. Dropped as unnecessary here: LiteLLM, Postgres, Authelia, the
budget guard, cost projection, the model registry, the paid-model lane, and the 14
non-Omarchy benches.
