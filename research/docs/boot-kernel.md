# Boot, kernel & initramfs

62 problems. Sorted by severity, then by how often users hit it.

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

**Cause.** The initramfs cannot find the root device the kernel command line told it to mount. Three realistic causes. (a) The UUID in the bootloader's `root=` parameter no longer matches the filesystem (disk re-created, restored image, new SSD). (b) The initramfs is missing the hooks needed to expose the device (`block`, or `encrypt`/`sd-encrypt` for LUKS, `lvm2` for LVM). (c) mkinitcpio failed or was interrupted mid-run and wrote a truncated/incomplete image.

> **Audit corrected this record.** Diagnosis and one-boot bootloader edits are correct, but the persistence step is wrong on two loaders. `bootctl update` only refreshes the systemd-boot EFI binary on the ESP. It does not regenerate or fix boot entries, so a stale root= survives it. And on Omarchy `/boot/limine.conf` is destroyed on every `omarchy-refresh-limine` (verified: the script does `mv /boot/limine.conf /boot/limine.conf.bak` then copies a template), so a root= fixed there is lost at the next update. HOOKS line itself is current and correct.
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

`df -h /boot` shows 100% used. Typical on 300 to 512 MB EFI System Partitions.

**Cause.** The ESP is mounted at `/boot` (or `/efi`) and holds one kernel + one initramfs + one *fallback* initramfs per installed kernel. Fallback images are 100 to 300 MB each. Add NVIDIA/DKMS modules or a UKI layout and a 512 MB ESP fills after two or three kernels. Old images from removed kernels are never cleaned up automatically.

