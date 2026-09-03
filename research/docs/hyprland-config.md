# Hyprland configuration

37 problems. Sorted by severity, then by how often users hit it.

## Fix a hypr tool failing with symbol lookup error after a system update

`hypr-stack-symbol-lookup-error-git-build` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`

**Symptom.** Hyprland or a hypr* tool refuses to start after a system update with `<app>: symbol lookup error: <app>: undefined symbol: <symbol>` or `error while loading shared libraries: <lib>: cannot open shared object file: No such file or directory` — sometimes just an immediate crash with no message.

**Cause.** The hypr* stack has no stable ABI between its own libraries. If you built Hyprland yourself, or use `-git` AUR packages (which count as building yourself), updating one component — hyprutils, hyprlang, hyprgraphics, aquamarine — without rebuilding the rest leaves mismatched symbols. Mixing distro packages with self-built components produces the same result.

> ⚠️ **Risk.** Never symlink one .so version to another to silence the loader — the FAQ is explicit that this causes memory corruption and crashes. Partial rebuilds of the stack are exactly the partial-upgrade failure mode; rebuild all of it or none of it.

**Fix.**

Rebuild the whole stack in dependency order, or stop mixing.

Order (from the Hyprland FAQ):
```
hyprland-protocols
hyprwayland-scanner
hyprutils
hyprgraphics
hyprlang
hyprcursor
aquamarine
xdg-desktop-portal-hyprland
hyprwire
hyprtoolkit
hyprland
```
Then hyprlock/hyprsunset/etc. in any order.

With AUR `-git` packages, force a clean rebuild of every one of them rather than a plain update:
```bash
yay -S --rebuildall hyprutils-git hyprlang-git hyprgraphics-git hyprcursor-git \
  aquamarine-git hyprwayland-scanner-git xdg-desktop-portal-hyprland-git hyprland-git
```
(the FAQ notes paru has been problematic for this; use yay)

The robust fix is to drop to packaged releases entirely:
```bash
yay -Rns hyprland-git
sudo pacman -S hyprland
```

**Verify.** `hyprctl version` runs and prints a version; `ldd $(which Hyprland) | grep 'not found'` returns nothing.

Sources: <https://wiki.hypr.land/FAQ/>

---

## Work out whether your Hyprland config should be hyprlang or Lua

`hyprlang-deprecated-lua-config-not-loading` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Edits to `~/.config/hypr/hyprland.conf` do nothing at all — no errors, no effect. Or the opposite: the wiki examples you copy (`hl.config({...})`, `hl.bind(...)`) are all rejected as syntax errors by your Hyprland.

**Cause.** Hyprland 0.55 (May 2026) deprecated hyprlang in favour of Lua and rewrote the whole wiki for Lua. Hyprland decides once, at startup: if `~/.config/hypr/hyprland.lua` exists it is loaded exclusively and `hyprland.conf` is ignored entirely; if it does not exist, the old `hyprland.conf` is loaded as before. So a leftover `hyprland.lua` silently orphans your `.conf`, and copying Lua snippets into a `.conf` (or hyprlang into a `.lua`) fails wholesale. hyprlang still works but is only guaranteed 'for a few releases'.

> ⚠️ **Risk.** `hyprctl reload full-reset` recreates the entire config context; the wiki says not to use it unless really necessary. Expect a visible flicker and layer-shell clients (bars, wallpapers) to re-init.

**Fix.**

Decide which one you are on, and be consistent.

```bash
ls -l ~/.config/hypr/hyprland.lua ~/.config/hypr/hyprland.conf
hyprctl version                     # confirm >= 0.55 before using Lua
```

To stay on hyprlang, remove/rename the Lua file and use the archived docs at https://wiki.hypr.land/0.54.0/ — the current wiki no longer shows hyprlang:
```bash
mv ~/.config/hypr/hyprland.lua ~/.config/hypr/hyprland.lua.disabled
hyprctl reload full-reset
```

To move to Lua, create `~/.config/hypr/hyprland.lua`. Split files with `require()`, not `source =`:
```lua
-- ~/.config/hypr/hyprland.lua
require("monitors")          -- ~/.config/hypr/monitors.lua
require("awesomeconf/keybinds")
hl.config({ general = { gaps_in = 5, gaps_out = 10, border_size = 2 } })
hl.bind("SUPER + Return", hl.dsp.exec_cmd("kitty"))
```

`hyprctl reload` alone will NOT switch engines — you need:
```bash
hyprctl reload full-reset
```

**Verify.** `hyprctl getoption general:gaps_in` reflects the value from the file you just edited; a deliberate typo in that file shows up in `hyprctl configerrors`.

Sources: <https://hypr.land/news/26_lua> · <https://hypr.land/news/update55> · <https://wiki.hypr.land/Configuring/Start/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/>

---

## Rebuild hyprpm plugins after a Hyprland update breaks the headers

`hyprpm-plugins-broken-after-hyprland-update` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`

**Symptom.** After a Hyprland update, plugins stop loading — `hyprpm reload` reports a version/headers mismatch, or you see `Headers corrupted. pkexec returned: You need to run make all first.` / `failed to install headers with error code 2`. `hyprctl plugin list` is empty and plugin keybinds do nothing.

**Cause.** Hyprland plugins are C++ shared objects compiled against the exact Hyprland headers of the version they will run inside. There is no stable ABI: any Hyprland version bump invalidates every installed plugin until it is rebuilt against the new headers. hyprpm keeps its own header tree and must re-fetch and rebuild it after each update; if that tree is stale or partially removed, the header install fails.

> ⚠️ **Risk.** Plugins run inside Hyprland as native code — a bad one can crash your whole session, and a malicious one can do anything your user can. Read the source of any plugin before enabling it, and never load a .so someone sent you. Hyprland's plugin-unload-on-crash protections are best-effort, not guaranteed.

**Fix.**

Rebuild plugins against the new headers, every time Hyprland changes version:

```bash
# build deps hyprpm needs
sudo pacman -S --needed cpio cmake git meson gcc

hyprpm update      # re-fetch + rebuild headers and all plugins for the current Hyprland
hyprpm list        # confirm each plugin says it built for your version
hyprpm reload -n   # load them, with a notification
```

If headers are wedged, start clean:
```bash
rm -rf ~/.local/share/hyprpm ~/.cache/hyprpm
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprexpo
hyprpm update && hyprpm reload
```

Make plugins load at every startup:
```lua
hl.on("hyprland.start", function() hl.exec_cmd("hyprpm reload -n") end)
```
```ini
exec-once = hyprpm reload -n
```

If Hyprland now crashes on start, the plugin is the cause — disable it from a TTY:
```bash
hyprpm disable <plugin-name>
```

Manual (non-hyprpm) plugins need `sudo make installheaders` from a Hyprland checkout at your exact version, then `hyprctl plugin load /absolute/path/to/plugin.so` — the path must be absolute.

**Verify.** `hyprctl plugin list` shows the plugin loaded, and `hyprpm list` reports no version mismatch.

Sources: <https://wiki.hypr.land/Plugins/Using-Plugins/> · <https://github.com/hyprwm/Hyprland/issues/4284> · <https://github.com/hyprwm/Hyprland/issues/5896> · <https://github.com/hyprwm/Hyprland/issues/6910>

---

## NVIDIA on Hyprland: black screen at start, flicker on wake, or the wrong GPU driving the outputs

`nvidia-hyprland-modeset-cursors-mgpu` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Hyprland starts to a black screen or exits immediately on an NVIDIA box; or it runs but flickers badly in Electron apps and XWayland games; or on a hybrid laptop the external HDMI/DP outputs are dead while the internal panel works; or the mouse pointer leaves a trail / disappears over fullscreen windows. `cat /sys/module/nvidia_drm/parameters/modeset` prints `N`.

**Cause.** Four separate NVIDIA-specific requirements, all of which look the same from the user's seat. (1) `nvidia_drm.modeset=1` is not set, so there is no DRM master for the compositor to take. (2) The wrong driver package for the card — 50xx-series and newer *require* the open kernel modules, and NVIDIA recommends them for Turing/Ampere (16xx/20xx) and later; older cards need the legacy branch. (3) On hybrid Intel-or-AMD-plus-NVIDIA laptops, Aquamarine picks a primary GPU on its own and a monitor wired to the card that was not selected simply does not appear. (4) NVIDIA's hardware cursor plane needs a CPU buffer; without it the pointer misbehaves. Separately, XWayland game flicker is the implicit-sync gap, fixed by explicit sync in xorg-xwayland >= 24.1 + wayland-protocols >= 1.34 + driver >= 555.

> ⚠️ **Risk.** Editing /etc/mkinitcpio.conf.d and re-running `mkinitcpio -P` rewrites your initramfs; if the DKMS module failed to build for the running kernel you can end up with an initramfs that references a module that does not exist and boot to a black screen. Confirm `dkms status` shows the module `installed` for every kernel before rebooting, and keep a known-good boot entry or Btrfs snapshot selectable. Loading the NVIDIA modules early also breaks resume-from-hibernation on some systems (the machine cold-boots instead of resuming) — if you hibernate, drop the MODULES line and rebuild.

**Fix.**

**1. Enable DRM modeset and early KMS.** On Arch and Omarchy this is already done by the installer; verify rather than assume:

```bash
cat /sys/module/nvidia_drm/parameters/modeset   # must print Y
```

If it prints `N`:

```bash
sudo tee /etc/modprobe.d/nvidia.conf >/dev/null <<'EOF'
options nvidia_drm modeset=1
EOF

sudo mkdir -p /etc/mkinitcpio.conf.d
sudo tee /etc/mkinitcpio.conf.d/nvidia.conf >/dev/null <<'EOF'
MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
EOF

sudo mkinitcpio -P
```

On a hybrid Intel iGPU + NVIDIA dGPU machine, load `i915` first or Electron/Chromium apps stall for up to a minute after boot: `MODULES+=(i915 nvidia nvidia_modeset nvidia_uvm nvidia_drm)`.

**2. Install the right driver set.** DKMS variants so every installed kernel is covered; headers for each kernel:

```bash
# GSP-capable (Turing/16xx/20xx and newer; mandatory on 50xx)
sudo pacman -S --needed linux-headers nvidia-open-dkms nvidia-utils lib32-nvidia-utils egl-wayland libva-nvidia-driver

# Older, pre-GSP cards - the 580xx legacy branch (AUR)
# yay -S nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils
```

This is exactly the split Omarchy's installer makes; on Omarchy check yours with `omarchy-hw-nvidia-gsp; echo $?` (0 = use nvidia-open-dkms).

**3. Environment variables** in `~/.config/hypr/hyprland.lua` (Omarchy sets these automatically in `/usr/share/omarchy/default/hypr/nvidia.lua`):

```lua
hl.env("LIBVA_DRIVER_NAME", "nvidia")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
hl.env("NVD_BACKEND", "direct")             -- "egl" on pre-GSP cards
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")   -- stops Electron/CEF flicker
```

**4. Pick the GPU explicitly on multi-GPU / hybrid boxes.** Never use bare `/dev/dri/cardN` — those numbers are reassigned at boot. Find the PCI id, then pin a udev symlink:

```bash
lspci -d ::03xx            # list display controllers
ls -l /dev/dri/by-path     # map PCI id -> cardN
```

```bash
AMD_IGPU_ID=$(lspci -d ::03xx | grep 'AMD' | cut -f1 -d' ')
printf 'KERNEL=="card*", KERNELS=="0000:%s", SUBSYSTEM=="drm", SUBSYSTEMS=="pci", SYMLINK+="dri/amd-igpu"\n' "$AMD_IGPU_ID" \
  | sudo tee /etc/udev/rules.d/amd-igpu-dev-path.rules
sudo udevadm control --reload && sudo udevadm trigger
```

```lua
-- First entry is the primary renderer. Any card that drives a monitor you
-- want to use MUST appear in this list, even if it is not primary.
hl.env("AQ_DRM_DEVICES", "/dev/dri/amd-igpu:/dev/dri/card1")
hl.env("AQ_FORCE_LINEAR_BLIT", "0")   -- last resort for a broken secondary monitor
```

**5. Cursor artefacts:**

```lua
hl.config({
  cursor = {
    use_cpu_buffer = 1,        -- required on NVIDIA for working HW cursors (default 2 = auto/nvidia)
    no_hardware_cursors = 1,   -- only if use_cpu_buffer alone does not fix it
  },
})
```

**6. Suspend/wake:** `nvidia-suspend.service`, `nvidia-hibernate.service` and `nvidia-resume.service` must be enabled (already done on Arch), and `nvidia.NVreg_PreserveVideoMemoryAllocations=1` must be on the kernel command line.

**Verify.** `cat /sys/module/nvidia_drm/parameters/modeset` prints `Y`; `hyprctl systeminfo | grep -i gpu` and `hyprctl monitors` list every physical output; `nvidia-smi` and `vainfo` both succeed; a full-screen XWayland game no longer flickers.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Multi-GPU/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/nvidia.sh> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/nvidia.lua>

---

## Clear the wall of config errors after the Hyprland windowrule syntax overhaul

`windowrule-syntax-overhaul-053-invalid-field` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** After an update, dozens of red 'Config error' lines cover the top of the screen at login, e.g. `Config error in file /home/vs/.local/share/omarchy/default/hypr/apps/hyprshot.conf at line 2: invalid field selection: missing a value`, `invalid field noscreenshare: missing a value`, `invalid field class:^(1[p|P]assword)$: missing a value`, followed by `(47 more...)`. Windows open in the wrong place, nothing floats any more.

**Cause.** Hyprland 0.53 (Dec 2025) completely rewrote the window-rule and layer-rule grammar. The old form put the rule first and the matcher second (`windowrule = float, class:foo`); the new form requires explicit `match:` props (`windowrule = match:class foo, float`). Every old-syntax line is parsed as an unknown field, hence 'invalid field <x>: missing a value'. `windowrulev2` is gone entirely. Distro/desktop config packs that still ship pre-0.53 rules produce one error per rule line.

