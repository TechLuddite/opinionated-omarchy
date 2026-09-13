# Omarchy theming & bar

41 problems. Sorted by severity, then by how often users hit it.

## Stop the whole desktop hard-freezing when the Walker launcher renders

`walker-gtk4-vulkan-renderer-amdgpu-hard-freeze` · severity: **critical** · frequency: **rare** · applies to: `amd`, `desktop`, `hyprland`, `omarchy`, `omarchy-3`, `wayland`

**Symptom.** The entire desktop freezes. The display is frozen and keyboard and mouse are dead, but audio keeps playing, because PipeWire never touches the GPU. Only a hard reset recovers. `journalctl -k` from the previous boot shows `BUG: kernel NULL pointer dereference` at `RIP: ttm_lru_bulk_move_pos_tail+0x4f/0xb0 [ttm]` with `Comm: walker`, preceded by `WARNING: drivers/gpu/drm/ttm/ttm_resource.c:235 at ttm_resource_add_bulk_move`, then `watchdog: BUG: soft lockup - CPU#16 stuck for 495s! [kworker/u97:3]` inside `amdgpu_dm_atomic_commit_tail`.

This is an Omarchy 3 failure on AMD graphics. Omarchy 4 (Quattro) does not ship Walker, so the Omarchy-specific trigger is gone there. The kernel and GTK4 halves still apply to any GTK4 application on amdgpu, so the same oops can appear with a different `Comm:`.

**Cause.** On Omarchy 3 the `GSK_RENDERER=cairo` workaround is applied only inside `bin/omarchy-launch-walker`, and only in a branch that does not normally run. The resident `walker --gapplication-service` process is started by the XDG autostart entry `~/.config/autostart/walker.desktop`, whose `Exec=walker --gapplication-service` carries no environment override. `systemd-xdg-autostart-generator` turns that entry into `app-walker@autostart.service` and starts it at session start, before any keybind is pressed, so the guard `if ! pgrep -f "walker --gapplication-service"` in the launch script is dead code and the variable is never applied.

Walker therefore runs with GTK4's default renderer. On Wayland that is the Vulkan renderer: `gsk_renderer_new_for_surface_full` walks the display override, then `GSK_RENDERER`, then the backend, then Vulkan, and only then the OpenGL renderer, and Arch's gtk4 is built against `vulkan-icd-loader`. On amdgpu, Walker page-faults on a GEM buffer, the kernel takes a NULL dereference inside TTM while holding the LRU spinlock, and every subsequent display atomic commit deadlocks on that lock, which is why input dies while audio survives. The underlying defect is kernel-side TTM and amdgpu. The missing environment variable is what exposes it.

The workaround used to be session-wide in Omarchy 3's `default/hypr/envs.conf` and was narrowed to the launcher, which is how the gap opened. Omarchy 4 ships neither Walker nor that file. Its Hyprland config is Lua and its session environment comes from `/usr/share/uwsm/env.d/10-omarchy`.

> **Audit corrected this record.** Verified against upstream that the Omarchy 3 mechanism this record describes is accurate. `bin/omarchy-launch-walker` on the `master` branch of `omacom/omarchy` sets `GSK_RENDERER=cairo` only inside the `if ! pgrep -f "walker --gapplication-service"` branch, `default/walker/walker.desktop` carries a bare `Exec=walker --gapplication-service` with no override, and `bin/omarchy-restart-walker` restarts `app-walker@autostart.service`, which confirms the generated unit name the record uses. The cited issue 6443 exists, is titled exactly as the record's cause describes, and its body supports every step of the chain including the `30ddfeda` commit that moved the variable out of `default/hypr/envs.conf`, so the source audit was right. The record's failure is that it was filed as an Omarchy record when it is an Omarchy 3 record. On this Omarchy 4.0.2-1 workstation `pacman -Q walker` fails, `pacman -Ql omarchy` lists no walker path, `/usr/share/omarchy/bin` contains no `omarchy-launch-walker` or `omarchy-refresh-walker`, `~/.config/autostart/` holds only `limine-snapper-notify.desktop`, `org.fcitx.Fcitx5.desktop` and `print-applet.desktop`, and the `quattro` tree contains no path matching walker. dhh closed issue 6443 with "Walker is gone on quattro." I did not reject it because the kernel and GTK4 halves are unchanged and the same oops can hit another GTK4 application on amdgpu, and because Walker is still installable from the AUR at 2.17.0-1. The second real defect is the fix's fallback: `~/.config/hypr/envs.conf` with `env = GSK_RENDERER,cairo` is hyprlang syntax, that file does not exist on Omarchy 4, and Omarchy 4's Hyprland config is Lua using `hl.env`, so the record as written pointed an Omarchy 4 reader at a file nothing reads. I read `/usr/share/uwsm/env.d/10-omarchy`, which names `~/.config/uwsm/env.d/*` as the preferred user override, and `/usr/share/doc/uwsm/README.md` lines 112 and 634 to 654, which confirm uwsm sources `uwsm/env.d/*` from each config dir and that `~/.profile` is only sourced when the session did not start through `uwsm start`. `~/.config/environment.d/` is also live on this box, holding a working `omarchy-firefox-wayland.conf`. On the GTK claim, I read `gsk/gskrenderer.c` at tag 4.22.4: `get_renderer_for_name` still accepts `cairo` at line 496, and the `renderer_possibilities` table still tries Vulkan before the OpenGL renderer on Wayland, so the record's "default Vulkan" claim holds, but its "Vulkan/ngl" phrasing is stale, because line 501 now warns "The new GL renderer has been renamed to gl" and the help text records that the old GL renderer was removed in GTK 4.18. Arch's gtk4 1:4.22.4-1 depends on `vulkan-icd-loader` and `libgtk-4.so.1` links `libvulkan.so.1`, so Vulkan is genuinely compiled in here. I lowered frequency from `occasional` to `rare` because the distribution no longer ships the trigger, and kept severity `critical` because an unrecoverable freeze is still the consequence for anyone affected. Not exercised: this workstation has an NVIDIA card, not amdgpu, so I could not reproduce the TTM oops or confirm whether kernel 7.1.9-arch1-2 still carries the underlying amdgpu defect, and I installed nothing.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Until this is applied, the failure mode is an unrecoverable freeze requiring a hard reset, which risks filesystem damage on btrfs or ext4 with unflushed writes. On Omarchy 3, `~/.config/autostart/walker.desktop` is rewritten by `bin/omarchy-refresh-walker`, by `install/config/walker-elephant.sh` and by migrations, so re-check the `Exec=` line after any `omarchy update`. `GSK_RENDERER=cairo` disables GPU acceleration for that application's rendering, so expect slower redraws and higher CPU use. Set it as narrowly as the problem allows rather than session-wide.

**Fix.**

**On Omarchy 3**, confirm the variable is genuinely absent from the running service:

```bash
pgrep -a walker
tr '\0' '\n' < /proc/$(pgrep -x walker)/environ | grep GSK_RENDERER
```

Force the Cairo renderer on the autostart entry:

```bash
sed -i 's|^Exec=walker --gapplication-service|Exec=env GSK_RENDERER=cairo walker --gapplication-service|' \
  ~/.config/autostart/walker.desktop
systemctl --user daemon-reload
systemctl --user restart app-walker@autostart.service
```

Or set it session-wide in `~/.config/hypr/envs.conf`, which is Omarchy 3's hyprlang config:

```conf
env = GSK_RENDERER,cairo
```

then log out and back in.

**On Omarchy 4 (Quattro)** neither Walker nor `~/.config/hypr/envs.conf` exists, so neither step above applies. If you need the Cairo renderer for some other GTK4 application that is oopsing on amdgpu, set it where Omarchy 4 actually reads session environment. `/usr/share/uwsm/env.d/10-omarchy` names `~/.config/uwsm/env.d/*` as the preferred user override, and uwsm sources those files as shell:

```bash
mkdir -p ~/.config/uwsm/env.d
echo 'export GSK_RENDERER=cairo' > ~/.config/uwsm/env.d/50-gsk-renderer
```

`~/.config/environment.d/*.conf` also reaches the systemd user manager and the graphical session:

```conf
GSK_RENDERER=cairo
```

Log out and back in for either file to take effect. Do not put it in `~/.profile`: uwsm sources a POSIX profile only when the session was not started through `uwsm start`, so on Omarchy 4 that path is unreliable and the variable may never reach the session.

To scope the change to one application rather than the whole session, wrap that application's `Exec=` line with `env GSK_RENDERER=cairo` instead.

Check the value you set is still accepted by your gtk4:

```bash
GSK_RENDERER=help gtk4-demo 2>&1 | head -20
```

`cairo` remains valid on gtk4 4.22.4. `ngl` does not: GTK renamed that renderer to `gl`, and `GSK_RENDERER=ngl` now logs `The new GL renderer has been renamed to gl` and selects the OpenGL renderer anyway.

**Verify.** On Omarchy 3, `tr '\0' '\n' < /proc/$(pgrep -x walker)/environ | grep GSK_RENDERER` prints `GSK_RENDERER=cairo`, and no new `Comm: walker` TTM oopses appear in `journalctl -k -b -1` over subsequent days.

On Omarchy 4, confirm the variable reached the session rather than only the shell:

```bash
systemctl --user show-environment | grep GSK_RENDERER
```

Then confirm the application picked it up, substituting its process name:

```bash
tr '\0' '\n' < /proc/$(pgrep -x <app>)/environ | grep GSK_RENDERER
```

Sources: <https://github.com/omacom/omarchy/issues/6443> · <https://github.com/omacom/omarchy/blob/master/bin/omarchy-launch-walker> · <https://gitlab.gnome.org/GNOME/gtk/-/raw/4.22.4/gsk/gskrenderer.c> · <https://aur.archlinux.org/packages/walker>

---

## Restore a top bar that vanished after an accidental Super+Shift+Space

`bar-missing-and-toggle-bar-on-hides-it` · severity: **high** · frequency: **common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** The top bar is completely gone, and it stays gone across reboots. `omarchy toggle bar on` seems to do nothing (or re-hides it). No `waybar` process exists, so it looks like the bar crashed. `hyprctl layers` still shows an `omarchy-bar` layer, but parked just above the screen at something like `xywh: 1920 -26 1920 26`.

**Cause.** `omarchy-toggle-bar` forwards the raw `on`/`off` argument straight through to the underlying `bar-off` flag without inverting it, so `omarchy toggle bar on` sets `bar-off=on` (bar hidden) and `omarchy toggle bar off` clears it (bar shown). The hidden state is persisted in `~/.local/state/omarchy/toggles/bar-off`, so it survives a reboot. `SUPER+SHIFT+SPACE` is bound to "Toggle top bar" directly beside the `SUPER+SPACE` launcher binding, which is how most people trigger it by accident. On Omarchy 4 there is no `waybar` process at all (Quickshell replaced it), which reinforces the wrong conclusion that the bar crashed.

**Fix.**

Confirm the bar is hidden rather than dead:

```bash
hyprctl layers | grep -A2 omarchy-bar     # layer exists, y is negative => hidden
omarchy toggle enabled bar-off; echo $?   # exit 0 => bar-off flag is set
```

Bring it back (note the inverted verb):

```bash
omarchy toggle bar off
```

Or just delete the persisted flag and restart the shell:

```bash
rm -f ~/.local/state/omarchy/toggles/bar-off
omarchy restart shell
```

The verbless form is not affected and does the right thing:

```bash
omarchy toggle bar
```

**Verify.** `omarchy toggle enabled bar-off` now exits 1, and `hyprctl layers` shows the `omarchy-bar` layer back at `y: 0` (e.g. `xywh: 1920 0 1920 26`). The bar is visible and survives a reboot.

Sources: <https://github.com/basecamp/omarchy/issues/7022>

---

## Recover the top bar after docking, a resolution change, or a lock that killed the shell

`bar-missing-or-wrong-after-monitor-hotplug` · severity: **high** · frequency: **common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** You dock the laptop or plug in a second monitor and the new display gets windows but no bar and no wallpaper — `hyprctl monitors` lists it fine, `hyprctl layers` shows nothing on it. Or after toggling bar transparency on and off, one monitor's bar text and icons stay washed out at about 70% opacity while the other monitor is correct. Or the machine idles, locks, and you come back to Hyprland's "it looks like you locked your screen but the lockscreen app died" wall — and after clearing it the bar is gone from every monitor, with `DEBUG: Not creating lock surface for screen QScreen(0x…, name="") as it is not backed by a valid wayland output` and `WARN: The Wayland connection experienced a fatal error: Invalid argument` as the last two lines the shell wrote.

