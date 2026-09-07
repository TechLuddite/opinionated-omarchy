# Re-audit brief: is this record true on Omarchy 4?

The prompt handed to each auditor in the 2026-09-06 boot-kernel re-audit, kept because it
found ten defects in ten records. Hand it to one general-purpose agent per one or two
records, with the record JSON and an output directory; assemble the verdicts into a
`merge_gapfill.py` payload scoped to those slugs (one `{"category", "audit": {"verdicts"}}`
entry per category); dry-run on a copy; diff; then merge. The environment facts below are
for the workstation this repo is developed on and go stale with each Omarchy release, so
recheck the versions with `pacman -Q` before reuse.

You are re-auditing records of an Omarchy/Arch troubleshooting corpus. Each record already
passed a source audit with status `ok`, which means "matches its cited sources". The
question now is narrower and harder: is it TRUE ON OMARCHY 4, or is it sound generic Arch
advice mis-specialised to Omarchy? The last five records checked this way were all wrong
somewhere. Look for: files that cannot exist or cannot get a .pacnew on Omarchy 4, paths
from the Omarchy 3 layout, hyprlang syntax where Omarchy 4 ships Lua, commands blocked by
the ALPM guard, hooks or modules Omarchy sets in a drop-in the record ignores, a cited
issue that does not actually support the claim, and version floors that are stale.

## The environment you are on

This machine IS an Omarchy 4 install: omarchy-settings 4.0.2-1, mkinitcpio 41.1-1,
limine-mkinitcpio-hook 1.37.1-1, Hyprland 0.56.2, kernel 7.1.9. Omarchy 4 is
pacman-packaged at /usr/share/omarchy (NOT a git checkout at ~/.local/share/omarchy, that
was Omarchy 3). State is in ~/.local/state/omarchy. It boots a UKI at
/boot/EFI/Linux/omarchy_linux.efi via Limine; there may be no /boot/vmlinuz-linux or
/boot/initramfs-linux.img. /boot is a vfat ESP mounted dmask=0077, so as an unprivileged
user you cannot list it; do not conclude a file is absent from a permission error.
Hooks are assigned wholesale by /etc/mkinitcpio.conf.d/omarchy_hooks.conf (owned by
omarchy-settings), /etc/mkinitcpio.conf is package-stock and unmodified, and
/etc/default/limine is owned by no package (the package template is
/etc/limine-entry-tool.conf from limine-mkinitcpio-hook, kernel cmdline drop-ins are
/etc/limine-entry-tool.d/*.conf). Direct `pacman -Syu` is blocked by an ALPM guard; the
supported path is `omarchy update`, bypass for one transaction is
OMARCHY_ALLOW_DIRECT_PACMAN=1. A bare `pacman -Sy <pkg>` is a partial upgrade and is a
defect in any fix.

You may run READ-ONLY commands here: cat, grep, ls, pacman -Q/-Ql/-Qo/-Qii/-Qkk, systemctl
status/show, journalctl (may need permissions), hyprctl. You have NO sudo. Do not change
anything on this machine. Useful: `ls /usr/share/omarchy/bin | grep <topic>` and reading
the scripts there, `pacman -Ql limine-mkinitcpio-hook`, `cat /etc/limine-entry-tool.d/*`,
`ls /etc/mkinitcpio.conf.d/`, `cat /usr/share/omarchy/default/...`.

## Fetching sources

- wiki.archlinux.org is behind Anubis anti-bot. Fetch raw wikitext:
  `curl -sA 'Mozilla/5.0' 'https://wiki.archlinux.org/index.php?title=<Title>&action=raw'`.
  Cite the canonical https://wiki.archlinux.org/title/<Title> URL.
- The upstream repo is **`omacom/omarchy`** (renamed from `basecamp/omarchy`, which still
  redirects for `gh issue view` but NOT for the search API). Its default branch is
  `quattro`; `master` is Omarchy 3 and 404s on many paths. Use
  `gh api -H 'Accept: application/vnd.github.raw' repos/omacom/omarchy/contents/<path>?ref=quattro`,
  `gh api repos/omacom/omarchy/git/trees/quattro?recursive=1 | jq -r '.tree[].path' | grep <x>`,
  and `gh issue view <n> -R omacom/omarchy --comments`. Read cited issues in full and say
  whether they actually support the claim.
- wiki.hypr.land is JS-only; fetch markdown from hyprwm/hyprland-wiki via gh api
  (content/... paths). Cite the canonical https://wiki.hypr.land/... URL.
- mkinitcpio source: https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/<path>.
- Arch package pages: `curl -s https://archlinux.org/packages/<repo>/x86_64/<pkg>/json/`.
- Never invent a URL. Cite only pages you retrieved.

## Verdict

For each record write `<output directory>/verdict-<slug>.json`:

{"slug": "<slug>", "status": "ok" | "corrected" | "reject", "confidence": "high" | "medium" | "low",
 "reason": "<audit note, 3 to 10 sentences: what you checked, against which source or which local file, what held, what was wrong. Say explicitly when a claim was confirmed on this machine versus from a source. Say what was NOT exercised.>",
 "corrected_cause": "<full replacement, only if wrong>", "corrected_fix": "<full replacement in the same markdown style with fenced blocks, only if wrong>",
 "corrected_symptom": "<only if wrong>", "corrected_danger": "<only if wrong>",
 "sources": ["<every URL you retrieved and relied on>"]}

Omit corrected_* keys you do not need. `ok` means every claim held for Omarchy 4 AND plain
Arch, and the reason must still say what you checked and where. `reject` only if the
problem does not exist. Prefer `corrected` with a full rewrite of the wrong field over
patching prose. Keep what is right; do not restyle correct text.

Writing rules for all prose you produce: no em dashes, no en dashes, no semicolons, plain
specific words, real commands and paths in fenced blocks. Every number, version and file
name verified. Where the record's advice branches Omarchy 4 versus plain Arch, keep both
branches and label them.

Reply to the orchestrator with only: per record, the status, the confidence, and two lines
on the finding. Do not paste the JSON back.
