# GPU & drivers

35 problems. Sorted by severity, then by how often users hit it.

## Repair a DKMS driver that did not rebuild after a kernel update

`dkms-nvidia-build-fails-after-kernel-update` · severity: **critical** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** After `sudo pacman -Syu` and a reboot you land in a TTY or a black screen. `nvidia-smi` says `NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver`, `modprobe nvidia` reports `Module nvidia not found in directory /lib/modules/<version>`, and `dkms status` shows the module built only for the *old* kernel.

**Cause.** DKMS rebuilds out-of-tree modules on kernel upgrade, but silently fails when the matching `*-headers` package for the kernel you booted is missing, when the build errors out against a new kernel API, or when the pacman transaction was interrupted. The rebuild failure scrolls past in the pacman output and is easy to miss.

> ⚠️ **Risk.** Never run `pacman -Sy <pkg>` to grab headers — that is a partial upgrade and will break the system. Always `pacman -Syu`. If a kernel update and a driver update land in the same transaction, do not reboot until you have confirmed `dkms status` shows the module built for the NEW kernel; keep `linux-lts` installed as a fallback boot entry.

**Fix.**

From a TTY:

```bash
uname -r
dkms status

# Install headers for EVERY kernel you have installed
sudo pacman -S --needed linux-headers
# plus, as applicable:
# sudo pacman -S --needed linux-lts-headers linux-zen-headers linux-hardened-headers

# Rebuild everything for the running kernel
sudo dkms autoinstall
# ...or for a specific kernel:
sudo dkms autoinstall -k "$(uname -r)"
```

If the build still fails, read the log it names (typically `/var/lib/dkms/nvidia/<version>/build/make.log`). A driver too old for the kernel is the usual cause — upgrade `nvidia-dkms`/`nvidia-open-dkms` (or the AUR legacy branch) before rebooting into the new kernel.

Clear out stale builds and refresh the module map:

```bash
sudo dkms status                       # note old versions
sudo dkms remove nvidia/<old-version> --all
sudo depmod -a "$(uname -r)"
sudo mkinitcpio -P
reboot
```

If you are stuck with no console at all, boot the previous kernel from your bootloader menu (or a live USB + `arch-chroot`) and do the above there.

**Verify.** `dkms status` shows `installed` for the running kernel; `modinfo nvidia | head -3` prints a version; `nvidia-smi` works.

Sources: <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://wiki.archlinux.org/title/NVIDIA> · <https://github.com/basecamp/omarchy/issues/7947>

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

**Symptom.** After a routine `sudo pacman -Syu` (or `omarchy-update`) on a machine with a GTX 1050/1060/1070/1080, GTX 9xx, MX150 or Titan X, the graphical session no longer comes up — black screen, or you land in a TTY. `nvidia-smi` prints `NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver`. `dmesg` shows the NVIDIA module refusing to bind to the GPU.

**Cause.** NVIDIA driver 590 dropped support for Pascal and older GPUs, and Arch simultaneously switched the main packages to the open kernel modules (`nvidia` → `nvidia-open`, `nvidia-dkms` → `nvidia-open-dkms`, `nvidia-lts` → `nvidia-lts-open`). The open kernel modules only support Turing (GTX 16xx / RTX 20xx) and newer, so on Pascal and older the driver simply fails to load after the upgrade.

> ⚠️ **Risk.** `pacman -Rdd` skips dependency checks — only use it to break the nvidia/nvidia-utils circular dependency, and reinstall a working driver in the same session. Do NOT reboot between removing the old driver and installing the new one unless you are comfortable working from a TTY. Building the AUR DKMS package needs matching kernel headers; if headers are missing the module silently is not built and you reboot into a black screen.

**Fix.**

From a TTY (Ctrl+Alt+F2) or a chroot:

```bash
# Remove whatever mainline NVIDIA packages are installed
sudo pacman -Rdd nvidia nvidia-open nvidia-dkms nvidia-open-dkms nvidia-lts nvidia-lts-open 2>/dev/null

# Make sure headers for every installed kernel are present
sudo pacman -S --needed linux-headers      # add linux-lts-headers / linux-zen-headers as applicable

# Install the legacy proprietary 580xx branch from the AUR
yay -S nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils

sudo mkinitcpio -P
reboot
```

