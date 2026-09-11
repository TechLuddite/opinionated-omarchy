# GPU & drivers

39 problems. Sorted by severity, then by how often users hit it.

## Repair a DKMS driver that did not rebuild after a kernel update

`dkms-nvidia-build-fails-after-kernel-update` · severity: **critical** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** After a system upgrade (`omarchy update` on Omarchy 4, `sudo pacman -Syu` on plain Arch) and a reboot you land in a TTY or a black screen. `nvidia-smi` says `NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver`, `modprobe nvidia` reports `Module nvidia not found in directory /lib/modules/<version>`, and `dkms status` shows the module built only for the *old* kernel.

**Cause.** DKMS rebuilds out-of-tree modules on kernel upgrade, driven by the pacman hooks `/usr/share/libalpm/hooks/70-dkms-upgrade.hook` and `70-dkms-install.hook`. It fails quietly when the matching `*-headers` package for the kernel you booted is missing, when the build errors out against a new kernel API, or when the pacman transaction was interrupted. The rebuild failure scrolls past in the pacman output and is easy to miss. Omarchy 4 adds a second way to land here with a module that did build fine: the machine boots a Unified Kernel Image written by `limine-mkinitcpio-install`, not a plain initramfs, so a module rebuilt by hand and followed by `mkinitcpio -P` never reaches the image the machine actually boots.

> **Audit corrected this record.** The generic DKMS mechanism in the record holds, and I confirmed the pieces on this machine. `/usr/share/libalpm/hooks/70-dkms-upgrade.hook` and `70-dkms-install.hook` drive the rebuild, `dkms status` reports `nvidia/610.57.04, 7.1.9-arch1-2, x86_64: installed`, and reading /usr/bin/dkms (3.4.3) confirms `dkms autoinstall` and `dkms autoinstall -k "$(uname -r)"` are both valid: the autoinstall branch calls have_one_kernel, which bans --all and defaults to the running kernel. The man page on this machine confirms `dkms remove [module/module-version] [-k kernel/arch] [--all]`, so that command is right too. The make.log path is right for a failed build: dkms writes it to the build dir and only moves it to <kernel>/<arch>/log/make.log after a successful install (/usr/bin/dkms line 1708). Three defects, and the first two are severe. First, `sudo mkinitcpio -P` writes no new boot image on Omarchy 4, which makes the whole fix a no-op on the distro the record claims to cover. Confirmed here: /etc/mkinitcpio.d contains zero entries, mkinitcpio takes its presets from that directory (/usr/bin/mkinitcpio line 25 sets _d_presets to /etc/mkinitcpio.d), and the stock kernel hook is replaced by /etc/pacman.d/hooks/90-mkinitcpio-install.hook, which calls /usr/share/libalpm/scripts/limine-mkinitcpio-install to write a UKI at /boot/EFI/Linux/omarchy_linux.efi. /usr/local/bin/mkinitcpio, shipped by limine-mkinitcpio-hook and ahead of /usr/bin in PATH, warns that -P does not update Limine boot entries and then prompts interactively, which is useless in a chroot with no tty. The Arch wiki Limine page says to run limine-mkinitcpio instead of mkinitcpio. Second, the danger tells the user to keep linux-lts installed as a fallback boot entry, and the fix tells them to boot the previous kernel from the bootloader menu. Neither exists on a stock Omarchy 4 install. `limine-list` on this machine prints one kernel entry under Omarchy, a Snapshots submenu with two btrfs snapshots, and an `EFI fallback` line which is the removable UEFI boot path, not a kernel. /etc/limine-entry-tool.d/omarchy-defaults.conf sets ENABLE_LIMINE_FALLBACK=yes but never sets MKINITCPIO_FALLBACK, which is what the Arch wiki Limine page says controls fallback image generation, so no fallback initramfs entry is produced. A user who follows the danger believes they have a way back and does not, which on a record about losing your desktop is the defect that matters. The real Omarchy 4 recovery is a btrfs snapshot from the Limine menu. Third, the cited GitHub issue is wrong twice over. https://github.com/basecamp/omarchy/issues/7947 returns a bare 404 and does not redirect (curl -I shows 404 text/plain while the repo root 301s to omacom). Read in full through `gh issue view 7947 -R omacom/omarchy`, the issue is titled "nvidia.sh fails on Pascal GPUs (MX150): nvidia-580xx-dkms and lib32-nvidia-580xx-utils not found" and is about the Omarchy installer being unable to find AUR packages. It says nothing about DKMS failing to rebuild after a kernel update, so it does not support this record at all. It belongs on nvidia-590-drops-pascal-broken-desktop instead, and I have added it there. I found no upstream issue that does support this record, so the corrected record rests on the two Arch wiki pages plus what is verifiable on the machine. Also corrected: the symptom and danger both assume `sudo pacman -Syu`, which /usr/bin/omarchy-update-pacman-guard refuses on Omarchy 4 (I read the script, it aborts when both -S and -u are present unless OMARCHY_ALLOW_DIRECT_PACMAN=1). Not exercised: I have no sudo here, so I did not run dkms, mkinitcpio, limine-mkinitcpio or depmod, and I did not induce a failed rebuild. I could not read /boot, which is a vfat ESP mounted dmask=0077, so the UKI filename comes from the limine-entry-tool config (CUSTOM_UKI_NAME="omarchy") and from limine-list rather than from a directory listing. Severity critical and frequency very-common are both left unchanged: every DKMS user meets this eventually and the result is no desktop.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Never run `pacman -Sy <pkg>` to grab headers. That is a partial upgrade and will break the system. Always `pacman -Syu`, and on Omarchy 4 use `omarchy update`, because a direct `pacman -Syu` is refused by `/usr/bin/omarchy-update-pacman-guard`.

If a kernel update and a driver update land in the same transaction, do not reboot until `dkms status` shows the module built for the NEW kernel.

A stock Omarchy 4 install has no second kernel and no fallback initramfs entry, so there is nothing to fall back to. `limine-list` shows one entry per installed kernel plus a Snapshots submenu, and the `EFI fallback` line is the removable UEFI boot path, not a kernel. The recovery that does work is a btrfs snapshot from the Limine menu. If you want a second kernel to boot into, you have to create it, for example with `sudo pacman -S --needed linux-lts linux-lts-headers` followed by `sudo limine-mkinitcpio`, and then confirm with `limine-list` that the entry exists before you rely on it.

On Omarchy 4, `sudo mkinitcpio -P` reports no error and writes no image, because `/etc/mkinitcpio.d` holds no presets. Treat a rebuild that finishes instantly with no output as a failure, and run `sudo limine-mkinitcpio`.

**Fix.**

From a TTY:

```bash
uname -r
dkms status
```

**1. Install headers for EVERY kernel you have installed.**

```bash
sudo pacman -S --needed linux-headers
# plus, as applicable:
# sudo pacman -S --needed linux-lts-headers linux-zen-headers linux-hardened-headers
```

**2. Rebuild the modules for the running kernel.**

```bash
sudo dkms autoinstall
# ...or for a specific kernel:
sudo dkms autoinstall -k "$(uname -r)"
```

If the build still fails, read the log dkms names in its error output. A failed build leaves it at `/var/lib/dkms/nvidia/<version>/build/make.log`, and a successful one moves it to `/var/lib/dkms/nvidia/<version>/<kernel>/x86_64/log/make.log`. A driver too old for the kernel is the usual cause, so upgrade `nvidia-open-dkms` (or the AUR legacy branch, for Maxwell, Pascal and Volta cards) before rebooting into the new kernel.

**3. Clear out stale builds and refresh the module map.**

```bash
sudo dkms status                       # note old versions
sudo dkms remove nvidia/<old-version> --all
sudo depmod -a "$(uname -r)"
```

**4. Rebuild the boot image.** This step differs by distro and skipping the difference is what leaves you booting the old modules:

```bash
# Omarchy 4: the machine boots a UKI at /boot/EFI/Linux/omarchy_linux.efi,
# written by limine-mkinitcpio-install. /etc/mkinitcpio.d is EMPTY, so
# `mkinitcpio -P` has no presets to process and silently builds nothing.
sudo limine-mkinitcpio

# Plain Arch, where kernel packages drop a preset in /etc/mkinitcpio.d:
sudo mkinitcpio -P
```

```bash
reboot
```

**If you have no console at all**, the recovery path depends on the distro:

- **Omarchy 4**: reboot and pick a btrfs snapshot from the Limine menu's Snapshots submenu. Run `limine-list` beforehand, while you still can, to see what is there.
- **Plain Arch**: boot another installed kernel from the bootloader menu, or boot a live USB and `arch-chroot` into the install, then repeat the steps above.

**Verify.** `dkms status` shows `installed` for the running kernel. `modinfo nvidia | head -3` prints a version. `nvidia-smi` prints a driver version and lists your GPU. On Omarchy 4, `limine-list` shows a boot entry for the kernel you rebuilt against.

Sources: <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/Mkinitcpio> · <https://wiki.archlinux.org/title/Limine>

---

## Enable nvidia_drm modeset so Hyprland can start on NVIDIA

`nvidia-drm-modeset-disabled-black-screen-hyprland` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** After installing the NVIDIA driver, Hyprland does not start on Wayland — the screen goes black at boot or right after login, or Hyprland exits back to the TTY. The log shows `backend failed to start`. Switching to a TTY may still work. `cat /sys/module/nvidia_drm/parameters/modeset` prints `N`.

