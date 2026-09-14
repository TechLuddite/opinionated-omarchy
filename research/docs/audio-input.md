# Audio & input devices

35 problems. Sorted by severity, then by how often users hit it.

## Unmute the ALSA channel that silences sound after a reboot or headphones

`alsa-muted-after-reboot-or-headphones` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Sound worked, then after a reboot (or after plugging in headphones) there is silence, even though `wpctl status` shows the right sink and the volume slider is at 100%. `alsamixer` shows `MM` under one or more channels, or `Auto-Mute` is set to `Enabled`.

**Cause.** PipeWire's volume sits on top of the ALSA hardware mixer. If the underlying ALSA control is muted or at 0, or if the codec's `Auto-Mute Mode` is muting the speakers because it thinks a jack is inserted, nothing PipeWire does will produce sound. The ALSA state is restored on boot from `/var/lib/alsa/asound.state`, so a bad state persists.

> **Audit corrected this record.** The diagnosis is right and matches ALSA/Troubleshooting line 19 (Auto-Mute set to Disabled) and the asound.state persistence story. But the interactive section correctly warns 'select the real card, not default/PipeWire' and then the non-interactive block hardcodes `-c 0`, which on the majority of machines with a discrete GPU is the HDMI card, so every amixer line silently targets the wrong device. It also names Master/Speaker/Headphone unconditionally - SOF/UCM laptops frequently expose none of those simple controls and each line will fail with 'Unable to find simple control', which reads as the fix being broken.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

```bash
sudo pacman -S --needed alsa-utils
aplay -l          # note the card NUMBER of the real analog card, e.g. "card 1: PCH"
```

```bash
alsamixer -c 1    # substitute your number; F6 confirms, F5 shows all controls
```

- Any channel showing `MM`: highlight it and press `M` to unmute (should read `OO`).
- Raise `Master`, `Speaker`, `Headphone`, `PCM` with the up arrow.
- Set `Auto-Mute Mode` to `Disabled`.

Persist:

```bash
sudo alsactl store
```

Non-interactive - substitute your card number and list what your codec actually has first, because many SOF/UCM laptops have no Master or Speaker control and those lines will just report "Unable to find simple control":

```bash
CARD=1
amixer -c "$CARD" scontrols
amixer -c "$CARD" sset Master 80% unmute
amixer -c "$CARD" sset Speaker 80% unmute
amixer -c "$CARD" sset Headphone 80% unmute
amixer -c "$CARD" sset 'Auto-Mute Mode' Disabled
sudo alsactl store
```

If sound broke specifically after resume:

```bash
sudo alsactl init      # or: sudo alsactl restore
```

**Verify.** `amixer -c 0 sget Master` shows `[on]`, and sound survives a reboot without re-running anything.

Sources: <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting> · <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture>

---

## Fix a microphone PipeWire never lists as an input source

`microphone-not-detected-pipewire` · severity: **high** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** No microphone anywhere — `wpctl status` has an empty `Sources:` list or only shows a monitor source, and browsers/Discord say no input device. `arecord -l` may still list the capture hardware. On laptops the internal mic and the headset mic on the combo jack are both missing.

**Cause.** Either the card is on a playback-only profile (no `Analog Stereo Duplex`), or WirePlumber's ALSA monitor is using the ACP card profile instead of the UCM profile that modern laptop codecs need to expose their capture path.

> **Audit corrected this record.** The profile advice, the `monitor.alsa.properties = { alsa.use-ucm = true }` drop-in and the context.objects api.alsa.pcm.source declaration are all verbatim-correct against Arch PipeWire/Troubleshooting lines 57-66 and 116-120 and PipeWire lines 432-436. Two real defects: (1) the ALSA test line hardcodes `--device=hw:0,0`, but card 0 device 0 is a playback PCM on most machines and `hw:` refuses the dat format/rate that internal mics do not natively support - the user gets a confusing failure that looks like broken hardware; it also omits that PipeWire holds the device, so the recording will usually just return 'Device or resource busy'. (2) The UCM drop-in is named alsa-config.conf, the exact same filename the crackling/underrun record tells users to create in the same directory - applying both records silently destroys the first one.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

First check whether ALSA sees the capture device at all - read the real card/device numbers, do not assume 0,0, and stop PipeWire so the device is free:

```bash
arecord -l    # note "card N ... device M" of the CAPTURE device; it is rarely 0,0
systemctl --user stop pipewire.socket pipewire-pulse.socket pipewire.service pipewire-pulse.service wireplumber.service
arecord -f cd -d 5 -D plughw:N,M /tmp/test-mic.wav   # plughw, not hw: hw rejects rates/formats the codec lacks
systemctl --user start pipewire.service wireplumber.service pipewire-pulse.service
aplay /tmp/test-mic.wav
```

If ALSA records fine but PipeWire has no source, fix the profile in pavucontrol -> Configuration (`Analog Stereo Duplex`, or a profile containing `+ Analog Stereo Input`), or from the CLI:

```bash
wpctl status                 # note the Devices: ID of the card
wpctl set-profile <device-id> <profile-index>
```

If the input still never appears, force UCM. Give the file a distinct name - do NOT reuse `alsa-config.conf` if you already created that file for the period-size/headroom fix, or you will overwrite it:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

```conf
# ~/.config/wireplumber/wireplumber.conf.d/60-alsa-ucm.conf
monitor.alsa.properties = {
  alsa.use-ucm = true
  # if UCM alone does not help, also try turning ACP off:
  # alsa.use-acp = false
}
```

```bash
systemctl --user restart wireplumber.service
```

The manual `context.objects` declaration and the alsamixer/wpctl unmute steps are correct as written - just substitute the card/device numbers you got from `arecord -l` into `api.alsa.path`.

**Verify.** `wpctl status` lists a `Source` with a `*`, and `pw-record --target <source-id> /tmp/t.wav` followed by `pw-play /tmp/t.wav` plays back your voice.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting>

---

## Fix a laptop with no sound card at all from missing SOF firmware

`no-sound-missing-sof-firmware` · severity: **high** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Brand-new or recent laptop (Intel 11th gen and newer, many AMD too) has absolutely no sound card — `aplay -l` prints `no soundcards found...` and `wpctl status` has an empty Sinks list. `dmesg` or `journalctl -b -k` shows `error: sof firmware file is missing`, `error: failed to load DSP firmware -2`, `error: sof_probe_work failed err: -2`.

**Cause.** Modern laptops route audio through a Sound Open Firmware DSP instead of a plain HDA codec. The kernel driver loads but has no firmware blob to hand it, so no PCM device is ever registered. On laptops with Cirrus Logic smart amplifiers the separate `linux-firmware-cirrus` package is also required.

**Fix.**

```bash
sudo pacman -S --needed sof-firmware alsa-ucm-conf alsa-firmware
```

On laptops with Cirrus Logic boosted amps (most recent ThinkPads, Dell XPS, many ASUS/HP) also install:

```bash
sudo pacman -S --needed linux-firmware-cirrus
```

Some Intel audio devices additionally need:

```bash
sudo pacman -S --needed linux-firmware-intel
```

Reboot (the firmware is loaded at driver probe time, a service restart is not enough):

```bash
reboot
```

After reboot, confirm the card appeared and unmute it:

```bash
aplay -l
alsamixer          # F6 to pick the card, unmute (M) and raise Master/Speaker
sudo alsactl store
```

**Verify.** `aplay -l` lists a card, `journalctl -b -k | grep -i sof` no longer shows `firmware file is missing`, and `speaker-test -c2 -twav -l1` makes noise.

Sources: <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture> · <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting>

---

## Fix no sound at all when PipeWire reports no audio sinks

`pipewire-no-sinks-service-not-started` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** No sound at all. `wpctl status` shows no Sinks, or apps error out: `[ao/pipewire] PipeWire does not have any audio sinks, skipping` / `[ao] Failed to initialize audio driver 'pipewire'`, and `pactl info` prints `Connection failure: Connection refused`. Volume keys do nothing.

**Cause.** PipeWire is socket-activated, so nothing starts until a client connects. If the client races WirePlumber, or if `pipewire-pulse.service` / `wireplumber.service` are not running (common after a fresh install, after removing pulseaudio, or after killing the daemons), there is no session manager to create the nodes and no PulseAudio shim for apps that speak the Pulse protocol.

**Fix.**

Check what is actually running and what devices exist:

```bash
systemctl --user status pipewire pipewire-pulse wireplumber
wpctl status
pactl info
```

Make sure the compat packages are installed (`pipewire-pulse` replaces `pulseaudio` and `pulseaudio-bluetooth`; `pipewire-audio` is required for Bluetooth audio):

```bash
pacman -Qs '^pipewire|^wireplumber'
sudo pacman -S --needed pipewire pipewire-audio pipewire-pulse pipewire-alsa wireplumber
```

Enable them explicitly instead of relying on socket activation:

```bash
systemctl --user enable --now pipewire.service pipewire-pulse.service wireplumber.service
```

If they were already running, restart the whole stack:

```bash
systemctl --user restart pipewire.service pipewire-pulse.service wireplumber.service
```

**Verify.** `wpctl status` lists at least one entry under `Sinks` with a `*` next to it, `pactl info` prints `Server Name: PulseAudio (on PipeWire x.y.z)`, and `speaker-test -c2 -twav -l1` produces sound.

Sources: <https://wiki.archlinux.org/title/PipeWire> · <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://wiki.archlinux.org/title/WirePlumber>

---

## Fix Bluetooth audio refusing to connect with br-connection-profile-unavailable

`bluetooth-br-connection-profile-unavailable` · severity: **high** · frequency: **common** · applies to: `arch`, `bluetooth`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Bluetooth headphones or speaker refuse to connect. `bluetoothctl` prints `Failed to connect: org.bluez.Error.Failed br-connection-profile-unavailable`, and the journal shows bluetoothd rejecting the audio profile.

**Cause.** BlueZ hands audio profiles off to whatever media backend has registered with it. With PipeWire installed but not currently running (socket-activated and never woken), no A2DP endpoint is registered, so BlueZ has no profile to connect to.

**Fix.**

Start PipeWire before connecting:

```bash
systemctl --user start pipewire.service wireplumber.service pipewire-pulse.service
```

Make sure `pipewire-audio` is installed — it is what provides the Bluetooth audio support:

```bash
sudo pacman -S --needed pipewire-audio
```

Enable the units so this cannot recur:

```bash
systemctl --user enable --now pipewire.service wireplumber.service pipewire-pulse.service
```

Then retry the connection:

```bash
bluetoothctl connect XX:XX:XX:XX:XX:XX
```

Also make sure the old PulseAudio Bluetooth stack is not half-installed alongside:

```bash
pacman -Qs pulseaudio
```

**Verify.** `bluetoothctl info XX:XX:XX:XX:XX:XX` shows `Connected: yes`, and the device appears in `wpctl status` as a `bluez_output.*` sink.

Sources: <https://wiki.archlinux.org/title/Bluetooth>

---

## Fix bluetoothctl reporting No default controller available

`bluetoothctl-no-default-controller` · severity: **high** · frequency: **common** · applies to: `arch`, `bluetooth`, `cachyos`, `desktop`, `endeavouros`, `grub`, `hyprland`, `intel`, `laptop`, `manjaro`, `omarchy`, `systemd-boot`, `wayland`

**Symptom.** `bluetoothctl` says `No default controller available`, the Bluetooth toggle in the panel does nothing, and `bluetoothctl scan on` errors with `org.bluez.Error.NotReady`. `journalctl | grep hci` may show `command tx timeout` or `Reading Intel version command failed`.

**Cause.** Four different faults produce the same message, and they need different fixes.

1. **The kernel never bound a controller.** `btusb` (or the PCI/UART driver for the part) did not load, or it loaded and the firmware blob it wants is missing. `/sys/class/bluetooth` is then empty and bluetoothd has nothing to offer, so bluetoothctl reports no default controller.
2. **The controller firmware wedged.** Common on Intel combo Wi-Fi/Bluetooth cards, and notoriously after dual booting Windows, which leaves the part in a state a warm reboot does not clear. The journal shows `command tx timeout` or `Reading Intel version command failed`.
3. **bluetoothd is not running.** On plain Arch `bluetooth.service` is not enabled by default. On Omarchy 4 it is: `/usr/share/omarchy/install/hardware/bluetooth.sh` runs `systemctl enable bluetooth.service` at install, so this cause is usually already excluded there.
4. **An rfkill block.** This one normally presents differently. A soft block leaves the controller listed by `bluetoothctl list` with `Powered: no`, and `bluetoothctl power on` fails rather than the controller vanishing. It matters on Omarchy 4 because the rfkill block **is** how Omarchy stores the Bluetooth on/off state: `/usr/share/omarchy/bin/omarchy-bluetooth-power` blocks and unblocks, the shell's Bluetooth panel calls it (`/usr/share/omarchy/shell/plugins/panels/bluetooth/Panel.qml`), and systemd-rfkill restores the block on the next boot from `/var/lib/systemd/rfkill`. So Bluetooth staying off across reboots on Omarchy is deliberate, not a fault.

> **Audit corrected this record.** Re-audited on this Omarchy 4 workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, bluez 5.87-2, util-linux 2.42.2-1, kernel 7.1.9), which does have a working adapter: `rfkill list` shows `0: hci0: Bluetooth` unblocked, `bluetoothctl list` shows one controller, `bluetoothctl show` reports `Powered: yes`, and `systemctl status bluetooth` shows the unit enabled and running. The Arch wiki Bluetooth page was refetched and its "bluetoothctl: No default controller available" section (around line 788 of the raw wikitext) does support the record's cold-power-cycle and `btusb.enable_autosuspend=n` claims, so the source audit was right. Two things are wrong for Omarchy 4. First and worst, the bootloader advice names two bootloaders Omarchy 4 does not have: `pacman -Q grub systemd-boot` reports neither is installed, `/etc/default/grub` does not exist, and `/boot/loader/entries` is not a thing on this machine. Omarchy 4 boots a UKI through Limine and the kernel cmdline comes from drop-ins under `/etc/limine-entry-tool.d/`, confirmed by reading `omarchy-defaults.conf` there and matching it against `/proc/cmdline`. A reader following the record on Omarchy would edit a file that does not exist and conclude the fix does not work. Replaced the primary route with `/etc/modprobe.d/`, which is bootloader independent and verified here: `zgrep CONFIG_BT_HCIBTUSB /proc/config.gz` gives `=m`, `lsmod` shows `btusb` loaded, and `modinfo btusb` lists `enable_autosuspend:Enable USB autosuspend by default (bool)`. Second, the record misses the single most Omarchy-specific cause. Omarchy 4 stores the Bluetooth on/off state as an rfkill soft block on purpose: `/usr/share/omarchy/bin/omarchy-bluetooth-power` does `rfkill block` and `rfkill unblock` and its own comments state that a plain `bluetoothctl power on` fails while the block is set, and `Panel.qml` line 637 in the shell's Bluetooth panel invokes it. So on Omarchy the recovery is `omarchy-bluetooth-power on` or the menu's `omarchy-restart-bluetooth`, which is literally `rfkill unblock bluetooth`. Also corrected two smaller things: `sudo systemctl enable --now bluetooth.service` is a no-op on Omarchy 4 because `/usr/share/omarchy/install/hardware/bluetooth.sh` already enables it, and the record's ordering mixed diagnosis with remediation, so the fix now separates a read-only diagnostic block from the actions and says which reading points at which cause. One accuracy fix to the cause: an rfkill soft block usually leaves the controller listed with `Powered: no` rather than producing "No default controller available", so it is worth checking but is not the usual cause of that exact string. Left severity `high` and frequency `common` alone. NOT exercised: nothing was paired, connected, blocked, unblocked or restarted, and no module was unloaded, so the `modprobe -r btusb` and cold power cycle steps were verified from module metadata and the wiki, not run. I could not read `/boot` to check whether `btusb` is bundled into the initramfs, because `/boot` is a vfat ESP mounted `dmask=0077` and I did not use sudo. If it were bundled, the modprobe drop-in would also need a UKI rebuild, but `btusb` is not a boot-critical module and the `autodetect` plus `modconf` hooks in `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` would not normally pull it in.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `sudo modprobe -r btusb` drops every connected Bluetooth device at once. If you are using a Bluetooth keyboard or mouse, you lose the input you are typing on, so have a wired fallback attached first. The kernel command line branch touches boot configuration: on Omarchy 4 that is a drop-in under `/etc/limine-entry-tool.d/` feeding a rebuilt UKI, and a typo there can leave the machine unbootable. Prefer the `/etc/modprobe.d/btusb-autosuspend.conf` file, which needs no rebuild and cannot affect boot. Check `cat /proc/cmdline` after the next boot if you take the kernel parameter route.

**Fix.**

**Diagnose before you fix.** These commands separate the four causes and none of them change anything:

```bash
ls /sys/class/bluetooth          # expect hci0. Empty means the kernel bound nothing
bluetoothctl list                # controllers bluetoothd knows about
rfkill list bluetooth            # rfkill ships in util-linux, there is no separate package
systemctl status bluetooth.service
lsmod | grep -E 'btusb|btintel|bluetooth'
journalctl -b -k | grep -i -E 'hci|bluetooth|firmware'
```

Read them like this:

- `/sys/class/bluetooth` empty **and** no `btusb` in `lsmod`: the driver never bound. Find the part with `lsusb` or `lspci -nn | grep -i blue`, then look in the journal for a `Direct firmware load ... failed` line naming the blob it wanted.
- Controller listed, `bluetoothctl show` says `Powered: no`, `rfkill list bluetooth` says `Soft blocked: yes`: a block, not a broken adapter.
- Journal shows `command tx timeout` or `Reading Intel version command failed`: the controller firmware is wedged, and no software fix will clear it.

**Clear a block.** On Omarchy 4 go through Omarchy's wrapper, because BlueZ refuses `bluetoothctl power on` while a block is set:

```bash
omarchy-bluetooth-power on     # rfkill unblock, then wait for bluetoothd to power the adapter
omarchy-restart-bluetooth      # what the Omarchy menu runs: rfkill unblock bluetooth, then show the state
```

On plain Arch:

```bash
sudo rfkill unblock bluetooth
bluetoothctl power on
```

**Start the service.** Only needed on plain Arch, since Omarchy 4 enables it at install:

```bash
sudo systemctl enable --now bluetooth.service
```

**Reload the driver** when the adapter is present but dead:

```bash
sudo modprobe -r btusb
sudo modprobe btusb
sudo systemctl restart bluetooth.service
```

**Cold power cycle** when the journal showed `command tx timeout` or `Reading Intel version command failed`. A reboot will not fix it. Shut down, unplug the power cable (and remove the battery if it is removable) for about 30 seconds, then boot. That is what forces the controller to reload its firmware.

**If the adapter disappears after suspend or after USB autosuspend**, turn autosuspend off for `btusb` with a modprobe drop-in rather than a kernel parameter. `btusb` is a module on the Arch kernel (`CONFIG_BT_HCIBTUSB=m`) and `modinfo btusb` lists `enable_autosuspend` as a bool, so this works whatever the bootloader is and cannot break boot:

```bash
printf 'options btusb enable_autosuspend=n\n' | sudo tee /etc/modprobe.d/btusb-autosuspend.conf
sudo modprobe -r btusb && sudo modprobe btusb
```

That file sits alongside `/usr/lib/modprobe.d/bluetooth-usb.conf`, which bluez ships with `options btusb reset=1`. Leave the bluez file alone, it is package owned.

