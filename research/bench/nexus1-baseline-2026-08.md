# Skill-efficacy baseline — nexus1 Skill Bench, 2026-08-25 → 08-27

What the Omarchy skill is worth, measured. 911 graded cases, ten local models, twelve
runs, zero errors. Every number here was computed from [`raw/nexus1-cases.json`](raw/nexus1-cases.json).

## Provenance and trust

Measured on the lab host `nexus1` by its Skill Bench (FR-011), which prompts a model
through LiteLLM and grades the reply with deterministic checks — regexes, required and
forbidden strings, length caps. Runs 31–43, 2026-08-25 to 08-27, all local models, no
paid spend.

Three things to hold onto before using any of it:

1. **This grades what a model *says*, not what it does.** Every task asks for commands;
   the checks look for the right tool, the right path, the absence of a trap. A model
   that names `hyprctl` and would then fumble the edit scores the same as one that
   would not. The lab's own backlog says this suite is "the clearest argument for P3
   agentic mode" for exactly that reason.
2. **Only `SKILL.md` was benched.** The omarchy skill is a 7-file bundle; its six topic
   guides were not in the prompt. Any instruction that lives only in a topic guide could
   not possibly lift a score, so **every lift below is a floor**, not the real-harness
   number. A keybinding bench was abandoned mid-design over precisely this.
3. **Nobody hand-checked the model outputs.** The checks were verified sound — a regrade
   reported zero bad check configs across 133 patterns — but "the check passed" is not
   "the answer was good".

## Headline

The skill helps, and it helps *specifically*.

| Bench | Run | Model set | Bare | With skill | Δ |
| --- | --- | --- | ---: | ---: | ---: |
| `omarchy-command-discovery` | 39 | qwen2.5 | 0.500 | **1.000** | +50.0 pt |
| `crash-forensics` | 36 | qwen2.5 | 0.656 | **1.000** | +34.4 pt |
| `omarchy-monitor-config` | 33 | 10 models | 0.529 | **0.800** | +27.1 pt |
| `linux-desktop-gauntlet` | 34 | 10 models | 0.574 | **0.732** | +15.8 pt |
| `linux-desktop-gauntlet` | 43 | 10 models | 0.579 | **0.718** | +13.9 pt |

## The discrimination result — the one that matters

`linux-desktop-gauntlet` carries one task from each of ten single-problem benches: six
Omarchy-specific, four general Linux. The general four are a **control**: the skill says
nothing about them, so it should not move them. Pooled across all ten models and the
three gauntlet runs (34, 41, 43):

| Task | Domain | Bare | With skill | Δ |
| --- | --- | ---: | ---: | ---: |
| `shell-bar` | Omarchy | 0.400 | 0.893 | **+49.3** |
| `privilege-escalation` | Omarchy | 0.500 | 0.917 | **+41.7** |
| `command-discovery` | Omarchy | 0.600 | 0.933 | **+33.3** |
| `wrong-tree-edit` | Omarchy | 0.650 | 0.858 | **+20.8** |
| `monitor-config` | Omarchy | 0.492 | 0.667 | **+17.5** |
| `theme-customize` | Omarchy | 0.642 | 0.775 | **+13.3** |
| `pacman-keyring` | control | 0.625 | 0.633 | +0.8 |
| `disk-full` | control | 0.450 | 0.458 | +0.8 |
| `runaway-process` | control | 0.750 | 0.717 | −3.3 |
| `boot-partition-full` | control | 0.693 | 0.620 | −7.3 |

**Omarchy tasks: +29.3 pt mean. Control tasks: −2.3 pt mean.**

That gap is the evidence the lift is real. A skill that merely made answers longer, or
that made the model more agreeable to regex matching in general, would lift the controls
too. It does the opposite — it drifts them slightly negative, which is what you would
expect from spending context on something irrelevant to the question.

## Per-model lift (gauntlet, runs 34/41/43)

| Model | Bare | With skill | Δ |
| --- | ---: | ---: | ---: |
| devstral-small | 0.754 | 0.974 | +21.9 |
| gpt-oss | 0.500 | 0.719 | +21.9 |
| qwen3.8 | 0.509 | 0.711 | +20.2 |
| qwen2.5 | 0.614 | 0.807 | +19.3 |
| qwen2.5-coder | 0.728 | 0.912 | +18.4 |
| qwen2.5-vl | 0.632 | 0.807 | +17.5 |
| gemma4-26b | 0.421 | 0.553 | +13.2 |
| qwen3-coder | 0.816 | 0.904 | +8.8 |
| gemma4 | 0.421 | 0.474 | +5.3 |
| muse-glimmer | 0.421 | 0.430 | +0.9 |

Every model improves; none is harmed. The strongest bare models gain least
(`qwen3-coder` 0.816 → 0.904) and `muse-glimmer` barely moves at all — a skill cannot
help a model that will not follow instructions in the first place.

## What the bare models actually get wrong

The most-failed checks, bare, pooled across all ten models on the gauntlet. This is the
useful part: it is a list of the specific facts the skill supplies.

