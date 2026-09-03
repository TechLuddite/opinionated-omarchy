# Corpus validation: exercising records against a real Omarchy install

Induce a problem on a throwaway VM, apply a fix, assert on the machine. One record,
one scenario, one appended line in [runs.jsonl](runs.jsonl).

```sh
./run.py scenarios/<slug>.yaml --vm 192.168.122.177
./run.py scenarios/<slug>.yaml --vm 192.168.122.177 --seed-only   # leave it broken
```

**Run this only against a disposable test VM.** Scenarios edit `/etc` and rebuild the
initramfs as root. Reset with `../../tools/golden-test-vm.sh reset 1`, measured at
**0.76 s to reset and ~7 s more to ssh**, so a clean machine per run is essentially free.

## What a green run means, and what it does not

This is the part that matters, and it is deliberately narrow.

A `pass` means: **this scenario's executable reading of the record's prose produced the
asserted end state, on this VM, at this Omarchy version, on this date.**

It does **not** mean the record is correct. A fix can pass by accident, pass only on
this hardware, or pass while its stated *cause* is wrong. So:

- **Validation never touches `audit_status`.** That field means "checked against its
  sources", and one VM agreeing is not a source confirming. Widening it to "…and it
  worked once in a VM" would destroy the distinction the corpus is built on. That is the same
  laundering that made a blanket disclaimer stop carrying information in the 2026-08-30
  session.
- **Results live here, not in `problems.jsonl`.** A record has one audit but many runs,
  each with its own date, Omarchy version and verdict. That is one-to-many, and it does
  not fit a record field. `build_db.py` also deletes and regenerates its outputs, so an
  append-only log has to live outside it.
- **`repair:` is an operator's reading, not the record.** Record fixes are prose with
  branches: triage, a primary path, a conditional fallback, an Omarchy-specific
  variant. Only 6 of 456 records have a fenced `verify` block; the rest describe
  verification in sentences. Nothing here executes "the fix"; it executes one
  interpretation of it, and the scenario says so at the top.

## What this scales to

Not 456. Every scenario needs a hand-written seed and hand-written assertions, and the
expensive part is neither: it is establishing ground truth on a live machine first.
Roughly a third of the corpus is also structurally out of reach of these VMs. That is 67
`nvidia` / 49 `intel` / 47 `amd` records against a virtio GPU, 297 `laptop` and most of
`power-suspend` with no lid and no battery, and much of `network` on a NAT-only bridge.

Treat this as **spot-check and bench-source**, not corpus validation. A scenario that
works is also most of an agentic bench task: `seed:` is a bench `seed:`, and `asserts:`
is most of a bench `post:`.

## Writing a scenario

Assertion types: `command_succeeds`, `command_output_matches`,
`command_output_not_matches`, and `repair_output_matches` / `repair_output_not_matches`
which grade text the repair phase already emitted.

Four traps, all of which bit during the first spike:

- **Assert as root where the target is root-only.** `/boot` is a vfat ESP mounted
  `dmask=0077`, so an unprivileged `test -s /boot/...` returns 1 for *unreadable*, which
  is indistinguishable from *absent*. The first version of the ESP assertion failed for
  this reason and looked like a real defect.
- **Do not assert by re-running the repair.** An assertion that runs
  `limine-mkinitcpio` to read its log rebuilds the boot image just to grade it. Use
  `repair_output_*` against the captured output instead.
- **Assert the artifact this system actually boots.** There is no `/boot/vmlinuz-linux`
  on Omarchy 4; it boots a UKI at `/boot/EFI/Linux/omarchy_linux.efi`.
- **Use a login shell.** `run.py` wraps everything in `bash -lc` because `OMARCHY_PATH`
  comes from `~/.bashrc`, and sudo authenticates via `SUDO_ASKPASS` rather than
  `sudo -S`, which consumes stdin: a `printf ... | sudo tee file` in a seed writes
  the *password* into the file and still exits 0.

Prove an assertion can fail before trusting it. The `mkinitcpio-pacnew` scenario's two
hook assertions were checked against a deliberately destroyed `HOOKS` line, and both
correctly went red.

## Findings from the first spike (2026-09-01)

Scenario: `mkinitcpio-pacnew-unhandled-breaks-next-boot`, against omarchy `4.0.1-1`,
kernel `7.1.9-arch1-2`. **6/6 assertions pass.** The record's remediation advice is
sound and its Omarchy-vs-plain-Arch branch is confirmed by the system itself:
`/usr/local/bin/mkinitcpio` is a wrapper shipped by `limine-mkinitcpio-hook` that warns
`This does not update Limine boot entries` and offers to run `limine-mkinitcpio`
instead, exactly what the record tells you to do.

**Three claims in the same record are wrong for Omarchy 4, and none was caught by the
source audit.** They are recorded here rather than edited into the corpus, because a
correction needs an `audit_note` and a `cause_reconciled` stamp through
`merge_gapfill.py`, not a silent rewrite:

1. **`/etc/default/limine` cannot produce a `.pacnew`.** The record's symptom block
   quotes `warning: /etc/default/limine installed as /etc/default/limine.pacnew`. That
   file exists on Omarchy 4 but is **owned by no package** (`pacman -Qo` errors), so
   pacman never manages it and never writes a `.pacnew` for it. The package-owned file
   is `/etc/limine-entry-tool.conf`, whose own header says to copy it to
   `/etc/default/limine` and edit *that*. The record warns about a `.pacnew` on the very
   file it elsewhere recommends as the override.
2. **`/etc/mkinitcpio.conf` is `[unmodified]` on a stock install**, so it too generates
   no `.pacnew`. Of 30 locally-modified backup files on a fresh VM, it is not one.
3. **The danger claim overstates for Omarchy 4.** "Overwriting `/etc/mkinitcpio.conf`
   with the `.pacnew` removes your encryption, plymouth and btrfs hooks". It does not.
   Those hooks are set by `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` (owned by
   `omarchy-settings`), which is sourced *after* the main file and assigns `HOOKS=`
   wholesale. Measured effective hooks are unchanged by anything done to
   `mkinitcpio.conf`.

This is the "generic Arch advice, mis-specialised to Omarchy" pattern the project keeps
finding, the same family as the Omarchy 3 → 4 tree split.

**One thing deliberately not called a defect.** `limine-mkinitcpio` reports
`Unified kernel image generation successful` while leaving the ESP's UKI untouched. That
looks like a broken install step. It is not: with a genuinely changed input the log gains
a `Copied: … -> /boot/EFI/Linux/omarchy_linux.efi` line and the UKI's size and mtime
change; revert the input and it returns to the original size. The tool skips
byte-identical writes. Verified by changing `MODULES` and reverting, rather than
asserted from the first observation.

**A lead, not a finding.** `/etc/mkinitcpio.conf.d/omarchy_resume.conf` is
`HOOKS+=(resume)`, which appends `resume` *after* `filesystems`, `fsck` and
`btrfs-overlayfs`. That is the exact ordering corpus record
`resume-hook-after-filesystems-hibernation` (one of the 4 remaining `unaudited` records)
describes as a problem. Either the record is wrong or Omarchy ships the broken ordering
by default. **This needs a source check before anyone claims either**; observing the
ordering does not establish which.