If you would rather set it on the kernel command line, use the bootloader the machine actually has.

- **Omarchy 4** boots a unified kernel image through Limine. There is no `/boot/loader/entries` and no `/etc/default/grub`. Add a drop-in, which `limine-entry-tool` reads when the UKI is rebuilt:

  ```
  # /etc/limine-entry-tool.d/99-btusb.conf
  KERNEL_CMDLINE[default]+=" btusb.enable_autosuspend=n"
  ```

  The rebuild happens on the next kernel or mkinitcpio update through `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`. Confirm with `cat /proc/cmdline` after the next boot.

- **systemd-boot**: add it to the `options` line of `/boot/loader/entries/*.conf`.
- **GRUB**: add it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then run `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

**Verify.** ```bash
bluetoothctl list                # prints a Controller line
bluetoothctl show | grep Powered # Powered: yes
rfkill list bluetooth            # Soft blocked: no, Hard blocked: no
```

Then `bluetoothctl scan on` discovers nearby devices. On Omarchy 4, `omarchy-bluetooth-power is-on` exits 0 when any controller is powered, which is the check Omarchy's own panel uses. If you added the modprobe drop-in, confirm it took with:

```bash
cat /sys/module/btusb/parameters/enable_autosuspend   # expect N
```

Sources: <https://wiki.archlinux.org/title/Bluetooth>

---

## Sound card vanishes from wpctl after resume and only a reboot brings it back

`sound-card-disappears-after-suspend-resume` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `systemd`

**Symptom.** Close the lid, open it again, and the audio device is gone. `wpctl status` shows an empty `Sinks:` list or only the HDMI outputs — the laptop speakers or the USB DAC are no longer there. `aplay -l` may print `no soundcards found...`, or list the card while everything stays silent. The journal has lines like `snd-usb-audio 1-6.1.2:1.0: resume error -22`, `Could not recover alsa device from SUSPENDED state`, or `Error opening PCM device front:1: No such file or directory`; `pactl list sinks` can hang and eventually return `Connection failure: Timeout`. Physically unplugging and replugging a USB audio interface brings it straight back, and a reboot always fixes it.

**Cause.** The ALSA driver failed to reinitialise the hardware on resume, so the card never comes back up underneath PipeWire. Several distinct triggers land here: the HDA controller or codec does not restore state (worsened by `power_save`, which is on by default); USB autosuspend cut power to a USB DAC and the device did not re-enumerate; a stale `/var/lib/alsa/asound.state` gets restored and re-mutes or mis-routes the channels; or WirePlumber holds a node for a device that no longer exists and refuses to rebuild it. This is distinct from the mute-state and WirePlumber-state records: here the *card itself* is missing, not just misconfigured.

> **Audit corrected this record.** The seven-step ladder is technically sound and well sourced, with one wrong Omarchy claim at the end. Verified: the systemd-sleep hook contract is exactly as stated — systemd-suspend.service(8) documents /usr/lib/systemd/system-sleep/, $1 = pre|post, $2 = the sleep action, and carries the precise warning the record relies on: "Note that user.slice will be frozen while the executables are running, so they should not attempt to communicate with any user services expecting a reply" — so the 'the hook cannot call systemctl --user' caveat is right and is the detail most versions of this advice get wrong. Step 6 reproduces the Arch ALSA/Troubleshooting procedure exactly (mkdir -p /etc/alsa; touch /etc/alsa/state-daemon.conf to stop alsa-store.service rewriting the file; rm /var/lib/alsa/asound.state; reboot; then rm the condition file and alsactl store). The power_save=0 power_save_controller=N modprobe.d snippet is the wiki's verbatim recommendation, `lspci -k -nn -d ::0403` and /proc/asound/modules are the right discovery commands, and `rm -r ~/.local/state/wireplumber/` touches only per-user state (no system path). ONE defect: `omarchy-restart-audio` does not exist in basecamp/omarchy. The menu path is right — bin/omarchy-menu's show_update_hardware_menu maps "Audio" to `present_terminal omarchy-restart-pipewire` — but the command name is wrong, and so is the scope claim: omarchy-restart-pipewire's whole body is `systemctl --user restart wireplumber.service pipewire.service` plus a conditional restart of pipewire-pulse.service. That is step 1 only. It does NOT wipe ~/.local/state/wireplumber, so it does not perform step 7, and a reader who runs it expecting the ghost-device cleanup will think step 7 has been tried when it has not.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `modprobe -r` fails with `Module snd_hda_intel is in use` if any process still holds /dev/snd — never force it. A broken or slow script in /usr/lib/systemd/system-sleep/ delays suspend and resume for every sleep cycle, because systemd waits for all of them to finish; the `|| true` guards above keep a failed unload from blocking suspend. Deleting /var/lib/alsa/asound.state discards every saved mixer level for every card, so you may have to reset volumes and re-unmute channels afterwards. Deleting ~/.local/state/wireplumber discards remembered default devices, per-device volumes and Bluetooth profile choices.

**Fix.**

Replace the closing Omarchy line with:

**On Omarchy**, *Update > Hardware > Audio* runs `omarchy-restart-pipewire` (not `omarchy-restart-audio`, which does not exist). That covers step 1 only — its entire body is:

```bash
systemctl --user restart wireplumber.service pipewire.service
# plus pipewire-pulse.service if it is active
```

Step 7 is not included: the WirePlumber state directory is left in place. If the card is still missing after the menu item, do the state wipe by hand:

```bash
systemctl --user stop wireplumber
rm -r ~/.local/state/wireplumber/
systemctl --user start wireplumber
```

(That loses remembered per-device volumes, chosen profiles and default-device picks — you will reselect them once. No system-level risk.)

One addition to step 3 while you are there: if `fuser --all --verbose /dev/snd/*` keeps showing holders after you stop the services, the sockets are re-activating them. Stop those too before the modprobe:

```bash
systemctl --user stop pipewire.socket pipewire-pulse.socket wireplumber pipewire pipewire-pulse
```

**Verify.** Suspend and resume, then check `cat /proc/asound/cards` still lists the card and `wpctl status` still lists the sink. `journalctl -b -k --since "5 minutes ago" | grep -i -E 'snd|resume error'` should be clean. Run `speaker-test -c 2` after resume. Repeat over three or four suspend cycles — this failure is frequently intermittent (often described as 'about every third suspend'), so a single successful resume proves nothing.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting> · <https://wiki.archlinux.org/title/WirePlumber> · <https://wiki.archlinux.org/title/Power_management> · <https://raw.githubusercontent.com/systemd/systemd/main/man/systemd-suspend.service.xml> · <https://bbs.archlinux.org/viewtopic.php?id=305291> · <https://bbs.archlinux.org/viewtopic.php?id=274296> · <https://bbs.archlinux.org/viewtopic.php?id=177755>

---

## Laptop speakers, headphone jack or internal mic never work despite the card being detected

`snd-hda-intel-model-quirk-speakers-mic-jack` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `aplay -l` lists the HDA card and `wpctl status` shows a sink, but the built-in speakers are permanently silent — or the headphone jack outputs nothing, or plugging a headset into the combined 4-pole (TRRS) jack gives you audio out but the headset microphone is never offered as an input. Nothing in `alsamixer` is muted and there are no obvious errors in `dmesg`. Installing `sof-firmware` and reinstalling PipeWire made no difference.

**Cause.** The HD-Audio driver builds its pin configuration from the BIOS pin defaults, and on a lot of laptops (and most cheap or very new ones) those defaults are wrong or incomplete. The driver then wires the wrong DAC to the wrong pin, or does not know the jack is a shared headset jack, and the affected output or input simply never appears. The kernel keeps a whitelist of per-machine 'fixups' selected by PCI SSID, but a machine that is not yet in that list gets generic handling. This is the escalation step past the SOF-firmware and mute-state records: the firmware is loaded and the card is present, it is the pin/model mapping that is wrong.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, kernel 7.1.9-arch1-2, mkinitcpio 41.1-1, limine-mkinitcpio-hook 1.37.1-1) and against the cited pages, all four of which I retrieved and all four of which still say what the record claims. docs.kernel.org/sound/hd-audio/notes.html returned 200 and carries the nofixup wording, the generic wording, the SSID alias introduced in 5.15 and the request_firmware and /lib/firmware sentence verbatim. models.html returned 200. The Arch ALSA troubleshooting page still carries the three chip-identification commands and the dell-headset-multi tip including the not-a-Dell caveat and both codec families, and the power_save line verbatim. alsa-tools is extra 1.2.15-3. The two identification commands work here: both report ALC1220 on card 0. Two real defects and two gaps. The worst is in the danger field: the record states that nothing here touches the initramfs, and on Omarchy 4 that is false. /etc/mkinitcpio.conf.d/omarchy_hooks.conf assigns HOOKS containing modconf, and /usr/lib/initcpio/install/modconf line 5 is add_full_dir /etc/modprobe.d '*.conf', so anything written to /etc/modprobe.d is bundled into the UKI at the next rebuild. The conclusion the record draws is still right, because snd_hda_intel is not in MODULES and autodetect does not pull sound modules, so the option takes effect from the real root with no rebuild needed. The reasoning was wrong, and the corpus has already been bitten by records assuming the wrong initramfs model. I added the correct rebuild command for the case where someone does need one: /etc/mkinitcpio.d/ is empty on this machine, so mkinitcpio -P finds no presets, and the UKI comes from limine-mkinitcpio. Second, step 3's service stop omitted the sockets. pipewire.socket and pipewire-pulse.socket socket-activate the daemon on the next client connection, so the fuser gate can pass and the card be retaken a second later. The record's own audit note spotted this in 2026 and never put it in the fix, so it is now in the fix. Third, the record offered model=XXXX:YYYY without saying where the subsystem ID comes from. It is in the same file as the codec name: grep -i 'Subsystem Id' /proc/asound/card0/codec#0 returns 0x1458a0c3 on this machine, which is model=1458:a0c3. Fourth, alsa-info.sh is what both the kernel docs and the Arch wiki ask for in a bug report and it is already in alsa-utils 1.2.16-1, so that is now step 8. I also named omarchy-restart-audio, which is the supported way to bring audio back here. NOT exercised, and this is the important limit on the confidence. This machine is a desktop: card 0 is an Intel PCH with an ALC1220, card 1 is NVidia HDMI, and the mic is a USB Blue Yeti. There are no laptop speakers, no combined TRRS jack and no internal mic, so the symptom cannot be reproduced and no model string could be tested. I did not run modprobe, did not write anything under /etc/modprobe.d and did not rebuild the initramfs, all of which the audit forbids on the operator's daily workstation. alsa-tools is not installed, so hdajackretask and hda-verb were confirmed from the package file list and the kernel docs rather than by running them, and the exact hda-verb argument form is reproduced from the record and the hwdep section of notes.html rather than from its own --help. The /etc/modprobe.d finding was read from the hook files and the modconf install script, not proven by inspecting a built UKI, because /boot is a vfat ESP mounted dmask=0077 and unreadable unprivileged.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A wrong `model=` string can leave you with less working audio than you started with, including no sound at all, until you delete the file from /etc/modprobe.d and reboot. Keep a note of what the file contained. `hda-verb` writes raw verbs straight to codec registers with no driver state tracking, and on some machines it can unmute an amplifier past its safe level, so lower the volume before experimenting and do not run verbs you cannot explain.

Nothing here can stop the machine booting, because `snd_hda_intel` is not loaded in early userspace. It does reach the initramfs on Omarchy 4, though, and the record used to say otherwise. Omarchy assigns `HOOKS` wholesale in `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` and that list contains `modconf`, whose install script does `add_full_dir /etc/modprobe.d '*.conf'`. So every file you write there is copied into the UKI at the next rebuild. That is harmless for a sound quirk, but it means `/etc/modprobe.d` is not an initramfs-free zone here, and a stale copy of the file survives inside the image until the next rebuild.

If you ever do need that rebuild, **`mkinitcpio -P` is the wrong command on Omarchy 4**: `/etc/mkinitcpio.d/` is empty, so there are no presets and it does nothing. The image is a UKI built by `limine-mkinitcpio-hook`:

```bash
sudo limine-mkinitcpio
```

**Fix.**

**1. Identify the codec chip.**

```bash
grep 'Codec:' /proc/asound/card*/codec#*
grep . /sys/class/sound/hwC?D?/chip_name
alsamixer          # 'Chip:' in the top-left corner
```

**2. Note the subsystem ID at the same time.** You need it for the SSID form in step 4, and it is in the same file:

```bash
grep -i 'Subsystem Id' /proc/asound/card0/codec#0
# Subsystem Id: 0x1458a0c3   ->   model=1458:a0c3
```

**3. Look your chip up in the kernel's model list** at https://docs.kernel.org/sound/hd-audio/models.html and pick a candidate `model` string. For a headset mic that is not detected on a combined 4-pole jack, try `dell-headset-multi` first even if the machine is not a Dell. It is the standard answer for ALC22x/23x/25x/269/27x/28x/29x and ALC66x/67x/892 codecs.

**4. Test it without rebooting.** Nothing may hold `/dev/snd` while you reload, and stopping the services is not enough on its own: `pipewire.socket` and `pipewire-pulse.socket` will socket-activate the daemon again the moment any client connects, and it takes the card back mid-procedure. Stop the sockets too.

```bash
systemctl --user stop pipewire.socket pipewire-pulse.socket
systemctl --user stop wireplumber.service pipewire.service pipewire-pulse.service
fuser --all --verbose /dev/snd/*        # must be empty, kill whatever is listed
sudo modprobe -r snd_hda_intel
sudo modprobe snd_hda_intel model=dell-headset-multi
```

Bring audio back. On Omarchy use the shipped wrapper, which starts the same units and additionally recovers a USB audio device left stuck by the reload:

```bash
omarchy restart audio      # or: omarchy-restart-audio
```

On plain Arch:

```bash
systemctl --user start pipewire.socket pipewire-pulse.socket
systemctl --user start pipewire.service pipewire-pulse.service wireplumber.service
wpctl status
```

**5. Make it permanent** once a model string works:

```bash
sudo tee /etc/modprobe.d/alsa-hda.conf >/dev/null <<'EOF'
options snd_hda_intel model=dell-headset-multi
EOF
```

No initramfs rebuild is needed for this to take effect. `snd_hda_intel` is loaded by udev from the real root after `switch_root`, and modprobe reads `/etc/modprobe.d` there. See the danger note for the one Omarchy detail that goes with it.

Since kernel 5.15 the option also accepts an SSID alias, which applies another machine's whole quirk set. That is what to reach for when your laptop is a rebadge of a supported one, using the subsystem ID from step 2:

```
options snd_hda_intel model=103c:8862
```

Two special values worth knowing: `model=nofixup` skips the device-specific fixups in the codec parser (use when a *wrong* quirk is being applied and broke things), and `model=generic` skips the codec-specific parser and uses only the generic one.

**6. If no model string fits, remap the pins yourself.**

```bash
sudo pacman -S alsa-tools
hdajackretask         # GUI: override a pin's function, then 'Install boot override'
```

`hdajackretask` writes a firmware patch file and the matching `/etc/modprobe.d` entry for you. For hand-written patches, the driver reads the file with `request_firmware()`, so it must sit on the firmware path, typically `/lib/firmware`:

```
options snd_hda_intel patch=my-laptop-patch.fw
```

For one-off register pokes while experimenting, `hda-verb` (also in `alsa-tools`) writes directly to a codec node. It needs `CONFIG_SND_HDA_HWDEP`, which is what creates the `/dev/snd/hwC0D0` device it talks to:

```bash
sudo hda-verb /dev/snd/hwC0D0 0x0 PARAMETERS VENDOR_ID
```

**7. While you are in `/etc/modprobe.d`**, a second HDA option is worth setting on laptops that pop or clip the first half-second of every sound:

```
options snd_hda_intel power_save=0 power_save_controller=N
```

**8. If nothing works, report it with the data the maintainers ask for.** `alsa-info.sh` is already present in `alsa-utils`, so there is nothing to install:

```bash
sudo alsa-info.sh --no-upload
```

Send that output, plus the vendor, product and model names and `uname -r`, with the bug report.

**Verify.** After the reload, `wpctl status` lists the previously-missing sink or source. `speaker-test -c 2 -D hw:0,0` produces sound from the built-in speakers. Plug in a headset and confirm `wpctl status` gains a 'Headset Microphone' source and `arecord -f cd -d 5 /tmp/t.wav && aplay /tmp/t.wav` captures your voice. `alsamixer` should show new controls that were absent before.

Sources: <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting> · <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture> · <https://docs.kernel.org/sound/hd-audio/notes.html> · <https://docs.kernel.org/sound/hd-audio/models.html> · <https://archlinux.org/packages/extra/x86_64/alsa-tools/>

---

## Revive a dead Synaptics touchpad after a kernel upgrade

`synaptics-touchpad-dead-needs-intertouch` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Touchpad is detected but completely non-functional after a kernel upgrade — the cursor never moves. `libinput list-devices` shows it as `SynPS/2 Synaptics TouchPad`. The kernel log contains: `Your touchpad says it can support a different bus. If i2c-hid and hid-rmi are not used, you might want to try setting psmouse.synaptics_intertouch to 1`.

**Cause.** The touchpad supports the RMI4/SMBus ("InterTouch") interface but the kernel bound it to the legacy PS/2 protocol instead, which on these panels yields a non-functional device. Reported on Omarchy with a Synaptics TM3114-001 (SYN3228/SYN1e00) after a kernel bump.

> **Audit corrected this record.** The problem and the core fix are confirmed straight from cited omarchy issue 5991, which contains the same kernel hint string, the same /etc/modprobe.d/psmouse.conf content, the same modprobe -r/modprobe reload, and the same before/after device naming (SynPS/2 Synaptics TouchPad -> Synaptics TM3114-001 on rmi4). The defect is the trailing step: `sudo mkinitcpio -P` is presented as what makes the setting survive kernel upgrades, and that rationale is simply false - a modprobe.d file is read at module load from the root filesystem and persists on its own; psmouse is not in the initramfs. Users who see no change after the reload will now also sit through an initramfs rebuild for nothing, and the record never tells them what to check.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Unloading `psmouse` also disconnects a PS/2 keyboard on some laptops. Have a USB keyboard/mouse to hand, or just reboot instead of using `modprobe -r`.

**Fix.**

```conf
# /etc/modprobe.d/psmouse.conf
options psmouse synaptics_intertouch=1
```

Apply it without rebooting:

```bash
sudo modprobe -r psmouse && sudo modprobe psmouse
```

This already persists across kernel upgrades - do NOT run `mkinitcpio -P` for it. psmouse is not in the initramfs, so regenerating it changes nothing here.

Verify it took:

```bash
cat /sys/module/psmouse/parameters/synaptics_intertouch   # should print Y
sudo dmesg | grep -i -E 'psmouse|synaptics|rmi4'
sudo libinput list-devices | grep -A3 -i touchpad
```

The device should now be reported as the real model name (e.g. `Synaptics TM3114-001`) driven by `rmi4` rather than `SynPS/2 Synaptics TouchPad`. If it does not come up, confirm the SMBus driver loaded (`lsmod | grep rmi`) and reboot once - some controllers only re-bind to RMI4 on a cold probe.

**Verify.** `sudo libinput list-devices` shows the touchpad under its real model name, and `sudo libinput debug-events` emits motion events as you move a finger.

Sources: <https://github.com/basecamp/omarchy/issues/5991> · <https://wiki.archlinux.org/title/Libinput>

---

## Stop the loud pop or crack every time audio starts or stops

`audio-pop-crack-when-playback-starts` · severity: **medium** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** A loud click, pop or crack out of the speakers/headphones every time a sound starts or stops — notification sounds, a YouTube video starting, or the first half-second of audio being clipped off. Often described as "the first word of every notification is cut off".

**Cause.** WirePlumber suspends idle nodes to save power (`session.suspend-timeout-seconds`, default 5s). Resuming the ALSA device re-powers the codec and produces the pop, and the ramp-up eats the start of the stream. Separately, `snd_hda_intel` runtime power saving powers the whole controller down.

> **Audit corrected this record.** The WirePlumber suspend-timeout config is verbatim-correct against Arch PipeWire/Troubleshooting lines 695-750, and the modprobe option string matches the ALSA/Troubleshooting page exactly. Two defects: (1) `sudo mkinitcpio -P` does nothing here - snd_hda_intel is not in the initramfs, and the record gives no step that actually applies the module option, so the user reboots-less and concludes it failed; (2) the dither block is a mid-file fragment (trailing commas, no enclosing structure) presented as if it were a standalone conf file - pasted as-is it is a parse error.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Disabling `snd_hda_intel` power saving measurably shortens laptop battery life. `mkinitcpio -P` rebuilds every preset — if it errors out, do not reboot until it succeeds.

**Fix.**

Keep the disable-suspension.conf as written, then restart:

```bash
systemctl --user restart pipewire.service wireplumber.service
```

If it still pops, the HDA controller is power-gating:

```conf
# /etc/modprobe.d/audio_disable_powersave.conf
options snd_hda_intel power_save=0 power_save_controller=N
```

Do NOT run `mkinitcpio -P` for this - snd_hda_intel is not in the initramfs and regenerating it changes nothing. Apply the option by reloading the module (stop the audio stack first or it will be busy) or simply reboot:

```bash
systemctl --user stop pipewire.socket pipewire-pulse.socket pipewire.service pipewire-pulse.service wireplumber.service
sudo modprobe -r snd_hda_intel && sudo modprobe snd_hda_intel
systemctl --user start pipewire.service wireplumber.service pipewire-pulse.service
```

Verify it took:

```bash
cat /sys/module/snd_hda_intel/parameters/power_save   # must print 0
```

For the dither workaround, the three lines are NOT a separate file - they go inside the existing `update-props = { ... }` block of disable-suspension.conf, alongside session.suspend-timeout-seconds:

```conf
      update-props = {
        session.suspend-timeout-seconds = 0
        dither.method = "wannamaker3"
        dither.noise = 2
      }
```

**Verify.** Play a short sound twice in a row with a 30s gap — no click on either. `wpctl status` shows the sink staying in a non-suspended state; battery drain increases slightly, which is expected.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting>

---

## Use a Bluetooth headset's microphone without wrecking the audio quality

`bluetooth-headset-mic-hfp-a2dp-profile` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `bluetooth`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Bluetooth headphones sound good for music but the built-in mic is not offered as an input. Or the moment you join a call the output collapses to tinny mono and stays that way. `pactl list cards | grep -E 'Name:|Active Profile:'` shows the `bluez_card.*` entry flipping between `a2dp-sink` and `headset-head-unit` (or a codec-suffixed variant such as `headset-head-unit-msbc`), and `wpctl status` shows the stereo sink replaced by a low rate mono one. On Omarchy 4 there is no `pavucontrol` to watch this in, so read it from `pactl` or `wpctl`.

**Cause.** Classic Bluetooth cannot carry high quality stereo output and microphone input over A2DP at the same time. A2DP sink is output only, so using the mic means switching the whole card to the mono HFP profile, and the playback quality drops with it. WirePlumber performs that switch on its own: the setting `bluetooth.autoswitch-to-headset-profile` defaults to `true` in the schema in `/usr/share/wireplumber/wireplumber.conf`, and `/usr/share/wireplumber/scripts/device/autoswitch-bluetooth-profile.lua` switches whenever a client links to the device's loopback source node, which includes apps that only probe for a mic. The trade is no longer absolute. PipeWire 1.6.8 also carries duplex A2DP codecs (`faststream_duplex`, `aptx_ll_duplex`, `opus_05_duplex`) and LE Audio BAP, either of which can give a usable mic and good output together when both ends support them. Most common headsets still do not, so on those the trade is real and the switch is what you see.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, bluez 5.87-2, pipewire 1:1.6.8-1, wireplumber 0.5.15-1, kernel 7.1.9) and against the two cited Arch wiki pages, both refetched. The core of the record holds: `bluetooth.autoswitch-to-headset-profile` is still the setting name, still defaults to `true`, and is still read by WirePlumber 0.5.15. Confirmed on this machine in the schema block of `/usr/share/wireplumber/wireplumber.conf` and at lines 590 and 625 of `/usr/share/wireplumber/scripts/device/autoswitch-bluetooth-profile.lua`. `wpctl settings --save KEY VAL` exists in wpctl 0.5.15 (`man wpctl`), and `~/.config/wireplumber/wireplumber.conf.d/*.conf` is the correct 0.5 location, matching the shipped template `/usr/share/doc/wireplumber/examples/wireplumber.conf.d/bluetooth.conf`. Four things were wrong for Omarchy 4. First, the mSBC advice is PulseAudio-era framing: `man 7 pipewire-props` on pipewire 1.6.8 defines `bluez5.enable-msbc` as "Override device quirk list and enable MSBC for devices for which it is disabled", so mSBC is already on except for quirked hardware and the record told the reader to enable something already enabled. Second, the record ignores that Omarchy 4 already installs a file into the exact directory it tells the reader to create: `/usr/share/omarchy/config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf`, byte-identical to the copy present at `~/.config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf` on this machine, and `omarchy refresh` restores Omarchy's copy from `$OMARCHY_PATH/config/`. Third, the symptom names `pavucontrol`, which `pacman -Q pavucontrol` reports is not installed on Omarchy 4. `pactl` is present via libpulse 17.0+r98+gb096704c0-1. Fourth, the danger understated the cost of the roles override: `man 7 pipewire-props` gives the default role list as `[ a2dp_sink a2dp_source bap_sink bap_source bap_bcast_sink bap_bcast_source hfp_hf hfp_ag ]`, so restricting it to the two A2DP roles also kills LE Audio, which the record did not say. The cause was also overstated as an absolute, since pipewire 1.6.8 ships duplex A2DP codecs and BAP, and the autoswitch script's own header comment names Faststream as a non-HFP mic path. Added an Omarchy branch for the restart step using `omarchy-restart-audio`, which also restarts `pipewire-pulse` (the record restarted only pipewire and wireplumber). Corrected the verify command: the original `grep -A5 'Active Profile'` prints the five lines after the profile line, which do not identify the card. NOT exercised: no Bluetooth device was paired, connected or profile-switched, because this is the operator's daily workstation, so the `pactl set-card-profile` commands and the codec-suffixed profile names were read from the plugin strings in `/usr/lib/spa-0.2/bluez5/libspa-bluez5.so` (`headset-head-unit` plus a `%s-%s` format) and from the shipped codec plugins `libspa-codec-bluez5-hfp-msbc.so`, `libspa-codec-bluez5-hfp-lc3-swb.so` and `libspa-codec-bluez5-hfp-cvsd.so`, not observed live.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `bluez5.roles = [ a2dp_sink a2dp_source ]` removes more than the headset microphone. On pipewire 1.6.8 the default role list is `[ a2dp_sink a2dp_source bap_sink bap_source bap_bcast_sink bap_bcast_source hfp_hf hfp_ag ]`, so that line also disables LE Audio. A device that only speaks LE Audio will then produce no sink at all. Do not apply it if you take calls on those headphones, or if you own an LE Audio device.

**Fix.**

Two settings decide this, and both live in WirePlumber 0.5. PulseAudio-era `module-bluetooth-policy` advice is dead on PipeWire.

Stop apps dragging the headset into HFP. You give up the headset mic while this is off:

```bash
wpctl settings --save bluetooth.autoswitch-to-headset-profile false
```

That key is current on wireplumber 0.5.15. Its schema is in `/usr/share/wireplumber/wireplumber.conf` under `wireplumber.settings.schema` with `default = true`, and `/usr/share/wireplumber/scripts/device/autoswitch-bluetooth-profile.lua` reads it through `Settings.get_boolean`.

To set it from a file instead, and to drop the HFP role entirely:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

```conf
# ~/.config/wireplumber/wireplumber.conf.d/51-mitigate-annoying-profile-switch.conf
wireplumber.settings = {
  bluetooth.autoswitch-to-headset-profile = false
}

monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source ]
}
```

**On Omarchy 4 that directory is not empty.** Omarchy ships `config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf` and copies it into `~/.config/wireplumber/wireplumber.conf.d/`. It sets `bluez5.auto-connect = [ a2dp_sink a2dp_source ]` through a `monitor.bluez.rules` entry. Add your own file next to it rather than editing it, because `omarchy refresh` restores Omarchy's copy from `$OMARCHY_PATH/config/`.

If you want the headset mic to work well instead, leave auto-switching on and **do not reach for `bluez5.enable-msbc`**. On pipewire 1.6.8 mSBC is already active for every device the quirk database does not exclude. `man 7 pipewire-props` describes the property as "Override device quirk list and enable MSBC for devices for which it is disabled", so it is an override, not a switch. Set it only when your specific headset is on the quirk list:

```conf
# ~/.config/wireplumber/wireplumber.conf.d/90-bluez-force-codecs.conf
monitor.bluez.properties = {
  bluez5.enable-msbc = true
  bluez5.enable-sbc-xq = true
}
```

Restart audio, then reconnect the device. On Omarchy 4 use the wrapper, which also restarts `pipewire-pulse` and recovers a stuck USB audio device:

```bash
omarchy-restart-audio
```

On plain Arch:

```bash
systemctl --user restart wireplumber.service pipewire.service pipewire-pulse.service
```

Switch profile by hand at any time. `pactl` is present on Omarchy 4 through `libpulse`, but `pavucontrol` is not installed:

```bash
pactl list cards short
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX a2dp-sink
```

The HFP profile name carries the negotiated codec, built as `headset-head-unit-<codec>`, so it may be `headset-head-unit-cvsd`, `headset-head-unit-msbc` or `headset-head-unit-lc3_swb` depending on what the headset agreed to. List what your card actually offers before naming one:

```bash
pactl list cards | grep -E 'headset-head-unit|a2dp-sink'
```

**Verify.** ```bash
wpctl settings bluetooth.autoswitch-to-headset-profile
```

prints `false` once saved (a bare `wpctl settings KEY` only reads it). Then:

```bash
pactl list cards | grep -E 'Name:|Active Profile:'
```

shows `Active Profile: a2dp-sink` for the `bluez_card.*` entry and it stays there when you open a video call site. To see which HFP profiles the headset actually offers, rather than assuming mSBC:

```bash
pactl list cards | grep -E 'headset-head-unit'
```

Sources: <https://wiki.archlinux.org/title/Bluetooth_headset> · <https://wiki.archlinux.org/title/PipeWire>

---

## Make Bluetooth devices reconnect on their own after suspend

`bluetooth-not-reconnecting-after-suspend` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `bluetooth`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Bluetooth headphones/keyboard/mouse pair fine but never reconnect on their own — after a suspend/resume, or after the device sleeps, you have to open the Bluetooth panel and connect manually every time. The journal shows `bluetoothd[487]: Authentication attempt without agent` and `bluetoothd[487]: Access denied: org.bluez.Error.Rejected`.

**Cause.** The device is paired but not marked *trusted*. Without the trusted flag BlueZ requires an authorisation agent to be present for each incoming connection; on a bare Hyprland session none is running at that moment, so the reconnect is rejected.

**Fix.**

```bash
bluetoothctl
```

```
[bluetooth]# devices
[bluetooth]# trust XX:XX:XX:XX:XX:XX
[bluetooth]# connect XX:XX:XX:XX:XX:XX
[bluetooth]# quit
```

Or non-interactively:

```bash
bluetoothctl trust XX:XX:XX:XX:XX:XX
```

If reconnect still fails and the device was previously paired with Windows on the same machine (dual boot), the device is storing one link key per MAC and yours was overwritten — you must re-pair, and to have it work in both OSes you have to copy the link keys between them (see the Arch Wiki "Dual boot pairing" section).

If the device connects and then drops after a few seconds, with `bluetoothd: connect error: Connection refused (111)` in the journal, you may be hitting the BlueZ 5.83+ regression affecting multipoint devices; the interim workaround is:

```bash
sudo systemctl restart bluetooth.service
```

**Verify.** `bluetoothctl info XX:XX:XX:XX:XX:XX` shows `Trusted: yes`, and the device reconnects on its own after `systemctl suspend` and resume.

Sources: <https://wiki.archlinux.org/title/Bluetooth> · <https://github.com/bluez/bluez/issues/1330>

---

## Fix keyboard and touchpad settings ignored after the Hyprland 0.55 Lua switch

`hyprland-055-lua-config-input-ignored` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** On plain Hyprland, `~/.config/hypr/hyprland.conf` stops being read the moment a `~/.config/hypr/hyprland.lua` exists: keyboard layout reverts to US, touchpad natural scrolling and tap-to-click stop applying, and gestures stop working. If you had no config at all, Hyprland writes a fresh `hyprland.lua` example and shows a yellow warning overlay on every start. On Omarchy 4 you never see the autogenerated config or the yellow bar, because the upgrade installs Omarchy's own `hypr/hyprland.lua` and `hypr/input.lua`. What you see on Omarchy 4 is narrower: an option you had left at a `.conf` default is now unset in Lua and the behaviour it used to give is gone. Touchpad right-click is the common one.

**Cause.** Since Hyprland 0.55 hyprlang is deprecated in favour of Lua and the config is `$XDG_CONFIG_HOME/hypr/hyprland.lua`, normally `~/.config/hypr/hyprland.lua`. Hyprland 0.56.2, which Omarchy 4 ships, has not removed the old parser. `Jeremy::getMainConfigPath` looks for `hyprland.lua` first, falls back to `hyprland.conf` when no Lua file exists, and generates an example `hyprland.lua` carrying `hl.config({ autogenerated = true })` only when it finds neither. `hyprctl reload full-reset` is documented as switching the config context to or from hyprlang. So a `.conf` is not rejected, it is shadowed: once any `hyprland.lua` is present, every `input { ... }`, `device { ... }` and `gesture = ...` line in the `.conf` is dead. On Omarchy 4 a `hyprland.lua` is always present, because `omarchy-upgrade-to-quattro` lists `hypr/hyprland.lua`, `hypr/input.lua`, `hypr/bindings.lua`, `hypr/looknfeel.lua`, `hypr/monitors.lua` and `hypr/autostart.lua` in `always_copy_config_files` and installs the packaged copies. Omarchy also rewrites `package.path` in `/usr/share/omarchy/default/hypr/bootstrap.lua` to `~/.local/state/?.lua;~/.config/?.lua;$OMARCHY_PATH/?.lua`, so a `require` there resolves from those roots and not from the directory holding `hyprland.lua`.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1, kernel 7.1.9) against the Hyprland wiki pages the record cites and against Hyprland's own source at tag v0.56.2. What held: the wiki Start page says almost word for word what the record's cause says, including "Since Hyprland 0.55, hyprlang is deprecated in favor of lua", the config being $XDG_CONFIG_HOME/hypr/hyprland.lua, the yellow warning and the line hl.config({ autogenerated = true }) that clears it, and require with / or . as separators resolved relative to hyprland.lua. I confirmed the autogenerated text and the warning overlay in src/config/lua/DefaultConfig.hpp and CConfigManager::postConfigReload. Every option name in the record's block is real and typed as claimed in the wiki config-options table, the hl.gesture form and both examples match the gestures page (fingers, direction, action, with "fullscreen" a listed action), and I confirmed live that hyprctl getoption input:touchpad:tap_to_click resolves with colon nesting. Three things are wrong. First and worst, the cause claims a hyprlang config is "simply not read" on 0.55 and newer. On 0.56.2 it is shadowed, not rejected: Jeremy::getMainConfigPath searches for hyprland.lua first, falls back to hyprland.conf when no Lua file exists, and only generates the autogenerated example when it finds neither. The .conf parser is still compiled in and hyprctl reload full-reset is documented as switching to or from hyprlang. The fallback is gone on Hyprland main, but main is unreleased and v0.56.2 is the newest tag. Second, the whole autogenerated and yellow-bar half of the symptom cannot happen on Omarchy 4: /usr/share/omarchy/bin/omarchy-upgrade-to-quattro lists hypr/hyprland.lua, hypr/input.lua, hypr/bindings.lua, hypr/looknfeel.lua, hypr/monitors.lua and hypr/autostart.lua in always_copy_config_files and installs the packaged copies, backing up what was there, so a hyprland.lua always exists. Third, the fix sends an Omarchy reader to the wrong file and trips two known traps. On Omarchy 4 personal input overrides belong in ~/.config/hypr/input.lua, which is required after default.hypr.omarchy and ships fully commented out. Its kb_options = "caps:escape" replaces rather than merges, so it silently drops Omarchy 4's compose:caps,shift:both_capslock_cancel, and caps:escape collides with compose:caps. Its clickfinger_behavior = false flips the value Omarchy 4 sets in /usr/share/omarchy/default/hypr/input.lua, and the cited issue is about exactly that option: omacom/omarchy#6935 is a Framework touchpad losing right-click entirely after the 4.0 migration because the option was left unset in Lua, and the reporter states plainly that "the 4.0 migration correctly converted this file to the new Lua format". So the cited issue contradicts the record's framing and supports the corrected one. The require rule is also wrong on Omarchy, where /usr/share/omarchy/default/hypr/bootstrap.lua rewrites package.path to ~/.local/state/?.lua;~/.config/?.lua;$OMARCHY_PATH/?.lua rather than leaving Hyprland's configdir/?.lua default from CConfigManager. tap_to_click and disable_while_typing are already Hyprland defaults (both confirmed in the config-options table) and scroll_factor 0.4 is already Omarchy's value, so three of the example's lines are no-ops the reader will misread as a failed edit. Severity dropped from high to medium: on Omarchy 4 nobody loses a config to this, and the real Omarchy consequence is a handful of touchpad defaults changing, which matches the sibling record keyboard-layout-not-applied-hyprland at medium. Frequency stays very-common. ON DUPLICATION: this is not a duplicate of keyboard-layout-not-applied-hyprland, but the two overlap and should cross-reference. This record uniquely holds the Lua migration itself as the cause (hyprland.conf shadowed, the autogenerated config, the warning overlay), the require and split-file mechanics, the gesture syntax move, and the 0.54-and-older branch. The sibling uniquely holds layout specifics, localectl and /etc/vconsole.conf, switchxkblayout, the omarchy.keyboard-layout bar widget, and resolve_binds_by_sym. What genuinely duplicates is the hl.config input block and the kb_options replacement trap. On filing: this record sits in audio-input while the sibling sits in hyprland-config, and neither is about audio. Both are Hyprland input configuration and belong in one category. That is an operator call, but the split is a filing error, not a distinction. NOT exercised: nothing was written, and no reload, eval, keyword or dispatch was run, because this is the operator's live graphical session. There is no touchpad on this machine, so every touchpad claim comes from the wiki, from Omarchy's packaged input.lua and from InputManager.cpp, not from hardware. The autogenerated-config path and the hyprland.conf fallback were read in source at v0.56.2 and never triggered here.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A Lua syntax error stops the config loading. Hyprland 0.56 has an emergency mode for the worst case: if a Lua error leaves no keybinds registered it shows an error overlay and binds SUPER+Q to a known terminal, SUPER+R to `hyprland-run` and SUPER+M to exit, so a broken edit does not usually lock you out. Do not rely on it. Run `hyprctl reload` then `hyprctl configerrors` from a running session before you log out, and keep a copy of the file you edited. On Omarchy 4, editing `~/.config/hypr/input.lua` takes it out of the stock set, so migration `/usr/share/omarchy/migrations/1781485962.sh`, which sha-gates the packaged copy, stops replacing it on update. That is what you want, and it also means later Omarchy improvements to that file will not reach you.

**Fix.**

**On Omarchy 4 your input settings go in `~/.config/hypr/input.lua`, not `hyprland.lua`.** `~/.config/hypr/hyprland.lua` is Omarchy's packaged entry point. It runs `/usr/share/omarchy/default/hypr/bootstrap.lua`, then `require("default.hypr.omarchy")`, then `require("hypr.input")`, so your file loads after Omarchy's defaults and wins.

`~/.config/hypr/input.lua` ships as one fully commented-out `hl.config` block. Uncomment only the lines you want and keep the surrounding structure:

```lua
-- ~/.config/hypr/input.lua
hl.config({
  input = {
    -- kb_options REPLACES the previous string, it does not merge. Omarchy 4 sets
    -- "compose:caps,shift:both_capslock_cancel" in
    -- /usr/share/omarchy/default/hypr/input.lua, so repeat those unless you mean to
    -- drop them. caps:escape and compose:caps both claim Caps Lock, so pick one.
    kb_options = "compose:caps,shift:both_capslock_cancel",
    repeat_rate = 40,
    repeat_delay = 250,
    follow_mouse = 1,

    touchpad = {
      natural_scroll = true,         -- Hyprland default false, Omarchy 4 also sets false
      clickfinger_behavior = true,   -- Omarchy 4 already sets this, see the warning below
      scroll_factor = 0.4,           -- Omarchy 4 already sets this
      disable_while_typing = true,   -- already the Hyprland default
      tap_to_click = true,           -- already the Hyprland default
      drag_3fg = 1,
    },
  },
})
```

**Do not leave `clickfinger_behavior` unset on a touchpad.** omacom/omarchy#6935 reports right-click dead after the 4.0 migration, neither two-finger nor lower-right corner, on a config that had the line commented out. Setting it explicitly to `true` or `false` restores it. `true` gives two-finger right-click, `false` gives lower-right corner.

**On plain Hyprland 0.55 or newer** the same block goes in `~/.config/hypr/hyprland.lua`. Split files use Lua's `require`, resolved relative to the directory holding `hyprland.lua`, and `/` or `.` both work as separators:

```lua
require("myconf/input")
require("myconf.binds")
```

That relative rule does not hold on Omarchy 4. `bootstrap.lua` rewrites `package.path` to `~/.local/state/?.lua;~/.config/?.lua;$OMARCHY_PATH/?.lua` plus Lua's own, which is why Omarchy's entry point writes `require("hypr.input")` to reach `~/.config/hypr/input.lua`.

**Gestures moved too.** The old `gesture = 3, horizontal, workspace` line becomes:

```lua
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
hl.gesture({ fingers = 4, direction = "up", action = "fullscreen" })
```

**If Hyprland wrote the config for you**, you had neither `hyprland.lua` nor `hyprland.conf`. Remove the `hl.config({ autogenerated = true })` line to clear the yellow warning overlay. This does not happen on Omarchy 4, which always installs its own `hyprland.lua`.

**Apply and check:**

```bash
hyprctl reload
hyprctl configerrors
hyprctl getoption input:kb_layout
hyprctl getoption input:touchpad:tap_to_click
```

`getoption` prints a `set:` line as well as the value. `set: true` means something in your config set it, `set: false` means you are reading a built-in default and your edit did not land.

**If you are pinned to Hyprland 0.54 or older**, keep the hyprlang `hyprland.conf`. The 0.54 wiki pages document that syntax. On 0.56 the old parser is still present and `hyprctl reload full-reset` switches the context to or from hyprlang, but Omarchy 4 does not support running that way.

**Verify.** `hyprctl configerrors` prints nothing after `hyprctl reload`. `hyprctl getoption input:kb_layout` and `hyprctl getoption input:touchpad:tap_to_click` return the values you set and report `set: true`, not `set: false`. `hyprctl getoption input:kb_options` still contains Omarchy 4's `compose:caps,shift:both_capslock_cancel` if you meant to keep it. On a laptop, two-finger right-click, natural scrolling and any gesture you added behave as configured.

Sources: <https://wiki.hypr.land/Configuring/Start/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Gestures/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/supplementary/jeremy/Jeremy.cpp> · <https://github.com/hyprwm/Hyprland/blob/main/src/config/lua/DefaultConfig.hpp> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/config-options.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/binds/gestures.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/using-hyprctl.md> · <https://github.com/omacom/omarchy/issues/6935> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/input.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/input.lua> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-upgrade-to-quattro>

---

## Set a keyboard layout Hyprland actually applies, not setxkbmap

`keyboard-layout-not-applied-wayland` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** `localectl set-x11-keymap` or `setxkbmap de` has no effect under Hyprland — the layout stays US, or only changes inside XWayland apps. Caps-Lock-as-Escape remaps done "the X11 way" don't work either.

**Cause.** Wayland compositors do not use the Xorg keyboard configuration path. Hyprland loads its own XKB keymap from its config and pushes it to clients over the Wayland protocol; `setxkbmap` only talks to an X server, and `localectl`'s X11 keymap is not consulted at all.

**Fix.**

Set the layout in Hyprland's config (Lua, 0.55+):

```lua
-- ~/.config/hypr/hyprland.lua
hl.config({
  input = {
    kb_layout = "us,de",
    kb_variant = ",nodeadkeys",
    kb_options = "grp:alt_shift_toggle,caps:escape",
    numlock_by_default = true,
  },
})
```

On Hyprland 0.54 and older the equivalent hyprlang is:

```
input {
    kb_layout = us,de
    kb_variant = ,nodeadkeys
    kb_options = grp:alt_shift_toggle,caps:escape
    numlock_by_default = true
}
```

```bash
hyprctl reload
```

Browse valid values with:

```bash
less /usr/share/X11/xkb/rules/evdev.lst
localectl list-x11-keymap-layouts
localectl list-x11-keymap-options | grep caps
```

For a *specific* keyboard only (name from `hyprctl devices`):

```lua
hl.device({ name = "my-external-keyboard", kb_layout = "de" })
```

Note that per-device layouts do not change how keybinds resolve unless you also set `resolve_binds_by_sym = 1`.

Also set the TTY/console layout separately, since it is a different subsystem:

```bash
sudo localectl set-keymap de
```

**Verify.** `hyprctl getoption input:kb_layout` shows your layout; typing in a native Wayland app (e.g. `foot`, `kitty`) produces the right symbols, and `wev` reports the expected keysyms.

Sources: <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Devices/> · <https://wiki.archlinux.org/title/Keyboard_input>

---

## Volume, mute and brightness keys do nothing on a bare Hyprland session

`media-keys-volume-brightness-not-bound-hyprland` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Fresh Arch/EndeavourOS/CachyOS + Hyprland install: the laptop's volume up/down, mute, mic-mute, play/pause and screen-brightness keys do absolutely nothing. No OSD, no change. `wpctl get-volume @DEFAULT_AUDIO_SINK@` prints the same number before and after pressing the key, and `brightnessctl get` never moves. Audio itself works fine from pavucontrol and the same keys worked in GNOME/KDE. A variant: the keys work on the desktop but stop working the moment hyprlock is up.

**Cause.** Hyprland is a bare compositor and ships no default keybinds at all. XF86AudioRaiseVolume, XF86AudioMute, XF86MonBrightnessUp etc. are just keysyms until you bind them yourself, and there is no DE settings daemon (gnome-settings-daemon, powerdevil) listening for them. Two follow-on gotchas: a bind without the `repeating` flag fires once per press instead of repeating while held, and a bind without the `locked` flag is swallowed while an input inhibitor (hyprlock) is active, which is why volume keys 'stop working on the lock screen'. Omarchy already ships these binds in default/hypr/bindings/media.lua, so this bites bare Hyprland and DIY installs rather than Omarchy.

> **Audit corrected this record.** Core fix verified end to end. Local Binds.md confirms hl.bind flag names `locked` ("Will also work when an input inhibitor (e.g. a lockscreen) is active") and `repeating` ("Will repeat when held"), and the wiki's own volume-key example is nearly identical to this record's. hyprlang `bindel`/`bindl` letters are correct. `basecamp/omarchy/dev/default/hypr/bindings/media.lua` exists and does ship these binds with `{ locked = true }`/`repeating = true`, confirming this bites bare Hyprland not Omarchy; Omarchy 4's user override file `~/.config/hypr/bindings.lua` exists in config/hypr. Arch packages wireplumber, brightnessctl, playerctl, wev, swayosd all in extra (swayosd 0.3.2, ships /usr/lib/systemd/system/swayosd-libinput-backend.service). The brightnessctl/logind claim checks out: the Arch PKGBUILD builds and installs with `make ENABLE_SYSTEMD=1` only and never passes INSTALL_UDEV_RULES, so no udev rules are shipped and writes go through logind, requiring an active seat session. ONE defect: the swayosd block enables only `swayosd-libinput-backend.service`, which upstream documents as *optional* (caps/num/scroll-lock notifications). The component that actually draws the OSD is `swayosd-server`, which must be running in the compositor session — as written, `swayosd-client --output-volume raise` will silently do nothing.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Replace the swayosd paragraph with:

```bash
sudo pacman -S --needed swayosd
# OPTIONAL: only for caps-lock / num-lock / scroll-lock OSDs
sudo systemctl enable --now swayosd-libinput-backend.service
```

The OSD is drawn by `swayosd-server`, which must be running in your Hyprland session — without it `swayosd-client` does nothing. Autostart it:

```lua
-- Hyprland 0.55+ (~/.config/hypr/hyprland.lua, or Omarchy 4 ~/.config/hypr/autostart.lua)
hl.exec_once("swayosd-server")
```

```
# Hyprland 0.54 and older
exec-once = swayosd-server
```

Then point the binds at swayosd-client instead of wpctl/brightnessctl, keeping the same flags:

```lua
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("swayosd-client --output-volume raise"), { repeating = true, locked = true })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("swayosd-client --output-volume mute-toggle"), { locked = true })
hl.bind("XF86MonBrightnessUp",  hl.dsp.exec_cmd("swayosd-client --brightness +5"), { repeating = true, locked = true })
```

Verify with `systemctl --user status swayosd-server` or `pgrep swayosd-server` before assuming a bind is broken. (On Omarchy, swayosd-server is already autostarted and `omarchy-restart-swayosd` restarts it.)

**Verify.** Run `wev`, press each key, and confirm the keysym matches what you bound. Then press volume up and check `wpctl get-volume @DEFAULT_AUDIO_SINK@` changes; press brightness up and check `brightnessctl get` changes. Lock the screen with `hyprlock` and confirm the volume keys still work — that proves the `locked` flag took effect.

Sources: <https://wiki.hypr.land/Configuring/Basics/Binds/> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Binds.md> · <https://wiki.archlinux.org/title/WirePlumber> · <https://wiki.archlinux.org/title/Backlight> · <https://gitlab.archlinux.org/archlinux/packaging/packages/brightnessctl/-/raw/main/PKGBUILD> · <https://raw.githubusercontent.com/basecamp/omarchy/dev/default/hypr/bindings/media.lua>

---

## Mouse feels accelerated, floaty or too slow after switching from X11 to Hyprland

`mouse-acceleration-sensitivity-hyprland` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** "My mouse feels completely wrong under Hyprland." The pointer accelerates when you move fast and crawls when you move slow, so aiming in games and precise clicking are impossible; or it is simply far too slow/too fast compared to the same mouse under X11 or Windows. Setting `input { sensitivity = ... }` seems to do nothing above a certain value, and turning the sensitivity up to fix the mouse makes the touchpad unusably twitchy at the same time.

**Cause.** libinput applies its `adaptive` pointer-acceleration profile by default, and its own documentation calls adaptive "the default profile for all devices". That is the same curve X11 users usually disabled long ago with `libinput Accel Profile Flat` in an xorg.conf.d snippet, which no longer applies on Wayland. Hyprland ships no acceleration override of its own: `input.accel_profile` defaults to empty, meaning "use libinput's default mode for your input device". Omarchy 4 does not override it either. `/usr/share/omarchy/default/hypr/input.lua` sets `sensitivity = 0` and says nothing about `accel_profile`, confirmed on a running install where `hyprctl getoption input:accel_profile` reports `str: [[EMPTY]]` with `set: false`. Four further things confuse people. `input.sensitivity` is clamped to the range -1.0 to 1.0, so cranking the number past 1 does nothing. `input.*` settings are global and hit the touchpad and trackpoint as well as the mouse. `force_no_accel` is read only as the global `input:force_no_accel` and cannot go inside a per-device block. And `flat` is not free: libinput describes it as "a constant factor applied to all device deltas, regardless of the speed of motion", so you lose the slow-precision and fast-travel split and usually need more DPI or more physical movement to cross the screen.

> **Audit corrected this record.** Re-checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1, kernel 7.1.9) against the current Hyprland wiki, libinput's own documentation and Hyprland's source at tag v0.56.2. Every version-sensitive claim in the record held. The wiki config-options table still says `sensitivity` is float, default 0.0, limits -1.0 to 1.0; `accel_profile` is string, default [[Empty]], "Leave empty to use libinput's default mode for your input device", options adaptive, flat and custom; `force_no_accel` is bool, default false, with the wiki's own "not recommended due to potential cursor desynchronization" note. The custom form `custom <step> <points...>` with the example `custom 200 0.0 0.5` is verbatim from that page. The devices page still gives `hl.device({ name = ..., ... })` and still excludes `force_no_accel` and the window-management options from a device block, and I confirmed that in source: `src/managers/input/InputManager.cpp` reads `force_no_accel` only as the global `input:force_no_accel`, while `sensitivity` and `accel_profile` go through `getDeviceFloat` and `getDeviceString` with a per-device bare key. libinput's pointer-acceleration page confirms the cause in its own words: "The adaptive profile is the default profile for all devices" and "The flat profile is simply a constant factor applied to all device deltas, regardless of the speed of motion". One thing the previous auditor could not check is now confirmed in source rather than inferred: the record's touchpad device block sets bare `natural_scroll` and `scroll_factor` rather than nesting them under `touchpad = { ... }`, and that is correct. InputManager.cpp resolves a per-device key by its bare name and chooses the fallback by device type, so `natural_scroll` in a touchpad's block falls back to `input:touchpad:natural_scroll` and in a mouse's block to `input:natural_scroll`. Confirmed live on this machine: `hyprctl getoption input:sensitivity` returns `float: 0.000000` with `set: true`, and `hyprctl getoption input:accel_profile` returns `str: [[EMPTY]]` with `set: false`, which is the record's central claim about Omarchy proved on hardware. Four things needed correcting. First, the device names were invented. `logitech-g502-hero-gaming-mouse` is not a name anything printed, and the record gave no rule for the lowercase-hyphen form, so the corrected fix prints them with `hyprctl -j devices` and uses real ones from this machine: `razer-razer-basilisk-v3` and `corsair-corsair-gaming-k55-rgb-keyboard-1`. Second, the Omarchy path was right but the instruction was not. `~/.config/hypr/input.lua` here is byte-identical to the packaged template at omacom/omarchy@quattro `config/hypr/input.lua` and ships fully commented out, and lines 22 to 26 of that template already carry `sensitivity = 0.35` and `accel_profile = "flat"`. The Omarchy fix is therefore uncommenting two lines, not writing a new block, and a reader who uncomments the whole block instead picks up `kb_layout = "us,dk,eu"` and a `kb_options` string that replaces rather than merges and so drops Omarchy 4's `compose:caps,shift:both_capslock_cancel`. Third, the record's step 1 told the reader to set `sensitivity = 0.0`, which is already what `/usr/share/omarchy/default/hypr/input.lua` sets, so on Omarchy that line changes nothing and reads as a failed edit. Fourth, and this is the one the record was most incomplete on, it said flat means no acceleration without ever saying what flat costs. The corrected fix gives libinput's own description and the consequence: a slow movement and a fast flick use the same factor, crossing a wide desktop takes more physical travel, raising DPI is the usual answer, and adaptive is normally better on a touchpad. The record also never told the reader how to confirm the change took, so a step 7 now gives `hyprctl configerrors` and the `getoption` before-and-after values measured here, with the caveat that `getoption` is global only and a per-device override cannot be read back that way. Severity and frequency held at medium and very-common, and the cause was correct on every point, so it is reissued only to add the Omarchy facts and the cost of flat. Sources: the two raw wiki URLs the record cited have moved in the hyprland-wiki tree, so I retrieved the current paths (`content/configuring/core/config-options.md` and `content/configuring/core/devices.md`) and added them, along with libinput's pointer-acceleration page and the quattro-branch Omarchy files. Removed the `raw.githubusercontent.com/basecamp/omarchy/dev/config/hypr/input.lua` URL: it still 200s through the rename redirect, but the repo is `omacom/omarchy` now and `dev` is not the branch Omarchy 4 ships, so the quattro URL replaces it. Kept hyprwm/Hyprland#7088 with lower weight: it resolves and it does show a user whose global sensitivity did nothing and whose per-device block worked, but it is from July 2024 and v0.41.2, predates the Lua config, and was closed in a bulk move to discussions rather than resolved. It is a symptom report, not evidence for 0.56 behaviour. NOT exercised: nothing was written, and no reload, eval, keyword or dispatch was run, because this is the operator's live graphical session with the mouse in use. There is no touchpad on this machine (`hyprctl -j devices` reports an empty touch list), so every touchpad claim comes from the wiki, from Omarchy's packaged input.lua and from InputManager.cpp, not from hardware. Neither `accel_profile = "flat"` nor the custom curve was applied here, so their feel is reported from the documentation only.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `force_no_accel` is documented as not recommended because it can desynchronise the cursor from real pointer position. Prefer `accel_profile = "flat"`.

**Fix.**

**1. Know what you are trading before you turn acceleration off.** libinput's default profile on every device is `adaptive`, which scales the pointer with how fast you move. `flat` is "a constant factor applied to all device deltas, regardless of the speed of motion". That is what you want for aiming, and the cost is that a slow careful movement and a fast flick now use the same factor, so crossing a wide desktop takes more physical travel. The usual answer is to raise the mouse's own DPI rather than the sensitivity. On a touchpad, where physical travel is small, `adaptive` is usually the better choice, which is one more reason to scope this per device.

**2. On Omarchy 4 the lines are already in the file, commented out.** `~/.config/hypr/input.lua` ships as one fully commented-out `hl.config` block that already contains `accel_profile` and `sensitivity`. Uncomment only those two lines and the `hl.config({ input = { ... } })` structure around them. Do not uncomment the whole block: it also carries `kb_layout = "us,dk,eu"` and a `kb_options` string, and `kb_options` replaces rather than merges, so uncommenting it silently drops Omarchy 4's `compose:caps,shift:both_capslock_cancel`.

```lua
-- ~/.config/hypr/input.lua
hl.config({
  input = {
    -- Turn off mouse acceleration (libinput default: adaptive).
    accel_profile = "flat",

    -- Clamped to -1.0 .. 1.0. Omarchy 4 already sets 0 in
    -- /usr/share/omarchy/default/hypr/input.lua, so leaving this at 0 changes
    -- nothing and is easy to mistake for a failed edit.
    sensitivity = 0.35,
  },
})
```

Omarchy 4 sets `sensitivity = 0` and never sets `accel_profile`, so the acceleration you are fighting is libinput's own default and not something Omarchy chose.

**Plain Hyprland 0.55 or newer**: the same block goes in `~/.config/hypr/hyprland.lua`.

**Hyprland 0.54 and older only** (hyprlang, `~/.config/hypr/hyprland.conf`). Omarchy 4 never ships this:

```
input {
    accel_profile = flat
    sensitivity = 0.0
}
```

Apply with `hyprctl reload`.

**3. Try values live before committing them.** On 0.55 and newer:

```bash
hyprctl eval 'hl.config({ input = { accel_profile = "flat", sensitivity = -0.3 } })'
```

`hyprctl keyword input:accel_profile flat` is the 0.54-and-older form. On 0.56 the Lua parser refuses it with "keyword can't work with non-legacy parsers", so do not copy it from an older guide.

**4. Scope it per device so the touchpad is not collateral damage.** Hyprland lowercases the libinput name and turns spaces into hyphens, so do not guess it. Print the exact strings:

```bash
hyprctl -j devices | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(m["name"]) for m in d["mice"]]'
```

Real names from a live Omarchy 4 machine: `razer-razer-basilisk-v3`, `corsair-corsair-gaming-k55-rgb-keyboard-1`.

```lua
-- flat and slower for the gaming mouse only
hl.device({
  name = "razer-razer-basilisk-v3",
  accel_profile = "flat",
  sensitivity = -0.4,
})

-- leave the touchpad on the adaptive curve, tune scroll separately
hl.device({
  name = "elan1200:00-04f3:30fe-touchpad",   -- your own name from hyprctl -j devices
  accel_profile = "adaptive",
  natural_scroll = true,
  scroll_factor = 0.4,
})
```

Touchpad options go in an `hl.device` block under their bare names, not under a nested `touchpad = { ... }` table. Hyprland resolves a per-device key by its bare name and picks the fallback by device type, so `natural_scroll` inside a touchpad's block falls back to `input.touchpad.natural_scroll` and inside a mouse's block to `input.natural_scroll`.

**5. If sensitivity is still not enough range**, do not fight the clamp. Change the mouse's own DPI, on the mouse itself or with `piper` and `libratbag` for supported mice, or define a custom curve. The form is `custom <step> <points...>`:

```lua
hl.config({ input = { accel_profile = "custom 200 0.0 0.5" } })
```

**6. Absolute last resort**, `force_no_accel = true` bypasses most pointer processing for the rawest possible signal. The wiki explicitly does not recommend it, because of cursor desynchronisation, and Hyprland reads it only from `input:force_no_accel`, so it cannot go inside an `hl.device()` block. It is all devices or nothing:

```lua
hl.config({ input = { force_no_accel = true } })
```

**7. Confirm the edit landed.** After `hyprctl reload`:

```bash
hyprctl configerrors
hyprctl getoption input:accel_profile
hyprctl getoption input:sensitivity
```

`accel_profile` reads `str: [[EMPTY]]` with `set: false` on a stock Omarchy 4 machine and must read `str: flat` with `set: true` once your edit is in force. `getoption` reports global values only, so a per-device override cannot be read back this way and has to be judged by feel.

**Verify.** `hyprctl configerrors` prints nothing after `hyprctl reload`. `hyprctl getoption input:accel_profile` returns `str: flat` with `set: true`, where a stock Omarchy 4 machine returns `str: [[EMPTY]]` with `set: false`. `hyprctl -j devices` lists each pointer with the exact name you matched on. Move the mouse slowly then quickly across the same physical distance: with `flat` the cursor travels the same screen distance both times. Confirm the touchpad still feels normal if you scoped the change with `hl.device()`. `getoption` reports global values only, so a per-device override cannot be read back that way.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Devices/> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Advanced%20and%20Cool/Devices.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Advanced%20and%20Cool/Using-hyprctl.md> · <https://github.com/hyprwm/Hyprland/issues/7088> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/config-options.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/devices.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/using-hyprctl.md> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/managers/input/InputManager.cpp> · <https://wayland.freedesktop.org/libinput/doc/latest/pointer-acceleration.html> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/input.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/input.lua>

---

## Make audio switch automatically to a headset or dock when you plug it in

`no-auto-switch-to-new-audio-device` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `bluetooth`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Plugging in a USB headset, a dock, or connecting a Bluetooth speaker does nothing — audio keeps coming out of the built-in speakers until you manually change the default. A common Omarchy report: "autoconnected bluetooth speaker doesn't play audio... i open the bluetooth menu, disconnect, connect again, audio works."

**Cause.** PipeWire's PulseAudio shim does not load `module-switch-on-connect` by default, unlike stock PulseAudio. Without it, a newly appearing sink never becomes the default, and already-running streams are never moved to it.

**Fix.**

Create the drop-in (user scope shown; use `/etc/pipewire/...` for system-wide):

```bash
mkdir -p ~/.config/pipewire/pipewire-pulse.conf.d
```

```conf
# ~/.config/pipewire/pipewire-pulse.conf.d/switch-on-connect.conf
pulse.cmd = [
    { cmd = "load-module" args = "module-switch-on-connect" }
]
```

Restart the shim:

```bash
systemctl --user restart pipewire-pulse.service
```

As a one-shot fallback for a device that is already connected:

```bash
pactl list short sinks
pactl set-default-sink <sink-name>
pactl list short sink-inputs
pactl move-sink-input <input-id> <sink-name>
```

**Verify.** `pactl list short modules | grep switch-on-connect` returns a line, and unplugging/replugging a USB headset moves the `*` in `wpctl status` automatically.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://github.com/basecamp/omarchy/issues/8231>

---

## Turn on touchpad tap-to-click, natural scrolling and palm rejection

`touchpad-tap-to-click-and-gestures-missing` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Fresh Hyprland/Omarchy install: the touchpad moves the cursor but tapping does nothing (you must physically press the pad), scrolling goes the "wrong" way, the pad fires clicks while you type, and three-finger swipes between workspaces don't work.

**Cause.** Hyprland's libinput defaults are conservative and its gesture bindings are opt-in. `tap_to_click` defaults on but `natural_scroll` is off, `clickfinger_behavior` is off, `drag_3fg` is off, and no gestures are bound unless you declare them.

**Fix.**

```lua
-- ~/.config/hypr/hyprland.lua
hl.config({
  input = {
    touchpad = {
      tap_to_click = true,
      tap_and_drag = true,
      drag_lock = 1,
      natural_scroll = true,
      disable_while_typing = true,
      scroll_factor = 0.4,
      middle_button_emulation = true,
      tap_button_map = "lrm",   -- 1/2/3 fingers = Left/Right/Middle
      drag_3fg = 1,             -- 1 = three-finger drag, 2 = four-finger
    },
  },
})

hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
hl.gesture({ fingers = 4, direction = "up",         action = "fullscreen" })
hl.gesture({ fingers = 3, direction = "down", mods = "ALT", action = "close" })
```

```bash
hyprctl reload
```

On Hyprland 0.54 and older the same settings live in a hyprlang `input { touchpad { ... } }` block with `gesture = 3, horizontal, workspace` lines.

To tune one specific pad, get its name and use a per-device block:

```bash
hyprctl devices
```

```lua
hl.device({ name = "elan1200:00-04f3:3090-touchpad", sensitivity = -0.2, natural_scroll = true })
```

**Verify.** `hyprctl getoption input:touchpad:tap_to_click` returns 1; a single-finger tap clicks, a three-finger horizontal swipe changes workspace, and typing does not generate stray clicks.

Sources: <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Gestures/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Devices/> · <https://wiki.archlinux.org/title/Libinput>

---

## Stop audio going out over HDMI instead of the speakers or headphone jack

`wrong-default-sink-audio-goes-to-hdmi` · severity: **medium** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Sound plays out of the wrong device — monitor speakers over HDMI/DisplayPort instead of the laptop speakers or the headphone jack, or out of a USB dock that isn't even plugged into speakers. Volume keys change the wrong device's volume.

**Cause.** WirePlumber picks the default sink by priority score, and HDMI/DisplayPort sinks on discrete GPUs frequently score higher than the analog codec. There is no desktop-environment sound applet on a bare Hyprland session to correct it, so the wrong default just sticks.

**Fix.**

List the nodes and note the numeric IDs:

```bash
wpctl status
```

The `Sinks:` block looks like this; the `*` marks the current default:

```
├─ Sinks:
│  *   51. Built-in Audio Analog Stereo        [vol: 0.60]
│      53. Built-in Audio Digital Stereo (HDMI) [vol: 1.00]
```

Set the one you want (WirePlumber remembers this across reboots in `~/.local/state/wireplumber/`):

```bash
wpctl set-default 51
wpctl set-volume @DEFAULT_AUDIO_SINK@ 50%
wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
```

If the device you want is not listed at all, its card is on the wrong profile — see `wpctl status` for the `Devices:` ID and switch profile:

```bash
wpctl set-profile 42 1     # analog
wpctl set-profile 42 3     # HDMI
```

For a GUI, install `pavucontrol` and set it on the *Output Devices* tab (green tick = default):

```bash
sudo pacman -S pavucontrol
```

**Verify.** `wpctl status` shows the `*` on the sink you chose, and it survives a reboot.

Sources: <https://wiki.archlinux.org/title/PipeWire> · <https://wiki.archlinux.org/title/WirePlumber>

---

## Fix audio crackling and stuttering when a second stream starts

`audio-crackling-underruns-multiple-streams` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Audio crackles, stutters, or cuts out — especially when a second stream starts (a Discord notification over music, a browser tab starting playback). `journalctl --user -u pipewire-pulse.service` shows lines like `pulse-server 0x...: [Nightly] UNDERFLOW channel:0 offset:370676 underrun:940` or `spa.alsa: front:0p: snd_pcm_avail after recover: Broken pipe`.

**Cause.** The ALSA buffer/headroom PipeWire requests is too small for the device or the scheduling latency of the machine, so the ring buffer underruns each time a new stream forces a re-negotiation of the graph quantum.

> **Audit corrected this record.** The configuration in this record is right and the defect class the re-audit was hunting is absent. On this workstation, pipewire 1:1.6.8-1 and wireplumber 0.5.15-1, the drop-in path `~/.config/wireplumber/wireplumber.conf.d/` is a real directory that Omarchy itself writes into (`/usr/share/omarchy/install/user/hardware/asus/fix-audio-mixer.sh` copies a drop-in there), not a symlink into /usr/share, and it is not a superseded full-file override. Both property names exist in the shipped ALSA plugin: `strings /usr/lib/spa-0.2/alsa/libspa-alsa.so` lists `api.alsa.period-size` and `api.alsa.headroom`. WirePlumber 0.5.15 ships the very same stanza at `/usr/share/wireplumber/wireplumber.conf.d/alsa-vm.conf`, using `monitor.alsa.rules` with `api.alsa.period-size = 1024` and headroom 2048 or 8192, so the key name and the values are upstream's own. The Arch wiki section 'Audio cutting out when multiple streams start playing' and the upstream PipeWire troubleshooting wiki both still carry this exact fix with the exact UNDERFLOW line the symptom quotes. What was wrong is Omarchy specialisation. The restart line restarts only `pipewire.service` and `wireplumber.service`, which leaves `pipewire-pulse.service` untouched even though `pipewire-pulse` is what logs the underrun, and Omarchy ships `omarchy-restart-audio` (`omarchy restart audio`) which restarts all three and then recovers a USB audio device left in `SETUP`. I read that script rather than running it. Second, `rtkit` is not installed and is not in `omarchy-base.packages` or `omarchy-other.packages`, so `libpipewire-module-rt` has no RTKit bus to fall back to and `realtime-privileges` is the only path on Omarchy, which makes that half of the fix more load-bearing here, not less. I also confirmed by reading `/usr/bin/omarchy-update-pacman-guard` that the ALPM guard aborts only when both `-S` and `-u` are present, so `sudo pacman -S realtime-privileges` is allowed and is not a defect. Finally I checked the quantum names the fix might escalate to and kept them straight: the daemon reads `default.clock.quantum`, `default.clock.min-quantum` and `default.clock.max-quantum` from `/usr/share/pipewire/pipewire.conf`, while the pulse server reads `pulse.min.quantum`, `pulse.min.req` and `pulse.default.req` from `/usr/share/pipewire/pipewire-pulse.conf`, and the record correctly does not mix them. NOT exercised: I did not write the drop-in, did not restart any audio unit and did not install `realtime-privileges`, so the readback of the properties after the drop-in applies is unverified. `pw-dump` on this machine shows the property names in the node param list but no value, so I did not publish it as a verify step.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Larger period-size/headroom adds output latency — noticeable if you do low-latency music production or competitive gaming. Halve the values if latency becomes a problem.

**Fix.**

The configuration is identical on Omarchy 4 and plain Arch, because both run PipeWire 1.6.8 and WirePlumber 0.5.15 and both read the same drop-in directory. Only the restart differs.

Add a WirePlumber drop-in. This is a drop-in directory, not a full-file override, so it survives a WirePlumber upgrade:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

```conf
# ~/.config/wireplumber/wireplumber.conf.d/alsa-config.conf
monitor.alsa.rules = [
  {
    matches = [
      { node.name = "~alsa_output.*" }
    ]
    actions = {
      update-props = {
        api.alsa.period-size   = 1024
        api.alsa.headroom      = 8192
      }
    }
  }
]
```

Then restart audio.

On Omarchy 4, use the shipped command. It restarts `pipewire.service`, `pipewire-pulse.service` and `wireplumber.service` together, and if PipeWire still does not answer it resets a USB audio device left stuck in `SETUP`:

```bash
omarchy restart audio
```

On plain Arch, restart all three yourself. Restarting only `pipewire.service` and `wireplumber.service` leaves `pipewire-pulse.service` on its old connection, and `pipewire-pulse` is the process that logs the `UNDERFLOW`:

```bash
systemctl --user restart pipewire.service pipewire-pulse.service wireplumber.service
```

Realtime priority is a second, independent cause of the same symptom. Omarchy does not install `rtkit`, so PipeWire's `libpipewire-module-rt` has no RTKit bus to fall back to and depends entirely on the rlimits that `realtime-privileges` grants. If `journalctl --user -u pipewire.service` shows `RTKit error: org.freedesktop.DBus.Error.AccessDenied`, or `Failed to mlock memory ... consider increasing RLIMIT_MEMLOCK`:

```bash
sudo pacman -S realtime-privileges
sudo gpasswd -a "$USER" realtime
```

Log out and back in for the group to take effect. Omarchy's ALPM guard aborts only a transaction carrying both `-S` and `-u`, so a plain `pacman -S` is allowed. If the sync databases are stale, run `omarchy update` first. Never use `pacman -Sy <pkg>`, which is a partial upgrade.

Two things to know before reaching further:

* Inside a virtual machine you do not need this drop-in at all. WirePlumber already ships the same stanza at `/usr/share/wireplumber/wireplumber.conf.d/alsa-vm.conf` for PCI audio under any hypervisor.
* If you escalate to quantum settings, those are PipeWire daemon settings rather than WirePlumber ones, and the daemon and the Pulse server use different names for them. The daemon reads `default.clock.quantum`, `default.clock.min-quantum` and `default.clock.max-quantum` from `~/.config/pipewire/pipewire.conf.d/`. The Pulse server reads `pulse.min.quantum`, `pulse.min.req` and `pulse.default.req` from `~/.config/pipewire/pipewire-pulse.conf.d/`. Setting one and expecting the other to move is the usual dead end.

Watch it live with `pw-top`. The `ERR` column is the underrun counter.

**Verify.** `pw-top` shows the `ERR` column staying at 0 while music plays and a notification fires, and no new `UNDERFLOW` lines appear in `journalctl --user -u pipewire-pulse.service -f`. Confirm the drop-in was parsed rather than skipped, because a WirePlumber file with a syntax error is ignored and the symptom then does not change: `journalctl --user -u wireplumber.service -b | grep -iE 'parse|invalid'` should print nothing.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://gitlab.freedesktop.org/pipewire/pipewire/-/wikis/Troubleshooting>

---

## Fix Bluetooth music stuttering, skipping or sounding low-bitrate

`bluetooth-audio-stutters-codec` · severity: **medium** · frequency: **common** · applies to: `arch`, `bluetooth`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Bluetooth music stutters, skips, or sounds "muddy" and low-bitrate, especially when you walk a few metres away or when a Bluetooth mouse is also connected. `systemctl --user status pipewire` shows lines like `pipewire[249297]: (bluez_input.18:54:CF:04:00:56.a2dp-sink-60) client too slow! rate:512/48000 pos:370688 status:triggered`.

**Cause.** The negotiated A2DP codec/bitrate is too aggressive for the link quality, or 2.4 GHz congestion (Wi-Fi, BT mouse/keyboard sharing the radio) is starving the stream. `client too slow!` means PipeWire could not fill the Bluetooth transport buffer in time.

**Fix.**

Check which codec is in use:

```bash
pactl list sinks | grep -i codec
```

Pin a more robust codec set — SBC-XQ gives noticeably better quality than plain SBC at similar robustness:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

```conf
# ~/.config/wireplumber/wireplumber.conf.d/bluez-config.conf
monitor.bluez.properties = {
  bluez5.enable-sbc-xq = true
  bluez5.enable-msbc = true
  bluez5.codecs = [ sbc sbc_xq ]
}
```

```bash
systemctl --user restart pipewire.service wireplumber.service
```

Reconnect the headphones. Valid values for `bluez5.codecs` are `sbc sbc_xq aac ldac aptx aptx_hd` — if you have LDAC hardware and the link is strong, try `[ ldac aac sbc_xq sbc ]` instead; if it still stutters, fall back to `[ sbc_xq sbc ]`.

Also disable node suspension for Bluetooth (see the pop/crack record) and move your 2.4 GHz Wi-Fi to 5 GHz if you can.

**Verify.** `pactl list sinks | grep -i codec` shows the codec you selected, and `journalctl --user -u pipewire -f` stays free of `client too slow!` during a full song.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://wiki.archlinux.org/title/Bluetooth_headset>

---

## Bluetooth off at every boot, slow to reconnect, and no headset battery level

`bluetooth-main-conf-autoenable-fastconnectable-experimental` · severity: **medium** · frequency: **common** · applies to: `arch`, `bluetooth`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Three complaints that all trace back to the same file. (1) Bluetooth is dead after every boot — `bluetoothctl show` prints `Powered: no` and you have to run `power on` by hand or toggle it in the bar every single time. (2) Your headset or mouse takes 10-30 seconds to reconnect when you turn it on, where Windows reconnects near-instantly. (3) The headphones connect fine but their battery level never appears anywhere — `upower -d` shows no percentage and the bar shows nothing.

**Cause.** `/etc/bluetooth/main.conf` governs adapter power-on, reconnect behaviour and which BlueZ features are exposed, and its shipped defaults are conservative. `[Policy] AutoEnable` defaults to true since bluez 5.65, but a stale `AutoEnable=false` left over from an old guide (or a persistent rfkill soft block) keeps the adapter down. `[General] FastConnectable` defaults to false, which leaves the page-scan interval long and makes peripheral-initiated reconnection slow. Battery reporting for most headsets is served over BlueZ's D-Bus *experimental* interfaces, which are off unless `Experimental = true` is set — so upower and every bar widget that reads it has nothing to show. Separately, `[General] ControllerMode` defaults to `dual`, and BR/EDR-only devices sometimes fail to associate until it is forced to `bredr`.

> **Audit corrected this record.** The main.conf content is unusually accurate — I checked every key against bluez master src/main.conf and each one is in the section the record puts it in: [General] holds Class (0x000100), DiscoverableTimeout, ControllerMode (default dual), FastConnectable (default false), Experimental (default false), KernelExperimental (default false); [Policy] holds ReconnectAttempts (7), ReconnectIntervals (1,2,4,8,16,32,64), AutoEnable (default true), ResumeDelay (2). The Arch Bluetooth page confirms the AutoEnable history exactly — "As of bluez 5.65, BlueZ' default behavior is to power on all Bluetooth adapters when starting the service or resuming from suspend" — the ControllerMode=bredr fallback for BR/EDR-only devices, the DiscoverableTimeout=0 recipe, and that battery reporting for headsets rides on the D-Bus experimental interfaces ("enabling D-Bus experimental interfaces currently allows to report battery level for old headsets"). The `--experimental` drop-in and /usr/lib/bluetooth/bluetoothd path are right, as is the rfkill escalation. ONE defect, in the Omarchy paragraph: `omarchy-restart-bluetooth` does exist and *is* reachable at Update > Hardware > Bluetooth in bin/omarchy-menu, but its entire body is `rfkill unblock bluetooth; rfkill list bluetooth` — it never touches bluetooth.service. So the record's advice to use it "after changing this file rather than fighting the daemon by hand" is backwards: it will not reload main.conf, and the user will conclude their edit did nothing. (Minor: the text refers to "the danger note" about the pacman-owned file, but no such note is in the record — pacman lists main.conf in bluez's backup array, so edits survive upgrades and land as .pacnew, which is worth stating instead.)
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `/etc/bluetooth/main.conf` is owned by the `bluez` package, so editing it means every bluez upgrade drops a `main.conf.pacnew` next to it and your settings silently stop matching upstream defaults. Run `pacdiff` (from `pacman-contrib`) after upgrades and merge. `Experimental` and `KernelExperimental` deliberately turn on code paths BlueZ has not declared stable — if pairing or audio becomes flaky after enabling them, they are the first thing to revert. `FastConnectable = true` increases idle power consumption, which matters on a laptop. Setting `ControllerMode = bredr` disables Bluetooth LE entirely, which will break LE-only peripherals (many modern mice, trackers and keyboards).

**Fix.**

Replace the Omarchy paragraph with:

**On Omarchy**, still apply the change with `sudo systemctl restart bluetooth.service`. The menu item *Update > Hardware > Bluetooth* runs `omarchy-restart-bluetooth`, which despite the name only does `rfkill unblock bluetooth` and prints `rfkill list bluetooth` — it does not restart bluetoothd and will not pick up a changed `main.conf`. Use it for the rfkill-soft-block case (the escalation later in this record), not for config changes:

```bash
sudo systemctl restart bluetooth.service
bluetoothctl show          # confirm Powered: yes and the new settings took
```

Also replace the "see the danger note" aside with the accurate statement: `/etc/bluetooth/main.conf` is owned by the `bluez` package but is listed in its `backup` array, so your edits are preserved across upgrades and a changed upstream default arrives as `/etc/bluetooth/main.conf.pacnew` — merge it with `pacdiff` after a bluez update rather than assuming your file is current.

**Verify.** `bluetoothctl show` reports `Powered: yes` immediately after a cold boot with no manual intervention. `busctl --system introspect org.bluez /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX | grep -i battery` shows the Battery1 interface once Experimental is on. `upower -i` on the headset device prints a `percentage:` line. Time a reconnect before and after `FastConnectable = true`.

Sources: <https://wiki.archlinux.org/title/Bluetooth> · <https://raw.githubusercontent.com/bluez/bluez/master/src/main.conf>

---

## Get CJK input working in Electron and XWayland apps under Hyprland

`fcitx5-cjk-input-not-working-wayland` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Ctrl+Space does nothing and Chinese/Japanese/Korean input is impossible, or it works in some apps but not others — typically dead in Electron/Chromium and XWayland apps while working in native Wayland ones. The candidate popup may also fail to appear at all.

**Cause.** On Wayland, native clients use the `text-input` protocol and need no environment variables, but XWayland and toolkit-specific clients still need the legacy IM-module env vars. Version mismatches (Chromium defaults to `text-input-v1` while most compositors implement `v3`) break it further, and fcitx5 must actually be autostarted.

> **Audit corrected this record.** The diagnosis is accurate and most of it is wiki-sourced: fcitx5-im is confirmed a real package GROUP (fcitx5, fcitx5-configtool, fcitx5-gtk, fcitx5-qt - exactly the four the record names), fcitx5-chinese-addons and fcitx5-mozc exist in extra, and `chromium --wayland-text-input-version=3` is verbatim from Arch Fcitx5 line 41 along with the v1-vs-v3 mismatch explanation. The defect is a fabricated API call: `hl.exec_once()` does not exist in Hyprland's Lua config. I grepped the entire wiki content tree - there is no hl.exec_once anywhere. Autostart.md documents autostart exclusively as hl.on("hyprland.start", ...) with hl.exec_cmd(). Pasting hl.exec_once will throw a Lua error that kills execution of the rest of that config file, so it breaks more than just the IME.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

```bash
sudo pacman -S --needed fcitx5-im fcitx5-chinese-addons fcitx5-mozc
```

Set the env vars for XWayland/toolkit clients. On Omarchy the session is started by uwsm, and the Hyprland wiki explicitly says uwsm users should NOT put env vars in hyprland.lua - use `~/.config/uwsm/env` with `export KEY=VAL`:

```sh
# ~/.config/uwsm/env
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export SDL_IM_MODULE=fcitx
```

Only if you are NOT using uwsm, the Hyprland equivalent is `hl.env("GTK_IM_MODULE", "fcitx")` etc. Note that setting GTK_IM_MODULE/QT_IM_MODULE globally also diverts native Wayland apps off the text-input protocol; the Arch wiki recommends scoping them to XWayland apps where you can.

Autostart the daemon - `hl.exec_once()` does NOT exist and will throw a Lua error that kills the rest of that config file. Use the documented form:

```lua
-- ~/.config/hypr/hyprland.lua
hl.on("hyprland.start", function()
  hl.exec_cmd("fcitx5 -d")
end)
```

On Hyprland 0.54 and older the hyprlang equivalents are `env = GTK_IM_MODULE,fcitx` and `exec-once = fcitx5 -d`.

Log out and back in, then configure input methods with `fcitx5-configtool`, and run `fcitx5-diagnose` when something still does not work. For Chromium/Electron apps on the wrong protocol version, launch with `chromium --wayland-text-input-version=3`.

**Verify.** `fcitx5-diagnose` reports no errors for your frontends, and Ctrl+Space switches input methods with a working candidate popup in both a native Wayland terminal and an XWayland app.

Sources: <https://wiki.archlinux.org/title/Fcitx5>

---

## Make the fingerprint reader authenticate sudo, polkit and the lock screen

`fingerprint-reader-not-used-for-login-sudo` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** The fingerprint reader is listed by `lsusb` and `fprintd-enroll` works, but nothing ever asks for a fingerprint — `sudo`, the lock screen and polkit prompts all still demand a password. Or `fprintd-enroll` fails with `EnrollStart failed: GDBus.Error:net.reactivated.Fprint.Error.PermissionDenied: Not Authorized: net.reactivated.fprint.device.enroll`.

**Cause.** `fprintd` only provides the D-Bus service; nothing uses it until `pam_fprintd.so` is added to the relevant PAM stacks. Enrolment itself needs a running polkit authentication agent — on a bare Hyprland session there often isn't one, which produces the PermissionDenied error.

> **Audit corrected this record.** Every command and PAM snippet is sourced correctly - the pam_unix/pam_fprintd sufficient pair, the system-local-login stanza, the enrol-all-fingers brace-expansion loop and the polkit 50-default.rules copy are all verbatim from Arch Fprint (lines 52-95 and 165-178). But the wiki carries an explicit warning immediately above the stanza this record reproduces, and the record drops it: 'This setting (fingerprint-only authentication) is a security breach if used for su, polkit, or sudo as it allows background processes to obtain permissions without prompting the user for a fingerprint (via fingerprint hijacking). See CVE-2024-37408.' Handing a user a /etc/pam.d/sudo edit with no mention of that, and no mention that a typo in that file locks them out of sudo entirely, is dangerous-without-warning. `nullok` is also carried over unnecessarily and permits empty passwords.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Adding `pam_fprintd.so` as `sufficient` to `sudo`/`su`/polkit is a documented security weakness (CVE-2024-37408): a background process can obtain elevated permissions when you touch the reader for something else. Editing PAM incorrectly can lock you out of the system entirely — keep a root TTY or a live USB open while you test, and never edit `/etc/pam.d/system-auth` without a second session already logged in.

**Fix.**

WARNING before you touch PAM: fingerprint-only authentication for sudo, su or polkit is a security weakness - a background process can obtain elevated permissions without you being prompted to touch the sensor (fingerprint hijacking, CVE-2024-37408). If that matters to you, add pam_fprintd to the graphical login stack only and leave sudo on passwords.

WARNING before editing /etc/pam.d/sudo: a syntax error there locks you out of sudo. Keep a second terminal with an active root shell open (`sudo -i`) until you have verified the change works in a THIRD terminal.

Install and check the reader:

```bash
sudo pacman -S --needed fprintd usbutils
lsusb
systemctl status fprintd.service
```

Enrol (as root if no polkit agent is running):

```bash
sudo fprintd-enroll "$USER"
fprintd-verify
```

Enrol several fingers:

```bash
fprintd-delete "$USER"
for finger in {left,right}-{thumb,{index,middle,ring,little}-finger}; do
  fprintd-enroll -f "$finger" "$USER"
done
```

For local graphical login, add to the top of the auth section of `/etc/pam.d/system-local-login`:

```
auth      sufficient  pam_fprintd.so
auth      include     system-login
```

Only if you accept the CVE-2024-37408 risk above, for `sudo` - note `nullok` is dropped, it permits empty passwords and is not needed here:

```
# /etc/pam.d/sudo
auth      sufficient  pam_unix.so try_first_pass likeauth
auth      sufficient  pam_fprintd.so
auth      include     system-auth
```

This prompts for a password first; pressing Enter on a blank field falls through to the fingerprint. If you need both prompts simultaneously (some GTK polkit agents reject blank input), use `pam-fprint-grosshack` from the AUR instead.

If fingerprint works for login and sudo but not polkit prompts:

```bash
sudo cp /usr/share/polkit-1/rules.d/50-default.rules /etc/polkit-1/rules.d/
```

then edit the returned group in that copy to match your admin group (`unix-group:wheel` on Arch).

**Verify.** `fprintd-verify` succeeds, and running `sudo -k; sudo true` in a terminal prompts for a fingerprint (pressing Enter on the empty password field falls through to the reader).

Sources: <https://wiki.archlinux.org/title/Fprint>

---

## Game controller pairs or plugs in but no game sees any input

`gamepad-not-detected-or-no-input` · severity: **medium** · frequency: **common** · applies to: `arch`, `bluetooth`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** An Xbox or generic USB controller shows up in `lsusb` (or pairs successfully in `bluetoothctl`) but nothing responds to it. Common variants: `ls /dev/input/js*` returns `No such file or directory`; the pad works in Steam Big Picture but not in the game; the buttons are all mapped wrong and the triggers act like buttons; an Xbox Wireless controller over Bluetooth enters an endless connect/disconnect loop; the Xbox Wireless Adapter dongle appears in `lsusb` but no controller ever binds to it.

**Cause.** Four separate causes wear the same symptom. (1) In-kernel `xpad` only supports Xbox controllers over USB — over Bluetooth an Xbox One S/Series pad is handled by `hid-generic`, which gives wrong mappings, no rumble and no battery, and on stock firmware often loops connect/disconnect. (2) The Microsoft Xbox Wireless Adapter dongle has no in-kernel driver at all; it needs the out-of-tree `xone` driver plus its firmware blob. (3) Device permissions: udev must grant your user access to the `/dev/input/event*` and `hidraw` nodes, and if no installed package ships a rule for your pad, it is simply not readable. (4) The pad is fine but the game is using a different API than the one you tested (legacy joydev `/dev/input/js*` vs evdev vs SDL).

> **Audit corrected this record.** Most of this is faithfully and precisely sourced — but the last section does not work on the platform this record targets. Verified good: joyutils (extra 1.8.1, ships jstest — the wiki names exactly this package), linuxconsole (extra, fftest/evdev-joystick), evtest (extra), usbutils; xpadneo-dkms 0.10.4, xone-dkms 0.5.8, xone-dongle-firmware 2.0.0, game-devices-udev all live in the AUR; the xone-dkms PKGBUILD really does `install -Dm644 install/modprobe.conf "$pkgdir/usr/lib/modprobe.d/xone-blacklist.conf"`, so the blacklist path and the mandatory reboot are exactly right. The permissions section quotes the wiki's grep, the systemd 664/input-group default and the Steam Controller workaround verbatim (/usr/lib/udev/rules.d/70-steam-controller.rules → /etc/udev/rules.d/99-steam-controller-perms.rules, MODE 0660→0666). Three defects: (1) The final /etc/X11/xorg.conf.d/51-joystick.conf block is presented as the fix "for XWayland apps" — that is wrong. XWayland takes its input from the Wayland compositor and does not read xorg.conf.d InputClass sections at all, so on Hyprland/Omarchy (every tag on this record) the file is inert. It also needs `Driver "joystick"` from xf86-input-joystick, which is NOT in the repos (AUR only, 1.6.4-5) and is unmentioned. (2) `[GATT] ReconnectIntervals=1,1,2,3,5,8,13,21,34,55` — the Arch Bluetooth page really does print it under [GATT], but bluez's own src/main.conf defines ReconnectIntervals (and ReconnectAttempts, AutoEnable, ResumeDelay) under [Policy]; under [GATT] it is parsed as an unknown key and ignored. (3) `sudo pacman -S steam-devices` fails on a box without multilib — steam-devices is multilib/1.0.0.87, not extra.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** xpadneo-dkms and xone-dkms are DKMS modules: they must rebuild against every new kernel. If `linux-headers` (or `linux-lts-headers`, matching your installed kernel) is missing at upgrade time, the build fails silently during the pacman hook and the controller stops working after the next reboot. Keep the matching headers package installed, and check `dkms status` after a kernel upgrade.

**Fix.**

Three changes.

**1. Replace the "cursor moves when you push the stick" section.** The xorg.conf.d snippet only works under a real X server; XWayland ignores xorg.conf.d entirely, so it does nothing on Hyprland. On Wayland the fix is:

```bash
# Steam: Settings > Controller > turn OFF "Enable Steam Input for desktop configuration"
# or make the pad's evdev node invisible as a pointer, per-device:
sudo tee /etc/udev/rules.d/60-joystick-not-a-pointer.rules >/dev/null <<'EOF'
SUBSYSTEM=="input", ATTRS{name}=="*Controller*", ENV{ID_INPUT_MOUSE}="", ENV{ID_INPUT_POINTINGSTICK}=""
EOF
sudo udevadm control --reload && sudo udevadm trigger
```

Reconnect the pad. Only keep the xorg.conf.d block if you are actually running Xorg, and note it needs the AUR package `xf86-input-joystick` (it is not in the repos) for `Driver "joystick"` to resolve.

**2. Fix the main.conf section headers.** `ReconnectIntervals` is a `[Policy]` key in bluez, not `[GATT]` (the Arch wiki misfiles it):

```ini
# /etc/bluetooth/main.conf
[General]
JustWorksRepairing = always
FastConnectable = true
Class = 0x000100

[Policy]
AutoEnable = true
ReconnectAttempts = 7
ReconnectIntervals = 1,1,2,3,5,8,13,21,34,55
```

```bash
sudo systemctl restart bluetooth.service
```

**3. steam-devices is in multilib.** Enable the `[multilib]` repo in `/etc/pacman.conf` first, or use the broad AUR alternative:

```bash
sudo pacman -Syu steam-devices      # requires [multilib]
yay -S game-devices-udev            # no multilib needed
```

Also worth adding for the older Xbox 360 pad over Bluetooth, which this record omits: add the kernel parameter `bluetooth.disable_ertm=1`. And per the wiki, the most reliable cure for an Xbox One S pairing loop is to pair it once in Windows using the *same* Bluetooth adapter before pairing under Linux.

**Verify.** As your normal user (not root), `evtest` shows button and axis events. `jstest /dev/input/js0` prints changing axis values. Open https://gamepad-tester.com/ in Chromium and confirm the pad appears with working buttons. For xpadneo, `cat /sys/class/power_supply/*/capacity` reports the controller's battery level — proof the right driver bound rather than hid-generic.

Sources: <https://wiki.archlinux.org/title/Gamepad> · <https://wiki.archlinux.org/title/Bluetooth> · <https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=xone-dkms> · <https://github.com/atar-axis/xpadneo/>

---

## Get audio out of an HDMI or DisplayPort monitor that offers none

`hdmi-displayport-audio-no-output` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Monitor or TV connected over HDMI/DisplayPort shows no audio option, or the HDMI sink exists in `wpctl status` but selecting it gives silence. Common on desktops with a discrete GPU and on laptops docked over USB-C.

**Cause.** HDA cards expose analog and digital outputs as *mutually exclusive card profiles* — if the card sits on the analog profile the HDMI PCM is never created. Separately, HDMI performs a handshake on cable connect: a sink that was connected while no audio stream was present may have disabled its audio decoder.

**Fix.**

Find the card device ID and switch its profile:

```bash
wpctl status
# Devices:
#      42. HD Audio Controller                 [alsa]
wpctl set-profile 42 3      # try successive indices until the HDMI sink appears
wpctl status
```

Then make it the default:

```bash
wpctl set-default <hdmi-sink-id>
```

Test the raw ALSA path to separate a PipeWire problem from a hardware/handshake problem — get card and device numbers from `aplay -l`:

```bash
aplay -l
# card 1: Generic [HD-Audio Generic], device 3: HDMI 0 [HDMI 0]
aplay -D plughw:1,3 /usr/share/sounds/alsa/Front_Center.wav
```

If `aplay` reports no error but you hear nothing, power-cycle the monitor/TV/AV receiver, or unplug and replug the HDMI cable *while audio is playing*, so the handshake happens with a live stream.

On Hyprland, also make sure the output is actually enabled:

```bash
hyprctl monitors
```

**Verify.** `wpctl status` shows the HDMI sink with a `*`, and `speaker-test -D plughw:1,3 -c2 -twav -l1` plays through the display.

Sources: <https://wiki.archlinux.org/title/PipeWire> · <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting>

---

## People on calls hear your keyboard, fan, and an echo of themselves

`mic-noise-suppression-echo-cancellation-pipewire` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** On Zoom, Google Meet, Discord or Teams, everyone complains that they can hear your mechanical keyboard, your laptop fan, and room hiss whenever you are not speaking. Worse, when you use speakers instead of headphones, the other side hears their own voice bounced back at them half a second later. The same machine was fine under Windows or macOS. Nothing in the Omarchy audio menu, `wpctl status` or `pactl list` offers a noise suppression or echo cancellation switch, and Omarchy 4 does not install `pavucontrol` either.

**Cause.** PipeWire performs no DSP on capture streams by default — what the microphone hears is what the app gets. `module-echo-cancel` exists but is not loaded unless you write a drop-in for it. The browser-side WebRTC AEC that handles this on other platforms is frequently bypassed on Linux (the app has to own both the capture and playback path for it to work), and on Wayland screen/audio capture paths it often does not engage at all. Neither GNOME nor KDE ships a toggle for it either, so nothing on an Arch/Hyprland box will do it for you.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, pipewire and pipewire-pulse 1:1.6.8-1, wireplumber 0.5.15-1, kernel 7.1.9-arch1-2) and against the upstream pages. Everything technical in the record still holds on 1.6.8 and I confirmed it locally rather than from memory: `strings /usr/lib/spa-0.2/aec/libspa-aec-webrtc.so` contains all four keys the record sets (webrtc.high_pass_filter, webrtc.noise_suppression, webrtc.gain_control, webrtc.voice_detection), `strings /usr/lib/pipewire-0.3/libpipewire-module-echo-cancel.so` contains library.name, node.latency, monitor.mode, aec.args and all four props blocks, and docs.pipewire.org/page_module_echo_cancel.html now renders as PipeWire 1.6.8 with an example matching the record arg for arg. The module ships in pipewire-audio 1:1.6.8-1 (pacman -Qo). noise-suppression-for-voice is extra 1.21-1, not flagged out of date, and its file list carries usr/lib/ladspa/librnnoise_ladspa.so. swh-plugins 0.4.17-7 and easyeffects 8.2.8-1 are also in extra. The label noise_suppressor_mono and all three control names match werman's README verbatim, and both version footnotes match the Arch PipeWire page verbatim. The record's own structure already separates the three symptoms correctly, so that check passed: part A is echo and says both the source and the sink must be routed through the module, part B is keyboard, fan and hiss and is source side only. Three Omarchy 4 facts are missing and they are why this is corrected rather than ok. First, the record hosts the RNNoise chain in ~/.config/pipewire/pipewire.conf.d/. That still loads on 1.6.8, but PipeWire 1.6 ships /usr/share/pipewire/filter-chain/source-rnnoise.conf whose header says to copy it into ~/.config/pipewire/filter-chain.conf.d/ and run `pipewire -c filter-chain.conf`, and Omarchy's own speaker tuning migrated off the daemon drop-in for a stated reason I read in /usr/share/omarchy/default/systemd/user/omarchy-speaker-tuning.service: a malformed tuning breaks only that client, where a bad drop-in in the daemon config stops PipeWire from starting at all. /usr/share/pipewire/filter-chain.conf confirms it merges ~/.config/pipewire/filter-chain.conf.d/. Second, /usr/share/omarchy/bin/omarchy-audio-tuning refuses to install while EasyEffects is running and sets omarchy_speaker_tuning as the default sink, so the record's EasyEffects recommendation and its instruction to make the AEC sink the default both silently bypass a shipped tuning (/usr/share/omarchy/default/audio/tunings/dell-xps-2026/ is the one currently shipped). Third, Omarchy ships /usr/share/omarchy/bin/omarchy-restart-audio, which restarts the same three units and additionally recovers a stuck USB audio device, so it is the supported restart here. I also corrected the symptom: pavucontrol is not installed on Omarchy 4 and is owned by no package. I checked the ALPM guard at /usr/share/libalpm/hooks/00-omarchy-update-guard.hook and it triggers only on Operation = Upgrade, so the record's `pacman -S --needed` is not blocked, and I left it with a note about syncing first. NOT exercised: I changed nothing on this machine. No config was written, no filter chain was loaded, no service restarted and no default device moved, so neither half was run end to end here. noise-suppression-for-voice, swh-plugins and easyeffects are not installed, so the LADSPA label was confirmed from upstream and the package file list rather than from a loaded plugin. Live state read only: PulseAudio on PipeWire 1.6.8, default sink alsa_output.pci-0000_00_1f.3.analog-stereo, default source the USB Blue Yeti, no filter nodes present, and ~/.config/pipewire does not exist.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting a virtual sink as your system default means that if you later delete the config without resetting the default, apps chase a sink that no longer exists and you get silence. Reset with `wpctl set-default <real sink id>` before removing it. Echo cancellation also adds latency (default `node.latency` 1024/48000, about 21 ms), so do not leave it as the default output for music or gaming. A malformed drop-in under `~/.config/pipewire/pipewire.conf.d/` stops the PipeWire daemon from starting, which takes all audio with it. Recover by deleting the file and running `omarchy restart audio`. That is the reason part B is hosted as a `pipewire -c filter-chain.conf` client instead. On Omarchy, both an AEC sink set as default and EasyEffects will take playback off the shipped speaker tuning. Check `omarchy audio tuning status` first.

**Fix.**

There are three symptoms in the title and **two** independent fixes. Noise suppression is a filter on the source only. Echo cancellation needs the source *and* the sink, because the module can only subtract what it can see. Do not expect one config to do both.

**A. Echo (they hear themselves) - PipeWire's WebRTC AEC.** Create `~/.config/pipewire/pipewire.conf.d/20-echo-cancel.conf`:

```
context.modules = [
  { name = libpipewire-module-echo-cancel
    args = {
      # library.name  = aec/libspa-aec-webrtc
      # node.latency  = 1024/48000
      # monitor.mode  = false
      aec.args = {
        webrtc.high_pass_filter  = true
        webrtc.noise_suppression = true
        webrtc.gain_control      = false
        webrtc.voice_detection   = true
      }
      capture.props = {
        node.name = "Echo Cancellation Capture"
      }
      source.props = {
        node.name        = "Echo Cancellation Source"
        node.description = "Echo Cancelled Mic"
      }
      sink.props = {
        node.name        = "Echo Cancellation Sink"
        node.description = "Echo Cancelled Output"
      }
      playback.props = {
        node.name = "Echo Cancellation Playback"
      }
    }
  }
]
```

This one has to go in `pipewire.conf.d/`, because it loads into the daemon. The daemon reads that directory only at startup, so it needs a restart. On Omarchy use the shipped wrapper, which also recovers a USB audio device that hangs on the way down:

```bash
omarchy restart audio      # or: omarchy-restart-audio
```

On plain Arch:

```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
wpctl status
```

Both ends must go through the module, so set the new source as the default input **and** the new sink as the default output:

```bash
# take the IDs from `wpctl status`
wpctl set-default <id of Echo Cancellation Source>
wpctl set-default <id of Echo Cancellation Sink>
```

**On Omarchy, check `omarchy audio tuning status` before you touch the default sink.** If a speaker tuning is installed, `omarchy_speaker_tuning` is the default sink and every app is moved onto it. Making the Echo Cancellation Sink the default takes playback back off the tuned path. Turn the tuning off deliberately (`omarchy audio tuning off`) rather than leaving both half applied.

**B. Keyboard, fan and hiss - RNNoise filter chain.** Separate DSP, and it can be stacked with A.

```bash
sudo pacman -S --needed noise-suppression-for-voice swh-plugins
```

On Omarchy run `omarchy update` first if you have not synced recently. The ALPM guard only fires on an upgrade, so a plain `-S` of a new package is not blocked, but installing against a stale database is still how a partial upgrade starts. Never reach for `pacman -Sy`.

PipeWire 1.6 ships a worked example of this chain at `/usr/share/pipewire/filter-chain/source-rnnoise.conf`, and its own header tells you where it belongs. **Host it as a filter-chain client, not as a daemon drop-in.** A malformed fragment under `filter-chain.conf.d/` breaks only that client. The same mistake under `pipewire.conf.d/` stops the audio daemon from starting at all, which is why Omarchy's speaker tuning moved out of `pipewire.conf.d/` and runs its own `pipewire -c` client instead.

```bash
mkdir -p ~/.config/pipewire/filter-chain.conf.d
```

Create `~/.config/pipewire/filter-chain.conf.d/99-input-denoising.conf`:

```
context.modules = [
{   name = libpipewire-module-filter-chain
    flags = [ nofail ]
    args = {
        node.description = "Noise Canceling source"
        media.name       = "Noise Canceling source"
        filter.graph = {
            nodes = [
                {
                    type   = ladspa
                    name   = rnnoise
                    plugin = librnnoise_ladspa
                    label  = noise_suppressor_mono
                    control = {
                        "VAD Threshold (%)"          = 50.0
                        "VAD Grace Period (ms)"      = 200
                        "Retroactive VAD Grace (ms)" = 0
                    }
                }
            ]
        }
        capture.props = {
            node.name     = "capture.rnnoise_source"
            node.passive  = true
            audio.rate    = 48000
            audio.channels = 1
            audio.position = [ MONO ]
        }
        playback.props = {
            node.name   = "rnnoise_source"
            media.class = Audio/Source
            audio.rate  = 48000
            audio.channels = 1
            audio.position = [ MONO ]
        }
    }
}
]
```

Try it in a terminal first. Nothing is restarted and Ctrl+C takes it away again:

```bash
pipewire -c filter-chain.conf
```

`filter-chain.conf` comes from `/usr/share/pipewire/` and merges every fragment in `~/.config/pipewire/filter-chain.conf.d/`. Once it works, keep it with a user unit, `~/.config/systemd/user/rnnoise-source.service`:

```
[Unit]
Description=RNNoise noise-canceling source
After=pipewire.service wireplumber.service
Requires=pipewire.service
Wants=wireplumber.service
PartOf=pipewire.service

