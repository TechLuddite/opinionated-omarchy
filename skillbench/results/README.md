# Banked bench results

Every measurement the Skill Bench has produced, in a form that survives the machine it was
produced on. Regenerate with:

```sh
python3 skillbench/tools/export_results.py
```

## Why this is tracked when `data/` is not

The repo's usual rule is that derived artefacts are rebuilt rather than committed, and
`skillbench/data/skillbench.db` is gitignored under exactly that rule. But the rule assumes
the artefact **can** be rebuilt. `research/data/problems.db` regenerates from the JSONL in
0.2 s. This one regenerates from nothing.

It is the record of many hours of GPU time across 31 runs, and every figure in
[JOURNAL.md](../../JOURNAL.md) and [MODELS.md](../MODELS.md) traces back to it. Until this
export existed, one disk sat between the project and its entire measured history, and the
failure mode was not "lose a file" but "every number in the journal becomes an unsupported
claim".

## What is here

| file | one line per | why |
| --- | --- | --- |
| `runs.jsonl` | run | metadata, plus per-variant and per-task aggregates computed exactly as `app/main.py:_agg` does, so a journal figure can be checked without SQL or the container |
| `cases.jsonl` | case | status, timings and grade tallies, so every significance test in the journal is re-derivable |
| `grades.jsonl` | assertion | *which* check failed is the actual diagnostic, and it is the one thing no summary reconstructs |
| `specs/<sha>.json` | distinct spec | benches are sha-pinned, so a run stays interpretable even after its spec is edited |

## What is deliberately dropped

`case_result.request` is 4.87 MB of the ~5.7 MB database: the full prompt, re-recorded for
every case. It is derivable from the spec, which is exported beside it, so keeping it would
multiply the tracked size by ten to preserve nothing. The non-prompt keys inside it
(`lane`, `vm`, `queue_wait_s`) **are** kept, since those are per-case facts that exist
nowhere else.

The spec files are **pretty-printed JSON, not the original YAML, and cannot be checked
against their filename.** `spec_sha` is `sha256` of the raw YAML file, while the database
stores a re-serialised parse of it, so the sha identifies *which* spec ran and the file
records *what that spec contained*. Reformatting therefore loses nothing that was not
already gone, and turns a 6 KB single-line blob into something readable.

## Reading the numbers correctly

**`state` in `runs.jsonl` is a micro-average**, `post_passed / post` summed over cases.
**`lift_test.py` uses a macro-average**, the mean of per-case ratios, because
[the unit is the case, not the assertion](../tools/lift_test.py): the 6 post assertions in
one case are heavily correlated and treating them as independent samples manufactures
significance.

The two agree when every case has the same number of post assertions and diverge slightly
when they do not. Run 28 has 6 everywhere, so both give 0.8710. Run 31 mixes 6 and 5, so the
micro-average reads 0.7478 against a macro-average of 0.7473. Neither is wrong. Quote the
macro-average for anything inferential.

## One thing this cannot give you

**The agentic transcripts were never captured.** `app/runner.py` invokes `pi` without
`--mode json`, so it stored only the final text, which is a median of 16 characters across
roughly 600 agentic cases, and no token accounting at all. Run 21's finding that 11 of 14
local models cannot drive an agent loop was reached by reading transcripts live, and those
transcripts are gone. The conclusion is probably right. It is no longer re-derivable from
anything in this repository, and that limit is recorded in [MODELS.md](../MODELS.md) too.
