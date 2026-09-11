# Omarchy core

50 problems. Sorted by severity, then by how often users hit it.

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

## Fix the screensaver closing itself after a second and leaving the session unlocked

`screensaver-self-dismisses-and-session-never-locks` · severity: **critical** · frequency: **common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `omarchy-shell`, `quickshell`, `wayland`

**Symptom.** The screensaver appears as a small floating terminal window in the middle of the screen instead of filling it, animates briefly, and closes on its own after about one second with no input. The session then does not lock on that idle cycle, and the journal records the screensaver as dismissed:

```
omarchy idle ... idle-cycle-cancel: screensaver-dismissed
```

It is deterministic with any bar widget panel open when the idle timer fires, and it also happens with no panel open.

One reporter measured the consequence over two days on omarchy 4.0.2-1 with `lock: 300` configured: 239 dismissals, 233 of them between 1.396 and 1.560 seconds after the screensaver started, mean 1.420 seconds with a 0.03 second spread. One overnight stretch ran 225 idle cycles, every one of them dismissed, and the session stayed unlocked from 21:47 until 07:28. In cycles where no screensaver window existed, the lock fired at the deadline every time.

Reported on Omarchy 4.0.0-1 and 4.0.2-1, Hyprland 0.56.2, Quickshell 0.3.0 and 0.3.1, with `foot` and with Ghostty as the terminal, on Intel and on AMD graphics, single monitor and multi monitor.

**Cause.** `/usr/share/omarchy/bin/omarchy-screensaver` runs a poll loop whose exit test is line 44:

```bash
if read -n1 -t 1 || ! screensaver_in_focus; then
```

`screensaver_in_focus`, line 6, asks the compositor for the class of the focused window:

```bash
hyprctl activewindow -j | jq -e '.class == "org.omarchy.screensaver"'
```

The trigger is any layer surface holding exclusive keyboard focus, which is wider than the bar widget panel in the issue title. While one does, `hyprctl activewindow` keeps reporting the window that was focused before the screensaver mapped, so the class never matches and the first tick exits. Upstream reproduced it with a bar panel, with the Omarchy menu, and with the agents panel, and named the clipboard picker, emoji picker and polkit prompt as the same shape. One reporter hit it with only `omarchy-background` and `omarchy-bar` present and could not identify the surface. A collaborator instrumented the script on a disposable worker and measured five identical runs: exactly one tick at +1.09 seconds, with `read` returning 142, which is a timeout with no byte read, and the focus check returning false. No keypress is involved, and the one second is the `read` timeout.

Two details of the appearance follow from the same cause. `/usr/share/omarchy/default/hypr/apps/system.lua` lines 35 to 37 register `fullscreen`, `float` and an animation for `org.omarchy.screensaver` and no size, and `/usr/share/omarchy/default/foot/screensaver.ini` sets no size either, so the 700x500 box is `foot`'s own default for `initial-window-size-pixels` as documented in `man 5 foot.ini`, and a different terminal gives a different box. The compositor declines the fullscreen rule specifically while a layer surface holds keyboard focus, while the float rule from the same block still applies.

The idle service is what turns a cosmetic problem into an unlocked machine. `/usr/share/omarchy/shell/plugins/services/idle/Service.qml` lines 129 to 139 treat any screensaver window closing as a user dismissal and call `cancelIdleCycle("screensaver-dismissed")`, and that function stops `lockTimer` at line 103. It also clears `idledThisCycle` at line 108, so the compositor's next idle edge starts a fresh cycle and the whole thing repeats at the screensaver timeout plus about a second, which is why the lock deadline is never reached on a machine nobody touches. Upstream corrected one detail of that loop: `omarchy-system-wake` is not what re-arms it and generates no input of its own. Nothing in the journal reads as an error, because the cancel is logged at debug level like every other idle event.

`omacom/omarchy#7102`, which only treats lost focus as a dismissal once the screensaver has actually held focus, is open and unmerged against `quattro` on 2026-09-11. Nothing in this path changed at v4.0.3: `bin/omarchy-screensaver`, `bin/omarchy-launch-screensaver`, `bin/omarchy-toggle-screensaver` and `default/hypr/apps/system.lua` at that tag are byte-identical to the files installed by omarchy 4.0.2-1, and the only change to the idle service there is an unrelated fallback for reading `idleConfig`.

> **Audit corrected this record.** Confirmed on this machine, omarchy 4.0.2-1 with Hyprland 0.56.2 and quickshell 0.3.1, by reading the shipped code rather than the thread. Claim 1 holds exactly: `/usr/share/omarchy/bin/omarchy-screensaver` line 44 is `if read -n1 -t 1 || ! screensaver_in_focus; then exit_screensaver`, and `screensaver_in_focus` at lines 5 to 7 is `hyprctl activewindow -j | jq -e '.class == "org.omarchy.screensaver"'`. Claim 2 holds: `handleScreensaverWindowClosed` at `/usr/share/omarchy/shell/plugins/services/idle/Service.qml` lines 129 to 139 calls `cancelIdleCycle("screensaver-dismissed")` for any screensaver window closing, and `cancelIdleCycle` at lines 100 to 111 stops `lockTimer` on line 103 and clears `idledThisCycle` on line 108, which is also the re-arm the record's 225-cycle overnight measurement needs and which the record never explained. Claim 5 holds: `default/hypr/apps/system.lua` lines 35 to 37 set `fullscreen`, `float` and an animation for `org.omarchy.screensaver` and no size, `/usr/share/omarchy/default/foot/screensaver.ini` sets no size, and `man 5 foot.ini` on foot 1.27.0-2 gives `initial-window-size-pixels` a default of 700x500. Claim 3, the one that matters, also holds in the shipped code: `omarchy-launch-screensaver` lines 13 to 15 exit before mapping a window when `screensaver-off` is set, so no `closewindow` arrives, and the 3 second grace timer at `Service.qml` lines 272 to 281 cancels only when `!idleMonitor.isIdle`, so an untouched machine keeps `lockTimer` and locks at `idle.lock`. Upstream state rechecked today: issue 6917 is open with 7 comments and pull request 7102 is open and unmerged against `quattro`, and the thread does support every claim, including the instrumented five runs and the `read` return of 142. I also checked v4.0.3, published 2026-09-08, because it is newer than this workstation: `bin/omarchy-screensaver`, `bin/omarchy-launch-screensaver`, `bin/omarchy-toggle-screensaver` and `default/hypr/apps/system.lua` at that tag diff clean against the installed 4.0.2-1 files, and the only idle service change is an unrelated `idleConfig` fallback, so nothing in this area moved at v4.0.3. Corrected for three things. First, the fix named `omarchy-toggle-screensaver`, which is `omarchy-toggle screensaver-off` with no explicit action and therefore a flip: on a machine where the screensaver is already off it turns the screensaver back on and silently restores an unlocked session, which is unacceptable in the one record whose failure mode is a machine that does not lock, so the fix now sets the flag with `omarchy-toggle screensaver-off on` and confirms it with `omarchy-toggle-enabled screensaver-off`. Second, the fix presented closing a bar panel as one of "two things that work now" while the record's own symptom says the defect also happens with no panel open, and the last reporter in the thread saw it with only `omarchy-background` and `omarchy-bar` present, so that workaround is now labelled as not reliable. Third, `jq '.idle' ~/.config/omarchy/shell.json` reports only what is written in the file and says nothing about whether idle is enabled, so it is replaced by `omarchy-shell idle status`, which I ran here and which returned `"enabled": false` because this workstation has stay-awake set. Verify now leads with `omarchy-debug-idle`, which I read in full and ran read-only: its Screensaver detector prints `disabled` exactly when the flag is set, and the journal grep now matches `lock-system` because the lock event is logged as `lock-system: lock-timeout`. On claim 4, the empty `danger` was wrong and is now filled, which follows the corpus precedent in `walker-gtk4-vulkan-renderer-amdgpu-hard-freeze` of using `danger` for the residual risk of the unfixed state as well as for the cost of the fix, and there is a genuine fix-side risk here in the toggle flipping back. Severity `high` is too low for a deterministic, silent loss of session locking measured over nine hours: `critical` already covers comparable security exposure with no data loss in `docker-published-ports-bypass-ufw`, and I recommend `critical`, but the verdict schema carries no `corrected_severity` and `merge_gapfill.py` applies only fix, cause, symptom, danger, verify and sources, so severity has to be changed in the record by hand before ingest or it will silently stay `high`. What I could not exercise: nothing was reproduced here. This workstation has `stay-awake` set, so `omarchy-shell idle status` reports `"enabled": false` and the idle service never runs a cycle, and I was instructed not to launch the screensaver, not to toggle it and not to lock the session. So the compositor declining the fullscreen rule while a layer surface holds keyboard focus, the `activewindow` false negative itself, the 1.42 second dismissal clustering and the self-sustaining wake loop are all from the thread and from reading the source, not from a local reproduction. The `#7193` caveat in the thread, that a native screensaver binary would be `exec`ed ahead of the `screensaver-off` check and would make the toggle depend on that binary honouring the flag, does not apply yet: no native screensaver package is installed here and `/usr/bin/omarchy-launch-screensaver` carries no such `exec`.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy-toggle-screensaver` is a toggle, so running it twice, or running it on a machine where the screensaver is already off, re-enables the screensaver and silently puts the session back to not locking. Use `omarchy-toggle screensaver-off on` and confirm with `omarchy-toggle-enabled screensaver-off`. Until one of those is in place, treat the session as not locking: nothing in the journal reads as an error, and the only visible sign is the display blanking and flashing back every screensaver timeout. Do not treat closing a bar panel as the fix on a machine you leave unattended.

**Fix.**

There is no upstream fix yet, and only one of the two workarounds in circulation actually restores locking.

**Turn the screensaver off. This is the one to use if you care about the machine locking.** Set the flag explicitly rather than flipping it, so the result does not depend on what it was before:

```bash
omarchy-toggle screensaver-off on
omarchy-toggle-enabled screensaver-off && echo "screensaver off, lock path clear"
```

`omarchy-launch-screensaver` reads that flag at lines 13 to 15 and exits before mapping anything, so no window ever opens and no `closewindow` event can be misread as a dismissal. The 3 second grace timer at `Service.qml` lines 272 to 281 cancels the cycle only when the idle monitor has gone **active**, so on a machine nobody touches the lock timer survives and fires at `idle.lock`. The reporter's control measurement is exactly this: every idle cycle with no screensaver window locked on time, with the same configuration and the same idle service.

To put the screensaver back later:

```bash
omarchy-toggle screensaver-off off
```

The menu command `omarchy-toggle-screensaver` sets the same flag and sends a notification saying which way it went, but it is a toggle rather than an off switch, so running it on a machine where the screensaver is already off turns it back on and silently restores the defect.

**Closing a bar panel is not a reliable fix.** With no surface holding keyboard focus the screensaver does take focus, fill the output and stay up until you touch the machine, which is why it looks like one. It depends on you remembering before you walk away, and at least one reporter hits this with no panel open and an unidentified surface, so do not rely on it to lock a machine.

Check what the idle service is actually doing, because the screensaver and the lock are separate deadlines and the stay-awake toggle disables both:

```bash
omarchy-shell idle status | jq .
```

`"enabled": false` there means idle is off entirely and nothing will lock, whatever the timeouts say.

**Verify.** ```bash
omarchy-debug-idle 200
```

That is the shipped diagnostic. Its **Screensaver detector** section prints `disabled` once the flag is set, and its **Idle IPC status** section reports the effective `screensaver` and `lock` timeouts and whether idle is enabled at all.

For the defect itself, read the cycle in the shell journal:

```bash
journalctl --user -t omarchy-shell -b --no-pager | grep -E 'process-start: screensaver|idle-cycle-cancel|lock-system'
```

A broken cycle shows `idle-cycle-cancel: screensaver-dismissed` about a second after the screensaver started and never reaches `lock-system: lock-timeout`. A healthy cycle reaches it. After turning the screensaver off, wait out the lock timeout once without touching the machine and confirm the session locks.

Sources: <https://github.com/omacom/omarchy/issues/6917> · <https://github.com/omacom/omarchy/pull/7102> · <https://github.com/omacom/omarchy/releases> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-screensaver> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-launch-screensaver> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-toggle-screensaver> · <https://github.com/omacom/omarchy/blob/v4.0.3/shell/plugins/services/idle/Service.qml> · <https://github.com/omacom/omarchy/blob/v4.0.3/default/hypr/apps/system.lua>

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

## Fix an ISO install that fails with "failed retrieving file ... from disk" for a package in the offline mirror

`iso-install-failed-retrieving-file-offline-mirror` · severity: **high** · frequency: **common** · applies to: `arch`, `desktop`, `laptop`, `omarchy`, `usb`

**Symptom.** Installing from the Omarchy 4.0.x ISO fails part way through. During the "Installing Arch + Omarchy" (pacstrap) stage:

```
failed retrieving file 'gst-plugin-gtk-1.28.6-1-x86_64.pkg.tar.zst' from disk : Could not open file
ERROR: Failed to install packages to new root
```

or, on the first attempt in a boot, during "Configuring system":

```
:: File /var/cache/pacman/pkg/nvidia-utils-610.57.04-1-x86_64.pkg.tar.zst is corrupted
Do you want to delete it? [Y/n]  error: failed to commit transaction (invalid or corrupted package)
Failed: /usr/share/omarchy/install/hardware/nvidia.sh
```

Looking in `/var/cache/omarchy/mirror/offline/` from the installer shell, the named package really is absent, and `/etc/pacman.conf` points at `Server = file:///var/cache/omarchy/mirror/offline/`. Retrying in the same boot fails the same way every time, and a later retry can add `failed retrieving 'offline.db' from disk`. The network is up and unrelated. Reported on the 4.0.0 (`IMAGE_VERSION=2026.08.14`), 4.0.1 and 4.0.2 ISOs, naming `gst-plugin-gtk` (three reporters) and `nvidia-utils` (one).

**Cause.** The ISO is not missing the package. A collaborator checked the published 4.0.0 and 4.0.1 images against their own signatures and manifests and found every package in the offline mirror present with a matching sha256 (1247 and 1249 packages respectively). The failure happens between that file and pacman reading it: a bad download, a bad write to the stick, or a bad read off it.

During the pacstrap stage the offline mirror directory is bind-mounted onto pacman's package cache, so the repository pacman fetches from and the cache it validates are the same directory. `_mount_offline_package_cache` in the ISO installer runs `mount --bind /var/cache/omarchy/mirror/offline <target>/var/cache/pacman/pkg`, which is done to avoid copying several GiB twice. When one package fails its checksum, pacman's "File ... is corrupted. Do you want to delete it?" is answered yes by `--noconfirm` and the file is unlinked out of the mirror. The collaborator reproduced that on a clean VM with pacman 7.1.0: intact, the package installs. With 64 bytes altered, pacman reports `invalid or corrupted package (checksum)` and deletes it, and the next attempt reports the `Could not open file` error this issue was filed about. The deletion lands in the live session's RAM overlay, not on the stick, because archiso mounts the root image read-only and layers a tmpfs over it, and no Omarchy boot entry asks for a persistent overlay. That is why every retry in the same boot fails on the missing file and a reboot brings it back.

That bind is released before the "Configuring system" stage, so the two symptoms above do not share one mechanism. The installer unmounts the mirror from the target cache in the `finally` that closes the base-install block, then bind-mounts the mirror at its own path inside the target instead, leaving the target's `/var/cache/pacman/pkg` as its own btrfs `@pkg` subvolume. A package pacman deletes during `omarchy-apply-system` is therefore a copy in that subvolume, and from source it should not remove anything from the mirror. The `nvidia-utils` reporter on the 4.0.2 ISO nevertheless found the mirror missing the package on the retry, followed by `failed retrieving 'offline.db' from disk`, and the collaborator's reading of that second error is that the reads themselves had started failing rather than one package having been deleted. Treat a mirror-path error after a "Configuring system" failure as a sign of a failing medium, not as the deletion cascade. What the `nvidia-utils` report does settle is that nothing here is specific to `gst-plugin-gtk`.

Two reporters confirmed the media side. One was booting from a microSD card in a USB reader on a USB-C dongle: `sha512sum -c airootfs.sha512` reported a mismatch, and the install succeeded after writing the same ISO to a real USB drive. The reporter who opened the issue was on the same microSD-plus-adapter setup.

One reporter also found that when the abort lands in "Configuring system", the target is left half configured: the login step and the post-install step that replaces the offline `pacman.conf` never run, and the first boot reached an SDDM greeter that rejected the password because the theme submitted an empty username. Treat a failed install as one to redo, not one to boot.

