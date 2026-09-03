# Displays & monitors

34 problems. Sorted by severity, then by how often users hit it.

## Stop closing the lid from killing every GUI app at once

`clamshell-lid-close-kills-all-gui-clients` · severity: **critical** · frequency: **common** · applies to: `hyprland`, `intel`, `laptop`, `omarchy`, `wayland`

**Symptom.** Plug in HDMI, close the laptop lid a couple of seconds later, and every GUI app dies at once — terminals, Nautilus, Brave, the bar, portals, fcitx5, XWayland. Hyprland itself stays up. Journal shows `wl_registry#2: error 0: global wl_output (79) is unavailable`, `The Wayland connection experienced a fatal error: Protocol error` and `XWAYLAND: (EE) failed to dispatch Wayland events: Protocol error`. Afterwards `xprop -root` hangs and X11 apps will not start until you log out.

**Cause.** A Hyprland 0.56.2 registry-bind race: the `wl_output` global is destroyed while clients are still binding it, and every client that was mid-bind gets a fatal protocol error. Omarchy's clamshell helper is what fires that path on a stock laptop — on `monitoradded` it runs `hyprctl reload` (with retries at 1s/3s/7s), and on lid close it writes `hl.monitor({ output = "eDP-1", disabled = true })` into a toggle file that is loaded as config, then reloads again. A specific-output disable of the panel is what turns 'one client dies' into a whole-session wipe.

> **Audit corrected this record.** The diagnosis is solid — basecamp/omarchy#7853 exists with a matching title, and quattro's bin/omarchy-hyprland-monitor-clamshell does exactly what is described (disable_internal writes `hl.monitor({ output = "eDP-1", disabled = true })` into the toggle file then reloads), while bin/omarchy-hyprland-monitor-watch retries `sync_clamshell` at 1s/3s/7s after monitoradded. The o.bind signature and `{ locked = true }` option are correct, `omarchy-brightness-display` really does accept `off`/`on`, and the toggle paths and `uwsm stop` are right. But the replacement bind has three real defects. (a) Per Omarchy's own config/hypr/bindings.lua, an existing default must be unbound first — `o.bind` on a key the defaults already claim does not reliably replace it. (b) The stock `switch:on:Lid Switch` bind runs `omarchy-system-lid-close`, which locks the session when the lid closes with no external monitor attached; silently replacing it means the laptop no longer locks on lid close. (c) `omarchy-brightness-display off` acts on the *focused* monitor, which in a docked lid-close is usually the external one — it will blank the wrong screen unless you pass `--monitor`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Rebinding the lid switch means the laptop panel is no longer removed from the layout when you close the lid — windows stay on an output you cannot see. Check with `hyprctl monitors` before assuming a workspace is lost.

**Fix.**

Until the compositor fix lands, stop Omarchy from destroying the internal `wl_output` on lid close. Unbind the defaults first, then point the lid switch at a backlight blank of the *internal* panel — and keep the lock, which the stock `omarchy-system-lid-close` provides and a bare backlight bind would silently drop. In `~/.config/hypr/bindings.lua`:

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

Operationally: plug the external display in *first*, wait for it to settle, and only then close the lid. If the session is already wiped, XWayland is not respawned — log out with `uwsm stop` and log back in.

**Verify.** Plug in HDMI, wait, close the lid: `hyprctl clients | wc -l` stays roughly the same and `journalctl -b -g 'wl_output.*unavailable'` returns nothing.

Sources: <https://github.com/basecamp/omarchy/issues/7853> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/bindings/utilities.lua> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-clamshell>

---

## Fix Hyprland hanging at startup from a rule on a disconnected port