> **Audit corrected this record.** The syntax analysis is correct and verified. hypr.land/news/update53 confirms the windowrule grammar was 'completely overhauled' in 0.53. The 0.54 archived wiki shows `windowrule = match:class my-window, border_size 10` and `layerrule = blur on, match:namespace waybar` (both orderings are accepted). Every snake_case rename in the table is confirmed against the current effects tables (no_focus, no_blur, no_anim, no_screen_share, suppress_event, border_color, scroll_touchpad, stay_focused, keep_aspect_ratio, max_size, min_size, render_unfocused, idle_inhibit, dim_around, nearest_neighbor, force_rgbx, pseudo, border_size). Cited issue #4023 is real and quotes these exact errors on Omarchy 3.2.3 / Hyprland 0.53.0-2. The Omarchy remedy is the defect: I read bin/omarchy-refresh-hyprland and bin/omarchy-refresh-config — refresh-hyprland ONLY overwrites ~/.config/hypr/*.lua from $OMARCHY_PATH/config. It never touches $OMARCHY_PATH/default/hypr/, which is where the erroring files in the symptom live. So it cannot fix this class of error. `omarchy-channel-set stable` is also a no-op for someone already on stable. The correct action is omarchy-update. Also note the record shows *.lua in a 0.53-era (hyprlang/.conf) scenario, which is anachronistic.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** On Omarchy, editing files under ~/.local/share/omarchy/default/ or /usr/share/omarchy/ works until the next update silently reverts them; put overrides in ~/.config/hypr/ instead. Switching package channels (stable/rc/edge/dev) changes which Hyprland version pacman installs and can move you to an untested set — a channel switch plus reboot is the intended flow, not a partial upgrade.

**Fix.**

Rewrite every rule using the mechanical transformation shown (that part is correct and verified against the 0.54 wiki). But replace the Omarchy section: the erroring files live under the package-owned defaults tree ($OMARCHY_PATH/default/hypr/, i.e. ~/.local/share/omarchy/default on 3.x, /usr/share/omarchy/default on 4.x). `omarchy-refresh-hyprland` only rewrites ~/.config/hypr/ from $OMARCHY_PATH/config and will NOT clear these errors. Use:

```bash
omarchy-channel-current      # informational
omarchy-update               # THIS is what ships corrected defaults
hyprctl configerrors         # confirm they are gone
```

Only reach for `omarchy-refresh-hyprland` if the remaining errors point at files under ~/.config/hypr/ (your own configs), and note it backs yours up as *.bak.<epoch>. Do not hand-edit the defaults tree — it is replaced on every update.

**Verify.** `hyprctl configerrors` prints nothing, and the red error bar is gone after `hyprctl reload`.

Sources: <https://github.com/basecamp/omarchy/issues/4023> · <https://github.com/basecamp/omarchy/issues/4058> · <https://hypr.land/news/update53> · <https://wiki.hypr.land/0.54.0/Configuring/Window-Rules/> · <https://wiki.hypr.land/Configuring/Basics/Window-Rules/>

---

## hyprlock/hypridle break after converting their .conf files to Lua

`hyprlock-hypridle-conf-not-lua` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** After migrating `hyprland.conf` to `hyprland.lua` for 0.55, the same treatment applied to `hyprlock.conf` and `hypridle.conf` kills both. The screen never locks on idle; `hypridle` exits immediately; running `hyprlock` by hand prints a config parse error and returns to the shell without locking; or `hyprlock` starts but the session is left unlocked while the machine sleeps. On Omarchy 4, `hyprlock` and `hypridle` are simply not installed and `command not found`.

**Cause.** The Lua migration in Hyprland 0.55 applies to **the compositor only**. The rest of the Hypr ecosystem — hyprlock, hypridle, hyprpaper, hyprsunset — still parses hyprlang and still reads `.conf` files. Renaming or rewriting `~/.config/hypr/hyprlock.conf` as Lua leaves hyprlock with nothing it can parse; upstream is explicit that if no config file is found in any searched path, hyprlock exits with an error and your session will not be locked. hypridle is stricter still: a config file is required and it will not run without one. Separately, Omarchy 4 "Quattro" retired both packages (they appear in the removal list in `bin/omarchy-upgrade-to-quattro`) in favour of its own Quickshell lock, so an Omarchy 3 config carried forward has nothing left to read it.

> **Audit corrected this record.** The diagnosis is right and well sourced. Vaxry's Lua-ification post states other hypr* tools "will for now continue using hyprlang"; the hyprlock wiki warns in a box that if no config file is found in any searched path hyprlock "exits with an error and your session will not be locked" (search order $XDG_CONFIG_HOME/hypr/hyprlock.conf, $HOME/.config/hypr/hyprlock.conf, XDG_CONFIG_DIRS, /etc/xdg/hypr/); the hypridle wiki says "A config file is required; hypridle won't run without one" and gives the same autostart / `systemctl --user enable --now hypridle.service` split. Both hyprlock and hypridle are genuinely in the retired-package removal list inside bin/omarchy-upgrade-to-quattro, so the Omarchy 4 'command not found' framing is accurate. The hyprlang snippets use real options (general:hide_cursor, background monitor/color, input-field size/position/halign/valign/placeholder_text, general lock_cmd/before_sleep_cmd/after_sleep_cmd, listener timeout/on-timeout/on-resume) and `hl.dsp.dpms({ action = "on"/"off" })` matches the dispatcher table's documented action values. Two defects in the fix, both copy-paste level. (1) The autostart line is wrong for a daemon: top-level Lua runs on every config load AND every reload/save, so `hl.dispatch(hl.dsp.exec_cmd("hypridle"))` stacks a new hypridle on each reload. Per the Autostart wiki the once-per-session hook is `hl.on("hyprland.start", ...)`. (2) The 'put the hyprlang versions back' step is mislabeled: `mv ~/.config/hypr/hyprlock.lua ~/.config/hypr/hyprlock.conf.bak` restores nothing — it only moves the Lua file aside (and .conf.bak is not in hyprlock's search list, which is the one thing it gets right).
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A broken hyprlock config is a security failure, not just an annoyance: hypridle's `lock_cmd` runs, hyprlock exits with a parse error, and the machine goes to sleep or sits idle **unlocked**. Never edit hyprlock.conf and walk away — run `hyprlock` from a terminal first and confirm it actually locks. Conversely, if you are already locked out by a crashed lock screen, switch to a TTY with Ctrl+Alt+F2 and `pkill hyprlock` rather than power-cycling.

**Fix.**

Keep everything as written, with two changes.

(1) Start hypridle from the documented once-per-session hook, not from top-level Lua:

```lua
-- ~/.config/hypr/autostart.lua
hl.on("hyprland.start", function()
  hl.exec_cmd("hypridle")
end)
```

On Omarchy the file's own idiom is `o.launch_on_start("hypridle")`. A bare `hl.dispatch(hl.dsp.exec_cmd("hypridle"))` at file scope re-executes on every config reload and leaves a pile of daemons; under uwsm use `systemctl --user enable --now hypridle.service` instead of either.

(2) Relabel the restore step — moving the Lua file aside is only cleanup, not a restore:

```bash
ls -la ~/.config/hypr/                  # find hyprlock.lua / hypridle.lua you created
mv ~/.config/hypr/hyprlock.lua ~/.config/hypr/hyprlock.lua.bak   # get the unparseable file out of the way
# then either restore your pre-migration hyprlock.conf / hypridle.conf from backup,
# or write the two hyprlang files below from scratch.
```

On Omarchy 4 the packages are gone, so nothing will read those files until you deliberately `sudo pacman -S --needed hyprlock hypridle` — which the record correctly advises against unless you mean to replace omarchy-shell's lock.

**Verify.** `hyprlock` run from a terminal locks the screen and unlocks with your password (exit code 0, nothing on stderr). `hypridle` run in the foreground prints no parse errors and locks the session after the configured timeout.

Sources: <https://wiki.hypr.land/Hypr-Ecosystem/hyprlock/> · <https://wiki.hypr.land/Hypr-Ecosystem/hypridle/> · <https://wiki.hypr.land/Configuring/Start/> · <https://github.com/hyprwm/Hyprland/releases/tag/v0.55.0> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-upgrade-to-quattro> · <https://wiki.archlinux.org/title/Hyprland>

---

## Get out of Hyprland emergency mode when a Lua error registered no binds

`hyprland-emergency-mode-no-binds-registered` · severity: **high** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`

**Symptom.** A banner sits on top of every workspace: `Emergency mode tripped: A lua config error resulted in no binds being registered. Emergency binds active: SUPER + Q -> any known terminal, SUPER + R -> hyprland-run, SUPER + M -> Exit` followed by `Your config has errors:` and a Lua stack traceback such as `cannot open /usr/share/omarchy/default/hypr/bootstrap.lua: No such file or directory`. None of your normal keybindings work.

**Cause.** Hyprland 0.56 trips emergency mode when a Lua config error kills execution before any bind is registered. Common triggers: a `require()`/`dofile()` of a path that does not exist (a typo, or a file that vanished for a moment while pacman replaced the package that owns it during `omarchy update`), or a syntax error early in `hyprland.lua`. Because `require()` scope protection does not cover module loading, one missing module kills the whole file.

> ⚠️ **Risk.** `debug:suppress_errors = true` hides real config errors — turn it back off. Do not reboot to 'fix' this while a pacman transaction is still running; you can end up with a half-applied upgrade.

**Fix.**

Use the emergency binds to get a terminal: press SUPER + Q.

Read the actual error:
```bash
hyprctl configerrors
tail -n 200 "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log"
```

If it was a transient mid-update file, just reload once the update finished:
```bash
hyprctl reload
```

If a module really is optional, wrap it so it cannot take the config down:
```lua
local ok, err = pcall(require, "maybe-nonexistent")
if not ok then
  hl.notification.create({ text = "skipped module: " .. tostring(err), timeout = 4000 })
end
```

To stop reloads firing during a package transaction at all:
```bash
hyprctl eval 'hl.config({ misc = { disable_autoreload = true }, debug = { suppress_errors = true } })'
# ... run the update ...
hyprctl eval 'hl.config({ misc = { disable_autoreload = false }, debug = { suppress_errors = false } })'
hyprctl reload
```

Last resort on Omarchy, restore shipped configs:
```bash
omarchy-refresh-hyprland
hyprctl reload
```

**Verify.** The emergency banner disappears, `hyprctl configerrors` is empty, and `hyprctl binds` lists your bindings again.

Sources: <https://github.com/basecamp/omarchy/issues/8637> · <https://wiki.hypr.land/Configuring/Start/> · <https://wiki.hypr.land/Crashes-and-Bugs/>

---

## Fix os.execute failing with 'no child processes' in a Lua Hyprland config

`lua-config-os-execute-no-child-processes` · severity: **high** · frequency: **occasional** · applies to: `amd`, `arch`, `desktop`, `hyprland`, `intel`, `laptop`, `nvidia`, `omarchy`

**Symptom.** Conditional logic in a Lua Hyprland config never takes the branch it should. A shell probe that exits 0 when run manually reports failure from inside the config. Debugging shows `os.execute("true")` returning `nil, "No child processes", 10`. On Omarchy 4.0.0 the visible effect was that `NVD_BACKEND`, `LIBVA_DRIVER_NAME` and `__GLX_VENDOR_LIBRARY_NAME` were never set for NVIDIA GPUs.

**Cause.** Hyprland reaps or ignores SIGCHLD for its own children, so the `wait()` inside Lua's `os.execute()` can never find the process it just forked. `os.execute()` therefore always fails to retrieve an exit status (classic ECHILD) when called from Hyprland's Lua config context. Anything that shells out and branches on success is silently always-false. `io.open()` and `io.popen()` (reading output, not exit status) still work.

**Fix.**

Do not branch on `os.execute()` exit status inside the config. Read the answer instead of testing it.

Read sysfs / files directly:
```lua
local function has_nvidia()
  local f = io.popen("lspci -nn 2>/dev/null")
  if not f then return false end
  local out = f:read("*a") or ""
  f:close()
  return out:match("NVIDIA") ~= nil
end

if has_nvidia() then
  hl.env("LIBVA_DRIVER_NAME", "nvidia")
  hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
  hl.env("NVD_BACKEND", "direct")
end
```
Or have the script print a token and test the output:
```lua
local f = io.popen("my-detector && echo YES")
local ok = (f:read("*a") or ""):match("YES") ~= nil
f:close()
```

Confirm the env vars actually landed:
```bash
hyprctl dispatch 'hl.dsp.exec_cmd("env > /tmp/envtest.txt")'
grep -E 'NVD_BACKEND|LIBVA_DRIVER_NAME|__GLX_VENDOR_LIBRARY_NAME' /tmp/envtest.txt
systemctl --user show-environment | grep -E 'NVD_BACKEND|LIBVA_DRIVER_NAME'
```

On Omarchy, this specific bug is fixed in v4.0.1 — update rather than patching:
```bash
omarchy-update    # or: Update > Omarchy from the menu
```

**Verify.** `grep NVD_BACKEND /tmp/envtest.txt` (produced by the dispatch above) shows the value, and `systemctl --user show-environment` lists it after a full session restart.

Sources: <https://github.com/basecamp/omarchy/issues/7755> · <https://wiki.hypr.land/Configuring/Start/>

---

## Fix the autogenerated-config banner and lost Omarchy look after an update

`omarchy-lua-configs-with-older-hyprland` · severity: **high** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`

**Symptom.** After updating Omarchy 3.7.0 -> 3.8.0 and rebooting, Hyprland comes up with the yellow 'autogenerated config' banner and none of the Omarchy look, keybindings or window rules apply.

**Cause.** Omarchy 3.8.0 shipped the new Hyprland 0.55 Lua configs, but the Omarchy stable pacman mirror was still pinned to hyprland 0.54.3. A 0.54 binary cannot parse `hyprland.lua`, finds no usable config, and falls back to its own autogenerated one. It is a channel/version skew, not a broken config.

> **Audit corrected this record.** The diagnosis is real and the cited issue is genuine: omarchy #5797 'Omarchy 3.8.0 breaks hyprland' says exactly this — 3.8.0 shipped Lua configs for 0.55 while the stable mirror still pointed at 0.54.3, producing the autogenerated-config banner — and the reporter's own workaround was `omarchy refresh pacman edge` + reboot. omarchy-channel-current and omarchy-channel-set both exist in bin/ and omarchy-channel-set carries `omarchy:requires-sudo=true`, so the sudo is right. Two problems. First, this is a May 2026 skew that stable resolved long ago; on any current system the first move is `omarchy-update`, not a channel switch. Second, and more serious, the record understates what a channel switch does: I read bin/omarchy-channel-set — 'edge' does not merely repoint a mirror, it swaps the installed packages to omarchy-dev + omarchy-settings-dev. Going back with `omarchy-channel-set stable` swaps them back AND returns the pacman mirror to stable, which means Hyprland gets downgraded — reintroducing the exact 0.54-can't-parse-Lua breakage if stable has not actually caught up yet. 'Once stable catches up, move back' needs to be a hard precondition, not an afterthought.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Switching to `edge` or `dev` pulls less-tested packages system-wide, not just Hyprland. `dev` links Omarchy to a git checkout in ~/omarchy and is for Omarchy developers only. Never mix mirrors by hand — that is how you get a partial upgrade.

