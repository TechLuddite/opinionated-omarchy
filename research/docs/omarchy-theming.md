# Omarchy theming & bar

41 problems. Sorted by severity, then by how often users hit it.

## Stop the whole desktop hard-freezing when the Walker launcher renders

`walker-gtk4-vulkan-renderer-amdgpu-hard-freeze` · severity: **critical** · frequency: **occasional** · applies to: `amd`, `desktop`, `hyprland`, `omarchy`, `omarchy-3`, `wayland`

**Symptom.** The entire desktop freezes — display frozen, keyboard and mouse dead — but audio keeps playing. Only a hard reset recovers. `journalctl -k` from the previous boot shows `BUG: kernel NULL pointer dereference` at `RIP: ttm_lru_bulk_move_pos_tail+0x4f/0xb0 [ttm]` with `Comm: walker`, preceded by `WARNING: drivers/gpu/drm/ttm/ttm_resource.c:235 at ttm_resource_add_bulk_move`, then `watchdog: BUG: soft lockup - CPU#16 stuck for 495s! [kworker/u97:3]` inside `amdgpu_dm_atomic_commit_tail`.

**Cause.** Omarchy's `GSK_RENDERER=cairo` workaround is applied only in `bin/omarchy-launch-walker`, but the resident `walker --gapplication-service` process is normally started by the XDG autostart entry (`~/.config/autostart/walker.desktop`, `Exec=walker --gapplication-service`), which systemd's `systemd-xdg-autostart-generator` turns into `app-walker@autostart.service` with no env override. So walker runs with GTK4's default Vulkan/ngl renderer. The guard `if ! pgrep -f "walker --gapplication-service"` in the launch script is dead code because the service is already running. On amdgpu, walker page-faults on a GEM buffer, the kernel takes a NULL deref inside TTM while holding the LRU spinlock, and every subsequent display atomic commit deadlocks on it — which is why input dies too. The underlying defect is kernel-side TTM/amdgpu; the missing env var is what exposes it.

> ⚠️ **Risk.** Until this is applied, the failure mode is an unrecoverable freeze requiring a hard reset — which risks filesystem damage on btrfs/ext4 with unflushed writes. `~/.config/autostart/walker.desktop` is rewritten by `omarchy-refresh-walker` and by migrations, so re-check the Exec line after any `omarchy update`.

**Fix.**

Confirm the env var is genuinely absent from the running service:

```bash
pgrep -a walker
tr '\0' '\n' < /proc/$(pgrep -x walker)/environ | grep GSK_RENDERER
```

Force the cairo renderer on the autostart entry:

```bash
sed -i 's|^Exec=walker --gapplication-service|Exec=env GSK_RENDERER=cairo walker --gapplication-service|' \
  ~/.config/autostart/walker.desktop
systemctl --user daemon-reload
systemctl --user restart app-walker@autostart.service
```

Or set it session-wide in `~/.config/hypr/envs.conf`:

```conf
env = GSK_RENDERER,cairo
```

then log out and back in.

**Verify.** `tr '\0' '\n' < /proc/$(pgrep -x walker)/environ | grep GSK_RENDERER` prints `GSK_RENDERER=cairo`. No new `Comm: walker` TTM oopses appear in `journalctl -k -b -1` over subsequent days.

Sources: <https://github.com/basecamp/omarchy/issues/6443>

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

## Fix the Walker launcher stuck on "Waiting for elephant"

