# Boot, kernel & initramfs

35 problems. Sorted by severity, then by how often users hit it.

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

**Symptom.** Right after a kernel or system update the normal boot entry drops to an emergency shell or hangs, but selecting the *fallback* entry in the boot menu boots fine. Users report this most often on encrypted Btrfs roots after a kernel bump.

**Cause.** The default initramfs is built with the `autodetect` hook, which strips out every module the running system was not using at build time. If mkinitcpio ran in a degraded environment (chroot without the real hardware, a full /boot, an interrupted upgrade), the resulting default image is missing the modules needed for your root device. The fallback image has no `autodetect`, so it still contains everything.

> ⚠️ **Risk.** Do not delete the fallback image to save space until the default image is confirmed working — the fallback is often the only thing standing between you and a live-USB rescue.

**Fix.**

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

On Omarchy (Limine + UKI) rebuild through the distro wrapper so the unified kernel images on the ESP are refreshed too:

```sh
sudo limine-mkinitcpio
```

If the rebuild itself errors, fix the underlying cause first (usually a full /boot — see that record — or a hook referencing a module that no longer exists).

**Verify.** `ls -l /boot/initramfs-linux.img /boot/initramfs-linux-fallback.img` shows both files with a current timestamp and a plausible size (tens to hundreds of MB), and the *default* entry boots.