> **Audit corrected this record.** Checked the installer source in omacom/omarchy-iso on `quattro` and the archiso runtime source, and read issue 7704 in full with all eleven comments. Nothing here could be exercised on this machine: this is an installed Omarchy 4.0.2-1 system, not a live ISO, so there is no `/run/archiso`, no offline mirror and no pacstrap to run, and every claim below is from source or from the thread rather than observed. The bind-mount claim is confirmed from source. `_mount_offline_package_cache` at `configs/airootfs/usr/share/omarchy-iso/orchestrator/phases_impl.py:642` runs `mount --bind /var/cache/omarchy/mirror/offline <target>/var/cache/pacman/pkg`, called at line 250, and `configs/pacman-offline.conf` carries `Server = file:///var/cache/omarchy/mirror/offline/`, so during pacstrap the repository and the validated cache are one directory and a `--noconfirm` delete unlinks out of the mirror. The installer's own `omarchy-install-diagnose-media` says the same in its header comment. The recovery path is confirmed right for archiso. I pulled `mkinitcpio-archiso` 73-1 from a pacman mirror and read `usr/lib/initcpio/hooks/archiso`: line 370 is `_mnt_fs "${fs_img}" "/run/archiso/airootfs"`, `_mnt_fs` attaches the image with `losetup --find --show --read-only` and mounts it `-r`, and line 374 overlays it with `upperdir=/run/archiso/cowspace/${cow_directory}/upperdir`, where `/run/archiso/cowspace` is a tmpfs unless a `cow_device` is passed. Omarchy's `configs/grub/grub.cfg` cmdline at lines 57 and 63 passes only `archisobasedir`, `archisosearchuuid` and display options, so there is no `copytoram` and no persistent overlay, which makes the record's "reboot brings it back" correct. The checksum command is right too: `configs/profiledef.sh` sets `install_dir="arch"`, `arch="x86_64"` and `airootfs_image_type="squashfs"`, and `mkarchiso` in archiso 90-1 calls `_mkchecksum` unconditionally, writing `sha512sum airootfs.sfs >airootfs.sha512`, so the path and the expected `airootfs.sfs: OK` both hold. One thing was wrong. The cause presented the bind mount as covering the whole install and used it to explain both quoted symptoms, and it does not. `_unmount_offline_package_cache` runs in the `finally` that closes the base-install block, before `_prepare_target_setup`, which bind-mounts the mirror at its own path inside the target rather than onto the cache, leaving the target's `/var/cache/pacman/pkg` as the btrfs `@pkg` subvolume written into fstab at line 848. The `nvidia-utils` failure happened in "Configuring system" under `omarchy-apply-system`, which is after that unmount, so from source the deletion should not have reached the mirror. I rewrote that paragraph to confirm the mechanism for the pacstrap window, to say it is not established for the later window, and to keep the reporter's observation with the collaborator's reading of the follow-on `failed retrieving 'offline.db' from disk` as failing reads. Two smaller corrections to the fix: every 4.0.x release note publishes an ISO sha256, not only v4.0.1 (v4.0.0 `9224fab3`, v4.0.1 `69cbb4e1`, v4.0.2 `2ef8e624`, v4.0.3 `03d60bc7`), and the fix omitted that the failure screen now diagnoses the medium by itself. `omarchy-install-diagnose-media` landed 2026-08-23 in omarchy-iso PR #120, is installed 0755 per `configs/profiledef.sh:42`, and `omarchy-install-dashboard` calls it unconditionally at line 844, so it is on the 4.0.1, 4.0.2 and 4.0.3 ISOs but not 4.0.0. I added it as the first step along with the one case where it stays silent, which follows from its own `sed` pattern matching only `/mnt/var/cache/pacman/pkg` while the `nvidia-utils` reporter's log line was the in-chroot path. Issue 7704 supports every other claim in the record, including the 1247 and 1249 package counts, the microSD-versus-USB switch, and the SDDM empty-username consequence, and it is still open.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Read the failure screen first. On the 4.0.1 and later ISOs the installer runs `omarchy-install-diagnose-media` itself when a step fails and prints a verdict that names the medium, so the answer is often already on screen. It is silent in one case worth knowing: it only matches a corrupt-package line under `/mnt/var/cache/pacman/pkg`, so a failure logged from inside the chroot during "Configuring system" prints nothing. The 4.0.0 ISO predates the tool.

Then check the medium, from a shell in the live session on a fresh boot, before starting the installer. This re-reads the whole root image off the stick and takes a few minutes:

```bash
cd /run/archiso/bootmnt/arch/x86_64 && sha512sum -c airootfs.sha512
```

A mismatch means the copy on the stick is wrong. Re-download the ISO, check it against the sha256 published in that version's release notes (every 4.0.x release publishes one beside the download link), and write it to a different medium. A plain USB drive worked where a microSD card in a USB reader did not (confirmed by the reporter who switched, and it is the setup the original reporter was on too).

`OK` means the stick is sound. Reboot between attempts, because a package deleted during pacstrap stays deleted for the rest of that boot, and quote the first error after a fresh boot, since `failed retrieving file ... Could not open file` is only ever the wake of an earlier failure. `/var/log/omarchy-install.log` in the live session holds the full text.

To retry without rebooting, put the deleted package back from the read-only image, which archiso keeps mounted at `/run/archiso/airootfs` for the whole session. The collaborator tested this arrangement on a VM, no reporter has confirmed it on real media:

```bash
sudo cp /run/archiso/airootfs/var/cache/omarchy/mirror/offline/gst-plugin-gtk-*.pkg.tar.zst \
        /var/cache/omarchy/mirror/offline/
```

Substitute whichever package the error named, then start the installer again. That `cp` is also a test, because it re-reads the same bytes off the same stick. It succeeds and the install gets past the package: a one-off misread. The install rejects the same package again with `invalid or corrupted package (checksum)`: the bytes on the stick are wrong, re-download and re-flash. The `cp` fails with an input/output error: the medium itself is failing, use another port or another stick.

Which package is named after a fresh reboot is a useful signal. The same package again means a stable fault in your copy (bad download or bad write). A different package each time means the bytes are fine and the reads are not (port, cable, card reader, or memory).

Note that the 4.0.0 ISO carries `gst-plugin-gtk-1.28.6-1` and 4.0.1 carries `-2`, so the version in the error tells you which image you booted.

**Verify.** `sha512sum -c airootfs.sha512` prints `airootfs.sfs: OK`, and the installer runs through "Installing Arch + Omarchy" and "Configuring system" without naming a package. On a stick that failed the check, the same ISO written to a different USB drive installed cleanly.

Sources: <https://github.com/omacom/omarchy/issues/7704> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/share/omarchy-iso/orchestrator/phases_impl.py> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/pacman-offline.conf> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/profiledef.sh> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/grub/grub.cfg> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/local/bin/omarchy-install-diagnose-media> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/usr/local/bin/omarchy-install-dashboard> · <https://archlinux.org/packages/extra/any/mkinitcpio-archiso/> · <https://archlinux.org/packages/extra/any/archiso/> · <https://github.com/omacom/omarchy/releases/tag/v4.0.0> · <https://github.com/omacom/omarchy/releases/tag/v4.0.1> · <https://github.com/omacom/omarchy/releases/tag/v4.0.2> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3>

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

## Finish an Omarchy 4.0 install that stops at `Module psmouse not found`

`omarchy-install-fails-psmouse-module-not-found` · severity: **high** · frequency: **common** · applies to: `intel`, `laptop`, `lenovo`, `omarchy`, `thinkpad`

**Symptom.** A clean Omarchy 4.0.0 (Quattro) install halts during the `Configuring system` phase with:

```
modprobe: FATAL: Module psmouse not found in directory /lib/modules/7.1.8-arch1-Watanare-T2-2-t2
[Failed]: /usr/share/omarchy/install/hardware/fix-synaptic-touchpad.sh (exit code: 1)
```

It does not matter whether you picked full-disk or free-space install. Reported on a ThinkPad (free-space dual boot), a Lenovo IdeaPad L340 (full disk) and a Lenovo IdeaPad 330-15IKB, plus one further full-disk report and one user who gave up and installed Omarchy 3.6 first. If you patch around it and resume by hand, the next hardware scripts fail with `error: failed retrieving file '...' from disk : Could not open file /var/cache/omarchy/mirror/offline/...` even with working internet.

**Cause.** Established by the maintainers' triage and fixed in `#7236`. `install/hardware/fix-synaptic-touchpad.sh` fires on any machine with an input device merely named `synaptics` and runs `modprobe psmouse synaptics_intertouch=1`. During an install it runs inside `arch-chroot`, where `uname -r` still names the live ISO's `linux-t2` kernel while `/lib/modules` holds the target's stock `linux`, so modprobe cannot find the module, and because the hardware phase runs under `set -euo pipefail` the whole install stops. The follow-on `Could not open file /var/cache/omarchy/mirror/offline/...` errors are a consequence of resuming by hand: the installer bind-mounts the ISO's offline mirror into the target and unmounts it when it exits, leaving an empty directory that the target's `pacman.conf` still names as its only repository. That part is the triage's reading of the source, not something a reporter measured.

> **Audit corrected this record.** Checked the mechanism, the merge and the shipped script, and reproduced the failure with a stub `modprobe`. Confirmed from the GitHub API that `#7236` is merged into `quattro` with `merged_at` 2026-08-24T13:33:04Z, and that the script at tag v4.0.1 (published 2026-08-25) carries the `modprobe -qn psmouse` guard. Confirmed on this machine that `/usr/share/omarchy/install/hardware/fix-synaptic-touchpad.sh` on omarchy 4.0.2-1 has that guard at line 22, and that `/usr/bin/omarchy-apply-system` exists. Confirmed on this machine that `install/hardware/all.sh` runs `fix-synaptic-touchpad.sh` at line 9, `nvidia.sh` at 11, `vulkan.sh` at 12 and the `intel/` scripts from 14, so the offline-mirror errors cannot occur in an untouched run, which is the evidence for the record's own statement that they are a consequence of resuming by hand. Fetched the v4.0.0 script and ran it under `bash -euo pipefail` against a stub `modprobe` that fails: exit 1, and the patched and the upstream-corrected versions both exit 0, so the cause and the workaround both hold. Two things were wrong. The `sed` command in the fix does not work: with `|` as the `s` delimiter the literal `||` was written `\||`, so the unescaped pipe ends the replacement and sed exits 1 with `unknown option to 's'` and leaves the file unpatched. I reproduced that verbatim against the v4.0.0 script and replaced it with a `#`-delimited command I tested, which produces `modprobe psmouse synaptics_intertouch=1 2>/dev/null || true` and passes `bash -n`. The second was provenance: issue 6985 has one further explicit full-disk report (`kridaydave`) and one user who installed 3.6 instead (`rez1-dev`) rather than two full-disk reports, and nobody in the thread reported installing from the v4.0.1 ISO. `gtech-pedrol` only pointed at the release page and `kridaydave` acknowledged it, so I replaced the "two reporters confirmed" claim with the tag reading I did myself. Issue 6985 otherwise supports the record: the maintainer triage states the chroot kernel mismatch, that the gate is evaluated in the ISO environment so the install mode cannot matter, and that the unmounted bind mount explains the `Could not open file` errors. Not exercised: no install was run from any ISO, and the bind-mount resume step was not tested. The v4.0.1 release carries no release assets and `omacom/omarchy-iso` has no tags or releases, so the ISO image itself could not be inspected and the version claim rests on the tagged script content.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Resuming a half-finished install by hand skips whatever the installer had not yet reached. If anything after the hardware phase also fails, reinstall from the v4.0.1 ISO rather than patching further, or the target may not boot cleanly.

**Fix.**

Install from the v4.0.1 ISO or later, and prefer the newest: v4.0.3 was published on 2026-09-08. `#7236` merged into `quattro` on 2026-08-24 and the v4.0.1 tag (2026-08-25) carries the corrected script, which asks `modprobe -qn psmouse` before loading and warns instead of failing. That was checked by reading the script at both tags and at the installed 4.0.2-1 copy, not by running an install from the ISO. Installing Omarchy 3.6 and upgrading also avoids it, because the script only runs from the ISO, and one reporter did exactly that.

If you are stuck mid-install with the 4.0.0 ISO, patch the script in the target from the live environment. Two reporters confirmed that appending `2>/dev/null || true` to the `modprobe` line gets past the touchpad step:

```bash
sed -i 's#^\(\s*modprobe psmouse synaptics_intertouch=1\).*#\1 2>/dev/null || true#' \
  /mnt/usr/share/omarchy/install/hardware/fix-synaptic-touchpad.sh
grep -n modprobe /mnt/usr/share/omarchy/install/hardware/fix-synaptic-touchpad.sh
```

The `#` delimiter is not cosmetic. With `s|...|...|` the literal `||` has to be written `\|\|`, and one escape short of that makes sed exit 1 with `sed: -e expression #1, char 72: unknown option to 's'` and leave the file untouched, which looks like the patch worked until the install fails again. The `grep` must print exactly:

```
  modprobe psmouse synaptics_intertouch=1 2>/dev/null || true
```

Before resuming, put the offline mirror back so the remaining hardware scripts can find their packages. This step is the triage's proposed resume and was not confirmed by a reporter, but the reporters who skipped it hit the `Could not open file` errors on every following script:

```bash
mount --bind /var/cache/omarchy/mirror/offline /mnt/var/cache/omarchy/mirror/offline
findmnt /mnt/var/cache/omarchy/mirror/offline
ls /mnt/var/cache/omarchy/mirror/offline | head
```

Then resume the way the original reporter did, with your install username:

```bash
arch-chroot /mnt /usr/bin/omarchy-apply-system --install-user <user> --first-install
```

**Verify.** On a v4.0.1 or later ISO the corrected script is in place:

```bash
grep -n 'modprobe -qn psmouse' /usr/share/omarchy/install/hardware/fix-synaptic-touchpad.sh
```

After a resumed 4.0.0 install, the `[Failed]` line does not recur and the hardware scripts complete. One reporter confirmed the rest of the install finished after patching the touchpad script and restoring package access.

Sources: <https://github.com/omacom/omarchy/issues/6985> · <https://github.com/omacom/omarchy/pull/7236> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/fix-synaptic-touchpad.sh> · <https://github.com/omacom/omarchy/releases/tag/v4.0.1> · <https://github.com/omacom/omarchy/blob/v4.0.0/install/hardware/fix-synaptic-touchpad.sh> · <https://github.com/omacom/omarchy/blob/v4.0.1/install/hardware/fix-synaptic-touchpad.sh> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3>

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

## Top bar gone and staying gone: omarchy-shell crash-loops and its supervisor gives up

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

## Recover the Omarchy shell after 'undefined symbol: _ZN23QUntypedPropertyBindingC1EP23QPropertyBindingPrivate'

`omarchy-shell-quickshell-undefined-symbol-qt-private-api` · severity: **high** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** After an `omarchy update` on 2026-08-20 or 2026-08-21 the bar, menu and notifications vanish. Hyprland itself still runs. The update ends with `Omarchy shell did not become ready after restart.`, and `omarchy restart shell` fails the same way. The error carries one of two symbol version suffixes, and which one you get depends on which side of the skew your channel landed on:

```
quickshell: symbol lookup error: quickshell: undefined symbol: _ZN23QUntypedPropertyBindingC1EP23QPropertyBindingPrivate, version Qt_6
```

```
quickshell: symbol lookup error: quickshell: undefined symbol: _ZN23QUntypedPropertyBindingC1EP23QPropertyBindingPrivate, version Qt_6_PRIVATE_API
```

```
Giving up on the Omarchy shell after 6 relaunches in under a minute.
Omarchy shell did not become ready after restart.
```

A reboot gives a black screen or a bare Hyprland session with no shell. `yay -S quickshell-git --rebuild` changes nothing, and neither does `yay -S --aur --rebuild --redownload quickshell-git`: in August 2026 the shell came prebuilt as `quickshell-git` from the `omarchy` package repository rather than compiled from the AUR, and yay reinstalled the same binary. Hit on the edge, rc and stable channels on Omarchy 4.0.0-1. Omarchy 4.0.2 and later install `quickshell` from Arch `extra` instead, so the two publication systems that disagreed here are no longer both in play.

**Cause.** Confirmed by dhh and by the omarchybot triage on omacom/omarchy#7634, closed as the same failure as #7596. Quickshell links Qt's private ABI, so a build loads only against the Qt release it was compiled against. Omarchy's own package repository and Omarchy's Arch mirrors are separate systems on independent sync cadences, and nothing sequenced a publish against a mirror sync, so a single rebuild broke channels in **opposite directions**.

On edge the mirrors moved to `qt6-base 6.11.2` while the shell was still the 10 August `quickshell-git 0.3.0.r20.g28771c7-1` build. That build resolves the constructor at `Qt_6_PRIVATE_API`, which 6.11.2 no longer exports under that version tag, so it fails with the `Qt_6_PRIVATE_API` suffix.

On rc and stable the repository published `quickshell-git 0.3.0.r20.g28771c7-2`, rebuilt against `qt6-base 6.11.2` and `qt6-declarative 6.11.2-1` as its `.BUILDINFO` records, while those Arch mirrors still served `qt6-base 6.11.1-1`. The `-2` build resolves the constructor at `Qt_6` and 6.11.1's `libQt6Core` exports it only at `Qt_6_PRIVATE_API`, so it fails with the `Qt_6` suffix.

Nothing stopped either pairing. The `quickshell-git` PKGBUILD declared `depends=('qt6-declarative' 'qt6-base' ...)` with no version constraints, and the published package carried none, so pacman installed a build made against one Qt beside the other without complaint. `quickshell-check.hook` lists only `Target = qt6-base` and `Target = qt6-wayland`, so a transaction that upgraded `quickshell-git` alone fired no check and warned nobody. Stable made it worse by not rebuilding at all: the edge artifact is rsynced into stable, so stable shipped a binary linked against edge's Qt.