`explicit-rule-on-disconnected-connector-freezes` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`, `wayland`

**Symptom.** Hyprland hangs completely at startup — black or frozen screen, bar never draws, mouse may still move — on a machine where you wrote a monitor rule for a port that currently has nothing plugged into it (very common on Apple Silicon/Asahi, where `DP-1` is always exposed).

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

**Symptom.** On a hybrid Intel/AMD + NVIDIA laptop, the HDMI or USB-C port (which is wired to the dGPU) gives 'No Signal' on the external monitor. Hyprland runs fine on the internal panel; `hyprctl monitors` never lists the external one. Or the external comes up but is unusably laggy.

**Cause.** On many laptops the external ports are physically wired to the NVIDIA GPU. If `nvidia_drm.modeset` is off, or if aquamarine picked the iGPU as the only DRM device, the compositor never drives those connectors. NVIDIA also lacks features needed for good multi-GPU buffer sharing.

> **Audit corrected this record.** Steps 1, 2 and 4 are accurate and match the hyprland-wiki Nvidia page (modeset must read Y; options nvidia_drm modeset=1; MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm) plus sudo mkinitcpio -P; the page also flags that early KMS can break hibernation resume, which the record omits here). The uwsm file paths are correct — uwsm(1) documents uwsm/env-${compositor} and uwsm/env.d/*. Two problems in step 3. First, `AQ_FORCE_LINEAR_BLIT=0` is undocumented and its effect is the opposite of what the framing implies: in aquamarine's src/allocator/GBM.cpp the flag reads `!envExplicitlyDisabled("AQ_FORCE_LINEAR_BLIT")`, i.e. it is ON by default, and setting it to 0 makes aquamarine try to allocate a LINEAR-modifier buffer for cross-GPU sharing — which the adjacent source comment says 'Nvidia doesn't support', so on the exact hardware this record targets it is more likely to hurt than help. Second, the hyprland-wiki Multi-GPU page explicitly warns against using /dev/dri/cardN paths at all ('Do not use the card1 symlink... It is dynamically assigned at boot and is subject to frequent change'), and gives a udev-symlink recipe instead.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `mkinitcpio -P` regenerates every initramfs. Run it only after a fully completed `pacman -Syu` — doing it mid partial-upgrade, or with a failed nvidia-dkms build, produces an initramfs missing the module and a black screen at boot. Keep the fallback boot entry.

**Fix.**

1. Confirm DRM modesetting is on — this is the single most common cause:

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

then `sudo mkinitcpio -P` and reboot. Note that early KMS can stop resume-from-hibernation working; if that happens, remove these entries again. On Intel hybrids, put `i915` first in the list.

3. If the external is detected but laggy or broken, tell aquamarine which GPU to use, NVIDIA node first. Do not use raw `/dev/dri/cardN` paths — those numbers are reassigned at boot. Create a stable symlink instead:

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

Add the iGPU as a second `:`-separated entry if the internal panel hangs off it. Log out and back in (`uwsm stop`) for this to take effect. Do not set `AQ_FORCE_LINEAR_BLIT=0` here — it makes aquamarine attempt LINEAR-modifier buffers that NVIDIA does not support.

4. If your BIOS offers it, switching from Hybrid to Discrete graphics avoids the problem entirely (remove `optimus-manager` first — disabling the service is not enough).

**Verify.** `hyprctl monitors` lists the external output with a real mode, and `cat /sys/module/nvidia_drm/parameters/modeset` returns `Y`.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Nvidia/_index.md> · <https://wiki.archlinux.org/title/Hyprland>

---

## Get DisplayLink dock monitors redetected after a replug

`displaylink-dock-monitors-not-redetected` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `dock`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Boot with the DisplayLink dock attached and all screens work. Unplug the dock, plug it back in, and `hyprctl monitors` shows only the laptop display. The kernel is happy — `evdi: [I] (card3) Connector state: connected` and `/dev/dri/card2..card5` all exist — but Hyprland ignores them. `hyprctl reload`, `hyprctl dispatch dpms off/on` and explicit `desc:` monitor rules all do nothing.

**Cause.** Hyprland/aquamarine enumerate DRM devices once at startup and do not rescan for DRM *devices* (as opposed to connectors) that appear at runtime. When a DisplayLink dock is replugged, evdi creates brand-new card nodes; Hyprland never opens them — `ls -la /proc/$(pgrep Hyprland)/fd | grep -i evdi` is empty.

> **Audit corrected this record.** The problem and root cause are well sourced — hyprwm/Hyprland#14538 ('DRM devices from evdi (DisplayLink) not re-detected after dock reconnect without full compositor restart') and #7292 both exist, and `uwsm stop` is the documented Arch/Omarchy logout. But two of the diagnostic/fix commands are simply wrong. The AUR `displaylink` package installs `/usr/lib/systemd/system/displaylink.service` — there is no `displaylink-driver.service`, so both `systemctl status displaylink-driver.service` and `sudo systemctl enable --now displaylink-driver.service` fail outright (that unit name is the Ubuntu vendor installer's, not Arch's). Separately, `ls -la /proc/$(pgrep -x Hyprland)/fd | grep -i evdi` can never match: those fds are symlinks to /dev/dri/cardN, and the string 'evdi' appears nowhere in the listing, so the check reports the bug for everyone including healthy systems.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

There is no runtime fix in the compositor today. Practical options:

1. Restart the session with the dock already attached:

```bash
uwsm stop        # Omarchy / Arch with uwsm; then log back in
```

2. Confirm the driver side is actually healthy before blaming it. The Arch AUR `displaylink` package's unit is `displaylink.service` (there is no `displaylink-driver.service` on Arch — that name comes from the vendor's Ubuntu installer):

```bash
systemctl status displaylink.service
lsmod | grep evdi
ls /dev/dri/
```

Compare the card nodes evdi created against the ones Hyprland actually holds open — the fds are symlinks to /dev/dri/cardN, so match the numbers by hand:

```bash
ls -l /sys/class/drm/*/device/driver | grep evdi   # which cardN are evdi's
ls -l /proc/$(pgrep -x Hyprland)/fd | grep /dev/dri  # which cardN Hyprland opened
```

An evdi card that never appears in the second list is one Hyprland never opened.

3. Have the driver running before login so the card nodes exist when Hyprland starts:

```bash
sudo systemctl enable --now displaylink.service
```

This is necessary but not sufficient — the dock must also be attached before the session starts, since Hyprland enumerates DRM devices once.

4. If you dock and undock all day, prefer a DisplayPort-Alt-Mode/Thunderbolt dock over a DisplayLink one — those drive real connectors on your GPU and are hotplugged normally.

**Verify.** After re-login with the dock attached, `hyprctl monitors | grep ^Monitor` lists every panel, and `ls -la /proc/$(pgrep -x Hyprland)/fd | grep -c evdi` is non-zero.

Sources: <https://github.com/hyprwm/Hyprland/issues/14538> · <https://github.com/hyprwm/Hyprland/issues/7292>

---

## One external monitor never comes back after the idle screen-off timeout

`dpms-external-monitor-wont-wake-after-idle` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** hypridle blanks the screens after the idle timeout. Moving the mouse brings back the laptop panel and one external monitor, but the third display stays completely black — the only way back is to unplug and replug it, or reboot. The journal shows `Couldn't commit output DP-5`. Sometimes the reverse happens on the way down: `hyprctl dispatch dpms off` from hypridle turns off only the primary monitor while the others stay lit, then flicker when I come back.

**Cause.** Hyprland's DPMS dispatcher issues a DRM-level power change per output, and on some links (Thunderbolt/USB4 docks, DisplayPort MST, NVIDIA) the commit for one output fails and is never retried, leaving that screen dark while the others come back. The all-monitors form of the dispatcher is also unreliable when driven by hypridle rather than by hand — discussion #11230 reports that a manual invocation turns off all monitors while the hypridle-triggered one regularly misses some, and #14234 tracks monitors that will not come back on at all. (Historical note: #2437 is the frequently-cited report of `Couldn't commit output DP-5` on a Thunderbolt-attached Dell, but it is closed as completed and was traced to a wlroots bug fixed with `WLR_DRM_NO_MODIFIERS`; Hyprland has run on Aquamarine rather than wlroots since 0.42, so that specific fix no longer applies and the current failures are a different code path with the same symptom.) On top of the commit failures, `misc:mouse_move_enables_dpms` and `misc:key_press_enables_dpms` both default to `false`, so input does not wake the outputs at all unless something explicitly re-enables them.

> **Audit corrected this record.** Strong record with one API defect and one stale citation. Verified: `hl.dsp.dpms({ action?, monitor? })` and `hl.dsp.force_renderer_reload()` are both documented, the Monitor param accepts a name or `desc:`, and `hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'` is exactly the form Omarchy uses in `omarchy-brightness-display` and `omarchy-hyprland-monitor-clamshell`. `misc:mouse_move_enables_dpms` and `misc:key_press_enables_dpms` both default to `false` as stated. `hypridle.conf` is still hyprlang/ini, so "do not convert it to Lua" is right. #2437 is real and its body does contain `[ERR] Couldn't commit output DP-5` on a Thunderbolt-attached Dell; discussion #11230 is real and matches its summary. `wlopm` is in `extra`, so `pacman -S --needed wlopm` works (the `yay` fallback is unnecessary but harmless). The Omarchy 4 section is exact: hypridle is not in Quattro at all, `~/.config/omarchy/shell.json` carries a top-level `idle` block with `screensaver` and `lock` in seconds — the record's JSON matches `manual/13-toggles-idle-screensaver.md` verbatim, defaults included — and `omarchy-debug-idle` exists. The defect: `hl.set("misc:mouse_move_enables_dpms", true)` is not a real API. Only `hl.config({ category = { option = ... } })` is documented, and `hl.set` appears nowhere in the wiki or the Omarchy tree. Step 1 is the first thing a reader pastes, and it takes the config file down with it. Separately, #2437 is closed as *completed* and was resolved via the wlroots `WLR_DRM_NO_MODIFIERS` workaround — Hyprland has used Aquamarine, not wlroots, since 0.42, so presenting it as the live mechanism is stale; #11230 and #14234 are the current threads.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The Hyprland wiki warns that binding DPMS directly to a key "might cause undefined behavior" — call it from a timer or a script, not straight from a bind. If you experiment with `dpms disable` on your only monitor and input wake is not configured, you will have a black but running session: switch to a TTY with `Ctrl+Alt+F2` and run `hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'` with `HYPRLAND_INSTANCE_SIGNATURE` exported, rather than power-cycling.

**Fix.**

Steps 2 through 5 and the Omarchy 4 section are correct as written — keep the per-output `hypr-dpms-on` retry loop, the `monitors all` filter, the manual `hl.dsp.dpms({ action = "enable", monitor = "DP-5" })` rescue, `hl.dsp.force_renderer_reload()`, and the `wlopm` alternative. Only step 1 needs replacing.

**1. Let input wake the displays.** Both options default to `false`. The documented Lua syntax is `hl.config`, not `hl.set` — add to `~/.config/hypr/looknfeel.lua`:

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

**Symptom.** Laptop in clamshell on a Thunderbolt/USB4 dock. Short sleeps come back fine, but after ~40 minutes or more of suspend the machine wakes (keyboard works, `hyprctl` answers, fans spin) and the external monitor never lights up — it sits in standby until you open the lid or reboot. Journal shows `[drm] Skip DMUB HPD IRQ callback in suspend/resume` and `xhci_hcd 0000:03:00.0: Controller not ready at resume -19`.

**Cause.** On resume, amdgpu discards hotplug interrupts raised inside the resume window, so re-detection depends on the dock re-asserting HPD *after* resume. After a long s2idle the Thunderbolt tunnel does not fully come back and that HPD never arrives. The kernel keeps the stale pre-suspend `connected` state, so nothing looks wrong from userspace and nothing re-modesets. This is a kernel/DRM state problem, not a compositor one — `hyprctl reload` does not help.

> **Audit corrected this record.** The problem is real (basecamp/omarchy#7328 exists with a matching title) and the sysfs force-reprobe is a legitimate workaround, but three things need fixing. (1) The connector example is wrong for the command given: `ls -d /sys/class/drm/card*-*` yields `/sys/class/drm/card1-DP-5`, not `/sys/class/drm/card1/card1-DP-5`. (2) The reasoning about `echo detect` is inverted, and the consequence matters: in drm_sysfs.c, status_store calls fill_modes for `detect` too (the `|| !connector->force` branch), so detect *does* re-probe — what none of off/on/detect does is emit a hotplug uevent. That is why the compositor often does not notice, and why a `hyprctl reload` is needed afterwards (the sibling records for the same technique include one; this one omits it). (3) The resume hook is genuinely harmful as written: it forces every DP connector off for a second on every single resume, including the ones that came back fine, which shuffles workspaces and windows on healthy multi-monitor setups. It also belongs in /etc/systemd/system-sleep/ — /usr/lib/systemd/system-sleep/ is the vendor directory for packages.
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

To automate it, drop a resume hook — but only re-probe connectors that came back *dis*connected, so a working monitor is never blanked on every resume:

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

(Use `/etc/systemd/system-sleep/`, not `/usr/lib/systemd/system-sleep/` — the latter is the package-owned vendor directory.)

**Verify.** After a >40 minute suspend, the external panel lights up on wake with the lid still closed, and `hyprctl monitors` reports the correct mode.

Sources: <https://github.com/basecamp/omarchy/issues/7328>

---

## Lock screen draws the password box on one monitor only; the others are blank

`hyprlock-password-box-only-on-one-monitor` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-3`, `omarchy-4`, `wayland`

**Symptom.** hyprlock locks the session but the clock, avatar and password field only render on the laptop panel. The two external monitors are just a flat colour — or still showing a frozen image of my desktop — with no indication of where to type. I have to guess which screen has focus. On a triple-monitor desk it looks like the lock screen half-crashed.

**Cause.** hyprlock puts a session-lock surface on every output, but the *widgets* drawn on those surfaces are filtered by each widget's `monitor` field. The wiki states: *"`monitor` is available for all widgets and can be left empty for 'all monitors'."* Most shared configs and theme drops pin `monitor = eDP-1` (or a `desc:` string) on the `background`, `input-field` and `label` blocks — often copied from someone's single-laptop setup — so every other output gets a bare surface with nothing on it. A `background` block pinned to one monitor likewise leaves the others on the fallback `color`.

> **Audit corrected this record.** The diagnosis and the main fix are correct and well sourced. The quoted line "`monitor` is available for all widgets and can be left empty for 'all monitors'" is verbatim from the hyprlock wiki, which also confirms `monitor` defaults to empty on `background`, `image`, `shape`, `input-field` and `label`, that it takes the same string as the Hyprland monitor config including `desc:`, and that `path = screenshot` is valid. hyprlock.conf is indeed still hyprlang while Hyprland moved to Lua, so "do not convert it" is right. The Omarchy 4 section checks out: the lock screen is the Quickshell Omarchy shell configured through `~/.config/omarchy/shell.json`, `omarchy-shell lock status` is the real subcommand (`omarchy-restart-shell` calls exactly that and parses `.secure` / `.requested`), `omarchy-debug-idle` exists, and `omarchy-restart-shell` does refuse while the session is genuinely locked and secure. The defect is the test step: `hyprlock --immediate` is not a valid flag. The documented argument list is `-v/--verbose`, `-q/--quiet`, `-c/--config`, `--display`, `--grace`, `--immediate-render`, `--no-fade-in`, `-V/--version`, `-h/--help`. `--immediate` will be rejected and hyprlock will not start — and even the real `--immediate-render` only skips waiting for background resources, so it was never the flag that makes a test safe. The record's own safety advice (open a TTY first) is the right instinct, but the command it pairs with is wrong and `--grace` is the flag that actually gives you an escape hatch.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A broken hyprlock config is a locked-out-of-your-machine failure: hyprlock fails safe by staying locked. Always have a second TTY logged in before testing lock-screen changes, and never migrate `hyprlock.conf`/`hypridle.conf` to Lua — the hypr* tools deliberately stayed on hyprlang after Hyprland 0.55 deprecated it, so a Lua rewrite of these files will fail to parse and leave you with a lock screen that cannot authenticate you.

**Fix.**

Everything else in the record stands — leave `monitor =` bare on `background`, `input-field` and `label`, use `grep -n 'monitor' ~/.config/hypr/hyprlock.conf` to find pinned widgets, add an empty-`monitor` catch-all if you want per-screen backgrounds, keep `input-field` unpinned, and prefer `desc:` over connector names. Only the test step is wrong.

**Test without locking yourself out.** `--immediate` does not exist; hyprlock's flags are `-v/--verbose`, `-q/--quiet`, `-c/--config FILE`, `--display NAME`, `--grace SECONDS`, `--immediate-render`, `--no-fade-in`, `-V/--version`, `-h/--help`. Use `--grace`, which gives you a window to dismiss the lock without authenticating:

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

(`--immediate-render` is the flag the record was reaching for by name, but it only starts drawing widgets before background resources finish loading — it is a rendering option, not a safety net.)

**Verify.** Lock the session with a second TTY open as an escape hatch. Every monitor should show the background and the password field, and typing should register no matter which screen you look at.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Hypr%20Ecosystem/hyprlock.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-shell> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-debug-idle> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/manual/13-toggles-idle-screensaver.md>

---

## Stop a docked laptop's internal scale jumping back to 2 by itself

`internal-scale-snaps-back-to-2-nwg-displays` · severity: **high** · frequency: **common** · applies to: `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** On a docked laptop the internal panel's scale keeps jumping back to 2 every couple of seconds, all by itself, no matter what you set in the display panel or in `monitors.lua`. Everything on the laptop screen is comically huge. Some users see the same reset only after the screensaver/lock screen runs.

**Cause.** `omarchy-hyprland-monitor-clamshell` runs a 2-second `sync_internal_scale` poll whenever a laptop has an external monitor active. It reads the wanted scale out of `monitors.lua` with a *line-anchored* regex that only matches when `hl.monitor({` and `output = "eDP-1"` are on the same line. GUI tools like `nwg-displays` write each monitor as a multi-line block, so the grep finds nothing, every fallback misses, and `read_monitor_scale` returns its hardcoded default of `2` — which the poll then re-applies twice a second.

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

**Symptom.** You disabled the laptop panel with Super+Ctrl+Delete to work external-only, then later unplugged the external monitor — and the laptop screen stays completely black. It came back automatically on Omarchy 3.x. `hyprctl monitors` still lists the monitor you unplugged.

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

**Symptom.** A monitor that was switched off (or on a different input) when you booted stays black forever afterwards, even once you power it on. `hyprctl monitors all` lists it as enabled but with a size of `0x0`, and no amount of replugging brings it up.

**Cause.** A powered-off display answers the DDC probe with a partial EDID that carries no video modes. Hyprland brings the output up anyway, at 0x0, and nothing in the compositor fires an event for that state, so it never retries. Omarchy ships `omarchy-hyprland-monitor-modeless` specifically to detect it.

> ⚠️ **Risk.** Editing kernel parameters touches the bootloader (systemd-boot: /boot/loader/entries/*.conf, GRUB: /etc/default/grub + grub-mkconfig). A typo in the loader entry can leave the machine unbootable — keep a known-good entry and a live USB handy.

**Fix.**

Detect it:

```bash
hyprctl monitors all -j | jq -c '.[] | select(.disabled != true and (.width == 0 or .height == 0)) | {name,width,height}'
```

Power the monitor on / select the right input, then force a re-probe and reload:

```bash
CONN=$(ls -d /sys/class/drm/card*-HDMI-A-1)   # substitute your connector
echo off    | sudo tee $CONN/status
sleep 1
echo on     | sudo tee $CONN/status
echo detect | sudo tee $CONN/status
hyprctl reload
```

If it still comes up modeless, pin an explicit mode in `~/.config/hypr/monitors.lua` so Hyprland does not depend on the EDID:

```lua
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "auto", scale = 1 })
```

As a last resort, force the mode from the kernel command line so it is set before the compositor starts: add `video=HDMI-A-1:1920x1080@60` to your kernel parameters.

**Verify.** `hyprctl monitors all -j | jq -c '.[] | {name,width,height}'` reports a non-zero width and height for the output.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-modeless> · <https://wiki.archlinux.org/title/Kernel_mode_setting>

---

## Fix NVIDIA monitors staying black or corrupted after suspend

`nvidia-black-screen-external-after-suspend` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `systemd-boot`, `wayland`

**Symptom.** Wake the machine from suspend and the external monitor (or all monitors) stays black, or comes back with corrupted garbage. Sometimes only a full reboot recovers it. NVIDIA GPU.

**Cause.** NVIDIA does not preserve video memory across suspend unless explicitly told to, and the suspend/resume helper services must be enabled. Without them the driver loses the framebuffer contents and cannot re-modeset the outputs on resume.

> ⚠️ **Risk.** Editing bootloader entries or GRUB config can make the system unbootable if you break the line. Copy the existing entry to a backup first, and never edit only /etc/default/grub without re-running grub-mkconfig.

**Fix.**

On Arch these are usually already in place, but verify:

```bash
systemctl is-enabled nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
sudo systemctl enable nvidia-suspend.service nvidia-hibernate.service nvidia-resume.service
```

Add the kernel parameter that keeps video memory across suspend:

- systemd-boot: append to the `options` line in `/boot/loader/entries/<entry>.conf`
- GRUB: append inside `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

```
nvidia.NVreg_PreserveVideoMemoryAllocations=1
```

Reboot and check it took:

```bash
cat /proc/cmdline | tr ' ' '\n' | grep NVreg
```

If resume-from-hibernation stops working after this, disable early KMS (remove the nvidia entries from `MODULES=()` in `/etc/mkinitcpio.conf` and run `sudo mkinitcpio -P`) — early module loading and hibernate resume conflict. If you are on `nvidia-open-dkms` and still broken, the fully proprietary driver is worth a try, and vice versa.

**Verify.** `systemctl suspend`, wake, and all monitors light up with the right modes; `cat /proc/cmdline` contains `NVreg_PreserveVideoMemoryAllocations=1`.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Nvidia/_index.md>

---

## Monitor reports garbage or no EDID (KVM, long HDMI run, cheap adapter) — override it with a firmware EDID

`edid-override-for-bad-or-missing-monitor-edid` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `grub`, `hyprland`, `kvm`, `laptop`, `limine`, `manjaro`, `mkinitcpio`, `omarchy`, `omarchy-4`, `systemd-boot`, `wayland`

**Symptom.** Through a KVM switch, a 15 m HDMI run, or a USB-C→HDMI dongle, the monitor comes up at 1024x768 or 640x480 and `hyprctl monitors all` lists only two or three junk modes — the native 2560x1440 is simply not there. Sometimes the output shows up enabled but `0x0`, or the display is not detected at all. Plugged straight into the GPU with a short cable it is perfect, so the panel is fine — the EDID is being mangled in transit.

**Cause.** The monitor's EDID is read over the DDC/I²C sideband channel, which is the first thing to fail on a marginal link. A KVM, a long passive cable, or a cheap active adapter can return a truncated, corrupted, or empty EDID; the kernel then falls back to a generic mode list and the compositor can only offer what the kernel gave it. Arch's KMS page states this directly: *"If your native resolution is not automatically configured or no display at all is detected, then your monitor might send none or just a skewed EDID file. The kernel will try to catch this case and will set one of the most typical resolutions."* The remedy is to hand the kernel a known-good EDID binary for that connector.

> **Audit corrected this record.** Almost everything is verified verbatim against the Arch KMS page: the quoted sentence about a skewed or missing EDID, `/usr/lib/firmware/edid/`, `drm.edid_firmware=edid/file.bin`, the `CONNECTOR:` scoping, the comma-separated multi-connector form, `cat file > /sys/kernel/debug/dri/0/HDMI-A-2/edid_override`, `echo -n reset > ...edid_override`, `echo 1 > ...trigger_hotplug`, the lockdown-mode caveat, `echo edid/file.bin > /sys/module/drm/parameters/edid_firmware` taking effect only for newly plugged displays, the `video=<conn>:<xres>x<yres>[M][R][-<bpp>][@<refresh>][i][m][eDd]` syntax, the `video=DVI-I-1:1024x768@85 video=TV-1:d` example, and the note that `video=` "is useful for all Wayland compositors". `read-edid` (providing `get-edid`) is in `extra`. The Limine claims hold: `/etc/limine-entry-tool.d/omarchy-defaults.conf` exists with exactly the `KERNEL_CMDLINE[default]+=" ... "` form and `ENABLE_UKI=yes`, `limine-update` is a real command Omarchy calls, and `/etc/mkinitcpio.conf.d/` is a directory Omarchy already populates with `kms` in HOOKS (so the early-KMS warning is right). The gap is step 4: on Omarchy 4 the initramfs *and the UKI Limine actually boots* are rebuilt by `limine-mkinitcpio`, not by `mkinitcpio -P`. Omarchy's own scripts make this explicit — `omarchy-hibernation-setup` writes a `KERNEL_CMDLINE` drop-in and then runs `sudo limine-mkinitcpio` with the comment "limine-mkinitcpio rebuilds initramfs/UKI for all kernels and updates the /boot/limine.conf entries via limine-entry-tool", and `omarchy-plymouth-set` uses `sudo mkinitcpio -P` only as the fallback when `limine-mkinitcpio` is absent. A user who runs `mkinitcpio -P` and reboots may find the EDID silently absent from the UKI. Also minor: the connector-discovery loop's `card?-` pattern breaks on `card10` and above.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A wrong or corrupt EDID binary can leave you with no display at all from early boot onward, before any TTY is usable. Always test with the `edid_override` debugfs path first — it is reversible with `echo -n reset` and survives nothing more than a reboot. Editing the kernel command line and running `mkinitcpio -P`/`limine-update` rewrites your boot entries: keep the fallback entry that Omarchy generates (`ENABLE_LIMINE_FALLBACK=yes`) and know how to reach the Limine menu, because if Direct Boot is on you may need to pick Limine from the firmware boot menu to get a rescue entry. Do not run `mkinitcpio -P` in the middle of an interrupted `pacman`/`omarchy update` transaction.

**Fix.**

Steps 1, 2, 3 and 5 and the `video=` alternative are correct as written. Two changes.

**Step 1 — make the connector listing robust.** `${con#*/card?-}` only matches single-digit card numbers, so it silently mangles `card10-DP-1` on machines with several DRM devices. Use:

```bash
for p in /sys/class/drm/card*-*/status; do
  d=${p%/status}
  printf '%s\t%s\n' "${d##*/}" "$(cat "$p")"
