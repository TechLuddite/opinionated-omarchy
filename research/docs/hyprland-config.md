# Hyprland configuration

39 problems. Sorted by severity, then by how often users hit it.

## Fix a hypr tool failing with symbol lookup error after a system update

`hypr-stack-symbol-lookup-error-git-build` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`

**Symptom.** Hyprland or a hypr* tool refuses to start after a system update with `<app>: symbol lookup error: <app>: undefined symbol: <symbol>` or `error while loading shared libraries: <lib>: cannot open shared object file: No such file or directory` — sometimes just an immediate crash with no message.

**Cause.** The hypr* stack has no stable ABI between its own libraries. Hyprland 0.56.2 links `libhyprutils.so.13`, `libhyprlang.so.2`, `libhyprgraphics.so.4`, `libhyprcursor.so.0` and `libaquamarine.so.13`, each with a version in the soname, so a rebuild of any one of them can move the number or drop a symbol. If you built Hyprland yourself, or use `-git` AUR packages (which count as building yourself), updating one component without rebuilding the rest leaves mismatched symbols. Mixing distro packages with self-built components produces the same result, and it is the usual way this happens: a `-git` package declares `provides=` for the repo package, so pacman will happily satisfy a repo Hyprland's dependency with a git-built library. Hyprland 0.55 and later also build against Lua for the new config API, and Lua is the first entry in upstream's mandatory build order.

> **Audit corrected this record.** Checked against the current Hyprland wiki and against this Omarchy 4 workstation (omarchy 4.0.2-1, hyprland 0.56.2-1, kernel 7.1.9-arch1-2). The symptom text, the do-not-symlink warning and the paru-versus-yay note are all genuinely on the FAQ page, confirmed by fetching content/faq/_index.md from hyprwm/hyprland-wiki. Three things were wrong. First, the build order list is not on the FAQ at all: the FAQ links out to the installation page, and the list lives in content/getting-started/installation.md under Manual build. The record's list matches it except that it omits the first entry, `Lua`, which Hyprland 0.55 and later need for the Lua config API, so the record's order was both mis-attributed and incomplete. Second, the list has grown `hyprwire` and `hyprtoolkit`, both installed here as hyprwire 0.3.1-3 and hyprtoolkit 0.5.4-4, and the record's `yay -S --rebuildall` line names neither. Third, the fallback recipe removes only `hyprland-git`, which leaves any other `-git` library installed to satisfy the repo package through `provides=`, so it does not actually end the mismatch. I confirmed the real linked set with `ldd /usr/bin/Hyprland`: libaquamarine.so.13, libhyprlang.so.2, libhyprutils.so.13, libhyprcursor.so.0 and libhyprgraphics.so.4, so the cause's library list was missing hyprcursor. `yay --rebuildall` is a real flag on yay v13.0.1 here ("Always build all AUR packages"). On the Omarchy interaction, I read `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` and `/usr/bin/omarchy-update-pacman-guard`: the guard aborts only when both `-S` and `-u` are present, so nothing in this fix trips it, and the fix contains no bare `-Sy`, so it is not a partial upgrade as written. The real partial-upgrade risk is installing into a system whose databases are ahead of its packages, which the corrected fix now names. Not exercised: I did not build or remove anything, so the rebuild order itself is taken from upstream rather than tested, and `hyprland-git` has never been installed on this machine. Also worth noting for the record's own framing, `hyprlock` is not installed on Omarchy 4 at all, since Omarchy locks through omarchy-shell. The `applies_to` list omits `omarchy` even though the problem is reachable there by installing `-git` packages, but a verdict cannot change that field.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Never symlink one .so version to another to silence the loader. Upstream is explicit that this leads to memory bugs and crashes, on both the Manual build section of the installation page and in the FAQ. Rebuild the whole stack or none of it: a half rebuilt stack is the state you are trying to leave. The separate partial-upgrade risk is in the recovery step, not the rebuild: `pacman -S hyprland` on a system whose sync databases are newer than its installed packages pulls in new dependencies against old ones. Upgrade fully first, with `omarchy update` on Omarchy, and never use a bare `pacman -Sy`.

**Fix.**

Rebuild the whole stack in dependency order, or stop mixing.

Order (from the Hyprland installation page, Manual build section):
```
Lua
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
Anything else in the stack, such as hyprlock or hyprsunset, builds in any order after Hyprland.

With AUR `-git` packages, force a clean rebuild of every one of them rather than a plain update. `hyprwire-git` and `hyprtoolkit-git` joined the stack and are easy to miss:

```bash
yay -S --rebuildall hyprutils-git hyprlang-git hyprgraphics-git hyprcursor-git \
  aquamarine-git hyprwayland-scanner-git hyprwire-git hyprtoolkit-git \
  xdg-desktop-portal-hyprland-git hyprland-git
```
The FAQ's own wording for this case is to remove every `-git` hypr* package and install them again, with `CleanBuild` on each. It notes paru has been problematic here, so use yay, and if you do use paru, clear `~/.cache/paru` of the hypr* packages by hand.

The robust fix is to drop to packaged releases entirely. Remove the whole git stack, not only `hyprland-git`: leaving `hyprutils-git` installed lets it satisfy the repo Hyprland's dependency through `provides=` and you are back in the same mismatch.

```bash
pacman -Qq | grep '^hypr.*-git$'          # see what you actually have
yay -Rns hyprland-git hyprutils-git hyprlang-git hyprgraphics-git hyprcursor-git \
  aquamarine-git hyprwayland-scanner-git hyprwire-git hyprtoolkit-git \
  xdg-desktop-portal-hyprland-git
sudo pacman -S hyprland xdg-desktop-portal-hyprland
```

**On Omarchy 4**, run `omarchy update` first so the sync databases and the installed packages are at the same point, then do the `pacman -S` above. Installing into a system whose databases are ahead of its packages is a partial upgrade even without `-Sy`. Omarchy's ALPM guard does not get in the way here: `/usr/bin/omarchy-update-pacman-guard` aborts only when `-S` and `-u` appear in the same pacman command line, so `pacman -S hyprland` runs, while a bare `yay` (which is `yay -Syu`) is refused and tells you to use `omarchy update`. Omarchy 4 ships `hyprland` from `extra` and is built against that package, so a `-git` Hyprland is unsupported there regardless of whether it links.

**Verify.** ```bash
hyprctl version                          # prints a version and a commit
ldd /usr/bin/Hyprland | grep 'not found' # no output
pacman -Qkk hyprland                     # no altered or missing files
```
`/usr/bin/hyprland` is a symlink to `/usr/bin/Hyprland`, so either name works with `ldd`.

Sources: <https://wiki.hypr.land/FAQ/> · <https://wiki.hypr.land/getting-started/installation/>

---

## Work out whether your Hyprland config should be hyprlang or Lua

`hyprlang-deprecated-lua-config-not-loading` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Edits to `~/.config/hypr/hyprland.conf` do nothing at all — no errors, no effect. Or the opposite: the wiki examples you copy (`hl.config({...})`, `hl.bind(...)`) are all rejected as syntax errors by your Hyprland.

