# Omarchy core

35 problems. Sorted by severity, then by how often users hit it.

## Break out of an SDDM login loop after an NVIDIA DKMS update

`nvidia-dkms-login-loop-after-update` · severity: **critical** · frequency: **common** · applies to: `arch`, `desktop`, `hyprland`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** After `omarchy update` and a reboot, SDDM accepts the password and then immediately bounces straight back to the login screen, forever. No error is shown. Switching to a TTY works. Some users see `atomic drm request: failed to commit: invalid argument` or Aquamarine errors when launching Hyprland by hand from the TTY.

**Cause.** The NVIDIA DKMS module failed to compile against the newly installed kernel (often a GCC version bump). mkinitcpio still "succeeded" and regenerated the image/UKI without the NVIDIA modules, while userspace `nvidia-utils` was upgraded. The kernel-module/userspace version mismatch makes Hyprland fail to get a DRM device, so the session dies instantly and SDDM re-prompts.

> **Audit corrected this record.** Symptom, diagnosis and the diagnostic commands are sound; `limine-mkinitcpio` is real (shipped by limine-mkinitcpio-hook, listed in install/omarchy-other.packages) and SDDM is indeed the DM. Two substantive errors. (1) Driver package selection is wrong: install/hardware/nvidia.sh picks `nvidia-open-dkms nvidia-utils lib32-nvidia-utils libva-nvidia-driver` for GSP-capable (Turing+) GPUs and `nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils` for pre-Turing. The record says 'nvidia-dkms for pre-Turing', which is wrong - pre-Turing needs the 580xx legacy branch. (2) `sudo mkinitcpio -P` followed by `sudo limine-mkinitcpio` is redundant: per the comment in bin/omarchy-hibernation-setup, limine-mkinitcpio 'rebuilds initramfs/UKI for all kernels and updates the' boot entries itself. Also `pacman -S nvidia-open-dkms nvidia-utils` without -u is a partial-upgrade pattern, and `linux-lts-headers` is pointless unless linux-lts is installed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Regenerating initramfs/UKI incorrectly can leave the machine unbootable. Keep the LTS kernel entry and at least one snapshot available in the Limine menu before running mkinitcpio.

**Fix.**

Drop to a TTY with `Ctrl + Alt + F2` and confirm the mismatch:

```bash
cat /proc/driver/nvidia/version   # kernel module version
pacman -Q nvidia-utils nvidia-580xx-utils 2>/dev/null   # userspace version
dkms status
```

Rebuild the module and the boot image. On Omarchy, `limine-mkinitcpio` rebuilds the initramfs/UKI for every kernel AND regenerates the Limine entries, so it replaces `mkinitcpio -P` rather than following it:

```bash
sudo dkms autoinstall -k "$(uname -r)"
sudo limine-mkinitcpio
sudo reboot
```

If `dkms autoinstall` fails to build, read the build log, then reinstall the driver that matches your GPU generation. Which branch you need is not a guess - Omarchy's own detector tells you:

```bash
sudo cat /var/lib/dkms/nvidia*/*/build/make.log | tail -40

omarchy-hw-nvidia-gsp && echo "Turing or newer -> nvidia-open-dkms"
omarchy-hw-nvidia-without-gsp && echo "pre-Turing -> nvidia-580xx-dkms"
```

Install headers for the kernels you actually have, then the matching driver set (use -Syu, not -S, so you do not end up in a partial upgrade):

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --needed linux-headers

# Turing (GTX 16xx / RTX 20xx) and newer:
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --needed nvidia-open-dkms nvidia-utils lib32-nvidia-utils

# Pre-Turing (Maxwell / Pascal / Volta) - the 580xx legacy branch, NOT nvidia-dkms:
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --needed nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils

sudo limine-mkinitcpio
```

To get a working session right now without rebooting:

```bash
sudo systemctl stop sddm
sudo modprobe -r nvidia_drm nvidia_uvm nvidia_modeset nvidia
sudo modprobe nvidia_drm
sudo systemctl start sddm
```

If none of this works, reboot and select the pre-update snapshot in the Limine menu.

**Verify.** `modinfo -F version nvidia` matches `pacman -Q nvidia-utils`, and `hyprctl version` returns JSON after logging in.

Sources: <https://github.com/basecamp/omarchy/issues/5706> · <https://github.com/basecamp/omarchy/issues/6439> · <https://github.com/basecamp/omarchy/issues/8319>

---

## Omarchy 3 → 4 'Quattro' upgrade stops partway and leaves the machine half-v3, half-v4

`quattro-upgrade-incomplete-do-not-reboot` · severity: **critical** · frequency: **common** · applies to: `omarchy-3`, `omarchy-4`

**Symptom.** Running the Omarchy menu (Super + Alt + Space) > Update > "Omarchy To Quattro", or `omarchy-upgrade-to-quattro` directly, on an Omarchy 3.8.x box stops partway and prints in red:

```
Upgrade incomplete - do NOT reboot.
The system is part Omarchy 3 and part Omarchy quattro; rebooting now can leave it without a working network or desktop.
Fix the error reported above and run this script again. Re-running is safe and resumes the remaining steps.
```

The error just above it is usually one of: pacman rejecting cached `omarchy-*` packages as "invalid or corrupted package (PGP signature)" / checksum failures, `error: omarchy-keyring: signature from "Omarchy ..." is unknown trust`, or

```
Error: Legacy Limine configs exist (/boot/limine/limine.conf) but /boot/limine.conf does not. Do not reboot until the bootloader config is repaired.
```

**Cause.** `omarchy-upgrade-to-quattro` is a one-way, multi-stage transaction: it rewrites `/etc/pacman.d/mirrorlist` and the `[omarchy]` section of `/etc/pacman.conf` to point at the Quattro package servers (`pkgs.omarchy.org`), reinstalls the whole desktop as pacman packages under `/usr/share/omarchy`, retires a long list of v3 packages, and only then replaces the user's `~/.local/share/omarchy` git checkout with a symlink. It runs under `set -euo pipefail`, so any single failing step aborts and leaves the system with a v4 pacman config and a partly-v3 package set. The most common concrete trigger: pre-Quattro installs have `omarchy-*` packages cached in `/var/cache/pacman/pkg` that the Quattro server rebuilt under the same name and version with different bytes, so the cached copies fail the new database's checksum and abort the `--noconfirm` transaction.

> **Audit corrected this record.** Cause is verbatim-accurate against upstream `bin/omarchy-upgrade-to-quattro` (master, 2447 lines): `set -euo pipefail` (L8), the three-line red banner including "Re-running is safe and resumes the remaining steps." (L372-374), `as_root find /var/cache/pacman/pkg -maxdepth 1 -name 'omarchy-*' -delete` (L443) with the same-name/same-version/different-bytes comment, the key `40DFB630FF42BCFFB047046CF0134EE680CAC571` + `--keyserver keys.openpgp.org` + `--lsign-key` (L452-453), `pkgs.omarchy.org` channel servers (L319-327), `Legacy Limine configs exist (...) but /boot/limine.conf does not. Do not reboot until the bootloader config is repaired.` (L490), the exact four legacy paths (L473-476), timestamped `.omarchy-upgrade-to-quattro.<suffix>.bak` backups, and `--yes` / `--channel stable|rc|edge` (L4). `default/limine/limine.conf` exists in v3.8.0, so the `~/.local/share/omarchy/...` path is valid on a 3.8.x box. Two real defects in the fix. (1) Step 3 is unsafe in the exact state the record is about. The shipped `default/limine/limine.conf` is a branding/timeout template with ZERO boot entries (verified identical on v3.8.0 and quattro: no `protocol:`, no `path:`, no `//Snapshots`) — copying it blows away whatever entries /boot/limine.conf had, and the block then `rm -f`s all four alternate configs with no check that `limine-update` actually regenerated bootable entries. On a machine already displaying "do NOT reboot", that can turn a recoverable state into an unbootable one. Upstream itself gates on `grep -qE '(^|[[:space:]])root=' /boot/limine.conf` (L615); the record omits that gate. (2) The comment `--channel stable` / "stay on your current channel explicitly" is wrong: the script auto-detects the channel from the v3 mirrorlist (L58-64, matching `stable-mirror.omarchy.org` / `rc-mirror.omarchy.org` / `mirror.omarchy.org`) and `--channel` *overrides* that detection (usage L22: "Override the default stable Omarchy package channel"). `sudo limine-snapper-sync` is fine — ArchWiki's Limine page documents running it by hand as a check step.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** This upgrade is one-way — the script's own banner says "Upgrading Omarchy to Quattro is a one-way street! You cannot downgrade from Quattro." Take a snapshot (`omarchy-snapshot create`) and back up $HOME before starting; a snapshot restore recovers `/` but never `/home`. Rebooting while the "Upgrade incomplete" banner is showing can bring the machine up with no network and no desktop, because the pacman repos are already v4 while the installed packages are not. If the Limine config error appeared, do not reboot until `/boot/limine.conf` exists and `limine-update` succeeded, or the machine will not boot at all.

**Fix.**

Do **not** reboot while that banner is on screen. Read the real error above it, clear it, then re-run — the script is idempotent and resumes:

```bash
# 1. Cached legacy omarchy-* packages fail the new repo's checksums. This is
#    exactly what the script does internally; do it by hand if it aborted early.
sudo find /var/cache/pacman/pkg -maxdepth 1 -name 'omarchy-*' -delete
sudo pacman -Syy

# 2. Keyring / "unknown trust" failures on the [omarchy] repo
sudo pacman -Syy --noconfirm archlinux-keyring omarchy-keyring
# still failing? trust the Omarchy packaging key directly (same key the script uses)
sudo pacman-key --recv-keys 40DFB630FF42BCFFB047046CF0134EE680CAC571 --keyserver keys.openpgp.org
sudo pacman-key --lsign-key 40DFB630FF42BCFFB047046CF0134EE680CAC571
sudo pacman -Syy --noconfirm archlinux-keyring omarchy-keyring
```

**3. "Legacy Limine configs exist but /boot/limine.conf does not"** — repair the bootloader config BEFORE anything else. Prefer promoting the config you already have: it contains your real kernel entries. The Omarchy default under `default/limine/` is only branding + timeout and has **no boot entries at all**, so copying it is a last resort that depends entirely on `limine-update` regenerating them.

```bash
sudo ls -l /boot/limine.conf /boot/limine/limine.conf \
            /boot/EFI/limine/limine.conf /boot/EFI/arch-limine/limine.conf \
            /boot/EFI/BOOT/limine.conf 2>/dev/null

# 3a. Preferred: promote the alternate that already has working entries
sudo cp -a /boot/limine/limine.conf /boot/limine.conf     # or whichever one exists

# 3b. Only if none of them has entries: start from the Omarchy template
# sudo cp ~/.local/share/omarchy/default/limine/limine.conf /boot/limine.conf

# Regenerate kernel + snapshot entries
sudo limine-update
sudo limine-snapper-sync

# GATE - this is the same check the upgrade script uses (do not skip it).
# No output means /boot/limine.conf has no bootable entry: STOP and fix that
# before deleting anything or rebooting.
sudo grep -nE '(^|[[:space:]])root=' /boot/limine.conf
sudo grep -nc '^ *//' /boot/limine.conf     # count of entries

# Only once the gate passes, retire the stale alternates (back them up first)
sudo mkdir -p /root/limine-legacy
for f in /boot/limine/limine.conf /boot/EFI/limine/limine.conf \
         /boot/EFI/arch-limine/limine.conf /boot/EFI/BOOT/limine.conf; do
  [ -f "$f" ] && sudo cp -a "$f" "/root/limine-legacy/$(echo "${f#/boot/}" | tr / _)"
done
sudo rm -f /boot/limine/limine.conf /boot/EFI/limine/limine.conf \
           /boot/EFI/arch-limine/limine.conf /boot/EFI/BOOT/limine.conf
```

```bash
# 4. Resume the upgrade
omarchy-upgrade-to-quattro
#   non-interactive:  omarchy-upgrade-to-quattro --yes
#   The channel is auto-detected from your existing /etc/pacman.d/mirrorlist
#   (stable-mirror / rc-mirror / mirror.omarchy.org). Pass --channel only to
#   OVERRIDE that detection:
#                     omarchy-upgrade-to-quattro --channel stable|rc|edge
```

Everything it replaced is backed up next to the original with a timestamped suffix, so you can diff after the fact:

```bash
ls -d /etc/pacman.conf.omarchy-upgrade-to-quattro.*.bak \
      /etc/pacman.d/mirrorlist.omarchy-upgrade-to-quattro.*.bak \
      ~/.local/share/omarchy.omarchy-upgrade-to-quattro.*.bak
find ~/.config -maxdepth 3 -name '*.omarchy-upgrade-to-quattro.*.bak'
```

**Verify.** `omarchy-version` reports 4.x; `pacman -Q omarchy` returns a version; `ls /usr/share/omarchy/bin | head`; `readlink ~/.local/share/omarchy` prints `/usr/share/omarchy`; `omarchy update` runs to completion.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-upgrade-to-quattro> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-menu> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/update-process.md> · <https://learn.omacom.io/2/the-omarchy-manual/101/system-snapshots>

---

## Fix a permanent black screen after install on an older NVIDIA card

`black-screen-after-install-old-nvidia` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `desktop`, `nvidia`, `omarchy`

**Symptom.** Install completes and the machine reboots to a permanent black screen — no login prompt, sometimes not even a TTY. Common on older NVIDIA cards (Kepler/Maxwell/Pascal era, e.g. GT 630, GTX 10xx) paired with older Intel CPUs.

**Cause.** Two overlapping causes: (a) modern `nvidia`/`nvidia-open` packages no longer support pre-Turing GPUs — Arch's NVIDIA 590 release dropped Pascal and older and switched the main packages to the Open Kernel Modules; (b) with an unsupported card the DRM device never initialises, so Hyprland cannot start and there is nothing to display.

> **Audit corrected this record.** The problem is real but the fix throws away a supported path. Verified in install/hardware/nvidia.sh: Omarchy already handles pre-Turing cards by installing the legacy branch - `nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils` when `omarchy-hw-nvidia-without-gsp` matches, versus `nvidia-open-dkms nvidia-utils` for GSP-capable GPUs. All of those are listed in install/omarchy-other.packages. So the first move should be installing the 580xx branch, not ripping NVIDIA out for nouveau. The mkinitcpio guidance repeats the error from the sibling record: Omarchy uses /etc/mkinitcpio.conf.d/nvidia.conf (MODULES+=) and /etc/mkinitcpio.conf.d/omarchy_hooks.conf for the conditional kms removal, not /etc/mkinitcpio.conf; and modesetting is set in /etc/modprobe.d/nvidia.conf, not on the kernel cmdline, so 'drop nvidia_drm.modeset=1 from the kernel cmdline' targets something that is not there. Also GPU generations are conflated: a GT 630 is Fermi/Kepler and needs the 470xx branch, while a GTX 10xx is Pascal and is covered by 580xx. `pacman -Rns nvidia-utils` can cascade into other packages that depend on it.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Removing driver packages and editing mkinitcpio.conf can leave the machine with no working display path at all. Do this from a TTY you can get back to, keep the LTS kernel entry, and note that `pacman -Rns nvidia-utils` may cascade-remove other packages — read the transaction list before confirming.

**Fix.**

Get to a console. If `Ctrl + Alt + F2` is dead, reboot, press `e` on the Limine entry and append `nomodeset` to the kernel cmdline for a one-off text boot.

Identify the card and let Omarchy's own detector tell you which driver branch you need:

```bash
lspci -k | grep -A3 -i vga
lsmod | grep -E 'nvidia|nouveau'
journalctl -b -p err --no-pager | head -50

omarchy-hw-nvidia-gsp && echo "Turing+ -> nvidia-open-dkms"
omarchy-hw-nvidia-without-gsp && echo "pre-Turing -> nvidia-580xx-dkms"
```

For a pre-Turing card, install the **legacy 580xx branch** - do not go to nouveau first. This is the path Omarchy's installer itself takes:

```bash
# Maxwell / Pascal / Volta (e.g. GTX 9xx, GTX 10xx, Titan V):
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --needed \
  nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils linux-headers
sudo limine-mkinitcpio
sudo reboot
```

For a Fermi/Kepler card (e.g. GT 630, GTX 6xx/7xx), 580xx does NOT cover it - you need the older legacy branch from the AUR:

```bash
yay -S nvidia-470xx-dkms nvidia-470xx-utils
sudo limine-mkinitcpio
```

Only if no legacy branch supports your card, fall back to nouveau/Mesa:

```bash
sudo pacman -Rns nvidia-open-dkms nvidia-utils lib32-nvidia-utils   # review the cascade before confirming
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --needed mesa lib32-mesa vulkan-nouveau
```

Then remove Omarchy's NVIDIA drop-ins - these are separate files, NOT edits to /etc/mkinitcpio.conf:

```bash
sudo rm -f /etc/mkinitcpio.conf.d/nvidia.conf
sudo rm -f /etc/modprobe.d/nvidia.conf
sudo limine-mkinitcpio
sudo reboot
```

Leave the `kms` hook alone - /etc/mkinitcpio.conf.d/omarchy_hooks.conf restores it automatically once nvidia_drm is no longer early-loaded. And do not go hunting for `nvidia_drm.modeset=1` on the kernel cmdline; Omarchy sets modesetting via modprobe.d, so it was never there.

**Verify.** After reboot the login screen appears; `lsmod | grep nouveau` shows the module loaded and `hyprctl monitors` lists your display.

Sources: <https://github.com/basecamp/omarchy/issues/2434> · <https://archlinux.org/news/> · <https://github.com/basecamp/omarchy/issues?q=is%3Aissue+nvidia>

---

## Add the missing Limine boot entry after a suspiciously fast install

`limine-boot-entry-missing-after-install` · severity: **critical** · frequency: **occasional** · applies to: `amd`, `arch`, `desktop`, `laptop`, `nvidia`, `omarchy`

**Symptom.** Install finishes suspiciously fast ("under 3 minutes"), with an error that flashes past too quickly to read. On reboot the machine lands in the Limine boot menu but the only entry is a generic **EFI** option — no Omarchy/Arch kernel entry at all. Reported on both AMD and NVIDIA hardware.

**Cause.** The Omarchy installer's Limine step failed (commonly the initramfs/UKI generation or the Limine config write), so no kernel boot entry was created. The installer's error handling swallowed it and the run "completed".