**Cause.** Wayland compositors require DRM kernel mode setting on the NVIDIA driver. Without `nvidia_drm.modeset=1`, aquamarine (Hyprland's backend) cannot get a DRM master / usable framebuffer, so the compositor never brings up an output. Since nvidia-utils 560.35.03-5 Arch enables modeset by default, so this mostly bites users on older/legacy AUR driver branches (nvidia-580xx, nvidia-470xx, nvidia-390xx), on custom kernels, or on systems where somebody put `nvidia_drm.modeset=0` on the kernel command line.

> **Audit corrected this record.** Diagnosis and the modeset=1 fix are correct and match upstream (Hyprland wiki 'Early KMS, modeset and fbdev'; Arch NVIDIA#DRM kernel mode setting), and the Omarchy nvidia.sh quoted really does write those two files (verified against master). But the record hands the user early KMS as if it were part of the fix. Arch wiki states plainly: 'For basic functionality, just adding the kernel parameter should suffice' and 'Early loading the modules will break hibernation, as video memory preservation is enabled by default' — so this record creates the exact problem that record [4] then tells them to undo. Also `printf ... | sudo tee /etc/modprobe.d/nvidia.conf` silently clobbers an existing file of that name (Omarchy's own), and fbdev only needs setting on legacy branches.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing mkinitcpio and rebuilding the initramfs can make the system unbootable if you typo a module name. Keep a fallback boot entry (Arch ships `*-fallback.img`) and a live USB handy. Never run `mkinitcpio -P` in the middle of a half-finished `pacman` transaction.

**Fix.**

Verify first:

```bash
cat /sys/module/nvidia_drm/parameters/modeset   # want: Y
cat /sys/module/nvidia_drm/parameters/fbdev     # want: Y
```

On Arch, `nvidia-utils` already enables both by default (since 560.35.03-5, via `/usr/lib/modprobe.d/`), so you only need this on legacy AUR branches (nvidia-580xx/470xx/390xx), custom kernels, or a hand-installed .run driver:

```bash
# use a distinct filename so you don't clobber Omarchy's /etc/modprobe.d/nvidia.conf
printf 'options nvidia_drm modeset=1 fbdev=1\n' | sudo tee /etc/modprobe.d/nvidia-drm-modeset.conf
sudo mkinitcpio -P
```

Do NOT add the nvidia modules to the initramfs to fix this. Early loading is not needed for modeset, and the Arch wiki warns it breaks resume from hibernation (the driver has no access to `NVreg_TemporaryFilePath` in the initramfs). Only add early KMS if the module is genuinely loading after your display manager:

```bash
sudo tee /etc/mkinitcpio.conf.d/nvidia.conf >/dev/null <<'EOF'
MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
EOF
sudo mkinitcpio -P
```

(That second file is what Omarchy's `install/config/hardware/nvidia.sh` writes — remove it if you hibernate.)

Then check nothing on the kernel command line forces it off:

```bash
cat /proc/cmdline    # look for nvidia_drm.modeset=0
```

Remove it in your bootloader (systemd-boot: `options` in `/boot/loader/entries/*.conf`; Limine: `cmdline:` in `/boot/limine.conf`; GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` + `sudo grub-mkconfig -o /boot/grub/grub.cfg`). Reboot.

**Verify.** `cat /sys/module/nvidia_drm/parameters/modeset` returns `Y`, and Hyprland starts and shows a desktop. `hyprctl monitors` lists your outputs.

Sources: <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.hypr.land/Nvidia/> · <https://github.com/basecamp/omarchy/blob/master/install/config/hardware/nvidia.sh>

---

## NVRM: API mismatch after a partial upgrade or an un-rebooted kernel update

`nvrm-api-mismatch-partial-upgrade` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy-4`

**Symptom.** After an update the desktop never comes back — black screen, or you get dumped at a TTY. `nvidia-smi` says:

```
NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
```

and `sudo dmesg | grep NVRM` shows:

```
NVRM: API mismatch: this kernel module has the version 580.95.05, but
NVRM: this NVIDIA driver component has the version 590.48.  Please
NVRM: make sure that this kernel module and all NVIDIA driver
NVRM: components have the same version.
```

Or modprobe just cannot find it at all:

```
modprobe: FATAL: Module nvidia not found in directory /lib/modules/6.18.4-arch1-1
```

**Cause.** The NVIDIA driver ships as two halves that must be the exact same version: the userspace libraries (`nvidia-utils`) and the kernel module (`nvidia`, `nvidia-dkms`, `nvidia-open-dkms`). Two things desynchronise them.

1. A partial upgrade. `pacman -Sy nvidia`, or `pacman -Sy` followed by `pacman -S <anything>`, refreshes the database and pulls one half forward while leaving the other behind. The Arch wiki is explicit that partial upgrades are unsupported and that you must never run `pacman -Sy`. On Omarchy this is not covered by the update guard: `bin/omarchy-update-pacman-guard` only aborts when both a sync flag and a sysupgrade flag are present, so `sudo pacman -Sy nvidia` sails straight past it.

2. A kernel package upgraded underneath a running kernel. Pacman deletes `/usr/lib/modules/<old-version>/` when it installs the new kernel, so the still-running kernel loses every module it has not already loaded. That produces the `Module nvidia not found in directory /lib/modules/$(uname -r)` variant until you reboot.

A third, rarer variant: a stale DKMS build from an older driver version still sitting in `/usr/lib/modules/<kernel>/updates/dkms/` shadowing the correctly-versioned packaged module.

This is distinct from a DKMS *build failure* — here the build succeeded, the versions just do not line up.

> ⚠️ **Risk.** Do NOT "fix" a partial upgrade by symlinking library sonames — the Arch wiki warns explicitly against this; sonames are bumped precisely because they are incompatible. If the `-Syu` that follows the bad `-Sy` fails halfway, you are now in a genuine partial-upgrade state and must resolve the error and finish the transaction before running any other pacman operation. Booting with `nomodeset` gives you a low-resolution text console only — do not leave it in the permanent command line. `dkms remove --all` deletes built modules for every kernel; if you remove the wrong version you lose the working module too, so read `dkms status` first.

**Fix.**

**1. Confirm the mismatch before touching anything.**

```bash
uname -r
pacman -Q linux linux-headers nvidia-utils nvidia-dkms nvidia-open-dkms 2>/dev/null
cat /proc/driver/nvidia/version 2>/dev/null   # what the loaded module thinks it is
modinfo -F version nvidia 2>/dev/null         # what the on-disk module is
dkms status
```

If `/proc/driver/nvidia/version` and `pacman -Q nvidia-utils` disagree, it is a version skew. If `modinfo` says "module not found", the running kernel lost its modules.

**2. Complete the upgrade properly — never `pacman -Sy <pkg>`.**

```bash
# Omarchy 4:
omarchy update

# plain Arch / EndeavourOS / CachyOS / Manjaro:
sudo pacman -Syu
```

If you are stuck on a black screen with no shell: press `Ctrl+Alt+F2` for a TTY, or at the Limine menu select the entry and add `nomodeset` to the command line (Limine's editor; see the key hints on the menu's help line) to get a text console, then run the upgrade there.

**3. Clear a stale DKMS build if one is shadowing the packaged module.**

```bash
dkms status
find /usr/lib/modules -path '*updates/dkms*' -name 'nvidia*.ko*' -printf '%p\n'
# remove the old version by name, e.g.:
sudo dkms remove nvidia/580.95.05 --all
sudo dkms autoinstall -k "$(uname -r)"
```

**4. Rebuild the initramfs so early-KMS modules match, then reboot.**

```bash
# Omarchy 4 (Limine + UKI):
sudo limine-mkinitcpio
sudo limine-update

# plain mkinitcpio systems:
sudo mkinitcpio -P

sudo reboot
```

**5. Stop it happening again.** Install the hook that keeps the running kernel's modules on disk across an upgrade:

```bash
sudo pacman -S kernel-modules-hook
```

**Verify.** After reboot: `nvidia-smi` prints the device table; `cat /proc/driver/nvidia/version` reports the same version as `pacman -Q nvidia-utils`; `cat /sys/module/nvidia_drm/parameters/modeset` returns `Y`; `dmesg | grep -i 'API mismatch'` returns nothing.

Sources: <https://wiki.archlinux.org/title/System_maintenance> · <https://wiki.archlinux.org/title/General_troubleshooting> · <https://bbs.archlinux.org/viewtopic.php?id=291394> · <https://bbs.archlinux.org/viewtopic.php?id=261042> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pacman-guard> · <https://wiki.archlinux.org/title/NVIDIA>

---

## Hyprland will not start: 'aquamarine could not find a GPU', no seat, no DRM device

`hyprland-no-drm-device-seat-failure` · severity: **critical** · frequency: **common** · applies to: `amdgpu`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy-4`

**Symptom.** Hyprland exits immediately back to the TTY. The log ends with:

```
[CRITICAL] m_pAqBackend was null! This usually means aquamarine could not find a GPU or encountered some issues. Make sure you're running either on a tty or on a Wayland session, NOT an X11 one.
```

and further up one or more of:

```
[ERR] libseat: failed to open a seat
[ERR] Failed to open a session
[ERR] libseat: Couldn't open device at /dev/dri/card1
[ERR] drm: No gpus in scanGPUs.
[ERR] drm: Found no gpus to use, cannot continue
[CRITICAL] No backend could be opened. Make sure there was a correct backend passed to CBackend, and that your environment supports at least one of them.
```

Older builds and other wlroots compositors phrase the same thing as `Couldn't open a DRM device` / `Found 0 GPUs, cannot create backend`.

**Cause.** Three separate failures produce nearly the same message, and the log line above tells you which:

1. **No seat.** Hyprland takes DRM master through libseat, which needs either a valid systemd-logind session or a running seatd. `libseat: failed to open a seat` means neither was available — launching over SSH, from inside tmux, with `sudo Hyprland`, from a display manager that never created a proper session, or on a system with no polkit package and seatd.service not enabled. The Arch Hyprland page is explicit: install a polkit package *or* enable seatd.service, otherwise Hyprland fails to start.
2. **No GPU visible.** `drm: No gpus in scanGPUs` / `Found no gpus to use` means udev enumerated nothing with KMS. Causes: `nomodeset` on the kernel command line, the DRM driver blacklisted or not built for this hardware (see the i915/xe force_probe case), a VM with 3D acceleration disabled, or an `AQ_DRM_DEVICES` value naming a device node that does not exist or is not in the enumerated set. Note that a *symlink* is fine: aquamarine canonicalises both the paths you give it and each enumerated device path before comparing them, so /dev/dri/by-path/... resolves correctly — and the Hyprland Multi-GPU wiki actively recommends the by-path name, because /dev/dri/cardN numbering is assigned dynamically at boot and changes. If aquamarine logs `drm: Explicit device <path> not found`, the path is wrong or the card really is absent, not merely symlinked.
3. **Wrong context.** Launching Hyprland from inside an existing X11 or Wayland session, which the error message calls out directly.

> **Audit corrected this record.** The three-way split of an ambiguous error is the right structure, and the seat half is solid: Arch Hyprland wiki line 19 says verbatim "Make sure to install the Polkit package, or start and enable seatd.service. As the lack thereof will cause Hyprland to fail to start", the seatd PKGBUILD comment confirms the `seat` group ('Allow users in the "seat" group to access seatd'), hyprpolkitagent is real (extra 0.1.3), the log path and `lspci -k -d ::03xx` are both correct, and 'never sudo Hyprland' is right. But the AQ_DRM_DEVICES advice is backwards on both counts. I read aquamarine src/backend/drm/DRM.cpp:194-236: it splits AQ_DRM_DEVICES on ':' and then calls std::filesystem::canonical() on *both* the values you gave it *and* each enumerated device path before comparing. Canonicalisation is exactly what makes a /dev/dri/by-path/... symlink work — it is not 'a known way to make it see nothing'. And the Multi-GPU wiki says the opposite of the record's fix: "Do not use the card1 symlink indicated here. It is dynamically assigned at boot and is subject to frequent change, making it unsuitable as a marker for GPU selection" — i.e. prefer the stable by-path name over /dev/dri/cardN. Following the record's step 3 replaces a stable path with an unstable one. Second defect, Omarchy-specific: that same wiki page ends with "uwsm users are advised to export the AQ_DRM_DEVICES variable inside ~/.config/uwsm/env-hyprland, instead" — Omarchy starts Hyprland under uwsm, so `hl.env("AQ_DRM_DEVICES", ...)` in hyprland.lua is the wrong place there. Third, minor: `pacman -S drm_info` fails; the package is drm-info.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Adding your user to `input` grants read access to every input device on the machine — that is a keylogging surface; only do it if you actually need the seatd backend (logind users do not). Do not remove polkit to "test" the seatd path: polkit is what lets your session authenticate for mounts, network changes and reboots. Do not run `sudo Hyprland` as a workaround — it creates root-owned files in your `$XDG_RUNTIME_DIR` and in `~/.cache`, which then break the normal session in ways that are tedious to unpick.

**Fix.**

**1. Read the log first — the specific error decides the path.**

```bash
cat "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log" 2>/dev/null \
  || cat ~/.local/share/hyprland/hyprland.log
```

**2. `libseat: failed to open a seat` — fix the session.**

```bash
loginctl
loginctl show-session "$(loginctl | awk -v u="$USER" '$3==u{print $1; exit}')" -p Type -p Active -p Seat -p Remote
echo "$XDG_RUNTIME_DIR"      # must be /run/user/$(id -u), not empty

# Arch/Omarchy: a polkit package OR seatd is mandatory
pacman -Qs polkit
sudo pacman -S polkit hyprpolkitagent          # preferred on Hyprland

# alternative: the seatd backend
sudo pacman -S seatd
sudo systemctl enable --now seatd.service
sudo usermod -aG seat,video,input "$USER"      # seatd's own group, created by the package
# log out fully and log back in - group changes need a new login session
```

Then launch from a real virtual console: Ctrl+Alt+F3, log in, and run `Hyprland` (or `uwsm start hyprland.desktop`). Never `sudo Hyprland`.

**3. `Found no gpus to use` — fix the GPU side.**

```bash
ls -l /dev/dri/                       # expect cardN and renderD128
lspci -k -d ::03xx                    # "Kernel driver in use:" must be set
sudo dmesg | grep -iE 'drm|i915|xe |amdgpu|nouveau|nvidia' | head -40
grep -o nomodeset /proc/cmdline       # if this prints, remove it from the cmdline
echo "AQ_DRM_DEVICES=$AQ_DRM_DEVICES" # if set, must be a ':'-separated list of real nodes
grep -i 'Explicit device' "$XDG_RUNTIME_DIR/hypr/"*/hyprland.log
```

If /dev/dri/ is empty, the kernel driver never bound — a driver problem, not a Hyprland problem (blacklisted module, `nomodeset`, or hardware needing force_probe).

If the log says `drm: Explicit device <path> not found`, your AQ_DRM_DEVICES entry is simply wrong. Do **not** "fix" it by swapping a by-path symlink for /dev/dri/cardN — aquamarine canonicalises both sides, so symlinks work, and the Multi-GPU wiki warns that cardN numbering changes at boot. Use the stable by-path name:

```bash
ls -l /dev/dri/by-path/            # match the PCI address from lspci
```

Where you set it depends on how the session starts. **On Omarchy the session is started by uwsm, and the Hyprland wiki says uwsm users must export it in `~/.config/uwsm/env-hyprland`:**

```sh
# ~/.config/uwsm/env-hyprland
export AQ_DRM_DEVICES=/dev/dri/by-path/pci-0000:06:00.0-card:/dev/dri/by-path/pci-0000:01:00.0-card
```

Only if you are *not* using uwsm does the config form apply:

```lua
-- ~/.config/hypr/hyprland.lua
hl.env("AQ_DRM_DEVICES", "/dev/dri/by-path/pci-0000:06:00.0-card")
```

**4. Prove the stack works independently of Hyprland.** The package is `drm-info`; the binary is `drm_info`:

```bash
sudo pacman -S drm-info && drm_info | head -30
```

**Verify.** Hyprland starts from a TTY. `hyprctl monitors` lists your outputs. `loginctl show-session ... -p Active` reports `Active=yes`, and the log contains `drm: Found N GPUs` instead of the errors above.

Sources: <https://wiki.archlinux.org/title/Hyprland> · <https://github.com/hyprwm/Hyprland/blob/main/src/Compositor.cpp> · <https://github.com/hyprwm/aquamarine/blob/main/src/backend/Session.cpp> · <https://github.com/hyprwm/aquamarine/blob/main/src/backend/drm/DRM.cpp> · <https://gitlab.archlinux.org/archlinux/packaging/packages/seatd/-/raw/main/PKGBUILD> · <https://github.com/hyprwm/Hyprland/issues/1185>

---

## Recover a GTX 10xx/9xx desktop broken by the NVIDIA 590 upgrade

`nvidia-590-drops-pascal-broken-desktop` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** After a system upgrade (`omarchy update` on Omarchy 4, `sudo pacman -Syu` on plain Arch) on a machine with a GTX 1050/1060/1070/1080, GTX 9xx, MX150 or Titan X, the graphical session no longer comes up. You get a black screen, or you land in a TTY. `nvidia-smi` prints `NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver`. `dmesg` shows the NVIDIA module refusing to bind to the GPU.

**Cause.** NVIDIA driver 590 dropped support for Pascal and older GPUs, and Arch simultaneously switched the main packages to the open kernel modules: `nvidia` became `nvidia-open`, `nvidia-dkms` became `nvidia-open-dkms`, and `nvidia-lts` became `nvidia-open-lts`. The open kernel modules need GSP firmware, which arrived with Turing, so they support Turing (GTX 16xx and RTX 20xx) and newer only. On Pascal and older the driver simply fails to load after the upgrade. Note that the Arch news item announcing the change wrote the LTS package name as `nvidia-lts-open`, but the package Arch actually ships is `nvidia-open-lts`.

> **Audit corrected this record.** The cause holds. I fetched the cited Arch news item of 2025-12-20 and read it in full: driver 590 drops Pascal and older, nvidia becomes nvidia-open, nvidia-dkms becomes nvidia-open-dkms, and Pascal users must move to nvidia-580xx-dkms from the AUR. The Arch wiki NVIDIA table (fetched as raw wikitext) lists Volta, Pascal and Maxwell against nvidia-580xx-dkms, status Legacy supported, and the AUR RPC shows nvidia-580xx-dkms, nvidia-580xx-utils and lib32-nvidia-580xx-utils all at 580.178.04-1, maintained and not flagged out of date. Confirmed on this machine by reading /usr/share/omarchy/install/hardware/nvidia.sh: Omarchy 4 picks exactly those three packages when omarchy-hw-nvidia-without-gsp matches, and yay 13.0.1-1 is installed so the AUR step is available. Five defects. First and worst, `sudo mkinitcpio -P` writes no new boot image on Omarchy 4: /etc/mkinitcpio.d is empty on this machine (zero entries), mkinitcpio takes its presets from that directory (line 25 of /usr/bin/mkinitcpio sets _d_presets to /etc/mkinitcpio.d), the stock kernel hook is replaced by /etc/pacman.d/hooks/90-mkinitcpio-install.hook calling limine-mkinitcpio-install, and /usr/local/bin/mkinitcpio (from limine-mkinitcpio-hook, first in PATH) warns that it does not update Limine boot entries and then prompts interactively. The user reboots into the old UKI with no working driver, which is the exact black screen the danger warns about. The Arch wiki Limine page says plainly to run limine-mkinitcpio instead of mkinitcpio. Second, the env var step is Omarchy 3 advice. I fetched install/config/hardware/nvidia.sh from the master branch and it is the file that appends `env = NVD_BACKEND,egl` to ~/.config/hypr/envs.conf. On Omarchy 4 there is no envs.conf (confirmed by listing ~/.config/hypr) and /usr/share/omarchy/default/hypr/nvidia.lua already sets NVD_BACKEND to egl for without-GSP cards, pulled in by default/hypr/envs.lua, so the user must add nothing. Third, the `pacman -Rdd` line always fails: pacman aborts the whole transaction on the first target that is not installed. Confirmed here with `pacman -Rp nvidia-open-dkms doesnotexist-pkg-xyz`, which exits 1 with `error: target not found` and removes nothing. The six names in the record conflict with one another so no machine has all six, and the `2>/dev/null` hides the only clue. Fourth, package names are stale: nvidia, nvidia-dkms and nvidia-lts 404 on archlinux.org/packages, and nvidia-lts-open never existed. The real LTS package is nvidia-open-lts (extra, 1:615.71.09-2), and the removal list omits nvidia-utils, which nvidia-580xx-utils conflicts with and which nvidia-open-dkms pins at an exact version (both confirmed with pacman -Qi here). Fifth, the verify step `cat /sys/module/nvidia_drm/parameters/modeset` is Permission denied for an unprivileged user on this machine and needs sudo. Two source problems: https://github.com/basecamp/omarchy/issues/3954 returns a bare 404 and does not redirect (curl -I shows 404 text/plain, while the repo root 301s to omacom), and the master blob URL resolves but points at the Omarchy 3 tree that produced the wrong envs.conf advice. I also add omacom/omarchy#7947, which is open and reports that the 580xx packages are not in the repositories at all, which is why the fix needs yay rather than pacman -S. Not exercised: I have an RTX 3090 (Turing or newer, driver 610.57.04), so I could not install or boot the 580xx branch, could not run limine-mkinitcpio or mkinitcpio, and could not confirm nouveau or NVK performance on Pascal. The NVK hardware floor comes from the Arch wiki Nouveau page, which states Kepler and newer. Severity critical and frequency common are both left as they are: the machine loses its desktop, and the population is every Omarchy 3 or Arch upgrade on a Maxwell, Pascal or Volta card.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `pacman -Rdd` skips dependency checks. Use it only to break the version pin between `nvidia-open-dkms` and `nvidia-utils`, and install the replacement driver in the same session. Do NOT reboot between removing the old driver and installing the new one unless you are comfortable working from a TTY.

A fixed `pacman -Rdd` package list is itself a trap. Pacman aborts the whole transaction on the first target that is not installed, removes nothing, and says so in one line that is easy to miss. Check what it actually removed before you carry on.

Building the AUR DKMS package needs headers matching every installed kernel. If headers are missing the module is not built, `dkms status` will say so, and you reboot into a black screen.

On Omarchy 4, `sudo mkinitcpio -P` is not enough and gives no useful error. `/etc/mkinitcpio.d` is empty, so there are no presets to process and no new boot image is written. You reboot into the old UKI with the old modules. Run `sudo limine-mkinitcpio` instead.

If you do end up with no desktop, Omarchy 4's Limine menu carries btrfs snapshots under a Snapshots submenu. Boot the newest snapshot taken before the upgrade rather than reinstalling. Check what the menu holds with `limine-list`.

**Fix.**

From a TTY (Ctrl+Alt+F2) or a chroot.

**1. Remove only the mainline NVIDIA packages that are actually installed.** A fixed list does not work: `pacman -Rdd` aborts the entire transaction on the first name that is not installed and removes nothing, and those package names conflict with each other so no machine has them all.

```bash
installed=()
for p in nvidia nvidia-open nvidia-dkms nvidia-open-dkms nvidia-lts nvidia-open-lts \
         nvidia-utils lib32-nvidia-utils opencl-nvidia lib32-opencl-nvidia; do
  pacman -Qq "$p" &>/dev/null && installed+=("$p")
done
printf '%s\n' "${installed[@]}"
(( ${#installed[@]} )) && sudo pacman -Rdd "${installed[@]}"
```

`-Rdd` skips dependency checks. It is needed here only because `nvidia-open-dkms` pins `nvidia-utils` to an exact version and `nvidia-580xx-utils` conflicts with `nvidia-utils`.

**2. Install headers for every kernel you have installed.**

```bash
sudo pacman -S --needed linux-headers      # add linux-lts-headers / linux-zen-headers as applicable
```

**3. Install the legacy proprietary 580xx branch.** It is AUR-only, so plain `pacman -S` reports `target not found` (this is what breaks the Omarchy installer in omacom/omarchy#7947). Omarchy ships `yay`:

```bash
yay -S nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils
```

`nvidia-580xx-utils` provides `nvidia-utils`, which is what `hyprland`, `libglvnd` and `steam` depend on, so those stay satisfied.

**4. Rebuild the boot image.** The command differs by distro, and getting it wrong is what leaves you at a black screen:

```bash
# Omarchy 4: /etc/mkinitcpio.d is EMPTY and the system boots a UKI at
# /boot/EFI/Linux/omarchy_linux.efi. `mkinitcpio -P` has no presets to process,
# so it builds nothing and the UKI keeps the old modules.
sudo limine-mkinitcpio

# Plain Arch, where kernel packages drop a preset in /etc/mkinitcpio.d:
sudo mkinitcpio -P
```

```bash
reboot
```

Omarchy's installer picks these same three packages for Maxwell, Pascal and Volta. See `/usr/share/omarchy/install/hardware/nvidia.sh` and its detector `/usr/share/omarchy/bin/omarchy-hw-nvidia-without-gsp`, which matches NVIDIA PCI device IDs from `0x1340` up to but not including `0x1e00`.

These cards also need `NVD_BACKEND=egl` rather than `direct`. Where that goes depends on the version:

- **Omarchy 4 sets it for you** at every session start, from `/usr/share/omarchy/default/hypr/nvidia.lua`, keyed on the same detector and loaded by `default/hypr/envs.lua`. Add nothing. Hardcoding it yourself only risks pinning the wrong value if you later change cards.
- **Omarchy 3** wrote it to `~/.config/hypr/envs.conf` in hyprlang:

```
env = NVD_BACKEND,egl
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
```

- **Plain Arch on Hyprland 0.55 or newer**, in your own Lua config:

```lua
hl.env("NVD_BACKEND", "egl")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
```

If you would rather not touch the AUR, the fully open nouveau and NVK stack (`mesa` plus `vulkan-nouveau`) covers Kepler and newer, so it does run on these cards. Expect a large performance cost, and note that the Arch wiki still marks NVK a work in progress.

**Verify.** `nvidia-smi` prints a driver version in the 580.x series and lists your GPU. `sudo cat /sys/module/nvidia_drm/parameters/modeset` returns `Y` (that file is root-readable only, so it needs sudo). `dkms status` shows the nvidia module `installed` against your running kernel. Hyprland starts.

Sources: <https://archlinux.org/news/nvidia-590-driver-drops-pascal-support-main-packages-switch-to-open-kernel-modules/> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/Nouveau> · <https://wiki.archlinux.org/title/Limine> · <https://wiki.archlinux.org/title/Mkinitcpio> · <https://aur.archlinux.org/packages/nvidia-580xx-dkms> · <https://github.com/omacom/omarchy/issues/3954> · <https://github.com/omacom/omarchy/issues/7947> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/nvidia.sh>

---

## Kernel parameters do not stick on Omarchy 4 because /boot/limine.conf is generated

`limine-kernel-parameters-not-applying-omarchy` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `laptop`, `limine`, `omarchy-4`, `uki`

**Symptom.** Every GPU fix you find says "add `amdgpu.dcdebugmask=0x10` (or `nvidia_drm.modeset=1`, `i915.force_probe=…`, `nomodeset`) to your kernel command line", but Omarchy has no `/etc/default/grub`. You edit `/boot/limine.conf`, reboot, and `cat /proc/cmdline` does not show the parameter — or it works once and is silently reverted by the next `omarchy update` or kernel upgrade.

**Cause.** Omarchy 4 does not hand-maintain `/boot/limine.conf`. It boots a **Unified Kernel Image** at `/boot/EFI/Linux/omarchy*.efi`, built by `limine-mkinitcpio` and registered by `limine-entry-tool`. `/boot/limine.conf` holds only theming and menu options and is regenerated from configuration on every kernel/limine transaction, so anything you type into it is discarded. Worse, with a UKI the command line is *baked into the .efi image*, so even a correct `limine.conf` edit could not change it.

The real sources of the command line, in increasing priority:

1. `/etc/kernel/cmdline` (the generic default when nothing else is set),
2. drop-ins in `/etc/limine-entry-tool.d/*.conf`, read in lexical filename order,
3. `/etc/default/limine`, which the Arch wiki notes has the **highest** priority and overrides all drop-ins.

Omarchy ships its own drop-in, `/etc/limine-entry-tool.d/omarchy-defaults.conf`, containing `quiet splash loglevel=0 systemd.show_status=false rd.udev.log_level=0 vt.global_cursor_default=0` plus `initramfs_async=0`. That file is package-owned: editing it means your changes turn into `.pacnew` conflicts on the next update.

> ⚠️ **Risk.** A bad kernel parameter is a failure to boot — test it in the Limine editor before writing a drop-in. Using `KERNEL_CMDLINE[default]=` instead of `+=`, or naming your file so it sorts *before* `omarchy-defaults.conf`, silently drops Omarchy's `initramfs_async=0`, which the packaged comment says is what keeps Plymouth alive at the LUKS prompt — an encrypted machine then falls back to an unthemed text prompt or hangs. `limine-mkinitcpio` rewrites the UKI on the ESP: run `df -h /boot` first, because a full ESP produces a truncated, unbootable image. If you enabled Secure Boot with `ENABLE_ENROLL_LIMINE_CONFIG=yes`, modifying `limine.conf` without re-enrolling the checksum makes the machine refuse to boot even after you disable Secure Boot — keep an unsigned fallback loader. Recovery for all of the above is the Limine snapshot entry, so do not enable Direct Boot until you are done experimenting.

**Fix.**

**Put your parameters in your own drop-in whose filename sorts after Omarchy's**, and always use `+=` so you append rather than replace:

```bash
sudo tee /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
# Local kernel parameters.
# `+=` appends to what earlier drop-ins set. A bare `=` REPLACES them and will
# wipe Omarchy's quiet/splash/initramfs_async defaults.
KERNEL_CMDLINE[default]+=" amdgpu.dcdebugmask=0x10"
EOF

# rebuild the UKI/initramfs, then regenerate the Limine boot entries
sudo limine-mkinitcpio
sudo limine-update
sudo reboot
```

After reboot:

```bash
cat /proc/cmdline
```

**Variants:**

```bash
# only for a specific kernel entry (matches the boot menu entry name)
KERNEL_CMDLINE[linux-lts]+=" nvidia_drm.modeset=1"

# only for the fallback entry
KERNEL_CMDLINE[fallback]+=" nomodeset"
```

**Test a parameter once, without persisting anything:** at the Limine boot menu select the entry and open Limine's editor (the key hints are printed in the menu's help line; `editor_enabled` defaults to `yes`), edit the command line, and boot. Nothing is written to disk. If Omarchy's *Direct Boot* is enabled (`omarchy-setup-direct-boot` adds an `Omarchy` EFI entry that jumps straight to the UKI), the Limine menu is bypassed entirely — pick Limine from the firmware boot menu (usually F12/F8/Esc) to get it back.

**If you already clobbered `/boot/limine.conf`,** restore the packaged one:

```bash
omarchy-refresh-limine
# moves your file to /boot/limine.conf.bak, copies the packaged default,
# then runs `limine-update` and `limine-snapper-sync`
```

**On other Arch-based distros using Limine (e.g. CachyOS):** the same mechanism applies — `/etc/default/limine` and `/etc/limine-entry-tool.d/`, then `limine-mkinitcpio` (or `limine-dracut`) and `limine-update`. On GRUB systems it is `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` plus `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

**Verify.** `cat /proc/cmdline` contains both your parameter and Omarchy's defaults (`quiet splash loglevel=0 … initramfs_async=0`). `sudo limine-list` shows the entries. For a module parameter, `cat /sys/module/<module>/parameters/<param>` reflects the new value.

Sources: <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-limine> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-setup-direct-boot> · <https://github.com/basecamp/omarchy/blob/quattro/default/limine/default.conf> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md>

---

## Stop NVIDIA black screens and corruption after suspend/resume

`nvidia-suspend-resume-black-screen-vram` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** The laptop or desktop suspends fine, but on wake the monitors stay black or show 'No Signal' — the machine is still running (you can SSH in, or Ctrl+Alt+F2 to a TTY and back sometimes helps), or the desktop comes back visibly corrupted. `journalctl -b -1` contains lines like:

```
NVRM: Xid (PCI:0000:08:00): 13, pid='<unknown>', name=<unknown>, Graphi>
nvidia-modeset: ERROR: GPU:0: Failed detecting connected display devices
nvidia-modeset: WARNING: GPU:0: Unable to read EDID for display device ... (DP-0)
```

**Cause.** The NVIDIA driver saves and restores only essential video memory across a suspend cycle by default. The rest is lost, the userspace driver cannot always reconstruct it, and the result is rendering corruption, dead outputs and `Xid 13` errors from whatever was drawing. Full preservation is reached two different ways depending on the driver branch. The open kernel modules from 595 onward do it themselves when `NVreg_UseKernelSuspendNotifiers=1`, which is what Arch ships in `/usr/lib/modprobe.d/nvidia-sleep.conf`. The 430 to 590 branch, which includes the `nvidia-580xx` driver Omarchy installs on Maxwell, Pascal and Volta, needs `NVreg_PreserveVideoMemoryAllocations=1` plus the `nvidia-suspend`, `nvidia-hibernate` and `nvidia-resume` services, because under that parameter NVIDIA requires the save and restore to be driven through `/proc/driver/nvidia/suspend`. On Omarchy 4 the two paths get crossed: `gpu-screen-recorder` is in the base package set and its `/usr/lib/modprobe.d/gsr-nvidia.conf` turns `PreserveVideoMemoryAllocations` on for every NVIDIA machine, while the installer never enables the services that parameter then requires.

> **Audit corrected this record.** Checked on this workstation, which is Omarchy 4.0.2-1, kernel 7.1.9, `nvidia-open-dkms` and `nvidia-utils` 610.57.04-1 on an RTX 3090, and against the cited pages plus NVIDIA's own 610.57.04 power management README. The symptom and the cause are real. Confirmed from the NVIDIA README that video memory preservation "is handled automatically" on the open modules when `NVreg_UseKernelSuspendNotifiers=1`, and that `/proc/driver/nvidia/suspend` "is required when using" `PreserveVideoMemoryAllocations=1`. Confirmed from the Arch wiki that Arch sets these for supported drivers so preserve works out of the box, which makes the record's hand-written `/etc/modprobe.d/nvidia-power.conf` redundant on Arch and Omarchy alike. Four things are wrong on Omarchy 4. First, `sudo mkinitcpio -P` does nothing here: confirmed on this machine that `/etc/mkinitcpio.d/` holds zero files and that neither `linux` nor `mkinitcpio` installs a preset into it, so the command processes no presets and never rebuilds the UKI that Limine boots. The Omarchy 4 command is `sudo limine-mkinitcpio`, which is what every Omarchy migration under `/usr/share/omarchy/migrations/` calls. Second, the advice to leave the sleep services off on 595 and newer is wrong on Omarchy specifically: confirmed on this machine that `gpu-screen-recorder` 6.0.1-1 owns `/usr/lib/modprobe.d/gsr-nvidia.conf` setting `NVreg_PreserveVideoMemoryAllocations=1`, that the package is line 47 of `/usr/share/omarchy/install/omarchy-base.packages`, that `/proc/driver/nvidia/params` therefore reports `PreserveVideoMemoryAllocations: 1` on this box, and that `systemctl is-enabled` reports all three sleep units disabled with no `nvidia-suspend` string anywhere under `/usr/share/omarchy`. Upstream `quattro`'s `install/hardware/nvidia.sh`, retrieved today, still does not enable them, so omacom/omarchy PR 8127 is unmerged and the gap is live on 4.0.3. Reading `/usr/lib/systemd/system-sleep/nvidia` on this machine confirms it only handles the `post` resume case for a plain suspend, so the save never runs while the restore is attempted. Third, the danger field missed the sharpest consequence: with `Preserve=1` on Omarchy's early-KMS layout, hibernate resume fails and the image is discarded, which omacom/omarchy issue 8126 documents with a kernel trace and the Hyprland wiki warns about in general form. Omarchy ships `HOOKS+=(resume)`, confirmed in `/etc/mkinitcpio.conf.d/omarchy_resume.conf`, so hibernation is configured by default and this is a real data-loss path. Fourth, "`/var/tmp` must be on a real filesystem (ext4/XFS, not tmpfs)" is too narrow: Omarchy's default root is btrfs and `/var/tmp` lives on it here, and the real requirement per NVIDIA is unnamed temporary file support plus capacity. Two smaller points: `sort /proc/driver/nvidia/params` needs no `sudo`, confirmed by reading it as an unprivileged user, and the record names three sleep units where four exist. On sources: both cited GitHub issues fail to support the record. Read in full, issue 2635 is an Omarchy 3.0 to 3.8 display-wake bug reported on AMD, Intel Iris and NVIDIA alike, whose stated workaround is `systemctl restart sddm`, and it never mentions video memory preservation or `Xid 13`. Issue 2112 is the same family on Omarchy 3, with `hypridle.conf` as the workaround. Neither names a parameter this record sets, so both go in `sources_remove` and are replaced with the NVIDIA README, omacom/omarchy issue 8126 and PR 8127, and the upstream driver install script. Severity `high` and frequency `very-common` both stand and are left alone: the misconfiguration ships by default to every Omarchy NVIDIA machine. NOT exercised: a suspend cycle. This workstation cannot be suspended for this audit, so option A and option B are argued from the driver README, the shipped unit files and the tracker report, not from a resume I watched. The claim that option B is also needed on some open-driver machines comes from one user's A/B in issue 8126 and is reported, not confirmed here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Under `PreserveVideoMemoryAllocations=1` the driver demands the `/proc/driver/nvidia/suspend` handshake at every power transition. Omarchy early-loads the NVIDIA modules, so on a hibernate resume the initramfs kernel already has nvidia bound and there is no systemd to drive that handshake. The image loads and is then discarded, with `PM: hibernation: Failed to load image, recovering` in the log, followed by a cold boot, and every unsaved thing that was open is gone. Omarchy also ships `HOOKS+=(resume)` in `/etc/mkinitcpio.conf.d/omarchy_resume.conf`, so hibernation is configured out of the box. Suspend and hibernate are mutually exclusive under this configuration, so decide which one you want before changing anything. The Hyprland wiki carries the same warning in general form: loading the NVIDIA modules early may stop resume from hibernation working, and the machine just boots instead. Separately, `/var/tmp` has to hold a full copy of video memory plus about 5 percent, so a short root filesystem makes suspend fail or hang. Any change under `/etc/modprobe.d` needs the initramfs rebuilt because of early KMS, and an interrupted `limine-mkinitcpio` leaves an unbootable UKI, so do not power-cycle while it runs.

**Fix.**

First read what the driver is actually doing. This needs no root:

```bash
sort /proc/driver/nvidia/params | grep -E 'PreserveVideoMemoryAllocations|UseKernelSuspendNotifiers|TemporaryFilePath'
systemctl is-enabled nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
pacman -Qs 'nvidia-open-dkms|nvidia-580xx-dkms'
```

Which branch you are on decides everything below. Omarchy 4 picks the driver for you in `install/hardware/nvidia.sh`: `nvidia-open-dkms` on Turing and newer, `nvidia-580xx-dkms` on Maxwell, Pascal and Volta.

- **`nvidia-open-dkms` (595 and newer, 610.57.04 at the time of writing).** The open kernel modules preserve video memory themselves when `UseKernelSuspendNotifiers: 1`. `nvidia-utils` already ships that, together with `TemporaryFilePath: "/var/tmp"`, in `/usr/lib/modprobe.d/nvidia-sleep.conf`. There is nothing to hand-write, and the three sleep services stay off.
- **`nvidia-580xx-dkms` (the 430 to 590 branch).** No suspend notifier support. This branch needs `PreserveVideoMemoryAllocations=1` plus `nvidia-suspend.service`, `nvidia-hibernate.service` and `nvidia-resume.service`, because NVIDIA's power management README says the `/proc/driver/nvidia/suspend` mechanism "is required when using this parameter".

**The Omarchy 4 trap.** `gpu-screen-recorder` is in the base package set (`/usr/share/omarchy/install/omarchy-base.packages`), so every Omarchy machine has it, and its packaging ships:

```
/usr/lib/modprobe.d/gsr-nvidia.conf
options nvidia NVreg_PreserveVideoMemoryAllocations=1
```

That turns the parameter on for every Omarchy NVIDIA machine, including the open-driver ones that did not ask for it. Omarchy's installer never enables the services that parameter requires (`grep -r nvidia-suspend /usr/share/omarchy` returns nothing, and upstream `quattro` still does not do it). `/usr/lib/systemd/system-sleep/nvidia` only covers the `post` case for a plain suspend, so the restore is attempted on the way up while the save on the way down never ran. That is the asymmetry that produces `Xid 13` across the compositor, the shell and the browser on resume.

Pick one of the two consistent configurations and do not leave the machine between them.

**Option A, let the notifier path own it.** Open driver only. Keeps hibernation working. A file in `/etc/modprobe.d` with the same basename completely replaces the one in `/usr/lib/modprobe.d`, so shadow the gpu-screen-recorder file:

```bash
sudo tee /etc/modprobe.d/gsr-nvidia.conf >/dev/null <<'EOF'
# Shadows /usr/lib/modprobe.d/gsr-nvidia.conf from gpu-screen-recorder.
# The open kernel modules preserve video memory through
# NVreg_UseKernelSuspendNotifiers=1, which nvidia-utils already sets.
options nvidia NVreg_PreserveVideoMemoryAllocations=0
EOF
sudo limine-mkinitcpio
```

**Option B, honour `PreserveVideoMemoryAllocations=1`.** Required on `nvidia-580xx-dkms`, and reported on the tracker to be needed on some open-driver machines too. Enable the units NVIDIA's README asks for:

```bash
sudo systemctl enable nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
```

Add `nvidia-suspend-then-hibernate.service` if you use suspend-then-hibernate. Read the danger field before choosing this one: on Omarchy's default early-KMS layout it costs you hibernation.

Then check the backing store. It has to hold a copy of all video memory plus about 5 percent, and it has to support unnamed temporary files. Omarchy's default root is btrfs, which does. `/tmp` is tmpfs on Omarchy and is the wrong place, which is why Arch points the parameter at `/var/tmp`:

```bash
nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits
df -hT /var/tmp
```

Reboot and test one suspend cycle.

**Regenerating the initramfs on Omarchy 4.** Omarchy early-loads the NVIDIA modules through `/etc/mkinitcpio.conf.d/nvidia.conf`, and the `modconf` hook copies both `/etc/modprobe.d` and `/usr/lib/modprobe.d` into the image, so any change to those files needs a rebuild. `mkinitcpio -P` does nothing on Omarchy 4: `/etc/mkinitcpio.d/` is empty and the `linux` package ships no preset. Omarchy boots a UKI through Limine and the command that rebuilds it is:

```bash
sudo limine-mkinitcpio
```

On plain Arch, where `/etc/mkinitcpio.d/linux.preset` exists, `sudo mkinitcpio -P` is still the right command.

**Verify.** Read the parameters back, no root needed, and confirm they agree with the option you chose:

```bash
sort /proc/driver/nvidia/params | grep -E 'Preserve|UseKernelSuspend|TemporaryFilePath'
systemctl is-enabled nvidia-suspend.service nvidia-resume.service
```

The three sleep units must be enabled if and only if `PreserveVideoMemoryAllocations: 1`. Then suspend once, wake, and read the boot you suspended in:

```bash
journalctl -b -k | grep -iE 'Xid \(PCI|nvidia-modeset: ERROR'
```

That should be empty and the desktop should come back with no corruption. Use `journalctl -b -1 -k` instead only when the machine had to be power-cycled. If you chose option B, confirm the units actually fired:

```bash
journalctl -b -u nvidia-suspend.service -u nvidia-resume.service
```

Sources: <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks> · <https://wiki.archlinux.org/title/NVIDIA/Troubleshooting> · <https://wiki.hypr.land/Nvidia/> · <https://download.nvidia.com/XFree86/Linux-x86_64/610.57.04/README/powermanagement.html> · <https://github.com/omacom/omarchy/issues/8126> · <https://github.com/omacom/omarchy/pull/8127> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/nvidia.sh>

---

## Steam and Proton fail with 'libGL error: failed to load driver' because the 32-bit graphics stack is missing

`steam-proton-lib32-graphics-missing` · severity: **high** · frequency: **very-common** · applies to: `amdgpu`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy-4`, `proton`, `steam`

**Symptom.** Steam will not start, or games launch to a black window and die. Running `steam` from a terminal shows one of:

```
libGL error: MESA-LOADER: failed to open iris: /usr/lib32/dri/iris_dri.so: cannot open shared object file: No such file or directory
libGL error: failed to load driver: iris
```

```
libGL error: MESA-LOADER: failed to open radeonsi
libGL error: failed to load driver: radeonsi
```

On NVIDIA:

```
Steam: An X Error occurred
X Error of failed request:  GLXBadContext
Major opcode of failed request:  151
```

Proton titles add `wine: failed to initialize vulkan` or complain about no DRI3/Vulkan support. Native 64-bit apps and `vkcube` are fine — only 32-bit ones break.

**Cause.** Steam's client is 32-bit and most Proton/Wine prefixes still load a 32-bit graphics path, so they need `/usr/lib32/` copies of the whole stack: the Mesa DRI drivers, the Vulkan loader, and the vendor Vulkan ICD. Those live in the `multilib` repository, which is **not enabled by default on plain Arch** (it *is* pre-enabled in Omarchy's shipped `pacman.conf`). Even with multilib on, `pacman -S steam` only pulls a generic `lib32-vulkan-driver` provider — and the Arch wiki warns that pacman picks alphabetically, offering `lib32-nvidia-utils` first even on an AMD or Intel machine, which leaves you with no working 32-bit Vulkan at all.

The NVIDIA `GLXBadContext` variant is a version skew: `nvidia-utils` and `lib32-nvidia-utils` must be the *same* version, and they drift apart if you installed one of them via a partial upgrade or from a lagging mirror.

> **Audit corrected this record.** The diagnosis is right and the Omarchy-specific claims all hold up. Arch Steam wiki line 28 is the source for the provider warning almost verbatim: "By default, pacman alphabetically chooses lib32-nvidia-utils, which can introduce issues such as being unable to use Vulkan at all due to the driver not corresponding to your GPU vendor." Omarchy's shipped default/pacman/pacman-stable.conf does contain an uncommented `[multilib]` block, so 'skip on Omarchy' is correct. bin/omarchy-install-gaming-gpu-lib32 is real on quattro and does exactly what the record says — lspci-detects Intel/AMD and adds lib32-vulkan-intel/lib32-vulkan-radeon, plus lib32-nvidia-utils or lib32-nvidia-580xx-utils. lib32-vulkan-icd-loader, lib32-mesa, lib32-vulkan-radeon, lib32-vulkan-intel, lib32-nvidia-utils, lib32-libnm, lib32-systemd and lib32-pipewire all exist in multilib. Three fixable problems. (1) `lib32-libva-mesa-driver` is no longer a package — Mesa's VA-API driver was merged into mesa, and lib32-mesa now only *provides* the name (provides: lib32-libva-driver, lib32-libva-mesa-driver=1:26.2.1-1). It resolves via provides rather than hard-failing, but it is a stale name that will confuse anyone who searches for it. (2) `lib32-libva-intel-driver` is the legacy i965 driver for pre-Broadwell only; for anything Broadwell-or-newer the VA-API driver is intel-media-driver, and there is no lib32 build of it in the repos — so the Intel line silently gives a modern laptop the wrong VA-API driver. (3) Step 4's order is backwards: `pacman -Rns lib32-nvidia-utils` before installing a replacement will be refused, because steam depends on the lib32-vulkan-driver provision that lib32-nvidia-utils is currently satisfying. Install the correct ICD first, then remove.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never install a single lib32 package with `pacman -Sy lib32-nvidia-utils` — that is a partial upgrade and is exactly what produces the `GLXBadContext`/NVRM version skew this record is trying to fix. Use `pacman -Syu`. `lib32-vulkan-intel` and the NVIDIA Vulkan ICD are mutually exclusive per the Arch wiki; installing both on one machine breaks Vulkan for everything. Enabling multilib pulls a full second architecture's worth of libraries — expect a few hundred MB and a longer upgrade every time.

**Fix.**

**1. Enable multilib (skip on Omarchy — already enabled in its shipped pacman.conf).**

```bash
grep -A1 '^\[multilib\]' /etc/pacman.conf
sudo sed -i '/^#\[multilib\]/,+1 s/^#//' /etc/pacman.conf
sudo pacman -Syu
```

**2. Omarchy 4 has a one-shot helper that detects your GPUs and installs the right set:**

```bash
omarchy-install-gaming-gpu-lib32
```

**3. Manual equivalent — install the lib32 packages matching your actual vendor.**

```bash
# always:
sudo pacman -S lib32-vulkan-icd-loader

# AMD:
sudo pacman -S lib32-mesa lib32-vulkan-radeon
#   (lib32-mesa now PROVIDES lib32-libva-mesa-driver - the standalone
#    lib32-libva-mesa-driver package no longer exists, so do not chase it.)

# Intel:
sudo pacman -S lib32-mesa lib32-vulkan-intel
#   VA-API on 32-bit Intel: there is NO lib32-intel-media-driver in the repos.
#   lib32-libva-intel-driver is the legacy i965 driver and is only correct on
#   pre-Broadwell hardware - do not install it on a modern laptop.

# NVIDIA proprietary (must match the 64-bit package exactly):
sudo pacman -S lib32-nvidia-utils
pacman -Q nvidia-utils lib32-nvidia-utils      # the two versions MUST be identical

# Pre-GSP NVIDIA (Maxwell/Pascal/Volta) is on the frozen 580 branch, in the AUR:
#   nvidia-580xx-utils + lib32-nvidia-580xx-utils - these two must match too.
```

If the versions do not match, do a full upgrade (never `pacman -Sy lib32-nvidia-utils`) and switch to an up-to-date mirror:

```bash
sudo pacman -Syu
```

**4. If you already answered a provider prompt wrongly**, install the correct ICD FIRST, then remove the wrong one. Removing first is refused, because steam depends on the `lib32-vulkan-driver` provision the wrong package is currently satisfying:

```bash
pacman -Qs 'lib32-vulkan|lib32-nvidia'
sudo pacman -S lib32-vulkan-radeon       # e.g. on an AMD-only machine
sudo pacman -Rns lib32-nvidia-utils      # now this succeeds
```

**5. Common extras that come up in the same breath:** `lib32-libnm` (Steam library window never appears), `lib32-systemd` (DNS resolution failures inside Steam), `lib32-pipewire` (no audio in 32-bit games).

**Verify.** ```bash
ls /usr/share/vulkan/icd.d/            # must include a *.i686.json for your vendor
vulkaninfo --summary | head -30
LIBGL_DEBUG=verbose glxinfo -B 2>&1 | head
```
Steam starts to the library without the `libGL error` lines, and a 32-bit title (e.g. Half-Life 2) launches.

Sources: <https://wiki.archlinux.org/title/Steam> · <https://wiki.archlinux.org/title/Steam/Troubleshooting> · <https://wiki.archlinux.org/title/Vulkan> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-install-gaming-gpu-lib32> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf>

---

## Stop AMD GPU freezes and reboots when idle or waking from sleep

`amdgpu-idle-freeze-gfxoff-ppfeaturemask` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** An AMD desktop or laptop locks up hard or spontaneously reboots when left idle, typically on a multi-monitor setup, and especially after resuming from sleep. Nothing is logged before the freeze.

**Cause.** AMD PowerPlay's GFXOFF feature (and, on some cards, stutter mode) puts the graphics engine into a power state it does not reliably recover from, producing unrecoverable driver crashes.

> **Audit corrected this record.** The single cited source, https://wiki.archlinux.org/title/AMDGPU, does support the symptom and the general approach. I fetched its raw wikitext and the section "System freezes or reboots when idle" says PowerPlay features such as GFXOFF can cause frequent unrecoverable driver crashes that coincide with idle GPU usage on a multi-monitor setup and especially waking from sleep, which is the record's symptom almost word for word, and it names `amdgpu.ppfeaturemask=0xffff7fff` plus the `0xfffd7fff`, `0xfffd3fff` and `0` alternatives. So the source stands and I removed nothing. The recommended mask is still wrong, and the source is why: the wiki itself says `0xffff7fff` "leaves all other (implemented and unimplemented) PowerPlay features enabled", and the record rewrote that into "disables only PP_GFXOFF_MASK and leaves everything else enabled", which reads as a minimal change when it is not. I checked the driver at tag v7.1: `drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c` sets `uint amdgpu_pp_feature_mask = 0xfff7bfff;` under the comment "OverDrive(bit 14) disabled by default / GFX DCS(bit 19) disabled by default", and `drivers/gpu/drm/amd/include/amd_shared.h` gives `PP_OVERDRIVE_MASK = 0x4000`, `PP_GFXOFF_MASK = 0x8000`, `PP_STUTTER_MODE = 0x20000`, `PP_GFX_DCS_MASK = 0x80000`. So `0xffff7fff` re-enables Overdrive and GFX Async DCS, and the same file's `amdgpu_init` calls `add_taint(TAINT_CPU_OUT_OF_SPEC, ...)` and `pr_crit("Overdrive is enabled ...")` when the Overdrive bit is set. The correct minimal value on kernel 7.1 is the driver default with GFXOFF cleared, `0xfff73fff`, which the wiki also lists, and I replaced the copied ladder with the computed form the wiki uses elsewhere for the Overdrive case. The bigger defect is the same one the last thirty-seven re-audits found. The fix told an Omarchy reader to edit `/etc/default/grub` or the `cmdline:` line in `/boot/limine.conf`. I confirmed on this workstation (omarchy 4.0.2-1, kernel 7.1.9-arch1-2) that `/etc/default/grub` does not exist and no `grub` package is installed, and the installed `/etc/limine-entry-tool.conf` template documents the real path: drop-ins under `/etc/limine-entry-tool.d/*.conf`, `+=` to append and `=` to replace. That agrees with the Limine Arch wiki page and with the existing corpus record `limine-kernel-parameters-not-applying-omarchy`, which I read so this correction does not contradict it. I read `/etc/limine-entry-tool.d/omarchy-defaults.conf` locally and fetched the same file at upstream tag v4.0.3 (published 2026-09-08, the newest tag) and they are identical, so this holds on the current release. I rewrote the danger because the old one said only that disabling PowerPlay costs power and that a bootloader reinstall can drop the parameter, and it missed that a copied mask can itself produce flicker and broken resume, and that a bare `=` in the drop-in silently deletes `initramfs_async=0` and can leave an encrypted machine at a text prompt with no desktop. NOT EXERCISED: this workstation has an NVIDIA GeForce RTX 3090 and no `amdgpu` module is loaded (`/sys/module/amdgpu` does not exist), so no AMD behaviour, no mask and no freeze was reproduced here. Every mask claim comes from the kernel source at v7.1 and the wiki, and I ran nothing that writes to the bootloader or the initramfs.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A wrong mask is the danger here, not a typo in the parameter name. `amdgpu.ppfeaturemask` is a raw bitmask with no validation, so a copied value silently enables features the kernel keeps off. `0xffff7fff`, the value most forum posts quote, turns on Overdrive and GFX Async DCS on kernel 7.1. Overdrive taints the kernel with `TAINT_CPU_OUT_OF_SPEC` and makes any bug report unwelcome upstream, and the Arch wiki warns that enabling unstable PowerPlay bits can cause screen flicker or broken resume from suspend, which is the failure you were trying to fix. `amdgpu.ppfeaturemask=0` disables DPM as well, so the card can sit at boot clocks with poor performance and higher idle power. Disabling GFXOFF at all increases idle power draw and heat, which matters on a laptop.

On Omarchy 4 the second risk is the drop-in itself. Writing `KERNEL_CMDLINE[default]=` instead of `+=`, or naming the file so it sorts before `omarchy-defaults.conf`, throws Omarchy's own defaults away including `initramfs_async=0`. The packaged comment says that parameter is what stops plymouthd exiting on kernel 7.1, so an encrypted machine falls back to an unthemed text LUKS prompt or sits there with no graphical session. `limine-mkinitcpio` rewrites the UKI on the ESP, so run `df -h /boot` first, because a full ESP produces a truncated image that will not boot. Recovery is the Limine snapshot entry or the Limine boot menu editor, and Omarchy's Direct Boot bypasses that menu, so do not enable Direct Boot while you are still testing parameters. The parameter does survive kernel updates once it is in a drop-in, because the drop-in is what the UKI is rebuilt from.

**Fix.**

Disable GFXOFF with the PowerPlay feature mask, but compute the value from your own kernel's default instead of copying a number. Copied masks are the usual defect here, because they set bits the kernel deliberately leaves clear.

```bash
printf 'amdgpu.ppfeaturemask=0x%x\n' \
  "$(( $(cat /sys/module/amdgpu/parameters/ppfeaturemask) & ~0x8000 ))"
```

`0x8000` is `PP_GFXOFF_MASK` in `drivers/gpu/drm/amd/include/amd_shared.h`. On kernel 7.1 the driver default is `0xfff7bfff`, so the command above prints:

```
amdgpu.ppfeaturemask=0xfff73fff
```

**Do not use `0xffff7fff`.** It sets every bit except GFXOFF, which switches on two features kernel 7.1 keeps off on purpose: `PP_OVERDRIVE_MASK` (`0x4000`) and `PP_GFX_DCS_MASK` (`0x80000`). Enabling Overdrive taints the kernel and logs `Overdrive is enabled, please disable it before reporting any bugs unrelated to overdrive.`, and the Arch wiki warns that turning on undefined or unstable PowerPlay bits can itself cause screen flicker or broken resume from suspend.

If freezes persist, clear more bits from the same starting point:

```
0xfff53fff   GFXOFF plus PP_STUTTER_MODE (0x20000) cleared
0            every PowerPlay feature off, diagnostic only, and it costs power management
```

**Apply it on Omarchy 4 in a Limine drop-in.** There is no `/etc/default/grub`, and editing `/boot/limine.conf` does nothing, because Omarchy boots a Unified Kernel Image with the command line baked into the `.efi` and regenerates `/boot/limine.conf` on every kernel transaction. Use your own drop-in that sorts after `omarchy-defaults.conf`, with `+=`:

```bash
sudo tee /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
# `+=` appends. A bare `=` REPLACES Omarchy's defaults and drops
# quiet/splash/initramfs_async=0.
KERNEL_CMDLINE[default]+=" amdgpu.ppfeaturemask=0xfff73fff"
EOF

sudo limine-mkinitcpio
sudo limine-update
sudo reboot
```

The full mechanism, including testing a parameter once from the Limine boot menu with nothing written to disk, is in the record `limine-kernel-parameters-not-applying-omarchy`.

**On other Arch-based systems:**

- Limine: the same `/etc/limine-entry-tool.d/*.conf` drop-in, then `sudo limine-update`
- systemd-boot: the `options` line in `/boot/loader/entries/*.conf`
- GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

Reboot.

**Verify.** ```bash
cat /proc/cmdline                                  # shows amdgpu.ppfeaturemask=0xfff73fff
cat /sys/module/amdgpu/parameters/ppfeaturemask    # shows the same value
```

On Omarchy, `/proc/cmdline` must also still show Omarchy's own defaults (`quiet splash loglevel=0 ... initramfs_async=0`). If they are gone, your drop-in used a bare `=` or sorts before `omarchy-defaults.conf`.

Confirm no Overdrive taint was picked up:

```bash
sudo dmesg | grep -i overdrive     # must print nothing
```

Then leave the machine idle overnight with the monitors attached and check it is still responsive in the morning. As root, `/sys/kernel/debug/dri/0/amdgpu_gfxoff_status` reports the current GFXOFF state if debugfs is mounted.

Sources: <https://wiki.archlinux.org/title/AMDGPU> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/torvalds/linux/blob/v7.1/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c> · <https://github.com/torvalds/linux/blob/v7.1/drivers/gpu/drm/amd/include/amd_shared.h> · <https://github.com/omacom/omarchy/blob/v4.0.3/etc/limine-entry-tool.d/omarchy-defaults.conf>

---

## AMD GPU hangs and resets under load: 'ring gfx_0.0.0 timeout'

`amdgpu-ring-gfx-timeout-gpu-reset` · severity: **high** · frequency: **common** · applies to: `amdgpu`, `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy-4`, `rdna2`, `rdna3`

**Symptom.** Mid-game (or during a shader compile, or in a VR session) the screen freezes for a few seconds, the game crashes or the whole session dies back to a TTY, and `journalctl -k -b -1` shows:

```
amdgpu 0000:03:00.0: amdgpu: ring gfx_0.0.0 timeout, signaled seq=7073226, emitted seq=7073228
amdgpu 0000:03:00.0: amdgpu: Process information: process gamename pid 4711 thread gamename pid 4711
amdgpu 0000:03:00.0: amdgpu: GPU reset begin!
...
amdgpu 0000:03:00.0: amdgpu: GPU reset(1) succeeded!
```

When the reset does not work you get `GPU reset(1) failed with error -110` and a hard lock — no SysRq, only the power button. The milder variant just logs `ring gfx_0.0.0 timeout, but soft recovered` and the game stutters.

**Cause.** A command submitted to the graphics ring did not signal its completion fence within the scheduler's watchdog window (2000 ms by default, per amdgpu's own `lockup_timeout` module parameter description), so the driver declared the ring hung and attempted a reset. That is a *symptom*, not a diagnosis — the actual culprit is almost always one of three things, in rough order of frequency on RDNA2/RDNA3 desktops:

1. **An unstable overclock or undervolt.** DDR5 EXPO/DOCP profiles, PBO/Curve Optimizer, and LACT/CoreCtrl undervolt profiles are the single most common cause of gfx ring timeouts on desktop Radeon cards.
2. **A Mesa/RADV shader bug.** A specific shader compiles to something the hardware chokes on. Reproduces with one game and never with another.
3. **A genuine driver/firmware bug** for that ASIC and kernel combination, or marginal power delivery.

Note that GPU reset is already *enabled* by default on this hardware: amdgpu's `gpu_recovery` defaults to `-1` (auto), and amdgpu_device_should_recover_gpu() returns true under auto for every ASIC except a legacy list (SI, CIK, Carrizo, Stoney, Cyan Skillfish). So on RDNA2/RDNA3 the "GPU reset begin!" you are seeing IS the auto path working; a failed reset is a firmware/hardware problem, not a missing kernel parameter.

This is a different failure from `flip_done timed out` (display pipeline, fixed with amdgpu.dcdebugmask) and from idle GFXOFF lockups — those hang while doing nothing, this one hangs under load.

> **Audit corrected this record.** The diagnosis and the triage order (evidence, then update, then RADV, then overclock, only then kernel params) are excellent, and most specifics verify exactly. The 2000 ms watchdog is right: amdgpu_drv.c:365 reads "GPU lockup timeout in ms (default: 2000...), format: [single value for all] or [GFX,Compute,SDMA,Video]". The RADV_DEBUG strings are verbatim from docs.mesa3d.org/envvars.html, including hang's "$HOME/radv_dumps_<pid>_<time>". noretry's "(0 = retry enabled, 1 = retry disabled, -1 auto (default))" is verbatim from amdgpu_drv.c:715. The devcoredump path is valid — devcoredump.c:421 creates a `devcoredump` symlink on the failing device, so /sys/class/drm/card1/device/devcoredump/data resolves. Two factual errors. (1) The `amdgpu.gpu_recovery=1` bullet is wrong, and wrong in the direction that wastes the reader's reboot: amdgpu_device_should_recover_gpu() (amdgpu_device.c:4878) returns true under the -1 auto default for everything except a short legacy list (SI, CIK, Carrizo, Stoney, Cyan Skillfish). Recovery is NOT "disabled outside SR-IOV" — on the RDNA2/RDNA3 hardware this record targets, auto already enables it and `gpu_recovery=1` is a no-op. (2) The devcoredump does not survive until "the next boot": include/linux/devcoredump.h:16 is `#define DEVCD_TIMEOUT (HZ * 60 * 5)` with the comment "if data isn't read by userspace after 5 minutes then delete it". A reader who thinks they can grab it tomorrow will find it gone. Also, the `sudo tee` in step 5 truncates zz-local.conf, silently discarding any parameter the reader added from a sibling record.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `gpu_recovery` is declared with `module_param_named_unsafe` in the kernel — setting it taints the kernel, and a *failed* reset can wedge the machine harder than the original hang would have, so save your work before testing. Setting `lockup_timeout` too high converts a recoverable ring hang into a multi-second (or permanent) full-desktop freeze. Disabling EXPO/DOCP drops your RAM to JEDEC base speed until you re-enable it. Never leave `RADV_DEBUG=hang` on permanently — it forces synchronisation and costs significant performance.

**Fix.**

**1. Collect the evidence while it is still there — the crash dump self-deletes after FIVE MINUTES.**

The kernel's devcoredump has a hard 5-minute expiry (`DEVCD_TIMEOUT (HZ * 60 * 5)`), so grab it in the same session as the hang, not after a reboot:

```bash
journalctl -k -b -1 | grep -iE 'amdgpu|drm|ring .* timeout' | tail -60
lspci -nnk -d ::03xx
uname -r; pacman -Q mesa vulkan-radeon linux linux-firmware

ls /sys/class/drm/card*/device/devcoredump/ 2>/dev/null
sudo cat /sys/class/drm/card1/device/devcoredump/data > ~/amdgpu-coredump.txt
```

**2. Update first.** Ring timeouts are fixed upstream constantly; a stale Mesa or kernel is the cheapest thing to rule out.

```bash
omarchy update        # Omarchy 4
sudo pacman -Syu      # plain Arch / EndeavourOS / CachyOS
```

**3. Decide whether it is userspace or hardware.** Add to the game's Steam launch options, one at a time:

```
RADV_DEBUG=hang %command%      # writes a report to ~/radv_dumps_<pid>_<time>
RADV_DEBUG=nongg %command%     # disables NGG on GFX10/10.3
RADV_DEBUG=zerovram %command%  # zero-init VRAM allocations
```

If the hang stops under `hang` or `nongg`, it is a Mesa bug — file the dump at gitlab.freedesktop.org/mesa/mesa and stay on the workaround. If it hangs identically under all of them, go to step 4.

**4. Take the overclock out of the picture.** Reboot into firmware setup and disable EXPO/DOCP (RAM back to JEDEC) and PBO/Curve Optimizer, and remove any GPU undervolt:

```bash
systemctl status lactd 2>/dev/null && sudo systemctl stop lactd
ls ~/.config/corectrl/ 2>/dev/null
cat /sys/class/drm/card1/device/pp_od_clk_voltage 2>/dev/null
```

Run the game for an hour. If it is now stable, reintroduce one setting at a time.

**5. Only then reach for kernel parameters.** On Omarchy 4 add them as a drop-in that sorts after Omarchy's own defaults. Use `tee -a` — a bare `tee` truncates the file and would discard any parameter you added earlier from another record:

```bash
sudo tee -a /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
# `+=` appends; a bare `=` would wipe Omarchy's defaults.
KERNEL_CMDLINE[default]+=" amdgpu.lockup_timeout=10000"
EOF
sudo limine-mkinitcpio && sudo limine-update && sudo reboot
```

Useful values, per amdgpu's own module documentation:

- `amdgpu.lockup_timeout=10000` — watchdog in ms (default 2000); format is a single value or `GFX,Compute,SDMA,Video`. Use only if a legitimately long compute/shader job is being killed.
- `amdgpu.noretry=0` — re-enable XNACK retry faults (`0 = retry enabled, 1 = retry disabled, -1 = auto`). Worth a try on GFX9/Vega where a VM fault escalates into a ring hang.
- `amdgpu.gpu_recovery=1` — **only useful on legacy ASICs.** The `-1` auto default already enables recovery on everything except SI, CIK, Carrizo, Stoney and Cyan Skillfish, so on RDNA2/RDNA3 this parameter changes nothing. If your reset is failing with `error -110`, that is a firmware/hardware problem and this will not fix it.

On GRUB systems put the same parameters in `GRUB_CMDLINE_LINUX_DEFAULT` in /etc/default/grub and run `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

**Verify.** Run the offending workload for 30+ minutes. `journalctl -k -b | grep -i 'ring .* timeout'` stays empty, or at worst shows `but soft recovered` with no `GPU reset`. `cat /sys/class/drm/card1/device/gpu_recovery 2>/dev/null` and `cat /sys/module/amdgpu/parameters/gpu_recovery` reflect the value you set.

Sources: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/amdgpu_job.c> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c> · <https://docs.mesa3d.org/envvars.html> · <https://bbs.archlinux.org/viewtopic.php?id=301378> · <https://bbs.archlinux.org/viewtopic.php?id=284033> · <https://wiki.archlinux.org/title/AMDGPU>

---

## Fix black/flickering video in Chromium browsers on hybrid Intel+NVIDIA

`chromium-video-black-hybrid-angle` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** After a system update, videos in Chromium, Brave or Chrome show a black rectangle, stutter badly, or the browser crashes. Launching from a terminal spews:

```
ERROR:ui/gl/angle_platform_impl.cc:42] ImageEGL.cpp:112 (operator()): eglCreateImage failed with 0x00003009
ERROR:gpu/command_buffer/service/shared_image/ozone_image_backing.cc:316] OzoneImageBacking::ProduceSkiaGanesh failed to create GL representation
ERROR:gpu/command_buffer/service/shared_image/shared_image_manager.cc:404] SharedImageManager::ProduceSkia: Trying to produce a Skia representation from an incompatible backing: OzoneImageBacking
```

**Cause.** Cross-GPU buffer sharing. The compositor renders on one GPU (often the NVIDIA dGPU) while Chromium's ANGLE/EGL path imports DMA-BUFs allocated on the other (the Intel iGPU). The two do not agree on format modifiers, so `eglCreateImage` fails and every video frame is dropped.

> **Audit corrected this record.** The symptom, the eglCreateImage 0x3009 / OzoneImageBacking log trio and the cross-GPU DMA-BUF modifier explanation are real and match Omarchy issues 3891 and 4901 (both exist, titled 'Videos not playing after recent update' and 'Hybrid Intel+NVIDIA: Chromium hardware acceleration requires manual workarounds'). Two flags are wrong: `--use-gl=desktop` was removed from Chromium years ago (Linux is ANGLE-only now; the value is ignored/errors and the modern equivalent is `--use-angle=gl`), and `--disable-gpu-compositing` is offered as a routine step when it turns off GPU compositing browser-wide — a last-resort sledgehammer that costs performance everywhere.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Pin Chromium's VA-API to the iGPU:

```
env = LIBVA_DRIVER_NAME,iHD            # Omarchy 3.x / Hyprland <= 0.54
```
```lua
hl.env("LIBVA_DRIVER_NAME", "iHD")     -- Hyprland 0.55+ / Omarchy 4
```

Then `~/.config/chromium-flags.conf` (or `brave-flags.conf` / `chrome-flags.conf`):

```
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandLinuxDrmSyncobj,VaapiVideoDecodeLinuxGL,VaapiVideoEncoder
--enable-gpu-rasterization
--enable-zero-copy
--ignore-gpu-blocklist
```

Fully restart the browser (`pkill chromium`) and check `chrome://gpu` — 'Video Decode: Hardware accelerated' and no ANGLE/EGL errors.