done
```

That prints the full directory name (`card1-DP-1`), which is what you feed to `cp`; the connector name Hyprland uses is the part after the first `-` (`DP-1`).

**Step 4 — rebuild the right image.** On Omarchy 4 (and any Limine + `limine-entry-tool` setup with `ENABLE_UKI=yes`), the cmdline and `FILES` are baked into a UKI that plain `mkinitcpio -P` does not regenerate the boot entry for. Write the drop-in as the record says:

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

If you also added the `KERNEL_CMDLINE` drop-in in step 3, `sudo limine-mkinitcpio` covers both — `sudo limine-update` also works but additionally re-deploys the bootloader binary and rebuilds a second time, which is why Omarchy prefers `limine-mkinitcpio` for a cmdline-only change.

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

**Symptom.** A TV or cheap monitor on HDMI blanks for about 0.2 s on every mouse click or window interaction, then recovers. The same cable, port and kernel are fine under Sway and in a plain TTY — only Hyprland flickers. Disabling blur, animations, hardware cursors, `render:cm_enabled`, `render:direct_scanout` and `misc:vfr` changes nothing.

**Cause.** The TV renegotiates the HDMI link (or drops out of its low-latency mode) when the compositor changes what it presents. Hyprland's presentation path triggers this on some Intel i915 + consumer-TV combinations where Sway's does not. A closely related variant on AMD iGPUs: a DPMS-off from a screen blanker makes amdgpu emit a spurious connector hotplug that reads as disconnected, producing a metronomic black/on cycle and thousands of `Disabling output HDMI-A-2` lines in `hyprland.log`.

> **Audit corrected this record.** Both halves of the problem are real and well cited — hyprwm/Hyprland#13338 exists as 'Samsung Smart TV flickers on interaction via HDMI — works fine under Sway', and basecamp/omarchy#8689 exists as 'Lock screen alternates black <-> lock UI every ~13.5s on AMD iGPU over HDMI', matching the AMD spurious-hotplug variant. The option names in the symptom (render:cm_enabled, render:direct_scanout) are both real, the per-monitor `bitdepth = 8` and `vrr = 0` fields are valid per the Monitors page, and Super+Ctrl+I is confirmed bound to 'Toggle locking on idle' in default/hypr/bindings/utilities.lua. The one hard error is step 3: `vfr` is not in the misc category. The Variables page lists it under Debug (`debug:vfr`, bool, default true) — `hl.config({ misc = { vfr = false } })` targets a nonexistent option and will be rejected or silently ignored, leaving the user thinking they tested the workaround when they did not.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Work around it at the display and the compositor:

1. Turn off the TV's own picture processing — set the HDMI input's label to `PC` and enable Game Mode. This is what fixes it most often on Samsung/LG sets.
2. Pin a plain 60 Hz mode and 8-bit output so the link is never renegotiated:

```lua
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "0x0", scale = 1, bitdepth = 8, vrr = 0 })
```

3. Stop variable-frame-rate presentation from idling the link. `vfr` lives under `debug`, not `misc` — `misc.vfr` does not exist:

```lua
hl.config({
  debug = { vfr = false },
  misc  = { vrr = 0 },
})
```

Leave `debug.vfr = false` in place only while testing; it is on by default to conserve power, so turn it back on if it makes no difference.

4. If the flicker only happens once the screen has been idle/locked, disable the blanker rather than the compositor. On Omarchy, check `journalctl --user -b | grep -c 'Disabling output'` — a large number confirms the spurious-hotplug variant; toggle idle locking off with Super+Ctrl+I.

**Verify.** `grep -c 'Disabling output' ~/.local/share/hyprland/hyprland.log` (or `hyprctl rollinglog | grep 'Disabling output'`) stops growing, and clicking no longer blanks the panel.

Sources: <https://github.com/hyprwm/Hyprland/issues/13338> · <https://github.com/basecamp/omarchy/issues/8689> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Variables.md>

---

## Fix Chromium and Electron apps looking soft on a fractionally scaled monitor

`electron-chromium-blurry-fractional-scale` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Chrome/Brave/Chromium, VS Code, Slack, Signal, Spotify and Discord look soft, fuzzy or double-scaled on a fractionally scaled monitor (e.g. 150%). Fonts have halos; native GTK apps next to them look sharp.

**Cause.** Chromium/Electron apps that fall back to XWayland get bitmap-upscaled by the compositor. Even on native Wayland they follow GTK settings and ignore fractional factors unless told a device scale factor explicitly. Since Electron 38.2 Wayland is the default; older builds need an ozone hint.

> **Audit corrected this record.** The problem and most of the fix are right — ~/.config/chromium-flags.conf and --force-device-scale-factor are documented on the Arch HiDPI/Chromium pages, ~/.config/electron-flags.conf is the documented Arch Electron config file, the slack.desktop Exec-copy pattern is straight off the HiDPI page, and Omarchy's default/hypr/envs.lua really does export ELECTRON_OZONE_PLATFORM_HINT and OZONE_PLATFORM. But the Electron advice is obsolete: the Arch Electron page states `--ozone-platform-hint=wayland (removed in Electron 38)` and uses `--ozone-platform=wayland` instead, so `--ozone-platform-hint=auto` is a dead flag in electron-flags.conf and in the Slack launcher. Two further problems: electron-flags.conf is only read by Arch's `electron` package and NOT by apps that bundle their own Electron (slack-desktop, signal-desktop) — those need a per-app `~/.config/<app>-flags.conf` or the .desktop edit; and `hyprctl clients | grep -A2 xwayland` prints the lines *after* the xwayland field, so it never shows you which app it is.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Omarchy already exports `ELECTRON_OZONE_PLATFORM_HINT=wayland` and `OZONE_PLATFORM=wayland`. If an app still uses XWayland or renders blurry, force the scale factor.

Chromium (Arch's package reads this file; Chromium 140+ is already Wayland by default, so the ozone flag is only needed on older builds):

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

`--ozone-platform-hint` was removed in Electron 38 — use `--ozone-platform=wayland`. Note that `electron-flags.conf` is read only by Arch's `electron` package; apps that bundle their own Electron (slack-desktop, signal-desktop, Discord) ignore it. Some of those read a per-app file instead, e.g. `~/.config/spotify-flags.conf`. For the rest, copy the launcher and edit `Exec=`:

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

**Symptom.** Any script or command that used to work now fails: `hyprctl keyword monitor "HDMI-A-1,2560x1440@59.95,1600x0,1"` returns `keyword can't work with non-legacy parsers. Use eval.` The Omarchy display panel's enable/disable switch also appears to do nothing — you flip it and the monitor stays exactly as it was.

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

