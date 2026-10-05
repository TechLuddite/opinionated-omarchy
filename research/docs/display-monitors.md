# Displays & monitors

55 problems. Sorted by severity, then by how often users hit it.

## Stop closing the lid from killing every GUI app at once

`clamshell-lid-close-kills-all-gui-clients` · severity: **critical** · frequency: **common** · applies to: `hyprland`, `intel`, `laptop`, `omarchy`, `wayland`

**Symptom.** Plug in HDMI, close the laptop lid a couple of seconds later, and every GUI app dies at once: terminals, Nautilus, Brave, the bar, portals, fcitx5, XWayland. Hyprland itself stays up. Journal shows `wl_registry#2: error 0: global wl_output (79) is unavailable`, `The Wayland connection experienced a fatal error: Protocol error` and `XWAYLAND: (EE) failed to dispatch Wayland events: Protocol error`. Afterwards `xprop -root` hangs and X11 apps will not start until you log out.

**Cause.** A Hyprland 0.56.2 registry-bind race: the `wl_output` global is destroyed while clients are still binding it, and every client that was mid-bind gets a fatal protocol error. Omarchy's clamshell helper is what fires that path on a stock laptop. On `monitoradded` it runs `hyprctl reload` (with retries at 1s/3s/7s), and on lid close it writes `hl.monitor({ output = "eDP-1", disabled = true })` into a toggle file that is loaded as config, then reloads again. A specific-output disable of the panel is what turns 'one client dies' into a whole-session wipe.

> **Audit corrected this record.** The diagnosis is solid: basecamp/omarchy#7853 exists with a matching title, and quattro's bin/omarchy-hyprland-monitor-clamshell does exactly what is described (disable_internal writes `hl.monitor({ output = "eDP-1", disabled = true })` into the toggle file then reloads), while bin/omarchy-hyprland-monitor-watch retries `sync_clamshell` at 1s/3s/7s after monitoradded. The o.bind signature and `{ locked = true }` option are correct, `omarchy-brightness-display` really does accept `off`/`on`, and the toggle paths and `uwsm stop` are right. But the replacement bind has three real defects. (a) Per Omarchy's own config/hypr/bindings.lua, an existing default must be unbound first. `o.bind` on a key the defaults already claim does not reliably replace it. (b) The stock `switch:on:Lid Switch` bind runs `omarchy-system-lid-close`, which locks the session when the lid closes with no external monitor attached. Silently replacing it means the laptop no longer locks on lid close. (c) `omarchy-brightness-display off` acts on the *focused* monitor, which in a docked lid-close is usually the external one, so it will blank the wrong screen unless you pass `--monitor`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Rebinding the lid switch means the laptop panel is no longer removed from the layout when you close the lid. Windows stay on an output you cannot see. Check with `hyprctl monitors` before assuming a workspace is lost.

**Fix.**

Until the compositor fix lands, stop Omarchy from destroying the internal `wl_output` on lid close. Unbind the defaults first, then point the lid switch at a backlight blank of the *internal* panel, and keep the lock, which the stock `omarchy-system-lid-close` provides and a bare backlight bind would silently drop. In `~/.config/hypr/bindings.lua`:

```lua
hl.unbind("switch:on:Lid Switch")
hl.unbind("switch:off:Lid Switch")

o.bind("switch:on:Lid Switch", nil,
  "omarchy-system-lock; omarchy-brightness-display --monitor eDP-1 off", { locked = true })
o.bind("switch:off:Lid Switch", nil,
  "omarchy-brightness-display --monitor eDP-1 on", { locked = true })
```

Substitute your own internal connector for `eDP-1` (`omarchy-hyprland-monitor-laptop` prints it). Drop the `omarchy-system-lock;` half only if you deliberately do not want the laptop to lock when the lid shuts.

And clear any toggle that is already persisted:

```bash
rm -f ~/.local/state/omarchy/toggles/hypr/internal-monitor-clamshell.lua
rm -f ~/.local/state/omarchy/toggles/hypr/internal-monitor-disable.lua
hyprctl reload
```

Operationally: plug the external display in *first*, wait for it to settle, and only then close the lid. If the session is already wiped, XWayland is not respawned, so log out with `uwsm stop` and log back in.

**Verify.** Plug in HDMI, wait, close the lid: `hyprctl clients | wc -l` stays roughly the same and `journalctl -b -g 'wl_output.*unavailable'` returns nothing.

Sources: <https://github.com/basecamp/omarchy/issues/7853> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/bindings/utilities.lua> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-clamshell>

---

## Fix Hyprland hanging at startup from a rule on a disconnected port

`explicit-rule-on-disconnected-connector-freezes` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`, `wayland`

**Symptom.** Hyprland hangs completely at startup (black or frozen screen, bar never draws, mouse may still move) on a machine where you wrote a monitor rule for a port that currently has nothing plugged into it (very common on Apple Silicon/Asahi, where `DP-1` is always exposed).

**Cause.** When the kernel exposes a connector but reports it `disconnected` with no EDID/modes, and you have an explicit rule for that connector, Hyprland enables the output anyway. It gets a 0x0 framebuffer, bar/layer surfaces are created on the bogus output and never commit, and the renderer stalls.

**Fix.**

Always keep a catch-all fallback rule *after* your explicit rules, so unmatched or failed outputs degrade gracefully. In `~/.config/hypr/monitors.lua`:

```lua
hl.monitor({ output = "DP-1", mode = "3840x2160@30", position = "2560x0", scale = 1 })
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })   -- fallback
```

On Hyprland <= 0.54 (`~/.config/hypr/monitors.conf`):

```
monitor=DP-1,3840x2160@30.0,2560x0,1.0
monitor=,preferred,auto,1
```

If you are already frozen, get to a TTY with Ctrl+Alt+F2 and comment out the explicit rule:

```bash
sed -i 's|^hl.monitor({ output = "DP-1"|-- &|' ~/.config/hypr/monitors.lua
```

**Verify.** Boot with nothing plugged into that port: Hyprland comes up, and `hyprctl monitors all` shows the connector as disabled rather than 0x0-enabled.

Sources: <https://github.com/hyprwm/Hyprland/issues/13310> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md>

---

## Fix No Signal on a hybrid laptop's dGPU-wired HDMI or USB-C port

`nvidia-external-monitor-no-signal-hybrid-laptop` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** On a hybrid Intel/AMD + NVIDIA laptop, the HDMI or USB-C port (which is wired to the dGPU) gives 'No Signal' on the external monitor. Hyprland runs fine on the internal panel. `hyprctl monitors` never lists the external one. Or the external comes up but is unusably laggy.

**Cause.** On many laptops the external ports are physically wired to the NVIDIA GPU. If `nvidia_drm.modeset` is off, or if aquamarine picked the iGPU as the only DRM device, the compositor never drives those connectors. NVIDIA also lacks features needed for good multi-GPU buffer sharing.

> **Audit corrected this record.** Steps 1, 2 and 4 are accurate and match the hyprland-wiki Nvidia page: modeset must read Y, options nvidia_drm modeset=1, and MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm) plus sudo mkinitcpio -P. The page also flags that early KMS can break hibernation resume, which the record omits here. The uwsm file paths are correct: uwsm(1) documents uwsm/env-${compositor} and uwsm/env.d/*. Two problems in step 3. First, `AQ_FORCE_LINEAR_BLIT=0` is undocumented and its effect is the opposite of what the framing implies: in aquamarine's src/allocator/GBM.cpp the flag reads `!envExplicitlyDisabled("AQ_FORCE_LINEAR_BLIT")`, i.e. it is ON by default, and setting it to 0 makes aquamarine try to allocate a LINEAR-modifier buffer for cross-GPU sharing, which the adjacent source comment says 'Nvidia doesn't support', so on the exact hardware this record targets it is more likely to hurt than help. Second, the hyprland-wiki Multi-GPU page explicitly warns against using /dev/dri/cardN paths at all ('Do not use the card1 symlink... It is dynamically assigned at boot and is subject to frequent change'), and gives a udev-symlink recipe instead.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `mkinitcpio -P` regenerates every initramfs. Run it only after a fully completed `pacman -Syu`. Doing it mid partial-upgrade, or with a failed nvidia-dkms build, produces an initramfs missing the module and a black screen at boot. Keep the fallback boot entry.

**Fix.**

1. Confirm DRM modesetting is on. This is the single most common cause:

```bash
cat /sys/module/nvidia_drm/parameters/modeset    # must be Y
```

On current Arch, nvidia-utils already ships `options nvidia_drm modeset=1` in `/usr/lib/modprobe.d/nvidia-utils.conf`, so this usually already reads Y. If it prints `N`:

```bash
sudo tee /etc/modprobe.d/nvidia.conf <<'EOF'
options nvidia_drm modeset=1
EOF
sudo mkinitcpio -P
```

2. Load the modules early. In `/etc/mkinitcpio.conf`:

```
MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
```

then `sudo mkinitcpio -P` and reboot. Note that early KMS can stop resume-from-hibernation working. If that happens, remove these entries again. On Intel hybrids, put `i915` first in the list.

3. If the external is detected but laggy or broken, tell aquamarine which GPU to use, NVIDIA node first. Do not use raw `/dev/dri/cardN` paths, because those numbers are reassigned at boot. Create a stable symlink instead:

```bash
NV_ID=$(lspci -d ::03xx | grep -i nvidia | cut -f1 -d' ')
printf 'KERNEL=="card*", KERNELS=="0000:%s", SUBSYSTEM=="drm", SUBSYSTEMS=="pci", SYMLINK+="dri/nvidia-gpu"\n' "$NV_ID" \
  | sudo tee /etc/udev/rules.d/90-nvidia-dev-path.rules
sudo udevadm control --reload
sudo udevadm trigger
ls -l /dev/dri/nvidia-gpu
```

Then, in `~/.config/uwsm/env-hyprland` (this is where the Hyprland wiki says uwsm users should put AQ_* variables, on Arch and Omarchy alike), one export per line:

```sh
export AQ_DRM_DEVICES=/dev/dri/nvidia-gpu
```

Add the iGPU as a second `:`-separated entry if the internal panel hangs off it. Log out and back in (`uwsm stop`) for this to take effect. Do not set `AQ_FORCE_LINEAR_BLIT=0` here, because it makes aquamarine attempt LINEAR-modifier buffers that NVIDIA does not support.

4. If your BIOS offers it, switching from Hybrid to Discrete graphics avoids the problem entirely (remove `optimus-manager` first, since disabling the service is not enough).

**Verify.** `hyprctl monitors` lists the external output with a real mode, and `cat /sys/module/nvidia_drm/parameters/modeset` returns `Y`.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Nvidia/_index.md> · <https://wiki.archlinux.org/title/Hyprland>

---

## Get DisplayLink dock monitors redetected after a replug

`displaylink-dock-monitors-not-redetected` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `dock`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Boot with the DisplayLink dock attached and all screens work. Unplug the dock, plug it back in, and `hyprctl monitors` shows only the laptop display. The kernel is happy. `evdi: [I] (card3) Connector state: connected` and `/dev/dri/card2..card5` all exist, but Hyprland ignores them. `hyprctl reload`, `hyprctl dispatch dpms off/on` and explicit `desc:` monitor rules all do nothing.

**Cause.** Hyprland/aquamarine enumerate DRM devices once at startup and do not rescan for DRM *devices* (as opposed to connectors) that appear at runtime. When a DisplayLink dock is replugged, evdi creates brand-new card nodes. Hyprland never opens them, and `ls -la /proc/$(pgrep Hyprland)/fd | grep -i evdi` is empty.

> **Audit corrected this record.** The problem and root cause are well sourced: hyprwm/Hyprland#14538 ('DRM devices from evdi (DisplayLink) not re-detected after dock reconnect without full compositor restart') and #7292 both exist, and `uwsm stop` is the documented Arch/Omarchy logout. But two of the diagnostic/fix commands are simply wrong. The AUR `displaylink` package installs `/usr/lib/systemd/system/displaylink.service`. There is no `displaylink-driver.service`, so both `systemctl status displaylink-driver.service` and `sudo systemctl enable --now displaylink-driver.service` fail outright (that unit name is the Ubuntu vendor installer's, not Arch's). Separately, `ls -la /proc/$(pgrep -x Hyprland)/fd | grep -i evdi` can never match: those fds are symlinks to /dev/dri/cardN, and the string 'evdi' appears nowhere in the listing, so the check reports the bug for everyone including healthy systems.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

There is no runtime fix in the compositor today. Practical options:

1. Restart the session with the dock already attached:

```bash
uwsm stop        # Omarchy / Arch with uwsm; then log back in
```

2. Confirm the driver side is actually healthy before blaming it. The Arch AUR `displaylink` package's unit is `displaylink.service` (there is no `displaylink-driver.service` on Arch: that name comes from the vendor's Ubuntu installer):

```bash
systemctl status displaylink.service
lsmod | grep evdi
ls /dev/dri/
```

Compare the card nodes evdi created against the ones Hyprland actually holds open. The fds are symlinks to /dev/dri/cardN, so match the numbers by hand:

```bash
ls -l /sys/class/drm/*/device/driver | grep evdi   # which cardN are evdi's
ls -l /proc/$(pgrep -x Hyprland)/fd | grep /dev/dri  # which cardN Hyprland opened
```

An evdi card that never appears in the second list is one Hyprland never opened.

3. Have the driver running before login so the card nodes exist when Hyprland starts:

```bash
sudo systemctl enable --now displaylink.service
```

This is necessary but not sufficient: the dock must also be attached before the session starts, since Hyprland enumerates DRM devices once.

4. If you dock and undock all day, prefer a DisplayPort-Alt-Mode/Thunderbolt dock over a DisplayLink one, because those drive real connectors on your GPU and are hotplugged normally.

**Verify.** After re-login with the dock attached, `hyprctl monitors | grep ^Monitor` lists every panel, and `ls -la /proc/$(pgrep -x Hyprland)/fd | grep -c evdi` is non-zero.

Sources: <https://github.com/hyprwm/Hyprland/issues/14538> · <https://github.com/hyprwm/Hyprland/issues/7292>

---

## Bring dock monitors back when an undock leaves them black at 0x0 until reboot

`dock-monitors-stay-0x0-after-undock-aquamarine-0-15-0` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `dock`, `endeavouros`, `hyprland`, `intel`, `laptop`, `mst`, `omarchy`, `wayland`

**Symptom.** Booting docked works, and plugging the dock in after a clean boot works. But unplug the dock, plug it back in, and the external monitors never come back. `hyprctl monitors all` lists them at `0x0@60`, and the Hyprland log repeats `atomic drm request: failed to commit: Invalid argument, flags: ATOMIC_ALLOW_MODESET ATOMIC_TEST_ONLY`, walking down to 720x400 and 640x480 and still failing. Only a reboot fixes it. Some people get the same thing after every lock-screen blank on DisplayPort monitors with no dock at all. Downgrading the kernel does not help.

**Cause.** aquamarine 0.15.0, Hyprland's DRM backend, added a guard that rejects commits to disconnected outputs. On unplug the connector is marked disconnected before Hyprland commits the disable, so the disable itself is refused and the kernel keeps a CRTC active on a dead connector. That orphaned pipe holds the display pipe and link resources (on Intel Type-C ports, the `intel_tc` link reference), so every later modeset on the new connector fails with EINVAL. The log line to look for is `Cannot commit a disconnected output`, followed by `clearing stale crtc`. Upstream tracked it as hyprwm/aquamarine#386, fixed by #410 (merged 2026-09-15) and released in aquamarine 0.15.1 on 2026-09-17. Arch extra carries 0.15.1-1. As of 2026-10-05 Omarchy's stable and rc mirrors still serve aquamarine 0.15.0-2 and only the edge mirror serves 0.15.1-1. omarchy 11019 has reproductions on i915, xe, amdgpu and NVIDIA, from undocking, from lock-screen and idle DPMS blanking with directly attached DisplayPort, and from switching cables. omarchy 11066 has the MST lock-screen case.

> **Audit corrected this record.** The mechanism holds: aquamarine 386 (closed 2026-09-15) describes the guard and the orphaned CRTC, PR 410 merged 2026-09-15, v0.15.1 was published 2026-09-17 with #410 in its notes, and Arch extra's JSON shows 0.15.1-1 updated 2026-09-17. Re-checked the mirrors on 2026-10-05 by downloading extra.db: stable-mirror and rc-mirror still list aquamarine-0.15.0-2, and mirror.omarchy.org (the edge mirrorlist in /usr/share/omarchy/default/pacman/mirrorlist-edge) lists 0.15.1-1. This workstation runs 0.15.0-2. omarchy 11019 is open and supports both recovery methods, but it also shows the reports are broader than the cause says (amdgpu, xe and NVIDIA reproductions, not only i915), a 2026-10-02 MST case where a VT switch alone left the outputs at `0x0` until an explicit mode was re-applied, and that `hyprctl reload` did not retry the modeset. The 'disable before undocking' prevention is a commenter's untested suggestion ('should avoid'), so it is now labelled that way. The danger was overstated: two commenters (2026-09-18 and 2026-10-03) installed Arch's 0.15.1-1 with `pacman -U` and confirmed the fix, the package provides the same `libaquamarine.so=14` as the installed 0.15.0-2, and its library dependencies (`libhyprutils.so=13`, `libdisplay-info.so=3`) match what is installed here. Read /usr/bin/omarchy-update-pacman-guard: it blocks only transactions with both -S and -u, so `pacman -U` passes. Nothing was installed or run against a dock.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Switching Omarchy to the edge channel moves every package to the rolling mirror and replaces `omarchy` with `omarchy-dev`, not only aquamarine. Installing Arch's aquamarine with `pacman -U` puts one package ahead of Omarchy's tested snapshot. Reporters confirmed it works with Hyprland 0.56.2-2, but it is outside what Omarchy tests, and `omarchy update` will report the local package as newer until stable catches up. Do not use `pacman -U` with any aquamarine build whose `libaquamarine.so` version differs from the one your installed hyprland was built against (`pacman -Qi aquamarine | grep Provides`).

**Fix.**

**1. Confirm it is this bug:**

```bash
pacman -Q aquamarine                     # 0.15.0-2 is affected
grep -c 'Cannot commit a disconnected output' "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log"
for c in /sys/class/drm/card*-DP-*; do echo "${c##*/} $(cat $c/status) $(cat $c/enabled)"; done
```

A connector that reads `disconnected enabled` is the orphaned pipe.

**2. Recover without rebooting.** Methods reported to work in omarchy 11019:

- Switch to another VT and back (Ctrl+Alt+F2, then the VT your session runs on). It can take two rounds.
- On an MST dock the VT switch can free the pipes but leave the monitors at `0x0` on the remembered fallback mode. Then re-apply an explicit mode to each external output. MST connectors get new names on every re-dock, so take the names and modes from `hyprctl monitors all`:

```bash
hyprctl monitors all -j | jq -r '.[] | "\(.name)  \(.width)x\(.height)  \(.availableModes[0])"'
hyprctl eval 'hl.monitor({ output = "DP-3", mode = "1680x1050@59.95", position = "auto", scale = 1 })'   # repeat for each external output
```

- On i915, one reporter recovered by disabling every physical output, then re-applying the monitor config. This also works over ssh while the screens are black:

```bash
hyprctl eval 'hl.monitor({ output = "DP-1", disabled = true })'    # repeat for each external output
hyprctl eval 'dofile(os.getenv("HOME") .. "/.config/hypr/monitors.lua")'
```

`hyprctl reload` on its own was reported not to retry the modeset.

**3. Possible prevention until you have 0.15.1 (suggested in omarchy 11019, not confirmed).** Disable the external outputs before you pull the dock, so the disable is committed while the connector still exists, then reload after redocking:

```bash
hyprctl eval 'hl.monitor({ output = "DP-5", disabled = true })'    # each dock output, before unplugging
# after plugging back in:
hyprctl reload
```

**4. The fix is aquamarine 0.15.1.**

- **Plain Arch:** `sudo pacman -Syu`.
- **Omarchy 4:** run `omarchy update -y` and check `pacman -Q aquamarine`. As of 2026-10-05 the stable and rc mirrors still serve 0.15.0-2. The edge channel (`omarchy-channel-set edge`) has 0.15.1-1, but see the danger note. Two reporters in omarchy 11019 installed Arch's build directly and confirmed it fixes the bug. It provides the same library version (`libaquamarine.so=14`) as 0.15.0-2, so the installed Hyprland loads it:

```bash
sudo pacman -U https://archive.archlinux.org/packages/a/aquamarine/aquamarine-0.15.1-1-x86_64.pkg.tar.zst
```

Then log out and back in so Hyprland loads the new library.

**Verify.** `pacman -Q aquamarine` reports 0.15.1 or newer. Undock, redock, and `hyprctl monitors` shows the externals at their native modes with no new `Cannot commit a disconnected output` lines in the log.

Sources: <https://github.com/omacom/omarchy/issues/11019> · <https://github.com/omacom/omarchy/issues/11066> · <https://github.com/hyprwm/aquamarine/issues/386> · <https://github.com/hyprwm/aquamarine/pull/410> · <https://github.com/hyprwm/aquamarine/releases/tag/v0.15.1> · <https://archlinux.org/packages/extra/x86_64/aquamarine/> · <https://archive.archlinux.org/packages/a/aquamarine/aquamarine-0.15.1-1-x86_64.pkg.tar.zst> · <https://stable-mirror.omarchy.org/extra/os/x86_64/extra.db> · <https://mirror.omarchy.org/extra/os/x86_64/extra.db>

---

## One external monitor never comes back after the idle screen-off timeout

`dpms-external-monitor-wont-wake-after-idle` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** hypridle blanks the screens after the idle timeout. Moving the mouse brings back the laptop panel and one external monitor, but the third display stays completely black. The only way back is to unplug and replug it, or reboot. The journal shows `Couldn't commit output DP-5`. Sometimes the reverse happens on the way down: `hyprctl dispatch dpms off` from hypridle turns off only the primary monitor while the others stay lit, then flicker when I come back.

**Cause.** Hyprland's DPMS dispatcher issues a DRM-level power change per output, and on some links (Thunderbolt/USB4 docks, DisplayPort MST, NVIDIA) the commit for one output fails and is never retried, leaving that screen dark while the others come back. The all-monitors form of the dispatcher is also unreliable when driven by hypridle rather than by hand. Discussion #11230 reports that a manual invocation turns off all monitors while the hypridle-triggered one regularly misses some, and #14234 tracks monitors that will not come back on at all. (Historical note: #2437 is the frequently-cited report of `Couldn't commit output DP-5` on a Thunderbolt-attached Dell, but it is closed as completed and was traced to a wlroots bug fixed with `WLR_DRM_NO_MODIFIERS`. Hyprland has run on Aquamarine rather than wlroots since 0.42, so that specific fix no longer applies and the current failures are a different code path with the same symptom.) On top of the commit failures, `misc:mouse_move_enables_dpms` and `misc:key_press_enables_dpms` both default to `false`, so input does not wake the outputs at all unless something explicitly re-enables them.

> **Audit corrected this record.** Strong record with one API defect and one stale citation. Verified: `hl.dsp.dpms({ action?, monitor? })` and `hl.dsp.force_renderer_reload()` are both documented, the Monitor param accepts a name or `desc:`, and `hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'` is exactly the form Omarchy uses in `omarchy-brightness-display` and `omarchy-hyprland-monitor-clamshell`. `misc:mouse_move_enables_dpms` and `misc:key_press_enables_dpms` both default to `false` as stated. `hypridle.conf` is still hyprlang/ini, so "do not convert it to Lua" is right. #2437 is real and its body does contain `[ERR] Couldn't commit output DP-5` on a Thunderbolt-attached Dell. Discussion #11230 is real and matches its summary. `wlopm` is in `extra`, so `pacman -S --needed wlopm` works (the `yay` fallback is unnecessary but harmless). The Omarchy 4 section is exact: hypridle is not in Quattro at all, `~/.config/omarchy/shell.json` carries a top-level `idle` block with `screensaver` and `lock` in seconds (the record's JSON matches `manual/13-toggles-idle-screensaver.md` verbatim, defaults included), and `omarchy-debug-idle` exists. The defect: `hl.set("misc:mouse_move_enables_dpms", true)` is not a real API. Only `hl.config({ category = { option = ... } })` is documented, and `hl.set` appears nowhere in the wiki or the Omarchy tree. Step 1 is the first thing a reader pastes, and it takes the config file down with it. Separately, #2437 is closed as *completed* and was resolved via the wlroots `WLR_DRM_NO_MODIFIERS` workaround. Hyprland has used Aquamarine, not wlroots, since 0.42, so presenting it as the live mechanism is stale. #11230 and #14234 are the current threads.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The Hyprland wiki warns that binding DPMS directly to a key "might cause undefined behavior". Call it from a timer or a script, not straight from a bind. If you experiment with `dpms disable` on your only monitor and input wake is not configured, you will have a black but running session: switch to a TTY with `Ctrl+Alt+F2` and run `hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'` with `HYPRLAND_INSTANCE_SIGNATURE` exported, rather than power-cycling.

**Fix.**

Steps 2 through 5 and the Omarchy 4 section are correct as written. Keep the per-output `hypr-dpms-on` retry loop, the `monitors all` filter, the manual `hl.dsp.dpms({ action = "enable", monitor = "DP-5" })` rescue, `hl.dsp.force_renderer_reload()`, and the `wlopm` alternative. Only step 1 needs replacing.

**1. Let input wake the displays.** Both options default to `false`. The documented Lua syntax is `hl.config`, not `hl.set`. Add to `~/.config/hypr/looknfeel.lua`:

```lua
hl.config({
  misc = {
    mouse_move_enables_dpms = true,
    key_press_enables_dpms  = true,
  },
})
```

```bash
hyprctl reload
```

To test the pair before committing them to a file:

```bash
hyprctl eval 'hl.config({ misc = { mouse_move_enables_dpms = true, key_press_enables_dpms = true } })'
```

One addition to step 3: give `hypr-dpms-on` a `wlopm --on '*'` last resort at the end of the retry loop, since it goes through `wlr-output-power-management-v1` rather than Hyprland's DRM path and often succeeds where the dispatcher has already failed:

```bash
command -v wlopm >/dev/null && wlopm --on '*' 2>/dev/null || true
```

**Verify.** Trigger the timeout (or run the disable dispatcher by hand), then move the mouse. Every output should light up. `hyprctl monitors all -j | jq -r '.[] | "\(.name) \(.width)x\(.height) dpms=\(.dpmsStatus)"'` should report `dpmsStatus: true` and a non-zero mode for all of them.

Sources: <https://github.com/hyprwm/Hyprland/issues/2437> · <https://github.com/hyprwm/Hyprland/discussions/11230> · <https://github.com/hyprwm/Hyprland/discussions/14234> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Hypr%20Ecosystem/hypridle.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Dispatchers.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-debug-idle> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/manual/13-toggles-idle-screensaver.md>

---

## Fix a docked external display staying dark after a long suspend

`external-display-dark-after-long-suspend-dock` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `dock`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Laptop in clamshell on a Thunderbolt/USB4 dock. Short sleeps come back fine, but after ~40 minutes or more of suspend the machine wakes (keyboard works, `hyprctl` answers, fans spin) and the external monitor never lights up. It sits in standby until you open the lid or reboot. Journal shows `[drm] Skip DMUB HPD IRQ callback in suspend/resume` and `xhci_hcd 0000:03:00.0: Controller not ready at resume -19`.

**Cause.** On resume, amdgpu discards hotplug interrupts raised inside the resume window, so re-detection depends on the dock re-asserting HPD *after* resume. After a long s2idle the Thunderbolt tunnel does not fully come back and that HPD never arrives. The kernel keeps the stale pre-suspend `connected` state, so nothing looks wrong from userspace and nothing re-modesets. This is a kernel/DRM state problem, not a compositor one, and `hyprctl reload` does not help.