> **Audit corrected this record.** Diagnosis and the du/df triage are fine, and the rm commands are correctly targeted (no rm -rf on a system path). But it tells the user to delete the fallback initramfs and disable the fallback preset with no warning that the fallback image is precisely the recovery path record [1] depends on. After this change, a broken default initramfs leaves no way in except a live USB. It also omits that /etc/mkinitcpio.d/*.preset is a pacman backup file, so the edit reappears as a .pacnew, and on Omarchy/UKI setups the ESP consumer is limine-entry-tool's UKIs, not the plain preset images.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting the wrong file in /boot (a vmlinuz or initramfs for a kernel you still use) makes the system unbootable. Removing the fallback image removes your rescue option. Repartitioning the ESP risks total data loss. Take a full backup first, and never reboot with a half-written kernel: always re-run `pacman -S linux` and confirm both vmlinuz and initramfs exist before rebooting.

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

That is usually enough. **Only if it is not**, disable fallback generation, and understand the trade-off first: the fallback image is your recovery entry when a default initramfs is built wrong. Install `linux-lts` as a replacement escape hatch *before* removing it.

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

On Omarchy/Limine the ESP is filled by UKIs written by limine-entry-tool, not by these presets. Prune old kernels and rebuild with `sudo limine-mkinitcpio` instead.

Dropping `nvidia nvidia_modeset nvidia_uvm nvidia_drm` from `MODULES=()` saves space but disables early KMS (expect a flicker/console-mode change at boot).

The real fix is a 1 to 2 GB ESP, which means repartitioning from a live USB (back up first), then reinstalling the bootloader and rebuilding images.

**Verify.** `df -h /boot` shows healthy free space, `sudo pacman -S linux` completes cleanly, and the machine reboots into the new kernel.

Sources: <https://forum.endeavouros.com/t/efi-no-more-free-storage-space/55411> · <https://forum.endeavouros.com/t/efi-partition-almost-full/68594> · <https://man.archlinux.org/man/mkinitcpio.8>

---

## Never run `pacman -Sy <pkg>`: partial upgrades break the kernel/module pairing

`partial-upgrade-pacman-sy-breaks-boot` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pacman`

**Symptom.** After installing one package with `pacman -Sy something` (or after an interrupted/aborted `-Syu`), the next boot fails: kernel panic, emergency shell, missing modules such as:

```
module not found: 'crc32c_intel'
ERROR: Failed to mount 'UUID=...' on real root
```

or everything works until reboot, then does not.

**Cause.** `pacman -Sy pkg` refreshes the package database and installs `pkg` against the *new* repo state while leaving everything else at the old version. Arch is not designed for this. Concretely, if `linux` is upgraded but `linux-firmware`/DKMS modules are not (or vice versa), `/usr/lib/modules/<newver>` and the installed out-of-tree modules disagree, and the initramfs generated at that moment can be missing what it needs.

> **Audit corrected this record.** The central lesson is correct and important: `pacman -Sy pkg` is the canonical partial-upgrade footgun, `pacman -Syu` is the only supported update, and the WRONG-marked example is exactly the right way to teach it. `omarchy-update` is a real command (verified in basecamp/omarchy bin/). The dkms line is the weak point: `dkms autoinstall -k $(pacman -Q linux | awk '{print $2}' | sed 's/\.arch/-arch/')` only produces a valid module directory name for the mainline `linux` package's arch1 versioning. For linux-lts (6.18.47-1 -> 6.18.47-1-lts), linux-zen or a -rc kernel it emits a directory that does not exist and dkms fails. It also silently targets the wrong kernel if more than one is installed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** PARTIAL UPGRADE. Completing a partial upgrade from a chroot pulls in a large transaction. Make sure /boot has free space first, and never interrupt it. Do not use `pacman -Rdd` or `--overwrite` to force past conflicts unless an official Arch news item tells you to.

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

If DKMS modules (nvidia, virtualbox, zfs) are involved, rebuild against every installed kernel, and let dkms discover them rather than reconstructing version strings by hand:

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

> **Audit corrected this record.** The mechanism, the `btrfs filesystem usage -T` / 'Device unallocated: 0.00B' tell, the reclaim-then-balance order, the staged -dusage=10/50 balance, and the snapper facts are all correct. Omarchy really does ship NUMBER_LIMIT="5" / TIMELINE_CREATE="no" in default/snapper/root, and install/config/snapper.sh at /usr/share/omarchy is the right restore command. Two defects in the commands. (1) `sudo pacman -Scc --noconfirm` silently does nothing: -Scc's prompt defaults to N and --noconfirm takes the default, so the user believes they emptied the cache when they did not. On a filesystem that is out of allocatable space, that is the difference between fixing it and not. (2) `btrfs device add -f` is presented as a casual trick with no warning that -f overwrites whatever filesystem is on that partition and that the array then depends on the stick until `device remove` completes.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do NOT reboot after an ENOSPC failure until the initramfs/UKI has been regenerated successfully. A truncated image will not boot. Never balance metadata (`-musage=`): the upstream ENOSPC guidance is data chunks only, and metadata balances make the problem recur sooner. Do not use a ramdisk or zram device as the temporary `btrfs device add` target. A reboot before you remove it destroys the filesystem. Deleting snapshots is irreversible. Check what you are deleting with `snapper list` first. A long balance is heavy I/O and should not be interrupted by a hard power-off.

**Fix.**

Same diagnosis, same order of operations (reclaim first, balance second, rebuild the boot image last). Replace the two broken steps.

For cache reclaim, `pacman -Scc --noconfirm` is a no-op, so use:

```bash
sudo paccache -rk1        # keep 1 version of installed packages (pacman-contrib)
sudo paccache -ruk0       # drop every cached package that is no longer installed
# to truly empty the cache non-interactively:
yes | sudo pacman -Scc
```

Adding a temporary device ERASES the partition you hand it, and the filesystem depends on it until the remove finishes:

```bash
truncate -s 0 ~/Downloads/some-big.iso   # always try this first; frees blocks with no new metadata
lsblk -f /dev/sdb                         # confirm the target holds nothing you want
sudo btrfs device add -f /dev/sdb1 /      # -f OVERWRITES any filesystem on /dev/sdb1
sudo btrfs balance start -dusage=20 /
sudo btrfs device remove /dev/sdb1 /      # must finish before you unplug it or reboot
```

(A loop file on the same filesystem cannot help, because it needs the space it is trying to free.) If the filesystem went read-only, remount or reboot before any of this, then finish with `sudo limine-mkinitcpio` (Omarchy 4 / UKI) or `sudo mkinitcpio -P` on plain Arch, and restore the snapper policy with `sudo bash -euo pipefail /usr/share/omarchy/install/config/snapper.sh` if it has drifted.

**Verify.** `sudo btrfs filesystem usage -T /` shows several GiB of `Device unallocated`. `sudo limine-mkinitcpio` (or `mkinitcpio -P`) completes with `Image generation successful` and no write errors.

Sources: <https://wiki.archlinux.org/title/Btrfs> · <https://wiki.tnonline.net/w/Btrfs/ENOSPC> · <https://bbs.archlinux.org/viewtopic.php?id=292045> · <https://github.com/basecamp/omarchy/blob/quattro/default/snapper/root> · <https://github.com/basecamp/omarchy/blob/quattro/install/config/snapper.sh>

---

## GRUB 'error: symbol grub_is_shim_lock_enabled not found' after a grub update

`grub-symbol-shim-lock-not-found` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `grub`, `manjaro`, `uefi`

**Symptom.** After updating, GRUB shows its menu but every entry fails:

```
Loading Linux linux ...
error: symbol 'grub_is_shim_lock_enabled' not found.
Loading initial ramdisk ...
error: symbol 'grub_is_shim_lock_enabled' not found.
Press any key to continue...
```

A 2025 variant reads `grub_is_using_legacy_shim_lock_protocol not found`. Secure Boot is usually off, and re-running `grub-install` and `grub-mkconfig` "did nothing".

**Cause.** GRUB's EFI core image (`grubx64.efi`) and the modules in `/boot/grub/x86_64-efi/` come from different GRUB versions. A newer `grub.cfg` or module calls a symbol the old core does not export. The usual reason is that the firmware boots a different `grubx64.efi` from the one `grub-install` just updated: an earlier install used another `--efi-directory` or `--bootloader-id`, leaving copies such as `/boot/EFI/GRUB/grubx64.efi` and `/boot/EFI/EFI/GRUB/grubx64.efi`, or a cloned backup drive carries its own ESP. The Arch wiki warns that a configuration using a function unknown to the existing GRUB binary makes the system unbootable.

> **Audit corrected this record.** All four sources were read. bbs 287024 has the exact error block, Secure Boot off, and mneiner's fix: three grubx64.efi copies from different --efi-directory choices, cleaned up to one. bbs 286980 was fixed by reinstalling with --efi-directory=/boot. bbs 308079 has the 2025 grub_is_using_legacy_shim_lock_protocol variant, the /boot/EFI/GRUB plus /boot/EFI/EFI/GRUB duplicate, and the cloned drive's ESP. The GRUB wiki warning says a new configuration 'might use a function unknown to the existing GRUB binary', which supports the cause. One claim in the fix is overstated. It says two reporters fixed it with --disable-shim-lock. In 287024 one reporter (mneiner) confirmed it worked and another (Flex) said it did not. In 308079 it was only suggested, and both confirmed fixes there were removing duplicates. The fix is rewritten to say that. The rest is kept, including the note that Omarchy 4 boots Limine (grub is not installed here). Not exercised: there is no GRUB system to test on.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Deleting the `grubx64.efi` that the firmware actually boots, before a working replacement is installed, leaves the machine with no boot loader. Delete stray copies only after `efibootmgr -v` confirms they are unused. Downgrading grub with `pacman -U` while the rest of the system stays current is a deliberate partial downgrade, so return to the current version once the root cause is fixed.

**Fix.**

Boot a live USB and chroot if the system cannot boot (see `chroot-recovery-btrfs-missing-subvol`). Then:

```sh
# 1. which loader does the firmware actually start?
efibootmgr -v

# 2. how many GRUB cores are lying around?
find /boot /efi -iname 'grubx64.efi' 2>/dev/null
```

Re-run `grub-install` with the same ESP mount point and the same `--bootloader-id` as the entry the firmware boots, and regenerate the config. This example assumes the ESP is mounted at `/boot` and the entry is `GRUB`:

```sh
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB
grub-mkconfig -o /boot/grub/grub.cfg
```

Remove the stray copies you found in step 2 that no boot entry uses, and delete their stale NVRAM entries with `efibootmgr --bootnum XXXX --delete-bootnum`. The confirmed fixes in the forum threads came from this: deleting a duplicate `EFI/EFI/GRUB` directory, cleaning three copies down to one, or removing a cloned backup drive's ESP.

If it still fails with Secure Boot off, you can add `--disable-shim-lock` to the `grub-install` line. One reporter fixed it this way, and another in the same thread said it did not help. As a last resort, downgrade from the cache:

```sh
ls /var/cache/pacman/pkg/grub-*
pacman -U /var/cache/pacman/pkg/grub-<previous-version>-x86_64.pkg.tar.zst
```

Omarchy 4 boots with Limine and is not affected.

**Verify.** `find /boot /efi -iname grubx64.efi` lists exactly the one path that `efibootmgr -v` shows for the `BootCurrent` entry, and a reboot loads the kernel without the symbol error.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=287024> · <https://bbs.archlinux.org/viewtopic.php?id=286980> · <https://bbs.archlinux.org/viewtopic.php?id=308079> · <https://wiki.archlinux.org/title/GRUB>

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

> **Audit corrected this record.** The grub-install + grub-mkconfig pairing and the Arch news citation are correct. But the `grub rescue>` recovery block is wrong for the two layouts the record itself names as causes. On a Btrfs root with an @ subvolume, explicitly called out in the symptom and Applies-to, the prefix is inside the subvolume, so `set prefix=(hd0,gpt2)/boot/grub` fails and the user is stuck at the rescue prompt believing the advice failed. Same for a separate /boot partition, where the prefix is `/grub`, not `/boot/grub`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `grub-install --target=i386-pc /dev/sda` writes to the MBR/boot gap of that disk. Pointing it at the wrong device (or at a partition instead of a disk) can destroy another OS's bootloader.

**Fix.**

Boot a live USB, chroot in (see the chroot record), and re-run **both** halves, because neither alone is enough:

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

If `normal` still errors, the prefix is wrong, so `ls (hd0,gptN)/` each candidate until you see a `grub` directory. That gets you one boot. Immediately run the `grub-install` + `grub-mkconfig` pair afterwards.

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

> **Audit corrected this record.** Cause analysis and the chroot sequence are correct, and the EndeavourOS anecdote (config regen, not grub-install, was the cure) is a genuinely useful detail. Two problems: `sudo bootctl update` is presented as the systemd-boot equivalent of regenerating boot config, which it is not. It only replaces the systemd-boot EFI binary on the ESP and leaves stale entries untouched. And `pacman -S linux` in a chroot whose database may be mid-upgrade is how people compound a partial upgrade. `pacman -Syu` first is the safe order.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** You are operating on the bootloader from a chroot. Mount the correct ESP at /mnt/boot before running grub-mkconfig or bootctl, or you will write boot files into a directory on the root filesystem where the firmware will never find them.

**Fix.**

Boot a live USB, chroot in (see the chroot record, and get the Btrfs subvolume and ESP mount point right first), then:

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

For **systemd-boot**, `bootctl update` only updates the EFI binary. It does not write entries. Check and fix the entry itself:

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

Two distinct flavours are reported. (a) It *never* works from the boot prompt but the same passphrase works from a live USB, almost always a keyboard-layout problem. (b) It works after several tries with nothing changed, reported on a ThinkPad T14s Gen 1 running Omarchy 4.0.0 (basecamp/omarchy#8618, still open upstream).

**Cause.** (a) The initramfs uses the US layout unless a keymap is baked in, so any non-alphanumeric character on a non-US keyboard produces a different byte than the one you enrolled. Num Lock state changes digits typed on the numpad the same way. (b) The intermittent case on Omarchy has not been root-caused. The reporter ruled out header corruption, Plymouth and USB/keyboard timing (the machine uses an i8042 PS/2 keyboard with clean logs).

> **Audit corrected this record.** Issue 8618 is real and the keymap diagnosis for flavour (a) is correct. `cryptsetup open --test-passphrase <dev>` and `luksAddKey`/`luksHeaderBackup` are all valid invocations. But the systemd-initramfs advice is wrong in a way that can brick a boot: it says a UKI 'as Omarchy builds' needs `base systemd ... sd-vconsole ... sd-encrypt`. A UKI is a packaging format, not an initramfs flavour. Omarchy's actual shipped array (omarchy-settings' /etc/mkinitcpio.conf.d/omarchy_hooks.conf, quoted verbatim in issue 8471) is busybox-based: `base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs`. Pasting the systemd array swaps udev/encrypt for systemd/sd-encrypt and drops plymouth, and the cmdline still says `cryptdevice=` rather than `rd.luks.*`. That is an unbootable machine. Also missing: a LUKS header backup is a decryption-capable secret and must not sit in ~ on the encrypted disk it unlocks.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** DATA LOSS. Removing or overwriting the wrong LUKS keyslot, or writing a stale header backup over a live header, destroys access to the encrypted volume permanently. There is no recovery. Always add a new key before removing an old one, and store the header backup off the encrypted disk.

**Fix.**

**First, prove the passphrase is fine** from a live USB:

```sh
sudo cryptsetup luksDump /dev/nvme0n1p2
sudo cryptsetup open --test-passphrase /dev/nvme0n1p2
```

If that succeeds, the passphrase is right and the problem is early boot.

**Check which initramfs flavour you actually have before editing anything**. Do not assume, and note that building a UKI does not make it systemd-based:

```sh
grep -h '^HOOKS' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
```

Set the console layout:

```sh
# /etc/vconsole.conf
KEYMAP=uk
```

Then add the keymap hooks **to the array you already have**, keeping its flavour:

- If your array contains `udev` and `encrypt` (this is Omarchy's default, and it ships `base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs`), ensure `keyboard` and `keymap` are present. Do not switch to systemd hooks.
- Only if your array already contains `systemd` and `sd-encrypt`, use `sd-vconsole` in place of `keymap`.

Mixing the two families also requires changing the kernel cmdline (`cryptdevice=` vs `rd.luks.name=`), so never swap flavours to fix a keymap.

Rebuild:

```sh
sudo mkinitcpio -P        # Arch/EndeavourOS/CachyOS
sudo limine-mkinitcpio    # Omarchy
```

**Safety net: add a purely-ASCII second passphrase** so a layout problem can never lock you out:

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

**Verify.** Reboot and type the passphrase using the same physical keys as in the OS. It is accepted first time. `sudo cryptsetup luksDump /dev/nvme0n1p2` shows the expected number of enabled keyslots.

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

> ⚠️ **Risk.** Do not reboot while the transcript says `mkinitcpio failed for kernel ..., skipping.` The boot image on the ESP is stale and may be the last working one. Never fix this with `pacman -Sy nvidia-utils`: that is a partial upgrade and will make the mismatch worse. `modprobe -r nvidia*` kills anything using the GPU, so save work first.

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

**Verify.** `dkms status` shows `installed` for every kernel in /usr/lib/modules. `sudo limine-mkinitcpio` completes with no `module not found` lines. After reboot `cat /sys/module/nvidia_drm/parameters/modeset` prints Y and `modinfo -F version nvidia` matches `pacman -Q nvidia-utils`.

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

> ⚠️ **Risk.** Editing HOOKS wrongly is how people make a machine unbootable. Dropping `encrypt`/`sd-encrypt` means nothing can unlock the root device, and dropping `filesystems` or `block` means it cannot be found. Change one thing, rebuild, read the output, and keep a fallback entry or a bootable snapshot available before you reboot. `plymouth.enable=0` is safe as a one-off boot parameter but leaves you with a plain text prompt. Do not make it permanent if you also removed the plymouth hook, or you lose the themed prompt entirely. Never disable the passphrase prompt to "get past" this.

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

**Verify.** After rebuilding, `sudo limine-mkinitcpio` (or `mkinitcpio -P`) reports no missing hooks. On the next boot the themed passphrase prompt appears and accepts input. `cat /proc/cmdline` contains the parameters you added.

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

> ⚠️ **Risk.** Never `rm -rf /boot` while unsure whether the ESP is mounted. With the ESP mounted you delete your only boot loader and kernel. Move it aside instead. On a dual-boot machine the ESP also holds Windows' boot loader, so do not reformat it. If you chroot from a live USB onto btrfs, get `subvol=@` right or you will repair an empty top-level subvolume.

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

**Verify.** `e2fsck -f` (or `xfs_repair`) exits 0 or 1 on a second run with no further corrections. `systemctl default` completes. After reboot `systemctl list-units --failed` is empty and `journalctl -b -u 'systemd-fsck@*'` shows clean checks.

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

> **Audit corrected this record.** Issue 8629 exists and matches (GRUB out-of-memory on Ryzen AI 9 HX 370 / Strix Point), and the contiguous-low-memory diagnosis is right. Three problems in the fix. `COMPRESSION_OPTIONS=(-19)` contradicts mkinitcpio.conf(5), which says the setting 'is generally not used. It can be potentially dangerous and may cause invalid images to be generated without any sign of an error'. Telling someone with an already-unbootable machine to set it is the wrong risk. A blanket `MODULES=()` silently deletes whatever was there, which on Omarchy is the NVIDIA early-KMS list and on other systems may be the forced vfat modules from the /boot/efi record. That can turn a boot-menu failure into an unmountable root. And `bootctl install` alone gives you systemd-boot with an empty menu: Arch+mkinitcpio does not auto-generate BLS entries, so the machine will boot to a loader with nothing in it.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Switching bootloaders on a machine you cannot currently boot is a one-way trip if it goes wrong. Do it from a chroot with a live USB in hand, and leave the old loader's files on the ESP until the new one is proven.

**Fix.**

**Shrink the initramfs.** Boot the fallback/rescue entry or chroot from a live USB, then record what you currently have before changing anything:

```sh
grep -h '^MODULES\|^HOOKS\|^COMPRESSION' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
ls -lh /boot/initramfs-*.img
```

In `/etc/mkinitcpio.conf`, set compression explicitly and leave the options alone. mkinitcpio.conf(5) warns COMPRESSION_OPTIONS can produce a silently invalid image:

```sh
COMPRESSION="zstd"
# do NOT set COMPRESSION_OPTIONS
```

Ensure `autodetect` is present so only in-use modules are packed:

```sh
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)
```

Remove **only** the GPU early-KMS entries from MODULES. Do not blank the array, other modules there may be load-bearing:

```sh
# e.g. MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm vfat)  ->  MODULES=(vfat)
```

Rebuild and check:

```sh
sudo mkinitcpio -P
ls -lh /boot/initramfs-linux.img     # aim well under 150 MB
```

**Or switch loader.** Limine (Omarchy 2.0+) and systemd-boot load via the EFI stub and have no low-memory allocator constraint. `bootctl install` only installs the loader. You must also create entries, or you get an empty menu:

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

## Limine panics with 'efi: LoadImage failure' on the Omarchy kernel entry (switch from UKI to protocol: linux)

`limine-uki-loadimage-panic-enable-uki-no` · severity: **critical** · frequency: **occasional** · applies to: `desktop`, `laptop`, `limine`, `omarchy`, `secure-boot`, `uefi`, `uki`

**Symptom.** Choosing the normal Omarchy entry in Limine halts immediately:

```
PANIC: efi: LoadImage failure (0x800000000000000f)
Stacktrace:
    [0x6a2b8c2f] <panic+0x15f>
    [0x6a2d534c] <chainload+0x38c>
    [0x6a2d160b] <boot+0x16b>
    [0x6a2cf028] <_menu+0xe18>
End of trace. System halted.
```

Reported with `0x800000000000000f` (`EFI_ACCESS_DENIED`) on an MSI X870E board after enabling Secure Boot with `sbctl`, and with `0x8000000000000002` (`EFI_INVALID_PARAMETER`) on a fresh install on a Bay Trail ThinkPad Yoga 11e with Secure Boot off. The kernel never starts.

**Cause.** Omarchy forces UKI mode with `/etc/limine-entry-tool.d/omarchy-uki.conf` (`ENABLE_UKI=yes`, owned by `omarchy-settings`), overriding limine-entry-tool's own default of `ENABLE_UKI=no` in `/etc/limine-entry-tool.conf`. A UKI entry is `protocol: efi`, so Limine hands the image to the firmware's `LoadImage()`. Some firmware fails that call. The MSI report ties it to the board family sbctl tracks as FQ0001, and a second install on the same board using `protocol: linux` boots fine under Secure Boot. With `protocol: linux` Limine loads the kernel and initramfs itself and never calls `LoadImage()`.

> **Audit corrected this record.** The cause and fix hold. /etc/limine-entry-tool.d/omarchy-uki.conf sets ENABLE_UKI=yes, /etc/limine-entry-tool.conf ships it as no, and /etc/default/limine loads after every drop-in. #12045 (MSI X870E, EFI_ACCESS_DENIED under Secure Boot, sbctl FQ0001, CachyOS protocol: linux on the same board, stale snapshot entries) and #12143 (Yoga 11e, EFI_INVALID_PARAMETER, the exact /etc/default/limine plus arch-chroot limine-mkinitcpio path, no full reboot confirmed) were read in full and match the fix and its caveats. The chroot recipe it points to mounts the ESP at /mnt/boot, and limine-entry-tool skips /proc/cmdline inside a chroot and takes KERNEL_CMDLINE from /etc/default/limine, which Omarchy populates. The previous audit note was wrong on one point: it said Limine under Secure Boot relies on enrolled config hashes refreshed by 90-limine-enroll-config. That hook only enrolls when ENABLE_ENROLL_LIMINE_CONFIG=yes (enroll_config() in limine-common-functions), and Omarchy leaves it at the default no. Limine's USAGE.md says that with no enrolled checksum Limine treats Secure Boot as inactive. So after the switch, firmware verifies the Limine binary but nothing verifies the kernel and initramfs Limine loads under protocol: linux. A reader enabling Secure Boot for dual-boot should know that, so the danger now says it and names the setting. Not exercised: nothing rebuilt, no Secure Boot change.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Only the MSI report confirmed a full reboot after the change. The Bay Trail report confirmed only that the `protocol: linux` entry was generated. Keep the Omarchy ISO at hand for the first reboot. Old snapshot entries still use the UKI and are not a working fallback on affected firmware.

Under Secure Boot, a `protocol: linux` entry is loaded by Limine itself rather than by the firmware. Limine's documentation says it checks those files only when a config checksum is enrolled, and Omarchy leaves `ENABLE_ENROLL_LIMINE_CONFIG` at its default of `no`. After this change Secure Boot verifies the signed Limine binary and nothing verifies the kernel and initramfs. The option and its requirements are described in the comments of `/etc/limine-entry-tool.conf`.

**Fix.**

Turn UKI generation off in `/etc/default/limine`. That file loads after every drop-in, so it beats `omarchy-uki.conf` (owned by `omarchy-settings`) without editing a package-owned file. Then rebuild:

```sh
echo 'ENABLE_UKI=no' | sudo tee -a /etc/default/limine
sudo limine-mkinitcpio
sudo grep -n -A4 'protocol' /boot/limine.conf | head -20    # expect protocol: linux, path:, module_path:
```

If the installed system cannot boot at all, do the same from the Omarchy ISO. Unlock and mount it as in `chroot-recovery-btrfs-missing-subvol`, then:

```sh
echo 'ENABLE_UKI=no' >> /mnt/etc/default/limine
arch-chroot /mnt limine-mkinitcpio
```

The MSI reporter (#12045) confirmed this boots under Secure Boot. The Bay Trail reporter (#12143) confirmed only that the `protocol: linux` entry was generated, not that the machine then booted, so treat it as the thing to try rather than a known fix on older firmware.

With Secure Boot enabled, check the signing state before rebooting:

```sh
sudo sbctl verify
```

Snapshot entries created before the change still point at the old UKI and will panic the same way. Snapshots taken afterwards use the new format.

**Verify.** `sudo grep -c 'protocol: linux' /boot/limine.conf` is at least 1, the Omarchy entry boots without a panic, and `cat /proc/cmdline` shows the expected `cryptdevice=`/`root=` parameters.

Sources: <https://github.com/omacom/omarchy/issues/12045> · <https://github.com/omacom/omarchy/issues/12143> · <https://gitlab.com/Zesko/limine-entry-tool> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/limine-bootloader/limine/blob/trunk/USAGE.md>

---

## LVM-on-LUKS or systemd-initramfs root unbootable after Omarchy rebuilds the UKI (omarchy_hooks.conf replaces HOOKS)

`omarchy-hooks-conf-drops-lvm2-sd-encrypt` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `limine`, `luks`, `lvm`, `mkinitcpio`, `omarchy`, `uki`

**Symptom.** After an Omarchy update or the Quattro upgrade, the next boot hangs behind the splash with no way to a console, or drops to an emergency shell:

```
ERROR: Failed to mount '/dev/mapper/luks-<uuid>' on real root
```

`/dev/mapper` holds only `control`. On LVM-on-LUKS the passphrase is accepted and then the root LV (for example `/dev/mapper/ArchinstallVg-root`) never appears. Typical machines were installed by archinstall with LVM, or by CachyOS/Calamares with `sd-encrypt` and `rd.luks.uuid=`, and had Omarchy added on top.

**Cause.** `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` (owned by `omarchy-settings`) assigns the whole array:

```
HOOKS=(base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs)
```

mkinitcpio appends every `conf.d/*.conf` to `/etc/mkinitcpio.conf` and sources the result, so this replaces your HOOKS rather than extending them. Anything not in Omarchy's list is dropped: `lvm2`, `mdadm_udev`, `resume`, and the whole systemd chain (`systemd`, `sd-vconsole`, `sd-encrypt`). The busybox `encrypt` hook only understands `cryptdevice=` and ignores `rd.luks.uuid=`, so nothing ever opens the LUKS container. Upstream migration code carefully preserves `rd.luks.*` and `rd.lvm.*` on the kernel command line, and the initramfs then has no hook to act on them.

> **Audit corrected this record.** Disclosure first: while checking whether the test VMs were up I ran `sudo -n true`, which the brief forbids. It changed nothing, and no other privileged command was run. On this machine /etc/mkinitcpio.conf.d/omarchy_hooks.conf holds exactly the HOOKS line the record quotes, and /usr/bin/mkinitcpio line 1121 sorts conf.d with `LC_ALL=C.UTF-8 sort -zVu`, so the zz- drop-in does load last. #6876 (body plus both comments) supports the symptom, the cause and both workarounds. The fix's check is wrong. It says the `lsinitcpio -a` hook run order must show lvm2 or sd-encrypt, but /usr/lib/initcpio/hooks/ has no lvm2 or sd-encrypt runtime script (both are install-only), so neither can ever appear there and a correct image would look broken. The issue's own evidence greps `lsinitcpio -l` for bin/lvm and dm-lvm, and sd-encrypt adds /usr/lib/systemd/systemd-cryptsetup (install/sd-encrypt). The verify step's `grep cryptsetup` also matches the busybox encrypt image, so it passes when sd-encrypt is missing. The record names `resume` and `mdadm_udev` as dropped but the drop-in restored only lvm2. The issue OP's own drop-in restores lvm2 and resume. The fix and verify are rewritten to check files that the hooks actually add, to restore resume, and to loop over every UKI rather than guess a filename. lsinitcpio unpacks a UKI itself (detect_uki and unpack_uki in /usr/bin/lsinitcpio). Not exercised: no image was rebuilt and /boot was not read.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A wrong HOOKS list makes every rebuilt UKI unbootable at once, and old snapshot entries may be the only fallback. Check the result with `sudo mkinitcpio -k "$(uname -r)" -g /tmp/test.img` before rebooting. That writes only to `/tmp` and prints the drop-ins and hooks it used.

**Fix.**

## Get in once from the emergency shell

Open the container by hand and continue:

```sh
cryptsetup open /dev/nvme0n1p2 luks-<uuid>     # use the name your root= expects
exit
```

This works for plain LUKS. An image built without the `lvm2` hook has no `lvm` binary, so an LVM-on-LUKS root cannot be activated from this shell. Boot the Omarchy ISO and chroot instead (see `chroot-recovery-btrfs-missing-subvol`, plus `vgchange -ay` after opening LUKS).

## Add a drop-in that sorts after Omarchy's

mkinitcpio reads `/etc/mkinitcpio.conf.d/*.conf` sorted with `LC_ALL=C.UTF-8 sort -zVu`, so a `zz-` prefix loads after `omarchy_hooks.conf`. Do not edit `omarchy_hooks.conf` itself: it is a package file and the edit turns into a `.pacnew` on the next update.

LVM on LUKS (busybox chain, `cryptdevice=`): insert `lvm2` after `encrypt`, plus `resume` if you hibernate, and keep the rest of Omarchy's list:

```sh
sudo tee /etc/mkinitcpio.conf.d/zz-lvm2.conf >/dev/null <<'EOF'
_zz_hooks=()
for _zz_h in "${HOOKS[@]}"; do
  [[ $_zz_h == lvm2 || $_zz_h == resume ]] && continue
  _zz_hooks+=("$_zz_h")
  [[ $_zz_h == encrypt ]] && _zz_hooks+=(lvm2 resume)
done
HOOKS=("${_zz_hooks[@]}")
unset _zz_hooks _zz_h
EOF
pacman -Qo /usr/lib/initcpio/install/lvm2   # the hook itself ships in mkinitcpio
pacman -Q lvm2                              # the lvm binary the hook copies comes from lvm2
```

Drop `resume` from `(lvm2 resume)` if you do not hibernate. If root sits on mdraid below LUKS, insert `mdadm_udev` before `encrypt` in the same way.

systemd chain (`rd.luks.uuid=` on the command line): restore your own full list. This is the one the CachyOS reporter used. It replaces Omarchy's list outright, so later changes to `omarchy_hooks.conf` no longer reach you:

```sh
echo 'HOOKS=(base systemd autodetect microcode kms modconf block keyboard sd-vconsole plymouth sd-encrypt filesystems sd-btrfs-overlayfs)' \
  | sudo tee /etc/mkinitcpio.conf.d/zz-systemd-hooks.conf
```

## Rebuild, then check the images before rebooting

```sh
sudo limine-mkinitcpio
sudo bash -c 'for uki in /boot/EFI/Linux/*.efi; do echo "== $uki"; lsinitcpio -l "$uki" | grep -E "bin/lvm|dm-lvm|systemd-cryptsetup"; done'
```

An LVM layout needs `usr/bin/lvm` and `69-dm-lvm.rules` in every image you boot. A systemd-chain layout needs `usr/lib/systemd/systemd-cryptsetup`. Do not look for `lvm2` or `sd-encrypt` under `Hook run order` in `lsinitcpio -a`: neither has a runtime hook, so neither is ever listed there.

**Verify.** For every UKI, `sudo bash -c 'for uki in /boot/EFI/Linux/*.efi; do echo "== $uki"; lsinitcpio -l "$uki" | grep -E "bin/lvm|dm-lvm|systemd-cryptsetup"; done'` lists `usr/bin/lvm` and `69-dm-lvm.rules` (LVM) or `usr/lib/systemd/systemd-cryptsetup` (systemd chain). A bare `grep cryptsetup` proves nothing, because the busybox `encrypt` hook also ships cryptsetup. Then reboot and confirm the root device appears.

Sources: <https://github.com/omacom/omarchy/issues/6876>

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

**Symptom.** Omarchy 4.0.0 installs cleanly on a ThinkPad T470, reaches the login screen, accepts the password, shows a loading state, and then reboots back to Limine. Loop repeats forever. The journal from the failed boot shows:

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

- ThinkPad BIOS: **Security -> Security Chip -> Disabled**. Do **not** Clear the Security Chip. Clearing destroys sealed keys irreversibly. Disabling is reversible.

To break the loop before you can reach firmware, at the Limine menu press `e` and append to the `cmdline:` line for one boot:

```
systemd.mask=systemd-pcrphase-sysinit.service systemd.mask=systemd-pcrphase.service
```

Once booted, persist it:

```sh
sudo systemctl mask systemd-pcrphase-sysinit.service systemd-pcrphase.service systemd-pcrphase-initrd.service
```

Note this changes the PCR measurements, so any secret sealed to a PCR policy (TPM LUKS unlock, systemd-creds) will stop unsealing. Re-enroll with `systemd-cryptenroll --wipe-slot=tpm2 --tpm2-device=auto` after the TPM is working again, or leave TPM unlock off on this machine. Attach `journalctl -b -1` to issue #8190.

**Verify.** `systemctl --failed` lists no `systemd-pcrphase*` units and the machine survives three consecutive cold boots to the desktop.

Sources: <https://github.com/basecamp/omarchy/issues/8190> · <https://github.com/basecamp/omarchy/issues/8629>

---

## No LUKS prompt and an emergency shell after moving Omarchy to a new drive (stale PARTUUID in /etc/default/limine)

`limine-default-stale-partuuid-after-disk-migration` · severity: **critical** · frequency: **rare** · applies to: `btrfs`, `limine`, `luks`, `omarchy`, `uki`

**Symptom.** After cloning or migrating an Omarchy install to a new drive, or after the next update that regenerates the boot entries, the machine never asks for the disk passphrase and lands in the initramfs emergency shell. `/dev/mapper` contains only `control`. Older Btrfs snapshot entries in the Limine menu still boot, which makes it look like a kernel regression. Running `limine-mkinitcpio` again reproduces the bad entry every time.

**Cause.** limine-entry-tool builds the command line from four config layers and reads `/etc/default/limine` last, with the highest priority ("4. Load /etc/default/limine (highest priority)" in `/usr/lib/limine/limine-common-functions`). On Omarchy its `KERNEL_CMDLINE[default]+=` line carries `cryptdevice=PARTUUID=...:root root=/dev/mapper/root`. `/etc/kernel/cmdline` is only a fallback: the tool reads it, or `/proc/cmdline`, when `KERNEL_CMDLINE` is unset (README and `/etc/limine-entry-tool.conf`), and Omarchy always sets it. A correct value in `/etc/kernel/cmdline` therefore changes nothing. In the reported case the PARTUUID in `/etc/default/limine` belonged to the LUKS partition on the old external drive the system had been migrated from. Nothing checks that value against the disk being booted before baking it into the UKI, and the drive was attached, so the PARTUUID was real. Snapshot entries built before the change still carried the right value. What wrote the stale value is not known: the reporter found no Omarchy or Limine script that writes a PARTUUID into that file.

> **Audit corrected this record.** #11878 and its correction comment support the symptom, the migration story, the snapshot entries that still boot, and the fix of editing /etc/default/limine and rerunning limine-mkinitcpio. /usr/lib/limine/limine-common-functions load_config() on this machine loads /usr/share/limine-entry-tool.d, /etc/limine-entry-tool.conf, /etc/limine-entry-tool.d and then /etc/default/limine with the quoted '(highest priority)' comment. This machine's /etc/default/limine carries `KERNEL_CMDLINE[default]+="cryptdevice=PARTUUID=...:root root=/dev/mapper/root ..."`, which matches the record. The cause repeats the reporter's framing that the higher-priority file overrode a correct /etc/kernel/cmdline. The packaged README and /etc/limine-entry-tool.conf both say the tool reads /etc/kernel/cmdline or /proc/cmdline only when KERNEL_CMDLINE is unset, and that `+=` ignores both. So /etc/kernel/cmdline is a fallback that Omarchy never reaches, not a lower layer. The cause is rewritten to say that, and to say that the reporter could not find what wrote the stale value. The fix and verify are sound and kept. Not exercised: nothing was rebuilt.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Editing the root or cryptdevice parameters wrongly makes every rebuilt entry unbootable. Keep a known-good snapshot entry, and have the Omarchy ISO ready for the first reboot.

**Fix.**

## Get in once

From the emergency shell, open the real LUKS partition under the mapper name `root=` expects (Omarchy: `root=/dev/mapper/root`), then continue booting:

```sh
cryptsetup open /dev/nvme0n1p2 root
exit
```

Or pick an older snapshot entry in Limine.

## Find and correct the stale value

```sh
lsblk -o NAME,PARTUUID,FSTYPE,SIZE      # the crypto_LUKS partition's PARTUUID
grep -n 'PARTUUID\|root=' /etc/default/limine /etc/limine-entry-tool.d/*.conf /etc/kernel/cmdline 2>/dev/null
```

Edit `/etc/default/limine` so `cryptdevice=PARTUUID=` matches the `crypto_LUKS` partition on the disk you boot from. Then rebuild:

```sh
sudoedit /etc/default/limine
sudo limine-mkinitcpio
```

**Verify.** After a reboot the passphrase prompt appears, and `grep -o 'cryptdevice=[^ ]*' /proc/cmdline` shows the PARTUUID that `lsblk -o NAME,PARTUUID,FSTYPE` reports for the `crypto_LUKS` partition.

Sources: <https://github.com/omacom/omarchy/issues/11878>

---

## Old CPU without AVX2: kernel update leaves the machine unbootable ('does not support all of the following CPU features')

`limine-entry-tool-avx2-old-cpu-unbootable` · severity: **critical** · frequency: **rare** · applies to: `laptop`, `limine`, `old-hardware`, `omarchy`, `uki`

**Symptom.** On an older or low-end CPU (for example a Celeron N4000), a kernel update prints, among hundreds of lines:

```
The current machine does not support all of the following CPU features that are
required by the image: [CX8, CMOV, FXSR, MMX, SSE, SSE2, SSE3, SSSE3, SSE4_1,
SSE4_2, POPCNT, LZCNT, AVX, AVX2, BMI1, BMI2, FMA, F16C].
Please rebuild the executable with an appropriate setting of the -march option.
ERROR: failed to get kernel cmdline for 'linux'.
```

The update reports success. After a reboot the system breaks because the old kernel's modules are gone. `snapper-cleanup.service` may also fail daily.

**Cause.** From `limine-mkinitcpio-hook` 1.29.0, `/usr/lib/limine/limine-entry-tool` is a GraalVM native executable instead of a JVM program (upstream changelog, 1.29.0, 2026-01-30). The reporter's 1.29.0-1 build required AVX2 and refused to start on an x86-64-v2 CPU. `90-mkinitcpio-install.hook` runs `limine-mkinitcpio-install`, which calls the tool to fetch the command line, fails with `failed to get kernel cmdline`, and leaves the UKI unrebuilt. A failing PostTransaction hook does not abort pacman, which had already replaced the kernel and removed the old modules. `limine-mkinitcpio-hook` 1.38.0-1.1 and `limine-snapper-sync` 1.31.0-1.1 are built at x86-64-baseline and run on such CPUs. Which builds between those two were affected is not established. The reporter went straight from 1.29.0-1 to 1.38.0-1.1, and the upstream changelog for 1.29.1 (2026-02-05) already lists "Adjust GraalVM native-image build flags for different x86_64 CPUs". The issue describes the fixing update as a trap. Because the hook runs after every package in the transaction is unpacked, a transaction that brings 1.38.0-1.1 should run the fixed binary, so the danger lies in kernel updates made while an affected build was installed. The report comes from Omarchy 3.8.5. Omarchy 4 ships `kernel-modules-hook`, which keeps the old kernel's modules.

> **Audit corrected this record.** #11526 supports the error text, the reporter's jump from 1.29.0-1 to 1.38.0-1.1 and the x86-64-baseline rebuild. This machine has limine-mkinitcpio-hook 1.38.0-1.1, limine-snapper-sync 1.31.0-1.1 and kernel-modules-hook 0.1.7-3. /usr/share/libalpm/scripts/limine-mkinitcpio-install line 131 prints the quoted 'failed to get kernel cmdline' error, and 90-mkinitcpio-install.hook is PostTransaction, so the cause's reasoning about the fixing transaction holds. The cause's specifics are wrong in two places. The packaged CHANGELOG.md dates 1.29.0, the GraalVM native-image switch, to 2026-01-30 and not February. The corrected cause and the earlier audit note also assert that every build from 1.29 to 1.37 was affected. The reporter never ran those builds, and the upstream changelog for 1.29.1 (2026-02-05) already lists 'Adjust GraalVM native-image build flags for different x86_64 CPUs'. So only 1.29.0-1 is confirmed affected, and the cause is rewritten to say so. The fix and verify commands are correct and kept: readelf is in binutils 2.47-4, and `pacman -S` without -u is not blocked by the ALPM guard. Not exercised: no pre-AVX2 CPU was available.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Rebooting after an update that printed the CPU-features error starts the old UKI against a module tree that may no longer exist. Rebuild first. Omarchy also ships `kernel-modules-hook`, which restores the running kernel's modules after an upgrade. That may soften this case, but it was not exercised.

**Fix.**

## If you are still booted, do not reboot yet

```sh
pacman -Q limine-mkinitcpio-hook limine-snapper-sync
readelf -n /usr/lib/limine/limine-entry-tool | grep ISA     # want: x86-64-baseline
/usr/lib/limine/limine-entry-tool --version
```

If the fixed version is installed, rebuild the UKI before rebooting:

```sh
sudo limine-mkinitcpio
```

If it is not installed yet, run `omarchy update -y` to bring it in, then run `sudo limine-mkinitcpio` and check that it completes without the CPU-features error.

## If you already rebooted into a broken system

Boot the Omarchy ISO, unlock and mount the install as in `chroot-recovery-btrfs-missing-subvol`, then inside the chroot:

```sh
pacman -Q limine-mkinitcpio-hook        # 1.38.0-1.1 or later is fixed
# only if it is older:
pacman -S limine-mkinitcpio-hook limine-snapper-sync    # no -y: the database was synced by the update
limine-mkinitcpio
```

**Verify.** `readelf -n /usr/lib/limine/limine-entry-tool | grep ISA` prints `x86-64-baseline`. `sudo limine-mkinitcpio` finishes without the CPU-features error. After a reboot, `uname -r` matches `pacman -Q linux` (or `linux-omarchy`).

Sources: <https://github.com/omacom/omarchy/issues/11526>

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

> **Audit corrected this record.** The cause, the clock check, the keyring-first principle, `omarchy-update-keyring`, the Omarchy key fingerprint 40DFB630FF42BCFFB047046CF0134EE680CAC571 with keys.openpgp.org + --lsign-key + omarchy-keyring (all three verified verbatim in bin/omarchy-update-keyring), the gnupg reset, and the geo.mirror.pkgbuild.com fallback are right. But the explicit reassurance about Omarchy is false and leaves the user in the exact state the record warns against. bin/omarchy-update-pacman-guard sets has_sync on any short option containing S and has_sysupgrade on any containing u, and blocks when both are set, so `sudo pacman -Su` is blocked just as `-Syu` is. The recommended `sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su` therefore syncs the database and then refuses the upgrade, leaving a partially-synced system.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never stop after `pacman -Sy`. That leaves the sync database ahead of your installed packages, and the next single-package install becomes a partial upgrade that can break glibc/kernel pairing. Always chain `&& pacman -Su`. Do not "fix" this by setting `SigLevel = Never` or `TrustAll` in /etc/pacman.conf: you disable package authentication system-wide. Deleting /etc/pacman.d/gnupg also drops any locally signed third-party keys, which must be re-added afterwards.

**Fix.**

Clock first, keyring before everything else, which is unchanged:

```bash
timedatectl
sudo timedatectl set-ntp true
```

On Omarchy 4, use the packaged path (it recv/lsigns the Omarchy key, installs omarchy-keyring, and reinstalls archlinux-keyring even without a version bump):

```bash
omarchy-update-keyring
omarchy update
```

Do not use `sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su` on Omarchy. The ALPM guard blocks any pacman run carrying both -S and -u, and that includes a bare `-Su`: the first half syncs the databases, the second half is refused, and you are left with a synced-but-not-upgraded system, the partial-upgrade state this record exists to avoid. If you must drive pacman directly:

```bash
sudo pacman -Sy --needed archlinux-keyring
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Su
```

On plain Arch/EndeavourOS/CachyOS (no guard) the original one-liner is correct as written.

The rest of the record stands, with one caveat: `sudo rm -rf /etc/pacman.d/gnupg` also discards every key you locally signed for the AUR or third-party repos, so on Omarchy re-run `omarchy-update-keyring` (and re-lsign any custom repo keys) after `pacman-key --init && pacman-key --populate archlinux`. Note `pacman -Sc --noconfirm` does work, because -Sc's prompt defaults to yes, unlike -Scc's.

**Verify.** `sudo pacman -Syu` proceeds past the signature check and reaches the package list. `sudo pacman-key --list-keys | wc -l` grows. `pacman -Q archlinux-keyring` shows a recent version.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-keyring> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pacman-guard> · <https://wiki.archlinux.org/title/Pacman>

---

## Chroot from a live USB correctly (including the Btrfs subvol=@ trap)

`chroot-recovery-btrfs-missing-subvol` · severity: **high** · frequency: **very-common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `luks`, `manjaro`, `omarchy`

**Symptom.** You boot a live USB to repair the system, run `arch-chroot /mnt`, reinstall the kernel, and nothing improves. Or the repair itself fails with things like:

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

**Cause.** systemd generates a mount unit for every `/etc/fstab` line. If the device never appears, the generated `.device` unit waits (default 90 s) and then the mount fails. Because `local-fs.target` *requires* it, the whole boot fails into emergency mode. A reformatted ESP or a re-created swap partition has a new UUID, so the old fstab line can never be satisfied.

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

> **Audit corrected this record.** Almost all of it verified: Limine has an in-menu editor (CONFIG.md: editor_enabled, default yes) and `cmdline:` is the right key, systemd.unit=, systemd.mask=, nomodeset, fsck.mode=skip, init=/bin/bash and the SysV alias `3` are all real, and the /etc/limine-entry-tool.d/99-local.conf drop-in with KERNEL_CMDLINE[default]+=" ..." matches the exact syntax Omarchy uses in etc/limine-entry-tool.d/omarchy-defaults.conf. But the record contradicts itself and gives a dead-end escape: it correctly says rescue.target requires the root password, then recommends `systemd.unit=rescue.target` as the workaround for a machine where root has no password. rescue.service and emergency.service both run systemd-sulogin-shell, so rescue mode is exactly as unreachable as emergency mode on Omarchy's locked root. Also rd.break is offered without noting that Omarchy/Arch use mkinitcpio, not dracut, so it does nothing there.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `init=/bin/bash` leaves the root filesystem mounted read-only and journald not running. Remount rw before editing and remount ro (or sync) before power-cycling, or you will lose the edit or corrupt the filesystem. Anyone with physical access can use these parameters to get root without a password. That is exactly why full-disk encryption matters. On Omarchy the menu entries are unified kernel images, so a cmdline edited at the Limine prompt is only honoured when Secure Boot is off. If it appears to be ignored, boot a snapshot instead.

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

And `rd.break` is dracut-only. Omarchy and Arch use mkinitcpio. The equivalents there are:

```
break=premount     stop in the initramfs before root is mounted
break=postmount    stop after root is mounted, before the switch
disablehooks=plymouth   skip one initramfs hook for this boot
```

Everything else is accurate as written: the Limine `e` editor and `cmdline:` line, GRUB `e`/Ctrl+X, systemd-boot `e` (`editor yes` in /boot/loader/loader.conf), the parameter table, the read-only remount dance under init=/bin/bash, and making a parameter stick via /etc/limine-entry-tool.d/99-local.conf plus `sudo limine-mkinitcpio`.

**Verify.** `cat /proc/cmdline` after booting shows the parameter you added. `systemctl get-default` and `systemctl list-units --failed` work from the rescue shell.

Sources: <https://wiki.archlinux.org/title/Kernel_parameters> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://wiki.archlinux.org/title/Fsck>

---

## Windows asks for the BitLocker recovery key after installing Omarchy or Arch alongside it

`bitlocker-recovery-screen-after-linux-install` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `dual-boot`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `secure-boot`, `tpm`, `windows`

**Symptom.** "Since I installed Linux, Windows boots to a blue BitLocker recovery screen asking for the 48-digit key." It happens on every Windows boot, or only when Windows is started from the Limine or GRUB menu. Separately, the Omarchy installer refuses to install alongside Windows because BitLocker is enabled.

**Cause.** Windows seals the BitLocker key in the TPM against measured boot state, specifically PCR 7, which covers the Secure Boot state and the enrolled certificates. Omarchy's getting-started manual tells you to turn off Secure Boot and/or the TPM before installing. Turning Secure Boot off changes PCR 7, and turning the TPM off removes the key's store entirely, so either one sends Windows to the recovery screen. Changing the Secure Boot databases (for example `sbctl enroll-keys`) changes PCR 7 too. The Arch wiki also notes that Windows refuses PCR 7 binding when non-Microsoft certificates are in the boot chain, so launching Windows from a Linux boot manager can trigger recovery as well. Windows 11 and recently updated Windows 10 often have device encryption on even when Settings looks off, and Omarchy's dual-boot manual states its install method is not compatible with BitLocker.

> **Audit corrected this record.** Re-read the raw Arch wiki Dual_boot_with_Windows and both quattro manual pages. The wiki supports PCR 7 binding, recovery when Secure Boot is disabled, re-enabling Secure Boot restoring unlock, refusal of PCR 7 binding with non-Microsoft certificates in the chain (so not launching Windows from a Linux boot manager), default device encryption, Windows Hello methods being disabled, and 'permanent data loss'. manual/02-getting-started.md says 'You must turn off Secure Boot and/or TPM in the BIOS' and manual/50-dual-boot-install.md gives the Settings > Privacy & Security > Device encryption route. The cause and the manage-bde forms stand as the earlier audit found. One defect in the fix: step 3 told a reader at the recovery screen to re-enable Secure Boot, but the same Omarchy manual says Omarchy cannot be installed with it on, and an unsigned Limine will not boot with it on, so following step 3 trades the Windows prompt for an Omarchy that does not boot. The fix now says so and makes re-sealing from Windows the route for a machine that keeps Secure Boot off. Not exercised: no Windows here.
>
> *The Cause above was rewritten on 2026-10-04 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Changing Secure Boot keys or settings without the BitLocker recovery key saved can lock you out of the Windows partition permanently, which is **permanent data loss** in the Arch wiki's words. Get the key first. Turning BitLocker off removes encryption from the Windows partition, and may disable Windows Hello sign-in methods, so know your Windows password before doing it.

**Fix.**

## Before installing, or before touching Secure Boot

Save the recovery key somewhere off the machine. Then, in an elevated Windows command prompt, suspend protection for the next reboot:

```bat
manage-bde -protectors -get C:
manage-bde -protectors -disable C: -rc 1
```

Make the firmware change and boot Windows once. Protection resumes automatically after the count of reboots you set. This suspend-and-resume is the same path Windows uses for firmware updates.

For the Omarchy dual-boot installer, the manual's route is to turn BitLocker off completely: **Settings > Privacy & Security > Device encryption**, toggle it off, and wait for decryption to finish.

## Already at the recovery screen

1. Enter the recovery key, taken from your Microsoft account's BitLocker recovery keys page or from wherever you saved it.
2. Start Windows from the firmware boot menu (often F12) rather than from Limine or GRUB, so only Microsoft-signed code is in the chain.
3. Re-seal the key to the current firmware state from inside Windows. This is the route for an Omarchy dual boot, which keeps Secure Boot off:

```bat
manage-bde -protectors -delete C: -type tpm
manage-bde -protectors -add C: -tpm
```

4. The Arch wiki notes that re-enabling Secure Boot restores automatic unlock. On an Omarchy machine that stops Omarchy from booting, because the Omarchy manual requires Secure Boot off and its Limine is not signed. Only do it if you have set up your own Secure Boot signing for Linux, or no longer need Linux to boot.

**Verify.** Windows boots to the login screen without the recovery prompt across two consecutive boots, and `manage-bde -status C:` in Windows shows `Protection On` with a TPM protector listed.

Sources: <https://wiki.archlinux.org/title/Dual_boot_with_Windows> · <https://github.com/Foxboron/sbctl/wiki/Linux-Windows-Dual-Boot-with-Windows-Bitlocker> · <https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/manage-bde-protectors> · <https://github.com/omacom/omarchy/blob/quattro/manual/50-dual-boot-install.md> · <https://github.com/omacom/omarchy/blob/quattro/manual/02-getting-started.md>

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

> ⚠️ **Risk.** `grub-install --removable` overwrites `\EFI\BOOT\BOOTX64.EFI` on the ESP. On a shared ESP that is the fallback loader other operating systems (and some firmware) rely on. Check what is there first.

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

## omarchy update stops at migration 1789325478: "The Omarchy kernel has no Limine boot entry"

`kernel-migration-1789325478-no-limine-boot-entry` · severity: **high** · frequency: **common** · applies to: `desktop`, `dkms`, `laptop`, `limine`, `nvidia`, `omarchy`

**Symptom.** Updating to Omarchy 4.0.4 ends in the red "Something went wrong during the update!" screen. Just above it:

```
Running migration (1789325478)
Install the Omarchy kernel and make it the first Limine boot entry
Building UKI for linux-omarchy (7.2.5-3-omarchy)
...
==> ERROR: module not found: 'nvidia'
==> ERROR: module not found: 'nvidia_modeset'
==> ERROR: module not found: 'nvidia_uvm'
==> ERROR: module not found: 'nvidia_drm'
==> WARNING: errors were encountered during the build. The image may not be complete.
==> Creating unified kernel image: '/tmp/limine-mkinitcpio.BrnQbL/linux-omarchy.efi'
==> Unified kernel image generation successful
ERROR: mkinitcpio failed for kernel 7.2.5-3-omarchy, skipping.
The Omarchy kernel has no Limine boot entry; rerun omarchy-migrate after fixing the boot image build.
```

Every later `omarchy update` stops at the same place. The machine still boots, on the stock `linux` kernel.

**Cause.** Migration `1789325478.sh` (Omarchy 4.0.4) installs `linux-omarchy` and `linux-omarchy-headers`, rewrites `BOOT_ORDER` in `/etc/default/limine`, then runs `sudo limine-mkinitcpio linux-omarchy`. `limine-mkinitcpio-install` prints `mkinitcpio failed for kernel ..., skipping.` and still exits 0 when mkinitcpio returns non-zero, so the migration checks `limine-entry-tool --tree` itself and exits 1 with that message when no `linux-omarchy` entry exists. The guard line is a consequence. The real failure is the line above it.

On NVIDIA machines mkinitcpio fails because `/etc/mkinitcpio.conf.d/nvidia.conf` (written by `install/hardware/nvidia.sh`) asks for `nvidia nvidia_modeset nvidia_uvm nvidia_drm` early and mkinitcpio cannot find those modules for `7.2.5-3-omarchy`. Two situations are reported in issues 12044 and 5026:

1. The `nvidia-open-dkms` build for the new kernel died. One reporter's `make.log` showed `gcc: fatal error: Killed signal terminated program cc1`, the OOM killer. The package's `dkms.conf` sets `MAKE[0]="'make' -j\`nproc\` ..."`. The `make` is quoted to stop DKMS adding `KERNELRELEASE`, and a side effect is that DKMS's own `-j` setting is not applied either, so the build always runs one job per CPU.
2. DKMS reports the modules as `installed` for the new kernel, but mkinitcpio still says `module not found`, and running `depmod` for that kernel fixes it. Issue 5026 attributes this to `60-depmod` running before `70-dkms-install`. Arch's DKMS hook script also runs `depmod` itself after a successful build, so why the index was stale on those machines is not established. A manual `dkms install --no-depmod`, as in the 12044 workaround, also leaves it stale.

`omarchy-migrate` runs migrations in order under `set -e` and only writes the per-user marker after a migration succeeds, so this one stays pending, and every migration after it (including `1789444024`, which installs missing kernel headers) is blocked behind it. The rest of the update after the migrate step (post-update hooks, AUR, mise, orphan cleanup, the reboot prompt) is skipped too.

> **Audit corrected this record.** The installed /usr/share/omarchy/migrations/1789325478.sh is byte-identical to quattro and does what the cause says (omarchy-pkg-add of linux-omarchy and headers, BOOT_ORDER rewrite in /etc/default/limine, limine-mkinitcpio linux-omarchy, limine-entry-tool --tree check, exit 1). It is absent at v4.0.3 and present at v4.0.4. /usr/share/libalpm/scripts/limine-mkinitcpio-install prints 'mkinitcpio failed for kernel ..., skipping.' and process_kernel returns 0, confirmed. omarchy-migrate (identical to quattro) runs under set -euo pipefail with per-user markers in $HOME/.local/state/omarchy/migrations, and omarchy-update's set -e skips everything after it, confirmed. Issue 12044 supports the OOM make.log and the workaround, issue 5026's comment supports the 'dkms status installed but module not found, depmod fixes it' case. Three defects. (1) Fix step 2a ran 'dkms install --no-depmod' and then went straight to the UKI rebuild without depmod, which recreates the exact 'module not found' failure, and the 12044 reporter's working sequence includes depmod. (2) The cause stated that DKMS's quoting of 'make' exists so dkms's -j cannot lower it. The dkms.conf comment says the quoting is there to stop DKMS adding KERNELRELEASE. /usr/bin/dkms line 1603 only rewrites a leading bare make, so the loss of -j is a side effect, not the intent. (3) The cause presented issue 5026's '60-depmod runs before 70-dkms-install' as the mechanism, but /usr/share/libalpm/scripts/dkms runs depmod itself after each successful build (DKMS_DEPMOD=1 by default), so that mechanism is unconfirmed and was reworded. Not exercised: no NVIDIA rebuild or migration was run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Do not reboot expecting the new kernel while `limine-mkinitcpio linux-omarchy` still prints `skipping.`: there is no `linux-omarchy` entry yet and the stock `linux` entry is the only working one, so do not remove `linux` at this stage. Running `sudo omarchy-migrate` replays every migration as root against root's home and can write root-owned files and settings where your user's belong.

**Fix.**

Run these from a terminal in the working session (stock `linux` kernel). The versions below are the ones from the 4.0.4 reports. Use the ones `dkms status` and `ls /usr/lib/modules/` print on your machine.

**1. Find which case you are in.**

```bash
uname -r
ls /usr/lib/modules/
pacman -Q linux-omarchy linux-omarchy-headers
dkms status
```

You need a line like `nvidia/610.57.04, 7.2.5-3-omarchy, x86_64: installed`. If headers are missing, install them (this passes Omarchy's pacman guard, which only stops `-S` combined with `-u`), and check that the headers version matches `linux-omarchy`:

```bash
sudo pacman -S --needed linux-omarchy-headers
pacman -Q linux-omarchy linux-omarchy-headers
```

**2a. DKMS shows no `installed` line for the `-omarchy` kernel: rebuild it and read why it failed.**

```bash
sudo dkms install nvidia/610.57.04 -k 7.2.5-3-omarchy
# on failure:
sudo tail -n 40 /var/lib/dkms/nvidia/610.57.04/build/make.log
journalctl -k -b | grep -iE 'out of memory|killed process'
```

If `make.log` shows `Killed signal terminated program cc1`, the build ran out of memory. Close large programs and limit the build to two jobs for this one run. The edit is to a package-owned file that the next `nvidia-open-dkms` upgrade overwrites:

```bash
sudo sed -i 's/-j`nproc`/-j2/' /usr/src/nvidia-610.57.04/dkms.conf
sudo dkms install nvidia/610.57.04 -k 7.2.5-3-omarchy
```

One report used `sudo MAKEFLAGS="-j2" dkms install ...` instead. GNU make gives a `-j` on its command line priority over `MAKEFLAGS`, so do not rely on that form.

**2b. In every case, refresh the module index for the new kernel before rebuilding the image.** This is the whole fix when DKMS already said `installed` but mkinitcpio said `module not found`.

```bash
sudo depmod 7.2.5-3-omarchy
modinfo -k 7.2.5-3-omarchy -F filename nvidia     # must print a path, not an error
```

**3. Rebuild the Omarchy kernel's UKI and confirm the entry exists.**

```bash
sudo limine-mkinitcpio linux-omarchy
sudo limine-entry-tool --tree | grep linux-omarchy
```

The build output must not contain `skipping.`

**4. Finish the update.** Run it as your user. Never `sudo omarchy-migrate`: under sudo it reads root's state directory (`/root/.local/state/omarchy/migrations`), sees no markers there, and replays every migration as root.

```bash
omarchy update
```

That reruns the pending migrations, then the steps the failure skipped. The migration sets `reboot-required` when it completes. Reboot and check `uname -r`.

**Verify.** `omarchy-migrate --pending` prints nothing (exit status 1). `sudo limine-entry-tool --tree` lists `linux-omarchy`. After a reboot `uname -r` ends in `-omarchy` (unless Direct Boot is enabled, see the direct boot record), and `nvidia-smi` reports the driver.

Sources: <https://github.com/omacom/omarchy/issues/12044> · <https://github.com/omacom/omarchy/issues/5026> · <https://github.com/omacom/omarchy/blob/v4.0.4/migrations/1789325478.sh> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-migrate> · <https://github.com/omacom/omarchy/blob/v4.0.4/bin/omarchy-update> · <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support>

---

## No snapshot entries in the Limine menu when you need to roll back

`limine-snapshot-entries-missing-from-boot-menu` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `limine`, `omarchy`, `snapper`

**Symptom.** An update broke the system and the Omarchy manual says to pick a snapshot from the boot loader, but the Limine menu only lists "Omarchy" and maybe a fallback entry. No dated snapshot entries at all. Or the machine boots straight to the disk-decryption prompt and never shows Limine. Sometimes `omarchy-snapshot create` printed, and you scrolled past:

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

> ⚠️ **Risk.** Between `pacman -Rdd linux-firmware` and the reinstall your system has NO firmware files in /usr/lib/firmware. Do not reboot, suspend, or let the machine lose power in that window, because you would boot without GPU/Wi-Fi firmware and possibly without a usable display.

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

## linux-omarchy 7.2.5-3 black screen, emergency shell, dead TPM, touchscreen or Wi-Fi on some Intel machines (Intel IOMMU on by default)

`linux-omarchy-intel-iommu-default-on-boot-failures` · severity: **high** · frequency: **common** · applies to: `apple`, `desktop`, `intel`, `laptop`, `limine`, `linux-omarchy`, `omarchy`, `uki`

**Symptom.** After the Omarchy 4.0.4 update installed the `linux-omarchy` kernel, the machine no longer boots properly or loses a device, but choosing the plain `linux` entry in the Limine menu still works. Reported forms:

- MacBookPro13,3 (2016): black screen, last line around `amdgpu 0000:01:00.0: [drm] VCE enabled in VM mode`. With `amdgpu` blacklisted it gets further and drops to an emergency shell because the NVMe SSD never appears:

```
ERROR: device '/dev/mapper/omarchy_root' not found. Skipping fsck.
mount: /new_root: special device /dev/mapper/omarchy_root does not exist
You are now being dropped into an emergency shell.
```

- MacBookPro11,5 (2015): the session starts, then the Radeon R9 M370X wedges with `ring gfx timeout`, and on one machine Btrfs corruption counters climb.
- MacBookAir6,1: the internal SSD fails to identify, the encrypted root never appears, and the kernel panics with `Attempted to kill init!`.
- Dell XPS 13 9343: every boot stalls 90 seconds and the TPM disappears:

```
systemd[1]: Timed out waiting for device /dev/tpmrm0.
```

- Surface Pro 4 touchscreen dead, one desktop RTX 4070 Ti whose GSP firmware fails to boot, and one ASUS laptop whose Intel AX210 Wi-Fi drops off the PCIe bus on some cold boots.

`journalctl -k` on the failing kernel shows lines like `DMAR: [DMA Read NO_PASID] Request device [0000:00:16.7] fault addr ...`.

**Cause.** `linux-omarchy` 7.2.5-3 is built with `CONFIG_INTEL_IOMMU_DEFAULT_ON=y`. Arch's `linux` 7.2.3 leaves it unset. With VT-d DMA translation on by default, a device whose buffers the firmware DMAR table does not cover, or that needs a PCI DMA alias quirk the kernel lacks, faults on DMA.

The reported devices differ by machine. On the MacBookAir6,1 it is the Toshiba AHCI controller `1179:010b`, which needs a `quirk_dma_func1_alias` entry that a reporter sent to the Linux PCI maintainers on 2026-09-29. On the MacBookPro11,5 it is the internal Samsung AHCI SSD controller and the Southern Islands R9 M370X under `amdgpu`. On the MacBookPro13,3 it is the NVMe SSD, the Apple SPI keyboard and the Polaris Radeon Pro 450. Elsewhere it is the Intel ME PTT function at `00:16.7` that backs a firmware TPM, the Surface IPTS touch controller at `00:16.4`, and an Intel AX210 on one ASUS laptop, where 2 of 7 cold boots failed and no `intel_iommu=off` control was run.

On omacom/omarchy-pkgs#677 the reporter confirmed that a 7.2.7rc1 build with the option unset removed the faults and the 90 s wait. As of 2026-10-05 the stable repository still ships `linux-omarchy` 7.2.5-3.

Not every report in these threads is the IOMMU. The iMac18,3 reporter on #12119 retracted their data point after testing the variables separately, and on #12550 a MacBookPro11,5 with its dGPU bound to `radeon` and the panel on Intel showed no faults with the IOMMU on.

> **Audit corrected this record.** The mechanism and the fix hold. On this workstation linux-omarchy 7.2.5-3 has CONFIG_INTEL_IOMMU_DEFAULT_ON=y in /proc/config.gz, linux 7.2.3.arch1-3 is still installed, and /usr/lib/limine/limine-common-functions loads /etc/default/limine last ('4. Load /etc/default/limine (highest priority)'). limine-mkinitcpio with no argument pipes 'rebuild' to limine-mkinitcpio-install, and limine-update is limine-install plus limine-mkinitcpio, so both steps rebuild the UKIs. The pkgs.omarchy.org stable database fetched on 2026-10-05 still lists linux-omarchy-7.2.5-3, and no quattro migration after 1789444024.sh touches Limine or the IOMMU. omarchy-pkgs#677 confirms the XPS 13 9343 PTT fault, the 90 s wait and the 7.2.7rc1 fix. #12097 has a commenter using exactly the e, append, F10 one-boot path and the same drop-in. The cause and symptom contained fabricated precision. The cause called the Apple AHCI SSD controller 'Toshiba 1179:010b' for every Mac, but #14160's MacBookPro11,5 has a Samsung AHCI controller and #12119's MacBookPro13,3 has a Samsung NVMe SSD. The Toshiba controller is only the MacBookAir6,1. It also named only Southern Islands amdgpu chips while the 13,3 carries a Polaris Radeon Pro 450. The cited #13030 (AX210 Wi-Fi lost on 2 of 7 cold boots, no control run) and the #12550 radeon-bound 11,5 with no faults were missing. The title said 'older Intel machines', which the RTX 4070 Ti desktop and the 2019 ASUS laptop do not fit. Cause, symptom and title were rewritten. The fix is unchanged. Earlier audit's findings kept: the danger text about Btrfs corruption on affected Macs stays. Not exercised: no boot, no rebuild.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** On Intel Macs whose internal SSD is affected (MacBookPro11,x on #14160, MacBookAir6,1 on #12097), DMA writes to the SSD fault while the IOMMU is on, and #14160 shows Btrfs corruption errors climbing during such a boot. Do not keep booting `linux-omarchy` to experiment on these machines. Boot `linux`, or add `intel_iommu=off`, before doing anything else, and run `sudo btrfs scrub start -B /` afterwards. On a MacBook Air the stock `linux` kernel may have no working Wi-Fi driver, so plan for a USB network adapter or phone tethering if you need to download anything from it.

**Fix.**

## Get booted now

At the Limine menu pick the `linux` entry. The migration deliberately leaves the stock Arch kernel installed. Or highlight `linux-omarchy`, press `e`, append `intel_iommu=off` to the kernel command line and boot with F10.

## Make it persistent (Omarchy 4)

The command line is embedded in the UKI, so add a limine-entry-tool drop-in and rebuild. Never edit `/boot/limine.conf`.

```sh
echo 'KERNEL_CMDLINE[default]+=" intel_iommu=off"' | sudo tee /etc/limine-entry-tool.d/intel-iommu-off.conf
sudo limine-mkinitcpio
```

`[default]` applies to both kernels. That is harmless for the stock `linux` kernel, whose IOMMU is already off by default.

## Or keep booting the stock kernel by default

`/etc/default/limine` loads last and wins over every drop-in. The migration wrote a `BOOT_ORDER` line there. Put `linux` first:

```sh
sudo sed -i 's/^BOOT_ORDER=.*/BOOT_ORDER="linux, linux-omarchy, linux-omarchy-*, *, *fallback, Snapshots"/' /etc/default/limine
sudo limine-update
```

## Undo once a fixed kernel ships

When `pacman -Q linux-omarchy` shows a build with the option unset, remove the workaround:

```sh
zgrep INTEL_IOMMU_DEFAULT_ON /proc/config.gz    # run while booted on linux-omarchy
sudo rm /etc/limine-entry-tool.d/intel-iommu-off.conf
sudo limine-mkinitcpio
```

**Verify.** After a reboot on the `linux-omarchy` entry: `uname -r` ends in `-omarchy`, `grep -o intel_iommu=off /proc/cmdline` prints the parameter, `journalctl -k -b | grep -c 'DMAR: \[DMA'` prints 0, and on the TPM case `ls /dev/tpmrm0` exists and `systemd-analyze` no longer shows a 90 s userspace phase.

Sources: <https://github.com/omacom/omarchy/issues/12119> · <https://github.com/omacom/omarchy/issues/12097> · <https://github.com/omacom/omarchy/issues/12550> · <https://github.com/omacom/omarchy/issues/14160> · <https://github.com/omacom/omarchy-pkgs/issues/677> · <https://github.com/omacom/omarchy/issues/13030> · <https://gitlab.com/Zesko/limine-entry-tool> · <https://wiki.archlinux.org/title/Kernel_parameters>

---

## Hardware broke after 4.0.4 moved you to linux-omarchy: make the stock linux kernel the default again

`make-stock-linux-default-after-linux-omarchy-regression` · severity: **high** · frequency: **common** · applies to: `amd`, `apple`, `desktop`, `intel`, `laptop`, `limine`, `omarchy`

**Symptom.** Since the Omarchy 4.0.4 update (which installed `linux-omarchy 7.2.5-3` and made it the first Limine entry), something works only on the stock kernel: the machine resets before the LUKS prompt, freezes, loses Wi-Fi, touchpad, backlight, HDMI audio or suspend. Picking `linux` in the Limine menu at every boot fixes it until you forget.

**Cause.** Migration `1789325478.sh` installs `linux-omarchy` and writes `BOOT_ORDER="linux-omarchy, linux-omarchy-*, *, *fallback, Snapshots"` to `/etc/default/limine`, which `limine-entry-tool` reads last and which overrides every drop-in. It deliberately keeps stock `linux` installed "so it remains available if the new one cannot boot". The upstream tracker has many hardware-specific regressions reported against `linux-omarchy 7.2.5-3` that stock `linux 7.2.3` does not show. Its exemption covers T2 Macs only (`linux-t2` or a `-t2` kernel), so T1 and older Macs were switched too (issue 12281). The migration exits early once `/var/lib/omarchy/migrations/1789325478` exists, so it never rewrites `BOOT_ORDER` again.

> **Audit corrected this record.** Read migrations/1789325478.sh at v4.0.4 (identical to /usr/share/omarchy/migrations/1789325478.sh here): it skips only T2 (linux-t2 package or -t2 in uname -r), deletes and re-appends BOOT_ORDER in /etc/default/limine, keeps stock linux on purpose, and exits early once /var/lib/omarchy/migrations/1789325478 exists. Confirmed in /usr/lib/limine/limine-common-functions load_config() that /etc/default/limine is loaded after /etc/limine-entry-tool.d/*.conf, so editing omarchy-defaults.conf (which also sets BOOT_ORDER) cannot win. /usr/bin/limine-update runs limine-install --no-efi-register then limine-mkinitcpio, and limine-entry-tool --tree exists per its --help. Issue 12087 has a reporter (Beelink SER9) whose reset loop was fixed by a BIOS update and who gives exactly this BOOT_ORDER plus sudo limine-update stopgap. Issue 12281 confirms T1 Macs were switched, with a root-caused CS4208 speaker regression in a comment. The tracker lists many 7.2.5-3 regressions that stock 7.2.3 does not show (touchpad 12181, backlight 12188, HDMI audio 12131 and 12628, suspend 12190 and 13196, freezes 12926 and 12371, Wi-Fi 13795 and 13849), so the symptom and cause hold. Defects: the fix calls 12087 a "beta report", which it is not (it is a 4.0.4 user comment), and step 3 points at another record without the commands. Issue 12145 shows the direct-boot entry keeps pointing at omarchy_linux.efi and that omarchy-setup-direct-boot picks a UKI with find | head -1, so its choice is unpredictable with two UKIs. The corrected fix gives the efibootmgr commands that script itself uses. Issue 12664 claims default_entry: 2 selects the stock kernel. Limine CONFIG.md says an index can name a directory, so the /+Omarchy directory is entry 1 and the first kernel is entry 2, and this workstation boots 7.2.5-3-omarchy under that template. That issue does not invalidate the fix. Not exercised: I did not edit /etc/default/limine, run limine-update or reboot. /boot is dmask=0077 and I did not use root, so /boot/limine.conf was not read.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Stock `linux` must stay installed and its DKMS modules built (`dkms status`) for this to work. A mistyped `BOOT_ORDER` only reorders entries, but deleting the `KERNEL_CMDLINE` line from `/etc/default/limine` removes `root=` from every UKI on the next rebuild and nothing boots.

**Fix.**

**1. Put `linux` first in `/etc/default/limine`.** Editing `/etc/limine-entry-tool.d/omarchy-defaults.conf` does nothing here, because `/etc/default/limine` is read after every drop-in and overrides it.

```bash
sudoedit /etc/default/limine
```

Replace the `BOOT_ORDER=` line with:

```
BOOT_ORDER="linux, linux-omarchy, linux-omarchy-*, *, *fallback, Snapshots"
```

Leave the `ESP_PATH` and `KERNEL_CMDLINE` lines alone.

**2. Regenerate the Limine entries.**

```bash
sudo limine-update
sudo limine-entry-tool --tree        # linux should now be listed first
```

**3. If Direct Boot is enabled, the firmware entry decides, not Limine.** Check for it:

```bash
efibootmgr | grep -E 'Omarchy([[:space:]]|$)'
```

If it is there and its path is not `\EFI\Linux\omarchy_linux.efi`, replace it. Do not rely on `omarchy-setup-direct-boot` for this, because with two kernels it picks whichever `omarchy*.efi` file `find` lists first. These are the same commands that script runs. Replace `XXXX` with the number from the line above:

```bash
sudo ls /boot/EFI/Linux/                    # omarchy_linux.efi must be listed
findmnt -no SOURCE /boot                     # e.g. /dev/nvme0n1p1 is disk /dev/nvme0n1, partition 1
sudo efibootmgr --bootnum XXXX --delete-bootnum
sudo efibootmgr --create --disk /dev/nvme0n1 --part 1 --label Omarchy --loader '\EFI\Linux\omarchy_linux.efi'
```

**4. Keep `linux-omarchy` installed** so you can retest a later release from the menu. One reporter in issue 12087 (Beelink SER9) had the same reset loop fixed by a BIOS update alone, so check for a firmware update and retest. An Intel machine whose failure shows `DMAR:` faults may only need `intel_iommu=off` (see that record) rather than the stock kernel.

To return to the Omarchy kernel later, put `linux-omarchy` first again, rerun `sudo limine-update`, and point a Direct Boot entry at `\EFI\Linux\omarchy_linux-omarchy.efi`.

**Verify.** Reboot without touching the menu. `uname -r` prints the `-arch` version and the broken device works.

Sources: <https://github.com/omacom/omarchy/blob/v4.0.4/migrations/1789325478.sh> · <https://github.com/omacom/omarchy/issues/12281> · <https://github.com/omacom/omarchy/issues/12087> · <https://gitlab.com/Zesko/limine-entry-tool> · <https://github.com/omacom/omarchy/issues/12145> · <https://github.com/omacom/omarchy/issues/12181> · <https://github.com/omacom/omarchy/issues/12664> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md>

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

**After touching anything under `/etc/mkinitcpio.conf*`, `/etc/default/limine`, or `/etc/limine-entry-tool.d/`, rebuild immediately and read the output. Do not reboot on faith:**

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

Do not copy that line into your own drop-in. A later-sorting drop-in that assigns `HOOKS=` replaces it wholesale, and you will silently lose whatever Omarchy adds in a future release. Use `+=` on `MODULES`/`FILES`, and leave `HOOKS` to the packaged file.

**Verify.** `sudo find /etc -name '*.pacnew'` returns nothing. `sudo limine-mkinitcpio` (or `mkinitcpio -P`) completes with no ERROR lines. `grep -R HOOKS /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/` shows encrypt/plymouth/filesystems still present if you use them.

Sources: <https://wiki.archlinux.org/title/Pacman/Pacnew_and_Pacsave> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://wiki.archlinux.org/title/Mkinitcpio> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/blob/quattro/etc/mkinitcpio.conf.d/omarchy_hooks.conf> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio>

---

## Roll back to a working kernel (pacman cache, linux-lts, or an Omarchy snapshot)

`rollback-kernel-after-bad-update` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `grub`, `limine`, `manjaro`, `nvidia`, `omarchy`, `systemd-boot`

**Symptom.** A kernel update boots to a black screen, a panic, or breaks the GPU/Wi-Fi, and you need the previous kernel back. On plain Arch there is no second kernel in the menu because only one is installed.

**Cause.** Arch keeps only the currently installed kernel in `/boot`. The previous version is gone the moment the package upgrades. Without `linux-lts` or a snapshot you have nothing to fall back to.

> **Audit corrected this record.** All three options are real: `pacman -U` from cache, `downgrade` exists in the AUR, `linux-lts` is in core (6.18.47), and `omarchy-snapshot create|restore` is genuine. I read the script and restore calls `sudo limine-snapper-restore`. But two gaps matter for a machine that is currently unbootable. The cache may be empty: `paccache` runs from a systemd timer on many installs and Omarchy prunes packages during updates, so `ls /var/cache/pacman/pkg/linux-*` frequently returns nothing and the record offers no fallback (the Arch Linux Archive). And `IgnorePkg = linux linux-headers` pins the kernel while everything else keeps moving forward. That is a deliberate partial upgrade, which will eventually break DKMS and out-of-tree modules. It needs a warning and needs the DKMS/nvidia packages considered alongside.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Downgrading `linux` without downgrading DKMS modules (nvidia-dkms, virtualbox-host-dkms, zfs) is itself a partial upgrade and can leave you with no GPU driver. Rebuild them after the downgrade. Omarchy snapshot restore only rolls back the system root: /home and ~/.config are deliberately left untouched, so newer config formats may not match the older packages. Leaving `IgnorePkg = linux` in place indefinitely will eventually desync your kernel from the rest of the system.

**Fix.**

**Option 1: reinstall the previous package** (chroot from a live USB if you cannot boot):

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

Pin it so the next `-Syu` does not undo the rollback, in the `[options]` section of `/etc/pacman.conf`:

```
IgnorePkg = linux linux-headers
```

This is a deliberate partial upgrade: the rest of the system moves on while the kernel does not, and DKMS/out-of-tree modules will eventually stop matching. Treat it as temporary and remove the line as soon as a fixed kernel ships.

EndeavourOS (and anyone with the AUR `downgrade` helper) can automate the cache/ALA lookup:

```sh
sudo downgrade linux linux-headers
```

**Option 2: install the LTS kernel as a permanent escape hatch** (do this *before* you need it):

```sh
sudo pacman -S linux-lts linux-lts-headers
sudo mkinitcpio -P
sudo grub-mkconfig -o /boot/grub/grub.cfg    # GRUB
sudo limine-mkinitcpio                        # Omarchy/Limine
sudo bootctl list                             # systemd-boot: confirm the new entry
```

**Option 3: Omarchy snapshot rollback.** Omarchy snapshots via snapper on every update. Pick the snapshot by date/version in the Limine menu and boot it, then:

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

> **Audit corrected this record.** I verified every sbctl subcommand and flag against sbctl(8): create-keys, enroll-keys with -m/--microsoft, sign with -s/--save, verify, list-files, list-enrolled-keys, status all exist as written, and sbctl is in extra (0.18). Two fixes needed. The Limine signing path is wrong: the limine package ships usr/share/limine/BOOTX64.EFI and there is no limine.efi, so `sbctl sign -s /boot/EFI/limine/limine.efi` fails on a nonexistent file. And the record omits sbctl's own prominent warning: some devices ship signed firmware/option ROMs that are validated under Secure Boot, and enrolling keys without Microsoft's certificates can brick them. That warning belongs next to the enroll command, not nowhere.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** BRICKING RISK. `sbctl enroll-keys` without `-m` (Microsoft keys) can leave some laptops unable to run signed option ROMs (discrete GPU, Thunderbolt) or unable to boot Windows. A small number of firmwares handle custom PK enrollment badly. Always use `-m` on a dual-boot or OEM laptop, keep Secure Boot disabled until `sbctl verify` is clean, and know how to reset keys to factory defaults in your firmware setup.

**Fix.**

Put the firmware into **Setup Mode** (BIOS: Secure Boot -> Erase/Clear all keys, or 'Reset to Setup Mode'). Then:

```sh
sudo pacman -S sbctl
sudo sbctl status                 # expect: Setup Mode: Enabled
sudo sbctl create-keys
sudo sbctl enroll-keys -m         # -m is not optional in practice
```

**Keep the `-m`.** sbctl(8) warns that some devices have signed firmware/option ROMs validated when Secure Boot is on. Enrolling only your own keys without Microsoft's certificates can leave the machine unable to initialise its own hardware. If your firmware has no 'reset to factory keys' option, you have no way back.

Find what actually needs signing rather than guessing paths. The Limine binary is named `BOOTX64.EFI`, not `limine.efi`:

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

Verify **before** re-enabling Secure Boot, because an unsigned binary here means the machine will not boot:

```sh
sudo sbctl verify
sudo sbctl list-files
sudo sbctl list-enrolled-keys
```

On Omarchy, `limine-mkinitcpio-hook` optdepends on sbctl and re-signs UKIs automatically once they are registered.

After re-enabling Secure Boot, `sudo sbctl status` should show `Secure Boot: Enabled`, `Setup Mode: Disabled`.

If you just want to move on: disable Secure Boot in firmware and stop there. Nothing on an Arch system requires it.

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

**Cause.** On distros that use `kernel-install` to write versioned entries into `/efi/loader/entries/`, removing or shadowing the package that provides the kernel-install plugin (`kernel-install-for-dracut`, which `eos-dracut` and `mkinitcpio-archiso` conflict with) stops entries being regenerated on kernel upgrade. Note there is no standalone `kernel-install` package on Arch: the binary ships inside `systemd`. Separately, the systemd-boot EFI binary itself is not auto-updated when the `systemd` package updates unless the update service is enabled.

> **Audit corrected this record.** `sudo pacman -S kernel-install` fails. I searched the Arch package database for name=kernel-install and got zero matches. On Arch the kernel-install binary is shipped inside the `systemd` package. The EndeavourOS package the record is really thinking of is `kernel-install-for-dracut`. Pasting the given command into a root shell on a machine that is already one bad boot away from unusable just errors out. Separately, `pacman -R mkinitcpio-archiso eos-dracut` aborts the entire transaction if either package is absent, so the 'if present' caveat needs to be in the command, not the prose. The bootctl update / systemd-boot-update.service half is correct.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `bootctl install` (as opposed to `update`) rewrites `\EFI\BOOT\BOOTX64.EFI` on the ESP. On a dual-boot machine that can displace another loader, so prefer `bootctl update` when systemd-boot is already installed.

**Fix.**

Boot the old entry (it still works) or chroot from a live USB, then:

```sh
# remove conflicting packages, only the ones actually installed
for p in mkinitcpio-archiso eos-dracut; do pacman -Qq "$p" &>/dev/null && sudo pacman -R "$p"; done
```

There is **no `kernel-install` package in the Arch repos**: the binary comes from `systemd`. Check what you have:

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

If you write entries by hand (plain Arch + mkinitcpio), use **unversioned** paths so they never go stale, in `/boot/loader/entries/arch.conf`:

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

## USB or docked keyboard dead at the LUKS passphrase prompt (keyboard hook after autodetect)

`usb-keyboard-dead-at-luks-prompt-keyboard-hook` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `luks`, `manjaro`, `mkinitcpio`, `omarchy`

**Symptom.** "At boot it asks for my disk password but my external keyboard does nothing." Typical setups are a laptop with a USB keyboard, a keyboard behind a USB 3 hub or dock, or a desktop where the keyboard was swapped. The keyboard works once the system is up. Often hit right after an archinstall install.

**Cause.** mkinitcpio's `keyboard` hook adds keyboard drivers to the initramfs. Placed after `autodetect`, it includes only the drivers for hardware present when the image was built. A keyboard on a different controller (a USB 3 hub needing `xhci_hcd`, an I2C laptop keyboard needing `i2c_hid_acpi`, a dock) has no driver in early userspace. The Arch wiki says the hook must come before `autodetect` on systems booted with different hardware configurations.

> **Audit corrected this record.** The Mkinitcpio wiki (raw) supports the cause: the keyboard hook must sit before autodetect for systems booted with different hardware, and xhci_hcd for a USB 3 hub and i2c_hid_acpi for some laptop keyboards. Archinstall issue 630 and forum thread 280596 both report the fix as moving keyboard before autodetect. On this machine /etc/mkinitcpio.conf.d/omarchy_hooks.conf assigns HOOKS=(base udev plymouth keyboard autodetect ... encrypt ...) so the Omarchy branch is right, and a MODULES+= drop-in sorting after it is safe because omarchy_hooks.conf only reads MODULES. The defect is the plain Arch example. The stock /etc/mkinitcpio.conf in mkinitcpio 41.1 is systemd-based (base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck), and an encrypted systemd setup uses sd-encrypt with rd.luks options. The record gave a full busybox line with udev and encrypt to paste in, which on such a system swaps the init and the unlock hook, so the root device is never unlocked and the machine does not boot. The fix now says to move keyboard within the existing line and gives both variants. The Omarchy verify was also missing. Not exercised: no initramfs was rebuilt.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Rebuilding the initramfs with a broken HOOKS line can make the machine unbootable. Keep the fallback image on plain Arch (`/boot/initramfs-linux-fallback.img` is built by the default preset), and have a live USB ready.

**Fix.**

## Plain Arch, EndeavourOS, CachyOS

In `/etc/mkinitcpio.conf`, move `keyboard` (and `keymap` or `sd-vconsole` with it) before `autodetect`. **Keep your existing init and encryption hooks**: do not change `systemd` to `udev` or `sd-encrypt` to `encrypt`, or the root device will not unlock.

Systemd-based line (the mkinitcpio default since version 39), for example:

```
HOOKS=(base systemd keyboard sd-vconsole autodetect microcode modconf kms block sd-encrypt filesystems fsck)
```

Busybox-based line, for example:

```
HOOKS=(base udev keyboard keymap consolefont autodetect microcode modconf kms block encrypt filesystems fsck)
```

For a keyboard behind a USB 3 hub, or a laptop keyboard on I2C, also add the module:

```
MODULES=(xhci_hcd i2c_hid_acpi)
```

Then rebuild:

```sh
sudo mkinitcpio -P
```

## Omarchy 4

Editing `/etc/mkinitcpio.conf` has no effect, because `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` assigns HOOKS wholesale and already places `keyboard` before `autodetect`. If a keyboard is still dead on Omarchy, the cause is different. See `i8042-builtin-keyboard-dead-at-luks-prompt` for a built-in PS/2 keyboard and `bluetooth-keyboard-cannot-unlock-luks` for Bluetooth. An I2C keyboard can get its module through a drop-in that sorts last:

```sh
echo 'MODULES+=(i2c_hid_acpi)' | sudo tee /etc/mkinitcpio.conf.d/zz-keyboard.conf
sudo limine-mkinitcpio
```

**Verify.** Plain Arch: `lsinitcpio /boot/initramfs-linux.img | grep -E 'xhci|hid'` lists the drivers. Omarchy: `grep -n HOOKS /etc/mkinitcpio.conf.d/omarchy_hooks.conf` shows `keyboard` before `autodetect`, and `sudo limine-mkinitcpio` finishes without `skipping.`. On either, reboot with only the external keyboard attached and type the passphrase.

Sources: <https://wiki.archlinux.org/title/Mkinitcpio> · <https://bbs.archlinux.org/viewtopic.php?id=280596> · <https://github.com/archlinux/archinstall/issues/630>

---

## Restore Linux boot priority after a Windows update hijacks the UEFI boot order

`windows-update-takes-over-uefi-boot-order` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `dual-boot`, `endeavouros`, `grub`, `limine`, `manjaro`, `omarchy`, `systemd-boot`, `uefi`, `windows`

**Symptom.** The machine booted GRUB/Limine fine for months. After a Windows feature update (or a BIOS update, or a CMOS reset) it now boots straight into Windows, or shows `grub rescue>`. The Linux entry is still in the firmware's boot list but sits below Windows Boot Manager.

**Cause.** Windows Setup writes `\EFI\Microsoft\Boot\bootmgfw.efi` and pushes `Windows Boot Manager` to the front of the UEFI `BootOrder` variable. Some firmware also rewrites `\EFI\BOOT\BOOTX64.EFI` (the removable fallback), clobbering a Linux loader that was installed there.

> **Audit corrected this record.** The efibootmgr diagnosis and `-o` reordering are correct. The manual entry-creation example names a loader file that does not exist: I checked the file list of the `limine` package (extra, 12.6.1) and it ships `usr/share/limine/BOOTX64.EFI`. There is no `limine.efi`. Omarchy's own scripts reference `/boot/EFI/limine/` and `/boot/EFI/BOOT/`, both holding BOOTX64.EFI. A user pasting `--loader '\EFI\limine\limine.efi'` creates a boot entry pointing at nothing, which on many firmwares is worse than the original problem.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `efibootmgr` writes NVRAM. A malformed `--create` can leave a dead entry. On a handful of buggy laptop firmwares, filling NVRAM with entries has caused firmware corruption. Delete stale entries with `efibootmgr -b XXXX -B` rather than accumulating them.

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

> **Audit corrected this record.** Issue 8454 is real and the replug workaround is exactly what the reporter confirms. But the issue's own quoted cmdline uses `archisosearchuuid=` and waits on /dev/disk/by-uuid. Current archiso replaced `archisolabel=` with archisosearchuuid=/archisosearchfilename=, so the suggested `archisolabel=<LABEL>` line is obsolete and will not be honoured. `copytoram` is also the wrong tool for this failure: copytoram runs *after* the medium is located, so it cannot rescue a device that is never found. It helps only once boot already works. And `dd of=/dev/sdX` is offered with no instruction to confirm the target, which is the classic way to overwrite the wrong disk.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `dd of=/dev/sdX` will destroy everything on whatever device you name. Confirm the target with `lsblk` immediately before running it, and never point it at a partition (`/dev/sdX1`) or at your system disk.

**Fix.**

**Verified workaround**: physically unplug and re-plug the USB stick as soon as the bootloader has handed off to the kernel (the moment the 'Waiting N seconds for device' line appears). The device re-enumerates and boot proceeds.

If it already dropped to the shell, re-plug and then:

```sh
blkid                       # confirm the medium is now visible
exit                        # returns control to the archiso hook, which retries
```

**Other things worth trying, in order:**

- Use a different physical port. Prefer USB-A 2.0 over USB-C/Thunderbolt on affected machines.
- At the boot menu press `e` and lengthen the initramfs device wait: append `rootdelay=60` to the kernel line. This is the timeout that produces the 'Waiting N seconds' message.
- Do **not** bother with `copytoram` for this failure. It copies the ISO to RAM only *after* the medium has been found, so it cannot help when the device is never detected. (Current archiso also no longer uses `archisolabel=`. The parameters are `archisosearchuuid=` / `archisosearchfilename=`, set by the ISO's own boot entries, so do not hand-write them.)
- Re-write the stick with `dd`. **Confirm the target device first**: `of=` pointed at the wrong disk destroys it with no prompt and no undo:

```sh
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS    # identify the USB stick by size/model/TRAN=usb
sudo dd if=omarchy.iso of=/dev/sdX bs=4M status=progress oflag=sync   # replace sdX, no partition number
sync
```

**Verify.** The installer reaches its menu/desktop without the emergency shell, and `lsblk -f` inside the live session shows the ISO label on the USB device.

Sources: <https://github.com/basecamp/omarchy/issues/8454> · <https://github.com/basecamp/omarchy/issues/8680>

---

## /boot became read-only mid-session, so the kernel update could not write the new image

`boot-esp-read-only-fat-errors-kernel-not-written` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `grub`, `limine`, `manjaro`, `omarchy`, `systemd-boot`, `uefi`

**Symptom.** An update prints something like:

```
install: cannot create regular file '/boot/vmlinuz-linux': Read-only file system
```

or fails while writing the UKI to `/boot/EFI/Linux/`. `dmesg` shows the ESP's FAT filesystem tripping:

```
FAT-fs (nvme0n1p1): error, fat_free_clusters: deleting FAT entry beyond EOF
FAT-fs (nvme0n1p1): Filesystem has been set read-only
```

Earlier in the log there may be `FAT-fs (nvme0n1p1): Volume was not properly unmounted. Some data may be corrupt. Please run fsck.`

**Cause.** The ESP is normally mounted with `errors=remount-ro`. Omarchy's own fstab line carries it, and so do most genfstab outputs. When the kernel's FAT driver hits an inconsistency, it silently remounts `/boot` read-only. Nothing tells you until something tries to write there, which is usually the next kernel update. The package's files under `/usr/lib/modules` are replaced, the boot image is not, and the next reboot starts a stale kernel against missing modules. The inconsistency comes from an unclean shutdown, a crash during an ESP write, or NVMe controller faults (see the NVMe APST record).

> **Audit corrected this record.** Confirmed on this workstation: the ESP fstab line carries errors=remount-ro (archinstall's genfstab output on an Omarchy install), /usr/bin/limine-update runs limine-install --no-efi-register then limine-mkinitcpio, and fsck.fat is from dosfstools 4.2. Forum thread 298530 supports the symptom lines (install: cannot create regular file '/boot/vmlinuz-linux', fat_free_clusters, set read-only) and the NVMe link, but the 'Volume was not properly unmounted' line in that thread was for dm-1 and sda1, not the ESP, and thread 249657 shows it only as an fsck dirty-bit prompt. Two defects in the fix. First, the source thread's own mount output was 'source write-protected, mounted read-only' and the expert reply says recovery most likely needs a reboot into the install ISO and a chroot. The record's online umount/fsck/remount path cannot work when the device itself refuses writes, and the record had no branch for that, leaving the reader told not to reboot with no way forward. Second, the plain Arch 'pacman -S linux' does not guarantee the same version: it takes whatever the sync database holds, so it was replaced with a pacman -U from the package cache at the installed version. The Omarchy branch now also notes that 4.0.4 machines carry two kernels (linux and linux-omarchy) and limine-update rebuilds both. Not exercised: no ESP was repaired, /boot is root-only here and was not listed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** `fsck.fat -a` picks the least destructive repair, but it can still truncate or drop damaged files on the ESP, which holds the boot loader, the kernel image and other systems' loaders. Copy the ESP first, as shown. Rebooting before the image is rewritten can leave the machine unbootable.

**Fix.**

**Do not reboot until `/boot` is repaired and the kernel image is rewritten, unless step 2 says the device itself is refusing writes.**

1. Confirm what happened:

```sh
sudo dmesg | grep -iE 'FAT-fs|nvme'
findmnt -n -o SOURCE,OPTIONS /boot        # 'ro,' at the start means it was remounted read-only
```

2. Back up the ESP, unmount it, repair it, and remount it:

```sh
sudo mkdir -p /root/esp-backup && sudo cp -a /boot/. /root/esp-backup/
esp=$(findmnt -n -o SOURCE /boot)
sudo umount /boot
sudo fsck.fat -v -a "$esp"
sudo fsck.fat -n "$esp"                   # second pass, check only
sudo mount /boot
findmnt -n -o OPTIONS /boot               # must start with rw
```

If `fsck.fat` cannot write, or `mount` prints `WARNING: source write-protected, mounted read-only`, the drive is refusing writes (often an NVMe controller fault, see `nvme-apst-controller-down-will-reset`). It cannot be fixed from this session. Boot the install USB, run `fsck.fat -a` on the ESP there, then chroot and rebuild the boot image as below (see `chroot-recovery-btrfs-missing-subvol`).

3. Rewrite the boot image.

Omarchy 4 (rebuilds every installed kernel, including both `linux` and `linux-omarchy` on 4.0.4):

```sh
sudo limine-update      # limine-install --no-efi-register, then limine-mkinitcpio
```

Plain Arch: reinstall the exact kernel version that is installed, from the package cache, so its hooks run again and no newer version is pulled in:

```sh
sudo pacman -U "/var/cache/pacman/pkg/linux-$(pacman -Q linux | cut -d' ' -f2)-x86_64.pkg.tar.zst"
```

If that file is not in the cache, `sudo pacman -S linux` works only when the sync database has not been refreshed since the failed update. Never use `-Sy` here.

**Verify.** `findmnt -n -o OPTIONS /boot` starts with `rw`, `sudo fsck.fat -n "$(findmnt -n -o SOURCE /boot)"` reports no errors, and the boot image's timestamp is current: `sudo ls -l /boot/EFI/Linux/` on Omarchy, `ls -l /boot/vmlinuz-linux` on Arch.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=298530> · <https://bbs.archlinux.org/viewtopic.php?id=249657>

---

## The ESP fills up after the linux-omarchy migration: two kernels plus snapshot copies, and the update checks only /

`esp-filling-with-two-kernels-after-linux-omarchy` · severity: **high** · frequency: **occasional** · applies to: `btrfs`, `limine`, `nvidia`, `omarchy`, `snapper`, `uefi`

**Symptom.** Since the 4.0.4 update `df -h /boot` keeps climbing. Then one of these: snapshot entries stop appearing in the Limine menu, a kernel update ends with a write error from the UKI hook, or the machine no longer boots its normal entry. `omarchy update` never warned. A reporter's 2 GB ESP held:

```
834M  /boot/EFI/Linux
  280M  omarchy_linux.efi
  277M  recovery20260920_linux-omarchy.efi
  277M  recovery20260920_linux.efi
