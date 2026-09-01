# Journal — handoff

Last updated: 2026-09-01

## Session of 2026-09-01 — the last unaudited records, and the Windows remnants

Item 2 of "What's left" is closed, and the repo no longer carries anything from its
Windows era.

### 1. The 28 unaudited records are audited

`wayland-compat` (12) and `network` (16) had been harvested but never reviewed since the
gap-fill pass, whose audit agents died on API streaming errors. Four auditors, batched by
category, returned **28/28 verdicts**:

| | `ok` | `corrected` | `reject` |
| --- | ---: | ---: | ---: |
| `wayland-compat` | 5 | 7 | 0 |
| `network` | 7 | 8 | 1 |
| **total** | **12** | **15** | **1** |

27 of 28 verdicts are `confidence: high`. Seven `corrected` records also had their `cause`
rewritten and stamped `cause_reconciled: 2026-09-01`, so the corpus now carries 29 stamps
across two dates. The corpus is **456 records**, `ok` 240 / `corrected` 212 / `unaudited` 4.

**The one rejection is the most interesting result.**
`usb-tethering-renamed-wwan-networkmanager-ignores` described a real kernel regression —
the auditor confirmed commit `67d1a89` "rndis_host: Flag RNDIS modems as WWAN devices" and
verified by fetching `drivers/net/usb/rndis_host.c` at each stable tag that
`wwan_rndis_info` appears in exactly the versions the record named. **But the patch was
reverted**, and is absent from v6.15, v6.17 and master. The record presented a six-week
2025 regression as a live problem at `frequency: common`, on a workstation running 7.1.8.
Its own cited thread said so at post #60. Separately the auditor traced NetworkManager's
source to show the record's headline fix *cannot* work even on an affected kernel, because
`nm-wwan-factory.c` unconditionally sets `*out_ignore = TRUE`, so no device object is ever
created for `nmcli` to act on.

That is the `fabricated precision` failure mode from the 2026-08-30 session showing up
once more, in its most convincing costume yet: every specific in the cause was checkable
and correct, and the conclusion was still wrong because nobody checked whether the story
had ended.

### 2. Two blockers in that path, both fixed first

Neither would have failed loudly.

- **`research/tools/gapfill-workflow.js:15` pointed at a Windows path.** `ROOT` was
  `c:/Projects/Personal/skills/omarchy/research`, which agents use to read the corpus off
  disk. Every gap-fill and audit agent would have failed on the read.
- **`merge_gapfill.py` would have destroyed the `cause_reconciled` work.** Its writer
  projects each record onto `FIELDS`, and the 2026-08-30 schema change never added the
  field there — so a merge would have **stripped all 22 stamps**. It also rewrote causes
  without stamping them, which would have made `build_db.py` and `ask.py` print *"The Cause
  above was not rewritten and may still contain the error described"* about causes it had
  just replaced. Both fixed: the field is in `FIELDS`, and `apply_verdict` stamps
  `date.today()` whenever it applies a `corrected_cause`.

Both are written up in full in
[writeups/2026-09-01-merge-gapfill-silent-defects.md](writeups/2026-09-01-merge-gapfill-silent-defects.md),
including the two follow-ups they leave open: the corpus tooling has no tests at all, and
adding a schema field still has no checklist covering its four consumers.

The second was caught by dry-running the merge against a **copy** of the corpus with
synthetic verdicts before letting it near the real file — worth doing again, because the
failure is silent and the evidence it destroys is the evidence of honesty.

That dry run also confirmed the property that actually makes this merge safe: **merge
iterates every record in the audited category, not just the targeted ones.** Records with
no verdict are preserved, so scoping the verdict set is what protects the 33 already-audited
`wayland-compat` records. The workflow filters verdicts to the assigned slugs for the same
reason.

### 3. The Windows era is gone

The repo was converted from Windows earlier; two things survived that conversion.

- The `gapfill-workflow.js` path above — the only functional remnant left anywhere.
- **`CLAUDE.md`'s "previously developed on Windows" paragraph.** The LF and UTF-8 rules it
  introduced are load-bearing and stay, but they now stand on their own merits instead of
  being framed as inherited concessions.

**Two things that look like Windows remnants are not, and should be left alone.**

- `research/{lua,u55,wr054}.txt` carry CRLF. That is deliberate: `.gitattributes` pins
  `research/*.txt -text` so downloaded wiki pages keep their harvested bytes. Provenance,
  not drift.
- Every other "Windows" hit is **corpus content** — dual-boot Bluetooth link keys, NTFS,
  "works on Windows but not Arch" — or Hyprland *windows* in `wr054.txt`'s window rules.
  Stripping those would delete real records.

## Session of 2026-08-30 — catching the journal up, and starting the re-audit

Housekeeping first, then item 3 of "What's left". Three things had drifted out of the
written record since the 29th.

