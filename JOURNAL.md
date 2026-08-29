# Journal — handoff

Last updated: 2026-08-29

## Session of 2026-08-29 — the agentic lane

The Skill Bench now grades what an agent **does** on a real machine, not only what a model
says. This was the top item on "what's left" and it is built, running and documented.

### 1. How it works

A bench declares `lane: agentic`. Each case then: acquires a VM from a pool, restores the
paths the bench declares, applies a `seed:` (the breakage), runs `pi --print --skill <dir>`
in a **tmux window**, and evaluates the task's `post:` block over ssh.

Two graders, kept apart in the UI on purpose — QUALITY (transcript) and STATE (the VM).
Collapsing them would hide a model that describes the right edit and never makes it.

`omarchy-agentic-config` is the first bench: add a keybinding, switch a theme, configure a
monitor. Every task also asserts `pacman -Qkk omarchy` reports **0 altered files**, which
is a hard statement that the agent stayed out of `/usr/share/omarchy` — the exact place
Omarchy-3-era advice sends it. A chat bench can only ask whether a model *mentions* the
right directory.

### 2. What the paired runs showed: no signal, because the bench is SATURATED

Runs 14 and 15, `devstral-small-2:24b`, `none` vs `skill:omarchy`, **3 repeats**, the
Omarchy bench against its new control:

| bench | none | skill | delta |
| --- | ---: | ---: | ---: |
| `omarchy-agentic-config` | **24/24 = 1.000** | 22/24 = 0.917 | −8.3 pt |
| `linux-agentic-triage` (control) | 17/18 = 0.944 | 16/18 = 0.889 | −5.5 pt |

**The bare model already scores 100% on the Omarchy bench.** There is no headroom for a
skill to help, so this bench cannot measure skill efficacy against an agent this capable.
Both deltas are slightly negative and the control moved nearly as far as the Omarchy bench
(−5.5 vs −8.3) — which, by the rule the controls exist to enforce, means these numbers are
not measuring the skill at all.

The tasks need to be harder before this bench discriminates. Writing tasks that a good
agent fails without the skill is the actual open problem; three tasks a competent agent
does by default measure nothing.

**The one clear, reproducible effect is cost.** Mean case latency:

| bench | none | skill | |
| --- | ---: | ---: | --- |
| `omarchy-agentic-config` | 364 s | 714 s | 2.0× |
| `linux-agentic-triage` | 33 s | 146 s | 4.5× |

It shows up in the **control** too, so it is the cost of putting ~3.1k tokens into an agent
loop, not anything Omarchy-specific. Two of 36 cases hit the 600 s timeout — one in each
variant, so that part is not attributable to the skill.

### 2a. The first paired run was wrong, and the control is what caught it

Runs 12/13 reported +12.5 pt / −5.6 pt. **Those numbers were invalid** and are retained
here only as a lesson. Two grader bugs:

- **Tilde paths were shell-quoted.** `shlex.quote("~/x")` gives `'~/x'`, which the shell
  never expands, so `test -e` looked for a directory literally named `~`. The asymmetry is
  what made it dangerous: `file_exists`/`file_contains` failed closed and looked like agent
  failure, while **`file_absent` passed trivially and read as green**. An assertion that
  cannot fail is the one thing a grader must never have.
- **`pgrep -f bench-runaway-marker` matched its own shell**, whose command line contains
  the pattern, so `command_fails` could never pass. Fixed with the `[b]ench-…` bracket.

The tell was the control scoring **exactly 0.500 on every task in both variants** — a
constant, not a measurement. A control that cannot move is a broken control, and catching
that on its first outing is precisely what it is for. Three regression tests now cover it,
including one that scans every shipped bench for post paths that cannot resolve.

### 3. The lesson that changed the bench: good agents do not narrate

devstral scored **3/3 on the monitor task while its entire transcript was "Task
completed."** The chat lane's `checks:` were therefore scoring *verbosity* and marking the
best-performing agent down for being terse. Forbidden-pattern checks are no better — a
silent agent passes them all and reads as 100%.

So the agentic bench now carries **no transcript checks at all**. In this lane the machine
is the measurement.