Omarchy's installer picks these same packages for Maxwell/Pascal/Volta (see `omarchy-hw-nvidia-without-gsp`). For these cards Omarchy sets `NVD_BACKEND=egl` rather than `direct`; in `~/.config/hypr/envs.conf`:

```
env = NVD_BACKEND,egl
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
```

On Hyprland 0.55+/Omarchy 4 Lua config the equivalent is:

```lua
hl.env("NVD_BACKEND", "egl")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
```

If you would rather not use the AUR at all, the fully-open `nouveau`/NVK stack (`mesa` + `vulkan-nouveau`) works on these cards, at a large performance cost.

**Verify.** `nvidia-smi` prints a driver version in the 580.x series and lists your GPU; `cat /sys/module/nvidia_drm/parameters/modeset` returns `Y`; Hyprland starts.

Sources: <https://archlinux.org/news/nvidia-590-driver-drops-pascal-support-main-packages-switch-to-open-kernel-modules/> · <https://github.com/basecamp/omarchy/issues/3954> · <https://wiki.archlinux.org/title/NVIDIA> · <https://github.com/basecamp/omarchy/blob/master/install/config/hardware/nvidia.sh>

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

**Cause.** By default the NVIDIA driver only saves and restores essential video memory across a suspend cycle; everything else is lost, which the userspace driver cannot always reconstruct — hence corruption, dead outputs and crashing clients. Full VRAM preservation needs a module parameter plus (on 430–590 series drivers) the nvidia suspend/hibernate/resume systemd services.

> ⚠️ **Risk.** If `/var/tmp` (or `/tmp`, on default upstream settings) does not have enough free space for your VRAM, the suspend can fail or hang. Verify free space before relying on suspend. Regenerating the initramfs is required when using early KMS — an interrupted `mkinitcpio -P` leaves an unbootable image.

**Fix.**

Check what is actually set:

```bash
sudo sort /proc/driver/nvidia/params | grep -E 'PreserveVideoMemoryAllocations|UseKernelSuspendNotifiers|TemporaryFilePath'
systemctl is-enabled nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
```

On 430–590 drivers you want `PreserveVideoMemoryAllocations: 1` and `TemporaryFilePath: "/var/tmp"`; on 595+ drivers you want `UseKernelSuspendNotifiers: 1` instead.

If the parameter is missing:

```bash
# drivers 430-590
sudo tee /etc/modprobe.d/nvidia-power.conf >/dev/null <<'EOF'
options nvidia NVreg_PreserveVideoMemoryAllocations=1 NVreg_TemporaryFilePath=/var/tmp
EOF

# drivers 595+
# sudo tee /etc/modprobe.d/nvidia-power.conf >/dev/null <<'EOF'
# options nvidia NVreg_UseKernelSuspendNotifiers=1
# EOF

sudo mkinitcpio -P
```

On 430–590 drivers also enable the services (Arch enables them by default, but a manual driver install or an old system may not have them):

```bash
sudo systemctl enable nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
```

On 595+ drivers those services are deliberately **disabled** — leave them off.

`/var/tmp` must be on a real filesystem (ext4/XFS, not tmpfs) with room for all your VRAM plus ~5%:

```bash
nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits
df -h /var/tmp
```

Reboot and test a suspend cycle.

**Verify.** `sudo sort /proc/driver/nvidia/params | grep -E 'Preserve|UseKernelSuspend'` shows the value `1`; `systemctl suspend` followed by a wake brings the displays back with no corruption, and `journalctl -b -1 | grep -i xid` is empty.

Sources: <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks> · <https://wiki.archlinux.org/title/NVIDIA/Troubleshooting> · <https://wiki.hypr.land/Nvidia/> · <https://github.com/basecamp/omarchy/issues/2635> · <https://github.com/basecamp/omarchy/issues/2112>

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

