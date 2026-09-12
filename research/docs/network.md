# Networking

47 problems. Sorted by severity, then by how often users hit it.

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

## Fix a brand-new Intel Wi-Fi card that finds no usable firmware

`iwlwifi-no-suitable-firmware-new-intel-card` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `intel`, `laptop`, `omarchy`

**Symptom.** Fresh install on new hardware (e.g. Dell XPS 13 with Intel Wi-Fi 7 BE213) has no Wi-Fi at all, across reboots. `journalctl -k | grep iwlwifi` shows:

```
iwlwifi 0000:00:14.3: Detected Intel(R) Wi-Fi 7 BE213 160MHz
iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-bz-b0-wh-b0-c101.ucode failed with error -2
iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-bz-b0-wh-b0-100.ucode failed with error -2
iwlwifi 0000:00:14.3: no suitable firmware found!
iwlwifi 0000:00:14.3: minimum version required: iwlwifi-bz-b0-wh-b0-100
iwlwifi 0000:00:14.3: maximum version supported: iwlwifi-bz-b0-wh-b0-c101
```

**Cause.** The `linux-firmware-intel` split package on the install media predates the ucode revision the running `iwlwifi` driver will accept for that card. Firmware acceptance is a range and both ends move. The driver declares a minimum and a maximum version it will load, and on the reported machine the ucode that eventually worked, `iwlwifi-bz-b0-wh-b0-c102.ucode`, sits ABOVE the old driver's stated maximum of `c101`. That is why a newer kernel and newer firmware are both needed and newer firmware alone is not enough. With no second NIC in the laptop this is a chicken-and-egg problem: there is no network to fetch either package over. `linux-firmware` is a metapackage that depends on twelve `linux-firmware-*` split packages, and the Intel one is a separate 139 MB download, so it can lag behind the rest on a mirror. The original reporter saw one `pacman -Syu` update every other split and leave `linux-firmware-intel` behind. A full upgrade should not do that, so treat it as a single unexplained observation and check the installed version directly rather than assuming the upgrade covered it.

> **Audit corrected this record.** Read omacom/omarchy issue 6551 in full. It supports the symptom, the chicken-and-egg cause and the sideload recovery, and it is the record's only source. Three defects, two of them Omarchy-specific. First, `sudo pacman -Syu linux linux-firmware linux-firmware-intel` cannot run on Omarchy 4. I read `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` and `/usr/bin/omarchy-update-pacman-guard` on this machine: the hook is `PreTransaction` with `AbortOnFail`, and the script aborts any pacman command line carrying both a sync and a sysupgrade flag, so the record's headline fix is refused. Second, `sudo mkinitcpio -P` fails hard here. `/etc/mkinitcpio.d/` is empty on this install and mkinitcpio 41.1-1 line 986 reads `[[ -e "${_optpreset[0]}" ]] || die 'No presets found in %s'`, so the command dies rather than rebuilding anything. The step is also unnecessary on plain Arch: the only initramfs MODULES on Omarchy come from `/etc/mkinitcpio.conf.d/` and are `nvidia*` plus `thunderbolt`, no `iwlwifi`, and Wi-Fi firmware is read from the mounted root after the initramfs has handed off. The rebuild is driven by the pacman hook `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`, owned by `limine-mkinitcpio-hook 1.37.1-1`, when the kernel package is installed. Third, the `danger` field's remedy was `run a full pacman -Syu`, which is the blocked command, so the danger was telling the reader to do the thing the guard refuses. Confirmed on this machine: `linux-firmware 20260810-2` is a metapackage and `linux-firmware-intel 20260810-2` is a separate package that owns `/usr/lib/firmware/iwlwifi-bz-b0-wh-b0-c102.ucode.zst`, the exact ucode the reporter ended up loading, so the split-package advice is right and current. From the Arch package API, `linux-firmware` in `core` is `20260910-1` and depends on twelve `linux-firmware-*` splits including `-intel`, which is 139 MB compressed. The record's version-pinned sideload filenames were the reporter's from August and are now stale, so the fix now shows current versions and how to look them up. I kept and made explicit the point the record had right and that matters: the ucode that worked, `c102`, is ABOVE the old driver's stated maximum of `c101`, so a newer kernel and newer firmware are both required and firmware alone would have been rejected. I qualified the claim that a `pacman -Syu` left `linux-firmware-intel` behind: that is one reporter's observation on one machine and is not how a full upgrade behaves, per the Arch wiki on partial upgrades, so the fix now says to check the installed version rather than presenting it as expected behaviour. Frequency moved from `common` to `occasional`: upstream labelled the issue `device specific`, it has zero comments, and it needs install media older than a just-released card plus no second NIC. Severity stays `critical` because a fresh install has no network at all. Cited URL replaced: the `basecamp/omarchy/issues/6551` path returned 404 on two of three attempts before redirecting once, so it is not a reliable citation and the canonical `omacom` URL replaces it. NOT exercised: I have no BE213 card and did not install, sideload, reboot or run mkinitcpio here, so the recovery path itself is from the issue and from reading the guard and mkinitcpio sources, not from a live run.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Installing single packages with `pacman -U` from a stale snapshot is a partial upgrade. A kernel installed that way also replaces the module tree under `/usr/lib/modules`, so the running kernel loses its modules and anything not already loaded will fail to load until you reboot. Install the kernel and its firmware in one transaction, reboot straight away, then take a full upgrade as soon as you have real network: `omarchy update` on Omarchy, `sudo pacman -Syu` on plain Arch. Never reach for `pacman -Sy linux-firmware-intel`, which is a partial upgrade in its own right.

**Fix.**

Get any temporary network first. A USB Ethernet dongle works, or USB tethering from a phone (`Settings > Personal Hotspot > USB` on iOS), where the phone appears as a `usb0` or `enp0s...` device that NetworkManager will DHCP automatically. Then take a full upgrade, which pulls the new kernel and the new firmware together.

On Omarchy:

```bash
omarchy update
```

On plain Arch, EndeavourOS or CachyOS:

```bash
sudo pacman -Syu
```

Do NOT run `sudo pacman -Syu linux linux-firmware linux-firmware-intel` on Omarchy. An ALPM hook aborts any pacman command line carrying both a sync and a sysupgrade flag:

```
Woah partner...

This looks like a direct pacman system upgrade. Omarchy updates should normally
run through:

  omarchy update
```

If you genuinely need to bypass it for one transaction:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
```

With no network at all, download a matching kernel and firmware pair on another machine and install them in ONE transaction, so the initramfs and boot entry are rebuilt once against a consistent set:

```bash
sudo pacman -U \
  /run/media/$USER/USB/linux-7.1.9.arch1-2-x86_64.pkg.tar.zst \
  /run/media/$USER/USB/linux-firmware-intel-20260910-1-any.pkg.tar.zst
sudo reboot
```

Use whatever versions are current rather than the ones above, and check on the machine doing the downloading:

```bash
curl -s https://archlinux.org/packages/core/any/linux/json/ | grep -o '"pkgver": "[^"]*"'
curl -s https://archlinux.org/packages/core/any/linux-firmware-intel/json/ | grep -o '"pkgver": "[^"]*"'
```

Do not run `sudo mkinitcpio -P` afterwards. On Omarchy 4 `/etc/mkinitcpio.d/` is empty, so it dies with `==> ERROR: No presets found in /etc/mkinitcpio.d` and rebuilds nothing. It is unnecessary on plain Arch too. Installing the kernel package fires `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`, which on Omarchy comes from `limine-mkinitcpio-hook` and rebuilds the UKI, and Wi-Fi firmware is not in the initramfs in any case because `iwlwifi` is read from the mounted root long after the initramfs has handed off.

**Verify.** ```bash
journalctl -k | grep iwlwifi
nmcli device wifi list
pacman -Q linux linux-firmware-intel
```

The kernel log carries a loaded line in place of `no suitable firmware found!`, for example `iwlwifi 0000:00:14.3: loaded firmware version 102.07fca168.0 bz-b0-wh-b0-c102.ucode op_mode iwlmld`, `nmcli device wifi list` returns networks, and `pacman -Q linux-firmware-intel` shows the version you installed rather than the one from the install media.

Sources: <https://github.com/omacom/omarchy/issues/6551> · <https://archlinux.org/packages/core/any/linux-firmware/json/> · <https://archlinux.org/packages/core/any/linux-firmware-intel/json/> · <https://wiki.archlinux.org/title/System_maintenance>

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

`/etc/resolv.conf` is the expected symlink to `/run/systemd/resolve/stub-resolv.conf`, but `systemctl status systemd-resolved` shows it `inactive (dead)`. On some machines the same total DNS failure appears with resolved active, or with resolved not installed at all, because the mid-upgrade package update left a stale `NetworkManager` daemon and `nmcli` reports a version mismatch.

**Cause.** Two paths reach the same symptom and the cited issue carries both.

The resolved path. Migration `1782002156` restarts `systemd-resolved` with `|| true` at lines 58 and 88 of `/usr/share/omarchy/migrations/1782002156.sh`, so a failed restart is swallowed and the pipeline continues. Omarchy routes all DNS through resolved: `/etc/resolv.conf` is a symlink to `../run/systemd/resolve/stub-resolv.conf`, `resolvectl status` reports `resolv.conf mode: stub`, and NetworkManager sets no `dns=` key, so it auto-detects the resolved backend and does not write `/etc/resolv.conf` itself. The `[global-dns-domain-*]` Cloudflare block in `/etc/NetworkManager/conf.d/20-omarchy-dns.conf` is pushed into NetworkManager and into `/etc/systemd/resolved.conf`, so it is not a fallback. With resolved down the symlink target does not exist and every lookup fails, including the pacman database sync in `run_final_system_package_upgrade` at `/usr/bin/omarchy-upgrade-to-quattro:1210`. The original reporter's non-standard conditions, an ext4 root so the snapshot steps failed and an EFI partition that was never mounted, are what he believes made the restart fail.

The NetworkManager path. On a machine not using resolved, the same upgrade replaces NetworkManager underneath the running daemon, which then goes stale against the new libraries. `nmcli` reports a version mismatch and asks for a restart, and until NetworkManager is restarted nothing resolves.

> **Audit corrected this record.** Read omacom/omarchy issue 8395 in full, body and its one comment. The body supports the record's symptom and cause, and I confirmed the mechanism on this Omarchy 4 workstation rather than taking it from the issue. `/usr/share/omarchy/migrations/1782002156.sh` restarts `systemd-resolved` with `|| true` at lines 58 and 88, exactly as claimed. `/etc/resolv.conf` is a symlink to `../run/systemd/resolve/stub-resolv.conf`, `resolvectl status` reports `resolv.conf mode: stub`, and `NetworkManager --print-config` shows no `dns=` key, so NetworkManager auto-selects the resolved backend and never writes `/etc/resolv.conf` itself. That settles the question the global-dns override raised: `/etc/NetworkManager/conf.d/20-omarchy-dns.conf` sets a `[global-dns-domain-*]` Cloudflare block, but `omarchy-dns` pushes those servers into NetworkManager and into `/etc/systemd/resolved.conf`, never into `resolv.conf`, so the override is no fallback. With resolved down the symlink target does not exist and every lookup fails. The failing step is `run_final_system_package_upgrade` at `/usr/bin/omarchy-upgrade-to-quattro:1210`, and it runs pacman under `OMARCHY_UPDATE_PACMAN=1`, so the ALPM guard is not what broke it. Two defects. First, the resume step. The record said `sudo pacman -Syu` then `omarchy update`. `sudo pacman -Syu` is aborted by `/usr/bin/omarchy-update-pacman-guard`, which refuses any command line carrying both a sync and a sysupgrade flag, and `omarchy update` is the routine update path rather than the 3 to 4 migration. The script's own cleanup text at `/usr/bin/omarchy-upgrade-to-quattro:374` is `Fix the error reported above and run this script again. Re-running is safe and resumes the remaining steps.`, so the correct resume is `omarchy upgrade to quattro`. Second, the cited source carries a whole branch the record dropped. The comment from @paul-fornage reports the same total DNS failure after the same upgrade on a machine not using `systemd-resolved` at all, fixed by `sudo systemctl restart NetworkManager` after `nmcli` reported a version mismatch. A reader whose resolved is active, or absent, would have been sent nowhere by the record as written, so the fix now branches on which resolver the machine actually uses. I scrutinised both `danger` clauses. The reboot warning is real and I verified its text, but `mismatched boot config` understates what the script itself says at line 372, which is that the system is part Omarchy 3 and part quattro and rebooting can leave it with no working network or desktop, so I replaced it with the verified consequence. I also added the hazard the record created and never warned about: its own static `/etc/resolv.conf` fallback outlives the emergency and silently overrides everything `omarchy dns` configures. Backed the stub-mode and NetworkManager auto-detection claims against the Arch wiki systemd-resolved page, which gives the same relative symlink form the machine has. Severity stays `critical` and frequency stays `occasional`: the reporter says the resolved path needs non-standard conditions and probably cannot be recreated, but the comment shows a second person reaching the same symptom by another route. NOT exercised: I did not run a quattro upgrade, did not stop `systemd-resolved` and did not restart `NetworkManager` on this machine, all of which would disrupt a live workstation, so the failure state itself is from the issue and from reading the migration and upgrade scripts, not from a live reproduction.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not reboot while the upgrade has printed `Upgrade incomplete - do NOT reboot.`. The script's own wording at `/usr/bin/omarchy-upgrade-to-quattro:372` is that the system is part Omarchy 3 and part Omarchy quattro, and rebooting then can leave it with no working network and no desktop. Finish the upgrade first. Separately, the static `/etc/resolv.conf` fallback outlives the emergency: it bypasses the resolved stub, so `omarchy dns` changes stop taking effect and VPN split DNS stops working until the symlink is restored.

**Fix.**

Find out which resolver the machine actually uses before changing anything:

```bash
ls -l /etc/resolv.conf
systemctl is-active systemd-resolved NetworkManager
```

If `/etc/resolv.conf` points at `stub-resolv.conf` and resolved is not active, start it:

```bash
sudo systemctl enable --now systemd-resolved
resolvectl status | head -20
getent hosts stable-mirror.omarchy.org
```

If resolved is not in use, or it is active and names still do not resolve, restart NetworkManager. The upgrade replaces it underneath the running daemon and `nmcli` will report a version mismatch:

```bash
sudo systemctl restart NetworkManager
getent hosts stable-mirror.omarchy.org
```

Then resume the upgrade rather than rebooting. Rerun the same script that failed, which is what it tells you to do and which picks up the remaining steps:

```bash
omarchy upgrade to quattro
```

Do not substitute `sudo pacman -Syu`, which an ALPM hook aborts because the command line carries both a sync and a sysupgrade flag, and do not substitute `omarchy update`, which is the routine update path and not the 3 to 4 migration.

If neither resolver will come up, get DNS back just long enough to finish by replacing the symlink with a static file:

```bash
sudo rm /etc/resolv.conf
printf 'nameserver 1.1.1.1\nnameserver 9.9.9.9\n' | sudo tee /etc/resolv.conf
```

Put the symlink back as soon as the upgrade completes, because a static file silently overrides everything `omarchy dns` configures:

```bash
sudo rm /etc/resolv.conf
sudo ln -sf ../run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
sudo systemctl restart systemd-resolved
```

**Verify.** ```bash
systemctl is-active systemd-resolved NetworkManager
resolvectl status | head -20
getent hosts stable-mirror.omarchy.org
ls -l /etc/resolv.conf
```

`getent hosts stable-mirror.omarchy.org` returns addresses, `/etc/resolv.conf` is back to the `../run/systemd/resolve/stub-resolv.conf` symlink, and `omarchy upgrade to quattro` runs to completion with no further `Could not resolve host` error.

Sources: <https://github.com/omacom/omarchy/issues/8395> · <https://wiki.archlinux.org/title/Systemd-resolved>

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

Sources: <https://wiki.archlinux.org/title/Network_configuration/Wireless> · <https://bbs.archlinux.org/viewtopic.php?id=295916> · <https://bbs.archlinux.org/viewtopic.php?id=284180> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/mediatek/mt76/mt7921/pci.c> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-hibernation-setup> · <https://raw.githubusercontent.com/torvalds/linux/master/kernel/power/suspend.c> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-hibernation-setup>

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

## Recover a link saturated by orphaned `omarchy-network-speedtest` workers

`omarchy-speedtest-orphan-workers-saturate-link` · severity: **high** · frequency: **common** · applies to: `desktop`, `laptop`, `omarchy`, `omarchy-shell`, `quickshell`

**Symptom.** After running the shell's Speed Test panel and closing it before it finished (clicking away, or the shell restarting during the test), the internet stays very slow for tens of minutes. `ps` shows several `/bin/bash /usr/share/omarchy/bin/omarchy-network-speedtest down` (or `up`) processes reparented to `systemd --user`, each with a `curl` pulling from or posting to `*.nflxvideo.net/speedtest`. Reporters measured 300 to 440 Mbit/s of sustained traffic for 31 to 47 minutes, and one upload run reached about 126 GB transmitted before it was killed. Reported on Omarchy 4.0.0-1 and 4.0.1-1 with quickshell 0.3.0 and 0.3.1.

**Cause.** Established by several reporters reading `bin/omarchy-network-speedtest` and the panel code. The script forks eight `traffic_worker` loops that run `while true` with no duration cap and no `curl --max-time`, and relies on `trap cleanup EXIT` in the parent to reap them. Hiding the panel sends SIGTERM through `Process.running = false` and then destroys the panel `Process` object in the same event-loop turn, so `QProcess` finishes the parent with SIGKILL before its trap has run and the workers are adopted by `systemd --user`. A plain SIGTERM to the parent from a terminal cleans up correctly every time, which is what isolates the leak to the panel teardown. The script is unchanged on `quattro` since 2026-07-22 and `#7598` (bound each worker) and `#9344` (keep the panel loaded during cleanup) are both open.

> **Audit corrected this record.** Confirmed on this machine (omarchy 4.0.2-1, quickshell 0.3.1-1) by reading the shipped code rather than trusting the thread. /usr/share/omarchy/bin/omarchy-network-speedtest is a symlink to /usr/bin/omarchy-network-speedtest, owned by omarchy 4.0.2-1, and is byte-identical to the file at both quattro HEAD and tag v4.0.3, whose only commits are 2026-06-29 and 2026-07-22, so no fix has landed and the record's unchanged-since claim holds. In that script I confirmed parallel=8, traffic_worker looping while true with no duration cap, curl with no --max-time, trap cleanup EXIT as the only reaper, and a sampling loop that blocks in sleep 1, which is the latency the teardown race beats. I confirmed the panel side locally too: /usr/share/omarchy/shell/plugins/panels/speedtest/manifest.json sets no keepLoaded, shell.qml:625 ties the panel Loader's active to keepLoaded or openPanelIds, and shell.qml:480-495 hide() calls close() and then drops the id in the same turn, while Panel.qml close() only sets speedTestProc.running = false and phaseTimer.interval is 5000, so a full run is about 10 s and a Run again control exists. I checked the fix patterns instead of assuming them: the worker command line is /bin/bash /usr/share/omarchy/bin/omarchy-network-speedtest down because /usr/share/omarchy/bin precedes /usr/bin in PATH, so pkill -f omarchy-network-speedtest matches the workers and nothing else on a normal system, and fetching the script's own fast.com v2 target list today returned https://ipv4-c653-sjc002-dev-ix.1.oca.nflxvideo.net/speedtest, so pkill -f 'nflxvideo.net/speedtest' does match the live curl children, which carry only the URL. The dd feeding an upload curl needs no pattern because it stops after 64 MiB or on SIGPIPE. Issue 6989 read in full with all seven comments does support every claim, including the versions 4.0.0-1 and 4.0.1-1, quickshell 0.3.0 and 0.3.1, 300 to 440 Mbit/s, 31 and 47 minutes, and about 126.7 GB, and gh confirms today that 6989 is open, 7598 is an open pull request, and 9344 is an open pull request. One thing was wrong: the fix said the workaround stops being needed once 7598 or 9344 lands, but 9344 only marks the panels keepLoaded and so fixes ordinary dismissal, leaving the shell-crash and restart path that the record's own symptom describes and that is tracked in open issue 8515, while 7598 bounds a worker to 30 s and shortens the leak rather than removing it. I rewrote the fix to separate those two paths, name 8515, and cite the 5 s phase timer behind the run-it-to-completion advice, and I filled the empty danger because the verify block tells a reader to start a real unbounded transfer. Not exercised: I did not run the speedtest, the repro, or any kill, so the QProcess destructor SIGKILL, the reparenting to systemd --user, and the claim that a terminal SIGTERM reaps cleanly every time remain from the thread and from Qt's documented destructor behaviour, not from my own measurement.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The reproduction in `verify` deliberately starts real unbounded traffic. One reported orphan run moved about 126 GB in 33 minutes, so do not run it on a metered or capped connection.