Sources: <https://forum.endeavouros.com/t/solved-boots-into-emergency-shell-after-update-encrypted-root-is-not-mounted/38101> · <https://man.archlinux.org/man/mkinitcpio.8> · <https://github.com/basecamp/omarchy/issues/8319>

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
==> Creating unified kernel image: '/tmp/staging_uki.efi'
==> Unified kernel image generation successful
ERROR: mkinitcpio failed for kernel 7.0.3-arch1-2, skipping.
```

pacman still exits 0 and `omarchy update` reports success. Sometimes `nvidia-smi` on a TTY prints `NVRM: API mismatch: this kernel module has version 595.58.03 but this NVIDIA driver component has version 595.71.05`.

**Cause.** nvidia-open-dkms / nvidia-dkms failed to compile against the newly installed kernel — usually because the matching `linux-headers` package is not installed, the kernel and module were built with different GCC major versions (a stray `/opt/cuda/bin` in PATH is a classic cause), or the driver simply does not support that kernel yet. Omarchy's `install/hardware/nvidia.sh` puts `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` in `/etc/mkinitcpio.conf.d/nvidia.conf` for early KMS, and `omarchy_hooks.conf` drops the `kms` hook on NVIDIA-only machines, so when those four modules do not exist mkinitcpio cannot build a usable image and `limine-mkinitcpio-install` refuses to install the UKI. Nothing gets rebuilt, `/boot/EFI/Linux/omarchy_linux.efi` still holds the OLD kernel module, but userspace `nvidia-utils` on disk is new — the kernel/userspace version pair no longer matches, Hyprland aborts in `CHyprOpenGLImpl::initEGL`, and SDDM loops.

> ⚠️ **Risk.** Do not reboot while the transcript says `mkinitcpio failed for kernel ..., skipping.` — the boot image on the ESP is stale and may be the last working one. Never fix this with `pacman -Sy nvidia-utils`: that is a partial upgrade and will make the mismatch worse. `modprobe -r nvidia*` kills anything using the GPU, so save work first.

**Fix.**

Get a text console with Ctrl+Alt+F2 and log in.

If you are stuck in the SDDM login loop (kernel module and userspace disagree), unstick the running session first:

```bash
sudo systemctl stop sddm
sudo modprobe -r nvidia_drm nvidia_uvm nvidia_modeset nvidia
sudo modprobe nvidia_drm
sudo systemctl start sddm
```

Now find out what actually failed:

```bash
uname -r
ls /usr/lib/modules/
dkms status
pacman -Q linux linux-lts linux-headers nvidia-open-dkms nvidia-utils 2>/dev/null
sudo tail -40 /var/lib/dkms/*/*/build/make.log
```

Install the headers that match every installed kernel and rebuild the modules:

```bash
sudo pacman -S --needed linux-headers        # add linux-lts-headers / linux-zen-headers as applicable
env -u PATH PATH=/usr/bin:/usr/sbin sudo dkms autoinstall -k 7.0.3-arch1-2
dkms status                                   # every kernel should now show "installed"
```

Confirm the modules really exist before you rebuild the boot image:

```bash
ls /usr/lib/modules/7.0.3-arch1-2/updates/dkms/nvidia*.ko*
```

Rebuild the initramfs. On Omarchy 4 (Limine + UKI) you must use the Limine wrapper, not bare mkinitcpio, or the UKI on the ESP is never replaced:

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

If you are already at a black screen and cannot reach a TTY, pick a pre-update snapshot from the Limine menu, or add `nomodeset` at the boot menu to reach a console, then follow the steps above.

**Verify.** `dkms status` shows `installed` for every kernel in /usr/lib/modules; `sudo limine-mkinitcpio` completes with no `module not found` lines; after reboot `cat /sys/module/nvidia_drm/parameters/modeset` prints Y and `modinfo -F version nvidia` matches `pacman -Q nvidia-utils`.

Sources: <https://github.com/basecamp/omarchy/issues/5706> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/nvidia.sh> · <https://github.com/basecamp/omarchy/blob/quattro/etc/mkinitcpio.conf.d/omarchy_hooks.conf> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio> · <https://bbs.archlinux.org/viewtopic.php?id=295952> · <https://wiki.archlinux.org/title/Limine>

---

## Boot hangs on the splash screen and the LUKS passphrase prompt never appears

`plymouth-swallows-luks-passphrase-prompt` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `limine`, `luks`, `manjaro`, `omarchy`, `plymouth`

**Symptom.** The machine reaches the Omarchy/Arch boot splash (or a black screen with a spinner) and stops there forever. No `Enter passphrase for /dev/nvme0n1p2:` prompt, no cursor. Typing the passphrase blind and pressing Enter sometimes works, which is the giveaway. Pressing Esc shows nothing useful. Variants after editing the initramfs config:

```
==> ERROR: Hook 'plymouth-encrypt' cannot be found
==> ERROR: Hook 'plymouth' cannot be found
```

On a docked laptop the prompt may be drawn on an external monitor that is still asleep.

**Cause.** Plymouth takes over the console early in boot. If the `plymouth` hook runs *after* the `encrypt`/`sd-encrypt` hook, or if `splash` is on the kernel command line while plymouth is not actually in the initramfs, plymouth swallows the password prompt and the boot deadlocks waiting for input it never displays. Two related traps: `plymouth-encrypt` is not a hook on Arch at all (the `plymouth` package ships only `/usr/lib/initcpio/hooks/plymouth`; it is a Manjaro-only deprecated alias for `encrypt`), so guides recommending it make every rebuild fail; and plymouth defaults to SimpleDRM on UEFI, which does not light up secondary monitors, so a docked laptop can show the prompt on a dark screen.

> ⚠️ **Risk.** Editing HOOKS wrongly is how people make a machine unbootable — dropping `encrypt`/`sd-encrypt` means nothing can unlock the root device, and dropping `filesystems` or `block` means it cannot be found. Change one thing, rebuild, read the output, and keep a fallback entry or a bootable snapshot available before you reboot. `plymouth.enable=0` is safe as a one-off boot parameter but leaves you with a plain text prompt; do not make it permanent if you also removed the plymouth hook, or you lose the themed prompt entirely. Never disable the passphrase prompt to "get past" this.

**Fix.**

**Get in first.** At the boot menu, edit the entry and disable plymouth for one boot — Limine: press `e` and edit `cmdline:`; GRUB: press `e`, edit the `linux` line, `Ctrl+X`:

```
plymouth.enable=0 disablehooks=plymouth
```

Remove `quiet` and `splash` from the same line so you can see the prompt. The text `Enter passphrase for ...:` should now appear.

**Fix the hook order.** `plymouth` must come after `udev` (or `systemd`) and *before* `encrypt`/`sd-encrypt`. This is Omarchy 4's shipped order, in the package-owned `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`:

```
HOOKS=(base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs)
```

On plain Arch, edit `/etc/mkinitcpio.conf` to the same shape:

```
HOOKS=(base udev plymouth autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)
```

If you copied `plymouth-encrypt` from another distro's guide, replace it with plain `encrypt` — it does not exist on Arch.

**Rebuild and read the output.** On Omarchy the entries are unified kernel images, so `mkinitcpio -P` alone will not update what actually boots:

```bash
sudo limine-mkinitcpio      # Omarchy 4 / Limine + UKI
# plain Arch:
sudo mkinitcpio -P
```

There must be no `Hook '...' cannot be found`.

**Docked laptop / external monitor** — make plymouth use the real GPU driver instead of the UEFI framebuffer so all outputs come up:

```
plymouth.use-simpledrm=0
```

**Keyboard layout at the prompt.** If the passphrase is rejected rather than absent, the initramfs is using us layout. Omarchy bundles `/etc/vconsole.conf` into the image automatically for Latin layouts; on plain Arch add it yourself:

```
# /etc/mkinitcpio.conf.d/99-local.conf
FILES+=(/etc/vconsole.conf)
```

**Debug what plymouth is doing** by adding `plymouth.debug` to the command line and reading `/var/log/plymouth-debug.log` after you get in.

**Make a parameter permanent on Omarchy** (do not edit the generated `/boot/limine.conf`):

```bash
sudo tee /etc/limine-entry-tool.d/99-local.conf >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" plymouth.use-simpledrm=0"
EOF
sudo limine-mkinitcpio
```

Note that Omarchy already ships `initramfs_async=0` in `/etc/limine-entry-tool.d/omarchy-defaults.conf` to work around a kernel 7.1 race in which plymouthd exits before it can read `/proc/cmdline`, dropping encrypted boots to an unthemed text prompt. If your booted `cat /proc/cmdline` is missing it, your boot image predates that default — `sudo limine-mkinitcpio` regenerates it.

If the splash is merely ugly rather than broken, reset the theme instead of disabling plymouth:

```bash
sudo plymouth-set-default-theme -R omarchy
# Omarchy:
omarchy-refresh-plymouth
```

**Verify.** After rebuilding, `sudo limine-mkinitcpio` (or `mkinitcpio -P`) reports no missing hooks; on the next boot the themed passphrase prompt appears and accepts input; `cat /proc/cmdline` contains the parameters you added.

Sources: <https://wiki.archlinux.org/title/Plymouth> · <https://wiki.archlinux.org/title/Dm-crypt/System_configuration> · <https://github.com/basecamp/omarchy/blob/quattro/etc/mkinitcpio.conf.d/omarchy_hooks.conf> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://archlinux.org/packages/extra/x86_64/plymouth/files/> · <https://gitlab.manjaro.org/packages/extra/plymouth/-/blob/master/PKGBUILD> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio> · <https://wiki.archlinux.org/title/Kernel_parameters>

---

## /boot (the ESP) was not mounted during the upgrade, so the new kernel went to the root filesystem

`boot-esp-not-mounted-during-kernel-upgrade` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`, `uefi`