`walker-waiting-for-elephant` · severity: **high** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-3`, `wayland`

**Symptom.** Pressing `SUPER+SPACE` opens the launcher, but the search box shows the placeholder `Launch...` with a transparent list below it reading `Waiting for elephant`. Nothing is searchable. `coredumpctl` may show `Process <pid> (walker) of user 1000 dumped core` with a stack through `g_application_run` and `libglib-2.0`.

**Cause.** Walker's backend indexer (`elephant`) is not running or has crashed, so Walker has nothing to query. It happens intermittently after an Omarchy update that restarts the services at the wrong moment, and sometimes Walker itself segfaults inside its GLib main loop and takes the pairing down with it. This is Omarchy 3.x only — Omarchy 4 (Quattro) replaced Walker and Elephant with the native Quickshell launcher.

> ⚠️ **Risk.** `omarchy upgrade to quattro` is a major version migration that rewrites config files and can clobber customizations — see the `shell-json-reset-by-quattro-upgrade` record before running it.

**Fix.**

Restart the launcher and its backend:

```bash
omarchy-restart-walker
```

If that does not take, restart both services explicitly and check what elephant says:

```bash
systemctl --user restart elephant.service
systemctl --user restart walker.service
systemctl --user status elephant.service
```

Watch the failure live while reproducing it:

```bash
journalctl --user -f
# then press SUPER+SPACE
```

A reboot clears it for many people; if it recurs constantly, check for crashes:

```bash
coredumpctl list walker
```

Upgrading to Omarchy 4 removes the component entirely:

```bash
omarchy upgrade to quattro
```

**Verify.** `SUPER+SPACE` shows your applications immediately with no "Waiting for elephant" line, and `systemctl --user is-active elephant.service` prints `active`.

Sources: <https://github.com/basecamp/omarchy/issues/2638>

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

## Recover from a custom theme that leaves the terminal unable to start

`installed-theme-without-colors-toml-breaks-foot` · severity: **high** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After `omarchy theme install <git-url>` or `omarchy theme set <my-theme>`, new terminal windows refuse to open. Running foot by hand prints: `err: config.c:896: /home/<user>/.config/foot/foot.ini:2: [main].include: ~/.local/state/omarchy/current/theme/foot.ini: failed to open: No such file or directory` and exits 230. `omarchy theme set` itself exited 0 with no warning.

**Cause.** `bin/omarchy-theme-set` accepts any directory under `~/.config/omarchy/themes/` and `omarchy theme install` clones and applies any repo with no validation. The per-app config generator only runs `if [[ -f $COLORS_FILE ]]` (`bin/omarchy-theme-set-templates:371`), so a theme with no `colors.toml` (and no legacy `alacritty.toml` to convert from) produces a `~/.local/state/omarchy/current/theme/` containing no `foot.ini`, `alacritty.toml`, `kitty.conf` or `shell.toml`. `config/foot/foot.ini:2` is an unconditional `include` of that missing file and foot treats a missing include as fatal. Alacritty and kitty include it unconditionally too; only Ghostty is guarded (`config-file = ?"..."`). Already-open terminals keep running, so you only discover it when you open a new one.

> ⚠️ **Risk.** `omarchy theme install <git-url>` clones and applies an arbitrary repository with no validation. Only install themes from a repo you have looked at.

**Fix.**

If you still have a terminal open, just switch back to a stock theme:

```bash
omarchy theme set tokyo-night
```

If you have no terminal left, get a shell from a TTY with `Ctrl+Alt+F2`, log in, and run the same command.

To actually keep the broken theme, give it a `colors.toml`. Minimum viable file:

```bash
cat > ~/.config/omarchy/themes/<my-theme>/colors.toml <<'EOF'
mode = "dark"
background = "#1a1b26"
foreground = "#c0caf5"
EOF
omarchy theme set <my-theme>
```

Before installing any third-party theme, check it first:

```bash
ls ~/.config/omarchy/themes/<name>/colors.toml || echo "NO colors.toml - will break terminals"
```

**Verify.** `foot --check-config; echo $?` returns 0, and `ls -A ~/.local/state/omarchy/current/theme` lists `foot.ini`, `alacritty.toml`, `kitty.conf` and `colors.toml` rather than just `hyprland.conf`.

Sources: <https://github.com/basecamp/omarchy/issues/7105> · <https://learn.omacom.io/2/the-omarchy-manual/92/making-your-own-theme>

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

**Symptom.** `omarchy theme set <any-theme>` never returns. Or `omarchy update` hangs inside a migration (e.g. `1787481315`, "Re-stage the current theme..."), never writes its marker file, so every later `omarchy update` re-runs it and hangs again. `ps` shows a stray `/usr/bin/brave --refresh-platform-policy --no-startup-window`.

**Cause.** `bin/omarchy-theme-set-browser` guards its plain-Brave branch with `pgrep -x brave`. brave-origin's processes are all named plain `brave`, so with brave-origin running and Brave not running the guard produces a false positive; the script then launches the *other* binary, `/usr/bin/brave` from `brave-bin`. With `--no-startup-window` that instance has no window to close, never exits, and `run_parallel`'s `wait` in the post-theme command list blocks on it forever. Related hangs exist for other post-theme commands — e.g. `omarchy-theme-set-keyboard-f16` with a Keychron K8 Pro attached.

> ⚠️ **Risk.** A migration that hangs never records its marker, so the whole migration queue behind it stays pending. Do not Ctrl+C out of `omarchy update` partway through its `pacman -Syu` — that risks a partial upgrade. Kill the stray browser process instead and let the update continue.

**Fix.**

Unblock the running command:

```bash
pkill -f 'brave --refresh-platform-policy --no-startup-window'
```

Confirm the false positive:

```bash
pgrep -xc brave                    # non-zero
pgrep -af brave | grep -v origin   # nothing -> real Brave is NOT running
readlink -f /usr/bin/brave /usr/bin/brave-origin
```

Simplest permanent avoidance: quit brave-origin before a theme change or update.

```bash
pkill -f /opt/brave-origin-bin/
omarchy update
```

Or patch the guard to match on binary path the way the brave-origin branch already does — in `bin/omarchy-theme-set-browser`, change:

```bash
refresh_running_browser brave brave
```

to:

```bash
refresh_running_browser /opt/brave-bin/ brave -f
```

If the machine is a Keychron K8 Pro and the hang is in `omarchy-theme-set-keyboard-f16` instead, unplug the keyboard and retry.

**Verify.** `omarchy theme set tokyo-night` completes in a few seconds. `omarchy update` runs the pending migration through to completion and writes its marker, so a second `omarchy update` does not re-run it.

Sources: <https://github.com/basecamp/omarchy/issues/8158> · <https://github.com/basecamp/omarchy/issues/8212> · <https://github.com/basecamp/omarchy/issues/8243>

---

## Make Nautilus and other GTK4/libadwaita apps follow the Omarchy theme

`gtk4-libadwaita-apps-ignore-omarchy-theme` · severity: **medium** · frequency: **very-common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** Every theme applies to the terminal, bar, launcher and lock screen, but Nautilus, Geary and GNOME Calendar stay in stock Adwaita colors no matter which theme you set. `omarchy theme set <any-theme>` then opening Nautilus shows no color change at all.

**Cause.** libadwaita ignores the `gtk-theme` setting by design. The only user-level lever it honors is `@define-color` overrides in `~/.config/gtk-4.0/gtk.css`, and stock Omarchy never writes that file — the only themed GTK CSS shipped anywhere in the tree is for the Hyprland share-picker. Compounding it, libadwaita reads the user stylesheet only at process startup, and these apps run as `--gapplication-service` daemons that survive window close, so they keep painting a days-old theme even after you rewrite the CSS.

> ⚠️ **Risk.** The hook overwrites `~/.config/gtk-4.0/gtk.css` on every theme change. If you already hand-maintain that file, back it up first or make the hook append to a separate `@import`ed file instead.

**Fix.**

Write the libadwaita overrides yourself and re-apply them on every theme change. Create the hook:

```bash
mkdir -p ~/.config/omarchy/hooks/theme-set.d
cat > ~/.config/omarchy/hooks/theme-set.d/20-gtk4-colors.sh <<'EOF'
#!/bin/bash
set -euo pipefail
colors=~/.local/state/omarchy/current/theme/colors.toml
[[ -f $colors ]] || exit 0
val() { sed -n "s/^$1[[:space:]]*=[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$colors" | head -1; }
bg=$(val background); fg=$(val foreground)
[[ -n $bg && -n $fg ]] || exit 0
mkdir -p ~/.config/gtk-4.0
cat > ~/.config/gtk-4.0/gtk.css <<CSS
@define-color window_bg_color $bg;
@define-color window_fg_color $fg;
@define-color view_bg_color $bg;
@define-color view_fg_color $fg;
@define-color headerbar_bg_color $bg;
@define-color headerbar_fg_color $fg;
@define-color sidebar_bg_color $bg;
@define-color sidebar_fg_color $fg;
@define-color card_bg_color $bg;
@define-color card_fg_color $fg;
@define-color popover_bg_color $bg;
@define-color popover_fg_color $fg;
CSS
# libadwaita reads the stylesheet only at startup; these are D-Bus activatable
pkill -f 'nautilus --gapplication-service' || true
pkill -x geary || true
pkill -x gnome-calendar || true
EOF
chmod +x ~/.config/omarchy/hooks/theme-set.d/20-gtk4-colors.sh
omarchy theme refresh
```

Note that GTK3 cannot be recolored this way at all — `@define-color` in the user stylesheet is provider-scoped and never reaches the Adwaita theme's own rules. GTK3 apps still need an approximate binary theme selected via `gtk-theme`.

**Verify.** `cat ~/.config/gtk-4.0/gtk.css` shows real hex values (not `#;`), and opening Nautilus after `omarchy theme set gruvbox` then `omarchy theme set tokyo-night` shows two visibly different window backgrounds.