[Service]
Type=simple
ExecStart=/usr/bin/pipewire -c filter-chain.conf
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now rnnoise-source.service
```

Then pick **Noise Canceling source** as the input in the app, or `wpctl set-default <its id>`.

*Alternative, if you would rather keep it in the daemon:* the same `context.modules` block works in `~/.config/pipewire/pipewire.conf.d/99-input-denoising.conf`, which is what the Arch wiki and upstream's README still show. It costs an audio restart on every edit and a typo costs you the daemon, so prefer the client above.

Two version-sensitive details in that file:

- PipeWire 1.6.3 and newer resolve `plugin` as a *name* in the LADSPA search path, hence `plugin = librnnoise_ladspa`. On older PipeWire use the full path instead: `plugin = /usr/lib/ladspa/librnnoise_ladspa.so`.
- The explicit `audio.channels = 1` and `audio.position = [ MONO ]` lines in both prop blocks are needed since PipeWire 1.4.10 when the source reports stereo. Without them the chain can fail to instantiate.

**If you would rather click than edit config:** `sudo pacman -S easyeffects`, run it, go to the *Input* tab and add the *Noise Reduction* effect. It does the same RNNoise work with a GUI and per-app presets. **On Omarchy, EasyEffects and the shipped speaker tuning are mutually exclusive.** `omarchy audio tuning on` refuses to install while EasyEffects is running, because EasyEffects moves anything following the default sink onto its own sink and the tuning would be bypassed. Pick one:

```bash
systemctl --user disable --now easyeffects.service   # to keep the tuning
```

**Verify.** `wpctl status` lists the new virtual nodes under Sources (and Sinks for the AEC). For the filter-chain client, `systemctl --user status rnnoise-source.service` should be active and the node should appear without an audio restart. Record and listen back:

```bash
parecord --device=rnnoise_source /tmp/test.wav   # type loudly while recording
# Ctrl+C, then:
paplay /tmp/test.wav
```

For the AEC, play music out of the speakers, record from the Echo Cancellation Source, and confirm the music is largely absent from the recording. `pw-top` shows the filter nodes running while a call is active. `parecord` and `paplay` come from `libpulse`, which is already installed alongside `pipewire-pulse`.

Sources: <https://docs.pipewire.org/page_module_echo_cancel.html> · <https://raw.githubusercontent.com/PipeWire/pipewire/master/src/modules/module-echo-cancel.c> · <https://raw.githubusercontent.com/PipeWire/pipewire/master/spa/plugins/aec/aec-webrtc.cpp> · <https://wiki.archlinux.org/title/PipeWire> · <https://raw.githubusercontent.com/werman/noise-suppression-for-voice/master/README.md> · <https://docs.pipewire.org/page_module_filter_chain.html> · <https://archlinux.org/packages/extra/x86_64/noise-suppression-for-voice/files/> · <https://archlinux.org/packages/extra/x86_64/noise-suppression-for-voice/> · <https://archlinux.org/packages/extra/x86_64/swh-plugins/> · <https://archlinux.org/packages/extra/x86_64/easyeffects/>

---

## Fix a microphone that is inaudible or clipped and distorted on calls

`microphone-too-quiet-or-distorted` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** People on calls say you are inaudible, or that you sound blown-out and clipped/static-y. Recordings are either near-silent or heavily distorted even at moderate speaking volume.

**Cause.** The ALSA `Mic Boost` / `Internal Mic Boost` control is at maximum (distortion) or the `Capture` control is at zero (silence). PipeWire's source volume is a separate, additional gain stage on top of it, so raising one while the other is wrong makes it worse.

**Fix.**

Set the hardware gain sanely first:

```bash
alsamixer -c 0
```

Press `F4` for the capture view, then set `Mic Boost` / `Internal Mic Boost` to `0` or `1` step, and raise `Capture` to around 70-80%. Non-interactively:

```bash
amixer -c 0 sset 'Mic Boost' 0
amixer -c 0 sset 'Internal Mic Boost' 0
amixer -c 0 sset Capture 75% cap
sudo alsactl store
```

Then set PipeWire's software gain (values above 1.0 are extra gain, use sparingly):

```bash
wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 100%
wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0
```

Monitor your own level while adjusting:

```bash
arecord -vv --format=dat /dev/null
```

The bar graph should peak around 60-80%, never pinning at the right edge.

**Verify.** `arecord -vv --format=dat /dev/null` shows peaks in the upper-middle of the meter while speaking normally, and a test recording plays back clean.

Sources: <https://wiki.archlinux.org/title/Advanced_Linux_Sound_Architecture/Troubleshooting> · <https://wiki.archlinux.org/title/PipeWire/Troubleshooting>

---

## Restore touchpad right-click after updating to Omarchy 4.0

`omarchy-touchpad-right-click-broken` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** After updating to Omarchy 4.0, touchpad right-click stopped working entirely — neither a two-finger tap nor a click in the lower-right corner produces a context menu, in any application (Chromium, Thunderbird, GTK apps). `libinput debug-events` still shows `BTN_RIGHT` being generated, so the hardware and libinput are fine.

**Cause.** Omarchy's migration from the old hyprlang `.conf` format to the Lua config carried over `clickfinger_behavior` as a commented-out line. The old hyprlang parser had a working default for the unset state; the Lua path does not, and leaving it unset breaks right-click interpretation entirely.

**Fix.**

Set the value explicitly in your Hyprland Lua config rather than leaving it commented out:

```lua
-- ~/.config/hypr/hyprland.lua  (or your Omarchy input override file)
hl.config({
  input = {
    touchpad = {
      clickfinger_behavior = false,   -- click position decides the button (bottom-right = RMB)
      tap_to_click = true,
      scroll_factor = 0.4,
    },
  },
})
```

Set it to `true` instead if you prefer the macOS-style behaviour where 1/2/3 fingers anywhere on the pad map to LMB/RMB/MMB:

```lua
      clickfinger_behavior = true,