277M  /boot/<machine-id>/limine_history/omarchy_linux.efi_sha256_...
```

**Cause.** With `ENABLE_UKI=yes` (Omarchy's `omarchy-uki.conf`) each installed kernel package gets its own UKI in `/boot/EFI/Linux/`, named `omarchy_<package>.efi` because Omarchy sets `CUSTOM_UKI_NAME="omarchy"`. The migration keeps stock `linux` and adds `linux-omarchy`, so the ESP space needed for current kernels doubles. UKIs written under another name, for example by a recovery root as in issue 13355, stay on the ESP until removed. `limine-snapper-sync` also stores the kernel files of each snapshot under `/boot/<machine-id>/limine_history/`, deduplicated by hash, so each distinct kernel version costs another copy. A UKI carrying NVIDIA modules and GPU firmware can exceed 250 MB. `limine-snapper-sync` stops adding entries at `LIMIT_USAGE_PERCENT=85`, which still allows the ESP to fill to 85 percent. Omarchy pins `MAX_SNAPSHOT_ENTRIES=6` in `/etc/limine-entry-tool.d/omarchy-defaults.conf`, but `limine-snapper-sync` 1.31.0 names only `/etc/limine-snapper-sync.conf` and `/etc/default/limine` as its config files, so that pin likely does not reach it. `omarchy-update-requires-free-space` checks only `/` for 10 GiB (identical in 4.0.4 and `quattro`). The UKI is written by the `90-mkinitcpio-install` hook after the pacman transaction has committed. Issue 11821 traced that `limine-entry-tool` copies with replace-existing, which unlinks the old UKI first, so running out of space part way through leaves that kernel with no UKI at all.

> **Audit corrected this record.** Confirmed that bin/omarchy-update-requires-free-space is byte-identical on quattro and in /usr/share/omarchy/bin and checks only / against 10 GiB. Confirmed in /usr/share/libalpm/scripts/limine-mkinitcpio-install line 115 that each kernel package gets ${UKI_PREFIX}_${KERNEL_NAME}.efi, with CUSTOM_UKI_NAME="omarchy" and ENABLE_UKI=yes from /etc/limine-entry-tool.d/. It runs from the PostTransaction hook /etc/pacman.d/hooks/90-mkinitcpio-install.hook. LIMIT_USAGE_PERCENT=85 is in /etc/limine-snapper-sync.conf. The limine-snapper-sync README recommends at least 4 GiB, and the Arch wiki ESP page suggests 8 GiB for Limine with Snapper. Issue 13355 supplies the quoted listing, the 280 MB UKI and the unbootable outcome, and issue 11821 supplies the REPLACE_EXISTING trace. Three defects. First, the `skipping.` string in the verify and danger is printed only when mkinitcpio fails to build the image in a temp directory (lines 202, 231, 244), not when the copy to the ESP runs out of space, so its absence proves nothing. Second, step 4 says a 98-*.conf drop-in is overridden by omarchy-defaults.conf's MAX_SNAPSHOT_ENTRIES=6. The only config paths in the limine-snapper-sync 1.31.0 binary are /etc/limine-snapper-sync.conf and /etc/default/limine, and its README names only those two. So it likely does not read /etc/limine-entry-tool.d at all, and Omarchy's pin of 6 may be inert, which leaves the default auto pruning. That is likely, not confirmed by running it. The advice to use /etc/default/limine stands either way. Third, the listing in 13355 shows UKIs named recovery20260920_* from a second root, which the cause did not explain. Not exercised: no command under /boot was run because it needs root, and no entries were removed.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Never delete files in `/boot/EFI/Linux/` or `limine_history` by hand. Use `limine-snapper-remove` and package removal, which also update `limine.conf`. If a kernel update printed an `ERROR:` from the UKI hook or ran out of space, do not reboot until `sudo limine-mkinitcpio` finishes without an `ERROR:` line and `sudo ls -lh /boot/EFI/Linux/` shows a full-size UKI for the kernel you boot. The hook's `skipping.` message covers only a failed image build, not a failed copy to the ESP. Repartitioning the ESP can destroy data.

**Fix.**

**1. See what is using the ESP.** `/boot` is mounted `dmask=0077`, so listing it needs root:

```bash
df -h /boot
sudo du -h --max-depth=3 /boot | sort -h | tail -15
sudo ls -lhS /boot/EFI/Linux/
limine-snapper-list
sudo limine-snapper-info
```

A UKI in `/boot/EFI/Linux/` that does not start with `omarchy_` was written by another root or under an old name. Find out which root wrote it before removing it.

**2. Remove the kernel you do not boot.** If `linux-omarchy` works on this machine, removing stock `linux` halves the space taken by current kernels. Follow the record on removing the unused stock kernel, which lists the checks to do first.

**3. Remove old snapshot entries** (the IDs come from `limine-snapper-list`):

```bash
sudo limine-snapper-remove 1..2
```

**4. Keep fewer entries from now on.** Put the setting in `/etc/default/limine`. `limine-snapper-sync` reads that file and `/etc/limine-snapper-sync.conf`, and it likely ignores `/etc/limine-entry-tool.d/`, so a drop-in there does not reliably reach it.

```bash
sudoedit /etc/default/limine
```

```
MAX_SNAPSHOT_ENTRIES=4
```

If you keep both kernels, the `EXCLUDE_SNAPSHOT_ENTRIES` setting documented in `/etc/limine-snapper-sync.conf` can keep the stock kernel out of new snapshot entries. Its patterns match entry names, so `EXCLUDE_SNAPSHOT_ENTRIES="linux"` should match only the entry named `linux`. That is untested here, so check `sudo limine-entry-tool --tree` after the next snapshot.

```bash
sudo limine-update
sudo limine-snapper-sync
```

**5. Before each update until this is fixed upstream**, check the ESP yourself:

```bash
df -h /boot      # keep free space above the size of your largest UKI plus a margin
```

The lasting fix is a larger ESP. limine-snapper-sync recommends at least 4 GiB, and Arch suggests 8 GiB when booting Snapper snapshots from Limine. Resizing means repartitioning from a live USB with a full backup.

**Verify.** `df -h /boot` shows free space well above one UKI's size. `sudo ls -lh /boot/EFI/Linux/` lists a non-empty `omarchy_<package>.efi` for every installed kernel. `sudo limine-entry-tool --tree` lists each kernel, and `sudo limine-snapper-info` reports no missing or corrupt kernels.

Sources: <https://github.com/omacom/omarchy/issues/11821> · <https://github.com/omacom/omarchy/issues/13355> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-requires-free-space> · <https://gitlab.com/Zesko/limine-snapper-sync> · <https://gitlab.com/Zesko/limine-entry-tool> · <https://wiki.archlinux.org/title/EFI_system_partition>

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

## Selecting linux-omarchy resets the machine back to Limine while the stock linux entry boots

`linux-omarchy-hard-reset-at-boot` · severity: **high** · frequency: **occasional** · applies to: `amd`, `desktop`, `intel`, `laptop`, `limine`, `linux-omarchy`, `omarchy`, `uki`

**Symptom.** "Since the 4.0.4 update made `linux-omarchy` the default, picking it in Limine reboots the machine within a couple of seconds. The Limine menu comes back every time and I never see the LUKS prompt. The regular `linux` entry boots fine." Sometimes it is intermittent: several reset cycles, then one attempt gets through and runs for days. `journalctl --list-boots` shows only the successful boots on the old kernel, and there is no pstore record.

**Cause.** There is no single root cause yet. On a Beelink SER9 (Ryzen AI 9 HX PRO 370) the reporter traced it to the platform firmware: BIOS SER9T407 reset the machine in very early boot on `linux-omarchy` 7.2.5-3, and flashing SER9T409 fixed it with nothing changed on the Linux side. The UKI hash, `limine.conf` and the module tree were all verified intact. The original Lenovo P1 Gen5 report is unresolved, and the maintainer asked affected users to test a 7.2.7rc1 kernel. The reporter noted config differences from Arch's kernel (`CONFIG_RESET_ATTACK_MITIGATION=y`, `CONFIG_SECURITY_LOCKDOWN_LSM_EARLY=y`) but could not tie them to the failure. On Intel machines, rule out the IOMMU default first (see `linux-omarchy-intel-iommu-default-on-boot-failures`).

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A BIOS flash that is interrupted can brick the board. Use AC power and the vendor's procedure.

**Fix.**

## Boot the stock kernel and make it the default for now

The migration keeps `linux` installed so it stays available if the new kernel cannot boot. `/etc/default/limine` overrides every drop-in:

```sh
sudo sed -i 's/^BOOT_ORDER=.*/BOOT_ORDER="linux, linux-omarchy, linux-omarchy-*, *, *fallback, Snapshots"/' /etc/default/limine
sudo limine-update
```

This is reversible, and `linux-omarchy` stays installed and listed.

## Look for a firmware update

```sh
omarchy-update-firmware      # wraps fwupd. Run it without sudo, it calls sudo itself
```

Many small-PC vendors are not on LVFS. If fwupd offers nothing, check the vendor's support page for a newer BIOS and flash it by the vendor's method.

## On Intel, try the IOMMU workaround once

At the Limine menu highlight `linux-omarchy`, press `e`, append `intel_iommu=off`, and boot with F10. If that boots, follow `linux-omarchy-intel-iommu-default-on-boot-failures`.

## Report with logs

If a failed attempt left anything behind, it is here (boot the stock kernel first):

```sh
journalctl --list-boots
journalctl -b -1 -k
uname -a
cat /proc/cmdline
```

**Verify.** `uname -r` shows the kernel you intended (`-arch` for stock, `-omarchy` for linux-omarchy). After a firmware update, select `linux-omarchy` across several cold boots and confirm none of them resets.

Sources: <https://github.com/omacom/omarchy/issues/12087>

---

## NVMe drive drops out with I/O timeouts and 'failed to set APST feature (-19)' (broken APST)

`nvme-apst-controller-down-will-reset` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `nvme`, `omarchy`, `systemd-boot`

**Symptom.** Random freezes, Btrfs suddenly read-only, or ext4 I/O errors, with the kernel log showing something like:

```
nvme nvme0: I/O 566 QID 7 timeout, aborting
nvme nvme0: I/O 840 QID 6 timeout, reset controller
nvme nvme0: Device not ready; aborting reset, CSTS=0x1
nvme nvme0: failed to set APST feature (-19)
```

The drive is unusable until the system is reset.

**Cause.** Some NVMe drives mishandle Autonomous Power State Transitions (APST) and do not come back from a deep power state. Reports cover the Kingston A2000 on firmware S5Z42105, some Samsung, Western Digital/SanDisk and SK Hynix drives. The controller stops answering, the kernel's reset fails, and the filesystem on it is lost for the rest of the boot. When it hits during writes to `/boot`, it is also a common cause of the FAT errors that remount the ESP read-only.

> **Audit corrected this record.** Fetched the raw Arch wiki Solid_state_drive/NVMe. It supports the cause (Kingston A2000 on S5Z42105, Samsung, WD/SanDisk, SK Hynix), the log lines in the symptom's first block, Btrfs read-only and ext4 I/O errors, nvme_core.default_ps_max_latency_us=0, the pcie_aspm=off pcie_port_pm=off fallback, the BIOS power-saving step and the Kingston firmware. It does not contain 'controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10' anywhere, yet the title is built on it and the record cites no other source. That message and its PCI_STATUS value are unsupported precision, so the title and symptom were corrected to the messages the source gives. The Omarchy branch held on this machine: /usr/lib/limine/limine-common-functions loads /etc/limine-entry-tool.d/*.conf before /etc/default/limine and every file appends with +=, so a drop-in named nvme-apst-off.conf is applied, and limine-mkinitcpio rebuilds the UKI that carries the cmdline. CONFIG_NVME_CORE=m on linux-omarchy 7.2.5-3 and /sys/module/nvme_core/parameters/default_ps_max_latency_us exists (reads 100000 here), so the verify step is valid. Not exercised: the parameter was not applied.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Disabling APST, and especially PCIe ASPM, raises idle power draw and shortens laptop battery life. Each controller drop risks losing unwritten data, so back up before experimenting.

**Fix.**

Disable APST with the kernel parameter `nvme_core.default_ps_max_latency_us=0`.

Omarchy 4:

```sh
echo 'KERNEL_CMDLINE[default]+=" nvme_core.default_ps_max_latency_us=0"' | sudo tee /etc/limine-entry-tool.d/nvme-apst-off.conf
sudo limine-mkinitcpio
```

Plain Arch with GRUB: add it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then:

```sh
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

