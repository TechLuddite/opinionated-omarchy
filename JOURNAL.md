# Journal: handoff

Last updated: 2026-09-11

> ## START HERE: the next session is about getting back on track
>
> The operator's reading on 2026-09-06, after this repo's published pages were audited and
> found to reproduce: **the corpus needs massive expansion and deep auditing, and the
> skill phase has not started.** Everything in this journal since 2026-08-29 has been the
> bench, and the bench has spent most of that time catching its own defects. The next
> session is not another bench session.
>
> **What "back on track" means, in the order the dependencies run:**
>
> 1. **Expand the corpus.** 456 records across 12 categories is the harvest of one
>    interrupted workflow plus one gap-fill pass. `CLAUDE.md` "Regenerating the corpus"
>    names the three workflow scripts, what each does, and that `harvest-workflow.js`
>    costs about 35 agents. Check `/usage-credits` first; the first harvest died on a spend
>    limit. Pass the corpus root in `args`. Every new record lands with its provenance
>    marked, never blended in as audited.
> 2. **Audit deeper.** The last 4 `unaudited` records and the three VM-found defects were
>    applied on 2026-09-06 (second session below), and all four unaudited records turned
>    out to be wrong. What remains is the larger point: `audit_status: ok` still means
>    "matches its sources", which the first live scenario showed is not "true on Omarchy
>    4", and 207 records carry that status on one source pass. The first 32 re-audited
>    for that, boot-kernel and pacman-aur records with a `danger`, all needed correcting. Use
>    `audit-existing-workflow.js` for records that exist, and `research/validation/` for
>    the ones a VM can reach. Six ways forward, O1 to O6, are item 8 under "What's
>    left": O1 (lint) and O2 (workflow prompts) are done, O3 has cleared `boot-kernel`
>    and `pacman-aur`, and O4 is harvested, reconciled and audited: 36 records banked unmerged as of 2026-09-11, all 36
>    corrected by the audit. The corpus prose has 1,756 dashes across 405 records, item 6
>    under "What's left", and is its own job.
> 3. **Then the skill.** The design is settled in `opinionated-omarchy/CLAUDE.md` and does
>    not need re-deriving; it needs a corpus worth retrieving from. The root `README.md`
>    now says in public that the skill is vaporware. Make that stop being true in that
>    order, not the other way round.
>
> **Carried forward from the bench, not the priority:** runs 43 to 46 are void (opencode
> auto-rejecting tool calls outside its working directory, no error on the case, the
> control hit too) and need repeating with the permission grant now in `app/runner.py`.
> The recipe is in the 2026-09-05 fourth session. `omarchy-agentic-published-wrong` is not
> calibrated. The chat-lane result (+22.6 to +28.8 pt on four models, controls flat) and
> the n=31 agentic null (DiD +0.2, p=0.98) stand.
>
> **State of the record:** every figure on the seven published pages was recomputed on
> 2026-09-06 and reproduces from the repo. Trust the pages as of that date; recompute
> before quoting anything newer.

## Session of 2026-09-10 and 2026-09-11: O4 harvested, reconciled and audited. 36 of 36 records were wrong

Steps 2 and 1 of the O4 pick-up list, in that order: the duplicates reconciled, then batch
01 read, then a second duplicate pass on 2026-09-11 that found three groups the first pass had
missed, then the audit of all 36. **Every one of the 36 came back `corrected`.** Nothing was clean
and nothing was rejected, so the problems are all real and the detail was all wrong somewhere.
`data/problems.jsonl` is untouched and still reads `ok` 207 / `corrected` 249 / `unaudited` 0.
The banked set is [research/raw/issue-harvest-reconciled.json](research/raw/issue-harvest-reconciled.json),
batch 01 on its own is `raw/harvest-01.json`, and `issue-harvest-partial.json` is left exactly
as the workflow wrote it, so the provenance of what the harvesters actually produced survives.

### 1. Nine groups, found in two passes, and the first pass was not good enough

The banked payload listed six `near_duplicates_to_reconcile` pairs. Three of those pairs
share a record, so they are five groups covering eleven records. A similarity pass over all 40,
token-set Jaccard on title plus symptom plus cause at a 0.25 threshold, found a sixth group the
harvest's own detector missed: the two plugin-lock records, from issues 7106 and 9441, which
are one defect with two outcomes. Thirteen records became six.

**That threshold was too high, and it cost a second pass.** On 2026-09-11, while batching the
records for audit, two of them turned out to be the same defect by reading their titles side by
side: `nvidia-env-forced-on-igpu-primary-hybrid-laptop` and
`libva-driver-name-nvidia-forced-on-hybrid-laptop`, both blaming
`/usr/share/omarchy/default/hypr/nvidia.lua`, both citing commit `33d7363c`, both fixed by the
same `hl.env` override. They score 0.231. Re-running the sweep at 0.15, and adding two signals
that do not depend on wording, found two more: the two migration 1786643346 records at 0.214
and the two VMware records at 0.160.

The two signals are worth keeping for any future dedup, because each one caught a pair on its
own: **a source URL shared between two records**, and **two or more shared file paths**. Two
harvesters writing up the same defect agree on the file they blame long before they agree on
prose. After the second pass the only candidate left is two records that happen to cite the
same release tag, which is not a duplicate.

Nine groups over nineteen records became nine records. 40 plus batch 01's six, minus ten, is 36.

| group | records in | kept |
| --- | --- | --- |
| installer ESP mount failure | 2 | `installer-mounting-the-esp-failed-squashfs-superblock` |
| AMD AV1 firmware corruption | 2 | `av1-video-color-corruption-linux-firmware-amdgpu-20260810-1` |
| Codex limits unavailable | 3 | `codex-limits-unavailable-agents-panel` |
| Gemini default agent | 2 | `default-agent-gemini-fails-antigravity-replacement` |
| migration 1787515927 | 2 | `omarchy-update-migration-1787515927-fails-bash-5-3` |
| plugin write while locked | 2 | `plugin-file-write-while-locked-strands-session` |
| NVIDIA env on a hybrid laptop | 2 | `nvidia-env-forced-on-igpu-primary-hybrid-laptop` |
| migration 1786643346 | 2 | `migration-1786643346-browser-window-open-loop` |
| VMware shell black desktop | 2 | `vmware-shell-black-desktop-qt-quick-dmabuf` |

The records outside those groups are carried through byte-identical and in their original
order, and the `existing` and `skipped` lists are untouched.

### 2. Reconciling is not deduplicating, and six groups disagreed with themselves

Every group was read in full and settled against upstream sources and this workstation
rather than by keeping the longer record. What that turned up:

- **The two ESP records disagreed about the cause.** One blamed a bare `mount` with no
  `-t vfat` on the freshly created EFI partition, naming `omarchy-iso#111`. The other
  blamed the free-space path for expecting an ESP that was not there. The installer source
  settles it: that path always creates its own EFI partition and never adopts an existing
  one, so the device in the SQUASHFS message is always the partition it just made, and the
  `sda2` in the second thread is that partition in the lowest free GPT slot. The second
  cause was discarded. Its workaround, hand-creating an EFI partition first, is kept and
  labelled as reported twice with no known mechanism.
- **A fix had shipped under us.** Both plugin-lock records said `PR #9485` was in no tagged
  release. `v4.0.3` was published on 2026-09-08, two days before this session, and contains
  commit `d3d23fdd`: `unloadPluginServices` at that tag consults `serviceKeepLoaded`. The
  merged record says update to 4.0.3 rather than wait.
- **Two records contradicted each other about `omarchy-restart-shell`.** One said it refuses
  while locked, the other offered it as the recovery step. Lines 28 to 36 of the installed
  script show both are half right: it refuses while the wedged lock service still reports
  `.secure` or `.requested`, and it re-locks a fresh shell when neither is true. The merged
  record states the condition instead of the conclusion.
- **Three dates were wrong or uncheckable.** Arch published `linux-firmware-amdgpu
  20260810-2` on 2026-08-14, not the 2026-08-15 both AV1 records claimed, per the Arch
  package archive listing. Those two also disagreed on when Omarchy's stable mirror picked
  it up, 2026-08-21 against 2026-08-24, and neither is checkable from here, so the merged
  record states the one hard local fact: this workstation upgraded to `-2` on 2026-08-22.
  The 2026-06-18 date both Gemini records gave for Google's cutoff is cited by nothing and
  was dropped rather than laundered into a merged record.
- **`#8952` is an open pull request, not an issue**, titled as the backport of `#6900`.
  Stable still ships Gemini at the `v4.0.3` tag: `install/user/mise.sh` runs
  `omarchy-mise-install gemini`, there is no `migrations/1786719479.sh`, and the packaged
  menu still lists `setup.default.agent.gemini`.
- **One record's placement advice was above the line that would have overridden it.** Of the
  two VMware records, one told the reader to add `QT_QUICK_BACKEND=software` immediately after
  the bootstrap `dofile` on line 4 of `~/.config/hypr/hyprland.lua`, which is above where
  `require("default.hypr.omarchy")` on line 14 loads Omarchy's own environment. It works for
  this variable only because Omarchy sets no `QT_QUICK_BACKEND` of its own, confirmed on
  4.0.2-1. The merged record says to put it below the `require` and says why.
- **The shipped stale-lock check is narrower than both migration records implied.** It tests
  `SingletonLock` and `SingletonSocket` only, read at line 129 of the migration on 4.0.2-1, so
  deleting `SingletonCookie` as both records advised is harmless but is not what unsticks it.

Local confirmations that went into the merged records, all on omarchy 4.0.2-1: line 531 of
`omarchy-agent-usage-codex` reads `-a on-request`, the `cleanup()` at line 82 of
`omarchy-theme-set-browser-policy` is an `if` block and line 16 of migration 1787515927 ends
in `|| true`, and `shell.qml` lines 348 to 354 still destroy every plugin service.

### 3. What the audit still owns

None of this is an audit. The reconciled file carries nine open questions, Q1 to Q9, one per
group, naming what a merge may not assume: whether `omarchy-iso#111` is the accepted fix and
why hand-creating an EFI partition helps, whether the RDNA4 quantizer-matrix mechanism
explains the RDNA3 integrated-GPU reports, the codex release note that retired `untrusted`,
the date Google cut individual accounts off, whether the migration reporters were on dev or
edge, `PR #7169`, the three competing gates proposed for the NVIDIA environment and the Pascal
case none of them fixes, whether `PR #7026` has merged, and whether the VMware failure has a
compositor-side fix in `hyprwm/Hyprland#12966`.

Three `lint_corpus.py` hits survive across the 36 records and all three are legitimate: two
`sudo pacman -Syu` inside a branch labelled plain Arch, and one `/boot/limine.conf` in a
symptom describing what a reporter saw in that generated file rather than telling anyone to
edit it. They are new hits, so `lint_corpus.py --check` will fail the first time these
records enter the corpus. Add them to `data/lint-baseline.json` in the merge commit rather
than rewording correct text.

### 4. Batch 01, the ten issues the 2026-09-07 run never reached

Read in full on 2026-09-10 against `issue-harvest-brief.md`, with every claim about what
Omarchy ships checked on this workstation (4.0.2-1) and against the `quattro` branch or a
release tag. Six records, four mapped onto records that already exist, nothing skipped.