**Symptom.** `pacman -Syu` (or `omarchy update`) finished with no errors at all, but the next boot fails — the boot loader cannot find the kernel, or the system boots and then everything modular breaks (no Wi-Fi, no GPU, `modprobe: FATAL: Module ... not found in directory /lib/modules/7.0.3-arch1-2`), or you land in an emergency shell. Once you get a shell, `uname -r` reports an older version than `pacman -Q linux`, and `ls /boot` shows either an empty directory or kernels that do not match. There was no warning during the upgrade — current mkinitcpio no longer prints the old "/boot appears to be a separate partition but is not mounted" message.

**Cause.** The EFI system partition was not mounted at `/boot` when the transaction ran, usually because the fstab entry is missing/wrong, because the mount silently failed earlier in the session (`vfat` module not loaded, dirty FAT flagged `errors=remount-ro`), or because the ESP is mounted somewhere else and you relied on systemd automount. pacman happily writes `vmlinuz-linux` and `initramfs-linux.img` into the plain `/boot` *directory* on the root filesystem, which the firmware cannot read. The modules under `/usr/lib/modules/<newver>` are updated, so the old kernel that the firmware does load has no matching modules.

> ⚠️ **Risk.** Never `rm -rf /boot` while unsure whether the ESP is mounted — with the ESP mounted you delete your only boot loader and kernel. Move it aside instead. On a dual-boot machine the ESP also holds Windows' boot loader, so do not reformat it. If you chroot from a live USB onto btrfs, get `subvol=@` right or you will repair an empty top-level subvolume.

**Fix.**

First confirm the diagnosis:

```bash
findmnt /boot            # no output at all = the ESP is NOT mounted
lsblk -f                 # find the vfat/FAT32 partition
uname -r; pacman -Q linux
ls -l /boot
```

If the system still boots (on the old kernel), repair it in place. Move the stray files off the root filesystem first, otherwise they stay there forever wasting space and confusing you later:

```bash
sudo mv /boot /boot.stray
sudo mkdir /boot
```

Add or fix the fstab entry, then mount:

```bash
sudo blkid -s UUID -o value /dev/nvme0n1p1     # your ESP
```

```
# /etc/fstab
UUID=1234-ABCD  /boot  vfat  rw,relatime,fmask=0137,dmask=0027,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro  0 2
```

```bash
sudo systemctl daemon-reload
sudo mount /boot
findmnt /boot            # must now show the vfat device
```

Reinstall every kernel you have and regenerate the boot image:

```bash
sudo pacman -S linux linux-firmware          # add linux-lts etc. if installed
sudo limine-mkinitcpio                        # Omarchy 4 / Limine UKI
# plain Arch instead:
sudo mkinitcpio -P
```

Then reinstall the boot loader entries:

```bash
sudo limine-update            # Limine
sudo bootctl update           # systemd-boot
sudo grub-mkconfig -o /boot/grub/grub.cfg   # GRUB
```

If it no longer boots at all, do the same from the Arch/Omarchy ISO:

```bash
lsblk -f
# LUKS first if encrypted:
cryptsetup open /dev/nvme0n1p2 root
mount -o subvol=@ /dev/mapper/root /mnt      # drop -o subvol=@ if not btrfs
mount --mkdir /dev/nvme0n1p1 /mnt/boot
arch-chroot /mnt
pacman -S linux linux-firmware
limine-mkinitcpio || mkinitcpio -P
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

Once you are booting off the ESP again, delete `/boot.stray`.

**Verify.** `findmnt /boot` shows the vfat partition, `ls /boot` lists the vmlinuz/initramfs (or /boot/EFI/Linux/omarchy_linux.efi on Omarchy) with today's date, and after a reboot `uname -r` matches `pacman -Q linux`.

Sources: <https://wiki.archlinux.org/title/EFI_system_partition> · <https://bbs.archlinux.org/viewtopic.php?id=194153> · <https://bbs.archlinux.org/viewtopic.php?id=285144> · <https://wiki.archlinux.org/title/Limine> · <https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio>

---

## "UNEXPECTED INCONSISTENCY; RUN fsck MANUALLY" drops the boot into a maintenance shell

`fsck-unexpected-inconsistency-maintenance-shell` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `ext4`, `laptop`, `manjaro`, `omarchy`, `xfs`

**Symptom.** After a hard power-off, a crash, or pulling an external drive, the boot stops with:

```
/dev/nvme0n1p2: UNEXPECTED INCONSISTENCY; RUN fsck MANUALLY.
	(i.e., without -a or -p options)
fsck failed with exit status 4.
[FAILED] Failed to start File System Check on /dev/disk/by-uuid/1a2b3c4d-....
[DEPEND] Dependency failed for /home.
You are in emergency mode. After logging in, type "journalctl -xb" to view
system logs, "systemctl reboot" to reboot, "systemctl default" or "exit"
to boot into default mode.
Give root password for maintenance (or press Control-D to continue):
```

On a machine where root has no password (the Omarchy default) that prompt is a dead end — Ctrl-D just loops.

**Cause.** fsck found damage it will not repair without confirmation (usually a dirty journal plus orphaned inodes on ext4) and exits non-zero. On Arch the check runs either from the mkinitcpio `fsck` hook for the root filesystem, or from `systemd-fsck@.service` for anything with a non-zero pass number in the 6th field of `/etc/fstab`. Either way systemd refuses to continue mounting and falls into emergency mode.

> ⚠️ **Risk.** Running fsck on a mounted read-write filesystem will destroy it — always confirm with `findmnt` / `umount` first, and prefer a live USB for root. `fsck -y` on a physically failing disk can throw away recoverable data; if the drive is suspect, image it first with `ddrescue` and repair the image. Never run e2fsck against btrfs or XFS. `btrfs check --repair` is documented as dangerous and can make a recoverable filesystem unrecoverable — do not reach for it before trying a plain mount and `--readonly`.

**Fix.**

**If the failing filesystem is not root** (a `/home`, `/data`, or `/boot` entry), you can repair it from the maintenance shell:

```bash
findmnt --verify --fstab
umount /dev/sda3          # must NOT be mounted
fsck -f /dev/sda3         # answer y, or use -y to accept everything
systemctl default
```

**If it is the root filesystem**, do not fsck it from that shell — root is mounted. Boot the Arch/Omarchy ISO and work on it unmounted:

```bash
lsblk -f
# open LUKS first if encrypted:
cryptsetup open /dev/nvme0n1p2 root

