# Journal: handoff

Last updated: 2026-09-03

## Session of 2026-09-03 (fourth): the incumbent's agentic lift is not real, and one case can poison a run

### 1. Run 28, n=31: the lift decays to nothing

`omarchy-agentic-stale-advice`, `devstral-small-2:24b`, 31 repeats, `agent_timeout` raised
to 900 s as a launch param:

| variant | n | STATE (ok-only) |
| --- | ---: | ---: |
| `none` | 62 | 0.887 |
| `skill:omarchy` | 62 | 0.907 |

**Lift +1.9 pt, p = 0.59, 95% CI [-3.8, +7.5].** The interval spans zero.

The decay is the finding, not the endpoint:

| run | n | lift | p |
| --- | ---: | ---: | ---: |
| 23 | 3 | +11.1 pt | 0.55 |
| 25 | 10 | +8.3 pt | 0.21 |
| 28 | 31 | **+1.9 pt** | **0.59** |

This is not an underpowered null. The power calculation from run 25 asked for about 62
cases per variant and that is exactly what run 28 has. Had the n=3 figure been published,
this project would have claimed an eleven point lift that does not exist.

The residue is confined to one task. `rebind-packaged-default` moved from 12/31 solved to
16/31; `looknfeel-not-hyprlang` went backwards, 26/31 to 25/31. A real skill effect does
not appear in one task and reverse in the other.

### 2. Run 29 is void, and the reason matters more than the run

The control run lost **11 consecutive cases** to `No route to host` on test1, starting at
case 786. Every one was `skill:omarchy` on `dropin-shadows-unit`.

test1 was found at a TTY login prompt rather than in its autologin session; test2 had its
tmux session but no IP. The host was healthy throughout: dnsmasq listening on 67 and 53,
all three `virbr0` ufw rules present, libvirtd not restarted since 28 August. A reset from
the golden image recovered both machines immediately.

**The mechanism is not established.** The most plausible reading is that a case rebooted or
otherwise disrupted test1, which is notable because rebooting is exactly the wrong answer
`dropin-shadows-unit` exists to catch. An earlier guess that the guest kernel showed an
agent-run system update was **wrong**: the golden image carries the same 7.1.9-arch1-2.

**The bug the incident exposed is in the runner, not the VM.** `_one_agentic_case` released
its machine back to the pool in a `finally`, unconditionally, so a dead VM was handed to
case after case. Because the runner finishes one variant before starting the next, the
losses land on whichever variant was running late. An infrastructure failure therefore
arrives looking exactly like a model result, and here it looked like the skill degrading
general Linux performance by 5.5 points. That number would have been reported.

Fixed three ways:

- A machine is only released if `ready()` still answers. Otherwise `Pool.drain()` removes
  it from rotation.
- `acquire()` on a fully drained pool raises and names the dead hosts, rather than blocking
  on an empty queue forever, which reads as a slow run instead of a failed one.
- A run that drained any machine finishes with **DEGRADED** on the run record, saying the
  losses are variant-correlated and the comparison is unsafe. A run quietly finishing on
  half its machines was the actual failure here.

Two regression tests pin it, 45 total now. The second is deliberately synchronous, driven
through `asyncio.run`, because the test image installs plain pytest and an `asyncio`-marked
test would be collected, skipped, and prove nothing.

**Remember the rebuild.** `compose.yaml` does not mount `./app`, so this fix needed
`docker compose up -d --build` to take effect. A bench YAML is picked up live; an app change
is not.

### 3. What this means for the skill

The bar in `opinionated-omarchy/CLAUDE.md` said "do not regress the incumbent on the
agentic lane". That bar is now trivially low: there is no incumbent lift on that lane to
regress. The chat lane's **+29.3 pt** remains the only demonstrated skill effect in this
repository, which strengthens the case for the token-light resident core rather than
weakening it. A corpus-backed skill that shows a surviving agentic lift at n=31 would be a
new result, not a repeat of one.

## Session of 2026-09-03 (third): the writing standard, applied everywhere but the corpus

Every prose file in the repo outside `research/data/problems.jsonl` now follows
`writing-and-responding`. The audit found more than punctuation: a 720-line duplicated
block in this file, a wrong control count in `CLAUDE.md`, and a `README` recipe that named
the workflow which does the opposite of what it claimed.

### 1. `JOURNAL.md` contained 720 duplicated lines

Lines 978-1697 were a **byte-exact** copy of lines 258-977: five whole sessions
(2026-09-02 second, 2026-09-02, 2026-09-01 second, 2026-09-01 first, 2026-08-30) written
twice, 37% of the file. Verified as an exact match before deleting rather than merged by
hand, and the file went 1948 to 1228 lines with no unique content lost. Nothing flagged
it because nothing reads this file mechanically; it only surfaced when a duplicate-line
count was run as part of the audit.

### 2. Four substance defects, all in agent context files

These are the ones that would have cost someone real time, and they are worth more than
the punctuation pass that surfaced them:

- **`CLAUDE.md` said "Five benches are controls" and listed five.** There are **six**:
  `linux-agentic-deep-triage` is flagged `control: true` and was missing from the list.
  `skillbench/README.md` and the bench files both had it right. An agent trusting
  `CLAUDE.md` would have concluded the agentic lane had one control, not two.
- **`research/README.md` told the reader to close 28 unaudited records with
  `gapfill-workflow.js` and a trimmed `GAP_CATEGORIES`.** Wrong twice: those 28 were
  audited on 2026-09-01, and that is the exact mistake `CLAUDE.md` warns about, because
  `gapfill-workflow.js` harvests new records and audits nothing existing. Replaced with a
  pointer to `audit-existing-workflow.js` and the reason.
- **The site's meta description hardcoded `456`** while every other number on the page is
  computed from the corpus. Now `f"{len(recs)} verified..."`.
- **The site's fine print overstated the validation finding.** It said one audited record
  "turned out to name two files that cannot occur on Omarchy 4 at all". Both files exist;
  what cannot occur is the `.pacnew` the record's symptom block quotes. Corrected to
  "quote two .pacnew files". `skillbench/README.md` also still described
  `omarchy-agentic-root-config` as **not yet run against a model**, which the 2026-09-02
  scan had already done.

Smaller: `opinionated-omarchy/CLAUDE.md` introduced a three-item list as "two ways", and
`skillbench/README.md` and `CLAUDE.md` disagreed on the skill's context cost (~3.2k vs
~3.1k tokens). Measured at 12557 characters after frontmatter stripping, so ~3.1k, and
both now say that.

### 3. What was changed, and what was deliberately not

Clean: `CLAUDE.md`, `JOURNAL.md`, `NOTICE`, `opinionated-omarchy/CLAUDE.md`,
`research/README.md`, `research/bench/README.md`, `research/bench/nexus1-baseline-2026-08.md`,
`research/validation/README.md`, `research/assets/fonts/README.md`, `skillbench/README.md`,
`skillbench/MODELS.md`, `skillbench/benches/CLAUDE.md`, the writeup, and the prose
`build_site.py` emits.

Four bodies of text were **left alone on purpose**, and the reasons are not
interchangeable:

- **`omarchy/`, `diagnose-crash/`, and the OFL licence and copyright notices.** Upstream
  and third-party text. `omarchy/SKILL.md` must stay byte-identical or the +29.3 pt
  baseline stops being comparable, and altering a copyright notice is a licence breach.
- **The ~17 loose Hyprland wiki pages in `research/`.** Downloaded, not authored here.
  Reproducing someone else's text means reproducing it exactly.
- **`skillbench/benches/*.yaml` and `research/bench/raw/`.** Bench specs are sha-pinned:
  editing one starts a new series and invalidates the paired comparison. `raw/` is
  provenance and is meant to be verbatim.
- **The corpus.** 1,891 dashes across 424 records, now item 6 of "What's left" with the
  reasons it is its own job.

Inline code comments were also left. The skill's scope excludes code, and the line worth
holding is between a comment and a string a user actually sees. Four generator strings in
`build_db.py` and `ask.py` **were** fixed, because they are prose: they print to the CLI
and are written into the tracked `research/docs/` pages. `research/docs/` was regenerated
and the diff is exactly those strings, 17 lines across 5 files, nothing in a record.

### 4. Agent instructions seeded in three places

- `~/.grok/skills/writing-and-responding/` symlinked into `~/.claude/skills/`, matching
  how `omarchy` and `diagnose-crash` are already linked there, so `Skill()` resolves it.
- `~/.claude/CLAUDE.md` now names it as the standing default and says to decide response
  mode versus author mode first.
- A `## Writing` section in this repo's `CLAUDE.md` covering the three repo-specific
  traps: site prose lives in `build_site.py` rather than `docs/`, the pass-through set
  above must not be restyled, and every number in prose here is checkable against the
  corpus so it should be computed rather than copied.