**Cause.** Hyprland 0.55 deprecated hyprlang in favour of Lua and rewrote the whole wiki for Lua. The change landed on git on 26 April 2026 and shipped in 0.55 on 9 May 2026. Hyprland decides once, at startup, in `Jeremy::getMainConfigPath()`: if `~/.config/hypr/hyprland.lua` exists it is loaded exclusively and `hyprland.conf` is ignored entirely, if it does not exist `hyprland.conf` is loaded by the legacy hyprlang manager, and if neither exists Hyprland generates a default `hyprland.lua`. So a leftover `hyprland.lua` silently orphans your `.conf`, and copying Lua snippets into a `.conf` (or hyprlang into a `.lua`) fails wholesale. The only record of which engine won is a DEBUG line in Hyprland's own log, so nothing tells you on screen. Upstream says hyprlang is supported for 1 to 2 releases starting from 0.55 and is then dropped, and no new config features are added to it. Omarchy 4 is already past that decision: it ships `~/.config/hypr/hyprland.lua` from `omarchy-settings` and ships no `hyprland.conf`, so on Omarchy there is nothing to fall back to and removing the Lua file costs you the whole desktop rather than reverting it.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1) and against the Hyprland v0.56.2 source. The precedence claim is CONFIRMED twice over: `Jeremy::getMainConfigPath()` returns the `.lua` path if `Hyprutils::Path::findConfig(..., "lua")` finds one and only falls through to `.conf` otherwise, and the Lua announcement says the same in prose. `Config::initConfigManager()` then picks `Lua::CConfigManager` or `Legacy::CConfigManager` from the extension. The path is cached in a function-local static and only `Config::Supplementary::Jeremy::flushCachedCfgPath()` clears it, which `reloadRequest()` in `src/debug/HyprCtl.cpp` calls only when the request ends with `full-reset`, so the record's claim that plain `hyprctl reload` will not switch engines is CONFIRMED from source. The wiki text the danger paraphrases is verbatim: "`full-reset` should not be used unless really necessary." Four things were wrong. First, the version story: the record says "0.55 (May 2026)" and "guaranteed for a few releases", where the announcement says the change landed 26 April 2026 and that hyprlang lasts "1 - 2 releases starting from 0.55", which matters because 0.56 shipped on 20 July 2026 and the runway is nearly gone. Second, and this is the Omarchy defect, the record lists `omarchy` in applies_to and then hands an Omarchy user `mv ~/.config/hypr/hyprland.lua ~/.config/hypr/hyprland.lua.disabled`: there is no `hyprland.conf` in `~/.config/hypr` on this machine, `/usr/share/omarchy/config/hypr/` ships `hyprland.lua` and no `.conf`, and with neither file present `initConfigManager()` generates a stock default, so that command destroys the Omarchy desktop rather than reverting it. `omarchy-refresh-hyprland` is the supported restore and was read at `/usr/share/omarchy/bin/omarchy-refresh-hyprland`. Third, the diagnosis step was `ls`, when `hyprctl systeminfo` reports `configProvider: lua` directly (confirmed on this machine) and Hyprland logs `[cfg] Using lua config found at ...` (confirmed in this session's `$XDG_RUNTIME_DIR/hypr/*/hyprland.log`). Fourth, the verify used `hyprctl getoption general:gaps_in`, which on 0.56.2 prints `css gap data: 5 5 5 5` rather than a value (confirmed by running it), so it was swapped for `general:border_size`, which printed `int: 2`. The recovery gap the fix now closes is that a reader whose config does not load has no keybindings: `src/config/lua/Emergency.hpp` binds SUPER+Q to the first installed terminal, SUPER+R to `hyprland-run` and SUPER+M to exit, tripped in `CConfigManager::reload()` when there are errors and no binds. NOT exercised: nothing was written under `~/.config/hypr`, no config was renamed, `full-reset` was never run and neither was `omarchy-refresh-hyprland`, so the recovery paths are read from source and from the shipped scripts rather than performed. One plain `hyprctl reload` fired accidentally while probing argument handling and re-read the unchanged config with no effect.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `hyprctl reload full-reset` recreates the entire config context. The wiki says `full-reset` should not be used unless really necessary. Expect a visible flicker and layer-shell clients (bars, wallpapers) to re-init.

On Omarchy 4 the bigger risk is the hyprlang branch itself. There is no `~/.config/hypr/hyprland.conf` to fall back to, so moving `hyprland.lua` aside makes Hyprland write a stock default over it and you lose every Omarchy binding, the bar and the theme in one keystroke. Restore with `omarchy-refresh-hyprland`, which backs up what it replaces as `<file>.bak.<epoch>`.

**Fix.**

Do not guess from the file names. Ask the running compositor which engine it loaded.

```bash
hyprctl systeminfo | grep configProvider     # "lua" or "hyprlang"
hyprctl version | head -1                    # Lua needs >= 0.55
ls -l ~/.config/hypr/hyprland.lua ~/.config/hypr/hyprland.conf
```

Hyprland also records the decision in its own log at startup, which is the only place it is written down:

```bash
grep '\[cfg\]' "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log"
# [cfg] Using lua config found at /home/you/.config/hypr/hyprland.lua
# or
# [cfg] Lua config not found, using legacy config at /home/you/.config/hypr/hyprland.conf
```

**On Omarchy 4, you are on Lua and there is no hyprlang branch.** Omarchy ships
`~/.config/hypr/hyprland.lua` from `/usr/share/omarchy/config/hypr/hyprland.lua`
(owned by `omarchy-settings`) and ships no `hyprland.conf` at all. Renaming
`hyprland.lua` away does not fall back to anything: Hyprland finds no config,
writes a stock default `hyprland.lua`, and you lose every Omarchy default in one
step, including the bar, the theme, `SUPER + SPACE` and `SUPER + RETURN`. If you
have already broken your config, restore the shipped files instead of hand
editing. It backs up what it replaces as `<file>.bak.<epoch>`:

```bash
omarchy-refresh-hyprland          # restores hyprland.lua, bindings.lua, monitors.lua,
                                  # input.lua, looknfeel.lua, autostart.lua, .luarc.json
```

Run that from a login shell. `OMARCHY_PATH` is unset in a non-interactive ssh, so
over ssh use `ssh host 'bash -lc omarchy-refresh-hyprland'`.

**On plain Arch or another distro, to stay on hyprlang** you need an existing
`hyprland.conf` to fall back to. Check it is there first, because if both files
are missing Hyprland writes a fresh default `hyprland.lua` and you are back on Lua:

```bash
test -f ~/.config/hypr/hyprland.conf && mv ~/.config/hypr/hyprland.lua ~/.config/hypr/hyprland.lua.disabled
hyprctl reload full-reset
```

The current wiki no longer documents hyprlang. The archived 0.54 docs are at
https://wiki.hypr.land/0.54.0/. This is a short runway: upstream says hyprlang is
supported for 1 to 2 releases from 0.55 and then dropped, and 0.56 is already out.

**To move to Lua**, create `~/.config/hypr/hyprland.lua`. Split files with
`require()`, not `source =`:

```lua
-- ~/.config/hypr/hyprland.lua
require("monitors")          -- ~/.config/hypr/monitors.lua
require("awesomeconf/keybinds")
hl.config({ general = { gaps_in = 5, gaps_out = 10, border_size = 2 } })
hl.bind("SUPER + Return", hl.dsp.exec_cmd("kitty"))
```

`hyprctl reload` alone will NOT switch engines. The resolved config path is cached
for the life of the compositor and only `full-reset` flushes it:

```bash
hyprctl reload full-reset
```

**If the config errors and you are left with no keybindings at all**, Hyprland
0.55+ trips emergency mode and binds three keys for you, and prints them on screen:

```
SUPER + Q   launch the first of kitty, alacritty, foot, wezterm, gnome-terminal, xterm
SUPER + R   hyprland-run
SUPER + M   exit Hyprland
```

Emergency mode only trips when the config raised an error AND no binds were
registered. If your config half loaded you may have neither. A TTY on
`CTRL + ALT + F2` always works.

**Verify.** `hyprctl systeminfo | grep configProvider` reports `lua` or `hyprlang` and is the definitive answer. Then `hyprctl getoption general:border_size` reflects the value from the file you just edited, and a deliberate typo in that file shows up in `hyprctl configerrors`. Use `border_size` rather than `general:gaps_in`, which on 0.56 prints `css gap data: 5 5 5 5` instead of a single number.

Sources: <https://hypr.land/news/26_lua> · <https://hypr.land/news/update55> · <https://wiki.hypr.land/Configuring/Start/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://hypr.land/news/26_lua/> · <https://wiki.hypr.land/0.54.0/> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/supplementary/jeremy/Jeremy.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/ConfigManager.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/debug/HyprCtl.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/Emergency.hpp> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/using-hyprctl.md>

---

## NVIDIA on Hyprland: black screen at start, flicker on wake, or the wrong GPU driving the outputs

`nvidia-hyprland-modeset-cursors-mgpu` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `wayland`

**Symptom.** Hyprland starts to a black screen or exits immediately on an NVIDIA box, or it runs but flickers badly in Electron apps and XWayland games, or on a hybrid laptop the external HDMI/DP outputs are dead while the internal panel works, or the mouse pointer leaves a trail or disappears over fullscreen windows. `sudo cat /sys/module/nvidia_drm/parameters/modeset` prints `N` instead of `Y`. That file is mode 0400, so an ordinary user gets `Permission denied` rather than a letter, and a permission error is not a diagnosis.

**Cause.** Four separate NVIDIA-specific requirements, all of which look the same from the user's seat. (1) DRM mode setting is off, so there is no DRM master for the compositor to take. On drivers older than 560 this had to be switched on by hand with `nvidia_drm.modeset=1`. From `nvidia-utils` 560.35.03-5 Arch enables it by default, and in the 610 series the module's own default is already on, so on a current Arch or Omarchy install this branch is almost always already satisfied and the real fault is one of the other three. (2) The wrong driver package for the card. 50xx-series and newer require the open kernel modules, NVIDIA recommends them for Turing and Ampere (16xx/20xx) and later, and older cards need the legacy branch. (3) On hybrid Intel-or-AMD-plus-NVIDIA laptops, Aquamarine picks a primary GPU on its own and a monitor wired to the card that was not selected simply does not appear. (4) NVIDIA's hardware cursor plane needs a CPU buffer. Hyprland's `cursor:use_cpu_buffer` defaults to 2, auto, which already enables it on NVIDIA, so a pointer still misbehaving on a current release is a case for `cursor:no_hardware_cursors` rather than for `use_cpu_buffer`. Separately, XWayland game flicker is the implicit-sync gap, fixed by explicit sync in xorg-xwayland 24.1 or later plus wayland-protocols 1.34 or later plus driver 555 or later.

> **Audit corrected this record.** Re-audited against this Omarchy 4 workstation, which has an NVIDIA RTX 3090 with nvidia-open-dkms 610.57.04-1 and hyprland 0.56.2-1, and against the current Hyprland and Arch wikis. Most of the record held: the driver split, the early-KMS MODULES list, the i915-first note for Intel hybrids, the AQ_DRM_DEVICES and AQ_FORCE_LINEAR_BLIT advice with the udev symlink recipe, and the XWayland explicit-sync version floors all still match content/nvidia/_index.md and content/configuring/extra/multi-gpu.md in hyprwm/hyprland-wiki. Omarchy's side still matches install/hardware/nvidia.sh and default/hypr/nvidia.lua, both read on disk. Four things were wrong, and three of them are version drift. First, `/sys/module/nvidia_drm/parameters/modeset` is declared `bool, 0400` at line 35 of `/usr/src/nvidia-610.57.04/kernel-open/nvidia-drm/nvidia-drm-linux.c`, so the record's symptom, fix and verify all tell the reader to run a command that returns `Permission denied` unprivileged. Confirmed by running it here. It needs sudo, and the Arch wiki prints it with a root prompt for the same reason. Second, the whole modeset step is now largely obsolete: `nvidia-drm-os-interface.c` line 45 sets `nv_drm_modeset_module_param = true` as the in-driver default, and the Arch wiki says DRM has been enabled by default since nvidia-utils 560.35.03-5, so framing `modeset=1` as the headline cause misdirects a reader on a current install. Third, `sudo mkinitcpio -P` does not work on Omarchy 4. `/etc/mkinitcpio.d/` is empty here and `/usr/bin/mkinitcpio` calls `die 'No presets found in %s'` in the `-P` case, so the command aborts and rebuilds nothing. Omarchy builds a UKI through `limine-mkinitcpio-hook`, whose script is `/usr/share/libalpm/scripts/limine-mkinitcpio-install`, so the fix now says to fire that hook by reinstalling the kernel package, and notes that `/usr/bin/omarchy-update-pacman-guard` aborts only when `-S` and `-u` are both present, so nothing here trips the guard and there is no bare `-Sy`. Fourth, step 6 is stale: the Arch NVIDIA/Tips_and_tricks page says `NVreg_PreserveVideoMemoryAllocations` was for the 430 to 590 drivers and was succeeded by `NVreg_UseKernelSuspendNotifiers=1` on 595 and later, and that the three nvidia sleep services are now disabled by default per upstream. Confirmed on this box: nvidia-utils ships `/usr/lib/modprobe.d/nvidia-sleep.conf` setting `NVreg_UseKernelSuspendNotifiers=1` and `NVreg_TemporaryFilePath=/var/tmp`, `sort /proc/driver/nvidia/params` shows both, `/proc/cmdline` carries no nvidia parameter at all, and `systemctl is-enabled nvidia-suspend nvidia-hibernate nvidia-resume` returns `disabled` three times. The record's advice to enable them would be a regression. I also corrected two smaller points. `hyprctl getoption cursor:use_cpu_buffer` returns `int: 2` with `set: false` here, and the wiki's config-options table gives `2` as auto, enabled with NVIDIA, so setting it to 1 on an NVIDIA card is a no-op and `no_hardware_cursors` is the knob that does something. Omarchy sets `ELECTRON_OZONE_PLATFORM_HINT` to `wayland` in envs.lua, not `auto` in nvidia.lua, which the previous audit noted as a nit without giving the value. The kernel-parameter branch now names Omarchy's real mechanism, `/etc/limine-entry-tool.d/*.conf`, which I read on disk. Not exercised: I changed nothing, rebuilt no initramfs and rebooted nothing, so the corrected rebuild path is read from the hook script and mkinitcpio source rather than run. I could not list `/boot` to confirm the fallback UKI file exists, because the ESP is mounted dmask=0077, so the danger note tells the reader to check the boot menu instead. This machine is a single-GPU NVIDIA desktop, so the hybrid and multi-GPU branches were checked against the wiki only. Severity and frequency are left alone: the modeset branch is now rare, but the multi-GPU, cursor and XWayland flicker branches are still very common on NVIDIA, and a black screen at start is still high.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Editing `/etc/mkinitcpio.conf.d` and rebuilding the initramfs can leave you with an image that references a module that does not exist, which boots to a black screen. Confirm `dkms status` shows the module `installed` for every kernel before rebooting. Do not run `mkinitcpio -P` on Omarchy 4: with no presets in `/etc/mkinitcpio.d/` it aborts rather than rebuilding, and the real path is the `limine-mkinitcpio-hook` pacman hook, reached by reinstalling the kernel package. Omarchy 4 does give you a way back: `/etc/limine-entry-tool.d/omarchy-defaults.conf` sets `ENABLE_LIMINE_FALLBACK=yes` and a `BOOT_ORDER` of `*, *fallback, Snapshots`, so a fallback entry and Snapper snapshots are selectable in the boot menu. Check that the fallback entry is really there before you reboot, because a machine that has never rebuilt its UKI may not have one yet. Loading the NVIDIA modules early also breaks resume from hibernation, because the nvidia module in the initramfs has no access to `NVreg_TemporaryFilePath` where the previous video memory is stored. If you hibernate, drop the `MODULES` line and rebuild.

**Fix.**

**1. Check DRM mode setting before changing anything.** The `modeset` parameter is declared
`module_param_named(modeset, nv_drm_modeset_module_param, bool, 0400)` in the driver source, so only
root can read it back:

```bash
sudo cat /sys/module/nvidia_drm/parameters/modeset   # must print Y
```

On a current install it already prints `Y`. Arch turns DRM on by default from `nvidia-utils`
560.35.03-5, and in the 610 series the module default is `true` in the driver itself. Omarchy's
installer writes both files anyway, so on Omarchy 4 `/etc/modprobe.d/nvidia.conf` and
`/etc/mkinitcpio.conf.d/nvidia.conf` already exist.

Only on a driver older than 560, or a distribution that does not set it, write them yourself:

```bash
sudo tee /etc/modprobe.d/nvidia.conf >/dev/null <<'EOF'
options nvidia_drm modeset=1
EOF

sudo mkdir -p /etc/mkinitcpio.conf.d
sudo tee /etc/mkinitcpio.conf.d/nvidia.conf >/dev/null <<'EOF'
MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
EOF
```

On a hybrid Intel iGPU plus NVIDIA dGPU machine, load `i915` first or Electron and Chromium apps
stall for up to a minute after boot: `MODULES+=(i915 nvidia nvidia_modeset nvidia_uvm nvidia_drm)`.

Keep the file name `nvidia.conf`. On Omarchy 4 it sorts before `omarchy_hooks.conf`, which reads
`MODULES` and drops the `kms` hook when nvidia_drm is early loaded and NVIDIA owns every display
controller. A differently named drop-in that sorts after it changes that decision.

**Regenerating the initramfs is not the same command on both.**

Plain Arch:

```bash
sudo mkinitcpio -P
```

Omarchy 4: do not run that. `/etc/mkinitcpio.d/` holds no presets, and `mkinitcpio -P` calls
`die 'No presets found in %s'` when the glob is empty, so the command aborts without building
anything. Omarchy boots a UKI built by `limine-mkinitcpio-hook`, whose pacman hook runs
`/usr/share/libalpm/scripts/limine-mkinitcpio-install`. Fire that hook by reinstalling the kernel
package you run:

```bash
sudo pacman -S linux      # or linux-lts, linux-zen, whichever is installed
```

Omarchy's update guard does not block this. `/usr/bin/omarchy-update-pacman-guard` aborts only when
`-S` and `-u` appear in the same pacman command line. Never use a bare `pacman -Sy`.

**2. Install the right driver set.** DKMS variants so every installed kernel is covered, plus headers
for each kernel:

```bash
# GSP-capable (Turing/16xx/20xx and newer, mandatory on 50xx)
sudo pacman -S --needed linux-headers nvidia-open-dkms nvidia-utils lib32-nvidia-utils egl-wayland libva-nvidia-driver

# Older, pre-GSP cards, the 580xx legacy branch (AUR)
# yay -S nvidia-580xx-dkms nvidia-580xx-utils lib32-nvidia-580xx-utils
```

`egl-wayland` is already a dependency of `nvidia-utils`, so naming it is belt and braces rather than
a separate step. This is the same split Omarchy's installer makes in `install/hardware/nvidia.sh`.
Check which side you are on with `omarchy-hw-nvidia-gsp; echo $?` (0 means use nvidia-open-dkms).

**3. Environment variables** in `~/.config/hypr/hyprland.lua`. On Omarchy 4 you do not need any of
this, and duplicating it only creates a second place to keep in step. Omarchy sets `NVD_BACKEND`,
`LIBVA_DRIVER_NAME` and `__GLX_VENDOR_LIBRARY_NAME` in
`/usr/share/omarchy/default/hypr/nvidia.lua`, gated on whether the card is GSP-capable, and it sets
`ELECTRON_OZONE_PLATFORM_HINT` to `wayland` in `/usr/share/omarchy/default/hypr/envs.lua`. On
pre-GSP cards Omarchy sets `NVD_BACKEND` to `egl` and leaves `LIBVA_DRIVER_NAME` unset.

On any other distribution:

```lua
hl.env("LIBVA_DRIVER_NAME", "nvidia")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
hl.env("NVD_BACKEND", "direct")                  -- "egl" on pre-GSP cards
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")   -- stops Electron/CEF flicker
```

**4. Pick the GPU explicitly on multi-GPU and hybrid boxes.** Never use a bare `/dev/dri/cardN`,
because those numbers are reassigned at boot. Find the PCI id, then pin a udev symlink:

```bash
lspci -d ::03xx            # list display controllers
ls -l /dev/dri/by-path     # map PCI id to cardN
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

**5. Cursor artefacts.** Check what is in effect before setting anything:

```bash
hyprctl getoption cursor:use_cpu_buffer
hyprctl getoption cursor:no_hardware_cursors
```

Both default to `2`, auto. `use_cpu_buffer` auto means enabled on NVIDIA, so on an NVIDIA card it is
already on and writing `use_cpu_buffer = 1` changes nothing. The option that changes behaviour is
`no_hardware_cursors`, whose auto means disable only while tearing:

```lua
hl.config({
  cursor = {
    no_hardware_cursors = 1,   -- 0 use hw cursors if possible, 1 never, 2 auto
  },
})
```

On Omarchy put that in `~/.config/hypr/looknfeel.lua`, which is where Omarchy's own
`install/user/hardware/fix-nouveau-cursor.sh` appends the same setting for nouveau cards.

**6. Suspend and wake.** The mechanism changed in the 595 series and the old advice is now wrong on a
current driver.

Drivers 595 and later, which includes everything Omarchy 4 installs today: video memory preservation
is handled by kernel suspend notifiers, set by the packaged `/usr/lib/modprobe.d/nvidia-sleep.conf`.
There is nothing to add to the kernel command line, and `nvidia-suspend.service`,
`nvidia-hibernate.service` and `nvidia-resume.service` are deliberately disabled. Leave them
disabled. Verify with:

```bash
sort /proc/driver/nvidia/params | grep -E 'UseKernelSuspendNotifiers|TemporaryFilePath'
```

You want `UseKernelSuspendNotifiers: 1` and `TemporaryFilePath: "/var/tmp"`.

Drivers 430 to 590 only: enable `nvidia-suspend.service`, `nvidia-hibernate.service` and
`nvidia-resume.service`, which Arch already does, and put
`nvidia.NVreg_PreserveVideoMemoryAllocations=1` on the kernel command line. On Omarchy 4 a kernel
parameter goes in a drop-in under `/etc/limine-entry-tool.d/`, not in `/etc/default/grub`, and the
UKI has to be rebuilt afterwards:

```bash
printf 'KERNEL_CMDLINE[default]+=" nvidia.NVreg_PreserveVideoMemoryAllocations=1"\n' \
  | sudo tee /etc/limine-entry-tool.d/nvidia.conf
sudo pacman -S linux
```

**Verify.** ```bash
sudo cat /sys/module/nvidia_drm/parameters/modeset   # Y
sort /proc/driver/nvidia/params | grep -E 'UseKernelSuspendNotifiers|TemporaryFilePath'
hyprctl systeminfo | grep -iA2 'GPU information'
hyprctl monitors | grep '^Monitor'                   # every physical output listed
nvidia-smi
vainfo
```
The `modeset` read needs root because the parameter is mode 0400. `/proc/driver/nvidia/params` is readable unprivileged. A full-screen XWayland game should no longer flicker.

Sources: <https://wiki.hypr.land/Nvidia/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Multi-GPU/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/nvidia.sh> · <https://github.com/basecamp/omarchy/blob/quattro/default/hypr/nvidia.lua> · <https://wiki.archlinux.org/title/NVIDIA> · <https://wiki.archlinux.org/title/NVIDIA/Tips_and_tricks>

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

## Rebuild hyprpm plugins after a Hyprland update breaks the headers

`hyprpm-plugins-broken-after-hyprland-update` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`

**Symptom.** After a Hyprland update, plugins stop loading. `hyprpm reload` prints `<plugin> will be loaded after restarting Hyprland`, or `hyprpm update` fails with `failed to install headers with error code 2` or `Headers corrupted. Please run hyprpm update to fix those.` `hyprctl plugin list` reports `no plugins loaded` and the plugin keybinds do nothing. The Hyprland log records `Plugin <path> could not be loaded. (API version mismatch)`.

**Cause.** Hyprland plugins are C++ shared objects compiled against the exact Hyprland build they will run inside, and there is no stable ABI. On load, Hyprland reads the plugin's reported API version and refuses anything that does not match its own `HYPRLAND_API_VERSION`, logging `Plugin <path> could not be loaded. (API version mismatch)`. Every Hyprland version bump therefore invalidates every installed plugin until it is rebuilt. hyprpm keeps its own header tree and validates it two ways: it compares the `GIT_COMMIT_HASH` in the installed `version.h` against the running Hyprland's commit hash, and a stored ABI hash against the running Hyprland's ABI string, the value `hyprctl version` prints as `Version ABI string`. A mismatch in either means the headers must be re-fetched and the plugins rebuilt. On Hyprland 0.56.2 that header tree is at `/var/cache/hyprpm/<username>/headersRoot` and is root owned, not in your home directory, so hyprpm escalates with sudo, doas or run0 to write it. Omarchy 4 plays no part: `hyprpm` ships inside the `hyprland` package at `/usr/bin/hyprpm` and nothing in Omarchy calls it, so `omarchy update` upgrades Hyprland and leaves stale plugins behind.

> **Audit corrected this record.** Checked on this workstation, omarchy 4.0.2-1 and hyprland 0.56.2-1, plus the Hyprland v0.56.2 source. The headline claim holds: plugins are built against one exact Hyprland build and `src/plugins/PluginSystem.cpp` refuses a load when the plugin's API version does not match `HYPRLAND_API_VERSION`, while `hyprpm/src/core/PluginManager.cpp` `headersValid()` compares the headers' `GIT_COMMIT_HASH` against the running commit and a stored ABI hash against the running ABI string. Three things were wrong for Omarchy 4 and Hyprland 0.56.2. First, the cleanup command is dead: `hyprpm/src/core/DataState.cpp` puts the state at `/var/cache/hyprpm/<username>` with headers in `headersRoot`, so `rm -rf ~/.local/share/hyprpm ~/.cache/hyprpm` removes nothing, and confirmed on this machine that neither path exists while `/usr/bin/hyprpm` is present and owned by `hyprland 0.56.2-1`. The replacement is `hyprpm purge-cache`, which `hyprpm --help` on the installed binary lists and which hyprpm itself recommends in its own error output. Second, the quoted symptom strings are stale: `pkexec` is gone from hyprpm, `hyprpm/src/helpers/Sys.cpp` now uses sudo, doas or run0, and the current text is `Headers corrupted. Please run hyprpm update to fix those.` The 2023 issue 4284 documented the pkexec wording and no longer describes anything 0.56.2 emits, so it is removed. `failed to install headers with error code 2` does still exist and issue 5896 stays. Third, the autostart snippets were unlabelled: Omarchy 4 is Lua and its own `/usr/share/omarchy/default/hypr/autostart.lua` uses exactly `hl.on("hyprland.start", function() hl.exec_cmd(...) end)`, so both branches are now labelled and the user file named as `~/.config/hypr/autostart.lua`. Added the Omarchy 4 fact that matters most: `hyprpm` appears nowhere in `/usr/share/omarchy` and nowhere in the omacom/omarchy `quattro` tree (GitHub code search returned 0), so `omarchy update` does nothing about plugins, and the similarly named `omarchy plugin` / `omarchy-plugin-update` commands manage Quickshell QML plugins under `~/.config/omarchy/plugins/` and are a different system entirely. The build-dependency line was checked against `/usr/bin/omarchy-update-pacman-guard` and is safe: the guard only aborts when both `-S` and `-u` are present, so `pacman -S --needed` passes. Frequency lowered from very-common to common, because on Omarchy 4 there is no shipped plugin story at all and users are steered to the shell plugin system instead. NOT exercised: no plugin was installed, so `hyprpm add`, `hyprpm update`, `hyprpm list` and `hyprpm reload` were not run on this machine, per the read-only rule.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Plugins run inside Hyprland as native code. A bad one can crash the whole graphical session and take unsaved work in every open window with it, and a malicious one can do anything your user can. Read the source of any plugin before enabling it, and never load a `.so` someone sent you. Hyprland's plugin-unload-on-crash protections are best effort, not guaranteed. `hyprpm update` and `hyprpm purge-cache` escalate to root with sudo, doas or run0 to write under `/var/cache/hyprpm`, so be sure what you are running before you type the password.

**Fix.**

Rebuild the plugins against the new headers every time Hyprland changes version.

Install the build dependencies first. This is a plain install with no database refresh, so Omarchy's ALPM guard does not block it. The guard in `/usr/bin/omarchy-update-pacman-guard` only aborts when both `-S` and `-u` are present:

```bash
sudo pacman -S --needed cpio cmake git meson gcc
```

Then rebuild and reload:

```bash
hyprpm update       # re-fetch the headers for the running Hyprland and rebuild every plugin
hyprpm list         # confirm each plugin is enabled and was built
hyprpm reload -n    # load them, with a notification
```

If `hyprpm reload` prints `<plugin> will be loaded after restarting Hyprland`, the running compositor does not match what the plugin was built against. Run `hyprpm update` first, then log out and back in.

If the headers are wedged, reset hyprpm completely. On Hyprland 0.56.2 the hyprpm state lives in `/var/cache/hyprpm/<username>` and is root owned, so deleting `~/.local/share/hyprpm` or `~/.cache/hyprpm` does nothing at all. Use the built-in command, which escalates with sudo, doas or run0 and will prompt for your password:

```bash
hyprpm purge-cache
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprexpo
hyprpm update && hyprpm reload
```

Make the plugins load at every startup.

Omarchy 4 and any Hyprland 0.55 or newer use Lua. Put this in `~/.config/hypr/autostart.lua`, which is the file Omarchy reserves for your own startup commands:

```lua
hl.on("hyprland.start", function() hl.exec_cmd("hyprpm reload -n") end)
```

Older Hyprland on hyprlang config, in `hyprland.conf`:

```ini
exec-once = hyprpm reload -n
```

If Hyprland now crashes on start, the plugin is the cause. Disable it from a TTY:

```bash
hyprpm disable <plugin-name>
```

Manual plugins that do not go through hyprpm need `sudo make installheaders` from a Hyprland checkout at your exact version, then `hyprctl plugin load /absolute/path/to/plugin.so`. The path must be absolute.

Omarchy 4 note. `omarchy plugin ...` and `omarchy-plugin-update` are a different system and will not help here. They manage QML plugins for `omarchy-shell` under `~/.config/omarchy/plugins/`, which are Quickshell code with no connection to hyprpm or to Hyprland C++ plugins. There is no reference to `hyprpm` anywhere in `/usr/share/omarchy` or in the omacom/omarchy `quattro` tree, so `omarchy update` upgrades Hyprland and leaves your plugins stale. Running `hyprpm update` afterwards is on you.

**Verify.** `hyprctl plugin list` names the plugin instead of printing `no plugins loaded`, and `hyprpm list` shows it enabled with no version mismatch. `hyprpm update` completing without a `failed to install headers` or `Headers corrupted` line means the header tree now matches the commit hash and ABI string that `hyprctl version` reports.

Sources: <https://wiki.hypr.land/Plugins/Using-Plugins/> · <https://github.com/hyprwm/Hyprland/issues/5896> · <https://github.com/hyprwm/Hyprland/issues/6910> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/hyprland-plugins/using-plugins.md> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/hyprpm/src/core/DataState.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/hyprpm/src/core/PluginManager.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/hyprpm/src/helpers/Sys.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/plugins/PluginSystem.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/hyprpm/src/main.cpp>

---

## Get out of Hyprland emergency mode when a Lua error registered no binds

`hyprland-emergency-mode-no-binds-registered` · severity: **high** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`

**Symptom.** A banner sits on top of every workspace: `Emergency mode tripped: A lua config error resulted in no binds being registered. Emergency binds active: SUPER + Q -> any known terminal, SUPER + R -> hyprland-run, SUPER + M -> Exit` followed by `Your config has errors:` and a Lua stack traceback such as `cannot open /usr/share/omarchy/default/hypr/bootstrap.lua: No such file or directory`. None of your normal keybindings work.

**Cause.** Hyprland 0.56.2 trips emergency mode when a config reload finishes with at least one error and zero keybinds registered. The test is in `src/config/lua/ConfigManager.cpp`: `const bool emergencyModeTripped = !m_errors.empty() && g_pKeybindManager->m_keybinds.empty();`. Only the main config file is syntax checked before anything is torn down. The reload then clears every keybind, resets the Lua state, and runs the config under a protected call, so a `require()` or `dofile()` of a path that does not exist raises at that point, after the old binds have already gone. On Omarchy 4 the first executable line of `~/.config/hypr/hyprland.lua` is `dofile((os.getenv("OMARCHY_PATH") or "/usr/share/omarchy") .. "/default/hypr/bootstrap.lua")`, so one missing file under `/usr/share/omarchy` takes the whole config down. The usual triggers are a typo in a `require()` path, a syntax error early in `hyprland.lua`, and a file that vanishes for a moment while pacman replaces the package that owns it during `omarchy update`.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1) and against Hyprland v0.56.2 source fetched from hyprwm/Hyprland. Emergency mode is real and still called that: `src/config/lua/Emergency.hpp` holds the `EMERGENCY_PCALL` Lua block, and the same strings are in the shipped `/usr/bin/Hyprland` binary, so the escape route is confirmed on this machine and not only in the source. The binds are `SUPER + Q` which launches the first installed of kitty, alacritty, foot, wezterm, gnome-terminal, xterm, `SUPER + R` which launches hyprland-run, and `SUPER + M` which exits. That list is the whole escape route and the record never gave it, so a reader could not tell whether SUPER + Q would do anything: on stock Omarchy 4 it does, because `foot` is at line 41 of `/usr/share/omarchy/install/omarchy-base.packages` and `hyprland-run` is owned by `hyprland-guiutils 0.2.2-2`. The record's cause sentence about "require() scope protection" does not describe anything in the code, so I replaced it with the real sequence from `src/config/lua/ConfigManager.cpp`, where phase 1 only runs `luaL_loadfile` on the main config path and the runtime error lands after `clearKeybinds()`. The log path held: `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log` is the live path here, but `HYPRLAND_INSTANCE_SIGNATURE` is absent from a text console or a plain ssh shell, so I added the wiki's newest-instance form for a reader who has no session terminal. The manual `hyprctl eval` pause and resume pair is mis-specialised to Omarchy: `/usr/share/omarchy/bin/omarchy-hyprland-reload-guard` does the same job, saves and restores the prior values under `/run/omarchy/hyprland-reload-guard/`, and is already wired to `/usr/share/libalpm/hooks/10-omarchy-hyprland-reload-pause.hook` and `90-omarchy-hyprland-reload-resume.hook`, all three read on this machine. The `omarchy-refresh-hyprland` step was the worst advice on the record: read at `/usr/share/omarchy/bin/omarchy-refresh-hyprland`, it overwrites seven files in `~/.config/hypr` through `omarchy-refresh-config` and touches nothing under `/usr/share/omarchy`, so it cannot fix the cited mid-transaction cause and it destroys user overrides, recoverable only from `.bak.<epoch>` copies. I confirmed `omarchy update` itself never calls it, and that the migrations under `/usr/share/omarchy/migrations/` patch `hyprland.lua` surgically rather than replacing it, so neither the record's edits nor the pcall wrapper are transient. Issue 8637 was read in full on omacom/omarchy: it describes exactly this record's scenario, names the pause hook, and is still open as of 2026-09-13, so the trigger is current. The basecamp URL on the record 404s for an anonymous fetch, so it is removed in favour of the omacom one. NOT exercised: I did not induce emergency mode, break a config, run `hyprctl reload`, or press any emergency bind, because this is the operator's daily workstation, so the bind behaviour is confirmed from source and from strings in the installed binary rather than by tripping it.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `debug:suppress_errors = true` hides real config errors, the emergency banner included, so turn it back off when you are done. The emergency binds still register while it is on, but nothing on screen tells you the config is broken. Do not reboot to clear this while a pacman transaction is still running, because you can end up with a half applied upgrade. `omarchy-refresh-hyprland` overwrites seven files in `~/.config/hypr` with the Omarchy defaults and keeps only timestamped `.bak` copies of your versions.

**Fix.**

Emergency mode registers three binds of its own, so you are not locked out:

- `SUPER + Q` launches the first of `kitty`, `alacritty`, `foot`, `wezterm`, `gnome-terminal`, `xterm` that is installed.
- `SUPER + R` launches `hyprland-run`.
- `SUPER + M` exits Hyprland.

On a stock Omarchy 4 install `foot` is listed in `/usr/share/omarchy/install/omarchy-base.packages` and `hyprland-run` comes from the `hyprland-guiutils` package, so the first two both work. If none of those six terminals is installed, switch to a text console with `Ctrl + Alt + F2` and log in there instead.

Read the actual error. From a terminal inside the session:

```bash
hyprctl configerrors
tail -n 200 "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log"
```

From a text console or over ssh `HYPRLAND_INSTANCE_SIGNATURE` is not set, so pick the newest instance directory:

```bash
tail -n 200 "$XDG_RUNTIME_DIR/hypr/$(ls -t "$XDG_RUNTIME_DIR/hypr/" | head -n 1)/hyprland.log"
```

If the file was missing only while pacman was replacing it, let `omarchy update` finish, then reload once:

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

Omarchy ships a helper that does the same check up front, `/usr/share/omarchy/default/hypr/require_optional.lua`:

```lua
local require_optional = require("default.hypr.require_optional")
require_optional.module("maybe-nonexistent")
```

To stop reloads firing during a package transaction, use the shipped guard rather than a raw `hyprctl eval`:

```bash
omarchy-hyprland-reload-guard pause
# ... run the transaction ...
omarchy-hyprland-reload-guard resume
```

Omarchy 4 already runs that pair automatically around any `omarchy-settings` upgrade, through `/usr/share/libalpm/hooks/10-omarchy-hyprland-reload-pause.hook` and `90-omarchy-hyprland-reload-resume.hook`. The guard saves the previous values of `misc.disable_autoreload` and `debug.suppress_errors` under `/run/omarchy/hyprland-reload-guard/` and restores them, where a hand written `hyprctl eval` pair turns both off whatever they were set to before.

Last resort, and only when the broken file is one of your own:

```bash
omarchy-refresh-hyprland
hyprctl reload
```

That replaces all seven of `~/.config/hypr/.luarc.json`, `autostart.lua`, `bindings.lua`, `input.lua`, `looknfeel.lua`, `hyprland.lua` and `monitors.lua` with the Omarchy defaults, keeping each old file as `<name>.bak.<epoch>`. It touches nothing under `/usr/share/omarchy`, so it does not help when the missing file is a shipped default.

**Verify.** The emergency banner disappears, `hyprctl configerrors` is empty, and `hyprctl binds` lists your bindings again.

Sources: <https://wiki.hypr.land/Configuring/Start/> · <https://wiki.hypr.land/Crashes-and-Bugs/> · <https://github.com/omacom/omarchy/issues/8637> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/Emergency.hpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/ConfigManager.cpp>

---

## Fix a Lua config getter that hangs the keybindings menu or eats all memory

`lua-config-getters-infinite-loop-at-load` · severity: **high** · frequency: **occasional** · applies to: `arch`, `hyprland`, `omarchy`

**Symptom.** `omarchy-menu-keybindings` (SUPER+K) never opens — no menu, no error, no timeout. `omarchy-menu-keybindings --print` hangs forever. In worse cases the machine runs out of memory and freezes. Hyprland itself is fine: `hyprctl reload` and `hyprctl configerrors` are clean.

**Cause.** Iterating any `hl.*` getter with `ipairs` at config-evaluation time. Omarchy's keybinding scanner (`build_lua_bind_cache()` in `/usr/share/omarchy/bin/omarchy-menu-keybindings`) re-evaluates `~/.config/hypr/hyprland.lua` in a bare `lua` interpreter with `hl` replaced by a stub. The stub implements only `hl.bind`, `hl.dsp` and `hl.get_config`, and answers every other key through a `__index` metamethod that returns a `noop` table which is itself indexable and callable. So `hl.get_monitors()` returns `noop`, and `ipairs(noop)` reads index 1, 2, 3 and never hits nil. That is the whole family, not three names: Hyprland 0.56.2 registers `get_windows`, `get_window`, `get_active_window`, `get_urgent_window`, `get_workspaces`, `get_workspace`, `get_active_workspace`, `get_monitors`, `get_monitor`, `get_layers`, `get_workspace_windows` and more, and the stub covers none of them. Hyprland itself is unaffected because the compositor evaluates the config under a watchdog that aborts after 1500 ms, and inside the real compositor the getters return real tables anyway. Only the scanner subprocess spins. Two things make it worse than a hang. If the loop body allocates, for example `table.insert`, that `lua` process grows without bound. And because the menu never appears, pressing SUPER+K again starts another one, so the leak compounds: the upstream reporter accumulated 63 `lua` processes holding about 56 GB, hit a kernel global OOM, and the machine rebooted. Still unfixed in omarchy 4.0.2-1.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, hyprland 0.56.2-1, lua 5.5.1) and against Hyprland v0.56.2 source. The mechanism is CONFIRMED here, not inferred: I copied the stub out of `/usr/share/omarchy/bin/omarchy-menu-keybindings` into a scratch script and ran it, and `ipairs` over it passed 1,000,000 iterations without reaching nil while `#stub` was 0, so the record's guard genuinely works. The scanner path is CONFIRMED: `build_lua_bind_cache()` runs `pcall(dofile, "$HOME/.config/hypr/hyprland.lua")` in a bare `lua` with `hl` set to a table whose metatable `__index` returns a callable, indexable `noop`, and `pcall` does not interrupt a loop. `SUPER + K` is bound to `omarchy-menu-keybindings` at `/usr/share/omarchy/default/hypr/bindings/utilities.lua:10`. The getters are CONFIRMED registered in `src/config/lua/bindings/LuaBindingsQuery.cpp` and the events `hyprland.start`, `monitor.added` and `monitor.layout_changed` in the wiki source, so the fix's API calls are real. The cited issue omacom/omarchy#7025 is open and does support the claim, including the memory exhaustion. Five corrections. The cause named three getters when the stub misses every one of the twenty or so `hl.get_*` functions, which a second reporter on the issue confirmed independently using `hl.get_windows()`. The cause left the compositor's immunity unexplained: `LUA_TIMEOUT_CONFIG_RELOAD_MS = 1500` in `src/config/lua/ConfigManager.hpp` plus `guardedPCall`'s instruction-count watchdog is why `hyprctl reload` stays clean, which is what a reader needs to stop suspecting Hyprland. The amplification was missing, and it is the reason this reaches OOM rather than staying a hang. The grep only covered three names and only `~/.config/hypr`, missing `~/.local/state/omarchy/` which Omarchy's `bootstrap.lua` also puts on `package.path`. The verify was unreliable because omarchy 4.0.2 added a scan cache at `~/.cache/omarchy/keybindings-<sha>.records`, which exists on this machine and is dated 29 August, so a reader can get a clean `--print` from a stale file. Severity raised from medium to high: the documented consequence is a kernel OOM that takes the session down and reboots the machine, which is not a medium-severity outcome even if the trigger is uncommon. Frequency left at occasional, because no file under `/usr/share/omarchy/default/hypr/` iterates a getter at load time (grep found only `hl.get_active_window()` and `hl.get_config()`, both inside functions), so a stock machine never trips it. The source URL was corrected: `https://github.com/basecamp/omarchy/issues/7025` returns a plain 404 to a browser, because GitHub's rename redirect covers the repository root but not the issue path, even though `gh issue view -R basecamp/omarchy` still resolves it through the API. NOT exercised: I did not reproduce the hang end to end, because that means writing a loop into `~/.config/hypr` on the operator's daily workstation and risking the OOM the record describes. The stub behaviour was reproduced in isolation instead, and the scanner, the bindings and the cache were read on disk.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** If the loop body allocates, each hung `lua` grows without bound, and every press of SUPER+K starts another one because the menu never appears to tell you the first failed. The upstream report reached 63 `lua` processes holding about 56 GB, a kernel global OOM, an OOM-killed Hyprland session and a reboot, in roughly two minutes on a 64 GB machine. Test config changes with a TTY available (`CTRL + ALT + F2`) and kill the runaway processes with `pkill -x lua` rather than pressing the key again.

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
-- react to hotplug:
hl.on("monitor.added", function(monitor)
  -- ...
end)
-- "hyprland.start" fires once per compositor start, so if the work also has to
-- survive a `hyprctl reload`, hook the arrangement event too:
hl.on("monitor.layout_changed", function()
  -- ...
end)
```

If you must run it at load, guard it. The stub has no `__len`, so `#stub` is 0 and this skips:
```lua
local mons = hl.get_monitors()
if type(mons) == "table" and #mons > 0 and #mons < 64 then
  for i = 1, #mons do local m = mons[i] end
end
```

A guard that names the stub directly works for any getter. Real getters return a
plain table, the stub returns one that is also callable:
```lua
local function real_list(value)
  local mt = type(value) == "table" and getmetatable(value) or nil
  if type(value) ~= "table" or (mt and mt.__call) then return {} end
  return value
end

for _, m in ipairs(real_list(hl.get_monitors())) do
  -- ...
end
```

Find the offender. Search every file the config can reach, not just `hyprland.lua`, because
Omarchy's bootstrap puts `~/.local/state`, `~/.config` and `$OMARCHY_PATH` on `package.path`,
and a third-party module such as `shezdy/hyprsplit` iterates all three list getters in its
own `init.lua`:
```bash
grep -rn 'hl\.get_' ~/.config/hypr/ ~/.local/state/omarchy/
```

Then look at each hit and ask whether it is inside an `hl.on(...)` callback or at
top level. Only top-level calls hang.

Recovery while it is hung: the runaway processes are ordinary user processes, so
kill them from a TTY (`CTRL + ALT + F2`) or any terminal before the machine runs
out of memory.
```bash
pkill -f omarchy-menu-keybindings
pkill -x lua
```

**Verify.** Clear the cache first, because omarchy 4.0.2 caches the scan in `~/.cache/omarchy/keybindings-<sha>.records` and a stale file makes a still-broken config look fixed.

```bash
rm -f ~/.cache/omarchy/keybindings-*.records
timeout 30 omarchy-menu-keybindings --print | wc -l
```

It returns a list of bindings and exits instead of hanging. A `timeout` exit status of 124 means it is still hung.

Sources: <https://github.com/omacom/omarchy/issues/7025> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsQuery.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/ConfigManager.hpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/ConfigManager.cpp> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/events.md>

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

## hyprctl keyword silently does nothing under a Lua config, so use eval or repl

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

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1, kernel 7.1.9-arch1-2) and against the three Hyprland wiki pages the record cites, all of which still resolve and still say what the record claims. Confirmed here: the record contains no hyprlang anywhere, every `input` option name, type and range in its block matches the Variables page, `hl.device({ name = ... })` is the current per-device form (Omarchy's own default/hypr/disabled-input-device.lua and omarchy-toggle-input-device use it), `hyprctl switchxkblayout <device|current|all> next|prev|ID` matches `hyprctl switchxkblayout --help` on 0.56.2, `hyprctl eval` exists on 0.56.2, `hyprctl getoption input.kb_layout` and `input:kb_layout` both work, and both wiki traps hold verbatim. The Omarchy claim is confirmed by reading /usr/share/omarchy/default/hypr/input.lua locally and at omacom/omarchy@quattro: it parses /etc/vconsole.conf, and ~/.config/hypr/input.lua here is byte-identical to the packaged fully commented-out template and is required after default.hypr.omarchy, so a user override genuinely wins. Five things were wrong or missing. First, `kb_options` replaces rather than merges, so the record's example silently drops Omarchy 4's `compose:caps,shift:both_capslock_cancel`, and its `caps:escape` collides with `compose:caps` because both claim Caps Lock (both option names verified in /usr/share/X11/xkb/rules/evdev.lst). Second, `sudo localectl set-x11-keymap fr` with no further arguments wipes `XKBMODEL` and `XKBOPTIONS`, confirmed in systemd's localectl.c where the omitted positionals are sent as empty strings, and this machine's /etc/vconsole.conf carries `XKBMODEL=pc105+inet` and `XKBOPTIONS=terminate:ctrl_alt_bksp` to lose. Third, `switchxkblayout current` targets the `main: yes` keyboard, which on this machine is `hl-virtual-keyboard-fcitx5` and not anything the operator types on, a trap Omarchy's own bar widget source documents. Fourth, the record told the reader to get a device name from `hyprctl devices` but gave two invented names and no rule for the lowercase-hyphen form, so the corrected fix prints them with `hyprctl -j devices` and uses real ones. Fifth, Omarchy 4 ships a supported surface the record ignores: the `omarchy.keyboard-layout` bar widget added by migration 1786279107, present in ~/.config/omarchy/shell.json here, which appears once kb_layout has more than one entry and cycles on click. The corrected fix also answers whether an update eats the edit: migration 1781485962.sh sha-gates the copy, so only a still-stock input.lua is replaced. There is no `omarchy-*` command for setting the layout. `ls /usr/share/omarchy/bin | grep -iE 'keyboard|input|layout|xkb'` returns only RGB-lighting theming, the menu text-input helper and the touchpad enable toggle, so hand-editing input.lua is the supported path and not a workaround. The touchpad half stays: the symptom names it and the root cause is the same, that Hyprland programs libinput itself, but the corrected block now labels which of those lines Omarchy 4 or Hyprland already sets by default so the reader is not told to change settings that are already in force. Cause, symptom, danger, severity and frequency all held and are unchanged. NOT exercised: nothing was written, no reload, eval, keyword or dispatch was run, and no layout was switched, because this is the operator's live graphical session. The per-device `kb_layout` override and `resolve_binds_by_sym` were verified from the wiki and from the option table only, not by applying them here.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting a single non-Latin `kb_layout` (ru, gr, th, ua, ...) with no Latin layout first means keybinds that use Latin keysyms stop firing — including your terminal and launcher binds — leaving a desktop you cannot drive. Always lead with a Latin layout (`kb_layout = "us,ru"`) and add a switch option such as `grp:alts_toggle`, which is exactly what Omarchy does for you at install time.

**Fix.**

**First, see what is actually in effect.** Both separators work on 0.56:

```bash
hyprctl getoption input:kb_layout
hyprctl getoption input:kb_options
hyprctl devices
```

**Set it in the compositor.** Plain Hyprland: `~/.config/hypr/hyprland.lua`. Omarchy 4: `~/.config/hypr/input.lua`, which ships as one fully commented-out `hl.config` block, so nothing in it takes effect until you uncomment it. `~/.config/hypr/hyprland.lua` calls `require("default.hypr.omarchy")` and only then `require("hypr.input")`, so your file is read after Omarchy's defaults and wins.

```lua
hl.config({
  input = {
    kb_layout  = "us,fr",
    kb_variant = ",",                 -- one comma-separated entry per layout, or one for all
    kb_model   = "",

    -- kb_options REPLACES the previous string, it does not merge. Omarchy 4 sets
    -- "compose:caps,shift:both_capslock_cancel" in
    -- /usr/share/omarchy/default/hypr/input.lua, and this line drops both unless you
    -- repeat them. caps:escape and compose:caps both claim Caps Lock, so pick one.
    kb_options = "compose:caps,shift:both_capslock_cancel,grp:alt_shift_toggle",
    kb_rules   = "",

    numlock_by_default = true,
    repeat_rate  = 40,                -- repeats per second, Hyprland default 25
    repeat_delay = 250,               -- ms, Hyprland default 600

    follow_mouse = 1,
    sensitivity  = 0,                 -- -1.0 .. 1.0
    accel_profile = "flat",           -- "adaptive" | "flat" | "custom"

    touchpad = {
      natural_scroll        = true,   -- Hyprland default false, Omarchy 4 also sets false
      disable_while_typing  = true,   -- already the Hyprland default
      clickfinger_behavior  = true,   -- 2-finger = right click, Omarchy 4 already sets this
      tap_to_click          = true,   -- already the Hyprland default
      scroll_factor         = 0.4,    -- Omarchy 4 already sets this
    },
  },
})
```

Valid layout, variant and option names:

```bash
localectl list-x11-keymap-layouts
localectl list-x11-keymap-variants fr
grep -E '^[[:space:]]*(caps|grp|compose):' /usr/share/X11/xkb/rules/evdev.lst
```

**Apply it.** `hyprctl reload` re-runs the whole Lua config, including Omarchy's `/etc/vconsole.conf` read:

```bash
hyprctl reload
```

Try a value before writing it. On 0.56 `hyprctl eval` takes a Lua string, which is how Omarchy's own `omarchy-toggle-input-device` drives the compositor:

```bash
hyprctl eval 'hl.config({ input = { kb_options = "compose:caps,caps:escape" } })'
```

`hyprctl dispatch` also takes Lua on 0.56, so a bare `hyprctl dispatch <dispatcher> <args>` copied from an older guide will fail to parse.

**Per-device settings.** Hyprland lowercases the libinput name and turns spaces into hyphens, so do not guess it. Print the exact strings:

```bash
hyprctl -j devices | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(k["name"]) for k in d["keyboards"]]'
hyprctl -j devices | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(m["name"]) for m in d["mice"]]'
```

Real names from a live Omarchy 4 machine: `corsair-corsair-gaming-k55-rgb-keyboard`, `razer-razer-basilisk-v3`.

```lua
hl.device({
  name = "razer-razer-basilisk-v3",
  sensitivity   = -0.2,
  accel_profile = "flat",
  natural_scroll = false,
})

hl.device({
  name = "corsair-corsair-gaming-k55-rgb-keyboard",
  kb_layout = "us,pl,de",
})
```

Every `input` option and subcategory such as `input.touchpad` works inside `hl.device` except `force_no_accel` and the window-management ones (`follow_mouse`, `follow_mouse_threshold`, `float_switch_override_focus`, `mouse_refocus`, `special_fallthrough`). `enabled`, `keybinds` and `tags` exist only in `hl.device`.

**Switch layouts at runtime:**

```bash
hyprctl switchxkblayout corsair-corsair-gaming-k55-rgb-keyboard next
hyprctl switchxkblayout all next
hyprctl switchxkblayout current 1
```

`current` means the keyboard `hyprctl devices` marks `main: yes`, which is often not a keyboard you type on. With fcitx5 running it is `hl-virtual-keyboard-fcitx5`. Name the physical device, or use `all`.

**Omarchy 4 puts this on the bar for you.** Once `kb_layout` holds more than one entry the `omarchy.keyboard-layout` widget appears next to the clock and a click cycles the layout. It hides itself on a single-layout install, which is why you may never have seen it:

```bash
grep -n 'omarchy.keyboard-layout' ~/.config/omarchy/shell.json
omarchy-bar put omarchy.keyboard-layout --after omarchy.clock    # only if it is missing
```

**Keybinds firing on the wrong layout.** By default binds resolve against the first `kb_layout` entry. Either keep a Latin layout first, which is what Omarchy does automatically, or opt into symbol-based resolution:

```lua
hl.config({ input = { resolve_binds_by_sym = true } })
```

**Omarchy: change the system layout so the default picks it up.** `/usr/share/omarchy/default/hypr/input.lua` reads `XKBLAYOUT` and `XKBVARIANT` from `/etc/vconsole.conf` every time the config loads, so a system-wide change is enough as long as you have not written a local override:

```bash
grep XKB /etc/vconsole.conf                                      # record all four lines first
sudo localectl set-x11-keymap fr pc105 '' terminate:ctrl_alt_bksp
grep XKB /etc/vconsole.conf                                      # check all four, not just the layout
hyprctl reload
```

Pass model, variant and options explicitly. `localectl` sends an empty string for every positional argument you leave off (`src/locale/localectl.c`, `verb_set_x11_keymap`), so a bare `sudo localectl set-x11-keymap fr` also wipes `XKBMODEL` and `XKBOPTIONS`. Omarchy's Hyprland config ignores `XKBOPTIONS`, but the virtual console and Xwayland do not.

**Will `omarchy update` overwrite your edit?** Only while the file is still stock. `/usr/share/omarchy/migrations/1781485962.sh` takes a sha256 of `~/.config/hypr/input.lua` with the `kb_layout` and `kb_variant` lines stripped out, and copies the packaged template over it only on a match. Once you have uncommented anything the file is yours and no migration replaces it.

**Verify.** `hyprctl getoption input:kb_layout` and `hyprctl getoption input:kb_options` return exactly what you set, including the Omarchy options you meant to keep. `hyprctl devices` shows each keyboard with the expected `rules:` line and `active keymap`, and a per-device override shows only on that device. After a `localectl` change, `grep XKB /etc/vconsole.conf` still shows `XKBMODEL` and `XKBOPTIONS`, not just `XKBLAYOUT`. With two or more layouts, the `omarchy.keyboard-layout` widget appears on the bar and its label changes when you switch. Typing in a terminal produces the right characters, Caps Lock behaves as configured, and your Super keybinds still fire.

Sources: <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Devices/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://wiki.archlinux.org/title/Xorg/Keyboard_configuration> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/using-hyprctl.md> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/input.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/input.lua> · <https://github.com/omacom/omarchy/blob/quattro/migrations/1781485962.sh> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/bar/widgets/KeyboardLayout.qml> · <https://github.com/systemd/systemd/blob/main/src/locale/localectl.c>

---

## hl.monitor() does nothing: wrong connector name, or a mode the driver never advertised

`monitor-config-ignored-name-or-mode` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** "My monitor config is just ignored." `hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@144", position = "0x0", scale = 1 })` sits in monitors.lua, the file saves, no error appears in `hyprctl configerrors` — and the display still runs at 60 Hz, or at 1366x768, or the external screen never lights up at all. Sometimes instead you get an on-screen warning about overlapping monitors, or "Invalid scale passed to monitor".

**Cause.** Four separate failures all present as "the rule did nothing", and only one of them ever produces a config error.

(1) The `output` string does not match a real connector. Names are assigned by the kernel and shift between boots, docks and GPUs, so a monitor on `HDMI-A-2` will never be touched by a rule for `HDMI-A-1`, and a rule naming an output that does not exist is silently inert.

(2) The `mode` is not one the driver reports, and Hyprland does not simply give up. On 0.56.2 it sorts the driver's mode list by closeness to what you asked for, keeps the best three, and if none of them is within one pixel and one Hz of the request it also pushes your exact numbers as a custom DRM mode. The first candidate that passes the atomic modeset test wins. Asking for `2560x1440@140` on a panel that only offers 144 and 120 therefore lands you on 144 or 120, with nothing in `hyprctl configerrors`, which reads as "my line was ignored". Only if every candidate fails does Hyprland fall through to any mode that works and raise a red on-screen notification for five seconds. As the maintainer put it: "if the mode is not listed in hyprctl monitors there's nothing hyprland can do. Custom modelines might or might not work. It's all down to the driver."

(3) The `scale` does not divide the resolution into whole logical pixels. 1920x1080 / 1.5 = 1280x720 is fine, 1920x1080 / 1.4 = 1371.43x771.43 is not. Hyprland does not refuse the value. It searches up to 90 steps of 1/120 either side for the nearest scale that divides cleanly, applies that one instead, and shows a notification naming both the value you wrote and the value it used. Only when no clean divisor exists in that window does it log `Invalid scale passed to monitor, <n> failed to find a clean divisor` and revert the output to its default scale. Either way you end up on a scale you did not ask for.

(4) The panel was powered off when Hyprland started. A sleeping display answers with a partial EDID carrying no video modes at all, so Hyprland brings the output up at 0x0 and the screen stays black while the output is still listed as enabled. Nothing fires an event for this state. Omarchy ships `omarchy-hyprland-monitor-modeless` to detect it.

Plain `hyprctl monitors` also hides disabled outputs and mirrors, so the connector you need may not appear in the list you are reading.

> **Audit corrected this record.** Re-checked on this workstation (omarchy 4.0.2-1, hyprland 0.56.2-1, kernel 7.1.9-arch1-2) against the current Hyprland wiki markdown and against Hyprland's own source at tag v0.56.2, and found three claims that are stale or wrong plus one failure mode missing.

The Lua shape is correct and needed no change: every snippet already uses `hl.monitor()` with the `output` key, which matches `/usr/share/omarchy/config/hypr/monitors.lua` and the live `~/.config/hypr/monitors.lua` on this machine, and matches the field table in `content/configuring/core/monitors/_index.md`. `hyprctl eval` as the live-test path is confirmed by `hyprctl --help` here and by the wiki's using-hyprctl page. The scaled-position rule, the inverted Y axis, the no-overlap rule, transform 0 to 7, `mirror`, `disabled`, the four mode keywords and the empty-output fallback all still hold. All three Omarchy binaries exist at `/usr/share/omarchy/bin/` and `default/hypr/bindings/utilities.lua` line 32 and 33 bind exactly `SUPER + CTRL + Delete` and `SUPER + CTRL + ALT + Delete` as the record says.

What was wrong. First, the record said an unavailable mode is "rejected and the monitor falls back to preferred". `src/output/Monitor.cpp` at v0.56.2 does the opposite: lines 818 to 849 sort the driver's modes by closeness to the request and keep the best three, then push the exact requested numbers as a custom mode, and lines 878 to 965 take the first candidate that passes the atomic test. Only when all of them fail does it use any working mode and raise a five-second red notification. The practical result is the nearest available mode, which is what the reader is actually looking at. Second, the instruction to "DROP the trailing (DP-2) portname" from a `desc:` string is stale. `Monitor.cpp` line 254 and 255 build the short description as make, model and serial and the comment says it "excludes the parenthesized DRM node name suffix", and `matchesStaticSelector` at line 1201 prefix-matches the selector against both forms. Confirmed live: `hyprctl monitors all` here prints `description: Microstep MSI G274QPF CC2H634102253` with no port name to remove, so the old instruction sends the reader looking for text that is not there. Third, the record said an invalid scale is refused with a warning. `Monitor.cpp` lines 997 to 1050 search plus or minus 90 steps of 1/120 for the nearest scale giving whole logical pixels and apply that instead, notifying with both numbers, and only log `Invalid scale passed to monitor, <n> failed to find a clean divisor` when the search fails. Omarchy's own `omarchy-hyprland-monitor-scaling` implements the same 1/120 gcd rounding, which corroborates it.

Added a fourth cause the record missed and Omarchy documents: a display powered off at boot returns a partial EDID with no modes, the output comes up at 0x0 and the screen stays black. `/usr/share/omarchy/bin/omarchy-hyprland-monitor-modeless` exists solely to detect that state and its header comment says so.

Also corrected the danger. `omarchy-hw-recover-internal-monitor` was presented as the recovery for a self-inflicted `disabled = true`. Reading `/usr/bin/omarchy-hw-recover-internal-monitor` shows it only removes `~/.local/state/omarchy/toggles/hypr/internal-monitor-disable.lua` when no external monitor is attached, so it cannot undo a hand-written rule. Corrected the verify for the same reason the cause was wrong: `hyprctl configerrors` stays empty for both the mode fallback and the scale correction, so it is not the check to rely on, and it now uses `monitors all` so a mirrored or disabled output is visible.

Not exercised. Nothing was written and no mode or scale was changed, because this is the operator's daily workstation driving a real panel. The fallback and notification paths were read from the v0.56.2 source rather than triggered, and the invalid-scale path was not run. The `desc:` selector was not tested against a live rule, only read from `matchesStaticSelector`. `misc:disable_autoreload` reads `bool: false, set: false` here, so auto-reload is on by default, but a save-triggered reload was not observed.

Swapped the four `basecamp/omarchy` blob URLs for `omacom/omarchy`, the current name. The old ones still redirect, but every path was re-fetched against `omacom/omarchy@quattro` for this audit and that is the name the search API resolves.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `disabled = true` does not just blank the screen. It removes the output from the layout and migrates all of its windows and workspaces onto the remaining monitors. Disabling your only display leaves you with no way back except Ctrl+Alt+F2 to a TTY, then:

```bash
hyprctl -i 0 eval 'hl.monitor({ output = "eDP-1", disabled = false })'
```

or edit `monitors.lua` and reboot. Use the `dpms` dispatcher if you only want the panel powered off. On Omarchy, `omarchy-hw-recover-internal-monitor` recovers only from Omarchy's own `omarchy-hyprland-monitor-internal toggle`: it deletes `~/.local/state/omarchy/toggles/hypr/internal-monitor-disable.lua` when no external monitor is connected. It does nothing about a `disabled = true` you wrote into `monitors.lua` yourself.

**Fix.**

First, get the truth from the compositor. `all` is load-bearing, because plain `hyprctl monitors` omits disabled and mirrored outputs:

```bash
hyprctl monitors all          # every output, plus every mode the driver actually offers
hyprctl -j monitors all | jq  # same thing, easier to grep
```

If an output is listed, `disabled: false`, and reports a size of 0x0, the panel was asleep at boot and handed the kernel an EDID with no modes. Wake it and replug the cable. On Omarchy there is a check for exactly this:

```bash
omarchy-hyprland-monitor-modeless   # exit 0 = an enabled monitor has no mode
```

Otherwise copy the connector name and one of the listed `availableModes` entries verbatim into `~/.config/hypr/monitors.lua` (Omarchy) or `~/.config/hypr/hyprland.lua` (plain Hyprland):

```lua
-- Exact name, and a mode that appears in `hyprctl monitors all`
hl.monitor({ output = "DP-2", mode = "2560x1440@143.97", position = "0x0", scale = 1 })

-- Connector names shuffle between docks and boots. Match the EDID description
-- instead. Copy the `description:` line from `hyprctl monitors` exactly as it
-- is printed: on 0.56 that line is already the make, model and serial with no
-- port name appended, so there is nothing to strip. Matching is a prefix test,
-- so a shortened description still selects the monitor.
hl.monitor({ output = "desc:Dell Inc. DELL U2720Q 8FGZ043", mode = "highrr", position = "auto", scale = 1 })

-- Stop guessing modes. preferred = EDID preferred, highres = highest resolution,
-- highrr = highest refresh rate, maxwidth = widest mode. They cannot be combined.
-- An empty output is the catch-all fallback. Keep it LAST in the file.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

-- Rotated panel: 0 normal, 1 = 90 deg, 2 = 180, 3 = 270, 4-7 = flipped variants
hl.monitor({ output = "DP-3", mode = "preferred", position = "auto", scale = 1, transform = 1 })

-- Mirror the laptop panel onto an external (mirrors do NOT show in plain `hyprctl monitors`)
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "0x0", scale = 1, mirror = "eDP-1" })

-- Remove an output from the layout entirely
hl.monitor({ output = "eDP-1", disabled = true })
```

Try a rule live before committing it to a file. Under a Lua config this is `eval`, not `keyword`:

```bash
hyprctl eval 'hl.monitor({ output = "DP-2", mode = "2560x1440@143.97", position = "0x0", scale = 1 })'
```

Positions are in **scaled** pixels: a 3840-wide monitor at scale 2 occupies 1920 logical px, so the next monitor starts at `1920x0`, not `3840x0`. Y is inverted, so negative y is up. No two monitors may overlap, and an overlapping pair is refused with a warning rather than registered.

Hyprland watches the config file and reloads it when you save, unless `misc:disable_autoreload` is set, so a `monitors.lua` edit applies with no logout. Force it with `hyprctl reload` if you want to be sure.

On Omarchy 4 use the shipped tooling instead of hand-editing where one exists:

```bash
omarchy-hyprland-monitor-scaling 1.6      # rounds to the nearest scale that divides cleanly,
                                          # applies it, and writes both the monitor scale and
                                          # GDK_SCALE back into ~/.config/hypr/monitors.lua
omarchy-hyprland-monitor-internal-mirror toggle   # SUPER + CTRL + ALT + Delete
omarchy-hyprland-monitor-internal toggle          # SUPER + CTRL + Delete
```

`omarchy-hyprland-monitor-scaling` only rewrites the file while it still carries Omarchy's generic catch-all shape. Once you have replaced that with per-output rules it changes the live scale and leaves the file alone, so the setting is lost on the next reload.

**Verify.** ```bash
hyprctl -j monitors all | jq -r '.[] | "\(.name) \(.width)x\(.height)@\(.refreshRate) scale=\(.scale) disabled=\(.disabled)"'
```

reports the connector, resolution, refresh rate and scale you asked for. Use `all`, because a mirrored or disabled output is absent from the plain list. Do not use `hyprctl configerrors` as the test here: a mode that could not be set and a scale that was silently corrected both leave it empty, and both announce themselves as a red on-screen notification instead. If the numbers come back different from what you wrote, that is the closest-mode or nearest-clean-scale fallback doing its job, not a typo in your file.

Sources: <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://bbs.archlinux.org/viewtopic.php?id=301057> · <https://github.com/hyprwm/Hyprland/discussions/12064> · <https://wiki.hypr.land/configuring/core/monitors/> · <https://wiki.hypr.land/configuring/core/monitors/modes/> · <https://wiki.hypr.land/configuring/core/monitors/output-selection/> · <https://wiki.hypr.land/configuring/core/monitors/positioning/> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/output/Monitor.cpp> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/monitors.lua> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-scaling> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-internal> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-internal-mirror> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-modeless> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hw-recover-internal-monitor> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/bindings/utilities.lua>

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

**Symptom.** A variable set with `hl.env("FOO", "bar")` is visible in a terminal you launched from a keybind, but `systemctl --user show-environment` does not list it. Downstream: the theme or cursor is right in apps you launch by hotkey and wrong in anything started by a `.service` or by `.desktop` D-Bus activation, a `--user` service you wrote cannot find the variable, `flatpak run` apps ignore your env, and portal-launched helpers behave as though the variable does not exist.

On a stock Omarchy 4 you will usually not see this at all, because Omarchy's own autostart imports the entire session environment into the systemd user manager. Omarchy users hit the narrower cases instead: a variable set after `hyprland.start` has already run, a user manager started by ssh or by lingering, or a unit that was already running when the variable appeared.

**Cause.** `hl.env("FOO", "bar")` calls `setenv()` inside the compositor's own process, so the variable is inherited only by processes Hyprland forks after that line runs. Confirmed in Hyprland 0.56.2 in `src/config/lua/bindings/LuaBindingsConfigRules.cpp`, where the binding body is a plain `setenv(name.c_str(), value.c_str(), 1)`.

Separately, Hyprland pushes a fixed seven-name allowlist into the systemd user manager and the D-Bus activation environment. From `src/Compositor.cpp` at tag `v0.56.2`, in `CCompositor::startCompositor()`:

```
systemctl --user import-environment DISPLAY WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP QT_QPA_PLATFORMTHEME PATH XDG_DATA_DIRS
dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE QT_QPA_PLATFORMTHEME PATH XDG_DATA_DIRS
```

It runs only when the backend has a session and `HYPRLAND_NO_SD_VARS` is unset. Anything outside that list is invisible to user units and to D-Bus-activated apps, and anything already running when Hyprland starts never sees it.

Two things change that picture on Hyprland 0.56 and on Omarchy 4.

1. `hl.env()` takes a third boolean argument that does the push for you. With `hl.env("XCURSOR_THEME", "Bibata-Modern-Classic", true)` Hyprland runs `systemctl --user import-environment 'XCURSOR_THEME'` followed by `dbus-update-activation-environment --systemd 'XCURSOR_THEME'` for that single name. Same file, same version.

2. Omarchy 4 already imports the whole session environment. `/usr/share/omarchy/default/hypr/autostart.lua` runs this on `hyprland.start`, before it launches the shell and the session services:

```lua
hl.exec_cmd("systemctl --user import-environment $(env | cut -d'=' -f 1)")
hl.exec_cmd("dbus-update-activation-environment --systemd --all")
```

Measured on this workstation (omarchy 4.0.2-1, hyprland 0.56.2-1): `systemctl --user show-environment` carries `GDK_BACKEND`, `OZONE_PLATFORM`, `ELECTRON_OZONE_PLATFORM_HINT`, `XCURSOR_SIZE`, `HYPRCURSOR_SIZE`, `XCOMPOSEFILE`, `OMARCHY_PATH`, `QT_QPA_PLATFORM`, `XDG_SESSION_DESKTOP` and `XDG_MENU_PREFIX`. Not one of those is in Hyprland's allowlist, and every one of them is set by `hl.env()` in `/usr/share/omarchy/default/hypr/envs.lua`.

So on Omarchy 4 the remaining failure cases are narrower: a variable that first appears after that import has already run, a systemd user manager started by ssh or by lingering rather than by the graphical session (it never saw the session environment at all), and units that were already running when the variable arrived.

> **Audit corrected this record.** Checked against Hyprland source at tag v0.56.2 and against this workstation (omarchy 4.0.2-1, hyprland 0.56.2-1, uwsm 0.26.7-1). The seven-name allowlist claim is exact: `src/Compositor.cpp` at v0.56.2 contains `systemctl --user import-environment DISPLAY WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP QT_QPA_PLATFORMTHEME PATH XDG_DATA_DIRS` and the six-name `dbus-update-activation-environment --systemd ...` line, guarded by `m_aqBackend->hasSession()` and `HYPRLAND_NO_SD_VARS`. Two defects, both Omarchy-4 specialisation failures of exactly the kind this re-audit looks for. First, `hl.env()` takes a third boolean argument on 0.56.2 that makes Hyprland run `systemctl --user import-environment '<name>'` and `dbus-update-activation-environment --systemd '<name>'` itself, confirmed in `src/config/lua/bindings/LuaBindingsConfigRules.cpp` at v0.56.2, and the record never mentions it while recommending the manual commands. Second, and worse, the symptom is usually absent on a stock Omarchy 4 because `/usr/share/omarchy/default/hypr/autostart.lua` already runs `systemctl --user import-environment $(env | cut -d'=' -f 1)` and `dbus-update-activation-environment --systemd --all` on `hyprland.start`. Confirmed on this machine: `systemctl --user show-environment` carries GDK_BACKEND, OZONE_PLATFORM, ELECTRON_OZONE_PLATFORM_HINT, XCURSOR_SIZE, HYPRCURSOR_SIZE, XCOMPOSEFILE, OMARCHY_PATH, QT_QPA_PLATFORM, XDG_SESSION_DESKTOP and XDG_MENU_PREFIX, all set by `hl.env()` in `/usr/share/omarchy/default/hypr/envs.lua` and none of them in Hyprland's allowlist. That makes the record's step C actively wrong advice on Omarchy, since it tells the reader to add to `~/.config/hypr/autostart.lua` a command Omarchy already runs. Step D was also stale: the current wiki page `content/configuring/core/environment-variables.md` is 68 lines and contains no uwsm guidance at all, and Omarchy's own `/usr/share/uwsm/env.d/10-omarchy` names `~/.config/uwsm/env.d/*` as the preferred override point, not `~/.config/uwsm/env`. The uwsm file names themselves still hold: uwsm 0.26.7's README line 112 lists `uwsm/env`, `uwsm/env.d/*`, `uwsm/env-${desktop}` and `uwsm/env-${desktop}.d/*`, and `${desktop}` is `hyprland` because `/usr/share/wayland-sessions/hyprland-uwsm.desktop` runs `uwsm start -e -D Hyprland hyprland.desktop`. The `environment.d` mechanism and the `/etc/environment` danger both held: the wiki carries that warning verbatim, and `~/.config/environment.d/omarchy-firefox-wayland.conf` on this machine puts MOZ_ENABLE_WAYLAND into the user manager. I did NOT exercise anything: per the job's safety constraint I ran no `systemctl --user import-environment`, no `dbus-update-activation-environment`, started or restarted no unit, and wrote no config, so the corrected fix's write steps are read from source and from Omarchy's own shipped files rather than executed. I also did not test a lingering or ssh-started user manager.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not put Wayland-specific variables in /etc/environment. That file is read by every session on the machine, including Xorg ones and display managers, and setting things like GDK_BACKEND=wayland there will break logins into non-Wayland sessions.

**Fix.**

Pick the mechanism that matches who needs the variable.

**A. Anything Hyprland launches (keybinds, autostart, exec rules).** `hl.env()` is correct and sufficient:

```lua
hl.env("GTK_THEME", "Adwaita:dark")
-- reference an existing variable with os.getenv, not shell $ syntax:
hl.env("SSH_AUTH_SOCK", os.getenv("XDG_RUNTIME_DIR") .. "/ssh-agent.socket")
```

**B. One variable that also has to reach systemd and D-Bus: use the third argument.** Hyprland 0.56 accepts a boolean third argument on `hl.env()` and does the push itself:

```lua
hl.env("XCURSOR_THEME", "Bibata-Modern-Classic", true)
```

That runs `systemctl --user import-environment 'XCURSOR_THEME'` and `dbus-update-activation-environment --systemd 'XCURSOR_THEME'`. Prefer this over calling either command by hand. Like every push, it affects units started after it runs, not units already running.

**C. systemd --user services and D-Bus-activated apps, durable across everything: `environment.d`.** The user manager parses these at start, so they apply even to a manager that never saw a graphical session:

```bash
mkdir -p ~/.config/environment.d
cat > ~/.config/environment.d/10-wayland.conf <<'EOF'
XCURSOR_THEME=Bibata-Modern-Classic
XCURSOR_SIZE=24
ELECTRON_OZONE_PLATFORM_HINT=auto
MOZ_ENABLE_WAYLAND=1
EOF
```

Log out and back in. The user manager only re-reads these on start, so `systemctl --user daemon-reload` will not pick them up. Confirmed on this machine: `~/.config/environment.d/omarchy-firefox-wayland.conf` contains `MOZ_ENABLE_WAYLAND=1` and that variable is in `systemctl --user show-environment`.

**D. On Omarchy 4, check before you fix anything.** Omarchy's `/usr/share/omarchy/default/hypr/autostart.lua` already imports the whole environment into the user manager on `hyprland.start`, so the variable is very likely there already:

```bash
systemctl --user show-environment | grep XCURSOR_THEME
```

If it is there, you have no problem to fix. If you want to change an Omarchy session default, the supported override point is a uwsm drop-in, which `/usr/share/uwsm/env.d/10-omarchy` names in its own comments:

```sh
mkdir -p ~/.config/uwsm/env.d
cat > ~/.config/uwsm/env.d/50-mine <<'EOF'
export XCURSOR_THEME=Bibata-Modern-Classic
EOF
```

Log out and back in. Verified by the same route on omarchy 4.0.2-1: `TERMINAL=xdg-terminal-exec` and `EDITOR=omarchy-launch-editor --inline` are set only by `/usr/share/omarchy/default/uwsm/default`, which `/usr/share/uwsm/env.d/10-omarchy` sources, and both appear in `systemctl --user show-environment`.

**E. uwsm sessions generally.** uwsm 0.26.7 sources `uwsm/env`, `uwsm/env.d/*`, `uwsm/env-${desktop}` and `uwsm/env-${desktop}.d/*` from each config directory, one `export KEY=VAL` per line. On Omarchy the session entry is `uwsm start -e -D Hyprland hyprland.desktop`, so `${desktop}` is `hyprland` and `~/.config/uwsm/env-hyprland` is the per-compositor file. Use it for `HYPR*` and `AQ_*`:

```sh
# ~/.config/uwsm/env-hyprland
export AQ_DRM_DEVICES="/dev/dri/amd-igpu:/dev/dri/card1"
```

The wiki advice to keep env vars out of `hyprland.lua` entirely under uwsm does not match what Omarchy ships. Omarchy sets about fifteen variables with `hl.env()` in `/usr/share/omarchy/default/hypr/envs.lua`. Treat the uwsm files as the place for your overrides, not as a rule that `hl.env()` is wrong.

**F. Push what is already in the session, right now.** Useful for a one-off, or for a portal that came up before your variables existed:

```bash
dbus-update-activation-environment --systemd --all
systemctl --user import-environment QT_QPA_PLATFORMTHEME XCURSOR_THEME XCURSOR_SIZE
```

On plain Hyprland, run it from your autostart so it happens every session. Hyprland's documented hook is the start event, not a bare top-level dispatch, which would re-run on every config reload:

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("dbus-update-activation-environment --systemd --all")
end)
```

Do not add this on Omarchy 4. `/usr/share/omarchy/default/hypr/autostart.lua` already runs both commands, and your `~/.config/hypr/autostart.lua` is loaded in addition to it, so you would only be running them twice.

This affects units started after it runs, not units already running. Restart the affected service.

If you use dbus-broker rather than the reference dbus daemon, `dbus-update-activation-environment` is redundant, because dbus-broker already reuses systemd's activation environment.

**Verify.** `systemctl --user show-environment | grep XCURSOR_THEME` prints your value, and `systemctl --user restart <yourservice>` then `systemctl --user show <yourservice> -p Environment` shows it reaching the unit.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/> · <https://raw.githubusercontent.com/hyprwm/Hyprland/main/src/Compositor.cpp> · <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.archlinux.org/title/Systemd/User> · <https://wiki.archlinux.org/title/Hyprland> · <https://wiki.hypr.land/configuring/core/environment-variables/> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/Compositor.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsConfigRules.cpp> · <https://github.com/Vladimir-csp/uwsm/blob/master/README.md>

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

**Cause.** Two distinct failures.

**(1) The picker never returned a selection.** XDPH shells out to whatever `screencopy:custom_picker_binary` names in `~/.config/hypr/xdph.conf`, and when the spawned process fails, exits without printing a `[SELECTION]` marker, or is cancelled by the user, XDPH keeps the default-constructed selection and tears the session down. `selection -1` is literally `SSelectionData.type` cast to int, and `TYPE_INVALID = -1` in `src/shared/ScreencopyShared.hpp`. The log line is `Debug::log(LOG, "[screencopy] SHAREDATA returned selection {}", (int)SHAREDATA.type)` in `src/portals/Screencopy.cpp`.

Omarchy 4 ships `custom_picker_binary = hyprland-preview-share-picker` in `/usr/share/omarchy/config/hypr/xdph.conf`, copied to `~/.config/hypr/xdph.conf` on install. When that package is missing or broken, every screen share fails this way. That is exactly what bit Omarchy 3.2.3 (omacom/omarchy issue 3989, whose logs match this record line for line).

Note which picker you are debugging, because the two are different toolkits:

- `hyprland-preview-share-picker` is GTK4 plus gtk4-layer-shell. Omarchy's default.
- `/usr/bin/hyprland-share-picker` ships inside `xdg-desktop-portal-hyprland` itself and is Qt6 (`libQt6Widgets`, `libQt6Gui`, `libQt6Core`, `libQt6DBus`). This is the one that needs `qt6-wayland`. XDPH only raises the "qt5-wayland or qt6-wayland doesn't seem to be installed" notification when the picker's output contains `qt.qpa.plugin: Could not find the Qt platform plugin`, so that diagnosis does not apply to the GTK picker.

Neither picker is drawn by Quickshell. `omarchy-shell` draws the bar and the lock screen, not the share picker.

**(2) Black capture** is usually XWayland. An app running under XWayland can only see other XWayland windows, so it cannot capture a Wayland window or a whole screen. A `bitdepth` on the monitor that does not match the panel also breaks capture, and 10-bit output in particular stops some apps capturing at all.

> **Audit corrected this record.** Checked against xdg-desktop-portal-hyprland source on `master`, the Hyprland wiki repo, omacom/omarchy issue 3989 read in full, and this workstation (omarchy 4.0.2-1, xdg-desktop-portal-hyprland 1.4.1-1, xdg-desktop-portal 1.22.1-2, hyprland-preview-share-picker 0.2.1-1). The load-bearing mechanism is exact and I confirmed it in source rather than assuming: `selection -1` is `SSelectionData.type` printed as an int by `Debug::log(LOG, "[screencopy] SHAREDATA returned selection {}", (int)SHAREDATA.type)` in `src/portals/Screencopy.cpp`, and `TYPE_INVALID = -1` in `src/shared/ScreencopyShared.hpp`. The config file path `~/.config/hypr/xdph.conf` is built in `CPortalManager::CPortalManager()` in `src/core/PortalManager.cpp`, and the four option names and defaults are registered there as `screencopy:max_fps` 120, `screencopy:allow_token_by_default` 0, `screencopy:custom_picker_binary` empty string, `screencopy:force_shm` 0, with `promptForScreencopySelection()` substituting `hyprland-share-picker` when the string is empty, so the record's fallback advice is right. Issue 3989 supports the claim in full, including the exact two log lines and the exact working config, and the `bitdepth` and XWayland claims are still on the wiki verbatim (`content/configuring/core/monitors/colors.md` says "Some applications do not support screen capture with 10 bit enabled", `content/useful-utilities/screen-sharing.md` carries the XWayland explanation and the bitdepth-must-match line). Three defects. First, the qt6-wayland diagnosis is mis-attached: Omarchy's configured picker `hyprland-preview-share-picker` is GTK4 and gtk4-layer-shell (confirmed by `pacman -Qi` depends and by `ldd /usr/bin/hyprland-preview-share-picker`, which links `libgtk-4.so.1` and `libgtk4-layer-shell.so.0` and no Qt at all), while the Qt6 dependency belongs to the stock `/usr/bin/hyprland-share-picker` shipped by xdg-desktop-portal-hyprland (`ldd` shows libQt6Widgets, libQt6Gui, libQt6Core, libQt6DBus), and XDPH only emits that notification on the specific string `qt.qpa.plugin: Could not find the Qt platform plugin`. Second, `sudo pacman -S --needed hyprland-preview-share-picker` only works on Omarchy, where it comes from the `[omarchy]` repo in `/etc/pacman.conf` and is listed in `/usr/share/omarchy/install/omarchy-base.packages`. The archlinux.org package search returns zero results for that name and the AUR RPC returns only `hyprland-preview-share-picker-git`, so the command fails on the arch, endeavouros, cachyos and manjaro targets this record claims. The supported Omarchy wrapper is `omarchy-pkg-add`, and the ALPM guard `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` does not block a plain `-S` because it triggers only on `Operation = Upgrade` and `/usr/bin/omarchy-update-pacman-guard` only aborts when both sync and sysupgrade are present. Third, the fix's `ELECTRON_OZONE_PLATFORM_HINT` advice ignores that Omarchy already sets it to `wayland` (not `auto`) in `/usr/share/omarchy/default/hypr/envs.lua`, along with `MOZ_ENABLE_WAYLAND`. Corrections applied, plus the Omarchy-specific picker config at `~/.config/hyprland-preview-share-picker/config.yaml` with its `debug` flag and theme stylesheet path, both read on this machine. Both portal units exist and are running here (`xdg-desktop-portal.service` and `xdg-desktop-portal-hyprland.service`, active for 6 days, both `static` and D-Bus activated). I did NOT exercise a screen share, restart either portal unit, or install or remove anything, per the job's safety constraint on the operator's daily workstation, so the recovery path is verified from source and from the shipped files rather than by reproducing the failure. Severity and frequency left alone: the failure is total for screen sharing but loses no data, and the black-capture half of the record stays common even though the Omarchy 3.2.3 picker regression itself is historical. The cited basecamp issue URL now returns a hard 404 to an ordinary fetch (only the `gh` API follows the rename), so it is replaced with the omacom URL.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `allow_token_by_default = true` pre-ticks "Allow restore token", which lets an app silently resume capturing the same screen on later requests without showing you the picker. Convenient for Meet, but it means an app you shared with once can start capturing again without a prompt. Set it to false if that matters to you.

**Fix.**

**Confirm the whole stack is installed and running:**

```bash
pacman -Q pipewire wireplumber xdg-desktop-portal xdg-desktop-portal-hyprland xdg-desktop-portal-gtk qt6-wayland
systemctl --user status xdg-desktop-portal xdg-desktop-portal-hyprland
```

Both units are `static` and D-Bus activated, so they will not show `enabled`. `active (running)` is what you want. A crash in the status output, when you are using the stock Qt picker, usually means `qt6-wayland` (or `qt5-wayland`) is missing.

**Fix a picker that returns -1.** First check the binary is actually there and runnable:

```bash
command -v hyprland-preview-share-picker
```

On Omarchy 4 the package comes from the `[omarchy]` pacman repo (it is listed in `/usr/share/omarchy/install/omarchy-base.packages`), so reinstall it with Omarchy's own wrapper:

```bash
omarchy-pkg-add hyprland-preview-share-picker
```

On plain Arch, EndeavourOS, CachyOS or Manjaro that package name does not exist. It is in neither the official repositories nor the AUR. The AUR carries only `hyprland-preview-share-picker-git`. Do not run `pacman -S hyprland-preview-share-picker` there, it will just fail to resolve.

Whatever the distro, the reliable recovery is to fall back to the picker that ships with XDPH itself:

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

`custom_picker_binary` defaults to the empty string and XDPH substitutes `hyprland-share-picker` when it is empty, so deleting the line entirely has the same effect and is the safest thing to do while debugging.

**If the preview picker is the one failing, turn its own logging on.** It reads `~/.config/hyprland-preview-share-picker/config.yaml`, and Omarchy's copy sets `debug: false` and points `stylesheets` at `~/.local/state/omarchy/current/theme/hyprland-preview-share-picker.css`. Set `debug: true` there and check that the stylesheet path resolves, since a theme switch that left the CSS missing is a plausible way for the picker to die on launch:

```bash
ls -l ~/.local/state/omarchy/current/theme/hyprland-preview-share-picker.css
```

**Fix black capture:**

```bash
# Is the app on XWayland? If `xwayland: 1`, that is your answer.
hyprctl clients | grep -B8 -A2 'xwayland: 1'
```

Run the app natively on Wayland instead. Omarchy 4 already sets both of these in `/usr/share/omarchy/default/hypr/envs.lua`, so check before adding them:

```lua
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "wayland")  -- Discord/Vesktop, Slack, VSCodium
hl.env("MOZ_ENABLE_WAYLAND", "1")                  -- Firefox
```

or per-app: `--enable-features=UseOzonePlatform --ozone-platform=wayland`.

Make sure the `bitdepth` in your monitor rule matches the panel. Drop `bitdepth = 10` while debugging, since some apps cannot screen-capture with 10-bit enabled. On Omarchy 4 that is Lua:

```lua
hl.monitor({ output = "DP-1", bitdepth = 10 })
```

On a multi-GPU box where DMA-BUF allocation fails, force the slower but reliable path:

```ini
screencopy {
    force_shm = true
}
```

**Portal not autostarting and producing no logs at all** almost always means the XDG environment is wrong:

```bash
systemctl --user show-environment | grep -E 'XDG_CURRENT_DESKTOP|WAYLAND_DISPLAY'
```

On Omarchy 4 both are normally present, because `/usr/share/omarchy/default/hypr/autostart.lua` imports the whole session environment on `hyprland.start`. If they are missing, you are almost certainly looking at a user manager that was started by ssh or by lingering rather than by the graphical session.

**Verify.** `journalctl --user -u xdg-desktop-portal-hyprland -f` while starting a share shows a picker session created and no `selection -1`; the picker window appears; the receiving end sees live video rather than black.

Sources: <https://wiki.hypr.land/Hypr-Ecosystem/xdg-desktop-portal-hyprland/> · <https://wiki.hypr.land/Useful-Utilities/Screen-Sharing/> · <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://wiki.hypr.land/Nvidia/> · <https://github.com/omacom/omarchy/issues/3989> · <https://github.com/hyprwm/xdg-desktop-portal-hyprland/blob/master/src/shared/ScreencopyShared.cpp> · <https://github.com/hyprwm/xdg-desktop-portal-hyprland/blob/master/src/shared/ScreencopyShared.hpp> · <https://github.com/hyprwm/xdg-desktop-portal-hyprland/blob/master/src/portals/Screencopy.cpp> · <https://github.com/hyprwm/xdg-desktop-portal-hyprland/blob/master/src/core/PortalManager.cpp> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/xdph.conf> · <https://wiki.hypr.land/configuring/core/monitors/colors/> · <https://wiki.hypr.land/useful-utilities/screen-sharing/> · <https://github.com/WhySoBad/hyprland-preview-share-picker>

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

## Stop the screensaver and lock firing over a fullscreen Steam game

`steam-game-fullscreen-not-inhibiting-idle` · severity: **medium** · frequency: **occasional** · applies to: `desktop`, `gamescope`, `hyprland`, `omarchy`, `steam`, `wayland`

**Symptom.** A fullscreen Steam or Proton game played with a controller gets the Omarchy screensaver drawn over it after the idle timeout, and the lock screen follows. Mouse and keyboard activity prevent it, controller input does not. `hyprctl clients -j` shows the game with `inhibitingIdle: false`:

```json
{
  "class": "steam_app_244210",
  "title": "Assetto Corsa",
  "fullscreen": 2,
  "xwayland": true,
  "inhibitingIdle": false
}
```

Four people report the symptom on issue 6947. Three of them name a controller, a Sony DualSense, a GameSir Cyclone 2 and a Steam Controller, and the fourth only says controller. Three give Omarchy 4.0.0-1 and two of those give Hyprland 0.56.2.

**Cause.** Omarchy's default Steam rule in `default/hypr/apps/steam.lua` is:

```lua
o.window("steam", { float = true, idle_inhibit = "fullscreen" })
```

`o.window` with a string assigns that string to `rules.match.class` and hands the table to `hl.window_rule`, which is what `/usr/share/omarchy/default/hypr/helpers.lua` does, and Hyprland 0.56.2 matches a class against the whole string. The rule therefore covers the Steam client, whose class is `steam`, and not the games, whose XWayland class is `steam_app_<appid>`. Games started through gamescope expose the class `gamescope` and miss the rule the same way. A controller does not reset the compositor idle timer on its own, so with no inhibitor the idle timeout runs during play.

The inhibitor is what Omarchy's idle handling watches. `/usr/share/omarchy/shell/plugins/services/idle/Service.qml` drives a Quickshell `IdleMonitor` with `respectInhibitors: true`, default `idle.screensaver` 150 seconds and `idle.lock` 300 seconds, so a Hyprland window inhibitor stops both the screensaver and the lock, and a window without one gets both.

Still the shipped default on `quattro`, on tag `v4.0.3` of 2026-09-08, and on omarchy 4.0.2-1:

```bash
grep -n idle_inhibit /usr/share/omarchy/default/hypr/apps/steam.lua
```

Issue 6947 is open. Two pull requests add `o.window("steam_app_.*", { idle_inhibit = "fullscreen" })` to that file, 9651 and 9667, and both were still open on 2026-09-11. Neither covers the `gamescope` class, so the fix below is wider than either.

> **Audit corrected this record.** Checked on this workstation, which runs omarchy 4.0.2-1 and Hyprland 0.56.2, and against issue 6947 read in full with comments. Confirmed here: `/usr/share/omarchy/default/hypr/apps/steam.lua` line 1 is exactly the rule the record quotes, `/usr/share/omarchy/default/hypr/helpers.lua` assigns a string `match` straight to `rules.match.class` and calls `hl.window_rule`, the installed `/usr/bin/Hyprland` exports only RE2's `FullMatchN` and no `PartialMatchN`, and `/usr/share/omarchy/default/hypr/apps/terminals.lua` carries the comment `The class is matched in full`, so the full-match premise holds. `hyprctl clients -j` on this session shows `fullscreen` as an integer and `inhibitingIdle` as a real field, so both the symptom JSON and the verify block name fields that exist. `idle_inhibit` is a recognised rule key in the 0.56.2 binary, which also carries the string `idle_inhibit rule has unknown mode "{}"`, and the Hyprland wiki lists the modes as none, always, focus and fullscreen, so both the record's `fullscreen` and the reported `focus` variant are valid. `hyprctl reload` and `hyprctl configerrors` are both in `hyprctl --help` here. The comment the fix anchors to, `Add any other personal Hyprland configuration below`, is present verbatim in `/usr/share/omarchy/config/hypr/hyprland.lua`, and `o` is global by then, which my own config already relies on.

The missing link the record left implicit is now in the cause and it checks out here: `/usr/share/omarchy/shell/plugins/services/idle/Service.qml` lines 250 to 256 run a Quickshell `IdleMonitor` with `respectInhibitors: true`, so a Hyprland inhibitor really does suppress Omarchy's screensaver and lock rather than only a hypridle that is not installed.

Issue 6947 supports the claim. The reporter gives the class, the `inhibitingIdle: false` reading and the same one-line rule, VillainRU confirms the workaround with `inhibitingIdle: true` and controller-only play past the timeout, cinco gives the gamescope class with `inhibitingIdle: false` and confirms the gamescope rule, and etherealheim reports the `focus` variant without a second confirmation, which is how the record already describes it. Corrected rather than ok for two reasons. The record's version line stops at omarchy 4.0.2-1 and `quattro`, and tag `v4.0.3` of 2026-09-08 is newer and still ships the unfixed rule, which I checked with `gh api` on both refs. And two pull requests now exist, 9651 and 9667, both open on 2026-09-11, both adding only the `steam_app_.*` rule and neither covering `gamescope`. The symptom's user and controller counts were also loose, so they are restated exactly. Not exercised: I did not launch Steam or a game, gamescope is not installed here, and I never reloaded the running config, so every live reading of a `steam_app_*` or `gamescope` window comes from the issue thread rather than from this machine.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Add rules for the game window classes to the end of `~/.config/hypr/hyprland.lua`, below the `Add any other personal Hyprland configuration below` comment:

```lua
-- ~/.config/hypr/hyprland.lua
o.window("steam_app_.*", { idle_inhibit = "fullscreen" })
o.window("gamescope", { idle_inhibit = "fullscreen" })
```

Reload and check the config parsed:

```bash
hyprctl reload
hyprctl configerrors
```

`steam_app_.*` covers Proton games. A native Linux game can use its own class, so if one still triggers the screensaver, read its class while it is running and add a rule for it:

```bash
hyprctl clients -j | jq '.[] | {class, initialClass, title, fullscreen, inhibitingIdle}'
```

One reporter used `idle_inhibit = "focus"` instead for games run borderless-windowed rather than fullscreen. Nobody else confirmed that variant.

**Verify.** With the game fullscreen, the window now reports the inhibitor, and normal idle locking resumes when the game is closed:

```bash
hyprctl clients -j | jq '.[] | select(.class | test("^steam_app_|^gamescope")) | {class, fullscreen, inhibitingIdle}'
```

Expected `"fullscreen": 2` and `"inhibitingIdle": true`. Two reporters confirmed controller-only play past the idle timeout with neither screensaver nor lock activating.

Sources: <https://github.com/omacom/omarchy/issues/6947> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/apps/steam.lua> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/helpers.lua> · <https://github.com/omacom/omarchy/pull/9651> · <https://github.com/omacom/omarchy/pull/9667> · <https://github.com/omacom/omarchy/blob/v4.0.3/default/hypr/apps/steam.lua> · <https://wiki.hypr.land/configuring/core/rules/window-rules/> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/rules/window-rules.md>

---

## Stop hyprpm asking permission to load plugins on every login

`hyprpm-plugin-permission-popup-every-time` · severity: **medium** · frequency: **rare** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`