systemd-boot: append it to the `options` line in `/boot/loader/entries/*.conf`.

If failures continue, the wiki's next step is to add `pcie_aspm=off pcie_port_pm=off` the same way, and to look for NVMe or PCIe power-saving options in the firmware setup. Also check the vendor for a drive firmware update, such as Kingston's for the A2000.

**Verify.** `cat /sys/module/nvme_core/parameters/default_ps_max_latency_us` prints `0`, and `journalctl -k | grep -i 'nvme.*\(timeout\|reset\)'` stays empty across days of normal use.

Sources: <https://wiki.archlinux.org/title/Solid_state_drive/NVMe>

---

## Omarchy: Limine panics on a stale /EFI/Linux/arch-linux.efi entry after upgrading

`omarchy-limine-panic-stale-arch-linux-efi` · severity: **high** · frequency: **occasional** · applies to: `desktop`, `laptop`, `limine`, `omarchy`, `uefi`

**Symptom.** After upgrading to Omarchy Quattro (4.x), the Limine countdown expires and the machine panics instead of booting:

```
PANIC: efi: Failed to open image with path 'boot():/EFI/Linux/arch-linux.efi'
```

The menu still lists an entry titled `Arch Linux (linux)` that no longer works.

**Cause.** `archinstall` originally wrote a Limine entry pointing at the unified kernel image `/EFI/Linux/arch-linux.efi`. Omarchy's upgrade path deletes that UKI when it takes over kernel image generation, but `normalize_limine_config()` does not strip the now-dangling entry from `/boot/limine.conf`. If that stale entry is the default, the timeout selects a file that is not there. Tracked as basecamp/omarchy#7989.