Sources: <https://github.com/basecamp/omarchy/issues/7557> · <https://github.com/basecamp/omarchy/issues/8380>

---

## Restore bar widgets and plugins wiped by the Quattro upgrade

`shell-json-reset-by-quattro-upgrade` · severity: **medium** · frequency: **very-common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After `omarchy upgrade to quattro`, every bar customization is gone: extra bar widgets, the enabled-plugins list, `transparent: true`, and custom idle timers are all back to stock defaults. The plugin directories under `~/.config/omarchy/plugins/` are all still there, untouched — only the config was reset, with no warning.

**Cause.** `omarchy-upgrade-to-quattro` lists `omarchy/shell.json` in `always_copy_config_files` (around line 1641) and unconditionally installs the stock Quattro default over it, regardless of whether the existing file was valid and customized. `backup_config_file()` does save the old one first (suffix from `date +%Y%m%d%H%M%S`), but nothing tells you it happened. The schema is actually unchanged across the upgrade (`bar`, `idle`, `plugins`, `version` — no new required keys), so a straight restore works.

> ⚠️ **Risk.** Restoring a pre-Quattro `shell.json` wholesale can reintroduce keys the new shell does not expect — keep `shell.json.quattro-default` so you can fall back. Do not delete the `.bak` files until you have confirmed the restore works.