| issue | outcome |
| --- | --- |
| 6868 | `ghostty-epoll-backend-segfault-write-queue` |
| 6882 | `windows-vm-launch-no-rdp-window-stale-log` |
| 6887 | `mise-stale-registry-attestation-install-failure` |
| 6894 | `quattro-upgrade-uki-missing-root-parameter` |
| 6909 | `internal-panel-forced-to-2x-scale-clamshell-poll` |
| 6917 | `screensaver-self-dismisses-and-session-never-locks` |
| 6858 | existing: `omarchy-lockscreen-no-keyboard-focus-after-resume` |
| 6888 | existing: the pending plugin-lock record, added as a third source |
| 6889 | existing: the pending Gemini record, already cited |
| 6890 | existing: `quattro-upgrade-incomplete-do-not-reboot` |

Two of the six are live defects on 4.0.2-1 with no merged fix, which is why they are worth
having. Omarchy ships `async-backend = epoll` in its Ghostty config as a workaround for
Hyprland slowness, and that setting selects a libxev backend with a null dereference in its
write path: six reporters, four Omarchy releases, one fault offset, and every window in the
single-instance process dies together. The removal is `omacom/omarchy#6963`, still open. And
the screensaver closes itself about a second after it opens whenever a bar panel holds
keyboard focus, which cancels the pending lock: one reporter measured 239 dismissals over two
days, 233 of them within 1.40 to 1.56 seconds, and an overnight run of 225 idle cycles in
which the session never locked at all. That is `omacom/omarchy#7102`, still open, and the
workaround is to turn the screensaver off so the lock path runs without it.

The `existing` notes are the more useful half again. The corpus record for the lock screen
not taking keystrokes scopes the defect to lid-open resume and tells the reader to edit
`~/.config/hypr/hypridle.conf`. Neither hypridle nor hyprlock is installed on Omarchy 4 and
no such file exists, and the thread shows the defect is one single-shot focus grab that five
separate paths lose, with three pull requests open and none merged. That record needs a
re-audit, not a tweak.

### 5. The audit: 36 of 36 corrected

21 agent batches of one or two records each, grouped by category, each handed `reaudit-brief.md`,
the record JSON and an output directory, exactly as the brief prescribes. Three facts were passed
in on top of the brief because they are newer than it: today's date, that `v4.0.3` is the newest
tag rather than `v4.0.2`, and that every cited issue and pull request state in these records was
written between 2026-09-07 and 2026-09-11 and had to be re-checked. That last one was not
hypothetical, since it is what the `v4.0.3` correction above came from.

The result is [research/raw/issue-harvest-audited.json](research/raw/issue-harvest-audited.json),
36 records carrying `audit_status`, `audit_confidence` and the auditor's reason verbatim as
`audit_note`, with `cause_reconciled` stamped on the 25 whose cause was rewritten.

| | |
| --- | --- |
| verdicts | 36 corrected, 0 ok, 0 rejected |
| confidence | 34 high, 2 medium |
| `fix` rewritten | 29 |
| `cause` rewritten | 25 |
| `danger` rewritten | 13 |
| `symptom` rewritten | 13 |
| `verify` rewritten | 12 |
| records with a `danger` | 16 of 36 |

**The fix field is where the defects live.** 29 of 36 fixes were rewritten, and the failures are
not subtle once someone runs them. A `sed` command could not run at all, because the substitution
used `|` as its delimiter while the replacement contained `||`. A `chmod g-s` promised mode 700 and
produces 777 from what the container actually leaves. A verify command grepped six lines after a
marker for a value printed five lines before it. Another called a script with no argument, so it
prints usage and fails even on a fixed system. None of these survive one attempt by a person at a
keyboard, which is the whole argument for the audit.

**Three fixes were actively harmful.** The screensaver record told the reader to run
`omarchy-toggle-screensaver` to restore locking, and that command is a flip, so on a machine where
the screensaver is already off it re-enables it and silently restores the unlocked session the
record exists to prevent. The fingerprint record stopped the daemon synchronously during resume,
which blocks the thaw for the stop timeout in exactly the wedged case the hook exists for. And the
boot record's example `root=` named a device that does not exist on an ISO-installed machine, so a
reader following it literally stays unbootable.

**Mechanisms were wrong even where the fix worked.** The installer ESP cause blamed an unsettled
udev re-read, and the script already runs `partprobe`, `sync`, a sleep, a device wait and `wipefs`
before formatting. The real mechanism is the untyped `mount` walking `/proc/filesystems`, where
`squashfs` is present on the live ISO and `vfat` is not. The pull request author had already removed
the settle and sleep from the patch after review, so our fix told readers to add two steps upstream
had dropped. The VMware cause blamed a rejected dmabuf modifier where the established mechanism is
a driver surface handle failing to close, disproved for modifiers by standalone tests. The Codex
cause described an 8 second timeout that never happens, because the read returns empty on the dead
child and raises immediately, measured upstream in single-digit milliseconds.

**Staleness inside three days.** One record pinned a guard to a line number read on 4.0.2-1, and
`v4.0.3` rewrote that file and moved it, so the auditor replaced the pin with a grep. Another had
its version floor corrected from one release to a range. A third had a release-note claim tightened
from "about three hours" to two hours forty-three minutes.

**Four of the nine open questions were answered, three of them against my own judgement.** The
Gemini cutoff date I dropped as uncited is citable: the issue links a Google developers blog post,
retrieved 2026-09-11, stating that Gemini CLI stopped serving individual accounts on 2026-06-18.
The Codex approval-policy change I declined to cite exists as `openai/codex#39630`, merged
2026-08-20. Q2 resolved to "do not split the AV1 record", because Arch's `-2` reverted every amdgpu
VCN blob and the Mesa fix is gated on the quantizer matrix rather than on any ASIC, so one
regression covers RDNA3 and RDNA4. Q5 resolved to both channels, with one reporter's own
`$OMARCHY_PATH` proving a dev checkout where they had written edge.

**The audit found two gaps in its own schema.** An auditor judged a severity wrong and had nowhere
to put it, because `reaudit-brief.md`'s verdict carries no `corrected_severity`, so the judgement
went into prose and was applied by hand. A second found a cited GitHub issue number that is really
a discussion and could only say in prose that the URL must be deleted, because a verdict can append
sources and never remove one. Both are recorded in the audited file under `audit.schema_gaps`, and
the brief needs both fields before the next run.

**Every source was then fetched.** 273 distinct URLs, all resolving except `api.fast.com`, which
answers 403 to an anonymous GET and is kept deliberately with that noted. Nine URLs were repaired by
hand: seven `omacom-io` organisation names normalised to the canonical `omacom`, one `blob/main` path
corrected to `blob/master`, and the discussion-as-issue URL removed.

### 6. Where to pick this up

1. Merge the 36, through `merge_gapfill.py`, dry-run on a copy first. Expect it to need a small
   change, because its append path assigns `gapfill-unaudited` and these records arrive audited.
   The records are already projected onto `corpus.FIELDS` key order.
2. Raise `screensaver-self-dismisses-and-session-never-locks` to `critical` if it is re-derived
   from the verdicts rather than taken from the audited file, since the verdict schema could not
   carry that change and it was applied by hand.
3. Add the 12 lint hits to `data/lint-baseline.json` in the same commit. Every one was read and
   every one is legitimate: plain-Arch branches, the documented `OMARCHY_ALLOW_DIRECT_PACMAN`
   bypass, and warnings that tell the reader not to run the matched command.
4. Add `corrected_severity` and `corrected_frequency` to `reaudit-brief.md`, and a way to remove a
   source, before the next audit run.
5. A commit touching `data/problems.jsonl` must regenerate `research/docs/` with it.

## Session of 2026-09-07 (second): O4 harvests from the issue tracker, and stops one batch short

O4, the option that says stop harvesting the web and read the upstream tracker instead.
Six corpus records had cited GitHub issues that did not support them, so the standard here
is narrow: **a record exists only where the thread carries a fix a maintainer or a second
reporter confirmed.** A plausible workaround nobody confirmed is not a record.

**Nothing from this reached the corpus, deliberately.** `data/problems.jsonl` is untouched
and still reads `ok` 207 / `corrected` 249 / `unaudited` 0. The harvest is banked as raw
provenance in [research/raw/issue-harvest-partial.json](research/raw/issue-harvest-partial.json),
which says so in its own `status` field.

### 1. What was built

- **[research/tools/issue_candidates.py](research/tools/issue_candidates.py)** selects what
  is worth reading: closed issues since the 4.0.0 release with at least two comments, plus
  the most-discussed open ones, minus the `enhancement` / `question` / `duplicate` /
  `invalid` / `wontfix` labels. It found **109 candidates**, 49 closed and 60 open, and
  writes `raw/issue-candidates.json` so the selection is reproducible rather than a
  judgement made once in a prompt.
- **[research/tools/issue-harvest-brief.md](research/tools/issue-harvest-brief.md)** is the
  harvester prompt. It requires reading `reaudit-brief.md` first, reading each issue in full
  with its comments and linked PRs, grepping the corpus before writing a slug, and sorting
  every assigned issue into exactly one of `records`, `existing` or `skipped`.

### 2. What came back

Eleven harvesters, ten issues each. **Ten of eleven finished; batch 01 died on the weekly
limit** and its ten issues (6858, 6868, 6882, 6887, 6888, 6889, 6890, 6894, 6909, 6917) were
never read. From 99 issues:

| | |
| --- | ---: |
| records written | 40 |
| issues mapped to an existing record instead | 21 |
| skipped as unconfirmed, feature requests or duplicates | 37 |

The skip rate is the point. Thirty-seven threads had no fix anyone confirmed, and under the
old standard several would have become records.

The `existing` list is the more valuable half and is **re-audit fuel for O3**: it names
records whose cause the tracker contradicts. Among them, `chromium-video-black-hybrid-angle`
(the variable comes from `nvidia.lua`, went live in 4.0.1, and needs a logout),
`laptop-display-stays-dark-after-external-unplug` (the cause is Hyprland 0.56's FALLBACK
output, not a stale monitor list), and `suspend-fails-nvidia-video-memory` (carries a
`mkinitcpio -P` defect the lint already flags).

### 3. Why it was not merged

Two blockers, either one sufficient:

- **No audit pass.** These are harvester output. Every other record in the corpus was
  audited by a second agent before entering it, and the whole 2026-09-06 finding is that
  one pass is not enough.
- **Six near-duplicate pairs, two of them certain.** `ingest.py`'s own symptom-fingerprint
  detector flags them, and two cite the same issue number from different batches
  (7514 and 8833). Two batches independently wrote the AV1 firmware corruption and the
  bash 5.3 migration failure. The pairs are listed in the banked payload under
  `near_duplicates_to_reconcile`.

Merging would also have put 21 `omarchy-core` records into a category that has 2 `ok`
records with a `danger` today, skewing the corpus toward the tooling and away from the
hardware problems users hit.

### 4. Two live facts changed under us, both now corrected

- **The upstream repo is `omacom/omarchy`, renamed from `basecamp/omarchy`.** The old name
  redirects for `gh issue view` and raw content, but **GitHub's search API does not follow
  it** and returns a 422. That cost the first sizing run. Corrected in the domain facts and
  in `reaudit-brief.md`.