**Cause.** Hyprland only accepts a scale that turns the monitor's pixel resolution into whole logical pixels, in 1/120 steps. Formally, `round(scale*120)` must divide `gcd(width*120, height*120)`. 1920x1080/1.4 = 1371.43x771.43, so 1.4 is rejected. The valid set differs per resolution: 1.5 is fine on 1920x1080 and 3840x2160 but invalid on 2560x1440; 1.75 is invalid on all three.

> **Audit corrected this record.** The mechanism, the awk helper and the preset list are all verified correct — the awk function is byte-for-byte Omarchy quattro's clean_scale() from bin/omarchy-hyprland-monitor-scaling, SCALES=(1 1.25 1.6 2 3 4) matches exactly, and the wiki confirms the divisibility rule. The resolution-specific claims check out (1.5 valid on 1920x1080 and 3840x2160, invalid on 2560x1440; 1.75 invalid on all three). But the worked example's stated output is wrong: gcd(2560*120,1440*120)=19200, k=210, and the smallest divisor of 19200 that is >=210 is 240, so `cleanscale 1.75 2560 1440` prints 2, not 1.777. A user who sees 2 will think the helper is broken. Also `omarchy hyprland monitor scaling` accepts any value 1..4, not only the presets.
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

`up`/`down` step through the presets `1 1.25 1.6 2 3 4`; an explicit argument may be any value between 1 and 4 and is rounded to the nearest legal scale for the focused monitor.

**Verify.** `hyprctl monitors | grep -E 'scale|^Monitor'` shows the scale you asked for and no config-error banner is drawn on the screen.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-scaling>

---

## Mirroring one display onto another, and why the mirror vanishes from hyprctl monitors