**Fix.**

Find the backup:

```bash
ls -la ~/.config/omarchy/shell.json*
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

Before running the upgrade in the first place, take your own copy:

```bash
cp ~/.config/omarchy/shell.json ~/shell.json.pre-quattro
```

**Verify.** `jq '.bar.layout, .plugins, .bar.transparent' ~/.config/omarchy/shell.json` shows your customizations back, and after `omarchy restart shell` the extra widgets are visible in the bar again.

Sources: <https://github.com/basecamp/omarchy/issues/8357>

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

**Symptom.** You install a theme with `omarchy theme install <git-url>` and the bar, terminal and shell all retint, but the Hyprland window borders keep the same cyan-to-green gradient for every theme, and the theme's rounding/shadow/blur never appear. Running the switch from a terminal instead of the menu prints `Ignored in /home/<user>/.config/omarchy/themes/<name>: hyprland.lua` and `A theme installed from a git repo cannot supply Lua, a terminal config, or vscode.json.` on stderr; from the Style > Theme menu you see nothing at all. `hyprctl getoption general:col.active_border` still reports the stock `rgba(33ccffee) rgba(00ff99ee) 45deg`.

**Cause.** `bin/omarchy-theme-set` treats any theme directory that contains a `.git` directory as "came from a stranger" (`theme_came_from_a_repo`) and refuses to stage anything that can run code. `is_denied_installed_file` drops every `*.lua` unconditionally, plus `alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf` and `vscode.json` (`INSTALLED_THEME_DENIED`) — Hyprland `require`s a theme's `hyprland.lua` and `gum_env.lua` at login, so that is deliberate policy, not a bug. What gets staged instead is generated from `default/themed/hyprland.lua.tpl`, which carries only `general.col.active_border` / `inactive_border` and the matching `group.col` keys, resolved from `hyprland_active_border` / `hyprland_inactive_border` in `colors.toml` with `accent` and `rgba(595959aa)` as fallbacks. Rounding, shadow and blur have no `colors.toml` channel at all, so a theme that expressed its identity in `hyprland.lua` half-works. The refusal is announced only on stderr, which the menu discards (issue #8393). Separately, even a correct `hyprland.lua` does not repaint until `omarchy-restart-hyprctl` (`hyprctl reload`) has run — it is one of the `post_theme_commands`, so a theme change that died partway leaves stale borders.

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

**Verify.** `grep active_border_color ~/.local/state/omarchy/current/theme/hyprland.lua` shows your theme's colours rather than the stock gradient, and `hyprctl getoption general:col.active_border` matches. Switching between two themes visibly changes the focused window's border.

Sources: <https://github.com/basecamp/omarchy/issues/8393> · <https://github.com/basecamp/omarchy/issues/7884> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set> · <https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md> · <https://github.com/basecamp/omarchy/blob/quattro/manual/43-making-your-own-theme.md>

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

**Cause.** `bin/omarchy-theme-install` pre-screens the URL with `bin/omarchy-git-url-check` before cloning. That refuses anything starting with `-`, anything matching `<helper>::<address>` (git's transport-helper shape — `ext::` runs a shell command), and any `<scheme>://` whose scheme is not on the allowlist `ssh git git+ssh ssh+git http https ftp ftps file`. It then derives the theme name from the URL: strip an `scp`-style `user@host:` prefix, `basename ... .git`, strip a leading `omarchy-` and a trailing `-theme`, lowercase — and refuses a name that is empty, starts with a dot, or contains a slash. Anything that survives goes to a plain `git clone`, with the terminal's stdin: a private repo over HTTPS prompts for credentials, and a first-time SSH host prompts for the host key, so the command blocks. A URL pointing at a GitHub *page* (`.../tree/main`) or a tarball is not a repository and git rejects it. And critically, the existing `~/.config/omarchy/themes/<derived-name>` is `rm -rf`'d **before** the clone runs, so a failed install destroys whatever was already there.