- **This workstation is `omarchy 4.0.2-1`**, not the 4.0.0-1 `CLAUDE.md` claimed. Caught by
  a harvester checking a fix against the local install. The VM figure is left as last
  measured and labelled as unverified, because the VMs were not booted today.

### 5. Where to pick this up

1. Run batch 01: `gh issue view <n> -R omacom/omarchy --comments` for the ten numbers above,
   with `issue-harvest-brief.md`. DONE 2026-09-10: six records, four mapped onto existing
   records, nothing skipped. See the 2026-09-10 session.
2. Reconcile the six near-duplicate pairs into one record each. DONE 2026-09-10, and it
   was six groups over thirteen records rather than six pairs. See the 2026-09-10 session
   and `raw/issue-harvest-reconciled.json`.
3. Audit all 40 with `reaudit-brief.md`, one agent per one or two records.
4. Only then merge, through `merge_gapfill.py`, dry-run on a copy first, and expect
   `merge_gapfill.py` to need a small change: its append path assigns `gapfill-unaudited`
   and these records will arrive already audited.

## Session of 2026-09-07: all 22 pacman-aur records re-audited, all wrong, and the lint earned its keep

O3 on `pacman-aur`: the 22 records that were `ok` with a `danger` and apply to Omarchy,
one auditor per two records, the same brief as the boot-kernel batch plus a section of
pacman facts read off this workstation (the guard script, `DownloadUser = alpm`, the
`[omarchy]` repo, `HoldPkg`, yay from the Omarchy repo and no paru). Eleven auditors were
launched; five died on a session limit, but three of those had already written both
verdicts, so **18 of 22 records came back, all `corrected`, all at high confidence**. The
operator paused there, then resumed for the four lost records with two more auditors:
all four `corrected`, three at high confidence and `local-package-database-corrupted` at
medium. Section 4 has them. O3 stops after this category.

### 1. What was wrong, again in clusters

- **Every upgrade command was `sudo pacman -Syu`**, which the guard aborts. Sixteen of
  the eighteen. The Omarchy form is `omarchy update`, or the one-transaction bypass.
- **Omarchy already does the thing the record tells you to do**, and the record did not
  know: `omarchy-update-keyring` refreshes the keyring before every update,
  `omarchy-update-pkg-prune` runs `paccache -rk2`, `omarchy-update-system-pkgs-when-conflicted`
  moves conflicting `omarchy*` files aside and retries, `omarchy-update-requires-free-space`
  refuses to run under 10 GiB free, and `omarchy-update-aur-pkgs` runs yay with
  `--cleanafter`. `pacman-contrib` is a hard dependency of `omarchy`, so four "install it
  first" lines were no-ops.
- **The mirror model is different.** Omarchy 4's mirrorlist is one line,
  `stable-mirror.omarchy.org`, a pinned snapshot that lagged Arch by twelve days on the
  day of the audit; the maintainer tells users not to run reflector. Rolling Arch back
  through the archive while the `[omarchy]` repo, which has no archive, stays current
  produces a mismatched system, so the ALA record now leads with the Snapper and Limine
  Snapshots restore.
- **Three records cited evidence that did not support them.** Issue 4197 is a keyring
  case cited for a checksum claim, issues 3877 and 3902 are Omarchy 3.2 with a yay built
  against an older libalpm (yay 13 dlopens `libalpm.so.16` and cannot produce the loader
  error at all), and issue 3497 is Omarchy 3 behaviour for `omarchy-refresh-pacman`,
  which `omarchy update` on 4.0.2 never calls.
- **Four claims were disproved from pacman's source.** The HoldPkg prompt fires only in
  `pacman -R`; `ignoring package upgrade` never reaches `pacman.log`; a provider question
  under `--noconfirm` picks the first provider silently rather than aborting; and
  `nvidia-dkms` no longer exists in the repos.
- **`omarchy-update-overwrites-pacman-conf` describes Omarchy 3.** On 4.0.2 the file is a
  pacman backup file, gets a `.pacnew`, and the supported way to keep a custom repo is the
  `pre-refresh-pacman` hook Omarchy ships a sample for.

### 2. The lint caught the auditors

`lint_corpus.py --check` ran after the merge and flagged three new hits. One was a
labelled plain-Arch aside and went into the baseline. The other two were the auditors'
own `sudo omarchy-snapshot create`, in two rewritten fixes, and `omarchy-snapshot` calls
sudo itself and reads `OMARCHY_PATH`, which sudo strips. That is the shape the lint was
built from one day earlier, written fresh by an agent holding the brief that names it.
Both records were patched through `corpus.write_jsonl` with a sentence appended to the
audit note, and the baseline was rewritten deliberately: 139 records, the three changes
listed in the commit.

### 3. Verified, and not

Dry-run then diff: exactly eighteen records changed, only in the named fields, and the
four records without a verdict came through untouched. `research/tests/run.sh` passes
(18), the site builds. Nothing was exercised on a VM, no stale keyring, lock or conflict
was induced, and the six verdicts from auditors that died after writing were read in full
rather than trusted on their status.

After the first eighteen: `ok` 211 / `corrected` 245.

### 4. The four lost records, and a sibling audit catching an applied one

The four came back with the same shapes plus two the batch had not seen. The hook-failed
record's title and cause were the opposite of what happens on Omarchy: the commonest source
of `command failed to execute correctly` here is the update guard, the only hook on the
machine with `AbortOnFail`, and it installs nothing. Its sample output cannot occur at all
(no presets, and limine-mkinitcpio-hook's script swallows build failures and fails only on
the ESP check). The database record gained the recovery Omarchy makes cheap: every
`omarchy update` snapshots the root subvolume, and `/.snapshots/N/snapshot/var/lib/pacman/local`
is a complete copy to restore from. The AUR record quoted yay 12 text that yay 13 does not
print. The disk-full record now says the 10 GiB check runs before the prune, so under
10 GiB `omarchy update` frees nothing.

One of those auditors also read `omarchy-update-aur-pkgs` and contradicted a claim the
yay-libalpm verdict had made and I had merged the day before: that `omarchy update` aborts
at the AUR step. The script runs yay inside an `if` body whose last command is `echo`, so
it exits 0 whatever yay returned and the update continues. Confirmed by reading the script,
the applied record's symptom was rewritten and its audit note says what was wrong and who
caught it. Two auditors, two readings of the same file, and the one that read it more
carefully was right. That is the argument for reading every verdict rather than trusting
its confidence field.

The lint flagged two new hits after the merge, both legitimate (a labelled plain-Arch line
and a symptom block that shows the guard firing), and the baseline is now 140 records.

The corpus is now **456 records, `ok` 207 / `corrected` 249 / `unaudited` 0**, 925
distinct sources, 55 `cause_reconciled` stamps across four dates, 1,756 dashes across 405
records. Thirty-seven `ok` records have been checked against Omarchy 4 since 2026-09-06,
and thirty-seven needed correcting.

## Session of 2026-09-06 (second): the last four unaudited records, the VM findings, and ten boot-kernel re-audits

Item 2 of the START HERE block, the part that did not need a 35-agent harvest. Four
records had carried `unaudited` since the first harvest's auditors never returned a verdict
for them, and the three defects the 2026-09-01 VM scenario found in
`mkinitcpio-pacnew-unhandled-breaks-next-boot` had sat in `research/validation/README.md`
unapplied. All five are now `corrected`, each with an `audit_note` naming what was checked
and where, and no record carries `unaudited`.

### 1. All four unaudited records were wrong, and one was wrong about its own cause

One auditor per record, against the primary sources with the fetch workarounds in
`CLAUDE.md`, and against this workstation where the claim was checkable locally. Every one
came back `corrected` at high confidence:

- **`resume-hook-after-filesystems-hibernation`**: the cause is disproved by mkinitcpio's
  own `init`, which runs every hook's `run_hook` before it mounts root on `/sysroot`, while
  `filesystems` has no runtime script at all. The Arch wiki's own example puts `resume`
  after `filesystems`. Issue basecamp/omarchy#8471, the record's main source, has no
  comments and its reporter says they could not demonstrate a failure from the ordering.
  The cold boots people actually report are basecamp/omarchy#8352: `nvidia.sh` early-loads
  the NVIDIA modules into the initramfs on hybrid laptops, the freeze callback returns -5,
  and the kernel discards the image. Symptom, cause, fix and danger all rewritten. The old
  fix also edited `/boot/limine.conf`, which `limine-entry-tool` regenerates, dropped
  `plymouth` from its example HOOKS line, and named the swap UUID where a btrfs swapfile on
  LUKS needs the mapper device. The new fix was not exercised with a hibernate cycle, and
  the audit note says so.
- **`xwayland-game-flicker-explicit-sync`**: the version floors hold. The fix said Kepler
  needs the 535xx branch; Kepler ended at 470 and no driver it can run has explicit sync,
  while Maxwell through Volta sit on 580xx, which already exceeds the 555 floor. `hl.set`
  does not exist, and `sudo pacman -Syu` is blocked by the ALPM guard. The danger
  overstated the lib32 risk: the AUR lib32 packages pin an exact `nvidia-utils` version and
  conflict with the repo one, so pacman refuses the mismatch. Its raw `Variables.md` source
  URL now 404s and was replaced.
- **`virtiofs-share-requires-shared-memory`**: XML, mount syntax and session-mode ID
  mapping all verbatim from libvirt's kbase and the Arch wiki. The danger was wrong for the
  fix it accompanied: `<source type='memfd'/>` builds `memory-backend-memfd` with no
  `mem-path`, so nothing lands under `memory_backing_dir`. The cause never explained the
  `unknown filesystem type 'virtiofs'` line, which is a guest kernel older than 5.4.
- **`tearing-and-vrr-not-working`**: every Lua form, option value and `hyprctl` command
  checked on this Hyprland 0.56.2 machine, including `hyprctl eval` live. The gamescope
  line was attributed to the Arch Gaming page, which does not carry it, and the "panels
  change perceived brightness with refresh rate" mechanism appears in no cited source. The
  cause now attributes flicker to a narrow VRR range, as the Arch VRR page does, and the
  fix gains the wiki's own `tearingBlockedBy` diagnostic.

The same shape as 2026-09-01: sound advice, mis-specialised, and one record whose cited
issue does not support its claim. Every audit note names the sources, and the sources an
auditor relied on that the record did not list were appended to it.

### 2. The VM findings are applied, and the merge tool can now carry them

`merge_gapfill.py` honoured only `corrected_fix` and `corrected_cause`. Two of the three
2026-09-01 findings were a wrong `symptom` and an overstated `danger`, so there was no
honest way to apply them. It now honours `corrected_symptom` and `corrected_danger` the
same way, and appends any `sources` a verdict carries. One test covers all three, and the
suite is 14 tests, all green.