### 1. Runs 16 and 17 happened and were never written down

Both on `muse-glimmer:30b`, a model the agentic lane had not been tried with before.

Run 16 (`linux-boot-partition-full`, chat lane) is unremarkable and that is the point:
**1.000 in both variants**, 91 prompt tokens bare against 3197 with the skill. A control
behaving exactly as a control should.

Run 17 (`omarchy-agentic-config`, agentic lane) reports 0.333 bare against 0.667 with the
skill, and **that spread is entirely timeout attrition, not skill signal**. Every case that
did not error passed every assertion; the run's STATE score is 1.000 in both variants. The
whole difference is which cases hit the wall:

| task | none | skill:omarchy |
| --- | --- | --- |
| `binding-user-tree` | ok, 176 s | ok, 251 s |
| `monitor-persist` | **agent exceeded 600s** | **agent exceeded 600s** |
| `theme-switch` | **agent exceeded 600s** | ok, 847 s |

So the bench is still saturated exactly as the 29th recorded it — this adds only that a
30B model does not fit the current `agent_timeout: 600`. Do not read run 17 as a lift.

### 2. A grader question run 17 raised, still open

**Post assertions are evaluated on timed-out cases too, and they passed there.** Both
`monitor-persist` cases errored on the timeout, yet each reports `post 3/3` and contributes
`state = 1.0`. That is why the run shows STATE 1.000 alongside a success rate of 0.333.

This may well be correct — an agent can finish the edit and then burn the remaining budget
without exiting, and refusing to score work it demonstrably did would be its own distortion.
But it means STATE currently averages over cases the runner classified as failures, so STATE
and `success` can disagree without either being wrong, and a reader comparing them will
assume one is broken. **Decide which it is before the next paired run**, and whichever way it
goes, make the UI say so. This is the same class of thing the control caught in run 12/13:
not a wrong number, but a number whose meaning is not written down.

### 3. Smaller drift

- **The suite is 43 tests, not 39.** `CLAUDE.md` still advertised 39; corrected there. The
  "27 unit tests" in the 08-28/29 entry below is left alone — it was true on the day, and
  a journal entry is a dated record, not a live figure.
- **`skillbench/app/ui.py` had an uncommitted change** moving the run-history table below
  the fold, so the run you just launched is not pushed off screen by the history. Committed
  as-is; it was finished, not half-done.

### 4. Item 3 of "What's left" is closed: 22 stale causes, not 130

The backlog said "roughly 130 `corrected` records may still carry a `cause` the auditor
disproved". That number was never a count of defects — it was the size of the population
nobody had looked at. All 130 have now been read, and **22 actually had a cause their own
audit note contradicts.** The other 108 are fine: their notes open with "the diagnosis is
right", "cause verified exactly", "the mechanism is real", and go on to object to the
*fix*, which the first-pass audit had already rewritten.

**Scoping it took provenance, not keywords.** The README records that the second pass's
auditors could return a `corrected_cause` while the first pass's could not, so the
affected set is exactly the `corrected` records whose audit came from the first pass.
Reconstructing that from `raw/harvest-result.json` and `raw/gapfill-result.json` —
`apps-services` was the only category re-audited in pass 2, everything else in
`gapfill-result` audits the *new* records — yields **130 records, and independently
reproduces the README's "20 causes replaced" figure**, which is what confirmed the
mapping was right. Keyword heuristics on the notes gave a union of 123 and would have
been both wrong and unfalsifiable.

**The rewrites needed no new source work.** The auditor had already done it; the first
pass simply had no field to put the result in. Each new cause is written from its own
note. Two failure modes dominate, and both are worth recognising again elsewhere:

- **The Omarchy 3 → 4 tree split.** Causes asserting a git checkout at
  `~/.local/share/omarchy` that `omarchy update` hard-syncs, when Omarchy 4 is
  pacman-owned at `/usr/share/omarchy` and the reason edits vanish is a package upgrade.
  Same trap the agentic bench's `pacman -Qkk` assertion exists to catch.
- **Fabricated precision.** A confident specific the source does not support: a
  "430-590 vs 595+" NVIDIA driver boundary that is really open-vs-proprietary modules; a
  `kernel-install` package that does not exist on Arch; `48-guessfamily.conf` asserted as
  a filename the auditor could not find; an `omarchy-sleep-lock.service` that is not in
  the repo. These read as more authoritative than the vague text around them, which is
  what makes them worse than vagueness.

**A schema change was needed to stay honest.** Rewriting a cause silently would have
destroyed the distinction between "cause checked and correct" and "cause never
revisited". Records now carry `cause_reconciled` (a date, or absent), it is a column in
`schema.sql`, and the disclaimer under the audit note in both `ask.py` and the generated
markdown is now **conditional** on it — previously it told every reader of all 197
corrected records that the cause "was not rewritten", which is now false for 22 of them.
A blanket disclaimer that is wrong for part of its audience is the same class of problem
as the assertion that could not fail: it stops carrying information.