**Symptom.** You turned Hyprland's permission enforcement on, and now every `hyprpm reload`, including the one in your autostart, pops a Hyprland dialog asking whether to let hyprpm load a plugin. The plugins only load if you click Allow. The dialog offers only Deny and Allow, with no option to remember the choice, so it returns on the next run even inside the same session. On a stock Omarchy 4 install you will not see this at all, because permission enforcement is off by default and nothing is ever asked.

**Cause.** Hyprland's permission system gates plugin loading and the `plugin` permission defaults to ASK, but the gate is only reached when `ecosystem:enforce_permissions` is true. In Hyprland 0.56.2 both entry points in `src/managers/permissions/DynamicPermissionManager.cpp` read that option first and return `PERMISSION_RULE_ALLOW_MODE_ALLOW` immediately when it is 0, so with enforcement off no rule is consulted and no dialog is drawn. Omarchy 4 ships it off: on a stock 4.0.2-1 install `hyprctl getoption ecosystem:enforce_permissions` reports `bool: false` and `set: false`, and `/usr/share/omarchy` sets no permission rules of its own. Once enforcement is on, a plugin load arrives through `clientPermissionModeWithString` with no `wl_client`, and that branch builds the dialog with only Deny and Allow. The allow and remember option exists only where a `wl_client` is present, which covers permissions such as screencopy and never covers plugins. Nothing is written to disk either way: granted rules live in an in-memory vector for the life of the compositor, and a cached grant is keyed on the requesting process id, so a fresh `hyprpm` process never matches an earlier one and is asked again. The only persistent grant is a config rule. `hyprland-guiutils` must also be installed, because without it Hyprland logs that it cannot ask and falls back to allowing.

