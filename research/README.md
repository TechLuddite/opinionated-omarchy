# Omarchy / Arch troubleshooting research

A corpus of real, reported problems that Omarchy and Arch-based desktop/laptop users
hit, each paired with a concrete fix and the source it came from.

The goal is practical coverage, not a headcount. A record only earns its place if the
`fix` field is something you could paste into a shell or a config file.

## What's in here now

**456 problems across 12 categories**, drawn from 766 distinct sources. Every record
carries at least one real, fetched source URL, and no two records share a slug.

| audit status | count | meaning |
| --- | --- | --- |
| `ok` | 240 | audited and confirmed accurate |
| `corrected` | 212 | problem real, fix (and sometimes cause) rewritten by the audit |
| `unaudited` | 4 | audit returned no verdict for these slugs |

So 452 of 456 records (99%) have been through an adversarial audit. The last
`gapfill-unaudited` records were audited on 2026-09-01; that status is still a value the
schema and `merge_gapfill.py` can produce, but no record currently carries it.

This was built in three passes. The first harvested 314 records but hit the account spend
limit, which killed the gap-fill stage and left `apps-services` unaudited. The second
pass closed both: it audited those 26 records and filled 143 new records against the 117
gaps the first pass's auditors had named. Only two of the second pass's audits failed
(`wayland-compat`, `network`: API errors rather than budget), leaving 28 records harvested
but never reviewed.

The third pass, on 2026-09-01, audited exactly those 28: **12 `ok`, 15 `corrected`, and 1
rejected and removed**, which is why the corpus is 456 records rather than 457. Since
then no record carries `gapfill-unaudited`.

The second pass also fixed a flaw in the first: its auditors could return a
`corrected_cause`, not just a corrected fix. **20 records had a disproved cause
replaced** rather than left standing. A later pass on 2026-08-30 closed the same gap
for the first pass's 130 corrected records: all were reviewed and **22 had their cause
rewritten** to match their own audit note. The third pass added **7 more**, for 29 stamped
records across two dates. See the trust model below.

## Datastore design

SQLite fits, but only for one job, so it isn't the source of truth:

- **`data/problems.jsonl` is authoritative.** One JSON object per line. It diffs
  cleanly in git, appends without rewriting, and stays readable when the tooling
  isn't around. Hand-edit this.
- **`data/problems.db` is a derived index.** Delete it any time; `build_db.py`
  rebuilds it. SQLite earns its keep because the real access pattern is *"a user
  describes a symptom in their own words → find the matching record"*, which is a
  ranked full-text query. FTS5 + bm25 does that in one statement, and the relational
  tables handle the tag/source fan-out that flat JSONL can't query.
- **`docs/*.md` is derived too.** One page per category, sorted by severity. This is
  what a human or an agent reads directly, with no tooling required.

So: JSONL for truth and diffs, SQLite for search, markdown for reading. Anything
generated can be thrown away and rebuilt.

## Layout

```
research/
  data/problems.jsonl     source of truth — edit this
  data/categories.json    category key -> display label
  data/problems.db        generated FTS5 index
  docs/                   generated markdown, one page per category
  raw/                    unprocessed workflow output, kept for provenance
  bench/                  skill-efficacy measurements — hand-written, NOT generated
  validation/             records exercised on a real VM — a SEPARATE signal from the
                          audit, and never merged into audit_status (see below)
  tests/                  stdlib-unittest tests for the corpus writers; ./tests/run.sh
  tools/corpus.py         the record schema (FIELDS) + the only reader/writer
  tools/build_db.py       JSONL -> DB + markdown
  tools/ask.py            symptom search
  tools/schema.sql        DB schema
  tools/harvest-workflow.js   the agent workflow that produced the corpus
```

## Usage

```sh
python3 tools/build_db.py                              # rebuild after editing JSONL
./tests/run.sh                                         # 13 tests, stdlib only

python3 tools/ask.py "screen share is black in zoom"   # search by symptom
python3 tools/ask.py "wifi keeps dropping" -v          # include verify steps + sources
python3 tools/ask.py --tag nvidia --tag laptop --list  # filter by tags
python3 tools/ask.py --slug some-problem-slug          # exact lookup
```

The scripts are executable and carry a `python3` shebang, so `./tools/ask.py ...` works
too.

Search is deliberately forgiving: query text is tokenised and OR-matched, so a user's
phrasing finds a record even when it shares no exact wording. Any FTS5 operators in
the query are quoted into literals rather than parsed.

Colour is emitted only when stdout is a terminal, and suppressed by `NO_COLOR` or
`TERM=dumb`. Redirecting to a file gives clean text; the `!! RISK` and `!! NOT
INDEPENDENTLY AUDITED` markers are ASCII prefixes, so a warning is never carried by
colour alone.

