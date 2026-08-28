# CLAUDE.md

Orientation for an agent picking this project up. For current status and what's
outstanding, read [JOURNAL.md](JOURNAL.md).

## What this project is

A working directory for **Omarchy Linux** agent skills and supporting research. Omarchy
is DHH's opinionated Arch + Hyprland distro. Two things live here:

1. **Upstream skills**, downloaded from `basecamp/omarchy` — [omarchy/](omarchy/) (system
   customization: Hyprland, theming, keybindings) and [diagnose-crash/](diagnose-crash/)
   (crash diagnosis from systemd-coredump).
2. **A troubleshooting corpus** in [research/](research/) — 457 real Omarchy/Arch
   desktop+laptop problems with verified, copy-pasteable fixes, searchable by symptom.

This **is** a git repository: `TechLuddite/opinionated-omarchy`, work happening on
`claude/greenfield-repo-setup-l5fzae`. Everything below about what is tracked and what is
generated is enforced by [.gitignore](.gitignore) and [.gitattributes](.gitattributes).

## Layout

```
omarchy/                 upstream skill: system customization  (7 files)
diagnose-crash/          upstream skill: crash diagnosis       (2 files)
opinionated-omarchy/     placeholder for the third skill, nothing written yet
omarchy-old/             placeholder, purpose not yet recorded
research/                the troubleshooting corpus + its tooling
  README.md              design, record schema, trust model — read this first
  data/problems.jsonl    SOURCE OF TRUTH, one JSON record per line
  data/problems.db       DERIVED index; NOT tracked, build it after cloning
  data/categories.json   category key -> display label
  docs/*.md              DERIVED per-category markdown; tracked, see the rule below
  raw/                   unprocessed workflow output, kept for provenance
  tools/                 build/search/ingest scripts + the two workflow scripts
  *.md, *.html, hc.cpp   loose Hyprland wiki pages the user downloaded; NOT corpus
JOURNAL.md               where we stopped, what's left
```

Both placeholder directories hold a zero-byte `.gitkeep`. Git tracks files, not
directories, so an empty directory cannot be committed and would simply vanish from a
clone; the `.gitkeep` is the conventional way to hold the slot open. Delete it when real
content lands.

## Environment

**Omarchy 4.0.0.alpha, Hyprland 0.56.2, bash, Python 3.14, UTF-8 throughout.** The
machine this repo is developed on *is* the system the corpus is about: `/usr/share/omarchy`
is present, so the Omarchy 4 layout described under "Domain facts" can be read directly
rather than inferred.

This repository was previously developed on Windows and has been converted. Nothing here
targets Windows any more, and the concessions it required — ASCII-only stdout, a cp1252
console, `python` rather than `python3` — are gone. Two habits from that era were kept
because they are good practice independent of platform, and both are load-bearing:

- **Generated files are written LF, explicitly.** Every `write_text` / `open("w")` in
  `research/tools/` passes `newline="\n"`, and `.gitattributes` normalises on top. Since
  `research/docs/` is tracked *and* fully regenerated on every build, anything that writes
  native line endings turns a rebuild into a ~1.5 MB whitespace-only diff.
- **Every read and write pins `encoding="utf-8"`.** Never rely on the ambient locale; the
  corpus contains typography, box drawing, arrows and a Nerd Font glyph, and a build that
  silently depended on `LANG` would be reproducible only by accident.

Scripts in `research/tools/` carry `#!/usr/bin/env python3` and are executable, so both
`./tools/ask.py …` and `python3 tools/ask.py …` work. Prefer `python3` over `python` in
anything written here: on Arch they are the same binary, but on a bare container often
only `python3` exists.

Python is not version-pinned — 3.11 through 3.14 all run the tooling, and every one of
them bundles a `sqlite3` with FTS5. A standalone `sqlite3` CLI exists on this machine but
nothing requires it; query through Python so the tooling stays self-contained.

### Verifying against a real install

Fixes can now be *checked*, not only cited. The plan is throwaway Omarchy VMs rather than
the development machine, so a fix that breaks boot or eats a partition costs a snapshot
rollback instead of a workstation. **Not built yet** — `/dev/kvm` is present but no
qemu/libvirt/virt-manager is installed, and the install ISO
(`omarchy-4.0.1.iso`) is sitting in `~/Downloads`.

Note the version skew when that happens: the ISO is **4.0.1** and this workstation is
**4.0.0.alpha**, so a VM is not a mirror of the dev box and a behavioural difference
between them may be a release change rather than a bug.

It does not change the corpus's trust model. `audit_status` records how a record was
verified **against its sources**, and one VM agreeing is not the same as a source
confirming — a fix can work by accident, or work only on that hardware. If you validate a
record live, say so explicitly in the record rather than silently upgrading its status.

## Working with the corpus

```sh
cd research
python3 tools/ask.py "zoom screen share is a black rectangle"   # search by symptom
python3 tools/ask.py --tag nvidia --tag laptop --list           # filter by tag
python3 tools/ask.py --slug some-problem-slug -v                # exact lookup + sources
python3 tools/build_db.py                                       # rebuild DB + docs from JSONL
```

