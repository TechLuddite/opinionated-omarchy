# Power, suspend & thermal

38 problems. Sorted by severity, then by how often users hit it.

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

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, Hyprland 0.56.2-1, kernel 7.1.9-arch1-2). It is a DESKTOP with an NVIDIA card, so there is no AMD GPU here and the symptom, the parameters and the suspend cycles could NOT be exercised. Everything below is a config and source check. What held: `modinfo -p amdgpu` on kernel 7.1.9 still lists all three parameters (`dcdebugmask`, `sg_display`, `runpm`), so none has been removed. wiki.archlinux.org/title/AMDGPU section 'Frozen or unresponsive display (flip_done timed out)' still gives 0x10 and 0x12 with the record's near-verbatim wording, 'Screen flickering white/gray' still gives `amdgpu.sg_display=0`, and the dGPU power-management section still gives `amdgpu.runpm=0`. I read bbs.archlinux.org/viewtopic.php?id=309052 in full: it is dated 2025-10-03, its dmesg matches the record's symptom block verbatim, and the reporter's closing post shows 6.16.10-arch1-1, so the record's 'resolved purely by moving from 6.16.7 to 6.16.10' claim is exactly right. `/usr/bin/omarchy-update-pacman-guard` aborts only when both sync and sysupgrade are present, so `pacman -S linux-lts` is allowed as the record says. Nothing under `/usr/share/omarchy` mentions amdgpu at all, so the advice collides with nothing Omarchy ships. Three things were wrong. First and worst, step 2. `/etc/limine-entry-tool.d/omarchy-uki.conf` sets ENABLE_UKI=yes, so the command line is embedded in `/boot/EFI/Linux/omarchy_linux.efi`, and systemd-stub's own documentation says an invocation command line is used to 'override' the embedded one and is ignored outright under Secure Boot. Limine's CONFIG.md confirms `cmdline` is a general entry option that applies to the `efi` protocol. So a menu edit holding only `amdgpu.dcdebugmask=0x10` replaces the whole command line and drops `cryptdevice=`, `root=` and `rootflags=subvol=@`, which is a failed boot, not the 'no config edits, nothing to undo' step the record promises. The rewrite prints the real command line with `limine-entry-tool --get-cmdline linux`, which I ran unprivileged here and which returned the full string. Second, step 3 named `/etc/default/limine`, which does work (it is loaded last and highest priority per `/usr/lib/limine/limine-common-functions` lines 99 to 129, and Omarchy's own copy uses `+=`), but Omarchy 4 keeps its command line in `/etc/limine-entry-tool.d/*.conf` and ships `resume.conf` and `omarchy-defaults.conf` there, so the drop-in is now the primary branch with `/etc/default/limine` kept as the labelled alternative. Third, the symptom was not distinguishable from a lock screen failure, which is the specific Omarchy 4 trap here: `omarchy-system-sleep-monitor` holds a logind delay inhibitor and runs `omarchy-system-sleep-lock` before every suspend, so you always resume into an `ext-session-lock` surface drawn by omarchy-shell, and a lock that fails to draw gives the identical 'black screen, ssh works' picture. Step 1 now separates the two with `omarchy-hyprland-session-locked` before anything is changed. Minor fixes folded in: `sudo limine-update` after installing linux-lts is redundant because `90-mkinitcpio-install.hook` already builds and registers the entry, and the danger now names Snapshots as the recovery path because Omarchy 4 builds no fallback kernel entry (MKINITCPIO_FALLBACK is unset everywhere and `limine-list` shows only Omarchy > linux, Snapshots and the EFI fallback bootloader). I could not read `/boot/limine.conf` to see whether a UKI entry carries a `cmdline:` line at all, because /boot is mounted dmask=0077 and I did not use sudo. Sources: the cited raw.githubusercontent.com/basecamp/omarchy/master/default/limine/default.conf still returns 200, but `master` is the branch this project treats as stale and its content no longer matches what 4.0.2 ships, which splits that file between `/etc/default/limine` (ESP_PATH plus the cmdline line) and `/etc/limine-entry-tool.d/omarchy-defaults.conf` (everything else). I replaced it with the two quattro paths I fetched through the gh API.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `amdgpu.runpm=0` stops the discrete GPU powering down at runtime. On a hybrid-graphics laptop that costs several watts of idle battery and makes the machine run hotter, so only keep it if it is genuinely the fix.

On Omarchy 4 the Limine menu editor replaces the UKI's embedded command line rather than adding to it, so a `cmdline:` line holding only the new parameter boots to an initramfs emergency shell with no root filesystem. Copy the whole command line from `limine-entry-tool --get-cmdline linux` before you edit. The edit is not persisted, so a plain reboot recovers.

Adding a drop-in and running `limine-mkinitcpio` or `limine-update` rewrites your boot entries. Keep the Limine menu visible (do NOT enable Setup > Direct Boot while you are experimenting). Omarchy 4 builds no fallback kernel entry, so if the machine stops booting the recovery path is a Snapshots entry, not a fallback entry.

**Fix.**

**1. Rule out the lock screen first, then confirm which amdgpu failure you have**

On Omarchy 4 every suspend is preceded by a lock. `omarchy-system-sleep-monitor` holds a logind delay inhibitor and runs `omarchy-system-sleep-lock`, which asks `omarchy-shell` for an `ext-session-lock` surface before the machine sleeps. So you always resume into a lock screen, and a lock surface that fails to draw looks exactly like this record's symptom: black panel, machine alive, ssh works. Separate the two before touching the kernel command line:

```bash
omarchy-hyprland-session-locked          # LOCK in solitaryBlockedBy means the compositor is locked
sudo journalctl -b -1 -k --no-pager | grep -iE 'amdgpu|drm|flip_done|PM: suspend'
```

If the compositor reports itself locked and the journal shows no `amdgpu`, `flip_done` or `resume of IP block` lines, this is a lock screen or compositor problem, not an amdgpu resume bug, and nothing below will help. Omarchy 4's lock cannot be released headlessly, so type the password on the console or use `virsh send-key` on a VM.

**2. Try the parameter live at the boot menu, but type the whole command line**

Omarchy 4 boots a UKI with the command line embedded in its `.cmdline` PE section. systemd-stub uses an invocation command line **instead of** the embedded one, not in addition to it, and ignores it altogether when Secure Boot is on. So a `cmdline:` line typed at the Limine menu that holds only the new parameter drops `cryptdevice=`, `root=` and `rootflags=subvol=@`, and the machine lands in an initramfs emergency shell. Print the real command line first:

```bash
limine-entry-tool --get-cmdline linux --no-mutex --no-hooks
```

At the Limine menu press `e` on the Omarchy entry, set `cmdline:` to that entire string plus the parameter, and boot:

```
cmdline: <everything the command above printed> amdgpu.dcdebugmask=0x10
```

Nothing is written to disk, so a reboot undoes it. `0x10` disables PSR v1 and Panel Self Refresh-Selectively Updated. If that is not enough, try `amdgpu.dcdebugmask=0x12`, which additionally disables memory stutter mode.

Other candidates, one at a time:

- `amdgpu.sg_display=0` for laptops and APUs that flicker white or stay blank when a display is attached or re-attached.
- `amdgpu.runpm=0` for discrete AMD cards that vanish or fail to come back after being powered down.

All three parameters exist on kernel 7.1.9: `modinfo -p amdgpu | grep -E 'dcdebugmask|sg_display|runpm'`.

**3. Make the winning parameter permanent on Omarchy 4 (Limine + UKI)**

Omarchy sets its own command line from drop-ins, so add one of your own rather than editing a shipped file. Any name works, `+=` is what makes it append:

```bash
printf 'KERNEL_CMDLINE[default]+=" amdgpu.dcdebugmask=0x10"\n' \
  | sudo tee /etc/limine-entry-tool.d/zz-amdgpu.conf
sudo limine-mkinitcpio
sudo reboot
```

`/etc/default/limine` also works and is read last, after every drop-in, so `+=` there appends too. It is owned by no package, so it takes no `.pacnew`. Either file is fine, the drop-in just matches how Omarchy ships `resume.conf`. `sudo limine-update` is the same thing plus a bootloader reinstall.

On GRUB systems instead: add it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`. On systemd-boot: append it to `/etc/kernel/cmdline` or the entry's `options` line. Neither applies to Omarchy 4.

**4. If no parameter helps, it is a kernel regression, so change kernels rather than keep guessing**

```bash
sudo pacman -S linux-lts linux-lts-headers
```

The `90-mkinitcpio-install.hook` pacman hook builds the UKI and registers the Limine entry for you, so no further command is needed. This is not caught by Omarchy's update guard, which aborts only when both `-S` and `-u` are present. Reboot into `linux-lts` from the Limine menu. If resume works there, stay on it until the mainline fix lands and re-test after each `omarchy update`.

**5. Firmware**

AMD laptop resume bugs are frequently EC or BIOS side. Check for an update:

```bash
sudo fwupdmgr refresh --force && sudo fwupdmgr get-updates
```

On Omarchy this is also exposed as Update > Firmware.

**Verify.** `cat /proc/cmdline` shows the parameter after reboot. Run three suspend/resume cycles (`sudo systemctl suspend`, wake, repeat) and then `sudo journalctl -b -k | grep -iE 'flip_done|resume of IP block|SMU'` — a clean run has no matches, and `grep -c 'PM: suspend exit' <<< "$(journalctl -b -k)"` counts the resumes that completed.

Sources: <https://wiki.archlinux.org/title/AMDGPU> · <https://bbs.archlinux.org/viewtopic.php?id=309052> · <https://wiki.archlinux.org/title/Kernel_parameters> · <https://wiki.archlinux.org/title/Limine> · <https://www.freedesktop.org/software/systemd/man/latest/systemd-stub.html> · <https://github.com/limine-bootloader/limine/blob/trunk/CONFIG.md> · <https://github.com/omacom/omarchy/blob/quattro/default/limine/default.conf> · <https://github.com/omacom/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf>

---

## Stop a laptop draining its battery while suspended (s2idle instead of S3)

`battery-drains-overnight-s2idle-no-deep-sleep` · severity: **high** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `omarchy`

**Symptom.** I close the lid at 100% and eight hours later the battery is at 30-40%, or the laptop is warm inside the bag. `cat /sys/power/mem_sleep` prints `[s2idle] shallow deep` or only `[s2idle]`.

**Cause.** The machine is using suspend-to-idle (S0ix / "Modern Standby") rather than S3 suspend-to-RAM. On many laptops the platform never actually reaches the deep S0i3 substate — a device keeps a runtime-PM reference or the EC keeps generating wakeups — so the CPU idles at a high power floor all night.

> **Audit corrected this record.** The generic Arch half of this record holds. I fetched the raw wikitext of Power_management/Suspend_and_hibernate and it prescribes the same two routes the record does, with the same filename: /etc/systemd/sleep.conf.d/mem-deep.conf carrying MemorySleepMode=deep, or the mem_sleep_default=deep kernel parameter, plus the UEFI sleep-state hunt when deep is not advertised. Power_management/Wakeup_triggers confirms acpi.ec_no_wakeup and the /sys/module/acpi/parameters/ec_no_wakeup file, which exists here and reads N. The installed systemd-sleep.conf(5) on systemd 261.2-1 lists MemorySleepMode= as added in version 256, so the directive is current. Two things were wrong for Omarchy 4 and both were checked on this machine. First, the Omarchy branch told the reader to write /etc/limine-entry-tool.d/deep-sleep.conf and also append to /etc/default/limine. Either route works on its own. The header of /etc/limine-entry-tool.conf says /etc/default/limine overrides the drop-in configs, and doing both would set the parameter twice. Omarchy's own code uses the drop-in alone, in /usr/share/omarchy/install/hardware/apple/fix-t2.sh, which writes /etc/limine-entry-tool.d/t2-mac.conf containing mem_sleep_default=deep and whose migration /usr/share/omarchy/migrations/1785944594.sh refreshes it with sudo limine-mkinitcpio. So limine-mkinitcpio alone is right, matching what mt7921e-dead-after-suspend-aspm says, and the /etc/default/limine clause is the defect. Second, /etc/systemd/sleep.conf.d/ does not exist on a stock Omarchy 4 install: ls reports no such directory, and the only file present is /etc/systemd/sleep.conf, owned by systemd 261.2-1 with every entry commented out. The fix now says to create the directory. The verify step was also wrong in a way that reads as a failure. systemd writes /sys/power/mem_sleep only while suspending, confirmed in systemd's src/sleep/sleep.c where write_mode("/sys/power/mem_sleep", ...) sits inside the sleep execution path, so after MemorySleepMode=deep the file still shows [s2idle] until a suspend happens. Only the kernel-parameter route makes it visible at rest. The old verify also asserted the literal string s2idle shallow [deep], and shallow is listed only where the platform advertises standby. This workstation is a DESKTOP (Gigabyte Z390 AORUS ULTRA, chassis type 3, no /sys/class/power_supply entries at all) and reads s2idle [deep] with no shallow, which confirms the string point but is NOT evidence about laptop firmware. Not exercised: no suspend was run, no laptop was tested, and the actual power draw claim of roughly 1%/hour on S3 was not measured anywhere.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** S3 is unvalidated by many vendors on post-2020 laptops — forcing `deep` can produce a machine that suspends but never resumes (black screen, hard power off, unsaved work lost). Test several cycles with nothing important open before trusting it.

**Fix.**

First check what the hardware advertises:

```bash
cat /sys/power/mem_sleep
```

The kernel lists only the states the platform claims, and the current one is in square brackets. `shallow` appears only where standby is advertised, so its absence is normal.

If `deep` is listed, test it for a few cycles:

```bash
echo deep | sudo tee /sys/power/mem_sleep
systemctl suspend
```

Make it permanent one of two ways, not both.

**Through systemd**, which writes `/sys/power/mem_sleep` at the moment of each suspend. The drop-in directory does not exist on a stock Omarchy 4 install, so create it:

```bash
sudo mkdir -p /etc/systemd/sleep.conf.d
```

```ini
# /etc/systemd/sleep.conf.d/mem-deep.conf
[Sleep]
MemorySleepMode=deep
```

Leave `/etc/systemd/sleep.conf` alone. It is shipped by the `systemd` package with every entry commented out, and a drop-in is the documented way to override it. `MemorySleepMode=` needs systemd 256 or newer.

**Or through the kernel command line**, which sets the default from boot. On plain Arch, add `mem_sleep_default=deep` wherever your bootloader keeps the command line. On Omarchy 4, which boots a UKI through Limine, command-line drop-ins live in `/etc/limine-entry-tool.d/`:

```bash
sudo mkdir -p /etc/limine-entry-tool.d
printf '%s\n' 'KERNEL_CMDLINE[default]+=" mem_sleep_default=deep"' \
  | sudo tee /etc/limine-entry-tool.d/deep-sleep.conf
sudo limine-mkinitcpio
```

Do not also edit `/etc/default/limine`. That file overrides the drop-ins rather than adding to them, and setting the parameter in both places duplicates it. Omarchy uses exactly this drop-in shape itself: `/usr/share/omarchy/install/hardware/apple/fix-t2.sh` writes `/etc/limine-entry-tool.d/t2-mac.conf` with `mem_sleep_default=deep` in it. `limine-mkinitcpio` alone re-reads the command line, rebuilds the initramfs and UKI, and updates the Limine entries. `limine-update` is only needed when the Limine binary on the ESP also has to change. The new command line takes effect at the next reboot.

If `deep` is **not** listed, look in the UEFI setup for a sleep-state option ("S3/Modern Standby support", "Windows 10" vs "Linux S3"). If there is none, stop fighting it and use suspend-then-hibernate instead (see the suspend-then-hibernate record).

Embedded-controller wakeups are a second common drain on s2idle machines:

```bash
cat /sys/module/acpi/parameters/ec_no_wakeup   # Y = EC wakeups suppressed
```

If it reads `N` and you do not rely on EC-driven wake, set the `acpi.ec_no_wakeup=1` kernel parameter. On Omarchy 4 that is another drop-in:

```bash
printf '%s\n' 'KERNEL_CMDLINE[default]+=" acpi.ec_no_wakeup=1"' \
  | sudo tee /etc/limine-entry-tool.d/ec-no-wakeup.conf
sudo limine-mkinitcpio
```

**Verify.** Which check applies depends on the route you took. With the `mem_sleep_default=deep` kernel parameter, reboot, then `cat /sys/power/mem_sleep` shows `deep` in the square brackets, for example `s2idle [deep]`, and `grep -o 'mem_sleep_default=deep' /proc/cmdline` confirms the parameter reached the running kernel. With `MemorySleepMode=deep`, systemd writes `/sys/power/mem_sleep` only as it suspends, so the file still reads `[s2idle]` beforehand and that is not a failure. Confirm the setting with `systemd-analyze cat-config systemd/sleep.conf | grep -i memorysleepmode`, suspend once, then check `journalctl -b -u systemd-suspend.service` shows no `Failed to write mode to /sys/power/mem_sleep`. Either way, note `cat /sys/class/power_supply/BAT*/capacity` before and after an hour of sleep. A healthy S3 laptop loses roughly 1%/hour or less.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers> · <https://man.archlinux.org/man/systemd-sleep.conf.5.en> · <https://github.com/systemd/systemd/blob/main/src/sleep/sleep.c>

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

## Fix hibernation that powers off but boots a fresh session instead of resuming

`hibernate-resume-hook-missing-or-misordered` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `limine`, `manjaro`, `mkinitcpio`, `omarchy`

**Symptom.** Hibernate works — the machine writes to disk and powers off cleanly — but on the next boot it just boots normally and my session is gone. No error message anywhere obvious.

**Cause.** The initramfs never attempted the resume. Two separate things have to be in place and either can be missing.

First, on a busybox-based initramfs the `resume` hook has to be in `HOOKS`. It has to come after the hooks that make the resume device available, which means after `udev`, and after `encrypt` or `lvm2` when the swap sits on LUKS or LVM. Its position relative to `filesystems` and `fsck` does not matter. Neither of those hooks has a runtime component, and `/usr/lib/initcpio/init` runs every `run_hook` function before it fsck's or mounts the root filesystem, so a `resume` at the end of the array still runs before root is mounted.

Second, the kernel has to be told where the hibernation image lives, through `resume=` and, for a swapfile, `resume_offset=`. On systemd 255 and later the `resume` hook installs and calls `/usr/lib/systemd/systemd-hibernate-resume`, which can also read the `HibernateLocation` EFI variable, so a UEFI machine sometimes resumes without those parameters and a BIOS machine will not.

On a systemd-based initramfs, one using the `systemd` hook instead of `udev`, the resume mechanism is built in and a `resume` hook must not be added at all.

> **Audit corrected this record.** The underlying problem is real: a busybox initramfs with no `resume` hook, or with no `resume=`/`resume_offset=` on the kernel cmdline, will not resume. Four other claims are wrong on Omarchy 4 and one is wrong on plain Arch too. First, the cause's mechanism is false. `/usr/lib/initcpio/install/filesystems` (mkinitcpio 41.1-1) has only a `build()` function and there is no `/usr/lib/initcpio/hooks/filesystems`, and `/usr/lib/initcpio/init` runs `run_hookfunctions 'run_hook' 'hook' $HOOKS` and only then calls `fsck_root` and `"$mount_handler" /new_root`. Root is mounted after every `run_hook`, whatever the array position, so `resume` after `filesystems` is not too late. The Arch wiki page this record already cites agrees: its own example is `HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems resume fsck)`, with `resume` after `filesystems`, and it requires only that `resume` follow `udev` and follow `encrypt` or `lvm2`. Confirmed live on this workstation, where the effective array ends `... filesystems fsck btrfs-overlayfs resume` and `/sys/power/resume` still reads `253:0`, matching `/dev/mapper/root`, so the hook ran and resolved the device from last position. Second, `sudo mkinitcpio -P` fails outright on Omarchy 4: `/etc/mkinitcpio.d/` is empty, and `/usr/bin/mkinitcpio` line 986 does `[[ -e "${_optpreset[0]}" ]] || die 'No presets found in %s'`. Presets are empty because `limine-mkinitcpio-hook` ships `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`, which overrides the stock hook and execs `limine-mkinitcpio-install` instead of `/usr/share/libalpm/scripts/mkinitcpio`, and only the stock script's `generate_presets` writes `/etc/mkinitcpio.d/<pkgbase>.preset`. Third, the fix's sample `HOOKS=(...)` line is not Omarchy's array and editing `/etc/mkinitcpio.conf` on Omarchy has no effect, because `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` (owned by `omarchy-settings` 4.0.2-1) assigns `HOOKS` wholesale afterwards. Fourth, the danger tells the reader to keep a fallback boot entry, and Omarchy 4 has none: `MKINITCPIO_FALLBACK` is set nowhere, and `limine-mkinitcpio-install` removes any fallback UKI when it is unset. The real recovery path is a Snapper snapshot entry, with `snapper` 0.13.1-3 and `limine-snapper-sync` 1.31.0-1 installed and `BOOT_ORDER="*, *fallback, Snapshots"` in `/etc/limine-entry-tool.d/omarchy-defaults.conf`. Fifth, the verify names `/boot/initramfs-linux.img`, which Omarchy 4 does not keep: `ENABLE_UKI=yes` and `CUSTOM_UKI_NAME="omarchy"` make `limine-mkinitcpio-install` build `/boot/EFI/Linux/omarchy_linux.efi` and delete the separate images, and `/boot` is a vfat ESP mounted `dmask=0077`, so `ls /boot` fails for a normal user. The cited issue does not support the record: `omacom/omarchy` 8471 is open with zero comments and its author writes that he has not been able to demonstrate a resume failure attributable to the ordering. Two sibling reports, 8888 (an open unmerged pull request) and 10375, repeat the same wrong mechanism and are also unconfirmed. I dropped the issue URL and added the `quattro` copy of `omarchy-hibernation-setup`, which is what actually writes the drop-ins. Severity lowered from critical to high because the consequence is a lost session on a machine that boots normally, not an unbootable system or data loss. NOT exercised: I did not run a hibernate and power-on cycle, did not rebuild an initramfs, and could not read `/boot`, which needs root.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A malformed `HOOKS` array produces an initramfs that cannot mount root, which is an unbootable system.

On Omarchy 4 there is no fallback boot entry to fall back to. `MKINITCPIO_FALLBACK` is set nowhere, and `limine-mkinitcpio-install` deletes any fallback UKI while it is unset, so the Limine menu carries one `Omarchy` entry plus Snapper snapshots. `ENABLE_LIMINE_FALLBACK=yes` in `/etc/limine-entry-tool.d/omarchy-defaults.conf` is about installing Limine on the UEFI fallback path and does not give you a fallback initramfs. Take a snapshot before rebuilding and know how to boot one from the Limine menu:

```bash
omarchy-snapshot create
```

On plain Arch, keep the `fallback` preset entry and confirm it boots before relying on it. Have installation media on hand either way.

**Fix.**

Print the array mkinitcpio will actually use. Drop-ins are concatenated onto `/etc/mkinitcpio.conf` in version-sorted basename order, so an assignment or an append in a later file wins:

```bash
bash -c 'source /etc/mkinitcpio.conf
         for f in /etc/mkinitcpio.conf.d/*.conf; do source "$f"; done
         printf "%s\n" "${HOOKS[@]}" | nl'
```

`resume` has to appear somewhere after `udev`, and after `encrypt` or `lvm2` if the swap is on LUKS or LVM. It does not have to precede `filesystems`.

**Omarchy 4.** Do not edit `/etc/mkinitcpio.conf` and do not run `mkinitcpio -P`. `/etc/mkinitcpio.conf` is package-stock and `HOOKS` is assigned by `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, so an edit to the main file is overwritten at build time. `/etc/mkinitcpio.d/` is empty on Omarchy, so `mkinitcpio -P` exits with `No presets found in /etc/mkinitcpio.d`. Let Omarchy configure it:

```bash
omarchy-hibernation-setup
```

That creates the `/swap` subvolume and `/swap/swapfile`, adds it to `/etc/fstab`, writes `HOOKS+=(resume)` into `/etc/mkinitcpio.conf.d/omarchy_resume.conf`, writes `resume=` and `resume_offset=` into `/etc/limine-entry-tool.d/resume.conf`, and rebuilds the UKI. Check what it produced:

```bash
cat /etc/mkinitcpio.conf.d/omarchy_resume.conf
cat /etc/limine-entry-tool.d/resume.conf
omarchy-hibernation-available && echo available
```

If only the initramfs and boot entries need rebuilding:

```bash
sudo limine-mkinitcpio
```

**Plain Arch, EndeavourOS, CachyOS, Manjaro.** Put `resume` in `HOOKS` in `/etc/mkinitcpio.conf` after `udev`, and after `encrypt` or `lvm2` if they are present:

```
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt lvm2 filesystems resume fsck)
```

```bash
sudo mkinitcpio -P
```

**Both.** Confirm the kernel is told where the image is:

```bash
tr ' ' '\n' </proc/cmdline | grep -E '^resume'
```

For a swapfile you need `resume=` naming the device that holds it and `resume_offset=` for the file's physical offset. On btrfs:

```bash
sudo btrfs inspect-internal map-swapfile -r /swap/swapfile
```

On Omarchy set those in `/etc/limine-entry-tool.d/resume.conf`, not in `/etc/default/limine`, and rebuild with `sudo limine-mkinitcpio`.

**systemd-based initramfs.** If the array contains `systemd` rather than `udev`, resume is already provided. Do not add a `resume` hook. Check `resume=` and `resume_offset=` instead.

**Verify.** After a reboot with hibernation configured, the resume hook has run if `/sys/power/resume` names the resume device rather than `0:0`:

```bash
cat /sys/power/resume          # for example 253:0
cat /sys/power/resume_offset   # non-zero when hibernating to a swapfile
ls -l /dev/mapper/root         # major and minor must match /sys/power/resume
```

On Omarchy also:

```bash
omarchy-hibernation-available && echo available
```

Then hibernate and power the machine on. `journalctl --list-boots` shows no new boot, and the session is still the one you left.

Do not use `lsinitcpio /boot/initramfs-linux.img` on Omarchy 4. `limine-mkinitcpio-install` builds `/boot/EFI/Linux/omarchy_linux.efi` and deletes the separate `initramfs` and `vmlinuz` files, and `/boot` is a vfat ESP mounted `dmask=0077`, so it cannot be listed without root. On plain Arch, where the image is kept:

```bash
sudo lsinitcpio -l /boot/initramfs-linux.img | grep resume
```

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/bin/omarchy-hibernation-setup>

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

**Symptom.** `systemctl hibernate` does not power the machine off. Either it hangs with the display dead and the keyboard backlight still on, and only a forced power-off recovers it, or it reboots instead of shutting down and the next cold boot resumes the session anyway. In the hang case the last kernel lines are:
```
PM: hibernation: Creating image
PM: hibernation: Need to copy 3457488 pages
ACPI: PM: Restoring platform NVS memory
```
and `swsusp_save()` printed none of its own outcomes, so the machine was already unwinding.

**Cause.** The firmware's ACPI S4 sleeping state is unreliable on this board, and systemd's compiled default is `HibernateMode=platform shutdown`, which tries `platform` first. Two different failures come out of that. On some machines the kernel aborts inside `swsusp_save()` while creating the image, unwinds and half-resumes, so no image is ever written and the machine sits powered on with a dead display. Reported on the ASUS ROG Zephyrus G14 (GA403UV) in omacom/omarchy#8589. On others the image is written correctly but the platform reboots instead of entering S4, and the following cold boot resumes the session. Reported on a pre-T2 Intel MacBookPro11,1 in omacom/omarchy#10038. The built-in `shutdown` fallback rescues neither, because systemd falls back only when the write to `/sys/power/disk` itself fails, and here the write succeeds and the firmware misbehaves afterwards.

> **Audit corrected this record.** The fix itself is right and survives every check. The Arch wiki section "System does not power off when hibernating", fetched as raw wikitext, prescribes exactly HibernateMode=shutdown in /etc/systemd/sleep.conf.d/hibernatemode.conf, and the adjacent section "Operating system not found (or wrong OS booting) when booting after hibernation" supports the record's extra claim about an external boot disk, which was previously unsourced in effect. The installed systemd-sleep.conf(5) on systemd 261.2-1 still documents HibernateMode=, and /etc/systemd/sleep.conf on this machine shows the compiled default as HibernateMode=platform shutdown, so platform is tried first. The cause is wrong against the record's own cited issue. I read omacom/omarchy#8589 in full through the API: on that machine swsusp_save() aborted DURING image creation, none of its own outcome lines printed even with pm_debug_messages=1, and the kernel unwound and half-resumed, so no image was written at all. The record says the opposite, that the image is written correctly. The "image written, then reboots" shape the record describes is real but belongs to a second machine family, omacom/omarchy#10038 (pre-T2 Intel MacBookPro11,1), linked from a comment on 8589. Both shapes are now in the cause, labelled. Three Omarchy 4 corrections, all checked here. /etc/systemd/sleep.conf.d/ does not exist on a stock install (ls reports no such directory, the only file is /etc/systemd/sleep.conf owned by systemd 261.2-1 with everything commented), so the fix now creates it. sudo systemctl daemon-reload was the wrong refresh: systemctl cat systemd-hibernate.service shows ExecStart=/usr/lib/systemd/systemd-sleep hibernate, and that binary reads sleep.conf and its drop-ins at every invocation, so nothing needs reloading. It is replaced with systemd-analyze cat-config systemd/sleep.conf. And the danger warned about resume= and resume_offset= without saying where they live on Omarchy 4: /usr/share/omarchy/bin/omarchy-hibernation-setup writes them into /etc/limine-entry-tool.d/resume.conf and the resume hook into /etc/mkinitcpio.conf.d/omarchy_resume.conf, both of which are present on this workstation, and they reach the kernel only after limine-mkinitcpio and a reboot. I also corrected the verify: the kernel strings the report quotes are pm_pr_dbg and pm_deferred_pr_dbg calls in kernel/power/hibernate.c line 850 and kernel/power/snapshot.c lines 2121 and 2145, so they print only with pm_debug_messages=1, and the exact current text is "Image created (%d pages copied, %d zero pages)". Severity and frequency are left alone. Not exercised: nothing was hibernated. This workstation is a DESKTOP (Gigabyte Z390 AORUS ULTRA, no battery), so its /sys/power/disk reading of [platform] shutdown reboot suspend test_resume confirms only that platform is the default here, and says nothing about the laptop firmware in either issue. The basecamp/omarchy URL on the record still redirects but the repository is now omacom/omarchy, so the canonical URL replaces it.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** With `HibernateMode=shutdown` the machine looks like a normal power-off. If `resume=` or `resume_offset=` are wrong you will boot a fresh session and silently lose everything that was open. On Omarchy 4 those two parameters live in `/etc/limine-entry-tool.d/resume.conf` and reach the kernel only after `sudo limine-mkinitcpio` and a reboot, so check that `/proc/cmdline` actually carries them before trusting a hibernate.

**Fix.**

Tell systemd to write the image and then do a plain shutdown instead of entering S4. The drop-in directory does not exist on a stock Omarchy 4 install, so create it first:

```bash
sudo mkdir -p /etc/systemd/sleep.conf.d
```

```ini
# /etc/systemd/sleep.conf.d/hibernate-mode.conf
[Sleep]
HibernateMode=shutdown
```

Nothing needs restarting or reloading. `systemd-hibernate.service` runs `ExecStart=/usr/lib/systemd/systemd-sleep hibernate`, and that binary reads `sleep.conf` and its drop-ins on every invocation. Check the merged configuration, then hibernate:

```bash
systemd-analyze cat-config systemd/sleep.conf | grep -i hibernatemode
systemctl hibernate
```

Leave `/etc/systemd/sleep.conf` alone. It is shipped by the `systemd` package with every entry commented out, and a drop-in is the documented way to override it.

The same setting fixes the related "Operating system not found" or wrong-OS-boots case after hibernating from an external disk.

On Omarchy 4 this only helps if hibernation is configured at all. `omarchy-hibernation-setup` is what configures it: a btrfs swapfile at `/swap/swapfile`, `HOOKS+=(resume)` in `/etc/mkinitcpio.conf.d/omarchy_resume.conf`, `resume=` and `resume_offset=` in `/etc/limine-entry-tool.d/resume.conf`, then a UKI rebuild with `limine-mkinitcpio`. Confirm that before blaming the sleep mode:

```bash
omarchy-hibernation-available
echo "exit=$?"          # 0 means swap and the resume hook are both in place
cat /etc/limine-entry-tool.d/resume.conf
grep -o 'resume=[^ ]*' /proc/cmdline
```

**Verify.** `systemctl hibernate` results in a fully powered-off machine (fans off, no LEDs), and pressing the power button resumes the previous session rather than booting fresh. For a log-level check, add `pm_debug_messages=1` to the kernel command line first, because the hibernation progress lines are debug-only: `Image created (N pages copied, N zero pages)` from `kernel/power/snapshot.c` says the image was built, and `Hibernation image restored successfully.` from `kernel/power/hibernate.c` appears only on the resume-from-image path, so together they prove a real write, power-off and restore cycle. Read them with `journalctl -k -b | grep -i 'hibernation'`.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://man.archlinux.org/man/systemd-sleep.conf.5.en> · <https://github.com/omacom/omarchy/issues/8589> · <https://github.com/omacom/omarchy/issues/10038> · <https://github.com/torvalds/linux/blob/master/kernel/power/hibernate.c> · <https://github.com/torvalds/linux/blob/master/kernel/power/snapshot.c>

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

`touchpad-kernel-panic-on-resume-intel-lpss` · severity: **high** · frequency: **rare** · applies to: `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `mkinitcpio`, `omarchy`

**Symptom.** Resuming gives a dead machine with the Caps Lock LED blinking, which is a kernel panic. Nothing is written to the journal because the panic happens before the disk is writable again. Intel laptop with an I2C/LPSS touchpad.

The only reported case is resume from hibernation, where the initramfs runs again to restore the image. Resume from suspend to RAM never re-enters the initramfs, so if your machine dies coming back from an ordinary suspend, this record is probably not your problem.

**Cause.** `MODULES=` in mkinitcpio does more than copy a module into the image. `/usr/lib/initcpio/init` runs `modprobe -qab $MODULES` before anything else, so naming `intel_lpss_pci` there force-loads the driver for the LPSS controller behind the touchpad early, before the hibernation image is restored. The `autodetect` hook already copies that module into the image on a laptop that uses it, so mere presence is not the fix, the early load is.

The evidence is thin and old. The Arch wiki's only citation is one 2017 forum reply about a hibernation resume hang, and current mainline `drivers/mfd/intel-lpss.c` carries a full `LATE_SYSTEM_SLEEP_PM_OPS` with an explicit resume-children-before-sleep step, so the original bug may well be gone on kernel 7.1.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, Hyprland 0.56.2-1, kernel 7.1.9-arch1-2), which is a DESKTOP with an NVIDIA card, so no Intel LPSS touchpad is present and the panic itself, the fix and the suspend cycles could NOT be exercised. `lsmod | grep intel_lpss` returns nothing here and `modinfo intel_lpss_pci` shows the module exists at `/lib/modules/7.1.9-arch1-2/kernel/drivers/mfd/intel-lpss-pci.ko.zst` with no module parameters, so the `lsmod` step in the fix is sound but unexercised. Four things were wrong. First, the boot command: `/etc/mkinitcpio.d/` is empty on this machine and neither the `linux` nor the `mkinitcpio` package ships a preset into it, so `sudo mkinitcpio -P` is a no-op on Omarchy 4, and `/usr/local/bin/mkinitcpio` (from limine-mkinitcpio-hook 1.37.1-1) is a wrapper that warns about exactly this and offers `limine-mkinitcpio`. Second, the file: Omarchy assigns MODULES and HOOKS from `/etc/mkinitcpio.conf.d/` (nvidia.conf, omarchy_hooks.conf, omarchy_resume.conf, thunderbolt_module.conf are present), `/etc/mkinitcpio.conf` is package stock, and `/usr/bin/mkinitcpio` lines 1120 to 1137 concatenate the main file then the drop-ins in `sort -V` order, so a drop-in using `+=` is the correct shape. Third, the verify: there is no `/boot/initramfs-linux.img` on a UKI install, the image is inside `/boot/EFI/Linux/omarchy_linux.efi` (derived from CUSTOM_UKI_NAME="omarchy" in `/etc/limine-entry-tool.d/omarchy-defaults.conf` and the UKI_PATH line in `/usr/share/libalpm/scripts/limine-mkinitcpio-install`), `/boot` is `dmask=0077` so the read needs root, and `grep intel_lpss` would miss the file because it is stored as `intel-lpss-pci.ko.zst` with hyphens. lsinitcpio 41.1 does unpack a UKI (`detect_uki`/`unpack_uki`). Fourth, the danger told the reader to keep a fallback boot entry, and Omarchy 4 has none: `MKINITCPIO_FALLBACK` is unset in `/etc/default/limine` and in every `/etc/limine-entry-tool.d/*.conf`, and `limine-list` shows only Omarchy > linux, a Snapshots submenu and the EFI fallback bootloader, so Snapshots is the real recovery path. On sources: the cited Arch wiki section 'Touchpad causes a kernel panic on resume' does say what the record claims, but its single citation is https://bbs.archlinux.org/viewtopic.php?id=231881, which I read in full. It is titled 'Stuck during resume from hibernation', dated 2017, and the whole fix is one reply of 2017-12-23 saying intel_lpss_pci in MODULES solved it for that person. There is no evidence for suspend to RAM anywhere, and the initramfs is not re-entered on an S3 or s2idle resume, which is why the symptom now names hibernation. The cause was rewritten because presence in the image is not the mechanism: `/usr/lib/initcpio/init` line 38 runs `modprobe -qab $MODULES`, and the `autodetect` hook already pulls the module in on affected hardware. Frequency was moved from occasional to rare because the whole evidence base is one report from kernel 4.14 era, and current mainline `drivers/mfd/intel-lpss.c` has a full LATE_SYSTEM_SLEEP_PM_OPS with an explicit resume-children-before-sleep step, so the 2017 failure may no longer exist. I could not test whether it does. The record carried no kernel version floor and no fixed-in claim, so there was none to correct.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** This is the opposite of the fix for a black screen on hibernate resume, where modules have to be removed from `MODULES` instead. Change one thing at a time.

Omarchy 4 builds no fallback boot entry. `MKINITCPIO_FALLBACK` is unset in `/etc/default/limine` and in every `/etc/limine-entry-tool.d/*.conf`, so `limine-list` shows only `Omarchy > linux`, a `Snapshots` submenu and the EFI fallback bootloader. If a rebuilt initramfs stops the machine booting, recover from a Snapshots entry, not from a fallback kernel entry that does not exist. On plain Arch, keep the `-fallback` entry your bootloader already generates.

**Fix.**

Force the module to load early in the initramfs. On Omarchy 4 and on plain Arch the file you edit and the command you run are different.

**On Omarchy 4.** `/etc/mkinitcpio.conf` is package stock and Omarchy assigns `MODULES` and `HOOKS` from drop-ins in `/etc/mkinitcpio.conf.d/`. Add your own drop-in and use `+=`, so it cannot clobber the `MODULES` that `nvidia.conf` and `thunderbolt_module.conf` set:

```bash
printf 'MODULES+=(intel_lpss_pci)\n' | sudo tee /etc/mkinitcpio.conf.d/intel_lpss.conf
sudo limine-mkinitcpio
```

Do not use `sudo mkinitcpio -P` here. Omarchy 4 boots a UKI that `limine-mkinitcpio-hook` builds from `/usr/lib/modules/*/pkgbase`, and `/etc/mkinitcpio.d/` is empty, so `-P` finds no preset and silently does nothing. `/usr/local/bin/mkinitcpio` is a wrapper that spots `-P` or `-p`, warns that it did not update the Limine entries, and offers to run `limine-mkinitcpio` for you. `sudo limine-update` also works and additionally reinstalls the bootloader.

**On plain Arch** with a conventional initramfs and no Limine UKI:

```
# /etc/mkinitcpio.conf
MODULES=(intel_lpss_pci)
```

```bash
sudo mkinitcpio -P
```

If `MODULES=()` already has entries, append rather than replace.

Either way, confirm the module is the one your touchpad sits behind:

```bash
lsmod | grep intel_lpss
```

**Verify.** On Omarchy 4 the initramfs lives inside the UKI and `/boot` is mounted `dmask=0077`, so the check needs root. `lsinitcpio` 41 unpacks a UKI, and the file inside the image is named with hyphens, so grep for `intel-lpss` and not `intel_lpss`:

```bash
sudo lsinitcpio -l /boot/EFI/Linux/omarchy_linux.efi | grep intel-lpss
```

On plain Arch: `sudo lsinitcpio -l /boot/initramfs-linux.img | grep intel-lpss`.

Then five hibernate and resume cycles complete without a panic.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://bbs.archlinux.org/viewtopic.php?id=231881> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/mfd/intel-lpss.c> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/mfd/intel-lpss-pci.c>

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

> **Audit corrected this record.** Checked the cause against the Arch wiki raw wikitext for Power management/Suspend and hibernate, which states that the suspend image cannot span multiple swap partitions or swap files and that a `Failed to put system to sleep. System resumed again` line means not enough free swap was available, so the cause and the symptom hold on plain Arch and on Omarchy 4. The `/etc/tmpfiles.d/hibernation_image_size.conf` snippet is verbatim from that page and does not collide with the `/etc/tmpfiles.d/omarchy-zswap.conf` that omarchy-settings 4.0.2-1 ships on this machine. Read `/usr/share/omarchy/bin/omarchy-hibernation-setup` and `omarchy-hibernation-available` here: the setup script does create a Btrfs `/swap` subvolume with a swapfile sized to MemTotal, as the record says. Two defects in the Omarchy paragraph. First, `omarchy-hibernation-available` also requires `/etc/mkinitcpio.conf.d/omarchy_resume.conf` to exist, not only that the non-zram swap sum exceeds `/sys/power/image_size`, so the record's advice to grow swap by hand leaves the Hibernate menu entry hidden and the record never says so. Second, the Omarchy 4 documented entry point is `omarchy hibernation setup`, confirmed with `omarchy hibernation --help` on this workstation and in `manual/36-system-sleep.md` on the quattro branch, not the bare script name the record gives. I also replaced the invented `/dev/mapper/extra-swap` in the swapoff example with a real device taken from `swapon --show`, and added that Omarchy 4 runs zram at swap-priority 100 while the hibernation swapfile gets pri=0, which makes the multiple-swap consolidation case rare on a stock Omarchy machine. Confirmed on this workstation: `/proc/swaps` shows `/swap/swapfile` at priority 0 and `/dev/zram0` at priority 100, and `/sys/power/image_size` is 13351321600 against a MemTotal of 32784988 kB. NOT exercised: I did not run `systemctl hibernate` or change any power state, so the resume path itself is unverified here, and this machine is a desktop, so no laptop-only behaviour was tested.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Growing swap consumes disk equal to RAM (Omarchy warns: 32 GB RAM means 32 GB of free space on the boot drive). Running `swapoff` on a busy system can OOM-kill processes if there is not enough free RAM to absorb the swapped-out pages.

**Fix.**

Check what you have:

```bash
swapon --show
free -h
cat /sys/power/image_size
```

Either grow one swap space, or shrink the image. To shrink it persistently, on plain Arch and on Omarchy 4 alike:

```bash
sudo tee /etc/tmpfiles.d/hibernation_image_size.conf <<'EOF'
#    Path                   Mode UID  GID  Age Argument
w    /sys/power/image_size  -    -    -    -   0
EOF
sudo systemd-tmpfiles --create
```

`0` asks the kernel to make the image as small as it can. Test immediately, before committing to the tmpfiles snippet:

```bash
echo 0 | sudo tee /sys/power/image_size
systemctl hibernate
```

If `swapon --show` lists more than one non-zram swap, free space cannot be pooled. Give them different priorities so one stays mostly empty, or temporarily switch one off so usage consolidates. Take the real device name from `swapon --show`, for example:

```bash
sudo swapoff /dev/nvme0n1p3
systemctl hibernate
```

**On Omarchy 4** do not build the swapfile by hand. The documented entry point is:

```bash
omarchy hibernation setup
```

(the underlying script is `/usr/share/omarchy/bin/omarchy-hibernation-setup`, and `omarchy hibernation remove` undoes it). It creates a Btrfs `/swap` subvolume with `chattr +C`, makes `/swap/swapfile` sized to `MemTotal` with `btrfs filesystem mkswapfile`, adds it to `/etc/fstab` at `pri=0`, writes `HOOKS+=(resume)` into `/etc/mkinitcpio.conf.d/omarchy_resume.conf` and `resume=`/`resume_offset=` into `/etc/limine-entry-tool.d/resume.conf`, then rebuilds the UKI with `limine-mkinitcpio`. It needs the default Limine bootloader and refuses otherwise.

The Hibernate entry in the Omarchy menu is guarded by `omarchy-hibernation-available`, and that script tests **two** conditions, not one:

```bash
# /usr/share/omarchy/bin/omarchy-hibernation-available
SWAPSIZE_KB=$(awk '!/Filename|zram/ {sum += $3} END {print sum+0}' /proc/swaps)
SWAPSIZE=$(( 1024 * ${SWAPSIZE_KB:-0} ))
HIBERNATION_IMAGE_SIZE=$(cat /sys/power/image_size)