`scripts/check-writing.ps1` needs PowerShell, which is not installed here, so both review
passes were manual. `CLAUDE.md` carries a `git ls-files | grep` equivalent scoped to the
audited set, run and verified: every line it returns is a code fence, a copyright range,
or a numeric range.

### 5. Verified

`research/tests/run.sh` 13/13, `build_db.py` and `build_site.py` both rebuild clean, and
the documented check command returns only the exempt shapes. The site was rebuilt and its
intro re-read as rendered text rather than as source.

## Session of 2026-09-03 (second): a control with headroom, and the public site

### 1. `linux-agentic-deep-triage`, the control the DiD needed

`linux-agentic-triage` scores **0.950 bare**, five points of headroom, so it could not show
a lift by construction and the difference-in-differences in runs 25/26 was weak in both
directions. The new control scores **0.759 bare** (run 27): about 24 points of room, the
same difficulty profile as the Omarchy trap bench, and nothing the skill mentions
(contamination checked: 0 files in the bundle mention lsof, drop-ins, `systemctl edit`,
deleted files, df, du or inodes).

Two tasks, both with an attractive wrong answer:

- **`deleted-file-holds-disk`**: `df` says 100%, `du` says 13 K. A process holds an
  unlinked file. `lsof` is **not installed** on these VMs, so it has to be found through
  `fuser -m` or `/proc/*/fd`. Bare: 0.67, 0.67, 1.00, 0.50.
- **`dropin-shadows-unit`**: the unit file at `/etc/systemd/system/` is *correct*; a
  drop-in silently overrides `ExecStart`. Invisible unless you run `systemctl cat`. Bare:
  0.80, 0.80, 0.60, 0.80, 1.00.

Hand-verified across every outcome state, and **a reboot scores below doing nothing** (3/6
and 2/5 against floors of 4/6 and 3/5) via a marker in `/run`, which is tmpfs.

**Three assertion bugs found in verification, all the same family as the 2026-08-29 tilde
bug, and all green before the agent runs:**

- **`df` on an unmounted path silently reports `/`.** "Unmount it" scored a *false pass*
  until the check was guarded behind `mountpoint -q`.
- **ext4 reserves 5% for root**, so the write probe succeeded on a 100%-full filesystem.
  Fixed with `mkfs.ext4 -m 0`, and the probe writes 2 MiB rather than 2 bytes.
- **`systemctl stop` does not clear a transient unit left FAILED**, so `systemd-run` refused
  to recreate it and the seed aborted; that cost a real case in run 27. Fixed with
  `reset-failed`.

`test_control_benches_are_flagged` failed when the bench was added, which is the test doing
its job: the control set is pinned so adding one is deliberate.

### 2. The public site: `research/tools/build_site.py`

