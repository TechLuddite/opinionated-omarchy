# Power, suspend & thermal

37 problems. Sorted by severity, then by how often users hit it.

## Fix hibernation that powers off but boots a fresh session instead of resuming

`hibernate-resume-hook-missing-or-misordered` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `limine`, `manjaro`, `mkinitcpio`, `omarchy`

**Symptom.** Hibernate works — the machine writes to disk and powers off cleanly — but on the next boot it just boots normally and my session is gone. No error message anywhere obvious.

**Cause.** The initramfs never attempted the resume. With a busybox-based initramfs the `resume` hook is missing from `HOOKS`, or it is placed after `filesystems` (too late — the root filesystem has already been mounted read-write, and resuming on top of that would corrupt it, so the kernel skips it). It must come after the hooks that provide the block device (`udev`, `encrypt`, `lvm2`) and before `filesystems`.

> ⚠️ **Risk.** A malformed HOOKS array produces an initramfs that cannot mount root — an unbootable system. Keep the previous initramfs or a fallback boot entry, and have installation media on hand before regenerating.

**Fix.**

Inspect the effective HOOKS line:

```bash
grep -h '^HOOKS' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
```

Move `resume` into place, e.g.:

```
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt lvm2 resume filesystems fsck)
```

Regenerate:

```bash
sudo mkinitcpio -P          # Arch / EndeavourOS / CachyOS
sudo limine-mkinitcpio      # Omarchy (rebuilds the UKI and boot entries)
```

If you use the **systemd-based** initramfs (the `systemd` hook rather than `udev`), the resume mechanism is already built in and you should **not** add a `resume` hook at all — check `resume=`/`resume_offset=` instead.

Also confirm the kernel is told where the image lives:

```bash
cat /proc/cmdline | tr ' ' '\n' | grep -E 'resume'
```

**Verify.** After a hibernate/power-on cycle, `journalctl -b | head` shows the session continuing rather than a fresh boot, and `systemd-analyze` reports no full startup. `lsinitcpio /boot/initramfs-linux.img | grep resume` lists the hook.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://github.com/basecamp/omarchy/issues/8471>

---

## Fix a total hang on the second suspend caused by Intel Wi-Fi firmware

`iwlwifi-hang-on-second-suspend` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `omarchy`

**Symptom.** First suspend/resume is fine. The second suspend — often a lid close — hangs the machine completely and only a hard power-off recovers it. The journal is full of:
`iwlwifi 0000:00:14.3: Failed to run INIT ucode: -110`
repeated dozens of times over 30 seconds before the freeze.

**Cause.** After the first resume the Intel Wi-Fi driver fails to reinitialise its firmware and enters an indefinite retry loop. When logind starts another suspend while that loop is running, the suspend never completes and the system deadlocks.

> **Audit corrected this record.** The problem is real and correctly described — basecamp/omarchy#8461 reports repeated "Failed to run INIT ucode: -110" after the first resume on ThinkPad X1 / Intel AX hardware, with a second suspend during the retry loop hanging the machine, and proposes both the sleep hook and enable_ini=N. The sleep-hook path and pre/post arguments match systemd-sleep(8). Two gaps make the fix miss on current hardware: newer Intel parts (BE200/BE201 and recent AX on current kernels) bind to iwlmld rather than iwlmvm, so `modprobe -r iwlmvm iwlwifi` fails with "Module iwlwifi is in use" and the hook silently does nothing; and `options iwlwifi power_save=0` is the older knob — the effective one for MVM devices is iwlmvm power_scheme=1. The hook also has no error handling, so a failed unload is invisible.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Scripts placed in `/usr/lib/systemd/system-sleep/` sit in a package-owned directory and can be removed by a systemd upgrade — re-check after major updates. Unloading iwlwifi drops any active VPN or network mount at suspend time.

**Fix.**

Check which sub-driver your card actually uses before writing the hook:

```bash
lsmod | grep -E '^iwl'
```

Unload whichever of iwlmvm/iwlmld/iwldvm is present, then iwlwifi, and log failures instead of swallowing them:

```bash
sudo tee /etc/systemd/system-sleep/iwlwifi.sh <<'EOF'
#!/bin/sh
case $1 in
  pre)
    /usr/bin/modprobe -r iwlmld iwlmvm iwldvm 2>/dev/null
    /usr/bin/modprobe -r iwlwifi || echo "iwlwifi unload failed" >&2
    ;;
  post)
    /usr/bin/modprobe iwlwifi
    ;;
esac
EOF
sudo chmod +x /etc/systemd/system-sleep/iwlwifi.sh
```

(/etc/systemd/system-sleep/ is the admin directory; /usr/lib/systemd/system-sleep/ also works but belongs to packages.)

Verify it runs and that the unload succeeds — if NetworkManager holds the interface, the unload fails and the hook is useless:

```bash
systemctl suspend
journalctl -b -u systemd-suspend.service | grep -i iwl
```

If the unload fails, take the interface down first in the `pre` branch (`nmcli radio wifi off`) and bring it back in `post`.

For the modprobe options, set both — power_save is the iwlwifi-level knob, power_scheme=1 is the one that matters for MVM/MLD devices:

```
# /etc/modprobe.d/iwlwifi.conf
options iwlwifi enable_ini=N power_save=0
options iwlmvm power_scheme=1
```

```bash
sudo mkinitcpio -P      # or sudo limine-mkinitcpio on Omarchy, only if iwlwifi is in the initramfs
```

**Verify.** Do three suspend/resume cycles in a row. `journalctl -b -k | grep iwlwifi` shows no `Failed to run INIT ucode` retry storm, and `nmcli device` shows the interface back up after each resume.

Sources: <https://github.com/basecamp/omarchy/issues/8461> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Power_management>

---

## Fix a black or frozen screen after ordinary suspend on AMD graphics

`amdgpu-black-screen-on-resume-from-suspend` · severity: **high** · frequency: **very-common** · applies to: `amd`, `amdgpu`, `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** I close the lid (or suspend the desktop), open it again, and the screen stays black. The machine is clearly alive — the Caps Lock LED toggles, I can SSH in, music keeps playing — but nothing ever draws. Sometimes the panel comes back but frozen or full of corruption. `journalctl -b -1 -k` has:

```
amdgpu 0000:03:00.0: amdgpu: SMU: I'm not done with your previous command: SMN_C2PMSG_66:0x0000003A
amdgpu 0000:03:00.0: amdgpu: RunBtc failed!
amdgpu 0000:03:00.0: amdgpu: Failed to setup smc hw!
amdgpu 0000:03:00.0: amdgpu: resume of IP block <smu> failed -62
[drm:dc_dmub_srv_wait_idle] *ERROR* [CRTC:82:crtc-0] flip_done timed out
```

**Cause.** Several distinct amdgpu resume bugs land on the same symptom. On laptop eDP panels the usual culprit is PSR (Panel Self Refresh): the panel keeps showing its own stale frame and the display controller never re-arms after resume, producing `flip_done timed out`. On dGPUs the SMU (power-management microcontroller) can fail to re-initialise, giving `resume of IP block <smu> failed`. A third variant is scatter-gather display on APUs, which flickers white or stays blank when the framebuffer is re-created. All three are workaround-able from the kernel command line, and several have been fixed and re-broken across kernel releases — one Arch BBS report was resolved purely by moving from 6.16.7 to 6.16.10.

> ⚠️ **Risk.** `amdgpu.runpm=0` stops the discrete GPU from powering down at runtime — on a hybrid-graphics laptop that costs several watts of idle battery and makes the machine run hotter, so only keep it if it is genuinely the fix. Editing `/etc/default/limine` and running `limine-update` rewrites your boot entries: keep the Limine menu visible (do NOT enable Setup > Direct Boot while you are experimenting) so you can pick the fallback or a snapshot entry if the machine stops booting. Prefer testing at the menu with `e` before committing anything to the file.

**Fix.**

**1. Confirm which failure you have**

```bash
sudo journalctl -b -1 -k --no-pager | grep -iE 'amdgpu|drm|flip_done|PM: suspend'
```

**2. Try the parameter live at the boot menu first — no config edits, nothing to undo**

At the Limine menu press `e`, append to the `cmdline:` line, and boot:

```
amdgpu.dcdebugmask=0x10
```

`0x10` disables PSR v1 and Panel-Self-Refresh-Selectively-Updated. If it is not enough, try `amdgpu.dcdebugmask=0x12`, which additionally disables memory stutter mode.

Other candidates, one at a time:

- `amdgpu.sg_display=0` — APUs/laptops that flicker white or blank when a display is (re-)attached.
- `amdgpu.runpm=0` — discrete AMD cards that vanish or fail to come back after being powered down.

**3. Make the winning parameter permanent on Omarchy (Limine + UKI)**

Edit `/etc/default/limine` and add a line — use `+=` so you append to what Omarchy already sets:

```bash
sudo nano /etc/default/limine
```

```sh
KERNEL_CMDLINE[default]+=" amdgpu.dcdebugmask=0x10"
```

Then regenerate:

```bash
sudo limine-update
sudo reboot
```

On GRUB systems instead: add it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`. On systemd-boot: append it to `/etc/kernel/cmdline` or the entry's `options` line.

**4. If no parameter helps, it is a kernel regression — bisect the kernel, do not keep guessing**

```bash
sudo pacman -S linux-lts linux-lts-headers
sudo limine-update      # adds a linux-lts entry to the boot menu
```

Reboot into `linux-lts` from the Limine menu. If resume works there, stay on it until the mainline fix lands, and re-test after each `omarchy update`.

**5. Firmware**

AMD laptop resume bugs are frequently EC/BIOS-side. Check for an update:

```bash
sudo fwupdmgr refresh --force && sudo fwupdmgr get-updates
```

On Omarchy this is also exposed as Update > Firmware.

**Verify.** `cat /proc/cmdline` shows the parameter after reboot. Run three suspend/resume cycles (`sudo systemctl suspend`, wake, repeat) and then `sudo journalctl -b -k | grep -iE 'flip_done|resume of IP block|SMU'` — a clean run has no matches, and `grep -c 'PM: suspend exit' <<< "$(journalctl -b -k)"` counts the resumes that completed.

Sources: <https://wiki.archlinux.org/title/AMDGPU> · <https://bbs.archlinux.org/viewtopic.php?id=309052> · <https://wiki.archlinux.org/title/Kernel_parameters> · <https://wiki.archlinux.org/title/Limine> · <https://raw.githubusercontent.com/basecamp/omarchy/master/default/limine/default.conf>

---

## Stop a laptop draining its battery while suspended (s2idle instead of S3)

`battery-drains-overnight-s2idle-no-deep-sleep` · severity: **high** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `omarchy`

**Symptom.** I close the lid at 100% and eight hours later the battery is at 30-40%, or the laptop is warm inside the bag. `cat /sys/power/mem_sleep` prints `[s2idle] shallow deep` or only `[s2idle]`.

**Cause.** The machine is using suspend-to-idle (S0ix / "Modern Standby") rather than S3 suspend-to-RAM. On many laptops the platform never actually reaches the deep S0i3 substate — a device keeps a runtime-PM reference or the EC keeps generating wakeups — so the CPU idles at a high power floor all night.

> ⚠️ **Risk.** S3 is unvalidated by many vendors on post-2020 laptops — forcing `deep` can produce a machine that suspends but never resumes (black screen, hard power off, unsaved work lost). Test several cycles with nothing important open before trusting it.

**Fix.**

First check what the hardware advertises:

```bash
cat /sys/power/mem_sleep
```

If `deep` is listed, test it for a few cycles:

```bash
echo deep | sudo tee /sys/power/mem_sleep
systemctl suspend
```

Make it permanent:

```ini
# /etc/systemd/sleep.conf.d/mem-deep.conf
[Sleep]
MemorySleepMode=deep
```

or use the `mem_sleep_default=deep` kernel parameter (on Omarchy: `/etc/limine-entry-tool.d/deep-sleep.conf` with `KERNEL_CMDLINE[default]+=" mem_sleep_default=deep"`, appended to `/etc/default/limine`, then `sudo limine-mkinitcpio`).

If `deep` is **not** listed, look in the UEFI setup for a sleep-state option ("S3/Modern Standby support", "Windows 10" vs "Linux S3"). If there is none, stop fighting it and use suspend-then-hibernate instead (see the suspend-then-hibernate record).

Embedded-controller wakeups are a second common drain on s2idle machines:

```bash
cat /sys/module/acpi/parameters/ec_no_wakeup   # Y = EC wakeups suppressed
```

Set the `acpi.ec_no_wakeup=1` kernel parameter if it reads `N` and you do not rely on EC-driven wake.

**Verify.** `cat /sys/power/mem_sleep` shows `s2idle shallow [deep]`. Note `cat /sys/class/power_supply/BAT0/capacity` before and after an hour of sleep — a healthy S3 laptop loses roughly 1%/hour or less.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers> · <https://man.archlinux.org/man/systemd-sleep.conf.5.en>

---

## Stop the machine waking instantly from suspend via the USB controller

`suspend-instant-wake-usb-controller` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** I hit suspend, the screen goes black and the fans stop for about a second, then the machine wakes straight back up. `journalctl -b -1 -k` shows:
`PM: Some devices failed to suspend, or early wake event detected`
and just above it `xhci_hcd 0000:02:00.0: PM: failed to suspend async: error -16`.

**Cause.** An ACPI wakeup source is armed on the USB host controller (or on a device attached to it, e.g. a Logitech Unifying/Bolt receiver or a USB dock). Buggy firmware asserts a wake event as soon as the xHCI controller enters D3, so the kernel aborts the suspend and immediately resumes. On some Intel Haswell/LynxPoint chipsets this is a known firmware bug the kernel only denylists case by case.

> **Audit corrected this record.** The diagnosis, the sysfs paths and both udev rules are correct. The gap is that writing to /proc/acpi/wakeup is a TOGGLE, not a set: `echo XHC > /proc/acpi/wakeup` flips the current state. If XHC is already disabled the command re-ARMS it (making things worse), and if the string does not exist on that board the write silently does nothing. The record never says this, and a user pasting the line twice undoes their own fix. Also, `echo disabled > /sys/bus/usb/devices/usb1/power/wakeup` disables wake for the root hub only if usb1 is the right bus — it should be picked, not assumed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Disabling wakeup on the USB controller also kills wake-on-keyboard and wake-on-mouse — you will need the power button to wake the machine. Do not disable the one source you rely on to wake it.

**Fix.**

1. List the armed sources and note the Status column:

```bash
cat /proc/acpi/wakeup
```