**Fix.**

Kill the leftover workers. Three reporters confirmed this restores normal throughput immediately:

```bash
pkill -f omarchy-network-speedtest
pkill -f 'nflxvideo.net/speedtest'     # ends the in-flight curl transfers straight away
```

The first pattern matches the orphaned worker shells, whose command line is `/bin/bash /usr/share/omarchy/bin/omarchy-network-speedtest down`. The second is still needed because the `curl` children carry only the fast.com target URL, and a worker shell blocked in a foreground `curl` does not act on SIGTERM until that transfer ends. The `dd` feeding an upload `curl` needs no pattern of its own, since it stops after 64 MiB or on SIGPIPE.

Until a fix ships, let a test run through to the `Run again` button before closing the panel. Each phase is capped at 5 seconds by the panel's own timer (`phaseTimer.interval: 5000` in `/usr/share/omarchy/shell/plugins/panels/speedtest/Panel.qml`), so a complete run takes about 10 seconds and leaves nothing behind. Do not restart the shell while one is running.

The two open pull requests cover different paths, so neither alone retires the workaround:

- `#9344` marks both speed test panels `keepLoaded`, which fixes ordinary panel dismissal. A shell crash or restart mid-test still orphans the workers, tracked in open issue `#8515`.
- `#7598` bounds each worker with a parent check, `curl --max-time` and a 30 second lifetime, which covers every path but shortens the leak rather than removing it.

As of 2026-09-11 neither had landed, and the shipped script is byte-identical to the one at tag `v4.0.3`.

**Verify.** ```bash
ps -e -o pid=,ppid=,cmd= | grep -F '/omarchy-network-speedtest' | grep -v grep
pgrep -af nflxvideo
```

Both should print nothing. To reproduce the leak deliberately on an unpatched shell, two reporters used:

```bash
omarchy-shell shell summon omarchy.speedtest '{}'
sleep 7
omarchy-shell shell hide omarchy.speedtest
sleep 4
ps -e -o pid=,ppid=,cmd= | grep -F '/omarchy-network-speedtest' | grep -v grep
```

Sources: <https://github.com/omacom/omarchy/issues/6989> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-network-speedtest> · <https://github.com/omacom/omarchy/pull/7598> · <https://github.com/omacom/omarchy/pull/9344> · <https://github.com/omacom/omarchy/issues/8515> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-network-speedtest> · <https://api.fast.com/netflix/speedtest/v2>

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

## Fix total DNS failure after connecting Tailscale

`tailscale-accept-dns-breaks-all-dns` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** Toggling Tailscale on breaks **all** DNS, not just MagicDNS — nothing resolves anywhere while the Tailscale widget still says "Connected". `tailscale status --json` health messages include:

```
Tailscale can't reach the configured DNS servers. Internet connectivity may be affected.
Some peers are advertising routes but --accept-routes is false
```

**Cause.** On Linux `tailscale up` defaults to `--accept-dns` on and `--accept-routes` off. Tailscale's CLI reference gives `--accept-dns` as 'Defaults to accepting DNS settings' and `--accept-routes` as off on every platform except Windows, iOS, Android and the two macOS variants. When the tailnet pushes nameservers that only exist behind a peer-advertised subnet route, the client takes the nameservers and refuses the routes that reach them, so every lookup fails rather than only MagicDNS names. This needs a tailnet that overrides or split-DNS-points at internal resolvers. A tailnet with no DNS override loses only `*.ts.net` names, not all of them.

Two Omarchy 4 details make it easy to land in. Both were read out of the shipped files on an omarchy 4.0.2-1 machine and are unchanged on tag `v4.0.3`. The installer is the only path that passes the flag, and that same command is the login gate, so skipping auth there means the pref is never written:

```bash
# /usr/share/omarchy/bin/omarchy-install-service-tailscale
sudo tailscale up --accept-routes
```

The bar widget then logs in with a flagless `tailscale up`, which applies the Linux defaults on a fresh node:

```js
// /usr/share/omarchy/shell/plugins/panels/tailscale/Model.js, loginPlan()
return { authUrl: "", command: ["tailscale", "up"] }
```

The widget parses `tailscale status --json` and ignores `Health`, so it keeps reporting Connected.

Omarchy's own DNS override is not the cause, and it is worth ruling out before chasing it. `omarchy-dns` writes a NetworkManager global override at `/etc/NetworkManager/conf.d/20-omarchy-dns.conf` and a global `DNS=` line in `/etc/systemd/resolved.conf`, and `NetworkManager.conf(5)` says a valid `[global-dns-domain-*]` block overrides the servers of active connections. NetworkManager never manages `tailscale0`, and tailscaled pushes its resolvers straight into systemd-resolved as per-link DNS on that interface, so the override does not reach them. When the tailnet overrides local DNS, tailscaled also gives `tailscale0` the route-only domain `~.`, and per `systemd-resolved.service(8)` a query is sent to the DNS servers of the best matching routing domain. `~.` matches everything, so the tailnet resolvers win over the global Cloudflare servers and take every name to an address the machine cannot reach.

> **Audit corrected this record.** The cited source was the wrong URL and the corpus copy of it was stale. `https://github.com/basecamp/omarchy/issues/6962` is a hard 404, confirmed with `curl -o /dev/null -w '%{http_code}'`. The issue lives at `https://github.com/omacom/omarchy/issues/6962` and returns 200. I read that issue and every comment in full. It supports the record closely: the reporter gives the same two health strings, `CorpDNS: true` with `RouteAll: false`, the installer-only `--accept-routes`, and the flagless widget `tailscale up`. It is still OPEN, so nothing was fixed upstream. I confirmed the two Omarchy claims myself on this machine rather than trusting the issue: `/usr/share/omarchy/bin/omarchy-install-service-tailscale` runs `sudo tailscale up --accept-routes`, and `/usr/share/omarchy/shell/plugins/panels/tailscale/Model.js` line 73 returns `["tailscale", "up"]` with no flags. Both are byte-identical on tag `v4.0.3`, fetched with `gh api`, so the record is true on the newest release and not only on the 4.0.0 the reporter ran. The flag defaults hold: Tailscale's CLI reference says `--accept-dns` 'Defaults to accepting DNS settings' and `--accept-routes` defaults off on every platform except Windows, iOS, Android and the two macOS variants. What the record misses is the Omarchy DNS stack, which is the thing a reader will chase first and waste time on. `omarchy-dns` writes a NetworkManager global override at `/etc/NetworkManager/conf.d/20-omarchy-dns.conf` and a global `DNS=1.1.1.1 ...` into `/etc/systemd/resolved.conf`, and `NetworkManager.conf(5)` states that a valid `[global-dns-domain-*]` block overrides the servers of active connections. It does NOT apply here: NetworkManager never manages `tailscale0`, and tailscaled pushes resolvers into systemd-resolved as per-link DNS. I confirmed the live shape with `resolvectl status`, `resolvectl dns` and `resolvectl domain`: Global DNS is Cloudflare, every link has zero DNS servers and `-DefaultRoute`, `/etc/resolv.conf` is a symlink to `../run/systemd/resolve/stub-resolv.conf`, `systemd-resolved` is enabled and active, and `/etc/systemd/resolved.conf.d/10-disable-multicast.conf` from omarchy-settings 4.0.2-1 sets `LLMNR=no` and `MulticastDNS=no`. Per `systemd-resolved.service(8)` a query goes to the servers of the best matching routing domain, so once tailscaled sets `~.` on `tailscale0` the tailnet resolvers take every name and the global Cloudflare servers are never consulted. That is the mechanism behind 'all DNS breaks', and it also means the symptom needs the tailnet to override local DNS, which the record does not say. I also found a real diagnostic trap by reading `current_dns_provider()` in `/usr/share/omarchy/bin/omarchy-dns`: it reads only the NM drop-in then `/etc/systemd/resolved.conf`, so `omarchy dns` prints `Cloudflare` while every lookup is going to a dead tailnet resolver. The `danger` was half right. It correctly warns about route shadowing but says nothing about the cost of the other remedy: with `--accept-dns=false` there is no DNS on `tailscale0`, so queries fall to the global Cloudflare servers `omarchy-dns` wrote, which sends internal names outside the tunnel in clear text. That belongs in a danger. Tailscale is NOT installed here (`pacman -Q tailscale` fails), so nothing about tailscaled's runtime behaviour was exercised: I did not observe `tailscale0`, did not run `tailscale` in any form, and did not reproduce the widget resetting `RouteAll`. That last point is the issue reporter's observation, attributed as such in the corrected danger rather than asserted. I set `corrected_frequency` to `occasional` because `common` overstates it: the symptom needs a tailnet that overrides DNS, resolvers that live only behind a peer-advertised subnet route, and auth skipped in the installer, and one upstream report is the whole evidence base.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `--accept-routes` makes this machine honour every subnet route advertised on the tailnet, which can shadow local LAN addresses. On a home network that overlaps a tailnet subnet, this can black-hole your own router.

`--accept-dns=false` carries a different cost on Omarchy. With no DNS left on `tailscale0`, every lookup falls back to the global servers `omarchy-dns` wrote into `/etc/systemd/resolved.conf`, which are Cloudflare's `1.1.1.1` and `1.0.0.1` on a stock install. Internal names the tailnet admin meant to keep inside the tunnel are then sent to Cloudflare in clear text, and MagicDNS names stop resolving at all.

Either pref can be undone from the bar. The widget's on and off path runs a flagless `tailscale up`, confirmed in the shipped `Model.js`, and a reporter on the cited issue traced a silently reset `RouteAll=false` to exactly that path. That reset was not reproduced here. Re-check `tailscale debug prefs` after toggling the widget.

**Fix.**

First establish that this is the tailnet resolver and not Omarchy's own DNS setting. `omarchy dns` reads only `20-omarchy-dns.conf` and `/etc/systemd/resolved.conf`, so it reports `Cloudflare` and tells you nothing about `tailscale0`:

```bash
resolvectl status tailscale0
resolvectl domain                 # a ~. on tailscale0 means every lookup goes to the tailnet
tailscale status --json | jq '.Health'
tailscale debug prefs | grep -E 'CorpDNS|RouteAll'
```

Then pick one. Accept the routes that make the pushed resolvers reachable:

```bash
sudo tailscale set --accept-routes=true
```

Or stop using tailnet DNS and keep the local resolvers:

```bash
sudo tailscale set --accept-dns=false
sudo resolvectl flush-caches
```

`sudo` is unnecessary once the installer's `sudo tailscale set --operator="$USER"` has applied.

Do not reach for `omarchy dns` to fix this. It rewrites `/etc/systemd/resolved.conf` wholesale and reloads the DNS stack without touching the per-link configuration on `tailscale0`, which is where the broken resolvers are.

**Verify.** `tailscale debug prefs` shows `RouteAll: true`, or `CorpDNS: false` if you took the other branch. `tailscale status --json | jq '.Health'` is empty or null, and `resolvectl query archlinux.org` succeeds with Tailscale connected. After `--accept-dns=false`, `resolvectl domain` no longer shows `~.` on `tailscale0` and `resolvectl status tailscale0` lists no DNS servers.

Sources: <https://github.com/omacom/omarchy/issues/6962> · <https://tailscale.com/docs/reference/tailscale-cli/up> · <https://man.archlinux.org/man/systemd-resolved.service.8> · <https://man.archlinux.org/man/NetworkManager.conf.5>

---

## Fix RTL8125 2.5GbE ethernet that never gets a DHCP lease

`rtl8125-no-dhcp-lease-tx-checksum-offload` · severity: **high** · frequency: **rare** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `omarchy`

**Symptom.** Wired ethernet shows link up and negotiates the correct speed, but never receives an IP address. `nmcli`/`networkctl` report DHCP timing out on every retry. Wi-Fi on the same machine works. The same cable and port get a lease instantly from Windows on the same hardware. `sudo tcpdump -i eno1 -n udp port 67 or port 68` shows DHCPDISCOVER going out repeatedly with zero replies.

**Cause.** One reporter traced this to TX checksum offload in the in-kernel `r8169` driver on an RTL8125D: the NIC computes bad checksums on outgoing packets, the router drops every DHCP request, and no reply ever comes back. A `tcpdump` capture cannot rule that out, because the capture is taken before the hardware inserts the checksum, so the request looks sound in the capture whatever the card later puts on the wire. The same reporter ruled out firewall rules, EEE, PCIe ASPM, the DHCP client identifier and the choice of NetworkManager versus systemd-networkd, which are the usual suspects for these symptoms. Treat the attribution as one person's diagnosis rather than a confirmed driver bug: the upstream issue is still open with no maintainer response, `r8169` on kernel 7.1 exposes no module parameters to tune this, and the only other person on the thread reports the same symptom on an Intel `e1000e` NIC, which points at something wider than one Realtek revision. The test is cheap and reversible, so it is worth trying before spending hours on the router.

> **Audit corrected this record.** Three defects, one of them fatal to checking the record at all. First, the single cited source is dead: `https://github.com/basecamp/omarchy/issues/7804` returns a hard 404 with no redirect, tested with both a browser user agent and a named tool user agent, as does every other `basecamp/omarchy/issues/<n>` path, so the rename to `omacom/omarchy` is not followed for issue URLs. The live issue is `https://github.com/omacom/omarchy/issues/7804`, opened 2026-08-22 by donutWolf and titled "Wired ethernet stopped getting a DHCP lease after upgrading to Quattro (RTL8125 NICs)", and I read it in full through the API: it supports the symptom, the cause, the ruled-out list and the `ethtool -K ... tx off` plus systemd service fix almost word for word, so the record's content was faithful and only its URL was wrong. Second, the fix cannot run as written on Omarchy 4: `ethtool` is not installed on this workstation, `/usr/bin/ethtool` does not exist, `pacman -Qo /usr/bin/ethtool` reports no owner, and it is neither a dependency nor an optional dependency of networkmanager 1.58.1-1, so `sudo ethtool -K eno1 tx off` fails with command not found and the unit's `ExecStart=/usr/bin/ethtool` would fail 203/EXEC at every boot. It is `extra/ethtool 1:7.1-1`, and the corrected fix installs it through `omarchy update` followed by `sudo pacman -S --needed ethtool`, which I confirmed is not blocked: `/usr/bin/omarchy-update-pacman-guard` aborts only when the pacman command line carries both a sync and a sysupgrade flag. Third, the persistence mechanism ignores that NetworkManager owns the connections on Omarchy. NetworkManager 1.58.1 has `ethtool.feature-tx`, which I confirmed both in `man nm-settings-nmcli` on this machine and in the upstream nm-settings-nmcli page, and it is applied during activation ahead of the first DHCP request, so it needs no `ethtool` binary and does not race. The record's device-unit approach does race, because the oneshot and NetworkManager's own activation both fire when `sys-subsystem-net-devices-<iface>.device` appears, and I confirmed such device units exist and are active here. I kept that unit as a labelled fallback and added a third route independent of any connection manager, a `.link` file using `TransmitChecksumOffload=false`, which systemd.link(5) has carried since version 245 and this machine runs systemd 261.2-1, with the default `NamePolicy` and `AlternativeNamesPolicy` lines copied from `/usr/lib/systemd/network/99-default.link` because the Arch wiki warns that only the first matching `.link` file applies and that omitting the default content can misconfigure the interface. I set `corrected_frequency` to `rare` and left severity at `high`: the evidence is one self-reported, still open issue with a single comment, that comment reports the same symptom on an `e1000e` NIC rather than a Realtek one, `modinfo -p r8169` on kernel 7.1.9 prints nothing so the driver exposes no knob for this, and the Arch wiki Ethernet page has no RTL8125 or checksum-offload section at all, so `occasional` overstated how often this is the answer while losing the network entirely is still high severity. The cause is rewritten to keep the mechanism but say whose diagnosis it is, and the danger now names the interface-rename trap in the `.link` route, which can leave a machine with no network and is a worse outcome than the offload change it was flagging. Not exercised: no RTL8125 is in this machine (the wired NIC is an Intel I219-V on `e1000e`), so no lease failure could be reproduced, and per instruction I ran no `ethtool -K`, installed nothing and changed no network configuration here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Disabling TX checksum offload moves checksumming to the CPU. The cost is negligible at 2.5 Gbit, but it is a real behaviour change, so do not apply it to a NIC that is working. The larger risk is in the persistence step rather than in the offload. A `.link` file that matches your interface and omits the default `NamePolicy` and `AlternativeNamesPolicy` lines can change the interface name, and NetworkManager's saved profile then no longer matches it, which leaves the machine with no network at all. Only the first matching `.link` file is applied, so check the result with `sudo udevadm test-builtin net_setup_link /sys/class/net/eno1` and `networkctl status eno1` before you reboot, and keep a way back in that does not depend on this NIC.

**Fix.**

Confirm the chipset and the driver first:

```bash
lspci -k | grep -A3 -i ethernet     # look for RTL8125 and "Kernel driver in use: r8169"
ip -br link show                    # the interface name, eno1 in the examples below
```

Omarchy 4 does not ship `ethtool`, so install it before testing anything. Do not reach for `pacman -Sy`, which is a partial upgrade, and note that `pacman -Syu` is aborted by Omarchy's ALPM guard:

```bash
omarchy update                      # the supported full sync and upgrade
sudo pacman -S --needed ethtool
```

Test the theory without persisting anything:

```bash
sudo ethtool -K eno1 tx off
sudo nmcli connection up "Wired connection 1"
ip addr show eno1                   # expect an IPv4 address within a few seconds
```

If that gets a lease, make it persistent. **On Omarchy 4 NetworkManager owns the connection**, so put the setting on the connection profile. NetworkManager applies it during activation, before it sends the first DHCP request, and it needs neither the `ethtool` binary nor an extra unit:

```bash
nmcli -g NAME,DEVICE connection show --active
sudo nmcli connection modify "Wired connection 1" ethtool.feature-tx off
sudo nmcli connection up "Wired connection 1"
nmcli -f ethtool connection show "Wired connection 1"
```

To undo it, clear the property rather than setting it back to `on`, so the kernel default returns:

```bash
sudo nmcli connection modify "Wired connection 1" ethtool.feature-tx ""
```

**If the machine does not use NetworkManager**, or the NIC has to come up with the offload already off before any connection manager touches it, use a systemd link file, which udev applies as the device appears. Copy the default `NamePolicy` and `AlternativeNamesPolicy` lines from `/usr/lib/systemd/network/99-default.link`, because only the first matching `.link` file is applied and dropping them can rename the interface:

```bash
sudo tee /etc/systemd/network/50-rtl8125-txoff.link >/dev/null <<'EOF'
[Match]
Driver=r8169

[Link]
NamePolicy=keep kernel database onboard slot path
AlternativeNamesPolicy=database onboard slot path mac
MACAddressPolicy=persistent
TransmitChecksumOffload=false
EOF

sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=net --action=add
```

`Driver=r8169` matches every r8169 NIC in the machine. To pin it to one card, match on the address instead with `MACAddress=aa:bb:cc:dd:ee:ff` in the `[Match]` section.

The systemd service the upstream issue suggests also works once `ethtool` is installed, but it can race the first DHCP attempt, because the service and NetworkManager both start when the device appears:

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

**Verify.** Check the setting took:

```bash
ethtool -k eno1 | grep tx-checksumming            # expect: off
nmcli -f ethtool connection show "Wired connection 1" | grep feature-tx
```

Then reboot cold and confirm the lease arrives on its own, every time:

```bash
ip addr show eno1                                 # an IPv4 address within a couple of seconds
journalctl -b -u NetworkManager | grep -i dhcp    # a lease, not repeated timeouts
```