| Failed | Task | The model failed to mention |
| ---: | --- | --- |
| 30/30 | `privilege-escalation` | `pkexec` |
| 30/30 | `shell-bar` | `shell.json` |
| 30/30 | `shell-bar` | `omarchy refresh shell` |
| 30/30 | `shell-bar` | `omarchy restart shell` |
| 27/30 | `monitor-config` | `~/.config/hypr` |
| 27/30 | `pacman-keyring` | `archlinux-keyring` |
| 27/30 | `wrong-tree-edit` | `~/.config` |
| 25/30 | `theme-customize` | `~/.config/omarchy/themes` |
| 24/30 | `command-discovery` | `omarchy commands` |
| 24/30 | `monitor-config` | `hyprctl` |

Four of these fail **30 out of 30** — every model, every time. Omarchy 4 replaced waybar
with its own Quickshell bar (`~/.config/omarchy/shell.json`, `omarchy refresh shell`),
and no bare model knows it; they answer "waybar" from memory. That single fact is most
of the `shell-bar` +49.3.

## Negative controls

Two runs deliberately tested whether the bench rewards *any* skill or only the right one.

| Run | Bench | A | B | Result |
| --- | --- | --- | --- | --- |
| 37 | `crash-forensics` | none 0.688 | `skill:rewst` **0.563** | an unrelated skill made it **worse** |
| 38 | `crash-forensics` | `diagnose-crash` 1.000 | `omarchy+diagnose-crash` **0.906** | stacking a good skill on a good skill made it worse |

Run 38 is the sharper finding: adding the (perfectly good, but irrelevant here) omarchy
skill on top of `diagnose-crash` cost 3 checks **and** took prompt tokens from 922 to
4102. Context is not free and irrelevant context actively dilutes.

## What the skill costs

Prompt tokens, mean per case, gauntlet run 34:

| Variant | Prompt tokens | Completion tokens |
| --- | ---: | ---: |
| `none` | 134 | 212 |
| `skill:omarchy` | 3,369 | 200 |

About **3.2k tokens of context per call**, every call, for roughly +16 points on the
gauntlet and +29 on the Omarchy-specific half. Completion length barely moves, so the
skill is not buying the score with verbosity.

## Reading these numbers against the lab's own write-ups

The nexus1 handoffs quote slightly different figures for the same runs — e.g. run 31 as
`0.521 → 0.792` with `334 → 13066` prompt tokens, where this document says
`0.500 → 0.786` and `84 → 3266`. **Both are correct; the conventions differ**, and it is
worth knowing which before anyone "fixes" one to match the other:

- The handoffs **macro-average** (mean of per-case pass rates) and quote **total** prompt
  tokens across the run.
- This document **micro-averages** (pooled checks: total passed ÷ total checks) and
  quotes **mean** prompt tokens per case.

Verified: run 31 micro 0.500 / macro 0.521, tokens mean 84 / total 334 — both reproduce
exactly from `raw/nexus1-cases.json`.

## Replication on this workstation, 2026-08-29

`skillbench/` re-ran `omarchy-monitor-config` against the same ten models with the same
task prompts and checks (the spec sha differs only because the file's `skills:` suggestion
list was edited; no prompt or check changed).

| | nexus1 run 33 | ohmy-omarchy run 4 |
| --- | ---: | ---: |
| bare | 0.529 | 0.729 |
| `skill:omarchy` | 0.800 | 0.971 |
| **lift** | **+27.1 pt** | **+24.3 pt** |
| models improving | 10 of 10 | 10 of 10 |
| prompt tokens, skilled | 3,266 | 3,244 |

**The lift reproduces; the absolute levels do not.** Both sides land higher here. The two
candidate causes are the serving path (LiteLLM there, direct Ollama here, with different
default parameters) and model weights having moved under the same tags.

The lesson worth carrying: the bench pins bench and skill content by sha, but **nothing
pins model weights**. Absolute scores are only comparable within a run; deltas survive.
The near-identical prompt-token count (3,244 vs 3,266) confirms the skill body itself is
identical and injected identically, which is what makes the delta comparison legitimate.

## Runs in this dataset

| Run | Bench | Models | Variants | Status |
| --- | --- | ---: | --- | --- |
| 31 | omarchy-monitor-config | 1 | none vs skill:omarchy | done |
| 32 | linux-desktop-gauntlet | 1 | none | done |
| 33 | omarchy-monitor-config | 10 | none vs skill:omarchy | done |
| 34 | linux-desktop-gauntlet | 10 | none vs skill:omarchy | done |
| 35 | crash-forensics | 1 | none vs skill:diagnose-crash | done |
| 36 | crash-forensics | 1 | none vs skill:diagnose-crash | done |
| 37 | crash-forensics | 1 | none vs skill:rewst | done |
| 38 | crash-forensics | 1 | diagnose-crash vs omarchy+diagnose-crash | done |
| 39 | omarchy-command-discovery | 1 | none vs skill:omarchy | done |
| 40 | linux-desktop-gauntlet | 10 | none vs diagnose-crash+frontend-design | aborted |
| 41 | linux-desktop-gauntlet | 10 | none vs diagnose-crash+omarchy | done |
| 43 | linux-desktop-gauntlet | 10 | none vs omarchy+diagnose-crash | done |

Run 40 was stopped by the operator part-way; its rows are kept because a partial matrix
is valid data. Run 42 is absent because it is the `canvas-philosophy` bench (aborted), which is not
part of the Omarchy suite and so falls outside this export's filter.