**Cause.** On Omarchy 4 the bar is a Quickshell surface created per `QScreen`, not a per-monitor process. Screens are bound at shell start and on `wl_output` events, so an output that arrives late, is re-modeset by a dock, or briefly presents as a screen with an empty name (DPMS, lid close, monitor sleep) can end up with no bar surface. In the lock path that same empty-named screen is fatal: the shell correctly declines to create a lock surface for it and then the Wayland connection dies, taking `omarchy-shell` — and therefore every bar — with it, writing no crash report (issue #6684). Per-`Bar` state such as `useTransparentForeground` is also not re-derived after a transparency toggle, which strands one monitor's foreground at reduced opacity (issue #8024). There is no per-monitor bar restriction to configure around this: `bar.screens` is still an open feature request (issue #6501).

> **Audit corrected this record.** Cause and diagnostics are solid. Issue #6684 is titled "omarchy-shell exits when locking with a screen that has no valid Wayland output — bar disappears and the session is left on 'lockscreen app died'" and quotes both log lines the record quotes, including the no-crash-report detail. #6501 is an open PR adding `bar.screens`, so "still an open feature request" is right. Bar.qml carries useTransparentForeground and debugBarGeometry(), hyprlock is genuinely absent from install/omarchy-base.packages (only hyprland, hyprland-guiutils, hyprland-preview-share-picker, hyprpicker, hyprsunset, xdg-desktop-portal-hyprland), and shell/plugins/lock/manifest.json declares id "omarchy.lock" — so the killall -9 hyprlock remark is correct. `omarchy-shell shell ping` is real (omarchy-restart-shell polls exactly that), so the watchdog unit is sound, and it cannot fight a live lock because omarchy-restart-shell refuses while a locker reports secure. The defect: `hyprctl --instance 0 eval 'hl.clear_crashed_lockscreen()'` names a function that does not exist. It appears nowhere in the Omarchy tree, nowhere in the Hyprland Lua config docs, and searches turn up only the documented recovery (misc:allow_session_lock_restore plus relaunching a lock client). Omarchy already sets `allow_session_lock_restore = true` in default/hypr/looknfeel.lua and bin/omarchy-restart-shell implements the whole recovery itself: omarchy-hyprland-session-locked detects LOCK in solitaryBlockedBy, and when no live locker answers it restarts the shell and re-locks so you can authenticate out.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `hl.clear_crashed_lockscreen()` unlocks the session **without a password**. Only run it at the physical machine, and lock again (`omarchy system lock`) immediately afterwards. The watchdog timer above deliberately does not clear a crashed lock, only restart the shell — do not extend it to call `clear_crashed_lockscreen`, or an idle machine will unlock itself. `omarchy restart shell` refuses to run while the session is genuinely locked, which is intended.

**Fix.**

Drop the `hl.clear_crashed_lockscreen()` line — there is no such function. From a TTY (Ctrl+Alt+F2) or over SSH as the session user, the shell restart IS the recovery:

```bash
omarchy-hyprland-session-locked; echo "locked=$?"   # 0 = compositor holds a session lock
omarchy restart shell                                # restarts and re-secures the lock so you can authenticate
```

It prints "Refusing to restart Omarchy shell while the session is locked." only when a live locker reports the lock secure — in the dead-locker case it proceeds, relocks, and exits 0 (or tells you the lock was not re-secured). If the compositor was started without it, make sure lock restore is permitted first (Omarchy sets this by default in default/hypr/looknfeel.lua):

```bash
hyprctl keyword misc:allow_session_lock_restore 1
```

Everything else in the record — the geometry/journal probes, `hyprctl reload` before the shell restart after a dock, and the watchdog timer — is correct as written.

**Verify.** `hyprctl layers | grep -c omarchy-bar` equals the number of enabled monitors, and `omarchy-shell shell debugBarGeometry` reports non-zero geometry with `'visible': True` for each. Unplug and replug the external display — the bar comes back on it on its own.

Sources: <https://github.com/basecamp/omarchy/issues/6684> · <https://github.com/basecamp/omarchy/issues/8024> · <https://github.com/basecamp/omarchy/issues/6501> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-restart-shell>

---

## Bring Waybar back after it silently dies and stays dead

`waybar-crashes-and-never-restarts-uwsm-scope` · severity: **high** · frequency: **common** · applies to: `arch`, `desktop`, `hyprland`, `laptop`, `omarchy`, `omarchy-3`, `wayland`

**Symptom.** On Omarchy 3.x the Waybar top bar disappears mid-session and never comes back on its own. `coredumpctl` shows `Signal: 11 (SEGV)` for `app-Hyprland-waybar-<hash>.scope` with the stack in `/usr/lib/libglib-2.0.so.0.8800.1 (deleted)`, or SIGABRT with `raise -> abort -> std::terminate -> __cxa_throw`. Waybar logs also show `Gtk-CRITICAL: gtk_widget_set_accel_path: assertion 'GTK_IS_ACCEL_GROUP (accel_group)' failed`.

**Cause.** Two layers. First, Omarchy launches Waybar as a transient UWSM app scope (`exec-once = ! omarchy-toggle-enabled waybar-off && uwsm-app -- waybar` in `default/hypr/autostart.conf`, and `omarchy-restart-waybar` does `pkill -9 -x waybar; setsid uwsm-app -- waybar &`), not through the packaged `waybar.service` which carries `Restart=on-failure`. So one crash leaves the bar down permanently. Second, the crash itself: a long-running Waybar keeps mapping deleted GLib/GIO objects after `pacman -Syu` upgrades glib2 underneath it, and separately the battery/udev refresh worker throws an uncaught exception on machines with extra power-supply devices (Logitech HID batteries, USB-C PD) when the config does not pin a specific battery.

> **Audit corrected this record.** Problem and unit are real: Arch's waybar package ships /usr/lib/systemd/user/waybar.service, and upstream resources/waybar.service.in confirms ExecStart, `ExecReload=kill -SIGUSR2 $MAINPID` and `Restart=on-failure` exactly as claimed. But the fix is incomplete and order-dependent: `omarchy toggle waybar` is the VERBLESS toggle, so if the flag is already set it clears it (same inversion trap as the bar record); and enabling the unit without first killing the running transient uwsm scope leaves two waybars. Added explicit flag-setting, pkill, ordering, and a way to list real battery names.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `systemctl --user enable waybar.service` plus the `waybar-off` toggle changes who owns the Waybar lifecycle. If you later clear the `waybar-off` toggle without disabling the unit you get two Waybars stacked on top of each other.

**Fix.**

Immediate recovery:

```bash
omarchy restart waybar
```

Switch to the packaged supervised unit. Do this in order, or you end up with two bars:

```bash
# 1. Check the flag state first - do NOT blind-toggle
omarchy-toggle-enabled waybar-off && echo "already off" || echo "currently on"

# 2. Set it explicitly (omarchy toggle waybar with no verb would UNSET it if already set)
omarchy-toggle waybar-off on

# 3. Kill the transient uwsm-app scope that autostart.conf started
pkill -x waybar

# 4. Now enable + start the packaged unit
systemctl --user enable --now waybar.service
systemctl --user status waybar.service
```

Verified against upstream `resources/waybar.service.in` and the Arch package file list: the unit is `/usr/lib/systemd/user/waybar.service` with `ExecStart=/usr/bin/waybar`, `ExecReload=kill -SIGUSR2 $MAINPID`, `Restart=on-failure`, `WantedBy=graphical-session.target`. `Restart=on-failure` does cover death by SIGSEGV/SIGABRT.

Pin the battery in `~/.config/waybar/config.jsonc` - list the real names first rather than assuming BAT0:

```bash
ls /sys/class/power_supply/
```

```jsonc
"battery": { "bat": "BAT1" }
```

If you also see the GTK accel-group criticals, remove `"group/tray-expander"` from the `modules-right` array.

Apply config edits without a full restart:

```bash
systemctl --user reload waybar.service
```

Log out and back in after any `glib2` upgrade so Waybar is not left holding deleted mappings.

Omarchy 3.x only. Omarchy 4 replaced Waybar with Quickshell and has no waybar process at all.

**Verify.** `systemctl --user status waybar.service` shows `active (running)`. Kill it with `pkill -9 -x waybar` and the bar reappears within a second or two on its own. `coredumpctl list waybar` records no new dumps over the following days.

Sources: <https://github.com/basecamp/omarchy/issues/6159> · <https://github.com/basecamp/omarchy/issues/7508>

---

## Recover the bar after `omarchy plugin clone omarchy.bar` removes it entirely

`bar-plugin-clone-kills-the-bar` · severity: **high** · frequency: **occasional** · applies to: `amd`, `desktop`, `hyprland`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** You clone the built-in bar plugin to customize it and the bar disappears from every monitor — even with a byte-for-byte unmodified copy. `omarchy-plugin-list --json` reports the clone as `"enabled": true, "active": true`, but `hyprctl layers` shows no `omarchy-bar` surface anywhere. The shell log has `WARN scene: file:///home/<user>/.config/omarchy/plugins/<user>.bar/Bar.qml[15:3]: Required property omarchyPath was not initialized` (and the same for `barWidgetRegistry` and `barConfig`), followed by `WARN scene: @shell.qml[256:-1]: ReferenceError: errorString is not defined`.

**Cause.** `omarchy plugin clone` copies the QML but the clone is not wired to receive the required properties the shell injects into the built-in bar (`omarchyPath`, `barWidgetRegistry`, `barConfig`), so the component fails to instantiate and takes the bar down on all monitors. The `errorString` ReferenceError is a secondary bug in `shell.qml`'s own error-handling path that masks the real load error.

> **Audit corrected this record.** The commands are right - bin/omarchy-plugin-clone (`<source-id> [--edit]`) and bin/omarchy-plugin-remove (`[id] [--yes]`, with `--yes|-y` parsed explicitly) both exist with those exact signatures, and PLUGINS_DIR is ~/.config/omarchy/plugins. The shell.toml [bar] keys are valid and ~/.config/omarchy/shell.toml is a real layered override. But the shell.json snippet is actively harmful as written: `"layout": { "left": [], "center": [], "right": [] }` produces a completely blank bar, and manual/05-the-top-bar.md warns that once you own shell.json there is no deep merge with Omarchy's defaults - so pasting that is a second way to lose the bar. Omarchy ships first-class commands for exactly these cases, which the record omits.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `omarchy plugin remove <user>.bar --yes` deletes the cloned plugin directory including any edits you made to it. Copy `~/.config/omarchy/plugins/<user>.bar/Bar.qml` somewhere safe first if you want to keep your changes.

**Fix.**

Remove the clone to get the stock bar back immediately:

```bash
omarchy plugin remove <user>.bar --yes
omarchy restart shell
```

Check what happened first if you want the log:

```bash
omarchy-plugin-list --json
hyprctl layers | grep omarchy-bar
tail -50 /run/user/$UID/quickshell/by-id/*/log.qslog
```

**Do not paste a hand-written empty layout.** The original's `"layout": { "left": [], "center": [], "right": [] }` yields a completely blank bar - a second way to lose it. Layout entries are objects like `{"id": "omarchy.clock"}`, and once you own `shell.json` there is no deep merge with Omarchy's defaults, so new default widgets never appear. Use the supported commands instead:

```bash
omarchy bar defaults                 # restore the shipped layout
omarchy bar position top             # top | bottom | left | right
omarchy bar transparent toggle
omarchy bar move omarchy.clock --section center --index 0

omarchy plugin list                  # every widget id the shell knows
omarchy plugin enable omarchy.media --section center
omarchy plugin disable omarchy.weather
```

Sizing and typography live in `~/.config/omarchy/shell.toml`, which layers over the active theme:

```toml
[font]
base-size = 12

[bar]
size-horizontal = 32
scale-with-font = true
```

Only `scale-with-font`, `size-horizontal` and `size-vertical` are read from `[bar]` - every other key there is silently ignored. The shell watches the file, so no restart is normally needed; `omarchy restart shell` if in doubt.

There is still no per-monitor bar restriction in `shell.json` - that case has no workaround.

**Verify.** `hyprctl layers | grep omarchy-bar` shows a bar layer on each monitor and the bar is visible again. `omarchy-plugin-list --json` no longer lists `<user>.bar`.

Sources: <https://github.com/basecamp/omarchy/issues/6971>

---

## Make the SDDM login screen match the theme (and fix White's black-on-black greeter)

`sddm-greeter-not-following-theme-white-black-on-black` · severity: **high** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Every theme applies to the desktop but the login/logout screen is still Tokyo Night blue. On the White theme it is worse: after logging out you get what looks like a dead greeter — a black rectangle where the background, password field and lock glyph should be, with only the logo visible and the red "wrong password" assets showing on a failed attempt. `grep -m1 'color:' /usr/share/sddm/themes/omarchy/Main.qml` prints `color: "#000000"` even though the theme's `background` is `#ffffff`.

**Cause.** The SDDM greeter is not part of `omarchy theme set` at all — nothing in `post_theme_commands` touches it. It is written only by `bin/omarchy-plymouth-set` (what Style > Unlock runs), which pipes `$OMARCHY_PATH/default/sddm/omarchy/Main.qml` through two sed expressions on the same stream — `s/#1a1b26/#$bg_hex/g` then `s/#ffffff/#$text_hex/g` — into `/usr/share/sddm/themes/omarchy/Main.qml`. The shipped template contains no `#ffffff` of its own (all greeter text is images), so the second expression is dead code for every theme except one: for White, `bg_hex=ffffff`, so the first expression's own output is immediately rewritten to the foreground `#000000` (issue #7115, fix in #8469). The other half of the confusion is `omarchy-refresh-sddm`, which people reach for by name — it does `sudo rm -rf` on the theme directory and copies the package default back, so it restores the stock Tokyo Night greeter rather than applying your theme.

> **Audit corrected this record.** The mechanism is exactly right. bin/omarchy-plymouth-set pipes $OMARCHY_PATH/default/sddm/omarchy/Main.qml through `sed -e "s/#1a1b26/#$bg_hex/g" -e "s/#ffffff/#$text_hex/g"` into /usr/share/sddm/themes/omarchy/Main.qml; I fetched that template and it contains exactly one `#1a1b26` (line 8, `color: "#1a1b26"`, the root Rectangle) and zero `#ffffff`, so the second expression is dead for every theme except White — whose colors.toml is literally background="#ffffff", foreground="#000000", producing `color: "#000000"` on the first line grep -m1 finds. The failed-attempt assets really are recolored #f7768e, which is why only those and the logo stay visible. SDDM is absent from post_theme_commands, and omarchy-refresh-sddm really is `sudo rm -rf /usr/share/sddm/themes/omarchy` + copy of the package default. omarchy-plymouth-set-by-theme takes a theme name and gruvbox is a stock theme. Only defect: the closing line tells the reader to run `omarchy plymouth preview` bare. bin/omarchy-plymouth-preview requires four arguments (<background-hex> <text-hex> <logo.png> <output-path>) and exits 1 with a usage error otherwise; it does not derive preview-unlock.png from unlock.png on its own.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `omarchy-plymouth-set` runs `plymouth-set-default-theme omarchy` and then rebuilds the initramfs (`limine-mkinitcpio`, or `mkinitcpio -P`). Do not interrupt it — a truncated initramfs will not boot, and on an encrypted root you lose the LUKS prompt. `/usr/share/sddm/themes/omarchy` is package-owned, so `omarchy update` can restore it and silently undo the sed patch; re-check after an update. Never run `omarchy-refresh-sddm` expecting it to apply your theme — it deletes the themed greeter and copies the Tokyo Night default back.

**Fix.**

Keep every command as written, but replace the trailing sentence about generating the preview. A theme is listed under Style > Unlock when it ships preview-unlock.png (bin/omarchy-plymouth-list gates on that file alone); unlock.png is what omarchy-plymouth-set-by-theme then applies, so ship both. Generate the preview explicitly, since omarchy-plymouth-preview takes four arguments:

```bash
THEME=~/.config/omarchy/themes/<name>
omarchy-plymouth-preview \
  "$(omarchy-theme-color --file $THEME/colors.toml background)" \
  "$(omarchy-theme-color --file $THEME/colors.toml foreground)" \
  $THEME/unlock.png \
  $THEME/preview-unlock.png
```

Also worth noting for the reader: omarchy-plymouth-set-by-theme rebuilds the initramfs (mkinitcpio -P or limine-mkinitcpio) and needs imagemagick's `magick`, so it is not instant.

**Verify.** `grep -m1 'color:' /usr/share/sddm/themes/omarchy/Main.qml` shows your theme's `background` hex, not `#000000`. Log out (or `systemctl restart sddm` from a TTY) and the greeter background, password field and lock glyph are visible and match the desktop.

Sources: <https://github.com/basecamp/omarchy/issues/7115> · <https://github.com/basecamp/omarchy/issues/8469> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-plymouth-set> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-sddm> · <https://github.com/basecamp/omarchy/blob/quattro/manual/43-making-your-own-theme.md>

---

## Fix `omarchy theme set` or `omarchy update` hanging forever

`theme-set-hangs-with-brave-origin-running` · severity: **high** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy theme set <any-theme>` never returns. Or `omarchy update` hangs inside a migration, for example `1787481315` ("Re-stage the current theme so an installed theme's code is dropped"), never writes that migration's marker file, so every later `omarchy update` re-runs it and hangs again. `pgrep -af -- '--refresh-platform-policy'` shows a stray browser refresh, most often `/usr/bin/brave --refresh-platform-policy --no-startup-window`.

**Cause.** `omarchy-theme-set-browser` calls the browser refresh in the foreground with nothing bounding it. Confirmed unchanged in omarchy 4.0.2-1 and on the `quattro` branch, in `/usr/bin/omarchy-theme-set-browser`:

```bash
refresh_running_browser() {
  local process="$1"
  local command="$2"
  local pgrep_args="${3:--x}"

  if omarchy-cmd-present "$command" && pgrep $pgrep_args "$process" >/dev/null; then
    "$command" --refresh-platform-policy --no-startup-window &>/dev/null
  fi
}
```

`omarchy-theme-set` runs that script as one of its 14 `post_theme_commands` through `run_parallel`, whose `wait` has no timeout, so a refresh that does not return holds the theme change open forever.

There are two ways in. The first is a detection mix-up: the plain-Brave branch is guarded by `pgrep -x brave`, and brave-origin's processes are all named plain `brave`, so with brave-origin running and Brave not running the guard passes and the script launches the other binary, `/usr/bin/brave` from `brave-bin`. With `--no-startup-window` that instance has no window to close and never exits. The second is a refresh that is slow even when detection is right, which is not Brave-specific: a correctly detected Chromium was measured at 68 seconds.

`omarchy update` is caught because migration `1787481315` ("Re-stage the current theme so an installed theme's code is dropped") calls `omarchy-theme-refresh`, which calls `omarchy-theme-set`. `omarchy-migrate` writes a migration's marker only once the script exits, so a hung migration stays pending and every later `omarchy update` re-runs it. `omarchy-theme-set-keyboard-f16` fails the same way for a different reason: it calls `qmk_hid` with no bound and blocks on a QMK or VIA keyboard such as a Keychron K8 Pro.

> **Audit corrected this record.** Read `/usr/bin/omarchy-theme-set-browser`, `/usr/bin/omarchy-theme-set`, `/usr/bin/omarchy-theme-refresh`, `/usr/bin/omarchy-migrate`, `/usr/bin/omarchy-update` and `/usr/share/omarchy/migrations/1787481315.sh` on this workstation at omarchy 4.0.2-1, and fetched `bin/omarchy-theme-set-browser` from `omacom/omarchy` at `quattro`. The mechanism holds: `refresh_running_browser brave brave` still guards on `pgrep -x brave`, the refresh call is still in the foreground with no timeout, `run_parallel`'s `wait` still has none, and migration `1787481315` still calls `omarchy-theme-refresh`, so a hang there leaves the marker unwritten. Issue 8158 supports every claim in the record, including the `pgrep -x brave` false positive across brave-origin and the suggested `refresh_running_browser /opt/brave-bin/ brave -f`. Issue 8243 supports the Keychron K8 Pro hang in `omarchy-theme-set-keyboard-f16`, and I confirmed that script calls `qmk_hid` with no bound. Issue 8212, which the record did not use, adds that a correctly detected Chromium took 68 seconds and that a bound needs `timeout -k`, so the defect is wider than the Brave detection mix-up and the cause now says so. Three things were wrong or misleading and are rewritten. The `danger` claimed a Ctrl+C risks a partial upgrade, but `omarchy-update` runs `omarchy-migrate` after `omarchy-update-system-pkgs` has completed the `pacman -Syu` and no pacman hook calls the theme scripts, so at the hang point there is no transaction to interrupt. The recovery command `pkill -f 'brave --refresh-platform-policy --no-startup-window'` is unanchored and matches the command line of the shell it is typed in, which I confirmed here with `pgrep -af`, so it is replaced with an anchored `pgrep` and a kill by PID. Paths are moved to the installed 4.0.2-1 form, and the fix now notes that `/usr/share/omarchy/bin/omarchy-theme-set-browser` is a symlink to `/usr/bin/omarchy-theme-set-browser` and that `sed -i` on the symlink path would replace it. Not exercised: neither `brave-bin` nor `brave-origin-bin` is installed here, so the hanging refresh itself was never reproduced and that part rests on issue 8158. The basecamp URLs redirect but the repository is now `omacom/omarchy`, so the citations are moved to the canonical name.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A migration that hangs never records its marker, so that migration and every one behind it stay pending and re-run on the next `omarchy update`. `omarchy-update` runs `omarchy-migrate` after `omarchy-update-system-pkgs` has finished its `pacman -Syu`, so interrupting the hang does not risk a partial upgrade, but it does abandon the rest of the update: the `post-update` hook, AUR packages, mise, and the orphan prune. Kill the stray browser process and let the update continue rather than pressing Ctrl+C. Any edit to `/usr/bin/omarchy-theme-set-browser` is reverted by the next `omarchy update`, because that file is owned by the `omarchy` package.

**Fix.**

Find the stray refresh process and kill it by PID. Anchor the pattern at the start of the command line, because an unanchored `pkill -f` also matches the shell you typed it in and the terminal running the update:

```bash
pgrep -af -- '^/usr/bin/brave --refresh-platform-policy'
kill <pid>
```

Confirm the false positive:

```bash
pgrep -xc brave                    # non-zero
pgrep -af brave | grep -v origin   # nothing, so real Brave is NOT running
readlink -f /usr/bin/brave /usr/bin/brave-origin
```

Simplest permanent avoidance: quit brave-origin before a theme change or an update.

```bash
pkill -f -- '^/opt/brave-origin-bin/'
omarchy update
```

Or patch the guard to match on the binary path the way the brave-origin branch already does. The file to edit is `/usr/bin/omarchy-theme-set-browser`. `/usr/share/omarchy/bin/omarchy-theme-set-browser` is only a symlink to it, and `sed -i` on that path would replace the symlink with a regular file instead of patching the script:

```bash
sudo sed -i 's|^refresh_running_browser brave brave$|refresh_running_browser /opt/brave-bin/ brave -f|' \
  /usr/bin/omarchy-theme-set-browser
```

That fixes the detection mix-up and nothing else. To bound every browser refresh, including a correctly detected one that is merely slow, change the call inside `refresh_running_browser` to:

```bash
timeout -k 1 10 "$command" --refresh-platform-policy --no-startup-window &>/dev/null
```

The `-k` is what makes it a bound. Plain `timeout` sends SIGTERM and then waits for a child that ignores it. The policy is read at the browser's next launch anyway, so abandoning the live refresh costs nothing.

If the machine has a QMK or VIA keyboard such as a Keychron K8 Pro and the hang is in `omarchy-theme-set-keyboard-f16` instead, unplug the keyboard and retry.

**Verify.** `omarchy theme set tokyo-night` completes in a few seconds. `omarchy update` runs the pending migration through to completion and writes its marker, so a second `omarchy update` does not re-run it.

Sources: <https://github.com/omacom/omarchy/issues/8158> · <https://github.com/omacom/omarchy/issues/8212> · <https://github.com/omacom/omarchy/issues/8243>

---

## Fix the Walker launcher stuck on "Waiting for elephant"

`walker-waiting-for-elephant` · severity: **high** · frequency: **rare** · applies to: `hyprland`, `omarchy`, `omarchy-3`, `wayland`

**Symptom.** Pressing `SUPER + SPACE` opens the Walker launcher, but the search box shows the placeholder `Launch...` with a transparent list below it reading `Waiting for elephant...`. Nothing is searchable. A near variant is a launcher that opens and lists nothing at all, which means Elephant is running but has no provider installed. `coredumpctl` may show `Process <pid> (walker) of user 1000 dumped core` with a stack through `g_application_run` and `libglib-2.0`.

This is an Omarchy 3 symptom. Omarchy 3 shipped Walker and Elephant, Omarchy 4 (Quattro) does not install either package, and on Omarchy 4 `SUPER + SPACE` opens the Quickshell menu instead. An Omarchy 4 machine can only show this if Walker was installed from the AUR by hand.

**Cause.** Walker's backend indexer (`elephant`) is not running or has crashed, so Walker has nothing to query and leaves its placeholder row on screen. The string comes from Walker's own default theme, `resources/themes/default/layout.xml`, so it is Walker reporting the backend missing rather than Omarchy reporting anything. It happens intermittently after an update that restarts the two services at the wrong moment, and sometimes Walker itself segfaults inside its GLib main loop and takes the pairing down with it. A separate cause produces an empty list rather than the placeholder: Elephant's data providers are packaged separately from Elephant, so a running Elephant with no `elephant-desktopapplications` installed indexes nothing.

Omarchy 4 replaced the whole pairing with the native Quickshell launcher in `/usr/share/omarchy/shell`, and `SUPER + SPACE` is bound to `omarchy-menu toggle`. Neither `walker` nor `elephant` is installed and no `omarchy-restart-walker` exists. Walker and Elephant are still maintained upstream and are current in the AUR, so the failure remains reachable on Omarchy 4 for anyone who added them themselves.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2-1 workstation that Walker is not part of Omarchy 4 at all: `pacman -Q walker` and `pacman -Q elephant` both fail, `pacman -Ql omarchy` lists no walker or elephant path, and the only matches for either word under `/usr/share/omarchy` are unrelated English prose, a code comment about a TOML walker in `shell/Commons/Color.qml` line 173, a comment in `shell/plugins/agents/Panel.qml` line 415, and the elephant emoji in `shell/plugins/emojis/emojis.json`. `SUPER + SPACE` is bound to `omarchy-menu toggle` in `/usr/share/omarchy/default/hypr/bindings/utilities.lua` line 1, and `omarchy-restart-walker` is not among the 428 scripts in `/usr/share/omarchy/bin`. Against upstream, the `quattro` tree of `omacom/omarchy` contains no path matching walker or elephant, while the Omarchy 3 `master` tree contains `bin/omarchy-restart-walker`, `bin/omarchy-launch-walker`, `default/walker/`, `default/elephant/` and `install/config/walker-elephant.sh`, so this is an Omarchy 3 record that the corpus was presenting as an Omarchy record. The cited issue 2638 is real and does support the symptom, filed against Omarchy v3.1.1 with the exact placeholder text, and dhh closed it with "Closing because Quattro replaces Walker, Elephant, and the old menu surfaces with the native Omarchy shell launcher and menus." I did not reject the record because the problem is still reachable rather than impossible: `walker` 2.17.0-1 and `elephant` 2.22.0-1 are current in the AUR, upstream released both on 2026-07-16, and the string `Waiting for elephant...` still exists verbatim in the Walker v2.17.0 tarball at `resources/themes/default/layout.xml` line 64, so an Omarchy 4 user who installed Walker by hand can hit exactly this. One command in the old fix was wrong rather than merely stale: there is no `walker.service`, because the Walker v2.17.0 tarball ships no systemd unit and Omarchy 3's own `bin/omarchy-restart-walker` restarts `app-walker@autostart.service`, the unit generated from `walker.desktop`. Elephant does ship `assets/elephant.service`, so the elephant half of the old fix was correct. I confirmed `omarchy upgrade to quattro` is the right invocation from the `omarchy:examples` metadata line in `/usr/share/omarchy/bin/omarchy-upgrade-to-quattro`, so that command is kept unchanged, and I added the `elephant-desktopapplications` provider case that the issue thread reports as the fix for the empty-list variant. I lowered frequency from `common` to `rare` because the distribution no longer ships the component, leaving only users who added Walker themselves. Not exercised: I installed nothing and did not reproduce either failure, and `applies_to` still lists `omarchy` unqualified alongside `omarchy-3`, which should be narrowed by hand since the verdict schema has no field for it. I replaced the `basecamp/omarchy` issue URL with the canonical `omacom/omarchy` one, which is the same issue, because the search API does not follow the rename.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy upgrade to quattro` is a major version migration that rewrites config files and can clobber customizations — see the `shell-json-reset-by-quattro-upgrade` record before running it.

**Fix.**

First establish which Omarchy you are on, because the two cases have different fixes:

```bash
pacman -Q omarchy walker elephant
```

If `walker` and `elephant` both report `was not found`, skip to the Omarchy 4 section.

**On Omarchy 3**, restart the launcher and its backend:

```bash
omarchy-restart-walker
```

That script restarts `elephant.service` and `app-walker@autostart.service`. If it does not take, drive the two units directly. Note the Walker unit is `app-walker@autostart.service`, which `systemd-xdg-autostart-generator` derives from `~/.config/autostart/walker.desktop`. There is no `walker.service`:

```bash
systemctl --user restart elephant.service
systemctl --user restart app-walker@autostart.service
systemctl --user status elephant.service
```

Watch the failure live while reproducing it:

```bash
journalctl --user -f
# then press SUPER + SPACE
```

If the launcher opens but lists nothing instead of showing `Waiting for elephant...`, Elephant is running and has no provider. Providers are separate AUR packages:

```bash
yay -S elephant-desktopapplications
```

If it recurs constantly, check for crashes:

```bash
coredumpctl list walker
```

**On Omarchy 4 (Quattro)** there is nothing to restart. The launcher is the Quickshell shell in `/usr/share/omarchy/shell`, `SUPER + SPACE` runs `omarchy-menu toggle`, and no Walker or Elephant package is installed:

```bash
grep -rn 'SUPER + SPACE' /usr/share/omarchy/default/hypr/bindings/utilities.lua
```

If you see this symptom on Omarchy 4 you installed Walker from the AUR yourself and it is yours to manage. Elephant ships its own unit at `assets/elephant.service`, so `systemctl --user restart elephant.service` still applies, but Omarchy will not start Walker for you and `omarchy-restart-walker` does not exist.

**Migrating from Omarchy 3 removes the component entirely:**

```bash
omarchy upgrade to quattro
```

**Verify.** On Omarchy 3, `SUPER + SPACE` shows your applications immediately with no `Waiting for elephant...` line, `systemctl --user is-active elephant.service` prints `active`, and `systemctl --user is-active app-walker@autostart.service` prints `active`.

On Omarchy 4, `SUPER + SPACE` opens the Quickshell menu and `pacman -Q walker` reports `error: package 'walker' was not found`. That absence is the expected state, not a fault.

Sources: <https://github.com/omacom/omarchy/issues/2638> · <https://github.com/abenz1267/walker> · <https://aur.archlinux.org/packages/walker> · <https://aur.archlinux.org/packages/elephant> · <https://github.com/omacom/omarchy/blob/master/bin/omarchy-launch-walker>

---

## Make Nautilus and other GTK4/libadwaita apps follow the Omarchy theme

`gtk4-libadwaita-apps-ignore-omarchy-theme` · severity: **medium** · frequency: **very-common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Every theme applies to the terminal, bar, launcher and lock screen, but Nautilus and other GTK4/libadwaita apps keep stock Adwaita colours. Running `omarchy theme set gruvbox` and then `omarchy theme set tokyo-night` leaves the Nautilus window, header bar and sidebar the same grey both times. Two GTK-visible things do change on every theme set, so this is not "nothing happens": `omarchy-theme-set-gnome` writes `org.gnome.desktop.interface color-scheme` to `prefer-dark` or `prefer-light` from the theme's `mode`, sets `gtk-theme` to `Adwaita` or `Adwaita-dark`, and sets `icon-theme` from the theme's `icons.theme`. What never follows the theme is the palette.

**Cause.** Nothing in Omarchy writes a GTK palette. The only themed GTK CSS template in the whole tree is `/usr/share/omarchy/default/themed/hyprland-preview-share-picker.css.tpl`, for the Hyprland share picker, and no theme under `/usr/share/omarchy/themes/` ships a GTK file. What `omarchy-theme-set` does run is `omarchy-theme-set-gnome`, and that only flips `org.gnome.desktop.interface` between `color-scheme prefer-dark` with `gtk-theme Adwaita-dark` and the light pair, plus `icon-theme` from the theme's `icons.theme`. libadwaita ignores `gtk-theme` by design, so even the theme name is inert for these apps and only the light or dark preference lands.

The user-level lever that does work is the GTK user stylesheet, `~/.config/gtk-4.0/gtk.css`. GTK4 adds it at `GTK_STYLE_PROVIDER_PRIORITY_USER` and libadwaita registers its own stylesheet at `GTK_STYLE_PROVIDER_PRIORITY_THEME`, so rules in the user file win. On libadwaita 1.9.3 the documented way to override a colour is a CSS custom property on `:root`, for example `--window-bg-color`. The older `@define-color window_bg_color` form still works, because libadwaita's compiled stylesheet declares the legacy names and maps each one forward, but GTK deprecated `@define-color` in 4.16 in favour of custom properties, `:root` and `var()`.

Compounding it, GTK4 loads that file exactly once per process. `gtk_settings` builds a single static `GtkCssProvider`, calls `gtk_css_provider_load_from_path` on it if the file exists, and installs no file monitor. Apps that run as `--gapplication-service` daemons survive their last window closing, so they keep painting a days-old palette after you rewrite the CSS.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, gtk4 1:4.22.4-1, libadwaita 1:1.9.3-1, nautilus 50.2.2-1). Three claims held and three did not. Held, and confirmed on this machine: nothing in the Omarchy tree writes a GTK palette, because the only GTK CSS template under /usr/share/omarchy/default/themed is hyprland-preview-share-picker.css.tpl and no theme directory ships a GTK file. Held: the hook path is real, since omarchy-theme-set calls `omarchy-hook theme-set "$THEME_NAME"` and omarchy-hook runs every file in ~/.config/omarchy/hooks/theme-set.d/. Held, and confirmed from GTK source rather than locally: gtk_settings builds one static GtkCssProvider, calls gtk_css_provider_load_from_path on ~/.config/gtk-4.0/gtk.css and registers no file monitor, so the file is read once per process, and nautilus is D-Bus activated as `/usr/bin/nautilus --gapplication-service`. Wrong, confirmed on this machine: the symptom said no colour change at all, but /usr/share/omarchy/bin/omarchy-theme-set-gnome sets color-scheme, gtk-theme and icon-theme from the theme, and with the gruvbox theme active `gsettings get org.gnome.desktop.interface icon-theme` returns Yaru-olive, exactly the content of /usr/share/omarchy/themes/gruvbox/icons.theme, so light or dark and the icon set do follow the theme. Wrong, from sources: the cause called `@define-color` the only lever, but libadwaita 1.9.3 documents CSS custom properties on `:root` as the override mechanism, and GTK 4 documentation states that define-color is deprecated and that custom properties, the :root selector and var() should be used instead, supported since 4.16. The old form still works only because libadwaita's compiled stylesheet declares the legacy names and maps each one forward as `--window-bg-color: @window_bg_color`, which I read out of the installed /usr/lib/libadwaita-1.so.0. Wrong, from source: the GTK3 note blamed provider scoping, but gtk_style_cascade_get_color in both gtk-3-24 and gtk4 main walks providers from the highest priority down, and the user stylesheet sits at GTK_STYLE_PROVIDER_PRIORITY_USER above libadwaita's GTK_STYLE_PROVIDER_PRIORITY_THEME, so an override does reach the theme. The real obstacle is that GTK3's compiled Adwaita declares 163 named colours and then references only @theme_text_color five times and @selected_bg_color three times, counted in the installed /usr/lib/libgtk-3.so.0, so there is almost nothing for an override to reach. I also replaced the sed reader with omarchy-theme-color, the supported colors.toml reader that omarchy-theme-set-gnome and omarchy-theme-set-templates both use, and confirmed `omarchy-theme-color --file ~/.local/state/omarchy/current/theme/colors.toml background` returns #282828 here. Both cited issues were read in full and both support the record, although 7557 is an open feature request whose prose the record reproduced including the two errors above, and 8380 is a separate transparency report about a user's own broken hook. NOT exercised: I did not write gtk.css, install the hook, change the theme, restart any app or render anything, so the visual result of the corrected CSS is unverified on this machine and rests on the libadwaita documentation.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** The hook overwrites `~/.config/gtk-4.0/gtk.css` on every theme change. Omarchy itself never writes that file, so nothing but this hook will clobber it, but if you already hand-maintain it, back it up first or have the hook write a separate file and `@import` it. The hook also sends SIGTERM to GTK4 daemons. All of them are D-Bus activatable and respawn on demand, but an unsaved dialog in one of them is lost.

**Fix.**

Write the libadwaita overrides yourself and re-apply them on every theme change. Omarchy never writes `~/.config/gtk-4.0/gtk.css`, so nothing else competes for that file and nothing overwrites your copy except this hook.

```bash
mkdir -p ~/.config/omarchy/hooks/theme-set.d
cat > ~/.config/omarchy/hooks/theme-set.d/20-gtk4-colors.sh <<'EOF'
#!/bin/bash
set -uo pipefail

colors="$HOME/.local/state/omarchy/current/theme/colors.toml"
[[ -f $colors ]] || exit 0

# omarchy-theme-color is the supported reader for colors.toml. It resolves
# legacy colorN names and derived shades that a raw sed over the file misses.
bg=$(omarchy-theme-color --file "$colors" background || true)
fg=$(omarchy-theme-color --file "$colors" foreground || true)
[[ -n $bg && -n $fg ]] || exit 0

mkdir -p "$HOME/.config/gtk-4.0"
cat > "$HOME/.config/gtk-4.0/gtk.css" <<CSS
:root {
  --window-bg-color: $bg;
  --window-fg-color: $fg;
  --view-bg-color: $bg;
  --view-fg-color: $fg;
  --headerbar-bg-color: $bg;
  --headerbar-fg-color: $fg;
  --sidebar-bg-color: $bg;
  --sidebar-fg-color: $fg;
  --secondary-sidebar-bg-color: $bg;
  --secondary-sidebar-fg-color: $fg;
  --dialog-bg-color: $bg;
  --dialog-fg-color: $fg;
  --popover-bg-color: $bg;
  --popover-fg-color: $fg;
}
CSS

# GTK4 loads ~/.config/gtk-4.0/gtk.css once per process and sets up no file
# monitor on it, so a D-Bus activated daemon keeps painting the palette it
# started with. Every name below respawns on demand, so SIGTERM is safe.
pkill -f 'nautilus --gapplication-service' || true
pkill -x geary || true
pkill -x gnome-calendar || true
EOF
chmod +x ~/.config/omarchy/hooks/theme-set.d/20-gtk4-colors.sh
omarchy theme refresh
```

`omarchy-theme-set` calls `omarchy-hook theme-set "$THEME_NAME"` after it swaps the theme in, and `omarchy-hook` runs every file in `~/.config/omarchy/hooks/theme-set.d/`, so the hook fires on every `omarchy theme set`.

Two deliberate omissions. `--accent-bg-color` is left alone because libadwaita derives `--accent-color` from it in the Oklab space, and overriding one without the other gives you accent text with no contrast guarantee. `--card-bg-color` is left alone because Adwaita defines it as a translucent white overlay (`RGB(255 255 255 / 8%)` in the dark style), so pinning it to the opaque window background makes every card disappear into the window.

Omarchy 4 versus plain Arch:

- On Omarchy 4 the hook above is the mechanism, because `~/.config/omarchy/hooks/theme-set.d/` and `omarchy-theme-color` both exist and a theme change is what needs to trigger the rewrite.
- On plain Arch there is no theme-set event. Write the same `:root` block into `~/.config/gtk-4.0/gtk.css` once by hand and restart the affected apps.

Syntax note. `@define-color window_bg_color <hex>;` in the same file still works on libadwaita 1.9.3, because its compiled stylesheet still declares the old names and maps them forward with `--window-bg-color: @window_bg_color;`. It is the older form: GTK deprecated `@define-color` in 4.16 and its own documentation says to use custom properties, the `:root` selector and `var()` instead. Prefer the `:root` block.

GTK3 apps cannot be recoloured this way, but not for the reason usually given. A user `@define-color` does reach the theme: GTK3 and GTK4 both resolve a named colour by walking the style cascade from the highest priority provider down, and the user stylesheet sits at `GTK_STYLE_PROVIDER_PRIORITY_USER` above the theme. The real obstacle is that GTK3's compiled Adwaita declares 163 named colours and then almost never refers to them, so there is nothing for an override to reach. GTK3 apps still need an approximate binary theme selected through `gtk-theme`.

**Verify.** Check the file was written with real values and that the apps picked it up:

```bash
cat ~/.config/gtk-4.0/gtk.css
```

Every line must carry a six-digit hex value. An empty `#` or a bare `$bg` means `omarchy-theme-color` returned nothing and the guard did not catch it. Then run `omarchy theme set gruvbox`, open Nautilus, run `omarchy theme set tokyo-night`, open Nautilus again, and confirm the window background is visibly different between the two. Opening it twice matters because the daemon has to have been restarted in between.