> **Audit corrected this record.** The problem is real (basecamp/omarchy#7328 exists with a matching title) and the sysfs force-reprobe is a legitimate workaround, but three things need fixing. (1) The connector example is wrong for the command given: `ls -d /sys/class/drm/card*-*` yields `/sys/class/drm/card1-DP-5`, not `/sys/class/drm/card1/card1-DP-5`. (2) The reasoning about `echo detect` is inverted, and the consequence matters: in drm_sysfs.c, status_store calls fill_modes for `detect` too (the `|| !connector->force` branch), so detect *does* re-probe. What none of off/on/detect does is emit a hotplug uevent. That is why the compositor often does not notice, and why a `hyprctl reload` is needed afterwards (the sibling records for the same technique include one, but this one omits it). (3) The resume hook is genuinely harmful as written: it forces every DP connector off for a second on every single resume, including the ones that came back fine, which shuffles workspaces and windows on healthy multi-monitor setups. It also belongs in /etc/systemd/system-sleep/, because /usr/lib/systemd/system-sleep/ is the vendor directory for packages.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The sleep hook runs as root and writes to every DisplayPort connector on every resume. On a machine where the display is already working this forces a brief blank/re-modeset. Test the manual commands first and narrow the glob to your specific connector.

**Fix.**

Force the kernel to re-probe the connector (needs root). Find your connector path first:

```bash
ls -d /sys/class/drm/card*-*    # e.g. /sys/class/drm/card1-DP-5
```

Then toggle it off and back on. Writing to `status` re-probes but emits no hotplug uevent, so nudge the compositor afterwards:

```bash
CONN=/sys/class/drm/card1-DP-5
echo off    | sudo tee $CONN/status
sleep 1
echo on     | sudo tee $CONN/status
echo detect | sudo tee $CONN/status
hyprctl reload
```

To automate it, drop a resume hook, but only re-probe connectors that came back *dis*connected, so a working monitor is never blanked on every resume:

```bash
sudo tee /etc/systemd/system-sleep/99-reprobe-drm <<'EOF'
#!/bin/bash
[ "$1" = post ] || exit 0
for c in /sys/class/drm/card*-DP-*; do
  [ -e "$c/status" ] || continue
  [ "$(cat "$c/status")" = disconnected ] || continue
  echo off > "$c/status"; sleep 1
  echo on > "$c/status"; echo detect > "$c/status"
done
EOF
sudo chmod +x /etc/systemd/system-sleep/99-reprobe-drm
```

(Use `/etc/systemd/system-sleep/`, not `/usr/lib/systemd/system-sleep/`: the latter is the package-owned vendor directory.)

**Verify.** After a >40 minute suspend, the external panel lights up on wake with the lid still closed, and `hyprctl monitors` reports the correct mode.

Sources: <https://github.com/basecamp/omarchy/issues/7328>

---

## Lock screen draws the password box on one monitor only and the others are blank

`hyprlock-password-box-only-on-one-monitor` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-3`, `omarchy-4`, `wayland`

**Symptom.** hyprlock locks the session but the clock, avatar and password field only render on the laptop panel. The two external monitors are just a flat colour, or still showing a frozen image of my desktop, with no indication of where to type. I have to guess which screen has focus. On a triple-monitor desk it looks like the lock screen half-crashed.

**Cause.** hyprlock puts a session-lock surface on every output, but the *widgets* drawn on those surfaces are filtered by each widget's `monitor` field. The wiki states: *"`monitor` is available for all widgets and can be left empty for 'all monitors'."* Most shared configs and theme drops pin `monitor = eDP-1` (or a `desc:` string) on the `background`, `input-field` and `label` blocks, often copied from someone's single-laptop setup, so every other output gets a bare surface with nothing on it. A `background` block pinned to one monitor likewise leaves the others on the fallback `color`.

> **Audit corrected this record.** The diagnosis and the main fix are correct and well sourced. The quoted line "`monitor` is available for all widgets and can be left empty for 'all monitors'" is verbatim from the hyprlock wiki, which also confirms `monitor` defaults to empty on `background`, `image`, `shape`, `input-field` and `label`, that it takes the same string as the Hyprland monitor config including `desc:`, and that `path = screenshot` is valid. hyprlock.conf is indeed still hyprlang while Hyprland moved to Lua, so "do not convert it" is right. The Omarchy 4 section checks out: the lock screen is the Quickshell Omarchy shell configured through `~/.config/omarchy/shell.json`, `omarchy-shell lock status` is the real subcommand (`omarchy-restart-shell` calls exactly that and parses `.secure` / `.requested`), `omarchy-debug-idle` exists, and `omarchy-restart-shell` does refuse while the session is genuinely locked and secure. The defect is the test step: `hyprlock --immediate` is not a valid flag. The documented argument list is `-v/--verbose`, `-q/--quiet`, `-c/--config`, `--display`, `--grace`, `--immediate-render`, `--no-fade-in`, `-V/--version`, `-h/--help`. `--immediate` will be rejected and hyprlock will not start, and even the real `--immediate-render` only skips waiting for background resources, so it was never the flag that makes a test safe. The record's own safety advice (open a TTY first) is the right instinct, but the command it pairs with is wrong and `--grace` is the flag that actually gives you an escape hatch.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A broken hyprlock config is a locked-out-of-your-machine failure: hyprlock fails safe by staying locked. Always have a second TTY logged in before testing lock-screen changes, and never migrate `hyprlock.conf`/`hypridle.conf` to Lua. The hypr* tools deliberately stayed on hyprlang after Hyprland 0.55 deprecated it, so a Lua rewrite of these files will fail to parse and leave you with a lock screen that cannot authenticate you.

**Fix.**

Everything else in the record stands: leave `monitor =` bare on `background`, `input-field` and `label`, use `grep -n 'monitor' ~/.config/hypr/hyprlock.conf` to find pinned widgets, add an empty-`monitor` catch-all if you want per-screen backgrounds, keep `input-field` unpinned, and prefer `desc:` over connector names. Only the test step is wrong.

**Test without locking yourself out.** `--immediate` does not exist. hyprlock's flags are `-v/--verbose`, `-q/--quiet`, `-c/--config FILE`, `--display NAME`, `--grace SECONDS`, `--immediate-render`, `--no-fade-in`, `-V/--version`, `-h/--help`. Use `--grace`, which gives you a window to dismiss the lock without authenticating:

```bash
hyprlock --grace 30
```

Still open a second TTY *first* (`Ctrl+Alt+F2`, log in there and leave it) before you run it, so you have a way back if the widgets render but authentication misbehaves. From that TTY:

```bash
pkill hyprlock
```

To iterate on a config without touching your real one:

```bash
hyprlock -c /tmp/hyprlock-test.conf --grace 30 --no-fade-in
```

(`--immediate-render` is the flag the record was reaching for by name, but it only starts drawing widgets before background resources finish loading. It is a rendering option, not a safety net.)

**Verify.** Lock the session with a second TTY open as an escape hatch. Every monitor should show the background and the password field, and typing should register no matter which screen you look at.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Hypr%20Ecosystem/hyprlock.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-shell> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-debug-idle> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/manual/13-toggles-idle-screensaver.md>

---

## Stop a docked laptop's internal scale jumping back to 2 by itself

`internal-scale-snaps-back-to-2-nwg-displays` · severity: **high** · frequency: **common** · applies to: `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** On a docked laptop the internal panel's scale keeps jumping back to 2 every couple of seconds, all by itself, no matter what you set in the display panel or in `monitors.lua`. Everything on the laptop screen is comically huge. Some users see the same reset only after the screensaver/lock screen runs.

**Cause.** `omarchy-hyprland-monitor-clamshell` runs a 2-second `sync_internal_scale` poll whenever a laptop has an external monitor active. It reads the wanted scale out of `monitors.lua` with a *line-anchored* regex that only matches when `hl.monitor({` and `output = "eDP-1"` are on the same line. GUI tools like `nwg-displays` write each monitor as a multi-line block, so the grep finds nothing, every fallback misses, and `read_monitor_scale` returns its hardcoded default of `2`, which the poll then re-applies twice a second.

**Fix.**

Rewrite each monitor rule in `~/.config/hypr/monitors.lua` as a single line so the poll can read it:

```lua
-- multi-line block written by nwg-displays: NOT matched
-- hl.monitor({
--     output = "eDP-1",
--     mode = "1920x1080@60.0",
--     position = "1536x0",
--     scale = 1.25
-- })

-- single line: matched by the clamshell poll
hl.monitor({ output = "eDP-1", mode = "1920x1080@60.0", position = "1536x0", scale = 1.25 })
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "0x0", scale = 1 })
```

Then `hyprctl reload`. If you want to confirm the poll is the culprit, watch it fight you:

```bash
watch -n1 "hyprctl monitors -j | jq -c '.[] | {name, scale}'"
```

**Verify.** The scale reported by `hyprctl monitors -j | jq -c '.[] | {name,scale}'` stays constant for a full minute while docked.

Sources: <https://github.com/basecamp/omarchy/issues/8335> · <https://github.com/basecamp/omarchy/issues/7301>

---

## Bring the laptop panel back after unplugging the external monitor

`laptop-display-stays-dark-after-external-unplug` · severity: **high** · frequency: **common** · applies to: `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** You disabled the laptop panel with Super+Ctrl+Delete to work external-only, then later unplugged the external monitor, and the laptop screen stays completely black. It came back automatically on Omarchy 3.x. `hyprctl monitors` still lists the monitor you unplugged.

**Cause.** Omarchy 4's `omarchy-hyprland-monitor-internal recover` gates on `omarchy-hyprland-monitor-external-active`, which asks `hyprctl monitors all -j`. On cable removal Hyprland does not always drop the output from its list immediately, so that check still says an external is active and `recover()` returns early without deleting the disable toggle or reloading. (Omarchy 3.x checked `/sys/class/drm/card*-*/status` directly instead.)

**Fix.**

Blindly (screen is black) or from a TTY / SSH session, delete the toggle file and reload:

```bash
rm -f ~/.local/state/omarchy/toggles/hypr/internal-monitor-disable.lua
rm -f ~/.local/state/omarchy/toggles/hypr/internal-monitor-clamshell.lua
hyprctl reload
hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'
```

Or use the shipped recovery helper, which checks real DRM status rather than Hyprland's cached list:

```bash
omarchy-hw-recover-internal-monitor
hyprctl reload
```

To avoid it recurring, re-enable the panel *before* unplugging (Super+Ctrl+Delete again).

**Verify.** `hyprctl monitors -j | jq -c '.[] | {name, disabled, width, height}'` shows `eDP-1` present, not disabled, with a non-zero mode, and the panel lights up.

Sources: <https://github.com/basecamp/omarchy/issues/7228> · <https://github.com/basecamp/omarchy/issues/7209> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-internal> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hw-recover-internal-monitor>

---

## Recover a monitor that stays black because it was switched off at boot

`monitor-powered-off-at-boot-black-0x0` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `omarchy`, `wayland`

**Symptom.** A monitor that was switched off, or on a different input, when you booted stays black afterwards even once you power it on. `hyprctl monitors all -j` lists it as enabled with a width and height of 0. Pressing the monitor's own power button changes nothing, because that fires no hotplug event. Unplugging and replugging the cable often does recover it, since that does fire a hotplug, but on a laptop dock or a panel you cannot reach that is not an option.

**Cause.** A display that is switched off, or on another input, answers the probe with a partial EDID that carries no video modes. Hyprland brings the output up anyway with no mode, so it reports 0x0 and stays black. It does retry, but only three times at one second intervals (`CMonitor::scheduleModeRetry`, `MAX_MODE_RETRIES = 3`, `src/output/Monitor.cpp` on v0.56.2), and then gives up for good. Powering the panel on afterwards fires no DRM hotplug event, so nothing asks the compositor to look again, and a reload is the only thing that re-reads the connector. Omarchy 4 fills that gap in userspace: `omarchy-hyprland-monitor-watch` runs a `recover_modeless` loop that polls `omarchy-hyprland-monitor-modeless` and issues `hyprctl reload` on an exponential backoff capped at 60 seconds until the output reports a mode.

> **Audit corrected this record.** Checked against Hyprland v0.56.2 source, the kernel DRM sysfs source, the installed omarchy 4.0.2-1 package on this workstation, and the Arch KMS wiki. Four defects. First, the `danger` names systemd-boot `/boot/loader/entries/*.conf` and GRUB `/etc/default/grub`, neither of which exists on a stock Omarchy 4 install. Confirmed on this machine that Omarchy 4 boots a UKI through Limine: `/etc/limine-entry-tool.d/omarchy-defaults.conf` and `omarchy-uki.conf` are owned by omarchy-settings 4.0.2-1 and carry `KERNEL_CMDLINE[default]+=`, and `/usr/lib/limine/limine-common-functions` lines 99 to 129 load `/usr/share/limine-entry-tool.d/*.conf`, then `/etc/limine-entry-tool.d/*.conf`, then `/etc/default/limine` at highest priority. `/usr/bin/limine-update` runs `limine-install --no-efi-register` and `limine-mkinitcpio`, which is what rebuilds the UKI. Second, the cause claims Hyprland never retries. It retries three times at one second intervals: `CMonitor::scheduleModeRetry` in `src/output/Monitor.cpp` with `MAX_MODE_RETRIES = 3`, then gives up permanently. More importantly the record omits that Omarchy 4 already recovers this by itself. `omarchy-hyprland-monitor-watch` is launched from `/usr/share/omarchy/default/hypr/autostart.lua`, and its `recover_modeless` function polls `omarchy-hyprland-monitor-modeless` and issues `hyprctl reload` on a backoff capped at 60 seconds until a mode appears. That process is live here as PID 2316. Third, the `off` then `on` then `detect` sysfs sequence is wrong and dangerous. `status_store` in `drivers/gpu/drm/drm_sysfs.c` maps `off` to `DRM_FORCE_OFF`, `on` to `DRM_FORCE_ON` and `detect` to clearing the force, and re-probes whenever the force changed or is zero, so only the final `detect` does useful work while the first two leave a connector forced until something writes `detect` back. That same function emits no hotplug event, which is exactly why the record's `hyprctl reload` is needed and why powering a panel on changes nothing on its own. Fourth, the record gave no route in when the black monitor is the only one, which is the whole point of the problem. On duplication with `monitor-config-ignored-name-or-mode`: only the cause sentence overlaps. This record uniquely holds the detection test, the DRM re-probe, the kernel `video=` pin and the Omarchy watcher. The sibling holds mode and scale matching for rules that are accepted but ignored. Merging is an operator call, but they are not the same failure. `omarchy-hw-recover-internal-monitor` is NOT the recovery for this and is not cited here, correctly: read in full, it only removes `~/.local/state/omarchy/toggles/hypr/internal-monitor-disable.lua` when `omarchy-hw-external-monitors` reports no external panel, driven by the oneshot user unit `omarchy-recover-internal-monitor.service` before `graphical-session-pre.target`. It has nothing to do with a modeless output. Confirmed live on this machine: the four DRM connectors are `card1-DP-1`, `card1-DP-2`, `card1-DP-3` and `card1-HDMI-A-1`, only HDMI-A-1 connected, and `hyprctl monitors all -j` carries the `name`, `width`, `height` and `disabled` fields the detection and verify commands read. NOT exercised: nothing was written, no reload or re-probe was run, and no monitor was powered off, so the recovery sequence itself is reasoned from source rather than performed. I also could not list `/boot` to confirm the Limine fallback entry, because it is a vfat ESP mounted dmask=0077 and I was not to use sudo.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Editing kernel parameters touches the bootloader, and a mistake there can stop the machine booting. On Omarchy 4 that is Limine with a UKI: the drop-ins are `/etc/limine-entry-tool.d/*.conf` and `/etc/default/limine`, and `sudo limine-update` rebuilds `/boot/EFI/Linux/omarchy_linux.efi`. There is no `/boot/loader/entries` and no `/etc/default/grub` on a stock Omarchy 4 install, so advice naming those paths is written for a different system. Omarchy's `/etc/limine-entry-tool.d/omarchy-uki.conf` sets `ENABLE_LIMINE_FALLBACK=yes` and a `BOOT_ORDER` that includes fallback and Snapper snapshot entries, so the boot menu should offer something older, but keep a live USB handy rather than relying on that. Separately, writing `off` or `on` to a connector's `/sys/class/drm/*/status` forces that connector's state until you write `detect` back or reboot. Aim it at the wrong connector and you blank a monitor that was working.

**Fix.**

**On Omarchy 4 this usually recovers itself.** `omarchy-hyprland-monitor-watch` is started from `/usr/share/omarchy/default/hypr/autostart.lua` and runs for the life of the session. Power the monitor on, or select the right input, and wait up to a minute. Check the watcher is alive first, from a working screen or over ssh:

```bash
pgrep -af omarchy-hyprland-monitor-watch
```

**Detect the state.** This is the exact test Omarchy's own `omarchy-hyprland-monitor-modeless` runs, and it works on any Hyprland:

```bash
hyprctl monitors all -j | jq -c '.[] | select(.disabled != true and (.width == 0 or .height == 0)) | {name,width,height}'
```

**If the black monitor is your only screen, you need another way in.** The session is running fine and only that output has no mode, so ssh from another machine is the reliable route. `Ctrl+Alt+F2` is not: the console draws on the same dead connector, so the TTY is black too.

**Manual recovery on any Hyprland 0.55+ with a Lua config.** Power the monitor on, then reload. A reload is what re-reads the connector, and it needs no root:

```bash
hyprctl reload
```

**If a reload is not enough, force a DRM re-probe.** This needs root. Write `detect` and nothing else: per `status_store` in `drivers/gpu/drm/drm_sysfs.c`, `detect` clears any forced state and re-probes, while `off` sets `DRM_FORCE_OFF` and `on` sets `DRM_FORCE_ON` and either one sticks until something writes `detect` back. List your real connector names first:

```bash
for p in /sys/class/drm/*/status; do echo "$p: $(cat "$p")"; done
```

```bash
echo detect | sudo tee /sys/class/drm/card1-HDMI-A-1/status   # use your own connector
hyprctl reload
```

The write re-probes but sends no hotplug event, so the `hyprctl reload` is still needed.

**Pin an explicit mode** in `~/.config/hypr/monitors.lua` so Hyprland does not depend on the EDID. When the named resolution is in no driver mode list, Hyprland falls through to trying it as a custom DRM mode, which the driver may still reject:

```lua
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "auto", scale = 1 })
```

**Last resort: force the mode from the kernel command line**, so it is set before the compositor starts:

```
video=HDMI-A-1:1920x1080@60
```

*Omarchy 4 (Limine with a UKI).* Add a drop-in rather than editing a packaged file. `/etc/limine-entry-tool.d/*.conf` and `/etc/default/limine` are both read by `/usr/lib/limine/limine-common-functions`, the latter at highest priority:

```bash
printf 'KERNEL_CMDLINE[default]+=" video=HDMI-A-1:1920x1080@60"\n' \
  | sudo tee /etc/limine-entry-tool.d/99-force-monitor-mode.conf
sudo limine-update
```

`limine-update` runs `limine-install --no-efi-register` and `limine-mkinitcpio`, which rebuilds the UKI at `/boot/EFI/Linux/omarchy_linux.efi` with the new command line. Confirm afterwards with `cat /proc/cmdline` on the next boot.

*Plain Arch.* systemd-boot: append it to the `options` line in `/boot/loader/entries/*.conf`. GRUB: append it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then run `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

**Verify.** `hyprctl monitors all -j | jq -c '.[] | {name,width,height}'` reports a non-zero width and height for the output, and the screen shows a picture. On Omarchy 4, `omarchy-hyprland-monitor-modeless` exits 1 when no enabled output is modeless, 0 while one still is, and 2 when the compositor cannot answer.

Sources: <https://wiki.archlinux.org/title/Kernel_mode_setting> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-modeless> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-watch> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/output/Monitor.cpp> · <https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/drivers/gpu/drm/drm_sysfs.c?h=v6.17>

---

## Override a firmware EDID when the monitor reports garbage or none (KVM, long HDMI run, cheap adapter)

`edid-override-for-bad-or-missing-monitor-edid` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `grub`, `hyprland`, `kvm`, `laptop`, `limine`, `manjaro`, `mkinitcpio`, `omarchy`, `omarchy-4`, `systemd-boot`, `wayland`

**Symptom.** Through a KVM switch, a 15 m HDMI run, or a USB-C→HDMI dongle, the monitor comes up at 1024x768 or 640x480 and `hyprctl monitors all` lists only two or three junk modes. The native 2560x1440 is simply not there. Sometimes the output shows up enabled but `0x0`, or the display is not detected at all. Plugged straight into the GPU with a short cable it is perfect, so the panel is fine. The EDID is being mangled in transit.

**Cause.** The monitor's EDID is read over the DDC/I²C sideband channel, which is the first thing to fail on a marginal link. A KVM, a long passive cable, or a cheap active adapter can return a truncated, corrupted, or empty EDID. The kernel then falls back to a generic mode list and the compositor can only offer what the kernel gave it. Arch's KMS page states this directly: *"If your native resolution is not automatically configured or no display at all is detected, then your monitor might send none or just a skewed EDID file. The kernel will try to catch this case and will set one of the most typical resolutions."* The remedy is to hand the kernel a known-good EDID binary for that connector.

> **Audit corrected this record.** Almost everything is verified verbatim against the Arch KMS page: the quoted sentence about a skewed or missing EDID, `/usr/lib/firmware/edid/`, `drm.edid_firmware=edid/file.bin`, the `CONNECTOR:` scoping, the comma-separated multi-connector form, `cat file > /sys/kernel/debug/dri/0/HDMI-A-2/edid_override`, `echo -n reset > ...edid_override`, `echo 1 > ...trigger_hotplug`, the lockdown-mode caveat, `echo edid/file.bin > /sys/module/drm/parameters/edid_firmware` taking effect only for newly plugged displays, the `video=<conn>:<xres>x<yres>[M][R][-<bpp>][@<refresh>][i][m][eDd]` syntax, the `video=DVI-I-1:1024x768@85 video=TV-1:d` example, and the note that `video=` "is useful for all Wayland compositors". `read-edid` (providing `get-edid`) is in `extra`. The Limine claims hold: `/etc/limine-entry-tool.d/omarchy-defaults.conf` exists with exactly the `KERNEL_CMDLINE[default]+=" ... "` form and `ENABLE_UKI=yes`, `limine-update` is a real command Omarchy calls, and `/etc/mkinitcpio.conf.d/` is a directory Omarchy already populates with `kms` in HOOKS (so the early-KMS warning is right). The gap is step 4: on Omarchy 4 the initramfs *and the UKI Limine actually boots* are rebuilt by `limine-mkinitcpio`, not by `mkinitcpio -P`. Omarchy's own scripts make this explicit: `omarchy-hibernation-setup` writes a `KERNEL_CMDLINE` drop-in and then runs `sudo limine-mkinitcpio` with the comment "limine-mkinitcpio rebuilds initramfs/UKI for all kernels and updates the /boot/limine.conf entries via limine-entry-tool", and `omarchy-plymouth-set` uses `sudo mkinitcpio -P` only as the fallback when `limine-mkinitcpio` is absent. A user who runs `mkinitcpio -P` and reboots may find the EDID silently absent from the UKI. Also minor: the connector-discovery loop's `card?-` pattern breaks on `card10` and above.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A wrong or corrupt EDID binary can leave you with no display at all from early boot onward, before any TTY is usable. Always test with the `edid_override` debugfs path first. It is reversible with `echo -n reset` and survives nothing more than a reboot. Editing the kernel command line and running `mkinitcpio -P`/`limine-update` rewrites your boot entries: keep the fallback entry that Omarchy generates (`ENABLE_LIMINE_FALLBACK=yes`) and know how to reach the Limine menu, because if Direct Boot is on you may need to pick Limine from the firmware boot menu to get a rescue entry. Do not run `mkinitcpio -P` in the middle of an interrupted `pacman`/`omarchy update` transaction.

**Fix.**

Steps 1, 2, 3 and 5 and the `video=` alternative are correct as written. Two changes.

**Step 1: make the connector listing robust.** `${con#*/card?-}` only matches single-digit card numbers, so it silently mangles `card10-DP-1` on machines with several DRM devices. Use:

```bash
for p in /sys/class/drm/card*-*/status; do
  d=${p%/status}
  printf '%s\t%s\n' "${d##*/}" "$(cat "$p")"
done
```

That prints the full directory name (`card1-DP-1`), which is what you feed to `cp`. The connector name Hyprland uses is the part after the first `-` (`DP-1`).

**Step 4: rebuild the right image.** On Omarchy 4 (and any Limine + `limine-entry-tool` setup with `ENABLE_UKI=yes`), the cmdline and `FILES` are baked into a UKI that plain `mkinitcpio -P` does not regenerate the boot entry for. Write the drop-in as the record says:

```bash
sudo tee /etc/mkinitcpio.conf.d/edid.conf >/dev/null <<'EOF'
FILES+=(/usr/lib/firmware/edid/u2723qe.bin)
EOF
```

Then rebuild with the Limine-aware command, exactly as Omarchy's own `omarchy-hibernation-setup` and `omarchy-plymouth-set` do:

```bash
if command -v limine-mkinitcpio >/dev/null; then
  sudo limine-mkinitcpio      # rebuilds initramfs + UKI for all kernels, updates /boot/limine.conf
else
  sudo mkinitcpio -P          # plain mkinitcpio setups only