The pacnew record's verdict was written from the validation findings plus ownership checks
on this workstation: `/etc/default/limine` is owned by no package, the package-owned
template is `/etc/limine-entry-tool.conf` from `limine-mkinitcpio-hook`, and the file on
Omarchy 4 that can both get a `.pacnew` and carry the hook list is
`/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, a backup file of `omarchy-settings`. The
symptom now quotes the right files, the cause names the right owners, and the danger says
what overwriting each one actually does on Omarchy 4 versus plain Arch. The fix stands.

### 3. Verified

Dry-run on a copy of the corpus first, then the real merge produced a byte-identical
file. Exactly five records changed and only in the fields the verdicts named. The verdict
set was scoped to those five slugs, and the 152 other records in the four affected
categories came through with every field unchanged. `build_db.py` regenerated four
category pages, `research/tests/run.sh` passes, and the site builds.

After this batch the corpus was **456 records, `ok` 239 / `corrected` 217 / `unaudited`
0**, with 33 records stamped `cause_reconciled`. Section 5 moves it again.

### 4. What this does not change

`audit_status: ok` still means "matches its sources". Nothing here was exercised on a VM
except the pacnew record, whose scenario already passed 6/6. The rewritten hibernation fix
in particular is built from two issue threads and the setup script, not from a hibernate
cycle, and a scenario for it needs a hybrid laptop these VMs cannot imitate. Item 1 of
START HERE, the harvest, is untouched: it needs a `/usage-credits` check and an explicit
decision to spend about 35 agents.

### 5. Ten boot-kernel records re-audited for Omarchy 4: ten out of ten were wrong

The four unaudited records and the pacnew finding share one shape: sound Arch advice that
was never checked against what Omarchy 4 actually ships. So the next batch asked that
question directly of the records where being wrong breaks boot: the ten `boot-kernel`
records with status `ok`, a `danger` set, and `omarchy` in `applies_to`. One brief, five
auditors, two records each, every claim checked against the cited source and, where it
could be, against this workstation. **All ten came back `corrected`**, nine at high
confidence and one (`nvidia-modules-missing-from-initramfs-black-screen`) at medium
because no DKMS failure was induced.

The defects cluster, which is the useful part:

- **`mkinitcpio -P` is dead on Omarchy 4.** `/etc/mkinitcpio.d/` is empty, so it stops
  with `No presets found`. Six of the ten records offered it as the rebuild step or the
  fallback. The command is `limine-mkinitcpio`, or `pacman -S linux`, which the ALPM
  guard lets through because the guard aborts only a transaction carrying both `-S` and
  `-u` (read from `/usr/bin/omarchy-update-pacman-guard`).
- **There is no fallback initramfs and no fallback boot entry.** `limine-mkinitcpio-install`
  builds `omarchy_linux-fallback.efi` only when `MKINITCPIO_FALLBACK` is set, nothing sets
  it, and the hook deletes any fallback UKI it finds. The record whose whole premise was
  "boot the fallback entry" now says so and offers the Snapshots entry or an ISO chroot.
- **Hooks are assigned wholesale by `omarchy_hooks.conf`.** Edits to `/etc/mkinitcpio.conf`
  that move `microcode` or add `kms` are overridden. The `fsck` hook is present but packs
  only `fsck.btrfs`, a no-op, and every btrfs fstab line has pass 0, so the fsck record's
  symptom cannot occur on a stock install and now says which extra disk it can name.
- **Layout the records did not know.** Four subvolumes (`@`, `@home`, `@log`, `@pkg`) where
  the chroot record mounted two, ESP at `/boot` not `/boot/efi`, no swap partition, the
  cmdline embedded in the UKI so kernel parameters go through
  `/etc/limine-entry-tool.d/` rather than the bootloader menu, and a mapper name that does
  not matter because the chroot reads its own `/etc/default/limine`.
- **Two cited issues did not support their records** (basecamp/omarchy#8319 for the
  fallback record, and the snapshot record's cause was backwards about `//Snapshots`).
  `sudo omarchy-refresh-limine` breaks because `sudo` strips `OMARCHY_PATH`, and the
  script calls `sudo` itself. `plymouth-set-default-theme -R` runs the dead
  `mkinitcpio -P`.
- **Three things a plain-Arch record would never think of.** The in-place NVIDIA module
  reload after an upgrade only works because Omarchy installs `kernel-modules-hook`. Root
  may or may not be locked depending on which ISO installed the machine. And
  `omarchy-hibernation-remove` leaves `resume=` in the UKI's drop-in.

Every fix now carries labelled Omarchy 4 and plain Arch branches where they differ, and
every audit note says what was checked locally versus from a source and what was not
exercised. `merge_gapfill.py` gained `corrected_verify` on the way, because the chroot
record's verify step looked for `/boot/vmlinuz-linux`. Same dry-run-then-diff discipline:
exactly ten records changed, only in the named fields, and the 25 other boot-kernel
records are untouched.

The corpus is now **456 records, `ok` 229 / `corrected` 227 / `unaudited` 0**, from 832
distinct sources (verdict sources are appended to the record), with 41 records stamped
`cause_reconciled` across three dates. Dashes: 1,839 across 418 records.

**The deploy failed on the merge, and the failure was correct.** `pages.yml`'s sanity
check required an `UNAUDITED` label somewhere under `docs/records/`, as a guard that the
provenance disclaimer still renders. With zero unaudited records that grep is empty, so
the first site build after this work stopped before deploy. The check now asserts that
every record page carries an audit LED and that at least one carries a non-clean one,
which is the property it meant to guard. Fixed in a follow-up PR the same day.

### 6. O1 landed: a lint for the shapes the re-audit found

`research/tools/lint_corpus.py` greps every record that applies to Omarchy for eleven
shapes today's audits found wrong on Omarchy 4: `mkinitcpio -P`, `sudo pacman -Syu`,
bare `pacman -Sy`, `/boot/vmlinuz-linux`, the Omarchy 3 tree, `hyprland.conf`, `hl.set`,
edits to `/boot/limine.conf`, bare `hyprctl dispatch`, `sudo omarchy-`, and `/boot/efi`.
It is a candidate finder, not an audit: some hits sit in a branch labelled plain Arch.
**138 of 456 records carry at least one hit**, and `mkinitcpio -P` alone is in 52 (18
still `ok`). `data/lint-baseline.json` records those 138 as known, `--check` and a test
fail on any hit outside it, and the test was proved able to fail by injecting a hit into a
clean record. Clearing a slug from the baseline belongs in the commit that re-audits it.
The six options themselves are item 8 under "What's left".

### 7. O2 landed: the workflows now read the brief first

All three workflow scripts prepend the same preamble to every harvester, gap-filler and
auditor prompt: read `tools/reaudit-brief.md` from the corpus root before writing
anything, hold every claim to it, and write both branches where Omarchy 4 and plain Arch
differ. The preamble also carries inline the shapes that caught the most records, so an
agent that skims the file still sees them. `harvest-workflow.js` now takes `args.root`
(CLAUDE.md had said all three did; only two did), its audit schema accepts every
`corrected_*` field plus `sources`, and its merge applies them with a `cause_reconciled`
stamp instead of honouring `corrected_fix` alone. Verified by evaluating each script's
constant section under node with a fake root; no workflow was run. O6, making that
harvest extend the corpus rather than replace it through `ingest.py`, is still open and
still a precondition for running it.

**What this says about the other 219 `ok` records.** Fifteen records checked against
Omarchy 4 today, fifteen wrong. The boot-kernel set was chosen because it is where the
cost is highest, not because it is where the errors are, so the rate elsewhere is
unknown but there is no reason to expect zero. The same brief
(`scratchpad/audit2/PREAMBLE.md` this session, worth promoting into
`research/tools/` as the prompt for `audit-existing-workflow.js`) runs at about 130k to
180k tokens per two-record agent, and now lives at `research/tools/reaudit-brief.md`.
Of the 219, 142 carry a `danger` and apply to Omarchy: `apps-services` 23, `pacman-aur`
22, `power-suspend` 16, `omarchy-theming` 15, `network` 15, `gpu-drivers` 14. The
`pacman-aur` set is the next batch by cost of being wrong (partial upgrades, keyring,
downgrades), then `gpu-drivers`.

## Session of 2026-09-06: the published documents audited against the repo

Every document the site renders under "How this was built" was read against the corpus,
the bench specs and the tracked export. Every published figure that could be recomputed
was, and all of them reproduce. What did not hold:

- **The recompute commands on the results page failed on a clean clone.** `lift_test.py`
  opened the untracked database and nothing else, so the page's first sentence, that every
  number can be recomputed with no database and no container, was false. It now reads the
  export when the database is absent, `--export` forces it, and both sources give the same
  figures for every run the page quotes.
- **Run 44, the control, was contaminated too.** The retraction named runs 43, 45 and 46
  and said the tasks that failed were the ones outside `$HOME`. Both control tasks are
  outside `$HOME`, and the database shows the refusal on 53 of run 44's 80 cases, more than
  run 43. The retraction now says so, and "the control does not move" goes with it.
- **The refusal counts were not in the export.** The transcript head banked per case is
  4,000 characters and the rejection sits later, so the retraction table could not be
  re-derived from `results/`. The export now distils a `rejections` column per case; the
  re-export changed 224 opencode cases and nothing else.
- **Stale counts and claims.** `skillbench/README.md` said seventeen benches and three
  Omarchy agentic ones (eighteen and four), described the agentic lane as `pi` only, said
  every model is local and free, and listed one credential. `MODELS.md` quoted the run 18
  "3.0× latency" that the 2026-09-02 entry had already said not to quote, and ranked
  "three" capable models where its own table has four. `ZEN.md` still listed as open three
  questions the journal had closed, and its whole-suite cost no longer matched the tool.
  `research/README.md` said two workflow scripts and listed one; there are three. The
  results page rendered one heading twice, and the journal carried a nested-backtick
  construct the renderer cannot express.
- **Verified rather than changed.** The chat-lane table, the n=3/10/31 decay, the n=31
  null, the output-token comparison, the run 21 table, the run 4 replication, the runs
  14/15 saturation figures, the corpus counts and the raw-harvest counts all reproduce
  from the repo. The Go plan's caps are expressed as requests per 5-hour window on its
  public page, which is what `ZEN.md` says; the "$12 per 5 hours" reading below is not
  reconciled with it and is left as recorded.

Both fixed in the same PR before merge: `CLAUDE.md` said seventeen bench specs and nine
Omarchy ones, and `skillbench/results/README.md` said 31 runs. Later the same day the repo
gained a root `README.md`, its first, with a screenshot of the site and a plain statement
that the skill is vaporware, and this block was rewritten to point the next session at the
corpus rather than the bench.

## Session of 2026-09-05 (fourth): the turn budget was not real, and four runs are void

**Runs 43 to 46 are contaminated and their conclusions are withdrawn**, including one
that had already been published on the site.

### 1. opencode was silently refusing the agent's edits

`opencode run` is non-interactive, and opencode's default policy is
`external_directory: {"*": "ask"}`. In non-interactive mode "ask" means **auto-reject**, for
any tool call touching a path outside the working directory:

```
! permission requested: external_directory (/tmp/many/*); auto-rejecting
tool_use bash {"command":"mkdir -p /tmp/many"} -> "The user rejected permission to use
                                                   this specific tool call."
step_finish reason: "tool-calls"
```

**No error is recorded on the case.** The run completes, status `ok`, and the transcript
ends at `reason: "tool-calls"`, which is exactly what a model that chose to stop looks like.

It was hitting every one of the four runs, the control included:

| run | task | cases with a rejection |
| --- | --- | ---: |
| 43 | `rebind-packaged-default` | 32/40 |
| 43 | `looknfeel-not-hyprlang` | 28/40 |
| 44 (control) | `dropin-shadows-unit` | 32/40 |
| 44 (control) | `deleted-file-holds-disk` | 21/40 |
| 45 | `theme-overlay-not-packaged` | 20/20 |
| 46 | `theme-overlay-not-packaged` | 10/10 |
| 45/46 | `idle-lock-not-hypridle` | 3/20, 0/10 |

**The tasks that failed are exactly the ones reaching outside `$HOME`**, and both control
tasks do, in `/etc` and `/var/tmp`. The one that worked lives entirely inside it. (The
run 44 rows were added on 2026-09-06; the entry as first written omitted the control.)

### 2. Two conclusions withdrawn

- **"The skill diverts an agent into research instead of action."** Published in
  `RESULTS.md`. The zero-edit finding was the harness refusing the edit, not the skill
  changing the model's behaviour. Retracted on the page rather than deleted, because it was
  published there.
- **"These models have a five-turn budget."** Same runs, same cause. Given an unobstructed
  task the same model runs **22 steps and finishes cleanly**, all ten files written.
- **"The control does not move."** Run 44 was refused more often than run 43, so its flat
  control column measured the refusal, not the skill. Added 2026-09-06.

The chat-lane results and the n=31 agentic null are **unaffected**: both predate the
opencode backend and ran through `pi`.

### 3. What actually found it

The operator asked why the agent was stopping instead of accepting a workaround. Three
hypotheses were tested and two were wrong:

- **An opencode step limit.** Wrong. `steps ?? 1/0` in the binary: the default is Infinity.
  A first grep read that as `1` because it truncated at `1/0`.
- **A Go subscription turn limit.** Wrong. Go's limits are dollar-denominated ($12 per 5
  hours), and no 429 appeared in any run. (The public Go page expresses the cap as
  requests per 5-hour window, as `ZEN.md` records; the two readings are not reconciled,
  and neither is a turn limit.)
- **A permission refusal.** Correct, and it prints the reason plainly the moment a task is
  run outside the bench.

`--dir "$HOME"` from the previous session was a **half fix**: it made `~/.config` writable
and left everything else refused. That is why `idle-lock-not-hypridle` worked and nothing
else did.

### 4. The fix, and the lesson worth keeping

`app/runner.py` writes `~/.config/opencode/opencode.json` per case with
`permission.external_directory: {"*": "allow"}`, pinned by a test that carries the case
counts in its docstring. `autoupdate` stays false so opencode cannot change version mid-run.

**A silent refusal and a model giving up are indistinguishable from the score column, and
nearly indistinguishable from the transcript.** Only the string `auto-rejecting` separates
them, and it appears in the tmux output rather than in the JSON event stream. This is the
fourth harness bug in this lane to imitate a capability failure, after the scratch HOME, the
working directory, and run 21's VRAM spill.

## Session of 2026-09-05 (third): a new bench, and the constraint it exposed

`omarchy-agentic-published-wrong` was written from
[benches/SKILL-COVERAGE.md](skillbench/benches/SKILL-COVERAGE.md), hand-verified across all
three outcome states, and then measured. **Both tasks fail, in opposite directions**, and
the reason is more useful than the bench.

### 1. The bench is not calibrated, and is marked so

| task | result |
| --- | --- |
| `idle-lock-not-hypridle` | bare **1.0** on GLM-class. Too easy: they already know `idle.lock` is in `shell.json`. 27 of 30 cases edited. |
| `theme-overlay-not-packaged` | both arms at the 0.8 floor. **Zero of 30 cases ever edited anything.** |

Hand-verification was sound: seed-only 5/6 and 4/5, wrong answer 4/6 and 2/5, correct 6/6
and 5/5, so a wrong answer scores below doing nothing in both. The bench measures what it
was built to measure. The models simply do not reach the state it grades.

### 2. The real constraint is a TURN BUDGET, not difficulty

Measured across every opencode agentic case run so far:

| task | median turns | cases that edited anything |
| --- | ---: | ---: |
| `idle-lock-not-hypridle` | 4 | 27/30 |
| `looknfeel-not-hyprlang` | 6 | 9/40 |
| `rebind-packaged-default` | 6 | 7/40 |
| `theme-overlay-not-packaged` | 4 | **0/30** |

**Overall median 5 turns.** Two reads plus one edit gets done. Find-a-thing, make a
directory, copy, then modify does not, and it fails *silently*: the model stops at the same
budget and never signals it has not finished.

That reframes run 43's finding. The skill diverting an agent into `/usr/share/omarchy/` did
not merely waste effort, it **spent the whole budget**. Under a five-turn ceiling, a skill
that adds one research step is the difference between finishing and not.

**A task is not too hard, it is too many steps.** Seed away the setup so the agent only has
to make the change. This is now in `SKILL-COVERAGE.md` alongside the saturation rule.

### 3. A property of the split bundle, ruled out as the cause

`skill:omarchy` is `files: [SKILL.md]`, and `SKILL.md` links to six topic guides while
telling the reader to consult them. In that variant the guides are **absent**, so an agent
follows the pointer and finds nothing. Observed verbatim: *"The skill's theming guide
doesn't exist, so I'll explore the stock Everforest theme structure directly."*

The bundle is complete on disk; this is an artefact of how `skills.yaml` splits it. It means
`omarchy` is not simply "less skill" than `omarchy-full` but a skill with dangling
references, which is worth remembering when reading any comparison between the two.

**It was not the cause here.** Run 46 with `omarchy-full`, which does contain `theming.md`,
scored identically: 0 edits in 10 cases. Recording it because it was my first hypothesis and
it was wrong, and because it still affects interpretation elsewhere.

### 4. What the next attempt needs

Not a harder seam. A **shorter** one. Either make task 1 require more than a single edit, or
seed task 2's overlay directory so the agent only has to write the file. The seam inventory
is sound; the step count is what has to change.

## Session of 2026-09-05 (second): the first Go ladder, and the skill diverts an agent

Runs 43 and 44: the GLM ladder (`glm-5.1`, `5.2`, `5.3-flash`, `5.3`) on the agentic lane
through opencode, 5 repeats, `none` vs `skill:omarchy`, 160 cases across both. **Zero
marginal cost**, because every rung is `opencode-go/`.

### 1. The numbers

| rung | Omarchy lift (run 43) | control lift (run 44) | DiD |
| --- | ---: | ---: | ---: |
| `glm-5.1` | **-20.0 pt** (p=0.02) | +0.0 pt (p=1.00) | **-20.0** |
| `glm-5.2` | +10.0 pt (p=0.21) | +0.4 pt (p=1.00) | **+9.6** |
| `glm-5.3-flash` | -13.3 pt (p=0.14) | -10.0 pt (p=0.10) | **-3.3** |
| `glm-5.3` | -16.7 pt (p=0.06) | -3.7 pt (p=0.53) | **-13.0** |

**The control does not move**, so nothing here says the skill degrades general Linux. The
Omarchy direction is negative on three rungs of four and inconsistent, mean DiD about
-6.7 pt.

**Corrected 2026-09-06: every number in that table is void**, the control column included.
Run 44 was hit by the permission refusal described in the fourth session on 53 of 80 cases,
more than run 43, so the flat control measured the refusal rather than the skill.

### 2. The mechanism, which is the solid part

On `rebind-packaged-default` with the skill loaded: **zero edit-tool calls and zero clean
stops across 20 cases.** The same skill on the sibling task produced 7 edits and 7 clean
stops, so this is not truncation, a step cap or plumbing.

The transcripts show what happens. The skill sends the model to grep `/usr/share/omarchy/`
for the binding API, it researches the packaged defaults, and it never gets round to editing
`~/.config/hypr/bindings.lua`. Bare, lacking that pointer, it pokes about locally and edits
the user file.

**That is directly useful for the skill this repo exists to build.** A corpus-backed skill
should say what to change, not invite a tour of upstream.

### 3. Three caveats, all load-bearing

- **The Omarchy bench is saturated for this model class.** Bare is 0.90 to 0.97. It was
  calibrated against `devstral-small-2:24b`, which scores 8/20 on it. At 29 of 30 assertions
  there is nowhere to go but down, which compresses every number above.
- **Timeouts are variant-correlated.** In the control, 8 skill cases hit the 600 s cap
  against 3 bare, plus 2 infrastructure `VMError`s. Modest, and consistent with the
  mechanism rather than random, but it is the shape that voided run 29.
- **n=5 per rung.** This project has watched +11.1 pt decay to +1.9 pt between n=3 and
  n=31 on this exact lane. Treat the magnitudes as directional.

### 4. What the next bench needs

`omarchy-agentic-stale-advice` cannot measure GLM-class models: they nearly max it bare. A
harder Omarchy agentic bench is now the blocking artefact, and the mechanism above suggests
what it should test, namely whether an agent **acts** rather than researches.

### 5. Goldens re-saved

Both VMs powered off, saved one per invocation, restarted, `ready:true` on both, and the
agent key verified at 67 characters from a login shell after the reboot. Without this the
next `reset` would have dropped the key exactly as it dropped NOPASSWD sudo on 2026-09-01
and both bench keys on 2026-09-02.

## Session of 2026-09-05: the agentic lane runs on opencode, and three bugs wore one costume

### 1. Go was reachable all along, under a prefix I never tried

`opencode models` reports two providers: **`opencode/` (69 models, pay-as-you-go)** and
**`opencode-go/` (27 models, the subscription)**. Every model previously written up as "not
supported" (`glm-5.3`, `qwen3.8-flash`, `longcat-2.0`, `omen-alpha`, `hy3`, `kimi-k2.6` and
the rest) is a Go model reachable only under the second prefix, and only through the CLI.

The previous session's conclusion that Go was unreachable was **wrong**, and it was wrong
because I called `opencode/<model>` throughout without ever listing the providers. The
operator's TUI screenshot showing `Qwen3.8 Flash  OpenCode Go` at `$0.00` is what found it.

**Go is free at the margin**, measured rather than assumed: `opencode/` moved the account
balance by exactly what `opencode stats` reported, while five `opencode-go/` sessions moved
it not at all and `stats` still claimed about two cents. So **`opencode stats` reports
notional cost and does not separate covered from billed.** That also corrects the earlier
"the API has no cost accounting" claim, which was too broad in the other direction.

### 2. The agentic lane now drives opencode, and it is instrumented

`params.agent: "opencode"` runs `opencode run --format json`. For the first time since run
18 the lane records **turns, tokens, tool calls and cost per case**, against a 16-character
median transcript and no token accounting before.

That instrumentation is not a nicety. It is the only reason the next section was solvable.

### 3. Three bugs, all producing exactly 4/6

Runs 39, 40 and 41 scored the do-nothing floor on every case, across two models. Each had a
different cause and all three looked identical from the score column, which is the failure
mode [MODELS.md](skillbench/MODELS.md) exists to warn about:

- **Scratch `HOME` broke the task.** Relocating HOME to control skill discovery also
  removes the `~/.config/hypr` the tasks edit, so the agent found no config and wrote its
  edits where no assertion looks. Fixed by rewriting only `~/.agents/skills` in the real
  HOME, fresh every case.