## Record shape

```jsonc
{
  "slug": "nvidia-black-screen-after-suspend",   // unique, kebab-case
  "title": "Black screen after resume on NVIDIA",
  "category": "gpu-drivers",
  "symptom": "...",          // as a USER would describe it, incl. literal error text
  "cause": "...",
  "fix": "...",              // copy-pasteable commands / config, markdown fenced
  "verify": "...",           // how to confirm it worked
  "applies_to": ["arch", "omarchy", "nvidia", "laptop"],
  "severity": "critical|high|medium|low",
  "frequency": "very-common|common|occasional|rare",
  "danger": "",              // non-empty when the fix risks data loss or boot
  "audit_status": "ok|corrected|unaudited|gapfill-unaudited",
  "audit_confidence": "high|medium|low",
  "cause_reconciled": "2026-08-30",   // optional; see the trust model below
  "sources": ["https://..."]
}
```

## Trust model: read this before running anything

These fixes were gathered by agents from wikis, issue trackers, and forums, then put
through a second adversarial audit pass against the Arch and Hyprland wikis. The audit
rejects fixes that are wrong, obsolete, dangerous, or citing sources that don't hold
up, and corrects ones that are salvageable. Every record carries what it survived:

| `audit_status` | meaning |
| --- | --- |
| `ok` | audited and confirmed accurate |
| `corrected` | problem was real, fix was wrong; the audited version is stored |
| `unaudited` | the auditor never returned a verdict for it |
| `gapfill-unaudited` | added in a later gap-fill pass, never audited; none remain, but `merge_gapfill.py` still assigns it when an audit agent dies |

`unaudited` and `gapfill-unaudited` records are flagged in both `ask.py` output and the
generated markdown. Treat them as leads, not instructions.

**One limitation of `corrected` records from the first pass.** Those audits rewrote only
the `fix` field. Where the auditor's objection was really about the `cause` (a wrong
mechanism, an outdated architecture claim), that stale text was left sitting in `cause`.
The second pass fixed this going forward: its auditors supply `corrected_cause`, and 20
causes were replaced. The first pass's 130 corrected records were not covered by that.

**All 130 were reviewed on 2026-08-30, and 22 were found to have a cause its own audit
note contradicts.** Those 22 have been rewritten from the note (the auditor had already
done the source work; the first pass simply had nowhere to put the result) and each is
stamped `cause_reconciled`. The other 108 were left alone: their notes affirm the cause
("the diagnosis is right", "cause verified exactly") and object only to the fix. The
worst offenders were the Omarchy 3 → 4 tree split (`~/.local/share/omarchy` git checkout
vs the pacman-owned `/usr/share/omarchy`) and fabricated precision: a version boundary
or a config filename asserted with more confidence than the source supports.

So the "~130 possibly-stale causes" figure that appeared in earlier notes was a
worst-case bound on an unreviewed population, not a count of defects. The real number
is 22.

The 2026-09-01 audit stamped a further **7**, so 29 records carry `cause_reconciled`
across two dates. From that pass onward the stamp is applied by `merge_gapfill.py` itself
whenever an auditor supplies a `corrected_cause`. It previously rewrote the cause and
left the field unset, which made the renderers below assert the opposite of what had
happened. See
[../writeups/2026-09-01-merge-gapfill-silent-defects.md](../writeups/2026-09-01-merge-gapfill-silent-defects.md).

Both `ask.py` and the generated markdown still print the full audit note directly
beneath the cause. The line that follows it now says which case you are in: cause
rewritten to match the note, or cause not rewritten and possibly still wrong. Read the
note before trusting the cause on any corrected record; the fix itself is always the
audited version.

This is a research corpus, not a warranty. It is worth reading `danger` and confirming
against the cited source before running anything as root, particularly for anything
touching pacman, the bootloader, initramfs, or partitions.

### Exercising a record on a real machine is a different signal

[validation/](validation/) induces a record's problem on a throwaway Omarchy VM, applies a
fix, and asserts on the machine. It answers a question the audit cannot: **does this work
on Omarchy 4?**

**It never touches `audit_status`, and the two must not be conflated.** `audit_status`
means "checked against its sources". One VM agreeing is not a source confirming. A fix
can pass by accident, pass only on that hardware, or pass while its stated `cause` is
wrong. Results live in `validation/runs.jsonl`, an append-only log, because a record has
one audit but many runs, each with its own date and Omarchy version.