The write below is a TOGGLE, not a set. Only echo a device that currently reads `*enabled`, and never run it twice — a second write re-arms it. Verify after every write:

```bash
# only if XHC currently shows *enabled
sudo sh -c 'echo XHC > /proc/acpi/wakeup'
grep -E '^(XHC|EHC)' /proc/acpi/wakeup   # confirm it now reads *disabled
systemctl suspend
```

2. Make it permanent with the idempotent sysfs attribute (this one is a set, not a toggle). Take KERNEL from the `Sysfs node` column with the `pci:` prefix stripped:

```
# /etc/udev/rules.d/90-disable-usb-wakeup.rules
ACTION=="add", SUBSYSTEM=="pci", KERNEL=="0000:00:14.0", ATTR{power/wakeup}="disabled"
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=pci
```

3. To blame one USB device instead, find the right node first rather than guessing usb1:

```bash
grep -H . /sys/bus/usb/devices/*/power/wakeup 2>/dev/null | grep enabled
lsusb -t   # map bus/port to the device
echo disabled | sudo tee /sys/bus/usb/devices/usb1/power/wakeup
```

The per-device udev rule as given is correct. Note that disabling wakeup on the xHCI controller also kills wake-on-USB-keyboard/mouse for the whole controller — prefer the per-device rule if you rely on that.

**Verify.** `systemctl suspend` and leave it for 60 seconds — it should stay asleep and wake only on the power button. Compare `grep -F "" /sys/class/wakeup/*/device/power/wakeup_count` before and after a sleep cycle to see which source fired.

Sources: <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Get the right resume_offset for a Btrfs swapfile (filefrag lies)

`hibernate-btrfs-swapfile-wrong-resume-offset` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `grub`, `limine`, `manjaro`, `omarchy`

**Symptom.** Hibernation writes the image and powers off, but the machine always boots fresh. I got `resume_offset` from `filefrag -v` as every guide says. Or the Omarchy setup left `resume_offset="` empty in `/etc/limine-entry-tool.d/resume.conf`.

**Cause.** On Btrfs, `filefrag`'s `physical_offset` is an address in Btrfs's virtual address space, not the real on-disk offset, because Btrfs supports multiple devices. The kernel resume code needs the true physical offset, so a `filefrag`-derived value silently points at the wrong blocks.

> **Audit corrected this record.** The Btrfs diagnosis is exactly right and `sudo btrfs inspect-internal map-swapfile -r` is what omarchy-hibernation-setup itself uses (RESUME_OFFSET=$(sudo btrfs inspect-internal map-swapfile -r "$SWAP_FILE")). The Limine drop-in commands match the real script. But the no-reboot test at the end has the two sysfs writes in the WRONG ORDER: writing to /sys/power/resume triggers the resume attempt immediately, so it must be written last, after resume_offset. As printed, the offset is applied to a resume that has already been attempted with offset 0 — the test appears to fail even when the values are right, and on a machine with a stale image it can attempt a resume from the wrong blocks.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A wrong `resume_offset` points the kernel at arbitrary blocks on the swap device. It normally just fails to resume, but never point `resume=` at a partition that is not actually swap — that risks writing the hibernation image over a filesystem.

**Fix.**

Everything above the no-reboot test is correct. Replace only that block — resume_offset MUST be written before resume, because the write to /sys/power/resume is what triggers the resume attempt:

```bash
# offset FIRST
echo 198122980 | sudo tee /sys/power/resume_offset
# device LAST - this write triggers the resume attempt
lsblk -o NAME,MAJ:MIN,SIZE   # e.g. nvme0n1p2 -> 259:2
echo 259:2 | sudo tee /sys/power/resume
```

Also worth adding: `btrfs inspect-internal map-swapfile` only produces a usable offset on a single-device Btrfs filesystem — hibernation to a swapfile on a multi-device Btrfs volume is not supported by the kernel at all. Check with `sudo btrfs filesystem show` before spending time on the offset.

And verify the result actually reached the kernel after rebuilding:

```bash
cat /proc/cmdline | tr ' ' '\n' | grep -E 'resume'
```

**Verify.** `cat /proc/cmdline` shows both `resume=` and a non-empty `resume_offset=`, and a hibernate/power-on cycle restores the session.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-setup>

---

## Make hibernation resume work on a LUKS-encrypted install

`hibernate-encrypted-root-resume-mapper-device` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `laptop`, `luks`, `manjaro`, `omarchy`

**Symptom.** Full-disk-encrypted laptop. `systemctl hibernate` writes the image and powers off properly, but on the next boot I type the LUKS passphrase and land in a brand-new session — everything is gone. Sometimes the initramfs prints `ERROR: resume: hibernation device '/dev/nvme0n1p3' not found` or hangs on `Waiting 10 seconds for device /dev/mapper/cryptswap ...` and then boots normally anyway.

**Cause.** Three separate mistakes, all of which produce the same silent 'fresh boot' result. (a) `resume=` points at the raw LUKS partition. That partition contains ciphertext and has no swap header, so the kernel finds no hibernation image — `resume=` must name the *decrypted* device-mapper node. (b) With the busybox `encrypt` hook, the `resume` hook runs before the container is unlocked. The Arch wiki is explicit: when swap sits on stacked storage (dm-crypt, LVM, RAID) the `resume` hook must be placed *after* `encrypt`/`lvm2`, and after `udev`. (c) The swap device is set up in `/etc/crypttab` with the `swap` option, i.e. re-encrypted with a random key from `/dev/urandom` on every boot. That deliberately makes suspend-to-disk impossible — the key that encrypted the image was thrown away at shutdown.

> **Audit corrected this record.** The diagnosis is correct and well sourced — the random-key crypttab swap, resume= pointing at the mapper node, and 'the resume hook must be placed after encrypt or lvm2' are all on wiki.archlinux.org/title/Power_management/Suspend_and_hibernate; the filefrag awk one-liner and `btrfs inspect-internal map-swapfile -r` (including the 198122980 example) are verbatim from it, as are the /sys/power/resume major:minor and /sys/power/resume_offset test steps. Two substantive problems. (1) For a SEPARATE encrypted swap partition, reordering the hooks is NOT enough. dm-crypt/Swap encryption is explicit: 'If the swap device is on a different device from that of the root file system, it will not be opened by the encrypt hook' and 'the encrypt hook ... can only unlock a single device'. A user who follows step 2's `cryptdevice=UUID=...:cryptroot ... resume=/dev/mapper/cryptswap` plus step 3's hook reorder will still land in a fresh boot, because /dev/mapper/cryptswap never exists in early userspace. (2) The record never mentions that Omarchy already ships the whole procedure: bin/omarchy-hibernation-setup (`omarchy hibernation setup`) creates /swap/swapfile on the encrypted Btrfs root, adds it to fstab, writes `HOOKS+=(resume)` to /etc/mkinitcpio.conf.d/omarchy_resume.conf, computes resume=/resume_offset= into /etc/limine-entry-tool.d/resume.conf, and rebuilds. Also, `sudo limine-update` followed by `sudo limine-mkinitcpio` is redundant — upstream's own comment in that script says limine-mkinitcpio 'rebuilds initramfs/UKI for all kernels and updates the /boot/limine.conf entries', and limine-update 'would also re-deploy the binary and rebuild a second time'.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing HOOKS is how people make a machine unbootable. If you drop or misplace `encrypt`/`sd-encrypt`, the initramfs cannot unlock root and you get an emergency shell with no way in — have an Arch/Omarchy live USB ready before you rebuild, and note that Omarchy's Limine snapshot entries do not help here because the initramfs/UKI is outside the snapshot. Removing a `/etc/crypttab` swap line without also removing or fixing the matching `/etc/fstab` entry leaves a failing swap unit that can block boot. Reformatting a partition that was previously a LUKS container to use as plain swap destroys whatever was on it.

**Fix.**

Add before step 1, for Omarchy:

**0. On Omarchy, do not hand-roll this.** The supported path handles the encrypted-root case end to end:

```bash
omarchy hibernation setup          # bin/omarchy-hibernation-setup
```

It creates /swap/swapfile on the encrypted Btrfs root, adds it to /etc/fstab, writes `HOOKS+=(resume)` to /etc/mkinitcpio.conf.d/omarchy_resume.conf, computes `resume=`/`resume_offset=` into /etc/limine-entry-tool.d/resume.conf (and /etc/default/limine), and runs `limine-mkinitcpio`. Undo with `omarchy hibernation remove`. Read the rest of this record only if that fails or you are on plain Arch.

Rewrite step 3 to add the missing constraint:

**3b. A separate encrypted swap partition needs to be UNLOCKED in the initramfs, not just ordered.** The busybox `encrypt` hook unlocks exactly one device (the one named by `cryptdevice=`), so `resume=/dev/mapper/cryptswap` refers to a node that does not exist yet no matter where you put `resume`. Pick one:

- **Preferred:** switch to the systemd initramfs and list both containers, then drop `resume` entirely:

```
/etc/crypttab.initramfs
cryptroot UUID=<root-luks-uuid>  none
cryptswap UUID=<swap-luks-uuid>  none
```
```
HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block sd-encrypt lvm2 filesystems fsck)
```

- Or put swap inside the *same* LUKS container (LVM logical volume, or a swapfile on the encrypted root — the swapfile variant in step 2 is the one that works with the plain `encrypt` hook).
- Or install `mkinitcpio-openswap` (AUR) / write an `openswap` hook that runs `cryptsetup open` before `resume`.

And in step 4, drop `sudo limine-update` — `sudo limine-mkinitcpio` alone rebuilds the initramfs/UKI for every kernel and regenerates the Limine entries; running both does the work twice.

**Verify.** After reboot, `cat /sys/power/resume` must print a non-zero `major:minor` matching the mapper device from `lsblk -o NAME,MAJ:MIN`, and `cat /sys/power/resume_offset` must match your swapfile offset. Hibernate, power on, and check `sudo journalctl -b -k | grep -i 'PM: Image'` — a real resume logs `PM: Image loading progress` / `PM: Image loading done`. `grep -h '^HOOKS' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf` should show `resume` after `encrypt`.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Dm-crypt/System_configuration> · <https://wiki.archlinux.org/title/Dm-crypt/Swap_encryption> · <https://wiki.archlinux.org/title/Limine> · <https://raw.githubusercontent.com/basecamp/omarchy/master/default/limine/default.conf>

---

## Fix Omarchy's resume hook always landing after `filesystems`

`omarchy-resume-hook-appended-after-filesystems` · severity: **high** · frequency: **common** · applies to: `btrfs`, `laptop`, `limine`, `mkinitcpio`, `omarchy`

**Symptom.** On Omarchy I ran the hibernation setup, it reported success, hibernation powers the machine off — but it never resumes. `grep -h '^HOOKS' /etc/mkinitcpio.conf.d/*.conf` shows `resume` sitting at the very end of the array, after `filesystems` and `fsck`.

**Cause.** Two mkinitcpio drop-ins fight each other. `omarchy_hooks.conf` (shipped by `omarchy-settings`) *assigns* the array with `HOOKS=(...)`, and `omarchy_resume.conf` (written by `omarchy-hibernation-setup`) *appends* with `HOOKS+=(resume)`. Drop-ins are read in alphabetical order, so the append always runs last and `resume` can never be positioned before `filesystems`.

> ⚠️ **Risk.** You are hand-writing the full HOOKS array — omitting `encrypt`, `btrfs-overlayfs` or `filesystems` makes the machine unbootable. Copy the existing line verbatim and move only `resume`. Take an Omarchy system snapshot first.

**Fix.**

Replace the append with an explicit, correctly ordered array in a drop-in that sorts last. First print the current array:

```bash
grep -h '^HOOKS' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
```

Take that line, delete the trailing `resume`, and reinsert `resume` immediately after `encrypt` (or after `udev`/`block` if the disk is not encrypted) — everything before `filesystems`. Then:

```bash
sudo rm /etc/mkinitcpio.conf.d/omarchy_resume.conf
sudo tee /etc/mkinitcpio.conf.d/zz_resume.conf <<'EOF'
# full array copied from above, with resume moved before filesystems
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt resume filesystems fsck btrfs-overlayfs)
EOF
sudo limine-mkinitcpio
```

Double-check the resume target survived:

```bash
cat /etc/limine-entry-tool.d/resume.conf
cat /proc/cmdline | tr ' ' '\n' | grep resume
```

**Verify.** `grep -h '^HOOKS' /etc/mkinitcpio.conf.d/*.conf` shows `resume` before `filesystems`, and a hibernate/power-on cycle restores the running session.

Sources: <https://github.com/basecamp/omarchy/issues/8471> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-setup> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Recover a Hyprland screen that never comes back after DPMS off

`screen-never-wakes-after-dpms-off` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** I bound a key to `hyprctl dispatch dpms off` and now the display is dead — keyboard and mouse do nothing to bring it back, and I have to hard-reboot. Or: after hypridle blanks the screen it never turns back on when I move the mouse.

**Cause.** `dpms off` used as a direct keybind is explicitly not recommended: nothing is registered to turn it back on, so there is no path back. In an idle daemon the same thing happens if a listener has `on-timeout = hyprctl dispatch dpms off` without the matching `on-resume`.

**Fix.**

Never bind `dpms off` directly. Drive it from hypridle with a paired resume action:

```ini
# ~/.config/hypr/hypridle.conf
general {
    lock_cmd = pidof hyprlock || hyprlock
    before_sleep_cmd = loginctl lock-session
    after_sleep_cmd = hyprctl dispatch dpms on
}

listener {
    timeout = 300
    on-timeout = loginctl lock-session
}

listener {
    timeout = 600
    on-timeout = hyprctl dispatch dpms off
    on-resume = hyprctl dispatch dpms on
}

listener {
    timeout = 900
    on-timeout = systemctl suspend
}
```