Sources: <https://github.com/omacom/omarchy/issues/7557> · <https://github.com/omacom/omarchy/issues/8380> · <https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.9/css-variables.html> · <https://docs.gtk.org/gtk4/css-properties.html> · <https://wiki.archlinux.org/title/GTK> · <https://raw.githubusercontent.com/GNOME/gtk/main/gtk/gtksettings.c> · <https://raw.githubusercontent.com/GNOME/gtk/main/gtk/gtkstylecascade.c> · <https://raw.githubusercontent.com/GNOME/gtk/gtk-3-24/gtk/gtkstylecascade.c> · <https://raw.githubusercontent.com/GNOME/libadwaita/libadwaita-1-9/src/adw-style-manager.c>

---

## Fix "failed to parse rgb color {{ color8 }}" after creating a theme with Aether

`custom-theme-missing-color-keys-rgb-parse-error` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After building a custom theme in Aether, some apps break — the Wi-Fi panel and similar surfaces fail with an error like `failed to parse rgb color {{ color8 }}`. Alacritty is most affected. Stock themes work fine.

**Cause.** Omarchy renders per-app configs from templates in `default/themed/*.tpl` by pure sed substitution of `{{ key }}` placeholders out of the theme's `colors.toml`. Aether writes a `colors.toml` that does not define the full `color0`..`color15` ANSI palette, so any placeholder with no matching key is left in the output verbatim and the consuming app tries to parse the literal string `{{ color8 }}` as a color.

> **Audit corrected this record.** The mechanism is real - omarchy-theme-set-templates substitutes `{{ key }}` by building a sed script only from keys present in the theme, so any placeholder with no matching key survives verbatim into the generated config and the consuming app tries to parse it. But the prescribed fix is aimed at an outdated schema. docs/theming.md shows current colors.toml is semantic-first (accent, selection, muted, the background/foreground ramps, named colours), and explicitly states that `muted` 'also serves as ANSI color8' and that `accent` falls back to `color4`; legacy colorN names are still supported and resolved canonical values are re-exposed through them. So dumping a bare color0..color15 list can leave templates referencing {{ muted }}, {{ accent }} or {{ bright_foreground }} still unsubstituted. The verification grep and the copy-a-stock-theme advice are both correct and worth keeping.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The mechanism is real: `omarchy-theme-set-templates` substitutes `{{ key }}` via a sed script built only from keys your theme actually defines, so any placeholder with no matching key survives verbatim into the generated config.

But current Omarchy's `colors.toml` is **semantic-first**, not a raw ANSI list, so supply the canonical keys:

```bash
nvim ~/.config/omarchy/themes/<my-theme>/colors.toml
```

```toml
mode = "dark"

accent    = "#7aa2f7"
selection = "#292e42"
muted     = "#414868"     # also serves as ANSI color8

background         = "#1a1b26"
dark_background    = "#13141c"
darker_background  = "#0e0e14"
lighter_background = "#24283b"

foreground        = "#a9b1d6"
dark_foreground   = "#565f89"
light_foreground  = "#b4bee6"
bright_foreground = "#c0caf5"

red  = "#f7768e"
blue = "#7aa2f7"
```

Per `docs/theming.md`: `muted` also serves as ANSI `color8`, `accent` falls back to `color4` when absent, and `red`/`color1` populates the shell's urgent role. Legacy `colorN` names still work and adding `color0`..`color15` does no harm - but they alone will not satisfy templates that reference `{{ muted }}`, `{{ accent }}` or `{{ bright_foreground }}`, which is why the bare 16-colour list is not sufficient.

Re-apply and verify nothing was left unsubstituted:

```bash
omarchy theme set <my-theme>
grep -rn '{{' ~/.local/state/omarchy/current/theme/ || echo "all placeholders resolved"
```

The reliable way to start a theme is still to copy a stock one, which already has every key:

```bash
cp -a ~/.local/share/omarchy/themes/tokyo-night ~/.config/omarchy/themes/my-theme
```

**Verify.** `grep -rn '{{' ~/.local/state/omarchy/current/theme/` returns nothing, and the Wi-Fi panel and Alacritty open without the rgb parse error.

Sources: <https://github.com/basecamp/omarchy/issues/7317> · <https://learn.omacom.io/2/the-omarchy-manual/92/making-your-own-theme>

---

## Fix window border colors and rounding that never change with a community theme

`installed-theme-hyprland-lua-stripped-borders` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** You install a theme with `omarchy theme install <git-url>` and the bar, terminal and shell all retint, but the theme's own Hyprland look never arrives. Its rounding, shadow and blur are missing entirely, and the window border comes out as a flat version of the theme's `accent` colour instead of the gradient or the exact colour the author wrote. In the rarer case where the cloned theme ships no `colors.toml` and no `alacritty.toml` to derive one from, the borders instead stay on Omarchy's stock cyan-to-green gradient for every theme you switch to. Running the switch from a terminal instead of the menu prints `Ignored in /home/<user>/.config/omarchy/themes/<name>: hyprland.lua` and `A theme installed from a git repo cannot supply Lua, a terminal config, or vscode.json.` on stderr. From the Style > Theme menu you see nothing at all. `hyprctl getoption general:col.active_border` reports a single-stop gradient such as `gradient data: ff7daea3 0deg`, which is the accent rather than the border the theme author asked for.

**Cause.** `bin/omarchy-theme-set` treats any theme directory that contains a `.git` directory as "came from a stranger" (`theme_came_from_a_repo`) and refuses to stage anything that can run code. `is_denied_installed_file` drops every `*.lua` unconditionally, plus `alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf` and `vscode.json` (`INSTALLED_THEME_DENIED`) — Hyprland `require`s a theme's `hyprland.lua` and `gum_env.lua` at login, so that is deliberate policy, not a bug. What gets staged instead is generated from `default/themed/hyprland.lua.tpl`, which carries only `general.col.active_border` / `inactive_border` and the matching `group.col` keys, resolved from `hyprland_active_border` / `hyprland_inactive_border` in `colors.toml` with `accent` and `rgba(595959aa)` as fallbacks. Rounding, shadow and blur have no `colors.toml` channel at all, so a theme that expressed its identity in `hyprland.lua` half-works. The refusal is announced only on stderr, which the menu discards (issue #8393). Separately, even a correct `hyprland.lua` does not repaint until `omarchy-restart-hyprctl` (`hyprctl reload`) has run — it is one of the `post_theme_commands`, so a theme change that died partway leaves stale borders.

> **Audit corrected this record.** Re-audited on this workstation at omarchy 4.0.2-1, omarchy-settings 4.0.2-1, Hyprland 0.56.2-1, and against bin/omarchy-theme-set and default/themed/hyprland.lua.tpl on the quattro branch. The premise holds and is Lua, not hyprlang: 5 of the 22 themes in /usr/share/omarchy/themes (kanagawa, last-horizon, lumon, retro-82, solitude) ship a real `hyprland.lua` using `hl.config({ general = { col = { active_border = ... } } })`, default/hypr/omarchy.lua ends with `require_optional.module("omarchy.current.theme.hyprland")`, and default/hypr/envs.lua requires `omarchy.current.theme.gum_env`. The mechanism in the cause is correct line for line on the installed script: `INSTALLED_THEME_DENIED=(alacritty.toml foot.ini ghostty.conf kitty.conf vscode.json)`, `is_denied_installed_file` returns 0 for every `*.lua`, `theme_came_from_a_repo` is `[[ ! -L $source && -d $source/.git ]]`, `report_ignored_theme_files` emits the two quoted stderr lines byte for byte, and `omarchy-restart-hyprctl` is literally `hyprctl reload` and sits in `post_theme_commands`. The fix is correct and its paths are Omarchy 4, not Omarchy 3: `~/.config/hypr/looknfeel.lua` exists and ships as an all-comment file, `config/hypr/hyprland.lua` requires `hypr.looknfeel` after `default.hypr.omarchy`, `omarchy theme refresh` is a real subcommand that re-runs `omarchy-theme-set` with `OMARCHY_THEME_SKIP_BACKGROUND=1`, `omarchy-theme-color` accepts an arbitrary `hyprland_active_border` key whose value charset covers `rgba(33ccffee) rgba(00ff99ee) 45deg`, and docs/theming.md on quattro documents that exact TOML line and the `hypr_gradient` helper. The danger is right too: `omarchy-theme-extras` selects on `-d $theme/.git`, so removing `.git` really does drop the theme out of `omarchy theme update`. What was wrong is the symptom, and it is wrong in the common case rather than an edge case. The template resolves `hyprland_active_border` with `accent` as its fallback, so any cloned theme with a `colors.toml` does repaint the border. Confirmed live on this machine: the current theme is gruvbox, the staged /home/techluddite/.local/state/omarchy/current/theme/hyprland.lua reads `local active_border_color = "#7daea3"` which is gruvbox's accent, and `hyprctl getoption general:col.active_border` returns `gradient data: ff7daea3 0deg`, not the stock `rgba(33ccffee) rgba(00ff99ee) 45deg` the record quotes. The record also quotes hyprctl as printing rgba() notation, which it does not. Symptom and verify are rewritten for both points. Issue 8393 was read in full and supports the claim exactly, including that the menu discards stderr and that rounding, shadow and blur go missing. Issue 7884 is the merged change that introduced the policy and supports the cause. Not exercised: no theme was installed, set, removed or refreshed on this machine, and no cloned theme was staged, so the stderr lines and the `rm -rf .git` promotion path were read from the script rather than triggered.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting `.git` from a theme directory promotes the whole tree to a hand-written theme, so Omarchy stages **every** file the stranger's repo shipped — including `hyprland.lua` and `gum_env.lua`, which Hyprland executes at login, and `neovim.lua`, which Neovim executes at startup. A bad or hostile file there can leave you with a session that will not start. Read them before you do this, and note that it also breaks `omarchy theme update` for that theme, since there is no longer a repo to pull from.

**Fix.**

Confirm this is the refusal and not a broken theme — run the switch from a terminal so stderr survives:

```bash
omarchy-theme-set <name> 2>&1 | sed -n '/^Ignored in/,$p'
[[ -d ~/.config/omarchy/themes/<name>/.git ]] && echo "cloned theme: .lua is dropped by policy"
ls ~/.local/state/omarchy/current/theme/hyprland.lua
grep -n active_border_color ~/.local/state/omarchy/current/theme/hyprland.lua
```

If the borders are simply stale, reload the compositor:

```bash
omarchy-restart-hyprctl        # this is just: hyprctl reload
hyprctl getoption general:col.active_border
```

**The supported fix** is to express the borders through `colors.toml`, which a cloned theme *is* allowed to ship. Both a solid colour and a Hyprland gradient work in the same key:

```bash
nvim ~/.config/omarchy/themes/<name>/colors.toml
```

```toml
hyprland_active_border   = "rgba(33ccffee) rgba(00ff99ee) 45deg"
hyprland_inactive_border = "rgba(595959aa)"
```

```bash
omarchy theme refresh
```

Rounding, shadow and blur have no theme channel — put them in your own Hyprland config, which no theme ever overwrites:

```bash
cat >> ~/.config/hypr/looknfeel.lua <<'EOF'

hl.config({
  decoration = {
    rounding = 8,
    shadow = { enabled = true },
    blur = { enabled = true },
  },
})
EOF
hyprctl reload
```

To run the author's `hyprland.lua` as written, you must adopt the theme as your own by removing its git checkout — read the file first (see the risk note):

```bash
less ~/.config/omarchy/themes/<name>/hyprland.lua
less ~/.config/omarchy/themes/<name>/neovim.lua
rm -rf ~/.config/omarchy/themes/<name>/.git
omarchy theme set <name>
```

**Verify.** `grep active_border_color ~/.local/state/omarchy/current/theme/hyprland.lua` names the colour you put in `colors.toml` rather than the theme's bare `accent` or Omarchy's stock `rgba(33ccffee)`. `hyprctl getoption general:col.active_border` prints the stops as `gradient data: <aarrggbb> [<aarrggbb> ...] <n>deg` followed by `set: true`, so an accent of `#7daea3` reads back as `gradient data: ff7daea3 0deg` and a two-stop gradient reads back as two colour words and a non-zero angle. Switching between two themes visibly changes the focused window's border.

Sources: <https://github.com/basecamp/omarchy/issues/8393> · <https://github.com/basecamp/omarchy/issues/7884> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set> · <https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md> · <https://github.com/basecamp/omarchy/blob/quattro/manual/43-making-your-own-theme.md> · <https://github.com/omacom/omarchy/issues/8393> · <https://github.com/omacom/omarchy/issues/7884> · <https://github.com/omacom/omarchy/blob/quattro/default/themed/hyprland.lua.tpl> · <https://github.com/omacom/omarchy/blob/quattro/docs/theming.md>

---

## Fix a light theme that Omarchy insists is a dark one

`light-theme-detected-as-dark-gtk-apps` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** You build a light theme; the terminal, bar and shell all come up light, but GNOME/GTK apps (Nautilus, Text Editor, Calendar) open with dark headerbars and dark chrome around your light content, and tmux/nvim behave as though the background were dark. `omarchy-theme-color --file ~/.local/state/omarchy/current/theme/colors.toml mode` prints `dark`, and `gsettings get org.gnome.desktop.interface color-scheme` prints `'prefer-dark'`.

**Cause.** bin/omarchy-theme-color resolves the mode with this precedence: the `mode` key, then the legacy `theme_type` key, then a `light.mode` marker file beside colors.toml, then a background-luminance guess, then `dark`. resolve_theme_mode runs at the end of resolve_theme_colors, so legacy aliases (`bg` -> `background`, `color0` -> `background`) are already in place by then and a short-name palette is not the problem. What goes wrong is the guess itself: it is a bare `R + G + B > 382` out of 765, so a muted "light" background such as `#7d7d7d` (375) is classified dark. A theme that defines no background under any name at all (no `background`, no `bg`, no `color0`) skips the luminance branch entirely and falls straight through to `dark`. bin/omarchy-theme-set-gnome then sets `color-scheme prefer-dark` and `gtk-theme Adwaita-dark`, and bin/omarchy-theme-set-tmux exports `COLORFGBG=15;0`.

> **Audit corrected this record.** The precedence chain, the threshold, and the downstream effects are right: bin/omarchy-theme-color resolves mode from the `mode` key, then legacy `theme_type`, then a `light.mode` file beside colors.toml, then `(( lum > 382 ))` on a bare R+G+B sum out of 765, else dark; omarchy-theme-set-gnome sets prefer-dark + Adwaita-dark on the dark branch; omarchy-theme-set-tmux exports COLORFGBG=15;0. But the headline half of the cause is backwards. resolve_theme_mode is NOT called inside parse_colors_file — it is called at the very END of resolve_theme_colors (line 279), after every legacy alias has been applied: `alias_theme_color background bg` runs at lines 192-194 and `[[ ${THEME_COLORS[background]} ]] || THEME_COLORS[background]="${THEME_COLORS[color0]}"` at line 197. So a theme defining only `bg = "#fdf6e3"` or only `color0` DOES have `background` set when the mode is decided, and #fdf6e3 sums to 726 > 382, i.e. it is correctly detected as light. Only two things actually produce a wrong `dark`: a background whose channel sum is 382 or less (the record's own #7d7d7d = 375 example), and a theme with no background under any name (no background, no bg, no color0), which falls through to the literal `dark` default. The supported fix (`mode = "light"`) is correct and does beat every fallback.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The fix commands are right as written — keep them:

```bash
omarchy-theme-color --file ~/.local/state/omarchy/current/theme/colors.toml mode
sed -i '1i mode = "light"' ~/.config/omarchy/themes/<name>/colors.toml
omarchy theme set <name>
```

Drop the claim that the legacy short names "are not resolved in time to feed the luminance guess" — they are (omarchy-theme-color aliases bg/color0 to background before resolving the mode). Canonical key names are still worth using for clarity, but they will not change the detected mode. If you would rather not set `mode`, make sure the theme defines a `background` (or `bg`/`color0`) whose R+G+B exceeds 382; the empty `light.mode` marker in the theme root next to colors.toml also still works.

**Verify.** `omarchy-theme-color --file ~/.local/state/omarchy/current/theme/colors.toml mode` prints `light`, `gsettings get org.gnome.desktop.interface color-scheme` prints `'prefer-light'`, and a freshly launched Nautilus has a light headerbar.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-color> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set-gnome> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set-tmux> · <https://github.com/basecamp/omarchy/blob/quattro/manual/43-making-your-own-theme.md> · <https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md>

---

## Stop `omarchy font set` from redirecting every font whose name contains "mono"

`omarchy-font-set-hijacks-named-mono-families` · severity: **medium** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After `omarchy font set "Monaspace Neon NF"`, apps that explicitly ask for a different monospace font get the wrong one. `fc-match "JetBrainsMono Nerd Font"`, `fc-match "Liberation Mono"` and `fc-match "Adwaita Mono"` all return `Monaspace Neon NF`. Half the fonts listed by `omarchy font list` become unreachable, with no error anywhere.

**Cause.** Two rules combine. Fontconfig ships a generic-guessing rule that loads early and appends the generic `monospace` to the family list of any pattern whose *name contains the substring* `mono` - a name heuristic, not real monospace detection. (Confirm which file provides it on your system with `fc-conflist`; do not assume a filename.) Then `omarchy-font-set` writes a `~/.config/fontconfig/fonts.conf` rule with `<test name="family" qual="any"><string>monospace</string></test>` and `mode="prepend_first" binding="strong"`, which matches that appended generic and inserts the chosen font at the *head* of the whole family list, ahead of what the app actually asked for. Families like `Monaspace` escape because their name does not contain `mono`, which is why the bug is invisible if you only test with Monaspace.

> **Audit corrected this record.** The core mechanism is confirmed verbatim. bin/omarchy-font-set writes ~/.config/fontconfig/fonts.conf with exactly `<test name="family" qual="any"><string>monospace</string></test>` and `<edit name="family" mode="prepend_first" binding="strong">`. default/fontconfig/conf.avail/50-omarchy.conf confirms the caveat precisely: three generic rules using `mode="assign" binding="strong"` for sans-serif->Liberation Sans, serif->Liberation Serif, monospace->JetBrainsMono Nerd Font, and 50-omarchy sorts before 50-user. Two problems: (1) the fix is not durable - omarchy-font-set REGENERATES fonts.conf from scratch (`cat >"$fontconfig_file"`) on every font change, silently undoing the hand-edit, which the record never warns about; (2) '48-guessfamily.conf' could not be verified as a real fontconfig filename (upstream conf.d is not reachable and the man page does not enumerate it) - the guess-generic-from-name behaviour is real but the filename should be discovered with fc-conflist, not asserted.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `/etc/fonts/conf.d/50-omarchy.conf` is package-owned. Editing it directly means your change is reverted on the next `omarchy update` / `pacman -Syu`, and pacman may leave a `.pacnew`. Prefer overriding in `~/.config/fontconfig/fonts.conf` where possible. Also note that a later `omarchy font set` rewrites `~/.config/fontconfig/fonts.conf` and undoes the alias fix.

**Fix.**

Bisect to confirm fontconfig is the source:

```bash
mv ~/.config/fontconfig/fonts.conf{,.off}
fc-match "Liberation Mono"     # -> Liberation Mono, correct
mv ~/.config/fontconfig/fonts.conf{.off,}
fc-match "Liberation Mono"     # -> hijacked again
```

Find the real filenames and load order on YOUR system rather than assuming `48-guessfamily.conf` - the rule that appends a generic family based on the name containing `mono` ships under different filenames across fontconfig versions:

```bash
fc-conflist
```

**The critical gap in the original fix:** `omarchy-font-set` rewrites `~/.config/fontconfig/fonts.conf` from scratch every time you set a font, so any hand-edit is thrown away the next time you pick a font in Style > Font. Make it durable with a `font-set` hook, which `omarchy-font-set` runs *after* it writes fonts.conf:

```bash
mkdir -p ~/.config/omarchy/hooks/font-set.d
cat > ~/.config/omarchy/hooks/font-set.d/20-font-alias.sh <<'EOF'
#!/bin/bash
font="$1"
[[ -n $font ]] || exit 0
mkdir -p ~/.config/fontconfig
cat > ~/.config/fontconfig/fonts.conf <<XML
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias binding="strong">
    <family>monospace</family>
    <prefer><family>$font</family></prefer>
  </alias>
</fontconfig>
XML
fc-cache -f
EOF
chmod +x ~/.config/omarchy/hooks/font-set.d/20-font-alias.sh
omarchy font set "Monaspace Neon NF"
fc-match "Liberation Mono"    # should now be Liberation Mono
```

**Confirmed caveat.** `/etc/fonts/conf.d/50-omarchy.conf` really does use `mode="assign" binding="strong"` on the three generics, and `50-omarchy` sorts before `50-user`, so the literal `monospace` token is replaced with `JetBrainsMono Nerd Font` before your file loads and the alias never fires:

```xml
<edit name="family" mode="assign" binding="strong">
  <string>JetBrainsMono Nerd Font</string>
</edit>
```

Do not edit that file in place - it is package-owned and `omarchy update` restores it. Copy it into the user tree where it sorts later and convert the three generic rules to alias/prefer:

```bash
mkdir -p ~/.config/fontconfig/conf.d
cp /etc/fonts/conf.avail/50-omarchy.conf ~/.config/fontconfig/conf.d/99-omarchy-generics.conf
# edit that copy: change each mode="assign" rule to an <alias><family>monospace</family><prefer>...</prefer></alias>
fc-cache -f
fc-match monospace
```

**Verify.** `fc-match monospace` returns your chosen font, while `fc-match "Liberation Mono"` returns `Liberation Mono` and `fc-match "JetBrainsMono Nerd Font"` returns `JetBrainsMono Nerd Font`.

Sources: <https://github.com/basecamp/omarchy/issues/8404>

---

## Fix tray icons that vanish, refuse clicks, or take the whole tray widget with them

`quickshell-tray-icons-missing-stuck-unclickable` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Three related failures in the Omarchy 4 top bar's system tray. (1) An app's icon (fcitx5, Signal, Dropbox, NordVPN, Cryptomator, udiskie) disappears mid-session and the slot stays blank; a shell restart brings it back until the next time the app changes its icon. (2) Left-clicking a tray icon does nothing and double-clicking it toggles the *whole bar's* background transparency instead. (3) After clicking Hide on your only tray icon, the entire tray widget disappears — including the chevron whose menu is the only way to unhide it — and `omarchy-shell shell debugBarGeometry | grep tray` reports `'width': 0, 'height': 0, 'visible': False`.

**Cause.** Three separate defects in `shell/plugins/bar/widgets/Tray.qml`. (1) When an app flips its `IconName` between a `-symbolic` and a non-symbolic name, the `Image`'s `visible` and `layer.enabled` are both bound to the same `symbolic` property and flip together; the layer is never populated, so `MultiEffect` samples an empty texture and the icon silently vanishes (issue #7288; #8434 is the same shape). It works on first creation because nothing flips, which is why a restart looks like a fix. (2) `TrayItem` is a bare `MouseArea` and never calls `registerClickTarget`, unlike `Ui/BarIconButton.qml`, so `pressModuleClickTarget` finds no target, sets `mouse.accepted = false`, and the click propagates to `CenterGestureArea` — which despite its name is `anchors.fill: parent` across the entire bar and whose `onDoubleClicked` calls `toggleTransparency()` (issue #8111). (3) `Tray.qml:213` gates the widget root on `visible: pinnedItems.length > 0 || drawerCount > 0`; hidden items are in neither bucket, so hiding every reporting item makes the root invisible and the bar collapses the slot to width 0 (issue #7117). Separately, an app that only ever published an XEmbed tray icon has no StatusNotifierItem and will never appear on Wayland at all.

> **Audit corrected this record.** All three defects verified. (1) shell/plugins/bar/widgets/Tray.qml TrayIcon binds `visible: !trayIconRoot.symbolic` and `layer.enabled: trayIconRoot.symbolic` on the same Image feeding a MultiEffect; issue #7288 ("Tray icon vanishes when an app switches its IconName between symbolic and non-symbolic (fcitx5)") states the same root cause verbatim. (2) Issue #8111 is titled "Tray icons are unclickable: clicks fall through to the bar's gesture area and toggle transparency" and cites Tray.qml:814 — which is exactly the bare MouseArea in the file; shell/Ui/WidgetButton.qml (parent of BarIconButton) does call bar.registerClickTarget/triggerPress, TrayItem does not, and Bar.qml has registerClickTarget (line 104), pressModuleClickTarget (784) with `if (!root.pressModuleClickTarget(...)) mouse.accepted = false`, and `component CenterGestureArea: MouseArea` instantiated as `CenterGestureArea { anchors.fill: parent }` whose onDoubleClicked calls root.toggleTransparency(). (3) Tray.qml line 213 is literally `visible: pinnedItems.length > 0 || drawerCount > 0`. debugBarGeometry() exists in Bar.qml and `omarchy bar defaults` is a real subcommand ("Restore the default bar and service widgets"). The defect is the jq recovery one-liner: config/omarchy/shell.json stores `.bar.layout` as an OBJECT of three arrays (left/center/right), so `.bar.layout[]?` yields arrays and `select(.id == ...)` errors with "Cannot index array with \"id\"". jq exits non-zero (the `&&` saves the config from being clobbered by the empty redirect), so the step silently does nothing and the tray stays gone.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Once you own `~/.config/omarchy/shell.json` there is no deep merge with Omarchy's defaults — widgets added by later releases will never appear in your bar. Keep the backup shown above. `omarchy bar defaults` discards your entire bar layout, plugin placement and per-widget options, not just the tray entry.

**Fix.**

For "tray widget gone after hiding the last icon", use the supported command instead of hand-editing (the shell owns the in-memory config):

```bash
cp ~/.config/omarchy/shell.json ~/shell.json.bak
omarchy bar set omarchy.tray hidden '[]' --json
omarchy bar set omarchy.tray pinned '[]' --json
```

If you must edit the file (shell not running), the layout is an object of three arrays, so the path needs two levels of iteration:

```bash
jq '(.bar.layout[]?[]? | select(.id == "omarchy.tray")) |= (.hidden = [] | .pinned = []))' \
  ~/.config/omarchy/shell.json > /tmp/shell.json && mv /tmp/shell.json ~/.config/omarchy/shell.json
omarchy restart shell
```

(without the trailing paren typo: `... |= (.hidden = [] | .pinned = []))` should be `... |= (.hidden = [] | .pinned = [])`). Everything else in the record — the D-Bus probes, `omarchy restart shell`, the Activate call, `omarchy bar defaults` — is correct as written.

**Verify.** `omarchy-shell shell debugBarGeometry | grep tray` reports a non-zero `width` and `'visible': True`, the icon is drawn, and toggling the app's icon state (e.g. `fcitx5-remote -c` then `fcitx5-remote -o`) no longer blanks the slot.

Sources: <https://github.com/basecamp/omarchy/issues/7117> · <https://github.com/basecamp/omarchy/issues/7288> · <https://github.com/basecamp/omarchy/issues/8111> · <https://github.com/basecamp/omarchy/blob/quattro/shell/plugins/bar/widgets/Tray.qml>

---

## Fix `omarchy theme install` refusing a URL, hanging, or eating an existing theme