> **Audit corrected this record.** Checked against Hyprland v0.56.2 source and this workstation, omarchy 4.0.2-1 and hyprland 0.56.2-1. The record's headline symptom cannot occur on a stock Omarchy 4 install, and its cause statement about enforcement being off is the reverse of what the code does. Confirmed live here that `hyprctl getoption ecosystem:enforce_permissions` returns `bool: false` with `set: false`, so Omarchy 4 leaves the value at Hyprland's own default. In `src/managers/permissions/DynamicPermissionManager.cpp`, both `clientPermissionMode` and `clientPermissionModeWithString` open with a read of `ecosystem:enforce_permissions` and `if (*PPERM == 0) return PERMISSION_RULE_ALLOW_MODE_ALLOW;`, which returns before any rule walk and before `askForPermission` is ever called. So with enforcement off there is no popup at all, not a popup without remember as the record claims. The wiki's BSD paragraph is where that claim comes from and it does not match 0.56.2, so the page is kept as a source for the rest but the sentence was dropped. The record's fix then makes it worse by telling an Omarchy 4 reader to set `enforce_permissions = true`, which switches on ASK prompts for screencopy, cursorpos and input-capture system wide in order to suppress one prompt they were not getting. The fix is rewritten to check the option first and branch. Two mechanics were added after reading the source. `src/plugins/PluginSystem.cpp` calls `clientPermissionModeWithString(pid, path, PERMISSION_TYPE_PLUGIN)` with no `wl_client`, and in `askForPermission` the {Deny, Allow and remember, Allow once} option set requires `!binaryPath.empty() && client`, so a plugin prompt only ever offers Deny and Allow: there is no remember button for plugins. And the grant is stored nowhere on disk. Rules live in the manager's in-memory `m_rules` vector with no write path, and the cache entry matches on `e->m_pid`, so each new hyprpm process is asked again. The only file that persists a grant is the Lua config holding `hl.permission`, `~/.config/hypr/hyprland.lua` on Omarchy 4. Confirmed the record's table form is valid: `hlPermission` in `src/config/lua/bindings/LuaBindingsConfigRules.cpp` accepts both `{binary, type, mode}` and the three positional strings, and `/usr/share/hypr/stubs/hl.meta.lua` declares `permission fun(spec: HL.PermissionSpec)`. Confirmed `hyprland-guiutils 0.2.2-2` is installed here and that the no-hot-reload claim holds, both from the wiki and from the comment at lines 67 and 68 of the shipped `/usr/share/hypr/hyprland.lua`. Frequency lowered from common to rare, because the state is reachable only for someone who deliberately enabled a feature that both Hyprland and Omarchy 4 ship off. NOT exercised: enforcement was not enabled and no dialog was triggered, since that would mean writing to the operator's live config and restarting the session.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not blanket-allow `plugin` for `hyprctl`. Anyone who can reach your hyprctl socket could then run `hyprctl plugin load /tmp/malicious.so` inside your compositor. Allow the hyprpm binary path specifically. Likewise a blanket `screencopy` allow for `.*` lets any local process silently record your screen. The opposite mistake is worth naming too: switching `ecosystem:enforce_permissions` on and then pasting broad allow rules to stop the resulting prompts leaves you worse off than the Omarchy 4 default, which at least does not claim to enforce anything. If you enable it, add narrow rules only for binaries you can name.