Generates the repo-root `docs/` (GitHub Pages' default), **not** `research/docs/`, which
`build_db.py` unlinks on every corpus build. 456 record pages, a client-side symptom search
over a 193 KB JSON index, and 12 category groups.

**The design is the Control Room theme**, recovered from `work.handoffs` at
`2026-08/22-controlroom-clean-room-extraction`. That is a `draft`, `human_reviewed: false`
document whose section 1 is transcribed verbatim from the original `style.css` (the reliable part;
its sections 2-3 are unreviewed judgement and were not used). All five motifs are
reproduced: scanline+vignette, twin corner gradients, phosphor traces, glowing LEDs, and
accent-keyed chrome.

**The mapping that makes it fit this project: `audit_status` drives the status LED.** Teal
for audited, amber for corrected, red for unchecked. The board therefore reads the corpus's
*honesty* at a glance rather than burying it, and the conditional `cause_reconciled`
disclaimer is reproduced on the record page exactly as `ask.py` and the markdown do it. A
site that told a reader the cause "was not rewritten" about one that was would be the same
defect in a third place.

The Control Room's five group accents are mapped onto the twelve fix categories in thematic
families (Omarchy core/theming teal, Hyprland/display/wayland blue, GPU/boot/power purple,
pacman/apps amber, network/audio pink). **Twelve distinct accents was considered and
rejected**: past roughly eight, categorical colours stop being reliably distinguishable
under colour-vision deficiency, and the group name is always present as text, so colour is
redundant encoding here rather than the only channel.

**`docs/` is gitignored.** It is 4.3 MB regenerated wholesale on every run; committing it
would add that churn to every corpus change. Pages can build it in CI instead. That is a
decision still open, along with self-hosting the two webfonts: the source handoff is
explicit that fetching Space Grotesk and IBM Plex Mono from a CDN at build time yields a
silently unstyled page on a network blip, so the generator ships fallback stacks only.

### 3. CI publishes the site, and three theme defects fixed

`.github/workflows/pages.yml` builds the site from the JSONL and publishes the artifact, so
the 4.3 MB never enters history. It **sanity-checks before publishing**: one page per
record (a silent drop would otherwise ship a smaller corpus that looks complete), and that
`UNAUDITED` still renders. If the generator ever stops emitting provenance, that must fail
the build rather than publish a corpus reading as uniformly trustworthy. Needs the repo
public and Pages set to "GitHub Actions"; until then the deploy step fails, which is the
honest failure mode.

Three defects found by measuring rather than looking, all inherited from the original:

- **`--muted` was 3.50:1 and used at 8-9.5px.** Micro labels, uptime, timestamps and the
  footer all sit in it. Lifted to `#6b7c8e` (4.51:1, AA) keeping hue and saturation, so the
  recessive hierarchy survives.
- **`--faint` was 2.08:1**, an outright fail. Now `#516072` (3.01:1), and it is used for
  placeholder text only.
- **Only four of the five motifs were implemented.** The phosphor trace was missing because
  a corpus record has no timeseries. It now plots **audit coverage per category** (the one
  series this project has an opinion about) on a fixed 0-100 scale rather than the
  original's autoscale, because autoscaling a percentage makes 100% and 60% look identical.
  Each group heading also carries a stacked audited/corrected/unchecked meter.

**The font question is not solvable by picking a universal font.** There is no widely
installed face that is both CRT-flavoured and legible at 8px: Courier New is the only
truly universal "old mono" and it is a thin, wide typewriter face that fails at label
sizes. The fallback chain now covers the three platforms properly
(`ui-monospace`/`SF Mono`/`Cascadia Mono`/`JetBrains Mono`/`DejaVu Sans Mono`/`Liberation
Mono`), but the real fix is the one the source handoff already mandates: **self-host the
woff2**. Left undone deliberately: it is a licensing and binary-assets decision.

### 4. Departure Mono, vendored: the CRT chrome, and only one third party

The font question from section 3 is resolved, and not by finding a universal face. **One
font is vendored, not two:** Departure Mono (22 KB woff2) carries the *chrome* (wordmark,
micro-labels, group headings, the places letterforms are decoration) while readouts, code
blocks and sources stay on the system `ui-monospace` stack, which is good on all three
platforms and costs nothing. Vendoring a second family for the data would have doubled the
licensing surface for no gain.

**Licence, stated precisely because the metadata is wrong.** The upstream repo's GitHub API
entry reports **MIT**; the bundled `LICENSE` is **SIL Open Font License 1.1**, © 2022–2024
Helena Zhang, and that is the one that governs. No Reserved Font Name is declared, so
redistributing the unmodified file is straightforward. OFL clause 2 requires each copy to
carry the notice and licence, so `build_site.py` copies **both** into `docs/fonts/` and the
CI job now **fails the build** if either is missing: a licence breach should not be able to
ship quietly.

**Pixel fonts need whole-pixel sizes.** The transcribed spec uses 8.5px and 9.5px labels;
at fractional sizes a pixel face blurs into mush. Every rule that switched to the CRT face
is rounded to an integer, and smoothing is disabled on those rules only. That is a
deliberate divergence from the transcription, and the reason is recorded in
`research/assets/fonts/README.md` next to the font.

Self-hosted rather than fetched, for the reason the original handoff gives: the Control
Room's own Dockerfile curled five woff2 files at build time with `|| true` on each, so a
network blip produced a silently unstyled build. 22 KB in git removes that failure mode and
every runtime third party at once.

### 5. The repo is public, the site is live, and the context files were re-audited

<https://techluddite.github.io/opinionated-omarchy/>. Build and deploy both green on the
first run, and the `paths` trigger works: writing the 150 titles rebuilt and republished
the site with no manual step.

Every context file was then re-checked **against the repo rather than copied forward**:
456 records / `ok` 240 / `corrected` 212 / `unaudited` 4 / 0 titleless, 766 sources, 12
categories, 29 `cause_reconciled` stamps, **17 bench specs (9 Omarchy, 6 controls, 5
agentic)**, 3 workflow scripts, 43 skillbench tests, 13 corpus tests. What had drifted:

- **The bench count.** Two benches were added this session, so `CLAUDE.md` and
  `skillbench/README.md` both understated it, and both undercounted the *controls*, which
  is the number that makes a lift interpretable.
- **The repo's own status.** `CLAUDE.md` still described a private repo with no site.
- **Three directories missing from the layout tree**: `docs/`, `.github/workflows/`
  and `research/assets/fonts/`, plus `skillbench/tools/` and `MODELS.md`.
- **[opinionated-omarchy/CLAUDE.md](opinionated-omarchy/CLAUDE.md) had none of this
  session's architecture.** That is the file the skill session opens first, so it now
  carries the three measured retrieval findings and the chat-lane contradiction. See below.

### 6. Pre-flight for going public, and what the screenshots caught

Rendering the site found three defects that reading the generator would not have:

- **Record pages showed `1 RECORDS / 1 AUDITED`** in the masthead: the vitals were computed
  from the single record being rendered instead of the corpus. Now corpus-wide.
- **150 of 456 records carry no `title`**, so a third of pages had a raw slug as their `h1`.
  `build_db.py` has the same fallback, so the site was *consistent*. This is a **corpus
  content gap, not a site bug**. The slug is prettified for display only; filling those
  titles in properly is a content task, now on the backlog.
- **The phosphor trace read as a solid slab.** Audit coverage is 97-100%, so the area under
  the line is nearly the whole box and `--signal-soft` (.14) filled it. Dropped to .06 so it
  reads as a trace.

Pre-flight for the public flip came back clean: **no keys or tokens in tracked files or in
history** (the bench key was never added; it is ignored by a nested
`skillbench/.gitignore`). Two things were fixed first:

- **`/home/techluddite` was hardcoded** in both harvest workflow scripts. Unportable in a
  public clone, and a silent failure: agents read the corpus off disk, so a wrong root
  surfaces as a missing file *inside an agent*. Now required in `args`, failing loudly at
  launch.
- The **test-VM credentials in CLAUDE.md are published deliberately.** They guard NAT-only
  VMs with loopback VNC and no real data, and the file says so. Anyone cloning this should
  change them before giving those machines a routable address.

### 7. Scaling settled: per-record files, and FTS5 rather than grep

**Per-category storage is already broken, not a future risk.** Seven of the twelve category
pages exceed the 32K context window *today* at 456 records; `network.md` is 43.3k tokens.
With per-record files a category is metadata, so splitting one is a field edit, never a
migration.

The real limit is **match precision, not file size**. Unranked grep over an index returns 22
hits for `bluetooth`, 32 for `nvidia`, 45 for `audio` and **94 for `boot`**. Reading those
is ~94k tokens, and at 10x growth it is hopeless. `ask.py` already solves this with FTS5 +
bm25 and tuned per-column weights, so **the skill should ship the SQLite index, not grep**.
Confirmed with the operator as the intended direction.

## Session of 2026-09-03: n=10, and the lift does not survive it

Runs 25 and 26 replicate runs 23/24 at ten repeats. **The +11.1 pt lift does not hold.**

| bench | none | skill | lift | 95% CI | p |
| --- | ---: | ---: | ---: | --- | ---: |
| `omarchy-agentic-stale-advice` | 0.800 | 0.883 | +8.3 pt | [−1.7, +18.3] | 0.205 |
| `linux-agentic-triage` (control) | 0.950 | 1.000 | +5.0 pt | [+0.0, +13.3] | 0.491 |
| **difference in differences** | | | **+3.3 pt** | | **0.807** |

Read the last row. **The skill lifts the general-Linux control nearly as much as it lifts
the Omarchy bench**, and that is precisely the condition the controls exist to detect: by
this repo's own rule it is measuring answer length, not Omarchy knowledge. The n=3 figures
(+11.1 vs +5.6, a +5.6 gap) shrank to +8.3 vs +5.0, a **+3.3 gap at p = 0.81**. Classic
small-sample optimism, caught by doing the obvious thing and running it again bigger.

The binary framing agrees exactly and is easier to hold onto: **solved outright, 8/20 bare
vs 13/20 with the skill, Fisher exact p = 0.205.**

### 1. n=10 was underpowered by about 3x, and that is computable

At the observed effect (0.40 → 0.65 solved) and its variance, 80% power at α=0.05 needs
**~62 cases per variant ≈ 31 repeats**. We ran 10. So "not significant" here means the experiment
was too small to tell, **not** that the skill does nothing. The honest next step is either
31 repeats or accepting that this effect size is not worth the hours.

[skillbench/tools/lift_test.py](skillbench/tools/lift_test.py) now does this properly:
permutation test, bootstrap CI, and the difference-in-differences, stdlib only. **The unit
is the case, not the assertion**: the 6 post assertions inside a case are heavily
correlated, and treating 60 assertions as 60 independent samples would have manufactured
significance out of nothing.

### 2. The control is saturated, which is a real limit on this comparison

`linux-agentic-triage` scores **0.950 bare**, so it has 5 points of headroom and cannot
show a large lift by construction. That caps how much signal the difference-in-differences
can ever carry, and it means the DiD test here is weak in both directions.

**A control needs headroom for the comparison to mean anything.** Every existing control
was chosen to be *easy general Linux*; none was chosen to be *hard* general Linux. That is
the flaw to fix before spending 31 repeats on anything.

### 3. What did hold up

- **The trap bench has real headroom** and is the only agentic bench that does: bare solves
  it 8/20, against saturation at 8/8 everywhere else. The bench design works even though
  the skill result was negative.
- **Scores are cleanly bimodal**: 4/6 (did nothing) or 6/6 (did it right), almost nothing
  between. The "wrong answer scores below the floor" design gives a grader that separates
  the three outcomes, and the data shows agents really do land in exactly those bins.
- **`skill:omarchy` halves the error rate**: 6 of 20 bare cases errored, against 2 of 20
  with the skill. That is a real and separate effect from the STATE lift, and it is what
  drove the +20 pt `success` difference. Worth measuring deliberately rather than as a
  by-product.

### 4. The latency fix is NOT live, and runs 25/26 still carry the old semantics

`compose.yaml` mounts `./benches` and `./data` but **not `./app`**, so `app/runner.py` is
baked into the image. The queue-wait fix committed on 2026-09-02 therefore did not take
effect for runs 25 and 26: **it needs `docker compose up -d --build`**. Correcting the
previous entry: the old latency semantics apply through **run 26**, not run 24. (This is
also why a new bench YAML is picked up with no rebuild but an app change is not.)

## Session of 2026-09-02 (second): the trap seam, and the first agentic lift

Two things were asked for and both landed: `qwen3.8:27b` is unblocked, and the Omarchy 3
trap seam now has a bench. The lift is positive but **not yet demonstrated**: the control
moved too.

### 1. `qwen3.8:27b` was never incapable

Recorded as **blocked** earlier the same day on one bare case: `pi exited 1`, a transcript
containing only `500: no user query found in messages`, and a floor score. Re-run with 3
repeats (run 22) it scores **8/8, 8/8, 7/8**, and the 7/8 case had already done most of the
work before erroring. It is the **fourth capable model**, and run directly it produced the
best solution of anything tested: it used Omarchy's own `omarchy-refresh-limine` instead of
hand-rolling `limine-update`, and noticed `OMARCHY_PATH` is not passed through `sudo`.

**Root cause, and it is Ollama's, not pi's.** `no user query found in messages` is compiled
into the **Ollama binary**. `qwen3.8:27b` reports family `qwen35` with template
`{{ .Prompt }}` (a stub), so Ollama renders it with a **built-in renderer for that family
which requires at least one `user` message**. One curl reproduces it with no agent involved:
`system`+`user` returns 200, `system` alone returns the 500, and so does
`system`+`assistant`. `devstral-small-2:24b` accepts all three, which is why only this model
trips. Somewhere in a long loop pi sends an array with no surviving user turn. Intermittent,
about **1 run in 3**.

**The lesson is about the scan, not the model:** a one-repeat scan cannot separate "cannot
act" from "hit an intermittent harness failure". Anything recorded as blocked deserves a
re-run before it is believed. This is now written into
[skillbench/MODELS.md](skillbench/MODELS.md).

### 2. `omarchy-agentic-stale-advice`, the first bench with headroom

Two tasks where the *widely published* answer is wrong on Omarchy 4: the Omarchy 3
`~/.local/share/omarchy` git checkout, and hyprlang config that Hyprland 0.55 deprecated for
Lua. Both prompts say the change **"must survive an `omarchy update`"**, the phrasing a
real user would use, satisfiable only from the user tree, and it never names the answer.

**The design rule worth copying: the wrong answer scores BELOW doing nothing.** Verified by
hand on a VM across five outcome states:

| outcome | task 1 | task 2 |
| --- | ---: | ---: |
| does nothing | 4/6 | 4/6 |
| hyprlang `hyprland.conf` | **3/6** | **3/6** |
| resurrects the Omarchy 3 tree | **3/6** | n/a |
| correct Lua in the user tree | **6/6** | **6/6** |

A pass/fail assertion cannot separate "did nothing" from "did the wrong thing"; this does.

**Both first-draft patterns were green on a file the agent never touched.** `bindings.lua`
ships a commented `-- hl.unbind("SUPER + SPACE")` example and `looknfeel.lua` ships **five**
commented `hl.config(` examples plus a commented `gaps_in`, so `hl\.unbind` and `hl\.config`
matched the pristine template and task 2 would have scored 6/6 while doing nothing. Fixed
with `^[^-]*`, which excludes Lua comments. **This is the tilde-quoting bug of 2026-08-29 in
different clothes**, and it was caught only because the schema doc insists on hand-verifying
before and after on a real VM. Hand-verify against the SHIPPED templates, not an empty file.

### 3. Run 23/24: a positive lift, and an honest control that undercuts it

`devstral-small-2:24b`, 3 repeats, `none` vs `skill:omarchy`:

| bench | none | skill | lift |
| --- | ---: | ---: | ---: |
| `omarchy-agentic-stale-advice` | 0.889 | 1.000 | **+11.1 pt** |
| `linux-agentic-triage` (control) | 0.944 | 1.000 | **+5.6 pt** |

**This is the first positive lift the agentic lane has ever produced**, and the trap bench
is the first with real headroom: bare hits the floor on `rebind-packaged-default` in 2 of
3 runs, where every earlier agentic bench was saturated at 8/8.

**But do not report it as a result yet.** The control moved +5.6 pt, which is *one assertion
flipping* out of 18; the Omarchy delta is four out of 36. Both are a couple of assertion
flips on n=3. The direction is right and the Omarchy bench moved twice the control, but the
sample cannot separate a real effect from noise. **More repeats is the whole next step.**

Also worth noting: the two tasks behave differently. `looknfeel-not-hyprlang` is nearly
saturated bare (6/6, 6/6, 4/6) while `rebind-packaged-default` is not (4/6, 4/6, 6/6). The
headroom is in the *binding* task, and a future bench should lean that way.

### 4. Agentic `latency_s` was measuring the queue, and a previous claim was wrong

`t0` was set **before** `pool.acquire()`, so agentic latency included time spent waiting for
a VM. Concurrency there is the pool (2), so a case launched 12th banks the whole queue, and
because the runner finishes one variant before the next, **the second variant systematically
looks slower**. That inflated run 23's `skill` mean to 1572 s against 790 s bare, and it
means the **"3.0x latency" reported for run 18 overstates the skill's cost**; that figure
should not be quoted.

Fixed: the clock starts after `acquire()`, and `queue_wait_s` is recorded separately.
**Corrected 2026-09-03: the fix is not live.** `compose.yaml` does not mount `./app`, so
the runner is baked into the image and needs `docker compose up -d --build`. The old
semantics therefore apply through **run 26**, not run 24.

## Session of 2026-09-02: what the local models can actually do

The agentic bench got its first paired run and its first honest answer, and the answer
moves the open problem rather than closing it.

### 1. Run 18: the paired run, and it is a flat zero

`omarchy-agentic-root-config`, `devstral-small-2:24b`, `none` vs `skill:omarchy`, 3 repeats:

| variant | cases | success | STATE | mean latency |
| --- | ---: | ---: | ---: | ---: |
| `none` | 3 | 1.000 | **0.958** (23/24) | 97 s |
| `skill:omarchy` | 3 | 1.000 | **0.958** (23/24) | 291 s |

Identical to three decimals, at **3.0x the latency**. The cost of putting the skill in an
agent loop reproduces (2.0x and 4.5x in runs 14/15); the benefit still does not exist.

### 2. Run 21: the reason, and it is not task difficulty

The standing assumption was that the bench needed harder tasks. **That assumption is now
evidence-against.** A bare scan of all 14 tool-capable local models
([skillbench/MODELS.md](skillbench/MODELS.md)) found:

- **3 of 14 can do the task at all**: `qwen3-coder:30b` (41 s), `devstral-small-2:24b`
  (86 s), `gemma4:26b` (96 s). All three score **8/8**.
- **11 score the untouched floor of 5/8**, and none of them for a reason a skill could fix.
  They emit the tool call as prose, or as pseudo-XML, or return an empty transcript, or
  give up on the first permission error.

**Every model capable enough to drive the loop is also capable enough to finish the task.**
The band is that narrow. Harder tasks do not widen it; they just move the three capable
models down while the other eleven keep scoring the floor for unrelated reasons.

**The floor is 5/8, not 0**, which is what makes this easy to misread: five of the eight
assertions are "you did not break anything", so a model that does nothing still scores
0.625. Score alone cannot distinguish "did nothing" from "did most of it".

### 3. Failure modes that look identical in the score column

Four different causes produce the same 5/8, and telling them apart needed transcripts,
`/api/ps` and the error field:

- **VRAM.** `qwen3:32b` is 22.7 GB of a 25.2 GB footprint on a 24 GiB card: **90% on GPU,
  10% spilled to CPU**. It does not fail cleanly; it crawls and dies at 237 s. A memory
  failure reads exactly like a capability failure.
- **Throughput.** `muse-glimmer:30b` fits *entirely* on GPU and still blew the 600 s budget.
- **Harness compatibility.** `qwen3.8:27b` returns `500: no user query found in messages`
  from pi's OpenAI-compat request and never gets to try. Recorded as **blocked, not
  judged**; calling that a capability verdict would be a lie.
- **Competence.** The remaining eight, in various shapes.

**The result worth remembering: `gemma4` (8B) reported the merge complete while changing
nothing.** A transcript-trusting grader scores that a success. It is the sharpest possible
argument for why the agentic lane asserts on the machine and carries no transcript checks.

### 4. Context and VRAM are hard constraints, and they lived nowhere in the repo

Both now in [CLAUDE.md](CLAUDE.md), because both are on the ollama systemd unit rather
than in this repository and are therefore easy to lose:

- **`OLLAMA_CONTEXT_LENGTH=32768`** is a *server* cap on every model. **Ollama's own
  default is 4096.** If that variable were ever lost, every agentic result would silently
  become garbage rather than fail.
- **`pi --list-models` reporting `128K` is cosmetic.** pi speaks OpenAI-compat, which has
  no way to set `num_ctx`. The server decides. Believing the client here would have been
  an easy and invisible mistake.
- At 32K the `omarchy` body is ~10% of the budget, `omarchy-full` ~20%.
- **24 GiB is the real ceiling and the 30B class already sits at ~20.2 GiB.**

### 5. Three defects in the VM tooling, all silent

Found while getting the pool usable again; all three cost time before they were understood.

- **The pool came up dead.** `/readyz` reported `ready:false, tmux:false` on both machines:
  they had been reset to a golden image carrying NOPASSWD sudo but **no bench key and no
  tmux units**. Re-installed and re-provisioned, then re-saved the goldens from the
  provisioned state and verified across a reboot.
- **`golden-test-vm.sh save 1 2` silently saves only VM 1.** It takes a single number;
  the extra argument is ignored without error. CLAUDE.md had documented the two-argument
  form, which is how the goldens went stale in the first place. `reset` has the same shape.
- **`provision-bench-vm.sh` hardcoded four models** into pi's `models.json`. pi still
  *runs* an unlisted model. It warns `not found for provider ollama. Using custom model
  id` and carries on with its own defaults, so listed and unlisted models were not
  configured identically and nothing surfaced as an error. The list is now **derived from
  Ollama's tool-capable models**; pull a model and re-provision, never edit a list.

### 6. The grader question from run 17 is answered, with data

The 2026-08-30 entry asked whether STATE is inflated by scoring timed-out cases, and said
to decide before the next paired run. Computing it both ways over run 17 gives
`state_ok` == `state_all` == 1.000: every timed-out case had genuinely passed all its post
assertions. **STATE is not inflated.** STATE and `success` measure different things (did
the machine end up correct, versus did the agent exit within budget) and both were right.
No grader change. Run 18 had no timeouts, so it does not bind there either.

## Session of 2026-09-01 (second): writer tests, the first live scenario, and root in the bench

Item 4 of "What's left" is closed, and the VM spot-checking under item 5 has started.

### 1. The corpus writers now have one schema definition, and tests

`ingest.py`'s `FIELDS` allowlist was missing `cause_reconciled`. That was predicted in
the backlog ("read `ingest.py` for the same defect, before it is next run") and it was
real: the replace path projected records onto a private list that never learned about the
field added on 2026-08-30.

Adding the string to the second list is not the fix; two lists that must never diverge is
the defect. [research/tools/corpus.py](research/tools/corpus.py) now holds the only
`FIELDS`, plus the only `read_jsonl` / `write_jsonl`, and both writers import it. That
also pins `newline="\n"` and `encoding="utf-8"` in one place instead of at each call site.

`write_jsonl` **raises** on a key it cannot classify. The harvest genuinely emits chaff
the corpus drops on purpose (`cause_note`, `cause_extra`, `verify_note`, enumerated
from the raw payloads into `WORKFLOW_ONLY`), so a blanket raise would have broken every
merge. The distinction is the point: dropping enumerated chaff is the projection working,
dropping an unclassified key is an unfinished schema change.

**13 tests, stdlib `unittest`, `research/tests/run.sh`.** Not pytest: the corpus tooling
is dependency-free by design so it runs on a bare container, and a suite that needed
pytest installed would be the first thing to break that. Two of them are the ones that
would have caught 2026-08-30: `FIELDS` is asserted against `schema.sql` and against the
live corpus, in both directions.

**The tests were checked against the defect, not just run green.** Removing
`cause_reconciled` from `FIELDS` again produces 3 failures and 8 errors, and both
invariant tests name the missing field in their message. An assertion that cannot fail is
the thing this project keeps catching itself on, so it gets proved rather than assumed.

Two consumers of the four are now checked automatically. `schema.sql`, `build_db.py`,
`ask.py` and `corpus.py` still all have to be edited by hand for a new field.

**The refactor is provably neutral:** reading all 456 records and writing them back
through the new code is byte-identical to `data/problems.jsonl` (sha256
`fd5f5bfe653745e8…`). Key order is load-bearing (it is the key order of every line on
disk), so `FIELDS` may be appended to but never reordered.

### 2. The first live scenario: a corpus record exercised on a real VM

New directory [research/validation/](research/validation/): induce a problem on a
throwaway VM, apply a fix, assert on the machine, append to `runs.jsonl`. Read its
README before adding one; the trust model is the whole design.

**Validation never touches `audit_status`.** That field means "checked against its
sources", and one VM agreeing is not a source confirming. Results are a separate
append-only log because a record has one audit but many runs, each with its own date and
Omarchy version. And `repair:` is explicitly *an operator's reading* of the record's
prose, not the record: record fixes are branching prose, and only 6 of 456 have a fenced
`verify` block, so nothing here can execute "the fix" itself.

First scenario: `mkinitcpio-pacnew-unhandled-breaks-next-boot` on omarchy `4.0.1-1`.
**6/6 assertions pass**: the record's remediation advice is sound, and its
Omarchy-vs-plain-Arch branch is confirmed by the system itself: `/usr/local/bin/mkinitcpio`
is a wrapper from `limine-mkinitcpio-hook` that warns `This does not update Limine boot
entries` and offers `limine-mkinitcpio` instead, exactly as the record says.

**But three claims in that record are wrong for Omarchy 4, and the source audit missed
all three.** `/etc/default/limine` is owned by no package, so it can never produce the
`.pacnew` the record's symptom block quotes; `/etc/mkinitcpio.conf` is `[unmodified]` on
a stock install, so neither can it; and the danger claim that overwriting
`mkinitcpio.conf` "removes your encryption, plymouth and btrfs hooks" is false, because
those come from a package-owned drop-in sourced afterwards that assigns `HOOKS=`
wholesale. Measured, not inferred. Generic Arch advice mis-specialised to Omarchy, the
same family as the Omarchy 3 → 4 tree split.

**These are recorded in the validation README, not edited into the corpus.** A correction
needs an `audit_note` and a `cause_reconciled` stamp through `merge_gapfill.py`; a silent
rewrite is exactly what the provenance fields exist to prevent.

### 3. What the spike cost, which was the point of running it

The harness is written once. Per record after that, the expensive part is neither the
seed nor the assertions: it is **establishing ground truth on a live machine first**.
Eight ssh round trips went into learning that `/boot` is a root-only vfat ESP, that
Omarchy boots a UKI and has no `vmlinuz`, that the hooks live in a drop-in, and that
`/etc/default/limine` is unowned. Only after that could the assertions be written
correctly.

Two of six assertions were wrong on the first run and both failed *for the wrong reason*:
one asserted `/boot/vmlinuz-linux`, which does not exist on this system, and did so as an
unprivileged user against a `dmask=0077` mount, where `test` returns 1 for "unreadable"
and looks identical to "absent". A third re-ran `limine-mkinitcpio` inside an assertion,
making grading a side effect that rebuilt the boot image; that is why the runner now has
`repair_output_*` types.

Realistically **30–45 minutes per scriptable record**, more for anything needing a
reboot to observe. So this scales to a few dozen records, not 456; roughly a third of
the corpus is out of reach of these VMs anyway (67 `nvidia` / 49 `intel` / 47 `amd`
against a virtio GPU, 297 `laptop`, most of `power-suspend`, much of `network`).
**Spot-check and bench-source, not corpus validation**, and the README says so.

**The golden-image workflow was exercised end to end and matches its documentation:**
reset 0.76 s, ssh reachable ~7 s later. `virsh shutdown` is still ignored; poweroff over
ssh works.

### 4. Item 1 is unblocked: the agentic lane could not reach root, and now can

Writing the scenario into a bench turned up why `omarchy-agentic-config` is saturated,
and it is not that nobody wrote hard tasks. **Every task in it is a `~/.config` edit
because that was the ceiling.** The bench drives the VM over ssh with no tty (`vm.py`
`run()` is `bash -lc` with nothing on stdin), and the bench user had no passwordless
sudo, so nothing requiring root could be seeded, performed by the agent, or asserted.
Userspace config is the easy end of Omarchy, and the bench could only ever measure that
end.

`tools/provision-bench-vm.sh` now installs `/etc/sudoers.d/99-bench-nopasswd`, validated
with `visudo -c` so a broken sudoers is never shipped, and using `id -un` rather than
`$USER`. `$USER` is set by login(1) and is frequently empty in a non-interactive ssh,
which would have written a rule for the wrong name or none.

**Both golden images were re-saved with it baked in**, because the first reset silently
dropped it and a `sudo` assertion would then fail looking like a bench bug. Verified: a
reset now comes back with NOPASSWD intact and no leftover bench state.

This is safe on these VMs and nowhere else: disposable, NAT-only, no real data, and
their password is already committed in plain text. It does let a misbehaving agent break
the machine, which is what the 0.76 s reset is for.

### 5. The first deliberately hard agentic bench

`skillbench/benches/omarchy-agentic-root-config.yaml`. One task: resolve a `.pacnew` for
the Limine boot config, keeping both the operator's local setting and the new upstream
one, and regenerate the boot config.

**The difficulty is structural rather than obscure.** Both wrong answers are single
plausible commands that exit 0 and look like completion: `mv` the `.pacnew` over the live
file adopts upstream and destroys the local edit; `rm` keeps local and silently discards
the new option. Asserting on *both* values means each shortcut fails a different
assertion, so the bench says which mistake was made rather than just "failed".

**Checked by hand on a VM as `benches/CLAUDE.md` requires**, all four states:

| state | score | what failed |
| --- | --- | --- |
| after seed, nothing done | 5/8 | both values, the `.pacnew`, the rebuild |
| `mv` the .pacnew over the file | 7/8 | the local setting |
| `rm` the .pacnew | 7/8 | the upstream setting |
| a real merge, then rebuild | **8/8** | n/a |

The remaining five assertions are collateral-damage guards (hooks intact, UKI present,
`pacman -Qkk omarchy` clean) which correctly pass on an untouched machine and are there
to catch an agent that succeeds destructively.

Two things in it are worth copying and are written into `benches/CLAUDE.md`: the
"both wrong answers are one command" shape, and the fact that **a seed touching `/etc`
must be idempotent**, since `defaults.vm.restore` is `$HOME`-relative and `/etc` persists
between cases. That bench keeps a pristine copy on first run and re-derives from it.

All **43 skillbench tests still pass** with the new spec, so it loads, its assertions
compile, its paths are absolute, and the control set is still pinned.

**Not yet run against a model.** The bench is validated as a measuring instrument; what
it measures is the next session's work, and it needs a paired bare/skill run to say
anything about lift.

### 6. A lead worth someone's time

`/etc/mkinitcpio.conf.d/omarchy_resume.conf` is `HOOKS+=(resume)`, which appends `resume`
*after* `filesystems`, `fsck` and `btrfs-overlayfs`. Corpus record
`resume-hook-after-filesystems-hibernation` (one of the 4 remaining `unaudited` records)
describes that exact ordering as a problem. Either the record is wrong, or Omarchy ships
the broken ordering by default. Observing the ordering does not establish which, and
guessing would be the fabricated-precision failure mode again. **Check it against a
source.**

## Session of 2026-09-01 (first): the last unaudited records, and the Windows remnants

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
`usb-tethering-renamed-wwan-networkmanager-ignores` described a real kernel regression:
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
  field there, so a merge would have **stripped all 22 stamps**. It also rewrote causes
  without stamping them, which would have made `build_db.py` and `ask.py` print *"The Cause
  above was not rewritten and may still contain the error described"* about causes it had
  just replaced. Both fixed: the field is in `FIELDS`, and `apply_verdict` stamps
  `date.today()` whenever it applies a `corrected_cause`.

Both are written up in full in
[writeups/2026-09-01-merge-gapfill-silent-defects.md](writeups/2026-09-01-merge-gapfill-silent-defects.md),
including the two follow-ups they leave open: the corpus tooling has no tests at all, and
adding a schema field still has no checklist covering its four consumers.

The second was caught by dry-running the merge against a **copy** of the corpus with
synthetic verdicts before letting it near the real file; worth doing again, because the
failure is silent and the evidence it destroys is the evidence of honesty.

That dry run also confirmed the property that actually makes this merge safe: **merge
iterates every record in the audited category, not just the targeted ones.** Records with
no verdict are preserved, so scoping the verdict set is what protects the 33 already-audited
`wayland-compat` records. The workflow filters verdicts to the assigned slugs for the same
reason.

### 3. The audit workflow is now a third script in the repo

`research/tools/audit-existing-workflow.js`. The repo had two workflow shapes and neither
audits a record that already exists: `gapfill-workflow.js` **harvests** against
auditor-named gaps and audits only what it just wrote, and its one audit-existing path is
Track A, hardcoded to `apps-services`. That gap is exactly what made the old item-2 recipe
wrong, so the fix is a script rather than a note.

Retarget it by editing `BATCHES`; slugs are listed explicitly rather than derived, which
keeps the run resumable and means a verdict can never land on a record you did not name.
Batches of 6-8 leave each agent enough budget to actually fetch each record's sources.
The obvious next user is the 4 remaining `unaudited` records.

### 4. The Windows era is gone

The repo was converted from Windows earlier; two things survived that conversion.

- The `gapfill-workflow.js` path above, the only functional remnant left anywhere.
- **`CLAUDE.md`'s "previously developed on Windows" paragraph.** The LF and UTF-8 rules it
  introduced are load-bearing and stay, but they now stand on their own merits instead of
  being framed as inherited concessions.

**Two things that look like Windows remnants are not, and should be left alone.**

- `research/{lua,u55,wr054}.txt` carry CRLF. That is deliberate: `.gitattributes` pins
  `research/*.txt -text` so downloaded wiki pages keep their harvested bytes. Provenance,
  not drift.
- Every other "Windows" hit is **corpus content** (dual-boot Bluetooth link keys, NTFS,
  "works on Windows but not Arch") or Hyprland *windows* in `wr054.txt`'s window rules.
  Stripping those would delete real records.

## Session of 2026-08-30: catching the journal up, and starting the re-audit

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

So the bench is still saturated exactly as the 29th recorded it; this adds only that a
30B model does not fit the current `agent_timeout: 600`. Do not read run 17 as a lift.

### 2. A grader question run 17 raised, still open

**Post assertions are evaluated on timed-out cases too, and they passed there.** Both
`monitor-persist` cases errored on the timeout, yet each reports `post 3/3` and contributes
`state = 1.0`. That is why the run shows STATE 1.000 alongside a success rate of 0.333.

This may well be correct: an agent can finish the edit and then burn the remaining budget
without exiting, and refusing to score work it demonstrably did would be its own distortion.
But it means STATE currently averages over cases the runner classified as failures, so STATE
and `success` can disagree without either being wrong, and a reader comparing them will
assume one is broken. **Decide which it is before the next paired run**, and whichever way it
goes, make the UI say so. This is the same class of thing the control caught in run 12/13:
not a wrong number, but a number whose meaning is not written down.

### 3. Smaller drift

- **The suite is 43 tests, not 39.** `CLAUDE.md` still advertised 39; corrected there. The
  "27 unit tests" in the 08-28/29 entry below is left alone; it was true on the day, and
  a journal entry is a dated record, not a live figure.
- **`skillbench/app/ui.py` had an uncommitted change** moving the run-history table below
  the fold, so the run you just launched is not pushed off screen by the history. Committed
  as-is; it was finished, not half-done.

### 4. Item 3 of "What's left" is closed: 22 stale causes, not 130

The backlog said "roughly 130 `corrected` records may still carry a `cause` the auditor
disproved". That number was the size of the population nobody had
looked at, never a count of defects. All 130 have now been read, and **22 actually had a cause their own
audit note contradicts.** The other 108 are fine: their notes open with "the diagnosis is
right", "cause verified exactly", "the mechanism is real", and go on to object to the
*fix*, which the first-pass audit had already rewritten.

**Scoping it took provenance, not keywords.** The README records that the second pass's
auditors could return a `corrected_cause` while the first pass's could not, so the
affected set is exactly the `corrected` records whose audit came from the first pass.
Reconstructing that from `raw/harvest-result.json` and `raw/gapfill-result.json`
(`apps-services` was the only category re-audited in pass 2; everything else in
`gapfill-result` audits the *new* records) yields **130 records, and independently
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
markdown is now **conditional** on it: previously it told every reader of all 197
corrected records that the cause "was not rewritten", which is now false for 22 of them.
A blanket disclaimer that is wrong for part of its audience is the same class of problem
as the assertion that could not fail: it stops carrying information.

### 5. Agent context files brought current, and two gaps filled

Three counts had gone stale as the repo moved, all in the direction that matters: they
undercounted work that had landed:

- `CLAUDE.md` advertised **12 bench specs (6 Omarchy, 4 controls)**; it is 14 (7 Omarchy,
  5 controls). `skillbench/README.md` said **"Four of the twelve"**. Both missed
  `linux-agentic-triage`, the agentic lane's control, added on 2026-08-29 and never
  written into either file. The control that exists to make a lift interpretable was
  invisible in the docs describing the controls.
- `skillbench/README.md`'s layout line said 13 specs and, once corrected, would have
  double-counted: the agentic control is *both* a control and agentic. It now reads
  "6 Omarchy chat + 1 Omarchy agentic, 5 controls (1 of them agentic), gauntlet, crash",
  which actually sums to 14.
- `CLAUDE.md` gained the `cause_reconciled` rule from section 4 above.

**Two supplemental files were added, both where an agent would otherwise have had to
reverse-engineer from source.**

`skillbench/benches/CLAUDE.md`, the bench-spec schema. This was the real gap: the
README explains *why* the bench exists across 310 lines but never documents the spec, so
writing a bench meant reading `spec.py`, `checks.py` and `vmchecks.py`. That matters right
now, because "write harder agentic tasks" is the top open item. It carries the full `post:`
and `checks:` type tables, the three loader/test rules that are enforced (name must match
filename, agentic-without-`post` is refused, every lane needs a control), and both grader
traps that invalidated runs 12/13 (the tilde-quoting asymmetry and `pgrep` matching its
own shell) because those are exactly what a new bench author will reproduce.

`opinionated-omarchy/CLAUDE.md`, what the skill has to be. That directory had a
zero-byte `.gitkeep` and nothing else, and it is the one place an agent is most likely to
start writing from a blank slate. It now records the retrieval-shape problem (the corpus
does not fit in context and "run ask.py" is not a skill), the **+29.3 pt Omarchy /
−2.3 pt control** baseline it has to beat, the instruction to write its benches *before*
tuning it, and the provenance it must not launder: 28 records are still
`gapfill-unaudited` and must not reach a user reading as audited. It replaces the
`.gitkeep`, which a real tracked file makes redundant.

Every figure in these files was checked against the repo rather than copied forward: bench
counts and control names from the YAML, `43` tests from a run, `457`/`228`/`197`/`28`/`4`
and the 22 reconciled from the JSONL, `911` cases and the two lift figures from
`research/bench/`, `1.6 MB` from `du`. The named tests were confirmed to exist before being
cited.

## Session of 2026-08-29: the agentic lane

The Skill Bench now grades what an agent **does** on a real machine, not only what a model
says. This was the top item on "what's left" and it is built, running and documented.

### 1. How it works

A bench declares `lane: agentic`. Each case then: acquires a VM from a pool, restores the
paths the bench declares, applies a `seed:` (the breakage), runs `pi --print --skill <dir>`
in a **tmux window**, and evaluates the task's `post:` block over ssh.

Two graders, kept apart in the UI on purpose: QUALITY (transcript) and STATE (the VM).
Collapsing them would hide a model that describes the right edit and never makes it.

`omarchy-agentic-config` is the first bench: add a keybinding, switch a theme, configure a
monitor. Every task also asserts `pacman -Qkk omarchy` reports **0 altered files**, which
is a hard statement that the agent stayed out of `/usr/share/omarchy`, the exact place
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
(−5.5 vs −8.3), which, by the rule the controls exist to enforce, means these numbers are
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
loop, not anything Omarchy-specific. Two of 36 cases hit the 600 s timeout, one in each
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

The tell was the control scoring **exactly 0.500 on every task in both variants**, a
constant rather than a measurement. A control that cannot move is a broken control, and catching
that on its first outing is precisely what it is for. Three regression tests now cover it,
including one that scans every shipped bench for post paths that cannot resolve.

### 3. The lesson that changed the bench: good agents do not narrate

devstral scored **3/3 on the monitor task while its entire transcript was "Task
completed."** The chat lane's `checks:` were therefore scoring *verbosity* and marking the
best-performing agent down for being terse. Forbidden-pattern checks are no better: a
silent agent passes them all and reads as 100%.

So the agentic bench now carries **no transcript checks at all**. In this lane the machine
is the measurement.

### 4. Four things that cost real time, all now written down in CLAUDE.md

- **libvirt rejects every new forwarded connection into `192.168.122.0/24`.** A bridged
  container cannot reach the test VMs, and no ufw rule can override it: in nftables an
  `accept` in one base chain does not stop another base chain rejecting, and only
  `reject`/`drop` are terminal. The bench moved to `network_mode: host`, which also
  **deleted** the old pinned-subnet ufw rule for Ollama. One less invisible host-level
  dependency, in a repo where that class of trap has now bitten three times.
- **`OMARCHY_PATH` comes from `~/.bashrc`**, so a non-interactive ssh has it unset and every
  `omarchy` subcommand fails with `find: '/themes/'`. Everything on the VM runs under
  `bash -l`. It matters twice: a tmux window inherits the *tmux server's* environment, and
  that server is a systemd user unit with no profile sourced. Without this the **agent**
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
at the host's Ollama. `tools/install-bench-key.sh` gives the bench its **own** ssh key
(never the operator's), gitignored under `skillbench/secrets/`.

Read-only is load-bearing both ways: a watcher cannot type into a running case, and the
runner therefore must never use `tmux send-keys` (tmux refuses it outright). Launching each
case *as* a window is the supported path.

### 7. Isolation: what it is, and what it is not

Before every case the VM is restored from a tar of the paths the bench declares. **Anything
outside those paths persists.** Verified working: an agent invented
`~/.config/omarchy/keybinds.conf` and the next case's restore removed it.

It is not a disk rollback, deliberately: the container runs `cap_drop: ALL`,
`no-new-privileges` and has no libvirt socket, and handing it the hypervisor would trade a
real security property for convenience. The disk reset stays an operator action between
runs.

## What's left

### 1. The agentic lane shows no incumbent lift, so decide what the bar actually is

**Answered 2026-09-03 at full power.** Run 28, n=31: `skill:omarchy` lifts
`omarchy-agentic-stale-advice` by **+1.9 pt, p = 0.59**, with the effect decaying
monotonically as n grew (+11.1 at n=3, +8.3 at n=10). The power calculation asked for 62
cases per variant and the run has exactly that, so this is a null rather than an
underpowered result.

Run 29, the matching control, is **void**: a case left a VM unreachable and the runner fed
eleven subsequent cases to the dead host, all of them the same variant. That is fixed and
tested, so a re-run is now safe, but a difference-in-differences cannot rescue a null. The
control is worth re-running only to answer a separate question, which is whether the skill
actively *degrades* general Linux performance. The void run hinted at -5.5 pt. That number
came from the corrupted arm and means nothing, but the question is real and cheap to settle
at about four hours.

What remains open is the bar itself, not the measurement:

- The chat lane's **+29.3 pt** is the only demonstrated skill effect in this repository.
- "Do not regress the incumbent on the agentic lane" is trivially satisfiable, because there
  is nothing there to regress.
- So a corpus-backed skill either shows a surviving agentic lift at n=31, which would be new,
  or it competes on the chat lane where the incumbent actually wins.

Still true and unchanged: only **4 of 14** local models can drive the loop at all
([skillbench/MODELS.md](skillbench/MODELS.md)), so difficulty is not the lever, wrongness is.

### 2. 150 records have no `title` (**DONE 2026-09-03**)

All 150 written and merged. **Every record now carries a title** and no generated heading
is a bare slug.

Worth recording *why* they were missing, because it says something about the harvest: the
gap was not scattered. It sat in **exactly six categories at 23-27 records each**
(`audio-input`, `hyprland-config`, `display-monitors`, `wayland-compat`, `pacman-aur`,
`omarchy-core`): one harvester pass that never emitted the optional field, not 150
independent omissions. `title` is optional in the schema and nothing validated it, so the
gap survived two audits and only surfaced when the site was rendered and a third of the
pages were headed `screenshare-black-screen-no-portal`.

Written from each record's own `symptom`, in the voice the existing titles already used:
imperative and specific, naming the error where there is one. Applied through
`corpus.write_jsonl` so field order, LF and UTF-8 stayed pinned, and verified as a
title-only change: **0 non-title field differences across all 456 records**, 150 titles
changed, every one of them previously empty.

The site's slug-prettifier is now dead code for this corpus but is kept: `title` is still
optional, so the next harvest can reintroduce the gap.

### 3. Finish auditing 28 records (**DONE 2026-09-01**)

All 28 audited: 12 `ok`, 15 `corrected`, 1 rejected and removed. No record carries
`gapfill-unaudited` any more. See the 2026-09-01 session entry above.

**The recipe that used to live here was wrong, and is worth keeping as a warning.** It
said to edit `GAP_CATEGORIES` down to those two categories and re-run the gap-fill
workflow. That list drives the *harvest* phase, and the harvest had already succeeded:
those 28 records **are** its output; only `gapfillAudit` came back `NONE`. Running it
would have re-harvested the same topics as `-2` suffixed duplicates and left all 28
exactly as unaudited as before. Track B has no audit-existing path at all; that shape
exists only in Track A, hardcoded to `apps-services`.

### 4. Stale `cause` fields on first-pass corrected records (**DONE 2026-08-30**)

All 130 reviewed, 22 rewritten, each stamped `cause_reconciled`. The "~130" was a
worst-case bound on an unreviewed population, not a defect count. See the 2026-08-30
session entry above.

### 5. The corpus tooling has no tests, and one script is unread (**DONE 2026-09-01**)

Closed by the second session of 2026-09-01. `ingest.py` did carry the predicted defect;
there is now one `FIELDS` in `corpus.py` and 13 stdlib tests, verified against the defect
rather than merely run green. The four-consumer checklist is written into CLAUDE.md and
two of the four are now checked automatically. Original text follows.


New, and a direct consequence of what the 2026-09-01 audit turned up. Two defects in
`merge_gapfill.py` would have silently destroyed the `cause_reconciled` provenance, and
**nothing in the repo would have caught either**: `skillbench/tests/` covers the bench,
and there is no test anywhere for `build_db.py`, `ask.py`, `merge_gapfill.py` or
`ingest.py`.

Two concrete follow-ups, in order of value:

- **A round-trip test that asserts every schema field survives a merge.** This is the
  cheap one and it catches the exact class of bug that got through: the writer projects
  records onto an allowlist (`FIELDS`), so adding a schema field without updating that
  list drops it with no error. A fixture record carrying every field, merged and read
  back, would have failed loudly on 2026-08-30.
- **Read `ingest.py` for the same defect.** It was out of scope on 2026-09-01 because it
  is the *replace* path rather than the *extend* path, but it writes the corpus too and
  may well share the projection pattern. Do this before it is next run, not after.

Also worth writing down: adding a field to the record schema currently has **four**
consumers and no checklist: `schema.sql`, `build_db.py`, `ask.py`, `merge_gapfill.py`.
Three were updated when `cause_reconciled` landed and one was missed.

Full detail in
[writeups/2026-09-01-merge-gapfill-silent-defects.md](writeups/2026-09-01-merge-gapfill-silent-defects.md).

### 6. The corpus prose has not been through the writing standard

Everything outside `research/data/problems.jsonl` was audited against
`writing-and-responding` on 2026-09-03 and is clean. **The corpus itself was deliberately
left alone**, and it is the largest remaining body of prose in the repo.

The measurement: **1,891 em and en dashes across 424 of 456 records**, concentrated in
`fix` (658), `audit_note` (412), `danger` (253), `cause` (255) and `symptom` (247). Those
render straight onto the public site's record pages and into `research/docs/`, so the
front page now reads to one standard and the 456 pages behind it do not.

Three things make this bigger than a find-and-replace, and they are why it was not done
in the same pass:

- **It edits the source of truth.** Every change goes through `corpus.write_jsonl` to keep
  field order, LF and UTF-8 pinned, and the commit has to carry a regenerated
  `research/docs/` with it. Same shape as the 150-title pass in item 2, which is the
  precedent to copy: apply through `corpus.py`, then assert **0 differences in any field
  you did not mean to touch**.
- **`audit_note` is the auditors' own words.** Rewriting it edits the evidence rather than
  the presentation. Decide explicitly whether it is in scope before starting; the
  defensible position is that it is composed text like everything else, but the decision
  belongs in the commit message either way.
- **A dash inside a fenced block or an inline code span is exempt**, and `fix` is mostly
  fenced commands. A blind pass over the raw field will corrupt commands.

Do not fix these piecemeal. A partial pass leaves the untouched records looking like a
deliberate editorial choice rather than work not yet done.

### 7. Optional / not started

- `opinionated-omarchy/` still holds no skill. Settled: this is where it goes, the one
  that turns the corpus into something an agent can consume. It now carries an orientation
  file (`opinionated-omarchy/CLAUDE.md`) recording what the skill has to be, the
  +29.3 pt / −2.3 pt baseline it has to beat, and the provenance it must not launder; that
  file replaced the `.gitkeep`.
- Spot-checking the corpus against a real install is **started, not finished**; see
  [research/validation/](research/validation/). One scenario exists and passes 6/6; it
  also turned up three wrong claims in the record it validated, none of which the source
  audit caught. The next steps are more scenarios (the `boot-kernel` records with
  `danger` set are the highest-value targets, and the cheapest to test given a 0.76 s
  reset), and feeding a working scenario into the agentic bench as a `seed:`/`post:`
  pair, which is what item 1 needs.
- The three record defects found on 2026-09-01 are **written up but not applied**. They
  need an audit pass through `merge_gapfill.py` so the corrections carry an `audit_note`
  and a `cause_reconciled` stamp.
- `research/` root holds ~17 loose Hyprland wiki pages. Not corpus, no tooling reads them.
  Left in place deliberately.

## Session of 2026-08-28/29: the Skill Bench landed

Two things happened: the lab's skill-efficacy data was brought into this repo, and a
dedicated bench container was built here to extend it.

### 1. This workstation is `ohmy-omarchy`, and that changes what is easy

Worth stating plainly because it was not obvious: the dev box **is** the lab's local LLM
endpoint. RTX 3090, Ollama on `0.0.0.0:11434` with eleven models, including `qwen2.5`,
the exact model every nexus1 Omarchy measurement was taken on. Docker 29.7.2 was already
installed and running.

So the bench needs no LiteLLM, no API key, no cloud, and no lab round-trip. Routing
through nexus1 would mean ohmy-omarchy → nexus1 → ohmy-omarchy, since nexus1's LiteLLM
points back here.

### 2. The nexus1 baseline is recorded: [research/bench/](research/bench/)

911 graded cases, ten models, twelve runs, pulled from the lab's Postgres with the bench
specs and skill provenance alongside. The headline: **the Omarchy skill lifts
Omarchy-specific tasks +29.3 pt on average and the general-Linux control tasks −2.3 pt.**
That gap is the whole argument: a skill that merely made answers longer would lift both.

`omarchy/SKILL.md` here is **byte-identical** to what nexus1 benched (sha `a8d88cf…`), so
those numbers are a baseline to reproduce, not merely a reference. `diagnose-crash` is
**not** identical (5710 bytes here vs a 4173-byte asset there); treat its figures as
indicative only.

It is in `research/bench/`, not `research/docs/`, because
[`build_db.py:167`](research/tools/build_db.py) unlinks every `*.md` in `docs/` before
regenerating. A hand-written page there survives until the next corpus build.

### 3. [skillbench/](skillbench/), a bench container in this repo

Omarchy-only port of the lab's Skill Bench: one container, local Ollama, SQLite,
`http://127.0.0.1:8878`. Dropped as unnecessary: LiteLLM, Postgres, Authelia, budget
guard, cost projection, model registry, the paid lane, and 14 non-Omarchy benches.

Two deliberate improvements over the original, both methodology rather than features:

- **Skills are bundles.** nexus1 could inject only a single `SKILL.md`, so instructions in
  a topic guide could never lift a score; its own backlog called every measured lift *"a
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

The lift reproduces and the token counts are near-identical: the skill body is the same
and injected the same way. Absolute levels are higher on both sides, most likely the
serving path (LiteLLM vs direct Ollama) plus weights moving under the same tags.

**The lesson that came out of it:** benches and skills are sha-pinned, but **model weights
cannot be pinned**. Trust deltas within a run; distrust absolute scores across runs
separated by time. Written up in both READMEs.

### 4. The firewall gotcha, again, in a new costume

Containers could not reach Ollama. Cause: Omarchy's `ufw` is default-deny incoming and
Docker manages only forwarding, **the same family as the `virbr0` DHCP gap**, which is
now written up as one pattern in [CLAUDE.md](CLAUDE.md) rather than two incidents.

The subtlety worth keeping: an interface-scoped rule on `docker0` does **not** work,
because Compose puts the container on its own generated bridge. `compose.yaml` therefore
pins the network to `172.28.7.0/24` so the rule can name it.

### 5. Housekeeping

`omarchy-old/` deleted: its purpose was never recorded and could not be reconstructed.
`opinionated-omarchy/` is confirmed as the destination for the skill this repo is building.

## Where the references are

| What | Where |
| --- | --- |
| Corpus design, schema, trust model | [research/README.md](research/README.md) |
| The 456 records (source of truth) | `research/data/problems.jsonl` |
| Generated per-category reading | `research/docs/*.md` |
| The public site | <https://techluddite.github.io/opinionated-omarchy/> |
| Site generator, and the CI that publishes it | `research/tools/build_site.py`, `.github/workflows/pages.yml` |
| Which local models can run the agentic lane | [skillbench/MODELS.md](skillbench/MODELS.md) |
| Is a measured lift real? | `skillbench/tools/lift_test.py` |
| Search / build / ingest tooling | `research/tools/` |
| Deep-research report (13 verified findings, 12 refuted folk fixes) | `research/raw/deep-research-report.json` |
| Raw workflow output, kept for provenance | `research/raw/harvest-result.json`, `research/raw/gapfill-result.json`, `research/raw/audit-28-result.json` |
| Post-mortems worth keeping outside the journal | [writeups/](writeups/) |
| Gaps the auditors named | `research/raw/gapfill-todo.json` |
| Per-category harvest/audit counts | `research/raw/harvest-stats.json` |
| Test VM build / viewer scripts | `tools/make-test-vm.sh`, `tools/view-test-vms.sh` |
| Test VM credentials, VNC ports, ufw rules | [CLAUDE.md](CLAUDE.md) → "Test VMs" |

The refuted list in the deep-research report is worth a read on its own; it is mostly
widely repeated folk fixes that primary sources actually contradict.

## Gotchas that cost time

Full list in [CLAUDE.md](CLAUDE.md). The ones that bit hardest:

- **`basecamp/omarchy`'s default branch is `quattro`, not `master`.** `master` is still
  the Omarchy 3 tree and several raw URLs 404 against it.
- **Omarchy 4 is pacman-packaged at `/usr/share/omarchy`**, not a git checkout in
  `~/.local/share/omarchy`. Most stale advice online assumes the old layout.
- **`wiki.archlinux.org` is behind Anubis anti-bot**; `WebFetch` gets "Access Denied".
  Use `index.php?title=X&action=raw` or `rest.php/v1/page/X`.

From the VM work, and both cost real time:

- **Omarchy's host `ufw` silently blocks libvirt DHCP.** It runs default-deny with `INPUT`
  policy `DROP`, and libvirt's nftables table only manages the `forward` hook, so nothing
  opens port 67 and guests retry DHCP forever with no lease and no IP. What makes it
  genuinely confusing is that it only shows up *after* a completely successful install: the
  5.9 GB ISO carries an offline package set, so the install never needs the network and the
  machine looks fine right up until it boots. Fix is three `virbr0`-scoped rules in
  [CLAUDE.md](CLAUDE.md).
- **`/usr/share/omarchy/version` is branding, not a version.** It reads `4.0.0.alpha` on the
  workstation *and* in a 4.0.1 VM. The number that means anything is `pacman -Q omarchy`.
  A version comparison built on that file will be wrong and look authoritative.