**Fix.**

Diagnose first — this is almost always already fixed:
```bash
hyprctl version | head -1
pacman -Q hyprland
omarchy-channel-current
omarchy-update          # try this FIRST; stable has long since caught up
```

Only if `omarchy-update` genuinely leaves you with Lua configs and a pre-0.55 Hyprland is a channel switch warranted. Understand what it does: `omarchy-channel-set edge` replaces the `omarchy`/`omarchy-settings` packages with `omarchy-dev`/`omarchy-settings-dev` and moves you to the edge repo — it is a package swap, not a mirror tweak.

```bash
sudo omarchy-channel-set edge
reboot
```

Before going back, CHECK that stable actually carries a Hyprland new enough for the configs you have, or you will downgrade Hyprland straight back into the same breakage:
```bash
omarchy-channel-current
# verify stable's hyprland >= the version your configs need, THEN:
sudo omarchy-channel-set stable
reboot
```

`omarchy-refresh-hyprland` restores ~/.config/hypr/*.lua from the shipped defaults and backs yours up as *.bak.<epoch> (verified in bin/omarchy-refresh-config) — but it will not help if the installed Hyprland cannot parse Lua at all.

**Verify.** `hyprctl version` reports >= 0.55.0, the autogenerated banner is gone, and your Omarchy keybindings (SUPER+Return etc.) work.

Sources: <https://github.com/basecamp/omarchy/issues/5797> · <https://hypr.land/news/26_lua> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-refresh-hyprland>

---

## Fix apps taking 20 seconds to open and file pickers never appearing

`autostart-apps-slow-portal-dbus-environment` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Apps take 15-25 seconds to open after login, file pickers hang or never appear, and screen sharing does not work — but everything is fine if you restart the app later. Sometimes accompanied by multiple xdg-desktop-portal implementations running.

**Cause.** Portals and systemd user services are started before Hyprland has exported `WAYLAND_DISPLAY` and `XDG_CURRENT_DESKTOP` into the D-Bus/systemd activation environment, so `xdg-desktop-portal` picks the wrong backend or blocks waiting for one, and every portal call waits out its timeout.

**Fix.**

Export the environment on Hyprland start, before anything that needs a portal.

Lua (0.55+):
```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE")
end)
```
hyprlang:
```ini
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE
```

If portals still launch too early, restart them after a delay — the FAQ's own workaround:
```bash
#!/usr/bin/env bash
sleep 4
killall -e xdg-desktop-portal-hyprland
killall xdg-desktop-portal
/usr/lib/xdg-desktop-portal-hyprland &
sleep 4
/usr/lib/xdg-desktop-portal &
```
Save as `~/.local/bin/fix-portals.sh`, `chmod +x`, and run it from autostart.

Check for competing implementations:
```bash
pacman -Qs xdg-desktop-portal
systemctl --user status 'xdg-desktop-portal*'
systemctl --user show-environment | grep -E 'WAYLAND_DISPLAY|XDG_CURRENT_DESKTOP'
```
Remove portal backends you do not use (e.g. `xdg-desktop-portal-gnome` on a Hyprland-only box).

**Verify.** `systemctl --user show-environment` lists `WAYLAND_DISPLAY` and `XDG_CURRENT_DESKTOP=Hyprland`; a GTK file dialog opens instantly.

Sources: <https://wiki.hypr.land/FAQ/> · <https://wiki.hypr.land/Configuring/Basics/Autostart/>

---

## Cut Hyprland's idle GPU use, fan noise and battery drain from blur

`blur-animations-battery-and-stutter` · severity: **medium** · frequency: **very-common** · applies to: `amd`, `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** Hyprland feels laggy, the fans spin up while idle, or the laptop's battery drains noticeably faster than under a plain WM. GPU usage sits high with nothing on screen.

**Cause.** Two different costs, worth separating. `*angle` animations using the `loop` style force Hyprland to render new frames continuously at the monitor's refresh rate - and the wiki warns this applies even when animations are otherwise disabled or the affected decoration is not visible. Blur (including blur on the special workspace and popups) and shadows are expensive *per frame* but do not by themselves force frames to be drawn. Fractional monitor scaling adds further GPU cost. On Intel iGPU laptops, TLP's aggressive default GPU floor causes stutter independent of Hyprland.

> **Audit corrected this record.** Most of this is confirmed, some of it verbatim. The Performance wiki's fractional-scaling advice is character-for-character the record's monitor line: 'try setting the scaling to integer numbers such as 1 or 2 like in this example hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 2 })'. The TLP section matches too, including the exact keys INTEL_GPU_MIN_FREQ_ON_AC / _ON_BAT in /etc/tlp.conf and the 300->500 bump. The blur/shadow disable lines match the wiki's 'Useful Optimizations'. Every blur sub-option is real (new_optimizations 'Recommended to leave on, as it will massively improve performance'; xray 'Only available if new_optimizations is true'; special 'note: expensive'; popups). config/hypr/looknfeel.lua does exist in the omarchy repo as a user override file. The error is in the cause paragraph: it attributes continuous full-refresh-rate rendering to blur, and then attaches the wiki's 'even when animations are disabled or the decoration is not visible' warning to that claim. That warning belongs solely to *angle loop animations. The Animations wiki says: 'Using the loop style for *angle animations requires Hyprland to constantly render new frames at a frequency equal to your screen's refresh rate... This will apply even if animations are disabled or the affected decorations are not visible.' Blur is expensive per frame but does not force frames; conflating them will send someone hunting the wrong thing.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

All the settings are correct — only the cause needs splitting into its two distinct mechanisms, because they have different fixes:

1. `*angle` loop animations (borderangle / shadowangle / glowangle with style = "loop") are the ones that force continuous rendering at your full refresh rate. The wiki's warning is specific to these: it applies 'even if animations are disabled or the affected decorations are not visible'. This is the one to hunt first on a laptop — it burns GPU on a completely idle screen.

```bash
grep -rnE 'borderangle|shadowangle|glowangle' ~/.config/hypr/
```
Remove any `loop` style; the default is `once`.

2. Blur and shadows do NOT force frames — they make each frame more expensive. They cost you when something is actually redrawing. Disable or tune them as the record shows (the blur { new_optimizations = true, xray = true, special = false, popups = false } block is correct and matches the wiki's own notes).

3. Fractional monitor scale and the Intel iGPU + TLP floor are separate, independent causes — both as the record describes.

On Omarchy, ~/.config/hypr/looknfeel.lua is the right place; it is a shipped user override file.

**Verify.** `hyprctl getoption decoration:blur:enabled` reports 0; GPU utilisation drops to near zero on an idle desktop (`intel_gpu_top` / `nvtop` / `radeontop`).

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Performance/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Animations/> · <https://github.com/basecamp/omarchy/blob/master/config/hypr/looknfeel.lua>

---

## Mouse cursor is invisible, enormous, or the wrong theme in XWayland apps

`cursor-invisible-giant-or-wrong-theme` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hidpi`, `hyprland`, `manjaro`, `nouveau`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Any of: the pointer vanishes entirely (often on older NVIDIA cards running nouveau, or only over certain surfaces); the pointer is gigantic in GIMP, Steam or pavucontrol while normal everywhere else; the pointer is the default black X11 cross in XWayland apps but your chosen theme in Wayland apps; or the pointer is literally the Hyprland logo.

**Cause.** Three unrelated mechanisms all showing up as "the cursor is wrong". (1) **Hardware cursor plane.** The compositor hands the pointer to a DRM cursor plane; nouveau does not display it on many older NVIDIA GPUs, so the pointer is composited nowhere and you see nothing. (2) **Two cursor systems.** Hyprland prefers hyprcursor (`HYPRCURSOR_THEME`/`HYPRCURSOR_SIZE`); apps that do not support server-side cursors — GTK in particular — fall back to XCursor and read `XCURSOR_THEME`/`XCURSOR_SIZE` plus the GTK gsettings key. Set one and not the other and you get a split. If neither resolves to an installed theme, Hyprland draws its own logo. (3) **Size on scaled outputs.** `XCURSOR_SIZE` is a fixed pixel number; with `xwayland:force_zero_scaling` on, the XWayland side is unscaled, so a size chosen for a 2x display looks enormous in X11 apps.

**Fix.**

**Invisible pointer — disable the hardware cursor plane.** Add to `~/.config/hypr/looknfeel.lua` (Omarchy) or `hyprland.lua`:

```lua
hl.config({
  cursor = {
    no_hardware_cursors = true,
  },
})
```

This is precisely what Omarchy's installer appends to `~/.config/hypr/looknfeel.lua` when it detects `Kernel driver in use: nouveau`. Confirm you are on nouveau with `lspci -k | grep -A3 -i vga`. On the proprietary NVIDIA driver, try `cursor { use_cpu_buffer = 1 }` first — that is the supported way to keep HW cursors working there.

**Wrong or split theme — set both systems and GTK.** Install a theme (hyprcursor themes go in `~/.local/share/icons` or `~/.icons`, *not* `/usr/share/icons`), then:

```lua
hl.env("HYPRCURSOR_THEME", "Bibata-Modern-Classic")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("XCURSOR_THEME", "Bibata-Modern-Classic")
hl.env("XCURSOR_SIZE", "24")
```

GTK ignores all four; it needs gsettings:

```bash
gsettings set org.gnome.desktop.interface cursor-theme 'Bibata-Modern-Classic'
gsettings set org.gnome.desktop.interface cursor-size 24
# if gsettings schemas are unavailable:
# dconf write /org/gnome/desktop/interface/cursor-theme "'Bibata-Modern-Classic'"
```

Apply live without a relogin (note: since 0.37 `setcursor` takes **hyprcursor** themes only; legacy XCursor themes must go through the env vars):

```bash
hyprctl setcursor Bibata-Modern-Classic 24
```

**Flatpak apps with the wrong cursor:**

```bash
flatpak override --user --filesystem=~/.themes:ro --filesystem=~/.icons:ro
```

Omarchy 4 ships `XCURSOR_SIZE=24` and `HYPRCURSOR_SIZE=24` in `/usr/share/omarchy/default/hypr/envs.lua`; override them in `~/.config/hypr/looknfeel.lua`, which is loaded after the defaults.

Env vars only reach apps launched afterwards — `hyprctl reload`, then restart the app.

**Verify.** `hyprctl getoption cursor:no_hardware_cursors` reflects your setting; the pointer is visible and correctly sized over a fullscreen XWayland app (GIMP or Steam) and over a native Wayland one (nautilus/foot) at the same time.

Sources: <https://wiki.hypr.land/Hypr-Ecosystem/hyprcursor/> · <https://wiki.hypr.land/FAQ/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://github.com/hyprwm/Hyprland/issues/7349> · <https://github.com/basecamp/omarchy/blob/quattro/install/user/hardware/fix-nouveau-cursor.sh> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://wiki.archlinux.org/title/Hyprland>

---

## hyprctl keyword silently does nothing under a Lua config — use eval / repl

`hyprctl-keyword-noop-under-lua` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Scripts, waybar modules, GUI display panels and copy-pasted one-liners that call `hyprctl keyword monitor DP-1,disable` or `hyprctl keyword general:border_size 10` return no visible result and change nothing. Running it by hand appears to succeed. The error only shows on stderr, which most callers throw away: `keyword can't work with non-legacy parsers. Use eval.` The most reported instance is Omarchy's Display panel, where clicking a monitor row to disable or re-enable it does nothing at all.

**Cause.** `hyprctl keyword` drives the legacy hyprlang parser. Since 0.55 a `hyprland.lua` config uses the Lua config provider and the keyword path has nothing to write into, so the command changes nothing: on 0.55 the compositor answers `keyword can't work with non-legacy parsers. Use eval.`, and on 0.56+ `keyword` is not a registered IPC command at all, so the answer is `unknown request`. The trap is the exit code, not the stream: hyprctl prints the compositor's reply on STDOUT and only returns non-zero when that reply starts with `error:` — neither of these does, so the call exits 0. Anything that tests `$?` (a shell `if`, a Qt/Quickshell Process, a bar module) sees success, while a `$(...)` capture does receive the refusal text and usually discards it as uninteresting output. `hyprctl dispatch` has the same split: the classic `hyprctl dispatch workspace 3` form is rejected and must be given as a Lua expression.

> **Audit corrected this record.** The core advice is right and the replacement commands are correct: eval/dispatch take Lua expressions, single-quoting the outer string is the right shell hygiene, `hyprctl repl` is a real interactive Lua REPL (Ctrl+D to exit) and the wiki's own examples are `hyprctl repl 'hl.get_active_window().class'` and the get_windows loop, `hyprctl getoption` uses section.option dotted form, nothing set with eval survives a reload, and the quoted 0.55 error string is exact — src/debug/HyprCtl.cpp at tag v0.55.0 contains `return "keyword can't work with non-legacy parsers. Use eval.";`. But the stated mechanism is wrong and so is one command. Reading hyprctl/src/main.cpp: the reply is printed by `log()` -> `std::println` i.e. STDOUT, and `request()` returns non-zero (7) only when the reply starts with `error:`. Neither the 0.55 keyword message nor 0.56's reply starts with `error:`, so the exit code is 0 and the text lands on stdout — meaning a `$(...)` capture actually DOES receive the message, while callers that check `$?` are the ones fooled. The record has the failure inverted. Also, on current main `keyword` is no longer a registered socket1 command at all (src/ipc/s1/Commands.cpp registers dispatch/eval/repl/getoption/... but no keyword), so src/ipc/s1/S1.cpp answers `unknown request`. Finally `hyprctl descriptions | jq -r '.[].value'` is wrong: Config::Values::getAsJson emits objects with `name`, `description`, `default`, `current` — there is no `value` key (and no type/range keys), so that pipeline prints a column of nulls.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `hyprctl eval 'hl.monitor({ output = "...", disabled = true })'` takes effect instantly and, on a single-monitor machine, blanks your only display with no config file to reload from. Test monitor changes with a second display attached, or be ready to reach a TTY (Ctrl+Alt+F2) and run `hyprctl -i 0 eval 'hl.monitor({ output = "eDP-1", disabled = false })'`. `hyprctl reload full-reset` recreates the whole config context and should not be used unless genuinely necessary.

**Fix.**

Keep every replacement command as written — `hyprctl eval 'hl.monitor({ output = "DP-1", disabled = true })'`, `hyprctl eval 'hl.config({ general = { border_size = 10 } })'`, `hyprctl eval 'hl.workspace_rule({ workspace = "2", layout = "scrolling" })'`, `hyprctl dispatch 'hl.dsp.focus({ workspace = "3" })'`, single quotes outside so the inner double quotes survive the shell. Two fixes.

1. Check the result correctly. Unlike `keyword`, a failing `hyprctl eval` DOES reply with a string starting `error:` and hyprctl exits 7, so the exit code is trustworthy here — and the reply is on stdout, so `2>&1` is belt-and-braces rather than the point:

```bash
if ! out=$(hyprctl eval 'hl.config({ general = { border_size = 10 } })'); then
  printf 'hyprctl eval failed: %s\n' "$out" >&2
fi
[ "$out" = "ok" ] || printf 'unexpected reply: %s\n' "$out" >&2
```

When auditing an old script, do not trust `$?` on the `keyword` call it is replacing: that one exits 0 while doing nothing.

2. Enumerate options with `.name`, not `.value` — `hyprctl descriptions` entries are `{name, description, default, current}`:

```bash
hyprctl descriptions | jq -r '.[].name' | head          # every option name
hyprctl descriptions | jq -r '.[] | "\(.name) = \(.current)  (default \(.default))"' | head
hyprctl getoption general.border_size
hyprctl configerrors
```

**Verify.** `hyprctl eval 'hl.config({ general = { border_size = 10 } })'` prints `ok` and the change is visible immediately; `hyprctl getoption general.border_size` reports 10; `hyprctl reload` reverts it to your configured value.

Sources: <https://github.com/basecamp/omarchy/issues/6968> · <https://github.com/hyprwm/Hyprland/discussions/14525> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://wiki.hypr.land/0.54.0/Configuring/Using-hyprctl/> · <https://wiki.hypr.land/Configuring/Start/>

---

## $mainMod and source= have no direct Lua equivalent after the 0.55 migration

`hyprlang-variables-and-source-to-lua` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Half-migrated config throws errors on reload: `attempt to index a nil value (global 'o')`, `attempt to call a nil value`, `attempt to concatenate a nil value (global 'mainMod')`, or `module 'modules.monitors' not found`. Symptoms in the session: whole blocks of keybinds silently missing, the Hyprland emergency-binds banner, or one file's worth of settings gone while the rest applied. Requiring an absolute path produces a mangled result like `/home/you//~/.config/wal/colors-hyprland.lua`.

**Cause.** hyprlang's `$name = value` was text substitution and `source = ./other.conf` was a textual include; Lua has neither. `$mainMod` becomes an ordinary Lua local and obeys Lua scope — a local in `hyprland.lua` is NOT visible inside a file you `require()`, because Hyprland deliberately gives each required file its own scope so an error in one does not kill the others. `source =` becomes `require()`, which resolves module names against package.path relative to `hyprland.lua`, accepts `.` or `/` as the separator, and supports wildcards. require also accepts ABSOLUTE paths — the wiki's own example is `require("/usr/share/among/us.lua")`, extension included — so absoluteness is not the problem; the problem is that `~` is never expanded, so `require("~/.cache/wal/colors-hyprland")` gets glued onto the config directory and yields a path like `/home/you//~/.cache/...`. And a missing module is one of the few errors require()'s protection does not cover: `require("nonexistent")` throws in the calling file and kills the rest of it.

> **Audit corrected this record.** Most of this is solid and matches the Start Here page: require() gives each file its own Lua scope so an error in one does not stop the others; a MISSING module is the documented exception ("require(\"nonexistent\") in your main Hyprland config will kill the execution of your main config") and pcall is the wiki's own remedy; `.` and `/` are both valid separators; wildcards are supported; hyprlang `$var` really has no Lua equivalent so locals + a module returning a table is the right port. The Omarchy 4 ordering block is verbatim correct — quattro's config/hypr/hyprland.lua opens with `dofile((os.getenv("OMARCHY_PATH") or "/usr/share/omarchy") .. "/default/hypr/bootstrap.lua")`, then `require("default.hypr.omarchy")`, then hypr.monitors / hypr.input / hypr.bindings / hypr.looknfeel / hypr.autostart (the real file also ends with `require("default.hypr.toggles")`), so `o.*` being nil in a carried-over Omarchy 3 config is a genuine failure mode. The defect is the absolute-path claim: the wiki explicitly documents `require("/usr/share/among/us.lua")` alongside `require("./stuff/*")`, i.e. require DOES take absolute paths and DOES accept a .lua extension there. What it does not do is expand `~`. The record generalizes the tilde bug into a false rule about absoluteness and prints it as the reason to reach for loadfile.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A syntax error early in hyprland.lua means no binds get registered at all. Hyprland catches this and gives you emergency binds (SUPER+Q terminal, SUPER+R run, SUPER+M exit), but if you have rebound SUPER or run a non-standard terminal you can end up in a session you cannot drive. Before a big migration, confirm you can reach a TTY with Ctrl+Alt+F2, and test with `Hyprland --verify-config` rather than by logging out.

**Fix.**

Same as written, except the absolute-path section. Absolute paths work fine with require — it is `~` that does not expand:

```lua
-- WRONG: ~ is never expanded -> /home/you//~/.cache/...
-- require("~/.cache/wal/colors-hyprland")

-- Fine: require takes an absolute path, extension included
require(os.getenv("HOME") .. "/.cache/wal/colors-hyprland.lua")
```

For a generated file that may not exist yet (pywal, theme output), still prefer `loadfile` — not because the path is absolute, but because loadfile returns nil instead of throwing and so cannot take the rest of the file down with it:

```lua
local chunk = loadfile(os.getenv("HOME") .. "/.cache/wal/colors-hyprland.lua")
if chunk then chunk() end
```

Everything else in the record stands: locals + a module that returns a table for shared variables, `require("monitors")` / `require("modules.binds")` / `require("./themes/*")` for includes, `pcall(require, "maybe-missing")` for optional ones, the Omarchy bootstrap ordering, and `hyprctl reload && hyprctl configerrors` / `hyprctl binds` to confirm.

**Verify.** `hyprctl configerrors` is empty, `hyprctl binds` lists binds originating from every required file, and `Hyprland --verify-config` exits 0.

Sources: <https://wiki.hypr.land/Configuring/Start/> · <https://wiki.hypr.land/Configuring/Basics/Binds/> · <https://github.com/hyprwm/Hyprland/discussions/14396> · <https://github.com/basecamp/omarchy/issues/5879> · <https://github.com/hyprwm/Hyprland/releases/tag/v0.55.0> · <https://github.com/basecamp/omarchy/blob/quattro/config/hypr/hyprland.lua> · <https://wiki.hypr.land/0.54.0/Configuring/Using-hyprctl/>

---

## Keyboard layout, caps:escape and touchpad settings are ignored under Hyprland

`keyboard-layout-not-applied-hyprland` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** `setxkbmap fr` has no effect, `localectl status` shows the right layout but Hyprland still types QWERTY, `/etc/X11/xorg.conf.d/00-keyboard.conf` is ignored, and `caps:escape` / `compose:caps` never engage. On a laptop: two-finger right-click, natural scrolling and disable-while-typing behave nothing like they did before. On Omarchy, editing `~/.config/hypr/input.lua` appears to do nothing because everything in it is still commented out.

**Cause.** Hyprland is a Wayland compositor: it programs the keymap through libxkbcommon itself and never reads `/etc/X11/xorg.conf.d/00-keyboard.conf`, and `setxkbmap` only touches an already-running X server, which Hyprland is not. Input settings live in the compositor's own `input` section, plus optional per-device blocks. Two further traps: keybinds resolve against the **first** entry in a comma-separated `kb_layout` unless you set `resolve_binds_by_sym`, and a per-device layout does not change the keybind keymap at all. On Omarchy 4, `/usr/share/omarchy/default/hypr/input.lua` derives `kb_layout`/`kb_variant` from `XKBLAYOUT`/`XKBVARIANT` in `/etc/vconsole.conf` and prepends `us,` for layouts that cannot type Latin letters — so the layout you want may be set system-wide and still not be first.

> ⚠️ **Risk.** Setting a single non-Latin `kb_layout` (ru, gr, th, ua, ...) with no Latin layout first means keybinds that use Latin keysyms stop firing — including your terminal and launcher binds — leaving a desktop you cannot drive. Always lead with a Latin layout (`kb_layout = "us,ru"`) and add a switch option such as `grp:alts_toggle`, which is exactly what Omarchy does for you at install time.

**Fix.**

**Set it in the compositor.** Plain Hyprland — `~/.config/hypr/hyprland.lua`; Omarchy — uncomment the block in `~/.config/hypr/input.lua`, which is loaded after Omarchy's defaults and overrides them:

```lua
hl.config({
  input = {
    kb_layout  = "us,fr",
    kb_variant = ",",                 -- one comma-separated entry per layout, or one for all
    kb_model   = "",
    kb_options = "grp:alt_shift_toggle,caps:escape",
    kb_rules   = "",

    numlock_by_default = true,
    repeat_rate  = 40,
    repeat_delay = 250,

    follow_mouse = 1,
    sensitivity  = 0,                 -- -1.0 .. 1.0
    accel_profile = "flat",           -- "adaptive" | "flat" | "custom"

    touchpad = {
      natural_scroll        = true,
      disable_while_typing  = true,
      clickfinger_behavior  = true,   -- 2-finger = right click
      tap_to_click          = true,
      scroll_factor         = 0.4,
    },
  },
})
```

Valid layout/variant/option names:

```bash
localectl list-x11-keymap-layouts
localectl list-x11-keymap-variants fr
localectl list-x11-keymap-options | grep -E '^(caps|grp|compose):'
# or read /usr/share/X11/xkb/rules/evdev.lst directly
```

**Per-device settings** (an external keyboard, a second mouse) — get the exact name from `hyprctl devices`, then:

```bash
hyprctl devices
```

```lua
hl.device({
  name = "logitech-mx-master-3",
  sensitivity   = -0.2,
  accel_profile = "flat",
  natural_scroll = false,
})

hl.device({
  name = "my-external-keyboard",
  kb_layout = "us,pl,de",
})
```
Every `input` option works inside `hl.device` except `force_no_accel` and the window-management ones (`follow_mouse`, `mouse_refocus`, `special_fallthrough`, ...).

**Switch layouts at runtime:**

```bash
hyprctl switchxkblayout at-translated-set-2-keyboard next
hyprctl switchxkblayout current 1
hyprctl switchxkblayout all next
```

**Keybinds firing on the wrong layout.** By default binds resolve against the first `kb_layout` entry. Either keep a Latin layout first (what Omarchy does automatically), or opt into symbol-based resolution:

```lua
hl.config({ input = { resolve_binds_by_sym = true } })
```

**Omarchy: change the system layout so the default picks it up:**

```bash
sudo localectl set-x11-keymap fr
grep XKB /etc/vconsole.conf      # XKBLAYOUT=fr should now be there
hyprctl reload
```

Test a value live before writing it:

```bash
hyprctl eval 'hl.config({ input = { kb_options = "caps:escape" } })'
```

**Verify.** `hyprctl getoption input.kb_layout` and `hyprctl getoption input.kb_options` return what you set; `hyprctl devices` shows each keyboard with the expected `active keymap`; typing in a terminal produces the right characters and Caps Lock behaves as configured.

Sources: <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Devices/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://wiki.archlinux.org/title/Xorg/Keyboard_configuration> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/input.lua> · <https://github.com/basecamp/omarchy/blob/quattro/config/hypr/input.lua>

---

## hl.monitor() does nothing: wrong connector name, or a mode the driver never advertised

`monitor-config-ignored-name-or-mode` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** "My monitor config is just ignored." `hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@144", position = "0x0", scale = 1 })` sits in monitors.lua, the file saves, no error appears in `hyprctl configerrors` — and the display still runs at 60 Hz, or at 1366x768, or the external screen never lights up at all. Sometimes instead you get an on-screen warning about overlapping monitors, or "Invalid scale passed to monitor".

**Cause.** Three separate failures all present as "the rule did nothing". (1) The `output` string does not match a real connector. Names are assigned by the kernel and shift between boots, docks and GPUs — a monitor on `HDMI-A-2` will never be touched by a rule for `HDMI-A-1`, and a rule for an output that does not exist is silently inert. (2) The `mode` is not one the driver reports. Hyprland can only program modes the DRM connector advertises from the EDID; a mode you invented, or one a KVM/long cable/cheap adapter stripped out of the EDID, is rejected and the monitor falls back to preferred. As the maintainer put it: "if the mode is not listed in hyprctl monitors there's nothing hyprland can do. Custom modelines might or might not work. It's all down to the driver." (3) The `scale` does not divide the resolution into whole logical pixels — 1920x1080 / 1.5 = 1280x720 is fine, / 1.4 = 1371.43x771.43 is not — so Hyprland refuses it and warns. Plain `hyprctl monitors` also hides disabled outputs and mirrors, so the connector you need may not even appear in the list you are reading.

> ⚠️ **Risk.** `disabled = true` does not just blank the screen — it removes the output from the layout and migrates all of its windows and workspaces onto the remaining monitors. Disabling your only display leaves you with no way back except Ctrl+Alt+F2 to a TTY (then `hyprctl -i 0 eval 'hl.monitor({ output = "eDP-1", disabled = false })'`, or edit monitors.lua and reboot). Use the `dpms` dispatcher if you only want the panel powered off. On Omarchy, `omarchy-hw-recover-internal-monitor` exists for exactly this.

**Fix.**

First, get the truth from the compositor. `all` is load-bearing — plain `hyprctl monitors` omits disabled and mirrored outputs:

```bash
hyprctl monitors all          # every output, plus every mode the driver actually offers
hyprctl -j monitors all | jq  # same thing, easier to grep
```

Copy the connector name and one of the listed `availableModes` entries verbatim into `~/.config/hypr/monitors.lua` (Omarchy) or `~/.config/hypr/hyprland.lua` (plain Hyprland):

```lua
-- Exact name, and a mode that appears in `hyprctl monitors all`
hl.monitor({ output = "DP-2", mode = "2560x1440@143.97", position = "0x0", scale = 1 })

-- Connector names shuffle between docks and boots. Match the EDID description
-- instead: take the `description:` line from `hyprctl monitors` and DROP the
-- trailing "(DP-2)" portname.
hl.monitor({ output = "desc:Dell Inc. DELL U2720Q 8FGZ043", mode = "highrr", position = "auto", scale = 1 })

-- Stop guessing modes. preferred = EDID preferred, highres = highest resolution,
-- highrr = highest refresh rate, maxwidth = widest mode.
-- An empty output is the catch-all fallback; keep it LAST in the file.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

-- Rotated panel: 0 normal, 1 = 90 deg, 2 = 180, 3 = 270, 4-7 = flipped variants
hl.monitor({ output = "DP-3", mode = "preferred", position = "auto", scale = 1, transform = 1 })

-- Mirror the laptop panel onto an external (mirrors do NOT show in plain `hyprctl monitors`)
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "0x0", scale = 1, mirror = "eDP-1" })

-- Remove an output from the layout entirely
hl.monitor({ output = "eDP-1", disabled = true })
```

Try a rule live before committing it to a file — under a Lua config this is `eval`, not `keyword`:

```bash
hyprctl eval 'hl.monitor({ output = "DP-2", mode = "2560x1440@143.97", position = "0x0", scale = 1 })'
```

Positions are in **scaled** pixels: a 3840-wide monitor at scale 2 occupies 1920 logical px, so the next monitor starts at `1920x0`, not `3840x0`. Y is inverted — negative y is up. No two monitors may overlap.

On Omarchy 4 use the shipped tooling instead of hand-editing where one exists:

```bash
omarchy-hyprland-monitor-scaling 1.6      # sets the focused monitor's scale AND GDK_SCALE, persists to ~/.config/hypr/monitors.lua
omarchy-hyprland-monitor-internal-mirror toggle   # SUPER + CTRL + ALT + Delete
omarchy-hyprland-monitor-internal toggle          # SUPER + CTRL + Delete
hyprctl reload
```

**Verify.** `hyprctl -j monitors | jq -r '.[] | "\(.name) \(.width)x\(.height)@\(.refreshRate) scale=\(.scale)"'` reports the resolution, refresh rate and scale you asked for, and `hyprctl configerrors` prints nothing.

Sources: <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://bbs.archlinux.org/viewtopic.php?id=301057> · <https://github.com/hyprwm/Hyprland/discussions/12064> · <https://github.com/basecamp/omarchy/blob/quattro/config/hypr/monitors.lua> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-scaling> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-internal-mirror> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/bindings/utilities.lua>

---

## Fix a window rule that never fires because the class does not match

`windowrule-not-matching-wrong-class` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** A window rule 'does nothing' — `windowrule = match:class ^(discord)$, workspace 4` never fires, the app still opens tiled on the current workspace, and there is no error in `hyprctl configerrors`.

**Cause.** The class string in the rule does not match what the window actually reports. Common causes: the real app_id is reverse-DNS (`com.mitchellh.ghostty`, `org.gnome.Nautilus`, `com.obsproject.Studio`) not the friendly name; XWayland reports a different, often capitalised class than the Wayland app_id; the regex is anchored with `^(...)$` but the real value has a suffix; matching is case-sensitive; and Hyprland uses Google RE2, so lookaheads/backreferences silently never match.

> **Audit corrected this record.** The diagnosis is excellent and fully verified: the current Window-Rules wiki confirms Hyprland uses Google RE2 ('all operations requiring polynomial time to compute will not work' — so lookaheads/backreferences silently fail), confirms `negative:` as the negation prefix with `negative:kitty` as its own example, and confirms class/title/initial_class/initial_title/xwayland as match props. The hyprctl clients / activewindow / jq inspection commands are right, and the closing advice about Electron/Java apps changing class late maps exactly onto the wiki's static-vs-dynamic split. But the Lua example is broken and contradicts the record's own following sentence. `"^(com%.obsproject%.Studio)$"` uses `%.`, which is Lua *pattern* escaping. The string is handed to RE2, where `%` is a literal percent — so that regex matches the literal text 'com%.obsproject%.Studio' and will never fire. A user copy-pastes it and reproduces the exact bug the record is about.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Everything except the Lua regex is correct. Replace the Lua example — RE2 does not understand Lua's `%` escapes:

```lua
-- WRONG: %. is a Lua pattern escape; RE2 reads % literally, so this never matches
-- hl.window_rule({ match = { class = "^(com%.obsproject%.Studio)$" }, workspace = "4" })

-- Right - escape for RE2, doubling the backslash for the Lua string literal:
hl.window_rule({ match = { class = "^(com\\.obsproject\\.Studio)$" }, workspace = "4" })

-- Or use a long-bracket string so no Lua-level escaping is needed at all:
hl.window_rule({ match = { class = [[^(com\.obsproject\.Studio)$]] }, workspace = "4" })
```

The record's own note ("escape the dot as \\. in a normal quoted string or use [[...]]") is the correct rule — the example just does not follow it.

**Verify.** Reopen the app; `hyprctl clients` shows it on the intended workspace/floating state. `hyprctl -j clients | jq '.[].class'` matches your regex exactly.

Sources: <https://wiki.hypr.land/Configuring/Basics/Window-Rules/> · <https://wiki.hypr.land/0.54.0/Configuring/Window-Rules/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/>

---

## Restore three-finger workspace swiping after gesture:workspace_swipe was removed

`gestures-workspace-swipe-does-not-exist-051` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `omarchy`

**Symptom.** `Config error in file /home/xxx/.local/share/omarchy/default/hypr/input.conf at line 20: config option <gesture:workspace_swipe> does not exist.` — and three-finger workspace swiping on the trackpad has stopped working.

**Cause.** Hyprland 0.51 (Sept 2025) removed exactly three keys - `gestures:workspace_swipe`, `gestures:workspace_swipe_fingers` and `gestures:workspace_swipe_min_fingers` - in favour of a general-purpose `gesture` keyword that binds any finger count + direction to an action. The `gestures.` category itself was **not** removed: `workspace_swipe_distance`, `workspace_swipe_invert`, `workspace_swipe_touch`, `workspace_swipe_cancel_ratio`, `workspace_swipe_create_new`, `workspace_swipe_direction_lock`, `workspace_swipe_forever`, `close_max_timeout` and `gestures.scrolling.*` are all still documented, so deleting the whole block discards real swipe tuning with no error to point at.

> **Audit corrected this record.** The new `gesture` keyword and every Lua example are confirmed verbatim against the current Gestures wiki page (hl.gesture with fingers/direction/mods/scale/action; the ALT+down close and 4-finger fullscreen examples are near-copies of the wiki's). animations:first_launch_animation -> monitorAdded is plausible; monitorAdded exists in the current animation tree. But the stated cause is wrong and the fix is destructive because of it: the `gestures:` category was NOT removed. The current Variables wiki still documents a full `gestures.` subcategory (workspace_swipe_distance, workspace_swipe_invert, workspace_swipe_touch, workspace_swipe_cancel_ratio, workspace_swipe_create_new, workspace_swipe_direction_lock, workspace_swipe_forever, close_max_timeout, plus gestures.scrolling.*). Only three keys were removed. The wiki says so explicitly: 'workspace_swipe, workspace_swipe_fingers and workspace_swipe_min_fingers were removed in favor of the new gestures system.' Telling a user to 'Delete the old gestures { ... } block entirely' silently discards their swipe tuning (invert, distance, cancel_ratio, forever), which is a real behavior regression with no error to point at.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Do NOT delete the whole `gestures` block — it still exists. Only three keys were removed in 0.51: `workspace_swipe`, `workspace_swipe_fingers`, `workspace_swipe_min_fingers`. Everything else in `gestures.` (workspace_swipe_distance, workspace_swipe_invert, workspace_swipe_touch, workspace_swipe_cancel_ratio, workspace_swipe_create_new, workspace_swipe_direction_lock, workspace_swipe_forever, close_max_timeout, gestures.scrolling.*) is still valid and still tunes the swipe.

hyprlang (0.51-0.54) — remove only the three dead keys, keep the rest:
```ini
gestures {
  # workspace_swipe = true            # REMOVED in 0.51
  # workspace_swipe_fingers = 3       # REMOVED in 0.51
  # workspace_swipe_min_fingers = ... # REMOVED in 0.51
  workspace_swipe_distance = 300      # still valid
  workspace_swipe_invert = true       # still valid
}

gesture = 3, horizontal, workspace
```

Lua (0.55+):
```lua
hl.config({ gestures = { workspace_swipe_distance = 300, workspace_swipe_invert = true } })
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
```

Verify what survived on your build with `hyprctl getoption gestures.workspace_swipe_distance`.

**Verify.** Swipe three fingers horizontally on the touchpad — workspaces move. `hyprctl configerrors` is clean.

Sources: <https://github.com/basecamp/omarchy/issues/1594> · <https://hypr.land/news/update51> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Gestures/> · <https://wiki.hypr.land/0.54.0/Configuring/Gestures/>

---

## hl.env() variables never reach systemd user services or D-Bus-activated apps

`hl-env-not-visible-to-systemd-user-services` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `systemd`, `wayland`

**Symptom.** A variable set with `hl.env("FOO", "bar")` is visible in a terminal you launched from a keybind, but `systemctl --user show-environment` does not list it. Symptoms downstream: the theme or cursor is right in apps you launch by hotkey and wrong in anything started by a `.service` or a `.desktop` D-Bus activation; a `--user` service you wrote cannot find `WAYLAND_DISPLAY`-adjacent variables you set; `flatpak run` apps ignore your env entirely; portal-launched helpers behave as though the variable does not exist.

**Cause.** `hl.env()` sets the variable in the compositor's own process environment, so it is inherited only by processes Hyprland itself forks after that line runs. Hyprland separately pushes a **fixed seven-name allowlist** into the systemd user manager and the D-Bus activation environment — from src/Compositor.cpp: `systemctl --user import-environment DISPLAY WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP QT_QPA_PLATFORMTHEME PATH XDG_DATA_DIRS` and the matching `dbus-update-activation-environment --systemd` line. Anything outside that list — `XCURSOR_THEME`, `GDK_BACKEND`, `MOZ_ENABLE_WAYLAND`, `ELECTRON_OZONE_PLATFORM_HINT`, `AQ_DRM_DEVICES`, `GTK_THEME`, your own variables — is invisible to user units and to every app D-Bus activates. Anything already running when Hyprland starts never sees it either.

> ⚠️ **Risk.** Do not put Wayland-specific variables in /etc/environment. That file is read by every session on the machine, including Xorg ones and display managers, and setting things like GDK_BACKEND=wayland there will break logins into non-Wayland sessions.

**Fix.**

Pick the mechanism that matches who needs the variable.

**A. Anything Hyprland launches (keybinds, autostart, exec rules)** — `hl.env()` is correct and sufficient:

```lua
hl.env("GTK_THEME", "Adwaita:dark")
-- reference an existing variable with os.getenv, not shell $ syntax:
hl.env("SSH_AUTH_SOCK", os.getenv("XDG_RUNTIME_DIR") .. "/ssh-agent.socket")
```

**B. systemd --user services and D-Bus-activated apps** — the durable fix is `environment.d`, which the user manager parses at startup:

```bash
mkdir -p ~/.config/environment.d
cat > ~/.config/environment.d/10-wayland.conf <<'EOF'
XCURSOR_THEME=Bibata-Modern-Classic
XCURSOR_SIZE=24
ELECTRON_OZONE_PLATFORM_HINT=auto
MOZ_ENABLE_WAYLAND=1
EOF
systemctl --user daemon-reload
```

Log out and back in (the user manager only re-reads these on start).

**C. Push what is already in the session, right now** — useful for a one-off or for a portal that came up before your variables existed:

```bash
dbus-update-activation-environment --systemd --all
systemctl --user import-environment QT_QPA_PLATFORMTHEME XCURSOR_THEME XCURSOR_SIZE
```

Run it from your autostart so it happens every session. In Omarchy that is `~/.config/hypr/autostart.lua`:

```lua
hl.dispatch(hl.dsp.exec_cmd("dbus-update-activation-environment --systemd --all"))
```

This affects units started *after* it runs, not units already running — restart the affected service.

**D. uwsm sessions** — do not put env vars in `hyprland.lua` at all. Use `~/.config/uwsm/env` for theming/xcursor/Nvidia/toolkit variables and `~/.config/uwsm/env-hyprland` for `HYPR*` and `AQ_*`, one `export KEY=VAL` per line:

```sh
# ~/.config/uwsm/env-hyprland
export AQ_DRM_DEVICES="/dev/dri/amd-igpu:/dev/dri/card1"
```

If you use dbus-broker rather than the reference dbus daemon, step C's `dbus-update-activation-environment` is redundant — it already reuses systemd's activation environment.

**Verify.** `systemctl --user show-environment | grep XCURSOR_THEME` prints your value, and `systemctl --user restart <yourservice>` then `systemctl --user show <yourservice> -p Environment` shows it reaching the unit.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/> · <https://raw.githubusercontent.com/hyprwm/Hyprland/main/src/Compositor.cpp> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.archlinux.org/title/Systemd/User> · <https://wiki.archlinux.org/title/Hyprland>

---

## Clear the config errors Hyprland 0.55 throws for options it removed

`hyprland-055-removed-options-pseudotile-border-locked` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`

**Symptom.** Three errors on a fresh boot after updating to Hyprland 0.55: `Config error in file /home/<user>/.local/share/omarchy/default/hypr/looknfeel.conf at line 53: Error parsing gradient -1: failed to parse -1 as a color`, the same for line 54, and `Config error in file .../looknfeel.conf at line 111: config option dwindle:pseudotile does not exist.`

**Cause.** Hyprland 0.55 removed `dwindle:pseudotile` (it had become a no-op — pseudotiling is per-window only now) and stopped accepting the `-1` 'inherit from parent colour' shorthand for `group:col.border_locked_active` / `col.border_locked_inactive`; the parser now demands a real colour or gradient. 0.55 also removed `decoration:shadow:ignore_window` and `render:cm_fs_passthrough`, and moved `misc:vfr` to `debug:vfr`.

> **Audit corrected this record.** Nearly all verified. hypr.land/news/update55 lists exactly these breaking changes: dwindle:pseudotile removed ('as it wasn't doing anything'), decoration:shadow:ignore_window removed, render:cm_fs_passthrough removed, misc:vfr moved to debug: — and the current Variables wiki indeed shows vfr under the Debug subcategory. Omarchy issue #5758 is real, quotes these exact three errors, and PR #5723 ('Hyprland lua conversion') is merged. `windowrule = match:class ^(mpv)$, pseudo on` and the Lua equivalent are both valid (pseudo is a documented static effect). One factual error in the fix: the claim that deleting col.border_locked_* makes Hyprland 'fall back to col.border_active/col.border_inactive' is false. The current Variables wiki gives group.col.border_locked_active its own default of 0x66ff5500 and col.border_locked_inactive 0x66775500 — deleting the lines yields those orange group colors, not your normal border colors. Separately, the suggested replacement rgba(00000000) makes locked-group borders fully transparent, which removes the visual cue that a group is locked; that is a deliberate choice, not a neutral one, and should be stated.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing /usr/share/omarchy/ or ~/.local/share/omarchy/default/ directly is reverted by the next update.

**Fix.**

Removals and the misc:vfr -> debug:vfr move are correct as written. Fix the border_locked guidance:

Deleting `col.border_locked_active` / `col.border_locked_inactive` does NOT fall back to `col.border_active`/`col.border_inactive` — those keys have their own defaults (`0x66ff5500` active, `0x66775500` inactive), so you get orange locked-group borders.

Pick deliberately:
```ini
group {
  # Keep locked groups visually distinct (just delete the -1 lines, accept defaults):
  #   -> orange 0x66ff5500 / 0x66775500

  # Or reproduce the old "inherit" look by naming your normal border colors:
  col.border_locked_active   = rgba(33ccffee) rgba(00ff99ee) 45deg
  col.border_locked_inactive = rgba(595959aa)

  # rgba(00000000) is NOT "inherit" - it makes locked-group borders invisible.
}

dwindle { }              # pseudotile removed in 0.55
misc    { }              # vfr moved out of misc
debug   { vfr = true }   # default is already true; only set if you changed it
```

On 0.55+ `hyprctl getoption` documents the dot form, so prefer `hyprctl getoption dwindle.pseudotile` and `hyprctl getoption group.col.border_locked_active` (the colon form still resolves). And the record is right that these lines live in the package-owned defaults — run `omarchy-update`, do not edit them.

**Verify.** `hyprctl configerrors` is empty and `hyprctl getoption debug:vfr` returns a value.

Sources: <https://github.com/basecamp/omarchy/issues/5758> · <https://hypr.land/news/update55> · <https://wiki.hypr.land/Configuring/Basics/Variables/>

---

## Stop hyprpm asking permission to load plugins on every login

`hyprpm-plugin-permission-popup-every-time` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`

**Symptom.** Every time `hyprpm reload` runs (including at login) Hyprland pops a permission prompt asking whether to let it load a plugin, and plugins only load if you click through it. Or plugins silently never load and there is no prompt at all.

**Cause.** Hyprland's permission system (needs `hyprland-guiutils`) defaults the `plugin` permission to ASK. Until an explicit allow rule exists for the hyprpm binary, every load is gated behind a popup. Conversely, if `ecosystem:enforce_permissions` is false, config permission rules are ignored entirely — popups still appear but 'remember' is unavailable.

> ⚠️ **Risk.** Do not blanket-allow `plugin` for `hyprctl` — anyone who can reach your hyprctl socket could then run `hyprctl plugin load /tmp/malicious.so` inside your compositor. Allow the hyprpm binary path specifically. Likewise, a blanket `screencopy = allow` for `.*` lets any local process silently record your screen.

**Fix.**

Enable enforcement and allow the hyprpm binary explicitly.

Lua (0.55+), in `~/.config/hypr/hyprland.lua`:
```lua
hl.config({ ecosystem = { enforce_permissions = true } })
hl.permission({ binary = "/usr/(bin|local/bin)/hyprpm", type = "plugin", mode = "allow" })
```

While you are there, screen capture is gated the same way — allow your portal and screenshot tools rather than clicking through:
```lua
hl.permission({ binary = "/usr/bin/grim", type = "screencopy", mode = "allow" })
hl.permission({ binary = "/usr/(lib|libexec|lib64)/xdg-desktop-portal-hyprland", type = "screencopy", mode = "allow" })
```

Permission rules are NOT hot-reloaded — restart Hyprland (log out and back in) for them to take effect.

**Verify.** Log out and back in; `hyprpm reload -n` loads plugins with no prompt, and `hyprctl plugin list` shows them.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Permissions/> · <https://wiki.hypr.land/Plugins/Using-Plugins/>

---

## Fix SUPER+Space and the Omarchy menu stopping after a game or Discord

`omarchy-super-space-launcher-stops-working` · severity: **medium** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`

**Symptom.** SUPER+Space (the app launcher) and the Omarchy menu randomly stop responding after a while — often after opening a game or Discord. Other keybindings still work. Only a reboot seems to fix it.

**Cause.** The keybinding itself is fine; the launcher process it execs has died or wedged. In Omarchy 3.x this was Walker (`/usr/bin/walker --gapplication-service`) crashing or losing its D-Bus service. Hyprland reports nothing because `exec` succeeded from its point of view.

> **Audit corrected this record.** The diagnosis is sound and the cited issues (#2089, #2558) are real Omarchy 3.x reports: the bind survives while the exec'd launcher process dies, so Hyprland reports nothing because exec succeeded from its point of view. `hyprctl binds` is a documented info command and is the right first check. But the recovery half is obsolete and one claim is fabricated. I listed all 440 scripts in basecamp/omarchy bin/ — there is no omarchy-refresh-walker, and no walker-related script of any kind; a repo-wide code search returns walker only in bin/omarchy-upgrade-to-quattro (i.e. the migration away from it). Omarchy 4.x replaced Walker with omarchy-shell / omarchy-menu. So `omarchy-refresh-walker` returns 'command not found' because it no longer exists, not because of a capitalised O — that explanation is invented and will send a user chasing a typo that isn't there. `yay -S walker` is also wrong for the era it targets: Omarchy 3.x installed the AUR binary package, walker-bin.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `omarchy-refresh-hyprland` overwrites every user Hyprland config in ~/.config/hypr with the shipped defaults. It backs each one up as <file>.bak.<epoch> first, but your customisations will not be in the active file afterwards.

**Fix.**

First confirm the bind is still registered — the record is right that this is the useful discriminator:
```bash
hyprctl binds | grep -B2 -A4 -i 'SPACE'
```

Then fix by Omarchy generation.

Omarchy 4.x (current) — Walker is gone; the launcher is the Omarchy shell. Restart it rather than rebooting:
```bash
omarchy-restart-shell
```
If the bindings themselves look wrong, restore the shipped ones (backs yours up as *.bak.<epoch>):
```bash
omarchy-refresh-hyprland
hyprctl reload
```

Omarchy 3.x (historical) — the launcher was Walker:
```bash
pkill walker
walker --gapplication-service &
# if the binary is genuinely missing, the AUR package is walker-bin, not walker:
yay -S walker-bin
```

There is no `omarchy-refresh-walker` in current Omarchy (verified against all 440 scripts in bin/) — if you get 'command not found', the script has been removed, not miscapitalised.

**Verify.** `hyprctl binds | grep SPACE` shows the bind, and pressing SUPER+Space opens the launcher without a reboot.

Sources: <https://github.com/basecamp/omarchy/issues/2089> · <https://github.com/basecamp/omarchy/issues/2558> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-refresh-hyprland>

---

## Screen sharing fails instantly: the share picker never appears, or the shared window is black

`share-picker-never-appears-selection-minus-one` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Clicking "Share screen" in Google Meet, Discord, Zoom or Teams does nothing at all — no window/monitor picker dialog, the request just fails. `journalctl --user -u xdg-desktop-portal-hyprland` shows `[LOG] [screencopy] SHAREDATA returned selection -1` followed by `[LOG] [screencopy] Session destroyed`. Or the picker does appear, you choose a screen, and the far end sees a black rectangle.

**Cause.** Two distinct failures. (1) **The picker binary is missing or crashing.** XDPH shells out to whatever `screencopy:custom_picker_binary` names in `~/.config/hypr/xdph.conf`; if that binary is absent or dies on launch it returns selection `-1` and the portal tears the session down immediately. Omarchy ships `custom_picker_binary = hyprland-preview-share-picker`, and when that package is missing or broken every screen share fails this way — this is exactly what bit Omarchy 3.2.3. (2) **Black capture** is usually XWayland: an app running under XWayland can only see other XWayland windows, so it cannot capture a Wayland window or a whole screen. A mismatch between the monitor's `bitdepth` and what you configured also breaks capture — 10-bit output in particular stops some apps capturing at all.

> ⚠️ **Risk.** `allow_token_by_default = true` pre-ticks "Allow restore token", which lets an app silently resume capturing the same screen on later requests without showing you the picker. Convenient for Meet, but it means an app you shared with once can start capturing again without a prompt. Set it to false if that matters to you.

**Fix.**

**Confirm the whole stack is installed and running:**

```bash
pacman -Q pipewire wireplumber xdg-desktop-portal xdg-desktop-portal-hyprland xdg-desktop-portal-gtk qt6-wayland
systemctl --user status xdg-desktop-portal-hyprland
```
A crash in the status output usually means `qt6-wayland` (or `qt5-wayland`) is missing.

**Fix a picker that returns -1** — check the binary exists, then fall back to the stock picker in `~/.config/hypr/xdph.conf`:

```bash
command -v hyprland-preview-share-picker || sudo pacman -S --needed hyprland-preview-share-picker
```

```ini
# ~/.config/hypr/xdph.conf
screencopy {
    custom_picker_binary = hyprland-share-picker
    allow_token_by_default = true
    max_fps = 60
}
```

Then restart the portal:

```bash
systemctl --user restart xdg-desktop-portal-hyprland xdg-desktop-portal
```

Leaving `custom_picker_binary` unset falls back to `hyprland-share-picker` (the default), which is the safest thing to do when debugging.

**Fix black capture:**

```bash
# Is the app on XWayland? If `xwayland: 1`, that is your answer.
hyprctl clients | grep -B8 -A2 'xwayland: 1'
```

Run the app natively on Wayland instead:

```lua
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")   -- Discord/Vesktop, Slack, VSCodium
hl.env("MOZ_ENABLE_WAYLAND", "1")                -- Firefox
```
or per-app: `--enable-features=UseOzonePlatform --ozone-platform=wayland`.

Make sure the `bitdepth` in your monitor rule matches the panel; drop `bitdepth = 10` while debugging, since some apps cannot screen-capture with 10-bit enabled.

On a multi-GPU box where DMA-BUF allocation fails, force the slower but reliable path:

```ini
screencopy {
    force_shm = true
}
```

**Portal not autostarting and producing no logs at all** almost always means the XDG environment is wrong. Confirm and push it:

```bash
systemctl --user show-environment | grep -E 'XDG_CURRENT_DESKTOP|WAYLAND_DISPLAY'
dbus-update-activation-environment --systemd --all
```

**Verify.** `journalctl --user -u xdg-desktop-portal-hyprland -f` while starting a share shows a picker session created and no `selection -1`; the picker window appears; the receiving end sees live video rather than black.

Sources: <https://github.com/basecamp/omarchy/issues/3989> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.hypr.land/Useful-Utilities/Screen-Sharing/> · <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://github.com/basecamp/omarchy/blob/quattro/config/hypr/xdph.conf> · <https://wiki.hypr.land/Nvidia/>

---

## Escape a Hyprland submap that has left the keyboard dead

`stuck-in-submap-no-keys-work` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`

**Symptom.** After pressing the resize/move hotkey, the keyboard is effectively dead — no keybinding does anything, you cannot open a terminal, and you cannot get out.

**Cause.** A submap replaces the active bind set. If the submap definition has no bind that calls `submap reset`, or the reset key was typo'd, there is no way back from inside the submap. Any bind not marked submap-universal is inactive while you are in it.

**Fix.**

Always give a submap an escape hatch:

hyprlang:
```ini
bind = ALT, R, submap, resize
submap = resize
binde = , right, resizeactive, 10 0
binde = , left,  resizeactive, -10 0
bind  = , escape, submap, reset
submap = reset
```

Lua (0.55+):
```lua
hl.bind("ALT + R", hl.dsp.submap("resize"))
hl.define_submap("resize", function()
  hl.bind("right", hl.dsp.window.resize({ x = 10, y = 0, relative = true }), { repeating = true })
  hl.bind("escape", hl.dsp.submap("reset"))
end)
-- always-available escape, active in every submap:
hl.bind("SUPER + K", hl.dsp.exec_cmd("kitty"), { submap_universal = true })
```

To get out right now, from a terminal you still have open:
```bash
hyprctl dispatch submap reset                    # hyprlang era
hyprctl dispatch 'hl.dsp.submap("reset")'        # 0.55+ Lua
```
If you have no terminal, switch to a TTY with CTRL+ALT+F2, log in, and target the instance:
```bash
hyprctl instances
hyprctl dispatch --instance 0 'hl.dsp.submap("reset")'
```
Check where you are with `hyprctl submap`.

**Verify.** `hyprctl submap` prints the default/empty submap and your normal binds respond again.

Sources: <https://wiki.hypr.land/Configuring/Basics/Binds/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/>

---

## Make a window rule fire when an app renames its own title

`windowrule-float-on-title-change-never-fires` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`, `wayland`

**Symptom.** A rule like 'float any window whose title becomes "Save As"' or 'float the Zoom meeting window once it renames itself' never triggers, even though `hyprctl clients` clearly shows that title. Rules that use `opacity` or `border_color` on the same match work fine.

**Cause.** Hyprland splits rule effects into static and dynamic. Static effects (`float`, `tile`, `fullscreen`, `maximize`, `move`, `size`, `center`, `pseudo`, `monitor`, `workspace`, `pin`, `group`, `no_initial_focus`) are evaluated exactly once, at window open, and at that moment only `initialTitle`/`initialClass` are known. A later title change cannot retroactively float the window. Dynamic effects (`opacity`, `border_color`, `no_blur`, `max_size`, `tag`, ...) are re-evaluated on every property change, which is why those appear to work.

> **Audit corrected this record.** The cause is exactly right and is the wiki's own warning: 'It is not possible to float (or any other static rule) a window based on a change in the title after the window has been created. This applies to all static effects listed here. Instead, use a dispatch triggered by an event listener.' The record's static list (float, tile, fullscreen, maximize, move, size, center, pseudo, monitor, workspace, pin, group, no_initial_focus) is a correct subset of the wiki's static table, and its dynamic examples (opacity, border_color, no_blur, max_size, tag) are all in the dynamic table. The Lua listener is valid: window.title is a documented event, hl.dsp.window.float({action, window}) is a documented dispatcher, `action = "on"` is a documented value (the action param type is toggle/enable|on/disable|off), and `address:0x...` is a documented window selector. The `match:initial_title` advice is right. The bash/socat fallback is the problem — it is broken in two independent ways and floats windows it should not.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The Lua listener and the initial_title advice are correct as written. Replace the socat fallback, which as written floats EVERY window whose title changes (it has no title filter at all, despite the stated goal of matching 'Save As') and also misfires on windowtitlev2.

Per the IPC wiki, `windowtitle>>` carries only WINDOWADDRESS while `windowtitlev2>>` carries `WINDOWADDRESS,WINDOWTITLE`. The record's `windowtitle*` glob matches BOTH, so on a v2 event it builds `address:0x<ADDR>,<TITLE>` and the dispatch fails. Use v2 so you actually have the title to test:

```bash
socat -U - "UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock" |
  while read -r line; do
    case "$line" in
      windowtitlev2\>\>*)
        payload=${line#*>>}
        addr=${payload%%,*}
        title=${payload#*,}
        case "$title" in
          "Save As"*) hyprctl dispatch setfloating "address:0x${addr}" ;;
        esac
        ;;
    esac
  done
```

(`setfloating` is the hyprlang-era dispatcher name, correct for <= 0.54; on 0.55+ prefer the Lua listener shown above.)

**Verify.** Trigger the title change; `hyprctl clients` shows `floating: 1` for that address.

Sources: <https://wiki.hypr.land/Configuring/Basics/Window-Rules/> · <https://wiki.hypr.land/0.54.0/Configuring/Window-Rules/>

---

## Fix SUPER+1..9 not switching workspaces on an AZERTY layout

`workspace-binds-broken-non-qwerty-layout` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`

**Symptom.** On a French AZERTY (or similar) layout, SUPER+1..9 do not switch workspaces at all, while SUPER+letter binds work fine.

**Cause.** Keys used in binds must be reachable without modifiers in your keyboard layout. On AZERTY the digit row produces `&`, `é`, `"`, `'` etc. unmodified — the digits require SHIFT. So `bind = SUPER, 1, workspace, 1` describes a chord that never occurs.

**Fix.**

Bind the unmodified keysym names instead of the digits.

```ini
# French AZERTY
bind = $mainMod, ampersand,  workspace, 1
bind = $mainMod, eacute,     workspace, 2
bind = $mainMod, quotedbl,   workspace, 3
bind = $mainMod, apostrophe, workspace, 4
bind = $mainMod, parenleft,  workspace, 5
```

Find the right names for your layout with:
```bash
sudo pacman -S wev
wev            # press the key, read the `sym` field
```
The canonical list is the `XKB_KEY_` suffixes in `xkbcommon-keysyms.h`.

Alternatively bind by keycode, which is layout-independent:
```ini
bind = SUPER, code:10, workspace, 1     # top-row "1" position
```
```lua
hl.bind("SUPER + code:10", hl.dsp.focus({ workspace = "1" }))
```

**Verify.** `hyprctl binds` shows the bind, and pressing SUPER+<key> switches workspace.

Sources: <https://wiki.hypr.land/0.54.0/Configuring/Binds/> · <https://wiki.hypr.land/Configuring/Basics/Binds/>

---

## Fix a Lua config getter that hangs the keybindings menu or eats all memory

`lua-config-getters-infinite-loop-at-load` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`

**Symptom.** `omarchy-menu-keybindings` (SUPER+K) never opens — no menu, no error, no timeout. `omarchy-menu-keybindings --print` hangs forever. In worse cases the machine runs out of memory and freezes. Hyprland itself is fine: `hyprctl reload` and `hyprctl configerrors` are clean.

**Cause.** Iterating one of Hyprland's list getters (`hl.get_monitors()`, `hl.get_windows()`, `hl.get_workspaces()`) with `ipairs` at config-evaluation time. Omarchy's keybinding scanner re-evaluates `~/.config/hypr/hyprland.lua` in a bare `lua` interpreter with `hl` replaced by a catch-all stub whose `__index` returns a truthy value for every key — so `ipairs(hl.get_monitors())` reads index 1, 2, 3, ... and never hits nil. If the loop body allocates (e.g. `table.insert`), it also eats all RAM.

> ⚠️ **Risk.** If the loop body allocates, this can exhaust RAM and take the whole session down — test config changes with a TTY available (CTRL+ALT+F2).

**Fix.**

Move the iteration out of load time and into an event handler, so it only runs inside the real compositor.

Instead of:
```lua
-- ~/.config/hypr/monitors.lua  -- HANGS the bind scanner
for _, m in ipairs(hl.get_monitors()) do
  -- ...
end
```
write:
```lua
hl.on("hyprland.start", function()
  for _, m in ipairs(hl.get_monitors()) do
    -- ...
  end
end)
-- and/or react to hotplug:
hl.on("monitor.added", function(monitor)
  -- ...
end)
```

If you must run it at load, guard it so a stubbed `hl` cannot loop forever:
```lua
local mons = hl.get_monitors()
if type(mons) == "table" and #mons > 0 and #mons < 64 then
  for i = 1, #mons do local m = mons[i] end
end
```

Find the offender:
```bash
grep -rnE 'ipairs\(hl\.get_(monitors|windows|workspaces)' ~/.config/hypr/
```

**Verify.** `omarchy-menu-keybindings --print` returns a list of bindings and exits instead of hanging.

Sources: <https://github.com/basecamp/omarchy/issues/7025>

---

## Fix send_key_state errors on SUPER+C/V/X with a non-Latin layout active

`send-key-state-key-not-found-non-latin-layout` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `desktop`, `hyprland`, `laptop`, `omarchy`

**Symptom.** With a multi-layout keyboard (`kb_layout = "us,th"`, `us,ru`, `us,ua` ...), pressing SUPER+C / SUPER+V / SUPER+X while the non-Latin layout is active pops up `Runtime error in lua: send_key_state: key not found` and nothing is copied or pasted. It works in the English layout. Oddly, once it succeeds in English after a Hyprland reload, it keeps working in the other layout until the next reload.

**Cause.** Hyprland's `resolveKeycode` maps a key name like "C" to a keycode by scanning the keymap with the currently active layout group applied. A non-Latin group contains no Latin keysyms, so "C" is never found and the dispatcher raises a Lua runtime error. The keycode cache key does not include the layout group, which is why one success in Latin makes it work afterwards.

**Fix.**

Bind by keycode instead of key name — keycodes are layout-independent. XKB keycodes are evdev+8, so C/V/X are `code:54`, `code:55`, `code:53`.

```lua
-- ~/.config/hypr/bindings.lua
hl.unbind("SUPER + C")
hl.unbind("SUPER + V")
hl.unbind("SUPER + X")

hl.bind("SUPER + C", function()
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "code:54", state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "code:54", state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end)
```

Simplest alternative — drop the universal shortcuts and use the apps' native CTRL+C/V/X:
```lua
-- ~/.config/hypr/bindings.lua
hl.unbind("SUPER + C")
hl.unbind("SUPER + V")
hl.unbind("SUPER + X")
```

Confirm keycodes for your keyboard with `wev` (the `code` field it prints is the XKB keycode).

**Verify.** Switch to the non-Latin layout, select text, press SUPER+C — no error popup and `wl-paste` returns the selection.

Sources: <https://github.com/basecamp/omarchy/issues/7371> · <https://github.com/basecamp/omarchy/issues/7027> · <https://wiki.hypr.land/Configuring/Basics/Binds/>

---

## Clear the red config-error bar pinned across every screen

`config-error-bar-covers-screen` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`

**Symptom.** A red config-error bar is pinned across the top of every screen, over the browser and everything else, and stays there. Users describe it as 'IN YOUR FACE' and unusable.

**Cause.** Hyprland renders config parse errors as a persistent overlay bar. It is non-fatal — the offending lines are just ignored — but it is drawn above all windows until the config parses cleanly. Its position and how many errors it lists are configurable, and it can be suppressed outright.

> ⚠️ **Risk.** `suppress_errors = true` will hide genuinely broken config from you later.

**Fix.**

First, read them so you can actually fix the cause:
```bash
hyprctl configerrors
```

Move the bar to the bottom, or cap it:
```lua
hl.config({ debug = { error_position = 1, error_limit = 5 } })   -- 0 = top, 1 = bottom
```
hyprlang equivalent:
```ini
debug {
  error_position = 1
  error_limit    = 5
}
```

Suppress it entirely (only once you know what the errors are):
```lua
hl.config({ debug = { suppress_errors = true } })
```

To clear a bar set by a script rather than by the parser:
```bash
hyprctl seterror disable
```

**Verify.** `hyprctl configerrors` output matches what you fixed; after `hyprctl reload` the bar is gone or repositioned.

Sources: <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://github.com/basecamp/omarchy/issues/5758>

---

## Fix apps rendering at double size or blurry on a 1x display

`gdk-scale-apps-too-large-hyprland` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Some apps are enormous on a 1080p or 1x display — UI elements roughly double size — while native Wayland apps look correct. Others (XWayland ones) look blurry or pixelated instead.

**Cause.** Hyprland's monitor `scale` sizes Wayland-native output, but GTK/X11 apps are sized by the `GDK_SCALE` environment variable, which only accepts whole numbers. Omarchy assumes a 2x HiDPI panel and sets `GDK_SCALE=2`; on a 1x display everything GTK/XWayland draws is doubled. Separately, XWayland cannot scale fractionally at all, which is why those apps go blurry or pixelated rather than large.

**Fix.**

Set the GDK scale to the nearest integer to your monitor scale.

Omarchy 4.x — edit `~/.config/hypr/monitors.lua`:
```lua
local omarchy_monitor_scale = "auto"
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

local omarchy_gdk_scale = 1        -- was 2
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```
Omarchy 3.x used `~/.config/hypr/hyprland.conf` with `env = GDK_SCALE,1`.

Per-monitor scale on 0.55+:
```lua
hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "0x0", scale = 1 })
```
hyprlang: `monitor = DP-2,2560x1440@144,0x0,1`

List what your outputs actually support:
```bash
hyprctl monitors all
```

GDK_SCALE only reaches an app at launch — restart the oversized apps (or log out) after changing it. If a specific app is pixelated rather than large, it is running under XWayland; run it natively in Wayland where possible, or accept integer scaling for it.

**Verify.** `hyprctl monitors | grep -E 'scale|Monitor'` shows the intended scale, and a restarted GTK app is normal-sized.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting> · <https://github.com/basecamp/omarchy/blob/master/config/hypr/monitors.lua> · <https://wiki.hypr.land/FAQ/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Performance/>

---

## Find the trailing comma that makes a keybinding silently do nothing

`keybind-trailing-comma-hyprlang` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`

**Symptom.** A keybinding does nothing at all, silently — no error, no notification. E.g. `bind = SUPER, F, exec, firefox,` never launches Firefox, while the identical-looking line for another app works.

**Cause.** hyprlang's `bind` keyword takes exactly four comma-separated arguments. An accidental trailing comma becomes part of the last argument, so Hyprland tries to exec the literal command `firefox,` which does not exist. Example configs legitimately end with a trailing comma when the last argument is meant to be empty (`bind = SUPER, Tab, cyclenext,`), which is where the habit comes from.

**Fix.**

Count the commas — exactly three.

```ini
bind = SUPER, F, exec, firefox      # OK   - 4 args
bind = , Print, exec, grim          # OK   - empty mods
bind = SUPER, Tab, cyclenext,       # OK   - empty params, dispatcher takes none
bind = SUPER, F, exec, firefox,     # WRONG - execs `firefox,`
```

Find offenders across your config:
```bash
grep -rnE '^\s*bind[a-z]*\s*=.*exec,.*,\s*$' ~/.config/hypr/
```

On Lua (0.55+) this class of bug is gone — args are explicit:
```lua
hl.bind("SUPER + F", hl.dsp.exec_cmd("firefox"))
```

**Verify.** `hyprctl binds` lists the bind with the correct `arg`, and the key works after `hyprctl reload`.

Sources: <https://wiki.hypr.land/0.54.0/Configuring/Binds/>

---

## XWayland apps are blurry or pixelated on a scaled display

`xwayland-blurry-on-fractional-scale` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hidpi`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** On a HiDPI or fractionally scaled monitor, native Wayland apps look sharp but Steam, Zoom, older Electron builds, JetBrains IDEs, GIMP and Wine games are soft, fuzzy or visibly pixelated. The Hyprland FAQ answer people find is "This just means they are running through XWayland, which physically cannot scale by fractional amounts" — which explains it but doesn't fix it. Turning scaling off makes them sharp and everything tiny.

**Cause.** Xorg has no per-output scale, so XWayland surfaces are rendered at 1x and then bitmap-scaled by the compositor to the monitor's scale factor. Any non-integer factor means resampling, hence the blur; `xwayland:use_nearest_neighbor` (default true) swaps blur for pixelation but does not add detail. The documented remedy is to stop the compositor scaling XWayland at all (`xwayland:force_zero_scaling`) and instead let each toolkit draw its own UI larger — but that only works if the toolkit env vars are actually set, and `hl.env()` only reaches processes Hyprland itself spawns after that line runs.

> ⚠️ **Risk.** Setting `Xft.dpi` at the same time as a toolkit scale such as `GDK_SCALE` makes interface elements much larger than intended in some programs (Firefox is the usual casualty). Pick one mechanism per toolkit. Do not install the old XWayland HiDPI patches — upstream states they are no longer supported.

**Fix.**

Force XWayland to render 1:1 and hand the scaling job to the toolkits. In `~/.config/hypr/hyprland.lua` (plain Hyprland):

```lua
-- Monitor keeps its real resolution and fractional scale
hl.monitor({ output = "", mode = "highres", position = "auto", scale = 1.5 })

-- Stop the compositor from upscaling XWayland surfaces
hl.config({
  xwayland = {
    force_zero_scaling = true,
  },
})

-- Now each toolkit scales itself. GTK only honours whole numbers -
-- use the nearest integer to your monitor scale.
hl.env("GDK_SCALE", "2")
hl.env("XCURSOR_SIZE", "32")
hl.env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
```

**Omarchy 4 already does the first half for you.** `force_zero_scaling = true` is set in `/usr/share/omarchy/default/hypr/envs.lua`, and `GDK_SCALE` is set from a variable at the bottom of `~/.config/hypr/monitors.lua`. Edit that file, not a new one:

```lua
-- ~/.config/hypr/monitors.lua
local omarchy_monitor_scale = 1.6
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

local omarchy_gdk_scale = 2
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
```

or let Omarchy write both numbers consistently:

```bash
omarchy-hyprland-monitor-scaling 1.6
```

Toolkits GDK_SCALE does not cover:

```bash
# Java / JetBrains
hl.env("_JAVA_OPTIONS", "-Dsun.java2d.uiScale=2")

# Electron/Chromium apps still on XWayland - per-app flag, not an env var
#   e.g. ~/.config/code-flags.conf:  --force-device-scale-factor=2

# Legacy X11 apps that read Xft.dpi (integer multiples of 96)
printf 'Xft.dpi: 192\n' >> ~/.Xresources
xrdb -merge ~/.Xresources
```

Env changes only reach apps started **after** the reload, so `hyprctl reload` then relaunch the app — do not judge by a window that was already open.

**Verify.** Relaunch an XWayland app and check `hyprctl clients | grep -A2 xwayland` shows `xwayland: 1` for it; its text should now be crisp. `hyprctl getoption xwayland.force_zero_scaling` returns 1.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/XWayland/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/FAQ/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/> · <https://wiki.archlinux.org/title/HiDPI> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/basecamp/omarchy/blob/quattro/config/hypr/monitors.lua>

---

## Run hyprctl from a TTY, cron or SSH by setting the instance signature

`hyprctl-fails-outside-session-instance-signature` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `grub`, `hyprland`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** Running `hyprctl` from a TTY, a cron job, a systemd unit or an SSH session fails — no output, or it targets the wrong Hyprland when you have more than one running.

**Cause.** hyprctl talks to a per-instance UNIX socket under `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/`. Outside the compositor's own environment that variable is unset, so hyprctl has nothing to connect to; with multiple instances it needs to be told which.

> **Audit corrected this record.** The diagnosis and most commands are right: hyprctl talks to $XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/ (confirmed on the IPC wiki), `hyprctl instances` is a documented info command, `--instance` is a real flag (hyprctl.usage: `-i | --instance`), --batch is documented, and the batching-for-performance advice comes straight from the wiki's own warning that 'any spam of the utility will cause slowdowns. It's recommended to use --batch'. The log path is correct. The defect is the signature-export recipe, which is offered specifically 'for scripts and units' — the one context where it is most likely to fail. In a system unit or a cron job XDG_RUNTIME_DIR is not set, so the path collapses to /hypr and the command silently produces nothing. And `ls -t | head -n 1` picks the newest entry by mtime, which can be a stale directory left by a crashed session or a non-instance entry, so it can also silently target the wrong thing.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Diagnosis, `--instance`, `--batch` and the log path are all correct. Replace the export recipe, which fails in exactly the script/unit context it is recommended for.

Set XDG_RUNTIME_DIR explicitly first — it is unset in system units and cron:
```bash
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
```

Then prefer targeting by index, which needs no signature guessing:
```bash
hyprctl instances                 # lists running instances
hyprctl --instance 0 monitors     # put flags BEFORE the subcommand
hyprctl --instance 0 dispatch 'hl.dsp.submap("reset")'
```

If you must derive the signature, pick a live socket rather than the newest directory, so stale dirs from crashed sessions cannot win:
```bash
for d in "$XDG_RUNTIME_DIR"/hypr/*/; do
  [ -S "$d/.socket.sock" ] || continue
  export HYPRLAND_INSTANCE_SIGNATURE=$(basename "$d")
  break