# ext4:
e2fsck -f /dev/mapper/root          # add -y to auto-answer once you have read the prompts
# xfs:
xfs_repair /dev/mapper/root
# vfat ESP:
fsck.fat -a /dev/nvme0n1p1
# btrfs: DO NOT run fsck. Check only:
btrfs check --readonly /dev/mapper/root
```

For btrfs, a normal mount replays the log and fixes almost everything; if a mount fails, try `mount -o ro,rescue=usebackuproot` before considering repair tools.

**To get in once without repairing** (to take a backup first), add at the boot menu:

```
fsck.mode=skip
```

**To force a full check on the next boot** once you are back in:

```
fsck.mode=force fsck.repair=yes
```

Then make sure fstab is sane — this is a frequent cause of a check that never should have run. The 6th column is the pass number: `1` for root only, `2` for other checkable filesystems, `0` to skip. Anything non-Linux, or any network/removable mount, must be `0`:

```
/dev/nvme0n1p2  /      ext4  defaults                                    0 1
UUID=1234-ABCD  /boot  vfat  rw,relatime,fmask=0137,dmask=0027,utf8      0 2
UUID=...        /data  ntfs3 defaults,nofail,x-systemd.device-timeout=5s 0 0
```

If you use the mkinitcpio `fsck` hook (the Arch and Omarchy default), the kernel command line must contain `rw`, not `ro`, or the check cannot run.

Repeated inconsistencies mean failing hardware, not a software bug:

```bash
sudo smartctl -a /dev/nvme0n1
sudo dmesg | grep -iE 'i/o error|medium error|nvme.*reset'
```

**Verify.** `e2fsck -f` (or `xfs_repair`) exits 0 or 1 on a second run with no further corrections; `systemctl default` completes; after reboot `systemctl list-units --failed` is empty and `journalctl -b -u 'systemd-fsck@*'` shows clean checks.

Sources: <https://wiki.archlinux.org/title/Fsck> · <https://wiki.archlinux.org/title/Kernel_parameters> · <https://wiki.archlinux.org/title/Btrfs> · <https://wiki.archlinux.org/title/Mkinitcpio>

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

> ⚠️ **Risk.** Running pacman/grub-install inside a wrongly-mounted chroot can overwrite files on the wrong filesystem and make a recoverable system unrecoverable. Always confirm `/etc/fstab` is visible inside the chroot before writing anything.

**Fix.**

Boot the Arch (or Omarchy) ISO in **UEFI mode**, then:

```sh
# 1. see the layout
lsblk -f

# 2. unlock encryption if present (Omarchy full-disk encryption is the default)
sudo cryptsetup open /dev/nvme0n1p2 cryptroot

# 3. list the Btrfs subvolumes so you mount the right one
sudo mount /dev/mapper/cryptroot /mnt
sudo btrfs subvolume list /mnt
sudo umount /mnt

# 4. mount the ROOT subvolume (commonly @ or @root)
sudo mount -o subvol=@ /dev/mapper/cryptroot /mnt
sudo mount -o subvol=@home /dev/mapper/cryptroot /mnt/home

# 5. mount the ESP where the installed system expects it (/boot or /boot/efi or /efi)
sudo mount /dev/nvme0n1p1 /mnt/boot