`mirroring-a-display-and-hidden-mirror-outputs` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** I need to mirror my laptop screen onto a projector for a presentation, or mirror the internal panel while docked. Giving both monitors the same `position = "0x0"` doesn't mirror anything — Hyprland just warns that the monitors overlap and shoves one aside. And once I do get a mirror working, the mirrored output disappears completely from `hyprctl monitors`, so my status bar and my own scripts think the monitor was unplugged. `hl.get_monitors()` in Lua doesn't list it either, and `hl.get_monitor(id)` on it returns nil.

**Cause.** Mirroring is not done with positions — it is a dedicated `mirror` field on the monitor rule that names the output to copy. Once an output is mirroring another it is no longer an independent output in the layout, so Hyprland deliberately omits it from `hyprctl monitors`; it only appears in `hyprctl monitors all`. The same applies to the Lua API: `hl.get_monitors()` returns only enabled, non-mirrored outputs, which is why `HL.Monitor.is_mirror` reads as useless (hyprwm/Hyprland discussion #14645). Mirroring is also a straight scanout copy, not a re-render: a 1080p source mirrored onto a 4K panel stays 1080p, and mismatched aspect ratios get squished or stretched.

> ⚠️ **Risk.** If you write a `mirror` rule for the only external output and then disable the source panel (e.g. the internal-display toggle), you can end up with no monitor showing anything. Omarchy guards against this by forcing the `internal-monitor-disable` toggle off before enabling the mirror; if you hand-roll it, keep a TTY available (`Ctrl+Alt+F2`) and be ready to run `hyprctl reload` after reverting monitors.lua. A catch-all `output = ""` mirror rule also captures every future display, including a second desk monitor you wanted as an extended screen.

**Fix.**

**Mirror by hand (Hyprland 0.55+ Lua, `~/.config/hypr/monitors.lua`)**

The rule goes on the output that should *show* the copy, and `mirror` names the source:

```lua
-- eDP-1 is the real output; HDMI-A-1 shows a copy of it
hl.monitor({ output = "eDP-1",    mode = "preferred", position = "0x0",  scale = 1 })
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1, mirror = "eDP-1" })
```

A catch-all so *any* newly plugged screen mirrors the internal panel (useful for projectors whose connector name you don't know in advance):

```lua
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1, mirror = "eDP-1" })
```

Apply without restarting the session:

```bash
hyprctl reload
```

**On Omarchy 4** there is a shipped toggle — `Super + Ctrl + Alt + Delete`, or from a terminal:

```bash
omarchy-hyprland-monitor-internal-mirror toggle   # on/off/toggle/recover
```

It picks the first active non-`eDP`/`LVDS`/`DSI` output, writes a generated rule to
`~/.local/state/omarchy/toggles/hypr/internal-monitor-mirror.lua`, and runs `hyprctl reload`.
Turn it off explicitly with:

```bash
omarchy-hyprland-monitor-internal-mirror off
```

**Seeing the mirrored output again.** Plain `monitors` will not show it. Use:

```bash
hyprctl monitors all
hyprctl monitors all -j | jq -r '.[] | "\(.name)\tdisabled=\(.disabled)\t\(.width)x\(.height)@\(.refreshRate)"'
```

Omarchy's own `omarchy-hyprland-monitor-modeless` does exactly this and documents why:
*"Mirrors are absent from plain `monitors`, hence `all` plus an explicit disabled filter."*
Any script of yours that counts monitors must use `monitors all` too, or it will conclude a
mirrored screen is gone.

**Expectation setting:** the mirror is not re-rendered. Mirroring 1920x1080 onto a 3840x2160
panel gives you a 1080p image, and mirroring 16:10 onto 16:9 will stretch. If you need a
sharp image on the projector, set both outputs to the same mode instead of mirroring, or
accept the source resolution.

**Verify.** `hyprctl monitors` should now list only the source output, while `hyprctl monitors all` lists both. Confirm the copy is live by moving a window — it should appear on both screens simultaneously. On Omarchy, `omarchy-hyprland-toggle-enabled internal-monitor-mirror` exits 0 while mirroring is on.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md> · <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://github.com/hyprwm/Hyprland/discussions/14645> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-hyprland-monitor-internal-mirror> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-hyprland-monitor-modeless> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/default/hypr/bindings/utilities.lua>

---

## Get a 120, 144 or 165 Hz panel out of 60 Hz

`monitor-stuck-at-60hz-high-refresh` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** A 120/144/165/240 Hz panel runs at 60 Hz. `hyprctl monitors` lists `1920x1080@180.00Hz` under `availableModes`, but setting `mode = "1920x1080@180"` in the config is simply ignored and the current mode stays `1920x1080@60`. Motion feels sluggish and mouse movement stutters.

**Cause.** `preferred` uses the display's EDID preferred timing, which on many panels (and on almost everything behind the NVIDIA proprietary driver) is the 60 Hz DTD, not the fast one. On NVIDIA 595.x/610.x specifically, Hyprland 0.55.x/0.56.x has been reported to ignore an explicit `mode` and fall back to the EDID preferred timing anyway.

> ⚠️ **Risk.** Regenerating the initramfs (`mkinitcpio -P`) while a driver rebuild is half-finished can leave an unbootable initramfs. Do it after a completed `pacman -Syu`, never in the middle of a partial upgrade, and keep the fallback initramfs entry available in your bootloader.

**Fix.**

First try `highrr`, which asks for the highest supported refresh rate rather than the preferred one. In `~/.config/hypr/monitors.lua`:

```lua
hl.monitor({ output = "", mode = "highrr", position = "auto", scale = 1 })
```

On Hyprland <= 0.54 (`monitors.conf`): `monitor=,highrr,auto,1`.

If you need a specific rate, copy the string verbatim out of `availableModes` — the refresh must match a listed mode:

```bash
hyprctl monitors all -j | jq -r '.[] | .name, (.availableModes[])'
```

```lua
hl.monitor({ output = "DP-1", mode = "2560x1440@164.96", position = "0x0", scale = 1 })
```

On NVIDIA, make sure DRM modesetting is actually on before chasing anything else:

```bash
cat /sys/module/nvidia_drm/parameters/modeset   # must print Y
```

If it prints `N`, create `/etc/modprobe.d/nvidia.conf` with `options nvidia_drm modeset=1`, then `sudo mkinitcpio -P` and reboot.

**Verify.** `hyprctl monitors | grep -A1 '^Monitor'` shows the high rate as the *current* mode, not just in `availableModes`.

Sources: <https://github.com/basecamp/omarchy/pull/161> · <https://github.com/hyprwm/Hyprland/issues/15210> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Monitors.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Nvidia/_index.md>

---

## Workspaces bound to a monitor pile onto the wrong screen and never go back after docking

`workspace-monitor-binding-lost-on-hotplug` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** I pin workspaces 1-5 to the external `DP-1` and 6-10 to the laptop panel. If I boot or log in undocked, every workspace is created on the laptop screen. Then I dock, the external monitor lights up — and workspaces 1-5 stay on the laptop. They never migrate back. Same thing after a monitor sleeps and wakes. Persistent workspaces also stop being persistent, and after a reboot my monitors sometimes come back as `DP-2`/`HDMI-A-3` instead of `DP-1`/`HDMI-A-1`, so the rules don't match at all any more.

**Cause.** A workspace rule's `monitor` field is applied when the workspace is *created*, not continuously. If the named output does not exist at that moment, Hyprland creates the workspace on whatever monitor is available, and nothing moves it later when the output appears. There is no rule condition that matches monitor state: the feature request for one, hyprwm/Hyprland #7049 ("Window/Workspace Rules to Match Monitors States"), was closed as *not planned*, so this is settled behaviour rather than a pending fix. Connector names are a separate, compounding hazard — DRM connector numbering is not stable across boots or across cable/port changes, so a rule pinned to `DP-1` can silently match nothing after a reboot; this is why the wiki documents the `desc:` prefix. (Hyprland #5464 is the frequently-cited report of workspaces landing on the wrong screen, but note it was closed as not-planned during the issues→discussions migration and the reporter's specific case turned out to involve a config syntax error, so treat it as a symptom report rather than a root-cause analysis.)

> **Audit corrected this record.** The behaviour described is real and the fix is mechanically sound — `hl.workspace_rule` accepts `monitor`, `default` and `persistent` per the wiki; the Monitor param for dispatchers explicitly accepts `desc:` and a description; `hl.dsp.workspace.move({ workspace?, monitor })` and `hl.dsp.workspace.swap_monitors({ monitor1, monitor2 })` are both documented; the `socat -U - UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock | while read -r line` pattern and the `monitoradded` event are copied correctly from the IPC page's own bash example; `hyprctl dispatch 'hl.dsp....'` is a real invocation form (Omarchy's own `omarchy-hyprland-monitor-clamshell` uses `hyprctl dispatch "hl.dsp.dpms({ action = \"$action\", monitor = \"$INTERNAL\" })"`); `o.launch_on_start` is real (`default/hypr/helpers.lua:118`); socat is in `extra` so `pacman -S --needed socat` is correct and the Omarchy ALPM guard only blocks `-S` combined with `-u`. Two citation errors in the cause, though. (1) #7049 is **closed as not_planned**, not "still open". (2) The #5464 characterisation is wrong: the reporter did *not* find connector names shifting between boots — a commenter merely remarked in passing that "ports changing is normal"; the reporter's problem persisted after switching to `desc:` and the thread ended on a config syntax error (`default=true` instead of `default:true`), with vaxerski closing it as part of the issues→discussions migration. A reader who trusts "the rules were matching nothing" as the documented root cause is being misled about what that ticket shows.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `hl.dsp.workspace.move` will happily move a workspace to a monitor that is disabled or mirrored, which hides its windows. Guard the script against firing while only one monitor exists (the `monitoradded` trigger already does this in practice, but a manual run undocked will pile everything onto the laptop panel).

**Fix.**