Sources: <https://github.com/omacom/omarchy/issues/7804> · <https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html> · <https://man7.org/linux/man-pages/man5/systemd.link.5.html> · <https://wiki.archlinux.org/title/Network_configuration/Ethernet>

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

**Cause.** NetworkManager profiles can be pinned to a device by `connection.interface-name`. The 1.58 documentation for that property says setting it restricts the interfaces a connection can be used with, and that if interface names change or are reordered the connection may be applied to the wrong interface. When the name it names no longer exists, the profile becomes unusable. Renames happen for several ordinary reasons. Path-derived names such as `enp3s0` and `wlp3s0` come from PCI topology, so adding or removing a PCIe device can make the firmware renumber the bus (systemd issue 33347 reports `enp5s0` becoming `enp7s0` on Arch after a GPU swap). Onboard names such as `eno2` and `wlo1` come from a firmware-supplied index instead, so they survive PCIe changes but move if the firmware changes that index. A `.link` file shipped by a package can change the policy outright: installing `iwd` alone is enough, because it ships `/usr/lib/systemd/network/80-iwd.link` with `NamePolicy=keep kernel`, which sorts before `99-default.link` and therefore wins for all wlan interfaces and leaves them as `wlan0`. And a kernel change can reclassify a device into a different prefix entirely.

One thing masks the problem. `99-default.link` also sets `AlternativeNamesPolicy=database onboard slot path mac`, so every other candidate name is registered as a kernel alternative name and `ip` still accepts the old name after the primary name changes. The tooling looks fine. It is the NetworkManager profile that stops matching.

On Omarchy 4 nothing in the distribution renames interfaces: `/etc/systemd/network/` is empty, no Omarchy package ships a `.link` file, `iwd` is not installed, and both NICs resolve to `/usr/lib/systemd/network/99-default.link`. Omarchy 3 shipped `iwd`, which Omarchy 4 replaced with NetworkManager and `wpa_supplicant`, so the `iwd` branch below only applies if you installed it yourself.

> **Audit corrected this record.** Re-checked every load-bearing specific on this Omarchy 4 workstation (omarchy 4.0.2-1, networkmanager 1.58.1-1, systemd 261.2-1-arch, kernel 7.1.9) and against the current man pages and wiki. Most of the record holds and I kept it. Confirmed on this machine: the error string is in the shipped 1.58 binary verbatim, `strings /usr/bin/NetworkManager` yields both `Connection '%s' is not available on device %s because %s` and `profile is not compatible with device (%s)`. `man 5 systemd.link` states the first link file in lexicographic order wins and that a user file must sort before `99-default.link`, and `PermanentMACAddress=` is a real Match key. The Arch Iwd wiki reproduces `/usr/lib/systemd/network/80-iwd.link` with `NamePolicy=keep kernel` and the identical `ln -s /dev/null` mask. systemd issue 33347 is real and says what the record claims, `enp5s0` to `enp7s0` on Arch after a GPU swap. Network_configuration confirms the sort rule, the `PermanentMACAddress=` example, `udevadm trigger --verbose --subsystem-match=net --action=add`, `udevadm test-builtin net_setup_link` and its own accuracy flag behind the danger note. nmcli syntax is current for 1.58 and I verified it without touching anything, using `nmcli --offline connection modify` on a scratch keyfile: `connection.interface-name ""` removes the key (man nmcli confirms an empty value resets a property) and `802-11-wireless.mac-address` is accepted, while `802-3-ethernet.mac-address` is correctly rejected on a wifi profile, so the record's wired and wireless branching is right. All four diagnostics and all three verify commands ran here. Two real defects. (1) The fix said to get the permanent address from `ip -br link` or `ethtool -P <iface>`. Both are wrong on Omarchy 4. `ip -br link` prints the CURRENT address, and on Wi-Fi that is usually the randomized scan address, which is exactly the value the record warns against: `ip -br link` here shows wlo1 as fe:86:ef:5b:7e:d4 while `ip -d link show wlo1` shows `permaddr 3c:6a:a7:68:5c:5e`. Following the record as written would pin a throwaway MAC. And `ethtool` is not installed on Omarchy 4, confirmed that /usr/bin/ethtool does not exist and no package owns it. (2) The cause overgeneralised, saying predictable names are derived from PCI topology. True for `enp*`/`wlp*`, but both NICs here are onboard-named (`eno2`, `wlo1`) from ID_NET_NAME_ONBOARD under naming scheme v261, which does not move when a PCIe device is added. Added, because it answers whether the fix is even needed: `99-default.link` sets `AlternativeNamesPolicy=database onboard slot path mac`, so the other candidate names are registered as kernel altnames (`ip -d link show wlo1` lists `altname wlp0s20f3` and `altname wlx3c6aa7685c5e`) and `ip` still accepts the old name after a policy change, which masks the problem. The NetworkManager profile is what stops matching. Likely, not confirmed: NetworkManager 1.58 does not resolve altnames for `connection.interface-name`, since `strings` on /usr/bin/NetworkManager finds no altname literal and neither man page mentions altnames. Confirming that needs an actual rename on a test VM. Also labelled the Omarchy 4 branch, confirmed: /etc/systemd/network/ is empty, no Omarchy package ships a .link file (omarchy-settings ships only /etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf), iwd is not installed, and `udevadm info` reports ID_NET_LINK_FILE=/usr/lib/systemd/network/99-default.link for both NICs, so nothing in the distribution renames interfaces. Omarchy 3 did ship iwd, which dhh's closing comment on omacom/omarchy issue 4607 confirms Quattro replaced with NetworkManager. All four cited URLs resolve and support their claims, so nothing is removed. NOT exercised: no rename was induced and no profile was modified, added or deleted, because this is a live workstation. The repair steps themselves are unexercised and rest on the 1.58 documentation plus the offline syntax checks. severity and frequency unchanged.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Renaming an interface with a custom `.link` file means `99-default.link` no longer applies to that device, because only the first matching `.link` file is used, so every other property it would have set is lost, including `MACAddressPolicy=persistent` and `AlternativeNamesPolicy=`. The Arch wiki carries its own accuracy flag on exactly this point. If you rename a device that firewall rules or a `wg-quick` config refer to by name, those rules silently stop matching, so grep for the old name across `/etc` before you commit:

```bash
sudo grep -rn '<oldname>' /etc/ --include='*.conf' --include='*.rules' --include='fstab'
```

Every repair here interrupts the link. `nmcli connection up`, `udevadm trigger` and the reboot in the `iwd` branch all drop the interface, so do not run them against the NIC carrying your only route while you are logged in over it. Clearing `connection.interface-name` on a machine with more than one NIC of the same type lets the profile bind to whichever device activates first, which can put the wrong network on the wrong interface. Pin the MAC in that case rather than unpinning the name.

**Fix.**

Establish what changed:

```bash
ip -br link
nmcli -f NAME,UUID,TYPE,DEVICE connection show
grep -r 'interface-name' /etc/NetworkManager/system-connections/
ls -l /usr/lib/systemd/network/*.link /etc/systemd/network/*.link 2>/dev/null
udevadm info /sys/class/net/<iface> | grep -E 'ID_NET_NAME|ID_NET_LINK_FILE|ID_NET_NAMING_SCHEME'
udevadm test-builtin net_setup_link /sys/class/net/<iface>
```

`ID_NET_LINK_FILE` tells you which `.link` file actually won, which is the decisive fact.

**Quickest fix, unpin the profile** so it binds to whatever device of the right type is present:

```bash
nmcli connection modify "<name>" connection.interface-name ""
nmcli connection up "<name>"
```

**Better for machines with more than one NIC, pin to the MAC instead of the name**, which survives every rename:

```bash
# wired
nmcli connection modify "<name>" 802-3-ethernet.mac-address AA:BB:CC:DD:EE:FF
# wireless
nmcli connection modify "<name>" 802-11-wireless.mac-address AA:BB:CC:DD:EE:FF
nmcli connection modify "<name>" connection.interface-name ""
```

Get the permanent address with `ip -d link show <iface>`, which prints it as `permaddr`:

```bash
ip -d link show wlo1 | grep -o 'permaddr [0-9a-f:]*'
```

Do not read it from `ip -br link` or plain `ip link`. Those show the *current* address, and on Wi-Fi that is usually the randomized scan address, which is the one you must not pin. `ethtool -P` also works but `ethtool` is not installed on Omarchy 4.

**Or nail the name down** so it never moves again. A `.link` file ordered before `99-default.link`, because only the first matching file is applied:

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

**If installing `iwd` renamed your wireless interface** and you would rather keep predictable names, mask its link file. Omarchy 4 does not ship `iwd`, so this only applies if you installed it:

```bash
sudo ln -s /dev/null /etc/systemd/network/80-iwd.link
sudo reboot
```

After any of these, update anything else that referenced the old name: `/etc/fstab` `_netdev` mounts, firewall rules (`ufw status numbered`), `wg-quick` `PostUp` lines, and systemd-networkd `[Match] Name=` stanzas.

**Verify.** `nmcli -f NAME,DEVICE connection show --active` shows the profile bound to the current interface. `ip -br addr` shows an address on it. Reboot once and confirm it comes up unattended.

Sources: <https://wiki.archlinux.org/title/Network_configuration> · <https://wiki.archlinux.org/title/Iwd> · <https://wiki.archlinux.org/title/NetworkManager> · <https://networkmanager.dev/docs/api/latest/NetworkManager.conf.html> · <https://man.archlinux.org/man/nm-settings-nmcli.5> · <https://man.archlinux.org/man/nmcli.1> · <https://man.archlinux.org/man/systemd.link.5> · <https://github.com/systemd/systemd/issues/33347> · <https://github.com/omacom/omarchy/issues/4607>

---

## Fix SSH and HTTPS that hang mid-transfer on a VPN, PPPoE line or hotspot

`pmtu-blackhole-large-transfers-hang` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Small things work and big things stall. `ping` succeeds, DNS resolves, an SSH banner appears and then the session freezes the moment you run something that prints a lot; `git clone` and `apt`/`pacman` downloads hang at a few percent forever with no error; some HTTPS sites load and others hang after the TLS handshake. It happens on a VPN (WireGuard, corporate IPsec), behind a PPPoE DSL/fibre modem, or on certain hotel and mobile hotspots — and the same machine is fine on other networks.

**Cause.** A path MTU black hole. Something on the path has an MTU smaller than yours, the router that needs to fragment sees the DF bit and drops the packet, and the ICMP "fragmentation needed" message that would tell your kernel to shrink is filtered out somewhere along the way. Path MTU Discovery never completes, so your host keeps firing full-size segments into a hole. Small packets (ping, DNS, the SSH banner, the TLS handshake) fit and get through. Anything at full MSS does not. PPPoE takes 8 bytes off 1500, and WireGuard takes 60 for IPv4 or 80 for IPv6. The Arch WireGuard page describes this exact signature: ICMP ping works because of its low packet size while most TCP connections fail.

The filtering is almost never on your own machine. Omarchy's ufw is default-deny incoming, which makes it the obvious suspect, but `/etc/ufw/before.rules` accepts ICMP destination-unreachable in both `ufw-before-input` and `ufw-before-forward`, and "fragmentation needed" is a code of that type. Look upstream instead.

Omarchy 4 also differs from plain Arch here, and it matters for the first step. It ships `net.ipv4.tcp_mtu_probing=1` in `/etc/sysctl.d/99-omarchy-sysctl.conf`, commented "Solve common flakiness with SSH (MTU discovery on flaky links)", which is this symptom by name. The kernel documents that value as disabled by default and enabled when an ICMP black hole is detected, so on Omarchy the kernel should already probe its way down on its own. Plain Arch sets nothing and leaves the kernel default of 0, disabled. If you are on Omarchy 4 and still seeing this, either the sysctl is not in effect or the hole is on a path this host only forwards.

> **Audit corrected this record.** Every claim in the record checks out, and two Omarchy 4 facts it ignores change the first diagnostic step, so this is corrected by addition rather than by repair. Confirmed on this machine (omarchy 4.0.2-1, kernel 7.1.9-arch1-2, iputils 20250605-1, networkmanager 1.58.1-1): `ping -h` lists `-M <pmtud opt>` taking do, dont, want or probe, and the `ping` binary carries both `Frag needed and DF set (mtu = %u)` and `local error: message too long, mtu: %u`. The record quotes only the first, so I added the second, because it distinguishes a local interface limit from a real path black hole. Property names verified in `man 5 nm-settings-nmcli`: `802-3-ethernet.mtu` and `802-11-wireless.mtu` both read "If non-zero, only transmit packets of the specified size or smaller, breaking larger packets up into multiple Ethernet frames", which is what the record quotes. Read the Arch WireGuard page in full: it gives 1420 as the default, states that below 1280 wg-quick may fail to create the interface, and carries the signature near verbatim as "ICMP ping works because of its low packet size, but most of TCP connections fail because of full MTU size utilization". The arithmetic all holds: 1500 minus 8 is 1492 for PPPoE, payload plus 28 is the IPv4 MTU, and the WireGuard overheads of 60 and 80 are right.

First addition, and the substantive one. Omarchy 4 ships `net.ipv4.tcp_mtu_probing=1` in `/etc/sysctl.d/99-omarchy-sysctl.conf`, owned by `omarchy-settings 4.0.2-1` per `pacman -Qo`, under the comment "Solve common flakiness with SSH (MTU discovery on flaky links)". That is this record's headline symptom named in Omarchy's own source, and the same line is present on the upstream quattro branch. The kernel documents the value as "1 - Disabled by default, enabled when an ICMP black hole detected", and `net/ipv4/tcp_ipv4.c` never initialises `sysctl_tcp_mtu_probing`, so the built-in default is 0 and plain Arch leaves it there. Nothing under `/usr/lib/sysctl.d/` sets it, so on this machine the Omarchy drop-in is the only writer, and `sysctl net.ipv4.tcp_mtu_probing` returns 1. This is exactly the class of defect the brief asks for, a setting Omarchy assigns in a drop-in that the record ignores. It cuts both ways: on Omarchy the reader should check it before touching any MTU, and on plain Arch setting it is a cheaper remedy than the per-profile MTU edits the record jumps straight to. I also confirmed `net.ipv4.tcp_base_mss` is 1024 and `net.ipv4.tcp_mtu_probe_floor` is 48 locally, matching `TCP_BASE_MSS` and `TCP_MIN_SND_MSS` in the kernel source, which is why the new danger warns against value 2.

Second addition. Omarchy runs ufw with `DEFAULT_INPUT_POLICY="DROP"` and `ENABLED=yes`, which makes the local firewall the obvious suspect for the filtered ICMP the cause describes, and it is the wrong suspect. `/etc/ufw/before.rules` line 34 is `-A ufw-before-input -p icmp --icmp-type destination-unreachable -j ACCEPT` and line 40 is the same for `ufw-before-forward`, and fragmentation-needed is a code of destination-unreachable. `/etc/ufw/sysctl.conf` sets `net/ipv4/icmp_echo_ignore_all=0` and touches nothing MTU related. So ufw does not cause this and the cause now says so. Read unprivileged, no changes made.

Third, smaller. The record's clamping advice is correctly scoped to a machine that routes for others, so I kept it, but I named the two Omarchy specifics it leaves out. `/etc/ufw/before.rules` contains only a `*filter` table (`*filter` at line 12, `COMMIT` at line 75), so the mangle rule cannot live there, and `man ufw-framework` documents `/etc/ufw/before.init` as the initialization customization script `ufw-init` runs if present and executable, which is the right home. `/etc/default/ufw` sets `DEFAULT_FORWARD_POLICY="DROP"`, so clamping alone will not make this box route. I also changed the one-off `ip link set` example from `wlan0` to `wlo1`, because predictable naming is on here (no `net.ifnames=0` in `/proc/cmdline`, no `.link` override) and the actual device is `wlo1`.

Not exercised. I did not set an MTU, add or modify a connection, change a sysctl, run any `ping` at all, or use sudo, per the operator's instruction on a live workstation. So no path MTU black hole was induced and no remedy was observed working end to end. The MTU arithmetic, the WireGuard behaviour and the clamping rule come from the cited sources rather than from a local test. What I verified locally is version and file state: the sysctl file and its owner, the ufw rule text, the ping binary's strings and flags, the nmcli property documentation, and the interface names. All four cited URLs still resolve and all four still say what the record claims, so nothing is removed.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Lowering MTU costs a little throughput on paths that did not need it, so scope the change to the connection profile that is broken rather than applying it globally. Do not set an MTU below 1280 on any interface carrying IPv6, because it is below the protocol minimum and will break IPv6 outright. Set `net.ipv4.tcp_mtu_probing` to `1` and not `2`: at `2` probing is always on and starts from `net.ipv4.tcp_base_mss`, which defaults to 1024, so every healthy path pays for it. Add your own drop-in under `/etc/sysctl.d/` rather than editing `/etc/sysctl.d/99-omarchy-sysctl.conf`, which is owned by the `omarchy-settings` package and will be replaced on update. The `iptables` clamping rule is for a machine that forwards traffic, and on a workstation it is a no-op that looks like a fix.

**Fix.**

First, on Omarchy 4, check that the mitigation it ships is actually live. On plain Arch this is the cheapest real fix and the record's remaining steps are the fallback:

```bash
sysctl net.ipv4.tcp_mtu_probing
cat /etc/sysctl.d/99-omarchy-sysctl.conf
```

`1` means the kernel enables packetization-layer probing once it detects a black hole. `0` means it will never try. To set it on plain Arch, in a drop-in of your own rather than by editing Omarchy's file:

```bash
printf 'net.ipv4.tcp_mtu_probing=1\n' | sudo tee /etc/sysctl.d/99-local-mtu.conf
sudo sysctl --system
```

Then find the largest payload that survives the path. `-M do` sets DF, and the IPv4 header plus ICMP header is 28 bytes, so working MTU equals payload plus 28:

```bash
ping -M do -s 1472 -c 3 1.1.1.1      # 1472 + 28 = 1500
ping -M do -s 1452 -c 3 1.1.1.1      # 1480
ping -M do -s 1392 -c 3 1.1.1.1      # 1420
ping -M do -s 1272 -c 3 1.1.1.1      # 1300
```

A size too large for the path prints `Frag needed and DF set (mtu = NNNN)` when a router tells you, or simply times out when the ICMP is being filtered, which is the black hole case. A size too large for your own interface fails immediately with `local error: message too long, mtu: NNNN` instead, which is your NIC and not the path. Take the largest payload that succeeds and add 28.

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

1420 is the WireGuard default. Drop to 1380, then 1280 if the tunnel itself is riding over PPPoE or a mobile link. 1280 is the IPv6 minimum and is the safe floor, and `wg-quick` refuses to create the interface below it.

**Set it without a manager (one-off test):**

```bash
sudo ip link set dev wlo1 mtu 1400
```

**If this machine routes for others** (a Tailscale subnet router, a hotspot, a container host), clamp TCP MSS to the real path MTU instead of guessing per-client. A plain workstation behind a router is not the place for this, because nothing it sends is forwarded and the rule will never match:

```bash
sudo iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN \
  -j TCPMSS --clamp-mss-to-pmtu
```

On Omarchy, make that persistent through ufw rather than a raw `iptables` call at boot, and note two things. `/etc/ufw/before.rules` holds only a `*filter` table, so a mangle rule cannot go there. The supported home is `/etc/ufw/before.init`, which `man ufw-framework` describes as an initialization customization script that `ufw-init` executes if it exists and is executable. And `/etc/default/ufw` sets `DEFAULT_FORWARD_POLICY="DROP"`, so clamping alone will not make this machine route for anyone until forwarding is permitted as well.

**Verify.** `ip link show <iface>` reports the new MTU. `ping -M do -s $((MTU-28)) -c 3 1.1.1.1` succeeds while one byte larger fails. `sysctl net.ipv4.tcp_mtu_probing` reports `1` if you took that route. Then reproduce the original failure: `ssh <host> 'yes | head -100000'` runs to completion, and a `git clone` of a real repository finishes.