fi
```

If you also added the `KERNEL_CMDLINE` drop-in in step 3, `sudo limine-mkinitcpio` covers both. `sudo limine-update` also works but additionally re-deploys the bootloader binary and rebuilds a second time, which is why Omarchy prefers `limine-mkinitcpio` for a cmdline-only change.

**Verify before rebooting away from a working display:**

```bash
lsinitcpio /boot/initramfs-linux.img | grep -i edid   # or check the UKI was re-dated
cat /proc/cmdline                                      # after reboot, confirm drm.edid_firmware is present
```

**Verify.** After reboot, `hyprctl monitors all` lists the monitor's full `availableModes` including the native one, and `dmesg | grep -i edid` shows the firmware EDID being loaded rather than a fallback. `cat /sys/class/drm/card*-HDMI-A-2/edid | wc -c` should be 128 or 256 bytes, not 0.

Sources: <https://wiki.archlinux.org/rest.php/v1/page/Kernel_mode_setting> · <https://wiki.archlinux.org/title/Kernel_mode_setting> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/limine/default.conf> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md>

---

## Stop an HDMI TV blanking for a moment on every click

`hdmi-tv-flickers-black-on-every-click` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `omarchy`, `wayland`

**Symptom.** A TV or cheap monitor on HDMI blanks for about 0.2 s on every mouse click or window interaction, then recovers. The same cable, port and kernel are fine under Sway and in a plain TTY. Only Hyprland flickers. Disabling blur, animations, hardware cursors, `render:cm_enabled`, `render:direct_scanout` and `misc:vfr` changes nothing.

**Cause.** The TV renegotiates the HDMI link (or drops out of its low-latency mode) when the compositor changes what it presents. Hyprland's presentation path triggers this on some Intel i915 + consumer-TV combinations where Sway's does not. A closely related variant on AMD iGPUs: a DPMS-off from a screen blanker makes amdgpu emit a spurious connector hotplug that reads as disconnected, producing a metronomic black/on cycle and thousands of `Disabling output HDMI-A-2` lines in `hyprland.log`.

> **Audit corrected this record.** Both halves of the problem are real and well cited: hyprwm/Hyprland#13338 exists as 'Samsung Smart TV flickers on interaction via HDMI — works fine under Sway', and basecamp/omarchy#8689 exists as 'Lock screen alternates black <-> lock UI every ~13.5s on AMD iGPU over HDMI', matching the AMD spurious-hotplug variant. The option names in the symptom (render:cm_enabled, render:direct_scanout) are both real, the per-monitor `bitdepth = 8` and `vrr = 0` fields are valid per the Monitors page, and Super+Ctrl+I is confirmed bound to 'Toggle locking on idle' in default/hypr/bindings/utilities.lua. The one hard error is step 3: `vfr` is not in the misc category. The Variables page lists it under Debug (`debug:vfr`, bool, default true), so `hl.config({ misc = { vfr = false } })` targets a nonexistent option and will be rejected or silently ignored, leaving the user thinking they tested the workaround when they did not.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Work around it at the display and the compositor:

1. Turn off the TV's own picture processing: set the HDMI input's label to `PC` and enable Game Mode. This is what fixes it most often on Samsung/LG sets.
2. Pin a plain 60 Hz mode and 8-bit output so the link is never renegotiated:

```lua
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "0x0", scale = 1, bitdepth = 8, vrr = 0 })
```

3. Stop variable-frame-rate presentation from idling the link. `vfr` lives under `debug`, not `misc`, and `misc.vfr` does not exist:

```lua
hl.config({
  debug = { vfr = false },
  misc  = { vrr = 0 },
})
```

Leave `debug.vfr = false` in place only while testing. It is on by default to conserve power, so turn it back on if it makes no difference.

4. If the flicker only happens once the screen has been idle/locked, disable the blanker rather than the compositor. On Omarchy, check `journalctl --user -b | grep -c 'Disabling output'`. A large number confirms the spurious-hotplug variant. Toggle idle locking off with Super+Ctrl+I.

**Verify.** `grep -c 'Disabling output' ~/.local/share/hyprland/hyprland.log` (or `hyprctl rollinglog | grep 'Disabling output'`) stops growing, and clicking no longer blanks the panel.

Sources: <https://github.com/hyprwm/Hyprland/issues/13338> · <https://github.com/basecamp/omarchy/issues/8689> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Variables.md>

---

## Recover a laptop screen stuck black after turning brightness to the bottom

`backlight-trapped-at-zero-low-max-brightness` · severity: **high** · frequency: **rare** · applies to: `acpi-video`, `apple`, `hyprland`, `intel`, `laptop`, `omarchy`, `omarchy-4`

**Symptom.** I turned the brightness all the way down with Fn+F1 and the screen went completely black. Pressing Fn+F2 (brightness up) does nothing, so I cannot see anything to fix it. Shift+brightness-down does the same thing in one press. Reported on a 2012 13-inch MacBook Pro Retina and an Ivy Bridge HD 4000 laptop, both using `acpi_video0` with `max_brightness` 15.

**Cause.** Below 5%, `omarchy-brightness-display` steps one percent at a time. At 0% it computes a 1% target and runs `brightnessctl -d acpi_video0 set 1%`. With `max_brightness` 15, 1% is 0.15 of a raw step, which brightnessctl rounds to raw 0, so the brightness stays at 0 on every press and the up key can never climb out. The Shift+XF86MonBrightnessDown binding in `default/hypr/bindings/media.lua` runs `omarchy-brightness-display 1%`, which lands on the same raw 0 on these devices. Both are in 4.0.4-1 and on `quattro` as of 2026-10-04. The issue is open, and a reporter confirmed on 4.0.2-1 that a raw +1 step recovers the panel.

> **Audit corrected this record.** The cause holds. brightnessctl 0.5.1 percent_to_val is roundf(percent/100 * max), so 1% of 15 is raw 0, and omarchy-brightness-display turns +5% at 0% into an absolute 1%. Issue #8523 (open) confirms both reports. Two defects in the fix. First, it tells a user with a black screen to type blind, but the stock bindings in default/hypr/bindings/media.lua already escape: SHIFT + XF86MonBrightnessUp runs omarchy-brightness-display 100%, and ALT + XF86MonBrightnessUp runs +1%, which brightnessctl treats as relative and forces to at least one raw step (calc_value sets mod to 1 when rounding gives 0). Second, the prevention block leaves ALT + XF86MonBrightnessDown bound to omarchy-brightness-display 1%-. From raw 1 of 15 that is relative 5.67%, which rounds to raw 1, so brightnessctl forces -1 and lands on raw 0 again. The corrected fix adds the key escape first and unbinds the Alt variant too. --min-value=1 confirmed as brightnessctl 0.5.1's optional-argument form. Not exercised on a panel with max_brightness 15.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**Get the picture back with a key.** Press Shift+brightness-up (Shift+Fn+F2 where F2 needs Fn). Omarchy binds it to `omarchy-brightness-display 100%`, which sets full brightness and does not round to 0. Alt+brightness-up also works: it runs `omarchy-brightness-display +1%`, and brightnessctl always moves a relative change by at least one raw step.

If neither key is reachable, type this blind into a terminal (Super+Enter opens one), or run it over ssh. The value is a raw step, not a percentage:

```bash
brightnessctl -d "$(omarchy-hw-display)" set 5
```

**Check whether your panel is affected:**

```bash
omarchy-hw-display
cat /sys/class/backlight/$(omarchy-hw-display)/max_brightness
```

A `max_brightness` under 100 can round a 1% target to 0.

**Prevent it (Omarchy 4).** Replace the brightness-down bindings in `~/.config/hypr/bindings.lua` with raw steps that cannot fall below 1. Three default bindings can reach raw 0 on these panels: plain, Shift and Alt brightness-down. Swap `acpi_video0` for the name `omarchy-hw-display` printed:

```lua
hl.unbind("XF86MonBrightnessUp")
hl.unbind("XF86MonBrightnessDown")
hl.unbind("SHIFT + XF86MonBrightnessDown")
hl.unbind("ALT + XF86MonBrightnessDown")
o.bind("XF86MonBrightnessUp", "Brightness up", "brightnessctl -d acpi_video0 set +1", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Brightness down", "brightnessctl -d acpi_video0 --min-value=1 set 1-", { locked = true, repeating = true })
```

Shift+brightness-up and Alt+brightness-up keep their stock bindings, so the key escape above still works. These bindings skip Omarchy's on-screen brightness indicator.

**Verify.** Hold brightness-down until it stops, then press Alt+brightness-down a few times. `cat /sys/class/backlight/acpi_video0/brightness` reads 1, not 0, the panel is still faintly lit, and brightness-up raises it again.

Sources: <https://github.com/omacom/omarchy/issues/8523> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/bindings/media.lua> · <https://github.com/Hummer12007/brightnessctl/blob/0.5.1/brightnessctl.c>

---

## Fix Chromium and Electron apps looking soft on a fractionally scaled monitor

`electron-chromium-blurry-fractional-scale` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Chrome/Brave/Chromium, VS Code, Slack, Signal, Spotify and Discord look soft, fuzzy or double-scaled on a fractionally scaled monitor (e.g. 150%). Fonts have halos. Native GTK apps next to them look sharp.

**Cause.** Chromium/Electron apps that fall back to XWayland get bitmap-upscaled by the compositor. Even on native Wayland they follow GTK settings and ignore fractional factors unless told a device scale factor explicitly. Since Electron 38.2 Wayland is the default. Older builds need an ozone hint.

> **Audit corrected this record.** The problem and most of the fix are right: ~/.config/chromium-flags.conf and --force-device-scale-factor are documented on the Arch HiDPI/Chromium pages, ~/.config/electron-flags.conf is the documented Arch Electron config file, the slack.desktop Exec-copy pattern is straight off the HiDPI page, and Omarchy's default/hypr/envs.lua really does export ELECTRON_OZONE_PLATFORM_HINT and OZONE_PLATFORM. But the Electron advice is obsolete: the Arch Electron page states `--ozone-platform-hint=wayland (removed in Electron 38)` and uses `--ozone-platform=wayland` instead, so `--ozone-platform-hint=auto` is a dead flag in electron-flags.conf and in the Slack launcher. Two further problems. First, electron-flags.conf is only read by Arch's `electron` package and NOT by apps that bundle their own Electron (slack-desktop, signal-desktop), which need a per-app `~/.config/<app>-flags.conf` or the .desktop edit. Second, `hyprctl clients | grep -A2 xwayland` prints the lines *after* the xwayland field, so it never shows you which app it is.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Omarchy already exports `ELECTRON_OZONE_PLATFORM_HINT=wayland` and `OZONE_PLATFORM=wayland`. If an app still uses XWayland or renders blurry, force the scale factor.

Chromium (Arch's package reads this file, and Chromium 140+ is already Wayland by default, so the ozone flag is only needed on older builds):

```
# ~/.config/chromium-flags.conf
--force-device-scale-factor=1.5
--ozone-platform=wayland
```

Electron apps built against Arch's `electron` package:

```
# ~/.config/electron-flags.conf
--force-device-scale-factor=1.5
--ozone-platform=wayland
```

`--ozone-platform-hint` was removed in Electron 38, so use `--ozone-platform=wayland`. Note that `electron-flags.conf` is read only by Arch's `electron` package. Apps that bundle their own Electron (slack-desktop, signal-desktop, Discord) ignore it. Some of those read a per-app file instead, e.g. `~/.config/spotify-flags.conf`. For the rest, copy the launcher and edit `Exec=`:

```bash
cp /usr/share/applications/slack.desktop ~/.local/share/applications/
sed -i 's|^Exec=/usr/bin/slack|Exec=/usr/bin/slack --force-device-scale-factor=1.5 --ozone-platform=wayland|' \
  ~/.local/share/applications/slack.desktop
update-desktop-database ~/.local/share/applications
```

List which clients are actually on XWayland:

```bash
hyprctl clients -j | jq -r '.[] | select(.xwayland) | "\(.class)\t\(.title)"'
```

**Verify.** `hyprctl clients | grep -B4 'xwayland: 1'` no longer lists the app, and its UI text is crisp at the fractional scale.

Sources: <https://wiki.archlinux.org/title/HiDPI> · <https://wiki.archlinux.org/title/Wayland> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/hyprwm/Hyprland/issues/4677>

---

## Fix 'keyword can't work with non-legacy parsers' from monitor scripts

`hyprctl-keyword-monitor-non-legacy-parser` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`, `wayland`

**Symptom.** Any script or command that used to work now fails: `hyprctl keyword monitor "HDMI-A-1,2560x1440@59.95,1600x0,1"` returns `keyword can't work with non-legacy parsers. Use eval.` The Omarchy display panel's enable/disable switch also appears to do nothing. You flip it and the monitor stays exactly as it was.

**Cause.** Hyprland 0.55 replaced hyprlang with a Lua config parser (Omarchy 4 "Quattro" ships Hyprland 0.56.x with Lua configs). `hyprctl keyword` only speaks the legacy hyprlang parser, so it refuses every monitor command outright. Scripts, dotfiles and blog posts written for Hyprland <= 0.54 silently stop working, and Omarchy's own display widget shipped the old call for a while (fixed in PR #7036).

**Fix.**

Send monitor changes through `hyprctl eval` with a Lua `hl.monitor` call instead of `hyprctl keyword`.

```bash
# WRONG on Hyprland 0.55+ / Omarchy 4
hyprctl keyword monitor "HDMI-A-1,2560x1440@59.95,1600x0,1"

# RIGHT
hyprctl eval 'hl.monitor({ output = "HDMI-A-1", mode = "2560x1440@59.95", position = "1600x0", scale = 1 })'

# disable / re-enable an output at runtime
hyprctl eval 'hl.monitor({ output = "HDMI-A-1", disabled = true })'
hyprctl eval 'hl.monitor({ output = "HDMI-A-1", disabled = false })'
```

To make it permanent, put the same call in `~/.config/hypr/monitors.lua`:

```lua
hl.monitor({ output = "HDMI-A-1", mode = "2560x1440@59.95", position = "1600x0", scale = 1 })
```

On Hyprland <= 0.54 / Omarchy 3.x the file is `~/.config/hypr/monitors.conf` and the syntax is `monitor=HDMI-A-1,2560x1440@59.95,1600x0,1`.

**Verify.** `hyprctl eval '...'` prints `ok` and `hyprctl monitors` immediately shows the new mode/position/scale.

Sources: <https://github.com/basecamp/omarchy/pull/7036> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md>

---

## Pick a fractional scale Hyprland accepts instead of 'Invalid scale'

`hyprland-invalid-scale-not-divisible` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** You set a fractional scale like 1.75 and Hyprland refuses it: an "Invalid scale" / "scale is not divisible by integer" config error banner appears, or the display silently comes up at 1 or at some other scale you did not pick. Text is either too small or too big and nothing you type in the config changes it.

**Cause.** Hyprland only accepts a scale that turns the monitor's pixel resolution into whole logical pixels, in 1/120 steps. Formally, `round(scale*120)` must divide `gcd(width*120, height*120)`. 1920x1080/1.4 = 1371.43x771.43, so 1.4 is rejected. The valid set differs per resolution: 1.5 is fine on 1920x1080 and 3840x2160 but invalid on 2560x1440, and 1.75 is invalid on all three.

> **Audit corrected this record.** The mechanism, the awk helper and the preset list are all verified correct. The awk function is byte-for-byte Omarchy quattro's clean_scale() from bin/omarchy-hyprland-monitor-scaling, SCALES=(1 1.25 1.6 2 3 4) matches exactly, and the wiki confirms the divisibility rule. The resolution-specific claims check out (1.5 valid on 1920x1080 and 3840x2160, invalid on 2560x1440, and 1.75 invalid on all three). But the worked example's stated output is wrong: gcd(2560*120,1440*120)=19200, k=210, and the smallest divisor of 19200 that is >=210 is 240, so `cleanscale 1.75 2560 1440` prints 2, not 1.777. A user who sees 2 will think the helper is broken. Also `omarchy hyprland monitor scaling` accepts any value 1..4, not only the presets.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Compute a clean scale for your exact mode before writing it into the config:

```bash
# usage: cleanscale <wanted> <width> <height>
cleanscale() {
  awk -v s="$1" -v w="$2" -v h="$3" '
    function gcd(a,b,t){while(b){t=a%b;a=b;b=t}return a}
    BEGIN{g=gcd(w*120,h*120);k=int(s*120+0.5);if(k>g)k=g;while(g%k!=0)k++;printf "%g\n",k/120}'
}
cleanscale 1.75 2560 1440   # -> 2      (rounds UP to the next legal value)
cleanscale 1.75 1920 1080   # -> 1.875
cleanscale 1.6  2560 1440   # -> 1.6    (already legal)
```

Note the helper rounds *up* to the next legal value, so a request can jump a long way (1.75 -> 2 on 1440p). Then set the value it printed (Hyprland 0.55+ / Omarchy 4, `~/.config/hypr/monitors.lua`):

```lua
hl.monitor({ output = "DP-1", mode = "2560x1440@165", position = "0x0", scale = 1.6 })
```

On Omarchy just use the helper, which does this rounding for you and persists it:

```bash
omarchy hyprland monitor scaling 1.6    # or: up / down
```

`up`/`down` step through the presets `1 1.25 1.6 2 3 4`. An explicit argument may be any value between 1 and 4 and is rounded to the nearest legal scale for the focused monitor.

**Verify.** `hyprctl monitors | grep -E 'scale|^Monitor'` shows the scale you asked for and no config-error banner is drawn on the screen.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-scaling>

---

## Mirroring one display onto another, and why the mirror vanishes from hyprctl monitors

`mirroring-a-display-and-hidden-mirror-outputs` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** I need to mirror my laptop screen onto a projector for a presentation, or mirror the internal panel while docked. Giving both monitors the same `position = "0x0"` does not mirror anything. Hyprland raises a warning notification that the layout is invalid and then leaves both outputs sitting on top of each other. And once I do get a real mirror working, the mirrored output disappears completely from `hyprctl monitors`, so my status bar and my own scripts think the monitor was unplugged. `hl.get_monitors()` in Lua does not list it either, and `hl.get_monitor(id)` on it returns nil.

**Cause.** Mirroring is not done with positions. It is a dedicated `mirror` field on the monitor rule that names the output to copy. Once an output is mirroring another it is no longer an independent output in the layout, so Hyprland deliberately omits it from `hyprctl monitors`. It only appears in `hyprctl monitors all`. The same applies to the Lua API: `hl.get_monitors()` returns only enabled, non-mirrored outputs, which is why `HL.Monitor.is_mirror` reads as useless (hyprwm/Hyprland discussion #14645). Mirroring is also a straight scanout copy, not a re-render: a 1080p source mirrored onto a 4K panel stays 1080p, and mismatched aspect ratios get squished or stretched.

> **Audit corrected this record.** Re-checked every claim against Hyprland v0.56.2 source rather than only the wiki, plus the installed omarchy 4.0.2-1 and hyprland 0.56.2-1 packages on this workstation. The core of the record holds and is now proven at source level, not just documented. `hyprctl monitors` really does hide mirrors: `monitorsRequest` in `src/debug/HyprCtl.cpp` line 327 picks `allMonitors()` for `monitors all` and `monitors()` otherwise, and `CMonitorStateTracker` in `src/state/MonitorState.cpp` lines 33 to 36 erases anything where `isMirror()` is true and skips outputs that are not enabled or are mirrors. The Lua half holds too: `hlGetMonitors` in `src/config/lua/bindings/LuaBindingsQuery.cpp` iterates `monitors()`, so mirrors and disabled outputs are absent, and the shipped stub `/usr/share/hypr/stubs/hl.meta.lua` line 847 declares `get_monitors fun(): HL.Monitor[]` with no argument, confirming PR 14693 (merged 2026-08-21) is still not in a tagged release. v0.56.2 released 2026-08-05 is still the newest upstream release, so the first-pass note's forward-looking warning is still true and worth keeping. Discussion 14645 was read in full and does support the claim: the author reports `hl.get_monitor(id)` returning nil for a mirrored output, and a commenter states `hl.get_monitors()` only lists enabled monitors. The `mirror` field and both example forms match `content/configuring/core/monitors/_index.md` in the wiki repo, including the 'will not re-render' and squish-and-stretch wording, and the stub carries `---@field mirror? string` at line 579. Reading `/usr/share/omarchy/bin/omarchy-hyprland-monitor-internal-mirror` on the installed package confirms on, off, toggle and recover, the `^(eDP|LVDS|DSI)-` exclusion, the `internal-monitor-mirror.lua` state file, forcing the `internal-monitor-disable` toggle off first, and the trailing `hyprctl reload`. The keybind is at `default/hypr/bindings/utilities.lua` line 33 as claimed. `omarchy-hyprland-toggle-enabled` is a one-line file test on the flag path, so the verify claim is exact. Two defects. First, the symptom says overlapping positions make Hyprland 'shove one aside'. It does not. `CMonitorLayoutController::checkOverlapsAndNotify` in `src/state/MonitorLayoutController.cpp` logs an error and raises a 15 second warning notification, then breaks. The overlap is left in place, which is worse than the record implies, because the user sees a warning and two genuinely overlapping outputs. Second, the record presents the Omarchy toggle as the Omarchy 4 way to mirror without saying it is laptop only. `omarchy-hyprland-monitor-laptop` returns the first output matching `^(eDP|LVDS|DSI)-`, so on a desktop `INTERNAL` is empty and the script exits 1 with a 'No laptop monitor found to mirror' notification. The menu entry at `default/omarchy/omarchy-menu.jsonc` line 70 is gated on `omarchy-hw-laptop`, but the keybind is not, so a desktop user following this record gets a failure notification and no explanation. The hand-written `mirror` rule is the answer on a desktop. One dead source found and replaced: the cited raw wiki URL under `content/Configuring/Basics/Monitors.md` returns 404 because the wiki was reorganised to `content/configuring/core/monitors/_index.md`. The three `basecamp/omarchy` raw URLs still redirect and still serve, but the repo was renamed to `omacom/omarchy`, so they are swapped for canonical ones rather than deleted. NOT exercised: nothing was configured, no mirror was enabled, no reload or dispatch was run, and this workstation has a single connected output (HDMI-A-1, Microstep MSI G274QPF), so the disappearance from `hyprctl monitors` was confirmed from source and from Omarchy's own comment, not observed live.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** If you write a `mirror` rule for the only external output and then disable the source panel (e.g. the internal-display toggle), you can end up with no monitor showing anything. Omarchy guards against this by forcing the `internal-monitor-disable` toggle off before enabling the mirror. If you hand-roll it, keep a TTY available (`Ctrl+Alt+F2`) and be ready to run `hyprctl reload` after reverting monitors.lua. A catch-all `output = ""` mirror rule also captures every future display, including a second desk monitor you wanted as an extended screen.

**Fix.**

**Mirror by hand (Hyprland 0.55+ Lua, `~/.config/hypr/monitors.lua`)**

The rule goes on the output that should *show* the copy, and `mirror` names the source:

```lua
-- eDP-1 is the real output; HDMI-A-1 shows a copy of it
hl.monitor({ output = "eDP-1",    mode = "preferred", position = "0x0",  scale = 1 })
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1, mirror = "eDP-1" })
```

On a desktop the same shape works with two external outputs. Read your own connector names out of `hyprctl monitors all` first rather than copying `eDP-1`.

A catch-all so *any* newly plugged screen mirrors the source (useful for projectors whose connector name you do not know in advance):

```lua
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1, mirror = "eDP-1" })
```

Apply without restarting the session:

```bash
hyprctl reload
```

**On Omarchy 4 there is a shipped toggle, but it is laptop only.** It mirrors the internal panel onto the first external output, so it does nothing on a desktop. `Super + Ctrl + Alt + Delete`, or from a terminal:

```bash
omarchy-hyprland-monitor-internal-mirror toggle   # on/off/toggle/recover
```

It reads the internal panel from `omarchy-hyprland-monitor-laptop`, which matches `^(eDP|LVDS|DSI)-`. With no such output it sends a "No laptop monitor found to mirror" notification and exits 1. Otherwise it picks the first active non-`eDP`/`LVDS`/`DSI` output, forces the `internal-monitor-disable` toggle off, writes a generated rule to `~/.local/state/omarchy/toggles/hypr/internal-monitor-mirror.lua`, and runs `hyprctl reload`. The Omarchy menu entry for it is gated on `omarchy-hw-laptop` and is hidden on a desktop, but the keybind is not gated, so pressing it on a desktop just produces the notification.

Turn it off explicitly with:

```bash
omarchy-hyprland-monitor-internal-mirror off
```

**Seeing the mirrored output again.** Plain `monitors` will not show it. Use:

```bash
hyprctl monitors all
hyprctl monitors all -j | jq -r '.[] | "\(.name)\tdisabled=\(.disabled)\tmirrorOf=\(.mirrorOf)\t\(.width)x\(.height)@\(.refreshRate)"'
```

This is not an accident of the CLI. In Hyprland 0.56.2 the compositor keeps two lists, and the one behind plain `monitors` has every disabled and every mirroring output removed from it. `hyprctl monitors all` reads the other list. Omarchy's own `omarchy-hyprland-monitor-modeless` documents the same thing: *"Mirrors are absent from plain `monitors`, hence `all` plus an explicit disabled filter."* Any script of yours that counts monitors must use `monitors all` too, or it will conclude a mirrored screen is gone.

The Lua API has the same blind spot and no `all` option in 0.56.2: `hl.get_monitors()` takes no arguments and returns only enabled, non-mirrored outputs, and `hl.get_monitor(id)` on a mirror returns nil. Track mirror state yourself, for example by testing for the Omarchy toggle file, until a release ships the table form of `hl.get_monitors`.

**Expectation setting:** the mirror is a scanout copy, not a re-render. Mirroring 1920x1080 onto a 3840x2160 panel gives you a 1080p image, and mirroring 16:10 onto 16:9 will stretch. If you need a sharp image on the projector, set both outputs to the same mode instead of mirroring, or accept the source resolution.

**Verify.** `hyprctl monitors` should now list only the source output, while `hyprctl monitors all` lists both. Confirm the copy is live by moving a window. It should appear on both screens simultaneously. On Omarchy, `omarchy-hyprland-toggle-enabled internal-monitor-mirror` exits 0 while mirroring is on.

Sources: <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://github.com/hyprwm/Hyprland/discussions/14645> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/monitors/_index.md> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/state/MonitorState.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/state/MonitorLayoutController.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/debug/HyprCtl.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsQuery.cpp> · <https://github.com/hyprwm/Hyprland/pull/14693> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-internal-mirror> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-modeless> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/bindings/utilities.lua>

---

## Get a 120, 144 or 165 Hz panel out of 60 Hz

`monitor-stuck-at-60hz-high-refresh` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** A 120, 144, 165 or 240 Hz panel runs at 60 Hz, or at some rate below the one the panel is sold at. `hyprctl monitors` reports the low rate as the current mode. Two different shapes look identical from the chair: either the fast mode is missing from `availableModes` entirely, or it is listed there and a matching `mode` in the config still does not take. There is no config error and no message on screen. Motion feels sluggish and mouse movement stutters.

**Cause.** Four different faults land on the same low refresh rate, and they need different answers.

1. **The link cannot carry the mode.** HDMI 2.0b carries about 14.4 Gbps of payload, which is not enough for 2560x1440 at 165 Hz, and a DisplayPort link that trains at fewer lanes or a lower bit rate loses its top modes. A marginal cable can train and then fail the modeset. When the link is the limit the fast mode is usually absent from `availableModes` altogether, because the kernel filters modes the link cannot carry.

2. **The EDID does not offer the mode.** A monitor powered off at boot answers with a partial EDID carrying no video modes at all, which is the case Omarchy detects with `omarchy-hyprland-monitor-modeless`. A KVM, a splitter or a long passive adapter can present a reduced EDID the same way.

3. **Hyprland is asked for a mode it cannot set and silently lands on a neighbour.** On 0.56.2 an explicit `mode` is not ignored. `CMonitor::applyMonitorRule` in `src/output/Monitor.cpp` sorts every driver mode by closeness to the request, keeps the best three, appends the exact request as a custom mode when the closest match is more than 1 off, then tries them in reverse order and takes the first that passes the atomic test. A request for `@144` that fails the test therefore lands on 120 or on 143.91, and `@165` on a link that tops out at 144 lands on 144, with no config error either way. The rejected attempts are logged at error level as `Monitor <name>: REJECTED available mode ...`.

4. **No `mode` is set, so `preferred` is in force.** With no resolution in the rule, Hyprland tries the EDID preferred timing first and then the first three modes the driver reports. On many panels the preferred timing is the 60 Hz descriptor rather than the fast one. Omarchy 4 ships `mode = "preferred"` in the catch-all rule of `/usr/share/omarchy/config/hypr/monitors.lua`, so this is the state out of the box. A request to change that default to `highrr` was opened as omarchy pull request 161 and closed without merging.

> **Audit corrected this record.** Re-audited on this Omarchy 4.0.2-1 workstation (hyprland 0.56.2-1, kernel 7.1.9, nvidia-open-dkms 610.57.04-1) against the Hyprland 0.56.2 source, the current Hyprland wiki and the two cited GitHub threads read in full. The problem is real and very common, but the record's diagnosis is wrong in a way that sends the reader to the wrong fix, and three of its commands do not work as written. First, the mechanism. The cause claims Hyprland 0.55.x/0.56.x ignores an explicit `mode` on NVIDIA. It does not. Read at tag v0.56.2, `src/output/Monitor.cpp` lines 757 to 940 sort every driver mode by closeness to the requested one, keep the best three, append the exact request as a custom mode when the closest is more than 1 off, try them in reverse and take the first that passes `m_state.test()`. A request that fails the atomic test silently lands on a neighbouring mode, which is exactly why a bad `@144` shows up as 120 or 143.91 and looks ignored. The same file shows `preferred` is not only the EDID preferred timing either: with no resolution in the rule it also queues the first three driver modes behind it, and there is a final catch-all that will try any mode at all. Second, the cause omits the two commonest real reasons a panel sits at 60, and they are the ones with different answers: a link that cannot carry the mode, and an EDID that does not offer it. This machine demonstrates the first. `hyprctl monitors all` here reports a 165 Hz Microstep MSI G274QPF on HDMI-A-1 whose `availableModes` top out at `2560x1440@144.00Hz`, with no 165 Hz entry anywhere, because HDMI 2.0b cannot carry it. Current mode reads `2560x1440@144.00101`. The record as written would have a reader edit monitors.lua forever chasing a mode the kernel never exposed. The modeless EDID case is real enough that Omarchy ships a detector for it, `/usr/share/omarchy/bin/omarchy-hyprland-monitor-modeless`, whose own comment says a monitor powered off at boot answers with a partial EDID carrying no video modes. Third, three command defects. `cat /sys/module/nvidia_drm/parameters/modeset` returns `Permission denied` unprivileged, confirmed by running it here, because the file is `-r-------- root root`. `sudo mkinitcpio -P` rebuilds nothing on Omarchy 4, confirmed here: `/etc/mkinitcpio.d/` contains zero files, so the command aborts with no presets found. The rebuild is `sudo limine-mkinitcpio`. And the danger field tells the reader to run `pacman -Syu`, which the Omarchy ALPM guard blocks. Fourth, an omission the reader will trip on: `highrr` sorts by rounded refresh rate first and resolution second, confirmed in the `addBest3Modes` lambda, so on a panel offering 1080p240 and 1440p165 it silently drops the resolution, and the wiki states the predefined modes cannot be combined. Fifth, the whole NVIDIA modeset step is now largely obsolete: Arch has enabled DRM since nvidia-utils 560.35.03-5, the 610 module default is on, and Omarchy's installer writes the file anyway. On sources, both hyprland-wiki blob URLs 404, confirmed with curl: the content moved to `content/configuring/core/monitors/` and `content/nvidia/`, so both go in `sources_remove` and are replaced with the canonical pages that return 200. The two kept sources do support the symptom but need reading with care and the record should not lean on either as a mechanism. omarchy pull request 161 is real, it reports exactly this (`preferred` landing on 60 Hz on a 4090 with a 120 Hz panel, `highrr` fixing it), and it is CLOSED and never merged, which is confirmed by Omarchy 4 still shipping `mode = "preferred"` in `/usr/share/omarchy/config/hypr/monitors.lua`, read on disk here. Hyprland issue 15210 exists but was auto-closed by the github-actions bot with "Users are no longer allowed to open issues themselves" fourteen seconds after it was opened, so it carries no maintainer triage and its own root cause analysis is a user's guess that the source contradicts. Severity `medium` and frequency `very-common` both stand and are left alone. NOT exercised: I changed no mode, scale or config on this workstation and ran no `hyprctl keyword`, `reload` or `dispatch`, so the corrected fix is argued from the 0.56.2 source, the wiki and read-only `hyprctl monitors` output rather than from a mode I set and watched. I also could not observe a `REJECTED available mode` line here, because every mode this box uses applies cleanly and the compositor log had rotated past session start. The commands in steps 1 to 3 were each run read-only on this machine and produce the output described.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Only the NVIDIA branch touches anything risky. Rebuilding the initramfs while a DKMS driver build is half finished can leave an image referencing a module that does not exist, which boots to a black screen, so confirm `dkms status` reports `installed` for every kernel first. Direct `pacman -Syu` is blocked on Omarchy by an ALPM guard and a bare `pacman -Sy` is a partial upgrade, so update with `omarchy update` and rebuild only after it has finished. An interrupted `sudo limine-mkinitcpio` leaves an unbootable UKI, so do not power cycle while it runs. Changing a monitor mode itself is safe and reversible: a mode the hardware cannot set is rejected and the compositor falls back to a working one rather than blanking permanently.

**Fix.**

**1. List every mode the driver actually offers.** This is the command that settles which of the four causes you have, and it needs no root:

```bash
hyprctl monitors all -j | jq -r '.[] | "\(.name)  \(.description)", (.availableModes[] | "    \(.)")'
```

**2. Read that list before editing any config.**

- **The fast mode is absent.** The link or the EDID is the limit, not Hyprland, and no config line conjures a mode the kernel did not expose. Check the physical path: a 165 Hz 1440p panel needs DisplayPort, because HDMI 2.0b cannot carry that mode at all. Try a shorter or certified cable, try a different port, and power the monitor on before the machine boots.
- **`availableModes` is empty, or the monitor sits at 0x0.** That is the modeless EDID case. Omarchy ships a check for it:

```bash
omarchy-hyprland-monitor-modeless; echo $?   # 0 means an enabled monitor has no modes
```

  Power cycle the monitor and replug the cable. Hyprland re-reads the EDID on hotplug.
- **The fast mode is listed.** Go to step 3.

**3. Ask for a mode that is in the list, copied verbatim.** The refresh rate has to match a listed rate, not the number printed on the box. In `~/.config/hypr/monitors.lua`:

```lua
hl.monitor({ output = "DP-1", mode = "2560x1440@143.91", position = "0x0", scale = 1 })
```

On Hyprland 0.54 and older, in `monitors.conf`: `monitor=DP-1,2560x1440@143.91,0x0,1`.

Then read back what was actually set, because the fallback is silent:

```bash
hyprctl -j monitors | jq -r '.[] | "\(.name) \(.width)x\(.height)@\(.refreshRate)"'
```

If the rate that comes back is not the one you asked for, the mode failed the atomic test rather than being ignored. The compositor log names what it rejected:

```bash
grep -E 'REJECTED|using available mode|using custom mode' "$XDG_RUNTIME_DIR"/hypr/*/hyprland.log
```

A mode that is listed but rejected is almost always bandwidth. Step one rate down the list and see whether that holds.

**4. `highrr` is a shortcut with a cost.** It picks the highest refresh rate and only then the resolution, so on a panel offering both `1920x1080@240` and `2560x1440@165` it gives you the 1080p mode. The predefined modes cannot be combined, so there is no way to ask for highest resolution and highest rate together. Use it only when you have read the mode list and know the top rate belongs to the resolution you want:

```lua
hl.monitor({ output = "", mode = "highrr", position = "auto", scale = 1 })
```

**5. NVIDIA: DRM mode setting is rarely the fault any more.** Arch has enabled it since `nvidia-utils` 560.35.03-5, the 610 series module defaults to on in the driver itself, and Omarchy's installer writes `/etc/modprobe.d/nvidia.conf` regardless. The parameter file is mode 0400, so an unprivileged `cat` returns `Permission denied` rather than an answer:

```bash
sudo cat /sys/module/nvidia_drm/parameters/modeset   # Y
```

Only if that prints `N`, write the file and rebuild the initramfs:

```bash
sudo tee /etc/modprobe.d/nvidia.conf >/dev/null <<'EOF'
options nvidia_drm modeset=1
EOF
```

The rebuild command is not the same on both systems:

```bash
sudo limine-mkinitcpio   # Omarchy 4, which boots a UKI through Limine
sudo mkinitcpio -P       # plain Arch, which has presets in /etc/mkinitcpio.d/
```

On Omarchy 4, `mkinitcpio -P` aborts with no presets found because `/etc/mkinitcpio.d/` is empty, so it rebuilds nothing and the reboot changes nothing.

**Verify.** ```bash
hyprctl -j monitors | jq -r '.[] | "\(.name) \(.width)x\(.height)@\(.refreshRate)"'
```

The rate you asked for has to come back as the *current* mode. Finding it in `availableModes` proves only that the driver offers it, which was true before the change as well.

Sources: <https://github.com/basecamp/omarchy/pull/161> · <https://github.com/hyprwm/Hyprland/issues/15210> · <https://wiki.hypr.land/configuring/core/monitors/> · <https://wiki.hypr.land/configuring/core/monitors/modes/> · <https://wiki.hypr.land/Nvidia/> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/output/Monitor.cpp> · <https://github.com/omacom/omarchy/pull/161> · <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks>

---

## Workspaces bound to a monitor pile onto the wrong screen and never go back after docking

`workspace-monitor-binding-lost-on-hotplug` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** I pin workspaces 1-5 to the external `DP-1` and 6-10 to the laptop panel. If I boot or log in undocked, every workspace is created on the laptop screen. Then I dock, the external monitor lights up, and workspaces 1-5 stay on the laptop. They never migrate back. Same thing after a monitor sleeps and wakes. Persistent workspaces also stop being persistent, and after a reboot my monitors sometimes come back as `DP-2`/`HDMI-A-3` instead of `DP-1`/`HDMI-A-1`, so the rules don't match at all any more.

**Cause.** A workspace rule's `monitor` field is applied when the workspace is *created*, not continuously. If the named output does not exist at that moment, Hyprland creates the workspace on whatever monitor is available, and nothing moves it later when the output appears. There is no rule condition that matches monitor state: the feature request for one, hyprwm/Hyprland #7049 ("Window/Workspace Rules to Match Monitors States"), was closed as *not planned*, so this is settled behaviour rather than a pending fix. Connector names are a separate, compounding hazard. DRM connector numbering is not stable across boots or across cable/port changes, so a rule pinned to `DP-1` can silently match nothing after a reboot. This is why the wiki documents the `desc:` prefix. (Hyprland #5464 is the frequently-cited report of workspaces landing on the wrong screen, but note it was closed as not-planned during the issues→discussions migration and the reporter's specific case turned out to involve a config syntax error, so treat it as a symptom report rather than a root-cause analysis.)

> **Audit corrected this record.** The behaviour described is real and the fix is mechanically sound. `hl.workspace_rule` accepts `monitor`, `default` and `persistent` per the wiki. The Monitor param for dispatchers explicitly accepts `desc:` and a description. `hl.dsp.workspace.move({ workspace?, monitor })` and `hl.dsp.workspace.swap_monitors({ monitor1, monitor2 })` are both documented. The `socat -U - UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock | while read -r line` pattern and the `monitoradded` event are copied correctly from the IPC page's own bash example. `hyprctl dispatch 'hl.dsp....'` is a real invocation form (Omarchy's own `omarchy-hyprland-monitor-clamshell` uses `hyprctl dispatch "hl.dsp.dpms({ action = \"$action\", monitor = \"$INTERNAL\" })"`). `o.launch_on_start` is real (`default/hypr/helpers.lua:118`), and socat is in `extra` so `pacman -S --needed socat` is correct and the Omarchy ALPM guard only blocks `-S` combined with `-u`. Two citation errors in the cause, though. (1) #7049 is **closed as not_planned**, not "still open". (2) The #5464 characterisation is wrong: the reporter did *not* find connector names shifting between boots. A commenter merely remarked in passing that "ports changing is normal". The reporter's problem persisted after switching to `desc:` and the thread ended on a config syntax error (`default=true` instead of `default:true`), with vaxerski closing it as part of the issues→discussions migration. A reader who trusts "the rules were matching nothing" as the documented root cause is being misled about what that ticket shows.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `hl.dsp.workspace.move` will happily move a workspace to a monitor that is disabled or mirrored, which hides its windows. Guard the script against firing while only one monitor exists (the `monitoradded` trigger already does this in practice, but a manual run undocked will pile everything onto the laptop panel).