> ⚠️ **Risk.** `omarchy theme install` does `rm -rf "$THEME_PATH"` before it clones, so a clone that then fails leaves you with **no** theme at that name. The name is derived from the URL with `omarchy-` and `-theme` stripped, so two unrelated repos can collide on it and quietly replace each other — back up any hand-edited theme first: `cp -a ~/.config/omarchy/themes/<name> ~/theme-backup-<name>`. A cloned theme is also arbitrary content from a stranger; Omarchy drops the files that can run code but everything else is applied as-is.

**Fix.**

Run installs from a terminal, never from the Style > Theme menu, so git's prompts are visible:

```bash
omarchy theme install https://github.com/<owner>/omarchy-<name>-theme.git
```

Pre-flight the URL before you let it near your themes directory:

```bash
URL='https://github.com/<owner>/omarchy-<name>-theme.git'
omarchy-git-url-check "$URL" && echo 'url shape accepted'
git ls-remote "$URL" >/dev/null && echo 'repo reachable'
```

Accepted forms are `https://`, `http://`, `ssh://`, `git://`, `git+ssh://`, `ssh+git://`, `ftp://`, `ftps://`, `file://`, and scp-style `git@host:org/repo.git`. Copy the repo's **clone** URL, not the page URL — a `/tree/main` or `/releases/download/...` link is not a repository.

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

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-install> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-git-url-check> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-remove> · <https://github.com/basecamp/omarchy/blob/quattro/manual/43-making-your-own-theme.md>

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

**Cause.** The hicolor icon cache under `/usr/share/icons/hicolor` is stale, so the icon lookup finds nothing for the new `Icon=` name even though the icon file is on disk. Some AUR packages install icons without triggering a cache update. A separate but related failure is a `.desktop` file with no `Icon=` line at all.

> ⚠️ **Risk.** Editing files under `/usr/share/applications` directly means your change is lost on the next package upgrade — use the `~/.local/share/applications/` copy shown above instead.

**Fix.**

Rebuild the system icon cache:

```bash
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor
```

Check the desktop entry actually names an icon:

```bash
grep -n '^Icon=' /usr/share/applications/firefox.desktop
```