The mirrors were brought back into agreement on 2026-08-21. Omarchy then switched back to the Arch `extra` package `quickshell` on 2026-08-22 in commit `2c593dbbaad67698e7b9b0809d082d86540a7a1c`, so a current install carries `quickshell 0.3.1-1` signed by an Arch packager instead of a `quickshell-git` build from `pkgs.omarchy.org`, and keeping it in step with a Qt release is Arch's job rather than Omarchy's.

> **Audit corrected this record.** Read omacom/omarchy#7596 and #7634 in full with all comments. Both support the record. #7596 carries the symbol level analysis (the `-2` build links the constructor as `Qt_6` while 6.11.1's libQt6Core exports it only as `Qt_6_PRIVATE_API`, and both builds share the same 1572 Qt_6 versioned symbols), dhh's confirmation that `omarchy update` is the fix, and the stable and rc reports. #7634 carries the omarchybot triage the record cites, closed as completed. Confirmed from source today that the packaging mechanism is exactly as stated: omacom-io/omarchy-pkgs `pkgbuilds/quickshell-git/PKGBUILD` has `depends=('qt6-declarative' 'qt6-base' ...)` with no version constraints, and `pkgbuilds/quickshell-git/quickshell-check.hook` lists only `Target = qt6-base` and `Target = qt6-wayland`, so a transaction upgrading quickshell-git alone fired nothing. Confirmed on this machine at omarchy 4.0.2-1 that the record's closing claim about packaging is right and that the rest of the record is now written against a package Omarchy no longer uses: `pacman -Sl` reports `extra quickshell 0.3.1-1 [installed]`, `pacman -Qi quickshell` names an Arch packager and `Validated By: Signature`, `quickshell --version` prints `Quickshell 0.3.1 (revision , distributed by Arch Linux)`, `/usr/bin/quickshell` is owned by `quickshell 0.3.1-1`, and `/usr/share/omarchy/install/omarchy-base.packages:111` reads `quickshell`. The switch landed upstream on 2026-08-22 in commit 2c593dbbaad67698e7b9b0809d082d86540a7a1c, "Switch back to the packaged quickshell now that 0.3.1 kills synchronously", against `quickshell-git` at v4.0.0. So the record is right that this is not an AUR rebuild problem and right that Omarchy has moved to the packaged quickshell. Three defects. First, the symptom shows only the `version Qt_6` suffix while claiming the edge channel was hit, and the edge channel failed in the opposite direction: the opening report on #7596 and one commenter show edge's mirrors moving to Qt 6.11.2 under the old `-1` build, which fails with `version Qt_6_PRIVATE_API`. A reader on that error would not match this record. Second, the cause explains only the new-quickshell-against-old-Qt direction, so it does not cover edge at all. Third, the fix's sentence that the repository serves the matching `quickshell-git -2` is stale: `omarchy update` on 4.0.2 or v4.0.3 installs `quickshell` from Arch extra, so that sentence describes a package the current system does not carry. The advice itself, `omarchy update`, is unchanged and still correct. The danger named `quickshell-git` and is rewritten to name `quickshell`. Also verified: qt6-base in extra is now 6.11.2-3 and installed here is 6.11.2-2, and the omarchy-pkgs `.omarchy/package.json` now carries the `rebuild_on` and `rebuilt_against` hardening omarchybot described, pinned at qt6-base 6.11.2-3. Both verify commands ran here and passed: `quickshell --version` printed a version and `omarchy-shell shell ping` printed `ok`. NOT exercised: I could not reproduce the mismatch, since that needs a Qt downgrade and I have no sudo, and I could not query the upstream Quickshell issue tracker, which is Gitea at git.outfoxxed.me rather than GitHub, though its tag list confirms v0.3.1 is the newest release.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not pin or hold `quickshell` or `qt6-base` to get past this. Quickshell links Qt's private ABI, so a partial upgrade of the Qt stack reproduces the same mismatch in the other direction. Go through `omarchy update`, never `pacman -Sy quickshell` or `pacman -Sy qt6-base`.

**Fix.**

Get a terminal without the shell. `Super + Return` is a Hyprland binding and still works, and so does a tty. Then update again, as dhh confirmed:

```bash
omarchy update
```

That resolved it on every channel once the mirrors agreed on 2026-08-21, and it is still the right move on a current install, where `omarchy update` installs `quickshell` from Arch `extra` rather than `quickshell-git` from `pkgs.omarchy.org`. If the update does not restart the shell itself:

```bash
omarchy restart shell
```

Do not keep the interim workaround. Many reporters downgraded to the cached `-1` build to get a shell back:

```bash
sudo pacman -U /var/cache/pacman/pkg/quickshell-git-0.3.0.r20.g28771c7-1-x86_64.pkg.tar.zst
omarchy restart shell
```

`-1` loads only against Qt 6.11.1, so once the mirrors carried 6.11.2 it became the broken half, and `quickshell-git` is no longer the package Omarchy installs. Anyone still holding it should run `omarchy update` to come forward to `quickshell` from `extra`.

**Verify.** ```bash
quickshell --version
omarchy-shell shell ping
```

The first prints a version instead of the symbol lookup error, and the second prints `ok`. The bar and `Super + Space` menu are back.

Sources: <https://github.com/omacom/omarchy/issues/7596> · <https://github.com/omacom/omarchy/issues/7634> · <https://github.com/omacom/omarchy/commit/2c593dbbaad67698e7b9b0809d082d86540a7a1c> · <https://github.com/omacom/omarchy/blob/quattro/install/omarchy-base.packages> · <https://github.com/omacom/omarchy-pkgs/blob/master/pkgbuilds/quickshell-git/PKGBUILD> · <https://github.com/omacom/omarchy-pkgs/blob/master/pkgbuilds/quickshell-git/quickshell-check.hook> · <https://archlinux.org/packages/extra/x86_64/quickshell/> · <https://archlinux.org/packages/extra/x86_64/qt6-base/>

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

## A plugin file change while the session is locked strands the lock screen or aborts omarchy-shell

`plugin-file-write-while-locked-strands-session` · severity: **high** · frequency: **common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** The session is locked, by idle timeout or `omarchy system lock`. A file under `~/.config/omarchy/plugins/<plugin>/` then changes: `chezmoi apply` or Syncthing from another machine, a `git pull` in a plugin checkout, a background agent writing files, an editor still saving after you walked away, or a test suite dropping `__pycache__/` into the plugin directory. `journalctl --user -t omarchy-shell` shows:

```
Local plugin changed, reloading: <plugin id>
omarchy lock ... lock-stranded: recovering
omarchy lock ... lock-requested
omarchy lock ... lock-pending: screen-stabilizing
```

It then goes one of two ways. Either it never progresses, and Hyprland's "lockscreen app died" failsafe stays on screen with no password prompt, or omarchy-shell aborts:

```
FATAL: Tried to show lockscreen surfaces without active lock
```

That is a `SIGABRT` from `quickshell -n -p /usr/share/omarchy/shell`, one core in `coredumpctl`, after which a replacement shell starts within a second or two and usually re-locks properly so your password works. The abort can be delayed by hours and land on a later screen wake with no plugin write near it.

In the stranded case, `omarchy-shell lock status` reports `{"locked":true,"requested":true,"pending":true,"sessionLocked":false,"secure":true,...}` and `omarchy-restart-shell` answers `Refusing to restart Omarchy shell while the session is locked.`

The compositor usually keeps holding the lock, so the failsafe wall stays up and the desktop is not exposed. Do not rely on that. One reporter on issue 6888 saw the opposite after a stall: `omarchy-hyprland-session-locked` exited 1, `solitaryBlockedBy` carried no `LOCK`, and the only layers left were `omarchy-bar` and `omarchy-background`, with the shell still reporting `secure:true`. Check a wedged machine with `omarchy-hyprland-session-locked` before you walk away from it.

Reported on 4.0.0-1, 4.0.1-1 and 4.0.2-1, with quickshell-git 0.3.0 and quickshell 0.3.1-1 on Qt 6.11.1 and 6.11.2, on NVIDIA desktops, Intel i915 laptops, AMD amdgpu machines, one AMD plus NVIDIA dual-GPU machine and Apple Silicon (Asahi). One reporter hit it with no lock involved at all, from a plugin rewritten every 10 to 40 seconds.

**Cause.** Established in the threads by collaborator triage against `quattro` and the quickshell sources, and by core dumps from three reporters.

A plugin change triggers `reloadPlugins()`, which calls `unloadPluginServices()` in `shell/shell.qml`. Before the fix that function destroyed every plugin service unconditionally, including `omarchy.lock`, which owns the live `WlSessionLock`. The lock manifest's `keepLoaded: true` was honoured for panel Loaders only. Confirmed on an omarchy 4.0.2-1 install: `/usr/share/omarchy/shell/shell.qml` lines 348 to 354 destroy every service, and `keepLoaded` is consulted only around the panel Loader at line 625.

Destroying the lock client leaves the compositor's `ext-session-lock` standing with no locker, which is what Hyprland's failsafe is showing. It also leaves quickshell's process-global `QSWaylandSessionLockManager::active` pointer dangling, because only `unlock()` clears it, so no lock attempt in that process can succeed again. The rebuilt lock service then reads `sessionLock.secure` through that dangling pointer. If it reads true the service returns early forever, which is the silent `lock-pending` stall. If it reads false it sets `locked = true`, and in quickshell 0.3.1 `WlSessionLock::realizeLockTarget` calls `qFatal` when `manager->lock()` fails, which is the abort. Reading a field of a freed object is why the abort can arrive hours later, once that memory is reused.

`omarchy-restart-shell` refuses in the stranded case because it asks the same wedged service: lines 28 to 36 on 4.0.2-1 test `.secure or .requested` and bail out when either is true. The same teardown is reachable without any file write, through `omarchy plugin disable omarchy.lock` or `omarchy plugin remove` while locked, which also go through `_syncServices()`.

