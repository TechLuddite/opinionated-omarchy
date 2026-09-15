# 05 is deliberately not in this repository

The fifth upstream report in this sequence is a security report, filed with upstream through the
private channel their `.github/SECURITY.md` asks for. It is not committed here, and it should not be
moved here later while it is unresolved.

The working copy lives outside the repository at `~/.local/share/omarchy-security-reports/`, mode
0600 in a 0700 directory.

Neither the mechanism nor the report's contents belong in a public repository before upstream has
had the chance to fix it and say so. If you are picking this up and need the detail, read the local
copy rather than reconstructing it from the corpus.

One honest caveat, recorded because it affects how much protection the private channel is actually
providing: the underlying defect was already described in public before the report was filed, in
this repository's own `JOURNAL.md`, in a corpus record's `danger` field, and independently by a third
party on the upstream tracker. What the private report adds is the exploitability analysis, and that
part is not public. See the session entry for 2026-09-14/15 in [JOURNAL.md](../../JOURNAL.md).