if (( SWAPSIZE > HIBERNATION_IMAGE_SIZE )) && [[ -f /etc/mkinitcpio.conf.d/omarchy_resume.conf ]]; then
```

So growing swap on its own is not enough on Omarchy. Without `/etc/mkinitcpio.conf.d/omarchy_resume.conf` the Hibernate entry stays hidden however much swap you add, which is why `omarchy hibernation setup` is the route rather than a hand-rolled swapfile.

One Omarchy 4 detail that makes the multiple-swap case rare here: the shipped zram device runs at `swap-priority = 100` and the hibernation swapfile at `pri=0`, so the swapfile normally stays empty, and `omarchy-hibernation-available` excludes zram from its sum anyway. Check with:

```bash
cat /proc/swaps
```

**Verify.** `systemctl hibernate` powers the machine fully off, and after power-on your session comes back with all applications where you left them. `journalctl -b -1 | grep 'hibernation:'` shows no `Error -12`.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-available> · <https://learn.omacom.io/2/the-omarchy-manual/103/system-sleep> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/bin/omarchy-hibernation-available> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/bin/omarchy-hibernation-setup> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/manual/36-system-sleep.md>

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

**Cause.** logind honours inhibitor locks. A `block` inhibitor prohibits sleep indefinitely (Steam while downloading, a browser playing video, mpv, a package manager, an SSH session holding `systemd-inhibit`). A `delay` inhibitor only postpones sleep up to `InhibitDelayMaxSec`, which is 5 seconds on stock systemd and 15 seconds on Omarchy 4 because `omarchy-settings` ships a drop-in raising it. Delay inhibitors are normal: NetworkManager, UPower and, on Omarchy 4, the user unit `omarchy-sleep-lock.service` all hold one, the last so `omarchy-system-sleep-lock` can lock the session before the machine sleeps. Separately, an idle-only inhibitor stops logind's `IdleAction` from firing without blocking a manual `systemctl suspend`, which is why the two symptoms look different. On Omarchy 4 that second half is the part most advice gets wrong: `IdleAction` is set to `ignore`, idle is detected by a Quickshell plugin using the Wayland idle-inhibit protocol rather than by logind, and the whole idle path can be switched off by a state file that no inhibitor listing will ever show.

> **Audit corrected this record.** Every systemd claim held and every Omarchy claim was Omarchy 3. Checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, systemd 261.2-1, Hyprland 0.56.2-1): `systemd-inhibit --list` and its `--what`/`--mode` filters print the columns the record describes, `-i` is `--check-inhibitors=no`, `InhibitDelayMaxSec=` defaults to 5, `LidSwitchIgnoreInhibited=` defaults to yes and the three key options to no, all read from the installed logind.conf(5) and systemctl(1) and systemd-inhibit(1) man pages. Four defects. First, `hypridle` is not installed (`pacman -Q hypridle` fails), there is no `~/.config/hypr/hypridle.conf` and none in `/usr/share/omarchy/config/hypr/`. A `gh api` query on `omacom/omarchy` tree `quattro` returns zero hypridle paths, while the two cited `basecamp/omarchy/master` raw URLs still serve the Omarchy 3 hypridle.conf and the old pkill-based toggle, which is where the error came from. Omarchy 4 does idle in `/usr/share/omarchy/shell/plugins/services/idle/Service.qml` and locks before sleep via the user unit `omarchy-sleep-lock.service` running `omarchy-system-sleep-monitor`. Second, `omarchy-toggle-idle` on 4.0.2-1 takes `toggle|stay-awake|allow-idle|status` and only touches or removes `~/.local/state/omarchy/indicators/stay-awake`, so the record's double invocation is a no-op round trip and the stay-awake state, which disables idle with no inhibitor to see, was never mentioned. This machine is currently in that state (`omarchy-shell idle status` returns `"stayAwake":true,"enabled":false`). Third, step 3's `/etc/systemd/logind.conf.d/10-inhibit.conf` is dead on Omarchy, because omarchy-settings owns `20-inhibit-delay.conf` with `InhibitDelayMaxSec=15`, drop-ins sort lexicographically with the last writer winning, and the live `busctl get-property ... InhibitDelayMaxUSec` reads `t 15000000`. Fourth, step 6's logind idle branch is inert here because `IdleAction` reads `s "ignore"` and Omarchy's idle monitor sets `respectInhibitors: true` on a Wayland idle-inhibit monitor, so an app blocking the lock shows as `.inhibitingIdle == true` in `hyprctl clients -j` (field confirmed present on 0.56.2) and never in `systemd-inhibit --list --what=idle`, which was empty here. Rewrote the fix with plain-Arch and Omarchy 4 branches labelled, added `omarchy-debug-idle`, the stay-awake trap and the `omarchy-hyprland-session-locked` stale-lock check, and switched logind restart to reload (`CanReload=yes`). Not exercised: nothing was suspended, no drop-in was written and logind was not reloaded, so the new InhibitDelayMaxSec override and the lid setting are read from the man page and the shipped drop-in rather than from a live change. The record was not GNOME or KDE mis-specialised.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `systemctl suspend -i` overrides the lock rather than resolving it. If the inhibitor was a package upgrade, a disk write, a `dd`/`rsync` or a VM snapshot, suspending through it can corrupt that work. Read the `Why` string before you override. On Omarchy 4 it also skips nothing of the lock path, because that inhibitor is `delay` rather than `block`, but killing the `Omarchy` sleep inhibitor by PID does defeat it and leaves the machine suspending with the session unlocked. Use `sudo systemctl reload systemd-logind` rather than `restart` after editing logind drop-ins, because a restart can tear down running graphical sessions. Leaving `omarchy-toggle-idle stay-awake` set means the machine never locks or blanks at all, which is a security regression that no inhibitor listing will reveal. Omarchy 4's lock screen has no `unlock()` IPC and survives its own client dying, so do not experiment with locking on a machine you can only reach over ssh.

**Fix.**

**1. See who is holding a lock, the first-line diagnostic**

```bash
systemd-inhibit --list
systemd-inhibit --list --mode=block          # only the hard blockers
systemd-inhibit --list --what=sleep
systemd-inhibit --list --what=idle
```

The columns are `WHO UID USER PID COMM WHAT WHY MODE`. Quit that app, or kill the PID.

On a healthy Omarchy 4 machine the sleep list already has three delay inhibitors and none of them is a fault:

```
WHO            UID  USER        PID  COMM            WHAT  WHY                                       MODE
NetworkManager 0    root        1470 NetworkManager  sleep NetworkManager needs to turn off networks delay
UPower         0    root        2330 upowerd         sleep Pause device polling                      delay
Omarchy        1000 you         2531 systemd-inhibit sleep Lock screen before suspend                delay
```

The third is the user unit `omarchy-sleep-lock.service` running `/usr/bin/omarchy-system-sleep-monitor`. Do not kill it. It is what locks the screen before the machine sleeps, and without it the machine suspends with the session exposed.

**2. Override once, deliberately**

```bash
systemctl suspend -i        # -i is shorthand for --check-inhibitors=no
```

**3. Give delay-mode inhibitors more room**

Plain Arch: `InhibitDelayMaxSec=` defaults to 5 seconds.

Omarchy 4: `omarchy-settings` already ships `/etc/systemd/logind.conf.d/20-inhibit-delay.conf` setting `InhibitDelayMaxSec=15`, because Quickshell needs longer than 5 seconds to secure the session when closing the lid also reconfigures displays. Read the effective value rather than assuming a default:

```bash
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
  org.freedesktop.login1.Manager InhibitDelayMaxUSec     # t 15000000 on Omarchy 4