# 6. chroot
sudo arch-chroot /mnt
```

Inside the chroot, check `cat /etc/fstab` — it tells you the exact mount points and subvolume names the installed system uses. If `/mnt/boot` is empty or `/etc/fstab` names `/boot/efi`, unmount and remount accordingly before doing anything else.

For a non-Btrfs (ext4) install, step 4 is simply `sudo mount /dev/nvme0n1p2 /mnt`.

When done:

```sh
exit
sudo umount -R /mnt
sudo cryptsetup close cryptroot
reboot
```

`arch-chroot` is provided by `arch-install-scripts` and handles mounting `/dev`, `/proc`, `/sys` and copying `resolv.conf` for you — do not use plain `chroot` unless you replicate those bind mounts by hand.

**Verify.** Inside the chroot, `ls /etc/fstab /usr/bin/pacman` succeeds and `pacman -Q linux` prints your installed kernel — if either fails you mounted the wrong subvolume. After `pacman -S linux`, `ls -l /boot/vmlinuz-linux` shows a fresh timestamp.

Sources: <https://forum.endeavouros.com/t/boot-initramfs-linux-img-not-found-chroot-on-live-and-update-doesnt-help/50238> · <https://man.archlinux.org/man/arch-chroot.8> · <https://learn.omacom.io/2/the-omarchy-manual/93/security>

---

## A bad /etc/fstab entry drops the system to emergency mode or hangs 90 seconds

`fstab-bad-entry-emergency-mode` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** Boot stalls with:

```
A start job is running for /dev/disk/by-uuid/1a2b-3c4d (1min 30s / no limit)
```

and then:

```
[FAILED] Failed to mount /boot/efi.
[DEPEND] Dependency failed for Local File Systems.
You are in emergency mode. After logging in, type "journalctl -xb" to view
system logs, "systemctl reboot" to reboot ...
Give root password for maintenance (or press Control-D to continue):
```

Usually after swapping a disk, removing an external drive, reformatting the ESP, or turning off a swap partition.

**Cause.** systemd generates a mount unit for every `/etc/fstab` line. If the device never appears, the generated `.device` unit waits (default 90 s) and then the mount fails; because `local-fs.target` *requires* it, the whole boot fails into emergency mode. A reformatted ESP or a re-created swap partition has a new UUID, so the old fstab line can never be satisfied.

> ⚠️ **Risk.** Never add `nofail` to the root filesystem line. Editing fstab with a broken syntax (missing field, wrong pass number) can itself cause emergency mode — always run `sudo mount -a` before rebooting, and `sudo findmnt --verify` to validate the file.

**Fix.**

At the emergency prompt log in as root (or boot a live USB and chroot). Compare fstab against reality:

```sh
lsblk -f
blkid
cat /etc/fstab
```

Fix the UUIDs, or delete lines for devices that no longer exist. Root filesystem must stay mandatory, but make optional mounts non-fatal:

```
# <device>                                <dir>       <type> <options>                          <dump> <pass>
UUID=1a2b-3c4d                            /boot       vfat   defaults,noatime                   0 2
UUID=aaaa-bbbb-cccc                       /           ext4   rw,relatime                        0 1
UUID=dddd-eeee-ffff                       none        swap   defaults                           0 0
# external / removable: never block boot
UUID=1111-2222                            /mnt/data   ext4   defaults,nofail,x-systemd.device-timeout=10s  0 2
```

`nofail` makes the mount *wanted* rather than *required* by `local-fs.target`, and `x-systemd.device-timeout=` caps how long systemd waits for the device instead of the 90-second default.

Apply and test without rebooting blind:

```sh
sudo systemctl daemon-reload
sudo mount -a          # must return with no errors
sudo systemctl reboot
```

If the failing entry is a swap partition you removed, also drop `resume=` from the kernel command line, or early boot will keep waiting for it.

**Verify.** `sudo mount -a` produces no output, `systemctl --failed` is empty after reboot, and `systemd-analyze blame | head` no longer shows a ~90 s device job.

Sources: <https://man.archlinux.org/man/systemd.mount.5> · <https://forum.endeavouros.com/t/emergency-mode-failed-to-mount-boot-efi-vfat-error-tried-base-reinstall-issue-persists/75747> · <https://forum.endeavouros.com/t/a-start-job-is-running-for-dev-disk-uui-running-for-5min/80783> · <https://forum.endeavouros.com/t/whenever-kernel-updates-efi-mount-fails-on-reboot/77575>

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

**Cause.** Four independent things must all be true for snapshot entries to appear: snapper must have a `root` config, `limine-snapper-sync.service` must be running, `/boot/limine.conf` must still contain the `//Snapshots` (or `/Snapshots`) keyword that tells the tool where to write entries, and the ESP must have room. Any of them silently produces an empty snapshot list. A hand-edited or restored `limine.conf`, or a run of `omarchy-refresh-limine`, can drop the keyword. Separately, Omarchy's Setup > Direct Boot adds an EFI entry that jumps past Limine entirely, so the menu is never shown even when the entries exist.

> ⚠️ **Risk.** `omarchy-refresh-limine` overwrites /boot/limine.conf wholesale (old file kept as /boot/limine.conf.bak) — any hand-added entries, notably a Windows entry, are lost and must be re-added. Snapshot restore replaces the root subvolume but not /home and not ~/.config, so a rollback can leave newer config formats in place. Each snapshot entry costs a kernel plus initramfs/UKI on the ESP; raising MAX_SNAPSHOT_ENTRIES on a small ESP can fill /boot and break the next kernel upgrade. Snapshots created before limine-snapper-sync was installed cannot be made bootable.

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

**3. Does limine.conf still have the placeholder?**

```bash
grep -nE '^[[:space:]]*/{1,2}Snapshots' /boot/limine.conf
```

If that prints nothing, restore Omarchy's packaged config (it backs the current one up to `/boot/limine.conf.bak`):

```bash
sudo omarchy-refresh-limine
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
limine-snapper-list
sudo limine-snapper-info      # shows bootable snapshot count and flags missing/corrupt kernels
```

Check the caps in `/etc/default/limine` if fewer snapshots show than exist — entries are trimmed once the ESP crosses `LIMIT_USAGE_PERCENT` (default 85) or the `MAX_SNAPSHOT_ENTRIES` cap (Omarchy ships 6):

```bash
grep -nE 'ESP_PATH|MAX_SNAPSHOT_ENTRIES|LIMIT_USAGE_PERCENT' /etc/default/limine /etc/limine-entry-tool.d/*.conf
df -h /boot
```