Sources: <https://wiki.archlinux.org/title/WireGuard> · <https://wiki.archlinux.org/title/Network_configuration> · <https://networkmanager.dev/docs/api/latest/settings-802-3-ethernet.html> · <https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html> · <https://www.kernel.org/doc/Documentation/networking/ip-sysctl.rst> · <https://github.com/omacom/omarchy/blob/quattro/etc/sysctl.d/99-omarchy-sysctl.conf> · <https://man.archlinux.org/man/ufw-framework.8> · <https://man.archlinux.org/man/nm-settings-nmcli.5>

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

> **Audit corrected this record.** The primary fix is work Omarchy 4 already does, and does more safely than the record's commands. Confirmed on this machine: `/usr/share/omarchy/bin/omarchy-network-band` exists and `omarchy network band` runs, and it is in upstream `v4.0.3` at `bin/omarchy-network-band`. Reading it, it checks the SSID is actually reachable on the requested band before pinning, and on failure it restores the previous `802-11-wireless.band` and reconnects, with the comment "rather than leaving the machine stranded offline". The record's bare `nmcli connection modify ... band a` followed by `nmcli connection up` has neither guard, and the consequence, a laptop pinned to a band its AP does not serve with the setting surviving reboot, is missing from `danger` entirely. That is the main correction. The script also handles `6GHz`, which NetworkManager has accepted since 1.44 and the record does not mention, and a 6 GHz pin is strictly better for Bluetooth coexistence than 5 GHz.

The record's coexistence analysis is right and I extended it. `modinfo -p iwlwifi` on kernel 7.1.9 on this machine still lists `bt_coex_active`, so the parameter exists. A GitHub code search of torvalds/linux master for `bt_coex_active` under `drivers/net/wireless/intel/iwlwifi` returns five files: `iwl-modparams.h` and `iwl-drv.c` for the declaration, `dvm/main.c` and `dvm/lib.c` where it has real effect, and `mvm/mac80211.c` where line 461 only logs `iwlmvm doesn't allow to disable BT Coex, check bt_coex_active module parameter`. The record named only `dvm/main.c`. More importantly, kernel 7.1 ships a third driver, `iwlmld` (present at `/lib/modules/7.1.9-arch1-2/kernel/drivers/net/wireless/intel/iwlwifi/mld`), which does not reference `bt_coex_active` at all and configures coexistence unconditionally in `mld/coex.c` via `iwl_mld_send_bt_init_conf`. So on BE200 class hardware the parameter is not even read to complain about. The record's operational conclusion held, but its hardware boundary was a generation out of date.

The A2DP advice is correct but partly redundant on Omarchy 4, and I said so rather than dropping it. Confirmed on this machine: `~/.config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf` is installed and sets `bluez5.auto-connect = [ a2dp_sink a2dp_source ]`, and the same file is in `v4.0.3` at `config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf`. The profile name still resolves: `spa_bt_profile_name` in PipeWire's `spa/plugins/bluez5/defs.h` returns `a2dp-sink` for `SPA_BT_PROFILE_A2DP_SINK`, and `pipewire 1:1.6.8-1` with `wireplumber 0.5.15-1` is installed here, so `pactl set-card-profile ... a2dp-sink` is current rather than PulseAudio era advice.

The discovery advice is folklore on a stock Omarchy 4 machine and I cut it back. `bluetoothctl show` on this machine reports `Discoverable: no` on controller `3C:6A:A7:68:5C:62`, and `/usr/share/omarchy/default/systemd/user/bt-agent.service` documents that the adapter is only pairable while the user has the Bluetooth panel open and scanning. Nothing scans in the background, so `discoverable off` and `pairable off` recover no airtime, and `pairable off` actively fights Omarchy's own pairing flow. `omarchy-bluetooth-power` states that BlueZ never persists these properties, so none of the three commands survive a reboot anyway. `/etc/bluetooth/main.conf` is stock bluez 5.87-2 with every section empty, so Omarchy sets nothing there.

The kernel branch checks out, with one redundancy removed. I read `/usr/bin/omarchy-update-pacman-guard` and `/usr/share/omarchy/default/libalpm/hooks/00-omarchy-update-guard.hook`: the guard only aborts when both `-S` and `-u` appear in the pacman command line, so `pacman -S --needed linux-lts linux-lts-headers` passes, and the record's ordering of `omarchy update` first is the correct way to avoid a partial upgrade. `/usr/bin/limine-mkinitcpio` does exist, owned by `limine-mkinitcpio-hook`, but `80-limine-efi-deploy.hook` and `90-limine-mkinitcpio-remove-post.hook` already deploy the entry during the install transaction, so the manual call is redundant and I dropped it. `omarchy-setup-direct-boot` exists in `/usr/share/omarchy/bin`, so the existing Direct Boot warning is real and I kept it and named the command. The record's 6.11 to 6.12 RTL8852CE claim is sourced but four kernel series stale against 7.1.9, so I reframed it as a precedent rather than as current advice. `iw dev wlan0` was wrong throughout: this machine's only wireless interface is `wlo1`, with no `net.ifnames=0` on the kernel cmdline.

Both forum sources still resolve, HTTP 200 for `https://bbs.archlinux.org/viewtopic.php?id=287090` and `...id=302036`, and both raw kernel URLs return 200, so nothing is removed. Severity stays `medium` and frequency stays `common`, because unlike the power save record the distribution does not remove the underlying cause, it only gives a safer tool. Not exercised: this workstation has an Intel Wireless-AC 9560 CNVi part (`8086:a370`, subsystem `8086:0034`) paired with an Intel 9460/9560 Jefferson Peak Bluetooth controller on USB `8087:0aaa`, which is exactly the shared combo part the cause describes, but `wlo1` is down and the machine runs on `eno2`, and I was instructed not to touch NetworkManager, the radios, Bluetooth or audio. So I did not associate on 2.4 GHz, did not measure any throughput collapse or ping latency, did not pair a Bluetooth audio device (no `bluez_card.*` exists in `pactl list cards` here), and did not test any modprobe option, band pin or LTS kernel boot.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Pinning a band can leave the machine offline. `802-11-wireless.band a` on a profile whose AP has no 5 GHz radio means there is nothing to associate to, and the setting persists across reboots, so a laptop with no wired fallback has no way back on to the network until you clear it. Check the AP answers on the band first, or use `omarchy network band`, which refuses a band the SSID is not reachable on and reverts plus reconnects if the radio cannot come back up.

Installing an additional kernel and rebooting into it is safe as long as you keep the current one installed and the Limine menu reachable. Do not enable Omarchy's Direct Boot with `omarchy-setup-direct-boot` while you are testing, because it points firmware straight at the Omarchy UKI and you would then have no way to select the other entry without going through the firmware boot menu.

**Fix.**

Find the real interface name first. Omarchy 4 uses predictable names such as `wlo1` or `wlp3s0`, and `wlan0` does not exist:

```bash
iw dev | awk '/Interface/ {print $2}'
```

Use that name in place of `wlo1` below. Confirm you are actually on 2.4 GHz:

```bash
iw dev wlo1 link | grep -i freq     # 2412-2484 MHz = 2.4 GHz, 5xxx = 5 GHz
```

**The fix that works: move Wi-Fi off 2.4 GHz.**

On Omarchy 4, use the command the distribution already ships for this. It checks that the SSID is actually reachable on the band before pinning, and if the radio cannot come back up it puts the previous setting back and reconnects, so a wrong guess does not leave you offline:

```bash
omarchy network band          # show current band, what is available, what is pinned
omarchy network band 5        # pin 5 GHz
omarchy network band 6        # pin 6 GHz if the AP offers it
omarchy network band auto     # unpin
```

On plain Arch, or if you want to see the underlying property, NetworkManager takes `802-11-wireless.band` as `"a"` for 5 GHz, `"bg"` for 2.4 GHz, and since 1.44 `"6GHz"`:

```bash
nmcli -g 802-11-wireless.band connection show "<SSID>"
nmcli connection modify "<SSID>" 802-11-wireless.band a
nmcli connection up "<SSID>"
iw dev wlo1 link | grep -i freq
```

Check that the AP answers on the band before you pin it. If it does not, `nmcli connection up` fails and the profile stays pinned to a band with nothing to associate to:

```bash
nmcli -f SSID,FREQ device wifi list --rescan no | grep "<SSID>"
```

If the pin leaves you offline, put it back:

```bash
nmcli connection modify "<SSID>" 802-11-wireless.band ""
nmcli connection up "<SSID>"
```

If the two bands have separate SSIDs, connect to the 5 GHz one and give it a higher autoconnect priority:

```bash
nmcli connection modify "<SSID-5G>" connection.autoconnect-priority 10
```

If you must stay on 2.4 GHz, move the AP to channel 1 or 11 rather than leaving it on auto, so Bluetooth's adaptive frequency hopping has clear room away from your channel.

**Keep the headset on A2DP rather than HFP.** HFP and its SCO link keeps the radio at constant duty, where A2DP bursts. Omarchy 4 already asks WirePlumber to prefer the A2DP profiles on connect, in `~/.config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf`:

```
monitor.bluez.rules = [
  {
    matches = [ { device.name = "~bluez_card.*" } ]
    actions = { update-props = { bluez5.auto-connect = [ a2dp_sink a2dp_source ] } }
  }
]
```

WirePlumber still switches to HFP when an application opens the headset microphone, so check and override the live profile when you are not on a call:

```bash
pactl list cards | grep -E 'Name: bluez_card|Active Profile'
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX a2dp-sink
```

**Do not bother turning off discovery on a stock Omarchy 4 machine.** Active scanning does hop across the whole band, but Omarchy does not scan in the background. `bluetoothctl show` reports `Discoverable: no`, and `bt-agent.service` only auto-accepts pairing while you have the Bluetooth panel open and scanning. If you have started a scan by hand, stop that one scan. None of these properties persist across a reboot, because BlueZ never saves them:

```bash
bluetoothctl scan off
```

Leave `pairable` alone. Turning it off breaks Omarchy's own pairing flow and buys no airtime.

**On old Intel cards only**, the coexistence arbiter can be turned off. `bt_coex_active` is still declared in `iwlwifi/iwl-drv.c` and `modinfo -p iwlwifi` still lists it on kernel 7.1, but check which driver your card uses before spending time on it:

```bash
basename "$(readlink -f /sys/class/net/wlo1/device/driver)"
ls /sys/module | grep -E '^iwl(mvm|mld|dvm)$'
```

```bash
echo 'options iwlwifi bt_coex_active=0' | sudo tee /etc/modprobe.d/iwlwifi-coex.conf
sudo reboot
```

This only does anything under `iwldvm`, the 5000 and 6000 series cards. Under `iwlmvm` (7260 and newer through AX210) the only thing that reads the parameter is `mvm/mac80211.c`, and all it does is log `iwlmvm doesn't allow to disable BT Coex, check bt_coex_active module parameter`. Under `iwlmld`, which kernel 7.1 uses for BE200 class cards, nothing reads it at all and coexistence is configured unconditionally in `mld/coex.c`. So on any recent laptop this is a dead end, despite the amount of forum advice that says otherwise.

**If this started right after a kernel update**, suspect a coexistence regression rather than your setup. Realtek RTL8852CE users tracked exactly this to the 6.11 to 6.12 jump, which is the cited precedent rather than current advice against kernel 7.1. Test the LTS kernel, which installs alongside the one you have:

```bash
omarchy update
sudo pacman -S --needed linux-lts linux-lts-headers
sudo reboot
# pick the LTS entry from the Limine menu
```

Run `omarchy update` first. `pacman -S` on its own uses the sync databases as they stand, so a fully updated system is the only state in which it cannot pull a partial upgrade. The Omarchy ALPM guard does not block this command, because it only aborts when both `-S` and `-u` are present. Pacman's own Limine hooks deploy the new entry, so there is no need to run `limine-mkinitcpio` by hand.

**Verify.** With the Bluetooth device connected and playing audio, measure latency and loss against the router rather than against the internet:

```bash
ping -i 0.2 -c 300 <router-ip>
```

Latency should stay in single or low double digit milliseconds with no loss. Then confirm the band actually moved:

```bash
omarchy network band            # Omarchy 4
iw dev wlo1 link | grep -i freq   # any Arch: expect 5xxx or 6xxx MHz
```

A large download should hold its speed with the headset in use. If you pinned a band, reboot once and check it reassociated on that band by itself rather than falling back.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=287090> · <https://bbs.archlinux.org/viewtopic.php?id=302036> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/iwl-drv.c> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/dvm/main.c> · <https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-network-band> · <https://github.com/omacom/omarchy/blob/v4.0.3/config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/mvm/mac80211.c> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/mld/coex.c> · <https://raw.githubusercontent.com/PipeWire/pipewire/master/spa/plugins/bluez5/defs.h> · <https://man.archlinux.org/man/nm-settings-nmcli.5>

---

## Fix wg-quick failing or silently not applying DNS

`wireguard-dns-resolvconf-missing` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `sudo wg-quick up wg0` fails with:

```
/usr/bin/wg-quick: line 32: resolvconf: command not found
```

or it comes up but internal names never resolve — the tunnel carries traffic to IPs fine, but `DNS = 10.0.0.53` in the config has no visible effect and `resolvectl status wg0` lists no DNS servers.

**Cause.** `wg-quick`'s `DNS =` key is implemented entirely through `resolvconf(8)`. Arch ships no `resolvconf` binary by default, and systemd-resolved's implementation is the separate `systemd-resolvconf` package, which installs `/usr/bin/resolvconf` as a symlink to `resolvectl`. Confirmed on an omarchy 4.0.2-1 machine: `pacman -Qo /usr/bin/resolvconf` reports no owner and the file is absent.

Two details of the invocation matter and they come from the wireguard-tools source, not the man page:

```bash
# src/wg-quick/linux.bash
30  cmd() {
31    echo "[#] $*" >&2
32    "$@"
...
145 resolvconf_iface_prefix() {
146   [[ -f /etc/resolvconf/interface-order && ! -L $(type -P resolvconf) ]] || return 0
...
159   } | cmd resolvconf -a "$(resolvconf_iface_prefix)$INTERFACE" -m 0 -x
165   cmd resolvconf -d "$(resolvconf_iface_prefix)$INTERFACE" -f
```

The missing binary is reported at line 32, where `cmd` runs its arguments. And the `tun.` prefix the man page shows is conditional on openresolv's `/etc/resolvconf/interface-order` and on `resolvconf` not being a symlink, so with `systemd-resolvconf` the interface registered is the bare `wg0`. That is why `resolvectl status wg0` is the right place to look.

On Omarchy 4 the resolved side is already in place. `/etc/resolv.conf` is a symlink to `../run/systemd/resolve/stub-resolv.conf` and `systemd-resolved` is enabled and active, both confirmed on the workstation. Omarchy's own DNS override is a red herring here and worth ruling out early: `omarchy-dns` puts Cloudflare in a NetworkManager `[global-dns-domain-*]` block at `/etc/NetworkManager/conf.d/20-omarchy-dns.conf` and in a global `DNS=` line in `/etc/systemd/resolved.conf`, and `NetworkManager.conf(5)` confirms such a block overrides the servers of active connections, but `wg-quick` never goes through NetworkManager. `resolvectl(1)` maps the shim's `-x` to the route-only domain `~.`, and `systemd-resolved.service(8)` sends a query to the servers of the best matching routing domain, so once the shim is installed the tunnel's resolvers beat the global Cloudflare ones for every name.

> **Audit corrected this record.** The premise holds and the symptom is right down to the line number, but the cause mis-states the invocation, the fix has a partial-upgrade hazard, and the danger names the wrong conflict and omits a DNS leak that Omarchy makes certain. Both cited sources resolve (200) and both support what they are cited for: `wg-quick.8` documents that `DNS =` runs `resolvconf -a tun.INTERFACE -m 0 -x` on up and `resolvconf -d tun.INTERFACE` on down, and offers `PostUp`/`PostDown` as the alternative, explicitly allowing each to be given more than once. Neither is removed. Confirmed on this machine: `pacman -Qo /usr/bin/resolvconf` reports no owner, the file does not exist, and neither `openresolv` nor `systemd-resolvconf` is installed, so the record's whole premise is true on Omarchy 4 and not only on plain Arch. Also confirmed live: `/etc/resolv.conf` is a symlink to `../run/systemd/resolve/stub-resolv.conf`, `systemd-resolved` is enabled and active, and `/etc/systemd/resolved.conf.d/10-disable-multicast.conf` from omarchy-settings 4.0.2-1 sets `LLMNR=no` and `MulticastDNS=no`, so the resolved destination the fix targets is already in place. I read the wireguard-tools source rather than trusting the man page and found two things. `cmd()` at line 30 runs `"$@"` at line 32, which is why `line 32: resolvconf: command not found` is exactly right, so I kept the symptom untouched. And the `tun.` prefix is conditional: `resolvconf_iface_prefix` at line 145 returns nothing unless `/etc/resolvconf/interface-order` exists and `resolvconf` is not a symlink, which is openresolv's shape, so under `systemd-resolvconf` the registered interface is the bare `wg0`. The record's own `resolvectl status wg0` verify step is correct because of behaviour the cause gets wrong. `unset_dns` at line 165 also passes `-f`, which the man page omits. On the Omarchy override the operator asked about: it does not intercept here. `omarchy-dns` writes a NetworkManager `[global-dns-domain-*]` block and a global `DNS=` in `/etc/systemd/resolved.conf`, and `NetworkManager.conf(5)` confirms such a block overrides active connections, but `wg-quick` never goes through NetworkManager. `resolvectl(1)` says the shim maps `-x` to the route-only domain `~.`, and `systemd-resolved.service(8)` routes to the best matching routing domain, so the `DNS =` branch beats Cloudflare for every name. The leak is in the other branch: `systemd.network(5)` `DNSDefaultRoute=` defaults to automatic, meaning a link with DNS and no routing domain takes unmatched queries, so a user who copies `resolvectl dns %i` without `resolvectl domain %i` fans every query out to the tunnel and Cloudflare in parallel with first-answer-wins. Three fix defects. `systemd-resolvconf` depends on an exact `systemd=<version>`, verified both locally (`Depends On: systemd=261.2` against installed systemd 261.2-1) and from archlinux.org, which now serves 261.3-1 depending on `systemd=261.3`, so a bare `pacman -S` can drag systemd up alone. The instinctive repair is `-Syu`, which Omarchy blocks: I read `/usr/bin/omarchy-update-pacman-guard` and it aborts only when a command line carries both a sync and a sysupgrade flag, so plain `-S` passes and `-Syu <pkg>` does not. The danger is wrong on the conflict: `pacman -Si systemd-resolvconf` and the archlinux.org JSON both give `Conflicts With: resolvconf` and `Provides: openresolv resolvconf`, so it provides openresolv rather than conflicting with it by name, and `pacman -Qi openresolv` is the wrong check where `pacman -Qo /usr/bin/resolvconf` is the right one. The Arch wiki adds that `systemd-resolvconf` only works while `systemd-resolved.service` is running. NOT exercised: `wireguard-tools` is not installed here (`pacman -Q wireguard-tools` fails), so no tunnel was brought up, no package was installed, nothing was reverted, and `resolv.conf` was not touched. The routing and leak behaviour is derived from the man pages plus the live `resolvectl status`/`domain` output, not from a running `wg0`. Severity stays `medium`: the loud branch fails closed and nothing is destroyed.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** On Omarchy 4 the real risk is a DNS leak rather than a loud failure. `omarchy-dns` always writes global servers into `/etc/systemd/resolved.conf`, Cloudflare's `1.1.1.1` and `1.0.0.1` on a stock install. If `wg0` ends up with DNS servers and no routing domain, which is what happens if you take the `resolvectl dns %i` line without the `resolvectl domain %i` line, systemd-resolved treats the link as a default route and sends every unmatched query to the tunnel and to Cloudflare in parallel, returning whichever answers first. Internal names then leave the tunnel in clear text, and a Cloudflare `NXDOMAIN` can beat the tunnel's real answer. Check with `resolvectl domain` once the tunnel is up.

`systemd-resolvconf` conflicts with the virtual `resolvconf` provider and itself provides `openresolv`, so pacman offers to replace whatever provider is installed. Check what that is with `pacman -Qo /usr/bin/resolvconf` before confirming. Do not install `openresolv` here instead: it manages `/etc/resolv.conf` itself, which on Omarchy is a symlink into systemd-resolved's runtime directory. `systemd-resolvconf` also only works while `systemd-resolved.service` is running, so do not install it on a machine that has resolved disabled.