done
hyprctl monitors
```

For a systemd *user* unit, the cleanest fix is `After=graphical-session.target` plus `PartOf=graphical-session.target` and letting Hyprland's `dbus-update-activation-environment` seed the environment (see the portal record).

**Verify.** `hyprctl monitors` returns your outputs from the TTY/script context.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://wiki.hypr.land/Configuring/Basics/Binds/> · <https://wiki.hypr.land/Crashes-and-Bugs/>

---

## Fix 'misc:new_window_takes_over_fullscreen does not exist' after an update

`misc-new-window-takes-over-fullscreen-does-not-exist` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`

**Symptom.** `misc:new_window_takes_over_fullscreen does not exist` in the on-screen config error list right after updating Hyprland. Also seen as `master:inherit_fullscreen does not exist`.

**Cause.** Hyprland 0.53 replaced both `misc:new_window_takes_over_fullscreen` and `master:inherit_fullscreen` with a single option, `misc:on_focus_under_fullscreen`. The old names are hard errors, not warnings.

**Fix.**

Delete the old keys and use the new one.

hyprlang (0.53–0.54):
```ini
misc {
  # new_window_takes_over_fullscreen = 2   # remove
  on_focus_under_fullscreen = 2
}
```

Lua (0.55+):
```lua
hl.config({ misc = { on_focus_under_fullscreen = 2 } })
```