**Fix.**

Steps 1-3 are correct as written. Keep the `desc:` monitor rules, the `hypr-restore-workspaces` socat listener, and the one-shot `hl.dsp.workspace.move` repair. Three refinements:

**Trim the duplicate rules in Step 1.** The loop already emits a rule for workspaces 1 and 6, and the two `default = true` lines below re-declare them. Merge instead, so there is exactly one rule per workspace and exactly one default per monitor:

```lua
for i = 1, 5 do
  hl.workspace_rule({ workspace = tostring(i), monitor = EXT, persistent = true, default = (i == 1) })
end
for i = 6, 10 do
  hl.workspace_rule({ workspace = tostring(i), monitor = LAP, persistent = true, default = (i == 6) })
end
```

**Verify the description string round-trips before relying on it.** A `desc:` value with a typo fails silently exactly like a stale connector name:

```bash
hyprctl monitors -j | jq -r '.[] | "\(.name)\t\(.description)"'
hyprctl dispatch 'hl.dsp.focus({ monitor = "desc:Dell Inc. DELL U2723QE 8CJ3XX3" })'
```

If focus does not move, the string is wrong. Remember to drop the trailing `(DP-1)`.

**Also handle `monitorremoved`.** The listener only re-homes on `monitoradded`, so a monitor that sleeps and wakes without emitting an add event leaves workspaces stranded. Widen the case:

```bash
handle() {
  case $1 in
    monitoradded*|monitorremoved*) sleep 1; restore ;;
  esac
}
```

**Verify.** Undock, log in, dock again. `hyprctl workspaces -j | jq -r '.[] | "\(.id) -> \(.monitor)"'` should show workspaces 1-5 on the external and 6-10 on the laptop within a second or two of the monitor coming up.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Workspace-Rules.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Dispatchers.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/IPC/_index.md> · <https://github.com/hyprwm/Hyprland/issues/5464> · <https://github.com/hyprwm/Hyprland/issues/7049> · <https://wiki.hypr.land/Configuring/Basics/Workspace-Rules/>

---

## Fix X11 apps being blurry or unreadably tiny on a HiDPI screen

`xwayland-apps-blurry-or-tiny-on-hidpi` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** On a HiDPI/scaled screen, X11 apps (Steam, JetBrains IDEs, older Electron builds, Zoom, wine games) are either a pixelated blurry mess or razor-sharp but so small you cannot read them, while native Wayland apps look perfect.

**Cause.** Xorg cannot scale, so a compositor has two bad options: upscale the XWayland surface (blurry) or leave it at 1:1 (crisp but tiny). Omarchy ships `xwayland.force_zero_scaling = true` in `/usr/share/omarchy/default/hypr/envs.lua`, which picks 'crisp but tiny'. The toolkits then have to be told to draw bigger themselves, and GTK's `GDK_SCALE` only honours whole numbers.

**Fix.**

Keep zero scaling and scale the toolkits. In `~/.config/hypr/monitors.lua` (Omarchy 4):

```lua
local omarchy_monitor_scale = 2
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- GTK/X11 apps: integers only, use the nearest whole number to the monitor scale
local omarchy_gdk_scale = 2
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
hl.env("XCURSOR_SIZE", "32")
```

On plain Hyprland 0.55+ without Omarchy:

```lua
hl.config({ xwayland = { force_zero_scaling = true } })
hl.env("GDK_SCALE", "2")
hl.env("XCURSOR_SIZE", "32")
```

On Hyprland <= 0.54 (hyprlang):

```
xwayland { force_zero_scaling = true }
env = GDK_SCALE,2
env = XCURSOR_SIZE,32
```

Qt/X11 apps additionally want, in `~/.config/uwsm/env.d/20-user` (Omarchy) or `~/.config/uwsm/env` (Arch + uwsm), one export per line:

```sh
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_ENABLE_HIGHDPI_SCALING=1
```

Restart each app (and log out/in for the env file) for the change to reach it. Do not use the old XWayland HiDPI patches. They are unsupported.

**Verify.** Restart the X11 app: `xeyes`/`xprop` era apps and Steam render at readable size with sharp text. `echo $GDK_SCALE` inside a terminal launched from a keybind returns your value.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Advanced%20and%20Cool/XWayland.md> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://wiki.archlinux.org/title/HiDPI> · <https://wiki.archlinux.org/title/Hyprland>

---

## Stop losing windows and workspaces when you disable a monitor

`disable-monitor-loses-windows-and-workspaces` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** You disable a monitor (display panel toggle, or a `disabled = true` rule) and all the windows that were on it vanish, or reappear stacked on top of everything on the remaining screen. Turning the monitor back on does not restore the layout. Users also report using `disabled` to 'turn the screen off' and being surprised the workspaces moved.

**Cause.** `disabled = true` literally removes the output from the layout: Hyprland migrates every window and workspace off it onto whatever is left. It is not a screen-blank. `dpms` is the screen-blank. Omarchy's display-panel toggle writes a runtime-only rule with no persisted flag, so nothing re-enables the output when the external is later unplugged.

> **Audit corrected this record.** The distinction being drawn is correct and important, and it is upstream's own: the Monitors page warns 'Disabling a monitor will literally remove it from the layout, moving all windows and workspaces to any remaining ones. If you want to disable your monitor in a screensaver style (just turn off the monitor) use the dpms dispatcher.' hyprwm/Hyprland#8024 exists ('All windows/workspaces lost when monitor disconnects'), and `omarchy-hyprland-monitor-internal toggle|on` are real subcommands bound to Super+Ctrl+Delete. The dpms calls are right. But the last command is a legacy hyprlang dispatcher name pasted into Lua: there is no `hl.dsp.moveworkspacetomonitor`. The Dispatchers page puts it in the workspace namespace as `hl.dsp.workspace.move({ workspace?, monitor })`, so the recovery step, the one a user reaches for precisely when their windows are already stranded on an invisible output, fails as written.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Use the right tool for the intent.

Turn the panel *off* without destroying the layout:

```bash
hyprctl dispatch 'hl.dsp.dpms({ action = "disable" })'
hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'
```

Actually remove an output from the layout (windows will move):

```lua
hl.monitor({ output = "HDMI-A-1", disabled = true })
```

On Omarchy, toggle the laptop panel through the helper that keeps a recovery flag, rather than the raw rule:

```bash
omarchy-hyprland-monitor-internal toggle   # Super+Ctrl+Delete
omarchy-hyprland-monitor-internal on       # force it back
```

If windows are already on an invisible output, move the workspace back. The dispatcher lives in the workspace namespace. `hl.dsp.moveworkspacetomonitor` is the old hyprlang name and does not exist in Lua:

```bash
hyprctl monitors -j | jq -r '.[].name'
hyprctl dispatch 'hl.dsp.workspace.move({ workspace = "3", monitor = "eDP-1" })'
```

The `monitor` argument also accepts a direction, `current`, a relative `+1`/`-2`, or a `desc:` description.

**Verify.** `hyprctl monitors -j | jq -c '.[] | {name,disabled}'` matches what you intended, and `hyprctl workspaces -j | jq -c '.[] | {id, monitor}'` shows every workspace on a monitor you can actually see.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md> · <https://github.com/basecamp/omarchy/pull/7036> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-internal> · <https://github.com/hyprwm/Hyprland/issues/8024>

---

## Set environment variables where a uwsm session will actually see them