```

Drop-ins are read in lexicographic filename order and the last file to set an option wins, so a file named `10-inhibit.conf` is silently overridden by Omarchy's `20-inhibit-delay.conf` and changes nothing. Name yours so it sorts after. systemd recommends the 60 to 90 range for local drop-ins:

`/etc/systemd/logind.conf.d/90-inhibit.conf`:

```ini
[Login]
InhibitDelayMaxSec=20
```

```bash
sudo systemctl reload systemd-logind
```

Prefer `reload` over `restart`. `systemctl show systemd-logind -p CanReload` prints `CanReload=yes`, and a restart can tear down the graphical session.

**4. Make lid close respect block inhibitors**

By default `LidSwitchIgnoreInhibited=yes`, so closing the lid suspends regardless of who is blocking. To make it obey, and again using a filename that sorts after Omarchy's own drop-ins:

`/etc/systemd/logind.conf.d/90-lid.conf`:

```ini
[Login]
LidSwitchIgnoreInhibited=no
```

(`SuspendKeyIgnoreInhibited=`, `HibernateKeyIgnoreInhibited=`, `PowerKeyIgnoreInhibited=` and `RebootKeyIgnoreInhibited=` already default to `no`.)

**5. Omarchy 4 has no hypridle, so ignore every hypridle recipe**

`pacman -Q hypridle` returns "package not found" and there is no `~/.config/hypr/hypridle.conf`. Idle detection, the screensaver and the lock are a Quickshell plugin at `/usr/share/omarchy/shell/plugins/services/idle/`. The hypridle options `inhibit_sleep`, `ignore_dbus_inhibit` and `ignore_systemd_inhibit` do not exist here. Anything telling you to edit `hypridle.conf` is Omarchy 3 advice.

The one command that dumps the whole idle, screensaver and lock picture:

```bash
omarchy-debug-idle
```

The two IPC calls it wraps, if you want just those:

```bash
omarchy-shell idle status | jq .
omarchy-shell lock status | jq .
```

**6. The Omarchy trap: stay-awake**

`omarchy-toggle-idle` does not start or stop a daemon. It creates or removes `~/.local/state/omarchy/indicators/stay-awake`, and while that file exists the Quickshell idle monitor is disabled outright. Nothing dims, screensaves or locks, and `systemd-inhibit --list` shows nothing at all, because no inhibitor is involved.

```bash
omarchy-toggle-idle status     # {"enabled":true,...} means stay-awake is ON, idle is OFF
ls -l ~/.local/state/omarchy/indicators/stay-awake
omarchy-toggle-idle allow-idle # idle back on
omarchy-toggle-idle stay-awake # idle off, on purpose
```

The accepted arguments are `toggle`, `stay-awake`, `allow-idle` and `status`. Running it twice is a round trip back to where you started, not a restart.

**7. An app blocking idle on Omarchy 4 is a Wayland inhibitor, not a logind one**

The Quickshell idle monitor runs with `respectInhibitors: true`, so a browser playing video takes an `idle-inhibit-unstable-v1` lock that the compositor honours and logind never sees. `systemd-inhibit --list --what=idle` will be empty while the screen refuses to lock. Ask Hyprland instead:

```bash
hyprctl clients -j | jq -r '.[] | select(.inhibitingIdle == true) | [.pid,.class,.title] | @tsv'
```

**8. logind IdleAction is inert on Omarchy 4**

`loginctl` idle hints and logind's `IdleAction=` only matter on a plain Arch or systemd desktop. Omarchy leaves `IdleAction=ignore`, so this branch will never explain an Omarchy symptom:

```bash
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
  org.freedesktop.login1.Manager IdleAction      # s "ignore" on Omarchy 4