### 4. Four things that cost real time, all now written down in CLAUDE.md

- **libvirt rejects every new forwarded connection into `192.168.122.0/24`.** A bridged
  container cannot reach the test VMs, and no ufw rule can override it — in nftables an
  `accept` in one base chain does not stop another base chain rejecting, and only
  `reject`/`drop` are terminal. The bench moved to `network_mode: host`, which also
  **deleted** the old pinned-subnet ufw rule for Ollama. One less invisible host-level
  dependency, in a repo where that class of trap has now bitten three times.
- **`OMARCHY_PATH` comes from `~/.bashrc`**, so a non-interactive ssh has it unset and every
  `omarchy` subcommand fails with `find: '/themes/'`. Everything on the VM runs under
  `bash -l`. It matters twice: a tmux window inherits the *tmux server's* environment, and
  that server is a systemd user unit with no profile sourced — without this the **agent**
  is the thing running without `OMARCHY_PATH`.
- **Omarchy 4's lock cannot be released headlessly.** It is an `ext-session-lock` surface
  drawn by `omarchy-shell` (`hyprlock` is not installed); the IPC has `lock()` but
  deliberately no `unlock()`, and it outlives its client. Recovery was typing the password
  through `virsh send-key`. Prevention is the only fix.
- **`hyprctl dispatch` takes Lua on 0.56**: `hl.dsp.exec_cmd("...")`, not `dispatch exec ...`.

### 5. Golden disk images replaced snapshots

`/var/lib/libvirt/images` is btrfs with no NOCOW flag, so `cp --reflink=always` shares
extents: **reset 1 s, boot to ssh 14 s, full cycle ~30 s**, verified with a marker file,
against minutes for an ISO rebuild. `tools/golden-test-vm.sh save|reset|status`.

Note `virsh shutdown` (ACPI) is ignored by these VMs; use `ssh <vm> 'sudo systemctl poweroff'`.

### 6. The VMs are now provisioned, and mirrored to their consoles

`tools/provision-bench-vm.sh` makes a VM a bench target, idempotently: SDDM autologin,
never lock/blank/suspend, a systemd **user unit** holding a long-lived tmux session, a
second unit attaching a `foot` terminal to it **read-only** on the console, and pi pointed
at the host's Ollama. `tools/install-bench-key.sh` gives the bench its **own** ssh key —
never the operator's — gitignored under `skillbench/secrets/`.

Read-only is load-bearing both ways: a watcher cannot type into a running case, and the
runner therefore must never use `tmux send-keys` (tmux refuses it outright). Launching each
case *as* a window is the supported path.

### 7. Isolation: what it is, and what it is not

Before every case the VM is restored from a tar of the paths the bench declares. **Anything
outside those paths persists.** Verified working — an agent invented
`~/.config/omarchy/keybinds.conf` and the next case's restore removed it.

It is not a disk rollback, deliberately: the container runs `cap_drop: ALL`,
`no-new-privileges` and has no libvirt socket, and handing it the hypervisor would trade a
real security property for convenience. The disk reset stays an operator action between
runs.

## What's left

### 1. Make the agentic bench hard enough to measure anything

The lane works, the control exists, and the graders are fixed. The blocker now is task
difficulty: `devstral-small-2:24b` scores **24/24 bare** on `omarchy-agentic-config`, so
there is no headroom for a skill to show up in. Tasks are needed that a capable agent gets
WRONG without the skill — the Omarchy-3-vs-4 tree split is the right seam (that is what
`pacman -Qkk` already tests), but the current three are too easy.

Open alongside that: whether `skill:omarchy-full` (~6.6k tokens) is even loadable by a 24B
model in an agentic loop. One earlier case ran 199 s and returned an empty transcript
having done nothing.

### 2. Finish auditing 28 records  (the oldest real loose end)

Unchanged from before. `wayland-compat` (12) and `network` (16) gap-fill records are
harvested but never audited; their audit agents died on API streaming errors. They are
flagged `gapfill-unaudited` and warn in both `ask.py` and the generated markdown.

