# Wayland app compatibility

37 problems. Sorted by severity, then by how often users hit it.

## screenshare-black-screen-no-portal

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

## discord-screenshare-stops-after-one-second

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

## No CJK / compose input in Electron and Chromium apps on Wayland

`electron-chromium-ime-no-wayland-text-input` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Fcitx5 works fine in kitty, Firefox and native Wayland apps, but in Chromium, VS Code, Discord, Obsidian or Spotify pressing Ctrl+Space does nothing — no candidate window ever appears and I cannot type a single Chinese/Japanese/Korean character. Dead keys and the Compose key are dead in the same apps. `fcitx5-diagnose` reports no problems.

**Cause.** Wayland IME goes through the `text-input` protocol. Chromium's Ozone/Wayland backend does not enable its Wayland IME path at all unless `--enable-wayland-ime` is passed, and when it does it defaults to `text-input-v1` while most toolkits/compositors speak `v3`. The ArchWiki Fcitx5 page states this outright: "Chromium defaults to text-input-v1 (can be overridden via --wayland-text-input-version=3)". So the env vars that fix GTK/Qt/XWayland apps (GTK_IM_MODULE, QT_IM_MODULE, XMODIFIERS) have no effect on Chromium-based clients — they need command-line flags instead. Electron apps that bundle their own Chromium inherit the same defect.

> ⚠️ **Risk.** Do not combine `--enable-wayland-ime` with `--gtk-version=4`; the ArchWiki lists them as alternatives for the same problem and using both together is a known source of AltGr/Compose regressions. `--disable-gtk-ime` is a third, mutually exclusive workaround — pick one and test before adding another.

**Fix.**

First confirm fcitx5 is actually running and has an input method configured (see the existing `fcitx5-cjk-input-not-working-wayland` record for the daemon/env-var side):

```bash
pgrep -a fcitx5
fcitx5-diagnose | head -40
```

Now add the Chromium IME flags. Arch's `chromium` package reads flags from a plain-text file, one flag per line:

```conf
# ~/.config/chromium-flags.conf
--enable-wayland-ime
--wayland-text-input-version=3
```

Arch's `electron` package (and apps built against it) reads the same style of file:

```conf
# ~/.config/electron-flags.conf
--enable-wayland-ime
--wayland-text-input-version=3
```

If the app is pinned to a specific Electron major, the versioned file wins — create it too:

```bash
printf -- '--enable-wayland-ime\n--wayland-text-input-version=3\n' > ~/.config/electron38-flags.conf
```

Some apps support a per-application flags file named after the binary (vesktop, spotify, code):

```bash
for a in vesktop spotify code obsidian; do
  printf -- '--enable-wayland-ime\n--wayland-text-input-version=3\n' > ~/.config/$a-flags.conf
done
```

Apps that bundle their own Electron (discord, slack-desktop, many AppImages) ignore all of the above — patch their desktop entry instead:

```bash
cp /usr/share/applications/discord.desktop ~/.local/share/applications/
sed -i 's|^Exec=/usr/bin/discord|Exec=/usr/bin/discord --enable-wayland-ime --wayland-text-input-version=3|' \
  ~/.local/share/applications/discord.desktop
update-desktop-database ~/.local/share/applications
```

Fully quit the app (do not use the in-app relaunch button — Chromium relaunches on the old platform) and start it again from the launcher.

If an app still refuses and is running under XWayland, it needs the legacy XIM path instead. On an Omarchy/uwsm session put these in `~/.config/uwsm/env` (the Hyprland wiki says uwsm users must not put env vars in `hyprland.lua`):

```sh
# ~/.config/uwsm/env
export XMODIFIERS=@im=fcitx
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
```

Then log out and back in.

**Verify.** Open the app, press Ctrl+Space, and check the fcitx5 candidate window appears over the app window. `hyprctl clients | grep -A6 <class>` should show `xwayland: 0` for a native Wayland Electron app. If the popup appears but characters land in the wrong place, you are still on text-input-v1 — confirm the flag file is being read by launching from a terminal and checking `chrome://version` shows the flags in the command line.

Sources: <https://wiki.archlinux.org/title/Chromium> · <https://wiki.archlinux.org/title/Fcitx5> · <https://wiki.archlinux.org/title/Electron> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/>

