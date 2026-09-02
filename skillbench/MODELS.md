# Local model feasibility — the agentic lane

**Measured 2026-09-02** on `omarchy-agentic-root-config` (run 21), bare (`variant: none`),
one repeat per model, all 14 tool-capable models the host serves.

Read this **before concluding a bench is too easy**. A model that cannot drive the agent
loop and a model that finds the task trivial produce *different* scores, but a model that
runs out of VRAM, one that times out, and one that emits its tool call as prose all
produce the **same** score — the untouched floor. The score column alone cannot tell you
which you are looking at, and that difference decides whether the fix is a harder bench or
a different model.

## The floor is 5/8, not 0

`omarchy-agentic-root-config` has 8 post assertions. **A model that does nothing scores
5/8**, because five of them are "you did not break anything" — `pacman -Qkk` clean, the
local customisation still present, and so on. The three that actually move are: adopt the
new upstream setting, remove the `.pacnew`, regenerate the boot config.

So **5/8 means "did nothing"** and 8/8 means "did the whole job". There is very little in
between, which is itself the finding.

## Four gates, and they fail differently

1. **Tool support.** `capabilities` must include `tools`. Without it pi fails instantly
   with HTTP 400 `does not support tools`. Check with
   `python3 skillbench/tools/probe_models.py` — no run needed.
2. **VRAM.** Weights *plus* a 32K KV cache must fit the 24 GiB card. A model that does not
   fit **does not fail cleanly** — Ollama spills the remainder to CPU and the case crawls
   into the agent timeout, which reads as a capability failure. Confirm with
   `curl -s localhost:11434/api/ps` mid-run and look at `size_vram` against `size`.
3. **Harness compatibility.** The model must survive pi's OpenAI-compat request shape.
   `qwen3.8:27b` returns `500: no user query found in messages` and never gets to try —
   that is a **blocked** verdict, not an incapable one, and it must not be recorded as a
   capability judgement.
4. **Agentic competence.** Declared tool support is *not* competence. Most models that
   pass gate 1 still fail here, and a skill cannot fix any of them: they do not lose on
   Omarchy knowledge, they lose before knowledge is reachable.

## Results

| model | params | disk | on GPU | score | time | verdict | what happened |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `qwen3-coder:30b` | 30.5B | 18.6 GB | 100% | 8/8 | 41 s | **✓ capable** | **Solves it.** |
| `gemma4:26b` | 25.8B | 18.0 GB | 100% | 8/8 | 96 s | **✓ capable** | **Solves it.** |
| `devstral-small-2:24b` | 24.0B | 15.2 GB | 100% | 8/8 | 86 s | **✓ capable** | **Solves it.** |
| `qwen3.8:27b` | 27.3B | 17.7 GB | 100% | 5/8 | 220 s | ⚠ blocked | **Blocked, not judged** — pi/Ollama: `no user query found in messages`. |
| `qwen3:32b` | 32.8B | 20.2 GB | 90% | 5/8 | 236 s | ✗ floor | Weights + 32K KV exceed the card — 10% on CPU, then stalls. |
| `muse-glimmer:30b` | 27.9B | 18.2 GB | 100% | 5/8 | 603 s | ✗ floor | Fits entirely on GPU; still exceeded the 600 s budget. |
| `mistral-small3.2:24b` | 24.0B | 15.2 GB | 100% | 5/8 | 19 s | ✗ floor | Acts, hits a permission error, gives up. |
| `gpt-oss:20b` | 20.9B | 13.8 GB | 100% | 5/8 | 61 s | ✗ floor | Empty transcript. |
| `gemma4` | 8.0B | 9.6 GB | 100% | 5/8 | 39 s | ✗ floor | **Claims success falsely** — reports the merge done, changed nothing. |
| `qwen3:14b` | 14.8B | 9.3 GB | 100% | 5/8 | 25 s | ✗ floor | Empty transcript. |
| `qwen2.5-coder:14b` | 14.8B | 9.0 GB | 100% | 5/8 | 15 s | ✗ floor | Emits the tool call as fenced `json` text. |
| `qwen2.5vl:7b` | 8.3B | 6.0 GB | – | – | – | ✗ no tools | No tool support — HTTP 400, cannot run. |
| `granite3.3:8b` | 8.2B | 4.9 GB | 100% | 5/8 | 14 s | ✗ floor | Emits pseudo-XML `<file name=…>` instead of a tool call. |
| `llama3.1:8b` | 8.0B | 4.9 GB | 100% | 5/8 | 10 s | ✗ floor | Emits the tool call as JSON text. |
| `qwen2.5` | 7.6B | 4.7 GB | 100% | 5/8 | 81 s | ✗ floor | Narrates shell in markdown; never executes. |

## What this means for measuring skills

**Three of fourteen local models can run this bench at all**, and all three already score
8/8 bare. There is therefore **no headroom on this bench for any skill to demonstrate a
lift**, and run 18 confirmed it directly: `devstral-small-2:24b`, `none` vs
`skill:omarchy`, came out 0.958 vs 0.958 — identical to three decimals — at 3.0× the
latency.

The band is narrow and it is not obvious from the outside: **every model capable enough to
drive the loop is also capable enough to finish the task.** Writing harder agentic tasks
is therefore *not* obviously the fix — the failing models will keep scoring the floor for
reasons that have nothing to do with what a skill could tell them. That was the assumption
behind the old backlog item and this table is the evidence against it.

The most dangerous single result is `gemma4` (8B), which **reported the merge complete
while changing nothing**. Any grader that trusted the transcript would have scored it a
success. This is exactly why the agentic lane asserts on the machine and carries no
transcript checks.

## Reproducing

```sh
python3 skillbench/tools/probe_models.py          # gates 1 and 2, no run needed
tools/provision-bench-vm.sh 1 2                   # REQUIRED after adding a model
```

**Re-provision after pulling a model.** pi's `~/.pi/agent/models.json` is written by
provisioning. pi still *runs* an unlisted model — it warns `not found for provider ollama.
Using custom model id` and carries on with its own defaults — so an unlisted model is not
configured identically to a listed one, and nothing surfaces as an error. The list is
derived from Ollama's tool-capable models, so pulling plus re-provisioning is enough; you
never edit the list by hand.

Then launch a bare scan across every model from the UI, or:

```sh
curl -sX POST http://127.0.0.1:8878/api/runs -H 'Content-Type: application/json' \
  -d '{"bench":"omarchy-agentic-root-config","variants":["none"],"repeats":1,
       "models":["<model>", "..."]}'
```

## Caveats

- **One repeat per model on one bench.** Enough to separate "cannot act" from "solves it",
  which is what this table is for. It is *not* enough to rank the three capable models
  against each other.
- **Model weights cannot be pinned.** A tag moves under you. Trust deltas within a run;
  distrust absolute scores across runs separated by time — the same warning the READMEs
  give for the chat lane applies here.
- **The host settings are load-bearing and live outside this repo**, on the ollama systemd
  unit: `OLLAMA_CONTEXT_LENGTH=32768` (Ollama's own default is 4096),
  `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_MAX_LOADED_MODELS=1`.
  `pi --list-models` reporting `128K` is **cosmetic** — pi speaks OpenAI-compat, which
  cannot set `num_ctx`; the server decides. See [../CLAUDE.md](../CLAUDE.md).
- `qwen3.8:27b` is unjudged, not incapable. Fixing the pi/Ollama request-shape problem
  would add a fourth data point in the 27B class, where the capable models already live.