If the line is missing, copy the entry to your user directory and add it there rather than editing the packaged file:

```bash
cp /usr/share/applications/firefox.desktop ~/.local/share/applications/
sed -i '/^\[Desktop Entry\]/a Icon=firefox' ~/.local/share/applications/firefox.desktop
```

Confirm the icon file exists:

```bash
ls /usr/share/icons/hicolor/scalable/apps/ | grep -i firefox
```

Then refresh the launcher index:

```bash
update-desktop-database ~/.local/share/applications
omarchy restart shell     # Omarchy 4
# omarchy-restart-walker  # Omarchy 3.x
```

**Verify.** The app shows its real icon in the launcher, and `gtk-update-icon-cache` reports the cache was rewritten rather than up to date.

Sources: <https://github.com/basecamp/omarchy/issues/2547>

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

**Cause.** The Quattro upgrade moves the legacy icon directory aside — `mv -f "$legacy_icons_dir/$icon" "$legacy_icons_backup/"`, where the backup is `~/.local/share/applications/icons.omarchy-upgrade-to-quattro.<timestamp>.bak`. Your custom `.desktop` files survive, so their absolute `Icon=` paths into the old directory become dangling. Separately, the upgrade copies `Alacritty.desktop` into `~/.local/share/applications/` guarded only on the file not already existing, never on whether `alacritty` is actually installed — so the Quickshell Apps menu shows it despite its `TryExec=alacritty`.

> ⚠️ **Risk.** Do not delete the `icons.omarchy-upgrade-to-quattro.*.bak` directory until you have confirmed every referenced icon has been restored from it — it is the only copy.

**Fix.**

Restore the icons your surviving launchers still reference:

```bash
ls -d ~/.local/share/applications/icons.omarchy-upgrade-to-quattro.*.bak
mkdir -p ~/.local/share/applications/icons
cp ~/.local/share/applications/icons.omarchy-upgrade-to-quattro.*.bak/*.png \
   ~/.local/share/applications/icons/
```

Find any remaining dangling absolute icon paths:

```bash
grep -h '^Icon=/' ~/.local/share/applications/*.desktop | sed 's/^Icon=//' \
  | while read -r p; do [[ -e $p ]] || echo "MISSING: $p"; done
```

Remove the ghost launcher if alacritty is not installed:

```bash
command -v alacritty >/dev/null || rm -f ~/.local/share/applications/Alacritty.desktop
```

Rebuild the desktop database and refresh the menu:

```bash
update-desktop-database ~/.local/share/applications
omarchy restart shell
```

**Verify.** The check loop above prints no `MISSING:` lines, the Apps menu shows real icons for your custom launchers, and there is no Alacritty entry. Reopening the menu adds no new `QQuickImage Cannot open` lines to `journalctl --user -f`.

Sources: <https://github.com/basecamp/omarchy/issues/6883>

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

## Fix top-bar icons rendering at roughly half size after changing the system font

`bar-icons-half-size-with-iosevka-nerd-font-mono` · severity: **low** · frequency: **common** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** After `omarchy font set "Iosevka Nerd Font Mono"`, the top-bar icons (Wi-Fi, volume, Bluetooth, power, monitor) render at roughly half the size they did with JetBrainsMono Nerd Font. Text in the bar is fine; only the icons look shrunken.

**Cause.** The bar draws each icon as a single Nerd Font glyph at a fixed pixel size (`Style.bar.iconFont`, default 13px, scaled by `[font] base-size` in `~/.config/omarchy/shell.toml`). The *painted* size depends entirely on how each font patches the icon inside its em box. Iosevka Nerd Font Mono patches icon glyphs at about 50% of the em box (measured 500x398 units for U+F0928 Wi-Fi) while Iosevka Nerd Font Propo and JetBrainsMono Nerd Font use 75-97% (970x772 for the same codepoint). At a fixed 13px that is roughly 6.5px painted versus 12.6px. There is no config knob to compensate: `Style.qml`'s `applyShellValues` only reads `size-horizontal`, `size-vertical` and `scale-with-font` from the `[bar]` section, so the `icon-font` / `icon-canvas` / `icon-slot` tokens are not parsed from `shell.toml`.

