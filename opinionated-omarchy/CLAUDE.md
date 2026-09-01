# opinionated-omarchy — the skill this repo exists to produce

**Nothing is written here yet.** This file exists so that whoever writes the first line
knows what the thing is for, what it has to beat, and what would make it dishonest.

The slot is not speculative: it is the settled destination for the skill that turns the
[research corpus](../research/) into something an agent can consume. `.gitkeep` holds the
directory open because git tracks files, not directories; delete it when real content
lands.

## What it has to be

The corpus is **456 records** of real Omarchy/Arch problems with verified, copy-pasteable
fixes, searchable by symptom (`research/data/problems.jsonl` is the source of truth). It is
currently reachable two ways, and neither is a skill:

- `research/tools/ask.py` — a CLI, which needs Python and a built index.
- `research/docs/*.md` — ~1.7 MB of generated markdown, far past any context budget.

So the job is a **retrieval shape**, not a document dump. The interesting design question
is what an agent gets handed: the whole corpus does not fit, and a skill that merely says
"run `ask.py`" adds nothing a tool description could not.

## What it has to beat, and how you will know

There is a working measurement rig — do not write this skill blind.
[../skillbench/](../skillbench/) grades whether a skill measurably improves a model, with
**five control benches** of general Linux the skill says nothing about. The controls are
the whole argument: a skill that merely makes answers longer lifts both, and that shows up.

The bar to clear is on the record. `omarchy/SKILL.md` — the upstream skill, byte-identical
to what the lab benched — lifts Omarchy-specific tasks **+29.3 pt** while moving the
general-Linux controls **−2.3 pt** ([research/bench/](../research/bench/)). A corpus-backed
skill that cannot beat that is not worth shipping, and the bench will say so.

Add benches for it in `skillbench/benches/` (see the schema in
[benches/CLAUDE.md](../skillbench/benches/CLAUDE.md)) **before** tuning the skill, not
after. Writing the bench second is how you end up measuring what you already built.

## What would make it dishonest

The corpus carries per-record provenance and that is load-bearing, not decoration:

- `audit_status` — `ok` (240), `corrected` (212), `unaudited` (4).
- `cause_reconciled` — set on the 29 records whose `cause` was rewritten to match their own
  audit note: 22 on 2026-08-30, 7 on 2026-09-01.

**A skill that flattens those into undifferentiated advice launders the 4 never-reviewed
records, and the 212 whose fix an auditor had to rewrite, into the same voice as the
records that passed clean.** Whatever shape the skill takes, an
unaudited record has to still read as unaudited by the time it reaches the user. Both
`ask.py` and the generated markdown already do this; do not regress it.

The same applies to `danger`: it is non-empty exactly when a fix can lose data, break boot,
or cause a partial upgrade. Anything touching pacman, the bootloader, initramfs, or
partitions deserves confirmation against the cited source before it runs as root.

## Read before writing

| | |
| --- | --- |
| Corpus design, record schema, trust model | [../research/README.md](../research/README.md) |
| The measurement rig and its limits | [../skillbench/README.md](../skillbench/README.md) |
| The baseline to beat (911 graded cases) | [../research/bench/](../research/bench/) |
| Repo-wide conventions and domain facts | [../CLAUDE.md](../CLAUDE.md) |
| Current status, what is outstanding | [../JOURNAL.md](../JOURNAL.md) |

The **domain facts** section of the root `CLAUDE.md` is not optional reading. Get the
Omarchy 3 → 4 tree split wrong and the skill will confidently send agents to edit
`/usr/share/omarchy`, which is exactly the failure the agentic bench exists to catch.