loginctl list-sessions
loginctl show-session "$XDG_SESSION_ID" -p IdleHint -p IdleSinceHint
```

**9. If the screen locked and will not come back**

Omarchy 4's lock is an `ext-session-lock` surface drawn by `omarchy-shell`. `hyprlock` is not installed, the lock IPC exposes no `unlock()`, and the compositor stays locked even if the lock client dies. There is no headless way out: type the password at the console, or power cycle. Detect the stale case with:

```bash
omarchy-hyprland-session-locked; echo $?    # 0 locked, 1 unlocked, 2 undetermined
```

**10. Take a deliberate lock yourself** when you want to protect a long job:

```bash
systemd-inhibit --what=sleep --why="backup running" -- restic backup /home
```

`--mode=` defaults to `block` and `--what=` defaults to `idle:sleep:shutdown`, so the explicit `--what=sleep` above narrows it.

**Verify.** `systemd-inhibit --list --mode=block` is empty (or lists only things you expect), then `systemctl suspend` without `-i` actually suspends. On Omarchy 4, `systemd-inhibit --list --what=sleep` should still show three `delay` entries, including `Omarchy` with `Lock screen before suspend`, and `systemctl --user is-active omarchy-sleep-lock.service` prints `active`. For an idle or lock complaint on Omarchy 4, `omarchy-toggle-idle status` prints `{"enabled":false,...}` once stay-awake is off, `omarchy-shell idle status` reports `"enabled":true`, and `hyprctl clients -j | jq '.[] | select(.inhibitingIdle == true)'` returns nothing once the offending app is closed.

Sources: <https://man.archlinux.org/man/systemd-inhibit.1.en> · <https://man.archlinux.org/man/logind.conf.5.en> · <https://man.archlinux.org/man/systemctl.1.en> · <https://wiki.hypr.land/Hypr-Ecosystem/hypridle/> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-toggle-idle> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-system-sleep-monitor> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-system-sleep-lock> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/services/idle/Service.qml> · <https://github.com/omacom/omarchy/blob/quattro/default/systemd/user/omarchy-sleep-lock.service>

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

> **Audit corrected this record.** The kernel interfaces all check out and two factual claims about them do not, plus the record is silent on the Omarchy 4 trap that makes this recipe dangerous to run over ssh. Confirmed on this workstation (kernel 7.1.9-arch1-2, Intel, omarchy 4.0.2-1): `/sys/power/` holds `pm_debug_messages`, `pm_print_times`, `pm_async`, `pm_test`, `pm_wakeup_irq` and `suspend_stats/`, all root-writable only, and `cat /sys/power/pm_test` prints `[none] core processors platform devices freezer`. The pm_test modes, the freezer to devices to platform to processors to core order and the roughly 5 second return are verbatim from docs.kernel.org/power/basic-pm-debugging.html. The step 1 echo pair is the kernel's own recipe in docs.kernel.org/arch/x86/amd-debugging.html. `amd-s2idle test` really takes `--count`, `--duration` and `--format` with html, txt or md, and states the 6.1 kernel floor, per docs/amd-s2idle.md on superm1/amd-debug-tools master, and the package is `amd-debug-tools 0.2.21-1` in extra. Defect one: the `# kernel 6.9+` comment on `/sys/power/suspend_stats/*` is wrong. Documentation/ABI/testing/sysfs-power dates the directory and `fail`, `success`, `last_failed_dev` and `last_failed_step` to July 2019, and `suspend_stats_show` still exists under CONFIG_DEBUG_FS in kernel/power/main.c, so the debugfs copy is current rather than a legacy fallback. Defect two: the record presents `last_hw_sleep` as an AMD check, but `suspend_attr_is_visible()` in kernel/power/main.c hides `last_hw_sleep`, `total_hw_sleep` and `max_hw_sleep` unless `acpi_gbl_FADT.flags & ACPI_FADT_LOW_POWER_S0`, and its ABI date is June 2023. On this Intel desktop `/sys/power/mem_sleep` reads `s2idle [deep]` and the three files are absent, so a reader following the verify step gets No such file and no explanation. Defect three, and the reason this is not an `ok`: `sudo systemctl suspend` on Omarchy 4 fires the `omarchy-sleep-lock.service` delay inhibitor and locks the session through Quickshell, and that `ext-session-lock` surface has no `unlock()` IPC and outlives its client, so a suspend that hangs on a remote machine is unrecoverable without the physical console. The record also never says the shipped `InhibitDelayMaxSec=15` makes a broken lock look like a slow suspend. Added a step 0 for that, added `/sys/power/pm_wakeup_irq` which the AMD debugging page names first for a spurious wakeup, fixed the wakeup_sources sort, which the record ran as `sort -k3` on `event_count` with the header line dragged in. The header printed by `wakeup_sources_stats_seq_start()` in drivers/base/power/wakeup.c puts `wakeup_count`, the count of wakeups from system sleep, in field 4, so the fix now drops the header and sorts on `-k4`, and split the Limine step into an Omarchy drop-in (`/etc/limine-entry-tool.d/99-pm-debug.conf`, since `/etc/default/limine` is owned by no package here) and a plain Arch branch, noting that `omarchy-defaults.conf` sets `quiet splash loglevel=0`. Not exercised, deliberately: nothing was suspended, nothing under /sys/power/ was written, and `/sys/kernel/debug/` was not readable unprivileged, so the debugfs and wakeup_sources commands are from the sources rather than run. The Limine menu `e` editing claim for a UKI entry could not be checked because /boot is a vfat ESP mounted dmask=0077, so the fix now hedges it and recommends the drop-in. The record was not GNOME or KDE mis-specialised, and its `journalctl -b -k` is right because a resume is the same boot.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Leaving `/sys/power/pm_test` set to anything but `none` is the classic self-inflicted wound: every subsequent `systemctl suspend` will appear to work and immediately return without the machine ever sleeping, so a laptop in a bag stays fully awake. Always reset it. It does not survive reboot, so reboot if in doubt. `no_console_suspend` keeps the console powered across suspend and slightly increases sleep-state power draw, so remove it once you are done. Writing to `/sys/power/state` directly bypasses logind, so nothing locks your screen and no sleep hooks run, and on Omarchy 4 that means `omarchy-sleep-lock.service` never fires and the session is exposed. Conversely, testing suspend through logind on Omarchy 4 does lock the screen, and that lock has no `unlock()` IPC and outlives its client, so a failed suspend on a headless or remote machine can leave you with no way back in short of the physical console or a power cycle. Run `omarchy-toggle-idle stay-awake` before you start and remember to undo it.

**Fix.**

**0. On Omarchy 4, take the lock screen out of the loop first**

`systemctl suspend` goes through logind, which fires the `omarchy-sleep-lock.service` delay inhibitor and locks the session through Quickshell before sleeping. Omarchy 4's lock is an `ext-session-lock` surface with no `unlock()` IPC and it survives its own client dying, so a suspend test that hangs can leave a machine you can only recover by typing the password at the physical console or power cycling. Before testing suspend on a machine you reach over ssh:

```bash
omarchy-toggle-idle stay-awake     # no idle lock while you work
omarchy-hyprland-session-locked; echo $?   # 0 locked, 1 unlocked, 2 undetermined
```

Note also that `InhibitDelayMaxSec=15` on Omarchy (`/etc/systemd/logind.conf.d/20-inhibit-delay.conf`), so if locking is broken `systemctl suspend` sits for up to 15 seconds before it really suspends. That is the inhibitor window expiring, not a slow device.

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

`-b` is correct here: a resume is the same boot as the suspend. If the machine never resumed and you power cycled it, read the previous boot instead, and accept that anything the kernel printed after the journal stopped flushing is gone:

```bash
journalctl --list-boots
sudo journalctl -b -1 -k --no-pager | tail -200
```

`pm_print_times` gives a `calling <device>+ @ ...` / `call <device>+ returned N after M usecs` pair per device, so the last device before the hang is named explicitly.

**2. Read the failure counters, they name the guilty device directly**

```bash
grep -H '' /sys/power/suspend_stats/*
```

This directory has existed since 2019, not only on recent kernels. On kernel 7.1 it holds 13 files: `fail`, `success`, `failed_freeze`, `failed_prepare`, `failed_suspend`, `failed_suspend_late`, `failed_suspend_noirq`, `failed_resume`, `failed_resume_early`, `failed_resume_noirq`, `last_failed_dev`, `last_failed_errno`, `last_failed_step`. `last_failed_dev` is the device and `last_failed_step` the phase (`suspend`, `suspend_late`, `suspend_noirq`, `freeze`, `prepare`).

The same data is also exported through debugfs on current kernels, which is the only place it lives on anything older than 5.4:

```bash
sudo cat /sys/kernel/debug/suspend_stats
```

**3. Bisect with `pm_test`, which stages the suspend and returns without really sleeping**

```bash
for stage in freezer devices platform processors core; do
  echo "== $stage"
  echo $stage | sudo tee /sys/power/pm_test
  echo mem | sudo tee /sys/power/state      # returns after ~5s
  sudo dmesg | tail -30
done
echo none | sudo tee /sys/power/pm_test     # MUST reset
```

The first stage that misbehaves tells you the layer: `freezer` means a userspace process will not freeze, `devices` means a driver's suspend callback, `platform` and `core` mean ACPI or firmware. Reading the file shows the available modes with the current one bracketed:

```
$ cat /sys/power/pm_test
[none] core processors platform devices freezer
```

**4. If a driver hangs, serialise the suspend so the log ordering is trustworthy**

```bash
echo 0 | sudo tee /sys/power/pm_async
```

Per-device, once you know the suspect:

```bash
echo 0 | sudo tee /sys/devices/pci0000:00/0000:00:14.0/power/async
```

**5. Machine wakes straight back up? Find the wakeup source**

Start with the IRQ the kernel recorded, which is the cheapest answer:

```bash
cat /sys/power/pm_wakeup_irq
grep -w "$(cat /sys/power/pm_wakeup_irq)" /proc/interrupts
```

Then rank the wakeup sources:

```bash
# columns: name active_count event_count wakeup_count expire_count active_since
#          total_time max_time last_change prevent_suspend_time
# wakeup_count (field 4) is the one that counts wakeups from system sleep
sudo cat /sys/kernel/debug/wakeup_sources | tail -n +2 | sort -k4 -n -r | head -20
grep -H '' /sys/class/wakeup/*/device/power/wakeup_count
cat /proc/acpi/wakeup
# dmidecode's guess, unreliable on many boards
sudo dmidecode -t system | grep -P '\tWake-up Type: '
```

Snapshot `wakeup_count` before suspending and diff after resume. The counter that moved is the trigger.

**6. Keep the console alive so you can read a hang that never resumes**

Temporarily, edit the entry in the Limine menu (`e`) if your entry exposes an editable cmdline. Omarchy 4 boots a UKI by default (`ENABLE_UKI=yes` in `/etc/limine-entry-tool.d/omarchy-uki.conf`), which carries its cmdline inside the image, so prefer a drop-in you can delete afterwards.

Omarchy 4, `/etc/limine-entry-tool.d/99-pm-debug.conf`:

```sh
KERNEL_CMDLINE[default]+=" no_console_suspend ignore_loglevel"
```

Plain Arch with limine-mkinitcpio-hook and no drop-in directory, `/etc/default/limine`:

```sh
KERNEL_CMDLINE[default]+=" no_console_suspend ignore_loglevel"
```

```bash
sudo limine-update
```

On Omarchy this deliberately fights the defaults that `/etc/limine-entry-tool.d/omarchy-defaults.conf` sets (`quiet splash loglevel=0 systemd.show_status=false rd.udev.log_level=0`), which is the point: you want the messages back. Delete the drop-in and re-run `limine-update` when you are done.

**7. On AMD s2idle systems, use the purpose-built analyser**

```bash
sudo pacman -S amd-debug-tools      # Omarchy: omarchy pkg install amd-debug-tools
sudo amd-s2idle test --count 3 --duration 30 --format txt
```

It needs kernel 6.1 or later, drives the suspend cycles itself, and prints the blocking IP block, GPIO or missing hardware-sleep residency. Check residency by hand with:

```bash
cat /sys/power/suspend_stats/last_hw_sleep
```

A value of 0 means the platform never reached hardware sleep, so the battery drained because the machine only ever froze the CPUs.

`last_hw_sleep`, `total_hw_sleep` and `max_hw_sleep` are only created when the firmware advertises ACPI Low Power S0 Idle. On a machine without it, typically a desktop reporting `s2idle [deep]` in `/sys/power/mem_sleep`, the files are simply absent and `cat` returns "No such file or directory". That is expected, not a fault, and it means this whole step does not apply.

**Verify.** `grep -H '' /sys/power/suspend_stats/*` shows `fail` and `last_failed_dev` populated after a failed attempt, and `cat /sys/power/pm_test` prints the mode list with `[none]` bracketed when you are finished. `cat /sys/power/pm_async` reads `1` again once you have undone step 4. On an AMD or Intel machine that advertises ACPI Low Power S0 Idle, `cat /sys/power/suspend_stats/last_hw_sleep` is non-zero after a successful s2idle cycle; on a machine without it that file does not exist at all. On Omarchy 4, run `omarchy-toggle-idle allow-idle` afterwards to put idle locking back.

Sources: <https://docs.kernel.org/power/basic-pm-debugging.html> · <https://docs.kernel.org/arch/x86/amd-debugging.html> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Power_management/Wakeup_triggers> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/base/power/wakeup.c> · <https://archlinux.org/packages/extra/any/amd-debug-tools/> · <https://github.com/superm1/amd-debug-tools/blob/master/docs/amd-s2idle.md> · <https://wiki.archlinux.org/title/Limine> · <https://raw.githubusercontent.com/torvalds/linux/master/kernel/power/main.c> · <https://raw.githubusercontent.com/torvalds/linux/master/Documentation/ABI/testing/sysfs-power> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-session-locked> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-toggle-idle>

---

## Enable hibernation on a system whose only swap is zram

`hibernate-blocked-by-zram-only-swap` · severity: **medium** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `zram`

**Symptom.** Omarchy or CachyOS style setup with zram. `swapon --show` lists only `/dev/zram0`, and hibernation is unavailable: on Omarchy 4 the Hibernate entry is missing from the Omarchy menu (`Super + Esc`), because the menu hides any item whose `when:` guard fails and `system.hibernate` is guarded by `omarchy-hibernation-available`. Run directly, `systemctl hibernate` fails and logind reports that there is not enough swap space.

**Cause.** zram lives in RAM, so it cannot hold a hibernation image. logind deliberately ignores zram block devices when sizing the hibernation target, and hibernating into zram is unsupported even with a backing device.

> **Audit corrected this record.** Cause confirmed against the Arch wiki raw wikitext for Power management/Suspend and hibernate: hibernating to swap on zram is unsupported even with a backing device, and systemd always ignores zram block devices before triggering hibernation. The warning against an on-demand swap unit is on the same page, citing systemd issues 16708 and 30083, so it stays. The Btrfs branch of the fix matches `/usr/share/omarchy/bin/omarchy-hibernation-setup` on this machine step for step: `/swap` subvolume, `chattr +C`, `btrfs filesystem mkswapfile -s` at MemTotal, `defaults,pri=0` in fstab, `swapon -p 0`. The defect is the zram configuration step. Omarchy 4 ships `/usr/lib/systemd/zram-generator.conf.d/90-omarchy.conf` from omarchy-settings 4.0.2-1 with `zram-size = ram`, `compression-algorithm = zstd` and `swap-priority = 100`, and `zram-generator.conf(5)` states that the main configuration file has the lowest precedence and is overridden by any drop-in, so writing `/etc/systemd/zram-generator.conf` as the record instructs changes nothing on Omarchy 4, and its `zram-size = ram / 2` contradicts the `ram` Omarchy actually uses. Worse, `/usr/share/omarchy/migrations/1785013000.sh` deletes a stock-looking copy of that file on the next `omarchy update` and prints that local changes belong in `/etc/systemd/zram-generator.conf.d/99-local.conf`. I also corrected the symptom: the Hibernate entry is hidden, not greyed out, because `/usr/share/omarchy/shell/plugins/menu/Menu.qml` says guarded items are hidden when their `when:` evaluates false and `omarchy-menu.jsonc` guards `system.hibernate` with `omarchy-hibernation-available`, and the Omarchy 4 command is `omarchy hibernation setup`, confirmed with `omarchy hibernation --help` here and in `manual/36-system-sleep.md` on quattro. Confirmed on this workstation: `/proc/swaps` lists `/dev/zram0` at priority 100 and `/swap/swapfile` at priority 0, exactly the shape the verify step describes. NOT exercised: I ran no `systemctl hibernate`, touched no zram or swap unit, and this machine is a desktop, so the record's `laptop` tag was not tested. `applies_to` lists laptop but not desktop even though the problem applies equally on a desktop, and the verdict schema has no field to correct that.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The swapfile consumes disk space equal to total RAM. Editing /etc/fstab incorrectly can leave the boot hanging on a swap unit that never appears.