> **Audit corrected this record.** Issue 7989 is real and the title matches the record's cause exactly ('omarchy-upgrade-to-quattro leaves archinstall's /EFI/Linux/arch-linux.efi Limine entry in place, so the default boot entry panics'), and normalize_limine_config() does exist in bin/omarchy-upgrade-to-quattro. The hand-edit works, but it is the fragile route: any subsequent `omarchy update` replaces /boot/limine.conf anyway. Also `default_entry: 1` is offered as the example while Omarchy's shipped template uses `default_entry: 2`. Limine's index is 1-based (confirmed in CONFIG.md), so pasting 1 may silently select a different entry than intended.
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

`default_entry` is a **1-based index into the entries that remain after your edit**. Count them rather than copying a number. Verify by booting once with a visible menu:

```
timeout: 5
default_entry: 1
```

Then apply:

```sh
sudo limine-update          # re-reads /boot/limine.conf
sudo limine-mkinitcpio      # rebuilds the UKIs on the ESP
```

A hand-edited /boot/limine.conf does not survive the next `omarchy update`, but that is fine here, because the refresh regenerates from the template, which never contained the stale entry.

**Verify.** Reboot and let the timeout expire without touching the keyboard. The machine boots straight into Omarchy. `grep -n 'arch-linux.efi' /boot/limine.conf` returns nothing.