---

## obs-no-screen-capture-source

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

## share-picker-crashes-missing-qt6-wayland

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

## steam-games-xwayland-fullscreen-flicker

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

## xwayland-app-cannot-share-wayland-windows

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

## zoom-screen-share-not-working-wayland

`zoom-screen-share-not-working-wayland` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** In the Zoom desktop client, clicking "Share Screen" either shows no screens to pick, or shares a black/frozen window. Sharing works for other apps on the same machine.

**Cause.** Zoom does not use the portal by default on Wayland — its Wayland share path is gated behind a config flag, and the client may also be running under XWayland where it can only see X11 windows.

> ⚠️ **Risk.** Setting `xwayland=false` is documented to make the ZoomWebviewHost process stop with 0MB memory, which disables whiteboard and some in-meeting features. Revert it if you lose functionality.

**Fix.**

Install the WebRTC screen-sharing prerequisites, then enable Zoom's Wayland share explicitly in `~/.config/zoomus.conf`:

```ini
enableWaylandShare=true
```

Restart Zoom completely (quit from the tray, not just close the window).

If it still refuses to use PipeWire, force it in the GUI: Settings -> Share Screen -> Advanced -> **Screen capture mode: PipeWire** (instead of Automatic).

To run Zoom natively on Wayland rather than XWayland, also set in `~/.config/zoomus.conf`:

```ini
xwayland=false
```

If the Zoom UI is then too small on a HiDPI screen:

```bash
QT_SCALE_FACTOR=2 zoom
```

If none of this works, the Zoom web client avoids the problem entirely — replace `/j/` with `/wc/join/` in the meeting URL:
`https://<subdomain>.zoom.us/wc/join/<meeting_id>?pwd=<password>`

**Verify.** Click Share Screen — the Hyprland share picker appears and the shared preview shows live desktop content rather than black.

Sources: <https://wiki.archlinux.org/title/Zoom_Meetings> · <https://wiki.archlinux.org/title/PipeWire>

---

## chromium-xwayland-nvidia-gpu-crash

`chromium-xwayland-nvidia-gpu-crash` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`, `xwayland`

**Symptom.** Chromium's GPU process crashes repeatedly on NVIDIA — tabs go blank or show "Aw, Snap!", `chrome://gpu` reports the GPU process restarting. On Omarchy some users additionally see Chromium die with `SIGTRAP (int3)` at a fixed offset when a new window is spawned for an OAuth popup, in a ~20-crash loop, while the same flow works on KDE Plasma.

**Cause.** Chromium's GPU process initialisation is fragile on NVIDIA under XWayland (ANGLE/GL backend selection), and separately on Hyprland its Ozone/Wayland GPU compositing path can fail when a brand-new browser process is spawned rather than a new window in an existing one.

> ⚠️ **Risk.** `--disable-gpu` turns off hardware acceleration for the whole browser: expect higher CPU use and no hardware video decode. Treat it as a stopgap, and prefer `--ozone-platform=x11` if that alone fixes it.

**Fix.**

For the XWayland GPU-process crashes, add to `~/.config/chromium-flags.conf`:

```
--use-angle=vulkan
--use-cmd-decoder=passthrough
```

For the OAuth-popup `SIGTRAP` crash loop on Hyprland, the confirmed workaround is to take GPU out of the path for that process:

```
--disable-gpu
```

A narrower alternative that also avoids the crash is forcing X11 for the browser:

```
--ozone-platform=x11
```

Quit Chromium entirely (`pkill chromium`) and relaunch — flags are only read at process start.

Check what actually crashed:

```bash
coredumpctl list chromium
journalctl -b | grep -i 'trap int3'
```

**Verify.** `chrome://gpu` no longer shows the GPU process restarting, and the OAuth login popup opens instead of crash-looping.

Sources: <https://wiki.archlinux.org/title/Chromium> · <https://github.com/basecamp/omarchy/issues/8394>

---

## electron-app-no-window-ozone-wayland

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

## java-gray-window-nonreparenting

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

## share-picker-outputs-tab-empty

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

## chrome-sharing-indicator-stuck-center-screen

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

