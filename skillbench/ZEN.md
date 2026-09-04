# OpenCode Zen: what the API actually does

**Measured 2026-09-04** against `https://opencode.ai/zen/v1` with one account key. The
local-model sibling to this file is [MODELS.md](MODELS.md), and it exists for the same
reason: establish the terrain *before* designing runs, because a model that cannot be
reached and a model that fails the task look identical in a score column.

Re-check any of this with:

```sh
python3 skillbench/tools/probe_zen.py snapshot -o /tmp/zen-a.json
python3 skillbench/tools/probe_zen.py diff /tmp/zen-a.json /tmp/zen-b.json
```

## The shape of it

`POST /zen/v1/chat/completions` and `GET /zen/v1/models`, OpenAI-compatible, with
`Authorization: Bearer <key>`. **A Go subscription does reach the raw API**, which was the
open question at signup, so the bench can drive it directly rather than through the
opencode CLI.

```
listed 66 | probed 59 | reachable 18 | HTTP 500 on 38
```

## Reachable, and the ladders they form

| family | rungs |
| --- | --- |
| GLM | `glm-5` → `glm-5.1` → `glm-5.2` |
| MiniMax | `minimax-m2.5` → `m2.7` → `m3` |
| Kimi | `kimi-k2.5` → `k2.6` → `k3` |
| Qwen | `qwen3.5-plus` → `qwen3.6-plus` |
| DeepSeek | `deepseek-v4-flash` → `v4-pro` |
| free | `ling-3.0-flash-fin-free`, `nemotron-3-ultra-free`, `nemotron-3.5-lightning-free`, `laguna-s-2.1-free`, `big-pickle`, `mimo-v2.5-free` |

Five within-family ladders under one key. That is the instrument the open question needs,
which is not "does the skill help" but **over what capability band does it help**: the
local work established that nothing helps a model which cannot emit a tool call, and run
28 established that nothing helps a model already capable enough to finish the task.

## Six things that will corrupt a run if you do not know them

### 1. Half the reachable models return no `content` at all

Twelve of the eighteen returned `null` or empty `content` on a short prompt, with the
answer in **`message.reasoning`** instead. `app/runner.py` used to read `content` alone, so
those cases recorded as "said nothing" with status `ok` and graded as a zero.

`_answer_of` now falls back to `reasoning` and records **`case_result.output_source`** as
`content`, `reasoning` or `empty`. The source is recorded rather than hidden, because
grading a reasoning trace is not the same as grading an answer: a trace may consider and
reject the trap before settling on the right command, so a `regex_forbidden` check can fire
on a model that got it right. Anything comparing the two has to be able to see which is
which.

### 2. `options{}` was never applied, on either server

Generation parameters used to be sent in an Ollama-native `options` object. The
OpenAI-compatible `/v1` endpoint ignores it. Measured both ways with
`options.num_predict = 8`:

| server | completion tokens returned |
| --- | ---: |
| Ollama `/v1` | 80 |
| Zen `/v1` | 172 |

So **no chat-lane run has ever applied the temperature its spec asked for**, including the
+29.3 pt baseline; every one used the server default. Both arms of a paired run were
equally affected, so past comparisons stand on their own terms, but a run made after this
fix is not comparable to one made before it.

### 3. `max_tokens` is honoured inconsistently, and a small cap is worse than no cap

`ling` stopped at exactly the 24 requested. `big-pickle` returned 257 against a request for
8. Treat the cap as advisory.

More importantly, the reasoning models above spend their budget *before* producing any
content. At `max_tokens: 8` only 6 of 59 models produced text. Re-probing the 12
silent ones at 512 turned 9 of them into real answers, while `kimi-k2.5` and `k2.6` still
returned empty after burning all 531 tokens on reasoning and `mimo-v2.5-free` errored.

Under a plan metered in **requests**, a truncated answer is the worst outcome available: it
spends a whole unit of the scarce resource and returns nothing gradeable. The runner
therefore sends `max_tokens` only when a spec asks for one. The right default is an open
question rather than an oversight.

### 4. An unreachable model returns a bare 500