Check the option actually exists on your build before writing it:
```bash
hyprctl getoption misc:on_focus_under_fullscreen
```

**Verify.** `hyprctl getoption misc:on_focus_under_fullscreen` returns a value rather than `no such option`, and the error disappears from `hyprctl configerrors`.

Sources: <https://github.com/basecamp/omarchy/issues/4023> · <https://hypr.land/news/update53>

---

## Tearing and VRR do nothing, or VRR causes brightness flicker

`tearing-and-vrr-not-working` · severity: **low** · frequency: **common** · applies to: `amdgpu`, `arch`, `cachyos`, `desktop`, `endeavouros`, `gaming`, `hyprland`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** `allow_tearing` is on and the `immediate` window rule is set, but frame times in a game are unchanged and there is no tearing at all. Or tearing works and the game freezes instead, or shows random coloured pixels. Or VRR is enabled and the desktop now flickers in brightness — worst while scrolling, watching a fullscreen YouTube video, or in any game whose framerate swings.

**Cause.** **Tearing** is only applied when the tearing window is fullscreen and is the *only* thing visible on that output. A notification, a bar, a lock surface, an overlay or a second window on the same monitor suppresses it, and it needs both the `general:allow_tearing` master toggle and a per-window `immediate` rule. Frozen or artefacted output means the GPU driver does not really support tearing — there is no compositor-side fix. **VRR brightness flicker** is a monitor property, not a Hyprland bug: many panels change perceived brightness with refresh rate, so a rate that swings between (say) 72 and 144 Hz visibly pulses. VRR also requires DisplayPort on most hardware, and some monitors only expose VRR below their maximum refresh rate.