```

Then:

```bash
hyprctl reload
```

Check for the leftover commented line and delete or uncomment it:

```bash
grep -rn 'clickfinger_behavior' ~/.config/hypr/
```

**Verify.** `hyprctl getoption input:touchpad:clickfinger_behavior` returns the value you set, and a two-finger tap opens a context menu in a browser.

Sources: <https://github.com/basecamp/omarchy/issues/6935> · <https://wiki.hypr.land/Configuring/Basics/Variables/>

---

## Pick the webcam node that works when one of two cameras is black

`webcam-black-image-ipu6-wrong-node` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `omarchy`, `wayland`

**Symptom.** The webcam picker or a video app offers two cameras and only one works: selecting the first gives a black overlay or a `Link severed` error. On Intel 11th-gen and newer laptops, `/dev/video0` is present but unusable while the real camera is at a much higher number such as `/dev/video42`. Auto-detect always picks the broken one.

**Cause.** Intel IPU6 MIPI cameras expose many `/dev/video*` nodes, most of which are raw-Bayer or output-only sub-device nodes rather than usable capture devices. Tools that just take the first `/dev/video*` open a node that will never produce a viewable frame; the usable stream is presented separately (commonly via a v4l2loopback node fed by the IPU6 userspace stack).

**Fix.**

Enumerate the nodes and their capabilities instead of guessing:

```bash
sudo pacman -S --needed v4l-utils
v4l2-ctl --list-devices
```

For each node, check whether it really does video capture:

```bash
for d in /dev/video*; do
  echo "== $d"
  v4l2-ctl --device="$d" --info | grep -A4 'Device Caps'