Steps 1-3 are correct as written; keep the `desc:` monitor rules, the `hypr-restore-workspaces` socat listener, and the one-shot `hl.dsp.workspace.move` repair. Three refinements:

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

If focus does not move, the string is wrong — remember to drop the trailing `(DP-1)`.

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

Restart each app (and log out/in for the env file) for the change to reach it. Do not use the old XWayland HiDPI patches — they are unsupported.

**Verify.** Restart the X11 app: `xeyes`/`xprop` era apps and Steam render at readable size with sharp text. `echo $GDK_SCALE` inside a terminal launched from a keybind returns your value.

Sources: <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Advanced%20and%20Cool/XWayland.md> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://wiki.archlinux.org/title/HiDPI> · <https://wiki.archlinux.org/title/Hyprland>

---

## Stop losing windows and workspaces when you disable a monitor

`disable-monitor-loses-windows-and-workspaces` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** You disable a monitor (display panel toggle, or a `disabled = true` rule) and all the windows that were on it vanish — or reappear stacked on top of everything on the remaining screen. Turning the monitor back on does not restore the layout. Users also report using `disabled` to 'turn the screen off' and being surprised the workspaces moved.

**Cause.** `disabled = true` literally removes the output from the layout: Hyprland migrates every window and workspace off it onto whatever is left. It is not a screen-blank. `dpms` is the screen-blank. Omarchy's display-panel toggle writes a runtime-only rule with no persisted flag, so nothing re-enables the output when the external is later unplugged.

> **Audit corrected this record.** The distinction being drawn is correct and important, and it is upstream's own: the Monitors page warns 'Disabling a monitor will literally remove it from the layout, moving all windows and workspaces to any remaining ones. If you want to disable your monitor in a screensaver style (just turn off the monitor) use the dpms dispatcher.' hyprwm/Hyprland#8024 exists ('All windows/workspaces lost when monitor disconnects'), and `omarchy-hyprland-monitor-internal toggle|on` are real subcommands bound to Super+Ctrl+Delete. The dpms calls are right. But the last command is a legacy hyprlang dispatcher name pasted into Lua: there is no `hl.dsp.moveworkspacetomonitor`. The Dispatchers page puts it in the workspace namespace as `hl.dsp.workspace.move({ workspace?, monitor })`, so the recovery step — the one a user reaches for precisely when their windows are already stranded on an invisible output — fails as written.
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

If windows are already on an invisible output, move the workspace back. The dispatcher lives in the workspace namespace — `hl.dsp.moveworkspacetomonitor` is the old hyprlang name and does not exist in Lua:

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

**Cause.** Omarchy and the recommended Arch setup start Hyprland through `uwsm`. Variables set inside the compositor config only reach clients Hyprland itself spawns, not the systemd user session that launches most apps. The Arch wiki explicitly says not to put environment variables in `hyprland.lua` under uwsm.

> ⚠️ **Risk.** Do not bind `hl.dsp.exit()` or kill the Hyprland process under uwsm — it bypasses the normal shutdown. Use `uwsm stop` or `loginctl terminate-user ""`.

**Fix.**

Put session-wide variables in the uwsm env files, one `export KEY=VALUE` per line, no comments:

```sh
# ~/.config/uwsm/env  (Arch)  or  ~/.config/uwsm/env.d/20-user  (Omarchy)
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_ENABLE_HIGHDPI_SCALING=1
export GDK_DPI_SCALE=1
```

Hyprland-only / aquamarine variables (`HYPR*`, `AQ_*`) go in the Hyprland-specific file:

```sh
# ~/.config/uwsm/env-hyprland
export AQ_DRM_DEVICES=/dev/dri/card1:/dev/dri/card0
```

The exception on Omarchy is `GDK_SCALE`, which the display tooling manages for you in `~/.config/hypr/monitors.lua`:

```lua
local omarchy_gdk_scale = 2
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```

These files are read at session start — log out and back in (`uwsm stop`), a `hyprctl reload` is not enough.

**Verify.** After re-login, `systemctl --user show-environment | grep QT_ENABLE_HIGHDPI_SCALING` shows the value, and apps launched from the launcher pick it up.

Sources: <https://wiki.archlinux.org/title/Hyprland> · <https://github.com/basecamp/omarchy/blob/quattro/default/uwsm/env.d/10-omarchy> · <https://github.com/basecamp/omarchy/blob/quattro/config/hypr/monitors.lua>

---

## HDR / 10-bit enabled: washed-out SDR, banded borders, blank screen shares