**Fix.**

Keep zram for everyday swapping and add a **disk-backed** swap space at a *lower* priority for hibernation only.

**On Omarchy 4**, run the supported command and change nothing else:

```bash
omarchy hibernation setup
```

It creates the Btrfs `/swap` subvolume with `chattr +C`, makes `/swap/swapfile` sized to `MemTotal` with `btrfs filesystem mkswapfile`, appends `/swap/swapfile none swap defaults,pri=0 0 0` to `/etc/fstab`, runs `swapon -p 0`, writes `HOOKS+=(resume)` into `/etc/mkinitcpio.conf.d/omarchy_resume.conf` and `resume=`/`resume_offset=` into `/etc/limine-entry-tool.d/resume.conf`, then rebuilds the UKI with `limine-mkinitcpio`. It requires the default Limine bootloader.

Do **not** write `/etc/systemd/zram-generator.conf` on Omarchy 4. The priority you want is already set, in a vendor drop-in owned by `omarchy-settings`:

```
# /usr/lib/systemd/zram-generator.conf.d/90-omarchy.conf
[zram0]
zram-size = ram
compression-algorithm = zstd
swap-priority = 100
```

`zram-generator.conf(5)` says the main configuration file "is read before any of the configuration directories, and has the lowest precedence", so anything in `/etc/systemd/zram-generator.conf` is overridden by that drop-in and does nothing. Omarchy's own migration `/usr/share/omarchy/migrations/1785013000.sh` deletes a stock-looking copy of that file on the next `omarchy update`. If you do need a local change, put it in a later-sorting drop-in:

```bash
sudo mkdir -p /etc/systemd/zram-generator.conf.d
sudo tee /etc/systemd/zram-generator.conf.d/99-local.conf <<'EOF'
[zram0]
zram-size = ram / 2
EOF
sudo systemctl daemon-reload
```

**On plain Arch**, or any distro that ships no such drop-in, build the swapfile yourself. On Btrfs:

```bash
sudo btrfs subvolume create /swap
sudo chattr +C /swap
sudo btrfs filesystem mkswapfile -s "$(awk '/MemTotal/ {print $2}' /proc/meminfo)k" /swap/swapfile
printf '\n/swap/swapfile none swap defaults,pri=0 0 0\n' | sudo tee -a /etc/fstab
sudo swapon -p 0 /swap/swapfile
```

and give zram the higher priority:

```
# /etc/systemd/zram-generator.conf
[zram0]
zram-size = ram / 2
swap-priority = 100
```

Then set `resume=` and `resume_offset=` for the swapfile and add the `resume` hook, as described in the other records. The two values come from:

```bash
findmnt -no SOURCE -T /swap/swapfile
sudo btrfs inspect-internal map-swapfile -r /swap/swapfile
```

Do **not** create an on-demand or one-shot swap unit that enables swap only at hibernate time. The Arch wiki states plainly that this is not officially supported, citing systemd issues 16708 and 30083.

**Verify.** `swapon --show` lists both zram (PRIO 100) and the swapfile (PRIO 0); `omarchy-hibernation-available; echo $?` returns 0 on Omarchy; `systemctl hibernate` completes.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-setup> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-hibernation-available> · <https://learn.omacom.io/2/the-omarchy-manual/103/system-sleep> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/bin/omarchy-hibernation-setup> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/bin/omarchy-hibernation-available> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/default/systemd/zram-generator.conf.d/90-omarchy.conf> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/manual/36-system-sleep.md>

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

## Fingerprint unlock fails after every suspend: fprintd reports 'Cannot run while suspended'

`lock-screen-fingerprint-fails-after-suspend-cannot-run-while-suspended` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `fprintd`, `framework`, `goodix`, `hyprland`, `intel`, `laptop`, `omarchy`, `omarchy-shell`, `quickshell`, `wayland`

**Symptom.** The fingerprint reader unlocks the Omarchy lock screen fine after boot. After the machine suspends and resumes, the lock screen's fingerprint prompt hangs or fails instantly, and only the password gets you in. In the journal:

```
fprintd[PID]: Device reported an error during verify: Cannot run while suspended.
```

Some readers log `transfer timed out` or `device was disconnected` instead, and on the way down `pam_fprintd` usually logs a failed release:

```
pam_fprintd(omarchy-lock-fingerprint:auth): ReleaseDevice failed: Release failed with error: The device is still busy with another operation, please try again later.
```

The lock screen then retries fingerprint PAM about four times a second, so the journal fills with lines like these until you type the password:

```
omarchy-shell[...]: Error while authenticating: "Authentication service cannot retrieve authentication info" (code 9)
```

`sudo` and polkit with a fingerprint usually keep working, because they activate fprintd outside any sleep transition. That is not guaranteed. One reporter on a Synaptics reader lost sudo and polkit too, with the lid open, because there the stale daemon keeps a second ghost device object and `pam_fprintd` always picks the first one.

Reported on Omarchy 4.0.0-1, 4.0.1-1, 4.0.2-1 and 4.0.3-1, on Goodix MOC readers (`27c6:609c`, `27c6:634c`, `27c6:659c`, `27c6:6594`) and on a Synaptics Prometheus `06cb:00fc`, across Intel Meteor Lake, Panther Lake, a 12th gen Intel, AMD Ryzen AI and AMD Ryzen 5 laptops, fprintd 1.94.5-2 with either libfprint 1.94.100-1 or libfprint-git, on both s2idle and deep sleep.

**Cause.** A fingerprint verify is open across the sleep transition, its `ReleaseDevice` fails on the still busy device, and the claim left behind survives resume. The same fprintd process then refuses every verify until it exits on its own idle timer, which can be hours later because that timer barely advances across s2idle. One reporter measured a poisoned instance lasting just over ten hours and 56 failed unlock attempts.

The common route to that on the lock path is Omarchy specific and is proven in source. `omarchy-system-sleep-monitor` runs itself under a delay inhibitor and locks the screen inside that window:

```bash
exec systemd-inhibit \
  --what=sleep --mode=delay --who=Omarchy \
  --why="Lock screen before suspend" \
  "$sleep_monitor" --inhibited
```

`shell/plugins/lock/Service.qml` then calls `startFingerprint()` as soon as the session goes secure, which opens a `pam_fprintd` session against `omarchy-lock-fingerprint` and D-Bus activates fprintd while logind's sleep operation is already in flight. logind refuses fprintd its own sleep delay inhibitor:

```
fprintd[...]: Failed to install a sleep delay inhibitor: GDBus.Error:org.freedesktop.login1.OperationInProgress: The operation inhibition has been requested for is already running
```

fprintd is then never told to release the reader before suspend and never sees the wake up signal after it, so it goes down holding an open USB handle. That is also why `sudo` normally works: it activates fprintd outside any sleep transition.

The refused inhibitor is the common trigger, not the whole cause, and two reports rule it out as the only one. On Omarchy 4.0.3-1 one reporter had fprintd activated 2 minutes 32 seconds before `Reached target Sleep`, no `OperationInProgress` line anywhere in the journal, and fprintd suspending its device on cue one second before the sleep target, so its inhibitor was granted and the daemon still wedged. A second reporter on a Synaptics reader found that when the reader drops off the bus on resume, fprintd registers a second device object by hotplug and keeps the wedged first one, and `pam_fprintd` uses the first, which is why sudo and polkit fail on that machine too. Upstream tracks the lock ordering half as issue 10252.

The roughly 4 Hz retry storm is a separate lock-screen defect, `fingerprintRetryTimer` in the same file has `interval: 250` with no backoff and no failure cap, tracked as issues 7172 and 7176. It does not cause this problem but it makes it far louder, 94 PAM sessions in 27 seconds in one report and 298 in a single locked session in another.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, systemd 261.2-1) and against every cited issue and pull request read in full today. Confirmed locally: the lock screen authenticates through omarchy-shell's Quickshell lock plugin using PAM, at `/usr/share/omarchy/shell/plugins/lock/` with `/etc/pam.d/omarchy-lock-password` present and `omarchy-lock-fingerprint` absent because this box has no reader, and `hyprlock` and `hypridle` are not installed, so the record is right to stay away from them. Confirmed locally in source: the `exec systemd-inhibit --what=sleep --mode=delay` block at the end of `/usr/share/omarchy/bin/omarchy-system-sleep-monitor`, `startFingerprint()` called from the secure-state change at `Service.qml:209-241`, `fingerprintRetryTimer` with `interval: 250` at `Service.qml:357-358`, and the `fprintd-list` plus `/etc/pam.d/omarchy-lock-fingerprint` probe at `Service.qml:380`. Also confirmed locally: `/usr/lib/systemd/system-sleep/` is the only directory systemd 261 scans, from `man 8 systemd-sleep` and from `strings /usr/lib/systemd/systemd-sleep`, the man page states that `user.slice` is frozen and that the action does not continue until every hook returns, and `/usr/lib/systemd/system-sleep/keyboard-backlight` sits there at mode 644 and is therefore inert. `fprintd` and `libfprint` are not installed here and this machine has no fingerprint reader, so the flow itself was not exercised and nothing about the daemon's behaviour was reproduced.

The problem is real and well evidenced, so this is not a reject: issue 7229 carries eight independent reproductions with journals, and the `omarchybot` comment confirms the Omarchy-side trigger against `quattro` at `f99d33a8`. Three fields were wrong. First, the cause states the refused sleep-delay inhibitor as the established mechanism, and two later reports in the same thread rule it out as the only one. A reporter on Omarchy 4.0.3-1 had fprintd activated 2 minutes 32 seconds before `Reached target Sleep`, zero `OperationInProgress` lines in the journal, and fprintd suspending its device on cue, so the inhibitor was granted and the daemon still wedged. A Synaptics Prometheus `06cb:00fc` reporter found a ghost second device object created by hotplug on resume, which also breaks sudo and polkit. The common factor both point to is the failed `ReleaseDevice` on an in-flight verify, so the cause is rewritten to lead with that and keep the inhibitor race as the common lock-path trigger, with upstream issue 10252 named for the ordering half.

Second, the fix is defective in two ways upstream itself documents. Its `pre` stop is contradicted by pull request 9868's own hook comment, which says a `pre` stop loses the race because fprintd is D-Bus activated and the lock and polkit plugins re-activate it before the machine goes down, and both upstream hooks act on `post` only. Its synchronous `systemctl stop` in `post` blocks the thaw for the stop timeout in exactly the wedged case the hook exists for, which is why pull request 7158 uses `systemctl --no-block try-restart` plus a `TimeoutStopSec=3s` drop-in and why a reporter measured about 10 seconds added to every resume. The rewritten fix uses the `post`-only SIGKILL form that reporter verified at 28ms, explains the executable-bit and ownership traps against Omarchy 4.0.3's own `migrations/1788662350.sh`, and warns that `fprintd-reset` and `fprintd-resume` are the filenames the open pull requests would install over a hand written hook. I did not test the rewritten hook, for want of a reader.

Third, the symptom's version and hardware list stopped at 4.0.2-1 and Goodix, which was true on 2026-09-07 but not now, and it asserted that sudo keeps working, which the Synaptics report contradicts. Both are corrected. The verify block also misattributed its evidence: the reporter who corrected the directory confirmed the negative, that the `/etc` hook never ran and the PID was unchanged, so verify is rewritten around the journal line the hook actually produces. The empty `danger` is filled, because a root hook in that directory blocks resume by design. Re-checked upstream today: issues 7229, 7172, 7176 and 10252 are open, pull requests 7158, 9868 and 9919 are all open with `mergedAt` null, and the `v4.0.2...v4.0.3` diff adds no fprintd sleep hook, so the record's "none has merged" still holds at v4.0.3. v4.0.3 did touch this area, which is why the symptom needed the version bump: it changed `bin/omarchy-setup-security-fingerprint` to install `libfprint-git` rather than stock `libfprint`, added a `capabilities: ["authentication"]` block to the lock plugin manifest, and hardened `bin/omarchy-apply-lock` and the two shipped sleep hooks. None of that fixes this bug, and the 4.0.3-1 reporter on `libfprint-git` still hit it.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Anything dropped in `/usr/lib/systemd/system-sleep/` runs as root on every suspend and resume, with `user.slice` frozen, and resume does not continue until it returns. A hook that blocks holds the wake, and a hook that hangs hangs it. Keep it root owned, mode 0755, `post` only and non-blocking, and test one `systemctl suspend` cycle from a terminal before trusting it on a closed lid.

**Fix.**

Discard fprintd on resume so the next authentication activates a fresh daemon against whatever the bus actually has. Do it in a `post` hook only, and do not let the hook block.

Three things decide whether the hook works at all, and the thread has a reporter who got each one wrong:

- `/usr/lib/systemd/system-sleep/` is the only directory systemd scans. A copy in `/etc/systemd/system-sleep/` never runs and nothing is logged. Confirmed on systemd 261.2-1:

```bash
man 8 systemd-sleep | grep -o '/[a-z/-]*system-sleep' | sort -u
strings /usr/lib/systemd/systemd-sleep | grep system-sleep
```

- The file must be executable or it is ignored silently. This is not hypothetical on Omarchy: on a 4.0.2-1 workstation `/usr/lib/systemd/system-sleep/keyboard-backlight` is mode 644 and therefore inert, and Omarchy 4.0.3 added migration `1788662350.sh` that reinstalls its own hooks there as root:root mode 0755.
- `user.slice` is frozen while hooks run and resume does not continue until every hook returns, both stated in `man 8 systemd-sleep`. A plain `systemctl stop` on an fprintd wedged on a stale handle waits out `TimeoutStopSec` before SIGKILL and holds the wake for that long. One reporter measured about 10 seconds added to every resume that way. Check your own bound with `systemctl show fprintd.service -p TimeoutStopUSec` rather than assuming it is short.

Do not add a `pre` stop. fprintd is D-Bus activated and the lock screen re-activates it inside the same delay window before the machine goes down, which is the reasoning upstream gives in pull request 9868 for its own hook being `post` only.

SIGKILL is safe here. Enrolments live on disk under `/var/lib/fprint`, which is `StateDirectory=fprint` in fprintd's own unit, not in the process.

```bash
sudo tee /usr/lib/systemd/system-sleep/fprintd-clear-stale-claim >/dev/null <<'EOF'
#!/bin/bash
# Drop fprintd on resume so the lock screen's next attempt claims a fresh
# daemon instead of the one that rode through suspend holding the reader.
[[ $1 == post ]] || exit 0
systemctl kill --signal=KILL fprintd.service 2>/dev/null || true
systemctl reset-failed fprintd.service 2>/dev/null || true
exit 0
EOF
sudo chmod 0755 /usr/lib/systemd/system-sleep/fprintd-clear-stale-claim
```

Ownership matters as much as the mode, because everything in that directory runs as root at every suspend. `sudo tee` plus `sudo chmod 0755` gives root:root 0755, which is what the 4.0.3 migration enforces for Omarchy's own hooks.

Do not name the file `fprintd-reset` or `fprintd-resume`. Those are the exact filenames the two open upstream pull requests would install, so a merge would overwrite a hand written hook with either name.

The upstream shape is the same idea without SIGKILL, and it needs a drop-in to stay fast:

```bash
# equivalent body for the hook above
systemctl --no-block try-restart fprintd.service 2>/dev/null || true
```

with `TimeoutStopSec=3s` in a `/etc/systemd/system/fprintd.service.d/` drop-in so a wedged daemon cannot stall the restart. Either form works. The kill form needs no drop-in.

To recover right now without installing a hook:

```bash
systemctl kill --signal=KILL fprintd.service && systemctl reset-failed fprintd.service
```

The same applies on plain Arch with any lock screen that starts fingerprint auth around suspend. The directory and the blocking behaviour are systemd behaviour, not Omarchy behaviour. The delay window that usually triggers it is Omarchy's.

Upstream has three open pull requests as of 2026-09-11 and none has merged. 7158 ships `default/systemd/system-sleep/fprintd-resume` plus a `TimeoutStopSec=3s` drop-in, 9868 ships `default/systemd/system-sleep/fprintd-reset`, and 9919 holds the lock screen's fingerprint calls until after resume. Omarchy 4.0.3 shipped none of the three, so the hook is still the fix.

**Verify.** ```bash
systemctl show fprintd.service -p MainPID            # note the PID, 0 if not running
systemctl suspend
# after resume, before typing the password:
systemctl show fprintd.service -p MainPID            # 0, or a new PID once the lock screen activates it
journalctl -b -u fprintd.service | grep 'on client request'
```

Check the last command first, because a hook in the wrong directory or without the executable bit fails silently. When the hook fires, systemd logs `fprintd.service: Sent signal SIGKILL to main process <pid> on client request`. One reporter running this form out of `/usr/lib/systemd/system-sleep/` recorded that line landing between `System returned from sleep operation 'suspend'` and `Successfully thawed unit 'user.slice'`, the hook taking 28ms, and the finger accepted three seconds later. Two other reporters proved the negative case: with the hook in `/etc/systemd/system-sleep/` it never executed and fprintd carried the same PID straight through the suspend.