`env-vars-in-hyprland-config-ignored-uwsm` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`, `wayland`

**Symptom.** You add `env = GDK_SCALE,2` or an `export` to your Hyprland config, reload, and nothing changes. Apps launched from the app launcher or from systemd user services never see the variable, though a terminal you open from a keybind sometimes does.

**Cause.** Omarchy 4 keeps three separate environment stores, and a variable is only seen by the programs whose store it reached.

1. The Hyprland process environment. `hl.env("NAME", "VALUE")` in a loaded Lua file sets it here, and every client Hyprland itself spawns inherits it.
2. The systemd user manager environment, which starts user services and anything launched through `uwsm app`. Read it with `systemctl --user show-environment`.
3. The D-Bus activation environment, which starts D-Bus activated services such as the `xdg-desktop-portal` processes. It is a different store from the systemd one, and that is why a portal or a user service can see a different environment from a terminal.

Generic uwsm advice, including the Arch wiki's Hyprland page, says not to put environment variables in `hyprland.lua` at all. That advice is written for a bare Hyprland plus uwsm install, where Hyprland pushes only seven fixed names into the other two stores (`DISPLAY WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP QT_QPA_PLATFORMTHEME PATH XDG_DATA_DIRS`, in `src/Compositor.cpp`), so anything else set with `hl.env` would stop at store 1.

Omarchy 4 closes that gap and the advice therefore does not transfer unchanged. `/usr/share/omarchy/default/hypr/autostart.lua` runs `systemctl --user import-environment $(env | cut -d'=' -f 1)` and `dbus-update-activation-environment --systemd --all` on the `hyprland.start` event, so on a stock install a variable set with `hl.env` reaches all three stores. Omarchy relies on this for its own defaults in `/usr/share/omarchy/default/hypr/envs.lua`.

Three things still produce the symptom:

- The import fires on `hyprland.start` only, never on `config.reloaded`. A variable added after login reaches Hyprland's own newly spawned children after a reload, but the systemd and D-Bus stores keep the old value until the next login.
- `~/.config/hypr/envs.lua` is never loaded. `~/.config/hypr/hyprland.lua` requires exactly five user modules: `hypr.monitors`, `hypr.input`, `hypr.bindings`, `hypr.looknfeel` and `hypr.autostart`. There is no `hypr.envs`, so `hl.env()` lines placed in `envs.lua` are a silent no-op.
- Running `systemctl --user import-environment NAME` by hand from an already open terminal imports that terminal's value, which is the value from before the edit.

> **Audit corrected this record.** Re-audited against this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1, uwsm 0.26.7-1) and against upstream source. The record's `fix` files are real and its `danger` is a faithful reading of the Arch wiki, which at `Hyprland` says verbatim not to put environment variables in `hyprland.lua` under uwsm and names `~/.config/uwsm/env` and `~/.config/uwsm/env-hyprland`. The `cause` is wrong for Omarchy 4. It claims variables set in the compositor config never reach the systemd user session. On this machine `systemctl --user show-environment` carries `GDK_SCALE`, `XCOMPOSEFILE`, `OMARCHY_PATH`, `QT_QPA_PLATFORMTHEME` and the whole `GUM_*` block, and the environ of all three running `xdg-desktop-portal` processes (pids 2556, 2701, 2756) carries the same names, yet none of them is in Hyprland's own import list. I read that list in `src/Compositor.cpp` at v0.56.2: it is exactly seven names (`DISPLAY WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP QT_QPA_PLATFORMTHEME PATH XDG_DATA_DIRS`). The variables get there because `/usr/share/omarchy/default/hypr/autostart.lua` runs `systemctl --user import-environment $(env | cut -d'=' -f 1)` and `dbus-update-activation-environment --systemd --all` on `hyprland.start`, so the generic uwsm advice does not transfer to Omarchy unchanged and the record was presenting a symptom that a stock Omarchy install mostly does not have.

I replaced the cause and fix with the three-store model and an ordered decision procedure covering all four places a reader might put a variable, because this record is the one other records should point at. Three mechanisms were added, each confirmed at source rather than assumed. `~/.config/hypr/envs.lua` is never loaded: both `/usr/share/omarchy/config/hypr/hyprland.lua` and the live `~/.config/hypr/hyprland.lua` require exactly five user modules and none is `hypr.envs`, so `hl.env()` lines there are a silent no-op. `hl.env` takes a third boolean on 0.56.2 which makes Hyprland run `systemctl --user import-environment '<name>'` and `dbus-update-activation-environment --systemd '<name>'` itself, read in `src/config/lua/bindings/LuaBindingsConfigRules.cpp` around line 525. And `hyprland.start` and `config.reloaded` are distinct events in `src/config/lua/LuaEventHandler.cpp` (lines 151 and 165), so a reload re-applies `hl.env` inside Hyprland but does not refresh the systemd or D-Bus stores, which is the residual failure the record should have described.

Three smaller corrections. The record framed `~/.config/uwsm/env` as the Arch path and `~/.config/uwsm/env.d/20-user` as the Omarchy one. That split is false: `/usr/lib/uwsm/prepare-env.sh` sources `uwsm/env`, `uwsm/env.d/*`, `uwsm/env-${desktop}` and `uwsm/env-${desktop}.d/*` from every rung of `$XDG_CONFIG_HOME:$XDG_CONFIG_DIRS:$XDG_DATA_DIRS`, so all four shapes work identically on both, and uwsm's own README says the same at the "where to put a user-level var" summary. The record called `GDK_SCALE` in `monitors.lua` an exception, when it is the general Omarchy pattern, and upstream ships `local omarchy_gdk_scale = 2` there, which I confirmed on `quattro`. The record never mentioned `~/.config/environment.d/`, which is the correct answer for a systemd-user-only variable and which Omarchy itself uses at `/usr/share/omarchy/default/environment.d/10-omarchy-fcitx.conf`. I added the D-Bus activation environment as a named separate store and put a read of it into `verify`, since the record previously checked only the systemd store. I also rewrote `danger` to drop an em dash. Its content is unchanged and still matches the wiki.

Severity and frequency left at `medium` / `common`. The consequence is a variable that silently does nothing, not a broken machine, and the question of where to put one is asked constantly even though the stock install absorbs most cases.

Not exercised: I changed nothing and logged out of nothing, so the claim that a fresh uwsm env file is picked up at the next login is from `prepare-env.sh` and the uwsm README rather than from a session restart on this box. I did not run `systemctl --user import-environment`, `dbus-update-activation-environment`, `hyprctl reload` or any `hyprctl keyword`. The `env-hyprland` filename is derived from `prepare-env.sh` lowercasing `XDG_CURRENT_DESKTOP`, which is `Hyprland` here, rather than from a file that exists on this machine. `~/.config/uwsm/` does not exist on this install, so the user-side uwsm paths are documented rather than observed in use.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not bind `hl.dsp.exit()` and do not kill the Hyprland process directly under uwsm. Either one bypasses the normal shutdown of the session units. Use `uwsm stop` or `loginctl terminate-user ""` instead.

```lua
hl.bind("SUPER + M", hl.dsp.exec_cmd("uwsm stop"))
```

**Fix.**

Pick the location by who has to see the variable. The first match wins.

**1. Everything in the graphical session, including systemd user services and D-Bus activated services.** Use a uwsm env file. This is the most robust choice on both Omarchy and plain Arch, and it is what Omarchy's own `/usr/share/uwsm/env.d/10-omarchy` points users at.

```sh
# ~/.config/uwsm/env.d/20-user     (create ~/.config/uwsm/env.d first)
# or ~/.config/uwsm/env            for a single file
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_ENABLE_HIGHDPI_SCALING=1
export GDK_DPI_SCALE=1
```

uwsm sources `uwsm/env`, `uwsm/env.d/*`, `uwsm/env-${desktop}` and `uwsm/env-${desktop}.d/*` from every directory in `$XDG_CONFIG_HOME:$XDG_CONFIG_DIRS:$XDG_DATA_DIRS`, so both file shapes work on Arch and on Omarchy. They are POSIX shell, one `export KEY=VALUE` per line. The Arch wiki asks for no comments in them.

**2. Hyprland and Aquamarine only** (`HYPR*`, `AQ_*`). Keep these out of the common file so another compositor does not inherit them.

```sh
# ~/.config/uwsm/env-hyprland
export AQ_DRM_DEVICES=/dev/dri/card1:/dev/dri/card0
```

**3. The systemd user manager, including sessions that are not graphical.**

```sh
# ~/.config/environment.d/50-user.conf     KEY=VALUE, no `export`, no shell
GDK_DPI_SCALE=1
```

This is read by the user manager at start, so it reaches user services and anything it activates. It does not reach a login shell or a plain ssh command. Omarchy uses this path itself for input method variables in `/usr/share/omarchy/default/environment.d/10-omarchy-fcitx.conf`.

**4. Terminals and shell scripts only.** `~/.bashrc`, or `~/.profile` for login shells. Nothing graphical that was already running will see it.

**On Omarchy specifically**, `hl.env()` in one of the five loaded user modules also works, because `default/hypr/autostart.lua` imports the whole environment into systemd and D-Bus at session start. Omarchy's own display tooling uses this for `GDK_SCALE` in `~/.config/hypr/monitors.lua`:

```lua
local omarchy_gdk_scale = 2
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```

If you use `hl.env` for a variable of your own and want it pushed to the other two stores without waiting for the next login, pass the third argument, which Hyprland 0.56 added. It makes Hyprland run `systemctl --user import-environment` and `dbus-update-activation-environment --systemd` for that one name:

```lua
hl.env("MY_VAR", "1", true)
```

**Do not use `~/.config/hypr/envs.lua`.** Nothing loads it. Put `hl.env()` lines in one of the five modules `hyprland.lua` actually requires, or better, in a uwsm env file.

Whichever you pick, **log out and back in** with `uwsm stop`. A `hyprctl reload` re-runs `hl.env` inside Hyprland but does not refresh the systemd or D-Bus stores, because Omarchy's import is bound to `hyprland.start` and not to `config.reloaded`.

**Verify.** Check all three stores, because a variable can be in one and not the others.

```sh
# 1. systemd user manager
systemctl --user show-environment | grep QT_ENABLE_HIGHDPI_SCALING

# 2. D-Bus activation environment, read through a service it started
tr '\0' '\n' < /proc/$(pgrep -f /usr/lib/xdg-desktop-portal | head -1)/environ \
  | grep QT_ENABLE_HIGHDPI_SCALING

# 3. Hyprland's own process environment
tr '\0' '\n' < /proc/$(pgrep -x Hyprland | head -1)/environ \
  | grep QT_ENABLE_HIGHDPI_SCALING
```

A value present in 3 but missing from 1 and 2 means you set it with `hl.env` and have only reloaded, not logged out. A value missing from all three after a re-login means the file you edited is not being read, most often `~/.config/hypr/envs.lua`, which nothing loads.

Sources: <https://wiki.archlinux.org/title/Hyprland> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/autostart.lua> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/hyprland.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/monitors.lua> · <https://github.com/omacom/omarchy/blob/quattro/default/uwsm/env.d/10-omarchy> · <https://github.com/omacom/omarchy/blob/quattro/default/environment.d/10-omarchy-fcitx.conf> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/Compositor.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsConfigRules.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/LuaEventHandler.cpp> · <https://wiki.hypr.land/Configuring/Core/Environment-variables/> · <https://github.com/Vladimir-csp/uwsm>

---

## Stop Ghostty, Nautilus and other GTK4 apps crashing when a monitor is plugged in

`gtk4-apps-crash-on-monitor-hotplug` · severity: **medium** · frequency: **common** · applies to: `arch`, `desktop`, `gtk4`, `hyprland`, `laptop`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** GTK4 apps such as Ghostty, Nautilus, LocalSend and the Voxtype OSD vanish when a monitor is plugged in or out, when a dock connects, or while the lock screen is flapping the display. Sometimes Nautilus dies seconds after it opens. `coredumpctl list` fills up with them, and the kernel log shows:

```
segfault at 5d96d4756008 ... error 4 in libgtk-4.so.1.2200.4
```

**Cause.** gtk4 4.22.4 has a use-after-free in its Wayland dmabuf feedback handling. `linux_dmabuf_format_table()` calls `munmap()` on the wrong pointer. Usually that does nothing, but when `malloc()` has returned a page-aligned chunk it unmaps live heap, and the next `zwp_linux_dmabuf_feedback_v1.done` event segfaults the client. Hyprland resends the format table on every monitor hotplug, so any GTK4 client can die whenever an output is added or removed. GTK fixed it in 4.22.5, which Arch extra has shipped since 2026-09-10. Omarchy installs from a dated stable mirror, and on 2026-10-04 that mirror's `extra.db` (last modified 2026-09-08) still carried `gtk4 1:4.22.4-1`, so `omarchy update` does not deliver the fix.

> **Audit corrected this record.** Confirmed: this workstation has gtk4 1:4.22.4-1. Arch extra has 1:4.22.5-1, last updated 2026-09-10 (archlinux.org JSON). The Omarchy stable mirror's extra.db, downloaded today, is Last-Modified 2026-09-08 and contains gtk4-1:4.22.4-1. The archive URL returns HTTP 200. /usr/bin/omarchy-update-pacman-guard aborts only when the arguments carry both S and u, so pacman -U passes. Issue #12530 is open and matches the cause and the segfault line. The 4.22.5 package has the same unversioned dependency list as the installed 4.22.4. Only the danger was missing. Installing one package from the Arch archive ahead of the Omarchy mirror is a targeted partial upgrade, and the corpus rule is to fill danger for anything that can cause one. The install was not exercised. Second audit confirmed the corrected text: Rechecked the current text, including the danger added by the first audit. Issue #12530 (open) states the munmap use-after-free, the dmabuf feedback done crash, the segfault line, the Nautilus-at-startup and Voxtype OSD reports, and the 4.22.5 fix, so cause and symptom are supported. archlinux.org JSON shows extra gtk4 1:4.22.5-1 last updated 2026-09-10 with an unversioned dependency list. The live stable-mirror.omarchy.org extra.db is still Last-Modified 2026-09-08, the local sync db carries gtk4-1:4.22.4-1, this workstation has gtk4 1:4.22.4-1 and upstream latest is still v4.0.4, so the advice that omarchy update does not deliver the fix holds today. The archive URL returns HTTP 200. No installed package declares a versioned dependency on gtk4 (checked every Required By entry), so pacman -U resolves. The pacman -U install itself was not exercised.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** `pacman -U` from the Arch archive installs one package ahead of the rest of the system, which is a small partial upgrade. gtk4 4.22.5-1 declares the same dependencies as 4.22.4-1, so it installs cleanly today, but do not use this pattern for other packages without comparing their dependencies. Until the Omarchy mirror catches up, `omarchy update` will report gtk4 as newer than the repository and leave it alone, which is expected.

**Fix.**

**Check what you have:**

```bash
pacman -Q gtk4
coredumpctl list | tail
```

**Omarchy 4:** either wait for the mirror to advance and run `omarchy update`, or install the fixed build from the Arch package archive now. `pacman -U` is not blocked by Omarchy's update guard, which refuses only a transaction that combines `-S` and `-u`:

```bash
sudo pacman -U https://archive.archlinux.org/packages/g/gtk4/gtk4-1%3A4.22.5-1-x86_64.pkg.tar.zst
```

Then close and reopen your GTK4 apps.

**Plain Arch:** a normal full upgrade gets 4.22.5 or later:

```bash
sudo pacman -Syu
```

**Verify.** `pacman -Q gtk4` prints `gtk4 1:4.22.5-1` or later. Unplug and replug a monitor a few times with Ghostty and Nautilus open. Both survive, and `coredumpctl list` shows no new entries.

Sources: <https://github.com/omacom/omarchy/issues/12530> · <https://archlinux.org/packages/extra/x86_64/gtk4/>

---

## Stop an HDMI monitor waking and blanking over and over while the session is locked

`hdmi-monitor-relights-locked-screen-loop` · severity: **medium** · frequency: **common** · applies to: `amd`, `desktop`, `hdmi`, `hyprland`, `laptop`, `omarchy`, `omarchy-4`, `quickshell`

**Symptom.** While the session is locked, the display keeps turning on and off. Each time it comes back it shows the password field for a few seconds, then goes dark again, and this repeats for as long as the machine stays locked, all night if you let it. One reporter counted 4,182 display sleep transitions in a single day. The Hyprland log (`$XDG_RUNTIME_DIR/hypr/*/hyprland.log`) has pairs like this, over and over:

```
drm: Connector HDMI-A-1 disconnected
ERR from aquamarine ]: drm: Cannot commit a disconnected output
drm: HDMI-A-1 is not connected, clearing stale crtc 67
drm: Connector HDMI-A-1 connected
drm: Modesetting HDMI-A-1 with 3840x2160@60.00Hz
```

Mostly reported on AMD (APUs and discrete Radeon) with HDMI monitors. GTK4 apps may crash during the loop (see `gtk4-apps-crash-on-monitor-hotplug`).

**Cause.** Five seconds after the session locks, Omarchy's lock blanks the screens with `omarchy-brightness-display off` (DPMS off). Many HDMI monitors drop their hotplug-detect (HPD) line when they go into standby, then raise it again a few seconds later. The kernel reports that as a disconnect and a reconnect. Hyprland removes the output and adds it back with DPMS on, the lock surface is rebuilt for the new output, and the pointer entering that surface counts as activity. The lock wakes, re-arms its 5-second blank, and the loop starts again. On some AMD machines the HDMI audio codec's `SW_VIDEOOUT_INSERT` switch events also count as activity. The Omarchy-side fixes (PRs #8896, #10343 and #13129) are open and not in 4.0.4. amdgpu has an HDMI HPD filter that is off by default. When it is on, a disconnect followed by the same EDID returning within the window never reaches the compositor. The parameter `hdmi_hpd_debounce_delay_ms` was confirmed with `modinfo` on kernel 7.2.5-3-omarchy.

> **Audit corrected this record.** The cause and the AMD branch hold. shell/plugins/lock/Service.qml on 4.0.4-1 has idleBlankTimer at 5000 ms running omarchy-brightness-keyboard off and omarchy-brightness-display off. Issues #13812 and #8863 (both open) give the log pairs, the pointer-enter wake path, the HDMI audio SW_VIDEOOUT_INSERT path and the 4,182 transitions figure. PRs #8896, #10343 and #13129 are all open. modinfo on 7.2.5-3-omarchy lists hdmi_hpd_debounce_delay_ms. amdgpu_dm_connector.c reads it at connector init and clamps it to AMDGPU_DM_MAX_HDMI_HPD_DEBOUNCE_MS, 5000, so the reboot and the stated maximum are right. omarchy_hooks.conf contains modconf and kms. The defect is the mitigation for other GPUs. omarchy toggle idle stay-awake only writes ~/.local/state/omarchy/indicators/stay-awake, which the idle service reads to cancel the idle cycle. beginLock() in the lock service arms the 5 s blank on every lock, with no stay-awake check and no lock-only path in 4.0.4-1. So a lock started by hand, or before suspend, still blanks and loops. The record presents the toggle as stopping the lock from blanking. Rewritten to say what it covers. Not exercised: no lock was triggered here.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** The initramfs rebuild writes the UKI to the ESP. Run `df -h /boot` first, because a full ESP produces a truncated image that does not boot. `omarchy toggle idle stay-awake` turns off automatic locking, so an unattended machine stays unlocked until you lock it by hand.

**Fix.**

**AMD graphics with an HDMI monitor: turn on amdgpu's HPD debounce.**

```bash
modinfo -p amdgpu | grep hdmi_hpd     # must list hdmi_hpd_debounce_delay_ms
echo 'options amdgpu hdmi_hpd_debounce_delay_ms=1500' | sudo tee /etc/modprobe.d/amdgpu-hdmi-hpd.conf
```

amdgpu is loaded from the initramfs (the `kms` and `modconf` hooks), and the parameter is read only when the module sets up its connectors, so rebuild and reboot:

- **Omarchy 4:** `sudo limine-mkinitcpio && sudo reboot`
- **Plain Arch:** `sudo mkinitcpio -P && sudo reboot`

1500 ms is the value AMD and the Omarchy PR chose (the kernel caps it at 5000). The filter covers HDMI only, not DisplayPort.

**Any other GPU, or a DisplayPort monitor:** there is no packaged fix yet. The mitigation reporters use is to stop the session locking on idle:

```bash
omarchy toggle idle stay-awake
```

That turns off automatic locking and screen-off. It does not change what happens after a lock you start yourself: Omarchy's lock blanks the screens 5 seconds after any lock, so a manual lock on an affected monitor still loops. Until upstream fixes it, leave the machine unlocked only where that is safe, or power the monitor off by its own button while locked. Undo the toggle with `omarchy toggle idle allow-idle`. One reporter instead pins the connector's EDID and forces the connector on, so the kernel never sees the monitor leave. See the record `edid-override-for-bad-or-missing-monitor-edid` for that mechanism, which breaks hot-swapping on that port.

**Verify.** After the reboot, `cat /sys/module/amdgpu/parameters/hdmi_hpd_debounce_delay_ms` prints `1500`. Lock the session and leave it for two minutes. The screen stays dark, and `grep -c 'disconnected' "$XDG_RUNTIME_DIR"/hypr/*/hyprland.log` does not grow while you wait.

Sources: <https://github.com/omacom/omarchy/issues/13812> · <https://github.com/omacom/omarchy/issues/8863> · <https://github.com/omacom/omarchy/pull/13129> · <https://github.com/omacom/omarchy/pull/8896> · <https://github.com/omacom/omarchy/pull/10343> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_connector.c> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c>

---

## HDR / 10-bit enabled: washed-out SDR, banded borders, blank screen shares

`hdr-10bit-washed-out-and-broken-capture` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`, `xdg-desktop-portal`

**Symptom.** I turned on HDR with `bitdepth = 10` and `cm = "hdr"` and now everything SDR looks grey and washed out: the desktop, the browser, YouTube in a window. Window borders and gradients look banded. Worse, screen sharing in Discord/Meet/OBS now shows a completely black or blank window, and `hyprshot`/screenshots come out empty or transparent. Sometimes after a fullscreen HDR game exits, the whole desktop stays washed out until I run `hyprctl reload`.

**Cause.** Three separate documented effects get blamed on one setting. (1) `cm = "hdr"` puts the whole output on a wide-gamut BT.2020 + PQ transfer function, and SDR content mapped into it looks dim and desaturated unless `sdrbrightness`/`sdrsaturation` are raised. The Hyprland wiki marks `hdr`/`hdredid` as experimental. (2) The wiki warns explicitly that colors registered inside Hyprland (window border colors, gradients) do *not* support 10 bit, so borders band. (3) 10-bit/HDR buffers are not consumable by many capture clients: xdg-desktop-portal-hyprland issue #313 is exactly "screenshare is broken when HDR is enabled", fixed by dropping back to 8 bit. HDR-mode screenshots also come out empty unless `render:keep_unmodified_copy` is forced on. The lingering washed-out desktop after a fullscreen HDR app exits is hyprwm/Hyprland #9286 / discussion #10950.

> **Audit corrected this record.** The diagnosis and every wiki fact are right: `render:cm_auto_hdr` default `1`, `keep_unmodified_copy` default 2 with the literal note "Set to 1 if screenshots are transparent.", `quirks:prefer_hdr` 0/1/2 with 2 = gamescope only, the `cm` preset block reproduced verbatim, sdrbrightness/sdrsaturation defaults 1.0 and the documented 1.0..2.0 range, the "Colors registered in Hyprland (e.g. the border color) do not support 10 bit" warning, `cm_enabled` "requires a restart of Hyprland to fully take effect", and the mpv `--target-colorspace-hint-mode=source` note. xdph #313, Hyprland #9286 and discussion #10950 all exist and say what is claimed. But the config API is fabricated: `hl.set("render:keep_unmodified_copy", 1)` does not exist. The Variables page documents exactly one syntax, `hl.config({ category = { value = ... } })`, and there is no `hl.set` anywhere in the wiki or in the entire Omarchy quattro tree, which uses `hl.config({ cursor = { no_hardware_cursors = ... } })` throughout. Copy-pasting those two lines throws a Lua error and the whole config file fails to load, which is worse than the original symptom. The `hl.monitor({...})` blocks are fine as written.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `cm` and `bitdepth` changes force a modeset. The wiki notes that `render:send_content_type` (default true) reporting content type to the monitor "may result in a black screen during the switch". On some panels the screen can stay black for several seconds or until you re-plug. Do not set `cm = "hdr"` on your only monitor without a TTY (`Ctrl+Alt+F2`) available so you can edit `~/.config/hypr/monitors.lua` back and `hyprctl reload`. `hdr`/`hdredid` are marked experimental upstream. An ICC profile plus HDR is explicitly unsupported ("ICCs are fundamentally incompatible with HDR gaming").

**Fix.**

Only the two `hl.set(...)` lines are wrong. Everything else in the record stands as written. Replace them with the documented `hl.config` form (Variables page: `hl.config({ category = { value = ... } })`).

Fix blank/empty screen capture and screenshots. In `~/.config/hypr/looknfeel.lua`:

```lua
hl.config({ render = { keep_unmodified_copy = 1 } })  -- default 2 (auto); 1 = always keep an SDR copy
```

Fix apps that need HDR on before they launch (gamescope):

```lua
hl.config({ quirks = { prefer_hdr = 2 } })   -- 0 off, 1 always, 2 gamescope only
```

Both can be merged into one call:

```lua
hl.config({
  render = { keep_unmodified_copy = 1 },
  quirks = { prefer_hdr = 2 },
})
```

To try either without editing a file first, `hyprctl eval` takes the same Lua:

```bash
hyprctl eval 'hl.config({ render = { keep_unmodified_copy = 1 } })'
```

Then `hyprctl reload` as the record already says. Also worth adding: #9286 is closed as *completed* and #10950 is its open follow-up discussion, so the stuck-washed-out-after-fullscreen behaviour is version-dependent. Check `hyprctl version` before assuming you are hitting it.

**Verify.** `hyprctl monitors -j | jq -r '.[] | "\(.name) \(.currentFormat) \(.activelyTearing)"'` shows a 10-bit format (e.g. `XRGB2101010`) once `bitdepth = 10` is active. Take a screenshot and confirm it is not transparent/empty, then start a screen share and confirm the preview is not black.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/xdg-desktop-portal-hyprland/issues/313> · <https://github.com/hyprwm/Hyprland/discussions/10950> · <https://wiki.hypr.land/Configuring/Basics/Monitors/>

---

## Stop the internal laptop panel snapping back to 2x scale a second after every change

`internal-panel-forced-to-2x-scale-clamshell-poll` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `laptop`, `omarchy`, `omarchy-shell`, `quickshell`, `wayland`

**Symptom.** After the Quattro upgrade the internal laptop display is held at scale 2 while external monitors scale normally at any value. Every manual change to the internal panel's scale is reverted about a second after it is applied, whether it is made in `~/.config/hypr/monitors.lua`, with `hyprctl`, or in the Display panel on the bar. Opening the Display panel snaps the viewport straight back to 2.

Reported on Omarchy 4 on a laptop with a 1920x1080 built-in panel and an external 1920x1080 monitor, and by three more people with different `monitors.lua` shapes.

**Cause.** `omarchy-hyprland-monitor-clamshell` is polled every two seconds by `omarchy-hyprland-monitor-watch` for as long as an external monitor is active, and each pass re-asserts what it reads as the internal panel's configured scale. When that read produced no number it substituted a hardcoded `2`. With the shipped `monitors.lua`, where `local omarchy_monitor_scale = "auto"` and no rule names the internal panel, that fallback fired on every poll, which is why the panel returned to 2 about a second after any change.

`omacom/omarchy#7581` merged as commit `b63616422f427bb778f49f573e6cc197e29c7b4f` on 2026-08-22 and first shipped in v4.0.1. It did not remove the hardcoded fallback. It added a guard in `sync_internal_scale`: when the config yields no usable number and the panel has a valid active scale, the poll returns without writing, so an auto-scaled panel keeps whatever Hyprland's `auto` resolved. The `echo 2` is still in the shipped script at line 153 of `read_monitor_scale`. It is now reached only when the script re-enables a panel it disabled itself and `~/.local/state/omarchy/toggles/hypr/internal-monitor-scale` holds nothing usable.

Because that guard tests for the *absence* of a number, it stops protecting the panel the moment `monitors.lua` yields one. Adjusting scale from the Display panel on the bar rewrites `local omarchy_monitor_scale` to a single number, which is `omacom/omarchy#7505`, open. After one such adjustment the poll re-asserts that one global number on the internal panel, and resets its position to `auto`, whenever the panel's live scale differs from it. It does not repeat every two seconds once corrected, because `scales_match` then returns early. It writes again on the next `hyprctl reload`, resume or redock that restores the user's value.

A reader limitation from the same thread is also still live, and it looks identical from the outside. `monitor_rule_regex` matches only a rule written as `hl.monitor({` with a literal quoted `output = "<name>"` on the same line of `~/.config/hypr/monitors.lua`. A rule keyed by `desc:`, spread over several lines, naming a variable in `output`, or living in another file that `hyprland.lua` requires is invisible to the poll, which then acts on the catch-all rule or on the global knob instead of on the rule. That is `omacom/omarchy#7084`, open, with `#7146` proposed against it and not merged as of 2026-09-11.

> **Audit corrected this record.** Checked the three claims separately against the shipped script on this workstation (omarchy 4.0.2-1) and against every cited thread read in full today, 2026-09-11.

Claim 1 is half wrong. PR 7581 is merged into `quattro` with `merge_commit_sha` exactly `b63616422f427bb778f49f573e6cc197e29c7b4f` (`gh api repos/omacom/omarchy/pulls/7581`), confirmed, and the shipped `/usr/share/omarchy/bin/omarchy-hyprland-monitor-clamshell` is byte-identical to both `quattro` and `v4.0.3`. But the hardcoded scale fallback is NOT gone: `echo 2` sits at line 153 in `read_monitor_scale`, and the PR is +24/-2 on that file, a guard rather than a removal. The record's sentence "the shipped script has no hardcoded scale left" is false as written, so the cause is rewritten to describe the guard at line 192 and to say where the `2` is still reachable (re-enabling a panel the script itself disabled, with no usable remembered scale). The record's version floor is also understated: I fetched the script at every 4.x tag, and v4.0.1, v4.0.2 and v4.0.3 are identical and all carry the guard, while v4.0.0 is the only release without it and has the `echo 2` at line 137, the line the upstream comments cite. The triage comment on issue 7084 claiming the fix is "not in v4.0.0 or v4.0.1" is itself wrong about v4.0.1, which was published 2026-08-25, three days after the merge.

A live path the record misses, and the reason for the rewritten fix. The 7581 guard only fires when the config yields NO usable number. I ran the shipped reader functions (lines 22 to 165, no side effects) against fixture configs under a temp HOME: the stock file resolves `configured_monitor_scale` to `auto`, so the guard holds and nothing is written, but the same file with `local omarchy_monitor_scale = 1.6` resolves to 1.6, the guard does not fire, and the poll pushes 1.6 and `position = auto` onto the internal panel. Confirmed on this machine that `shell/plugins/panels/monitor/Panel.qml:308` runs `omarchy-hyprland-monitor-scaling`, whose `set_scale()` rewrites `local omarchy_monitor_scale` to one number. So anyone who has touched the Display panel is back in the symptom, which the record's "no config change is needed" does not cover.

Claim 2 confirmed, and extended. I copied `monitor_rule_regex` and the extraction `sed` verbatim into a scratch script and ran them over four fixtures: the one-line connector-keyed rule returns `scale=1.33`, while the `desc:`-keyed, multiline and variable-in-`output` shapes all return nothing. `omarchy-hyprland-monitor-laptop` only ever prints a connector name matching `^(eDP|LVDS|DSI)-`, so a `desc:` rule can never match. Issue 7084 is open (4 comments) and PR 7146 is open and unmerged. Its thread adds a fourth trigger the record omits and which its own advice does not cover: `MONITOR_LUA` is pinned at line 10, so a correctly formatted rule in a `require()`d file is never read. Added, along with the 1/120 rounding caveat and the cadence correction that the rewrite does not repeat every two seconds once the scales match.

Claim 3 confirmed from the source and on this machine. Issue 7505 is open with 0 comments, and its body matches the claim: the `sed -i` in `set_scale()` replaces `local omarchy_monitor_scale` and `local omarchy_gdk_scale`, destroying `"auto"` on the first adjustment. I read that `sed` in the shipped script and it is as described. PR 8145, "Persist monitor scaling onto named per-output rules", is open against it and is now named. A `danger` was added because 7505's own suggested restore, `omarchy refresh config hypr/monitors.lua`, discards the user's monitor config.

Symptom left unchanged: issue 6909's body matches it (built-in 1920x1080 at 144 Hz forced to 2, external 1920x1080 at 60 Hz scaling normally, reverted one second after any change, Display panel crash). If anything it undercounts the other reporters, since four more describe the same symptom in that thread.

Not exercised: this machine is a desktop workstation (`/sys/class/dmi/id/chassis_type` is 3, and `hyprctl monitors all -j` shows only HDMI-A-1 plus a vncpanel output, no eDP). With no internal panel, `INTERNAL` is empty and every function in the script returns early, so the clamshell poll, the lid-open path and the actual reapplication of a scale could not be run here. Everything above is source reading plus the script's own config-reading functions driven over fixture files, not an observed fix on a laptop.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Restoring the shipped catch-all with `omarchy refresh config hypr/monitors.lua` overwrites `~/.config/hypr/monitors.lua` with the template and loses every per-monitor rule, mode, position and transform in it. Edit the file by hand instead, or copy it somewhere first.

**Fix.**

**Update first. The fix is in v4.0.1 and later, so only v4.0.0 carries the original defect.**

```bash
omarchy update
pacman -Q omarchy
hyprctl reload
```

No config change is needed for the stock `monitors.lua`, and an explicit rule added only to stop the snapping can be dropped again. The script is byte-identical across v4.0.1, v4.0.2 and v4.0.3.

**Then check the global scale knob, because this is the part that is still live.**

```bash
grep -n 'local omarchy_monitor_scale' ~/.config/hypr/monitors.lua
```

The guard only holds while the config gives the poll no number. `"auto"` is such a value. A bare number is not. Changing scale from the Display panel, or running `omarchy-hyprland-monitor-scaling <n>`, rewrites that line to one number and destroys `"auto"` (`omacom/omarchy#7505`, open, with `#8145` proposed against it). From then on the poll pushes that number onto the internal panel and resets its position to `auto`. Put `"auto"` back, or give the internal panel a rule of its own:

```lua
-- ~/.config/hypr/monitors.lua
local omarchy_monitor_scale = "auto"
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })
hl.monitor({ output = "eDP-1", mode = "2560x1600@240", position = "0x0", scale = 1.33 })
```

Then `hyprctl reload`. Edit the file by hand rather than running `omarchy refresh config hypr/monitors.lua`, which restores the template and discards the rest of your monitor config.

**If the scale still moves on its own, the poll is not reading your rule.** It reads one file with a line-based regex, so the rule must be on one line, name the connector in a literal quoted string, and live in `~/.config/hypr/monitors.lua`. These four shapes are all invisible to it:

```lua
-- keyed by description: the script only ever looks for the connector name
hl.monitor({ output = "desc:Samsung Display Corp ATNA60HR07-0", scale = 1.33 })

-- spread over several lines
hl.monitor({
  output = "eDP-1",
  scale = 1.33,
})

-- the output named through a variable
local laptop_output = "eDP-1"
hl.monitor({ output = laptop_output, scale = 1.33 })
```

The fourth is scope rather than syntax: `MONITOR_LUA` is pinned to `~/.config/hypr/monitors.lua` at line 10 of the script, so a correctly written rule in a file that `hyprland.lua` pulls in with `require()`, such as a layout written by HyprMon, is never opened. Duplicate that rule into `monitors.lua`.

Get the connector name, and the scale value to write, from Hyprland itself:

```bash
hyprctl monitors all -j | jq -r '.[] | "\(.name) \(.scale) \(.description)"'
```

Use the scale Hyprland reports, not the one you asked for. It rounds to whole logical pixels in steps of 1/120, so a requested 1.66 on 2256x1504 becomes 1.6, and the poll's 0.001 tolerance would otherwise mismatch and reapply.

One thing from the original report is still untracked: the Display panel crashing when it is opened was never explained and has no issue of its own. The scale snapping back to 2 in that same moment was this defect.

**Verify.** ```bash
pacman -Q omarchy                                  # v4.0.1-1 or later carries the fix

# the guard PR 7581 added. No output means a pre-v4.0.1 script
grep -n 'valid_scale "$configured_scale"' /usr/share/omarchy/bin/omarchy-hyprland-monitor-clamshell

# must not be a bare number unless you want that number on the internal panel too
grep -n 'local omarchy_monitor_scale' ~/.config/hypr/monitors.lua

hyprctl monitors all -j | jq -r '.[] | "\(.name) \(.scale) \(.x)x\(.y)"'
sleep 5
hyprctl monitors all -j | jq -r '.[] | "\(.name) \(.scale) \(.x)x\(.y)"'   # unchanged after more than two polls
```

Sources: <https://github.com/omacom/omarchy/issues/6909> · <https://github.com/omacom/omarchy/pull/7581> · <https://github.com/omacom/omarchy/issues/7084> · <https://github.com/omacom/omarchy/issues/7505> · <https://github.com/omacom/omarchy/pull/7146> · <https://github.com/omacom/omarchy/pull/8145> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-clamshell> · <https://github.com/omacom/omarchy/blob/v4.0.1/bin/omarchy-hyprland-monitor-clamshell> · <https://github.com/omacom/omarchy/blob/v4.0.0/bin/omarchy-hyprland-monitor-clamshell> · <https://github.com/omacom/omarchy/releases/tag/v4.0.1>

---

## Stop a laptop panel flickering or stuttering from Panel Self Refresh

`laptop-panel-flicker-stutter-psr-panel-replay` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `grub`, `intel`, `laptop`, `limine`, `manjaro`, `oled`, `omarchy`, `omarchy-4`, `systemd-boot`

**Symptom.** The laptop's own screen flickers, or short horizontal strips of artefacts flash across part of the screen when scrolling or playing video. External monitors on the same machine are fine. Variants that users report:

- Intel: flicker, sometimes with `[i915] *ERROR* CPU pipe A FIFO underrun` in `journalctl -k`.
- Newer Intel on the `xe` driver (Dell XPS 13 DX13260, Wildcat Lake): scrolling judders far below the panel's 120 Hz and the cursor moves in jerks. `i915_psr_status` shows `PSR mode: Panel Replay Selective Update enabled (Early Transport)`.
- AMD: ThinkPad T14 Gen5 AMD OLED with intermittent horizontal artefacts during video and scrolling.

If the whole image freezes instead, with `flip_done timed out` in the log, see the record `amdgpu-flip-done-timed-out`.

**Cause.** Panel Self Refresh (PSR) and its successor Panel Replay are eDP power-saving features. During static periods the GPU stops sending frames and the panel refreshes from its own memory. Bugs in the driver or in a particular panel's wake and exit path cause flicker, artefacts, or late frame delivery when the panel has to wake for an update. That is why cursor movement and scrolling show it most. The Arch wiki documents PSR flicker on Intel and recommends turning it off. On Intel, i915 and xe share one display code path in which `enable_psr` gates PSR only and `enable_panel_replay` gates Panel Replay separately, so turning off PSR alone leaves Panel Replay running. Omarchy's own installer turns off Panel Replay for the ASUS ExpertBook B9406 for that reason. On amdgpu, `dcdebugmask=0x10` turns off PSR v1 and PSR Selective Update, and Panel Replay has its own bit, `0x400`. All six Intel and AMD parameters used below were confirmed with `modinfo -p` on kernel 7.2.5-3-omarchy.

> **Audit corrected this record.** The Intel i915 row is incomplete. modinfo -p i915 on 7.2.5-3-omarchy lists enable_panel_replay, and in mainline intel_psr.c the enable_psr parameter gates only _psr_compute_config, while panel_replay_global_enabled checks only the debug flag and params.enable_panel_replay. So i915.enable_psr=0 leaves Panel Replay on, the same gap the record already warns about for xe. Meteor Lake class panels on i915 can use Panel Replay. The amdgpu row also needs a note: amd_shared.h defines DC_DISABLE_PSR 0x10 as PSR v1 and PSR-SU only, with Panel Replay on a separate bit, DC_DISABLE_REPLAY 0x400. 0x10 is what the T14 Gen5 thread confirmed and stays the first choice. Everything else held: issue #6853 has the XPS i915_psr_status output, the runtime echo 1 test, the both-knobs reasoning and the enable_psr=2 comment, #11016 confirms debug 1 disables both PSR and Panel Replay, the ASUS B9406 script exists and says xe.enable_psr=0 does not cover Panel Replay, and the BBS thread confirms 0x10 for the T14 Gen5 AMD OLED. Cause and verify are rewritten to match. The debugfs write needs root and was not run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Turning off PSR or Panel Replay raises idle power draw. The XPS report estimated 0.5 to 1.5 W, which is a visible hit to battery life. On Omarchy 4, a drop-in written with `=` instead of `+=`, or with `tee` instead of `tee -a`, silently drops Omarchy's own kernel parameters, including `initramfs_async=0`, which keeps the Plymouth LUKS prompt working. `limine-mkinitcpio` rewrites the UKI on the ESP, so check `df -h /boot` first. To recover from a bad parameter, edit it out in the Limine boot menu editor or boot a Limine snapshot entry.

**Fix.**

**Find your display driver:**

```bash
lspci -k | grep -A3 -E 'VGA|Display'
```

**Intel only: test at runtime first** (the path is from the XPS report and may differ by PCI address):

```bash
sudo cat /sys/kernel/debug/dri/0000:00:02.0/eDP-1/i915_psr_status
echo 1 | sudo tee /sys/kernel/debug/dri/0000:00:02.0/i915_edp_psr_debug
```

Writing 1 turns off both PSR and Panel Replay. If that makes the flicker or stutter stop at once, PSR or Panel Replay is the cause. It resets at reboot.

**Pick the parameters for the driver `lspci -k` showed as in use:**

| Driver in use | Parameters |
| --- | --- |
| `i915` | `i915.enable_psr=0 i915.enable_panel_replay=0` |
| `xe` | `xe.enable_psr=0 xe.enable_panel_replay=0` |
| `amdgpu` | `amdgpu.dcdebugmask=0x10` |

On Intel you need both parameters. `enable_psr=0` does not cover Panel Replay, and turning off only Panel Replay falls back to PSR2 selective fetch, which stuttered the same way in the XPS report. One reporter on the same laptop found that `xe.enable_psr=2 xe.enable_panel_replay=0` also cured it, at a smaller battery cost, so try that first if battery matters.

On `amdgpu`, `0x10` turns off PSR v1 and PSR Selective Update, which is what fixed the ThinkPad T14 Gen5 report. It does not turn off Panel Replay. If the artefacts persist, use `amdgpu.dcdebugmask=0x410` instead, which adds the kernel's `DC_DISABLE_REPLAY` bit (`0x400`).

**Omarchy 4:** write only the row for your driver. The block below is the `xe` row. For `i915` the line is `KERNEL_CMDLINE[default]+=" i915.enable_psr=0 i915.enable_panel_replay=0"`, and for `amdgpu` it is `KERNEL_CMDLINE[default]+=" amdgpu.dcdebugmask=0x10"`. Always use `+=`, because a bare `=` would wipe Omarchy's own defaults.

```bash
sudo tee -a /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" xe.enable_psr=0 xe.enable_panel_replay=0"
EOF
sudo limine-mkinitcpio && sudo limine-update && sudo reboot
```

After the reboot, check that the parameters reached the kernel:

```bash
cat /proc/cmdline
```

**Plain Arch:** add the parameters for your driver to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` and run `sudo grub-mkconfig -o /boot/grub/grub.cfg`, or append them to `options` in `/boot/loader/entries/*.conf` for systemd-boot. Then reboot.

**Verify.** After the reboot, `cat /proc/cmdline` shows the parameters. On Intel, `cat /sys/module/i915/parameters/enable_psr` and `cat /sys/module/i915/parameters/enable_panel_replay` (or the same files under `/sys/module/xe/parameters/`) both print `0`, and `i915_psr_status` no longer reports PSR or Panel Replay as enabled. On AMD, `cat /sys/module/amdgpu/parameters/dcdebugmask` prints `16` for 0x10, or `1040` for 0x410. Scroll a long page and play a video to check that the flicker and judder are gone.

Sources: <https://wiki.archlinux.org/title/Intel_graphics> · <https://wiki.archlinux.org/title/AMDGPU> · <https://bbs.archlinux.org/viewtopic.php?id=300966> · <https://github.com/omacom/omarchy/issues/6853> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/asus/fix-asus-ptl-b9406-display.sh> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_display_types.h> · <https://github.com/omacom/omarchy/issues/11016> · <https://github.com/omacom/omarchy/issues/6768> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_display_params.c> · <https://github.com/omacom/omarchy/issues/5423> · <https://github.com/omacom/omarchy/issues/12875> · <https://github.com/omacom/omarchy/issues/11176> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_psr.c> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/include/amd_shared.h>

---

## Write monitor rules that survive a cable swap or a dock replug

`monitor-rules-break-when-ports-swap` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Your carefully written per-monitor rules stop matching after you move a cable, replug a dock, or reboot. The same physical screen is now `DP-3` instead of `DP-2`, so the scale/position/refresh rule silently does not apply and everything comes up at defaults.

**Cause.** Connector names (`DP-1`, `HDMI-A-1`, `DP-5`) are assigned by the kernel per port and are not stable across cable swaps, dock topologies or GPU driver changes. Rules keyed on the connector name break whenever the numbering shifts.

**Fix.**

Key rules on the monitor's EDID description instead, using the `desc:` prefix. Get the description:

```bash
hyprctl monitors | grep -E '^Monitor|description:'
# Monitor eDP-1 (ID 0):
#         description: Chimei Innolux Corporation 0x150C (eDP-1)
```

Use everything up to but **not including** the `(portname)`:

```lua
hl.monitor({ output = "desc:Chimei Innolux Corporation 0x150C", mode = "preferred", position = "auto", scale = 1.5 })
hl.monitor({ output = "desc:Dell Inc. DELL U2723QE 8CJ2P43", mode = "3840x2160@60", position = "auto-right", scale = 1.5 })
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })   -- keep the fallback last
```

On Hyprland <= 0.54: `monitor=desc:Dell Inc. DELL U2723QE 8CJ2P43,3840x2160@60,auto,1.5`.

**Verify.** Move the cable to a different port and reboot: `hyprctl monitors -j | jq -c '.[] | {name,description,scale,x,y}'` shows the rule still applied on the new connector name.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md>

---

## Stop the display scale snapping straight back after you change it

`monitor-scale-reverts-instantly-per-monitor-rule` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `omarchy`, `wayland`

**Symptom.** You change the display scale (Super+Ctrl+D panel, or `omarchy hyprland monitor scaling 1.25`) and the screen resizes for about a tenth of a second and then snaps straight back to the old scale. It is impossible to make the change stick, and there is no error anywhere.

**Cause.** `omarchy-hyprland-monitor-scaling` applies the scale at runtime via `hyprctl eval`, then persists it by sed-rewriting only the catch-all variables `omarchy_monitor_scale` / `omarchy_gdk_scale` in `monitors.lua`. Hyprland auto-reloads on any config-file write (~30 ms later). If your `monitors.lua` also has an explicit per-output rule such as `hl.monitor({ output = "DP-2", ..., scale = 1 })`, that rule wins over the catch-all on reload, so the reload undoes the tool's own runtime change.

**Fix.**

Edit the scale in the explicit rule instead of using the tool. In `~/.config/hypr/monitors.lua`:

```lua
-- before
hl.monitor({ output = "DP-2", mode = "2560x1440@165", position = "1920x0", scale = 1 })
-- after
hl.monitor({ output = "DP-2", mode = "2560x1440@165", position = "1920x0", scale = 1.25 })
```

Then `hyprctl reload`.

Alternatively, delete the per-output rules and keep only Omarchy's stock catch-all so the helper's persistence path is the one the reload reads:

```lua
local omarchy_monitor_scale = 1.25
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })
local omarchy_gdk_scale = 1
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```

**Verify.** `hyprctl monitors -j | jq '.[] | {name, scale}'` still reports the new scale 5 seconds later and after `hyprctl reload`.

Sources: <https://github.com/basecamp/omarchy/issues/7242> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-scaling> · <https://github.com/basecamp/omarchy/blob/quattro/config/hypr/monitors.lua>

---

## Find out why a USB-C dock or MST hub hides your monitor's high refresh rate

`mst-dock-high-refresh-mode-pruned-dsc` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `dock`, `endeavouros`, `hyprland`, `intel`, `laptop`, `omarchy`, `wayland`

**Symptom.** My 3440x1440 165 Hz (or 2560x1440 240 Hz) monitor runs at full rate plugged straight into the laptop, but through my USB-C dock or MST hub `hyprctl monitors all` tops out lower: 100 Hz for the 3440x1440 165 Hz panel in i915 17207, 120 Hz for a 3440x1440 panel in i915 17228, and 144 Hz for the 2560x1440 240 Hz panel in i915 16640. Windows on the same dock and cable does the full rate. Editing the `mode` line does nothing, because the fast mode is not in `availableModes` at all.

**Cause.** The kernel removes the mode before Hyprland ever sees it, and two limits stack on a dock path.

1. **Two lanes.** Many USB-C docks and hubs that also carry USB 3 data run DisplayPort Alt Mode on two of the four high-speed lanes. Two HBR3 lanes carry about 12.96 Gbps of payload, half of a direct 4-lane link. The Lenovo dock in omarchy 13119 and the hub in i915 16640 both negotiate 2 lanes.

2. **Conservative DSC behind MST.** The mode must then fit after Display Stream Compression, and the Intel driver reports a compressed rate of 16 bits per pixel in `i915_display_info`. In i915 16640 (Raptor Lake) 2560x1440@240 needs about 1056.75 MHz × 16 bpp, roughly 16.9 Gbps, which exceeds the 2-lane budget, so the mode is pruned. The reporter calculates that it would fit at 8 bpp, and the same laptop, hub and monitor run 240 Hz on Windows. i915 17207 (Meteor Lake, Lenovo 40AY dock) shows `port_clock=810000, lane_count=2` and `compressed-bpp:16.0000` with 3440x1440@165 missing, while a direct USB-C to DP cable offers it. i915 17228 (Tiger Lake, Dell WD19) logs the 144, 165 and 180 Hz modes as pruned with `CLOCK_HIGH`. All three are open as of 2026-10-05.

The Omarchy record `monitor-stuck-at-60hz-high-refresh` covers the general case of a missing mode. This record is the dock and MST case, where the cable is fine and the same monitor works direct.

> **Audit corrected this record.** Read i915 16640, 17207 and 17228 and omarchy 13119. All four are open as of 2026-10-05. The lane counts, `port_clock=810000, lane_count=2`, `compressed-bpp:16.0000`, the 1056.75 MHz 240 Hz timing, the 17207 direct-cable result and the 17228 CLOCK_HIGH pruning of 144/165/180 Hz all match. Two specifics are not supported. The symptom says the dock path tops out at 100 or 120 Hz, but 16640 exposes 144 Hz for its 240 Hz panel, and nothing cited shows a 60 Hz only case. The cause says Windows uses 8 bpp, but no source reports what Windows picks: 16640's reporter calculated that 8 bpp would fit and observed Windows running 240 Hz. omarchy 13119 is a different bug (a 7.2.5 amdgpu MST regression) and supports only the 2-lane dock negotiation it is cited for. The fix commands were checked for shape only: amdgpu debugfs `link_settings` exists in amdgpu_dm_debugfs.c and its `Current: 4 0x1e 16` format is shown in drm/amd 5033. The debugfs reads were not run here because they need root. Symptom and cause rewritten, fix kept.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

**1. Confirm the mode is missing, not misconfigured:**

```bash
hyprctl monitors all -j | jq -r '.[] | .name, (.availableModes | join(" "))'
```

If the fast rate is listed, this is not your record. Go to `monitor-stuck-at-60hz-high-refresh`.

**2. Read the link the dock negotiated** (root needed):

Intel (i915 or xe):

```bash
sudo sh -c 'grep -E "port_clock|lane_count|dsc-dss|compressed-bpp" /sys/kernel/debug/dri/*/i915_display_info'
```

AMD:

```bash
journalctl -k -b | grep 'DM_MST'          # e.g. "DM_MST: DP14, 2-lane link detected"
sudo sh -c 'for f in /sys/kernel/debug/dri/*/DP-*/link_settings; do echo "== $f"; cat "$f"; done'
```

In `link_settings` the first number after `Current:` is the lane count and the second is the link rate code (`0x14` is 5.4 Gbps per lane, `0x1e` is 8.1 Gbps per lane).

**3. Pick a remedy.** No monitor rule can bring back a mode the kernel pruned.

- Connect the monitor directly with a USB-C to DisplayPort cable. That uses all four lanes, and it is how the i915 17207 reporter got 165 Hz on the same laptop.
- Put fewer monitors on the hub. MST splits one link's bandwidth across every display behind it.
- Run the highest rate the dock does offer, copied verbatim from `availableModes`, in `~/.config/hypr/monitors.lua`:

```lua
hl.monitor({ output = "desc:<description from hyprctl monitors>", mode = "3440x1440@99.98", position = "auto", scale = 1 })
```

On Intel, follow i915 16640 and 17207 for a driver change to the compressed bpp choice.

**Verify.** On a direct cable the fast rate appears in `availableModes` and `hyprctl monitors` runs it. On the dock, the pinned rate holds after a replug.

Sources: <https://gitlab.freedesktop.org/drm/i915/kernel/-/work_items/16640> · <https://gitlab.freedesktop.org/drm/i915/kernel/-/work_items/17207> · <https://gitlab.freedesktop.org/drm/i915/kernel/-/work_items/17228> · <https://github.com/omacom/omarchy/issues/13119> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_debugfs.c> · <https://gitlab.freedesktop.org/drm/amd/-/work_items/5033>

---

## Stop VRR flicker and backlight pumping with adaptive sync on

`vrr-flicker-and-brightness-pumping` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** With adaptive sync / FreeSync enabled the screen flickers, or the backlight visibly pumps brighter and darker, especially in fullscreen YouTube, in Chromium/Electron windows, or when the frame rate drops out of the VRR window. Some users see a brief black flash on every mouse click.

**Cause.** VRR drives the panel outside its stable refresh window when the frame rate swings (idle desktop, video with a fixed cadence, browser compositing). Many FreeSync/'G-SYNC Compatible' panels are not validated and flicker at low refresh. Hyprland's global `misc:vrr = 1` applies this to the whole desktop, not just games.

**Fix.**

Restrict VRR to fullscreen apps instead of the whole desktop, or turn it off per output. In `~/.config/hypr/looknfeel.lua` (Omarchy) or your Hyprland config:

```lua
hl.config({
  misc = {
    vrr = 2,      -- 0 off, 1 always, 2 fullscreen only, 3 fullscreen with video/game content type
  },
})
```

Per-monitor, so a flickery panel stays fixed-rate while a good one keeps VRR:

```lua
hl.monitor({ output = "DP-1", mode = "2560x1440@240", position = "0x0", scale = 1, vrr = 1 })
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "2560x0", scale = 1, vrr = 0 })
```

On Hyprland <= 0.54: `misc { vrr = 2 }` and `monitor=DP-1,2560x1440@240,0x0,1,vrr,1`.

If cursor movement causes frame-rate spikes in fullscreen VRR:

```lua
hl.config({ cursor = { no_break_fs_vrr = 1, no_hardware_cursors = 1, min_refresh_rate = 60 } })
```

VRR needs DisplayPort on most hardware. Over HDMI it requires HDMI 2.1 VRR support on both ends.

**Verify.** `hyprctl monitors` shows `vrr: true` only on the outputs you intended, and the flicker stops on the desktop.

Sources: <https://wiki.archlinux.org/title/Variable_refresh_rate> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/Hyprland/issues/5797>

---

## Fix brightness keys that move the OSD but never change the laptop screen

`brightness-keys-drive-wrong-backlight-device` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `grub`, `intel`, `laptop`, `limine`, `manjaro`, `nvidia`, `omarchy`, `omarchy-4`, `systemd-boot`

**Symptom.** The brightness keys show the OSD going up and down, but the screen never gets brighter or dimmer. `ls /sys/class/backlight` lists two devices, for example `intel_backlight` and `nvidia_wmi_ec_backlight`, or `acpi_video0` and `amdgpu_bl1`, and writing to the one in use does nothing. Common on Optimus and MUX laptops and on some Razer, Lenovo and Acer models. The kernel log may show `nvidia-modeset: ACPI reported no NVIDIA native backlight available; attempting to use ACPI backlight.`

**Cause.** The kernel can register more than one backlight interface for the same panel, and only one of them actually drives it. Since Linux 6.1 the kernel picks which types register from ACPI heuristics, and `acpi_backlight=` overrides that choice. On Omarchy, `omarchy-hw-display` picks the device in a fixed order: `gmux_backlight`, then `amdgpu_bl*`, then `intel_backlight`, then `acpi_video*`, then the first device listed. If the working interface is a different one, for example `nvidia_wmi_ec_backlight` on a hybrid laptop, or the earlier entry in the order is the dead one, every key press goes to an interface that the panel ignores.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A wrong kernel parameter can leave you with no backlight control, or a black panel until it is removed. Per the Arch wiki, `acpi_backlight=vendor` can make the interface disappear entirely on NVIDIA-only laptops. On Omarchy 4, writing `KERNEL_CMDLINE[default]=` without the `+`, or using a bare `tee` instead of `tee -a`, wipes Omarchy's own parameters, including `initramfs_async=0`, which keeps the Plymouth LUKS prompt working. `limine-mkinitcpio` rewrites the UKI on the ESP, so run `df -h /boot` first. To recover, remove the parameter in the Limine boot menu editor, or boot a Limine snapshot entry.

**Fix.**

**Find the interface that works.** Try each device listed and watch the screen:

```bash
ls /sys/class/backlight/
omarchy-hw-display                       # the one Omarchy's keys use
brightnessctl -d intel_backlight set 30%
brightnessctl -d nvidia_wmi_ec_backlight set 30%
```

**Quick fix with no reboot:** rebind the keys in `~/.config/hypr/bindings.lua` to the device that worked:

```lua
hl.unbind("XF86MonBrightnessUp")
hl.unbind("XF86MonBrightnessDown")
o.bind("XF86MonBrightnessUp", "Brightness up", "brightnessctl -d nvidia_wmi_ec_backlight set +5%", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Brightness down", "brightnessctl -d nvidia_wmi_ec_backlight set 5%-", { locked = true, repeating = true })
```

**Proper fix: make the kernel register the right type.** Pick the parameter from what worked, using the Arch wiki's guidance:

- `acpi_backlight=native`: the GPU's own interface works (`intel_backlight`, `amdgpu_bl*`). The wiki also gives it for NVIDIA-only MUX laptops where `nvidia_wmi_ec_backlight` registers but does nothing.
- `acpi_backlight=nvidia_wmi_ec`: some Optimus laptops.
- `acpi_backlight=video`, with `amdgpu.backlight=0` on AMD if needed: Razer Blade 14, Lenovo Yoga Slim 7, Lenovo IdeaPad Gaming 3, Acer AN517-41.

If you already pass an `acpi_backlight=` parameter, remove it first. The wiki says the 6.1 rework made old values counterproductive.

**Omarchy 4** builds the kernel command line into the UKI. Add a drop-in that sorts after `omarchy-defaults.conf`, and always use `+=`:

```bash
sudo tee -a /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" acpi_backlight=native"
EOF
sudo limine-mkinitcpio && sudo limine-update && sudo reboot
```

**Plain Arch:** add it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` and run `sudo grub-mkconfig -o /boot/grub/grub.cfg`, or append it to `options` in `/boot/loader/entries/*.conf` for systemd-boot. Then reboot.

**Verify.** `cat /proc/cmdline` contains the new parameter, `ls /sys/class/backlight` shows the working device (alone, or first in `omarchy-hw-display`'s order), and the brightness keys change the panel.

Sources: <https://wiki.archlinux.org/title/Backlight> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hw-display>

---

## Stop an external monitor going black every time the Display panel opens

`ddc-brightness-probe-blanks-external-monitor` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `ddcutil`, `desktop`, `hyprland`, `intel`, `laptop`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Every time I open the display module in the bar, or run `omarchy brightness display --monitor DP-1`, that one external monitor goes completely black for two or three seconds and then comes back by itself. Nothing is changed on it. It happens on every open, not only the first. Some people see multicoloured pixel noise instead of black. It is common with a monitor behind a USB-C to HDMI adapter, or one that answers `ddcutil detect` but has no readable brightness. With the panel left open, the journal fills with lines like:

```
Error detecting VCP version using VCP feature xDF: DDCRC_RETRIES; EREMOTEIO(10)
```

roughly every 50 seconds, and `journalctl -k` shows nothing at all.

**Cause.** `omarchy-brightness-display-ddc` caches each connector's I2C bus in `$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc/<connector>.bus`, so that the expensive `ddcutil --skip-ddc-checks detect --brief` scan runs only once. If the scan finds no monitor it writes an `unavailable <timestamp>` entry that holds for 60 seconds. The failing case takes a different path. When `detect` finds the monitor but `getvcp 10` (brightness) fails, `read_brightness` runs `rm -f "$cache_file"` and keeps no record of the failure. So every later call, and the Display panel calls it each time it opens or refreshes, repeats the full `detect` scan, and that scan probes the DDC channel of every attached display. Some monitors, and some converters inside USB-C to HDMI cables, drop and retrain the link when probed, which is the blank. Because DDC/CI is I2C sideband traffic there is no modeset and no kernel log line. The `rm -f` branch is still present in 4.0.4-1 and on the `quattro` branch as of 2026-10-04, and the issue is open.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** The entry disables DDC brightness for that connector name, not for that monitor. If a different monitor later gets the same name, for example after a dock replug renumbers the ports, its brightness keys and slider stop working too. Delete the `.bus` file and the tmpfiles line to undo it.

**Fix.**

**Confirm it is this path.** Replace `DP-2` with the monitor that blanks (`hyprctl monitors | grep ^Monitor`):

```bash
omarchy-brightness-display --monitor DP-2; echo "exit=$?"
ls -la "$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc/"
```

If the command exits 1 and the directory has no `DP-2.bus` entry, this is the bug.

**Workaround (Omarchy 4): write the negative verdict the script does not keep.** The cache check treats an entry as fresh while `now - stamp < 60`, so a far-future stamp makes it permanent and the helper returns before it ever calls `ddcutil`:

```bash
mkdir -p "$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc"
echo "unavailable 9999999999" > "$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc/DP-2.bus"
```

`$XDG_RUNTIME_DIR` is a tmpfs that is emptied at logout, so to keep it across sessions use a user tmpfiles rule:

```
# ~/.config/user-tmpfiles.d/omarchy-ddc-skip.conf
d %t/omarchy-brightness-display-ddc 0755 - - -
f+ %t/omarchy-brightness-display-ddc/DP-2.bus 0644 - - - unavailable 9999999999
```

The user unit that applies these rules is disabled on Omarchy 4 (checked on 4.0.4-1), so enable it:

```bash
systemctl --user enable systemd-tmpfiles-setup.service
systemd-tmpfiles --user --create
```

This gives up DDC brightness on that connector. On the monitors this bug hits, the brightness read was already failing, so nothing that worked is lost.

**Verify.** Open and close the Display panel several times. The monitor no longer blanks. `cat "$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc/DP-2.bus"` prints `unavailable 9999999999`, and `journalctl --user -b | grep -c DDCRC_RETRIES` stops climbing.

Sources: <https://github.com/omacom/omarchy/issues/6855> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display-ddc>

---

## Pin a 4K monitor to 120 Hz when its 144 Hz DSC mode commits but shows nothing

`dsc-4k144-mode-accepted-but-monitor-black` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `dock`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** 4K 144 Hz monitor on USB-C or DisplayPort, AMD laptop. `hyprctl monitors` says the output is running `3840x2160@144` and there is no config error, but the monitor shows no picture or reports no signal. Setting `3840x2160@120` brings the picture straight back on the same cable and port. Windows runs 144 Hz on the same hardware. Through some USB4 docks, switching to 144 Hz also resets every USB device on the dock.

**Cause.** 4K at 144 Hz with 8-bit colour needs about 1265.75 MHz × 24 bpp, roughly 30.4 Gbps, while a 4-lane DisplayPort 1.4 HBR3 link carries about 25.9 Gbps of payload, so the mode only fits with Display Stream Compression. On the reported Krackan Point machine (drm/amd 5033, open) amdgpu selects DSC, trains HBR3 on 4 lanes, commits the stream and reports success, yet the monitor displays nothing. Through a Lenovo USB4 dock the same switch hits a kernel WARNING in `update_dpia_stream_allocation_table` and a USB topology reset. Because the kernel accepts the commit, Hyprland sees a working mode and never falls back to a neighbouring rate. Omarchy's default catch-all rule uses `mode = "preferred"`, so a monitor whose EDID prefers 144 Hz lands in this state on first plug.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**1. Get the picture back.** From the laptop panel, or over ssh (`hyprctl -i 0` picks the running instance there):

```bash
hyprctl monitors all -j | jq -r '.[] | "\(.name)  \(.width)x\(.height)@\(.refreshRate)  desc:\(.description)"'
hyprctl eval 'hl.monitor({ output = "DP-2", mode = "3840x2160@120", position = "auto", scale = 1.5 })'
```

**2. Confirm DSC was the difference** (AMD, root needed):

```bash
sudo sh -c 'for f in /sys/kernel/debug/dri/*/DP-*/dsc_clock_en; do echo "$f: $(cat $f)"; done'
```

A `1` on the connector at 144 Hz and `0` at 120 Hz matches this record.

**3. Pin the working rate.** In `~/.config/hypr/monitors.lua`, add a rule for this monitor below the catch-all. Matching on `desc:` survives a port change. Copy the rate verbatim from `availableModes`:

```lua
hl.monitor({ output = "desc:<description from step 1>", mode = "3840x2160@120", position = "auto", scale = 1.5 })
```

On Hyprland 0.54 and older (hyprlang): `monitor = desc:<description>, 3840x2160@120, auto, 1.5`.

**4. Things that do not help** on the reported hardware: changing cables, because 120 Hz already works on the same cable, and asking Hyprland for `highrr`, which picks the broken 144 Hz mode. Watch drm/amd 5033 for a kernel fix before removing the pin.

**Verify.** `hyprctl monitors` shows the output at the pinned 120 Hz rate after a reboot and after replugging, and the monitor shows a picture.

Sources: <https://gitlab.freedesktop.org/drm/amd/-/work_items/5033> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/monitors/modes.md> · <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_debugfs.c>

---

## Fix a USB4 or Thunderbolt monitor reporting No signal after a reboot

`usb4-displayport-no-signal-after-reboot` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** A monitor connected over USB4/Thunderbolt DP-Alt-Mode works perfectly once you are in the session, but after a reboot the screen reports 'No signal' on the Thunderbolt input from the bootloader menu onwards. The only way back is to plug in the native DisplayPort or HDMI cable, get a picture, then replug the USB4 cable.

**Cause.** The Thunderbolt tunnel is not established before the OS takes over the display: the device is not pre-boot authorized, and the DP tunnel only comes up once the Thunderbolt stack is loaded and the device is authorized in Linux. Until then the connector reports nothing.

> **Audit corrected this record.** The technical content is accurate and matches the Arch Thunderbolt wiki exactly. The udev rule `ACTION=="add", SUBSYSTEM=="thunderbolt", ATTR{authorized}=="0", ATTR{authorized}="1"` is that page's verbatim 99-removable.rules example, and the force_power path with GUID 86CCFD48-205E-4A77-9C48-2021CBEDE341 is its verbatim example too. `sudo pacman -S bolt` is correctly a plain -S with no -Sy partial-upgrade hazard, boltctl list is right, and the connector re-probe loop plus `hyprctl reload` is consistent with the other records. basecamp/omarchy#374 exists ('Problems with Display Port over USB4 (BeeLink SER9)'). What is missing is a warning: steps 1 and 2 together, dropping BIOS Thunderbolt security to `none` AND blanket auto-authorizing every device that is ever plugged in, remove Thunderbolt's DMA-attack protection entirely. That is a real security downgrade being handed to a user as a copy-paste, and it needs to be stated. `udevadm control --reload` also needs a `trigger` to affect already-present devices.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting the Thunderbolt security level to `none` or auto-authorizing every device removes the protection against DMA attacks from a malicious plugged-in device. Do not do this on a machine that gets plugged into untrusted docks or cables.

**Fix.**

1. In firmware/BIOS, enable Thunderbolt pre-boot support. Prefer security level `dponly` (tunnels DisplayPort only, no PCIe/DMA) over `none`. `dponly` is enough to get a picture at the boot menu and keeps DMA protection. This is what makes the boot menu appear on the USB4 input.

2. Auto-authorize Thunderbolt devices in Linux so the tunnel comes up without a prompt:

> **Security warning:** this authorizes *every* Thunderbolt device the moment it is plugged in, including one plugged in while the machine is unattended. Combined with a BIOS security level of `none` it removes Thunderbolt's DMA-attack protection. On a laptop that leaves your sight, prefer enrolling your dock once with `boltctl enroll <uuid>` instead of the blanket rule below.

```bash
sudo pacman -S bolt
boltctl list                       # find your dock's UUID
sudo boltctl enroll <uuid>         # trust just this dock, persistently
```

If you accept the risk and want everything auto-authorized:

```bash
sudo tee /etc/udev/rules.d/99-removable.rules <<'EOF'
ACTION=="add", SUBSYSTEM=="thunderbolt", ATTR{authorized}=="0", ATTR{authorized}="1"
EOF
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=thunderbolt
```

3. If the tunnel is up but the connector is stale, force a re-probe:

```bash
for c in /sys/class/drm/card*-DP-*; do
  [ -e "$c/status" ] || continue
  echo off | sudo tee $c/status; sleep 1
  echo on | sudo tee $c/status; echo detect | sudo tee $c/status
done
hyprctl reload
```

4. If your controller powers itself down, force it on (Dell/Intel WMI only, and the attribute is absent on machines that do not expose it):

```bash
echo 1 | sudo tee /sys/bus/wmi/devices/86CCFD48-205E-4A77-9C48-2021CBEDE341/force_power
```

**Verify.** Reboot with only the USB4 cable attached: the bootloader menu and then the Hyprland session both appear on that input, and `hyprctl monitors` shows the native mode.

Sources: <https://github.com/basecamp/omarchy/issues/374> · <https://wiki.archlinux.org/title/Thunderbolt> · <https://github.com/basecamp/omarchy/issues/7328>

---

## Wake a USB4 monitor that stays dark on hotplug by setting a lower mode first

`usb4-monitor-dark-on-hotplug-two-lane-tunnel` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `thunderbolt`, `usb4`, `wayland`

**Symptom.** AMD Ryzen AI 300 (Strix Point) laptop with USB4, a Framework Laptop 13 in the report. Plug a 4K monitor into the USB4 port: it is detected, the EDID is read and modes are listed, but the screen never lights. Windows lights the same monitor at 4K@60 immediately. The report was made under GNOME, where Mutter logged `Page flip failed: drmModeAtomicCommit: No space left on device` over a thousand times. Under Hyprland the same failure should show the output at `0x0` in `hyprctl monitors all` and failed commits ending in `No space left on device` in the Hyprland log, but no Hyprland report has confirmed that.

**Cause.** On hotplug the USB4 DisplayPort tunnel first comes up as a 2-lane DP 1.4 link, about 12.96 Gbps, and 3840x2160@60 at 8 bits needs about 14.25 Gbps, so the kernel's atomic check fails with `ENOSPC`. The kernel log shows `DM_MST: DP14, 2-lane link detected`. The bandwidth is there once the tunnel settles: in drm/amd 5011 (open) setting 4K@30 first, waiting 3 seconds and then switching to 4K@60 succeeds, with the laptop panel at 2880x1920@120 alongside. The reporter's reading is that the driver neither waits for the full tunnel allocation before the first modeset nor retries after it grows. That is an analysis in the report, not a confirmed driver diagnosis. The workaround was demonstrated under GNOME. On Hyprland the same two-step modeset is done with `hyprctl eval`, which the report did not test.

> **Audit corrected this record.** Read drm/amd 5011 in full (open): Framework 13 Ryzen AI 300 (Strix Point), BenQ RD320UA, `DM_MST: DP14, 2-lane link detected`, 12.96 versus 14.25 Gbps, ENOSPC on every commit, and 4K@30 then a 3-second wait then 4K@60 succeeds with eDP-1 at 2880x1920@120. Three statements go beyond it. The symptom presents Hyprland behaviour (`0x0` in hyprctl, a Hyprland log line) as observed, but the report is GNOME only, where Mutter logged `Page flip failed: drmModeAtomicCommit: No space left on device`. The cause states as fact that the driver neither waits nor retries, which is the reporter's analysis under a heading that says 'appears'. And the fix claims `hyprctl keyword` does nothing under a Lua config, which no source here supports: the Lua-era hyprctl wiki page documents `eval` and `dispatch` and is silent on `keyword`, and `hyprctl --help` on 0.56.2 still lists `keyword`. Confirmed on this machine: `hyprctl eval` exists on 0.56.2, the Hyprland wiki documents the `hl.monitor` fields used, `o.bind` in /usr/share/omarchy/default/hypr/helpers.lua wraps a string in `hl.dsp.exec_cmd`, and SUPER + CTRL + ALT + M is not bound by any Omarchy default. Nothing was exercised on USB4 hardware, and `hyprctl eval` was not run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**1. Confirm the signature:**

```bash
journalctl -k -b | grep -E 'DM_MST: DP14, [0-9]-lane'
grep -c 'No space left on device' "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log"
hyprctl monitors all -j | jq -r '.[] | "\(.name) \(.width)x\(.height)"'
```

**2. Step the mode up by hand.** Replace `DP-9` with the name from step 1. A rule set with `eval` lasts until the next config reload:

```bash
hyprctl eval 'hl.monitor({ output = "DP-9", mode = "3840x2160@30", position = "auto", scale = 1.5 })'
sleep 3
hyprctl eval 'hl.monitor({ output = "DP-9", mode = "3840x2160@60", position = "auto", scale = 1.5 })'
```

**3. Keep it one keypress away.** Save it as a script:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/usb4-monitor-kick <<'EOF'
#!/bin/bash
out="${1:-DP-9}"
hyprctl eval "hl.monitor({ output = \"$out\", mode = \"3840x2160@30\", position = \"auto\", scale = 1.5 })"
sleep 3
hyprctl eval "hl.monitor({ output = \"$out\", mode = \"3840x2160@60\", position = \"auto\", scale = 1.5 })"
EOF
chmod +x ~/.local/bin/usb4-monitor-kick
```

and bind it in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + CTRL + ALT + M", "Kick USB4 monitor", "~/.local/bin/usb4-monitor-kick DP-9")
```

Check the key combination is free first with `omarchy menu keybindings --print`.

**Plain Arch with a hyprlang config (Hyprland 0.54 or older):** `hyprctl keyword monitor DP-9,3840x2160@30,auto,1.5`, wait 3 seconds, then the same with `@60`. Omarchy 4 ships a Lua config, so use the `hyprctl eval` form above there.

**Verify.** `hyprctl monitors` shows the output at `3840x2160@60` and the monitor is lit. `grep -c 'No space left on device'` on the log stops growing.

Sources: <https://gitlab.freedesktop.org/drm/amd/-/work_items/5011> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/using-hyprctl.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/monitors/_index.md>

---

## Keep a rotated laptop or handheld panel rotated after a reboot

`rotated-internal-panel-loses-transform-clamshell` · severity: **medium** · frequency: **rare** · applies to: `gpd`, `handheld`, `hyprland`, `laptop`, `omarchy`, `omarchy-4`, `rotated-display`

**Symptom.** I set `transform = 3` in `~/.config/hypr/monitors.lua` to rotate my built-in screen (reported on a GPD handheld, whose panels are natively portrait), and it works until I reboot. After a reboot the config still says `transform = 3` but the screen is not rotated. Changing the transform value, saving, then changing it back fixes it until the next reboot. A related report on a Dell Latitude says the internal panel's manually set `position` snaps back to an automatic one within about a second.

**Cause.** LIKELY, inferred from reading `omarchy-hyprland-monitor-clamshell` and `omarchy-hyprland-monitor-watch` on 4.0.4-1 and not yet confirmed by the reporter. Omarchy autostarts `omarchy-hyprland-monitor-watch`, which runs the clamshell script when it starts at login, again 1, 4 and 11 seconds later, and the same way after every monitor added or removed event. On a machine it treats as a laptop (an ACPI lid switch, or a portable DMI chassis type) it also runs it every 2 seconds while an external monitor is active. It does not run it on a config reload. When the internal panel's active scale differs from the scale the script reads from `monitors.lua`, it re-applies the panel with `hyprctl eval "hl.monitor({ output = \"$INTERNAL\", mode = \"preferred\", position = \"$position\", scale = $scale })"`. That rule carries no `transform`, so the panel falls back to unrotated, and its `position` comes from a single-line rule naming the panel's connector, or `auto` when there is none. A mismatch is expected when the configured scale does not divide the panel's resolution cleanly, which the Hyprland wiki calls an invalid scale, because the active scale then differs from the one written. The reported config used `scale = "1.2"` on the catch-all rule, and the report does not give the panel's resolution. Saving `monitors.lua` reloads the whole config, which re-applies the full rule with its transform, and because a reload does not trigger the watcher, the rotation then holds until the next login or hotplug. That explains why "change it and change it back" works until a reboot. To confirm, watch `hyprctl monitors -j` for the transform dropping to 0 within about 11 seconds of login.

> **Audit corrected this record.** Read /usr/share/omarchy/bin/omarchy-hyprland-monitor-clamshell, omarchy-hyprland-monitor-watch, omarchy-hyprland-monitor-laptop, omarchy-hw-laptop, omarchy-hyprland-monitor-scaling and omarchy-refresh-config on 4.0.4-1, and issues #7066 and #7326 in full. The core inference holds and is honestly flagged LIKELY: sync_internal_scale re-applies the panel with an hl.monitor eval that has no transform when the active scale differs from the configured one, position comes from a connector-named single-line rule or auto, and the reported config is scale "1.2" with transform = 3 on the catch-all. Reading the watcher strengthens it: it runs the clamshell script at login and again 1, 4 and 11 seconds later, and not on configreloaded, which explains why the rotation holds after a save and fails after a reboot. The cause misstated the 2-second poll, which only runs on a machine omarchy-hw-laptop accepts. The danger was wrong: omarchy-refresh-config copies the user file to monitors.lua.bak.<epoch> before replacing it, so nothing is lost. Whether 1.2 is invalid for the reporter's panel is not known, because #7066 gives no resolution. The fix also missed that the Display panel's scale buttons drop the transform the same way. Nothing was reloaded or re-applied on this machine.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Do not try to reset this with `omarchy refresh config hypr/monitors.lua`. It replaces your file with the shipped template, which has no rotation and no per-panel rule. It saves your version first as `~/.config/hypr/monitors.lua.bak.<epoch seconds>`, so if you ran it, copy that backup back over `monitors.lua`.

**Fix.**

**Give the internal panel its own one-line rule** with the transform, an explicit position, and a scale Hyprland applies exactly. The script matches only single-line rules naming the connector in a quoted string. First read the panel's name, current scale and transform:

```bash
hyprctl monitors all -j | jq -r '.[] | "\(.name) scale=\(.scale) transform=\(.transform)"'
```

```lua
-- ~/.config/hypr/monitors.lua
hl.monitor({ output = "DSI-1", mode = "preferred", position = "0x0", scale = 1.25, transform = 3 })
```

Use your panel's name (`eDP-1`, `DSI-1`) and a scale that divides its resolution cleanly, then run `hyprctl reload`. Check that `hyprctl monitors -j` reports exactly the scale you wrote. If it reports a different number, use that number in the rule, so the watcher sees no mismatch and leaves the panel alone.

Or keep the stock `local omarchy_monitor_scale = "auto"`. The watcher does not re-apply a scale it cannot read as a number, but a `transform` on the catch-all rule still applies to every monitor, so a per-panel rule is cleaner.

The Display panel's scale buttons have the same gap: `omarchy-hyprland-monitor-scaling` re-applies the focused monitor with `position = "auto"` and no `transform`, so using them on the rotated panel unrotates it until the next `hyprctl reload`. Change the scale in `monitors.lua` instead.

Also check the record `hyprland-invalid-scale-not-divisible` for choosing a scale Hyprland accepts.

**Verify.** Reboot, wait ten seconds, then run `hyprctl monitors -j | jq '.[] | {name, scale, transform, x, y}'`. The panel still shows `transform: 3` and the position you set, and both survive plugging in and removing an external monitor.

Sources: <https://github.com/omacom/omarchy/issues/7066> · <https://github.com/omacom/omarchy/issues/7326> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-clamshell> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/monitors/positioning.md> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-watch>

---

## Fix monitors in the wrong order or with a dead gap between them

`monitor-positions-wrong-order-with-scaling` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Two monitors are in the wrong order (you move the mouse right and it lands on the left screen), or there is a dead gap you have to drag the pointer through, or Hyprland warns that monitors overlap. Setting `position = "3840x0"` for a screen next to a 4K display does not put it where you expect.

**Cause.** Hyprland positions monitors on a virtual layout in *scaled logical* pixels, not physical pixels. A 3840x2160 display at scale 2 is 1920 logical pixels wide, so the monitor to its right starts at x=1920. A rotated (transform 1/3) monitor contributes its rotated logical size. Getting this wrong either leaves a gap or makes the outputs overlap, which Hyprland refuses.

**Fix.**

Compute positions from the scaled resolution. Example: 4K at scale 2 on the left, 1080p at scale 1 on the right:

```lua
hl.monitor({ output = "DP-1", mode = "3840x2160@144", position = "0x0",    scale = 2 })
hl.monitor({ output = "DP-2", mode = "1920x1080@60",  position = "1920x0", scale = 1 })
```

A 1440p panel rotated 90 degrees to the left of a 1080p one (rotated logical width = 1440):

```lua
hl.monitor({ output = "DP-1", mode = "2560x1440@60", position = "-1440x0", scale = 1, transform = 1 })
hl.monitor({ output = "DP-2", mode = "1920x1080@60", position = "0x0", scale = 1 })
```

Y is inverted-cartesian: a negative y puts a monitor *higher*. If you just want them auto-arranged left-to-right, use the special values:

```lua
hl.monitor({ output = "DP-2", mode = "preferred", position = "auto-right", scale = 1 })
-- also: auto, auto-left/up/down, auto-center-right/left/up/down
```

Read back what Hyprland actually computed:

```bash
hyprctl monitors -j | jq -c '.[] | {name, x, y, width, height, scale, transform}'
```

**Verify.** The pointer crosses from one screen to the other with no gap and in the physical direction you expect, and no overlap warning is drawn.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md>

---

## Newly plugged-in monitor has a black background and no bar until you restart the wallpaper/bar daemon

`no-wallpaper-or-bar-on-hotplugged-monitor` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-3`, `omarchy-4`, `wayland`

**Symptom.** I dock the laptop or plug in a second screen. Hyprland picks it up fine (windows move there, `hyprctl monitors` lists it), but the new display is just black behind the windows, and the top bar only draws on the original screen. hyprpaper's log says `Monitor DP-3 does not have a target! A wallpaper will not be created.` Killing and restarting hyprpaper and the bar fixes it until the next hotplug.

**Cause.** Wallpaper and bar daemons are ordinary Wayland clients, not part of the compositor. hyprpaper assigns a wallpaper per output at config-parse time. An output that did not exist then has no target, and hyprpaper logs exactly that message rather than falling back (hyprwm/hyprpaper #154, #110). The wiki is explicit that the empty-monitor entry is a *fallback* and "only applies to monitors that have never had a specific monitor target assigned", so if you have only named entries, a new connector gets nothing. Status bars behave the same way: many only enumerate outputs at startup, so a display that appears later gets no layer surface until the bar is restarted.

> **Audit corrected this record.** The hyprpaper half is accurate: the wiki documents `monitor` "If empty, will use this wallpaper as a fallback", the `fit_mode` values, `hyprctl hyprpaper wallpaper '[mon], [path], [fit_mode]'`, `listactive` with output matching the record's sample, and the exact sentence "The fallback wallpaper only applies to monitors that have never had a specific monitor target assigned." hyprpaper #154's title is literally the quoted warning. The socat/IPC listener and `o.launch_on_start` are correct, and `omarchy-restart-shell` exists and behaves as described (kills every quickshell instance for the config dir, then relaunches via `hyprctl dispatch 'hl.dsp.exec_cmd("omarchy-launch-shell")'` so it inherits the session environment). Two problems. (1) The record is tagged `omarchy-4` and leads with editing `~/.config/hypr/hyprpaper.conf`, but Omarchy 4 does not ship or use hyprpaper at all. There is not one reference to it anywhere in the quattro tree, the background/bar/lock surfaces are all the Quickshell Omarchy shell, and `omarchy-upgrade-to-quattro` removes hypridle-era packages. An Omarchy 4 user will edit a file nothing reads and conclude the record is broken. (2) The closing claim that an `Invalid config line at line N` parse failure is documented in hyprpaper #154 is not supported. That issue is a user on pre-1.0 `wallpaper = mon,path` syntax, closed not_planned with "update hyprlang and hyprpaper", and never mentions a parse-failure line.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Split the record by platform up front, because the two cases share a symptom and nothing else.

**On Omarchy 4 (Quattro), hyprpaper is not installed and `hyprpaper.conf` is not read.** The wallpaper, bar and lock surface are all the Quickshell-based Omarchy shell. A display that appears after the shell started and gets no background or bar is fixed with one command:

```bash
omarchy-restart-shell
```

It kills every running instance for the shell config dir and relaunches it from inside the Hyprland session so it inherits the correct environment. It refuses to run while the session is genuinely locked, which is the intended guard. Confirm the outputs the compositor is offering it:

```bash
hyprctl monitors all -j | jq -r '.[] | "\(.name)\tdisabled=\(.disabled)"'
```

Do not create `~/.config/hypr/hyprpaper.conf` on Omarchy 4. Nothing will read it.

**On bare Hyprland / Arch with hyprpaper**, the rest of the record is correct as written: add a `wallpaper { monitor = ... }` catch-all block with an empty `monitor`, reload with `pkill hyprpaper; hyprpaper & disown` or `systemctl --user restart hyprpaper.service`, set a live output with `hyprctl hyprpaper wallpaper 'DP-3, /home/you/Pictures/wall.jpg, cover'`, verify with `hyprctl hyprpaper listactive`, and autostart the socat `monitoradded` listener. Restart Waybar with `pkill waybar; waybar & disown` or `systemctl --user restart waybar.service`.

**Drop the #154 attribution on the parse-failure paragraph.** The advice itself is still worth keeping. Run hyprpaper in the foreground and read the first lines, because a config that fails to parse leaves every output without a target:

```bash
pkill hyprpaper; hyprpaper 2>&1 | head -20
```

Just don't cite #154 for it. That issue is a user on the pre-1.0 `wallpaper = monitor,path` syntax, and the answer there was to update hyprpaper and hyprlang.

**Verify.** `hyprctl hyprpaper listactive` lists every name from `hyprctl monitors -j | jq -r '.[].name'`. The bar should be visible on the new display without a Hyprland restart.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Hypr%20Ecosystem/hyprpaper.md> · <https://wiki.hypr.land/Hypr-Ecosystem/hyprpaper/> · <https://github.com/hyprwm/hyprpaper/issues/154> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/IPC/_index.md> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-shell>

---

## Fix a cursor that changes size between mixed-DPI monitors

`cursor-wrong-size-on-scaled-or-mixed-monitors` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** The mouse cursor is a tiny speck on the 4K screen and a giant arrow on the 1080p one, or it changes size the moment it crosses between monitors. Sometimes the cursor is completely invisible over XWayland windows or in a VM.

**Cause.** XCursor themes are bitmaps at fixed sizes, so a single `XCURSOR_SIZE` cannot be right on two displays with different scales. Omarchy ships `XCURSOR_SIZE=24` and `HYPRCURSOR_SIZE=24` in `/usr/share/omarchy/default/hypr/envs.lua`. Invisible cursors are usually a hardware-cursor plane the driver cannot commit (vmwgfx, some virtual GPUs).

**Fix.**

Set both sizes together. They must agree, or the cursor changes size between Wayland-native and XWayland surfaces. In `~/.config/hypr/looknfeel.lua` (or your own Hyprland config):

```lua
hl.env("XCURSOR_SIZE", "32")
hl.env("HYPRCURSOR_SIZE", "32")
```

On Hyprland <= 0.54: `env = XCURSOR_SIZE,32` and `env = HYPRCURSOR_SIZE,32`.

Keep GTK's own setting in sync so CSD apps agree:

```bash
gsettings set org.gnome.desktop.interface cursor-size 32
```

For an invisible cursor (VMs, vmwgfx, some NVIDIA setups), fall back to a software cursor:

```lua
hl.config({ cursor = { no_hardware_cursors = 1 } })
```

On NVIDIA, hardware cursors need `cursor.use_cpu_buffer` (default `2` = auto-on for NVIDIA). Set it to `1` if the cursor is corrupt.

Log out and back in for the env change to reach already-running apps.

**Verify.** The cursor is the same apparent physical size on both monitors and stays visible over XWayland windows.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Advanced%20and%20Cool/XWayland.md> · <https://github.com/basecamp/omarchy/issues/7918>

---

## Make brightness keys control an external monitor over DDC/CI

`external-monitor-ddc-brightness-does-nothing` · severity: **low** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `intel`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** On Omarchy 4 the brightness keys and the Display panel slider work on the laptop panel but do nothing on my external monitor, or the panel shows `FIXED BRIGHTNESS` for it. `omarchy-brightness-display --monitor DP-1` exits 1 with no output.

**Cause.** Omarchy 4 controls external monitor brightness over DDC/CI with ddcutil (`omarchy-brightness-display-ddc`, added in Quattro by omarchy pull request 6490, with ddcutil installed by a migration). The script maps the Hyprland connector to an I2C bus through `ddcutil detect`, then reads and writes VCP feature 0x10. Any of these breaks it:

- DDC/CI is switched off in the monitor's on-screen menu, or a monitor feature such as dynamic contrast or an eye-care mode is holding brightness.
- `i2c-dev` is not loaded or the user cannot open `/dev/i2c-*`. The ddcutil package loads it at boot through `/usr/lib/modules-load.d/ddcutil.conf`, and its udev rule `/usr/lib/udev/rules.d/60-ddcutil-i2c.rules` tags video-adapter I2C buses `uaccess`.
- NVIDIA's proprietary driver fails I2C on some cards.
- The monitor sits behind an MST dock or hub. It appears on a virtual connector with no I2C bus of its own, and ddcutil refuses the physical port's bus because the kernel reports that port disconnected (omarchy 14005, open, no fix in 4.0.4).
- A failed lookup is cached as `unavailable` for 60 seconds in `$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc/`, so fixing the monitor and retrying immediately still fails.

Apple displays use a different path, and all-in-one built-in panels are wrongly sent down this one. Both have their own records.

> **Audit corrected this record.** Read /usr/share/omarchy/bin/omarchy-brightness-display-ddc and omarchy-brightness-display on this machine: the `ddcutil detect` bus mapping, VCP 0x10, the 60-second `unavailable` cache under `$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc/` and the silent exit 1 all match. PR 6490 'Support external monitor brightness in Quattro' merged 2026-08-01 into quattro. Migration 1785608251.sh runs `omarchy-pkg-add ddcutil`. 'FIXED BRIGHTNESS' is in shell/plugins/panels/monitor/Panel.qml. omarchy 14005 is open and matches the MST description exactly. ddcutil.com/nvidia gives the same `options nvidia NVreg_RegistryDwords=RMUseSwI2c=0x01;RMI2cSpeed=100` line and the /proc check. /etc/mkinitcpio.conf.d here has `modconf` in HOOKS and the nvidia modules in MODULES, so the UKI rebuild with `limine-mkinitcpio` is the right step. One misattribution: /usr/lib/modules-load.d/ddcutil.conf (`i2c-dev`) and the udev rule are owned by the ddcutil 2.2.7-1 package (`pacman -Qo`), not by Omarchy, so plain Arch with ddcutil gets them too. The cause is corrected for that. The fix holds as written. Not exercised: no ddcutil command or module load was run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** The NVIDIA `RegistryDwords` option is undocumented by NVIDIA. If the display misbehaves after it, delete `/etc/modprobe.d/nvidia-i2c.conf` and rebuild the initramfs again.

**Fix.**

**1. Run the pieces by hand:**

```bash
pacman -Q ddcutil
hyprctl monitors -j | jq -r '.[].name'
omarchy-brightness-display-ddc DP-1; echo "exit $?"
ddcutil detect
```

**2. Act on what `ddcutil detect` shows.**

- **Monitor listed with an I2C bus:** test it directly with `ddcutil --bus N getvcp 10`. If that fails, enable DDC/CI in the monitor's menu and turn off dynamic contrast or eye-care modes. Then clear Omarchy's cache and retry:

```bash
rm -rf "$XDG_RUNTIME_DIR/omarchy-brightness-display-ddc"
omarchy-brightness-display --monitor DP-1 50%
```

- **No `/dev/i2c-*` devices or permission errors:**

```bash
lsmod | grep i2c_dev || sudo modprobe i2c-dev
ddcutil environment          # prints what it thinks is wrong
```

- **NVIDIA proprietary driver and no monitor detected:** ddcutil's documented workaround is an undocumented driver option. Omarchy bakes `/etc/modprobe.d` into the UKI, so rebuild it:

```bash
echo 'options nvidia NVreg_RegistryDwords=RMUseSwI2c=0x01;RMI2cSpeed=100' | sudo tee /etc/modprobe.d/nvidia-i2c.conf
# Omarchy 4
sudo limine-mkinitcpio && sudo reboot
# plain Arch
sudo mkinitcpio -P && sudo reboot
# after reboot
grep RegistryDwords /proc/driver/nvidia/params
```

- **Monitor behind an MST dock or hub, not listed at all:** no Omarchy fix as of 4.0.4. Use the monitor's own buttons, or connect it directly, where `ddcutil detect` will list it.

**Plain Arch:** `sudo pacman -S ddcutil`, then `ddcutil --bus N setvcp 10 70` sets an absolute value and `ddcutil --bus N setvcp 10 + 10` a relative one. Bind those to your brightness keys.

**Verify.** `omarchy-brightness-display --monitor DP-1` prints a percentage, the keys move it with the external monitor focused, and the Display panel shows a slider for that monitor.

Sources: <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display-ddc> · <https://github.com/omacom/omarchy/pull/6490> · <https://github.com/omacom/omarchy/issues/14005> · <https://www.ddcutil.com/faq/> · <https://www.ddcutil.com/nvidia/> · <https://www.ddcutil.com/kernel_module/> · <https://www.ddcutil.com/i2c_permissions/> · <https://wiki.archlinux.org/title/Backlight>

---

## Fix Firefox rendering blurry or double-scaled on a fractional scale

`firefox-blurry-or-double-scaled-wayland` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Firefox is fuzzy on a fractionally scaled display, or is enormous. Set the screen to 150% and Firefox renders at 200% then gets shrunk back down, so every glyph looks smeared.

**Cause.** Firefox picks up GTK's scale, which is integer-only, then the compositor downscales the result. `GDK_SCALE` does not scale Firefox consistently and does not accept fractional values at all.

**Fix.**

Omarchy already sets `MOZ_ENABLE_WAYLAND=1`. In `about:config` set:

```
widget.wayland.fractional-scale.enabled = true
```

If the UI is still the wrong size, override it directly instead of using `GDK_SCALE`:

```
layout.css.devPixelsPerPx = 1.5     # 1.25 = 125%, 1.5 = 150%; -1.0 = follow system
```

Restart Firefox. Do not also set `Xft.dpi`. Setting it alongside a toolkit scale makes Firefox's UI much larger than intended.

**Verify.** `about:support` -> Graphics shows `Window Protocol: wayland`, and page text is sharp at your chosen scale.

Sources: <https://wiki.archlinux.org/title/HiDPI> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua>

---

## 144 Hz screen animates like 60 Hz once a 60 Hz monitor is plugged in

`mixed-refresh-rate-monitors-animation-judder` · severity: **low** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** On its own my 144/165/180 Hz monitor is buttery. The moment I plug in the second 60 Hz screen, window animations and workspace switches judder on both. It feels like the whole desktop dropped to the slower panel's rate. Unplugging the 60 Hz display makes it smooth again. Sometimes the fast monitor's own `hyprctl monitors` output still says `@144.00` while it visibly stutters.

**Cause.** Until late 2025, Hyprland scheduled *all* animations from a single monitor, an internal `m_mostHzMonitor`, rather than from each output's own refresh rate, so a mixed-rate setup animated everything on one shared clock. That was removed in hyprwm/Hyprland PR #12418 ("animation: improvement animation on multi refresh rate monitors"), merged 23 Nov 2025: *"I removed the logic that referenced m_mostHzMonitor for animation scheduling and switched to using each monitor's own refresh rate."* If you are on a build older than that, the judder is the bug itself. On current builds the residual causes are almost always local: `debug:vfr` turned off (which is a developer-only knob that forces a fixed render loop), VRR set to always-on so the refresh rate flaps on every cursor move, hardware-cursor plane bugs across differently-transformed/refreshed outputs, or the fast monitor having silently negotiated down to 60 Hz because of cable/bandwidth limits.

> **Audit corrected this record.** The upstream research is excellent and checks out exactly: PR #12418 is real, merged 2025-11-23, and the quoted body ("I removed the logic that referenced m_mostHzMonitor for animation scheduling and switched to using each monitor's own refresh rate.") is verbatim. `debug:vfr` defaults to `true` with the wiki's "Heavily recommended to leave enabled to conserve resources", `misc:vrr` has exactly the documented 0/1/2/3 modes, `cursor:no_hardware_cursors` is 0/1/2 as described, `render:new_render_scheduling` is the triple-buffering option, and per-monitor `vrr` is a real `hl.monitor` field. Discussion #10969 genuinely confirms `no_hardware_cursors = 1` as the working workaround for rotated/multi-monitor cursor artefacts, with multiple users confirming and one posting it in `hl.config` form. Omarchy's ALPM guard is real (`default/libalpm/hooks/00-omarchy-update-guard.hook` + `bin/omarchy-update-pacman-guard`, which aborts when it sees sync and sysupgrade together), so `omarchy update` is right. Two defects. (1) Four of the six fix steps use `hl.set("category:option", value)`, which is not a real API. The Variables page documents only `hl.config({ category = { option = ... } })`, and `hl.set` appears nowhere in the wiki or in Omarchy's quattro tree. Steps 3, 4, 5 and 6 all fail on paste and take the whole config file down with them. (2) The version floor is wrong in a way that matters: the record says "Hyprland 0.54+" but then hands the reader Lua config, and Lua only exists from 0.55 (0.54.x is hyprlang). v0.54.0 shipped 2026-02-27 so it does contain PR #12418, but a 0.54 user following this record writes Lua into a hyprlang parser.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `debug:*` options are documented "Only for developers". Do not leave `debug:vfr = false` in a config permanently. It burns power and defeats per-output scheduling. `cursor:no_hardware_cursors = 1` moves the cursor into the composited frame, which costs a little latency and GPU time on every output.

**Fix.**

Steps 1, 2 and the `hl.monitor` snippets are correct as written. Fix the version floor and replace every `hl.set` with the documented `hl.config` form.

**1. Update first.** The floor for the animation fix is a build newer than 2025-11-23 (v0.54.0+), but everything below is Lua config, which requires **0.55+**:

```bash
hyprctl version   # need 0.55 or newer for the Lua config shown here
```

On Omarchy 4 use `omarchy update` (a direct `pacman -Syu` is aborted by the ALPM guard), and elsewhere `sudo pacman -Syu`.

**2.** Unchanged. Check the *reported* mode with `hyprctl monitors -j | jq ...` and pin the mode with `hl.monitor({...})` if the fast panel negotiated down.

**3-6. The option settings.** All four go in one call in `~/.config/hypr/looknfeel.lua`:

```lua
hl.config({
  debug  = { vfr = true },                  -- default true; "heavily recommended to leave enabled"
  misc   = { vrr = 2 },                     -- 0 off, 1 on, 2 fullscreen only, 3 fullscreen video/game
  cursor = { no_hardware_cursors = 1 },     -- 0 hw if possible, 1 never, 2 auto
  render = { new_render_scheduling = true },-- triple buffering on weaker GPUs
})
```

Apply them one at a time rather than all at once, so you learn which one actually mattered. `hyprctl eval` takes the same Lua and does not touch your files:

```bash
hyprctl eval 'hl.config({ cursor = { no_hardware_cursors = 1 } })'
```

The per-monitor `vrr` variant in the record is correct and is the better option if only one display should get VRR:

```lua
hl.monitor({ output = "DP-1", mode = "2560x1440@165", position = "0x0", scale = 1, vrr = 2 })
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "2560x0", scale = 1, vrr = 0 })
```

Then `hyprctl reload`.

**Verify.** With both monitors connected, drag a window or switch workspaces on the fast display. It should be smooth while the 60 Hz screen animates at its own rate. `hyprctl monitors -j | jq -r '.[] | "\(.name) @\(.refreshRate)"'` should show the two different rates steadily, not one of them oscillating.

Sources: <https://github.com/hyprwm/Hyprland/pull/12418> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/Hyprland/discussions/10969> · <https://github.com/hyprwm/Hyprland/issues/9029> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md>

---

## Allow tearing in games without tearing the desktop

`screen-tearing-in-games-not-enabled` · severity: **low** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Either the opposite complaints: a game feels laggy because it is vsynced and `allow_tearing` seems to do nothing, or the desktop tears randomly after every reboot and after every lock/unlock cycle on an AMD card over DP 1.4 DSC.

**Cause.** Tearing in Hyprland is opt-in per window and only takes effect when the game is fullscreen and is the *only* thing on that monitor. A notification, bar, overlay or lockscreen on the same output silently disables it. Conversely, unwanted desktop tearing on AMD DSC links is usually a modeset/driver state issue that clears when something forces a re-modeset (users report the hyprsunset restart in Omarchy's update flow doing exactly that).

**Fix.**

To enable tearing for a game (Hyprland 0.55+):

```lua
hl.config({ general = { allow_tearing = true } })
hl.window_rule({ match = { class = "cs2" }, immediate = true })
```

On Hyprland <= 0.54:

```
general { allow_tearing = true }
windowrule = immediate, class:^(cs2)$
```

The window must be fullscreen with nothing else drawn on that monitor. If the app freezes instead of tearing, your GPU driver does not support it, so turn `allow_tearing` back off.

For unwanted desktop tearing, force a re-modeset without rebooting:

```bash
hyprctl dispatch 'hl.dsp.dpms({ action = "disable" })'; sleep 2
hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'
# or on Omarchy
omarchy-restart-hyprsunset
```

And make sure tearing is not globally on: `hl.config({ general = { allow_tearing = false } })`.

**Verify.** In-game frame times stop being quantised to the refresh interval (tearing enabled), or the tear line disappears from the desktop after the re-modeset.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Advanced%20and%20Cool/Tearing.md> · <https://github.com/basecamp/omarchy/issues/5461> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Variables.md>

---

## Make the text console readable on a HiDPI laptop

`tty-console-font-tiny-on-hidpi` · severity: **low** · frequency: **common** · applies to: `arch`, `endeavouros`, `hidpi`, `laptop`, `mkinitcpio`, `omarchy`, `omarchy-4`, `tty`

**Symptom.** On a 4K or other HiDPI laptop, the text console (Ctrl+Alt+F2, or the screen you land on when Hyprland crashes or an emergency shell opens) uses microscopic text that I can barely read.

**Cause.** The kernel picks its large built-in font, `TER16x32`, for high-resolution displays by itself. Userspace then overrides it. On an install made by archinstall, which Omarchy's installer uses, `/etc/vconsole.conf` contains `FONT=default8x16`, because archinstall's default `console_font` is `default8x16`. systemd-vconsole-setup loads that 8x16 font over the kernel's choice. On Omarchy 4 the `consolefont` hook is in the `HOOKS` set by `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, and that hook reads `FONT` from `/etc/vconsole.conf` when the initramfs is built and loads it in early userspace, so the small font is applied from early boot. Checked on this 4.0.4-1 workstation.