If `ESP_PATH` is unset the tool probes `/efi`, `/boot`, `/boot/efi`, `/limine`; Omarchy sets `ESP_PATH="/boot"`.

**Test end to end before you need it:**

```bash
omarchy-snapshot create
limine-snapper-list         # the new snapshot must appear
```

**If the menu never appears at all**, Direct Boot is on. Run Setup > Direct Boot from the Omarchy menu again to remove the EFI entry, or press the firmware's boot-device key at power-on and pick Limine manually.

To restore from a snapshot once you can boot one: click the notification that appears inside the snapshot, or run `omarchy-snapshot restore` / `sudo limine-snapper-restore`.

**Verify.** `limine-snapper-list` shows dated entries, `sudo limine-snapper-info` reports a non-zero bootable snapshot count with kernels verified, and the entries are visible under "Snapshots" in the Limine menu at the next reboot.

Sources: <https://wiki.archlinux.org/title/Limine> · <https://gitlab.com/Zesko/limine-snapper-sync> · <https://github.com/basecamp/omarchy/blob/quattro/install/config/snapper.sh> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-snapshot> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-limine> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://github.com/basecamp/omarchy/blob/quattro/manual/47-system-snapshots.md> · <https://wiki.archlinux.org/title/Snapper>

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

**Cause.** In `linux-firmware 20250613.12fe085f-5` upstream Arch split the monolithic `linux-firmware` package into vendor packages and changed the NVIDIA firmware symlink layout at the same time. pacman cannot reconcile the old directory/symlink with the new package's real files, so the transaction aborts. Anyone who skipped updates across June 2025 hits this on their next `-Syu`.

> ⚠️ **Risk.** Between `pacman -Rdd linux-firmware` and the reinstall your system has NO firmware files in /usr/lib/firmware. Do not reboot, suspend, or let the machine lose power in that window — you would boot without GPU/Wi-Fi firmware and possibly without a usable display.

**Fix.**

Arch's official news item gives the exact two-step remedy:

```sh
sudo pacman -Rdd linux-firmware
sudo pacman -Syu linux-firmware
```

`-Rdd` removes the package without touching dependencies or running scripts, leaving the files temporarily absent; the immediate `-Syu` reinstalls the new split packages over the top. Do **not** reboot between the two commands.

After it completes, rebuild the initramfs so early-KMS firmware is picked up:

```sh
sudo mkinitcpio -P        # Arch / EndeavourOS / CachyOS
sudo limine-mkinitcpio    # Omarchy
```

**Verify.** `pacman -Qs linux-firmware` lists the new vendor packages (e.g. `linux-firmware-nvidia`, `linux-firmware-amdgpu`, `linux-firmware-intel`), and `sudo pacman -Syu` completes with no conflicting-files error.

Sources: <https://archlinux.org/news/linux-firmware-2025061312fe085f-5-upgrade-requires-manual-intervention/> · <https://archlinux.org/news/>

---

## An ignored .pacnew for mkinitcpio.conf or the boot loader config breaks the next boot

`mkinitcpio-pacnew-unhandled-breaks-next-boot` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `luks`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** An upgrade prints, somewhere in a long transcript:

```
warning: /etc/mkinitcpio.conf installed as /etc/mkinitcpio.conf.pacnew
warning: /etc/default/limine installed as /etc/default/limine.pacnew
```

Nothing breaks that day. Weeks later a kernel update rebuilds the initramfs and the machine drops to an emergency shell, or the LUKS prompt never appears, or the root device is not found — because the file that is actually read no longer matches what the current package expects (a renamed hook, a changed default, a new required entry). Users also break it the other way round by running `mv /etc/mkinitcpio.conf.pacnew /etc/mkinitcpio.conf`, which silently deletes their `encrypt`, `plymouth`, or `btrfs-overlayfs` hooks.

**Cause.** pacman never merges configuration. When a package ships a new version of a file you have edited, it writes `.pacnew` alongside and leaves yours untouched. `/etc/mkinitcpio.conf` (from mkinitcpio) and `/etc/default/limine` (from limine-entry-tool) are exactly such files, and they are the ones that decide whether the machine can boot. Because the damage only surfaces at the next initramfs rebuild, the cause and the symptom can be a month apart.

> ⚠️ **Risk.** Overwriting /etc/mkinitcpio.conf (or the Omarchy hooks drop-in) with the .pacnew removes your encryption, plymouth and btrfs hooks and produces an initramfs that cannot open or find the root device — an unbootable machine. Merge, rebuild, and confirm the rebuild succeeded before you reboot. Keep a fallback boot entry, an LTS kernel, or a working snapshot available while you do this. Deleting a .pacsave loses the only copy of a config from a package you removed.

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

