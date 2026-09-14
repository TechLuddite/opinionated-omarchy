# Wayland app compatibility

38 problems. Sorted by severity, then by how often users hit it.

## Fix screen share showing a black rectangle or no picker at all

`screenshare-black-screen-no-portal` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Screen sharing does nothing, or shares a black rectangle. In Google Meet / Discord / Zoom the "share screen" dialog either never appears or shows an empty source list. No picker window pops up at all. Sometimes apps also take 20+ seconds to launch.

**Cause.** xdg-desktop-portal-hyprland (XDPH) is not running, or it is running but cannot talk to the compositor because XDG_CURRENT_DESKTOP / WAYLAND_DISPLAY were never imported into the systemd user session and the D-Bus activation environment. XDPH is D-Bus-activated, so it appears "installed" while being completely non-functional. Screen capture on Wayland goes app -> xdg-desktop-portal -> XDPH -> PipeWire; if any link is missing you get silence or black frames.

**Fix.**

Install the whole chain and make sure PipeWire is up:

```bash
sudo pacman -S --needed pipewire wireplumber xdg-desktop-portal xdg-desktop-portal-hyprland xdg-desktop-portal-gtk qt6-wayland
systemctl --user enable --now pipewire.service pipewire-pulse.service wireplumber.service
```

Check the systemd user session actually has the XDG variables (this is the usual culprit):

```bash
systemctl --user show-environment | grep -E 'XDG_CURRENT_DESKTOP|WAYLAND_DISPLAY'
```

If either is missing, import them and restart the portals:

```bash
systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP=Hyprland
systemctl --user restart xdg-desktop-portal-hyprland.service xdg-desktop-portal.service
```

Make it permanent in your Hyprland config so it happens before the portals start.

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/autostart.lua`):

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("systemctl --user import-environment $(env | cut -d'=' -f 1)")
  hl.exec_cmd("dbus-update-activation-environment --systemd --all")
end)
```

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/hyprland.conf`):

```conf
env = XDG_CURRENT_DESKTOP,Hyprland
env = XDG_SESSION_TYPE,wayland
env = XDG_SESSION_DESKTOP,Hyprland
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
```

Omarchy already ships exactly this in `/usr/share/omarchy/default/hypr/envs.lua` and `autostart.lua`, so on a stock Omarchy the fault is nearly always a stopped/crashed portal — restart it with the `systemctl --user restart` line above.

**Verify.** `systemctl --user status xdg-desktop-portal-hyprland` shows `active (running)` with log lines `[screencopy] Registered for toplevel export` and `[screenshot] init successful`. Then open https://mozilla.github.io/webrtc-landing/gum_test.html and click the screen-share button — a Qt/GTK picker listing your monitors must appear.

Sources: <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://wiki.archlinux.org/title/PipeWire> · <https://wiki.hypr.land/Useful-Utilities/Screen-Sharing/> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.hypr.land/0.54.0/Configuring/Environment-variables/>

---

## Fix Discord screen share stopping after about a second

`discord-screenshare-stops-after-one-second` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Screen share starts and immediately stops after about a second, and the list of shareable windows is frozen — opening or closing windows no longer updates it. Portal log shows: `[WARN] [pipewire] Asked for a wl_shm buffer which is legacy.`, `[WARN] [pw] DMA-BUF allocation failed, falling back to SHM`, `[LOG] [sc] Incompatible formats, renegotiate stream`, `[ERR] [screencopy] tried scheduling on already scheduled cb (type 1)`.

**Cause.** XDPH's screencopy session state was left corrupt after a previous share ended (buffer renegotiation between DMA-BUF and SHM raced and double-scheduled a frame callback), so the portal kept running but every subsequent ScreenCast session died immediately. Reported against xdg-desktop-portal-hyprland 1.4.0 with Hyprland 0.56. **This was fixed upstream** by commit `c46162255e00` ('core: fix loop hangup detection', 2026-07-24), released in XDPH v1.4.1 (2026-07-29), which Arch `extra` now carries - so on a current system this is an out-of-date XDPH rather than a live bug.

> **Audit corrected this record.** Symptom, logs, cause and the restart workaround all match xdg-desktop-portal-hyprland#418 verbatim — but the record is now obsolete as written. That issue was closed by upstream commit c46162255e00 ('core: fix loop hangup detection', 2026-07-24), which shipped in XDPH v1.4.1 (2026-07-29). Arch extra currently carries 1.4.1-1. Telling a user to permanently pin force_shm — which the XDPH wiki explicitly documents as the slower path, especially at high resolutions — when a plain system upgrade fixes the bug outright is the wrong first move. The force_shm advice itself is valid (the option exists, and the Omarchy caveat about editing the existing screencopy block is correct) but belongs after the upgrade, scoped to genuine multi-GPU DMA-BUF allocation failures.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `force_shm = true` sends every frame through shared memory instead of a GPU buffer. At 4K/high refresh this raises CPU use noticeably. Only set it if DMA-BUF allocation is actually failing in the logs.

**Fix.**

First: this exact bug (xdg-desktop-portal-hyprland#418) was fixed upstream and the fix is in XDPH 1.4.1, which is already in Arch `extra`. Upgrade before doing anything else:

```bash
sudo pacman -Syu
pacman -Q xdg-desktop-portal-hyprland   # want 1.4.1 or newer
```

Then restart the backend once:

```bash
systemctl --user restart xdg-desktop-portal-hyprland.service
```

That restart is also the immediate recovery if you hit the frozen-source-list state on an older build — no logout needed.

Only if you are on 1.4.1+ and DMA-BUF allocation still genuinely fails (real multi-GPU / hybrid laptops) fall back to shared memory in `~/.config/hypr/xdph.conf`:

```conf
screencopy {
    max_fps = 60
    force_shm = true
}
```

`force_shm` is a real XDPH option, but SHM is slower than DMA-BUF (noticeably so at high resolution), so treat it as a workaround and not a default. Omarchy ships its own `~/.config/hypr/xdph.conf` containing a `screencopy { }` block with `allow_token_by_default` and `custom_picker_binary` — add `force_shm` inside that existing block rather than creating a second one. Restart the portal again afterwards.

**Verify.** Start a share, stop it, and start a second one — the second share must survive past a few seconds and the source list must refresh when you open a new window.

Sources: <https://github.com/hyprwm/xdg-desktop-portal-hyprland/issues/418> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/>

---

## Add a working PipeWire screen capture source to OBS

`obs-no-screen-capture-source` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** OBS has no working screen capture — there is no "Screen Capture (PipeWire)" source in the Add Source list, or adding it shows a black preview. Or OBS refuses to start at all with a Qt platform plugin error.

**Cause.** OBS 28+ is a Qt 6 app and needs qt6-wayland to run natively on Wayland. Screen capture on Wayland goes through the PipeWire source, which needs the portal chain up and running; without it OBS falls back to nothing.

**Fix.**

```bash
sudo pacman -S --needed obs-studio qt6-wayland pipewire wireplumber xdg-desktop-portal xdg-desktop-portal-hyprland
systemctl --user enable --now pipewire.service wireplumber.service
systemctl --user restart xdg-desktop-portal-hyprland.service
```

In OBS: Sources -> + -> **Screen Capture (PipeWire)**. The Hyprland share picker appears; pick a monitor or a window.

Check OBS actually found the PipeWire capture backend by launching it from a terminal:

```bash
obs
```

You should see:

```
info: Platform: Wayland
info: [pipewire] Available capture sources:
info: [pipewire]     - Monitor source
info: [pipewire]     - Window source
```

If `Platform:` says X11, OBS is on XWayland and will only capture X11 windows.

For capturing Vulkan/OpenGL games without portal overhead, use the direct hook instead:

```bash
yay -S obs-vkcapture lib32-obs-vkcapture
```

**Verify.** OBS log shows `info: [pipewire] Available capture sources:` with a Monitor source, and a Screen Capture (PipeWire) source shows live video in the preview.

Sources: <https://wiki.archlinux.org/title/Open_Broadcaster_Software> · <https://wiki.archlinux.org/title/PipeWire> · <https://wiki.hypr.land/0.54.0/FAQ/> · <https://github.com/basecamp/omarchy/issues/6040>

---

## Fix the share picker crashing on a missing Qt6 Wayland library

`share-picker-crashes-missing-qt6-wayland` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Screen share silently fails. `journalctl --user -u xdg-desktop-portal-hyprland` or `systemctl --user status xdg-desktop-portal-hyprland` shows: `hyprland-share-picker[5621]: Could not load the Qt platform plugin "wayland" in "" even though it was found.` followed by `This application failed to start because no Qt platform plugin could be initialized.` and `No shell integration named "xdg-shell" found`.

**Cause.** `hyprland-share-picker` is a Qt 6 application and needs the `qt6-wayland` platform plugin to create a window; without a usable one the picker dies instantly and the portal never gets a selection back, so the calling app just sees the share request fail. Read the log carefully to tell the two states apart: 'Could not load the Qt platform plugin "wayland" ... **even though it was found**', together with 'No shell integration named "xdg-shell" found', means `qt6-wayland` is installed but ABI-mismatched against `qt6-base` after a partial upgrade - the plugin is present and refuses to load. The same root cause makes OBS unable to open.

> **Audit corrected this record.** The problem is real and the cited source (xdg-desktop-portal-hyprland#367) is genuine, but the fix does not follow from the log that is quoted. 'Could not load the Qt platform plugin "wayland" ... even though it was found' plus 'No shell integration named "xdg-shell" found' means qt6-wayland IS installed but is ABI-mismatched against qt6-base (classic partial upgrade). Against that state `pacman -S --needed qt6-wayland` is a silent no-op because --needed skips already-installed packages, so the user runs the command, sees 'nothing to do', and concludes the record is wrong. The maintainer's own resolution in that issue was to reinstall qt6-base and qt6-wayland together. Also: hyprland-share-picker is Qt6 only, so qt5-wayland is irrelevant to it.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

First rule out a partial upgrade, which is the actual cause when the log says the plugin was FOUND but could not load:

```bash
sudo pacman -Syu
```

If qt6-wayland was simply absent, that installs it. If it was present but ABI-mismatched with qt6-base (the case in xdg-desktop-portal-hyprland#367), force a matched reinstall of both:

```bash
sudo pacman -S qt6-base qt6-wayland
```

Only if pacman insists they are already up to date and the picker still dies, force the file reinstall:

```bash
sudo pacman -S --overwrite '*' qt6-base qt6-wayland
```

Then restart the backend:

```bash
systemctl --user restart xdg-desktop-portal-hyprland.service
```

If the picker starts but is unthemed, push the Qt theme vars into the activation environment (this pair is straight off the Hyprland wiki):

```bash
dbus-update-activation-environment --systemd --all
systemctl --user import-environment QT_QPA_PLATFORMTHEME
```

Test the picker standalone — it should open a window instead of exiting:

```bash
hyprland-share-picker
```

Note: on Omarchy the stock Qt picker is replaced by `hyprland-preview-share-picker` in `~/.config/hypr/xdph.conf`, so run that binary instead when testing there.

**Verify.** `hyprland-share-picker` opens a window listing outputs/windows instead of printing the Qt platform plugin error. Screen share in a browser now shows the picker.

Sources: <https://github.com/hyprwm/xdg-desktop-portal-hyprland/issues/367> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.hypr.land/0.54.0/FAQ/>

---

## Stop Steam games flickering between sizes instead of going fullscreen

`steam-games-xwayland-fullscreen-flicker` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`, `xwayland`

**Symptom.** Steam games will not go fullscreen — the window rapidly flickers between sizes and positions, sometimes z-fighting with the bar. Mashing SUPER+F occasionally lands on a maximised window. Windowed mode works, but switching back to fullscreen restarts the flicker. Separately: fullscreen games open at the wrong monitor's resolution on multi-monitor setups.

**Cause.** An XWayland fullscreen-request loop: the game asks X for a mode change, XWayland resizes the surface, the compositor responds with a different size, and the game asks again. On multi-monitor setups the second symptom is that XWayland's default primary output is not the monitor you want, so games size themselves to the wrong screen.

> **Audit corrected this record.** The diagnosis is sound and omarchy#4595 ('Steam games (xwayland) won't fullscreen.') is real, as is gamescope in extra. The gap is that `xrandr` is not present on a stock Omarchy install — xorg-xrandr is not in install/omarchy-base.packages — so the very first step, an exec-once/autostart line calling xrandr, fails silently at session start with 'command not found' and the user never learns why the wrong-monitor fix did nothing. A command placed in autostart must come with its package. Two smaller gaps: `hyprctl monitors` is offered for finding the ID but the XWayland-side name should be confirmed with `xrandr --listmonitors`, and the trailing stayfocused rule is given only in hyprlang with no 0.55+ form.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

For the wrong-monitor resolution, set the X11 primary output at session start. `xrandr` is NOT installed by default on Omarchy — install it first or the autostart line silently does nothing:

```bash
sudo pacman -S --needed xorg-xrandr
```

Find your monitor ID with `hyprctl monitors`, and confirm XWayland sees the same name with `xrandr --listmonitors`, then:

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/hyprland.conf`):

```conf
exec-once = xrandr --output DP-3 --primary
```

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/autostart.lua`):

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("xrandr --output DP-3 --primary")
end)
```

For the fullscreen flicker, run the game inside gamescope, which gives it a fixed, stable output to fullscreen into:

```bash
sudo pacman -S --needed gamescope
```

Then in Steam -> game Properties -> Launch Options (match -W/-H/-r to your actual monitor):

```
gamescope -f -W 2560 -H 1440 -r 144 -- %command%
```

Many reports are also fixed by switching the game's compatibility tool to **Proton Experimental** (Properties -> Compatibility -> Force the use of a specific Steam Play compatibility tool), or by using Proton-GE's Wayland driver.

If a game's popups/dropdowns vanish on hover (common with the Steam client itself), pin them with a window rule — get class/title from `sleep 3 && hyprctl clients`:

Hyprland <=0.54 / Omarchy 3.x:

```conf
windowrule = stayfocused, class:^(steam)$, title:^(Friends List)$
```

Hyprland 0.55+ / Omarchy 4.x:

```lua
hl.window_rule({
    match = { class = "^(steam)$", title = "^(Friends List)$" },
    stay_focused = true
})
```

**Verify.** The game enters fullscreen and stays there through an alt-tab cycle, at the correct monitor's native resolution.

Sources: <https://github.com/basecamp/omarchy/issues/4595> · <https://wiki.hypr.land/0.54.0/FAQ/> · <https://wiki.archlinux.org/title/Steam>

---

## Fix an XWayland app that can only offer other X11 windows to share

`xwayland-app-cannot-share-wayland-windows` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`, `xwayland`

**Symptom.** In Discord (native app), Skype, or any other X11/XWayland app, the screen-share source list only shows a couple of other X11 windows — your Wayland apps and "Entire Screen" are missing, or sharing the whole screen gives a black/frozen image. The same site works fine in Firefox.

**Cause.** An app running under XWayland talks to the X server, not to the Wayland compositor. X11 screen capture can only see the XWayland root window and other XWayland clients; native Wayland surfaces are simply not part of that X screen. This is a structural limitation, not a bug in Hyprland.

> **Audit corrected this record.** Cause and overall strategy are correct. Three concrete defects: (1) `~/.config/hypr/windows.lua` does not exist in Omarchy 4.x and nothing requires it — config/hypr/hyprland.lua only requires hypr.monitors, hypr.input, hypr.bindings, hypr.looknfeel, hypr.autostart, so a rule written there is silently never loaded. (2) In the Lua window-rule schema the `opacity` effect takes a STRING (e.g. "0.8", with an optional " override" suffix); `opacity = 0.0` is the wrong type and drops the `override` that the hyprlang version correctly has, so the rule will not fully hide the bridge. (3) On Omarchy, ELECTRON_OZONE_PLATFORM_HINT=wayland is already exported globally in default/hypr/envs.lua, so the `ELECTRON_OZONE_PLATFORM_HINT=wayland discord` line is a no-op there. Also worth flagging: xwaylandvideobridge is AUR-only and currently marked out-of-date.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Best fix — make the app run natively on Wayland so it uses the XDG ScreenCast portal:

```bash
# Discord / any Electron app
ELECTRON_OZONE_PLATFORM_HINT=wayland discord
```

On Omarchy this variable is already exported globally in `/usr/share/omarchy/default/hypr/envs.lua`, so the app is already native Wayland and this line changes nothing — skip to the bridge below.

Or use a Wayland-native client (`vesktop` for Discord) or the web app in Firefox/Chromium.

If the app cannot be moved off XWayland, install KDE's xwaylandvideobridge from the AUR (note: currently flagged out-of-date, build may need attention):

```bash
yay -S xwaylandvideobridge
```

Hyprland does not support the way it hides its own window, so hide it with window rules.

Hyprland 0.55+ / Omarchy 4.x — Omarchy has no `windows.lua`, so either append this to the bottom of `~/.config/hypr/hyprland.lua`, or create `~/.config/hypr/windows.lua` AND add `require("hypr.windows")` to `~/.config/hypr/hyprland.lua`:

```lua
hl.window_rule({
    name = "xwayland-video-bridge-fixes",
    match = { class = "xwaylandvideobridge" },
    no_initial_focus = true,
    no_focus = true,
    no_anim = true,
    no_blur = true,
    max_size = {1,1},
    opacity = "0.0 override"
})
```

(`opacity` is a string effect; a bare `0.0` is the wrong type and loses the `override`.)

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/hyprland.conf`):

```conf
windowrulev2 = opacity 0.0 override, class:^(xwaylandvideobridge)$
windowrulev2 = noanim, class:^(xwaylandvideobridge)$
windowrulev2 = noinitialfocus, class:^(xwaylandvideobridge)$
windowrulev2 = maxsize 1 1, class:^(xwaylandvideobridge)$
windowrulev2 = noblur, class:^(xwaylandvideobridge)$
```

**Verify.** `hyprctl clients -j | grep -A2 xwayland` for the sharing app shows `"xwayland": false`, or the share source list now offers your monitors and Wayland windows.

Sources: <https://wiki.hypr.land/Useful-Utilities/Screen-Sharing/> · <https://wiki.archlinux.org/title/Wayland>

---

## Fix Zoom offering no screens to share, or sharing a black window

`zoom-screen-share-not-working-wayland` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** In the Zoom desktop client, clicking "Share Screen" either shows no screens to pick, or shares a black/frozen window. Sharing works for other apps on the same machine.

**Cause.** Zoom's Linux desktop client does not use the XDG desktop portal for screen capture until its own Wayland share path is turned on. That path is gated behind `enableWaylandShare` in `~/.config/zoomus.conf`, and until it is set Zoom falls back to X11 capture. Under XWayland on Hyprland, X11 capture sees only XWayland surfaces, so the picker offers nothing useful or the shared frame is black. On Omarchy 4 the rest of the chain is already correct and is not the cause: `xdg-desktop-portal`, `xdg-desktop-portal-hyprland` and `pipewire` are installed by default, both portal units run, and `/usr/share/omarchy/default/hypr/envs.lua` already exports the `XDG_CURRENT_DESKTOP` and `XDG_SESSION_TYPE` values the portal needs. Zoom's own capture mode can also sit on Automatic and never select PipeWire even when everything else is in place.

> **Audit corrected this record.** Checked every claim against the current ArchWiki Zoom Meetings page, fetched 2026-09-13 via index.php?action=raw, and against this Omarchy 4.0.2-1 workstation. The wiki still documents all four of the record's client-side steps verbatim: `enableWaylandShare=true` in `~/.config/zoomus.conf` for Wayland screen share, the Settings then Share Screen then Advanced then Screen capture mode PipeWire fallback, `xwayland=false` to run without XWayland with the ZoomWebviewHost 0MB caveat the record's `danger` reproduces, `QT_SCALE_FACTOR=2` for the undersized UI, and the `/j/` to `/wc/join/` web client rewrite. So the record is not stale advice and it is not a duplicate of `share-picker-never-appears-selection-minus-one`: that record is about the picker binary itself returning selection -1, this one is about Zoom's own config gate, and they only share a symptom. Three defects were found. First, "Install the WebRTC screen-sharing prerequisites" is not a concrete fix and the corpus convention rejects that shape, and on Omarchy it is a no-op, confirmed here by `pacman -Q`: xdg-desktop-portal 1.22.1-2, xdg-desktop-portal-hyprland 1.4.1-1, pipewire 1:1.6.8-1, with both user units active since 2026-09-06 and `org.freedesktop.impl.portal.desktop.hyprland` owned on the session bus. Second, the `verify` line is wrong for Omarchy in two ways: the picker is `hyprland-preview-share-picker` 0.2.1-1, which `readelf -d` shows links libgtk-4 and libgtk4-layer-shell and no Qt at all, selected by `custom_picker_binary` in `~/.config/hypr/xdph.conf`, and that same file sets `allow_token_by_default = true`, so a repeat share can be auto-restored with no picker at all and the old verify would read as a failure. Third, the record implies `xwayland=false` cures the black window, which https://bbs.archlinux.org/viewtopic.php?id=313237 contradicts: that thread, posts dated 2026-04, tracked window sharing going black on Hyprland and concluded the fault was Wayland-side rather than XWayland-specific, with the browser client the only thing that worked. Rewrote `cause`, `fix` and `verify`, kept `symptom`, `danger`, `severity` and `frequency` as they stand, since the danger matches the wiki's "Running on Wayland without Xwayland" and "Disable ZoomWebviewHost" sections. NOT exercised: Zoom itself is not installed here (`pacman -Q zoom` fails, `~/.config/zoomus.conf` does not exist) and installing it is out of scope for an audit on the operator's workstation, so no zoomus.conf key and no share attempt was tested live. The AUR `zoom` package was confirmed to exist at 7.1.5.4332, last modified 2026-07-21, but its bundled Qt platform plugins were not inspected.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Setting `xwayland=false` is documented to make the ZoomWebviewHost process stop with 0MB memory, which disables whiteboard and some in-meeting features. Revert it if you lose functionality.

**Fix.**

On Omarchy 4 the portal side of this already ships. Confirm it rather than installing anything:

```bash
pacman -Q xdg-desktop-portal xdg-desktop-portal-hyprland pipewire
systemctl --user status xdg-desktop-portal xdg-desktop-portal-hyprland
```

Measured on Omarchy 4.0.2-1: `xdg-desktop-portal 1.22.1-2`, `xdg-desktop-portal-hyprland 1.4.1-1`, `pipewire 1:1.6.8-1`, all installed and both units running. On plain Arch install `xdg-desktop-portal`, a wlroots backend such as `xdg-desktop-portal-hyprland`, and `pipewire` first.

1. Turn on Zoom's Wayland share path in `~/.config/zoomus.conf`:

```ini
enableWaylandShare=true
```

Quit Zoom completely from the tray, not just the window, then start it again.

2. If Zoom still refuses to use PipeWire, force it in the GUI: Settings, then Share Screen, then Advanced, then set Screen capture mode to PipeWire instead of Automatic.

3. Only if Zoom is still running under XWayland and you want it native, also set in `~/.config/zoomus.conf`:

```ini
xwayland=false
```

Do not reach for this first. Omarchy already exports `XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=Hyprland` and `QT_QPA_PLATFORM=wayland;xcb` from `/usr/share/omarchy/default/hypr/envs.lua`, and `XDG_CURRENT_DESKTOP=Hyprland` is what makes `xdg-desktop-portal` pick `hyprland.portal` for ScreenCast, so do not set any of those by hand. Going native also does not cure a black shared window. The Arch forum thread cited below tracked window sharing going black on Hyprland and found it happened under native Wayland as well as under XWayland.

If the Zoom UI is then too small on a HiDPI screen:

```bash
QT_SCALE_FACTOR=2 zoom
```

4. If no application can share, not Zoom and not Chromium and not OBS, the fault is the share picker rather than Zoom. See the record `share-picker-never-appears-selection-minus-one`.

5. If none of this works, the Zoom web client avoids the desktop client entirely. Replace `/j/` with `/wc/join/` in the meeting URL:
`https://<subdomain>.zoom.us/wc/join/<meeting_id>?pwd=<password>`

**Verify.** Start a meeting and click Share Screen. On Omarchy the window that appears is `hyprland-preview-share-picker` (package `hyprland-preview-share-picker` 0.2.1-1, a GTK4 program), not the stock Qt `hyprland-share-picker` from xdg-desktop-portal-hyprland, because `~/.config/hypr/xdph.conf` sets `custom_picker_binary = hyprland-preview-share-picker`. Pick an output and check the shared preview shows live desktop content rather than black.

Omarchy also sets `allow_token_by_default = true` in that same file, so sharing the same target again can be restored from a token with no picker shown at all. A silent restore is expected on Omarchy and is not a failure. Changes to `xdph.conf` only take effect when the portal restarts, for example at next login.

Sources: <https://wiki.archlinux.org/title/Zoom_Meetings> · <https://wiki.archlinux.org/title/PipeWire> · <https://bbs.archlinux.org/viewtopic.php?id=313237> · <https://aur.archlinux.org/packages/zoom>

---

## Stop Chromium's GPU process crashing repeatedly on NVIDIA

`chromium-xwayland-nvidia-gpu-crash` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`, `xwayland`

**Symptom.** Chromium's GPU process crashes repeatedly on NVIDIA — tabs go blank or show "Aw, Snap!", `chrome://gpu` reports the GPU process restarting. On Omarchy some users additionally see Chromium die with `SIGTRAP (int3)` at a fixed offset when a new window is spawned for an OAuth popup, in a ~20-crash loop, while the same flow works on KDE Plasma.

**Cause.** Two different problems share the symptom.

The XWayland GPU-process crashes are Chromium's ANGLE and GL backend selection failing on the proprietary NVIDIA driver, and they only apply when Chromium is genuinely running on XWayland. Omarchy seeds `~/.config/chromium-flags.conf` from `/usr/share/omarchy/config/chromium-flags.conf`, which sets `--ozone-platform=wayland`, so on a stock Omarchy install Chromium is native Wayland and this half does not apply unless the user has switched it to X11.