done
```

Only nodes whose caps include `Video Capture` are usable. The udev property is a quicker filter:

```bash
udevadm info --query=property --name=/dev/video0 | grep ID_V4L_CAPABILITIES
# usable capture nodes report :capture:
```

Test the candidate directly and note the working path:

```bash
v4l2-ctl --device=/dev/video42 --list-formats-ext
ffplay -f v4l2 -i /dev/video42
```

Then point your app at that specific node — e.g. in OBS choose the device by name rather than by index, and for Chromium/Firefox use the entry that matches the working node.

**Verify.** `ffplay -f v4l2 -i /dev/videoN` shows a live picture, and `v4l2-ctl --device=/dev/videoN --info` lists `Video Capture` in its Device Caps.

Sources: <https://github.com/basecamp/omarchy/issues/5722> · <https://wiki.archlinux.org/title/Webcam_setup>

---

## Recover an audio device that vanished after WirePlumber state went bad

`wireplumber-state-corrupt-devices-missing` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** An audio device that used to work has vanished from `wpctl status` / pavucontrol, or auto-switching and the remembered default sink stopped working entirely after an update. Sometimes a device shows up but is stuck at profile "Off".

**Cause.** WirePlumber 0.5 persists per device state as plain text under `$XDG_STATE_HOME/wireplumber`, which is `~/.local/state/wireplumber` by default, in four files: `default-nodes` for the configured default sink and source, `default-routes` for per profile route selection, volumes and mute, `default-profile` for the chosen card profile, and `stream-properties` for per application volume, mute and target. That state can be left inconsistent by an interrupted update, by a device whose ALSA node name changed so the stored key no longer matches anything, or by a stored profile of `off` that is restored on every boot. WirePlumber rewrites these files on a save timer and again on shutdown, which is why a deletion made while it is running comes straight back.

> **Audit corrected this record.** The state path is right on WirePlumber 0.5.15 and I confirmed it on this machine, not only from a source. `~/.local/state/wireplumber/` exists here and holds `default-nodes`, `default-routes` and `stream-properties`, and the shipped Lua in `/usr/share/wireplumber/scripts/` names every state file explicitly: `State ("default-nodes")` in `default-nodes/state-default-nodes.lua`, `State ("default-routes")` in `device/state-routes.lua`, `State ("stream-properties")` in `node/state-stream.lua` and `StateMetadata ("default-profile")` in `device/state-profile.lua`. So the 0.4-era worry does not apply: the record names no file that stopped existing. Both cited Arch pages still say what the record claims, checked as raw wikitext, and the WirePlumber page's 'Delete corrupt settings' section gives the same stop, delete, start sequence. `wpctl set-default` is still a real subcommand in 0.5.15. Four things were wrong for Omarchy 4. First the fix jumps straight to `rm -rf` of the whole directory when the distribution ships a narrower repair: `omarchy restart audio` restarts all three units and, when WirePlumber still does not answer, strips only the USB lines from `default-nodes` and `default-routes` after copying each to a timestamped `.bak`, which I read in `/usr/share/omarchy/bin/omarchy-restart-audio` rather than running. Second, the record gives no way to delete less than everything, even though the symptom points at one file, and Omarchy's own `install/user/hardware/asus/fix-audio-mixer.sh` demonstrates the targeted form by removing only `default-routes`. Third, it does not say why the stop has to come first, which is the part people skip: WirePlumber saves state on a timeout and on shutdown, so a delete while it runs is written straight back. Fourth, the `pipewire-media-session` cleanup is presented as a general step. That package is still in Arch extra as deprecated 1:0.4.3-1 but is not in `omarchy-base.packages` or `omarchy-other.packages` and `~/.config/pipewire` does not exist on this install, so it belongs behind a condition rather than in the main path. I also checked that nothing Omarchy installs lives in the state directory, so the speaker tuning from `omarchy audio tuning on`, which writes to `~/.config/pipewire/` and `~/.config/systemd/user/`, survives the deletion. NOT exercised: per the safety rule I did not stop `wireplumber.service`, delete any state file, or change a default, so the recovery itself is unverified on this machine and rests on the two Arch pages plus the shipped scripts.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Deleting the whole state directory loses every remembered per device volume, mute, card profile, route and default device choice, plus per application volumes, and you will have to set them again. Deleting one file loses only that category. There is no system level risk and no data outside the state directory is touched. Stop `wireplumber.service` before deleting, otherwise the file is written back from memory on shutdown and you will conclude the fix did not work.

**Fix.**

Try the shipped repair before deleting anything. On Omarchy 4, `omarchy restart audio` restarts `pipewire.service`, `pipewire-pulse.service` and `wireplumber.service`, and if PipeWire still does not answer it resets a stuck USB audio device and strips only the USB entries from `default-nodes` and `default-routes`, backing up each file first:

```bash
omarchy restart audio
```

If the device is still missing, delete state. Stop WirePlumber first, or the file is rewritten from memory on shutdown and your deletion is undone:

```bash
systemctl --user stop wireplumber.service
```

Delete only the file that matches the symptom:

```
~/.local/state/wireplumber/default-profile     card stuck at profile "Off"
~/.local/state/wireplumber/default-routes      wrong port, volume or mute per profile
~/.local/state/wireplumber/default-nodes       chosen default sink or source will not stick
~/.local/state/wireplumber/stream-properties   one application starts at the wrong volume or device
```

```bash
rm -f ~/.local/state/wireplumber/default-profile
```

If you cannot tell which, remove the whole directory:

```bash
rm -rf ~/.local/state/wireplumber/
```

Start it again and look at the graph:

```bash
systemctl --user start wireplumber.service
wpctl status
```

Re-set your defaults. On Omarchy 4 the shipped commands also move streams that are already playing, and they take the node id and the node name, both of which `wpctl status` prints:

```bash
omarchy-audio-output-set-default <node-id> <sink-name>
omarchy-audio-input-set-default <node-id> <source-name>
```

`omarchy audio output switch` cycles outputs without you having to read an id at all.

On plain Arch, take the ids from `wpctl status`:

```bash
wpctl set-default <sink-id>
wpctl set-default <source-id>
```

Only on a machine that once ran the deprecated `pipewire-media-session` is there anything else to clear. Omarchy 4 has never installed it, so skip this unless the directory is actually there:

```bash
rm -rf ~/.config/pipewire/media-session.d/
```

Nothing Omarchy installs lives in the state directory. Its audio configuration sits in `~/.config/wireplumber/wireplumber.conf.d/` and `~/.config/pipewire/`, so a speaker tuning installed by `omarchy audio tuning on` survives all of this. Confirm with `omarchy audio tuning status`.

**Verify.** `wpctl status` lists every device again after the restart, the card is no longer on profile `Off`, and the default you set still holds after a reboot. `ls ~/.local/state/wireplumber/` shows the files being written again, which is what tells you WirePlumber restarted and is saving state rather than failing early.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://wiki.archlinux.org/title/WirePlumber>

---

## Fix a fingerprint reader that stops working after the first suspend

`fprintd-broken-after-suspend` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** The fingerprint reader works after boot but stops after the first suspend/resume — `fprintd-verify` hangs or errors, and login prompts hang for ~10 seconds before falling back to a password. Sometimes reported as the login screen freezing when revealing the password prompt after resume.

**Cause.** fprintd keeps running for ~30 seconds after a successful auth; suspending in that window wedges it. Separately, some USB readers are re-enumerated on resume and fprintd holds a stale handle because USB persistence is off for that device.

**Fix.**

Kill fprintd before every sleep:

```ini
# /etc/systemd/system/kill-fprintd.service
[Unit]
Description=Kill fprintd before sleep
Before=sleep.target

