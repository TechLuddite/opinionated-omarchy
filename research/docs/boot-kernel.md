# Boot, kernel & initramfs

37 problems. Sorted by severity, then by how often users hit it.

## Recover from "ERROR: device 'UUID=...' not found" dropping to an initramfs emergency shell

`emergency-shell-device-uuid-not-found` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** After a `pacman -Syu` (or after cloning/resizing/reformatting a disk) the machine no longer boots. Instead of the desktop you get a tiny busybox prompt:

```
:: running early hook [udev]
ERROR: device 'UUID=6f3c1b2a-...' not found. Skipping fsck.
:: mounting 'UUID=6f3c1b2a-...' on real root
mount: /new_root: can't find UUID=6f3c1b2a-...
ERROR: Failed to mount 'UUID=6f3c1b2a-...' on real root
You are now being dropped into an emergency shell.
sh: can't access tty; job control turned off
[rootfs ]#
```

**Cause.** The initramfs cannot find the root device the kernel command line told it to mount. Three realistic causes: (a) the UUID in the bootloader's `root=` parameter no longer matches the filesystem (disk re-created, restored image, new SSD); (b) the initramfs is missing the hooks needed to expose the device (`block`, or `encrypt`/`sd-encrypt` for LUKS, `lvm2` for LVM); (c) mkinitcpio failed or was interrupted mid-run and wrote a truncated/incomplete image.

> **Audit corrected this record.** Diagnosis and one-boot bootloader edits are correct, but the persistence step is wrong on two loaders. `bootctl update` only refreshes the systemd-boot EFI binary on the ESP; it does not regenerate or fix boot entries, so a stale root= survives it. And on Omarchy `/boot/limine.conf` is destroyed on every `omarchy-refresh-limine` (verified: the script does `mv /boot/limine.conf /boot/limine.conf.bak` then copies a template), so a root= fixed there is lost at the next update. HOOKS line itself is current and correct.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing the kernel command line permanently in the wrong place can leave you with no bootable entry at all. Always test the change as a one-off edit in the boot menu first, and never delete the fallback entry until the default entry boots.

**Fix.**

From the emergency shell, compare what exists against what was asked for:

```sh
blkid
cat /proc/cmdline
```

One-boot menu edit (GRUB: `e`, fix root=UUID, Ctrl+X / Limine: `e`, fix `cmdline:`, Enter / systemd-boot: `e`, edit appended cmdline).

Once booted, make it permanent:

```sh
sudo blkid
sudoedit /etc/fstab
sudo systemctl daemon-reload
sudo mount -a          # must return clean BEFORE you reboot
sudo mkinitcpio -P
```

Then persist root= in the place your loader actually reads:

```sh
# GRUB
sudo grub-mkconfig -o /boot/grub/grub.cfg

# systemd-boot: bootctl update does NOT touch entries. Edit the entry itself:
sudoedit /boot/loader/entries/arch.conf     # fix the `options root=UUID=...` line
sudo bootctl update                          # only refreshes the EFI binary

# Omarchy / Limine: /boot/limine.conf is overwritten by omarchy-refresh-limine.
# The persistent cmdline lives here instead:
sudoedit /etc/default/limine                 # KERNEL_CMDLINE[default]="..."
# or a drop-in: /etc/limine-entry-tool.d/<name>.conf with KERNEL_CMDLINE[default]+=" ..."
sudo limine-mkinitcpio
```

If you cannot boot at all, use the fallback entry, or repair via chroot from a live USB.

Minimum HOOKS in /etc/mkinitcpio.conf:

```sh
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)
```

For LUKS add `encrypt` (busybox initramfs) or `sd-encrypt` (systemd initramfs) before `filesystems`.

**Verify.** `sudo mkinitcpio -P` finishes with no `==> ERROR` lines, `cat /proc/cmdline` after reboot shows the correct root UUID, and the system boots to the display manager/Hyprland without touching the boot menu.

Sources: <https://forum.endeavouros.com/t/error-device-not-found-drops-to-emergency-shell/39005> · <https://forum.endeavouros.com/t/solved-boots-into-emergency-shell-after-update-encrypted-root-is-not-mounted/38101> · <https://man.archlinux.org/man/mkinitcpio.8> · <https://man.archlinux.org/man/mkinitcpio.conf.5>

---

## Free space on a full /boot or ESP when kernel installs fail

`esp-boot-partition-full-no-space` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `nvidia`, `omarchy`, `systemd-boot`

**Symptom.** `pacman -Syu` fails part-way through a kernel update and the machine may not survive the next reboot:

```
install: cannot create regular file '/boot/vmlinuz-linux': No space left on device
==> ERROR: failed to install kernel to /boot
```

or on kernel-install/dracut systems:

```
install: Errors when writing '/efi/<machine-id>/6.9.1-zen1-1-zen/linux': No more storage space available on the device
```

`df -h /boot` shows 100% used. Typical on 300–512 MB EFI System Partitions.

**Cause.** The ESP is mounted at `/boot` (or `/efi`) and holds one kernel + one initramfs + one *fallback* initramfs per installed kernel. Fallback images are 100–300 MB each; add NVIDIA/DKMS modules or a UKI layout and a 512 MB ESP fills after two or three kernels. Old images from removed kernels are never cleaned up automatically.