Not a 402, not a 403. `{"error": "Internal server error"}`, indistinguishable from a real
outage, on 38 of 59 models. `_status_of` classifies a provider 5xx as **`unavailable`**
rather than `error`, so an unconfigured model cannot be read as one that failed the task.
**Filter `unavailable` out before scoring.**

Only one model gave an honest message: `kimi-k2.6` returned 401 `Model is disabled`.

### 5. Model ids carry no tag

`_resolve` appends `:latest` for Ollama. A gateway id is a plain string, and
`glm-5.2:latest` does not exist. The tag is applied only when the chat base *is* the Ollama
base. The agentic lane still resolves against Ollama, because `pi` runs on a VM talking to
the local server.

### 6. The endpoint 403s Python-urllib's default User-Agent

Any named agent is accepted, so identify yourself rather than impersonating a browser.
`httpx`, which the runner uses, sends its own and is unaffected: verified 200 from inside
the container. Same family as the Anubis block on `wiki.archlinux.org` already noted in
[CLAUDE.md](../CLAUDE.md), where the request is fine and the client string is what gets
refused.

## Requests are the scarce resource, not tokens

Go meters **requests per 5-hour window**, from 110,000 (Kimi K3) down to 1,350 (Grok 4.6).
That inverts the usual instinct: tokens are close to free and requests are what runs out.

- The **chat lane is one request per case.** A 124-case paired run is 124 requests and fits
  inside every published cap.
- The **agentic lane is many requests per case**, and is what will actually meet a ceiling.
  We cannot yet say how many, because the runner invokes `pi` without `--mode json` and has
  never recorded turns per case. That is a budgeting prerequisite, not only a diagnostic
  one.

Rate limits are real and easy to trip: repeated probing of the free models returned
`429 Rate limit exceeded` within one session.

## The account settings do nothing here

Three toggles were flipped on and then off again, with a full snapshot at each step:

| setting | effect on listing | effect on reachability |
| --- | --- | --- |
| allow models that train on request data | none | none |
| allow models hosted in China | none | none |
| use available balance after usage limits | none | none |

Only the **per-model enable toggles** moved anything, and they moved it a long way: 20
models listed became 66. The three above sit under a heading reading "control which
providers are used for **routing**", which is the likely explanation: they govern how the
CLI picks a model when you have not named one, and naming a model explicitly over the API
leaves nothing to route. Unconfirmed.

## Key handling, because the key is all-or-nothing

There is no way to scope a Zen key, so blast radius is managed at our end.

- **The key never leaves the host.** It lives in `skillbench/secrets/zen.env`, mode 600,
  in a directory gitignored since before it existed.
- **Environment only**, via `SB_CHAT_API_KEY`. Never a spec field, never a command-line
  argument, so it cannot reach a bench file, the results database or the process table.
- **Never onto a test VM.** The agentic lane runs `pi` *on* a disposable machine with
  NOPASSWD sudo, under the control of the agent being measured. When that lane goes cloud,
  put a header-injecting relay on the host bound to `192.168.122.1` and point the VM at it,
  mirroring how the VMs already reach Ollama. The VM then holds nothing worth stealing.
- The runner records the request **body**, not headers, so the key does not reach
  `case_result.request` or the tracked export.

## Open questions

1. **Does Go cover API calls, or do they draw on pay-as-you-go balance?** Unresolved, and
   it matters: the flat cap is the reason Go was chosen over PAYG for an agent that can
   loop. No quota, plan or credit headers are returned on a successful response. Watching
   whether the account balance moves during a run is the cheapest available answer.
2. **Why does every Western-lab model return 500?** All OpenAI, Anthropic, Google and xAI
   ids fail while every Chinese-lab and open model works on the same key. Not explained by
   any of the three settings. BYOK for those providers is the leading hypothesis.
3. **Which ids do the Go page's models use?** `glm-5.3`, `glm-5.3-flash`, `qwen3.8-flash`,
   `qwen3.7-plus`, `longcat-2.0` and `omen-alpha` all return "not supported", which may
   mean the id is wrong rather than the model unavailable.