> ⚠️ **Risk.** Tearing is experimental and driver-dependent: if the driver does not support it, apps that should tear will freeze outright or render corrupted frames, and there is no compositor-side workaround. Turn `allow_tearing` back off before assuming a game is broken. Setting `vrr = 1` (always on) on a panel with a narrow VRR range can make the whole desktop flicker constantly — `vrr = 2` is the safe default.

**Fix.**

**Tearing** — master toggle plus a per-game rule:

```lua
hl.config({
  general = {
    allow_tearing = true,
  },
})

hl.window_rule({ match = { class = "cs2" }, immediate = true })
-- or for anything the compositor tags as a game:
hl.window_rule({ match = { content = "game", fullscreen = true }, immediate = true })
```

Then actually make the conditions hold: fullscreen (not maximised), nothing else drawn on that output. Move your bar and notifications to the other monitor while testing.

```bash
hyprctl getoption general.allow_tearing     # must be 1
hyprctl clients | grep -A2 -i cs2           # confirm the rule matched the real class
```

**VRR** — global default, then per-monitor where it matters. `0` off, `1` always on, `2` fullscreen only, `3` fullscreen with `video`/`game` content type:

```lua
hl.config({
  misc = {
    vrr = 2,      -- fullscreen only: the standard answer to desktop flicker
  },
})

-- Per-display override; a monitor `vrr` field beats the misc default
hl.monitor({ output = "DP-1", mode = "2560x1440@144", position = "0x0", scale = 1, vrr = 2 })
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1, vrr = 0 })
```

