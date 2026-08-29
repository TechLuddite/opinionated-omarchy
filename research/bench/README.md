# research/bench

Skill-efficacy measurements: does giving a model the Omarchy skill measurably improve
its answers, on what, and at what cost in context?

**This is not part of the troubleshooting corpus.** Nothing in `research/tools/` reads
it, `build_db.py` does not generate it, and it has no `audit_status`. It lives beside
the corpus because it is the same kind of thing — a dated snapshot of measurements with
its provenance attached — not because the tooling knows about it.

> **Why not `research/docs/`?** That directory is machine-owned.
> [`build_db.py:167`](../tools/build_db.py) opens with
> `for old in DOCS.glob("*.md"): old.unlink()` — it deletes every markdown file there
> before regenerating from the JSONL. A hand-written page in `docs/` survives exactly
> until the next corpus build.

## What's here

| Path | What it is |
| --- | --- |
| [nexus1-baseline-2026-08.md](nexus1-baseline-2026-08.md) | The analysis: 911 cases, ten models, measured on the lab's Skill Bench 2026-08-25/27 |
| `raw/nexus1-runs.json` | 12 run records — models, variants, skill shas, spec shas, status |
| `raw/nexus1-cases.json` | 911 case records with per-check pass/fail and the failure note |
| `raw/nexus1-benches/` | The 12 bench specs those runs executed, verbatim |
| `raw/nexus1-skill-sources.yaml` | Upstream provenance and verified shas for the benched skill bundles |

The raw files are the record; the markdown is derived from them by inspection. Every
number in the markdown was computed from `raw/nexus1-cases.json` and can be recomputed.

## Why this baseline is directly usable here

The skill benched on nexus1 is byte-identical to the one in this repo:

```
$ sha256sum omarchy/SKILL.md
a8d88cfbb12e65f6bae1be57dfaeb4a368d313d842911635302752ec2d06adbe
```

which is the sha `raw/nexus1-skill-sources.yaml` records as the verified upstream asset.
Same skill, same models, same bench specs — so a run of [`skillbench/`](../../skillbench)
on this workstation is comparable to these numbers rather than merely similar in spirit.

`diagnose-crash` is **not** identical: this repo carries a 5710-byte `SKILL.md` plus
`reporting.md`, while nexus1 recorded a 4173-byte asset. Treat the crash-forensics
figures as indicative, not as a baseline to reproduce.