> **Audit corrected this record.** Confirmed on this workstation: /etc/vconsole.conf has FONT=default8x16, the kernel has CONFIG_FONT_TER16x32=y, latarcyrheb-sun32 is owned by kbd 2.10.0-1, limine-mkinitcpio exists, and omarchy_hooks.conf includes consolefont. archinstall's locale.py defaults console_font to default8x16, and the Arch HiDPI page supports TER16x32 auto-selection, latarcyrheb-sun32 and the video= workaround. Three defects. The cause credits the drop-in's FILES+=(/etc/vconsole.conf) for the early-boot font, but that block exists for Plymouth's keyboard layout. /usr/lib/initcpio/install/consolefont reads FONT from /etc/vconsole.conf itself and embeds the font regardless of layout. The fix gives the video= parameter with no place to put it, and on Omarchy 4 kernel parameters go in /etc/limine-entry-tool.d/*.conf, the format omarchy-defaults.conf there uses. The danger calls a misspelt font harmless, but the consolefont install hook raises an error, mkinitcpio counts it and warns the image may not be complete. The verify step contained a placeholder 'Super+Alt+...', and loginctl here shows the Hyprland session on VTNr=1. No initramfs was rebuilt and no kernel parameter was exercised.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** The initramfs rebuild writes to the ESP on Omarchy 4. Run `df -h /boot` first, because a full ESP produces a truncated image that does not boot, and Omarchy 4 has no fallback image. A misspelt font name is not harmless at build time: the `consolefont` hook fails with `consolefont: requested font not found`, and mkinitcpio warns that the image may not be complete. Correct the name and rebuild before rebooting. If a `video=` mode leaves the console blank, delete `/etc/limine-entry-tool.d/console-mode.conf` and run `sudo limine-mkinitcpio` again.