**Recovering a currently-dead screen without rebooting** — switch to a TTY with `Ctrl+Alt+F2`, log in, and run blind:

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t $XDG_RUNTIME_DIR/hypr | head -1)
hyprctl dispatch dpms on
```

then `Ctrl+Alt+F1` back. The same commands work over SSH from another machine.

**Verify.** After the idle timeout the screen blanks and a keypress brings it straight back. `hyprctl monitors | grep -i dpms` reports the monitors as on.

Sources: <https://wiki.archlinux.org/title/Hyprland> · <https://wiki.hypr.land/Hypr-Ecosystem/hypridle/> · <https://github.com/hyprwm/Hyprland/issues?q=is%3Aissue+monitors+not+waking+after+suspend>

---

## Fix suspend failing outright on an NVIDIA machine

`suspend-fails-nvidia-video-memory` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Suspend aborts and the machine stays awake (or wakes instantly). `journalctl -k` shows:
```
NVRM: GPU 0000:01:00.0: PreserveVideoMemoryAllocations module parameter is set. System Power Management attempted without driver procfs suspend interface. Please refer to the 'Configuring Power Management Support' section in the driver README.
PM: pci_pm_suspend(): nv_pmops_suspend+0x0/0x20 [nvidia] returns -5
nvidia 0000:01:00.0: PM: failed to suspend async: error -5
```

**Cause.** The NVIDIA driver is set to preserve all video memory across suspend, but the mechanism that actually saves it is not active. There are two such mechanisms and the discriminator is **which kernel modules are in use, not a driver version cut-off**: with the open kernel modules the driver registers a suspend notifier, enabled by `NVreg_UseKernelSuspendNotifiers=1`; otherwise it is the `nvidia-suspend` / `nvidia-hibernate` / `nvidia-resume` systemd services, which the current driver README still documents as installed and enabled by default. Disabling those services on a proprietary-module machine breaks suspend rather than fixing it.

> **Audit corrected this record.** The symptom, the NVRM message and the general cause are real, and NVreg_UseKernelSuspendNotifiers genuinely exists (nv-reg.h: "If enabled, this option prompts the NVIDIA kernel module to register a notifier that saves and restores all video memory allocations across system power management cycles if PreserveVideoMemoryAllocations is enabled. 0: Suspend notifiers are not used (default), 1: Suspend notifiers are used when available"). But the '430-590 vs 595+' version boundary is fabricated precision and the instruction to DISABLE the three services on '595+' is actively harmful. The current driver README (610.57.04, matching Arch's nvidia-utils 610.57.04-1) says the notifier path applies "When the open kernel modules are in use" and still documents nvidia-suspend/hibernate/resume as installed and enabled by default. The discriminator is open vs proprietary modules, not a version cut-off; blindly masking the services on a proprietary-driver box will break suspend rather than fix it.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** If you use early KMS (the `nvidia` module loaded from the initramfs) the driver has no access to `NVreg_TemporaryFilePath`, so hibernation cannot preserve VRAM — do not use early KMS if you need hibernation. Changing modprobe options requires regenerating the initramfs or the setting silently does not apply.

**Fix.**

Find out which module flavour you are on — that, not the version number, decides the mechanism:

```bash
nvidia-smi --query-gpu=driver_version --format=csv,noheader
modinfo -F license nvidia            # "Dual MIT/GPL" = open modules; "NVIDIA" = proprietary
pacman -Qs 'nvidia-open|^nvidia '
sudo sort /proc/driver/nvidia/params | grep -E 'UseKernelSuspendNotifiers|PreserveVideoMemoryAllocations|TemporaryFilePath'
systemctl is-enabled nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
```

**Proprietary modules (nvidia / nvidia-dkms) — the default, and the case for most users.** The three services ARE the mechanism; they drive /proc/driver/nvidia/suspend. They ship enabled. If you disabled them, put them back:

```bash
sudo systemctl enable nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
```

Do NOT disable them and do NOT set NVreg_UseKernelSuspendNotifiers here.

**Open kernel modules (nvidia-open / nvidia-open-dkms).** The kernel suspend notifier can handle it instead:

```
# /etc/modprobe.d/nvidia-power.conf
options nvidia NVreg_PreserveVideoMemoryAllocations=1 NVreg_UseKernelSuspendNotifiers=1 NVreg_TemporaryFilePath=/var/tmp
```

Only then, and only after confirming suspend works, is it safe to drop the services. Change one thing at a time and test a suspend cycle between each.

Either way, rebuild the initramfs if the nvidia modules are in it:

```bash
sudo mkinitcpio -P     # or sudo limine-mkinitcpio on Omarchy
```

The VRAM dump target must support unnamed temporary files (O_TMPFILE — ext4, XFS and Btrfs all do) and must not be a tmpfs, which is why /var/tmp is used instead of the default /tmp. It needs room for the total VRAM in use:

```bash
nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits
df -h /var/tmp
```

**Verify.** `sudo sort /proc/driver/nvidia/params` shows `UseKernelSuspendNotifiers: 1` (or `PreserveVideoMemoryAllocations: 1` on older drivers) and `TemporaryFilePath: "/var/tmp"`. `systemctl suspend` now completes without the `error -5` lines.

Sources: <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks> · <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers>

---

## Fix a desktop that wakes 1-2 seconds after suspending (GPP/NVMe PCIe bridge)

`suspend-instant-wake-pcie-bridge-desktop` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `manjaro`, `omarchy`

**Symptom.** Desktop suspends — monitor goes off, case RGB stays lit — then it wakes again after a second or two, or it never comes back and needs a hard power off. Common on Gigabyte B550/A520, ASRock B850 AM5 and MSI X870 boards.

**Cause.** The PCIe root port bridging the NVMe drive (`GPP0`, `GPP1`) or the xHCI controller (`XH00`) has ACPI wakeup armed and generates a spurious wake event immediately after entering the sleep state.

> **Audit corrected this record.** Real problem, and the udev rule is right. Two defects in the systemd unit: (a) /proc/acpi/wakeup is a toggle, so a unit that unconditionally echoes GPP0 at every boot will re-ARM the wake source on any boot where firmware already left it disabled — the exact bug it is meant to fix, intermittently; (b) the unit has no `Type=oneshot`/`RemainAfterExit=yes`, so systemd treats it as a simple service that exits immediately and `systemctl status` will show it as dead/failed-looking. `Description="..."` also keeps the literal quotes in systemd unit syntax. The udev rule already does this idempotently and correctly, so the unit is redundant; if kept, it must be made conditional.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A blanket rule such as `SUBSYSTEM=="pci", DRIVER=="pcieport", ATTR{power/wakeup}="disabled"` disables wakeup on every PCIe port, which breaks Wake-on-LAN and wake-from-dock.

**Fix.**

Diagnose the same way:

```bash
cat /proc/acpi/wakeup
```

Toggle it for the current session — only for a device whose Status column currently reads `*enabled`, and verify, since the write flips rather than sets:

```bash
sudo sh -c 'echo GPP0 > /proc/acpi/wakeup'
grep '^GPP0' /proc/acpi/wakeup   # must now read *disabled
systemctl suspend
```

For persistence prefer the udev rule (idempotent, no toggle hazard). Get KERNEL from the `Sysfs node` column with the `pci:` prefix removed:

```
# /etc/udev/rules.d/90-fix-wakeup.rules
ACTION=="add", SUBSYSTEM=="pci", KERNEL=="0000:00:01.1", ATTR{power/wakeup}="disabled"
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=pci
```

If you really want a unit instead, it must be oneshot and must check the current state before toggling:

```ini
# /etc/systemd/system/disable-gpp0-wakeup.service
[Unit]
Description=Disable GPP0 ACPI wakeup to fix instant resume

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'grep -q "^GPP0.*\\*enabled" /proc/acpi/wakeup && echo GPP0 > /proc/acpi/wakeup; exit 0'

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now disable-gpp0-wakeup.service
```

Do not install both the udev rule and an unconditional unit — the second one can toggle the first one's fix back on.

**Verify.** `cat /proc/acpi/wakeup | grep GPP0` shows `*disabled`, and `systemctl suspend` keeps the machine asleep for more than a minute.

Sources: <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Fix a black screen when resuming from hibernation

`black-screen-on-resume-from-hibernate-early-kms` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `manjaro`, `mkinitcpio`, `nvidia`, `omarchy`

**Symptom.** Resume from hibernate leaves a completely black screen — no console, no TTY, the machine is otherwise alive (Caps Lock LED toggles, SSH sometimes works). Resuming from ordinary suspend is fine.

**Cause.** Graphics devices are being initialised inside the initramfs (early KMS / explicit `MODULES=`) before the hibernation image is restored. The device state set up by the initramfs conflicts with the state recorded in the image. It can also be a kernel regression introduced by an update.

> **Audit corrected this record.** The early-KMS-vs-hibernation-image conflict is a real and correctly diagnosed failure mode, and the LTS-kernel and nvidiafb suggestions are reasonable. The defect is Omarchy-specific and this record explicitly claims to apply to Omarchy: it tells the user to edit MODULES= and HOOKS= in /etc/mkinitcpio.conf, but Omarchy ships /etc/mkinitcpio.conf.d/omarchy_hooks.conf which REASSIGNS HOOKS with `=` and is read after the main file — so the edit is silently discarded and the user rebuilds an unchanged initramfs. This is the same drop-in precedence trap the omarchy-resume-hook record documents. The example HOOKS array also drops `kms` while keeping `encrypt`, which on an encrypted root can leave the LUKS passphrase prompt on a blank screen.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Removing the `kms` hook loses flicker-free boot and can change console/plymouth behaviour, and on an encrypted root the password prompt may render at a different resolution. A wrong HOOKS array is unbootable — keep a fallback entry.

**Fix.**

First check where HOOKS is actually coming from — on Omarchy the main config is overridden by a drop-in:

```bash
grep -h '^\(HOOKS\|MODULES\)' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
```

**Arch / EndeavourOS / CachyOS** (no drop-in reassigning HOOKS) — edit /etc/mkinitcpio.conf directly:

```
MODULES=()
HOOKS=(base udev autodetect microcode modconf keyboard keymap consolefont block encrypt resume filesystems fsck)
```

**Omarchy** — editing /etc/mkinitcpio.conf will NOT take effect. Write a drop-in that sorts last, starting from the array the grep above printed and removing only `kms` (keep everything else, including any btrfs-overlayfs hook):

```bash
sudo tee /etc/mkinitcpio.conf.d/zz_no_early_kms.conf <<'EOF'
MODULES=()
# full array from the grep above, with kms removed
HOOKS=(base udev autodetect microcode modconf keyboard keymap consolefont block encrypt resume filesystems fsck btrfs-overlayfs)
EOF
sudo limine-mkinitcpio
```

On either distro, rebuild and confirm the result actually changed:

```bash
sudo mkinitcpio -P          # sudo limine-mkinitcpio on Omarchy
lsinitcpio -a /boot/initramfs-linux.img | head   # or check the UKI was regenerated
```

Caveat the record omits: with an encrypted root, removing `kms` means the LUKS passphrase prompt may render on a black screen on some GPUs — you are typing blind. Test that you can still unlock before relying on it, and be ready to boot the previous entry.

The LTS-kernel and `blacklist nvidiafb` suggestions are fine as written; on Omarchy, `sudo pacman -S linux-lts linux-lts-headers` followed by `sudo limine-mkinitcpio` generates the extra boot entry for you.

**Verify.** Hibernate and resume — the desktop reappears. `journalctl -b | grep -i 'PM: hibernation'` shows a clean restore with no device errors.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks>

---

## Fix hibernation that hangs or reboots instead of powering off

`hibernate-does-not-power-off-hibernatemode-shutdown` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `asus`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `systemctl hibernate` writes the image and then the machine hangs — display dead, keyboard backlight still on, only a forced power-off recovers it — or it reboots instead of shutting down. The last kernel lines are:
```
PM: hibernation: Creating image...
ACPI: PM: Restoring platform NVS memory
```
and nothing after.

**Cause.** The firmware's ACPI S4 sleeping state is unreliable on this board. The image is written correctly, but the platform never completes the transition into S4. Reported on the ASUS ROG Zephyrus G14 (GA403UV) among others.

> ⚠️ **Risk.** With `HibernateMode=shutdown` the machine looks like a normal power-off. If `resume=`/`resume_offset=` are wrong you will boot a fresh session and silently lose everything that was open.

**Fix.**

Tell systemd to write the image and then do a plain shutdown instead of entering S4:

```ini
# /etc/systemd/sleep.conf.d/hibernate-mode.conf
[Sleep]
HibernateMode=shutdown
```

```bash
sudo systemctl daemon-reload
systemctl hibernate
```

The same setting fixes the related "Operating system not found" / wrong-OS-boots case after hibernating from an external disk.

**Verify.** `systemctl hibernate` results in a fully powered-off machine (fans off, no LEDs), and pressing the power button resumes the previous session rather than booting fresh.

Sources: <https://github.com/basecamp/omarchy/issues/8589> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://man.archlinux.org/man/systemd-sleep.conf.5.en>

---

## Fix a 60-second hang on suspend that ends with the machine waking back up

`suspend-hangs-60s-user-slice-freeze` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** Suspend takes about a minute and then the machine wakes itself back up, or it resumes but I can no longer open a new session. The journal shows `Failed to freeze unit 'user.slice'` before sleep, and login attempts fail with:
`pam_systemd(login:session): Failed to create session: Job 9876 for unit 'session-6.scope' failed with 'frozen'`

**Cause.** Since systemd v256, `systemd-sleep` freezes `user.slice` before entering sleep. On some kernels this fails — notably when KVM is in use — leaving cgroups stuck in the frozen state.

> **Audit corrected this record.** The mechanism and the env var are real — systemd's ENVIRONMENT.md documents SYSTEMD_SLEEP_FREEZE_USER_SESSIONS as "Takes a boolean. When true (the default), user.slice will be frozen during sleep. When false it will not be." The four unit names and drop-in paths are correct, and `systemctl thaw user.slice` is a real command. What is missing is the caveat that ships with that same documentation: systemd upstream explicitly recommends against setting it, because disabling the freeze causes undesired behaviour with home-directory encryption and with systemd-suspend-then-hibernate.service — which the suspend-then-hibernate record in this same set tells users to enable. Handing someone a copy-paste loop that silently degrades s2h and homed without saying so is an incomplete fix.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The Arch wiki notes this drop-in can itself prevent some systems from entering sleep at all (an AMD graphics bug). If suspend stops working entirely afterwards, delete the drop-in files and `daemon-reload`.

**Fix.**

Confirm this is actually your failure before changing anything — you want to see the freeze failure in the journal, not just a slow suspend:

```bash
journalctl -b -1 -u systemd-suspend.service | grep -i 'freeze\|user.slice'
```

Unstick a currently frozen session without rebooting:

```bash
sudo systemctl thaw user.slice
```

If KVM/libvirt is involved, try stopping the guests before suspend first — that avoids the workaround entirely.

Only then apply the override. Read this first: systemd upstream advises against this setting; with it disabled you can get incorrect behaviour with encrypted home directories (systemd-homed) and with systemd-suspend-then-hibernate. If you use suspend-then-hibernate, apply the drop-in to the suspend unit only rather than all four:

```bash
for u in systemd-suspend systemd-hibernate systemd-hybrid-sleep systemd-suspend-then-hibernate; do
  sudo mkdir -p "/etc/systemd/system/$u.service.d"
  printf '[Service]\nEnvironment=SYSTEMD_SLEEP_FREEZE_USER_SESSIONS=false\n' \
    | sudo tee "/etc/systemd/system/$u.service.d/nofreeze.conf" >/dev/null
