# What the two bundles actually answer

A bench can only measure a skill on ground the skill covers. A task outside that ground
measures noise, and the result looks exactly like "the skill does not work". So this is the
menu a bench may order from, taken by reading `omarchy/` and `diagnose-crash/` rather than
from the corpus or from memory.

**The bench adapts to the skill, never the reverse.** `omarchy/SKILL.md` must stay
byte-identical or the +29.3 pt chat-lane baseline stops being comparable, and both bundles
are redistributed unmodified under upstream's licence.

## What is in the bundle

`skills.yaml` lists files explicitly, so this is the whole surface:

| variant | files | size |
| --- | --- | ---: |
| `omarchy` | `SKILL.md` | 13.2 KB |
| `omarchy-full` | `+ hyprland.md theming.md capture.md plugins.md hooks.md contributing.md` | 26.4 KB |
| `diagnose-crash` | `SKILL.md` | 5.7 KB |
| `diagnose-crash-full` | `+ reporting.md` | 9.7 KB |

A task answerable only from a topic guide can lift `omarchy-full` and never `omarchy`. That
difference is the reason both variants exist.

## The trap seams: where the packaged answer differs from the published one

These are the only places a skill can produce a lift, because everywhere else a competent
model already knows the answer. Ranked by how wrong the widely-published answer is.

### 1. Idle and lock live in `shell.json`, not in Hyprland

**Published answer:** Hyprland uses `hypridle` and `hyprlock`; edit `~/.config/hypr/hypridle.conf`.
**Omarchy 4:** `idle.screensaver` and `idle.lock` in `~/.config/omarchy/shell.json`, read by
the Omarchy shell. `hyprlock` is not even installed.
**Why it is a good trap:** the wrong answer creates a file that does nothing, so it is
distinguishable from doing nothing, and asserting on it is exact.
**Verified on a test VM 2026-09-05:** `hyprlock` and `hypridle` are **not installed**, and
the packaged default is `idle: {screensaver: 150, lock: 300}`. The published answer does not
merely differ, it targets software that is not on the machine.

### 2. Customising a stock theme means overlaying, never editing

**Published answer:** edit the theme's colour file.
**Omarchy 4:** put an edited `colors.toml` in `~/.config/omarchy/themes/<stock-name>/`, which
overlays the packaged theme, then re-apply. Editing `/usr/share/omarchy/themes/` is
explicitly forbidden and is reverted by the next `omarchy update`.
**Why it is a good trap:** the wrong answer is *destructive*, and `pacman -Qkk omarchy`
detects it, so a wrong answer can be scored below doing nothing.
**Verified 2026-09-05:** `pacman -Qkk omarchy` reports `1654 total files, 0 altered files`
on a clean VM, and that assertion is already proven in `omarchy-agentic-root-config`.

### 3. Built-in plugins are cloned, and cloning renames them

**Published answer:** edit the plugin.
**Omarchy 4:** `omarchy plugin clone omarchy.workspaces` copies it to
`~/.config/omarchy/plugins/<username>.workspaces/` **under the operator's username**, and the
bar switches to the clone. Editing the packaged copy is forbidden.
**Why it is a good trap:** the username rename is specific, non-guessable and exactly
assertable.
**Verified 2026-09-05:** `omarchy-plugin-clone` line 131 is
`new_id="${USER:-$(id -un)}.${source_id#omarchy.}"`. Note it carries the same `$USER`
fallback this repo already documents as a trap, so a bench seeding it must not assume
`$USER` is set in a non-interactive shell.

### 4. Two Hyprland files are not applied by `hyprctl reload`

**Published answer:** edit the config, `hyprctl reload`.
**Omarchy 4:** `hyprsunset.conf` and `xdph.conf` are read by *separate processes*.
`hyprctl` neither applies nor validates them. Night light needs
`omarchy restart hyprsunset`; the portal applies at next login.
**Why it is a good trap:** the wrong answer looks like it worked.

### 5. Rebinding requires an explicit `hl.unbind` first

Already used by `omarchy-agentic-stale-advice`. Kept here because the seam is real, but see
the warning below.

### 6. Config is Lua, not hyprlang

Also already used. `~/.config/hypr/*.lua` with `hl.*` and `o.*`, not `hyprland.conf`.

### 7. Smaller seams, verified present in the bundle

- `omarchy debug` **must** carry `--no-sudo --print`, or it hangs on a sudo prompt.
- `omarchy refresh config <path>` takes a path **relative to `~/.config/`**.
- `omarchy pkg add` rather than `pacman -S`; direct `pacman -Syu` is guarded.
- `sudo` when a terminal can take a password, `pkexec` when it cannot. Not interchangeable.
- Hooks are `~/.config/omarchy/hooks/<name>.d/` directories, installed with
  `omarchy hook install`.

## What is NOT in the bundle, and therefore untestable

Do not build a bench on any of this, however good a task it would make:

- Anything in `research/data/problems.jsonl`. **The corpus is not the skill.** 456 records of
  NVIDIA, audio, boot and network troubleshooting have no counterpart in these 39 KB.
- Hardware-specific failure: GPU drivers, suspend, Bluetooth, printing.
- Omarchy source development, which `SKILL.md` puts explicitly out of scope.
- Window-rule syntax. The skill deliberately refuses to state it and tells the reader to
  fetch the current wiki page, so there is no packaged answer to reward.

## Two constraints from measurement, not from taste

**Hard enough for the model class.** `omarchy-agentic-stale-advice` scores **0.90 to 0.97
bare** for GLM-class models. It was calibrated against `devstral-small-2:24b`, which solves
it 8 times in 20. A bench that saturates cannot measure anything, and a saturated control is
why the difference-in-differences was weak in runs 25 and 26.

**Reward acting, not researching.** Run 43 found the skill diverting an agent into
`/usr/share/omarchy/` to study the binding API while it never edited the user file: zero
edits and zero clean stops across 20 cases, against 7 of each on the sibling task. A task
whose answer is "go and read the packaged defaults" plays to that failure. Prefer tasks where
the skill names a **destination and an action**, and where the post assertions check the
machine changed.

Both of these argue for seams 1, 2 and 3 over seam 5.