`hdr-10bit-washed-out-and-broken-capture` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`, `xdg-desktop-portal`

**Symptom.** I turned on HDR with `bitdepth = 10` and `cm = "hdr"` and now everything SDR looks grey and washed out — the desktop, the browser, YouTube in a window. Window borders and gradients look banded. Worse, screen sharing in Discord/Meet/OBS now shows a completely black or blank window, and `hyprshot`/screenshots come out empty or transparent. Sometimes after a fullscreen HDR game exits, the whole desktop stays washed out until I run `hyprctl reload`.

**Cause.** Three separate documented effects get blamed on one setting. (1) `cm = "hdr"` puts the whole output on a wide-gamut BT.2020 + PQ transfer function, and SDR content mapped into it looks dim and desaturated unless `sdrbrightness`/`sdrsaturation` are raised — the Hyprland wiki marks `hdr`/`hdredid` as experimental. (2) The wiki warns explicitly that colors registered inside Hyprland (window border colors, gradients) do *not* support 10 bit, so borders band. (3) 10-bit/HDR buffers are not consumable by many capture clients: xdg-desktop-portal-hyprland issue #313 is exactly "screenshare is broken when HDR is enabled", fixed by dropping back to 8 bit; and HDR-mode screenshots come out empty unless `render:keep_unmodified_copy` is forced on. The lingering washed-out desktop after a fullscreen HDR app exits is hyprwm/Hyprland #9286 / discussion #10950.

> **Audit corrected this record.** The diagnosis and every wiki fact are right — `render:cm_auto_hdr` default `1`, `keep_unmodified_copy` default 2 with the literal note "Set to 1 if screenshots are transparent.", `quirks:prefer_hdr` 0/1/2 with 2 = gamescope only, the `cm` preset block reproduced verbatim, sdrbrightness/sdrsaturation defaults 1.0 and the documented 1.0..2.0 range, the "Colors registered in Hyprland (e.g. the border color) do not support 10 bit" warning, `cm_enabled` "requires a restart of Hyprland to fully take effect", and the mpv `--target-colorspace-hint-mode=source` note. xdph #313, Hyprland #9286 and discussion #10950 all exist and say what is claimed. But the config API is fabricated: `hl.set("render:keep_unmodified_copy", 1)` does not exist. The Variables page documents exactly one syntax — `hl.config({ category = { value = ... } })` — and there is no `hl.set` anywhere in the wiki or in the entire Omarchy quattro tree, which uses `hl.config({ cursor = { no_hardware_cursors = ... } })` throughout. Copy-pasting those two lines throws a Lua error and the whole config file fails to load, which is worse than the original symptom. The `hl.monitor({...})` blocks are fine as written.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `cm` and `bitdepth` changes force a modeset. The wiki notes that `render:send_content_type` (default true) reporting content type to the monitor "may result in a black screen during the switch" — on some panels the screen can stay black for several seconds or until you re-plug. Do not set `cm = "hdr"` on your only monitor without a TTY (`Ctrl+Alt+F2`) available so you can edit `~/.config/hypr/monitors.lua` back and `hyprctl reload`. `hdr`/`hdredid` are marked experimental upstream; an ICC profile plus HDR is explicitly unsupported ("ICCs are fundamentally incompatible with HDR gaming").

**Fix.**

Only the two `hl.set(...)` lines are wrong; everything else in the record stands as written. Replace them with the documented `hl.config` form (Variables page: `hl.config({ category = { value = ... } })`).

Fix blank/empty screen capture and screenshots — in `~/.config/hypr/looknfeel.lua`:

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

Then `hyprctl reload` as the record already says. Also worth adding: #9286 is closed as *completed* and #10950 is its open follow-up discussion, so the stuck-washed-out-after-fullscreen behaviour is version-dependent — check `hyprctl version` before assuming you are hitting it.

**Verify.** `hyprctl monitors -j | jq -r '.[] | "\(.name) \(.currentFormat) \(.activelyTearing)"'` shows a 10-bit format (e.g. `XRGB2101010`) once `bitdepth = 10` is active. Take a screenshot and confirm it is not transparent/empty, then start a screen share and confirm the preview is not black.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/xdg-desktop-portal-hyprland/issues/313> · <https://github.com/hyprwm/Hyprland/discussions/10950> · <https://wiki.hypr.land/Configuring/Basics/Monitors/>

---

## Write monitor rules that survive a cable swap or a dock replug

`monitor-rules-break-when-ports-swap` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Your carefully written per-monitor rules stop matching after you move a cable, replug a dock, or reboot — the same physical screen is now `DP-3` instead of `DP-2`, so the scale/position/refresh rule silently does not apply and everything comes up at defaults.

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

VRR needs DisplayPort on most hardware; over HDMI it requires HDMI 2.1 VRR support on both ends.

**Verify.** `hyprctl monitors` shows `vrr: true` only on the outputs you intended, and the flicker stops on the desktop.

Sources: <https://wiki.archlinux.org/title/Variable_refresh_rate> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/Hyprland/issues/5797>

---

## Fix a USB4 or Thunderbolt monitor reporting No signal after a reboot

`usb4-displayport-no-signal-after-reboot` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `dock`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** A monitor connected over USB4/Thunderbolt DP-Alt-Mode works perfectly once you are in the session, but after a reboot the screen reports 'No signal' on the Thunderbolt input from the bootloader menu onwards. The only way back is to plug in the native DisplayPort or HDMI cable, get a picture, then replug the USB4 cable.

**Cause.** The Thunderbolt tunnel is not established before the OS takes over the display: the device is not pre-boot authorized, and the DP tunnel only comes up once the Thunderbolt stack is loaded and the device is authorized in Linux. Until then the connector reports nothing.

> **Audit corrected this record.** The technical content is accurate and matches the Arch Thunderbolt wiki exactly — the udev rule `ACTION=="add", SUBSYSTEM=="thunderbolt", ATTR{authorized}=="0", ATTR{authorized}="1"` is that page's verbatim 99-removable.rules example, and the force_power path with GUID 86CCFD48-205E-4A77-9C48-2021CBEDE341 is its verbatim example too. `sudo pacman -S bolt` is correctly a plain -S with no -Sy partial-upgrade hazard, boltctl list is right, and the connector re-probe loop plus `hyprctl reload` is consistent with the other records. basecamp/omarchy#374 exists ('Problems with Display Port over USB4 (BeeLink SER9)'). What is missing is a warning: steps 1 and 2 together — dropping BIOS Thunderbolt security to `none` AND blanket auto-authorizing every device that is ever plugged in — remove Thunderbolt's DMA-attack protection entirely. That is a real security downgrade being handed to a user as a copy-paste, and it needs to be stated. `udevadm control --reload` also needs a `trigger` to affect already-present devices.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting the Thunderbolt security level to `none` or auto-authorizing every device removes the protection against DMA attacks from a malicious plugged-in device. Do not do this on a machine that gets plugged into untrusted docks or cables.

**Fix.**

1. In firmware/BIOS, enable Thunderbolt pre-boot support. Prefer security level `dponly` (tunnels DisplayPort only, no PCIe/DMA) over `none` — `dponly` is enough to get a picture at the boot menu and keeps DMA protection. This is what makes the boot menu appear on the USB4 input.

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

4. If your controller powers itself down, force it on (Dell/Intel WMI only; the attribute is absent on machines that do not expose it):

```bash
echo 1 | sudo tee /sys/bus/wmi/devices/86CCFD48-205E-4A77-9C48-2021CBEDE341/force_power
```

**Verify.** Reboot with only the USB4 cable attached: the bootloader menu and then the Hyprland session both appear on that input, and `hyprctl monitors` shows the native mode.

Sources: <https://github.com/basecamp/omarchy/issues/374> · <https://wiki.archlinux.org/title/Thunderbolt> · <https://github.com/basecamp/omarchy/issues/7328>

---

## Fix monitors in the wrong order or with a dead gap between them

`monitor-positions-wrong-order-with-scaling` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Two monitors are in the wrong order — you move the mouse right and it lands on the left screen — or there is a dead gap you have to drag the pointer through, or Hyprland warns that monitors overlap. Setting `position = "3840x0"` for a screen next to a 4K display does not put it where you expect.

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

**Symptom.** I dock the laptop or plug in a second screen. Hyprland picks it up fine — windows move there, `hyprctl monitors` lists it — but the new display is just black behind the windows, and the top bar only draws on the original screen. hyprpaper's log says `Monitor DP-3 does not have a target! A wallpaper will not be created.` Killing and restarting hyprpaper and the bar fixes it until the next hotplug.

**Cause.** Wallpaper and bar daemons are ordinary Wayland clients, not part of the compositor. hyprpaper assigns a wallpaper per output at config-parse time; an output that did not exist then has no target, and hyprpaper logs exactly that message rather than falling back (hyprwm/hyprpaper #154, #110). The wiki is explicit that the empty-monitor entry is a *fallback* and "only applies to monitors that have never had a specific monitor target assigned" — so if you have only named entries, a new connector gets nothing. Status bars behave the same way: many only enumerate outputs at startup, so a display that appears later gets no layer surface until the bar is restarted.

> **Audit corrected this record.** The hyprpaper half is accurate: the wiki documents `monitor` "If empty, will use this wallpaper as a fallback", the `fit_mode` values, `hyprctl hyprpaper wallpaper '[mon], [path], [fit_mode]'`, `listactive` with output matching the record's sample, and the exact sentence "The fallback wallpaper only applies to monitors that have never had a specific monitor target assigned." hyprpaper #154's title is literally the quoted warning. The socat/IPC listener and `o.launch_on_start` are correct, and `omarchy-restart-shell` exists and behaves as described (kills every quickshell instance for the config dir, then relaunches via `hyprctl dispatch 'hl.dsp.exec_cmd("omarchy-launch-shell")'` so it inherits the session environment). Two problems. (1) The record is tagged `omarchy-4` and leads with editing `~/.config/hypr/hyprpaper.conf`, but Omarchy 4 does not ship or use hyprpaper at all — there is not one reference to it anywhere in the quattro tree, the background/bar/lock surfaces are all the Quickshell Omarchy shell, and `omarchy-upgrade-to-quattro` removes hypridle-era packages. An Omarchy 4 user will edit a file nothing reads and conclude the record is broken. (2) The closing claim that an `Invalid config line at line N` parse failure is documented in hyprpaper #154 is not supported — that issue is a user on pre-1.0 `wallpaper = mon,path` syntax, closed not_planned with "update hyprlang and hyprpaper", and never mentions a parse-failure line.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Split the record by platform up front, because the two cases share a symptom and nothing else.

**On Omarchy 4 (Quattro) — hyprpaper is not installed and `hyprpaper.conf` is not read.** The wallpaper, bar and lock surface are all the Quickshell-based Omarchy shell. A display that appears after the shell started and gets no background or bar is fixed with one command:

```bash
omarchy-restart-shell
```

It kills every running instance for the shell config dir and relaunches it from inside the Hyprland session so it inherits the correct environment. It refuses to run while the session is genuinely locked, which is the intended guard. Confirm the outputs the compositor is offering it:

```bash
hyprctl monitors all -j | jq -r '.[] | "\(.name)\tdisabled=\(.disabled)"'
```

Do not create `~/.config/hypr/hyprpaper.conf` on Omarchy 4 — nothing will read it.

**On bare Hyprland / Arch with hyprpaper**, the rest of the record is correct as written: add a `wallpaper { monitor = ... }` catch-all block with an empty `monitor`, reload with `pkill hyprpaper; hyprpaper & disown` or `systemctl --user restart hyprpaper.service`, set a live output with `hyprctl hyprpaper wallpaper 'DP-3, /home/you/Pictures/wall.jpg, cover'`, verify with `hyprctl hyprpaper listactive`, and autostart the socat `monitoradded` listener. Restart Waybar with `pkill waybar; waybar & disown` or `systemctl --user restart waybar.service`.

**Drop the #154 attribution on the parse-failure paragraph.** The advice itself is still worth keeping — run hyprpaper in the foreground and read the first lines, because a config that fails to parse leaves every output without a target:

```bash
pkill hyprpaper; hyprpaper 2>&1 | head -20
```

Just don't cite #154 for it; that issue is a user on the pre-1.0 `wallpaper = monitor,path` syntax, and the answer there was to update hyprpaper and hyprlang.

**Verify.** `hyprctl hyprpaper listactive` lists every name from `hyprctl monitors -j | jq -r '.[].name'`. The bar should be visible on the new display without a Hyprland restart.

Sources: <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Hypr%20Ecosystem/hyprpaper.md> · <https://wiki.hypr.land/Hypr-Ecosystem/hyprpaper/> · <https://github.com/hyprwm/hyprpaper/issues/154> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/IPC/_index.md> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-restart-shell>

---

## Fix a cursor that changes size between mixed-DPI monitors

`cursor-wrong-size-on-scaled-or-mixed-monitors` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** The mouse cursor is a tiny speck on the 4K screen and a giant arrow on the 1080p one, or it changes size the moment it crosses between monitors. Sometimes the cursor is completely invisible over XWayland windows or in a VM.

**Cause.** XCursor themes are bitmaps at fixed sizes; a single `XCURSOR_SIZE` cannot be right on two displays with different scales. Omarchy ships `XCURSOR_SIZE=24` and `HYPRCURSOR_SIZE=24` in `/usr/share/omarchy/default/hypr/envs.lua`. Invisible cursors are usually a hardware-cursor plane the driver cannot commit (vmwgfx, some virtual GPUs).

**Fix.**

Set both sizes together — they must agree, or the cursor changes size between Wayland-native and XWayland surfaces. In `~/.config/hypr/looknfeel.lua` (or your own Hyprland config):

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

On NVIDIA, hardware cursors need `cursor.use_cpu_buffer` (default `2` = auto-on for NVIDIA) — set it to `1` if the cursor is corrupt.

Log out and back in for the env change to reach already-running apps.

**Verify.** The cursor is the same apparent physical size on both monitors and stays visible over XWayland windows.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Advanced%20and%20Cool/XWayland.md> · <https://github.com/basecamp/omarchy/issues/7918>

---

## Fix Firefox rendering blurry or double-scaled on a fractional scale

`firefox-blurry-or-double-scaled-wayland` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Firefox is fuzzy on a fractionally scaled display, or is enormous — set the screen to 150% and Firefox renders at 200% then gets shrunk back down, so every glyph looks smeared.

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

Restart Firefox. Do not also set `Xft.dpi` — setting it alongside a toolkit scale makes Firefox's UI much larger than intended.

**Verify.** `about:support` -> Graphics shows `Window Protocol: wayland`, and page text is sharp at your chosen scale.

Sources: <https://wiki.archlinux.org/title/HiDPI> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua>

---

## 144 Hz screen animates like 60 Hz once a 60 Hz monitor is plugged in

`mixed-refresh-rate-monitors-animation-judder` · severity: **low** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** On its own my 144/165/180 Hz monitor is buttery. The moment I plug in the second 60 Hz screen, window animations and workspace switches judder on both — it feels like the whole desktop dropped to the slower panel's rate. Unplugging the 60 Hz display makes it smooth again. Sometimes the fast monitor's own `hyprctl monitors` output still says `@144.00` while it visibly stutters.

**Cause.** Until late 2025, Hyprland scheduled *all* animations from a single monitor — an internal `m_mostHzMonitor` — rather than from each output's own refresh rate, so a mixed-rate setup animated everything on one shared clock. That was removed in hyprwm/Hyprland PR #12418 ("animation: improvement animation on multi refresh rate monitors"), merged 23 Nov 2025: *"I removed the logic that referenced m_mostHzMonitor for animation scheduling and switched to using each monitor's own refresh rate."* If you are on a build older than that, the judder is the bug itself. On current builds the residual causes are almost always local: `debug:vfr` turned off (which is a developer-only knob that forces a fixed render loop), VRR set to always-on so the refresh rate flaps on every cursor move, hardware-cursor plane bugs across differently-transformed/refreshed outputs, or the fast monitor having silently negotiated down to 60 Hz because of cable/bandwidth limits.

> **Audit corrected this record.** The upstream research is excellent and checks out exactly: PR #12418 is real, merged 2025-11-23, and the quoted body ("I removed the logic that referenced m_mostHzMonitor for animation scheduling and switched to using each monitor's own refresh rate.") is verbatim. `debug:vfr` defaults to `true` with the wiki's "Heavily recommended to leave enabled to conserve resources", `misc:vrr` has exactly the documented 0/1/2/3 modes, `cursor:no_hardware_cursors` is 0/1/2 as described, `render:new_render_scheduling` is the triple-buffering option, and per-monitor `vrr` is a real `hl.monitor` field. Discussion #10969 genuinely confirms `no_hardware_cursors = 1` as the working workaround for rotated/multi-monitor cursor artefacts, with multiple users confirming and one posting it in `hl.config` form. Omarchy's ALPM guard is real (`default/libalpm/hooks/00-omarchy-update-guard.hook` + `bin/omarchy-update-pacman-guard`, which aborts when it sees sync and sysupgrade together), so `omarchy update` is right. Two defects. (1) Four of the six fix steps use `hl.set("category:option", value)`, which is not a real API — the Variables page documents only `hl.config({ category = { option = ... } })`, and `hl.set` appears nowhere in the wiki or in Omarchy's quattro tree. Steps 3, 4, 5 and 6 all fail on paste and take the whole config file down with them. (2) The version floor is wrong in a way that matters: the record says "Hyprland 0.54+" but then hands the reader Lua config, and Lua only exists from 0.55 (0.54.x is hyprlang). v0.54.0 shipped 2026-02-27 so it does contain PR #12418, but a 0.54 user following this record writes Lua into a hyprlang parser.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `debug:*` options are documented "Only for developers" — do not leave `debug:vfr = false` in a config permanently; it burns power and defeats per-output scheduling. `cursor:no_hardware_cursors = 1` moves the cursor into the composited frame, which costs a little latency and GPU time on every output.

**Fix.**

Steps 1, 2 and the `hl.monitor` snippets are correct as written. Fix the version floor and replace every `hl.set` with the documented `hl.config` form.

**1. Update first.** The floor for the animation fix is a build newer than 2025-11-23 (v0.54.0+), but everything below is Lua config, which requires **0.55+**:

```bash
hyprctl version   # need 0.55 or newer for the Lua config shown here
```

On Omarchy 4 use `omarchy update` (a direct `pacman -Syu` is aborted by the ALPM guard); elsewhere `sudo pacman -Syu`.

**2.** Unchanged — check the *reported* mode with `hyprctl monitors -j | jq ...` and pin the mode with `hl.monitor({...})` if the fast panel negotiated down.

**3-6. The option settings.** All four go in one call in `~/.config/hypr/looknfeel.lua`:

```lua
hl.config({
  debug  = { vfr = true },                  -- default true; "heavily recommended to leave enabled"
  misc   = { vrr = 2 },                     -- 0 off, 1 on, 2 fullscreen only, 3 fullscreen video/game
  cursor = { no_hardware_cursors = 1 },     -- 0 hw if possible, 1 never, 2 auto
  render = { new_render_scheduling = true },-- triple buffering on weaker GPUs
})
```

Apply them one at a time rather than all at once, so you learn which one actually mattered — `hyprctl eval` takes the same Lua and does not touch your files:

```bash
hyprctl eval 'hl.config({ cursor = { no_hardware_cursors = 1 } })'
```

The per-monitor `vrr` variant in the record is correct and is the better option if only one display should get VRR:

```lua
hl.monitor({ output = "DP-1", mode = "2560x1440@165", position = "0x0", scale = 1, vrr = 2 })
hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "2560x0", scale = 1, vrr = 0 })
```

Then `hyprctl reload`.

**Verify.** With both monitors connected, drag a window or switch workspaces on the fast display — it should be smooth while the 60 Hz screen animates at its own rate. `hyprctl monitors -j | jq -r '.[] | "\(.name) @\(.refreshRate)"'` should show the two different rates steadily, not one of them oscillating.

Sources: <https://github.com/hyprwm/Hyprland/pull/12418> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Variables.md> · <https://github.com/hyprwm/Hyprland/discussions/10969> · <https://github.com/hyprwm/Hyprland/issues/9029> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md>

---

## Allow tearing in games without tearing the desktop

`screen-tearing-in-games-not-enabled` · severity: **low** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Either the opposite complaints: a game feels laggy because it is vsynced and `allow_tearing` seems to do nothing, or the desktop tears randomly after every reboot and after every lock/unlock cycle on an AMD card over DP 1.4 DSC.

**Cause.** Tearing in Hyprland is opt-in per window and only takes effect when the game is fullscreen and is the *only* thing on that monitor — a notification, bar, overlay or lockscreen on the same output silently disables it. Conversely, unwanted desktop tearing on AMD DSC links is usually a modeset/driver state issue that clears when something forces a re-modeset (users report the hyprsunset restart in Omarchy's update flow doing exactly that).

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

The window must be fullscreen with nothing else drawn on that monitor. If the app freezes instead of tearing, your GPU driver does not support it — turn `allow_tearing` back off.

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

## TV over HDMI crops the edges of the desktop (overscan) and Wayland has no underscan setting

`tv-overscan-edges-cut-off-over-hdmi` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Hooked the machine to a TV over HDMI and the top bar is half off-screen, the bottom of windows is cut away, and roughly 3-5% of every edge is missing. The TV is at the correct 1920x1080, `hyprctl monitors` looks right, and everything is fine on a normal monitor. There is no underscan or overscan slider anywhere in Hyprland or in the Omarchy display panel.

**Cause.** The TV is applying legacy CRT overscan: it crops the incoming frame and zooms the remainder to fill the panel. Nothing on the computer side is wrong. Under X11 you could compensate with the display's border/underscan property, but there is no Wayland protocol for output margins — hyprwm/Hyprland issue #277 ("Underscan/Overscan Support") is closed as *not planned*, and the same gap is documented for other compositors (labwc #2049: *"I have yet to find a way of doing it under Wayland"*, and the only workaround there is shrinking the panel and background, which still lets the pointer leave the visible area).

**Fix.**

**1. Turn overscan off on the TV — this is the actual fix.** The setting is in the TV's picture menu and is named differently per brand:

- Samsung: *Picture → Picture Size Settings → Picture Size → **Screen Fit*** (and set *Fit to Screen* on)
- LG: *Picture → Aspect Ratio → **Just Scan*** (or *Original*)
- Sony: *Screen → Display Area → **Full Pixel***
- Panasonic / Philips / TCL: *Aspect → **1:1 Pixel Mapping*** / *Unscaled* / *Dot by Dot*

If the option is greyed out, rename the HDMI input to **PC** (Samsung/LG both unlock 1:1 mapping and 4:4:4 chroma only on an input labelled PC). On many sets this single change fixes it permanently.

**2. If the TV genuinely has no such setting, keep your UI out of the cropped strip.** Hyprland's `reserved_area` field reserves pixels that tiled windows will not occupy — it does not shrink the output, but it stops the bar and window content from landing in the cut-off band. In `~/.config/hypr/monitors.lua`:

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

Measure the real crop first — put a window at each edge and count the missing pixels, or run a
fullscreen image with a 1px border and see how much is gone. Note the wiki's constraint:
*"This stacks on top of the calculated reserved area (e.g. bars), but you may only use one of
these rules per monitor in the config."* So one `reserved_area` per monitor, and your bar's own
reservation is added on top of it.

**3. Long shot, only if the above fails.** The kernel's modedb accepts margin options on the video= command line, documented on Arch's KMS page for exactly this case (*"typically to deal with overscan on TVs"*):

```
video=HDMI-A-1:1920x1080@60,margin_top=24,margin_bottom=24,margin_left=40,margin_right=40
```

Reports of this taking effect under a Wayland compositor are thin — treat it as something to
try, not something to rely on, and set the TV correctly if you possibly can.

**Do not** "fix" this by setting a smaller custom mode (e.g. 1776x1000 into a 1080p TV). The TV
will upscale *and* still crop, giving you a soft picture with the edges still missing.

**Verify.** Open a terminal and maximise it: all four borders should be visible. `hyprctl monitors -j | jq -r '.[] | "\(.name) \(.reserved)"'` shows the reserved band on the TV output.

Sources: <https://github.com/hyprwm/Hyprland/issues/277> · <https://github.com/labwc/labwc/issues/2049> · <https://raw.githubusercontent.com/hyprwm/hyprland-wiki/main/content/Configuring/Basics/Monitors.md> · <https://wiki.archlinux.org/rest.php/v1/page/Kernel_mode_setting> · <https://wiki.hypr.land/Configuring/Basics/Monitors/>

---
