# Journal — handoff

Last updated: 2026-08-29

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

## Where we stopped

The repo now lives on the machine it is about. It was cloned to
`/home/techluddite/Projects/opinionated-omarchy` on an **Omarchy 4 workstation**, and two
sessions of work happened there. Read [CLAUDE.md](CLAUDE.md) first — the environment and
Test VM sections were both rewritten and are current.

**Branch state: resolved.** Those two commits went in through PR #1 and
`claude/greenfield-repo-setup-l5fzae` — the repo's default branch on GitHub, there is no
`main` or `master` — is clean and in sync with origin.

```
b6ddc60  Merge pull request #1 from TechLuddite/chore/linux-native-toolchain
d4291dd  Add two unattended Omarchy test VMs, with VNC consoles
69f632f  Convert repo from Windows to Linux-native
8be248c  Initial import: Omarchy skills and troubleshooting corpus
```

### 1. The repo was converted from Windows to Linux-native

The project used to be developed on Windows 11. It is not any more, and the concessions
that required are gone: `python` → `python3` in 28 places, the four `research/tools/*.py`
scripts made executable (they already carried a `python3` shebang but were mode 644, so it
was inert), and the comments citing a cp1252 console replaced. One of those comments was
already false — it claimed ASCII-only output directly above code printing record text
containing arrows, box drawing and a Nerd Font glyph.

`ask.py` also emitted ANSI unconditionally, so redirecting to a file embedded escape
codes. It now gates on `stdout.isatty()` and honours `NO_COLOR` / `TERM=dumb`. The `!!` and
`~~` prefixes already carried the warnings, so uncoloured output loses emphasis but never a
risk marker.

**Kept deliberately, with better reasoning:** `eol=lf` and the explicit `newline="\n"` pins.
They are not Windows compatibility — they are what stops a rebuild of the tracked,
fully-regenerated `research/docs/` from producing a 1.5 MB whitespace diff. `research/raw/**`
stays `-text`; several of those files legitimately carry CRLF exactly as harvested.

### 2. Two test VMs exist and work

`opinionated-omarchy-test1` and `-test2`: Omarchy 4.0.1, libvirt/KVM, NAT on `virbr0`,
VNC consoles on `127.0.0.1:5901` / `:5902`. Full details, credentials and gotchas are in
[CLAUDE.md](CLAUDE.md) under "Test VMs".

They install **unattended** — the Omarchy ISO supports a `cidata` drive (cloud-init
NoCloud), and `omarchy-cidata-load` on the ISO skips the `gum` configurator when it finds
one. `tools/make-test-vm.sh` builds that drive and defines the domain, so rebuilding is one
command. Rebuild through the script; the archinstall schema is unforgiving and the sizes are
in bytes.

This is what changes the corpus's possibilities: fixes can now be *checked* rather than only
cited. It does **not** change the trust model — `audit_status` records verification against
sources, and one VM agreeing is not a source confirming. Say so explicitly in a record if
you validate it live.

### 3. Housekeeping done along the way

- An ed25519 keypair was generated at `~/.ssh/id_ed25519` — there was **no `~/.ssh` at all**
  on this machine before. Its public half is installed on both test VMs.
- The virtualization stack was installed via `omarchy pkg add` (a thin `pacman -S --needed`
  with no `-y`, so no partial-upgrade risk), `libvirtd`/`virtlogd` enabled, the `default`
  network started and set to autostart, and the user added to `libvirt`/`kvm`.
- Three `ufw` rules were added on the **host**, scoped to `virbr0` only. Without them the
  VMs get no network at all — see the gotchas below.

## What's left

### 1. The agentic lane — the bench's real payoff  (decided, not built)

The current bench grades what a model **says**. The agreed next block is grading what it
**does**: drive `omarchy agent` inside the test VMs and assert on the machine's end state.
Groundwork already surveyed:

- **`omarchy-agent` is the abstraction.** `/usr/share/omarchy/bin/omarchy-default-agent`
  supports nine harnesses (`pi, omp, opencode, claude, codex, grok, gemini, copilot,
  crush`), and `omarchy-agent` already encodes each one's non-interactive flags.
  `--inline` execs directly instead of spawning a terminal, which is what headless driving
  needs. The harness becomes a bench dimension, exactly as models are today.
- **`pi --skill <path>` loads a file *or a directory*.** The multi-file ceiling disappears
  entirely in agentic mode — pi loads the real bundle the way the real harness does.
  `pi --print --mode json --no-session` is non-interactive with structured output.
