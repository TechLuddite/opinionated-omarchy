# Networking

45 problems. Sorted by severity, then by how often users hit it.

## Fix a brand-new Intel Wi-Fi card that finds no usable firmware

`iwlwifi-no-suitable-firmware-new-intel-card` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `omarchy`

**Symptom.** Fresh install on new hardware (e.g. Dell XPS 13 with Intel Wi-Fi 7 BE213) has no Wi-Fi at all, across reboots. `journalctl -k | grep iwlwifi` shows:

```
iwlwifi 0000:00:14.3: Detected Intel(R) Wi-Fi 7 BE213 160MHz
iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-bz-b0-wh-b0-c101.ucode failed with error -2
iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-bz-b0-wh-b0-100.ucode failed with error -2
iwlwifi 0000:00:14.3: no suitable firmware found!
iwlwifi 0000:00:14.3: minimum version required: iwlwifi-bz-b0-wh-b0-100
iwlwifi 0000:00:14.3: maximum version supported: iwlwifi-bz-b0-wh-b0-c101
```

**Cause.** The `linux-firmware` (specifically the `linux-firmware-intel` split package) shipped on the install media predates the ucode revision the running driver will accept for that card. With no other NIC in the laptop this is a chicken-and-egg problem: you cannot `pacman -Syu` to fix it because you have no network. A plain `pacman -Syu` can also update every other `linux-firmware-*` split package while leaving `linux-firmware-intel` behind.

> ⚠️ **Risk.** Installing individual packages with `pacman -U` from a stale mirror snapshot creates a partial upgrade. Install a matching kernel and firmware pair, and run a full `pacman -Syu` as soon as you have real network access.

**Fix.**

Get any temporary network first — USB Ethernet dongle, or USB tethering from a phone (`Settings > Personal Hotspot > USB`, the phone appears as a `usb0`/`enp0s...` device that NetworkManager will DHCP automatically). Then:

```bash
sudo pacman -Syu linux linux-firmware linux-firmware-intel
sudo reboot
```

With no network at all, download the packages on another machine and sideload them from a USB stick:

```bash
sudo pacman -U /run/media/$USER/USB/linux-7.1.5.arch1-2-x86_64.pkg.tar.zst
sudo pacman -U /run/media/$USER/USB/linux-firmware-intel-20260622-1-any.pkg.tar.zst
sudo mkinitcpio -P
sudo reboot
```

**Verify.** `journalctl -k | grep iwlwifi` now shows a loaded firmware line, e.g. `loaded firmware version 102.07fca168.0 bz-b0-wh-b0-c102.ucode op_mode iwlmld`, and `nmcli device wifi list` returns networks.

Sources: <https://github.com/basecamp/omarchy/issues/6551>

---

## Restore Wi-Fi after an upgrade leaves NetworkManager pointing at a removed iwd backend

`nm-wifi-backend-iwd-orphaned-after-quattro` · severity: **critical** · frequency: **common** · applies to: `arch`, `desktop`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** After upgrading Omarchy to Quattro (4.x) there is no Wi-Fi at all. The Wi-Fi icon/panel shows nothing, and `nmcli device status` shows the wireless device stuck at `unavailable` forever:

```
DEVICE   TYPE   STATE         CONNECTION
wlp2s0   wifi   unavailable   --
```

`systemctl status iwd` says `Unit iwd.service could not be found.` Meanwhile the kernel log is perfectly healthy — `iwlwifi ... loaded firmware version ...`, `base HW address: ...`, no rfkill block, `WIFI-HW enabled`, `WIFI enabled`.

**Cause.** Older Omarchy (2.x/3.x) drove Wi-Fi with `iwd` and dropped a NetworkManager config fragment selecting it as the Wi-Fi backend (`/etc/NetworkManager/conf.d/wifi_backend.conf` or `10-iwd-backend.conf`, filename varies by era). The Quattro migration removes the `iwd` package but the drop-in survives, so NetworkManager is configured to use a backend daemon that no longer exists on disk. Every Wi-Fi device therefore sits at `unavailable`. The shipped migration only fires when `wpa_supplicant.service` is *masked*; on installs where it was merely `disabled`, the migration exits early and records itself as applied.

> **Audit corrected this record.** Cause is verified: omarchy migrations/1786567036.sh does exit early unless wpa_supplicant.service is literally masked (`[[ $state == masked* ]] || exit 0`), and install/hardware/network.sh only does `systemctl disable iwd.service`. But the fix greps only /etc/NetworkManager/conf.d/ while `wifi.backend` is equally often set in /etc/NetworkManager/NetworkManager.conf itself or in /usr/lib/NetworkManager/conf.d/, and it then hardcodes `mv .../wifi_backend.conf{,.bak}` which aborts with 'No such file' on the installs where the drop-in is named 10-iwd-backend.conf. It also never verifies wpa_supplicant can actually be D-Bus-activated.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting rather than renaming the drop-in loses any other device settings it contained. Keep the `.bak` until Wi-Fi is confirmed working.

**Fix.**

```bash
# 1. Find every place the backend can be pinned, not just conf.d
grep -rn 'wifi\.backend' /etc/NetworkManager/ /usr/lib/NetworkManager/ 2>/dev/null

# 2. Move aside whichever drop-in(s) matched, by their real names
for f in $(grep -rls 'wifi\.backend' /etc/NetworkManager/conf.d/ 2>/dev/null); do
  sudo mv -v "$f" "$f.bak"
done
# If the setting is in /etc/NetworkManager/NetworkManager.conf instead, comment it out:
sudo sed -i 's/^\s*wifi\.backend\s*=/#&/' /etc/NetworkManager/NetworkManager.conf

# 3. Make sure the supplicant is installed and unmasked (NM D-Bus-activates it)
pacman -Q wpa_supplicant || sudo pacman -Syu --needed wpa_supplicant
sudo systemctl unmask wpa_supplicant.service
sudo systemctl unmask --runtime wpa_supplicant.service 2>/dev/null || true

sudo systemctl restart NetworkManager
nmcli device status
```

Only if a saved profile is still pinned to the old iwd-era interface name:

```bash
nmcli -g NAME,TYPE connection show | grep wifi
sudo nmcli connection modify "<profile>" connection.interface-name ""
sudo nmcli connection up "<profile>"
```

**Verify.** `nmcli device status` shows the Wi-Fi device as `disconnected` (not `unavailable`), and `nmcli device wifi list` returns access points. `systemctl status wpa_supplicant` shows it D-Bus activated on demand.

Sources: <https://github.com/basecamp/omarchy/issues/7323> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/network.sh> · <https://man.archlinux.org/man/NetworkManager.conf.5>

---

## Repair /etc/resolv.conf after an update repoints it at systemd-resolved

`resolv-conf-symlink-clobbered-by-update` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `manjaro`, `omarchy`

**Symptom.** DNS stops working right after a system update. Nothing resolves — browsers fail, `ping google.com` says `Temporary failure in name resolution` — but IP addresses still ping fine. `ls -l /etc/resolv.conf` shows it is now a symlink to `/run/systemd/resolve/stub-resolv.conf` on a machine that uses NetworkManager's own resolver and has `systemd-resolved` disabled.

**Cause.** The update replaced the `resolv.conf` symlink with the systemd-resolved layout without checking whether `systemd-resolved` is actually enabled. The symlink target does not exist (or the stub listener is not running), so every lookup fails.

> **Audit corrected this record.** Layout A is correct and complete. Layout B is not: it never removes or overrides the `[main] dns=systemd-resolved` setting that layout A creates and that Omarchy ships by default, and it does not remove /etc/NetworkManager/conf.d/20-omarchy-dns.conf. With `dns=systemd-resolved` still in effect, NetworkManager pushes resolvers into resolved and does not populate /run/NetworkManager/resolv.conf, so the new symlink points at a file that stays empty or absent and DNS is still dead. It should also stop the leftover stub listener cleanly.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting `/etc/resolv.conf` while it is a regular file loses hand-written nameservers. Copy it first: `sudo cp -a /etc/resolv.conf /root/resolv.conf.bak`.

**Fix.**

**A — you want systemd-resolved (the Omarchy 4.x default):** as written in the record, it is correct.

**B — you want NetworkManager to manage resolv.conf itself:**

```bash
sudo systemctl disable --now systemd-resolved

# Tell NetworkManager to stop handing DNS to resolved (this step is the missing one)
sudo rm -f /etc/NetworkManager/conf.d/10-dns.conf /etc/NetworkManager/conf.d/20-omarchy-dns.conf
sudo tee /etc/NetworkManager/conf.d/10-dns.conf >/dev/null <<'EOF'
[main]
dns=default
rc-manager=unmanaged
EOF

sudo rm -f /etc/resolv.conf
sudo ln -s /run/NetworkManager/resolv.conf /etc/resolv.conf
sudo systemctl restart NetworkManager

# verify
ls -l /etc/resolv.conf && cat /etc/resolv.conf     # must list your real nameservers
getent hosts archlinux.org
```

If `/run/NetworkManager/resolv.conf` does not exist after the restart, NetworkManager is still using a non-default dns backend — re-check /etc/NetworkManager/conf.d/ and NetworkManager.conf for a `dns=` line.

**Verify.** `resolvectl status` (layout A) shows a running resolver with DNS servers per link, or `cat /etc/resolv.conf` (layout B) lists real nameservers. `getent hosts archlinux.org` returns an address.

Sources: <https://github.com/basecamp/omarchy/issues/2710> · <https://man.archlinux.org/man/systemd-resolved.service.8> · <https://man.archlinux.org/man/NetworkManager.conf.5>

---

## Restart systemd-resolved when a mid-upgrade DNS failure stops pacman

`resolved-inactive-breaks-upgrade-dns` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `omarchy`

**Symptom.** An Omarchy Quattro upgrade dies partway through with pacman unable to resolve anything:

```
:: Checking for remaining system package updates
error: failed retrieving file 'core.db' from stable-mirror.omarchy.org : Could not resolve host: stable-mirror.omarchy.org
error: failed to synchronize all databases (failed to retrieve some files)

Upgrade incomplete - do NOT reboot.
```

`/etc/resolv.conf` is the expected symlink to `/run/systemd/resolve/stub-resolv.conf`, but `systemctl status systemd-resolved` shows it `inactive (dead)`.

**Cause.** The upgrade migration restarts `systemd-resolved` with `|| true`, so a failed restart is silently swallowed and the pipeline continues. With resolved down, the stub-resolv.conf symlink target does not exist and every subsequent step — including the pacman database sync — has no DNS. Non-standard conditions (ext4 root instead of btrfs so snapshot steps failed, an unmounted EFI partition) make the failed restart more likely.

> ⚠️ **Risk.** Rebooting while the upgrade reports "Upgrade incomplete - do NOT reboot" can leave a partially migrated system with mismatched boot config. Finish the upgrade before rebooting.

**Fix.**

```bash
sudo systemctl enable --now systemd-resolved
resolvectl status | head -20
getent hosts stable-mirror.omarchy.org
```

Then resume the upgrade rather than rebooting into a half-migrated system:

```bash
sudo pacman -Syu
omarchy update
```

If resolved refuses to start, get DNS back long enough to finish by writing a static resolv.conf:

```bash
sudo rm /etc/resolv.conf
printf 'nameserver 1.1.1.1\nnameserver 9.9.9.9\n' | sudo tee /etc/resolv.conf
```

…and restore the symlink afterwards with `sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf`.

**Verify.** `systemctl is-active systemd-resolved` prints `active`, `getent hosts stable-mirror.omarchy.org` resolves, and the upgrade completes without further `Could not resolve host` errors.

Sources: <https://github.com/basecamp/omarchy/issues/8395>

---

## Get past airport/hotel captive portals blocked by forced DNS and DNS-over-TLS

`captive-portal-never-loads-forced-dns` · severity: **high** · frequency: **very-common** · applies to: `arch`, `laptop`, `omarchy`, `wayland`

**Symptom.** Repeated failures on airport, hotel and university Wi-Fi: you associate fine, the portal sometimes appears, but after clicking through nothing loads. `http://captive.apple.com` and `http://example.com` cannot be reached. Public IPs ping fine — it is purely DNS. Setting `nameserver 1.1.1.3` in `/etc/resolv.conf` by hand does not help either.

**Cause.** Omarchy's DNS helper writes a hard `DNS=` list plus `DNSOverTLS=opportunistic` into `/etc/systemd/resolved.conf` and a global-DNS override into `/etc/NetworkManager/conf.d/20-omarchy-dns.conf`. Captive portals work by hijacking plain DNS on port 53 and only whitelisting the portal host; a pinned upstream resolver reached over TLS on port 853 is simply blocked before you authenticate, so the portal redirect never happens and no name ever resolves.

> **Audit corrected this record.** Cause verified against bin/omarchy-dns: it does write `DNS=...#cloudflare-dns.com` plus `DNSOverTLS=opportunistic` to /etc/systemd/resolved.conf and a `[global-dns-domain-*] servers=` block to /etc/NetworkManager/conf.d/20-omarchy-dns.conf, and `omarchy dns DHCP` is a real, correctly-spelled invocation that writes exactly the `[Resolve]\nDNSOverTLS=no` shown. The manual fallback is incomplete in a way that leaves the user still broken: omarchy-dns also runs `set_connection_dns`, which stamps `ipv4.ignore-auto-dns yes` + `ipv4.dns 1.1.1.1 1.0.0.1` (and the IPv6 equivalents) onto EVERY wifi/ethernet profile. Deleting the two global files does not undo that, so the portal still cannot hijack DNS.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Preferred — the helper clears all three layers:

```bash
omarchy dns DHCP          # Omarchy 4.x (Quattro)
```

Manual equivalent, if the helper is unavailable — note the third step, which the global files alone do not cover:

```bash
# 1. global NetworkManager override
sudo rm -f /etc/NetworkManager/conf.d/20-omarchy-dns.conf

# 2. resolved's pinned upstream + DoT
sudo tee /etc/systemd/resolved.conf >/dev/null <<'EOF'
[Resolve]
DNSOverTLS=no
EOF

# 3. per-profile DNS that omarchy-dns also wrote onto every wifi/ethernet profile
while IFS=: read -r uuid type; do
  case "$type" in 802-11-wireless|802-3-ethernet)
    sudo nmcli connection modify "$uuid" \
      ipv4.ignore-auto-dns no ipv4.dns "" \
      ipv6.ignore-auto-dns no ipv6.dns "" ;;
  esac
done < <(nmcli -t -f UUID,TYPE connection show)

sudo systemctl restart systemd-resolved NetworkManager
```

Then force the portal open:

```bash
resolvectl status | grep -A3 'Link.*wlan0'   # DNS Servers must now be the AP's address
xdg-open http://neverssl.com
```

Switch back afterwards with `omarchy dns Cloudflare`.

**Verify.** `resolvectl status` shows the link's DNS server as the local gateway and `DNSOverTLS=no`; `curl -sI http://neverssl.com` returns a 302 to the portal.

Sources: <https://github.com/basecamp/omarchy/issues/1841> · <https://github.com/basecamp/omarchy/issues/3445> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-dns>

---

## Recover a MediaTek MT7921/MT7922 Wi-Fi card that is dead after suspend

`mt7921e-dead-after-suspend-aspm` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Wi-Fi works fine from a cold boot, but after the first suspend/resume the card is gone — no networks in the list, `nmcli device` shows the interface as unavailable or it disappears entirely, and only a reboot brings it back. The journal shows `mt7921e 0000:24:00.0: PM: failed to resume async: error -110`, `mt7921e 0000:24:00.0: PM: dpm_run_callback(): pci_pm_resume+0x0/0xf0 returns -110` and `Message 00020007 (seq 8) timeout`, or on some machines `mt7921e 0000:2e:00.0: Unable to change power state from D3cold to D0, device inaccessible`. Often accompanied by `driver own failed` / `chip reset failed`. These cards are also branded AMD RZ608 (MT7921) and RZ616 (MT7922).

**Cause.** The mt7921e driver leaves PCIe Active State Power Management (and L1 substates) enabled across suspend. On many consumer boards and laptops the card cannot be brought back out of D3cold, so the resume callback times out with -110 and the device is left inaccessible on the bus. The Arch wiki documents disabling ASPM as the only fix for the related high-latency problem on the same chipsets, and the upstream driver exposes exactly one knob for it. On some machines the real trigger is that the firmware only offers s2idle rather than real S3, in which case a BIOS update plus `mem_sleep_default=deep` fixes it outright.

> ⚠️ **Risk.** `mem_sleep_default=deep` on a machine whose firmware does not properly implement S3 can cause the laptop to suspend and never wake, or to wake with the fans at full speed — test it interactively before you rely on it, and be prepared to hold the power button. Adding a bad kernel-parameter drop-in and running `limine-mkinitcpio` rewrites your boot entries; keep the Limine menu reachable (do not enable Direct Boot) so you can edit the entry if the machine will not come back.

**Fix.**

First check what the card is and how the machine suspends:

```bash
lspci -knn | grep -A3 -i network
cat /sys/power/mem_sleep          # [s2idle] means no real S3
journalctl -kb | grep -i mt7921
```

Step 1 — disable ASPM for the driver:

```bash
sudo tee /etc/modprobe.d/mt7921e.conf >/dev/null <<'EOF'
options mt7921e disable_aspm=1
EOF

sudo modprobe -r mt7921e && sudo modprobe mt7921e
```

The option is real: `mt76/mt7921/pci.c` declares `module_param_named(disable_aspm, mt7921_disable_aspm, bool, 0644)`. Confirm it took:

```bash
cat /sys/module/mt7921e/parameters/disable_aspm   # expect Y or 1
```

Step 2 — if that alone does not survive a suspend cycle, unload and reload the module around sleep. Create a systemd sleep hook (this is the workaround the Arch forum thread settled on):

```bash
sudo tee /usr/lib/systemd/system-sleep/mt7921e >/dev/null <<'EOF'
#!/usr/bin/env bash
case "$1" in
  pre)
    modprobe -r mt7921e
    ;;
  post)
    modprobe mt7921e
    ;;
esac
EOF
sudo chmod +x /usr/lib/systemd/system-sleep/mt7921e
```

Everything executable in `/usr/lib/systemd/system-sleep/` is run by systemd-sleep with `pre`/`post` as `$1`. Test with `systemctl suspend`, then `journalctl -b -u systemd-suspend.service`.

Step 3 — if `/sys/power/mem_sleep` reports only `[s2idle]`, update the BIOS first, then force real S3. On Omarchy 4, kernel parameters go in a limine-entry-tool drop-in, not by hand-editing `/boot/limine.conf` (which `omarchy-refresh-limine` resets):

```bash
sudo mkdir -p /etc/limine-entry-tool.d
echo 'KERNEL_CMDLINE[default]+=" mem_sleep_default=deep"' \
  | sudo tee /etc/limine-entry-tool.d/deep-sleep.conf
sudo limine-mkinitcpio
```

On plain Arch with GRUB, add `mem_sleep_default=deep` to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` and run `sudo grub-mkconfig -o /boot/grub/grub.cfg`.

As a one-off recovery without rebooting:

```bash
sudo modprobe -r mt7921e && sudo modprobe mt7921e
sudo systemctl restart NetworkManager bluetooth
```

**Verify.** Run `systemctl suspend`, resume, then `nmcli device status` — the wlan device should be `connected` or `disconnected`, never `unavailable`. `journalctl -kb | grep -i mt7921` should show no `error -110`, no `driver own failed` and no `D3cold` message after the resume timestamp. `cat /sys/module/mt7921e/parameters/disable_aspm` should print `Y`.

Sources: <https://wiki.archlinux.org/title/Network_configuration/Wireless> · <https://bbs.archlinux.org/viewtopic.php?id=295916> · <https://bbs.archlinux.org/viewtopic.php?id=284180> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/mediatek/mt76/mt7921/pci.c> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-hibernation-setup>

---

## Fix the Wi-Fi password prompt that never appears on Hyprland

`no-secret-agent-wifi-password-prompt-never-appears` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Clicking a secured network in the bar does nothing — no password dialog ever opens and the connection silently fails. From the terminal: `Error: Connection activation failed: (7) Secrets were required, but not provided`. The journal shows `no secrets: No agents were available for this request.` or `Failed to request VPN secrets #1: No agents were available for this request.` Anything else that needs elevation (mounting a disk in a file manager, `pkexec`) also fails without prompting.