**Fix.**

Decide first whether you want the permission system at all, because on Omarchy 4 it is off and this problem cannot happen.

Check what you have:

```bash
hyprctl getoption ecosystem:enforce_permissions
```

If it reports `bool: false`, enforcement is off, hyprpm is never gated, and there is nothing to fix. That is the Omarchy 4 default. Do not turn enforcement on in order to stop a prompt you are not getting: `screencopy`, `cursorpos` and `input-capture` all default to ASK, so enabling it starts prompting for screenshots, screen sharing and cursor access across the whole system.

If it reports `bool: true`, you opted into the permission system and the fix is an explicit allow rule for the hyprpm binary. Put it in `~/.config/hypr/hyprland.lua` on Omarchy 4, or in your main Lua config on any Hyprland 0.55 or newer:

```lua
hl.permission({ binary = "/usr/(bin|local/bin)/hyprpm", type = "plugin", mode = "allow" })
```

`binary` is a regex matched against the full path of the calling binary. On Omarchy 4 hyprpm is at `/usr/bin/hyprpm` and is owned by the `hyprland` package, so the pattern above covers it.

While enforcement is on you will also want to name the screen capture tools you actually use, rather than clicking through a dialog every time:

```lua
hl.permission({ binary = "/usr/bin/grim", type = "screencopy", mode = "allow" })
hl.permission({ binary = "/usr/(lib|libexec|lib64)/xdg-desktop-portal-hyprland", type = "screencopy", mode = "allow" })
```