Sources: <https://github.com/basecamp/omarchy/issues/7989> · <https://github.com/limine-bootloader/limine/blob/v9.x/CONFIG.md>

---

## UEFI boot entries vanish after every reboot (NVRAM full, or firmware wiping entries)

`uefi-nvram-boot-entries-dropped-use-fallback-path` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`, `uefi`

**Symptom.** You create a boot entry, `efibootmgr -v` shows it, everything works, and after one reboot it is gone again, or the firmware boots Windows instead, or you get `No bootable device found` / `Reboot and Select proper Boot device`. Sometimes `efibootmgr --create` fails outright with:

```
Could not prepare Boot variable: No space left on device
```

Common on Lenovo ThinkPads (T16 Gen 2 and similar), on boards with CSM enabled, and after running Omarchy's Setup > Direct Boot, which adds an EFI entry the firmware may then discard.

**Cause.** Three separate firmware behaviours produce the same symptom. (1) NVRAM is full, and some boards silently drop entries instead of erroring. (2) The UEFI spec allows OEMs to do "NVRAM maintenance" at boot: firmware that finds no EFI binary at a hardcoded path concludes the disk has no OS and wipes the entries associated with it. (3) Options such as Lenovo's "OS Optimized Defaults", or a firmware that removes entries pointing at drives absent at POST, delete non-Windows entries on principle. In all three cases NVRAM is the wrong place to rely on, and the removable-media fallback path is the durable answer.

> **Audit corrected this record.** The three firmware behaviours, the fallback-path strategy, and every non-Limine command check out (grub-install --removable, `bootctl install` which does write EFI/BOOT/BOOTX64.EFI, bootctl --no-variables install, efibootmgr --create/-o/-b NNNN -B, clearing dump-* efivars, Lenovo OS Optimized Defaults, and Omarchy's Direct Boot which is documented as refusing to run on American Megatrends and Apple firmware). But the headline command for the target distro is invented: there is no `limine-install` binary and no `--fallback` flag anywhere in the limine, limine-entry-tool, limine-mkinitcpio-hook or limine-snapper-sync packages. The limine package ships /usr/share/limine/BOOTX64.EFI and the fallback install is a config switch (ENABLE_LIMINE_FALLBACK), which Omarchy already sets to yes in etc/limine-entry-tool.d/omarchy-defaults.conf. The manual-copy step also invents a source path (/boot/EFI/limine/limine_x64.efi), and the efibootmgr --loader value repeats it.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting the wrong `efibootmgr -b NNNN -B` entry (Windows Boot Manager on a dual-boot machine) leaves that OS unbootable until you recreate it. Writing to or deleting files under /sys/firmware/efi/efivars has bricked machines with buggy firmware. Remove only `dump-*` files, never `rm -rf` the directory. Do not add `efi_no_storage_paranoia` as a permanent kernel parameter: it disables the safeguard that keeps NVRAM from filling to the point of bricking the board. On a shared ESP, `grub-install --removable` and `bootctl install` both overwrite `\EFI\BOOT\BOOTX64.EFI`, which may currently be another OS's loader.

**Fix.**

Everything in the record stands except the Limine steps.

There is no `limine-install --fallback`. On Omarchy/limine-entry-tool the fallback path is a configuration switch, and Omarchy already ships it enabled:

```bash
grep -rn 'ENABLE_LIMINE_FALLBACK' /etc/default/limine /etc/limine-entry-tool.d/
# Omarchy: ENABLE_LIMINE_FALLBACK=yes in /etc/limine-entry-tool.d/omarchy-defaults.conf
sudo limine-update
ls -l /boot/EFI/BOOT/BOOTX64.EFI
```

If it is unset (plain Arch), add `ENABLE_LIMINE_FALLBACK=yes` to /etc/default/limine and run `sudo limine-update`, or place the binary by hand. The source is the one the limine package ships:

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

**Verify.** `efibootmgr -v` lists your entry after a reboot. `ls -l /boot/EFI/BOOT/BOOTX64.EFI` exists. The machine still boots after clearing NVRAM entries or resetting the firmware to defaults.

Sources: <https://wiki.archlinux.org/title/Unified_Extensible_Firmware_Interface> · <https://wiki.archlinux.org/title/EFI_system_partition> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/blob/quattro/manual/47-system-snapshots.md>

---

## "unknown filesystem type 'vfat'" when mounting /boot or /boot/efi at boot

`vfat-module-missing-boot-efi-mount-fails` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `manjaro`, `omarchy`, `systemd`, `uefi`

**Symptom.** Immediately after an update the boot sequence reports:

```
[FAILED] Failed to mount /boot/efi.
mount: /boot/efi: unknown filesystem type 'vfat'.
```

and the system drops to emergency mode. The partition is fine: `fsck.vfat` from a live USB reports no errors, and reinstalling GRUB does not help.

**Cause.** The `vfat` kernel module (plus its `nls_iso8859-1` / `nls_cp437` codepage dependencies) is not available when the mount is attempted. Two ways this happens: the initramfs/early boot lacks the module, or the kernel package was upgraded while running and `/usr/lib/modules/$(uname -r)` was replaced, so `modprobe vfat` fails until reboot.

> **Audit corrected this record.** The two causes and both remedies are right, and `kernel-modules-hook` is a real package (extra 0.1.7) that solves the upgrade-while-running case. Two problems. `MODULES=(vfat nls_cp437 nls_iso8859-1)` is written as a bare assignment. On Omarchy and on NVIDIA systems MODULES already holds the early-KMS list, and pasting this silently deletes it, trading a /boot/efi mount failure for a black screen. Also the module name is spelled `nls_iso8859-1` in the mkinitcpio block and `nls_iso8859_1` in the dracut block. Because modprobe treats - and _ interchangeably this happens to work, but the inconsistency invites hand-editing errors.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

**First, is this only the running system?** If `modprobe vfat` fails with 'Module vfat not found in directory /lib/modules/6.x', the kernel was upgraded underneath you, so just reboot, then prevent recurrence:

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

Rebuild (one command, not both, because limine-mkinitcpio wraps mkinitcpio):

```sh
sudo mkinitcpio -P        # Arch / CachyOS
sudo limine-mkinitcpio    # Omarchy (rebuilds initramfs AND the UKIs on the ESP)
```

For a **dracut** system (EndeavourOS default), use a drop-in, and keep the module names consistent with the mkinitcpio spelling:

```sh
sudo tee /etc/dracut.conf.d/force-vfat.conf >/dev/null <<'EOF'
force_drivers+=" vfat nls_cp437 nls_iso8859-1 "
EOF
sudo dracut-rebuild
```

(`dracut-rebuild` is EndeavourOS's wrapper. On plain dracut use `sudo dracut --regenerate-all --force`.)

**Verify.** `lsinitcpio /boot/initramfs-linux.img | grep vfat` (mkinitcpio) or `lsinitrd | grep vfat` (dracut) finds the module, `sudo mount -a` succeeds, and `systemctl --failed` is empty after reboot.

Sources: <https://forum.endeavouros.com/t/emergency-mode-failed-to-mount-boot-efi-vfat-error-tried-base-reinstall-issue-persists/75747> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://forum.endeavouros.com/t/boot-failing-after-update-kernel-modules-not-loading/37928>

---

## Laptop's built-in keyboard types nothing at the LUKS prompt but works after boot (i8042 multiplexing)

`i8042-builtin-keyboard-dead-at-luks-prompt` · severity: **high** · frequency: **rare** · applies to: `arch`, `cachyos`, `endeavouros`, `grub`, `laptop`, `limine`, `luks`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** "At the disk unlock prompt my laptop's own keyboard does nothing. It works in the BIOS, in the boot menu and on the desktop after boot. I have to plug in a USB keyboard to type the passphrase." Seen on Fujitsu LIFEBOOK P727 and U938 among others. The kernel log shows the built-in keyboard as `AT Translated Set 2 keyboard` on the i8042 controller, with:

```
i8042: PNP: PS/2 Controller [PNP0320:KBC,PNP0f13:PS2M] at 0x60,0x64 irq 1,12
i8042: Detected active multiplexing controller, rev 1.1
```

**Cause.** The i8042 PS/2 controller reports active multiplexing (separate AUX ports), and on these models the keyboard does not work in that mode during early boot. The initramfs is not missing a module: Omarchy's hooks already put `keyboard` before `autodetect`, and the keyboard works later in the same boot. `i8042.nomux` tells the kernel not to use the multiplexing mode. The upstream kernel already carries the same quirk for LIFEBOOK E5411 and U728 as `SERIO_QUIRK_NOAUX`, so the affected set is wider than one model. `noaux` disables the AUX port entirely, which kills a PS/2 touchpad, so `nomux` is the right choice where the touchpad is PS/2.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

## Test for one boot

At the boot menu edit the entry (Limine: `e`, GRUB: `e`, systemd-boot: `e`), append `i8042.nomux` to the kernel command line and boot. Unplug any USB keyboard and confirm the built-in one types at the prompt.

## Omarchy 4: persist it in the UKI

```sh
echo 'KERNEL_CMDLINE[default]+=" i8042.nomux"' | sudo tee /etc/limine-entry-tool.d/i8042-nomux.conf
sudo limine-mkinitcpio
```

## Plain Arch

GRUB: add it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then:

```sh
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

systemd-boot: append `i8042.nomux` to the `options` line of the entry in `/boot/loader/entries/*.conf`.

If your touchpad is I2C rather than PS/2 and `nomux` does not help, `i8042.noaux` is what the upstream kernel quirks use for those models. It will disable a PS/2 touchpad.

**Verify.** `grep -o i8042.nomux /proc/cmdline` prints the parameter. `journalctl -k -b | grep i8042` no longer shows `Detected active multiplexing controller`. Cold boot with no USB keyboard attached and type the passphrase on the built-in keyboard.

Sources: <https://github.com/omacom/omarchy/issues/13502> · <https://github.com/omacom/omarchy/pull/13675>

---

## UKI rebuild fails with 'module not found' for every module and 'No modules were added to the image' (missing modules.dep)

`missing-modules-dep-no-modules-added` · severity: **high** · frequency: **rare** · applies to: `arch`, `limine`, `mkinitcpio`, `omarchy`, `uki`

**Symptom.** The first time anything rebuilds the initramfs or UKI on a fresh install (a kernel update, a new kernel parameter, enabling hibernation), mkinitcpio reports every module as missing, even core ones:

```
==> ERROR: module not found: 'nvme_core'
==> ERROR: module not found: 'dm_crypt'
==> WARNING: No modules were added to the image. This is probably not what you want.
==> WARNING: errors were encountered during the build. The image may not be complete.
```

**Cause.** `/usr/lib/modules/<version>/modules.dep` and the other depmod outputs were never generated for the installed kernel. In the report, the module directory held only `kernel/`, `modules.builtin`, `modules.builtin.modinfo`, `modules.order`, `pkgbase` and `vmlinuz` after an install bootstrapped with `pacman -r /mnt`. The reporter guessed that depmod used the live ISO's `uname -r`, but kmod's alpm script (`/usr/share/libalpm/scripts/depmod`) passes each target's version explicitly, so that is not the mechanism. Why the hook left nothing behind is not confirmed. Without `modules.dep`, mkinitcpio cannot resolve any module name. `limine-mkinitcpio-install` detects the failed build and keeps the existing UKI, so the machine still boots its current kernel.

> **Audit corrected this record.** #11399 supports the symptom, the module directory listing, the depmod repair and the safe failure. The error strings are exact: /usr/lib/initcpio/functions lines 740 and 1308 and /usr/bin/mkinitcpio line 409. /usr/share/libalpm/scripts/limine-mkinitcpio-install prints 'mkinitcpio failed for kernel ..., skipping.' and moves on, which matches the claim that the existing UKI is kept. /usr/share/libalpm/scripts/depmod from kmod 34.2-1 runs `depmod $(basename "$f")` for each target, so the cause is right to reject the reporter's uname -r guess and to call the mechanism unconfirmed. On this workstation both installed kernels (7.2.3-arch1-3, 7.2.5-3-omarchy) have modules.dep, though later updates may have regenerated them. The fix loop and both rebuild branches are correct. The only change is frequency. The evidence is one issue with no comments and no confirmed mechanism, which does not support 'occasional', so it is set to rare. Not exercised: depmod was not run, and the test VMs were shut off so their install-time module trees were not checked.
>
> *The Cause above was rewritten on 2026-10-04 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Generate the missing depmod files for every installed kernel that lacks them, then rebuild:

```sh
ls /usr/lib/modules/
for d in /usr/lib/modules/*/; do
  v=$(basename "$d")
  [[ -f "$d/kernel" || -d "$d/kernel" ]] || continue
  [[ -f "$d/modules.dep" ]] || sudo depmod -a "$v"
done
```

Omarchy 4:

```sh
sudo limine-mkinitcpio
```

Plain Arch:

```sh
sudo mkinitcpio -P
```

**Verify.** `ls /usr/lib/modules/$(uname -r)/modules.dep` exists, and the rebuild finishes without `module not found` or `No modules were added to the image`.

Sources: <https://github.com/omacom/omarchy/issues/11399>

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

**Symptom.** You dual-boot Omarchy with Windows. You add a Windows entry to the Limine menu and it works. Then after the next `omarchy update` (or any run of `omarchy-refresh-limine`) the Windows entry is gone again and the only way into Windows is the firmware boot menu. On some installs the Omarchy installer also created a second, redundant 2 GB ESP (`omarchy-efi`) instead of reusing the Windows ESP, so the firmware never surfaces the Omarchy entry at the top level.

**Cause.** `omarchy-refresh-limine` overwrites `/boot/limine.conf` from a template that contains no OS entries, then runs helpers that only re-add Linux/snapshot entries. Any foreign-OS entry in the file is silently and permanently discarded. Tracked upstream as basecamp/omarchy#7867.

> **Audit corrected this record.** The problem is real and precisely described. I read bin/omarchy-refresh-limine and it does `sudo mv /boot/limine.conf /boot/limine.conf.bak` then copies default/limine/limine.conf over it, and issue 7867's title confirms both the dropped Windows entry and the redundant ESP. The Limine syntax is valid (CONFIG.md confirms `protocol: efi` is the EFI-chainload alias and `boot(N):/...` selects partition N of the boot drive). But the fix has three defects. The `cp /boot/limine.conf /etc/limine-windows-entry.conf.bak` line saves the whole config under a name implying it holds only the Windows entry and is never used again. The re-apply script never runs `limine-update`, so the edited config may not be picked up. `boot(1)` is only correct when Windows sits on partition 1 of the *same* drive Limine booted from, and on the dual-ESP layout the record itself describes, that is exactly what is not true.
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

Add to `/boot/limine.conf`. If Windows is on the same drive Limine booted from, `boot(N)` works. N is the 1-based partition index, **not** always 1:

```
/Windows
    protocol: efi
    path: boot(1):/EFI/Microsoft/Boot/bootmgfw.efi
```

If Windows has its own ESP on another disk (the redundant-ESP layout in issue 7867), `boot()` cannot reach it, so use the partition GUID instead, which is stable across disk reordering:

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

**Verify.** Reboot. The Limine menu lists **Windows** and selecting it chainloads the Windows Boot Manager. Re-run `omarchy update`, then confirm the entry is still (or is again) present in `/boot/limine.conf`.

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

## Boot stalls 90 seconds on 'Timed out waiting for device /dev/tpmrm0'