- **Writes were being auto-rejected.** opencode asks permission for any write outside its
  working directory, and `run` is non-interactive, so every edit came back *"The user
  rejected permission to use this specific tool call"* and the agent carried on as though
  it had chosen not to act. The bench works in `/tmp/skillbench/<window>` while the tasks
  edit `~/.config`, so **no case could ever have passed**. Fixed with `--dir "$HOME"`.
  Omarchy's own launcher solves this with `opencode --auto`, which `run` does not accept.
- **Neither was a model problem**, though both read as one. `qwen3.8-flash` and `glm-5.3`
  looked equally incapable while both were reading exactly the right files.

Run 42, after the fixes: `looknfeel-not-hyprlang` none 4/6 skill 6/6, `rebind-packaged-default`
none 6/6 skill 4/6. One win each way at n=1, which says nothing about the skill and
everything about the harness: it discriminates now instead of flooring everything.

### 4. A stock Omarchy machine has no bare condition

Omarchy symlinks `omarchy` and `diagnose-crash` into `~/.agents/skills` on every install,
host and VM alike. So the `none` arm silently carries the skill it is the control for unless
the harness clears it, and more interestingly, **every opencode session a real Omarchy user
starts already has the skill loaded**. "Does the skill help" is not hypothetical for them,
it is their default.

### 5. Credential handling, and one mistake

[tools/install-agent-key.sh](tools/install-agent-key.sh) provisions the model key onto the
VMs once, the way `install-bench-key.sh` does for ssh. The runner handles no token: a
login shell already exports it, and a test asserts the generated command contains no
`API_KEY`, `sk-`, `Bearer` or `token`.

Two failures worth keeping. Nested quoting through a login shell failed **silently** under
`set -e`; and `printf '%s'` with no trailing newline made the remote `read` hit EOF, return
non-zero, and abort the whole remote script before it wrote anything. The key lives in
`~/.bash_profile`, not `~/.bashrc`, because Omarchy's `.bashrc` returns on line 5 for
non-interactive shells, which is exactly why Omarchy exports `OMARCHY_PATH` above that line.

**The key was also printed in plaintext into a session transcript** by running `bash -x` on
a script that handles a secret. Rotation was offered and deferred. Do not trace a script
that touches a credential.

## Session of 2026-09-04 (fourth): the docs are published, and Go turns out to be unreachable

### 1. Go bills nothing, because an API key means pay-as-you-go

Settled by a controlled experiment rather than by reading docs. The operator read the
balance, a measured batch ran through the **opencode CLI** on Go-listed models only, and the
balance was read again:

| | |
| --- | --- |
| balance | $4.98 to $4.62, **-$0.36** |
| `opencode stats` | $0.07 to $0.43, **+$0.36** |

Exact match. **Neither `/zen/v1` nor `opencode run` draws on the Go subscription** when
authenticated with an API key. A second, larger batch predicted $4.13 against an actual
$4.20, so `opencode stats` is close but over-reports by roughly 8% and is not authoritative.

Two things this corrects:

- **"The API has no cost accounting" was too broad.** `opencode stats` is accurate to the
  cent. The gap is API-specific: `/zen/v1` has no balance endpoint reachable with a Bearer
  token (`/auth/balance` exists but wants a website session) and returns six response
  headers, none of them quota or cost. So a script cannot enforce its own ceiling; the CLI
  can report one.
- **The Western-lab 500s were never entitlement.** `grok-4.6`, `gpt-5-nano`, `gpt-5.6-luna`,
  `claude-haiku-4-5` and `gemini-3.5-flash-lite` all return HTTP 500 over the API and work
  fine through `opencode run` **on the same key**. Every theory offered for that split,
  including BYOK, was wrong: the API endpoint simply serves a subset. Confirmed on the test
  VM too, so the agentic lane could drive it.

The open question is no longer "does Go cover the API" but **"how is Go reachable at all"**,
since an API key appears to mean pay-as-you-go by definition.

### 2. The project's own documents are now pages on the site

The "How this was built" cards linked out to GitHub. They now open rendered pages:
`research/README.md`, `skillbench/README.md`, `skillbench/MODELS.md`, `skillbench/ZEN.md`,
`JOURNAL.md` and the writeup, driven by a `DOCS` table in `build_site.py`.

`md_doc` extends `md_lite` to what these files actually contain: headings, paragraphs,
lists, fenced and inline code, **pipe tables** (64 rows across the docs), blockquotes, bold,
italic, links and rules. Same escape-first rule, so no document can inject markup.

Three defects were caught by rendering rather than by reading the generator, which is the
same lesson as the paragraph bug:

- **The H1 rendered twice**, once as the page title and again as the first body heading.
- **Emphasis could not span a code span.** Splitting on backticks first left a bold run
  that contained a code span with stranded asterisks, which is a shape these docs use often. Code spans are now lifted
  to placeholders so emphasis spans them.
- **Headings collapsed to body size**, because shifting every level down one made a
  document's `##` an `<h3>` at the same 16px as the prose.

Cross-document links resolve locally where the target is rendered and fall back to GitHub at
HEAD otherwise, so `[MODELS.md](MODELS.md)` inside `ZEN.md` becomes `models.html`.

**`pages.yml` now triggers on those six sources**, and CI fails if any doc page is missing or
if the cards stop pointing at them. Without that the site would quietly serve a stale copy of
its own documentation, which is the failure that a `paths` trigger is for.

## Session of 2026-09-04 (third): the chat lane on cloud models, and a real Omarchy effect

The first cloud runs. **The skill shows a large, replicated, Omarchy-specific lift on the
chat lane**, which is the opposite of the agentic lane's null and the first positive result
this project has produced under proper controls.

### 1. Four clean models, four replications

`linux-desktop-gauntlet`, 10 repeats, `none` vs `skill:omarchy`, 200 cases per model.

| model | Omarchy tasks | control tasks | DiD |
| --- | ---: | ---: | ---: |
| `nemotron-3.5-lightning-free` | **+28.8 pt** | +3.4 pt | **+25.5** |
| `deepseek-v4-flash` | **+25.1 pt** | +1.8 pt | **+23.2** |
| `qwen3.5-plus` | **+27.3 pt** | -5.3 pt | **+32.6** |
| `qwen3.6-plus` | **+22.6 pt** | -1.8 pt | **+24.3** |

Every Omarchy lift is p < 0.0001. **No control is significant.** Against the agentic lane's
DiD of +0.2 pt at p = 0.98, this is the same skill and the same corpus behaving completely
differently on the lane where the incumbent was always shown to work.

**The gauntlet is a MIXED bench**, six Omarchy tasks and four general-Linux ones, so it
carries its own control and the difference-in-differences comes out of one run at no extra
cost. Reporting only the pooled figure would state a lift belonging to neither group: on
run 34 the pooled +18.6 pt is +28.8 on Omarchy and +3.4 on controls. `lift_test.py` now
splits automatically and takes `--model=`, since a run can hold several.

Checked against the obvious objection, that the controls are simply easier: the skill uses
**42% of available headroom on Omarchy tasks against 10% on controls**, so the effect
survives normalising for the ceiling.

### 2. I contaminated three models, by fixing a bug

The gauntlet spec carries `max_tokens: 350`. That cap had **never been in force**, because
`options{}` was ignored. Making parameters work made it effective for the first time, and
reasoning models spend 350 tokens thinking and emit nothing. Those cases graded zero.

The truncation is **variant-correlated**, because the skill makes answers shorter:

| model | bare truncated | skilled truncated | as scored | excluding truncated |
| --- | ---: | ---: | --- | --- |
| `deepseek-v4-pro` | 81/100 | 19/100 | om +37.1, DiD +8.5 | om +9.1, DiD +1.0 |
| `minimax-m3` | 59/100 | 26/100 | om +32.2, DiD +36.3 | om +15.5, DiD +20.1 |
| `minimax-m2.5` | 53/100 | 28/100 | om +31.1, DiD +33.0 | om +20.2, DiD +16.1 |

**The guard I wrote had a hole exactly where the risk was.** The commit says `max_tokens` is
sent "only when a spec asks for one" so it cannot impose a new cap. The spec *does* ask for
one. I guarded the default and not the spec value.

`lift_test.py` now drops `output_source='empty'` cases: a response with no text cannot be
graded on its text, and scoring it zero conflates "wrong" with "did not finish". The four
clean models are unchanged by that, which is the check that it is not doing something
arbitrary. **`deepseek-v4-pro` is unmeasurable at this cap rather than null**, since
excluding truncation leaves 19 bare cases.

**This is the evidence for the held `max_tokens` decision.** At 350 the bench cannot measure
a reasoning model at all. Raising it edits a bench spec and starts a new series, so it stays
an operator decision.

### 3. The free tier cannot carry a bench

Of six free models, three produced unusable data: `big-pickle` and `mimo-v2.5-free` returned
**429 on all 200 cases** each, exhausted by earlier probing, and `laguna` and `ling` lost 63
and 84 cases to 503 **at different rates per variant**, which is the shape that voided run
29. Discarded rather than reported.

`_status_of` classified the 503s as `unavailable` rather than as model failures, which is
the PR #34 fix working on its first real outing.

### 4. The skill makes answers shorter as well as better

`deepseek-v4-flash` averaged **3,257 output tokens bare against 1,000 with the skill**. That
cuts directly against the "it just makes the model write more" explanation that killed the
agentic lift, and it is why bare cases time out more often (10 against 4 on run 37). That
bias is conservative: dropping the slowest bare cases raises the bare mean, so the measured
lift is a floor.

### 5. Cost

**$3.09 actual against a $5 budget**, six paid models, 1,200 cases. The estimator predicted
input to within 0.2% and underestimated output by 33%, so the reasoning multiplier is 4x
rather than 3x. The contaminated models were *cheaper* than predicted, because truncation
cut their output short.

## Session of 2026-09-04 (second): the cloud terrain, and four defects that fail silently

The chat lane can now post to an OpenAI-compatible gateway. Getting there turned up four
things that would each have produced plausible, wrong numbers, and one of them reaches
backwards into every chat-lane run this project has ever made.

### 1. `options{}` has never been applied, on Ollama either

Generation parameters sat in an Ollama-native `options` object. The OpenAI-compatible
`/v1` endpoint ignores it. Measured on both servers with `options.num_predict = 8`:

| server | completion tokens returned |
| --- | ---: |
| Ollama `/v1` | 80 |
| Zen `/v1` | 172 |

**No chat-lane run has ever used the temperature its spec asked for**, including the
+29.3 pt baseline. Every one ran at the server default. Both arms of every paired run were
equally affected, so the past comparisons stand on their own terms, but a run made after
this fix is not comparable to one made before it. Parameters now go top level.

`max_tokens` is deliberately **not** sent unless a spec asks for one. The nominal 512 was
never in force, so emitting it would impose a brand new cap while looking like a
portability fix. The right value is an open question the operator is still weighing.

### 2. Half the reachable models return no `content` at all

Twelve of eighteen reachable Zen models returned `null` or empty `content` on a short
prompt, with the answer in `message.reasoning`. The runner read `content` alone, so those
recorded as "said nothing" at status `ok` and graded as zero. `_answer_of` now falls back
to `reasoning` and records `case_result.output_source` so the two can be told apart. That
distinction is load-bearing: a reasoning trace may consider and reject the trap before
settling on the right command, so a `regex_forbidden` check can fire on a model that got
it right.

### 3. An unreachable model returns a bare 500