`theme-install-refused-or-hangs-on-bad-git-url` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy theme install <url>` fails in one of several ways. It prints `omarchy-git-url-check: '<url>' names the 'sftp' transport, which Omarchy does not clone from.` or `omarchy-git-url-check: '<url>' names a git option or transport helper, not a repository.` and stops. Or it prints `Error: '<url>' does not give a usable theme name.` Or git runs and fails with `fatal: repository '<url>' not found` followed by `Error: Failed to clone theme repo.` Or — the worst one — it just sits there forever with no output, because git is waiting on `Username for 'https://github.com':` or an SSH host-key prompt you cannot see when the install was launched from the Omarchy menu.

**Cause.** `bin/omarchy-theme-install` pre-screens the URL with `bin/omarchy-git-url-check` before cloning. That refuses anything starting with `-`, anything matching `<helper>::<address>` (git's transport-helper shape, and `ext::` runs a shell command), and any `<scheme>://` whose scheme is not on the allowlist `ssh git git+ssh ssh+git http https ftp ftps file`. It then derives the theme name from the URL: strip an scp-style `user@host:` prefix when the URL holds no `://` and the part before the first colon holds no slash, then `basename -- ... .git`, strip a leading `omarchy-` and a trailing `-theme`, and lowercase. The derived name is then held to a positive allowlist under a pinned locale rather than to a short list of bad shapes:

```bash
if ! (LC_ALL=C; [[ $THEME_NAME =~ ^[a-z0-9_][a-z0-9._+-]*$ ]]); then
  echo "Error: '$REPO_URL' does not give a usable theme name."
  exit 1
fi
```

So the name must start with a lowercase ASCII letter, a digit or an underscore, and may then contain only those plus `.`, `+` and `-`. A basename carrying a space, `@`, `~`, a second colon, a slash or a non-ASCII letter is refused, and so is an empty name, one starting with `.` or `-`, and one that reduces to `..`. The locale is pinned because a bare `[a-z]` range follows collation and would otherwise let `é` through. That strictness is deliberate: the name is joined into a path that is about to be `rm -rf`'d, and is later passed around by name into menu command lines. Anything that survives goes to `git clone -- "$REPO_URL" "$THEME_PATH"`, where the `--` is what stops a dash-leading URL being read as a git option. That clone inherits the terminal's stdin, sets no `GIT_TERMINAL_PROMPT=0` and has no timeout, so a private repo over HTTPS prompts for credentials and a first-time SSH host prompts for the host key, and the command blocks forever when it was launched from the Omarchy menu where nothing can answer the prompt. A URL pointing at a GitHub page (`.../tree/main`) or a tarball is not a repository and git rejects it. And critically, the existing `~/.config/omarchy/themes/<derived-name>` is `rm -rf`'d **before** the clone runs, so a failed install destroys whatever was already there. git itself deletes the destination it created when a clone fails, so there is no half-clone left to tidy up, but the directory that was removed first does not come back.

> **Audit corrected this record.** Re-audited against /usr/share/omarchy/bin/omarchy-theme-install and /usr/share/omarchy/bin/omarchy-git-url-check on this workstation at omarchy 4.0.2-1, and against bin/omarchy-theme-install on the quattro branch, which is byte-identical to the installed copy. Most of the record holds. Both refusal strings are exact (`names the '$scheme' transport, which Omarchy does not clone from.` and `names a git option or transport helper, not a repository.`), `TRANSPORTS=(ssh git git+ssh ssh+git http https ftp ftps file)` is exact with `ext` and `fd` deliberately excluded, `Error: '<url>' does not give a usable theme name.` and `Error: Failed to clone theme repo.` are exact, the `rm -rf "$THEME_PATH"` really does run before `git clone`, and the clone has no timeout, no `GIT_TERMINAL_PROMPT=0` and inherited stdin, so the hang story holds as read from the script. Every path is Omarchy 4: `~/.config/omarchy/themes`, and `~/.local/state/omarchy/current/theme.name` which `omarchy-theme-set` really writes. Nothing points at `~/.local/share/omarchy`. `omarchy-theme-remove` takes an optional name and otherwise shows an `omarchy-menu-select` picker, `omarchy theme refresh` and the other subcommands are all present in the dispatcher, and tokyo-night is one of the 22 themes in /usr/share/omarchy/themes. One claim is out of date and is the reason for the correction. The record says the derived name is refused when it is empty, starts with a dot, or contains a slash. That was the rule described in the merged issue 7884, but the shipping script now applies a positive allowlist under a pinned locale, `LC_ALL=C` with `^[a-z0-9_][a-z0-9._+-]*$`, which also refuses a leading `-`, a space, `@`, `~` and any non-ASCII letter. A reader hitting the name error on a repo like `omarchy-Solarized Light-theme` would not be explained by the record's rule, and the fix offered no way to predict the name at all. The cause is rewritten with the real regex and the fix gains a pre-flight block that derives the name and tests it. Current behaviour is better than the record describes in two places, and both are now stated: the name check is stricter and safer, and a failed clone leaves nothing behind. That second point was exercised here rather than assumed, with `GIT_TERMINAL_PROMPT=0 git clone -- https://github.com/omacom/definitely-not-a-real-repo-o3.git /tmp/o3clonetest`, which exited 128 and left no `/tmp/o3clonetest`. The destructive pre-clone `rm -rf` of an existing theme is therefore still the only real loss, and the record's danger already says so correctly. Not exercised: `omarchy theme install` was never run on this machine, so the refusals, the hang and the theme-name error were read from the script rather than triggered, and no credential or host-key prompt was provoked.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy theme install` does `rm -rf "$THEME_PATH"` before it clones, so a clone that then fails leaves you with **no** theme at that name. The name is derived from the URL with `omarchy-` and `-theme` stripped, so two unrelated repos can collide on it and quietly replace each other — back up any hand-edited theme first: `cp -a ~/.config/omarchy/themes/<name> ~/theme-backup-<name>`. A cloned theme is also arbitrary content from a stranger; Omarchy drops the files that can run code but everything else is applied as-is.

**Fix.**

Run installs from a terminal, never from the Style > Theme menu, so git's prompts are visible:

```bash
omarchy theme install https://github.com/<owner>/omarchy-<name>-theme.git
```

Pre-flight the URL **and** the theme name it derives, before you let either near your themes directory:

```bash
URL='https://github.com/<owner>/omarchy-<name>-theme.git'
omarchy-git-url-check "$URL" && echo 'url shape accepted'
git ls-remote "$URL" >/dev/null && echo 'repo reachable'