`tpmrm0-timeout-slow-boot` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`, `tpm`

**Symptom.** After an update, boot sits on a black screen with a blinking cursor for 30 to 90 seconds before the login screen. The journal shows:

```
systemd[1]: Expecting device /dev/tpmrm0...
systemd[1]: dev-tpmrm0.device: Job dev-tpmrm0.device/start timed out.
systemd[1]: Timed out waiting for device /dev/tpmrm0.
systemd-tpm2-setup[784]: No complete TPM2 support detected, exiting gracefully.
```

usually after a kernel line such as:

```
tpm_crb MSFT0101:00: [Firmware Bug]: ACPI region does not cover the entire command/response buffer.
tpm_crb MSFT0101:00: probe with driver tpm_crb failed with error -16
```

**Cause.** `systemd-tpm2-generator` makes `sysinit.target` wait on `tpm2.target` when the firmware reports a TPM2 but the kernel has not exposed one yet. This arrived with systemd 256 in June 2024. When the kernel driver fails to probe (a firmware ACPI region bug, `tpm_tis` error -1, or a TPM disabled in a way the firmware still advertises), the device never appears, and systemd waits for the full device timeout before giving up. On Omarchy's `linux-omarchy` 7.2.5-3, a separate cause gives the same symptom on Broadwell machines with Intel PTT: see `linux-omarchy-intel-iommu-default-on-boot-failures`.

> **Audit corrected this record.** bbs 296699 carries the exact journal lines, the tpm_crb ACPI region error -16, systemd 256-1-arch, and both mask fixes (tpm2.target and dev-tpmrm0.device). bbs 297009 adds the tpm_tis error -1 case and a 30 to 40 second wait. systemd 261's NEWS lists systemd-tpm2-generator and tpm2.target under 'CHANGES WITH 256', and systemd-tpm2-generator(8) on this machine documents `systemd.tpm2_wait=` with false meaning the target is not inserted even if the firmware reported a device. omarchy-pkgs#677 supports the linux-omarchy 7.2.5-3 Broadwell PTT cross-reference. It is still open, the reporter confirmed 7.2.7rc1 fixes it, and the local omarchy sync database (dated 2026-09-18) still offers 7.2.5-3. The Omarchy branch writes a `KERNEL_CMDLINE[default]+=` drop-in into /etc/limine-entry-tool.d, which matches the shape of /etc/limine-entry-tool.d/omarchy-defaults.conf. The one defect is that the symptom puts a paraphrase in quotation marks as if it were a user's words. No source contains that sentence, so the symptom is rewritten without the quote. Not exercised: no parameter was applied and no unit was masked.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Masking `tpm2.target` or passing `systemd.tpm2_wait=0` on a machine that unlocks LUKS through the TPM can make the unlock run before the TPM is ready, so you fall back to the passphrase or the boot fails. Only apply it where the TPM is unused or absent.

**Fix.**

First decide whether you use the TPM at all, for example for LUKS auto-unlock with `systemd-cryptenroll`. If you do, fix the firmware side instead (BIOS update, or TPM enabled properly under Security > TPM 2.0).

## Tell the generator not to wait (preferred)

The kernel parameter `systemd.tpm2_wait=0` is documented in `systemd-tpm2-generator(8)` for exactly this case.

Omarchy 4:

```sh
echo 'KERNEL_CMDLINE[default]+=" systemd.tpm2_wait=0"' | sudo tee /etc/limine-entry-tool.d/tpm2-nowait.conf
sudo limine-mkinitcpio
```

Plain Arch with GRUB: add `systemd.tpm2_wait=0` to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`. With systemd-boot, append it to the `options` line in `/boot/loader/entries/*.conf`.

## Or mask the wait (the forum fix)

```sh
sudo systemctl mask tpm2.target
# one reporter masked the device unit instead:
# sudo systemctl mask dev-tpmrm0.device
```

If you have no TPM and the firmware still advertises one, disabling the TPM in firmware setup also removes the wait.

**Verify.** `journalctl -b | grep -i tpmrm0` shows no timeout, and `systemd-analyze` reports userspace time down by roughly the old wait. `systemd-analyze critical-chain` no longer lists `dev-tpmrm0.device`.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=296699> · <https://bbs.archlinux.org/viewtopic.php?id=297009> · <https://github.com/omacom/omarchy-pkgs/issues/677>

---

## Remove the unused stock linux kernel that sits beside linux-omarchy (and whose entry can get booted by mistake)

`unused-stock-linux-kernel-entry-remove-safely` · severity: **medium** · frequency: **common** · applies to: `btrfs`, `limine`, `omarchy`, `snapper`

**Symptom.** The machine runs `linux-omarchy`, yet `pacman -Q linux` shows the stock kernel still installed and the Limine menu still lists a `linux` entry. Fresh 4.0.4 installs have it too. One reporter booted it by accident three weeks after installing, on a kernel version they had never run, and blamed it for a Btrfs failure. Others just see the ESP filling and kernel updates taking twice as long, since every update rebuilds two UKIs and two sets of DKMS modules.