If video is still black, escalate in this order:

```
--use-angle=gl          # force the GL ANGLE backend instead of the default
```

and only as a last resort:

```
--disable-gpu-compositing   # disables GPU compositing for the whole browser
```

Do not use `--use-gl=desktop` (removed from Chromium; silently ignored) and do not use `--use-angle=vulkan` on this setup (reported to render the window transparent).

**Verify.** `chrome://gpu` shows 'Video Decode: Hardware accelerated' and no `eglCreateImage` errors on stderr; a 1080p YouTube video plays smoothly and `intel_gpu_top` shows the Video engine above 0%.

Sources: <https://github.com/basecamp/omarchy/issues/4901> · <https://github.com/basecamp/omarchy/issues/3891> · <https://github.com/basecamp/omarchy/issues/3899> · <https://wiki.archlinux.org/title/Hardware_video_acceleration>

---

## Make Hyprland use the right GPU with AQ_DRM_DEVICES

`hyprland-wrong-gpu-aq-drm-devices` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** On a multi-GPU machine Hyprland either picks the wrong renderer (dGPU pegged and hot on a laptop, or the compositor is unusably laggy), or a monitor plugged into the second GPU shows nothing at all and is missing from `hyprctl monitors`.

**Cause.** Hyprland's aquamarine backend picks a DRM device on its own. `/dev/dri/card0` and `card1` are assigned at boot and can swap between reboots, so whichever card is enumerated first wins. Any GPU that drives a monitor must be in the device list, even if it is not the primary renderer.

> **Audit corrected this record.** Checked on this omarchy 4.0.2-1 workstation (Hyprland 0.56.2, kernel 7.1.9-arch1-2) and against both cited wiki pages fetched in full. The cause holds and is left alone: the upstream Multi-GPU page (fetched as `content/configuring/extra/multi-gpu.md` from `hyprwm/hyprland-wiki`) says the `cardN` symlink is dynamically assigned at boot and unsuitable as a GPU marker, and says a card driving a monitor must appear in `AQ_DRM_DEVICES` even when it is not the primary renderer. Confirmed on this machine that `cardN` numbering is not even dense: one RTX 3090 at `01:00.0` is `card1` and there is no `card0`.

The fix was wrong for Omarchy 4 in the way the brief predicts. It wrote `env = AQ_DRM_DEVICES,...` into `~/.config/hypr/envs.conf`, which is hyprlang syntax in a file nothing reads. Confirmed here: `~/.config/hypr/hyprland.lua` requires only `hypr.monitors`, `hypr.input`, `hypr.bindings`, `hypr.looknfeel` and `hypr.autostart`, and `grep -rn 'hypr.envs' /usr/share/omarchy ~/.config/hypr` returns exactly one hit, `default.hypr.envs` at `/usr/share/omarchy/default/hypr/omarchy.lua:16`, so `~/.config/hypr/envs.lua` is dead too. The record already carried an `hl.env` line but offered it as a "Hyprland 0.55+" afterthought rather than the Omarchy 4 path, and gave no placement rule. Rewrote the fix to lead with `hl.env` in `~/.config/hypr/hyprland.lua` below `require("default.hypr.omarchy")`, and kept the hyprlang form labelled as Hyprland 0.54 and older on plain Arch.

Two source URLs are dead and are removed. `https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Advanced%20and%20Cool/Multi-GPU.md` returns 404: the page moved to `content/configuring/extra/multi-gpu.md`, canonical `https://wiki.hypr.land/configuring/extra/multi-gpu/`. `https://github.com/basecamp/omarchy/issues/1776` returns 404 over HTTP even though `https://github.com/basecamp/omarchy` itself redirects to `omacom/omarchy`: the rename redirect does not carry issue paths, so `https://github.com/omacom/omarchy/issues/1776` replaces it. Read issue 1776 in full. It is a hybrid-GPU power-management request and it does support the udev symlink recipe and the `AQ_DRM_DEVICES` list, though its own instructions put the export in `~/.config/uwsm/env` and in `~/.config/hypr/hyprland.conf`, both of which are Omarchy 3 era advice.

Corrected the uwsm branch rather than deleting it. The record named `~/.config/uwsm/env-hyprland`, which `/usr/share/doc/uwsm/README.md` (uwsm 0.26.7-1) does list, but Omarchy 4's default session is `/usr/share/wayland-sessions/hyprland.desktop` with `Exec=/usr/bin/start-hyprland` and no uwsm, and the uwsm-managed entry is a separate `hyprland-uwsm.desktop`. Confirmed the running compositor here is `Hyprland --watchdog-fd 4` with no uwsm in the process tree. Omarchy's own `/usr/share/uwsm/env.d/10-omarchy` points users at `~/.config/uwsm/env.d/*`, so that is what the fix now shows.

Corrected `verify`. `nvidia-smi` showing no processes is not a usable test on Omarchy 4, because `/usr/share/omarchy/default/hypr/nvidia.lua` sets `LIBVA_DRIVER_NAME=nvidia` on Turing and newer and that alone keeps browsers holding `/dev/nvidia-uvm`. Replaced it with reading the compositor's own DRM file descriptors, confirmed working here as an unprivileged user: `ls -l /proc/$(pgrep -x Hyprland | head -1)/fd` shows three `card1` handles and four `renderD128`. Also noted where the line falls against the neighbouring record: `nvidia-env-forced-on-igpu-primary-hybrid-laptop` owns the `LIBVA_DRIVER_NAME` and `__GLX_VENDOR_LIBRARY_NAME` pin that Omarchy forces on hybrid laptops, this record owns which DRM device the compositor renders and scans out on. They are adjacent and not duplicates.

Corrected `danger`. The original advised testing by running `Hyprland` from `Ctrl+Alt+F2` and pressing Ctrl+C, which does not work on Omarchy: a second `Hyprland` reads the same `~/.config/hypr/hyprland.lua`, tries to start a full second Omarchy session, and cannot take DRM master while the first compositor holds it. Kept the real risk, which is a next login with no output, added that `hyprctl reload` neither tests nor undoes the change because aquamarine reads the variable once at backend creation, and made the TTY the recovery route rather than the test route. Left severity `high` and frequency `common` alone.

Not exercised: this is a single-GPU NVIDIA desktop with one card at `01:00.0`, so no multi-GPU selection, no udev symlink, no `AQ_FORCE_LINEAR_BLIT` and no iGPU-primary path could be tried here. `AQ_DRM_DEVICES` is unset in this session. Nothing on this machine was modified and no `hyprctl` command other than read-only `version`, `monitors` and the process inspection above was run. The ordering claim that an `hl.env` below `require("default.hypr.omarchy")` wins is taken from the shipped comment in `~/.config/hypr/hyprland.lua` and from the neighbouring record's own audit, not re-tested here.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** If the list names only a GPU that drives no monitor, or a symlink that does not exist, Hyprland starts with no visible output and your next login is a black screen. Aquamarine reads the variable only when it creates the DRM backend, so `hyprctl reload` cannot test it and cannot undo it either.

Check every path resolves before you log out:

```bash
ls -l /dev/dri/intel-igpu /dev/dri/nvidia-dgpu
```

Make sure you can reach a text console with `Ctrl + Alt + F2` first, so a bad list costs one line deleted from `~/.config/hypr/hyprland.lua` rather than a rebuild. On Omarchy 4 there is no second desktop session to fall back into.

Do not try to test it by running a second `Hyprland` from the console. On Omarchy that reads the same `~/.config/hypr/hyprland.lua` and tries to start a whole second Omarchy session, and it cannot take DRM master while the first compositor holds it, so the run tells you nothing about the variable.

**Fix.**

Identify the cards by PCI address, not by `cardN`. The `cardN` numbers are handed out at boot and are not even predictable on a single-GPU machine. This workstation has one RTX 3090 and its node is `card1`, with no `card0` present at all.

```bash
lspci -d ::03xx
ls -l /dev/dri/by-path
```

Create a stable symlink for each card with udev. The example is for an Intel iGPU. Repeat it with `AMD` or `NVIDIA` and a different symlink name for the other card:

```bash
IGPU_ID=$(lspci -d ::03xx | grep 'Intel' | cut -f1 -d' ')
sudo tee /etc/udev/rules.d/90-intel-igpu-dev-path.rules >/dev/null <<EOF
KERNEL=="card*", KERNELS=="0000:$IGPU_ID", SUBSYSTEM=="drm", SUBSYSTEMS=="pci", SYMLINK+="dri/intel-igpu"
EOF

sudo udevadm control --reload
sudo udevadm trigger
ls -l /dev/dri/intel-igpu
```

Then give Hyprland the priority order. The first entry is the primary renderer and the list is `:`-separated.

**Omarchy 4.** Put the line in `~/.config/hypr/hyprland.lua`, below the `require("default.hypr.omarchy")` line, so it loads after Omarchy's defaults:

```lua
-- ~/.config/hypr/hyprland.lua, below require("default.hypr.omarchy")
hl.env("AQ_DRM_DEVICES", "/dev/dri/intel-igpu:/dev/dri/nvidia-dgpu")
```

Do not use `~/.config/hypr/envs.conf` or `~/.config/hypr/envs.lua`. Omarchy 4 reads neither. The shipped `~/.config/hypr/hyprland.lua` requires only `hypr.monitors`, `hypr.input`, `hypr.bindings`, `hypr.looknfeel` and `hypr.autostart`, nothing in `/usr/share/omarchy` requires `hypr.envs`, and the only `envs` module in the tree is `default.hypr.envs`, required at `/usr/share/omarchy/default/hypr/omarchy.lua:16`. A file at either of those paths is simply never read.

**Plain Arch on Hyprland 0.55 or newer**, which also uses Lua. The same call, in whichever file your `hyprland.lua` loads:

```lua
hl.env("AQ_DRM_DEVICES", "/dev/dri/intel-igpu:/dev/dri/nvidia-dgpu")
```

**Plain Arch on Hyprland 0.54 or older**, which still uses hyprlang:

```
env = AQ_DRM_DEVICES,/dev/dri/intel-igpu:/dev/dri/nvidia-dgpu
```

**If you log in through a uwsm-managed session** you can export the variable before the compositor starts instead. Omarchy 4 ships both session entries, `/usr/share/wayland-sessions/hyprland.desktop` (`Exec=/usr/bin/start-hyprland`, no uwsm) and `/usr/share/wayland-sessions/hyprland-uwsm.desktop`, and the default is the plain one, so check which you are on before bothering:

```bash
pgrep -a uwsm
```

If you are on the uwsm session, Omarchy's own `/usr/share/uwsm/env.d/10-omarchy` points at the `env.d` directory:

```
# ~/.config/uwsm/env.d/gpu
export AQ_DRM_DEVICES="/dev/dri/intel-igpu:/dev/dri/nvidia-dgpu"
```

uwsm also reads `~/.config/uwsm/env` and `~/.config/uwsm/env-hyprland`, per `/usr/share/doc/uwsm/README.md`.

If a secondary monitor on the NVIDIA card is still broken or laggy, add:

```lua
hl.env("AQ_FORCE_LINEAR_BLIT", "0")
```

Log out and back in. `hyprctl reload` is not enough. Aquamarine reads `AQ_DRM_DEVICES` once, when it creates the DRM backend at compositor start, so a reload re-parses the config without re-picking the device.

**Verify.** Check which DRM nodes the compositor actually opened, and which vendor owns them:

```bash
ls -l /proc/$(pgrep -x Hyprland | head -1)/fd | grep -oE 'card[0-9]+|renderD[0-9]+' | sort | uniq -c

for n in /sys/class/drm/renderD*; do
  printf '%s %s vendor=%s\n' "$(basename "$n")" "$(basename "$(readlink -f "$n/device")")" "$(cat "$n/device/vendor")"
done
```

Vendor `0x8086` is Intel, `0x1002` is AMD, `0x10de` is NVIDIA. The node Hyprland holds should be the one you named first.

```bash
hyprctl monitors            # every connected display is listed
env | grep AQ_DRM_DEVICES   # your list, in a terminal Hyprland spawned
```

Do not use `nvidia-smi` showing no processes as the test. On Omarchy 4 `/usr/share/omarchy/default/hypr/nvidia.lua` sets `LIBVA_DRIVER_NAME=nvidia` on Turing and newer cards, which keeps browsers holding `/dev/nvidia-uvm` open for reasons that have nothing to do with `AQ_DRM_DEVICES`. That is the subject of `nvidia-env-forced-on-igpu-primary-hybrid-laptop`.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.hypr.land/configuring/extra/multi-gpu/> · <https://github.com/omacom/omarchy/issues/1776>

---

## Boot the Omarchy install USB with nomodeset when an NVIDIA machine goes to a black screen

`installer-usb-black-screen-nvidia-nomodeset` · severity: **high** · frequency: **common** · applies to: `desktop`, `installer`, `laptop`, `nvidia`, `omarchy`

**Symptom.** Booting the Omarchy 4 (Quattro) install medium on a machine with an NVIDIA card shows a black screen and never reaches the installer. Reported on an RTX 5060 Ti, an RTX 5060 and an RTX 4090 in this thread, and on an RTX 3060 in #7061. One reporter saw the screen stay black for about 20 seconds, the keyboard backlight go out, and the monitor start its sleep countdown. On UEFI no boot menu is shown at all, so there is nowhere obvious to type a kernel parameter.

**Cause.** The workaround is confirmed by three reporters on three cards in #7045, an RTX 5060 Ti, an RTX 4090 and an RTX 5060, and by a fourth reporter on an RTX 3060 in #7061. The mechanism is the collaborator's reading of the `omarchy-iso` sources, not a reproduction, since nobody triaging had an NVIDIA card. `configs/airootfs/etc/mkinitcpio.conf.d/archiso.conf` puts `kms` in HOOKS with no `autodetect`, so every in-tree DRM driver is built into the live initramfs and modesets during the live boot. `builder/build-iso.sh` adds no NVIDIA driver to the live environment, so nouveau is the NVIDIA display driver in play. The default boot entry carries `quiet splash`, so when that takeover fails nothing is left on screen. Exactly what nouveau gets wrong on these cards is not established. The missing UEFI menu is configuration, not a symptom: `configs/grub/grub.cfg` in `omacom/omarchy-iso` sets `timeout=0` and `timeout_style=hidden` at lines 49 and 50, and `configs/grub/loopback.cfg` does the same for the Ventoy and loopback path, so GRUB boots the default entry on every UEFI machine without drawing anything (re-read on `quattro` on 2026-09-11). Legacy BIOS boots show a syslinux menu for 15 seconds (`TIMEOUT 150` in `configs/syslinux/archiso_sys.cfg`). `nomodeset` is needed on the live medium only. The installed system boots normally without it afterwards, confirmed on the 4090.

> **Audit corrected this record.** Re-read issue omacom/omarchy#7045 in full today with all eleven comments, plus issue #7061, plus every cited omarchy-iso file on the `quattro` branch. The issues do support the symptom and the workaround: the opening report is an RTX 5060 Ti whose author states that adding `nomodeset` to the installer's GRUB parameters lets the installer boot, joaomcarlos confirmed the same on an RTX 4090 after patching the stick with `dd`, fbal98 confirmed it on an RTX 5060 from the `grub>` prompt using the exact four commands the record quotes, and Ycaro-Oleg reports the same live-ISO failure and workaround on an RTX 3060 in #7061. Confirmed from source on 2026-09-11: `configs/grub/grub.cfg:49-50` still sets `timeout=0` and `timeout_style=hidden` with no `nomodeset` entry, `configs/grub/loopback.cfg` matches it, `configs/syslinux/archiso_sys.cfg:4` sets `TIMEOUT 150`, `configs/syslinux/archiso_sys-linux.cfg:6` carries the exact menu label the fix tells the user to highlight, `configs/airootfs/etc/mkinitcpio.conf.d/archiso.conf:2` puts `kms` in HOOKS with no `autodetect`, `builder/build-iso.sh:121` adds no NVIDIA driver to the live environment, and `configs/profiledef.sh` sets `install_dir="arch"` and `arch="x86_64"`, which is what makes the `/arch/boot/x86_64/vmlinuz-linux-t2` paths in the `grub>` recipe correct. Two things were wrong. The canonical repository name is `omacom/omarchy-iso` and every source URL in the record used the old `omacom-io/omarchy-iso` name, which redirects on github.com but is not the current name. And the release enumeration is stale: PR #110 is still open at head `c7cbcb4` with base `quattro`, last updated 2026-09-08 and never merged, while omarchy v4.0.3 was published on 2026-09-08, so the affected-image list has to include it rather than stopping at 4.0.2. I also added a labelled note on `omacom/omarchy-iso#160`, raised on #7045 on 2026-09-07, which puts `modprobe.blacklist=nouveau` on both GRUB boot paths and deliberately not on the syslinux one, is still open, and has never been tested by anyone with an affected card. On this machine I confirmed only that an installed Omarchy 4.0.2 NVIDIA system has no `nomodeset` in `/proc/cmdline`, which supports the verify step. Nothing about the live ISO boot was exercised: this workstation runs `nvidia-open-dkms 610.57.04` on a card none of the reports cover, and booting an install medium is outside what a read-only audit can do.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Add `nomodeset` to the live medium's kernel command line for that one boot.

**Legacy BIOS boot.** The syslinux menu is visible for 15 seconds. Highlight `Omarchy install medium (x86_64, BIOS)`, press Tab, append ` nomodeset` to the end of the line, press Enter.

**UEFI boot, if you can raise the hidden GRUB menu.** Hold Shift from the moment the firmware hands off. This is a GRUB side effect that depends on the firmware reporting modifier state, so it may do nothing. If a menu appears, highlight `Omarchy`, press `e`, find the line beginning `linux`, append ` nomodeset`, and press Ctrl-X.

**UEFI boot, no menu at all.** Get to the `grub>` prompt (one reporter reached it with Shift+Esc during boot, on one machine) and boot the live kernel by hand. The paths and arguments are the shipped default entry with `archisosearchuuid=` swapped for `archisosearchfilename=`, because the UUID is not known at a bare prompt:

```
search --file --set=root /arch/boot/x86_64/vmlinuz-linux-t2
linux /arch/boot/x86_64/vmlinuz-linux-t2 archisobasedir=arch archisosearchfilename=/arch/boot/x86_64/vmlinuz-linux-t2 quiet splash xe.enable_panel_replay=0 initramfs_async=0 nomodeset
initrd /arch/boot/x86_64/initramfs-linux-t2.img
boot
```

If the screen still goes black, drop `quiet splash` from that `linux` line so the last kernel message stays visible.

The installer then runs as normal, and the installed system does not need `nomodeset`.

**Status of the real fix, re-checked on 2026-09-11.** The proposed fix is an `Omarchy with safe graphics` menu entry carrying `nomodeset` plus a three second visible menu, `omacom/omarchy-iso#110`. It is still open and has never merged, head `c7cbcb4`, base `quattro`, last updated 2026-09-08. `quattro` still sets `timeout=0` and `timeout_style=hidden` at `configs/grub/grub.cfg:49-50` and carries no `nomodeset` entry anywhere, and both the nightly and the released image build from `quattro`, so every image published up to and including the omarchy v4.0.3 release of 2026-09-08 still black-screens with no safe entry and no visible UEFI menu.

A second and different proposal, `omacom/omarchy-iso#160`, puts `modprobe.blacklist=nouveau` on both GRUB boot paths (`configs/grub/grub.cfg` and `configs/grub/loopback.cfg`, deliberately not on the syslinux BIOS path). That would rescue the boot with nothing for the user to select and without stopping Intel or AMD modesetting. It is also open and unmerged, it was raised for an unrelated reason, and nobody with an affected card has tested it, so treat it as an idea rather than a workaround.

**Verify.** The Omarchy logo and the installer's configurator appear instead of a black screen. After the install, reboot without the USB stick: the installed system starts its graphical session with no `nomodeset` anywhere (`cat /proc/cmdline` shows the Omarchy defaults only).

Sources: <https://github.com/omacom/omarchy/issues/7045> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/grub/grub.cfg> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/syslinux/archiso_sys-linux.cfg> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/syslinux/archiso_sys.cfg> · <https://github.com/omacom/omarchy-iso/pull/110> · <https://github.com/omacom/omarchy/issues/7061> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/grub/loopback.cfg> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/etc/mkinitcpio.conf.d/archiso.conf> · <https://github.com/omacom/omarchy-iso/blob/quattro/builder/build-iso.sh> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/profiledef.sh> · <https://github.com/omacom/omarchy-iso/pull/160> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3>

---

## nouveau grabs the card instead of the NVIDIA driver (or a stale blacklist stops nvidia loading)

`nouveau-loaded-instead-of-nvidia-blacklist` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy-4`

**Symptom.** Two mirror-image complaints.

Direction A — "I installed the NVIDIA driver but nothing uses it": `lspci -k` says `Kernel driver in use: nouveau`, `nvidia-smi` fails, and `glxinfo -B` reports a Mesa/NVK/llvmpipe renderer. Games run at single-digit FPS.

Direction B — the reverse: `nvidia-smi` fails with `NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver`, and `journalctl -b` shows the module was refused:

```
modprobe: ERROR: could not insert 'nvidia': Operation not permitted
```

or `sudo modprobe -v nvidia` prints `install /bin/false` / reports the module is blacklisted — while `/etc/modprobe.d/` looks empty to you.

**Cause.** nouveau and nvidia both claim the same PCI device; whichever binds first wins. The blacklist that separates them ships with nvidia-utils at /usr/lib/modprobe.d/nvidia-utils.conf, which currently contains `blacklist nouveau`, `blacklist nova_core`, `blacklist nova_drm`, `softdep nvidia post: nvidia-uvm nvidia-drm`, plus two `options nvidia NVreg_*` lines.

Direction A (nouveau wins) happens when nvidia-utils is not installed (you installed only nvidia-dkms), or the initramfs was built before it was and the `kms` hook still pulls nouveau in during early boot, or the NVIDIA module failed to build for the running kernel.

Direction B (nvidia refused) is where the original cause overreached. A plain `blacklist nvidia` line only suppresses automatic, alias-driven loading — it does not block an explicit `modprobe nvidia`, and it never produces `Operation not permitted`. That EPERM refusal comes from one of: an `install nvidia /bin/false` line in /etc/modprobe.d/ (the form old "disable the dGPU" howtos actually use, and the only modprobe.d form that defeats explicit loading), `/proc/sys/kernel/modules_disabled=1`, or kernel lockdown/module-signature enforcement. A `module_blacklist=`/`modprobe.blacklist=` kernel parameter likewise only blocks autoload and is invisible to modprobe.d inspection. So on Direction B, check for `install ... /bin/false` and for enforcement — not just for a blacklist line — because /etc/modprobe.d/ genuinely can look empty of relevant blacklists while nvidia is still being refused.

> **Audit corrected this record.** The core is right and the diagnostics are unusually good — `lspci -k -d ::03xx` is valid (pciutils lib/filter.c parse_hex_field accepts 'x' wildcards for the class field, and the Hyprland Multi-GPU wiki uses the identical form), /etc/modprobe.d overriding /usr/lib/modprobe.d is correct, and `systemd-analyze cat-config modprobe.d` is the right merged view. Three defects. (1) Direction B's headline symptom is misattributed: `blacklist nvidia` does NOT stop an explicit `modprobe nvidia` — blacklist only suppresses alias-driven autoload. `could not insert 'nvidia': Operation not permitted` (EPERM) comes from an `install nvidia /bin/false` line, /proc/sys/kernel/modules_disabled, or lockdown — not from a blacklist entry. A reader hunting for a bare blacklist line on that error will find nothing. (2) The quoted /usr/lib/modprobe.d/nvidia-utils.conf is stale: the current file (nvidia-utils 610.57.04) also carries `options nvidia NVreg_UseKernelSuspendNotifiers=1` and `options nvidia NVreg_TemporaryFilePath=/var/tmp`. The blacklist/softdep half quoted is verbatim correct. (3) `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -S nvidia-utils` is cargo-cult: I read the guard, and it only trips when both a sync and a sysupgrade flag are present, so a plain `pacman -S` never needed the escape hatch.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Adding the NVIDIA modules to `MODULES=` (early KMS) is documented by both Arch and the Hyprland wiki to break resume-from-hibernation — the machine cold-boots instead of restoring. If you hibernate, skip that step. Removing `kms` from `HOOKS` costs you the early framebuffer and a themed Plymouth/LUKS prompt. Always rebuild the initramfs *and* regenerate the boot entries before rebooting; a UKI built from a half-edited mkinitcpio.conf boots to a black screen, and on Omarchy 4 you then need the Limine snapshot entry to get back.

**Fix.**

**1. Find out who owns the card and what is actually blocking what.**

```bash
lspci -k -d ::03xx                       # "Kernel driver in use:" line is the answer
lsmod | grep -E 'nouveau|nvidia|nova'