# the name Omarchy will derive, and the rule that name has to pass
P="$URL"
[[ $P != *"://"* && $P == *:* && ${P%%:*} != */* ]] && P="${P#*:}"
NAME=$(basename -- "$P" .git | sed -E 's/^omarchy-//; s/-theme$//' | tr '[:upper:]' '[:lower:]')
echo "theme name: $NAME"
(LC_ALL=C; [[ $NAME =~ ^[a-z0-9_][a-z0-9._+-]*$ ]]) && echo 'name accepted' || echo 'name refused'
[[ -d ~/.config/omarchy/themes/$NAME ]] && echo "WARNING: install deletes ~/.config/omarchy/themes/$NAME first"
```

Accepted URL forms are `https://`, `http://`, `ssh://`, `git://`, `git+ssh://`, `ssh+git://`, `ftp://`, `ftps://`, `file://`, and scp-style `git@host:org/repo.git`. Copy the repo's **clone** URL, not the page URL. A `/tree/main` or `/releases/download/...` link is not a repository. If the name check is what refused you, rename the repo or clone it yourself into `~/.config/omarchy/themes/<a-name-that-passes>` and run `omarchy theme set <that-name>`.

For a private repo, get the credentials working outside Omarchy first:

```bash
ssh -T git@github.com          # accepts the host key, proves the key works
git clone git@github.com:<owner>/<repo>.git /tmp/theme-probe && rm -rf /tmp/theme-probe
```

Clean up a half-installed theme:

```bash
omarchy theme remove <name>          # interactive picker if you omit the name
omarchy theme set tokyo-night
```

Or by hand, if the directory name is not what you expected:

```bash
ls -la ~/.config/omarchy/themes/
rm -rf ~/.config/omarchy/themes/<name>
```

**Verify.** `ls ~/.config/omarchy/themes/<name>/colors.toml` exists, `cat ~/.local/state/omarchy/current/theme.name` names the new theme, and `grep -rn '{{' ~/.local/state/omarchy/current/theme/` returns nothing.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-install> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-git-url-check> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-remove> · <https://github.com/basecamp/omarchy/blob/quattro/manual/43-making-your-own-theme.md> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-theme-install> · <https://github.com/omacom/omarchy/issues/7884>

---

## Fix Super+Ctrl+Shift+Space opening no theme picker

`theme-switcher-keybinding-does-nothing` · severity: **medium** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `SUPER+CTRL+SHIFT+SPACE` does nothing. Clicking Style > Theme in the Omarchy menu just closes the menu with no picker. `omarchy menu summon style.theme` prints `ok` but no window appears. Meanwhile `omarchy theme set <name>` from a terminal works fine, and the background switcher (`SUPER+CTRL+SPACE`) may work normally on the same machine.

**Cause.** Most reports of this turn out to be a stale plugin override left in the user menu file - `~/.config/omarchy/extensions/omarchy-menu.jsonc`: a plugin (e.g. themebook) added a `style.theme` route pointing at its own command, the plugin was uninstalled, and the override was never cleaned up, so the menu dutifully runs a command that no longer exists and reports `ok`. Separately, note that `style.theme` and `style.background` are *action* rows, not submenus: the menu deliberately closes and runs the command. The window that should appear is drawn by the shell's image-picker plugin, so `hyprctl layers` never showing an `omarchy-menu` layer for these two bindings is expected and is not evidence of a fault. Also, `omarchy-menu toggle` is declared `void` and cannot print `ok` at all, so an `ok` from `toggle` means nothing.

> **Audit corrected this record.** The action-row insight is correct and confirmed: default/omarchy/omarchy-menu.jsonc defines "style.theme" with `"action":"theme=$(omarchy-theme-switcher); [[ -n $theme ]] && omarchy-theme-set \"$theme\""` - an action, not a submenu. But the grep target is wrong: there is no ~/.config/omarchy/menu.jsonc. The user menu override is ~/.config/omarchy/extensions/omarchy-menu.jsonc (confirmed in config/omarchy/ and in omarchy-upgrade-to-quattro's always_copy_config_files). The layer namespace 'omarchy-image-selector' is also unverified - the shell plugin is shell/plugins/image-picker - so I replaced that guess with a command that lists all namespaces.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Check for stale plugin routes in the right file. There is no `~/.config/omarchy/menu.jsonc`; user menu overrides live in the extensions directory:

```bash
grep -n 'style.theme\|style.background' ~/.config/omarchy/extensions/omarchy-menu.jsonc
```

Compare what you find against the stock action, which is what should run:

```jsonc
"style.theme": {"icon":"󰸌","label":"Theme","action":"theme=$(omarchy-theme-switcher); [[ -n $theme ]] && omarchy-theme-set \"$theme\""}
```

Delete any route pointing at a plugin you no longer have installed, then:

```bash
omarchy restart shell
```

`style.theme` and `style.background` are *action* rows, not submenus - the menu deliberately closes and runs the command, so no `omarchy-menu` layer appearing is expected and is not a fault.

Don't guess the picker's layer namespace. List them all and watch which appears:

```bash
hyprctl layers | grep -i omarchy
```

Drive the chain manually to confirm it works end to end:

```bash
theme=$(omarchy-theme-switcher) && omarchy-theme-set "$theme"
```

Stale Quickshell instance dirs:

```bash
ls /run/user/$UID/quickshell/by-id/
omarchy restart shell
```

**Verify.** `SUPER+CTRL+SHIFT+SPACE` opens the picker, `hyprctl layers` shows an `omarchy-image-selector` layer while it is open, and selecting a theme changes `~/.local/state/omarchy/current/theme.name`.

Sources: <https://github.com/basecamp/omarchy/issues/8262>

---

## Recover from a custom theme that leaves the terminal unable to start

`installed-theme-without-colors-toml-breaks-foot` · severity: **medium** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After `omarchy theme install <git-url>` or `omarchy theme set <my-theme>`, new terminal windows refuse to open. Running foot by hand prints: `err: config.c:896: /home/<user>/.config/foot/foot.ini:2: [main].include: ~/.local/state/omarchy/current/theme/foot.ini: failed to open: No such file or directory` and exits 230. `omarchy theme set` itself exited 0 with no warning.

**Cause.** `bin/omarchy-theme-set` applies any directory under `~/.config/omarchy/themes/` whose name passes its regex, and the template generator only runs `if [[ -f $COLORS_FILE ]]` (`/usr/share/omarchy/bin/omarchy-theme-set-templates:371`). A theme with no `colors.toml`, and no legacy `alacritty.toml` to convert from, therefore produces a `~/.local/state/omarchy/current/theme/` with none of the generated files: no `foot.ini`, `alacritty.toml`, `kitty.conf`, `ghostty.conf`, `shell.toml` or `hyprland.lua`. `/usr/share/omarchy/config/foot/foot.ini:2` is an unconditional `include` of that missing `foot.ini` and foot treats a missing include as fatal. Alacritty (`general.import`) and kitty (`include`) are unconditional too, and only Ghostty is guarded, with `config-file = ?"..."`. The Hyprland session is not affected, because the theme's `hyprland.lua` and `gum_env.lua` are loaded through `require_optional` (`default/hypr/omarchy.lua:22`, `default/hypr/envs.lua:5`), and already-open terminal windows keep running because `omarchy-restart-terminal` has no foot action. You only discover it when you open a new window, and `omarchy theme set` exited 0 with no warning. On Omarchy 4.0.2 a theme installed from a git repo is staged rather than copied wholesale, and `foot.ini` is on the refused list, so such a theme cannot ship its own `foot.ini` to cover the gap. Only a `colors.toml` closes it.

> **Audit corrected this record.** Checked on this workstation at omarchy 4.0.2-1, omarchy-settings 4.0.2-1, foot 1.27.0-2, with alacritty, kitty and ghostty not installed. The core mechanism holds exactly: `/usr/share/omarchy/bin/omarchy-theme-set-templates:371` is `if [[ -f $COLORS_FILE ]]`, `/usr/share/omarchy/config/foot/foot.ini:2` is an unconditional `include`, alacritty and kitty include unconditionally and only ghostty uses the guarded `config-file = ?"..."` form, `omarchy-restart-terminal` has no foot action so open windows survive, `default/xdg-terminal-exec` names only `foot.desktop`, and all 22 directories under `/usr/share/omarchy/themes` ship a `colors.toml`. I reproduced the symptom text exactly: `foot --check-config` against a config whose include is missing prints `err: config.c:896: ... failed to open: No such file or directory` and exits 230. Four things are wrong. First and worst, the fix does not work: I ran `omarchy-theme-set-templates` in a sandboxed HOME against the record's own three-key `colors.toml` and `omarchy-theme-color --all` returns empty strings for red, green, yellow, blue, magenta and cyan, so the generated `foot.ini` carries `regular1=` with no value and foot still refuses, now with `err: config.c:3268: [colors-dark].regular1: syntax error: key/value pair has no value` and exit 230. Repeating the same sandbox with the six hues added gave a `foot.ini` that `foot --check-config` accepts with exit 0, so the corrected fix carries nine keys and points at a shipped palette as the easier route. Second, the recovery path assumed a terminal or a TTY and missed the terminal-free one: `default/hypr/bindings/utilities.lua:18` binds SUPER + SHIFT + CTRL + SPACE to `omarchy-menu toggle theme`, and `default/omarchy/omarchy-menu.jsonc` key `style.theme` runs `omarchy-theme-switcher` then `omarchy-theme-set`. Third, the cause and danger claim `omarchy theme install` applies a repo with no validation, which was true at the commit in issue 7105 but is false on 4.0.2: `omarchy-theme-install` calls `omarchy-git-url-check`, holds the theme name to `^[a-z0-9_][a-z0-9._+-]*$`, and `omarchy-theme-set` stages a cloned theme through `stage_installed_theme`, refusing symlinks at any depth and dropping `INSTALLED_THEME_DENIED=(alacritty.toml foot.ini ghostty.conf kitty.conf vscode.json)` plus every `.lua`, naming them on stderr. That change makes the failure stricter for the clone path, because a cloned theme can no longer ship its own `foot.ini` to cover the gap. Fourth, the verify field's `hyprland.conf` is Omarchy 3 wording taken from the issue's own reproduction. Omarchy 4 generates `hyprland.lua` from `default/themed/hyprland.lua.tpl`, and my sandbox run produced 18 files including `shell.toml` and `hyprland.lua`. I dropped severity from high to medium because the blast radius is narrower than the record implies: the theme's `hyprland.lua` and `gum_env.lua` are loaded with `require_optional` (`default/hypr/omarchy.lua:22`, `default/hypr/envs.lua:5`), so a missing one does not break the Hyprland session, open terminals keep running, and recovery is one keybinding away with no terminal at all. Issue 7105 is open on omacom/omarchy, I read it in full, and it supports the record including its own appended correction that only new foot launches break. The cited omacom manual page returns 200 and does say `colors.toml` is the file to tweak, but its app list is Omarchy 3 era (Hyprlock, Mako, SwayOSD, Walker, Waybar) and it never mentions foot, so it backs the palette claim only. NOT exercised: I did not install a theme, run `omarchy-theme-set`, or change the live theme on this machine, so every claim about the applied result comes from reading the scripts plus the sandboxed template run under a throwaway HOME. I also did not test whether Ctrl+Alt+F2 reaches a getty on this install.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy theme install <git-url>` clones a repository into `~/.config/omarchy/themes/` and applies it immediately. On Omarchy 4.0.2 the URL is checked by `omarchy-git-url-check`, the theme name is held to `^[a-z0-9_][a-z0-9._+-]*$`, symlinks are refused at any depth, and `alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf`, `vscode.json` and every `.lua` are dropped and named on stderr, so a cloned theme cannot run code at login. Nothing checks that the theme has a `colors.toml`, so a repo you have not read can still leave you unable to open a new terminal. Look at the repo before installing it.

**Fix.**

You do not need a terminal to get out of this. Press **Super+Shift+Ctrl+Space** for the Theme menu, or **Super+Space** and pick Style then Theme, then choose a stock theme. That menu entry runs `omarchy-theme-switcher` and `omarchy-theme-set` directly, so it works with every terminal on the machine broken.

If a terminal window is still open it keeps working, so you can switch back there instead:

```bash
omarchy theme set tokyo-night
```

If the graphical session is gone as well, get a shell from a TTY with `Ctrl+Alt+F2`, log in, and run the same command.

To keep the broken theme, give it a `colors.toml`. A three-key file is not enough: `omarchy-theme-color` returns an empty string for every hue it cannot derive, so the generated `foot.ini` gets `regular1=` with no value and foot still refuses to start, this time with `err: config.c:3268: [colors-dark].regular1: syntax error: key/value pair has no value` and exit 230. The smallest file that produces a config foot accepts carries the six hues too:

```bash
cat > ~/.config/omarchy/themes/<my-theme>/colors.toml <<'EOF'
mode       = "dark"
background = "#1a1b26"
foreground = "#c0caf5"
red        = "#f7768e"
green      = "#9ece6a"
yellow     = "#e0af68"
blue       = "#7aa2f7"
magenta    = "#ad8ee6"
cyan       = "#449dab"
EOF
omarchy theme set <my-theme>
```

Copying a shipped palette and editing the values is easier and fills in every optional key, including the bright and background shades the templates otherwise derive:

```bash
cp /usr/share/omarchy/themes/tokyo-night/colors.toml ~/.config/omarchy/themes/<my-theme>/colors.toml
omarchy theme set <my-theme>
```

Before installing any third-party theme, check it first:

```bash
ls ~/.config/omarchy/themes/<name>/colors.toml || echo "NO colors.toml - new terminal windows will not open"
```

**Verify.** `foot --check-config; echo $?` returns 0, and `ls -A ~/.local/state/omarchy/current/theme` lists the generated files as well as whatever the theme shipped: `colors.toml`, `foot.ini`, `alacritty.toml`, `kitty.conf`, `ghostty.conf`, `shell.toml` and `hyprland.lua` are all present. If the directory holds only the theme's own images, `icons.theme` and similar, the template pass did not run.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/92/making-your-own-theme> · <https://github.com/omacom/omarchy/issues/7105> · <https://github.com/omacom/omarchy/blob/quattro/docs/theming.md>

---

## Bisect a theme switch that hangs, or that kills btop with SIGABRT

`post-theme-retint-hangs-or-kills-btop` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy theme set <name>` never returns — the colours changed but the command sits there. Or it returns and something is dead: the classic is btop vanishing, with `coredumpctl list btop` showing a fresh `Signal: 6 (ABRT)` timestamped a few hundred milliseconds after the theme was applied, and a stack of `std::__glibcxx_assert_fail` -> `std::vector<std::string>::operator[]` -> `Gpu::draw(...)` -> `Runner::_runner(...)` failing the assertion `__n < this->size()`.

**Cause.** Once the staged theme is swapped in and the shell has accepted it, `bin/omarchy-theme-set` releases its `flock` and fires `run_parallel` over `post_theme_commands`: `omarchy-restart-terminal`, `-hyprctl`, `-btop`, `-opencode`, `-helix`, then `omarchy-theme-set-foot`, `-tmux`, `-gnome`, `-pi`, `-claude`, `-browser`, `-vscode`, `-obsidian`, `-keyboard`. Each is launched as `bash -lc "$command" &` and `run_parallel` then `wait`s on every pid with **no timeout**, so any single command that blocks blocks the whole theme change. `omarchy-restart-btop` is nothing but `pkill -SIGUSR2 btop`, which btop treats as a configuration hot-reload; on Arch's btop 1.4.7 with GPU boxes enabled that reload path indexes `Gpu::box` out of range and aborts (issue #8711, upstream aristocratos/btop#860). The theme itself always applies — the damage is downstream of it.

> **Audit corrected this record.** Verified almost verbatim. bin/omarchy-theme-set releases its flock (`flock -u 9`) right after the shell accepts the transition, then run_parallel launches each of post_theme_commands as `bash -lc "$command" &` and `wait`s on every pid with no timeout; the fourteen commands are in exactly the order the record lists (omarchy-restart-terminal, -hyprctl, -btop, -opencode, -helix, omarchy-theme-set-foot, -tmux, -gnome, -pi, -claude, -browser, -vscode, -obsidian, -keyboard). omarchy-restart-btop is nothing but `pkill -SIGUSR2 btop`. OMARCHY_THEME_HEADLESS=1 does skip the whole run_parallel/hook/cache block (it also skips the applyTheme IPC, which is why the follow-up `omarchy restart shell` is right). Issue #8711 is titled "Theme switching can SIGABRT running btop 1.4.7 via SIGUSR2 reload", cites the out-of-bounds GPU layout access in Gpu::draw() and upstream aristocratos/btop#860. The bisect loop and pkill triage are sound. One error: btop validates show_gpu_info against `const vector<string> Config::show_gpu_values = { "Auto", "On", "Off" }` (src/btop_config.cpp) case-sensitively, rejecting anything else with "Invalid value for show_gpu_info: ...". Writing `"off"` lowercase is invalid, so btop discards it and keeps the default — the reader stays on the crashing path.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not `Ctrl+C` out of `omarchy update` when it hangs inside a theme migration — the migration never writes its marker file, so it re-runs and re-hangs on every subsequent update, and the whole queue behind it stays pending. Kill the individual blocking child instead and let the update carry on. `OMARCHY_THEME_HEADLESS=1` also skips the background change and the hook, so use it for diagnosis rather than as a permanent habit.

**Fix.**

Use the capitalized value btop actually accepts (valid values are exactly "Auto", "On", "Off"), and create the key if the config does not already carry it:

```bash
coredumpctl list btop
grep -n 'shown_boxes\|show_gpu_info' ~/.config/btop/btop.conf
if grep -q '^show_gpu_info' ~/.config/btop/btop.conf; then
  sed -i 's/^show_gpu_info = .*/show_gpu_info = "Off"/' ~/.config/btop/btop.conf
else
  printf 'show_gpu_info = "Off"\n' >> ~/.config/btop/btop.conf
fi
grep -n '^show_gpu_info' ~/.config/btop/btop.conf
```

If a GPU box is also in `shown_boxes`, drop it there too (e.g. `shown_boxes = "cpu mem net proc"`). Everything else in the record — the pgrep/pkill triage, the timeout-124 bisect loop, and `OMARCHY_THEME_HEADLESS=1 omarchy-theme-set <name>` followed by `omarchy restart shell` — is correct as written.

**Verify.** `time omarchy theme set tokyo-night` completes in a couple of seconds, and `coredumpctl list btop` records no new dump after switching themes with btop running.

Sources: <https://github.com/basecamp/omarchy/issues/8711> · <https://github.com/aristocratos/btop/issues/860> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set> · <https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md>

---

## Restore bar widgets and plugins wiped by the Quattro upgrade

`shell-json-reset-by-quattro-upgrade` · severity: **medium** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After running `omarchy upgrade to quattro` on a machine that already had a `~/.config/omarchy/shell.json`, every bar customization is gone: extra bar widgets, the enabled-plugins list, `transparent: true`, and custom idle timers are all back to stock defaults. The plugin directories under `~/.config/omarchy/plugins/` are all still there, untouched. Only the config was reset, and nothing on screen says a backup was written.

A genuine first upgrade from Omarchy 3.x does not hit this, because 3.x has no `shell.json` to lose. What hits it is a second run of the upgrade script, which its own abort banner recommends after any failure.

**Cause.** `omarchy-upgrade-to-quattro` lists `omarchy/shell.json` in `always_copy_config_files` (line 1670 of the script shipped with omarchy 4.0.2-1, line 1641 in the Omarchy 3 `master` tree the issue was filed against). `copy_always_config_defaults` (line 1918) calls `copy_config_default`, which installs the stock Quattro default over the existing file unless the two are byte-identical. `backup_config_file()` does save the old one first, to `~/.config/omarchy/shell.json.omarchy-upgrade-to-quattro.<timestamp>.bak`, where the timestamp is one per run from `backup_suffix=$(date +%Y%m%d%H%M%S)` at line 387. Nothing in the script ever prints that a `.bak` was written, for any of the places it writes one.

Two things narrow and widen that. It cannot bite a genuine first upgrade from Omarchy 3.x, because 3.x has no `~/.config/omarchy/shell.json` at all and configures the bar through `~/.config/waybar/config.jsonc`. With the file absent, `copy_config_default` just installs the default and writes no backup. The machines that lose a config are ones where the script runs against a `shell.json` that already exists, which means a re-run, and the script's own abort banner at line 374 says "Re-running is safe and resumes the remaining steps".

A re-run also cannot be skipped by the byte-identical guard. Every upgrade run finishes with `run_as_user_omarchy omarchy-bar defaults` at line 2372, which writes through `omarchy-shell-config`'s `commit` helper. That serialises with `jq -S`, so the file comes back key-sorted while the shipped `/usr/share/omarchy/config/omarchy/shell.json` is not (confirmed on this workstation: `jq -S .` of the shipped file is byte-different from the shipped file). The `cmp -s` guard in `copy_config_default` therefore never fires again on a machine that has completed the upgrade once.

`omarchy-bar defaults` is a second, independent reset. Its `commit` program starts `.bar = $defaults[0].bar`, replacing the whole `bar` subtree, so layout, `position`, `transparent` and per-widget settings go regardless of what the copy step did. It leaves `plugins` and `idle` alone, so the copy step is what accounts for those two.

The list is wider than `shell.json`. `always_copy_config_files` also carries `hypr/hyprland.lua`, `hypr/bindings.lua`, `hypr/monitors.lua`, `hypr/input.lua`, `hypr/looknfeel.lua`, `hypr/autostart.lua`, `hypr/.luarc.json`, `omarchy/extensions/omarchy-menu.jsonc` and `omarchy/hooks/pre-refresh-pacman.d/add-custom-repo.sample`. A re-run resets a monitor layout and a keybinding set the same way it resets a bar, and backs each one up under the same suffix.

The `shell.json` schema itself is unchanged across the copy (`version`, `idle`, `bar`, `plugins`, with no new required keys), so a straight restore of the `.bak` parses and loads.

> **Audit corrected this record.** Checked the shipped `/usr/share/omarchy/bin/omarchy-upgrade-to-quattro` on this workstation (omarchy 4.0.2-1) rather than the issue text. The mechanism holds: `omarchy/shell.json` is in `always_copy_config_files` at line 1670, `copy_always_config_defaults` runs it at line 1918, `copy_config_default` backs up via `backup_config_file` to `<file>.omarchy-upgrade-to-quattro.<timestamp>.bak`, and `backup_suffix=$(date +%Y%m%d%H%M%S)` is at line 387. Confirmed no `log`, `warn` or `echo` in the script mentions a `.bak`. Confirmed on this machine that `shell.json`, not `shell.toml`, is the file the record is about: `/usr/share/omarchy/bin/omarchy-shell-config` declares itself "Shared helpers for editing ~/.config/omarchy/shell.json", while `shell.toml` is theme styling generated from `/usr/share/omarchy/default/themed/shell.toml.tpl` and read by the Quickshell QML. Neither supersedes the other, so the record points at the right file.

Three things were wrong or missing. First, the record presents this as what a Quattro upgrade does to any customized install. It cannot happen on a genuine first upgrade from Omarchy 3.x, which has no `~/.config/omarchy/shell.json` and configures the bar through waybar, so the precondition is that the script runs against a file that already exists, which in practice means a re-run. Second, the record misses that the `cmp -s` skip in `copy_config_default` can never fire again after one completed upgrade: `omarchy-bar defaults` writes through `commit`, which serialises with `jq -S`, and I confirmed locally that `jq -S .` of `/usr/share/omarchy/config/omarchy/shell.json` is byte-different from the shipped file. Third, the record misses a second independent reset. `run_as_user_omarchy omarchy-bar defaults` at line 2372 runs a `commit` program beginning `.bar = $defaults[0].bar`, replacing the whole bar subtree, which means the record's restore is incomplete advice for anyone re-running the script. `always_copy_config_files` also covers seven `hypr/` files and `omarchy/extensions/omarchy-menu.jsonc`, which the fix now names.

The cited source URL was wrong. `https://github.com/basecamp/omarchy/issues/8357` returns 404 (the issue was created 2026-08-26, after the repo rename), while `https://github.com/omacom/omarchy/issues/8357` returns 200. Read the issue in full: it is OPEN, it supports the record's mechanism, and its own collaborator comment supplies the three corrections above. Frequency is dropped from very-common to occasional because the precondition is a re-run rather than an upgrade. Severity stays medium: the data is backed up and recoverable.

Not exercised: I did not run `omarchy-upgrade-to-quattro`, did not run `omarchy bar defaults`, and did not restore any file on this machine. The line numbers, the `jq -S` byte difference and the migration done-marker directory were all read or computed locally. Whether the restore then breaks a specific plugin was not tested.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Restoring a pre-Quattro `shell.json` wholesale reinstates whatever that file said, and update-time migrations do not re-run to correct it. They are marked done per user under `~/.local/state/omarchy/migrations/`, so a restore can permanently bring back a widget or a format a migration removed, for example `1785189600.sh` (removes the tmux alert bar indicator), `1784989000.sh` (moves the bar indicators left of the clock) and `1786099804.sh` (renames the model usage widget to agents). Keep `shell.json.quattro-default` so you can fall back, and do not delete the `.bak` files until you have confirmed the restore works.

**Fix.**

Find the backup. There is one per upgrade run, and the same suffix is on every other file the script replaced:

```bash
ls -la ~/.config/omarchy/shell.json*
ls -la ~/.config/hypr/*.omarchy-upgrade-to-quattro.*.bak
```

Keep the new default aside, then restore:

```bash
cp ~/.config/omarchy/shell.json ~/.config/omarchy/shell.json.quattro-default
cp ~/.config/omarchy/shell.json.omarchy-upgrade-to-quattro.<timestamp>.bak \
   ~/.config/omarchy/shell.json
omarchy restart shell
```

If you would rather merge only the parts you care about onto the new default:

```bash
jq -s '.[0] * {bar: .[1].bar, plugins: .[1].plugins, idle: .[1].idle}' \
  ~/.config/omarchy/shell.json.quattro-default \
  ~/.config/omarchy/shell.json.omarchy-upgrade-to-quattro.<timestamp>.bak \
  > ~/.config/omarchy/shell.json
omarchy restart shell
```

Check what else the same run replaced, and restore any of those you had customized:

```bash
for f in ~/.config/hypr/hyprland.lua ~/.config/hypr/bindings.lua \
         ~/.config/hypr/monitors.lua ~/.config/hypr/input.lua \
         ~/.config/hypr/looknfeel.lua ~/.config/hypr/autostart.lua \
         ~/.config/omarchy/extensions/omarchy-menu.jsonc; do
  ls "$f".omarchy-upgrade-to-quattro.*.bak 2>/dev/null
done
```

Before running the upgrade in the first place, take your own copy:

```bash
cp ~/.config/omarchy/shell.json ~/shell.json.pre-quattro
```

The restore survives ordinary `omarchy update` runs. Update-time migrations edit `shell.json` with targeted `jq` changes and never replace it, so nothing puts the default back. It does not survive another run of `omarchy-upgrade-to-quattro`: that run replaces the file again and, at line 2372, also runs `omarchy bar defaults`, which resets the whole `bar` subtree on its own. If you re-run the script, expect to restore again, and note that restoring the `.bak` does not undo the `omarchy bar defaults` step, so do the restore after the script has finished rather than in the middle of it.

**Verify.** `jq '.bar.layout, .plugins, .bar.transparent' ~/.config/omarchy/shell.json` shows your customizations back, `jq . ~/.config/omarchy/shell.json` parses, and after `omarchy restart shell` the extra widgets are visible in the bar again.

Sources: <https://github.com/omacom/omarchy/issues/8357>

---

## Fix a blank wallpaper and dangling background symlink after applying a custom theme

`theme-without-backgrounds-blanks-wallpaper` · severity: **medium** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After applying a user-installed theme the notification says "No background was found for theme", and later — after a shell restart or reboot — the desktop has no wallpaper at all. `omarchy theme bg current` prints `Unknown`.

**Cause.** `set_theme_background` (`bin/omarchy-theme-set:94-100`) notifies and returns without touching `~/.local/state/omarchy/current/background` when the new theme ships no `backgrounds/` directory. But the previous wallpaper lived at `current/theme/backgrounds/<file>`, and `bin/omarchy-theme-set:164` has just `rm -rf`'d and replaced that directory. So the symlink now points into a directory that no longer exists. All 22 shipped themes have backgrounds, so this only bites user-installed themes.

**Fix.**

Confirm the dangling link:

```bash
readlink ~/.local/state/omarchy/current/background
readlink -f ~/.local/state/omarchy/current/background   # resolves to nothing
[[ -e ~/.local/state/omarchy/current/background ]] && echo ok || echo DANGLING
```

Give the theme a background so this stops happening:

```bash
mkdir -p ~/.config/omarchy/themes/<my-theme>/backgrounds
cp ~/Pictures/wall.jpg ~/.config/omarchy/themes/<my-theme>/backgrounds/1-wall.jpg
omarchy theme set <my-theme>
```

Or point the background at any image directly without touching the theme:

```bash
omarchy theme bg set ~/Pictures/wall.jpg
```

**Verify.** `readlink -f ~/.local/state/omarchy/current/background` resolves to a file that exists, and `omarchy theme bg current` prints its name instead of `Unknown`. The wallpaper survives `omarchy restart shell`.

Sources: <https://github.com/basecamp/omarchy/issues/7116>

---

## Fix a black lock screen when the wallpaper is a WebP image

`webp-wallpaper-black-lock-screen` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** The desktop wallpaper displays perfectly, but `omarchy system lock` shows a solid black background instead of the wallpaper. Wallpaper thumbnails in the picker panels are blank too. Confusing because "the wallpaper works, so why is the lock screen black?"

**Cause.** `omarchy-shell` runs on Qt6/Quickshell, and QML `Image` needs a codec plugin in `/usr/lib/qt6/plugins/imageformats/`; without `libqwebp.so` there, WebP decodes to nothing. The desktop looks fine because Hyprland's wallpaper daemon decodes WebP independently of Qt. This is now a stale-install problem rather than a packaging gap: `qt6-imageformats` **is** listed in `install/omarchy-base.packages`, and `migrations/1787133200.sh` adds it to existing installs - so it bites machines that predate that migration and have not run `omarchy update`.

> **Audit corrected this record.** The package name is correct and the remedy works, but the stated cause is now obsolete: qt6-imageformats IS listed in install/omarchy-base.packages, and migrations/1787133200.sh adds it to existing installs, so it is no longer true that it 'is not a dependency of the omarchy package'. On a current system the fix is to run omarchy update and let the migration do it. Also `sudo pacman -S qt6-imageformats` against a stale sync db can fail or pull an outdated version; `-Syu` is the correct form (and `-Sy` alone would be a partial upgrade).
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

The cause is out of date: `qt6-imageformats` is now listed in `install/omarchy-base.packages`, and migration `1787133200` adds it to existing installs. So run the update first - on a current system it fixes this for you:

```bash
omarchy update
```

Confirm the codec is present:

```bash
ls /usr/lib/qt6/plugins/imageformats/ | grep -i webp   # want libqwebp.so
```

If it is still missing, install it. Use `-Syu`, never bare `-S` against a stale sync db and never `-Sy` (partial upgrade):

```bash
sudo pacman -Syu qt6-imageformats
omarchy restart shell
```

The underlying explanation still holds: the Quickshell-based `omarchy-shell` needs a Qt image-format plugin to decode WebP, while the desktop wallpaper looks fine because Hyprland's wallpaper daemon decodes WebP independently of Qt.

Alternatively convert the wallpaper:

```bash
magick ~/Pictures/wall.webp ~/Pictures/wall.jpg
omarchy theme bg set ~/Pictures/wall.jpg
```

**Verify.** `ls /usr/lib/qt6/plugins/imageformats/ | grep webp` shows `libqwebp.so`, and `omarchy system lock` displays the WebP wallpaper. Previews in the wallpaper picker render instead of being blank.

Sources: <https://github.com/basecamp/omarchy/issues/8392>

---

## Understand why a font change appears to do nothing in an open terminal

`font-change-appears-to-do-nothing-until-terminal-restart` · severity: **low** · frequency: **very-common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** You change the font via Style > Font or `omarchy font set "JetBrainsMono Nerd Font"`, the command exits successfully, but the running Ghostty or Foot window keeps the old font and no notification ever appears. It reads as "the font change didn't work". Running the underlying command by hand prints `Usage: omarchy-notification-send [--exec <command>] [--app-name <app-name>] [-g <glyph>] ... <headline> [description] [notify-send options]`.

**Cause.** Ghostty and Foot only read the font face at process start. `omarchy-font-set` is supposed to tell you to restart them, but lines 71 and 75 of `bin/omarchy-font-set` call `omarchy-notification-send -g  "You must restart Ghostty to see font change"` - the message lands in the `-g`/`--glyph` slot, which takes a value, leaving no headline argument. `omarchy-notification-send` then prints its usage line and exits 1. The script has no `set -e`, and `omarchy-hook font-set "$font_name"` runs after those lines, so the script's exit status comes from the hook rather than the failed notification - the reminder is dropped completely silently.

> **Audit corrected this record.** The bug is confirmed verbatim - bin/omarchy-font-set contains `omarchy-notification-send -g  "You must restart Ghostty to see font change"` (with the double space) and the same for Foot, so the message lands in the -g/--glyph value slot and leaves no headline. Two corrections: the cause is wrong that these are 'its last statements' - `omarchy-hook font-set "$font_name"` runs after them, so the script's exit status comes from the hook, not from the failed notification. More importantly the `sudo sed -i` patch targets a package-owned file that `omarchy update`/pacman restores, silently reverting the patch; a font-set hook achieves the same thing durably and without sudo.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy-font-set` lives in a package-owned path, so a `sed` patch to it is reverted on the next `omarchy update`.

**Fix.**

The font change did apply - just restart the terminals. **This closes all their windows, so save your work first:**

```bash
pkill -x ghostty
pkill -x foot
```

Confirm the setting really did change before restarting:

```bash
fc-match monospace
grep -i 'font' ~/.config/ghostty/config
grep '^font=' ~/.config/foot/foot.ini
```

Correction to the cause: the two broken calls are **not** the script's last statements - `omarchy-hook font-set "$font_name"` runs after them, so the exit status comes from the hook rather than from the failed notification. The `-g` bug itself is real and verbatim in the source; it just fails silently for a different reason than stated.

Do **not** `sudo sed` the packaged script. `bin/omarchy-font-set` is package-owned and `omarchy update` restores it, silently reverting your patch. Get the notification back with a `font-set` hook instead, which Omarchy runs at the end of every font change:

```bash
mkdir -p ~/.config/omarchy/hooks/font-set.d
cat > ~/.config/omarchy/hooks/font-set.d/30-restart-notice.sh <<'EOF'
#!/bin/bash
pgrep -x ghostty >/dev/null && omarchy-notification-send "Restart Ghostty to see the font change"
pgrep -x foot    >/dev/null && omarchy-notification-send "Restart Foot to see the font change"
exit 0
EOF
chmod +x ~/.config/omarchy/hooks/font-set.d/30-restart-notice.sh
```

**Verify.** A newly opened Ghostty/Foot window renders in the new font. `omarchy-notification-send "test" "test"; echo $?` returns 0 and shows a toast, confirming the notification path itself is healthy.

Sources: <https://github.com/basecamp/omarchy/issues/7183>

---

## Fix newly installed apps showing no icon in the launcher

`launcher-missing-app-icons-stale-icon-cache` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `omarchy-3`, `omarchy-4`, `wayland`

**Symptom.** Newly installed applications (Firefox, Chrome, GIMP, Brave, Calibre — often AUR packages) appear in the launcher and start correctly, but with a blank or generic icon. Reinstalling the package sometimes fixes it, which makes it look random.

**Cause.** On Omarchy 4 the launcher and the Apps menu are drawn by the Quickshell shell under `/usr/share/omarchy/shell`, not by Walker. `walker` and `elephant` are not installed at all, so any advice aimed at Walker describes Omarchy 3. Icon lookup lives in `/usr/share/omarchy/shell/services/AppLibrary.qml`. Its `iconSource()` resolves, in order: the value itself when it starts with `file://`, `image://` or `/`, then the shell's own icon index, then Qt's themed lookup through `Quickshell.iconPath()`, then `application-x-executable`. That index is built by `iconIndexScanCommand()`, which shells out to `find` over `$HOME/.icons`, `$HOME/.local/share/icons` and every `$XDG_DATA_DIRS` entry's `icons` directory for files under an `apps` or `devices` path, plus `/usr/share/pixmaps` at depth 1. It is a filesystem scan. Nothing in that path reads GTK's binary cache at `/usr/share/icons/hicolor/icon-theme.cache`, so a stale GTK cache is not the cause of a blank icon in the Omarchy 4 launcher. The index is also rebuilt whenever the desktop entry list changes, debounced by 750 ms, and again on every menu open through `refreshIcons()`, so a newly installed app normally shows its icon the next time the menu is opened with no command run at all. What does still produce a blank icon on Omarchy 4: the `.desktop` file has no `Icon=` line, the name in `Icon=` matches no file, or the package installed its icon somewhere the scan does not reach, such as a `status` or `mimetypes` subdirectory of a theme or a subdirectory below `/usr/share/pixmaps`. On plain Arch with a GTK based launcher, panel or file chooser, a stale `hicolor` cache is a genuine cause and `gtk-update-icon-cache` is the right tool for that layer.

> **Audit corrected this record.** The fix was aimed at the wrong layer for Omarchy 4. I read the launcher source on this machine at /usr/share/omarchy/shell/services/AppLibrary.qml and confirmed it byte for byte against the upstream quattro branch: iconSource() resolves an absolute or file:// value directly, then consults the shell's own icon index, then Qt's Quickshell.iconPath(). That index is a find over $HOME/.icons, $HOME/.local/share/icons, every $XDG_DATA_DIRS icons directory restricted to */apps/* and */devices/*, and /usr/share/pixmaps at depth 1. It never reads GTK's /usr/share/icons/hicolor/icon-theme.cache, so `sudo gtk-update-icon-cache -f /usr/share/icons/hicolor` cannot be what fixes this on Omarchy 4. Confirmed on this workstation that walker and elephant are not installed (pacman -Q fails for both), and that the cited issue 2547 is titled 'Walker not showing icons for newly installed apps Omarchy 3.1', body says Omarchy 3.1, state CLOSED, so the source supports the record only for Omarchy 3. I also confirmed the shell rebuilds the index on every menu open via refreshIcons() in plugins/menu/Menu.qml and on desktop entry changes debounced by 750 ms, which is why a newly installed app usually needs no command at all. `omarchy restart shell` is a real route (/usr/share/omarchy/bin/omarchy-restart-shell carries omarchy:examples=omarchy restart shell) and `omarchy-restart-walker` did exist on the Omarchy 3 master tree, so both commands in the old fix are real even though the first two steps were not. The record's applies_to still lists omarchy-3 and omarchy-4 together and the corrected fix now labels the two branches rather than blending them. I left severity low and frequency very-common unchanged: the symptom stays common on plain Arch GTK desktops, and it is the mechanism rather than the prevalence that was wrong. NOT exercised: I did not install a package or restart the shell on this workstation, and I did not reproduce a blank icon, so the corrected fix is read from source rather than run.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Editing files under `/usr/share/applications` directly means your change is lost on the next package upgrade — use the `~/.local/share/applications/` copy shown above instead.

**Fix.**

On Omarchy 4, check the two things that actually decide the icon, then reopen the menu.

**1. Does the desktop entry name an icon?**

```bash
grep -n '^Icon=' /usr/share/applications/firefox.desktop
```

If the line is missing, copy the entry into your own directory and add it there rather than editing the packaged file:

```bash
cp /usr/share/applications/firefox.desktop ~/.local/share/applications/
sed -i '/^\[Desktop Entry\]/a Icon=firefox' ~/.local/share/applications/firefox.desktop
```

**2. Is the icon file somewhere the shell's index looks?**

The Omarchy 4 shell indexes only files under an `apps` or `devices` directory inside `$HOME/.icons`, `$HOME/.local/share/icons` or any `$XDG_DATA_DIRS` entry's `icons` directory, plus `/usr/share/pixmaps` at depth 1. Search all of those for the name in `Icon=`:

```bash
find /usr/share/icons ~/.local/share/icons ~/.icons \
     \( -path '*/apps/*' -o -path '*/devices/*' \) -iname 'firefox.*' 2>/dev/null
find /usr/share/pixmaps -maxdepth 1 -iname 'firefox.*' 2>/dev/null
```

Nothing found means the package did not install an icon under a name matching `Icon=`, and no cache rebuild will help. Find what it did install with `pacman -Ql <pkg> | grep -E 'icons|pixmaps'` and set `Icon=` to that name, or to the absolute path of the file.

**3. Reopen the menu.**

Press Super+Space, then Apps. The shell rebuilds its icon index on every menu open, and again about 750 ms after the desktop entry list changes, so a newly installed app picks up its icon with no command. Only if it is still blank after reopening:

```bash
omarchy restart shell
```

`omarchy restart shell` refuses to run while the session is locked.

**Plain Arch, and GTK applications on Omarchy:** GTK's own menus and file choosers do read the binary cache at `/usr/share/icons/hicolor/icon-theme.cache`, and a package that installed icons without triggering a cache update leaves it stale. Rebuild it there:

```bash
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor
```

That has no effect on the Omarchy 4 launcher, which never reads that file.

**Omarchy 3.x only:** the launcher was Walker, and the restart command was `omarchy-restart-walker`.

**Verify.** Open the Omarchy menu with Super+Space, go to Apps, and the application shows its real icon. If it does not, `find` in step 2 prints the icon file whose basename matches the `Icon=` value, and `journalctl --user -b` shows no `QML QQuickImage ... Cannot open` line naming it. On plain Arch or for GTK applications, `gtk-update-icon-cache -f` exits 0 and the GTK application menu picks the icon up.

Sources: <https://github.com/omacom/omarchy/issues/2547> · <https://github.com/omacom/omarchy/blob/quattro/shell/services/AppLibrary.qml> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/menu/Menu.qml>

---

## Fix nerd-font icons rendering as empty boxes or tofu in the bar and menus

`nerd-font-icons-render-as-boxes-stale-fontconfig-cache` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Menu and bar entries show a broken-character box instead of an icon, while other entries in the same menu render fine. Classic case: the Update > Omarchy row shows tofu where every other row (Channel, Config, Extra Themes) has a proper glyph. The glyph really is present in the font file — `fc-scan` and fontTools both find it — so it looks like a missing-glyph bug that isn't.

**Cause.** Stale fontconfig caches. Old cache-format directories (`cache-7`, `cache-9`, `cache-10`, ...) left behind by previous fontconfig upgrades cause the cache builder to produce an incomplete charset bitmap for a font. In the canonical report, `omarchy.ttf` indexed only its ASCII codepoints and silently dropped the `U+E900` private-use entry, so pango fell back to a non-nerd font and drew tofu. A related but distinct cause is a codepoint from the old Nerd Font v2 private-use range that the v2-to-v3 remap relocated — those genuinely do not resolve on current Nerd Font builds.

**Fix.**

Inspect the cached charset — a missing page means a stale cache, not a missing glyph:

```bash
fc-list -v omarchy | grep -A5 charset
# a healthy result has a line starting  00e9:  for U+E900
```

Nuke every cache generation and rebuild:

```bash
rm -rf ~/.cache/fontconfig/*
fc-cache -fv
```

Then restart whatever draws the glyph:

```bash
omarchy restart shell     # Omarchy 4
# omarchy restart walker  # Omarchy 3.x
```

If a system-wide cache is also stale:

```bash
sudo fc-cache -fv
```

And confirm the Nerd Font is actually installed:

```bash
fc-list | grep -i 'nerd font' | head
```

**Verify.** `fc-list :charset=e900 family` prints `omarchy`, `fc-list -v omarchy | grep -A5 charset` now includes the `00e9:` page, and `pango-view --text=$''` renders a glyph instead of a box.

Sources: <https://github.com/basecamp/omarchy/issues/6620>

---

## Fix broken launcher icons and a ghost Alacritty entry after the Quattro upgrade

`app-menu-broken-icons-after-quattro-upgrade` · severity: **low** · frequency: **common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After upgrading from Omarchy 3 to Quattro, custom launchers in the Apps menu have broken icons, and there is a dead Alacritty entry with a generic gear icon that launches nothing (even though alacritty is not installed). `journalctl --user` shows `QML QQuickImage ... Cannot open: file:///home/<user>/.local/share/applications/icons/GitHub.png`.

**Cause.** `omarchy-upgrade-to-quattro` does not move the legacy icon directory aside. It moves twenty *named* stock PNGs out of `~/.local/share/applications/icons` into `~/.local/share/applications/icons.omarchy-upgrade-to-quattro.<timestamp>.bak` with `mv -f "$legacy_icons_dir/$icon" "$legacy_icons_backup/"`, then runs `rmdir` on both directories, which succeeds only if they are empty. Any PNG you put there yourself is left exactly where it was. Custom `.desktop` files survive the upgrade, so an entry whose `Icon=` is an absolute path to one of those twenty names is now dangling, and the Quickshell shell logs `QML QQuickImage ... Cannot open: file:///home/<user>/.local/share/applications/icons/GitHub.png`. The Alacritty entry is a second defect in the same script. The upgrade first deletes `~/.local/share/applications/Alacritty.desktop` as part of a list of stale Omarchy 3 entries, then copies `default/alacritty/Alacritty.desktop` back guarded only on `[[ ! -f $HOME/.local/share/applications/Alacritty.desktop ]]`, a test on the file it has just removed, so the guard always passes. There is no check that `alacritty` is installed, unlike `omarchy-refresh-applications`, which does guard on `omarchy-cmd-present alacritty`. The Apps menu lists the entry regardless of its `TryExec=alacritty`, and selecting it launches nothing.

> **Audit corrected this record.** Both defects are still present in omarchy 4.0.2-1 on this workstation. I read /usr/share/omarchy/bin/omarchy-upgrade-to-quattro lines 2169 to 2224 and confirmed the same content on the upstream quattro branch. The record's cause was imprecise in one way that changes the fix: the script does not move the legacy icon directory aside, it moves twenty specifically named stock PNGs out of it and then rmdirs the directory only if that emptied it, so a user's own PNGs are untouched and a dangling path can only be one of those twenty names. I also found a detail the record missed that strengthens it: the same script deletes ~/.local/share/applications/Alacritty.desktop in an earlier cleanup loop and then copies it back guarded on `! -f` of the file it just deleted, so the guard always passes and the ghost entry is created on every upgrade rather than only sometimes. Cited issue 6883 was read in full, is OPEN, and supports every claim the record makes including the exact mv line and the QQuickImage log text. The larger correction is to the fix. omarchy-settings 4.0.2-1 ships 18 of the 20 legacy icons as themed icons under /usr/share/icons/hicolor/*/apps/, which I verified by find plus pacman -Qo (windows.png, basecamp.png, chatgpt.png and others are owned by omarchy-settings 4.0.2-1), so rewriting the entry to the icon name is durable while restoring PNGs into a directory Omarchy no longer maintains is not. Only GitHub.png and Battle.net.png have no packaged equivalent, which is also the correct scope for the danger note. I corrected the danger accordingly, since the old text claimed the backup was the only copy of everything. NOT exercised: this workstation has no icons.omarchy-upgrade-to-quattro.*.bak directory and no Alacritty.desktop, alacritty is not in PATH, and the dangling scan from the record prints nothing here, so this machine was never upgraded through that path and the symptom was not reproduced live. I did not run the upgrade script. Severity low and frequency common were left alone: the consequence is cosmetic plus one dead menu entry, and it hits anyone who upgraded rather than installed fresh.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `GitHub.png` and `Battle.net.png` exist nowhere else on Omarchy 4, so `icons.omarchy-upgrade-to-quattro.*.bak` is the only copy of those two. Do not delete that directory until every entry that referenced them has been restored or rewritten. The other eighteen names are shipped by `omarchy-settings` and can be recovered with `pacman -S omarchy-settings` at any time.

**Fix.**

**1. Find the dangling absolute icon paths.**

```bash
grep -h '^Icon=/' ~/.local/share/applications/*.desktop | sed 's/^Icon=//' \
  | while read -r p; do [[ -e $p ]] || echo "MISSING: $p"; done
```

**2. Point the entry at the packaged icon name, not at a restored file.**

`omarchy-settings` ships 18 of those 20 legacy icons as themed icons under `/usr/share/icons/hicolor/*/apps/`, lowercased with spaces turned into hyphens: `basecamp`, `chatgpt`, `cliamp`, `disk-usage`, `docker`, `google-contacts`, `google-maps`, `google-messages`, `google-photos`, `hey`, `imv`, `retro-gaming`, `whatsapp`, `windows`, `x`, `youtube`, `zoom`, and `omarchy-discord` for Discord. Rewriting the entry to the name survives future upgrades, because `~/.local/share/applications/icons` is no longer a directory Omarchy maintains:

```bash
sed -i 's|^Icon=.*/applications/icons/windows\.png$|Icon=windows|' \
  ~/.local/share/applications/windows-vm.desktop
```

Confirm the name resolves before trusting it:

```bash
find /usr/share/icons -path '*/apps/*' -iname 'windows.*'
```

**3. Restore from the backup only for the two with no packaged equivalent.**

`GitHub.png` and `Battle.net.png` ship nowhere on Omarchy 4, so the `.bak` directory is the only copy of those:

```bash
ls -d ~/.local/share/applications/icons.omarchy-upgrade-to-quattro.*.bak
mkdir -p ~/.local/share/applications/icons
cp ~/.local/share/applications/icons.omarchy-upgrade-to-quattro.*.bak/GitHub.png \
   ~/.local/share/applications/icons/
```

If no `.bak` directory exists, the upgrade found none of the twenty names to move and your dangling path points at something you added yourself, which the upgrade never touched.

**4. Remove the ghost Alacritty entry.**

```bash
command -v alacritty >/dev/null || rm -f ~/.local/share/applications/Alacritty.desktop
update-desktop-database ~/.local/share/applications
```

The Apps menu's own remove action runs `omarchy-remove-launcher-entry Alacritty Alacritty`, which does the same delete plus the database refresh for a user owned entry.

**5. Refresh the menu.**

The shell watches `~/.local/share/applications`, so the removed entry disappears and the icon index rebuilds on the next menu open with no restart. Only if an icon is still stale after reopening the menu:

```bash
omarchy restart shell
```

`omarchy restart shell` refuses to run while the session is locked.

**Verify.** The loop in step 1 prints no `MISSING:` lines. The Apps menu under Super+Space shows real icons for your custom launchers and no Alacritty entry. Reopening the menu adds no new `QQuickImage Cannot open` lines to `journalctl --user -f`.

Sources: <https://github.com/omacom/omarchy/issues/6883> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-upgrade-to-quattro> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-refresh-applications>

---

## Change the bar's font face and its size (two different commands)

`bar-font-and-size-not-changing-after-font-set` · severity: **low** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy font set "CaskaydiaMono Nerd Font"` changes the terminals but the top bar keeps rendering in the old face. Or the face changes but the bar text is exactly the same size no matter which font you pick, so "the font is too small in the bar" never gets better. Sometimes `omarchy font set` exits 0 and the bar still never updates, with nothing printed to explain why.

**Cause.** Two different knobs that people conflate. `bin/omarchy-font-set` only sets the **family**: it seds the four terminal configs and writes `~/.config/fontconfig/fonts.conf` with a `prepend_first`/`binding="strong"` rule on the generic `monospace`, then calls `omarchy-restart-shell`. The Quickshell bar resolves `monospace` through fontconfig once, at process start, so that restart is what makes the face take — and `omarchy-restart-shell` refuses to run while the session is locked (`Refusing to restart Omarchy shell while the session is locked.`) and exits non-zero, which `omarchy-font-set` neither checks nor reports. **Size** is not a font-set concern at all: it is `[font] base-size` in `~/.config/omarchy/shell.toml`, the rem root every `Style.font.*` token derives from, which is what `bin/omarchy-display-text-size` writes. That file layers over the theme's generated `shell.toml`, so it survives theme switches, and the shell watches it — size changes re-flow live with no restart.

> **Audit corrected this record.** Nearly all verified. bin/omarchy-font-set only sets the family: it seds alacritty.toml, kitty.conf, ghostty/config and foot.ini, writes ~/.config/fontconfig/fonts.conf with exactly a `prepend_first` / `binding="strong"` edit on the generic `monospace` pattern, then calls omarchy-restart-shell without testing its status. bin/omarchy-restart-shell does print "Refusing to restart Omarchy shell while the session is locked." and `exit 1` when a live locker reports secure — so the silent no-op is real. bin/omarchy-display-text-size is exactly as described: [font] base-size in ~/.config/omarchy/shell.toml as the rem root, GTK text-scaling-factor quantized against the interface font point size, terminal pt anchored 12px -> 9pt, integer 9-20 enforced, `reset` returning 12px/1.0/9pt, and the no-arg form printing px / factor / pt. shell.toml.tpl confirms `base-size = 12` with commented per-token overrides including `# icon = 14`, and [bar] carries scale-with-font = true, size-horizontal = 26, size-vertical = 28 with the same top/bottom vs left/right semantics. One wrong claim: "Only scale-with-font, size-horizontal and size-vertical are read from [bar] — every other key there is silently ignored." The generated [bar] section also carries background, background-alpha, text and active, all of which the shell reads; a reader following that sentence would wrongly conclude they cannot set bar colours in ~/.config/omarchy/shell.toml.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `omarchy display text size` also rewrites the point size in `~/.config/alacritty/alacritty.toml`, `~/.config/kitty/kitty.conf`, `~/.config/ghostty/config` and `~/.config/foot/foot.ini`, and sets GNOME's `text-scaling-factor`. If you hand-tuned any of those, copy them first: `cp ~/.config/ghostty/config ~/ghostty.config.bak`. `omarchy font set` separately rewrites `~/.config/fontconfig/fonts.conf` from scratch every time it runs, discarding anything you put there by hand.

**Fix.**

Keep every command as written. Correct the [bar] sentence: alongside `scale-with-font`, `size-horizontal` (height of a top/bottom bar) and `size-vertical` (width of a left/right bar), the [bar] section also carries the surface colours the shell reads — `background`, `background-alpha`, `text` and `active` — and those layer from ~/.config/omarchy/shell.toml over whatever the theme generated just like the sizes do. Only keys the shell does not know are ignored. Confirm the merged sections with:

```bash
sed -n '/^\[bar\]/,/^\[/p' ~/.local/state/omarchy/current/theme/shell.toml
```

**Verify.** `fc-match monospace` names your chosen family, and the bar renders in it after `omarchy restart shell`. `omarchy display text size` reports the new px value, and the bar's height and type change without a restart.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-font-set> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-display-text-size> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-restart-shell> · <https://github.com/basecamp/omarchy/blob/quattro/default/themed/shell.toml.tpl> · <https://github.com/basecamp/omarchy/issues/6587>

---

## Set a cursor theme that Hyprland, GTK, Qt and XWayland apps all agree on

`cursor-theme-not-following-theme-or-xwayland` · severity: **low** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** The mouse pointer stays the default white arrow no matter which Omarchy theme you set — it never changes with the theme. Inside XWayland clients (Steam and Proton games, JetBrains IDEs, older Electron apps) it is a different pointer again: the black X11 "X", or a giant pointer, or nothing at all. `hyprctl setcursor <theme> 24` reports success but only some apps change.

**Cause.** Omarchy themes carry no cursor. There is no cursor key in `colors.toml` — the `cursor` key that `omarchy-theme-color` resolves is the *terminal text* cursor, derived from `bright_foreground` — and nothing in `post_theme_commands` touches XCursor. Omarchy exports only a size, in `/usr/share/omarchy/default/hypr/envs.lua`: `hl.env("XCURSOR_SIZE", "24")` and `hl.env("HYPRCURSOR_SIZE", "24")`, with no `XCURSOR_THEME` and no `hyprctl setcursor`. So the pointer is whatever the `default` cursor theme resolves to. Three mechanisms then disagree: since Hyprland 0.37 `hyprctl setcursor` accepts **hyprcursor** themes only and legacy xcursor themes must come from `XCURSOR_THEME`/`XCURSOR_SIZE`; GTK reads its own `gtk-cursor-theme-name` setting (which is why the wiki says setcursor "will set the theme for everything except GTK"); and XWayland clients read the X root resource the compositor publishes from those env vars, which `hl.env` only reaches if it is set before the client starts.

> **Audit corrected this record.** The cause is fully verified: default/hypr/envs.lua exports only `hl.env("XCURSOR_SIZE", "24")` and `hl.env("HYPRCURSOR_SIZE", "24")` with no XCURSOR_THEME and no hyprctl setcursor; nothing in post_theme_commands touches XCursor; omarchy-theme-color derives `cursor` from bright_foreground (terminal cursor, not pointer); the hyprctl wiki says setcursor "Will set the theme for everything except GTK" and "since 0.37.0, this only accepts hyprcursor themes. For legacy xcursor themes, use the XCURSOR_THEME and XCURSOR_SIZE env vars"; cursor:sync_gsettings_theme defaults to true; install/user/hardware/fix-nouveau-cursor.sh appends the identical no_hardware_cursors block to ~/.config/hypr/looknfeel.lua; and hypr.monitors really is required before hypr.autostart in config/hypr/hyprland.lua, next to the GDK_SCALE line. Two concrete errors in the fix: (a) `xcursor-breeze` is not an Arch package — the xcursor-* packages in Extra are xcursor-comix, xcursor-themes, xcursor-vanilla-dmz(-aa) only; Breeze cursors come from `breeze-cursors`, and that package installs `breeze_cursors` and `Breeze_Light`, not `Breeze_Snow` (the `breeze` package ships no cursors at all). (b) `sudo pacman -Syu <pkg>` is aborted on Omarchy 4 by default/libalpm/hooks/00-omarchy-update-guard.hook -> omarchy-update-pacman-guard, which refuses any transaction carrying both S and u with "Woah partner...".
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Replace the install step and the theme name:

```bash
ls -d /usr/share/icons/*/cursors 2>/dev/null
omarchy update                     # syncs+upgrades; a direct `pacman -Syu` is refused by Omarchy's ALPM guard
sudo pacman -S breeze-cursors      # installs /usr/share/icons/breeze_cursors and /usr/share/icons/Breeze_Light
```

Then use the real theme name everywhere (`breeze_cursors`, or `Breeze_Light`):

```bash
cat >> ~/.config/hypr/monitors.lua <<'EOF'

-- Cursor theme. hl.env only reaches processes Hyprland starts after this line.
hl.env("XCURSOR_THEME", "breeze_cursors")
hl.env("XCURSOR_SIZE", "24")
EOF
```

Only set HYPRCURSOR_THEME/HYPRCURSOR_SIZE if you actually installed a hyprcursor theme (e.g. from the AUR); pointing it at an xcursor-only name just falls back. Then:

```bash
gsettings set org.gnome.desktop.interface cursor-theme 'breeze_cursors'
gsettings set org.gnome.desktop.interface cursor-size 24
mkdir -p ~/.local/share/icons/default
printf '[Icon Theme]\nInherits=breeze_cursors\n' > ~/.local/share/icons/default/index.theme
```

Log out and back in — the rest of the record (no_hardware_cursors block, log-out requirement for XWayland) is correct as written.

**Verify.** `hyprctl getoption cursor:no_hardware_cursors` reports what you set, and `tr '\0' '\n' < /proc/$(pgrep -x Hyprland)/environ | grep XCURSOR` shows your theme. Open a native app, a GTK app and an XWayland app (`steam` or `xterm`) side by side — all three draw the same pointer at the same size.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/basecamp/omarchy/blob/quattro/install/user/hardware/fix-nouveau-cursor.sh> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/FAQ/> · <https://wiki.archlinux.org/title/Cursor_themes>

---

## Stop Foot's font size resetting to 9pt every time you change the font family

`foot-font-size-reset-to-9-after-font-change` · severity: **low** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After picking a font in Style > Font (or running `omarchy font set`), the Foot terminal is suddenly much smaller than kitty/alacritty/ghostty. `grep '^font=' ~/.config/foot/foot.ini` shows `font=MesloLGLDZ Nerd Font:size=9` even though you had previously set a larger size with `omarchy display text size`.

**Cause.** The Foot branch of `bin/omarchy-font-set` rewrites the whole `font=` line with a hardcoded size: `sed -i "s/^font=.*/font=$font_name:size=9/g" ~/.config/foot/foot.ini`. The kitty, alacritty and ghostty branches only rewrite the family, so their size survives. The two commands fight: picking a font in the GUI silently undoes `omarchy display text size`.

**Fix.**

Re-apply the display text size after every font change:

```bash
omarchy display text size 16
grep '^font=' ~/.config/foot/foot.ini
```

Or fix the size directly in `~/.config/foot/foot.ini`:

```bash
sed -i 's/^font=\(.*\):size=.*/font=\1:size=12/' ~/.config/foot/foot.ini
```

To stop it recurring, add a post-font hook that re-applies your size:

```bash
mkdir -p ~/.config/omarchy/hooks/font-set.d
cat > ~/.config/omarchy/hooks/font-set.d/20-foot-size.sh <<'EOF'
#!/bin/bash
sed -i 's/^font=\(.*\):size=.*/font=\1:size=12/' ~/.config/foot/foot.ini
EOF
chmod +x ~/.config/omarchy/hooks/font-set.d/20-foot-size.sh
```

Foot does not hot-reload the font size, so open a new Foot window to see it.

**Verify.** `grep '^font=' ~/.config/foot/foot.ini` shows your intended `:size=N`, and a newly opened Foot window is visually the same text size as kitty/alacritty/ghostty.

Sources: <https://github.com/basecamp/omarchy/issues/6957>

---

## Make Ghostty honor its own font-family instead of the global Omarchy font

`ghostty-explicit-font-ignored-by-global-fontconfig` · severity: **low** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`, `wayland`

**Symptom.** `~/.config/ghostty/config` sets `font-family = JetBrainsMono Nerd Font Mono` and `ghostty +show-config` confirms it, but the terminal visibly renders in the Omarchy system font. `ghostty +show-face --string='abc012Il1'` resolves to the global font instead, e.g. `file: "/usr/share/fonts/TTF/CaskaydiaCoveNerdFontMono-Regular.ttf"`.

**Cause.** Same root as the family-hijack bug: `omarchy font set` writes a strong `prepend_first` assignment for `monospace` into `~/.config/fontconfig/fonts.conf`. Because `48-guessfamily.conf` appends the generic `monospace` to any family name containing `mono`, Ghostty's explicit `JetBrainsMono Nerd Font Mono` request arrives carrying `monospace`, matches the rule, and the global font is prepended ahead of it with a strong binding. The result is that the global Style > Font selection behaves as an override rather than a default.

> **Audit corrected this record.** Same confirmed root cause as the family-hijack record - the strong prepend_first rule on `monospace` is verbatim in bin/omarchy-font-set, and Ghostty's `?` include prefix is correct optional-include syntax. Diagnostics are all valid. Two gaps: the referenced fonts.conf rewrite is undone by the next `omarchy font set` (the script regenerates the file unconditionally), so the fix needs the font-set hook; and `pkill -x ghostty` closes every Ghostty window including any with unsaved work in running programs, which is stated without warning.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Moving `~/.config/fontconfig/fonts.conf` aside also drops the global Style > Font selection for every app that asks for generic `monospace`.

**Fix.**

Diagnose:

```bash
ghostty +show-config | grep font-family
ghostty +show-face --string='abc012Il1'
fc-match "JetBrainsMono Nerd Font Mono"
```

Quick proof that fontconfig, not Ghostty, is the culprit:

```bash
mv ~/.config/fontconfig/fonts.conf{,.off}
ghostty +show-face --string='abc012Il1'   # now resolves to JetBrainsMono
mv ~/.config/fontconfig/fonts.conf{.off,}
```

Apply the alias/prefer rewrite **via a font-set hook**, not by hand. `omarchy-font-set` rewrites `~/.config/fontconfig/fonts.conf` from scratch on every font change, so a hand-edit survives only until the next Style > Font pick:

```bash
mkdir -p ~/.config/omarchy/hooks/font-set.d
cat > ~/.config/omarchy/hooks/font-set.d/20-font-alias.sh <<'EOF'
#!/bin/bash
font="$1"
[[ -n $font ]] || exit 0
mkdir -p ~/.config/fontconfig
cat > ~/.config/fontconfig/fonts.conf <<XML
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias binding="strong">
    <family>monospace</family>
    <prefer><family>$font</family></prefer>
  </alias>
</fontconfig>
XML
fc-cache -f
EOF
chmod +x ~/.config/omarchy/hooks/font-set.d/20-font-alias.sh
fc-cache -f
```

Then fully restart Ghostty - it reads its face only at startup. **This closes every Ghostty window, so save your work first** (`pkill -SIGUSR2 ghostty` reloads config but will not re-resolve the font face):

```bash
pkill -x ghostty
```

If `fc-match monospace` still returns JetBrainsMono, `/etc/fonts/conf.d/50-omarchy.conf`'s `mode="assign"` generic rule is still winning - see the `omarchy-font-set-hijacks-named-mono-families` fix for the user-tree override that sorts after it.

**Verify.** `ghostty +show-face --string='abc012Il1'` reports the file path of the font named in `~/.config/ghostty/config`, while `fc-match monospace` still returns the Omarchy global font.

Sources: <https://github.com/basecamp/omarchy/issues/5675> · <https://github.com/basecamp/omarchy/issues/8404>

---

## Understand why a git-installed theme leaves Neovim and terminals unthemed

`installed-theme-neovim-and-terminal-configs-stripped` · severity: **low** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** You install a community theme with `omarchy theme install <git-url>`, and the bar, terminal palette and shell surfaces follow it — but Neovim keeps its stock colorscheme, terminal niceties like inactive border colors are generic, and VS Code is unstyled. `omarchy theme update` appears to succeed but nothing on the desktop changes.

**Cause.** Deliberate, as of commit ef6d9e6 / PR #7884 ("Stop an installed theme from running code", shipped in 4.0.0.r1803). `omarchy-theme-set` now drops every `.lua`, terminal config (`kitty.conf`, `foot.ini`, `ghostty.conf`, `alacritty.toml`) and `vscode.json` from themes installed from a git repo, then regenerates them from `$OMARCHY_PATH/default/themed/*.tpl`. So a repo theme cannot ship a Neovim integration at all. Separately, `omarchy theme update` only runs `git pull` inside the clone and never re-stages, so pulled changes stay invisible until you re-select the theme — and when the re-stage happens, the same files are stripped again.

> **Audit corrected this record.** The cause is confirmed in detail. bin/omarchy-theme-set defines `INSTALLED_THEME_DENIED=(alacritty.toml foot.ini ghostty.conf kitty.conf vscode.json)`, is_denied_installed_file additionally returns true for every *.lua, and theme_came_from_a_repo gates it on a .git directory - the in-source comment even says a repo theme 'cannot supply Lua, a terminal config, or vscode.json'. The user-template path ~/.config/omarchy/themed is confirmed in omarchy-theme-set-templates and docs/theming.md ('User templates in ~/.config/omarchy/themed/*.tpl are processed before the built-in templates'). One factual error: bin/omarchy-theme-update takes NO argument - it iterates omarchy-theme-extras and git-pulls every user-installed git theme - so `omarchy theme update <name>` silently ignores the name.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The stripping is a deliberate security boundary — installed themes must not be able to run code. Do not defeat it by hand-copying `.lua` files out of a stranger's theme repo into your nvim config without reading them first.

**Fix.**

`omarchy-theme-update` takes **no arguments** - it git-pulls every user-installed git theme (those listed by `omarchy-theme-extras`). Passing a name is silently ignored. Force the pulled theme to actually re-stage:

```bash
omarchy theme update          # pulls ALL git themes
omarchy theme set <name>      # re-stage; theme update alone never re-stages
```

The stripping is deliberate and confirmed in `bin/omarchy-theme-set`: every `*.lua` plus `INSTALLED_THEME_DENIED=(alacritty.toml foot.ini ghostty.conf kitty.conf vscode.json)` is dropped from any theme with a `.git` directory, then regenerated from `$OMARCHY_PATH/default/themed/*.tpl`. Dropped files are named on stderr, so watch that output:

```bash
omarchy theme set <name> 2>&1 | grep -i ignored
```

For the Neovim colours the author intended, install their colorscheme plugin yourself. In `~/.config/nvim/lua/plugins/theme.lua`:

```lua
return {
  { "tahadx/noir.nvim", lazy = false, priority = 1000 },
  { "LazyVim/LazyVim", opts = { colorscheme = "noir" } },
}
```

then inside nvim: `:Lazy sync`

For terminal details the stock template does not cover, put your own template in the user templates directory. These are processed *before* the built-ins, and a user template sharing an output filename causes the built-in to be skipped entirely:

```bash
mkdir -p ~/.config/omarchy/themed
# e.g. ~/.config/omarchy/themed/kitty.conf.tpl
omarchy theme refresh
```

**Verify.** `omarchy theme set <name>` then `ls ~/.local/state/omarchy/current/theme/` shows regenerated `kitty.conf`/`foot.ini`; nvim opens with the colorscheme you installed rather than the LazyVim default.

Sources: <https://github.com/basecamp/omarchy/issues/7942> · <https://learn.omacom.io/2/the-omarchy-manual/92/making-your-own-theme>

---

## Fix VS Code losing its color theme when you use a community Omarchy theme

`installed-theme-vscode-json-denied` · severity: **low** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Every stock theme retints VS Code, VSCodium or Cursor, but a theme installed with `omarchy theme install` does not — and worse, VS Code drops back to Dark+ entirely because `"workbench.colorTheme"` has been removed from `settings.json`. `ls ~/.local/state/omarchy/current/theme/vscode.json` says `No such file or directory`, even though the theme's repo obviously contains one.

**Cause.** `vscode.json` names an extension that bin/omarchy-theme-set-vscode would install with --install-extension, and a VS Code extension is arbitrary JavaScript, so it sits on INSTALLED_THEME_DENIED in bin/omarchy-theme-set alongside alacritty.toml, foot.ini, ghostty.conf, kitty.conf and every *.lua, and is dropped from any theme whose directory contains a .git — exactly what `omarchy theme install` leaves behind. What you get instead is Omarchy's own generated theme: set_theme() falls to its `elif [[ -f $GENERATED_THEME ]]` branch, renders default/themed/vscode-theme.json.tpl into the staged theme, registers it as the local extension `local.omarchy-theme`, and writes `"workbench.colorTheme": "Omarchy"`. So the editor still retints, just with a mechanical palette instead of the author's hand-tuned extension theme. The key is stripped out of settings.json entirely — dropping the editor to Dark+ — only in the last branch, when neither vscode.json nor the generated vscode-theme.json exists, which means the theme shipped no colors.toml either (and none could be derived from an alacritty.toml).

> **Audit corrected this record.** The staging half is correct: vscode.json is on INSTALLED_THEME_DENIED in bin/omarchy-theme-set and is dropped from any theme directory containing .git, which is what `omarchy theme install` leaves, so ~/.local/state/omarchy/current/theme/vscode.json is genuinely absent. The four toggle flag names are exact (skip-vscode-theme-changes, skip-vscode-insiders-theme-changes, skip-codium-theme-changes, skip-cursor-theme-changes), `omarchy-toggle <flag> on` and the verbless flip are correct, and the settings paths match. But the symptom and cause are wrong about the consequence. set_theme() in bin/omarchy-theme-set-vscode has an intermediate branch the record skips: `elif [[ -f $GENERATED_THEME ]]` where GENERATED_THEME is ~/.local/state/omarchy/current/theme/vscode-theme.json — and default/themed/vscode-theme.json.tpl exists, so that file is generated for every theme that has a colors.toml (which a cloned theme IS allowed to ship, and which is even synthesized from alacritty.toml when absent). In that branch the script installs the local `local.omarchy-theme` extension and sets workbench.colorTheme to "Omarchy". So VS Code does retint after installing a cloned theme — with Omarchy's mechanically generated palette rather than the author's chosen extension. The `elif [[ -f $settings_path ]]` branch that seds the key out is reached only when there is neither vscode.json nor vscode-theme.json, i.e. a theme with no colors.toml at all — that, not the vscode.json denial, is what drops the editor to Dark+.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Removing `.git` promotes the whole cloned tree to a hand-written theme, so Omarchy will then stage and act on every file in it — `hyprland.lua` and `gum_env.lua` are executed by Hyprland at login, `neovim.lua` by Neovim at startup, the terminal configs name the program your terminal launches, and `vscode.json` causes an extension to be installed. Read those files before doing it. It also breaks `omarchy theme update` for that theme.

**Fix.**

First find out which of the two situations you are in:

```bash
ls ~/.local/state/omarchy/current/theme/vscode.json ~/.local/state/omarchy/current/theme/vscode-theme.json
grep -n 'workbench.colorTheme' ~/.config/Code/User/settings.json
```

If vscode-theme.json exists, VS Code is on the generated "Omarchy" theme. To get the author's theme instead, install it yourself and pin it:

```bash
jq -r '.name, .extension' ~/.config/omarchy/themes/<name>/vscode.json
code --install-extension <publisher.extension>
omarchy-toggle-enabled skip-vscode-theme-changes && echo already-set || echo not-set
omarchy-toggle skip-vscode-theme-changes on
```

then set `"workbench.colorTheme": "<Theme Name>"` in ~/.config/Code/User/settings.json.

If BOTH files are missing, the theme has no colors.toml and that is why the key was deleted — give it one and the generated theme comes back:

```bash
cp /usr/share/omarchy/themes/tokyo-night/colors.toml ~/.config/omarchy/themes/<name>/colors.toml
omarchy theme set <name>
```

The re-file-as-your-own escape hatch is correct as written (a plain directory with no .git is staged in full, vscode.json included).

**Verify.** `ls ~/.local/state/omarchy/current/theme/vscode.json` exists (or the toggle is set), `grep colorTheme ~/.config/Code/User/settings.json` still shows a theme name after `omarchy theme set <name>`, and VS Code opens in the expected colours.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set-vscode> · <https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md> · <https://github.com/basecamp/omarchy/issues/7884>

---

## Fix a theme that applies from the CLI but never appears in the theme picker

`theme-missing-from-picker-no-preview-image` · severity: **low** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy theme set my-theme` works, but the theme is simply not in the picker at `Super+Ctrl+Shift+Space` (Style > Theme) — no tile, no blank tile, nothing. Or the tile is there but blank, or shows an image you replaced days ago. The background picker (`Super+Ctrl+Space`) shows blank tiles for wallpapers you just added.

**Cause.** `bin/omarchy-theme-switcher` does not list theme directories. It builds a directory of symlinks at `~/.cache/omarchy/theme-selector/previews`, one per theme, and hands *that* to `omarchy-menu-images`. A theme only gets a symlink if `find_preview` finds something: a top-level `preview.png` / `.jpg` / `.jpeg` / `.webp` / `.gif` / `.bmp`, or failing that the first image inside `backgrounds/`. A theme with neither is never added to the directory, so it does not exist as far as the picker is concerned. Rebuilds are gated on a "fast signature" built from the mtimes of the theme *directories* only, so a preview that changed without the directory's mtime changing can leave the cache stale. Wallpaper thumbnails are a second, separate cache under `~/.cache/omarchy/image-selector`, keyed by an md5 of the directory list and warmed by `omarchy-theme-bg-cache`, which `omarchy-theme-set` fires in the background at the end of every theme change.

> **Audit corrected this record.** The cache mechanics are exact. bin/omarchy-theme-switcher builds ~/.cache/omarchy/theme-selector/previews as a symlink directory and hands only that to omarchy-menu-images; find_preview tries preview.png, .jpg, .jpeg, .webp, .gif, .bmp at maxdepth 1 and then falls back to `find backgrounds -maxdepth 1 ... | sort | head -n 1`; a theme with neither gets no symlink and so does not exist to the picker; and the rebuild is gated on a fast signature built from `stat -Lc '%Y'` of the theme directories only, so a preview replaced in place can leave the cache stale. omarchy-theme-bg-cache is the separate warmer (`omarchy-menu-images --cache-only` over the theme backgrounds plus ~/.config/omarchy/backgrounds/<theme>) and omarchy-theme-set fires it in the background at the end of every theme change. cp -a from /usr/share/omarchy/themes/tokyo-night is the right Omarchy-4 path. Two errors: `omarchy plymouth preview` does not generate preview-unlock.png from unlock.png — bin/omarchy-plymouth-preview requires four arguments (<background-hex> <text-hex> <logo.png> <output-path>) and errors out otherwise; and the unlock picker lists a theme on preview-unlock.png alone (bin/omarchy-plymouth-list gates on that single file; unlock.png is what omarchy-plymouth-set-by-theme then needs to apply it, so both still matter, just not for listing).
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `~/.cache/omarchy/image-selector` also holds every wallpaper thumbnail the background picker has ever generated. Deleting it is safe but the next `Super+Ctrl+Space` regenerates all of them, which is slow and CPU-heavy on a large wallpaper collection — run `omarchy-theme-bg-cache` first and let it finish.

**Fix.**

Keep the cache steps as written (they are correct, including `rm -rf ~/.cache/omarchy/theme-selector ~/.cache/omarchy/image-selector`, `omarchy-theme-switcher --preload`, `omarchy-theme-bg-cache`). Replace the unlock-picker block with:

```bash
ls ~/.config/omarchy/themes/<name>/unlock.png ~/.config/omarchy/themes/<name>/preview-unlock.png
```

preview-unlock.png is what puts the theme in the Style > Unlock list; unlock.png is what omarchy-plymouth-set-by-theme applies. Generate the preview with all four arguments:

```bash
THEME=~/.config/omarchy/themes/<name>
omarchy-plymouth-preview \
  "$(omarchy-theme-color --file $THEME/colors.toml background)" \
  "$(omarchy-theme-color --file $THEME/colors.toml foreground)" \
  $THEME/unlock.png \
  $THEME/preview-unlock.png
```

**Verify.** `ls ~/.cache/omarchy/theme-selector/previews | grep <name>` returns a symlink, and `Super+Ctrl+Shift+Space` shows the theme with an image on its tile.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-switcher> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-bg-cache> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set> · <https://github.com/basecamp/omarchy/blob/quattro/manual/43-making-your-own-theme.md>

---

## Fix a theme switch always jumping back to the theme's first wallpaper

`theme-switch-always-restores-first-wallpaper` · severity: **low** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Each theme ships several wallpapers. You pick the third one for Tokyo Night, switch to Catppuccin, then switch back to Tokyo Night — and you get the first wallpaper again, not the one you chose.

**Cause.** `choose_theme_background` in `bin/omarchy-theme-set` compares `readlink` of `~/.local/state/omarchy/current/background` against the *new* theme's files. That symlink points into `current/theme/backgrounds/`, which the same script has just `rm -rf`'d and replaced, so the path can never match and it falls through to `backgrounds[0]`. There is also no per-theme record of the last choice anywhere on disk.

**Fix.**

There is no built-in per-theme memory yet. Record and restore it yourself with a theme-set hook:

```bash
mkdir -p ~/.config/omarchy/hooks/theme-set.d ~/.local/state/omarchy/bg-memory
cat > ~/.config/omarchy/hooks/theme-set.d/90-remember-bg.sh <<'EOF'
#!/bin/bash
set -euo pipefail
state=~/.local/state/omarchy
mem=$state/bg-memory
theme=$(cat "$state/current/theme.name")
want="$mem/$theme"
if [[ -f $want ]]; then
  candidate="$state/current/theme/backgrounds/$(cat "$want")"
  [[ -f $candidate ]] && omarchy-theme-bg-set "$candidate"
fi
EOF
chmod +x ~/.config/omarchy/hooks/theme-set.d/90-remember-bg.sh
```

And save your pick whenever you choose one:

```bash
theme=$(cat ~/.local/state/omarchy/current/theme.name)
basename "$(readlink ~/.local/state/omarchy/current/background)" \
  > ~/.local/state/omarchy/bg-memory/"$theme"
```

Simplest alternative if you only care about one wallpaper per theme: rename your preferred file so it sorts first inside the theme's `backgrounds/` directory:

```bash
cd ~/.config/omarchy/themes/<theme>/backgrounds
mv 3-favourite.jpg 0-favourite.jpg
omarchy theme set <theme>
```

**Verify.** `omarchy theme set catppuccin && omarchy theme set tokyo-night && omarchy theme bg current` reports the wallpaper you last chose for Tokyo Night, not the first sorted file.

Sources: <https://github.com/basecamp/omarchy/issues/7668>

---

## Stop the Plymouth/SDDM unlock screen reverting to default after every update

`unlock-screen-theme-reverts-after-omarchy-update` · severity: **low** · frequency: **common** · applies to: `arch`, `desktop`, `grub`, `laptop`, `omarchy`, `omarchy-4`, `systemd-boot`

**Symptom.** You pick a custom unlock screen via Style > Unlock and it applies. After the next `omarchy update`, the boot splash (including the LUKS password prompt) and the SDDM logout screen are back to the default green/yellow Omarchy design. `omarchy plymouth current` now reports `default`.

**Cause.** `omarchy-plymouth-set` writes the recolored assets straight into package-owned directories, `/usr/share/plymouth/themes/omarchy/` and `/usr/share/sddm/themes/omarchy/`, both owned by the `omarchy-settings` package. `omarchy update` runs `omarchy-update-system-pkgs`, which is `sudo pacman -Syu --noconfirm --overwrite '/usr/share/omarchy/*'`, and that upgrades `omarchy-settings` and restores those files to the shipped defaults. Neither directory is in the package's `backup` array, so pacman overwrites without leaving a `.pacnew`.

Unlike `omarchy theme set`, the plymouth setter persists no state anywhere. `omarchy-plymouth-current` works it out after the fact by byte-comparing the installed `/usr/share/plymouth/themes/omarchy/logo.png` against each theme's `unlock.png`, which is exactly why the reverted state reads back as `default`. Nothing re-applies the selection: `omarchy-update` calls `omarchy-update-system-pkgs`, then `omarchy-migrate`, then `omarchy-hook post-update`, and none of the shipped migrations or hooks restore a plymouth or sddm theme.

This is Omarchy 4's boot splash and SDDM greeter, not the session lock screen. The session lock on Omarchy 4 is an `ext-session-lock` surface drawn by `omarchy-shell` (Quickshell) and is styled by `~/.config/omarchy/shell.toml`, and `hyprlock` is not installed. SDDM is installed, enabled and active on Omarchy 4, so the SDDM half of this is real and not a leftover from another distro.

> **Audit corrected this record.** Checked every claim against the shipped scripts on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, sddm 0.21.0-7, plymouth 26.134.222-2) rather than against the issue text. Confirmed locally: `omarchy-plymouth-set` publishes into `/usr/share/plymouth/themes/omarchy` and `/usr/share/sddm/themes/omarchy`, `pacman -Qo` names `omarchy-settings 4.0.2-1` as the owner of both `logo.png` and `Main.qml`, and `pacman -Qii omarchy-settings` lists six backup files, none of them under those two directories, so pacman overwrites them silently on upgrade. Confirmed `omarchy-update` runs `omarchy-update-system-pkgs` (which is `sudo pacman -Syu --noconfirm --overwrite '/usr/share/omarchy/*'`), then `omarchy-migrate`, then `omarchy-hook post-update`, in that order, so a post-update hook is the right place and runs after the package that reverts the theme. Confirmed nothing re-applies it: the only two migrations mentioning plymouth are `1784917531.sh` (adds `initramfs_async=0`) and `1788025225.sh` (removes a retired `omarchy-plymouth-shutdown.service`), and neither restores a theme. Confirmed `omarchy-plymouth-current` holds no state and derives the answer by byte-comparing `logo.png`, which is why it reports `default` after a revert.

Confirmed the record is describing the right system, which the brief flagged as the risk. It does not name `hyprlock`, and the Omarchy 4 session lock is a separate thing: an `ext-session-lock` surface drawn by `omarchy-shell`. SDDM is genuinely installed, enabled and active here (`/etc/systemd/system/display-manager.service` points at `/usr/lib/systemd/system/sddm.service`), and `/usr/share/sddm/themes/omarchy` exists, so naming SDDM is correct rather than borrowed from another distro. The "Style > Unlock" path is real: `style.unlock` in `/usr/share/omarchy/default/omarchy/omarchy-menu.jsonc` runs `omarchy-plymouth-switcher` and then `omarchy-plymouth-set-by-theme`. `vantablack` is one of the 23 names `omarchy-plymouth-list` returns here.

Two defects in the fix. It re-applies unconditionally on every `omarchy update`, and `omarchy-plymouth-set` ends with `sudo limine-mkinitcpio`, so as written it adds a full initramfs and UKI rebuild to every update including ones where `omarchy-settings` was never upgraded. The corrected hook guards on `omarchy plymouth current`. It also never says the hook needs sudo: `omarchy-plymouth-set` carries `omarchy:requires-sudo=true`, refuses to run when `EUID` is 0, and calls `sudo` itself, so it can prompt for a password in the middle of an update and will do so under `omarchy update -y`. The `danger` field understated the consequence: on Omarchy 4 an interrupted rebuild is `limine-mkinitcpio` regenerating the UKI at `/boot/EFI/Linux/omarchy_linux.efi`, which risks an unbootable machine rather than an unreadable splash. Read issue 6864 in full: it is OPEN, created 2026-08-14 against 4.0.0rc5-1, and it supports every claim the record's cause makes.

Two smaller points left alone because the verdict schema has no field for them. `applies_to` carries `systemd-boot` and `grub`, and Omarchy 4 boots a UKI through Limine, so those two tags do not apply on Omarchy 4. The symptom says the revert follows "the next `omarchy update`" when it in fact follows the next update that upgrades `omarchy-settings`, which the `verify` field already states correctly, so `verify` carries the precise version. Severity `low` and frequency `common` both stand: the loss is cosmetic and recoverable, and it recurs on every `omarchy-settings` upgrade for anyone who set a custom unlock screen.

Not exercised: I did not run `omarchy update`, did not run `omarchy plymouth set-by-theme`, did not rebuild any initramfs, and did not install the hook. Everything above was read from the shipped scripts, `pacman -Q` output and the upstream issue. Whether the guarded hook completes without a password prompt inside a real update depends on the sudo timestamp surviving the pacman step, and that was not measured.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy plymouth set-by-theme` rewrites files inside the Plymouth theme directory and then rebuilds the initramfs. On Omarchy 4 that is `sudo limine-mkinitcpio`, which regenerates the UKI at `/boot/EFI/Linux/omarchy_linux.efi`, so an interrupted rebuild risks a machine that does not boot, not just an ugly splash. On a LUKS-encrypted machine the same rebuild is what carries the Plymouth password prompt, so keep a bootable USB around before experimenting. Do not run this concurrently with `omarchy update`, which is already holding `omarchy-update-lock` and may be rebuilding the initramfs itself, and do not add an unguarded re-apply to `post-update.d`, because that puts an initramfs rebuild into every update whether or not anything reverted.

**Fix.**

Record your choice and re-apply it after an update that reverted it. Save the selection:

```bash
mkdir -p ~/.local/state/omarchy
echo vantablack > ~/.local/state/omarchy/unlock.name
```

Add a post-update hook. `omarchy-hook` runs every non-`.sample` file in the directory with `bash`, so the name and the executable bit do not matter, but the guard does: `omarchy plymouth set-by-theme` rebuilds the initramfs, so re-applying blindly adds a `limine-mkinitcpio` run to every single update:

```bash
mkdir -p ~/.config/omarchy/hooks/post-update.d
cat > ~/.config/omarchy/hooks/post-update.d/50-replymouth.sh <<'EOF'
#!/bin/bash
name_file=~/.local/state/omarchy/unlock.name
[[ -f $name_file ]] || exit 0
want=$(cat "$name_file")
[[ -n $want ]] || exit 0
# Only re-apply when the package upgrade actually reverted it.
[[ "$(omarchy plymouth current)" == "$want" ]] && exit 0
omarchy plymouth set-by-theme "$want"
EOF
```

`omarchy plymouth set-by-theme` calls `omarchy-plymouth-set`, which is marked `requires-sudo` and runs `sudo plymouth-set-default-theme omarchy` plus `sudo limine-mkinitcpio` itself. It refuses to run under `sudo`, so leave the hook unprivileged. It can prompt for a password inside the update. If you run `omarchy update -y` unattended, expect that prompt, or re-apply by hand instead.

Manual re-apply any time:

```bash
omarchy plymouth set-by-theme vantablack
omarchy plymouth current
```

List what you can pick from, and reset to stock:

```bash
omarchy plymouth list
omarchy plymouth reset
```

Confirm what pacman owns, to see why it keeps reverting:

```bash
pacman -Qo /usr/share/plymouth/themes/omarchy/logo.png
pacman -Qo /usr/share/sddm/themes/omarchy/Main.qml
grep 'omarchy-settings' /var/log/pacman.log | tail -3
```

The hook itself survives updates: `~/.config/omarchy/hooks/post-update.d/` is user-owned and no package replaces it. The plymouth theme does not, which is the whole point of the hook. Upstream issue #8357's `always_copy_config_files` list does not cover `hooks/post-update.d`, so only a re-run of `omarchy-upgrade-to-quattro` would go near it. This is a workaround for an open upstream bug, not a setting, so drop the hook once upstream persists the selection itself.

**Verify.** `omarchy plymouth current` reports your theme immediately after an `omarchy update` that upgraded `omarchy-settings`, and `pacman -Qo /usr/share/plymouth/themes/omarchy/logo.png` still names `omarchy-settings` while the file's mtime is later than the upgrade line in `/var/log/pacman.log`. At the next boot the LUKS prompt shows the custom splash.

Sources: <https://github.com/omacom/omarchy/issues/6864>

---

## Fix `omarchy theme bg next` never advancing past the first wallpaper

`background-next-stuck-on-symlinked-backgrounds` · severity: **low** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy theme bg next` sets the first wallpaper and then does nothing on every subsequent press. `omarchy theme bg current` reports the same file every time. Only happens when `~/.config/omarchy/backgrounds/<theme>/` is a symlink into a dotfiles repo (stow, chezmoi).

**Cause.** A path-canonicalisation mismatch between two scripts, both confirmed unchanged in omarchy 4.0.2-1 and on the `quattro` branch. `/usr/bin/omarchy-theme-bg-set` line 12 stores the chosen background as `BACKGROUND="$(realpath "$1")"`, so the state symlink `~/.local/state/omarchy/current/background` points at the resolved path, such as `/home/u/dotfiles/walls/foo.jpg`. `/usr/bin/omarchy-theme-bg-next` builds its candidate list with `find -L "$HOME/.config/omarchy/backgrounds/$THEME_NAME/" ...`, which prints the path it walked rather than the resolved one, then string-compares each entry against a plain `readlink` of that state symlink. The strings never match, `INDEX` stays `-1`, and the script falls through to `BACKGROUNDS[0]` on every press.

The list is `sort -z`ed as one set and `~/.config` sorts before `~/.local`, so entry 0 is always a user background whenever that directory holds images. That is why the result is the same file every time rather than an alternation between two.

The same mismatch appears when the directory is real but the image files inside it are symlinks, which is what `stow` leaves when the tree is not folded. Stock theme backgrounds are unaffected because `~/.local/state/omarchy/current/theme/backgrounds/` is a real copied directory, so `realpath` of a stock background equals the path `find` prints and the lookup succeeds. `choose_theme_background` in `/usr/bin/omarchy-theme-set` has the identical comparison and the identical defect. There is no `omarchy-theme-bg-prev` on 4.0.2-1 or on `quattro`, so stepping backwards means picking a wallpaper directly.

> **Audit corrected this record.** Read `/usr/bin/omarchy-theme-bg-next`, `-bg-set`, `-bg-current`, `-bg-cache`, `-bg-switcher` and `/usr/bin/omarchy-theme-set` on this workstation at omarchy 4.0.2-1, and fetched `bin/omarchy-theme-bg-next` and the `quattro` file tree from `omacom/omarchy`. Every mechanical claim held. `omarchy-theme-bg-set` line 12 is still `BACKGROUND="$(realpath "$1")"`, `omarchy-theme-bg-next` still builds its list with `find -L` over `~/.config/omarchy/backgrounds/$THEME_NAME/` and `~/.local/state/omarchy/current/theme/backgrounds/` and still compares against a bare `readlink`, and `choose_theme_background` in `omarchy-theme-set` repeats it. I confirmed the asymmetry directly in a scratch directory under `/tmp`, with no omarchy command run: `find -L` printed the walked path and `realpath` printed the resolved one, both for a symlinked directory and for a symlinked file inside a real directory, so the defect is wider than the record said and the cause now covers both. I confirmed on this machine that the stock case is safe, because `realpath` of `~/.local/state/omarchy/current/theme/backgrounds/1-the-backwater.jpg` equals the path `find` prints and equals the current `readlink` of the state symlink. I also checked the sort order, since `sort -z` puts `~/.config` paths before `~/.local` ones in both `en_US.UTF-8` and `LC_ALL=C`, which is what makes entry 0 always a user background and the symptom a stuck file rather than an alternation. Issue 8594 supports the record almost verbatim, including the suggested patch, and issue 8508 supports the missing `prev` command, whose only comment points at unmerged pull requests. Corrections: the record said "you cannot step backwards", but `omarchy-theme-bg-switcher` and `omarchy-theme-bg-set <path>` both reach any wallpaper, so only the keybinding cycle is one-way. Paths are moved to the installed 4.0.2-1 form, the `cp` in the workaround gains `-L` so it cannot recreate the bug, and the danger names the symlink that `sed -i` would replace. Not exercised: no background command was run on this workstation, by instruction, so the end-to-end cycle was not reproduced here. Severity stays `low` and frequency stays `occasional`, since this needs a symlinked user background directory and loses no data.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `/usr/bin/omarchy-theme-bg-next` and `/usr/bin/omarchy-theme-set` are owned by the `omarchy` package, so a manual patch is reverted by the next `omarchy update`. `/usr/share/omarchy/bin/omarchy-theme-bg-next` is a symlink to the `/usr/bin` file, and `sed -i` without `--follow-symlinks` replaces that symlink with a regular file, which leaves two divergent copies of the script on disk.

**Fix.**

Simplest workaround, use a real directory instead of a symlink. `rm` removes only the link, not the dotfiles it points at:

```bash
rm ~/.config/omarchy/backgrounds/<theme>
mkdir -p ~/.config/omarchy/backgrounds/<theme>
cp -L ~/dotfiles/walls/* ~/.config/omarchy/backgrounds/<theme>/
```

`-L` matters when the source entries are themselves symlinks, because copying a symlink reproduces the bug inside the new directory.

Or patch the comparison to canonicalise both sides. The file to edit is `/usr/bin/omarchy-theme-bg-next`. `/usr/share/omarchy/bin/omarchy-theme-bg-next` is only a symlink to it. Change the current-background read and the loop comparison to:

```bash
CURRENT_BACKGROUND=$(readlink -f "$CURRENT_BACKGROUND_LINK")
...
if [[ $(realpath "${BACKGROUNDS[$i]}") == "$CURRENT_BACKGROUND" ]]; then
```

The same change applies to `choose_theme_background` in `/usr/bin/omarchy-theme-set`.

There is no `prev` command, so to reach a specific wallpaper pick it directly:

```bash
omarchy-theme-bg-switcher                       # image picker, any wallpaper for this theme
omarchy-theme-bg-set ~/dotfiles/walls/foo.jpg   # explicit path
```

**Verify.** Pressing the background-next binding four times cycles `a.jpg -> b.jpg -> c.jpg -> a.jpg`; `omarchy theme bg current` changes on each press.

Sources: <https://github.com/omacom/omarchy/issues/8594> · <https://github.com/omacom/omarchy/issues/8508>

---

## Fix top-bar icons rendering at roughly half size after changing the system font

`bar-icons-half-size-with-iosevka-nerd-font-mono` · severity: **low** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After `omarchy font set "Iosevka Nerd Font Mono"`, the top-bar icons (Wi-Fi, volume, Bluetooth, power, monitor) render at roughly half the size they did with JetBrainsMono Nerd Font. Bar text also reads a little smaller, because Iosevka is a narrow face drawn at the same pixel size, but the icons are the striking part and the only thing that changes by a factor of two.

**Cause.** The bar draws each icon as a single Nerd Font glyph at a fixed pixel size. `shell/Ui/BarIconButton.qml` sets `fontSize: Style.bar.iconFont`, `shell/Ui/OpticalGlyph.qml` renders that straight into `font.pixelSize` and corrects only the horizontal centring, and `Style.bar.iconFont` is `barToken("icon-font", 13)`, so 13px by default, multiplied by `fontScale`, which is `[font] base-size` divided by 12. Nothing measures the glyph, so the painted size is whatever the font draws inside that box.

Nerd Fonts patches each family in three widths, and the variant is the whole story. Upstream's patcher documents `--single-width-glyphs` as "generate the glyphs as single-width not double-width (default is double-width)" and names that build Nerd Font Mono, while `--variable-width-glyphs`, "do not adjust advance width", is Nerd Font Propo. So the Mono variant squeezes every icon into one character cell. Iosevka's cell is unusually narrow: in the measurements on omacom/omarchy#8608, every icon under Iosevka Nerd Font Mono is exactly 500 units wide on a 1000-unit em, which is that single-cell advance, against 750 to 970 units for the same codepoints in Iosevka Nerd Font, Iosevka Nerd Font Propo and JetBrainsMono Nerd Font. At a fixed 13px that is roughly 6.5px painted against 12.6px.

There is no per-icon config knob. `Style.qml`'s `applyShellValues` reads only `size-horizontal`, `size-vertical` and `scale-with-font` out of the `[bar]` section, so `icon-font`, `icon-canvas`, `icon-slot` and `status-slot` are not settable from `shell.toml` at all. The only lever that moves them is `[font] base-size`, which scales the whole shell.

> **Audit corrected this record.** Read the shipped Quickshell shell on this workstation (omarchy 4.0.2-1, quickshell 0.3.1-1, Hyprland 0.56.2-1) and every mechanical claim about the shell held exactly. Confirmed locally in /usr/share/omarchy/shell/Commons/Style.qml: `Style.bar.iconFont` is `barToken("icon-font", 13)`, `barToken` multiplies by `fontScale`, which is `fontBaseSize / 12`, `barScaleWithFont` defaults to true, and `applyShellValues` parses only `scale-with-font`, `size-horizontal` and `size-vertical` from the `[bar]` section, so `icon-font`, `icon-canvas`, `icon-slot` and `status-slot` really are unreachable from shell.toml. Also confirmed locally: /usr/share/omarchy/shell/Ui/BarIconButton.qml sets `fontSize: Style.bar.iconFont`, OpticalGlyph.qml renders that into `font.pixelSize` and corrects only the horizontal centre, and Color.qml reads `~/.config/omarchy/shell.toml` with `watchChanges: true` and merges it over the theme with user keys winning. Both cited issues were read in full and both support the record, with 8608 carrying the glyph measurement table the cause paraphrases and 7305 being a weaker corroborating report. Four things were wrong or missing. The symptom claimed bar text is fine and only icons shrink, which contradicts the record's own second source, 7305, whose title is that text and icons are both very small, so I made the symptom honest about the narrow face. The cause stated the 50 percent figure as a property of how Iosevka patches glyphs, without the reason, so I added the Nerd Fonts variant mechanism from upstream's own patcher documentation, where `--single-width-glyphs` is documented as "generate the glyphs as single-width not double-width (default is double-width)" and named as Nerd Font Mono, and `--variable-width-glyphs` as Nerd Font Propo, which is what makes every Mono row in 8608's table exactly 500 units on a 1000-unit em. The fix told the user to run `omarchy restart shell` after `omarchy font set`, which is redundant because omarchy-font-set already calls omarchy-restart-shell, and to set `[bar] scale-with-font = true`, which is already the default, and it missed `omarchy display text size`, the supported CLI that writes `[font] base-size` and accepts 9 to 20. The danger covered only shell text and missed that `omarchy-font-set` rewrites the fontconfig monospace alias and the alacritty, kitty, ghostty and foot font families, so abandoning the Mono variant changes icon cell width in the terminal too. I dropped frequency from common to occasional because the fault needs a specific non-default font variant to be chosen, and there are two open issues rather than a broad pattern. NOT exercised, and this is the main gap: Iosevka is not installed on this machine, `fc-list` here reports only JetBrainsMono Nerd Font, and the pacman files database is not synced, so I could not re-measure any glyph bounding box or confirm the exact family names `ttf-iosevka-nerd` 3.5.1-2 installs. Those numbers and names come from issue 8608 and are consistent with the upstream patcher documentation, not from a local measurement. I also changed no font, no theme and no setting on this machine.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Two costs. `omarchy display text size` deliberately moves GTK apps and terminal font size along with the shell, and editing `[font] base-size` by hand scales every piece of shell text rather than only the bar icons. And `omarchy font set` rewrites the fontconfig `monospace` alias and the alacritty, kitty, ghostty and foot font families, so leaving the Mono variant also changes how icons occupy cells in your terminal. The plain `Iosevka Nerd Font` draws icon glyphs double-width, which can misalign a TUI prompt or status line that assumed one cell.

**Fix.**

Switch to a variant that does not force icons into a single cell:

```bash
omarchy font set "Iosevka Nerd Font"
```

`omarchy-font-set` calls `omarchy-restart-shell` itself, so no separate restart is needed. Check first what the `ttf-iosevka-nerd` package actually gave you, because the variant names are what `fc-list` reports and nothing else:

```bash
fc-list : family | tr ',' '\n' | grep -i iosevka | sort -u
```

`omarchy font list` will not necessarily show every variant. It runs `fc-list :spacing=100`, which lists only fonts fontconfig considers monospaced, so a `Propo` build can be missing from that list even though `omarchy font set` accepts it, since `omarchy-font-set` only tests `fc-list | grep -Fqi`.

If you want to keep the Mono variant, the only knob that moves the icons is the shell base font size. The supported command is:

```bash
omarchy display text size 16
```

It accepts 9 to 20, writes `[font] base-size` into `~/.config/omarchy/shell.toml`, and moves GTK's `text-scaling-factor` and the terminal point size in lockstep with it. To move the shell alone, edit the same file by hand:

```toml
[font]
base-size = 18
```

The shell watches `~/.config/omarchy/shell.toml` and re-reads it on change, so this takes effect live with no restart, and a user key there wins over the theme's own `shell.toml`. Do not bother setting `[bar] scale-with-font`: it is already `true` by default, which is what makes `base-size` reach the icons at all.

Omarchy 4 versus plain Arch: all of the above is Omarchy-specific, because the bar is the Omarchy Quickshell shell. On plain Arch with another bar, the same Nerd Font Mono single-width behaviour applies, but the fix is whatever font size that bar exposes.

**Verify.** Confirm which font the shell resolved and compare the two variants:

```bash
omarchy font current
fc-match monospace -f '%{family[0]}\n'
```

Then set `"Iosevka Nerd Font Mono"` and `"Iosevka Nerd Font"` in turn and look at the Wi-Fi, volume and Bluetooth icons. Under the non-Mono variant they should be the same optical size they were on JetBrainsMono Nerd Font, and the jump between the two settings should be obvious rather than subtle.

Sources: <https://github.com/omacom/omarchy/issues/8608> · <https://github.com/omacom/omarchy/issues/7305> · <https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/readme.md>

---

## Fix Chromium's tab strip turning bright yellow under a warm light theme

`chromium-tab-strip-bright-yellow-on-light-theme` · severity: **low** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** With a light theme whose background is a warm near-white — tufte (`#fffcf0`) is the usual culprit — the Chromium tab strip renders bright yellow (`#ffde5a`) instead of the theme color. Dark themes and neutral light themes such as latte (`#eff1f5`) are fine. `/etc/chromium/policies/managed/color.json` correctly contains `BrowserThemeColor: #fffcf0`.

**Cause.** Chromium derives the tab strip color from the seed by darkening it while preserving hue and saturation. In Skia's HSL, any channel at 255 counts as fully saturated (s=1.0), so a cream like `#fffcf0` is treated as a fully saturated yellow and darkens to a saturated yellow rather than to a warm grey. The policy file and the Omarchy state are both correct; the derivation is what goes wrong.

> **Audit corrected this record.** The colour math is genuinely correct - for a light colour with any channel at 255, HSL saturation computes to 1.0, and the `3*max - min >= 510` test is the right algebraic form of S>=0.5 when L>0.5. The policy path /etc/chromium/policies/managed and the BrowserThemeColor key are confirmed in bin/omarchy-theme-set-browser. But the theme names are wrong: `tufte` is NOT one of the 22 shipped Omarchy themes - the theme whose background is #fffcf0 is flexoki-light. `latte` is `catppuccin-latte`. I verified the actual backgrounds: flexoki-light #FFFCF0 -> 525 (triggers), rose-pine #faf4ed -> 513 (triggers, and Omarchy's rose-pine is mode="light"), catppuccin-latte #eff1f5 -> 496 (fine), white #ffffff is achromatic so S=0 (fine, though the record's own test returns exactly 510 for it). The fix also drops the `BrowserColorScheme: "device"` key that omarchy-theme-set-browser writes alongside the colour, and the hook's `sudo -n` fails silently without passwordless sudo.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The hook writes to `/etc/chromium/policies/managed/` with sudo on every theme change. `sudo -n` will fail silently without a NOPASSWD sudoers rule for exactly that file — if you are not comfortable adding one, write the policy once by hand instead of on every switch.

**Fix.**

**Theme-name correction.** `tufte` is not an Omarchy theme. The shipped set is catppuccin, catppuccin-latte, ethereal, everforest, flexoki-light, gruvbox, hackerman, kanagawa, last-horizon, lumon, lupine, matte-black, miasma, nord, osaka-jade, retro-82, ristretto, rose-pine, solitude, tokyo-night, vantablack, white. The theme with background `#fffcf0` is **flexoki-light**. Verified against each theme's `colors.toml` using the `3*max - min >= 510` test:

```
flexoki-light     #FFFCF0 -> 525   triggers
rose-pine         #faf4ed -> 513   triggers  (Omarchy's rose-pine is mode = "light")
catppuccin-latte  #eff1f5 -> 496   fine
white             #ffffff -> achromatic (max == min), S = 0, fine
```

Seed Chromium with a slightly darkened colour, and **keep the `BrowserColorScheme` key** that `omarchy-theme-set-browser` writes - dropping it changes Chromium's light/dark behaviour:

```bash
sudo tee /etc/chromium/policies/managed/color.json >/dev/null <<'JSON'
{ "BrowserThemeColor": "#f5f2e6", "BrowserColorScheme": "device" }
JSON
pkill -x chromium
```

Chromium re-reads managed policy only at startup, so it must be fully quit.

Hook version. It runs after `omarchy-theme-set-browser`, so it wins. The theme-set hook receives the theme name as `$1`, so reading `current/theme.name` is unnecessary. Test the `sudo -n` line by hand once - without passwordless sudo it fails silently:

```bash
mkdir -p ~/.config/omarchy/hooks/theme-set.d
cat > ~/.config/omarchy/hooks/theme-set.d/30-chromium-seed.sh <<'EOF'
#!/bin/bash
case "$1" in
  flexoki-light|rose-pine)
    printf '{ "BrowserThemeColor": "#f5f2e6", "BrowserColorScheme": "device" }\n' \
      | sudo -n tee /etc/chromium/policies/managed/color.json >/dev/null \
      || echo "chromium seed hook: passwordless sudo required" >&2
    ;;
esac
EOF
chmod +x ~/.config/omarchy/hooks/theme-set.d/30-chromium-seed.sh
```

**Verify.** Reopen Chromium under the tufte theme — the tab strip is a warm off-white/grey rather than `#ffde5a`. `chrome://policy` shows the `BrowserThemeColor` value you set.

Sources: <https://github.com/basecamp/omarchy/issues/7624>

---

## Fix Neovim erroring with "could not load your colorscheme" after a theme change

`nvim-colorscheme-error-after-theme-change` · severity: **low** · frequency: **occasional** · applies to: `arch`, `omarchy`, `omarchy-4`

**Symptom.** After a theme change, every nvim launch shows LazyVim's `Could not load your colorscheme` error and the editor opens in Neovim's builtin `habamax` with none of the theme's colours.

**Cause.** Omarchy 4 ships its own Neovim config as the `omarchy-nvim` package (`2026.8.13-1` here), seeded from `/etc/skel/.config/nvim` when the account is created, with the reference copy kept at `/usr/share/omarchy-nvim/config`. It is LazyVim, and `~/.config/nvim/lua/plugins/theme.lua` is a **symlink** to `~/.local/state/omarchy/current/theme/neovim.lua`, not a copy:

```
lrwxrwxrwx theme.lua -> ../../../../.local/state/omarchy/current/theme/neovim.lua
```

`omarchy theme set` rebuilds that staged theme directory (`rm -rf "$CURRENT_THEME_PATH"` then `mv` of `next-theme`), so the file behind the symlink changes and the next Neovim start reads the new spec. The staged `neovim.lua` comes from one of two places. 15 of the 22 shipped themes carry their own `neovim.lua`. For the other 7 (`ethereal`, `last-horizon`, `lupine`, `miasma`, `ristretto`, `vantablack`, `white`) `omarchy-theme-set-templates` generates one from `$OMARCHY_PATH/default/themed/neovim.lua.tpl`, which uses `bjarneo/aether.nvim` and asks for `colorscheme = "aether"`. A theme cloned by `omarchy theme install` always gets the generated one, because staging drops every `*.lua` a cloned theme ships.

The error is LazyVim's, raised in `lua/lazyvim/config/init.lua` when `vim.cmd.colorscheme()` throws, and its `on_error` falls back to Neovim's builtin `habamax`:

```lua
  }, {
    msg = "Could not load your colorscheme",
    on_error = function(msg)
      LazyVim.error(msg)
      vim.cmd.colorscheme("habamax")
    end,
  })
```

So the failure means the plugin checkout under `~/.local/share/nvim/lazy/` does not register the name the staged `neovim.lua` asked for. That is a plugin pin problem, not a theme bug. For catppuccin, upstream renamed the colorscheme to `catppuccin-nvim` in catppuccin/nvim PR #977, released in v2.0.0 on 2026-04-02, because Neovim 0.12 ships its own builtin `catppuccin` at `/usr/share/nvim/runtime/colors/catppuccin.vim`. A checkout from before v2.0.0 has no `colors/catppuccin-nvim.vim`, so the name genuinely is missing.

Omarchy 4 does ship a `lazy-lock.json`, contrary to the cited issue thread, and its catppuccin pin (`edefef779ab08ce1a4a404713e3012b0d202bd35`) is already past the rename, so a fresh 4.0.2 install does not hit the catppuccin case. What still hits it is a lock that predates the current one, because `omarchy update` never rewrites an existing account's `~/.config/nvim/lazy-lock.json`. The same applies to `aether`, which an older lock does not carry at all, so on such an install every theme with no shipped `neovim.lua`, and every theme installed from a git repo, asks for a colorscheme that is not on disk.

> **Audit corrected this record.** Checked on this workstation at omarchy 4.0.2-1, omarchy-nvim 2026.8.13-1, neovim 0.12.5-1. The record's mechanism is wrong: `omarchy-theme-set` does not copy a `neovim.lua` into the nvim config, it rebuilds `~/.local/state/omarchy/current/theme/` and `~/.config/nvim/lua/plugins/theme.lua` is a symlink into that directory, shipped as a symlink by `omarchy-nvim` in `/etc/skel/.config/nvim/lua/plugins/theme.lua` and confirmed unaltered by `pacman -Qkk omarchy-nvim`. That makes the record's last fix step actively harmful, because it tells the reader to edit a file that `omarchy-theme-set` deletes with `rm -rf "$CURRENT_THEME_PATH"` on the next theme change. The cause's claim that "Omarchy ships no lazy-lock.json" is false on Omarchy 4: `pacman -Ql omarchy-nvim` lists `/etc/skel/.config/nvim/lazy-lock.json`, the reference copy is `/usr/share/omarchy-nvim/config/lazy-lock.json`, and its catppuccin pin `edefef779ab08ce1a4a404713e3012b0d202bd35` already registers `catppuccin-nvim`, verified by listing `~/.local/share/nvim/lazy/catppuccin/colors/` on this machine. That sentence was copied verbatim from the cited issue comment, which I read in full at https://github.com/omacom/omarchy/issues/6648: the comment is otherwise correct and the rename claim holds, since catppuccin/nvim PR #977 merged 2026-03-13 and shipped in v2.0.0 on 2026-04-02, and Neovim 0.12.5 does carry `/usr/share/nvim/runtime/colors/catppuccin.vim`. The error string is LazyVim's, from `lua/lazyvim/config/init.lua`, and it falls back to `habamax` rather than to an unthemed editor, so the symptom was rewritten too. The fix now covers the case the record missed entirely: 7 of the 22 shipped themes carry no `neovim.lua`, and `omarchy-theme-set` drops every `*.lua` from a theme cloned by `omarchy theme install`, so both get a spec generated from `$OMARCHY_PATH/default/themed/neovim.lua.tpl` asking for `aether`, which is what a lock older than that template lacks. Frequency lowered to `occasional` because the shipped lock now carries the post-rename catppuccin pin, so a current install does not reproduce the catppuccin case and only a drifted or pre-aether lock does. NOT exercised: I changed no theme, installed no third-party theme and did not start Neovim, so every claim here comes from reading the scripts, the package file list, the on-disk plugin checkouts and the cited sources rather than from reproducing the failure.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `:Lazy restore` and `:Lazy sync` move every plugin, not only the colorscheme, and rewrite `~/.config/nvim/lazy-lock.json`. Copy the lock aside first, as the fix does, and commit it if you version your dotfiles. Do not edit `~/.config/nvim/lua/plugins/theme.lua`: it is a symlink into `~/.local/state/omarchy/current/theme/`, which `omarchy-theme-set` removes with `rm -rf` on the next theme change, so the edit is lost and the staged theme carries your override until then.

**Fix.**

First find out what Omarchy asked for and what your Neovim actually has. Both are read-only.

```bash
# what the current theme asks LazyVim to load
grep colorscheme ~/.local/state/omarchy/current/theme/neovim.lua

# every colorscheme name this Neovim can resolve
ls ~/.local/share/nvim/lazy/*/colors/*.lua ~/.local/share/nvim/lazy/*/colors/*.vim \
   /usr/share/nvim/runtime/colors/*.vim /usr/share/nvim/runtime/colors/*.lua 2>/dev/null \
  | xargs -n1 basename | sed 's/\.\(lua\|vim\)$//' | sort -u
```

If the name from the first command is in the second list, the colorscheme is not the problem and you are looking at a different plugin error. If it is missing, read on.

**Case 1: your lock file has drifted from the one Omarchy ships.** This is the usual cause on an install that has been upgraded rather than freshly installed.

```bash
diff /usr/share/omarchy-nvim/config/lazy-lock.json ~/.config/nvim/lazy-lock.json
```

If they differ, take Omarchy's pins back:

```bash
cp ~/.config/nvim/lazy-lock.json ~/.config/nvim/lazy-lock.json.bak
cp /usr/share/omarchy-nvim/config/lazy-lock.json ~/.config/nvim/lazy-lock.json
nvim
```

then in Neovim run `:Lazy restore`, wait for it to finish, quit and reopen. For catppuccin specifically the shipped pin is `edefef779ab08ce1a4a404713e3012b0d202bd35`, which does register `catppuccin-nvim`:

```bash
ls ~/.local/share/nvim/lazy/catppuccin/colors/
# catppuccin-frappe.lua  catppuccin-latte.lua  catppuccin.lua
# catppuccin-macchiato.lua  catppuccin-mocha.lua  catppuccin-nvim.vim
```

**Case 2: the locks match but the plugin was never fetched.** Open `nvim` and run `:Lazy install`, or `:Lazy update <plugin>` for one plugin, for example `:Lazy update catppuccin`.

**Case 3: a theme you installed yourself, or a shipped theme with no Neovim fragment.** Staging drops every `*.lua` from a theme cloned by `omarchy theme install`, and 7 shipped themes ship no `neovim.lua`, so in both cases Omarchy generates the spec from its own template and asks for `aether`:

```bash
grep -n 'aether\|colorscheme' ~/.local/state/omarchy/current/theme/neovim.lua
ls ~/.local/share/nvim/lazy/aether/colors/
```

If `~/.local/share/nvim/lazy/aether` is absent, the plugin is simply not installed. Fix it the same way as case 1 or case 2. There is no per-theme colorscheme to hunt for, because a third-party theme is never allowed to supply one.

**Do not edit `~/.config/nvim/lua/plugins/theme.lua`.** It is a symlink into the staged theme directory, so an edit there writes into `~/.local/state/omarchy/current/theme/neovim.lua` and the next `omarchy theme set` deletes it:

```bash
ls -l ~/.config/nvim/lua/plugins/theme.lua
```

If you want a colorscheme of your own that survives theme changes, put it in a separate spec file whose name sorts after `theme`:

```lua
-- ~/.config/nvim/lua/plugins/zz-colorscheme.lua
return {
  { "LazyVim/LazyVim", opts = { colorscheme = "catppuccin-mocha" } },
}
```

lazy.nvim imports a plugins directory in alphabetical order of module name (`table.sort` on `modname` in `lua/lazy/core/plugin.lua`), so the later file's `opts.colorscheme` wins and Omarchy's theme switching leaves it alone.

**Verify.** `nvim` opens with no error banner, and `:echo g:colors_name` prints the same name that `grep colorscheme ~/.local/state/omarchy/current/theme/neovim.lua` reports. `:Lazy` shows the theme plugin as installed rather than pending.

Sources: <https://github.com/omacom/omarchy/issues/6648> · <https://github.com/catppuccin/nvim/pull/977> · <https://github.com/catppuccin/nvim/releases/tag/v2.0.0> · <https://github.com/omacom/omarchy/blob/quattro/themes/catppuccin/neovim.lua> · <https://github.com/omacom/omarchy/blob/quattro/manual/16-neovim.md>

---

## Fix one monitor keeping the old wallpaper after a theme change

`one-monitor-keeps-old-wallpaper-after-theme-change` · severity: **low** · frequency: **occasional** · applies to: `amd`, `desktop`, `hyprland`, `intel`, `nvidia`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy theme set kanagawa` retints everything and updates the wallpaper on the primary monitor, but the second monitor keeps showing the previous theme's wallpaper indefinitely. The bar on that same monitor updates normally (clock ticking, new colors) — only the background is stale. `omarchy background refresh` does nothing.

**Cause.** Two things. On a multi-GPU setup (the stale output is the one behind the cross-GPU blit path — aquamarine logs `GBM: Buffer is marked as multigpu, forcing linear`), that output's background surface never commits a new frame after the source changes, and the compositor keeps scanning out its last buffer. A wallpaper is static, so nothing ever forces another redraw. Then the obvious fix is a guaranteed no-op: `refreshBackground()` in `shell/plugins/background/Background.qml` ends in `transitionBackground(...)`, which early-returns on `if (!path || (!force && finalPath === currentBackground)) return` — and the shell already believes it is showing the new wallpaper. Compounding it, the theme reveal animation is gated on a single shared `revealProgress` root property, so only the first monitor whose frame loads ever runs the reveal.

> **Audit corrected this record.** The recovery and diagnostics are fine - omarchy restart shell is correct, and the readlink/theme.name/hyprctl layers and grim+magick pixel-sampling checks are all read-only and sensible for proving the state is right while the pixels are stale. The problem is the persistence step: Omarchy 4 configures Hyprland in Lua (hypr/hyprland.lua, hypr/bindings.lua, hypr/looknfeel.lua, hypr/monitors.lua are all in omarchy-upgrade-to-quattro's always_copy_config_files), so a `bind = ...` line dropped into ~/.config/hypr/bindings/custom.conf is never sourced on the omarchy-4 systems this record is tagged for, and the user would conclude the whole fix failed. Also /run/user/1000 hardcodes a uid.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The reliable recovery is a full shell restart:

```bash
omarchy restart shell
```

Confirm the state is right and only the pixels are wrong before doing that:

```bash
readlink ~/.local/state/omarchy/current/background
cat ~/.local/state/omarchy/current/theme.name
hyprctl layers | grep -c omarchy-background   # one per monitor, as expected
```

Sample what each output is actually painting:

```bash
grim -o HDMI-A-1 /tmp/a.png && magick /tmp/a.png -format '%[pixel:p{50,950}]' info:
grim -o DP-1 /tmp/b.png && magick /tmp/b.png -format '%[pixel:p{50,950}]' info:
```

**Keybinding correction.** Omarchy 4 configures Hyprland in Lua, not `.conf` - `~/.config/hypr/bindings/custom.conf` is never sourced, so that bind would silently do nothing. Add it to `~/.config/hypr/bindings.lua`, following the form of the entries already in that file, then:

```bash
hyprctl reload
```

Verify the bind actually registered:

```bash
hyprctl binds | grep -A3 -i 'restart shell'
```

(On Omarchy 3.x the `~/.config/hypr/bindings/custom.conf` + `bind = SUPER SHIFT, R, exec, omarchy restart shell` form was correct.)

**Verify.** After `omarchy restart shell`, `grim` samples of both outputs return matching colors for the new wallpaper, and both monitors visibly show the same background.

Sources: <https://github.com/basecamp/omarchy/issues/8679>

---

## Fix a `shell.lock.toml` section override that is silently ignored

`shell-section-override-ignored-without-colors-toml` · severity: **low** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** You add `shell.lock.toml` to your theme to restyle the lock screen (or `shell.menu.toml`, `shell.notifications.toml`, …) and nothing changes — the lock surface keeps the generated colours, with no warning anywhere. `ls ~/.local/state/omarchy/current/theme/shell.toml` reports `No such file or directory`, and `grep -A5 '^\[lock\]' ~/.local/state/omarchy/current/theme/shell.toml` fails because there is no file to grep.

**Cause.** A `shell.<section>.toml` is not a standalone file — `apply_shell_section_override` in `bin/omarchy-theme-set-templates` splices its body into the generated `shell.toml`, and its very first line is `[[ -f $NEXT_THEME_DIR/shell.toml ]] || return`. `shell.toml` itself is only rendered from `default/themed/shell.toml.tpl` inside the `if [[ -f $COLORS_FILE ]]` gate, so a partial theme with no `colors.toml` produces no `shell.toml` and every section override is dropped without a message. Two smaller traps sit on top of that: the **filename** decides the target section (so the `[lock]` header inside the file is optional and a wrong header is ignored), and a misspelt filename such as `shell.lockscreen.toml` is happily appended as a `[lockscreen]` section that the shell never reads — again silently. Note also that a theme shipping a full hand-written `shell.toml` wins over the template outright, because `omarchy-theme-set-templates` never overwrites an output file that already exists.

> ⚠️ **Risk.** Shipping a complete hand-written `shell.toml` in a theme replaces the generated file entirely — `omarchy-theme-set-templates` will not overwrite it, so any key later Omarchy releases add is missing and those surfaces silently fall back to built-in defaults. Prefer a `shell.<section>.toml`, or `~/.config/omarchy/shell.toml`, both of which layer rather than replace.

**Fix.**

Confirm the generated file exists at all — this is almost always the whole problem:

```bash
ls -l ~/.local/state/omarchy/current/theme/colors.toml ~/.local/state/omarchy/current/theme/shell.toml
```

If `colors.toml` is missing, give the theme one; that is what makes the entire template pass run:

```bash
cp /usr/share/omarchy/themes/tokyo-night/colors.toml ~/.config/omarchy/themes/<name>/colors.toml
omarchy theme set <name>
```

Get the section name right — the valid ones are exactly the sections in the generated file:

```bash
grep -o '^\[[a-z-]*\]' ~/.local/state/omarchy/current/theme/shell.toml
# [bar] [hyprland] [controls] [popups] [tooltip] [notifications] [launcher]
# [menu] [polkit] [lock] [image-picker] [spacing] [font]
```

Write the override with just the keys — the header is optional because the filename decides the section:

```bash
cat > ~/.config/omarchy/themes/<name>/shell.lock.toml <<'EOF'
background       = "#000000"
background-alpha = 0.8
text             = "#ffffff"
placeholder      = "#ffffff"
text-error       = "#ff5555"
border           = "#ffffff"
border-active    = "#ffffff"
border-error     = "#ff5555"
border-alpha     = 1.0
EOF
omarchy theme set <name>
```

Then check that it actually landed in the generated file:

```bash
sed -n '/^\[lock\]/,/^\[/p' ~/.local/state/omarchy/current/theme/shell.toml
```

If you want the override on **every** theme rather than one, put it in your own file instead — `~/.config/omarchy/shell.toml` layers over whatever the theme generated and survives theme switches:

```toml
[lock]
border = "#ffffff"
```

```bash
omarchy restart shell     # the shell watches the file; usually not needed
omarchy system lock       # check it
```

**Verify.** `sed -n '/^\[lock\]/,/^\[/p' ~/.local/state/omarchy/current/theme/shell.toml` shows your values, and `omarchy system lock` displays the restyled password input.

Sources: <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-theme-set-templates> · <https://github.com/omacom/omarchy/blob/quattro/default/themed/shell.toml.tpl> · <https://github.com/omacom/omarchy/blob/quattro/docs/theming.md>

---

## Fix black/fuchsia checkerboard placeholders instead of icons on Vantablack/White themes

`vantablack-white-theme-broken-icon-placeholders` · severity: **low** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** On the Vantablack or White theme, notification icons and some tray/app icons render as a black-and-fuchsia checkerboard placeholder instead of a real icon. The shell log shows `WARN: Could not load icon "battery-caution" at size QSize(40, 40) from request`, or the same for names like `nordvpn-tray-blue`.

**Cause.** `vantablack/icons.theme` sets the GNOME icon theme to `Yaru-gray`, but no such icon theme exists on disk — Ubuntu dropped it upstream and neither `yaru-icon-theme` nor `omarchy` ships it. The fallback in `omarchy-theme-set-gnome` only fires when the `icons.theme` state file is *missing*; it never validates the name it finds. So gsettings ends up pointing at an unresolvable theme and every themed icon lookup fails.

> **Audit corrected this record.** The bug is real and confirmed verbatim: themes/vantablack/icons.theme contains exactly `Yaru-gray`, and bin/omarchy-theme-set-gnome does `if [[ -f $GNOME_ICONS_THEME ]]; then gsettings set ... "$(<$GNOME_ICONS_THEME)"; else ... "Yaru-blue"; fi` - the fallback fires only on a MISSING file and never validates the name, exactly as stated. But the prescribed replacements are wrong: Yaru ships color variants (Yaru, Yaru-blue, Yaru-purple, ...), not Yaru-dark/Yaru-light, so the fix swaps one non-existent name for another. Also themes/white/icons.theme is `Yaru-grey` (different spelling), and yaru-icon-theme is already in install/omarchy-base.packages so the install step is redundant - and `pacman -S` there should be `-Syu`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `Yaru-dark` restores working icons but brings back app brand colors, losing the intentional monochrome look of Vantablack/White. It is a reliability fix, not a design fix.

**Fix.**

Confirm the bad value and see what icon themes actually exist:

```bash
gsettings get org.gnome.desktop.interface icon-theme   # -> 'Yaru-gray'
ls /usr/share/icons                                     # the real list
```

Both affected themes name a Yaru grey variant that does not exist, with different spellings:

```
themes/vantablack/icons.theme -> Yaru-gray
themes/white/icons.theme      -> Yaru-grey
```

`Yaru-dark` and `Yaru-light` do not exist either - Yaru ships colour variants. Use a name that is really installed. Omarchy's own built-in fallback is `Yaru-blue`, so it is the safe choice:

```bash
cp -a "$(omarchy theme dir vantablack)" ~/.config/omarchy/themes/vantablack
echo "Yaru-blue" > ~/.config/omarchy/themes/vantablack/icons.theme
omarchy theme refresh
```

Same for the White theme:

```bash
cp -a "$(omarchy theme dir white)" ~/.config/omarchy/themes/white
echo "Yaru-blue" > ~/.config/omarchy/themes/white/icons.theme
omarchy theme refresh
```

Verify the name you chose resolves before trusting it:

```bash
ls -d /usr/share/icons/Yaru-blue
```

`yaru-icon-theme` is already listed in `install/omarchy-base.packages`, so it should be present. Verify rather than reinstall, and use `-Syu` (never `-S` against a stale db, and never `-Sy`, which causes a partial upgrade):

```bash
pacman -Qi yaru-icon-theme >/dev/null 2>&1 || sudo pacman -Syu yaru-icon-theme
```

**Verify.** `gsettings get org.gnome.desktop.interface icon-theme` returns `'Yaru-dark'`, and `omarchy-notification-send -u critical "test" "test" -i battery-caution` shows a real battery icon rather than a checkerboard. `journalctl --user -b | grep 'Could not load icon'` produces no new lines.

Sources: <https://github.com/basecamp/omarchy/issues/7203>

---