**Fix.**

**Try a font on the current console.** Run this on the text console itself (Ctrl+Alt+F2, then log in). From a terminal inside Hyprland it has no console to change:

```bash
setfont latarcyrheb-sun32
```

`latarcyrheb-sun32` ships in `kbd`, which is always installed. For Terminus, `sudo pacman -S terminus-font` and use `ter-132b` instead.

**Make it permanent:**

```bash
sudo sed -i 's/^FONT=.*/FONT=latarcyrheb-sun32/' /etc/vconsole.conf
grep -q '^FONT=' /etc/vconsole.conf || echo 'FONT=latarcyrheb-sun32' | sudo tee -a /etc/vconsole.conf
sudo systemctl restart systemd-vconsole-setup
```

Rebuild the initramfs so early boot uses it too, and read the output for `consolefont: requested font not found` before rebooting:

- **Omarchy 4:** `sudo limine-mkinitcpio`
- **Plain Arch:** `sudo mkinitcpio -P`

**If text turns garbled when you switch to other consoles,** the Arch wiki's fix is to force the native KMS mode with a `video=` kernel parameter, using your panel's resolution, for example `video=2560x1600@60`.

- **Omarchy 4:** the kernel command line is inside the UKI and comes from `/etc/limine-entry-tool.d/*.conf`. Add a drop-in and rebuild:

```bash
echo 'KERNEL_CMDLINE[default]+=" video=2560x1600@60"' | sudo tee /etc/limine-entry-tool.d/console-mode.conf
sudo limine-mkinitcpio
```

- **Plain Arch:** add `video=2560x1600@60` to your boot loader's kernel command line, as described on the Arch wiki's Kernel parameters page.

**Verify.** `grep ^FONT /etc/vconsole.conf` prints the new font. Switch to Ctrl+Alt+F2 and the text is readable. After a reboot it is still large from early boot onwards. Ctrl+Alt+F1 returns you to the Hyprland session, which runs on tty1.

Sources: <https://wiki.archlinux.org/title/HiDPI> · <https://wiki.archlinux.org/title/Linux_console> · <https://github.com/archlinux/archinstall/blob/master/archinstall/lib/models/locale.py>

---

## Make Steam and Proton games open on your main monitor

`xwayland-games-open-on-wrong-monitor` · severity: **low** · frequency: **common** · applies to: `arch`, `desktop`, `gaming`, `hyprland`, `omarchy`, `omarchy-4`, `proton`, `steam`, `wayland`, `xwayland`

**Symptom.** Steam and Proton games open on my second monitor, or open fullscreen at the second monitor's resolution so the picture is squished or offset. After a monitor goes to sleep or is power-cycled, games start landing on the wrong screen again even though it was fixed before.

**Cause.** Wayland has no concept of a primary monitor, but games running through XWayland, which is how Proton runs them, place themselves on X's RandR primary output. Hyprland's config has no setting for it, so the primary is whichever output XWayland happened to choose. A primary set with `xrandr` is lost when that output is removed and re-added, for example when the monitor sleeps and drops its connection, which is why the problem comes back.