> **Audit corrected this record.** The scenario and the chroot recovery shape are sound, and /boot/limine.conf is the correct path (13 references across the repo vs 1 legacy reference to /boot/limine/limine.conf). `limine-mkinitcpio` is real. But `pacman -S limine limine-mkinitcpio-hook` is wrong as written: archlinux.org shows only `limine` (extra, 12.6.1) in the official repos - `limine-mkinitcpio-hook` is not an official package, it comes from the AUR / the [omarchy] repo (it is listed in install/omarchy-other.packages). From a plain Arch ISO chroot that command fails unless the [omarchy] repo and its keyring are already configured. The `mkinitcpio -P` + `limine-mkinitcpio` pair is redundant (limine-mkinitcpio rebuilds initramfs/UKI for all kernels itself), and the recovery omits `limine-update`, which is what actually writes the entries. `limine bios-install /dev/nvme0n1` on an NVMe UEFI install is very unlikely to be what anyone wants and deserves a stronger caveat.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Chroot bootloader surgery on the wrong device wipes the ESP. Double-check `lsblk -f` before mounting, and never run `limine bios-install` against a UEFI-only install.

**Fix.**

Boot the Omarchy/Arch ISO, mount and chroot into the installed system:

```bash
cryptsetup open /dev/nvme0n1p2 cryptroot   # your LUKS partition
mount -o subvol=@ /dev/mapper/cryptroot /mnt
mount /dev/nvme0n1p1 /mnt/boot             # your ESP
arch-chroot /mnt
```

Inside the chroot, regenerate the initramfs/UKI and the Limine entries. `limine-mkinitcpio` does the initramfs rebuild for every kernel and updates the boot entries in one pass, so you do not need a separate `mkinitcpio -P`:

```bash
limine-mkinitcpio
limine-update
cat /boot/limine.conf        # confirm a kernel entry now exists
ls /boot/EFI/Linux/          # confirm the UKI (omarchy_linux.efi) exists
exit
umount -R /mnt
reboot
```

If the tooling is missing, install it. Only `limine` is in the official Arch repos - `limine-mkinitcpio-hook` comes from the AUR or the [omarchy] repo, so on a plain Arch ISO chroot you need that repo configured (or build it from the AUR) first:

```bash
pacman -S limine
pacman -S limine-mkinitcpio-hook limine-entry-tool   # requires the [omarchy] repo or AUR
```

If `/boot/limine.conf` is missing entirely, restore Omarchy's default and rebuild:

```bash
cp /usr/share/omarchy/default/limine/limine.conf /boot/limine.conf
limine-mkinitcpio
limine-update
```

Do NOT run `limine bios-install` on a UEFI machine. Omarchy installs are UEFI (Secure Boot off, ESP at /boot), and BIOS-installing Limine to the disk is only correct for a genuine legacy-BIOS install.

**Verify.** `ls /boot/EFI/Linux/` (or `/boot/limine.conf`) contains a kernel/UKI entry, and the Limine menu shows a named Omarchy entry on next boot.

Sources: <https://github.com/basecamp/omarchy/issues/4152> · <https://github.com/basecamp/omarchy/issues/3543> · <https://github.com/basecamp/omarchy/issues?q=is%3Aissue+installer+fails+sort%3Acomments-desc>

---

## Fix a black screen after the LUKS passphrase is accepted

`luks-prompt-then-no-desktop` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** After an update and reboot, the LUKS passphrase prompt appears and accepts the password, then the screen goes black with a blinking cursor. A message flashes for a fraction of a second and is unreadable. `Ctrl + Alt + F2` does nothing — the machine is completely inaccessible.

**Cause.** The graphical session fails to come up after unlock. On Omarchy 4 that means SDDM or the uwsm session, not `seamless-login`: `bin/omarchy-upgrade-to-quattro` removes `/etc/systemd/system/omarchy-seamless-login.service` and `/usr/local/bin/seamless-login` and disables the unit, and Omarchy 4 boots through SDDM (`install/login/sddm.sh`). Under uwsm the session is `wayland-wm@hyprland.service`, not a `hyprland` unit. Because Omarchy hides the boot text and the session never comes up, there is no TTY handoff either, so the console appears dead. It is a session-startup failure, not a disk-decryption failure.

> **Audit corrected this record.** The recovery approach is sound and the multi-user.target trick is the right instinct. But the cause is half-obsolete and one command is wrong. `seamless-login` no longer exists on current Omarchy: bin/omarchy-upgrade-to-quattro explicitly removes /etc/systemd/system/omarchy-seamless-login.service and /usr/local/bin/seamless-login and disables the unit - Omarchy 4 boots through SDDM (install/login/sddm.sh). So on a current system the thing to inspect is sddm, not seamless-login. `uwsm start hyprland` is not the correct invocation - uwsm takes a desktop entry (hyprland-uwsm.desktop) or an explicit `--` separator. Under uwsm the session is also not a `hyprland` unit, so a `journalctl -u hyprland` style lookup returns nothing; it is wayland-wm@hyprland.service. Minor: `cat file | tail` is a useless use of cat, and the quiet/splash removal should go through Omarchy's limine-entry-tool drop-ins rather than hand-editing.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Editing the kernel cmdline at the Limine prompt is temporary and safe, but making it permanent in limine.conf incorrectly can prevent boot. Do not remove the `cryptdevice`/`rd.luks` parameters — that makes the encrypted root unreachable.

**Fix.**

Boot into a text-only session so you can read the error. At the Limine menu press `e` on the Omarchy entry and append to the kernel cmdline:

```
systemd.unit=multi-user.target
```

Boot, log in at the console, then read what actually failed. Current Omarchy logs in through SDDM, so check that first:

```bash
journalctl -b -1 -p err --no-pager | tail -60
systemctl status sddm
journalctl -b -1 -u sddm --no-pager | tail -40
```

The compositor runs under uwsm, so look at the session unit rather than a `hyprland` unit:

```bash
journalctl --user -b -1 -u wayland-wm@hyprland.service --no-pager | tail -60
```

And review the update transcript:

```bash
tail -60 /tmp/omarchy-update.log
```

Try launching the compositor by hand to see the real error text. uwsm wants a desktop entry, not a bare name:

```bash
uwsm start hyprland-uwsm.desktop
```

(If that entry is absent, `uwsm start -- Hyprland` works as a fallback.)

If it is a driver/session mismatch, the reliable escape is the pre-update snapshot: reboot, pick the dated snapshot entry in the Limine menu, then run `omarchy-snapshot restore`.

To make future failures debuggable, drop the silent-boot flags. On Omarchy these live in limine-entry-tool drop-ins, so edit there and regenerate rather than hand-editing the bootloader config:

```bash
ls /etc/limine-entry-tool.d/
sudo limine-mkinitcpio
```

**Verify.** `systemctl --user status` shows the graphical session units active after a normal boot, and the desktop appears without the black-screen stall.

Sources: <https://github.com/basecamp/omarchy/issues/688> · <https://github.com/basecamp/omarchy/issues/6439> · <https://learn.omacom.io/2/the-omarchy-manual/101/system-snapshots>

---

## Recover a black screen after an update migration rebuilt the initramfs

`nvidia-initramfs-migration-breaks-boot` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `hyprland`, `nvidia`, `omarchy`, `wayland`

**Symptom.** After an `omarchy update` that ran a migration touching the boot image, the machine reboots into a black screen or a broken session, and the crash watcher reports:

```
failed to get hyprland version string (bad json)
```

Users report the update "looked fine" and only the reboot revealed the breakage.

**Cause.** An Omarchy migration script rebuilds the initramfs via `limine-mkinitcpio`. On NVIDIA systems that rebuild can drop the required modules (or the nouveau GSP firmware), so the proprietary driver never loads. Hyprland then cannot get GPU rendering and exits, and the watchdog's `hyprctl version -j` returns nothing parseable — hence the "bad json".

> **Audit corrected this record.** The symptom is real but the fix edits the wrong files and would actively damage an Omarchy system. Verified in the repo: Omarchy does NOT manage /etc/mkinitcpio.conf directly - install/hardware/nvidia.sh writes /etc/mkinitcpio.conf.d/nvidia.conf containing `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` (append, not assign). Telling the user to set `MODULES=(nvidia ...)` in /etc/mkinitcpio.conf clobbers other hardware drop-ins (thunderbolt_module.conf, surface/apple keyboard drop-ins all use MODULES+=). The kms advice is also wrong: /etc/mkinitcpio.conf.d/omarchy_hooks.conf already drops kms automatically and CONDITIONALLY (only when nvidia_drm is early-loaded and NVIDIA owns every display), with a dedicated test at test/shell.d/nvidia-kms-hook-test.sh - hand-editing HOOKS fights it. Worst of all, the cmdline check is wrong: install/hardware/nvidia.sh sets modesetting via /etc/modprobe.d/nvidia.conf (`options nvidia_drm modeset=1`), NOT the kernel cmdline, so `cat /proc/cmdline | grep -i nvidia` returns nothing on a perfectly healthy machine and will send users chasing a non-problem.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing mkinitcpio.conf and rebuilding the boot image can make the system unbootable if the wrong hooks are removed. Keep an Arch live USB handy and do not delete the previous snapshot until the new boot is confirmed.

**Fix.**

Boot the previous snapshot from the Limine menu, or get to a TTY with `Ctrl + Alt + F2`. Confirm the driver did not load:

```bash
lsmod | grep -i nvidia
journalctl -b -p err --no-pager | head -50
```

Do NOT edit /etc/mkinitcpio.conf. Omarchy configures NVIDIA entirely through drop-ins; check that they still exist and are intact:

```bash
cat /etc/mkinitcpio.conf.d/nvidia.conf
# expect: MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)

cat /etc/modprobe.d/nvidia.conf
# expect: options nvidia_drm modeset=1
```

If the mkinitcpio drop-in is missing or was truncated, recreate it exactly as the installer does - note the `+=`, which appends instead of wiping the other hardware drop-ins:

```bash
printf 'MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)\n' | sudo tee /etc/mkinitcpio.conf.d/nvidia.conf
printf 'options nvidia_drm modeset=1\n' | sudo tee /etc/modprobe.d/nvidia.conf
```

Leave the `kms` hook alone. Omarchy's /etc/mkinitcpio.conf.d/omarchy_hooks.conf removes it automatically, and only on systems where nvidia_drm is early-loaded and NVIDIA drives every display - removing it by hand breaks hybrid-GPU laptops.

Rebuild the initramfs and the Limine entries in one step:

```bash
sudo limine-mkinitcpio
sudo reboot
```

Verify modesetting is actually on. It is set through modprobe.d, so it will NOT appear in /proc/cmdline - check the module parameter instead:

```bash
cat /sys/module/nvidia_drm/parameters/modeset
# expect: Y
```

**Verify.** After reboot, `lsmod | grep nvidia_drm` shows the module loaded and `hyprctl version -j` returns valid JSON.

Sources: <https://github.com/basecamp/omarchy/issues/8319> · <https://github.com/basecamp/omarchy/issues/5706>

---

## Hyprland customizations silently revert after the Quattro upgrade because ~/.config/hypr/*.conf is no longer read

`hypr-conf-overrides-ignored-after-quattro` · severity: **high** · frequency: **very-common** · applies to: `omarchy-4`

**Symptom.** "After upgrading to Omarchy 4 all my Hyprland tweaks are gone." Custom keybinds, monitor resolution/refresh/scale, keyboard layout (an AZERTY/QWERTZ session comes back as US QWERTY), touchpad natural scrolling and `exec-once` autostarts all revert to stock — but `~/.config/hypr/hyprland.conf`, `bindings.conf`, `input.conf`, `monitors.conf`, `looknfeel.conf` are still sitting on disk with the settings in them.

A subset of users instead get a black screen with a red Hyprland error banner:

```
attempt to index a nil value (global 'o')
```

referencing `default/hypr/autostart.lua:1`, `default/hypr/bindings/media.lua:2`, `default/hypr/bindings/clipboard.lua:13`, `default/hypr/windows.lua:3`.

**Cause.** Hyprland 0.55 deprecated hyprlang in favour of Lua. It loads `$XDG_CONFIG_HOME/hypr/hyprland.lua` when that file exists and only falls back to `hyprland.conf` when it does not. `omarchy-upgrade-to-quattro` unconditionally installs the stock Quattro entry points — its `always_copy_config_files` list is `hypr/hyprland.lua`, `hypr/bindings.lua`, `hypr/input.lua`, `hypr/looknfeel.lua`, `hypr/monitors.lua`, `hypr/autostart.lua`, `hypr/.luarc.json` — and deliberately leaves the legacy `.conf` files alone ("Hyprland .conf files are intentionally left in place for users to reference/port after the upgrade"). The moment `hyprland.lua` exists, every `.conf` it used to source is dead weight.