**Fix.**

Install the resolvconf shim that feeds systemd-resolved. `systemd-resolvconf` depends on an exact `systemd=<version>`, so installing it on its own can drag systemd up by itself, which is a partial upgrade. Bring the system current first. On Omarchy this also fetches the pacman sync databases, which a fresh offline install does not have:

```bash
omarchy update
sudo pacman -S --needed systemd-resolvconf
systemctl is-enabled systemd-resolved      # already enabled on a stock Omarchy 4
sudo wg-quick down wg0 || true
sudo wg-quick up wg0
```

Do not write that as `sudo pacman -Syu systemd-resolvconf`. Omarchy's guard at `/usr/bin/omarchy-update-pacman-guard` aborts any pacman command line carrying both a sync and a sysupgrade flag. A plain `-S` is not blocked.

Or skip resolvconf entirely and drive resolved from the config. `wg-quick.8` allows each hook key more than once, so keep them on separate lines:

```ini
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <key>
Address = 10.0.0.2/24
# DNS = 10.0.0.53           <-- remove this
PostUp  = resolvectl dns %i 10.0.0.53
PostUp  = resolvectl domain %i '~corp.example.com'
PreDown = resolvectl revert %i

[Peer]
PublicKey = <peer-key>
Endpoint = vpn.example.com:51820
AllowedIPs = 10.0.0.0/24
```

Keep the `resolvectl domain` line. Without it the link has DNS servers and no routing domain, which leaks queries to Omarchy's global resolvers. Use `resolvectl domain %i '~.'` instead if every lookup should go down the tunnel.

**Verify.** `resolvectl status wg0` lists the tunnel's DNS server, and `resolvectl domain` shows `~.` on `wg0` after the `DNS =` path or the configured routing domain after the `PostUp` path. `resolvectl query intranet.corp.example.com` resolves and reports it was acquired via `wg0`. `resolvectl status wg0` lists no DNS servers after `sudo wg-quick down wg0`.

Sources: <https://man.archlinux.org/man/wg-quick.8> · <https://man.archlinux.org/man/systemd-resolved.service.8> · <https://man.archlinux.org/man/resolvectl.1> · <https://man.archlinux.org/man/NetworkManager.conf.5> · <https://git.zx2c4.com/wireguard-tools/plain/src/wg-quick/linux.bash> · <https://wiki.archlinux.org/title/WireGuard> · <https://wiki.archlinux.org/title/Systemd-resolved> · <https://archlinux.org/packages/core/x86_64/systemd-resolvconf/>

---

## Join a WPA2-Enterprise (802.1X) network like eduroam from the command line

`wpa2-enterprise-8021x-connect-from-cli` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** University or corporate Wi-Fi either cannot be joined or joins and then reports itself wrong. With `impala` or `iwctl` the picker offers only a password field and the enterprise network never associates, which is what "impala can't connect to school wifi using WPA2 enterprise 802.1X" describes. On Omarchy 4 the bar panel does ask for an identity, so the failures look different. The profile it creates performs no server certificate check at all, and the panel can go on showing a working enterprise connection as `NOT CONNECTED` while `nmcli` reports it activated and the IP address, gateway, ping and traffic figures on that same panel are all correct.

**Cause.** Two different causes, and Omarchy 4 changed which one applies.

With `impala` or `iwctl`, the Omarchy 3 default, the TUI does not expose the fields an enterprise network needs, which are the EAP method, the phase 2 inner auth, the identity, the anonymous identity and the CA certificate. Those tools drive **iwd**, not wpa_supplicant, and iwd expects an 802.1X network to be described by a provisioning file it reads from `/var/lib/iwd` rather than by credentials entered at a prompt.

Omarchy 4 does not use iwd at all. Its hardware setup runs `systemctl disable iwd.service` and the stack is NetworkManager driving wpa_supplicant. Its bar panel does detect an enterprise SSID and does ask for an identity, then builds a PEAP/MSCHAPv2 profile. What it does not set is `802-1x.ca-cert` or `802-1x.domain-suffix-match`, so the profile it writes accepts any RADIUS server that answers. Separately, the panel's connected indicator misreads an active 802.1X profile and can display `NOT CONNECTED` for a connection NetworkManager considers activated. That second one is cosmetic and does not affect traffic.

> **Audit corrected this record.** Checked the whole command against `man 5 nm-settings-nmcli` and `man 1 nmcli` from networkmanager 1.58.1-1 on this machine, then executed the record's exact command under `nmcli --offline`, which builds the keyfile on stdout and never contacts the daemon. It is valid and produces a correct profile, so every property name holds for 1.58: `wifi-sec.key-mgmt wpa-eap`, `802-1x.eap peap`, `802-1x.phase2-auth mschapv2`, `802-1x.identity`, `802-1x.anonymous-identity`, `802-1x.password`, `802-1x.ca-cert`, `802-1x.domain-suffix-match`, and the `--` separator. `man 1 nmcli` states that nmcli accepts `wifi-sec` in place of `802-11-wireless-security`. The man page describes `phase2-auth` under PEAP as selecting from gtc, otp, md5 and tls, which reads as excluding mschapv2, but the combined valid-values list includes it and Omarchy 4 itself ships exactly this pairing, so the record is right and the man prose is incomplete.

Three defects, all confirmed on this machine rather than inferred. First, the symptom claim that the GUI "only asks for a password" is false on Omarchy 4. `/usr/share/omarchy/shell/plugins/panels/network/Panel.qml` computes `isEnterprise` at line 1604 and shows a field with `placeholderText: "Identity (user@domain)"` at line 1848, and `/usr/share/omarchy/shell/plugins/panels/network/Model.js` lines 319 to 326 hold `enterpriseConnectScript`, which runs `nmcli connection add ... wifi-sec.key-mgmt wpa-eap 802-1x.eap peap 802-1x.phase2-auth mschapv2 802-1x.identity "$2"`. Second, the cause is Omarchy 3 framing and contains a factual error: `impala` and `iwctl` drive iwd, not wpa_supplicant, so "wpa_supplicant has nothing to authenticate with" is wrong for those tools. Omarchy 4 ships neither. `install/hardware/network.sh` on the quattro branch runs `systemctl disable iwd.service`, `pacman -Q iwd impala` reports both absent here, `systemctl is-enabled iwd` returns not-found, nothing under `/usr/share/omarchy` mentions impala, and `wpa_supplicant` is the running supplicant (pid 1624). Third, `ifname wlan0` and `ip addr show wlan0` are wrong. Predictable naming is active (no `net.ifnames=0` in `/proc/cmdline`, no `.link` file and no `80-net-setup-link.rules` override) and the card here is `wlo1` on iwlwifi. The offline run showed the record's command baking `interface-name=wlan0` into the keyfile, which would pin the profile to a nonexistent device. Omarchy's own script omits `ifname`, and an offline run without it emits no `interface-name` line.

Two additions to `danger`, both genuine. Omarchy 4's own enterprise path sets no CA certificate and no domain-suffix-match, so the record's warning understates the situation by treating omission as the reader's mistake when it is the shipped default. And the record passes the password as an `nmcli` argument, which Omarchy explicitly avoids: the comment at Model.js lines 315 to 318 says "argv is world-readable in /proc, so the secret must never be an argument" and pipes it through `nmcli connection edit` instead. The corrected fix adopts that pattern. `802-1x.ca-cert` is documented as "This property can be unset even if the EAP method supports CA certificates, but this allows man-in-the-middle attacks and is NOT recommended", which backs the record's original instinct.

Sources. Both cited `basecamp/omarchy` issue URLs are hard 404s under curl with no redirect, so they are removed and replaced with the `omacom` equivalents. Read both in full: #2382 is the impala WPA2-Enterprise report the symptom quotes, and #7257 is the Quickshell panel showing an enterprise connection as NOT CONNECTED. #7257 is still open with no comments as of 2026-09-11, against a newest tag of v4.0.3, so that half of the symptom is a live Omarchy 4 bug. `NetworkManager.conf.5` is removed: it resolves but documents the daemon config file and says nothing about 802-1x connection properties, so it never supported the claim. `nm-settings-nmcli.5` and `nmcli.1` replace it.

Not exercised. No enterprise SSID is reachable from this workstation and I was instructed not to add a connection or use sudo, so association and EAP authentication were never performed. The Wi-Fi card `wlo1` is present and unblocked in rfkill but sits disconnected because the machine is on ethernet `eno2`. Everything above is either read from a local file, read from the upstream quattro branch, or produced by `nmcli --offline`, which alters nothing. The claim that the corrected fix successfully authenticates against a real RADIUS server is untested.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** An 802.1X profile with no `802-1x.ca-cert` and no `802-1x.domain-suffix-match` trusts any RADIUS server that presents a certificate, which is all an attacker needs to harvest the credentials from a spoofed SSID. Set both. This is not hypothetical on Omarchy 4: the bar panel's own enterprise connect path sets neither, so a profile created from the GUI needs both added afterwards. Putting the password on an `nmcli` command line is a second exposure, because `/proc/<pid>/cmdline` is world readable while the command runs and the line also enters shell history. Set the secret over stdin with `nmcli connection edit`. Prefer the CA your institution publishes over `/etc/ssl/certs/ca-certificates.crt`, because the system bundle lets any publicly trusted CA vouch for the RADIUS server and `802-1x.domain-suffix-match` is then the only thing standing between you and a mis-issued certificate.

**Fix.**

Build the profile with `nmcli` so every 802.1X field is set explicitly.

Leave `ifname` out. Predictable interface naming is on by default, so the device is normally `wlo1` or `wlp3s0` and almost never `wlan0`. Passing a name that does not exist bakes `interface-name=` into the profile and it will never activate. Check what you actually have:

```bash
nmcli -f DEVICE,TYPE device status | grep wifi
```

PEAP with MSCHAPv2 is the common case, eduroam included:

```bash
sudo nmcli connection add type wifi con-name eduroam ssid "eduroam" \
  wifi-sec.key-mgmt wpa-eap \
  802-1x.eap peap \
  802-1x.phase2-auth mschapv2 \
  802-1x.identity "you@uni.edu" \
  802-1x.anonymous-identity "anonymous@uni.edu" \
  802-1x.ca-cert /etc/ssl/certs/ca-certificates.crt \
  802-1x.domain-suffix-match "radius.uni.edu"
```

Set the password separately, not on that command line. `/proc/<pid>/cmdline` is world readable for the life of the process, and the line lands in shell history too. `read` and `printf` are both bash builtins, so with this form the secret never becomes an argument to any process:

```bash
read -rs -p 'EAP password: ' pw
printf 'set 802-1x.password %s\nsave\nquit\n' "$pw" \
  | sudo nmcli connection edit eduroam
unset pw
sudo nmcli connection up eduroam
```

For TTLS with PAP instead:

```bash
sudo nmcli connection modify eduroam 802-1x.eap ttls 802-1x.phase2-auth pap
sudo nmcli connection up eduroam
```

Most institutions publish their own RADIUS CA and hostname. Use that CA file rather than the whole system bundle where one is offered:

```bash
sudo nmcli connection modify eduroam \
  802-1x.ca-cert /etc/ssl/certs/your-institution-ca.pem
```

Watch the authentication if it fails:

```bash
journalctl -u NetworkManager -u wpa_supplicant -f
```

**Omarchy 4.** The bar panel (`Super + Ctrl + W`) does detect an enterprise SSID and offer an identity field, so you can join from the GUI. It builds a PEAP/MSCHAPv2 profile and sets neither `802-1x.ca-cert` nor `802-1x.domain-suffix-match`, so add both to whatever profile it left behind:

```bash
sudo nmcli connection modify "<ssid>" \
  802-1x.ca-cert /etc/ssl/certs/ca-certificates.crt \
  802-1x.domain-suffix-match "radius.uni.edu"
sudo nmcli connection up "<ssid>"
```

If that panel keeps showing `NOT CONNECTED` while `nmcli` reports the connection activated, the link is fine and the indicator is wrong. Trust `nmcli`.

**Omarchy 3, or any install using `impala` or `iwctl`.** Those drive iwd, which wants a provisioning file under `/var/lib/iwd/<ssid>.8021x` rather than credentials typed at a prompt. Switch to NetworkManager and use the commands above, which is the route Omarchy 4 took.

**Verify.** `nmcli -f GENERAL.STATE connection show eduroam` reports `activated` and `ip addr show <device>` has an address. Take the device name from `nmcli -f DEVICE,TYPE device status | grep wifi` rather than assuming `wlan0`. `nmcli -f 802-1x connection show eduroam` lists the EAP settings, and both `802-1x.ca-cert` and `802-1x.domain-suffix-match` must be non-empty there. On Omarchy 4 ignore the bar panel's connected indicator for this check and trust `nmcli`.

Sources: <https://github.com/omacom/omarchy/issues/2382> · <https://github.com/omacom/omarchy/issues/7257> · <https://man.archlinux.org/man/nm-settings-nmcli.5> · <https://man.archlinux.org/man/nmcli.1> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/panels/network/Model.js> · <https://github.com/omacom/omarchy/blob/quattro/shell/plugins/panels/network/Panel.qml> · <https://github.com/omacom/omarchy/blob/quattro/install/hardware/network.sh> · <https://wiki.archlinux.org/title/NetworkManager>

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

**Cause.** Docker's built-in `default-address-pools` are documented as six pools inside `172.16.0.0/12` followed by `{ "base": "192.168.0.0/16", "size": 20 }`. The three `/16` pools and three `/14` pools at size 16 supply 15 networks in total, so once those are taken the next bridge network Docker creates automatically comes out of `192.168.0.0/20`. Containers there still resolve through the embedded resolver at `127.0.0.11`, which forwards to whatever DNS server the daemon was given, and on Omarchy that is `172.17.0.1`, the docker0 gateway.

Three shipped pieces have to line up for that address to answer. `/etc/docker/daemon.json`, owned by `omarchy-settings`, sets `"dns": ["172.17.0.1"]` and `"bip": "172.17.0.1/16"`. `/etc/systemd/resolved.conf.d/20-docker-dns.conf`, same package, sets `DNSStubListenerExtra=172.17.0.1` so systemd-resolved actually listens on that address. `/usr/share/omarchy/install/config/firewall.sh` then opens port 53 on it to the container subnets.

**On a current Omarchy 4 install this is already fixed and the record does not apply.** `firewall.sh` opens both pools:

```sh
ufw allow in proto udp from 172.16.0.0/12 to 172.17.0.1 port 53 comment 'allow-docker-dns'
ufw allow in proto udp from 192.168.0.0/16 to 172.17.0.1 port 53 comment 'allow-docker-dns'
```

The second line landed when upstream issue 5464 was closed as completed on 2026-04-29, and it is still there on tag v4.0.3. `firewall.sh` runs at install time only and no Omarchy migration adds the rule afterwards, so a machine installed from an ISO older than that and upgraded in place still carries only the `172.16.0.0/12` rule and still fails. Plain Arch, EndeavourOS and CachyOS have neither rule and hit this as soon as a container on a `192.168` network needs the host as its DNS server. Check what is on the machine before adding anything.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, omarchy-settings 4.0.2-1, ufw 0.36.2-7, docker 1:29.7.2-1) and against the cited issue and the Docker docs. The mechanism holds: docs.docker.com/engine/network confirms the built-in default pools verbatim, six inside `172.16.0.0/12` and then `{ "base": "192.168.0.0/16", "size": 20 }`, and 15 networks come out of the 172 pools before Docker reaches the 192.168 one. The scope is wrong. Confirmed on this machine that `/usr/share/omarchy/install/config/firewall.sh` already carries the `192.168.0.0/16` rule alongside the `172.16.0.0/12` one, and `/etc/ufw/user.rules` shows both applied as tuples with the `allow-docker-dns` comment, so the record's cause sentence saying Omarchy allows Docker DNS "only from 172.16.0.0/12" is false on any install made after upstream closed issue 5464 as completed on 2026-04-29. The rule is still on tag v4.0.3. A reader on a current machine is told to add a rule that already exists, which ufw declines as a duplicate, and learns something untrue about their own system. The record is still true for Omarchy machines installed before that fix, because `firewall.sh` runs at install time and nothing re-runs it: I grepped all 96 scripts in `/usr/share/omarchy/migrations` and the only one mentioning ufw is `1788025225.sh`, which removes retired installer sudoers files and adds no firewall rule. It is also still true on plain Arch and the derivatives, which ship neither rule. Rewrote the cause to say all of that rather than rejecting the record.

On the daemon.json question I was asked to check: this record does not tell the reader to paste a whole `daemon.json`, so it does not delete anything. The keys it relies on are intact and consistent. `pacman -Qo /etc/docker/daemon.json` reports `omarchy-settings 4.0.2-1`, the file carries `"dns": ["172.17.0.1"]` and `"bip": "172.17.0.1/16"`, `ip -4 addr show docker0` shows `172.17.0.1/16` live, and `firewall.sh` opens port 53 on exactly that address. I found a third shipped piece the record never mentioned and added it, because without it the DNS server the containers are pointed at would not answer: `/etc/systemd/resolved.conf.d/20-docker-dns.conf`, also owned by `omarchy-settings` and also a pacman backup file, sets `DNSStubListenerExtra=172.17.0.1`. That is worth having in the cause, since a reader who deletes that drop-in or changes `bip` gets the same symptom for a different reason. I cross-referenced the danger with the `docker-gpu-could-not-select-device-driver` finding and confirmed `/etc/docker/daemon.json` is in the `omarchy-settings` backup array and currently unmodified, so the `.pacnew` claim in that record is correct and I repeated it here.

Three smaller defects. The fix calls `docker network inspect` bare and the verify calls `docker run` bare, but Omarchy deliberately leaves the user out of the `docker` group: confirmed with `id -nG`, which shows no `docker`, and `docker network ls` here fails with `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`. Both now use `sudo`. The verify asked for "a non-zero packet count" from `sudo ufw status`, which never prints counters at all, so that check could not pass however healthy the machine, and it now points at `iptables -L ufw-user-input -n -v` instead. The danger clause was directionally right and imprecise: the rule is scoped to destination `172.17.0.1`, so a LAN host in `192.168.0.0/16` is not automatically able to reach it, but the thing behind it is a recursive resolver and anything that can route to `172.17.0.1` gets an open resolver, which is the sharper statement. I also added the alternative that avoids the firewall change entirely, a `default-address-pools` entry keeping automatic subnets inside `172.16.0.0/12`, and flagged that restarting dockerd stops running containers. `172.18.0.0/15` at size 24 is arithmetic from the documented pool format and does not overlap docker0's `bip`, but I could not run it. Severity `medium` and frequency `occasional` both stand: the consequence is failed name resolution in one container and nothing is damaged, and although the condition is now unreachable on a fresh Omarchy 4 install it remains genuine on older installs and on the three other targets the record claims.

Sources: the only cited URL, `https://github.com/basecamp/omarchy/issues/5464`, is a hard 404 even after following redirects, so it is removed and replaced with the `omacom/omarchy` URL, which returns 200. I read the issue in full with `gh issue view 5464 -R omacom/omarchy`: it has no comments, was filed against Omarchy 2.x on 2026-04-27 and closed as completed two days later, and it does support the mechanism the record describes, including the observed `curl: (6) Could not resolve host` line and the workaround rule.

Not exercised, and I did not use sudo on this workstation by instruction: I ran no docker command, so I never created a network in the 192.168 pool, never reproduced the resolution failure, and never confirmed the fix end to end. I ran no `ufw` command either, so the applied rules come from reading `/etc/ufw/user.rules` rather than from live `ufw status` output, and the exact `ufw status` formatting quoted in the fix is the documented two-line shape rather than a transcript from this machine. I did not restart dockerd or test the `default-address-pools` alternative.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** The rule allows any source in `192.168.0.0/16` to reach port 53 on `172.17.0.1`, and on Omarchy that address is a real recursive resolver, systemd-resolved's extra stub listener from `/etc/systemd/resolved.conf.d/20-docker-dns.conf`. A host on your LAN cannot reach it by accident, because a packet has to be addressed to `172.17.0.1` and routed to this machine, but anything on the same link that can add a route can use it as an open resolver. Narrow the source to the exact Docker subnet, or avoid the rule altogether with the `default-address-pools` change above.