Permission rules are deliberately not hot reloaded. `hyprctl reload` will not apply them. Log out and back in.

The dialog needs `hyprland-guiutils`. Confirm it is installed, because without it Hyprland cannot ask and quietly allows instead:

```bash
pacman -Q hyprland-guiutils
```

The older package name `hyprland-qtutils` is not what Omarchy 4 ships.

**Verify.** `hyprctl getoption ecosystem:enforce_permissions` reports the value you meant to have. With enforcement on and the rule in place, log out and back in, then `hyprpm reload -n` loads the plugins with no dialog and `hyprctl plugin list` names them instead of printing `no plugins loaded`.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Permissions/> · <https://wiki.hypr.land/Plugins/Using-Plugins/> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/advanced-configuration/permissions.md> · <https://github.com/hyprwm/hyprland-wiki/blob/main/content/hyprland-plugins/using-plugins.md> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/managers/permissions/DynamicPermissionManager.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/plugins/PluginSystem.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsConfigRules.cpp>

---

## Clear the red config-error bar pinned across every screen

`config-error-bar-covers-screen` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `manjaro`, `omarchy`

**Symptom.** A red config-error bar is pinned across the top of every screen, over the browser and everything else, and stays there. Users describe it as 'IN YOUR FACE' and unusable.

**Cause.** Hyprland draws config errors in an overlay bar, `src/errorOverlay/Overlay.cpp`, re-queued on every config reload and rendered on every monitor. It reserves screen space on the focused monitor, so windows there are pushed down or up rather than covered, while on any other monitor it sits on top of whatever is below it. What happens to the rest of the config depends on the syntax. A hyprlang parse error skips the offending line and the rest of the file still loads, which is the "non-fatal" behaviour most advice describes. A Lua error stops execution at that point, so nothing later in the file runs, and if that leaves zero keybinds registered Hyprland 0.56.2 also trips emergency mode. The bar's position and the number of lines it shows are configurable through `debug:error_position` and `debug:error_limit`, and `debug:suppress_errors` stops it being drawn at all.