**The JSONL is authoritative; the `.db` and `docs/` are derived.** Edit the JSONL, then
re-run `build_db.py`. Never hand-edit the database or the generated markdown, because the
build deletes and regenerates both.

The two derived artefacts are treated differently by git, and the difference is the whole
of the process:

- **`data/problems.db` is not tracked.** It is a 4 MB binary that is rewritten in full on
  every build, so committing it would put a new multi-megabyte blob in history each time.
  A fresh clone has no index. `ask.py` exits with `no database at ... Run: python
  tools/build_db.py`, so nothing fails silently, but **build it once after cloning.**
- **`docs/*.md` is tracked.** The point of that directory is that a human or an agent can
  read a category page straight out of the clone with no Python and no build step. That
  only holds if it is in the clone.

Which gives one rule: **a commit that changes `data/problems.jsonl` must change
`research/docs/` in the same commit.** Run the build before you stage anything, and check
that nothing is left over:

```sh
cd research && python3 tools/build_db.py
git diff --exit-code research/docs/     # must be clean once the build output is staged
```

There is no refresh cadence, and inventing one would be dishonest about what this is. The
corpus is a dated snapshot, not a feed. Rebuild when the JSONL changes; re-run a harvest
workflow only when there is a reason, such as the 28 records still awaiting audit or an
Omarchy release that changes the underlying facts. See [JOURNAL.md](JOURNAL.md).

Two ingest paths, and picking the wrong one destroys work:

- `tools/ingest.py` **replaces** the corpus from a full harvest result.
- `tools/merge_gapfill.py` **extends** it in place. Use this for incremental work.

Every record carries an `audit_status` (`ok` / `corrected` / `unaudited` /
`gapfill-unaudited`) recording how much scrutiny it survived. Unaudited records are
flagged in both the CLI and the markdown. **Preserve that honesty** — if you add records,
mark their provenance rather than letting them blend in with audited ones.

## Domain facts that are load-bearing

Get these wrong and you will write fixes that break machines. They were all verified
against primary sources during the research and repeatedly caught stale advice.

- **`basecamp/omarchy`'s default branch is `quattro`, not `master`.** `master` is still
  the Omarchy 3 tree; several raw URLs 404 against it. Fetch from `quattro`.
- **Omarchy 4 ("Quattro") is pacman-packaged at `/usr/share/omarchy`**, with state in
  `~/.local/state/omarchy`. It is *not* a git checkout at `~/.local/share/omarchy` —
  that was Omarchy 3, and most advice online still assumes it.
- **Hyprland 0.55+ deprecated hyprlang in favour of Lua.** Config is `hyprland.lua` using
  the `hl.*` API (`hl.bind`, `hl.monitor`, `hl.window_rule`). Old `hyprland.conf` syntax
  still works but is not what Omarchy 4 ships. The 0.54 wiki has the old syntax.
- **Direct `pacman -Syu` is blocked** on Omarchy by an ALPM guard; the supported path is
  `omarchy update`. Bypass for one transaction with `OMARCHY_ALLOW_DIRECT_PACMAN=1`.
- **`pacman -Sy <pkg>` alone is a partial upgrade** and a classic way to break a system.
  Always `-Syu`. Treat any fix containing bare `-Sy` as a defect.
- The Omarchy menu is **Super+Space**; Super+Alt+Space is the Apps menu.

## Fetching sources

- **`wiki.archlinux.org` sits behind Anubis anti-bot.** `WebFetch` returns "Access
  Denied". Use `index.php?title=X&action=raw` or `rest.php/v1/page/X`, or `curl` with a
  browser user-agent. Cite the canonical `/title/` URL regardless.
- **`wiki.hypr.land` is JS-only.** Fetch the markdown source from the
  `hyprwm/hyprland-wiki` repo instead (`content/...`), e.g. via the `gh` API.
- `gh` CLI is authenticated and works for GitHub API queries.

## Conventions

- Never invent a source URL. A record cites only pages actually retrieved; `build_db.py`
  filters anything that isn't `http(s)://` and warns on records with no usable source.
- Fixes must be concrete — real commands, real paths, real config in fenced blocks. "Check
  your configuration" is not a fix and the audit rejects it.
- Fill `danger` whenever a fix can lose data, break boot, or cause a partial upgrade.
- The corpus is research, not a warranty. Anything touching pacman, the bootloader,
  initramfs, or partitions deserves a confirmation against the cited source before it
  runs as root.

## Regenerating the corpus

Both workflow scripts live in `research/tools/` and run via the `Workflow` tool pointed
at their `scriptPath`:

- `harvest-workflow.js` — full harvest from scratch: one harvester per category, each
  audited, plus a gap-fill pass. ~35 agents, expensive.
- `gapfill-workflow.js` — extend an existing corpus: audit unaudited categories and fill
  auditor-named gaps. ~25 agents.

These consume a lot of budget (the first harvest died partway through on a spend limit).
Check `/usage-credits` before launching, and prefer trimming a workflow's category list
over re-running everything. `resumeFromRunId` did **not** behave well here — see
[JOURNAL.md](JOURNAL.md).