Editing `/etc/docker/daemon.json` carries its own risk on Omarchy 4. It is a pacman backup file owned by `omarchy-settings`, so a hand-edited copy produces a `.pacnew` during `omarchy update` that has to be merged rather than ignored, and dropping the shipped `dns` and `bip` keys breaks DNS in every container. Whatever you change, the file must stay valid JSON. A stray trailing comma makes `docker.service` fail to start and takes every container down with it, so run `python3 -m json.tool /etc/docker/daemon.json` before restarting the daemon.

**Fix.**

Check what is already there first. On a current Omarchy 4 install both rules ship and `ufw` answers `Skipping adding existing rule` rather than changing anything:

```bash
sudo ufw status | grep -i docker-dns
```

Expected on a current install:

```
172.17.0.1 53/udp            ALLOW       172.16.0.0/12              # allow-docker-dns
172.17.0.1 53/udp            ALLOW       192.168.0.0/16             # allow-docker-dns
```

Then confirm the broken network really is outside `172.16.0.0/12`, and that the daemon is pointing containers at the docker0 gateway. Omarchy leaves your user out of the `docker` group unless you opted in through Setup > Security > Sudoless Docker, so the client needs `sudo` or it fails with `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`:

```bash
sudo docker network inspect <network> --format '{{ (index .IPAM.Config 0).Subnet }}'
cat /etc/docker/daemon.json
ip -4 addr show docker0
```

If the rule really is missing, add it. It takes effect immediately, with no reload:

```bash
sudo ufw allow in proto udp from 192.168.0.0/16 to 172.17.0.1 port 53 comment 'allow-docker-dns'
```

Add TCP only if something needs the DNS-over-TCP fallback:

```bash
sudo ufw allow in proto tcp from 192.168.0.0/16 to 172.17.0.1 port 53 comment 'allow-docker-dns-tcp'
```

**The narrower fix is to keep Docker out of the 192.168 pool instead of widening the firewall.** Set `default-address-pools` so every automatically allocated subnet stays inside `172.16.0.0/12`, which the stock rule already covers. `172.18.0.0/15` gives 512 networks at size 24 and does not collide with the `172.17.0.0/16` that `bip` pins to docker0:

```json
{
    "log-driver": "json-file",
    "log-opts": { "max-size": "10m", "max-file": "5" },
    "dns": ["172.17.0.1"],
    "bip": "172.17.0.1/16",
    "default-address-pools": [
        { "base": "172.18.0.0/15", "size": 24 }
    ]
}
```

```bash
python3 -m json.tool /etc/docker/daemon.json
sudo systemctl restart docker.service
```

Restarting the daemon stops every running container. Existing networks keep the subnets they were created with, so delete and recreate the broken one afterwards.

**Do not paste a whole-file `daemon.json` from a blog over the top on Omarchy 4.** The file is owned by `omarchy-settings` and the `dns` and `bip` keys above are what make container DNS work at all, because the firewall permits port 53 only to `172.17.0.1`. Add keys and keep the rest:

```bash
pacman -Qo /etc/docker/daemon.json     # omarchy-settings
```

On plain Arch, EndeavourOS or CachyOS the file usually does not exist and none of this applies, so set `dns` yourself or leave the daemon on the host's resolvers.

**Verify.** ```bash
sudo docker run --rm --network <network> alpine nslookup registry.npmjs.org
```

resolves, and `sudo ufw status` lists the `192.168.0.0/16` line to `172.17.0.1` port 53. Do not expect a packet count there, because `ufw status` never prints counters. If you want to see the rule matching, `sudo iptables -L ufw-user-input -n -v` shows packets against it. Before concluding the firewall was the problem, confirm the rule was absent to begin with: on a current Omarchy 4 install `sudo ufw status | grep -i docker-dns` already prints two lines, and `ufw` refuses the duplicate with `Skipping adding existing rule`.

Sources: <https://github.com/omacom/omarchy/issues/5464> · <https://docs.docker.com/engine/network/> · <https://github.com/omacom/omarchy/blob/quattro/install/config/firewall.sh>

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

## Disable MAC randomization for hotspots and MAC-registered networks

`mac-randomization-breaks-hotspot-and-portal-networks` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Tethering to a phone hotspot "often disconnects automatically and I have to manually reconnect", while the same laptop is stable on home/office Wi-Fi. On university, hotel or corporate networks that register your device by MAC, you get kicked back to the sign-in page every reconnect and have to re-register.

**Cause.** Two independent mechanisms, and only one of them is on by default. `wifi.scan-rand-mac-address` in the `[device]` section defaults to `yes`, so NetworkManager sets a random, locally administered MAC on the radio while it scans. Separately, the per-connection `wifi.cloned-mac-address` and `ethernet.cloned-mac-address` decide the address used at association, and since NetworkManager 1.6 both default to `preserve`, which means NetworkManager does not touch the MAC when a profile activates. The two combine: the random address left behind by scanning is the one carried into the association, so an AP that registers your device by MAC sees a different station each time and the lease or the portal registration does not carry over. The default is not a per-connection random MAC, which would be `random` or `stable`, and neither is set on a stock Omarchy 4 or Arch install. This mechanism fully explains the MAC-registered portal case. It is a plausible but undiagnosed explanation for plain hotspot drops, because the upstream report was filed against Omarchy 3 on the old iwd stack and nobody there identified a cause.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, networkmanager 1.58.1-1, wpa_supplicant 2:2.12-1, iwd not installed, kernel 7.1.9) and against the 1.58 man pages, the Arch wiki and the upstream author's reference post. Four defects. (1) The cited URL https://github.com/basecamp/omarchy/issues/4607 is a hard 404 with no redirect, so it is removed and replaced with the omacom path. Read in full, issue 4607 supports only the quoted symptom. It reports omarchy 3.3.3, nobody diagnosed a cause, MAC randomization is never mentioned, and dhh closed it with "Quattro replaces the iwd, Impala, and systemd-networkd stack with NetworkManager and the native network panel". Worse, the Arch wiki MAC_address_spoofing page states NetworkManager ignores MAC spoofing options from conf.d on the iwd backend, so the record's own fix could not have worked on the machine in the cited report. The mechanism is real on Omarchy 4, but the cited issue is not evidence for it. (2) The cause was mechanically wrong. It said NetworkManager "can also use a per-connection random MAC", implying that is a default. man nm-settings-nmcli for 1.58 states wifi.cloned-mac-address defaults to "preserve", and "preserve" means not to touch the MAC on activation. The upstream author's post records that the default changed from "permanent" to "preserve" in 1.6. So the real mechanism is that the random address left on the radio by scanning is carried into the association, which is why the fix works. Nothing on this install sets "random" or "stable". Confirmed live: wlo1 currently reads fe:86:ef:5b:7e:d4 against permaddr 3c:6a:a7:68:5c:5e, a locally administered scan address on a disconnected radio. (3) verify called ethtool -P. Confirmed on this machine that /usr/bin/ethtool does not exist and no package owns it, so ethtool is not installed on Omarchy 4. It also used wlan0, a name Omarchy 4 does not produce: naming scheme v261 under 99-default.link gives wlo1 here. Rewritten to ip -d link show, which prints permaddr, confirmed working unprivileged. (4) systemctl restart NetworkManager is heavier than needed. man nmcli 1.58 documents nmcli general reload conf, allowed non-root via PolicyKit, and the Arch wiki uses nmcli general reload. On the precedence question asked: conf.d is read in lexicographic order with later files winning, and Omarchy's /etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf (owned by omarchy-settings) has no numeric prefix, so it is read after every numerically prefixed file. It sets only wifi.powersave, so it does not shadow the MAC keys and 25-mac-stable.conf does land, but no numeric prefix can ever override Omarchy's file, which the fix now says. Confirmed the only other drop-ins are 20-omarchy-dns.conf (unowned, managed by omarchy-dns, [global-dns] only) and /usr/lib/NetworkManager/conf.d/20-connectivity.conf. nmcli syntax verified without changing anything by running nmcli --offline connection modify against a scratch keyfile: wifi.cloned-mac-address permanent is accepted and also emits the deprecated companion key mac-address-randomization=1, which the fix now notes. NOT exercised: this machine has a Wi-Fi radio (wlo1, iwlwifi) but no association is possible here, so the association-time MAC, the hotspot reconnect and the captive portal re-registration were not reproduced. Those rest on the 1.58 documentation and the upstream post, not on observation. frequency is lowered to occasional because the MAC-registered portal case is real but the headline hotspot-drop symptom was never diagnosed as MAC related in the only report cited. severity stays medium.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Pinning the permanent MAC removes the privacy benefit of randomization, so you become trackable across public networks by one stable identifier. The `[connection]` block is a global default and applies to every Wi-Fi and Ethernet profile on the machine, not only the one that misbehaves, so prefer the single-connection form if that matters. Reconnecting a profile drops the link, so do not run `nmcli connection up` on the connection carrying your only route while you are logged in over it.

**Fix.**

Two settings are involved and they are independent. Turn off scan randomization and force the permanent address at association:

```bash
sudo tee /etc/NetworkManager/conf.d/25-mac-stable.conf >/dev/null <<'EOF'
[device]
wifi.scan-rand-mac-address=no

[connection]
wifi.cloned-mac-address=permanent
ethernet.cloned-mac-address=permanent
EOF
nmcli general reload conf
```

`nmcli general reload conf` re-reads `conf.d` without restarting the service and is allowed for a non-root user through PolicyKit. The MAC is only applied when a profile activates, so reconnect the affected network:

```bash
nmcli connection down "<SSID>" && nmcli connection up "<SSID>"
```

Or for just one network, leaving randomization on elsewhere:

```bash
nmcli connection modify "<SSID>" wifi.cloned-mac-address permanent
nmcli connection up "<SSID>"
```

That also writes the deprecated companion key `mac-address-randomization=1` into the profile, which is expected and not an error.

**Omarchy 4 note on file ordering.** Omarchy ships its own drop-in, `/etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf`, owned by `omarchy-settings`. Files in `conf.d` are read in lexicographic order and later files win, and because Omarchy's filename has no numeric prefix it is read after every numerically prefixed file. It sets only `wifi.powersave`, so it does not shadow the MAC keys above and `25-mac-stable.conf` takes effect. If you ever need to override `wifi.powersave` itself, no numeric prefix will do it: the file has to sort after `omarchy-`, for example `/etc/NetworkManager/conf.d/zz-local.conf`.

**If you switched NetworkManager to the `iwd` backend**, none of the above applies. NetworkManager ignores MAC spoofing options from `NetworkManager.conf` and `conf.d` on that backend and the setting has to go in `/etc/iwd/main.conf`. Omarchy 4 does not install `iwd` and uses `wpa_supplicant`.

**Verify.** `ethtool` is not installed on Omarchy 4, so read both addresses with `ip`. `ip -d link show <iface>` prints the current `link/ether` and the hardware `permaddr`:

```bash
ip -d link show wlo1 | grep -oE 'link/ether [0-9a-f:]+|permaddr [0-9a-f:]+'
```

They must match both while the radio is idle or scanning and while associated. Before the change they differ, and the current address has the locally administered bit set, so its first octet ends in `2`, `6`, `a` or `e`. Then reconnect to the hotspot or portal network and confirm it no longer asks you to register again. Use your own interface name from `ip -br link`, which on Omarchy 4 is typically `wlo1` or `wlp*` and not `wlan0`.

Sources: <https://man.archlinux.org/man/NetworkManager.conf.5> · <https://github.com/omacom/omarchy/issues/4607> · <https://man.archlinux.org/man/nm-settings-nmcli.5> · <https://man.archlinux.org/man/nmcli.1> · <https://wiki.archlinux.org/title/MAC_address_spoofing> · <https://wiki.archlinux.org/title/NetworkManager> · <https://blogs.gnome.org/thaller/2016/08/26/mac-address-spoofing-in-networkmanager-1-4-0/>

---

## Fix `.local` names and service discovery failing, and why opening 5353/udp is not the fix

`mdns-local-hostname-not-resolving` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `ping nas.local` or `ping raspberrypi.local` fails with `Name or service not known`, `getent hosts nas.local` returns nothing, and a network printer or Home Assistant box that other devices reach by `.local` name is unreachable. The device answers fine by IP address. A related symptom in the same area is the machine's own hostname gaining a number (`myhost-2.local`, then `myhost-3.local`), which means two mDNS responders are fighting over it. One thing that looks like this symptom but is not: on Omarchy 4, `resolvectl query nas.local` returning `No appropriate name servers or networks for name found` is the expected reply even when `.local` resolution is working perfectly, because Omarchy disables systemd-resolved's mDNS and lets Avahi own it.

**Cause.** Two different mDNS stacks can serve `.local` names, and which one is in play decides everything. The record this replaces assumed systemd-resolved, which is wrong for Omarchy.

**Omarchy 4 gives mDNS to Avahi and preconfigures all of it.** `avahi` and `nss-mdns` ship in `/usr/share/omarchy/install/omarchy-base.packages`, `/usr/share/omarchy/install/config/enable-services.sh` runs `systemctl enable avahi-daemon.service`, and Omarchy replaces `/etc/nsswitch.conf` with its own copy whose `hosts:` line already carries `mdns_minimal [NOTFOUND=return]` ahead of `resolve`. Omarchy also ships `/etc/systemd/resolved.conf.d/10-disable-multicast.conf` setting `MulticastDNS=no` and `LLMNR=no`, so systemd-resolved is deliberately neither an mDNS resolver nor a responder. The visible consequence is that on a healthy Omarchy 4 box `getent hosts nas.local` succeeds while `resolvectl query nas.local` fails, and that is correct rather than broken. When `.local` genuinely fails on Omarchy the cause is normally `avahi-daemon` being down or its socket stuck, a firewall gap on unicast port 5353, or systemd-resolved answering the `SOA` query for the `local` domain, which makes `nss-mdns` stand down.

**On plain Arch and the other derivatives nothing is preconfigured, and two separate switches are off.** systemd-resolved's global `MulticastDNS=` does default to yes, but mDNS activates for a connection only when the network manager enables it per connection as well, and NetworkManager's `connection.mdns` default of `-1` leaves it off. Independently of that, glibc will not consult Avahi at all until `nss-mdns` is installed and named in the `hosts:` line.

The hostname-gaining-a-number symptom is the opposite fault, two responders on one interface, with Avahi and systemd-resolved both answering mDNS and fighting over the name. That is reachable on plain Arch and not on a stock Omarchy 4 install, where resolved's responder is already off. Avahi additionally has a long-standing hostname race of its own that can produce the same renaming even with a single responder.

**The firewall is almost never the cause, and opening 5353/udp changes nothing on a stock install.**
ufw's own `/etc/ufw/before.rules` accepts inbound multicast mDNS before any user rule is consulted,
on Arch and on Omarchy alike:

```
# if MULTICAST, RETURN
-A ufw-not-local -m addrtype --dst-type MULTICAST -j RETURN
...
# allow MULTICAST mDNS for service discovery (be sure the MULTICAST line above
# is uncommented)
-A ufw-before-input -p udp -d 224.0.0.251 --dport 5353 -j ACCEPT
```

`/etc/ufw/before6.rules` carries the `ff02::fb` equivalent. Both lines have shipped since ufw 0.30.1
in March 2011, so no version anyone is running drops multicast mDNS. Avahi never sets the
unicast-response bit in the questions it asks, so every answer it wants arrives at the multicast
group and that rule accepts it. Measured on a stock Omarchy 4 machine whose only open ports are
LocalSend's 53317 and two Docker DNS rules: `avahi-browse` lists the LAN, `lpstat -e` finds the
network printer and `getent hosts nas.local` resolves.

Two firewall shapes do break it, and both are narrower than the usual advice:

1. **The `ufw-not-local` MULTICAST RETURN line commented out.** `ufw-before-input` jumps to
   `ufw-not-local` before it reaches the mDNS accept, so a multicast packet dropped there never gets
   the chance to match. ufw's own comment above the accept warns about exactly this.
2. **Unicast mDNS replies.** The accept matches destination 224.0.0.251 only, and a unicast reply
   does not match the conntrack entry created by a query sent to the multicast group, so it falls
   through to the default deny. Avahi does not ask for unicast replies, but a one-shot resolver in a
   script or an application library does, and a legacy unicast reply arrives at an ephemeral port
   that no `--dport 5353` rule can cover.

> **Audit corrected this record.** The record's central framing is inverted for Omarchy 4, and I confirmed that on this workstation (omarchy 4.0.2-1, kernel 7.1.9, avahi 1:0.9rc5-1, nss-mdns 0.15.1-2). Omarchy ships `/etc/systemd/resolved.conf.d/10-disable-multicast.conf` with `MulticastDNS=no` and `LLMNR=no`, owned by `omarchy-settings 4.0.2-1` and shown as applied by `systemd-analyze cat-config systemd/resolved.conf`, so the claim that resolved's global `MulticastDNS=` is on by default and that per-connection NetworkManager enablement is the missing half is true on plain Arch and false here. Omarchy hands mDNS to Avahi and preconfigures every part: `avahi` and `nss-mdns` are in `install/omarchy-base.packages`, `install/config/enable-services.sh` enables `avahi-daemon.service`, and `/etc/nsswitch.conf` already reads `hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns` against the Arch stock line in `/usr/share/factory/etc/nsswitch.conf`, which has no `mdns_minimal`. Measured end to end against a real LAN device rather than reasoned about: `getent hosts truenas.local` and `avahi-resolve -n truenas.local` both return addresses while `resolvectl query truenas.local` fails with `No appropriate name servers or networks for name found`, so the record's Path A verify command reports a fault on a fully working machine, and a user acting on that reading would run Path A, disable `avahi-daemon`, and actually break both `.local` resolution and CUPS printer discovery, since the Arch CUPS wiki states DNS-SD is supported only through Avahi and never through resolved. `resolvectl query <own-hostname>.local` is a false pass on top of that, returning addresses tagged `Data from: synthetic` even with mDNS off. The most serious unflagged hazard is the nsswitch clobber: upstream `docs/file-layout.md` on `quattro` and the scriptlet at `/var/lib/pacman/local/omarchy-settings-4.0.2-1/install` both show `omarchy-settings` doing `cp -f /usr/share/omarchy/etc-overrides/nsswitch.conf /etc/nsswitch.conf` from `post_install` and `post_upgrade`, with an upstream comment saying customizations will be reset on every upgrade, so a hand edit vanishes with no `.pacnew`, no backup and nothing `pacdiff` can show. The `host -t SOA local` step cannot run as written, confirmed: `bind` is not installed and `command -v host` finds nothing. Everything generic in the record is source-backed and I kept it, checking each cited page in full: the Arch Avahi wiki gives the identical `hosts:` line including `[!UNAVAIL=return]`, the `NXDOMAIN` SOA precondition, the `mdns` plus `/etc/mdns.allow` fallback, the `mtr` and `traceroute` reverse-lookup breakage and a troubleshooting section for the incrementing hostname, the Systemd-resolved wiki gives the two-places activation rule and `MulticastDNS=resolve` for Avahi coexistence, and the nss-mdns README says plainly to test with `getent hosts` and not with `host` or `nslookup` because those bypass NSS. All three cited URLs resolve and support what the record draws from them, so nothing needs removing. I also checked tag v4.0.3 (`0534987`, 2026-09-08) and `etc/nsswitch.conf`, the resolved drop-in and `enable-services.sh` are unchanged there, so this holds on the newest release. Corrected symptom, cause, fix, verify and danger, and lowered frequency to `occasional` because on Omarchy the stack ships working so the condition is not commonly hit, while it stays genuine on the six other targets. On the boundary question, this record and `mdns-local-hostnames-fail-ufw-blocks-5353` are the same problem and the sibling is the better of the two, so I narrowed this one to the stack-ownership and responder-conflict question and cross-referenced the sibling for the firewall and nsswitch half rather than duplicating it. My recommendation is that a later pass merge them into one `network` record. Flagging separately that the sibling now needs its own re-audit, because stock ufw already accepts multicast mDNS: `/etc/ufw/before.rules` line 68 carries `-A ufw-before-input -p udp -d 224.0.0.251 --dport 5353 -j ACCEPT` and `before6.rules` line 136 the `ff02::fb` equivalent, both clean under `pacman -Qkk ufw`, and on this box `/etc/ufw/user.rules` opens only 53317 yet `avahi-browse` lists the whole LAN, which contradicts the sibling's claim that ufw drops mDNS replies until a rule is added. The sibling also tells users to reconcile a nsswitch `.pacnew` that will never appear. Not exercised, because I have no sudo: I did not disable `avahi-daemon`, did not switch to the resolved stack, did not add a ufw rule, did not read live `ufw status` output, and could not reproduce either the hostname-renaming loop or a unicast-5353 block.

