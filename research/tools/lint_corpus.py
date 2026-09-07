#!/usr/bin/env python3
"""Flag corpus records that carry advice known to be wrong on Omarchy 4.

    python3 tools/lint_corpus.py                  # report every hit, grouped by pattern
    python3 tools/lint_corpus.py --check          # exit 1 on any hit not in the baseline
    python3 tools/lint_corpus.py --write-baseline # accept the current hits as known

Option O1 from the 2026-09-06 session. Fifteen `ok` records checked against what
Omarchy 4 actually ships were all wrong, and the defects fell into a handful of
greppable shapes: `mkinitcpio -P` where there are no presets, `sudo pacman -Syu`
where the ALPM guard refuses it, edits to files a tool regenerates, paths from the
Omarchy 3 tree. This is not an audit. A hit is a candidate for the re-audit brief
(`tools/reaudit-brief.md`), and some hits are legitimate, such as a command inside a
branch labelled "plain Arch". The baseline (`data/lint-baseline.json`) records the
hits the corpus carried when the lint landed, so `--check` fails only on NEW ones:
a harvested or edited record that reintroduces a known-bad shape. Clearing a
record from the baseline is a deliberate act that belongs in the commit that
re-audits it.

Only records with `omarchy` in `applies_to` are linted. A record scoped to plain
Arch is allowed to say `mkinitcpio -P`.
"""

import json
import re
import sys
from pathlib import Path

from corpus import read_jsonl

ROOT = Path(__file__).resolve().parent.parent
JSONL = ROOT / "data" / "problems.jsonl"
BASELINE = ROOT / "data" / "lint-baseline.json"

# key -> (regex, why it is suspect on Omarchy 4)
PATTERNS = {
    "mkinitcpio-P": (
        r"mkinitcpio -P\b",
        "/etc/mkinitcpio.d/ is empty on Omarchy 4, so this stops with 'No presets found'. "
        "The rebuild is limine-mkinitcpio, or pacman -S linux."),
    "bare-pacman-Sy": (
        r"pacman -Sy(?![a-z]*u)\b",
        "-Sy without -u is a partial upgrade. A defect anywhere, not only on Omarchy."),
    "sudo-pacman-Syu": (
        r"sudo pacman -Syu\b",
        "The ALPM guard aborts any transaction carrying both -S and -u. The supported path "
        "is omarchy update, or OMARCHY_ALLOW_DIRECT_PACMAN=1 for one transaction."),
    "boot-vmlinuz-or-initramfs": (
        r"/boot/(vmlinuz-linux|initramfs-linux)",
        "Omarchy 4 boots a UKI at /boot/EFI/Linux/omarchy_linux.efi. Neither file exists."),
    "omarchy3-tree": (
        r"\.local/share/omarchy",
        "The Omarchy 3 git checkout. Omarchy 4 is a package at /usr/share/omarchy with "
        "state in ~/.local/state/omarchy."),
    "hyprland-conf": (
        r"hyprland\.conf\b",
        "Omarchy 4 ships hyprland.lua with the hl.* API. hyprlang syntax still parses but "
        "is not what the user's config looks like."),
    "hl-set": (
        r"hl\.set\(",
        "Not part of the Hyprland Lua API. The form is hl.config({ section = { key = v } })."),
    "boot-limine-conf": (
        r"/boot/limine\.conf",
        "limine-entry-tool regenerates it. Kernel parameters go in "
        "/etc/limine-entry-tool.d/*.conf, then limine-mkinitcpio."),
    "hyprctl-dispatch-bare": (
        r"hyprctl dispatch [a-z]",
        "hyprctl dispatch takes Lua on 0.56: hl.dsp.exec_cmd(\"foo\"), not a bare "
        "dispatcher name."),
    "sudo-omarchy-cmd": (
        r"sudo omarchy-",
        "sudo strips OMARCHY_PATH, so every omarchy subcommand fails with "
        "find: '/themes/': No such file or directory. The scripts call sudo themselves."),
    "boot-efi": (
        r"/boot/efi\b",
        "The ESP is mounted at /boot on Omarchy 4."),
}

LINTED_FIELDS = ("symptom", "cause", "fix", "verify", "danger")


def lint_record(rec):
    """Return the sorted list of pattern keys that match this record."""
    if "omarchy" not in (rec.get("applies_to") or []):
        return []
    text = "\n".join(str(rec.get(f) or "") for f in LINTED_FIELDS)
    return sorted(k for k, (rx, _) in PATTERNS.items() if re.search(rx, text))


def lint(records):
    """slug -> [pattern keys], only for records with at least one hit."""
    out = {}
    for rec in records:
        hits = lint_record(rec)
        if hits:
            out[rec["slug"]] = hits
    return out


def load_baseline(path=BASELINE):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def new_hits(current, baseline):
    """Hits in `current` that the baseline does not already carry."""
    out = {}
    for slug, keys in current.items():
        known = set(baseline.get(slug, []))
        fresh = [k for k in keys if k not in known]
        if fresh:
            out[slug] = fresh
    return out


def main(argv):
    records = read_jsonl(JSONL)
    current = lint(records)
    status = {r["slug"]: r.get("audit_status") for r in records}

    if "--write-baseline" in argv:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(current, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        print(f"baseline: {len(current)} records with hits written to {BASELINE.name}")
        return 0

    if "--check" in argv:
        fresh = new_hits(current, load_baseline())
        if not fresh:
            print(f"lint: no hits outside the baseline ({len(current)} known)")
            return 0
        print("lint: NEW hits not in data/lint-baseline.json:")
        for slug, keys in sorted(fresh.items()):
            print(f"  {slug}: {', '.join(keys)}")
        print("Fix the record, or re-audit it and update the baseline deliberately.")
        return 1

    by_pattern = {}
    for slug, keys in current.items():
        for k in keys:
            by_pattern.setdefault(k, []).append(slug)
    for k, (_, why) in PATTERNS.items():
        slugs = sorted(by_pattern.get(k, []))
        ok = sum(1 for s in slugs if status[s] == "ok")
        print(f"\n{k}: {len(slugs)} records, {ok} still `ok`\n  {why}")
        for s in slugs:
            print(f"    {status[s]:9s} {s}")
    print(f"\n{len(current)} of {len(records)} records carry at least one hit")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