# merged view of EVERY modprobe.d fragment, in priority order:
systemd-analyze cat-config modprobe.d | grep -nE 'nouveau|nvidia|nova'
grep -rnE 'blacklist (nouveau|nvidia|nova)|^install (nvidia|nouveau)' /etc/modprobe.d/ /usr/lib/modprobe.d/

# the command line overrides modprobe.d entirely - check it too:
grep -oE 'module_blacklist=[^ ]*|modprobe\.blacklist=[^ ]*|nomodeset' /proc/cmdline

sudo modprobe -v nvidia                  # shows exactly what modprobe would do
```

If `modprobe nvidia` fails with `Operation not permitted`, that is NOT a plain blacklist — check these three instead:

```bash
cat /proc/sys/kernel/modules_disabled     # want: 0
cat /sys/kernel/security/lockdown         # want: [none] integrity confidentiality
cat /sys/module/module/parameters/sig_enforce   # want: N
```

**Direction A - nouveau is winning.** Install the package that owns the blacklist, then rebuild the initramfs:

```bash
# Omarchy 4 (idiomatic; the update guard only blocks -Syu, so plain -S is fine either way):
omarchy-pkg-add nvidia-utils
# plain Arch/EndeavourOS/CachyOS:
sudo pacman -S nvidia-utils

# optional but decisive: load the NVIDIA modules early instead of nouveau
sudoedit /etc/mkinitcpio.conf
#   MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
#   (on an Intel iGPU + NVIDIA dGPU laptop put i915 FIRST: MODULES=(i915 nvidia ...))

sudo limine-mkinitcpio && sudo limine-update   # Omarchy 4
# or, on plain mkinitcpio systems:
sudo mkinitcpio -P
sudo reboot
```

If you would rather not use early KMS, you can instead keep nouveau out of the image by removing `kms` from the `HOOKS` array in /etc/mkinitcpio.conf and rebuilding - the alternative the Arch NVIDIA page documents.

**Direction B - something is stopping nvidia.** Remove whatever the greps above named:

```bash
# a blacklist/install fragment (use the real filename you found):
sudo rm /etc/modprobe.d/blacklist-nvidia.conf

# if it was on the command line, on Omarchy 4 (note tee -a, so you do not
# clobber an existing zz-local.conf):
sudoedit /etc/limine-entry-tool.d/zz-local.conf  # remove module_blacklist=nvidia...
sudo limine-mkinitcpio && sudo limine-update
sudo reboot
```

If instead `modules_disabled` was 1, or lockdown/sig_enforce was enforcing, this is not a blacklist problem at all - see the Secure Boot / module-signature record.

**Verify.** `lspci -k -d ::03xx` shows `Kernel driver in use: nvidia`; `cat /sys/module/nvidia_drm/parameters/modeset` returns `Y`; `nvidia-smi` prints the device table; `lsmod | grep nouveau` is empty.

Sources: <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/Kernel_module> · <https://gitlab.archlinux.org/archlinux/packaging/packages/nvidia-utils/-/raw/main/nvidia-utils.conf> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Nvidia/_index.md> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pacman-guard>

---

## Fix corrupted browser video and a dGPU that never sleeps on a hybrid laptop whose panel runs on the iGPU

`nvidia-env-forced-on-igpu-primary-hybrid-laptop` · severity: **high** · frequency: **common** · applies to: `amd`, `chrome`, `chromium`, `edge`, `electron`, `hyprland`, `intel`, `laptop`, `nvidia`, `omarchy`, `teams`

**Symptom.** Omarchy 4.0.1 or later on a hybrid laptop whose Intel or AMD iGPU renders the session. Usually the NVIDIA card drives nothing, but the same failure happens when it scans out an external monitor while the compositor and the browser still render on the iGPU.

Chromium, Chrome, Edge, Discord, Teams and other Electron apps show corrupted or black video, ghosting while scrolling, elements that paint only on mouse hover, hard scroll stalls on video-heavy pages, or a WebRTC stream that never paints. Live streams with a chat panel open are the most reliable trigger, while static pages stay smooth and ordinary playback can look fine. Rarely the browser's GPU process aborts with `SIGTRAP` and leaves a `chromium` core with `--type=gpu-process` in `coredumpctl`. Launched from a terminal, Chromium prints hundreds of:

```
eglCreateImage failed with 0x00003009
Unable to initialize binding from pixmap
OzoneImageBacking::ProduceSkiaGanesh failed to create GL representation
```

The session carries the NVIDIA values even though the NVIDIA card is not the rendering device:

```console
$ systemctl --user show-environment | grep -E 'LIBVA|NVD_BACKEND|__GLX'
LIBVA_DRIVER_NAME=nvidia
NVD_BACKEND=direct
__GLX_VENDOR_LIBRARY_NAME=nvidia
```

`vainfo` reports the NVDEC driver rather than the Intel or AMD one, and installing `intel-media-driver` alone changes nothing. On most of the reported machines every NVIDIA connector under `/sys/class/drm/` reads `disconnected` and `disabled` while the iGPU's `eDP-1` is `connected`, but on several the NVIDIA card has a live external output and the browser's GPU process is still pinned to the iGPU's render node.

On battery the dGPU never runtime-suspends while a browser is open. `/sys/bus/pci/devices/<dgpu>/power/runtime_status` stays `active` and `runtime_suspended_time` stays 0. One reporter measured the dGPU at about a third of idle draw on a 99.9 Wh laptop.

**Cause.** Established in the threads by the repository's triage collaborator, from source, and confirmed on an omarchy 4.0.2-1 workstation where `nvidia.lua` and all three detectors read exactly as described. The file is unchanged at the `v4.0.3` tag. The cluster's canonical thread is issue 8215.

`/usr/share/omarchy/default/hypr/nvidia.lua`, loaded from `default/hypr/envs.lua`, which `default/hypr/omarchy.lua` requires, runs `hl.env("NVD_BACKEND", "direct")`, `hl.env("LIBVA_DRIVER_NAME", "nvidia")` and `hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")` whenever `bin/omarchy-hw-nvidia` and `bin/omarchy-hw-nvidia-gsp` both succeed. Those detectors only check that a PCI device with vendor `0x10de` at class `0x03*` exists with a device id at or above `0x1e00`, which is Turing and newer. Neither asks whether the NVIDIA GPU renders or scans out anything, and class `0x0302`, a 3D controller, drives no display by definition. `default/hypr/autostart.lua` then exports the whole environment session-wide on `hyprland.start` through `systemctl --user import-environment` and `dbus-update-activation-environment --systemd --all`, so every app inherits it.

`LIBVA_DRIVER_NAME` overrides libva's DRM-based autodetection, so every VA-API client loads `nvidia_drv_video.so` against the iGPU's render node. Compositing then happens on the iGPU while NVDEC decode runs on the NVIDIA card and the exported frames cross GPUs, which fails on import with `EGL_BAD_MATCH`. A contributor isolated the rare abort to Chromium's `CHECK_EQ(handle.modifier, object.drm_format_modifier)` in `VaapiWrapper::ExportVASurfaceAsNativePixmapDmaBufUnwrapped`, because `libva-nvidia-driver` returns a different NVIDIA block-linear modifier for the half-height UV plane than for the Y plane. The NVIDIA VA driver is decode only and exposes no `VAEntrypointEnc*` entrypoints, so the pin removes the iGPU's hardware encode as well. Any app touching video decode also opens `/dev/nvidia-uvm`, which is what blocks runtime suspend. Which mechanism breaks Teams was not isolated.

Scanout is not the same thing as rendering, which is why "does an NVIDIA connector report connected" is the wrong question to ask about a machine. Four machines in the tracker have a live NVIDIA output and still show the bug, because the compositor keeps rendering on the iGPU while the dGPU only scans out the ports wired to it, and the browser follows the compositor's render node. What decides it is the render node the compositor and the browser actually open.

The branch went live in 4.0.1 through commit `33d7363c`, which fixed `o.shell_succeeds()` always returning false inside Hyprland and so un-masked code that had been dead in 4.0.0. These machines were accidentally correct before that.

Two limits established in the threads. An `hl.env` placed before `require("default.hypr.omarchy")` loses, because the default loads after it, and the shipped `config/hypr/hyprland.lua` says plainly that the personal files load after the defaults. And `~/.config/hypr/envs.lua` is never loaded by anything, confirmed here: nothing in `/usr/share/omarchy` requires `hypr.envs`, the only match in the tree is `default.hypr.envs` at `default/hypr/omarchy.lua:16`, so an override written there does nothing. That is issue 9902.

Maxwell, Pascal and Volta take the other branch, device ids from `0x1340` to `0x1dff`, which sets `NVD_BACKEND=egl` and `__GLX_VENDOR_LIBRARY_NAME=nvidia` with no `LIBVA_DRIVER_NAME`. Anything older than Maxwell matches neither detector and gets no NVIDIA environment at all. One Quadro P520 reporter found the dGPU pinned awake with `nvidia_uvm used_by=0` and no process holding a CUDA context, so the mechanism above is not what holds it there, and that machine is not fixed by the override below. None of the open pull requests fixes it either, because all of them work on the GSP branch. The thread had no confirmed fix for it, only an untested suggestion of `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json`.

Three upstream pull requests propose different gates, 7851, 9483 and 10588, and none has merged as of 2026-09-11. Triage's recommendation on issue 10410 is 7851, which reads PCI vendors rather than connectors and so cannot flip when a monitor is docked, with one condition: a fix has to clear `LIBVA_DRIVER_NAME` rather than merely decline to set it, because `systemctl --user import-environment` only adds or overwrites names and anyone who has run 4.0.1 or 4.0.2 already has the stale value in their systemd user environment.

> **Audit corrected this record.** Confirmed on this machine, omarchy 4.0.2-1: /usr/share/omarchy/default/hypr/nvidia.lua sets all three variables behind omarchy-hw-nvidia plus omarchy-hw-nvidia-gsp with no display check, /usr/share/omarchy/default/hypr/envs.lua requires default.hypr.nvidia, /usr/share/omarchy/default/hypr/omarchy.lua:16 requires default.hypr.envs, and /usr/share/omarchy/default/hypr/autostart.lua:3-4 runs systemctl --user import-environment and dbus-update-activation-environment --systemd --all. The file is byte-identical to the v4.0.3 tag fetched with gh api, so claim 1 holds, and I also ran the three detectors here: nvidia and nvidia-gsp both succeed and the session really carries LIBVA_DRIVER_NAME=nvidia, NVD_BACKEND=direct and __GLX_VENDOR_LIBRARY_NAME=nvidia. Claim 2 holds: nothing under /usr/share/omarchy requires hypr.envs, the only match in the tree is default.hypr.envs, and the shipped config/hypr/hyprland.lua requires hypr.monitors, hypr.input, hypr.bindings, hypr.looknfeel and hypr.autostart and no envs file, so ~/.config/hypr/envs.lua is dead, which is upstream issue 9902. Claim 3 holds by load order in that same file, where require("default.hypr.omarchy") runs above the personal requires, so an hl.env placed before it loses. Claim 4, Q7, is honest: issue 8989 carries the Quadro P520 report with nvidia_uvm used_by=0 and no LIBVA_DRIVER_NAME on that branch, no confirmed fix, and only an untested __EGL_VENDOR_LIBRARY_FILENAMES hypothesis, but the record says "Pascal and older" where omarchy-hw-nvidia-without-gsp is bounded 0x1340 to 0x1dff, so Maxwell, Pascal and Volta take that branch and anything older than Maxwell matches neither branch and gets no NVIDIA environment at all. Two defects, both in the gate rather than the mechanism. First, the fix tells the reader to apply the override only when every NVIDIA connector is disconnected and disabled and the danger says the shipped setting is correct otherwise, and I read four machines in issue 8215 that falsify this: Hakira-Shymuy, RTX 4060 driving HDMI-A-1 with a monitor attached while Brave's GPU process stays on the AMD node, marioxabel, RTX 2060 driving DP-3 while Chromium stays on the Intel node, jhostileo, fixed with an hl.env override on an AMD panel plus NVIDIA HDMI plus dock, and a Lenovo i7-13800H with an RTX 4060 on DP-2 whose single-variable A/B gives a blank YouTube window under nvidia and clean playback under iHD. Scanout ownership is not render-device ownership, triage on issue 10410 settled the same point, so I rewrote the gate around which render node the compositor holds and rewrote the danger to match. Second, the fix says the __GLX_VENDOR_LIBRARY_NAME line was confirmed by an Arrow Lake plus RTX 5070 reporter, and that confirmation does not exist: that reporter set LIBVA_DRIVER_NAME only and pointed out that __GLX survives it, the issue 9890 reporter wrote that he had not tested __GLX, and the Arrow Lake plus RTX 5070 Ti reporter who did set both saw the eglCreateImage storm stop while the corruption persisted without a full logout. Everything else held from source: the CHECK_EQ modifier isolation in issue 9890, the decode-only entrypoint tables, the 99.9 Wh one-third idle draw measurement in issue 8989's body, the 4.0.1 attribution to 33d7363c which gh api shows inside the v4.0.0..v4.0.1 range, and pull requests 7851, 9483 and 10588 all open on quattro as of 2026-09-11. Not exercised: this is a desktop with one NVIDIA card driving card1-HDMI-A-1 and renderD128 on vendor 0x10de, so the hybrid path, the corruption, the crash and the power behaviour could not be reproduced here, and all of those rest on the reporters.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** On a machine where the NVIDIA card is the rendering device, a desktop or a muxed laptop in dGPU mode, `LIBVA_DRIVER_NAME=nvidia` matches the render device and this override will break hardware decode instead of fixing it. Check which render node the compositor and the browser hold first, as the fix shows. A connected NVIDIA output is not that test: on a hybrid laptop the dGPU can scan out an external monitor while the compositor and the browser still render on the iGPU, and the override applies there too.

**Fix.**

Omarchy 4 only, and only on a machine where the iGPU is the rendering device. Check that first, because where the NVIDIA card renders, a desktop or a muxed laptop in dGPU mode, the shipped setting matches the render device and this override is wrong.

Find which render node the compositor holds, and which PCI vendor owns it:

```sh
ls -l /proc/$(pgrep -x Hyprland | head -1)/fd | grep -oE 'renderD[0-9]+' | sort | uniq -c
for n in /sys/class/drm/renderD*; do
  printf '%s %s vendor=%s\n' "$(basename "$n")" "$(basename "$(readlink -f "$n/device")")" "$(cat "$n/device/vendor")"
done
```

Vendor `0x8086` is Intel, `0x1002` is AMD, `0x10de` is NVIDIA. If the node the compositor holds belongs to the Intel or AMD iGPU, the override applies. Check the browser the same way once it is running, because it picks its own node:

```sh
ls -l /proc/$(pgrep -f 'type=gpu-process' | head -n1)/fd | grep -oE 'renderD[0-9]+' | sort | uniq -c
```

Connector state is a useful cross-check and nothing more. A dGPU with a monitor plugged into one of its own ports can still be a machine whose compositor and browser render on the iGPU, and four machines in the upstream cluster are exactly that, so do not read a connected NVIDIA output as "the shipped setting is right here":

```sh
for c in /sys/class/drm/card*-*; do printf '%s status=%s enabled=%s\n' "$(basename "$c")" "$(cat "$c/status")" "$(cat "$c/enabled")"; done
```

Intel iGPU, install the media driver first:

```sh
omarchy update                      # fetch the sync databases first on a fresh install
sudo pacman -S intel-media-driver
```

Then override the variable from your own config, which loads after Omarchy's defaults, so the last `hl.env` assignment wins. Put it in `~/.config/hypr/hyprland.lua` **below** the `require("default.hypr.omarchy")` line:

```lua
-- ~/.config/hypr/hyprland.lua, below require("default.hypr.omarchy")
hl.env("LIBVA_DRIVER_NAME", "iHD")              -- Intel iGPU
hl.env("__GLX_VENDOR_LIBRARY_NAME", "mesa")
```

On an AMD iGPU use `radeonsi` in place of `iHD`. Mesa is already installed there. `~/.config/hypr/autostart.lua` works as well, because `hyprland.lua` requires it after the defaults, and one reporter fixed an AMD machine that way. Do not use `~/.config/hypr/envs.lua`, which nothing loads.

Both lines together are the workaround the issue 8989 reporter validated, and after a relogin he reported no corruption, the dGPU in D3cold even during playback, and about 5 W less idle draw. The `LIBVA_DRIVER_NAME` line is the one that carries the fix: two other reporters cleared their machines with it alone, one on an Arrow Lake plus RTX 5070 Max-Q laptop who then removed `--disable-gpu-compositing` and kept full GPU acceleration, and one who restored incoming Discord streams with `iHD`. A third set both lines on an Arrow Lake plus RTX 5070 Ti, saw the `eglCreateImage` errors stop, and still had corruption in the live session because he did not log out, so do not skip the relogin below.

Then log out and back in. `hyprctl reload` re-parses the config and processes Hyprland spawns afterwards do see the new value, but Omarchy's autostart runs `systemctl --user import-environment` at session start, so apps launched through systemd user scopes keep the old value until the next login. Fully quit any browser or Electron app that was running before the change, because each keeps its old environment until restarted.

Leave `NVD_BACKEND=direct` alone. The same branch still sets it and it is inert once the NVIDIA VA driver is no longer loaded.

Remove any `--disable-gpu-compositing` line from `~/.config/chromium-flags.conf` or `chrome-flags.conf` afterwards, because reporters found full GPU compositing works once the driver matches. `--disable-features=VaapiVideoDecoder` does not fix this, because the NVIDIA VA driver still loads.

Apps that should run on the dGPU keep working with PRIME offload scoped to their own launch:

```sh
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia <game>
```

**Verify.** After a fresh login:

```bash
systemctl --user show-environment | grep -E 'LIBVA|__GLX'   # iHD or radeonsi, and mesa
vainfo 2>/dev/null | head -3                                # the iGPU driver, not NVDEC
dgpu=$(grep -l 0x10de /sys/bus/pci/devices/*/vendor | head -1 | xargs dirname)
cat "$dgpu/power/runtime_status"                            # suspended, even during playback
cat "$dgpu/power/runtime_suspended_time"                    # grows over time
```

Then restart the browser and check what its GPU process actually maps:

```bash
GP=$(pgrep -f 'type=gpu-process' | head -n1)
grep -oE '/usr/lib/dri/[a-z0-9_]+_drv_video\.so' /proc/$GP/maps | sort -u
grep -oE 'lib(cuda|nvcuvid)\.so[.0-9]*' /proc/$GP/maps | sort -u
ls -l /proc/$GP/fd | grep -oE 'renderD[0-9]+|nvidia[a-z0-9-]*' | sort | uniq -c
```

On Intel, `iHD_drv_video.so` is mapped, the `libcuda` and `libnvcuvid` grep is empty, and the `/dev/nvidia0` and `/dev/nvidia-uvm` fds are gone. On AMD, `nvidia_drv_video.so` is absent, since the radeonsi driver resolves to `libgallium-*.so`, and the count of `/dev/nvidia0` fds is zero. Do not read `/proc/<pid>/environ` of the browser process, because Chromium rewrites that region for process titles and it reads back as garbage. The `chrome_crashpad_handler` child inherits the same environment and reads correctly. Chromium should also play video with no `eglCreateImage failed with 0x00003009` lines.

Sources: <https://github.com/omacom/omarchy/issues/8989> · <https://github.com/omacom/omarchy/issues/9890> · <https://github.com/omacom/omarchy/issues/10410> · <https://github.com/omacom/omarchy/pull/7851> · <https://github.com/omacom/omarchy/pull/9483> · <https://github.com/omacom/omarchy/pull/10588> · <https://github.com/omacom/omarchy/commit/33d7363c337134f11ec6ffcea132c92053bc8fe8> · <https://github.com/omacom/omarchy/issues/8215> · <https://github.com/omacom/omarchy/issues/9902> · <https://github.com/omacom/omarchy/blob/v4.0.3/default/hypr/nvidia.lua>

---

## DKMS module refuses to load under Secure Boot: 'Key was rejected by service'

`secure-boot-dkms-module-key-rejected` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `dkms`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy-4`, `secure-boot`

**Symptom.** You turned Secure Boot on (or enrolled keys with sbctl) and now the graphical session will not start. Loading the module by hand fails:

```
$ sudo modprobe nvidia
modprobe: ERROR: could not insert 'nvidia': Key was rejected by service
```

The journal shows one or both of:

```
Loading of unsigned module is rejected
nvidia: module verification failed: signature and/or required key missing - tainting kernel
```

Same thing happens with `nvidia-open-dkms`, `virtualbox-host-dkms`, `zfs-dkms`, `v4l2loopback-dkms`.

**Cause.** First, separate the two messages. `module verification failed: signature and/or required key missing - tainting kernel` on its own is **harmless and normal** on every Arch box that uses DKMS — the module still loads, the kernel just marks itself tainted. Only `Key was rejected by service` (or `Loading of unsigned module is rejected`) is an actual refusal.

A refusal means the kernel is *enforcing* module signatures. That is not the Arch default. The Arch Security wiki states that all officially supported kernels initialize the lockdown LSM but **none of them enforce any lockdown mode**, and notes that the `kernel_lockdown(7)` claim that lockdown is auto-enabled by Secure Boot is not true of upstream or of Arch's packaged kernels. So if you are seeing a rejection, enforcement was turned on by something: `module.sig_enforce=1` or `lockdown=integrity` in the kernel command line, `linux-hardened`, a shim-based boot chain, or a non-Arch kernel.

The second half of the problem is that the standard "enroll a MOK" answer does not apply to a typical Arch/Omarchy machine. MOK is a shim feature. Arch and Omarchy boot Limine/UKI via efistub with your own PK/KEK/db keys (sbctl), with no shim in the chain, so there is no MokList for `mokutil` to write into — enrolling through MokManager appears to succeed and `modprobe` still fails.

> ⚠️ **Risk.** Turning Secure Boot off in firmware invalidates TPM-sealed secrets. If this machine dual-boots Windows with BitLocker, or uses a TPM-sealed LUKS key (systemd-cryptenroll --tpm2-device with PCR 7), it will demand a recovery key or password on the next boot — have that recovery key in hand before you touch the firmware setting. Enrolling a MOK requires you to complete the MokManager prompt at the very next boot; if you miss it the request expires and the module stays unloadable. `dkms generate_mok` overwrites `/var/lib/dkms/mok.key`/`mok.pub` if either file is missing — regenerating invalidates any previously enrolled DKMS key, so every DKMS module must be rebuilt and the new key re-enrolled.

**Fix.**

**1. Find out whether enforcement is genuinely on.**

```bash
mokutil --sb-state                              # SecureBoot enabled/disabled
cat /sys/kernel/security/lockdown               # want: [none] integrity confidentiality
cat /sys/module/module/parameters/sig_enforce   # want: N
cat /proc/cmdline
uname -r; pacman -Q linux linux-hardened linux-lts 2>/dev/null
sudo dmesg | grep -iE 'lockdown|Key was rejected|module verification'
```

If `lockdown` reads `[none]` and `sig_enforce` is `N`, module signing is not your problem — look elsewhere (a failed DKMS build, or the boot loader/kernel itself not being signed).

**2a. You put the enforcement there yourself — take it back out.** On Omarchy 4 the command line lives in `limine-entry-tool` drop-ins, not in `/boot/limine.conf`:

```bash
grep -rn 'sig_enforce\|lockdown' /etc/limine-entry-tool.d/ /etc/default/limine /etc/kernel/cmdline 2>/dev/null
sudoedit /etc/limine-entry-tool.d/zz-local.conf   # delete the parameter
sudo limine-mkinitcpio && sudo limine-update
sudo reboot
```

On GRUB systems remove it from `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` and run `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

**2b. You genuinely have a shim in the chain (dual-boot with a shim-signed distro, or you installed `shim-signed`).** DKMS auto-generates a signing key on first build; enroll its certificate:

```bash
ls -l /var/lib/dkms/mok.pub || sudo dkms generate_mok
sudo mokutil --import /var/lib/dkms/mok.pub
# type a one-time password when prompted, then:
sudo reboot
# MokManager appears at boot -> Enroll MOK -> Continue -> View key -> Continue
# -> enter the one-time password -> reboot
sudo dkms autoinstall -k "$(uname -r)"
sudo modprobe nvidia
```

**2c. You run a custom kernel and want DKMS modules signed with its own build-time key.** Point DKMS at the kernel's certs (`sign_file` ships in the headers package):

```ini
# /etc/dkms/framework.conf
# $kernel_source_dir resolves to /usr/lib/modules/`uname -r`/build
mok_signing_key=$kernel_source_dir/certs/signing_key.pem
mok_certificate=$kernel_source_dir/certs/signing_key.x509
```

```bash
sudo dkms autoinstall -k "$(uname -r)"
```

This only works if your kernel package actually installs `certs/signing_key.pem` into the headers — Arch's stock `linux` does not, which is why 2c is a custom-kernel path only.

**3. Emergency escape while you sort it out:** boot once with Secure Boot disabled in firmware, or add `module.sig_enforce=0` at the Limine menu (the editor is unconditionally disabled when Secure Boot is active, so this needs Secure Boot off first).

**Verify.** `sudo modprobe nvidia && nvidia-smi` succeeds; `sudo dmesg | grep -i 'Key was rejected'` is empty; `cat /sys/kernel/security/lockdown` shows `[none]` (or the module loads despite lockdown, meaning the signature is now trusted).

Sources: <https://wiki.archlinux.org/title/Security> · <https://wiki.archlinux.org/title/Signed_kernel_modules> · <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://man.archlinux.org/man/dkms.8> · <https://wiki.archlinux.org/title/Unified_Extensible_Firmware_Interface/Secure_Boot> · <https://bbs.archlinux.org/viewtopic.php?id=283289> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md>

---

## Fix flickering/out-of-order frames in XWayland games on NVIDIA

`xwayland-game-flicker-explicit-sync` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Steam/Proton and other XWayland games flicker violently, show frames out of order, or are effectively unplayable on NVIDIA under Hyprland, while the rest of the desktop is fine.

**Cause.** The NVIDIA driver has no implicit synchronisation. Explicit sync (`linux-drm-syncobj-v1`) is only negotiated when XWayland, wayland-protocols and the NVIDIA driver are all new enough; older combinations present buffers before rendering has finished.

> **Audit corrected this record.** Checked the Hyprland wiki Nvidia page (content/nvidia/_index.md), which still has the Flickering in Xwayland games section with the same floors: xorg-xwayland 24.1, wayland-protocols 1.34, NVIDIA 555, and a 535xx fallback for GPUs the 555 driver dropped. Symptom, cause and the three version floors are confirmed, and the Arch wiki NVIDIA page carries the same note about pre-555 drivers and linux-drm-syncobj-v1. Four things were wrong. The Kepler claim is wrong: the Arch wiki NVIDIA driver table puts Kepler on nvidia-470xx-dkms and Maxwell, Pascal and Volta on nvidia-580xx-dkms, so no GPU family needs 535xx today and the 580 branch already exceeds the 555 floor, while Kepler cannot run any explicit-sync driver at all. `hl.set` does not exist: the wiki config-options page documents `hl.config({ ... })` and every Omarchy file under /usr/share/omarchy uses that form, so the Lua block was replaced with `hl.config({ render = { direct_scanout = 0 } })` and the 0/1/2 values were added from the same page, which also shows the default is 0. `sudo pacman -Syu <pkgs>` is blocked by Omarchy's ALPM guard, so the fix now uses `omarchy update`. The danger overstated the lib32 mixing risk: AUR metadata shows lib32-nvidia-535xx-utils and lib32-nvidia-580xx-utils depend on an exactly matching nvidia-utils version and conflict with the repo lib32-nvidia-utils, so pacman refuses the mismatch rather than letting 32-bit games fail. `hyprctl systeminfo` reporting the driver version was confirmed on this machine, which prints an NVRM version line for 610.57.04. Current repo versions (xorg-xwayland 24.1.13, wayland-protocols 1.49, nvidia-utils 610.57.04) and the AUR packages 535xx 535.309.01, 580xx 580.178.04 and 470xx 470.256.02 were read from archlinux.org and the AUR RPC on 2026-09-06. The cited raw Variables.md URL now returns 404 and was replaced with the current config-options page.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The legacy branches are AUR packages that pin you to a driver NVIDIA has stopped updating, and the whole set must move together. `lib32-nvidia-580xx-utils` and `lib32-nvidia-535xx-utils` each depend on an exactly matching `nvidia-utils` version and conflict with the repo `lib32-nvidia-utils`, so pacman refuses a mismatched pair rather than installing it. Remove the repo `nvidia-utils`, `lib32-nvidia-utils` and your `nvidia-open-dkms` or `nvidia-dkms` before installing the branch, and install the branch's dkms, utils and lib32 packages in one transaction. Installing a branch that does not support your GPU (for example 580xx on Kepler) leaves you with no display after reboot, so confirm the GPU family on the Arch wiki NVIDIA table first.

**Fix.**

Bring the whole stack up to the versions that negotiate explicit sync. On Omarchy, direct `pacman -Syu` is blocked by the ALPM guard, so update through the supported command:

```bash
omarchy update
pacman -Q xorg-xwayland wayland-protocols nvidia-utils
```

On plain Arch the equivalent is `sudo pacman -Syu`. The floors, from the Hyprland Nvidia page, are:

- `xorg-xwayland` >= 24.1
- `wayland-protocols` >= 1.34
- NVIDIA driver >= 555

The Arch repos are well past all three (xorg-xwayland 24.1.13, wayland-protocols 1.49, nvidia-utils 610.57.04 as of 2026-09-06), so a fully updated install already meets them. If `pacman -Q` shows older versions, the update did not complete.

If the current `nvidia-utils` no longer supports your GPU, pick the legacy branch by GPU family rather than reaching for 535xx:

- Maxwell, Pascal and Volta (GTX 900, GTX 10 series, Titan V) are dropped from the current driver but supported by the 580 branch, which is newer than 555 and negotiates explicit sync. Install `nvidia-580xx-dkms`, `nvidia-580xx-utils` and, for Steam and 32-bit games, `lib32-nvidia-580xx-utils` from the AUR in place of the repo packages.
- Kepler (GTX 600 and 700 series) and older ended with the 470 branch. No driver those cards can run has explicit sync, and the 535xx AUR packages do not support them either. The Hyprland wiki points older cards at Nouveau.

Check which branch you are on:

```bash
hyprctl systeminfo | grep 'NVRM version'
```

If a specific fullscreen game still glitches after the stack is current, make sure direct scanout is off. It defaults to `0` in Hyprland and Omarchy does not change it, so this only matters if you enabled it. In `~/.config/hypr/hyprland.lua` (Hyprland 0.55+):

```lua
hl.config({ render = { direct_scanout = 0 } })
```

Valid values are `0` (off), `1` (on) and `2` (auto, on for windows with content type game). On Hyprland 0.54 and earlier the hyprlang form is:

```
render {
    direct_scanout = 0
}
```

**Verify.** `pacman -Q xorg-xwayland wayland-protocols nvidia-utils` meets the version floors above, and the game renders cleanly. `hyprctl systeminfo` reports the NVIDIA driver version in use.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.archlinux.org/title/NVIDIA> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/nvidia/_index.md> · <https://wiki.hypr.land/configuring/core/config-options/> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/configuring/core/config-options.md> · <https://archlinux.org/packages/extra/x86_64/xorg-xwayland/> · <https://archlinux.org/packages/extra/any/wayland-protocols/> · <https://archlinux.org/packages/extra/x86_64/nvidia-utils/> · <https://archlinux.org/packages/multilib/x86_64/lib32-nvidia-utils/> · <https://aur.archlinux.org/packages/lib32-nvidia-535xx-utils> · <https://aur.archlinux.org/packages/nvidia-580xx-dkms> · <https://aur.archlinux.org/packages/nvidia-470xx-dkms>

---

## Fix a frozen AMD display with 'flip_done timed out' in the log

`amdgpu-flip-done-timed-out` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** The screen stops updating entirely — the image is frozen but audio keeps playing and SSH still works. `journalctl -k` shows:

```
[drm:drm_atomic_helper_wait_for_flip_done] *ERROR* [CRTC:...] flip_done timed out
```

**Cause.** A bug in the amdgpu display code around Panel Self Refresh stops the atomic page flip from ever completing, so the compositor waits forever for a flip that never lands and the image freezes while the rest of the machine keeps running.

`amdgpu.dcdebugmask` is a bitmask over `enum DC_DEBUG_MASK` in the kernel. `DC_DISABLE_PSR` is `0x10` and turns off Panel Self Refresh v1 and PSR Selectively Updated. `DC_DISABLE_STUTTER` is `0x2` and turns off memory stutter mode, so `0x12` is both.