The keyboard layout is a special case: the packaged `default/hypr/input.lua` reads `local kb_layout = vconsole.XKBLAYOUT or "us"`. Most installs have only `KEYMAP=fr` in `/etc/vconsole.conf` and no `XKBLAYOUT`, so the layout silently falls back to `us` (issue #6878).

The `global 'o'` crash is different: it hits people who already hand-wrote a `hyprland.lua` on an earlier release whose entrypoint never called `require("default.hypr.helpers")`, which is where the `o` helper table is defined. No migration backfills that line (issue #5879).

> **Audit corrected this record.** Cause verified line-for-line. hypr.land/news/26_lua: "if you don't have a hyprland.lua config file, your old hyprland.conf will be loaded... However, if you do have one, hyprland.lua will be loaded instead. This check is only done once at startup" — plus "Other hypr* tools will for now continue using hyprlang", which validates leaving hyprsunset.conf/xdph.conf alone. The `always_copy_config_files` list in omarchy-upgrade-to-quattro (L1631) matches the record exactly (hypr/.luarc.json, autostart.lua, bindings.lua, hyprland.lua, input.lua, looknfeel.lua, monitors.lua). `default/hypr/input.lua` really does read `local kb_layout = vconsole.XKBLAYOUT or "us"`. `default/hypr/helpers.lua` really defines global `o = o or {}`, and upstream `config/hypr/hyprland.lua` does NOT require it directly (it goes bootstrap -> `require("default.hypr.omarchy")`), so the missing-require diagnosis is correct; bootstrap.lua puts `~/.config/?.lua` and `$OMARCHY_PATH/?.lua` on package.path so the require resolves. Every Lua line in the fix is copied verbatim from upstream's own commented examples (hl.monitor / hl.env / hl.config / o.bind / hl.unbind / o.launch_on_start). Issues #6878 and #5879 are real and titled exactly as described. Two defects: (1) `hyprctl getoption input:kb_layout` uses the retired hyprlang colon syntax — wiki.hypr.land's hyprctl page now states "the option name should be written as `section.option`" with examples `general.border_size` and `input.touchpad.disable_while_typing`, so it must be `input.kb_layout`; the colon form is exactly the kind of stale pre-Lua syntax that should not ship. (2) For the most-reported symptom (#6878, layout reverting to US) the record only offers hardcoding kb_layout in input.lua, and never mentions the one-line root-cause fix: populate XKBLAYOUT in /etc/vconsole.conf, which the packaged default already reads. ArchWiki Xorg/Keyboard_configuration confirms "localectl additionally writes the keyboard configuration to /etc/vconsole.conf using variables XKBLAYOUT, XKBMODEL, XKBVARIANT and XKBOPTIONS".
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** hyprlock and hypridle deliberately stayed on hyprlang — the Hyprland announcement says "Other hypr* tools will for now continue using hyprlang as their config language provider." Do not convert `hyprlock.conf` to Lua while porting; a broken hyprlock config locks you out of a running session. `omarchy-refresh-config` overwrites the target file (it does write a `.bak.<epoch>` first). Move the legacy `.conf` files rather than deleting them until you have confirmed every setting is ported.

**Fix.**

Your old settings are still readable — port them block by block into the Lua files Omarchy now loads.

```bash
ls -l ~/.config/hypr/*.conf   # the settings you are missing are in here
```

**Keyboard layout first — it has a one-line root-cause fix.** Omarchy's packaged `default/hypr/input.lua` reads `vconsole.XKBLAYOUT or "us"`, and most installs only have `KEYMAP=` set. Give it the variable it is looking for and the layout comes back everywhere (Hyprland, TTY, initramfs prompt):

```bash
grep -E 'KEYMAP|XKB' /etc/vconsole.conf     # likely KEYMAP=fr and no XKBLAYOUT
sudo localectl set-x11-keymap fr            # writes XKBLAYOUT=fr to /etc/vconsole.conf
# with a variant/options, e.g.:
# sudo localectl set-x11-keymap fr "" azerty compose:caps
grep -E 'XKB' /etc/vconsole.conf
hyprctl reload && hyprctl getoption input.kb_layout
```

Then port the rest:

```lua
-- ~/.config/hypr/monitors.lua
-- old: monitor = DP-2,2560x1440@144,0x0,1
hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "0x0", scale = 1 })
-- old: env = GDK_SCALE,2
hl.env("GDK_SCALE", "2")

-- ~/.config/hypr/input.lua  (only if you want to override vconsole.conf here)
-- old: input { kb_layout = fr; kb_options = compose:caps; touchpad { natural_scroll = true } }
hl.config({
  input = {
    kb_layout = "fr",
    kb_variant = "",
    kb_options = "compose:caps",
    accel_profile = "flat",
    touchpad = { natural_scroll = true, disable_while_typing = false },
  },
})

-- ~/.config/hypr/bindings.lua
-- old: bind = SUPER SHIFT, R, exec, alacritty -e ssh your-server
o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")
-- old: unbind = SUPER SHIFT, B
hl.unbind("SUPER + SHIFT + B")

-- ~/.config/hypr/looknfeel.lua
-- old: general { gaps_in = 0; gaps_out = 0; border_size = 0 }
hl.config({ general = { gaps_in = 0, gaps_out = 0, border_size = 0 } })

-- ~/.config/hypr/autostart.lua
-- old: exec-once = my-service
o.launch_on_start("my-service")
```

Apply and check without logging out. Note that on Hyprland 0.55+ `getoption` takes `section.option` with **dots** — the old `input:kb_layout` colon form is hyprlang syntax and no longer correct:

```bash
hyprctl reload
hyprctl getoption input.kb_layout
hyprctl getoption input.touchpad.natural_scroll
hyprctl monitors
hyprctl binds | grep -B2 -A2 'SSH'
hyprctl configerrors
# try a setting live before writing it to a file:
hyprctl repl
```

For the `global 'o'` crash, either add the missing require to your own `~/.config/hypr/hyprland.lua` right after the bootstrap/paths line:

```lua
dofile((os.getenv("OMARCHY_PATH") or "/usr/share/omarchy") .. "/default/hypr/bootstrap.lua")
require("default.hypr.helpers")
require("default.hypr.omarchy")
```

or reset to the shipped entrypoint (it saves yours as `hyprland.lua.bak.<epoch>` and prints the diff):

```bash
omarchy-refresh-config hypr/hyprland.lua
```

Once ported, get the dead files out of the way — but leave `hyprsunset.conf` and `xdph.conf`, whose tools are still hyprlang:

```bash
mkdir -p ~/.config/hypr/legacy-conf
mv ~/.config/hypr/hyprland.conf ~/.config/hypr/bindings.conf ~/.config/hypr/input.conf \
   ~/.config/hypr/monitors.conf ~/.config/hypr/looknfeel.conf ~/.config/hypr/autostart.conf \
   ~/.config/hypr/envs.conf ~/.config/hypr/legacy-conf/ 2>/dev/null
```

**Verify.** `hyprctl getoption input:kb_layout` reports your layout; `hyprctl monitors` shows the right mode/scale; `hyprctl binds` lists your custom binds; no red error banner at login.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-upgrade-to-quattro> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/config/hypr/hyprland.lua> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/config/hypr/monitors.lua> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/config/hypr/input.lua> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/config/hypr/bindings.lua> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/config/hypr/looknfeel.lua> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/config/hypr/autostart.lua> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-refresh-config> · <https://github.com/basecamp/omarchy/issues/6878> · <https://github.com/basecamp/omarchy/issues/5879> · <https://hypr.land/news/26_lua/>

---

## Finish an omarchy update that aborted partway with a red banner

`omarchy-update-aborted-midway` · severity: **high** · frequency: **very-common** · applies to: `omarchy`

**Symptom.** Running the update from the menu (Super + Alt + Space > Update > Omarchy) or `omarchy update` stops partway with a red banner: "Something went wrong during the update! Please review the output above carefully, correct the error, and retry the update." The desktop may then be in a half-updated state — theme wrong, menu items missing, or waybar/shell not restarting.

**Cause.** `omarchy-update` is a wrapper around an ordered chain, and any non-zero exit in it trips the script's `trap` and aborts. The real order is: pkg-prune -> `omarchy-snapshot create` -> `omarchy-update-dev` -> `omarchy-update-keyring` -> `omarchy-update-system-pkgs` (packages) -> `omarchy-migrate` (migrations) -> hooks -> AUR. Packages come **before** migrations, deliberately - upstream's own comment reads 'Migrations ship with the packages installed here and are written against them, so everything below waits on this finishing.' So an abort partway leaves packages upgraded with their migrations unapplied. There is no `git pull` step: Omarchy 4 is pacman-packaged at `/usr/share/omarchy`. The whole session is teed to a log file.

> **Audit corrected this record.** Log path /tmp/omarchy-update.log, the ERR trap, the red banner text, `omarchy update`, and `omarchy debug --print` -> /tmp/omarchy-debug.log all verified in bin/omarchy-update and bin/omarchy-debug. But the Cause section has the step order BACKWARDS. bin/omarchy-update runs: pkg-prune -> omarchy-snapshot create -> omarchy-update-dev -> omarchy-update-keyring -> omarchy-update-system-pkgs (packages) -> omarchy-migrate (migrations) -> hooks -> AUR. Upstream's own comment says: 'Migrations ship with the packages installed here and are written against them, so everything below waits on this finishing.' The record claims migrations run in step 2 and packages in step 3. Also: the menu is Super+Space (Super+Alt+Space is the Apps menu, per default/hypr/bindings/utilities.lua), there is no longer a git pull into ~/.local/share/omarchy (Omarchy 4 is pacman-packaged at /usr/share/omarchy), and the bare `sudo pacman -Syu` fallback is now BLOCKED by bin/omarchy-update-pacman-guard.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** An aborted update leaves the system in a partial-upgrade state. Do NOT install new packages until `sudo pacman -Syu` completes cleanly — installing against a half-synced database is the classic Arch way to break glibc/libalpm linkage.

**Fix.**

Read the log first - it is always written, even when the screen scrolled past:

```bash
less /tmp/omarchy-update.log
```

Understand the order so you know what state you are in. `omarchy-update` runs: snapshot -> keyring refresh -> **package upgrade** -> **migrations** -> post-update hooks -> AUR packages. Packages come FIRST because migrations are written against the packages they ship with. So an abort during the package step means migrations have NOT run yet (config is still old, consistent); an abort during migrations means new packages are installed against partially-migrated config.

Fix the reported cause and re-run. The update is idempotent - already-applied migrations are tracked in ~/.local/state/omarchy/migrations and are skipped:

```bash
omarchy update
```

Menu equivalent: `Super + Space` > **Update** > **Omarchy**. (`Super + Alt + Space` is the Apps menu, not this.)

If the failure was in package resolution, do NOT run bare `pacman -Syu` - Omarchy installs an ALPM guard that aborts direct system upgrades. Use the documented bypass for a single transaction, then resume:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
omarchy update
```

If it still fails, collect a diagnostic bundle:

```bash
omarchy debug          # writes /tmp/omarchy-debug.log, offers upload to logs.omarchy.org
omarchy debug --print  # dump to terminal instead
```

If the machine is unusable, reboot and pick the pre-update snapshot from the Limine menu (see `limine-snapshot-rollback`).

**Verify.** `omarchy update` completes and prints no error banner; `tail -n 40 /tmp/omarchy-update.log` shows the package transaction finishing.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-debug> · <https://learn.omacom.io/2/the-omarchy-manual/68/updates> · <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting>

---

## Get past Secure Boot blocking the Omarchy ISO or the installed system

`secure-boot-blocks-omarchy-install` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** The Omarchy ISO won't boot at all ("Security Violation", "Invalid signature detected", or it drops straight back to the firmware menu), or the install completes but the machine refuses to boot the new Limine entry afterwards.

**Cause.** Omarchy ships an unsigned bootloader and unsigned DKMS kernel modules. Secure Boot rejects them. TPM-backed measurements can also invalidate the boot chain after the installer rewrites the ESP. The install docs state Secure Boot and/or TPM must be off.

> ⚠️ **Risk.** Switching an existing Windows install from Intel RST to AHCI will make Windows blue-screen on boot unless you enable safe-mode first. Omarchy's installer also WIPES the selected drive and applies full-disk encryption — back up before selecting a disk that has data on it.

**Fix.**

Enter firmware setup (usually `F2`/`Del`/`F10` at power-on) and:

1. Set **Secure Boot** to *Disabled* (some vendors require setting **OS Type** to *Other OS* first, or clearing the Secure Boot keys with "Delete all Secure Boot variables" / "Reset to Setup Mode").
2. Disable **TPM / PTT / fTPM** if present.
3. Set SATA/NVMe mode to **AHCI**, not *RAID*/*Intel RST* — Linux cannot see the disk in RST mode.
4. Disable **Fast Boot**.
5. Save and exit, then boot the USB.

Confirm from a live shell that Secure Boot is actually off:

```bash
bootctl status | grep -i 'secure boot'
# expect: Secure Boot: disabled
```

Or:

```bash
mokutil --sb-state
```

**Verify.** `bootctl status` reports `Secure Boot: disabled`, the ISO boots to the installer, and after install the Limine entry appears and boots.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/50/getting-started> · <https://learn.omacom.io/2/the-omarchy-manual/96/manual-installation> · <https://github.com/basecamp/omarchy/issues?q=is%3Aissue+installer+fails+sort%3Acomments-desc>

---

## Enter the LUKS passphrase when only a Bluetooth keyboard is available

`bluetooth-keyboard-cannot-unlock-luks` · severity: **high** · frequency: **common** · applies to: `arch`, `desktop`, `laptop`, `omarchy`

**Symptom.** Fresh install boots to the full-disk-encryption passphrase prompt and the Bluetooth keyboard is completely unresponsive — no characters appear. The same keyboard works fine once the desktop is up. Also reported at the SDDM login screen.

**Cause.** The LUKS prompt runs from the initramfs, before userspace, so the Bluetooth stack (bluetoothd, pairing keys) does not exist yet. Bluetooth keyboards physically cannot type the passphrase. The same limitation hits the display manager on some setups because Bluetooth input devices aren't reconnected before it starts. Omarchy's install docs call this out as a hard prerequisite.

> ⚠️ **Risk.** `systemd-cryptenroll` modifies LUKS keyslots. Verify you still have a working passphrase keyslot (`cryptsetup luksDump /dev/nvme0n1p2`) before rebooting, and keep a header backup.

**Fix.**

Use a wired USB keyboard, or a 2.4 GHz dongle keyboard (which enumerates as a plain USB HID device and works in the initramfs), for the passphrase prompt.

Check what the initramfs will actually see:

```bash
lsusb
```

If you must keep Bluetooth, enrol a TPM2 or FIDO2 token so the disk unlocks without typing (note: Omarchy asks you to disable TPM at install, so this needs a deliberate change):

```bash
sudo systemd-cryptenroll --fido2-device=auto /dev/nvme0n1p2
```

For the *login* screen specifically, make Bluetooth start early and auto-power the adapter — in `/etc/bluetooth/main.conf`:

```
[Policy]
AutoEnable=true
```

then:

```bash
sudo systemctl enable --now bluetooth.service
```

**Verify.** Typing at the LUKS prompt echoes asterisks/characters and the disk unlocks; `bluetoothctl devices Connected` lists the keyboard after login.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/50/getting-started> · <https://learn.omacom.io/2/the-omarchy-manual/96/manual-installation> · <https://github.com/basecamp/omarchy/issues?q=is%3Aissue+bluetooth+OR+wifi+not+working>

---

## Roll back to a Limine snapshot after an update broke the desktop

`limine-snapshot-rollback` · severity: **high** · frequency: **common** · applies to: `desktop`, `laptop`, `omarchy`, `systemd-boot`

**Symptom.** An update left the machine broken — black screen, login loop, or a desktop that won't start — and the user wants to get back to the state from 10 minutes ago. They ask "how do I undo an omarchy update?"

**Cause.** Omarchy takes a btrfs snapshot before every update and registers it as a bootable Limine entry. Most users don't know the entries are there, or they roll back and are then surprised that their dotfiles didn't change back.

> **Audit corrected this record.** `omarchy-snapshot create` and `omarchy-snapshot restore` are verified real (restore shells out to `sudo limine-snapper-restore`), and manual/47-system-snapshots.md confirms the whole flow including the click-the-notification step. Three corrections. (1) The 'Applies to' tag lists systemd-boot, which is flatly wrong - the manual states the feature 'is only available on installations using the Limine boot loader ... It's not available if you're on GRUB or systemd-boot.' (2) Snapshots are snapper-managed, not raw btrfs: install/config/snapper.sh installs a `root` config from default/snapper/root with NUMBER_LIMIT=5 and TIMELINE_CREATE=no. (3) It omits the Direct Boot trap - if Setup > Direct Boot is enabled, the firmware boots Omarchy straight past Limine, so the snapshot entries are unreachable until you pick Limine from the BIOS boot menu. That is exactly the situation where a user needs a rollback and cannot find one.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Snapshot restore only restores the root subvolume — /home is NOT rolled back, so ~/.config keeps its post-update state and can still be mismatched. Snapshots only exist on Limine installs; GRUB/systemd-boot installs have no rollback entries. `omarchy reinstall` overwrites customised configs.

**Fix.**

1. Reboot. At the **Limine** boot menu, pick the snapshot entry labelled with the date and Omarchy version from *before* the bad update (the version shows in the bottom-left corner).

   If you never see a Limine menu, you have *Setup > Direct Boot* enabled - the firmware is jumping straight to Omarchy. Interrupt at power-on and choose **Limine** from your BIOS/UEFI boot menu to reach the snapshot entries.

   Snapshots require the Limine bootloader (default since Omarchy 2.0). They do not exist on GRUB or systemd-boot installs.

2. The system boots read-write into that snapshot. A notification appears - click it to make the rollback permanent, or run:

```bash
omarchy-snapshot restore
```

To take a snapshot manually before doing something risky:

```bash
omarchy-snapshot create
```

Snapshots are managed by snapper against the `root` config only, and Omarchy keeps the last 5 with no timeline snapshots. Inspect them with:

```bash
sudo snapper -c root list
```

Remember a restore covers the root subvolume only - /home and ~/.config are untouched (see `snapshot-restore-does-not-restore-home`).

If the desktop is fine but only Omarchy's own config is mangled, skip the rollback:

```bash
omarchy-refresh-hyprland     # overwrites ~/.config/hypr/*.lua with defaults (.bak kept)
```

or the nuclear option, which reinstalls default packages, forces you back to stable, downgrades anything too new, and resets every config file:

```bash
omarchy reinstall
```

**Verify.** `omarchy --version` (or the version shown in the Limine entry you booted) reflects the older release, and the desktop starts normally.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/101/system-snapshots> · <https://learn.omacom.io/2/the-omarchy-manual/68/updates> · <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting>

---

## Unlock an account faillock locked after failed password attempts

`locked-out-faillock-too-many-attempts` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `manjaro`, `omarchy`

**Symptom.** After mistyping the password a few times, the login screen (or `sudo`) rejects even the correct password. `su` reports `Account locked due to N failed logins`, or authentication just silently fails every time.

**Cause.** PAM's `pam_faillock` has locked the account after repeated failed authentications. It stays locked until the deny window expires or the counter is reset. Very common right after an install where the keyboard layout defaulted to a different one than the user typed the password in.

> **Audit corrected this record.** Substantially correct - manual/45-troubleshooting.md gives almost this exact procedure (`CTRL + ALT + F2`, login as root, `faillock --reset --user [your-username]`). Two gaps. (1) It omits the single most useful fact: bin/omarchy-apply-lock configures pam_faillock with `deny=10 unlock_time=120`, so the lockout clears itself after two minutes - most users just need to wait rather than drop to a TTY. (2) The keyboard-layout remedy uses the obsolete `.conf` format; current Omarchy uses ~/.config/hypr/input.lua with an hl.config() call. Minor caveat worth adding: logging in as root at the TTY only works if a root password was actually set.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Omarchy configures pam_faillock with `deny=10 unlock_time=120`, so the simplest fix is to **wait two minutes** and try again - the lockout expires on its own.

If you do not want to wait, switch to a text console with `Ctrl + Alt + F2` and log in as **root** (this requires a root password to have been set), then reset the counter:

```bash
faillock --user yourusername --reset
```

Check the state first if you want:

```bash
faillock --user yourusername
```

If root has no password, log in as your own user on the TTY once the 120s window has expired and run it with sudo:

```bash
sudo faillock --user yourusername --reset
```

Then `Ctrl + Alt + F1` back to the graphical session.

If the underlying cause was a wrong keyboard layout at the login screen, fix it in `~/.config/hypr/input.lua`:

```lua
hl.config({
  input = {
    kb_layout = "us",
  },
})
```

(On an older Omarchy 3 install this is `~/.config/hypr/input.conf` using the `input { kb_layout = us }` block syntax.) Apply with `hyprctl reload`.

**Verify.** `faillock --user yourusername` reports no failures and the normal password works at the login screen.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting> · <https://learn.omacom.io/2/the-omarchy-manual/67/faq>

---

## Fix unknown-trust signatures on packages from the omarchy repository

`omarchy-keyring-signature-unknown-trust` · severity: **high** · frequency: **common** · applies to: `arch`, `omarchy`

**Symptom.** Updating fails with pacman signature errors on packages from the `[omarchy]` repository, e.g.

```
error: omarchy-shell: signature from "Omarchy <...>" is unknown trust
:: File /var/cache/pacman/pkg/....pkg.tar.zst is corrupted (invalid or corrupted package (PGP signature)).
```

or `error: failed to synchronize all databases (invalid or corrupted database (PGP signature))`.

**Cause.** Omarchy ships its own signed pacman repository. Its signing key (fingerprint `40DFB630FF42BCFFB047046CF0134EE680CAC571`) must be in the local pacman keyring and locally signed. The key gets lost or goes stale after a clock skew, a restored snapshot, a manual /etc/pacman.d edit, or an `archlinux-keyring` that fell far behind.

> **Audit corrected this record.** The fingerprint 40DFB630FF42BCFFB047046CF0134EE680CAC571 and keyserver keys.openpgp.org are verified exactly (bin/omarchy-update-keyring and manual/48-security.md). The clock-first advice is good. Three problems. (1) It misses the canonical one-command fix: `omarchy-update-keyring` exists and does precisely this recv-keys/lsign-key/install-omarchy-keyring dance. (2) `sudo pacman -Sy` then `sudo pacman -S ...` then `sudo pacman -Syyuu` will be aborted by bin/omarchy-update-pacman-guard on the -Syyuu step. (3) `sudo pacman -Syyuu --noconfirm` is genuinely dangerous as written - the double-u enables downgrades and --noconfirm accepts every one of them silently. The `rm -rf /etc/pacman.d/gnupg` step is the standard Arch recovery but is presented with no warning that it destroys every locally-signed key on the machine.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `pacman -Syyuu` can downgrade packages (`-uu`) — that is intentional here to resync with the Omarchy mirror, but do not run it while a previous transaction is half-applied.

**Fix.**

Make sure the system clock is right first - a wrong clock invalidates every signature:

```bash
timedatectl set-ntp true
timedatectl status
```

Then use Omarchy's own repair command, which imports and locally signs the key and installs the keyring package exactly the way the installer does:

```bash
omarchy-update-keyring
```

If that is unavailable, do it by hand. This is the same sequence upstream runs:

```bash
sudo pacman-key --init
sudo pacman-key --populate archlinux
sudo pacman-key --recv-keys 40DFB630FF42BCFFB047046CF0134EE680CAC571 --keyserver keys.openpgp.org
sudo pacman-key --lsign-key 40DFB630FF42BCFFB047046CF0134EE680CAC571
sudo pacman-key --list-keys 40DFB630FF42BCFFB047046CF0134EE680CAC571   # confirm it is there
```

Then refresh the keyring packages and finish the upgrade through Omarchy, which handles the guard and the ordering for you:

```bash
omarchy update
```

If you must drive pacman directly, use the documented bypass and do NOT pass --noconfirm to a downgrade-enabled upgrade - `-uu` permits downgrades and you want to see them before they happen:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Sy archlinux-keyring omarchy-keyring
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
```

Only if the keyring database itself is corrupt, rebuild it from scratch:

```bash
# WARNING: this deletes every key and every local signature on this machine,
# including any keys you added yourself. You must re-import and re-lsign after.
sudo rm -rf /etc/pacman.d/gnupg
sudo pacman-key --init
sudo pacman-key --populate archlinux
sudo pacman-key --recv-keys 40DFB630FF42BCFFB047046CF0134EE680CAC571 --keyserver keys.openpgp.org
sudo pacman-key --lsign-key 40DFB630FF42BCFFB047046CF0134EE680CAC571
```

Then resume with `omarchy update`.

**Verify.** `pacman-key --list-keys 40DFB630FF42BCFFB047046CF0134EE680CAC571` shows the key with a local signature, and `sudo pacman -Syu` completes with no PGP errors.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/master/install/preflight/pacman.sh> · <https://learn.omacom.io/2/the-omarchy-manual/93/security>

---

## Top bar gone and staying gone — the Quickshell omarchy-shell crash-loops and its supervisor gives up

`omarchy-shell-bar-crash-loop` · severity: **high** · frequency: **common** · applies to: `omarchy-4`

**Symptom.** The Omarchy top bar disappears and does not come back. No tray icons, Super+Space does nothing, the theme and background switchers never render, notifications stop. `hyprctl layers` shows `omarchy-background` but no `omarchy-bar`. In the journal:

```
omarchy-shell[2888127]: Omarchy shell exited with status 255; relaunching.
omarchy-shell[…]: Giving up on the Omarchy shell after 6 relaunches in under a minute.
```

Other fatal lines seen right before it dies:

```
WARN quickshell.hyprland.ipc: Got removal for monitor "FALLBACK" which was not previously tracked.
WARN: The Wayland connection experienced a fatal error: Invalid argument
FATAL: Tried to show lockscreen surfaces without active lock
```

Often Wi-Fi, Bluetooth or audio appear dead at the same time simply because their bar controls are gone.

**Cause.** Omarchy 4 dropped Waybar — the bar, tray, notifications, launcher, menu and lock screen are all one Quickshell process, `omarchy-shell`, launched and supervised by `omarchy-launch-shell`. That supervisor relaunches on any non-zero exit but gives up after 5 relaunches inside a 60-second window, which is when the bar stays gone. Documented triggers: (1) a `quickshell`/Qt upgrade landing while the old shell is still running — updates rewrite `$OMARCHY_PATH/shell`, and `omarchy-update-restart` restarts the shell unconditionally for exactly this reason; (2) DPMS wake / monitor hotplug where Hyprland emits a removal for a transient `FALLBACK` output Quickshell never recorded as added, desyncing its surface bookkeeping into a fatal Wayland protocol error (issue #7380); (3) the lockscreen `qFatal` after the quickshell 0.3.1 / Qt 6.11.2 update (issue #8647); (4) a broken user plugin under `~/.config/omarchy/plugins`.

> ⚠️ **Risk.** `omarchy-restart-shell` deliberately refuses when the session is genuinely locked — "Refusing to restart Omarchy shell while the session is locked." — because killing a live locker leaves you behind Hyprland's failsafe with no way to authenticate. Do not force past that guard; use a TTY or reboot. If you move `~/.config/omarchy/plugins` aside, remember to move it back after testing, and note that saving a file under that directory while the session is locked has itself been reported to strand the session (issue #7106).

**Fix.**

```bash
# 1. Read why it died (this is the only durable log - Quickshell's own log is on tmpfs)
journalctl --user -b -t omarchy-shell -n 200 --no-pager
ls -t ~/.cache/quickshell/crashes | head

# 2. Bring it back without logging out. Works from a terminal or over ssh.
omarchy-restart-shell                 # menu: Update > Process > Shell

# 3. Dies again straight away? Take user plugins out of the picture.
mv ~/.config/omarchy/plugins ~/.config/omarchy/plugins.off
omarchy-restart-shell

# 4. Reset the shell config to the shipped default (saves yours as .bak.<epoch>)
omarchy-refresh-config omarchy/shell.json
omarchy-restart-shell

# 5. Hardware whose only visible control went with the bar - the Update > Hardware
#    menu items, runnable directly:
omarchy-restart-wifi        # rfkill unblock wifi; nmcli radio wifi on; rescan
omarchy-restart-bluetooth   # rfkill unblock bluetooth
omarchy-restart-audio       # restart wireplumber/pipewire/pipewire-pulse, unstick USB cards
omarchy-restart-trackpad

# 6. If quickshell/Qt were upgraded under the running session, reboot - the shell
#    cannot be made consistent with a half-swapped QML tree.
omarchy-system-reboot
```

No graphical session left at all? Switch to a TTY with `Ctrl+Alt+F2`, log in, and run `omarchy-restart-shell` there — it derives `HYPRLAND_INSTANCE_SIGNATURE` from the newest instance runtime dir on its own.

**Verify.** `omarchy-shell shell ping` returns; `hyprctl layers | grep omarchy-bar` shows the layer; `journalctl --user -b -t omarchy-shell` stops emitting "relaunching" lines.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-launch-shell> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-shell> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-restart> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-audio> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-wifi> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-bluetooth> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/omarchy/omarchy-menu.jsonc> · <https://github.com/basecamp/omarchy/issues/7380> · <https://github.com/basecamp/omarchy/issues/8647>

---

## Update aborts with 'exists in filesystem' file conflicts in /usr/share/omarchy

`pacman-file-exists-in-filesystem-omarchy` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `manjaro`, `omarchy-4`

**Symptom.** An update stops with:

```
error: failed to commit transaction (conflicting files)
omarchy: /usr/share/omarchy/bin/omarchy-foo exists in filesystem
Errors occurred, no packages were upgraded.
```

Run through `omarchy update` you may instead see it recover by itself with a yellow "Taking over files pacman doesn't own yet:" block. Run by hand with `pacman -Syu` there is no recovery and every subsequent attempt fails the same way. A different, easily confused error is `:: package X and package Y are in conflict. Remove Y? [y/N]`, where `--noconfirm` answers No and the whole upgrade stops.

**Cause.** pacman refuses by design to install over a file that no package owns. On Omarchy this is common because `/usr/share/omarchy` gets written by installers, migrations and hand edits as well as by the `omarchy` package, and because pre-Quattro installs left files behind that the packaged layout now claims. Omarchy's own path already anticipates this: `omarchy-update-system-pkgs` runs `pacman -Syu --noconfirm --overwrite '/usr/share/omarchy/*'`, and on failure execs `omarchy-update-system-pkgs-when-conflicted`, which greps the pacman stderr report for `^omarchy(-dev|-settings|-settings-dev)?: <path> exists in filesystem`, re-checks each path with `pacman -Qo`, moves the unowned ones under `/var/lib/omarchy/replaced/<original path>`, retries once, and puts them back if the retry did not claim them. A *package-vs-package* conflict is a decision rather than a cleanup, so it is deliberately handed back to you for an interactive answer and is never auto-resolved under `-y`.

> ⚠️ **Risk.** Never widen the glob to `--overwrite '*'` — it will silently clobber files owned by other packages and is the single fastest way to make a system unrepairable. Only overwrite a path you have confirmed with `pacman -Qo` is unowned. Move conflicting files instead of deleting them: on this system `sddm.conf.d` and `systemd/system-sleep` are read wholesale, so a copy left *beside* the original would still be live, which is exactly why Omarchy quarantines to a mirrored path under `/var/lib/omarchy/replaced` rather than renaming in place.

**Fix.**

```bash
# 1. Does a package own it? If yes, this is a packaging bug - report it, do not delete.
pacman -Qo /usr/share/omarchy/bin/omarchy-foo

# 2. Unowned: move it aside (do NOT delete) exactly the way Omarchy does, then retry.
sudo mkdir -p /var/lib/omarchy/replaced/usr/share/omarchy/bin
sudo mv -T --backup=numbered /usr/share/omarchy/bin/omarchy-foo \
        /var/lib/omarchy/replaced/usr/share/omarchy/bin/omarchy-foo
omarchy update

# 3. For conflicts confined to Omarchy's own tree, the supported one-liner
#    (this is the exact command the updater uses, guard flag included):
sudo env OMARCHY_UPDATE_PACMAN=1 pacman -Syu --overwrite '/usr/share/omarchy/*'

# 4. For a package-vs-package conflict, run the update interactively so you can
#    answer the prompt. Never use -y here - it promises not to ask, so the step
#    reports and skips instead.
omarchy update

# 5. See what was quarantined on your behalf and clean up once you are happy
sudo find /var/lib/omarchy/replaced -type f -o -type l
```

If the conflict is caused by a corrupt local package database entry rather than a stray file (the classic ArchWiki case — an empty or missing `/var/lib/pacman/local/<pkg>-<ver>/files`), reinstall that one package with a scoped overwrite:

```bash
sudo env OMARCHY_UPDATE_PACMAN=1 pacman -S --overwrite '/usr/share/omarchy/*' omarchy
```

**Verify.** `pacman -Qkk omarchy omarchy-settings` reports no missing or altered files; `omarchy update` completes; `sudo find /var/lib/omarchy/replaced -type f` shows only files you expect to have been taken over.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-system-pkgs> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-system-pkgs-when-conflicted> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/update-process.md> · <https://wiki.archlinux.org/title/Pacman>

---

## 'omarchy update' refuses to start: you need at least 10 GiB free (btrfs snapshots eating the root subvolume)

`update-blocked-insufficient-free-space` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `omarchy-4`

**Symptom.** `omarchy update` exits immediately, before it even asks for confirmation:

```
You need at least 10 GiB free to safely update Omarchy.
```

On a btrfs root the confusing part is that `df -h /` can still show a couple of gigabytes free while `sudo btrfs filesystem usage /` shows the device is effectively full, and an update that is forced through then dies later with `No space left on device` out of mkinitcpio or pacman.

**Cause.** `omarchy-update-requires-free-space` runs `df --output=avail --block-size=1 /` and aborts below 10 GiB (10737418240 bytes). On Omarchy's default btrfs layout that space is usually not "used by files" at all: `install/config/snapper.sh` installs a snapper `root` config with `NUMBER_LIMIT=5` / `NUMBER_LIMIT_IMPORTANT=5`, and `omarchy update` creates a pre-update snapshot on every run. Those five snapshots pin every block that any deleted file used to occupy, including `/var/cache/pacman/pkg`, which lives on the same snapshotted subvolume — which is exactly why `omarchy-update-pkg-prune` runs `paccache -rk2` *before* the snapshot rather than after. Deleting files inside the live root therefore frees nothing until the snapshots holding them age out.

> ⚠️ **Risk.** `snapper delete` is permanent — those snapshots are the rollback targets you would boot to from Limine if the update breaks the desktop, so never delete the newest one and never delete the snapshot you are currently booted into. `OMARCHY_UPDATE_FORCE=1` on a genuinely full root is how you get a truncated `vmlinuz`/initramfs written mid-transaction and an unbootable machine; only use it when you have verified the free space yourself. `btrfs balance` is I/O-heavy and must not be interrupted by a power loss — run it on AC.

**Fix.**

```bash
# 1. Get the truth. df lies on btrfs; use btrfs's own accounting.
sudo btrfs filesystem usage /
df -h /
sudo du -xhd1 /var | sort -h | tail

# 2. Pacman + AUR caches (Omarchy keeps 2 versions; drop to 1 to reclaim more)
sudo paccache -rk1
sudo paccache -ruk0          # drop every cached version of uninstalled packages
yay -Sc --noconfirm          # ~/.cache/yay build trees

# 3. Journal
journalctl --disk-usage
sudo journalctl --vacuum-size=200M

# 4. The usual real culprit: old snapshots. Keep at least the newest one.
sudo snapper -c root list
sudo snapper -c root delete --sync 12 13 14      # --sync releases the space now
sudo snapper -c root delete --sync 20-24         # a range works too
sudo snapper -c root cleanup number              # apply NUMBER_LIMIT=5 retention

# 5. Re-check and update
sudo btrfs filesystem usage /
omarchy update
```

If btrfs still reports the device full after deleting snapshots (allocated-but-unused chunks):

```bash
sudo btrfs balance start -dusage=20 -musage=20 /
sudo btrfs filesystem usage /
```

Only when you are certain the 10 GiB figure is wrong for your layout (for example `/var` is a separate filesystem with plenty of room), bypass the check:

```bash
OMARCHY_UPDATE_FORCE=1 omarchy update
```

**Verify.** `df -h /` shows more than 10 GiB available on `/`, `sudo btrfs filesystem usage /` shows free (estimated) well above that, and `omarchy update` reaches its confirmation prompt.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-requires-free-space> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-pkg-prune> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/snapper/root> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/install/config/snapper.sh> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/update-process.md> · <https://wiki.archlinux.org/title/Snapper>

---

## Fix yay failing with a libalpm.so shared library error

`yay-libalpm-shared-library-error` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `manjaro`, `omarchy`

**Symptom.** After an interrupted or manual upgrade, every AUR command dies instantly with:

```
yay: error while loading shared libraries: libalpm.so.15: cannot open shared object file: No such file or directory
```

`omarchy update` then fails too, because it shells out to yay. Users describe it as "deadlocked — I can't update because the updater is broken."

**Cause.** Classic partial upgrade. `pacman` was upgraded (bumping libalpm's soname, e.g. .so.14 -> .so.15) but `yay`, which links against libalpm, was not upgraded in the same transaction. Usually caused by `pacman -Sy <pkg>`, a Ctrl-C'd transaction, or an update that aborted after pacman but before yay.

> **Audit corrected this record.** The failure mode is real and yay is still shipped (install/omarchy-base.packages lists `yay`). But the primary fix `sudo pacman -Syu` is now BLOCKED on Omarchy by bin/omarchy-update-pacman-guard, so the record's first command fails outright. The premise is also overstated: `omarchy update` is not deadlocked by a broken yay, because bin/omarchy-update runs omarchy-update-system-pkgs (pacman) first and omarchy-update-aur-pkgs (yay) last, and omarchy-update-aur-pkgs is skipped entirely unless `pacman -Qem` reports foreign packages. Additionally yay-bin conflicts with/provides yay, so `makepkg -si` will prompt to replace the installed yay, and makepkg must not be run as root - neither is mentioned.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not `pacman -Sy` a single package to "fix" this — that deepens the partial upgrade. Always use a full `-Syu`.

**Fix.**

`pacman` itself still works. On Omarchy, a bare `pacman -Syu` is stopped by the update guard, so either run the normal updater (preferred - it upgrades system packages with pacman before it ever touches yay):

```bash
omarchy update
```

or, if you need pacman directly for this one transaction:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
```

Either one pulls the rebuilt `yay` and the soname mismatch goes away. Confirm:

```bash
yay --version
```

Only if yay is still broken (its repo build genuinely lags the new libalpm) fall back to the prebuilt `yay-bin`. Run makepkg as your normal user, never with sudo. `yay-bin` conflicts with `yay`, so pacman will ask to replace it - answer yes:

```bash
sudo pacman -S --needed git base-devel
cd /tmp
git clone https://aur.archlinux.org/yay-bin.git
cd yay-bin
makepkg -si          # as your user; accepts replacing yay with yay-bin
```

Then resume the normal path:

```bash
omarchy update
```

**Verify.** `yay --version` prints a version instead of the loader error, and `omarchy update` runs to completion.

Sources: <https://github.com/basecamp/omarchy/issues/3877> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update>

---

## Direct Boot hides the Limine menu, so snapshot rollback is unreachable when an update breaks the desktop

`direct-boot-hides-limine-snapshot-menu` · severity: **high** · frequency: **occasional** · applies to: `omarchy-4`

**Symptom.** After enabling Setup > Direct Boot, the green "Omarchy Bootloader" menu never appears — the machine goes straight from the vendor logo into Omarchy. Later, when an update breaks the desktop and the manual says "restart and select a pre-update snapshot from the boot menu", there is no boot menu to select from. Users report being stuck at a black screen or login loop with no visible way back.

A related report: Setup > Direct Boot itself fails with `Error: No Omarchy UKI found in /boot/EFI/Linux/` even though `sudo ls /boot/EFI/Linux/` clearly shows `omarchy_linux.efi`.

**Cause.** `omarchy-setup-direct-boot` creates a firmware boot entry with `efibootmgr --create --label Omarchy --loader '\EFI\Linux\<uki>.efi'`, and efibootmgr places new entries at the head of `BootOrder`. The firmware then loads the unified kernel image directly and Limine never runs — and Limine is what renders the snapshot entries that `limine-snapper-sync` writes into `/boot/limine.conf`. The confirmation prompt says as much: "Setup direct boot (so snapshot booting must be done via bios)?". Some users reach the same state a different way, by setting `timeout: 0` in `/boot/limine.conf` (Omarchy ships it commented out as `#timeout: 3`, so Limine's own 5s default applies). Separately, the script refuses to run at all on some machines, and these are the current reasons: it hard-exits when `/sys/class/dmi/id/bios_vendor` matches *american megatrends* ("may not safely support custom EFI entries") or *apple*, when not booted UEFI, or when `efibootmgr` is not functional. `Error: No Omarchy UKI found in /boot/EFI/Linux/` means the probe `sudo find /boot/EFI/Linux/ -name 'omarchy*.efi'` matched nothing — the ESP is not mounted at /boot, or the install boots a separate kernel+initramfs rather than a UKI, or the UKI is not named `omarchy*.efi`. This is **not** a sudo/permissions problem: the script's find already runs under sudo, and the beta bug that did have that symptom (issue #6651) is fixed and closed.

> **Audit corrected this record.** The main mechanism is correct and well sourced: `bin/omarchy-setup-direct-boot` does `efibootmgr --create --disk --part --label "Omarchy" --loader "\\EFI\\Linux\\$uki_file"` (efibootmgr prepends new entries to BootOrder), the confirm prompt is verbatim "Setup direct boot (so snapshot booting must be done via bios)?", re-running detects the entry and offers "Disable direct boot (remove Omarchy EFI entry)?" then `efibootmgr --bootnum "$boot_num" --delete-bootnum`, and `default/limine/limine.conf` really ships `#timeout: 3` commented out (Limine's own default of 5s then applies, as the record says). ArchWiki's Limine page confirms limine-snapper-sync is the thing that writes snapshot entries and that running `limine-snapper-sync` by hand is a documented check step. But the second half of the cause is factually wrong against current upstream: the script's probe is `uki_file=$(sudo find /boot/EFI/Linux/ -name "omarchy*.efi" -printf "%f\n" 2>/dev/null | head -1)` — it already runs under sudo, so "the script's find runs without sudo" is not true, and the cited issue #6651 ("Quattro, beta 1: Setup -> Direct boot reports Error: No Omarchy UKI found") is CLOSED, i.e. fixed. Telling readers "the file is there, the script just cannot see it" sends them chasing a bug that no longer exists. The record also misses the reason Direct Boot most visibly refuses to run today: the script hard-exits on `american megatrends` and `apple` BIOS vendors before it ever looks for a UKI — and the record's manual `efibootmgr --create` fallback walks straight past that deliberate safety check with no warning.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never delete an EFI boot entry you have not identified — `efibootmgr --delete-bootnum` on the wrong `Boot####` can leave the machine with nothing bootable. Confirm a Limine/Arch entry exists in `efibootmgr` output *before* rebooting after a deletion; if in doubt, reorder with `--bootorder` instead of deleting. `omarchy-setup-direct-boot` deliberately refuses to run on American Megatrends and Apple firmware because they mishandle custom EFI entries — do not work around that by creating the entry by hand on those machines. Also remember a snapshot restore recovers `/` but not `/home`, so `~/.config` stays as-is after a rollback.

**Fix.**

```bash
# Right now, to reach a snapshot once: use the firmware's one-time boot menu
#   (F12 / F8 / F9 / Esc, vendor-specific) and pick the Limine/Arch/disk entry
#   rather than the "Omarchy" entry.

# Permanent: run the same menu item again - it detects the entry and offers removal
omarchy-setup-direct-boot            # menu: Setup > Direct Boot

# Or by hand
sudo efibootmgr                      # note BootOrder and the Boot#### of "Omarchy"
sudo efibootmgr --bootnum 0003 --delete-bootnum      # remove it
sudo efibootmgr --bootorder 0001,0003                # or just demote it

# Make sure Limine still has a visible menu and current snapshot entries
sudo grep -n '^ *#\?timeout' /boot/limine.conf
#   commented out  -> Limine's own default (5s) applies
#   timeout: 0     -> menu is skipped; change it to 'timeout: 3'
sudo sed -i 's/^timeout: 0$/timeout: 3/' /boot/limine.conf
sudo limine-snapper-sync
sudo limine-snapper-list             # the entries that should appear in the menu
sudo snapper -c root list
```

If `omarchy-setup-direct-boot` refuses to run, read which check stopped it — the message is specific, and two of them are deliberate refusals, not bugs:

```bash
cat /sys/class/dmi/id/bios_vendor
#   American Megatrends / Apple -> the script exits on purpose. AMI firmware may
#   not safely handle custom EFI entries and Apple uses its own boot manager.
#   Do NOT hand-roll the entry to get around this.
[ -d /sys/firmware/efi ] && echo UEFI || echo "BIOS/CSM - direct boot N/A"
sudo efibootmgr >/dev/null && echo "efibootmgr OK"
```

`Error: No Omarchy UKI found in /boot/EFI/Linux/` means the probe genuinely matched nothing — it already runs as `sudo find`, so this is not a permissions artefact (that beta bug, issue #6651, is fixed). Check what is actually there:

```bash
findmnt /boot                        # is the ESP mounted where you think?
sudo ls -l /boot/EFI/Linux/          # need a file matching omarchy*.efi
```

If the listing is empty or the kernel is a separate vmlinuz + initramfs rather than a UKI, there is nothing for direct boot to point at — configure a UKI first (`limine-mkinitcpio-hook` / `limine-update`) instead of creating the entry by hand.

**Verify.** `sudo efibootmgr` no longer shows "Omarchy" first in `BootOrder`; rebooting shows the "Omarchy Bootloader" menu; snapshot entries with dates and the Omarchy version in the bottom-left corner are listed.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-setup-direct-boot> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/limine/limine.conf> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-refresh-limine> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/omarchy/omarchy-menu.jsonc> · <https://github.com/basecamp/omarchy/issues/6651> · <https://learn.omacom.io/2/the-omarchy-manual/101/system-snapshots>

---

## Fix 'Limine config not found' when the installer wrote a working one

`limine-snapper-wrong-config-path` · severity: **high** · frequency: **occasional** · applies to: `arch`, `omarchy`

**Symptom.** Install or update aborts with:

```
Error: Limine config not found at /boot/limine/limine.conf
```

even though the installer clearly wrote a working `/boot/limine.conf`. Reported on Omarchy 3.2 installs.

**Cause.** The limine-snapper integration script has a fallback branch that assumes the config lives at `/boot/limine/limine.conf` (the BIOS layout). On installs where Limine's config was written to `/boot/limine.conf` (or `/boot/EFI/BOOT/limine.conf`), the path check misses and the script bails.

> **Audit corrected this record.** The path confusion is real - /boot/limine.conf is Omarchy's actual location and a legacy /boot/limine/limine.conf reference does still exist in the tree (bin/omarchy-upgrade-to-quattro:476). But the proposed fix cannot work on a normal Omarchy install. /boot IS the EFI System Partition (record 9 in this same set mounts /dev/nvme0n1p1 at /mnt/boot), and the ESP is vfat. vfat does not support symbolic links, so `sudo ln -sf /boot/limine.conf /boot/limine/limine.conf` fails with 'Operation not permitted' - it will never satisfy the path check. A bind mount or a copy is required instead, and the copy has to be kept in sync or the bootloader reads a stale config.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not move or delete the real limine.conf — symlink to it. Removing it leaves the machine unbootable.

**Fix.**

Find where the config actually is:

```bash
sudo find /boot -name 'limine.conf' 2>/dev/null
findmnt /boot        # note the FSTYPE - on Omarchy this is usually vfat (the ESP)
```

On Omarchy the real file is `/boot/limine.conf`.

Do NOT try to symlink it into place. `/boot` is the EFI System Partition and is formatted vfat, which has no symlink support - `ln -s` there fails outright. If you need the legacy `/boot/limine/limine.conf` path to resolve, use a bind mount, which works on vfat and disappears on reboot (so it cannot silently rot):

```bash
sudo mkdir -p /boot/limine
sudo mount --bind /boot/limine.conf /boot/limine/limine.conf
```

Re-run the failing step, then unmount:

```bash
omarchy update
sudo umount /boot/limine/limine.conf
```

The real fix is to update - the path detection was corrected upstream, and current Omarchy consistently uses `/boot/limine.conf`:

```bash
omarchy update
```

If your Limine config genuinely is at a different location, regenerate Omarchy's canonical one rather than papering over the path:

```bash
omarchy-refresh-limine     # moves the old file to /boot/limine.conf.bak, rewrites it,
                           # then runs limine-update and limine-snapper-sync
```

**Verify.** `sudo limine-mkinitcpio` runs without the "Limine config not found" error, and snapshot entries appear in the boot menu.

Sources: <https://github.com/basecamp/omarchy/issues/3543>

---

## Stop omarchy update wiping your config edits every time

`customizations-lost-editing-omarchy-defaults` · severity: **medium** · frequency: **very-common** · applies to: `hyprland`, `omarchy`, `wayland`

**Symptom.** User edits a config file, everything works, then the next `omarchy update` silently reverts all of it. They report "my keybindings/theme tweaks keep getting wiped on every update." Usually they had edited something under ~/.local/share/omarchy/default/hypr/.

**Cause.** Omarchy 4's defaults are pacman-owned and live at `/usr/share/omarchy` (the `omarchy` package). Edits there vanish because a package upgrade rewrites the files - not because of a git hard-sync; the `~/.local/share/omarchy` git checkout was Omarchy 3. The config is Lua and layered: `~/.config/hypr/hyprland.lua` does `dofile(OMARCHY_PATH .. "/default/hypr/bootstrap.lua")`, then `require("default.hypr.omarchy")`, then requires `hypr.monitors` / `hypr.input` / `hypr.bindings` / `hypr.looknfeel` / `hypr.autostart`, then `default.hypr.toggles`. The user files are loaded after the defaults so they win. Editing the defaults is always the wrong layer.

> **Audit corrected this record.** The principle (never edit Omarchy's defaults, put overrides in the user layer) is correct and still correct. But essentially every specific in this record is obsolete, and the quoted load order is not real. Verified: config/hypr/hyprland.conf DOES NOT EXIST in the current repo - the quoted `source =` block cannot be reproduced from upstream. Current Omarchy uses Lua: ~/.config/hypr/hyprland.lua does `dofile(OMARCHY_PATH .. "/default/hypr/bootstrap.lua")`, then `require("default.hypr.omarchy")`, then requires hypr.monitors / hypr.input / hypr.bindings / hypr.looknfeel / hypr.autostart, then default.hypr.toggles. The defaults path is /usr/share/omarchy (pacman-owned), not a git checkout at ~/.local/share/omarchy - so the reason edits vanish is that a package upgrade overwrites them, not a git hard-sync. The `unbind = SUPER, K` conf syntax no longer applies; Omarchy 4 exposes `omarchy_default_bindings = false` and `omarchy_preinstalled_bindings = false` in hyprland.lua and uses `o.bind(...)`.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Never edit anything under `/usr/share/omarchy` (older installs: `~/.local/share/omarchy`). On current Omarchy that directory is owned by the `omarchy` pacman package, so every upgrade overwrites it. Put overrides in the matching user file - they are loaded after Omarchy's defaults and therefore win:

| Want to change | Edit |
|---|---|
| monitors, scale, GDK_SCALE | `~/.config/hypr/monitors.lua` |
| keyboard layout, repeat, touchpad | `~/.config/hypr/input.lua` |
| keybindings | `~/.config/hypr/bindings.lua` |
| gaps, borders, animations, blur | `~/.config/hypr/looknfeel.lua` |
| apps started at login | `~/.config/hypr/autostart.lua` |

The real load order lives in `~/.config/hypr/hyprland.lua`:

```lua
-- Omarchy's bootstrap keeps path setup out of this user config.
dofile((os.getenv("OMARCHY_PATH") or "/usr/share/omarchy") .. "/default/hypr/bootstrap.lua")

-- Load Omarchy defaults.
require("default.hypr.omarchy")

-- Your personal overrides, loaded after the defaults so they win.
require("hypr.monitors")
require("hypr.input")
require("hypr.bindings")
require("hypr.looknfeel")
require("hypr.autostart")

require("default.hypr.toggles")
```

To replace a default keybinding, just bind the same key in `~/.config/hypr/bindings.lua` - it is loaded later and overrides:

```lua
o.bind("SUPER + K", "My command", "your-command")
```

To turn Omarchy's bindings off wholesale, uncomment the flags in `hyprland.lua`:

```lua
omarchy_default_bindings = false        -- drop all Omarchy bindings
omarchy_preinstalled_bindings = false   -- keep window-manager bindings, drop app launchers
```

Apply without logging out:

```bash
hyprctl reload
```

On an older Omarchy 3 install the same principle holds, but the files are `.conf`, the defaults live in `~/.local/share/omarchy/default/hypr/`, and unbinding uses `unbind = SUPER, K`.

**Verify.** `hyprctl binds | grep -i <yourkey>` shows your binding, and it survives the next `omarchy update`.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/master/config/hypr/hyprland.conf> · <https://github.com/basecamp/omarchy/tree/master/default/hypr> · <https://learn.omacom.io/2/the-omarchy-manual/65/dotfiles>

---

## 'Woah partner...' — the Omarchy pacman guard aborts every direct pacman -Syu

`pacman-guard-blocks-direct-syu` · severity: **medium** · frequency: **very-common** · applies to: `omarchy-4`

**Symptom.** Any direct system upgrade aborts before a single package is touched:

```
:: Checking Omarchy update entrypoint...

Woah partner...

This looks like a direct pacman system upgrade. Omarchy updates should normally
run through:

  omarchy update
...
error: command failed to execute correctly
```

Hits `sudo pacman -Syu`, `yay -Syu`, `paru -Syu`, and any GUI frontend that shells out to them. Installing a single package (`pacman -S foo`) still works.

**Cause.** The `omarchy` package installs an ALPM PreTransaction hook, `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook`, with `AbortOnFail`, `Operation = Upgrade`, `Type = Package`, `Target = *`, running `/usr/bin/omarchy-update-pacman-guard`. The guard reads the invoking pacman's command line from `/proc/$PPID/cmdline` and exits non-zero when it sees both a sync flag and a sysupgrade flag (`-S` + `-u`, `-Syu`, `--sync --sysupgrade`). It allows the transaction when `OMARCHY_UPDATE_PACMAN=1` (set by Omarchy's own update commands) or `OMARCHY_ALLOW_DIRECT_PACMAN=1` (your explicit opt-out). It exists because a raw `-Syu` skips the transcript, the pre-update snapshot, the keyring refresh, the per-user migrations, the post-update hooks and the shell restart.

> **Audit corrected this record.** Cause is exact. `default/libalpm/hooks/00-omarchy-update-guard.hook` is verbatim `Operation = Upgrade` / `Type = Package` / `Target = *` / `Description = Checking Omarchy update entrypoint...` / `When = PreTransaction` / `Depends = omarchy` / `Exec = /usr/bin/omarchy-update-pacman-guard` / `AbortOnFail`, which also explains the leading ":: Checking Omarchy update entrypoint..." line. `bin/omarchy-update-pacman-guard` reads `/proc/$PPID/cmdline`, requires BOTH a sync and a sysupgrade flag (so `pacman -S foo` really is unaffected), honours `OMARCHY_UPDATE_PACMAN=1` and `OMARCHY_ALLOW_DIRECT_PACMAN=1`, and its message is reproduced word for word including the suggested `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu`. alpm-hooks(5) confirms the shadow trick verbatim: system dir is /usr/share/libalpm/hooks, custom dir defaults to /etc/pacman.d/hooks, and "Hooks may be overridden by placing a file with the same name in a higher priority hook directory. Hooks may be disabled by overriding them with a symlink to /dev/null." `omarchy-migrate --pending` exits 0 when pending, as claimed, and `omarchy-hook post-update` exists. The defect is the AUR-helper escape hatch, both lines of it. `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 yay -Syu` tells the reader to run yay as root, which yay refuses/breaks on by design (it builds as an unprivileged user and warns against sudo). And dropping the sudo does not work either: yay and paru shell out to their own `sudo pacman -Syu`, and sudo's default env_reset strips OMARCHY_ALLOW_DIRECT_PACMAN before pacman ever sees it, so the guard reads `-Syu` off /proc and aborts anyway. Both lines fail in practice.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Bypassing is the whole point of the message: you skip the snapshot (no rollback target if the upgrade breaks the desktop), the keyring refresh, the migrations and the post-update hooks. The usual result of repeated bypasses is a desktop that starts but with a broken bar, theme or portal, because configs written for the newer library versions never landed. Always follow a bypass with `omarchy-migrate`. Do not `rm` the hook file itself — the `/etc/pacman.d/hooks` symlink override is the reversible way, and deleting the packaged file just means the next upgrade silently restores the guard.

**Fix.**

```bash
# The blessed path
omarchy update

# Deliberate one-off bypass for pacman itself - this exact command is what the
# guard prints
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
```

**AUR helpers need a different approach.** Never run yay or paru under sudo — they refuse it and build as an unprivileged user by design. And exporting the variable in your own shell is not enough either: the helper invokes its own `sudo pacman -Syu`, and sudo's default `env_reset` strips the variable before pacman sees it, so the guard still aborts. Split the upgrade instead — `-Sua` is AUR-only and never triggers the guard:

```bash
# repo half (guard bypassed explicitly)
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
# AUR half (no guard involved)
yay -Sua            # or: paru -Sua
```

If you really want `yay -Syu` in one shot, the variable has to survive the helper's internal sudo. Either pass it through sudo explicitly:

```bash
OMARCHY_ALLOW_DIRECT_PACMAN=1 yay -Syu \
  --sudoflags "--preserve-env=OMARCHY_ALLOW_DIRECT_PACMAN"
```

or whitelist it once in sudoers (`sudo visudo -f /etc/sudoers.d/omarchy-direct-pacman`):

```
Defaults env_keep += "OMARCHY_ALLOW_DIRECT_PACMAN"
```

```bash
# After ANY bypass, run the per-user migrations the guard exists to protect.
# Omarchy otherwise only nudges you at your next graphical login.
omarchy-migrate --pending    # prints pending names, exits 0 if any are pending
omarchy-migrate
omarchy-hook post-update     # runs your ~/.config/omarchy/hooks/post-update{,.d}
```

If you genuinely want the guard off permanently, do not delete the hook — it is package-owned and returns on the next `omarchy` upgrade. Shadow it from the higher-priority hook directory instead, which `alpm-hooks(5)` documents as the supported way ("Hooks may be disabled by overriding them with a symlink to /dev/null"):

```bash
sudo mkdir -p /etc/pacman.d/hooks
sudo ln -sf /dev/null /etc/pacman.d/hooks/00-omarchy-update-guard.hook
# undo:
sudo rm /etc/pacman.d/hooks/00-omarchy-update-guard.hook
```

**Verify.** `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu` runs the transaction; `omarchy-migrate --pending` prints nothing and exits non-zero once migrations are applied.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-pacman-guard> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/libalpm/hooks/00-omarchy-update-guard.hook> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/update-process.md> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-migrate> · <https://man.archlinux.org/man/alpm-hooks.5.en> · <https://learn.omacom.io/2/the-omarchy-manual/68/updates>

---

## Repair the menu and keybindings after updating with pacman instead of omarchy

`pacman-syu-instead-of-omarchy-update` · severity: **medium** · frequency: **very-common** · applies to: `omarchy`

**Symptom.** User updates with `sudo pacman -Syu` or `yay -Syu` out of habit. Packages update fine, but afterwards the Omarchy menu has missing/renamed entries, keybindings from the release notes don't exist, themes look wrong, or the top bar shows an "emergency mode" banner. Re-running `pacman -Syu` says everything is up to date.

**Cause.** Omarchy 4 is installed as pacman packages (`omarchy`, `omarchy-settings`) at `/usr/share/omarchy`, and ships numbered migration scripts in `/usr/share/omarchy/migrations` with applied-state in `~/.local/state/omarchy/migrations`. `omarchy update` runs those migrations after the package upgrade; a bare `pacman -Syu` / `yay -Syu` upgrades packages and never runs them, so config and packages drift apart. On current Omarchy this is largely prevented rather than merely warned about: `bin/omarchy-update-pacman-guard` is an ALPM pre-transaction hook that aborts any direct `-S` + `-u` transaction.

> **Audit corrected this record.** The underlying advice (always update through Omarchy) is correct and manual/30-updates.md warns about it. But three things are wrong for current Omarchy. (1) The symptom is largely obsolete: bin/omarchy-update-pacman-guard is an ALPM pre-transaction hook that ABORTS any direct -S+-u transaction with a 'Woah partner...' message, so users can no longer silently drift this way. (2) The cause is obsolete: Omarchy 4 is installed as pacman packages (omarchy, omarchy-settings) at /usr/share/omarchy, not a git checkout at ~/.local/share/omarchy; migrations live in /usr/share/omarchy/migrations with state in ~/.local/state/omarchy/migrations. (3) Menu keybind is Super+Space, not Super+Alt+Space. Also, `omarchy-refresh-hyprland` is presented as a harmless repair but it OVERWRITES every user hypr config (monitors, bindings, input, looknfeel, autostart) with defaults - that needs a warning.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy-refresh-hyprland` OVERWRITES ~/.config/hypr/{hyprland,autostart,bindings,input,looknfeel,monitors}.conf with stock defaults. Back them up first: `cp -r ~/.config/hypr ~/.config/hypr.bak`.

**Fix.**

Always update through Omarchy so migrations and config updates run alongside packages:

```bash
omarchy update
```

or from the menu: `Super + Space` > **Update** > **Omarchy**.

Note that on current Omarchy you generally cannot cause this drift any more - a direct `pacman -Syu` / `yay -Syu` is stopped by Omarchy's ALPM guard, which prints a message pointing you back at `omarchy update`. If you deliberately bypassed it with `OMARCHY_ALLOW_DIRECT_PACMAN=1`, just run the update once and pending migrations replay in order:

```bash
omarchy update
```

Check what is actually still pending before assuming config is the problem:

```bash
omarchy-migrate --pending
```

Only if the Hyprland configs are genuinely mangled, reset them - but be aware this is destructive:

```bash
# WARNING: overwrites ~/.config/hypr/{hyprland,monitors,input,bindings,looknfeel,autostart}.lua
# with Omarchy defaults. Timestamped .bak copies are left beside each file.
omarchy-refresh-hyprland
```

To reset a single file instead of all of them:

```bash
omarchy-refresh-config hypr/bindings.lua
```

(Menu equivalent: **Update** > **Config**.)

**Verify.** `omarchy update` reports no pending migrations on a second run, and the new keybindings/menu entries from the release notes are present.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/68/updates> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update> · <https://github.com/basecamp/omarchy/tree/master/migrations> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-refresh-hyprland>

---

## Fix Chromium playing video as a black rectangle after an update

`chromium-video-black-after-update` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `hyprland`, `intel`, `nvidia`, `omarchy`, `wayland`

**Symptom.** After an Omarchy update, videos in Chromium/Brave/Chrome play as a black rectangle (audio still works), or the browser lags, flickers and jitters badly. The browser log is full of:

```
SharedImageManager::ProduceSkia: Trying to produce a Skia representation from an incompatible backing
eglCreateImage failed with 0x00003009
OzoneImageBacking::ProduceSkiaGanesh failed to create GL representation
```

**Cause.** Chromium defaults to ANGLE (egl-angle) on Wayland. A Mesa/Wayland stack bump shipped by an Omarchy update broke the ANGLE -> EGLImage -> DMA-BUF video path on some GPU/driver combinations, so the compositor gets an unusable buffer.

> **Audit corrected this record.** The symptom and ANGLE diagnosis are plausible, but the fix flag does not exist and the procedure will break the user's browser. Verified against chromium/chromium ui/gl/gl_switches.cc: the only valid --use-gl values are egl, angle, mock, stub, disabled. There is no 'desktop' value - it was removed. Forcing native GL instead of ANGLE's default backend is `--use-angle=gl` (valid ANGLE names include default, gl, gl-egl, gles, vulkan, swiftshader). `--disable-features=UseChromeOSDirectVideoDecoder` is a ChromeOS-only feature flag, is inert on Linux, and does not disable GPU rasterization as claimed. Most damaging: Omarchy SHIPS a populated ~/.config/chromium-flags.conf containing --ozone-platform=wayland, --ozone-platform-hint=wayland, --password-store=gnome-libsecret and --load-extension=... . Telling users to 'create the file ... one flag per line' invites them to overwrite it, which drops Chromium out of Wayland/ozone and breaks keyring-backed password storage.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Force Chromium off ANGLE's default backend onto native desktop GL. The flag is `--use-angle=gl` - `--use-gl=desktop` was removed from Chromium and is silently ignored (the only valid `--use-gl` values today are `egl`, `angle`, `mock`, `stub`, `disabled`).

Omarchy already ships a populated flags file, so **append** to it - never overwrite it. Overwriting drops `--ozone-platform=wayland` and `--password-store=gnome-libsecret` and will break Wayland rendering and your saved passwords.

For Chromium:

```bash
cat ~/.config/chromium-flags.conf                    # look before you touch it
echo '--use-angle=gl' >> ~/.config/chromium-flags.conf
```

For Brave:

```bash
echo '--use-angle=gl' >> ~/.config/brave-flags.conf
```

Fully quit and relaunch - a background process keeps the old flags:

```bash
pkill -f chromium; pkill -f brave
```

Confirm what actually took effect by visiting `chrome://gpu` and checking the ANGLE line.

If `gl` does not help, try the Vulkan backend instead:

```bash
echo '--use-angle=vulkan' >> ~/.config/chromium-flags.conf
```

If you already clobbered the flags file, restore Omarchy's defaults:

```bash
omarchy-refresh-chromium
```

**Verify.** Open `chrome://gpu` — the GL renderer no longer reports ANGLE — and a YouTube video renders instead of showing black.

Sources: <https://github.com/basecamp/omarchy/issues/3891> · <https://github.com/basecamp/omarchy/issues/3899>

---

## Get back to the stable update channel after dev broke the desktop

`dev-channel-broke-my-desktop` · severity: **medium** · frequency: **common** · applies to: `omarchy`

**Symptom.** User switched to the `dev` or `edge` update channel (or a feature branch) to try something new, and now every `omarchy update` pulls half-finished code — the shell crashes, the menu is broken, or migrations fail. They want back on stable but don't know how.

**Cause.** Omarchy has four update channels: **stable** (default, packages roughly a month behind), **edge** (latest packages, stable Omarchy code), **rc** (pre-release validation) and **dev** (cutting-edge code *and* packages). `dev` is explicitly for experienced users and regularly ships breakage. `omarchy-channel-set` is the single entry point - there is no `omarchy-branch-set`, and the channel and the source checkout are not set independently: `omarchy-channel-set` moves the package repo and the dev checkout together, and on `dev` that checkout is at `~/omarchy`.

> **Audit corrected this record.** The four channels are real and confirmed by manual/30-updates.md, and `omarchy-channel-set` is correct. But most of the commands are wrong for current Omarchy. `omarchy-branch-set` DOES NOT EXIST - there is no such file in bin/ (only omarchy-channel-set, omarchy-channel-current, omarchy-version-branch, omarchy-version-channel). Channel and branch are no longer set independently: omarchy-channel-set handles the package repo and the dev checkout together. The dev checkout is at `~/omarchy`, not `~/.local/share/omarchy` - the manual says 'the dev channel, which links Omarchy directly to a git checkout of the source code in ~/omarchy' - so every `git -C ~/.local/share/omarchy ...` command targets a directory that does not exist on Omarchy 4. `omarchy-channel-set stable` already ends by running `omarchy-update -y`, so the trailing `omarchy update` is redundant. `sudo pacman -Syyuu` is blocked by the update guard, and the downgrade is already performed for you by omarchy-refresh-pacman. Finally, channel repos are configured from default/pacman/pacman-{stable,rc,edge}.conf, so grepping /etc/pacman.d/mirrorlist is the wrong file.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Downgrading from edge/dev to stable with `pacman -Syyuu` rolls packages backwards; a downgraded kernel plus an already-rebuilt DKMS module can break the next boot. Take a snapshot (`omarchy-snapshot create`) before switching channels.

**Fix.**

Check what you are actually on first:

```bash
omarchy-channel-current
omarchy-version-channel
```

Switch back through the menu - `Super + Space` > **Setup** > **Channel** > *stable* - or from a terminal. One command does everything: it repoints the pacman channel, swaps the omarchy-dev packages back to the stable ones, unlinks any dev checkout, and finishes by running the update itself:

```bash
omarchy-channel-set stable
```

Do not look for `omarchy-branch-set` - it no longer exists. Channel and branch are not set independently any more; `omarchy-channel-set` handles both.

Moving from dev/edge back to stable means *downgrading* packages. `omarchy-channel-set` already does this for you via `omarchy-refresh-pacman`, which runs a full `pacman -Syyuu` with the update guard bypassed. Do not run a bare `sudo pacman -Syyuu` yourself - Omarchy's ALPM guard will abort it.

If you had actually been on the **dev** channel, the source checkout lives at `~/omarchy` (not `~/.local/share/omarchy`). If local edits there are getting in the way, deal with them before switching:

```bash
git -C ~/omarchy status
git -C ~/omarchy stash
```

Switching to stable unlinks that checkout automatically (`omarchy-dev-unlink`), leaving OMARCHY_PATH back at /usr/share/omarchy. A reboot is flagged as required - take it.

If the system is still inconsistent afterwards, the documented reset reinstalls the default packages, forces stable, downgrades anything too new, and rewrites every config file:

```bash
omarchy reinstall
```

**Verify.** `git -C ~/.local/share/omarchy branch --show-current` shows the stable branch, `/etc/pacman.d/mirrorlist` points at the stable Omarchy mirror, and `omarchy update` completes cleanly.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/68/updates> · <https://github.com/basecamp/omarchy/tree/master/bin> · <https://raw.githubusercontent.com/basecamp/omarchy/master/install/preflight/pacman.sh>

---

## Set up enough swap for hibernation to actually resume

`hibernation-fails-no-swap-space` · severity: **medium** · frequency: **common** · applies to: `arch`, `laptop`, `omarchy`

**Symptom.** Enabling hibernation from *Setup > System Sleep* fails, or hibernate is offered under `Super + Esc` but the machine just powers off and cold-boots instead of restoring. On some laptops the hibernate image creation aborts partway.

**Cause.** Hibernation writes the entire contents of RAM to disk. Omarchy's setup creates a `/swap` btrfs subvolume sized to physical RAM; if the drive doesn't have that much free space the swapfile can't be created or is too small, and the resume image never gets written. Firmware/ACPI quirks on some laptops also break the default `HibernateMode`.

> **Audit corrected this record.** Largely accurate and the tooling checks out - bin/omarchy-hibernation-setup and bin/omarchy-hibernation-remove both exist, it does create a `/swap` btrfs subvolume with a swapfile sized to MemTotal via `btrfs filesystem mkswapfile -s`, and it writes resume params to the kernel cmdline through /etc/limine-entry-tool.d/resume.conf, so the `/proc/cmdline | grep resume` check is valid. One genuinely risky instruction: `sudo systemctl restart systemd-logind` is unnecessary here (systemd-sleep reads /etc/systemd/sleep.conf at hibernate time, not from logind) and restarting logind can tear down the running graphical session and any active user sessions. Also /etc/systemd/sleep.conf is a package-managed file - a drop-in under /etc/systemd/sleep.conf.d/ is the correct place for the override. Minor: the menu is reached via Super + Space.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The swap subvolume consumes RAM-sized disk space permanently (32 GB RAM = 32 GB gone). A wrong `resume_offset` in the kernel cmdline causes a failed resume that discards the session — save work before testing.

**Fix.**

Check RAM and free space first - you need at least RAM-size free:

```bash
free -h
btrfs filesystem usage /
```

Free space, then re-run the setup (menu: `Super + Space` > **Setup** > **System Sleep**):

```bash
omarchy-hibernation-setup
```

Confirm the swapfile and resume offset are wired up. Omarchy creates a `/swap` btrfs subvolume with a swapfile sized to physical RAM, adds `HOOKS+=(resume)` via /etc/mkinitcpio.conf.d/omarchy_resume.conf, and appends the resume parameters to the kernel cmdline via /etc/limine-entry-tool.d/resume.conf:

```bash
swapon --show
cat /proc/cmdline | tr ' ' '\n' | grep -E 'resume'
# expect resume=UUID=... and resume_offset=...
cat /etc/limine-entry-tool.d/resume.conf
```

If the offset came out empty, re-running `omarchy-hibernation-setup` repairs it in place.

If image creation aborts on your laptop, switch hibernate to shutdown mode. Use a drop-in rather than editing the packaged /etc/systemd/sleep.conf:

```bash
sudo mkdir -p /etc/systemd/sleep.conf.d
printf '[Sleep]\nHibernateMode=shutdown\n' | sudo tee /etc/systemd/sleep.conf.d/omarchy-hibernate.conf
```

Then just try it - do NOT restart systemd-logind, which will kill your graphical session and is not needed (systemd-sleep reads this config at hibernate time):

```bash
sudo systemctl hibernate
```

To back it all out:

```bash
omarchy-hibernation-remove
```

**Verify.** `swapon --show` lists a swapfile at least as large as RAM, and `sudo systemctl hibernate` powers off and then restores the exact session on next power-on.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/103/system-sleep> · <https://github.com/basecamp/omarchy/tree/master/bin> · <https://github.com/basecamp/omarchy/issues?q=is%3Aissue+suspend+OR+sleep+black+screen+wake>

---

## Make Omarchy usable in a VM without GPU acceleration

`omarchy-in-vm-no-gpu-acceleration` · severity: **medium** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`, `wayland`

**Symptom.** Omarchy installed in VirtualBox / VMware / a generic QEMU VM boots to a black screen, or the desktop appears but is unusably slow — dragging a window takes seconds, animations stutter, video is a slideshow. Sometimes Hyprland exits immediately with an EGL/DRM error.

**Cause.** Hyprland requires a DRM device with working GL/EGL. Many hypervisor display adapters expose no usable 3D acceleration, so either no DRM node is found (black screen) or everything falls back to software rendering (slow). Note that Hyprland is no longer a wlroots compositor - it uses its own Aquamarine backend - so the old wlroots software-rendering escape hatches do not exist, and the compositor reads its environment at process start, before any config is applied, so a variable set from the Hyprland config cannot affect its own startup. Omarchy's own docs acknowledge VirtualBox works but "performance probably won't be great".

> **Audit corrected this record.** The problem is real and manual/49-omarchy-on.md acknowledges VirtualBox and VMware with the 'performance probably won't be great' caveat. But the technical framing and the fallback are obsolete. Hyprland is no longer a wlroots compositor - it moved to its own Aquamarine backend - and `WLR_RENDERER_ALLOW_SOFTWARE` is a dead wlroots variable: a code search across the entire hyprwm org returns zero occurrences of it (and zero for LIBGL_ALWAYS_SOFTWARE). Beyond being obsolete, the delivery mechanism cannot work: `env`/`hl.env` in monitors.conf/monitors.lua exports variables to clients Hyprland launches, but the compositor's own renderer reads its environment at process start, before the config is applied - so setting a software-rendering variable there cannot affect Hyprland's own startup. It must be set in the session environment before Hyprland launches. Minor: `glxinfo -B` needs mesa-utils (not mentioned), and `journalctl --user -b -u hyprland` matches nothing because under uwsm the unit is wayland-wm@hyprland.service.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `LIBGL_ALWAYS_SOFTWARE=1` disables all GPU acceleration system-wide for the session — remove it once real acceleration works, or video playback and browsers will stay unusable.

**Fix.**

Confirm what the guest actually has. `glxinfo` comes from `mesa-utils`, and under uwsm the compositor's unit is `wayland-wm@hyprland.service`, not `hyprland`:

```bash
ls -l /dev/dri/
sudo pacman -S --needed mesa-utils
glxinfo -B | grep -E 'renderer|OpenGL version'
journalctl --user -b -u wayland-wm@hyprland.service --no-pager | tail -40
```

If `/dev/dri/` is empty there is no DRM node at all and no environment variable will help - you must give the VM a virtual GPU.

**QEMU/KVM (best option):** give the guest virtio-gpu with venus/virgl and enough VRAM. In virt-manager set Video model to **Virtio** and tick **3D acceleration**, and set Display to **SPICE** with OpenGL enabled. In the guest:

```bash
sudo pacman -S --needed mesa vulkan-virtio qemu-guest-agent spice-vdagent
sudo systemctl enable --now qemu-guest-agent spice-vdagentd
```

**VirtualBox / VMware:** enable EFI, allocate 128 MB video memory, enable 3D acceleration, and install guest additions.

If you need software rendering, note that `WLR_RENDERER_ALLOW_SOFTWARE` does nothing - Hyprland dropped wlroots for its own Aquamarine backend and never reads that variable. Use the Mesa variable, and set it in the **session environment before Hyprland starts**, not in monitors.lua (variables set there go to the apps Hyprland launches, not to the compositor itself):

```bash
mkdir -p ~/.config/uwsm
echo 'export LIBGL_ALWAYS_SOFTWARE=1' >> ~/.config/uwsm/env
```

Then log out and back in. Expect llvmpipe-class performance.

Set a fixed resolution rather than `preferred` - virtual displays often report a useless preferred mode. In `~/.config/hypr/monitors.lua`:

```lua
hl.monitor({ output = "", mode = "1920x1080@60", position = "auto", scale = 1 })
```

**Verify.** `ls /dev/dri/` shows a `card0`/`renderD128` node, `hyprctl monitors` lists a monitor at the expected resolution, and window dragging is smooth.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/79/omarchy-on> · <https://github.com/basecamp/omarchy/discussions>

---

## Understand why a snapshot rollback leaves your home directory broken

`snapshot-restore-does-not-restore-home` · severity: **medium** · frequency: **common** · applies to: `omarchy`

**Symptom.** User rolls back to a pre-update Limine snapshot to escape a broken update, but the desktop is still broken in the same way — the theme is still wrong, the top bar still misbehaves, the same keybindings are still missing.

**Cause.** Omarchy snapshots cover the root subvolume only. Everything under /home — including ~/.config/hypr, ~/.config/waybar, ~/.config/omarchy — is untouched by a restore. Migrations that rewrote files in ~/.config are therefore still applied after the rollback, so package state and user config are now mismatched in the opposite direction.

> **Audit corrected this record.** The cause is exactly right and confirmed almost verbatim by manual/47-system-snapshots.md ('This will restore your root filesystem, but not your /home ... your ~/.config directory is kept as-is') and by default/snapper/root which sets SUBVOLUME="/". Only the file names are stale: current Omarchy uses Lua Hyprland configs, so `omarchy-refresh-config hypr/bindings.conf` and `hypr/looknfeel.conf` will not resolve - they are now hypr/bindings.lua and hypr/looknfeel.lua. Minor: the manual `cp -r` backup is redundant because omarchy-refresh-config already writes a timestamped .bak beside each file and deletes it again if nothing changed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `omarchy-refresh-config` overwrites the named file with stock defaults with no prompt. Copy ~/.config/hypr aside first.

**Fix.**

After rolling back the system, also reset the user-side config, which the snapshot did not touch. Note that omarchy-refresh-config already makes a timestamped `.bak` of anything it replaces, so an extra manual copy is optional:

```bash
omarchy-refresh-hyprland
```

For individual files, refresh just the one that drifted. Current Omarchy uses Lua configs, not .conf:

```bash
omarchy-refresh-config hypr/bindings.lua
omarchy-refresh-config hypr/looknfeel.lua
omarchy-refresh-config hypr/monitors.lua
omarchy-refresh-config hypr/input.lua
```

If you are on an older Omarchy 3 install these are still `.conf` (hypr/bindings.conf, hypr/looknfeel.conf). Check which you have:

```bash
ls ~/.config/hypr/
```

Because of this root-only split, back up your dotfiles independently of snapshots - keep ~/.config in a git repo or use GNU stow.

**Verify.** `diff -r ~/.config/hypr ~/.local/share/omarchy/config/hypr` shows only your intentional overrides, and the desktop matches the rolled-back version.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/101/system-snapshots> · <https://learn.omacom.io/2/the-omarchy-manual/65/dotfiles> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-refresh-hyprland>

---

## Theme half-applied after a failed update: 'omarchy theme current' says Unknown and the wallpaper symlink dangles

`theme-state-broken-after-failed-update` · severity: **medium** · frequency: **common** · applies to: `omarchy-4`

**Symptom.** After an interrupted `omarchy update` or a theme switch that died partway, the desktop is visually inconsistent: terminal, bar and GTK apps disagree on colors, window borders are the wrong accent, the wallpaper is missing or reverts to the default. Diagnostics:

```
$ omarchy theme current
Unknown
$ omarchy theme bg current
Unknown
$ readlink ~/.local/state/omarchy/current/background
/home/you/.local/state/omarchy/current/theme/backgrounds/1-quattro.jpg
$ readlink -f ~/.local/state/omarchy/current/background
            # resolves to nothing - dangling
```

A git-installed theme can also produce "my theme's terminal colors and window borders are wrong", with this on stderr from the theme set:

```
Ignored in /home/you/.config/omarchy/themes/foo: hyprland.lua alacritty.toml
A theme installed from a git repo cannot supply Lua, a terminal config, or vscode.json.
```

**Cause.** `omarchy-theme-set` stages into `~/.local/state/omarchy/current/next-theme`, then `rm -rf`s `~/.local/state/omarchy/current/theme` and `mv`s the staging dir into place. Interrupted between those two steps, `current/theme` is gone while `current/background` still points inside it — hence the dangling symlink and `theme.name` no longer matching what is on disk. The same end state is reached deliberately when a theme ships no `backgrounds/` directory: the notification says "No background was found for theme" and returns without touching `current/background`, but the previous wallpaper lived inside the directory that was just deleted (issue #7116). Note the path moved in Omarchy 4: the live theme state is `~/.local/state/omarchy/current/`, not `~/.config/omarchy/current/`.

Per-app files (`btop.theme`, `shell.toml`, `hyprland.lua`, `chromium.theme`, `helix.toml`, `icons.theme`…) are rendered from `/usr/share/omarchy/default/themed/*.tpl` **only when the staged theme has a `colors.toml`** — a theme without one leaves those files stale. And a theme cloned by `omarchy theme install <git-url>` has every `*.lua`, `alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf` and `vscode.json` dropped at staging time on purpose (those run code), with the generated template used instead, so it can legitimately look different from the author's screenshots.

> ⚠️ **Risk.** Do not `rm -rf ~/.local/state/omarchy/current` while the shell is running — delete only `next-theme` and re-apply with `omarchy theme set`. Reach for `omarchy-reinstall-configs` only as a last resort: it replays `/etc/skel` over your entire `$HOME` (`cp -af /etc/skel/. ~/`) and overwrites every Omarchy-shipped user config, including your `~/.config/hypr/*.lua` overrides, with no backup. `omarchy theme remove` is an unconditional `rm -rf` of `~/.config/omarchy/themes/<name>` — commit any local edits to that theme first.

**Fix.**

```bash
# 1. See what state it is actually in
ls -l ~/.local/state/omarchy/current/
cat  ~/.local/state/omarchy/current/theme.name
readlink -f ~/.local/state/omarchy/current/background   # empty output = dangling
ls ~/.local/state/omarchy/current/theme/                # colors.toml + generated files

# 2. Clear any half-written staging directory, then re-apply cleanly
rm -rf ~/.local/state/omarchy/current/next-theme
omarchy theme list
omarchy theme set "Tokyo Night"          # any shipped theme rebuilds everything

# 3. Already on the theme you want - just regenerate the per-app files
omarchy-theme-refresh

# 4. Wallpaper only
omarchy theme bg next
omarchy theme bg current

# 5. Half-installed / broken third-party theme
omarchy theme remove <name>
omarchy theme install https://github.com/author/omarchy-<name>-theme.git

# 6. Apps that did not retint (they are restarted in parallel by omarchy-theme-set)
omarchy-restart-terminal
omarchy-restart-hyprctl        # window borders / gradients
omarchy-restart-btop
omarchy-theme-set-gnome        # GTK apps
omarchy-theme-set-browser
```

If a shipped theme still will not render its per-app files, check that `colors.toml` reached the staged theme — without it no template runs at all:

```bash
ls -l ~/.local/state/omarchy/current/theme/colors.toml
```

**Verify.** `omarchy theme current` prints the theme name; `readlink -f ~/.local/state/omarchy/current/background` resolves to a real image file; `ls ~/.local/state/omarchy/current/theme` contains `colors.toml` plus the generated `shell.toml`, `btop.theme`, `hyprland.lua` etc.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-theme-set> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-theme-refresh> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-theme-list> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-theme-remove> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-reinstall-configs> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/theming.md> · <https://github.com/basecamp/omarchy/issues/7116> · <https://github.com/basecamp/omarchy/issues/8262>

---

## Web app launchers open the wrong page or fail after a browser update or default-browser change

`webapp-launchers-broken-after-browser-change` · severity: **medium** · frequency: **common** · applies to: `omarchy-4`

**Symptom.** The Omarchy web-app launchers stop working while their icons stay in the launcher. Super+Shift+A (ChatGPT), Super+Shift+Alt+A (Grok), Super+Shift+X, and `omarchy launch webapp <url>` either do nothing, open the browser on its start page instead of the site, or fail outright with:

```
error: path "--app=https://messenger.com" does not exist!
```

Typically starts right after installing Firefox/Opera and making it default, after removing Chromium, or after a Chromium-family package rename.

**Cause.** Every `.desktop` file written by `omarchy-webapp-install` has `Exec=omarchy-launch-webapp <url>`. `omarchy-launch-webapp` reads `xdg-settings get default-web-browser`, keeps only chromium-family desktop ids (`google-chrome*`, `brave*`, `microsoft-edge*`, `opera*`, `vivaldi*`, `helium*`) and otherwise falls back to a hardcoded `chromium.desktop`, then greps the `Exec=` line out of that desktop file and appends `--app=<url>`:

```bash
exec setsid uwsm-app -- $(sed -n 's/^Exec=\([^ ]*\).*/\1/p' \
  {~/.local,~/.nix-profile,/usr}/share/applications/$browser 2>/dev/null | head -1) --app="$1" "${@:2}"
```

With Firefox default and Chromium uninstalled, `chromium.desktop` does not exist, the command substitution yields an empty binary path, and `uwsm-app` treats `--app=...` as the executable (issue #7034). With Opera default, it *is* whitelisted so the launch "succeeds" — but Opera ignores `--app=`, so the flag is dropped and you get the start page (issue #8298).

> **Audit corrected this record.** Cause is exact. `bin/omarchy-launch-webapp` is reproduced character for character, including the whitelist `google-chrome* | brave* | microsoft-edge* | opera* | vivaldi* | helium*`, the `*) browser="chromium.desktop"` fallback, and the `exec setsid uwsm-app -- $(sed -n 's/^Exec=\([^ ]*\).*/\1/p' {~/.local,~/.nix-profile,/usr}/share/applications/$browser 2>/dev/null | head -1) --app="$1" "${@:2}"` line — so the empty-command-substitution analysis and the Opera-is-whitelisted-but-ignores---app analysis are both right. `bin/omarchy-webapp-install` writes `EXEC_COMMAND="${CUSTOM_EXEC:-omarchy-launch-webapp $APP_URL}"` into `Exec=`, its documented args really are `[name url icon-url-or-name [custom-exec] [mime-types]]` (so the 4th-argument override is correct), and it really does refuse a name containing '/' with that exact rationale. Issues #7034 and #8298 exist with titles matching the two failure modes; omarchy-webapp-remove and omarchy-install-browser exist. The keybinds are right too: `default/hypr/bindings/applications.lua` has `SUPER + SHIFT + A` ChatGPT, `SUPER + SHIFT + ALT + A` Grok, `SUPER + SHIFT + X` X. But that is exactly the defect: those binds do not go through any .desktop file. `default/hypr/helpers.lua` resolves `{ webapp = url }` to the literal string `"omarchy-launch-webapp " .. shell_quote(url)` (or `omarchy-launch-or-focus-webapp` for sole-instance apps), so editing `~/.local/share/applications/ChatGPT.desktop` or reinstalling with a custom exec fixes the launcher icon and leaves Super+Shift+A just as broken. The record leads with the keybinds in its symptom and then offers a fix that cannot address them, so a Firefox/Opera user following it will conclude the fix failed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `omarchy-webapp-remove-all` deletes every web-app launcher in `~/.local/share/applications`, including ones you wrote by hand, and `omarchy-remove-preinstalls` has been reported to remove user-created web apps too (issue #4830) — copy `~/.local/share/applications` somewhere safe first. Never put a `/` in a web app name: it creates a nested `.desktop` path that `omarchy-webapp-remove` cannot delete, leaving an entry stuck in the launcher (issue #7914). Editing a `.desktop` by hand means an `omarchy update` that regenerates preinstalled web apps can overwrite it — keep custom apps under names Omarchy does not ship.

**Fix.**

```bash
# 1. What does Omarchy think your default browser is, and does that file exist?
xdg-settings get default-web-browser
ls /usr/share/applications/chromium.desktop ~/.local/share/applications/chromium.desktop 2>/dev/null

# 2. Simplest fix, and the only one that fixes the keybinds and the launcher
#    icons at once: keep a chromium-family browser installed and default.
omarchy-install-browser                 # or: sudo pacman -S --needed chromium
ls /usr/share/applications | grep -iE 'chromium|brave|vivaldi|edge'
xdg-settings set default-web-browser chromium.desktop     # use the id you saw above
```

To keep Firefox or Opera as your default browser you have to fix **two separate things** — the keybinds and the launcher entries do not share a code path.

**a) The keybinds (Super+Shift+A and friends).** These are Lua, not .desktop files: `{ webapp = "..." }` expands to a direct `omarchy-launch-webapp <url>` call, so no amount of .desktop editing reaches them. Rebind them in `~/.config/hypr/bindings.lua`:

```lua
-- ~/.config/hypr/bindings.lua
hl.unbind("SUPER + SHIFT + A")
o.bind("SUPER + SHIFT + A", "ChatGPT", "firefox --new-window https://chatgpt.com")

hl.unbind("SUPER + SHIFT + ALT + A")
o.bind("SUPER + SHIFT + ALT + A", "Grok", "firefox --new-window https://grok.com")

hl.unbind("SUPER + SHIFT + X")
o.bind("SUPER + SHIFT + X", "X", "firefox --new-window https://x.com/")
```

Or drop the whole preinstalled set in one line and add back only what you want, in `~/.config/hypr/hyprland.lua` **before** `require("default.hypr.omarchy")`:

```lua
omarchy_preinstalled_bindings = false
```

```bash
hyprctl reload
hyprctl binds | grep -A3 ChatGPT
```

**b) The launcher entries.** `omarchy-webapp-install` takes a custom exec as its 4th argument:

```bash
omarchy-webapp-install "ChatGPT" "https://chatgpt.com" \
  "https://chatgpt.com/apple-touch-icon.png" \
  "firefox --new-window https://chatgpt.com"
```

or edit the desktop entry directly:

```ini
# ~/.local/share/applications/ChatGPT.desktop
[Desktop Entry]
Type=Application
Name=ChatGPT
Exec=setsid uwsm-app -- firefox --new-window https://chatgpt.com
Icon=chatgpt
Terminal=false
StartupNotify=true
```

```bash
update-desktop-database ~/.local/share/applications
gtk-update-icon-cache ~/.local/share/icons/hicolor
```

Rebuild a broken or wrongly-named entry from scratch:

```bash
omarchy-webapp-remove "ChatGPT"
omarchy-webapp-install            # interactive; it refuses names containing '/'
```

**Verify.** `omarchy-launch-webapp https://example.com` opens an app-mode window on that URL; `gio launch ~/.local/share/applications/ChatGPT.desktop` opens ChatGPT, not a start page.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-launch-webapp> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-webapp-install> · <https://github.com/basecamp/omarchy/issues/7034> · <https://github.com/basecamp/omarchy/issues/8298> · <https://github.com/basecamp/omarchy/issues/7914> · <https://github.com/basecamp/omarchy/issues/4830>

---

## AUR packages never update because omarchy update skipped the AUR step and still exited green

`aur-updates-silently-skipped` · severity: **medium** · frequency: **occasional** · applies to: `omarchy-3`, `omarchy-4`

**Symptom.** `omarchy update` finishes successfully but AUR/foreign packages never move — for weeks or months. The only sign is one red line buried in the transcript:

```
AUR is unavailable (so skipping updates)
```

Run `yay -Qua` afterwards and it lists updates the run should have installed. Eventually a stale AUR package breaks against a newer library and the user reports it as a broken update, not as a skipped one.

**Cause.** `omarchy-update-aur-pkgs` only runs `yay -Sua` if `omarchy-pkg-aur-accessible` succeeds. That helper is a single probe:

```bash
curl -sf --connect-timeout 30 --retry 3 --retry-delay 3 -A "omarchy-update" \
  "https://aur.archlinux.org/rpc/?v=5&type=info&arg=base"
```

Any AUR outage, DNS failure, captive portal, corporate proxy, VPN/Tailscale split-DNS, or firewall rule blocking that one request makes the whole AUR step a no-op — and the step is not `set -e` guarded, so `omarchy update` still exits 0 and prints its success banner. It probes `aur.archlinux.org` only; `yay` may well be able to reach the package git repos fine.

> ⚠️ **Risk.** Use `yay -Sua` (AUR only), never `yay -Syu` — the latter is a full system upgrade and will be aborted by the Omarchy pacman guard, or, if you bypass the guard, will skip migrations and post-update hooks. If a DKMS AUR package rebuilds here, it builds against the *installed* kernel headers; if you have not rebooted since a kernel upgrade you can end up with a module built for a kernel you are not running. Reboot after DKMS rebuilds.

**Fix.**

```bash
# 1. Reproduce the exact probe the updater uses
curl -sf --connect-timeout 30 -A omarchy-update \
  "https://aur.archlinux.org/rpc/?v=5&type=info&arg=base" >/dev/null \
  && echo AUR-REACHABLE || echo AUR-BLOCKED

# 2. What is actually stale?
pacman -Qem          # foreign (AUR/manually built) packages
yay -Qua             # pending AUR updates

# 3. If the probe fails but the AUR is reachable for you, do the step by hand.
#    -Sua is AUR-only and does NOT trip the Omarchy pacman guard.
yay -Sua --cleanafter

# 4. Chase the network cause
resolvectl query aur.archlinux.org
curl -sI https://aur.archlinux.org | head -1
tailscale status                 # exit node / MagicDNS hijacking resolution?
cat /etc/resolv.conf

# 5. Confirm what the last run actually did
grep -n 'Update AUR packages\|AUR is unavailable' /tmp/omarchy-update.log
```

Make the silence loud — a post-update hook that warns you when foreign packages are behind:

```bash
mkdir -p ~/.config/omarchy/hooks/post-update.d
cat > ~/.config/omarchy/hooks/post-update.d/warn-stale-aur <<'EOF'
#!/bin/bash
pending=$(yay -Qua 2>/dev/null | wc -l)
(( pending > 0 )) && omarchy-notification-send "AUR packages stale" "$pending pending update(s)"
exit 0
EOF
chmod +x ~/.config/omarchy/hooks/post-update.d/warn-stale-aur
```

**Verify.** `yay -Qua` prints nothing after an update, and `/tmp/omarchy-update.log` contains the green "Update AUR packages" heading rather than "AUR is unavailable (so skipping updates)".

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-aur-pkgs> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-pkg-aur-accessible> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/update-process.md>

---

## Update > Firmware finds nothing, or reboots without applying the BIOS/UEFI capsule

`firmware-update-fwupd-not-applied` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `omarchy-4`

**Symptom.** Update > Firmware (or `omarchy-update-firmware`) either reports no updatable devices, or fails with one of:

```
failed to write file /boot/EFI/arch/fw/...: No space left on device
UEFI capsule updates not available or enabled in firmware setup
file system is read-only
```

or — most confusingly — reports success, prompts for a reboot, and after the reboot `fwupdmgr get-devices` still shows the old firmware version. On some laptops the reboot shows a black screen with no messages for minutes.

**Cause.** `omarchy-update-firmware` installs `fwupd` if missing, copies `/usr/lib/fwupd/efi/fwupdx64.efi` to `/boot/EFI/arch/fwupdx64.efi` when booted UEFI, then runs `fwupdmgr refresh --force` and `sudo fwupdmgr update`. Peripheral firmware (docks, SSDs, mice, Thunderbolt) is applied live. BIOS/UEFI firmware is **not**: fwupd stages a capsule on the ESP and the firmware applies it during the next boot. That staging silently fails or is ignored when the ESP is small or full, when the directory is `efi/` rather than uppercase `EFI/`, when `/boot` is a bind mount (fwupd deduces the wrong mount point and reports a misleading read-only error), when efivars are unavailable, or when the firmware's boot order is locked so the capsule loader never runs — the classic "no error but no upgrade on reboot".

> **Audit corrected this record.** Cause is accurate against `bin/omarchy-update-firmware`, which is exactly: install fwupd if `omarchy-cmd-missing fwupdmgr`, then when `/sys/firmware/efi` exists `sudo install -D /usr/lib/fwupd/efi/fwupdx64.efi /boot/EFI/arch/fwupdx64.efi`, then `fwupdmgr refresh --force` and `sudo fwupdmgr update`. Every failure mode is corroborated by ArchWiki's Fwupd page: the uppercase-EFI warning verbatim ("The EFI directory must be in all upper-case; if you used lower-case, fwupd may detect the esp as esp/efi/"), the bind-mount trap verbatim ("deduces the wrong mount point if bind is used to mount the EFI system partition to /boot... results in a (misleading) file system is read-only error"), "In BIOS settings changing the boot order must be allowed" as the cause of a silent no-op, and the stuck/black reboot. The Secure Boot block is quoted correctly too: `sbctl sign -s -o /usr/lib/fwupd/efi/fwupdx64.efi.signed /usr/lib/fwupd/efi/fwupdx64.efi`, and `[uefi_capsule] DisableShimForSecureBoot=true` is the current fwupd-1.9+ location in /etc/fwupd/fwupd.conf (the wiki notes the pre-1.9 uefi_capsule.conf path). Two concrete defects. (1) `sudo tee -a /etc/fwupd/fwupd.conf` appends a second `[uefi_capsule]` group to a file that already ships that section — the wiki presents this as a config-file edit, not an append, and duplicating a group in a GKeyFile is at best undefined and at worst leaves the key silently inert, which is indistinguishable from the very symptom the record is diagnosing. Edit the existing section. (2) `sudo fwupdmgr update <update_ID>` is not a real argument: `fwupdmgr update` takes a DEVICE-ID or GUID from `get-devices`/`get-updates`; `get-history` shows what was attempted, not ids to feed back to update. The record also omits `EspLocation`, which the wiki gives as the fix for the "ESP not detected" case it raises in its own cause.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never power-cycle, force-reset or unplug the machine during a firmware flash, even if the screen stays black for several minutes — that is how a board gets bricked. Run it only on AC power with a charged battery. A UEFI firmware update can discard existing NVRAM boot entries: after a successful BIOS update be ready to recreate one, e.g. `sudo efibootmgr --create --disk /dev/nvme0n1 --part 1 --label Omarchy --loader '\EFI\Linux\omarchy_linux.efi'`, or boot the removable `/EFI/BOOT/BOOTX64.EFI` fallback. This is not part of the normal `omarchy update` pipeline and should not be run casually.

**Fix.**

```bash
# 1. Preconditions
[ -d /sys/firmware/efi ] && echo "UEFI OK"      # nothing works in BIOS/CSM mode
findmnt /boot                                    # ESP must actually be mounted
df -h /boot                                      # capsules need tens of MB free
ls -d /boot/EFI                                  # must be UPPERCASE 'EFI'

# 2. Free space on a full ESP before anything else
sudo du -xhd2 /boot | sort -h | tail

# 3. Drive it step by step instead of through the menu
sudo systemctl restart fwupd.service
fwupdmgr get-devices
fwupdmgr refresh --force
fwupdmgr get-updates
sudo fwupdmgr update            # reboot when prompted; the screen may stay black for minutes

# 4. Nothing changed after the reboot - was it applied, or never run?
fwupdmgr get-history            # what was attempted and its result
fwupdmgr get-devices            # copy the Device ID of the device you want
sudo fwupdmgr update <DEVICE-ID>   # apply one device at a time
```

In the firmware setup, enable "allow boot order change" / disable "boot order lock" — a locked boot order is the standard reason the capsule silently never runs.

If fwupd cannot find the ESP (or picks one on another disk), pin it in the `[uefi_capsule]` section of `/etc/fwupd/fwupd.conf`:

```ini
[uefi_capsule]
EspLocation=/boot
```

On Secure Boot systems fwupd chainloads through shim; with your own keys, sign it and tell fwupd to skip shim:

```bash
sudo sbctl sign -s -o /usr/lib/fwupd/efi/fwupdx64.efi.signed /usr/lib/fwupd/efi/fwupdx64.efi
```

Then **edit the `[uefi_capsule]` section that already exists** in `/etc/fwupd/fwupd.conf` — do not append a second copy of the section header, or the key may never be read:

```bash
sudo grep -n '\[uefi_capsule\]\|DisableShimForSecureBoot' /etc/fwupd/fwupd.conf
sudoedit /etc/fwupd/fwupd.conf
#   under the existing [uefi_capsule] section, set (uncommenting if present):
#       DisableShimForSecureBoot=true
sudo systemctl restart fwupd.service
```

(On installs predating fwupd 1.9 this option lives in `/etc/fwupd/uefi_capsule.conf` instead.)

**Verify.** `fwupdmgr get-devices` shows the new version string for the device; `fwupdmgr get-history` lists the update with `Status: Success`.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-firmware> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/omarchy/omarchy-menu.jsonc> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/update-process.md> · <https://wiki.archlinux.org/title/Fwupd>

---

## Recover logins after an update reset the keyring

`keyring-reset-after-update-logins-cleared` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`, `wayland`

**Symptom.** After an `omarchy update` and reboot, all browser login sessions are gone, `gh auth status` says not logged in, and a dialog asks the user to *create a new keyring*. Looking in `~/.local/share/keyrings` shows a freshly written `default` file and a new `Default_Keyring_1.keyring` next to the older keyring files.

**Cause.** gnome-keyring's `default` pointer file was rewritten during the update/session change, so the daemon created and selected a brand-new empty keyring instead of unlocking the existing one. The old secrets are still on disk — they're just no longer the default.

> **Audit corrected this record.** The mechanism (gnome-keyring's `default` pointer file selecting the wrong keyring) is real, and 'do NOT delete anything' is good advice. But the key value is wrong for Omarchy. Verified in install/user/default-keyring.sh: Omarchy creates `~/.local/share/keyrings/Default_keyring.keyring` and writes `Default_keyring` (with a trailing newline) into the `default` file. It is deliberately a passwordless keyring - install/login/sddm.sh strips the pam_gnome_keyring lines from /etc/pam.d/sddm specifically to 'prevent password-based SDDM logins from creating an encrypted login keyring that conflicts with Omarchy's passwordless default keyring behavior'. So pointing `default` at `login` is exactly the keyring Omarchy avoids creating, and on most Omarchy machines no `login` keyring exists at all - the fix would leave the user worse off. Also `systemctl --user restart gnome-keyring-daemon.service` is not how gnome-keyring runs here; the pkill fallback is the real path.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never delete files in ~/.local/share/keyrings — the old secrets are unrecoverable without them. Always copy `default` aside before editing.

**Fix.**

Do NOT delete anything. List what is actually there first:

```bash
ls -la ~/.local/share/keyrings/
cat ~/.local/share/keyrings/default
```

The `default` file contains a bare keyring name with no `.keyring` suffix. On Omarchy the correct value is **`Default_keyring`** (matching `Default_keyring.keyring`) - not `login`. Omarchy deliberately uses a passwordless default keyring and strips pam_gnome_keyring from /etc/pam.d/sddm, so a `login` keyring usually does not exist on these systems.

Pick whichever keyring file actually holds your secrets - check sizes and dates in the listing above - and point `default` at its name minus the `.keyring` suffix:

```bash
cp ~/.local/share/keyrings/default ~/.local/share/keyrings/default.bak
printf 'Default_keyring\n' > ~/.local/share/keyrings/default
```

Upstream writes that value with a trailing newline, so keep the `\n`.

Restart the daemon, then log out and back in:

```bash
pkill -f gnome-keyring-daemon
```

Inspect and merge with Seahorse if the names are ambiguous:

```bash
sudo pacman -S --needed seahorse
seahorse
```

If the keyring files themselves are gone rather than just mis-pointed, recreate Omarchy's default:

```bash
bash /usr/share/omarchy/install/user/default-keyring.sh
```

Once the right keyring is default again, browser sessions and `gh auth` come back on next login. Re-authenticate anything still missing with `gh auth login`.

**Verify.** `cat ~/.local/share/keyrings/default` names your original keyring, `secret-tool search --all service gh` returns entries, and the browser no longer prompts to create a keyring.

Sources: <https://github.com/basecamp/omarchy/issues/5105>

---

## 'An Omarchy update is already running' when nothing is running (leaked update lock fd)

`stale-omarchy-update-lock` · severity: **medium** · frequency: **occasional** · applies to: `omarchy-4`

**Symptom.** Every `omarchy update` exits instantly with:

```
An Omarchy update is already running.
```

Nothing is updating, `ps` shows no `omarchy-update` or `pacman`, a reboot fixes it for exactly one run and then it comes back after the next update. The pending-migrations notification at login also stops appearing.

**Cause.** `omarchy-update-lock run` opens `${XDG_RUNTIME_DIR:-/tmp}/omarchy-update.lock`, takes a non-blocking `flock`, exports the descriptor number and `exec`s the update — without `FD_CLOEXEC`. Every child of the update therefore inherits the locked descriptor. Any process started during the update that daemonises and does not close inherited fds keeps the flock alive after the update itself is long gone. The reported case is `adb` started by a `flutter-beta` AUR rebuild during `omarchy-update-aur-pkgs` (`yay -Sua`), which reparents onto the user's systemd and holds `/run/user/1000/omarchy-update.lock` indefinitely (issue #8077). The same happens with any sticky helper an AUR build leaves behind, and after an update that was killed mid-run. `omarchy-migrate-notify` reads the same lock to decide whether to stay quiet, so a stale lock also suppresses the login prompt to run pending migrations.

> ⚠️ **Risk.** Only remove the lock file after `pgrep -af 'omarchy-update|/usr/bin/pacman|yay'` returns nothing. Deleting it while a real update is mid-transaction lets a second pacman run start alongside the first — concurrent writers to `/var/lib/pacman` can corrupt the local package database, which is far worse than the blocked update. Note the lock lives in `$XDG_RUNTIME_DIR` (tmpfs), so it never survives a reboot; if it comes back after a reboot, a process is re-leaking it and you need to find that process, not keep deleting the file.

**Fix.**

```bash
# 1. Find the actual holder
fuser -v "${XDG_RUNTIME_DIR:-/tmp}/omarchy-update.lock"
# or
sudo lsof "${XDG_RUNTIME_DIR:-/tmp}/omarchy-update.lock"

# Example output:
#   /run/user/1000/omarchy-update.lock:
#                        you  139567 F.... adb

# 2. Prove no real update is in flight before touching anything
pgrep -af 'omarchy-update|omarchy-migrate|/usr/bin/pacman|yay'

# 3a. Kill the leftover holder (preferred - it also stops it re-leaking)
adb kill-server            # for the adb case
kill 139567                # generic

# 3b. Or drop the lock file; the next open creates a fresh inode
rm -f "${XDG_RUNTIME_DIR:-/tmp}/omarchy-update.lock"

# 4. Resume, then apply any migrations the suppressed notification hid from you
omarchy update
omarchy-migrate --pending && omarchy-migrate
```

To stop it recurring, keep sticky build daemons out of the update: `adb kill-server` before running `omarchy update`, or update those AUR packages separately with `yay -Sua` outside the Omarchy pipeline.

**Verify.** `fuser -v "${XDG_RUNTIME_DIR:-/tmp}/omarchy-update.lock"` prints nothing, and `omarchy update` reaches its confirmation prompt.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update-lock> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-update> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/docs/update-process.md> · <https://github.com/basecamp/omarchy/issues/8077>

---

## Understand and restore a Caps Lock key that appears dead

`caps-lock-does-nothing` · severity: **low** · frequency: **very-common** · applies to: `hyprland`, `omarchy`, `wayland`

**Symptom.** Caps Lock appears dead — pressing it doesn't toggle capitals, and the LED doesn't light. Users assume the keyboard or the install is broken.

**Cause.** Omarchy remaps Caps Lock to the XCompose key by default (`kb_options = compose:caps`), so it can be used for emoji and special-character sequences. It is intentionally no longer Caps Lock.

> **Audit corrected this record.** Cause is exactly right and confirmed - default/hypr/input.lua sets kb_options with a comment reading 'CapsLock is the compose key, so Caps Lock itself has to live somewhere else', and manual/45-troubleshooting.md documents the same remap. Only the config format is stale: current Omarchy uses ~/.config/hypr/input.lua with an hl.config() call, not the `input { }` .conf block. One substantive omission: the actual default is `compose:caps,shift:both_capslock_cancel`, so replacing kb_options with just `compose:ralt` silently drops the shift:both_capslock_cancel behavior. Also worth noting Omarchy appends `grp:alts_toggle` automatically when multiple layouts are configured.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Move Compose to another key and give Caps Lock back. Edit `~/.config/hypr/input.lua`:

```lua
hl.config({
  input = {
    kb_options = "compose:ralt",
  },
})
```

Note that Omarchy's real default is `compose:caps,shift:both_capslock_cancel` - if you want to keep the second behavior (both Shift keys cancel Caps Lock), carry it over:

```lua
hl.config({
  input = {
    kb_options = "compose:ralt,shift:both_capslock_cancel",
  },
})
```

To drop Compose entirely, set an empty value:

```lua
hl.config({
  input = {
    kb_options = "",
  },
})
```

The same file is where multi-layout switching lives:

```lua
hl.config({
  input = {
    kb_layout = "us,fr",
    kb_options = "compose:ralt,grp:alts_toggle",
  },
})
```

Apply it:

```bash
hyprctl reload
```

On an older Omarchy 3 install this is `~/.config/hypr/input.conf` using the `input { kb_options = compose:ralt }` block syntax.

**Verify.** `hyprctl getoption input:kb_options` shows the new value and Caps Lock toggles capitals again.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting> · <https://learn.omacom.io/2/the-omarchy-manual/67/faq>

---

## Fix every application being enormous on first boot

`everything-too-big-gdk-scale` · severity: **low** · frequency: **very-common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Right after first boot every application is enormous — text, buttons, the file manager, Spotify. Windows spill off the screen. Users on 1080p/1440p monitors say "Omarchy looks like it's zoomed to 200%".

**Cause.** Omarchy defaults `GDK_SCALE` to 2 so 4K panels are legible out of the box, and on a standard-DPI display that doubles every GTK app. Only `GDK_SCALE` causes the oversizing - `config/hypr/monitors.lua` leaves the Hyprland monitor scale at `"auto"`, not 2. The knob is `local omarchy_gdk_scale = 2` in that same file. GTK honours only whole numbers, so a fractional `GDK_SCALE` is parsed as an integer and silently becomes 1.

> **Audit corrected this record.** Real problem, and manual/45-troubleshooting.md confirms it - but nearly every specific is wrong. Verified against config/hypr/monitors.lua: the monitor scale default is `"auto"`, NOT 2, so the claim that 'Hyprland's monitor scale' is 2 is false; only GDK_SCALE=2 causes the oversizing. The file is monitors.lua, not monitors.conf, and the knob is `local omarchy_gdk_scale = 2`. Critically, `env = GDK_SCALE,1.75` is invalid - upstream's own comment in monitors.lua states 'GTK only honors whole numbers, so use the nearest integer to the monitor scale.' A fractional GDK_SCALE is parsed as an integer and silently becomes 1. The monitor scale 1.666667 is also wrong: upstream's commented fractional example uses 1.6, because Hyprland rejects scales that do not yield integer pixel dimensions. 'Older installs may carry GDK_SCALE=2 in hyprland.conf' is wrong - it lives in monitors.conf. And `Super + /` scale cycling and `Ctrl + Alt + Del` closing all windows do not exist in the bindings (the only Delete binding is SUPER+CTRL+ALT+Delete for display mirroring); those appear fabricated.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Omarchy assumes a 2x HiDPI display. The compositor's monitor scale is already `"auto"` - the thing making apps enormous on a 1x display is `GDK_SCALE`, which Omarchy sets to 2 for GTK/XWayland windows.

Edit `~/.config/hypr/monitors.lua` and change the GDK scale to 1:

```lua
local omarchy_gdk_scale = 1
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```

GDK_SCALE is integer-only - GTK honors whole numbers and nothing else, so never set 1.5 or 1.75 (they are read as 1). Use the nearest integer to your monitor scale.

For a 27"/32" 4K panel where 2x is too big and 1x is too small, use a fractional *monitor* scale with an integer GDK scale. Hyprland rejects fractional scales that do not produce whole-pixel dimensions, so use 1.6 (upstream's own suggested value), not 1.666667:

```lua
local omarchy_monitor_scale = 1.6
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

local omarchy_gdk_scale = 2
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```

Apply:

```bash
hyprctl reload
```

`GDK_SCALE` only reaches apps started *after* the change, so quit and relaunch anything still oversized.

For Spotify specifically, shrink the UI in-app with `Ctrl + Minus` (`Ctrl + Plus` to grow it).

On an older Omarchy 3 install the same two knobs live in `~/.config/hypr/monitors.conf` as `env = GDK_SCALE,1` and `monitor=,preferred,auto,1`.

**Verify.** `hyprctl monitors | grep scale` shows the new value and newly launched GTK apps render at normal size.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting> · <https://learn.omacom.io/2/the-omarchy-manual/86/monitors>

---