> **Audit corrected this record.** Diagnosis and the du/df triage are fine, and the rm commands are correctly targeted (no rm -rf on a system path). But it tells the user to delete the fallback initramfs and disable the fallback preset with no warning that the fallback image is precisely the recovery path record [1] depends on — after this change, a broken default initramfs leaves no way in except a live USB. It also omits that /etc/mkinitcpio.d/*.preset is a pacman backup file, so the edit reappears as a .pacnew, and on Omarchy/UKI setups the ESP consumer is limine-entry-tool's UKIs, not the plain preset images.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting the wrong file in /boot (a vmlinuz or initramfs for a kernel you still use) makes the system unbootable. Removing the fallback image removes your rescue option. Repartitioning the ESP risks total data loss — take a full backup first, and never reboot with a half-written kernel: always re-run `pacman -S linux` and confirm both vmlinuz and initramfs exist before rebooting.

**Fix.**

Triage first:

```sh
df -h /boot
sudo du -xh --max-depth=2 /boot | sort -h | tail -20
ls -la /boot
pacman -Q | grep -E '^linux'      # what kernels are actually installed
```

Delete only images whose kernel package is gone:

```sh
sudo rm /boot/vmlinuz-linux-zen /boot/initramfs-linux-zen.img /boot/initramfs-linux-zen-fallback.img
sudo mkinitcpio -P
sudo pacman -S linux              # re-run the kernel install that failed
```

That is usually enough. **Only if it is not**, disable fallback generation — and understand the trade-off first: the fallback image is your recovery entry when a default initramfs is built wrong. Install `linux-lts` as a replacement escape hatch *before* removing it.

```sh
sudo pacman -S linux-lts          # keep a second bootable kernel
sudoedit /etc/mkinitcpio.d/linux.preset
```

```sh
PRESETS=('default')
default_image="/boot/initramfs-linux.img"
#fallback_image="/boot/initramfs-linux-fallback.img"
#fallback_options="-S autodetect"
```

This file is a pacman backup file: after a `linux` upgrade check for `/etc/mkinitcpio.d/linux.preset.pacnew` and re-apply.

```sh
sudo rm -f /boot/initramfs-linux-fallback.img
sudo mkinitcpio -P
```

On Omarchy/Limine the ESP is filled by UKIs written by limine-entry-tool, not by these presets — prune old kernels and rebuild with `sudo limine-mkinitcpio` instead.

Dropping `nvidia nvidia_modeset nvidia_uvm nvidia_drm` from `MODULES=()` saves space but disables early KMS (expect a flicker/console-mode change at boot).

The real fix is a 1–2 GB ESP, which means repartitioning from a live USB (back up first), then reinstalling the bootloader and rebuilding images.

**Verify.** `df -h /boot` shows healthy free space, `sudo pacman -S linux` completes cleanly, and the machine reboots into the new kernel.

Sources: <https://forum.endeavouros.com/t/efi-no-more-free-storage-space/55411> · <https://forum.endeavouros.com/t/efi-partition-almost-full/68594> · <https://man.archlinux.org/man/mkinitcpio.8>

---

## Never run `pacman -Sy <pkg>`: partial upgrades break the kernel/module pairing

`partial-upgrade-pacman-sy-breaks-boot` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pacman`

**Symptom.** After installing one package with `pacman -Sy something` (or after an interrupted/aborted `-Syu`), the next boot fails — kernel panic, emergency shell, missing modules such as:

```
module not found: 'crc32c_intel'
ERROR: Failed to mount 'UUID=...' on real root
```

or everything works until reboot, then does not.

**Cause.** `pacman -Sy pkg` refreshes the package database and installs `pkg` against the *new* repo state while leaving everything else at the old version. Arch is not designed for this. Concretely, if `linux` is upgraded but `linux-firmware`/DKMS modules are not (or vice versa), `/usr/lib/modules/<newver>` and the installed out-of-tree modules disagree, and the initramfs generated at that moment can be missing what it needs.

> **Audit corrected this record.** The central lesson is correct and important — `pacman -Sy pkg` is the canonical partial-upgrade footgun, `pacman -Syu` is the only supported update, and the WRONG-marked example is exactly the right way to teach it. `omarchy-update` is a real command (verified in basecamp/omarchy bin/). The dkms line is the weak point: `dkms autoinstall -k $(pacman -Q linux | awk '{print $2}' | sed 's/\.arch/-arch/')` only produces a valid module directory name for the mainline `linux` package's arch1 versioning; for linux-lts (6.18.47-1 -> 6.18.47-1-lts), linux-zen or a -rc kernel it emits a directory that does not exist and dkms fails. It also silently targets the wrong kernel if more than one is installed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** PARTIAL UPGRADE. Completing a partial upgrade from a chroot pulls in a large transaction — make sure /boot has free space first, and never interrupt it. Do not use `pacman -Rdd` or `--overwrite` to force past conflicts unless an official Arch news item tells you to.

**Fix.**

There is only one supported update command:

```sh
sudo pacman -Syu
```

To install a package, never add `-y` to `-S`:

```sh
sudo pacman -Syu package-name       # correct: full upgrade + install
sudo pacman -S package-name         # correct if you are already up to date
# sudo pacman -Sy package-name      # WRONG -- partial upgrade
```

If you are already in the broken state, boot a live USB, chroot in, and complete the upgrade:

```sh
sudo arch-chroot /mnt
pacman -Syu
mkinitcpio -P
grub-mkconfig -o /boot/grub/grub.cfg   # or limine-mkinitcpio
exit
```

If DKMS modules (nvidia, virtualbox, zfs) are involved, rebuild against every installed kernel — let dkms discover them rather than reconstructing version strings by hand:

```sh
ls /usr/lib/modules            # the real module directories
sudo dkms autoinstall          # builds for all installed kernels
sudo dkms status               # every entry must say 'installed'
```

To target one kernel, copy the directory name straight from `ls /usr/lib/modules`:

```sh
sudo dkms autoinstall -k 6.18.4-arch1-1
```

On Omarchy always update through the distro wrapper so its migrations run too:

```sh
omarchy-update
```

**Verify.** `pacman -Qu` prints nothing (system fully up to date), `sudo mkinitcpio -P` completes without errors, and the machine reboots into the new kernel.

Sources: <https://forum.endeavouros.com/t/kernel-panic-vfs-unable-to-mount-root-fs-on-unknown-block-0-0/72531> · <https://forum.endeavouros.com/t/eos-fails-to-boot-after-update/74864> · <https://archlinux.org/news/>

---

## Boot the fallback initramfs and rebuild after a bad mkinitcpio run

`broken-initramfs-after-update-boot-fallback` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `grub`, `limine`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** Right after a kernel or system update the normal boot entry drops to an emergency shell or hangs. On plain Arch with a preset that still builds a fallback image, selecting the *fallback* entry in the boot menu boots fine. On Omarchy 4 the Limine menu has no fallback entry, only the normal Omarchy entry and the `Snapshots` submenu, so the first sign is the normal entry failing with nothing else to pick except a snapshot. Users report this most often on encrypted Btrfs roots after a kernel bump.

**Cause.** The default initramfs is built with the `autodetect` hook, which strips out every module the running system was not using at build time. If mkinitcpio ran in a degraded environment (chroot without the real hardware, a full /boot, an interrupted upgrade), the resulting default image is missing the modules needed for your root device. A fallback image is built with `-S autodetect`, so it still contains everything.

Whether a fallback exists depends on the distro. On plain Arch it is built only if the kernel's preset lists it, and mkinitcpio 40 (2025-11-04) removed `fallback` from the default preset template, so an `/etc/mkinitcpio.d/linux.preset` from an older install still has `PRESETS=('default' 'fallback')` while a newer one has `PRESETS=('default')` alone.

On Omarchy 4 the initramfs is not built from presets at all. `limine-mkinitcpio-hook` replaces mkinitcpio's pacman hook, `/etc/mkinitcpio.d` stays empty, and `/usr/share/libalpm/scripts/limine-mkinitcpio-install` builds one UKI per kernel at `/boot/EFI/Linux/omarchy_linux.efi`. It builds a fallback UKI only when `MKINITCPIO_FALLBACK` is `yes` or the kernel name, and Omarchy sets that nowhere: not in `/etc/limine-entry-tool.conf`, not in `/etc/limine-entry-tool.d/omarchy-defaults.conf` or `omarchy-uki.conf`, not in `/etc/default/limine`. With it unset the hook deletes any fallback UKI it finds. A stock Omarchy 4 has no fallback initramfs to boot.

> **Audit corrected this record.** Checked on this machine (omarchy-settings 4.0.2-1, limine-mkinitcpio-hook 1.37.1-1, mkinitcpio 41.1-1) whether a fallback initramfs or fallback boot entry exists at all. It does not. /usr/share/libalpm/scripts/limine-mkinitcpio-install builds the fallback UKI only when MKINITCPIO_FALLBACK is yes or the kernel name, and otherwise calls remove_uki_if_present on the fallback path. MKINITCPIO_FALLBACK is commented out in /etc/limine-entry-tool.conf, absent from all three /etc/limine-entry-tool.d drop-ins (omarchy-defaults.conf, omarchy-uki.conf, resume.conf), absent from /etc/default/limine, and absent from the same two drop-ins in the basecamp/omarchy quattro tree. The record's symptom (the fallback entry boots fine) therefore cannot happen on a stock Omarchy 4, and its verify step names /boot/initramfs-linux.img and /boot/initramfs-linux-fallback.img, neither of which Omarchy 4 produces, since ENABLE_UKI=yes and CUSTOM_UKI_NAME=omarchy give /boot/EFI/Linux/omarchy_linux.efi. /etc/mkinitcpio.d is empty here because limine-mkinitcpio-hook ships /etc/pacman.d/hooks/90-mkinitcpio-install.hook, which shadows mkinitcpio's own hook of that name and never runs generate_presets, so the record's sudo mkinitcpio -P dies with 'No presets found in /etc/mkinitcpio.d' (mkinitcpio line 986) and the -g /boot/initramfs-linux.img form writes a file no Limine entry references. The limine-mkinitcpio line the record already has is the right Omarchy command and was confirmed against /usr/bin/limine-mkinitcpio and /usr/bin/limine-update. On plain Arch the mkinitcpio CHANGELOG (v40, 2025-11-04) says the default kernel preset no longer includes the fallback image, confirmed by PRESETS=('default') in /usr/share/mkinitcpio/hook.preset on 41.1, so the fallback entry now exists only on installs whose preset predates that or was edited. The cited EndeavourOS thread (March 2023, GRUB, encrypt hook) does support the plain-Arch symptom and the fallback-then-rebuild fix. The cited omarchy issue 8319 does not support anything in the record: it is a start-hyprland 'bad json' failure traced by the triage comment to a stale /usr/local/bin/start-hyprland, the reporter's initramfs hypothesis was ruled out there, and nobody in it booted a fallback. Not exercised: booting a Limine snapshot entry, running limine-mkinitcpio with MKINITCPIO_FALLBACK=yes, and the arch-chroot path. The fallback UKI name and the linux-fallback entry name in the corrected fix are read from set_kernel_context and process_uki_kernel in the hook script, not observed on disk.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** On plain Arch do not delete the fallback image to save space until the default image is confirmed working. The fallback is often the only thing standing between you and a live-USB rescue. On Omarchy 4 there is no fallback image to keep, and `mkinitcpio -P` or `mkinitcpio -g` there can report success while the broken UKI at `/boot/EFI/Linux/omarchy_linux.efi` is untouched. `MKINITCPIO_FALLBACK=yes` costs ESP space, and the template's own note says especially so when keeping multiple snapshots.

**Fix.**

**Omarchy 4 (Limine + UKI)**

There is no fallback entry to pick. Get to a working root first, either way:

- In the Limine menu open `Snapshots` and boot the newest snapshot taken before the update. `omarchy update` takes a snapper snapshot before upgrading and `limine-snapper-sync` lists them in the menu.
- Or boot the Omarchy ISO, unlock and mount the root subvolume at `/mnt`, mount the ESP at `/mnt/boot`, and `arch-chroot /mnt`.

Then rebuild the UKI and its Limine entry:

```sh
sudo limine-mkinitcpio
```

Watch the output for `==> ERROR`, `==> WARNING: errors were encountered during the build`, or `mkinitcpio failed for kernel ..., skipping` from the hook, which means the old UKI was left in place. `sudo limine-update` does the same and also redeploys the Limine binary.

Do not reach for `mkinitcpio -P` or `mkinitcpio -g /boot/initramfs-linux.img` here. `/etc/mkinitcpio.d` is empty on Omarchy 4, so `-P` exits with `No presets found in /etc/mkinitcpio.d`, and `-g` writes a file no Limine entry references. The `/usr/local/bin/mkinitcpio` wrapper that `limine-mkinitcpio-hook` installs prints `This does not update Limine boot entries` for exactly this reason.

To have a fallback next time, opt in. `/etc/default/limine` is the user-owned file that overrides every drop-in:

```sh
echo 'MKINITCPIO_FALLBACK=yes' | sudo tee -a /etc/default/limine
sudo limine-mkinitcpio
```

That builds `/boot/EFI/Linux/omarchy_linux-fallback.efi` with `-S autodetect` and adds a `linux-fallback` entry, which `BOOT_ORDER="*, *fallback, Snapshots"` in `omarchy-defaults.conf` already sorts after the normal entry.

Check the result with a privileged listing, since `/boot` is mounted `dmask=0077`:

```sh
sudo ls -l --time-style=long-iso /boot/EFI/Linux/
sudo limine-list
```

**Plain Arch (preset-driven, any bootloader)**

Boot the fallback entry, then rebuild every preset:

```sh
sudo mkinitcpio -P
```

Watch the output for `==> ERROR` or `==> WARNING: errors were encountered during the build`. If only one kernel is broken, target it directly:

```sh
sudo mkinitcpio -p linux
sudo mkinitcpio -p linux-lts
# or fully manual:
sudo mkinitcpio -k 6.12.10-arch1-1 -g /boot/initramfs-linux.img
```

If the menu has no fallback entry because the preset was generated by mkinitcpio 40 or later, uncomment `PRESETS=('default' 'fallback')` and the `fallback_image` and `fallback_options` lines in `/etc/mkinitcpio.d/linux.preset`, then run `sudo mkinitcpio -P` again. `ls -l /boot/initramfs-linux.img /boot/initramfs-linux-fallback.img` should show both with a current timestamp.

If the rebuild itself errors, fix the underlying cause first (usually a full /boot, see that record, or a hook referencing a module that no longer exists).

**Verify.** `ls -l /boot/initramfs-linux.img /boot/initramfs-linux-fallback.img` shows both files with a current timestamp and a plausible size (tens to hundreds of MB), and the *default* entry boots.

Sources: <https://forum.endeavouros.com/t/solved-boots-into-emergency-shell-after-update-encrypted-root-is-not-mounted/38101> · <https://man.archlinux.org/man/mkinitcpio.8> · <https://github.com/basecamp/omarchy/issues/8319> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/CHANGELOG> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-uki.conf>

---

## Btrfs "No space left on device" during mkinitcpio or pacman while df shows free space

`btrfs-metadata-exhaustion-enospc-truncated-initramfs` · severity: **critical** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `snapper`

**Symptom.** An update dies part-way with something like:

```
==> Creating zstd-compressed initcpio image: '/boot/initramfs-linux.img'
bsdtar: Write error
==> ERROR: Image generation FAILED: 'zstd' reported an error
```

or

```
error: could not commit transaction
error: failed to commit transaction (No space left on device)
```

but `df -h /` says there are tens of gigabytes free. Sometimes the filesystem flips read-only mid-write and the journal shows `BTRFS: error (device nvme0n1p2) ... No space left on device` / `BTRFS info: forced readonly`. On Omarchy, `omarchy update` may abort earlier with a free-space warning.

**Cause.** Btrfs allocates disk in two stages: large chunks are reserved for DATA or METADATA, then blocks are handed out inside them. Once every byte of the device is *allocated* to chunks, a write that needs a new chunk of the other type fails with ENOSPC even though the chunks themselves are half empty. `df` only reports block-level free space and cannot see this. On snapshot-heavy installs (Omarchy takes a snapper snapshot on every update) old snapshots pin data into chunks that would otherwise be reclaimable, and the pacman cache does the same.

> **Audit corrected this record.** The mechanism, the `btrfs filesystem usage -T` / 'Device unallocated: 0.00B' tell, the reclaim-then-balance order, the staged -dusage=10/50 balance, and the snapper facts are all correct — Omarchy really does ship NUMBER_LIMIT="5" / TIMELINE_CREATE="no" in default/snapper/root, and install/config/snapper.sh at /usr/share/omarchy is the right restore command. Two defects in the commands. (1) `sudo pacman -Scc --noconfirm` silently does nothing: -Scc's prompt defaults to N and --noconfirm takes the default, so the user believes they emptied the cache when they did not — on a filesystem that is out of allocatable space, that is the difference between fixing it and not. (2) `btrfs device add -f` is presented as a casual trick with no warning that -f overwrites whatever filesystem is on that partition and that the array then depends on the stick until `device remove` completes.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do NOT reboot after an ENOSPC failure until the initramfs/UKI has been regenerated successfully — a truncated image will not boot. Never balance metadata (`-musage=`): the upstream ENOSPC guidance is data chunks only, and metadata balances make the problem recur sooner. Do not use a ramdisk or zram device as the temporary `btrfs device add` target — a reboot before you remove it destroys the filesystem. Deleting snapshots is irreversible; check what you are deleting with `snapper list` first. A long balance is heavy I/O and should not be interrupted by a hard power-off.

**Fix.**

Same diagnosis, same order of operations (reclaim first, balance second, rebuild the boot image last). Replace the two broken steps.

Cache reclaim — `pacman -Scc --noconfirm` is a no-op, use:

```bash
sudo paccache -rk1        # keep 1 version of installed packages (pacman-contrib)
sudo paccache -ruk0       # drop every cached package that is no longer installed
# to truly empty the cache non-interactively:
yes | sudo pacman -Scc
```

Temporary device — this ERASES the partition you hand it, and the filesystem depends on it until the remove finishes:

```bash
truncate -s 0 ~/Downloads/some-big.iso   # always try this first; frees blocks with no new metadata
lsblk -f /dev/sdb                         # confirm the target holds nothing you want
sudo btrfs device add -f /dev/sdb1 /      # -f OVERWRITES any filesystem on /dev/sdb1
sudo btrfs balance start -dusage=20 /
sudo btrfs device remove /dev/sdb1 /      # must finish before you unplug it or reboot
```

(A loop file on the same filesystem cannot help - it needs the space it is trying to free.) If the filesystem went read-only, remount or reboot before any of this, then finish with `sudo limine-mkinitcpio` (Omarchy 4 / UKI) or `sudo mkinitcpio -P` on plain Arch, and restore the snapper policy with `sudo bash -euo pipefail /usr/share/omarchy/install/config/snapper.sh` if it has drifted.

**Verify.** `sudo btrfs filesystem usage -T /` shows several GiB of `Device unallocated`; `sudo limine-mkinitcpio` (or `mkinitcpio -P`) completes with `Image generation successful` and no write errors.

Sources: <https://wiki.archlinux.org/title/Btrfs> · <https://wiki.tnonline.net/w/Btrfs/ENOSPC> · <https://bbs.archlinux.org/viewtopic.php?id=292045> · <https://github.com/basecamp/omarchy/blob/quattro/default/snapper/root> · <https://github.com/basecamp/omarchy/blob/quattro/install/config/snapper.sh>

---

## Recover from `grub rescue>` with "error: unknown filesystem"

`grub-unknown-filesystem-rescue-prompt` · severity: **critical** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `manjaro`

**Symptom.** The machine no longer reaches the GRUB menu. Instead:

```
error: unknown filesystem.
Entering rescue mode...
grub rescue> 
```

Seen after a `grub` package update, after a hard reset/power loss on a Btrfs root, after resizing partitions, or after a Windows 11 feature update.

**Cause.** GRUB's installed `core.img` on the ESP/MBR gap no longer matches what it needs to read `/boot`. Either the `grub` package was upgraded without re-running `grub-install` (Arch has published a news item about exactly this class of breakage), or the filesystem gained a feature the old `core.img` cannot parse (very common with Btrfs after `btrfs-progs` enables new on-disk features), or a partition move invalidated the embedded block list.

> **Audit corrected this record.** The grub-install + grub-mkconfig pairing and the Arch news citation are correct. But the `grub rescue>` recovery block is wrong for the two layouts the record itself names as causes. On a Btrfs root with an @ subvolume — explicitly called out in the symptom and Applies-to — the prefix is inside the subvolume, so `set prefix=(hd0,gpt2)/boot/grub` fails and the user is stuck at the rescue prompt believing the advice failed. Same for a separate /boot partition, where the prefix is `/grub`, not `/boot/grub`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `grub-install --target=i386-pc /dev/sda` writes to the MBR/boot gap of that disk. Pointing it at the wrong device (or at a partition instead of a disk) can destroy another OS's bootloader.

**Fix.**

Boot a live USB, chroot in (see the chroot record), and re-run **both** halves — neither alone is enough:

```sh
sudo arch-chroot /mnt
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB   # UEFI
# BIOS/MBR instead:
# grub-install --target=i386-pc /dev/sda
grub-mkconfig -o /boot/grub/grub.cfg
```

Make that pair a habit whenever `grub` appears in a `pacman -Syu`.

**One-shot rescue without a live USB.** At `grub rescue>`, find the partition and then set a prefix that matches your actual layout:

```
ls
ls (hd0,gpt2)/            # look at what is really there before setting prefix
set root=(hd0,gpt2)
```

Then pick the matching prefix:

```
# /boot on the root partition, plain ext4:
set prefix=(hd0,gpt2)/boot/grub

# Btrfs root with an @ subvolume (Omarchy/EndeavourOS/CachyOS default):
set prefix=(hd0,gpt2)/@/boot/grub

# separate /boot partition (that partition IS /boot):
set prefix=(hd0,gpt2)/grub
```

```
insmod normal
normal
```

If `normal` still errors, the prefix is wrong — `ls (hd0,gptN)/` each candidate until you see a `grub` directory. That gets you one boot; immediately run the `grub-install` + `grub-mkconfig` pair afterwards.

**Verify.** Reboot without the live USB and land on the GRUB menu. `sudo grub-install --version` and the on-disk `/boot/grub/i386-pc/` or `/boot/EFI/GRUB/` files share the same version.

Sources: <https://archlinux.org/news/grub-bootloader-upgrade-and-configuration-incompatibilities/> · <https://forum.endeavouros.com/t/unknown-filesystem-grub-rescue-at-boot-after-system-lockup/78128> · <https://forum.endeavouros.com/t/my-grub-breaks-after-the-last-update-of-my-system/56563> · <https://forum.endeavouros.com/t/cannot-start-endeavour-since-bios-update/70209>

---

## Fix "Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)"

`kernel-panic-vfs-unable-to-mount-root-fs` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** The screen fills with a kernel trace immediately after the bootloader hands over:

```
Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
CPU: 0 PID: 1 Comm: swapper/0 Not tainted 6.12.x-arch1-1
```

Sometimes with a QR code (systemd's kernel panic screen). Happens after a botched update, after repartitioning for dual boot, or after a motherboard/BIOS change.

**Cause.** `unknown-block(0,0)` means the kernel got **no initramfs at all**, or an initramfs that ended without ever mounting a root filesystem. Either the bootloader entry's `initrd` line points at a file that does not exist (deleted, or wiped by a full /boot), or the initramfs was never regenerated after the kernel changed, or the bootloader config still references an old kernel/root layout after repartitioning.

> **Audit corrected this record.** Cause analysis and the chroot sequence are correct, and the EndeavourOS anecdote (config regen, not grub-install, was the cure) is a genuinely useful detail. Two problems: `sudo bootctl update` is presented as the systemd-boot equivalent of regenerating boot config, which it is not — it only replaces the systemd-boot EFI binary on the ESP and leaves stale entries untouched. And `pacman -S linux` in a chroot whose database may be mid-upgrade is how people compound a partial upgrade; `pacman -Syu` first is the safe order.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** You are operating on the bootloader from a chroot. Mount the correct ESP at /mnt/boot before running grub-mkconfig or bootctl, or you will write boot files into a directory on the root filesystem where the firmware will never find them.

**Fix.**

Boot a live USB, chroot in (see the chroot record — get the Btrfs subvolume and ESP mount point right first), then:

```sh
lsblk -f
sudo cryptsetup open /dev/nvme0n1p2 cryptroot   # only if LUKS
sudo mount -o subvol=@ /dev/mapper/cryptroot /mnt
sudo mount /dev/nvme0n1p1 /mnt/boot             # confirm against /mnt/etc/fstab
sudo arch-chroot /mnt

# inside the chroot
cat /etc/fstab                 # verify /boot vs /boot/efi vs /efi before anything else
pacman -Syu                    # finish any half-done upgrade FIRST
pacman -S linux                # reinstalls vmlinuz + triggers mkinitcpio
mkinitcpio -P
ls -l /boot                    # vmlinuz-linux AND initramfs-linux.img must both exist
```

Then regenerate the loader's own config:

```sh
grub-mkconfig -o /boot/grub/grub.cfg    # GRUB
limine-mkinitcpio                        # Omarchy / Limine
```

For **systemd-boot**, `bootctl update` only updates the EFI binary — it does not write entries. Check and fix the entry itself:

```sh
bootctl list
cat /boot/loader/entries/*.conf    # the `initrd` line must name a file that exists
```

Then:

```sh
exit
sudo umount -R /mnt
reboot
```

**Verify.** `ls -l /boot/vmlinuz-linux /boot/initramfs-linux.img` both exist with current timestamps, and the boot entry's `initrd` path matches a real file. The machine boots to a login prompt.

Sources: <https://forum.endeavouros.com/t/kernel-panic-vfs-unable-to-mount-root-fs-on-unknown-block-0-0/72531> · <https://forum.endeavouros.com/t/kernel-panic-not-syncing-vfs-unable-to-mount-root-fs-on-unknown-block-8-17/34774> · <https://man.archlinux.org/man/arch-chroot.8>

---

## LUKS passphrase rejected at the boot prompt (keymap, or intermittent)

`luks-passphrase-rejected-at-boot` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `luks`, `manjaro`, `omarchy`

**Symptom.** At the encryption prompt the correct passphrase is refused:

```
A password is required to access the cryptroot volume:
Enter passphrase for /dev/nvme0n1p2:
No key available with this passphrase.
```

Two distinct flavours are reported: (a) it *never* works from the boot prompt but the same passphrase works from a live USB — almost always a keyboard-layout problem; (b) it works after several tries with nothing changed, reported on a ThinkPad T14s Gen 1 running Omarchy 4.0.0 (basecamp/omarchy#8618, still open upstream).

**Cause.** (a) The initramfs uses the US layout unless a keymap is baked in, so any non-alphanumeric character on a non-US keyboard produces a different byte than the one you enrolled. Num Lock state changes digits typed on the numpad the same way. (b) The intermittent case on Omarchy has not been root-caused; the reporter ruled out header corruption, Plymouth and USB/keyboard timing (the machine uses an i8042 PS/2 keyboard with clean logs).

> **Audit corrected this record.** Issue 8618 is real and the keymap diagnosis for flavour (a) is correct; `cryptsetup open --test-passphrase <dev>` and `luksAddKey`/`luksHeaderBackup` are all valid invocations. But the systemd-initramfs advice is wrong in a way that can brick a boot: it says a UKI 'as Omarchy builds' needs `base systemd ... sd-vconsole ... sd-encrypt`. A UKI is a packaging format, not an initramfs flavour. Omarchy's actual shipped array (omarchy-settings' /etc/mkinitcpio.conf.d/omarchy_hooks.conf, quoted verbatim in issue 8471) is busybox-based: `base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs`. Pasting the systemd array swaps udev/encrypt for systemd/sd-encrypt and drops plymouth, and the cmdline still says `cryptdevice=` rather than `rd.luks.*` — that is an unbootable machine. Also missing: a LUKS header backup is a decryption-capable secret and must not sit in ~ on the encrypted disk it unlocks.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** DATA LOSS. Removing or overwriting the wrong LUKS keyslot, or writing a stale header backup over a live header, destroys access to the encrypted volume permanently — there is no recovery. Always add a new key before removing an old one, and store the header backup off the encrypted disk.

**Fix.**

**First, prove the passphrase is fine** from a live USB:

```sh
sudo cryptsetup luksDump /dev/nvme0n1p2
sudo cryptsetup open --test-passphrase /dev/nvme0n1p2
```

If that succeeds, the passphrase is right and the problem is early boot.

**Check which initramfs flavour you actually have before editing anything** — do not assume, and note that building a UKI does not make it systemd-based:

```sh
grep -h '^HOOKS' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
```

Set the console layout:

```sh
# /etc/vconsole.conf
KEYMAP=uk
```

Then add the keymap hooks **to the array you already have**, keeping its flavour:

- If your array contains `udev` and `encrypt` (this is Omarchy's default — it ships `base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs`), ensure `keyboard` and `keymap` are present. Do not switch to systemd hooks.
- Only if your array already contains `systemd` and `sd-encrypt`, use `sd-vconsole` in place of `keymap`.

Mixing the two families also requires changing the kernel cmdline (`cryptdevice=` vs `rd.luks.name=`), so never swap flavours to fix a keymap.

Rebuild:

```sh
sudo mkinitcpio -P        # Arch/EndeavourOS/CachyOS
sudo limine-mkinitcpio    # Omarchy
```

**Safety net — add a purely-ASCII second passphrase** so a layout problem can never lock you out:

```sh
sudo cryptsetup luksAddKey /dev/nvme0n1p2
```

**Back up the LUKS header first.** Treat the backup as equivalent to the disk's contents: anyone holding it plus any passphrase that was valid *at backup time* can decrypt the disk, even after you later change that passphrase. Write it to removable media you keep offline, never to the encrypted disk itself:

```sh
sudo cryptsetup luksHeaderBackup /dev/nvme0n1p2 \
  --header-backup-file /run/media/$USER/USBSTICK/luks-header-nvme0n1p2.img
sudo chmod 600 /run/media/$USER/USBSTICK/luks-header-nvme0n1p2.img
```

For the intermittent Omarchy case (#8618), keep retrying and attach `journalctl -b -1` to the issue.

**Verify.** Reboot and type the passphrase using the same physical keys as in the OS — it is accepted first time. `sudo cryptsetup luksDump /dev/nvme0n1p2` shows the expected number of enabled keyslots.

Sources: <https://github.com/basecamp/omarchy/issues/8618> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://forum.endeavouros.com/t/solved-boots-into-emergency-shell-after-update-encrypted-root-is-not-mounted/38101>

---

## Black screen or SDDM login loop after an update: NVIDIA DKMS failed, so nvidia is missing from the initramfs/UKI

`nvidia-modules-missing-from-initramfs-black-screen` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `limine`, `nvidia`, `omarchy`

**Symptom.** After `omarchy update` (or `pacman -Syu`) and a reboot the machine goes to a black screen after the boot menu, or SDDM takes the password and bounces straight back to the login screen with no error. Scrolling back through the update transcript shows:

```
Error! Bad return status for module build on kernel: 7.0.3-arch1-2 (x86_64)
Consult /var/lib/dkms/nvidia-open/595.71.05/build/make.log for more information.
...
==> ERROR: module not found: 'nvidia'
==> ERROR: module not found: 'nvidia_modeset'
==> ERROR: module not found: 'nvidia_uvm'
==> ERROR: module not found: 'nvidia_drm'
==> WARNING: errors were encountered during the build. The image may not be complete.
==> Creating unified kernel image: '/tmp/limine-mkinitcpio.XXXXXX/linux.efi'
==> Unified kernel image generation successful
ERROR: mkinitcpio failed for kernel 7.0.3-arch1-2, skipping.
```

(Older versions of limine-mkinitcpio-hook printed the staging path as `/tmp/staging_uki.efi`. The `skipping` line is the one that matters.)

pacman still exits 0 and `omarchy update` reports success. Sometimes `nvidia-smi` on a TTY prints `NVRM: API mismatch: this kernel module has version 595.58.03 but this NVIDIA driver component has version 595.71.05`.

**Cause.** nvidia-open-dkms / nvidia-dkms failed to compile against the newly installed kernel. On Omarchy 4 the usual reason is that the driver does not support that kernel yet (issue 5706 was a GCC internal compiler error in NVIDIA's source on 7.0.x), because `install/hardware/nvidia.sh` already installs the matching `<kernel>-headers` package. Missing headers is still the first thing to check for a second kernel you added yourself (`linux-lts` without `linux-lts-headers`) and on plain Arch, and a kernel and module built with different GCC major versions is the other classic cause.

Omarchy's `install/hardware/nvidia.sh` writes `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` to `/etc/mkinitcpio.conf.d/nvidia.conf` for early KMS, and the package-owned `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` drops the `kms` hook when nvidia_drm is early-loaded and NVIDIA owns every display controller. When those four modules do not exist mkinitcpio prints `module not found` for each, still writes the image, then exits non-zero. `limine-mkinitcpio-install` treats that exit code as a failure, prints `mkinitcpio failed for kernel ..., skipping.` and never installs the staged UKI. Nothing gets rebuilt and pacman exits 0, so `/boot/EFI/Linux/omarchy_linux.efi` still holds the OLD kernel and the OLD nvidia module in its initramfs, while `nvidia-utils` on disk is new. The kernel/userspace version pair no longer matches, Hyprland aborts in `CHyprOpenGLImpl::initEGL`, and SDDM loops. On plain Arch with a normal initramfs the outcome is different: mkinitcpio -P installs the incomplete image anyway, the new kernel boots with no nvidia module, and you get a black screen or a bare framebuffer instead.

One Omarchy detail decides whether you can recover without rebooting. Omarchy 4 installs `kernel-modules-hook`, whose pacman hooks copy the running kernel's whole module tree (including `build/` and `updates/dkms/`) aside before the transaction and restore it afterwards. DKMS therefore builds the new driver for the running kernel too, and if that build succeeded you can unload the stale module and load the new one in place. Plain Arch without that package deletes `/usr/lib/modules/<running kernel>` during the kernel upgrade, so nothing can be modprobed until you reboot.

> **Audit corrected this record.** Confirmed on this machine (omarchy-settings 4.0.2-1, limine-mkinitcpio-hook 1.37.1-1, mkinitcpio 41.1-1, nvidia-open-dkms 610.57.04-1): /etc/mkinitcpio.conf.d/nvidia.conf is exactly MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm), /etc/modprobe.d/nvidia.conf is options nvidia_drm modeset=1, and both match install/hardware/nvidia.sh fetched from quattro. /etc/mkinitcpio.conf.d/omarchy_hooks.conf (owned by omarchy-settings) drops the kms hook only when nvidia_drm is in MODULES and every PCI class 0x03 device has vendor 0x10de, which is the case here (single RTX 3090). /usr/bin/limine-mkinitcpio exists and runs echo rebuild | /usr/share/libalpm/scripts/limine-mkinitcpio-install, whose error text is verbatim 'mkinitcpio failed for kernel X, skipping.' and which returns before limine-entry-tool --add-uki, so the old UKI stays. /usr/bin/mkinitcpio exits !!_builderrors (line 1238) and 'module not found' is an error() in /usr/lib/initcpio/functions:740 that counts, so the exit code claim holds. /etc/mkinitcpio.d is empty on Omarchy 4 because /etc/pacman.d/hooks/90-mkinitcpio-install.hook shadows the stock hook that would write linux.preset, so mkinitcpio -P dies with 'No presets found' (mkinitcpio:986): the wrapper-only claim holds and is stronger than stated. The ALPM guard (/usr/share/omarchy/bin/omarchy-update-pacman-guard) trips only when -S and -u are both present, so pacman -S --needed linux-headers passes. Issue 5706 (open, labels bug and nvidia) supports every element of the cause: DKMS built for the running kernel but not the new ones, UKI rebuild skipped, pacman exit 0, stale UKI with old module, initEGL abort, SDDM loop. What the record misses is WHY the in-place modprobe recovery works: Omarchy 4 installs kernel-modules-hook (line 66 of /usr/share/omarchy/install/omarchy-base.packages, installed 0.1.7-3 here), whose 10-linux-modules-pre/post alpm hooks rsync the running kernel's module tree, including build/ and updates/dkms/, around the transaction, so DKMS can build the new driver for the running kernel and modprobe can load it. On plain Arch without that package the kernel upgrade deletes /usr/lib/modules/$(uname -r), so the record's modprobe -r then modprobe nvidia_drm fails with 'Module nvidia_drm not found' and leaves no driver loaded at all. The reload also only helps when dkms status shows the new driver installed for $(uname -r), which the record never checks. Fix rewritten to gate the reload on that and to label the Omarchy versus plain Arch branch. Symptom transcript path updated: hook 1.37.1-1 builds to /tmp/limine-mkinitcpio.XXXXXX/<kernel>.efi, not /tmp/staging_uki.efi (that was an older hook, quoted from the May 2026 issue). Cause reordered so the Omarchy-typical trigger (driver does not build against the new kernel) comes first, since nvidia.sh already installs the headers. NOT exercised: no DKMS failure was induced, no reboot, no VM run, and dkms autoinstall -k was not executed. The kernel-modules-hook interaction with the dkms upgrade hook is read from the hook files, not observed.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not reboot while the transcript says `mkinitcpio failed for kernel ..., skipping.` — the boot image on the ESP is stale and may be the last working one. Never fix this with `pacman -Sy nvidia-utils`: that is a partial upgrade and will make the mismatch worse. `modprobe -r nvidia*` kills anything using the GPU, so save work first.

**Fix.**

Get a text console with Ctrl+Alt+F2 and log in.

Find out what actually failed:

```bash
uname -r
ls /usr/lib/modules/
dkms status
pacman -Q linux linux-lts linux-headers nvidia-open-dkms nvidia-utils 2>/dev/null
sudo tail -40 /var/lib/dkms/*/*/build/make.log
```

**If you are stuck in the SDDM login loop** (kernel module and userspace disagree), you can unstick the running session without a reboot, but only when `dkms status` shows the NEW driver version `installed` for the kernel `uname -r` reports:

```bash
dkms status | grep "$(uname -r)"      # must list the new driver version as installed
sudo systemctl stop sddm
sudo modprobe -r nvidia_drm nvidia_uvm nvidia_modeset nvidia
sudo modprobe nvidia_drm
sudo systemctl start sddm
```

Omarchy 4 ships `kernel-modules-hook`, which is what keeps the running kernel's modules on disk through the upgrade so this works. On plain Arch without that package the running kernel's module directory is gone after a kernel upgrade, `modprobe nvidia_drm` will fail with `Module nvidia_drm not found`, and you would be left with no driver at all: skip this block, rebuild, and reboot.

Install the headers that match every installed kernel and rebuild the modules. Omarchy 4 already installs `<kernel>-headers` for the kernel it found at install time, so this step matters for a second kernel you added and for plain Arch:

```bash
sudo pacman -S --needed linux-headers        # add linux-lts-headers / linux-zen-headers as applicable
sudo dkms autoinstall -k 7.0.3-arch1-2       # the kernel version from ls /usr/lib/modules/
dkms status                                   # every kernel should now show "installed"
```

Confirm the modules really exist before you rebuild the boot image:

```bash
ls /usr/lib/modules/7.0.3-arch1-2/updates/dkms/nvidia*.ko*
```

Rebuild the initramfs. On Omarchy 4 (Limine + UKI) you must use the Limine wrapper, not bare mkinitcpio: `/etc/mkinitcpio.d` is empty on Omarchy 4, so `mkinitcpio -P` stops with `No presets found` and the UKI on the ESP is never replaced:

```bash
sudo limine-mkinitcpio      # Omarchy / limine-mkinitcpio-hook
# plain Arch with a normal initramfs instead:
sudo mkinitcpio -P
```

Read that output. There must be no `module not found:` lines and no `mkinitcpio failed for kernel ..., skipping.` Verify modeset is on before rebooting:

```bash
cat /sys/module/nvidia_drm/parameters/modeset   # must print Y
cat /etc/modprobe.d/nvidia.conf                 # options nvidia_drm modeset=1
cat /etc/mkinitcpio.conf.d/nvidia.conf          # MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
```

If the driver genuinely does not support the new kernel yet, install an LTS kernel to boot from and rebuild:

```bash
sudo pacman -S --needed linux-lts linux-lts-headers
sudo dkms autoinstall
sudo limine-mkinitcpio
```

If you are already at a black screen and cannot reach a TTY, pick a pre-update snapshot from the Limine menu (Omarchy ships limine-snapper-sync and lists snapshots under `Snapshots`), or press `e` on the boot entry and add `nomodeset` to the `cmdline:` line to reach a console, then follow the steps above.

**Verify.** `dkms status` shows `installed` for every kernel in /usr/lib/modules; `sudo limine-mkinitcpio` completes with no `module not found` lines; after reboot `cat /sys/module/nvidia_drm/parameters/modeset` prints Y and `modinfo -F version nvidia` matches `pacman -Q nvidia-utils`.

Sources: <https://github.com/basecamp/omarchy/issues/5706> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/nvidia.sh> · <https://github.com/basecamp/omarchy/blob/quattro/etc/mkinitcpio.conf.d/omarchy_hooks.conf> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio> · <https://bbs.archlinux.org/viewtopic.php?id=295952> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md> · <https://github.com/limine-bootloader/limine/blob/trunk/common/menu.c>

---

## Boot hangs on the splash screen and the LUKS passphrase prompt never appears

`plymouth-swallows-luks-passphrase-prompt` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `limine`, `luks`, `manjaro`, `omarchy`, `plymouth`

**Symptom.** The machine reaches the Omarchy/Arch boot splash (or a black screen with a spinner) and stops there forever. No `Enter passphrase for /dev/nvme0n1p2:` prompt, no cursor. Typing the passphrase blind and pressing Enter sometimes works, which is the giveaway. Pressing Esc shows nothing useful. Variants after editing the initramfs config:

```
==> ERROR: Hook 'plymouth-encrypt' cannot be found
==> ERROR: Hook 'plymouth' cannot be found
```

On a docked laptop the prompt may be drawn on an external monitor that is still asleep.

**Cause.** The `encrypt` hook asks for the passphrase in one of two ways. If plymouthd is already running in the initramfs (`plymouth --ping` succeeds) it hands the prompt to `plymouth ask-for-password`, which draws it on the splash and pipes what you type to cryptsetup. Otherwise it prints `A password is required to access the root volume:` as plain text. The hang happens in the first case when plymouthd is running but cannot draw: the initramfs has no early KMS driver for the GPU, or plymouth is on SimpleDRM and the output it chose is dark. The prompt is invisible but input still works, which is why typing the passphrase blind sometimes gets you in. This is what the Arch dm-crypt page means by "use the correct modules or Plymouth will swallow the password prompt".

On Omarchy 4 the hook order is fixed by the package-owned `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` (plymouth right after udev, `encrypt` later, not `sd-encrypt`), so a wrong order only occurs when someone overrides HOOKS in `/etc/mkinitcpio.conf` or another drop-in. Even then the result is an unthemed text prompt rather than a deadlock, because plymouthd is not running yet when `encrypt` asks. The same file drops the `kms` hook on machines where NVIDIA owns every display controller and relies on `/etc/mkinitcpio.conf.d/nvidia.conf` early-loading `nvidia_drm`, so on those machines a missing nvidia module means no display driver at all at the prompt. Omarchy also ships `initramfs_async=0` because kernel 7.1 unpacks the initramfs asynchronously, plymouthd exits when it cannot read `/proc/cmdline`, and encrypted boots fall back to a text prompt.

Two related traps: `plymouth-encrypt` is not a hook on Arch at all (the `plymouth` package ships only `/usr/lib/initcpio/hooks/plymouth`, and the name is a deprecated Manjaro alias for `encrypt`), so guides recommending it make every rebuild fail with `Hook 'plymouth-encrypt' cannot be found`. And plymouth defaults to SimpleDRM on UEFI, which does not light up secondary monitors, so a docked laptop can show the prompt on a dark screen.

> **Audit corrected this record.** Confirmed on this machine (omarchy-settings 4.0.2-1, plymouth 26.134.222-2, limine-mkinitcpio-hook 1.37.1-1): the quoted HOOKS line is byte-identical to /etc/mkinitcpio.conf.d/omarchy_hooks.conf, Omarchy 4 uses the udev-based `encrypt` hook (not sd-encrypt) with cryptdevice= in /etc/default/limine and in the running /proc/cmdline, the vconsole.conf Latin-layout bundling is in the same file, and initramfs_async=0 with the kernel 7.1 race comment is verbatim in /etc/limine-entry-tool.d/omarchy-defaults.conf and present in /proc/cmdline. pacman -Ql plymouth lists only hooks/plymouth, install/plymouth and install/plymouth-shutdown, so plymouth-encrypt is not an Arch hook, and mkinitcpio's wording is verbatim "Hook 'X' cannot be found" (/usr/lib/initcpio/functions:1244). The Arch Plymouth page still says plymouth goes before encrypt or sd-encrypt, still documents SimpleDRM by default on UEFI with the docked-laptop warning, plymouth.use-simpledrm=0, plymouth.enable=0 disablehooks=plymouth and plymouth.debug, and the Dm-crypt/System_configuration troubleshooting section is the origin of the 'swallow the password prompt' wording. The drop-in mechanism holds: /usr/lib/limine/limine-common-functions loads /usr/share/limine-entry-tool.d, /etc/limine-entry-tool.conf, /etc/limine-entry-tool.d/*.conf, then /etc/default/limine, the local /etc/default/limine uses +=, and limine-mkinitcpio re-embeds the cmdline via limine-entry-tool --get-cmdline before --add-uki. The one-off Limine edit holds too: menu.c opens the entry editor on e/E, the entry tool writes a cmdline: line, CONFIG.md says the editor defaults to enabled unless a config hash is enrolled or Secure Boot is active, ENABLE_ENROLL_LIMINE_CONFIG is unset on Omarchy 4 and sbctl is not installed, and systemd-stub only refuses a load-options cmdline under Secure Boot. Two things were wrong. First, the cause's mechanism: /usr/lib/initcpio/hooks/encrypt only calls plymouth ask-for-password when plymouth --ping succeeds, so a plymouth hook ordered after encrypt gives a plain text prompt, not a hang, and splash with no plymouth in the initramfs cannot swallow anything because plymouthd is not running. The hang the symptom describes comes from plymouthd running but unable to draw (no early KMS driver, SimpleDRM on a dark output, or the kernel 7.1 race), which is what the Arch dm-crypt page's 'use the correct modules' means. Cause rewritten, and the Omarchy 4 angle added: omarchy_hooks.conf drops kms on NVIDIA-only machines and relies on nvidia.conf early-loading nvidia_drm. Second, the theme-reset block: plymouth-set-default-theme -R runs /usr/lib/plymouth/plymouth-update-initrd, which is bare mkinitcpio -P, and /etc/mkinitcpio.d is empty on Omarchy 4 so that cannot rebuild the UKI. omarchy-refresh-plymouth already runs plymouth-set-default-theme omarchy followed by limine-mkinitcpio and refuses to run under sudo, so on Omarchy it is the only command needed. NOT exercised: no boot was performed, no Limine edit, no rebuild, and the Manjaro plymouth-encrypt origin was not re-fetched (the Manjaro GitLab raw URL returned nothing), so that sentence rests on the previous audit. GitHub issue search was unavailable to this token, so no Omarchy issue was checked for this record.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Editing HOOKS wrongly is how people make a machine unbootable — dropping `encrypt`/`sd-encrypt` means nothing can unlock the root device, and dropping `filesystems` or `block` means it cannot be found. Change one thing, rebuild, read the output, and keep a fallback entry or a bootable snapshot available before you reboot. `plymouth.enable=0` is safe as a one-off boot parameter but leaves you with a plain text prompt; do not make it permanent if you also removed the plymouth hook, or you lose the themed prompt entirely. Never disable the passphrase prompt to "get past" this.

**Fix.**

**Get in first.** At the boot menu, edit the entry and disable plymouth for one boot. Limine: press `e` on the entry and edit the `cmdline:` line (the editor is on by default. Omarchy does not enrol a config hash or set up Secure Boot, either of which would disable it and make the cmdline embedded in the UKI non-overridable). GRUB: press `e`, edit the `linux` line, `Ctrl+X`:

```
plymouth.enable=0 disablehooks=plymouth
```

Remove `quiet` and `splash` from the same line so you can see the prompt. The text `A password is required to access the root volume:` should now appear.

**Fix the hook order.** `plymouth` must come after `udev` (or `systemd`) and *before* `encrypt`/`sd-encrypt`, otherwise you get an unthemed text prompt. This is Omarchy 4's shipped order, in the package-owned `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, so on Omarchy check that nothing in `/etc/mkinitcpio.conf` or another drop-in overrides it:

```
HOOKS=(base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs)
```

On plain Arch, edit `/etc/mkinitcpio.conf` to the same shape:

```
HOOKS=(base udev plymouth autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)
```

If you copied `plymouth-encrypt` from another distro's guide, replace it with plain `encrypt`. It does not exist on Arch.

**Rebuild and read the output.** On Omarchy the entries are unified kernel images and `/etc/mkinitcpio.d` is empty, so `mkinitcpio -P` stops with `No presets found` and never touches what boots:

```bash
sudo limine-mkinitcpio      # Omarchy 4 / Limine + UKI
# plain Arch:
sudo mkinitcpio -P
```

There must be no `Hook '...' cannot be found`.

**Docked laptop / external monitor.** Make plymouth use the real GPU driver instead of the UEFI framebuffer so all outputs come up:

```
plymouth.use-simpledrm=0
```

**Keyboard layout at the prompt.** If the passphrase is rejected rather than absent, the initramfs is using us layout. Omarchy bundles `/etc/vconsole.conf` into the image automatically for Latin layouts. On plain Arch add it yourself:

```
# /etc/mkinitcpio.conf.d/99-local.conf
FILES+=(/etc/vconsole.conf)
```

**Debug what plymouth is doing** by adding `plymouth.debug` to the command line and reading `/var/log/plymouth-debug.log` after you get in.

**Make a parameter permanent on Omarchy** (do not edit the generated `/boot/limine.conf`). Drop-ins under `/etc/limine-entry-tool.d/` are read before `/etc/default/limine`, and Omarchy's `/etc/default/limine` appends with `+=`, so a drop-in survives:

```bash
sudo tee /etc/limine-entry-tool.d/99-local.conf >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" plymouth.use-simpledrm=0"
EOF
sudo limine-mkinitcpio
```

Note that Omarchy already ships `initramfs_async=0` in `/etc/limine-entry-tool.d/omarchy-defaults.conf` to work around a kernel 7.1 race in which plymouthd exits before it can read `/proc/cmdline`, dropping encrypted boots to an unthemed text prompt. If your booted `cat /proc/cmdline` is missing it, your boot image predates that default and `sudo limine-mkinitcpio` regenerates it.

If the splash is merely ugly rather than broken, reset the theme instead of disabling plymouth. On Omarchy run this as your user, not under sudo (it refuses otherwise). It republishes the packaged theme, runs `plymouth-set-default-theme omarchy` and then `limine-mkinitcpio`:

```bash
omarchy-refresh-plymouth
```

On plain Arch:

```bash
sudo plymouth-set-default-theme -R <theme>
```

Do not use `plymouth-set-default-theme -R` on Omarchy: its rebuild step is bare `mkinitcpio -P`, which has no presets to run there.

**Verify.** After rebuilding, `sudo limine-mkinitcpio` (or `mkinitcpio -P`) reports no missing hooks; on the next boot the themed passphrase prompt appears and accepts input; `cat /proc/cmdline` contains the parameters you added.

Sources: <https://wiki.archlinux.org/title/Plymouth> · <https://wiki.archlinux.org/title/Dm-crypt/System_configuration> · <https://github.com/basecamp/omarchy/blob/quattro/etc/mkinitcpio.conf.d/omarchy_hooks.conf> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://archlinux.org/packages/extra/x86_64/plymouth/files/> · <https://gitlab.manjaro.org/packages/extra/plymouth/-/blob/master/PKGBUILD> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio> · <https://wiki.archlinux.org/title/Kernel_parameters> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md> · <https://github.com/limine-bootloader/limine/blob/trunk/common/menu.c> · <https://github.com/systemd/systemd/blob/main/man/systemd-stub.xml>

---

## /boot (the ESP) was not mounted during the upgrade, so the new kernel went to the root filesystem

`boot-esp-not-mounted-during-kernel-upgrade` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`, `uefi`

**Symptom.** The kernel upgrade ran, but the next boot fails: the boot loader cannot find the kernel, or the system boots and then everything modular breaks (no Wi-Fi, no GPU, `modprobe: FATAL: Module ... not found in directory /lib/modules/7.0.3-arch1-2`), or you land in an emergency shell. Once you get a shell, `uname -r` reports an older version than `pacman -Q linux`, and `sudo ls /boot` shows either an empty directory or kernels that do not match.

On plain Arch the upgrade printed no warning at all: current mkinitcpio no longer prints the old "/boot appears to be a separate partition but is not mounted" message. On Omarchy 4 the Limine hook did complain, and it is easy to scroll past inside `omarchy update`:

```
ERROR: Boot path '/boot' is not a mounted FAT32 boot partition.
error: command failed to execute correctly
```

The transaction still finished, because a failing PostTransaction hook does not abort pacman.

**Cause.** The EFI system partition was not mounted at `/boot` when the transaction ran, usually because the fstab entry is missing/wrong, because the mount silently failed earlier in the session (`vfat` module not loaded, dirty FAT flagged `errors=remount-ro`), or because the ESP is mounted somewhere else and you relied on systemd automount.

Plain Arch: mkinitcpio's pacman hook happily writes `vmlinuz-linux` and `initramfs-linux.img` into the plain `/boot` *directory* on the root filesystem, which the firmware cannot read.

Omarchy 4: `limine-mkinitcpio-hook` replaces that hook with `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`. Its script checks that `ESP_PATH` (`/boot`, from `/etc/default/limine`) is a mounted vfat filesystem before building anything, fails with the error above, and writes nothing, so the UKI at `/boot/EFI/Linux/omarchy_linux.efi` on the unmounted ESP is simply left at the old version.

Either way the modules under `/usr/lib/modules/<newver>` are updated and the old ones removed, so the old kernel that the firmware does load has no matching modules.

> **Audit corrected this record.** Checked on this Omarchy 4 machine and against the mkinitcpio and limine-entry-tool sources. On Omarchy 4 /boot is the vfat ESP from fstab (fmask=0077,dmask=0077, confirmed with findmnt), the kernel package ships only /usr/lib/modules/<ver>/vmlinuz, and limine-mkinitcpio-hook overrides the stock hook with /etc/pacman.d/hooks/90-mkinitcpio-install.hook (same name, higher priority per alpm-hooks(5)), whose script runs initialize_header in /usr/lib/limine/limine-common-functions before touching anything. With the ESP unmounted that fails on check_boot_partition (`Boot path '/boot' is not a mounted FAT32 boot partition.`) or, without ESP_PATH, on find_boot_partition, and exits 1, so pacman prints `error: command failed to execute correctly` and nothing is written into the root-filesystem /boot directory. The record's symptom ("no errors at all") and cause (stray vmlinuz/initramfs on the root filesystem) therefore describe plain Arch, not Omarchy 4, though the consequence is the same: modules replaced, boot image not rebuilt, old kernel boots with no modules. Also wrong for Omarchy 4: `mkinitcpio -P` cannot serve as a fallback because /etc/mkinitcpio.d is empty here and mkinitcpio 41.1 dies with `No presets found` (line 986 of /usr/bin/mkinitcpio), and `ls /boot` needs sudo. What held: findmnt/lsblk diagnosis, the wiki ESP mount options and the vfat modules-load advice, daemon-reload before mount, `pacman -S linux linux-firmware` passing omarchy-update-pacman-guard (it aborts only when -S and -u are both present), the UKI path /boot/EFI/Linux/omarchy_linux.efi (CUSTOM_UKI_NAME=omarchy and the `${prefix}_${kernel}.efi` pattern in limine-mkinitcpio-install, also used by omarchy-refresh-limine), limine-mkinitcpio and limine-update as real commands (limine-update runs limine-install --no-efi-register then limine-mkinitcpio), subvol=@ and the `root` mapper name matching this machine's cmdline, and the old mkinitcpio warning being absent from both the installed 41.1 script and master. bbs 194153 quotes that old warning and the chroot-and-reinstall cure. bbs 285144 is a uname/pacman -Q mismatch thread and only weakly supports the record. Not exercised: an actual unmounted-ESP upgrade, the chroot path, or GRUB and systemd-boot.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Never `rm -rf /boot` while unsure whether the ESP is mounted — with the ESP mounted you delete your only boot loader and kernel. Move it aside instead. On a dual-boot machine the ESP also holds Windows' boot loader, so do not reformat it. If you chroot from a live USB onto btrfs, get `subvol=@` right or you will repair an empty top-level subvolume.

**Fix.**

First confirm the diagnosis:

```bash
findmnt /boot            # no output at all = the ESP is NOT mounted
lsblk -f                 # find the vfat/FAT32 partition
uname -r; pacman -Q linux
sudo ls -l /boot         # sudo: Omarchy mounts the ESP dmask=0077
```

If the system still boots (on the old kernel), repair it in place.

**Plain Arch only:** move the stray files off the root filesystem first, otherwise they stay there forever wasting space and confusing you later. On Omarchy 4 the hook wrote nothing, so the directory is empty and this step can be skipped (it is harmless if you do it anyway):

```bash
sudo mv /boot /boot.stray
sudo mkdir /boot
```

Add or fix the fstab entry, then mount:

```bash
sudo blkid -s UUID -o value /dev/nvme0n1p1     # your ESP
```

Omarchy's installer writes this shape (masks 0077, so only root can read the ESP):

```
# /etc/fstab
UUID=1234-ABCD  /boot  vfat  rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro  0 2
```

The Arch wiki's `fmask=0137,dmask=0027` variant is equally valid on plain Arch.

```bash
sudo systemctl daemon-reload
sudo mount /boot
findmnt /boot            # must now show the vfat device
```

Reinstall every kernel you have and regenerate the boot image. On Omarchy 4 the reinstall itself fires the Limine hook, which rebuilds the UKI, so the explicit command is belt and braces. `pacman -S` without `-u` is not blocked by Omarchy's update guard:

```bash
sudo pacman -S linux linux-firmware          # add linux-lts etc. if installed
sudo limine-mkinitcpio                        # Omarchy 4 / Limine UKI
# plain Arch instead:
sudo mkinitcpio -P
```

Do not use `mkinitcpio -P` on Omarchy 4: it has no presets in `/etc/mkinitcpio.d/` and dies with `No presets found`, and the `/usr/local/bin/mkinitcpio` wrapper that Omarchy's hook package installs only warns and offers `limine-mkinitcpio` anyway.

Then reinstall the boot loader entries:

```bash
sudo limine-update            # Limine (also re-runs limine-mkinitcpio)
sudo bootctl update           # systemd-boot
sudo grub-mkconfig -o /boot/grub/grub.cfg   # GRUB
```

If it no longer boots at all, do the same from the Arch/Omarchy ISO, booted in UEFI mode (the Limine tools refuse to build a UKI unless `/sys/firmware/efi` exists inside the chroot):

```bash
lsblk -f
# LUKS first if encrypted:
cryptsetup open /dev/nvme0n1p2 root
mount -o subvol=@ /dev/mapper/root /mnt      # drop -o subvol=@ if not btrfs
mount --mkdir /dev/nvme0n1p1 /mnt/boot
arch-chroot /mnt
pacman -S linux linux-firmware
limine-mkinitcpio        # Omarchy 4 / Limine
mkinitcpio -P            # plain Arch instead
exit
umount -R /mnt
```

To stop it recurring when the ESP is not at `/boot`, preload the FAT modules so the mount never fails early:

```
# /etc/modules-load.d/vfat.conf
vfat
nls_cp437
nls_ascii
```

Once you are booting off the ESP again, delete `/boot.stray` if you created it.

**Verify.** `findmnt /boot` shows the vfat partition, `ls /boot` lists the vmlinuz/initramfs (or /boot/EFI/Linux/omarchy_linux.efi on Omarchy) with today's date, and after a reboot `uname -r` matches `pacman -Q linux`.

Sources: <https://wiki.archlinux.org/title/EFI_system_partition> · <https://bbs.archlinux.org/viewtopic.php?id=194153> · <https://bbs.archlinux.org/viewtopic.php?id=285144> · <https://wiki.archlinux.org/title/Limine> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/libalpm/scripts/mkinitcpio> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/mkinitcpio> · <https://gitlab.com/Zesko/limine-entry-tool> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-limine> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-uki.conf> · <https://aur.archlinux.org/rpc/v5/info?arg[]=limine-snapper-sync&arg[]=limine-mkinitcpio-hook>

---

## "UNEXPECTED INCONSISTENCY; RUN fsck MANUALLY" drops the boot into a maintenance shell

`fsck-unexpected-inconsistency-maintenance-shell` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `ext4`, `laptop`, `manjaro`, `omarchy`, `xfs`

**Symptom.** After a hard power-off, a crash, or pulling an external drive, the boot stops with:

```
/dev/sda3: UNEXPECTED INCONSISTENCY; RUN fsck MANUALLY.
	(i.e., without -a or -p options)
fsck failed with exit status 4.
[FAILED] Failed to start File System Check on /dev/disk/by-uuid/1a2b3c4d-....
[DEPEND] Dependency failed for /data.
You are in emergency mode. After logging in, type "journalctl -xb" to view
system logs, "systemctl reboot" to reboot, "systemctl default" or "exit"
to boot into default mode.
Give root password for maintenance (or press Control-D to continue):
```

On plain Arch with an ext4 root the same `UNEXPECTED INCONSISTENCY` line can name the root partition and come from the initramfs instead, followed by a `FILESYSTEM CHECK FAILED` banner and a `[rootfs ]#` shell that reboots the machine when you leave it.

On Omarchy 4 the root, `/home`, `/var/log` and `/var/cache/pacman/pkg` are btrfs subvolumes that are never checked, so this message only ever names an extra ext4 or XFS filesystem you added to `/etc/fstab` yourself. If the root account is locked, the maintenance prompt cannot be passed and Ctrl-D brings it straight back.

**Cause.** fsck found damage it will not repair without confirmation (usually a dirty journal plus orphaned inodes on ext4) and exits with status 4, "errors left uncorrected". On Arch the check runs from one of two places: the mkinitcpio `fsck` hook checks the root filesystem before it is mounted, and `systemd-fsck@.service` checks every other `/etc/fstab` entry with a non-zero pass number in the 6th field. `systemd-fsck@` fails on status 4, the mount unit that `Requires` it fails, and unless the entry carries `nofail`, `local-fs.target` activates `emergency.target`.

On Omarchy 4 both paths are effectively off for the system's own filesystems. `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` keeps `fsck` in `HOOKS`, but with `autodetect` the hook packs only `fsck.btrfs`, a shell script from `btrfs-progs` that prints a hint and exits 0 without touching the disk. Every btrfs line the installer writes to `/etc/fstab` (`/`, `/home`, `/var/log`, `/var/cache/pacman/pkg`, all `subvol=/@...`) has pass `0`. The only entry with a pass number is the vfat ESP at `/boot` (pass `2`), which `systemd-fsck@` checks at every boot with `fsck.fat -a`, and `fsck.fat` only exits 0, 1 or 2, so it does not produce status 4. A broken ESP therefore surfaces as a mount failure (see `fstab-bad-entry-emergency-mode`), and an `UNEXPECTED INCONSISTENCY` on an Omarchy machine points at an ext4 or XFS filesystem you added to fstab.

> **Audit corrected this record.** The generic Arch content held: the Fsck, Kernel_parameters and Btrfs wiki pages (raw wikitext) confirm the two check paths, fsck.mode=skip/force, fsck.repair=yes, the rw requirement for the mkinitcpio fsck hook, the fstab pass-number rules and the warning on btrfs check --repair, and the mkinitcpio hooks/fsck, install/fsck and init_functions sources confirm how the hook builds and what the initramfs does on status 4. rescue=usebackuproot (btrfs 5.9+), btrfs check --readonly as the default, findmnt --verify and fsck.fat exit codes 0/1/2 were confirmed from the local btrfs(5), btrfs-check(8), findmnt(8) and fsck.fat(8) man pages, and systemd-fsck@.service(8) confirms that a status-4 failure on a non-nofail fstab entry activates emergency.target. What did not hold is the Omarchy specialisation. On this machine /etc/mkinitcpio.conf.d/omarchy_hooks.conf does keep fsck in HOOKS, but with autodetect the hook packs only fsck.btrfs, which /usr/bin/fsck.btrfs (btrfs-progs 7.1) shows is a script that exits 0 without checking, and every btrfs line in /etc/fstab (/ /home /var/log /var/cache/pacman/pkg, all subvol=/@...) carries pass 0. The only checked entry is the vfat ESP at /boot with pass 2, and systemctl status shows systemd-fsck@ running fsck.fat 4.2 on it at every boot. fsck.fat cannot return 4, so the record's symptom (an ext4 message on nvme0n1p2, which is the LUKS root on Omarchy) cannot occur on an Omarchy install as shipped and only appears for an extra ext4 or XFS disk the user added with a non-zero pass number. The btrfs advice was moved to its own branch labelled as the Omarchy 4 root, with scrub as the safe check. The claim that root has no password on Omarchy is not a constant: getent shadow root on this 4.0.0 workstation shows the account locked (!*), but the current ISO configurator writes root_enc_password from the same hash as the user password (archinstall_adapter.py creates root with it) and omarchy-provision-owner line 741 sets root to the owner password with chpasswd on deferred-provisioning installs, so the fix now says to try the login password first. The kernel-parameter advice was given an Omarchy branch: the cmdline is embedded in the UKI, so it goes in a /etc/limine-entry-tool.d/ drop-in followed by limine-mkinitcpio, and systemd-stub(7) states that a passed cmdline is ignored under Secure Boot when a .cmdline section exists. Not exercised: no filesystem was damaged or repaired, no VM was booted (pool was down), the Limine menu editor path was not tested, and whether an ext4 root on plain Arch drops to the initramfs shell was taken from init_functions rather than reproduced.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Running fsck on a mounted read-write filesystem will destroy it. Confirm with `findmnt` and `umount` first, and use a live USB for root. `fsck -y` on a physically failing disk can throw away recoverable data. If the drive is suspect, image it first with `ddrescue` and repair the image. Never point e2fsck or xfs_repair at a btrfs device by hand: `fsck` dispatches by type and lands on the harmless `fsck.btrfs`, but `fsck.ext4 /dev/mapper/root` on a btrfs root will rewrite it into garbage. `btrfs check --repair` is called dangerous by btrfs-progs itself and can turn a mountable filesystem into an unmountable one. Reach for it only after `mount -o ro,rescue=usebackuproot` and `btrfs check --readonly` have failed and you hold a backup or an image, and never with `--force` on a mounted filesystem. On Omarchy 4 that one filesystem holds `/`, `/home`, the package cache and every Snapper snapshot, so there is no second copy on the disk to fall back to.

**Fix.**

**Getting past the maintenance prompt.** It asks for the root password. On Omarchy 4 that depends on how the machine was installed: the current ISO's configurator gives root the same password as the user you created, and a deferred-provisioning install sets root to the owner's password at first boot, but an early 4.0.0 install can have root locked. Try your own login password first. If root is locked the prompt cannot be passed, and you work from the ISO instead (the Omarchy ISO gives a root shell with no password on Ctrl+Alt+F2, the Arch ISO on tty1).

**If the failing filesystem is not root** (an extra `/data`, or `/home` on plain Arch), repair it from the maintenance shell:

```bash
findmnt --verify --fstab
umount /dev/sda3          # must NOT be mounted
fsck -f /dev/sda3         # answer y, or use -y to accept everything
systemctl default
```

**If it is an ext4 or XFS root** (plain Arch), do not fsck it from that shell, because root is mounted. Boot the Arch or Omarchy ISO and work on it unmounted:

```bash
lsblk -f
# open LUKS first if encrypted (any mapper name works):
cryptsetup open /dev/nvme0n1p2 root

# ext4:
e2fsck -f /dev/mapper/root          # add -y to auto-answer once you have read the prompts
# xfs:
xfs_repair /dev/mapper/root
# vfat ESP (Omarchy: /dev/nvme0n1p1, normally mounted at /boot):
fsck.fat -a /dev/nvme0n1p1
```