> **Audit corrected this record.** Checked against Hyprland v0.56.2 source (hyprwm/Hyprland), against the live wiki page the record already cites, and live on this Omarchy 4 workstation (hyprland 0.56.2-1, omarchy 4.0.2-1). The three options are real and the record's semantics held: `src/errorOverlay/Overlay.cpp` reads `debug:error_limit` and `debug:error_position` and sets `const bool TOPBAR = *BAR_POSITION == 0;`, so 0 is top and 1 is bottom as the record says, and https://wiki.hypr.land/Configuring/Basics/Variables/ documents error_position default 0, error_limit default 5 and suppress_errors default false. That last one is the first defect: the record tells the reader to cap the bar at `error_limit = 5`, which is already the default, confirmed live here with `hyprctl getoption debug:error_limit` returning `int: 5 set: false`, so the advice as written changes nothing. The second defect is the `hyprctl seterror disable` framing. It is not limited to a bar set by a script: `dispatchSeterror` in `src/debug/HyprCtl.cpp` calls `ErrorOverlay::overlay()->destroy()` for any invocation with fewer than three arguments, so it clears the parser's bar too, and the wiki's Using-hyprctl page says the error string "will reset when Hyprland's config is reloaded". So the honest answer is that the bar can be dismissed without fixing the config, but only until the next reload, and I rewrote the fix to say that rather than leaving the folklore in place. The third defect is the cause: "the offending lines are just ignored" is true of a hyprlang parse error but not of Lua, where an error stops the file, and on 0.56.2 a file that stops before registering any bind also trips emergency mode, which the record's sibling covers. I also labelled the hyprlang block as plain Arch and said where the Lua goes on Omarchy 4, `~/.config/hypr/looknfeel.lua`, after reading `/usr/share/omarchy/config/hypr/hyprland.lua` to confirm the module load order. Checked whether the edit is transient: `/usr/share/omarchy/bin/omarchy-update` never calls `omarchy-refresh-hyprland`, and the migrations under `/usr/share/omarchy/migrations/` patch `hyprland.lua` surgically, so the edit survives `omarchy update` and is only lost if the reader runs `omarchy-refresh-hyprland` themselves. Cited issue 5758 was read in full: it is real and closed on 2026-05-12, and it supports the symptom and the non-fatal hyprlang behaviour, but it is Omarchy 3.8 on Hyprland 0.55 with `.conf` files under `~/.local/share/omarchy`, so it does not carry the Omarchy 4 Lua specifics on its own. Its basecamp URL 404s for an anonymous fetch after the rename, so it is replaced by the omacom one. NOT exercised: I did not run `hyprctl seterror`, `hyprctl keyword` or `hyprctl reload` on this workstation, and I did not induce a config error, so the dismissal behaviour is confirmed from the v0.56.2 source and the wiki rather than by triggering the bar.
>
> *The Cause above was rewritten on 2026-09-13 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `suppress_errors = true` hides genuinely broken config from you later, including the emergency mode banner that tells you no keybindings were registered. `hyprctl seterror disable` clears the bar only until the next config reload, so it is easy to mistake for a fix when the config is still broken.

**Fix.**

Read the errors first, because everything below only changes how they are shown:

```bash
hyprctl configerrors
```

Move the bar to the bottom. On Omarchy 4 put this in `~/.config/hypr/looknfeel.lua`, which is loaded after the Omarchy defaults:

```lua
hl.config({ debug = { error_position = 1 } })   -- 0 = top, 1 = bottom
```

`debug:error_limit` already defaults to 5 and accepts 0 to 20, so setting it to 5 changes nothing. Lower it only if five lines is still too many:

```lua
hl.config({ debug = { error_position = 1, error_limit = 2 } })
```

On plain Arch with a hyprlang `~/.config/hypr/hyprland.conf`, the equivalent is:

```ini
debug {
  error_position = 1
  error_limit    = 2
}
```

Omarchy 4 ships no `hyprland.conf`. Its Hyprland config is `~/.config/hypr/hyprland.lua` plus the `hypr/*.lua` modules it requires, so use the Lua form there.

Drop the bar right now without editing anything:

```bash
hyprctl seterror disable
```

That destroys the overlay whatever put it there, the config parser included, not only a bar set by a script. It is temporary: the next config reload draws it again.

Suppress it for good, once you know what the errors are:

```lua
hl.config({ debug = { suppress_errors = true } })
```

Neither of those fixes the config, and the errors are still listed by `hyprctl configerrors`. If the bar is the only thing telling you the config is broken, the real fix is the config.

`omarchy update` does not overwrite `~/.config/hypr/*.lua`, so an edit there survives updates. `omarchy-refresh-hyprland` does overwrite them with the Omarchy defaults, so re-apply the setting if you ever run it.

**Verify.** `hyprctl configerrors` prints nothing once the config parses cleanly. After `hyprctl reload` the bar is gone, or sits at the bottom if you moved it. Confirm the settings took with `hyprctl getoption debug:error_position` and `hyprctl getoption debug:error_limit`.

Sources: <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Using-hyprctl/> · <https://github.com/omacom/omarchy/issues/5758> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/errorOverlay/Overlay.cpp> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/debug/HyprCtl.cpp>

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

> **Audit corrected this record.** Re-checked on this workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, hyprland 0.56.2-1, kernel 7.1.9-arch1-2, NVIDIA) against the live system, the current Hyprland wiki markdown and Hyprland's source at tag v0.56.2. The mechanism and both Omarchy claims hold. The verify block is wrong in two ways and the toolkit advice is incomplete.

What held, and where. `xwayland:force_zero_scaling` is still the option name on 0.56.2 and reads `bool: true, set: true` here, and `xwayland:use_nearest_neighbor` reads `bool: true, set: false`, so the record's "default true" is confirmed live rather than only from the wiki. `/usr/share/omarchy/default/hypr/envs.lua` on this machine does set `force_zero_scaling = true` in an `hl.config()` block and does set `XCURSOR_SIZE` and `HYPRCURSOR_SIZE` to 24. `/usr/share/omarchy/config/hypr/monitors.lua` does carry `local omarchy_gdk_scale` and `hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))`. The current wiki page `content/configuring/extra/xwayland.md` still recommends exactly `force_zero_scaling` plus `GDK_SCALE` and `XCURSOR_SIZE` with the monitor at `highres`, and still carries the warning against XWayland HiDPI patches, so the record's `danger` is right. The Arch HiDPI page confirms the `Xft.dpi` versus `GDK_SCALE` conflict with Firefox named as the usual casualty, and confirms `--force-device-scale-factor` for Electron and integer multiples of 96 for `Xft.dpi`.

Placement is right and this matters, because on Omarchy 4 most session environment comes from uwsm. `hl.env()` is nevertheless the correct place, not `~/.profile` and not `~/.config/uwsm/env.d/`, and that is confirmed on this machine rather than reasoned: `~/.config/hypr/monitors.lua` here sets `local omarchy_gdk_scale = 1` and `systemctl --user show-environment` reports `GDK_SCALE=1`, alongside `XCURSOR_SIZE=24` from `envs.lua`. `~/.config/uwsm/` does not exist on this install at all. The record's claim that an env change needs a reload plus a relaunch is also correct: `hlEnv` in `src/config/lua/bindings/LuaBindingsConfigRules.cpp` at v0.56.2 calls `setenv` unconditionally and only short-circuits when the value is unchanged, so a reload does re-apply it.

What was wrong. The verify said `hyprctl getoption xwayland.force_zero_scaling` "returns 1". Run here it prints `bool: true` and `set: true` on two lines, never `1`, so a reader following it literally concludes the option is unset. It also said `hyprctl clients | grep -A2 xwayland` shows `xwayland: 1` for the app. Run here that prints `xwayland: 0`, `pinned: 0`, `pinFullscreened: 0` and no class or title, because `xwayland: N` is itself the matched line, so it can never tell you which window the flag belongs to. Both replaced with checks that were run on this machine. The fix said `GDK_SCALE` is set "at the bottom" of `monitors.lua`, which is wrong on 4.0.2-1: in the shipped template the two locals and the `hl.env` line sit at the top above the catch-all rule, and the bottom of the file holds commented examples. The Qt advice set only `QT_AUTO_SCREEN_SCALE_FACTOR`, which the Arch HiDPI page records as replaced by `QT_ENABLE_HIGHDPI_SCALING` in Qt 5.14, and recommends setting both. Added a GDK_SCALE mismatch paragraph, because this workstation carries a first-hand instance of it in a comment in `~/.config/hypr/monitors.lua`: `GDK_SCALE=2` on a scale-1 27 inch 1440p panel made Steam draw zoomed with its titlebar drag region offset so its windows could not be moved. Finally the last block was fenced as `bash` while its first two lines were Lua. The previous auditor saw this and called it cosmetic. In a corpus whose whole claim is copy-pasteable fixes it is a defect, so the Lua line is now in its own Lua fence.