[Service]
ExecStart=killall fprintd

[Install]
WantedBy=sleep.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable kill-fprintd.service
```

If the reader is re-enumerated on resume, enable USB persistence for it. Get the vendor/product IDs from `lsusb` and substitute them:

```bash
lsusb | grep -i -E 'fingerprint|synaptics|goodix|elan|validity'
```

```
# /etc/udev/rules.d/01-fingerprint.rules
ACTION=="add", SUBSYSTEM=="usb", DRIVERS=="usb", ATTRS{idVendor}=="06cb", ATTRS{idProduct}=="00fc", ATTR{power/persist}="1", RUN="/usr/bin/chmod 444 %S%p/../power/persist"
```

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Upstream also recommends s2idle rather than S3 for these readers — check what your machine uses:

```bash
cat /sys/power/mem_sleep
```

**Verify.** `systemctl suspend`, resume, then `fprintd-verify` succeeds immediately without a hang.

Sources: <https://wiki.archlinux.org/title/Fprint>

---

## Fix Bluetooth headphones being painfully loud at the lowest volume step

`bluetooth-volume-jumps-to-max` · severity: **low** · frequency: **common** · applies to: `arch`, `bluetooth`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Bluetooth headphones are painfully loud at the lowest usable setting — the very first step above mute is already too loud, and the volume slider is unusably coarse. Changing volume on the headphones also yanks the system slider and vice versa.

**Cause.** Since PipeWire 0.3.26 the headset's hardware (AVRCP absolute) volume is linked to the system volume. On devices with a coarse hardware volume table, the combined mapping collapses the useful range into a couple of steps.

**Fix.**

Disable hardware volume for Bluetooth devices:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

```conf
# ~/.config/wireplumber/wireplumber.conf.d/80-bluez-properties.conf
monitor.bluez.properties = {
  bluez5.enable-hw-volume = false
}
```

To do it for one device only (get the name from `pactl list cards short`):

```conf
# ~/.config/wireplumber/wireplumber.conf.d/80-bluez-properties.conf
monitor.bluez.rules = [
  {
    matches = [
      { device.name = "~bluez_card.XX_XX_XX_XX_XX_XX" }
    ]
    actions = {
      update-props = {
        bluez5.hw-volume = []
      }
    }
  }
]
```

```bash
systemctl --user restart pipewire.service wireplumber.service
```

Then disconnect and reconnect the headphones.

**Verify.** `wpctl set-volume @DEFAULT_AUDIO_SINK@ 10%` is now quiet-but-audible, and the headphone's own volume buttons no longer move the system slider.

Sources: <https://wiki.archlinux.org/title/Bluetooth_headset>

---

## USB DAC stuck at 48 kHz, so everything is resampled

`pipewire-sample-rate-stuck-48khz-resampling` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pipewire`