Sources: <https://github.com/omacom/omarchy/issues/7229> · <https://github.com/omacom/omarchy/pull/7158> · <https://github.com/omacom/omarchy/pull/9868> · <https://github.com/omacom/omarchy/pull/9919> · <https://github.com/omacom/omarchy/issues/7172> · <https://github.com/omacom/omarchy/issues/7176> · <https://github.com/omacom/omarchy/issues/10252> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3> · <https://github.com/omacom/omarchy/compare/v4.0.2...v4.0.3> · <https://github.com/omacom/omarchy/blob/v4.0.3/migrations/1788662350.sh> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-apply-lock> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-setup-security-fingerprint> · <https://gitlab.freedesktop.org/libfprint/fprintd/-/blob/master/data/fprintd.service.in>

---

## Omarchy's resume hook lands last in `HOOKS`, and that is not the bug

`omarchy-resume-hook-appended-after-filesystems` · severity: **medium** · frequency: **common** · applies to: `btrfs`, `desktop`, `laptop`, `limine`, `mkinitcpio`, `omarchy`

**Symptom.** Hibernation was set up on Omarchy, it reported success, the machine powers off and then boots a fresh session instead of resuming. Looking for the reason, `grep -h '^HOOKS' /etc/mkinitcpio.conf.d/*.conf` shows `resume` at the very end of the array, after `filesystems` and `fsck`, which looks wrong against every ordering guide. Three upstream issues say it is wrong. It is not, and the fix circulating for it will damage the machine.

**Cause.** The array really does end that way, and the mechanism is exactly as reported. `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, owned by `omarchy-settings`, assigns the array with `HOOKS=(...)`, and `/etc/mkinitcpio.conf.d/omarchy_resume.conf`, written by `omarchy-hibernation-setup`, appends with `HOOKS+=(resume)`. `/usr/bin/mkinitcpio` collects the drop-ins with `sort -zVu` and concatenates them onto `/etc/mkinitcpio.conf` in that order, so the append always lands last and `resume` sits at position 15.

What does not follow is the failure. Hook position does not decide when root is mounted. `/usr/lib/initcpio/init` runs `run_hookfunctions 'run_hook' 'hook' $HOOKS` and only afterwards calls `fsck_root` and the mount handler, so every `run_hook` in the array, including the last one, runs before root is mounted. `filesystems` and `fsck` contribute nothing at that stage in any case: `/usr/lib/initcpio/install/filesystems` has only a `build()` function, and there is no `/usr/lib/initcpio/hooks/filesystems` and no `/usr/lib/initcpio/hooks/fsck` to run. `btrfs-overlayfs` is a `run_latehook` and runs after the mount whatever the array says.

The one ordering rule that does exist is that `resume` must follow `udev` and must follow `encrypt` or `lvm2`, and landing last satisfies it. The Arch wiki's own example array, cited by this record before it was re-audited, puts `resume` after `filesystems`.

> **Audit corrected this record.** Re-audited 2026-09-12 and returned as a reject, meaning the problem does not exist. The record was kept and rewritten by hand instead of retired, because its URL is published and its warning is worth keeping, but note that the slug still names the non-defect. The auditor's verdict follows verbatim, and it is the evidence for every claim above.

The mechanics this record describes are real, the defect it infers from them is not, and its fix would damage a working machine. Confirmed on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, mkinitcpio 41.1-1, limine-mkinitcpio-hook 1.37.1-1, kernel 7.1.9-arch1-2): `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, owned by `omarchy-settings`, assigns `HOOKS=(base udev plymouth keyboard autodetect microcode modconf kms keymap consolefont block encrypt filesystems fsck btrfs-overlayfs)`, and `/etc/mkinitcpio.conf.d/omarchy_resume.conf`, written by `omarchy-hibernation-setup` and owned by no package, contains `HOOKS+=(resume)`. `/usr/bin/mkinitcpio` line 1121 collects the drop-ins with `LC_ALL=C.UTF-8 find ... | LC_ALL=C.UTF-8 sort -zVu` and `cat`s them onto `/etc/mkinitcpio.conf` in that order, so the append does land last and `resume` is position 15. That much is right. The consequence is wrong. `/usr/lib/initcpio/install/filesystems` has only a `build()` function that adds filesystem modules and `mount.FSTYPE` helpers, and there is no `/usr/lib/initcpio/hooks/filesystems` and no `/usr/lib/initcpio/hooks/fsck`, so neither contributes anything at runtime. `/usr/lib/initcpio/init` calls `run_hookfunctions 'run_hook' 'hook' $HOOKS` and only afterwards `fsck_root` and `"$mount_handler" /new_root`. Root is mounted after every `run_hook`, regardless of array position, so `resume` at the end still runs before root is mounted. `btrfs-overlayfs` is a `run_latehook` and runs after the mount in any case. The only ordering requirement, that `resume` follow `udev` and follow `encrypt`, is satisfied precisely because the append lands last. Live evidence on this machine: `/sys/power/resume` reads `253:0` and `/dev/mapper/root` is major 253 minor 0, so the resume hook ran from last position, resolved the encrypted device and wrote it. The kernel could not have done that itself from `resume=/dev/mapper/root`, since that device does not exist at cmdline parse time. The record's own Arch wiki source contradicts it as well: its example is `HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems resume fsck)`, with `resume` after `filesystems`, and it asks only that `resume` follow `udev` and follow `encrypt` or `lvm2`. It never says `resume` must precede `filesystems`. The cited issue does not support the record either. `omacom/omarchy` 8471 is open with zero comments and its author states he has not been able to demonstrate a resume failure attributable to the ordering, and that hibernation is separately unavailable on his machine. Issues 8888 (an open, unmerged, AI-worded pull request) and 10375 repeat the same wrong mechanism and are also unconfirmed. The fix is actively harmful. `sudo rm /etc/mkinitcpio.conf.d/omarchy_resume.conf` breaks `omarchy-hibernation-available` and `omarchy-hibernation-remove`, which both test that exact path for `^HOOKS+=(resume)$`, so the menu reports hibernation unavailable and the user can never remove it cleanly. Re-running `omarchy-hibernation-setup` then recreates the file and the array carries `resume` twice. Worse, `grep -h '^HOOKS'` prints the literal line from `omarchy_hooks.conf`, which always contains `kms`, while that file strips `kms` at build time on machines where NVIDIA drives every display. Copying the grep output into a `zz_resume.conf` assignment reinstates `kms` and drags nouveau and roughly 100 MB of GSP firmware back into the initramfs. The sample array in the fix also omits `plymouth`, which Omarchy 4 ships and needs for the themed LUKS prompt. The symptom a user arrives with, hibernate powering off and boot coming up clean, is real and belongs under `hibernate-resume-hook-missing-or-misordered`, which I corrected in the same batch. This record should be retired rather than merged, because its slug and its whole content name a non-defect. That is the operator's call. NOT exercised: I did not run a hibernate and power-on cycle, did not rebuild an initramfs, and could not read `/boot`, which needs root.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** **Do not apply the fix that circulates for this.** Deleting `/etc/mkinitcpio.conf.d/omarchy_resume.conf` and hand-writing a full `HOOKS=` array breaks a working machine in three ways. `omarchy-hibernation-available` and `omarchy-hibernation-remove` both test that exact path for `^HOOKS+=(resume)$`, so the menu reports hibernation unavailable and it can never be removed cleanly, and re-running `omarchy-hibernation-setup` recreates the file so the array then carries `resume` twice. Copying the output of `grep -h '^HOOKS'` into that array reinstates `kms`, because the printed line always contains it while `omarchy_hooks.conf` strips it at build time on machines where NVIDIA drives every display, which drags nouveau and roughly 100 MB of GSP firmware back into the initramfs. And the array published in those issues omits `plymouth`, which Omarchy 4 ships and needs for the themed LUKS prompt.

**Fix.**

Change nothing about the hook order. Confirm it is working, then go and find the real fault.

Confirm the resume hook ran and resolved the device:

```bash
cat /sys/power/resume
lsblk -o NAME,MAJ:MIN,MOUNTPOINTS
```

`/sys/power/resume` holds a `major:minor` pair. If it matches the device holding the swap, the hook did its job from last position. On an encrypted root it reads something like `253:0` against `/dev/mapper/root`, and the kernel could not have written that from `resume=/dev/mapper/root` on its own, because that device does not exist when the cmdline is parsed. A reading of `0:0` means the hook did not resolve anything, which is a real fault and a different record.

Check that the pieces are present at all:

```bash
cat /etc/mkinitcpio.conf.d/omarchy_resume.conf
cat /etc/limine-entry-tool.d/resume.conf
tr ' ' '\n' < /proc/cmdline | grep -E 'resume|hibernate'
omarchy-hibernation-available; echo "exit $?"
```

If hibernation powers off and comes back to a fresh session, the causes worth checking are in `hibernate-resume-hook-missing-or-misordered` (the hook or the `resume=` parameter genuinely absent), `hibernate-not-enough-free-swap` (the image does not fit), `hibernate-blocked-by-zram-only-swap` (the only swap is zram) and `hibernate-does-not-power-off-hibernatemode-shutdown` (the image never gets written). None of them are about hook order.

Rebuild only if you changed something, and use the Omarchy command rather than `mkinitcpio -P`, which finds no preset here and reports success having written nothing:

```bash
sudo limine-mkinitcpio
```

**Verify.** `cat /sys/power/resume` prints the `major:minor` of the device holding swap rather than `0:0`, and `omarchy-hibernation-available` exits 0. A hibernate and power-on cycle restores the running session, which is the only end-to-end proof.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://github.com/omacom/omarchy/issues/8471> · <https://github.com/omacom/omarchy/issues/10375> · <https://github.com/omacom/omarchy/issues/8888> · <https://raw.githubusercontent.com/omacom/omarchy/quattro/bin/omarchy-hibernation-setup>

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

## Resolve TLP and power-profiles-daemon fighting over the same knobs

`tlp-power-profiles-daemon-conflict` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `power-profiles-daemon`, `tlp`

**Symptom.** I installed TLP for better battery life and now settings randomly revert, or the desktop's power-profile switcher does nothing. `tlp-stat` prints:
`Warning: PLATFORM_PROFILE_ON_AC/BAT is not set because power-profiles-daemon is running.`
(TLP 1.5 said: `Error: conflicting power-profiles-daemon.service is enabled, power saving will not apply on boot.`)

**Cause.** TLP and power-profiles-daemon change some of the same kernel tunables, including the platform profile, the CPU energy performance preference, PCIe ASPM and USB autosuspend, and they overwrite each other's tuning. `power-profiles-daemon.service` declares a `Conflicts=` line that names TLP, read on this machine on 2026-09-12:

```
$ systemctl show power-profiles-daemon.service -p Conflicts
Conflicts=tuned.service shutdown.target system76-power.service tlp.service auto-cpufreq.service
```

A systemd `Conflicts=` only stops both units running at once. It does not stop both packages being installed. On Arch the `tlp` package conflicts with `tuned` and not with `power-profiles-daemon`, so the two install side by side and resolving the conflict is left to you.

This is never Omarchy 4's default state. Omarchy installs `power-profiles-daemon` from `/usr/share/omarchy/install/omarchy-base.packages` and enables it in `/usr/share/omarchy/install/config/enable-services.sh`, and TLP appears nowhere in `/usr/share/omarchy` or in the upstream `omacom/omarchy` `quattro` tree. TLP on an Omarchy box is something you added.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation on 2026-09-12 and against TLP's ppd FAQ, the Arch TLP and CPU frequency scaling wiki pages, the Arch package data for tlp and tlp-pd, and omacom/omarchy issue 8596. What held: the two warning strings in the symptom are verbatim from the TLP FAQ for 1.6-and-later and 1.5, the shared tunables and the overwriting are stated there, and `systemctl show power-profiles-daemon.service -p Conflicts` on this machine returns `tuned.service shutdown.target system76-power.service tlp.service auto-cpufreq.service`, confirming the Conflicts claim locally. What was wrong is the Omarchy framing and the tlp-pd advice. Omarchy 4 installs power-profiles-daemon 0.30-1 from install/omarchy-base.packages and enables it in install/config/enable-services.sh, and it never installs TLP: the only `tlp` match in /usr/share/omarchy and in the whole quattro tree is the substring inside `hyprctlProc` in shell/Commons/Style.qml, so the record was reading as an Omarchy default when it is a user-added package. The real defect is the fix's `pacman -S tlp-pd` line: tlp-pd 1.10.2 declares conflicts=power-profiles-daemon and provides=power-profiles-daemon and ships only /usr/bin/tlp-pd, /usr/bin/tlpctl and the two D-Bus service files, so installing it removes /usr/bin/powerprofilesctl, which pacman -Qo confirms is owned by power-profiles-daemon 0.30-1, while omarchy-powerprofiles-list, omarchy-powerprofiles-set and shell/plugins/menu/Menu.qml line 277 all invoke `powerprofilesctl` by name. On Omarchy the record's recommended TLP branch therefore breaks the exact UI it claims to preserve. The danger was also overstated: issue 8596 is still open and a contributor comment on it reproduces the crash with power-profiles-daemon active, enabled and healthy and no TLP, and the unconditional two-second `powerprofilesctl get` poll that comment blames is no longer in shell/plugins/services/battery/Service.qml on 4.0.2-1. I also confirmed the ALPM guard does not block these commands: /usr/bin/omarchy-update-pacman-guard aborts only when both a sync and a sysupgrade flag are on the pacman command line. Frequency lowered from very-common to common because on this corpus's primary target the problem cannot occur until the user installs TLP by hand. NOT exercised: I did not mask power-profiles-daemon, install tlp or tlp-pd, or start or stop any unit on this workstation, so the resulting menu breakage is reasoned from the package file lists and the Omarchy scripts rather than observed.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Masking `power-profiles-daemon` leaves GNOME, KDE and Omarchy's power menu with no profile source. On Omarchy 4, installing `tlp-pd` does not repair that, it breaks the menu a second way by removing `/usr/bin/powerprofilesctl`. Omarchy issue 8596 reports `powerprofilesctl` aborting rather than failing cleanly when the daemon is masked, but that issue is open and a contributor comment on it reproduces the same interpreter teardown crash with `power-profiles-daemon` active, enabled and unmasked and no TLP installed, so masking widens the window rather than being the cause.

**Fix.**

Pick one. On Omarchy 4 the answer is almost always power-profiles-daemon.

**Keeping power-profiles-daemon (what Omarchy 4 ships, and what its power menu drives):**

```bash
sudo systemctl disable --now tlp.service
sudo systemctl unmask power-profiles-daemon.service
sudo systemctl enable --now power-profiles-daemon.service
```

Removing the package is cleaner than leaving a disabled unit behind, and it is what TLP's own FAQ prefers:

```bash
sudo pacman -Rns tlp tlp-rdw
```

**Keeping TLP (plain Arch, and on Omarchy it costs you the power menu):**

```bash
sudo systemctl stop power-profiles-daemon.service
sudo systemctl mask power-profiles-daemon.service
sudo systemctl enable --now tlp.service
sudo systemctl mask systemd-rfkill.service systemd-rfkill.socket
```

Masking `systemd-rfkill` is the Arch wiki's instruction on the TLP page, because it implements the same radio state save and restore that TLP does.

To keep a power-profile switcher in GNOME, KDE or Cinnamon, install TLP's D-Bus compatibility layer, which has existed since TLP 1.9:

```bash
sudo pacman -S tlp-pd
```

**Do not do that on Omarchy 4.** `tlp-pd` 1.10.2 carries `conflicts=power-profiles-daemon` and `provides=power-profiles-daemon`, so pacman removes `power-profiles-daemon` in order to install it, and `/usr/bin/powerprofilesctl` goes with it. `tlp-pd` ships only `/usr/bin/tlp-pd`, `/usr/bin/tlpctl` and two D-Bus service files. Omarchy's power UI does not speak that D-Bus API directly, it shells out to `powerprofilesctl` by name:

```
/usr/share/omarchy/bin/omarchy-powerprofiles-list    powerprofilesctl list
/usr/share/omarchy/bin/omarchy-powerprofiles-set     powerprofilesctl set "$profile"
/usr/share/omarchy/shell/plugins/menu/Menu.qml:277   powerprofilesctl get
```

Omarchy's menu and power panel then show an empty profile list. Install `tlp-pd` only if you accept losing that menu.

Do not run `tuned` or `tuned-ppd` alongside either one. Both are named in the same `Conflicts=` line.

Omarchy's ALPM guard does not block any pacman command above. `/usr/bin/omarchy-update-pacman-guard` aborts only when the pacman command line carries both a sync flag and a sysupgrade flag, so `pacman -S` and `pacman -Rns` pass through it. Never turn one of them into `pacman -Sy <pkg>`, which is a partial upgrade.

**Verify.** `systemctl is-active tlp power-profiles-daemon` shows exactly one of the two active. With TLP running, `sudo tlp-stat -s` prints no conflict warning. With power-profiles-daemon running, `powerprofilesctl` lists the profiles and exits 0. On Omarchy 4, also check the command the menu actually calls:

```bash
omarchy-powerprofiles-list
```

Empty output means the power menu is broken even when the D-Bus API answers.

Sources: <https://linrunner.de/tlp/faq/ppd.html> · <https://wiki.archlinux.org/title/TLP> · <https://wiki.archlinux.org/title/CPU_frequency_scaling> · <https://archlinux.org/packages/extra/any/tlp-pd/> · <https://archlinux.org/packages/extra/any/tlp/> · <https://github.com/omacom/omarchy/issues/8596>

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

## Restart fan control after a suspend/resume cycle

`fancontrol-stops-after-suspend` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** My custom fan curve works fine until I suspend the machine. After resume the fans are stuck — either full blast or off entirely — until I restart the service by hand.

**Cause.** An open lm-sensors bug, `lm-sensors/lm-sensors#172`. On resume the hwmon `pwm*_enable` attributes are reset out of manual mode, so the hardware or the driver takes the fans back and `fancontrol` neither notices nor reasserts them. The fans then stay wherever the reset left them, usually full speed or off, until `fancontrol.service` is restarted. The bug is in `fancontrol` itself and not in Omarchy, so it behaves the same on any Arch system.