Not exercised. Nothing was written and no scale, mode or config was changed, because this is the operator's daily workstation driving a real panel and libvirt VMs. `force_zero_scaling` was read, never toggled. No app was relaunched to observe sharpness, so the visual outcome is from the wiki, not from a test here. `_JAVA_OPTIONS` and the Electron flag file were not tried. The XWayland client filter was validated against the real `hyprctl clients` output on this machine, but every window open at the time reported `xwayland: 0`, so the `select(.xwayland)` branch matched nothing and was checked by reading the field rather than by seeing it fire.

Swapped the two `basecamp/omarchy` blob URLs for `omacom/omarchy`, the current name. The old ones still redirect, but both files were re-fetched against `omacom/omarchy@quattro` for this audit.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

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

-- Now each toolkit scales itself. GTK only honours whole numbers, so use the
-- nearest integer to your monitor scale.
hl.env("GDK_SCALE", "2")
hl.env("XCURSOR_SIZE", "32")

-- Qt. QT_AUTO_SCREEN_SCALE_FACTOR was replaced by QT_ENABLE_HIGHDPI_SCALING in
-- Qt 5.14 and everything current on Arch is Qt 6, so set both.
hl.env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
hl.env("QT_ENABLE_HIGHDPI_SCALING", "1")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
```

**Omarchy 4 already does the first half for you.** `force_zero_scaling = true` is set in the `hl.config()` block at the end of `/usr/share/omarchy/default/hypr/envs.lua`, and `XCURSOR_SIZE` and `HYPRCURSOR_SIZE` are set to 24 in the same file. `GDK_SCALE` is set near the **top** of `~/.config/hypr/monitors.lua`, above the catch-all monitor rule, from a local variable. Edit that file, not a new one:

```lua
-- ~/.config/hypr/monitors.lua
local omarchy_gdk_scale = 2
local omarchy_monitor_scale = "auto"

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })
```

or let Omarchy write both numbers consistently:

```bash
omarchy-hyprland-monitor-scaling 1.6
```

**Keep the two numbers in step.** `GDK_SCALE` must be the nearest integer to the monitor scale. Setting `GDK_SCALE=2` on a monitor running at scale 1 makes every GTK and XWayland client draw at double size, and on Steam, which is XWayland plus CEF, it also offsets the titlebar drag region so the window cannot be moved. `omarchy-hyprland-monitor-scaling` writes both numbers together for exactly this reason, but only while `monitors.lua` still has Omarchy's generic shape.

Toolkits `GDK_SCALE` does not cover. Lua lines go in your Hyprland config:

```lua
-- Java / JetBrains
hl.env("_JAVA_OPTIONS", "-Dsun.java2d.uiScale=2")
```

The rest are per-app files, not environment variables:

```bash
# Electron/Chromium apps still on XWayland: a flag file, e.g. ~/.config/code-flags.conf
echo '--force-device-scale-factor=2' >> ~/.config/code-flags.conf

# Legacy X11 apps that read Xft.dpi (integer multiples of 96)
printf 'Xft.dpi: 192\n' >> ~/.Xresources
xrdb -merge ~/.Xresources
```

Env changes only reach apps started **after** the config is re-read. Hyprland re-runs every `hl.env()` line on reload, so `hyprctl reload` and then relaunch the app from a Hyprland keybind or the Omarchy menu is enough. Two things it is not enough for: a terminal that was already open keeps the old value and passes it to anything you start from it, and the systemd user environment is only guaranteed to match after a full session restart (log out and back in). Do not judge the fix by a window that was already open.

**Verify.** Relaunch the app, then confirm the option and the client:

```bash
hyprctl getoption xwayland:force_zero_scaling
# bool: true
# set: true

hyprctl -j clients | jq -r '.[] | select(.xwayland) | "\(.class)\t\(.title)"'
```

`getoption` prints `bool: true`, not `1`. The dotted form `xwayland.force_zero_scaling` works too. The `jq` filter is the reliable way to find XWayland clients, because `hyprctl clients | grep xwayland` matches the `xwayland: 0` flag line itself and never the window it belongs to. Text in the relaunched app should now be crisp rather than soft or blocky, and it should be the same physical size as a native Wayland window.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/XWayland/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/FAQ/> · <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/> · <https://wiki.archlinux.org/title/HiDPI> · <https://wiki.hypr.land/configuring/extra/xwayland/> · <https://wiki.hypr.land/configuring/core/environment-variables/> · <https://wiki.hypr.land/configuring/core/monitors/> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsConfigRules.cpp> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/envs.lua> · <https://github.com/omacom/omarchy/blob/quattro/config/hypr/monitors.lua> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hyprland-monitor-scaling>

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

## Make LocalSend float again: Omarchy's window rule does not match class `org.localsend.localsend_app`

`localsend-opens-tiled-window-rule-class-mismatch` · severity: **low** · frequency: **common** · applies to: `hyprland`, `localsend`, `omarchy`, `wayland`

**Symptom.** LocalSend opens tiled in the active layout instead of as a centered 1100x700 floating window. The older report 7482 adds that clicks do not reach the window's buttons while it is tiled, and that floating the window fixes that too. Reported on Omarchy 4.0.0-1 with `localsend` 1.18.1-1 and on Omarchy 4.0.1-1 with `localsend` 1.18.2-1, both from the Arch repos, on Hyprland 0.56.2. `hyprctl clients` shows the window's class:

```json
{
  "class": "org.localsend.localsend_app",
  "initialClass": "org.localsend.localsend_app",
  "title": "LocalSend"
}
```

**Cause.** `/usr/share/omarchy/default/hypr/apps/localsend.lua` matches the class with `(Share|localsend)` and `localsend`:

```lua
-- Float LocalSend and fzf file picker.
o.window("(Share|localsend)", { float = true, center = true })
o.window("localsend", { size = { 1100, 700 } })
```

`o.window` in `default/hypr/helpers.lua` puts that string straight into `rules.match.class` and hands it to `hl.window_rule`, and Hyprland 0.56 matches a class against the whole string, so `(Share|localsend)` cannot match `org.localsend.localsend_app` and the window gets no rule at all. Anchors were never the missing piece, the app id was.

That app id is the installed package's own. The binary `/usr/lib/localsend/localsend_app` and `/usr/lib/localsend/lib/libapp.so` from `localsend` 1.18.2-1 both carry the string:

```bash
strings -a /usr/lib/localsend/localsend_app | grep org.localsend
```

Three people report the same class. peteonrails reproduced it with the real application on Hyprland 0.56.2, stock rules giving `floating: false` at 656x1167 and an anchored rule giving floating at 1100x700. The repository's review bot reached the same result on a disposable worker, though with a terminal relabelled to that app id rather than LocalSend itself.

Nothing has shipped. Issue 7482 is open, issue 8817 was closed on 2026-09-03 by its own reporter as a duplicate of 7482 and not because a fix landed, and the two pull requests that make the byte-identical change to `default/hypr/apps/localsend.lua`, 7736 and 8878, were both still open on 2026-09-11. `quattro` and tag `v4.0.3` of 2026-09-08 both still carry the unfixed rule, as does omarchy 4.0.2-1 on disk.

> **Audit corrected this record.** Checked on this workstation, which runs omarchy 4.0.2-1, Hyprland 0.56.2 and has `localsend` 1.18.2-1 installed, and against issues 8817 and 7482 and pull requests 8878 and 7736, all read in full with comments. Confirmed here: `/usr/share/omarchy/default/hypr/apps/localsend.lua` is still the two unfixed rules the record quotes, `/usr/share/omarchy/default/hypr/helpers.lua` assigns a string `match` to `rules.match.class` and calls `hl.window_rule`, the installed `/usr/bin/Hyprland` exports only RE2's `FullMatchN` with no `PartialMatchN`, and `/usr/share/omarchy/default/hypr/apps/terminals.lua` states `The class is matched in full`, so the full-match mechanism is confirmed on this machine and not only asserted upstream. The app id is confirmed here too: `strings -a /usr/lib/localsend/localsend_app` and the same on `/usr/lib/localsend/lib/libapp.so` both return `org.localsend.localsend_app`. `hyprctl clients -j` on this session has `floating` and `size` as real fields, so the verify block is well formed, and `hyprctl reload` is in `hyprctl --help`. The comment in `/usr/share/omarchy/config/hypr/hyprland.lua` confirms a user rule appended after the `require` lines is loaded after Omarchy's defaults, and in this case there is no conflict to resolve because the shipped rule matches nothing for that app id. The fix's Lua is correct: `org\\.` in the record renders as `org\.` in the file, which reaches RE2 as a literal dot, and it is byte-identical to the change in both pull requests, which I read as diffs.

The cited issues do support the claim. 7482 gives the class, the tiled window and the dead clicks, with a working anchored workaround, although its own root-cause hypothesis about unanchored matching is wrong and the record correctly does not repeat it. 8817 gives the same class with the same diagnosis. Corrected rather than ok on three points of fact. 8817 is now closed, on 2026-09-03, by the reporter as a duplicate rather than by a fix, and a reader who saw only a closed issue would draw the wrong conclusion. The record's date line stopped at 2026-09-07 while both pull requests are still open on 2026-09-11 and tag `v4.0.3` of 2026-09-08 still ships the unfixed file, which I checked on both refs with `gh api`. And the version pairing in the symptom was wrong: 7482 reports `localsend` 1.18.1-1 on Omarchy 4.0.0-1, while 1.18.2-1 belongs to the 4.0.1-1 report. The stronger evidence was also under-credited, so the cause now names peteonrails' reproduction with the real application and says plainly that the bot's reproduction used a relabelled terminal. Not exercised: I did not launch LocalSend and did not reload the running config, so the floating and 1100x700 result comes from those reports rather than from this machine.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Until the fix ships, add the corrected rules to your own config. `~/.config/hypr/hyprland.lua` loads Omarchy's defaults first, so a rule placed after the `require` lines wins. Append at the end of the file:

```lua
-- LocalSend's Wayland app id is org.localsend.localsend_app, which the
-- shipped (Share|localsend) rule cannot match. Same rules as omarchy PR #8878.
o.window("^(Share|localsend|org\\.localsend\\.localsend_app)$", { float = true, center = true })
o.window("^(localsend|org\\.localsend\\.localsend_app)$", { size = { 1100, 700 } })
```

Reload and relaunch LocalSend:

```bash
hyprctl reload
```

Remove the two lines once an update ships a `localsend.lua` that names the app id:

```bash
grep -n localsend_app /usr/share/omarchy/default/hypr/apps/localsend.lua
```

**Verify.** ```bash
hyprctl clients -j | jq '.[] | select(.class == "org.localsend.localsend_app") | {floating, size}'
```

Expect `"floating": true` and `"size": [1100, 700]`. The collaborator's reproduction on Hyprland 0.56.2 gave exactly that with the fixed rules and `floating=false` at the layout's size without them.

Sources: <https://github.com/omacom/omarchy/issues/8817> · <https://github.com/omacom/omarchy/issues/7482> · <https://github.com/omacom/omarchy/pull/8878> · <https://github.com/omacom/omarchy/pull/7736> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/apps/localsend.lua> · <https://github.com/omacom/omarchy/blob/v4.0.3/default/hypr/apps/localsend.lua> · <https://github.com/omacom/omarchy/blob/quattro/default/hypr/helpers.lua> · <https://wiki.hypr.land/configuring/core/rules/window-rules/>

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

**Cause.** **Tearing** is only applied when the tearing window is fullscreen and is the *only* thing visible on that output. A notification, a bar, a lock surface, an overlay or a second window on the same monitor suppresses it, and it needs both the `general:allow_tearing` master toggle and a per-window `immediate` rule. `hyprctl monitors` says which condition is failing in its `tearingBlockedBy` field. Frozen or artefacted output almost always means the GPU driver does not support tearing, and the Hyprland wiki asks that it not be reported as a Hyprland bug. **VRR brightness flicker** is not something Hyprland controls. FreeSync panels often have a VRR range much narrower than their maximum refresh rate, and a panel driven across a limited range shows it as flicker: the one Hyprland report cited (an AOC FreeSync monitor over DisplayPort on AMD, swinging between 72 and 144 Hz while the game held 120 fps) matches that pattern, and it was auto-closed without a maintainer reply because Hyprland no longer accepts user-filed issues. VRR also requires DisplayPort on most hardware, HDMI VRR needs a display that implements that part of HDMI 2.1, and some monitors only expose VRR below their maximum refresh rate.

> **Audit corrected this record.** Checked every Lua form on this Omarchy 4 / Hyprland 0.56.2 machine and against the wiki. The Tearing page gives the identical hl.config allow_tearing plus hl.window_rule immediate snippet, states the fullscreen-and-only-thing-visible precondition, and says freezes and colourful artefacts almost definitely mean the driver does not support tearing. The config options page confirms misc:vrr 0/1/2/3 with 3 meaning video or game content type, cursor:no_break_fs_vrr 0/1/2 with default 2, and cursor:min_refresh_rate default 24 range 10 to 500, and the machine's hyprctl getoption returns the same defaults. hyprctl --help and the Using hyprctl page both list eval, and `hyprctl eval 'hl.config({ misc = { vrr = 0 } })'` returned ok and flipped getoption to set: true, so the live-try command is real. hyprctl -j monitors exposes vrr, activelyTearing and tearingBlockedBy, and Hyprland 0.56.2's MonitorRuleManager.cpp line 214 uses the monitor rule's vrr when set and misc:vrr otherwise, so the precedence claim holds. The window rules page lists content (none/photo/video/game) and fullscreen as match props and immediate as an effect. The Arch VRR page confirms DisplayPort is required, HDMI VRR needs partial HDMI 2.1, some monitors only do VRR below their maximum rate, and FreeSync ranges are often narrow. Two things were wrong: the gamescope launch line is not on the cited Arch Gaming page, which only links to the Gamescope page where `gamescope -W 1920 -H 1080 -r 60 -- %command%`, `-f` and `--adaptive-sync` are documented, and the 'panels change perceived brightness with refresh rate' mechanism appears in no cited source, so the cause now attributes flicker to a limited VRR range as the Arch page does. Hyprland issue 11712 is a user report of 72 to 144 Hz flicker on an AOC FreeSync panel that the bot closed 11 seconds after filing, so it is evidence the symptom exists and nothing more. The fix gains the wiki's own tearingBlockedBy diagnostic and the gamescope --adaptive-sync flag, and was otherwise correct.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Tearing is experimental and driver-dependent: if the driver does not support it, apps that should tear will freeze outright or render corrupted frames, and there is no compositor-side workaround. Turn `allow_tearing` back off before assuming a game is broken. Setting `vrr = 1` (always on) on a panel with a narrow VRR range can make the whole desktop flicker constantly — `vrr = 2` is the safe default.

**Fix.**

**Tearing** needs the master toggle plus a per-game rule:

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
hyprctl monitors | grep -i tearing          # activelyTearing, and tearingBlockedBy says why not
```

`tearingBlockedBy` lists the exact blocker: `user settings` means the master toggle is off, `missing candidate` means no fullscreen window with an `immediate` rule is the only thing on that output.

**VRR** is a global default, then per-monitor where it matters. `0` off, `1` always on, `2` fullscreen only, `3` fullscreen with `video`/`game` content type:

```lua
hl.config({
  misc = {
    vrr = 2,      -- fullscreen only: the standard answer to desktop flicker
  },
})

-- Per-display override. A monitor `vrr` field beats the misc default.
hl.monitor({ output = "DP-1", mode = "2560x1440@144", position = "0x0", scale = 1, vrr = 2 })
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1, vrr = 0 })
```

Try it live before committing:

```bash
hyprctl eval 'hl.config({ misc = { vrr = 2 } })'
```

If flicker persists at `vrr = 2` inside games, the panel's VRR range is the problem. Cap the in-game framerate inside that range, drop the monitor to a refresh rate the panel supports VRR at, or turn VRR off for that output. Use DisplayPort. HDMI VRR only works on displays that implement the relevant part of HDMI 2.1.

Cursor movement can also break VRR framepacing in fullscreen apps:

```lua
hl.config({
  cursor = {
    no_break_fs_vrr = 1,      -- 0 off, 1 on, 2 auto (on for content type 'game'). May need no_hardware_cursors = 1
    min_refresh_rate = 60,    -- floor for cursor-driven frames, default 24
  },
})
```

**When Proton/Wine still misbehaves**, run the game inside gamescope, which gives it an isolated micro-compositor with its own framerate and scaling handling rather than fighting Hyprland's. Add `--adaptive-sync` if you want VRR inside the gamescope session:

```bash
sudo pacman -S --needed gamescope
# Steam launch options:
#   gamescope -W 2560 -H 1440 -r 144 -f -- %command%
#   gamescope -W 2560 -H 1440 -r 144 -f --adaptive-sync -- %command%
```

**Verify.** `hyprctl getoption general.allow_tearing` is 1 and `hyprctl getoption misc.vrr` matches what you set; `hyprctl -j monitors | jq -r '.[] | "\(.name) vrr=\(.vrr)"'` shows the per-output state; in a fullscreen game the reported refresh rate tracks the framerate and the desktop no longer pulses.

Sources: <https://wiki.hypr.land/Configuring/Advanced-and-Cool/Tearing/> · <https://wiki.hypr.land/Configuring/Basics/Variables/> · <https://wiki.hypr.land/Configuring/Basics/Monitors/> · <https://wiki.archlinux.org/title/Variable_refresh_rate> · <https://github.com/hyprwm/Hyprland/issues/11712> · <https://wiki.archlinux.org/title/Gaming> · <https://wiki.hypr.land/configuring/extra/tearing/> · <https://wiki.hypr.land/configuring/core/config-options/> · <https://wiki.hypr.land/configuring/core/rules/window-rules/> · <https://wiki.hypr.land/configuring/core/advanced-configuration/using-hyprctl/> · <https://wiki.archlinux.org/title/Gamescope> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/shared/monitor/MonitorRuleManager.cpp>

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
