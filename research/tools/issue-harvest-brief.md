# Issue-harvest brief: records from the Omarchy tracker, confirmed fixes only

Option O4 from the 2026-09-06 session. You are turning `omacom/omarchy` issue threads
(formerly `basecamp/omarchy`; the old name redirects for `gh issue view`) into records of
the opinionated-omarchy troubleshooting corpus. Thirty-seven of thirty-seven corpus records
checked against Omarchy 4 were wrong, and six cited issues that did not support them, so
this harvest has one standard: **a record exists only for a problem whose fix is confirmed
in the thread**, by a maintainer (dhh, or anyone whose merged PR or commit closes it), by
a linked commit or PR that plainly makes the change, or by a second reporter saying the
same fix worked. A plausible workaround one person posted and nobody confirmed is not a
record. Say so in `skipped` and move on.

## Before anything else

1. Read `tools/reaudit-brief.md` (relative to the corpus root you were given) in full. It
   says what Omarchy 4 ships and how to fetch the Arch wiki, the Hyprland wiki and the
   `quattro` tree. Every fix you write is held to it: `omarchy update` not `sudo pacman
   -Syu`, `limine-mkinitcpio` not `mkinitcpio -P`, `hl.config` not `hl.set`,
   `/etc/limine-entry-tool.d/` not `/boot/limine.conf`, never `sudo omarchy-<cmd>`.
2. Read each issue you were assigned IN FULL, with comments:
   `gh issue view <N> -R omacom/omarchy --comments`. Follow linked PRs and commits
   (`gh pr view <N> -R omacom/omarchy`, `gh api repos/omacom/omarchy/commits/<sha>`) when
   they are what confirms the fix. Do not write from the title.
3. Check the corpus before writing: `grep -i '<key words>' data/problems.jsonl | cut -c1-200`
   and read any record that looks close. If a record already covers the problem, do NOT
   write a new one. Put it under `existing` with the slug and one sentence on what the
   issue adds or contradicts. That list feeds the next re-audit.

## What a record is

One JSON object with exactly these keys (the audit keys are set by the pipeline, not you):

- `slug`: kebab-case, unique, descriptive, no `omarchy-` prefix unless the problem is
  about the omarchy tooling itself. Check it is not already in `data/problems.jsonl`.
- `title`: short imperative, names the error where there is one.
- `category`: one of `omarchy-core omarchy-theming hyprland-config display-monitors
  wayland-compat pacman-aur boot-kernel gpu-drivers power-suspend audio-input network
  apps-services`.
- `symptom`: how the reporter described it, with the literal error text in a fenced block
  when there is one, and the Omarchy version or channel where the thread names it.
- `cause`: what the thread established, not what you infer. If the maintainer named the
  cause, that. If only the fix is known, say the cause is not established in the thread.
- `fix`: copy-pasteable. Real commands, real paths, real config in fenced blocks. Where
  the fix is "update", say which version or migration carries it and give `omarchy
  update`. Where Omarchy 4 and plain Arch differ, both branches, labelled.
- `verify`: how the reporter or maintainer confirmed it, as a command where possible.
- `applies_to`: tags from this set where true: `omarchy arch hyprland wayland nvidia amd
  intel laptop desktop limine luks btrfs quickshell omarchy-shell` plus the hardware or
  app the thread names. Always include `omarchy`.
- `severity`: `critical` (unbootable, data loss) `high` (core function broken) `medium`
  `low`.
- `frequency`: `very-common common occasional rare`, judged from the thread (number of
  "me too" reporters, whether a maintainer called it widespread).
- `danger`: non-empty exactly when the fix can lose data, break boot, or cause a partial
  upgrade. Otherwise the empty string.
- `sources`: the canonical issue URL `https://github.com/omacom/omarchy/issues/<N>` first,
  then every PR, commit, wiki page or file you actually retrieved and relied on. Never a
  URL you did not fetch.

## Output

Write `<output directory>/harvest-<batch>.json` as:

```json
{"records": [ ...record objects... ],
 "existing": [{"number": 1234, "slug": "existing-record-slug", "note": "what the issue adds"}],
 "skipped": [{"number": 1234, "why": "one sentence: unconfirmed, feature request, not a user problem, ..."}]}
```

Every assigned issue appears in exactly one of the three lists. An empty `records` list
is a valid result. Do not pad.

## Writing rules

No em dashes, no en dashes, no semicolons in prose. Plain specific words. Reproduce error
text and quoted commands exactly, dashes included. Every version, path and file name
verified, from the thread or from this machine. Say in the `cause` or `fix` when
something was reported on one machine only.

Reply to the orchestrator with only: how many records, existing and skipped, and one line
per record (slug and the issue number). Do not paste the JSON back.