The `SIGTRAP` (`int3`) crash loop reported in omacom/omarchy#8394 has no established cause. The reporter suspected Ozone and Wayland GPU initialisation, but the only reproduction on the thread sees the same `SIGTRAP` under `--ozone-platform=x11` and with extensions disabled, and isolates the common factor as the `--oauth2-client-id` and `--oauth2-client-secret` lines that `omarchy-install-chromium-google-account` appends to `~/.config/chromium-flags.conf`. The issue was still open on 2026-09-13.

> **Audit corrected this record.** Checked on this workstation, which has an NVIDIA RTX 3090 with nvidia-open-dkms 610.57.04-1 and nvidia_drm loaded, omarchy 4.0.2-1, Hyprland 0.56.2, and chromium 151.0.7922.173-1, the exact Chromium build the cited issue names. Three things held. The flag file mechanism is real: /usr/bin/chromium is Arch's launcher and its embedded help text says custom flags are read from /etc/chromium-flags.conf and $XDG_CONFIG_HOME/chromium-flags.conf, so the record is not writing flags to a file nothing reads. The two ANGLE switches exist in the shipped binary (strings on /usr/lib/chromium/chromium matches use-angle, use-cmd-decoder, and the values vulkan and passthrough), and the Arch wiki section Running on Xwayland recommends exactly --use-angle=vulkan --use-cmd-decoder=passthrough for NVIDIA GPU-process crashes. coredumpctl list and journalctl -b -k both run unprivileged here, so the diagnostic commands work as written. Four things were wrong. First, the cause states as fact what the issue reporter offered as a guess. omacom/omarchy#8394 is still OPEN as of 2026-09-13 with no root cause, and the only reproduction comment on the thread (btownsend, on 4.0.2-1 with the same Chromium build) gets the identical SIGTRAP under X11 and with extensions disabled, and isolates the common factor as the --oauth2-client-id and --oauth2-client-secret lines that /usr/share/omarchy/bin/omarchy-install-chromium-google-account appends to ~/.config/chromium-flags.conf. It is not established to be a GPU or Ozone fault. Second, the record presents --ozone-platform=x11 as an alternative that also avoids the crash, which is the original reporter's table but is directly contradicted by that reproduction, so the record must not recommend it as reliable. Third, the record says add to ~/.config/chromium-flags.conf without noting that on Omarchy that file already exists, seeded from /usr/share/omarchy/config/chromium-flags.conf, and already contains --ozone-platform=wayland and --ozone-platform-hint=wayland, so appending --ozone-platform=x11 leaves two contradictory lines (base::CommandLine::AppendSwitchNative does switches_[key] = value so the last wins for lookups, but both stay in argv_ and are passed to child processes, and the honest instruction is to edit the existing line). Fourth, the record does not say that on a stock Omarchy install Chromium is already native Wayland, so the XWayland half only applies once the user has moved it to X11. Added to verify a check that the flag was actually read, because chrome://version lists the full command line. The cited issue URL uses the old basecamp/omarchy name, replaced with omacom/omarchy. NOT exercised: I did not launch Chromium, did not reproduce the SIGTRAP, and did not test the ANGLE flags, because this is the operator's daily workstation.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `--disable-gpu` turns off hardware acceleration for the whole browser: expect higher CPU use and no hardware video decode. Treat it as a stopgap. `--ozone-platform=x11` moves Chromium back onto XWayland, which is the condition the ANGLE flags above exist to work around, and one reproducer on omacom/omarchy#8394 reports it does not stop the crash. Deleting the `--oauth2-client-*` lines removes Chromium's ability to sign in to a Google account until you re-run `omarchy-install-chromium-google-account`.

**Fix.**

On Omarchy `~/.config/chromium-flags.conf` already exists and is seeded from `/usr/share/omarchy/config/chromium-flags.conf`. Append to it, and where you are contradicting a line that is already there, edit that line instead of adding a second copy. Chromium's launcher reads `/etc/chromium-flags.conf` and then `~/.config/chromium-flags.conf` into one command line, and a duplicated switch is both confusing and unreliable across child processes.

**XWayland GPU-process crashes on NVIDIA.** Only relevant if Chromium is actually on X11 or XWayland:

```
--use-angle=vulkan
--use-cmd-decoder=passthrough
```

The Arch wiki attaches a note to these: they do not prevent all XWayland-related crashes.