> **Audit corrected this record.** The core claim holds. I read lm-sensors issue 172 with `gh issue view 172 -R lm-sensors/lm-sensors` and it is still OPEN, titled "Fancontrol doesn't work after waking from sleep", and the reporter names the real mechanism: on resume `/sys/class/hwmon/hwmonN/pwm*_enable` is no longer 1, so the fans sit where the reset left them until the service restarts. The Arch wiki Fan_speed_control page has a matching section, "Fancontrol stops working after suspend-wake cycles", which cites that same issue and points at a systemd sleep hook, so both cited sources do say what the record claims. The hook contract was confirmed on this machine against `man 8 systemd-suspend.service` from systemd 261.2-1: the executables live in `/usr/lib/systemd/system-sleep/`, the first argument is `pre` or `post` and the second is the sleep action, so the record's `case $1 in post)` script is correct, and `strings /usr/lib/systemd/systemd-sleep` contains only `/usr/lib/systemd/system-sleep`, confirming there is no `/etc` equivalent to prefer. Two things were wrong. First, the danger claim that scripts in that directory "may be removed by systemd package upgrades" is false on Arch: pacman does not delete files it does not own, and this workstation has an unowned `/usr/lib/systemd/system-sleep/keyboard-backlight` sitting alongside `nvidia` (nvidia-utils) and `unmount-fuse` (omarchy-settings 4.0.2-1) that has survived updates, so I replaced that line with the real hazard, which is that `pwmconfig` stops fans one at a time while it measures them. Second, the record offers only the sleep hook, while the Arch wiki Power_management/Suspend_and_hibernate page carries a note that systemd considers the hook a hack and runs the hooks concurrently with no ordering, and directs the reader to a custom systemd unit instead, which is the form the wiki's own amdgpu-fancontrol example uses with `After=suspend.target` and `WantedBy=suspend.target`. I put the unit first and kept the hook as a labelled second method, with the point that a file there must be chmod +x or it is ignored silently. I also added where `fancontrol` comes from, because `pacman -Q fancontrol` fails on Omarchy 4: it is shipped by `lm_sensors` 1:3.6.2-1 at `/usr/bin/fancontrol` with `/usr/lib/systemd/system/fancontrol.service`, and `lm_sensors` is already installed here as a `mesa` dependency, so a reader on Omarchy has the tool but has `fancontrol.service` disabled and no `/etc/fancontrol`, which is what the unit's `ConditionFileNotEmpty=/etc/fancontrol` checks. Nothing here is Omarchy-specific and nothing in the Omarchy 4 layout interferes. NOT exercised: I did not suspend this workstation, did not install the hook or the unit, and did not create `/etc/fancontrol`, so the restart-on-resume behaviour is confirmed from the upstream issue and the systemd man page rather than observed.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A misconfigured `/etc/fancontrol` can stop the fans entirely and let the CPU or GPU overheat. `pwmconfig` itself stops each fan in turn to measure it, so do not run it on a machine that is already hot or under load, and watch `sensors` for a few minutes after any change.

**Fix.**

`fancontrol` has no package of its own. It ships in `lm_sensors`, which is already installed on Omarchy 4 as a `mesa` dependency, and `fancontrol.service` only starts once `/etc/fancontrol` exists. Check that first:

```bash
pacman -Q lm_sensors
systemctl is-enabled fancontrol.service
ls -l /etc/fancontrol
```

Then restart the service on resume. Either method works. The systemd unit is the better one, because `systemd-sleep` runs the sleep hooks in parallel with no ordering and `systemd-suspend.service(8)` calls them a hack.

**Method 1, a systemd unit (preferred):**

```bash
sudo tee /etc/systemd/system/fancontrol-resume.service <<'EOF'
[Unit]
Description=Restart fan control after resume
After=suspend.target hibernate.target hybrid-sleep.target

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart fancontrol.service

[Install]
WantedBy=suspend.target hibernate.target hybrid-sleep.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable fancontrol-resume.service
```

**Method 2, a sleep hook.** `systemd-sleep` runs every executable in `/usr/lib/systemd/system-sleep/` with `pre` or `post` as the first argument and `suspend`, `hibernate`, `hybrid-sleep` or `suspend-then-hibernate` as the second:

```bash
sudo tee /usr/lib/systemd/system-sleep/fancontrol.sh <<'EOF'
#!/bin/sh
case $1 in
  post) /usr/bin/systemctl restart fancontrol.service ;;
esac
EOF
sudo chmod +x /usr/lib/systemd/system-sleep/fancontrol.sh
```

The `chmod +x` is not optional. A file in that directory that is not executable is ignored with no error.

If `fancontrol.service` fails after a kernel update rather than after a suspend, it is a moved hwmon path and not this bug. Check which:

```bash
systemctl status fancontrol.service
journalctl -b -u fancontrol.service
sensors
grep -E 'DEVPATH|DEVNAME|FCTEMPS|FCFANS' /etc/fancontrol
```

`fancontrol` refuses to start with `Configuration appears to be outdated, please run pwmconfig again` when the recorded `DEVPATH` no longer matches the `hwmonN` numbers, which can reorder across reboots. Correct the numbers in `/etc/fancontrol`, or regenerate the file:

```bash
sudo sensors-detect
sudo pwmconfig
```

To stop the numbers reordering in the first place, pin the module load order: take the modules listed in `/etc/conf.d/lm_sensors` and put them one per line in `/etc/modules-load.d/modules.conf`.

**Verify.** Suspend and resume, then confirm the fan RPM tracks temperature again with `watch -n2 sensors` and that `systemctl is-active fancontrol` reports `active`. To see which restart path fired, `systemctl status fancontrol-resume.service` for the unit and `journalctl -b -u systemd-suspend.service` for the sleep hook, which logs the hook's output.

Sources: <https://wiki.archlinux.org/title/Fan_speed_control> · <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://github.com/lm-sensors/lm-sensors/issues/172>

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

## Fix Wi-Fi or Bluetooth staying off at boot or after resume with TLP installed

`wifi-bluetooth-off-after-boot-with-tlp` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `iwd`, `laptop`, `manjaro`, `networkmanager`, `omarchy`, `tlp`

**Symptom.** After installing TLP, Wi-Fi is off every time I boot and I have to toggle it on by hand, or Bluetooth never comes back after resume. `rfkill list` shows the device soft-blocked.

**Cause.** Two things save and restore radio state, and only one of them can win. `systemd-rfkill` saves each rfkill switch at shutdown and restores it at boot, keeping the state under `/var/lib/systemd/rfkill`. On this machine that directory holds `pci-0000:00:14.3:wlan` and `pci-0000:00:14.0-usb-0:14:1.0:bluetooth`. TLP does the same job through its radio device switching settings. TLP's own documentation records that Debian and Ubuntu mask `systemd-rfkill.service` because it implements identical functionality, and the Arch wiki tells every TLP user to mask both the service and the socket to avoid conflicts and to let TLP's radio switching work properly. Whichever one ran last decides the state you get, which is why the radio seems to come back at random.

Separately, TLP does not bring a radio up that Linux left down. `DEVICES_TO_ENABLE_ON_STARTUP` is unset by default, and `RESTORE_DEVICE_STATE_ON_STARTUP`, which used to cover this, is deprecated as of TLP 1.10. Arch ships tlp 1.10.2.

None of this is Omarchy's doing. Omarchy 4 does not install TLP and does not reference it anywhere in `/usr/share/omarchy` or in the upstream `quattro` tree, so TLP on an Omarchy machine is something you added.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation on 2026-09-12 and against the Arch TLP and Power management wiki pages and TLP's own radio and introduction settings pages. What held: the masking advice is the Arch TLP page's own instruction, `DEVICES_TO_ENABLE_ON_STARTUP` is real and takes `wifi` and `bluetooth`, `/etc/tlp.d/*.conf` is a supported drop-in directory, and the NetworkManager and iwd snippets are copied correctly from the Power management page. `rfkill`, `iw` and `/var/lib/systemd/rfkill` all exist here, rfkill coming from util-linux 2.42.2-1, and the state directory holds one file per radio. What was wrong. First, the Omarchy framing: TLP is not installed and is referenced nowhere in /usr/share/omarchy or in the upstream quattro tree, so the record read as an Omarchy default when TLP is user-added. Second, the NetworkManager advice is redundant on Omarchy 4, which already ships /etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf owned by omarchy-settings 4.0.2-1 setting `wifi.powersave = 2`. Per `man 5 NetworkManager.conf` on this machine, conf.d files are read in order with later files overriding earlier ones, so the record's `powersave.conf` does win over `omarchy-wifi-powersave.conf` on name order, but only by luck, and a numeric-prefixed name such as 00-powersave.conf would silently lose. Third, the verify step names `wlan0`, which does not exist under predictable naming: this machine's interface is `wlo1`, and `iw dev wlo1 get power_save` reports `Power save: on` despite Omarchy's file, because the interface is down and unassociated and NetworkManager applies wifi.powersave per connection at activation. Fourth, the cause called it a race between TLP and systemd-rfkill, where TLP's own documentation says the two implement identical functionality and names RESTORE_DEVICE_STATE_ON_STARTUP as deprecated since TLP 1.10, with Arch on 1.10.2. Fifth, the danger said hardware kill-switch state, where systemd-rfkill saves the soft block. The record also used `systemctl restart tlp.service` where TLP documents `sudo tlp start`. Frequency lowered from common to occasional because on this corpus's primary target the problem cannot occur until the user installs TLP by hand. NOT exercised: I installed nothing, masked nothing and restarted no unit on this workstation, and I have no Wi-Fi association here to test the power_save value on a live link.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Masking `systemd-rfkill` means the soft block state of each radio is no longer saved across reboots, so a radio you switched off comes back or stays off according to TLP alone. A hardware kill switch is physical and is unaffected either way. Disabling Wi-Fi power saving costs battery life on a laptop.

**Fix.**

Mask systemd's rfkill state handling so TLP is the only thing touching the radios:

```bash
sudo systemctl mask systemd-rfkill.service systemd-rfkill.socket
```

Then tell TLP to bring the radios up at boot:

```
# /etc/tlp.d/00-enable-wifi-at-startup.conf
DEVICES_TO_ENABLE_ON_STARTUP="wifi bluetooth"
```

```bash
sudo tlp start
```

`sudo tlp start` is TLP's documented way to apply a config change, alongside a reboot or an AC transition. Mind the read order: `/etc/tlp.d/*.conf` is read in alphabetical order and `/etc/tlp.conf` is read last, so an uncommented `DEVICES_TO_ENABLE_ON_STARTUP` in `/etc/tlp.conf` beats the drop-in. Every parameter in a stock `/etc/tlp.conf` is commented out, so the drop-in applies unless you have edited that file.

If latency or dropouts on Wi-Fi are the actual problem, that is Wi-Fi power saving rather than rfkill, and it is a separate setting.

**On Omarchy 4 it is already disabled and you do not need to add anything.** `omarchy-settings` 4.0.2-1 owns this file:

```
# /etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf
[connection]
wifi.powersave = 2
```

**On plain Arch**, create it yourself:

```
# /etc/NetworkManager/conf.d/powersave.conf
[connection]
wifi.powersave=2
```

```bash
sudo systemctl restart NetworkManager
```

`2` means power saving globally disabled. If you do write your own drop-in on Omarchy, mind the file name. NetworkManager reads `/etc/NetworkManager/conf.d/*.conf` in order and a later file overrides an earlier one, so a name that sorts after `omarchy-wifi-powersave.conf` wins, and a name that sorts before it, such as `00-powersave.conf`, loses to Omarchy's file.

With iwd instead of wpa_supplicant, which is plain Arch only because Omarchy 4 installs neither `iwd` nor any `wifi.backend` setting and NetworkManager therefore defaults to wpa_supplicant:

```
# /etc/iwd/main.conf
[DriverQuirks]
PowerSaveDisable=*
```

**Verify.** `rfkill list` shows no soft block after a reboot. For the power saving check, use the real interface name: Arch and Omarchy use predictable interface names and `wlan0` is usually not one of them. On this workstation it is `wlo1`.

```bash
iw dev
iw dev wlo1 get power_save
```

Run that while the interface is associated. NetworkManager applies `wifi.powersave` per connection at activation time, so an interface that is down reports the driver default instead. On this machine `wlo1` is down and `iw dev wlo1 get power_save` prints `Power save: on` even though `omarchy-wifi-powersave.conf` sets `wifi.powersave = 2`.

Sources: <https://wiki.archlinux.org/title/TLP> · <https://wiki.archlinux.org/title/Power_management> · <https://linrunner.de/tlp/settings/radio.html> · <https://linrunner.de/tlp/settings/introduction.html>

---

## Fix 'only powersave and performance available' and governors that reset at boot

`cpu-governor-not-persistent-pstate-active` · severity: **low** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `limine`, `manjaro`, `omarchy`

**Symptom.** `cpupower frequency-set -g ondemand` fails, and `cpupower frequency-info` lists only `powersave` and `performance`. Whatever I set reverts to `powersave` after a reboot, and I assume my CPU is being throttled.

**Cause.** `intel_pstate` and `amd_pstate` in *active* mode bypass the classic cpufreq governors and expose two pseudo-governors that happen to share their names. These are not the old governors. Both scale dynamically and map onto an Energy Performance Preference (EPP) hint, so nothing is being throttled and `ondemand` is not missing, it does not exist in this mode. Sysfs writes to `scaling_governor` and `energy_performance_preference` are also not persistent across boots on their own. On Omarchy 4 there is a second and larger reason a hand-set value does not stick: `power-profiles-daemon` is in the base package set, is enabled at install, and is driven from the Super+Space menu and from `omarchy-powerprofiles-init` at session start. Its `intel_pstate` and `amd_pstate` drivers write both `scaling_governor` and `energy_performance_preference` for every policy on every profile change, so they overwrite anything set by hand or from `tmpfiles.d`.

> **Audit corrected this record.** The diagnosis is right and the mechanics around it are wrong in four places. This workstation reproduces the headline symptom exactly and is real evidence, because it is a desktop with an Intel i9-9900K: `/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver` reads `intel_pstate`, `scaling_available_governors` reads `performance powersave`, `scaling_governor` reads `powersave`, `energy_performance_preference` reads `performance`, `energy_performance_available_preferences` reads `default performance balance_performance balance_power power`, and `/sys/devices/system/cpu/intel_pstate/status` reads `active`. I fetched https://www.kernel.org/doc/html/latest/admin-guide/pm/intel_pstate.html and https://www.kernel.org/doc/html/latest/admin-guide/pm/amd-pstate.html rather than recalling them, and the record's explanation of active versus passive mode matches the kernel's own wording closely, including that the two pseudo-governors share names with the generic ones but do not behave like them and that nothing is throttled. The first defect is the one that decides whether the fix survives a reboot at all, and the record does not mention it. `power-profiles-daemon` 0.30-1 is installed, enabled and active here, and Omarchy ships it deliberately: it is listed at `/usr/share/omarchy/install/omarchy-base.packages:104`, enabled at `/usr/share/omarchy/install/config/enable-services.sh:13`, exposed in the Super+Space menu through `omarchy-powerprofiles-list` and `omarchy-powerprofiles-set`, and restored at session start by `hl.exec_cmd("omarchy-powerprofiles-init")` in `/usr/share/omarchy/default/hypr/autostart.lua:8`. I read the daemon's own source at https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/raw/main/src/ppd-driver-intel-pstate.c and https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/raw/main/src/ppd-driver-amd-pstate.c: both write `scaling_governor` and then `energy_performance_preference` for every policy on every profile change, with the intel file carrying the comment "Force a scaling_governor where the preference can be written" and mapping the profiles to `power`, `balance_power` or `balance_performance`, and `performance`. That matches what this machine shows, profile `performance` with EPP `performance`. So the record's `tmpfiles.d` persistence is applied at boot and then overwritten, and the supported Omarchy route is to set the profile. The second defect is internal: the record tells the reader to test `balance_performance` and then writes `balance_power` into the tmpfiles file. The third is the Limine edit. The drop-in path and the `KERNEL_CMDLINE[default]+=` syntax are correct and match `/etc/limine-entry-tool.d/omarchy-defaults.conf` on this machine, and `sudo limine-mkinitcpio` is the right rebuild command, but the extra `sudo tee -a /etc/default/limine < /etc/limine-entry-tool.d/pstate.conf` is wrong twice over: `/usr/lib/limine/limine-common-functions` lines 99 to 129 load `/usr/share/limine-entry-tool.d/*.conf`, then `/etc/limine-entry-tool.conf`, then `/etc/limine-entry-tool.d/*.conf`, then `/etc/default/limine` last at highest priority, so with `+=` in both files the parameter is appended to the cmdline twice, and `/etc/default/limine` is owned by no package (`pacman -Qo` confirms) so it is the wrong place to put a new setting. The fourth is that the record never says the EPP write is refused while the pseudo-governor is `performance`: the kernel doc states that in HWP plus performance the driver writes 0 to the EPP knob and "any attempts to change the EPP/EPB to a value different from 0 (performance) via sysfs in this configuration will be rejected". Things the record got right and I kept: `/etc/default/cpupower-service.conf` and `cpupower.service` are the correct names, confirmed against the Arch wiki CPU_frequency_scaling page and against the package file list from https://archlinux.org/packages/extra/x86_64/cpupower/json/ (cpupower 7.2.5-1 in extra, not installed here). `sudo pacman -S cpupower` is not blocked by the Omarchy guard: I read `/usr/bin/omarchy-update-pacman-guard` and it aborts only when both sync and sysupgrade are present, so a plain `-S` passes. I added that `cpupower.service` and `power-profiles-daemon.service` both write `scaling_governor` and must not both run, which the Arch wiki flags for the same reason for TLP and tuned. Severity `low` and frequency `very-common` are right and I left them, because nothing is actually broken. NOT exercised: I changed nothing, so I did not write an EPP value, did not add a Limine drop-in, did not reboot into passive mode, and did not install cpupower. The rejected-EPP-write behaviour and everything about `amd_pstate` are from the kernel documentation rather than from this machine, which has no `/sys/devices/system/cpu/amd_pstate/`.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Forcing the `performance` profile or EPP on a laptop raises temperatures and shortens battery life noticeably. Watch temperatures with `sensors` after changing it. The passive-mode step edits the kernel command line and `limine-mkinitcpio` rebuilds the UKI and the boot entry, so make sure you can reach the Limine menu and its snapshot entries before you reboot. Running `cpupower.service` alongside `power-profiles-daemon.service` leaves the governor at whichever of the two wrote last.

**Fix.**