done
sudo systemctl daemon-reload
```

Treat it as a temporary workaround and re-test after kernel/systemd updates — remove the drop-ins with `sudo rm -r /etc/systemd/system/systemd-{suspend,hibernate,hybrid-sleep,suspend-then-hibernate}.service.d/nofreeze.conf` and `daemon-reload`.

**Verify.** `systemctl suspend` enters sleep within a couple of seconds. `journalctl -b | grep -i freeze` shows no `Failed to freeze unit` lines, and `systemctl show user.slice -p FreezerState` reports `FreezerState=running`.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Work around AM5 boards that wake instantly even with all ACPI wakeups disabled

`suspend-instant-wake-gigabyte-acpi-osi` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `limine`, `omarchy`, `systemd-boot`

**Symptom.** Suspend still ends immediately after disabling every entry in `/proc/acpi/wakeup`, including `GPP0`. Seen on Gigabyte B650/B850/X670/X870 and MSI PRO X870E-P WIFI boards.

**Cause.** The board's ACPI tables take a broken code path when the kernel reports itself as a recent Windows version through the `_OSI` interface, and the firmware re-arms a wake source the OS cannot see.

> **Audit corrected this record.** The Omarchy/Limine drop-in mechanism is genuine (omarchy-hibernation-setup does exactly `echo 'KERNEL_CMDLINE[default]+=" ..."' > /etc/limine-entry-tool.d/<name>.conf` then `sudo tee -a /etc/default/limine < "$DROP_IN"`), but the acpi_osi value is BROKEN as written. kernel-parameters.txt is explicit: "Double-quotes can be used to protect spaces in values, e.g.: param=\"spaces in here\"". The record's echo emits `acpi_osi=!Windows 2015` with a bare space, so the kernel parses `acpi_osi=!Windows` (an _OSI string that does not exist) plus a stray `2015` token — the fix silently does nothing. The quotes must survive into the final cmdline. Also `acpi_os_name` is name-dropped with no value or guidance, and there is no warning that a bad cmdline baked into a UKI can leave the machine unbootable.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Changing the reported _OSI string alters which ACPI code paths the firmware takes; fan curves, battery reporting or thermal behaviour can change. Keep a known-good boot entry so you can boot without the parameter.

**Fix.**

The quotes are load-bearing — `acpi_osi=!Windows 2015` without them is parsed as two separate parameters and does nothing.

On Omarchy (Limine + UKI), escape the inner quotes so they land in the generated cmdline:

```bash
sudo mkdir -p /etc/limine-entry-tool.d
printf 'KERNEL_CMDLINE[default]+=" acpi_osi=\\"!Windows 2015\\""\n' \
  | sudo tee /etc/limine-entry-tool.d/acpi-osi.conf