## clipboard-lost-when-source-app-closes

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

## gdk-scale-mismatch-oversized-xwayland

`gdk-scale-mismatch-oversized-xwayland` · severity: **medium** · frequency: **very-common** · applies to: `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`, `xwayland`

**Symptom.** On stock Omarchy, XWayland and Java apps render at double size — Steam's whole UI is 2x on a 1080p screen, or a Java IDE's window is wider than the monitor with the right-hand side hanging off the edge and no way to shrink it. Native Wayland apps look correct. `xprop` shows `WM_NORMAL_HINTS` minimum widths that are exactly twice the app's real minimum.

**Cause.** Omarchy's packaged `monitors.lua` hardcodes `GDK_SCALE=2` while the monitor scale is computed (`scale = "auto"`), and `default/hypr/envs.lua` sets `xwayland = { force_zero_scaling = true }`. With force_zero_scaling on, XWayland clients see the full physical resolution (e.g. 1920x1080) and are told by GDK_SCALE to draw everything at 2x. The two settings disagree, so X11/Java/Swing windows demand twice the pixels they need. On a display where auto-scale resolves to 1, GDK_SCALE=2 is simply wrong outright.

> ⚠️ **Risk.** Editing the packaged defaults under `/usr/share/omarchy/default/hypr/` or `~/.local/share/omarchy/default/hypr/` gets reverted by `omarchy update`. Only edit files under `~/.config/hypr/`.

**Fix.**

Match GDK_SCALE to the actual monitor scale. Check what Hyprland picked:

```bash
hyprctl monitors | grep -E 'Monitor|scale'
```

Omarchy 4.x — edit `~/.config/hypr/monitors.lua` and set the integer nearest your real scale:

```lua
local omarchy_monitor_scale = "auto"
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- was: local omarchy_gdk_scale = 2
local omarchy_gdk_scale = 1        -- use 1 when hyprctl reports scale 1 or 1.25
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```

Omarchy 3.x — same change in `~/.config/hypr/monitors.conf`:

```conf
env = GDK_SCALE,1
```

GDK_SCALE is read at process start and is exported through the systemd user manager, so `hyprctl reload` is not enough — log out and back in, or re-export and restart the app:

```bash
systemctl --user import-environment GDK_SCALE
dbus-update-activation-environment --systemd GDK_SCALE
```

To fix one stubborn app without changing the global value (keeps Wayland GTK correct):

```bash
GDK_SCALE=1 GDK_DPI_SCALE=1 JAVA_TOOL_OPTIONS=-Dsun.java2d.uiScale=1 <command>
```

For a Flatpak:

```bash
flatpak override --user --env=GDK_SCALE=1 --env=JAVA_TOOL_OPTIONS=-Dsun.java2d.uiScale=1 <app.id>
```

For a Steam game, in Properties -> Launch Options:

```
GDK_SCALE=1 %command%
```

**Verify.** `tr '\0' '\n' < /proc/$(pgrep -x steam)/environ | grep GDK_SCALE` shows the value you set, and after restarting the app its window fits the screen with normally-sized UI.

Sources: <https://github.com/basecamp/omarchy/issues/7021> · <https://github.com/basecamp/omarchy/issues/2824> · <https://github.com/basecamp/omarchy/issues/6415> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/XWayland/>

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

## xwayland-apps-blurry-hidpi

`xwayland-apps-blurry-hidpi` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`, `xwayland`

**Symptom.** Some apps look soft, fuzzy or pixelated compared to the rest of the desktop — text has visible fringing. Typically Steam, older Electron builds, Java IDEs, Wine apps, VS Code launched in X11 mode, or anything launched before the toolkit env vars were set. Native GTK/Qt apps look fine.

**Cause.** The app is running under XWayland. Xorg has no fractional-scaling concept, so with a monitor scale of e.g. 1.5 or 2 the compositor renders the X client at 1x and bitmap-stretches it up. The result is blurry, not pixelated-but-sharp.

> ⚠️ **Risk.** Do not install "XWayland HiDPI patches" — the Hyprland wiki explicitly states they are no longer supported and must not be used.

**Fix.**

First confirm it really is XWayland:

```bash
hyprctl clients -j | jq '.[] | {class, xwayland}'
# or
xlsclients -l
```

Best fix: make the app native Wayland. Set these once, at session level.

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/envs.lua`):