The upstream report the Arch wiki points at is https://gitlab.freedesktop.org/drm/amd/-/issues/4141, filed against a Ryzen 7840U with a Radeon 780M iGPU and labelled `PSR` and `Phoenix / Hawk Point`, so recent AMD APU laptops are where this is reported most. That report was closed on 2026-08-12 and its comments need a login to read, so whether a kernel fix has landed is not established here. The Arch wiki still recommended the workaround when this record was re-audited on 2026-09-11, so check your kernel version against the report before assuming you still need it.

> **Audit corrected this record.** The single cited source resolves and does support the technical claim. I fetched https://wiki.archlinux.org/title/AMDGPU as raw wikitext and its section "Frozen or unresponsive display (flip_done timed out)" recommends exactly `amdgpu.dcdebugmask=0x10` (Panel self refresh v1 and PSR-SU) or `amdgpu.dcdebugmask=0x12` (Panel self refresh and memory stutter mode), so the record's wording is close to verbatim and the source stays. I checked the bit values against the kernel rather than trusting the wiki: `enum DC_DEBUG_MASK` in drivers/gpu/drm/amd/include/amd_shared.h gives `DC_DISABLE_PSR = 0x10` and `DC_DISABLE_STUTTER = 0x2`, so 0x12 is both, confirmed. In drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c the parameter is `module_param_named(dcdebugmask, amdgpu_dc_debug_mask, uint, 0444)`, which is read-only at runtime and confirms a reboot is genuinely required, and gives a better verify path than /proc/cmdline alone. What was wrong is the apply step. The record told an Omarchy reader to put the parameter in `cmdline:` in /boot/limine.conf, or in /etc/default/grub. Neither works on Omarchy 4, and the record carries `omarchy` in applies_to. On this workstation (omarchy 4.0.2-1, hyprland 0.56.2, kernel 7.1.9) there is no /etc/default/grub, the boot is a UKI, and the real drop-ins are /etc/limine-entry-tool.d/, which I read directly: omarchy-defaults.conf contains `KERNEL_CMDLINE[default]+=` lines for quiet splash and for initramfs_async=0, and omarchy-uki.conf sets ENABLE_UKI=yes. The packaged template /etc/limine-entry-tool.conf from limine-mkinitcpio-hook 1.37.1-1 states the operator rules, that `+=` appends in /etc/limine-entry-tool.d/*.conf and a bare `=` replaces. So the fix, verify and danger are replaced to match the existing record `limine-kernel-parameters-not-applying-omarchy` rather than contradict it, keeping the systemd-boot and GRUB branches labelled for other distributions. The cause is also replaced, because the upstream report the wiki cites, https://gitlab.freedesktop.org/drm/amd/-/issues/4141, is worth scoping honestly: it was filed against a Ryzen 7840U with a Radeon 780M, is labelled `PSR` and `Phoenix / Hawk Point`, and was closed on 2026-08-12. Its comments need a login, so I could not read the closing note and cannot say whether a kernel fix landed. The wiki still recommends the workaround today. NOT EXERCISED: this workstation has an NVIDIA RTX 3090 and `lsmod` shows amdgpu is not loaded, so nothing about amdgpu behaviour was tested here. The Omarchy 4 boot mechanism was confirmed on this machine, the amdgpu facts come from the kernel source and the wiki only. Severity `high` and frequency `occasional` are left alone: a frozen display is serious, and the upstream report is confined to one APU family.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Disabling Panel Self Refresh costs battery life on a laptop, and `0x12` also disables memory stutter mode, which costs more. On Omarchy 4 the drop-in itself is the larger risk. Writing `KERNEL_CMDLINE[default]=` instead of `+=`, or naming your file so it sorts before `omarchy-defaults.conf`, silently drops Omarchy's `initramfs_async=0`, and the packaged comment in that file says that is what keeps Plymouth alive at the LUKS prompt, so an encrypted machine falls back to an unthemed text prompt or hangs. `limine-mkinitcpio` rewrites the UKI on the ESP, so run `df -h /boot` first, because a full ESP produces a truncated image that will not boot. A bad kernel parameter is a failure to boot. Recovery is the Limine boot menu editor or a Limine snapshot entry, and both are bypassed if you have enabled Omarchy's Direct Boot, in which case pick Limine from the firmware boot menu (usually F12, F8 or Esc). On a GRUB system the equivalent recovery is GRUB's own `e` editor at the menu.

**Fix.**

`dcdebugmask` is a `0444` module parameter, readable but not writable at runtime, so it can only be set at boot. Start with:

```
amdgpu.dcdebugmask=0x10
```

which disables Panel Self Refresh v1 and PSR Selectively Updated. If that is not enough, change the same value to:

```
amdgpu.dcdebugmask=0x12
```

which disables Panel Self Refresh and memory stutter mode. Edit the value in place rather than adding a second parameter.

**Omarchy 4** has no `/etc/default/grub`, and `/boot/limine.conf` is regenerated on every kernel or limine transaction, so an edit there is discarded. Omarchy boots a Unified Kernel Image, which bakes the command line into the `.efi` image. Kernel parameters go in your own drop-in under `/etc/limine-entry-tool.d/` whose filename sorts after Omarchy's `omarchy-defaults.conf`, and always with `+=`:

```bash
sudo tee -a /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
# `+=` appends. A bare `=` would wipe Omarchy's own defaults.
KERNEL_CMDLINE[default]+=" amdgpu.dcdebugmask=0x10"
EOF
sudo limine-mkinitcpio && sudo limine-update && sudo reboot
```

Use `tee -a` rather than `tee`. A bare `tee` truncates the file and would drop any parameter you added earlier from another record. The full mechanism, including how to test a parameter from the Limine boot menu editor without writing anything to disk, is in the record `limine-kernel-parameters-not-applying-omarchy`.

**Other bootloaders:**

- systemd-boot: append to `options` in `/boot/loader/entries/*.conf`
- GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

Reboot in every case.

**Verify.** ```bash
cat /sys/module/amdgpu/parameters/dcdebugmask   # 16 for 0x10, 18 for 0x12
cat /proc/cmdline
```

`/proc/cmdline` contains `amdgpu.dcdebugmask=0x10`. On Omarchy 4 it must also still contain Omarchy's own defaults (`quiet splash loglevel=0 systemd.show_status=false rd.udev.log_level=0 vt.global_cursor_default=0` and `initramfs_async=0`). If those have gone, your drop-in used `=` where it needed `+=`. Then `journalctl -k -g flip_done` stays empty after a full day of use and the display no longer freezes.

Sources: <https://wiki.archlinux.org/title/AMDGPU> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/include/amd_shared.h> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c> · <https://gitlab.freedesktop.org/drm/amd/-/issues/4141>

---

## Brand-new Intel GPU does not probe: 'not properly supported by i915 in this kernel version'

`intel-gpu-force-probe-required` · severity: **high** · frequency: **occasional** · applies to: `arc`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `lunar-lake`, `manjaro`, `meteor-lake`, `omarchy-4`

**Symptom.** On a just-released laptop (Meteor Lake, Lunar Lake, Arrow Lake, Panther Lake, Arc) there is no hardware acceleration at all: everything renders on `llvmpipe`, video playback pegs the CPU, and Hyprland may refuse to start with `drm: Found no gpus to use, cannot continue`. `dmesg` says exactly:

```
i915 0000:00:02.0: Your graphics device 7d55 is not properly supported by i915 in this
kernel version. To force driver probe anyway, use i915.force_probe=7d55
module parameter or CONFIG_DRM_I915_FORCE_PROBE=7d55 configuration option,
or (recommended) check for kernel updates.
```

or, for the newer driver:

```
xe 0000:00:02.0: Your graphics device 9a49 is not officially supported
by xe driver in this kernel version. To force Xe probe,
use xe.force_probe='9a49' and i915.force_probe='!9a49'
module parameters or CONFIG_DRM_XE_FORCE_PROBE='9a49' and
CONFIG_DRM_I915_FORCE_PROBE='!9a49' configuration options.
```

`lspci -k` shows the VGA controller with no `Kernel driver in use:` line at all.

**Cause.** Intel gates support for hardware it considers not yet validated behind a `require_force_probe` flag in the driver's device table. Until Intel clears it, the driver refuses `-ENODEV` on probe and prints the message above, and you fall back to `simpledrm`/`efifb` plus software rendering.

The second half of the problem is the i915-vs-xe split. Both drivers exist in the same kernel and both claim overlapping PCI IDs. `i915` covers everything up to and including Alchemist/Meteor Lake; `xe` is the newer driver and is the only option for Lunar Lake, Battlemage and later. For first-generation Xe hardware (Tiger Lake, Rocket Lake, Alder Lake, Arc A-series) both drivers can bind, and the Arch wiki flags `xe` as *experimental* on those parts. Two drivers cannot own the same device, so switching to `xe` always requires excluding the ID from `i915` at the same time.

> ⚠️ **Risk.** Force-probing calls `add_taint(TAINT_USER)` — the kernel is marked tainted, and Intel will not accept bug reports from that state. Unvalidated hardware can hang, corrupt the display, or fail to resume from suspend; keep a snapshot or a second boot entry. Switching Tiger Lake / Rocket Lake / Alder Lake / Arc A-series to `xe` is explicitly experimental per the Arch wiki, with no stability or feature-parity guarantee — have a way to revert (edit the entry at the Limine menu, or boot a snapshot) before you reboot. Getting the `!` wrong on the i915 exclusion leaves both drivers fighting for the device and you get no display at all.

**Fix.**

**1. Get your PCI device ID.** It is the four hex digits after `8086:`.

```bash
lspci -nnd ::03xx
# 00:02.0 VGA compatible controller [0300]: Intel Corporation ... [8086:7d55] (rev 08)

dmesg | grep -iE 'i915|xe ' | head -20
lspci -k -d ::03xx        # confirm no "Kernel driver in use"
```

**2. Prefer the real fix: a newer kernel.** The driver message says so itself. Before forcing anything, update and try the newest kernel available; on Arch-based systems that means `linux` at minimum, and `linux-firmware` for the GuC/HuC blobs the newer parts require.

```bash
omarchy update                                  # Omarchy 4
sudo pacman -Syu linux linux-headers linux-firmware linux-firmware-intel mesa vulkan-intel
```

If `linux` is still too old, `linux-mainline` (AUR) or CachyOS's kernels usually have it.

**3. Force the probe if you cannot wait.** Substitute your own ID for `7d55`/`9a49`.

Stay on `i915`:

```bash
sudo tee /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" i915.force_probe=7d55"
EOF
sudo limine-mkinitcpio && sudo limine-update && sudo reboot
```

Switch to `xe` (must exclude the ID from `i915` in the same breath):

```bash
sudo tee /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" i915.force_probe=!9a49 xe.force_probe=9a49"
EOF
sudo limine-mkinitcpio && sudo limine-update && sudo reboot
```

The modprobe.d equivalent (works only if the module is loaded from the initramfs *after* your config is included — the cmdline is more reliable for early KMS):

```conf
# /etc/modprobe.d/intel_xe.conf
options i915 force_probe=!9a49
options xe   force_probe=9a49
```

On GRUB systems, put the same string in `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` and run `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

**4. Make sure the Mesa/Vulkan userspace is present too**, otherwise you get KMS but still no acceleration:

```bash
sudo pacman -S mesa vulkan-intel intel-media-driver
```

**Verify.** `lspci -k -d ::03xx` now shows `Kernel driver in use: i915` (or `xe`); `glxinfo -B | grep -i 'OpenGL renderer'` names your Intel GPU instead of `llvmpipe`; `vulkaninfo --summary` lists an Intel device; `dmesg | grep -i force` shows `Force probing unsupported Device ID 7d55, tainting kernel`, confirming the parameter took effect.

Sources: <https://wiki.archlinux.org/title/Intel_graphics> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/i915_pci.c> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/xe/xe_pci.c> · <https://wiki.archlinux.org/title/Limine>

---

## Stop NVIDIA freezing when the display blanks (GSP Timeout / Xid 119)

`nvidia-dpms-gsp-timeout-freeze` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** The machine hard-freezes seconds after the screen blanks on idle, or right after resuming — mouse dead, no TTY switch, only a power-button reset works. `journalctl -b -1 -k` shows:

```
NVRM: _kgspLogXid119: ***** GSP Timeout *****
NVRM: Xid (PCI:0000:01:00): 119, Timeout after 6s of waiting for RPC response from GPU0 GSP! Expected function 76 (GSP_RM_CONTROL) sequence 1321
```

**Cause.** During DPMS off and suspend or resume transitions the GPU can drop into a very low clock state that the GSP firmware does not recover from. The RPC to the GSP microcontroller then times out, the driver wedges, and the whole machine goes with it. Only GPUs that carry GSP firmware are exposed, which means Turing and newer, and on Omarchy 4 that is the set of cards the installer gives `nvidia-open-dkms` to. Pre-Turing cards get `nvidia-580xx-dkms` and cannot hit this.

> **Audit corrected this record.** Checked on this workstation, which is Omarchy 4.0.2-1, Hyprland 0.56.2, kernel 7.1.9, `nvidia-open-dkms` 610.57.04-1 on an RTX 3090, and against the cited pages. The core of the record holds. The Arch wiki's NVIDIA/Troubleshooting section "System freeze when the display powers off or on resume" carries the same `Xid 119` GSP timeout log, the same low-clock explanation, the same `nvidia-persistenced` prerequisite, the same `nvidia-smi -lgc` and `-lmc` test values and byte-for-byte the same `nvidia-clocks.service` unit, so the fix body is a faithful copy of a live source. Confirmed on this machine that `nvidia-smi` 610.57.04 still offers `-lgc`, `-lmc`, `-rgc` and `-rmc`, so the commands have not aged out. Three things are wrong. First and worst, the stopgap: "removing or raising the DPMS timeout in your hypridle config (`~/.config/hypr/hypridle.conf`)" cannot be done on Omarchy 4. Confirmed on this machine that `pacman -Q hypridle hyprlock` reports neither package installed, that `~/.config/hypr/` contains no `hypridle.conf`, and that grepping `/usr/share/omarchy/shell/`, `/usr/share/omarchy/bin/` and `/usr/share/omarchy/default/` for `dpms` returns only `key_press_enables_dpms` and `mouse_move_enables_dpms` in `default/hypr/input.lua`, which are about waking from DPMS rather than entering it. Reading `/usr/share/omarchy/shell/plugins/services/idle/Service.qml` confirms the Omarchy 4 idle cycle is a screensaver window followed by the lock, with no blanking step, driven by `idle.screensaver` and `idle.lock` in `~/.config/omarchy/shell.json` (150 and 300 seconds on this box) and disabled by the `stay-awake` marker that `omarchy-toggle-idle` writes. The old advice is kept as the plain-Arch branch. Second, the verify field reads `journalctl -b -1 -k`, the previous boot. If the fix works there is no reboot, so that command inspects the wrong boot and would show the old crash forever. Corrected to `-b` with a note on when `-b -1` is right. Third, the record does not scope itself to hardware that has GSP firmware at all. Omarchy ships `omarchy-hw-nvidia-gsp`, read here, which splits at PCI device id `0x1e00`, and `install/hardware/nvidia.sh`, retrieved from `quattro` today, installs `nvidia-open-dkms` above that line and `nvidia-580xx-dkms` below it. Two additions. The `danger` field was thin: it covers power and heat but not the trap a reader will walk into next, which is the Arch wiki's own GSP-firmware section recommending `NVreg_EnableGpuFirmware=0` while stating that it only works with the proprietary driver. Omarchy's GSP path is the open driver, so that is not available, and with Omarchy's early KMS a driver that will not initialise costs the display. And omacom/omarchy issue 11249, filed on Omarchy 4.0.3 with `nvidia-open-dkms` 610.57.04, reports an `aquamarine` 0.15.0 regression where an external monitor powered off never recovers, on `nvidia-drm` among others, with an `NVRM GSP task watchdog timeout` noted in one of three attempts. That is a different root cause with an almost identical presentation and it is live on current Omarchy, so the fix now opens by separating the two. On sources: both cited GitHub issues fail to support this record and go in `sources_remove`. Read in full, issue 2112 is an Omarchy 3 display-wake bug whose only suggested workaround is editing `hypridle.conf`, and issue 2635 is the same family across Omarchy 3.0 to 3.8, reported on AMD, Intel Iris and NVIDIA alike, whose stated workaround is `systemctl restart sddm`. Neither contains the string GSP, `Xid`, or any clock parameter, so neither supports the claim it was cited for. Frequency is dropped from `common` to `occasional`: searching the omacom/omarchy tracker for "GSP Timeout" and for `Xid 119` returns nothing on point across 63 and 5 hits respectively, and Omarchy 4's own idle path never issues the DPMS off that the record names as the primary trigger, so the exposure on this distribution is narrower than `common` implies. Severity stays `high`, since the outcome is a power-button reset. NOT exercised: nothing here was reproduced. Suspend cannot be run on this workstation for this audit, and no `hyprctl` command that changes DPMS state was issued, because this machine's lock screen cannot be released headlessly. The clock-pinning fix is therefore carried on the Arch wiki's authority plus a check that the `nvidia-smi` flags still exist, not on a freeze I induced and cleared.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Locking clocks raises idle power draw and temperature. On a laptop that measurably shortens battery life, so do not set the minimum near the card's maximum on a thermally constrained machine. Separately, do not reach for the other workaround you will find for GSP problems. The Arch wiki states that `NVreg_EnableGpuFirmware=0` only works with the proprietary NVIDIA driver, and Omarchy installs the open modules (`nvidia-open-dkms`) on every GSP-capable card, so on Omarchy 4 that parameter is not an available workaround. Omarchy also early-loads the NVIDIA modules from the initramfs, so a driver that fails to initialise leaves you with no display at all and a rebuild through `sudo limine-mkinitcpio` from a rescue shell. Check `pacman -Q nvidia-open-dkms` before writing anything into `/etc/modprobe.d`.

**Fix.**

Rule out the Omarchy 4 look-alike first, because it is far more common right now and locking clocks will not touch it. Since `aquamarine` 0.15.0 landed with Omarchy 4.0.3 on 2026-09-09, an external display that is powered off, unplugged or allowed to sleep can come back as "No Signal" and never recover, on `nvidia-drm` as well as i915, xe and amdgpu. From the chair that looks like this freeze. The machine is not wedged:

```bash
pacman -Q aquamarine
hyprctl monitors | grep -E 'Monitor|dpmsStatus'
journalctl -b -k | grep -iE 'GSP Timeout|Xid \(PCI'
```

If you can still ssh in and `hyprctl monitors` answers, it is the aquamarine regression and not this record. See `https://github.com/omacom/omarchy/issues/11249`.

A real `Xid 119` GSP timeout needs a GPU that has GSP firmware, which means Turing or newer. Omarchy installs `nvidia-open-dkms` on exactly those cards and `nvidia-580xx-dkms` on Maxwell, Pascal and Volta, and ships a detector for the split:

```bash
omarchy-hw-nvidia-gsp && echo "GSP capable" || echo "no GSP firmware, this record does not apply"
```

Then pin a higher minimum GPU and memory clock so the GPU never reaches the unstable state.

```bash
sudo systemctl enable --now nvidia-persistenced.service

# find valid clock values for your card
nvidia-smi -q -d SUPPORTED_CLOCKS
nvidia-smi -q -d CLOCK

# temporary test, adjust the upper bounds to your GPU's real max
sudo nvidia-smi -lgc 800,2100
sudo nvidia-smi -lmc 800,10000

# revert with
sudo nvidia-smi -rgc
sudo nvidia-smi -rmc
```

If that stops the freezes, make it permanent:

```bash
sudo tee /etc/systemd/system/nvidia-clocks.service >/dev/null <<'EOF'
[Unit]
Description=Set NVIDIA GPU minimum clocks to avoid GSP timeouts
Requires=nvidia-persistenced.service
After=nvidia-persistenced.service

[Service]
Type=oneshot
ExecStart=/usr/bin/nvidia-smi -lgc 500,2100
ExecStart=/usr/bin/nvidia-smi -lmc 500,10000
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now nvidia-clocks.service
```

Lower the 500 floor to reduce idle power draw. Too low and the freeze comes back.

**The idle stopgap, on Omarchy 4.** There is no `hypridle` and no `~/.config/hypr/hypridle.conf`. Neither `hypridle` nor `hyprlock` is installed, and the Omarchy shell never issues a DPMS off: on idle it launches a screensaver and then locks. The two knobs are `idle.screensaver` and `idle.lock` in `~/.config/omarchy/shell.json`, both counted in seconds from when idle began:

```json
{
  "idle": {
    "screensaver": 150,
    "lock": 300
  }
}
```

To stop the machine idling at all for this session:

```bash
omarchy-toggle-idle stay-awake
```

If the panel still powers off after that, it is the monitor's own standby timer or a system suspend, not a Hyprland setting.

**On plain Arch with hypridle installed**, raising or removing the `dpms off` timeout in `~/.config/hypr/hypridle.conf` is still the stopgap.

**Verify.** Confirm the unit came up and the floor is applied:

```bash
systemctl is-active nvidia-clocks.service
nvidia-smi -q -d CLOCK
```

Then leave the machine idle past `idle.screensaver` in `~/.config/omarchy/shell.json`, come back and wake it. The desktop returns, and the log of the boot you are still in is clean:

```bash
journalctl -b -k | grep -iE 'GSP Timeout|Xid \(PCI'
```

Use `journalctl -b -1 -k` instead only when you are reading back a boot that actually froze and had to be power-cycled.

Sources: <https://wiki.archlinux.org/title/NVIDIA/Troubleshooting> · <https://github.com/omacom/omarchy/issues/11249> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/nvidia.sh>

---

## Disable GSP firmware when NVIDIA crashes or Vulkan fails

`nvidia-gsp-firmware-crashes` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Random full-system crashes, Vulkan applications refusing to start, or on some Ampere laptops the driver failing outright (no display, `nvidia-smi` errors) — all starting with driver 555 or later. Games and `vkcube` die with Vulkan initialisation errors.

**Cause.** The GSP (GPU System Processor) firmware, enabled by default since driver 555, is known to cause a range of failures including Vulkan breakage, broken PCIe D3 power management on pre-Ampere cards, and complete driver failure on some Ampere-equipped laptops.