**Symptom.** "My DAC's front panel always shows 48 kHz no matter what I play." 44.1 kHz CD rips and 96/192 kHz hi-res files are all silently resampled, and `grep rate: /proc/asound/card*/pcm*p/sub*/hw_params` reports `rate: 48000 (48000/1)` for every track. A related complaint on cheap or old cards: audio is audibly distorted or crunchy because the hardware only really does 44.1 kHz and PipeWire is forcing 48 kHz at it.

**Cause.** PipeWire sets a single fixed global clock rate of 48000 Hz by default and resamples every stream to it. It will happily follow a stream's native rate instead, but only for rates listed in `default.clock.allowed-rates`, which ships containing just `[ 48000 ]`. Two extra traps: setting `default.clock.rate` to a new fixed value (a very common piece of forum advice) just moves the problem and additionally breaks the min/max quantum ratios, because quantums are expressed in samples and are not recalculated for you; and rate switching only happens when the graph is idle, so a single background client holding a stream open — cava, EasyEffects, a muted browser tab, a Discord call — pins the rate for everything else.

**Fix.**

**1. Find out what the hardware can actually do.**

```bash
grep -E 'Codec|Audio Output|rates' /proc/asound/card*/codec#*
# for USB DACs that report no codec info:
grep -m1 -Hn "" /proc/asound/card?/stream? | tee /dev/tty | awk -F':' '{print $1}' | xargs grep 'Rates'
```