### 5. Agent context files brought current, and two gaps filled

Three counts had gone stale as the repo moved, all in the direction that matters — they
undercounted work that had landed:

- `CLAUDE.md` advertised **12 bench specs (6 Omarchy, 4 controls)**; it is 14 (7 Omarchy,
  5 controls). `skillbench/README.md` said **"Four of the twelve"**. Both missed
  `linux-agentic-triage`, the agentic lane's control — added on 2026-08-29 and never
  written into either file. The control that exists to make a lift interpretable was
  invisible in the docs describing the controls.
- `skillbench/README.md`'s layout line said 13 specs and, once corrected, would have
  double-counted: the agentic control is *both* a control and agentic. It now reads
  "6 Omarchy chat + 1 Omarchy agentic, 5 controls (1 of them agentic), gauntlet, crash",
  which actually sums to 14.
- `CLAUDE.md` gained the `cause_reconciled` rule from section 4 above.

**Two supplemental files were added, both where an agent would otherwise have had to
reverse-engineer from source.**

`skillbench/benches/CLAUDE.md` — the bench-spec schema. This was the real gap: the
README explains *why* the bench exists across 310 lines but never documents the spec, so
writing a bench meant reading `spec.py`, `checks.py` and `vmchecks.py`. That matters right
now, because "write harder agentic tasks" is the top open item. It carries the full `post:`
and `checks:` type tables, the three loader/test rules that are enforced (name must match
filename, agentic-without-`post` is refused, every lane needs a control), and both grader
traps that invalidated runs 12/13 — the tilde-quoting asymmetry and `pgrep` matching its
own shell — because those are exactly what a new bench author will reproduce.

`opinionated-omarchy/CLAUDE.md` — what the skill has to be. That directory had a
zero-byte `.gitkeep` and nothing else, and it is the one place an agent is most likely to
start writing from a blank slate. It now records the retrieval-shape problem (the corpus
does not fit in context and "run ask.py" is not a skill), the **+29.3 pt Omarchy /
−2.3 pt control** baseline it has to beat, the instruction to write its benches *before*
tuning it, and the provenance it must not launder — 28 records are still
`gapfill-unaudited` and must not reach a user reading as audited. It replaces the
`.gitkeep`, which a real tracked file makes redundant.

Every figure in these files was checked against the repo rather than copied forward: bench
counts and control names from the YAML, `43` tests from a run, `457`/`228`/`197`/`28`/`4`
and the 22 reconciled from the JSONL, `911` cases and the two lift figures from
`research/bench/`, `1.6 MB` from `du`. The named tests were confirmed to exist before being
cited.

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

### 2. Finish auditing 28 records  — **DONE 2026-09-01**

All 28 audited: 12 `ok`, 15 `corrected`, 1 rejected and removed. No record carries
`gapfill-unaudited` any more. See the 2026-09-01 session entry above.

**The recipe that used to live here was wrong, and is worth keeping as a warning.** It
said to edit `GAP_CATEGORIES` down to those two categories and re-run the gap-fill
workflow. That list drives the *harvest* phase, and the harvest had already succeeded —
those 28 records **are** its output; only `gapfillAudit` came back `NONE`. Running it
would have re-harvested the same topics as `-2` suffixed duplicates and left all 28
exactly as unaudited as before. Track B has no audit-existing path at all; that shape
exists only in Track A, hardcoded to `apps-services`.

### 3. Stale `cause` fields on first-pass corrected records  — **DONE 2026-08-30**

All 130 reviewed, 22 rewritten, each stamped `cause_reconciled`. The "~130" was a
worst-case bound on an unreviewed population, not a defect count. See the 2026-08-30
session entry above.

### 4. Optional / not started

- `opinionated-omarchy/` still holds no skill. Settled: this is where it goes — the one
  that turns the corpus into something an agent can consume. It now carries an orientation
  file (`opinionated-omarchy/CLAUDE.md`) recording what the skill has to be, the
  +29.3 pt / −2.3 pt baseline it has to beat, and the provenance it must not launder; that
  file replaced the `.gitkeep`.
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
| The 456 records (source of truth) | `research/data/problems.jsonl` |
| Generated per-category reading | `research/docs/*.md` |
| Search / build / ingest tooling | `research/tools/` |
| Deep-research report (13 verified findings, 12 refuted folk fixes) | `research/raw/deep-research-report.json` |
| Raw workflow output, kept for provenance | `research/raw/harvest-result.json`, `research/raw/gapfill-result.json`, `research/raw/audit-28-result.json` |
| Post-mortems worth keeping outside the journal | [writeups/](writeups/) |
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