Merged on 2026-09-11 with `mdns-local-hostnames-fail-ufw-blocks-5353`, which is removed. Both
records were re-audited that day and both came back `corrected`. They described one problem from two
ends, and the removed record's slug and title asserted the cause its own audit disproved, that ufw
blocks 5353, which no verdict field can rename. What moved into this record: the negative firewall
finding with the exact shipped rule text and the instruction to check before opening anything, the
`ufw-not-local` ordering trap in both the cause and the danger, and the unicast-reply caveat. The
KDE Connect half became its own record, `kde-connect-ports-blocked-by-ufw`, because KDE Connect does
not use mDNS. This record also moved from `apps-services` to `network`. Measured for the merge on
omarchy 4.0.2-1: `/etc/ufw/before.rules:68` and `before6.rules:136` carry the accepts as unmodified
pacman backup files, `/etc/ufw/after.rules:27` sends broadcast to `ufw-skip-to-policy-input`, and
`install/config/firewall.sh` opens only 53317.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not hand-edit `/etc/nsswitch.conf` on Omarchy 4 and expect the edit to last. The file belongs to the Arch `filesystem` package, so Omarchy cannot ship it through pacman without a conflict, and `omarchy-settings` instead runs `cp -f /usr/share/omarchy/etc-overrides/nsswitch.conf /etc/nsswitch.conf` from both its `post_install` and its `post_upgrade` scriptlet. Upstream's own comment on those lines states that users who customize the file will have their changes reset to Omarchy defaults on every upgrade. There is no `.pacnew`, no backup and nothing for `pacdiff` to offer, so the edit disappears silently at the next `omarchy update` that bumps `omarchy-settings`. You almost never need to touch it, because the shipped line already carries `mdns_minimal`.

Getting the `hosts:` line wrong breaks all name resolution system-wide, pacman included. Copy the file aside first with `sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.bak` and test with `getent hosts archlinux.org` before you log out or reboot.

Disabling `avahi-daemon.service` on Omarchy 4 is not a neutral cleanup. CUPS supports DNS-SD only through Avahi and never through systemd-resolved, so it removes network printer discovery on a distro that enables `cups.service` by default, and it strands the `mdns_minimal` entry that Omarchy's own `hosts:` line depends on. The mirror-image error is running Avahi and systemd-resolved as mDNS responders at the same time, which causes the hostname-conflict renaming loop. Run exactly one responder.

Using the full `mdns` module instead of `mdns_minimal` makes reverse lookups in `mtr` and `traceroute` time out rather than falling back to other DNS services.

The firewall edit worth warning about is the opposite one. Commenting out
`-A ufw-not-local -m addrtype --dst-type MULTICAST -j RETURN` as a hardening step silently removes
`.local` resolution, service discovery and network printing, and the breakage surfaces nowhere near
the file that caused it. Copy the file aside before touching it, and remember it is a pacman backup
file that can arrive as a `.pacnew` on a ufw upgrade. In the other direction, opening 5353 hides
less than it appears to: Avahi already answers multicast queries from the whole local link with no
user rule at all, so your hostname and advertised services are visible on café and hotel Wi-Fi
whether or not you add anything. If that matters, stop `avahi-daemon.service` on untrusted networks
rather than trusting a closed port to hide you.

**Fix.**

First find out which mDNS stack is actually in play. All of these are read-only:

```bash
grep '^hosts:' /etc/nsswitch.conf
systemctl is-active avahi-daemon.service
resolvectl mdns
systemd-analyze cat-config systemd/resolved.conf | grep -iE 'MulticastDNS|LLMNR'
```

**On Omarchy 4, Avahi already owns mDNS and it is already wired up.** A stock install carries `avahi` and `nss-mdns` from `/usr/share/omarchy/install/omarchy-base.packages`, has `avahi-daemon.service` enabled by `/usr/share/omarchy/install/config/enable-services.sh`, ships a `hosts:` line that already reads:

```
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns
```

and ships `/etc/systemd/resolved.conf.d/10-disable-multicast.conf`:

```ini
[Resolve]
LLMNR=no
MulticastDNS=no
```

So there is nothing to install and nothing to edit. Test with `getent hosts`, never with `resolvectl`:

```bash
getent hosts nas.local
avahi-browse --all --ignore-local --resolve --terminate
```

If `getent hosts` returns an address you are done. `resolvectl query nas.local` failing with `No appropriate name servers or networks for name found` is the expected reply on Omarchy 4 and is not a fault.

If `getent hosts` fails, work through it in this order:

```bash
systemctl status avahi-daemon.service
sudo systemctl restart avahi-daemon.service avahi-daemon.socket
getent hosts nas.local
```

A stuck `/run/avahi-daemon/socket` stops NSS forwarding lookups to mDNS, and restarting both units clears it. If service discovery is the part that fails rather than name lookup, work through the firewall section below before changing anything.

**Checking the `SOA` precondition needs a tool Omarchy does not ship.** `nss-mdns` stands down for `.local` if the DNS server in `/etc/resolv.conf` answers `SOA` for the `local` domain, and on Omarchy that server is systemd-resolved's stub at `127.0.0.53`. The `host` command comes from `bind`, which is not installed:

```bash
sudo pacman -S --needed bind
host -t SOA local
```

`NXDOMAIN` is the answer you want. Plain `pacman -S` is safe here, because Omarchy's ALPM guard aborts only when both `-S` and `-u` are present.

**Switching Omarchy to systemd-resolved instead of Avahi costs you printing.** CUPS supports DNS-SD only through Avahi, so stopping `avahi-daemon.service` removes network printer discovery, and Omarchy enables `cups.service` alongside it. It also strands the shipped `mdns_minimal` entry in the `hosts:` line, which talks to Avahi over D-Bus. If you still want resolved to own mDNS, all three steps are required:

```bash
sudo tee /etc/systemd/resolved.conf.d/50-mdns.conf >/dev/null <<'EOF'
[Resolve]
MulticastDNS=yes
EOF
sudo systemctl restart systemd-resolved.service

nmcli connection modify "<connection-name>" connection.mdns yes
nmcli connection up "<connection-name>"

sudo systemctl disable --now avahi-daemon.service avahi-daemon.socket
resolvectl query nas.local
```

The `50-` prefix matters. Omarchy's own drop-in is `10-disable-multicast.conf`, systemd applies drop-ins in filename order and the last one wins, so a file sorting before that one is silently overridden. Do not edit `10-disable-multicast.conf` itself. It belongs to `omarchy-settings`, so an edit there becomes a `.pacnew` to reconcile on the next upgrade.

**On plain Arch, EndeavourOS, CachyOS or Manjaro nothing is preconfigured.** Two things are separately off. systemd-resolved's `MulticastDNS=` defaults to yes, but mDNS activates for a connection only when the network manager enables it too, and NetworkManager's `connection.mdns` default of `-1` leaves it off. Separately, glibc will not consult Avahi until `nss-mdns` is installed and named in the `hosts:` line. Pick one stack.

Avahi, which is what you want if you print:

```bash
sudo pacman -S --needed avahi nss-mdns
sudo systemctl enable --now avahi-daemon.service
```

```
# /etc/nsswitch.conf, mdns_minimal must come BEFORE resolve and dns
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve [!UNAVAIL=return] files myhostname dns
```

```bash
sudo mkdir -p /etc/systemd/resolved.conf.d
sudo tee /etc/systemd/resolved.conf.d/50-mdns.conf >/dev/null <<'EOF'
[Resolve]
MulticastDNS=resolve
EOF
sudo systemctl restart systemd-resolved.service
```

`MulticastDNS=resolve` lets systemd-resolved cache mDNS answers without responding, so Avahi stays the only responder.

Or systemd-resolved, if you do not need service discovery:

```bash
sudo tee /etc/systemd/resolved.conf.d/50-mdns.conf >/dev/null <<'EOF'
[Resolve]
MulticastDNS=yes
EOF
sudo systemctl restart systemd-resolved.service

nmcli connection modify "<connection-name>" connection.mdns yes
nmcli connection up "<connection-name>"
sudo systemctl disable --now avahi-daemon.service avahi-daemon.socket
```

**If the hostname keeps gaining a number** (`myhost-2.local`, then `myhost-3.local`), two responders are claiming it. Check which are live and turn one off:

```bash
resolvectl mdns
systemctl is-active avahi-daemon.service
```

Set `MulticastDNS=resolve` or `MulticastDNS=no` for resolved, or disable `avahi-daemon`, but never leave both responding. This cannot happen on a stock Omarchy 4 install, because resolved's responder is already off. Upstream also tracks a hostname race inside Avahi that survives having only one responder, and the workaround there is to limit Avahi to a single interface in `/etc/avahi/avahi-daemon.conf`:

```ini
[server]
allow-interfaces=eno1
```


**If service discovery is what fails, check the firewall before you change it, because the rule you
are about to add is almost certainly already there.** These three lines ship with ufw itself and all
three must be present and uncommented:

```bash
grep -n 'dst-type MULTICAST' /etc/ufw/before.rules
grep -n '224.0.0.251' /etc/ufw/before.rules
grep -n 'ff02::fb' /etc/ufw/before6.rules
```

On a stock Omarchy 4 or Arch install that prints:

```
57:-A ufw-not-local -m addrtype --dst-type MULTICAST -j RETURN
68:-A ufw-before-input -p udp -d 224.0.0.251 --dport 5353 -j ACCEPT
136:-A ufw6-before-input -p udp -d ff02::fb --dport 5353 -j ACCEPT
```

If one of them is commented out, that is the fault. `/etc/ufw/before.rules` is a pacman backup file,
so copy it aside, uncomment the line by hand and reload:

```bash
sudo cp /etc/ufw/before.rules /etc/ufw/before.rules.bak
sudoedit /etc/ufw/before.rules
sudo ufw reload
```

If all three are present, stop. Opening 5353/udp will not help and the fault is in the resolver
stack, which is the rest of this record. The one case that does want a rule is unicast mDNS, which
Avahi never asks for and some application libraries do:

```bash
sudo ufw allow 5353/udp comment 'mDNS unicast replies'
```

Scope it to your own network if you use café or hotel Wi-Fi:

```bash
sudo ufw allow in proto udp from 192.168.0.0/16 to any port 5353 comment 'mDNS unicast, LAN only'
```

A phone that never appears in KDE Connect looks like this symptom and is not: KDE Connect does not
use mDNS and needs its own ports. See `kde-connect-ports-blocked-by-ufw`.

**Verify.** `getent hosts nas.local` returns an address. That is the test that matters, because it is the path applications use and the only one that exercises the `hosts:` line in `/etc/nsswitch.conf`. Then `avahi-browse --all --ignore-local --resolve --terminate` lists services from other machines, and `ping nas.local` works. Do not verify with `resolvectl query` or with `host`. The `host` command bypasses NSS entirely and so bypasses `nss-mdns`, and `resolvectl` reports only systemd-resolved, so on a correctly working Omarchy 4 box it fails with `No appropriate name servers or networks for name found` while `getent hosts` succeeds. `resolvectl query <own-hostname>.local` is worse than useless as a check, because resolved synthesizes an answer for the local hostname and tags it `Data from: synthetic`, which passes even with mDNS switched off completely. Use `resolvectl query nas.local` as the check only if you deliberately switched to the systemd-resolved stack. Before you conclude the firewall was the problem, confirm it ever was:
`grep -n '224.0.0.251' /etc/ufw/before.rules` printing an uncommented ACCEPT line means multicast
mDNS was already allowed and any 5353 rule you added made no difference.

Sources: <https://wiki.archlinux.org/title/Systemd-resolved> · <https://wiki.archlinux.org/title/Avahi> · <https://wiki.archlinux.org/title/CUPS> · <https://github.com/avahi/nss-mdns/blob/master/README.md> · <https://github.com/omacom/omarchy/blob/quattro/docs/file-layout.md> · <https://github.com/omacom/omarchy/blob/v4.0.3/etc/nsswitch.conf> · <https://github.com/omacom/omarchy/blob/v4.0.3/etc/systemd/resolved.conf.d/10-disable-multicast.conf> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/config/enable-services.sh> · <https://wiki.archlinux.org/title/Uncomplicated_Firewall> · <https://git.launchpad.net/ufw/plain/conf/before.rules> · <https://git.launchpad.net/ufw/patch/?id=c7acf0166e9cb175d32c42ee957c2a0d89fc9c87> · <https://www.rfc-editor.org/rfc/rfc6762.txt> · <https://github.com/avahi/avahi/blob/master/avahi-core/query-sched.c> · <https://github.com/avahi/avahi/blob/master/avahi-core/dns.h> · <https://github.com/omacom/omarchy/blob/quattro/install/config/firewall.sh> · <https://github.com/omacom/omarchy/blob/quattro/etc/nsswitch.conf>

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

## Stop Wi-Fi dropping every few minutes by disabling power save

`wifi-drops-every-few-minutes-powersave` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `intel`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** "Every 5 or so minutes, my wifi disconnects, no matter what WiFi I'm on." The connection reassociates by itself after a delay, or needs a manual reconnect. It is worse on battery, and on phone hotspots the drop happens most often while the screen is idle. On a stock Omarchy 4 install this is unlikely to be power save, because Omarchy already ships a NetworkManager drop-in that turns power save off. Reach for this record on plain Arch, or on Omarchy only after checking that something has overridden that drop-in or that a per-connection setting is defeating it.

**Cause.** With no configuration, NetworkManager leaves `wifi.powersave` at `ignore` and the driver default stands, which on most Intel, Realtek and MediaTek parts means 802.11 power save is on. The radio sleeps between beacons, and access points with aggressive client timeouts, phone hotspots especially, age the station out so the driver has to reassociate.

Two things change that picture on Omarchy 4. First, `omarchy-settings` installs `/etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf` with `wifi.powersave = 2`, so power save is already off out of the box and this cause is already handled. Second, NetworkManager only consults that global default when the connection profile's own `802-11-wireless.powersave` is `0` (default). A profile saved with `3` (enable) or `1` (ignore) beats the drop-in, which is the remaining way a stock Omarchy 4 machine can still suffer this.

> **Audit corrected this record.** The fix is work Omarchy 4 already does, which the record does not mention. Confirmed on this machine: `/etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf` exists, `pacman -Qo` reports it owned by `omarchy-settings 4.0.2-1`, it contains `[connection]` with `wifi.powersave = 2`, and `NetworkManager --print-config` reports `wifi.powersave=2` as the effective value on `networkmanager 1.58.1-1`. It is also in upstream `v4.0.3` at `etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf`, so it is not a local artefact. `/usr/share/omarchy/migrations/1784914435.sh` additionally runs `iw dev <iface> set power_save off` on every wireless interface, and its own comment states why: NetworkManager applies `wifi.powersave` only when a connection activates. That matches what I measured, `iw dev wlo1 get power_save` prints `Power save: on` on this machine despite the drop-in, because `wlo1` is disconnected. The record's verify step would therefore read as a failure on a correctly configured machine.

Load order is wrong in the record and confirmed wrong here. `NetworkManager --print-config` lists its conf.d files as `{20-omarchy-dns.conf, omarchy-wifi-powersave.conf}`, and NetworkManager.conf(5) says later files override earlier ones, so the record's `20-wifi-powersave.conf` is read before the package file and loses to it. Harmless while both set `2`, but the record is teaching a name that cannot win. I also checked `pacman -Qii omarchy-settings`: that conf is not in the backup list, so editing it in place is overwritten on upgrade with no `.pacnew`, which the record's danger field does not cover. A second mechanism the record misses is that nm-settings-nmcli(5) defines `802-11-wireless.powersave` as default (0), ignore (1), disable (2), enable (3), and NetworkManager.conf(5) states a `[connection]` default is only consulted when the per-profile property asks for it, so a profile saved with `3` defeats any drop-in. That is the one way this still bites a stock Omarchy 4 machine, and the record does not mention it.

`wlan0` does not exist on Omarchy 4. Confirmed on this machine, the only wireless interface is `wlo1`, with no `net.ifnames=0` on the kernel cmdline, so both the live test and the verify command as written fail outright. The Intel modprobe advice is half dead. `modinfo -p iwlwifi` on kernel 7.1.9 shows `power_save` with `default: disable`, so `power_save=0` is a no-op, and a GitHub code search of torvalds/linux master finds `iwlwifi_mod_params.power_save` read only in `drivers/net/wireless/intel/iwlwifi/dvm/mac80211.c`, meaning iwldvm 5000 and 6000 series cards only. `options iwlmvm power_scheme=1` is real, confirmed consumed in `mvm/power.c` and `mvm/mac80211.c`, but kernel 7.1.9 also ships `iwlmld` for BE200 class parts, and `modinfo -p iwlmld` reports its own `power_scheme` with values 1-active and 2-balanced. The record names only iwlmvm, so the exact hardware Omarchy's drop-in comment calls out is the hardware it misses.

Both cited GitHub URLs are dead and neither issue supports the cause. `https://github.com/basecamp/omarchy/issues/3882` and `.../2925` both return HTTP 404 to `curl -sL`, because the repo is now `omacom/omarchy`. Read in full with `gh issue view 3882 -R omacom/omarchy --comments`: the body is the record's symptom verbatim on Omarchy 3.2.2, but the thread converges on Portmaster, on NetworkManager and systemd-networkd both running, and on several users saying the problem started when they installed NetworkManager at all. One comment offers `sudo iw dev wlan0 set power_save off` with nobody confirming it, and another user states that disabling power save did not work. Issue 2925 is a different problem entirely, network dead after suspend, with DNS, tailscaled and NordVPN named, and one commenter merely proposing to try power save without ever reporting a result. Both threads are Omarchy 3, which shipped `iwd`, so the record's NetworkManager fix did not even apply to those machines. `iwd` is not installed here and `systemd-networkd` is disabled and inactive. I am keeping 3882 under its `omacom` URL because it is the source of the symptom text and removing both would leave the record with only a man page, and dropping 2925, which supports nothing the record claims.

Frequency drops from `very-common` to `occasional`, because on Omarchy 4 the distribution already applies the fix and only an overriding per-connection value or a removed drop-in can reproduce it. Severity stays `medium`. Not exercised: this workstation has an Intel Wireless-AC 9560 CNVi part (`8086:a370`, subsystem `8086:0034`, driver `iwlwifi`) but `wlo1` is down and the machine runs on `eno2`, and I was told not to change any NetworkManager or radio state, so I did not associate, did not measure any disconnect rate, and did not test any modprobe option or reboot.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Turning Wi-Fi power save off costs idle battery, though the amount is small. Omarchy's own drop-in describes the trade as a fraction of a watt against 20 to 300 ms latency spikes on an idle link.

Two traps matter more than the power. Do not edit `/etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf` in place: it belongs to `omarchy-settings` and is not a pacman backup file, so the next upgrade overwrites the edit without producing a `.pacnew` and your change disappears with no warning. And if you add your own drop-in, check where its name sorts. NetworkManager reads `conf.d/*.conf` in filename order with later files winning, so a numeric prefix such as `20-` loses to `omarchy-wifi-powersave.conf` and silently has no effect.

**Fix.**

First check whether the machine already has this handled. On Omarchy 4 it does:

```bash
cat /etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf
pacman -Qo /etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf
NetworkManager --print-config | sed -n '/^\[connection\]/,/^$/p'
```

If `wifi.powersave=2` is already the effective value, stop. Adding another drop-in changes nothing and the cause is elsewhere.