> **Audit corrected this record.** Checked every mechanical claim on this workstation (omarchy 4.0.2-1, quickshell 0.3.1-1, Hyprland 0.56.2) and every source claim against the threads read in full today. Confirmed here: `unloadPluginServices()` at /usr/share/omarchy/shell/shell.qml lines 348 to 354 destroys every service with no `keepLoaded` test, `keepLoaded` is read only around the panel Loader at line 625, /usr/share/omarchy/shell/plugins/lock/manifest.json sets `keepLoaded: true`, and /usr/share/omarchy/bin/omarchy-restart-shell lines 29 to 37 run `jq -r '.secure or .requested'` and print `Refusing to restart Omarchy shell while the session is locked.` at line 33, then set `relock=1` and re-lock through `relock_session()` when neither is true, so claim 1 holds exactly as written. Confirmed here for claim 2: `hl.clear_crashed_lockscreen` is a function in the live `hl` table (`hyprctl repl 'return type(hl.clear_crashed_lockscreen)'` answers `function`), so is `hl.dsp.exec_cmd`, `hyprctl --instance 0` and `hyprctl eval` both exist, hyprlock is not installed, and /usr/share/hypr/lockdead.png is the failsafe wall and prints the record's command verbatim plus the `killall -9 hyprlock` line that does nothing on Omarchy 4. Hyprland v0.56.2 source shows `hlClearCrashedLockscreen` refusing with `session is locked with a client, refusing to unlock` when `clientLocked() || clientDenied()` and otherwise calling `forceUnlock()`, which is the refuse-then-unlock behaviour the record claims. /usr/share/omarchy/bin/omarchy-launch-shell is the supervisor: it waits on quickshell, logs `Omarchy shell exited with status $status; relaunching.` at line 89, and gives up at line 85 with `Giving up on the Omarchy shell after 6 relaunches in under a minute.`, so the SIGKILL route and both quoted journal lines are right. From sources: the fix claim is current. PR 9485 merged to `quattro` on 2026-09-02 as `d3d23fdd`, and shell.qml at tag v4.0.3 has `serviceKeepLoaded()` and an `unloadPluginServices()` that keeps those services, so the `grep -n serviceKeepLoaded` test is valid. `omarchy 4.0.3-1` is in the [omarchy] stable repo today (fetched pkgs.omarchy.org/stable/x86_64/omarchy.db), so `omarchy update` really does deliver it. The still-open list also holds: v4.0.3's `_syncServices` still destroys unconditionally and never consults `keepLoaded`, and PR 7169 is still open. Issues 7106, 9441 and 6888 support the symptom, the status JSON, the refusal text, the delayed abort, the `__pycache__` trigger and the `pkill -9` recovery (cyppe on 7106 records status 137, then `secure=true` six seconds later, and the `hl.clear_crashed_lockscreen()` note the record's last-resort block is built from). Two things were wrong. First, no reporter in 7106, 9441 or 6888 has an Intel plus NVIDIA machine. What is attested is NVIDIA-only desktops, Intel i915 laptops, AMD amdgpu, one AMD plus NVIDIA dual-GPU machine and Apple Silicon. Second, `The compositor lock holds throughout, so nothing on screen is exposed` is contradicted by parnoldx on 6888, whose stalled machine had `omarchy-hyprland-session-locked` exiting 1, no `LOCK` in `solitaryBlockedBy` and no lock layer while the shell still reported `secure:true`. That is a security claim, so it is now qualified rather than stated flat. The danger field was rewritten to say what `hl.clear_crashed_lockscreen()` actually does (`forceUnlock()`), to name the re-lock step, and to record that killing quickshell is not free once the supervisor's five-relaunch budget is gone. Not exercised: nothing on the recovery path was run. This session cannot lock the screen, kill quickshell or call `hl.clear_crashed_lockscreen()` without stranding itself, so the kill-and-relaunch sequence and the failsafe clear rest on the scripts, the Hyprland source and the reporters, not on a local run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The last resort unlocks the machine. `hl.clear_crashed_lockscreen()` calls Hyprland's `forceUnlock()`, so the desktop is live and unattended from the moment it returns until something locks it again, and the usual way into this recovery is a TTY or an ssh session from somewhere else. Only run it when you are physically at the machine, and lock again with `omarchy-shell lock lock` as soon as the shell is back. Killing quickshell is safer, because the compositor keeps holding the lock while the supervisor restarts the shell. It is not free either: `omarchy-launch-shell` allows five relaunches in sixty seconds, then logs `Giving up on the Omarchy shell after 6 relaunches in under a minute.` and stops, which leaves the failsafe up with no shell at all.

**Fix.**

**The fix shipped in 4.0.3.** PR #9485, "Honor keepLoaded for services during plugin hot-reload", merged to `quattro` on 2026-09-02 as commit `d3d23fdd`, makes `unloadPluginServices()` keep any service whose manifest sets `keepLoaded: true`, which `omarchy.lock` does. The v4.0.3 tag, published 2026-09-08, contains it, and 4.0.2-1 and earlier do not:

```bash
omarchy update
grep -n serviceKeepLoaded /usr/share/omarchy/shell/shell.qml   # present once the fix has arrived
```

Still open after that merge: `omarchy plugin disable` or `remove` while locked, and recovery of a process that has already taken the damage, which is PR #7169.

**Prevention on 4.0.2 and earlier.** Do not write under `~/.config/omarchy/plugins/` while the screen is locked. Edit a plugin in a scratch directory and copy it in when you are at the keyboard, and gate sync and dotfile tools on `omarchy-hyprland-session-locked`, which exits 0 while the compositor holds a session lock. One reporter runs this as a chezmoi pre-apply hook:

```bash
if omarchy-hyprland-session-locked; then
  echo "session is locked, not touching plugins" >&2
  exit 1
fi
```

**If the abort already happened** and a replacement shell is up, type your password. Nothing else is needed.

**If the session is stranded** with no password prompt, work from a TTY (`Ctrl+Alt+F2`) or over ssh as the session user, inside a login shell (`bash -lc`, otherwise `OMARCHY_PATH` is unset and every `omarchy` command fails). Kill the wedged shell. `SIGKILL` cannot be caught by quickshell's crash handler, so the supervisor `omarchy-launch-shell` logs `Omarchy shell exited with status 137; relaunching.` and the fresh process re-secures the lock on its own within a few seconds, after which the password prompt works. One reporter confirmed this on 4.0.2-1, and it matches the source analysis that only a new process clears the dangling pointer:

```bash
pkill -9 -x quickshell
sleep 6
omarchy-shell lock status        # expect "sessionLocked":true,"secure":true
```

`omarchy-restart-shell` is the shorter route only once no locker is reporting: it refuses while the wedged service still says `.secure` or `.requested`, and re-locks a fresh shell when neither is true.

If the supervisor has given up (`Giving up on the Omarchy shell after 6 relaunches in under a minute.` in the journal) or you killed `omarchy-launch-shell` too, no client holds the lock any more. Clear Hyprland's failsafe and start the shell again. The session comes back **unlocked**:

```bash
hyprctl --instance 0 eval 'hl.clear_crashed_lockscreen()'
hyprctl --instance 0 dispatch 'hl.dsp.exec_cmd("omarchy-launch-shell")'
```

`hl.clear_crashed_lockscreen()` exists in Hyprland 0.56.2 and refuses while a client still holds the lock, which is why the kill comes first. The failsafe text's `killall -9 hyprlock` does nothing on Omarchy 4, which does not install hyprlock.

**Verify.** ```bash
grep -n serviceKeepLoaded /usr/share/omarchy/shell/shell.qml    # the fix is installed
journalctl --user -t omarchy-shell -n 30 --no-pager             # lock-requested, then secure=true
omarchy-shell lock status | jq '.sessionLocked, .secure'        # true, true
coredumpctl list quickshell                                     # no new entry after a plugin write
```

Then type the password at the lock screen. One reporter's journal after the kill: `lock-stranded: recovering` at 12:45:59, `secure=true` at 12:46:05, password accepted. The upstream test plan for #9485 checks that after `omarchy-shell shell rescanPlugins` the lock service's `lastEventAt` is unchanged and its status is not `lock-stranded`.

Sources: <https://github.com/omacom/omarchy/issues/7106> · <https://github.com/omacom/omarchy/issues/9441> · <https://github.com/omacom/omarchy/issues/6888> · <https://github.com/omacom/omarchy/pull/9485> · <https://github.com/omacom/omarchy/pull/7169> · <https://github.com/omacom/omarchy/blob/d3d23fdddef846ebb98b52122a6ece66211c0daf/shell/shell.qml> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3> · <https://github.com/omacom/omarchy/blob/v4.0.3/shell/shell.qml> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsToplevel.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/render/Renderer.cpp>

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

## omarchy update fails at migration 1787515927 on every retry (Bash 5.3 EXIT trap returns 1)

`omarchy-update-migration-1787515927-fails-bash-5-3` · severity: **high** · frequency: **occasional** · applies to: `arch`, `bash`, `chromium`, `firefox`, `omarchy`, `zen-browser`

**Symptom.** `omarchy update` aborts at the same migration on every retry, with nothing between the banner and the failure:

```
Running migration (1787515927)
Stop world-writable Chromium and Firefox policy directories

Something went wrong during the update!

Please review the output above carefully, correct the error, and retry the update.
```

`/tmp/omarchy-update.log` shows no error between the migration banner and the failure. Run on its own, the policy script writes the correct file and still reports failure:

```console
$ sudo -n /usr/bin/omarchy-theme-set-browser-policy 060b1e; echo "exit=$?"
exit=1
$ cat /etc/chromium/policies/managed/color.json
{"BrowserThemeColor": "#060b1e", "BrowserColorScheme": "device"}
```

Both reports were filed on 2026-08-28 against omarchy-dev builds with bash `5.3.15-1`. One reporter was on the dev channel, where `$OMARCHY_PATH` points at a linked `~/omarchy` checkout. The other was on the edge channel, running the packaged `omarchy 4.0.0.r1872.g7d58bb9-1` out of `/usr/bin` with no checkout. Stable 4.0.1 never shipped this migration and stable 4.0.2 shipped it already fixed, so only dev and edge installs between 2026-08-25 and 2026-08-29 could hit it.

**Cause.** The migration is fine. It calls `omarchy-theme-set-browser`, which runs `omarchy-theme-set-browser-policy`, and that script's `EXIT` trap was:

```bash
cleanup() { [[ -n $staged ]] && rm -f "$staged"; }
```

`staged` is cleared after each policy file is written, so on every successful run the test is false, the `&&` list short-circuits, and the handler's last status is 1. Bash 5.3 makes the exit status of the `EXIT` trap the script's exit status, where 5.2 did not, so `exit "$failed"` with `failed=0` became exit 1. The migration runs under `bash -euo pipefail`, aborts between its Chromium loop and its Firefox loop, and `omarchy-migrate` never writes its completion marker, which is why every retry fails identically and why the Firefox hardening never ran. Theme switching was unaffected because `omarchy-theme-set` does not run under `set -e`.

Minimal reproduction, no Omarchy needed:

```console
$ bash -c 'set -euo pipefail; staged=""; cleanup(){ [[ -n $staged ]] && rm -f "$staged"; }; trap cleanup EXIT; exit 0'; echo $?
1
```

A second reporter reproduced it on a machine where the migration had nothing to harden, which isolates it to the exit status and rules out a permissions edge case. The bad trap entered `quattro` on 2026-08-25 in commit `bafc9a1000`, which moved the colour write behind a passwordless helper. It was fixed in PR #8835, merged 2026-08-29 as commit `62eb5182`: the trap became an `if` block, and the migration now calls `omarchy-theme-set-browser || true` so a cosmetic repaint cannot block the Firefox hardening after it. Confirmed on an omarchy 4.0.2-1 install and at the v4.0.2 tag: `cleanup()` at line 82 of `/usr/bin/omarchy-theme-set-browser-policy` is an `if` block, and line 16 of the migration ends in `|| true`.

> **Audit corrected this record.** The mechanism is right in every detail and I confirmed the two named anchors plus the bash behaviour directly on this machine. Confirmed locally on omarchy 4.0.2-1 with bash 5.3.15-1: `cleanup()` starts at line 82 of /usr/bin/omarchy-theme-set-browser-policy and is an `if` block, and the script even carries the comment 'Bash 5.3 makes the EXIT trap's last command decide the script's exit status, so this handler must not end on a false test.' Line 16 of /usr/share/omarchy/migrations/1787515927.sh is `  omarchy-theme-set-browser || true`, guarded by `if (( repaired ))`. I ran the minimal reproduction from the cause and it returns 1, and the `if` form of the same handler returns 0, so the Bash 5.3 claim is exercised here and not taken on trust. Also confirmed locally: /usr/bin/omarchy-theme-set-browser takes no argument, calls the policy script with the theme hex and ends on `exit "$failed"`, the helper's BROWSER_POLICY_FIREFOX_DIRS is exactly /usr/lib/firefox/distribution and /opt/zen-browser/distribution, /usr/bin/omarchy-theme-set has no `set -e` and calls omarchy-theme-set-browser at line 329, `omarchy-migrate --pending` exists, and the marker path ~/.local/state/omarchy/migrations/1787515927.sh is real and already present here. Confirmed from upstream: the v4.0.1 tree has no migrations/1787515927.sh at all, and the v4.0.2 tree already has the `if` handler at line 82 and the `|| true` call, so 'v4.0.1 never shipped it and v4.0.2 shipped it fixed' holds. Commit 62eb5182d073191e62bee137bf8e2521414445cc is the merge of PR #8835 dated 2026-08-29T01:24:32Z and touches exactly bin/omarchy-theme-set-browser-policy, migrations/1787515927.sh and test/shell.d/browser-policy-dir-test.sh. Issue #8833 carries the same diagnosis, the same minimal reproduction and the `sudo -n` reproduction the record quotes. Issue #8832 is the original report and #8835 says 'Fixes #8832. Root cause diagnosed in #8833.' The second-reporter claim holds: jasonfried on #8833 reproduced it on a machine where both loops were no-ops, which is what rules out a permissions edge case. The interactive-sourcing warning holds: avenkidur sourced the migration and saw 'command not found: as_root', and jasonfried explained why that is an artefact of the interactive shell. The edge confirmation holds: avenkidur wrote 'I was able to do nothing and let a subsequent update run' and reported Chromium and /opt/zen-browser-bin/distribution at 0755 afterwards.

Two defects. First, the verify block's third line is wrong and I proved it here. `omarchy-theme-set-browser-policy; echo "exit=$?"` passes no argument, and the script starts with `if (( $# != 1 )); then usage; exit 1; fi`, so it prints its usage line and returns 1 on the fixed script too. Running it on this machine gave exit=1. The correct argument-free caller is `omarchy-theme-set-browser`, which is also the command the migration invokes. Second, open question Q5 is answerable, and both source records were half right, so the symptom's 'source-checkout builds' framing is wrong on its own. In #8832 avenkidur's System details say 'Omarchy Quattro Edge', but their own trace resolves $OMARCHY_PATH to /home/jon/omarchy and sources /home/jon/omarchy/install/helpers/browser-policy.sh, which is the dev-channel linked checkout rather than edge. In #8833 jasonfried gives omarchy 4.0.0.r1872.g7d58bb9-1, quotes /usr/bin/omarchy-theme-set-browser-policy and says the quattro copy is byte-identical to the installed one, which is the edge omarchy-dev package with no checkout. So one reporter was on dev and one was on edge. The date window is also off: the migration's epoch-derived id is 2026-08-23 20:12 UTC, but the file reached quattro on 2026-08-24 and the failing `staged` trap was only introduced on 2026-08-25T19:01:01Z by commit bafc9a1000 and fixed on 2026-08-28T23:00:03Z by commit 5925929cb6, merged 2026-08-29. Both issues were filed on 2026-08-28.

Not exercised: I did not run omarchy update, omarchy-migrate, omarchy-theme-set-browser or the policy script with a colour argument, since all of those write to /etc and I have no sudo. The marker-file workaround and the post-fix update rest on #8832 and #8833, not on me. The migration has already run on this machine, so I could not observe the failure itself.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** The marker-file workaround skips the migration that hardens world-writable browser policy directories. Check those directory modes first, and delete the marker later so the migration runs for real.

**Fix.**

**Omarchy 4.** Update to a build that carries commit `62eb5182`. v4.0.2 and later do:

```bash
omarchy update
```

One reporter on edge did nothing else and the next `omarchy update`, after the fix had landed, ran the migration through and left `/etc/chromium/policies/managed` and `/opt/zen-browser-bin/distribution` at `0755`.

**Stuck on a build before the fix.** Confirm it is this defect and not a real policy write failure:

```bash
omarchy-theme-set-browser; echo "exit=$?"         # exit=1 with a correct file below is this bug
cat /etc/chromium/policies/managed/color.json
bash -c 'set -euo pipefail; staged=""; cleanup(){ [[ -n $staged ]] && rm -f "$staged"; }; trap cleanup EXIT; exit 0'; echo $?
```

If the update itself is blocked and you cannot pull a fixed package, a reporter's workaround writes the migration's marker so it is skipped. Check first that the directories it hardens are already correct, because the marker stops the migration from ever running:

```bash
stat -c '%a %U:%G %n' /etc/chromium/policies/managed /opt/zen-browser/distribution /usr/lib/firefox/distribution 2>/dev/null
touch ~/.local/state/omarchy/migrations/1787515927.sh
omarchy-migrate --pending    # should print nothing
omarchy update
```

Delete that marker once a fixed package is installed if you want the migration to run for real. Do not source the migration into an interactive shell to debug it: one reporter did and saw `command not found: as_root`, which was an artefact of the interactive shell rather than the cause.

**Verify.** ```bash
grep -n -A3 '^cleanup()' /usr/bin/omarchy-theme-set-browser-policy   # an if block, not && rm
grep -n 'theme-set-browser' /usr/share/omarchy/migrations/1787515927.sh   # ends in || true
omarchy-theme-set-browser; echo "exit=$?"                             # exit=0 on the fixed script
omarchy-migrate --pending                                            # empty after a successful update
stat -c '%a %U' /etc/chromium/policies/managed /opt/zen-browser/distribution 2>/dev/null
```

Use `omarchy-theme-set-browser` and not `omarchy-theme-set-browser-policy` for the exit-status check. The policy script requires a six hex digit colour argument and prints its usage line and returns 1 without one, on the fixed script as well, so a bare call proves nothing.

Sources: <https://github.com/omacom/omarchy/issues/8832> · <https://github.com/omacom/omarchy/issues/8833> · <https://github.com/omacom/omarchy/pull/8835> · <https://github.com/omacom/omarchy/commit/62eb5182d073191e62bee137bf8e2521414445cc> · <https://github.com/omacom/omarchy/releases/tag/v4.0.2> · <https://github.com/omacom/omarchy/commit/bafc9a1000> · <https://github.com/omacom/omarchy/commit/5925929cb6> · <https://github.com/omacom/omarchy/blob/v4.0.2/bin/omarchy-theme-set-browser-policy> · <https://github.com/omacom/omarchy/blob/v4.0.2/migrations/1787515927.sh>

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

## 'Woah partner...': the Omarchy pacman guard aborts every direct pacman -Syu

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

## Fix the Bluetooth panel stuck on 'Turned Off' while bluetoothctl says Powered: yes

`bluetooth-panel-turned-off-while-adapter-powered` · severity: **medium** · frequency: **common** · applies to: `amd`, `bluetooth`, `desktop`, `hyprland`, `intel`, `laptop`, `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** The Omarchy shell's Bluetooth panel shows `Turned Off`, its switch is unchecked, and clicking the switch does nothing. The AVAILABLE list never fills, so no new device can be paired from the panel. Underneath, Bluetooth is fully working: `bluetoothctl show` reports `Powered: yes`, `rfkill list bluetooth` shows no block, `omarchy-bluetooth-power is-on` exits 0, and `bluetoothctl scan on` finds devices. Already-paired devices can still connect and play audio. Each click on the dead switch logs another `rfkill: unblock set for type bluetooth` in the journal. Reported on Omarchy 4.0.0-1 and 4.0.1-1 with `quickshell-git 0.3.0.r20.g28771c7` and packaged `quickshell 0.3.1-1`, on Intel 8087:0a2b and 8087:0032, Realtek RTL8852BU, Qualcomm QCA9377 and Broadcom BCM20702 controllers. It appears either at boot, when the controller's firmware finishes loading after the shell has started, or after a suspend and resume with Bluetooth left on.

**Cause.** Established in the thread by instrumented Quickshell logs from two reporters on different hardware and by a source read of Quickshell 0.3.1. `Panel.qml:24` is `readonly property var adapter: Bluetooth.defaultAdapter`, and `adapter.enabled` is a live binding onto BlueZ's `org.bluez.Adapter1.Powered` through Quickshell's `BluetoothAdapter`. Quickshell fills that cache from two places only: the property snapshot carried in BlueZ's `InterfacesAdded` or `GetManagedObjects` payload, and later `PropertiesChanged` signals. The `PropertiesChanged` subscription is installed in the adapter object's constructor, which runs strictly later than the moment BlueZ built the payload, and `BluetoothAdapter` is one of only two of Quickshell's D-Bus property groups that never calls `GetAll` to reconcile afterwards. A `Powered` transition landing in that gap is in neither source, so the cache keeps `false` and nothing repairs it for as long as `Powered` then stays `true`.

There are two ways into that gap, and they are different events. At boot the shell can build its **first** adapter object while the controller is still loading firmware, which is the Intel 8087:0a2b case at 1.44 seconds of firmware load. On resume BlueZ re-registers `hci0` after a firmware reload, Quickshell destroys the adapter object and builds a new one, and that snapshot arrives carrying `PowerState: Enabling` with `Powered: false` while BlueZ is still powering the controller up. Both instrumented logs record that exact pair as the last write to `Powered` in the whole session, and both logs count zero `GetAll` calls for `org.bluez` in a process that made well over a hundred for NetworkManager. The resume route does not need the USB device to be re-enumerated: one reporter's controller held the same bus address across every cycle and BlueZ still tore the adapter object down and rebuilt it after the rampatch reload.

Because `toggleBluetooth()` at `Panel.qml:635-637` sends a direction derived from the cached value, the switch sends `on` to an adapter that is already on, which is a no-op. The defect is in Quickshell, not in Omarchy's panel: the `v0.3.0` to `v0.3.1` diff touches no file under `src/bluetooth/` or `src/dbus/`, so `quickshell-git 0.3.0.r20.g28771c7` and packaged `quickshell 0.3.1` run identical code here. No fix had landed on either side as of 2026-09-11. Omarchy's bluetooth panel is unchanged through v4.0.3, and `v0.3.1` is still the newest Quickshell release.

> **Audit corrected this record.** Read omacom/omarchy#7573 in full with all six comments. It supports the record: the triage comment establishes the missing reconciliation from a Quickshell 0.3.1 source read, and two reporters later posted instrumented QT_LOGGING_RULES logs on different hardware (Intel AX210 8087:0032 and Qualcomm QCA9377 04ca:3015) showing PowerState Enabling with Powered false as the final write to Powered in the session, and zero GetAll calls for org.bluez against 165 and 187 for NetworkManager. Confirmed on this machine at omarchy 4.0.2-1 by reading /usr/share/omarchy/shell/plugins/panels/bluetooth/Panel.qml: line 24 is the Bluetooth.defaultAdapter binding, line 79 returns "Turned Off" on !adapter.enabled, line 512 gates the discovery retry timer on adapter.enabled, and lines 635 to 637 are the toggleBluetooth that sends a direction from the cached value. /usr/share/omarchy/bin/omarchy-bluetooth-power has the is-on subcommand the symptom cites, and its header comment confirms the rfkill soft block is the state that persists. The verify command ran here and printed `b true` with rfkill unblocked, so that command and its output format are confirmed. Two defects. First, the cause said BlueZ re-registers hci0 at boot and Quickshell drops the adapter object and builds a new one, which is wrong for the boot route: the first reporter's shell built its FIRST adapter object during a 1.44 second Intel firmware load, with no prior object to drop, so the two entry routes are different and the cause is rewritten to keep both. Second, the fix claimed an omarchy-bluetooth-power off then on cycle leaves the panel reading the cached value, and the thread contradicts that: an rfkill soft block removes the adapter object entirely and the panel renders "No adapter" (the #6956 state the report itself distinguishes), and one instrumented log shows an explicit unblock's Powered transition being caught normally 38 seconds after a subscription was installed. The off and on cycle is a coin flip against the same race, not a guaranteed no-op, and its real hazard is the persisted block, so the fix paragraph is rewritten. Verified today that no fix has landed: v4.0.2...v4.0.3 touches no file under shell/plugins/panels/bluetooth/, the last commit to that Panel.qml is 3af7675a on 2026-08-26 requiring textFormat on Text elements, no merged pull request covers it, and the newest upstream Quickshell tag is v0.3.1 which is exactly what Arch extra ships and what is installed here. NOT exercised: I did not suspend or resume this workstation, did not toggle the adapter, and did not run an instrumented shell, so I confirmed the code path and the contradiction rather than reproducing the latch.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Restart the shell. A fresh process takes a fresh snapshot of the adapter:

```bash
omarchy restart shell
```

Every reporter in the thread confirmed this clears it for the session. It recurs on the next boot or resume that hits the same window. To pair a device without restarting, use the CLI, which talks to BlueZ directly:

```bash
bluetoothctl scan on
bluetoothctl pair <MAC>
bluetoothctl connect <MAC>
```

Do not reach for an off and on cycle instead. The panel switch cannot perform one, because in this state it believes the adapter is already off and sends `on`, so you would have to run the helper by hand:

```bash
omarchy-bluetooth-power off
omarchy-bluetooth-power on
```

That is a coin flip rather than a cure. `off` sets an rfkill soft block, which removes the adapter object and makes the panel read `No adapter` instead, and `on` builds a new object against the same snapshot race, so it can latch `false` again. The block is also the half that systemd-rfkill persists across reboots, so an `on` that does not complete leaves Bluetooth switched off at the next boot. `omarchy restart shell` has neither failure mode.

**Verify.** Before restarting, confirm the mismatch:

```bash
busctl --system get-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Powered
```

`b true` while the panel says `Turned Off` is this bug. After `omarchy restart shell` the panel shows the adapter on, the switch responds, and the AVAILABLE list fills when the panel is open.

Sources: <https://github.com/omacom/omarchy/issues/7573> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/panels/bluetooth/Panel.qml> · <https://github.com/omacom/omarchy/blob/quattro/test/shell.d/bluetooth-test.sh> · <https://github.com/omacom/omarchy/compare/v4.0.2...v4.0.3> · <https://archlinux.org/packages/extra/x86_64/quickshell/> · <https://git.outfoxxed.me/quickshell/quickshell>

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

## The Gemini default agent will not install or sign in, and Omarchy has replaced it with Antigravity `agy`

`default-agent-gemini-fails-antigravity-replacement` · severity: **medium** · frequency: **common** · applies to: `antigravity`, `arch`, `gemini-cli`, `mise`, `omarchy`

**Symptom.** Choosing Gemini in the Omarchy menu under Setup, Defaults, Agent fails in one of two ways.

The mise install fails outright:

```
mise ERROR no tasks defined in ~/.local/share/mise/installs/gemini/0.56.0/node_modules/.mise/node-pty@1.0.0/node_modules/node-pty. Are you in a project directory?
mise ERROR Failed to install npm:@google/gemini-cli@latest: aube install failed: lifecycle script install failed for node-pty@1.0.0: script `install` exited with code Some(1)
Could not install Gemini with mise
```

Or the install succeeds and the sign-in fails in a full-screen terminal with no way to cancel, every time, after the browser half completes:

```
Failed to sign in. Message: This client is no longer supported for Gemini Code
Assist for individuals. To continue using Gemini, please migrate to the
Antigravity suite of products: https://antigravity.google
```

The manual says `agy` installs itself when run, but on stable `agy` is `command not found` and the menu still offers Gemini. Reporters gave omarchy 4.0.0-1, 4.0.2-1 and a fresh 4.0.2 install. The v4.0.1, v4.0.2 and v4.0.3 tags all carry the same menu entry and the same `omarchy-mise-install gemini` line, so every 4.0.x stable release is affected. `Super+Ctrl+Shift+A` and `omarchy refresh applications` reach the same failure.

**Cause.** Google stopped serving Gemini CLI requests for individual Google accounts on 2026-06-18 and withdrew the Login with Google path for them, which is what the sign-in error says. Google's own announcement reads: "On June 18, 2026, Gemini CLI and Gemini Code Assist IDE extensions will stop serving requests for Google AI Pro and Ultra, as well as those using it free of charge using Gemini Code Assist for individuals." Gemini CLI now needs a paid API key or an enterprise licence. Omarchy's menu entry still installs and selects it.

The maintainer replaced Gemini with Antigravity CLI (`agy`) in PR #6900, merged to `quattro` on 2026-08-20 as merge commit `ed7bae4ac`. That change makes `install/user/mise.sh` install `antigravity-cli` as `agy`, renames the menu key to `setup.default.agent.agy` labelled Antigravity, keeps `gemini` and `gemini-cli` as aliases resolving to `agy` in `omarchy-default-agent`, and adds migration `1786719479.sh`, which creates the lazy `agy` stub, rewrites a stored default of exactly `gemini` to `agy`, and removes the old `~/.local/bin/gemini` wrapper. Issues #6889, #8108, #8456 and #8553 were all closed as implemented on `quattro`, which the maintainer spelled out is not the same as shipped.

The stable package still has none of it. The backport is PR #8952, open against the `v4-0-2` branch as of 2026-09-11 and last updated 2026-09-08. v4.0.3 was published on 2026-09-08 without it, so the newest release is still affected. Checked at the v4.0.3 tag and on an omarchy 4.0.2-1 install: `install/user/mise.sh` still runs `omarchy-mise-install gemini`, there is no `migrations/1786719479.sh`, and `omarchy-menu.jsonc` still lists `setup.default.agent.gemini`. The v4.0.1 and v4.0.2 tags match.

> **Audit corrected this record.** Checked every claim against the v4.0.3 tag, the quattro branch, all six cited threads read in full with comments, and this omarchy 4.0.2-1 workstation. The three stable claims hold at the newest tag, not just at v4.0.2. Confirmed from upstream at v4.0.3 (published 2026-09-08): install/user/mise.sh line 4 still runs `omarchy-mise-install gemini`, the recursive tree carries no migrations/1786719479.sh, and default/omarchy/omarchy-menu.jsonc line 138 still carries setup.default.agent.gemini. v4.0.1 and v4.0.2 are the same. Confirmed on this machine: the same three facts, plus /usr/share/omarchy/bin/omarchy-default-agent accepts gemini and has no agy case so `omarchy-default-agent agy` hits the usage branch and exits 1, and `mise registry` maps both agy and antigravity-cli to aqua:google-antigravity/antigravity-cli while gemini maps to npm:@google/gemini-cli. Confirmed PR 6900: merged 2026-08-20T20:28:32Z into quattro as ed7bae4ac5a570e9df307486e0202fdafcc6ee24, touching install/user/mise.sh, bin/omarchy-default-agent, bin/omarchy-agent, default/omarchy/omarchy-menu.jsonc and migrations/1786719479.sh. Read the quattro copies: the menu key became setup.default.agent.agy labelled Antigravity, omarchy-default-agent line 36 resolves agy, antigravity, antigravity-cli, gemini and gemini-cli all to agent=agy, and the migration installs the stub then rewrites a stored default of exactly gemini to agy. PR 8952 is open today against base branch v4-0-2, last updated 2026-09-08, and its body confirms it is the backport of 6900. Two defects. First, the fix block has the channels backwards. It calls dev the thread's confirmed route and calls edge untested. In issue 6889, matheusdmlopes answered treeder with 'In stable branch isnt available yet. On edge channel, yes.' and treeder replied 'got it on edge, thx.' That is edge confirmed by a reporter for exactly this problem. Dev appears only in issue 8553 as GaleasAndres's suggestion, and developercrocodiles never tried it and switched to omp instead. So edge is confirmed and dev is the unconfirmed one. Second, open question Q4 is answerable. Issue 8108's body cites https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/ and I retrieved that page today, HTTP 200, 37445 bytes. It reads 'On June 18, 2026, Gemini CLI and Gemini Code Assist IDE extensions will stop serving requests for Google AI Pro and Ultra, as well as those using it free of charge using Gemini Code Assist for individuals.' PR 8952's body cites a second URL for the same date. The date belongs in the record with that citation rather than omitted. Smaller corrections folded into the rewrites: I read /usr/share/omarchy/bin/omarchy-mise-install, confirmed the two-argument form `<package> [command-name [bin-name]]` is supported so `omarchy-mise-install antigravity-cli agy` is valid, and confirmed it only writes an executable shim at ~/.local/bin/agy and prints nothing. The record made no claim about its output, so nothing needed fixing there, but the shim runs `mise use -g --quiet antigravity-cli` on every invocation and not only the first, so 'on first use' was reworded. The symptom claimed a report on 4.0.1-1 and no reporter states that version, so the symptom now names what reporters actually gave. The verify block claimed `agy --help` signs in, which help output does not do. Not exercised: I did not run omarchy-mise-install, omarchy-channel-set or agy, so the stub's behaviour after install and the sign-in with a personal Google account rest on odcpw on issue 8108 and toni-kk on issue 8553, not on me. ~/.local/bin/agy is absent here and ~/.local/bin/gemini is present, so nothing on this machine has run the new path.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Both channel switches replace the packaged `omarchy` and `omarchy-settings` with the `omarchy-dev` and `omarchy-settings-dev` packages from the edge pacman channel, so they bring unreleased changes with them and set a reboot-required state. `omarchy-channel-set dev` goes further: it clones the Omarchy source into `~/omarchy`, links Omarchy to that checkout with `omarchy-dev-link` so `OMARCHY_PATH` stops pointing at `/usr/share/omarchy`, and its own `gum` prompt says it is exclusively intended for developers working on Omarchy itself. Prefer the mise stub on a stable machine. If you do switch, edge is the lighter of the two and the one reporters confirmed, and `omarchy-channel-set stable` unlinks any checkout and puts the packaged tree back.

**Fix.**

**On stable, today.** Install the same stub the migration installs, then launch it by name. One reporter confirmed this on 4.0.2-1:

```bash
omarchy-mise-install antigravity-cli agy
agy
```

`omarchy-mise-install` takes `<package> [command-name [bin-name]]`, so that call writes an executable shim at `~/.local/bin/agy` and prints nothing. The shim exports `MISE_MINIMUM_RELEASE_AGE=0`, runs `mise use -g --quiet antigravity-cli` on every invocation, which installs the tool the first time and is a no-op after that, then runs `exec mise x antigravity-cli -- agy "$@"`. The mise registry already maps both `agy` and `antigravity-cli` to `aqua:google-antigravity/antigravity-cli`, so no extra plugin is needed. `omarchy-default-agent agy` will not work yet: the packaged `omarchy-default-agent` has no `agy` case, so it prints its usage line and exits 1 until PR #8952 lands.

**On a build that carries PR #6900.** Update, and migration `1786719479` installs the stub and rewrites a `gemini` default to `agy`:

```bash
omarchy update
omarchy-default-agent agy
```

Then Omarchy menu, Setup, Defaults, Agent, Antigravity. The thread's confirmed route to such a build is the **edge** channel, which swaps the `omarchy` and `omarchy-settings` packages for `omarchy-dev` and `omarchy-settings-dev` and leaves the packaged layout in place:

```bash
omarchy-channel-set edge
```

Two reporters on issue #6889 confirmed the Antigravity agent works on edge and is still missing on stable. The `dev` channel reaches the same code and was suggested on issue #8553, but nobody in the threads confirmed it for this, so treat dev as untested here. Both commands also sit behind Super+Space, Update, Channel. Return to the packaged tree later with:

```bash
omarchy-channel-set stable
```

Gemini's own configuration and credentials under `~/.gemini` are left in place either way. The migration does delete `~/.local/bin/gemini`, but only when that file is Omarchy's own generated wrapper, so a hand-written `gemini` launcher survives.

**Verify.** ```bash
ls -l ~/.local/bin/agy                                          # the stub omarchy-mise-install wrote
agy --help                                                     # installs antigravity-cli on first run, then prints help
grep -n 'antigravity' "$OMARCHY_PATH"/install/user/mise.sh     # on a build carrying PR #6900
ls "$OMARCHY_PATH"/migrations/1786719479.sh
cat ~/.config/omarchy/defaults/agent                           # agy once the migration has run
```

Signing in happens on a real `agy` run rather than on `--help`. One reporter on the fixed tree confirmed `agy` installs, signs in with a personal Google account and runs, and that the Agent submenu shows Antigravity checked.

Sources: <https://github.com/omacom/omarchy/issues/8108> · <https://github.com/omacom/omarchy/issues/8456> · <https://github.com/omacom/omarchy/issues/8553> · <https://github.com/omacom/omarchy/issues/6889> · <https://github.com/omacom/omarchy/pull/6900> · <https://github.com/omacom/omarchy/pull/8952> · <https://github.com/omacom/omarchy/blob/quattro/migrations/1786719479.sh> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-default-agent> · <https://github.com/omacom/omarchy/blob/quattro/default/omarchy/omarchy-menu.jsonc> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/user/mise.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/default/omarchy/omarchy-menu.jsonc> · <https://github.com/omacom/omarchy/blob/v4.0.1/install/user/mise.sh> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3> · <https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/>

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

## Stop the lock screen re-blanking a slow-waking monitor before it shows

`lock-screen-reblanks-slow-dpms-monitor` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `desktop`, `displayport`, `hyprland`, `nvidia`, `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** On Omarchy 4 (Quattro) a locked display does not wake reliably. One key press or mouse movement turns the monitor on but the lock screen never appears, or the password prompt shows for a moment and the monitor goes black again. Pressing keys or moving the mouse repeatedly eventually gets the lock screen up. `omarchy-shell` stays alive and there are no `FALLBACK` output or fatal Wayland errors in the journal, which separates this from the shell crash in #7380. The same hardware woke on the first press on Omarchy 3.

Seen on DisplayPort monitors that take more than five seconds to complete a DPMS wake: a ViewSonic VA3456-WQHD on an AMD Radeon 890M (Omarchy 4.0.0-1) and an ASUS XG32UCWMG at 3840x2160@240 on an RTX 2070 (Omarchy 4.0.0-1, issue #7399). The shipped value is unchanged on 4.0.2-1.

**Cause.** The Quickshell lock plugin blanks the display on a fixed one-shot timer. In `shell/plugins/lock/Service.qml` `idleBlankTimer` has `interval: 5000` with `repeat: false` (lines 415 to 417 on 4.0.2-1). `runWake()` (lines 167 to 170) starts `omarchy-system-wake` to turn DPMS on and, while `lockRequested` is true, immediately re-arms that timer. Nothing in the path observes whether the panel actually lit: `wakeProcess` has no completion handler (lines 405 to 407), and `omarchy-brightness-display on` returns once `hyprctl` has accepted the dispatch, not when the monitor shows a frame (`bin/omarchy-brightness-display:70`). A monitor whose DisplayPort wake handshake takes longer than five seconds is therefore blanked again before it becomes visible.

The budget is five seconds of inactivity on the lock surface rather than five seconds from the wake. `LockView.qml` emits `wakeRequested()` on pointer clicks and motion (lines 118 and 119) and on every keystroke and text change in the password field (lines 163 to 166 and 177 to 178), and the service maps that to `runWake()` at line 283, which re-arms the countdown. That is why repeated input eventually wins and why typing the password blind works.

A collaborator confirmed this reading against the source, and the reporter's controlled test (cloning the plugin and changing only the interval) confirmed it on hardware. A second user in #7399 fixed the same symptom the same way at 20000. The original reporter of #7399 saw no change at 30 seconds, so a second re-blank path exists on some hardware.

The interval is still a hardcoded literal in the newest release. `shell/plugins/lock/Service.qml` is byte-identical on this workstation (4.0.2-1) and at the `v4.0.1`, `v4.0.2` and `v4.0.3` tags, and `interval: 5000` is still hardcoded on the unreleased `quattro` branch as well. PR #7643, which makes it configurable as `idle.blank` in `shell.json`, was still open and unmerged on 2026-09-11, so the clone below is the only way to change the number on any shipped release.

> **Audit corrected this record.** Checked the record against the shipped source on this workstation (omarchy 4.0.2-1, Hyprland 0.56.2), against the `v4.0.1`, `v4.0.2`, `v4.0.3` and `quattro` copies of the file, and re-read issues #7749, #7399 and #7380 and PR #7643 in full today. The mechanism holds exactly as written. Confirmed on this machine, all read from the installed files. `idleBlankTimer` is `interval: 5000`, `repeat: false` at `/usr/share/omarchy/shell/plugins/lock/Service.qml:415-417`. `runWake()` at 167 to 170 starts `wakeProcess` and re-arms the timer when `lockRequested`. `wakeProcess` runs `omarchy-system-wake` (405 to 407) with no completion handler. `omarchy-system-wake` calls `omarchy-brightness-display on`, which dispatches `hl.dsp.dpms({ action = "enable" })` and exits without waiting for a frame (`bin/omarchy-brightness-display:70`), and skips the dispatch entirely when every active monitor already reports `dpmsStatus` true (line 69). `LockView.qml` emits `wakeRequested()` on clicks, pointer motion, keystrokes and text changes (118, 119, 163 to 166, 177 to 178), which `Service.qml:283` maps to `runWake()`. The tooling in the fix is real and works the way the record says. `omarchy-plugin-clone` builds the id as `${USER}.${source_id#omarchy.}`, copies the entry points, stamps `omarchy.clonedFrom`, enables the clone and calls `omarchy-shell shell rescanPlugins`. `resolveEnabledId` (`PluginRegistry.qml:146-157`) routes calls made with the built-in id to the enabled clone. The shell watches `~/.config/omarchy/plugins` with `inotifywait -m -r` (`PluginRegistry.qml:636-651`, and `inotify-tools 4.25.9.0-1` is installed), so a save does reload. `omarchy-plugin-remove` restores the `clonedFrom` source.

The cited issues do support the claims. #7749's opening post names the ViewSonic VA3456-WQHD on a Radeon 890M at Omarchy 4.0.0-1, quotes the same timer, and reports the controlled clone test at 15000. The `omarchybot` collaborator comment confirms the source reading and says plainly that it was not reproduced on hardware. #7399's reporter is a 6K ASUS ProArt PA32QCV who saw no change at 30000, and the commenter `orienw` is the ASUS XG32UCWMG at 3840x2160@240 on an RTX 2070 who was fixed by 20000, so the record attributes both correctly. #7380 is the separate FALLBACK shell-crash defect the record points at.

Two things needed changing, neither of them the mechanism. First, the date and release framing: I fetched `shell/plugins/lock/Service.qml` at every tag and the local file is byte-identical to `v4.0.2` and to `v4.0.3` (tagged 2026-09-08, the newest tag), and `interval: 5000` is still hardcoded even on `quattro` HEAD, where the only new timer is a 3000 ms `monitorDpmsTimer` that polls `hyprctl monitors` for video wallpapers and is not a readiness observer. PR #7643 reports `state: open` on 2026-09-11. The cause now says that, so the record cannot be read as describing a number that a release has already moved. Second, `danger` was empty and should not be. Enabling a clone of a non bar-widget plugin writes `omarchy.lock` into `disabledPlugins` in `~/.config/omarchy/shell.json` (`PluginRegistry.qml:523-525`, and the lock manifest's `kinds` is `["service"]`), and the `lock` IPC target lives inside the plugin (`Service.qml:510-511`), so a QML error in the clone leaves no lock service, and `omarchy-system-lock` sends `omarchy-shell lock lock` with output discarded and no exit check. The failure is a machine that silently stops locking, which is worth a danger on a fix that tells people to edit the lock screen's own source. I also added a `listPlugins` check to the fix and `--yes` to the remove command, since `omarchy-plugin-remove` refuses without a confirmation prompt outside a terminal.

Not exercised: I did not clone the plugin, did not edit any interval, did not lock this session and ran no DPMS or state-changing `hyprctl` command, because the audit is read-only here and Omarchy 4's lock surface cannot be released headlessly. The 15000 and 20000 values, the slow DisplayPort wake latency and the claim that a longer interval cures the symptom come from the two reporters in the issues rather than from anything I measured. Everything about the source, the plugin tooling and the clone's effect on `shell.json` is read from the installed files and from the upstream tags.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Enabling a cloned lock plugin turns the built-in one off, so a broken clone leaves the machine unable to lock. `PluginRegistry.qml:523-525` writes `omarchy.lock` into `disabledPlugins` in `~/.config/omarchy/shell.json` whenever the enabled clone declares a kind other than `bar-widget`, and the lock plugin's `manifest.json` declares `"kinds": ["service"]`. The `lock` IPC target lives inside the plugin itself (`Service.qml:510-511`), so a QML error in your copy means there is no lock service and no target for the `omarchy-shell lock lock` that `omarchy-system-lock` sends. That call discards its output and its exit status is not checked, so locking then fails silently and the session stays unlocked.

Change only the interval line, confirm the clone is loaded with `omarchy-shell shell listPlugins` before relying on it, and test with `omarchy-system-lock` while you are sitting at the machine. Do not test a lock-plugin clone over ssh on a headless or remote machine: Omarchy 4's lock surface is an `ext-session-lock` surface with no `unlock()` in its IPC, so the only ways back in are typing the password at the console or a reboot.

**Fix.**

Clone the built-in lock plugin into your config and raise the interval. Cloning switches the shell to your copy and routes the lock IPC calls to it (`PluginRegistry.qml` `resolveEnabledId`, line 146), so nothing else changes:

```bash
omarchy plugin clone omarchy.lock
```

That creates `~/.config/omarchy/plugins/<username>.lock/` (for user `dhh`, `dhh.lock`), enables it and switches the shell to it. Edit `Service.qml` in that directory and change the one line:

```qml
    interval: 5000
```

to

```qml
    interval: 15000
```

15000 worked for the ViewSonic reporter, 20000 for the #7399 commenter. Change nothing else: the same file holds the PAM flows and the `lock` IPC target, and a QML error in it leaves you with no lock screen at all. See the danger below.

Saving a file under `~/.config/omarchy/plugins/` reloads plugin code automatically, because the shell runs `inotifywait -m -r` on that directory (`services/PluginRegistry.qml:636-651`). Check the clone came back before you trust it:

```bash
omarchy-shell shell listPlugins | jq -r '.[] | select(.id | endswith(".lock")) | "\(.id) enabled=\(.enabled)"'
```

If the reload did not happen, force it:

```bash
omarchy-shell shell rescanPlugins
```

The clone stops tracking updates to the built-in lock plugin, so remove it once a release makes the interval configurable or fixes the race:

```bash
omarchy plugin remove <username>.lock --yes
```

Removing an active clone switches the shell back to the built-in `omarchy.lock`. The `--yes` matters only outside an interactive terminal, where `omarchy-plugin-remove` refuses to continue without a confirmation it cannot prompt for.

If raising the interval changes nothing, this is not your cause. The #7399 reporter saw no difference at 30 seconds, and a lock screen that never appears alongside `Got removal for monitor "FALLBACK"` in the journal is #7380 instead.

**Verify.** ```bash
omarchy-system-lock
```

Wait for the monitor to enter standby, then press Shift once. The monitor wakes and the lock screen stays visible without further input. `omarchy plugin list` shows `<username>.lock` enabled in place of `omarchy.lock`.

Sources: <https://github.com/omacom/omarchy/issues/7749> · <https://github.com/omacom/omarchy/issues/7399> · <https://github.com/omacom/omarchy/pull/7643> · <https://github.com/omacom/omarchy/issues/7380> · <https://github.com/omacom/omarchy/blob/v4.0.3/shell/plugins/lock/Service.qml> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/lock/Service.qml>

---

## Unstick migration 1786643346 when it insists a browser window is open

`migration-1786643346-browser-window-open-loop` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `brave`, `chromium`, `omarchy`, `vivaldi`

**Symptom.** `omarchy update` stops at migration `1786643346`, "Repair the Copy URL shortcut for profiles that predate its pinned extension id", and asks you to close the browser:

```
Close the browser windows to repair the Copy URL shortcut, then continue
```

It asks again however many times you confirm, with every browser closed, after `pkill -f` on all of them, and after several reboots. Declining prints:

```
A running browser would undo the Copy URL shortcut repair.
Close the browser windows, then run: omarchy-migrate
```

and exits 1. Because `omarchy-migrate` runs under `set -euo pipefail` and `omarchy-update` calls it under `set -e`, every migration sorting after it never runs and the rest of the update is skipped: the post-update hook, AUR packages, mise and the orphan cleanup. A pending-migration notification then appears at every login.

Reported on Omarchy 4.0.0-1 stable and after an Omarchy 3 to Quattro upgrade, with Brave, and confirmed by a second reporter with Vivaldi and Chromium.

**Cause.** Established in the threads and confirmed against the shipped migration on an omarchy 4.0.2-1 install, where `profile_open()` at line 129 reads:

```bash
profile_open() {
  [[ -L $1/SingletonLock || -e $1/SingletonLock || -S $1/SingletonSocket ]]
}
```

The migration never looks at processes or windows. It decides a Chromium-family profile is open purely from those filesystem markers in the profile's user-data-dir. Chromium-family browsers create `SingletonLock` as a symlink to `<hostname>-<pid>` and unlink it on a clean exit, but leave it behind after a crash, a `SIGKILL` or a hard power-off. It lives under `~/.config/`, so a reboot never clears it and `pkill` has nothing left to signal. The guard is a `while` loop, so a marker that is permanently present re-prompts forever.

`affected_profile_open()` gates on two sets of profiles rather than on browsers in general: the profiles whose `Preferences` still need the repair, and any profile root holding a `Preferences.omarchy-copy-url-repair.bak` from an attempt the migration has not yet verified. So the stale marker can sit in a profile you stopped using long ago. The second reporter's was an old Brave profile.

PR 7026 makes `profile_open()` read the `SingletonLock` symlink target and treat the lock as stale when `kill -0` on the PID it names fails. It is still open on 2026-09-11, and so is the competing PR 6872 against the same function. Upstream's review of 7026 is that its test is incomplete: `kill -0` returns `EPERM` for a live PID this user cannot signal, a PID reused after a reboot still reads as open, the hostname half of the target is discarded, and a lock left as a plain file or a profile with only `SingletonSocket` left behind still blocks. `profile_open()` is byte-identical on `quattro` today and at tag v4.0.3 (published 2026-09-08), so the manual removal below is still the fix on every shipped release up to and including 4.0.3.

> **Audit corrected this record.** Checked all three claims against the shipped migration on this workstation, which runs omarchy 4.0.2-1, and re-read both issues and the pull request today. Confirmed on this machine that `profile_open()` at lines 129 to 133 of `/usr/share/omarchy/migrations/1786643346.sh` tests only `-L $1/SingletonLock`, `-e $1/SingletonLock` and `-S $1/SingletonSocket`, with no liveness check on the PID the symlink names, and that the same function is byte-identical on `quattro` and at tag v4.0.3. Confirmed from the GitHub API that PR 7026 is still open on 2026-09-11, so the fix section stands. Confirmed on this machine that `grep -rn SingletonCookie /usr/share/omarchy/` returns nothing, so deleting `SingletonCookie` is harmless and is not what unsticks the migration, exactly as the record says. Also confirmed on this machine: `omarchy-migrate` sets `set -euo pipefail` at line 6 and runs each migration with `bash -euo pipefail` at line 93, touching the marker only after it succeeds at lines 94 to 95, and `omarchy-update` sets `set -e` at line 8 and calls `omarchy-migrate` at line 48, so the symptom's blast radius is right. The marker path and name in the verify block are right, `~/.local/state/omarchy/migrations/1786643346.sh`, and the record's `ls` globs cover all thirteen profile roots listed at lines 80 to 94. Both issues support the claim. Issue 7019 is the mechanism thread, and issue 7453 is the version and browser evidence, reporting Omarchy 4.0.0-1 after an Omarchy 3 to Quattro upgrade with Brave, with a second reporter on Vivaldi and Chromium. Three things needed correcting. The cause said the manual removal is the fix through 4.0.2, which went stale when v4.0.3 shipped on 2026-09-08 with the same unchanged function, and it did not mention PR 6872, the competing open PR, or upstream's own finding that 7026's `kill -0` test still misreads an `EPERM` PID, a reused PID, a foreign hostname and a socket-only profile. The danger was incomplete: it named `SingletonLock` only, although the fix also deletes `SingletonSocket` and the check accepts the socket alone, and it omitted the quiet failure the migration's own comments at lines 109 to 112 and 186 to 196 describe, where removal under a live browser gets the migration marked done while the browser reverts the repair on exit. I added the profile-directory warning because a reporter in 7019 deleted `~/.config/BraveSoftware` wholesale. The fix also claimed the two `rm` commands were what reporters confirmed, and they are not verbatim: both reporters' commands included `SingletonCookie`, so I kept the commands and described their provenance accurately. Not exercised: I did not delete any Singleton file, did not run `omarchy-migrate` or `omarchy update`, and this user has no Singleton files in any of those profile roots, so the unstick itself was not reproduced here and rests on both threads. Worth knowing but not a defect: the migration never removes `Preferences.omarchy-copy-url-repair.bak`, the only references being lines 75, 117 and 148, so a repaired profile stays eligible for the same gate if the completion marker is ever lost.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Only remove these markers while no Chromium-family browser is running, and the same caution covers `SingletonSocket` as well as `SingletonLock`, because the shipped check accepts either one on its own.

Removing them under a live browser does two kinds of damage. It lets a second instance open the same profile, which can corrupt that profile. It also defeats the prompt silently: the migration then repairs `Preferences` under the running browser, its own post-repair re-checks read the profile as closed too, `omarchy-migrate` writes the completion marker, and the browser writes its stale in-memory `Preferences` back when it exits. You are left with the migration recorded as done, the Copy URL shortcut still broken, and no prompt to tell you.

Do not delete a whole profile directory to clear the lock. One reporter removed `~/.config/BraveSoftware` outright, which loses that profile's bookmarks, history, saved passwords and extensions.

**Fix.**

With every Chromium-family browser genuinely closed, find the stale markers:

```bash
ls -l ~/.config/{chromium,google-chrome*,BraveSoftware/Brave-Browser*,microsoft-edge*,vivaldi,opera,helium}/Singleton* 2>/dev/null
```

Those globs cover all thirteen profile roots the migration scans, including the beta and nightly variants. A dangling symlink to a `<hostname>-<pid>` that no longer exists is the signature. Delete `SingletonLock`, and `SingletonSocket` if one is there, in whichever profile roots turn up. The shipped check accepts the socket on its own, so leaving it behind keeps the migration stuck. For the two combinations reporters were stuck on, Brave plus Chromium and Chromium plus Vivaldi:

```bash
rm -vf ~/.config/BraveSoftware/Brave-Browser/Singleton{Lock,Socket} ~/.config/chromium/Singleton{Lock,Socket}
rm -vf ~/.config/chromium/Singleton{Lock,Socket} ~/.config/vivaldi/Singleton{Lock,Socket}
```

Both reporters also deleted `SingletonCookie`, which sits beside them. That is harmless, and it is not what unstuck the migration: `SingletonCookie` appears nowhere in `/usr/share/omarchy`, so no shipped check looks at it.

Then run the migrations again, which also finishes the rest of the interrupted update:

```bash
omarchy-migrate
omarchy update
```

**Verify.** ```bash
omarchy-migrate                                            # runs to the end without the prompt
omarchy-migrate --pending                                  # prints nothing
ls ~/.local/state/omarchy/migrations/ | grep 1786643346    # the completion marker is written
```

No migration notification appears at the next login. Both reporters confirmed the migration ran through once the stale lock files were gone.

Sources: <https://github.com/omacom/omarchy/issues/7019> · <https://github.com/omacom/omarchy/issues/7453> · <https://github.com/omacom/omarchy/pull/7026> · <https://github.com/omacom/omarchy/blob/quattro/migrations/1786643346.sh> · <https://github.com/omacom/omarchy/pull/6872> · <https://github.com/omacom/omarchy/blob/v4.0.3/migrations/1786643346.sh> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3>

---

## Fix `Invalid TOML in config file: ~/.config/mise/config.toml` that keeps coming back

`mise-config-toml-corrupted-by-wrapper-race` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `desktop`, `laptop`, `mise`, `omarchy`

**Symptom.** Every mise-backed tool (`gh`, `claude`, `codex`, `opencode` and the rest of the wrappers in `~/.local/bin`) fails with:

```
mise::config::parse_error
Invalid TOML in config file: ~/.config/mise/config.toml
key with no value, expected `=`
```

The file ends in a fragment of a previous entry:

```toml
[tools]
gh = "latest"
st"
```

Deleting and recreating the file does not help, the fragment returns. The quieter form of the same bug is entries silently vanishing from `[tools]`, so a tool that worked yesterday now says it is not installed, and mise shims for services break with `mise ERROR No version is set for shim: npm`. Reported on Omarchy 4.0 with mise 2026.8.3 and again on 4.0.0.alpha after the 2026-08-19 upgrade.

**Cause.** Two mise bugs, both established by the maintainers' triage and by the reporter, who wrote the upstream fix. Every wrapper `omarchy-mise-install` writes into `~/.local/bin` runs `mise use -g <tool>` on every launch, which rewrites the whole global `config.toml`. Before mise 2026.8.7 that rewrite was in place rather than write-then-rename, so a shorter config written over a longer one left the tail of the old file behind: `[tools]\nclaude = "latest"\n` is 26 bytes, `[tools]\ngh = "latest"\n` is 22, and bytes 22 to 25 of the first are `st"`. Underneath that, `mise use -g` read and wrote the file with no lock, so two wrappers starting together lost each other's entries. Anything that launches a wrapper at high frequency makes it worse: an IDE polling GitHub through the `gh` wrapper produced 2,438 writes in two minutes and emptied a five-tool config within seconds.

> **Audit corrected this record.** Read omacom/omarchy#6948 in full with all four comments today. It supports the symptom, the cause and the byte arithmetic: TheTrueFerret reports the `st"` fragment and the in-place rewrite, reproduces entry loss with 16 concurrent writers on mise 2026.8.3, the maintainer triage names the two mise bugs, and saiqulhaq-hh reports 2,438 config writes in two minutes through an IDE polling the `gh` wrapper plus `mise ERROR No version is set for shim: npm`. I checked the byte math myself and it is right: `[tools]\nclaude = "latest"\n` is 26 bytes, `[tools]\ngh = "latest"\n` is 22, and offsets 22 to 25 of the longer file are `st"\n`. Both mise pull requests are merged (jdx/mise#12040 on 2026-08-15, jdx/mise#12069 on 2026-08-16) and both appear in the 2026.8.7 section of the mise CHANGELOG, with v2026.8.7 published 2026-08-17, so the version floor in the fix is correct. Confirmed on this machine: `pacman -Qi mise-bin` reports 2026.9.1-1 from Omarchy's own pacman repo and provides `mise`, `mise --version` prints 2026.9.1, `omarchy update` runs `omarchy-update-system-pkgs` and `omarchy-update-mise`, the generated wrappers in `~/.local/bin` still carry a per-launch `mise use -g`, `grep -h 'mise use -g' ~/.local/bin/*` prints exactly one package name per wrapper as the fix claims, and `mise use --help` confirms `mise use [TOOL@VERSION]...` accepts several tools in one call. The per-launch write is still the shipped pattern: `/usr/share/omarchy/bin/omarchy-mise-install` on 4.0.2-1, the same file at `quattro`, and at v4.0.3 all emit `mise use -g --quiet <package>` in the wrapper, and the only v4.0.3 change there is command-name validation and quoting, so nothing on the Omarchy side has removed the writer. One claim does not hold. The verify field says nobody in the thread has yet posted a post-2026.8.7 result, but the last comment is dated 2026-08-20 on a machine upgraded 2026-08-19, which is after v2026.8.7 shipped, and it never names a mise version, so it can be read neither as a post-fix failure nor as absent. I rewrote verify to say what the thread actually supports, and rewrote the fix to keep everything that was right while adding that `mise use -g` restores only plain `tool = "latest"` entries, so per-tool options are lost unless copied back from the saved file. This workstation carries exactly that shape, a `gemini` entry with `allow_builds`, so the repair as written would have silently dropped it. Not exercised: I did not run `mise use`, did not write `~/.config/mise/config.toml`, and did not reproduce the race, so the claim that 2026.8.7 closes it rests on the two merged pull requests and not on a measurement here.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Both fixes are in mise 2026.8.7 (released 2026-08-17): `#12040` writes the config atomically and `#12069` takes a cross-process lock around the read, edit and save inside `mise use`. Omarchy ships mise as the `mise-bin` package from its own pacman repo, so update and confirm the version:

```bash
omarchy update
mise --version        # 2026.8.7 or later
```

A workstation updated on 2026-09-11 has `mise-bin 2026.9.1-1`, so a current install is already well past that floor.

Then repair the file. If it is invalid TOML, move it aside, list the packages your wrappers expect, and re-add them in one command:

```bash
mv ~/.config/mise/config.toml ~/.config/mise/config.toml.bad
grep -h 'mise use -g' ~/.local/bin/*      # one line per wrapper, naming its package
mise use -g gh claude codex               # the packages from that list
```

`mise use -g` writes plain `tool = "latest"` entries, so any per-tool options you had are not restored. Read `~/.config/mise/config.toml.bad` and copy them back by hand. An entry of this shape is the case to watch for:

```toml
gemini = { version = "latest", allow_builds = ["@github/keytar", "node-pty"] }
```

If the file is valid but entries went missing, skip the `mv` and run only the `mise use -g` line with the missing packages.

Until the update has landed, launch wrapped tools one at a time rather than several at once. Two wrapper-side mitigations were posted in the thread (an `flock` around `mise use -g`, and skipping the write when `mise ls --current <tool>` already lists it) but each was confirmed by one person only, and `omarchy update` regenerates the wrappers over any edit.

**Verify.** ```bash
mise --version
cat ~/.config/mise/config.toml   # valid TOML, every wrapped tool listed under [tools]
gh --version
```

The two merged mise pull requests are the confirmation that the cause is closed: the atomic write removes the `st"` fragment and the cross-process lock stops concurrent `mise use -g` runs losing each other's entries. The Omarchy issue is still open as of 2026-09-11 and its last comment is from 2026-08-20. No comment in the thread names a mise version at or above 2026.8.7, and that last report, on a machine upgraded 2026-08-19, does not say which mise it ran, so it settles nothing either way. Treat this as an upstream fix that shipped rather than as a confirmed field result, and check `~/.config/mise/config.toml` again after a few days of normal use.

Sources: <https://github.com/omacom/omarchy/issues/6948> · <https://github.com/jdx/mise/pull/12040> · <https://github.com/jdx/mise/blob/main/CHANGELOG.md> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-mise-install> · <https://github.com/jdx/mise/pull/12069> · <https://github.com/jdx/mise/discussions/12067> · <https://github.com/jdx/mise/releases/tag/v2026.8.7> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-mise-install> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/user/mise.sh> · <https://github.com/omacom/omarchy/compare/v4.0.2...v4.0.3>

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

## Fix 'Codex limits unavailable' with the help text `initialize` in the Agents panel

`codex-limits-unavailable-agents-panel` · severity: **low** · frequency: **common** · applies to: `codex`, `mise`, `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** The Codex tab of the omarchy-shell Agents panel stops showing subscription limits. Local token and session statistics still count, but the limits area reads `Codex limits unavailable` with the bare help text `initialize` where a plan line and meters belong. Refreshing the panel does not recover it, and `codex login status` and `codex doctor` report a healthy login.

The stored record and the packaged collector both show it:

```console
$ jq '{limits, tierLabel, usageStatusText, authHelpText}' ~/.local/state/omarchy/agents/usage/codex.json
{
  "limits": [],
  "tierLabel": "",
  "usageStatusText": "Codex limits unavailable",
  "authHelpText": "initialize"
}
```

Launching app-server the way the collector does shows the real error:

```console
$ codex -s read-only -a untrusted app-server
error: invalid value 'untrusted' for '--ask-for-approval <APPROVAL_POLICY>'
  [possible values: on-request, never]
```

Reported on Omarchy 4.0.0-1 and 4.0.1-1 with codex-cli 0.149.0, 0.149.1 and 0.150.1, mostly installed through mise, by at least five reporters across six threads with more closed as duplicates.

**Cause.** `/usr/share/omarchy/bin/omarchy-agent-usage-codex` starts the Codex app-server at line 531 with `-a untrusted`. codex-cli 0.149 retired that approval-policy value and accepts only `on-request` and `never`, so `clap` rejects the argument and the process exits with status 2 before speaking JSON-RPC. The retirement is upstream Codex, not Omarchy: openai/codex#39630, "Retire the untrusted approval policy", merged to `main` on 2026-08-20, removes `untrusted` from the CLI, from the configuration schema and from the MCP tool interface.

The collector sends the child's stderr to `subprocess.DEVNULL` at line 534, so the rejection is invisible to it. What happens next is fast, not slow, and several comments on the issue threads get this backwards. `rpc_request()` does carry an 8 second deadline, but it is never reached. The child has already exited, so its stdout is closed: `select.select([proc.stdout], [], [], 0.25)` at line 483 reports it readable, `proc.stdout.readline()` at line 486 returns `""`, `if not line: break` at line 487 leaves the loop, and `raise TimeoutError(method)` at line 495 fires on the next statement. Collaborators measured that path at 42 to 44 ms on issue 7648 and at 7 to 8 ms on issue 7997. The handler at lines 559 to 561 then writes `str(exc)` into `authHelpText`, and `str(TimeoutError("initialize"))` is the bare method name. That is why the panel renders an RPC method name where an authentication hint belongs. Nothing about authentication is wrong.

At the time of the reports Omarchy's own `openai-codex-bin` package was still on 0.148.0, the last version that accepts `untrusted`, so the people hitting this had installed Codex another way, mostly mise. PR #7649, commit 4cd8a081, changed the value to `on-request` and merged to `quattro` on 2026-08-25 at 14:07 UTC, two hours and forty-three minutes after the v4.0.1 tag was published at 11:24 UTC, which is why every 4.0.1-1 install reproduces it.

Omarchy 4.0.2 and 4.0.3 both carry the fix. On an omarchy 4.0.2-1 workstation, checked on 2026-09-11, line 531 of the installed collector reads:

```
      [codex, "-s", "read-only", "-a", "on-request", "app-server"],
```

> **Audit corrected this record.** Checked every cited source again on 2026-09-11 and confirmed the mechanical claims on this workstation, which runs omarchy 4.0.2-1. Confirmed locally, four things. `grep -n '"-a"' /usr/share/omarchy/bin/omarchy-agent-usage-codex` returns exactly line 531 with `on-request`, so the record's closing quote is right. `find_command` is `shutil.which(name, path=ENV.get("PATH"))` at lines 90 to 91, so wrapping `codex` on PATH really is the mechanism the fix warns about. `omarchy-agent-usage-update` accepts `--force` and `--limits-only` as flags and treats any other word as an agent name, and it iterates `"$OMARCHY_PATH"/bin/omarchy-agent-usage-*` by absolute path, so `omarchy agent usage-update --force codex` is a valid invocation and nothing on PATH can shadow a collector. The collector's own argparse accepts `--limits-only` at line 582. codex-cli 0.153.4 is installed here through mise, and running `codex -s read-only -a untrusted app-server` printed the record's error text verbatim and exited 2, so the rejection still holds three minor versions past the reports. Confirmed from sources, three things. The blob at `v4.0.1` reads `untrusted` and the blobs at `v4.0.2` and `v4.0.3` read `on-request`. PR #7649 merged to `quattro` at 2026-08-25T14:07:17Z against the v4.0.1 tag published at 2026-08-25T11:24:30Z, which is two hours forty-three minutes rather than "about three hours", so I tightened it to the measured figure. All six issues exist and all describe this defect, five closed and #8460 still open, and the PATH-ordering trap in the fix is tony-roslund's comment on #8460 rather than an inference. Two things were wrong. First, the cause claimed `rpc_request()` raises after 8 seconds. It raises immediately, and I confirmed the path by reading lines 477 to 495 of the installed file: a closed pipe is reported readable by `select()`, `readline()` returns the empty string, `if not line: break` exits the loop, and the `raise` is the next statement, so the deadline is never consulted. Collaborator comments on #7648 and #7997 both correct this explicitly and give measurements of 42 to 44 ms and 7 to 8 ms. Second, the record's open question Q3 is answerable, so the record is not right to omit the upstream source. openai/codex#39630, "Retire the untrusted approval policy", is a pull request merged to `main` at 2026-08-20T07:04:50Z whose body states that it removes `untrusted` from the CLI, the configuration schema and the MCP tool interface. It is named in the omarchybot triage comment on #7648 and it retrieves cleanly, so I added it to the cause and to the sources. The symptom, fix and verify blocks are unchanged, because every claim in them held. Not exercised: I did not run `omarchy agent usage-update`, did not start `app-server` with an accepted policy, and did not open the Agents panel, so the restored plan line and meters are taken from reporters rather than observed here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

**Omarchy 4.** Update to 4.0.2-1 or newer, then regenerate the usage records:

```bash
omarchy update
omarchy agent usage-update --force codex
jq '{tierLabel, usageStatusText, limits}' ~/.local/state/omarchy/agents/usage/codex.json
```

**Stuck on 4.0.1-1 or older with no update available.** Make the same one-line change the merged commit makes. The file belongs to the `omarchy` package, so the next `omarchy update` overwrites your edit with the released fix, which is the outcome you want:

```bash
sudo sed -i 's/"-a", "untrusted", "app-server"/"-a", "on-request", "app-server"/' /usr/share/omarchy/bin/omarchy-agent-usage-codex
grep -n '"-a"' /usr/share/omarchy/bin/omarchy-agent-usage-codex
omarchy agent usage-update --force codex
```

Reporters across three of the threads verified `never` works equally well here, because the collector only sends `initialize`, `initialized`, `account/read` and `account/rateLimits/read` and never starts a model turn. Use `on-request` anyway, to match what shipped.

Do not try to fix it by wrapping `codex` in `~/.local/bin`. The collectors are called by absolute path under `$OMARCHY_PATH/bin`, and one reporter found omarchy-shell's `PATH` puts `~/.local/share/mise/shims` ahead of `~/.local/bin`, so the mise shim wins and the wrapper is ignored by the widget while the same test from a terminal succeeds. One reporter pinned codex-cli back to 0.148.0, the last version accepting `untrusted`, and nobody else confirmed that route.

**Verify.** ```bash
grep -n '"-a"' /usr/share/omarchy/bin/omarchy-agent-usage-codex     # expect -a on-request
codex -s read-only -a on-request app-server </dev/null; echo "exit $?"    # must not print 'invalid value'
omarchy-agent-usage-codex --limits-only | jq '{tierLabel, limits, usageStatusText, authHelpText}'
```

`tierLabel` shows your plan, `usageStatusText` is empty and `limits` lists the 5 hour and weekly windows. Reporters saw them return in under a second, and the Codex tab shows the plan line and meters after the next refresh.

Sources: <https://github.com/omacom/omarchy/issues/7648> · <https://github.com/omacom/omarchy/issues/7842> · <https://github.com/omacom/omarchy/issues/7873> · <https://github.com/omacom/omarchy/issues/7997> · <https://github.com/omacom/omarchy/issues/8032> · <https://github.com/omacom/omarchy/issues/8460> · <https://github.com/omacom/omarchy/pull/7649> · <https://github.com/omacom/omarchy/commit/4cd8a081cb67af345be7d8677faeee6575d89bef> · <https://github.com/omacom/omarchy/releases/tag/v4.0.2> · <https://github.com/omacom/omarchy/blob/v4.0.1/bin/omarchy-agent-usage-codex> · <https://github.com/omacom/omarchy/blob/v4.0.2/bin/omarchy-agent-usage-codex> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-agent-usage-codex> · <https://github.com/openai/codex/pull/39630>

---

## Stop ttfx dumping core every time the screensaver is torn down by the lock

`ttfx-screensaver-core-dump-on-lock` · severity: **low** · frequency: **common** · applies to: `desktop`, `laptop`, `omarchy`, `ttfx`

**Symptom.** On Omarchy 4.0.0-1 with `ttfx 0.3.1-1`, idling through the screensaver into the lock (or dismissing the screensaver) leaves a `ttfx` core dump behind and a "Process crashed" notification. `coredumpctl list | grep ttfx` shows `SIGABRT` entries, one per screensaver renderer, so one per monitor when the screensaver was up on all of them. The panic recovered from the core:

```
thread 'main' (7320) panicked at library/std/src/io/stdio.rs:1166:9:
failed printing to stderr: Input/output error (os error 5)
```

Reported on an Intel i7-4770HQ machine and a Framework 13 AMD laptop in issue 6995, with foot as the screensaver terminal, and on Ghostty 1.3.1 in the related issue 6762, all with `idle: {screensaver: 150, lock: 300}`.

**Cause.** `ttfx`, the screensaver renderer, is painting into a terminal that the lock script or the screensaver dismiss has already closed. Its next write fails with `EIO`, it reports that error with `eprintln!`, stderr is the same dead pty, and the report itself panics. Release builds abort on panic, hence `SIGABRT` and a core. Three routes into the same abort are documented across the thread and its linked issues: the lock script killing an already running screensaver (#6762, #6764), the screensaver supervisor loop respawning a renderer into a terminal that is being closed, and the one this issue reports, the idle service starting a fresh cycle and launching a second screensaver into a lock that is still being requested. The collaborator triage confirmed that last one in source: `lockSystem()` spawns `omarchy-system-lock` as a subprocess and about a second passes before `lock-requested` is set, `startIdleCycle()` consults no lock state, and with `screensaver <= lock` the delay is 0, so any idle re-assertion in that second launches a screensaver immediately.

> **Audit corrected this record.** Confirmed on this workstation: `pacman -Qi ttfx` reports 0.3.2-1 with build date Mon 17 Aug 2026, which is the date and version the record gives. The [omarchy] stable repo carries `ttfx 0.3.2-1` today (fetched pkgs.omarchy.org/stable/x86_64/omarchy.db), so `omarchy update` is the right instruction. The cause is verified line by line in /usr/share/omarchy/shell/plugins/services/idle/Service.qml: `lockSystem()` at line 71 clears `idledThisCycle` at 76 and spawns `omarchy-system-lock` as a subprocess at 79, `startIdleCycle()` at 82 to 98 consults no lock state at all, and `screensaverDelaySeconds` is `max(0, screensaver - min(screensaver, lock))` at lines 23 and 24, so it is 0 whenever `screensaver <= lock` and line 93 launches the screensaver immediately. The record's paraphrase of the collaborator triage is therefore more precise than the triage itself and is correct. /usr/share/omarchy/bin/omarchy-screensaver lines 9 to 14 send `pkill -x ttfx` and `pkill -f '[o]rg.omarchy.screensaver'` back to back with no wait, and lines 38 to 48 respawn a renderer as soon as the old one disappears, which are the other two routes the cause names. `coredumpctl list ttfx --since '-1h'` runs cleanly here, so the verify block is valid syntax. From sources: omacom-io/ttfx#18 "Stop dumping core when the terminal goes away" merged to master on 2026-08-17, and its diff matches the record exactly. It adds `output_closed()` treating EIO and BrokenPipe on tty output as the terminal going away and returning `RunOutcome::OutputClosed`, and it replaces `println!`/`eprintln!` with non-panicking `outln!`/`errln!` macros whose own doc comment reproduces the record's panic text and states that a release build aborts on panic. ttfx's Cargo.toml confirms `[profile.release] panic = "abort"`, so the record's SIGABRT explanation is right for this binary rather than a wrong generalisation about Rust. Issue 6995 supports the symptom, the panic location, the three routes and the isLocked window. PRs 7131 and 7132 are both still open, checked today. One thing was wrong. `Reported on Intel and AMD laptops and NVIDIA desktops` is not supported: no NVIDIA report appears in issue 6995, or in 6762, 6764 or omacom-io/ttfx#10. What is attested is an Intel i7-4770HQ machine and a Framework 13 AMD laptop. `ghostty` is attested, but in issue 6762, which the cause names by number and the record did not cite, so 6762 and 6764 are added to sources along with the two open PRs. The unmerged-PR date was also refreshed from 2026-09-07 to 2026-09-11, which is the day it was rechecked. Not exercised: no crash was reproduced here. This machine already runs the fixed ttfx 0.3.2-1, and idling it into the lock to test the old behaviour is not possible read-only, so the before state and the one-core-per-monitor shape come from the reporters rather than from a local run. `danger` is left empty, which is right: the fix is `omarchy update`, the supported upgrade path, and the failure loses nothing but a core file.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The fix is `ttfx 0.3.2` (omacom-io/ttfx#18, "Stop dumping core when the terminal goes away", merged 2026-08-17): a failed write to the tty is dropped instead of panicking, and `EIO`/`EPIPE` on the output tty ends the run quietly with exit 0. Omarchy's `[omarchy]` package repository carries `ttfx 0.3.2-1` (built 17 August 2026, confirmed on this machine).

```bash
pacman -Q ttfx      # 0.3.1-1 is affected
omarchy update
pacman -Q ttfx      # 0.3.2-1
```

The Omarchy-side race, a second screensaver launched into a pending lock, is still open: PRs #7131 and #7132 are unmerged as of 2026-09-11. With `ttfx 0.3.2` the terminal is still torn down abruptly, but the renderer exits instead of dumping core.

**Verify.** After the update, idle through the screensaver into the lock, unlock, then check that no new entry appeared:

```bash
coredumpctl list ttfx --since '-1h'
```

Sources: <https://github.com/omacom/omarchy/issues/6995> · <https://github.com/omacom/ttfx/pull/18> · <https://github.com/omacom/omarchy/issues/6762> · <https://github.com/omacom/omarchy/issues/6764> · <https://github.com/omacom/omarchy/pull/7131> · <https://github.com/omacom/omarchy/pull/7132> · <https://github.com/omacom/ttfx/blob/master/Cargo.toml>

---

## Dismiss the "Process crashed" notification, or turn crash capture off

`crash-capture-notification-dismiss-or-disable` · severity: **low** · frequency: **occasional** · applies to: `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** Omarchy 4 shows a critical "Process crashed" notification whenever a process dumps core. Clicking it launches `omarchy-agent-crash`, the AI crash diagnosis. There is no visible close control on the toast, and because the notification is critical it does not expire, so the only obvious way to make it go away is to start a diagnosis you did not want. People who crash programs on purpose (compiler and debugger work) get one after every crash. Reported on Omarchy 4.0.0-1.

**Cause.** `omarchy-crash-watch`, run by the user unit `omarchy-crash-watch.service`, sends the toast with `--urgency critical` and `--exec omarchy-agent-crash`, so a left click on the card runs the diagnosis. The toast never expires on its own: `durationFor()` in `shell/plugins/notifications/Service.qml:102-105` returns 0 for `NotificationUrgency.Critical`, and the popup countdown only runs while that duration is above zero.

No shipped Omarchy 4 release puts a close button on the notification card. `shell/plugins/notifications/components/NotificationCard.qml` is byte-identical on this workstation (omarchy 4.0.2-1) and at the `v4.0.1`, `v4.0.2` and `v4.0.3` tags, and the only pointer handling in it is one full-card `MouseArea` at line 77 with `acceptedButtons: Qt.LeftButton | Qt.RightButton`, which maps the right button to `closeRequested()` and every other button to `cardClicked()`. A hover-revealed `✕` was added to that file on the unreleased `quattro` branch after `v4.0.3`, and the two open pull requests argue over it rather than introduce it: #8980 keeps it on without hover, #9010 replaces it with a themed `PanelActionButton`. Both were still open on 2026-09-11. So on every release through v4.0.3 the right click is the only dismiss gesture the card offers, and there is nothing on screen to say so.

> **Audit corrected this record.** Checked every claim against the shipped source on this workstation (omarchy 4.0.2-1, Hyprland 0.56.2) and against the upstream tags, and re-read issue #7711 in full today. Confirmed on this machine, all read from the installed files. `/usr/share/omarchy/bin/omarchy-crash-watch` sends `--urgency critical` with `--exec omarchy-agent-crash`. `/usr/lib/systemd/user/omarchy-crash-watch.service` carries `ConditionPathExists=!%h/.local/state/omarchy/toggles/crash-capture-off`. `omarchy-toggle-crash-capture` calls `omarchy-toggle crash-capture-off`, stops the unit and sends "Crash capture disabled". `omarchy-toggle-enabled` tests `$HOME/.local/state/omarchy/toggles/<flag>`. The menu entry is `trigger.toggle.crash-capture` with label "Crash Capture" in `/usr/share/omarchy/default/omarchy/omarchy-menu.jsonc:87`, under `trigger` ("Trigger") and `trigger.toggle` ("Toggle"). `SUPER + SPACE` is the Omarchy menu in `/usr/share/omarchy/default/hypr/bindings/utilities.lua:1`. `core_pattern` pipes to `/usr/lib/systemd/systemd-coredump` from systemd 261.2-1, so dumps survive the watcher being off. `NotificationCard.qml:77-87` maps the right button to `closeRequested()`, which `Service.qml:1055` routes to `service.dismissPopup()`, so right-click dismiss is real. Issue #7711 does support the symptom: the reporter asks for a visible dismiss affordance on Omarchy 4.0.0-1, one commenter answers "You can still right click to dismiss it", and two more name the crash-capture toggle and place it in the menu under triggers.

One claim was wrong. The cause said the close affordance "is only revealed on hover", which the record took from a commenter summarising the two pull requests. No release has any close button at all: I fetched `NotificationCard.qml` at `v4.0.1`, `v4.0.2`, `v4.0.3` and `quattro`, and the local file is byte-identical to both `v4.0.2` and `v4.0.3` while only `quattro` HEAD (unreleased, after the v4.0.3 tag of 2026-09-08) adds the hover-revealed `✕` that #8980 and #9010 then fight over. The cause is rewritten to say that, and the "neither merged as of 2026-09-07" date is refreshed: `gh api repos/omacom/omarchy/issues/8980` and `/9010` both report `state: open` on 2026-09-11. I also added the `OMARCHY_CRASH_IGNORE` drop-in to the fix, because the symptom's own audience is people who crash programs deliberately and the shipped watcher already supports skipping named binaries without giving up crash capture.

Not exercised: I did not crash a process, did not toggle crash capture, and did not click a toast, because this audit is read-only on the workstation. The right-click gesture, the toast's non-expiry and the drop-in are therefore confirmed from source and from systemd's documented drop-in behaviour rather than from a live trial. `ulimit -c` is unlimited and `DefaultLimitCORE=infinity`, so the record's `sleep 100 & kill -SEGV $!` check should produce a dump here, but I did not run it.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Dismiss one toast: right-click it. The notification card handles a right button click as a close request and a left click as the card's action (`shell/plugins/notifications/components/NotificationCard.qml:77-87` on Omarchy 4.0.2-1, wired to `service.dismissPopup()` at `Service.qml:1055`). One commenter reported this and it holds in the shipped source.

Stop the notifications altogether: toggle crash capture off. Two reporters confirmed the toggle exists. Either from the Omarchy menu, Super+Space, then Trigger, Toggle, Crash Capture, or from a terminal:

```bash
omarchy-toggle-crash-capture
```

That writes the flag `~/.local/state/omarchy/toggles/crash-capture-off`, stops `omarchy-crash-watch.service` for this session, and sends a "Crash capture disabled" notification. The unit carries `ConditionPathExists=!%h/.local/state/omarchy/toggles/crash-capture-off`, so it stays off on the next login until you run the same command again, which removes the flag and starts the watcher.

Silence only the programs you crash on purpose, and keep the rest: `omarchy-crash-watch` reads an extended regex of process names to skip from `OMARCHY_CRASH_IGNORE`, matched against the executable's basename. Set it on the unit rather than in your shell, because the watcher is a systemd user service and does not inherit your interactive environment:

```bash
mkdir -p ~/.config/systemd/user/omarchy-crash-watch.service.d
cat > ~/.config/systemd/user/omarchy-crash-watch.service.d/ignore.conf <<'EOF'
[Service]
Environment=OMARCHY_CRASH_IGNORE=^(cc1|cc1plus|lldb|my-test-binary)$
EOF
systemctl --user daemon-reload
systemctl --user restart omarchy-crash-watch.service
```

The same mechanism exposes `OMARCHY_CRASH_DEDUPE_SECONDS`, which defaults to 60 and is the window in which one program is announced at most once.

Core dumps are still captured by systemd-coredump with the watcher off or the pattern set. `/proc/sys/kernel/core_pattern` pipes to `/usr/lib/systemd/systemd-coredump` regardless, only the notification and the one-click diagnosis go away, and `coredumpctl list` still works.

**Verify.** ```bash
omarchy-toggle-enabled crash-capture-off && echo off
systemctl --user is-active omarchy-crash-watch.service
```

`off` and `inactive` while disabled. Crash something (`sleep 100 & kill -SEGV $!`) and no toast appears.

Sources: <https://github.com/omacom/omarchy/issues/7711> · <https://github.com/omacom/omarchy/pull/8980> · <https://github.com/omacom/omarchy/pull/9010> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/notifications/components/NotificationCard.qml> · <https://github.com/omacom/omarchy/blob/v4.0.3/shell/plugins/notifications/components/NotificationCard.qml>

---

## Apply a shell plugin edit that the automatic reload silently ignores

`omarchy-plugin-edit-not-applied-until-shell-restart` · severity: **low** · frequency: **occasional** · applies to: `desktop`, `laptop`, `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** You edit a plugin under `~/.config/omarchy/plugins/<id>/` (or run `omarchy plugin update <id>`). The shell logs `Local plugin changed, reloading: <id>` and re-creates the widget or service, but it keeps running the old code: a changed label never appears, a `Component.onCompleted: console.warn(...)` marker never fires, and a service's `IpcHandler` still answers with the previous behaviour. Reported by four plugin authors on Omarchy 4.0.0-1 with quickshell 0.3.0 (r20.g28771c7) and Qt 6.11.2, for bar widgets and for service plugins.

**Cause.** Confirmed in source, both on a 4.0.2-1 install and at the current upstream tags. The reload path in `shell/shell.qml` guards its cache flush with

```qml
if (typeof Qt.clearComponentCache === "function") Qt.clearComponentCache()
```

but `clearComponentCache()` is a plain C++ method on `QQmlEngine` and is not exposed on the QML `Qt` object, so the branch never runs. Every plugin entry point is then loaded by a URL that does not change when a file is edited, through `Qt.createComponent` for services and bar widgets and through a `Loader` for panels and for a replacement bar, so the engine hands back the previously compiled component. `omarchy plugin update` ends in `omarchy-shell shell rescanPlugins`, which takes the same path.

The guard arrived in 4.0.0-beta3 and is unchanged in 4.0.0, 4.0.1, 4.0.2, 4.0.3 and on `quattro`. Only its position moves, so find it by content:

```bash
grep -n clearComponentCache /usr/share/omarchy/shell/shell.qml
```

That is line 757 on omarchy 4.0.2-1 and line 1470 in v4.0.3, which shipped on 2026-09-08 and rewrote much of that file without touching this line.

Two pull requests offer fixes and neither has landed as of 2026-09-11: `#9606` (restart the shell when the cache cannot be cleared, closed unmerged on 2026-09-06) and `#8766` (`Quickshell.reload(false)`, still open and gated on quickshell-mirror/quickshell#956, a use-after-free at engine generation teardown that is also still open).

One case is stale by design rather than by this bug. From 4.0.3, `shell/README.md` states that a service marked `keepLoaded` stays mounted across a plugin hot reload so that tearing down a changed widget cannot destroy `omarchy.lock` while the session is locked. That instance is never replaced, so edits to a `keepLoaded` service take effect only on a shell restart even if the component cache is fixed.

> **Audit corrected this record.** Read omacom/omarchy#6981 in full with all five comments today. It supports the record: farangkao's report names the dead guard and the URL-keyed component cache, aTotland and ryenski reproduce the stale marker on bar widgets, h3nr1-d14z reproduces it on a service whose `IpcHandler` keeps answering with the old code, and the maintainer triage confirms it in source and names the four load sites. Four plugin authors and three marker confirmations, which is what the record claims. Confirmed on this machine rather than from the thread: `grep -n clearComponentCache /usr/share/omarchy/shell/shell.qml` returns line 757 on omarchy 4.0.2-1, the shipped `finishPluginReload()` is unchanged from the quoted form, the four load sites are `Qt.createComponent(url, Component.PreferSynchronous)` for services at line 294, `Qt.createComponent(url, Component.Asynchronous)` for bar widgets at line 795, and `Loader { source: ... }` for panels at line 624 and for a replacement bar at line 250. `/usr/share/omarchy/bin/omarchy-plugin-update` ends in `omarchy-shell shell rescanPlugins`, not a restart, so `omarchy plugin update` takes the same stale path. `omarchy-refresh-shell` does run `omarchy-refresh-config omarchy/shell.json` and `omarchy-bar defaults` before restarting, and both it and `omarchy-restart-shell` are byte-identical to the `quattro` copies, so the warning about `omarchy refresh shell` is right. `omarchy-launch-shell` pipes the shell through `systemd-cat -t omarchy-shell`, and `journalctl --user -b -t omarchy-shell` on this box shows QML `WARN` lines, so the verify command works as written. What needed correcting is the version anchoring, which is why I did not mark this `ok`. v4.0.3 shipped on 2026-09-08 and rewrote much of `shell/shell.qml` (+742 / -29), so the guard is now line 1470 there and line 1459 at `quattro` HEAD (b5589faa, 2026-09-11), while the record pins only line 757 and only 4.0.2-1. The bug itself survives: I fetched `shell/shell.qml` at v4.0.0-beta3, v4.0.0, v4.0.1, v4.0.2, v4.0.3 and `quattro`, and the dead guard and the unchanged-URL loading are in every one of them, so the v4.0.3 plugin work did not fix this. v4.0.3 also adds a second, deliberate route to the same symptom that the record should carry: `shell/README.md` now states that a `keepLoaded` service survives a plugin hot reload and is not replaced, so code changes to that kind of service need a restart by design. I rewrote the cause to cover both releases, to give a grep instead of a bare line number, and to date the two pull requests, which I re-checked today: #9606 closed unmerged 2026-09-06 and #8766 still open, gated on quickshell-mirror/quickshell#956, which is also still open. The fix, symptom, verify and the empty danger all held and I left them alone. Not exercised: I did not edit a plugin, did not restart the shell and did not run any `omarchy plugin` subcommand, so the restart remedy rests on the three marker confirmations in the thread and on reading the shipped scripts, not on a test here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Restart the shell after any plugin change. A fresh process compiles the plugin from source:

```bash
omarchy restart shell      # same as: omarchy-restart-shell
```

Do not use `omarchy refresh shell` for this. That command runs `omarchy-refresh-config omarchy/shell.json` and `omarchy-bar defaults` before restarting, so it resets your shell configuration. `omarchy-restart-shell` refuses to run while the session is locked, so unlock first.

**Verify.** Add a marker to the plugin before restarting and look for it afterwards:

```qml
Component.onCompleted: console.warn("plugin reloaded")
```

```bash
omarchy restart shell
journalctl --user -b -t omarchy-shell -n 50 --no-pager | grep 'plugin reloaded'
```

Three reporters confirmed the marker fires only after the restart, never after the automatic reload.

Sources: <https://github.com/omacom/omarchy/issues/6981> · <https://github.com/omacom/omarchy/blob/quattro/shell/shell.qml> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-restart-shell> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-refresh-shell> · <https://github.com/omacom/omarchy/pull/9606> · <https://github.com/omacom/omarchy/pull/8766> · <https://github.com/omacom/omarchy/issues/9772> · <https://github.com/omacom/omarchy/blob/v4.0.3/shell/shell.qml> · <https://github.com/omacom/omarchy/blob/v4.0.2/shell/shell.qml> · <https://github.com/omacom/omarchy/blob/v4.0.0-beta3/shell/shell.qml> · <https://github.com/omacom/omarchy/blob/v4.0.3/shell/README.md> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-plugin-update> · <https://github.com/omacom/omarchy/compare/v4.0.2...v4.0.3> · <https://github.com/quickshell-mirror/quickshell/issues/956>

---
