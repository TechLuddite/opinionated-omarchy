# Does the skill help? What was actually measured

Every number here comes from [results/](results/), which is tracked, so each one can be
recomputed from a clean clone with no database and no container:

```sh
python3 skillbench/tools/lift_test.py 28 31          # the agentic null
python3 skillbench/tools/lift_test.py 34             # a chat-lane result, split by task group
```

**44 runs, 3,686 cases, 12,616 graded assertions** as of 2026-09-05.

## The short answer

The Omarchy skill produces a large, replicated, Omarchy-specific improvement when a model is
**asked what to do**, and no improvement at all when an agent is **left to do it**. Those are
two different questions and the bench keeps them apart on purpose.

## Chat lane: a real effect, replicated on four models

`linux-desktop-gauntlet`, 10 repeats, 200 cases per model. This bench is **mixed**, six
Omarchy tasks and four general-Linux ones, so it carries its own control and the
difference-in-differences comes out of a single run.

| model | Omarchy tasks | control tasks | difference |
| --- | ---: | ---: | ---: |
| `nemotron-3.5-lightning-free` | **+28.8 pt** | +3.4 pt | **+25.5** |
| `deepseek-v4-flash` | **+25.1 pt** | +1.8 pt | **+23.2** |
| `qwen3.5-plus` | **+27.3 pt** | -5.3 pt | **+32.6** |
| `qwen3.6-plus` | **+22.6 pt** | -1.8 pt | **+24.3** |

Every Omarchy lift is significant at p < 0.0001. **No control is significant**, and three of
the four are slightly negative.

Two things make this more than a big number. The effect **survives normalising for
headroom**: the skill uses 42% of the room available on Omarchy tasks against 10% on
controls, so it is not an artefact of the controls being easier. And the skill makes answers
**shorter**, 3,257 output tokens bare against 1,000 with it on `deepseek-v4-flash`, which
cuts against the obvious alternative explanation that more context simply produces more
words.

Three further models were run and are **excluded**, not hidden: a `max_tokens: 350` cap in
the bench spec truncated reasoning models before they emitted any answer, and the truncation
was variant-correlated because the skill shortens output. Their contaminated and corrected
figures are both in [JOURNAL.md](../JOURNAL.md).

## Agentic lane: no effect, at full statistical power

`devstral-small-2:24b`, 31 repeats, 62 cases per arm, which is exactly what the power
calculation asked for.

| bench | lift | p |
| --- | ---: | ---: |
| `omarchy-agentic-stale-advice` | +1.9 pt | 0.59 |
| `linux-agentic-deep-triage` (control) | +1.7 pt | 0.47 |
| **difference in differences** | **+0.2 pt** | **0.98** |

The skill moves general-Linux triage as much as it moves Omarchy tasks, which is the exact
condition the controls exist to detect.

**The decay is the methodological point, not the endpoint:**

| n | lift | p |
| ---: | ---: | ---: |
| 3 | +11.1 pt | 0.55 |
| 10 | +8.3 pt | 0.21 |
| 31 | **+1.9 pt** | 0.59 |

Publishing the n=3 figure would have claimed an eleven point improvement that does not exist.

## Agentic lane, cloud models: the skill can divert an agent

The GLM ladder through `opencode run`, 5 repeats per rung.

| rung | Omarchy | control | difference |
| --- | ---: | ---: | ---: |
| `glm-5.1` | -20.0 pt (p=0.02) | +0.0 pt | -20.0 |
| `glm-5.2` | +10.0 pt | +0.4 pt | +9.6 |
| `glm-5.3-flash` | -13.3 pt | -10.0 pt | -3.3 |
| `glm-5.3` | -16.7 pt | -3.7 pt | -13.0 |

The control does not move, so this is not the skill degrading general Linux. What it is, is
specific and visible in the transcripts: on `rebind-packaged-default` with the skill loaded,
**zero file edits and zero clean stops across 20 cases**, while the same skill on the sibling
task produced 7 of each. The skill points the model at `/usr/share/omarchy/`, it researches
the packaged binding API, and it never edits `~/.config/hypr/bindings.lua`. Bare, lacking
that pointer, it edits the user file.

**Treat the magnitudes as directional.** Bare scores 0.90 to 0.97 here, because this bench
was calibrated against a model that solves it 8 times in 20; timeouts run 8 in the skill arm
against 3 bare; and n=5 on a lane where +11.1 became +1.9 between n=3 and n=31.

## Which models can be measured at all

Separate from whether a skill helps: **only 4 of 14 local models can drive an agent loop**,
and the ones that fail do so for reasons no skill addresses, emitting tool calls as prose or
pseudo-XML. See [MODELS.md](MODELS.md) for the ladder and
[ZEN.md](ZEN.md) for the cloud terrain.

That distinction is the reason this bench exists. A model that cannot act and a model that
finds the task trivial produce different scores, but a model out of VRAM, one that times out,
and one that cannot emit a tool call all produce the **same** score: the untouched floor.

## What is not claimed

- **Nothing about the corpus skill.** Every number above measures the *upstream* Omarchy
  skill. The corpus-backed skill this repository exists to build has not been written.
- **Nothing about real users.** These are seeded VMs and graded assertions, not people.
- **Nothing durable about specific models.** Providers retire and replace them; the runs are
  dated and the ids are recorded so a figure can be attributed rather than assumed current.