**2. Allow those rates instead of pinning one.** Create `~/.config/pipewire/pipewire.conf.d/10-sample-rate.conf` (or the system-wide `/etc/pipewire/pipewire.conf.d/10-sample-rate.conf`):

```
context.properties = {
    default.clock.allowed-rates = [ 44100 48000 88200 96000 176400 192000 352800 384000 ]
}
```

Trim that list to rates your DAC actually reports. Up to 32 rates are accepted since PipeWire 0.3.61.

```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

Now PipeWire matches the stream's rate when both the allowed-rates list and the device support it, and falls back to resampling to `default.clock.rate` otherwise — no resampling in the common case.

**3. Only if the DAC will not follow** (usually because the kernel cannot read its supported rates) pin the rate — and move the quantums with it so latency stays sane:

```
context.properties = {
    default.clock.rate        = 96000
    default.clock.quantum     = 2048
    default.clock.min-quantum = 64
    default.clock.max-quantum = 4096
}
```

The stock values are `rate = 48000`, `quantum = 1024`, `min-quantum = 32`, `max-quantum = 2048`; the ones above preserve the same real-time duration at double the rate.

**4. Test a rate without editing anything** — this bypasses the allowed-rates check entirely and is the fastest way to prove the DAC can do it:

```bash
pw-metadata -n settings 0 clock.force-rate 96000   # force
pw-metadata -n settings 0 clock.force-rate 0       # release, back to automatic
```

**5. If the rate still never changes**, something is holding the graph. Find it and close it:

```bash
pw-top          # lists every running node and its rate
wpctl status    # look for unexpected RUNNING streams
```

Cava, EasyEffects, an open browser tab and an idle Discord are the usual culprits. Also check you do not have a stale `default.clock.rate` from older advice in `/etc/pipewire/pipewire.conf`, `~/.config/pipewire/pipewire.conf`, or any other drop-in — a file in a higher-precedence directory shadows the packaged one entirely.

**Verify.** Play a 44.1 kHz track, then while it is playing:

```bash
grep rate: /proc/asound/card?/pcm??/sub?/hw_params
```

It should read `rate: 44100 (44100/1)` (`pcm0p` = playback, `pcm0c` = capture). Play a 96 kHz file and confirm it changes to 96000. `pw-top` shows the same rate per node, and the DAC's own display should follow.

Sources: <https://wiki.archlinux.org/title/PipeWire/Troubleshooting> · <https://raw.githubusercontent.com/PipeWire/pipewire/master/src/daemon/pipewire.conf.in> · <https://docs.pipewire.org/page_man_pipewire_conf_5.html> · <https://bbs.archlinux.org/viewtopic.php?id=288932> · <https://wiki.archlinux.org/title/PipeWire>

---

## Remap keys system-wide with keyd, including the TTY and login screen

`system-wide-key-remap-wayland-keyd` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** You want Caps Lock as Ctrl/Escape, a home-row mod layer, or media keys remapped, and it must work everywhere — in Hyprland, in the TTY, on the SDDM/greeter login screen, and inside XWayland games. `setxkbmap`/`xmodmap` do nothing on Wayland, and Hyprland's `kb_options` only covers the compositor session, not the TTY or the display manager.

**Cause.** Hyprland's XKB settings are applied by the compositor to its own clients only. Anything outside the compositor session (virtual console, greeter, early boot) never sees them. Remapping below the compositor requires a kernel-level evdev/uinput daemon.

> **Audit corrected this record.** The mechanism and the config format are right, the Omarchy 4 specialisation and the danger are wrong. Confirmed correct against keyd's own docs at rvaiya/keyd master: the config must begin with an `[ids]` section, `*` matches every device keyd identifies as a keyboard, `[main]` is the base layer, `capslock = overload(control, esc)` is upstream's own first example, and `sudo keyd reload` is the documented reload. Packaging checked against archlinux.org: keyd is in `extra` at 2.6.0-5, not the AUR, and the unit really is `keyd.service` in `usr/lib/systemd/system/`. `pacman -Q keyd` fails on this workstation, so keyd is not installed here and nothing below was exercised live. `sudo pacman -S keyd` is not blocked on Omarchy: /usr/bin/omarchy-update-pacman-guard aborts only when the pacman command line carries both a sync and a sysupgrade flag, so a plain install passes. Three defects. (1) The flagship example collides head on with Omarchy 4. /usr/share/omarchy/default/hypr/input.lua line 37 sets `kb_options = "compose:caps,shift:both_capslock_cancel"`, so on Omarchy Caps Lock is already the Compose key and Caps Lock itself lives on both Shifts. `hyprctl -j devices` on this machine confirms it: every keyboard reports `options: compose:caps,shift:both_capslock_cancel`. A keyd `[main]` that turns capslock into control and esc means the compositor never sees the Caps Lock keycode, which kills Compose, kills ~/.XCompose, and makes /usr/lib/systemd/user/omarchy-fcitx5.service pointless, since that unit's stated job is exactly to turn CapsLock compose sequences into text. The record says nothing about this. (2) The Hyprland-only alternative replaces rather than extends. ~/.config/hypr/input.lua is loaded after Omarchy's defaults and its own header says uncommented settings replace them, and its commented kb_options example keeps `compose:caps,shift:both_capslock_cancel` as a prefix. The record's `kb_options = "caps:ctrl_modifier"` would silently drop both. It also does not say which file to put it in. (3) The danger names a recovery route that does not work. keyd's README states the escape hatch plainly: `backspace+escape+enter` terminates keyd. The record omits it and instead suggests a spare USB keyboard, which under `[ids] *` is grabbed too and helps with nothing, and `sudo systemctl stop keyd`, which needs a keyboard you no longer have. Worth knowing for this machine specifically: the README warns that mice emitting keys are matched by the wildcard and may need blacklisting, and `hyprctl devices` here lists corsair-corsair-gaming-k55-rgb-keyboard-1 and razer-razer-basilisk-v3-keyboard under mice, so the composite-device case is live on this hardware. On the compositor interaction: keyd works below Hyprland by grabbing evdev and emitting through uinput, so Hyprland's xkb options apply on top of keyd's output rather than instead of it, and the two stack. I did not install keyd, did not write any file under /etc/keyd, did not start the unit and did not run `keyd monitor`. Severity stays low because the underlying want is a preference. Frequency is unchanged. Sources all resolve and all say what is cited, so nothing is removed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** keyd runs as root and grabs your keyboards, so a bad config can leave you with no way to type, including at the TTY and the greeter. **Learn the escape hatch before you start**: keyd's own documentation says the key sequence `backspace+escape+enter` causes keyd to terminate. That is the only recovery that works when the keyboard is the thing that is broken. A spare USB keyboard does not help under `[ids] *`, because keyd grabs that one too, and `sudo systemctl stop keyd` needs a keyboard you no longer have or a second machine already logged in over ssh. Open an ssh session from another machine before you enable the unit, and keep it open while you test. On Omarchy 4 there is a second cost: a rule that consumes Caps Lock removes the Compose key that `kb_options = "compose:caps"` and `omarchy-fcitx5.service` depend on, so `~/.XCompose` sequences stop producing characters.

**Fix.**

keyd is in `extra`, so no AUR helper is needed. The Omarchy update guard only blocks a combined sync and sysupgrade, so a plain install is fine:

```bash
sudo pacman -S keyd
```

**Before you write a config on Omarchy 4, know what Caps Lock already does.** `/usr/share/omarchy/default/hypr/input.lua` sets:

```
kb_options = "compose:caps,shift:both_capslock_cancel"
```

So Caps Lock is the Compose key, Caps Lock itself is on both Shifts together, and `omarchy-fcitx5.service` exists to turn those compose sequences from `~/.XCompose` into text. Confirm on your own machine:

```bash
hyprctl -j devices | grep -m1 options
```

keyd sits below the compositor, so a rule that consumes Caps Lock means Hyprland never sees that keycode and Compose stops working. Pick a key Omarchy has not claimed, or accept losing Compose and say so to yourself first. This example leaves Caps Lock alone:

```
# /etc/keyd/default.conf
[ids]
*

[main]
# Swap left alt and left meta.
leftalt = leftmeta
leftmeta = leftalt

# Right alt becomes tap for Escape, hold for Control.
rightalt = overload(control, esc)
```

On **plain Arch**, where nothing owns Caps Lock, upstream's own example is the usual one:

```
[main]
capslock = overload(control, esc)
```

Enable and load it:

```bash
sudo systemctl enable --now keyd
sudo keyd reload
```

Watch what keyd produces while you test, and read the log if a config is rejected:

```bash
sudo keyd monitor
sudo journalctl -eu keyd
```

The remap now applies in Hyprland, in XWayland apps, at the greeter and in the TTY, because it happens before anything reads the device. Hyprland's own xkb options still apply on top of keyd's output, so the two stack rather than replacing each other.

**Watch the wildcard.** `*` matches every device keyd treats as a keyboard, and gaming mice and keyboard-equipped peripherals often qualify. `hyprctl devices` on this workstation lists `corsair-corsair-gaming-k55-rgb-keyboard-1` and `razer-razer-basilisk-v3-keyboard` under `mice`. Get ids from `sudo keyd monitor` and exclude what you do not want:

```
[ids]
*
-1532:00a6
```

If you only need the remap inside the Hyprland session, prefer the compositor setting. It is simpler and has no root daemon. **On Omarchy 4 it goes in `~/.config/hypr/input.lua`, which is loaded after Omarchy's defaults and replaces them wholesale**, so repeat the options you want to keep:

```lua
-- ~/.config/hypr/input.lua
hl.config({
  input = {
    kb_options = "compose:caps,shift:both_capslock_cancel,altwin:swap_lalt_lwin",
  },
})
```

Writing `kb_options = "caps:ctrl_modifier"` on its own there drops Compose and the both-Shifts Caps Lock. It also fights `compose:caps`, because both want Caps Lock.

**Verify.** `sudo keyd monitor` shows the remapped keysym, and the remap still works after switching to a TTY with Ctrl+Alt+F3. If nothing changes, read `sudo journalctl -eu keyd` for a config parse error, since keyd reports those to the journal rather than to the terminal. On Omarchy 4, also confirm you did not lose Compose: press Caps Lock followed by a sequence from `~/.XCompose` and check the character still arrives.

Sources: <https://wiki.archlinux.org/title/Input_remap_utilities> · <https://wiki.archlinux.org/title/Keyboard_input> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://github.com/rvaiya/keyd/blob/master/README.md> · <https://github.com/rvaiya/keyd/blob/master/docs/keyd.scdoc> · <https://archlinux.org/packages/extra/x86_64/keyd/>

---