To close: edit `GAP_CATEGORIES` in [research/tools/gapfill-workflow.js](research/tools/gapfill-workflow.js)
down to those two categories, run it, then:

```sh
cd research
python3 tools/merge_gapfill.py raw/gapfill-result.json
python3 tools/build_db.py
```

**Do not use `resumeFromRunId` for this.** It was tried and re-ran completed work.

### 3. Stale `cause` fields on first-pass corrected records  (known, mitigated)

Roughly 130 `corrected` records may still carry a `cause` the auditor disproved; the first
harvest's audits rewrote only `fix`. The audit note prints directly beneath the cause with a
warning, so a reader is never misled, but a re-audit pass would be a genuine improvement.

### 4. Optional / not started

- `opinionated-omarchy/` is still empty, held open by a `.gitkeep`. Settled: this is where
  the skill goes — the one that turns the corpus into something an agent can consume.
  Nothing written there yet.
- Now that the VMs exist and can be reset in a second, the corpus could be spot-checked
  against a real install. Nobody has done any of that.
- `research/` root holds ~17 loose Hyprland wiki pages. Not corpus, no tooling reads them.
  Left in place deliberately.

## Session of 2026-08-28/29 — the Skill Bench landed

Two things happened: the lab's skill-efficacy data was brought into this repo, and a
dedicated bench container was built here to extend it.

### 1. This workstation is `ohmy-omarchy`, and that changes what is easy

Worth stating plainly because it was not obvious: the dev box **is** the lab's local LLM
endpoint. RTX 3090, Ollama on `0.0.0.0:11434` with eleven models — including `qwen2.5`,
the exact model every nexus1 Omarchy measurement was taken on. Docker 29.7.2 was already
installed and running.

So the bench needs no LiteLLM, no API key, no cloud, and no lab round-trip. Routing
through nexus1 would mean ohmy-omarchy → nexus1 → ohmy-omarchy, since nexus1's LiteLLM
points back here.

### 2. The nexus1 baseline is recorded — [research/bench/](research/bench/)

911 graded cases, ten models, twelve runs, pulled from the lab's Postgres with the bench
specs and skill provenance alongside. The headline: **the Omarchy skill lifts
Omarchy-specific tasks +29.3 pt on average and the general-Linux control tasks −2.3 pt.**
That gap is the whole argument — a skill that merely made answers longer would lift both.

`omarchy/SKILL.md` here is **byte-identical** to what nexus1 benched (sha `a8d88cf…`), so
those numbers are a baseline to reproduce, not merely a reference. `diagnose-crash` is
**not** identical (5710 bytes here vs a 4173-byte asset there) — treat its figures as
indicative only.

It is in `research/bench/`, not `research/docs/`, because
[`build_db.py:167`](research/tools/build_db.py) unlinks every `*.md` in `docs/` before
regenerating. A hand-written page there survives until the next corpus build.

### 3. [skillbench/](skillbench/) — a bench container in this repo

Omarchy-only port of the lab's Skill Bench: one container, local Ollama, SQLite,
`http://127.0.0.1:8878`. Dropped as unnecessary — LiteLLM, Postgres, Authelia, budget
guard, cost projection, model registry, the paid lane, and 14 non-Omarchy benches.

Two deliberate improvements over the original, both methodology rather than features:

- **Skills are bundles.** nexus1 could inject only a single `SKILL.md`, so instructions in
  a topic guide could never lift a score — its own backlog called every measured lift *"a
  floor, not the real-harness number"*. Here `skill:omarchy` (body only, comparable with
  the baseline) and `skill:omarchy-full` (all 7 files) both ship, so the difference is
  measurable for the first time.
- **The four general-Linux benches are flagged `control: true`** and labelled in the UI,
  so the null case is visible rather than implicit.

Also fixed by construction, both open findings in nexus1's own audit of its bench: runs
orphaned by a restart are reconciled at startup instead of wedging at `running`, and
`/readyz` actually probes the DB and Ollama rather than only proving the HTTP process is
alive.

**Verified working, against the baseline.** 27 unit tests pass (`skillbench/tests/run.sh`).
The ten-model replication of nexus1's run 33 on `omarchy-monitor-config`:

| | nexus1 | here |
| --- | ---: | ---: |
| bare | 0.529 | 0.729 |
| skill | 0.800 | 0.971 |
| **lift** | **+27.1 pt** | **+24.3 pt** |
| models improving | 10/10 | 10/10 |
| prompt tokens | 3266 | 3244 |

The lift reproduces and the token counts are near-identical — the skill body is the same
and injected the same way. Absolute levels are higher on both sides, most likely the
serving path (LiteLLM vs direct Ollama) plus weights moving under the same tags.

**The lesson that came out of it:** benches and skills are sha-pinned, but **model weights
cannot be pinned**. Trust deltas within a run; distrust absolute scores across runs
separated by time. Written up in both READMEs.

### 4. The firewall gotcha, again, in a new costume

Containers could not reach Ollama. Cause: Omarchy's `ufw` is default-deny incoming and
Docker manages only forwarding — **the same family as the `virbr0` DHCP gap**, which is
now written up as one pattern in [CLAUDE.md](CLAUDE.md) rather than two incidents.

The subtlety worth keeping: an interface-scoped rule on `docker0` does **not** work,
because Compose puts the container on its own generated bridge. `compose.yaml` therefore
pins the network to `172.28.7.0/24` so the rule can name it.

### 5. Housekeeping

`omarchy-old/` deleted — its purpose was never recorded and could not be reconstructed.
`opinionated-omarchy/` is confirmed as the destination for the skill this repo is building.

## Where the references are

| What | Where |
| --- | --- |
| Corpus design, schema, trust model | [research/README.md](research/README.md) |
| The 457 records (source of truth) | `research/data/problems.jsonl` |
| Generated per-category reading | `research/docs/*.md` |
| Search / build / ingest tooling | `research/tools/` |
| Deep-research report (13 verified findings, 12 refuted folk fixes) | `research/raw/deep-research-report.json` |
| Raw workflow output, kept for provenance | `research/raw/harvest-result.json`, `research/raw/gapfill-result.json` |
| Gaps the auditors named | `research/raw/gapfill-todo.json` |
| Per-category harvest/audit counts | `research/raw/harvest-stats.json` |
| Test VM build / viewer scripts | `tools/make-test-vm.sh`, `tools/view-test-vms.sh` |
| Test VM credentials, VNC ports, ufw rules | [CLAUDE.md](CLAUDE.md) → "Test VMs" |

The refuted list in the deep-research report is worth a read on its own — it is mostly
widely repeated folk fixes that primary sources actually contradict.

## Gotchas that cost time

Full list in [CLAUDE.md](CLAUDE.md). The ones that bit hardest:

- **`basecamp/omarchy`'s default branch is `quattro`, not `master`.** `master` is still
  the Omarchy 3 tree and several raw URLs 404 against it.
- **Omarchy 4 is pacman-packaged at `/usr/share/omarchy`** — not a git checkout in
  `~/.local/share/omarchy`. Most stale advice online assumes the old layout.
- **`wiki.archlinux.org` is behind Anubis anti-bot**; `WebFetch` gets "Access Denied".
  Use `index.php?title=X&action=raw` or `rest.php/v1/page/X`.

From the VM work, and both cost real time:

- **Omarchy's host `ufw` silently blocks libvirt DHCP.** It runs default-deny with `INPUT`
  policy `DROP`, and libvirt's nftables table only manages the `forward` hook — so nothing
  opens port 67 and guests retry DHCP forever with no lease and no IP. What makes it
  genuinely confusing is that it only shows up *after* a completely successful install: the
  5.9 GB ISO carries an offline package set, so the install never needs the network and the
  machine looks fine right up until it boots. Fix is three `virbr0`-scoped rules in
  [CLAUDE.md](CLAUDE.md).
- **`/usr/share/omarchy/version` is branding, not a version.** It reads `4.0.0.alpha` on the
  workstation *and* in a 4.0.1 VM. The number that means anything is `pacman -Q omarchy`.
  A version comparison built on that file will be wrong and look authoritative.
