# Journal — handoff

Last updated: 2026-08-28

## Where we stopped

Three things happened in this project so far:

0. **The working directory became a git repository.** It is now
   `TechLuddite/opinionated-omarchy`, on branch `claude/greenfield-repo-setup-l5fzae`.
   Nothing about the corpus changed. What changed around it:
   - `research/data/problems.db` is no longer tracked, because it is a 4 MB binary
     rewritten in full on every build. **Run `python3 tools/build_db.py` after cloning**
     or `ask.py` will not have an index. `research/docs/` stays tracked so a clone is
     readable without running anything. The rule that follows is in
     [CLAUDE.md](CLAUDE.md): a commit touching `problems.jsonl` carries the regenerated
     `docs/` with it.
   - Six `write_text` / `open("w")` calls in `research/tools/` were writing platform
     newlines, so `docs/*.md` and `data/categories.json` came out CRLF on Windows. With
     `docs/` now tracked that would have made every rebuild a 1.5 MB whitespace diff.
     All six now pin `newline="\n"`, the affected files were regenerated as LF, and
     `.gitattributes` normalises on top. `research/raw/` and the loose wiki downloads
     are marked `-text` so their bytes are preserved exactly as harvested.
   - `opinionated-omarchy/` and `omarchy-old/` each hold a zero-byte `.gitkeep`, because
     git cannot commit an empty directory.

Before that:

1. **Downloaded the two upstream Omarchy skills** into [omarchy/](omarchy/) and
   [diagnose-crash/](diagnose-crash/). Complete, verified, nothing pending.
2. **Built a troubleshooting corpus** in [research/](research/) — 457 Omarchy/Arch
   desktop+laptop problems with copy-pasteable fixes, searchable by symptom.
   Complete and usable. See [research/README.md](research/README.md) for the design,
   trust model, and record schema.

The corpus is in a good, self-consistent state: 457 records, 769 distinct sources, no
duplicate slugs, every record cites a real fetched URL, and it rebuilds reproducibly
from JSONL.

## What's left

### 1. Finish auditing 28 records  (the only real loose end)

`wayland-compat` (12) and `network` (16) gap-fill records are harvested but never
audited — their two audit agents died on API streaming errors. They are flagged
`gapfill-unaudited` and surface a warning in both `ask.py` and the generated markdown,
so nothing is silently untrustworthy; they just haven't been checked.

To close: edit `GAP_CATEGORIES` in [research/tools/gapfill-workflow.js](research/tools/gapfill-workflow.js)
down to those two categories, run it, then:

```sh
cd research
python3 tools/merge_gapfill.py raw/gapfill-result.json
python3 tools/build_db.py
```

**Do not use `resumeFromRunId` for this.** It was tried and did not cleanly replay only
the failed agents — stalled-agent retries caused it to re-run completed work and consume
budget, and it had to be killed. Editing the category list is cheaper and predictable.

### 2. Stale `cause` fields on first-pass corrected records  (known, mitigated)

The first harvest's audits rewrote only `fix`, so roughly 130 `corrected` records may
still carry a `cause` the auditor disproved. The second pass added `corrected_cause`
(20 causes were replaced), but the first pass's records were not revisited. The audit
note is printed directly beneath the cause everywhere, with a warning, so a reader is
never misled — but a re-audit pass over first-pass records would be a genuine
improvement if anyone wants it.

### 3. Optional / not started

- `opinionated-omarchy/` at the root is still empty, held open by a `.gitkeep`. It is
  presumably the placeholder for a third skill. Nothing has been written there.
- `omarchy-old/` is also empty and held open by a `.gitkeep`, but **its purpose is not
  recorded anywhere.** Perry confirmed both directories exist because they have a planned
  purpose; that purpose needs writing down here before anyone else has to guess at it.
- Nothing turns the corpus into an actual Claude skill yet. That's the obvious next step
  if the goal is agent-consumable troubleshooting: a `SKILL.md` that tells an agent to
  query `research/tools/ask.py` by symptom.
- `research/` root holds ~17 loose Hyprland wiki pages the user downloaded
  (`binds.md`, `anim.md`, `lua.html`, `hyprctl.md`, `hc.cpp`, …). They are **not** part
  of the corpus and no tooling reads them. Left in place deliberately; could move to a
  `reference/` subfolder.

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

The refuted list in the deep-research report is worth a read on its own — it is mostly
widely repeated folk fixes that primary sources actually contradict.

## Gotchas that cost time

Full list in [CLAUDE.md](CLAUDE.md). The three that bit hardest:

- **`basecamp/omarchy`'s default branch is `quattro`, not `master`.** `master` is still
  the Omarchy 3 tree and several raw URLs 404 against it.
- **Omarchy 4 is pacman-packaged at `/usr/share/omarchy`** — not a git checkout in
  `~/.local/share/omarchy`. Most stale advice online assumes the old layout.
- **`wiki.archlinux.org` is behind Anubis anti-bot**; `WebFetch` gets "Access Denied".
  Use `index.php?title=X&action=raw` or `rest.php/v1/page/X`.