**Being source-audited does not mean being right about the machine, and the first run
proved it.** `mkinitcpio-pacnew-unhandled-breaks-next-boot` is `audit_status: ok` and its
remediation advice checks out, but three of its specifics are false on Omarchy 4:
`/etc/default/limine` is owned by no package and so can never produce the `.pacnew` its
symptom block quotes, `/etc/mkinitcpio.conf` is `[unmodified]` on a stock install and so
cannot either, and overwriting that file does not remove the encryption/plymouth/btrfs
hooks, because those are set by a package-owned drop-in sourced afterwards that assigns
`HOOKS=` wholesale. Generic Arch advice mis-specialised to Omarchy, the same family as
the Omarchy 3 → 4 tree split, and invisible to an auditor reading sources.

Scale expectations accordingly: every scenario needs a hand-written seed and assertions,
and roughly a third of the corpus is out of reach of these VMs anyway (GPU, laptop and
most network records). This is **spot-check and bench-source**, not corpus validation.

### The record schema has one definition

`tools/corpus.py` owns `FIELDS` and the only `read_jsonl` / `write_jsonl`. Both writers
import it. Before 2026-09-01 each kept a private copy, and `ingest.py`'s was missing
`cause_reconciled`; the replace path would have dropped that provenance silently.

`FIELDS` order is load-bearing: it is the key order of every line in `problems.jsonl`.
Append, never reorder. An unrecognised key raises rather than being dropped; harvest
working notes the corpus deliberately discards (`cause_note`, `cause_extra`,
`verify_note`) are enumerated in `WORKFLOW_ONLY`. Adding a schema field still means
editing four things by hand (`schema.sql`, `build_db.py`, `ask.py`, `corpus.py`), but
`tests/` now asserts `FIELDS` against both `schema.sql` and the live corpus, so the
2026-08-30 mistake fails the suite instead of destroying data.

## What is tracked, and what you build

`data/problems.jsonl` is the source of truth and is tracked. `docs/*.md` is generated and
is *also* tracked, because the reason that directory exists is that someone can read a
category page straight out of a clone without running anything. `data/problems.db` is
generated and is **not** tracked: it is a 4 MB binary rewritten in full on every build, so
each commit of it would add another blob that size to history.

So a fresh clone has the corpus and the reading copy, but no search index. Build it once:

```sh
cd research && python3 tools/build_db.py
```

`ask.py` refuses to run without it and prints that exact command, so the failure is loud.

The rule that follows: **any commit touching `data/problems.jsonl` must carry the
regenerated `docs/` with it.** Build, then confirm nothing is left unstaged:

```sh
python3 tools/build_db.py
git diff --exit-code docs/
```

### Nothing hand-written may live in `docs/`

`write_docs()` begins with `for old in DOCS.glob("*.md"): old.unlink()`. That deletes
**every** markdown file in `docs/`, including `docs/README.md`, before regenerating from
the JSONL. Anything hand-written there survives exactly until the next build, silently.

That is why [`bench/`](bench/) is a sibling of `docs/` rather than a page inside it. It
holds skill-efficacy measurements (whether giving a model the Omarchy skill measurably
improves its answers), which is research but **not corpus**: no `audit_status`, no slug,
no source list, and no tooling reads it. It is hand-written and stays that way.

## Refreshing the corpus

Two workflows built this, and either can be re-run with the `Workflow` tool pointed at
its script path:

```sh
# full harvest from scratch: one harvester per category, each audited
python3 tools/ingest.py raw/harvest-result.json        # after tools/harvest-workflow.js
python3 tools/build_db.py

# extend an existing corpus: audit unaudited categories, fill named gaps
python3 tools/merge_gapfill.py raw/gapfill-result.json # after tools/gapfill-workflow.js
python3 tools/build_db.py
```

`ingest.py` replaces the corpus; `merge_gapfill.py` extends it in place and is the one to
use for incremental work.

Pick the workflow by what the records need, not by category. `gapfill-workflow.js`
**harvests new records** against named gaps; it audits nothing that already exists.
To audit records already in the corpus, use `tools/audit-existing-workflow.js` and edit
its `BATCHES`. Pointing `GAP_CATEGORIES` at an unaudited category instead re-harvests the
same topics as `-2` suffixed duplicates and audits none of the originals. The 28
`gapfill-unaudited` records that used to be outstanding here were closed on 2026-09-01.

A note on resuming: `resumeFromRunId` did **not** cleanly replay only the failed agents
here: stalled-agent retries caused it to re-run work and burn budget, and it had to be
stopped. Prefer editing the script to target just the failing categories over resuming.

`raw/deep-research-report.json` is a separate, more heavily verified pass over the same
territory: 13 findings that each survived 3-vote adversarial verification, plus 12
refuted claims. The refuted list is worth reading on its own; it is mostly widely
repeated folk fixes that primary sources actually contradict.