Not 402, not 403. `Internal server error`, on 38 of 59 probed models, indistinguishable
from a real outage. Recorded as `unavailable` rather than `error` so an unconfigured model
cannot be read as one that failed the task. Only `kimi-k2.6` was honest about it, with a
401 `Model is disabled`.

### 4. Two smaller ones, both fatal in their own way

- `_resolve` appended `:latest` to every untagged model. That is an Ollama convention, and
  `glm-5.2:latest` does not exist. Now keyed on whether the chat base is Ollama.
- Compose interpolates an unset variable to the **empty string**, and
  `os.environ.get(k, default)` returns that empty string rather than the default. The chat
  lane would have posted to a URL with no host. Caught by writing the compose wiring and
  then testing it, not by reading it.

All four are pinned by tests, and each was **proved to fail against the old code** before
being kept: reverting the three runner fixes produces four failures, and reverting the
compose fix produces a fifth. 51 tests now.

### 5. The terrain is documented because it is not guessable

[skillbench/ZEN.md](skillbench/ZEN.md) and
[skillbench/tools/probe_zen.py](skillbench/tools/probe_zen.py), the cloud siblings to
`MODELS.md` and `probe_models.py`.

```
listed 66 | probed 59 | reachable 18 | HTTP 500 on 38
```

Five within-family ladders are usable: GLM three rungs, MiniMax three, Kimi three, Qwen
two, DeepSeek two, plus six free models. That is the instrument the capability-band
question needs, and it is better than the two ladders the first probe suggested.

**A listing is not an entitlement.** `/v1/models` lists ids that 500 on use, and omits ids
from OpenCode's own Go page (`glm-5.3`, `qwen3.8-flash`, `longcat-2.0`, `omen-alpha`)
which return "not supported".

### 6. Three account settings do nothing through the API

Flipped on, then off, with a full snapshot at each step. Zero effect on listing or
reachability, in both directions:

| setting | listing | reachability |
| --- | --- | --- |
| allow models that train on request data | none | none |
| allow models hosted in China | none | none |
| use available balance after usage limits | none | none |

Only the per-model enable toggles moved anything, and they moved it from 20 listed to 66.
The three above sit under "control which providers are used for **routing**", which is the
likely explanation: they govern how the CLI picks a model when none is named, and naming
one over the API leaves nothing to route. Unconfirmed.

### 7. Two things I had wrong, both caught by checking

Worth recording because the checks were cheap and the claims were not:

- **"Most reachable models return nothing" was my probe budget, not the models.** At
  `max_tokens: 8` only 6 of 59 produced text. Re-probing the 12 silent ones at 512 turned
  9 into real answers. The finding survived; the framing did not.
- **`omarchy-update` is a real binary.** `/usr/bin/omarchy-update` exists alongside 23
  `omarchy-update-*` scripts, and `omarchy update` is the documented front end that
  dispatches to it. I was one sentence away from scoring four models wrong for a right
  answer, on a question that turns out to be easy enough to be a poor proxy for headroom
  anyway.

### 8. Go does not cover the API, and a run now has a price

**The balance moved 2 cents during the probe session.** That answers the question the
previous section left open: API calls bill pay-as-you-go per token, and the Go plan's
request-per-5-hour caps govern its own routing rather than this endpoint.

It also inverts a claim made earlier the same day. "Requests, not tokens, are the scarce
resource" was correct about Go and wrong about the bench, and it stood for about an hour
before the balance settled it. Both `ZEN.md` and `CLAUDE.md` are corrected.

[skillbench/tools/estimate_cost.py](skillbench/tools/estimate_cost.py) prices a run before
it is launched, from measured per-case token use rather than assumption: the 272 banked
chat-lane cases that carry usage give 127 in / 654 out for `none` and 3,286 in / 320 out
for `skill:omarchy`.

One 2-task bench at 31 repeats, output tripled to allow for reasoning traces:

| scope | cost |
| --- | ---: |
| six free models | $0.00 |
| `deepseek-v4-flash` | $0.17 |
| eight cheapest paid models | $3.60 |
| all eleven paid models | $9.13 |

So **one bench walked across the whole ladder at full statistical power is affordable, and
the whole suite across many models is not**: every chat bench at 31 repeats runs $2.33 on
the cheapest paid model and $46.93 on `kimi-k3`. The plan is one bench with headroom, the
six free models for the bottom of the curve, and roughly eight paid rungs above them.

Caveat that belongs next to the number: every measured figure came from a local model, and
most local models are not reasoning models. The 1.0 multiplier is a floor.

### 9. Still open

1. **Why does every Western-lab model return 500** while every Chinese-lab and open model
   works on the same key? Every OpenAI, Anthropic, Google and xAI id fails. Not explained
   by any account setting, all three of which were flipped both ways. BYOK for those
   providers is the leading guess, and a 500 is indistinguishable from an outage either
   way.
2. **`--mode json`** remains unimplemented, so turns and tokens per agentic case are still
   unknown. That now blocks pricing the agentic lane, not just diagnosing it.
3. **Which ids do the Go page's models use?** `glm-5.3`, `glm-5.3-flash`, `qwen3.8-flash`,
   `qwen3.7-plus`, `longcat-2.0` and `omen-alpha` all return "not supported", which may
   mean the id is wrong rather than the model unavailable. Those are the newest rungs of
   two of the five ladders, so it is worth knowing.
4. **The `max_tokens` default**, deliberately left unset pending a decision. 5k is the
   operator's working figure.

## Session of 2026-09-04: the agentic lane is answered, and the answer is a null

Run 31, the control's third attempt, is the first clean one: **124/124 cases, zero seed
failures, no VM drained**, only legitimate agent timeouts. The seed repeatability check and
the pool drain guard both did their jobs, which is what the previous two attempts cost.

| bench | none | skill | lift | 95% CI | p |
| --- | ---: | ---: | ---: | --- | ---: |
| `omarchy-agentic-stale-advice` (run 28) | 0.871 | 0.890 | +1.9 pt | [-3.8, +7.5] | 0.59 |
| `linux-agentic-deep-triage` (run 31) | 0.747 | 0.765 | +1.7 pt | [-2.7, +6.2] | 0.47 |
| **difference in differences** | | | **+0.2 pt** | | **0.98** |

**The two lifts are the same size.** `skill:omarchy` nudges general-Linux triage exactly as
much as it nudges tasks about the Omarchy 3 to 4 split, which is the condition the controls
were built to detect: a small uniform effect consistent with more context making a model
marginally more careful, and nothing to do with Omarchy knowledge.

Worth stating plainly because it took four runs to get here honestly: **the incumbent skill
has no measurable Omarchy-specific effect on the agentic lane.** Not a weak one. p = 0.98 on
the difference.

### What this does and does not mean

It does **not** mean the corpus skill will fail. It means:

- The **chat lane's +29.3 pt** is the only demonstrated skill effect in this repository, and
  that finding now stands alone rather than alongside an agentic one.
- The bar in [opinionated-omarchy/CLAUDE.md](opinionated-omarchy/CLAUDE.md), "do not regress
  the incumbent on the agentic lane", is trivially satisfiable. It needs replacing.
- A corpus-backed skill that shows a **surviving agentic lift at n=31** would be a new
  result. The lane can measure; the incumbent simply has nothing to measure.

### The decay, kept as the methodological point

| n | lift | p |
| ---: | ---: | ---: |
| 3 | +11.1 pt | 0.55 |
| 10 | +8.3 pt | 0.21 |
| 31 | +1.9 pt | 0.59 |

Had the n=3 figure been published this project would have claimed an eleven point lift that
does not exist. The cost of getting that right was four runs, two of them lost to harness
defects now fixed and tested.

### The consistency framing was tested too, and it is also null

The obvious rescue for a null lift is that the skill buys *steadiness* rather than score:
fewer catastrophic runs, a higher floor, safer everyday use. That is a different measurement
from a mean and the bench stores enough to check it. Across the same 248 cases:

| run | variant | sd | min | below floor | solved | errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 28 Omarchy | none | 0.168 | 0.500 | 2/62 | 38/62 | 6 |
| 28 Omarchy | skill | 0.158 | 0.500 | 1/62 | 41/62 | 8 |
| 31 control | none | 0.118 | 0.600 | 0/62 | 7/62 | 12 |
| 31 control | skill | 0.136 | 0.500 | **2/62** | 11/62 | 14 |

Spread is flat on the Omarchy bench and **wider** on the control. The worst case gets worse
on the control, and two cases fall below the do-nothing floor where bare had none. Errors
rise in both arms.

**Run 25's "the skill halves the error rate" does not replicate.** That was 6 of 20 against 2
of 20, and the 2026-09-03 entry flagged it as worth measuring deliberately. At n=62 it is 6
against 8, and 12 against 14. Same shape as the +11.1 pt lift: convincing small, absent at
full power.

One thing does move in both arms: solved-outright, 38 to 41 and 7 to 11. Note which moved
more. The control gained 4 solves from a base of 7 while the Omarchy bench gained 3 from a
base of 38, so if anything the skill helped the **control** more. That sharpens the
answer-length reading rather than softening it.

### The question was never binary, and both ends of the curve are now measured

Read runs 21, 28 and 31 together and "does the skill help" is the wrong shape. The answer is
a curve over model capability, and this project has measured both ends and never the middle:

- **Below the band:** 11 local models that cannot emit a tool call at all. Nothing helps, and
  no skill could.
- **Above the band:** `devstral-small-2:24b`, already capable. DiD +0.2 pt.
- **The middle:** never tested, because nothing available sat in it.

That is what makes the local work an anchor rather than a dead end.

### The instrumentation gap, which is a bench choice and not a pi limitation

`app/runner.py:114` invokes `pi` **without `--mode json`**. pi supports `text`, `json` and
`rpc`, and ships read/bash/edit/write tools with an allowlist, so the harness was never the
limitation. But in text mode the runner stored only the final assistant text: a **median of
16 characters** across roughly 600 agentic cases, and **0 of them carry token accounting**.

Three consequences, in ascending order of cost:

- Run 21's per-model failure notes were read from live transcripts and are gone. The
  conclusion is probably right and is no longer re-derivable from anything in the repo. Now
  recorded as a caveat on the [MODELS.md](skillbench/MODELS.md) table.
- A failed case cannot be diagnosed without re-running it. Free locally, not free on cloud.
- There is no way to see what a run consumes, which is fine when compute is electricity and
  disqualifying when it is a rate cap.

**`--mode json` is a prerequisite for any paid run.**

### Everything local is banked

`skillbench/data/` is gitignored under the repo's usual rule that derived artefacts are
rebuilt rather than committed. That rule assumed the artefact *can* be rebuilt.
`research/data/problems.db` regenerates in 0.2 s; this one regenerates from nothing, and one
disk sat between the project and **31 runs, 1,044 cases, 4,465 grades**.

[skillbench/tools/export_results.py](skillbench/tools/export_results.py) writes the tracked
`skillbench/results/`: `runs.jsonl` with aggregates computed exactly as `app/main.py:_agg`
does, `cases.jsonl` with everything `lift_test.py` needs, `grades.jsonl` so *which* assertion
failed survives, and the 13 distinct sha-pinned specs.

1.3 MB against the database's 5.7 MB. The difference is almost entirely
`case_result.request`: 4.87 MB of prompt text re-recorded per case, derivable from the spec
exported beside it. The non-prompt keys in it (`lane`, `vm`, `queue_wait_s`) are kept.

