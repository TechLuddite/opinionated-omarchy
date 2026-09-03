# opinionated-omarchy: the skill this repo exists to produce

**Nothing is written here yet.** This file exists so that whoever writes the first line
knows what the thing is for, what it has to beat, and what would make it dishonest.

The slot is not speculative: it is the settled destination for the skill that turns the
[research corpus](../research/) into something an agent can consume. This file is what
holds the directory open (git tracks files, not directories), so it replaced the
zero-byte `.gitkeep` that used to do the job.

## What it has to be

The corpus is **456 records** of real Omarchy/Arch problems with verified, copy-pasteable
fixes, searchable by symptom (`research/data/problems.jsonl` is the source of truth). It is
currently reachable three ways, and none of them is a skill:

- `research/tools/ask.py`: a CLI, which needs Python and a built index.
- `research/docs/*.md`: ~1.6 MB of generated markdown, far past any context budget.
- <https://techluddite.github.io/opinionated-omarchy/>: the public site, for humans.

So the job is a **retrieval shape**, not a document dump. The interesting design question
is what an agent gets handed: the whole corpus does not fit, and a skill that merely says
"run `ask.py`" adds nothing a tool description could not.

### The retrieval architecture, settled 2026-09-03 with measurements

Three findings, and each closed a design option. **Do not re-derive these.**

**1. Per-category files are already impossible, not a future risk.** Seven of the twelve
`research/docs/*.md` pages exceed a 32K context window *today* at 456 records;
`network.md` is 43.3k tokens. So records must be reachable individually. That also
dissolves the "will a category need splitting in a few years" question: with per-record
granularity a category is **metadata**, so splitting one is a field edit, never a
migration.

**2. No index can be preloaded.** A one-line-per-record index costs 10.2k tokens with just
slug and title, 26.5k with a symptom snippet. Against a 32K budget the skill body must
teach the *search*, never carry the data.

**3. grep does not scale; ranking does. Ship the SQLite index.** Unranked matching over
this corpus returns 22 hits for `bluetooth`, 32 for `nvidia`, 45 for `audio` and **94 for
`boot`**. Reading those is ~94k tokens, and at 10x growth it is hopeless. `ask.py`
already solves this with **FTS5 + bm25 and tuned per-column weights**, returning ranked
top-N regardless of corpus size. Every Python 3.11+ bundles FTS5 and Omarchy ships 3.14,
so the dependency is free. `data/problems.db` is derived and gitignored; ship it prebuilt
or build it on first use.

## What it has to beat, and how you will know

There is a working measurement rig. Do not write this skill blind.
[../skillbench/](../skillbench/) grades whether a skill measurably improves a model, with
**six control benches** of general Linux the skill says nothing about. The controls are
the whole argument: a skill that merely makes answers longer lifts both, and that shows up.
Score a paired run with `skillbench/tools/lift_test.py`, which reports the
difference-in-differences and its p-value rather than two percentages to eyeball.

The bar to clear is on the record. `omarchy/SKILL.md` (the upstream skill, byte-identical
to what the lab benched) lifts Omarchy-specific tasks **+29.3 pt** while moving the
general-Linux controls **−2.3 pt** ([research/bench/](../research/bench/)). A corpus-backed
skill that cannot beat that is not worth shipping, and the bench will say so.

**But that figure was measured on the CHAT lane, and a retrieval skill cannot run there
at all**: no shell, no grep, no file reads. Resolve this before tuning anything. The
shape that survives the contradiction is two jobs in one bundle:

1. **A token-light core of load-bearing facts**: the Omarchy 3 → 4 tree split, Lua rather
   than hyprlang, the ALPM guard. This works in the chat lane, is what the +29.3 pt figure
   is comparable against, and is what the trap bench measures.
2. **Retrieval for depth**: agentic only, where the 456 records live.

Also worth knowing before you pick a target: on the agentic lane **only 4 of 14 local
models can drive the loop at all** ([../skillbench/MODELS.md](../skillbench/MODELS.md)),
and all four already score full marks on the easy benches. Difficulty is not the lever
there; *wrongness* is, which is why `omarchy-agentic-stale-advice` exists.

Add benches for it in `skillbench/benches/` (see the schema in
[benches/CLAUDE.md](../skillbench/benches/CLAUDE.md)) **before** tuning the skill, not
after. Writing the bench second is how you end up measuring what you already built.

Note what the rig can now reach that it could not before 2026-09-01: the agentic lane has
passwordless sudo on its VMs, so a bench can seed, perform and assert work that needs
root. Every task written before that date is a `~/.config` edit because that was the
ceiling, and it is a large part of why the agentic bench saturated. If this skill's value
is in boot, pacman or system-tree territory, that is where its benches belong.

## What would make it dishonest

The corpus carries per-record provenance and that is load-bearing, not decoration:

- `audit_status`: `ok` (240), `corrected` (212), `unaudited` (4).
- `cause_reconciled`: set on the 29 records whose `cause` was rewritten to match their own
  audit note: 22 on 2026-08-30, 7 on 2026-09-01.

**A skill that flattens those into undifferentiated advice launders the 4 never-reviewed
records, and the 212 whose fix an auditor had to rewrite, into the same voice as the
records that passed clean.** Whatever shape the skill takes, an
unaudited record has to still read as unaudited by the time it reaches the user. Both
`ask.py` and the generated markdown already do this; do not regress it.

**And `audit_status: ok` does not mean "true on Omarchy 4".** It means the record was
checked against its sources. The first record exercised on a real VM
(`mkinitcpio-pacnew-unhandled-breaks-next-boot`, status `ok`) turned out to name two files
that cannot produce a `.pacnew` on Omarchy 4 at all, and to overstate a danger that a
package-owned drop-in makes moot. Sound generic Arch advice, mis-specialised. That is
exactly the class of error a source audit cannot see and a skill will happily repeat with
more confidence than the record had. See [../research/validation/](../research/validation/)
for what live exercise does and does not establish; it is a third signal, deliberately
kept out of `audit_status`.

The same applies to `danger`: it is non-empty exactly when a fix can lose data, break boot,
or cause a partial upgrade. Anything touching pacman, the bootloader, initramfs, or
partitions deserves confirmation against the cited source before it runs as root.

## Read before writing

| | |
| --- | --- |
| Corpus design, record schema, trust model | [../research/README.md](../research/README.md) |
| The measurement rig and its limits | [../skillbench/README.md](../skillbench/README.md) |
| The baseline to beat (911 graded cases) | [../research/bench/](../research/bench/) |
| What live VM exercise proves, and what it does not | [../research/validation/](../research/validation/) |
| Repo-wide conventions and domain facts | [../CLAUDE.md](../CLAUDE.md) |
| Current status, what is outstanding | [../JOURNAL.md](../JOURNAL.md) |

The **domain facts** section of the root `CLAUDE.md` is not optional reading. Get the
Omarchy 3 → 4 tree split wrong and the skill will confidently send agents to edit
`/usr/share/omarchy`, which is exactly the failure the agentic bench exists to catch.