**Cause.** Two paths leave stock `linux` in place. The upgrade migration `1789325478.sh` keeps it on purpose as an escape hatch. Fresh installs get it from the archinstall base package set (`'linux'` appears in the installer's package list in `/var/log/archinstall/install.log` per issue 13537), even though Omarchy's own package lists name `linux-omarchy`. `limine-entry-tool` creates an entry for every installed kernel, so a never-updated-by-use kernel stays one keypress away. The Btrfs corruption attribution in issue 13537 was made by an agent-filed report and is not confirmed. limine-snapper-sync's own documentation does warn that switching often between kernel versions raises the risk of filesystem breakage.

> **Audit corrected this record.** Issue 13537 supports the fresh-install path. Its archinstall log line lists 'linux', it says omarchy-base.packages has no plain linux, and it says the report was filed by an agent (glm-5.3-flash via pi), so the record is right to call the Btrfs attribution unconfirmed. install/omarchy-other.packages on quattro names linux-omarchy and linux-omarchy-headers. The limine-snapper-sync README line 641 has the kernel-switching warning. Confirmed here: 00-omarchy-update-guard.hook triggers only on Operation = Upgrade, so `pacman -R` passes. The 60/90 remove hooks call `limine-entry-tool --remove-all <kernel>`, which removes the entry and its files. linux-omarchy provides KSMBD-MODULE, NTSYNC-MODULE, VIRTUALBOX-GUEST-MODULES and WIREGUARD-MODULE. Three defects in the fix. First, on a stock 4.0.4 machine `pacman -Qi linux` shows `Required By: ntsync-autoload` (it depends on NTSYNC-MODULE). The record tells the reader that this field shows prebuilt module packages that must be dealt with first, so a reader would stop or remove the wrong thing. linux-omarchy satisfies that dependency. Second, `pacman -R linux linux-headers` aborts with 'target not found' and removes nothing when linux-headers is absent. Third, it ignores Direct Boot. Issue 12145 shows the firmware entry pointing at \EFI\Linux\omarchy_linux.efi, the stock kernel's UKI, and the remove hook deletes that file. On such a machine the firmware entry then points at nothing, and the danger does not mention it. Not exercised: nothing was removed here, because this workstation still needs both kernels for other records.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Omarchy 4 has no fallback initramfs entry. After removal, the only bootable kernel is `linux-omarchy` plus older snapshot entries, so a future `linux-omarchy` regression on your hardware needs a snapshot or a live USB to recover. Keep an Omarchy or Arch USB stick. Never remove the kernel you are currently running. With Direct Boot enabled, removing `linux` deletes `omarchy_linux.efi`, so a firmware entry still pointing at it has nothing to boot. Repoint it before removing the kernel.

**Fix.**

**1. Check it is safe.** All of these must hold:

```bash
uname -r                                   # must end in -omarchy
pacman -Qi linux | grep 'Required By'      # see below
dkms status                                # DKMS modules built for the -omarchy kernel
pacman -Q linux-t2 2>/dev/null             # T2 Macs use linux-t2: stop here if present
efibootmgr | grep -E 'Omarchy([[:space:]]|$)'   # Direct Boot entry, see step 2
```

`ntsync-autoload` in `Required By` is expected on Omarchy 4. It depends on `NTSYNC-MODULE`, which `linux-omarchy` also provides, so it does not block removal. Any other package listed there, such as `nvidia-open`, is a prebuilt module package built for stock `linux` only: switch it to its DKMS variant first (see the prebuilt nvidia-open record). If this machine needed stock `linux` because of a `linux-omarchy` regression, keep it.

**2. If Direct Boot is enabled, point it away from the stock UKI first.** Removing `linux` deletes `/boot/EFI/Linux/omarchy_linux.efi`, and a Direct Boot entry may point at exactly that file. If the `efibootmgr` line above shows `\EFI\Linux\omarchy_linux.efi` (case may differ), replace the entry. `XXXX` is its number and the disk and partition come from `findmnt`:

```bash
findmnt -no SOURCE /boot                     # e.g. /dev/nvme0n1p1 is disk /dev/nvme0n1, partition 1
sudo efibootmgr --bootnum XXXX --delete-bootnum
sudo efibootmgr --create --disk /dev/nvme0n1 --part 1 --label Omarchy --loader '\EFI\Linux\omarchy_linux-omarchy.efi'
```

**3. Remove the stock kernel and, if installed, its headers.** `pacman -R` is not blocked by Omarchy's guard, which only fires on upgrade transactions. `pacman -R` aborts on a package that is not installed, so check the headers first:

```bash
pacman -Q linux-headers                    # if this says 'not found', drop it from the next line
sudo pacman -R linux linux-headers
```

The `60-limine-mkinitcpio-remove-pre` and `90-limine-mkinitcpio-remove-post` hooks remove its Limine entry and its UKI. If pacman refuses because another package requires `linux`, read the package it names before going further. `linux-omarchy` provides `NTSYNC-MODULE`, `WIREGUARD-MODULE`, `KSMBD-MODULE` and `VIRTUALBOX-GUEST-MODULES`, which satisfy packages depending on those.

**4. Check the result.**

```bash
sudo limine-entry-tool --tree
sudo ls /boot/EFI/Linux/
df -h /boot
efibootmgr | grep -E 'Omarchy([[:space:]]|$)'   # must not name omarchy_linux.efi
```

**Verify.** `pacman -Q linux` reports it is not installed, the Limine menu lists only `linux-omarchy` (plus snapshots), and a reboot lands in `uname -r` ending in `-omarchy`.

Sources: <https://github.com/omacom/omarchy/issues/13537> · <https://github.com/omacom/omarchy/blob/v4.0.4/migrations/1789325478.sh> · <https://gitlab.com/Zesko/limine-snapper-sync> · <https://github.com/omacom/omarchy/issues/12145>

---

## Windows entry added by limine-scan panics with 'image not found'

`limine-scan-windows-path-case-panic` · severity: **medium** · frequency: **occasional** · applies to: `dual-boot`, `limine`, `omarchy`, `uefi`, `windows`

**Symptom.** Following the Omarchy dual-boot manual, you run `limine-scan` and add Windows. Selecting **Windows Boot Manager** in Limine panics instead of starting Windows. The reported message:

```
image not found — is the path correct?
```

`/boot/limine.conf` shows the path in capitals:

```
/Windows Boot Manager
    protocol: efi
    path: guid(<esp-partuuid>):/EFI/MICROSOFT/BOOT/BOOTMGFW.EFI
```

**Cause.** `limine-scan` runs `limine-entry-tool --scan`, which takes EFI paths from `efibootmgr`. Firmware often reports the Windows loader path in upper case (`\EFI\MICROSOFT\BOOT\BOOTMGFW.EFI`), and the scanner only turns backslashes into slashes. Limine 12's path rules (`/usr/share/doc/limine/CONFIG.md`) match a FAT name case-insensitively only if it fits the 8.3 short form. `BOOT` and `BOOTMGFW.EFI` fit, so their case does not matter. `MICROSOFT` is nine characters and does not fit, so it must match the on-disk `Microsoft` exactly, and the lookup fails. The reporter on #7906 verified that correcting the casing made Windows boot immediately.

> **Audit corrected this record.** #7906 is an open report of exactly this problem, and the reporter verified that correcting the casing fixed it. The manual's limine-scan step is on the quattro branch at manual/50-dual-boot-install.md. The record's statement that Limine's FAT lookup is case-sensitive is too broad. /usr/share/doc/limine/CONFIG.md from limine 12.8.0-1 on this machine says: 'On FAT volumes a name that fits the 8.3 short form is matched case insensitively ... a name too long for that form is matched case sensitively.' So BOOT and BOOTMGFW.EFI resolve in either case. The component that fails is MICROSOFT, nine characters, which does not fit 8.3 and so must match 'Microsoft' exactly. That is why the casing fix works, and it tells a reader which part matters. The cause has been rewritten. limine-entry-tool's changelog has 1.31.0 'Ensure correct case-sensitive path resolution', which is older than the 2026-08-23 issue and evidently did not cover --scan. omarchy-refresh-limine on this machine does overwrite /boot/limine.conf from the default, which supports the closing note. Not exercised: no Windows ESP here. Second audit confirmed the corrected text: Second audit of the corrected text. #7906 is open and its reporter verified that fixing the casing booted Windows. The quattro manual/50-dual-boot-install.md still tells users to run limine-scan. /usr/share/doc/limine/CONFIG.md from limine 12.8.0-1 says paths are case sensitive except that on FAT a name fitting the 8.3 short form matches case insensitively, so the rewritten cause about MICROSOFT being nine characters holds. /usr/share/omarchy/bin/omarchy-refresh-limine moves /boot/limine.conf aside and copies the default template, which supports the closing note. A hand edit of /boot/limine.conf is not undone by config checksum enrollment on a default install, because ENABLE_ENROLL_LIMINE_CONFIG is commented out (default no) in /etc/limine-entry-tool.conf and set nowhere in the drop-ins or /etc/default/limine here. Not exercised: no Windows ESP here.
>
> *The Cause above was rewritten on 2026-10-04 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Find the real on-disk casing and correct the `path:` line.

```sh
# Windows on the same ESP as Omarchy
sudo find /boot/EFI -iname 'bootmgfw.efi'

# Windows on its own ESP on another disk: mount it read-only and look
lsblk -o NAME,PARTUUID,FSTYPE,SIZE
sudo mount -o ro /dev/nvme1n1p1 /mnt      # the other disk's vfat ESP
find /mnt/EFI -iname 'bootmgfw.efi'
sudo umount /mnt
```

Edit the entry in `/boot/limine.conf` so the path matches exactly, keeping the `guid(...)` prefix the scanner wrote:

```
/Windows Boot Manager
    protocol: efi
    path: guid(<esp-partuuid>):/EFI/Microsoft/Boot/bootmgfw.efi
```

A Windows entry hand-added to `/boot/limine.conf` is discarded whenever `omarchy-refresh-limine` runs. See `omarchy-limine-windows-entry-wiped` for keeping it across updates.

**Verify.** `sudo grep -n -A3 '^/Windows' /boot/limine.conf` shows the corrected path, and selecting the entry in Limine starts the Windows boot manager.

Sources: <https://github.com/omacom/omarchy/issues/7906> · <https://github.com/omacom/omarchy/blob/quattro/manual/50-dual-boot-install.md>

---

## Direct boot keeps booting the old linux UKI after the linux-omarchy migration

`omarchy-direct-boot-stuck-on-stock-kernel-uki` · severity: **medium** · frequency: **occasional** · applies to: `limine`, `linux-omarchy`, `omarchy`, `uefi`, `uki`

**Symptom.** "I set up direct boot with `omarchy-setup-direct-boot` and the update says it installed the Omarchy kernel, but `uname -r` still shows `7.2.x-arch...` weeks later. A reboot-required notice keeps coming back." `efibootmgr` shows the firmware starting the old file:

```
BootCurrent: 0000
Boot0000* Omarchy  HD(1,GPT,...)/\EFI\LINUX\OMARCHY_LINUX.EFI
```

**Cause.** Before the migration there was one UKI, `/boot/EFI/Linux/omarchy_linux.efi`, rewritten on every kernel update, so a firmware entry pointing at it always booted the current kernel. The UKI name now follows the kernel package (`CUSTOM_UKI_NAME="omarchy"`), so `linux-omarchy` writes a second file, `omarchy_linux-omarchy.efi`. Migration `1789325478.sh` only rewrites `BOOT_ORDER` in `/etc/default/limine`, which steers Limine. A direct-boot entry skips Limine entirely, so it keeps starting `omarchy_linux.efi`, the stock `linux` kernel. `omarchy-setup-direct-boot` also chooses its UKI with `find /boot/EFI/Linux/ -name "omarchy*.efi" ... | head -1`, so with two files a newly created entry points at whichever `find` lists first.

> **Audit corrected this record.** The cause matches #12145 and its second confirmation, and it matches /usr/share/omarchy/bin/omarchy-setup-direct-boot on this machine, which picks the UKI with `find ... -name "omarchy*.efi" ... | head -1`. CUSTOM_UKI_NAME="omarchy" is in /etc/limine-entry-tool.d/omarchy-defaults.conf. The fix has a dangerous defect. If the sed finds no Omarchy entry, $num is empty, and `efibootmgr --bootnum "" --delete-bootnum` deletes Boot0000. I read rhboot/efibootmgr src/efibootmgr.c: strtoul on an empty string returns 0, and endptr points at the terminating NUL, so the value passes validation as bootnum 0. On many machines Boot0000 is Windows Boot Manager or Limine. The corrected fix stops when no entry is found. It also applies the same AMI and Apple firmware refusals that the Omarchy script enforces. Nothing was run here, and no NVRAM was touched. Second audit confirmed the corrected text: Second audit of the corrected text. #12145 is open and a second reporter confirmed it on Intel Lunar Lake on 2026-09-30. /usr/share/libalpm/scripts/limine-mkinitcpio-install names the UKI ${UKI_PREFIX}_${KERNEL_NAME}.efi with UKI_PREFIX taken from CUSTOM_UKI_NAME, and /etc/limine-entry-tool.d/omarchy-defaults.conf sets CUSTOM_UKI_NAME="omarchy", so linux-omarchy writes omarchy_linux-omarchy.efi. omarchy-setup-direct-boot on quattro is identical to the installed 4.0.4-1 copy and still picks the UKI with find ... | head -1 and refuses AMI and Apple firmware. I ran the fix's entry-matching sed against sample efibootmgr lines: it returns the bootnum and returns nothing when there is no Omarchy entry, so the empty-number guard works. The disk and partition parsing gives /dev/nvme0n1 1, /dev/sda 1 and /dev/mmcblk0 1. ENABLE_LIMINE_FALLBACK=yes is set, so the danger's fallback claim holds. #12664 is removed from sources: it reports a different problem, default_entry: 2 in the Limine template, and supports nothing this record says. Its claim also conflicts with #12087 and #13030, where linux-omarchy did become the default after the migration, so it was not used to change the 'go back through Limine' branch. Not exercised: no NVRAM was touched.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Deleting the only working firmware boot entry, then failing to create the new one, leaves the firmware to fall back to `\EFI\BOOT\BOOTX64.EFI`. Omarchy installs Limine there (`ENABLE_LIMINE_FALLBACK=yes`), so the machine still boots through Limine, but check `sudo ls /boot/EFI/BOOT/` first.

**Fix.**

Recreate the firmware entry so it points at the `linux-omarchy` UKI by name. Do not simply re-run `omarchy-setup-direct-boot`, because with two UKIs present it can pick the wrong file again. The Omarchy script refuses to create entries on American Megatrends and Apple firmware. Respect that: on those machines, delete the entry and go back through Limine instead.

```sh
# 1. confirm both UKIs exist
sudo ls /boot/EFI/Linux/

# 2. find the existing Omarchy direct-boot entry. Stop if there is none:
#    an empty number makes efibootmgr act on Boot0000
num=$(efibootmgr | sed -n 's/^Boot\([0-9A-Fa-f]\{4\}\)\*\? Omarchy\([[:space:]].*\)\?$/\1/p' | head -1)
if [ -z "$num" ]; then echo "no Omarchy direct-boot entry found, nothing to delete"; else
  efibootmgr | grep "^Boot$num"          # check this is the entry you mean
  sudo efibootmgr --bootnum "$num" --delete-bootnum
fi

# 3. recreate it on the ESP's disk and partition, pointing at the new UKI
src=$(findmnt -n -o SOURCE /boot)              # e.g. /dev/nvme0n1p1
disk=$(echo "$src" | sed 's/p\?[0-9]*$//')
part=$(echo "$src" | grep -o '[0-9]*$')
echo "$disk $part"                             # must print a disk and a number
sudo efibootmgr --create --disk "$disk" --part "$part" --label "Omarchy" \
  --loader '\EFI\Linux\omarchy_linux-omarchy.efi'
```

`efibootmgr --create` puts the new entry first in `BootOrder`. To go back through Limine instead, which follows `BOOT_ORDER` and still offers the stock `linux` kernel if `linux-omarchy` fails to boot, do step 2 and stop there.

**Verify.** `efibootmgr -v` shows `Omarchy` pointing at `\EFI\Linux\omarchy_linux-omarchy.efi` and first in `BootOrder`. After a reboot `uname -r` ends in `-omarchy`.

Sources: <https://github.com/omacom/omarchy/issues/12145> · <https://github.com/rhboot/efibootmgr/blob/main/src/efibootmgr.c> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-setup-direct-boot> · <https://github.com/omacom/omarchy/blob/quattro/default/limine/limine.conf> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md>

---

## Out-of-tree and DKMS modules on linux-omarchy: build against linux-omarchy-headers, not kernel.org or Arch sources

`out-of-tree-module-on-linux-omarchy-wrong-source-or-headers` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `apple`, `dkms`, `limine`, `nvidia`, `omarchy`

**Symptom.** One of these after moving to the `linux-omarchy` kernel:

- A module you compiled yourself (a patched `amdgpu`, a Wi-Fi or touchpad driver) loads, its version string matches, and the machine hangs early in boot or black-screens before the LUKS prompt. The same module rebuilt for stock `linux` worked.
- DKMS refuses to build:

```
Error! Your kernel headers for kernel 7.2.5-3-omarchy cannot be found at /usr/lib/modules/7.2.5-3-omarchy/build or /usr/lib/modules/7.2.5-3-omarchy/source.
```

- The DKMS build compiles every object, then fails at the BTF step:

```
libbpf: failed to get e_shstrndx from /usr/lib/modules/7.2.5-3-omarchy/build/vmlinux
Failed to parse base BTF '/usr/lib/modules/7.2.5-3-omarchy/build/vmlinux': -4001
make[5]: *** [.../Makefile.modfinal:52: nvidia.ko] Error 255
```

**Cause.** `linux-omarchy` is its own kernel build. It carries patches the stock Arch kernel does not (issue 12281 traces a speaker regression to `pkgbuilds/linux-omarchy/0512-sound-fixes.patch`) and a different `.config`. On this workstation `linux-omarchy 7.2.5-3` has `CONFIG_INTEL_IOMMU_DEFAULT_ON=y` and `CONFIG_ARCH_MMAP_RND_BITS=32` where `linux 7.2.3-arch1-3` has the option unset and 28. A module built from plain kernel.org 7.2.5 sources can carry a matching version string, so `modprobe` accepts it, while its view of kernel structures differs from the running kernel. The issue 12119 reporter found exactly that on an iMac18,3 and withdrew an earlier IOMMU diagnosis once they tested the two causes apart.

DKMS builds against `/usr/lib/modules/<version>/build`, which only exists when the matching `linux-omarchy-headers` is installed. Migration `1789325478.sh` installs the headers, and migration `1789444024.sh` adds them on installs where an earlier path skipped them, but that second migration is blocked if the first one failed.

The BTF failure (issue 12856) means the `vmlinux` under `build/` is truncated on that machine. `vmlinux` belongs to `linux-omarchy-headers`, not `linux-omarchy`, and the Omarchy kernel maintainer could not reproduce it. On this workstation the same `7.2.5-3` file has intact `.BTF` and `.BTF_ids` sections, so a locally damaged headers file is the likely cause (not confirmed).

> **Audit corrected this record.** Confirmed on this machine: linux-omarchy 7.2.5-3 build/.config has CONFIG_INTEL_IOMMU_DEFAULT_ON=y and CONFIG_ARCH_MMAP_RND_BITS=32, linux 7.2.3-arch1-3 has it unset and 28. build/vmlinux is owned by linux-omarchy-headers 7.2.5-3 and readelf shows intact .BTF and .BTF_ids, the cached headers package is present under the exact filename the fix uses, and /usr/bin/dkms line 1287 prints the quoted header error with an 'Error!' prefix. Issue 12119 holds the iMac18,3 retraction exactly as described (ahmadtv, 2026-09-23). Issue 12856 has the BTF error text and the maintainer's 'cannot reproduce', and that reporter ran pacman -Qkk against linux-omarchy rather than the headers package, which supports the record's 'locally damaged headers file' reading. Issue 12281's comment names 0512-sound-fixes.patch. 1789444024.sh exists on quattro and matches the cause. One defect: step 2 built a hand-made module against $(uname -r), but a reader whose module hangs linux-omarchy is debugging from the stock linux kernel, so that builds for the wrong kernel again. The fix and verify now name the target kernel explicitly. Not exercised: no module was built.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Forcing a mismatched module in with `modprobe --force-vermagic` can crash the kernel or corrupt data. Do not use it to get past a version mismatch. Keep the stock `linux` entry available until a hand-built module is proven on `linux-omarchy`.

**Fix.**

**1. Headers must match the kernel exactly.**

```bash
pacman -Q linux-omarchy linux-omarchy-headers     # same version on both lines
ls -l /usr/lib/modules/7.2.5-3-omarchy/build      # must exist
```

Use the version `ls /usr/lib/modules/` shows for the `-omarchy` kernel. If headers are missing, install them, then let DKMS build for that kernel:

```bash
sudo pacman -S --needed linux-omarchy-headers
pacman -Q linux-omarchy linux-omarchy-headers     # versions must still match
sudo dkms autoinstall -k 7.2.5-3-omarchy
dkms status
```

If the versions differ, the sync database is newer than the installed kernel. Run `omarchy update` to bring both to the same version instead.

**2. Hand-built modules: build against the Omarchy kernel's own tree**, never against a kernel.org or Arch source checkout. Name the kernel explicitly, because you may be booted into stock `linux` while debugging, and `$(uname -r)` would then target the wrong kernel:

```bash
make -C /usr/lib/modules/7.2.5-3-omarchy/build M="$PWD" modules
```

If a driver project only offers "build against kernel X.Y sources", use its DKMS package instead, so it rebuilds against `linux-omarchy-headers` on every kernel update.

**3. BTF error: check the headers package, then reinstall it from the cache** (installing from the sync database could pull headers newer than the installed kernel):

```bash
readelf -S /usr/lib/modules/7.2.5-3-omarchy/build/vmlinux | grep BTF
pacman -Qkk linux-omarchy-headers
sudo pacman -U /var/cache/pacman/pkg/linux-omarchy-headers-7.2.5-3-x86_64.pkg.tar.zst
sudo dkms autoinstall -k 7.2.5-3-omarchy
```

Use the version `pacman -Q linux-omarchy` reports. A healthy `vmlinux` lists `.BTF` and `.BTF_ids` and `readelf` prints no `Error:` line.

**4. Rebuild the UKI** if the module is in the initramfs (NVIDIA early KMS, for example):

```bash
sudo limine-mkinitcpio linux-omarchy
```

**Verify.** `dkms status` shows `installed` for the `-omarchy` kernel. `modinfo -k 7.2.5-3-omarchy -F vermagic <module>` begins with `7.2.5-3-omarchy` (use your `-omarchy` version). The machine boots `linux-omarchy` with the module loaded (`uname -r` ends in `-omarchy` and `lsmod | grep <module>` lists it).

Sources: <https://github.com/omacom/omarchy/issues/12119> · <https://github.com/omacom/omarchy/issues/12856> · <https://github.com/omacom/omarchy/issues/12281> · <https://github.com/omacom/omarchy/blob/quattro/migrations/1789444024.sh> · <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://wiki.archlinux.org/title/Kernel_module>

---

## Limine snapshot entries start the stock kernel, and rolling back past 4.0.4 removes linux-omarchy for good

`snapshot-entries-boot-stock-kernel-rollback-drops-linux-omarchy` · severity: **medium** · frequency: **occasional** · applies to: `btrfs`, `limine`, `omarchy`, `snapper`

**Symptom.** After the kernel migration you open the Limine Snapshots submenu to roll back, and the snapshot entries only offer `linux`, not `linux-omarchy`. Or you restored a snapshot from before the 4.0.4 update, ran `omarchy update` afterwards, and `linux-omarchy` never came back: `pacman -Q linux-omarchy` says it is not installed and the menu shows only the stock kernel.

**Cause.** `limine-snapper-sync` adds each snapshot entry "with its matching kernel versions", meaning the kernels installed inside that snapshot's root, with their files kept under `/boot/<machine-id>/limine_history/`. `omarchy update` takes its snapshot (`omarchy-snapshot create`) before `omarchy-update-system-pkgs` installs anything, so the snapshot made by the very update that ran migration 1789325478 does not contain `linux-omarchy`, and neither does any older one. Every snapshot from before the migration boots a stock kernel. Only snapshots taken by later updates contain both kernels.

Restoring a pre-migration snapshot rolls back `@`, which holds the package database, `/etc/default/limine` and the machine-wide marker `/var/lib/omarchy/migrations/1789325478`. It does not roll back `@home`, which holds the per-user marker `~/.local/state/omarchy/migrations/1789325478.sh`. `omarchy-migrate` decides by the per-user marker, so it never reruns the migration, and the `omarchy` package does not depend on `linux-omarchy`, so no update reinstalls it. This follows from reading `omarchy-migrate`, `omarchy-update` and the migration on 4.0.4. A real restore was not exercised.

> **Audit corrected this record.** Read /usr/share/omarchy/bin/omarchy-update on 4.0.4-1. It runs `omarchy-snapshot create` before `omarchy-update-system-pkgs` and then `omarchy-migrate`, so the snapshot taken by the update that runs migration 1789325478 has no linux-omarchy. omarchy-migrate keys solely on $HOME/.local/state/omarchy/migrations/<name>.sh. The migration's own early exit keys on /var/lib/omarchy/migrations/1789325478, which is on @ and so goes back with a restore. `pacman -Qi omarchy` shows no dependency on linux-omarchy, and omarchy-update-system-pkgs only runs `pacman -Syu`, so nothing reinstalls it. Both per-user marker names (1789325478.sh, 1789444024.sh) exist with that spelling here, and 1789444024 only installs headers, so clearing its marker is harmless. limine-entry-tool --tree accepts a depth argument per --help. The README quote 'with its matching kernel versions' is verbatim. One defect: the cause asserts a workstation-specific observation (three snapshot entries at 12:50 against a 12:55 marker). That is not something a reader can check, it is stale since this machine has updated since, and I could not re-check it without root. It is removed from the cause. The marker times 2026-09-18 12:55 do match. The Arch wiki Limine page is general and kept. Not exercised: no snapshot was restored, and the marker-clearing recovery was not run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Delete only the two marker files named. Removing the whole `migrations` directory replays every Omarchy migration since install, some of which rewrite your configuration.

**Fix.**

**See which kernels a snapshot entry carries** before booting it:

```bash
limine-snapper-list
sudo limine-entry-tool --tree 4
```

Entries under a snapshot are named after the kernel packages it contains. A snapshot entry for `linux` boots that snapshot's root with the stock kernel, which is the right pairing for a snapshot taken before the migration.

**After restoring a pre-4.0.4 snapshot, bring the Omarchy kernel back** by clearing your per-user markers for the two kernel migrations and rerunning the update as your user:

```bash
ls ~/.local/state/omarchy/migrations/ | grep -E '1789325478|1789444024'
rm ~/.local/state/omarchy/migrations/1789325478.sh ~/.local/state/omarchy/migrations/1789444024.sh
omarchy update
```

The migration then installs `linux-omarchy` and its headers again, rewrites `BOOT_ORDER` and rebuilds its UKI. If it stops with "The Omarchy kernel has no Limine boot entry", follow that record.

If you restored that snapshot on purpose because `linux-omarchy` broke your hardware, leave the markers alone. You are already on the stock kernel.

**Verify.** `pacman -Q linux-omarchy` shows it installed, `sudo limine-entry-tool --tree` lists it first, and after a reboot `uname -r` ends in `-omarchy`. Snapshots created by the next `omarchy update` list both kernels.

Sources: <https://gitlab.com/Zesko/limine-snapper-sync> · <https://github.com/omacom/omarchy/blob/v4.0.4/migrations/1789325478.sh> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-migrate> · <https://github.com/omacom/omarchy/blob/v4.0.4/bin/omarchy-update> · <https://wiki.archlinux.org/title/Limine>

---

## omarchy update fails with "Boot path '/boot' is not a FAT32 filesystem" on a valid ESP

`omarchy-kernel-migration-boot-not-fat32-autofs` · severity: **medium** · frequency: **rare** · applies to: `limine`, `linux-omarchy`, `omarchy`, `systemd`, `uefi`

**Symptom.** `omarchy update` stops in the kernel migration:

```
Running migration (1789325478)
Install the Omarchy kernel and make it the first Limine boot entry
ERROR: Boot path '/boot' is not a FAT32 filesystem.
```

The ESP is a normal FAT32 partition and the machine boots fine.

**Cause.** `/boot` is not listed in `/etc/fstab`, so `systemd-gpt-auto-generator` mounts the ESP through a generated automount. Limine's validation in `limine-mkinitcpio-hook` (`check_boot_partition` in `/usr/lib/limine/limine-common-functions`) reads the filesystem type with `findmnt -n -o FSTYPE` and gets `autofs` for the outer automount layer instead of `vfat`, then rejects it. `findmnt /boot` shows both layers:

```
/boot systemd-1   autofs
/boot /dev/...    vfat
```

The Omarchy installer normally writes an explicit `/boot` vfat line to fstab. #12060 does not say how the reporter's install came to lack one.

> **Audit corrected this record.** #12060 supports the symptom, the error text, the two findmnt layers and the explicit fstab entry as the remedy. check_boot_partition() in /usr/lib/limine/limine-common-functions passes mountpoint -q on the automount, then reads the first line of findmnt -n -o FSTYPE and prints exactly "Boot path '$path' is not a FAT32 filesystem." The appended fstab line matches this workstation's installer-written /boot line apart from the UUID. omarchy-migrate touches its per-user marker only after the migration exits 0, and the migration writes /var/lib/omarchy/migrations/1789325478 only after the limine-entry-tool --tree check passes, so a failed run does retry, and the verify step names the right machine marker. The earlier audit's guard against an idle automount and an empty UUID is kept. One claim in the cause is unsupported: 'for example a system set up by other means and then converted to Omarchy'. #12060's reproduction says only that the ESP was not written to fstab and gives no account of how. The cause is rewritten without the invented example. Not exercised: no fstab edited, no autofs layout reproduced.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A wrong UUID or a typo in `/etc/fstab` for `/boot` can drop the next boot to emergency mode (see `fstab-bad-entry-emergency-mode`). Run `sudo findmnt --verify` before rebooting.

**Fix.**

Give `/boot` an explicit fstab entry so systemd generates a normal `boot.mount`, then let the migration retry.

```sh
# 1. trigger the automount, then confirm both layers
sudo ls /boot >/dev/null
findmnt /boot

# 2. find the ESP's UUID from the vfat layer, and stop if it is empty
esp_dev=$(findmnt -n -o SOURCE,FSTYPE /boot | awk '$2=="vfat"{print $1}' | head -1)
esp_uuid=$(lsblk -no UUID "$esp_dev")
echo "$esp_dev $esp_uuid"
[ -n "$esp_uuid" ] || { echo "no vfat UUID found, do not edit fstab"; false; }

# 3. append the same line Omarchy's installer writes (only after step 2 printed a UUID)
sudo cp /etc/fstab /etc/fstab.bak
echo "UUID=$esp_uuid  /boot  vfat  rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro  0 2" \
  | sudo tee -a /etc/fstab

# 4. check fstab parses before rebooting
sudo findmnt --verify
```

Reboot, then confirm, and rerun the pending migration. The migration writes its completion marker only after it succeeds, so it runs again:

```sh
findmnt -n -o FSTYPE /boot      # must print vfat, a single line
omarchy-migrate                 # no sudo, it calls sudo itself
```

If `findmnt --verify` complains, restore the backup with `sudo cp /etc/fstab.bak /etc/fstab` before rebooting.

**Verify.** `findmnt /boot` prints one line with FSTYPE `vfat`. `omarchy-migrate` completes, `sudo test -e /var/lib/omarchy/migrations/1789325478 && echo done` prints `done`, and `pacman -Q linux-omarchy` succeeds.

Sources: <https://github.com/omacom/omarchy/issues/12060> · <https://github.com/omacom/omarchy/blob/v4.0.4/migrations/1789325478.sh> · <https://wiki.archlinux.org/title/EFI_system_partition>

---

## 'ACPI BIOS Error (bug): Could not resolve symbol ... AE_NOT_FOUND' at boot

`acpi-bios-error-could-not-resolve-symbol-harmless` · severity: **low** · frequency: **very-common** · applies to: `acpi`, `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Red lines on the console or in `journalctl -k` at every boot, often on a new laptop:

```
ACPI BIOS Error (bug): Could not resolve symbol [^^^^NPCF.ACBT], AE_NOT_FOUND (20240827/psargs-332)
ACPI Error: Aborting method \_SB.PCI0.SBRG.EC0._Q83 due to previous error (AE_NOT_FOUND) (20240827/psparse-529)
```

Users often assume these are why boot is slow or failing.

**Cause.** The firmware's ACPI tables (DSDT/SSDT) reference objects that do not exist, usually because the vendor tested only against Windows. The kernel's ACPI interpreter reports each failed lookup and aborts that one method. The rest of the system carries on. Arch forum replies treat these as firmware bugs with usually little impact. One reporter saw an extra 3 to 4 seconds of boot time, and no thread ties them to a failed boot. If boot actually fails, the cause is elsewhere.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A failed or interrupted BIOS update can brick the board. Use AC power and the vendor's procedure.

**Fix.**

Treat these lines as noise unless a specific feature tied to the named method is broken, such as battery status for `_BST`/`_BIF` or fan control for EC `_Qxx` methods. Then:

1. Update the firmware. Omarchy: `omarchy-update-firmware` (no sudo). Elsewhere: `fwupdmgr refresh && fwupdmgr update`, or the vendor's BIOS tool.
2. In firmware setup, disable CSM and pick any "Linux" or "Other OS" option.

To keep them off the console, Arch: use `quiet loglevel=3`, which hides kernel messages at error level and below from the console only, in that order on the kernel command line. Omarchy 4 already boots with `quiet splash loglevel=0`, so these lines appear only in the journal.

To look for the real cause of a boot problem, read the errors around it rather than the ACPI noise:

```sh
journalctl -b -p err
systemd-analyze critical-chain
```

**Verify.** With `quiet loglevel=3` the ACPI lines no longer appear on the console, though `journalctl -k -p err -b` still lists them. Boot time and device function are unchanged.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=305498> · <https://wiki.archlinux.org/title/Silent_boot>

---

## bootctl warns 'random seed file is world accessible, which is a security hole'

`bootctl-random-seed-world-accessible` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `manjaro`, `systemd-boot`, `uefi`

**Symptom.** Running `bootctl install` or `bootctl update`, or watching the systemd-boot update service, prints:

```
Mount point '/boot' which backs the random seed file is world accessible, which is a security hole!
Random seed file '/boot/loader/random-seed' is world accessible, which is a security hole!
```

(or `/efi` in place of `/boot`). The system boots fine.

**Cause.** The ESP is a FAT filesystem with no Unix permissions. Ownership and modes come from the `fmask` and `dmask` mount options, and fstab lines written by genfstab or older installers often carry `fmask=0022,dmask=0022`, which makes every file readable by all users. systemd-boot keeps a random seed on the ESP for early-boot entropy. When bootctl writes or refreshes that seed and finds it, or the mount point backing it, readable by other users, it prints the warning and carries on. The seed is still written and the system still boots. Any local user could read it until the masks are tightened.

> **Audit corrected this record.** bbs 287695 has both warning lines (with /efi), notes that the system boots, and fixes it by changing fstab from 0022 to fmask=0077,dmask=0077. The strings in systemd 261.2's bootctl and libsystemd-shared match both messages. bootctl(8) says random-seed generates or refreshes the seed on the ESP for systemd-boot. On this machine /proc/mounts shows /boot as vfat with fmask=0077,dmask=0077, and grub and systemd-boot are not in use, which confirms the Omarchy note. Two defects. First, the cause says bootctl 'refuses to treat' a readable seed as secret. bootctl prints a warning and carries on, as the reporter's working install shows. Second, the cited EFI system partition wiki page says nothing about the random seed or the warning. Its only fmask/dmask lines are for a bind-mount setup. It is replaced by the Fstab page, whose ESP examples use fmask=0177,dmask=0077, and the FAT page, which states FAT has no Linux permissions. Not exercised: /boot was not remounted and bootctl was not run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A typo in the `/boot` fstab line can drop the next boot to emergency mode. Run `sudo findmnt --verify` before rebooting.

**Fix.**

Tighten the ESP mount options in `/etc/fstab`. Change `fmask=0022,dmask=0022` to:

```
UUID=XXXX-XXXX  /boot  vfat  rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro  0 2
```

Keep your own UUID and mount point. Then remount and regenerate the seed:

```sh
sudo systemctl daemon-reload
sudo umount /boot && sudo mount /boot
sudo bootctl random-seed
```

Omarchy 4 already mounts its ESP with `fmask=0077,dmask=0077`, and uses Limine rather than systemd-boot, so it does not see this warning.

**Verify.** `findmnt -n -o OPTIONS /boot` shows `fmask=0077,dmask=0077`, and `sudo bootctl random-seed` completes with no 'world accessible' warning.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=287695> · <https://wiki.archlinux.org/title/Fstab> · <https://wiki.archlinux.org/title/FAT>

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

**Cause.** mkinitcpio walks the modules it is about to include and notes any firmware file those modules *could* request that is not present in `/usr/lib/firmware`. `aic94xx`, `wd719x`, `bfa`, `qed` and `qat_4xxx` are enterprise SAS/SCSI/FC/QuickAssist drivers whose firmware is not redistributable and therefore not in `linux-firmware`. Unless you own that hardware, nothing is missing at runtime: the module simply never loads.

> **Audit corrected this record.** The 'do nothing' advice is right, but two of the three concrete commands are wrong. (1) `MODULES=(!aic94xx ...)` is not valid mkinitcpio syntax. I read `add_module()` in the mkinitcpio source: it handles a trailing `?` (ignore-errors) and nothing else. A leading `!` is not parsed, so the build will fail with 'module not found: !aic94xx'. (2) `qat_4xxx-firmware` does not exist: the AUR RPC returns resultcount 0 for it and for `qat-firmware`, so `yay -S qat_4xxx-firmware` is a fabricated package. (3) The `xhci_pci` warning is not an irreducible false positive: it is the Renesas uPD720201/202 firmware request, silenced by the AUR package `upd72020x-fw`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The correct action is **do nothing**. These are build-time notices about firmware a module *could* request, not a runtime failure. The system boots fine.

If you actually own the hardware (or just want a clean log), the real packages are:

```sh
yay -S aic94xx-firmware wd719x-firmware   # Adaptec SAS / WD719x SCSI
yay -S upd72020x-fw                        # silences the xhci_pci warning (Renesas uPD720201/202)
sudo mkinitcpio -P
```

There is no AUR package for `qat_4xxx`, `qed` or `bfa` firmware, so those warnings cannot be cleared and are harmless.

Do **not** try to exclude modules with `MODULES=(!aic94xx)`. mkinitcpio has no `!` exclusion syntax (only a trailing `?` to make a module optional), and the invalid entry makes the build fail. These warnings mostly come from the *fallback* image, which is built without `autodetect` and therefore packs every driver by design. Leave it that way, it is your recovery image.

**Verify.** `sudo mkinitcpio -P` completes. The last line is `==> Image generation successful` (warnings above it are irrelevant).

Sources: <https://forum.endeavouros.com/t/removing-missing-firmware-warnings-from-mkinitcpio/16510> · <https://forum.endeavouros.com/t/possibly-missing-firmware-for-module-aic94xx/19590> · <https://man.archlinux.org/man/mkinitcpio.conf.5>

---