```lua
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("MOZ_ENABLE_WAYLAND", "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "wayland")
hl.env("SDL_VIDEODRIVER", "wayland")
```

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/hyprland.conf`) — note: no quotes around values, Hyprland takes the raw string:

```conf
env = GDK_BACKEND,wayland,x11,*
env = QT_QPA_PLATFORM,wayland;xcb
env = MOZ_ENABLE_WAYLAND,1
env = ELECTRON_OZONE_PLATFORM_HINT,wayland
env = SDL_VIDEODRIVER,wayland
```

For apps that genuinely cannot do Wayland, stop the compositor upscaling them and let the toolkit scale instead.

Hyprland 0.55+ / Omarchy 4.x:

```lua
hl.monitor({ output = "", mode = "highres", position = "auto", scale = "2" })
hl.config({ xwayland = { force_zero_scaling = true } })
hl.env("GDK_SCALE", "2")
hl.env("XCURSOR_SIZE", "32")
```

Hyprland <=0.54:

```conf
monitor = , highres, auto, 2
xwayland {
  force_zero_scaling = true
}
env = GDK_SCALE,2
env = XCURSOR_SIZE,32
```

Omarchy already ships `force_zero_scaling = true` by default — see the `gdk-scale-mismatch-oversized-xwayland` record for the trap that creates.

**Verify.** `hyprctl clients -j` reports `"xwayland": false` for the app, or with force_zero_scaling on, the app's text is crisp (it may be small — that is the toolkit-scaling half of the problem, not blur).

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/XWayland/> · <https://wiki.hypr.land/0.54.0/Configuring/XWayland/> · <https://wiki.hypr.land/0.54.0/FAQ/> · <https://wiki.archlinux.org/title/Wayland> · <https://wiki.archlinux.org/title/HiDPI>

---

## apps-slow-to-launch-multiple-portals

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

## chromium-hangs-pasting-from-xwayland-app

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

## chromium-window-shrinks-fractional-scaling

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

## discord-global-keybinds-not-working

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

## firefox-no-download-save-dialog

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

## gtk-file-chooser-does-nothing-xwayland

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

## java-swing-apps-oversized

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

## obs-global-hotkeys-dont-work

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

## screenshot-tool-broken-multimonitor

`screenshot-tool-broken-multimonitor` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Flameshot (or another X11-era screenshot tool) opens on the wrong monitor, captures only one screen, produces a warped image when you Ctrl+C from its GUI, or hangs the session so Esc and clicks do nothing while the cursor still moves.

**Cause.** Flameshot was written for X11 and has poor Wayland support. Under Hyprland it grabs the X screen geometry, which does not match the Wayland output layout on multi-monitor or HiDPI setups.

> ⚠️ **Risk.** Launching Flameshot with `XDG_CURRENT_DESKTOP=sway` changes which portal backend that process talks to. Only set it on the Flameshot command line, never session-wide — session-wide it will break screen sharing for every app.

**Fix.**

Use native Wayland tooling instead — this is the recommendation on the Hyprland wiki:

```bash
sudo pacman -S --needed grim slurp wl-clipboard
```

Region screenshot straight to the clipboard.

Hyprland <=0.54 / Omarchy 3.x (`~/.config/hypr/bindings.conf`):

```conf
bind = , Print, exec, grim -g "$(slurp -d)" - | wl-copy
bind = SHIFT, Print, exec, grim -g "$(slurp -d)" ~/Pictures/$(date +%Y-%m-%d_%H-%M-%S).png
```

Hyprland 0.55+ / Omarchy 4.x (`~/.config/hypr/bindings.lua`):

```lua
hl.bind("Print", hl.dsp.exec_cmd('grim -g "$(slurp -d)" - | wl-copy'))
```

Omarchy already binds Print to its own capture tool — check that first before adding a duplicate binding.

If you must keep Flameshot, the Hyprland wiki's user-contributed rules make it usable (hyprlang syntax):

```conf
windowrule = float, class:flameshot
windowrule = move 0 0, class:flameshot
windowrule = pin, class:flameshot
windowrule = noinitialfocus, class:flameshot
windowrule = monitor 1, class:flameshot
```

and launch it pretending to be Sway, which fixes the warped-copy bug:

```bash
XDG_CURRENT_DESKTOP=sway flameshot gui
```

**Verify.** Press the screenshot bind, drag a region across the monitor boundary — the captured image matches what you selected and lands in the clipboard (`wl-paste --list-types` shows `image/png`).

Sources: <https://wiki.hypr.land/0.54.0/FAQ/> · <https://wiki.hypr.land/Useful-Utilities/Screenshots-and-Recording/>

---

## screen-recording-fails-hybrid-gpu-external-monitor

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

## Flatpak apps run under XWayland — blurry, wrong scaling, unaffected by session env vars

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

**Cause.** GTK gates middle-click paste on the `org.gnome.desktop.interface gtk-enable-primary-paste` setting, which comes from `gsettings-desktop-schemas` and is read by GTK on every desktop, not just GNOME. Upstream changed that key's default from `true` to `false`, so every GTK app that honours it went silent at once. Firefox and a few other apps implement middle-click paste themselves and ignore the setting, which is why they still work — that split is the giveaway. A separate Wayland behaviour compounds it: the primary selection is owned by the source window, so it disappears when that window closes.

> ⚠️ **Risk.** Do not run `wl-clip-persist --clipboard primary`. Upstream documents that primary-selection mode breaks the selection system in some GTK applications — text selection itself stops behaving correctly. Use `--clipboard regular` only.

**Fix.**

Check the current value, then turn it back on:

```bash
gsettings get org.gnome.desktop.interface gtk-enable-primary-paste
gsettings set org.gnome.desktop.interface gtk-enable-primary-paste true
```

If gsettings schemas are not available, write the key directly:

```bash
dconf write /org/gnome/desktop/interface/gtk-enable-primary-paste true
```

The setting is read once at application startup — fully quit and reopen the app (some users need a full re-login).

Confirm the primary selection itself is populated. Select some text, then:

```bash
wl-paste --primary
```

If that prints nothing, the source app is not exporting a primary selection at all, which is a different problem.

To keep the selection alive after the source window closes:

```bash
sudo pacman -S --needed wl-clip-persist
```

```lua
-- ~/.config/hypr/hyprland.lua
hl.on("hyprland.start", function()
  hl.exec_cmd("wl-clip-persist --clipboard regular")
end)
```

**Verify.** `gsettings get org.gnome.desktop.interface gtk-enable-primary-paste` returns `true`; select text in one GTK window and middle-click into another — the text pastes. `wl-paste --primary` prints the current selection.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=313089> · <https://github.com/ghostty-org/ghostty/discussions/12181> · <https://wiki.archlinux.org/title/Clipboard> · <https://wiki.hypr.land/Useful-Utilities/Clipboard-Managers/>

---

## OBS virtual camera missing, or Zoom/Meet/Teams never lists it

`obs-virtual-camera-not-listed-v4l2loopback` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** OBS has no "Start Virtual Camera" button, or it starts without error but Zoom, Google Meet, Teams and Discord never show "OBS Virtual Camera" in the camera dropdown — only my real webcam. `ls /dev/video*` shows only the webcam devices.

**Cause.** OBS's virtual camera on Linux writes into a `v4l2loopback` device, which is an out-of-tree kernel module that must be built and loaded. Without it there is no device node and OBS hides the button. When the module is loaded without `exclusive_caps=1` the device advertises both OUTPUT and CAPTURE capabilities at once; Chromium-based clients (Meet, Teams, Zoom, Discord, Slack) refuse to enumerate such a device, so it exists but is invisible to exactly the apps you want it in.

> ⚠️ **Risk.** v4l2loopback is DKMS-built: if `linux-headers` does not match the kernel you are actually running, the build fails silently during the pacman transaction and the camera disappears after the next reboot. After any kernel upgrade run `sudo dkms status` and, if needed, `sudo dkms autoinstall` then reboot — do not `modprobe -r` while OBS or a call is holding the device, as the removal will fail or wedge the app.

**Fix.**

1. Install the module and headers matching your **running** kernel:

```bash
uname -r
sudo pacman -S --needed v4l2loopback-dkms linux-headers
# linux-lts-headers / linux-zen-headers / linux-cachyos-headers if you run that kernel
```

2. Load it with the options that make it usable:

```bash
sudo modprobe -r v4l2loopback
sudo modprobe v4l2loopback video_nr=9 card_label="OBS Virtual Camera" exclusive_caps=1
v4l2-ctl --list-devices
```

3. Make it survive a reboot:

```bash
echo v4l2loopback | sudo tee /etc/modules-load.d/v4l2loopback.conf
printf 'options v4l2loopback video_nr=9 card_label="OBS Virtual Camera" exclusive_caps=1\n' \
  | sudo tee /etc/modprobe.d/v4l2loopback.conf