**Cause.** Arch moved the `systemd`, `udev`, `encrypt`, `sd-encrypt`, `lvm2` and `mdadm_udev` hooks from distro packages into upstream mkinitcpio, and deprecated the `--microcode` flag and the `microcode` preset option in favour of a new `microcode` **hook** that embeds the CPU microcode into the initramfs itself. Configs written before March 2024 still use the old two-initrd approach.

> ⚠️ **Risk.** Removing the `initrd /*-ucode.img` line from a systemd-boot entry *before* the `microcode` hook is in place and the image rebuilt leaves you booting without microcode updates. Do the HOOKS edit and `mkinitcpio -P` first, then edit the loader entry.

**Fix.**

Update the five packages together (they must move as a set):

```sh
sudo pacman -Syu mkinitcpio systemd lvm2 mdadm cryptsetup
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

If you use **systemd-boot with hand-written entries**, the separate microcode initrd line is now redundant — `/boot/loader/entries/arch.conf` becomes:

```
title   Arch Linux
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=UUID=xxxx-xxxx rw
```

(delete any `initrd /amd-ucode.img` or `initrd /intel-ucode.img` line). GRUB users need do nothing extra beyond `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

Also check `/etc/mkinitcpio.d/*.preset` for a leftover `--microcode` in `default_options`/`fallback_options` and remove it.

**Verify.** `dmesg | grep -i 'microcode'` shows `microcode: Current revision: ...` / `updated early`, and `mkinitcpio -P` runs without deprecation warnings.

Sources: <https://archlinux.org/news/mkinitcpio-hook-migration-and-early-microcode/> · <https://man.archlinux.org/man/mkinitcpio.conf.5> · <https://man.archlinux.org/man/mkinitcpio.8>

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

**Symptom.** You set up hibernation, the machine hibernates fine, but every resume is a cold boot — the swap image is ignored and any unsaved work is gone. On Omarchy this happens on every install with hibernation enabled, regardless of GPU. Inspecting the config shows `resume` at the end of the hook list, after `filesystems`, `fsck` and `btrfs-overlayfs`.

**Cause.** mkinitcpio hooks run in array order, and `resume` must write the swap device to `/sys/power/resume` **before** `filesystems` mounts the real root — otherwise the root FS is already mounted read-write and the kernel refuses to resume. On Omarchy, `omarchy-settings` ships `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` which *assigns* `HOOKS=(...)`, while `omarchy-hibernation-setup` ships `omarchy_resume.conf` which only *appends* `HOOKS+=(resume)`. Drop-ins are read in alphabetical order, so the assignment always runs first and the append can only ever put `resume` last. Tracked as basecamp/omarchy#8471.

> ⚠️ **Risk.** A hand-written HOOKS line that omits `encrypt`/`sd-encrypt`, `block` or `filesystems` produces an initramfs that cannot mount root — an unbootable system. Copy the existing list verbatim and only move `resume` into it; keep the fallback image so you have a way back.

**Fix.**

Add a drop-in that sorts **after** both existing files and re-declares the full array with `resume` in the right place — after the hook that provides the swap device (`encrypt`/`sd-encrypt`/`lvm2`) and before `filesystems`:

```sh
sudo tee /etc/mkinitcpio.conf.d/zz-resume-order.conf >/dev/null <<'EOF'
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt resume filesystems fsck btrfs-overlayfs)
EOF
```

Copy the exact hook list your system currently uses as the starting point — print it first so you do not drop a distro-specific hook:

```sh
grep -h '^HOOKS' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
```

Make sure the kernel command line names the swap device. For Limine, add to the `cmdline:` in `/boot/limine.conf` (or the Omarchy cmdline drop-in):

```
resume=UUID=<swap-uuid>
```
and for a swapfile on Btrfs, also `resume_offset=<offset>` from `sudo btrfs inspect-internal map-swapfile -r /swap/swapfile`.

Rebuild:

```sh
sudo limine-mkinitcpio     # Omarchy
sudo mkinitcpio -P         # plain Arch
```

**Verify.** `lsinitcpio /boot/initramfs-linux.img | grep -n resume` (or inspect the UKI) shows the resume hook, and `sudo systemctl hibernate` followed by power-on returns you to your open windows. `journalctl -b | grep -i 'resume'` shows the resume device being used.

> *Not independently audited — verify before running.*

Sources: <https://github.com/basecamp/omarchy/issues/8471> · <https://github.com/basecamp/omarchy/issues/8352> · <https://man.archlinux.org/man/mkinitcpio.conf.5>

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