Try it live before committing:

```bash
hyprctl eval 'hl.config({ misc = { vrr = 2 } })'
```

If flicker persists at `vrr = 2` inside games, the panel's VRR range is the problem — cap the in-game framerate inside that range, drop the monitor to a refresh rate the panel supports VRR at, or turn VRR off for that output. Use DisplayPort; HDMI VRR only works on displays that implement the relevant part of HDMI 2.1.

Cursor movement can also break VRR framepacing in fullscreen apps:

```lua
hl.config({
  cursor = {
    no_break_fs_vrr = 1,      -- 0 off, 1 on, 2 auto (on for content type 'game')
    min_refresh_rate = 60,    -- floor for cursor-driven frames
  },
})
```

**When Proton/Wine still misbehaves**, run the game inside gamescope, which gives it an isolated micro-compositor with its own framerate and scaling handling rather than fighting Hyprland's:

```bash
sudo pacman -S --needed gamescope
# Steam launch options:
#   gamescope -W 2560 -H 1440 -r 144 -f -- %command%
```

**Verify.** `hyprctl getoption general.allow_tearing` is 1 and `hyprctl getoption misc.vrr` matches what you set; `hyprctl -j monitors | jq -r '.[] | "\(.name) vrr=\(.vrr)"'` shows the per-output state; in a fullscreen game the reported refresh rate tracks the framerate and the desktop no longer pulses.