> ⚠️ **Risk.** Raising `[font] base-size` scales text everywhere in the shell, not just the bar icons.

**Fix.**

Switch to the proportional or non-Mono Iosevka variant, which patches icons at full size:

```bash
omarchy font set "Iosevka Nerd Font Propo"
# or
omarchy font set "Iosevka Nerd Font"
omarchy restart shell
```

If you must keep the Mono variant, raise the whole bar font so the icons scale with it, in `~/.config/omarchy/shell.toml`:

```toml
[font]
base-size = 18

[bar]
scale-with-font = true
```

then:

```bash
omarchy restart shell
```

You can confirm which font file each variant resolves to:

```bash
fc-match "Iosevka Nerd Font Mono" file
fc-match "Iosevka Nerd Font Propo" file
```

**Verify.** The Wi-Fi, volume and Bluetooth icons in the bar are the same optical size as they were on JetBrainsMono Nerd Font. Toggling between `omarchy font set "Iosevka Nerd Font Mono"` and `"Iosevka Nerd Font Propo"` shows a visible size jump, confirming which font is responsible.

Sources: <https://github.com/basecamp/omarchy/issues/8608> · <https://github.com/basecamp/omarchy/issues/7305>

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

## Fix Neovim erroring with "could not load your colorscheme" after a theme change

`nvim-colorscheme-error-after-theme-change` · severity: **low** · frequency: **common** · applies to: `arch`, `omarchy`, `omarchy-4`

**Symptom.** After selecting a theme (catppuccin is the common trigger), every nvim launch fails with LazyVim's "could not load your colorscheme" error and falls back to an unthemed editor.

**Cause.** `omarchy theme set` copies the theme's `neovim.lua` into your nvim config, and it names a colorscheme your installed plugin version does not register. For catppuccin specifically, upstream renamed the colorscheme to `catppuccin-nvim` in v2.0.0 (catppuccin/nvim PR #977) because Neovim 0.12 ships its own bundled `catppuccin`. Omarchy ships no `lazy-lock.json` and has no `:Lazy sync` hook, so your lock file is entirely yours — an install from a few months ago is still on v1, where `colors/catppuccin-nvim.vim` does not exist and the colorscheme genuinely is missing.

> ⚠️ **Risk.** `:Lazy sync` updates every plugin, not just catppuccin, and rewrites `lazy-lock.json`. Prefer `:Lazy update catppuccin` for a minimal change, and commit your lock file first if you version your dotfiles.

**Fix.**

Update the plugin so the renamed colorscheme exists:

```
nvim
:Lazy update catppuccin
```

Check what your lock file is pinned to:

```bash
jq '.catppuccin' ~/.config/nvim/lazy-lock.json
```

Confirm the colorscheme file is present after updating:

```bash
ls ~/.local/share/nvim/lazy/catppuccin/colors/
# expect: catppuccin-frappe.lua catppuccin-latte.lua catppuccin-macchiato.lua
#         catppuccin-mocha.lua catppuccin-nvim.vim catppuccin.lua
```

If you need it working right now without updating, override the name in `~/.config/nvim/lua/plugins/theme.lua`:

```lua
return {
  { "LazyVim/LazyVim", opts = { colorscheme = "catppuccin-mocha" } },
}
```

**Verify.** nvim opens with no error and `:echo g:colors_name` prints e.g. `catppuccin-mocha`.

Sources: <https://github.com/basecamp/omarchy/issues/6648>

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

**Cause.** `omarchy-plymouth-set` writes the recolored assets straight into package-owned directories — `/usr/share/plymouth/themes/omarchy/` and `/usr/share/sddm/themes/omarchy/`, both owned by the `omarchy-settings` package. `omarchy update` runs `pacman -Syu`, which upgrades `omarchy-settings` and restores those files to the shipped defaults. Unlike `omarchy theme set`, the plymouth setter persists no state anywhere, so nothing knows to re-apply it — neither `omarchy-migrate` nor the `post-update` hooks touch plymouth or sddm.

> ⚠️ **Risk.** `omarchy plymouth set-by-theme` rewrites files inside the initramfs-consumed Plymouth theme directory. If a regeneration is interrupted, the boot splash and the LUKS password prompt can end up unreadable — you can still type the passphrase blind, but keep a bootable USB around before experimenting on a LUKS-encrypted machine.