> **Audit corrected this record.** The problem and the core parameter are right (Arch NVIDIA/Troubleshooting#GSP firmware: enabled by default since 555, causes Vulkan failures and crashes; NVreg_EnableGpuFirmware=0 'only works with the proprietary NVIDIA driver'; the NVIDIA page's footnote 2 recommends exactly nvidia-580xx-dkms + that parameter for the Ampere-laptop failures). The fix is dangerous as written for one group: on Blackwell (RTX 50xx) and newer the open kernel modules are REQUIRED (Hyprland wiki states this in bold), and nvidia-580xx does not support Blackwell at all — a 50-series owner who runs `pacman -Rdd nvidia-open` and installs 580xx ends up with no working driver and no desktop. It also skips linux-headers ordering and the nvidia-utils conflict.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Swapping between the open and proprietary kernel modules with `pacman -Rdd` bypasses dependency checking and leaves you temporarily without a working driver — do the removal and the install in one session, from a TTY, and do not reboot in between. Blackwell (RTX 50xx) and newer REQUIRE the open modules; do not do this on those cards.

**Fix.**

First identify the GPU — the proprietary 580xx branch covers Maxwell through Ada only:

```bash
lspci -d ::03xx
```

- Blackwell (RTX 50xx) and newer: the open kernel modules are mandatory. GSP **cannot** be disabled. Do not remove `nvidia-open*`; look for another workaround (driver version change, `nvidia-open-beta`).
- Turing / Ampere / Ada (and Maxwell/Pascal/Volta, which are already on 580xx): you can switch to the proprietary branch.

```bash
sudo pacman -S --needed linux-headers      # plus linux-lts-headers / linux-zen-headers as applicable
yay -S nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils
# accept pacman's prompt to replace the conflicting nvidia-open*/nvidia-utils packages;
# you do not need a separate `pacman -Rdd` step
```

Then disable GSP:

```bash
sudo tee /etc/modprobe.d/nvidia-gsp.conf >/dev/null <<'EOF'
options nvidia NVreg_EnableGpuFirmware=0
EOF

sudo mkinitcpio -P     # only needed if the nvidia modules are in your initramfs
reboot
```

Verify afterwards with `cat /proc/driver/nvidia/params | grep EnableGpuFirmware` (want `0`).

**Verify.** `sudo sort /proc/driver/nvidia/params | grep EnableGpuFirmware` shows `0`; `nvidia-smi -q | grep -i 'GSP Firmware'` reports no GSP version in use; `vkcube` runs and the crashes stop.

Sources: <https://wiki.archlinux.org/title/NVIDIA/Troubleshooting> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/PRIME>

---

## Fix NVIDIA driver crash when switching to a TTY with VRR/G-Sync on

`nvidia-vrr-tty-switch-flip-timeout` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Pressing Ctrl+Alt+F2 (or leaving a G-Sync monitor idle) kills the session or hangs the display. The journal shows:

```
[drm:nv_drm_atomic_commit [nvidia_drm]] *ERROR* [nvidia-drm] [GPU ID ...] Flip event timeout
nvidia-modeset: ERROR: GPU:0: Idling display engine timed out: ...
```

**Cause.** The NVIDIA display engine mishandles the mode transition while variable refresh rate (G-Sync / FreeSync) is active, so the atomic commit never completes and the flip times out.

**Fix.**

Easiest test: turn VRR off in the monitor's own OSD menu, and off in Hyprland.

In `~/.config/hypr/hyprland.conf` (Hyprland ≤ 0.54):

```
misc {
    vrr = 0
}
```

Hyprland 0.55+ / Omarchy 4 Lua config:

```lua
hl.set("misc:vrr", 0)
```

To keep VRR usable for games only, use `vrr = 2` (fullscreen only) instead of `0`.

System-wide alternative — hide the driver's VRR capability entirely so nothing can enable it. Add this kernel parameter:

```
nvidia_modeset.conceal_vrr_caps=1
```

- systemd-boot: append to `options` in `/boot/loader/entries/*.conf`
- Limine: append to `cmdline:` in `/boot/limine.conf`
- GRUB: add to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

Reboot.

**Verify.** `hyprctl getoption misc:vrr` reports `0`; Ctrl+Alt+F2 and back no longer hangs, and `journalctl -k | grep 'Flip event timeout'` stays empty.

Sources: <https://wiki.archlinux.org/title/NVIDIA/Troubleshooting> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md>

---

## Finish an Omarchy install that fails with 'target not found: nvidia-580xx-dkms'

`omarchy-nvidia-580xx-target-not-found` · severity: **high** · frequency: **occasional** · applies to: `arch`, `laptop`, `nvidia`, `omarchy`

**Symptom.** During an Omarchy 4 install, or when re-running `omarchy apply hardware`, on a machine with an MX150, GTX 1050 or similar Maxwell, Pascal or Volta GPU, the hardware stage aborts with:

```
error: target not found: nvidia-580xx-dkms
error: target not found: lib32-nvidia-580xx-utils
[Failed]: /usr/share/omarchy/install/hardware/nvidia.sh (exit code: 1)
```

The whole install stops there rather than skipping the driver and carrying on.

**Cause.** Omarchy 4's `/usr/share/omarchy/install/hardware/nvidia.sh` runs `omarchy-hw-nvidia-without-gsp`, which matches any NVIDIA display device whose PCI ID is at least `0x1340` and below `0x1e00`, the Maxwell, Pascal and Volta span. On a match it asks `omarchy-pkg-add` for `nvidia-580xx-dkms`, `nvidia-580xx-utils` and `lib32-nvidia-580xx-utils`, because `nvidia-dkms` dropped Pascal at driver 590. `omarchy-pkg-add` is plain `pacman -S --noconfirm --needed`, so every target has to come from a synced pacman database and no AUR helper is ever consulted. None of the three is in `core`, `extra` or `multilib`. On an installed Omarchy 4.0.2 system they come from the `[omarchy]` repository at 580.178.04-1.1. The install fails when that repository is not reachable or its database is not synced at the hardware stage, which is what the ISO's offline package set produces. `pacman` then reports `target not found`, `omarchy-pkg-add` exits 1, and because `run_logged` executes each hardware script under `bash -eE` the script dies immediately and takes the rest of the install with it.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation (omarchy 4.0.2-1, mkinitcpio 41.1-1, limine-mkinitcpio-hook 1.37.1-1, kernel 7.1.9-arch1-2) and against the upstream `quattro` tree and both cited issues read in full. The core claim holds: I read `/usr/share/omarchy/install/hardware/nvidia.sh` locally and fetched the same file from `omacom/omarchy` at `quattro`, and the `omarchy-hw-nvidia-without-gsp` branch does request exactly `nvidia-580xx-dkms`, `nvidia-580xx-utils` and `lib32-nvidia-580xx-utils`. Issue 7947 is open, quotes the same two `target not found` lines, and confirms the failure aborts the install. Four things were wrong for Omarchy 4. First, the path: the record sends the reader to `~/.local/share/omarchy/install/config/hardware/nvidia.sh`, which is the Omarchy 3 git-checkout layout. Omarchy 4 is pacman-packaged and the file is `/usr/share/omarchy/install/hardware/nvidia.sh` (confirmed with `pacman -Qo`), reached as `/mnt/usr/share/omarchy/...` during the ISO install, which is the path issue 7947 itself names. Second, the AUR claim: `pacman -Sl omarchy` on this machine lists all three packages in the `[omarchy]` repository at 580.178.04-1.1 with a build date of 2026-08-13, ten days before issue 7947 was filed, and `omarchy-pkg-add` is plain `pacman -S --noconfirm --needed` that never consults an AUR helper, so `yay -S` is the wrong tool and "they live in the AUR" is the wrong cause. Third, `sudo mkinitcpio -P` fails on Omarchy 4: `/etc/mkinitcpio.d/` is empty and `mkinitcpio` line 986 dies with `No presets found in /etc/mkinitcpio.d`, so the rebuild is `sudo limine-mkinitcpio`. Fourth, the `~/.config/hypr/envs.conf` block is Omarchy 3 hyprlang and is redundant: `/usr/share/omarchy/default/hypr/nvidia.lua`, which I read both locally and upstream, already sets `NVD_BACKEND=egl` and `__GLX_VENDOR_LIBRARY_NAME=nvidia` behind the same `omarchy-hw-nvidia-without-gsp` test. The danger was rewritten because there is no git working tree to be dirty on Omarchy 4. The real risk is a silent pacman overwrite of a non-backup file, and the rebuild step needed a recovery path stated, which Omarchy 4 does not provide as a fallback initramfs entry. All three cited URLs are removed: `https://github.com/basecamp/omarchy/issues/7947` and `.../3954` both return HTTP 404 to `curl -L`, because GitHub's rename redirect covers the repository root and blob paths but not issue paths, and the `basecamp/omarchy/blob/master/install/config/hardware/nvidia.sh` URL resolves but serves the Omarchy 3 script and is the origin of the wrong path in the fix. Confirmed on this machine: the file paths, package ownership, the `[omarchy]` repository contents, the empty preset directory, the `mkinitcpio` die message in source, `bash -eE` in `run_logged`, `Backup Files : None`, and that the ALPM guard blocks only sync plus sysupgrade. Not exercised: I did not run an Omarchy install, so the claim that the `[omarchy]` database is what is missing during the ISO hardware stage rests on issue 7947 plus the package build date, not on a reproduction, and this workstation carries an RTX 3090 (GA102, `0x2204`) so it takes the GSP branch and I could not run the 580xx path at all.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `/usr/share/omarchy/install/hardware/nvidia.sh` is owned by the `omarchy` package and is not a pacman backup file (`pacman -Qii omarchy` reports `Backup Files : None`), so the `exit 0` edit is overwritten with no `.pacnew` and no warning the next time `omarchy` is upgraded, and `pacman -Qkk omarchy` flags it as altered until you revert it. Treat it as a workaround for one install, not a setting. Step 4 rebuilds the initramfs and rewrites the UKI on the ESP. If the machine then fails to reach Hyprland, Omarchy 4 builds no fallback initramfs entry, so recovery is a Limine btrfs snapshot entry (run `limine-list` first to see which exist) or a chroot from the Omarchy ISO. Do not reach for `pacman -Sy` to pick up the `[omarchy]` database: on its own it is a partial upgrade and a classic way to break an Arch system.

**Fix.**

Skip the failing hardware script, finish the install, then install the driver from the `[omarchy]` repository after first boot.

**1. Neutralise the hardware script in the install target.** From the ISO the installed system is mounted at `/mnt`, so the path carries that prefix:

```bash
sudo sed -i '1i exit 0' /mnt/usr/share/omarchy/install/hardware/nvidia.sh
```

On an already-booted machine that is failing a re-run of `omarchy apply hardware`, drop the `/mnt`:

```bash
sudo sed -i '1i exit 0' /usr/share/omarchy/install/hardware/nvidia.sh
```

**2. Resume the install.** This is the step the reporter of omacom/omarchy#7947 used:

```bash
sudo omarchy-apply-system
```

**3. After first boot, sync the databases and install the driver.** All three packages are in the `[omarchy]` repository (`Server = https://pkgs.omarchy.org/stable/$arch`), so no AUR helper is involved. Run `omarchy update` first, because a bare `pacman -Sy` is a partial upgrade:

```bash
omarchy update
sudo pacman -S --needed linux-headers nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils
```

The ALPM guard blocks only `-S` combined with `-u`, so a plain `pacman -S` is allowed here. On a non-stock kernel install that kernel's headers instead, for example `linux-lts-headers`.

**4. Apply the configuration the script never reached.** `run_logged` in `install/hardware/all.sh` runs each script under `bash -eE`, so `nvidia.sh` died at the package step and wrote neither file:

```bash
printf 'options nvidia_drm modeset=1\n' | sudo tee /etc/modprobe.d/nvidia.conf
printf 'MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)\n' | sudo tee /etc/mkinitcpio.conf.d/nvidia.conf
sudo limine-mkinitcpio
```

Use `limine-mkinitcpio`, not `mkinitcpio -P`. Omarchy 4 keeps `/etc/mkinitcpio.d/` empty and builds a UKI through Limine, so `mkinitcpio -P` stops with `ERROR: No presets found in /etc/mkinitcpio.d`.

**5. Do nothing about Hyprland environment variables.** Omarchy 4 sets them per session from `/usr/share/omarchy/default/hypr/nvidia.lua`, which runs `omarchy-hw-nvidia-without-gsp` and applies `NVD_BACKEND=egl` and `__GLX_VENDOR_LIBRARY_NAME=nvidia` for exactly this class of card. The `env = NVD_BACKEND,egl` lines in `~/.config/hypr/envs.conf` are Omarchy 3 hyprlang syntax and Omarchy 4 does not read them.

**6. Put the script back**, then reboot:

```bash
sudo sed -i '1{/^exit 0$/d}' /usr/share/omarchy/install/hardware/nvidia.sh
pacman -Qkk omarchy
reboot
```

Until the driver is installed the machine runs on `nouveau`, which is slow but fine for finishing setup.

**Verify.** ```bash
pacman -Q nvidia-580xx-dkms                                       # prints 580.178.04-1.1 or newer
dkms status                                                       # nvidia 580.178.04 installed for the running kernel
nvidia-smi                                                        # reports the GPU
sudo lsinitcpio /boot/EFI/Linux/omarchy_linux.efi | grep nvidia   # the four modules are in the UKI
pacman -Qkk omarchy                                               # 0 altered files, so step 6 really reverted the edit
```

`/boot` is a vfat ESP mounted `dmask=0077`, so the `lsinitcpio` line needs root. There is no `/boot/initramfs-linux.img` to inspect on Omarchy 4.

Sources: <https://github.com/omacom/omarchy/issues/7947> · <https://github.com/omacom/omarchy/issues/3954> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/nvidia.sh> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/nvidia.lua> · <https://archlinux.org/news/nvidia-590-driver-drops-pascal-support-main-packages-switch-to-open-kernel-modules/> · <https://wiki.archlinux.org/title/NVIDIA>

---

## Stop Electron/Chromium apps flickering on NVIDIA + Hyprland

`electron-chromium-flicker-nvidia-wayland` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** VS Code / VSCodium, Discord (Vesktop), Obsidian, Slack, Spotify and Chromium-based browsers flicker, tear, or show stale frames when scrolling or dragging, on an NVIDIA GPU under Hyprland. Native GTK apps look fine.

**Cause.** Electron/CEF apps default to running under XWayland and do not use the `linux-drm-syncobj-v1` (explicit sync) protocol. Without explicit sync, the NVIDIA driver has no implicit synchronisation for these buffers, so Hyprland presents half-rendered or out-of-order frames.

**Fix.**

Make Electron apps run natively on Wayland and enable explicit sync.

In `~/.config/hypr/envs.conf` (Omarchy 3.x / Hyprland ≤ 0.54):

```
env = ELECTRON_OZONE_PLATFORM_HINT,auto
```

Hyprland 0.55+ / Lua config:

```lua
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")
```

For apps that ignore the hint, add the flags to their per-app flags file:

```bash
# Chromium
cat >> ~/.config/chromium-flags.conf <<'EOF'
--enable-features=UseOzonePlatform,WaylandLinuxDrmSyncobj
--ozone-platform=wayland
EOF

# Brave / Chrome / VSCodium / Obsidian use the same pattern:
#   ~/.config/brave-flags.conf
#   ~/.config/chrome-flags.conf
#   ~/.config/codium-flags.conf
#   ~/.config/obsidian/user-flags.conf
```

For Spotify, use the `spotify-launcher` package (official repos) rather than the AUR `spotify`, and:

```bash
mkdir -p ~/.config
cat > ~/.config/spotify-launcher.conf <<'EOF'
[spotify]
extra_arguments = ["--enable-features=UseOzonePlatform", "--ozone-platform=wayland"]
EOF
```

Log out and back into Hyprland (env changes only apply to newly started sessions).

**Verify.** In Chromium open `chrome://gpu` — 'Ozone platform' should read `wayland`. The app window no longer flickers while scrolling. `hyprctl clients` shows the app without an `xwayland: 1` flag.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://github.com/basecamp/omarchy/issues/3899>

---

## Get the NVIDIA dGPU to actually power down on a hybrid laptop

`nvidia-dgpu-no-runtime-d3-battery-drain` · severity: **medium** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Battery life is roughly halved on a laptop with an NVIDIA dGPU. `nvidia-smi` shows the GPU permanently awake, `sudo lsof +c0 /dev/nvidia*` lists Hyprland and random desktop apps holding it open, and `cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status` never says `suspended`.

**Cause.** PCI-Express Runtime D3 power management is not configured, so the dGPU never enters D3cold. Anything that touches an EGL/Vulkan device enumeration (including the compositor itself) wakes it and keeps it up.

> **Audit corrected this record.** The udev rules are byte-identical to Arch's PRIME#PCI-Express Runtime D3 (RTD3) section, `options nvidia "NVreg_DynamicPowerManagement=0x02"` including the quoting is the wiki's own, the 0x03 note for 'Ampere or later notebooks with supported configurations' is correct, the runtime_status check path is correct, and nvidia-prime-rtd3pm really does ship those two files. Two defects in the tail: (a) `VK_DRIVER_FILES=/usr/share/vulkan/icd.d/intel_icd.json` is hardcoded to Intel on a record that also claims to apply to AMD iGPUs (the AMD file is `radeon_icd.json`), and pinning a single 64-bit ICD silently removes Vulkan from 32-bit Steam/Proton — a wrong path here breaks Vulkan everywhere with no error message; (b) enabling nvidia-persistenced is at best pointless here and reads as counterproductive advice in a 'make the dGPU sleep' record.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting `VK_DRIVER_FILES` and `__EGL_VENDOR_LIBRARY_FILENAMES` globally means Vulkan/OpenGL apps will NOT see the NVIDIA GPU unless you unset or override them per-app — Steam games launched without `prime-run` will silently run on the iGPU. If `Runtime D3 status: Not supported` persists on nvidia-open below driver 610, the udev rules have no effect.

**Fix.**

```bash
sudo tee /etc/udev/rules.d/80-nvidia-pm.rules >/dev/null <<'EOF'
# Enable runtime PM for NVIDIA VGA/3D controller devices on driver bind
ACTION=="bind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", TEST=="power/control", ATTR{power/control}="auto"
ACTION=="bind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", TEST=="power/control", ATTR{power/control}="auto"

# Disable runtime PM for NVIDIA VGA/3D controller devices on driver unbind
ACTION=="unbind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", TEST=="power/control", ATTR{power/control}="on"
ACTION=="unbind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", TEST=="power/control", ATTR{power/control}="on"
EOF

# Turing and Ampere-or-older notebooks:
sudo tee /etc/modprobe.d/nvidia-pm.conf >/dev/null <<'EOF'
options nvidia "NVreg_DynamicPowerManagement=0x02"
EOF
# Ampere-or-newer notebooks with supported configurations: use 0x03 instead.

reboot
```

(Or install the AUR package `nvidia-prime-rtd3pm`, which ships exactly these two files. Do not enable `nvidia-persistenced` for this — it is unrelated to RTD3.)

Verify:

```bash
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status          # want: suspended
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_suspended_time  # should be climbing
```

To stop EGL/GLX clients waking the card, default them to Mesa — but check your ICD filenames first, a bad path kills Vulkan silently:

```bash
ls /usr/share/vulkan/icd.d/ /usr/share/glvnd/egl_vendor.d/

sudo tee /etc/environment.d/50-mesa-default.conf >/dev/null <<'EOF'
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
__GLX_VENDOR_LIBRARY_NAME=mesa
EOF
```

Leave `VK_DRIVER_FILES` unset unless you have a reason to pin it; if you do set it, list every ICD you still need (Intel: `intel_icd.json`, AMD: `radeon_icd.json`, plus the 32-bit ones from that directory listing if you use Steam/Proton), colon-separated.

**Verify.** ```bash
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status   # suspended
cat /proc/driver/nvidia/gpus/0000:01:00.0/power              # Runtime D3 status: Enabled
```
If `runtime_status` reports `active`, check that `power/runtime_suspended_time` keeps incrementing — that also means it is asleep.

Sources: <https://wiki.archlinux.org/title/PRIME> · <https://github.com/basecamp/omarchy/issues/1776> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-toggle-hybrid-gpu>

---

## Run a specific application on the dGPU with PRIME render offload

`prime-render-offload-app-uses-igpu` · severity: **medium** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** A game or GPU app runs at a fraction of expected speed on a hybrid laptop. `glxinfo | grep "OpenGL renderer"` reports the Intel/AMD iGPU even though an NVIDIA card is present, and `nvidia-smi` shows no processes.

**Cause.** On a PRIME offload setup the iGPU is the primary renderer by design. Applications only use the dGPU when they are explicitly offloaded with the right GLVND/Vulkan environment variables.

**Fix.**

```bash
sudo pacman -S --needed nvidia-prime

# quick check
prime-run glxinfo | grep "OpenGL renderer"
prime-run vulkaninfo | head
```

`prime-run` is just a wrapper for these variables; use them directly when you cannot prefix the command:

```bash
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia <command>
```

For a Steam title, set the launch options to:

```
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

If you globally forced Mesa for power saving (see the RTD3 record), you must also override the ICD lists for offloaded apps:

```bash
__NV_PRIME_RENDER_OFFLOAD=1 \
__GLX_VENDOR_LIBRARY_NAME=nvidia \
__VK_LAYER_NV_optimus=NVIDIA_only \
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
<command>
```

If you have `bumblebee` installed, remove it — it blacklists `nvidia_drm`, which offloading requires:

```bash
sudo pacman -Rns bumblebee
```

**Verify.** `prime-run glxinfo | grep "OpenGL renderer"` names your NVIDIA GPU, and `nvidia-smi` lists the process while it runs.

Sources: <https://wiki.archlinux.org/title/PRIME> · <https://wiki.archlinux.org/title/Vulkan>

---

## Screen share is a black rectangle (or no picker appears) on Hyprland

`screen-share-black-portal-hyprland` · severity: **medium** · frequency: **very-common** · applies to: `amdgpu`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy-4`

**Symptom.** In Discord, Zoom, Google Meet, Teams or OBS you start a share and the other side sees a solid black rectangle — audio works, video does not. Or the Qt share picker never appears at all and the browser reports no capture sources. `journalctl --user -u xdg-desktop-portal -b` shows lines like `No skeleton portal implementation` or `Failed to load portal implementation`. A plain `grim screenshot.png` from the same session may work fine, which makes it look like the compositor is healthy.

**Cause.** Capture goes through a chain — app → `xdg-desktop-portal` → `xdg-desktop-portal-hyprland` (XDPH) → Hyprland's screencopy → PipeWire — and every link breaks in its own way:

1. `pipewire`, `wireplumber` or `xdg-desktop-portal-hyprland` is not running.
2. XDPH was D-Bus-activated before `WAYLAND_DISPLAY` / `XDG_CURRENT_DESKTOP` / `HYPRLAND_INSTANCE_SIGNATURE` reached the activation environment, so it cannot talk to the compositor and hands back an empty stream.
3. A second portal backend is installed (`xdg-desktop-portal-wlr`, `-gnome`, `-kde`) and wins the `ScreenCast` interface, or a stale `~/.config/xdg-desktop-portal/portals.conf` from an old setup routes it somewhere dead.
4. **10-bit output.** The Hyprland Monitors page states outright that "some applications do not support screen capture with 10 bit enabled", and the Screen Sharing page tells you to make sure `bitdepth` matches your physical monitor. A `bitdepth = 10` monitor line is one of the most common causes of a black capture.
5. The capturing app is running under XWayland (the Discord desktop client, older Skype). Per the Hyprland wiki it can then only see other XWayland windows — it cannot capture a whole screen or a native Wayland window.

> **Audit corrected this record.** Nearly all of this is verbatim wiki-sourced and correct. The XDPH wiki page carries the exact warning "XDPH doesn't implement a file picker. For that, it is recommended to install xdg-desktop-portal-gtk alongside XDPH", so keeping GTK is right. Screen-Sharing.md says "Ensure that the bitdepth set in your configuration matches that of your physical monitor" and Monitors.md says "Some applications do not support screen capture with 10 bit enabled" — both quoted accurately, and the bitdepth = 8 fix is the wiki's own. The XWayland limitation is quoted almost word for word from Screen-Sharing.md, and the xwaylandvideobridge window_rule block — including `opacity = 0.0`, which the Variables table types as a string but the wiki's own example writes as a number — is copied verbatim from that page, so I am not faulting it. hl.on("hyprland.start", ...) with hl.exec_cmd() is the documented autostart form. xwaylandvideobridge is correctly labelled AUR (0.4.0-3). One real defect: `/usr/share/xdg-desktop-portal/hyprland-portals.conf` does not exist. I pulled both Arch package file lists — xdg-desktop-portal-hyprland ships only usr/share/xdg-desktop-portal/portals/hyprland.portal, and xdg-desktop-portal ships no *-portals.conf at all (its only matching file is the portals.conf.5 man page). Omarchy ships none either. So step 3's `cp` fails with 'No such file or directory' and the parenthetical claim about default routing living there is wrong.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Removing `xdg-desktop-portal-wlr` with `-Rns` will also take its dependencies; if any other compositor on this machine relies on it, that session loses file pickers and screen capture. Do not remove `xdg-desktop-portal-gtk` — XDPH has no file picker of its own and every GTK/Electron "Open File" dialog will stop working. Dropping `bitdepth` from 10 to 8 loses HDR/wide-gamut output on that display.

**Fix.**

Steps 1, 2 and 4 through 8 stand as written. Two things change.

**Step 2's parenthetical:** keep `xdg-desktop-portal-gtk` — XDPH does not implement a file picker and the Hyprland wiki recommends GTK alongside it. XDPH's own interface declaration lives in `/usr/share/xdg-desktop-portal/portals/hyprland.portal`; there is **no** `/usr/share/xdg-desktop-portal/hyprland-portals.conf` on Arch or Omarchy.

**Step 3 — reset a stale user portals.conf.** Deleting it is the fix; there is no packaged Hyprland file to copy back, so just remove yours and let xdg-desktop-portal fall back to its built-in resolution:

```bash
rm -f ~/.config/xdg-desktop-portal/portals.conf
rm -f ~/.config/xdg-desktop-portal/hyprland-portals.conf   # if you made one
```

If you want an explicit routing file instead of the default, write it yourself rather than copying a file that does not exist:

```ini
# ~/.config/xdg-desktop-portal/portals.conf
[preferred]
default=hyprland;gtk
org.freedesktop.impl.portal.ScreenCast=hyprland
org.freedesktop.impl.portal.Screenshot=hyprland
org.freedesktop.impl.portal.FileChooser=gtk
```

See `man 5 portals.conf` for the syntax. Then restart the chain as in step 5:

```bash
systemctl --user restart pipewire wireplumber
systemctl --user restart xdg-desktop-portal-hyprland xdg-desktop-portal
```

**Verify.** Starting a share pops the Qt `hyprland-share-picker` window, and the receiving side sees live content. `grim /tmp/t.png && xdg-open /tmp/t.png` produces a non-black image (proves screencopy itself is fine). In OBS, a `PipeWire Screen Capture` source shows a live preview.

Sources: <https://wiki.hypr.land/Useful-Utilities/Screen-Sharing/> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Hypr%20Ecosystem/xdg-desktop-portal-hyprland.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md> · <https://gist.github.com/brunoanc/2dea6ddf6974ba4e5d26c3139ffb7580> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Nvidia/_index.md>

---

## AMD or Intel monitor capped at 4K@60 over HDMI, because HDMI 2.1 is not on the open drivers

`amd-hdmi-2-1-capped-at-60hz` · severity: **medium** · frequency: **common** · applies to: `amdgpu`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `omarchy-4`

**Symptom.** "My 4K 144 Hz monitor (or LG C-series OLED TV) only offers 60 Hz over HDMI on Linux, but does 120/144 Hz in Windows on the same cable and the same Radeon card." `hyprctl monitors all` lists no mode above `3840x2160@60`, or offers 120 Hz only with visibly degraded colour (text fringing) because it fell back to 4:2:0 chroma subsampling. Switching cables, ports, and `mode` strings changes nothing.

**Cause.** Not a bug and not fixable in config. The HDMI Forum refused to allow an open-source implementation of the HDMI 2.1 specification, so Mesa and the `amdgpu` kernel driver cannot implement Fixed Rate Link (FRL) signalling. The Arch wiki states it plainly: "Due to licensing issues the mesa driver cannot support HDMI 2.1. You must use DisplayPort."

The practical ceiling is therefore HDMI 2.0 bandwidth (18 Gbit/s): 4K@60 at 8-bit RGB, or 4K@120 only by dropping to 4:2:0. This affects every open driver — AMD `amdgpu` and Intel `i915`/`xe` alike. NVIDIA's proprietary driver is unaffected because it is a closed blob that ships its own HDMI implementation, which is why the same monitor behaves differently on an NVIDIA machine.

A related but separate symptom on the same page: chipmunk/double-speed or absent audio when a 4K@60 device is attached over HDMI, which is a handshake problem rather than a bandwidth one.

> **Audit corrected this record.** The substance is excellent and directly wiki-sourced. Arch AMDGPU wiki line 650 reads "Due to licensing issues the mesa driver cannot support HDMI 2.1. You must use DisplayPort. If your display does not support DisplayPort, some users have reported success with converter devices that take DisplayPort input and output HDMI 2.1 signals" — the record's quote is verbatim and even the active-converter recommendation is the wiki's own. The Lua is correct against the current Hyprland wiki: `hl.monitor({ output, mode, position, scale })` is the documented signature, `bitdepth` is a real field (integer, 8 or 10), and both /sys/class/drm/card*-HDMI-A-1/modes and the nested card*/card*-HDMI-A-1 form resolve. One concrete defect: the diagnostic line comments the package as `drm_info`, but the Arch package is named **drm-info** (extra) — `drm_info` is only the binary, and there is no drm_info package in extra or the AUR (only drm_info-git). Anyone who types the commented name gets 'target not found'.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Identical to the original, with one package name fixed in step 1 (`drm_info` is the binary; the package is `drm-info`):

**1. Confirm you are actually bandwidth-limited rather than mis-configured.**

```bash
hyprctl monitors all                     # look at availableModes for the HDMI output
sudo pacman -S drm-info                  # package is drm-info; binary is drm_info
drm_info 2>/dev/null | grep -iA5 'HDMI'
sudo cat /sys/class/drm/card*-HDMI-A-1/modes
lspci -nnd ::03xx                        # AMD/Intel = affected; NVIDIA proprietary = not
```

If `availableModes` genuinely has no entry above `3840x2160@60`, you are hitting the cap.

Steps 2 through 5 stand exactly as written: DisplayPort is the fix; an *active* DP-to-HDMI-2.1 protocol converter is the workaround for a display with no DP input (passive adapters and "HDMI 2.1 certified" cables do nothing); otherwise pick your compromise explicitly with `hl.monitor({ ... mode = "3840x2160@120" })` for 4:2:0, `"2560x1440@144"` for full colour at high refresh, or `mode = "3840x2160@60", bitdepth = 10`; and check the display's own OSD for "Ultra HD Deep Color" if HDMI audio is double-speed or missing.

**Verify.** `hyprctl monitors` shows the intended refresh rate as active for that output; `hyprctl monitors all | grep -A20 availableModes` confirms what the link can actually carry.

Sources: <https://wiki.archlinux.org/title/AMDGPU> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md> · <https://wiki.hypr.land/Useful-Utilities/Screen-Sharing/>

---

## Fix AMD screen flickering white/grey when plugging in a monitor

`amdgpu-screen-flicker-white-sg-display` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** On an AMD APU laptop, the screen flickers white or grey — or stays white — when changing resolution, plugging in an external monitor, or waking a display.

**Cause.** A bug in the amdgpu 'scatter-gather display' path, which lets the display engine scan out from system memory on APUs.

> **Audit corrected this record.** I checked the single cited source, https://wiki.archlinux.org/title/AMDGPU, by fetching its raw wikitext. It does support the symptom and the parameter: the section "Screen flickering white/gray" says verbatim that when you change resolution or connect to an external monitor and the screen flickers or stays white, you should add `amdgpu.sg_display=0` as a kernel parameter. So the source stands and I removed nothing. The cause also holds, and I confirmed it against the driver rather than the wiki: `drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c` at tag v7.1 documents `sg_display` as "Disable S/G (scatter/gather) display (i.e., display from system memory). This option is only relevant on APUs", with `int amdgpu_sg_display = -1; /* auto */`, so the parameter still exists on the kernel this corpus targets and `0` is the documented way to turn it off. What was wrong is the fix and the danger, both of which describe a machine Omarchy 4 is not. I confirmed on this workstation (omarchy 4.0.2-1, kernel 7.1.9-arch1-2) that `/etc/default/grub` does not exist and no `grub` package is installed, so the GRUB `sed` recipe is dead advice for the `omarchy` tag, and `/boot/limine.conf` is regenerated on every kernel transaction so the Limine line the record gives is silently discarded. The real path is a drop-in under `/etc/limine-entry-tool.d/` using `+=`, which I verified from the installed `/etc/limine-entry-tool.conf` template ("`+=` appends parameters ... Commonly used in drop-in configs: /etc/limine-entry-tool.d/*.conf", "`=` replaces") and from the Limine Arch wiki page, and which agrees with the existing corpus record `limine-kernel-parameters-not-applying-omarchy`. I read `/etc/limine-entry-tool.d/omarchy-defaults.conf` on this machine and fetched the same file at upstream tag v4.0.3 (published 2026-09-08, the newest tag), and the two are identical, so this is still true on the current release. The old danger was also wrong in substance: it claimed the recovery is to press `e` at the boot menu, which is not Limine's documented key, and it ignored that a bare `=` in the drop-in silently deletes `initramfs_async=0` and leaves an encrypted machine at an unthemed text prompt with no desktop. NOT EXERCISED: this workstation has an NVIDIA GeForce RTX 3090 and no `amdgpu` module is loaded (`/sys/module/amdgpu` does not exist), so nothing about the AMD behaviour was tested here. The parameter's effect is taken from the kernel source and the wiki, not from a reproduction, and I did not run `limine-mkinitcpio` or `limine-update` on this machine.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `amdgpu.sg_display=0` itself is low risk. It only stops the display engine scanning out of system memory on an APU, and the cost is that the driver must keep framebuffers in carved-out VRAM, which can fail under memory pressure on a small-carveout APU.

The risk is the drop-in. Writing `KERNEL_CMDLINE[default]=` instead of `+=`, or naming the file so it sorts before `omarchy-defaults.conf`, throws Omarchy's own defaults away, including `initramfs_async=0`. The comment in the packaged file says that parameter is what stops plymouthd exiting on kernel 7.1, so an encrypted machine falls back to an unthemed text LUKS prompt or sits there with no graphical session. `limine-mkinitcpio` rewrites the UKI on the ESP, so run `df -h /boot` first, because a full ESP produces a truncated image that will not boot. Recovery is the Limine snapshot entry or editing the command line in the Limine boot menu, and Omarchy's Direct Boot (`omarchy-setup-direct-boot`) bypasses that menu entirely, so do not enable Direct Boot while you are still testing kernel parameters.

**Fix.**

Add the kernel parameter `amdgpu.sg_display=0`.

**On Omarchy 4 the parameter goes in a Limine drop-in, not in a bootloader config.** There is no `/etc/default/grub` (no `grub` package is installed), and editing `/boot/limine.conf` is discarded, because Omarchy boots a Unified Kernel Image with the command line baked into the `.efi` and regenerates `/boot/limine.conf` on every kernel transaction. Write your own drop-in whose filename sorts after Omarchy's `omarchy-defaults.conf`, and always use `+=` so you append instead of replacing Omarchy's own defaults:

```bash
sudo tee /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
# `+=` appends. A bare `=` REPLACES Omarchy's defaults and drops
# quiet/splash/initramfs_async=0.
KERNEL_CMDLINE[default]+=" amdgpu.sg_display=0"
EOF

sudo limine-mkinitcpio
sudo limine-update
sudo reboot
```

The full mechanism, including how to test a parameter once from the Limine boot menu without writing anything to disk, is in the record `limine-kernel-parameters-not-applying-omarchy`.

**On other Arch-based systems:**

- Limine, with or without a UKI: the same `/etc/limine-entry-tool.d/*.conf` drop-in, then `sudo limine-update`
- systemd-boot: append it to the `options` line in `/boot/loader/entries/*.conf`
- GRUB:

```bash
sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="/&amdgpu.sg_display=0 /' /etc/default/grub
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

Reboot.

**Verify.** `cat /proc/cmdline` contains `amdgpu.sg_display=0`, and on Omarchy it must still contain Omarchy's own defaults (`quiet splash loglevel=0 ... initramfs_async=0`). If those defaults are missing, your drop-in used a bare `=` or sorts before `omarchy-defaults.conf`.

```bash
cat /sys/module/amdgpu/parameters/sg_display   # 0 once applied, -1 is the auto default
```

Then hot-plug the external monitor or change resolution and confirm the screen no longer flashes white.

Sources: <https://wiki.archlinux.org/title/AMDGPU> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/torvalds/linux/blob/v7.1/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c> · <https://github.com/torvalds/linux/blob/v7.1/drivers/gpu/drm/amd/include/amd_shared.h> · <https://github.com/omacom/omarchy/blob/v4.0.3/etc/limine-entry-tool.d/omarchy-defaults.conf>

---

## AV1 video shows shifted colours or blocky corruption on AMD graphics (linux-firmware-amdgpu 20260810-1)

`av1-video-color-corruption-linux-firmware-amdgpu-20260810-1` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `brave`, `chromium`, `desktop`, `firefox`, `laptop`, `omarchy`, `rdna4`, `rx-9070-xt`, `youtube`

**Symptom.** After updating, or on a fresh Omarchy 4.0.0-1 install, AV1 video in Firefox, Chromium and Brave shows rectangular areas in the wrong colours, sometimes pixelated. Lower resolutions such as 480p look fine and higher AV1 streams do not, for example YouTube `av01.0.12M.08` at 4K while `av01.0.04M.08` at 480p is clean. The corruption is in the decoded frames, so it appears in screenshots too.

Reported on a Ryzen 7 8745HS with Radeon 780M and a Ryzen 5 7640U with Radeon 760M, both on Omarchy 4.0.0-1, and on two Radeon RX 9070 XT machines, one of which was still on Omarchy 3.8.4 and read the broken firmware from the same Omarchy stable mirror. `pacman -Q linux-firmware-amdgpu` shows `20260810-1`. The RX 9070 XT reports add Mesa 26.1.7-1, libva 2.24.1-1 and kernel 7.1.8-arch1-3.

**Cause.** `linux-firmware-amdgpu 20260810-1` carries an AMD GPU firmware regression that corrupts hardware AV1 decoding. The browsers all reach the decoder through VA-API, which on Mesa is the radeonsi gallium media path, so every browser was affected.

The firmware changed how the AV1 decoder reads the quantizer matrix parameters. The high 4 bits of `qm_y`, `qm_u` and `qm_v` stopped being ignored, while Mesa was still OR-ing `0xf0` into all three unconditionally. Two independent fixes exist upstream and either one is enough, but they do not stack the way the version numbers suggest.

Arch published `linux-firmware-amdgpu 20260810-2` on 2026-08-14. Its packaging commit `ba3cc99c` is "20260810-2: Backport an upstream revert and revert all amdgpu VCN firmware", so it reverts every amdgpu VCN blob rather than only the RDNA4 one.

Mesa merge request 43787, `radeonsi,radv/video: Fix AV1 decode qmatrix params`, merged on 2026-08-17 and shipped in Mesa 26.1.8 on 2026-08-19. It carries two commits, `radeonsi/mm: Fix AV1 decode qmatrix params` for the VA-API path the browsers use and `radv/video: Fix AV1 decode qmatrix params` for Vulkan video. The radeonsi change, in `src/gallium/drivers/radeonsi/mm/si_video_dec.c`, passes the raw quantizer matrix values when the stream uses one and `0xff` when it does not, and it is not gated on any ASIC, so it covers every VCN generation.

Arch then published `20260810-3` on 2026-09-08 with packaging commit `cc4c7047`, "20260810-3: Remove VCN revert now that Mesa is fixed", and `20260910-1` on 2026-09-10 on top of that. From `-3` onwards the firmware revert is gone and the fix rests on Mesa alone, so a machine on `-3` or newer whose Mesa is older than 26.1.8 is back in the broken combination.

The thread established the mechanism on RDNA4 (gfx12, Navi 48), and the Radeon 780M and 760M reports belong in the same record rather than a separate one: they carry the same firmware version, the Mesa fix is ASIC-independent, and the `-2` revert covered all VCN generations. The 780M reporter confirmed that `-2` cleared it. The 760M reporter confirmed only the Firefox workaround and never reported back on the firmware update.

Omarchy's stable mirror lagged, which is why this reached people a week after Arch had fixed it. The reporter of issue 7514 read the mirror's `core.db` as last modified Fri, 14 Aug 2026 15:15:59 GMT, and `-2` reached the Arch archive at 15:52 the same day, so the snapshot was taken about 37 minutes before the fixed build existed. The mirror was serving `20260810-2` by 2026-08-22, read from `/var/log/pacman.log` on an Omarchy stable workstation.

> **Audit corrected this record.** Checked the Arch package archive with curl and a named user agent: 20260810-2 is dated 14-Aug-2026 15:52 and 20260810-3 is dated 08-Sep-2026 21:07, both as the record says, and a fourth build, 20260910-1, landed on 10-Sep-2026 which the record does not know about. The Arch packaging commits say what each build does, and that is the main defect: ba3cc99c is "20260810-2: Backport an upstream revert and revert all amdgpu VCN firmware" while cc4c7047 is "20260810-3: Remove VCN revert now that Mesa is fixed", so the record's "anything from -2 up carries the fix" is wrong. From -3 onwards the firmware revert is gone and the fix rests entirely on Mesa 26.1.8 or newer, so a machine on -3 or 20260910-1 with an older Mesa is back in the broken pair, and the fix and verify text had to be rewritten around that. Confirmed on this machine: /var/log/pacman.log records linux-firmware-amdgpu 20260810-1 installed at 2026-08-23T00:40:33+0000 and upgraded to 20260810-2 at 2026-08-22T17:52:45-0700, in the same transaction that took mesa from 1:26.1.7-1 to 1:26.1.8-1, which confirms the mirror claim as written. Mesa merge request 43787 is titled "radeonsi,radv/video: Fix AV1 decode qmatrix params", not "radv/video:" as the record has it, and it carries two commits, so the record quoted the Vulkan one while its own mechanism is VA-API, which runs through the radeonsi commit. On Q2 the answer is do not split the RDNA3 reports out: I read the radeonsi diff, src/gallium/drivers/radeonsi/mm/si_video_dec.c in si_dec_av1, and it is gated on using_qmatrix rather than on any ASIC, the Mesa 26.1.8 notes of 2026-08-19 list both commits, and the -2 package reverted all amdgpu VCN blobs rather than only the Navi 48 one, so one firmware regression covers both generations. Read both cited issues in full: 7377 supports the 780M and 760M reports and the Firefox workaround, and its 780M reporter confirmed -2 cleared it while the 760M reporter only ever confirmed the Firefox workaround, so I narrowed that sentence. 7514 does not support "after an upgrade from Omarchy 3.8.4": that reporter was running Omarchy 3.8.4 and read the broken firmware off the same Omarchy stable mirror, and his core.db last-modified of Fri, 14 Aug 2026 15:15:59 GMT sits 37 minutes before -2 reached the archive, which is better evidence for the lag claim than the record gives, so I put it in. Not exercised: this workstation has an NVIDIA card, so no AV1 decode on AMD hardware was reproduced here and nothing about the corruption itself was seen first hand.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Update. Omarchy 4:

```bash
omarchy update
pacman -Q linux-firmware-amdgpu mesa
```

Plain Arch:

```bash
sudo pacman -Syu
```

Either upstream fix alone is enough, but check which one you ended up with, because Arch dropped the firmware revert again:

- `20260810-2` carries the firmware revert and fixes this on any Mesa.
- `20260810-3` (2026-09-08) and `20260910-1` (2026-09-10) dropped that revert, so on those you need Mesa 26.1.8 or newer.

So the good pairs are `20260810-2` with any Mesa, or `-3` and newer with Mesa 26.1.8 or newer. A full `omarchy update` gives you both halves and is the supported path. Do not pull the firmware package on its own, which leaves you with a partially upgraded system.

Reboot afterwards. GPU firmware is loaded when the `amdgpu` module initialises, so the running session keeps the old firmware until then.

If you cannot update yet, turn off the hardware AV1 path in the browser. One reporter on a Radeon 760M confirmed that disabling AV1 in Firefox, `media.av1.enabled` set to `false` in `about:config`, stops the corruption, because YouTube then falls back to VP9. For Chromium and Brave, launch with `--disable-accelerated-video-decode`, which the RX 9070 XT reporter used to isolate the fault to hardware decode. That same reporter found that disabling hardware decoding in Firefox alone did not help on his machine, so treat the Firefox route as unconfirmed there. All of this is a workaround, not the fix.

**Verify.** ```bash
pacman -Q linux-firmware-amdgpu mesa
```

You want either `20260810-2` with any Mesa, or `20260810-3` and newer together with Mesa 26.1.8 or newer. Arch's mesa carries an epoch, so 26.1.8 reads as `1:26.1.8-1`.

After a reboot, play a 1080p or 4K AV1 stream with hardware decoding on: colours are stable and no blocks appear. One reporter on Omarchy 4.0.0-1 confirmed the firmware update alone fixed it, and another confirmed Mesa 26.1.8 alone fixed it with the firmware still on `20260810-1`.

Sources: <https://github.com/omacom/omarchy/issues/7377> · <https://github.com/omacom/omarchy/issues/7514> · <https://archlinux.org/packages/core/any/linux-firmware-amdgpu/> · <https://archive.archlinux.org/packages/l/linux-firmware-amdgpu/> · <https://archlinux.org/packages/extra/x86_64/mesa/> · <https://gitlab.freedesktop.org/mesa/mesa/-/merge_requests/43787> · <https://gitlab.archlinux.org/archlinux/packaging/packages/linux-firmware/-/commits/main> · <https://gitlab.freedesktop.org/mesa/mesa/-/commit/3c4d3e46> · <https://gitlab.freedesktop.org/mesa/mesa/-/blob/main/docs/relnotes/26.1.8.rst>

---

## Fix hibernation that cold-boots instead of resuming on NVIDIA

`nvidia-early-kms-breaks-hibernation` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** You hibernate with `systemctl hibernate`, and on power-on the machine boots normally instead of restoring the session. Every application is gone, as if you had shut down. On Omarchy 4 this needs no action on your part to trigger: the installer early-loads the NVIDIA modules on every NVIDIA machine. On plain Arch it usually starts after adding the NVIDIA modules to the initramfs to fix a black screen. `journalctl -b -1 -k` from the failed attempt shows the image loading and the driver then refusing:

```
PM: Image successfully loaded
NVRM: GPU 0000:01:00.0: PreserveVideoMemoryAllocations module parameter is set.
      System Power Management attempted without driver procfs suspend interface.
nvidia 0000:01:00.0: PM: pci_pm_freeze(): nv_pmops_freeze [nvidia] returns -5
PM: hibernation: Failed to load image, recovering.
PM: hibernation: resume failed (-5)
```

**Cause.** Early KMS loads `nvidia`, `nvidia_modeset`, `nvidia_uvm` and `nvidia_drm` from the initramfs. With video memory preservation turned on, the driver requires a save and restore handshake at every power management transition, and at the point the hibernation image is loaded the initramfs kernel already has `nvidia` bound with no userspace to drive that handshake. The driver refuses the transition with `-5`, the kernel abandons the resume and continues into a normal boot. The Arch wiki states the consequence directly under DRM kernel mode setting: "Early loading the modules will break hibernation, as video memory preservation is enabled by default", and its Tips and tricks page adds that the early-loaded module "has no access to `NVreg_TemporaryFilePath` which stores the previous video memory: early KMS should not be used if hibernation is desired". The Hyprland wiki repeats the same warning twice.

On Omarchy 4 preservation is definitely on. `/proc/driver/nvidia/params` on an Omarchy 4.0.2 workstation running `nvidia-open-dkms` 610.57.04-1 reports `PreserveVideoMemoryAllocations: 1`, `UseKernelSuspendNotifiers: 1` and `TemporaryFilePath: "/var/tmp"`. The `1` comes from `/usr/lib/modprobe.d/gsr-nvidia.conf`, owned by `gpu-screen-recorder`, which Omarchy installs, so it is set even on the 595-and-newer drivers where Arch alone would leave it off and rely on kernel suspend notifiers. Omarchy 4 also writes `/etc/mkinitcpio.conf.d/nvidia.conf` with `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` on every NVIDIA machine during install, and configures hibernation itself through `/etc/mkinitcpio.conf.d/omarchy_resume.conf` and a `resume=` kernel argument in `/etc/limine-entry-tool.d/resume.conf`. An Omarchy NVIDIA machine therefore arrives in this state without anyone choosing it.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation, which has a real NVIDIA GPU (RTX 3090, GA102 `10de:2204`), `nvidia-open-dkms` 610.57.04-1 loaded, early KMS configured, mkinitcpio 41.1-1 and limine-mkinitcpio-hook 1.37.1-1, and against all three cited sources read in full plus omacom/omarchy#8126. The symptom and the direction of the fix are correct and all three cited URLs resolve and say what the record claims. The Arch NVIDIA page carries the note "Early loading the modules will break hibernation, as video memory preservation is enabled by default", the Tips and tricks page carries the `NVreg_TemporaryFilePath` sentence the record's cause paraphrases, and the Hyprland Nvidia page warns twice that early loading "may cause resuming from hibernation to not work anymore (i.e. the system will just boot instead of resuming)". So no source is removed. Four things were wrong or incomplete for Omarchy 4. First, `sudo mkinitcpio -P` fails outright: `/etc/mkinitcpio.d/` is empty on this machine and `mkinitcpio` line 986 dies with `No presets found in /etc/mkinitcpio.d`, so the Omarchy 4 rebuild is `sudo limine-mkinitcpio`. Second, the `rm` is correct but not durable, and the record does not say so: `/etc/mkinitcpio.conf.d/nvidia.conf` is owned by no package, and `/usr/share/omarchy/install/hardware/nvidia.sh` recreates it with `cat >` whenever `omarchy-apply-hardware` runs, which `omarchy-apply-system` calls at lines 94 and 96. Third, the record misses a side effect I read in `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` (owned by omarchy-settings): that drop-in strips the `kms` hook only while `nvidia_drm` is in `MODULES`, so removing the nvidia drop-in reinstates `kms` and pulls `nouveau` and its GSP firmware back into the image. Fourth, the verify and danger both named files that do not exist here. `/boot/initramfs-linux.img` is not built, because `/etc/limine-entry-tool.d/omarchy-uki.conf` sets `ENABLE_UKI=yes` and `omarchy-defaults.conf` sets `CUSTOM_UKI_NAME="omarchy"`, and `cat /sys/module/nvidia_drm/parameters/modeset` fails for a normal user because that file is mode `0400`. The danger told the reader to boot a fallback initramfs entry, and there is none: `MKINITCPIO_FALLBACK` is commented out in `/etc/limine-entry-tool.conf` line 179 and set nowhere else, and `limine-list` prints only `Omarchy / linux`, two Snapshots, and the Limine binary's own EFI fallback. The cause was rewritten rather than replaced, keeping the wiki's claim but adding what is observable here: `/proc/driver/nvidia/params` reports `PreserveVideoMemoryAllocations: 1`, `UseKernelSuspendNotifiers: 1`, `TemporaryFilePath: "/var/tmp"`, and the `Preserve` value comes from `/usr/lib/modprobe.d/gsr-nvidia.conf` owned by `gpu-screen-recorder` 6.0.1-1, not from an Arch default, which matters because on 595-and-newer drivers Arch leaves it to kernel suspend notifiers instead. The precise failure mechanism and the kernel log in the new symptom come from omacom/omarchy#8126, where a reporter with the same driver version and kernel reproduced it. Frequency moves from `occasional` to `common` because Omarchy 4 writes the early-KMS drop-in on every NVIDIA machine at install and configures `resume=` itself, so this is the default state of an Omarchy NVIDIA box rather than an unusual configuration. Severity stays `medium`: the machine boots and only the unsaved session is lost. Not exercised: I have no sudo and was instructed not to hibernate or touch the initramfs, so I did not rebuild, did not delete the drop-in, and did not observe a hibernate resume either failing or succeeding. The `PreserveVideoMemoryAllocations=0` branch is reported behaviour from #8126 and I did not test it.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** You are rebuilding the initramfs and rewriting the UKI on the ESP. Omarchy 4 builds no fallback initramfs entry, so the record's old advice to boot one points at nothing: `MKINITCPIO_FALLBACK` is left commented out in `/etc/limine-entry-tool.conf` and is set nowhere in `/etc/limine-entry-tool.d/` or `/etc/default/limine`, and `limine-list` shows one kernel entry plus Snapshots plus the Limine binary's own EFI fallback, which is not a kernel. If the machine black-screens before Hyprland, recovery is a Limine btrfs snapshot entry, so run `limine-list` beforehand to see which exist, or a chroot from the Omarchy ISO to restore `/etc/mkinitcpio.conf.d/nvidia.conf` and re-run `limine-mkinitcpio`. Testing the fix means hibernating, and a failed resume discards everything that was open, so do it from a session with nothing unsaved. On a plain Arch install with `mkinitcpio -P` and a `linux-fallback` preset the fallback entry does exist and is the right recovery there.

**Fix.**

Drop early module loading. `nvidia_drm modeset=1` from `/etc/modprobe.d/nvidia.conf` still applies with a late load, so only the early load goes.

**Omarchy 4:**

```bash
sudo rm /etc/mkinitcpio.conf.d/nvidia.conf
sudo limine-mkinitcpio
```

Use `limine-mkinitcpio`, not `mkinitcpio -P`. Omarchy 4 keeps `/etc/mkinitcpio.d/` empty and builds a UKI at `/boot/EFI/Linux/omarchy_linux.efi`, so `mkinitcpio -P` stops with `ERROR: No presets found in /etc/mkinitcpio.d`.

Two Omarchy-specific consequences the plain Arch advice does not have:

- `/usr/share/omarchy/install/hardware/nvidia.sh` recreates that drop-in unconditionally with `cat >`. Running `omarchy apply hardware`, or `omarchy-apply-system` which calls it, puts early KMS straight back. Re-run the two commands above after any such reapply. A routine `omarchy update` does not call it.
- `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` drops the `kms` hook only while `nvidia_drm` is present in `MODULES`. With the drop-in gone that test is false, `kms` stays in `HOOKS`, and `autodetect` pulls `nouveau` and its GSP firmware into the image. `nouveau` is blacklisted by `/usr/lib/modprobe.d/nvidia-utils.conf` so it will not take the GPU, but the image grows by roughly 100 MB, which the upstream comment in that drop-in calls out.

**Plain Arch and other Arch derivatives:** the modules are usually in `MODULES=(...)` in `/etc/mkinitcpio.conf` itself, or in a distribution drop-in under `/etc/mkinitcpio.conf.d/`. Remove `nvidia nvidia_modeset nvidia_uvm nvidia_drm` from wherever they are set, then rebuild:

```bash
sudo mkinitcpio -P
```

Keep `/etc/modprobe.d/nvidia.conf` with `options nvidia_drm modeset=1` in both cases. Reboot and re-test hibernate.

If early KMS is what is holding your display up and you will not give it up, the other side of the trade is to turn preservation off and accept losing video memory contents across a sleep:

```bash
printf 'options nvidia NVreg_PreserveVideoMemoryAllocations=0\n' | sudo tee /etc/modprobe.d/zz-nvidia-no-preserve.conf
sudo limine-mkinitcpio
```

The `zz-` prefix matters, because modprobe sorts its config files by name and the last `options` line for a parameter wins, so anything sorting before `gsr-nvidia.conf` would be ignored. Omarchy users report corrupted GPU state after resume in that configuration (`NVRM: Xid ... 13, Graphics Exception` across the compositor, the shell and the browser, in omacom/omarchy#8126), so treat it as a trade, not a fix. You cannot have working suspend-with-preservation and working hibernate on the same early-KMS machine.

**Verify.** **Omarchy 4:**

```bash
ls /etc/mkinitcpio.conf.d/nvidia.conf                              # No such file or directory
sudo lsinitcpio /boot/EFI/Linux/omarchy_linux.efi | grep nvidia    # returns nothing
sudo cat /sys/module/nvidia_drm/parameters/modeset                 # still Y
```

All three need root. `/boot` is a vfat ESP mounted `dmask=0077` so an ordinary user cannot even list it, and `/sys/module/nvidia_drm/parameters/modeset` is mode `0400`. `lsinitcpio` 41.1 detects a UKI and unpacks it with `objcopy`, so pointing it at the `.efi` works. There is no `/boot/initramfs-linux.img` on Omarchy 4.

**Plain Arch:**

```bash
sudo lsinitcpio /boot/initramfs-linux.img | grep nvidia            # returns nothing
sudo cat /sys/module/nvidia_drm/parameters/modeset                 # still Y
```

Then `systemctl hibernate` from a session you can afford to lose, and on power-on your windows are back where they were.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks> · <https://github.com/omacom/omarchy/issues/8126> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/nvidia.sh>

---

## Fix Electron/Chromium apps stalling for a minute after boot on hybrid Intel+NVIDIA

`igpu-electron-stall-i915-module-order` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** On an Intel iGPU + NVIDIA dGPU laptop, the first launch of VS Code, Discord, Chromium etc. after boot hangs for up to a minute with a blank window before it finally appears. Later launches are fine.

**Cause.** Electron and CEF apps stall on their first launch after boot on Intel plus NVIDIA hybrid machines when the NVIDIA modules are loaded from the initramfs ahead of `i915`. Loading `i915` first clears it. That is exactly what the Hyprland NVIDIA wiki page documents, in the warning box under "Early KMS, modeset and fbdev". Neither that page nor the Arch NVIDIA page explains why the order matters, and the Arch page does not mention `i915` at all, so treat the ordering as an observed fix rather than an explained one.

On Omarchy 4 every hybrid machine starts in the bad order by default. `/usr/share/omarchy/install/hardware/nvidia.sh` writes `/etc/mkinitcpio.conf.d/nvidia.conf` containing `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` on any machine with an NVIDIA card, and `/etc/mkinitcpio.conf` ships stock with `MODULES=()`, so the NVIDIA modules are the first entries in the assembled list and nothing puts `i915` before them.

> **Audit corrected this record.** Checked against both cited pages fetched in full and against this omarchy 4.0.2-1 workstation (mkinitcpio 41.1-1, limine-mkinitcpio-hook 1.37.1-1, kernel 7.1.9-arch1-2). The symptom and the ordering fix are real and supported: the Hyprland NVIDIA page carries a warning box under "Early KMS, modeset and fbdev" stating that Electron or Chromium apps can stall for up to a minute after boot on Intel iGPU plus NVIDIA dGPU systems and that loading `i915` before the NVIDIA modules fixes it. The second cited source does not support the claim. I fetched `https://wiki.archlinux.org/index.php?title=NVIDIA&action=raw`, 626 lines, and `i915` appears zero times in it. It is kept on the record because it does support the surrounding mechanism, early module loading into the initramfs, and is the source of the hibernation caveat, but the ordering claim rests on the Hyprland page alone. Rewrote the cause to say that plainly: neither page gives a mechanism, so the record's original invented explanation about Electron enumerating the NVIDIA device first and blocking on it is unsourced and has been removed.

Four Omarchy 4 defects in the fix and its surroundings, all confirmed on this machine.

First, the fix did `sudo tee /etc/mkinitcpio.conf.d/nvidia.conf`, which overwrites a file Omarchy owns. `/usr/share/omarchy/install/hardware/nvidia.sh:30` writes that exact path with `cat >` and the file here holds exactly `MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)`. `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, owned by omarchy-settings 4.0.2-1, carries a comment naming nvidia.conf as sourced before it and reads `MODULES` to decide whether to drop the `kms` hook. Replaced that with a new drop-in, `/etc/mkinitcpio.conf.d/00-i915.conf` holding `MODULES+=(i915)`, which sorts ahead of `nvidia.conf` and leaves Omarchy's file alone. The sort order is confirmed from mkinitcpio source at `/usr/bin/mkinitcpio:1120`, which builds the drop-in list with `find ... -name '*.conf' -print0 | sed -z 's/.*\///' | LC_ALL=C.UTF-8 sort -zVu` and then `cat`s each onto the main config.

Second, `sudo mkinitcpio -P` fails here. `/etc/mkinitcpio.d/` is empty, and `/usr/bin/mkinitcpio:986` reads `[[ -e "${_optpreset[0]}" ]] || die 'No presets found in %s' "$_d_presets"`. There is also a shim: `/usr/local/bin/mkinitcpio`, owned by limine-mkinitcpio-hook, is first on `PATH` and, on `-P` or `-p`, prints a warning that Limine entries were not updated and offers to run `limine-mkinitcpio`. The supported rebuild is `sudo limine-mkinitcpio`, which is what Omarchy's own migrations call.

Third, `verify` named `/boot/initramfs-linux.img`, which does not exist on Omarchy 4. `/etc/limine-entry-tool.d/omarchy-uki.conf` sets `ENABLE_UKI=yes` and `omarchy-defaults.conf` sets `CUSTOM_UKI_NAME="omarchy"`, and `/usr/share/libalpm/scripts/limine-mkinitcpio-install:95` builds `UKI_PATH="${BOOT_PATH}/EFI/Linux/${UKI_PREFIX}_${KERNEL_NAME}.efi"`, so the image is `/boot/EFI/Linux/omarchy_linux.efi`. Replaced the primary check with `journalctl -b -k -o short-monotonic | grep -iE 'i915|nvidia'`, which I ran here as an unprivileged user and which does show the nvidia load sequence with monotonic timestamps. The `objcopy` extraction is offered as a secondary check and was NOT exercised, because `/boot` is `dmask=0077` and I have no sudo.

Fourth, the `danger` promised a fallback boot entry that does not exist on Omarchy 4. `grep -rn MKINITCPIO_FALLBACK` across `/etc/limine-entry-tool.d/`, `/etc/default/limine` and `/usr/share/omarchy` returns nothing, and `limine-list` on this machine prints `Omarchy` with one child `linux`, a `Snapshots` submenu with two entries, and a trailing `EFI fallback`. That last line is the `EFI/BOOT/BOOTX64.EFI` bootloader fallback from `ENABLE_LIMINE_FALLBACK=yes`, not a fallback initramfs. Rewrote the danger around the Snapshots submenu, which is the real recovery path, and kept the hibernation caveat both wiki pages give for early-loading NVIDIA modules.

Left severity `medium` and frequency `occasional` alone. The consequence is a slow first launch, not a broken machine, and it only reaches Intel plus NVIDIA hybrid laptops.

Not exercised: this is a single-GPU NVIDIA RTX 3090 desktop with no Intel iGPU, so the stall itself, the `i915` load and the corrected drop-in could not be reproduced or tested. Nothing on this machine was modified, no initramfs was rebuilt, and `mkinitcpio` was read rather than run. The drop-in ordering, the preset failure and the UKI path are read from installed files and package scripts here, not from a live rebuild.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** This rebuilds the initramfs, so a typo in the `MODULES` array can leave the machine unbootable.

Omarchy 4 has no fallback kernel entry to fall back on. `MKINITCPIO_FALLBACK` is not set in `/etc/limine-entry-tool.conf`, in `/etc/limine-entry-tool.d/` or in `/etc/default/limine`, so no `linux-fallback` image is built. The `EFI fallback` line in the Limine menu is the `EFI/BOOT/BOOTX64.EFI` bootloader fallback from `ENABLE_LIMINE_FALLBACK=yes` and is not a second kernel entry.

Your recovery route is the `Snapshots` submenu in the Limine menu, from `limine-snapper-sync`. Confirm there is a recent snapshot before you rebuild:

```bash
limine-list
```

If there is none, boot the Omarchy ISO and chroot to repair. Adding only `i915` is low risk in itself, because the NVIDIA modules were already early-loaded by Omarchy's own drop-in, so this changes order rather than content.

Separately, early-loading the NVIDIA modules at all, which Omarchy does by default on every machine with an NVIDIA card, is documented by both the Arch NVIDIA page and the Hyprland NVIDIA page as breaking resume from hibernation. This record does not change that either way, but Omarchy also ships `/etc/mkinitcpio.conf.d/omarchy_resume.conf` with `HOOKS+=(resume)`, so hibernation is configured and may already be affected.

**Fix.**

Get `i915` into the initramfs `MODULES` list ahead of the NVIDIA modules.

**Omarchy 4.** Do not edit `/etc/mkinitcpio.conf.d/nvidia.conf`. Omarchy's installer owns that file and rewrites it wholesale with `cat >`, and `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` reads `MODULES` after it to decide whether to drop the `kms` hook. Add a separate drop-in that sorts ahead of it. mkinitcpio 41 concatenates `/etc/mkinitcpio.conf.d/*.conf` onto `/etc/mkinitcpio.conf` in `sort -V` order, so a filename starting with a digit lands first:

```bash
printf 'MODULES+=(i915)\n' | sudo tee /etc/mkinitcpio.conf.d/00-i915.conf
```

Check the assembled order before rebuilding. Read the files top to bottom in the order below and confirm `i915` appears ahead of `nvidia`:

```bash
for f in /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf; do
  printf '== %s\n' "$f"
  grep -H MODULES "$f"
done
```

Then rebuild and reboot:

```bash
sudo limine-mkinitcpio
reboot
```

`sudo mkinitcpio -P` is wrong on Omarchy 4 and will not work. `/etc/mkinitcpio.d/` is empty, so `/usr/bin/mkinitcpio` exits with `No presets found in /etc/mkinitcpio.d`, and `/usr/local/bin/mkinitcpio`, shipped by `limine-mkinitcpio-hook`, shadows the real binary on `PATH` and prompts to run `limine-mkinitcpio` for you instead of failing cleanly. Omarchy boots a unified kernel image that only `limine-mkinitcpio` rebuilds and re-registers.

**Plain Arch**, where `MODULES` normally lives in `/etc/mkinitcpio.conf` itself. Edit that line so `i915` comes first:

```
MODULES=(i915 nvidia nvidia_modeset nvidia_uvm nvidia_drm)
```

```bash
sudo mkinitcpio -P
reboot
```

That branch does not apply on Omarchy 4, where `/etc/mkinitcpio.conf` is package-stock and unmodified with `MODULES=()`. Confirmed with `pacman -Qkk mkinitcpio`, which reports 103 files and 0 altered.

**Verify.** After a reboot the first cold launch of an Electron app returns promptly:

```bash
time chromium --version
```

Check the order the kernel actually took. This works on Omarchy 4 and on plain Arch, and needs no root:

```bash
journalctl -b -k -o short-monotonic | grep -iE 'i915|nvidia' | head
```

`i915` should initialise before the `nvidia`, `nvidia-modeset` and `nvidia-drm` lines.

On Omarchy 4 do not reach for `lsinitcpio /boot/initramfs-linux.img`. That file does not exist. `/etc/limine-entry-tool.d/omarchy-uki.conf` sets `ENABLE_UKI=yes` and `/etc/limine-entry-tool.d/omarchy-defaults.conf` sets `CUSTOM_UKI_NAME="omarchy"`, so the boot image is the unified `/boot/EFI/Linux/omarchy_linux.efi`, and `/boot` is a vfat ESP mounted `dmask=0077` so an ordinary user cannot even list it. To read the bundled initramfs, pull it out of the UKI first, which needs `binutils`:

```bash
sudo objcopy -O binary --only-section=.initrd /boot/EFI/Linux/omarchy_linux.efi /tmp/initrd
lsinitcpio /tmp/initrd | grep -E 'i915|nvidia'
```

On plain Arch with a separate initramfs image, `lsinitcpio /boot/initramfs-linux.img | grep -E 'i915|nvidia'` still works.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.archlinux.org/title/NVIDIA>

---

## Screen recording never starts on a Pascal NVIDIA card: 'Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0'

`screenrecord-nvenc-api-13-1-required-pascal-580xx` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `desktop`, `ffmpeg`, `gpu-screen-recorder`, `hyprland`, `kdenlive`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** `omarchy screenrecord` (every variant: fullscreen, region, with or without audio or webcam) does nothing. The bar's recording indicator never turns on and no file appears in `~/Videos`. With `OMARCHY_SCREENRECORD_DEBUG=true` set, `/tmp/omarchy-screenrecord.log` ends with:

```
gsr info: using h264 encoder because a codec was not specified
[h264_nvenc @ 0x557b3650a880] ignoring invalid SAR: 0/0
[h264_nvenc @ 0x557b3650a880] Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0
[h264_nvenc @ 0x557b3650a880] The minimum required Nvidia driver for nvenc is 610.00 or newer
gsr error: Could not open video codec: Function not implemented
```

Reported on Omarchy 4.0.0-1 with a GeForce GTX 1070 Ti on `nvidia-580xx-dkms 580.178.04` and `gpu-screen-recorder 6.0.0-1`. A second reporter hit the same two `h264_nvenc` lines from Kdenlive's NVENC export presets on a Quadro P1000 with the same driver, and the same message comes from any program that encodes through the system `ffmpeg`.

**Cause.** Named by the gpu-screen-recorder author in the thread and checked against ffmpeg's own source. ffmpeg 9.0 is built against nv-codec-headers that declare NVENC API 13.1, and `libavcodec/nvenc.c` refuses to open the encoder when the driver reports a lower maximum version, returning `AVERROR(ENOSYS)`, which surfaces as `Could not open video codec: Function not implemented`. The same function maps API 13.1 to a minimum driver of 610.00, which is where that second log line comes from. Pascal cards (GTX 10 series, Quadro P series) are stuck on the legacy `nvidia-580xx` branch, which reports API 13.0 only, and that branch is packaged in the AUR rather than in Arch's repositories, while `extra/nvidia-utils` is 610.57.04 and does not cover Pascal. `omarchy-capture-screenrecording` passes `-fallback-cpu-encoding yes` to `gpu-screen-recorder` (line 191 of the script, identical on this machine, at tag v4.0.3 and on `quattro`), but before 6.0.1 that option only checked whether the GPU supports NVENC, not whether ffmpeg accepts the driver's API version, so the recorder died opening the codec instead of falling back to software encoding. The author added an ffmpeg NVENC version check in gpu-screen-recorder 6.0.1 so the fallback fires. He also described making the `-Dffmpeg_static=true` build option (a bundled ffmpeg patched to negotiate the NVENC API at runtime) the default, but that is not what Arch ships: the upstream README still documents the option as disabled by default, and Arch's PKGBUILD for 6.1.1 passes `-Dffmpeg_static=false` and links the system ffmpeg. So on Omarchy the recording falls back to the CPU rather than regaining NVENC. Programs that use the system ffmpeg, such as Kdenlive, mpv and OBS, are not helped by either change.

> **Audit corrected this record.** Re-read issue omacom/omarchy#7217 in full with all five comments today, and it supports the record. The reporter's debug log carries both `h264_nvenc` lines and `gsr error: Could not open video codec: Function not implemented` on a GTX 1070 Ti with `nvidia-580xx-dkms 580.178.04` and `gpu-screen-recorder 6.0.0-1`, the recorder's author (dec05eba) states that ffmpeg 9.0 raised the minimum NVENC version to 13.1 and that he added the ffmpeg version check in 6.0.1, and ritechoice23 reproduces the identical two lines out of Kdenlive through the system `ffmpeg 2:9.0.1-1` on a Quadro P1000. I verified the mechanism in ffmpeg's source rather than accepting it from the thread: `libavcodec/nvenc.c` on `release/9.0` compares `NVENCAPI_MAJOR_VERSION`/`NVENCAPI_MINOR_VERSION` against the driver's reported maximum, logs exactly the `Driver does not support the required nvenc API version` line and returns `AVERROR(ENOSYS)`, and its `nvenc_print_driver_requirement` maps API 13.1 to minimum driver 610.00. nv-codec-headers declares `NVENCAPI_MAJOR_VERSION 13` and `NVENCAPI_MINOR_VERSION 1`, which is what ffmpeg 9 is built against. Confirmed on this machine: line 191 of `/usr/share/omarchy/bin/omarchy-capture-screenrecording` passes `-fallback-cpu-encoding yes` and is byte-identical at tag v4.0.3 and at `quattro` HEAD, the script exposes no way to inject extra recorder arguments (only `OMARCHY_SCREENRECORD_DIR`, `OMARCHY_SCREENRECORD_USE_PORTAL` and `OMARCHY_SCREENRECORD_DEBUG`), `omarchy screenrecord` is a real alias declared in the script header, the debug log path `/tmp/omarchy-screenrecord.log` is the one the script writes, and `gpu-screen-recorder --help` on the installed 6.0.1-1 lists `-w`, `-encoder gpu|cpu`, `-fallback-cpu-encoding yes|no`, `-f` and `-o`, so the workaround command is valid as written. Two claims were wrong. The record says the author made `-Dffmpeg_static=true` the default for later releases, but the upstream README fetched today still documents that option as disabled by default and Arch's PKGBUILD for 6.1.1 passes `-Dffmpeg_static=false`, so no Arch or Omarchy package restores NVENC on Pascal and the CPU fallback is the only relief. And the version history is stale: `extra` shipped 6.0.1-1 on 2026-08-20, 6.0.2-1 on 2026-08-29, 6.1.0-1 on 2026-09-01 rather than 2026-09-02, and 6.1.1-1 on 2026-09-10, which is what `extra` carries now (this workstation still has 6.0.1-1). The Pascal driver claim holds and is now cited: the Arch wiki driver table puts Maxwell, Pascal and Volta on AUR `nvidia-580xx-dkms`, marked legacy and supported. Not exercised: this workstation runs `nvidia-open-dkms 610.57.04`, so the API floor cannot be hit here and neither the failure nor the CPU fallback was reproduced.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

1. Check the recorder version. 6.0.1 or newer carries the fallback fix, so recording starts and encodes on the CPU instead of failing outright. On Omarchy 4 update through the supported path:

```bash
pacman -Q gpu-screen-recorder    # 6.0.0-1 is affected, 6.0.1-1 or newer has the fallback
omarchy update
```

On plain Arch, `sudo pacman -Syu`. Arch's `extra` repository shipped 6.0.1-1 on 2026-08-20, 6.0.2-1 on 2026-08-29, 6.1.0-1 on 2026-09-01 and 6.1.1-1 on 2026-09-10. No Arch build gives a Pascal card NVENC back: the PKGBUILD passes `-Dffmpeg_static=false`, so the package uses the system ffmpeg 9 and its API 13.1 floor still applies. The CPU fallback is the whole of the relief available here.

2. Until the update lands, or if it still fails, force software encoding when calling the recorder directly. The Omarchy wrapper has no option for this, so run `gpu-screen-recorder` yourself. Replace `DP-2` with your monitor name from `hyprctl monitors`:

```bash
gpu-screen-recorder -w DP-2 -encoder cpu -f 60 -o ~/Videos/recording.mp4
# stop with Ctrl+C, or from another terminal:
pkill -SIGINT -f gpu-screen-recorder
```

The reporter confirmed `-encoder cpu` produces a valid clip on the same card and driver.

3. Kdenlive, mpv, OBS and anything else that uses the system `ffmpeg` cannot use NVENC on a Pascal card with ffmpeg 9 at all. Pick a software encoder (x264 or x265) in those programs. No driver available through Arch changes this: the Arch wiki's driver table puts Maxwell, Pascal and Volta on the AUR `nvidia-580xx-dkms` branch, and the newer `extra/nvidia-utils` 610.57.04 that reports API 13.1 does not support those cards.

**Verify.** ```bash
pacman -Q gpu-screen-recorder            # 6.0.1-1 or newer
OMARCHY_SCREENRECORD_DEBUG=true omarchy screenrecord --fullscreen
```

The bar's recording indicator turns on, a file appears in `~/Videos`, and `/tmp/omarchy-screenrecord.log` no longer contains `Could not open video codec`.

Sources: <https://github.com/omacom/omarchy/issues/7217> · <https://git.dec05eba.com/gpu-screen-recorder/plain/README.md> · <https://archlinux.org/packages/extra/x86_64/gpu-screen-recorder/> · <https://gitlab.archlinux.org/archlinux/packaging/packages/gpu-screen-recorder/-/raw/main/PKGBUILD> · <https://archive.archlinux.org/packages/g/gpu-screen-recorder/> · <https://raw.githubusercontent.com/FFmpeg/FFmpeg/release/9.0/libavcodec/nvenc.c> · <https://raw.githubusercontent.com/FFmpeg/nv-codec-headers/master/include/ffnvcodec/nvEncodeAPI.h> · <https://wiki.archlinux.org/title/NVIDIA> · <https://archlinux.org/packages/extra/x86_64/ffmpeg/> · <https://archlinux.org/packages/extra/x86_64/nvidia-utils/>

---

## Fix 'vaInitialize failed' in screen recording and hardware video decode

`vaapi-init-failed-screen-recording` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Hardware video playback falls back to software, or a screen recording comes out CPU-encoded with dropped frames and high CPU use. `vainfo` errors with:

```
libva: /usr/lib/dri/<driver>_drv_video.so init failed
```

On Omarchy the recorder's own stderr is hidden unless you turn logging on. With `OMARCHY_SCREENRECORD_DEBUG=true` set, `/tmp/omarchy-screenrecord.log` shows:

```
gsr_get_supported_video_codecs_vaapi: vaInitialize failed
```

On Omarchy 3 this produced no file at all. On Omarchy 4 `omarchy-capture-screenrecording` passes `-fallback-cpu-encoding yes` to `gpu-screen-recorder`, so a VA-API failure usually yields a software-encoded file rather than nothing.

**Cause.** No usable VA-API driver is installed for the GPU that is actually driving the display, or the wrong one is being picked. On hybrid Intel plus NVIDIA laptops VA-API tries the first device it finds, and if only one vendor's driver is installed initialisation fails.

On Omarchy 4 the plain missing-driver case is mostly closed, because `install/hardware/intel/video-acceleration.sh` and `install/hardware/nvidia.sh` install the driver by detected hardware at install time. Two gaps remain. Those scripts run only during installation and `omarchy update` does not re-run them, so a GPU added later is not covered. And the Intel name match in `video-acceleration.sh` tests for `hd graphics`, `uhd graphics`, `xe`, `iris`, `arc` and `panther lake`, which the Haswell and Ivy Bridge generations do not match, so those machines finish an install with no VA-API driver.

The wrong-driver case is now the more common one on Omarchy 4, and it is usually not the user's doing. See the `danger` below.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation (kernel 7.1.9, mesa 1:26.2.1-1, nvidia-utils 610.57.04-1, gpu-screen-recorder 6.0.1-1) and against the two cited sources and the upstream tree at tag v4.0.3. What held: the symptom string is real, `strings /usr/bin/gpu-screen-recorder` on this machine contains `gsr_get_supported_video_codecs_vaapi: vaInitialize failed` verbatim. Issue 2706 is open and genuinely supports the symptom and the hybrid cause, and its most recent comment is a Haswell `8086:0416` machine on Omarchy 4.0.1-1 fixed by installing `libva-intel-driver` by hand. The Arch wiki supports the Intel generation split at Broadwell, the `iHD`, `i965` and `radeonsi` values and `vainfo --display drm`. I confirmed here that `mesa` owns `/usr/lib/dri/radeonsi_drv_video.so` and that `libva-utils` is not installed by Omarchy, so the `vainfo` step is genuinely needed.

Four things were wrong for Omarchy 4. First, `~/.config/hypr/envs.conf` does not exist and nothing in `/usr/share/omarchy` reads it, confirmed by `grep -rn envs.conf /usr/share/omarchy` returning nothing and by this machine's `~/.config/hypr/` holding only Lua files. That is the Omarchy 3 path. Second, the claim that setting `NVD_BACKEND` is "what Omarchy's installer does" is false on Omarchy 4. I read `/usr/share/omarchy/install/hardware/nvidia.sh` here and at tag v4.0.3: it sets no environment at all and carries the comment `Per-session Hyprland NVIDIA env vars are handled by default/hypr/nvidia.lua`, and that Lua file sets `NVD_BACKEND` and `LIBVA_DRIVER_NAME` itself. The cited `master` URL does resolve and does contain the `envs.conf` writing code, which is why the claim was true when written, so I kept that source and labelled it as the Omarchy 3 branch instead of removing it. Third, the package list is mostly noise on Omarchy 4 and omits what Omarchy actually installs: `video-acceleration.sh` installs `intel-media-driver libvpl vpl-gpu-rt`, which the record never mentions, and `linux-firmware-intel` is a dependency of `linux-firmware` on this machine (`Required By: linux-firmware`), so installing it is a no-op rather than a step. Fourth, the symptom is stale: `omarchy-capture-screenrecording` line 191 passes `-fallback-cpu-encoding yes` and sends stderr to `/dev/null` unless `OMARCHY_SCREENRECORD_DEBUG=true`, so "no file at all" and "running the recorder from a terminal shows" are both Omarchy 3 behaviour.

I rewrote `danger` because it blamed the user for forcing `LIBVA_DRIVER_NAME=nvidia`, which on Omarchy 4.0.1 and later is what Omarchy does by default on any Turing-or-newer machine. Overlap with neighbouring records: `screenrecord-nvenc-api-13-1-required-pascal-580xx` covers the NVENC API 13.1 mismatch on Pascal, which is the encoder failing to open with the driver present, a different failure from VA-API never initialising, so the line between them is driver-missing versus codec-open-refused and I left that record's territory alone. The hybrid-laptop environment case belongs to `nvidia-env-forced-on-igpu-primary-hybrid-laptop` and I point at it rather than duplicating it.

I dropped `frequency` from `very-common` to `occasional`, because Omarchy 4's installer now covers Intel Broadwell and newer, AMD through mesa and NVIDIA, leaving only the Haswell-era name-match gap and the wrong-driver case. Not exercised: I did not start a screen recording, did not run `vainfo` (`libva-utils` is not installed and I have no sudo), and this workstation is NVIDIA-only, so I could not test the hybrid path or the Haswell name-match failure on real hardware. The Haswell gap is read from the shipped script plus the issue reporter's confirmation, not reproduced here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** On Omarchy 4.0.1 and later you do not have to force `LIBVA_DRIVER_NAME=nvidia` to hit the hybrid-laptop trap, because Omarchy sets it for you. `/usr/share/omarchy/default/hypr/nvidia.lua` sets it on any machine carrying a Turing or newer NVIDIA card, whether or not that card renders or scans out anything, and `default/hypr/autostart.lua` exports it session-wide. On a hybrid laptop whose panel runs on the Intel or AMD iGPU that routes every VA-API client through the NVIDIA card and corrupts browser video, and it also costs you the iGPU's hardware encode, because `libva-nvidia-driver` is an NVDEC decode adapter. Set the driver of the GPU that actually renders the session, not the one that merely exists. The full diagnosis, including how to tell which render node the compositor holds, is the record `nvidia-env-forced-on-igpu-primary-hybrid-laptop`. The Arch wiki adds a separate warning that `libva-nvidia-driver` with default settings can draw more power than CPU decoding.

**Fix.**

**On Omarchy 4, find out what is already installed before installing anything.** Omarchy's installer picks VA-API drivers by hardware, so on most machines the driver is already there and a missing driver is not your problem:

```bash
pacman -Q intel-media-driver libva-intel-driver libva-nvidia-driver mesa 2>&1
ls /usr/lib/dri/*_drv_video.so
```

`/usr/share/omarchy/install/hardware/intel/video-acceleration.sh` installs `intel-media-driver libvpl vpl-gpu-rt` when the Intel GPU name matches `hd graphics`, `uhd graphics`, `xe`, `iris`, `arc` or `panther lake`, and `libva-intel-driver` when it matches `gma`. `/usr/share/omarchy/install/hardware/nvidia.sh` installs `libva-nvidia-driver` on GSP-capable cards. `mesa` supplies `radeonsi_drv_video.so` for AMD and is always present.

**Two Omarchy 4 gaps leave a machine with no driver.** Both scripts run only at install time and `omarchy update` never re-runs them. And the Intel name match misses the Haswell and Ivy Bridge generations, whose `lspci` name is `4th Gen Core Processor Integrated Graphics Controller` with no `hd graphics` in it, so those machines get nothing. That is the case reported on omarchy#2706 from a Haswell `8086:0416` laptop running Omarchy 4.0.1-1, fixed by installing `libva-intel-driver` by hand.

Get `vainfo`, which Omarchy does not ship:

```bash
sudo pacman -S --needed libva-utils
vainfo
```

Then install the driver for your hardware. On a hybrid machine install both vendors' drivers:

```bash
# Intel Broadwell (2014) and newer, including Arc:
sudo pacman -S --needed intel-media-driver libvpl vpl-gpu-rt
# Intel GMA 4500 (2008) through Coffee Lake, and the Haswell generation above:
sudo pacman -S --needed libva-intel-driver
# AMD: VA-API comes from mesa (radeonsi), which is already installed
pacman -Q mesa
# NVIDIA proprietary (NVDEC through VA-API):
sudo pacman -S --needed libva-nvidia-driver
```

`linux-firmware-intel` is a dependency of `linux-firmware`, so it is already installed on any Arch or Omarchy machine. Check rather than install it:

```bash
pacman -Q linux-firmware-intel
```

None of these commands is blocked by Omarchy's ALPM guard, which aborts only a transaction carrying both `-S` and `-u`. Never write `pacman -Sy libva-utils`, which is a partial upgrade.

**Pinning the driver, if autodetection picks the wrong one.** `LIBVA_DRIVER_NAME` values are `iHD` for `intel-media-driver`, `i965` for `libva-intel-driver`, `radeonsi` for AMD and `nvidia` for `libva-nvidia-driver`.

On **Omarchy 4** there is no `~/.config/hypr/envs.conf`. That file was the Omarchy 3 location and nothing on Omarchy 4 reads it. `~/.config/hypr/envs.lua` is not read either. Put the override in `~/.config/hypr/hyprland.lua`, **below** the `require("default.hypr.omarchy")` line, so it loads after Omarchy's defaults and wins:

```lua
-- ~/.config/hypr/hyprland.lua, below require("default.hypr.omarchy")
hl.env("LIBVA_DRIVER_NAME", "iHD")
```

Then log out and back in. `hyprctl reload` alone is not enough, because `default/hypr/autostart.lua` runs `systemctl --user import-environment` at session start and apps launched through systemd user scopes keep the old value.

On **plain Arch** with a `hyprland.conf`, use the old syntax:

```
env = LIBVA_DRIVER_NAME,iHD
```

**On NVIDIA, Omarchy 4 already sets the environment and you should not repeat it.** `/usr/share/omarchy/install/hardware/nvidia.sh` sets no environment variables at all and says so in a comment. `/usr/share/omarchy/default/hypr/nvidia.lua` sets `NVD_BACKEND=direct`, `LIBVA_DRIVER_NAME=nvidia` and `__GLX_VENDOR_LIBRARY_NAME=nvidia` on Turing and newer, and `NVD_BACKEND=egl` on Maxwell, Pascal and Volta. Omarchy 3 wrote those same values into `~/.config/hypr/envs.conf` from the installer, which is where the older advice comes from.

If `vainfo` cannot connect at all on a headless or secondary GPU, force the DRM display:

```bash
vainfo --display drm
```

**To see why an Omarchy recording failed**, the wrapper sends `gpu-screen-recorder` stderr to `/dev/null` unless you ask for it:

```bash
OMARCHY_SCREENRECORD_DEBUG=true omarchy-capture-screenrecording --fullscreen
cat /tmp/omarchy-screenrecord.log
```

**Verify.** `vainfo` lists profiles and entrypoints with no `init failed` line. `ls /usr/lib/dri/*_drv_video.so` shows the driver you expect. Start a recording, then confirm a file appears in `~/Videos` and that `/tmp/omarchy-screenrecord.log` under `OMARCHY_SCREENRECORD_DEBUG=true` names a hardware encoder such as `h264_vaapi` rather than falling back to the CPU. `nvtop` or `intel_gpu_top` shows the DEC or ENC engine above zero during playback.

Sources: <https://github.com/basecamp/omarchy/issues/2706> · <https://wiki.archlinux.org/title/Hardware_video_acceleration> · <https://github.com/basecamp/omarchy/blob/master/install/config/hardware/nvidia.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/hardware/nvidia.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/hardware/intel/video-acceleration.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/default/hypr/nvidia.lua> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-capture-screenrecording> · <https://archlinux.org/packages/core/any/linux-firmware-intel/> · <https://archlinux.org/packages/extra/x86_64/libva-utils/>

---

## Install the Vulkan ICD when an app silently refuses to launch

`vulkan-driver-missing-app-fails-to-start` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** An application that uses Vulkan (Zed, some Electron builds, games, `vkcube`) fails to start on a fresh install with no useful message, or exits immediately. `vulkaninfo` errors out or lists no physical devices.

**Cause.** The Vulkan ICD loader is installed but no vendor Vulkan driver is, so the loader finds no physical device and the application exits.

**On Omarchy 4 this gap is closed at install time.** `/usr/share/omarchy/install/hardware/vulkan.sh` reads `lspci` and installs `vulkan-intel`, `vulkan-radeon` or `vulkan-asahi` for each detected vendor, and `install/hardware/nvidia.sh` installs `nvidia-utils`, which carries the NVIDIA ICD. Issue 1441, which reported Zed failing to launch on a fresh Intel install, is closed and that script is what closed it.

Three cases still reach this record on Omarchy 4. The hardware scripts run only during installation and `omarchy update` does not re-run them, so a GPU added after install is not covered. The vendor match is `lspci | grep -iE "(VGA|Display).*(Intel|AMD|Apple)"`, so a device that reports neither a `VGA compatible controller` nor a `Display controller` class, or that names its vendor differently, is skipped. And 32-bit Vulkan for Steam, Proton and Wine is a separate set of packages that the install-time script does not touch.

On **plain Arch, EndeavourOS and Manjaro** the original cause stands as written: installing `vulkan-icd-loader` alone gives you no driver.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation against both cited sources and the upstream tree at tag v4.0.3. What held: the Arch wiki's Vulkan page supports every generic claim in the record, the `vulkan-icd-loader` plus vendor driver split, `vulkan-tools` being where `vulkaninfo` and `vkcube` live, `ls /usr/share/vulkan/icd.d/` as the check, and `MESA_VK_DEVICE_SELECT` requiring `vulkan-mesa-implicit-layers` with a trailing `!` to enforce. Every package the record names still exists: I queried the Arch package JSON API for each one and all resolved, `vulkan-mesa-implicit-layers` at 26.2.2-1 in extra included. I confirmed on this machine that `vulkan-tools` is not installed (no `vulkaninfo` or `vkcube` on PATH), so that step is genuinely needed on Omarchy.

The cause is wrong for Omarchy 4 and that is the substance of this verdict. The record says the missing vendor driver is "a very common gap on Intel iGPU laptops". Issue 1441 is CLOSED, and reading it in full shows why: it is the thread where contributors proposed an auto-detecting installer script, and Omarchy 4 now ships it. I read `/usr/share/omarchy/install/hardware/vulkan.sh` here and fetched it at tag v4.0.3, and the two are identical. It installs `vulkan-intel`, `vulkan-radeon` or `vulkan-asahi` per detected vendor, `install/hardware/nvidia.sh` installs `nvidia-utils` for the NVIDIA ICD, and `install/hardware/all.sh` calls both. So this is sound generic Arch advice mis-specialised to Omarchy, exactly the shape the brief warns about. I rewrote the cause to branch Omarchy 4 against plain Arch and to name the three cases that still reach it on Omarchy 4: the hardware scripts run at install time only and no migration re-runs them, which I checked by grepping the migrations directory, the `(VGA|Display).*vendor` match can miss a device, and 32-bit Vulkan is untouched by it.

I rewrote `danger`, which was the weakest field. It warned only that `lib32-*` needs `multilib`, and then described the failure as harmless, which makes it a note rather than a danger. On Omarchy that warning does not even apply: `multilib` is uncommented at line 25 of both `/etc/pacman.conf` here and Omarchy's shipped `default/pacman/pacman-stable.conf`. The real hazard is the record's own fix block, which lists Intel, AMD and NVIDIA packages in a way a reader can install wholesale. The wiki documents that a stray `nvidia_icd.json` makes Chromium and Electron applications hang for about 30 seconds before starting, which is indistinguishable from the symptom this record treats.

I also added what the record omitted and Omarchy provides: `omarchy-hw-vulkan` as the one-line ICD check, `omarchy-install-gaming-gpu-lib32` for the 32-bit set, `vulkan-nouveau` and `vulkan-swrast`, and the fact that pre-GSP NVIDIA cards need the AUR 580xx branch. No cited URL needed removing. Both resolve and both support what the record claims, issue 1441 for the Omarchy 3 era and the wiki for plain Arch, so `sources_remove` is empty. On the ALPM guard: I read `/usr/bin/omarchy-update-pacman-guard` and it aborts only when the parsed pacman arguments carry both a sync and a sysupgrade flag, so none of the record's `pacman -S --needed` commands is blocked. The thread's own `sudo pacman -Syu vulkan-radeon` would be, and I warn about it.

I dropped `frequency` from `common` to `occasional` for the same reason the cause changed. Not exercised: this workstation is NVIDIA-only and carries just `nvidia_icd.json` in `/usr/share/vulkan/icd.d/`, so I could not test the Intel or AMD paths, could not run `vulkaninfo` or `vkcube` (`vulkan-tools` absent, no sudo to install it), and did not reproduce the 30 second Chromium delay, which is taken from the wiki rather than observed here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Install only the ICD that matches your GPU. Two vendor ICDs registered at once is its own bug rather than a safety net: the loader reads every file in `/usr/share/vulkan/icd.d/`, and the Arch wiki records that Vulkan tries the NVIDIA driver before the Radeon one when `nvidia_icd.json` is present, which can leave Chromium and Electron applications hanging until a 30 second timeout before they start. That looks exactly like the symptom this record is meant to cure. If you already installed the wrong one, install the correct ICD first and remove the wrong one second, because Steam depends on the `lib32-vulkan-driver` provision the wrong package is currently satisfying.

`lib32-*` packages come from the `multilib` repository. It is enabled by default in Omarchy's shipped `pacman.conf`, so the "target not found" failure only happens on plain Arch, where it is a clean refusal rather than anything dangerous.

**Fix.**

**On Omarchy 4, check what is already there first.**

```bash
ls /usr/share/vulkan/icd.d/
pacman -Q vulkan-intel vulkan-radeon vulkan-asahi nvidia-utils 2>&1
```

An empty `icd.d` is the real failure. Omarchy ships `omarchy-hw-vulkan`, which tests exactly that and is the quickest check:

```bash
omarchy-hw-vulkan && echo "an ICD is registered" || echo "no ICD"
```

**Install the tools, which Omarchy does not ship.** `vulkaninfo` and `vkcube` live in `vulkan-tools`:

```bash
sudo pacman -S --needed vulkan-tools
vulkaninfo | head -30
vkcube
```

**Install the driver for the GPU you actually have.** Install one vendor's driver, not all of them:

```bash
# Intel iGPU or Arc:
sudo pacman -S --needed vulkan-intel
# AMD:
sudo pacman -S --needed vulkan-radeon
# Apple silicon:
sudo pacman -S --needed vulkan-asahi
# NVIDIA proprietary, Turing and newer: the ICD ships inside nvidia-utils
sudo pacman -S --needed nvidia-utils
# NVIDIA Maxwell, Pascal and Volta are on the frozen 580 branch:
#   nvidia-580xx-utils, from the AUR
# NVIDIA open-source NVK instead of the proprietary driver:
sudo pacman -S --needed vulkan-nouveau
```

On a machine with no usable GPU, such as a VM, install the software rasteriser:

```bash
sudo pacman -S --needed vulkan-swrast
```

None of these is blocked by Omarchy's ALPM guard, which aborts only a transaction carrying both `-S` and `-u`. Do not follow the `sudo pacman -Syu vulkan-radeon` form that appears in the upstream issue thread. On Omarchy the guard refuses it, and on any Arch system `pacman -Sy <pkg>` is a partial upgrade.

**32-bit Vulkan for Steam, Proton and Wine.** Omarchy has a helper that detects your GPUs and installs the matching set, which is safer than picking by hand:

```bash
omarchy-install-gaming-gpu-lib32
```

The manual equivalent, matching your vendor:

```bash
sudo pacman -S --needed lib32-vulkan-icd-loader
sudo pacman -S --needed lib32-vulkan-intel     # Intel
sudo pacman -S --needed lib32-vulkan-radeon    # AMD
sudo pacman -S --needed lib32-nvidia-utils     # NVIDIA, must match nvidia-utils exactly
```

`multilib` is already enabled in Omarchy's shipped `/etc/pacman.conf`. On plain Arch, enable it first:

```bash
grep -A1 '^\[multilib\]' /etc/pacman.conf
sudo sed -i '/^#\[multilib\]/,+1 s/^#//' /etc/pacman.conf
sudo pacman -Syu
```

**On a multi-GPU box you can force a specific Mesa device.** This needs `vulkan-mesa-implicit-layers` and works only for Mesa drivers, not for the NVIDIA proprietary ICD:

```bash
sudo pacman -S --needed vulkan-mesa-implicit-layers
MESA_VK_DEVICE_SELECT=list vulkaninfo
MESA_VK_DEVICE_SELECT=<vendorID>:<deviceID>! <command>
```

The trailing `!` enforces the selection.

**Verify.** `ls /usr/share/vulkan/icd.d/` lists a JSON file for your vendor. `vulkaninfo | grep deviceName` names your GPU rather than reporting no physical devices. `vkcube` renders a spinning cube. The application that would not start now launches, and starts promptly rather than after a pause of about 30 seconds.

Sources: <https://github.com/basecamp/omarchy/issues/1441> · <https://wiki.archlinux.org/title/Vulkan> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/hardware/vulkan.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/hardware/nvidia.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/hardware/all.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-install-gaming-gpu-lib32> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-hw-vulkan> · <https://archlinux.org/packages/extra/x86_64/vulkan-mesa-implicit-layers/> · <https://archlinux.org/packages/extra/x86_64/vulkan-tools/>

---

## Hotplug an NVIDIA eGPU on Wayland without rebooting

`egpu-nvidia-hotplug-wayland` · severity: **medium** · frequency: **rare** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** A Thunderbolt eGPU enclosure plugged in after boot is not picked up: `nvidia-smi` does not list it, or the driver grabs it but every application still renders on the internal GPU. Unplugging and replugging changes nothing.

**Cause.** The NVIDIA modules must not be in use when the eGPU is attached, and stray EGL clients hold the internal dGPU (each EGL program pins ~1 MB of dGPU memory even while rendering on the iGPU), so the modules cannot be unloaded and the new device is never enumerated.

> **Audit corrected this record.** The core sequence is lifted correctly from Arch's External_GPU#'Hotplugging NVIDIA eGPU' — the 1 MB-per-EGL-program explanation, /etc/environment.d/50_mesa.conf, the exact rmmod order (uvm, drm, modeset, nvidia), `modprobe nvidia-drm` to reload, and the four-variable offload string are all the wiki's own. What is missing will stop most readers cold: (1) the Thunderbolt device must be authorized (boltctl / BIOS setting), and the record says 'wait for Thunderbolt to authorise it' without saying how; (2) many laptops need PCIe hotplug kernel parameters before an eGPU is enumerated at all; (3) if the nvidia modules are early-loaded from the initramfs (which records [0] and [2] tell users to configure) or modeset/fbdev has bound a console, `rmmod` fails no matter how many EGL clients you kill — the record's only answer to that is `lsof`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Unloading `nvidia_drm` while the compositor is running on the NVIDIA GPU will kill your session. Do this only when the internal iGPU drives the display, and preferably from a TTY. Physically hot-unplugging a Thunderbolt eGPU while the driver holds it can hang the kernel.

**Fix.**

Default everything to Mesa so nothing pins the internal dGPU:

```bash
sudo tee /etc/environment.d/50_mesa.conf >/dev/null <<'EOF'
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
EOF
```

If the enclosure never appears in `lspci -d ::03xx` at all, add the PCIe hotplug kernel parameters (Arch External GPU) and reboot:

```
pcie_ports=native pci=assign-busses,hpbussize=0x33,realloc,hpmmiosize=128M,hpmmioprefsize=16G
```

Ensure the nvidia modules are NOT early-loaded, or they cannot be unloaded later:

```bash
ls /etc/mkinitcpio.conf.d/nvidia.conf 2>/dev/null && sudo rm /etc/mkinitcpio.conf.d/nvidia.conf && sudo mkinitcpio -P
```

Log out and back in, then with the eGPU **unplugged**:

```bash
sudo modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia
```

If that fails with 'Module nvidia is in use', find the holders and stop them:

```bash
sudo lsof +c0 /dev/nvidia*
```

Plug in the eGPU and authorize the Thunderbolt device (skip if your firmware is set to auto-authorize):

```bash
boltctl list
boltctl authorize <uuid>      # add --enroll to remember it
lspci -d ::03xx               # the eGPU should now be listed
```

Reload and confirm:

```bash
sudo modprobe nvidia_drm
nvidia-smi
```

Run a program on the eGPU by re-enabling the NVIDIA vendor for that process only:

```bash
__GLX_VENDOR_LIBRARY_NAME=nvidia \
__NV_PRIME_RENDER_OFFLOAD=1 \
__VK_LAYER_NV_optimus=NVIDIA_only \
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
<command>
```

Hyprland also needs to be told the eGPU exists — see the AQ_DRM_DEVICES record.

**Verify.** `nvidia-smi` lists the eGPU; the offload command above reports the eGPU in `glxinfo | grep "OpenGL renderer"`.

Sources: <https://wiki.archlinux.org/title/External_GPU> · <https://wiki.archlinux.org/title/PRIME>

---

## Fix cursor artifacts, ghosting or an invisible cursor on NVIDIA + Hyprland

`hyprland-nvidia-cursor-artifacts-hardware-cursors` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** The mouse pointer leaves trails, flickers, disappears entirely over some windows, or a frozen 'ghost' cursor stays on screen after a game exits — on an NVIDIA GPU under Hyprland.

**Cause.** Hyprland uses a hardware cursor plane by default (`cursor:no_hardware_cursors = 2`, auto). NVIDIA's hardware cursor plane misbehaves in several situations — mixed-scale multi-monitor setups, tearing/direct-scanout, and after an XWayland client dies holding a cursor surface.

> **Audit corrected this record.** The main fix is right and current: I confirmed against Hyprland's Variables.md that cursor:no_hardware_cursors is an int defaulting to 2 ('0 - use hw cursors if possible, 1 - don't use hw cursors, 2 - auto (disable when tearing)'), and that no_break_fs_vrr's description literally says 'may require no_hardware_cursors = true'. The tail is wrong: `hyprcursor` is the cursor format/library/utilities package — installing it gives you no cursor theme at all, so `hyprctl setcursor <ThemeName> 24` will fail with whatever name the user guesses. You need an actual theme package.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Force software cursors. Hyprland <= 0.54, in `~/.config/hypr/hyprland.conf`:

```
cursor {
    no_hardware_cursors = 1
}
```

Hyprland 0.55+ / Omarchy 4 Lua config:

```lua
hl.set("cursor:no_hardware_cursors", 1)
```

Apply without restarting:

```bash
hyprctl reload
```

If instead of artifacts you see the default Hyprland logo cursor, you have no cursor **theme** installed — `hyprcursor` is only the library/format, not a theme. Install a real theme and select it by its directory name:

```bash
sudo pacman -S --needed adwaita-cursors      # or xcursor-themes, breeze, a bibata-* AUR theme...
ls /usr/share/icons                          # theme names live here
hyprctl setcursor Adwaita 24
```

Make it stick across sessions by also exporting the theme for XWayland/GTK clients:

```
env = XCURSOR_THEME,Adwaita
env = XCURSOR_SIZE,24
```
```lua
hl.env("XCURSOR_THEME", "Adwaita")
hl.env("XCURSOR_SIZE", "24")
```

Note `cursor:no_break_fs_vrr = 1` requires `no_hardware_cursors = 1` to take effect.

**Verify.** `hyprctl getoption cursor:no_hardware_cursors` returns `1`, and moving the pointer across monitors leaves no trails or ghosts.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/Hyprland/issues/15110> · <https://wiki.hypr.land/Nvidia/>

---

## Fix washed-out, dim colours on an AMD laptop panel

`amdgpu-washed-out-colors-abm` · severity: **low** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Colours on the internal laptop display look grey and washed out, and get worse when the machine switches to a power-saving profile or goes on battery. External monitors look normal.

**Cause.** Adaptive Backlight Management, which the AMD driver exposes as Panel Power Savings, tells the GPU to reduce colour accuracy on the laptop's internal panel to save power. `power-profiles-daemon` has enabled it in its more aggressive power modes since version 0.20, and `tuned` does the same, which is why the colours track the power profile and the charger. External monitors are unaffected because ABM is an internal panel feature.

The kernel describes the parameter as `ABM level (0 = off, 1-4 = backlight reduction level, -1 auto (default))`, and adds that userspace can only override the level after boot while the parameter is left at auto. That is what lets a power profile change it at runtime, and it is also why pinning the parameter to `0` takes the setting away from the power daemon for good.

On Omarchy 4 the daemon in play is `power-profiles-daemon` (0.30-1 as of 2026-09-11). `tuned` is not installed. Omarchy drives the daemon through `omarchy-powerprofiles-set`, which detects AC or battery from UPower and remembers a separate profile for each under `~/.local/state/omarchy/powerprofiles/`.

> **Audit corrected this record.** The single cited source resolves and does support the claim. I fetched https://wiki.archlinux.org/title/AMDGPU as raw wikitext and its section "Colors appear washed out and dim on laptops" says that power-profiles-daemon and tuned have started to enable Panel Power Savings, that PPS makes the GPU lower colour accuracy to save power on more aggressive profiles, and that the fix is `amdgpu.abmlevel=0`. The record's cause and symptom are close to verbatim from it, so the source stays and nothing is removed. I then checked the parameter in the kernel rather than trusting the wiki: in drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c it is `module_param_named(abmlevel, amdgpu_dm_abm_level, int, 0444)` with the description `ABM level (0 = off, 1-4 = backlight reduction level, -1 auto (default))`, and the kerneldoc above it adds that userspace can only override this level after boot if it is set to auto. That is a real fact the record misses in both directions. It explains why a power profile can change your colours at all, and it means `amdgpu.abmlevel=0` is not `auto, but off`: it pins the level and stops power-profiles-daemon managing panel power savings afterwards. It also gives a reversible fix the record never offered.

What was wrong is the apply step, the same shape as the other AMD kernel-parameter records. The record told an Omarchy reader to edit `cmdline:` in /boot/limine.conf or /etc/default/grub, and carries `omarchy` in applies_to. On this workstation (omarchy 4.0.2-1, kernel 7.1.9) there is no /etc/default/grub, the boot is a UKI, and /boot/limine.conf is regenerated. I read /etc/limine-entry-tool.d/omarchy-defaults.conf and omarchy-uki.conf directly, and the packaged template /etc/limine-entry-tool.conf from limine-mkinitcpio-hook 1.37.1-1 states the `+=` versus `=` rule. The fix now matches the existing record `limine-kernel-parameters-not-applying-omarchy` instead of contradicting it, and keeps the systemd-boot and GRUB branches labelled for other distributions.

I also checked what Omarchy manages itself before leaving the reader to set anything by hand. Omarchy 4 ships power-profiles-daemon 0.30-1 (`pacman -Q`), tuned is not installed, and /usr/share/omarchy/bin carries omarchy-powerprofiles-set, -list and -init. I read omarchy-powerprofiles-set: it detects AC or battery from UPower, calls `powerprofilesctl set`, and remembers a profile per state under $XDG_STATE_HOME/omarchy/powerprofiles. `omarchy-powerprofiles-list` on this machine prints power-saver, balanced, performance. Omarchy's brightness tooling (omarchy-brightness-display and friends) drives brightnessctl and DDC and does not touch ABM, so there is no conflict with a theme refresh here. NOT EXERCISED: this workstation has an NVIDIA RTX 3090 and amdgpu is not loaded, so no ABM or colour behaviour was tested here and no profile was switched. The Omarchy boot and power-profile mechanisms were confirmed on this machine. Severity `low` and frequency `common` are left alone: the symptom is cosmetic and now has a one-command reversible fix, and it is common on AMD laptop panels.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Option 1 carries no risk worth naming. You can undo it with one command and nothing is written to the bootloader.

Option 2 has two costs. The panel draws slightly more power on battery in every profile. More importantly, the kernel says userspace can only override the ABM level after boot while the parameter is left at auto, so pinning it to `0` stops `power-profiles-daemon` managing panel power savings at all, which is not obvious from the parameter name. On Omarchy 4 the drop-in itself is the larger risk. Writing `KERNEL_CMDLINE[default]=` instead of `+=`, or naming your file so it sorts before `omarchy-defaults.conf`, silently drops Omarchy's `initramfs_async=0`, and the packaged comment in that file says that is what keeps Plymouth alive at the LUKS prompt, so an encrypted machine falls back to an unthemed text prompt or hangs. `limine-mkinitcpio` rewrites the UKI on the ESP, so run `df -h /boot` first, because a full ESP produces a truncated image that will not boot. A bad kernel parameter is a failure to boot. Recovery is the Limine boot menu editor or a Limine snapshot entry, and both are bypassed if you have enabled Omarchy's Direct Boot, in which case pick Limine from the firmware boot menu (usually F12, F8 or Esc). On a GRUB system the equivalent recovery is GRUB's own `e` editor at the menu.

**Fix.**

**Option 1, reversible and no reboot: stop using the most aggressive power profile.** The kernel parameter defaults to `-1` (auto), and only at auto can userspace change ABM after boot, so the power profile is what is actually moving your colours.

```bash
powerprofilesctl get

# Omarchy 4: sets it now and remembers it for the next time you are on battery
omarchy-powerprofiles-set battery balanced

# plain Arch, EndeavourOS, CachyOS, Manjaro
powerprofilesctl set balanced
```

Colours come back within a second or two. Try this first, because it costs nothing to undo.

**Option 2, permanent: turn ABM off with a kernel parameter.**

```
amdgpu.abmlevel=0
```

`abmlevel` is a `0444` module parameter, so this only takes effect at boot. Read the danger note first: `0` is not `auto, but off`. It pins the level, so `power-profiles-daemon` can no longer manage panel power savings on any profile.

**Omarchy 4** has no `/etc/default/grub`, and `/boot/limine.conf` is regenerated on every kernel or limine transaction, so an edit there is discarded. Omarchy boots a Unified Kernel Image, which bakes the command line into the `.efi` image. Kernel parameters go in your own drop-in under `/etc/limine-entry-tool.d/` whose filename sorts after Omarchy's `omarchy-defaults.conf`, and always with `+=`:

```bash
sudo tee -a /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
# `+=` appends. A bare `=` would wipe Omarchy's own defaults.
KERNEL_CMDLINE[default]+=" amdgpu.abmlevel=0"
EOF
sudo limine-mkinitcpio && sudo limine-update && sudo reboot
```

Use `tee -a` rather than `tee`. A bare `tee` truncates the file and would drop any parameter you added earlier from another record. The full mechanism, including how to test a parameter from the Limine boot menu editor without writing anything to disk, is in the record `limine-kernel-parameters-not-applying-omarchy`.

**Other bootloaders:**

- systemd-boot: append to `options` in `/boot/loader/entries/*.conf`
- GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

Reboot in every case.

**Verify.** For option 1:

```bash
powerprofilesctl get
```

reports the profile you chose, and the colours follow it when you switch profiles or unplug the charger.

For option 2:

```bash
cat /sys/module/amdgpu/parameters/abmlevel   # 0 once applied, -1 is the default
cat /proc/cmdline
```

`/proc/cmdline` contains `amdgpu.abmlevel=0`. On Omarchy 4 it must also still contain Omarchy's own defaults (`quiet splash loglevel=0 systemd.show_status=false rd.udev.log_level=0 vt.global_cursor_default=0` and `initramfs_async=0`). If those have gone, your drop-in used `=` where it needed `+=`. Then switch to `power-saver` and unplug the charger: the colours must not change.

Sources: <https://wiki.archlinux.org/title/AMDGPU> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c> · <https://www.phoronix.com/news/Power-Profiles-Daemon-0.20>

---

## Kill the 1–2 second app launch delay caused by waking the dGPU

`wayland-app-launch-delay-dgpu-wakeup` · severity: **low** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** On a hybrid laptop with working RTD3 power management, GUI apps take an extra second or two to appear every time — especially the first launch after idle. Nothing is CPU-bound; the delay is just dead time before the window shows.

**Cause.** OpenGL/EGL and Vulkan enumerate every candidate device listed in `/usr/share/glvnd/egl_vendor.d/` and `/usr/share/vulkan/icd.d/`. Even when the iGPU config sorts first, the loader still iterates the NVIDIA entry, which wakes the sleeping dGPU (~1 s) and burns battery, before falling back to the iGPU. It is an NVIDIA driver behaviour, not a compositor bug.

> **Audit corrected this record.** The mechanism (the GLVND/Vulkan loaders iterate every ICD in /usr/share/vulkan/icd.d and /usr/share/glvnd/egl_vendor.d and wake a sleeping dGPU on the way) is real and is the same trick Arch's External_GPU page uses, and the Intel path is right — I confirmed vulkan-intel currently ships /usr/share/vulkan/icd.d/intel_icd.json. But the AMD filename given is stale: vulkan-radeon ships radeon_icd.json, not radeon_icd.x86_64.json (Mesa dropped the arch suffix), so an AMD-iGPU reader copy-pastes a path that does not exist and loses Vulkan entirely with no error. Also missing: pinning one 64-bit ICD removes Vulkan from 32-bit Steam/Proton, and environment.d only applies to the systemd user session (not TTY logins or sudo).
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** With these set globally, Vulkan and EGL apps will not see the NVIDIA GPU at all — Steam games and CUDA/ML workloads launched without an explicit override will silently run on the iGPU or fail to find a device.

**Fix.**

Check what you actually have before pinning anything — a nonexistent path in `VK_DRIVER_FILES` silently disables Vulkan:

```bash
ls /usr/share/vulkan/icd.d/ /usr/share/glvnd/egl_vendor.d/
```

Current names: Intel `intel_icd.json`, AMD `radeon_icd.json`, NVIDIA `nvidia_icd.json` (32-bit variants appear here too if you have the lib32 packages).

```bash
sudo tee /etc/environment.d/50-mesa-default.conf >/dev/null <<'EOF'
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
__GLX_VENDOR_LIBRARY_NAME=mesa
EOF
```

That alone removes most of the wake-ups. Only add a Vulkan pin if you still see the delay, and list every ICD you need — e.g. on an Intel iGPU with Steam/Proton:

```bash
# append to the same file, using the exact filenames from the ls above
VK_DRIVER_FILES=/usr/share/vulkan/icd.d/intel_icd.json
```

Alternative that does not break 32-bit: install `vulkan-mesa-implicit-layers` and use `MESA_VK_DEVICE_SELECT=<vendorID>:<deviceID>` per app instead.

Log out and back in (`/etc/environment.d` is read by the systemd user manager, so it does not affect bare TTY logins). Override per-command when you want the dGPU — see the PRIME record.

**Verify.** Apps open without the extra pause, and `cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status` stays `suspended` while you launch them.

Sources: <https://wiki.archlinux.org/title/PRIME> · <https://wiki.archlinux.org/title/External_GPU>

---