> ⚠️ **Risk.** Disabling PowerPlay features increases idle power draw and heat. Make sure the parameter survives kernel updates (it lives in bootloader config, so it normally does — but a bootloader reinstall can drop it). Bootloader edits can break boot; use the boot-menu editor to recover.

**Fix.**

Disable GFXOFF via the PowerPlay feature mask kernel parameter:

```
amdgpu.ppfeaturemask=0xffff7fff
```

That mask disables only `PP_GFXOFF_MASK` and leaves everything else enabled. If freezes persist, escalate:
- `0xfffd7fff` — also disables stutter mode
- `0xfffd3fff` — also disables stutter mode and overdrive
- `0` — disables every PowerPlay feature (diagnostic only; costs power management)

Apply it where your bootloader keeps kernel parameters:
- systemd-boot: the `options` line in `/boot/loader/entries/*.conf`
- Limine: the `cmdline:` line in `/boot/limine.conf`
- GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

Reboot.

**Verify.** `cat /proc/cmdline` shows the parameter; leave the machine idle overnight with the monitors attached and it is still responsive in the morning.

Sources: <https://wiki.archlinux.org/title/AMDGPU>

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

> ⚠️ **Risk.** If you list only a GPU that drives no monitor, Hyprland will start with no visible output. Test the change from a TTY first (`Hyprland` from Ctrl+Alt+F2) so you can Ctrl+C out of it rather than being locked out of your desktop.

**Fix.**

Identify the cards by PCI address, not by `cardN`:

```bash
lspci -d ::03xx
ls -l /dev/dri/by-path
```

Create stable symlinks with udev (example for an Intel iGPU; repeat with `AMD`/`NVIDIA` and a different symlink name for the other card):

```bash
IGPU_ID=$(lspci -d ::03xx | grep 'Intel' | cut -f1 -d' ')
sudo tee /etc/udev/rules.d/90-intel-igpu-dev-path.rules >/dev/null <<EOF
KERNEL=="card*", KERNELS=="0000:$IGPU_ID", SUBSYSTEM=="drm", SUBSYSTEMS=="pci", SYMLINK+="dri/intel-igpu"
EOF

sudo udevadm control --reload
sudo udevadm trigger
ls -l /dev/dri/intel-igpu
```

Then tell Hyprland the priority order (first entry = primary renderer, `:`-separated). `~/.config/hypr/envs.conf`:

```
env = AQ_DRM_DEVICES,/dev/dri/intel-igpu:/dev/dri/nvidia-dgpu
```

Hyprland 0.55+/Lua:

```lua
hl.env("AQ_DRM_DEVICES", "/dev/dri/intel-igpu:/dev/dri/nvidia-dgpu")
```

If you launch Hyprland via uwsm, export it in `~/.config/uwsm/env-hyprland` instead:

```
export AQ_DRM_DEVICES="/dev/dri/intel-igpu:/dev/dri/nvidia-dgpu"
```

If a secondary monitor on the NVIDIA card is still broken or laggy, also set:

```
env = AQ_FORCE_LINEAR_BLIT,0
```

Log out and back in.

**Verify.** `hyprctl monitors` lists every connected display; `env | grep AQ_DRM_DEVICES` inside the session shows your list; on a laptop `nvidia-smi` shows no processes and the dGPU idle.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Advanced%20and%20Cool/Multi-GPU.md> · <https://wiki.hypr.land/Nvidia/> · <https://github.com/basecamp/omarchy/issues/1776>

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

## Stop NVIDIA freezing when the display blanks (GSP Timeout / Xid 119)

`nvidia-dpms-gsp-timeout-freeze` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** The machine hard-freezes seconds after the screen blanks on idle, or right after resuming — mouse dead, no TTY switch, only a power-button reset works. `journalctl -b -1 -k` shows:

```
NVRM: _kgspLogXid119: ***** GSP Timeout *****
NVRM: Xid (PCI:0000:01:00): 119, Timeout after 6s of waiting for RPC response from GPU0 GSP! Expected function 76 (GSP_RM_CONTROL) sequence 1321
```

**Cause.** During DPMS off and suspend/resume transitions the GPU drops into a very low clock state that the GSP firmware cannot recover from, so the RPC to the GSP microcontroller times out and the driver wedges.