**Cause.** NetworkManager does not prompt for Wi-Fi secrets itself. Unless the passphrase is stored in the profile, it asks a registered *secret agent* in your session for it, and if none has registered it gives up immediately with error 7 and logs `no secrets: No agents were available for this request.` A full desktop environment's shell provides one; a bare Hyprland session provides neither a secret agent nor a polkit authentication agent unless you start one. Omarchy 4 is a third case, and it is not the same mechanism: it registers **no** NetworkManager secret agent at all. Its network panel (part of the `omarchy-shell` Quickshell process that also draws the bar) collects the passphrase in its own dialog and passes it straight to `nmcli`, and a separate Quickshell plugin provides the **polkit** agent for `pkexec` and friends. Both live in that one process, so if `omarchy-shell` has crashed or is restart-looping you lose the Wi-Fi dialog and every privilege prompt on the machine together — but you will not see the NetworkManager "no agents" error from clicking the bar, because the bar never asked NetworkManager for secrets in the first place. You get that error from `nmcli` without `--ask`, from a VPN plugin, or on a bare Hyprland session with no agent running. Note also that Omarchy 4 retires the standalone `hyprpolkitagent.service` user unit during the Quattro upgrade, so a stale enabled copy of it is not what is answering.

> **Audit corrected this record.** The problem is real and the generic Arch half is verbatim-correct, but three Omarchy 4 / Hyprland 4 specifics are fabricated, and the cause conflates two different agents. Checked on the live Omarchy 4.0.0 install. (1) `omarchy-shell.service` does not exist as a user unit — `systemctl --user cat omarchy-shell.service` returns "No files found", there is no such file in /usr/lib/systemd/user, and worse, `omarchy-shell.service` is listed in the `retired_user_units` array of /usr/bin/omarchy-upgrade-to-quattro and actively deleted from ~/.config/systemd/user. The shell is started from Hyprland's autostart (`hl.exec_cmd("omarchy-launch-shell")` in /usr/share/omarchy/default/hypr/autostart.lua) and restarted with `omarchy-restart-shell` (`omarchy restart shell`). (2) `hl.exec_once(...)` is not a Hyprland Lua API. The hyprland-wiki page content/configuring/core/autostart.md shows the only documented form is `hl.on("hyprland.start", function() hl.exec_cmd("...") end)`, and `strings /usr/bin/Hyprland` on 0.56 has `exec_cmd` but no `exec_once` (only the legacy hyprlang keyword `exec-once`). (3) `busctl --user list | grep -i polkit` is a false-negative diagnostic: on this healthy machine, with the Quickshell polkit plugin loaded (/usr/share/omarchy/shell/plugins/polkit/PolkitAgent.qml, `import Quickshell.Services.Polkit`), that command matches nothing, so it would tell a user their agent is dead when it is fine. (4) The cause is wrong about mechanism. A NetworkManager *secret agent* (org.freedesktop.NetworkManager.AgentManager) and a *polkit* agent are different things; Omarchy 4 ships the latter but registers no secret agent — its network panel collects the passphrase itself and hands it to nmcli (see /usr/share/omarchy/shell/plugins/panels/network/Model.js, which builds `nmcli connection add ... | nmcli connection edit uuid ...` with the password on stdin). Verified as correct and kept: the error strings (Arch wiki NetworkManager: "If you make neither of these available, then authentication will fail with the error `no secrets: No agents were available for this request.`", and the i3 warning uses the same string); `nmcli --ask` and `nmtui` as their own agents; `psk-flags 0` = stored by NetworkManager in cleartext under /etc/NetworkManager/system-connections plus that danger note; the polkit rules snippet, which is character-for-character the wiki's 50-org.freedesktop.NetworkManager.rules with `subject.isInGroup("network")`; the Hyprland wiki listing an Authentication Agent under Must-have with "Starting method: manual (autostart in config)" and hyprpolkitagent's own page giving `systemctl --user start hyprpolkitagent` in autostart and `systemctl --user enable --now hyprpolkitagent.service` under uwsm; and the claim that Quattro retires hyprpolkitagent.service, which is true (it heads the retired_user_units list).
>
> *The Cause above was rewritten on 2026-09-01 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `psk-flags 0` writes the passphrase in clear text into `/etc/NetworkManager/system-connections/<name>.nmconnection`, readable by root and by anything that can read that directory. That is the normal Arch default, but do not do it for shared machines or for corporate credentials. The polkit rules file grants every member of `network` unprompted control over all NetworkManager settings including VPN configuration — only add users you would give sudo to.

**Fix.**

Confirm the diagnosis rather than guessing at the password:

```bash
journalctl -u NetworkManager -b --no-pager | grep -i 'secret\|agent' | tail -20
pkexec true          # should raise a password dialog; fails silently if no polkit agent
```

Do not use `busctl --user list | grep -i polkit` as the test — a working Quickshell or hyprpolkitagent agent owns no name on the user bus, so that matches nothing even on a healthy machine.

**Immediate workaround — no agent needed.** `nmcli` can be its own agent with `--ask`, and `nmtui` prompts in the terminal:

```bash
nmcli --ask device wifi connect "<SSID>"
# or
nmtui
```

**Omarchy 4.** The network panel and the polkit dialog both live in the `omarchy-shell` Quickshell process. There is no `omarchy-shell.service` user unit — Quattro retires that name — so check and restart it this way:

```bash
pgrep -af quickshell                              # is the shell alive?
journalctl --user -t omarchy-shell -b | tail -40  # why it died, if it did
omarchy-restart-shell                             # same as: omarchy restart shell
```

`omarchy-restart-shell` is deliberately careful about the lock screen; prefer it over killing the process by hand.