```

4. In OBS: **Start Virtual Camera** (bottom-right). OBS will offer to load the module via `pkexec` if it is not already loaded.

5. Test the device before blaming the conferencing app — remember it only advertises CAPTURE once something is feeding it:

```bash
ffplay /dev/video9
```

Browser check: open <https://webcamtests.com/> and pick the OBS device.

If the app *still* does not list it, flip `exclusive_caps` — the ArchWiki notes some apps want it and some do not:

```bash
sudo modprobe -r v4l2loopback
sudo modprobe v4l2loopback video_nr=9 card_label="OBS Virtual Camera"
```

**Verify.** `v4l2-ctl --list-devices` lists "OBS Virtual Camera" at `/dev/video9`. With OBS's virtual camera running, `ffplay /dev/video9` shows the OBS program feed, and the device appears in the browser's camera picker.

Sources: <https://wiki.archlinux.org/title/V4l2loopback> · <https://wiki.archlinux.org/title/Open_Broadcaster_Software> · <https://archlinux.org/packages/extra/x86_64/v4l2loopback-dkms/>

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

**Cause.** Wine's Wayland graphics driver is enabled by default, but the X11 driver still takes precedence whenever both are available — and under a Wayland session `DISPLAY` is always set because XWayland is running, so X11 always wins. Proton does not use the Wayland driver at all unless `PROTON_ENABLE_WAYLAND=1` is set for that game.

> ⚠️ **Risk.** `PROTON_ENABLE_WAYLAND=1` is experimental and breaks the Steam overlay in most games (reported against Baldur's Gate 3, Diablo 3, Overwatch 2, Path of Exile 2 among others); MangoHud may also fail to draw or crash the game. Set it per game in Launch Options rather than globally, so you can drop it for any title that misbehaves.

**Fix.**

**Plain Wine, one-off:** unset `DISPLAY` for that invocation.

```bash
env -u DISPLAY wine example.exe
```

**Plain Wine, prefix-wide:** write the driver preference into the prefix registry.

```bash
wine reg add 'HKEY_CURRENT_USER\Software\Wine\Drivers' /v Graphics /d 'wayland'
```

Revert with:

```bash
wine reg delete 'HKEY_CURRENT_USER\Software\Wine\Drivers' /v Graphics /f
```

**Proton / Steam:** set it per game. Right-click the game → Properties → Launch Options:

```
PROTON_ENABLE_WAYLAND=1 %command%
```

This needs Proton 10 / Proton Experimental or a recent Proton-GE; older Proton ignores it.

**If XWayland behaviour is what you actually want to fix** (flicker, wrong window location, wrong mouse position, keyboard not detected), the documented Wine workaround is a virtual desktop. In `winecfg` → Graphics tab, tick "Emulate a virtual desktop". If the window is already unresponsive and you cannot reach that checkbox:

```bash
wine explorer /desktop=name,1280x800 winecfg
```

If GUI windows never appear and you see `nodrv_CreateWindow ... no driver could be loaded` / `Could not create tray window`, try forcing a display:

```bash
DISPLAY=:1 wine winecfg
```

**Verify.** With the Wayland driver active, `hyprctl clients` shows the Wine/Proton window with `xwayland: 0`. Mouse position tracks correctly in fullscreen and the window no longer flickers between sizes.

Sources: <https://wiki.archlinux.org/title/Wine> · <https://github.com/GloriousEggroll/proton-ge-custom/issues/166> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/XWayland/>

---