sudo tee -a /etc/default/limine < /etc/limine-entry-tool.d/acpi-osi.conf
sudo limine-mkinitcpio
```

After rebooting, verify the parameter actually arrived intact — if you see `2015` as its own token, the quoting was lost:

```bash
cat /proc/cmdline
dmesg | grep -i 'ACPI: Added _OSI\|ACPI: Deleted _OSI'
```

GRUB: `GRUB_CMDLINE_LINUX_DEFAULT="... acpi_osi=\"!Windows 2015\""` in /etc/default/grub, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`.
systemd-boot: add `acpi_osi="!Windows 2015"` to the `options` line in /boot/loader/entries/*.conf.

Masking an _OSI string changes which ACPI code path the firmware takes for everything, not just wakeup — backlight, fan and battery control can regress. Test it as a one-off boot-time edit (press `e` in the Limine/GRUB menu) before making it permanent, and keep a known-good fallback boot entry, since a broken cmdline baked into a UKI is harder to recover from. Try `"!Windows 2020"`, `"!Windows 2019"` etc. one at a time if 2015 does not help. Drop the vague `acpi_os_name` mention — it takes a full string (e.g. `acpi_os_name="Microsoft Windows NT"`) and is rarely the right knob here.

**Verify.** `cat /proc/cmdline` contains the parameter, and `systemctl suspend` now stays asleep. `dmesg | grep -i _OSI` shows the string being masked.

Sources: <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers>

---

## Fix a kernel panic on resume on Intel laptops with an I2C touchpad

`touchpad-kernel-panic-on-resume-intel-lpss` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `mkinitcpio`, `omarchy`

**Symptom.** Resuming from suspend gives a dead machine with the Caps Lock LED blinking — a kernel panic. Nothing is written to the journal because the panic happens before the disk is writable again. Intel laptop with an I2C/LPSS touchpad.

**Cause.** The `intel_lpss_pci` module, which drives the LPSS controller behind the touchpad, is loaded too late during the resume path. Having it present in the initramfs avoids the panic.

> ⚠️ **Risk.** Note this is the opposite of the fix for a black screen on hibernate resume, where modules must be *removed* from the initramfs. Change one thing at a time and keep a fallback boot entry.

**Fix.**

Add the module to the initramfs:

```
# /etc/mkinitcpio.conf
MODULES=(intel_lpss_pci)
```

```bash
sudo mkinitcpio -P          # sudo limine-mkinitcpio on Omarchy
```

If you already have entries in `MODULES=()`, append rather than replace. Confirm the module is the one in use:

```bash
lsmod | grep intel_lpss
```

**Verify.** `lsinitcpio /boot/initramfs-linux.img | grep intel_lpss` finds the module, and five suspend/resume cycles complete without a panic.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Set a battery charge limit that survives reboot, suspend and hibernate

`battery-charge-threshold-resets-or-missing` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `asus`, `cachyos`, `dell`, `endeavouros`, `framework`, `laptop`, `manjaro`, `omarchy`, `system76`, `thinkpad`

**Symptom.** I want the laptop to stop charging at 80% like it did on Windows. Either the file isn't there at all (`ls: cannot access '/sys/class/power_supply/BAT0/charge_control_end_threshold': No such file or directory`), or I `echo 80` into it, it works, and then after a reboot — on ASUS machines after every resume from hibernate — it's silently back at 100 and the battery charges to full again.

**Cause.** The charge threshold is not a generic kernel feature. `charge_control_start_threshold` / `charge_control_end_threshold` are power-supply class attributes that only exist if a *vendor platform driver* creates them: `thinkpad_acpi` (natacpi) on ThinkPads, `asus_wmi` / `asus-nb-wmi` on ASUS, `dell-laptop`, `system76_acpi`, `cros_ec` on Framework. The value lives in volatile EC state, so nothing persists it across a power cycle — the Arch wiki notes the ASUS driver explicitly resets it to 100 on every power cycle, and that while the value survives suspend-to-RAM it is reset when resuming from hibernation. A second failure mode: the attribute does not exist until the platform module loads, so anything that writes it too early at boot silently does nothing.

> **Audit corrected this record.** Technically excellent and verified almost line-for-line against wiki.archlinux.org/title/Laptop/ASUS (BAT0/BAT1/BATC/BATT names, 'reset on every power cycle', the asus-nb-wmi udev rule, the /usr/lib/systemd/system-sleep/battery-threshold.sh script, and 'persists after suspend-to-RAM but is reset when resuming from hibernation'). 'You must always specify both charge thresholds ... otherwise TLP will reject both thresholds' is verbatim from linrunner.de/tlp/settings/battery.html, and the ASUS dummy START=0 matches bc-vendors.html. TLP genuinely does restore thresholds on resume. tlp/thinkpad_acpi/tp_smapi-dkms all check out. TWO Omarchy commands are wrong. (1) `omarchy pkg install tlp` does not install tlp: bin/omarchy-pkg-install is an interactive fzf picker (`pacman -Slq | fzf`) that ignores its arguments entirely — the by-name installer is bin/omarchy-pkg-add (`omarchy pkg add tlp`). (2) `OMARCHY_ALLOW_DIRECT_PACMAN=1 sudo pacman -S tlp` cannot work: sudo strips the environment, so the variable never reaches pacman; the documented form printed by the guard itself is `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu`. It is also unnecessary — bin/omarchy-update-pacman-guard only aborts when the pacman invocation has BOTH a sync (-S) and a sysupgrade (-u) flag, and the hook only triggers on Operation=Upgrade, so a plain `pacman -S tlp` is never blocked. Also missing the Arch TLP page's instruction to mask systemd-rfkill.service and systemd-rfkill.socket.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Installing TLP on Omarchy or any distro shipping power-profiles-daemon puts two daemons on the same knobs — see the existing TLP/power-profiles-daemon conflict record before enabling `tlp.service`, and be aware Omarchy's power menu reads powerprofilesctl. Do not set a stop threshold below your current charge and then expect the battery to discharge to it — it will simply sit there not charging. Setting a very low ceiling (e.g. 50%) on a laptop you also use unplugged leaves you with much less runtime than the battery gauge implies.

**Fix.**

Replace the Omarchy install paragraph in step 3 with:

```bash
omarchy pkg add tlp        # omarchy-pkg-add -> pacman -S --noconfirm --needed
sudo systemctl enable --now tlp.service
sudo systemctl mask systemd-rfkill.service systemd-rfkill.socket   # required by the Arch TLP page to avoid conflicts
```

On plain Arch/EndeavourOS/CachyOS: `sudo pacman -Syu --needed tlp`.

Drop the `OMARCHY_ALLOW_DIRECT_PACMAN=1 sudo pacman -S tlp` line. Omarchy's ALPM guard (bin/omarchy-update-pacman-guard) aborts only transactions carrying both -S and -u, so installing a single package is never blocked. If you ever do need the bypass, the env var must come *after* sudo or it is discarded: `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --needed tlp`. Everything else in the record stands as written.

**Verify.** `cat /sys/class/power_supply/BAT0/charge_control_end_threshold` prints your value after a full power-off/on cycle, and again after `systemctl hibernate` + resume. With TLP, `sudo tlp-stat -b` shows a `charge_control_end_threshold = 80 [%]` line and no 'not available' warnings. Charge past the threshold and `cat /sys/class/power_supply/BAT0/status` should read `Not charging` while on AC.

Sources: <https://wiki.archlinux.org/title/Laptop/ASUS> · <https://wiki.archlinux.org/title/TLP> · <https://linrunner.de/tlp/settings/battery.html> · <https://linrunner.de/tlp/settings/bc-vendors.html> · <https://raw.githubusercontent.com/torvalds/linux/master/Documentation/ABI/testing/sysfs-class-power> · <https://man.archlinux.org/man/tmpfiles.d.5.en> · <https://man.archlinux.org/man/systemd-sleep.8.en>

---

## Bring Bluetooth back when the adapter disappears after suspend

`bluetooth-dead-after-resume` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `bluetooth`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `mediatek`, `omarchy`

**Symptom.** Bluetooth works until the first suspend. After resume the icon is gone and:

```
$ bluetoothctl show
No default controller available
```

The adapter isn't in `lsusb` any more either — it's as if someone unplugged it. `dmesg` shows `Bluetooth: hci0: command 0x1001 tx timeout` or `hci0: link tx timeout`. Only a full reboot brings it back.

**Cause.** Two different things wearing the same face. Either bluez lost the adapter and just needs re-powering (`AutoEnable`, rfkill soft-block restored on resume), or — the harder case — the `btusb` USB device genuinely failed to re-enumerate on the xHCI bus after resume, usually because of USB autosuspend on the controller. Common on Intel AX200/AX201/AX211 and MediaTek MT7921/MT7922 combo cards. There is also a distinct bluez-5.80 regression where already-paired LE devices reconnect with a different address and fail to re-pair.

> **Audit corrected this record.** The escalation ladder is sound and mostly wiki-backed: `btusb.enable_autosuspend=n`, the modprobe -r/modprobe btusb cycle, and the rfkill check are all on wiki.archlinux.org/title/Bluetooth; bin/omarchy-restart-bluetooth is indeed just `rfkill unblock bluetooth` plus a listing (the record describes it correctly, unlike its own menu label); the Update > Hardware > Bluetooth mapping is confirmed in the menu JSON; usb_modeswitch and the Limine persistence step are correct. Three fixes needed. (1) Step 2 is stale as a *fix*: the Bluetooth page says 'As of bluez 5.65, BlueZ' default behavior is to power on all Bluetooth adapters when starting the service or resuming from suspend' — AutoEnable=true has been the default for years, so writing it changes nothing. It is only worth checking whether something set it to false. (2) Step 6's xhci_hcd unbind/bind is genuinely dangerous with no warning: unbinding the controller drops every USB device on it, including the keyboard and mouse, and any USB storage — mid-write. (3) The Arch wiki's targeted TLP fix for exactly the quoted `hci0: link tx timeout` symptom is USB_DENYLIST with the adapter's ID, which is far less costly than disabling USB autosuspend machine-wide.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Step 6's `xhci_hcd` unbind disconnects EVERY device on that controller — your keyboard and mouse included, and any mounted USB storage, which risks filesystem damage. Unmount USB drives first (`sudo umount /run/media/$USER/*`) and run it from an SSH session or on a laptop with a built-in keyboard on a different controller. Disabling USB autosuspend system-wide (`USB_AUTOSUSPEND=0`) measurably increases idle battery drain.

**Fix.**

Replace step 2 with:

**2. Confirm nothing disabled auto-power-on.** Since bluez 5.65 BlueZ powers on every adapter when the service starts *and* on resume from suspend, so this is already the default — you only need to check that it was not turned off:

```bash
grep -r -i autoenable /etc/bluetooth/
```

If you find `AutoEnable=false`, set it back (or delete the line):

```ini
# /etc/bluetooth/main.conf
[Policy]
AutoEnable=true
```
```bash
sudo systemctl restart bluetooth.service
```

In step 4, prefer the targeted TLP setting over the global one — the Arch Bluetooth/TLP pages document `USB_DENYLIST` for precisely this `link tx timeout` symptom. Get the ID from `lsusb`:

```ini
# /etc/tlp.d/20-bluetooth.conf
USB_DENYLIST="8087:0026"
```

Use `USB_AUTOSUSPEND=0` only if the denylist entry does not hold.

In step 6, add before the controller rebind:

> **Warning.** Unbinding `xhci_hcd` drops *every* device on that controller at once — USB keyboard, mouse, dock, and any attached USB storage (unmount it first). Run this over SSH, or from a laptop's built-in (non-USB) keyboard, and never while the root filesystem or /home lives on USB. Identify which controller owns the adapter with `lsusb -t` before picking a PCI address, and confirm it is not the one your input devices are on.

**Verify.** `sudo systemctl suspend`, wake, then `bluetoothctl show` prints a controller with `Powered: yes`, `lsusb` still lists the adapter, and `sudo journalctl -b -k | grep -i bluetooth` has no `tx timeout`. Repeat three cycles — this failure is often intermittent on the first cycle only.

Sources: <https://wiki.archlinux.org/title/Bluetooth> · <https://bbs.archlinux.org/viewtopic.php?id=289334> · <https://bbs.archlinux.org/viewtopic.php?id=304397> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-restart-bluetooth> · <https://wiki.archlinux.org/title/TLP> · <https://wiki.archlinux.org/title/Limine>

---

## Fix hibernation that returns straight to the desktop (not enough free swap)

`hibernate-not-enough-free-swap` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `systemctl hibernate` blanks the screen for a moment and then I am back at my desktop. The journal has `Failed to put system to sleep. System resumed again` and the kernel logged:
```
PM: hibernation: Normal pages needed: 999287 + 1024, available pages: 916116
PM: hibernation: Not enough free memory
PM: hibernation: Error -12 creating image
```

**Cause.** The hibernation image must fit entirely inside a **single** swap space, and it needs that much *free* swap at the moment of hibernating. Swap smaller than the working set, or free space spread across several swap devices, makes the kernel abort image creation with `-ENOMEM`.

> ⚠️ **Risk.** Growing swap consumes disk equal to RAM (Omarchy warns: 32 GB RAM means 32 GB of free space on the boot drive). Running `swapoff` on a busy system can OOM-kill processes if there is not enough free RAM to absorb the swapped-out pages.

**Fix.**

Check what you have:

```bash
swapon --show
free -h
cat /sys/power/image_size
```

Either grow one swap space to at least the size of RAM, or shrink the image. To shrink it persistently:

```bash
sudo tee /etc/tmpfiles.d/hibernation_image_size.conf <<'EOF'
#    Path                   Mode UID  GID  Age Argument
w    /sys/power/image_size  -    -    -    -   0
EOF
sudo systemd-tmpfiles --create
```

(`0` asks the kernel to make the image as small as it can. Test immediately with `echo 0 | sudo tee /sys/power/image_size`.)

If `swapon --show` lists more than one swap, free space cannot be pooled — temporarily `swapoff` one of them so usage consolidates, or give them different priorities so one stays mostly empty:

```bash
sudo swapoff /dev/mapper/extra-swap
systemctl hibernate
```

On Omarchy the supported route is `omarchy-hibernation-setup`, which creates a Btrfs `/swap` subvolume with a swapfile sized to total RAM; `omarchy-hibernation-available` explicitly refuses unless the sum of non-zram swap exceeds `/sys/power/image_size`.

**Verify.** `systemctl hibernate` powers the machine fully off, and after power-on your session comes back with all applications where you left them. `journalctl -b -1 | grep 'hibernation:'` shows no `Error -12`.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-available> · <https://learn.omacom.io/2/the-omarchy-manual/103/system-sleep>

---

## Control what closing the laptop lid does (docked, external monitor, on AC)

`lid-close-wrong-action-docked-or-external-power` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `systemd`, `wayland`

**Symptom.** Closing the lid still suspends the laptop even though it is docked with an external monitor attached — or the opposite, closing the lid does nothing at all and the machine cooks in my bag.

**Cause.** `systemd-logind` uses three separate settings: `HandleLidSwitch`, `HandleLidSwitchExternalPower` (on AC) and `HandleLidSwitchDocked` (docked, or more than one display connected — default `ignore`). A desktop power manager may also take an inhibitor lock and override logind entirely.

> **Audit corrected this record.** Almost entirely correct — the three-setting split is real, the action list matches logind.conf(5), and HandleLidSwitchDocked does default to ignore. Two errors. First, the closing note that "logind delays lid-close suspends by up to 90 s to detect docks" is wrong on both the number and the meaning: logind.conf(5) says HoldoffTimeoutSec "Specifies a period of time after system startup or system resume in which systemd will hold off on reacting to lid events... Defaults to 30s" — it is a post-boot/post-resume holdoff, not dock detection, and setting it to 30s as the record does changes nothing. Second, it says HandleLidSwitchExternalPower falls back to on-AC behaviour by default; the man page says it "is completely ignored by default (for backwards compatibility) — an explicit value must be set before it will be used", so on a stock system HandleLidSwitch governs on AC too.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `HandleLidSwitch=ignore` on a laptop means closing the lid and putting it in a bag leaves it running at full power — a real overheating and battery-drain risk.

**Fix.**

Set all three explicitly — HandleLidSwitchExternalPower is ignored entirely until you give it a value, so on a stock system HandleLidSwitch applies on AC as well:

```ini
# /etc/systemd/logind.conf.d/lid.conf
[Login]
HandleLidSwitch=suspend
HandleLidSwitchExternalPower=suspend
HandleLidSwitchDocked=ignore
```

Valid actions: ignore, poweroff, reboot, halt, suspend, hibernate, hybrid-sleep, suspend-then-hibernate, lock, kexec.

Apply:

```bash
sudo systemctl restart systemd-logind.service
```

(`reload` also works on current systemd. Either way, logind does not retroactively change already-active sessions — if behaviour does not change, log out and back in, or reboot. Check for stale sessions with `loginctl list-sessions`.)

Drop the HoldoffTimeoutSec=30s line from the original: 30s is already the default, and it is not dock detection. HoldoffTimeoutSec is the window after boot or after resume during which logind ignores lid events entirely — relevant if your machine suspends again immediately on opening the lid, not if it is picking the wrong action.

If logind is being overridden by a desktop power manager or an application inhibitor:

```bash
systemd-inhibit --list
systemd-inhibit --list --what=handle-lid-switch
```

A `block` inhibitor on handle-lid-switch means another process owns the lid, and no logind setting will win until it releases.

**Verify.** `loginctl show-session $XDG_SESSION_ID` and closing the lid produce the action you configured. `journalctl -f -u systemd-logind` logs `Lid closed.` and the action taken.

Sources: <https://wiki.archlinux.org/title/Power_management> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Diagnose 'systemctl suspend does nothing' when an inhibitor is holding it

`suspend-blocked-by-inhibitor-lock` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `systemctl suspend` returns instantly and the machine just sits there. Closing the lid does nothing either. Occasionally I get a message naming the culprit:

```
Operation inhibited by "Steam" (PID 4711 "steam", user me), reason is "Downloading".
Please retry operation after closing inhibitors and logging out other users.
```

Adding `-i` makes it suspend fine, so something is blocking it — I just can't see what.

**Cause.** logind honours inhibitor locks. A `block` inhibitor prohibits sleep indefinitely (Steam while downloading, a browser playing video, mpv, a package manager, an SSH session with `systemd-inhibit`); a `delay` inhibitor only postpones it up to `InhibitDelayMaxSec` (default 5 s) and is used by upower and screen lockers — including hypridle, whose `inhibit_sleep` option takes exactly such a lock so the lock screen is up before the machine sleeps. Separately, an idle-only inhibitor stops logind's `IdleAction` from ever firing without blocking a manual `systemctl suspend`, which is why the two symptoms look different.

> ⚠️ **Risk.** `systemctl suspend -i` overrides the lock rather than resolving it — if the inhibitor was a package upgrade, a disk write, a `dd`/`rsync` or a VM snapshot, suspending through it can corrupt that work. Read the `Why` string before you override. `sudo systemctl restart systemd-logind` can tear down running graphical sessions on some setups; prefer rebooting after editing logind.conf if you have unsaved work. Setting `ignore_systemd_inhibit = true` also defeats legitimate 'do not lock during a presentation' inhibitors.

**Fix.**

**1. See who is holding a lock — this is the first-line diagnostic**

```bash
systemd-inhibit --list
systemd-inhibit --list --mode=block          # only the hard blockers
systemd-inhibit --list --what=sleep
systemd-inhibit --list --what=idle
```

The output names the process, PID, user, the `What`, the `Why` string and the `Mode`. Quit that app, or kill the PID.

**2. Override once, deliberately**

```bash
systemctl suspend -i        # -i is shorthand for --check-inhibitors=no
```

**3. Give delay-mode inhibitors more room (fixes 'it suspends before my screen locks')**

`/etc/systemd/logind.conf.d/10-inhibit.conf`:

```ini
[Login]
InhibitDelayMaxSec=10
```

```bash
sudo systemctl restart systemd-logind
```

**4. Make lid close respect block inhibitors**

By default `LidSwitchIgnoreInhibited=yes`, so closing the lid suspends regardless of who is blocking. To make it obey:

`/etc/systemd/logind.conf.d/20-lid.conf`:

```ini
[Login]
LidSwitchIgnoreInhibited=no
```

(`SuspendKeyIgnoreInhibited=` and `HibernateKeyIgnoreInhibited=` already default to `no`.)

**5. The Hyprland side — hypridle**

`~/.config/hypr/hypridle.conf` is **still hyprlang, not Lua** — do not convert it. Omarchy ships:

```ini
general {
    lock_cmd = omarchy-system-lock
    before_sleep_cmd = OMARCHY_LOCK_ONLY=true omarchy-system-lock
    after_sleep_cmd = sleep 1 && omarchy-system-wake
    inhibit_sleep = 3          # 0 disable, 1 normal, 2 auto, 3 lock notify
}
```

If a browser's "prevent screensaver" keeps the display alive forever, tell hypridle to ignore those:

```ini
general {
    ignore_dbus_inhibit = true      # ignore dbus idle-inhibit (e.g. Firefox)
    ignore_systemd_inhibit = true   # ignore systemd-inhibit --what=idle
}
```

Restart it — on Omarchy the toggle does both halves:

```bash
omarchy-toggle-idle    # stops hypridle
omarchy-toggle-idle    # starts it again with the new config
```

**6. Check the session is even reported idle** (relevant only for `IdleAction`):

```bash
loginctl list-sessions
loginctl show-session $XDG_SESSION_ID -p IdleHint -p IdleSinceHint
```

**7. Take a deliberate lock yourself** when you want to protect a long job:

```bash
systemd-inhibit --what=sleep --why="backup running" -- restic backup /home
```

**Verify.** `systemd-inhibit --list --mode=block` is empty (or lists only things you expect), then `systemctl suspend` without `-i` actually suspends. After changing hypridle config, `pgrep -a hypridle` shows it running and the screen locks on the configured timeout again.

Sources: <https://man.archlinux.org/man/systemd-inhibit.1.en> · <https://man.archlinux.org/man/logind.conf.5.en> · <https://man.archlinux.org/man/systemctl.1.en> · <https://wiki.hypr.land/Hypr-Ecosystem/hypridle/> · <https://raw.githubusercontent.com/basecamp/omarchy/master/config/hypr/hypridle.conf> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-toggle-idle> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Resolve TLP and power-profiles-daemon fighting over the same knobs

`tlp-power-profiles-daemon-conflict` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `power-profiles-daemon`, `tlp`

**Symptom.** I installed TLP for better battery life and now settings randomly revert, or the desktop's power-profile switcher does nothing. `tlp-stat` prints:
`Warning: PLATFORM_PROFILE_ON_AC/BAT is not set because power-profiles-daemon is running.`
(TLP 1.5 said: `Error: conflicting power-profiles-daemon.service is enabled, power saving will not apply on boot.`)

**Cause.** TLP and power-profiles-daemon change some of the same kernel tunables (platform profile, EPP, PCIe ASPM, USB autosuspend) and overwrite each other. `power-profiles-daemon.service` also declares a `Conflicts=` with TLP. Running both gives unpredictable results.

> ⚠️ **Risk.** Masking `power-profiles-daemon` without installing `tlp-pd` breaks the power-profile switcher in GNOME, KDE and Omarchy's power menu — and on Omarchy it currently crashes `powerprofilesctl` outright (see the related record).

**Fix.**

Pick one. **Keeping TLP:**

```bash
sudo systemctl stop power-profiles-daemon.service
sudo systemctl mask power-profiles-daemon.service
sudo systemctl enable --now tlp.service
sudo systemctl mask systemd-rfkill.service systemd-rfkill.socket
```

So the desktop's power-profile UI still works, install TLP's D-Bus compatibility layer (TLP 1.9+), which implements the same API power-profiles-daemon exposes:

```bash
sudo pacman -S tlp-pd
```

**Keeping power-profiles-daemon (the simpler choice, and what Omarchy assumes):**

```bash
sudo systemctl disable --now tlp.service
sudo systemctl unmask power-profiles-daemon.service
sudo systemctl enable --now power-profiles-daemon.service
```

Do not run `tuned`/`tuned-ppd` at the same time as either.

**Verify.** `sudo tlp-stat -s` shows no conflict warning, or `powerprofilesctl` lists the available profiles without error. `systemctl is-active tlp power-profiles-daemon` should show exactly one active.

Sources: <https://linrunner.de/tlp/faq/ppd.html> · <https://wiki.archlinux.org/title/TLP> · <https://wiki.archlinux.org/title/CPU_frequency_scaling>

---

## Diagnose a CPU stuck at low clocks while the machine is cool

`cpu-power-limit-throttling-low-clocks` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `dell`, `endeavouros`, `intel`, `laptop`, `manjaro`, `omarchy`, `thinkpad`

**Symptom.** The laptop is barely warm — `sensors` says 55 °C — but everything crawls. Under full load `watch -n1 "grep 'MHz' /proc/cpuinfo"` sits at 400–800 MHz even with the performance governor and `boost` enabled. On a ThinkPad it drops to exactly 400 MHz the moment I plug into a dock or a non-Lenovo charger. On other machines the package sticks at ~15 W when the chip is rated for 45 W. It is clearly not heat — so what is limiting it?

**Cause.** You are being power-limited or signal-limited rather than limited by the CPU's own reported core temperature. Three mechanisms produce identical symptoms. (a) **BD PROCHOT** — a hardware line the embedded controller can assert to force the CPU to its minimum P-state. It is asserted by the EC, not by the CPU's thermal control, so `sensors` can look cool while it is active — but it is a protection mechanism and the EC asserts it for real reasons: a third-party or undersized battery/charger, a hot VRM or chassis sensor, a dock, and on many ThinkPads a CPU temperature crossing an EC threshold as low as ~60 °C (well below Tjmax). Clearing the bit disables that protection. (b) A **BIOS `_PPC` limit** exposed as `/sys/devices/system/cpu/cpu0/cpufreq/bios_limit`, typically set when the firmware sees a failing battery or an undersized adapter; the Arch wiki treats overriding it as a hardware risk. (c) **RAPL power limits** (PL1/PL2) programmed low by firmware or Intel DPTF, which the kernel honours faithfully. The governor cannot override any of these.

> **Audit corrected this record.** Diagnostics and mechanisms are right, and the throttlestop script is copied faithfully from wiki.archlinux.org/title/Lenovo_ThinkPad_T480#CPU_stuck_at_minimum_frequency (including the `reg%2` test and the msr-tools note). processor.ignore_ppc=1 / /sys/module/processor/parameters/ignore_ppc and the bios_limit path are verbatim from CPU frequency scaling. throttled (extra 0.12), turbostat, msr-tools, lm_sensors all exist. Three defects. (1) Wrong config path: the current Arch `throttled` package ships `etc/throttled.conf` and `usr/lib/systemd/system/throttled.service` — there is no /etc/lenovo_fix.conf. That name is the pre-rename lenovo_throttling_fix era; a user editing it will see no effect at all. (2) The cause is wrong on a safety-relevant point. The Arch wiki says BD PROCHOT 'is meant to protect the system and can be triggered by many reasons—the CPU temperature rising above 60 °C, using a third party battery, etc.' — so 'completely independent of core temperature' is false, and clearing the bit can remove a live thermal protection. (3) The record strips the wiki's explicit warning on ignore_ppc and presents it as merely 'reversible, no reboot'. The wiki carries a Warning box: 'CPU frequency limitation is a safety feature of your BIOS and should not need to be bypassed in most cases' and 'This can seriously damage your hardware: use at your own risk.' Given these commands go into a root shell, that omission has to be fixed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** This is the most hazardous fix in the set. BD PROCHOT and firmware RAPL limits are electrical and thermal *protections*: the Arch wiki's own warning on the BIOS frequency-limitation section is that bypassing them "can seriously damage your hardware." On a machine with a swollen or failing battery, an undersized or counterfeit charger, or a heatsink full of dust, clearing PROCHOT or raising PL1 can overheat the VRM/CPU or brown out the system under load. Do not apply any of this to a machine that is actually running hot — verify with `turbostat` first. Do not run `throttled.service` alongside a hand-rolled MSR script or another undervolting tool; they overwrite each other and the resulting state is unpredictable. `wrmsr` writes to a CPU model-specific register — a typo in the register number can hang or destabilise the machine.

**Fix.**

Step 3 — add the wiki's warning before the command:

> ⚠️ **Risk.** Per wiki.archlinux.org/title/CPU_frequency_scaling: 'CPU frequency limitation is a safety feature of your BIOS and should not need to be bypassed in most cases' and 'This can seriously damage your hardware: use at your own risk.' Before overriding it, check the BIOS for a manually-set frequency cap or thermal preference, and check whether the battery is failing or the adapter is undersized — those are the usual legitimate triggers.

Step 4 — fix the config path and add the same caveat:

```bash
omarchy pkg add throttled          # or: sudo pacman -Syu --needed throttled
sudo systemctl enable --now throttled.service
sudo systemctl status throttled.service
```

Its config is **`/etc/throttled.conf`** (the current package ships exactly `etc/throttled.conf` and `usr/lib/systemd/system/throttled.service`). `/etc/lenovo_fix.conf` was the old lenovo_throttling_fix name and editing it does nothing.

> ⚠️ **Risk.** BD PROCHOT is a protection signal. Before clearing it, watch `PkgTmp` and per-component temperatures in `turbostat`/`sensors` under load. If the EC is asserting it because of a hot VRM, a third-party charger or a dock, clearing the bit lets the machine run hot instead of slow. Do not run the hand-rolled throttlestop service *and* `throttled` at the same time — pick one, since both write MSR 0x1FC and RAPL limits.

Everything else (turbostat/RAPL inspection, powerprofilesctl, tlp-stat -p, the Limine persistence step, and the thermald pointer) is accurate as written.

**Verify.** Under a sustained load (`stress-ng --cpu $(nproc) --timeout 120s`), `sudo turbostat --quiet --interval 5 --show Bzy_MHz,PkgTmp,PkgWatt` shows `Bzy_MHz` at or near the rated all-core turbo and `PkgWatt` at the expected TDP, with `PkgTmp` still below the throttle point. `sudo rdmsr -d 0x1FC` returns an even value once BD PROCHOT is cleared, and `cat /sys/devices/system/cpu/cpu0/cpufreq/bios_limit` (if present) no longer caps you.

Sources: <https://wiki.archlinux.org/title/CPU_frequency_scaling> · <https://wiki.archlinux.org/title/Lenovo_ThinkPad_T480> · <https://wiki.archlinux.org/title/Laptop/Lenovo> · <https://docs.kernel.org/power/powercap/powercap.html> · <https://wiki.archlinux.org/title/Limine>

---

## Work out which device is failing or blocking suspend

`find-which-device-fails-suspend` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Suspend either fails outright, takes forever, or the machine wakes straight back up — and all I get is one useless line:

```
kernel: PM: Some devices failed to suspend, or early wake event detected
```

I don't know which device to blame, and every guide tells me to try a random kernel parameter.

**Cause.** By default the kernel logs almost nothing about the suspend path, and the console is blanked before the interesting messages appear, so a failure looks anonymous. The kernel does have a full debugging interface — per-device timing, a failure-counter directory, a staged test mode that stops before the risky part, and a wakeup-source accounting table — it is just off unless you turn it on.

> ⚠️ **Risk.** Leaving `/sys/power/pm_test` set to anything but `none` is the classic self-inflicted wound: every subsequent `systemctl suspend` will appear to work and immediately return without the machine ever sleeping — so a laptop in a bag stays fully awake. Always reset it, and it does not survive reboot, so reboot if in doubt. `no_console_suspend` keeps the console powered across suspend and slightly increases sleep-state power draw; remove it once you are done. Writing to `/sys/power/state` directly bypasses logind, so nothing locks your screen and no sleep hooks run.

**Fix.**

**1. Turn on verbose PM logging, then suspend**

```bash
echo 1 | sudo tee /sys/power/pm_debug_messages
echo 1 | sudo tee /sys/power/pm_print_times
sudo systemctl suspend
```

After you resume:

```bash
sudo journalctl -b -k --no-pager | grep -iE 'PM: suspend (entry|exit)|calling |late |noirq|failed to suspend'
```

`pm_print_times` gives a `calling <device>+ @ ...` / `call <device>+ returned N after M usecs` pair per device, so the last device before the hang is named explicitly.

**2. Read the failure counters — they name the guilty device directly**

```bash
grep -H '' /sys/power/suspend_stats/*          # kernel 6.9+
```

On older kernels the same data is in debugfs:

```bash
sudo mount -t debugfs none /sys/kernel/debug 2>/dev/null
sudo cat /sys/kernel/debug/suspend_stats
```

`last_failed_dev` is the device and `last_failed_step` the phase (`suspend`, `suspend_late`, `suspend_noirq`, `freeze`, `prepare`).

**3. Bisect with `pm_test` — stages the suspend and returns without really sleeping**

```bash
for stage in freezer devices platform processors core; do
  echo "== $stage"
  echo $stage | sudo tee /sys/power/pm_test
  echo mem | sudo tee /sys/power/state      # returns after ~5s
  sudo dmesg | tail -30
done
echo none | sudo tee /sys/power/pm_test     # MUST reset
```

The first stage that misbehaves tells you the layer: `freezer` = a userspace process won't freeze, `devices` = a driver's suspend callback, `platform`/`core` = ACPI/firmware.

**4. If a driver hangs, serialise the suspend so the log ordering is trustworthy**

```bash
echo 0 | sudo tee /sys/power/pm_async
```

Per-device, once you know the suspect:

```bash
echo 0 | sudo tee /sys/devices/pci0000:00/0000:00:14.0/power/async
```

**5. Machine wakes straight back up? Rank the wakeup sources instead**

```bash
sudo cat /sys/kernel/debug/wakeup_sources | sort -k3 -n -r | head -20
grep -H '' /sys/class/wakeup/*/device/power/wakeup_count
cat /proc/acpi/wakeup
# dmidecode's guess, unreliable on many boards
sudo dmidecode -t system | grep -P '\tWake-up Type: '
```

Snapshot `wakeup_count` before suspending and diff after resume — the counter that moved is the trigger.

**6. Keep the console alive so you can read a hang that never resumes**

Add `no_console_suspend` at the Limine menu (`e`, edit `cmdline:`), or permanently in `/etc/default/limine`:

```sh
KERNEL_CMDLINE[default]+=" no_console_suspend ignore_loglevel"
```

```bash
sudo limine-update
```

**7. On AMD s2idle systems, use the purpose-built analyser**

```bash
sudo pacman -S amd-debug-tools
sudo amd-s2idle test --count 3 --duration 30 --format txt
```

It needs kernel 6.1+, drives the suspend cycles itself, and prints the blocking IP block / GPIO / missing hardware-sleep residency. Check residency by hand with:

```bash
cat /sys/power/suspend_stats/last_hw_sleep
```

A value of 0 means the platform never reached hardware sleep — the battery drained because the machine only ever froze the CPUs.

**Verify.** `grep -H '' /sys/power/suspend_stats/*` shows `fail` and `last_failed_dev` populated after a failed attempt, and `cat /sys/power/pm_test` prints `[none]` when you are finished. On AMD, `cat /sys/power/suspend_stats/last_hw_sleep` is non-zero after a successful s2idle cycle.

Sources: <https://docs.kernel.org/power/basic-pm-debugging.html> · <https://docs.kernel.org/arch/x86/amd-debugging.html> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/base/power/wakeup.c> · <https://archlinux.org/packages/extra/any/amd-debug-tools/> · <https://github.com/superm1/amd-debug-tools/blob/master/docs/amd-s2idle.md> · <https://wiki.archlinux.org/title/Limine>

---

## Enable hibernation on a system whose only swap is zram

`hibernate-blocked-by-zram-only-swap` · severity: **medium** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `zram`

**Symptom.** CachyOS/Omarchy-style setup with zram. `swapon --show` shows only `/dev/zram0`, and hibernate is either greyed out in the menu or logind refuses it saying there is not enough swap.

**Cause.** zram lives in RAM, so it cannot hold a hibernation image. logind deliberately ignores zram block devices when sizing the hibernation target, and hibernating into zram is unsupported even with a backing device.

> ⚠️ **Risk.** The swapfile consumes disk space equal to total RAM. Editing /etc/fstab incorrectly can leave the boot hanging on a swap unit that never appears.

**Fix.**

Keep zram for everyday swapping and add a **disk-backed** swap space with a *lower* priority for hibernation only. On Btrfs:

```bash
sudo btrfs subvolume create /swap
sudo chattr +C /swap
sudo btrfs filesystem mkswapfile -s "$(awk '/MemTotal/ {print $2}' /proc/meminfo)k" /swap/swapfile
printf '\n/swap/swapfile none swap defaults,pri=0 0 0\n' | sudo tee -a /etc/fstab
sudo swapon -p 0 /swap/swapfile
```

Make sure zram has the higher priority so it is used first:

```
# /etc/systemd/zram-generator.conf
[zram0]
zram-size = ram / 2
swap-priority = 100
```

Then set `resume=`/`resume_offset=` for the swapfile and add the `resume` hook as described in the other records. On Omarchy just run:

```bash
omarchy-hibernation-setup
```

which does exactly this (`swapon -p 0`, Btrfs NOCOW subvolume, resume params, initramfs rebuild).

Do **not** create an on-demand/one-shot swap unit that enables swap only at hibernate time — that is explicitly unsupported by systemd.

**Verify.** `swapon --show` lists both zram (PRIO 100) and the swapfile (PRIO 0); `omarchy-hibernation-available; echo $?` returns 0 on Omarchy; `systemctl hibernate` completes.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-setup> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-available> · <https://learn.omacom.io/2/the-omarchy-manual/103/system-sleep>

---

## Fix 'Call to Hibernate failed: No such file or directory' with a swapfile in /home

`hibernate-swapfile-under-home-logind-error` · severity: **medium** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `systemctl hibernate` fails instantly with `Call to Hibernate failed: No such file or directory`, even though `swapon --show` clearly lists my swapfile and it is bigger than RAM.

**Cause.** `systemd-logind` runs with `ProtectHome=yes`, so it cannot see files under `/home`, `/root` or `/run/user`. Its pre-hibernation swap-size check therefore fails to stat the swapfile and reports ENOENT.

> **Audit corrected this record.** The ProtectHome=yes diagnosis is a genuine, well-known logind gotcha and the Btrfs path is correct (`btrfs filesystem mkswapfile -s SIZE file` is real per btrfs-filesystem.8, which also states "A swapfile must be created in a specific way: NOCOW and preallocated"). The ext4/XFS path is the weak spot: `fallocate` creates unwritten/preallocated extents, and on XFS `swapon` rejects the resulting file ("swapfile has holes"). The modern, filesystem-agnostic way is `mkswap --size --file`, which allocates correctly. The record also never adds the fstab entry for the ext4/XFS case, so the swapfile disappears on reboot.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting the old swapfile while it is still referenced in /etc/fstab leaves a boot that waits on a missing swap unit. Remove or update the fstab line in the same change.

**Fix.**

```bash
sudo swapoff /home/$USER/swapfile
sudo rm /home/$USER/swapfile
```

Recreate at the top level. Use `mkswap --size --file` rather than `fallocate` — fallocate produces unwritten extents that `swapon` refuses on XFS:

```bash
sudo mkswap -U clear --size 32G --file /swapfile
sudo chmod 0600 /swapfile
sudo swapon /swapfile
```

(On older util-linux without `--file`, use `dd if=/dev/zero of=/swapfile bs=1M count=32768 status=progress`, then chmod 600, mkswap, swapon. Do not use fallocate.)

Btrfs — NOCOW subvolume, as Omarchy does:

```bash
sudo btrfs subvolume create /swap
sudo chattr +C /swap
sudo btrfs filesystem mkswapfile -s 32g /swap/swapfile
sudo swapon -p 0 /swap/swapfile
```

Add to /etc/fstab in BOTH cases, or it is gone after reboot:

```
/swapfile      none swap defaults      0 0
# or, Btrfs:
/swap/swapfile none swap defaults,pri=0 0 0
```

Then redo `resume=` / `resume_offset=` for the new file (see the resume-offset record) and rebuild the initramfs. Sanity-check with `swapon --show` and `systemctl hibernate`.

**Verify.** `systemctl hibernate` no longer errors out immediately; `swapon --show` lists the new path and `findmnt -no UUID -T /swap/swapfile` resolves the backing device.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-setup>

---

## Quiet a hot, loud Intel laptop by running thermald

`intel-laptop-hot-loud-no-thermald` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `omarchy`

**Symptom.** The laptop runs noticeably hotter and the fan ramps far more aggressively on Arch/Omarchy than it did on Windows or Fedora, with no obvious runaway process.

**Cause.** Arch installs no thermal daemon by default. On Intel machines, `thermald` proactively manages P-states, T-states and the powerclamp driver to keep the package (and, where a skin sensor exists, the chassis) below target before the hardware falls back to aggressive throttling. Without it the firmware's blunt corrections drive the fan curve.

> **Audit corrected this record.** The thermald half is accurate — Arch ships no thermal daemon by default, thermald is Intel-only, and thermald plus lm_sensors are the correct Arch package names (lm_sensors with an underscore). The AMD guidance is fine. The problem is the closing `sudo powertop --auto-tune` presented as a diagnostic step for finding a runaway process. It is not diagnostic at all: it immediately applies every tunable, including USB autosuspend and SATA link power management, which is precisely the breakage the USB-autosuspend record in this same set is about — crackling DACs, dropped Bluetooth, stuttering mice, and on some machines a wedged input device. Telling the reader to 'inspect the Tunables tab before trusting it' after the flag has already applied everything is backwards ordering.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `powertop --auto-tune` enables every tunable including SATA/USB power saving, which can make mice, keyboards and external drives misbehave. Review the Tunables tab and apply selectively.

**Fix.**

```bash
sudo pacman -S thermald lm_sensors
sudo sensors-detect --auto
sudo systemctl enable --now thermald.service
```

Watch the effect:

```bash
watch -n2 sensors
```

On AMD, thermald does not apply — use power-profiles-daemon (or TLP, never both) and the EPP hint:

```bash
sudo systemctl enable --now power-profiles-daemon.service
powerprofilesctl set balanced
```

To find a runaway process, run powertop READ-ONLY first. Do not use --auto-tune as a diagnostic — it applies every tunable immediately, including USB autosuspend and SATA link power management, which is a well-known way to break USB audio, Bluetooth and input devices:

```bash
sudo pacman -S powertop
sudo powertop --calibrate      # optional, for accurate power estimates; screen will flicker
sudo powertop                  # interactive: check Overview and Tunables tabs
```

Apply tunables one at a time from the interactive Tunables tab (Enter toggles the highlighted one) and test after each. Only consider `--auto-tune` on a headless machine with no USB peripherals you care about, and note it is not persistent across reboots by itself.

Also check the obvious causes before blaming the thermal stack:

```bash
top -o %CPU
cat /sys/devices/system/cpu/cpufreq/boost      # 1 = boost enabled
```

**Verify.** `systemctl status thermald` is active; `sensors` shows the package temperature settling lower under sustained load and the fan stepping down.

Sources: <https://wiki.archlinux.org/title/CPU_frequency_scaling> · <https://wiki.archlinux.org/title/Power_management>

---

## Fix a machine that will not power off after a suspend cycle

`shutdown-hangs-after-suspend-cycle` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Since suspending, the machine refuses to shut down:

```
# systemctl poweroff
Failed to power off system via logind: There's already a shutdown or sleep operation in progress
```

Or I get the shutdown screen stuck on `A stop job is running for User Manager for UID 1000 (1min 30s / 2min)`, and at the end the machine reboots instead of powering off — or just hangs with the fans spinning until I hold the power button.

**Cause.** Three separate things, and it matters which one you have. (1) A previous suspend never completed, so `systemd-suspend.service` is still sitting in the job queue and logind refuses any new power operation. (2) A unit is refusing to stop and systemd is waiting out `DefaultTimeoutStopSec` (90 s by default) — most often `user@1000.service` because something in the graphical session won't die. (3) The firmware's ACPI power-off path is broken after an S3 cycle, so the kernel's chosen reset/poweroff method reboots or hangs instead.

> **Audit corrected this record.** Steps 1, 2, 3, 5 and 6 are excellent and verified. The 'Failed to power off system via logind: There's already a shutdown or sleep operation in progress' symptom, the `systemctl list-jobs` output showing 'systemd-suspend.service start running / suspend.target start waiting', and the `systemctl cancel` + `systemctl stop systemd-suspend.service` remedy are reproduced almost verbatim from wiki.archlinux.org/title/Systemd#Shutdown/reboot_takes_terribly_long. The /usr/lib/systemd/system-shutdown/debug.sh script and the debug cmdline are systemd.io/DEBUGGING's own method. HibernateMode=shutdown in /etc/systemd/sleep.conf.d/hibernatemode.conf matches the wiki's 'System does not power off when hibernating' section word for word, including the 'instead of powering off, the system might reboot or stay on but unresponsive' framing. The reboot_type list (bios, acpi, kbd, triple, efi, pci) is exact per Documentation/admin-guide/kernel-parameters.txt. Two defects. (1) Step 4 is misdirected: `reboot=` selects the *reboot* method (reboot_type feeds the emergency-restart path); it has no effect on the poweroff path, which goes through ACPI S5 / pm_power_off. Telling a user whose machine reboots instead of powering off to cycle reboot=acpi/pci/bios/efi sends them through four reboots for nothing. The real fix for that exact symptom is already the record's step 5 when hibernation is involved, and firmware/ACPI knobs otherwise. (2) `sudo systemctl daemon-reexec` re-executes only the system manager, so the /etc/systemd/user.conf.d drop-in does not take effect in the running user manager — which is the very manager whose stop job ('User Manager for UID 1000') the record is trying to shorten.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The SysRq sequence `S` `U` `O` syncs and remounts read-only first, but skipping straight to `O` (or holding the power button) leaves dirty filesystems and can lose recent writes; on Btrfs it can also cost you the most recent snapshot state. Lowering `DefaultTimeoutStopSec` globally means databases, VMs and long-running backup services get SIGKILLed 15 s into a shutdown instead of being allowed to flush — set a longer per-unit `TimeoutStopSec=` on anything that needs it. Booting with `systemd.log_level=debug` floods the journal; remove it once you have your log.

**Fix.**

Replace step 4 with:

**4. Machine reboots or hangs instead of powering off.** Do not reach for `reboot=` here — that parameter only selects how a *reboot* is performed (reboot_type in the emergency-restart path) and has no effect on the poweroff path, which goes through ACPI S5. Try, in order:

- If a hibernate cycle is involved, go straight to step 5 (`HibernateMode=shutdown`) — that is the documented fix for 'instead of powering off, the system might reboot or stay on but unresponsive'.
- Update the firmware (`sudo fwupdmgr refresh --force && sudo fwupdmgr get-updates`; on Omarchy, Update > Firmware).
- Check the BIOS for Wake-on-LAN / ErP / 'Restore on AC power loss' settings — these make a completed poweroff look like a reboot.
- Only then test ACPI overrides one at a time at the Limine menu (`e`, edit `cmdline:`): `acpi=force`, then `acpi_osi="!Windows 2015"` (see Power management/Wakeup triggers for the board-specific list). Persist the winner in /etc/default/limine with `KERNEL_CMDLINE[default]+=" ..."` and `sudo limine-update`.

Use `reboot=acpi|pci|bios|efi` only for the different symptom where `systemctl reboot` itself hangs or never completes.

In step 3, fix the reload: the user drop-in needs the *user* manager re-executed, not the system one.

```bash
sudo systemctl daemon-reexec        # picks up /etc/systemd/system.conf.d
systemctl --user daemon-reexec      # picks up /etc/systemd/user.conf.d
```

(Or just reboot once.) Note that the 'stop job is running for User Manager for UID 1000' timeout is governed by the *system* drop-in, since user@1000.service is a system unit.

**Verify.** `systemctl list-jobs` prints `No jobs running.` right after a failed suspend, and `systemctl poweroff` then completes. After changing `reboot=`, confirm with `cat /proc/cmdline` and do five power-off cycles — this failure is intermittent, so one success proves nothing. `systemd-analyze` on the next boot and `/shutdown-log.txt` should show no unit hitting its stop timeout.

Sources: <https://wiki.archlinux.org/title/Systemd> · <https://systemd.io/DEBUGGING/> · <https://raw.githubusercontent.com/torvalds/linux/master/Documentation/admin-guide/kernel-parameters.txt> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Limine> · <https://man.archlinux.org/man/systemctl.1.en>

---

## Make the laptop hibernate after sitting suspended instead of dying flat

`suspend-then-hibernate-not-configured` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `limine`, `manjaro`, `omarchy`

**Symptom.** I suspend the laptop on Friday and by Monday it is completely dead and has lost the session. I want it to sleep briefly and then hibernate, the way macOS and Windows do.

**Cause.** `systemctl suspend` alone never escalates to hibernation. `suspend-then-hibernate` does, but it needs working hibernation, and on s2idle-only machines it also needs a functioning RTC alarm to wake up and hand over to hibernate.

**Fix.**

Get hibernation working first (see the swap/resume records), then:

```ini
# /etc/systemd/sleep.conf.d/s2h.conf
[Sleep]
HibernateDelaySec=60min
```

Trigger it manually:

```bash
systemctl suspend-then-hibernate
```

To make it the automatic idle action:

```ini
# /etc/systemd/logind.conf.d/idle-action.conf
[Login]
IdleAction=suspend-then-hibernate
IdleActionSec=15min
```

And for lid close:

```ini
# /etc/systemd/logind.conf.d/lid.conf
[Login]
HandleLidSwitch=suspend-then-hibernate
```

On s2idle-only machines the RTC alarm often does not fire; Omarchy's own hibernation setup adds this kernel parameter for exactly that case:

```bash
sudo mkdir -p /etc/limine-entry-tool.d
echo 'KERNEL_CMDLINE[default]+=" rtc_cmos.use_acpi_alarm=1"' | sudo tee /etc/limine-entry-tool.d/rtc-alarm.conf
sudo tee -a /etc/default/limine < /etc/limine-entry-tool.d/rtc-alarm.conf
sudo limine-mkinitcpio
```

If you leave `HibernateDelaySec` unset, systemd estimates the delay from the measured battery discharge rate (`SuspendEstimationSec`), briefly waking the machine once to take the measurement — that brief wake is expected, not a bug.

**Verify.** Run `systemctl suspend-then-hibernate`, wait past `HibernateDelaySec`, and confirm the machine has powered itself fully off. After power-on, `journalctl -b -1 | grep -i hibernat` should show the handover.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://man.archlinux.org/man/systemd-sleep.conf.5.en> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-setup>

---

## Stop TLP's USB autosuspend killing DACs, headsets and Bluetooth on battery

`tlp-usb-autosuspend-breaks-devices` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `tlp`

**Symptom.** On battery my USB DAC crackles or disappears, my Bluetooth headphones cut out, or the mouse stutters — all fine when plugged into AC. `dmesg` shows `hci0: link tx timeout`.

**Cause.** With its default configuration TLP enables USB autosuspend on battery. Its own docs state that all input devices (driver `usbhid`), libsane-supported scanners **and audio devices** are excluded by default - `USB_EXCLUDE_AUDIO` defaults to 1 - so a USB DAC is already covered and autosuspend is usually not the explanation for it. The class that genuinely is *not* excluded by default is Bluetooth: `USB_EXCLUDE_BTUSB` defaults to 0, so a USB Bluetooth radio is the device this actually bites.

> **Audit corrected this record.** Two real errors. (1) The cause paragraph is wrong about defaults: TLP's own docs state "All input devices (driver usbhid), libsane-supported scanners and audio devices get excluded by default" — USB_EXCLUDE_AUDIO defaults to 1, so a USB DAC is already excluded and USB autosuspend is not the explanation for it. The device that genuinely is NOT excluded by default is Bluetooth (USB_EXCLUDE_BTUSB defaults to 0), which the record misses as the one-line fix. (2) The closing 'without TLP' udev rule is backwards and actively harmful: ATTR{power/control}="auto" ENABLES autosuspend on every non-mouse, non-keyboard USB device — it would cause the reported symptom on a machine that does not have it. Disabling autosuspend requires "on", not "auto". USB_DENYLIST and USB_AUTOSUSPEND=0 themselves are correct option names, and the note about /etc/tlp.conf taking precedence over /etc/tlp.d/ is right.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `USB_AUTOSUSPEND=0` measurably shortens battery life. Prefer denylisting the specific device.

**Fix.**

Identify the device:

```bash
lsusb
```

For Bluetooth — this is the common case, because unlike input, scanner and audio devices, Bluetooth is NOT excluded by default:

```
# /etc/tlp.d/10-usb.conf
USB_EXCLUDE_BTUSB=1
```

For anything else, denylist by vendor:product:

```
# /etc/tlp.d/10-usb.conf
USB_DENYLIST="1234:5678"
```

Note that USB audio devices (snd_usb_audio) and usbhid input devices are already excluded by TLP defaults — if your DAC crackles on battery, TLP's USB autosuspend is probably not the cause; look at CPU/PCIe power settings (PCIE_ASPM_ON_BAT, CPU_ENERGY_PERF_POLICY_ON_BAT) or PipeWire quantum settings instead.

Blunt fallback:

```
# /etc/tlp.d/10-usb.conf
USB_AUTOSUSPEND=0
```

```bash
sudo systemctl restart tlp.service
sudo systemctl restart bluetooth.service
tlp-stat -u        # confirm the device now shows as excluded
```

Settings in /etc/tlp.conf override /etc/tlp.d/ drop-ins, so make sure the same key is not also set there.

Without TLP, the correct udev rule DISABLES autosuspend for the offending device — `"auto"` turns it on, which is the opposite of what you want here:

```
# /etc/udev/rules.d/50-usb-no-autosuspend.rules
ACTION=="add", SUBSYSTEM=="usb", ATTRS{idVendor}=="8087", ATTRS{idProduct}=="0aaa", TEST=="power/control", ATTR{power/control}="on"
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=usb
```

Or disable USB autosuspend globally with the `usbcore.autosuspend=-1` kernel parameter.

**Verify.** `sudo tlp-stat -u` shows `control = on` for the denylisted device while on battery, and the device works normally unplugged from AC.

Sources: <https://wiki.archlinux.org/title/TLP> · <https://wiki.archlinux.org/title/Power_management>

---

## Fix Wi-Fi or Bluetooth staying off at boot or after resume with TLP installed

`wifi-bluetooth-off-after-boot-with-tlp` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `iwd`, `laptop`, `manjaro`, `networkmanager`, `omarchy`, `tlp`

**Symptom.** After installing TLP, Wi-Fi is off every time I boot and I have to toggle it on by hand, or Bluetooth never comes back after resume. `rfkill list` shows the device soft-blocked.

**Cause.** TLP by default does not power the Wi-Fi radio back on at startup, and `systemd-rfkill` independently saves and restores rfkill state — the two race and TLP's radio switching does not apply reliably.

> ⚠️ **Risk.** Masking `systemd-rfkill` means the hardware kill-switch state is no longer saved across reboots. Disabling Wi-Fi power saving costs battery life.

**Fix.**

Mask systemd's rfkill state handling so TLP is the only thing touching the radios:

```bash
sudo systemctl mask systemd-rfkill.service systemd-rfkill.socket
```

Then tell TLP to bring Wi-Fi up at boot:

```
# /etc/tlp.d/00-enable-wifi-at-startup.conf
DEVICES_TO_ENABLE_ON_STARTUP="wifi bluetooth"
```

```bash
sudo systemctl restart tlp.service
```

If latency or dropouts on Wi-Fi are the actual problem, disable Wi-Fi power saving:

```
# /etc/NetworkManager/conf.d/powersave.conf
[connection]
wifi.powersave=2
```

(`2` = power saving globally disabled.) With iwd instead of wpa_supplicant:

```
# /etc/iwd/main.conf
[DriverQuirks]
PowerSaveDisable=*
```

```bash
sudo systemctl restart NetworkManager
```

**Verify.** `rfkill list` shows no soft block after a reboot; `iw dev wlan0 get power_save` reports `off` if you disabled power saving.

Sources: <https://wiki.archlinux.org/title/TLP> · <https://wiki.archlinux.org/title/Power_management>

---

## Restart fan control after a suspend/resume cycle

`fancontrol-stops-after-suspend` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** My custom fan curve works fine until I suspend the machine. After resume the fans are stuck — either full blast or off entirely — until I restart the service by hand.

**Cause.** A known lm-sensors bug: `fancontrol` does not re-establish control of the PWM outputs after a suspend/resume cycle.

> ⚠️ **Risk.** A misconfigured /etc/fancontrol can stop fans entirely and let the CPU or GPU overheat. Always run `pwmconfig` and watch `sensors` for a few minutes after changing it. Scripts in /usr/lib/systemd/system-sleep/ may be removed by systemd package upgrades.

**Fix.**

Restart it automatically from a systemd sleep hook:

```bash
sudo tee /usr/lib/systemd/system-sleep/fancontrol.sh <<'EOF'
#!/bin/sh
case $1 in
  post) /usr/bin/systemctl restart fancontrol.service ;;
esac
EOF
sudo chmod +x /usr/lib/systemd/system-sleep/fancontrol.sh
```

If `fancontrol.service` fails after a kernel update instead, it is usually a moved hwmon path — check which one:

```bash
systemctl status fancontrol.service
sensors
grep -E 'DEVPATH|DEVNAME|FCTEMPS|FCFANS' /etc/fancontrol
```

and correct the `hwmonN` numbers in `/etc/fancontrol` (they can reorder across reboots), or regenerate the config:

```bash
sudo sensors-detect
sudo pwmconfig
```

**Verify.** Suspend and resume, then confirm fan RPM tracks temperature again with `watch -n2 sensors`, and `systemctl is-active fancontrol` reports `active`.

Sources: <https://wiki.archlinux.org/title/Fan_speed_control> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate>

---

## Fix Omarchy's power menu crashing after masking power-profiles-daemon for TLP

`omarchy-powerprofilesctl-crash-ppd-masked` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `laptop`, `omarchy`, `power-profiles-daemon`, `tlp`

**Symptom.** After masking `power-profiles-daemon` so TLP could take over, Omarchy's power panel throws on every AC/battery transition and when opened. Crash logs show `Signal: 6 (ABRT) si_code: SI_TKILL` with a stack through `PyGILState_Ensure()` → `_Py_FatalErrorFunc()` → `abort()`.

**Cause.** `powerprofilesctl` is a Python/PyGObject tool. When the D-Bus service is absent it takes a different error path in which a finalizer callback fires after the interpreter's GIL has been destroyed, and the interpreter aborts. Omarchy's shell plugins call `powerprofilesctl` unconditionally on power events.

**Fix.**

The clean fix is to keep something answering on that D-Bus name. Either go back to power-profiles-daemon:

```bash
sudo systemctl disable --now tlp.service
sudo systemctl unmask power-profiles-daemon.service
sudo systemctl enable --now power-profiles-daemon.service
```

or keep TLP and install its D-Bus compatibility layer so the API still responds:

```bash
sudo pacman -S tlp-pd
```

Before invoking `powerprofilesctl` from any script of your own, guard it:

```bash
systemctl is-active --quiet power-profiles-daemon.service && powerprofilesctl set balanced
```

With no daemon at all you can still read/write the CPU energy hint directly:

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
echo balance_power | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
```

**Verify.** `powerprofilesctl` prints the profile list and exits 0; the Omarchy power panel opens and switching profiles no longer produces an ABRT in the logs.

Sources: <https://github.com/basecamp/omarchy/issues/8596> · <https://linrunner.de/tlp/faq/ppd.html> · <https://wiki.archlinux.org/title/CPU_frequency_scaling>

---

## Fix 'only powersave and performance available' and governors that reset at boot

`cpu-governor-not-persistent-pstate-active` · severity: **low** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `limine`, `manjaro`, `omarchy`

**Symptom.** `cpupower frequency-set -g ondemand` fails, and `cpupower frequency-info` lists only `powersave` and `performance`. Whatever I set reverts to `powersave` after a reboot, and I assume my CPU is being throttled.

**Cause.** `intel_pstate` and `amd_pstate` in *active* mode bypass the classic cpufreq governors and expose two pseudo-governors of the same names. These are not the old governors — both scale dynamically; they map onto an Energy Performance Preference hint. Nothing is throttled. Separately, sysfs governor writes are not persistent across boots by themselves.

> ⚠️ **Risk.** Forcing the `performance` governor or EPP on a laptop raises temperatures and shortens battery life significantly. Watch temperatures with `sensors` after changing it.

**Fix.**

Check what you are actually running:

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
cpupower frequency-info
```

If it says `amd_pstate_epp` or `intel_pstate`, tune the EPP hint rather than hunting for `ondemand`:

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences
echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
```

Make that persistent:

```bash
sudo tee /etc/tmpfiles.d/energy_performance_preference.conf <<'EOF'
w /sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference - - - - balance_power
EOF
sudo systemd-tmpfiles --create
```

If you genuinely want the classic governors, switch the driver to passive mode with a kernel parameter — `amd_pstate=passive` (or `intel_pstate=passive`), or `amd_pstate=disable` to fall back to `acpi_cpufreq`. On Omarchy:

```bash
sudo mkdir -p /etc/limine-entry-tool.d
echo 'KERNEL_CMDLINE[default]+=" amd_pstate=passive"' | sudo tee /etc/limine-entry-tool.d/pstate.conf
sudo tee -a /etc/default/limine < /etc/limine-entry-tool.d/pstate.conf
sudo limine-mkinitcpio
```

To pin a governor at boot, configure `/etc/default/cpupower-service.conf` and enable the service:

```bash
sudo pacman -S cpupower
sudo systemctl enable --now cpupower.service
```

**Verify.** `cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference` shows your value after a reboot; `watch -n1 'grep MHz /proc/cpuinfo'` shows frequencies rising under load.

Sources: <https://wiki.archlinux.org/title/CPU_frequency_scaling> · <https://wiki.archlinux.org/title/Power_management>

---

## Change Omarchy's screensaver and lock timeouts (and make edits actually take effect)

`omarchy-hypridle-timeouts-too-aggressive` · severity: **low** · frequency: **very-common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** On Omarchy the screensaver kicks in after about two and a half minutes and the machine locks right after — far too aggressive while reading or watching something. Editing `~/.config/hypr/hypridle.conf` seems to change nothing.

**Cause.** Omarchy ships its own `hypridle.conf` with a 150 s screensaver listener and a 152 s lock listener (the screensaver resets the idle timer, so the lock timeout is deliberately "half plus a two-second margin", not five minutes of real idle). hypridle reads its config only at startup, so edits do nothing until it is restarted.

> ⚠️ **Risk.** Raising the lock timeout or setting `ignore_dbus_inhibit`/`ignore_systemd_inhibit` weakens screen-lock security on a portable machine.

**Fix.**

Omarchy's shipped config is:

```ini
general {
    lock_cmd = omarchy-system-lock
    before_sleep_cmd = OMARCHY_LOCK_ONLY=true omarchy-system-lock
    after_sleep_cmd = sleep 1 && omarchy-system-wake
    inhibit_sleep = 3
}

listener {
    timeout = 150
    on-timeout = pidof hyprlock || omarchy-launch-screensaver
}

listener {
    timeout = 152
    on-timeout = omarchy-system-lock
    on-resume = omarchy-system-wake
}
```

Edit `~/.config/hypr/hypridle.conf`, raise both timeouts keeping the same relationship (e.g. 600 and 602 for ten minutes), then restart the daemon:

```bash
systemctl --user restart hypridle.service 2>/dev/null || { pkill hypridle; uwsm app -- hypridle & }
```

To suppress idle for a single long task rather than changing the config:

```bash
systemd-inhibit --what=idle --why="watching a film" mpv film.mkv
```

Note `inhibit_sleep = 3` ("lock notify") means hypridle holds off the suspend until the lock screen is actually up — do not remove it, or you can suspend before the screen is locked.

**Verify.** `pgrep -a hypridle` shows the running daemon; leave the machine idle past the new timeout and confirm the screensaver and lock fire at the new times.

Sources: <https://raw.githubusercontent.com/basecamp/omarchy/master/config/hypr/hypridle.conf> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-system-lock> · <https://wiki.hypr.land/Hypr-Ecosystem/hypridle/>

---

## Work around the Omarchy lock screen not accepting keystrokes after lid-open

`omarchy-lockscreen-no-keyboard-focus-after-resume` · severity: **low** · frequency: **common** · applies to: `hyprland`, `intel`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** I open the lid, the lock screen is there, I type my password and nothing appears in the field. I have to click the password box first, then it works. Locking manually while awake is fine — only resume is affected.

**Cause.** A timing race: the password field calls `forceActiveFocus()` as soon as the lock is *requested*, not once the `WlSessionLock` surface has actually been mapped and granted exclusive keyboard focus by the compositor. On resume the lock is set up during the unstable early-resume window, so the focus call lands before the surface exists. Hybrid Intel+NVIDIA laptops make the window wider. Omarchy has no `omarchy-sleep-lock.service`; pre-sleep locking is driven by hypridle's `inhibit_sleep = 3` together with the hooks under `default/systemd/system-sleep/`.

> **Audit corrected this record.** The issue is real and the root-cause analysis is accurate — basecamp/omarchy#8520 describes the password field lacking keyboard focus after resume but not on manual lock, on Omarchy 4.0.1-1 with hybrid Intel+NVIDIA, and attributes it to forceActiveFocus() firing before "the WlSessionLock surface has actually been mapped and granted exclusive keyboard focus by the compositor". The workarounds (click the field, widen the after_sleep_cmd delay) are sound and the config block matches upstream apart from the intended sleep 2. The defect is the diagnostic step: there is no omarchy-sleep-lock.service in the Omarchy repository — Omarchy handles pre-sleep locking via hypridle's inhibit_sleep = 3 and hooks under default/systemd/system-sleep/. Those two commands will just report that the unit could not be found, sending the user chasing a non-existent service.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

No upstream fix yet. Immediate workaround: click the password field (or press Escape then Tab) before typing.

Widen the post-resume settling window by increasing the delay in after_sleep_cmd:

```ini
# ~/.config/hypr/hypridle.conf
general {
    lock_cmd = omarchy-system-lock
    before_sleep_cmd = OMARCHY_LOCK_ONLY=true omarchy-system-lock
    after_sleep_cmd = sleep 2 && omarchy-system-wake
    inhibit_sleep = 3
}
```

```bash
systemctl --user restart hypridle.service 2>/dev/null || { pkill hypridle; uwsm app -- hypridle & }
```

Replace the omarchy-sleep-lock.service checks — that unit does not exist. Omarchy locks before sleep through hypridle's `inhibit_sleep = 3` (lock notify) and systemd sleep hooks, so look there instead:

```bash
journalctl -b --since '-1h' | grep -i 'hypridle\|hyprlock\|omarchy-system-lock'
systemd-inhibit --list --what=sleep      # hypridle should hold a sleep inhibitor
ls /usr/lib/systemd/system-sleep/ /etc/systemd/system-sleep/
```

If hypridle is not holding a sleep inhibitor, `inhibit_sleep` is not in effect and the machine can suspend before the lock surface is up — which makes the focus race much worse. Confirm hypridle is actually running (`pidof hypridle`) before tuning delays.

**Verify.** Suspend, resume, and type immediately — characters appear in the field without clicking it first.

Sources: <https://github.com/basecamp/omarchy/issues/8520> · <https://github.com/basecamp/omarchy/issues?q=is%3Aissue+suspend> · <https://raw.githubusercontent.com/basecamp/omarchy/master/config/hypr/hypridle.conf>

---

## Make the laptop's Fn sleep key work when logind ignores the keyboard

`suspend-fn-key-does-nothing` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** The Fn+F4 (or similar) sleep key does nothing at all — not even a log line — no matter what I set in `logind.conf`. The power button works fine.

**Cause.** `systemd-logind` only watches input devices tagged `power-switch` by udev. On some laptops and most external keyboards the keyboard is not tagged, so logind never sees the sleep key.

> ⚠️ **Risk.** Restarting `systemd-logind.service` can terminate the graphical session on some setups — save your work first.

**Fix.**

Check which devices logind is watching:

```bash
journalctl --grep="Watching system buttons"
```

If no keyboard is listed, find yours:

```bash
stat -c%N /dev/input/by-id/*-kbd
sudo udevadm info -a /dev/input/event6 | grep 'ATTRS{name}'
```

Add the tag with a udev rule, substituting the exact `ATTRS{name}` string:

```
# /etc/udev/rules.d/70-power-switch-my.rules
ACTION=="remove", GOTO="power_switch_my_end"
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="SIGMACHIP USB Keyboard", TAG+="power-switch"
LABEL="power_switch_my_end"
```

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo systemctl restart systemd-logind.service
```

**Verify.** `journalctl --grep="Watching system buttons"` now includes your keyboard's event device, and pressing the sleep key suspends the machine.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Power_management>

---