- **pi reaches local Ollama** via a custom provider in `~/.pi/agent/models.json`
  (`api: openai-completions`, dummy `apiKey`). Ollama is the documented example. Set
  `compat.supportsDeveloperRole: false` or pi sends a role the server rejects.
- Both VMs already have `pi`, `opencode`, `claude`, `codex`, `crush` and `mise`.
- **Decided: snapshot and revert per case**, so cases cannot contaminate each other.
- **Prove first:** these domains are UEFI, and libvirt has historically refused *internal*
  snapshots on pflash domains. If that bites, go external or disk-only. The disks are
  qcow2, so snapshots are available in principle; no snapshots exist yet.
- **Expect the matrix to collapse.** Chat mode is ~7s/case; agentic is minutes plus revert,
  with concurrency 2. Agentic runs must be narrow by design.
- The VMs will need Ollama reachable at `192.168.122.1:11434` — a fourth `virbr0`-scoped
  ufw rule, same shape as the three already documented.
- `post:` is already reserved in the bench schema, so this needs no migration.

### 2. The lab host is reachable, and untouched

`skywalker@techluddite-nexus1.opsvibe.systems` (172.20.20.127). **Key auth works** from this
workstation — `ssh skywalker@techluddite-nexus1.opsvibe.systems` connects with no prompt,
verified under `BatchMode=yes`, so nothing interactive is hiding in the path.

The workstation's public key was appended to `~/.ssh/authorized_keys` there by hand. Note
the direction if this comes up again: `ssh-copy-id` copies a *local* key to a *remote* host,
so it must run **on the workstation**, not on the lab. Running it on the lab makes it look
for a key in the lab's own `~/.ssh` and fail.

Deliberately unexplored: connection and one `ls ~` and nothing more. That home directory has
`workspace/`, `.claude/`, `.claude.json`, `.docker/` and `.git-credentials` in it, so
whatever the lab is for, it is already set up — do not assume it is a blank machine.

### 3. Finish auditing 28 records  (the oldest real loose end)

`wayland-compat` (12) and `network` (16) gap-fill records are harvested but never audited —
their two audit agents died on API streaming errors. They are flagged `gapfill-unaudited`
and warn in both `ask.py` and the generated markdown, so nothing is silently untrustworthy;
they just haven't been checked.

To close: edit `GAP_CATEGORIES` in [research/tools/gapfill-workflow.js](research/tools/gapfill-workflow.js)
down to those two categories, run it, then:

```sh
cd research
python3 tools/merge_gapfill.py raw/gapfill-result.json
python3 tools/build_db.py
```

**Do not use `resumeFromRunId` for this.** It was tried and did not cleanly replay only the
failed agents — stalled-agent retries re-ran completed work and consumed budget, and it had
to be killed. Editing the category list is cheaper and predictable.

### 4. Stale `cause` fields on first-pass corrected records  (known, mitigated)

The first harvest's audits rewrote only `fix`, so roughly 130 `corrected` records may still
carry a `cause` the auditor disproved. The second pass added `corrected_cause` (20 causes
replaced), but first-pass records were not revisited. The audit note prints directly beneath
the cause everywhere, with a warning, so a reader is never misled — but a re-audit pass over
first-pass records would be a genuine improvement.

### 5. Optional / not started

- `opinionated-omarchy/` at the root is still empty, held open by a `.gitkeep`. **Settled
  2026-08-28: this is where the skill goes** — the one that turns the corpus into something
  an agent can consume. Still several steps out, nothing written there yet.
- `omarchy-old/` **deleted 2026-08-28.** Its purpose was never recorded and nobody could
  reconstruct it, so it was an empty directory kept alive by a `.gitkeep` for no stated
  reason.
- Nothing turns the corpus into an actual Claude skill yet. Still the obvious next step if
  the goal is agent-consumable troubleshooting: a `SKILL.md` telling an agent to query
  `research/tools/ask.py` by symptom.
- Now that the VMs exist, the corpus could be spot-checked against a real install. Nobody
  has done any of that yet.
- `research/` root holds ~17 loose Hyprland wiki pages (`binds.md`, `anim.md`, `lua.html`,
  `hyprctl.md`, `hc.cpp`, …). **Not** part of the corpus and no tooling reads them. Left in
  place deliberately; could move to a `reference/` subfolder.

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