> ⚠️ **Risk.** Locking clocks raises idle power draw and temperature; on a laptop this measurably shortens battery life. Do not set the minimum near the card's maximum on a thermally constrained machine.

**Fix.**

Pin a higher minimum GPU/memory clock so the GPU never enters the unstable state.

```bash
sudo systemctl enable --now nvidia-persistenced.service

# find valid clock values for your card
nvidia-smi -q -d SUPPORTED_CLOCKS
nvidia-smi -q -d CLOCK

# temporary test (adjust the upper bounds to your GPU's real max)
sudo nvidia-smi -lgc 800,2100
sudo nvidia-smi -lmc 800,10000
# revert with: sudo nvidia-smi -rgc ; sudo nvidia-smi -rmc
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

Lower the 500 floor to reduce idle power draw — too low and the freeze comes back. As a stopgap you can simply stop Hyprland from blanking by removing/raising the DPMS timeout in your hypridle config (`~/.config/hypr/hypridle.conf`).

**Verify.** Leave the machine idle past the blank timeout, then wake it: the desktop returns. `journalctl -b -1 -k | grep -i 'Xid\|GSP Timeout'` stays empty.

Sources: <https://wiki.archlinux.org/title/NVIDIA/Troubleshooting> · <https://github.com/basecamp/omarchy/issues/2112> · <https://github.com/basecamp/omarchy/issues/2635>

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

> ⚠️ **Risk.** Downgrading to the 535xx AUR branch pins you to an old driver; do not mix `nvidia-535xx-utils` with the repo `lib32-nvidia-utils` — install the matching `lib32-nvidia-535xx-utils` or 32-bit games will fail with GLX/Vulkan errors.

**Fix.**

Bring the whole stack up to the versions that support explicit sync:

```bash
sudo pacman -Syu xorg-xwayland wayland-protocols nvidia-utils
pacman -Q xorg-xwayland wayland-protocols nvidia-utils
```

You need at minimum:
- `xorg-xwayland` ≥ 24.1
- `wayland-protocols` ≥ 1.34
- NVIDIA driver ≥ 555

If your GPU is too old for the 555+ drivers (Kepler and older), the last driver series without this bug is 535 — install one of the `nvidia-535xx-*` AUR packages instead.

If a specific fullscreen game still glitches, disable direct scanout for it. Hyprland ≤ 0.54:

```
render {
    direct_scanout = 0
}
```

Hyprland 0.55+:

```lua
hl.set("render:direct_scanout", 0)
```

**Verify.** `pacman -Q xorg-xwayland wayland-protocols nvidia-utils` meets the version floors above, and the game renders cleanly. `hyprctl systeminfo` reports the NVIDIA driver version in use.

> *Not independently audited: verify before running.*

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.archlinux.org/title/NVIDIA> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md>

---

## Fix a frozen AMD display with 'flip_done timed out' in the log

`amdgpu-flip-done-timed-out` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** The screen stops updating entirely — the image is frozen but audio keeps playing and SSH still works. `journalctl -k` shows:

```
[drm:drm_atomic_helper_wait_for_flip_done] *ERROR* [CRTC:...] flip_done timed out
```

**Cause.** A bug in the amdgpu display code around Panel Self Refresh (PSR) / memory stutter mode stops the atomic page flip from ever completing.

> ⚠️ **Risk.** Disabling Panel Self Refresh costs battery life on laptops. Bootloader edits can break boot; recover from the boot menu editor.

**Fix.**

Add the amdgpu display debug mask as a kernel parameter:

```
amdgpu.dcdebugmask=0x10
```

That disables PSR v1 and 'Panel Self Refresh - Selectively Updated'. If that is not enough, use:

```
amdgpu.dcdebugmask=0x12
```

which disables Panel Self Refresh and memory stutter mode.

Apply via your bootloader:
- systemd-boot: `options` in `/boot/loader/entries/*.conf`
- Limine: `cmdline:` in `/boot/limine.conf`
- GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

Reboot.

**Verify.** `cat /proc/cmdline` contains `amdgpu.dcdebugmask=0x10`; the display no longer freezes and `journalctl -k -g flip_done` is empty after a full day of use.

Sources: <https://wiki.archlinux.org/title/AMDGPU>

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

**Symptom.** During an Omarchy install (or when re-running the hardware config) on a machine with an MX150, GTX 1050 or similar Pascal GPU, the install aborts with:

```
error: target not found: nvidia-580xx-dkms
error: target not found: lib32-nvidia-580xx-utils
```

**Cause.** Omarchy's `install/config/hardware/nvidia.sh` detects a Maxwell/Pascal/Volta card via `omarchy-hw-nvidia-without-gsp` and asks for `nvidia-580xx-dkms`, `nvidia-580xx-utils` and `lib32-nvidia-580xx-utils`. Those live in the AUR, not in the official repos, so if the AUR helper is not usable at that point in the install the `pacman` targets cannot be resolved and the script exits non-zero, taking the rest of the install with it.

> ⚠️ **Risk.** Editing files under ~/.local/share/omarchy puts them out of sync with upstream; `omarchy-update` may report a dirty working tree or overwrite your edit. Revert the `exit 0` line once the driver is installed.

**Fix.**

Let the install finish first, then install the driver by hand after first boot:

```bash
# 1. Skip the failing step: temporarily neutralise the script
sudo sed -i '1i exit 0' ~/.local/share/omarchy/install/config/hardware/nvidia.sh
# (re-run the installer / continue)

# 2. After booting into Omarchy, install the legacy driver via the AUR helper
yay -S --needed linux-headers nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils

# 3. Apply the same config the script would have applied
printf 'options nvidia_drm modeset=1\n' | sudo tee /etc/modprobe.d/nvidia.conf
sudo tee /etc/mkinitcpio.conf.d/nvidia.conf >/dev/null <<'EOF'
MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
EOF
sudo mkinitcpio -P

cat >> ~/.config/hypr/envs.conf <<'EOF'

# NVIDIA (Maxwell/Pascal/Volta without GSP firmware)
env = NVD_BACKEND,egl
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
EOF

reboot
```

Until the driver is installed the machine runs on `nouveau`, which is slow but perfectly usable for finishing setup.

**Verify.** `pacman -Q nvidia-580xx-dkms` prints a version, `dkms status` shows the module `installed` for your running kernel, and `nvidia-smi` reports the GPU.

Sources: <https://github.com/basecamp/omarchy/issues/7947> · <https://github.com/basecamp/omarchy/issues/3954> · <https://github.com/basecamp/omarchy/blob/master/install/config/hardware/nvidia.sh>

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

## Fix 'vaInitialize failed' in screen recording and hardware video decode

`vaapi-init-failed-screen-recording` · severity: **medium** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Screen recording produces no file at all, or video playback falls back to software. Running the recorder from a terminal shows:

```
gsr_get_supported_video_codecs_vaapi: vaInitialize failed
```

or `vainfo` errors with `libva: /usr/lib/dri/<driver>_drv_video.so init failed`.

**Cause.** No usable VA-API driver is installed for the GPU that is actually driving the display, or the wrong one is being picked. On hybrid Intel+NVIDIA laptops VA-API tries the first device it finds; if only one vendor's driver is installed, initialisation fails silently.

> ⚠️ **Risk.** On a hybrid laptop, forcing `LIBVA_DRIVER_NAME=nvidia` when the displays are driven by the Intel iGPU routes decoding through the wrong device and corrupts browser video — set it to the driver of the GPU that owns the outputs.

**Fix.**

Install the right VA-API driver for your hardware (install **both** on a hybrid machine):

```bash
sudo pacman -S --needed libva-utils            # provides vainfo

# Intel Broadwell (2014) and newer, incl. Arc:
sudo pacman -S --needed intel-media-driver
# Intel GMA 4500 (2008) through Coffee Lake:
sudo pacman -S --needed libva-intel-driver
# Skylake and later also need:
sudo pacman -S --needed linux-firmware-intel

# AMD: VA-API comes from mesa (radeonsi) — make sure mesa is installed
sudo pacman -S --needed mesa

# NVIDIA proprietary (NVDEC via VA-API):
sudo pacman -S --needed libva-nvidia-driver
```

Then pin the driver explicitly. `LIBVA_DRIVER_NAME` values: `iHD` (intel-media-driver), `i965` (libva-intel-driver), `radeonsi` (AMD), `nvidia` (NVIDIA proprietary).

`~/.config/hypr/envs.conf`:

```
env = LIBVA_DRIVER_NAME,iHD
```

Hyprland 0.55+/Lua:

```lua
hl.env("LIBVA_DRIVER_NAME", "iHD")
```

On NVIDIA also set `NVD_BACKEND` — `direct` on Turing and newer, `egl` on Maxwell/Pascal/Volta (this is what Omarchy's installer does).

If `vainfo` cannot connect at all on a headless/secondary GPU, force the DRM display:

```bash
vainfo --display drm
```

**Verify.** `vainfo` lists supported profiles and entrypoints without `init failed`. Start a recording and confirm a file is written; `intel_gpu_top` (Intel) / `nvtop` (any vendor) shows the DEC/ENC engine above 0% during playback.

Sources: <https://github.com/basecamp/omarchy/issues/2706> · <https://wiki.archlinux.org/title/Hardware_video_acceleration> · <https://github.com/basecamp/omarchy/blob/master/install/config/hardware/nvidia.sh>

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

> ⚠️ **Risk.** Editing bootloader configuration. A typo in the kernel command line can prevent boot — on systemd-boot/Limine you can edit the entry at the boot menu (press `e`) to recover.

**Fix.**

Add the kernel parameter `amdgpu.sg_display=0`.

- systemd-boot: append it to the `options` line in `/boot/loader/entries/*.conf`
- Limine: append it to the `cmdline:` line in `/boot/limine.conf`
- GRUB:

```bash
sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="/&amdgpu.sg_display=0 /' /etc/default/grub
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

Reboot.

**Verify.** `cat /proc/cmdline` contains `amdgpu.sg_display=0`; hot-plugging the external monitor no longer flashes white.

Sources: <https://wiki.archlinux.org/title/AMDGPU>

---

## Install the Vulkan ICD when an app silently refuses to launch

`vulkan-driver-missing-app-fails-to-start` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** An application that uses Vulkan (Zed, some Electron builds, games, `vkcube`) fails to start on a fresh install with no useful message, or exits immediately. `vulkaninfo` errors out or lists no physical devices.

**Cause.** The Vulkan ICD loader is installed but no vendor Vulkan driver is — a very common gap on Intel iGPU laptops, where `mesa` alone does not provide the Vulkan ICD.

> ⚠️ **Risk.** `lib32-*` packages come from the `multilib` repository — if it is not enabled in `/etc/pacman.conf` the install will fail with 'target not found' rather than doing anything dangerous.

**Fix.**

```bash
sudo pacman -S --needed vulkan-icd-loader vulkan-tools

# Intel iGPU / Arc:
sudo pacman -S --needed vulkan-intel lib32-vulkan-intel
# AMD:
sudo pacman -S --needed vulkan-radeon lib32-vulkan-radeon
# NVIDIA proprietary: the ICD ships with nvidia-utils
sudo pacman -S --needed nvidia-utils lib32-nvidia-utils

# 32-bit support (Steam/Proton/Wine) also needs:
sudo pacman -S --needed lib32-vulkan-icd-loader
```

Check what is actually registered:

```bash
ls /usr/share/vulkan/icd.d/
vulkaninfo | head -30
vkcube
```

On a multi-GPU box you can force a specific device (needs `vulkan-mesa-implicit-layers`):

```bash
MESA_VK_DEVICE_SELECT=list vulkaninfo
MESA_VK_DEVICE_SELECT=<vendorID>:<deviceID>! <command>
```

**Verify.** `vulkaninfo | grep deviceName` names your GPU, `vkcube` renders a spinning cube, and the application launches.

Sources: <https://github.com/basecamp/omarchy/issues/1441> · <https://wiki.archlinux.org/title/Vulkan>

---

## Fix Electron/Chromium apps stalling for a minute after boot on hybrid Intel+NVIDIA

`igpu-electron-stall-i915-module-order` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** On an Intel iGPU + NVIDIA dGPU laptop, the first launch of VS Code, Discord, Chromium etc. after boot hangs for up to a minute with a blank window before it finally appears. Later launches are fine.

**Cause.** When the NVIDIA modules are loaded from the initramfs before `i915`, Electron/CEF apps enumerate the NVIDIA device first and block waiting on it before falling back to the iGPU.

> ⚠️ **Risk.** Rebuilding the initramfs; keep the fallback boot entry available in case of a typo in the MODULES array.

**Fix.**

Load `i915` before the NVIDIA modules in the initramfs.

```bash
sudo tee /etc/mkinitcpio.conf.d/nvidia.conf >/dev/null <<'EOF'
MODULES+=(i915 nvidia nvidia_modeset nvidia_uvm nvidia_drm)
EOF

sudo mkinitcpio -P
reboot
```

If your `MODULES=(...)` array lives in `/etc/mkinitcpio.conf` directly, edit it there so that `i915` comes first in the list.

**Verify.** After a reboot, `time chromium --version` and the first cold launch of an Electron app return promptly. `lsinitcpio /boot/initramfs-linux.img | grep -E 'i915|nvidia'` shows both present.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.archlinux.org/title/NVIDIA>

---

## Fix hibernation that cold-boots instead of resuming on NVIDIA

`nvidia-early-kms-breaks-hibernation` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** You hibernate (`systemctl hibernate`), and on power-on the machine boots normally instead of restoring the session — every application is gone, as if you had shut down. This started after adding the NVIDIA modules to the initramfs to fix a black screen.

**Cause.** Early KMS loads `nvidia`/`nvidia_modeset`/`nvidia_uvm`/`nvidia_drm` from the initramfs. At that stage the driver has no access to `NVreg_TemporaryFilePath` (where the preserved video memory lives), so video-memory preservation — which is on by default on Arch — cannot work across hibernation, and the resume is abandoned.

> ⚠️ **Risk.** You are rebuilding the initramfs. If the boot then black-screens before Hyprland (the very problem early KMS was added to solve), boot the fallback initramfs entry and re-add the modules.

**Fix.**

Drop early module loading (you almost never need it once `nvidia_drm modeset=1` is set via modprobe.d):

```bash
sudo rm /etc/mkinitcpio.conf.d/nvidia.conf     # Omarchy writes this file
```

If the modules are listed directly in `/etc/mkinitcpio.conf`, edit the `MODULES=(...)` array and remove `nvidia nvidia_modeset nvidia_uvm nvidia_drm`. Then:

```bash
sudo mkinitcpio -P
```

Keep `/etc/modprobe.d/nvidia.conf` with `options nvidia_drm modeset=1` — modeset still works with late loading; only the *early* load is removed. Reboot and re-test hibernate.

**Verify.** `lsinitcpio /boot/initramfs-linux.img | grep nvidia` returns nothing, `cat /sys/module/nvidia_drm/parameters/modeset` still returns `Y`, and `systemctl hibernate` followed by power-on restores your session.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks>

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

**Cause.** Adaptive Backlight Management / Panel Power Savings. `power-profiles-daemon` and `tuned` now enable PPS in aggressive power modes, which instructs the AMD GPU to reduce colour accuracy to save power.

> ⚠️ **Risk.** Slightly higher panel power draw on battery. Bootloader edits can break boot; recover from the boot menu editor.

**Fix.**

Disable ABM with a kernel parameter:

```
amdgpu.abmlevel=0
```

- systemd-boot: append to `options` in `/boot/loader/entries/*.conf`
- Limine: append to `cmdline:` in `/boot/limine.conf`
- GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

Reboot. (You can also simply avoid the most aggressive power profile, but the kernel parameter is permanent.)

**Verify.** `cat /proc/cmdline` contains `amdgpu.abmlevel=0`; colours stay consistent when you switch power profiles or unplug the charger.

Sources: <https://wiki.archlinux.org/title/AMDGPU>

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