**Fix.**

Record your choice and re-apply it after every update. Save the selection:

```bash
mkdir -p ~/.local/state/omarchy
echo vantablack > ~/.local/state/omarchy/unlock.name
```

Add a post-update hook that restores it:

```bash
mkdir -p ~/.config/omarchy/hooks/post-update.d
cat > ~/.config/omarchy/hooks/post-update.d/50-replymouth.sh <<'EOF'
#!/bin/bash
name_file=~/.local/state/omarchy/unlock.name
[[ -f $name_file ]] || exit 0
omarchy plymouth set-by-theme "$(cat "$name_file")"
EOF
chmod +x ~/.config/omarchy/hooks/post-update.d/50-replymouth.sh
```

Manual re-apply any time:

```bash
omarchy plymouth set-by-theme vantablack
omarchy plymouth current
```

Confirm what pacman owns, to see why it keeps reverting:

```bash
pacman -Qo /usr/share/plymouth/themes/omarchy/logo.png
pacman -Qo /usr/share/sddm/themes/omarchy/Main.qml
grep 'omarchy-settings' /var/log/pacman.log | tail -3
```

**Verify.** `omarchy plymouth current` reports your theme immediately after an `omarchy update` that upgraded `omarchy-settings`, and the LUKS prompt at boot shows the custom splash.

Sources: <https://github.com/basecamp/omarchy/issues/6864>

---

## Fix `omarchy theme bg next` never advancing past the first wallpaper

`background-next-stuck-on-symlinked-backgrounds` · severity: **low** · frequency: **occasional** · applies to: `hyprland`, `omarchy`, `omarchy-4`, `wayland`

**Symptom.** `omarchy theme bg next` sets the first wallpaper and then does nothing on every subsequent press. `omarchy theme bg current` reports the same file every time. Only happens when `~/.config/omarchy/backgrounds/<theme>/` is a symlink into a dotfiles repo (stow, chezmoi).

**Cause.** A path-canonicalisation mismatch between two scripts. `bin/omarchy-theme-bg-set:12` stores the current background with `realpath "$1"` — symlink *resolved* (`/home/u/dotfiles/.../foo.jpg`). `bin/omarchy-theme-bg-next` builds its candidate list with `find -L "$HOME/.config/omarchy/backgrounds/$THEME_NAME/"`, which yields *unresolved* paths, then string-compares them against `readlink` of the state symlink. The strings never match, `INDEX` stays `-1`, and the script falls through to `BACKGROUNDS[0]` every time. Stock theme backgrounds are unaffected because `current/theme/backgrounds/` is a real copied directory. There is also no `bg prev` command at all, so you cannot step backwards.

> ⚠️ **Risk.** `bin/omarchy-theme-bg-next` is package-owned; a manual patch is reverted on the next `omarchy update`.

**Fix.**

Simplest workaround — use a real directory instead of a symlink:

```bash
rm ~/.config/omarchy/backgrounds/<theme>
mkdir -p ~/.config/omarchy/backgrounds/<theme>
cp ~/dotfiles/walls/* ~/.config/omarchy/backgrounds/<theme>/
```

Or patch the comparison to canonicalise both sides. In `bin/omarchy-theme-bg-next`, change the current-background read and the loop comparison to:

```bash
CURRENT_BACKGROUND=$(readlink -f "$CURRENT_BACKGROUND_LINK")
...
if [[ $(realpath "${BACKGROUNDS[$i]}") == "$CURRENT_BACKGROUND" ]]; then
```

The same fix applies to `choose_theme_background` in `bin/omarchy-theme-set`.

**Verify.** Pressing the background-next binding four times cycles `a.jpg -> b.jpg -> c.jpg -> a.jpg`; `omarchy theme bg current` changes on each press.

Sources: <https://github.com/basecamp/omarchy/issues/8594> · <https://github.com/basecamp/omarchy/issues/8508>

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

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-theme-set-templates> · <https://github.com/basecamp/omarchy/blob/quattro/default/themed/shell.toml.tpl> · <https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md>

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