**Verified by re-deriving the journal from the export alone, with no database.** Runs 28 and
31 come back at +1.9 and +1.7 pt with a DiD of +0.2, and run 21's 14 cases reproduce the
MODELS.md table exactly. The export is byte-deterministic, so a new run appends instead of
rewriting the file.

One subtlety to keep straight: `state` in `runs.jsonl` is a **micro**-average
(`post_passed / post` summed over cases) while `lift_test.py` uses a **macro**-average (the
mean of per-case ratios) because the unit is the case. They agree when every case has the
same number of post assertions (run 28: 0.8710 both ways) and diverge slightly when they do
not (run 31: 0.7478 against 0.7473). Quote the macro-average for anything inferential.

### Where this goes next: low-cost cloud

The corpus was always for people fixing their own Omarchy machines, and local models matter
to them for privacy and for cost. What died is the claim that the skill lifts a model that
was already capable. Those are different claims and only the second one is affected.

The shift is to **low-cost cloud** through OpenCode Zen's OpenAI-compatible endpoint at
`https://opencode.ai/zen/v1/chat/completions`. The Go plan is **$10/month flat**, with
per-model caps in requests per 5-hour window running from 110,000 (Kimi K3) down to 1,350
(Grok 4.6).

**The flat fee is the point, and not mainly for cost.** A pay-as-you-go key on an agent that
can loop is financially unbounded, which is the wrong shape for an unattended multi-hour run
and worse for a daily driver. A cap turns a runaway loop into a rate-limit error rather than
an invoice. It also makes a published result reproducible by a reader for $10, which matters
more than experimental convenience given who this is for.

Go's 25 models form **seven within-family capability ladders**: Qwen 3.6 Plus through 3.8
Max, GLM 5.1 through 5.3, Kimi K2.6 through K3, DeepSeek V4 Flash and Pro, MiniMax M2.7 and
M3, MiMo V2.5 and Pro, Hy3 and Hy4. One provider, one API, one fee, one harness, one
variable. That is the instrument the middle of the curve needs, and **the weak rungs are the
ones to test**: benching the headline models would reproduce the devstral null for the same
reason it happened the first time.

Order of work: `--mode json` first, then the **chat lane**, which needs no VM, costs one
request per case, and is the only lane where the skill has ever shown an effect. The agentic
lane follows. Nothing about cloud requires touching the VMs, the goldens, the seed checker or
the pool guard, and **no existing bench spec may be edited**, because they are sha-pinned and
editing one orphans runs 23, 25, 28 and 31.

To settle at signup: whether the Go entitlement covers raw API calls or only the opencode
CLI. The Go page says it "can be used with any agent", which implies the former, but the Zen
docs describe pay-as-you-go credits separately and the two are not stated to be the same.

## Session of 2026-09-03 (fifth): two harness defects, and the check that would have caught both

### 1. Run 30 is void, and it was my seed rather than the pool

The control's second attempt lost **51 of 124 cases** to `mount` exit 32, skewed 31 skill
against 20 bare. The teardown I wrote for `deleted-file-holds-disk` ran stop, `umount`,
`rm`. When the holder still owned its fd for a moment after `stop`, `umount` failed busy,
the `rm` deleted the image anyway, and the loop device stayed attached to a dead inode:

```
/dev/loop0: [0031]:269707 (/var/tmp/bench-disk.img (deleted))
```

Teardown now waits for the unmount rather than assuming it, falls back to lazy, detaches
any loop still pointing at the image, and removes the file last. The mount also prints
`losetup -a` on failure instead of exiting 32 with nothing, because a bare exit code is what
made this take a full run to find.

**The pool guard from run 29 worked.** No VM was drained, nothing cascaded, every failure
stayed inside its own case. Run 30 is unusable because half its cases never posed their
question, not because one bad case poisoned the rest. Those are different failures and the
fix for one does not address the other.

### 2. The real defect was in how seeds were verified

Run 27 and run 30 are the same shape: teardown that assumes the previous case finished
cleanly. Both survived hand-verification, because **a seed was verified once**. The runner
fires it before every case, so the second cycle is the one that matters.

[skillbench/tools/check_seeds.py](skillbench/tools/check_seeds.py) runs every agentic seed
N times back to back and fails on the first repeat that breaks. All nine pass; the disk
seed that lost run 30 now survives **12 consecutive cycles with zero deleted-inode loop
devices**, against 41% case loss.

**The checker caught a defect in itself first, and that is the part worth remembering.** A
first draft reported `omarchy-agentic-config/theme-switch` as broken. That seed is fine: it
was invoked through plain `bash -s` while `vm.run()` uses `bash -lc`, and `OMARCHY_PATH`
comes from `~/.bashrc`. A checker that does not match the runner invents failures and hides
real ones, which is worse than no checker.

It proves the runner can pose a question repeatedly. It does **not** check that assertions
still discriminate; that stays a hand-verification against the **shipped** templates.

### 3. Why this got built rather than just re-running

The harness is about to be pointed at cloud model classes and effort levels, so the cost of
a four-hour failure that only surfaces in the results is going up, not down. Two runs and
roughly eight hours were lost to bugs a few seconds of checking would have caught.

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
- **The corpus.** 1,880 dashes across 424 records, now item 6 of "What's left" with the
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

### 1. Replace the agentic bar, because the incumbent has nothing to regress

**Answered 2026-09-04, cleanly.** Runs 28 and 31, both n=31, both without a lost case:
Omarchy lift +1.9 pt (p = 0.59), control lift +1.7 pt (p = 0.47), **difference in
differences +0.2 pt at p = 0.98**. `skill:omarchy` moves general Linux as much as it moves
Omarchy, which is the condition the controls exist to detect.

The measurement question is closed. What is open is a **decision**, and it belongs to
whoever writes the skill:

- The chat lane's **+29.3 pt** is now the only demonstrated skill effect in this repository.
  A corpus-backed skill can be measured there against a real incumbent.
- On the agentic lane there is no incumbent effect to beat, so "do not regress" is
  meaningless. Either target a **surviving lift at n=31**, which would be a new result, or
  say plainly that the lane is a harm check rather than a proving ground.
- Budget accordingly. A clean n=31 pair is about eight hours of machine time, and
  `check_seeds.py` must be run first.

Unchanged: only **4 of 14** local models can drive the loop at all
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

The measurement on 2026-09-03: **1,880 em and en dashes across 424 of 456 records**
(1,839 across 418 after the 2026-09-06 corrections), concentrated in
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
- The three record defects found on 2026-09-01 were applied on 2026-09-06 through
  `merge_gapfill.py`, with an `audit_note` and a `cause_reconciled` stamp, and ten
  boot-kernel `ok` records were re-audited against Omarchy 4 the same day (all wrong). The next
  scenario worth writing is not the hibernation one: its rewritten fix targets hybrid
  NVIDIA laptops, which a virtio GPU cannot imitate.
- `research/` root holds ~17 loose Hyprland wiki pages. Not corpus, no tooling reads them.
  Left in place deliberately.

### 8. Six ways to make the corpus true on Omarchy 4, not only source-consistent

Recorded 2026-09-06 after fifteen of fifteen `ok` records checked against Omarchy 4
needed correcting. Cheapest and most forward-fixing first. Recommendation at the time:
O1 and O2 now, O3 on `pacman-aur` next, O4 and O6 before the generic harvest is run
again.

- **O1. Mechanical lint before any agent spend.** DONE 2026-09-06:
  `research/tools/lint_corpus.py`, baseline of 138 records, `--check` and a test fail on
  new hits. Section 6 of the second 2026-09-06 session has the per-pattern counts.
- **O2. Put the environment facts into the harvesters, not only the auditors.** DONE
  2026-09-06: every harvester, gap-filler and auditor prompt in the three workflow scripts
  now opens by reading `research/tools/reaudit-brief.md` from `args.root` and carries the
  eight shapes that caught the most records inline. `harvest-workflow.js` takes `args.root`
  like the other two, its audit schema accepts `corrected_cause`, `corrected_symptom`,
  `corrected_danger`, `corrected_verify` and `sources`, and its merge applies them and
  stamps `cause_reconciled`, the same rules as `merge_gapfill.py`. The other two schemas
  gained the same keys. None of the three has been run since; the change is verified by
  evaluating each script's prompt section under node, not by a workflow run.
- **O3. Re-audit the `ok` records with a `danger` that apply to Omarchy**, using the
  brief. STARTED 2026-09-06. `pacman-aur` is complete as of 2026-09-07: all 22 records
  corrected (see the 2026-09-07 session). Paused there on the operator's instruction.
  120 remain across the other categories: `apps-services` 23, `power-suspend` 16,
  `omarchy-theming` 15, `network` 15, `gpu-drivers` 14, `hyprland-config` 12,
  `wayland-compat` 9, `audio-input` 9, `display-monitors` 5, `omarchy-core` 2. About 750k to 900k tokens per ten records, one agent per two records, through
  `merge_gapfill.py` with the dry-run-then-diff discipline.
- **O4. Harvest from `omacom/omarchy` issues rather than the web.** STARTED and paused
  2026-09-07 on the weekly token limit. The selector (`tools/issue_candidates.py`) and the
  harvester brief (`tools/issue-harvest-brief.md`) are built and committed. Ten of eleven
  batches ran over 99 of 109 candidate issues and produced **40 records, 21 mappings onto
  existing records and 37 skipped as unconfirmed**, banked unmerged in
  `raw/issue-harvest-partial.json`. Both remaining blockers except the audit cleared on
  2026-09-10 and 2026-09-11: the duplicates were reconciled in two passes, nineteen records into
  nine, batch 01 was read, adding six more, and all 36 were audited. **Every one of the 36 came
  back `corrected`**, 34 at high confidence and 2 at medium, with 29 fixes rewritten. The audited
  set is `raw/issue-harvest-audited.json` and the merge is the only thing left. The `existing`
  list, now 25 entries, is re-audit fuel for O3 and names four records the tracker contradicts,
  one of which sends readers to a hypridle config file that does not exist on Omarchy 4.
- **O5. Add a `checked_against` field** (Omarchy package version and date) so "matches
  its sources" and "true on 4.0.2" stop sharing one status. Schema change, four
  consumers, covered by the `FIELDS` tests. Not started.
- **O6. Make the harvest extend rather than replace.** `harvest-workflow.js` output goes
  through `ingest.py`, which replaces the corpus and would discard every correction and
  `cause_reconciled` stamp. Route it through the merge path with slug-collision
  suffixing before any full harvest runs again. Not started, and a precondition for
  item 1 of START HERE.

### 9. Backlog: Omarchy plug-ins as corpus content

Idea from the operator, 2026-09-06. Omarchy has a plug-in ecosystem: a plug-in
installer the operator rates highly, one or two plug-ins of the operator's own, and a
plug-in library. None of it is in the corpus, which has no `plugins` category. The
library is a natural source for a common-problems-and-fixes list, in the same shape as
the existing categories, and the operator's own plug-ins are cases where the fix can be
verified against the author. Not started: the installer and plug-ins are not on this
workstation yet, and their names are not recorded here until they can be checked.
Recorded in the Substrata ideas backlog as well.

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