**The `SIGTRAP` (`int3`) crash loop on Hyprland (omacom/omarchy#8394).** The workaround the issue reports as working is to take the GPU out of the path:

```
--disable-gpu
```

Do not rely on `--ozone-platform=x11` here. The original reporter listed it as working, but the one person who reproduced the bug saw the same `SIGTRAP` under X11. If you try it anyway, change the existing `--ozone-platform=wayland` line rather than adding a second one, and remove `--ozone-platform-hint=wayland` at the same time.

If you added Google sign-in with `omarchy-install-chromium-google-account`, that reproduction points at the OAuth flags it appended, and removing them is the narrowest test:

```bash
sed -i '/^--oauth2-client-/d' ~/.config/chromium-flags.conf
```

Flags are only read at process start, so quit Chromium entirely and relaunch:

```bash
pkill chromium
```

Check what actually crashed:

```bash
coredumpctl list chromium
journalctl -b -k | grep -i 'trap int3'
```

**Verify.** `chrome://gpu` no longer shows the GPU process restarting, and the OAuth login popup opens instead of crash-looping. Confirm the flag was actually read before concluding anything: `chrome://version` prints the full command line, and the flag you added must appear in it.

Sources: <https://wiki.archlinux.org/title/Chromium> · <https://github.com/omacom/omarchy/issues/8394> · <https://chromium.googlesource.com/chromium/src/+/refs/heads/main/base/command_line.cc>

---

## Fix an Electron app that runs but never shows a window

`electron-app-no-window-ozone-wayland` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `electron`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** An Electron app starts — the process is alive in `ps` — but no window ever appears. `hyprctl clients` shows no client for it. No error, no crash, it just sits there. Often hit with games shipping a bundled Electron runtime, or older Electron builds launched from Steam.

**Cause.** Omarchy globally exports `ELECTRON_OZONE_PLATFORM_HINT=wayland` and `OZONE_PLATFORM=wayland` in `/usr/share/omarchy/default/hypr/envs.lua`. An app built against an Electron version whose Wayland/Ozone backend is broken or absent will fail to create a surface and silently produce no window instead of falling back to X11.

> **Audit corrected this record.** The core fix is correct and well-sourced: omarchy#7642 exists with that exact title, and Omarchy's default/hypr/envs.lua really does export both ELECTRON_OZONE_PLATFORM_HINT=wayland and OZONE_PLATFORM=wayland, so unsetting BOTH is genuinely required — the record gets this right where record 13 does not. The problem is the trailing elephant section. It is quoted accurately from omarchy#6206, but that issue is against Omarchy 3.x (Elephant 2.21 / Walker 2.16), and Omarchy 4.x has removed elephant entirely — there is no config/elephant directory and no elephant.service on the quattro branch. An Omarchy 4 user following that step gets 'Unit elephant.service not found' after writing a config file nothing reads.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting `hl.env("OZONE_PLATFORM", "")` globally pushes every Electron app back to XWayland, where they will be blurry on HiDPI and unable to screen-share Wayland windows. Prefer the per-app override.

**Fix.**

Unset both variables for that one process — Omarchy sets ELECTRON_OZONE_PLATFORM_HINT *and* OZONE_PLATFORM, so unsetting only one leaves the app on Wayland. From a terminal:

```bash
env -u ELECTRON_OZONE_PLATFORM_HINT -u OZONE_PLATFORM <app>
```

From Steam, in the game's Properties -> Launch Options:

```
env -u ELECTRON_OZONE_PLATFORM_HINT -u OZONE_PLATFORM %command%
```

For a desktop launcher, copy the entry to your user directory and wrap the Exec line:

```bash
cp /usr/share/applications/<app>.desktop ~/.local/share/applications/
```

```ini
Exec=env -u ELECTRON_OZONE_PLATFORM_HINT -u OZONE_PLATFORM /usr/bin/<app> %U
```

For Arch's shared `electron` package you can also pin flags per app in `~/.config/<application_name>-flags.conf`, e.g. `~/.config/vesktop-flags.conf`:

```
--ozone-platform=x11
```

**Omarchy 3.x only** — a related but different failure: the Elephant/Walker launcher may run apps under `systemd-run --user --scope`, which makes some Electron apps segfault and leave stale `~/.config/<App>/SingletonLock` files (omarchy#6206). Pin the launcher prefix in `~/.config/elephant/elephant.toml`:

```toml
auto_detect_launch_prefix = false
launch_prefix = "uwsm-app --"
```

then `systemctl --user restart elephant.service`.

This does not apply to Omarchy 4.x, which dropped Elephant and Walker for the Quickshell-based launcher — there is no `elephant.service` to restart there.

**Verify.** `hyprctl clients | grep -i <app>` now returns a client, and the window is visible.

Sources: <https://github.com/basecamp/omarchy/issues/7642> · <https://github.com/basecamp/omarchy/issues/6206> · <https://wiki.archlinux.org/title/Electron> · <https://wiki.archlinux.org/title/Wayland>

---

## No CJK / compose input in Electron and Chromium apps on Wayland

`electron-chromium-ime-no-wayland-text-input` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Fcitx5 works fine in kitty, Firefox and native Wayland apps, but in Chromium, VS Code, Discord, Obsidian or Spotify pressing Ctrl+Space does nothing, no candidate window ever appears, and you cannot type a single Chinese, Japanese or Korean character. Dead keys and the Compose key are dead in the same apps. `fcitx5-diagnose` reports no problems. This is now mostly a symptom of old builds: Chromium 135 and earlier, and apps bundling Electron 35 or earlier. Chromium 136 and later, which is what Omarchy 4 ships today, speak `text-input-v3` by default and do not need any flag.

**Cause.** Wayland IME goes through the `text-input` protocol, and which version a Chromium client speaks depends on its milestone. Chromium 136 and later enable the `WaylandTextInputV3` feature by default: `ui/base/ui_base_features.cc` declares it `FEATURE_ENABLED_BY_DEFAULT`, and `ui/ozone/platform/wayland/host/wayland_input_method_context.cc` turns the Wayland IME path on from that feature alone, then binds `zwp_text_input_v3`. On those builds no command-line flag is needed and the protocol is already v3. Chromium 135 and earlier shipped the feature disabled, so the Wayland IME path stayed off unless `--enable-wayland-ime` was passed, and it then bound `text-input-v1`, which most compositors and toolkits do not pair with. Electron follows its bundled Chromium: Electron 35 carries Chromium 134 and has the old behaviour, Electron 36 carries Chromium 136 and has the new one.

So on Omarchy 4 with the current `chromium` package, a missing candidate window is usually NOT a text-input version problem any more. The remaining causes are an app bundling Electron 35 or older, a build launched under XWayland where `text-input` does not apply at all and the legacy XIM path is used instead, or fcitx5 not running. The ArchWiki Fcitx5 and Chromium pages still state that Chromium defaults to `text-input-v1`, which was true through Chromium 135 and is no longer true.

> **Audit corrected this record.** The record is a faithful copy of a stale ArchWiki note and its central claim is false on the Chromium this machine runs. Checked in Chromium's own source at the exact branch of the installed build (chromium 151.0.7922.173-1, branch-heads/7922): ui/base/ui_base_features.cc declares `BASE_FEATURE(kWaylandTextInputV3, base::FEATURE_ENABLED_BY_DEFAULT)`, and ui/ozone/platform/wayland/host/wayland_input_method_context.cc `IsImeEnabled()` returns true on that feature alone, so `--enable-wayland-ime` is NOT required. The same file picks text-input-v1 only when `--enable-wayland-ime` AND `--wayland-text-input-version=1` are both passed, otherwise it calls `EnsureTextInputV3()`. So Chromium defaults to v3, not v1. I bisected the flip across branch-heads: 6998 (M134) and 6834 are FEATURE_DISABLED_BY_DEFAULT, 7103 (M136) and every branch after it are enabled. Milestone to branch mapping confirmed from chromiumdash fetch_milestones (134 -> 6998, 136 -> 7103, 151 -> 7922). Electron inherits this: releases.electronjs.org/releases.json gives electron 35 -> chromium 134.0.6998.x (still v1) and electron 36 -> chromium 136.0.7103.x (v3 by default). The ArchWiki Fcitx5 and Chromium pages still carry the old text, refetched today, so the cited sources do say what the record claims and none are removed. All four flags still exist in the installed binary (`strings /usr/lib/chromium/chromium` matches enable-wayland-ime, wayland-text-input-version, disable-gtk-ime, gtk-version), and the `~/.config/chromium-flags.conf` mechanism is real: the launcher binary's help text names chromium-flags.conf under /etc and $XDG_CONFIG_HOME. Four Omarchy 4 specifics the record misses. (1) Omarchy already ships the IM module variables in /usr/lib/environment.d/10-omarchy-fcitx.conf, owned by omarchy-settings 4.0.2-1, setting INPUT_METHOD, QT_IM_MODULE, XMODIFIERS and SDL_IM_MODULE to fcitx. `systemctl --user show-environment` on this machine shows QT_IM_MODULE=fcitx, XMODIFIERS=@im=fcitx, SDL_IM_MODULE=fcitx live. (2) GTK_IM_MODULE is deliberately absent from that file, and ArchWiki Fcitx5 says IM modules should be used only for Xwayland apps, so the record's instruction to export GTK_IM_MODULE=fcitx session wide pushes native GTK Wayland apps off the text-input path they already use. (3) Omarchy runs fcitx5 itself as /usr/lib/systemd/user/omarchy-fcitx5.service (active on this machine, PID 2541), and `hyprctl -j devices` shows `hl-virtual-keyboard-fcitx5` with `main: true`, so a reader here would find fcitx5 already attached and the record's `pgrep -a fcitx5` step passing while telling them nothing. (4) Omarchy actively manages ~/.config/chromium-flags.conf. /usr/share/omarchy/config/chromium-flags.conf is the template and migrations 1784508556.sh, 1780517689.sh and 1785543725.sh append --password-store=gnome-libsecret and --load-extension lines to it. The record's code fence reads as 'write this file' and the per-app loop uses `>` which truncates, which on this workstation would have destroyed a live ~/.config/spotify-flags.conf carrying a scale fix. The fix now says append. Also corrected: `electron38-flags.conf` names a package that is no longer in the repos, extra ships electron, electron39, electron40, electron41, electron42 and electron43 as of today, and ArchWiki Electron records that --ozone-platform-hint=wayland was removed in Electron 38. Hyprland 0.56.2 implements both protocols: upstream src/protocols at tag v0.56.2 contains TextInputV1.cpp, TextInputV3.cpp and InputMethodV2.cpp, and the installed /usr/bin/Hyprland binary contains zwp_text_input_manager_v1 and zwp_text_input_manager_v3. hyprctl has no command to list Wayland globals, only `devices` and `globalshortcuts`, so it cannot show which text-input version a client bound. NOT exercised: I did not launch Chromium or any Electron app, did not type a CJK character, did not write any flags file, and did not read chrome://version. Every behavioural claim above comes from source at the installed version or from a local file, not from a run.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not truncate `~/.config/chromium-flags.conf` on Omarchy 4. Omarchy seeds and then appends to that file through its migrations, and two of the lines it puts there matter: `--password-store=gnome-libsecret` pins the cookie and password encryption key, so losing it makes existing cookies and saved logins undecryptable and signs you out of everything, and a `--load-extension` list carries Omarchy's own browser extensions. Append with `>>`. The same applies to any per-application flags file you may already have. Pick one Chromium IME workaround and test it before adding another: `--enable-wayland-ime`, `--gtk-version=4` and `--disable-gtk-ime` are listed on the ArchWiki Chromium page as alternatives for the same class of problem, not as a set to combine.

**Fix.**

First find out whether you actually have a version problem.

**On Omarchy 4** fcitx5 is already installed, already started, and its environment variables are already set by the distribution. Check the service rather than hunting for a stray process:

```bash
systemctl --user status omarchy-fcitx5
cat /usr/lib/environment.d/10-omarchy-fcitx.conf
hyprctl -j devices | grep -i fcitx
```

A healthy Omarchy 4 session shows the unit `active (running)` and an `hl-virtual-keyboard-fcitx5` entry under `keyboards`. On plain Arch, start fcitx5 yourself and see the existing `fcitx5-cjk-input-not-working-wayland` record for the daemon and environment side.

Now check the Chromium version, because that decides whether any flag is needed:

```bash
pacman -Q chromium
```

**Chromium 136 or newer, or Electron 36 or newer, needs no flags.** Those builds enable the `WaylandTextInputV3` feature by default and bind `zwp_text_input_v3` on their own. Hyprland 0.56.2 implements `text-input-v1`, `text-input-v3` and `input-method-v2`, so the pair matches. If the candidate window still does not appear on such a build, the cause is elsewhere: the app is running under XWayland, or fcitx5 has no input method configured.

Find out which Electron an app bundles before deciding:

```bash
pacman -Qi <package> | grep -i depends     # names electron39, electron40, ...
```

Arch currently ships `electron`, `electron39`, `electron40`, `electron41`, `electron42` and `electron43` in `extra`. All of them are past Electron 36.

**Chromium 135 or older, or Electron 35 or older**, needs the flags. Arch's `chromium` reads one flag per line from `~/.config/chromium-flags.conf`.

> On Omarchy 4 that file is not yours alone. Omarchy seeds it from `/usr/share/omarchy/config/chromium-flags.conf` and its migrations append lines to it, including `--password-store=gnome-libsecret` and a `--load-extension` list. Overwriting it logs you out of every site whose cookies were sealed with the gnome-libsecret key and removes Omarchy's browser extensions. **Append, never truncate.**

```bash
printf -- '--enable-wayland-ime\n--wayland-text-input-version=3\n' >> ~/.config/chromium-flags.conf
```

Arch's `electron` package reads the same style of file, preferring the versioned name and falling back to the unversioned one:

```bash
printf -- '--enable-wayland-ime\n--wayland-text-input-version=3\n' >> ~/.config/electron-flags.conf
```

Some apps read a per-application file named after the binary. Append to those too, and check first, because you may already have one:

```bash
for a in vesktop spotify code obsidian; do
  [ -f ~/.config/$a-flags.conf ] && cat ~/.config/$a-flags.conf
  printf -- '--enable-wayland-ime\n--wayland-text-input-version=3\n' >> ~/.config/$a-flags.conf
done
```

Apps that bundle their own Electron, such as `discord` and `slack-desktop`, ignore all of the above. Patch their desktop entry instead:

```bash
cp /usr/share/applications/discord.desktop ~/.local/share/applications/
sed -i 's|^Exec=/usr/bin/discord|Exec=/usr/bin/discord --enable-wayland-ime --wayland-text-input-version=3|' \
  ~/.local/share/applications/discord.desktop
update-desktop-database ~/.local/share/applications
```

Fully quit the app and start it again from the launcher. Do not use an in-app relaunch button, because Chromium relaunches on the old platform.

If an app is running under XWayland it needs the legacy XIM path instead, not `text-input`. **On Omarchy 4 this is already done**: `XMODIFIERS=@im=fcitx`, `QT_IM_MODULE=fcitx`, `SDL_IM_MODULE=fcitx` and `INPUT_METHOD=fcitx` come from `/usr/lib/environment.d/10-omarchy-fcitx.conf`, shipped by `omarchy-settings`. Confirm rather than re-adding them:

```bash
systemctl --user show-environment | grep -E 'IM_MODULE|XMODIFIERS'
```

Do not add `GTK_IM_MODULE=fcitx`. Omarchy leaves it unset on purpose, and the ArchWiki Fcitx5 page recommends IM modules only for Xwayland applications, because setting it pushes native GTK Wayland apps off the `text-input` path they already use.

**On plain Arch with a uwsm session**, put the Xwayland variables in a uwsm drop-in rather than in `hyprland.lua`:

```sh
# ~/.config/uwsm/env.d/im.conf
export XMODIFIERS=@im=fcitx
export QT_IM_MODULE=fcitx
```

On Omarchy 4 the equivalent user override point is a drop-in read by the systemd user manager:

```conf
# ~/.config/environment.d/im.conf
QT_IM_MODULE=fcitx
```

Log out and back in either way.

**Verify.** Open the app, press Ctrl+Space, and check the fcitx5 candidate window appears over the app window. `hyprctl clients | grep -A6 <class>` should show `xwayland: 0` for a native Wayland Electron app, because an app on XWayland cannot use `text-input` at all and needs the XIM path instead. If you added flags, confirm they were read: launch the app from a terminal and check `chrome://version` shows them on the command line. On Chromium 136 or newer with no flags set, a working candidate window is the expected result and the absence of the flags on that command line is correct.

Sources: <https://wiki.archlinux.org/title/Chromium> · <https://wiki.archlinux.org/title/Fcitx5> · <https://wiki.archlinux.org/title/Electron> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/> · <https://chromium.googlesource.com/chromium/src/+/refs/branch-heads/7922/ui/base/ui_base_features.cc> · <https://chromium.googlesource.com/chromium/src/+/refs/branch-heads/7922/ui/ozone/platform/wayland/host/wayland_input_method_context.cc> · <https://chromium.googlesource.com/chromium/src/+/refs/branch-heads/7103/ui/base/ui_base_features.cc> · <https://chromium.googlesource.com/chromium/src/+/refs/branch-heads/6998/ui/base/ui_base_features.cc> · <https://chromiumdash.appspot.com/fetch_milestones> · <https://releases.electronjs.org/releases.json> · <https://github.com/hyprwm/Hyprland/tree/v0.56.2/src/protocols> · <https://archlinux.org/packages/search/json/?q=electron>

---

## Fix a Java app opening as a blank grey box that never draws

`java-gray-window-nonreparenting` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`, `xwayland`

**Symptom.** A Java/Swing application opens as a plain gray box with no UI drawn at all, or its menus flash open and close immediately on click, or the window refuses to redraw when the tiling WM resizes it.

**Cause.** AWT has a hardcoded list of "non-reparenting" window managers. Hyprland (and most tiling WMs) are not on that list, so AWT picks the wrong reparenting behaviour and never paints. This is separate from the scaling problem — the window is blank, not merely too big.

> **Audit corrected this record.** The primary fix is right and well-sourced — the Arch Java wiki describes the AWT hardcoded non-reparenting WM list, the gray-blob symptom and the menus-close-immediately symptom, and prescribes _JAVA_AWT_WM_NONREPARENTING=1. The -Dsun.awt.disablegrab=true JavaFX debugging freeze is also on that page. The defect is the AWT_TOOLKIT=MToolkit fallback: MToolkit (the Motif AWT toolkit) was removed from OpenJDK back in JDK 7, so on any JDK a user will actually be running the variable is inert. The wiki still carries the line as legacy text, and the record additionally inverts its wording — the wiki says 'for later versions', the record says 'on older JDKs'. Presenting dead advice as a step to try wastes the user's time on a real, fixable problem.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Set the non-reparenting hint before launching. For a single app:

```bash
_JAVA_AWT_WM_NONREPARENTING=1 ghidraRun
```

Session-wide.

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/envs.lua`, or the bottom of `~/.config/hypr/hyprland.lua`):

```lua
hl.env("_JAVA_AWT_WM_NONREPARENTING", "1")
```

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/hyprland.conf`):

```conf
env = _JAVA_AWT_WM_NONREPARENTING,1
```

Do NOT bother with `AWT_TOOLKIT=MToolkit`. The Arch wiki still lists it, but the Motif AWT toolkit was removed from OpenJDK in JDK 7 — on any JDK you can actually install today the variable is silently ignored.

If the hint alone is not enough, impersonate a WM that IS on AWT's list, which is the other approach the Arch Java page documents:

```bash
sudo pacman -S --needed wmname
wmname LG3D
```

Run that once per session (before launching the Java app) — it only affects XWayland clients.

If a JavaFX app freezes the whole session while debugging, add:

```bash
java -Dsun.awt.disablegrab=true -jar app.jar
```

**Verify.** The application window renders its actual UI instead of a gray rectangle, and menus stay open when clicked.

Sources: <https://wiki.archlinux.org/title/Java>

---

## Fix an empty Outputs tab in the screen-share picker

`share-picker-outputs-tab-empty` · severity: **high** · frequency: **occasional** · applies to: `amd`, `desktop`, `hyprland`, `intel`, `laptop`, `omarchy`, `wayland`

**Symptom.** The screen-share picker opens but the "Outputs"/"Screens" tab is completely empty — you can only pick individual windows. Picking "Region" records a black screen. Running the picker by hand prints only `(hyprland-preview-share-picker:269939): Gtk-CRITICAL **: gtk_flow_box_set_max_children_per_line: assertion 'n_children > 0' failed`.

**Cause.** Two distinct causes seen in the wild. (1) On Omarchy, `custom_picker_binary = hyprland-preview-share-picker` in `~/.config/hypr/xdph.conf` replaces the stock Qt picker with a GTK preview picker that can fail to render output thumbnails on some GPUs — the outputs are actually there but invisible. (2) Multi-monitor setups where the picker renders outputs off-screen; the entries exist but are not shown.

**Fix.**

First, try navigating blind — the entries are often present but not painted. Focus the Outputs tab and press the arrow keys, then Enter.

If that fails, capture a debug log to confirm outputs are being enumerated:

```bash
hyprland-preview-share-picker --debug --logs /tmp/picker.log
grep -i output /tmp/picker.log
```

A line like `transmitted image for output eDP-2` means the output is there and only the rendering is broken.

Fall back to the stock Qt picker by commenting out the custom binary in `~/.config/hypr/xdph.conf`:

```conf
screencopy {
    allow_token_by_default = true
    # custom_picker_binary = hyprland-preview-share-picker
}
```

Then:

```bash
systemctl --user restart xdg-desktop-portal-hyprland.service
```

The stock `hyprland-share-picker` lists outputs as plain text rows and works where the preview picker does not.

**Verify.** Re-open the share dialog; the Outputs tab lists your monitors by connector name (eDP-1, DP-3, HDMI-A-1) and selecting one produces live video rather than black.

Sources: <https://github.com/basecamp/omarchy/issues/4097> · <https://github.com/basecamp/omarchy/issues/6040> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/>

---

## Fix a black desktop with only a cursor in a VMware guest, where omarchy-shell cannot attach its buffers

`vmware-shell-black-desktop-qt-quick-dmabuf` · severity: **high** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`, `omarchy-shell`, `quickshell`, `vmware`, `vmwgfx`, `wayland`, `xwayland`

**Symptom.** Omarchy 4.0.x installs cleanly as a VMware guest and then boots to a uniform dark screen with only the mouse cursor. There is no bar and no wallpaper, and `Super + Space` does nothing, but Hyprland itself is running, so `Super + Enter` opens a terminal and applications launch.

`omarchy-launch-shell` relaunches the shell five times in under a minute and then logs `Giving up on the Omarchy shell`. Running the shell by hand with `WAYLAND_DEBUG=1` shows the fatal protocol error:

```
[Default Queue] -> zwp_linux_buffer_params_v1#34.create_immed(new id wl_buffer#46, 1718, 52, 875713089, 0)
[Default Queue] -> wl_surface#42.attach(wl_buffer#46, 0, 0)
[Display Queue] wl_display#1.error(wl_display#1, 1, "invalid arguments for wl_surface#42.attach")
WARN: The Wayland connection experienced a fatal error: Invalid argument
```

Hyprland logs `unknown object (61), message attach(?oii)` and `error in client communication`. Other GPU-rendered clients hit the same error, including `mpv --vo=gpu`, a plain GTK4 window and Ghostty, and XWayland dies when an X11 application such as Spotify starts. `foot`, `imv` and Chromium were reported fine on hardware GL by one reporter, so which clients survive varies between guests.

**This is the 3D-accelerated case.** Reported on Omarchy 4.0.0 through 4.0.2 with Hyprland 0.56.2, aquamarine 0.14.0, Mesa 26.1.7 and 26.2.1 and `vmwgfx` 2.21.0 on VMware SVGA II `15ad:0405`, with Windows 10, Windows 11 and Ubuntu hosts, in every case with VMware's `Accelerate 3D Graphics` enabled. With that setting off the guest fails differently: Hyprland cannot initialise its renderer at all and the display is blank, which is a separate problem and this fix does not address it.

**Cause.** Established by reporters across four threads and by one independent before-and-after measurement. No maintainer has given a verdict on any of them.

`vmwgfx` prime-imports a surface-backed dmabuf as a TTM surface handle rather than an ordinary GEM handle, because `vmw_prime_fd_to_handle` tries `ttm_prime_fd_to_handle` first and only falls back to `drm_gem_prime_fd_to_handle`. Hyprland's `CLinuxDMABUFParamsResource::commence()` in `src/protocols/LinuxDMABUF.cpp` then calls `drmCloseBufferHandle()`, which is GEM_CLOSE. That returns `EINVAL` because the handle is not in the GEM table, and Hyprland treats the whole import as failed. It answers `zwp_linux_buffer_params_v1.failed`, so the `wl_buffer` is never created, and the client's following `wl_surface.attach` names an object the compositor does not know. That is a fatal protocol error and the client is killed.

The format and the modifier are not the problem. One reporter wrote small GBM and EGL programs that import the exact buffer the client offers, 1920x1080 `XR24` at stride 7680 with modifier `0` (`LINEAR`), and every combination succeeded, including import on a second device fd. Mesa's `svga` driver does advertise zero dma-buf render modifiers for the scanout formats while `vmwgfx` KMS advertises only `LINEAR`, but the compositor still advertises 116 format and modifier pairs through `zwp_linux_dmabuf_v1` feedback and then fails the one the client picks out of its own tranche.

Qt leaves through `_exit()` on a fatal Wayland error and raises no signal, so Quickshell's crash handler never runs and `omarchy-launch-shell` sees a bare exit. omarchy-shell is a Quickshell client, which is why the bar, wallpaper and menus never appear while the compositor and shm-backed clients carry on. The compositor itself is not affected: aquamarine survives the missing modifiers with `GBM: Allocating with modifiers failed, falling back to implicit` and keeps scanning out. A minimal `qml6` window reproduces the same error with no Omarchy involved, which places the fault in the compositor's dmabuf import path rather than in Omarchy.

The upstream threads are `hyprwm/Hyprland` discussion 12966 (a discussion, not an issue, so the `/issues/12966` URL 404s) and `hyprwm/aquamarine` issue 360, which is still open with no maintainer reply. A userspace patch that falls back to `DRM_VMW_UNREF_SURFACE` when GEM_CLOSE fails was posted in discussion 12966 and has since been rebuilt and confirmed by two further reporters, one of whom measured dmabuf errors dropping from about 31,545 per minute to zero and found `LIBGL_ALWAYS_SOFTWARE=1` no longer needed. It was re-filed as `hyprwm/Hyprland` issue 16175 on 2026-09-07 and a bot closed it as not planned fifteen seconds later, because Hyprland no longer accepts user-filed issues. Nothing has landed in Hyprland or aquamarine as of 2026-09-11, so an environment variable is still the only fix that does not require building a patched package.

`omacom/omarchy` issue 7918 is the same GEM close failure reached through the DRM cursor plane. It reports `legacy drm: drmCloseBufferHandle in cursor failed` and an invisible pointer, and is fixed separately with `cursor { no_hardware_cursors = true }`.

> **Audit corrected this record.** This machine is an Omarchy 4.0.2-1 workstation on bare metal and is NOT a VMware guest, so nothing in this record could be exercised. Every claim about the failure and about the workaround rests on reporter testimony in the cited threads, which I read in full today, and the record is right to say so.

Confirmed on this machine: Omarchy sets no `QT_QUICK_BACKEND` and no `QSG_RHI_BACKEND` anywhere under `/usr/share/omarchy` (grep returns nothing for both), and it does set `QT_QPA_PLATFORM` and `QT_QPA_PLATFORMTHEME` at `/usr/share/omarchy/default/hypr/envs.lua:13` and `:14`. The load order holds: `require("default.hypr.omarchy")` is line 14 of both `~/.config/hypr/hyprland.lua` and the stock `/usr/share/omarchy/config/hypr/hyprland.lua`, the bootstrap `dofile` is line 4, and `/usr/share/omarchy/default/hypr/omarchy.lua:16` pulls in `default.hypr.envs`, so a later `hl.env` runs after Omarchy's. The override semantics come from Hyprland v0.56.2 source, `src/config/lua/bindings/LuaBindingsConfigRules.cpp:508`, which is `setenv(name.c_str(), value.c_str(), 1)`, so last write wins. Also confirmed locally: `nano` is not installed and `neovim 0.12.5-1` is, `omarchy-launch-shell` logs the exact string `exited with status` and gives up after five relaunches in under a minute, and `omarchy-restart-shell` respawns through `hyprctl dispatch 'hl.dsp.exec_cmd("omarchy-launch-shell")'`.

Confirmed from source, not from the thread: `QSG_RHI_BACKEND` accepts only `gl`, `gles2`, `opengl`, `d3d11`, `d3d`, `d3d12`, `vulkan`, `metal` and `null`, and anything else emits `Unknown key "%s" for QSG_RHI_BACKEND, falling back to default backend.` This is qtdeclarative 6.11 `src/quick/scenegraph/qsgrhisupport.cpp` lines 77 to 97, and the local `qt6-declarative` is 6.11.2-1. `QT_QUICK_BACKEND=software` is the documented way to request the Software adaptation on the Qt docs page the record already cites. The `LIBGL_ALWAYS_SOFTWARE=1` characterisation holds as a reporter measurement in `omacom/omarchy#8113`: a table gives llvmpipe compositing at about 12% Hyprland idle CPU against about 4% with the Qt-only switch, and a second reporter on a fresh 4.0.2 install got no shell with it.

Four defects, which is why this is `corrected`. First, the cited URL `https://github.com/hyprwm/Hyprland/issues/12966` does not exist and returns 404. 12966 is a DISCUSSION, "Kitty and alacritty cannot launch in vmware workstation pro, 3d accel is enabled", opened 2026-01-11 in the Bugs - DRM category with 3 comments and no accepted answer. The verdict can only append sources, so that dead URL has to be deleted from the record's `sources` by hand before ingest.

Second, the cause's mechanism was wrong. The record blames a modifier Hyprland rejects. The mechanism established across discussion 12966, `omacom/omarchy#8113` and `hyprwm/aquamarine#360` is that `vmwgfx` prime-imports surface-backed dmabufs as TTM surface handles, so Hyprland's `drmCloseBufferHandle()` (GEM_CLOSE) in `CLinuxDMABUFParamsResource::commence()` fails with `EINVAL`, the import is marked failed, `zwp_linux_buffer_params_v1.failed` is sent and the never-created `wl_buffer` makes the following `attach` fatal. The reporter on `aquamarine#360` imported the exact buffer, `XR24` 1920x1080 stride 7680 modifier `LINEAR`, through GBM and EGL in standalone programs and every combination succeeded, which rules the modifier out directly. The zero-render-modifiers finding is real but it explains why aquamarine falls back, not why the client is killed.

Third, "nobody else confirmed" the `DRM_VMW_UNREF_SURFACE` patch is false. It was posted by Pascal-0x90 in discussion 12966 with a kernel-level analysis, independently rebuilt and validated by carlpe on `aquamarine#360` (errors from about 31,545 per minute to zero, `LIBGL_ALWAYS_SOFTWARE=1` no longer needed), and rebuilt again by dsuarezv in `omacom/omarchy#8113`. What is true is that no maintainer has acted: `aquamarine#360` is open with no maintainer reply, and the re-filed `hyprwm/Hyprland#16175` (2026-09-07) was closed as `not_planned` fifteen seconds after opening by the bot that tells users to open a discussion instead. So no compositor-side fix has landed as of 2026-09-11.

Fourth, the symptom said the crash-loop was reported "both with and without VMware's `Accelerate 3D Graphics` enabled". The sources say the opposite: every dmabuf report had it enabled, and with it off Hyprland cannot initialise a renderer at all, which is a different blank-screen failure. Mesa was reported as both 26.1.7 and 26.2.1, not only 26.2.1.

Also corrected, and confirmed on this machine: the verify block told the reader to find the shell in `hyprctl clients -j`. It is never there. `hyprctl clients` here lists only `foot`, while `hyprctl layers` lists `omarchy-bar` and `omarchy-background`, because the shell draws layer-shell surfaces. And the fix's explanation for needing a logout was wrong: `hyprctl reload` does re-run `hl.env` and does `setenv` in the compositor, so the reason a reload is not enough is that the shell supervisor has already given up, which `omarchy-restart-shell` fixes without a logout.

Two further corrections kept small: the VMware `Accelerate 3D Graphics` paragraph now says the setting is required rather than "a setting to check", and the fix now names the upstream patch and says plainly that taking it means maintaining a package `omarchy update` will replace. Confidence is medium, not high, because the whole record is reporter testimony with no maintainer verdict, the guest side could not be exercised here, and `omacom/omarchy#7835` and `#8113` are both still open with no Omarchy-side fix. One reporter note deliberately not carried over: mktpostal in `#7835` refers to "Omarchy 4.1", which does not exist (newest tag is v4.0.3, 2026-09-08).
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Run Quickshell's Qt Quick scene graph on the software rasterizer, so its surface is an shm buffer and no dmabuf is created. The compositor stays on the GPU. Two reporters confirmed this on 4.0.2 and two more on earlier releases.

If you cannot reach a terminal, log in and press `Ctrl+Alt+F2` for a TTY. `nano` is not installed on Omarchy 4, confirmed on 4.0.2-1, so use `nvim`.

Add the line to `~/.config/hypr/hyprland.lua`, below the `require("default.hypr.omarchy")` line, which is line 14 of the stock file:

```lua
-- VMware: avoid Qt Quick dmabuf attachments vmwgfx cannot satisfy.
hl.env("QT_QUICK_BACKEND", "software")
```

Omarchy sets no `QT_QUICK_BACKEND` and no `QSG_RHI_BACKEND` of its own, confirmed on 4.0.2-1 by grepping `/usr/share/omarchy`, so anywhere after the bootstrap `dofile` on line 4 works for this variable. Below the `require` is the habit to keep, because `hl.env` calls `setenv()` with overwrite enabled, so for a variable Omarchy does set in `/usr/share/omarchy/default/hypr/envs.lua`, such as `QT_QPA_PLATFORM` or `GDK_BACKEND`, only a line after `require("default.hypr.omarchy")` wins.

Then log out and back in, which is the simplest way to get every client restarted with the new variable. A `hyprctl reload` does re-run `hl.env`, so clients started after it do inherit the setting, but the shell supervisor has already given up by then, so follow the reload with:

```bash
omarchy-restart-shell
```

That respawns the shell through `hyprctl dispatch 'hl.dsp.exec_cmd("omarchy-launch-shell")'`, so it inherits the compositor's environment rather than your terminal's. One reporter saw the desktop come up after a bare `hyprctl reload`.

If XWayland applications still kill XWayland, one reporter added this as well and tested the two together:

```lua
hl.env("XWAYLAND_NO_GLAMOR", "1")
```

That makes X11 applications render in software, and the same reporter measured Spotify at about 60% of a core with it. The same reporter also found that neither variable fixes the SDDM greeter, because SDDM runs its own Hyprland with its own environment, so logging out can still leave no visible login screen.

Three alternatives do not work, and two of them look like they should. `QSG_RHI_BACKEND=software` changes nothing, because `software` is not a value that variable accepts: Qt's `qsgrhisupport.cpp` takes only `gl`, `gles2`, `opengl`, `d3d11`, `d3d`, `d3d12`, `vulkan`, `metal` and `null`, and anything else logs `Unknown key "software" for QSG_RHI_BACKEND, falling back to default backend.` and leaves the GPU path in place. `QT_WAYLAND_DISABLE_HARDWARE_INTEGRATION=1` does not help either. `LIBGL_ALWAYS_SOFTWARE=1` does stop the crash, but it forces the whole session including the compositor onto llvmpipe, measured at about 12% idle CPU for Hyprland against 4% with the Qt-only switch, and one reporter on a fresh 4.0.2 install got no shell with it at all.

`Accelerate 3D Graphics` in VM Settings, Display, has to be on. Every crash-loop report came from a guest that had it enabled, and with it off Hyprland cannot bring up a renderer at all, so turning it off is not an alternative workaround.

The real fix is upstream and has not landed. A patch to `src/protocols/LinuxDMABUF.cpp` that falls back to `DRM_VMW_UNREF_SURFACE` when `drmCloseBufferHandle()` fails on a vmwgfx device is in `hyprwm/Hyprland` discussion 12966, and three reporters have built it against Hyprland 0.56.2 and found the whole family of failures gone with full GPU acceleration. Building it means maintaining a patched `hyprland` package that a normal `omarchy update` will replace, so the environment variable is the right answer until it is merged.

**Plain Arch:** the variable is the same for any Qt Quick client on `vmwgfx`. Set `QT_QUICK_BACKEND=software` in the environment of whatever launches the Qt application.

**Verify.** After a fresh login the bar, wallpaper and `Super + Space` menu appear and the shell stays up:

```bash
journalctl -b -t omarchy-shell | grep -c 'exited with status'     # 0 relaunches
hyprctl layers -j | jq -r '..|.namespace? // empty' | sort -u     # omarchy-bar, omarchy-background
cat /proc/$(pgrep -o quickshell)/environ | tr '\0' '\n' | grep QT_QUICK_BACKEND
```

The shell draws layer surfaces, not toplevel windows, so it never appears in `hyprctl clients`. Confirmed on Omarchy 4.0.2-1: `hyprctl layers` reports the namespaces `omarchy-bar` and `omarchy-background`.

The last command prints `QT_QUICK_BACKEND=software`. The journal shows `Disabling glamor and dri3 support, XWAYLAND_NO_GLAMOR is set` if that variable was added.

Sources: <https://github.com/omacom/omarchy/issues/7835> · <https://github.com/omacom/omarchy/issues/8113> · <https://github.com/omacom/omarchy/issues/7918> · <https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations.html> · <https://github.com/hyprwm/Hyprland/discussions/12966> · <https://github.com/hyprwm/Hyprland/issues/16175> · <https://github.com/hyprwm/aquamarine/issues/360> · <https://github.com/qt/qtdeclarative/blob/6.11/src/quick/scenegraph/qsgrhisupport.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsConfigRules.cpp>

---

## Move Chrome's screen-sharing bar off the centre of the display

`chrome-sharing-indicator-stuck-center-screen` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** While screen sharing from Chromium/Chrome (Google Meet especially), a small window titled `<site> is sharing your screen.` parks itself dead centre of the display and will not move. Clicking its "Hide" button does nothing. Ctrl+W on it stops the share entirely.

**Cause.** Chromium spawns the sharing indicator as its own toplevel with no position hint. Hyprland floats it and centres it; the "Hide" button is broken in Chromium's own Wayland path, so nothing dismisses it. Positioning has to be forced by the compositor.

> **Audit corrected this record.** Real problem, real source (omarchy#1862), and the hyprlang rule is quoted faithfully from that thread — but it faithfully reproduces the thread's bug. `move 100%-w-20 100%-w-20` uses the WINDOW WIDTH token for the Y coordinate; the vertical term must use the height token. The commenter who posted it claims it lands 20px from the right and bottom, and a later commenter in the same thread reports it still does not work. Separately, the Lua rule uses `no_border = true`, which is not a valid effect in the 0.55+ window-rule schema (the effects table has `border_size` and `decorate`, and no `no_border`) — an unknown key, not a working rule. And as with the xwaylandvideobridge record, `~/.config/hypr/windows.lua` is not a file Omarchy 4.x loads.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not edit `~/.local/share/omarchy/default/hypr/apps/browser.conf` or `/usr/share/omarchy/default/hypr/*` directly — `omarchy update` overwrites those files and your rule disappears. Put the rule in your own `~/.config/hypr/` files.

**Fix.**

Move it out of the way with a Hyprland window rule matched on its title.

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/hyprland.conf`, or a user override file — not the packaged defaults). Note the Y term uses the HEIGHT token; the widely-copied version from omarchy#1862 uses `100%-w-20` twice, which computes the vertical position from the window's width and parks it in the wrong place:

```conf
# Screen sharing indicator (Google Meet, etc)
windowrule = tag +screen-share-indicator, initialTitle:^.*is sharing your screen\.$
windowrule = noborder, tag:screen-share-indicator
windowrule = move 100%-w-20 100%-h-20, tag:screen-share-indicator
```

Hyprland 0.55+ / Omarchy 4.x — Omarchy has no `windows.lua`, so append to the bottom of `~/.config/hypr/hyprland.lua` (or create `~/.config/hypr/windows.lua` and add `require("hypr.windows")` to `hyprland.lua`):

```lua
hl.window_rule({
    name = "hide-screen-sharing-indicator",
    match = { title = ".*is sharing your screen.*" },
    workspace = "special:hidden",
    border_size = 0
})
```

(`no_border` is not a valid effect in the 0.55+ schema — use `border_size = 0`, or `decorate = false`.)

Or, to park it in a corner instead of hiding it:

```lua
hl.window_rule({
    name = "move-screen-sharing-indicator",
    match = { title = ".*is sharing your screen.*" },
    float = true,
    move = {"monitor_w - window_w - 20", "monitor_h - window_h - 20"},
    border_size = 0
})
```

Then:

```bash
hyprctl reload
```

If your desktop is not in English, change the title regex to match your locale's wording. Immediate manual workaround with no config change: hold SUPER and drag the window with the left mouse button, or SUPER + right-drag to resize it away.

**Verify.** Start a Google Meet share. The indicator appears in the bottom-right corner (or on the hidden workspace) instead of centre screen, and the meeting keeps sharing.

Sources: <https://github.com/basecamp/omarchy/issues/1862> · <https://wiki.hypr.land/0.54.0/FAQ/>

---

## Chromium and Electron apps ask to unlock the keyring on every launch, or lose all saved passwords

`chromium-electron-keyring-password-prompt-every-launch` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Every time I start Chromium, Slack, Signal or Element a dialog appears asking "Enter password to unlock your login keyring". If I dismiss it, all my saved logins and sessions are gone. Starting the app from a terminal prints `Failed to decrypt token for service AccountId-*`.

**Cause.** Chromium (and every Electron app, which uses the same `safeStorage`/Secret Service code) auto-detects which password store to use. With no desktop environment it guesses, and the guess changes as packages come and go — so the key that encrypted your cookies with one backend cannot be read back with another. Separately, on a bare Hyprland session gnome-keyring is often never unlocked: `pam_gnome_keyring.so` is not in the PAM stack, or `gnome-keyring-daemon --login` started by PAM died because it was never handed the session D-Bus environment, so the daemon has no unlocked `login` keyring to serve.

> **Audit corrected this record.** Real, very common problem, and the Chromium half is impeccable — but the PAM half sends an Omarchy reader to the wrong file on a wrong premise, and the verify command does not work. (a) The fix says "If you log in through a display manager (SDDM, GDM, LightDM, LXDM) this is already configured" (a faithful copy of ArchWiki GNOME/Keyring) and then walks the reader through /etc/pam.d/login. On Omarchy 4 both halves are wrong. Omarchy ships SDDM — `sddm` is in /usr/share/omarchy/install/omarchy-base.packages and /etc/sddm.conf.d/ is populated — so /etc/pam.d/login is never consulted; and Arch's sddm PAM stack is only half-configured for gnome-keyring. I read /etc/pam.d/sddm on this box: it has `-session optional pam_gnome_keyring.so auto_start` but **no `auth optional pam_gnome_keyring.so`** line, and `grep -n gnome_keyring /etc/pam.d/*` shows nothing else in the include chain (system-login/system-auth are clean). Without the auth half PAM never captures the login password, so the `login` keyring is started but never unlocked — which is precisely this record's symptom. The record therefore tells the majority of its audience "already configured, skip this" when it is the actual cause. (b) SDDM autologin, which Omarchy supports (/etc/sddm.conf.d/autologin.conf), has both PAM lines in /etc/pam.d/sddm-autologin but no password is ever typed, so the keyring still cannot be unlocked — a second real case the record does not cover. (c) The verify command `pgrep -a gnome-keyring-daemon` does not work: the name is 20 characters and pgrep refuses patterns over 15 ("pattern that searches for process name longer than 15 characters will result in zero matches"). It needs `pgrep -af`. (d) Step 2's hand-start is obsolete and mildly harmful: current gnome-keyring (1:50.0-1) ships gnome-keyring-daemon.socket, enabled by preset and active here, plus /etc/xdg/autostart/gnome-keyring-secrets.desktop which uwsm runs; ArchWiki warns a second start produces "discover_other_daemon: 1". Omarchy's own /usr/share/omarchy/default/hypr/autostart.lua already runs `dbus-update-activation-environment --systemd --all`. (e) Step 2 also names the wrong file for Omarchy: user autostart lives in ~/.config/hypr/autostart.lua, which hyprland.lua requires. What is correct and stays: the ArchWiki /etc/pam.d/login block and the /etc/pam.d/passwd append are verbatim-accurate; `--password-store=gnome-libsecret` is a real, currently documented value (ArchWiki Chromium "Force a password store" lists gnome-libsecret, kwallet5, kwallet6, basic, detect) and the `Failed to decrypt token for service AccountId-*` symptom is quoted verbatim from that same page; ArchWiki Electron documents --password-store for safeStorage; the danger about --password-store=basic writing plaintext into `Login Data` matches the wiki exactly; gnome-keyring, libsecret and seahorse are all in official repos; `busctl --user list | grep secrets` works (shows org.freedesktop.secrets owned by gnome-keyring-d).
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Changing the password store makes everything encrypted under the previous backend permanently unreadable — you are logged out of every site and all saved passwords in that profile are lost. Export what you need first. `--password-store=basic` is a last resort: it writes the cookie encryption key and passwords as plain text into the profile's `Login Data` file, readable by anything running as your user. Editing PAM files incorrectly can lock you out of login entirely — keep a root shell open on another TTY (Ctrl+Alt+F2) while you edit, and test in a second TTY before closing it. Deleting `~/.local/share/keyrings/login.keyring` permanently destroys every stored secret.

**Fix.**

**1. Find out which PAM stack your login actually uses — and check it, do not assume it is fine.**

```bash
systemctl status display-manager --no-pager | head -3
grep -n gnome_keyring /etc/pam.d/*
```

Omarchy 4 logs in through **SDDM**, so `/etc/pam.d/login` is never read. And Arch's `sddm` package ships only half of what gnome-keyring needs — `/etc/pam.d/sddm` has

```
-session    optional    pam_gnome_keyring.so    auto_start
```

but **no `auth` line**, so PAM never captures your login password and the `login` keyring comes up locked. That is the usual reason for a prompt on every launch on Omarchy, and it is why "a display manager configures this for you" is not true here.

Before editing any PAM file, **open a root shell on another TTY (Ctrl+Alt+F2) and leave it open** — a broken PAM stack locks you out of login entirely. Add the missing line after `auth include system-login`:

```
# /etc/pam.d/sddm
auth        include     system-login
-auth       optional    pam_gnome_keyring.so
```

Log out and back in, and confirm on the second TTY that you can still authenticate before you close it.

For a console login with no display manager, the file is `/etc/pam.d/login` and the ArchWiki block is:

```
#%PAM-1.0
auth       required     pam_securetty.so
auth       requisite    pam_nologin.so
auth       include      system-local-login
auth       optional     pam_gnome_keyring.so
account    include      system-local-login
session    include      system-local-login
session    optional     pam_gnome_keyring.so auto_start
```

`greetd` users edit `/etc/pam.d/greetd` instead.

**If you use SDDM autologin** (`/etc/sddm.conf.d/autologin.conf`), no password is ever typed, so PAM has nothing to unlock the keyring with and the missing `auth` line above will not help. Either accept one prompt per boot, or give the **Login** keyring an empty password in `seahorse` — which stores every secret in it **unencrypted on disk, readable by anything running as your user.** Do not do that on a machine anyone else can reach.

**2. Packages.** `gnome-keyring` and `libsecret` are already in Omarchy's base set; `seahorse` is not:

```bash
sudo pacman -S --needed gnome-keyring libsecret seahorse
```

**3. Do not hand-start the daemon — check it instead.** Current `gnome-keyring` ships `gnome-keyring-daemon.socket` (enabled by preset) and `/etc/xdg/autostart/gnome-keyring-secrets.desktop`, which uwsm runs; adding another `gnome-keyring-daemon --start` gives you `discover_other_daemon: 1`.

```bash
systemctl --user status gnome-keyring-daemon.socket
busctl --user list | grep org.freedesktop.secrets
```

The D-Bus activation environment is already handled on Omarchy by `/usr/share/omarchy/default/hypr/autostart.lua`. Only on a bare Hyprland session with no uwsm and no display manager do you need to add it yourself — and the user-owned file is `~/.config/hypr/autostart.lua`, not `hyprland.lua`:

```lua
-- ~/.config/hypr/autostart.lua
hl.on("hyprland.start", function()
  hl.exec_cmd("dbus-update-activation-environment --systemd --all")
end)
```

**4. Stop Chromium guessing which store to use.** Pin the backend explicitly:

```conf
# ~/.config/chromium-flags.conf
--password-store=gnome-libsecret
```

```conf
# ~/.config/electron-flags.conf
--password-store=gnome-libsecret
```

For an app bundling its own Electron (these files are read only by Arch's `electron` package), patch its desktop entry:

```bash
cp /usr/share/applications/slack.desktop ~/.local/share/applications/
sed -i 's|^Exec=\(.*slack\) |Exec=\1 --password-store=gnome-libsecret |' ~/.local/share/applications/slack.desktop
update-desktop-database ~/.local/share/applications
```

**5. If the keyring password no longer matches your login password**, change it in `seahorse`: right-click the **Login** keyring → Change Password → set it to your user password. To make it track your password automatically in future, append to `/etc/pam.d/passwd`:

```
password	optional	pam_gnome_keyring.so
```

**6. Log out completely and back in** — PAM only runs at login. Then verify (note the `-f`; the process name is 20 characters and plain `pgrep -a` refuses to match names longer than 15):

```bash
pgrep -af gnome-keyring-daemon
busctl --user list | grep org.freedesktop.secrets
```

**Verify.** `pgrep -a gnome-keyring-daemon` shows the daemon running with `--components=` including `secrets`. `busctl --user list | grep secrets` shows `org.freedesktop.secrets`. Launch Chromium: no prompt appears and previously saved passwords are listed under `chrome://settings/passwords`. `seahorse` shows the **Login** keyring as unlocked.

Sources: <https://wiki.archlinux.org/title/Chromium> · <https://wiki.archlinux.org/title/GNOME/Keyring> · <https://wiki.archlinux.org/title/Electron>

---

## Keep the clipboard after closing the app you copied from

`clipboard-lost-when-source-app-closes` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** You copy text from a terminal or editor, close that window, then paste — and nothing comes out, or you get the previous clipboard entry. Copying an image from a screenshot tool and closing it loses the image entirely.

**Cause.** By Wayland's design the clipboard is not a system buffer: the copied data lives in the memory of the source client and is only transferred when a paste actually happens. When the source client exits, the offer is withdrawn and the data is gone. This is normal Wayland behaviour, not a Hyprland bug.

> **Audit corrected this record.** The Wayland clipboard-ownership explanation is correct, wl-clip-persist is genuinely in extra (0.5.0), `--clipboard regular` is a real flag, and cliphist + wl-clipboard are both in extra. Two errors. First, the Omarchy 4.x note is factually wrong in a way that matters: default/hypr/bindings/clipboard.lua binds SUPER+V to 'Universal paste' (it synthesises Ctrl+V / Shift+Insert), and the clipboard manager is SUPER+CTRL+V (`omarchy-shell shell toggle omarchy.clipboard`). A user told to press SUPER+V to check for an existing history manager will see a paste happen and draw the wrong conclusion. Second, the cliphist section gives only hyprlang exec-once lines with no 0.55+/Lua equivalent, even though the rest of the record is dual-syntax — and it binds SUPER+V, colliding head-on with Omarchy's universal paste. `fuzzel` is also not installed on Omarchy.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `wl-clip-persist --clipboard primary` is documented as not recommended — persisting the primary selection has unintended side-effects in some GTK applications. Use `--clipboard regular` unless you specifically need middle-click paste to persist.

**Fix.**

Run a persistence daemon that takes ownership of the clipboard the moment something is copied.

Simplest — wl-clip-persist (in `extra`):

```bash
sudo pacman -S --needed wl-clip-persist
```

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/autostart.lua`):

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("wl-clip-persist --clipboard regular")
end)
```

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/hyprland.conf`):

```conf
exec-once = wl-clip-persist --clipboard regular
```

For history as well as persistence, add cliphist:

```bash
sudo pacman -S --needed cliphist wl-clipboard fuzzel
```

Hyprland <=0.54 / Omarchy 3.x:

```conf
exec-once = wl-paste --type text --watch cliphist store
exec-once = wl-paste --type image --watch cliphist store
bind = SUPER SHIFT, V, exec, cliphist list | fuzzel --dmenu --with-nth 2 | cliphist decode | wl-copy
```

Hyprland 0.55+ / Omarchy 4.x:

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("wl-paste --type text --watch cliphist store")
  hl.exec_cmd("wl-paste --type image --watch cliphist store")
end)

hl.bind("SUPER + SHIFT + V", hl.dsp.exec_cmd("cliphist list | fuzzel --dmenu --with-nth 2 | cliphist decode | wl-copy"))
```

Check Omarchy's own clipboard first before adding cliphist, so you do not end up with two managers fighting over the same clipboard. On Omarchy 4.x the paste history lives in the Quickshell shell on **SUPER+CTRL+V** — SUPER+V is 'Universal paste' (it injects Ctrl+V / Shift+Insert) and is NOT the history manager, so do not bind your own manager to SUPER+V or you will break pasting.

**Verify.** ```bash
wl-copy "persistence test" </dev/null
```
Open a terminal, copy some text, close the terminal, then run `wl-paste` in another terminal — the text must still come back.

Sources: <https://wiki.archlinux.org/title/Clipboard> · <https://wiki.archlinux.org/title/Wayland> · <https://wiki.hypr.land/Useful-Utilities/Clipboard-Managers/>

---

## Fix XWayland and Java apps rendering at double size on stock Omarchy

`gdk-scale-mismatch-oversized-xwayland` · severity: **medium** · frequency: **very-common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`, `xwayland`

**Symptom.** On stock Omarchy, XWayland and Java apps render at double size — Steam's whole UI is 2x on a 1080p screen, or a Java IDE's window is wider than the monitor with the right-hand side hanging off the edge and no way to shrink it. Native Wayland apps look correct. `xprop` shows `WM_NORMAL_HINTS` minimum widths that are exactly twice the app's real minimum.

**Cause.** Two Omarchy defaults disagree. The packaged template `/usr/share/omarchy/config/hypr/monitors.lua` is copied to `~/.config/hypr/monitors.lua` at install and hardcodes `local omarchy_gdk_scale = 2` while leaving the monitor scale computed (`local omarchy_monitor_scale = "auto"`). Separately, `/usr/share/omarchy/default/hypr/envs.lua` sets `xwayland = { force_zero_scaling = true }`. With `force_zero_scaling` on, XWayland clients are handed the full physical resolution (1920x1080, say) with no compositor scaling, and are then told by `GDK_SCALE=2` to draw everything at 2x. Java AWT and Swing follow the same path, because Java 9 and later read `GDK_SCALE` for Swing scaling. So X11 and Java windows demand twice the pixels they need, and a tiling compositor will not shift an oversized toplevel left the way Plasma does, so the surplus hangs off the right edge. On a display where auto-scale resolves to 1, `GDK_SCALE=2` is wrong outright and doubles native GTK apps too.

> **Audit corrected this record.** Re-checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1, quickshell 0.3.1-1, kernel 7.1.9, NVIDIA). Every claim in the cause is true, and all three cited issues genuinely support it, which is unusual for this corpus. The corrections are about paths, the supported command, and reload advice that would mislead.

Confirmed on this machine, not from a source. `/usr/share/omarchy/config/hypr/monitors.lua` contains `local omarchy_gdk_scale = 2`, `local omarchy_monitor_scale = "auto"` and `hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))`. `/usr/share/omarchy/default/hypr/envs.lua` ends in an `hl.config()` block setting `xwayland = { force_zero_scaling = true }`, and `hyprctl getoption xwayland:force_zero_scaling` returns `bool: true, set: true`. The operator's own `~/.config/hypr/monitors.lua` carries a first-hand instance in a comment: `GDK_SCALE=2` on a scale-1 27 inch 1440p panel made Steam draw zoomed with its titlebar drag region offset, and the file now sets 1.

Cited issues read in full on `omacom/omarchy`. Issue 7021 is this record's cause almost verbatim, including the measured `WM_NORMAL_HINTS` minimum width of 1530 against a real 1x minimum of 765, and it names both defaults. Issue 2824 reports over-scaled Java GUIs (BurpSuite, Ghidra, JADX-GUI, JD-GUI) on Omarchy 3.1.1. Issue 6415 reports Steam not correctly scaled on 3.8.4. All three support the record. I swapped the three `basecamp/omarchy` URLs for `omacom/omarchy`, the current name; the old ones still redirect but the search API does not follow the rename.

What was wrong. The cause said "Omarchy's packaged `monitors.lua`" without saying which one. There is no `/usr/share/omarchy/default/hypr/monitors.lua`; the template lives under `config/`, not `default/`, and the file that actually runs is the user copy in `~/.config/hypr/`. The `danger` compounded this by naming `/usr/share/omarchy/default/hypr/` and `~/.local/share/omarchy/default/hypr/`, the second of which is the Omarchy 3 layout and does not exist on Omarchy 4. Both rewritten with the real paths. The fix omitted `omarchy-hyprland-monitor-scaling`, which is the supported way to change a scale and which rewrites `local omarchy_gdk_scale` in the same pass. I read that script rather than running it: it persists `int(scale + 0.5)`, so at 1.5 it writes `GDK_SCALE=2` and does not fix this bug, which issue 7021 also reports. Both the helper and its limit are now in the fix. The reload advice said `GDK_SCALE` "is read at process start and is exported through the systemd user manager, so `hyprctl reload` is not enough", then offered `systemctl --user import-environment GDK_SCALE` and `dbus-update-activation-environment`. A reload does re-apply the value, because Hyprland re-runs every `hl.env()` line, and `import-environment` imports from the calling shell, which on an already-open terminal is the stale value the user is trying to escape. Replaced with what is actually true: reload plus relaunch from a keybind works, an already-open terminal does not, and the user manager is only guaranteed after a re-login. I added a `systemctl --user show-environment` read in its place, which I ran here and which reports `GDK_SCALE=1`. The fix's Lua snippet also put the monitor rule above the `GDK_SCALE` lines, the reverse of the shipped template; reordered so it can be pasted over the real file. The verify used `pgrep -x steam` only, and now also reads the user manager and shows the `xprop` check the symptom promises.

Java. The record's only Java advice is `JAVA_TOOL_OPTIONS=-Dsun.java2d.uiScale=1`, which is sound: the Arch HiDPI page documents `sun.java2d.uiScale` for AWT and Swing and records that Java 9 and later read `GDK_SCALE` for Swing, which is why fixing `GDK_SCALE` alone usually suffices. The record does not mention `_JAVA_AWT_WM_NONREPARENTING`, so there was nothing to correct, and that is the right call: `grep -rn "JAVA" /usr/share/omarchy/` returns nothing, so Omarchy sets no Java variable at all, and the variable no longer appears on the current Hyprland environment-variables wiki page. It addresses blank or grey AWT windows under non-reparenting window managers, not scaling, so it does not belong in this record.

Duplication. This record overlaps `xwayland-blurry-on-fractional-scale` in `hyprland-config`, which after its own re-audit carries a "keep the two numbers in step" paragraph describing exactly this mismatch. It is not a duplicate. The symptom is the inverse (oversized rather than blurry), the root cause is specific to Omarchy's own shipped defaults rather than to XWayland in general, and it holds material the sibling does not: the Flatpak override, the Steam launch-option form, the per-command escape hatch and the three upstream issues. A reader searching "Steam is double size" needs this record and would not find it under a blur title. I recommend keeping both and leaving the cross-reference I added, rather than merging. The record that should be merged away is `xwayland-apps-blurry-hidpi`, audited alongside this one.

Not exercised. Nothing was written and no config, scale, mode or reload was performed, because this is the operator's daily workstation driving a real panel and libvirt VMs; every hyprctl call was a read. I did not reproduce the oversized window, so the `WM_NORMAL_HINTS` doubling is from issue 7021's measurement and not observed here. `flatpak` and `xlsclients` are not installed on this machine, so neither the override nor that detection command was run. `JAVA_TOOL_OPTIONS` was not tested.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Edit only `~/.config/hypr/monitors.lua`. The file Omarchy ships is a template at `/usr/share/omarchy/config/hypr/monitors.lua`, copied into `~/.config` at install and owned by the `omarchy` package, and `/usr/share/omarchy/default/hypr/envs.lua` is a packaged default. Editing either is overwritten by the next `omarchy update`. Setting `GDK_SCALE` below the monitor scale makes native Wayland GTK apps small, so change it only to match what `hyprctl monitors` reports.

**Fix.**

Match `GDK_SCALE` to the actual monitor scale. Check what Hyprland picked:

```bash
hyprctl monitors -j | jq -r '.[] | "\(.name)\tscale=\(.scale)"'
```

**Omarchy 4.** Let Omarchy write both numbers together, which is the supported path:

```bash
omarchy-hyprland-monitor-scaling 1
```

That sets the focused monitor's scale and rewrites `local omarchy_gdk_scale` in `~/.config/hypr/monitors.lua` in the same pass, but only while that file still has Omarchy's generic shape. It persists `GDK_SCALE` as `int(scale + 0.5)`, so a fractional scale of 1.5 still writes 2 and the overflow comes straight back. At 1.5 edit the file by hand instead.

Editing `~/.config/hypr/monitors.lua` directly, keeping the shipped line order:

```lua
-- was: local omarchy_gdk_scale = 2
local omarchy_gdk_scale = 1        -- use 1 when hyprctl reports scale 1, 1.25 or 1.5
local omarchy_monitor_scale = "auto"

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })
```

**Omarchy 3.** The same change in `~/.config/hypr/monitors.conf`, which used hyprlang rather than Lua:

```conf
env = GDK_SCALE,1
```

**Getting the new value to the app.** Hyprland re-runs every `hl.env()` line on reload, so `hyprctl reload` followed by relaunching the app from a Hyprland keybind or the Omarchy menu picks it up. Two things a reload does not fix. A terminal that was already open keeps the old value and passes it to anything you start from it. And the systemd user environment, which is what D-Bus activated and Flatpak apps inherit, is only guaranteed to match after logging out and back in. Check what the user manager currently holds:

```bash
systemctl --user show-environment | grep GDK_SCALE
```

To fix one stubborn app without changing the global value, so native Wayland GTK stays correct:

```bash
GDK_SCALE=1 GDK_DPI_SCALE=1 JAVA_TOOL_OPTIONS=-Dsun.java2d.uiScale=1 <command>
```

For a Flatpak:

```bash
flatpak override --user --env=GDK_SCALE=1 --env=JAVA_TOOL_OPTIONS=-Dsun.java2d.uiScale=1 <app.id>
```

For a Steam game, in Properties then Launch Options:

```
GDK_SCALE=1 %command%
```

For the blurry or pixelated XWayland complaint, which is the same two settings pulling the other way, see `xwayland-blurry-on-fractional-scale`.

**Verify.** Restart the app, then read the value it actually got:

```bash
tr '\0' '\n' < /proc/$(pgrep -x steam)/environ | grep GDK_SCALE
systemctl --user show-environment | grep GDK_SCALE
```

Both should show the value you set. The app's window should now fit the screen with normally sized UI. For a Java or X11 app that was hanging off the right edge, confirm the hint shrank:

```bash
xprop WM_NORMAL_HINTS
```

Click the window when the cursor becomes a cross. The minimum width should be the app's real 1x minimum rather than twice it.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/XWayland/> · <https://github.com/omacom/omarchy/issues/7021> · <https://github.com/omacom/omarchy/issues/2824> · <https://github.com/omacom/omarchy/issues/6415> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/monitors.lua> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-scaling> · <https://wiki.hypr.land/configuring/extra/xwayland/> · <https://wiki.archlinux.org/title/HiDPI>

---

## Screen sharing sends video but no sound

`screenshare-has-no-audio` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** On a Google Meet / Discord / Teams call people can see my screen perfectly but hear nothing — no game audio, no YouTube, no system sounds. My microphone works fine. OBS captures the screen but the recording's desktop-audio track is silent.

**Cause.** On Hyprland the screen-cast stream comes from xdg-desktop-portal-hyprland, which streams video only — its documented configuration (`~/.config/hypr/xdph.conf`) exposes `max_fps`, `cursor_mode`, `force_shm` and token options and nothing at all for audio, because the portal's audio path is not implemented. So "share entire screen" carries no audio no matter which app you use. Audio has to be routed separately through PipeWire: either by capturing the sink's monitor source, or by using a client that does its own capture.

> **Audit corrected this record.** The cause is well supported: I pulled hyprwm/hyprland-wiki content/hypr-ecosystem/user/xdg-desktop-portal-hyprland.md, and the entire documented `~/.config/hypr/xdph.conf` surface is `max_fps`, `allow_token_by_default`, `custom_picker_binary`, `force_shm` and `cursor_mode` — there is no audio option, exactly as the record says. The pactl/pavucontrol/qpwgraph routing, the `.monitor` source naming, `pactl move-source-output <ID> <monitor>`, the OBS "Audio Output Capture (PulseAudio)" source and the AUR packages (`obs-pipewire-audio-capture` 1.2.1-1, `vesktop` 1.6.7-1, neither of which is in the official repos, so `yay` is correct) all check out. Two claims do not. (1) "choose Chrome Tab / **Firefox Tab** and tick Share tab audio" — Firefox cannot do this at all. Mozilla bug 1541425, "Implement audio capture for getDisplayMedia", is still status NEW with no resolution (queried via the Bugzilla REST API), so a Firefox tab share carries no audio track by any route. Sending a user to look for a checkbox that does not exist is exactly the kind of confident specific this audit is meant to catch. (2) "OBS 27+ already has the PipeWire screen-capture source; only the audio plugin is separate on older builds" implies current OBS ships application audio capture on Linux. It does not: a code search of obsproject/obs-studio for "Application Audio Capture" returns hits only under plugins/win-wasapi, plugins/win-capture and plugins/mac-capture — there is no Linux implementation in any release, including the 32.2.2 installed here. The plugin is separate on every build, not just old ones. Everything else, including the danger note about leaking notification sounds and other tabs into the call, is accurate and worth keeping.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Routing a sink monitor into a call means everything the machine plays — including notification sounds, other calls, and anything in another browser tab — goes out to the other participants. Mute or move any stream you do not want shared before joining.

**Fix.**

**Browsers (Meet, Teams, Jitsi, Discord in a tab).** Only a *tab* share can carry audio, and only in a Chromium-based browser. In Chrome/Chromium/Brave/Edge choose **Chrome Tab** in the share picker and tick **Share tab audio**. Whole-screen and window shares have no audio path.

Firefox cannot share audio at all — audio capture for `getDisplayMedia` has never been implemented (Mozilla bug [1541425](https://bugzilla.mozilla.org/show_bug.cgi?id=1541425), still open). If you must use Firefox, route the sink monitor into the call as described at the bottom of this fix, or join from a Chromium-based browser instead.

**OBS.** Capture the monitor of your output sink. Find its name:

```bash
pactl list short sources | grep monitor
# e.g. alsa_output.pci-0000_00_1f.3.analog-stereo.monitor
```

Then in OBS: `+` → **Audio Output Capture (PulseAudio)** → Device = that `.monitor` source. That captures the whole desktop.

For **per-application** audio instead, you need the third-party plugin — OBS has never shipped application audio capture on Linux, only on Windows and macOS, so this is a separate install on every OBS version:

```bash
yay -S obs-pipewire-audio-capture
```

After installing it, restart OBS and add `+` → **Application Audio Capture (PipeWire)**.

**Discord desktop.** The official client's Linux screenshare audio is unreliable on Wayland. `vesktop` implements Linux screenshare with sound natively:

```bash
yay -S vesktop
```

**Anything that only accepts a microphone (Zoom, Teams desktop, Firefox, older clients).** Point its capture stream at the sink monitor while the share is running:

```bash
pactl list short source-outputs          # find the app's record stream ID
pactl list short sources | grep monitor  # find the monitor source name
pactl move-source-output <ID> <monitor-source-name>
```

The same thing with a GUI: run `pavucontrol`, open the **Recording** tab, and change the app's input device from your microphone to `Monitor of <your output>`. To mix your voice *and* desktop audio, wire both into the app's capture node with `qpwgraph`.

**Verify.** `pactl list short source-outputs` shows the sharing app's record stream bound to a `*.monitor` source. In `pavucontrol`'s Recording tab the app's level meter moves while music plays. On the receiving end of the call, audio is audible.

Sources: <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.hypr.land/Useful-Utilities/Screen-Sharing/> · <https://wiki.archlinux.org/title/PipeWire> · <https://wiki.archlinux.org/title/Open_Broadcaster_Software> · <https://github.com/Vencord/Vesktop> · <https://aur.archlinux.org/packages/obs-pipewire-audio-capture>

---

## System tray icons never appear for Electron, Java, Qt and Wine apps

`tray-icons-missing-no-sni-host` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Discord, Nextcloud, KeePassXC, Insync and Steam all claim to "minimise to tray" but nothing ever shows up in the bar — Steam simply vanishes when I close its window and I cannot get it back. Under Wine/Proton (Battle.net, uTorrent) a tiny naked window containing the tray icons floats loose on the desktop instead of docking anywhere.

**Cause.** Wayland has no XEmbed system tray — the X11 `_NET_SYSTEM_TRAY` protocol that every classic tray icon used simply does not exist. On Wayland the bar must run a StatusNotifierItem (SNI/AppIndicator) *host*, and each app must publish an SNI on the session bus. GTK and Electron apps only publish an SNI if libappindicator is present at runtime; Wine, Java/Swing `SystemTray`, and older Qt4-era apps only ever speak XEmbed and will never publish one. XWayland gives those apps an X server but no tray host to dock into, which is why Wine draws its own floating icon window.

> **Audit corrected this record.** Cause is sound and the diagnosis via `busctl --user list | grep StatusNotifier` is right - I ran it on this Omarchy 4.0.0-1 / Hyprland 0.56.2 box and it prints `org.kde.StatusNotifierWatcher` owned by quickshell, and /usr/share/omarchy/shell/plugins/bar/widgets/Tray.qml does `import Quickshell.Services.SystemTray`. But three specifics in the fix are wrong. (1) The binary path is fabricated: the Arch file list for plasma-workspace 6.7.4-3 shows `usr/bin/xembedsniproxy`, not `/usr/lib/xembedsniproxy`, so the copy-pasteable Lua line launches nothing. The record's own cited source, hyprwm/Hyprland discussion 13083, just runs `xembedsniproxy` off PATH. (2) The window rule cannot match. The record matches `class = "^xembedsniproxy$"`, but discussion 13083 - fetched in full via the GitHub GraphQL API - says the leftover helper "commonly has an empty title" and its working rule matches `xwayland true, title ^$, class ^$, initial_class ^$, initial_title ^$`. (3) The parenthetical "Before KDE 6.7.0 the helper had an empty class and you had to match title/class ^$ instead" is invented precision with the sign flipped: plasma-workspace is currently 6.7.4 and the empty class/title is the present-day behaviour, not a pre-6.7.0 one. The `no_blur` claim is genuine - the discussion says "`no_blur on` is required, otherwise the window can remain visible as a faint blurred/dark rectangle even with opacity set to 0." Two more findings worth folding in: plasma-workspace ships `etc/xdg/autostart/xembedsniproxy.desktop` but KDE's copy of it is `OnlyShowIn=KDE;` with `X-systemd-skip=true`, so it will not autostart on a Hyprland/uwsm session (the explicit autostart really is needed), and `plasma-xembedsniproxy.service` has no [Install] section (only `PartOf=graphical-session.target`), so `systemctl --user enable` on it would fail - config autostart is the correct route. Finally, the danger note's "there is no separately packaged xembedsniproxy" is true of the repos but there is a standalone AUR `xembedsniproxy` 6.7.2-0 whose deps are just kcoreaddons/kcrash/kdbusaddons/kwindowsystem/qt6-base/xcb-*, which avoids the whole Plasma stack. Verified `libappindicator` 12.10.1-2 and `libayatana-appindicator` 0.6.0-2 both exist in extra, so step 2 stands as written.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `plasma-workspace` pulls in a large chunk of the KDE Plasma stack (hundreds of MB of Qt/KF6 dependencies) purely to obtain one small binary. On a minimal Hyprland install decide whether that trade is worth it before installing; there is no separately packaged `xembedsniproxy` in the Arch repos.

**Fix.**

1. Confirm something is hosting SNI. A bar with a tray module (Waybar's `tray`, Omarchy 4's Quickshell bar) registers the watcher:

```bash
busctl --user list | grep -i StatusNotifier
```

You want to see `org.kde.StatusNotifierWatcher`. On a stock Omarchy 4 session this is already there and owned by `quickshell` — the bar's tray widget (`/usr/share/omarchy/shell/plugins/bar/widgets/Tray.qml`) is an SNI host, so skip to step 2. If the watcher is absent, no bar is hosting the tray. For Waybar, add the module:

```jsonc
// ~/.config/waybar/config.jsonc
"modules-right": ["tray", "clock"],
"tray": { "icon-size": 18, "spacing": 8 }
```

and restart it: `pkill waybar; waybar & disown`

2. Give GTK/Electron apps the AppIndicator library they probe for:

```bash
sudo pacman -S --needed libappindicator libayatana-appindicator
```

Restart the app afterwards — it only probes at startup.

3. For XEmbed-only apps (Wine/Proton launchers, Java/Swing, Steam), run KDE's XEmbed→SNI proxy. Prefer the standalone AUR package, which pulls only a handful of KF6/Qt6 libraries:

```bash
yay -S xembedsniproxy
```

If you would rather stay in the official repos, the same binary ships in `plasma-workspace` — see the danger note before choosing this:

```bash
sudo pacman -S --needed plasma-workspace
```

Either way the binary lands at `/usr/bin/xembedsniproxy`; confirm with `command -v xembedsniproxy`.

4. Autostart it. The `.desktop` file that `plasma-workspace` installs is `OnlyShowIn=KDE;`, so it will **not** fire on a Hyprland/uwsm session, and the bundled `plasma-xembedsniproxy.service` has no `[Install]` section so `systemctl --user enable` on it fails. Start it from your Hyprland config instead:

```lua
-- ~/.config/hypr/hyprland.lua
hl.on("hyprland.start", function()
  hl.exec_cmd("xembedsniproxy")
end)
```

5. Hide the leftover helper window. Once the proxy is running, XWayland still leaves a small blank helper window with an **empty class and title**, which Hyprland draws as a faint blurred rectangle:

```lua
hl.window_rule({
  name = "hide-xembed-tray-helper",
  match = {
    xwayland      = true,
    class         = "^$",
    title         = "^$",
    initial_class = "^$",
    initial_title = "^$"
  },
  float             = true,
  no_focus          = true,
  no_initial_focus  = true,
  no_anim           = true,
  no_blur           = true,
  opacity           = 0.0
})
```

`no_blur` is required — with opacity alone the helper stays visible as a dark smear. Note that this rule is deliberately broad: any XWayland window that opens with no class and no title will also be hidden. If something legitimate disappears, narrow the match.

Apply with `hyprctl reload`.

6. Restart the offending app and re-check `busctl --user list | grep StatusNotifierItem` — each tray-owning app should now hold a name there.

**Verify.** `busctl --user list | grep StatusNotifierItem` lists one bus name per app that should have a tray icon, and `busctl --user list | grep StatusNotifierWatcher` shows the host. The icons then appear in the bar. If a name is listed on the bus but no icon draws, the problem is in the bar (a known GDBus property-caching bug affects some Electron 43+ items in Waybar), not in the app.

Sources: <https://github.com/hyprwm/Hyprland/discussions/13083> · <https://github.com/Alexays/Waybar/wiki/Module:-Tray> · <https://wiki.archlinux.org/title/Wayland> · <https://archlinux.org/packages/extra/x86_64/plasma-workspace/>

---

## Sharpen blurry XWayland apps on a HiDPI display

`xwayland-apps-blurry-hidpi` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`, `xwayland`

**Symptom.** Some apps look soft, fuzzy or blocky compared to the rest of the desktop, with visible fringing or stair-stepping on text. Typically Steam, older Electron builds, Java IDEs, Wine apps, VS Code launched in X11 mode, or anything launched before the toolkit environment variables were set. Native GTK and Qt apps on Wayland look fine.

**Cause.** The app is running under XWayland. Xorg has no per-output scale, so the compositor renders the X client at 1x and then scales that bitmap up to the monitor's scale factor. At a fractional scale such as 1.5 the resampling shows as soft, fuzzy text. On Hyprland 0.56.2 `xwayland:use_nearest_neighbor` defaults to true, confirmed live with `hyprctl getoption`, so the upscale is nearest neighbour and the result usually reads as blocky and pixelated rather than soft. Either way no detail is added, because the client was only ever asked to draw at 1x.

> **Audit corrected this record.** Re-checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1, quickshell 0.3.1-1, kernel 7.1.9, NVIDIA) against local files and the current upstream wikis. The mechanism holds and the danger holds, but the Omarchy 4 half of the fix is wrong in a way that makes it a no-op.

The hard defect: the record tells an Omarchy 4 user to put `hl.env()` lines in `~/.config/hypr/envs.lua`. That file does not exist and is never loaded. Read on this machine, the packaged template `/usr/share/omarchy/config/hypr/hyprland.lua` and the live `~/.config/hypr/hyprland.lua` both load `default.hypr.omarchy` and then require exactly five user modules: `hypr.monitors`, `hypr.input`, `hypr.bindings`, `hypr.looknfeel`, `hypr.autostart`. There is no `hypr.envs` and `default/hypr/require_all.lua` is not pointed at `~/.config/hypr`, so a user following the record creates a file that is never read and concludes the fix does not work. Replaced with the files Omarchy actually loads, plus the option of adding the require line yourself.

The second defect: on Omarchy 4 that whole first block is already shipped. `/usr/share/omarchy/default/hypr/envs.lua` on this machine sets `GDK_BACKEND`, `QT_QPA_PLATFORM`, `MOZ_ENABLE_WAYLAND`, `ELECTRON_OZONE_PLATFORM_HINT` and `OZONE_PLATFORM`, and `systemctl --user show-environment` reports all five live. `SDL_VIDEODRIVER` is the only one of the set Omarchy does not ship, and it is absent from `env` here. So the record's headline fix is generic Arch advice presented as an Omarchy action, and following it changes nothing. Rewritten to say what is already set and what is missing.

The cause was wrong on 0.56.2. It says the result is blurry rather than pixelated. `hyprctl getoption xwayland:use_nearest_neighbor` reads `bool: true, set: false` here, so the default upscale is nearest neighbour and pixelation is the normal presentation. Rewritten to cover both and to drop the false dichotomy.

Smaller items. `xlsclients` is not installed on this machine and `pacman -Qo /usr/bin/xlsclients` reports no owner, so the record should name `xorg-xlsclients`. The two full hyprlang blocks for Hyprland 0.54 and older were a copy-paste hazard in a corpus about Omarchy 4, where `env =` and an `xwayland { }` block are both wrong; compressed to one labelled sentence. Added the `force_zero_scaling` reading and the `select(.xwayland)` jq filter to verify, since the old verify never checked the option.

What held. The plain-Hyprland Lua block is verbatim correct against `content/configuring/extra/xwayland.md` in `hyprwm/hyprland-wiki`, including `scale = "2"` as a string, `GDK_SCALE` at 2 and `XCURSOR_SIZE` at 32, and that page still carries the warning that XWayland HiDPI patches are no longer supported, so the record's `danger` is right as written and was not touched. `force_zero_scaling = true` is in the `hl.config()` block at the end of `/usr/share/omarchy/default/hypr/envs.lua`, read here, and `hyprctl getoption xwayland:force_zero_scaling` returns `bool: true, set: true`. All five cited URLs return 200.

Duplication. This record duplicates `xwayland-blurry-on-fractional-scale` in `hyprland-config` almost completely: same symptom, same mechanism, same primary fix, same danger, three shared sources. The only thing it held that the sibling does not was the make-it-native-Wayland branch, and on Omarchy 4 four of those five variables are already set by default, so that branch is nearly empty on the distro this corpus is about. The sibling is the fuller record: it covers Qt, Java, Electron flag files, `Xft.dpi`, the `omarchy-hyprland-monitor-scaling` helper and the GDK_SCALE mismatch, and it has been re-audited against Omarchy 4. I recommend the operator merge this record into `xwayland-blurry-on-fractional-scale`, carrying over only the native-Wayland branch and the `SDL_VIDEODRIVER` gap. I have corrected it in place rather than rejecting it, because the problem is real and the decision is not mine.

Not exercised. Nothing was written, no config changed, no reload, no `hyprctl keyword` or `dispatch`, because this is the operator's daily workstation driving a real 1440p panel and libvirt VMs. No app was relaunched, so the visual outcome is from the wiki and not observed here. I did not prove that a user `hl.env()` overrides Omarchy's default for the same variable; that is reasoned from the load order in `hyprland.lua`, and the live `GDK_SCALE=1` only proves a variable Omarchy's `envs.lua` never sets.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not install "XWayland HiDPI patches" — the Hyprland wiki explicitly states they are no longer supported and must not be used.

**Fix.**

First confirm the app really is on XWayland:

```bash
hyprctl clients -j | jq -r '.[] | select(.xwayland) | "\(.class)\t\(.title)"'
```

`xlsclients -l` also works but is not installed by default on Omarchy 4 or Arch; it needs `xorg-xlsclients`. Do not use `hyprctl clients | grep xwayland`, because `xwayland: 0` is itself the matched line and never tells you which window it belongs to.

**Best fix: make the app native Wayland.**

On Omarchy 4 this is already done for you. `/usr/share/omarchy/default/hypr/envs.lua` ships:

```lua
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("MOZ_ENABLE_WAYLAND", "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "wayland")
hl.env("OZONE_PLATFORM", "wayland")
```

The only one of the usual set Omarchy does not ship is `SDL_VIDEODRIVER`. An app still on XWayland with those set either has no Wayland backend at all (Steam, Wine, most Java Swing) or was started from a shell that predates the setting.

On plain Arch with Hyprland 0.55 or newer, put the same lines in `~/.config/hypr/hyprland.lua`, plus:

```lua
hl.env("SDL_VIDEODRIVER", "wayland")
```

**Where these lines go on Omarchy 4.** There is no `~/.config/hypr/envs.lua`, and creating one does nothing: the stock `~/.config/hypr/hyprland.lua` loads Omarchy's defaults and then requires exactly five user files, `hypr.monitors`, `hypr.input`, `hypr.bindings`, `hypr.looknfeel` and `hypr.autostart`. Add your `hl.env()` lines to one of those, or add a `require("hypr.envs")` line to `~/.config/hypr/hyprland.lua` yourself. User files load after Omarchy's defaults, so a value you set there is the last one applied.

**For apps that genuinely cannot do Wayland**, stop the compositor scaling them and let the toolkit scale instead. This is the Hyprland wiki's recipe, for plain Hyprland 0.55 or newer:

```lua
hl.monitor({ output = "", mode = "highres", position = "auto", scale = "2" })

hl.config({
  xwayland = {
    force_zero_scaling = true,
  },
})

hl.env("GDK_SCALE", "2")
hl.env("XCURSOR_SIZE", "32")
```

**Omarchy 4 already ships the compositor half.** `force_zero_scaling = true` is in the `hl.config()` block at the end of `/usr/share/omarchy/default/hypr/envs.lua`, and `XCURSOR_SIZE` and `HYPRCURSOR_SIZE` are set to 24 in the same file. `GDK_SCALE` is set near the top of `~/.config/hypr/monitors.lua`, from a local variable, above the catch-all monitor rule. Edit that file rather than adding a second `hl.env("GDK_SCALE", ...)` somewhere else:

```lua
-- ~/.config/hypr/monitors.lua
local omarchy_gdk_scale = 2
local omarchy_monitor_scale = "auto"

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })
```

or let Omarchy write both numbers together:

```bash
omarchy-hyprland-monitor-scaling 2
```

`GDK_SCALE` must stay the nearest integer to the monitor scale. Setting it higher makes GTK, XWayland and Java apps draw at double size, which is the opposite complaint. See `gdk-scale-mismatch-oversized-xwayland`, and `xwayland-blurry-on-fractional-scale` for the fuller version of this same fix including Qt, Java, Electron and `Xft.dpi`.

Hyprland 0.54 and older used hyprlang rather than Lua, so the equivalent lines were `env = GDK_SCALE,2` and an `xwayland { force_zero_scaling = true }` block in `~/.config/hypr/hyprland.conf`. Nothing current on Arch or Omarchy 4 uses that syntax.

Environment changes only reach apps started after the config is re-read. Hyprland re-runs every `hl.env()` line on reload, so `hyprctl reload` and then relaunching the app from a keybind or the Omarchy menu is enough. A terminal that was already open keeps the old value and passes it to anything started from it, and the systemd user environment is only guaranteed to match after logging out and back in.

**Verify.** Relaunch the app, then check both halves:

```bash
hyprctl getoption xwayland:force_zero_scaling
# bool: true
# set: true

hyprctl clients -j | jq -r '.[] | select(.xwayland) | "\(.class)\t\(.title)"'
```

`getoption` prints `bool: true` on two lines, never `1`. If the app no longer appears in the second command it went native Wayland and the problem is gone. If it still appears but `force_zero_scaling` is on, its text should now be crisp rather than blocky. It may look small, which is the toolkit-scaling half of the job and is fixed with `GDK_SCALE`, not by turning `force_zero_scaling` back off.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/XWayland/> · <https://wiki.hypr.land/0.54.0/Configuring/XWayland/> · <https://wiki.hypr.land/0.54.0/FAQ/> · <https://wiki.archlinux.org/title/Wayland> · <https://wiki.archlinux.org/title/HiDPI> · <https://wiki.hypr.land/configuring/extra/xwayland/> · <https://wiki.hypr.land/configuring/core/environment-variables/> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/hyprland.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/monitors.lua>

---

## Fix apps taking 20 to 30 seconds to open with several portals installed

`apps-slow-to-launch-multiple-portals` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** GUI apps take 20-30 seconds to show a window, or a file-open dialog hangs for ~25 seconds before appearing. Screen sharing may also be broken at the same time. Nothing obvious in the app's own output.

**Cause.** More than one xdg-desktop-portal backend is installed and they compete for the same D-Bus interfaces, or a backend fails to launch and xdg-desktop-portal blocks on a 25-second D-Bus timeout before falling through. Portal backends declare which interfaces they handle in `/usr/share/xdg-desktop-portal/portals/*.portal`; when two claim the same one with no preference configured, requests stall.

> **Audit corrected this record.** The diagnosis and the inspection commands are sound, and the 25-second D-Bus timeout is real. Two problems. First, the 'pin the preference' step is a no-op as written: `default = hyprland;gtk` with `FileChooser = gtk` is byte-for-byte what the shipped `/usr/share/xdg-desktop-portal/hyprland-portals.conf` already contains, so copying it into ~/.config changes nothing. Second, the cited omarchy#7944 does not support this fix — in that issue the GTK portal itself is what times out, and the verified resolution was to route FileChooser AWAY from gtk (to Nautilus's own implementation), not toward it. The nuclear autostart script is real Hyprland wiki content but the record inflates the wiki's sleeps (1/2) to 4/4 without saying why.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Removing a portal backend that something actually depends on (e.g. removing xdg-desktop-portal-gtk) leaves you with no file chooser at all — apps will silently fail to open Save/Open dialogs. Remove one at a time and re-test.

**Fix.**

See which backends are installed:

```bash
pacman -Qs xdg-desktop-portal
ls /usr/share/xdg-desktop-portal/portals/
systemctl --user status 'xdg-desktop-portal*'
```

On Hyprland you want exactly two: `xdg-desktop-portal-hyprland` (screencast, screenshot, global shortcuts) and `xdg-desktop-portal-gtk` (file chooser, everything else). Remove strays such as `xdg-desktop-portal-wlr`, `-gnome` or `-kde` if you are not using those desktops (check first that nothing else pulls them in):

```bash
pactree -r xdg-desktop-portal-wlr
sudo pacman -Rns xdg-desktop-portal-wlr
```

Be aware that `default = hyprland;gtk` with `org.freedesktop.impl.portal.FileChooser = gtk` is ALREADY the shipped default in `/usr/share/xdg-desktop-portal/hyprland-portals.conf` — writing that same content into `~/.config/xdg-desktop-portal/hyprland-portals.conf` changes nothing and will not fix a stall. Only write a user override when you are actually changing the routing, e.g. to the KDE picker:

```ini
[preferred]
default = hyprland;gtk
org.freedesktop.impl.portal.FileChooser = kde
```

Restart the stack:

```bash
systemctl --user restart xdg-desktop-portal-hyprland.service xdg-desktop-portal-gtk.service xdg-desktop-portal.service
```

If the 25s stall persists with only these two backends installed, read the logs before changing config — a backend that is present but hanging (`xdg-desktop-portal-gtk: Error: Timeout was reached`, as in omarchy#7944) is a different fault from two backends competing:

```bash
journalctl --user -u xdg-desktop-portal -u xdg-desktop-portal-gtk -u xdg-desktop-portal-hyprland -b --no-pager | tail -50
```

If the portals still launch before the environment is ready, the Hyprland wiki's blunt-instrument autostart script works (wiki sleeps are 1 and 2; raise them only if that is not enough):

```bash
#!/bin/sh
sleep 1
killall -e xdg-desktop-portal-hyprland
killall xdg-desktop-portal
/usr/lib/xdg-desktop-portal-hyprland &
sleep 2
/usr/lib/xdg-desktop-portal &
```

**Verify.** `systemctl --user status xdg-desktop-portal` shows no repeated `A backend call failed` lines, and an app that used to hang (e.g. opening a file dialog in Firefox) responds within a second.

Sources: <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://wiki.hypr.land/0.54.0/FAQ/> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://github.com/basecamp/omarchy/issues/7944>

---

## Fix Chromium freezing when you paste from an XWayland app

`chromium-hangs-pasting-from-xwayland-app` · severity: **medium** · frequency: **common** · applies to: `arch`, `electron`, `hyprland`, `omarchy`, `wayland`, `xwayland`

**Symptom.** Copy something in one app, click into Chromium (or Obsidian, or another Electron app) and press Ctrl+V — the app freezes and shows "Application Not Responding". Most often reported copying out of a Windows VM / Docker Windows container, or out of an XWayland app into a native Wayland app. Recovery requires killing the app.

**Cause.** Under investigation upstream. The clipboard transfer between an XWayland source and a Wayland consumer stalls: Chromium blocks its UI thread waiting for a data-offer read that never completes, typically with rich-text/HTML mime types. Multiple Omarchy users confirm it is specific to XWayland-source -> Wayland-target transfers.

> **Audit corrected this record.** The problem is real and honestly framed — omarchy#2903 exists ('Chromium Freezes When Pasting Clipboard Data From Windows', still open), and the record correctly says no root-cause fix exists rather than inventing one. The mitigations (Ctrl+Shift+V, laundering through wl-clipboard, wl-clip-persist taking ownership) are all sound. The defect is the 0.55+ bind: `hl.bind("SUPER SHIFT + V", ...)` does not match the documented modifier syntax, which joins every modifier with ` + ` (the wiki's examples are "SUPER + SHIFT + Q", "SUPER + XF86AudioNext"), so the bind fails to parse and the user silently gets no key. The recovery command is also oversold — pkill on all renderer processes drops every tab's renderer, not just the hung one.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

No root-cause fix exists yet. Practical mitigations:

Paste as plain text, which avoids the rich-text mime negotiation that appears to trigger it:

```
Ctrl+Shift+V
```

Or launder the clipboard through wl-clipboard so a local, well-behaved client owns it before you paste:

```bash
wl-paste --no-newline | wl-copy
```

Bind that to a key.

Hyprland <=0.54 / Omarchy 3.x:

```conf
bind = SUPER SHIFT, V, exec, wl-paste --no-newline | wl-copy --type text/plain
```

Hyprland 0.55+ / Omarchy 4.x — every modifier is joined with ` + `; `"SUPER SHIFT + V"` will not parse:

```lua
hl.bind("SUPER + SHIFT + V", hl.dsp.exec_cmd("wl-paste --no-newline | wl-copy --type text/plain"))
```

(Use `hl.dsp.exec_cmd` rather than a plain Lua function here — the wiki warns that clipboard tools called inline from a bind callback block the compositor event loop and can freeze the whole desktop.)

Running `wl-clip-persist --clipboard regular` also helps, because the persist daemon becomes the clipboard owner instead of the dying/remote X client:

```bash
sudo pacman -S --needed wl-clip-persist
```

When it does hang, kill only that browser — note this drops every tab's renderer in that instance, not just the stuck one, so prefer the plain kill and let Chromium restore:

```bash
pkill chromium
```

**Verify.** Copy rich text out of the VM/XWayland app and paste with Ctrl+Shift+V — the target app stays responsive.

Sources: <https://github.com/basecamp/omarchy/issues/2903> · <https://wiki.archlinux.org/title/Clipboard>

---

## Stop a Chromium window shrinking a little on every interaction

`chromium-window-shrinks-fractional-scaling` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `electron`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Chromium or an Electron app running natively on Wayland shrinks itself a little on every interaction, so the window creeps smaller and smaller. Mouse clicks land offset from where you clicked. Only happens when the monitor scale is fractional (1.25, 1.5, 1.75).

**Cause.** A long-standing Chromium bug in its per-surface Wayland fractional-scaling implementation. Chromium mis-applies the fractional scale when reporting its own size back to the compositor, so each round trip shrinks it and desynchronises input coordinates. Affects everything built on the same Ozone code, i.e. all Electron apps.

**Fix.**

Disable Chromium's per-surface scaling. Put the flag in the persistent flags file — `~/.config/chromium-flags.conf` for the `chromium` package, `~/.config/chrome-flags.conf` for Google Chrome:

```
--disable-features=WaylandPerSurfaceScale
```

That flag was **removed in Chromium 146**. On 146 and later use:

```
--disable-features=WaylandFractionalScaleV1
```

Fully quit the browser (close every window and any background/tray instance) and relaunch — do not use the in-browser "Relaunch" button, it restarts on the old platform.

If you would rather pin an explicit scale instead:

```
--force-device-scale-factor=1.5 --gtk-version=4
```

On Omarchy, `~/.config/chromium-flags.conf` is the right place; Omarchy reads it for its Chromium install.

**Verify.** Open Chromium, resize it, click around a page for a minute — the window keeps its size and clicks land where the cursor is.

Sources: <https://wiki.archlinux.org/title/Chromium> · <https://wiki.archlinux.org/title/HiDPI>

---

## Get Discord push-to-talk working when its keybind recorder captures nothing

`discord-global-keybinds-not-working` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `electron`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Push-to-talk and other Discord keybinds do nothing. The Discord keybind recorder will not capture a key at all — pressing keys in the Keybinds settings page registers nothing.

**Cause.** Native-Wayland Discord cannot grab global keys; keyboard input only reaches a focused surface, and Discord does not implement the GlobalShortcuts portal. Under XWayland it can use X11 grabs, which is why the same build works there. Omarchy sets `ELECTRON_OZONE_PLATFORM_HINT=wayland` globally, so Discord runs native Wayland by default.

> **Audit corrected this record.** The cause (no global key grabs on Wayland, Discord does not implement the GlobalShortcuts portal) is correct, and the record even states that Omarchy sets ELECTRON_OZONE_PLATFORM_HINT globally — but the fix then contradicts that. Omarchy's default/hypr/envs.lua exports BOTH ELECTRON_OZONE_PLATFORM_HINT=wayland and OZONE_PLATFORM=wayland. Blanking only the Electron hint leaves OZONE_PLATFORM=wayland set, so Chromium's Ozone layer still selects the Wayland platform and Discord stays native Wayland — the keybind recorder still captures nothing and the user concludes the record is wrong. The companion record for Electron windows gets this right by unsetting both; this one does not. The .desktop file inherits the same bug. The wpctl push-to-talk alternative is correct (set-mute 0 on press, 1 on release) but is given only in hyprlang, with no 0.55+/Lua form.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Running Discord under XWayland means its screen share can no longer see native Wayland windows or the whole screen — see the `xwayland-app-cannot-share-wayland-windows` record. You are trading one capability for the other.

**Fix.**

Run Discord under XWayland. Omarchy exports BOTH `ELECTRON_OZONE_PLATFORM_HINT=wayland` and `OZONE_PLATFORM=wayland`, so blanking only the first leaves the app on Wayland — unset both, or force X11 outright:

```bash
env -u ELECTRON_OZONE_PLATFORM_HINT -u OZONE_PLATFORM discord
```

or, more explicit and immune to whatever else is exported:

```bash
discord --ozone-platform=x11
```

If that works, make a second desktop entry rather than editing the packaged one:

```bash
cp /usr/share/applications/discord.desktop ~/.local/share/applications/discord-x11.desktop
```

Edit `~/.local/share/applications/discord-x11.desktop`:

```ini
Name=DiscordX
Exec=env -u ELECTRON_OZONE_PLATFORM_HINT -u OZONE_PLATFORM /usr/bin/discord
```

Confirm it worked — the window must show as XWayland:

```bash
hyprctl clients -j | jq '.[] | select(.class|test("discord";"i")) | {class, xwayland}'
```

Alternative that keeps Wayland: bind push-to-talk in Hyprland and have it toggle mute in PipeWire instead of relying on Discord's own grab.

Hyprland <=0.54 / Omarchy 3.x:

```conf
bind = , mouse:276, exec, wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0
bindr = , mouse:276, exec, wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 1
```

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/bindings.lua`):

```lua
hl.bind("mouse:276", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0"))
hl.bind("mouse:276", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 1"), { release = true })
```

**Verify.** Open Discord Settings -> Keybinds -> Record Keybind and press a key — it is captured. Push-to-talk then works while another window is focused.

Sources: <https://wiki.hypr.land/0.54.0/FAQ/> · <https://wiki.archlinux.org/title/Wayland>

---

## Drag and drop refuses to drop between XWayland and native Wayland apps

`drag-drop-fails-across-xwayland-boundary` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Dragging a file from the file manager onto Discord, Slack, Steam or a Java IDE does nothing — the drop cursor shows the "no entry" symbol and the app never receives the file. Dragging an image out of Firefox into GIMP fails the same way. Everything works if I log into an X11 session instead.

**Cause.** A drag that starts in a Wayland client and ends in an X11 client (or the reverse) has to be bridged by the compositor's XWayland DnD implementation. Hyprland's broke and was re-added in 0.46.0 — the release notes say "XWayland Drag and Drop is back! You can now drag stuff from your Wayland clients to X11 clients." On current Hyprland the usual remaining cause is that one of the two apps is on the X11 side when it did not have to be: Electron apps fall back to X11 whenever the Ozone platform is not selected, and drags between two apps on the *same* side always work.

**Fix.**

1. Check your Hyprland version — anything before 0.46.0 has no XWayland DnD at all:

```bash
hyprctl version
```

On Omarchy update through `omarchy update` rather than a direct pacman transaction.

2. Find out which side each app is actually on:

```bash
hyprctl clients | grep -E '^\s+(class|title|xwayland)'
```

`xwayland: 1` means that client is an X11 client.

3. Move the Electron/Chromium app to native Wayland so both ends of the drag are Wayland clients. Electron ≥ 38.2 defaults to Wayland; older builds need a hint:

```sh
# ~/.config/uwsm/env
export ELECTRON_OZONE_PLATFORM_HINT=wayland
```

or per app, for Arch-packaged Electron apps:

```conf
# ~/.config/electron-flags.conf
--ozone-platform=wayland
```

For apps that bundle Electron, patch the desktop entry:

```bash
cp /usr/share/applications/slack.desktop ~/.local/share/applications/
sed -i 's|^Exec=\(.*\)/slack |Exec=\1/slack --ozone-platform=wayland |' ~/.local/share/applications/slack.desktop
update-desktop-database ~/.local/share/applications
```

4. If the target genuinely cannot run on Wayland (Steam, most Java/Swing apps, Wine), drag from an X11 file manager instead so both ends are X11:

```bash
GDK_BACKEND=x11 nautilus &   # or: GDK_BACKEND=x11 thunar &
```

or sidestep the drag entirely and use the app's own file-open dialog.

5. Restart both applications — the backend is chosen at process start.

**Verify.** `hyprctl clients` shows `xwayland: 0` for both the source and the target app, and the drop is accepted. As a control, drag between two known-native apps (e.g. two GTK4 windows) to confirm DnD works at all in your session.

Sources: <https://hypr.land/news/update46/> · <https://github.com/hyprwm/Hyprland/issues/7644> · <https://github.com/hyprwm/Hyprland/issues/1083> · <https://wiki.archlinux.org/title/Wayland> · <https://wiki.archlinux.org/title/Electron>

---

## Get Firefox to ask where to save downloads again

`firefox-no-download-save-dialog` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Firefox never asks where to save a file, even with "Always ask you where to save files" enabled in Settings — downloads go straight to the default folder or silently do nothing. Or upload file-pickers fail to open.

**Cause.** Firefox delegates the file chooser to the XDG portal, and no portal backend implementing `org.freedesktop.impl.portal.FileChooser` is installed or reachable. On a bare Hyprland/standalone-WM install this is common because XDPH deliberately does not implement a file picker.

**Fix.**

```bash
sudo pacman -S --needed xdg-desktop-portal xdg-desktop-portal-gtk
systemctl --user restart xdg-desktop-portal-gtk.service xdg-desktop-portal.service
```

If the picker still misbehaves, check whether `GTK_USE_PORTAL` is set — any value triggers a known Firefox bug:

```bash
env | grep GTK_USE_PORTAL
```

If it is set, remove it from your shell rc and from your Hyprland env config, then log out and back in.

If you want to control portal use explicitly, in `about:config`:

```
widget.use-xdg-desktop-portal.file-picker = 1     # 1 = always use portal, 2 = auto
```

Set it to `0` to use Firefox's own GTK dialog instead of the portal.

**Verify.** Download a file in Firefox — a Save dialog appears. Check `systemctl --user status xdg-desktop-portal-gtk` shows `active (running)`.

Sources: <https://wiki.archlinux.org/title/Firefox> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal>

---

## Fix an X11 app never receiving the file you picked in the GTK dialog

`gtk-file-chooser-does-nothing-xwayland` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`, `xwayland`

**Symptom.** In an X11/XWayland application, clicking "Open File" pops up the GTK file dialog, you pick a file, the dialog closes — and nothing happens. The app never receives the file. Or the dialog takes ~25 seconds to appear at all.

**Cause.** xdg-desktop-portal-hyprland implements no file picker at all, so `xdg-desktop-portal-gtk` has to be installed alongside it; with nothing claiming `org.freedesktop.impl.portal.FileChooser` the call blocks for the 25-second D-Bus timeout and then gives up. Note that portal results are returned to the caller over D-Bus via the `Response` signal - they do not travel over the X connection - so a missing `DISPLAY` in the portal user service's environment does not break the result path. At most it stops the GTK dialog being made transient-for an X11 parent window.

> **Audit corrected this record.** The first half is correct and useful — XDPH genuinely does not implement a file picker (the wiki carries an explicit warning to install xdg-desktop-portal-gtk alongside it), the 25-second figure is the real D-Bus timeout, and the Steam 'Add Library Folder' note is right. The DISPLAY drop-in is the problem. Portal results are returned to the caller over D-Bus via the Response signal; they do not travel over the X connection, so 'can show the dialog but cannot hand the result back to an XWayland client' is not a real mechanism. At most a DISPLAY lets the GTK portal make the dialog transient-for an X11 parent window. And hardcoding DISPLAY=:0 is a guess — Hyprland's XWayland can land on :1 or higher when another X server is present, in which case the drop-in points the portal at the wrong display. Telling a user to write a persistent systemd override on a false premise is the part worth removing.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Make sure the GTK backend is installed and is the declared FileChooser provider — XDPH does not implement a file picker at all:

```bash
sudo pacman -S --needed xdg-desktop-portal-gtk
```

Check what is actually claiming the interface, and whether a backend is timing out rather than missing:

```bash
ls /usr/share/xdg-desktop-portal/portals/
cat /usr/share/xdg-desktop-portal/hyprland-portals.conf
journalctl --user -u xdg-desktop-portal -u xdg-desktop-portal-gtk -b --no-pager | tail -50
```

`default = hyprland;gtk` with `org.freedesktop.impl.portal.FileChooser = gtk` is already the shipped default, so only write `~/.config/xdg-desktop-portal/hyprland-portals.conf` if you are changing the routing (e.g. to `kde`).

Then restart the stack:

```bash
systemctl --user restart xdg-desktop-portal-gtk.service xdg-desktop-portal.service
```

Do NOT add a `DISPLAY=:0` systemd drop-in for xdg-desktop-portal-gtk. Portal results are returned to the calling app over D-Bus, not over the X connection, so a missing DISPLAY cannot swallow your file selection — and Hyprland's XWayland is not guaranteed to be `:0`, so hardcoding it can point the portal at a display that does not exist. If you want the dialog to be modal over an X11 parent, import the real value instead of guessing it:

```bash
echo $DISPLAY
systemctl --user import-environment DISPLAY
systemctl --user restart xdg-desktop-portal-gtk.service
```

Better still, move the app off XWayland so the problem cannot occur — see the `xwayland-apps-blurry-hidpi` record for the toolkit env vars.

Steam has its own broken internal picker; installing `xdg-desktop-portal-gtk` is exactly what makes "Add Library Folder" work.

**Verify.** In an XWayland app, open a file dialog, pick a file — the app actually loads it, and the dialog appears in well under a second.

Sources: <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.hypr.land/0.54.0/FAQ/>

---

## Bring oversized Java apps like Ghidra and Burp Suite back to normal size

`java-swing-apps-oversized` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`, `xwayland`

**Symptom.** Java GUI applications — Burp Suite, Ghidra, JADX-GUI, JD-GUI, JetBrains IDEs — open enormously zoomed in. Buttons and fonts are roughly double size and the window may be larger than the screen. Non-Java apps are fine.

**Cause.** Since Java 9, AWT/Swing reads GDK_SCALE to pick its UI scale. Under a Wayland compositor Java runs through XWayland and does not see the Wayland scale, so it applies GDK_SCALE on top of an already-correctly-sized X screen. AWT/Swing only honours integer scales, so GDK_SCALE=2 doubles everything.

**Fix.**

Override the scale for Java processes only. Per-launch:

```bash
java -Dsun.java2d.uiScale=1 -jar burpsuite.jar
```

Or via environment, which works for wrapper scripts you cannot edit:

```bash
JAVA_TOOL_OPTIONS=-Dsun.java2d.uiScale=1 GDK_SCALE=1 ghidraRun
```

Make it permanent for a desktop entry — copy it to your user dir first so package updates do not clobber it:

```bash
cp /usr/share/applications/burpsuite.desktop ~/.local/share/applications/
```

then edit the Exec line:

```ini
Exec=env GDK_SCALE=1 JAVA_TOOL_OPTIONS=-Dsun.java2d.uiScale=1 /usr/bin/burpsuite
```

JavaFX apps use a different property and do support fractions:

```bash
java -Dglass.gtk.uiScale=1.5 -jar app.jar
```

For JetBrains IDEs, add to Help > Edit Custom VM Options:

```
-Dsun.java2d.uiScale.enabled=true
-Dsun.java2d.uiScale=1
```

**Verify.** Relaunch the Java app — the toolbar icons and menu font are the same physical size as in your other apps, and the window fits on screen.

Sources: <https://wiki.archlinux.org/title/HiDPI> · <https://github.com/basecamp/omarchy/issues/2824> · <https://github.com/basecamp/omarchy/issues/7021>

---

## Make OBS hotkeys fire while another window is focused

`obs-global-hotkeys-dont-work` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** OBS start/stop recording and scene-switch hotkeys only fire when the OBS window itself is focused. Press them while gaming or in a browser and nothing happens.

**Cause.** Wayland gives no client the ability to grab keys globally; that requires the GlobalShortcuts portal, which OBS does not implement (obsproject/obs-studio issue 10538). OBS's hotkey system falls back to focused-window input only.

> **Audit corrected this record.** Cause is right and the plugin is real — obs-wayland-hotkeys-git exists in the AUR (maintainer MonterraByte, upstream leia-uwu/obs-wayland-hotkeys, 'OBS Studio plugin that implements the global shortcuts portal'), and XDPH does implement org.freedesktop.impl.portal.GlobalShortcuts. The websocket alternative is broken as written: `obs-cmd toggle-record` is not a valid invocation. obs-cmd's CLI is noun-then-verb — the recording commands are `obs-cmd recording start|stop|toggle|pause|resume|status`. The record also never tells the user to install obs-cmd (AUR only, not in the official repos), and the Lua bind uses `"SUPER SHIFT + R"` where the 0.55+ syntax joins every modifier with ` + ` (`"SUPER + SHIFT + R"`), so the bind would not parse.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Install the plugin that wires OBS into the XDG GlobalShortcuts portal:

```bash
yay -S obs-wayland-hotkeys-git
```

Restart OBS — it will prompt to register global shortcuts on next launch (xdg-desktop-portal-hyprland implements `org.freedesktop.impl.portal.GlobalShortcuts`, so the prompt is handled).

Alternative without a plugin: bind the keys in Hyprland and drive OBS over its websocket. Enable Tools -> WebSocket Server Settings in OBS, note the port and password, then install the client (AUR only):

```bash
yay -S obs-cmd
```

The command is noun-then-verb — `obs-cmd recording toggle`, not `obs-cmd toggle-record`. If you set a websocket password, pass it with `--websocket obsws://localhost:4455/<password>` or export `OBS_WEBSOCKET_URL`.

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/bindings.conf`):

```conf
bind = SUPER SHIFT, R, exec, obs-cmd recording toggle
```

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/bindings.lua`) — note every modifier is joined with ` + `:

```lua
hl.bind("SUPER + SHIFT + R", hl.dsp.exec_cmd("obs-cmd recording toggle"))
```

Verify it before trusting the keybind:

```bash
obs-cmd recording status
```

**Verify.** Focus another window, press the hotkey, and OBS's recording indicator changes state.

Sources: <https://wiki.archlinux.org/title/Open_Broadcaster_Software> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal>

---

## Replace an X11-era screenshot tool that breaks on multiple monitors

`screenshot-tool-broken-multimonitor` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Flameshot (or another X11-era screenshot tool) opens on the wrong monitor, captures only one screen, produces a warped image when you Ctrl+C from its GUI, or hangs the session so Esc and clicks do nothing while the cursor still moves.

**Cause.** Flameshot has no direct way to read the screen on Wayland. It asks xdg-desktop-portal for the capture, then draws its own selection and annotation overlay as an ordinary toplevel window. Hyprland places that toplevel on one output like any other window, so the overlay appears on the wrong monitor, covers only that monitor, and the region the user drags is measured against one output instead of the whole layout. Scale and transform make it worse: a HiDPI or rotated output shifts the coordinates the overlay reports against the pixels the portal returned, which is where the warped image comes from. Upstream Flameshot documents the same conclusion and answers it with a per-monitor capture plus window rules rather than a whole-desktop grab. Omarchy 4 does not hit any of this, because it ships its own capture stack that reads the real monitor rectangles out of Hyprland before it captures anything.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, Hyprland 0.56.2, two real outputs: HDMI-A-1 at 0x0 2560x1440 and vncpanel at 2560x0 1920x1080) and against both cited pages plus Flameshot upstream. Four defects. (1) The record works around the distribution. Omarchy 4 binds PRINT to omarchy-capture-screenshot in /usr/share/omarchy/default/hypr/bindings/utilities.lua, and that script drives omarchy-capture-region, which reads hyprctl monitors -j, divides width and height by scale and swaps them for transform 1 and 3, so it is already the multi-monitor answer. grim 1.5.0-2, slurp 1.5.0-2 and wl-clipboard 1:2.3.0-1 are already installed, so the pacman line installs nothing. The record buries this in one sentence after telling the reader to add a duplicate bind. (2) The Flameshot window rules are not what the cited source says. The 0.54 FAQ (fetched, HTTP 200) has three rules in the form `windowrule = match:title flameshot, float true`, `move 0 0` and `suppress_event fullscreen`. The record's five rules with `class:flameshot`, `pin`, `noinitialfocus` and `monitor 1` appear on neither cited page, and the unversioned Screenshots and Recording page dropped the Flameshot rules entirely in the 2026-08-29 wiki restructure (hyprwm/hyprland-wiki commit cba1dbc5), leaving only 'make sure your desktop portal setup is working'. (3) `XDG_CURRENT_DESKTOP=sway flameshot gui` is misapplied. Flameshot's own docs/UsageHyprlandSwayWlroots.md scopes that to Sway and river with xdg-desktop-portal-wlr, exported before the compositor launches. Confirmed here that xdg-desktop-portal-wlr is not installed (pacman -Q fails) while xdg-desktop-portal-hyprland 1.4.1-1 is, so on Omarchy the trick points at a missing backend. Upstream's actual multi-monitor answer is `flameshot screen --number <id> --edit` driven by hl.get_active_monitor(), with hl.window_rule pin and float. (4) The cause blamed X screen geometry. Flameshot 14 on Wayland goes through the portal, and the overlay is an ordinary toplevel the compositor places on one output, which is the real mechanism. Flameshot is not abandoned: extra 14.0.0-1, last updated 2026-06-11 per archlinux.org JSON. Both cited URLs still resolve and both are still relied on, so neither is removed. NOT exercised: I did not run omarchy-capture-screenshot, slurp, grim or flameshot, because every one of them takes over the operator's screen or writes a file, so the multi-monitor capture itself is argued from the scripts and the monitor geometry rather than from a capture I took.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not export `XDG_CURRENT_DESKTOP=sway` on Hyprland, on the command line or session wide. It selects which portal backend every request from that process reaches. Omarchy 4 ships `xdg-desktop-portal-hyprland` and does not install `xdg-desktop-portal-wlr`, so the setting points at a backend that does not exist. Set session wide it breaks screen sharing for every application, not only the screenshot tool.

**Fix.**

**On Omarchy 4 the fix is to stop working around the distribution.** Omarchy already
ships a multi-monitor-aware capture stack and already binds it. `PRINT` runs
`omarchy-capture-screenshot`, defined in
`/usr/share/omarchy/default/hypr/bindings/utilities.lua`, and `SUPER + CTRL + C` opens the
capture menu. `grim`, `slurp`, `wl-clipboard`, `hyprpicker` and `jq` are all installed
already, so there is nothing to add.

```bash
omarchy-capture-screenshot            # smart pick, saves to file and clipboard
omarchy-capture-screenshot region     # freeform, can cross a monitor boundary
omarchy-capture-screenshot fullscreen # the focused monitor, no interaction
omarchy-capture-screenshot region copy # clipboard only, no file
```

It is multi-monitor aware by construction. `omarchy-capture-region` reads
`hyprctl monitors -j` and divides `width` and `height` by `scale`, swapping them for
`transform` 1 and 3, so a scaled or rotated output produces the right rectangle. `slurp`
opens one selection layer per monitor, so a freeform drag can span outputs, and `grim -g`
composites the result.

Screenshots land in `$OMARCHY_SCREENSHOT_DIR`, else `$XDG_PICTURES_DIR`, else `~/Pictures`.
The editor is `$OMARCHY_SCREENSHOT_EDITOR`, default `tensaku-edit`.

To put it on a different key, override in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + S", "Screenshot", "omarchy-capture-screenshot")
```

**On plain Arch or another Hyprland install**, install the native Wayland tools and bind
them yourself.

```bash
sudo pacman -S --needed grim slurp wl-clipboard
```

Hyprland 0.55 and newer, Lua config (`~/.config/hypr/hyprland.lua`):

```lua
hl.bind("Print", hl.dsp.exec_cmd('grim -g "$(slurp -d)" - | wl-copy'))
```

Hyprland 0.54 and older, hyprlang config (`~/.config/hypr/hyprland.conf`):

```conf
bind = , Print, exec, grim -g "$(slurp -d)" - | wl-copy
bind = SHIFT, Print, exec, grim -g "$(slurp -d)" ~/Pictures/$(date +%Y-%m-%d_%H-%M-%S).png
```

To capture one whole output with no picker, name it. Read the connector names first:

```bash
hyprctl monitors all | grep '^Monitor'
```

On the machine this was checked on that prints `Monitor HDMI-A-1 (ID 0)` and
`Monitor vncpanel (ID 1)`, so:

```bash
grim -o HDMI-A-1 ~/Pictures/hdmi.png
```

**Alternative: keep Flameshot.** It is current in `extra` (14.0.0-1, updated 2026-06-11),
not abandoned. Upstream says it works on Hyprland with little configuration as long as
`xdg-desktop-portal-hyprland` is installed and running, which it is on Omarchy 4
(1.4.1-1). The multi-monitor answer is to capture one monitor at a time rather than the
whole desktop, using the current Lua API:

```lua
hl.bind("Print", function()
  local mon = hl.get_active_monitor()
  local n = mon and mon.id or 0
  hl.exec_cmd("flameshot screen --number " .. n .. " --edit")
end)

hl.window_rule({
  match    = { class = "flameshot" },
  no_anim  = true,
  pin      = true,
  float    = true,
  decorate = false,
  no_blur  = true,
  no_shadow = true,
})
hl.window_rule({
  match = { class = "flameshot", title = "flameshot" },
  move  = { 0, 0 },
})
```

If capture fails outright, the problem is the portal, not Flameshot. Check that exactly one
screenshot backend is running:

```bash
systemctl --user status xdg-desktop-portal-hyprland
busctl --user list | grep portal
```

**Do not set `XDG_CURRENT_DESKTOP=sway` on Hyprland.** That advice belongs to Sway and
river, where it is exported before the compositor starts so that
`xdg-desktop-portal-wlr` is selected. `xdg-desktop-portal-wlr` is not installed on
Omarchy 4, so forcing `sway` only points the portal at a backend that is not there.

**Verify.** On Omarchy 4, press `PRINT`, drag a region across the boundary between two monitors, and confirm the saved PNG in `~/Pictures` matches what you selected and that `wl-paste --list-types` prints `image/png`. On plain Arch, press the bind you added and run the same check. To confirm the stack sees the real layout, compare `hyprctl monitors all | grep '^Monitor'` against the geometry in the captured image.

Sources: <https://wiki.hypr.land/0.54.0/FAQ/> · <https://wiki.hypr.land/Useful-Utilities/Screenshots-and-Recording/> · <https://github.com/flameshot-org/flameshot/blob/master/docs/UsageHyprlandSwayWlroots.md> · <https://archlinux.org/packages/extra/x86_64/flameshot/> · <https://wiki.hypr.land/FAQ/>

---

## Fix screen recording producing nothing on a hybrid-GPU external monitor

`screen-recording-fails-hybrid-gpu-external-monitor` · severity: **medium** · frequency: **occasional** · applies to: `amd`, `hyprland`, `intel`, `laptop`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Screen recording does nothing on the external monitor of a hybrid-GPU laptop — pressing the record keybind produces no file, no notification, no error. With debug on you see: `gsr error: display "HDMI-A-1" not found, expected one of: "screen" "eDP-1"`.

**Cause.** gpu-screen-recorder's KMS backend attaches to one DRM card and only enumerates that card's connectors. On a hybrid laptop the internal panel is on the iGPU (e.g. `card2`) and the external monitor is on the dGPU (`card1`), so the external connector is invisible to the recorder. The portal backend is GPU-agnostic and does work, but Omarchy's `--fullscreen` code path is evaluated before the portal branch and ignores `OMARCHY_SCREENRECORD_USE_PORTAL`.

> **Audit corrected this record.** Outstanding sourcing everywhere except the last step. I confirmed the mechanism in Omarchy's own bin/omarchy-capture-screenrecording on the quattro branch: the `if [[ $FULLSCREEN == "true" ]]` branch is evaluated BEFORE the `elif [[ ${OMARCHY_SCREENRECORD_USE_PORTAL:-false} == "true" ]]` branch, exactly as the record claims, and both env vars are real and documented in that script's header. Issues 7184, 7530 and 7640 all exist with matching titles. gpu-screen-recorder's `-w portal`, `--list-capture-options` and `-fallback-cpu-encoding yes|no` are all genuine. But the Pascal advice contradicts its own cited source: omarchy#7640 is titled '-fallback-cpu-encoding yes doesn't catch NVENC API version mismatch' and its body shows omarchy-capture-screenrecording ALREADY passes that flag while recording still fails hard at avcodec_open2; the issue's stated workaround is forcing `-encoder cpu` explicitly. So the record hands a Pascal user the exact flag its source proves does not work.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Confirm the split:

```bash
ls /sys/class/drm/card*-*/status
gpu-screen-recorder --list-capture-options
```

If your external connector is on a different card number than the one listed, that is this bug.

Work around it by recording through the portal instead of KMS — do not use the `--fullscreen` path, which is evaluated before the portal branch and ignores the variable:

```bash
OMARCHY_SCREENRECORD_USE_PORTAL=true omarchy-capture-screenrecording
```

Or call gpu-screen-recorder directly with the portal capture target:

```bash
gpu-screen-recorder -w portal -f 60 -o ~/Videos/recording.mp4
```

To see why a silent failure happened:

```bash
OMARCHY_SCREENRECORD_DEBUG=true omarchy-capture-screenrecording --fullscreen
```

On Pascal-era NVIDIA cards, do NOT rely on `-fallback-cpu-encoding yes` — omarchy#7640 shows that flag only guards encoder *detection* and does not catch the later `avcodec_open2` failure (`[h264_nvenc] Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0`), so recording still dies. Force software encoding explicitly instead:

```bash
gpu-screen-recorder -w portal -encoder cpu -o ~/Videos/recording.mp4
```

That is the workaround confirmed in the issue. The 13.0 NVENC ceiling is permanent on Pascal — driver branch 580.xx is the last one for that hardware — so no future driver update will restore GPU encoding there.

**Verify.** A file appears in `~/Videos` with real content, and `gpu-screen-recorder --list-capture-options` output no longer needs to contain your external connector for the recording to work (the portal target replaces it).

Sources: <https://github.com/basecamp/omarchy/issues/7184> · <https://github.com/basecamp/omarchy/issues/7530> · <https://github.com/basecamp/omarchy/issues/7640>

---

## GTK4/libadwaita apps stay blinding white while everything else is dark

`gtk4-libadwaita-apps-stuck-in-light-theme` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Nautilus, GNOME Text Editor, Loupe, Fractal and other GTK4/libadwaita apps launch in bright white while my whole desktop is dark. Putting `gtk-application-prefer-dark-theme=1` in `~/.config/gtk-4.0/settings.ini` does nothing. `GTK_THEME=Adwaita:dark` only half-works — the headerbar is dark but the content is not.

**Cause.** libadwaita does not read GTK theme files for light/dark, and `gtk-application-prefer-dark-theme` is a GTK3 key it ignores entirely. It asks the `org.freedesktop.impl.portal.Settings` portal for `org.freedesktop.appearance / color-scheme` and renders light for anything other than `prefer-dark`. xdg-desktop-portal-hyprland genuinely does not implement Settings — `/usr/share/xdg-desktop-portal/portals/hyprland.portal` declares only `Screenshot;ScreenCast;GlobalShortcuts;InputCapture` — but on its own that breaks nothing, because Hyprland ships `/usr/share/xdg-desktop-portal/hyprland-portals.conf` containing `default=hyprland;gtk`, so xdg-desktop-portal falls through to xdg-desktop-portal-gtk for Settings, and Omarchy installs that package in its base set. So on a stock Omarchy the portal chain already works and the actual cause is that `org.gnome.desktop.interface color-scheme` is still at its schema default of `'default'` (no preference). Omarchy sets it to `prefer-dark` at first run via `/usr/share/omarchy/install/user/first-run/gnome-theme.sh`, so this appears when that script never ran, when dconf was reset, or on a non-Omarchy Hyprland install where `xdg-desktop-portal-gtk` is simply not installed and nothing serves Settings at all.

> **Audit corrected this record.** Real problem, and the second half of the fix is right, but the cause's conclusion is disproven on the exact platform this corpus targets, and two specifics are fabricated. (a) The claim "With no backend serving Settings, the portal returns nothing" is false on a stock Hyprland/Omarchy install. Hyprland itself ships /usr/share/xdg-desktop-portal/hyprland-portals.conf containing `[preferred]` / `default=hyprland;gtk` (owned by package hyprland 0.56.2-1), so xdg-desktop-portal falls through to xdg-desktop-portal-gtk for any interface hyprland does not implement — including Settings — and Omarchy lists xdg-desktop-portal-gtk in /usr/share/omarchy/install/omarchy-base.packages. I verified this live on this machine, which has NO ~/.config/xdg-desktop-portal directory at all: `busctl --user call ... org.freedesktop.portal.Settings Read ss "org.freedesktop.appearance" "color-scheme"` answers correctly. So step 3 of the fix — creating a user hyprland-portals.conf — is unnecessary on a stock system, and it is the step the record's own `danger` field says can silently break FileChooser and ScreenCast. Telling every reader to write that file is the riskiest part of the record and it is usually not needed. (b) The enumeration of what xdg-desktop-portal-hyprland provides is wrong. /usr/share/xdg-desktop-portal/portals/hyprland.portal lists Screenshot;ScreenCast;GlobalShortcuts;InputCapture — there is no RemoteDesktop, and Screenshot is omitted. The true part (no Settings interface) is confirmed by that same file. (c) The verify's expected output is wrong: the real answer is `v v u 1`, a nested variant, not `v u 1`. (d) Correct-as-written: `gtk-application-prefer-dark-theme` is a GTK3 key that libadwaita ignores; xdg-desktop-portal-gtk is the Settings provider (ArchWiki Dark mode switching: "To query gsettings configuration, GTK requires the Settings XDG Desktop Portal, provided by xdg-desktop-portal-gtk, to be running"); `color-scheme 'prefer-dark'` is the right key/value (ArchWiki Dark mode switching); XDG_CURRENT_DESKTOP is Hyprland on Omarchy (set in /usr/share/omarchy/default/hypr/envs.lua) and portals.conf(5) confirms the filename is that value ASCII-lowercased, i.e. hyprland-portals.conf; all three systemd user units named exist. The real cause is simply that org.gnome.desktop.interface color-scheme sits at its schema default `'default'` (= no preference), which libadwaita renders light — Omarchy sets it at first run in /usr/share/omarchy/install/user/first-run/gnome-theme.sh, so this only bites when that never ran, dconf was reset, or xdg-desktop-portal-gtk is absent on a non-Omarchy Hyprland box.
>
> *The Cause above was rewritten on 2026-09-01 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A malformed `hyprland-portals.conf` — a typo in an interface name, or pointing an interface at a backend that does not implement it — silently breaks whatever it names. Getting `org.freedesktop.impl.portal.ScreenCast` or `FileChooser` wrong will kill screen sharing or every file-open dialog. Keep `default = hyprland;gtk` and only add specific overrides you have verified with the `busctl` call above.

**Fix.**

**1. Ask the portal what it currently answers, before changing anything.** The reply is a nested variant, `v v u N`, where 0 = no preference, 1 = prefer-dark, 2 = prefer-light:

```bash
busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop \
  org.freedesktop.portal.Settings Read ss "org.freedesktop.appearance" "color-scheme"
```

- Answers `v v u 0` → the portal works, you just have no preference set. Skip to step 3.
- Answers `v v u 1` → the portal already says dark; your problem is elsewhere (a GTK theme with no dark variant, or `GTK_THEME` forced in the environment — check `systemctl --user show-environment | grep GTK`).
- Errors, or reports no such backend → do step 2.

**2. Only if step 1 found no Settings backend: install one.** Hyprland does not implement the Settings portal, but it ships a fall-through to gtk, so installing the gtk backend is normally all that is required. On Omarchy it is already in the base package set:

```bash
sudo pacman -S --needed xdg-desktop-portal-gtk
cat /usr/share/xdg-desktop-portal/hyprland-portals.conf   # expect: [preferred] / default=hyprland;gtk
```

**3. Set the preference.** This is the actual fix in the common case:

```bash
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'
```

Without gsettings schemas available:

```bash
dconf write /org/gnome/desktop/interface/color-scheme "'prefer-dark'"
```

On Omarchy you can simply re-run the first-run script that does exactly this:

```bash
bash /usr/share/omarchy/install/user/first-run/gnome-theme.sh
```

**4. Restart the portal stack, then the apps.**

```bash
systemctl --user restart xdg-desktop-portal-gtk xdg-desktop-portal-hyprland xdg-desktop-portal
```

libadwaita queries the portal at startup and then follows live changes, but an app started before any backend existed never got a first answer — so restart the affected apps once.

**5. Pin the backend explicitly only if steps 1–4 did not fix it.** A user file at this path *shadows Hyprland's shipped one*, so you take over responsibility for every interface it names. `XDG_CURRENT_DESKTOP` is `Hyprland` on Omarchy and `portals.conf(5)` says the filename is that value with ASCII upper case folded to lower, hence `hyprland-portals.conf`:

```ini
# ~/.config/xdg-desktop-portal/hyprland-portals.conf
[preferred]
default = hyprland;gtk
org.freedesktop.impl.portal.Settings = gtk
```

Keep `default = hyprland;gtk` and add nothing you have not verified with the `busctl` call in step 1. Do **not** add `org.freedesktop.impl.portal.FileChooser` or `ScreenCast` overrides speculatively — pointing either at a backend that does not implement it kills every file dialog or all screen sharing, silently. Delete the file to go back to the shipped default.

To flip back to light: `gsettings set org.gnome.desktop.interface color-scheme 'prefer-light'`.

**Verify.** Ask the portal directly — it should answer `v u 1` (1 = prefer-dark, 2 = prefer-light, 0 = no preference):

```bash
busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop \
  org.freedesktop.portal.Settings Read ss "org.freedesktop.appearance" "color-scheme"
```

Then open Nautilus or GNOME Text Editor — it should be dark, and should follow a live `gsettings set ... color-scheme` change without restarting.

Sources: <https://wiki.archlinux.org/title/Dark_mode_switching> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://github.com/CachyOS/cachyos-niri-noctalia/issues/4> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/>

---

## Cursor reverts to the ugly X11 arrow (or vanishes) inside Steam, games and Java apps

`xwayland-apps-wrong-cursor-theme` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** The desktop has my chosen cursor, but the instant the pointer crosses into Steam, a Proton game, GIMP, or a Java tool (Ghidra, JetBrains, Burp) it turns into the plain black X11 arrow — or a huge white one, or nothing at all. Setting `XCURSOR_THEME` in my Hyprland config changed nothing. On a fresh install the cursor is the Hyprland logo.

**Cause.** Hyprland draws a server-side cursor for Wayland-native clients using hyprcursor (falling back to XCursor). XWayland clients draw their own client-side cursor through libXcursor, which resolves the theme name from `XCURSOR_THEME` *in the process's own environment* and, failing that, from the `Inherits=` line of the "default" theme — `~/.local/share/icons/default/index.theme`, then `~/.icons/default/index.theme`, then `/usr/share/icons/default/index.theme`. That last file is owned by the `default-cursors` package (a dependency of `libxcursor` and `wayland`, so it is always installed) and ships `Inherits=Adwaita`, which is why an unconfigured system usually lands on Adwaita rather than nothing. Env vars set with `hl.env()` only reach processes Hyprland launches after that line — Steam relaunched by its own updater, a game started by the Steam client, or anything started by a systemd user unit never sees them; and under uwsm, session-wide variables belong in `~/.config/uwsm/env` rather than in `hyprland.lua` at all. The Hyprland-logo cursor is the separate case where no cursor theme resolves at all: hyprcursor is the format/library, not a theme.

> **Audit corrected this record.** Most of this record holds up. The `~/.icons/default/index.theme` + `Inherits=` mechanism is documented verbatim at https://wiki.archlinux.org/title/Cursor_themes ("The default cursor theme is in the usual theme locations: ~/.local/share/icons/default/, ~/.icons/default/, /usr/share/icons/default/" and the Inheritance subsection). `adwaita-cursors` 50.0-1 exists in extra and ships `usr/share/icons/Adwaita/cursors/`. The gsettings and dconf commands are lifted from the hyprcursor wiki page, `cursor:sync_gsettings_theme` really does default to `true` and `cursor:enable_hyprcursor` to `true` (config-options.md), and the FAQ confirms "My cursor is a Hyprland icon? This means you have no hyprcursor theme installed, and Hyprland failed to find an XCursor theme as well." I also checked whether `hyprctl setcursor Adwaita 24` would fail on an XCursor-only theme, since the wiki still claims "since 0.37.0, this only accepts hyprcursor themes" — it does not fail: CCursorManager::changeTheme() in src/pointer/cursor/CursorManager.cpp logs "Hyprcursor failed loading theme, falling back to XCursor" and calls `m_xcursor->loadTheme(name, ...)`, so step 5 is fine as written. Two things are wrong. (1) The danger note attributes /usr/share/icons/default/index.theme to "adwaita-cursors, xcursor-themes or your theme package". It is owned by neither: `pacman -Qo /usr/share/icons/default/index.theme` on this Omarchy 4 box returns `default-cursors 3-1`, and the Arch file lists confirm adwaita-cursors ships only usr/share/icons/Adwaita/ while xcursor-themes ships only handhelds/redglass/whiteglass. `default-cursors` is a dependency of both `libxcursor` and `wayland`, so it is present on every install, and its index.theme already reads `Inherits=Adwaita` — which is useful context the record omits: the fallback chain is not empty on a stock system, so this record really applies to someone wanting a *different* theme. The warning itself (don't edit it, use ~/.icons) is correct; only the attribution is fabricated. (2) Step 4 puts `HYPRCURSOR_THEME`/`HYPRCURSOR_SIZE` in `~/.config/uwsm/env`, but the uwsm page it cites says the opposite: "use ~/.config/uwsm/env for theming, XCursor, NVIDIA and toolkit variables, and ~/.config/uwsm/env-hyprland for HYPR* and AQ_* variables." Also worth stating: Omarchy 4 already sets XCURSOR_SIZE and HYPRCURSOR_SIZE to 24 in /usr/share/omarchy/default/hypr/envs.lua, which is pacman-owned and must not be edited.
>
> *The Cause above was rewritten on 2026-09-01 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not edit `/usr/share/icons/default/index.theme` — that file is owned by a package (`adwaita-cursors`, `xcursor-themes` or your theme package) and pacman will silently revert your change on the next upgrade, or leave a `.pacnew` you never notice. Always use `~/.icons/default/index.theme`, which nothing owns.

**Fix.**

1. Install a real cursor theme and note its **directory** name (that is the name you use everywhere, not the pretty name):

```bash
sudo pacman -S --needed adwaita-cursors    # or an AUR theme such as bibata-cursor-theme
ls /usr/share/icons ~/.local/share/icons ~/.icons 2>/dev/null
```

Note that `default-cursors` is already installed on every Arch/Omarchy system — it is a dependency of `libxcursor` and `wayland` — and it ships `/usr/share/icons/default/index.theme` containing `Inherits=Adwaita`. So the XCursor fallback chain is normally *not* empty. If you are seeing the Hyprland-logo cursor, that package or the Adwaita cursors are genuinely missing; if you are seeing plain black X11 arrows, the chain is resolving to something you did not choose and the rest of this fix redirects it.

2. Set the libXcursor fallback so XWayland clients find your theme with no environment at all. Use the **user** path, which takes precedence over the system one:

```bash
mkdir -p ~/.icons/default
cat > ~/.icons/default/index.theme <<'EOF'
[Icon Theme]
Inherits=Adwaita
EOF
```

(Substitute your theme's directory name for `Adwaita`.)

3. Set it for GTK/CSD clients through gsettings (Hyprland's `cursor:sync_gsettings_theme` is `true` by default and will keep these in step):

```bash
gsettings set org.gnome.desktop.interface cursor-theme 'Adwaita'
gsettings set org.gnome.desktop.interface cursor-size 24
```

If gsettings schemas are unavailable: `dconf write /org/gnome/desktop/interface/cursor-theme "'Adwaita'"`

4. Set it for the compositor and for anything it launches. Omarchy 4 runs the session under uwsm, and the Hyprland wiki explicitly says uwsm users should not put theming/xcursor vars in `hyprland.lua`. It also splits them across two files — XCursor and toolkit vars in `~/.config/uwsm/env`, `HYPR*` vars in `~/.config/uwsm/env-hyprland`:

```sh
# ~/.config/uwsm/env
export XCURSOR_THEME=Adwaita
export XCURSOR_SIZE=24
```

```sh
# ~/.config/uwsm/env-hyprland
export HYPRCURSOR_THEME=Adwaita
export HYPRCURSOR_SIZE=24
```

Omarchy also sources `~/.config/uwsm/env.d/*`, which is the tidier place if you keep several drop-ins. Do **not** edit `/usr/share/omarchy/default/hypr/envs.lua`, which already sets `XCURSOR_SIZE` and `HYPRCURSOR_SIZE` to 24 — it is pacman-owned and your change would be reverted on the next `omarchy update`.

On a non-uwsm session the equivalent is in `~/.config/hypr/hyprland.lua`:

```lua
hl.env("XCURSOR_THEME", "Adwaita")
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_THEME", "Adwaita")
hl.env("HYPRCURSOR_SIZE", "24")
```

5. Apply to the running session without logging out:

```bash
hyprctl setcursor Adwaita 24
```

The wiki still says `setcursor` takes hyprcursor themes only; that is stale — Hyprland falls back to loading the same name as an XCursor theme if no hyprcursor theme matches. Add the call to your autostart so it survives a restart:

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("hyprctl setcursor Adwaita 24")
end)
```

This only affects server-side cursors, so it fixes Wayland-native clients immediately; XWayland clients still need steps 2 and 4.

6. Log out and back in, then relaunch Steam/the game so it inherits the new environment.

If a theme ships only one bitmap size, XWayland may still scale it up into a giant arrow — that is a property of the theme, not your config. Themes that ship 24/32/48 variants (Adwaita, Bibata) do not have this problem.

**Verify.** `hyprctl getoption cursor:enable_hyprcursor` and hover over an XWayland window — `hyprctl clients | grep -B2 -A6 xwayland` confirms which clients are on the X side. Launch `xterm` or `xeyes` and check the cursor matches the desktop. `echo $XCURSOR_THEME` inside a terminal started from the launcher (not from an old shell) should print your theme.

Sources: <https://wiki.hypr.land/Hypr-Ecosystem/hyprcursor/> · <https://wiki.hypr.land/FAQ/> · <https://github.com/hyprwm/Hyprland/discussions/8196> · <https://bbs.archlinux.org/viewtopic.php?id=311943> · <https://wiki.archlinux.org/title/Cursor_themes> · <https://wiki.hypr.land/Configuring/Basics/Variables/>

---

## Flatpak apps run under XWayland: blurry, wrongly scaled, deaf to session env vars

`flatpak-app-silently-runs-under-xwayland` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** My Flatpak Obsidian / Spotify / VS Code is noticeably blurry next to everything else, ignores my display scale, and `hyprctl clients` shows `xwayland: 1` for it. The exact same app installed from pacman is crisp. Setting the variable in `~/.config/uwsm/env` or with `hl.env()` makes no difference to the Flatpak.

**Cause.** A Flatpak's window ends up on XWayland because the app inside the sandbox never positively selected the Wayland backend: most manifests grant both `--socket=wayland` and `--socket=fallback-x11`, and the X11 fallback is taken silently, with no error and no log line. It is *not* the case that the sandbox gets none of your session environment — `flatpak run` starts from the host environment (`flatpak_bwrap_new(NULL)` falls through to `g_get_environ()` in `common/flatpak-bwrap.c`) and then overrides only the fixed `default_exports[]` list in `common/flatpak-run.c`. Of the variables that matter here, exactly one is on that list: **`GDK_BACKEND` is unset unconditionally**, which is why a GTK app in a Flatpak ignores the value you set in `~/.config/uwsm/env` or with `hl.env()`. `ELECTRON_OZONE_PLATFORM_HINT`, `QT_QPA_PLATFORM` and `MOZ_ENABLE_WAYLAND` are *not* stripped and do reach the sandbox — so if those are not taking effect, they are missing from the environment the launcher itself inherited (D-Bus/systemd activation), not being filtered out by Flatpak.

> **Audit corrected this record.** The symptom, the severity and every command in the fix are correct — but the cause is factually wrong in a way that would mislead someone diagnosing the same class of problem, so it cannot stand. The record asserts that ELECTRON_OZONE_PLATFORM_HINT, GDK_BACKEND, QT_QPA_PLATFORM and MOZ_ENABLE_WAYLAND "are not passed into the sandbox". Flatpak inherits the host environment by default: `flatpak_run_app()` in common/flatpak-run.c calls `flatpak_bwrap_new(NULL)`, and common/flatpak-bwrap.c does `bwrap->envp = g_get_environ()` when passed NULL. What Flatpak then does is override a fixed list, `default_exports[]` in common/flatpak-run.c. Of the four variables the record names, exactly one is on that list: `{"GDK_BACKEND", NULL}` — unset unconditionally, alongside XCURSOR_PATH, PYTHONPATH, the GST_* family and the VK_* family. ELECTRON_OZONE_PLATFORM_HINT, QT_QPA_PLATFORM and MOZ_ENABLE_WAYLAND are not stripped and do reach the sandbox. So the record is right about GTK apps and wrong about the other three, and it points a reader away from the real failure (the variable never reaching the launcher's environment in the first place — systemd/D-Bus activation) toward a sandbox filter that does not exist for those variables. Everything else verified: all flatpak flags used are real, checked against doc/flatpak-override.xml upstream (--user, --show, --socket, --nosocket, --env, --reset are all documented options); `flatpak info --show-permissions` and `flatpak kill` are real; `--socket=fallback-x11` is a real socket name so `--nosocket=fallback-x11` is a valid diagnostic and the danger note about it is correct; `com.github.tchx84.Flatseal` is the right Flathub app id (and `flatseal` 2.4.1-1 is in Arch `extra`, which is the simpler route on Omarchy); the `hyprctl clients` / `xwayland: 0` verify is accurate against Hyprland v0.56.2's HyprCtl.cpp; ArchWiki Flatpak confirms `flatpak override` and `flatpak override --reset name` and uses the same `-u override --env=` pattern for the analogous XCURSOR_PATH problem. No pacman -Sy, no rm -rf, no Omarchy 3 assumptions.
>
> *The Cause above was rewritten on 2026-09-01 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `--nosocket=fallback-x11` (or `--nosocket=x11`) will stop an app from starting at all if any part of it genuinely needs X11 — some Electron apps still spawn X11 helper processes. Use it as a diagnostic and reset it afterwards with `flatpak override --user --reset <app-id>`.

**Fix.**

**1. Look at what the sandbox actually receives, rather than guessing.**

```bash
flatpak info --show-permissions md.obsidian.Obsidian
flatpak override --user --show md.obsidian.Obsidian
flatpak run --command=env md.obsidian.Obsidian \
  | grep -E 'GDK_BACKEND|ELECTRON_OZONE|QT_QPA_PLATFORM|MOZ_ENABLE_WAYLAND|WAYLAND_DISPLAY'
```

Read the result this way:

- `GDK_BACKEND` will be **absent no matter what you set on the host** — Flatpak unsets it unconditionally. That is expected, and it is why GTK apps in a Flatpak ignore your session setting.
- `ELECTRON_OZONE_PLATFORM_HINT`, `QT_QPA_PLATFORM` and `MOZ_ENABLE_WAYLAND` *are* inherited. If they are missing here, fix the host side first — the launcher did not have them either:

```bash
systemctl --user show-environment | grep -E 'ELECTRON_OZONE|QT_QPA_PLATFORM|MOZ_ENABLE_WAYLAND'
```

- `WAYLAND_DISPLAY` missing means the sandbox has no Wayland socket at all; go straight to the `--socket=wayland` override below.

**2. Set the backend inside the sandbox.** For Electron/Chromium apps:

```bash
flatpak override --user --socket=wayland \
  --env=ELECTRON_OZONE_PLATFORM_HINT=wayland \
  md.obsidian.Obsidian
```

For GTK apps — this one is genuinely required, since the host value never survives:

```bash
flatpak override --user --socket=wayland --env=GDK_BACKEND=wayland <app-id>
```

For Qt apps:

```bash
flatpak override --user --socket=wayland --env=QT_QPA_PLATFORM=wayland <app-id>
```

For Firefox:

```bash
flatpak override --user --socket=wayland --env=MOZ_ENABLE_WAYLAND=1 org.mozilla.firefox
```

To apply a default to every Flatpak, omit the app id:

```bash
flatpak override --user --socket=wayland --env=GDK_BACKEND=wayland
```

Restart the app (`flatpak kill md.obsidian.Obsidian` first if it lingers) and re-check.

**3. To prove an app really can run without X11**, temporarily remove the fallback so it fails loudly instead of falling back silently:

```bash
flatpak override --user --nosocket=fallback-x11 md.obsidian.Obsidian
```

**4. Undo everything for one app:**

```bash
flatpak override --user --reset md.obsidian.Obsidian
```

**5. A GUI for all of the above** is Flatseal. On Arch/Omarchy it is in the official repos, which is simpler than installing it as a Flatpak:

```bash
sudo pacman -S --needed flatseal
# or, from Flathub:
flatpak install flathub com.github.tchx84.Flatseal
```

**Verify.** `hyprctl clients | grep -A8 <class>` reports `xwayland: 0` for the Flatpak window, and the window is sharp at your display scale. `flatpak override --user --show <app-id>` lists the env entries you set.

Sources: <https://wiki.archlinux.org/title/Flatpak> · <https://wiki.archlinux.org/title/Wayland> · <https://wiki.archlinux.org/title/Electron> · <https://docs.flatpak.org/en/latest/desktop-integration.html>

---

## Middle-click paste of the primary selection stopped working in GTK apps

`middle-click-primary-paste-stopped-working` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Middle-click paste no longer works. I select text, middle-click somewhere else, and nothing happens — in GNOME Text Editor, Ghostty, gedit, Nautilus's rename field, gVim, GTK apps generally. It still works in Firefox and in some terminals. I changed nothing; it just stopped after an update.

**Cause.** Three separate layers can each swallow a middle-click paste, and the record has to tell them apart. (1) **GTK.** GTK gates middle-click paste on `org.gnome.desktop.interface gtk-enable-primary-paste`, which ships in `gsettings-desktop-schemas` and is read by GTK on every desktop, not only GNOME. Upstream flipped that key's default from `true` to `false`, so every GTK application that honours it went silent at once. The shipped schema on Omarchy 4 confirms it: `/usr/share/glib-2.0/schemas/org.gnome.desktop.interface.gschema.xml` carries `<default>false</default>` for that key. Firefox and a few other applications implement middle-click paste themselves and ignore the setting, which is why they still work, and that split is the giveaway. (2) **The compositor.** Hyprland has its own `misc:middle_click_paste`, default `true`. Set to `false` it disables the feature for every client, and no gsettings change will bring it back. (3) **The application toolkit.** An application can simply not implement it. Ghostty is the current example: the primary selection is populated and Firefox pastes it, but Ghostty does not. A fourth behaviour compounds all of these rather than causing them: on Wayland the primary selection is owned by the source window, so it disappears when that window closes.

On Omarchy 4 specifically the key should already be `true`. `/usr/share/omarchy/install/user/first-run/gtk-primary-paste.sh` is one line, `gsettings set org.gnome.desktop.interface gtk-enable-primary-paste true`, so Omarchy treats the upstream default as a defect and corrects it on first run. If it is `false` on an Omarchy box, the first-run step did not complete, a different user account never ran it, or something reset the dconf value.

> **Audit corrected this record.** Re-checked the whole record on this Omarchy 4 workstation (omarchy 4.0.2-1, Hyprland 0.56.2) and against the cited pages. The core claim holds and I confirmed it here rather than accepting the prior note: the shipped /usr/share/glib-2.0/schemas/org.gnome.desktop.interface.gschema.xml carries `<default>false</default>` for gtk-enable-primary-paste, /usr/share/omarchy/install/user/first-run/gtk-primary-paste.sh exists and is exactly the one gsettings line, and the live value on this machine is `true`. wl-clip-persist is in extra at 0.5.0-2 (archlinux.org JSON), so the pacman line resolves. The danger is source accurate: hyprland-wiki content/useful-utilities/clipboard-managers.md line 197 says the primary mode is not recommended and links Linus789/wl-clip-persist#3. The cited Ghostty discussion 12181 is real (HTTP 200) and its body matches the record, including that wl-paste --primary works while Ghostty does not paste. Two defects. (1) The record blames one layer and never mentions the compositor. Hyprland has misc:middle_click_paste, documented under 'How to disable middle-click paste?' in the 0.54 FAQ, and confirmed live here: `hyprctl getoption misc:middle_click_paste` returns `bool: true, set: false`, so it is default on and Omarchy does not touch it (no hit for the string anywhere under /usr/share/omarchy). If a user has set it false, every step in the old fix is wasted effort. The fix is rewritten as an ordered walk down compositor, then selection source, then GTK setting, then the application itself. (2) The autostart line was put in ~/.config/hypr/hyprland.lua. Omarchy ships ~/.config/hypr/autostart.lua for exactly this, with an o.launch_on_start helper defined at /usr/share/omarchy/default/hypr/helpers.lua:118, and the raw hl.on idiom is kept as the labelled non-Omarchy branch. I also read /usr/share/omarchy/bin/omarchy-refresh-hyprland and omarchy-refresh-config: they overwrite those user files with the defaults and save a .bak.<epoch>, which is visible as nine such files in this user's ~/.config/hypr. No migration under /usr/share/omarchy/migrations calls refresh-config on a hypr file, so omarchy update does not wipe the edit, and that distinction is now in the fix. NOT exercised: I changed no setting and started no process, so the wl-clip-persist autostart and the re-run of the first-run script are argued from reading the scripts, not from running them.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not run `wl-clip-persist --clipboard primary`. Upstream documents that primary-selection mode breaks the selection system in some GTK applications — text selection itself stops behaving correctly. Use `--clipboard regular` only.

**Fix.**

Work down the layers. Stop at the first one that is wrong.

**1. Is the compositor still passing middle-click paste through?**

```bash
hyprctl getoption misc:middle_click_paste
```

`bool: true` is correct. `bool: false` means the failure is compositor wide and nothing else in
this record applies. Remove the `misc.middle_click_paste = false` line from your Hyprland
config. On Omarchy 4 that line is never shipped, so it would be your own.

**2. Is the primary selection actually being populated?**

Select some text in any window, then:

```bash
wl-paste --primary
```

If that prints nothing, the source application is not exporting a primary selection at all,
which is a different problem from the paste side.

**3. Is the GTK setting on?**

```bash
gsettings get org.gnome.desktop.interface gtk-enable-primary-paste
gsettings set org.gnome.desktop.interface gtk-enable-primary-paste true
```

If gsettings schemas are not available, write the key directly:

```bash
dconf write /org/gnome/desktop/interface/gtk-enable-primary-paste true
```

On Omarchy 4 the shipped first-run script does exactly this, so re-running it is the supported
way back:

```bash
bash /usr/share/omarchy/install/user/first-run/gtk-primary-paste.sh
```

The setting is read once at application startup. Fully quit and reopen the application. Some
users need a full re-login.

**4. Still only one application broken?**

If step 3 returns `true`, `wl-paste --primary` prints the selection, and Firefox pastes it but
one specific application does not, the application does not implement middle-click paste. That
is upstream's bug, not a system setting. Ghostty is the current example.

**Optional: keep the selection alive after the source window closes.**

```bash
sudo pacman -S --needed wl-clip-persist
```

Put the autostart line in `~/.config/hypr/autostart.lua`, which is the user file Omarchy ships
for this and which loads after Omarchy's own defaults:

```lua
-- ~/.config/hypr/autostart.lua
o.launch_on_start("wl-clip-persist --clipboard regular")
```

On plain Arch or another Hyprland install with no Omarchy helpers, use the raw Hyprland idiom
in `~/.config/hypr/hyprland.lua`:

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("wl-clip-persist --clipboard regular")
end)
```

One thing to know before you edit any of these files. `omarchy-refresh-hyprland` overwrites
`~/.config/hypr/hyprland.lua`, `bindings.lua`, `autostart.lua`, `input.lua`, `looknfeel.lua`
and `monitors.lua` with the shipped defaults, saving yours as `<file>.bak.<epoch>`. No current
migration runs it for those files, so a plain `omarchy update` leaves your edit alone, but if
you ever run that command yourself your line is in the backup, not in the live file.

**Verify.** `hyprctl getoption misc:middle_click_paste` prints `bool: true`. `gsettings get org.gnome.desktop.interface gtk-enable-primary-paste` returns `true`. Select text in one GTK window and middle-click into another, and the text pastes. `wl-paste --primary` prints the current selection.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=313089> · <https://github.com/ghostty-org/ghostty/discussions/12181> · <https://wiki.archlinux.org/title/Clipboard> · <https://wiki.hypr.land/Useful-Utilities/Clipboard-Managers/> · <https://wiki.hypr.land/0.54.0/FAQ/> · <https://github.com/Linus789/wl-clip-persist#primary-selection-mode-breaks-the-selection-system-3> · <https://archlinux.org/packages/extra/x86_64/wl-clip-persist/>

---

## OBS virtual camera missing, or Zoom/Meet/Teams never lists it

`obs-virtual-camera-not-listed-v4l2loopback` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** OBS has no "Start Virtual Camera" button, or it starts without error but Zoom, Google Meet, Teams and Discord never show "OBS Virtual Camera" in the camera dropdown — only my real webcam. `ls /dev/video*` shows only the webcam devices.

**Cause.** OBS's virtual camera on Linux writes into a `v4l2loopback` device, which is an out-of-tree kernel module that must be built and loaded. Without it there is no device node and OBS hides the button. When the module is loaded without `exclusive_caps=1` the device advertises both OUTPUT and CAPTURE capabilities at once; Chromium-based clients (Meet, Teams, Zoom, Discord, Slack) refuse to enumerate such a device, so it exists but is invisible to exactly the apps you want it in.

> **Audit corrected this record.** Re-checked on this Omarchy 4.0.2-1 workstation (obs-studio 32.2.2-1, kernel 7.1.9-arch1-2, linux-headers 7.1.9.arch1-2, dkms 3.4.3-2, v4l-utils 1.32.0-2) and against upstream. The core claim holds and OBS 32 has NOT replaced v4l2loopback: `strings /usr/lib/obs-plugins/linux-v4l2.so` still carries `modinfo v4l2loopback`, `v4l2loopback not installed, virtual camera not registered` and the literal autoload line `pkexec modprobe v4l2loopback exclusive_caps=1 card_label='OBS Virtual Camera' && sleep 0.5`, while `linux-pipewire.so` is an input path only (`pipewire-camera-source`, `org.freedesktop.portal.Camera`), so the PipeWire work in OBS is capture, not virtual camera output. Arch still lists `v4l2loopback-dkms: virtual camera support` as an obs-studio optdepend (package JSON fetched today). `exclusive_caps=1` is still required: upstream `v4l2loopback.c` line 166 defines `V4L2LOOPBACK_DEFAULT_EXCLUSIVECAPS 0`, so the default has not flipped, and the ArchWiki V4l2loopback page fetched today gives the same modprobe line and the same try-it-both-ways tip the record ends on. Four corrections. First, the fix used `sudo pacman -S` with no Omarchy branch. I confirmed by reading `/usr/share/omarchy/bin/omarchy-update-pacman-guard` that the guard fires only when both a sync flag and a sysupgrade flag are present, so a plain install is not blocked, and added the native `omarchy pkg add` form, which `/usr/share/omarchy/bin/omarchy-pkg-add` implements as `pacman -S --noconfirm --needed`. Second, the record hardcodes `/dev/video9` in step 5 and in `verify`, but OBS's own autoload passes no `video_nr`, so a reader who lets OBS load the module gets a different node and concludes the fix failed. Third, `v4l2loopback-utils` 0.15.4-2 exists in extra and provides `v4l2loopback-ctl` for dynamic add and delete, which the record never mentions. Fourth, the `danger` said the DKMS build "fails silently during the pacman transaction", which is right in effect but not in mechanism, so I named the actual hooks and the Omarchy specific reason it is easy to miss. The cited Arch package URL used the `x86_64` path, but the package is `any` on both `v4l2loopback-dkms` and `v4l2loopback-utils`, so the old URL only 301 redirects while `https://archlinux.org/packages/extra/any/v4l2loopback-dkms/` returns 200. Replaced it. Kept `symptom`, `severity` low and `frequency` common. NOT exercised: `v4l2loopback-dkms` is not installed here and there is no `/dev/video*` on this machine, so no module was built, loaded or probed, and no camera enumeration was tested in any browser or conferencing client. Installing and loading a kernel module is outside what an audit may do on the operator's workstation.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** v4l2loopback is DKMS built, so it has to be recompiled for every new kernel. The rebuild is driven by the pacman hooks `70-dkms-upgrade.hook` and `70-dkms-install.hook`, which call `/usr/share/libalpm/scripts/dkms`. That script prints a warning line and returns, it does not abort the transaction, so a failed build does not fail the upgrade. On Omarchy the risk is worse than on plain Arch because `omarchy update` funnels the whole pacman run through an update transcript, so one warning line is easy to miss, and the only visible symptom afterwards is that OBS's Start Virtual Camera button has quietly disappeared. If `linux-headers` is not upgraded alongside `linux`, the build has nothing to compile against. After any kernel upgrade run `sudo dkms status` and, if needed, `sudo dkms autoinstall` then reboot. Do not `modprobe -r` while OBS or a call is holding the device: the removal will fail or wedge the app.

**Fix.**

1. Install the module sources and the headers for the kernel you are actually running:

```bash
uname -r
pacman -Q linux linux-headers      # these two versions must match
```

On Omarchy 4 use the wrapper, which is `pacman -S --noconfirm --needed` underneath:

```bash
omarchy pkg add v4l2loopback-dkms linux-headers v4l2loopback-utils
```

On plain Arch:

```bash
sudo pacman -S --needed v4l2loopback-dkms linux-headers v4l2loopback-utils
```

Use `linux-lts-headers`, `linux-zen-headers` or `linux-cachyos-headers` instead if you run that kernel. This is an install, not a system upgrade, so Omarchy's ALPM guard does not block it: `/usr/share/omarchy/bin/omarchy-update-pacman-guard` aborts only when the pacman command line carries both a sync flag and a sysupgrade flag. `v4l2loopback-utils` is optional and gives you `v4l2loopback-ctl`.

2. Load it with the options that make it usable:

```bash
sudo modprobe -r v4l2loopback
sudo modprobe v4l2loopback video_nr=9 card_label="OBS Virtual Camera" exclusive_caps=1
v4l2-ctl --list-devices
```

`exclusive_caps=1` is still needed on v4l2loopback 0.15.4. Upstream's default is 0 (`V4L2LOOPBACK_DEFAULT_EXCLUSIVECAPS` in `v4l2loopback.c`), so a device loaded with no options advertises OUTPUT and CAPTURE together and the Chromium based clients will not list it.

3. Make it survive a reboot:

```bash
echo v4l2loopback | sudo tee /etc/modules-load.d/v4l2loopback.conf
printf 'options v4l2loopback video_nr=9 card_label="OBS Virtual Camera" exclusive_caps=1\n' \
  | sudo tee /etc/modprobe.d/v4l2loopback.conf
```

Do this before relying on the device number. OBS can load the module itself, but its own command passes no `video_nr`. In obs-studio 32.2.2 the string compiled into `/usr/lib/obs-plugins/linux-v4l2.so` is:

```text
pkexec modprobe v4l2loopback exclusive_caps=1 card_label='OBS Virtual Camera' && sleep 0.5
```

So if OBS loads it, the device lands on the first free number rather than on `/dev/video9`.

4. In OBS: **Start Virtual Camera** (bottom right). The same plugin gates the button on `modinfo v4l2loopback` succeeding and logs `v4l2loopback not installed, virtual camera not registered` when it does not, which is why a failed DKMS build makes the button vanish rather than error.

5. Test the device before blaming the conferencing app. It only advertises CAPTURE once something is feeding it:

```bash
ffplay /dev/video9
```

Browser check: open <https://webcamtests.com/> and pick the OBS device.

If the app still does not list it, flip `exclusive_caps`. The ArchWiki says to try it both ways:

```bash
sudo modprobe -r v4l2loopback
sudo modprobe v4l2loopback video_nr=9 card_label="OBS Virtual Camera"
```

You can also add and delete devices without reloading the module using `v4l2loopback-ctl add` and `v4l2loopback-ctl delete` from `v4l2loopback-utils`, but note upstream's warning that module options may be ignored for a dynamically added device and must be given explicitly.

**Verify.** `v4l2-ctl --list-devices` (from `v4l-utils`) lists "OBS Virtual Camera". It is at `/dev/video9` only if you loaded the module yourself with `video_nr=9` or wrote `/etc/modprobe.d/v4l2loopback.conf`, because OBS's own autoload passes no `video_nr` and takes the first free number. With OBS's virtual camera running, `ffplay /dev/videoN` shows the OBS program feed and the device appears in the browser's camera picker. Check the module actually built for the running kernel with:

```bash
uname -r
dkms status
modinfo v4l2loopback | head -3
```

Sources: <https://wiki.archlinux.org/title/V4l2loopback> · <https://wiki.archlinux.org/title/Open_Broadcaster_Software> · <https://archlinux.org/packages/extra/any/v4l2loopback-dkms/> · <https://archlinux.org/packages/extra/any/v4l2loopback-utils/> · <https://github.com/umlaeute/v4l2loopback>

---

## VM and remote-desktop windows either swallow all your Hyprland keybinds or leak keys to the compositor

`vm-remote-desktop-steals-or-leaks-compositor-binds` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** In a fullscreen VM (virt-manager, GNOME Boxes, VirtualBox) or a VNC/RDP client (Remmina, Vinagre), pressing SUPER switches my Hyprland workspace instead of opening the guest's start menu — the guest never sees the key. Or the opposite: while that window is focused none of my Hyprland binds work at all, I cannot change workspace or adjust volume, and I have to alt-tab out first.

**Cause.** Both behaviours come from the `keyboard-shortcuts-inhibit` Wayland protocol. A client that requests inhibition is handed every key including the compositor's own binds — that is what makes SUPER reach a guest OS, and also what makes your workspace binds go dead. A client that does not request it (or that you have configured Hyprland to refuse) leaks modifier combos to the compositor instead. Hyprland exposes both sides: a per-window rule to refuse an app's inhibit request, and per-bind flags that survive inhibition.

> **Audit corrected this record.** The cause and the protocol story are correct, and every flag the record names is real — I checked the current Lua wiki (hyprwm/hyprland-wiki content/configuring/core/binds/flags.md): `dont_inhibit` ("Bypasses the app's requests to inhibit keybinds"), `allow_input_capture` ("When input is captured by a client, this bind will still be processed"), `locked` and `repeating` are all in the flag table, and content/configuring/core/rules/window-rules.md lists `no_shortcuts_inhibit` ("Disallows the app from inhibiting your shortcuts") as a dynamic effect. The `{ name = ..., match = {...} }` rule schema and the `wpctl` volume binds match the wiki's own examples. The defect is the escape hatch — the one thing the record's own danger note says you must always have. It is written as `hl.dsp.exec_cmd("hyprctl dispatch fullscreen 0")`, and on Hyprland 0.56 `hyprctl dispatch` is documented as "a shorthand for `eval 'hl.dispatch(...)'`" (content/configuring/core/advanced-configuration/using-hyprctl.md), so the bare-dispatcher form `fullscreen 0` is evaluated as Lua and errors instead of un-fullscreening. A user trapped in a fullscreen VM presses the escape bind and nothing happens. The correct dispatcher is `hl.dsp.window.fullscreen({ action = "unset" })` (dispatchers.md: `fullscreen({ window?, action?, mode?, layout_aware? })`, action can be toggle/set/unset), and it should be dispatched directly rather than shelling out to hyprctl. Two additions while correcting: `hl.dsp.release_input_capture()` is a documented general dispatcher and is the right partner for the `allow_input_capture` case, and if the app never requests inhibition at all (toggling the rule changes nothing) no window rule can help — a submap that unbinds SUPER is the only compositor-side answer, using `hl.define_submap` / `hl.dsp.submap("reset")` / `submap_universal` as documented in binds/submaps.md.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Adding a broad `no_shortcuts_inhibit` rule (for example matching `class = ".*"`) makes SUPER and other modifier combos unusable inside every VM and remote session, which is usually worse than the original complaint. Match one specific class. Conversely, if you let an app inhibit everything and define no `dont_inhibit` escape bind, a fullscreen VM that grabs the keyboard can leave you unable to leave it without switching to a TTY with Ctrl+Alt+F2.

**Fix.**

Find the window's class first:

```bash
hyprctl clients | grep -E '^\s+(class|initialClass|title)'
```

**Case A — the app is stealing your binds and you want them back.** Refuse its inhibit request:

```lua
-- ~/.config/hypr/hyprland.lua
hl.window_rule({
  name = "no-inhibit-remote-desktop",
  match = { class = "^(org.remmina.Remmina)$" },
  no_shortcuts_inhibit = true
})
```

**Case B — you want the app to keep grabbing keys, but a few binds must always work.** Mark those binds `dont_inhibit` (bypasses the app's inhibit request) and/or `locked` (also fires while an input inhibitor such as a lockscreen is active). Note that `hyprctl dispatch` on 0.55+ evaluates its argument as Lua, so do **not** shell out to `hyprctl dispatch fullscreen 0` — call the dispatcher directly:

```lua
-- escape hatch that always works, even inside a fullscreen VM
hl.bind("SUPER + SHIFT + Escape", hl.dsp.window.fullscreen({ action = "unset" }), { dont_inhibit = true })

-- media keys that keep working everywhere
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+"),
        { repeating = true, dont_inhibit = true, locked = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),
        { repeating = true, dont_inhibit = true, locked = true })
```

For clients that use input *capture* rather than shortcut inhibition (some remote-desktop and input-sharing tools), the bind flag is `allow_input_capture`, and there is a dispatcher that tears the capture session down:

```lua
hl.bind("SUPER + SHIFT + Escape", function()
  hl.dispatch(hl.dsp.release_input_capture())
  hl.dispatch(hl.dsp.window.fullscreen({ action = "unset" }))
end, { dont_inhibit = true, allow_input_capture = true })
```

**If toggling the rule changes nothing**, the app is not using the protocol at all — it never requests inhibition, so there is nothing for Hyprland to refuse and no way to hand it SUPER either. The only compositor-side answer is a submap that clears your binds while you work in the guest:

```lua
hl.bind("SUPER + SHIFT + V", hl.dsp.submap("vm"))

hl.define_submap("vm", function()
  -- nothing is bound in here, so SUPER and friends all reach the guest
  hl.bind("SUPER + SHIFT + V", hl.dsp.submap("reset"))
end)
```

If you ever get stuck in it with no terminal, switch to a TTY and run
`hyprctl dispatch --instance 0 'hl.dsp.submap("reset")'`.

Apply without restarting:

```bash
hyprctl reload
```

Always keep at least one `dont_inhibit` escape bind, or a fullscreen VM that grabs the keyboard leaves you with no way out except a TTY switch.

On Hyprland 0.54 and older the same rule and bind flags exist in hyprlang form — see the pinned 0.54 wiki at <https://wiki.hypr.land/0.54.0/> for that syntax.

**Verify.** `hyprctl clients` gives you the class; after `hyprctl reload`, focus the VM/RDP window and press SUPER — with the rule applied, the compositor bind fires; without it, the key reaches the guest. Your `dont_inhibit` escape bind must work in both cases.

Sources: <https://wiki.hypr.land/Configuring/Basics/Binds/> · <https://wiki.hypr.land/Configuring/Basics/Window-Rules/> · <https://wiki.hypr.land/Configuring/Basics/Variables/>

---

## Wine and Proton stay on XWayland even though the Wayland driver exists

`wine-proton-native-wayland-driver` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Games under Proton have laggy or offset mouse input, flicker, or refuse to go properly fullscreen. I read that Wine has a native Wayland driver now, but `wine` still behaves exactly like before and setting an environment variable did nothing. `winecfg` windows sometimes open with no keyboard or mouse response at all.

**Cause.** Wine's Wayland graphics driver is built and shipped, but the X11 driver still takes precedence whenever both can load. Wine 11.16 sets `default_driver = L"mac,x11,wayland"` in `programs/explorer/desktop.c` and tries each name in order, and under a Wayland session `DISPLAY` is always set because XWayland is running, so `winex11.drv` loads first and wins.

Valve's own Proton is a separate matter. Proton 10, Proton 11, Proton Experimental and bleeding-edge have no Wayland environment variable at all. `PROTON_ENABLE_WAYLAND=1` is a GE-Proton option added in GE-Proton10-1, also honoured by proton-cachyos and set by launchers such as Lutris and Heroic. Setting it in Steam launch options under a stock Valve Proton does nothing.

> **Audit corrected this record.** The plain Wine half of this record is correct and I confirmed it against Wine source rather than only against the wiki, which matters because the wiki cites the wine-10.0 release notes and this workstation runs wine 11.16-1. In wine 11.16 `programs/explorer/desktop.c` line 43 sets `default_driver = L"mac,x11,wayland"`, and the loader walks that comma-separated list building `wine%s.drv` and taking the first `LoadLibraryW` that succeeds, so X11 genuinely does win when both work. The same function reads `HKEY_CURRENT_USER\Software\Wine\Drivers` value `Graphics` at lines 1011 to 1015, so the record's registry path and value name are exact. `DISPLAY=:0` is set in this Omarchy session (checked with `systemctl --user show-environment`), so the X11 driver loads and the record's cause holds here. `winewayland.drv` is present in `/usr/lib/wine/x86_64-windows/`. The `nodrv_CreateWindow` and `The explorer process failed to start.` strings are in `dlls/win32u/driver.c` lines 772 to 981, and `Could not create tray window` is in the Arch wiki block the record quotes. The verify line is exact: `hyprctl clients` on this machine prints `xwayland: 0` per window. One claim is wrong and it is the Proton half. `PROTON_ENABLE_WAYLAND` does not exist anywhere in Valve's own Proton. I fetched the `proton` launcher from `proton_10.0`, `proton_11.0`, `experimental_11.0` and `bleeding-edge` and enumerated every `PROTON_*` variable in each: none of them is a Wayland variable, and GitHub code search across `ValveSoftware/Proton` and `ValveSoftware/wine` returns zero hits for the name. It is a GE-Proton option, introduced in the GE-Proton10-1 release notes on 2025-05-14 (`New option for using Wine-Wayland: PROTON_ENABLE_WAYLAND=1`), and it is also read by `proton-cachyos`, whose launcher calls `check_environment("PROTON_ENABLE_WAYLAND", "wayland")`. So the record's own hedge, `Proton 10 / Proton Experimental or a recent Proton-GE`, is wrong in two of its three arms: a stock Proton 10 or Proton Experimental silently ignores the variable, which is the exact failure shape of a setting nothing reads. The GE release notes also tell users not to unset `DISPLAY` when using it, which the record does not mention. The Hyprland XWayland source resolves but is about HiDPI scaling and abstract Unix sockets and says nothing about Wine, Proton, mouse offset or flicker, so it does not support what the record claims and is removed. NOT exercised: I ran no `wine`, no `winecfg`, no game and no Steam client, and wrote no registry value, because this is the operator's daily workstation.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `PROTON_ENABLE_WAYLAND=1` is a GE-Proton option and is experimental. It breaks the Steam overlay in most games (reported against Baldur's Gate 3, Diablo 3, Overwatch 2 and Path of Exile 2 among others) and MangoHud may fail to draw or crash the game. Set it per game in Launch Options rather than globally, so you can drop it for any title that misbehaves. Setting `Graphics` to a bare `wayland` in the prefix registry leaves no X11 fallback, so if `winewayland.drv` fails to load the prefix has no graphics driver and applications exit with `nodrv_CreateWindow`.

**Fix.**

**Plain Wine, one-off:** unset `DISPLAY` for that invocation.

```bash
env -u DISPLAY wine example.exe
```

**Plain Wine, prefix-wide:** write the driver preference into the prefix registry. The value is a comma-separated list tried in order, so `wayland,x11` keeps an X11 fallback if `winewayland.drv` fails to load, while a bare `wayland` leaves you with no graphics driver if it does.

```bash
wine reg add 'HKEY_CURRENT_USER\Software\Wine\Drivers' /v Graphics /d 'wayland,x11'
```

Revert with:

```bash
wine reg delete 'HKEY_CURRENT_USER\Software\Wine\Drivers' /v Graphics /f
```

**Proton / Steam:** `PROTON_ENABLE_WAYLAND=1` is a **GE-Proton** option, not a Valve one. Stock Proton 10, Proton 11 and Proton Experimental have no Wayland variable and ignore it silently, so check which Proton the game is using first. Install GE-Proton, select it for the game under Properties then Compatibility, and set the variable in Launch Options:

```
PROTON_ENABLE_WAYLAND=1 %command%
```

GE's own release notes say that is all you need, and that you should not additionally blank `DISPLAY`, because unsetting it breaks applications that still want X11.

**If XWayland behaviour is what you actually want to fix** (flicker, wrong window location, wrong mouse position, keyboard not detected), the documented Wine workaround is a virtual desktop. In `winecfg`, Graphics tab, tick "Emulate a virtual desktop". If the window is already unresponsive and you cannot reach that checkbox:

```bash
wine explorer /desktop=name,1280x800 winecfg
```

If GUI windows never appear and you see `nodrv_CreateWindow ... no driver could be loaded` / `Could not create tray window`, try forcing a display:

```bash
DISPLAY=:1 wine winecfg
```

On Omarchy nothing here is overridden by the session. `/usr/share/omarchy/default/hypr/envs.lua` sets GDK, Qt, Electron and Mozilla variables only, and no Wine or Proton ones. Do not move the `DISPLAY` change into `~/.config/uwsm/env.d/`: that is the session-wide override point and unsetting `DISPLAY` there would break every XWayland application, not just Wine.

**Verify.** With the Wayland driver active, `hyprctl clients` shows the Wine/Proton window with `xwayland: 0`. Mouse position tracks correctly in fullscreen and the window no longer flickers between sizes.

Sources: <https://wiki.archlinux.org/title/Wine> · <https://github.com/GloriousEggroll/proton-ge-custom/issues/166> · <https://gitlab.winehq.org/wine/wine/-/raw/wine-11.16/programs/explorer/desktop.c> · <https://gitlab.winehq.org/wine/wine/-/raw/wine-11.16/dlls/win32u/driver.c> · <https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/GE-Proton10-1> · <https://github.com/ValveSoftware/Proton/blob/proton_11.0/proton>

---
