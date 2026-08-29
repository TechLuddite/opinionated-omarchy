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

**This grades what a model says, not what it does.** Tasks ask for commands; checks look
for the right tool, the right path, the trap avoided. A model that correctly names
`hyprctl` and would then fumble the edit scores identically to one that would not. That
ceiling is inherent to prompting a model and reading its reply, and it is why `post:` is
reserved in the bench schema (see below).

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

## The host firewall has to allow the bench subnet

Omarchy runs `ufw` with default-deny incoming, so a container cannot reach Ollama on the
host until you allow it. `compose.yaml` pins the network to **172.28.7.0/24** so the rule
can name it exactly — without a pinned subnet Compose allocates a fresh bridge whose name
and range move, and an interface-scoped rule silently stops matching:

```sh
sudo ufw allow from 172.28.7.0/24 to any port 11434 proto tcp \
  comment 'ollama api - omarchy skillbench container'
```

Symptom without it: the UI loads, the bench list populates, and `/readyz` reports
`{"db":true,"ollama":false}` with an empty error — a connect timeout, not a refusal.

This is the same family as the `virbr0` DHCP gap in [CLAUDE.md](../CLAUDE.md): libvirt and
Docker both manage forwarding, neither opens anything on the host's `INPUT` chain.

## Security posture

Plain HTTP, no authentication, and that is deliberate for what this is:

- The port is published on **127.0.0.1 only**. Nothing on the LAN can reach it. That
  binding, not TLS, is what actually contains this service — if you ever change it to
  `0.0.0.0`, you are publishing an unauthenticated remote-code-adjacent surface on your
  network, and TLS would not help.
- **It holds no credentials.** No API keys, no tokens, no passwords — local Ollama needs
  none. There is nothing in transit worth encrypting on a loopback interface.
- The container drops all capabilities, sets `no-new-privileges`, and has memory and pid
  limits. It writes only to `./data`.

The one thing to be aware of: the ufw rule above lets **any** container on 172.28.7.0/24
reach your Ollama. That subnet is dedicated to this compose project, so in practice that
means this bench.

## Layout

```
app/
  main.py     FastAPI routes, aggregation, startup reconciliation
  runner.py   matrix runner, Ollama client, model affinity
  spec.py     bench + skill bundle loading, sha pinning, variant parsing
  checks.py   deterministic graders
  db.py       SQLite schema and helpers
  theme.py    Omarchy colors.toml -> UI palette
  ui.py       the page
benches/      12 bench specs (6 Omarchy, 4 controls, gauntlet, crash-forensics)
skills.yaml   skill bundle manifest
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

## Reserved: the agentic lane

Bench tasks may carry a `post:` block. It is loaded and pinned but currently ignored. It is
where VM state assertions will live when the bench graduates to driving `omarchy agent`
inside the test VMs — running commands for real and grading whether the machine ended up
fixed, instead of whether the model named the right tool. Reserving the field now means
that lane needs no schema migration.

## Provenance

The bench specs, the check vocabulary and the run/resume/regrade semantics are ported from
the OpsVibe lab's Skill Bench (FR-011) on `nexus1`, with the grading semantics unchanged so
results stay comparable. Dropped as unnecessary here: LiteLLM, Postgres, Authelia, the
budget guard, cost projection, the model registry, the paid-model lane, and the 14
non-Omarchy benches.