If a leftover pre-Quattro unit is still enabled and fighting it, clear it (this is exactly what the Quattro upgrade's own cleanup does):

```bash
systemctl --user disable --now hyprpolkitagent.service 2>/dev/null
rm -f ~/.config/systemd/user/hyprpolkitagent.service
systemctl --user daemon-reload
```

**Bare Hyprland / plain Arch.** Install and autostart an agent. The Hyprland wiki lists an authentication agent under "must have" with its starting method as manual, via an autostart entry in the config:

```bash
sudo pacman -S --needed hyprpolkitagent
```

Hyprland 0.55+ config is Lua, and there is no `exec-once` equivalent function — autostart is an event handler. In `~/.config/hypr/hyprland.lua`:

```lua
hl.on("hyprland.start", function()
  hl.exec_cmd("systemctl --user start hyprpolkitagent")
end)
```

If you launch Hyprland through uwsm, enable it as a proper user unit instead and drop the autostart line:

```bash
systemctl --user enable --now hyprpolkitagent.service
```

Note that a polkit agent alone does not make NetworkManager stop reporting "no agents" — that error wants a *secret* agent. On a bare Hyprland session, either use `nmcli --ask` / `nmtui`, run a front-end that registers one (`nm-applet`, `networkmanager-dmenu`), or store the secret as below.

**Make the Wi-Fi password not need an agent at all.** Store it in the connection profile rather than in a keyring, so NetworkManager itself owns it (secret flag `0` = stored by NetworkManager):

```bash
nmcli connection modify "<SSID>" 802-11-wireless-security.psk-flags 0
nmcli connection modify "<SSID>" 802-11-wireless-security.psk '<password>'
nmcli connection up "<SSID>"
```

**If the prompt appears but is refused**, it is polkit authorisation rather than agent absence. Add yourself to `network` and grant it:

```bash
sudo usermod -aG network "$USER"
sudo tee /etc/polkit-1/rules.d/50-org.freedesktop.NetworkManager.rules >/dev/null <<'EOF'
polkit.addRule(function(action, subject) {
  if (action.id.indexOf("org.freedesktop.NetworkManager.") == 0 && subject.isInGroup("network")) {
    return polkit.Result.YES;
  }
});
EOF
```

Log out and back in for the group change to take effect.

**Verify.** `nmcli device wifi connect "<SSID>"` on a network whose password is not yet stored should pop a graphical prompt. `busctl --user list | grep -i polkit` shows an agent on the bus. `pkexec true` should prompt rather than fail silently.

Sources: <https://wiki.archlinux.org/title/NetworkManager> · <https://wiki.hypr.land/Useful-Utilities/Must-have/> · <https://wiki.hypr.land/Hypr-Ecosystem/hyprpolkitagent/> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-upgrade-to-quattro>

---

## Re-enable Wi-Fi that is soft-blocked by rfkill

`wifi-soft-blocked-rfkill` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Wi-Fi vanishes for no reason — the panel shows no networks, `nmcli device status` shows the wireless device as `unavailable`, and `nmcli radio wifi` prints `disabled`. It usually starts after an airplane-mode key press, a lid close, or a suspend/resume cycle.

**Cause.** A software rfkill block is set on the wireless (or all) radio types. Kernel drivers, laptop hotkey handlers (`thinkpad_acpi`, `dell-laptop`, `asus-wmi`) and NetworkManager itself can set it; nothing clears it automatically.

> **Audit corrected this record.** The diagnosis and the main sequence are exactly right — verified byte-for-byte against bin/omarchy-restart-wifi, which is `rfkill unblock wifi; nmcli networking on; nmcli radio wifi on; nmcli device wifi rescan; rfkill list wifi`. The last block is wrong and backwards: systemd-rfkill *saves and restores* rfkill state across reboots (that is its whole job — Omarchy's own bin/omarchy-bluetooth-power relies on exactly that to persist a block under /var/lib/systemd/rfkill). Enabling it does not 'unblock every radio at boot'; it makes a soft block sticky across reboots. It is also socket/udev-activated, not something you enable as a .service.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

```bash
rfkill list
sudo rfkill unblock wifi
nmcli networking on
nmcli radio wifi on
nmcli device wifi rescan
```

Or on Omarchy: `omarchy-restart-wifi`

If `Hard blocked: yes`, software cannot clear it — use the physical switch or the Fn airplane-mode key.

Note that `systemd-rfkill` **persists** blocks rather than clearing them: if the radio was soft-blocked at shutdown it is restored blocked at the next boot. If a block keeps coming back across reboots, that is systemd-rfkill restoring saved state — clear it once and shut down cleanly, or drop the saved state:

```bash
sudo rm -f /var/lib/systemd/rfkill/*
```

To force every radio unblocked at each boot regardless of saved state, use a unit of your own:

```bash
sudo tee /etc/systemd/system/rfkill-unblock-all.service >/dev/null <<'EOF'
[Unit]
Description=Unblock all rfkill switches at boot
After=systemd-rfkill.service

[Service]
Type=oneshot
ExecStart=/usr/bin/rfkill unblock all

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now rfkill-unblock-all.service
```

**Verify.** `rfkill list` shows `Soft blocked: no` for the wireless entry, and `nmcli device wifi list` returns access points.

Sources: <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-restart-wifi> · <https://github.com/basecamp/omarchy/issues/1422>

---

## Make a paired Bluetooth keyboard work at the SDDM login screen

`bluetooth-keyboard-dead-at-login-screen` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** A paired and trusted Bluetooth keyboard or mouse does not work at the SDDM greeter or after logging out. You cannot type your password without plugging in a USB keyboard. Once logged in with a wired keyboard, the Bluetooth one connects normally.

**Cause.** Two things combine: `AutoEnable` is not set in `/etc/bluetooth/main.conf`, so `bluetoothd` leaves the adapter unpowered until a user session turns it on; and `sddm.service` starts concurrently with `bluetooth.service` with no ordering constraint, so the greeter is already up before any adapter exists. Sleeping BLE HID devices also need `FastConnectable` to reconnect quickly enough for the greeter.

> **Audit corrected this record.** The problem is real and the SDDM ordering drop-in is appropriate — Omarchy 4.x does use SDDM (install/login/sddm.sh exists upstream), so that half applies. The defect is the first block: `tee -a` appends a whole new `[Policy]` section to /etc/bluetooth/main.conf, which already ships one (the sibling AutoEnable record documents `[Policy] AutoEnable=false` living there). main.conf is parsed as a GKeyFile, and a duplicated group with a conflicting AutoEnable is at best ambiguous and at worst a parse failure that makes bluetoothd fall back to defaults for the whole file. Edit the existing section in place. `ReconnectAttempts`/`ReconnectIntervals` are `[Policy]` keys and `FastConnectable` is a `[General]` key, so they cannot all go in one appended block anyway.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `FastConnectable=true` keeps the controller in page-scan mode continuously, which increases idle power draw slightly on laptops.

**Fix.**

Edit the existing sections in place instead of appending a second `[Policy]`:

```bash
grep -n -E '^\[|AutoEnable|FastConnectable|ReconnectAttempts|ReconnectIntervals' /etc/bluetooth/main.conf

sudo sed -i \
  -e 's/^[#[:space:]]*AutoEnable[[:space:]]*=.*/AutoEnable=true/' \
  -e 's/^[#[:space:]]*ReconnectAttempts[[:space:]]*=.*/ReconnectAttempts=7/' \
  -e 's/^[#[:space:]]*ReconnectIntervals[[:space:]]*=.*/ReconnectIntervals=1,2,4,8,16,32,64/' \
  -e 's/^[#[:space:]]*FastConnectable[[:space:]]*=.*/FastConnectable=true/' \
  /etc/bluetooth/main.conf

# confirm each landed exactly once, and note which section it is under
grep -n -E '^\[|AutoEnable|FastConnectable|ReconnectAttempts|ReconnectIntervals' /etc/bluetooth/main.conf
sudo systemctl restart bluetooth
systemctl status bluetooth --no-pager    # a parse error here means the file is malformed
```

If a key is genuinely absent, add it under the correct existing header — `AutoEnable`, `ReconnectAttempts`, `ReconnectIntervals` under `[Policy]`; `FastConnectable` under `[General]` — do not append a duplicate section.

The SDDM ordering drop-in and `bluetoothctl trust AA:BB:CC:DD:EE:FF` steps are correct as written.

**Verify.** Reboot to the greeter and type on the Bluetooth keyboard. From a TTY (`Ctrl+Alt+F2`) before logging in, `bluetoothctl show | grep Powered` prints `Powered: yes` and `bluetoothctl info AA:BB:CC:DD:EE:FF` shows `Connected: yes`.

Sources: <https://github.com/basecamp/omarchy/issues/8261>

---

## Recover Intel Wi-Fi that dies after suspend (Failed to run INIT ucode: -110)

`iwlwifi-init-ucode-timeout-after-resume` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `omarchy`, `systemd-boot`

**Symptom.** After waking a laptop from suspend, Wi-Fi is gone. `journalctl -k -b` fills with:

```
iwlwifi 0000:00:14.3: Failed to run INIT ucode: -110
```

repeated dozens of times. Worse: closing the lid again while the driver is stuck in that retry loop makes the second suspend never complete — the machine is completely unresponsive and needs a hard power-off.

**Cause.** The iwlwifi firmware fails to reinitialise on the resume path on some Intel AX-series parts. The driver retries the INIT ucode load indefinitely (-110 is ETIMEDOUT), and a suspend requested while it is mid-retry deadlocks the PM transition.

> **Audit corrected this record.** The problem and approach are real, and /usr/lib/systemd/system-sleep/ is the directory systemd-suspend.service(8) actually documents. Two defects: (a) `tee /etc/modprobe.d/iwlwifi.conf` truncates a file users commonly already own (e.g. the power-save options from the powersave record) — it must not claim that filename; (b) the sleep hook does no cleanup or logging and reloads the module without asking NetworkManager to re-adopt the device, and `modprobe -r` can fail while the link is up. Use a dedicated conf filename and bring the radio down first.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A system-sleep hook runs as root on every suspend. A syntax error in it can delay or abort suspend — test it with `sudo /usr/lib/systemd/system-sleep/iwlwifi.sh pre` before relying on it.

**Fix.**

```bash
sudo tee /usr/lib/systemd/system-sleep/iwlwifi.sh >/dev/null <<'EOF'
#!/bin/bash
case "$1" in
  pre)
    nmcli radio wifi off 2>/dev/null || true
    modprobe -r iwlmvm 2>/dev/null || true
    modprobe -r iwlmld 2>/dev/null || true
    modprobe -r iwlwifi 2>/dev/null || true
    ;;
  post)
    modprobe iwlwifi 2>/dev/null || true
    nmcli radio wifi on 2>/dev/null || true
    ;;
esac
exit 0
EOF
sudo chmod +x /usr/lib/systemd/system-sleep/iwlwifi.sh
```

Disable the INI/debug firmware images in a file of their own so an existing `/etc/modprobe.d/iwlwifi.conf` is not clobbered:

```bash
echo 'options iwlwifi enable_ini=N' | sudo tee /etc/modprobe.d/iwlwifi-enable-ini.conf
sudo reboot
```

Verify after reboot: `cat /sys/module/iwlwifi/parameters/enable_ini` should print `N`.

**Verify.** Suspend and resume twice in a row. `journalctl -k -b | grep -c 'INIT ucode'` returns 0 and `nmcli device status` shows the Wi-Fi device reconnected.

Sources: <https://github.com/basecamp/omarchy/issues/8461> · <https://github.com/basecamp/omarchy/issues/2925>

---

## Stop an NFS share in fstab from hanging boot and shutdown

`nfs-mount-hangs-boot-and-shutdown` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** With an NFS share in `/etc/fstab`, boot stalls for minutes on `A start job is running for /mnt/nas` whenever the server is off or you are away from that network, and shutdown hangs on `A stop job is running for /mnt/nas`. Once the server disappears mid-session, any process touching the mount becomes unkillable in `D` state and `df` hangs.

**Cause.** NFS mounts default to `hard`, meaning NFS requests are retried indefinitely rather than failing — that is the primary cause of NFS-related hangs. In `fstab` a network filesystem is also pulled into `remote-fs.target` as a hard requirement, so systemd blocks boot waiting for it and blocks shutdown trying to unmount a server that is already unreachable.

> **Audit corrected this record.** The diagnosis is accurate — `hard` is the NFS default and does retry indefinitely, and the record correctly notes that `retrans` does not bound a hard mount and that `soft` trades hangs for EIO. The fstab line and options are valid. The activation step is the weak part: `systemctl restart remote-fs.target` is an unreliable way to pick up a newly generated automount unit (targets carry no processes and mounts are only Wanted by them), so users following this often see nothing happen and conclude the fstab entry is wrong. Start the generated automount unit by name.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `soft` NFS mounts can cause silent data corruption — the man page recommends them only when client responsiveness matters more than data integrity. Never use `soft` for a share you write to.

**Fix.**

fstab line as written is correct:

```
nas.local:/export/media  /mnt/nas  nfs4  noauto,nofail,_netdev,x-systemd.automount,x-systemd.idle-timeout=600,x-systemd.mount-timeout=10,timeo=100,retrans=2  0 0
```

Activate it by starting the generated unit explicitly rather than restarting the target:

```bash
sudo systemctl daemon-reload
systemd-escape -p --suffix=automount /mnt/nas     # -> mnt-nas.automount
sudo systemctl start mnt-nas.automount
systemctl status mnt-nas.automount --no-pager
ls /mnt/nas          # triggers the mount on first access
```

To clear a mount that is already wedged (lazy detach is the part that works when the server is gone):

```bash
sudo umount -l /mnt/nas
```

Only add `soft` if you accept that the client returns EIO after `retrans` retransmissions instead of retrying forever — that risks silent data loss on writes, so keep `hard` for anything you write to.

**Verify.** `systemctl list-units 'mnt-nas.*'` shows an `.automount` unit active and the `.mount` unit inactive until first access. Power the server off, then reboot: boot reaches the greeter without stalling, and `systemctl poweroff` completes without a stop job.

Sources: <https://man.archlinux.org/man/nfs.5> · <https://man.archlinux.org/man/systemd.mount.5>

---

## Stop an RTL8111/8168 gigabit NIC from flapping or dropping to 100 Mbps

`r8169-rtl8111-link-flapping-r8168-dkms` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Onboard Realtek ethernet is unreliable: the link goes down and up every minute or so under load, the connection negotiates 100 Mbps instead of 1 Gbps on a cable that works fine elsewhere, or there is a link light but no traffic at all. `lspci` shows `Realtek Semiconductor Co., Ltd. RTL8111/8168/8411 PCI Express Gigabit Ethernet Controller`. The journal shows `Generic FE-GE Realtek PHY r8169-2200:00: Downshift occurred from negotiated speed 1Gbps to actual speed 100Mbps, check cabling!` and `r8169 0000:22:00.0 enp34s0: Link is Up - 100Mbps/Full (downshifted)`, or on worse boards a repeating `enp1s0: pci link is down` and PCIe AER `Uncorrected (Non-Fatal) error received` storms.

**Cause.** The RTL8111/8168 family covers dozens of silicon revisions behind one PCI ID. The in-tree `r8169` driver handles most of them well but some revisions misbehave, usually around PCIe ASPM and Energy Efficient Ethernet: the PHY drops into a low-power state, the link partner does not follow, and the link renegotiates or downshifts. On some mini-PCs and Gigabyte/MSI boards the PCIe root port itself throws AER errors when ASPM is active. This is distinct from the RTL8125 2.5 GbE offload bug, which is a different chip and a different fix.

> **Audit corrected this record.** Nearly everything here checks out against the cited sources and against this Omarchy 4 box. https://wiki.archlinux.org/title/Network_configuration/Ethernet carries the exact two log lines the symptom quotes ("MicroStar Motherboard with Realtek 8111/8168/8411" section), prescribes the `ip link set dev <iface> down/up` bounce verbatim, prescribes the AUR r8168 + blacklist r8169 route for flapping revisions, and documents `iommu=soft` for Gigabyte boards — so the record's "documented remedy" claim is real, not fabricated. bbs.archlinux.org/viewtopic.php?id=285421 is exactly the AER-storm mini-PC case and its accepted answer is literally `r8168.aspm=0 r8168.eee_enable=0 pcie_aspm=off` with r8168-dkms and r8169 blacklisted. I confirmed `aspm` and `eee_enable` are real module_param()s in r8168_n.c (lines 502 and 520), and that `r8168-dkms` exists in the AUR at 8.056.02-1, last updated 2026-02. The Omarchy-specific boot bits are correct for Quattro, not Omarchy 3: /etc/limine-entry-tool.d exists on this machine holding omarchy-defaults.conf and resume.conf, the `KERNEL_CMDLINE[default]+=" ..."` append syntax matches /etc/limine-entry-tool.conf's documented drop-in operator, `sudo limine-mkinitcpio` is precisely what /usr/share/omarchy/migrations/1784917531.sh and 1786482992.sh run after writing such a drop-in, and omarchy-refresh-limine really does overwrite /boot/limine.conf from $OMARCHY_PATH/default/limine/limine.conf, so the warning against hand-editing it is right. NetworkManager-dispatcher.service is enabled here, so the dispatcher hook will fire. ONE REAL GAP: `ethtool` is not installed on Omarchy 4 — `pacman -Q ethtool` returns "package not found" on this machine and `ethtool` appears nowhere in /usr/share/omarchy/install/*.packages. A user copy-pasting the diagnostic block or Step 1 gets "command not found", and the dispatcher script silently no-ops on /usr/bin/ethtool. Corrected fix adds the install and a check that the dispatcher actually took effect. Cause is accurate and stands.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `r8168` is an out-of-tree DKMS module. If it fails to build against a new kernel you boot with no ethernet at all — and because you blacklisted `r8169`, there is no fallback. Always install the matching `linux-headers` before a kernel upgrade, check `dkms status` afterwards, and keep a USB ethernet adapter or working Wi-Fi as a way back in. Try steps 1–3 on the in-tree driver first; most machines never need step 4. `pcie_aspm=off` disables PCIe power management system-wide and will measurably shorten laptop battery life — prefer the per-driver `r8168 aspm=0` where it is sufficient.

**Fix.**

**Step 0 — install `ethtool`.** Omarchy 4 does not ship it (it is not in `omarchy-base.packages`), so every command below fails with `command not found` without this:

```bash
sudo pacman -S --needed ethtool
```

Identify the exact revision and the bound driver:

```bash
lspci -nnk | grep -A3 -i ethernet
sudo ethtool <iface> | grep -E 'Speed|Duplex|Link detected'
sudo ethtool --show-eee <iface>
journalctl -kb | grep -iE 'r8169|r8168|downshift|aer'
```

**Step 1 — turn off EEE on the in-tree driver.** This alone fixes the flapping on many boards and costs you nothing but a fraction of a watt:

```bash
sudo ethtool --set-eee <iface> eee off
```

Test for a few minutes, then make it persistent with a NetworkManager dispatcher script:

```bash
sudo tee /etc/NetworkManager/dispatcher.d/50-realtek-eee >/dev/null <<'EOF'
#!/bin/bash
IFACE="$1"
ACTION="$2"
case "$IFACE" in en*|eth*) ;; *) exit 0 ;; esac
if [ "$ACTION" = "up" ]; then
  /usr/bin/ethtool --set-eee "$IFACE" eee off || true
fi
EOF
sudo chmod 755 /etc/NetworkManager/dispatcher.d/50-realtek-eee
sudo systemctl enable --now NetworkManager-dispatcher.service
```

Confirm it actually ran after the next link event, rather than assuming it did:

```bash
sudo nmcli device disconnect <iface> && sudo nmcli device connect <iface>
sudo ethtool --show-eee <iface>      # must still report EEE disabled
journalctl -u NetworkManager-dispatcher -n 20
```

**Step 2 — if the log shows `pci link is down` or AER errors, disable ASPM.** On Omarchy 4, kernel parameters go into a limine-entry-tool drop-in (hand edits to `/boot/limine.conf` are reset by `omarchy-refresh-limine`, which copies the packaged default over it):

```bash
sudo mkdir -p /etc/limine-entry-tool.d
echo 'KERNEL_CMDLINE[default]+=" pcie_aspm=off"' \
  | sudo tee /etc/limine-entry-tool.d/realtek-aspm.conf
sudo limine-mkinitcpio
sudo reboot
```

After the reboot, check the parameter actually made it into the booted command line — Omarchy builds a UKI, so a drop-in that was written without a rebuild will not be in effect:

```bash
grep -o 'pcie_aspm=off' /proc/cmdline
```

On plain Arch with GRUB, add `pcie_aspm=off` to `GRUB_CMDLINE_LINUX_DEFAULT` and run `sudo grub-mkconfig -o /boot/grub/grub.cfg`. On some Gigabyte boards (the wiki's example is the GA-990FXA-UD3) `iommu=soft` is the documented remedy instead.

**Step 3 — as a one-off recovery** when it has already downshifted, bounce the link:

```bash
sudo ip link set dev <iface> down
sudo ip link set dev <iface> up
```

**Step 4 — only if the in-tree driver still cannot hold a link**, switch to Realtek's out-of-tree driver:

```bash
yay -S linux-headers r8168-dkms

echo 'blacklist r8169' | sudo tee /etc/modprobe.d/blacklist-r8169.conf
sudo tee /etc/modprobe.d/r8168.conf >/dev/null <<'EOF'
options r8168 aspm=0 eee_enable=0
EOF

sudo dkms status                 # must show r8168 installed for your kernel
sudo mkinitcpio -P
sudo reboot
```

After the reboot, `lspci -k` should show `Kernel driver in use: r8168`. The `aspm=0 eee_enable=0` combination (with `pcie_aspm=off` on the cmdline) is what fixed the AER-storm case on affected mini-PCs.

**Verify.** `sudo ethtool <iface> | grep -E 'Speed|Link detected'` reports `1000Mb/s` and `yes`. `sudo ethtool --show-eee <iface>` shows EEE disabled. Then hold it under load: `ping -i 0.2 -c 600 <router-ip>` alongside a large transfer should complete with no loss, and `journalctl -kf | grep -iE 'r816|link is'` should stay silent for the duration.

Sources: <https://wiki.archlinux.org/title/Network_configuration/Ethernet> · <https://bbs.archlinux.org/viewtopic.php?id=285421> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-hibernation-setup>

---

## Restore VPN split DNS broken by a global DNS= in resolved.conf

`resolved-dns-override-breaks-vpn-split-dns` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** After connecting a corporate VPN (FortiClient, SonicWall Connect Tunnel, OpenVPN, AnyConnect), internal hostnames do not resolve and internal services are unreachable, even though the tunnel is up and routes exist. Adding entries to `/etc/hosts` reaches those specific hosts, proving routing works and only DNS is broken. `resolvectl status` shows the VPN's nameservers missing from the Global section.

**Cause.** Omarchy writes an explicit `DNS=` (and `FallbackDNS=`) into `/etc/systemd/resolved.conf`. A statically configured global `DNS=` takes precedence over anything a VPN client pushes, and clients that simply replace the `/etc/resolv.conf` symlink with a static file are ignored entirely because `resolv.conf` points at systemd-resolved's stub (`127.0.0.53`), not at the real resolvers.

> **Audit corrected this record.** The diagnosis is right — a static global `DNS=` in resolved.conf does outrank per-link DNS pushed by a VPN — and the `resolvectl dns/domain/revert` split-DNS recipe is correct, including `'~.'` for default-route-all-queries. Same defect as the captive-portal record: `omarchy dns Cloudflare/Google/Custom` also writes `ipv4.ignore-auto-dns yes` + explicit `ipv4.dns`/`ipv6.dns` onto every wifi and ethernet profile (verified in bin/omarchy-dns `set_connection_dns`), and clearing only resolved.conf and 20-omarchy-dns.conf leaves those per-profile servers in place, so internal names still will not resolve.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Overwriting `/etc/systemd/resolved.conf` discards any other Resolve settings you had (DNSSEC, MulticastDNS, custom FallbackDNS). Back it up first: `sudo cp /etc/systemd/resolved.conf{,.bak}`.

**Fix.**

```bash
# global resolved override
sudo tee /etc/systemd/resolved.conf >/dev/null <<'EOF'
[Resolve]
DNSOverTLS=no
EOF

# global NetworkManager override
sudo rm -f /etc/NetworkManager/conf.d/20-omarchy-dns.conf

# per-profile DNS pins that omarchy-dns also set (this step is required)
while IFS=: read -r uuid type; do
  case "$type" in 802-11-wireless|802-3-ethernet)
    sudo nmcli connection modify "$uuid" \
      ipv4.ignore-auto-dns no ipv4.dns "" \
      ipv6.ignore-auto-dns no ipv6.dns "" ;;
  esac
done < <(nmcli -t -f UUID,TYPE connection show)

sudo systemctl restart systemd-resolved NetworkManager
resolvectl status        # Global should now have no DNS Servers
```

On Omarchy 4.x, `omarchy dns DHCP` does all three of the above in one command.

For a client that never registers its DNS with resolved, wire split DNS by hand once the tunnel is up:

```bash
sudo resolvectl dns tun0 10.0.0.53 10.0.0.54
sudo resolvectl domain tun0 '~corp.example.com' '~internal'
sudo resolvectl flush-caches
resolvectl status tun0
```

Use `'~.'` as the domain to send every lookup down the tunnel. `sudo resolvectl revert tun0` undoes it.

**Verify.** `resolvectl status tun0` lists the VPN nameservers and the `~corp.example.com` routing domain; `resolvectl query intranet.corp.example.com` returns the internal address and reports it was resolved via `tun0`.

Sources: <https://github.com/basecamp/omarchy/issues/1509> · <https://github.com/basecamp/omarchy/issues/4853> · <https://man.archlinux.org/man/systemd-resolved.service.8> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-dns>

---

## Stabilise a Realtek RTL8821CE or RTL8822CE that keeps dropping or crawls

`rtw88-rtl8821ce-unstable-disable-aspm` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Wi-Fi on an RTL8821CE / RTL8822BE / RTL8822CE (very common in budget HP, Lenovo and Asus laptops) connects but is unusable — a few hundred kbit/s, pings jumping to seconds, the link dropping every couple of minutes and reconnecting, or the card going dead after a resume. `lspci -k` shows `Kernel driver in use: rtw88_8821ce`. Users describe it as "my Wi-Fi works on Windows but is unusable on Arch".

**Cause.** The in-kernel rtw88 driver enables PCIe ASPM and the deep low-power-save mode on hardware whose platform implementation is broken, so the link stalls, crawls or dies after resume. Upstream `rtw88/pci.c` carries a DMI quirk table (`rtw_pci_quirks[]`) that force-disables ASPM and deep LPS, but it has only two entries — "HP Notebook - P3S95EA#ACB" and "ASUS TUF Gaming A15 FA506II" — so every other affected machine has to set the module parameter by hand. The driver also force-disables ASPM at runtime for an 8821C sitting behind an Intel PCIe bridge (`rx_no_aspm`), which is why the same chip misbehaves on some boards and not others. This is the rtw88 sibling of the already-documented rtw89 problem; rtw88 covers the older Realtek PCIe parts (8821CE, 8822BE, 8822CE and the 802.11n 8723DE) while rtw89 covers the Wi-Fi 6 ones.

> **Audit corrected this record.** The fix is exactly right and I verified every module and parameter name against the cited kernel sources rather than from memory. drivers/net/wireless/realtek/rtw88/pci.c lines 20-23 declare `module_param_named(disable_msi, ...)` and `module_param_named(disable_aspm, rtw_pci_disable_aspm, bool, 0644)`; main.c line 38 declares `module_param_named(disable_lps_deep, rtw_disable_lps_deep_mode, bool, 0644)`. The rtw88 Makefile confirms main.o builds into `rtw88_core` and pci.o into `rtw88_pci`, and that `rtw88_8821ce`, `rtw88_8822ce`, `rtw88_8822be` and `rtw88_8723de` are real module names — so /etc/modprobe.d/70-rtw88.conf as written is correct, and the sysfs paths in the verify step exist. `rtl8821ce-dkms-git` and `rtw88-dkms-git` both exist in the AUR. Nothing here is Omarchy-3 shaped and the `yay -S` note correctly avoids a bare pacman upgrade. THE CAUSE IS WRONG ON A CHECKABLE SPECIFIC: it says the upstream DMI quirk table "only lists a handful of HP models". `rtw_pci_quirks[]` in pci.c has exactly TWO entries — "HP Notebook - P3S95EA#ACB" and "ASUS TUF Gaming A15 FA506II" — so it is two machines from two vendors, not a handful of HP models. That is precisely the kind of invented specific that reads more authoritative than the text around it. Two smaller points folded into the corrected text: the RTL8723DE is 802.11n, not a Wi-Fi 5 part; and pci.c also carries a narrower runtime workaround (`rx_no_aspm` for 8821C behind an Intel bridge) worth knowing about. Finally, `rtl8821ce-dkms-git` was last updated 2023-01 per the AUR RPC, which is a real build risk against a 7.x kernel and belongs in the text rather than only implied by the danger note.
>
> *The Cause above was rewritten on 2026-09-01 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Blacklisting `rtw88_8821ce` in favour of a DKMS module means that if the DKMS build fails on the next kernel upgrade you boot with no Wi-Fi at all and no way to download a fix. Keep an ethernet cable or a USB Wi-Fi dongle to hand, always install the matching `linux-headers` before upgrading, and check `dkms status` after every kernel bump. Do not blacklist the in-tree driver until you have confirmed the DKMS one actually loads.

**Fix.**

Identify the chip and the driver actually bound:

```bash
lspci -knn | grep -A3 -i 'network\|wireless'
```

Then disable ASPM and deep power save. The parameter names come straight from the driver source — `rtw88/pci.c` declares `module_param_named(disable_aspm, rtw_pci_disable_aspm, bool, 0644)` in module `rtw88_pci`, and `rtw88/main.c` declares `disable_lps_deep` in `rtw88_core`:

```bash
sudo tee /etc/modprobe.d/70-rtw88.conf >/dev/null <<'EOF'
options rtw88_pci disable_aspm=y
options rtw88_core disable_lps_deep=y
EOF

sudo modprobe -r rtw88_8821ce rtw88_pci rtw88_core 2>/dev/null
sudo modprobe rtw88_8821ce
```

(Substitute `rtw88_8822ce` / `rtw88_8822be` / `rtw88_8723de` for your part. Doing this over ssh will drop the connection — run it at the console.) Confirm:

```bash
cat /sys/module/rtw88_pci/parameters/disable_aspm
cat /sys/module/rtw88_core/parameters/disable_lps_deep
```

If `disable_msi` is also needed on your board (some report MSI interrupt trouble), the same module exposes it: add `options rtw88_pci disable_msi=y`.

If the in-tree driver is still unusable after that, fall back to an out-of-tree DKMS driver. It needs kernel headers, so install those first:

```bash
# Omarchy: use the AUR helper, never a bare pacman -Syu
yay -S linux-headers rtw88-dkms-git
```

Prefer `rtw88-dkms-git`: it is a backport of the whole mainline rtw88 series and is still maintained. The older single-chip `rtl8821ce-dkms-git` also exists, but its last AUR update was January 2023, so expect it to fail to build against a current kernel:

```bash
yay -S linux-headers rtl8821ce-dkms-git
```

Only after `dkms status` shows the replacement module built for your running kernel should you blacklist the in-tree one:

```bash
sudo dkms status
echo 'blacklist rtw88_8821ce' | sudo tee /etc/modprobe.d/blacklist-rtw88.conf
sudo mkinitcpio -P
sudo reboot
```

After the reboot `lspci -k` should show the replacement driver in `Kernel driver in use:`.

**Verify.** `cat /sys/module/rtw88_pci/parameters/disable_aspm` prints `Y`. Then run a sustained transfer and watch for drops: `ping -i 0.2 -c 200 <your-router-ip>` should show no gaps over one second and no packet loss, and `journalctl -kf | grep -i rtw88` should be quiet during it.

Sources: <https://wiki.archlinux.org/title/Network_configuration/Wireless> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/realtek/rtw88/pci.c> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/realtek/rtw88/main.c> · <https://bbs.archlinux.org/viewtopic.php?id=273440>

---

## Recover a Realtek RTL8852BE that wedges after suspend

`rtw89-rtl8852be-dead-after-s2idle` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `omarchy`, `wayland`

**Symptom.** Closing and reopening the lid kills Wi-Fi until reboot. `omarchy-restart-wifi` / `rfkill unblock wifi` do nothing. Kernel log on resume:

```
rtw89_8852be 0000:02:00.0: failed to write DBI register, addr=0xB48
rtw89_8852be 0000:02:00.0: failed to read PCI cap, ret=134
rtw89_8852be 0000:02:00.0: xtal si not ready(W): offset=90 val=10 mask=10
rtw89_8852be 0000:02:00.0: mac preinit fail, ret: -110
```

followed by `wpa_supplicant: Could not set interface wlp2s0 flags (UP): Connection timed out`.

**Cause.** The rtw89 resume path leaves the RTL8852BE PHY wedged on s2idle systems. Userspace tools like `rfkill unblock` / `nmcli radio wifi on` operate a layer above the dead PHY, so they cannot recover it. The usual `rtw89_pci` workaround module options (`disable_clkreq=y disable_aspm_l1=y disable_aspm_l1ss=y`) do not help.

> **Audit corrected this record.** Diagnosis, PCI ID 10ec:b852 and the sleep-hook module list are correct. The bug is in the second block: the already-wedged recovery uses a *shorter* module list (`rtw89_8852be rtw89_pci rtw89_core`) than the sleep hook. On kernels 6.9+ `rtw89_8852b` and `rtw89_8852b_common` are also loaded and hold a reference on `rtw89_core`, so `modprobe -r rtw89_core` fails with 'Module rtw89_core is in use' and the recovery silently does nothing.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Unloading the Wi-Fi stack drops any active connection. Do not run the manual `modprobe -r` sequence over SSH on Wi-Fi — you will disconnect yourself.

**Fix.**

Recover an already-wedged machine with the same full module list the sleep hook uses:

```bash
lsmod | grep rtw89          # see what is actually loaded
sudo modprobe -r rtw89_8852be rtw89_8852b rtw89_8852b_common rtw89_pci rtw89_core
lsmod | grep rtw89          # must now be empty
sudo modprobe rtw89_8852be
sudo systemctl restart NetworkManager
```

The sleep hook itself is fine as written; add `exit 0` at the end so a failed `modprobe -r` never returns non-zero into the sleep pipeline.

**Verify.** `lspci -n | grep 10ec:b852` confirms the chip. Close and reopen the lid; `ip link show` lists the wireless interface `UP` and it reassociates without a reboot.

Sources: <https://github.com/basecamp/omarchy/issues/7003> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-restart-wifi>

---

## Fix total DNS failure after connecting Tailscale

`tailscale-accept-dns-breaks-all-dns` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** Toggling Tailscale on breaks **all** DNS, not just MagicDNS — nothing resolves anywhere while the Tailscale widget still says "Connected". `tailscale status --json` health messages include:

```
Tailscale can't reach the configured DNS servers. Internet connectivity may be affected.
Some peers are advertising routes but --accept-routes is false
```

**Cause.** Linux defaults are `--accept-dns` on and `--accept-routes` off. When the tailnet pushes nameservers that only live behind an advertised subnet route, Tailscale rewrites the system resolvers to those addresses but refuses the routes needed to reach them, so every lookup fails. In Omarchy only the installer path passes `--accept-routes`; if you skip auth there and log in later from the bar widget, the widget runs a flagless `tailscale up` and the pref is never written.

> ⚠️ **Risk.** `--accept-routes` makes this machine honour every subnet route advertised on the tailnet, which can shadow local LAN addresses. On a home network that overlaps a tailnet subnet, this can black-hole your own router.

**Fix.**

Either accept the routes that make the pushed resolvers reachable:

```bash
sudo tailscale set --accept-routes
```

or stop using tailnet DNS entirely:

```bash
sudo tailscale set --accept-dns=false
sudo resolvectl flush-caches
```

Inspect what is actually set:

```bash
tailscale debug prefs | grep -E 'CorpDNS|RouteAll'
tailscale status --json | jq '.Health'
resolvectl status | grep -A4 tailscale0
```

**Verify.** `tailscale debug prefs` shows `RouteAll: true` (or `CorpDNS: false`), `resolvectl query archlinux.org` succeeds with Tailscale connected, and `tailscale status --json | jq '.Health'` is empty or null.

Sources: <https://github.com/basecamp/omarchy/issues/6962>

---

## Connect to a WPA3-SAE or mixed WPA2/WPA3 network that refuses to associate

`wpa3-sae-association-fails-no-psk-available` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A network the phone joins fine will not connect from Linux. With wpa_supplicant directly you get `wlan0: No PSK available for association` followed by `wlan0: SME: Failed to set WPA key management and encryption suites`. Through NetworkManager it fails with `Error: Connection activation failed: (7) Secrets were required, but not provided` even though the password is correct, or it associates and immediately deauthenticates. `wpa_cli scan_results` shows the network flagged `[WPA2-SAE-CCMP][ESS]` or `[WPA2-PSK+SAE-CCMP]`.

**Cause.** WPA3 Personal is SAE, not PSK. A WPA3-only AP needs `key_mgmt=SAE` with a literal `sae_password=` — a `psk=` line is simply not a credential SAE can use, hence "No PSK available". WPA3 also mandates Protected Management Frames (802.11w), so the connection fails unless PMF is negotiated. Mixed WPA2-PSK/WPA3-SAE "transition mode" APs are worse: the client has to pick the right key-mgmt suite and agree on PMF as *optional*, and a profile that hard-requires either mode fails against the other. Some APs are additionally configured for hash-to-element (H2E) only, which the supplicant will not use unless told to.

**Fix.**

Find out what the AP is actually offering:

```bash
sudo wpa_cli -i wlan0 scan
sudo wpa_cli -i wlan0 scan_results | grep -i '<your-ssid>'
# [WPA2-SAE-CCMP]      -> WPA3 only
# [WPA2-PSK+SAE-CCMP]  -> transition mode
```

Check the card can do PMF at all:

```bash
iw phy phy0 info | grep 00-0f-ac:6     # any output means MFP/PMF is supported
```

**With NetworkManager (the normal case).** For a WPA3-only network:

```bash
nmcli connection modify "<SSID>" \
  802-11-wireless-security.key-mgmt sae \
  802-11-wireless-security.psk '<the literal wifi password>' \
  802-11-wireless-security.pmf 3
nmcli connection up "<SSID>"
```

For a mixed WPA2/WPA3 transition-mode network, use `wpa-psk` (which NetworkManager documents as "WPA2 + WPA3 personal") and leave PMF optional — this is the combination that works against both halves of the AP:

```bash
nmcli connection modify "<SSID>" \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.pmf 2
nmcli connection up "<SSID>"
```

NetworkManager's `pmf` values are `0` default, `1` disable, `2` optional, `3` required. If an old AP breaks when PMF is even offered, `pmf 1` disables it outright.

**With bare wpa_supplicant.** WPA3-only:

```ini
# /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
ctrl_interface=/run/wpa_supplicant
update_config=1
sae_pwe=2

network={
  ssid="<SSID>"
  key_mgmt=SAE
  sae_password="the.literal.wifi.password"
  ieee80211w=2
}
```

Mixed WPA2-PSK/WPA3-SAE:

```ini
network={
  ssid="<SSID>"
  key_mgmt=WPA-PSK-SHA256
  psk="the.literal.wifi.password"
  ieee80211w=2
}
```

`sae_pwe=2` in the global section enables both hash-to-element and hunt-and-peck, which is required against APs configured for H2E only. `ieee80211w` is `0` disabled, `1` optional, `2` required.

Then:

```bash
sudo systemctl restart wpa_supplicant@wlan0.service
# or, to watch it fail loudly:
sudo wpa_supplicant -d -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
```

If you use iwd as the backend instead, it supports WPA3 Personal natively and generally needs no key-mgmt configuration at all — worth trying as a straight A/B test.

**Verify.** `nmcli -f GENERAL.STATE,802-11-wireless-security.key-mgmt connection show --active "<SSID>"` shows the connection active. `iw dev wlan0 link` reports the BSS and no repeated re-association. With wpa_supplicant running in the foreground you should see `CTRL-EVENT-CONNECTED` rather than `No PSK available for association`.

Sources: <https://wiki.archlinux.org/title/Wpa_supplicant> · <https://wiki.archlinux.org/title/Network_configuration/Wireless> · <https://bbs.archlinux.org/viewtopic.php?id=256573> · <https://networkmanager.dev/docs/api/latest/settings-802-11-wireless-security.html>

---

## Remove the brcmfmac feature_disable quirk that blocks association on Apple Silicon Macs

`brcmfmac-feature-disable-breaks-apple-silicon-wifi` · severity: **high** · frequency: **occasional** · applies to: `arch`, `laptop`, `omarchy`

**Symptom.** On an M1/M2 Mac running Asahi, `wlan0` exists and scanning lists every network in range, but joining any network hangs and times out — NetworkManager reports it like a wrong password. After a couple of attempts the chip stops answering entirely and even scanning dies until a driver reload or reboot. Logs:

```
wpa_supplicant: wlan0: Trying to associate with aa:bb:cc:00:00:01 (SSID='...' freq=2462 MHz)
wpa_supplicant: FT: Invalid key management type (2)
wpa_supplicant: wlan0: Authentication with aa:bb:cc:00:00:02 timed out.
ieee80211 phy0: brcmf_msgbuf_query_dcmd: Timeout on response for query command
ieee80211 phy0: brcmf_cfg80211_scan: scan error (-12)
```

**Cause.** `install/hardware/apple/fix-brcmfmac-supplicant.sh` writes `options brcmfmac feature_disable=0x82000` for any Apple machine whose Wi-Fi PCI ID appears in `brcm_hw_ids.h`. That ID list includes two Apple Silicon parts — `4425` (BCM4378, M1) and `4433` (BCM4387, M1 Pro/Max/Ultra, M2). The flag is meant to work around a WPA handshake that never completes on some Intel Macs; on BCM4378/BCM4387 it prevents association altogether.

> **Audit corrected this record.** Cause verified exactly: install/hardware/apple/fix-brcmfmac-supplicant.sh matches `14e4:(43ba|43bb|43bc|43a3|43dc|4464|4488|4425|4433)` on Apple DMI and writes `options brcmfmac feature_disable=0x82000` — 4425 and 4433 are in that list. But the fix does not stick: migrations/1786391100.sh re-applies the same flag on the next `omarchy update`, and its guard is `grep -Eq '^[[:space:]]*options[[:space:]]+brcmfmac[[:space:]].*feature_disable=0x82000'` — so both the plain `rm` and, worse, the sed that comments the line out, fail the guard and get the option appended straight back. The record's own second option is the one that is guaranteed to be undone.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

```bash
cat /etc/modprobe.d/brcmfmac.conf   # expect: options brcmfmac feature_disable=0x82000
sudo rm /etc/modprobe.d/brcmfmac.conf
sudo reboot
```

Do **not** just comment the line out — Omarchy's migration explicitly re-adds the option when no *active* `feature_disable=0x82000` line is present, so a commented-out line is re-appended on the next `omarchy update`.

To keep it from coming back, mask the file instead of deleting it (the migration's `tee -a` then writes into /dev/null and modprobe reads nothing):

```bash
sudo ln -sfn /dev/null /etc/modprobe.d/brcmfmac.conf
sudo reboot
cat /sys/module/brcmfmac/parameters/feature_disable   # expect 0
```

Re-check that value after every `omarchy update`; if it is back to 0x82000, the file was recreated.

**Verify.** `lspci -nn | grep -i network` shows `[14e4:4433]` or `[14e4:4425]`; after reboot `nmcli device wifi connect "<SSID>"` associates normally and repeated scans keep working.

Sources: <https://github.com/basecamp/omarchy/issues/7439>

---

## Stop broadcom-wl from hard-freezing a BCM4331 MacBook

`broadcom-wl-bcm4331-hard-freeze` · severity: **high** · frequency: **occasional** · applies to: `arch`, `laptop`, `omarchy`

**Symptom.** On a mid-2011 MacBook Air/Pro with Broadcom BCM4331, the machine hard-freezes (no console, no SysRq, power button only) either in the live installer while Wi-Fi is being set up, or shortly after boot on the installed system. Before installation the in-kernel driver worked fine.

**Cause.** Omarchy's `install/hardware/fix-bcm43xx.sh` installs `broadcom-wl` whenever it sees `14e4:43a0` (BCM4360) **or** `14e4:4331` (BCM4331). BCM4360 genuinely needs `wl` — there is no in-kernel driver — but BCM4331 is fully supported by the in-kernel `b43` driver. Worse, the `broadcom-wl` package ships a modprobe blacklist for `b43`, `ssb` and `bcma`, so installing it does not merely add an alternative, it disables the working in-kernel path.

> **Audit corrected this record.** Cause verified against install/hardware/fix-bcm43xx.sh, which really does `omarchy-pkg-add broadcom-wl dkms linux-headers` for both 14e4:43a0 and 14e4:4331. But the fix is broken in two ways. (1) broadcom-wl and broadcom-wl-dkms *conflict* (confirmed on the Arch package page), so exactly one can be installed and `pacman -Rns broadcom-wl broadcom-wl-dkms` aborts with 'target not found' and removes NOTHING — `2>/dev/null` only hides the error. (2) b43 firmware is NOT in linux-firmware-broadcom; the Arch broadcom-wl file list is just usr/lib/modprobe.d/broadcom-wl.conf + wl.ko.zst, and b43 needs proprietary firmware extracted by b43-fwcutter (AUR b43-firmware). Installing b43-fwcutter alone leaves the machine with no Wi-Fi at all. The `rm` targets are also wrong paths — the blacklist ships in /usr/lib/modprobe.d/, not /etc/modprobe.d/, and disappears with the package.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do NOT apply this on a BCM4360 (`14e4:43a0`) — there is no in-kernel driver for it and removing `broadcom-wl` there leaves you with no Wi-Fi at all.

**Fix.**

```bash
lspci -nn | grep -i network        # confirm [14e4:4331]

# Remove whichever variant is actually installed (they conflict; naming both aborts)
for p in broadcom-wl broadcom-wl-dkms; do
  pacman -Qq "$p" >/dev/null 2>&1 && sudo pacman -Rns "$p"
done

# The blacklist ships in /usr/lib/modprobe.d and goes away with the package.
# Only remove a local override if you actually have one:
ls -l /etc/modprobe.d/ | grep -i -E 'broadcom|b43|wl'
```

b43 needs firmware that Arch cannot redistribute — `b43-fwcutter` only extracts it, it ships none:

```bash
sudo pacman -S --needed b43-fwcutter linux-firmware-broadcom
# then install the AUR package that downloads Broadcom's blob and runs fwcutter:
#   paru -S b43-firmware      (BCM4331 needs the 5.100.138 firmware)
ls /usr/lib/firmware/b43/    # must be non-empty before rebooting
sudo reboot
```

After reboot: `dmesg | grep b43` should show the firmware loading, and `ip link` should show a `wl*` device.

To get in if it freezes first, append at the boot menu: `modprobe.blacklist=wl`

**Verify.** `lsmod | grep -E '^(b43|wl)'` shows `b43` loaded and `wl` absent. `ip link` lists the interface (often named `wlp2s0b1` under `b43`) and the machine stays up under Wi-Fi load.

Sources: <https://github.com/basecamp/omarchy/issues/7593> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/fix-bcm43xx.sh>

---

## Get an IPv4 lease when the router ignores NetworkManager's DHCP client-id

`dhcp-no-offer-until-client-id-none` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** After upgrading to Omarchy Quattro the laptop associates to Wi-Fi and gets a global IPv6 address and IPv6 default route, but no IPv4 address and no IPv4 route at all. Other devices on the same network are fine, and the same laptop gets IPv4 from a phone hotspot. NetworkManager's log shows:

```
ipv4.dhcp-client-id: no explicit client-id configured
client-id: set effective 01:xx:xx:xx:xx:xx:xx
event: send DISCOVER to 255.255.255.255
event: send DISCOVER to 255.255.255.255
```

with no OFFER ever arriving.

**Cause.** When no client-id is configured, NetworkManager synthesises RFC 2132 option 61 from the interface MAC (`01:<mac>`). Some ISP-supplied routers refuse to answer a DISCOVER that carries that option, or key their lease table on a different identifier. Setting the client-id to `none` makes NetworkManager omit option 61 entirely, which those routers accept.

**Fix.**

```bash
nmcli -g NAME,TYPE connection show      # find the profile name
sudo nmcli connection modify "<connection-name>" ipv4.dhcp-client-id none
sudo nmcli connection up "<connection-name>"
```

To watch the exchange while testing:

```bash
journalctl -u NetworkManager -f | grep -i dhcp
# healthy: received OFFER of 192.168.0.192 from 192.168.0.1 / received ACK ... / state changed new lease
```

To apply it to every new profile, drop in a default:

```bash
sudo tee /etc/NetworkManager/conf.d/30-dhcp-client-id.conf >/dev/null <<'EOF'
[connection]
ipv4.dhcp-client-id=none
EOF
sudo systemctl reload NetworkManager
```

**Verify.** `ip -4 addr show` shows an address and `ip -4 route` shows a default route via the router. The setting persists across reconnects (`nmcli -f ipv4.dhcp-client-id connection show "<name>"`).

Sources: <https://github.com/basecamp/omarchy/issues/7744> · <https://man.archlinux.org/man/NetworkManager.conf.5>

---

## Fix RTL8125 2.5GbE ethernet that never gets a DHCP lease

`rtl8125-no-dhcp-lease-tx-checksum-offload` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `omarchy`

**Symptom.** Wired ethernet shows link up and negotiates the correct speed, but never receives an IP address. `nmcli`/`networkctl` report DHCP timing out on every retry. Wi-Fi on the same machine works. The same cable and port get a lease instantly from Windows on the same hardware. `sudo tcpdump -i eno1 -n udp port 67 or port 68` shows DHCPDISCOVER going out repeatedly with zero replies.

**Cause.** Some RTL8125 revisions (notably RTL8125D) hit a TX checksum offload bug in the in-kernel `r8169` driver: the NIC hardware computes bad checksums on outgoing packets. `tcpdump` captures packets *before* the NIC finishes processing them, so every DHCP request looks perfectly normal on the wire capture while the router silently drops it. Firewall rules, EEE, ASPM and DHCP client-id are all red herrings here.

> ⚠️ **Risk.** Disabling TX checksum offload moves checksumming to the CPU. Throughput cost is negligible at 2.5 Gbit but it is a real behaviour change; do not apply it blindly to a working NIC.

**Fix.**

Confirm the chipset and driver, then disable TX offload:

```bash
lspci -k | grep -A3 -i ethernet     # look for RTL8125 and "Kernel driver in use: r8169"
sudo ethtool -K eno1 tx off         # substitute your interface name
sudo nmcli connection up "Wired connection 1"
```

Make it survive reboot with a systemd unit:

```bash
sudo tee /etc/systemd/system/rtl8125-txoff@.service >/dev/null <<'EOF'
[Unit]
Description=Disable TX checksum offload on %i
BindsTo=sys-subsystem-net-devices-%i.device
After=sys-subsystem-net-devices-%i.device

[Service]
Type=oneshot
ExecStart=/usr/bin/ethtool -K %i tx off
RemainAfterExit=yes

[Install]
WantedBy=sys-subsystem-net-devices-%i.device
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now rtl8125-txoff@eno1.service
```

**Verify.** `ethtool -k eno1 | grep tx-checksumming` reports `off`. Reboot cold; `ip addr show eno1` has an IPv4 address within a couple of seconds of boot, every time.

Sources: <https://github.com/basecamp/omarchy/issues/7804>

---

## Stop periodic Bluetooth audio dropouts caused by USB autosuspend

`bluetooth-audio-dropouts-btusb-autosuspend` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`, `pipewire`

**Symptom.** Bluetooth audio randomly cuts out for about a second then resumes, over and over. The device stays connected the whole time and nothing is logged. Reported with Sony WH-1000XM5, Marshall Major V, Logitech receivers, and on Macs with Broadcom Wi-Fi/BT combo cards.

**Cause.** The `btusb` driver autosuspends the controller between transmissions and power-cycles it back up for each burst, which drops audio frames. On Macs it is compounded by antenna contention — Wi-Fi and Bluetooth share one antenna — and by AAC re-encoding being timing-sensitive on those Broadcom controllers.

> **Audit corrected this record.** The btusb half is right: `enable_autosuspend` is a real btusb parameter and disabling it is the standard fix for periodic ~1s A2DP dropouts. Two problems. (1) `modprobe -r btusb` fails with 'Module btusb is in use' while bluetoothd holds the adapter — bluetooth.service must be stopped first, so as written the change silently does not take effect until reboot. (2) The WirePlumber block is self-contradictory: it is introduced as 'let WirePlumber fall back off AAC' but lists `aac` first in `bluez5.codecs`, which is exactly the preference order that keeps AAC selected. To stop negotiating AAC you must omit it from the list.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Disabling btusb autosuspend increases idle power draw slightly.

**Fix.**

```bash
echo 'options btusb enable_autosuspend=n' | sudo tee /etc/modprobe.d/btusb-autosuspend.conf

# bluetoothd holds the module open; stop it before reloading or the rmmod fails
sudo systemctl stop bluetooth
sudo modprobe -r btusb
sudo modprobe btusb
sudo systemctl start bluetooth

cat /sys/module/btusb/parameters/enable_autosuspend    # expect N
```

If dropouts persist, actually drop AAC from the negotiated codec list (leaving `aac` in the list keeps it preferred):

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
cat > ~/.config/wireplumber/wireplumber.conf.d/51-bluez-codecs.conf <<'EOF'
monitor.bluez.properties = {
  bluez5.codecs = [ sbc_xq sbc ]
  bluez5.enable-sbc-xq = true
  bluez5.roles = [ a2dp_sink a2dp_source bap_sink bap_source ]
}
EOF
systemctl --user restart wireplumber

# reconnect the headset, then confirm which codec is in use
pw-dump | grep -i 'api.bluez5.codec'
```

Add `aac` back to the front of `bluez5.codecs` if you decide the quality trade-off is not worth it.

**Verify.** `cat /sys/module/btusb/parameters/enable_autosuspend` prints `N`. Play audio for 10+ minutes with no interruptions; `pw-cli info all | grep -i codec` shows the negotiated codec.

Sources: <https://github.com/basecamp/omarchy/issues/1288> · <https://github.com/basecamp/omarchy/pull/7644>

---

## Get the microphone working on a Bluetooth headset under PipeWire

`bluetooth-headset-no-microphone-hfp-profile` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Bluetooth headphones play audio perfectly but the built-in mic is unusable. Either the headset's microphone never appears as an input at all and the only profile offered is "High Fidelity Playback (A2DP Sink)", or the "Headset Head Unit (HFP/HSP)" profile is listed but greyed out / marked unavailable, or you can select it and then get silence in both directions — nothing plays and the input meter never moves. In `bluetoothctl` the transport sits at `State: idle` on the headset profile where it goes `State: active` on A2DP.

**Cause.** Three different failures wear the same face. (1) A2DP is playback-only by design; the microphone only exists under HFP/HSP, which is a separate profile the card has to be switched to. (2) The adapter's firmware is missing, so the SCO link that carries HFP audio never comes up — Broadcom USB dongles are the classic case, logging `Bluetooth: hci0: BCM: firmware Patch file not found`. (3) The `hfp_hf` role or mSBC has been disabled in a WirePlumber drop-in, often copied from a "fix my headset" snippet whose whole purpose was to turn HFP off.

> **Audit corrected this record.** Almost all of this is verified and current, but the WirePlumber drop-in contradicts the default it just quoted and re-enables a role combination upstream deliberately leaves out. Verified correct first: `wpctl settings --save bluetooth.autoswitch-to-headset-profile <bool>` is real (Arch wiki Bluetooth headset uses that exact command; the key is in the schema at /usr/share/wireplumber/wireplumber.conf line 873 with default true). The stated upstream default `bluez5.roles = [ a2dp_sink a2dp_source bap_sink bap_source hfp_hf hfp_ag ]` is exactly what the wiki documents. `bluez5.roles`, `bluez5.enable-msbc`, `bluez5.enable-sbc-xq` and `bluez5.hfphsp-backend` are all real properties — I found all four in the strings of /usr/lib/spa-0.2/bluez5/libspa-bluez5.so on PipeWire 1.6.8. The profile names are real: bluez5-device.c builds codec profiles as `spa_aprintf("%s-%s", name, media_codec->name)` over base `headset-head-unit` with codec names `msbc`/`cvsd`, so `headset-head-unit-msbc` is right, and `pactl set-card-profile` taking the name while `wpctl set-profile` takes an index is right. Package names check out: broadcom-bt-firmware is AUR (wiki uses {{AUR|...}}), and linux-firmware-intel / linux-firmware-realtek are real core packages post-split — linux-firmware-intel owns 127 ibt-* Bluetooth blobs and linux-firmware-realtek owns 48 rtl_bt files. Nothing is stale PulseAudio advice; the danger note about /var/lib/bluetooth destroying every link key is correct and matches the dual-boot record. The defect: the drop-in writes `bluez5.roles = [ a2dp_sink a2dp_source bap_sink bap_source hsp_hs hsp_ag hfp_hf hfp_ag ]` under the heading "restore the roles explicitly", which is not the default it stated two lines earlier — it adds hsp_hs and hsp_ag. Upstream omits hsp_ag on purpose; the Arch wiki records why: "Currently some headsets (Sony WH-1000XM3) are not working with both hsp_ag and hfp_ag enabled, so by default we enable only HFP." A user copy-pasting this to fix a mic can break a headset that was working. Corrected fix restores the documented default list and says what to do if the headset only speaks HSP.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting `/var/lib/bluetooth` to force a clean re-pair (advice that circulates for this problem) removes the link keys for *every* paired device on the machine, including any you have painstakingly synchronised with a Windows dual boot. Back it up first: `sudo cp -a /var/lib/bluetooth /var/lib/bluetooth.bak`.

**Fix.**

See what the card is actually offering:

```bash
pactl list cards | grep -A 40 'bluez_card'
# look for the 'Profiles:' block and whether each is 'available: yes' or 'no'
wpctl status
```

**Switch to the headset profile by name.** `pactl` takes the profile name, which is what the listing above prints (`wpctl set-profile` wants a numeric index, which is easy to get wrong):

```bash
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX headset-head-unit-msbc
# if mSBC is not offered by the headset:
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX headset-head-unit
```

Replace the colons in the MAC with underscores. Then pick the mic as the default source:

```bash
wpctl status | grep -A 10 Sources
wpctl set-default <source-id>
```

**If all Headset Head Unit profiles are `available: no`, or selecting one gives silence in both directions**, the adapter is missing firmware. Check:

```bash
journalctl -kb | grep -i 'bluetooth.*firmware'
```

`BCM: firmware Patch file not found` means a Broadcom part, whose blobs are not in the repos:

```bash
yay -S broadcom-bt-firmware      # AUR
sudo systemctl restart bluetooth.service
```

Then unpair and re-pair the headset. For Intel adapters the `ibt-*` blobs are in `linux-firmware-intel`; for Realtek the `rtl_bt` blobs are in `linux-firmware-realtek`. Both are pulled in by the `linux-firmware` meta-package, so on a stock install they are already there.

**Make apps switch to the mic automatically** when a call starts (this is on by default in WirePlumber but is frequently turned off by copy-pasted configs):

```bash
wpctl settings --save bluetooth.autoswitch-to-headset-profile true
```

**Check nothing has disabled the HFP role.** Look for a drop-in that strips `hfp_hf`:

```bash
grep -rn 'bluez5.roles\|autoswitch-to-headset\|enable-msbc' \
  ~/.config/wireplumber/ /etc/wireplumber/ 2>/dev/null
```

The upstream defaults are `bluez5.roles = [ a2dp_sink a2dp_source bap_sink bap_source hfp_hf hfp_ag ]`, `bluez5.enable-msbc = true` and `bluez5.hfphsp-backend = "native"`. **Prefer deleting the offending drop-in** — that puts you back on the defaults with no drift. If you would rather be explicit, write the defaults back verbatim and nothing more:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
tee ~/.config/wireplumber/wireplumber.conf.d/51-bluez-roles.conf >/dev/null <<'EOF'
monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source bap_sink bap_source hfp_hf hfp_ag ]
  bluez5.enable-msbc = true
  bluez5.enable-sbc-xq = true
  bluez5.hfphsp-backend = "native"
}
EOF

systemctl --user restart wireplumber.service
```

Do **not** add `hsp_hs` / `hsp_ag` on spec. They are omitted from the upstream default deliberately: with both `hsp_ag` and `hfp_ag` enabled some headsets stop working entirely (the Sony WH-1000XM3 is the documented case). Only add `hsp_hs hsp_ag` if the headset is old enough to offer HSP but not HFP, and back it out the moment the profile stops appearing.

Reconnect the headset afterwards. Expect the sound quality to collapse while HFP is active — mSBC is 16 kHz wideband and CVSD is 8 kHz narrowband; that is the protocol, not a bug, and it is why you want autoswitch rather than staying on HFP permanently.

**Verify.** `pactl list cards | grep -A 5 'Active Profile'` shows a `headset-head-unit*` profile. `wpctl status` lists the headset under Sources. Record and play back a test: `pw-record /tmp/t.wav` (Ctrl-C after speaking) then `pw-play /tmp/t.wav`. `bluetoothctl info <MAC>` and the transport state should read `active`, not `idle`, while recording.

Sources: <https://wiki.archlinux.org/title/Bluetooth_headset> · <https://wiki.archlinux.org/title/PipeWire> · <https://bbs.archlinux.org/viewtopic.php?id=290780> · <https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html>

---

## Make Bluetooth power on automatically at boot

`bluetooth-off-at-every-boot-autoenable` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Bluetooth is off at every login. The panel/widget shows it disabled and you have to turn it on by hand after each reboot; paired headphones never auto-connect. `bluetoothctl show` reports `Powered: no`.

**Cause.** `/etc/bluetooth/main.conf` contains `[Policy] AutoEnable=false`. With that set, `bluetoothd` never powers on the adapter at boot or when one is hotplugged. Older Omarchy set it deliberately (mistakenly believing it persisted power state); some other distros ship it too.

**Fix.**

```bash
grep -n 'AutoEnable' /etc/bluetooth/main.conf
sudo sed -i 's/^[#[:space:]]*AutoEnable[[:space:]]*=.*/AutoEnable=true/' /etc/bluetooth/main.conf
grep -n 'AutoEnable' /etc/bluetooth/main.conf   # expect: AutoEnable=true (under [Policy])

sudo systemctl enable --now bluetooth.service
sudo systemctl restart bluetooth
```

If the adapter still comes up off, an rfkill soft block is being persisted instead — clear it:

```bash
rfkill list bluetooth
sudo rfkill unblock bluetooth
```

**Verify.** `bluetoothctl show | grep Powered` prints `Powered: yes` immediately after a fresh boot, without any manual toggle.

Sources: <https://github.com/basecamp/omarchy/issues/5868> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/bluetooth.sh>

---

## Fix .local hostnames, LocalSend, KDE Connect and printer discovery not working

`mdns-local-hostnames-fail-ufw-blocks-5353` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `ping nas.local` returns `Name or service not known`, network printers never appear in the CUPS or GTK print dialog, LocalSend and KDE Connect on the phone cannot see the laptop (or the laptop cannot see them), and `avahi-browse --all --ignore-local --resolve --terminate` prints nothing at all. Other machines on the same LAN discover each other fine.

**Cause.** Two separate things break this and both have to be right. First, the firewall: mDNS is UDP port 5353 and every device answers from that port to the multicast group, so with `ufw default deny incoming` the replies to your own queries are dropped. Omarchy ships exactly that default and opens only 53317 for LocalSend — 5353 is never opened. Second, glibc has to be told to consult mDNS at all: the `hosts:` line in `/etc/nsswitch.conf` needs `mdns_minimal [NOTFOUND=return]` ahead of `resolve` and `dns`, backed by the `nss-mdns` package. A third, subtler failure is systemd-resolved answering SOA queries for the `local` domain, which makes nss-mdns stand down.

> ⚠️ **Risk.** Opening 5353/udp exposes your hostname and advertised services to everyone on the local link. That is normal on a home or office LAN and a bad idea on café or hotel Wi-Fi — scope the rule if you roam: `sudo ufw allow in proto udp from 192.168.0.0/16 to any port 5353`. Editing `/etc/nsswitch.conf` incorrectly can break *all* name resolution including `dns`; keep a copy (`sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.bak`) and test with `getent hosts archlinux.org` before you log out.

**Fix.**

Diagnose in that order:

```bash
systemctl is-active avahi-daemon.service
grep '^hosts:' /etc/nsswitch.conf
sudo ufw status verbose | grep -i 5353
avahi-browse --all --ignore-local --resolve --terminate
```

**Open the port.** This is the missing piece on a stock Omarchy install:

```bash
sudo ufw allow 5353/udp comment 'mDNS'
sudo ufw reload
```

If you also use KDE Connect, it needs its own range:

```bash
sudo ufw allow 1714:1764/udp comment 'KDE Connect'
sudo ufw allow 1714:1764/tcp comment 'KDE Connect'
```

**Make glibc resolve .local.** Install the module and edit the hosts line:

```bash
sudo pacman -S --needed nss-mdns avahi
sudo systemctl enable --now avahi-daemon.service
```

```ini
# /etc/nsswitch.conf
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve [!UNAVAIL=return] files myhostname dns
```

Omarchy 4 already ships this file with `mdns_minimal` in place, so check before editing. If you do edit it there, be aware the file is package-owned and your change will surface as a `.pacnew` on the next update — reconcile it with `sudo pacdiff`.

**If .local still fails, check the SOA behaviour** that nss-mdns depends on:

```bash
host -t SOA local
```

If that does not return `NXDOMAIN`, switch to the full `mdns` module and confine it to `.local` with an allow-list:

```ini
# /etc/nsswitch.conf
hosts: mymachines mdns [NOTFOUND=return] resolve [!UNAVAIL=return] files myhostname dns
```

```bash
sudo tee /etc/mdns.allow >/dev/null <<'EOF'
.local.
.local
EOF
```

**If you would rather have systemd-resolved do mDNS instead of Avahi**, enable it globally and per-connection — both are required:

```bash
sudo tee /etc/systemd/resolved.conf.d/mdns.conf >/dev/null <<'EOF'
[Resolve]
MulticastDNS=yes
EOF
sudo systemctl restart systemd-resolved

nmcli connection modify "<connection-name>" connection.mdns yes
nmcli connection up "<connection-name>"
```

Or set it for every connection at once:

```ini
# /etc/NetworkManager/conf.d/10-mdns.conf
[connection]
connection.mdns=2
```

Do not run Avahi as a responder and systemd-resolved as a responder simultaneously; if you want Avahi to answer while resolved caches, set `MulticastDNS=resolve` instead of `yes`.

**Verify.** `avahi-browse --all --ignore-local --resolve --terminate` lists services from other machines. `getent hosts nas.local` returns an address. `resolvectl query nas.local` succeeds. `sudo ufw status | grep 5353` shows the ALLOW rule. Printers appear in `lpstat -e` / the GTK print dialog.

Sources: <https://wiki.archlinux.org/title/Avahi> · <https://wiki.archlinux.org/title/Systemd-resolved> · <https://github.com/basecamp/omarchy/blob/master/install/config/firewall.sh> · <https://github.com/basecamp/omarchy/blob/master/etc/nsswitch.conf> · <https://wiki.archlinux.org/title/Uncomplicated_Firewall>

---

## Stop NetworkManager-wait-online adding 30–120 seconds to every boot

`networkmanager-wait-online-delays-boot` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Boot sits on a blank screen or the splash for half a minute or more before the login screen appears, sometimes ending with `A start job is running for Network Manager Wait Online (1min 30s / no limit)` or a red `Failed to start Network Manager Wait Online`. `systemd-analyze blame` puts `NetworkManager-wait-online.service` at the top with 30s, 60s or 120s. It is worst on laptops that boot away from their usual Wi-Fi, and on machines with no cable plugged in.

**Cause.** `NetworkManager-wait-online.service` is `WantedBy=network-online.target`, so it only runs when something pulls that target in — and on a desktop install something almost always does. On Omarchy it is `cups-browsed.service`, which orders itself after `network-online.target`, which in turn gates `graphical.target`. The result is that the whole desktop waits for DHCP or Wi-Fi association before it will draw. Nothing in a Hyprland session actually needs the network to be up before it starts.

> **Audit corrected this record.** The problem, the remedy and every Omarchy-specific claim are correct — but one sentence of mechanism inside the fix is false, and it is exactly the confident-specific failure mode. Verified true: Omarchy 4's install/config/enable-services.sh on quattro really does `systemctl mask NetworkManager-wait-online.service`, migrations/1784568652.sh really does mask it on upgrade, and install/hardware/network.sh really does disable+mask systemd-networkd-wait-online.service while retiring archinstall's 'copy ISO network' units — the record even gets the archinstall provenance right. The cups-browsed cause is confirmed by the migration's own comment: "graphical.target was gated on network-online.target (cups-browsed orders itself after it)". The unit file on this machine confirms `ExecStart=/usr/bin/nm-online -s -q`, `Environment=NM_ONLINE_TIMEOUT=60` and `WantedBy=network-online.target`, so dropping -s to wait for real connectivity and raising NM_ONLINE_TIMEOUT are both right. What is wrong: "Mask, not disable: systemctl disable will not stop it, because it is pulled in as a dependency of network-online.target rather than started on its own." The enablement symlink is /etc/systemd/system/network-online.target.wants/NetworkManager-wait-online.service (there is no vendor .wants directory under /usr/lib), so `systemctl disable` does remove it and does stop it running. The real reason to prefer mask is in NetworkManager.service's own [Install]: `Also=NetworkManager-wait-online.service`, so any later `systemctl enable NetworkManager` or preset run silently re-enables it. Corrected fix replaces that one rationale with the verified one; all commands are unchanged.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Masking the unit means `network-online.target` is reached immediately, so any unit ordered `After=network-online.target` — NFS/CIFS mounts in fstab with `_netdev`, `wg-quick@`, backup timers, self-hosted services — can now start before there is an address and fail on the first try. Audit `systemctl list-dependencies network-online.target` before masking, and give anything genuinely network-dependent its own `Restart=on-failure` / `RestartSec=` rather than relying on the global wait.

**Fix.**

First confirm it is the culprit:

```bash
systemd-analyze blame | head -10
systemd-analyze critical-chain graphical.target
systemctl list-dependencies network-online.target --reverse
```

Then mask the unit:

```bash
sudo systemctl mask NetworkManager-wait-online.service
```

**Mask rather than disable.** `systemctl disable` does work — the enable symlink lives in `/etc/systemd/system/network-online.target.wants/` and disabling removes it — but it does not stick. `NetworkManager.service` carries `Also=NetworkManager-wait-online.service` in its own `[Install]` section, so the next `systemctl enable NetworkManager.service`, or any preset run, quietly re-enables the wait unit. A mask survives all of that.

If `systemd-networkd` is also installed (common on machines built by archinstall's "copy ISO network config" mode), mask its equivalent too:

```bash
sudo systemctl mask systemd-networkd-wait-online.service
```

Omarchy 4 does both of these for you — `install/config/enable-services.sh` masks the NetworkManager one on a fresh install, `install/hardware/network.sh` disables and masks the networkd one, and `migrations/1784568652.sh` masks the NetworkManager one on upgrade — so on Omarchy check first rather than assuming:

```bash
systemctl is-enabled NetworkManager-wait-online.service   # expect: masked
```

If you genuinely have a service that must not start before the network is really up (a network mount, a VPN, a backup job), do not mask the unit. Instead make it wait for actual connectivity rather than for NetworkManager to finish starting, by dropping the `-s` flag (the stock unit is `ExecStart=/usr/bin/nm-online -s -q`, and `-s` means "wait until NetworkManager logs startup complete", not "wait until there is an address"):

```bash
sudo systemctl edit NetworkManager-wait-online.service
```

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/nm-online -q
```

and raise the timeout in the same drop-in if the stock 60s is too tight:

```ini
[Service]
Environment=NM_ONLINE_TIMEOUT=120
```

**Verify.** Reboot, then `systemd-analyze blame | head -5` should no longer list either wait-online unit, and `systemd-analyze` should report a total boot time tens of seconds shorter. `systemctl is-enabled NetworkManager-wait-online.service` prints `masked`.

Sources: <https://wiki.archlinux.org/title/NetworkManager> · <https://github.com/basecamp/omarchy/blob/master/install/config/enable-services.sh> · <https://github.com/basecamp/omarchy/blob/master/migrations/1784568652.sh> · <https://github.com/basecamp/omarchy/blob/master/install/hardware/network.sh>

---

## Stop Wi-Fi dropping every few minutes by disabling power save

`wifi-drops-every-few-minutes-powersave` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** "Every 5 or so minutes, my wifi disconnects, no matter what WiFi I'm on." The connection reassociates by itself after a delay, or needs a manual reconnect. It is much worse on battery, and on phone hotspots the drop happens almost every time the screen is idle.

**Cause.** NetworkManager leaves `wifi.powersave` at the driver default, which on most Intel/Realtek/MediaTek parts enables 802.11 power save. The radio sleeps between beacons; APs (especially phone hotspots and consumer routers with aggressive client timeouts) then age the station out and the driver has to reassociate.

> ⚠️ **Risk.** Disabling Wi-Fi power save measurably increases idle battery drain on laptops.

**Fix.**

Test it live first — if drops stop, this is your cause:

```bash
iw dev wlan0 get power_save
sudo iw dev wlan0 set power_save off
```

Make it permanent through NetworkManager (`2` = disable, `3` = enable):

```bash
sudo tee /etc/NetworkManager/conf.d/20-wifi-powersave.conf >/dev/null <<'EOF'
[connection]
wifi.powersave = 2
EOF
sudo systemctl restart NetworkManager
```

On Intel cards you can also disable the driver-level power scheme:

```bash
sudo tee /etc/modprobe.d/iwlwifi-power.conf >/dev/null <<'EOF'
options iwlmvm power_scheme=1
options iwlwifi power_save=0
EOF
sudo reboot
```

**Verify.** `iw dev wlan0 get power_save` prints `Power save: off` after a reboot, and `journalctl -u NetworkManager --since '1 hour ago' | grep -c 'disconnected'` stays at 0 over a long idle period.

Sources: <https://github.com/basecamp/omarchy/issues/3882> · <https://github.com/basecamp/omarchy/issues/2925> · <https://man.archlinux.org/man/NetworkManager.conf.5>

---

## Recover a Bluetooth adapter that vanishes from the USB bus when turned off

`bluetooth-adapter-disappears-after-rfkill-block` · severity: **medium** · frequency: **common** · applies to: `arch`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Turning Bluetooth off from the panel makes the adapter disappear entirely instead of just powering down. `bluetoothctl list` returns nothing, `/sys/class/bluetooth/` is empty, the controller is gone from `lsusb`, and the bar widget vanishes so there is no way to turn it back on. `rfkill list` shows only a platform switch:

```
0: tpacpi_bluetooth_sw: Bluetooth
        Soft blocked: yes
        Hard blocked: no
```

Kernel log at the moment of the toggle: `kernel: usb 3-10: USB disconnect, device number 5`.

**Cause.** `omarchy-bluetooth-power off` runs `rfkill block bluetooth`, which is a **type-wide** `RFKILL_OP_CHANGE_ALL`. On ThinkPads (`thinkpad_acpi`) and Dells (`dell-laptop`) that also blocks the platform switch, and the embedded controller responds by cutting USB power to the Bluetooth module — so `hci0` leaves the kernel entirely rather than going `Powered: no`.

**Fix.**

Bring it back from a terminal:

```bash
sudo rfkill unblock bluetooth
sleep 3                       # re-enumeration + firmware load takes ~2.5s
bluetoothctl list
sudo systemctl restart bluetooth
```

Avoid the type-wide block in future by blocking only the adapter's own switch:

```bash
rfkill list bluetooth         # note the index of the hciN entry, not the platform switch
sudo rfkill block <index>
```

Or power it down through BlueZ instead of rfkill, which never touches the platform switch:

```bash
bluetoothctl power off
bluetoothctl power on
```

On hardware where unblock alone does not re-enumerate (some Dell Latitudes), a suspend/resume cycle brings the radio back:

```bash
systemctl suspend
```

**Verify.** `bluetoothctl list` shows the controller and `lsusb | grep -i bluetooth` lists the module again; `bluetoothctl show | grep Powered` reports `Powered: yes`.

Sources: <https://github.com/basecamp/omarchy/issues/7936> · <https://github.com/basecamp/omarchy/issues/6956> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-restart-bluetooth>

---

## Pair a Bluetooth keyboard that needs a displayed passkey

`bluetooth-passkey-pairing-fails-in-panel` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Pairing a Bluetooth keyboard (e.g. Logitech MX Mechanical Mini) from the GUI panel never completes. The panel does not show the six-digit passkey, the device flips repeatedly between "paired" and "connected", and the keyboard never becomes usable. The user journal shows the prompt going to a headless agent instead:

```
bt-agent[1184]: Authorize this device pairing (yes/no)? Device: MX MCHNCL M (XX:XX:XX:XX:XX:XX)
```

**Cause.** The pairing agent that registered with BlueZ does not implement `DisplayPasskey`/`KeyboardDisplay` capability, so BlueZ has nowhere to render the six digits the keyboard is waiting for. The pairing negotiation stalls and BlueZ tears it down and retries.

**Fix.**

Pair interactively with an agent that can display the passkey:

```bash
# stop the panel/agent from racing you
systemctl --user stop bt-agent.service

bluetoothctl
```

Then, at the `[bluetooth]#` prompt:

```
power on
agent KeyboardDisplay
default-agent
scan on
# put the keyboard into pairing mode, note its MAC when it appears
pair AA:BB:CC:DD:EE:FF
# type the displayed six digits on the Bluetooth keyboard, then press Enter
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
scan off
quit
```

Then restart the agent: `systemctl --user start bt-agent.service`.

**Verify.** `bluetoothctl info AA:BB:CC:DD:EE:FF` shows `Paired: yes`, `Bonded: yes`, `Trusted: yes`, `Connected: yes`, and the keyboard types.

Sources: <https://github.com/basecamp/omarchy/issues/8485> · <https://github.com/basecamp/omarchy/issues/7879>

---

## Stop bt-agent.service restart-looping after the Quattro upgrade

`bt-agent-service-restart-loop-missing-bluez-tools` · severity: **medium** · frequency: **common** · applies to: `arch`, `hyprland`, `omarchy`, `wayland`

**Symptom.** After upgrading to Omarchy Quattro, the journal fills up — hundreds of restarts per hour:

```
bt-agent.service: Unable to locate executable '/usr/bin/bt-agent': No such file or directory
bt-agent.service: Failed at step EXEC spawning /usr/bin/bt-agent: No such file or directory
bt-agent.service: Main process exited, code=exited, status=203/EXEC
bt-agent.service: Failed with result 'exit-code'.
```

Bluetooth pairing prompts also stop appearing.

**Cause.** `/usr/bin/bt-agent` comes from the `bluez-tools` package, not `bluez-utils`. The Quattro migration removes `blueberry` with `pacman -Rns`, which cascades and removes `gnome-bluetooth` and `bluez-tools` as now-orphaned dependencies, then enables the user unit `bt-agent.service`. `omarchy-settings` does not depend on `bluez-tools`, so nothing keeps the binary installed.

**Fix.**

```bash
sudo pacman -S --needed bluez-tools
systemctl --user restart bt-agent.service
systemctl --user status bt-agent.service
```

If you do not want the agent at all (you pair via `bluetoothctl` or the panel):

```bash
systemctl --user disable --now bt-agent.service
```

**Verify.** `systemctl --user status bt-agent.service` shows `active (running)` with no restart counter, and `journalctl --user -u bt-agent -n 20` no longer shows 203/EXEC.

Sources: <https://github.com/basecamp/omarchy/issues/6992>

---

## Fix a Samba/CIFS mount failing with mount error(112): Host is down

`cifs-mount-error-112-host-is-down` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Mounting a Windows or NAS share fails immediately:

```
mount error(112): Host is down
Refer to the mount.cifs(8) manual page (e.g. man mount.cifs) and kernel log messages (dmesg)
```

The server pings fine and is reachable from other machines. Sometimes the first symptom instead is `mount: /mnt/share: bad option; ... helper program not found` or `mount error(13): Permission denied`.

**Cause.** Despite the wording, error 112 is almost always a protocol dialect mismatch, not an unreachable host. Since kernel v4.13.5 the client negotiates the highest dialect ≥ 2.1 and SMB1 is no longer requested by default; older NAS boxes and printers that only speak SMB1 answer with nothing the client accepts. `helper program not found` means the `cifs-utils` package is missing entirely.

> **Audit corrected this record.** The diagnosis matches mount.cifs(8), which confirms the client has negotiated only SMB2.1+ by default since v4.13.5 and that SMB1 is no longer requested — so error 112 as a dialect mismatch is right, as is 'helper program not found' meaning cifs-utils is absent. Two concrete defects: `install -m600 /dev/null /etc/samba/credentials-nas` fails outright when /etc/samba does not exist, which is the normal state on a box with cifs-utils but not samba — the copy-paste dies there. And the record offers `vers=1.0` with no security warning, while the man page explicitly says SMB1 has 'much weaker security'.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `vers=1.0` enables SMB1, which the man page calls much weaker security. Use it only on an isolated LAN device that supports nothing newer. Also: a credentials file must be `chmod 600` — plaintext passwords in a world-readable fstab or credentials file expose the account.

**Fix.**

```bash
sudo pacman -S --needed cifs-utils
```

Probe which dialect the server accepts, newest first — stop at the first that works:

```bash
sudo mkdir -p /mnt/share
sudo mount -t cifs //192.168.1.50/share /mnt/share -o username=me,vers=3.1.1
sudo mount -t cifs //192.168.1.50/share /mnt/share -o username=me,vers=3.0
sudo mount -t cifs //192.168.1.50/share /mnt/share -o username=me,vers=2.0
```

Only if none of those work, and understanding that SMB1 is unauthenticated-downgrade-prone and should never cross an untrusted network:

```bash
sudo mount -t cifs //192.168.1.50/share /mnt/share -o username=me,vers=1.0,sec=ntlmssp
```

Create the credentials file with `-D` so the directory is created too:

```bash
sudo install -Dm600 /dev/null /etc/samba/credentials-nas
sudo tee /etc/samba/credentials-nas >/dev/null <<'EOF'
username=me
password=secret
domain=WORKGROUP
EOF
sudo chmod 600 /etc/samba/credentials-nas    # tee does not change mode, but verify
```

fstab entry (substitute the `vers=` that actually worked):

```
//192.168.1.50/share  /mnt/share  cifs  credentials=/etc/samba/credentials-nas,vers=3.0,uid=1000,gid=1000,file_mode=0644,dir_mode=0755,noauto,nofail,_netdev,x-systemd.automount,x-systemd.idle-timeout=600  0 0
```

```bash
sudo systemctl daemon-reload
sudo systemctl start mnt-share.automount
ls /mnt/share
```

**Verify.** `mount | grep cifs` shows the share mounted with the expected `vers=`, files are readable, and `dmesg | tail` has no new CIFS errors.

Sources: <https://man.archlinux.org/man/mount.cifs.8> · <https://man.archlinux.org/man/systemd.mount.5>

---

## Make DHCP-provided search domains work for short local hostnames

`dhcp-search-domain-ignored` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** Short local names do not resolve. `ping thing` fails while `ping thing.example.net` works, on a network whose DHCP server hands out `example.net` as the search domain. The only thing that helps is hand-editing `/etc/resolv.conf` to say `search example.net` and adding the local `nameserver` — which the next reconnect wipes out.

**Cause.** A pinned global DNS provider (Omarchy's `20-omarchy-dns.conf` plus `DNS=` in `resolved.conf`) replaces the DHCP-supplied nameserver, and with the DHCP resolver gone the DHCP search domain is not applied either. `resolv.conf` ends up with `search .` and a public resolver that knows nothing about your local zone.

**Fix.**

Return to DHCP-supplied DNS so the search domain comes with it:

```bash
omarchy dns DHCP        # Omarchy 4.x; writes only DNSOverTLS=no and clears the NM override
sudo systemctl restart systemd-resolved NetworkManager
```

If you want to keep a custom resolver but still get the domain, set both explicitly on the profile:

```bash
sudo nmcli connection modify "<SSID>" ipv4.ignore-auto-dns no
sudo nmcli connection modify "<SSID>" ipv4.dns-search "example.net"
sudo nmcli connection up "<SSID>"
```

And to route just that zone at your local resolver while everything else goes upstream:

```bash
sudo resolvectl dns wlan0 192.168.1.1
sudo resolvectl domain wlan0 example.net
```

**Verify.** `resolvectl status wlan0` lists `DNS Domain: example.net`, and `getent hosts thing` resolves to the local address.

Sources: <https://github.com/basecamp/omarchy/issues/1870> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-dns> · <https://man.archlinux.org/man/systemd-resolved.service.8>

---

## Reconnect after an interface rename orphans your NetworkManager profile

`interface-renamed-orphans-networkmanager-profile` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** After an update, a BIOS change, or plugging in a new PCIe/NVMe card, the network no longer comes up on its own. The saved connection is still listed by `nmcli connection show` but never activates, and `nmcli connection up "<name>"` fails with `Connection '<name>' is not available on device <iface> because profile is not compatible with device`. `ip link` shows an interface with a *different* name than before — `wlan0` where you had `wlp3s0`, or `enp4s0` where you had `enp3s0`, or `wwp0s20f0u3` where you had `enp0s20f0u3`.

**Cause.** NetworkManager profiles can be pinned to a device by `connection.interface-name`. When the kernel or udev renames the interface, the pin no longer matches anything and the profile becomes unusable. Renames happen for several ordinary reasons: predictable interface names are derived from PCI topology, so adding or removing a PCIe device can make the firmware renumber the bus (systemd issue 33347); a `.link` file shipped by a package can change the policy — installing `iwd` alone is enough, because it ships `/usr/lib/systemd/network/80-iwd.link` with `NamePolicy=keep kernel`, which suppresses predictable naming for *all* wlan interfaces and leaves them as `wlan0`; and a kernel change can reclassify a device into a different prefix entirely.

> ⚠️ **Risk.** Renaming an interface with a custom `.link` file means `99-default.link` no longer applies to that device, so any other property it would have set is lost. If you rename a device that firewall rules or a `wg-quick` config refer to by name, those rules silently stop matching — grep for the old name across `/etc` before you commit: `sudo grep -rn '<oldname>' /etc/ --include='*.conf' --include='*.rules' --include='fstab'`.

**Fix.**

Establish what changed:

```bash
ip -br link
nmcli -f NAME,UUID,TYPE,DEVICE connection show
grep -r 'interface-name' /etc/NetworkManager/system-connections/
ls -l /usr/lib/systemd/network/*.link /etc/systemd/network/*.link 2>/dev/null
udevadm test-builtin net_setup_link /sys/class/net/<iface>
```

**Quickest fix — unpin the profile** so it binds to whatever device of the right type is present:

```bash
nmcli connection modify "<name>" connection.interface-name ""
nmcli connection up "<name>"
```

**Better for machines with more than one NIC — pin to the MAC instead of the name**, which survives every rename:

```bash
# wired
nmcli connection modify "<name>" 802-3-ethernet.mac-address AA:BB:CC:DD:EE:FF
# wireless
nmcli connection modify "<name>" 802-11-wireless.mac-address AA:BB:CC:DD:EE:FF
nmcli connection modify "<name>" connection.interface-name ""
```

Get the permanent address from `ip -br link` or `ethtool -P <iface>` (not the randomised one).

**Or nail the name down** so it never moves again. A `.link` file ordered before `99-default.link`:

```ini
# /etc/systemd/network/10-net0.link
[Match]
PermanentMACAddress=aa:bb:cc:dd:ee:ff

[Link]
Name=net0
```

```bash
sudo udevadm trigger --verbose --subsystem-match=net --action=add
```

**If installing iwd renamed your wireless interface** and you would rather keep predictable names, mask its link file:

```bash
sudo ln -s /dev/null /etc/systemd/network/80-iwd.link
sudo reboot
```

After any of these, update anything else that referenced the old name — `/etc/fstab` `_netdev` mounts, firewall rules (`ufw status numbered`), `wg-quick` `PostUp` lines, and systemd-networkd `[Match] Name=` stanzas.

**Verify.** `nmcli -f NAME,DEVICE connection show --active` shows the profile bound to the current interface. `ip -br addr` shows an address on it. Reboot once and confirm it comes up unattended.

Sources: <https://wiki.archlinux.org/title/Network_configuration> · <https://wiki.archlinux.org/title/Iwd> · <https://wiki.archlinux.org/title/NetworkManager> · <https://networkmanager.dev/docs/api/latest/NetworkManager.conf.html>

---

## Disable MAC randomization for hotspots and MAC-registered networks

`mac-randomization-breaks-hotspot-and-portal-networks` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Tethering to a phone hotspot "often disconnects automatically and I have to manually reconnect", while the same laptop is stable on home/office Wi-Fi. On university, hotel or corporate networks that register your device by MAC, you get kicked back to the sign-in page every reconnect and have to re-register.

**Cause.** NetworkManager randomizes the MAC address during scanning (`wifi.scan-rand-mac-address` defaults to `yes`) and can also use a per-connection random MAC. A phone hotspot or MAC-whitelisted AP sees a different station each time, so the lease/registration does not carry over and the association is treated as a new (often rejected) client.

> ⚠️ **Risk.** Pinning the permanent MAC removes the privacy benefit of randomization — you become trackable across public networks.

**Fix.**

```bash
sudo tee /etc/NetworkManager/conf.d/25-mac-stable.conf >/dev/null <<'EOF'
[device]
wifi.scan-rand-mac-address=no

[connection]
wifi.cloned-mac-address=permanent
ethernet.cloned-mac-address=permanent
EOF
sudo systemctl restart NetworkManager
```

Or for just one network, leaving randomization on elsewhere:

```bash
sudo nmcli connection modify "<SSID>" wifi.cloned-mac-address permanent
sudo nmcli connection up "<SSID>"
```

**Verify.** `ip link show wlan0 | grep link/ether` matches the hardware MAC in `ethtool -P wlan0` both while scanning and while connected, and reconnecting to the hotspot no longer prompts for re-registration.

Sources: <https://github.com/basecamp/omarchy/issues/4607> · <https://man.archlinux.org/man/NetworkManager.conf.5>

---

## Fix SSH and HTTPS that hang mid-transfer on a VPN, PPPoE line or hotspot

`pmtu-blackhole-large-transfers-hang` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Small things work and big things stall. `ping` succeeds, DNS resolves, an SSH banner appears and then the session freezes the moment you run something that prints a lot; `git clone` and `apt`/`pacman` downloads hang at a few percent forever with no error; some HTTPS sites load and others hang after the TLS handshake. It happens on a VPN (WireGuard, corporate IPsec), behind a PPPoE DSL/fibre modem, or on certain hotel and mobile hotspots — and the same machine is fine on other networks.

**Cause.** A path MTU black hole. Something on the path has an MTU smaller than yours, the router that needs to fragment sets the DF bit and drops the packet, and the ICMP "fragmentation needed" message that would tell your kernel to shrink is filtered out somewhere. Path MTU Discovery never completes, so your host keeps sending full-size segments into a hole. Small packets (ping, DNS, the SSH banner, the TLS handshake) fit and get through; anything at full MSS does not. PPPoE takes 8 bytes off 1500, and WireGuard takes 60 (IPv4) or 80 (IPv6) — the Arch WireGuard page describes this exact signature: ICMP ping works because of its low packet size while most TCP connections fail.

> ⚠️ **Risk.** Lowering MTU costs a little throughput on paths that did not need it, so scope the change to the connection profile that is broken rather than applying it globally. Do not set an MTU below 1280 on any interface carrying IPv6 — it is below the protocol minimum and will break IPv6 outright.

**Fix.**

Find the largest payload that actually survives the path. `-M do` sets DF, and IPv4 header + ICMP header is 28 bytes, so working MTU = payload + 28:

```bash
ping -M do -s 1472 -c 3 1.1.1.1      # 1472 + 28 = 1500
ping -M do -s 1452 -c 3 1.1.1.1      # 1480
ping -M do -s 1392 -c 3 1.1.1.1      # 1420
ping -M do -s 1272 -c 3 1.1.1.1      # 1300
```

The smallest size that fails prints `Frag needed and DF set (mtu = NNNN)` or just times out. Walk down until one succeeds, then set that.

**Ethernet, via NetworkManager:**

```bash
nmcli connection modify "<connection-name>" 802-3-ethernet.mtu 1400
nmcli connection up "<connection-name>"
```

**Wi-Fi, via NetworkManager:**

```bash
nmcli connection modify "<connection-name>" 802-11-wireless.mtu 1400
nmcli connection up "<connection-name>"
```

(`mtu` is documented for both settings as "If non-zero, only transmit packets of the specified size or smaller". `0` restores the default.)

**PPPoE:** the ceiling is 1492. Anything above that will black-hole by definition.

**WireGuard:** set it in the interface, not on the underlying NIC:

```ini
# /etc/wireguard/wg0.conf
[Interface]
Address = 10.200.200.2/24
MTU = 1420
PrivateKey = <key>
```

```bash
sudo wg-quick down wg0 && sudo wg-quick up wg0
ip link show wg0 | grep mtu
```

1420 is the WireGuard default; drop to 1380, then 1280 if the tunnel itself is riding over PPPoE or a mobile link. 1280 is the IPv6 minimum and is the safe floor — `wg-quick` refuses to create the interface below it.

**Set it without a manager (one-off test):**

```bash
sudo ip link set dev wlan0 mtu 1400
```

**If this machine routes for others** (a Tailscale subnet router, a hotspot, a container host), clamp TCP MSS to the real path MTU instead of guessing per-client:

```bash
sudo iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN \
  -j TCPMSS --clamp-mss-to-pmtu
```

Make it persistent through your firewall's own config rather than a raw `iptables` call at boot.

**Verify.** `ip link show <iface>` reports the new MTU. `ping -M do -s $((MTU-28)) -c 3 1.1.1.1` succeeds while one byte larger fails. Then reproduce the original failure: `ssh <host> 'yes | head -100000'` runs to completion, and a `git clone` of a real repository finishes.

Sources: <https://wiki.archlinux.org/title/WireGuard> · <https://wiki.archlinux.org/title/Network_configuration> · <https://networkmanager.dev/docs/api/latest/settings-802-3-ethernet.html> · <https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html>

---

## Make 6 GHz / Wi-Fi 6E and the upper 5 GHz channels visible again

`six-ghz-channels-missing-world-regdomain` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A Wi-Fi 6E or Wi-Fi 7 card sees the 2.4 GHz and lower 5 GHz SSIDs but never the 6 GHz one, even though a phone standing next to it connects to it. Or 5 GHz networks are visible but will not associate — the log shows `send auth to xx:xx (try 1/3)`, `authenticated`, `associated`, then immediately `deauthenticating ... by local choice (Reason: 3=DEAUTH_LEAVING)`. `iw reg get` reports `global / country 00: DFS-UNSET` with every band tagged `PASSIVE-SCAN`, and `iw list` shows the channels as `no IR`.

**Cause.** Country `00` is the world regulatory domain: a lowest-common-denominator ruleset in which nearly every 5 GHz range is passive-scan / no-IR (no initiating radiation) and the whole 6 GHz band is simply absent. The card may legally listen but not transmit, so it can beacon-scan and never associate — and 6 GHz channels it is not permitted to use are never even enumerated. The kernel only leaves country 00 if `wireless-regdb` is installed and something actually sets a country. Intel cards muddy this: they are *self-managed* (Location Aware Regulatory), carry their own table in firmware, and are unaffected by `iw reg set` on the global domain — `iw reg get` prints a separate `phy#0 (self-managed)` block for them.

> **Audit corrected this record.** The cause is accurate and I confirmed it from the primary data rather than memory. In wireless-regdb's db.txt, `country 00:` has no 6 GHz range at all and every 5 GHz range carries NO-IR, exactly as claimed; `country US:` does have a 6 GHz range. The self-managed claim is right too — `iw reg get` on this Intel machine prints a `global` block followed by a separate `phy#0 (self-managed)` block, precisely the shape the record describes. `wireless-regdb` really does own /etc/conf.d/wireless-regdom and /usr/lib/udev/rules.d/85-regulatory.rules (which RUNs /usr/bin/set-wireless-regdom on cfg80211 module add), so the sed and the reboot advice are sound. `linux-firmware-intel` is a real Arch package and does contain /usr/lib/firmware/intel/iwlwifi (390 files), so that is not a fabricated package name. `pacman -S --needed wireless-regdb` after `omarchy update` is safe: I read /usr/bin/omarchy-update-pacman-guard and it only aborts when BOTH sync and sysupgrade are present, so a plain `-S` is not blocked. TWO DEFECTS. (1) The `country=` line in /etc/wpa_supplicant/wpa_supplicant.conf is inert on Omarchy: Arch's wpa_supplicant.service runs `/usr/bin/wpa_supplicant -u -s -O /run/wpa_supplicant` with no `-c`, so under NetworkManager that file is never read. Telling a user to edit it sends them chasing a no-op. (2) The verify criteria are wrong on two counts I checked live. regulatory.db supplies only a max-EIRP figure, so a country-set global block prints `(N/A, 23)` style entries — `(6, 22)` only ever appears in the self-managed Intel block, so "real EIRP figures such as (6, 22)" will never be satisfied by setting a country. And with country US set on this machine the 5925–7125 MHz range still shows `NO-OUTDOOR, PASSIVE-SCAN`, because that is what US 6 GHz client rules are; a user following the stated verify would conclude the fix failed when it worked.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting a regulatory domain other than the country you are actually in is illegal in most jurisdictions and can interfere with radar, aviation and licensed services on DFS and 6 GHz channels. Set your real country. Note also that software can only ever add restrictions on top of what the card's EEPROM/firmware allows — a device with a CN EEPROM will not transmit at US power levels no matter what you set.

**Fix.**

Diagnose first — the two blocks in this output mean different things:

```bash
iw reg get
# 'global / country 00: DFS-UNSET' with NO-IR / PASSIVE-SCAN everywhere = unset
# a trailing 'phy#0 (self-managed)' block = Intel-style LAR, the global domain is not what governs that card

iw list | grep -A 40 'Frequencies:' | grep -i 'no IR\|disabled\|5955\|6135'
journalctl -kb | grep -i 'regulatory\|regdb\|cfg80211'
# 'cfg80211: failed to load regulatory.db' means wireless-regdb is missing
```

Install the database and set your country persistently. (`wireless-regdb` is already in Omarchy's base package set, so normally it is present — check before assuming it is the problem.)

```bash
# Omarchy: go through the wrapper, direct pacman -Syu is blocked by the update guard
omarchy update
sudo pacman -S --needed wireless-regdb

sudo sed -i 's/^#WIRELESS_REGDOM="US"/WIRELESS_REGDOM="US"/' /etc/conf.d/wireless-regdom
```

Uncomment exactly one line in `/etc/conf.d/wireless-regdom`, matching where you physically are. That file is read by `/usr/bin/set-wireless-regdom`, which udev runs from `/usr/lib/udev/rules.d/85-regulatory.rules` when the `cfg80211` module appears — i.e. at boot. Apply it now without rebooting:

```bash
sudo /usr/bin/set-wireless-regdom     # reads the file you just edited
iw reg get
```

Do **not** bother putting `country=` in `/etc/wpa_supplicant/wpa_supplicant.conf` on Omarchy. NetworkManager starts the supplicant as `wpa_supplicant -u -s -O /run/wpa_supplicant` with no `-c`, so that file is never read; it only applies if you run `wpa_supplicant@<iface>.service` yourself instead of NetworkManager.

If `iw reg get` shows a `(self-managed)` phy (Intel AX210/AX211/BE200 and similar), the global setting is cosmetic for that card. Its domain comes from firmware plus the country IE in nearby beacons, so make sure the firmware is current and let it associate to a 2.4/5 GHz SSID from the same AP once:

```bash
sudo pacman -S --needed linux-firmware-intel
journalctl -kb | grep -i iwlwifi | head -20
```

Two further things block 6 GHz specifically even with a correct regdomain:

1. The card must genuinely be 6E/7. An AX200 is Wi-Fi 6 (2.4/5 GHz only) and will never see 6 GHz no matter what you set. Check with `lspci -knn | grep -i network` and confirm the exact part number.
2. 6 GHz mandates WPA3-SAE with PMF required. A profile saved as WPA2-PSK will not join the 6 GHz SSID — see the WPA3/SAE record and set `802-11-wireless-security.key-mgmt sae` and `.pmf 3`.

To confirm the band opened up:

```bash
iw list | grep -E '59[0-9]{2}|6[0-9]{3}\.0 MHz' | head
nmcli device wifi list --rescan yes
```

**What success actually looks like — read this before deciding it failed.** `iw reg get` should show `country US: DFS-FCC` (or your country) instead of `country 00: DFS-UNSET`, and the 5 GHz ranges should lose their `NO-IR` flag. The power figures will still print as `(N/A, 23)`: `regulatory.db` carries only a max-EIRP number and never a max antenna gain, so the first field is always `N/A` in the global block. A pair like `(6, 22)` appears only in a `(self-managed)` phy block and is not something setting a country can produce. The US 6 GHz range `5925 - 7125` legitimately keeps `NO-OUTDOOR, PASSIVE-SCAN` even when everything is correct — that is the US client rule, and the channel is unblocked once the card hears the AP's beacon or discovers it out-of-band from the 2.4/5 GHz SSID. The real end-to-end check is that `nmcli device wifi list --rescan yes` now shows the 6 GHz SSID and the profile associates.

**Verify.** `iw reg get` shows `country XX` (not `00`) with real EIRP figures such as `(6, 22)` instead of `(N/A, 20)`, and the previously blocked ranges no longer carry `PASSIVE-SCAN`. `iw list` lists frequencies in the 5955–7115 MHz range without `no IR`. `nmcli device wifi list` then shows the 6 GHz SSID.

Sources: <https://wiki.archlinux.org/title/Network_configuration/Wireless> · <https://wiki.archlinux.org/title/NetworkManager> · <https://bbs.archlinux.org/viewtopic.php?id=295044> · <https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html>

---

## Fix a Tailscale exit node or subnet router that forwards nothing behind ufw

`tailscale-exit-node-no-internet-ufw-forward` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** You advertise the machine as an exit node, approve it in the admin console, select it on your phone — and the phone loses all internet. Tailscale itself stays connected and you can still ping the exit node's 100.x address, but nothing routes through it. A subnet router shows the same shape: the route is approved and visible, but the LAN behind it is unreachable. `sysctl net.ipv4.ip_forward` prints `1` and it still does not work.

**Cause.** Two firewall-side causes. First and dominant: ufw's default forward policy is `DROP` (`DEFAULT_FORWARD_POLICY="DROP"` in /etc/default/ufw), so packets arriving on `tailscale0` destined elsewhere are dropped in the FORWARD chain before any of your `allow` rules are consulted — those rules govern INPUT, not FORWARD. That is why `sysctl net.ipv4.ip_forward` can read `1` and nothing routes. Second: ufw runs `sysctl -e -q -p /etc/ufw/sysctl.conf` every time it starts or reloads, so for any key that file actually sets, ufw's value wins over `/etc/sysctl.d/*`. On Arch the three forwarding keys ship commented out, so ufw is not resetting your setting — but /etc/ufw/sysctl.conf is nonetheless the durable place to enable forwarding on a ufw box, because it is applied last and survives every reload. Omarchy enables ufw with `default deny incoming` out of the box, so both apply.

> **Audit corrected this record.** Every command in the fix is source-supported and I checked them against the primary pages and against this machine. https://wiki.archlinux.org/title/Uncomplicated_Firewall documents both remedies verbatim: `DEFAULT_FORWARD_POLICY="ACCEPT"` in /etc/default/ufw, and the two `-A ufw-before-forward -i <if> -j ACCEPT` / `-o` lines placed after `# End required lines` in /etc/ufw/before.rules, plus "You may also need to uncomment" exactly the three slash-syntax lines `net/ipv4/ip_forward=1`, `net/ipv6/conf/default/forwarding=1`, `net/ipv6/conf/all/forwarding=1` — which are lines 8-10 of /etc/ufw/sysctl.conf on this box, commented, character for character as the record prints them. `sudo ufw allow in on tailscale0` is recommended verbatim by the cited tailscale.com/kb/1077. I confirmed `--advertise-exit-node`, `--exit-node`, `--exit-node-allow-lan-access`, `--stateful-filtering` and `--netfilter-mode` are all real flags on `tailscale set` in cmd/tailscale/cli/set.go. /etc/default/ufw here has DEFAULT_FORWARD_POLICY="DROP" and IPT_SYSCTL=/etc/ufw/sysctl.conf, and Omarchy's install/config/firewall.sh does `ufw default deny incoming` and enables ufw — so the Omarchy framing is right. THREE INACCURACIES, all in the cause and danger text rather than the commands. (1) The cause's headline "trap" overstates: ufw applies /etc/ufw/sysctl.conf with `sysctl -e -q -p` in ufw_start, so it overrides /etc/sysctl.d only for keys it actually sets — and on Arch all three forwarding lines ship commented out, so ufw does not silently reset an ip_forward=1 you set elsewhere. The real reason the symptom survives is DEFAULT_FORWARD_POLICY=DROP. Leaving the wrong mechanism standing sends a reader hunting a reset that is not happening. (2) The danger note says /etc/ufw/before.rules is package-owned and "a ufw upgrade can replace it and silently drop your rules". `pacman -Qii ufw` lists /etc/ufw/before.rules in the backup array, so pacman preserves a modified copy and writes a .pacnew instead — the described silent loss does not occur. (3) "`ufw reload` does not always re-read `before.rules`" is wrong for current ufw: ufw_reload() in /usr/lib/ufw/ufw-init-functions is a full stop-then-start, which re-reads before.rules and re-applies IPT_SYSCTL. The disable/enable cycle is harmless but should not be sold as necessary. Also, as with the sibling record, the cited github.com/basecamp/omarchy/blob/master/install/config/firewall.sh 404s — that file lives on `quattro`, not `master`.
>
> *The Cause above was rewritten on 2026-09-01 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `DEFAULT_FORWARD_POLICY="ACCEPT"` turns the machine into an open router for *every* interface, not just `tailscale0` — on a laptop that also runs Docker or a hotspot this is a real exposure. Prefer the two targeted `ufw-before-forward` lines. Note also that `/etc/ufw/before.rules` is package-owned: a ufw upgrade can replace it and silently drop your rules, so re-check after updates. Turning on IP forwarding at all changes the machine's role on the network; do not leave it enabled on a laptop that no longer needs to be an exit node.

**Fix.**

Diagnose in this order:

```bash
tailscale status
sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
grep -E '^#?net' /etc/ufw/sysctl.conf
grep DEFAULT_FORWARD_POLICY /etc/default/ufw
sudo ufw status verbose
```

**1. Enable forwarding where ufw will not undo it.** Uncomment these in `/etc/ufw/sysctl.conf` (note the slash-separated syntax that file uses). They ship commented out on Arch, so ufw is not currently resetting anything — but this file is applied on every `ufw` start and reload, which makes it the durable place for the setting on a ufw box:

```ini
# /etc/ufw/sysctl.conf
net/ipv4/ip_forward=1
net/ipv6/conf/default/forwarding=1
net/ipv6/conf/all/forwarding=1
```

**2. Let forwarded traffic through — this is the step that actually fixes the symptom.** Either globally:

```ini
# /etc/default/ufw
DEFAULT_FORWARD_POLICY="ACCEPT"
```

or, better, only for the tunnel — add these inside the `*filter` block of `/etc/ufw/before.rules`, after the `# End required lines` marker:

```
-A ufw-before-forward -i tailscale0 -j ACCEPT
-A ufw-before-forward -o tailscale0 -j ACCEPT
```

**3. Allow the tunnel itself in.**

```bash
sudo ufw allow in on tailscale0
sudo ufw allow 41641/udp comment 'tailscale direct'
```

**4. Reload.** `sudo ufw reload` is sufficient — `ufw_reload()` performs a full stop and start, so it re-reads `before.rules` and re-applies `/etc/ufw/sysctl.conf`. Restart the daemon afterwards so it re-installs its own rules on top:

```bash
sudo ufw reload
sudo systemctl restart tailscaled
```

**5. Re-advertise:**

```bash
sudo tailscale set --advertise-exit-node
# on the client:
sudo tailscale set --exit-node=<exit-node-ip> --exit-node-allow-lan-access=true
```

Do **not** add your own MASQUERADE rule. In its default netfilter mode Tailscale installs its own NAT and filter rules; adding a competing one produces asymmetric NAT that is harder to debug than the original problem. Only if you are deliberately managing every rule yourself should you take Tailscale out of the loop:

```bash
sudo tailscale up --netfilter-mode=off
```

and then you own the forwarding, MASQUERADE and filter rules entirely.

Also stop NetworkManager fighting over the interface, which produces intermittent tailnet connectivity that looks like a firewall problem:

```bash
sudo tee /etc/NetworkManager/conf.d/99-tailscale.conf >/dev/null <<'EOF'
[keyfile]
unmanaged-devices=interface-name:tailscale0
EOF
sudo systemctl restart NetworkManager tailscaled
```

One note on maintenance: `/etc/ufw/before.rules` is listed in ufw's pacman backup array, so an upgrade will **not** overwrite your edits — it leaves your file in place and drops a `.pacnew` beside it. Check for one after a ufw update (`find /etc/ufw -name '*.pacnew'`) so you do not miss upstream changes, but your two forward rules will still be there.

**Verify.** On the exit node: `sysctl net.ipv4.ip_forward` prints `1` after a `sudo ufw disable && sudo ufw enable` cycle, and `sudo iptables -L FORWARD -n -v` shows the tailscale0 ACCEPT rules with a non-zero packet counter once a client is routing. On the client: `tailscale status` shows the exit node in use, and a public IP lookup returns the exit node's address rather than yours.

Sources: <https://wiki.archlinux.org/title/Uncomplicated_Firewall> · <https://wiki.archlinux.org/title/Tailscale> · <https://tailscale.com/kb/1103/exit-nodes> · <https://tailscale.com/kb/1077/secure-server-ubuntu> · <https://github.com/basecamp/omarchy/blob/master/install/config/firewall.sh>

---

## Fix Wi-Fi collapsing whenever a Bluetooth device is connected

`wifi-throughput-collapses-with-bluetooth-audio` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** The moment Bluetooth headphones, a mouse or a controller connect, 2.4 GHz Wi-Fi falls apart — pages stop loading, YouTube buffers forever, `ping` latency jumps from 5 ms to hundreds of ms with packet loss, and downloads drop to a trickle. Disconnect the Bluetooth device and everything is instantly normal again. Sometimes it is symmetrical: the mouse stutters and the headset drops out while a large download runs.

**Cause.** Bluetooth and 2.4 GHz Wi-Fi share the same ISM band, and on almost every laptop they share the same combo chip and the same antenna. The chip's coexistence arbiter has to time-slice between them, and when the arbitration is poor — a firmware regression, a laptop whose antenna wiring the driver cannot detect, or a headset running the airtime-hungry HFP/SCO profile — one side starves the other. This is a hardware-arbitration problem, not a configuration error, so the reliable fixes are about getting off the shared band rather than tuning software.

> ⚠️ **Risk.** Installing an additional kernel and rebooting into it is safe as long as you keep the current one installed and the Limine menu reachable — do not enable Omarchy's Direct Boot while you are testing, or you will have no way to select the other entry without going through the firmware boot menu.

**Fix.**

Confirm you are actually on 2.4 GHz:

```bash
iw dev wlan0 link | grep -i freq     # 2412-2484 MHz = 2.4 GHz, 5xxx = 5 GHz
```

**The fix that works: move Wi-Fi off 2.4 GHz.** If your AP broadcasts one SSID on both bands, pin the profile to 5 GHz — NetworkManager documents `band` as `"a"` for 5 GHz, `"bg"` for 2.4 GHz:

```bash
nmcli connection modify "<SSID>" 802-11-wireless.band a
nmcli connection up "<SSID>"
iw dev wlan0 link | grep -i freq
```

If the two bands have separate SSIDs, just connect to the 5 GHz one and set `connection.autoconnect-priority` higher on it:

```bash
nmcli connection modify "<SSID-5G>" connection.autoconnect-priority 10
```

If you must stay on 2.4 GHz, move the AP to channel 1 or 11 (the edges) rather than leaving it on "auto" — Bluetooth's adaptive frequency hopping will then have more clear room away from your channel.

**Reduce Bluetooth's airtime.** Keep the headset on A2DP rather than HFP whenever you are not on a call — HFP/SCO keeps the radio at constant duty:

```bash
pactl list cards | grep -A 3 'Active Profile'
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX a2dp-sink
```

And stop background discovery, which hops across the whole band continuously:

```bash
bluetoothctl scan off
bluetoothctl discoverable off
bluetoothctl pairable off
```

**On old Intel cards only**, the coexistence arbiter can be turned off:

```bash
echo 'options iwlwifi bt_coex_active=0' | sudo tee /etc/modprobe.d/iwlwifi-coex.conf
sudo reboot
```

Be aware this does nothing on modern hardware. `bt_coex_active` is still declared in `iwlwifi/iwl-drv.c`, but the only remaining consumer in the tree is `iwlwifi/dvm/main.c` — the iwldvm driver, which covers the 5000/6000-series cards. Everything handled by iwlmvm (7260 and newer, including AX200, AX210 and BE200) ignores it entirely, so do not expect it to help on a recent laptop despite the amount of forum advice that says otherwise.

**If this started after a kernel update**, it is likely a coexistence regression rather than your setup — Realtek RTL8852CE users tracked exactly this to the 6.11→6.12 jump. Test the LTS kernel:

```bash
omarchy update
sudo pacman -S --needed linux-lts linux-lts-headers
sudo limine-mkinitcpio
sudo reboot     # pick the LTS entry from the Limine menu
```

**Verify.** With the Bluetooth device connected and playing audio, run `ping -i 0.2 -c 300 <router-ip>` — latency should stay in single- or low-double-digit milliseconds with no loss. `iw dev wlan0 link` should report a 5 GHz frequency and a stable bitrate. A large download should hold its speed with the headset in use.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=287090> · <https://bbs.archlinux.org/viewtopic.php?id=302036> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/iwl-drv.c> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/dvm/main.c> · <https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html>

---

## Fix wg-quick failing or silently not applying DNS

`wireguard-dns-resolvconf-missing` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `sudo wg-quick up wg0` fails with:

```
/usr/bin/wg-quick: line 32: resolvconf: command not found
```

or it comes up but internal names never resolve — the tunnel carries traffic to IPs fine, but `DNS = 10.0.0.53` in the config has no visible effect and `resolvectl status wg0` lists no DNS servers.

**Cause.** `wg-quick`'s `DNS =` key is implemented purely through `resolvconf(8)`: on up it runs `resolvconf -a tun.<INTERFACE> -m 0 -x` and on down `resolvconf -d tun.<INTERFACE>`. Arch ships no `resolvconf` binary by default, and systemd-resolved's own implementation lives in the separate `systemd-resolvconf` package.

> ⚠️ **Risk.** `systemd-resolvconf` conflicts with `openresolv`. If another VPN or DNS tool pulled in `openresolv`, pacman will ask to replace it — check what depends on it (`pacman -Qi openresolv`) before confirming.

**Fix.**

Install the resolvconf shim that feeds systemd-resolved:

```bash
sudo pacman -S systemd-resolvconf
sudo systemctl enable --now systemd-resolved
sudo wg-quick down wg0; sudo wg-quick up wg0
```

Or skip resolvconf entirely and drive resolved directly from the config — remove the `DNS =` line and add hooks instead:

```ini
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <key>
Address = 10.0.0.2/24
# DNS = 10.0.0.53           <-- remove this
PostUp  = resolvectl dns %i 10.0.0.53; resolvectl domain %i '~corp.example.com'
PreDown = resolvectl revert %i

[Peer]
PublicKey = <peer-key>
Endpoint = vpn.example.com:51820
AllowedIPs = 10.0.0.0/24
```

Use `resolvectl domain %i '~.'` instead if you want every lookup to go down the tunnel.

**Verify.** `resolvectl status wg0` lists the tunnel's DNS server and routing domain; `resolvectl query intranet.corp.example.com` resolves and reports it came from `wg0`. `resolvectl status wg0` returns nothing after `wg-quick down wg0`.

Sources: <https://man.archlinux.org/man/wg-quick.8> · <https://man.archlinux.org/man/systemd-resolved.service.8>

---

## Join a WPA2-Enterprise (802.1X) network like eduroam from the command line

`wpa2-enterprise-8021x-connect-from-cli` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** University or corporate Wi-Fi cannot be joined from the GUI — the network picker only asks for a password, or connecting silently fails and the panel keeps showing the enterprise network as disconnected even after it associates. Users report "impala can't connect to school wifi using WPA2 enterprise 802.1X".

**Cause.** Lightweight Wi-Fi TUIs (`impala`, `iwctl`-only flows) and some panel versions do not expose the 802.1X fields — EAP method, phase-2 auth, identity, CA certificate, anonymous identity — that enterprise networks require. Without them wpa_supplicant has nothing to authenticate with.

> ⚠️ **Risk.** Omitting `802-1x.ca-cert` and `802-1x.domain-suffix-match` makes the client trust any RADIUS server presenting a certificate, which allows credential theft on a spoofed SSID. Always set both.

**Fix.**

Create the profile explicitly with `nmcli` (PEAP/MSCHAPv2 is the common case, e.g. eduroam):

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name eduroam ssid "eduroam" -- \
  wifi-sec.key-mgmt wpa-eap \
  802-1x.eap peap \
  802-1x.phase2-auth mschapv2 \
  802-1x.identity "you@uni.edu" \
  802-1x.anonymous-identity "anonymous@uni.edu" \
  802-1x.password "your-password" \
  802-1x.ca-cert /etc/ssl/certs/ca-certificates.crt \
  802-1x.domain-suffix-match "radius.uni.edu"

sudo nmcli connection up eduroam
```

For TTLS/PAP instead:

```bash
sudo nmcli connection modify eduroam 802-1x.eap ttls 802-1x.phase2-auth pap
sudo nmcli connection up eduroam
```

Watch authentication if it fails:

```bash
journalctl -u NetworkManager -u wpa_supplicant -f
```

**Verify.** `nmcli -f GENERAL.STATE connection show eduroam` reports `activated` and `ip addr show wlan0` has an address. `nmcli -f 802-1x connection show eduroam` shows the EAP settings you configured.

Sources: <https://github.com/basecamp/omarchy/issues/2382> · <https://github.com/basecamp/omarchy/issues/7257> · <https://man.archlinux.org/man/NetworkManager.conf.5>

---

## Unlock 5 GHz on a Broadcom BCM43602 MacBook

`bcm43602-mac-no-5ghz-missing-nvram` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `laptop`, `omarchy`, `wayland`

**Symptom.** On a 2015–2017 Intel Mac, Wi-Fi works but only ever sees and joins 2.4 GHz networks. Dual-band APs appear only once, on channel 1–11, with poor throughput (~104/144 Mbit/s at -66 dBm). 5 GHz SSIDs never show up in a scan. Kernel log:

```
brcmfmac: brcmf_fw_alloc_request: using brcm/brcmfmac43602-pcie for chip BCM43602/2
brcmfmac: brcmf_c_process_clm_blob: no clm_blob available (err=-2), device may have limited channels available
brcmfmac: brcmf_c_process_txcap_blob: no txcap_blob available (err=-2)
```

**Cause.** Almost always the regulatory domain: with none set, the driver falls back to the most restrictive world domain and `iw phy` only ever advertises Band 1 (2.4 GHz). `wireless-regdb` ships `/etc/conf.d/wireless-regdom`, `/usr/bin/set-wireless-regdom` and `/usr/lib/udev/rules.d/85-regulatory.rules`, and Omarchy's `install/hardware/set-wireless-regdom.sh` already writes a `WIRELESS_REGDOM` line derived from the timezone - so the value may be set but wrong, and it must be edited rather than appended to. The board-NVRAM theory is much weaker than it looks: `no clm_blob available` is a benign informational message on many brcmfmac parts, and on Macs `brcmfmac` falls back to the on-device NVRAM.

> **Audit corrected this record.** The regulatory-domain half is verified and is the real, reproducible fix: core/any/wireless-regdb ships /etc/conf.d/wireless-regdom, /usr/bin/set-wireless-regdom and /usr/lib/udev/rules.d/85-regulatory.rules, and omarchy's install/hardware/set-wireless-regdom.sh already writes a WIRELESS_REGDOM line from the timezone — so the record's unconditional `tee -a` appends a *second* WIRELESS_REGDOM line. The NVRAM half is weak: `no clm_blob available` is a benign informational message on many brcmfmac parts, brcmfmac falls back to the on-device NVRAM on Macs, and the record tells the user to install an unvetted binary blob from a bugzilla attachment into /usr/lib/firmware. Lead with regdom; make the NVRAM step an explicitly optional last resort.
>
> *The Cause above was rewritten on 2026-08-30 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Installing an NVRAM file for the wrong board can push out-of-spec transmit power. Only use a file matched to your exact Mac model.

**Fix.**

```bash
lspci -nn | grep -i network      # expect [14e4:43ba]
iw reg get                       # country 00 = world roaming -> 5 GHz mostly no-IR/disabled
iw phy | grep -E 'Band|MHz \[(3[6-9]|4[0-9]|1[0-6][0-9])\]' | head
```

Fix the regulatory domain first — this alone restores 5 GHz on most Macs. Replace the existing line rather than appending a duplicate:

```bash
grep -n WIRELESS_REGDOM /etc/conf.d/wireless-regdom
sudo sed -i 's/^[#[:space:]]*WIRELESS_REGDOM=.*/WIRELESS_REGDOM="US"/' /etc/conf.d/wireless-regdom   # your ISO 3166 code
grep -c '^WIRELESS_REGDOM=' /etc/conf.d/wireless-regdom   # must be exactly 1
sudo iw reg set US
iw reg get
sudo nmcli device wifi rescan && nmcli device wifi list
```

Only if 5 GHz is still absent after the regdom is correct, and only with a file you trust for your exact board, add board NVRAM:

```bash
sudo install -Dm644 brcmfmac43602-pcie.txt /usr/lib/firmware/brcm/brcmfmac43602-pcie.txt
sudo modprobe -r brcmfmac && sudo modprobe brcmfmac
dmesg | grep brcmfmac | tail
```

If that makes things worse, remove the file and reload the driver — it is not shipped by linux-firmware-broadcom and is not required for the chip to work.

**Verify.** `iw phy | grep 'Band 2'` now matches, `iw dev wlan0 link` reports a 5 GHz frequency (e.g. `freq: 5745`) and much higher rates (867/650 Mbit/s), and 5 GHz SSIDs appear in `nmcli device wifi list`.

Sources: <https://github.com/basecamp/omarchy/issues/7672> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/set-wireless-regdom.sh>

---

## Allow Docker container DNS through UFW for the 192.168 address pool

`docker-container-dns-blocked-by-ufw` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** DNS works on the host and inside most containers, but fails inside one particular devcontainer / user-defined bridge network:

```
curl: (6) Could not resolve host: registry.npmjs.org
```

Containers on `172.x` networks are fine; the broken one is on something like `192.168.0.0/20`.

**Cause.** Omarchy points the Docker daemon at `"dns": ["172.17.0.1"]` and adds a UFW rule allowing Docker DNS only from `172.16.0.0/12`. Docker's documented default local address pools also include `192.168.0.0/16` split into `/20` networks — once enough `172.x` networks exist, Docker allocates from that pool instead. Containers there still use the embedded resolver `127.0.0.11`, which forwards to `172.17.0.1:53`, and UFW drops it.

> ⚠️ **Risk.** This opens UDP/53 on the Docker bridge gateway to the whole `192.168.0.0/16` range, which includes your LAN if it uses that space. Narrow the source to the exact Docker subnet if that matters to you.

**Fix.**

```bash
sudo ufw status numbered | grep -i docker-dns
docker network inspect <network> --format '{{ (index .IPAM.Config 0).Subnet }}'

sudo ufw allow in from 192.168.0.0/16 to 172.17.0.1 port 53 proto udp comment allow-docker-dns-192
sudo ufw reload
```

Add TCP as well if anything needs DNS-over-TCP fallback:

```bash
sudo ufw allow in from 192.168.0.0/16 to 172.17.0.1 port 53 proto tcp comment allow-docker-dns-192-tcp
```

**Verify.** `docker run --rm --network <network> alpine sh -c 'nslookup registry.npmjs.org'` resolves, and `sudo ufw status` lists the new rule with a non-zero packet count after the test.

Sources: <https://github.com/basecamp/omarchy/issues/5464>

---

## Fix DNS timeouts against [::1]:53 on dual-stack networks

`ipv6-dns-timeout-stub-not-on-localhost6` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** On native dual-stack networks (mobile hotspot, Starlink) name resolution intermittently times out. Tools that print resolver details show queries going to the IPv6 loopback:

```
dial tcp: lookup proxy.golang.org on [::1]:53: read udp [fe80::...]:43058->[::1]:53: i/o timeout
```

Users end up disabling IPv6 entirely to get anything working.

**Cause.** systemd-resolved's stub listener binds `127.0.0.53:53` (and `127.0.0.54:53`) — it does **not** listen on `::1`. If `/etc/resolv.conf` is a hand-written file containing `nameserver ::1`, or an application falls back to `::1` because `/etc/resolv.conf` is not the resolved stub file, every query is sent to a port nothing is listening on and times out.

> **Audit corrected this record.** The core diagnosis is right — systemd-resolved's stub binds 127.0.0.53:53 and 127.0.0.54:53 and never ::1, so a hand-written `nameserver ::1` times out — and both symlink targets named (stub-resolv.conf vs resolv.conf) are the two real supported layouts. The last block contradicts its own framing: it says 'prefer IPv4 for resolution rather than disabling IPv6 system-wide' and then gives `ipv6.method disabled`, which disables IPv6 outright on that connection — the exact thing it just told the user not to do. Preferring IPv4 for *resolution* is a getaddrinfo precedence setting.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Disabling IPv6 per-connection is a workaround, not a fix; do not disable IPv6 globally via sysctl on networks that are IPv6-only.

**Fix.**

```bash
ls -l /etc/resolv.conf
sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
cat /etc/resolv.conf        # must show: nameserver 127.0.0.53
sudo systemctl restart systemd-resolved
resolvectl flush-caches
resolvectl status | head -20
```

If you need every consumer to see the real upstream servers rather than the stub:

```bash
sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
```

If AAAA lookups themselves are slow on that network, prefer IPv4 *results* without turning IPv6 off — edit `/etc/gai.conf` and uncomment/add:

```
precedence ::ffff:0:0/96  100
```

That only reorders getaddrinfo results; IPv6 connectivity stays up. Reserve `nmcli connection modify "<SSID>" ipv6.method disabled` for the case where you really do want IPv6 off on that one network, and be aware it is not a DNS fix.

**Verify.** `cat /etc/resolv.conf` shows `nameserver 127.0.0.53`; `resolvectl query proxy.golang.org` returns A and AAAA records immediately, and `ss -lunp | grep ':53'` shows resolved bound on 127.0.0.53.

Sources: <https://github.com/basecamp/omarchy/issues/1478> · <https://man.archlinux.org/man/systemd-resolved.service.8>

---

## Restore access to Docker containers over the tailnet after a Tailscale update

`tailscale-docker-containers-unreachable-stateful-filtering` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Containers that were reachable from other devices on the tailnet stop answering after a Tailscale upgrade — a self-hosted service on `100.x.y.z:8080` times out from the phone even though the container is up and reachable from the host itself. Containers may also stop resolving DNS. The Tailscale client surfaces the message: `Stateful filtering is enabled and Docker was detected; this may prevent Docker containers on this host from resolving DNS and connecting to Tailscale nodes.`

**Cause.** Tailscale's stateful filtering only lets traffic through that is part of a connection it already tracked. Docker's own iptables rules move packets between the bridge network and the host in a way Tailscale does not see as part of an established flow, so return traffic to containers is dropped and container DNS can fail. This is not something a Tailscale upgrade does to you any more: it was on by default only in 1.66.0 through 1.66.3, and v1.66.4 (2024-05-20) turned it back off specifically because it broke containers. The current default in `ipn/prefs.go` is still `NoStatefulFiltering: true`, i.e. filtering off. So on a modern client you are seeing this because the node was explicitly brought up with `--stateful-filtering=true`, or because a pref set during that 2024 window has persisted in the node's state ever since. On Omarchy the warning fires readily because `docker`, `docker-compose` and `ufw-docker` are all in the base package set and `docker.socket` is enabled at install, so a bridge network is there for Tailscale to detect.

> **Audit corrected this record.** The remedy is well sourced — I pulled the cited page (tailscale.com/docs/reference/messages/client/docker-stateful-filtering) and it carries the warning string verbatim and lists `tailscale set --stateful-filtering=false`, `tailscale up --netfilter-mode=off` and `dockerd --iptables=false` as the fixes, so the commands are real and current. The Omarchy framing checks out against the quattro tree and this machine: `docker`, `docker-compose` and `ufw-docker` are all in omarchy-base.packages, install/config/enable-services.sh runs `systemctl enable docker.socket`, and install/config/firewall.sh does `ufw default deny incoming` and installs ufw-docker's after.rules block. THREE DEFECTS. (1) THE CAUSE IS STALE. It says "Nothing on your side changed; the filtering default did." Stateful filtering was on by default only in Tailscale 1.66.0–1.66.3; the changelog entry for v1.66.4 (2024-05-20) reads "Linux: Stateful filtering is now off by default" precisely because it broke container DNS, and it was never re-enabled — ipn/prefs.go in tailscale main still has `NoStatefulFiltering: opt.NewBool(true)` in the defaults with the comment "The default is to not apply stateful filtering." So on any client from mid-2024 onward this is not something an upgrade turns on; it is something the operator turned on. (2) The `docker.service` override drops the `--containerd=/run/containerd/containerd.sock` argument that Arch's shipped unit passes, so dockerd stops using the system containerd.service it still Wants/Afters and spawns its own — a second, avoidable breakage bolted onto an already-advanced step. (3) The verify reads `tailscale debug prefs | grep -i statefulfilter` "shows it disabled", but the pref is the inverted `NoStatefulFiltering`, so the correct state prints `true`; as written a reader is likely to read the output backwards. Also worth flagging for the record's provenance: the third source URL, github.com/basecamp/omarchy/blob/master/install/config/firewall.sh, 404s — `master` is the Omarchy 3 tree; the file exists only on `quattro`.
>
> *The Cause above was rewritten on 2026-09-01 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Disabling stateful filtering means the machine will accept unsolicited inbound traffic from other tailnet nodes to whatever it forwards, rather than only replies to connections it initiated. That is fine on a tailnet you control with ACLs in place, and a meaningful loosening on a shared tailnet — review your ACLs before doing it. Editing `docker.service` to pass `--iptables=false` will break container networking and any ufw-docker rules if the rest of the ruleset is not written by hand; do not do that as a first move.

**Fix.**

Check whether the warning is present and what state you are actually in:

```bash
tailscale status
sudo tailscale debug prefs | grep -i statefulfilter
docker network ls
```

Read that pref carefully — it is inverted. The field is `NoStatefulFiltering`, so `"NoStatefulFiltering": true` means stateful filtering is **off** (the default), and `false` means it is **on** and is what you are hitting.

Turn stateful filtering off:

```bash
sudo tailscale set --stateful-filtering=false
```

That is persistent — it does not need re-applying after a reboot or a `tailscale down`/`up` cycle. Then confirm from another tailnet device:

```bash
# from your phone or another machine
curl -v http://100.x.y.z:8080/
```

If you would rather Docker not manage netfilter at all (advanced, and you then own every rule), keep the rest of Arch's shipped `ExecStart` intact — only add the flag, or dockerd will also stop using the system `containerd.service` and start its own:

```bash
sudo systemctl edit docker.service
```

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock --iptables=false
```

Or the mirror image — Tailscale stops writing rules and you manage them:

```bash
sudo tailscale up --netfilter-mode=off
```

On Omarchy, remember `ufw-docker` has already installed its own block in `/etc/ufw/after.rules`; if you disable Docker's iptables management you break those protections too, so prefer the single `--stateful-filtering=false` change unless you have a specific reason not to.

Verify: `sudo tailscale debug prefs | grep -i statefulfilter` prints `"NoStatefulFiltering": true`, and the client no longer emits the Docker warning. From another tailnet device, `curl http://<tailscale-ip>:<port>/` against a containerised service returns a response. Inside a container, `getent hosts archlinux.org` resolves.

**Verify.** `sudo tailscale debug prefs | grep -i statefulfilter` shows it disabled, and the Tailscale client no longer emits the Docker warning. From another tailnet device, `curl http://<tailscale-ip>:<port>/` against a containerised service returns a response. Inside a container, `getent hosts archlinux.org` resolves.

Sources: <https://tailscale.com/docs/reference/messages/client/docker-stateful-filtering> · <https://wiki.archlinux.org/title/Tailscale> · <https://github.com/basecamp/omarchy/blob/master/install/config/firewall.sh>

---

## Stop re-pairing Bluetooth devices every time you switch between Linux and Windows

`bluetooth-pairing-lost-every-windows-dualboot` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A Bluetooth mouse, keyboard, headset or controller works fine until you boot the other OS. After pairing it in Windows it will no longer connect in Linux, and after re-pairing it in Linux it stops working in Windows. `bluetoothctl connect <MAC>` reports `Failed to connect: org.bluez.Error.Failed` or the device connects and immediately drops. Removing and re-pairing works — until the next reboot into the other OS.

**Cause.** Both installations share one Bluetooth adapter and therefore one adapter MAC address, but each generates its own link key during pairing. The device remembers only the most recent key for that MAC, so whichever OS paired last owns the device and the other is locked out. Nothing is broken; the two key stores have simply diverged.

> ⚠️ **Risk.** Editing files under `/var/lib/bluetooth` while `bluetooth.service` is running will get your changes silently overwritten when the daemon flushes state — always stop the service first. Mounting the Windows partition read-write while Windows Fast Startup or hibernation is active can corrupt the NTFS filesystem; run `powercfg /h off` in Windows and do a full shutdown first, and mount read-only if you only need to read the hive (`sudo mount -o ro ...`). Back up `/var/lib/bluetooth` before editing.

**Fix.**

Pair the device in **Linux first**, then reboot into Windows and pair it there. Then copy the Windows key back into BlueZ.

**Extract the key from Linux (no Windows tooling needed).** Mount the Windows system drive and read the registry hive with `chntpw`:

```bash
sudo pacman -S --needed chntpw
sudo mkdir -p /mnt/win && sudo mount /dev/nvme0n1p3 /mnt/win
cd /mnt/win/Windows/System32/config
sudo chntpw -e SYSTEM
```

Inside `chntpw`:

```
> cd CurrentControlSet\Services\BTHPORT\Parameters\Keys
> ls                       # one subkey per adapter, named by its MAC
> cd <adapter-mac>
> ls                       # one entry per paired device
> hex <device-mac>         # non-BLE: 16 bytes, this is the link key
```

If you see `ControlSet001` instead of `CurrentControlSet`, use that. If instead of a single 16-byte `REG_BINARY` you see a subkey containing `LTK`, `IRK`, `ERand`, `EDIV`, `AuthReq`, the device is Bluetooth 5.1 / BLE and needs the extra transformations documented on the Arch Bluetooth page — read those values with `hex <value_name>`.

**Extract from Windows instead**, if you prefer: the `Keys` hive is only readable by SYSTEM, so run regedit under that account with Sysinternals PsExec (`.\PsExec64.exe -s -i regedit.exe`), navigate to `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys`, and export the adapter's key as a `.reg` file.

**Write the key into BlueZ.** Stop the daemon first so it does not overwrite your edit:

```bash
sudo systemctl stop bluetooth.service
sudo nano /var/lib/bluetooth/<ADAPTER-MAC>/<DEVICE-MAC>/info
```

For a classic (non-BLE) device, replace the key under `[LinkKey]`:

```ini
[LinkKey]
Key=0123456789ABCDEF0123456789ABCDEF
```

Uppercase hex, no spaces, no separators. For a BLE device, substitute the corresponding values under `[IdentityResolvingKey]`, `[PeripheralLongTermKey]` and `[SlaveLongTermKey]`.

```bash
sudo systemctl start bluetooth.service
bluetoothctl connect <DEVICE-MAC>
```

Some devices — notably the Logitech MX Master line and Logitech Lightspeed receivers — increment the last octet of their own MAC on each new pairing. If so, rename the directory under `/var/lib/bluetooth/<ADAPTER-MAC>/` to the incremented address that Windows recorded before restarting the daemon.

**If you want to avoid the BLE complications entirely**, force the adapter to classic transport:

```ini
# /etc/bluetooth/main.conf
[General]
ControllerMode = bredr
```

**To automate the whole thing**, the `bt-dualboot` project scripts the extraction and import (it does not support BLE), and `bluetooth-dualboot` walks you through the commands without editing files itself.

**Between two Linux installs** this is much simpler: just make `/var/lib/bluetooth/<ADAPTER-MAC>/` identical on both, by copying or symlinking.

**Verify.** Reboot into Windows, use the device, reboot back into Linux, and connect without re-pairing. `bluetoothctl info <DEVICE-MAC>` shows `Paired: yes` and `Connected: yes` in both directions across several reboots.

Sources: <https://wiki.archlinux.org/title/Bluetooth> · <https://wiki.archlinux.org/title/Dual_boot_with_Windows>

---