Check what you are actually running:

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
cat /sys/devices/system/cpu/intel_pstate/status 2>/dev/null   # Intel only
```

If `scaling_driver` reads `intel_pstate` or `amd_pstate_epp` you are in active mode, `ondemand` does not exist, and the knob to turn is the EPP hint.

**On Omarchy 4, power-profiles-daemon owns this setting.** It is installed and enabled by default and it rewrites both `scaling_governor` and `energy_performance_preference` on every profile change, so set the profile rather than the sysfs file:

```bash
powerprofilesctl get
powerprofilesctl list
omarchy-powerprofiles-set ac balanced           # remembered for mains
omarchy-powerprofiles-set battery power-saver   # remembered for battery
```

`omarchy-powerprofiles-set` saves the choice under `~/.local/state/omarchy/powerprofiles/` and `omarchy-powerprofiles-init` restores it at session start, so that is the persistence you want here. The profiles map onto EPP `power` for power-saver, `balance_power` or `balance_performance` for balanced, and `performance` for performance. The same choices are in the Super+Space menu.

**On plain Arch with no power-profiles-daemon**, write the EPP yourself:

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences
echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
```

That write is refused while the pseudo-governor is `performance`. With HWP the driver pins EPP to `performance` and rejects any other value, so switch the pseudo-governor first:

```bash
echo powersave | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

Make it persistent with the same value you just tested:

```bash
sudo tee /etc/tmpfiles.d/energy_performance_preference.conf <<'EOF'
w /sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference - - - - balance_performance
EOF
sudo systemd-tmpfiles --create
```

If `power-profiles-daemon` is running, this file is applied at boot and then overwritten by the daemon. Use the profile route above or mask the daemon, but do not run both.

**If you genuinely want the classic governors**, switch the driver to passive mode with a kernel parameter: `intel_pstate=passive` or `amd_pstate=passive`, or `amd_pstate=disable` to fall back to `acpi_cpufreq`. On Omarchy 4 the kernel cmdline is assembled from Limine drop-ins. Put the parameter in a new file under `/etc/limine-entry-tool.d/` and nowhere else. Do not also append it to `/etc/default/limine`: that file is owned by no package and is read last at the highest priority, so with `+=` in both the parameter lands on the cmdline twice.

```bash
printf 'KERNEL_CMDLINE[default]+=" intel_pstate=passive"\n' | sudo tee /etc/limine-entry-tool.d/pstate.conf
sudo limine-mkinitcpio
sudo reboot
```

After the reboot, `scaling_driver` reads `intel_cpufreq` on Intel and `scaling_available_governors` lists the generic governors such as `schedutil`, `ondemand` and `conservative`. Only now is there a governor for `cpupower` to pin. `cpupower` is not installed on Omarchy 4, and on a fresh install the pacman sync databases are empty, so run `omarchy update` before installing anything:

```bash
sudo pacman -S cpupower
sudoedit /etc/default/cpupower-service.conf     # set governor='schedutil'
sudo systemctl enable --now cpupower.service
```

`cpupower.service` and `power-profiles-daemon.service` both write `scaling_governor`, so whichever runs last wins. Pick one. On Omarchy that means masking `power-profiles-daemon.service`, which also empties the power profile entry in the Super+Space menu.

**Verify.** After a reboot, `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver` and `cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference` show what you set. On Omarchy 4 check `powerprofilesctl get` as well, because the daemon is what wrote the value and it is the thing that will change it again. Under load, `watch -n1 'grep MHz /proc/cpuinfo'` shows frequencies rising.

Sources: <https://wiki.archlinux.org/title/CPU_frequency_scaling> · <https://wiki.archlinux.org/title/Power_management> · <https://www.kernel.org/doc/html/latest/admin-guide/pm/intel_pstate.html> · <https://www.kernel.org/doc/html/latest/admin-guide/pm/amd-pstate.html> · <https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/raw/main/src/ppd-driver-intel-pstate.c> · <https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/raw/main/src/ppd-driver-amd-pstate.c> · <https://archlinux.org/packages/extra/x86_64/cpupower/json/>

---

## Change Omarchy's screensaver and lock timeouts (and make edits actually take effect)

`omarchy-hypridle-timeouts-too-aggressive` · severity: **low** · frequency: **very-common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** On Omarchy 4 the screensaver appears after 150 seconds of idle and the machine locks at 300 seconds, which is too aggressive while reading or watching something. Editing `~/.config/hypr/hypridle.conf` changes nothing, and on a stock Omarchy 4 install that file does not exist.

**Cause.** Omarchy 4 does not use hypridle. Neither `hypridle` nor `hyprlock` is installed, and neither appears anywhere in the upstream `quattro` tree. Idle, screensaver and lock are a first-party Quickshell service inside `omarchy-shell`, which reads `idle.screensaver` and `idle.lock` from `~/.config/omarchy/shell.json` and falls back to `/usr/share/omarchy/config/omarchy/shell.json`. Both ship 150 seconds for the screensaver and 300 for the lock. Any advice naming `~/.config/hypr/hypridle.conf`, `lock_cmd`, `before_sleep_cmd` or `inhibit_sleep` is Omarchy 3 and applies to nothing on Omarchy 4.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation (omarchy-settings 4.0.2-1, Hyprland 0.56.2-1). The record's whole mechanism is Omarchy 3 and is false on Omarchy 4. `pacman -Q hypridle` and `pacman -Q hyprlock` both report the package is not found, `pacman -Qo /usr/bin/hypridle` reports no owner, `~/.config/hypr/` contains only Lua files plus `hyprsunset.conf` and `xdph.conf` with no `hypridle.conf`, and `gh api repos/omacom/omarchy/git/trees/quattro?recursive=1` returns no path matching hypridle. Idle is instead `/usr/share/omarchy/shell/plugins/services/idle/Service.qml`, a Quickshell service inside `omarchy-shell`, reading `idle.screensaver` and `idle.lock` from `~/.config/omarchy/shell.json` with `/usr/share/omarchy/config/omarchy/shell.json` as the default, both shipping 150 and 300 seconds. The record's 152 second lock is wrong, the real default is 300. The record's reload instruction is also wrong: there is no `hypridle.service`, and `/usr/share/omarchy/shell/shell.qml` gives the user config a `FileView` with `watchChanges: true` and `onFileChanged: reload()`, so an edit applies on save, with `omarchy-shell shell reloadConfig` as the manual fallback used by `omarchy-shell-config`. I read the live state read-only with `omarchy-shell idle status`, which returned `"screensaver":150,"lock":300` and confirmed the config path is what the running shell uses. I confirmed the same values in the upstream `quattro` copies of `config/omarchy/shell.json` and `shell/plugins/services/idle/Service.qml` through the GitHub API. I did NOT exercise any timeout, lock the session, or run `omarchy-toggle-idle`, because Omarchy 4's lock screen cannot be released headlessly. The `systemd-inhibit --what=idle` advice was dropped because the idle monitor is a Wayland `IdleMonitor` with `respectInhibitors: true` and I could not verify that a logind idle inhibitor reaches it, so the fix now names `omarchy-toggle-idle stay-awake` and Wayland idle inhibitors, which are both in the shipped code. The two `basecamp/omarchy` `master` raw URLs still return 200 but `master` is the Omarchy 3 tree, so they document a file Omarchy 4 does not ship, and the hypridle wiki page describes a daemon that is not installed. All three are removed. This machine is a desktop, so nothing laptop-specific was exercised.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Raising `idle.lock` leaves the screen unlocked for longer, which matters on a portable machine. `omarchy-toggle-idle stay-awake` persists across reboot through `~/.local/state/omarchy/indicators/stay-awake`, so a machine left in that state never locks itself again until `omarchy-toggle-idle allow-idle` is run. Hand-writing `~/.config/omarchy/shell.json` with only an `idle` block replaces the shipped defaults entirely, because the shell does not deep merge, and the bar then falls back to a smaller built-in layout.

**Fix.**

Omarchy 4 has no hypridle and no hyprlock. Neither package is installed (`pacman -Q hypridle` and `pacman -Q hyprlock` both report "not found" on 4.0.2-1) and neither exists in the upstream `quattro` tree. Idle, screensaver and lock are a Quickshell service inside `omarchy-shell`, at `/usr/share/omarchy/shell/plugins/services/idle/Service.qml`. The timeouts live in `~/.config/omarchy/shell.json`.

Read the live values first:

```bash
omarchy-shell idle status | jq
```

The shipped defaults are 150 seconds to the screensaver and 300 seconds to the lock, from `/usr/share/omarchy/config/omarchy/shell.json`:

```json
{
  "version": 1,
  "idle": {
    "screensaver": 150,
    "lock": 300
  }
}
```

To raise them to five and ten minutes, edit the `idle` block of your own `~/.config/omarchy/shell.json` in place. Edit rather than write a fresh file, because a user `shell.json` replaces the shipped defaults whole and is not merged into them:

```bash
tmp=$(mktemp)
jq '.idle.screensaver = 300 | .idle.lock = 600' ~/.config/omarchy/shell.json > "$tmp" && mv "$tmp" ~/.config/omarchy/shell.json
```

If `~/.config/omarchy/shell.json` does not exist, seed it from the shipped defaults first:

```bash
omarchy-refresh-config omarchy/shell.json
```

The shell watches that file and reloads it on save, so nothing has to be restarted. If a change does not take, force the reload over the shell's own IPC:

```bash
omarchy-shell shell reloadConfig
```

Both values are seconds counted from the moment the session goes idle, not from each other. A `lock` smaller than `screensaver` locks without ever showing the screensaver. Anything that is not a non-negative number falls back to the built-in default, silently. The file must keep `"version": 1` at the top level or the whole user config is ignored.

To stay awake for one long task instead of changing the config, use the shipped toggle, which is also the Stay Awake entry in the Omarchy menu:

```bash
omarchy-toggle-idle stay-awake     # no screensaver, no lock, until you turn it back
omarchy-toggle-idle allow-idle     # back to normal
omarchy-toggle-idle status
```

The idle monitor is created with `respectInhibitors: true`, so an application holding a Wayland idle inhibitor, a full-screen video player for example, already suppresses the idle cycle with no config change at all.

**Verify.** ```bash
omarchy-shell idle status | jq '{screensaver, lock, enabled, stayAwake}'
```

It reports the new `screensaver` and `lock` in seconds. `enabled: false` with `stayAwake: true` means idle is switched off entirely and no timeout will fire, so clear that first with `omarchy-toggle-idle allow-idle` before timing anything. Then leave the machine alone past the new screensaver time and confirm the screensaver and the lock arrive when expected.

Sources: <https://github.com/omacom/omarchy/blob/quattro/config/omarchy/shell.json> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/services/idle/Service.qml>

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

`suspend-fn-key-does-nothing` · severity: **low** · frequency: **rare** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** The laptop's Fn sleep key (Fn+F4 or similar) does nothing at all, not even a log line, whatever is set in `logind.conf`. On Omarchy 4 the power button does not suspend either, but that part is deliberate: Omarchy ships `HandlePowerKey=ignore` and binds the power key to its own system menu.

**Cause.** `systemd-logind` only watches input devices that udev tagged `power-switch`. Since systemd v251 the shipped `/usr/lib/udev/rules.d/70-power-switch.rules` tags every device with `ID_INPUT_KEY=1`, so on a current Arch or Omarchy 4 system the keyboard is normally tagged already and an untagged keyboard is the rare case rather than the usual one. Two other things stop the key on Omarchy 4 and neither is a udev problem. `omarchy-settings` ships `/etc/systemd/logind.conf.d/10-ignore-power-button.conf` setting `HandlePowerKey=ignore`, and drop-ins override `/etc/systemd/logind.conf`, so an edit to the main file is silently beaten by the drop-in. Some keyboards also never emit `KEY_SLEEP` for the Fn combination, in which case logind has nothing to act on no matter how it is configured.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation with systemd 261.2-1, and against the Arch wiki and systemd source. The record faithfully reproduces the Arch wiki section "Suspend from corresponding laptop Fn key not working", which is why it passed the source audit, but three claims do not hold today. First, the cause is stale: `/usr/lib/udev/rules.d/70-power-switch.rules` from systemd 261.2-1 contains `SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_KEY}=="1", TAG+="power-switch"`, so every key device is tagged. I confirmed the line is present in the systemd tags v251 through v255 and in `main`, and confirmed live that both USB keyboards on this machine carry `CURRENT_TAGS=:power-switch:` and appear in `journalctl --grep="Watching system buttons"`. The wiki's untagged-keyboard case is now rare, so the fix is rewritten diagnosis-first and the frequency is dropped from `occasional` to `rare`. Second, the symptom's "the power button works fine" is false on Omarchy 4: `busctl get-property ... HandlePowerKey` returns `ignore`, set by `/etc/systemd/logind.conf.d/10-ignore-power-button.conf` owned by `omarchy-settings` 4.0.2-1, and `/usr/share/omarchy/default/hypr/bindings/utilities.lua` binds `XF86PowerOff` to `omarchy-menu toggle system`. `HandleSuspendKey` returns `suspend`, the systemd default, and no Omarchy file binds `XF86Sleep`. Since `logind.conf(5)` states drop-ins override the main configuration file, a user editing `/etc/systemd/logind.conf` cannot beat Omarchy's drop-in, so the fix now writes a `90-` drop-in instead. Third, the record restarts `systemd-logind.service`: `/usr/share/omarchy/migrations/1784970000.sh` says in a comment "Reload rather than restart: restarting systemd-logind tears down the session", and `systemctl show systemd-logind -p CanReload` reports `yes`, so reload replaces restart and the danger field was rewritten around it. For the udev path no logind action is needed at all, because `src/login/logind.c` in systemd `main` calls `sd_device_monitor_filter_add_match_tag(m->device_button_monitor, "power-switch")` alongside an `input` subsystem filter, so a change event on a newly tagged device is picked up live. I did NOT exercise anything: no rule was installed, no unit was reloaded or restarted, no suspend was attempted, and this machine is a desktop, so no laptop Fn key was pressed. `/etc/systemd/logind.conf` here is package-stock and unmodified per `pacman -Qkk systemd`.
>
> *The Cause above was rewritten on 2026-09-12 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not restart `systemd-logind.service`. On Omarchy 4 that tears down the graphical session and loses unsaved work, which is why Omarchy's own migration reloads instead. `systemctl reload systemd-logind` applies a configuration change with the session intact, and a udev tag change needs no logind action at all. Setting `HandlePowerKey` to anything other than `ignore` on Omarchy 4 overrides the shipped drop-in and takes the power key away from the Omarchy system menu.

**Fix.**

On Omarchy 4, check what is actually true before adding a udev rule. Since systemd v251 the shipped rule tags every key device, so the untagged keyboard the old advice describes is now rare:

```
# /usr/lib/udev/rules.d/70-power-switch.rules   (owned by systemd, do not edit)
ACTION=="remove", GOTO="power_switch_end"
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_SWITCH}=="1", TAG+="power-switch"
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_KEY}=="1", TAG+="power-switch"
LABEL="power_switch_end"
```

**Step 1. Is logind watching the keyboard?** Neither command needs root:

```bash
for d in /dev/input/by-id/*-kbd; do
  echo "== $d"
  udevadm info --query=property "$d" | grep -E '^(TAGS|CURRENT_TAGS|ID_INPUT_KEY)='
done
journalctl -b --grep="Watching system buttons"
```

If `CURRENT_TAGS` already contains `power-switch` and the device shows up in the journal line, the tag is not your problem. Go to step 2.

**Step 2. What is logind configured to do with the key?** Read the value logind is enforcing, not the file:

```bash
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
  org.freedesktop.login1.Manager HandleSuspendKey HandlePowerKey HandleLidSwitch
```

On Omarchy 4 this returns `HandlePowerKey` = `ignore`, set by `/etc/systemd/logind.conf.d/10-ignore-power-button.conf` from the `omarchy-settings` package, because the power key is bound to the Omarchy system menu in `/usr/share/omarchy/default/hypr/bindings/utilities.lua`. `HandleSuspendKey` is left at the systemd default of `suspend`.

Drop-ins override the main file, so editing `/etc/systemd/logind.conf` cannot beat Omarchy's drop-in. Put a local override in a drop-in that sorts after it, in the 60 to 90 range `logind.conf(5)` reserves for the administrator:

```bash
sudo install -Dm644 /dev/stdin /etc/systemd/logind.conf.d/90-local-keys.conf <<'EOF'
[Login]
HandleSuspendKey=suspend
EOF
sudo systemctl reload systemd-logind
```

Reload, do not restart. On Omarchy 4, restarting `systemd-logind.service` tears down the graphical session, which Omarchy's own migration script `/usr/share/omarchy/migrations/1784970000.sh` states in a comment.

**Step 3. Only if step 1 showed the device is genuinely untagged**, tag it yourself. Get the exact parent name, substituting your own event number:

```bash
stat -c%N /dev/input/by-id/*-kbd
sudo udevadm info -a /dev/input/event6 | grep 'ATTRS{name}' | head -1
```

```
# /etc/udev/rules.d/70-power-switch-my.rules
ACTION=="remove", GOTO="power_switch_my_end"
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="SIGMACHIP USB Keyboard", TAG+="power-switch"
LABEL="power_switch_my_end"
```

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input --action=change
```

No logind restart is needed here either. `systemd-logind` runs a udev monitor filtered on the `power-switch` tag and the `input` subsystem, so it picks up a freshly tagged device from the change event on its own.

**Verify.** ```bash
udevadm info --query=property /dev/input/event6 | grep CURRENT_TAGS
journalctl -b --grep="Watching system buttons"
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
  org.freedesktop.login1.Manager HandleSuspendKey
```

`CURRENT_TAGS` contains `power-switch`, the keyboard's event device now appears in the journal line, `HandleSuspendKey` reads `suspend`, and pressing the sleep key suspends the machine.

Sources: <https://wiki.archlinux.org/title/Power_management/Suspend_and_hibernate> · <https://wiki.archlinux.org/title/Power_management> · <https://github.com/systemd/systemd/blob/main/rules.d/70-power-switch.rules> · <https://github.com/systemd/systemd/blob/main/src/login/logind.c> · <https://www.freedesktop.org/software/systemd/man/latest/logind.conf.html>

---