> **Audit corrected this record.** The cited blog post supports the cause (Proton runs through XWayland, X's RandR primary decides placement, xrandr --primary fixes it but is lost when the monitor powers off) and the udev fallback. The Hyprland events page documents monitor.layout_changed as firing on monitor add, remove, mode change and config reload, and Omarchy's /usr/share/omarchy/default/hypr/helpers.lua defines o.exec_on_start via hl.on("hyprland.start") calling hl.exec_cmd, so the Lua snippet uses real API. Hyprland's config-options page has no xwayland option for a primary output and src/xwayland in the Hyprland repo has no RandR primary handling, so 'no setting for it' holds. The Arch steam package depends on xorg-xrandr, as the record says. Two defects: the symptom's 'Dota 2 renders squished' appears in no cited source and no omacom/omarchy issue, so it is unsupported precision and is dropped, and the cited Hyprland xwayland.md page covers HiDPI scaling and the abstract socket only and says nothing about a primary monitor, so it does not support the record. The fix was not exercised.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

**Find the connector name and test:**

```bash
hyprctl monitors | grep ^Monitor
pacman -Q xorg-xrandr || sudo pacman -S --needed xorg-xrandr
xrandr --output DP-1 --primary
xrandr --listmonitors              # the primary carries a '*'
```

`xorg-xrandr` usually comes in as a Steam dependency.

**Make it stick (Omarchy 4, Hyprland Lua).** Add this to `~/.config/hypr/autostart.lua`. The second block re-applies the setting whenever the monitor layout changes, which covers sleep and hotplug:

```lua
o.exec_on_start("xrandr --output DP-1 --primary")
hl.on("monitor.layout_changed", function()
  hl.exec_cmd("sleep 2; xrandr --output DP-1 --primary")
end)
```

**Hyprland before 0.55 (hyprlang config):**

```
exec-once = xrandr --output DP-1 --primary
```

That version has no layout hook. Re-run the command after a monitor wakes, or use a udev rule as in the cited blog post.

**Verify.** `xrandr --listmonitors` shows `*` on your main monitor after a login and after the monitors wake from sleep. Launch a fullscreen game and check that it opens there at the correct resolution.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/events.md> · <https://kyouha.today/blog/rando/xwayland-game-primary-monitor/> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/config-options.md> · <https://archlinux.org/packages/multilib/x86_64/steam/>

---

## Clear the cached device when Studio Display brightness stops working after a replug

`apple-display-brightness-dead-after-replug` · severity: **low** · frequency: **occasional** · applies to: `apple`, `desktop`, `hyprland`, `laptop`, `omarchy`, `thunderbolt`, `wayland`

**Symptom.** Brightness keys on an Apple Studio Display worked, then after replugging the Thunderbolt cable or waking a dock they silently stop. The OSD pops up empty, the brightness never changes, and nothing reports an error. A reboot makes it work again.

**Cause.** `omarchy-brightness-display-apple` caches the display's HID node in `$XDG_RUNTIME_DIR/omarchy-brightness-display-apple.device`. On 4.0.4 it only re-checks that the cached path is still a hiddev character device. After a replug the display's USB interfaces renumber, and the old node can be taken by another of the display's own HID interfaces, so it still passes that check. `asdcontrol` then prints `This device is not a USB monitor!` and exits 0, so the script's retry, which only runs on a non-zero exit, never fires, and the OSD read that follows finds no level. Reported in omarchy pull request 7336 (open). Its author hit it on a Studio Display after a Thunderbolt replug, with key presses still driving `/dev/usb/hiddev3` after the display had moved to `hiddev2`. The reviewer confirmed the exit-0 path in asdcontrol's source and reproduced the stuck cache with a stub on a test VM.

> **Audit corrected this record.** Read /usr/share/omarchy/bin/omarchy-brightness-display-apple on 4.0.4-1: the cache path, the hiddev character-device check and the retry that fires only on a non-zero `asdcontrol` exit all match the cause. Read PR 7336 (open) and its review. The bot reviewer confirmed the 'This device is not a USB monitor!' exit-0 path in asdcontrol v0.6.0 source and with a stub on a VM. The cause says the mechanism was not confirmed on real hardware, but the PR author hit it on a real Studio Display after a Thunderbolt replug, with the journal showing writes to hiddev3 while the display had moved to hiddev2. That sentence is corrected. The fix's key binding is wrong: SUPER + CTRL + ALT + B is an Omarchy default ('Show battery remaining', /usr/share/omarchy/default/hypr/bindings/utilities.lua:93), so the record tells the reader to check the combination and then hands them a taken one. Replaced with SUPER + CTRL + ALT + A, which no default binds. `o.bind` wraps the string in `hl.dsp.exec_cmd`, so `$XDG_RUNTIME_DIR` is expanded by the shell. Not exercised on hardware.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Delete the cache and let the script detect the display again:

```bash
cat "$XDG_RUNTIME_DIR/omarchy-brightness-display-apple.device"     # the stale node
rm -f "$XDG_RUNTIME_DIR/omarchy-brightness-display-apple.device"
omarchy-brightness-display-apple +5%
```

The cache lives under `$XDG_RUNTIME_DIR`, so logging out and back in also clears it. If it happens on every replug, bind the reset to a key in `~/.config/hypr/bindings.lua`. SUPER + CTRL + ALT + A is free on a stock Omarchy 4.0.4 (SUPER + CTRL + ALT + B is the battery notification), but check your own set with `omarchy menu keybindings --print`:

```lua
o.bind("SUPER + CTRL + ALT + A", "Re-detect Apple display", 'rm -f "$XDG_RUNTIME_DIR/omarchy-brightness-display-apple.device"')
```

If brightness still fails after the reset, the cause is one of the gates in `apple-studio-display-brightness-keys-do-nothing`.

**Verify.** The brightness keys change the level again, the OSD shows a percentage, and the cache file holds a new node path.

Sources: <https://github.com/omacom/omarchy/pull/7336> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display-apple> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/bindings/utilities.lua>

---

## Get brightness keys working on an Apple Studio Display or Pro Display XDR

`apple-studio-display-brightness-keys-do-nothing` · severity: **low** · frequency: **occasional** · applies to: `apple`, `desktop`, `hyprland`, `laptop`, `omarchy`, `thunderbolt`, `wayland`

**Symptom.** Apple Studio Display or Pro Display XDR on Omarchy 4. The brightness keys do nothing, or the OSD appears with no level. `omarchy-brightness-display` prints nothing and exits 1, or prints `No Apple Display HID device found`. Running `sudo asdcontrol` by hand in a terminal works.

**Cause.** Omarchy 4 sends brightness for these displays through `omarchy-brightness-display-apple`, which runs `sudo asdcontrol` against the display's USB HID node. Three things must all hold, and each fails silently from a keybinding.

1. **Routing.** `omarchy-brightness-display` only takes the Apple path when `omarchy-hyprland-monitor-focused-apple` matches, which needs Hyprland to report make `Apple Computer Inc` and a model matching `StudioDisplay|ProDisplayXDR|Studio XDR` on the focused monitor. Anything else falls through to DDC/CI, which these displays do not answer.

2. **The sudo grant.** Omarchy stopped shipping its own `/etc/sudoers.d/omarchy-asdcontrol` in commit df819a6f (2026-08-30, the 4.0.2 security changes). The grant now comes from the `asdcontrol` package, 1:0.6.0-2, as `/etc/sudoers.d/50-asdcontrol`: NOPASSWD for `%wheel` only, and only for `--detect <hiddev>...`, `<hiddev>` and `<hiddev> -- [+-]N%`. With an older package, or a user outside `wheel`, sudo asks for a password a keybinding cannot type.

3. **The HID node.** `/dev/usb/hiddev*` exists only while the display's USB side is connected, which on these displays rides the same Thunderbolt cable as the picture.

> **Audit corrected this record.** Read /usr/share/omarchy/bin/omarchy-brightness-display, -display-apple and omarchy-hyprland-monitor-focused-apple on this machine: routing, the make `Apple Computer Inc`, the model regex, the `sudo asdcontrol` call shapes and the `No Apple Display HID device found` message all match. Commit df819a6f (2026-08-30) deletes etc/sudoers.d/omarchy-asdcontrol, and the tag trees confirm v4.0.1 has the file and v4.0.2 does not. The omarchy-pkgs asdcontrol.sudoers is a %wheel NOPASSWD grant restricted to the three hiddev shapes, the PKGBUILD is 1:0.6.0-2, and `pacman -Ql asdcontrol` here shows /etc/sudoers.d/50-asdcontrol (unreadable without root, not opened). Issue 8532 supports the scoping. The record does not add security detail beyond it. Default bindings in /usr/share/omarchy/default/hypr/bindings/media.lua match the `o.bind` form used. One defect: the not-routed fallback unbinds the plain brightness keys and points them at the Apple script for every monitor, which on a laptop silently breaks the built-in panel's brightness keys. The fix now uses a separate CTRL combination on laptops, which no Omarchy default binds. Issue 2278 is an Omarchy 3.0.2 report about `/usr/local/bin/asdcontrol` and is historical only. No Apple display was available, so nothing was exercised.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Adding a user to `wheel` gives that account full sudo, far more than brightness control. Only do it for an account that should administer the machine.

**Fix.**

**1. Check each gate:**

```bash
hyprctl monitors -j | jq -r '.[] | "\(.name)  make=\(.make)  model=\(.model)  focused=\(.focused)"'
omarchy-hyprland-monitor-focused-apple && echo "routed to asdcontrol" || echo "NOT routed to asdcontrol"
pacman -Q asdcontrol                         # want 1:0.6.0-2 or newer
id -nG | tr ' ' '\n' | grep -x wheel          # the package grant covers %wheel only
ls /dev/usb/hiddev* /dev/hiddev* 2>/dev/null
sudo -n asdcontrol --detect /dev/usb/hiddev*; echo "exit $?"   # must not say a password is required
```

**2. Fix the gate that failed.**

- `asdcontrol` missing or older than 1:0.6.0-2: run `omarchy update -y`.
- Not in `wheel`: the package grants nothing to other users. Run brightness from an account in `wheel`, or add yours with `sudo gpasswd -a "$USER" wheel` and log out and back in (read the danger note).
- No hiddev node: connect the display's Thunderbolt cable to a port that also carries USB, and check the display's camera or speakers appear in `lsusb`.
- Not routed (Hyprland reports a different make or model): bind keys to the Apple script directly in `~/.config/hypr/bindings.lua`, and report the model string upstream.

On a laptop, keep the plain brightness keys for the built-in panel and give the Apple display its own combination:

```lua
o.bind("CTRL + XF86MonBrightnessUp", "Apple display brightness up", "omarchy-brightness-display-apple +5%", { locked = true, repeating = true })
o.bind("CTRL + XF86MonBrightnessDown", "Apple display brightness down", "omarchy-brightness-display-apple 5%-", { locked = true, repeating = true })
```

On a desktop where the Apple display is the only screen, replacing the plain keys is fine:

```lua
hl.unbind("XF86MonBrightnessUp")
hl.unbind("XF86MonBrightnessDown")
o.bind("XF86MonBrightnessUp", "Brightness up", "omarchy-brightness-display-apple +5%", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Brightness down", "omarchy-brightness-display-apple 5%-", { locked = true, repeating = true })
```

Do not write a broader sudoers rule for `asdcontrol`, and do not run `sudo omarchy-brightness-display-apple`: the script calls sudo itself, and sudo strips `OMARCHY_PATH`.

**Plain Arch:** the Omarchy scripts do not exist there. Omarchy packages asdcontrol from https://github.com/omakasui/asdcontrol, and the same calls work by hand: `sudo asdcontrol --detect /dev/usb/hiddev*` to find the node, then `sudo asdcontrol /dev/usb/hiddevN -- +5%`.

**Verify.** With the Apple display focused, `omarchy-brightness-display` prints a percentage, the keys change the brightness, and the OSD shows the new level.

Sources: <https://github.com/omacom/omarchy/issues/8532> · <https://github.com/omacom/omarchy/commit/df819a6f> · <https://github.com/omacom-io/omarchy-pkgs/blob/master/pkgbuilds/asdcontrol/asdcontrol.sudoers> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display-apple> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-focused-apple> · <https://github.com/omacom/omarchy/issues/2278> · <https://github.com/omacom-io/omarchy-pkgs/blob/master/pkgbuilds/asdcontrol/PKGBUILD>

---

## Fix an external monitor that ignores the brightness slider while the OSD says it changed

`ddc-brightness-slider-moves-monitor-unchanged` · severity: **low** · frequency: **occasional** · applies to: `amd`, `ddcutil`, `desktop`, `hyprland`, `laptop`, `omarchy`, `omarchy-4`

**Symptom.** The Display panel finds my external monitor and shows a brightness slider. Dragging it, or pressing the brightness keys with that monitor focused, moves the OSD, but the screen's brightness never changes. The helper even claims success:

```
$ omarchy-brightness-display --no-osd --monitor DP-1 70%
$ echo $?
0
$ ddcutil --bus 9 getvcp 10 --brief
VCP 10 C 100 100
```

Reported with an LG UltraGear evo 27GM950B-B and an ASUS ProArt PA32QCV, both on amdgpu.

**Cause.** `omarchy-brightness-display-ddc` writes brightness on ddcutil's fast path, `ddcutil --bus "$bus" --skip-ddc-checks --noverify setvcp 10 "$raw_target"`. Two kinds of monitor fail behind that one symptom. Some, the LG in the report, accept the fast-path write with no error but ignore it, while a normal `ddcutil --bus 9 setvcp 10 70` with checks enabled works. Others, the ASUS, reject every write on every path with `Verification failed for feature 10` / `DDCRC_VERIFY`, which points at a firmware lock. In both cases the MCCS Set VCP command carries no acknowledgement and `--noverify` turns off the read-back, so the helper exits 0 and `omarchy-brightness-display` hands the requested value to the OSD. The proposed fix, PR #9876, is open and depends on ddcutil 3.0.1 or later. Arch extra has ddcutil 3.0.2, but the Omarchy stable mirror still serves 2.2.7-1 as of 2026-10-04, and the 4.0.4-1 helper still uses the fast path.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**Find the monitor's bus and test both write paths:**

```bash
ddcutil detect --brief
# then, with the bus number it printed:
ddcutil --bus 9 --skip-ddc-checks --noverify setvcp 10 70
ddcutil --bus 9 getvcp 10 --brief      # unchanged means the fast path is ignored
ddcutil --bus 9 setvcp 10 70
ddcutil --bus 9 getvcp 10 --brief      # changed means the full-check path works
```

**If the full-check write works**, add your own bindings that use it. Put them in `~/.config/hypr/bindings.lua`, on a modifier so the stock keys keep driving the laptop panel. ddcutil takes a relative change when `+` or `-` stands alone between spaces:

```lua
o.bind("CTRL + XF86MonBrightnessUp", "External brightness up", "ddcutil --bus 9 setvcp 10 + 10", { locked = true })
o.bind("CTRL + XF86MonBrightnessDown", "External brightness down", "ddcutil --bus 9 setvcp 10 - 10", { locked = true })
```

Saving the file reloads Hyprland. I2C bus numbers can change after a kernel update or a different port, so re-run `ddcutil detect --brief` if the binding stops working.

**If both writes fail with `DDCRC_VERIFY`**, the monitor refuses DDC/CI brightness writes and only its own OSD buttons will change it. Check that DDC/CI is turned on in the monitor's menu. One reporter's panel was in HDR mode (`cm = "hdredid"`), and whether HDR causes the refusal was not tested.

**Verify.** Press the new binding and run `ddcutil --bus 9 getvcp 10 --brief`. The current value moves by 10 each time and the screen visibly changes.

Sources: <https://github.com/omacom/omarchy/issues/8931> · <https://github.com/omacom/omarchy/pull/9876> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display-ddc> · <https://archlinux.org/packages/extra/x86_64/ddcutil/>

---

## Bring night light back after it switches itself off mid-session

`night-light-off-after-hyprsunset-dies` · severity: **low** · frequency: **occasional** · applies to: `desktop`, `hyprland`, `hyprsunset`, `laptop`, `omarchy`, `omarchy-4`

**Symptom.** I turned night light on in the evening, and some time later the screen is cold and blue again although I never turned it off. `omarchy-toggle-nightlight --status` prints `{"enabled":false,"temperature":null}`, and `hyprctl hyprsunset temperature` fails with `Couldn't connect to /run/user/1000/hypr/<signature>/.hyprsunset.sock`. It often follows a monitor flapping, when the journal shows `XWAYLAND: wl_registry#2: error 0: global wl_output (73) is unavailable`. With a scheduled sunset profile, a hyprsunset restart at night leaves the screen neutral until the next sunset.

**Cause.** Omarchy starts hyprsunset as a bare background process, `setsid uwsm-app -- hyprsunset &`, from `omarchy-toggle-nightlight` and from the shell's night light service, with no restart policy. If it dies, for example when an output disappears while it is binding to it, nothing restarts it for the rest of the session. A freshly started hyprsunset applies its default (about 6000K, or the `identity = true` profile in Omarchy's `hyprsunset.conf`), and hyprsunset profiles fire only at their clock time, not the most recent one that has passed. So even a restart leaves the screen neutral until the next scheduled change. Both issues are open against 4.0.4-1.

> **Audit corrected this record.** Issues #8161 and #12334 are open and support the cause: both launch paths (bin/omarchy-toggle-nightlight and the shell's nightlight Service.qml) start hyprsunset with setsid uwsm-app and pgrep -x, unchanged on quattro today, and a fresh hyprsunset comes back neutral. /usr/lib/systemd/user/hyprsunset.service from hyprsunset 0.4.0-3 has Restart=on-failure and PartOf=graphical-session.target as stated. Two defects. The verify step uses pkill -x hyprsunset to prove the restart, but pkill sends SIGTERM, which systemd counts as a clean exit, so Restart=on-failure does not restart it and a correctly working setup fails the check. Second, omarchy restart hyprsunset and omarchy refresh hyprsunset both run omarchy-restart-app, which is pkill -x followed by a bare setsid uwsm-app launch, so either one silently replaces the supervised instance with an unsupervised one until the next login, which the fix does not warn about. The fix also never stops an instance the toggle already started before enabling the unit. Separately, with a running but neutral hyprsunset the toggle picks its target from the reported temperature, so whether one press warms the screen was not confirmed. The corrected fix uses hyprctl hyprsunset temperature 4000, which sets it directly. Nothing was started, killed or enabled on this machine.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**Get the warmth back now:** press Super+Ctrl+N, or run:

```bash
omarchy toggle nightlight
```

With no hyprsunset running, the toggle starts one and retries until 4000K sticks.

**Have it restart on its own.** The `hyprsunset` package ships a supervised user unit, `/usr/lib/systemd/user/hyprsunset.service`, with `Restart=on-failure` and `PartOf=graphical-session.target`. Stop any instance the toggle already started, then enable the unit:

```bash
pkill -x hyprsunset
systemctl --user enable --now hyprsunset.service
```

Omarchy's toggle finds the running process with `pgrep` and drives it through `hyprctl hyprsunset`, so the keybinding keeps working. If you added `o.launch_on_start("hyprsunset")` to `~/.config/hypr/autostart.lua` for a schedule, remove that line, or you will run two instances.

Once the unit owns hyprsunset, restart it with `systemctl --user restart hyprsunset`. Do not use `omarchy restart hyprsunset` or `omarchy refresh hyprsunset`: both kill it with `pkill` and start a bare copy outside the unit, and systemd treats that kill as a clean exit, so supervision is gone until you log in again.

A restarted hyprsunset still comes back neutral at night. After a crash, set the warmth directly:

```bash
hyprctl hyprsunset temperature 4000
```

**Verify.** `systemctl --user is-active hyprsunset` prints `active`. Simulate a crash with `systemctl --user kill --signal=SIGKILL hyprsunset.service`, wait a few seconds, and `systemctl --user is-active hyprsunset` prints `active` again with a new PID from `pgrep -x hyprsunset`. Do not test with `pkill -x hyprsunset`: SIGTERM is a clean exit and `Restart=on-failure` correctly leaves it stopped. `hyprctl hyprsunset temperature` answers instead of failing to connect.

Sources: <https://github.com/omacom/omarchy/issues/8161> · <https://github.com/omacom/omarchy/issues/12334> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-toggle-nightlight> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/services/nightlight/Service.qml>

---

## Stop the mouse cursor turning fluorescent blue with night light on NVIDIA

`nightlight-cursor-blue-outline-nvidia` · severity: **low** · frequency: **occasional** · applies to: `desktop`, `hyprland`, `hyprsunset`, `laptop`, `nvidia`, `omarchy`, `omarchy-4`

**Symptom.** On an NVIDIA card, as soon as night light is on (Super+Ctrl+N), the mouse cursor's outline turns bright fluorescent blue over every window. With night light off the cursor looks normal. Reported with an RTX 3060 Ti on nvidia-open-dkms 610.57.04, Omarchy 4.0.4-1.

**Cause.** hyprsunset tints the screen with a colour transform matrix (CTM). On NVIDIA the hardware cursor plane does not receive that CTM, so the screen is warmed while the cursor keeps its original colours. Against the warmed background its edge reads as blue. The same driver behaviour has been reported on KDE Plasma 6, so it is at least partly in the NVIDIA driver and not specific to Hyprland. The issue is open.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**Use a software cursor (Omarchy 4, Hyprland Lua).** Add this to `~/.config/hypr/looknfeel.lua`:

```lua
hl.config({ cursor = { no_hardware_cursors = 1 } })
```

Saving reloads Hyprland. `1` means never use hardware cursors. The default `2` turns them off only while a window is tearing.

**Hyprland before 0.55 (hyprlang):**

```
cursor {
    no_hardware_cursors = 1
}
```

The reporter's alternative was to replace hyprsunset with a gamma-LUT client, `wl-gammarelay-rs`, because a gamma table does reach the hardware cursor. That means leaving Omarchy's night light toggle.

**Verify.** `hyprctl getoption cursor:no_hardware_cursors` reports `1`. Turn night light on, and the cursor is tinted like the rest of the screen, with no blue edge.

Sources: <https://github.com/omacom/omarchy/issues/13912> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/config-options.md>

---

## TV over HDMI crops the edges of the desktop (overscan) and Wayland has no underscan setting

`tv-overscan-edges-cut-off-over-hdmi` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Hooked the machine to a TV over HDMI and the top bar is half off-screen, the bottom of windows is cut away, and roughly 3-5% of every edge is missing. The TV is at the correct 1920x1080, `hyprctl monitors` looks right, and everything is fine on a normal monitor. There is no underscan or overscan slider anywhere in Hyprland or in the Omarchy display panel.

**Cause.** The TV is applying legacy CRT overscan: it crops the incoming frame and zooms the remainder to fill the panel. Nothing on the computer side is wrong. Under X11 you could compensate with the display's border/underscan property, but there is no Wayland protocol for output margins: hyprwm/Hyprland issue #277 ("Underscan/Overscan Support") is closed as *not planned*, and the same gap is documented for other compositors (labwc #2049: *"I have yet to find a way of doing it under Wayland"*, and the only workaround there is shrinking the panel and background, which still lets the pointer leave the visible area).

**Fix.**

**1. Turn overscan off on the TV. This is the actual fix.** The setting is in the TV's picture menu and is named differently per brand:

- Samsung: *Picture → Picture Size Settings → Picture Size → **Screen Fit*** (and set *Fit to Screen* on)
- LG: *Picture → Aspect Ratio → **Just Scan*** (or *Original*)
- Sony: *Screen → Display Area → **Full Pixel***
- Panasonic / Philips / TCL: *Aspect → **1:1 Pixel Mapping*** / *Unscaled* / *Dot by Dot*

If the option is greyed out, rename the HDMI input to **PC** (Samsung/LG both unlock 1:1 mapping and 4:4:4 chroma only on an input labelled PC). On many sets this single change fixes it permanently.

**2. If the TV genuinely has no such setting, keep your UI out of the cropped strip.** Hyprland's `reserved_area` field reserves pixels that tiled windows will not occupy. It does not shrink the output, but it stops the bar and window content from landing in the cut-off band. In `~/.config/hypr/monitors.lua`:

```lua
-- 1920x1080 TV cropping ~3% per side ≈ 30px vertical, 55px horizontal
hl.monitor({
  output        = "HDMI-A-1",
  mode          = "1920x1080@60",
  position      = "0x0",
  scale         = 1,
  reserved_area = { top = 30, bottom = 30, left = 55, right = 55 },
})
```

A single integer applies to all four sides:

```lua
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "0x0", scale = 1, reserved_area = 40 })
```

```bash
hyprctl reload
```

Measure the real crop first: put a window at each edge and count the missing pixels, or run a
fullscreen image with a 1px border and see how much is gone. Note the wiki's constraint:
*"This stacks on top of the calculated reserved area (e.g. bars), but you may only use one of
these rules per monitor in the config."* So one `reserved_area` per monitor, and your bar's own
reservation is added on top of it.

**3. Long shot, only if the above fails.** The kernel's modedb accepts margin options on the video= command line, documented on Arch's KMS page for exactly this case (*"typically to deal with overscan on TVs"*):

```
video=HDMI-A-1:1920x1080@60,margin_top=24,margin_bottom=24,margin_left=40,margin_right=40
```

Reports of this taking effect under a Wayland compositor are thin, so treat it as something to
try, not something to rely on, and set the TV correctly if you possibly can.

**Do not** "fix" this by setting a smaller custom mode (e.g. 1776x1000 into a 1080p TV). The TV
will upscale *and* still crop, giving you a soft picture with the edges still missing.

**Verify.** Open a terminal and maximise it: all four borders should be visible. `hyprctl monitors -j | jq -r '.[] | "\(.name) \(.reserved)"'` shows the reserved band on the TV output.

Sources: <https://github.com/hyprwm/Hyprland/issues/277> · <https://github.com/labwc/labwc/issues/2049> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md> · <https://wiki.archlinux.org/rest.php/v1/page/Kernel_mode_setting> · <https://wiki.hypr.land/Configuring/Basics/Monitors/>

---

## Make brightness keys work on an all-in-one whose built-in screen is DP-1

`aio-builtin-panel-on-dp-fixed-brightness` · severity: **low** · frequency: **rare** · applies to: `apple`, `desktop`, `hyprland`, `imac`, `intel`, `nouveau`, `omarchy`, `omarchy-4`

**Symptom.** On an iMac (or another all-in-one) running Omarchy, the brightness keys do nothing and the Display panel shows `FIXED BRIGHTNESS` with no slider:

```
$ omarchy-brightness-display; echo "exit=$?"
exit=1
$ hyprctl monitors -j | jq -r '.[].name'
DP-1
```

The backlight itself is fine: `brightnessctl -d acpi_video0 set 50%` changes the screen at once.

**Cause.** `omarchy-brightness-display` chooses between the kernel backlight and DDC/CI from the connector name alone. `monitor_is_internal` matches only `^(eDP|LVDS|DSI)-`, and everything else is treated as an external monitor and sent to `omarchy-brightness-display-ddc`. All-in-ones wire the built-in panel to a DisplayPort connector, so it is named `DP-1` or `DP-3`. A built-in panel does not answer DDC/CI (`ddcutil detect` reports `I2C slave address x37 is unresponsive`), so the script exits 1 even though `/sys/class/backlight/acpi_video0` exists. Reproduced on an iMac13,1 with nouveau and on an Iris Pro 5200 iMac with i915. The regex is unchanged in 4.0.4-1 and on `quattro` as of 2026-10-04, and the issue is open.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**Confirm the routing is the problem:**

```bash
ls /sys/class/backlight/
hyprctl monitors -j | jq -r '.[].name'
ddcutil detect
brightnessctl -d acpi_video0 set 50%
```

A backlight device that works, a non-eDP name and no DDC/CI means this record applies.

**Rebind the keys to the backlight directly (Omarchy 4)**, in `~/.config/hypr/bindings.lua`:

```lua
hl.unbind("XF86MonBrightnessUp")
hl.unbind("XF86MonBrightnessDown")
o.bind("XF86MonBrightnessUp", "Brightness up", "brightnessctl -d acpi_video0 set +5%", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Brightness down", "brightnessctl -d acpi_video0 set 5%-", { locked = true, repeating = true })
```

The Display panel keeps showing `FIXED BRIGHTNESS` until upstream changes the routing. Only the keys are fixed here.

**Verify.** Press the brightness keys, then run `cat /sys/class/backlight/acpi_video0/brightness`. The value changes and so does the screen.

Sources: <https://github.com/omacom/omarchy/issues/8015> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-brightness-display>

---

## Fix night light doing nothing when another user is also logged in

`nightlight-toggle-noop-with-second-user-session` · severity: **low** · frequency: **rare** · applies to: `hyprland`, `hyprsunset`, `multi-user`, `omarchy`, `omarchy-4`

**Symptom.** Super+Ctrl+N (`omarchy toggle nightlight`) does nothing. The screen temperature never changes and the toggle exits silently. Another user on the same machine has a Hyprland session open with night light on. `hyprctl hyprsunset temperature` fails with:

```
Couldn't connect to /run/user/1001/hypr/<signature>/.hyprsunset.sock. (3)
```

**Cause.** `omarchy-toggle-nightlight` decides whether to start hyprsunset with `pgrep -x hyprsunset`, which matches processes of every user. It finds the other user's hyprsunset, never starts one in your session, and then `hyprctl hyprsunset` has no socket in your Hyprland instance to talk to. The fix, PR #14038, restricts the check to `pgrep -x -u "$UID"`, and it was still open on 2026-10-04. The unpatched check is in 4.0.4-1 and on `quattro`.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

**Start hyprsunset for your own session, then toggle:**

```bash
pgrep -u "$USER" -x hyprsunset || setsid uwsm-app -- hyprsunset >/dev/null 2>&1 &
omarchy toggle nightlight
```

**To make it automatic,** run hyprsunset under your own user manager. It is scoped to your session, so the other user's process no longer matters:

```bash
systemctl --user enable --now hyprsunset.service
```

**Verify.** `pgrep -u "$USER" -x hyprsunset` prints a PID, `hyprctl hyprsunset temperature` answers, and Super+Ctrl+N visibly warms the screen.

Sources: <https://github.com/omacom/omarchy/issues/14037> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-toggle-nightlight>

---