**If the root is btrfs** (every Omarchy 4 install, and archinstall's btrfs layout), there is nothing to fsck: `fsck.btrfs` is a no-op by design, and a normal mount replays the log and fixes almost everything. If the mount itself fails, from the ISO:

```bash
cryptsetup open /dev/nvme0n1p2 root
mount -o ro,rescue=usebackuproot,subvol=@ /dev/mapper/root /mnt   # try the backup tree roots
btrfs check --readonly /dev/mapper/root                            # unmounted, read-only, report only
```

Once it mounts, `btrfs scrub start /` followed by `btrfs scrub status /` is the safe integrity check, and it runs on the mounted filesystem. `btrfs check --repair` stays the last resort, after a backup or a `ddrescue` image.

**To get in once without checking** (to take a backup first), add to the kernel command line:

```
fsck.mode=skip
```

**To force a full check on the next boot** once you are back in:

```
fsck.mode=force fsck.repair=yes
```

On plain Arch, edit the entry at the bootloader menu. On Omarchy 4 the command line is embedded in the UKI at `/boot/EFI/Linux/omarchy_linux.efi`, so put it in a drop-in and rebuild the UKI, as root, from a chroot if the machine does not boot:

```bash
echo 'KERNEL_CMDLINE[default]+=" fsck.mode=skip"' > /etc/limine-entry-tool.d/50-fsck-skip.conf
limine-mkinitcpio
```

Delete the drop-in and run `limine-mkinitcpio` again afterwards. Editing the line at the Limine menu only takes effect with Secure Boot off, because systemd-stub ignores a passed command line when Secure Boot is on and the UKI carries its own. Neither parameter does much on Omarchy, where nothing but the ESP is checked.

Then make sure fstab is sane, because a wrong pass number is a frequent cause of a check that never should have run. The 6th column is the pass number: `1` for an ext4 or XFS root only, `2` for other checkable filesystems, `0` to skip. btrfs, anything non-Linux, and any network or removable mount must be `0`:

```
UUID=974cda7f-...  /      btrfs  rw,relatime,compress=zstd:3,ssd,space_cache=v2,subvol=/@      0 0
UUID=16AE-BBB4     /boot  vfat   rw,relatime,fmask=0077,dmask=0077,utf8,errors=remount-ro       0 2
UUID=...           /data  ext4   defaults,nofail,x-systemd.device-timeout=5s                    0 2
UUID=...           /win   ntfs3  defaults,nofail,x-systemd.device-timeout=5s                    0 0
```

The first two lines are what the Omarchy installer writes. On plain Arch with an ext4 root the root line is `/dev/nvme0n1p2  /  ext4  defaults  0 1`.

If you use the mkinitcpio `fsck` hook (the Arch and Omarchy default), the kernel command line must contain `rw`, not `ro`, or the check cannot run. Omarchy's cmdline already has `rw`.

Repeated inconsistencies mean failing hardware, not a software bug:

```bash
sudo smartctl -a /dev/nvme0n1
sudo dmesg | grep -iE 'i/o error|medium error|nvme.*reset'
```

**Verify.** `e2fsck -f` (or `xfs_repair`) exits 0 or 1 on a second run with no further corrections; `systemctl default` completes; after reboot `systemctl list-units --failed` is empty and `journalctl -b -u 'systemd-fsck@*'` shows clean checks.

Sources: <https://wiki.archlinux.org/title/Fsck> · <https://wiki.archlinux.org/title/Kernel_parameters> · <https://wiki.archlinux.org/title/Btrfs> · <https://wiki.archlinux.org/title/Mkinitcpio> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/install/fsck> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/hooks/fsck> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/init_functions> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/share/omarchy-iso/orchestrator/archinstall_adapter.py> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/share/omarchy-iso/orchestrator/context.py> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-provision-owner> · <https://github.com/archlinux/archiso/blob/master/configs/releng/airootfs/etc/shadow>

---

## GRUB "ran out of memory" loading a large initramfs on AMD Zen 5 laptops

`grub-ran-out-of-memory-zen5-large-initramfs` · severity: **critical** · frequency: **occasional** · applies to: `amd`, `arch`, `grub`, `laptop`, `limine`, `omarchy`, `systemd-boot`

**Symptom.** Fresh install (Omarchy 4.0.1 reported, but the failure mode is generic) on an AMD Ryzen AI 9 HX 370 / Strix Point machine such as a Framework 13. The system dies at or just before the boot menu with:

```
error: ../../grub-core/loader/efi/linux.c:542:grub_cmd_linux: ran out of memory
```

Disabling Secure Boot, hiding the TPM and shrinking the iGPU allocation all fail to help.

**Cause.** GRUB must place the initramfs in a contiguous block of physical memory below 4 GB. A 240 MB+ initramfs (typical once NVIDIA/AMD firmware and early KMS modules are bundled) needs more contiguous low memory than the firmware leaves free once Pluton/fTPM reservations and iGPU carve-outs have fragmented that region. Tracked as basecamp/omarchy#8629.

> **Audit corrected this record.** Issue 8629 exists and matches (GRUB out-of-memory on Ryzen AI 9 HX 370 / Strix Point), and the contiguous-low-memory diagnosis is right. Three problems in the fix. `COMPRESSION_OPTIONS=(-19)` contradicts mkinitcpio.conf(5), which says the setting 'is generally not used. It can be potentially dangerous and may cause invalid images to be generated without any sign of an error' — telling someone with an already-unbootable machine to set it is the wrong risk. A blanket `MODULES=()` silently deletes whatever was there, which on Omarchy is the NVIDIA early-KMS list and on other systems may be the forced vfat modules from the /boot/efi record — that can turn a boot-menu failure into an unmountable root. And `bootctl install` alone gives you systemd-boot with an empty menu: Arch+mkinitcpio does not auto-generate BLS entries, so the machine will boot to a loader with nothing in it.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Switching bootloaders on a machine you cannot currently boot is a one-way trip if it goes wrong — do it from a chroot with a live USB in hand, and leave the old loader's files on the ESP until the new one is proven.

**Fix.**

**Shrink the initramfs.** Boot the fallback/rescue entry or chroot from a live USB, then record what you currently have before changing anything:

```sh
grep -h '^MODULES\|^HOOKS\|^COMPRESSION' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
ls -lh /boot/initramfs-*.img
```

In `/etc/mkinitcpio.conf`, set compression explicitly and leave the options alone — mkinitcpio.conf(5) warns COMPRESSION_OPTIONS can produce a silently invalid image:

```sh
COMPRESSION="zstd"
# do NOT set COMPRESSION_OPTIONS
```

Ensure `autodetect` is present so only in-use modules are packed:

```sh
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)
```

Remove **only** the GPU early-KMS entries from MODULES — do not blank the array, other modules there may be load-bearing:

```sh
# e.g. MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm vfat)  ->  MODULES=(vfat)
```

Rebuild and check:

```sh
sudo mkinitcpio -P
ls -lh /boot/initramfs-linux.img     # aim well under 150 MB
```

**Or switch loader.** Limine (Omarchy 2.0+) and systemd-boot load via the EFI stub and have no low-memory allocator constraint. `bootctl install` only installs the loader — you must also create entries, or you get an empty menu:

```sh
sudo bootctl --esp-path=/boot install
sudoedit /boot/loader/entries/arch.conf
```

```
title   Arch Linux
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=UUID=<your-root-uuid> rw
```

```sh
bootctl list                          # must show the entry BEFORE you reboot
sudo systemctl enable systemd-boot-update.service
sudo efibootmgr -v                    # then reorder with -o <new>,<old>
```

**Verify.** `ls -lh /boot/initramfs-linux.img` shows a substantially smaller image and the machine reaches the boot menu and boots without the memory error.

Sources: <https://github.com/basecamp/omarchy/issues/8629> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://man.archlinux.org/man/bootctl.1>

---

## Recover from "device '' not found" dropping to an emergency shell after the Quattro upgrade

`quattro-upgrade-uki-missing-root-parameter` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `btrfs`, `desktop`, `laptop`, `limine`, `luks`, `omarchy`

**Symptom.** The machine does not boot after upgrading to Omarchy 4 and lands in an initramfs emergency shell. The device in the message is empty quotes, not a UUID:

```
:: running hook [keymap]
:: Loading keymap...done
Error: device '' not found. Skipping fsck
:: mounting '' on real root
mount: /new_root: wrong fs type, bad option, bad superblock on , missing codepage or helper program, or other error.
:: running emergency hook [plymouth]
ERROR: Failed to mount '' on real root
sh: can't access tty; job control turned off
[rootfs ~]#
```

The empty quotes are the diagnostic detail. They mean the initramfs parsed a kernel command line carrying no `root=` at all, rather than a `root=` it could not resolve. A missing hook or a stale UUID would have printed the device name it failed to find.

A second reporter whose upgrade was interrupted mid-transaction hit the same message with two additional symptoms: the active entry in `/boot/limine.conf` had its `cmdline:` line truncated to `initramfs_async=0` alone, and the kernel image that entry pointed at was missing because the pacman transaction never finished.

**Cause.** Established by collaborator triage on `omacom/omarchy#6894`, which is now closed as completed. `/etc/limine-entry-tool.d/omarchy-defaults.conf` appends to `KERNEL_CMDLINE[default]` with `+=`, and `+=` by design stops `limine-entry-tool` falling back to `/etc/kernel/cmdline` or `/proc/cmdline`. On an install that predates the ISO pinning `root=` in `/etc/default/limine`, the moment that drop-in lands any UKI rebuilt afterwards carries only the drop-in's own parameters, and `root=` is gone. `omarchy-upgrade-to-quattro` repairs this in `preserve_kernel_cmdline_root`, but that runs after the package transaction, so there is a window in which the machine will not boot.

Confirmed on an omarchy 4.0.2-1 install. `/etc/limine-entry-tool.d/omarchy-defaults.conf` uses `KERNEL_CMDLINE[default]+=` for the `quiet splash` and `initramfs_async=0` parameters, and `/etc/default/limine` carries the pinned `cryptdevice=` and `root=` line that a repaired or newly installed machine has. `/proc/cmdline` on the running kernel shows those parameters, which is what proves that file and that syntax are the ones that take effect.

The `+=` behaviour is documented by the package itself, in `/etc/limine-entry-tool.conf` and at line 380 of `/usr/share/doc/limine-entry-tool/README.md`: `+=` "Ignores /etc/kernel/cmdline and /proc/cmdline". `/etc/default/limine` is the last of the four layers `load_config` reads in `/usr/lib/limine/limine-common-functions`, which is why pinning there wins and why the same file recommends `+=` rather than `=` there. The installer refuses to finish an install whose assembled config has no `root=` (`orchestrator/phases_impl.py:1288` on the `quattro` branch of `omacom/omarchy-iso`), and that is the pinning an upgraded machine never received.

`omacom/omarchy#6951`, which pins `root=` before the packages that can drop it, is still open on 2026-09-11, so the window is still there. It is still there in the newest release: at tag `v4.0.3`, published 2026-09-08, `omarchy-upgrade-to-quattro` still calls `install_omarchy_quattro_packages` at line 2360 and `preserve_kernel_cmdline_root` only at line 2363.

> **Audit corrected this record.** Checked every claim against local files on this omarchy 4.0.2-1 workstation and against `omacom/omarchy#6894` and `#6951` read in full today. The failure itself cannot be exercised here: this machine boots, it is already pinned, I have no sudo, and nothing was rebuilt, no UKI written and no VM used. So the mechanism is confirmed from source and from config files, and the recovery steps are confirmed as correct commands on Omarchy 4 rather than as a completed recovery.

Confirmed on this machine. `/etc/limine-entry-tool.d/omarchy-defaults.conf` does use `KERNEL_CMDLINE[default]+=` for `quiet splash` and for `initramfs_async=0`, and `/etc/default/limine` does carry a pinned `cryptdevice=` and `root=` line, exactly as the record says. `/proc/cmdline` shows all of those parameters on the running kernel, which is the strongest check available here: that file and that `+=` syntax demonstrably produce a working cmdline. The `+=` mechanism is documented by the package, not only asserted by a collaborator: `/etc/limine-entry-tool.conf` and line 380 of `/usr/share/doc/limine-entry-tool/README.md` both say `+=` "Ignores /etc/kernel/cmdline and /proc/cmdline", and `load_config` in `/usr/lib/limine/limine-common-functions` loads `/etc/default/limine` last of four layers. `preserve_kernel_cmdline_root` is at line 520 of `/usr/share/omarchy/bin/omarchy-upgrade-to-quattro` and is called at line 2362, after `install_omarchy_quattro_packages` at 2359, so the record's window claim holds on the installed version, and it still holds at tag `v4.0.3` (lines 2360 and 2363), which I fetched because 4.0.2 is no longer the newest release. `#6951` is still open. `#6894`'s collaborator comment supports the cause in detail and recommends the same recovery, appending to `/etc/default/limine` with `+=` and running `limine-mkinitcpio`, so the citation genuinely supports the claim. Issue `#6894` is closed as completed, which the record did not say.

`limine-mkinitcpio` over the preset form is correct, which I was asked to confirm. `/etc/mkinitcpio.d/` is empty here, and `/usr/bin/mkinitcpio` line 986 dies with `No presets found in %s` when it is, so the record's quoted message is right. The underlying reason is firmer than the record gave: `limine-mkinitcpio-hook` ships `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`, which overrides Arch's hook of the same name and calls `limine-mkinitcpio-install` instead of the script that generates presets, and `mkinitcpio` on `PATH` resolves to `/usr/local/bin/mkinitcpio`, a wrapper from that same package which warns "This does not update Limine boot entries" and offers `limine-mkinitcpio`. I also checked that the quattro upgrade never touches `/etc/mkinitcpio.d/`, so an upgraded machine can still hold a stale preset and `mkinitcpio -P` can run there and leave the boot entries untouched. That is the stronger reason to avoid it, so I put it first. I checked `sudo pacman -S linux` against `/usr/bin/omarchy-update-pacman-guard`: the guard aborts only when both `-S` and `-u` are present, so that command is not blocked and the record is not proposing a blocked path.

What was wrong. The fix's one worked example is `root=/dev/mapper/root`, and the Omarchy 4 ISO opens LUKS as `omarchy_root` (`configurator` on the `quattro` branch of `omacom/omarchy-iso`), so `/dev/mapper/omarchy_root`. On a boot fix, one example with no way to tell which name applies is a defect, so I rewrote the fix to derive the name from `ls -l /dev/mapper/` and to give the encrypted and unencrypted forms separately, with `cryptdevice=` and `root=` agreeing on the mapper name. Second, the record tells the reader to get real values off the machine but never warns that the values on hand come from a snapshot boot: `/proc/cmdline` there carries the snapshot's `rootflags=subvol=` and not `@`, and copying it reproduces the unbootable state. The package warns about this itself in `/etc/limine-entry-tool.conf`, and it now appears in both the fix and the danger. Everything else in the record held and I left it as written.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** You are editing the kernel command line on a machine that already will not boot. Keep `+=` rather than `=` in `/etc/default/limine`, because a bare `=` replaces Omarchy's own defaults, `initramfs_async=0` among them. Read the device names and the decrypted root's mapper name off the machine with `lsblk -f`, `blkid` and `ls -l /dev/mapper/` instead of copying the example: an ISO-installed machine is `omarchy_root` and an upgraded one is commonly `root`, and the wrong name is another failed boot. Do not copy `rootflags=` out of `/proc/cmdline` while you are booted from a snapshot, because it names the snapshot's subvolume rather than `@`, which is the same warning the package prints in `/etc/limine-entry-tool.conf`. If you rebuild while booted from a snapshot, restore that snapshot over `@` before rebooting, or the new entry stays rooted on the snapshot.

**Fix.**

Boot a working kernel first. The Limine menu's btrfs snapshot entries point at complete kernel copies, so pick one of those rather than the broken `linux` entry.

Read the real values off the machine before you write anything:

```bash
lsblk -f                 # the LUKS container and the btrfs root
blkid                    # PARTUUIDs and UUIDs
ls -l /dev/mapper/       # the decrypted root's actual mapper name
cat /proc/cmdline        # reference only, see the warning below
```

Two things that catch people here. The mapper name is not the same on every install: a machine installed by the Omarchy 4 ISO opens LUKS as `omarchy_root`, so `/dev/mapper/omarchy_root`, while a machine that came up through earlier releases is commonly `/dev/mapper/root`. Use what `ls -l /dev/mapper/` shows. And while you are booted from a snapshot, `/proc/cmdline` carries the snapshot's `rootflags=subvol=` value, not `@`, so do not copy that parameter out of it. The package warns about exactly this in `/etc/limine-entry-tool.conf`.

Then pin the parameters the UKI is missing, in the file Omarchy reads, and rebuild. On an encrypted root, `cryptdevice=` names the LUKS partition and the mapper name to create, and `root=` names that mapper:

```bash
# add to /etc/default/limine, keeping += so Omarchy's own defaults survive
sudo tee -a /etc/default/limine >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" cryptdevice=PARTUUID=<partuuid-of-the-luks-partition>:omarchy_root root=/dev/mapper/omarchy_root rootflags=subvol=@ rw rootfstype=btrfs"
EOF

sudo limine-mkinitcpio
```

On an unencrypted root, `root=` names the btrfs partition itself, by UUID rather than by a device node that can move:

```bash
sudo tee -a /etc/default/limine >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" root=UUID=<uuid-of-the-btrfs-partition> rootflags=subvol=@ rw rootfstype=btrfs"
EOF

sudo limine-mkinitcpio
```

If the upgrade was interrupted and the kernel image itself is missing, finish the transaction from the snapshot before rebuilding:

```bash
sudo mount -o remount,rw /
sudo pacman -S linux
sudo limine-mkinitcpio
```

That `pacman -S` is not blocked by Omarchy's ALPM guard, which aborts only when both `-S` and `-u` are present. Do not turn it into `pacman -Syu`: that is the guard's case, and on a half-finished upgrade it is a partial-upgrade risk as well.

Use `limine-mkinitcpio`, not the `mkinitcpio` preset form. The preset form does not update the Limine boot entries or rebuild the UKI, which is the whole of what this machine needs. On a machine installed by the Omarchy 4 ISO it does not even run: `limine-mkinitcpio-hook` ships `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`, which overrides Arch's own hook and never generates presets, so `/etc/mkinitcpio.d/` is empty and `mkinitcpio -P` stops with `No presets found in /etc/mkinitcpio.d`. An upgraded machine may still have a preset file left from before, in which case `mkinitcpio -P` runs and silently leaves the boot entries stale. `mkinitcpio` on `PATH` is itself a wrapper from that package at `/usr/local/bin/mkinitcpio`, and it answers a preset run by warning that it did not update the Limine boot entries and offering to run `limine-mkinitcpio` for you.

One trap from the reporter who recovered this way. Running the rebuild while booted from a snapshot roots the new boot entry on the snapshot rather than on the real `@` subvolume, and Omarchy notifies you to restore the snapshot before rebooting. Use the snapshot tool's restore menu to replace `@` with the snapshot you are running from, then reboot into the normal entry.

**Verify.** ```bash
cat /proc/cmdline                 # root= is present, with cryptdevice= on LUKS
mount | grep ' / '                # subvol=/@, not a snapshot path
omarchy-migrate --pending         # empty, if the upgrade had stalled
```

Sources: <https://github.com/omacom/omarchy/issues/6894> · <https://github.com/omacom/omarchy/pull/6951> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-upgrade-to-quattro> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/share/omarchy-iso/orchestrator/phases_impl.py>

---

## Boot/reboot loop when the TPM is present but unresponsive (systemd-pcrphase)

`tpm-unresponsive-reboot-loop` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `laptop`, `limine`, `omarchy`, `systemd-boot`, `tpm`

**Symptom.** Omarchy 4.0.0 installs cleanly on a ThinkPad T470, reaches the login screen, accepts the password, shows a loading state — and then reboots back to Limine. Loop repeats forever. The journal from the failed boot shows:

```
tpm tpm0: TPM0: Operation timed out
Failed to create TPM2 context: State not recoverable
systemd-pcrphase-sysinit.service: Main process exited, code=exited, status=1
```

**Cause.** `systemd-pcrphase-sysinit.service` tries to extend TPM PCRs during early boot. When the TPM chip is present in firmware but unresponsive (timeouts, I/O errors, invalid status), the unit fails hard and the failure cascades into a forced reboot rather than degrading gracefully. Tracked as basecamp/omarchy#8190.

> **Audit corrected this record.** Issue 8190 is real and the record reproduces its journal excerpt faithfully (the issue also shows the 'Forcibly rebooting' line that explains the loop). The workaround is the one confirmed upstream. What is missing is a safety warning that makes the difference between a fix and a lockout: if the machine uses TPM-backed LUKS unlock (systemd-cryptenroll --tpm2-device), disabling the Security Chip in firmware removes the unlock path, and masking the pcrphase units changes PCR values so TPM-sealed secrets no longer unseal. On a laptop whose owner set up TPM auto-unlock and does not remember the recovery passphrase, this advice ends the session at an unopenable LUKS prompt.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** If you have enrolled a LUKS key against the TPM (systemd-cryptenroll --tpm2-device), disabling or clearing the TPM makes that key unusable and you must unlock with your passphrase. Never clear the Security Chip without first confirming you still know a working LUKS passphrase.

**Fix.**

**Before touching the TPM, check whether anything is sealed to it.** If a TPM2 keyslot is enrolled, disabling the chip removes your unlock path:

```sh
sudo cryptsetup luksDump /dev/nvme0n1p2 | grep -A3 -i 'tpm2\|Tokens'
sudo systemd-cryptenroll /dev/nvme0n1p2      # lists enrolled slots
```

If a TPM2 token is listed, make sure you have a working passphrase or recovery key **and have tested it** before continuing.

The confirmed workaround is to hide the TPM in firmware:

- ThinkPad BIOS: **Security -> Security Chip -> Disabled**. Do **not** Clear the Security Chip — clearing destroys sealed keys irreversibly; disabling is reversible.

To break the loop before you can reach firmware, at the Limine menu press `e` and append to the `cmdline:` line for one boot:

```
systemd.mask=systemd-pcrphase-sysinit.service systemd.mask=systemd-pcrphase.service
```

Once booted, persist it:

```sh
sudo systemctl mask systemd-pcrphase-sysinit.service systemd-pcrphase.service systemd-pcrphase-initrd.service
```

Note this changes the PCR measurements, so any secret sealed to a PCR policy (TPM LUKS unlock, systemd-creds) will stop unsealing — re-enroll with `systemd-cryptenroll --wipe-slot=tpm2 --tpm2-device=auto` after the TPM is working again, or leave TPM unlock off on this machine. Attach `journalctl -b -1` to issue #8190.

**Verify.** `systemctl --failed` lists no `systemd-pcrphase*` units and the machine survives three consecutive cold boots to the desktop.

Sources: <https://github.com/basecamp/omarchy/issues/8190> · <https://github.com/basecamp/omarchy/issues/8629>

---

## Signature errors block every upgrade after months without updating (archlinux-keyring too old)

`archlinux-keyring-outdated-blocks-every-upgrade` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Any attempt to update fails before installing anything:

```
error: linux: signature from "Some Maintainer <maintainer@archlinux.org>" is unknown trust
:: File /var/cache/pacman/pkg/linux-7.0.3-1-x86_64.pkg.tar.zst is corrupted (invalid or corrupted package (PGP signature)).
Do you want to delete it? [Y/n]
error: failed to commit transaction (invalid or corrupted package (PGP signature))
Errors occurred, no packages were upgraded.
```

On Omarchy this shows up as `omarchy update` failing in the package step. It blocks every other repair you might want to attempt, because you cannot install anything.

**Cause.** Package signatures are verified against the keys in `/etc/pacman.d/gnupg`, which are shipped by the `archlinux-keyring` package. Maintainers rotate and add keys constantly, so a machine that has not updated for a few months holds a keyring that predates the keys on the current packages. A wrong system clock produces the same class of error (`signature ... is invalid`) because keys look expired or not-yet-valid.

> **Audit corrected this record.** The cause, the clock check, the keyring-first principle, `omarchy-update-keyring`, the Omarchy key fingerprint 40DFB630FF42BCFFB047046CF0134EE680CAC571 with keys.openpgp.org + --lsign-key + omarchy-keyring (all three verified verbatim in bin/omarchy-update-keyring), the gnupg reset, and the geo.mirror.pkgbuild.com fallback are right. But the explicit reassurance about Omarchy is false and leaves the user in the exact state the record warns against. bin/omarchy-update-pacman-guard sets has_sync on any short option containing S and has_sysupgrade on any containing u, and blocks when both are set — so `sudo pacman -Su` is blocked just as `-Syu` is. The recommended `sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su` therefore syncs the database and then refuses the upgrade, leaving a partially-synced system.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never stop after `pacman -Sy` — that leaves the sync database ahead of your installed packages, and the next single-package install becomes a partial upgrade that can break glibc/kernel pairing. Always chain `&& pacman -Su`. Do not "fix" this by setting `SigLevel = Never` or `TrustAll` in /etc/pacman.conf: you disable package authentication system-wide. Deleting /etc/pacman.d/gnupg also drops any locally signed third-party keys, which must be re-added afterwards.

**Fix.**

Clock first, keyring before everything else — unchanged:

```bash
timedatectl
sudo timedatectl set-ntp true
```

On Omarchy 4, use the packaged path (it recv/lsigns the Omarchy key, installs omarchy-keyring, and reinstalls archlinux-keyring even without a version bump):

```bash
omarchy-update-keyring
omarchy update
```

Do not use `sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su` on Omarchy. The ALPM guard blocks any pacman run carrying both -S and -u, and that includes a bare `-Su`: the first half syncs the databases, the second half is refused, and you are left with a synced-but-not-upgraded system — the partial-upgrade state this record exists to avoid. If you must drive pacman directly:

```bash
sudo pacman -Sy --needed archlinux-keyring
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Su
```

On plain Arch/EndeavourOS/CachyOS (no guard) the original one-liner is correct as written.

The rest of the record stands, with one caveat: `sudo rm -rf /etc/pacman.d/gnupg` also discards every key you locally signed for the AUR or third-party repos, so on Omarchy re-run `omarchy-update-keyring` (and re-lsign any custom repo keys) after `pacman-key --init && pacman-key --populate archlinux`. Note `pacman -Sc --noconfirm` does work — -Sc's prompt defaults to yes, unlike -Scc's.

**Verify.** `sudo pacman -Syu` proceeds past the signature check and reaches the package list; `sudo pacman-key --list-keys | wc -l` grows; `pacman -Q archlinux-keyring` shows a recent version.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-keyring> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pacman-guard> · <https://wiki.archlinux.org/title/Pacman>

---

## Chroot from a live USB correctly (including the Btrfs subvol=@ trap)

`chroot-recovery-btrfs-missing-subvol` · severity: **high** · frequency: **very-common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `luks`, `manjaro`, `omarchy`

**Symptom.** You boot a live USB to repair the system, run `arch-chroot /mnt`, reinstall the kernel — and nothing improves. Or the repair itself fails with things like:

```
'/boot/initramfs-linux.img' not found
dracut-install: Failed to find module 'zfs'
```

and after rebooting you are back in the emergency shell.

**Cause.** On Btrfs installs (Omarchy, EndeavourOS and CachyOS all default to Btrfs subvolumes) mounting `/dev/nvme0n1p2 /mnt` mounts the *top-level* subvolume, not the actual root. The chroot then sees an almost-empty filesystem, package scripts silently operate on the wrong tree, and the initramfs is written somewhere the bootloader never reads. The same class of failure comes from forgetting to mount the ESP at `/mnt/boot`, or forgetting to open the LUKS container first.

> **Audit corrected this record.** Checked the Omarchy 4 layout on this machine (findmnt, /etc/fstab, lsblk, /proc/cmdline, /etc/default/limine, /etc/limine-entry-tool.d/*.conf) and against the ISO configurator in omacom/omarchy-iso quattro: the root is LUKS2 on p2 with btrfs subvolumes @, @home, @log and @pkg mounted at /, /home, /var/log and /var/cache/pacman/pkg, the ESP is vfat at /boot, and Snapper's /.snapshots is a subvolume nested inside @ (inode 256 here), so there is no @snapshots to mount. The record mounts only @ and @home, so pacman inside its chroot writes the package cache and logs into the @ subvolume instead of @pkg and @log. The mapper name cryptroot is neither of the names Omarchy uses (omarchy_root in the current configurator, root on this 4.0.0 install per the cmdline). Any name works for a chroot because the rebuilt cmdline is read from /etc/default/limine and the drop-ins inside the chroot, and the corrected fix says so. The rebuild step was the main defect: on Omarchy 4 /etc/mkinitcpio.d/ is empty, so mkinitcpio -P dies with 'No presets found in /etc/mkinitcpio.d' (mkinitcpio 41.1 line 986, confirmed here), the kernel boots as the UKI /boot/EFI/Linux/omarchy_linux.efi, and the right command is limine-mkinitcpio (or pacman -S linux, whose 90-mkinitcpio-install hook from limine-mkinitcpio-hook runs the same script). The verify step's ls -l /boot/vmlinuz-linux therefore does not apply to Omarchy. Confirmed from /usr/bin/omarchy-update-pacman-guard that the ALPM guard only aborts when -S and -u are combined, so pacman -S linux in a chroot is not blocked. Confirmed from /usr/lib/limine/limine-common-functions that the ESP is found by a vfat mount at /efi, /boot, /boot/efi or /limine and the tool stops with 'FAT32 boot partition not found' otherwise, and from limine-mkinitcpio-install that the UKI is only built when /sys/firmware/efi exists, which is why UEFI mode matters. Confirmed from the archiso releng profile (GitHub mirror) that both ISOs autologin root on tty1 with an empty root password and ship arch-install-scripts, btrfs-progs and dosfstools, and from omarchy-iso build-iso.sh that the Omarchy ISO is seeded from releng and adds cryptsetup, so the record's sudo prefixes are unnecessary and a shell is on Ctrl+Alt+F2. The cited EndeavourOS thread (post 15) does support the subvol=@ claim, arch-chroot(8) was re-read (plain arch-chroot /mnt still works, -S is optional), and the Omarchy manual security page confirms LUKS is the installer default. Not exercised: no chroot was performed, no VM was booted (the pool was down), and the mapper name on installs between 4.0.0 and the current ISO was not sampled beyond this machine.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Writing into a wrongly mounted chroot damages the wrong tree. On btrfs the top-level subvolume (subvolid 5) holds `@`, `@home`, `@log` and `@pkg` as directories and nothing else, so a chroot into it has no `/etc/fstab` and no `pacman`. Confirm `/etc/fstab` is visible before writing anything. With `/boot` left unmounted, plain Arch's `mkinitcpio -P` writes `/boot/vmlinuz-linux` into the root subvolume where the bootloader never looks. Omarchy's `limine-mkinitcpio` refuses instead (`FAT32 boot partition not found`), but an ESP mounted at the wrong path still leaves the UKI where the firmware will not find it. Do not run `btrfs check --repair` or delete subvolumes while hunting for the root: the missing files are a mount mistake, not filesystem damage, and on Omarchy that one filesystem holds `/home` and every Snapper snapshot.

**Fix.**

Boot the Arch ISO or the Omarchy ISO in **UEFI mode**. Both log you in as root, so no `sudo` is needed. On the Omarchy ISO the installer owns tty1: press Ctrl+Alt+F2 and log in as `root` with no password (the live image is built on the Arch releng profile, which ships an empty root password plus `arch-install-scripts`, `btrfs-progs`, `dosfstools` and `cryptsetup`).

On Omarchy 4, try the **Snapshots** entry in the Limine menu before reaching for the ISO: it boots a Snapper snapshot of the root subvolume, and `omarchy-snapshot restore` can roll back from there. If that boots, you may not need a chroot at all.

```sh
# 1. see the layout. Omarchy: p1 is the vfat ESP, p2 is LUKS (bare btrfs on an unencrypted install)
lsblk -f

# 2. unlock encryption if present (the Omarchy installer encrypts by default).
#    The mapper name is yours to choose here: Omarchy's own installs use
#    "omarchy_root" (current ISO) or "root" (earlier 4.x installs), and the
#    rebuilt boot files do not inherit whatever you type.
cryptsetup open /dev/nvme0n1p2 omarchy_root

# 3. list the subvolumes so you mount the right ones
mount /dev/mapper/omarchy_root /mnt
btrfs subvolume list /mnt
umount /mnt

# 4. mount the ROOT subvolume, then every other subvolume fstab expects.
#    Omarchy 4 (from the ISO configurator): @ @home @log @pkg
mount -o subvol=@,compress=zstd     /dev/mapper/omarchy_root /mnt
mount -o subvol=@home,compress=zstd /dev/mapper/omarchy_root /mnt/home
mount -o subvol=@log,compress=zstd  /dev/mapper/omarchy_root /mnt/var/log
mount -o subvol=@pkg,compress=zstd  /dev/mapper/omarchy_root /mnt/var/cache/pacman/pkg

# 5. mount the ESP where the installed system expects it. Omarchy: /boot
mount /dev/nvme0n1p1 /mnt/boot

# 6. chroot
arch-chroot /mnt
```

Snapper's `/.snapshots` on Omarchy is a subvolume nested inside `@`, so it comes along with step 4 and needs no separate mount. Plain Arch installed with `archinstall`'s btrfs layout has a separate `@snapshots` for `/.snapshots`. Mount it the same way.

Inside the chroot, `cat /etc/fstab` tells you the exact mount points and subvolume names the installed system uses. If `/mnt/boot` is empty or `/etc/fstab` names `/boot/efi` or `/efi`, unmount and remount the ESP there before doing anything else.

For a non-Btrfs (ext4) install, step 4 is simply `mount /dev/nvme0n1p2 /mnt`.

Rebuilding the boot files differs between Omarchy 4 and plain Arch:

**Omarchy 4.** `/etc/mkinitcpio.d/` is empty, so `mkinitcpio -P` stops with `No presets found in /etc/mkinitcpio.d`. The kernel boots as a UKI at `/boot/EFI/Linux/omarchy_linux.efi`, built by `limine-mkinitcpio-hook`. Run:

```sh
limine-mkinitcpio        # rebuilds the UKI and the Limine entries
```

or `pacman -S linux`, whose `90-mkinitcpio-install` hook runs the same script. The Omarchy ALPM guard only aborts a transaction that combines `-S` with `-u`, so a plain `pacman -S linux` goes through. The kernel command line is read from `/etc/default/limine` and `/etc/limine-entry-tool.d/*.conf` inside the chroot, not from the live ISO, so the mapper name from step 2 does not end up in the UKI. The tool locates the ESP by looking for a vfat mount at `/efi`, `/boot`, `/boot/efi` or `/limine`, and with `/boot` unmounted it stops with `FAT32 boot partition not found` instead of writing anywhere. The UKI is only built when `/sys/firmware/efi` exists, which is why the ISO must be booted in UEFI mode.

**Plain Arch.** `pacman -S linux` or `mkinitcpio -P` writes `/boot/vmlinuz-linux` and `/boot/initramfs-linux.img`. Re-run your bootloader's install or config step afterwards if it copies files.

When done:

```sh
exit
umount -R /mnt
cryptsetup close omarchy_root
reboot
```

`arch-chroot` is provided by `arch-install-scripts` and handles mounting `/dev`, `/proc`, `/sys` and copying `resolv.conf` for you. Do not use plain `chroot` unless you replicate those bind mounts by hand.

**Verify.** Inside the chroot, `cat /etc/fstab` shows the `subvol=/@` line for `/` and `pacman -Q linux` prints your installed kernel. If either fails you mounted the wrong subvolume. Omarchy 4: after `limine-mkinitcpio`, `ls -l /boot/EFI/Linux/omarchy_linux.efi` shows a fresh timestamp. Plain Arch: after `pacman -S linux`, `ls -l /boot/vmlinuz-linux /boot/initramfs-linux.img` shows fresh timestamps.

Sources: <https://forum.endeavouros.com/t/boot-initramfs-linux-img-not-found-chroot-on-live-and-update-doesnt-help/50238> · <https://man.archlinux.org/man/arch-chroot.8> · <https://learn.omacom.io/2/the-omarchy-manual/93/security> · <https://wiki.archlinux.org/title/Chroot> · <https://gitlab.archlinux.org/archlinux/arch-install-scripts/-/raw/master/arch-chroot.in> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/share/omarchy-iso/orchestrator/phases_impl.py> · <https://github.com/omacom/omarchy-iso/blob/quattro/builder/build-iso.sh> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/.automated_script.sh> · <https://github.com/archlinux/archiso/blob/master/configs/releng/packages.x86_64> · <https://github.com/archlinux/archiso/blob/master/configs/releng/airootfs/etc/shadow> · <https://github.com/archlinux/archiso/blob/master/configs/releng/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf> · <https://github.com/basecamp/omarchy/blob/quattro/install/config/snapper.sh>

---

## A bad /etc/fstab entry drops the system to emergency mode or hangs 90 seconds

`fstab-bad-entry-emergency-mode` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** Boot stalls with:

```
A start job is running for /dev/disk/by-uuid/1a2b-3c4d (1min 30s / no limit)
```

and then:

```
[FAILED] Failed to mount /boot.
[DEPEND] Dependency failed for Local File Systems.
You are in emergency mode. After logging in, type "journalctl -xb" to view
system logs, "systemctl reboot" to reboot ...
Give root password for maintenance (or press Control-D to continue):
```

The mount point named is whatever line failed: `/boot` on Omarchy 4, where the ESP is mounted there, `/boot/efi` on EndeavourOS and many hand-built Arch installs. Usually after swapping a disk, removing an external drive, reformatting the ESP, or turning off a swap partition. On Omarchy the prompt appears after Plymouth quits, so it can follow a few seconds of blank splash.

**Cause.** systemd generates a mount unit for every `/etc/fstab` line. If the device never appears, the generated `.device` unit waits (default 90 s) and then the mount fails; because `local-fs.target` *requires* it, the whole boot fails into emergency mode. A reformatted ESP or a re-created swap partition has a new UUID, so the old fstab line can never be satisfied.

> **Audit corrected this record.** The systemd mechanics held against the installed systemd 261.2-1 man page (man -P cat systemd.mount, same text as https://man.archlinux.org/man/systemd.mount.5): fstab lines become mount units at boot and on daemon-reload, a block-backed mount gains Requires= and After= on its device unit, nofail turns the Requires= from local-fs.target into Wants= and drops the Before= ordering, and x-systemd.device-timeout= caps the device wait and is honoured only in fstab. systemctl show reports DefaultDeviceTimeoutUSec=1min 30s here, and /usr/lib/systemd/system/local-fs.target carries OnFailure=emergency.target, so the 90 second stall and the drop to emergency mode are confirmed on this machine. findmnt --verify is in findmnt(8) of util-linux 2.42.2, and mount -a is the correct dry run of the file. The root password prompt is reachable on Omarchy 4: the ISO configurator (omacom/omarchy-iso, quattro, configs/airootfs/root/configurator) writes root_enc_password with the same SHA-512 hash as the user's password into user_credentials.json, and orchestrator/archinstall_adapter.py's root_user() creates root from it, so root is not locked and the emergency prompt takes the login password. The wizard text says so too: "Used for user + root, and disk encryption when enabled". I could not confirm it against /etc/shadow here (root only), so it is from source, not this machine. What was wrong for Omarchy 4: the symptom names /boot/efi and the example fstab shows an ext4 root, while /etc/fstab here mounts the ESP at /boot (vfat, fmask=0077,dmask=0077, pass 2) and root is btrfs subvolumes (@, @home, @log, @pkg) on /dev/mapper/root, all pass 0. Omarchy's initramfs uses the busybox encrypt hook (HOOKS in /etc/mkinitcpio.conf.d/omarchy_hooks.conf) with cryptdevice=PARTUUID=...:root and rw on the kernel command line, so by the time emergency.target starts the mapper is open and / is mounted read-write, and lsblk -f and blkid show the mapper rather than the raw partition. The swap advice was the other miss: Omarchy has no swap partition, it hibernates to /swap/swapfile with resume=/dev/mapper/root resume_offset=... coming from /etc/limine-entry-tool.d/resume.conf, which is embedded in the UKI, so dropping resume= means removing that drop-in and running limine-mkinitcpio, not editing a GRUB line. omarchy-hibernation-remove deletes the swapfile, the fstab line and the resume hook but leaves resume.conf in place. On plain Arch with the mkinitcpio resume hook, hooks/resume calls resolve_device, which waits rootdelay (default 10 s per init_functions poll_device) and then continues, so the wait is 10 s rather than indefinite. The GRUB paths in the plain Arch branch are from https://wiki.archlinux.org/title/GRUB. The three EndeavourOS forum threads the record cites still resolve but were not re-read for this pass. The emergency shell itself was not exercised, and nothing was rebooted.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never add `nofail` to the root filesystem line, and on Omarchy 4 never add it to the `/home`, `/var/log` or `/var/cache/pacman/pkg` subvolume lines either: they sit on the same device as root and Omarchy's update path expects them mounted. Editing fstab with a broken syntax (missing field, wrong pass number) can itself cause emergency mode: always run `sudo findmnt --verify` and `sudo mount -a` before rebooting. On Omarchy the ESP is `/boot` and holds the Limine UKI, so a wrong UUID on that line means the next kernel or firmware update writes the UKI into the root filesystem instead of the ESP and the machine boots the old kernel.

**Fix.**

At the emergency prompt log in as root. On Omarchy 4 the root password is the password you chose at install, because the installer sets root and your user to the same one. If you cannot log in, boot a live USB and chroot instead. On an encrypted Omarchy install the LUKS container is already open (`/dev/mapper/root`) and `/` is mounted read-write by the time you reach this prompt. Compare fstab against reality:

```sh
lsblk -f
blkid
cat /etc/fstab
```

Fix the UUIDs, or delete lines for devices that no longer exist. Root filesystem must stay mandatory, but make optional mounts non-fatal.

**Plain Arch (ext4 root, ESP at `/boot/efi` or `/boot`):**

```
# <device>                                <dir>       <type> <options>                          <dump> <pass>
UUID=1a2b-3c4d                            /boot       vfat   defaults,noatime                   0 2
UUID=aaaa-bbbb-cccc                       /           ext4   rw,relatime                        0 1
UUID=dddd-eeee-ffff                       none        swap   defaults                           0 0
# external / removable: never block boot
UUID=1111-2222                            /mnt/data   ext4   defaults,nofail,x-systemd.device-timeout=10s  0 2
```

**Omarchy 4 (btrfs subvolumes on `/dev/mapper/root`, ESP at `/boot`):** the installer writes one line per subvolume, all with the same UUID and pass `0`, and the ESP with pass `2`. Keep those as they are and only add `nofail` to drives you bolted on later:

```
# /dev/mapper/root
UUID=<btrfs-uuid>  /                      btrfs  rw,relatime,compress=zstd:3,ssd,space_cache=v2,subvol=/@      0 0
UUID=<btrfs-uuid>  /home                  btrfs  rw,relatime,compress=zstd:3,ssd,space_cache=v2,subvol=/@home  0 0
UUID=<btrfs-uuid>  /var/cache/pacman/pkg  btrfs  rw,relatime,compress=zstd:3,ssd,space_cache=v2,subvol=/@pkg   0 0
UUID=<btrfs-uuid>  /var/log               btrfs  rw,relatime,compress=zstd:3,ssd,space_cache=v2,subvol=/@log   0 0
# /dev/nvme0n1p1
UUID=<esp-uuid>    /boot                  vfat   rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro  0 2
# Btrfs swapfile for system hibernation
/swap/swapfile     none                   swap   defaults,pri=0  0 0
# external / removable: never block boot
UUID=1111-2222     /mnt/data              ext4   defaults,nofail,x-systemd.device-timeout=10s  0 2
```

`nofail` makes the mount *wanted* rather than *required* by `local-fs.target` and removes the ordering before it, so boot continues whether or not the device turns up. `x-systemd.device-timeout=` caps how long systemd waits for the device instead of the 90-second default. It only works in `/etc/fstab`, not in a unit file.

Apply and test without rebooting blind:

```sh
sudo findmnt --verify   # parse check of /etc/fstab
sudo systemctl daemon-reload
sudo mount -a          # must return with no errors
sudo systemctl reboot
```

`daemon-reload` regenerates the mount units from the edited file. `mount -a` mounts every line not already mounted and fails loudly on a bad one, but it does not exercise the device timeout, so a `nofail` line for a missing drive still passes.

If the failing entry is swap you removed, also drop `resume=` from the kernel command line so the initramfs stops looking for it:

- **Plain Arch:** remove `resume=` from your bootloader's kernel line (for GRUB, `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` then `grub-mkconfig -o /boot/grub/grub.cfg`). With the mkinitcpio `resume` hook the wait is about 10 seconds (`rootdelay`), after which boot continues with an error in the log.
- **Omarchy 4:** the swap is a swapfile, and `resume=/dev/mapper/root resume_offset=...` lives in `/etc/limine-entry-tool.d/resume.conf`, which is baked into the UKI. Prefer `omarchy-hibernation-remove`, which disables the swapfile, drops its fstab line and removes the `resume` hook, then delete the drop-in and rebuild the UKI:

```sh
omarchy-hibernation-remove
sudo rm /etc/limine-entry-tool.d/resume.conf
sudo limine-mkinitcpio
```

**Verify.** `sudo mount -a` produces no output, `systemctl --failed` is empty after reboot, and `systemd-analyze blame | head` no longer shows a ~90 s device job.

Sources: <https://man.archlinux.org/man/systemd.mount.5> · <https://forum.endeavouros.com/t/emergency-mode-failed-to-mount-boot-efi-vfat-error-tried-base-reinstall-issue-persists/75747> · <https://forum.endeavouros.com/t/a-start-job-is-running-for-dev-disk-uui-running-for-5min/80783> · <https://forum.endeavouros.com/t/whenever-kernel-updates-efi-mount-fails-on-reboot/77575> · <https://man.archlinux.org/man/sulogin.8> · <https://man.archlinux.org/man/findmnt.8> · <https://wiki.archlinux.org/title/Fstab> · <https://wiki.archlinux.org/title/GRUB> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/hooks/resume> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/init_functions> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/share/omarchy-iso/orchestrator/archinstall_adapter.py> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hibernation-remove>

---

## Get a shell without a live USB: rescue kernel parameters at the boot menu (Limine, GRUB, systemd-boot)

`kernel-cmdline-rescue-parameters-at-boot-menu` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** "My machine boots to a black screen / hangs / drops straight into a failing graphical session and I don't have a USB stick handy. How do I get a root shell to fix it?" Common variants: a bad `/etc/fstab` line hangs the boot, a display manager crash-loops, a GPU driver update leaves nothing on screen after the boot menu, or systemd prints `You are in emergency mode` and refuses the root password.

**Cause.** Almost every one of these is recoverable by adding a kernel parameter for one boot. Boot loaders let you edit the command line of a menu entry before launching it, and both systemd and the kernel honour parameters that stop the boot early (before the display manager, before fstab mounts, or before KMS).

> **Audit corrected this record.** Almost all of it verified — Limine has an in-menu editor (CONFIG.md: editor_enabled, default yes) and `cmdline:` is the right key, systemd.unit=, systemd.mask=, nomodeset, fsck.mode=skip, init=/bin/bash and the SysV alias `3` are all real, and the /etc/limine-entry-tool.d/99-local.conf drop-in with KERNEL_CMDLINE[default]+=" ..." matches the exact syntax Omarchy uses in etc/limine-entry-tool.d/omarchy-defaults.conf. But the record contradicts itself and gives a dead-end escape: it correctly says rescue.target requires the root password, then recommends `systemd.unit=rescue.target` as the workaround for a machine where root has no password. rescue.service and emergency.service both run systemd-sulogin-shell, so rescue mode is exactly as unreachable as emergency mode on Omarchy's locked root. Also rd.break is offered without noting that Omarchy/Arch use mkinitcpio, not dracut, so it does nothing there.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `init=/bin/bash` leaves the root filesystem mounted read-only and journald not running — remount rw before editing and remount ro (or sync) before power-cycling, or you will lose the edit or corrupt the filesystem. Anyone with physical access can use these parameters to get root without a password; that is exactly why full-disk encryption matters. On Omarchy the menu entries are unified kernel images, so a cmdline edited at the Limine prompt is only honoured when Secure Boot is off — if it appears to be ignored, boot a snapshot instead.

**Fix.**

Keep the whole record except the no-root-password paragraph and add the mkinitcpio equivalents.

`systemd.unit=rescue.target` is NOT an escape from a locked root account: rescue.service and emergency.service both hand off to `systemd-sulogin-shell`, so rescue mode prompts for the same root password. On Omarchy (root locked, you use sudo) use one of these instead, at the boot menu:

```
systemd.mask=sddm.service 3     # normal boot without a display manager - log in as your own user, then sudo
systemd.debug_shell             # root shell on tty9 with no password (Ctrl+Alt+F9)
init=/bin/bash                  # no systemd at all; root is read-only, remount rw as shown below
```

Once you can boot again, you can make emergency/rescue usable in future without setting a root password (understand that this removes the password gate for anyone with physical access):

```bash
sudo systemctl edit emergency.service   # add:  [Service]\n Environment=SYSTEMD_SULOGIN_FORCE=1
```

And `rd.break` is dracut-only. Omarchy and Arch use mkinitcpio; the equivalents there are:

```
break=premount     stop in the initramfs before root is mounted
break=postmount    stop after root is mounted, before the switch
disablehooks=plymouth   skip one initramfs hook for this boot
```

Everything else — the Limine `e` editor and `cmdline:` line, GRUB `e`/Ctrl+X, systemd-boot `e` (`editor yes` in /boot/loader/loader.conf), the parameter table, the read-only remount dance under init=/bin/bash, and making a parameter stick via /etc/limine-entry-tool.d/99-local.conf plus `sudo limine-mkinitcpio` — is accurate as written.

**Verify.** `cat /proc/cmdline` after booting shows the parameter you added; `systemctl get-default` and `systemctl list-units --failed` work from the rescue shell.

Sources: <https://wiki.archlinux.org/title/Kernel_parameters> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://wiki.archlinux.org/title/Fsck>

---

## Fix "EFI variables are not supported on this system" during grub-install

`grub-install-efi-variables-not-supported` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `manjaro`, `uefi`

**Symptom.** Repairing GRUB from a live USB fails:

```
grub-install: error: cannot find EFI directory.
```
or
```
EFI variables are not supported on this system.
grub-install: error: efibootmgr failed to register the boot entry
```

Afterwards the firmware still boots straight to Windows or to the BIOS setup screen.

**Cause.** The live USB was booted in **legacy/CSM mode**, so the kernel never exposed `efivarfs` and GRUB cannot write a UEFI boot variable. A UEFI installation cannot be repaired from a BIOS-mode live session. Secondarily, `efivarfs` may simply not be mounted in the chroot.

> ⚠️ **Risk.** `grub-install --removable` overwrites `\EFI\BOOT\BOOTX64.EFI` on the ESP. On a shared ESP that is the fallback loader other operating systems (and some firmware) rely on — check what is there first.

**Fix.**

Confirm which mode the live session is in:

```sh
ls /sys/firmware/efi        # if this directory does not exist, you booted in BIOS mode
```

If it is missing: reboot, enter the firmware boot menu, and pick the entry prefixed **UEFI:** for your USB stick. Disable CSM/Legacy boot in the firmware if both entries appear.

If `/sys/firmware/efi` exists but `efivars` is not mounted (common inside a chroot):

```sh
sudo mount -t efivarfs efivarfs /sys/firmware/efi/efivars
```

Then chroot and reinstall GRUB, pointing `--efi-directory` at wherever the ESP is mounted in the installed system:

```sh
sudo arch-chroot /mnt
pacman -S grub efibootmgr
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB
grub-mkconfig -o /boot/grub/grub.cfg
efibootmgr -v          # confirm the GRUB entry now exists
```

If the ESP is at `/boot/efi` instead, use `--efi-directory=/boot/efi`.

On firmware that refuses to keep custom boot variables (many consumer laptops), also install to the removable-media fallback path:

```sh
grub-install --target=x86_64-efi --efi-directory=/boot --removable
```

**Verify.** `efibootmgr -v` lists a `GRUB` entry pointing at `\EFI\GRUB\grubx64.efi`, and the machine boots to the GRUB menu without using the firmware's one-time boot override.

Sources: <https://forum.endeavouros.com/t/endeaveouros-not-booting-anymore-after-2nd-linux-installation/58366> · <https://forum.endeavouros.com/t/solved-grub-not-working-after-installation-previously-ubuntu-partition/5424> · <https://archlinux.org/news/grub-bootloader-upgrade-and-configuration-incompatibilities/>

---

## No snapshot entries in the Limine menu when you need to roll back

`limine-snapshot-entries-missing-from-boot-menu` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `limine`, `omarchy`, `snapper`

**Symptom.** An update broke the system and the Omarchy manual says to pick a snapshot from the boot loader — but the Limine menu only lists "Omarchy" and maybe a fallback entry. No dated snapshot entries at all. Or the machine boots straight to the disk-decryption prompt and never shows Limine. Sometimes `omarchy-snapshot create` printed, and you scrolled past:

```
No Snapper configs found, so no snapshot was created.
Configure Snapper with: sudo bash -euo pipefail "/usr/share/omarchy/install/config/snapper.sh"
```

**Cause.** Four independent things must all be true for snapshot entries to appear: snapper must have a `root` config, `limine-snapper-sync.service` must be running, `/boot/limine.conf` must still contain the `//Snapshots` (or `/Snapshots`) keyword that tells the tool where to write entries, and the ESP must have room. Any of them silently produces an empty snapshot list. On Omarchy 4 the keyword is placed by `limine-entry-tool` from `BOOT_ORDER="*, *fallback, Snapshots"` in `/etc/limine-entry-tool.d/omarchy-defaults.conf`, so it survives every kernel update. It goes missing when `/boot/limine.conf` is hand-edited, restored from an old copy, or left empty by a power cut mid-write (FAT32 has no journal). Separately, Omarchy's Setup > Direct Boot adds an EFI entry that jumps past Limine entirely, so the menu is never shown even when the entries exist.

> **Audit corrected this record.** Checked on this Omarchy 4 machine (omarchy-settings 4.0.2-1, limine-snapper-sync 1.31.0-1, limine-mkinitcpio-hook 1.37.1-1) and against the quattro tree and the upstream READMEs. What held: the quoted omarchy-snapshot message is verbatim from /usr/share/omarchy/bin/omarchy-snapshot (identical to quattro), install/config/snapper.sh installs default/snapper/root (NUMBER_LIMIT=5, TIMELINE_CREATE=no) and enables snapper-cleanup.timer plus limine-snapper-sync.service, the service is enabled and running here, limine-snapper-sync/-list/-info/-restore all exist in /usr/bin, the //Snapshots or /Snapshots keyword is documented in the Arch wiki Limine page and the limine-snapper-sync README, MAX_SNAPSHOT_ENTRIES=6 is in /etc/limine-entry-tool.d/omarchy-defaults.conf (owned by omarchy-settings) and PR 6175 shows the value in that drop-in is what limine-snapper-sync reads, ESP_PATH=/boot is in the installer-written /etc/default/limine and in quattro default/limine/default.conf, the probe order /efi, /boot, /boot/efi, /limine is in limine-common-functions, and Direct Boot bypassing the menu is in manual/47-system-snapshots.md and omarchy-setup-direct-boot. Three things were wrong. First, the fix runs `sudo omarchy-refresh-limine`: the script reads $OMARCHY_PATH, which is exported by default/bash/env-bootstrap and not by any sudoers env_keep (the four files in etc/sudoers.d were read), and sudo's env_reset is on by default, so under sudo the `cp "$OMARCHY_PATH/default/limine/limine.conf"` step fails after the live config has already been moved to limine.conf.bak. The script is marked requires-sudo and calls sudo itself, so it must be run bare. Second, the cause claims omarchy-refresh-limine can drop the keyword. It does the opposite, because limine-update regenerates the OS entry under BOOT_ORDER="*, *fallback, Snapshots" and the script then runs limine-snapper-sync. Third, /boot is mounted dmask=0077 here (findmnt and fstab), so the unprivileged `grep /boot/limine.conf` in step 3 prints Permission denied rather than nothing, and LIMIT_USAGE_PERCENT=85 lives in /etc/limine-snapper-sync.conf, which the config grep did not include. Also corrected: with a numeric MAX_SNAPSHOT_ENTRIES the usage limit stops new entries being added, and trimming on usage is the `auto` behaviour (both from the shipped conf comments). limine-snapper-list was confirmed to work without sudo here. Not exercised: omarchy-refresh-limine itself, a restore, Direct Boot, and the contents of /boot/limine.conf (unreadable without root).
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy-refresh-limine` overwrites /boot/limine.conf wholesale (old file kept as /boot/limine.conf.bak). `limine-update` re-adds systemd-boot, rEFInd and the default EFI loader if present (`FIND_BOOTLOADERS=yes`) but not a Windows entry added with `limine-scan`, so re-run `limine-scan` afterwards. Do not prefix it with `sudo`: sudo drops `$OMARCHY_PATH`, the template copy fails after the live config has been moved aside, and you boot from a config regenerated without Omarchy's header (no branding, default timeout, `default_entry` reset). Snapshot restore replaces the root subvolume but not /home and not ~/.config, so a rollback can leave newer config formats in place. Each snapshot entry costs a kernel plus initramfs/UKI on the ESP, and raising MAX_SNAPSHOT_ENTRIES on a small ESP can fill /boot and break the next kernel upgrade. Snapshots created before limine-snapper-sync was installed cannot be made bootable.

**Fix.**

Work through the four preconditions in order.

**1. Does snapper have a config?**

```bash
sudo snapper --csvout list-configs
sudo snapper -c root list
```

If empty, create it with Omarchy's shipped policy (5 snapshots, no timeline):

```bash
sudo bash -euo pipefail /usr/share/omarchy/install/config/snapper.sh
```

**2. Is the sync service running?**

```bash
systemctl status limine-snapper-sync.service
sudo systemctl enable --now limine-snapper-sync.service
```

**3. Does limine.conf still have the placeholder?** On Omarchy 4 `/boot` is mounted with `dmask=0077`, so this needs root or it prints `Permission denied` instead of the line:

```bash
sudo grep -nE '^[[:space:]]*/{1,2}Snapshots' /boot/limine.conf
```

If that prints nothing on Omarchy 4, regenerate the config. Run this **without** `sudo` in front: the script calls `sudo` itself and needs `$OMARCHY_PATH`, which sudo strips, and with it stripped the script moves your config aside and then fails to copy the template. It keeps the old file as `/boot/limine.conf.bak`, copies Omarchy's header, then runs `limine-update` (which rewrites the OS entry and the `Snapshots` placeholder) and `limine-snapper-sync`:

```bash
omarchy-refresh-limine
```

On plain Arch, add the keyword by hand inside the OS entry:

```
/+Arch Linux
    //Linux
    protocol: linux
    path: boot():/vmlinuz-linux
    cmdline: root=UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx rw rootflags=subvol=/@
    module_path: boot():/initramfs-linux.img

    //Snapshots
```

**4. Sync and inspect:**

```bash
sudo limine-snapper-sync
limine-snapper-list        # works without sudo
sudo limine-snapper-info    # shows bootable snapshot count and flags missing/corrupt kernels
```

Check the caps if fewer snapshots show than exist. With a numeric `MAX_SNAPSHOT_ENTRIES` (Omarchy ships 6, one above snapper's `NUMBER_LIMIT=5` so the freshly created sixth is not reported as an overflow) no entry beyond the cap is written, and once the ESP crosses `LIMIT_USAGE_PERCENT` (default 85) no new entries are added at all. With `MAX_SNAPSHOT_ENTRIES=auto` older entries are trimmed instead, without warning. `/etc/default/limine` overrides everything else:

```bash
grep -nE 'ESP_PATH|MAX_SNAPSHOT_ENTRIES|LIMIT_USAGE_PERCENT' /etc/default/limine /etc/limine-entry-tool.d/*.conf /etc/limine-snapper-sync.conf
df -h /boot
```

If `ESP_PATH` is unset the tool probes `/efi`, `/boot`, `/boot/efi`, `/limine`. Omarchy's installer writes `ESP_PATH="/boot"` into `/etc/default/limine`.

**Test end to end before you need it:**

```bash
omarchy-snapshot create
limine-snapper-list         # the new snapshot must appear
```

**If the menu never appears at all**, Direct Boot is on. Run Setup > Direct Boot from the Omarchy menu again to remove the EFI entry, or press the firmware's boot-device key at power-on and pick Limine manually.

To restore from a snapshot once you can boot one: click the notification that appears inside the snapshot, or run `omarchy-snapshot restore` / `sudo limine-snapper-restore`.

**Verify.** `limine-snapper-list` shows dated entries, `sudo limine-snapper-info` reports a non-zero bootable snapshot count with kernels verified, and the entries are visible under "Snapshots" in the Limine menu at the next reboot.

Sources: <https://wiki.archlinux.org/title/Limine> · <https://gitlab.com/Zesko/limine-snapper-sync> · <https://github.com/basecamp/omarchy/blob/quattro/install/config/snapper.sh> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-snapshot> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-limine> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://github.com/basecamp/omarchy/blob/quattro/manual/47-system-snapshots.md> · <https://wiki.archlinux.org/title/Snapper> · <https://gitlab.com/Zesko/limine-snapper-sync/-/blob/master/README.md> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-setup-direct-boot> · <https://github.com/basecamp/omarchy/blob/quattro/default/limine/default.conf> · <https://github.com/basecamp/omarchy/blob/quattro/default/limine/limine.conf> · <https://github.com/basecamp/omarchy/blob/quattro/default/bash/env-bootstrap> · <https://github.com/basecamp/omarchy/blob/quattro/manual/50-dual-boot-install.md> · <https://github.com/omacom/omarchy/pull/6175> · <https://aur.archlinux.org/rpc/v5/info?arg[]=limine-snapper-sync&arg[]=limine-mkinitcpio-hook>

---

## Fix the linux-firmware split: "exists in filesystem" blocks the upgrade

`linux-firmware-split-exists-in-filesystem` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `intel`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** `sudo pacman -Syu` refuses to proceed, leaving the system on old firmware (and, if the kernel already updated in a previous partial run, potentially unbootable):

```
error: failed to commit transaction (conflicting files)
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad103 exists in filesystem
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad104 exists in filesystem
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad106 exists in filesystem
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad107 exists in filesystem
Errors occurred, no packages were upgraded.
```

**Cause.** In `linux-firmware 20250613.12fe085f-5` (Arch news, 2025-06-21) upstream Arch split the monolithic `linux-firmware` package into vendor packages (`linux-firmware-amdgpu`, `-atheros`, `-broadcom`, `-cirrus`, `-intel`, `-mediatek`, `-nvidia`, `-other`, `-radeon`, `-realtek`, plus `-whence` and optional `-liquidio`, `-marvell`, `-mellanox`, `-nfp`, `-qcom`, `-qlogic`), leaving `linux-firmware` as an empty package that depends on the default set. The same release picked up upstream's reorganised NVIDIA firmware symlink layout (`ad103`, `ad104`, `ad106` and `ad107` became symlinks to `ad102`). pacman cannot replace the old directories with the new package's symlinks, so the transaction aborts with conflicting files.

This fires only when the installed `linux-firmware` is `20250508.788aadc8-2` or older, meaning the machine has not updated since June 2025. Any Arch or Omarchy install made after that date already has the split and never sees it. On Omarchy, `omarchy update` runs the same `pacman -Syu` and its conflict handler only clears files under Omarchy's own package names, so the update ends with "Something went wrong during the update" and the firmware conflict printed above it.

> **Audit corrected this record.** The news item is https://archlinux.org/news/linux-firmware-2025061312fe085f-5-upgrade-requires-manual-intervention/ (2025-06-21, Jan Alexander Steffens), fetched as HTML. It gives exactly the two commands the record quotes and adds a scope the record omits: the conflict fires only when upgrading from linux-firmware 20250508.788aadc8-2 or earlier, and the four error lines in the symptom are reproduced verbatim from it. The split is confirmed current on this machine: pacman -Q shows linux-firmware 20260810-2 as an empty package depending on linux-firmware-amdgpu, -atheros, -broadcom, -cirrus, -intel, -mediatek, -nvidia, -other, -radeon, -realtek, with -whence installed and liquidio, marvell, mellanox, nfp, qcom, qlogic as optdepends, matching the core/any/linux-firmware JSON and the packaging .SRCINFO. /usr/lib/firmware/nvidia/ad103 through ad107 are symlinks to ad102 owned by linux-firmware-nvidia here, which is the layout change the news describes. Two things were wrong for Omarchy 4. First, the second command, pacman -Syu linux-firmware, is refused by /usr/share/libalpm/hooks/00-omarchy-update-guard.hook, whose /usr/bin/omarchy-update-pacman-guard exits 1 whenever the pacman command line carries both S and u unless OMARCHY_ALLOW_DIRECT_PACMAN=1 or OMARCHY_UPDATE_PACMAN=1 is set (read on this machine). The first command, pacman -Rdd, is a Remove operation and the hook only triggers on Operation = Upgrade, so it runs untouched. Second, routing the reinstall through omarchy update instead would leave the machine without firmware: pacman -Qii linux-firmware shows Required By none and only Optional For linux, so a plain -Syu never pulls it back, and omarchy-update-system-pkgs-when-conflicted only clears exists-in-filesystem lines whose package is omarchy, omarchy-dev, omarchy-settings or omarchy-settings-dev, so omarchy update cannot resolve the linux-firmware-nvidia conflict either. The manual initramfs rebuild is redundant on both platforms: 90-mkinitcpio-install.hook (Omarchy overrides it with /etc/pacman.d/hooks/90-mkinitcpio-install.hook from limine-mkinitcpio-hook, running limine-mkinitcpio-install) triggers on usr/lib/firmware/*, so the transaction rebuilds the initramfs or UKI itself. On Omarchy, mkinitcpio -P goes through the /usr/local/bin/mkinitcpio wrapper, which warns that it does not update Limine entries and offers limine-mkinitcpio. The problem is historical for any install made after June 2025: every Omarchy 4 ISO ships the split already, so a fresh install never sees it, but an older Omarchy or Arch machine that last updated before 2025-06-21 hits it on its next update, and omarchy update reports it as a failed transaction. The remedy itself was not exercised: no machine here has a pre-split linux-firmware to upgrade from.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Between `pacman -Rdd linux-firmware` and the reinstall your system has NO firmware files in /usr/lib/firmware. Do not reboot, suspend, or let the machine lose power in that window — you would boot without GPU/Wi-Fi firmware and possibly without a usable display.

**Fix.**

Arch's news item gives the two-step remedy: remove the old package without touching dependents, then reinstall it as part of a full upgrade. Do **not** reboot between the two commands.

**Plain Arch / EndeavourOS / CachyOS:**

```sh
sudo pacman -Rdd linux-firmware
sudo pacman -Syu linux-firmware
```

**Omarchy 4:** the first command is a remove and passes Omarchy's pacman guard, but the second is a `-Syu` and the guard refuses it. Bypass the guard for that one transaction:

```sh
sudo pacman -Rdd linux-firmware
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu linux-firmware
```

Do not substitute `omarchy update` for the second step. Nothing depends on `linux-firmware` (the kernel lists it only as an optional dependency), so a plain system upgrade after `-Rdd` leaves the machine with no firmware installed. Name the package explicitly.

`-Rdd` removes the package without checking dependencies and without running its scripts, so the firmware files are absent until the second command completes. The reinstall pulls in the new vendor packages, and the `mkinitcpio` pacman hook (on Omarchy, `limine-mkinitcpio-hook`'s version, which rebuilds the UKI) triggers on `usr/lib/firmware/*`, so the initramfs is rebuilt inside the same transaction. Watch for `Updating linux initcpios...` in the output. Only if that line is missing, rebuild by hand:

```sh
sudo mkinitcpio -P        # Arch / EndeavourOS / CachyOS
sudo limine-mkinitcpio    # Omarchy 4 (mkinitcpio -P alone does not update the Limine UKI)
```

**Verify.** `pacman -Qs linux-firmware` lists the new vendor packages (e.g. `linux-firmware-nvidia`, `linux-firmware-amdgpu`, `linux-firmware-intel`), and `sudo pacman -Syu` completes with no conflicting-files error.

Sources: <https://archlinux.org/news/linux-firmware-2025061312fe085f-5-upgrade-requires-manual-intervention/> · <https://archlinux.org/news/> · <https://archlinux.org/feeds/news/> · <https://archlinux.org/packages/core/any/linux-firmware/json/> · <https://gitlab.archlinux.org/archlinux/packaging/packages/linux-firmware/-/raw/main/.SRCINFO> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-pacman-guard> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-system-pkgs> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-system-pkgs-when-conflicted>

---

## An ignored .pacnew for mkinitcpio.conf or the boot loader config breaks the next boot

`mkinitcpio-pacnew-unhandled-breaks-next-boot` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `luks`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** An upgrade prints, somewhere in a long transcript:

```
warning: /etc/mkinitcpio.conf installed as /etc/mkinitcpio.conf.pacnew
warning: /etc/mkinitcpio.conf.d/omarchy_hooks.conf installed as /etc/mkinitcpio.conf.d/omarchy_hooks.conf.pacnew
warning: /etc/limine-entry-tool.conf installed as /etc/limine-entry-tool.conf.pacnew
```

Nothing breaks that day. Weeks later a kernel update rebuilds the initramfs and the machine drops to an emergency shell, or the LUKS prompt never appears, or the root device is not found. The file that is actually read no longer matches what the current package expects: a renamed hook, a changed default, a new required entry. Users also break it the other way round by running `mv /etc/mkinitcpio.conf.pacnew /etc/mkinitcpio.conf` on plain Arch, or by overwriting `omarchy_hooks.conf` with its `.pacnew` on Omarchy, which silently deletes whatever hook they had added by hand. You only see these warnings for files you edited: on a stock Omarchy 4 install all three are `[unmodified]` and pacman replaces them in place.

**Cause.** pacman never merges configuration. When a package ships a new version of a file you have edited, it writes `.pacnew` alongside and leaves yours untouched. The files that decide whether this machine can boot are exactly such files. On plain Arch that is `/etc/mkinitcpio.conf` (from `mkinitcpio`). On Omarchy 4 the hook list lives in `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` (a backup file of `omarchy-settings`), and the Limine entry template is `/etc/limine-entry-tool.conf` (from `limine-mkinitcpio-hook`). `/etc/default/limine` is the user copy that template tells you to make, is owned by no package, and never gets a `.pacnew`. Because the damage only surfaces at the next initramfs rebuild, the cause and the symptom can be a month apart.

> **Audit corrected this record.** Re-audited on 2026-09-06 after the record was exercised on a real Omarchy 4.0.1 VM (research/validation/, 6/6 assertions pass) and checked again on a 4.0.2 workstation with pacman -Qo, pacman -Qii and pacman -Qkk. The remediation (pacdiff, merge never overwrite, rebuild with limine-mkinitcpio and read the output, keep changes in drop-ins) is confirmed on the machine itself: /usr/local/bin/mkinitcpio is a wrapper from limine-mkinitcpio-hook that warns it does not update Limine entries. Three claims were wrong for Omarchy 4. The symptom quoted a .pacnew for /etc/default/limine, but no package owns that file (pacman -Qo errors), so pacman can never write one for it. The package-owned file is /etc/limine-entry-tool.conf, from limine-mkinitcpio-hook, whose header says to copy it to /etc/default/limine and edit the copy. The cause repeated the same error and named limine-entry-tool as the owner. The danger said overwriting /etc/mkinitcpio.conf with its .pacnew removes the encrypt, plymouth and btrfs-overlayfs hooks. On Omarchy 4 it does not: those hooks are assigned wholesale by /etc/mkinitcpio.conf.d/omarchy_hooks.conf, a backup file of omarchy-settings that mkinitcpio reads after the main file, and the effective HOOKS measured on the VM did not change whatever was done to mkinitcpio.conf. Also, a stock install leaves /etc/mkinitcpio.conf [unmodified], so the .pacnew only appears if you edited it. The file on Omarchy 4 that can both get a .pacnew and carry the hook list is omarchy_hooks.conf itself. Symptom, cause and danger rewritten to name the right files. The fix stands as written.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** On plain Arch, overwriting `/etc/mkinitcpio.conf` with the `.pacnew` removes your encryption, plymouth and btrfs hooks and produces an initramfs that cannot open or find the root device: an unbootable machine. On Omarchy 4 the hook list is assigned by `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, which mkinitcpio reads after the main file, so replacing `mkinitcpio.conf` does not touch the hooks, but overwriting `omarchy_hooks.conf` with its `.pacnew` drops any hook you added to it by hand. Merge, rebuild, and confirm the rebuild succeeded before you reboot. Keep a fallback boot entry, an LTS kernel, or a working snapshot available while you do this. Deleting a `.pacsave` loses the only copy of a config from a package you removed.

**Fix.**

Find every outstanding file:

```bash
sudo pacman -S --needed pacman-contrib
sudo find /etc -name '*.pacnew' -o -name '*.pacsave'
grep -E '\.pacnew|\.pacsave' /var/log/pacman.log | tail -20
```

Merge them interactively rather than replacing:

```bash
sudo DIFFPROG="nvim -d" pacdiff
# or, with a plain pager first:
sudo pacdiff --output
```

In `pacdiff`, `v` views the diff, `m` merges, `o` overwrites with the new file, `r` removes the .pacnew, `s` skips. For boot-critical files always `m`, never blindly `o`.

**After touching anything under `/etc/mkinitcpio.conf*`, `/etc/default/limine`, or `/etc/limine-entry-tool.d/`, rebuild immediately and read the output — do not reboot on faith:**

```bash
sudo limine-mkinitcpio      # Omarchy 4 / Limine + UKI: rebuilds AND installs the UKI
# plain Arch:
sudo mkinitcpio -P
sudo limine-update          # or: bootctl update / grub-mkconfig -o /boot/grub/grub.cfg
```

There must be no `ERROR: Hook '...' cannot be found`, no `module not found:`, and the run must end with `Image generation successful` (or `Unified kernel image generation successful` with no `skipping` line after it).

**Stop it recurring: never edit the package-owned files.** mkinitcpio reads `/etc/mkinitcpio.conf.d/*.conf` after the main file and those drop-ins take precedence, so put your changes in a file no package owns:

```
# /etc/mkinitcpio.conf.d/99-local.conf
MODULES+=(vfat nls_cp437)
FILES+=(/etc/vconsole.conf)
```

Same idea for kernel parameters on Omarchy:

```
# /etc/limine-entry-tool.d/99-local.conf
KERNEL_CMDLINE[default]+=" amdgpu.dcdebugmask=0x10"
```

For reference, Omarchy 4 ships its hooks in the package-owned `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`:

```
HOOKS=(base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs)
```

Do not copy that line into your own drop-in — a later-sorting drop-in that assigns `HOOKS=` replaces it wholesale, and you will silently lose whatever Omarchy adds in a future release. Use `+=` on `MODULES`/`FILES`, and leave `HOOKS` to the packaged file.

**Verify.** `sudo find /etc -name '*.pacnew'` returns nothing; `sudo limine-mkinitcpio` (or `mkinitcpio -P`) completes with no ERROR lines; `grep -R HOOKS /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/` shows encrypt/plymouth/filesystems still present if you use them.

Sources: <https://wiki.archlinux.org/title/Pacman/Pacnew_and_Pacsave> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://wiki.archlinux.org/title/Mkinitcpio> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/blob/quattro/etc/mkinitcpio.conf.d/omarchy_hooks.conf> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio>

---

## Roll back to a working kernel (pacman cache, linux-lts, or an Omarchy snapshot)

`rollback-kernel-after-bad-update` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `grub`, `limine`, `manjaro`, `nvidia`, `omarchy`, `systemd-boot`

**Symptom.** A kernel update boots to a black screen, a panic, or breaks the GPU/Wi-Fi, and you need the previous kernel back. On plain Arch there is no second kernel in the menu because only one is installed.

**Cause.** Arch keeps only the currently installed kernel in `/boot`; the previous version is gone the moment the package upgrades. Without `linux-lts` or a snapshot you have nothing to fall back to.

> **Audit corrected this record.** All three options are real: `pacman -U` from cache, `downgrade` exists in the AUR, `linux-lts` is in core (6.18.47), and `omarchy-snapshot create|restore` is genuine — I read the script and restore calls `sudo limine-snapper-restore`. But two gaps matter for a machine that is currently unbootable. The cache may be empty: `paccache` runs from a systemd timer on many installs and Omarchy prunes packages during updates, so `ls /var/cache/pacman/pkg/linux-*` frequently returns nothing and the record offers no fallback (the Arch Linux Archive). And `IgnorePkg = linux linux-headers` pins the kernel while everything else keeps moving forward — that is a deliberate partial upgrade, which will eventually break DKMS and out-of-tree modules; it needs a warning and needs the DKMS/nvidia packages considered alongside.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Downgrading `linux` without downgrading DKMS modules (nvidia-dkms, virtualbox-host-dkms, zfs) is itself a partial upgrade and can leave you with no GPU driver — rebuild them after the downgrade. Omarchy snapshot restore only rolls back the system root: /home and ~/.config are deliberately left untouched, so newer config formats may not match the older packages. Leaving `IgnorePkg = linux` in place indefinitely will eventually desync your kernel from the rest of the system.

**Fix.**

**Option 1 — reinstall the previous package** (chroot from a live USB if you cannot boot):

```sh
ls -1 /var/cache/pacman/pkg/linux-*.pkg.tar.zst
```

If the cache has been pruned by `paccache`/an update and that returns nothing, pull the exact version from the Arch Linux Archive instead:

```sh
curl -O https://archive.archlinux.org/packages/l/linux/linux-6.15.4.arch1-1-x86_64.pkg.tar.zst
```

Downgrade the kernel and its headers **together**, then rebuild:

```sh
sudo pacman -U ./linux-6.15.4.arch1-1-x86_64.pkg.tar.zst \
               ./linux-headers-6.15.4.arch1-1-x86_64.pkg.tar.zst
sudo mkinitcpio -P
sudo dkms autoinstall        # rebuild nvidia/vbox/zfs against the older kernel
```

Pin it so the next `-Syu` does not undo the rollback — in the `[options]` section of `/etc/pacman.conf`:

```
IgnorePkg = linux linux-headers
```

This is a deliberate partial upgrade: the rest of the system moves on while the kernel does not, and DKMS/out-of-tree modules will eventually stop matching. Treat it as temporary and remove the line as soon as a fixed kernel ships.

EndeavourOS (and anyone with the AUR `downgrade` helper) can automate the cache/ALA lookup:

```sh
sudo downgrade linux linux-headers
```

**Option 2 — install the LTS kernel as a permanent escape hatch** (do this *before* you need it):

```sh
sudo pacman -S linux-lts linux-lts-headers
sudo mkinitcpio -P
sudo grub-mkconfig -o /boot/grub/grub.cfg    # GRUB
sudo limine-mkinitcpio                        # Omarchy/Limine
sudo bootctl list                             # systemd-boot: confirm the new entry
```

**Option 3 — Omarchy snapshot rollback.** Omarchy snapshots via snapper on every update. Pick the snapshot by date/version in the Limine menu and boot it, then:

```sh
omarchy-snapshot restore     # calls limine-snapper-restore
```

Take one manually before a risky change:

```sh
omarchy-snapshot create      # no-op if snapper is unconfigured -- check its output
```

**Verify.** `uname -r` reports the older/LTS kernel after reboot and the broken behaviour is gone. `pacman -Q linux linux-lts` shows what is installed.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/101/system-snapshots> · <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting> · <https://forum.endeavouros.com/t/boot-failure-due-to-amd-gpu/72796> · <https://man.archlinux.org/man/mkinitcpio.8>

---

## Fix Secure Boot "Verification failed: (0x1A) Security Violation" with sbctl

`secure-boot-violation-sbctl` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `secure-boot`, `systemd-boot`, `uefi`

**Symptom.** With Secure Boot enabled the firmware refuses to launch the bootloader:

```
Verification failed: (0x1A) Security Violation
```

or the machine silently falls back to the firmware setup / Windows. Turning Secure Boot off in the BIOS makes Linux boot again.

**Cause.** GRUB/systemd-boot/Limine as shipped by Arch are unsigned, and the kernel is unsigned. The firmware's default key database (Microsoft KEK/db) does not vouch for them, so the UEFI image is rejected. There is no shim by default on Arch.

> **Audit corrected this record.** I verified every sbctl subcommand and flag against sbctl(8): create-keys, enroll-keys with -m/--microsoft, sign with -s/--save, verify, list-files, list-enrolled-keys, status all exist as written, and sbctl is in extra (0.18). Two fixes needed. The Limine signing path is wrong — the limine package ships usr/share/limine/BOOTX64.EFI and there is no limine.efi, so `sbctl sign -s /boot/EFI/limine/limine.efi` fails on a nonexistent file. And the record omits sbctl's own prominent warning: some devices ship signed firmware/option ROMs that are validated under Secure Boot, and enrolling keys without Microsoft's certificates can brick them. That warning belongs next to the enroll command, not nowhere.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** BRICKING RISK. `sbctl enroll-keys` without `-m` (Microsoft keys) can leave some laptops unable to run signed option ROMs (discrete GPU, Thunderbolt) or unable to boot Windows; a small number of firmwares handle custom PK enrollment badly. Always use `-m` on a dual-boot or OEM laptop, keep Secure Boot disabled until `sbctl verify` is clean, and know how to reset keys to factory defaults in your firmware setup.

**Fix.**

Put the firmware into **Setup Mode** (BIOS: Secure Boot -> Erase/Clear all keys, or 'Reset to Setup Mode'). Then:

```sh
sudo pacman -S sbctl
sudo sbctl status                 # expect: Setup Mode: Enabled
sudo sbctl create-keys
sudo sbctl enroll-keys -m         # -m is not optional in practice
```

**Keep the `-m`.** sbctl(8) warns that some devices have signed firmware/option ROMs validated when Secure Boot is on; enrolling only your own keys without Microsoft's certificates can leave the machine unable to initialise its own hardware. If your firmware has no 'reset to factory keys' option, you have no way back.

Find what actually needs signing rather than guessing paths — the Limine binary is named `BOOTX64.EFI`, not `limine.efi`:

```sh
sudo find /boot -iname '*.efi' -o -name 'vmlinuz-*'
```

Sign each real file, `-s` to register it so pacman hooks re-sign on update:

```sh
sudo sbctl sign -s /boot/vmlinuz-linux
sudo sbctl sign -s /boot/EFI/BOOT/BOOTX64.EFI
sudo sbctl sign -s /boot/EFI/GRUB/grubx64.efi                # GRUB
sudo sbctl sign -s /boot/EFI/systemd/systemd-bootx64.efi     # systemd-boot
sudo sbctl sign -s /boot/EFI/limine/BOOTX64.EFI              # Limine
for f in /boot/EFI/Linux/*.efi; do sudo sbctl sign -s "$f"; done   # UKIs (Omarchy)
```

Verify **before** re-enabling Secure Boot — an unsigned binary here means the machine will not boot:

```sh
sudo sbctl verify
sudo sbctl list-files
sudo sbctl list-enrolled-keys
```

On Omarchy, `limine-mkinitcpio-hook` optdepends on sbctl and re-signs UKIs automatically once they are registered.

After re-enabling Secure Boot, `sudo sbctl status` should show `Secure Boot: Enabled`, `Setup Mode: Disabled`.

If you just want to move on: disable Secure Boot in firmware and stop there — nothing on an Arch system requires it.

**Verify.** `sudo sbctl status` shows Secure Boot enabled with your keys enrolled, `sudo sbctl verify` reports every file signed, and the machine boots with Secure Boot on.

Sources: <https://github.com/Foxboron/sbctl> · <https://man.archlinux.org/man/bootctl.1>

---

## systemd-boot still lists the old kernel after an update

`systemd-boot-entries-not-updated-after-kernel` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `systemd-boot`, `uefi`

**Symptom.** You update, reboot, and land in an emergency shell. `bootctl list` shows only the *previous* kernel version even though the new initramfs was generated correctly:

```
type: Boot Loader Specification Type #1 (.conf)
title: Arch Linux
version: 6.1.1-arch1-1        <-- stale
```

**Cause.** On distros that use `kernel-install` to write versioned entries into `/efi/loader/entries/`, removing or shadowing the package that provides the kernel-install plugin - `kernel-install-for-dracut`, which `eos-dracut` and `mkinitcpio-archiso` conflict with - stops entries being regenerated on kernel upgrade. Note there is no standalone `kernel-install` package on Arch: the binary ships inside `systemd`. Separately, the systemd-boot EFI binary itself is not auto-updated when the `systemd` package updates unless the update service is enabled.

> **Audit corrected this record.** `sudo pacman -S kernel-install` fails — I searched the Arch package database for name=kernel-install and got zero matches. On Arch the kernel-install binary is shipped inside the `systemd` package; the EndeavourOS package the record is really thinking of is `kernel-install-for-dracut`. Pasting the given command into a root shell on a machine that is already one bad boot away from unusable just errors out. Separately, `pacman -R mkinitcpio-archiso eos-dracut` aborts the entire transaction if either package is absent, so the 'if present' caveat needs to be in the command, not the prose. The bootctl update / systemd-boot-update.service half is correct.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `bootctl install` (as opposed to `update`) rewrites `\EFI\BOOT\BOOTX64.EFI` on the ESP. On a dual-boot machine that can displace another loader — prefer `bootctl update` when systemd-boot is already installed.

**Fix.**

Boot the old entry (it still works) or chroot from a live USB, then:

```sh
# remove conflicting packages, only the ones actually installed
for p in mkinitcpio-archiso eos-dracut; do pacman -Qq "$p" &>/dev/null && sudo pacman -R "$p"; done
```

There is **no `kernel-install` package in the Arch repos** — the binary comes from `systemd`. Check what you have:

```sh
command -v kernel-install && pacman -Qo "$(command -v kernel-install)"
```

- On Arch: reinstall `systemd` if the binary is missing (`sudo pacman -S systemd`).
- On EndeavourOS with dracut: the entry generator is `kernel-install-for-dracut` (`sudo pacman -S kernel-install-for-dracut`).

Force regeneration and confirm:

```sh
sudo pacman -S linux
bootctl list        # must now show the NEW version before you reboot
```

Keep the systemd-boot binary on the ESP in sync with the `systemd` package:

```sh
sudo bootctl update
sudo systemctl enable systemd-boot-update.service
```

If you write entries by hand (plain Arch + mkinitcpio), use **unversioned** paths so they never go stale — `/boot/loader/entries/arch.conf`:

```
title   Arch Linux
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=UUID=xxxx-xxxx rw
```

and keep a fallback entry pointing at `/initramfs-linux-fallback.img`.

**Verify.** `bootctl list` shows the current kernel version, `bootctl status` reports the ESP loader version matching `pacman -Q systemd`, and a reboot lands in the new kernel (`uname -r`).

Sources: <https://forum.endeavouros.com/t/systemd-boot-not-generating-new-initramfs-when-updating-kernel/36592> · <https://man.archlinux.org/man/bootctl.1>

---

## Restore Linux boot priority after a Windows update hijacks the UEFI boot order

`windows-update-takes-over-uefi-boot-order` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `dual-boot`, `endeavouros`, `grub`, `limine`, `manjaro`, `omarchy`, `systemd-boot`, `uefi`, `windows`

**Symptom.** The machine booted GRUB/Limine fine for months; after a Windows feature update (or a BIOS update, or a CMOS reset) it now boots straight into Windows, or shows `grub rescue>`. The Linux entry is still in the firmware's boot list but sits below Windows Boot Manager.

**Cause.** Windows Setup writes `\EFI\Microsoft\Boot\bootmgfw.efi` and pushes `Windows Boot Manager` to the front of the UEFI `BootOrder` variable. Some firmware also rewrites `\EFI\BOOT\BOOTX64.EFI` (the removable fallback), clobbering a Linux loader that was installed there.

> **Audit corrected this record.** The efibootmgr diagnosis and `-o` reordering are correct. The manual entry-creation example names a loader file that does not exist: I checked the file list of the `limine` package (extra, 12.6.1) and it ships `usr/share/limine/BOOTX64.EFI` — there is no `limine.efi`. Omarchy's own scripts reference `/boot/EFI/limine/` and `/boot/EFI/BOOT/`, both holding BOOTX64.EFI. A user pasting `--loader '\EFI\limine\limine.efi'` creates a boot entry pointing at nothing, which on many firmwares is worse than the original problem.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `efibootmgr` writes NVRAM. A malformed `--create` can leave a dead entry; on a handful of buggy laptop firmwares, filling NVRAM with entries has caused firmware corruption. Delete stale entries with `efibootmgr -b XXXX -B` rather than accumulating them.

**Fix.**

Boot Linux via the firmware's one-time boot menu (F12/F11/Esc), then inspect:

```sh
sudo efibootmgr -v
```

Put your Linux loader first (use the numbers from *your* output):

```sh
sudo efibootmgr -o 0002,0000
```

If the Linux entry is missing entirely, recreate it:

```sh
# GRUB
sudo grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB

# systemd-boot
sudo bootctl install

# Limine: confirm the real filename first — it is BOOTX64.EFI, not limine.efi
sudo find /boot/EFI -iname '*.efi'
sudo efibootmgr --create --disk /dev/nvme0n1 --part 1 \
  --label "Limine" --loader '\EFI\limine\BOOTX64.EFI'
```

On Omarchy prefer the supported path, which rewrites the NVRAM entry for you:

```sh
sudo limine-mkinitcpio
```

Then verify with `sudo efibootmgr -v` that the new entry's File() path matches a file that actually exists before rebooting.

**Verify.** `sudo efibootmgr | head -3` shows `BootOrder:` beginning with your Linux entry, and a cold boot lands on the Linux boot menu.

Sources: <https://forum.endeavouros.com/t/win-11-bootloader-restores-precedence-over-grub/39801> · <https://forum.endeavouros.com/t/upgrade-to-windows-11-24h2/75367> · <https://man.archlinux.org/man/bootctl.1>

---

## Live installer USB: "ERROR: Device '<label>' not found" right after the bootloader

`archiso-usb-device-not-found-installer` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `installer`, `laptop`, `omarchy`

**Symptom.** Booting the Omarchy/Arch installer USB, the bootloader loads the kernel and then the initramfs cannot find the medium it just came from:

```
:: running hook [archiso]
Waiting 30 seconds for device /dev/disk/by-label/2026-08-25-11-17-12-00 ...
ERROR: Device '2026-08-25-11-17-12-00' not found. Skipping fsck.
You are now being dropped into an emergency shell.
```

Keyboard input in that shell is sluggish and drops characters. Reported on a ThinkPad T14 (basecamp/omarchy#8454).

**Cause.** A USB/xHCI enumeration handoff problem between the firmware and the kernel: the stick is present to the bootloader, but after the kernel takes over the xHCI controller the device is either not re-enumerated or is not present under `/dev/disk/by-uuid` in time, so the archiso hook's search for the boot medium times out. Current archiso locates the medium by `archisosearchuuid=`/`archisosearchfilename=` (the older `archisolabel=` label search is gone), so the wait is on the by-uuid symlink appearing. The image itself is fine.

> **Audit corrected this record.** Issue 8454 is real and the replug workaround is exactly what the reporter confirms. But the issue's own quoted cmdline uses `archisosearchuuid=` and waits on /dev/disk/by-uuid — current archiso replaced `archisolabel=` with archisosearchuuid=/archisosearchfilename=, so the suggested `archisolabel=<LABEL>` line is obsolete and will not be honoured. `copytoram` is also the wrong tool for this failure: copytoram runs *after* the medium is located, so it cannot rescue a device that is never found — it helps only once boot already works. And `dd of=/dev/sdX` is offered with no instruction to confirm the target, which is the classic way to overwrite the wrong disk.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `dd of=/dev/sdX` will destroy everything on whatever device you name. Confirm the target with `lsblk` immediately before running it, and never point it at a partition (`/dev/sdX1`) or at your system disk.

**Fix.**

**Verified workaround** — physically unplug and re-plug the USB stick as soon as the bootloader has handed off to the kernel (the moment the 'Waiting N seconds for device' line appears). The device re-enumerates and boot proceeds.

If it already dropped to the shell, re-plug and then:

```sh
blkid                       # confirm the medium is now visible
exit                        # returns control to the archiso hook, which retries
```

**Other things worth trying, in order:**

- Use a different physical port — prefer USB-A 2.0 over USB-C/Thunderbolt on affected machines.
- At the boot menu press `e` and lengthen the initramfs device wait: append `rootdelay=60` to the kernel line. This is the timeout that produces the 'Waiting N seconds' message.
- Do **not** bother with `copytoram` for this failure — it copies the ISO to RAM only *after* the medium has been found, so it cannot help when the device is never detected. (Current archiso also no longer uses `archisolabel=`; the parameters are `archisosearchuuid=` / `archisosearchfilename=`, set by the ISO's own boot entries — do not hand-write them.)
- Re-write the stick with `dd`. **Confirm the target device first** — `of=` pointed at the wrong disk destroys it with no prompt and no undo:

```sh
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS    # identify the USB stick by size/model/TRAN=usb
sudo dd if=omarchy.iso of=/dev/sdX bs=4M status=progress oflag=sync   # replace sdX, no partition number
sync
```

**Verify.** The installer reaches its menu/desktop without the emergency shell, and `lsblk -f` inside the live session shows the ISO label on the USB device.

Sources: <https://github.com/basecamp/omarchy/issues/8454> · <https://github.com/basecamp/omarchy/issues/8680>

---

## Omarchy installer dies at 'mounting the ESP failed (exit 32)' with a SQUASHFS superblock error

`installer-mounting-the-esp-failed-squashfs-superblock` · severity: **high** · frequency: **occasional** · applies to: `arch`, `btrfs`, `desktop`, `dual-boot`, `laptop`, `limine`, `luks`, `omarchy`, `windows`

**Symptom.** Installing Omarchy 4 from the ISO with the free space option, either alongside Windows or alongside plain data partitions. The installer creates the partitions, the LUKS container where asked for, the btrfs filesystem and its subvolumes, then stops at the last disk step:

```
mount: /mnt/boot: fsconfig() failed: Can't find a SQUASHFS superblock on nvme0n1p3.
       dmesg(1) may have more information after failed mount system call.
mounting the ESP failed (exit 32)
```

The device named in the message is the EFI partition the installer just created, so its number varies with the disk: `nvme0n1p3` on a dual-boot machine, `sda2` on a disk holding one data partition. The mount target is `/mnt/boot` on an encrypted install and `/mnt/efi` on an unencrypted one (`configurator:660` and `:662`). The aborted run removes the partitions it created before handing the disk back, so nothing is written to your existing partitions.

Two threads report it. In the first the free space was on a second NVMe drive with Windows on the first, and five other people in that thread report the identical message or confirm the workaround. In the second the target disk held a data partition and unallocated space but no EFI System Partition at all, reproduced by the reporter on a ten year old laptop and on a PC, once with an NTFS data partition and once with an empty Linux filesystem, and confirmed by other reporters on a MacBook Pro 16 (T2) with NTFS and exFAT partitions, on an MSI laptop, and on an Acer Nitro AN515-55 with a data-only NTFS drive.

One thing is common to every report in both threads: the target disk carried no FAT partition before the install. See the cause.

**Cause.** Named in the pull request that fixes it, `omacom/omarchy-iso#111`, still open and unmerged on 2026-09-11. Two facts about the installer combine.

First, the free-space path always creates its own dedicated EFI partition and never adopts an existing one. The comment at `configurator:531` says exactly that, and the only consumer of `detect_windows_esp` is a `say` line at `:539` that prints what it found. So the device named in the SQUASHFS error is always the partition the installer just made, and a thread that reads as a missing-ESP problem is the same defect.

Second, that new partition is formatted and then mounted with no filesystem type:

```bash
disk_step "creating the ESP filesystem on $efi_dev" mkfs.fat -F32 -n OMARCHY_EFI "$efi_dev"
disk_step "mounting the ESP" mount "$efi_dev" /mnt"$esp_mount_in_target"
```

Those are `configurator:772` and `:773` on the `quattro` branch of `omacom/omarchy-iso`, in the file last changed by commit `2673c613`, so every ISO built from that branch carries the defect. `detect_windows_esp` has the same untyped `mount -o ro` at `:396`.

The SQUASHFS text is not a claim about what is on the partition. `mount(8)` with no `-t` asks libblkid for the type, and when libblkid comes back empty or ambiguous it falls back to trying every non-`nodev` filesystem listed in `/etc/filesystems` or `/proc/filesystems`. On the live ISO `squashfs` is in that list, because the airootfs is a squashfs image, and `vfat` usually is not, because nothing mounts a FAT volume during a normal live boot. The error therefore names the last type tried, not the thing that failed. Naming the type removes the guess and also lets the kernel autoload the driver, which the untyped fallback cannot do.

It is not a timing race, despite the pull request's title, and it is not a leftover signature. `create_partition` already runs `partprobe` and `udevadm settle`, `configurator:718` to `:720` runs `partprobe`, `sync` and `sleep 2`, `wait_for_device` at `:722` polls for the device node and aborts the install if it never appears, and `wipefs -af` at `:728` and `mkfs.fat` at `:772` each open that device and write to it successfully before the mount runs. The ESP wipe arrived in commit `7d3b01e` on 2026-08-13, and a reporter hit the failure on an ISO dated 2026-08-14 with the FAT boot sector `dd`-verified as correctly written at the partition start. Upstream states plainly that why the libblkid probe comes back empty or ambiguous is still not pinned down: two attempts to reproduce the ambiguity on a loop device failed.

One likely explanation for the disk layouts involved, consistent with every report in both threads but not confirmed upstream. `detect_windows_esp` at `:391` loops over `blkid -t TYPE=vfat -o device`, skips any candidate that is not on the target disk, and mounts each one that is left. That mount hands a libblkid-identified `vfat` to `mount(2)`, which autoloads the `vfat` module and puts it in `/proc/filesystems`. A target disk that already carries a FAT partition therefore has `vfat` in the fallback list by the time `:773` runs, and a target disk without one does not. Every failing report is a target disk with no FAT partition on it, including the case where Windows and its ESP sat on a second drive and that same reporter then installed successfully onto the Windows disk itself. It also explains why creating a small FAT partition by hand works as a workaround.

> **Audit corrected this record.** Checked against the `quattro` branch of `omacom/omarchy-iso` fetched today, and against all four cited threads read in full with comments. Neither this record nor its fix can be exercised on this workstation: it is an installer defect on a live ISO, I have no sudo, no ISO was built and no VM was used, so everything below is source reading and thread reading, not a run.

What held. The central claim is confirmed in the source: the free-space path always creates its own ESP and never adopts an existing one, stated in the comment at `configurator:531` to `:536`, with `detect_windows_esp`'s only consumer a `say` line at `:539`, and the shared-ESP path deleted outright in commit `f79578f2` on 2026-07-18. All three line numbers the record cites still match today: the comment at `:531`, `create_partition` for the EFI partition at `:704`, and the untyped `mount -o ro` in `detect_windows_esp` at `:396`. The bare ESP mount is still present at `:773`, the file's last commit is still `2673c613` (2026-09-01), and `omacom/omarchy-iso#111` is still open, so an ISO built from `quattro` still carries the defect. The fix's rerun path is upstream's own: `abort()` at `configurator:178` to `:183` prints `You can retry later by running: ./.automated_script.sh`. The counts hold: three confirmations of the patch sequence in `#7263`, and the second route reported twice in `#7515`, once with a 256M partition and once with a 2 MB one, with one reporter deleting it afterwards and still booting.

What was wrong. The cause's mechanism is wrong, and it was the one thing I was asked to test hard. It claims the probe runs before udev has re-read the new partition, or reads a leftover signature. Upstream refutes both on the pull request: `create_partition` plus `configurator:718` to `:722` already run `partprobe`, `udevadm settle`, `sync`, `sleep 2` and a ten second `wait_for_device`, and `wipefs -af` at `:728` (added in `7d3b01e`, 2026-08-13) plus `mkfs.fat` at `:772` each open and write the device successfully before the mount. `udevadm settle` and `sleep 2` were in the PR's first revision and were removed from the head `daa0cc3` after review, so the record's fix reproduces lines upstream deliberately dropped and justifies them with a mechanism upstream rejects. The real mechanism, from `mount(8)` as quoted by the reviewer, is that an untyped mount whose libblkid probe comes back empty or ambiguous falls through every non-`nodev` type in `/proc/filesystems`, where `squashfs` is present on the live ISO and `vfat` is not, so the error names the last thing tried. Why the probe fails is explicitly not pinned down upstream, and I have said so rather than substituting a new guess. Two unverified specifics in the symptom also had to go: `#7515` says "empty linux fs partition", not ext4, and "including with the free space on the Windows disk" is contradicted by `#7263`'s own body, whose reporter says installing onto the Windows disk is what worked. I rewrote the danger: its first sentence mis-described the rollback, and `#7867`, which it already cited, carries two concrete hazards it did not pass on, one of them a command (`omarchy-refresh-limine`) that silently removes Windows from the boot menu after a successful install.

One addition is labelled as inference and not as fact. `detect_windows_esp` mounts any FAT partition found on the target disk, which autoloads `vfat` into `/proc/filesystems` before the ESP mount runs, and every failing report in both threads is a target disk with no FAT partition on it. That explains the otherwise unexplained second route and why it must be on the same disk. I marked it "not confirmed upstream" in the record because upstream says the trigger is still open.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** You are repartitioning a disk that holds data you want to keep. Confirm the target disk and partition on the installer's summary screen before accepting: on a two-disk machine the free space and the Windows ESP are on different drives, and picking the wrong one destroys Windows. The aborted run removes the partitions it created before handing the disk back (`disk_abort_hook` at `configurator:427`, which unmounts the target, closes LUKS and reclaims those partitions), so a rerun creates them again in the free space rather than reusing anything left over. The second route has you partition that same disk by hand, so back the data up first and create the new partition inside the free space only.

Two things afterwards on a dual-boot machine, both from `omacom/omarchy#7867`. This free-space path can leave a 2 GB ESP the firmware does not surface in its top-level boot list, so the machine boots straight to Windows, and recovery there took a chroot, a Limine reinstall, and repointing the `/boot` mount in `/etc/fstab` at the real Windows ESP. The same issue reports that `omarchy-refresh-limine` drops any Windows entry from `/boot/limine.conf` on every run and never restores it, because the template it copies in carries no OS entries and nothing downstream rescans for `bootmgfw.efi`, so do not run it on a dual-boot machine until that is fixed.

**Fix.**

One change fixes this: name the filesystem type on the ESP mount. Patch the installer script inside the live environment and rerun it. The aborted run already rolled back the partitions it created, and the edit is lost on reboot, so do it in the same live session that failed.

1. The installer prints `You can retry later by running: ./.automated_script.sh` and exits to a shell in `/root` on the live ISO. Open the script:

```bash
ls -la
nano configurator
```

Which editors the ISO ships was not confirmed. If `nano` is absent, try `vim`, or use the `sed` form at the end of this fix.

2. Find the block that formats and mounts the ESP (search for `mounting the ESP`):

```bash
disk_step "creating the ESP filesystem on $efi_dev" mkfs.fat -F32 -n OMARCHY_EFI "$efi_dev"
disk_step "mounting the ESP" mount "$efi_dev" /mnt"$esp_mount_in_target"
```

Change the second line to:

```bash
disk_step "mounting the ESP" mount -t vfat "$efi_dev" /mnt"$esp_mount_in_target"
```

That is the whole fix. The widely copied version of this workaround also inserts `udevadm settle` and `sleep 2` above the mount. They are harmless but they are not what repairs it, and upstream removed both from the pull request after review, because several settles and a ten second device poll already run before this point. Naming the type is the change that alters the outcome.

3. Optional, and only if Windows is on the target disk. In `detect_windows_esp`, change:

```bash
if mount -o ro "$p" "$tmp_mp" 2>/dev/null; then
```

to:

```bash
if mount -t vfat -o ro "$p" "$tmp_mp" 2>/dev/null; then
```

The loop already filters on `blkid -t TYPE=vfat`, so this changes no outcome on the success path. It makes an unreadable candidate fail as a FAT mount instead of falling through the same filesystem list.

4. Save, then start the installer again:

```bash
umount -R /mnt 2>/dev/null
./.automated_script.sh
```

Answer the installer's questions again exactly as before. Three people in `omacom/omarchy#7263` confirmed this sequence completes the install, and four more confirmed it on `omacom/omarchy-iso#111`, one of whom changed only the ESP mount line and nothing else, and one of whom built an ISO from the branch.

Without an editor, the same two edits:

```bash
sed -i 's|mount "$efi_dev" /mnt"$esp_mount_in_target"|mount -t vfat "$efi_dev" /mnt"$esp_mount_in_target"|' configurator
sed -i 's|mount -o ro "$p" "$tmp_mp"|mount -t vfat -o ro "$p" "$tmp_mp"|' configurator
grep -n 'mount -t vfat' configurator      # two hits
bash -n configurator                      # still parses
```

A second route was reported to work twice. On a disk with data partitions and no EFI System Partition, two reporters created a small FAT32 partition themselves before running the installer, and the free-space install then completed:

1. Press Ctrl+C at the installer to reach a shell, or open a second console.
2. `cfdisk /dev/sdX` on the target disk. Create a 256M partition inside the free space, set its type to `EFI System`, write, quit.
3. Format it: `mkfs.fat -F32 /dev/sdXN`
4. Relaunch with `./.automated_script.sh` and pick the free space option again.

The second reporter used a 2 MB FAT partition and rebooted into the installer first. The partition has to be on the disk you are installing to, because `detect_windows_esp` skips candidates that are not. It ends up unused either way: the installer still creates and uses its own EFI partition. Prefer the typed mount above, which is the change upstream is merging. One reporter deleted the spare partition afterwards and Omarchy still booted, but that was one machine, so check `findmnt /boot` points at the installer's own ESP before removing anything.

**Verify.** The installer passes `mounting the ESP` and continues to package installation. After the first boot into Omarchy:

```bash
findmnt /boot                    # FSTYPE vfat, SOURCE the new EFI partition
lsblk -f | grep OMARCHY_EFI
lsblk -o NAME,SIZE,FSTYPE,PARTTYPENAME /dev/sdX    # the data partition untouched
```

Sources: <https://github.com/omacom/omarchy/issues/7263> · <https://github.com/omacom/omarchy/issues/7515> · <https://github.com/omacom/omarchy/issues/7867> · <https://github.com/omacom/omarchy-iso/pull/111> · <https://github.com/omacom/omarchy-iso/blob/2673c613d9a71e23920e43fbb951238145e0f1e8/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/.automated_script.sh>

---

## Omarchy: Limine panics on a stale /EFI/Linux/arch-linux.efi entry after upgrading

`omarchy-limine-panic-stale-arch-linux-efi` · severity: **high** · frequency: **occasional** · applies to: `desktop`, `laptop`, `limine`, `omarchy`, `uefi`

**Symptom.** After upgrading to Omarchy Quattro (4.x), the Limine countdown expires and the machine panics instead of booting:

```
PANIC: efi: Failed to open image with path 'boot():/EFI/Linux/arch-linux.efi'
```

The menu still lists an entry titled `Arch Linux (linux)` that no longer works.

**Cause.** `archinstall` originally wrote a Limine entry pointing at the unified kernel image `/EFI/Linux/arch-linux.efi`. Omarchy's upgrade path deletes that UKI when it takes over kernel image generation, but `normalize_limine_config()` does not strip the now-dangling entry from `/boot/limine.conf`. If that stale entry is the default, the timeout selects a file that is not there. Tracked as basecamp/omarchy#7989.

> **Audit corrected this record.** Issue 7989 is real and the title matches the record's cause exactly ('omarchy-upgrade-to-quattro leaves archinstall's /EFI/Linux/arch-linux.efi Limine entry in place, so the default boot entry panics'), and normalize_limine_config() does exist in bin/omarchy-upgrade-to-quattro. The hand-edit works, but it is the fragile route: any subsequent `omarchy update` replaces /boot/limine.conf anyway. Also `default_entry: 1` is offered as the example while Omarchy's shipped template uses `default_entry: 2` — Limine's index is 1-based (confirmed in CONFIG.md), so pasting 1 may silently select a different entry than intended.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing limine.conf on the ESP with no working entry left will leave the machine unbootable without a live USB. Copy the file to limine.conf.bak first and verify at least one entry's `path:` resolves to a file that exists on the ESP.

**Fix.**

At the Limine menu, arrow to the working **Omarchy** entry and boot it. Then take the supported route, which rewrites the config from Omarchy's template and drops the dangling entry for you:

```sh
ls -l /boot/EFI/Linux/            # confirm arch-linux.efi is really gone
sudo omarchy-refresh-limine       # backs up to /boot/limine.conf.bak, regenerates, runs limine-update
```

If you would rather edit by hand:

```sh
sudo cp /boot/limine.conf /boot/limine.conf.bak
sudoedit /boot/limine.conf
```

Delete the whole stanza:

```
/Arch Linux (linux)
    protocol: efi
    path: boot():/EFI/Linux/arch-linux.efi
```

`default_entry` is a **1-based index into the entries that remain after your edit** — count them rather than copying a number. Verify by booting once with a visible menu:

```
timeout: 5
default_entry: 1
```

Then apply:

```sh
sudo limine-update          # re-reads /boot/limine.conf
sudo limine-mkinitcpio      # rebuilds the UKIs on the ESP
```

A hand-edited /boot/limine.conf does not survive the next `omarchy update`, but that is fine here — the refresh regenerates from the template, which never contained the stale entry.

**Verify.** Reboot and let the timeout expire without touching the keyboard — the machine boots straight into Omarchy. `grep -n 'arch-linux.efi' /boot/limine.conf` returns nothing.

Sources: <https://github.com/basecamp/omarchy/issues/7989> · <https://github.com/limine-bootloader/limine/blob/v9.x/CONFIG.md>

---

## UEFI boot entries vanish after every reboot (NVRAM full, or firmware wiping entries)

`uefi-nvram-boot-entries-dropped-use-fallback-path` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`, `uefi`

**Symptom.** You create a boot entry, `efibootmgr -v` shows it, everything works — and after one reboot it is gone again, or the firmware boots Windows instead, or you get `No bootable device found` / `Reboot and Select proper Boot device`. Sometimes `efibootmgr --create` fails outright with:

```
Could not prepare Boot variable: No space left on device
```

Common on Lenovo ThinkPads (T16 Gen 2 and similar), on boards with CSM enabled, and after running Omarchy's Setup > Direct Boot, which adds an EFI entry the firmware may then discard.

**Cause.** Three separate firmware behaviours produce the same symptom. (1) NVRAM is full — some boards silently drop entries instead of erroring. (2) The UEFI spec allows OEMs to do "NVRAM maintenance" at boot: firmware that finds no EFI binary at a hardcoded path concludes the disk has no OS and wipes the entries associated with it. (3) Options such as Lenovo's "OS Optimized Defaults", or a firmware that removes entries pointing at drives absent at POST, delete non-Windows entries on principle. In all three cases NVRAM is the wrong place to rely on, and the removable-media fallback path is the durable answer.

> **Audit corrected this record.** The three firmware behaviours, the fallback-path strategy, and every non-Limine command check out (grub-install --removable, `bootctl install` which does write EFI/BOOT/BOOTX64.EFI, bootctl --no-variables install, efibootmgr --create/-o/-b NNNN -B, clearing dump-* efivars, Lenovo OS Optimized Defaults, and Omarchy's Direct Boot which is documented as refusing to run on American Megatrends and Apple firmware). But the headline command for the target distro is invented: there is no `limine-install` binary and no `--fallback` flag anywhere in the limine, limine-entry-tool, limine-mkinitcpio-hook or limine-snapper-sync packages. The limine package ships /usr/share/limine/BOOTX64.EFI and the fallback install is a config switch (ENABLE_LIMINE_FALLBACK), which Omarchy already sets to yes in etc/limine-entry-tool.d/omarchy-defaults.conf. The manual-copy step also invents a source path (/boot/EFI/limine/limine_x64.efi), and the efibootmgr --loader value repeats it.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting the wrong `efibootmgr -b NNNN -B` entry (Windows Boot Manager on a dual-boot machine) leaves that OS unbootable until you recreate it. Writing to or deleting files under /sys/firmware/efi/efivars has bricked machines with buggy firmware — remove only `dump-*` files, never `rm -rf` the directory. Do not add `efi_no_storage_paranoia` as a permanent kernel parameter: it disables the safeguard that keeps NVRAM from filling to the point of bricking the board. On a shared ESP, `grub-install --removable` and `bootctl install` both overwrite `\EFI\BOOT\BOOTX64.EFI`, which may currently be another OS's loader.

**Fix.**

Everything in the record stands except the Limine steps.

There is no `limine-install --fallback`. On Omarchy/limine-entry-tool the fallback path is a configuration switch, and Omarchy already ships it enabled:

```bash
grep -rn 'ENABLE_LIMINE_FALLBACK' /etc/default/limine /etc/limine-entry-tool.d/
# Omarchy: ENABLE_LIMINE_FALLBACK=yes in /etc/limine-entry-tool.d/omarchy-defaults.conf
sudo limine-update
ls -l /boot/EFI/BOOT/BOOTX64.EFI
```

If it is unset (plain Arch), add `ENABLE_LIMINE_FALLBACK=yes` to /etc/default/limine and run `sudo limine-update`, or place the binary by hand — the source is the one the limine package ships:

```bash
sudo mkdir -p /boot/EFI/BOOT
sudo cp /usr/share/limine/BOOTX64.EFI /boot/EFI/BOOT/BOOTX64.EFI
```

When recreating the NVRAM entry, look at what is actually on the ESP instead of assuming a filename, and point the entry at a path that exists:

```bash
ls -R /boot/EFI
sudo efibootmgr --create --disk /dev/nvme0n1 --part 1 \
  --loader '\EFI\BOOT\BOOTX64.EFI' --label 'Limine' --unicode
sudo efibootmgr -o 0001,0000
```

GRUB, systemd-boot, the NVRAM-full cleanup (`efibootmgr -b 0005 -B`, `rm /sys/firmware/efi/efivars/dump-*`, disabling CSM), the Lenovo advice, and the Direct Boot advice are all correct as written.

**Verify.** `efibootmgr -v` lists your entry after a reboot; `ls -l /boot/EFI/BOOT/BOOTX64.EFI` exists; the machine still boots after clearing NVRAM entries or resetting the firmware to defaults.

Sources: <https://wiki.archlinux.org/title/Unified_Extensible_Firmware_Interface> · <https://wiki.archlinux.org/title/EFI_system_partition> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/blob/quattro/manual/47-system-snapshots.md>

---

## "unknown filesystem type 'vfat'" when mounting /boot or /boot/efi at boot

`vfat-module-missing-boot-efi-mount-fails` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `manjaro`, `omarchy`, `systemd`, `uefi`

**Symptom.** Immediately after an update the boot sequence reports:

```
[FAILED] Failed to mount /boot/efi.
mount: /boot/efi: unknown filesystem type 'vfat'.
```

and the system drops to emergency mode. The partition is fine — `fsck.vfat` from a live USB reports no errors, and reinstalling GRUB does not help.

**Cause.** The `vfat` kernel module (plus its `nls_iso8859-1` / `nls_cp437` codepage dependencies) is not available when the mount is attempted. Two ways this happens: the initramfs/early boot lacks the module, or the kernel package was upgraded while running and `/usr/lib/modules/$(uname -r)` was replaced, so `modprobe vfat` fails until reboot.

> **Audit corrected this record.** The two causes and both remedies are right, and `kernel-modules-hook` is a real package (extra 0.1.7) that solves the upgrade-while-running case. Two problems. `MODULES=(vfat nls_cp437 nls_iso8859-1)` is written as a bare assignment — on Omarchy and on NVIDIA systems MODULES already holds the early-KMS list, and pasting this silently deletes it, trading a /boot/efi mount failure for a black screen. Also the module name is spelled `nls_iso8859-1` in the mkinitcpio block and `nls_iso8859_1` in the dracut block; modprobe treats - and _ interchangeably so this happens to work, but the inconsistency invites hand-editing errors.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

**First, is this only the running system?** If `modprobe vfat` fails with 'Module vfat not found in directory /lib/modules/6.x', the kernel was upgraded underneath you — just reboot, then prevent recurrence:

```sh
sudo pacman -S kernel-modules-hook
```

**If it persists across a reboot**, force the modules into the image. Check what MODULES already holds before you assign, or you will delete it:

```sh
grep -h '^MODULES' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
```

Then **append** to the existing list rather than replacing it (add these three to whatever is already inside the parentheses):

```sh
# /etc/mkinitcpio.conf  -- e.g. MODULES=(nvidia nvidia_modeset vfat nls_cp437 nls_iso8859-1)
MODULES=(<keep whatever was there> vfat nls_cp437 nls_iso8859-1)
```

Ensure `modconf` is in HOOKS so /etc/modprobe.d and forced modules are honoured:

```sh
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)
```

Rebuild (one command, not both — limine-mkinitcpio wraps mkinitcpio):

```sh
sudo mkinitcpio -P        # Arch / CachyOS
sudo limine-mkinitcpio    # Omarchy (rebuilds initramfs AND the UKIs on the ESP)
```

For a **dracut** system (EndeavourOS default), use a drop-in — keep the module names consistent with the mkinitcpio spelling:

```sh
sudo tee /etc/dracut.conf.d/force-vfat.conf >/dev/null <<'EOF'
force_drivers+=" vfat nls_cp437 nls_iso8859-1 "
EOF
sudo dracut-rebuild
```

(`dracut-rebuild` is EndeavourOS's wrapper; on plain dracut use `sudo dracut --regenerate-all --force`.)

**Verify.** `lsinitcpio /boot/initramfs-linux.img | grep vfat` (mkinitcpio) or `lsinitrd | grep vfat` (dracut) finds the module, `sudo mount -a` succeeds, and `systemctl --failed` is empty after reboot.

Sources: <https://forum.endeavouros.com/t/emergency-mode-failed-to-mount-boot-efi-vfat-error-tried-base-reinstall-issue-persists/75747> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://forum.endeavouros.com/t/boot-failing-after-update-kernel-modules-not-loading/37928>

---

## Make Windows appear in the GRUB menu again (os-prober disabled by default)

`grub-windows-entry-missing-os-prober` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `dual-boot`, `endeavouros`, `grub`, `laptop`, `manjaro`, `uefi`, `windows`

**Symptom.** Dual-boot machine: after installing Arch/EndeavourOS, or after running `grub-mkconfig`, the GRUB menu shows only Linux. Windows is gone. `grub-mkconfig` prints:

```
Warning: os-prober will not be executed to detect other bootable partitions.
Systems on them will not be added to the GRUB boot configuration.
Check GRUB_DISABLE_OS_PROBER documentation entry.
```

**Cause.** Since GRUB 2.06, `os-prober` is disabled by default for security reasons, so `grub-mkconfig` no longer scans other partitions for bootable OSes. Additionally, `os-prober` cannot see a Windows install whose ESP is not mounted, and cannot read an NTFS partition without an NTFS driver.

> ⚠️ **Risk.** Leaving the Windows ESP permanently mounted in /etc/fstab at a writable location invites accidental damage to Windows boot files. Mount it only when needed, or mount read-only.

**Fix.**

Install the prerequisites, enable the prober, regenerate:

```sh
sudo pacman -S os-prober ntfs-3g
```

Edit `/etc/default/grub` and set (uncomment or add the line):

```sh
GRUB_DISABLE_OS_PROBER=false
```

Make sure the Windows ESP is mounted so os-prober can find `bootmgfw.efi`, then regenerate:

```sh
sudo mkdir -p /mnt/win-esp
sudo mount /dev/nvme0n1p1 /mnt/win-esp     # the Windows ESP
sudo os-prober                              # should print .../bootmgfw.efi:Windows Boot Manager:...
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

Also turn off Windows Fast Startup, which leaves NTFS dirty and hides the install from os-prober. In an Administrator Command Prompt on Windows:

```
powercfg /h off
```

If `os-prober` still finds nothing, add the entry by hand in `/etc/grub.d/40_custom`:

```sh
menuentry "Windows Boot Manager" {
    insmod part_gpt
    insmod fat
    insmod chain
    search --no-floppy --fs-uuid --set=root XXXX-XXXX
    chainloader /EFI/Microsoft/Boot/bootmgfw.efi
}
```

Replace `XXXX-XXXX` with the ESP's FAT UUID from `sudo blkid /dev/nvme0n1p1`, then re-run `grub-mkconfig -o /boot/grub/grub.cfg`.

**Verify.** `sudo os-prober` prints a Windows line, `grep -c Windows /boot/grub/grub.cfg` is non-zero, and the GRUB menu offers Windows Boot Manager.

Sources: <https://forum.endeavouros.com/t/windows-boot-manager-not-showing-in-grub-menu/42094> · <https://forum.endeavouros.com/t/grub-2-2-06-r322-gd9b4638c5-1-wont-boot-and-goes-straight-to-the-bios-after-update/30653> · <https://archlinux.org/news/grub-bootloader-upgrade-and-configuration-incompatibilities/>

---

## Migrate to the mkinitcpio `microcode` hook (mkinitcpio 38 / March 2024)

`microcode-hook-migration-mkinitcpio-38` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `grub`, `intel`, `limine`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** After the mkinitcpio 38 / systemd 255.4 upgrade, boot entries that hand-list microcode still work but `mkinitcpio` warns about the deprecated `--microcode` flag, or CPU microcode silently stops being loaded (`dmesg | grep -i microcode` shows no early update). Users on manual systemd-boot entries also report the boot failing to find `/intel-ucode.img` after cleaning /boot.

**Cause.** Arch moved the `systemd`, `udev`, `encrypt`, `sd-encrypt`, `lvm2` and `mdadm_udev` hooks from distro packages into upstream mkinitcpio, and deprecated the `--microcode` flag and the `microcode` preset option in favour of a new `microcode` **hook** that embeds the CPU microcode into the initramfs itself. Configs written before March 2024 still use the old two-initrd approach. mkinitcpio 41 still accepts the old flag and preset option, with a deprecation warning, so a preset or boot entry that was never migrated keeps working and keeps warning.

Omarchy 4 is not affected. It was packaged after this change, and its hooks are assigned wholesale by `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` (owned by `omarchy-settings`), which already carries `microcode` right after `autodetect`. The microcode is inside the UKI at `/boot/EFI/Linux/omarchy_linux.efi`, so no separate `intel-ucode.img` or `amd-ucode.img` line exists in the Limine entry.

> **Audit corrected this record.** Version claims checked against the mkinitcpio CHANGELOG and the gitlab tags: v38 was tagged 2024-02-28 with '--microcode has been deprecated and replaced by the new microcode hook', v38.1 on 2024-03-12 noted the hook prefers /usr/lib/firmware/*-ucode/ and uses /boot/*-ucode.img only as a fallback, and the Arch news post is dated 2024-03-04 and lists mkinitcpio 38-3, systemd 255.4-2, lvm2 2.03.23-3, mdadm 4.3-2 and cryptsetup 2.7.0-3. So 'mkinitcpio 38 / systemd 255.4 / March 2024' holds. On this machine mkinitcpio 41.1 still accepts --microcode with the warning 'The --microcode option has deprecated' (/usr/bin/mkinitcpio line 982) and warns on a preset's *_microcode or ALL_microcode option (lines 727 to 731), so the symptom is still reachable on an Arch install carrying a pre-2024 preset. The wiki Microcode page confirms the hook, the autodetect-before-microcode narrowing, the lsinitcpio --early check, and the separate-file layouts for GRUB, systemd-boot and Limine that the record describes. Omarchy 4 is not affected and the fix as written misdirects there: /etc/mkinitcpio.conf.d/omarchy_hooks.conf (owned by omarchy-settings 4.0.2-1) assigns HOOKS wholesale with microcode directly after autodetect, so the record's edit to HOOKS in /etc/mkinitcpio.conf is silently replaced when the drop-in is sourced afterwards. journalctl -k on this machine shows 'microcode: Updated early from: 0x000000ae' to revision 0x000000f8 with intel-ucode 20260812-1, confirming early loading works stock. sudo pacman -Syu mkinitcpio systemd lvm2 mdadm cryptsetup is refused on Omarchy 4 by /etc/pacman.d/hooks/00-omarchy-update-guard.hook, whose script aborts any pacman invocation carrying both S and u (omarchy-update-pacman-guard lines 23 to 47), while pacman -S amd-ucode passes because it has no u. sudo mkinitcpio -P exits with 'No presets found in /etc/mkinitcpio.d' because that directory is empty here (limine-mkinitcpio-hook shadows mkinitcpio's pacman hook and never generates presets), so the rebuild on Omarchy is limine-mkinitcpio, and the record's advice to grep /etc/mkinitcpio.d/*.preset has nothing to grep. The verify field also names mkinitcpio -P, which does not apply on Omarchy 4. Not exercised: lsinitcpio --early on the UKI (needs root to read /boot), a rebuild, and the systemd-boot and GRUB branches, which were checked against the wiki only.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Removing the `initrd /*-ucode.img` line from a systemd-boot entry *before* the `microcode` hook is in place and the image rebuilt leaves you booting without microcode updates. Do the HOOKS edit and `mkinitcpio -P` first, then edit the loader entry.

**Fix.**

**Omarchy 4**

Nothing to migrate. Confirm the hook is present and the microcode loads:

```sh
grep -h microcode /etc/mkinitcpio.conf.d/*.conf
journalctl -k --grep='microcode:'
```

Expect a `HOOKS=(... autodetect microcode ...)` line from `omarchy_hooks.conf` and `microcode: Updated early from: ...` in the journal. Do not edit `HOOKS` in `/etc/mkinitcpio.conf`: the drop-in assigns `HOOKS=(...)` after that file is read and replaces whatever you set there.

If the journal shows no early update, the microcode package is missing. Install the one for your CPU, then rebuild the UKI:

```sh
sudo pacman -S amd-ucode      # AMD
sudo pacman -S intel-ucode    # Intel
sudo limine-mkinitcpio
```

`pacman -S <pkg>` passes the ALPM guard, which only refuses `-Syu`. Use `limine-mkinitcpio`, not `mkinitcpio -P`: `/etc/mkinitcpio.d` is empty on Omarchy 4 and `-P` exits with `No presets found`. Do not add `initrd=/intel-ucode.img` to a `/etc/limine-entry-tool.d` file or a `module_path` line to `/boot/limine.conf`. Keep the packages current with `omarchy update`, since a direct `pacman -Syu` is refused.

**Plain Arch**

Bring the system fully current. The March 2024 announcement required mkinitcpio 38-3, systemd 255.4-2, lvm2 2.03.23-3, mdadm 4.3-2 and cryptsetup 2.7.0-3 to move as a set, and a full upgrade does that:

```sh
sudo pacman -Syu
```

Install the microcode package for your CPU if it is not already there:

```sh
sudo pacman -S amd-ucode      # AMD
sudo pacman -S intel-ucode    # Intel
```

Add the `microcode` hook right after `autodetect` in `/etc/mkinitcpio.conf`:

```sh
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)
```

Rebuild:

```sh
sudo mkinitcpio -P
```

If you use **systemd-boot with hand-written entries**, the separate microcode initrd line is now redundant. `/boot/loader/entries/arch.conf` becomes:

```
title   Arch Linux
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=UUID=xxxx-xxxx rw
```

(delete any `initrd /amd-ucode.img` or `initrd /intel-ucode.img` line). GRUB users need do nothing extra beyond `sudo grub-mkconfig -o /boot/grub/grub.cfg`. Limine users with a hand-written `limine.conf` can drop the `module_path: boot():/<cpu>-ucode.img` line once the hook is in place.

Also check `/etc/mkinitcpio.d/*.preset` for a leftover `--microcode` in `default_options` or `fallback_options` and remove it. Then confirm:

```sh
journalctl -k --grep='microcode:'
sudo lsinitcpio --early /boot/initramfs-linux.img | grep microcode
```

**Verify.** `dmesg | grep -i 'microcode'` shows `microcode: Current revision: ...` / `updated early`, and `mkinitcpio -P` runs without deprecation warnings.

Sources: <https://archlinux.org/news/mkinitcpio-hook-migration-and-early-microcode/> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://man.archlinux.org/man/mkinitcpio.8> · <https://wiki.archlinux.org/title/Microcode> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/CHANGELOG>

---

## Omarchy: Windows entry disappears from Limine after every update

`omarchy-limine-windows-entry-wiped` · severity: **medium** · frequency: **common** · applies to: `desktop`, `dual-boot`, `laptop`, `limine`, `omarchy`, `uefi`, `windows`

**Symptom.** You dual-boot Omarchy with Windows. You add a Windows entry to the Limine menu, it works — then after the next `omarchy update` (or any run of `omarchy-refresh-limine`) the Windows entry is gone again and the only way into Windows is the firmware boot menu. On some installs the Omarchy installer also created a second, redundant 2 GB ESP (`omarchy-efi`) instead of reusing the Windows ESP, so the firmware never surfaces the Omarchy entry at the top level.

**Cause.** `omarchy-refresh-limine` overwrites `/boot/limine.conf` from a template that contains no OS entries, then runs helpers that only re-add Linux/snapshot entries. Any foreign-OS entry in the file is silently and permanently discarded. Tracked upstream as basecamp/omarchy#7867.

> **Audit corrected this record.** The problem is real and precisely described — I read bin/omarchy-refresh-limine and it does `sudo mv /boot/limine.conf /boot/limine.conf.bak` then copies default/limine/limine.conf over it, and issue 7867's title confirms both the dropped Windows entry and the redundant ESP. The Limine syntax is valid (CONFIG.md confirms `protocol: efi` is the EFI-chainload alias and `boot(N):/...` selects partition N of the boot drive). But the fix has three defects: the `cp /boot/limine.conf /etc/limine-windows-entry.conf.bak` line saves the whole config under a name implying it holds only the Windows entry and is never used again; the re-apply script never runs `limine-update`, so the edited config may not be picked up; and `boot(1)` is only correct when Windows sits on partition 1 of the *same* drive Limine booted from — on the dual-ESP layout the record itself describes, that is exactly what is not true.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing /boot/limine.conf incorrectly (bad indentation, wrong boot() index) makes Limine drop to its own error screen. Keep a backup copy of the working file before editing, and never remove the Omarchy entries while adding Windows.

**Fix.**

Find the Windows ESP, its partition index, and its GUID:

```sh
sudo blkid | grep -i vfat
lsblk -o NAME,PARTLABEL,PARTUUID,SIZE,FSTYPE,MOUNTPOINT
sudo ls /boot/EFI/Microsoft/Boot/bootmgfw.efi 2>/dev/null   # is Windows on THIS ESP?
```

Add to `/boot/limine.conf`. If Windows is on the same drive Limine booted from, `boot(N)` works — N is the 1-based partition index, **not** always 1:

```
/Windows
    protocol: efi
    path: boot(1):/EFI/Microsoft/Boot/bootmgfw.efi
```

If Windows has its own ESP on another disk (the redundant-ESP layout in issue 7867), `boot()` cannot reach it — use the partition GUID instead, which is stable across disk reordering:

```
/Windows
    protocol: efi
    path: guid(XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX):/EFI/Microsoft/Boot/bootmgfw.efi
```

(GUID = the ESP's `PARTUUID` from the lsblk output above.)

Apply it and re-append after every update:

```sh
sudo tee /usr/local/bin/readd-windows-limine >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if ! grep -q '^/Windows' /boot/limine.conf; then
  cat >> /boot/limine.conf <<'ENTRY'

/Windows
    protocol: efi
    path: boot(1):/EFI/Microsoft/Boot/bootmgfw.efi
ENTRY
  limine-update
fi
EOF
sudo chmod +x /usr/local/bin/readd-windows-limine
```

Edit the `path:` line in that script to whichever form you verified works. Run `sudo readd-windows-limine` after each `omarchy update` until #7867 is fixed. Note `omarchy-refresh-limine` leaves the previous file at `/boot/limine.conf.bak`, so you can always recover your entry from there.

**Verify.** Reboot; the Limine menu lists **Windows** and selecting it chainloads the Windows Boot Manager. Re-run `omarchy update`, then confirm the entry is still (or is again) present in `/boot/limine.conf`.

Sources: <https://github.com/basecamp/omarchy/issues/7867> · <https://github.com/limine-bootloader/limine/blob/v9.x/CONFIG.md> · <https://learn.omacom.io/2/the-omarchy-manual/120/dual-boot-install>

---

## Hibernation never resumes: the `resume` hook lands after `filesystems`

`resume-hook-after-filesystems-hibernation` · severity: **medium** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `laptop`, `limine`, `luks`, `omarchy`

**Symptom.** After `omarchy hibernation setup` the machine hibernates, but powering on gives a cold boot and unsaved work is gone. Looking for the cause you find `resume` at the end of the effective hook list, after `filesystems`, `fsck` and `btrfs-overlayfs`, because `/etc/mkinitcpio.conf.d/omarchy_resume.conf` only appends `HOOKS+=(resume)`. That ordering is harmless. So far the failing machines are hybrid Intel+NVIDIA and AMD+NVIDIA laptops, and `journalctl -b | grep -iE 'PM: hibernation|nv_pmops'` shows `nvidia ... pci_pm_freeze(): nv_pmops_freeze [nvidia] returns -5` followed by `PM: hibernation: resume failed (-5)`.

**Cause.** The position of `resume` relative to `filesystems` does not matter in a busybox initramfs. mkinitcpio's `init` runs every hook's `run_hook` function first and mounts the real root on `/sysroot` afterwards, and the `filesystems` hook has no runtime script at all (its install script only adds filesystem modules and `mount.*` helpers to the image). The only ordering rules are that `resume` come after `udev` and after whatever provides the swap device (`encrypt`, `lvm2`), and Omarchy's `encrypt ... resume` order meets both. The Arch wiki's own example puts `resume` after `filesystems`. Issue basecamp/omarchy#8471 argues the ordering is wrong on paper and its reporter says they could not show a failure caused by it.

The cold boots reported on Omarchy come from a different drop-in. `install/hardware/nvidia.sh` writes `/etc/mkinitcpio.conf.d/nvidia.conf` with `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` on every NVIDIA machine, including hybrid laptops where the iGPU drives the only panel. Those modules load from the initramfs before the resume hook runs. When the kernel then tries to load the hibernation image it has to freeze every loaded driver, the NVIDIA instance in the initramfs fails `pci_pm_freeze()` with `-5`, and the kernel logs `Failed to load image, recovering` and continues as a normal boot. That is basecamp/omarchy#8352, confirmed by two more reporters on different hardware, and moving `resume` earlier does not change it because the modules are loaded by the `MODULES` array before any hook runs.

Two other things produce the same cold boot on Omarchy without any NVIDIA involvement. `omarchy-hibernation-setup` writes `resume=<device> resume_offset=<offset>` to `/etc/limine-entry-tool.d/resume.conf`, and if `btrfs inspect-internal map-swapfile` failed during setup the file carries an empty `resume_offset=`, which the script knows how to repair on its next run. And if `/sys/power/disk` reads `[disabled]` the kernel will not hibernate at all.

> **Audit corrected this record.** The cause is disproved by mkinitcpio's own init script. In the busybox initramfs, `init` runs `run_hookfunctions 'run_hook' 'hook' $HOOKS` for every hook in the array and only afterwards calls `fsck_root` and `"$mount_handler" /sysroot`, so root is mounted after all runtime hooks, including a `resume` placed last. The `filesystems` hook has only a `build()` function and no runtime script, so it cannot mount anything at boot. The Arch wiki's own busybox example is `block filesystems resume fsck`, and its stated constraints are only that `resume` follow `udev` and any of `encrypt`/`lvm2`, which Omarchy's `encrypt ... resume` order satisfies. Issue 8471, the record's main source, has zero comments and its reporter writes that they could not demonstrate a resume failure attributable to the ordering. Issue 8352 is the real defect behind cold boots on Omarchy: `install/hardware/nvidia.sh` writes `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` on hybrid laptops, the initramfs instance of `nvidia` fails its freeze callback with -5 and the kernel discards the image, and two independent reporters confirm that stripping the modules fixes it, while the reporter states reordering `resume` does not help. This workstation, an Omarchy 4.0.2-1 install with `resume` last, logs `PM: Image not found (code -22)` on every boot, which is the kernel checking the configured resume device before root is mounted. The record's fix also names `cmdline:` in `/boot/limine.conf`, which `limine-entry-tool` regenerates from `/etc/limine-entry-tool.d/*.conf`, where `omarchy-hibernation-setup` already writes `resume.conf`, and its example HOOKS line drops `plymouth`. `omarchy_resume.conf` is written by `bin/omarchy-hibernation-setup` on the quattro branch, not shipped by a package. Both issues now resolve under `omacom/omarchy` on GitHub. The corrected fix below is built from the issue 8352 reports and the setup script and was not exercised with a hibernate cycle on this machine.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Only strip the NVIDIA modules on a machine where another GPU drives the display. On an NVIDIA-only machine `omarchy_hooks.conf` has already dropped the `kms` hook because `nvidia_drm` is early-loaded, so removing the modules as well leaves Plymouth and the LUKS passphrase prompt without early KMS. Do not hand-edit `/boot/limine.conf`: `limine-entry-tool` overwrites it on the next rebuild. Leave `HOOKS` alone. A hand-written `HOOKS=` drop-in that omits `encrypt`, `block`, `filesystems` or `plymouth` produces an initramfs that cannot unlock or mount root, or loses the splash, for no benefit.

**Fix.**

Do not rewrite `HOOKS`. First confirm the hook order is what Omarchy intends and read the journal from the boot that should have resumed:

```sh
bash -c 'source /etc/mkinitcpio.conf; for f in /etc/mkinitcpio.conf.d/*.conf; do source "$f"; done; printf "%s\n" "${HOOKS[@]}" | nl'
journalctl -b | grep -iE 'PM: (hibernation|image)|nv_pmops|hibernate-resume'
cat /proc/cmdline | tr ' ' '\n' | grep resume
```

`resume` after `encrypt` is correct wherever it sits. A normal boot with `resume=` set logs `PM: Image not found (code -22)`, which shows the resume device was checked before root was mounted.

If the journal shows `nv_pmops_freeze [nvidia] returns -5` and the machine is a hybrid laptop whose panel is driven by an Intel or AMD iGPU, keep the NVIDIA modules out of the initramfs. This is the workaround from basecamp/omarchy#8352, verified with real hibernate cycles by its reporters. The `zz-` name sorts after `nvidia.conf` and after `omarchy_hooks.conf`, so the `kms` hook decision in `omarchy_hooks.conf` is unchanged:

```sh
sudo tee /etc/mkinitcpio.conf.d/zz-hibernate-no-nvidia.conf >/dev/null <<'EOF'
_zz_filtered=()
for _zz_m in "${MODULES[@]}"; do
  case "$_zz_m" in
    nvidia|nvidia_modeset|nvidia_uvm|nvidia_drm) continue ;;
  esac
  _zz_filtered+=("$_zz_m")
done
MODULES=("${_zz_filtered[@]}")
unset _zz_filtered _zz_m
EOF
sudo limine-mkinitcpio
```

If the journal shows no resume attempt, check the Limine cmdline drop-in rather than `/boot/limine.conf`, which `limine-entry-tool` regenerates from `/etc/limine-entry-tool.d/`:

```sh
cat /etc/limine-entry-tool.d/resume.conf
sudo btrfs inspect-internal map-swapfile -r /swap/swapfile
findmnt -no SOURCE -T /swap/swapfile
```

The device must be the block device backing the swapfile (`/dev/mapper/root` on an encrypted Omarchy install, not the swap UUID) and the offset must match the `map-swapfile` output. If `resume_offset=` is empty, rerun the setup, which repairs it and rebuilds the UKI:

```sh
omarchy hibernation setup
```

If `cat /sys/power/disk` prints `[disabled]`, the kernel cannot hibernate on this machine and no initramfs change will help.

**Verify.** `lsinitcpio /boot/initramfs-linux.img | grep -n resume` (or inspect the UKI) shows the resume hook, and `sudo systemctl hibernate` followed by power-on returns you to your open windows. `journalctl -b | grep -i 'resume'` shows the resume device being used.

Sources: <https://github.com/basecamp/omarchy/issues/8471> · <https://github.com/basecamp/omarchy/issues/8352> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hibernation-setup> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/init> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/init_functions> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/hooks/resume> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/install/resume> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/install/filesystems> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio/-/raw/master/man/mkinitcpio.conf.5.adoc>

---

## Ignore (or silence) "WARNING: Possibly missing firmware for module"

`mkinitcpio-possibly-missing-firmware-warnings` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Every kernel update prints a wall of warnings and people assume their system is broken:

```
==> WARNING: Possibly missing firmware for module: 'aic94xx'
==> WARNING: Possibly missing firmware for module: 'wd719x'
==> WARNING: Possibly missing firmware for module: 'xhci_pci'
==> WARNING: Possibly missing firmware for module: 'qat_4xxx'
==> WARNING: Possibly missing firmware for module: 'bfa'
==> WARNING: Possibly missing firmware for module: 'qed'
```

**Cause.** mkinitcpio walks the modules it is about to include and notes any firmware file those modules *could* request that is not present in `/usr/lib/firmware`. `aic94xx`, `wd719x`, `bfa`, `qed` and `qat_4xxx` are enterprise SAS/SCSI/FC/QuickAssist drivers whose firmware is not redistributable and therefore not in `linux-firmware`. Unless you own that hardware, nothing is missing at runtime — the module simply never loads.

> **Audit corrected this record.** The 'do nothing' advice is right, but two of the three concrete commands are wrong. (1) `MODULES=(!aic94xx ...)` is not valid mkinitcpio syntax — I read `add_module()` in the mkinitcpio source: it handles a trailing `?` (ignore-errors) and nothing else; a leading `!` is not parsed, so the build will fail with 'module not found: !aic94xx'. (2) `qat_4xxx-firmware` does not exist — the AUR RPC returns resultcount 0 for it and for `qat-firmware`, so `yay -S qat_4xxx-firmware` is a fabricated package. (3) The `xhci_pci` warning is not an irreducible false positive: it is the Renesas uPD720201/202 firmware request, silenced by the AUR package `upd72020x-fw`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The correct action is **do nothing** — these are build-time notices about firmware a module *could* request, not a runtime failure. The system boots fine.

If you actually own the hardware (or just want a clean log), the real packages are:

```sh
yay -S aic94xx-firmware wd719x-firmware   # Adaptec SAS / WD719x SCSI
yay -S upd72020x-fw                        # silences the xhci_pci warning (Renesas uPD720201/202)
sudo mkinitcpio -P
```

There is no AUR package for `qat_4xxx`, `qed` or `bfa` firmware — those warnings cannot be cleared and are harmless.

Do **not** try to exclude modules with `MODULES=(!aic94xx)`. mkinitcpio has no `!` exclusion syntax (only a trailing `?` to make a module optional), and the invalid entry makes the build fail. These warnings mostly come from the *fallback* image, which is built without `autodetect` and therefore packs every driver by design — leave it that way, it is your recovery image.

**Verify.** `sudo mkinitcpio -P` completes; the last line is `==> Image generation successful` (warnings above it are irrelevant).

Sources: <https://forum.endeavouros.com/t/removing-missing-firmware-warnings-from-mkinitcpio/16510> · <https://forum.endeavouros.com/t/possibly-missing-firmware-for-module-aic94xx/19590> · <https://man.archlinux.org/man/mkinitcpio.conf.5>

---