Find the real interface name. Omarchy 4 uses predictable names such as `wlo1` or `wlp3s0`, and `wlan0` does not exist:

```bash
for w in /sys/class/net/*/wireless; do basename "$(dirname "$w")"; done
iw dev | awk '/Interface/ {print $2}'
```

Use that name everywhere below in place of `wlo1`.

Check the per-connection value, because it overrides the global default unless it is `0`:

```bash
nmcli -g NAME connection show --active
nmcli -g 802-11-wireless.powersave connection show "<profile>"
```

`0` is default (use the global value), `1` is ignore, `2` is disable, `3` is enable. Anything other than `0` is what you need to change:

```bash
sudo nmcli connection modify "<profile>" 802-11-wireless.powersave 2
sudo nmcli connection up "<profile>"
```

**Plain Arch, or Omarchy where the shipped drop-in has been removed.** Add a drop-in whose name sorts after any existing one, because NetworkManager reads `/etc/NetworkManager/conf.d/*.conf` in filename order and later files win. A file called `20-wifi-powersave.conf` sorts before `omarchy-wifi-powersave.conf` and would lose to it:

```bash
sudo tee /etc/NetworkManager/conf.d/zz-wifi-powersave.conf >/dev/null <<'EOF'
[connection]
wifi.powersave = 2
EOF
sudo nmcli general reload conf
```

Do not edit `/etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf` itself. It is owned by `omarchy-settings` and is not in that package's backup list, so an upgrade overwrites your edit silently and leaves no `.pacnew` behind.

NetworkManager applies `wifi.powersave` only when a connection activates, so the running session needs one more step. Omarchy's own migration at `/usr/share/omarchy/migrations/1784914435.sh` does exactly this:

```bash
sudo iw dev wlo1 set power_save off
```

That is not persistent by itself. It is a live test and a way to settle the current session, not the fix.

**Intel driver level, only if the NetworkManager route did not help.** Identify which Intel driver the card uses first, because the parameter differs and two of the three commonly cited options do nothing:

```bash
basename "$(readlink -f /sys/class/net/wlo1/device/driver)"
ls /sys/module | grep -E '^iwl(mvm|mld|dvm)$'
```

For `iwlmvm` (7260 and newer through AX210):

```bash
sudo tee /etc/modprobe.d/iwlwifi-power.conf >/dev/null <<'EOF'
options iwlmvm power_scheme=1
EOF
sudo reboot
```

For `iwlmld`, which kernel 7.1 uses for BE200 class cards, the parameter lives on that module instead and accepts only `1` (active) or `2` (balanced):

```bash
sudo tee /etc/modprobe.d/iwlwifi-power.conf >/dev/null <<'EOF'
options iwlmld power_scheme=1
EOF
sudo reboot
```

Do not bother with `options iwlwifi power_save=0`. Its default is already false, and the only in-tree consumer is `drivers/net/wireless/intel/iwlwifi/dvm/mac80211.c`, so it reaches nothing newer than the 5000 and 6000 series cards.

**Verify.** Read the effective NetworkManager value, which does not depend on being connected:

```bash
NetworkManager --print-config | sed -n '/^\[connection\]/,/^$/p'
nmcli -g 802-11-wireless.powersave connection show "<profile>"
```

Then check the radio itself, but only while the link is up, because NetworkManager applies the setting on activation and a disconnected interface still reports the driver default:

```bash
iw dev wlo1 link          # must show a connected BSS first
iw dev wlo1 get power_save   # expect: Power save: off
```

Finally, count the drops over a long idle period rather than grepping for a word that appears in routine log lines:

```bash
journalctl -u NetworkManager --since '2 hours ago' \
  | grep -cE 'state change: (activated|ip-config) -> (deactivating|disconnected)'
```

Sources: <https://man.archlinux.org/man/NetworkManager.conf.5> · <https://github.com/omacom/omarchy/issues/3882> · <https://github.com/omacom/omarchy/blob/v4.0.3/etc/NetworkManager/conf.d/omarchy-wifi-powersave.conf> · <https://man.archlinux.org/man/nm-settings-nmcli.5> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/iwl-drv.c> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/iwl-modparams.h> · <https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/intel/iwlwifi/mvm/power.c>

---

## Stop re-pairing Bluetooth devices every time you switch between Linux and Windows

`bluetooth-pairing-lost-every-windows-dualboot` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A Bluetooth mouse, keyboard, headset or controller works fine until you boot the other OS. After pairing it in Windows it will no longer connect in Linux, and after re-pairing it in Linux it stops working in Windows. `bluetoothctl connect <MAC>` reports `Failed to connect: org.bluez.Error.Failed` or the device connects and immediately drops. Removing and re-pairing works — until the next reboot into the other OS.

**Cause.** Both installations share one Bluetooth adapter and therefore one adapter MAC address, but each generates its own link key during pairing. The device remembers only the most recent key for that MAC, so whichever OS paired last owns the device and the other is locked out. Nothing is broken; the two key stores have simply diverged.

> **Audit corrected this record.** Checked both cited pages and both resolve and support the record. I fetched the Arch Bluetooth page as raw wikitext and read the whole "Dual boot pairing", "Preparing Bluetooth 5.1 Keys" and "Saving the configuration" sections, plus the "Default transport 3.0 vs 5.x" section, and the Dual boot with Windows page, whose "Bluetooth pairing" section states the shared adapter MAC and divergent link keys exactly as the cause does. Confirmed on this machine at bluez 5.87-2: `/usr/share/doc/bluez/dbus-apis/settings-storage.txt` documents the `/var/lib/bluetooth/<adapter>/<device>/info` layout and the `[LinkKey]`, `[LongTermKey]` and `[PeripheralLongTermKey]` groups, and BlueZ 5.87's own `src/adapter.c` (fetched from kernel.org at tag 5.87) reads `[LinkKey] Key`, `[IdentityResolvingKey] Key`, then `[PeripheralLongTermKey]` with `[SlaveLongTermKey]` as the fallback, so all three stanzas the record names are still live and writing the LTK into both long term key groups is right. `chntpw` is `extra/chntpw 140201-5` (Arch package JSON) and is not installed here, so I extracted the package into `/tmp` and read its `MANUAL.txt`: `-e`, `hex <valuepath>` and the `b : REG_QWORD` type the BLE output shows are all real, and `reged -x` exists too. Confirmed here that `chntpw -e` tries read-write and prints `openHive(...) failed: Permission denied, trying read-only`, which is why the corrected fix copies the hive out and mounts `-o ro` instead of the record's bare read-write `mount`, a command that contradicted the record's own danger field. Confirmed here that `pacman -S --needed chntpw` is not blocked: `/usr/bin/omarchy-update-pacman-guard` aborts only when a sync and a sysupgrade flag both appear. Four real defects, so `corrected`: the fix mounted NTFS read-write, it never mentions that a BitLocker volume cannot be read this way at all (the wiki says so and current Windows enables device encryption on many installs), it says nothing about handling extracted link keys as secrets, and it ignores two Omarchy 4 behaviours I read in `/usr/share/omarchy/bin/omarchy-bluetooth-power`, `install/hardware/bluetooth.sh`, `migrations/1786380259.sh` and `shell/plugins/panels/bluetooth/Panel.qml`, namely that Bluetooth power lives in a persisted rfkill soft block so a restarted `bluetooth.service` can come back with no controller, and that the panel's forget key and `omarchy-bluetooth-device forget` both delete the device directory and the imported key with it. Where it touches the sibling record `bluetooth-panel-turned-off-while-adapter-powered`: that one is the Quickshell panel caching `Powered: false` while BlueZ says true, this one only tells the reader to check the rfkill block after the service restart, and the two do not overlap further. Also confirmed that Omarchy writes `/etc/bluetooth/main.conf` only in that one time `AutoEnable` migration, so the `ControllerMode = bredr` advice is safe, that `[General]` is line 1 of the shipped file with `#ControllerMode = dual` at line 52, that GLib merges duplicate `[General]` groups (tested with the system GLib), that `ntfs3` ships with kernel 7.1.9 while `ntfs-3g` is absent so a bare `mount` is correct, and that `bt-dualboot`, `bt-dualboot-ng` and `bluetooth-dualboot` all still exist, the first two in the AUR. `v4.0.2...v4.0.3` touches no Bluetooth file and `v4.0.3` is the newest tag. NOT exercised: there is no dual-boot Windows install here and no test device, so I never extracted a real key, never mounted an NTFS partition, never edited `/var/lib/bluetooth`, never stopped `bluetooth.service` and never paired or unpaired anything. Severity `low` and frequency `common` are left alone: the consequence is one unusable peripheral with an obvious workaround, and the hazards live in the fix rather than in the problem.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Editing files under `/var/lib/bluetooth` while `bluetooth.service` is running gets the change silently overwritten when the daemon flushes state, so stop the service first and keep a copy (`sudo cp -a /var/lib/bluetooth /var/lib/bluetooth.bak`). Mounting the Windows partition read-write while Fast Startup or hibernation is active can corrupt the NTFS filesystem: run `powercfg /h off` in Windows, do a full shutdown, and mount read only (`sudo mount -o ro ...`), because reading the hive needs nothing more. A wrong, truncated or lower case key leaves the device unusable from Linux, and editing the Windows side instead can leave it unusable from both operating systems, with `bluetoothctl remove <MAC>` and a fresh pairing in each OS as the only way back. The extracted keys are long term secrets that let anything holding them impersonate your adapter to that device, so never paste them into an issue, a paste site or a chat, and delete the hive copy and any `.reg` export when you are done. `bluetoothctl remove`, the Omarchy shell panel's forget key and `omarchy-bluetooth-device forget` all delete the device directory, so one keystroke throws an imported key away.

**Fix.**

Pair the device in **Linux first**, then reboot into Windows and pair it there. Then copy the Windows key back into BlueZ. Switch the device itself off before extracting anything so it cannot reconnect part way through.

**Extract the key from Linux (no Windows tooling needed).** Mount the Windows system drive **read only** and work on a copy of the registry hive, so nothing can write to NTFS:

```bash
sudo pacman -S --needed chntpw
lsblk -f                                      # find the NTFS partition holding Windows
sudo mkdir -p /mnt/win
sudo mount -o ro /dev/nvme0n1p3 /mnt/win      # in-kernel ntfs3, no -t needed
sudo cp /mnt/win/Windows/System32/config/SYSTEM ~/SYSTEM.hive
sudo chown "$USER" ~/SYSTEM.hive
chntpw -e ~/SYSTEM.hive
```

`chntpw -e` opens a hive read-write and only warns (`openHive(...) failed: Permission denied, trying read-only`) before falling back, so handing it a copy is what guarantees the Windows hive is never touched. If Windows is encrypted with BitLocker the hive cannot be read from Linux at all, and the Windows-side route below is the only way.

Inside `chntpw`:

```
> cd CurrentControlSet\Services\BTHPORT\Parameters\Keys
> ls                       # one subkey per adapter, named by its MAC
> cd <adapter-mac>
> ls                       # one entry per paired device
> hex <device-mac>         # non-BLE: 16 bytes, this is the link key
```

If you see `ControlSet001` instead of `CurrentControlSet`, use that. If instead of a single 16-byte `REG_BINARY` you see a subkey containing `LTK`, `KeyLength`, `ERand`, `EDIV`, `IRK`, `AuthReq`, the device is Bluetooth 5.1 / BLE and needs the extra transformations documented on the Arch Bluetooth page under "Preparing Bluetooth 5.1 Keys". Read those values with `hex <value_name>`.

**Extract from Windows instead**, if you prefer or if BitLocker is in the way: the `Keys` hive is only readable by SYSTEM, so run regedit under that account with Sysinternals PsExec (`.\PsExec64.exe -s -i regedit.exe`), navigate to `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys`, and export the adapter's key as a `.reg` file.

**Write the key into BlueZ.** Stop the daemon first so it does not overwrite your edit, and back the state directory up:

```bash
sudo systemctl stop bluetooth.service
sudo cp -a /var/lib/bluetooth /var/lib/bluetooth.bak
sudo nano /var/lib/bluetooth/<ADAPTER-MAC>/<DEVICE-MAC>/info
```

For a classic (non-BLE) device, replace the key under `[LinkKey]` and leave the `Type` and `PINLength` lines alone:

```ini
[LinkKey]
Key=0123456789ABCDEF0123456789ABCDEF
```

Uppercase hex, no spaces, no separators. For a BLE device, substitute the corresponding values under `[IdentityResolvingKey]`, `[PeripheralLongTermKey]` and `[SlaveLongTermKey]`. Write the long term key into both of those groups: BlueZ 5.87 reads `[PeripheralLongTermKey]` first and falls back to `[SlaveLongTermKey]`, and it writes both itself.

```bash
sudo systemctl start bluetooth.service
bluetoothctl connect <DEVICE-MAC>
```

**On Omarchy 4 the adapter can come back unpowered, which looks like a key failure and is not.** Omarchy keeps the Bluetooth on and off state in the rfkill soft block rather than in BlueZ, and systemd-rfkill restores that block on the next boot, so if Bluetooth was ever switched off from the shell panel BlueZ refuses to power the adapter and `bluetoothctl` reports no default controller:

```bash
omarchy-bluetooth-power is-on || omarchy-bluetooth-power on
```

Do not reach for `bluetoothctl remove`, the shell panel's `x` key or `omarchy-bluetooth-device forget <MAC>` afterwards. All three delete `/var/lib/bluetooth/<ADAPTER-MAC>/<DEVICE-MAC>/`, taking the key you just imported with it.

**Clean up the key material.** A link key is a long term secret for that device:

```bash
rm -f ~/SYSTEM.hive ~/bt-keys.reg
sudo umount /mnt/win
```

On the btrfs root Omarchy installs, `shred` cannot promise the old blocks are gone, so treat any key that left the machine as burnt and re-pair the device instead.

Some devices, notably the Logitech MX Master line and Logitech Lightspeed receivers, increment the last octet of their own MAC on each new pairing. If so, rename the directory under `/var/lib/bluetooth/<ADAPTER-MAC>/` to the incremented address that Windows recorded before restarting the daemon.

**If you want to avoid the BLE complications entirely**, force the adapter to classic transport. The shipped `/etc/bluetooth/main.conf` already carries the line commented out inside its `[General]` group, so edit it in place:

```ini
# /etc/bluetooth/main.conf
[General]
ControllerMode = bredr
```

Omarchy does not manage that file. Its only write is a one time migration that reverts the `AutoEnable=false` line Omarchy used to set, so a `ControllerMode` edit survives an `omarchy update`.

**To automate the whole thing**, `bt-dualboot` (AUR `bt-dualboot`) scripts the extraction and import and does not support BLE, a newer fork is packaged as AUR `bt-dualboot-ng`, and `bluetooth-dualboot` walks you through the commands without editing files itself.

**Between two Linux installs** this is much simpler: just make `/var/lib/bluetooth/<ADAPTER-MAC>/` identical on both, by copying or symlinking.

**Verify.** Reboot into Windows, use the device, reboot back into Linux, and connect without re-pairing. Check the edit actually survived the daemon restart first, because an edit made while `bluetooth.service` was running is the usual failure:

```bash
sudo grep -A1 '^\[LinkKey\]' /var/lib/bluetooth/<ADAPTER-MAC>/<DEVICE-MAC>/info
bluetoothctl info <DEVICE-MAC>
```

`bluetoothctl info <DEVICE-MAC>` shows `Paired: yes` and `Connected: yes` in both directions across several reboots. On Omarchy, check `omarchy-bluetooth-power is-on` before blaming the key: with the rfkill soft block set, `bluetoothctl` reports no default controller instead.

Sources: <https://wiki.archlinux.org/title/Bluetooth> · <https://wiki.archlinux.org/title/Dual_boot_with_Windows> · <https://git.kernel.org/pub/scm/bluetooth/bluez.git/plain/src/adapter.c?h=5.87> · <https://archlinux.org/packages/extra/x86_64/chntpw/json/> · <https://aur.archlinux.org/packages/bt-dualboot> · <https://aur.archlinux.org/packages/bt-dualboot-ng> · <https://github.com/x2es/bt-dualboot> · <https://github.com/nbanks/bluetooth-dualboot>

---

## Fix KDE Connect never finding the phone while everything else on the network is discoverable

`kde-connect-ports-blocked-by-ufw` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kde-connect`, `laptop`, `manjaro`, `omarchy`

**Symptom.** KDE Connect on the desktop and on the phone never see each other, while the rest of the
local network is fine: `.local` names resolve, `avahi-browse` lists other machines and network
printers appear. Pairing by typing the other device's address by hand also fails, or pairs and then
goes unavailable. Both devices are on the same subnet and the phone app reports no devices found.

**Cause.** KDE Connect does not use mDNS, so everything that makes `.local` names and printer
discovery work is irrelevant to it. It discovers over UDP broadcast and then connects on TCP, using
ports 1714 to 1764 on both protocols, which its own documentation states.

Two things on Omarchy 4 then stop it, both confirmed on an omarchy 4.0.2-1 install:

1. `/usr/share/omarchy/install/config/firewall.sh` opens only LocalSend's 53317 on both protocols. No
   Omarchy install step or migration opens the KDE Connect range, and `ufw status` on a stock machine
   shows no rule for it.
2. `/etc/ufw/after.rules:27` sends broadcast traffic to `ufw-skip-to-policy-input` under the comment
   `don't log noisy broadcast`, so the discovery packets reach the default deny policy and are
   dropped without a log line. Nothing appears in the journal to explain the silence.

This is why the symptom reads as a general network fault when nothing general is wrong.

> **Audit corrected this record.** Split out on 2026-09-11 from `mdns-local-hostnames-fail-ufw-blocks-5353`, which was
re-audited that day, came back `corrected` and was then merged into
`mdns-local-hostname-not-resolving`. KDE Connect was the one part of that record which survived its
audit intact and which is not mDNS at all, so it became its own record rather than being carried by a
record about name resolution. Every claim here was re-checked on omarchy 4.0.2-1 while splitting it:
the 1714 to 1764 range on both protocols is stated by KDE's own documentation, retrieved 2026-09-11,
`install/config/firewall.sh` opens only 53317, `ufw status` on this machine lists no rule for the
range, and `/etc/ufw/after.rules:27` is
`-A ufw-after-input -m addrtype --dst-type BROADCAST -j ufw-skip-to-policy-input` under the comment
`don't log noisy broadcast`. Not exercised: no KDE Connect client is installed here and no phone was
paired, so the remedy rests on the port range being right rather than on a reproduction.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** This opens 51 ports on two protocols to everything on the link, and KDE Connect's
pairing is what stands between that and another device on the network. On a laptop that joins café,
hotel or conference Wi-Fi, use the network-scoped form above rather than the open one.

**Fix.**

Open the range on both protocols:

```bash
sudo ufw allow 1714:1764/udp comment 'KDE Connect'
sudo ufw allow 1714:1764/tcp comment 'KDE Connect'
sudo ufw status
```

Scope it to your own network if you use café or hotel Wi-Fi, which is the better habit on a laptop:

```bash
sudo ufw allow in proto udp from 192.168.0.0/16 to any port 1714:1764 comment 'KDE Connect, LAN only'
sudo ufw allow in proto tcp from 192.168.0.0/16 to any port 1714:1764 comment 'KDE Connect, LAN only'
```

Nothing else is needed on the Omarchy side, and in particular do not reach for 5353 or for anything
about Avahi. If `.local` names or printer discovery are also failing, that is a different problem and
`mdns-local-hostname-not-resolving` covers it.

**Verify.** ```bash
sudo ufw status
```

Both `1714:1764/udp` and `1714:1764/tcp` are listed, and the phone appears in the KDE Connect app on
the desktop within a few seconds of both apps being open on the same network. If it still does not,
the fault is not the firewall: check that both devices are on the same subnet and that the phone is
not on a guest network that isolates clients.

Sources: <https://userbase.kde.org/KDEConnect> · <https://wiki.archlinux.org/title/KDE_Connect> · <https://wiki.archlinux.org/title/Uncomplicated_Firewall> · <https://git.launchpad.net/ufw/plain/conf/after.rules> · <https://github.com/omacom/omarchy/blob/quattro/install/config/firewall.sh>

---