> *Not independently audited: verify before running.*

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Tearing/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://wiki.archlinux.org/title/Variable_refresh_rate> · <https://github.com/hyprwm/Hyprland/issues/11712> · <https://wiki.archlinux.org/title/Gaming>

---

## Fix unbind doing nothing because the key name's case is wrong

`unbind-case-sensitive-key-name` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`

**Symptom.** `unbind = SUPER, Tab` appears to do nothing — the original binding still fires, and adding your own bind on the same key gives you two actions at once or the wrong one.

**Cause.** In `unbind`, the key name is case-sensitive and must match the case used in the original `bind` exactly. `Tab` and `TAB` are different keys as far as the unbind lookup is concerned.

> **Audit corrected this record.** The central claim is verbatim wiki text — the current Binds page states: 'In unbind, key is case-sensitive It must exactly match the case of the bind you are unbinding.' `hyprctl binds` is a documented info command. The Omarchy override block is confirmed almost character-for-character against config/hypr/bindings.lua in the omarchy repo, which ships exactly `hl.unbind("SUPER + SPACE")` followed by `o.bind("SUPER + SPACE", "Omarchy menu", "omarchy-menu toggle root")` as its worked example. `hl.unbind("SUPER + TAB")` is correct. The one defect: the runtime-test line `hyprctl keyword unbind SUPER, TAB` is hyprlang-era and is presented unlabeled between two 0.55+ Lua blocks. On a current Omarchy 4.x box (Hyprland 0.56, Lua config) a user pastes it and it does not work; the Binds wiki gives the Lua-era equivalent explicitly.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Everything is correct except the runtime-test command, which is unlabeled hyprlang-era. Use the form that matches your config engine:

hyprlang (<= 0.54):
```bash
hyprctl keyword unbind SUPER, TAB
```

Lua (0.55+) — this is the wiki's own example:
```bash
hyprctl eval 'hl.unbind("SUPER + TAB")'
```

Find the exact registered spelling first, since the case must match:
```bash
hyprctl binds | grep -A4 -i 'tab'
```

**Verify.** `hyprctl binds` no longer lists the old bind; pressing the key does only what you expect.

Sources: <https://wiki.hypr.land/0.54.0/Configuring/Binds/> · <https://github.com/basecamp/omarchy/blob/master/config/hypr/bindings.lua>

---

## Workspaces will not stay on the monitor they are bound to, especially after a hotplug

`workspace-not-pinned-to-monitor` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** `hl.workspace_rule({ workspace = "1", monitor = "DP-1" })` is in the config, but workspace 1 opens on whichever monitor happens to be focused. Or the binding works once and then stops: the first `SUPER+1` lands correctly, every later one pulls the workspace to the current screen. Or after undocking and re-docking, every workspace has piled onto the laptop panel and stays there. Or the rule quietly does nothing because the monitor was absent at login.

**Cause.** Workspace-to-monitor binding is a *rule about where a workspace is created*, not a permanent tether. If the named output does not exist when Hyprland evaluates the rule — monitor off, dock not attached, connector renamed from `DP-1` to `DP-2` — the workspace is created on whatever monitor is available and there is nothing that migrates it back when the output reappears. Compounding this: workspace *selectors* (`r[2-4]`, `w[t1]`, `m[DP-1]`) only ever match workspaces that already exist, so a selector-based rule cannot pre-place a workspace that has not been created yet. Connector names are also unstable across docks, which is what turns a working config into a broken one after a hardware change.

**Fix.**

Bind by EDID description rather than connector name, and make the workspaces persistent so they exist from login:

```lua
-- ~/.config/hypr/hyprland.lua  (Omarchy: put this in ~/.config/hypr/bindings.lua
-- or any file required from hyprland.lua after the Omarchy defaults)

-- Get the description from `hyprctl monitors` and DROP the trailing "(DP-1)"
local EXTERNAL = "desc:Dell Inc. DELL U2720Q 8FGZ043"
local LAPTOP   = "desc:Chimei Innolux Corporation 0x150C"

for _, id in ipairs({ "1", "2", "3", "4", "5" }) do
  hl.workspace_rule({ workspace = id, monitor = EXTERNAL, persistent = true })
end
for _, id in ipairs({ "6", "7", "8", "9" }) do
  hl.workspace_rule({ workspace = id, monitor = LAPTOP, persistent = true })
end

-- One workspace per monitor should be that monitor's default landing spot
hl.workspace_rule({ workspace = "1", monitor = EXTERNAL, default = true, persistent = true })
hl.workspace_rule({ workspace = "6", monitor = LAPTOP,   default = true, persistent = true })

-- Per-workspace look, while you are here
hl.workspace_rule({ workspace = "3", gaps_in = 0, gaps_out = 0, no_border = true })
```

Check what the compositor actually registered:

```bash
hyprctl workspacerules
hyprctl -j workspaces | jq -r '.[] | "\(.id) -> \(.monitor)"'
```

**After a hotplug**, nothing migrates workspaces back on its own. Re-apply by hand or from a script:

```bash
# Lua dispatcher form - `hyprctl dispatch moveworkspacetomonitor 3 DP-1` is the
# old hyprlang syntax and is rejected under a Lua config.
hyprctl dispatch 'hl.dsp.workspace.move({ workspace = "3", monitor = "DP-1" })'
```

A reload re-runs the rules, which is usually enough once the monitor is back:

```bash
hyprctl reload      # Omarchy: omarchy-restart-hyprctl
```

To automate it, bind the moves to a key or drive them from a `monitoradded` handler on `socket2` and call the dispatcher above for each workspace.

**Verify.** `hyprctl workspacerules` lists a `monitor` entry for each bound workspace; after `hyprctl reload` with both displays attached, `hyprctl -j workspaces | jq -r '.[] | "\(.id) -> \(.monitor)"'` shows each workspace on its intended output.

Sources: <https://wiki.hypr.land/Configuring/Basics/Workspace-Rules/> · <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://wiki.hypr.land/Configuring/Basics/Dispatchers/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://github.com/hyprwm/Hyprland/discussions/13755> · <https://github.com/hyprwm/Hyprland/issues/3120>

---
