# Apps, containers & services

59 problems. Sorted by severity, then by how often users hit it.

## Fix btrfs "No space left on device" while df still shows free space

`btrfs-no-space-left-with-free-space` · severity: **critical** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `snapper`

**Symptom.** Writes fail with `No space left on device` and pacman refuses to install anything, but `df -h /` shows several GB free. Deleting files barely helps.

**Cause.** Btrfs allocates disk in chunks for data and metadata separately. Once all raw space is allocated to chunks, a write can fail even though the chunks are half-empty. `df` reports file-level free space and does not account for chunk allocation or metadata, so it lies about this situation.

> **Audit corrected this record.** The core claim holds. The Arch wiki Btrfs page confirms that df cannot account for chunk allocation and that `btrfs filesystem usage` is the right diagnostic, and it confirms the staged balance and `--bg` plus `balance status` sequence. The cause needed no change. Four things were wrong or missing for Omarchy 4. First, the verify line ended with `pacman -Syu`, which `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` aborts with `AbortOnFail` via `/usr/bin/omarchy-update-pacman-guard`, confirmed on this machine. The previous auditor spotted this in the note and nobody applied it. Second, the closing advice that old snapshots are usually the real consumer is mis-specialised. Confirmed on this machine, `/etc/snapper/configs/root` is Omarchy's own file with `SUBVOLUME="/"`, `NUMBER_LIMIT="5"` and `TIMELINE_CREATE="no"`, so a current install holds at most five root snapshots and deleting them reclaims little. The genuine Omarchy sink is leaked `timeline` snapshots from earlier defaults, which `number` cleanup never reaps because man snapper documents the two algorithms separately. Upstream ships a drain migration for exactly this, which I read at `/usr/share/omarchy/migrations/1784809452.sh` and whose behaviour is pinned by `test/shell.d/snapper-timeline-leak-test.sh` in the quattro tree. Third, `findmnt -t btrfs` on this machine shows four subvolumes, `@`, `@home`, `@log` and `@pkg`, matching the archinstall layout in `tools/make-test-vm.sh`, so `/home` and `/var/cache/pacman/pkg` are outside the root snapshot and `snapper -c root delete` can never reclaim them. The fix now names `paccache -rk2` and points at the right subvolumes. Fourth, the record told a reader whose balance cannot allocate to delete snapshots, with no answer for a machine that has none. The wiki names the temporary `btrfs device add` route, which is now included. I also verified as an unprivileged user that `btrfs filesystem df /` exits 0 with no sudo, which the wiki states explicitly, so the old note's instruction to add sudo there was wrong and the fix keeps it unprivileged. Added: `omarchy update` refuses to start under 10 GiB free on `/` per `/usr/share/omarchy/bin/omarchy-update-requires-free-space`, so the automatic drain is unavailable on an already-full disk. Severity `critical` and frequency `common` are left alone as correct. Both cited URLs resolve and support the generic claims, so nothing was removed. NOT exercised: I have no sudo, so no balance, no snapshot delete, no paccache run and no `btrfs device add` was executed, and the ENOSPC condition itself was not induced. The 191 GiB free on this root means the failure state could only be reasoned about, not reproduced.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A full `btrfs balance` rewrites every chunk on the filesystem. It can take hours, hammers the disk, and must not be interrupted by a hard power-off. Always start with `-dusage=10`. Metadata is the riskier half, so if `-dusage=10 -musage=10` fails, retry data only with `-dusage=10`. If the filesystem is so full that balance cannot allocate a chunk at all, add a temporary device rather than forcing it. Deleting snapshots is irreversible. On Omarchy 4 each snapshot is also a Limine boot entry, visible with `limine-list`, so deleting the `number` snapshots removes the pre-update recovery entries that `omarchy-snapshot restore` offers. `limine-snapper-sync.service` resyncs the entry list, so a deletion leaves no dead boot entry behind while that service is enabled and active. Never delete the snapshot you are currently booted into. `paccache -rk2` keeps two cached versions of each package and discards the rest, which costs the offline downgrade path for the older ones.

**Fix.**

Look at the real picture first. `btrfs filesystem df` needs no root, and `btrfs filesystem usage` shows per-device detail only as root:

```bash
btrfs filesystem df /
sudo btrfs filesystem usage /
```

If `Device allocated` is close to `Device size` while `Free (estimated)` is much larger, reclaim mostly-empty chunks by rebalancing only lightly-used ones (fast, low IO):

```bash
sudo btrfs balance start -dusage=10 -musage=10 /
sudo btrfs balance status /
```

If that is not enough, raise the threshold gradually, data first:

```bash
sudo btrfs balance start -dusage=50 /
```

Or run a full background balance:

```bash
sudo btrfs balance start --bg /
sudo btrfs balance status /
```

If balance itself fails with `No space left on device` because it cannot allocate a new chunk, give it temporary room instead of forcing it. Add a spare device or loop file, balance, then remove it:

```bash
sudo btrfs device add -f /dev/<usb-or-loop> /
sudo btrfs balance start -dusage=10 /
sudo btrfs device remove /dev/<usb-or-loop> /
```

Now find what is actually holding the space. On Omarchy 4, and on any stock four-subvolume install, `/home` and the pacman cache sit on their own subvolumes (`@home`, `@pkg`), so a root snapshot never pins them and deleting snapshots never reclaims them:

```bash
findmnt -t btrfs
sudo btrfs filesystem du -s /var/cache/pacman/pkg /var/log
sudo paccache -rk2
```

**Omarchy 4.** Snapper here is configured for pre-update recovery only: `/etc/snapper/configs/root` carries `SUBVOLUME="/"`, `NUMBER_LIMIT="5"` and `TIMELINE_CREATE="no"`, so at most five root snapshots exist and deleting them frees little. The exception is a machine installed under Omarchy's earlier defaults, which took hourly `timeline` snapshots. Those are never reaped, because `number` cleanup only reaps `number`-marked snapshots. Count them:

```bash
sudo snapper -c root --csvout list --columns number,cleanup | awk -F, '$2 == "timeline"' | wc -l
```

If that is more than a handful, let the update drain them. `omarchy update` runs a migration that deletes exactly the `timeline` ones:

```bash
omarchy update
```

`omarchy update` refuses to start with less than 10 GiB free on `/`, so on an already-full disk free that much first or drain by hand in batches of about 20:

```bash
sudo snapper -c root --csvout list --columns number,cleanup |
  awk -F, '$2 == "timeline" { print $1 }' | head -20 |
  xargs sudo snapper -c root delete --sync
```

Repeat until the count is zero, and leave the `number` snapshots alone: those are the recovery points.

**Plain Arch, EndeavourOS, CachyOS, Manjaro.** Old timeline snapshots usually are the real consumer. List them and delete a range you do not need:

```bash
sudo btrfs subvolume list /
sudo snapper -c root list
sudo snapper -c root delete --sync 20-140
```

**Verify.** `sudo btrfs filesystem usage /` shows `Device allocated` meaningfully below `Device size`, and writes succeed again. On Omarchy 4, confirm through the update entrypoint rather than pacman directly, because the `00-omarchy-update-guard.hook` ALPM hook aborts a direct `pacman -Syu`:

```bash
sudo btrfs filesystem usage /
omarchy update
```

On plain Arch use `sudo pacman -Syu`. Btrfs frees the extents of a deleted snapshot in the background, so allow a minute before reading the numbers again, or pass `--sync` to `snapper delete`.

Sources: <https://wiki.archlinux.org/title/Btrfs> · <https://wiki.archlinux.org/title/Snapper> · <https://github.com/omacom/omarchy/blob/quattro/install/config/snapper.sh> · <https://github.com/omacom/omarchy/blob/quattro/test/shell.d/snapper-timeline-leak-test.sh>

---

## Stop Docker published ports from bypassing the UFW firewall

`docker-published-ports-bypass-ufw` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `laptop`, `omarchy`, `ufw`

**Symptom.** UFW says my firewall is active and only SSH is allowed, but a container started with `-p 8080:80` is reachable from every machine on my LAN (and from the internet if the box is exposed). `sudo ufw status` looks correct and yet the port is wide open.

**Cause.** Docker in its default mode writes its own iptables/nftables rules into the `DOCKER` and `DOCKER-USER` chains, which are evaluated for forwarded traffic before UFW's INPUT rules ever apply, so a published port is reachable regardless of `ufw status`. This affects any Arch box running ufw + Docker. Note that Omarchy 4 (Quattro) already ships `ufw-docker` and runs `ufw-docker install` at install time, so the DOCKER-USER block is normally present there — check before assuming you are exposed.

> **Audit corrected this record.** The security problem, the chain explanation (DOCKER/DOCKER-USER evaluated before UFW's INPUT rules), the loopback-binding containment, `ufw-docker` (present in the AUR, last updated 2026-02) and the warning against `"iptables": false` are all accurate and still current on Docker 28/29. The Omarchy-specific sentence in the cause is stale: Omarchy 4 ships `ufw-docker` in its base package list and runs `ufw-docker install` during installation (`install/config/firewall.sh`), so Quattro is NOT the false-sense-of-protection case the record claims — pasting `yay -S ufw-docker && sudo ufw-docker install` there re-applies rules that already exist and tells the reader the wrong thing about their machine.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do NOT "fix" this by setting `"iptables": false` in `/etc/docker/daemon.json` unless you know what you are doing — that disables all of Docker's rule management and container outbound networking/NAT will break.

**Fix.**

First check whether the protection is already installed (it is by default on Omarchy 4):

```bash
sudo ufw-docker check
sudo iptables -S DOCKER-USER
grep -n 'ufw-docker' /etc/ufw/after.rules
```

If the DOCKER-USER block is missing (plain Arch, EndeavourOS, CachyOS), install it:

```bash
yay -S ufw-docker
sudo ufw-docker install
sudo systemctl restart ufw    # or: sudo ufw reload
```

Then allow individual containers explicitly (`sudo ufw-docker allow <container-name> 80/tcp`). The loopback-binding containment (`"127.0.0.1:8080:80"`) and the `"iptables": false` warning stand as written.

**Verify.** From another machine on the LAN: `nc -vz <host-ip> 8080` is refused/times out for ports you did not explicitly allow, and succeeds for the ones you did. `sudo iptables -S DOCKER-USER` shows the ufw-docker rules.

Sources: <https://wiki.archlinux.org/title/Uncomplicated_Firewall> · <https://wiki.archlinux.org/title/Docker>

---

## Fix "Cannot connect to the Docker daemon" / permission denied on docker.sock

`docker-cannot-connect-to-daemon` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Running `docker ps` prints:

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

or

```
permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
```

It works with `sudo docker ps`.

**Cause.** Two separate causes with the same symptom: the daemon is not started/enabled at all, or your user is not in the `docker` group so it cannot open the root-owned socket.

> **Audit corrected this record.** Correct for plain Arch (packages `docker`, `docker-buildx`, `docker-compose` all exist; `newgrp` caveat and the 'docker group == root' warning are right). It is wrong for Omarchy 4, which is in applies_to: `install/config/docker.sh` in v4.0.1 documents that Quattro deliberately does NOT add the install user to the `docker` group ('membership in the docker group is equivalent to passwordless root'), and ships `omarchy-sudo-docker` plus an opt-in toggle. Pasting `usermod -aG docker $USER` silently undoes a shipped hardening decision instead of using the supported path. Also, Omarchy enables `docker.socket` only, not `docker.service` (see enable-services.sh), so `enable --now docker.service` there has the side effect covered by the sibling record.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Anyone in the `docker` group is effectively root: `docker run --privileged -v /:/host ...` gives full access to the host filesystem. Do not add untrusted users. Also note the daemon can fail to start while a VPN is connected because of IP conflicts with Docker's bridge/overlay networks — disconnect the VPN, start Docker, reconnect.

**Fix.**

On plain Arch/EndeavourOS/CachyOS the fix as written is right (`sudo pacman -S docker docker-buildx docker-compose`, `sudo systemctl enable --now docker.service`, `sudo usermod -aG docker $USER`, then log out and back in).

On **Omarchy 4 (Quattro)** do not add yourself to the `docker` group by hand — Quattro intentionally leaves that group empty because it is passwordless root. Either keep using the packaged wrappers (`omarchy-sudo-docker ...`, the Docker TUI via Super+Shift+D, or plain `sudo docker ...`), or opt in explicitly, behind the warning, with:

```bash
omarchy-setup-security-sudoless-docker   # Setup > Security > Sudoless Docker
```

(and `omarchy-remove-security-sudoless-docker` to undo it). Diagnostics (`systemctl status docker.service`, `journalctl -u docker.service -b --no-pager`) and the VPN/IP-conflict note are correct as written.

**Verify.** `docker info` succeeds without sudo and `docker run --rm archlinux bash -c "echo hello world"` prints `hello world`. `id -nG` includes `docker`.

Sources: <https://wiki.archlinux.org/title/Docker>

---

## Fix screen sharing showing a black window or no sources on Wayland

`wayland-screen-share-black-or-empty` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `omarchy`, `pipewire`, `wayland`, `xdg-desktop-portal`

**Symptom.** On a Google Meet / Teams / Discord call, clicking "Share screen" either shows an empty source list or shares a completely black rectangle. Works for other people on X11.

**Cause.** On Wayland, screen capture goes through the ScreenCast portal plus PipeWire, not X11. Either PipeWire/`pipewire-pulse` and `wireplumber` are not running, or the compositor's ScreenCast backend (`xdg-desktop-portal-hyprland`) is not running, or the browser is old enough that the PipeWire capturer is behind a flag.

**Fix.**

Make sure the whole chain is installed and running:

```bash
sudo pacman -S pipewire pipewire-pulse wireplumber xdg-desktop-portal xdg-desktop-portal-hyprland
systemctl --user enable --now pipewire.service pipewire-pulse.service wireplumber.service
systemctl --user restart xdg-desktop-portal.service xdg-desktop-portal-hyprland.service
```

Firefox 84+ and Chromium 110+ support this out of the box. On older Chromium/Electron builds enable the capturer:

- visit `chrome://flags/#enable-webrtc-pipewire-capturer` and set it to Enabled, or
- launch with `--enable-features=WebRTCPipeWireCapturer`

For Electron apps also force native Wayland so the portal is used:

```bash
ELECTRON_OZONE_PLATFORM_HINT=wayland <app>
```

**Verify.** Open https://mozilla.github.io/webrtc-landing/gum_test.html and start a screen capture — the picker lists your monitors and the preview is not black. `systemctl --user status xdg-desktop-portal-hyprland` is active.

Sources: <https://wiki.archlinux.org/title/PipeWire> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal>

---

## Reclaim a full root filesystem from journal logs and the pacman cache

`disk-full-journal-and-pacman-cache` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pacman`, `systemd`

**Symptom.** On plain Arch, `pacman -Syu` fails with `error: Partition /var/cache/pacman/pkg too full: <n> blocks needed, <n> blocks free` or `not enough free disk space`, and `df -h` shows `/` at 100%.

On Omarchy 4, `omarchy update` refuses before it starts anything:

```
You need at least 10 GiB free to safely update Omarchy.
```

Either way I have not knowingly installed anything huge.

**Cause.** Two directories grow on Arch by default. `/var/cache/pacman/pkg/` keeps every downloaded package version, and `/var/log/journal/` grows to 10% of the filesystem with a soft cap at 4 GiB, because `SystemMaxUse=` is unset in the stock `journald.conf`.

On Omarchy 4 the cache half is already handled and the journal half is not. Every `omarchy update` runs `omarchy-update-pkg-prune`, which is `sudo paccache -rk2`, so the cache is trimmed to two versions per package on each update. Omarchy ships no journald drop-in, so the 4 GiB soft cap is what applies to the journal.

Omarchy's installer also puts `/var/log` on the `@log` btrfs subvolume and `/var/cache/pacman/pkg` on `@pkg`. Those share the root filesystem's free space rather than holding a quota of their own, so filling either one still fills `/`. A third consumer that plain Arch does not have is the snapper snapshots of `/`, up to five of them, taken by `omarchy update`.

> **Audit corrected this record.** The generic Arch advice is sound and the three cited wiki pages all support it, but the record is mis-specialised to Omarchy 4 in four places and its first diagnostic command is actively wrong on the stock Omarchy layout. Confirmed on this machine (omarchy 4.0.2-1, systemd 261.2-1, pacman-contrib 1.13.1-1, kernel 7.1.9): the installer puts /var/log on the @log subvolume and /var/cache/pacman/pkg on @pkg, and btrfs gives each subvolume its own device number, so `du -xh --max-depth=1 /var` skips both of the directories this record is about. Measured here it reported /var/cache as 8.6M and omitted /var/log entirely, while the same command without -x reported /var/cache 6.8G and /var/log 682M. The four-subvolume layout is not local drift: research/tools/make-test-vm.sh, written to match the ISO configurator's own output, declares @, @home, @log and @pkg. Those subvolumes share the root filesystem's free pool rather than holding a quota, confirmed because `df -h` prints an identical 475G size and 191G available for /, /var/log and /var/cache/pacman/pkg, so the record's mechanism claim that filling either fills / is correct and was kept. Second defect, in the cause: the pacman cache does not grow without bound on Omarchy 4, because /usr/bin/omarchy-update calls omarchy-update-pkg-prune, which is `sudo paccache -rk2`, on every update, and that script is byte-identical at upstream tag v4.0.3 published 2026-09-08. Third, the symptom: on Omarchy 4 the user does not reach libalpm's message, verified as the format string "Partition %s too full: %jd blocks needed, %ju blocks free" in /usr/lib/libalpm.so, because omarchy-update-requires-free-space aborts first with "You need at least 10 GiB free to safely update Omarchy." Fourth, the verify step's `pacman -Syu` cannot run at all: /usr/share/libalpm/hooks/00-omarchy-update-guard.hook fires AbortOnFail into omarchy-update-pacman-guard, and reading that script shows it aborts whenever both S and u are present, so `pacman -S pacman-contrib` in the fix is safe but the verify command is not. The previous auditor noted that guard as a nit and nobody changed the record body. Two smaller points folded in: pacman-contrib reports `Required By : omarchy` here, so the install line is a no-op on Omarchy, and omarchy-update already offers the orphan step through omarchy-update-orphan-pkgs, which runs the same `pacman -Qtdq` then `pacman -Rns`. What I kept because it held: rotate before vacuum (Arch Systemd/Journal line 175), the journald.conf.d drop-in with SystemMaxUse=, `paccache -r` keeping three and `paccache -ruk0` (Arch Pacman lines 269 and 283), and paccache.timer really shipping in pacman-contrib (`pacman -Ql pacman-contrib` lists /usr/lib/systemd/system/paccache.timer). Enabling that timer is not noise: `systemctl is-enabled paccache.timer` reports disabled on this stock Omarchy install, /etc/conf.d/pacman-contrib has an empty PACCACHE_ARGS so the unit runs a bare `paccache -r`, and Omarchy ships no journald drop-in at all, since /etc/systemd/journald.conf.d does not exist and `systemd-analyze cat-config systemd/journald.conf` shows only the package-stock file with #SystemMaxUse= commented out. I added a snapper pointer because /etc/snapper/configs/root here has SUBVOLUME="/" with NUMBER_LIMIT="5" and TIMELINE_CREATE="no", matching upstream default/snapper/root, so `omarchy update` leaves up to five snapshots of / and a reader who trims the journal and cache and still sees / full has nowhere else to look. Frequency dropped from very-common to common with a reason: the single largest driver the cause names, an unbounded package cache, is pruned on every update on this platform and the 10 GiB pre-check catches the rest early. Severity left at high, since a full root still stops updates. Not exercised: I have no sudo, so I ran no vacuum, no paccache and no orphan removal, did not fill a disk to see either error text emitted, and could not run `btrfs subvolume list /` or `snapper -c root list`, both of which refused with Operation not permitted. Upstream's own comment at bin/omarchy-update line 29 says the cache sits on the snapshotted subvolume, which disagrees with the @pkg subvolume I measured here, and I did not take a snapshot to settle it, so the corrected text asserts nothing either way about snapshot interaction with the cache. All three cited URLs resolved and support what the record draws from them, so nothing was removed.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `paccache -rk0` (keeping zero versions) removes your ability to downgrade a package offline after a bad update, so keep at least one. On Omarchy 4 keep at least two: `omarchy-update-pkg-prune` runs `paccache -rk2` and calls the cache the only offline downgrade path, so trimming below that weakens Omarchy's own rollback story.

`pacman -Qtdq | pacman -Rns -` removes anything no longer required by an explicitly installed package. Read the list before confirming, since it can pull out things you actually use if they were originally installed as dependencies.

Do not delete `/var/log/journal` itself to reclaim space. Rotate and vacuum instead, because removing that directory turns persistent logging off and you lose the logs from the next crash.

**Fix.**

Find out where it went. Do not pass `-x` to `du` here: Omarchy puts `/var/log` and `/var/cache/pacman/pkg` on separate btrfs subvolumes, which carry their own device numbers, so `-x` silently skips both of the directories you are looking for.

```bash
sudo du -h --max-depth=1 /var | sort -h | tail
journalctl --disk-usage
du -sh /var/cache/pacman/pkg
findmnt -t btrfs
```

Trim the journal. Files must be rotated before vacuum can touch them:

```bash
sudo journalctl --rotate
sudo journalctl --vacuum-size=200M
```

Cap it permanently with a drop-in. Omarchy 4 ships no journald drop-in of its own, so this directory does not exist yet:

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/00-journal-size.conf >/dev/null <<'EOF'
[Journal]
SystemMaxUse=200M
EOF
sudo systemctl restart systemd-journald.service
```

Trim the pacman cache. `paccache -r` keeps the 3 most recent versions of each package:

```bash
sudo paccache -r
sudo paccache -ruk0          # drop ALL cached versions of uninstalled packages
```

On plain Arch, install `pacman-contrib` first, then enable the weekly timer:

```bash
sudo pacman -S pacman-contrib
sudo systemctl enable --now paccache.timer
```

On Omarchy 4, `pacman-contrib` is already a dependency of `omarchy`, so that install is a no-op. `paccache.timer` ships disabled and `omarchy update` prunes the cache itself, so the timer is only worth enabling if you go long stretches between updates.

Remove orphans. `omarchy update` already offers this step through `omarchy-update-orphan-pkgs`, so on Omarchy 4 you rarely need it by hand:

```bash
pacman -Qtdq | sudo pacman -Rns -
```

If `/` is still full on Omarchy 4 after all of that, look at the snapshots `omarchy update` leaves behind:

```bash
sudo snapper -c root list
```

**Verify.** `df -h /` shows free space again and `journalctl --disk-usage` is under your cap.

On Omarchy 4, `omarchy update` gets past its free-space check and completes. Do not test with `pacman -Syu`: `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` aborts it whatever the disk looks like. On plain Arch, `pacman -Syu` completes.

Where you enabled the timer, `systemctl is-enabled paccache.timer` reports `enabled`.

Sources: <https://wiki.archlinux.org/title/Systemd/Journal> · <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/System_maintenance> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-update> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-update-pkg-prune> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-update-requires-free-space> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-update-pacman-guard> · <https://github.com/omacom/omarchy/blob/v4.0.3/default/snapper/root>

---

## Stop Ghostty dying with a SIGSEGV in its io thread by removing Omarchy's async-backend = epoll

`ghostty-epoll-backend-segfault-write-queue` · severity: **high** · frequency: **common** · applies to: `arch`, `desktop`, `ghostty`, `hyprland`, `laptop`, `omarchy`, `wayland`

**Symptom.** Ghostty disappears, taking every window in the process with it. With the single-instance launch Omarchy uses (`--gtk-single-instance=true`) that is every terminal you had open, not one. It happens while typing, on an idle terminal, and on a theme switch.

`coredumpctl` shows the same fault every time, on six machines across four Omarchy releases:

```
kernel: io[493042]: segfault at 108 ip 000055eac209190d ... in ghostty[151b90d,55eac1d52000+88d000]
```

Thread `io`, `SIGSEGV` / `SEGV_MAPERR`, fault address `0x108`, offset `ghostty + 0x151c90d`, instruction `mov 0x108(%r14),%rcx` with `r14 = 0`, build-id `36aeb61c844ddf428f960758acdb8b37f30d7e31`.

Triggers reported, in order of how deterministic they are: launching a TUI that queries terminal capabilities at startup (`herdr` every time, on two machines, to the second), a tool issuing an OSC 4 palette query, plain shell-integration traffic on a terminal idle for 23 seconds after login, and a config reload from a theme switch.

Reported on Omarchy 4.0.0rc5-1, 4.0.0-1, 4.0.1-1 and 4.0.2-1, all with Ghostty 1.3.1-2, on NVIDIA, Intel `xe` and Intel Panther Lake graphics. One reporter's `herdr` client detached cleanly and its panes survived server side, so multiplexed work comes back and anything running directly in a surface does not.

**Cause.** Omarchy ships `async-backend = epoll` at line 41 of its Ghostty config and the migration copies it into your own, where it stays. Confirmed on an omarchy 4.0.2-1 install: the line is at line 41 of both `/usr/share/omarchy/config/ghostty/config` (owned by `omarchy-settings`) and `~/.config/ghostty/config`. It was added as a workaround for slowness on Hyprland.

The epoll backend of libxev, which that setting selects, has a null dereference in its write path. The thread's source reading is against libxev rev `34fa5087`, the revision Ghostty 1.3.1 pins: `epoll.zig` checks completion state when submitting but not when dispatching, so a dead completion still reaches its callback, and the write callback opens with `const req_inner: *xev.WriteRequest = q_inner.head.?` in `stream.zig` on a queue whose head and tail are both null. `next` sits at offset `0x108` of the epoll `WriteRequest`, which is the fault address. Upstream bug `mitchellh/libxev#234`, open since 2026-08-18 with no fix, and libxev's own queued-write test skips the x86_64 dynamic case as failing.

One reporter caught `error(io_exec): write error: error.FileDescriptorAlreadyPresentInSet` logged immediately before a crash, which is `epoll_ctl` returning `EEXIST` and cannot come from an io_uring backend, so the failing write was demonstrably in the epoll path. The second crash on that machine did not log it, so treat it as a co-symptom rather than a precursor.

> **Audit corrected this record.** Confirmed on this machine, omarchy 4.0.2-1 and omarchy-settings 4.0.2-1: `async-backend = epoll` is line 41 of `/usr/share/omarchy/config/ghostty/config`, `pacman -Qo` names `omarchy-settings 4.0.2-1` as its owner, and `diff` shows `~/.config/ghostty/config` byte-identical to the shipped file, so the migration claim holds. Also confirmed here that `/usr/bin/omarchy-refresh-config` copies the shipped file over the user one after saving `$user_config_file.bak.$(date +%s)`, which is what the fix warns about. I read `omacom/omarchy#6868` in full with comments: six reporters across 4.0.0rc5-1, 4.0.0-1, 4.0.1-1 and 4.0.2-1, all Ghostty 1.3.1-2, all the same `io` thread SIGSEGV at `ghostty + 0x151c90d` with `r14 = 0` faulting on `mov 0x108(%r14),%rcx`, on NVIDIA, Intel xe and Panther Lake, with the herdr, OSC 4, idle and theme-reload triggers the symptom lists. The thread supports the claim. I verified the libxev source claims directly rather than trusting the thread: `src/watcher/stream.zig:818` is `const req_inner: *xev.WriteRequest = q_inner.head.?`, `src/backend/epoll.zig:380` guards submission with `if (c.flags.state != .adding) continue` while the dispatch callbacks at lines 432, 452 and 494 have no such guard, and `test "pty: queued writes"` skips itself with `if (xev.dynamic and builtin.cpu.arch == .x86_64) return error.SkipZigTest`. `mitchellh/libxev#234` is open with no fix, and libxev main is still `9ce8e8e6` dated 2026-05-06, so nothing has landed. Two things were wrong in the fix and I rewrote it. First, the sentence "PR 7649 is not this one" cites `omacom/omarchy#7649`, which is a closed pull request titled "Fix Codex usage collection on 0.149" and appears nowhere in issue 6868 or pull request 6963, so it was misleading noise and is gone. Second, the release statement needed re-checking against a tag published after the record was written: `v4.0.3` (2026-09-08) and the `quattro` branch both still carry the epoll line at line 41, which is stronger evidence than the pull request being open, so the rewritten fix states both and adds a grep to tell when the fix ships. Not exercised: Ghostty is not installed on this workstation (only `foot 1.27.0-2`), so I could not run the `sed`, reproduce the crash, or see the `libxev manual backend=epoll` startup line, and the `verify` block is unchanged but untested here.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Remove the setting from your own config. Do not edit the file under `/usr/share/omarchy`: it belongs to the `omarchy-settings` package and is not the file Ghostty reads.

```bash
grep -n 'async-backend' ~/.config/ghostty/config
sed -i '/^async-backend = epoll$/d' ~/.config/ghostty/config
```

Then quit every Ghostty window and start it again. The crash lives in the long-running single-instance process, so a reload is not enough to leave the epoll backend behind. Ghostty falls back to its default backend, which is what the reporter who found the deterministic `herdr` trigger did.

Two things to know afterwards. `omarchy-refresh-config ghostty/config` copies the shipped file back over yours, epoll line included, after saving your version as `~/.config/ghostty/config.bak.<epoch>`, so if you ever run it you will need to delete the line again. And the removal is what upstream intends: `omacom/omarchy#6963`, "Remove unsafe Ghostty epoll workaround", was still open on 2026-09-11, and the newest tag `v4.0.3` (2026-09-08) still carries `async-backend = epoll` at line 41 of `config/ghostty/config`, as does the `quattro` branch. A plain `omarchy update` therefore does not fix this yet. Check whether it has landed before editing by hand:

```bash
grep -n 'async-backend' /usr/share/omarchy/config/ghostty/config   # no output once the PR ships
```

If you would rather keep the workaround the setting was added for, there is nothing else in the thread to offer: libxev has no fix, `mitchellh/libxev#237` was backported and measured in the issue thread without significantly reducing the crash rate, and Ghostty upstream asked for a debug build rather than more stripped 1.3.1-2 cores.

**Verify.** ```bash
grep -c 'async-backend' ~/.config/ghostty/config     # 0
coredumpctl list ghostty                              # no new entry after the restart
```

Ghostty's startup log line `info(gtk_ghostty_application): libxev manual backend=epoll` is what the setting produces, so its absence is the direct check.

Sources: <https://github.com/omacom/omarchy/issues/6868> · <https://github.com/omacom/omarchy/pull/6963> · <https://github.com/mitchellh/libxev/issues/234> · <https://github.com/omacom/omarchy/pull/7649> · <https://github.com/omacom/omarchy/blob/v4.0.3/config/ghostty/config> · <https://github.com/mitchellh/libxev/pull/237> · <https://github.com/mitchellh/libxev/blob/main/src/watcher/stream.zig> · <https://github.com/mitchellh/libxev/blob/main/src/backend/epoll.zig> · <https://github.com/mitchellh/libxev/blob/main/src/queue.zig>

---

## Fix virt-manager failing to connect to qemu:///system

`libvirt-virt-manager-permission-denied` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `hyprland`, `kvm`, `libvirt`, `manjaro`, `omarchy`, `polkit`, `qemu`

**Symptom.** virt-manager shows the connection as "Not Connected" and errors with `authentication unavailable: no polkit agent available` or `Failed to connect socket to '/var/run/libvirt/libvirt-sock': Permission denied`. `sudo virsh list --all` works fine.

**Cause.** The `qemu:///system` RW socket is protected by polkit (the default `unix_sock_auth` on Arch since libvirt pulls in polkit). Without group membership or a running polkit authentication agent, the connection is refused.

> **Audit corrected this record.** Most of this is right: polkit gating of the `qemu:///system` RW socket, the `libvirt` group having password-less access, the `org.libvirt.unix.manage` polkit action id, the package names (`libvirt`, `qemu-desktop`, `virt-manager`, `dnsmasq`, `iptables-nft`, `edk2-ovmf` all exist), and the `libvirt-qemu` group (Arch's libvirt does ship `/usr/lib/sysusers.d/libvirt-qemu.conf`, so that chown target is real). Three problems: (1) the polkit-agent instruction writes `exec-once = ...` into `~/.config/hypr/hyprland.conf`, which Hyprland 0.55+ and Omarchy 4 no longer read (config is `hyprland.lua`); (2) libvirt is mid-migration to modular daemons — `virtqemud.service/.socket`, `virtnetworkd`, `virtstoraged` etc. all ship in Arch's libvirt package and are the direction upstream is taking (monolithic `libvirtd` is slated for removal), and mixing the two setups is a known way to end up with a half-working stack; (3) `virtlogd` is socket-activated and pulled in by the daemon — enabling `virtlogd.service` is unnecessary. Minor: `chown -R $USER:libvirt-qemu` alone does not fix 'search permissions' when `$HOME` is mode 0700, since the QEMU user still cannot traverse it.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Members of the `libvirt` group can define and start VMs with arbitrary host device and disk passthrough — it is close to root-equivalent. A reboot may be required before polkit-based authentication behaves correctly. Permission changes to system directories under `/usr` or `/var/lib/libvirt` are lost on package update.

**Fix.**

Install the stack as written, then pick **one** daemon model and do not mix them:

```bash
sudo pacman -S libvirt qemu-desktop virt-manager dnsmasq iptables-nft edk2-ovmf
# modular daemons (the direction upstream is going):
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket virtstoraged.socket
# ...OR the monolithic daemon, if that is what your system already uses:
sudo systemctl enable --now libvirtd.socket
```

Do not enable `virtlogd.service` by hand — it is socket-activated. Check what you are already running with `systemctl list-units 'virt*' 'libvirtd*'` before changing anything.

Group membership (`sudo usermod -aG libvirt $USER`, then log out and back in) and the `/etc/polkit-1/rules.d/50-libvirt.rules` snippet are correct as written.

For the polkit agent: Omarchy already runs one (`pgrep -af polkit`) — check before adding anything. If you do need to start one and you are on Hyprland 0.55+ / Omarchy 4, the config is Lua, not `hyprland.conf`: add it to `~/.config/hypr/autostart.lua` (`o.launch_on_start("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1")`), or better install `hyprpolkitagent` and enable its user unit. Only pre-0.55 Hyprland takes the `exec-once =` line.

For 'doesn't have search permissions': moving the image into `/var/lib/libvirt/images` + `sudo virsh pool-refresh default` is the reliable fix. If you keep it under `$HOME`, `chown` is not enough on a 0700 home — grant traversal explicitly, e.g. `sudo setfacl -m u:libvirt-qemu:x /home/$USER` (and on each parent directory) plus read access on the image.

**Verify.** `virsh -c qemu:///system list --all` works as your normal user, and virt-manager shows "QEMU/KVM" connected. `id -nG` includes `libvirt`.

Sources: <https://wiki.archlinux.org/title/Libvirt>

---

## Get a working rollback safety net when the boot menu has no snapshot entries

`no-snapshot-rollback-without-limine-btrfs` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** An update broke the desktop and every guide says "boot the snapshot from the boot menu", but there are no snapshot entries: the machine uses GRUB or systemd-boot, or the root filesystem is ext4, or it is a plain Arch/EndeavourOS install that was never set up for snapshots. `snapper -c root list` errors with `Unknown config`, or `snapper` is not installed at all.

On a stock Omarchy 4 install this should not happen. `snapper` and `limine-snapper-sync` are installed and configured out of the box and `limine-snapper-sync` writes a `Snapshots` submenu into the Limine menu, so run `limine-list` and `sudo snapper -c root list` before concluding you have no safety net.

**Cause.** Bootable snapshot rollback is not one kernel feature. It needs three things together: btrfs subvolumes, a snapshot tool (snapper), and a bootloader integration that writes menu entries for those snapshots. Miss any one of them and there is nothing to boot.

Omarchy 4 ships all three. `snapper` and `limine-snapper-sync` come from Omarchy's own pacman repo at `https://pkgs.omarchy.org/stable/$arch`, `/usr/share/omarchy/install/config/snapper.sh` installs `/etc/snapper/configs/root` from the `/usr/share/omarchy/default/snapper/root` template (root subvolume only, `NUMBER_LIMIT="5"`, `TIMELINE_CREATE="no"`), and it enables `snapper-cleanup.timer` and `limine-snapper-sync.service` while disabling `snapper-timeline.timer`. `omarchy update` calls `omarchy-snapshot create` before it upgrades anything, and `omarchy-snapshot restore` hands off to `limine-snapper-restore`. The read-only-snapshot problem is handled too: the `btrfs-overlayfs` hook from `limine-mkinitcpio-hook` is the last entry in `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`.

Everywhere else you have to build it. On GRUB you need `grub-btrfs`, on rEFInd `refind-btrfs`, on Limine `limine-snapper-sync` from the AUR. On a non-btrfs root none of it applies and you need file-level backups instead.

> **Audit corrected this record.** Checked against this Omarchy 4 workstation (omarchy 4.0.2-1, snapper 0.13.1-3, limine-snapper-sync 1.31.0-1, kernel 7.1.9) and against the cited Snapper and Timeshift wiki pages plus the Limine wiki page, all fetched as raw wikitext. The generic structure held and I kept it: recover first with `pacman -U` from `/var/cache/pacman/pkg` then build the net, the filesystem triage, `grub-btrfs` plus `grub-btrfsd.service` for GRUB, rsync-mode Timeshift for non-btrfs, `snap-pac` for automatic pre/post snapshots, and the closing point that a system rollback is not a `/home` backup. Timeshift's hard `cronie` dependency is confirmed from `pacman -Si timeshift`, matching the wiki note. The Omarchy branch was wrong. `yay -S limine-snapper-sync` does not apply here: I confirmed with `pacman -Qi` that limine-snapper-sync 1.31.0-1 is installed from the `omarchy` repo (`Server = https://pkgs.omarchy.org/stable/$arch` in /etc/pacman.conf), not the AUR, and the whole net is already configured. I read `/usr/share/omarchy/install/config/snapper.sh`, which installs `/etc/snapper/configs/root` from `/usr/share/omarchy/default/snapper/root` and enables `snapper-cleanup.timer` and `limine-snapper-sync.service` while disabling `snapper-timeline.timer`. `systemctl is-enabled` on this machine confirms enabled, enabled, disabled. `limine-list` printed a live `Snapshots` submenu with two real entries, so the symptom as written cannot occur on a stock Omarchy 4 and I rewrote it to send the reader to `limine-list` first. I read `/usr/share/omarchy/bin/omarchy-snapshot` (create and restore, the latter calling `limine-snapper-restore`) and confirmed `/usr/bin/omarchy-update` line 36 calls `omarchy-snapshot create`, so the `snap-pac` claim needed an Omarchy exception: `pacman -Q snap-pac` reports the package is not installed. The `sudo mkinitcpio -P` line is correct where it stands, in the plain-Arch GRUB branch, but it needed labelling, because `/etc/mkinitcpio.d/` is empty here and `/usr/bin/mkinitcpio` line 986 dies with `No presets found in /etc/mkinitcpio.d`. I added the wiki caveat the record omitted, that `grub-btrfs-overlayfs` is a runtime hook with no systemd unit and is incompatible with a systemd initramfs (Snapper wiki, Booting into read-only snapshots), which matters because the stock `/etc/mkinitcpio.conf` on this machine ships `systemd` in HOOKS. I also recorded that Omarchy already solves the overlay problem: `btrfs-overlayfs` from `limine-mkinitcpio-hook` is the last hook in `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`, which is what the Limine wiki tells you to add after `filesystems`. The `pacman -U` recovery step is safe on Omarchy and I said so, having read `/usr/bin/omarchy-update-pacman-guard`, which aborts only when both sync and sysupgrade flags are present. NOT exercised: I have no sudo, so I ran no `snapper` command, took no snapshot, restored nothing, and did not boot a snapshot entry. The GRUB, rEFInd and Timeshift branches could not be tested on this machine at all and rest on the wiki. The `danger` field was left unchanged because both of its claims, the subvolid trap after a restore and Timeshift btrfs mode ignoring the exclude list, are confirmed in the Snapper and Timeshift wikis respectively. All three cited sources resolve and support what the record draws from them, so nothing is removed.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Converting an existing installation to a snapshot-friendly btrfs layout means moving subvolumes and reinstalling/reconfiguring the bootloader — get it wrong and the machine does not boot. In particular, if `genfstab` wrote a `subvolid=` option for `/` or `/home`, remove it or you will be unable to boot *after* restoring a snapshot. Do that work from a live ISO with a full backup already taken, never on a machine you need working in an hour. `timeshift --restore` overwrites system files in place; read the excluded/included paths in `/etc/timeshift/timeshift.json` before running it, and note that Timeshift in btrfs mode ignores the `exclude` list entirely.

**Fix.**

**Recover first, then build the net.** With no snapshot to boot, roll back the specific breakage from the pacman cache:

```bash
ls /var/cache/pacman/pkg/ | grep <package>
sudo pacman -U /var/cache/pacman/pkg/<package>-<older-version>-x86_64.pkg.tar.zst
```

Omarchy's ALPM guard does not block this. `/usr/bin/omarchy-update-pacman-guard` aborts a transaction only when the pacman command line carries both a sync and a sysupgrade flag, so `pacman -U` and `pacman -S --needed` run normally while `pacman -Syu` is refused in favour of `omarchy update`.

If the system will not boot at all, boot the Arch or Omarchy ISO, mount and `arch-chroot` in, and do the same from there.

**On Omarchy 4, check what you already have before installing anything:**

```bash
pacman -Q snapper limine-snapper-sync
sudo snapper -c root list
limine-list
systemctl is-enabled limine-snapper-sync.service snapper-cleanup.timer
```

`limine-list` prints the boot menu tree, including a `Snapshots` submenu once entries exist. Take one and roll back with Omarchy's own wrappers:

```bash
omarchy-snapshot create
omarchy-snapshot restore     # runs limine-snapper-restore
```

If `snapper -c root list` really does say `Unknown config` on Omarchy, the config was never written. Re-run Omarchy's setup rather than hand-rolling one, so you get its retention settings:

```bash
sudo bash -euo pipefail /usr/share/omarchy/install/config/snapper.sh
```

**Everywhere else, the path depends on the filesystem:**

```bash
findmnt -no FSTYPE /
cat /proc/cmdline | tr ' ' '\n' | grep -E 'rootflags|subvol'
bootctl status 2>/dev/null | head -5
```

*btrfs root plus GRUB, not Omarchy.* Snapshots in the GRUB menu:

```bash
sudo pacman -S --needed snapper snap-pac grub-btrfs inotify-tools
sudo snapper -c root create-config /
sudo systemctl enable --now grub-btrfsd.service
sudo grub-mkconfig -o /boot/grub/grub.cfg
sudo snapper -c root list
```

Snapper's snapshots are read-only, and many services need a writable `/var`, so booting one straight up often fails. Boot them through an overlay instead:

```bash
# add grub-btrfs-overlayfs to the END of HOOKS in /etc/mkinitcpio.conf
sudo mkinitcpio -P
```

Two traps there. `grub-btrfs-overlayfs` is a runtime hook with no systemd unit, so it does nothing in a systemd-based initramfs, and Arch's stock `/etc/mkinitcpio.conf` now ships `systemd` in `HOOKS`. Use the busybox hooks (`base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck`) or the overlay silently has no effect. And `sudo mkinitcpio -P` is the plain-Arch rebuild only: on Omarchy 4 `/etc/mkinitcpio.d/` is empty and `mkinitcpio -P` exits with `No presets found in /etc/mkinitcpio.d`, writing no boot image. The Omarchy rebuild is `sudo limine-mkinitcpio` followed by `sudo limine-update`.

*btrfs root plus Limine, built by hand on plain Arch.* This is what Omarchy already has, so do this only on a system you assembled yourself:

```bash
yay -S limine-snapper-sync
sudo pacman -S --needed snapper snap-pac
```

Then add `limine-mkinitcpio-hook`'s overlay hook after `filesystems` in `HOOKS`: `btrfs-overlayfs` with the busybox hooks, or `sd-btrfs-overlayfs` with the systemd hooks, because `btrfs-overlayfs` is incompatible with a systemd initramfs.

*Non-btrfs root (ext4, xfs).* Snapshots are not possible. Use rsync-mode Timeshift, which works on any filesystem. The `timeshift` package hard-depends on `cronie`, so enable it:

```bash
sudo pacman -S --needed timeshift cronie
sudo systemctl enable --now cronie.service
sudo timeshift-gtk        # choose RSYNC mode, pick a target device
sudo timeshift --create --comments "baseline"
sudo timeshift --list
```

Restore later with:

```bash
sudo timeshift --restore --snapshot "<snapshot>"
```

Either way, snapshot *before* risky changes, not after:

```bash
omarchy-snapshot create                                   # Omarchy 4
sudo snapper -c root create --description "before upgrade" # plain Arch
sudo timeshift --create --comments "before upgrade"        # non-btrfs
```

On plain Arch, installing `snap-pac` makes pacman take pre/post snapshots around every transaction automatically. Omarchy does not ship or use `snap-pac`. `/usr/bin/omarchy-update` calls `omarchy-snapshot create` itself, which runs `snapper create -c number` followed by `snapper cleanup number` for every configured snapper config.

Note that neither approach protects `/home` unless you configure it separately. A system rollback leaves your data as it is, which is usually what you want but is not a backup. Pair it with restic or borg for actual data backup.

**Verify.** On Omarchy 4: `pacman -Q snapper limine-snapper-sync` returns both, `systemctl is-enabled limine-snapper-sync.service snapper-cleanup.timer` reports `enabled` for both, `sudo snapper -c root list` lists snapshots, and `limine-list` prints a `Snapshots` submenu under the `Omarchy` entry. Elsewhere: `sudo snapper -c root list` (or `sudo timeshift --list`) shows snapshots, and for the btrfs paths a reboot presents a snapshot submenu in the bootloader that actually boots.

Sources: <https://wiki.archlinux.org/title/Snapper> · <https://wiki.archlinux.org/title/Timeshift> · <https://wiki.archlinux.org/title/Restic> · <https://wiki.archlinux.org/title/Limine>

---

## Make Omarchy's Docker containers come back after a reboot

`omarchy-docker-containers-dead-after-reboot` · severity: **high** · frequency: **common** · applies to: `arch`, `docker`, `omarchy`, `systemd`

**Symptom.** I installed Postgres/MySQL/Redis from Omarchy's Install > Development > Docker DB menu. It works, but after every reboot my app cannot connect — `connection refused` on `127.0.0.1:5432` — until I run `docker ps` once, after which everything springs to life.

**Cause.** Omarchy deliberately enables only `docker.socket` and leaves `docker.service` disabled to keep boot fast. Socket activation only fires when something actually touches `/run/docker.sock`. Published container ports are served by `docker-proxy`, a child of the daemon, which does not exist while the daemon is inactive — so the containers' `--restart unless-stopped` policy is never evaluated at boot.

**Fix.**

Enable the service alongside the socket:

```bash
sudo systemctl enable --now docker.service
```

Omarchy already ships a drop-in at `/etc/systemd/system/docker.service.d/no-block-boot.conf` that takes Docker off the critical boot path, so this does not slow down boot. Confirm both are enabled:

```bash
systemctl is-enabled docker.service docker.socket
```

And confirm the containers themselves have a restart policy:

```bash
docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}}' $(docker ps -aq)
docker update --restart unless-stopped <container>
```

**Verify.** Reboot, and without running any docker command, `ss -ltnp | grep 5432` shows the port listening and your app connects.

Sources: <https://github.com/basecamp/omarchy/issues/8541> · <https://wiki.archlinux.org/title/Docker>

---

## Understand what an Omarchy snapshot rollback does and does not restore

`omarchy-snapshot-restore-keeps-home` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `hyprland`, `limine`, `omarchy`

**Symptom.** An update broke my system. I booted an older snapshot from the Limine boot menu and ran the restore, but my apps still misbehave — configs seem to be from the broken version, and I am unsure whether my documents were rolled back too.

**Cause.** Omarchy takes a btrfs snapshot on every update and exposes them in the Limine boot menu. The restore rolls back the root subvolume only. `/home` — including `~/.config` — is deliberately left untouched so personal files survive, which means config files written in a newer format stay behind and can conflict with the older restored system.

> **Audit corrected this record.** Almost everything matches Omarchy 4's own manual (manual/47-system-snapshots.md) close to verbatim: snapshot on every update, pick the dated entry in Limine with the version shown bottom-left, the 'you are in a bootable snapshot' notification, `omarchy-snapshot create` / `omarchy-snapshot restore` (the script exists and `restore` calls `limine-snapper-restore`), root restored but `/home` and `~/.config` left alone, Limine-only and default since Omarchy 2.0. `omarchy-debug` and `omarchy-reinstall` also exist. The one stale piece is the recovery advice: Omarchy 4 has no 'Update > Config' menu entry that restores a single config to its shipped default. Quattro's equivalents are `omarchy-refresh-config <path>` (copies one shipped config from `$OMARCHY_PATH/config` into `~/.config`, backing up yours) and the per-component refreshers; `omarchy-reinstall-configs` is the blunt one and is destructive — it replays all of `/etc/skel` over `$HOME`.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Rolling back root while keeping `/home` can leave newer config formats in `~/.config` that the older software cannot read — expect to reset some configs by hand. Snapshot restore is only available on installs using the Limine boot loader (default since Omarchy 2.0); GRUB and systemd-boot installs have no rollback path, so back up before big updates. Restoring does not roll back your documents, so it is not a data-recovery mechanism.

**Fix.**

Snapshot/restore flow is right as written (`omarchy-snapshot create` before anything risky; reboot, pick the dated Limine entry, then the notification or `omarchy-snapshot restore`).

For the configs left behind in `~/.config`, use Quattro's refreshers rather than a 'Update > Config' menu entry:

```bash
omarchy refresh config hypr/hyprland.lua   # one shipped config; backs up yours as *.bak.<epoch>
omarchy refresh hyprland                   # per-component refreshers: hyprland, shell, limine, sddm, ...
```

Only if you want everything back to defaults:

```bash
omarchy reinstall configs   # DESTRUCTIVE: re-copies all of /etc/skel over $HOME
```

`omarchy-debug` for diagnostics and `omarchy-reinstall` for a broken component stay as written. Note the config paths are now Lua (`~/.config/hypr/hyprland.lua`), not `.conf`.

**Verify.** After restore and reboot, the version shown in the Limine entry matches the snapshot you selected, and the previously broken behaviour is gone. `sudo btrfs subvolume list /` shows the restored root.

Sources: <https://learn.omacom.io/2/the-omarchy-manual/101/system-snapshots> · <https://learn.omacom.io/2/the-omarchy-manual/88/troubleshooting>

---

## Windows VM launch does nothing after the polkit password (setgid bit on ~/Windows fails the mode check)

`omarchy-windows-vm-launch-silent-setgid-chmod` · severity: **high** · frequency: **common** · applies to: `arch`, `desktop`, `docker`, `laptop`, `omarchy`, `windows-vm`

**Symptom.** Omarchy 4.0.2-1. Apps menu > Windows, or `omarchy-windows-vm launch`, shows the polkit password dialog, accepts the password, and then nothing happens: no error, no window. Every retry asks for the password again. From a terminal the elevated step exits 1 with no output:

```console
$ stat -c %a ~/Windows
2700
$ pkexec /usr/bin/omarchy-windows-vm __priv up; echo $?
1
```

`omarchy-windows-vm remove` fails the same way with `Windows VM removal stopped before user-side cleanup`, so reinstalling does not help. It hits installs upgraded from 4.0.1 (`~/Windows` at `drwx--S---`) and fresh 4.0.2 installs from the second launch onward. Six reporters confirmed it on Intel and AMD machines, all on kernel 7.1.9-arch1-2, coreutils 9.11 and btrfs.

**Cause.** Established by the reporters and confirmed on this machine. `prepare_caller_mounts()` in `/usr/bin/omarchy-windows-vm` (line 583 in omarchy 4.0.2-1) runs `chmod 0700` on the pinned `~/.windows` and `~/Windows` sources and then requires `stat -Lc %a` to return exactly `700`. GNU coreutils `chmod` deliberately preserves a directory's setuid and setgid bits when given a numeric mode of four or fewer digits, so `chmod 0700` leaves `2700` as `2700` and the check returns 1. The same strict `mode == 700` test is in `mounted_leaf_matches()` (line 508), and `assert_mounts_safe` gates `launch`, `install` and `remove`, so none of them can recover. The `dockurr/windows` container sets the shared folder (`~/Windows` on the host) to `2777` when it starts against an **empty** share, which is why the second launch fails on a fresh install. One reporter traced that to the emptiness probe in the image's `/run/samba.sh` and found a non-empty share is left alone. `windows-vm.desktop` has `Terminal=false`, so the failure is invisible. This is coreutils behaviour, not a kernel regression, which the original report first claimed and then retracted.

> **Audit corrected this record.** Checked the code path against the installed script and the upstream tree, and checked the coreutils behaviour by experiment on this machine. Confirmed here on omarchy 4.0.2-1: line 583 of `/usr/bin/omarchy-windows-vm` is exactly `chmod 0700 -- "/proc/$BASHPID/fd/$storage_fd" "/proc/$BASHPID/fd/$shared_fd"`, and lines 588 to 590 reject any mode that is not `700`. `mounted_leaf_matches()` starts at line 508 and its test at line 518 is `$mode == 700`. `assert_mounts_safe()` at line 839 is called by `__priv_up` (line 896), `__priv_up_wait` (line 902) and `__priv_remove` (line 931), so launch, install and remove all gate on it. `up` is an accepted privileged action (line 149) and `with_vm_lock` returns the action's own status (line 131), which makes the record's exit 1 from `pkexec ... __priv up` consistent with the code. The desktop entry written at line 1170 does carry `Terminal=false`, and the `Windows VM removal stopped before user-side cleanup` message is at line 1373. `gh api` on `repos/omacom/omarchy/contents/bin/omarchy-windows-vm?ref=quattro` returned a file byte-identical to the installed one, and the v4.0.2 to v4.0.3 compare does not list `bin/omarchy-windows-vm`, so nothing has been fixed upstream. Issue 9334 is open and supports the cause in full, including the retraction of the original kernel claim, the `dockurr/windows` emptiness probe in the image's `/run/samba.sh`, the `hide dot files = yes` detail, and the inode and bind-anchor warning. PR #9322 is still open with `merged_at` null and its diff is the `chmod u=rwx,go=,a-s` change the record describes, so the fix section's claim that nothing has merged holds today, 2026-09-11. Measured in a throwaway `/tmp` directory here with coreutils 9.11: `chmod 0700` and `chmod 700` leave `2700` at `2700` and turn `2777` into `2700`, `chmod 00700` gives `700` from both, and the same preservation happens through the `/proc/$$/fd/N` indirection the script uses. That experiment is where the record broke. Its fix leads with `chmod g-s ~/Windows ~/.windows` and tells the reader to expect `700`, but `g-s` on the `2777` that the container leaves behind yields `777`, so a user following that check on the common fresh-install case sees `777` and concludes the workaround failed. The launch does still succeed from `777`, so the rewrite keeps `g-s` as a labelled alternative and leads with `chmod 00700`, which is the upstream issue's own recommendation and is correct from either starting mode. Two minor overreaches left in the symptom rather than rewritten: the thread carries seven confirmations, not six, and only four of them state kernel, coreutils and btrfs together, so "all on" is a little stronger than the source. Intel and AMD are both supported, since the reporter's machine is Intel CoffeeLake-H and christianguenter2 reports an AMD Ryzen AI 5 340. Not exercised: no Windows VM is installed here, `~/.windows` and `/var/lib/omarchy/windows` do not exist, `~/Windows` is a symlink to `/srv/vms/windows/shared`, and with no sudo I could not run `pkexec ... __priv up`, watch the container set `2777`, or read `/run/samba.sh` inside the image. Those three claims rest on the issue thread alone.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

No upstream fix has merged as of 2026-09-11. `bin/omarchy-windows-vm` on the `quattro` branch is byte-identical to the installed 4.0.2-1 copy and still runs `chmod 0700` at line 583, and v4.0.3 (2026-09-08) does not touch the file. PR #9322 (clear the special bits with `chmod u=rwx,go=,a-s` while keeping the strict check) is open, as are a dozen duplicate PRs for the same line, including #10046 and #10113.

Until one lands, clear the bits in place. `chmod` never changes the inode, so the root-owned bind anchor under `/var/lib/omarchy/windows/mounts/users/<uid>/` stays valid:

```bash
chmod 00700 ~/Windows ~/.windows
stat -c '%a %n' ~/Windows ~/.windows    # both 700
omarchy-windows-vm launch
```

Use the five-digit `00700`. It clears the setgid bit and sets mode 700 from either starting state, the `2700` of an upgraded install or the `2777` the container leaves behind. Measured on this workstation, omarchy 4.0.2-1 with coreutils 9.11:

```console
$ mkdir -m 2777 /tmp/sg && chmod 0700 /tmp/sg && stat -c %a /tmp/sg
2700
$ chmod 00700 /tmp/sg && stat -c %a /tmp/sg
700
```

`chmod g-s ~/Windows ~/.windows` also brings the next launch straight up and four reporters confirmed it, but do not expect mode 700 from it. It clears only the setgid bit, so a share the container left at `2777` becomes `777`, and the script's own `chmod 0700` is what takes it to 700 on the next launch. `chmod 0700` and `chmod 700` clear nothing at all.

The bit comes back whenever the container starts against an empty `~/Windows`, so either repeat the `chmod 00700` before each launch, or leave any file in the folder. A dotfile stays hidden from the guest because the generated `smb.conf` keeps Samba's default `hide dot files = yes`:

```bash
touch ~/Windows/.keep
```

Do not move or recreate `~/Windows`. That changes the inode, and the next launch then fails with `protected mount ... no longer matches its home source` until the anchor is unmounted with `pkexec umount /var/lib/omarchy/windows/mounts/users/$(id -u)/shared`.

**Verify.** ```bash
stat -c '%a %n' ~/Windows ~/.windows          # 700 and 700 after chmod 00700, no leading 2
pkexec /usr/bin/omarchy-windows-vm __priv up; echo $?   # 0 and the container comes up
```

If you used `chmod g-s` instead, expect `777` on a share the container had left at `2777`. That is not a failure. The launch still succeeds, because with no special bit in the way the script's own `chmod 0700` clears group and other access.

Sources: <https://github.com/omacom/omarchy/issues/9334> · <https://github.com/omacom/omarchy/pull/9322> · <https://github.com/omacom/omarchy/pull/10046> · <https://github.com/omacom/omarchy/pull/10113> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-windows-vm> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3>

---

## Fix rootless Podman failing with missing subuid/subgid ranges

`podman-rootless-missing-subuid` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `containers`, `endeavouros`, `flatpak`, `linux-hardened`, `manjaro`, `omarchy`, `podman`

**Symptom.** `podman run` as a normal user fails with something like:

```
ERRO[0000] cannot find UID/GID for user myuser: no subuid ranges found for user "myuser" in /etc/subuid
```

or `newuidmap: write to uid_map failed`. Running as root works.

**Cause.** Rootless containers need a range of subordinate UIDs/GIDs allocated to your user. Accounts created before `shadow` 4.11.1-3 (i.e. most long-lived Arch installs) have no entries in `/etc/subuid`/`/etc/subgid`, and `systemd-homed` users never get them.

> **Audit corrected this record.** The main fix is right: `usermod --add-subuids/--add-subgids`, checking `/etc/subuid`/`/etc/subgid` for overlap, 65536 as the practical range size, and `podman system migrate` to make Podman pick up the new mapping. `bubblewrap-suid` does exist in extra, so that note is fine. The secondary step is misleading on Arch: `kernel.unprivileged_userns_clone` is a hardened-kernel patch knob — it exists on `linux-hardened` but NOT on the stock `linux` kernel, where `sysctl kernel.unprivileged_userns_clone` errors out and the `/etc/sysctl.d/99-userns.conf` file the record tells you to write is inert. A reader on the stock kernel will chase a non-problem and end up with a dead sysctl drop-in.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Enabling `kernel.unprivileged_userns_clone=1` has real security implications — it is set to 0 on `linux-hardened` on purpose. Also, overlapping subuid ranges between users breaks isolation, so always check `/etc/subuid` before picking a block.

**Fix.**

Allocate the range and migrate exactly as written:

```bash
cat /etc/subuid /etc/subgid            # check the block is free first
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
podman system migrate
```

(or write `myuser:524288:65536` into both files by hand if 100000 is taken).

On the user-namespace check, be kernel-specific: `kernel.unprivileged_userns_clone` only exists on `linux-hardened` (and other patched kernels). On the stock `linux`/`linux-lts`/`linux-zen` kernels the sysctl does not exist and unprivileged user namespaces are already enabled — `sysctl kernel.unprivileged_userns_clone` returning 'cannot stat' there is normal, not a fault, and you should not create `/etc/sysctl.d/99-userns.conf`. Only on `linux-hardened` does the knob apply, and there the safer fix for Flatpak specifically is `sudo pacman -S bubblewrap-suid` rather than relaxing the sysctl globally. Verify with `podman unshare cat /proc/self/uid_map` and `podman run --rm docker.io/library/alpine echo ok`.

**Verify.** `podman unshare cat /proc/self/uid_map` shows your mapped range, and `podman run --rm docker.io/library/alpine echo ok` prints `ok` as a normal user.

Sources: <https://wiki.archlinux.org/title/Podman> · <https://wiki.archlinux.org/title/Flatpak>

---

## Stop automatic snapshots from filling the disk

`snapper-snapshots-eating-the-disk` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `manjaro`, `omarchy`, `snapper`, `systemd`

**Symptom.** My root filesystem keeps filling up over weeks even though I have not added files. `sudo btrfs filesystem usage /` shows most of the disk in use and `snapper -c root list` shows dozens or hundreds of snapshots going back months.

**Cause.** On plain Arch, snapper's default timeline keeps 10 hourly, 10 daily, 10 monthly and 10 yearly snapshots per config, and the package enables neither `snapper-timeline.timer` nor `snapper-cleanup.timer`, so nothing reaps what accumulates. Each snapshot pins the blocks of every file that has since changed. If `snap-pac` is installed, every package update adds a pre/post pair on top.

On Omarchy 4 the defaults differ and the mechanism is narrower. Omarchy installs `/etc/snapper/configs/root` from `/usr/share/omarchy/default/snapper/root` with `TIMELINE_CREATE="no"`, `NUMBER_CLEANUP="yes"` and `NUMBER_LIMIT="5"`, disables `snapper-timeline.timer`, and enables `snapper-cleanup.timer` and `limine-snapper-sync.service`. `snap-pac` is not installed, and one `number` snapshot is taken per `omarchy update` by `omarchy-snapshot create`. A current install is therefore capped at five root snapshots. The accumulation happens on machines installed under Omarchy's earlier defaults, which did take hourly timeline snapshots. The newer config stopped creating them, but the existing ones carry cleanup algorithm `timeline`, and `number` cleanup does not touch those because the two algorithms are separate. They pile up untouched, pinning extents that nothing on the machine will ever release.

> **Audit corrected this record.** The generic half checks out and the Omarchy half is wrong in a way that makes the fix harmful. Confirmed against the cited Arch wiki Snapper page: the default timeline really is 10 hourly, 10 daily, 10 monthly and 10 yearly, the package really enables neither timer, the retention keys and `TIMELINE_CREATE="no"` are correct, and man snapper confirms `delete number1-number2` range syntax. On Omarchy 4 none of the premise survives. Confirmed on this machine: `/etc/snapper/configs/root` is owned by no package and is Omarchy's template from `/usr/share/omarchy/default/snapper/root`, carrying `TIMELINE_CREATE="no"`, `NUMBER_CLEANUP="yes"` and `NUMBER_LIMIT="5"`. `systemctl is-enabled` reports `snapper-timeline.timer` disabled and `snapper-cleanup.timer` enabled, running hourly, so the cause's claim that the cleanup timer is not enabled automatically is false here. `pacman -Q snap-pac` reports the package absent, so there is no pre/post pair either. One `number` snapshot is taken per update by `/usr/share/omarchy/bin/omarchy-snapshot`, called from `omarchy-update`. The worst defect is the fix instructing `systemctl enable --now snapper-timeline.timer`. Upstream's `install/config/snapper.sh` on quattro explicitly runs `systemctl disable --now snapper-timeline.timer`, so that step restarts the exact mechanism that caused the reported problem and is reverted on the next repair. The retention-key edit is also futile there, because the same script does `install -m 0644 "$template" "$SNAPPER_CONFIG_PATH"` and `/usr/share/omarchy/migrations/1781984677.sh` re-runs it whenever the config is missing or the units drift. The real Omarchy cause and fix were absent: leaked `timeline`-marked snapshots that `number` cleanup cannot reap, drained by `/usr/share/omarchy/migrations/1784809452.sh` in batches of 20 to survive a D-Bus timeout, whose contract is pinned by `test/shell.d/snapper-timeline-leak-test.sh` in the quattro tree. That migration's own comment puts the cost at hundreds of snapshots pinning over 100 GB. The danger also missed the bootloader entirely: `limine-list` on this machine lists each snapshot as a boot entry, and `/usr/lib/systemd/system/snapper-cleanup.service.d/limine-snapper-override.conf` runs `limine-snapper-sync --no-force-save` afterwards, so deletions do resync and leave no dead entry while `limine-snapper-sync.service` is active, which it is here. Both cited URLs resolve and support the generic branch, so nothing was removed. Severity `high` and frequency `common` are left unchanged: on Omarchy the migration now makes this self-healing, but the record also applies to four distros that still ship the generic default, and upstream shipped a migration precisely because real users hit it. NOT exercised: no sudo, so `snapper list`, any delete, any cleanup run and the migration itself were all read rather than run, and I could not enumerate this machine's actual snapshots beyond the two boot entries `limine-list` shows.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Deleting snapshots is permanent and you lose the ability to roll back to those points. Never delete the snapshot you are currently booted into. On Omarchy 4 every snapshot is also a Limine boot entry, listed by `limine-list`, so deleting the `number` snapshots removes the pre-update recovery entries that `omarchy-snapshot restore` offers. `limine-snapper-sync.service` resyncs the entry list after `snapper-cleanup.service`, so a deletion leaves no dead boot entry behind while that service is enabled and active. Delete in batches of about 20, because one large delete can fail on a D-Bus timeout partway through and leave the rest untouched. Do not enable `snapper-timeline.timer` on Omarchy 4 to fix this: it restarts the mechanism that created the problem, and Omarchy disables it again on the next repair. On plain Arch, running a cron daemon alongside the systemd timers produces duplicate snapshots, so enable one mechanism, not both.

**Fix.**

See what you have, and which cleanup algorithm each snapshot carries, because that is what decides whether anything will ever reap it:

```bash
sudo snapper -c root list
sudo snapper -c root --csvout list --columns number,cleanup
sudo btrfs filesystem usage /
```

**Omarchy 4.** Do not enable `snapper-timeline.timer`, and do not edit the retention keys. Omarchy sets `TIMELINE_CREATE="no"` and `NUMBER_LIMIT="5"` deliberately, `install/config/snapper.sh` reinstalls that file from its template, and a migration re-runs that script whenever the config or the units drift. Confirm the config and the units first:

```bash
cat /etc/snapper/configs/root
systemctl is-enabled snapper-cleanup.timer limine-snapper-sync.service
systemctl is-enabled snapper-timeline.timer     # should report disabled
```

If the list is long, those are leaked `timeline` snapshots from an earlier default. `omarchy update` drains them through a migration that deletes only the `timeline` ones:

```bash
omarchy update
```

`omarchy update` refuses to start with less than 10 GiB free on `/`, so if the disk is already that full, drain by hand in batches of about 20. One large delete can die on a D-Bus timeout partway:

```bash
sudo snapper -c root --csvout list --columns number,cleanup |
  awk -F, '$2 == "timeline" { print $1 }' | head -20 |
  xargs sudo snapper -c root delete --sync
```

Repeat until no `timeline` rows remain. Leave the `number` snapshots alone: those are the pre-update recovery points, and `snapper-cleanup.timer` already holds them at five.

**Plain Arch, EndeavourOS, CachyOS, Manjaro.** Delete a range you do not need:

```bash
sudo snapper -c root delete --sync 20-140
```

Then tighten retention in `/etc/snapper/configs/root`:

```
TIMELINE_MIN_AGE="1800"
TIMELINE_LIMIT_HOURLY="5"
TIMELINE_LIMIT_DAILY="7"
TIMELINE_LIMIT_WEEKLY="0"
TIMELINE_LIMIT_MONTHLY="0"
TIMELINE_LIMIT_YEARLY="0"
```

The package enables neither timer, so enable the ones that create and reap snapshots:

```bash
sudo systemctl enable --now snapper-timeline.timer snapper-cleanup.timer
systemctl list-timers 'snapper*'
```

If you do not want timeline snapshots at all, set `TIMELINE_CREATE="no"` in the same file and enable only `snapper-cleanup.timer`.

**Verify.** On Omarchy 4, `sudo snapper -c root --csvout list --columns number,cleanup` shows no `timeline` rows and at most five `number` ones. On plain Arch it shows only the number your policy allows once `snapper-cleanup.timer` has run. In both cases `sudo btrfs filesystem usage /` shows `Used` fallen:

```bash
sudo snapper -c root --csvout list --columns number,cleanup
sudo btrfs filesystem usage /
```

Btrfs frees the extents of a deleted snapshot in the background, so the space appears a little after the delete returns unless you passed `--sync`.

Sources: <https://wiki.archlinux.org/title/Snapper> · <https://wiki.archlinux.org/title/Btrfs> · <https://github.com/omacom/omarchy/blob/quattro/install/config/snapper.sh> · <https://github.com/omacom/omarchy/blob/quattro/test/shell.d/snapper-timeline-leak-test.sh>

---

## Fix VirtualBox "Kernel driver not installed (rc=-1908)" after a kernel update

`virtualbox-kernel-driver-not-installed` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `virtualbox`

**Symptom.** After a system update and reboot, starting any VM in VirtualBox pops:

```
Kernel driver not installed (rc=-1908)
The VirtualBox Linux kernel driver is either not loaded or not set up correctly.
```

**Cause.** The `vboxdrv` kernel module is not loaded for the running kernel: the DKMS module was not (re)built for it, the matching `*-headers` package is missing, or you booted a new kernel while the previous modules were still loaded. VirtualBox on Arch is now DKMS-only — there is no prebuilt `virtualbox-host-modules-arch` package any more — so every kernel update depends on DKMS succeeding.

> **Audit corrected this record.** The failure mode, `vboxreload` (really shipped at `/usr/bin/vboxreload` by the `virtualbox` package), the `vboxnetadp`/`vboxnetflt` modules, the `vboxusers` group and the module-signing note are all correct. The problem is the headline command: `virtualbox-host-modules-arch` no longer exists in the Arch repositories — a search of the current repos returns `virtualbox`, `virtualbox-host-dkms`, `virtualbox-guest-*`, `virtualbox-ext-vnc`, `virtualbox-sdk` and nothing named `*-modules-arch`. `sudo pacman -S virtualbox virtualbox-host-modules-arch` therefore fails with 'target not found', which is a bad first line for a record whose whole point is a missing module.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Mixing `virtualbox-host-modules-arch` (built for the stock `linux` kernel) with a different kernel is exactly what causes this. Don't install both module packages. Rebuilding DKMS modules requires the matching `*-headers` package — installing a new kernel without its headers reproduces the failure on the next boot.

**Fix.**

Install VirtualBox with the DKMS modules and the headers for whichever kernel(s) you boot:

```bash
sudo pacman -S virtualbox virtualbox-host-dkms linux-headers
# add the matching headers for any other kernel you boot:
# linux-lts-headers / linux-zen-headers / linux-cachyos-headers ...
```

Then confirm the build and load it:

```bash
dkms status
sudo modprobe vboxdrv
sudo vboxreload                      # after updating modules under a running set
sudo modprobe vboxnetadp vboxnetflt  # bridged/host-only networking
sudo usermod -aG vboxusers $USER     # USB passthrough; log out/in afterwards
```

The `Required key not available` / `CONFIG_MODULE_SIG_FORCE` note and the 'install headers for every kernel you keep' warning stand as written; the warning about mixing module packages can go, since only the DKMS package remains.

**Verify.** `lsmod | grep vbox` lists `vboxdrv` (and `vboxnetflt`/`vboxnetadp` if you loaded them), and the VM starts. `dkms status` shows the module built for your running kernel.

Sources: <https://wiki.archlinux.org/title/VirtualBox>

---

## Fix xdg-desktop-portal not starting under Hyprland (no file dialogs, no screenshare)

`xdg-desktop-portal-not-starting-hyprland` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `greetd`, `hyprland`, `omarchy`, `wayland`, `xdg-desktop-portal`, `xwayland`

**Symptom.** File-open dialogs never appear, screen sharing offers nothing to share, and `systemctl --user status xdg-desktop-portal-hyprland` shows the service failing or never starting. Sometimes it only breaks when Hyprland is launched from a bare TTY or via greetd.

**Cause.** `xdg-desktop-portal-wlr` and `xdg-desktop-portal-hyprland` require `XDG_CURRENT_DESKTOP` and `WAYLAND_DISPLAY` to be present in the systemd user session and the D-Bus activation environment. If the compositor is started without importing them, the backend has no way to talk to the compositor. Separately, launching from a TTY/greetd that never reaches `graphical-session.target` makes `xdg-desktop-portal.service` refuse to start because of its `Requisite=graphical-session.target`.

> **Audit corrected this record.** The systemd analysis is verified correct: upstream `xdg-desktop-portal.service` really does carry `PartOf=graphical-session.target`, `Requisite=graphical-session.target`, `After=graphical-session.target`, so the empty-assignment drop-in via `systemctl --user edit` is the right technique, and the danger note about not editing `/usr/lib/systemd/user/` is right. What is stale is where the environment import goes: Hyprland 0.55+ deprecated hyprlang and reads `~/.config/hypr/hyprland.lua`, and Omarchy 4 (Quattro) ships `~/.config/hypr/hyprland.lua` + `autostart.lua` and starts the session under uwsm — so `exec-once = ...` lines added to `~/.config/hypr/hyprland.conf` are silently ignored on both. Under uwsm the imports are also unnecessary, because uwsm already populates the systemd/D-Bus activation environment.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not edit `/usr/lib/systemd/user/xdg-desktop-portal.service` directly — the next `xdg-desktop-portal` package update overwrites it and the fix silently disappears. Use `systemctl --user edit` so the drop-in lands in `~/.config/systemd/user/`.

**Fix.**

Diagnose the same way (`systemctl --user show-environment | grep -E 'XDG_CURRENT_DESKTOP|WAYLAND_DISPLAY'`), but fix it in the right place:

- **Preferred (and the Omarchy 4 default): start Hyprland through uwsm** (`uwsm start hyprland-uwsm.desktop`), which exports the session environment to systemd and D-Bus for you — no `exec-once` import lines needed. If you are already on Omarchy 4 and the variables are missing, that is a session bug to report, not something to paper over in the config.
- **If you launch `Hyprland` bare on 0.55+**, put the imports in the Lua config instead of `hyprland.conf` — on Omarchy that is `~/.config/hypr/autostart.lua` (`o.launch_on_start("systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE")`, same for the `dbus-update-activation-environment --systemd ...` line). Only a pre-0.55 Hyprland still takes the `exec-once =` form in `hyprland.conf`.

The `systemctl --user edit xdg-desktop-portal.service` drop-in (`[Unit]` with empty `Requisite=`, `After=`, `PartOf=`) and the `xdg-desktop-portal-gtk` `DISPLAY=:0` drop-in stay exactly as written.

**Verify.** `systemctl --user status xdg-desktop-portal-hyprland` is `active (running)`, and `systemctl --user show-environment` lists both variables. A file dialog from any GTK app now opens and returns the chosen file.

Sources: <https://wiki.archlinux.org/title/XDG_Desktop_Portal>

---

## Fix KVM/libvirt bridged networking breaking when Docker starts

`docker-breaks-kvm-libvirt-bridge` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `kvm`, `libvirt`, `manjaro`, `nftables`

**Symptom.** My VMs on a `br0` bridge had working networking. After installing Docker (or after a reboot where Docker now starts), the VMs get no IP or cannot reach the LAN. Stopping `docker.service` immediately fixes it.

**Cause.** Docker inserts iptables rules that set the FORWARD chain policy to DROP and only permit forwarding on its own interfaces, so traffic across your KVM bridge is dropped.

> **Audit corrected this record.** The core diagnosis (Docker sets the FORWARD policy to DROP and only permits its own interfaces) and the `iptables -I FORWARD -i br0 -o br0 -j ACCEPT` fix are correct, as is the `"iptables": false` warning. Two defects: (1) `IPForward=yes` is obsolete — current systemd.network(5) documents only `IPv4Forwarding=` and `IPv6Forwarding=`; `IPForward=` was removed and pasting it yields an ignored/warned key. (2) Setting `"bridge": "br0"` in `/etc/docker/daemon.json` hands your libvirt bridge to the Docker daemon as its default bridge (Docker then attaches containers to it and manages addressing on it) — that is not a safe 'alternative' for a bridge already carrying VMs and should not be offered as one.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** The blunt workaround `{"iptables": false}` in `/etc/docker/daemon.json` turns off all of Docker's firewall management. Container NAT/outbound networking and port publishing will break, and containers may end up unfiltered. Prefer the FORWARD rule.

**Fix.**

Preferred fix, unchanged:

```bash
sudo iptables -I FORWARD -i br0 -o br0 -j ACCEPT
```

Persist it the Arch way — save the live ruleset and enable the service that restores it:

```bash
sudo iptables-save | sudo tee /etc/iptables/iptables.rules
sudo systemctl enable --now iptables.service
```

(or add the equivalent accept rule to your `/etc/nftables.conf` forward chain and enable `nftables.service`).

Do **not** set `"bridge": "br0"` in `/etc/docker/daemon.json` — that makes Docker adopt and manage your libvirt bridge. If you want Docker off your bridge entirely, give it its own with `"bip"`/a user-defined network instead.

If forwarding is being reset under systemd-networkd, the current option names are `IPv4Forwarding=yes` (and `IPv6Forwarding=yes`) in the `[Network]` section of the relevant `.network` file — `IPForward=` no longer exists. Verify with `sysctl net.ipv4.ip_forward` and `sudo iptables -S FORWARD | head`.

**Verify.** With `docker.service` running, a VM on `br0` gets a DHCP lease and can ping the gateway. `sudo iptables -S FORWARD | head` shows your ACCEPT rule ahead of Docker's DROP.

Sources: <https://wiki.archlinux.org/title/Docker> · <https://wiki.archlinux.org/title/Libvirt>

---

## Fix a scheduled restic/borg backup that skips runs and then fails on a stale lock

`scheduled-backup-skipped-and-repo-locked` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** A nightly backup timer set for 03:00 has not run in days on a laptop — `systemctl list-timers` shows a `NEXT` time but `LAST` is `n/a` or weeks old. When it does eventually run it fails with restic's

```
Fatal: unable to create lock in backend: repository is already locked exclusively by PID 1234 on host by user (UID 0, GID 0)
```

or borg's `Failed to create/acquire the lock`, and every subsequent run fails the same way.

**Cause.** Two compounding problems. The schedule: a realtime `OnCalendar=` timer without `Persistent=true` does not record its last trigger time, so any occurrence that fell while the machine was powered off is dropped instead of caught up. Suspend behaves differently. A realtime timer that elapses during suspend does fire shortly after resume, because systemd arms `CLOCK_REALTIME` for it unless `WakeSystem=true` is set, so a laptop suspended at 03:00 gets a late backup on the next resume while a laptop shut down at 03:00 gets none at all. The lock: when a run is cut short by suspend, shutdown, an OOM kill or an unplugged drive, the repository lock it created is never released, and every later run is refused by a lock whose owning process is long gone. restic counts a lock stale once its creating process is dead on the same host, or once any lock is more than 30 minutes old without a refresh, which is why `restic unlock` clears the usual case and `--remove-all` is needed only for a live process or a recent lock from another host.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, systemd 261.2-1, kernel 7.1.9) and against primary sources. Three findings. First, the cause was wrong about suspend: `man systemd.timer` says `Persistent=` is "useful to catch up on missed runs of the service when the system was powered down", and systemd's own `src/core/timer.c` arms `t->wake_system ? CLOCK_REALTIME_ALARM : CLOCK_REALTIME`, so a realtime timer that elapses during suspend fires shortly after resume without `Persistent=` at all. Only power-off needs the catch-up. Second, the fix omitted `WakeSystem=true`, which is the only setting that makes the timer actually run at 03:00 on the suspended laptop the symptom describes, so the record did not fully answer its own scenario. I added it with the Arch wiki Systemd/Timers caveat that it can fail with "Failed to enter waiting state: Operation not supported". Third, confirmed on this machine that neither tool ships with Omarchy: `pacman -Q restic borg` reports both not found, and `grep -rniE 'restic|borg' /usr/share/omarchy/` matches nothing, while `/usr/share/omarchy/install/omarchy-other.packages` carries `snapper` and `limine-snapper-sync` instead (both installed here, snapper 0.13.1-3 and limine-snapper-sync 1.31.0-1). Both tools are in Arch `extra` (restic 0.19.1-1, borg 1.4.5-1), so the record stays correct for an Omarchy user who installs one, and `applies_to` keeps `omarchy`, but I added the install step and the snapper note and dropped `frequency` from `common` to `occasional`, because the problem needs a third-party tool Omarchy does not ship plus a hand-written system timer. `severity: high` stays: a backup that silently has not run for weeks is exactly that bad. What held, and where: the `pgrep` concurrency guard, `restic unlock` before the backup, `restic check --with-cache --read-data-subset=5G`, `chmod 744` and `chmod 700` are all verbatim from the Arch wiki Restic page, and `--read-data-subset` accepting a size is confirmed in restic's own "Working with repositories" page. `restic unlock` removing only stale locks and `--remove-all` removing all is confirmed in `cmd/restic/cmd_unlock.go` ("remove all locks, even non-stale ones"), and the staleness rule is `internal/repository/lock_file.go` lines 246 to 248: "stale if the timestamp is older than 30 minutes or if it was created on the current machine and the process isn't alive any more". That makes plain `unlock` sufficient for the symptom, which I folded into the fix and the danger to sharpen the gate on `--remove-all`. The symptom's quoted restic error is current: `lock_file.go` line 378 formats exactly "PID %d on %s by %s (UID %d, GID %d)". The danger held and is now backed by borg's own break-lock page, "Please use with care and only when no borg process (on any machine) is trying to access the cache or the repository", and by restic's troubleshooting page confirming an interrupted backup does not damage the repository but may need a manual `unlock`. `ExecCondition=` exiting 1 through 254 not marking the unit failed, and `RequiresMountsFor=` adding `Requires=` and `After=`, are both confirmed in `man systemd.service` and `man systemd.unit` here. Bare `systemd-inhibit` in `ExecStart=` resolves, confirmed in `man systemd.service`: a first argument without slashes is searched in a fixed path including `/usr/bin/`, and `/usr/bin/systemd-inhibit` exists here. Two corrections to the previous audit note rather than to the record: it credited the Arch wiki Restic page with the `Persistent=true` and `RandomizedDelaySec` pattern, but that page's timer is monotonic (`OnBootSec=5min`, `OnUnitActiveSec=15min`), and the pattern comes from Systemd/Timers and `man systemd.timer`. The cited `wiki.archlinux.org/title/Borg_backup` page resolves but contains no mention of locks at all, so it did not support the borg claim it was cited for. I kept it rather than removing it, because it does support the borg install step I added, and added borg's own break-lock page for the lock claim. Not exercised: I have no sudo, so I could not install restic, create a repository, run a backup, break a lock, start a timer, or test `WakeSystem=true` on real firmware. The claim that a root system service can take a block inhibitor is from source reading only: `/usr/share/polkit-1/actions/org.freedesktop.login1.policy` rates `inhibit-block-sleep` and `inhibit-block-shutdown` as `auth_admin_keep`, but systemd's `src/shared/bus-polkit.c` skips the polkit query for a privileged caller ("Don't query PK if client is privileged"), and a root service holds CAP_SYS_ADMIN, so the Arch wiki's note that `systemd-inhibit` "is only available when running in a user session" is misleading for a root system unit. I could not confirm that by running it.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `restic unlock --remove-all` and `borg break-lock` remove locks belonging to processes that may still be running. Borg's own documentation says to use `break-lock` with care and only when no borg process, on any machine, is trying to access the cache or the repository. Doing either while a backup or a prune is genuinely in progress can corrupt the repository. Plain `restic unlock` is the safe form and clears the usual stale lock, so treat `--remove-all` as a last resort and confirm nothing is running on any host that touches the repo first. `restic forget --prune` permanently deletes snapshots: test your retention flags with `restic forget --dry-run` before putting them in a timer. `restic backup /` with a missing or empty exclude file walks `/proc`, `/sys` and `/dev`, so write the exclude list before the first scheduled run. And note that an automated backup necessarily has the repository password available to root in plain text (the `--password-command` script), so protect it with `chmod 700` and remember that anyone with root can read your backups.

**Fix.**

Neither restic nor borg is part of Omarchy. Install the one you want first, after an update so the package databases are current:

```bash
omarchy update
sudo pacman -S --needed restic     # or: sudo pacman -S --needed borg
```

`pacman -S <pkg>` on its own is not blocked by Omarchy's ALPM guard, which aborts only when the pacman command line carries both a sync and a sysupgrade flag. Do not reach for `pacman -Sy restic`, which is a partial upgrade. Omarchy's own packaged snapshot tooling is `snapper` with `limine-snapper-sync`, which takes btrfs snapshots on the same disk and is not a replacement for a backup repository on separate storage.

Make the schedule catch up after downtime:

```ini
# /etc/systemd/system/restic-backup.timer
[Unit]
Description=Timer for full system backups

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=15m
Unit=restic-backup.service

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now restic-backup.timer
systemctl list-timers restic-backup.timer
systemd-analyze calendar "*-*-* 03:00:00"
```

`Persistent=true` stores the last trigger time on disk and runs the job immediately after boot if the scheduled time passed while the machine was powered down. It does not cover suspend and does not need to: a realtime timer that elapses while the machine is suspended fires shortly after resume on its own.

If you want the backup to run at 03:00 on a laptop that is suspended at 03:00, rather than whenever you next open the lid, add `WakeSystem=true` to the `[Timer]` section:

```ini
[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=15m
WakeSystem=true
Unit=restic-backup.service
```

That switches the timer to `CLOCK_REALTIME_ALARM` and resumes the machine. It needs hardware and firmware support, and a timer that cannot get it fails to start with `Failed to enter waiting state: Operation not supported`. It also does not suspend the machine again once the backup finishes.

Stop the run being cut short in the middle, and clear a stale lock before starting. This is what the recommended wrapper script does:

```ini
# /etc/systemd/system/restic-backup.service
[Unit]
Description=Backup system

[Service]
Type=oneshot
ExecStart=systemd-inhibit --what=sleep:shutdown --why="restic backup" /usr/local/bin/restic-backup
```

```bash
#!/bin/bash
# /usr/local/bin/restic-backup
if pgrep -f 'restic backup' > /dev/null; then
  echo 'restic is already running...' 1>&2
  exit 0
fi

set -e
export RESTIC_REPOSITORY='/mnt/restic'
export RESTIC_PASSWORD_COMMAND='/usr/local/bin/get-restic-password'
export RESTIC_CACHE_DIR=/root/.cache/restic
mkdir -p "$RESTIC_CACHE_DIR"

restic unlock
restic backup / --exclude-file=/etc/restic/excludes.txt --tag scheduled
restic check --with-cache --read-data-subset=5G
restic forget --prune --keep-daily 30 --keep-weekly 4 --keep-monthly 6 --keep-yearly 3
```

```bash
sudo chmod 744 /usr/local/bin/restic-backup
sudo chmod 700 /usr/local/bin/get-restic-password
```

`/etc/restic/excludes.txt` has to exist and has to exclude the pseudo filesystems before the first run, or `restic backup /` walks `/proc`, `/sys`, `/dev` and everything mounted under `/mnt`. The Arch wiki's Restic page carries a working list. Adding `--one-file-system` to the `restic backup` line is the alternative, and it keeps the mount point directories themselves in the snapshot.

To clear a stuck lock by hand:

```bash
# restic: clears locks whose process is dead on this host, and any lock over 30 minutes old
restic -r /mnt/restic unlock

# restic: clears live locks too. Only if you are certain nothing is running
restic -r /mnt/restic unlock --remove-all

# borg
borg break-lock /mnt/borgrepo
```

Plain `restic unlock` is enough for the case in the symptom, because a lock left behind by a killed backup on the same machine already counts as stale. Reach for `--remove-all` only when the lock belongs to a process that is still alive, or came from another host less than 30 minutes ago. Check for a run in progress on any machine that shares the repository before breaking a lock:

```bash
pgrep -a -f 'restic|borg'
systemctl is-active restic-backup.service
```

If the destination is an external drive that is not always attached, gate the service on the mount rather than letting it fail. Put it in a drop-in so the unit file above stays intact:

```bash
sudo systemctl edit restic-backup.service
```

```ini
[Unit]
RequiresMountsFor=/mnt/restic

[Service]
ExecCondition=/usr/bin/mountpoint -q /mnt/restic
```

An `ExecCondition=` that exits 1 through 254 skips the remaining commands without marking the unit failed, so a detached drive produces a clean no-op instead of a failed service and an alert.

Use a **system** timer (under `/etc/systemd/system/`) for a whole-system backup. A user timer only exists while your user instance does, unless you run `loginctl enable-linger`.

**Verify.** `systemctl list-timers restic-backup.timer` shows a `LAST` timestamp that advances daily, including after the machine has been powered off across 03:00, and `ls -l /var/lib/systemd/timers/stamp-restic-backup.timer` shows the stamp file that `Persistent=true` maintains, which is the mechanism that makes the catch-up happen. `restic -r /mnt/restic snapshots` lists a new snapshot per day, and `journalctl -u restic-backup.service -n 50` shows clean runs with no `unable to create lock` errors.

Sources: <https://wiki.archlinux.org/title/Restic> · <https://wiki.archlinux.org/title/Systemd/Timers> · <https://borgbackup.readthedocs.io/en/stable/faq.html> · <https://wiki.archlinux.org/title/Borg_backup> · <https://wiki.archlinux.org/title/Systemd/User> · <https://man.archlinux.org/man/systemd.timer.5.en> · <https://raw.githubusercontent.com/systemd/systemd/main/src/core/timer.c> · <https://raw.githubusercontent.com/systemd/systemd/main/src/shared/bus-polkit.c> · <https://raw.githubusercontent.com/restic/restic/master/cmd/restic/cmd_unlock.go> · <https://raw.githubusercontent.com/restic/restic/master/internal/repository/lock_file.go> · <https://restic.readthedocs.io/en/stable/045_working_with_repos.html> · <https://restic.readthedocs.io/en/stable/077_troubleshooting.html> · <https://borgbackup.readthedocs.io/en/stable/usage/lock.html> · <https://archlinux.org/packages/extra/x86_64/restic/> · <https://archlinux.org/packages/extra/x86_64/borg/>

---

## Fix VFIO GPU passthrough failing with "group is not viable"

`vfio-gpu-passthrough-group-not-viable` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `libvirt`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** Starting the VM with a passed-through GPU fails with:

```
vfio: error, group 13 is not viable, please ensure all devices within the iommu_group are bound to their vfio bus driver.
```

Or `/sys/kernel/iommu_groups/` is empty, or `lspci -nnk` still shows `Kernel driver in use: nvidia` / `amdgpu` for the card you meant to pass through.

**Cause.** An IOMMU group is the smallest unit that can be handed to a VM. Every device in the group must be bound to `vfio-pci` — if the GPU's HDMI audio function, a USB controller, or a PCIe root port shares the group and is still on its normal driver, the group is "not viable". An empty `iommu_groups` directory means IOMMU (Intel VT-d / AMD-Vi) is not enabled at all.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, mkinitcpio 41.1-1, limine-mkinitcpio-hook 1.37.1-1, kernel 7.1.9, RTX 3090) and against the cited Arch wiki page fetched as raw wikitext. The generic VFIO content held: the group-listing script is byte-for-byte the wiki's, the `10de:13c2` / `10de:0fbb` pair is the wiki's own example group 13, `intel_iommu=on` for Intel with nothing needed for AMD-Vi is still what the wiki says, `vfio_pci vfio vfio_iommu_type1` with `vfio_virqfd` absent since 6.2 is current, and the root-port and ACS-override warnings match the wiki notes. I confirmed the exact error string in QEMU source at hw/vfio/container-legacy.c line 796, which the wiki does not carry. Three Omarchy 4 claims were wrong. First, `sudo mkinitcpio -P` cannot work here: `/etc/mkinitcpio.d/` is empty (`ls` on this machine, and `pacman -Ql linux` ships no preset), and `/usr/bin/mkinitcpio` line 986 does `[[ -e "${_optpreset[0]}" ]] || die 'No presets found in %s'`, so the command dies and writes no boot image. The rebuild is `limine-mkinitcpio`, which runs `/usr/share/libalpm/scripts/limine-mkinitcpio-install`. Second, the instruction to put `intel_iommu=on` on the `cmdline:` line of `/boot/limine.conf` is wrong on Omarchy: `/usr/lib/limine/limine-common-functions` sets `LIMINE_CONFIG_PATH="${ESP_PATH}/limine.conf"` and the tool regenerates it, and `ENABLE_UKI=yes` in `/etc/limine-entry-tool.d/omarchy-uki.conf` means the command line is embedded in the UKI, so a drop-in under `/etc/limine-entry-tool.d/` with `+=` is the only place it persists. This agrees with the existing corpus record `limine-kernel-parameters-not-applying-omarchy` rather than contradicting it. Third, "make sure modconf is in your HOOKS" points at the wrong file: `/etc/mkinitcpio.conf` is package-stock here and `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` sets `HOOKS=` wholesale, so editing the former has no effect. I also found a new Omarchy-specific trap the record could not have known: mkinitcpio line 1121 concatenates `/etc/mkinitcpio.conf.d/*.conf` in `sort -V` order, and I verified with `sort -zVu` that `vfio.conf` sorts after `nvidia.conf`, so the wiki's requirement that VFIO modules precede an early-KMS driver is violated unless the drop-in is named to sort first, hence `00-vfio.conf`. The danger field's "known-good Limine/GRUB fallback entry" does not exist on Omarchy: `MKINITCPIO_FALLBACK` is commented out in `/etc/limine-entry-tool.conf` and `limine-list` prints only `linux` under `Omarchy` plus `EFI fallback`, which is the Limine binary on the removable-media path, not a separate initramfs. I could NOT exercise any of the binding: `ls /sys/kernel/iommu_groups/ | wc -l` is 0 on this workstation, so IOMMU is off in firmware here, and I have no sudo and ran nothing that touches modules, initramfs or the bootloader. The wiki's own note that nvidia modesetting forces the ids into the initramfs is confirmed as applying here, because `/etc/modprobe.d/nvidia.conf` contains `options nvidia_drm modeset=1` and `/etc/mkinitcpio.conf.d/nvidia.conf` early-loads `nvidia_drm`. The KVM and Libvirt wiki pages were fetched and support none of the record's claims (grep for vfio or iommu returns nothing in Libvirt and only an incidental lsmod paste in KVM), so they are removed in favour of the Limine wiki and the QEMU source.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** This is the record most likely to leave you staring at a black screen. Once `vfio-pci` claims a GPU it is unusable by the host, so binding the only GPU, or the one your monitor is plugged into, means the desktop does not come up after reboot. Set the motherboard to display from the *host* GPU first, and keep a way in.

On Omarchy 4 there is no fallback kernel entry to fall back to. `MKINITCPIO_FALLBACK` is left commented out in `/etc/limine-entry-tool.conf`, so `limine-list` shows one entry per kernel plus `EFI fallback`, which is the Limine binary on the removable-media path and boots the same image with the same command line. The recovery routes that do exist are the `Snapshots` submenu `limine-snapper-sync` writes into the Limine menu, and booting the Arch or Omarchy ISO to `arch-chroot` in, rename `/etc/modprobe.d/vfio.conf` and `/etc/mkinitcpio.conf.d/00-vfio.conf`, then rerun `limine-mkinitcpio` and `limine-update`. Have ssh from another machine as well.

Since kernel 6.0 the framebuffer freezes once VFIO loads and before GPU drivers do, which hides the LUKS passphrase prompt on encrypted systems. If your root is encrypted, add your host GPU driver to the initramfs too, or use the modprobe.d method rather than the initramfs one. The ACS override patch deliberately breaks PCIe isolation and has real security implications.

**Fix.**

First confirm IOMMU is on:

```bash
sudo dmesg | grep -i -e DMAR -e IOMMU | head
ls /sys/kernel/iommu_groups/ | wc -l
```

`kernel.dmesg_restrict = 1` on Omarchy 4, so `dmesg` needs `sudo`.

If the count is 0, enable VT-d or AMD-Vi in firmware, and for Intel add the kernel parameter `intel_iommu=on`. AMD needs no parameter, the kernel enables AMD-Vi automatically when the firmware advertises it. Where that parameter goes depends on the bootloader.

**Omarchy 4 (Limine plus a UKI).** Do not edit `/boot/limine.conf`. `limine-entry-tool` regenerates it on every kernel or limine transaction, and Omarchy boots a Unified Kernel Image (`ENABLE_UKI=yes` in `/etc/limine-entry-tool.d/omarchy-uki.conf`) whose command line is baked into the `.efi` file, so a `limine.conf` edit could not change it even if it survived. Add your own drop-in that sorts after Omarchy's `omarchy-defaults.conf`, and always append with `+=`:

```bash
sudo tee /etc/limine-entry-tool.d/zz-local.conf >/dev/null <<'EOF'
KERNEL_CMDLINE[default]+=" intel_iommu=on"
EOF
sudo limine-mkinitcpio
sudo limine-update
```

A bare `=` there replaces Omarchy's own defaults instead of adding to them.

**Plain Arch with systemd-boot:** the `options` line in `/boot/loader/entries/*.conf`.

**Plain Arch with GRUB:** `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`. Omarchy 4 has no `/etc/default/grub`.

Reboot, then list the groups:

```bash
#!/bin/bash
shopt -s nullglob
for g in $(find /sys/kernel/iommu_groups/* -maxdepth 0 -type d | sort -V); do
    echo "IOMMU Group ${g##*/}:"
    for d in $g/devices/*; do
        echo -e "\t$(lspci -nns ${d##*/})"
    done
done
```

Every non-bridge device in the target group must go to `vfio-pci`. Take the `[vendor:device]` IDs from that output (the wiki's example group 13 is `10de:13c2` for the GPU and `10de:0fbb` for its audio function) and bind them early:

```bash
sudo tee /etc/modprobe.d/vfio.conf >/dev/null <<'EOF'
options vfio-pci ids=10de:13c2,10de:0fbb
softdep drm pre: vfio-pci
EOF
```

If the proprietary NVIDIA driver is installed, use `softdep nvidia pre: vfio-pci` instead of `softdep drm pre: vfio-pci`. Do **not** bind a PCIe root port or bridge that happens to share the group, it has to stay on the host.

Then put the modules in the initramfs. On plain Arch that is the stronger of the two methods. On an Omarchy machine with the NVIDIA driver it is **required**, because Omarchy early-loads `nvidia_drm` with `modeset=1` (`MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` in `/etc/mkinitcpio.conf.d/nvidia.conf`, plus `options nvidia_drm modeset=1` in `/etc/modprobe.d/nvidia.conf`), and the wiki notes that with nvidia modesetting the `vfio-pci` ids must be embedded in the initramfs image rather than passed on the kernel command line.

**Omarchy 4.** The drop-in filename matters. mkinitcpio concatenates `/etc/mkinitcpio.conf.d/*.conf` in `sort -V` order before sourcing them, so a file called `vfio.conf` is read *after* `nvidia.conf` and the VFIO modules would land behind `nvidia_drm` in `MODULES`. The wiki requires every VFIO module to precede an early-modesetting driver, so name the file so it sorts first:

```bash
sudo tee /etc/mkinitcpio.conf.d/00-vfio.conf >/dev/null <<'EOF'
MODULES+=(vfio_pci vfio vfio_iommu_type1)
EOF
sudo limine-mkinitcpio
sudo limine-update
```

`sudo mkinitcpio -P` does **not** work on Omarchy 4. `/etc/mkinitcpio.d/` is empty, so mkinitcpio exits with `No presets found in /etc/mkinitcpio.d` and writes no boot image, leaving you rebooting into the old one. `limine-mkinitcpio` is the rebuild.

`modconf` is already in Omarchy's `HOOKS`, and `modconf` is what copies `/etc/modprobe.d/` into the image. Check it in the drop-in that actually sets `HOOKS`, not in `/etc/mkinitcpio.conf`, whose `HOOKS=` line that drop-in overwrites wholesale:

```bash
grep -o 'modconf' /etc/mkinitcpio.conf.d/omarchy_hooks.conf
```

**Plain Arch.** Add the modules to `MODULES` in `/etc/mkinitcpio.conf` (or a drop-in sorting before any early-KMS drop-in), make sure `modconf` is in `HOOKS`, then rebuild:

```bash
sudo mkinitcpio -P
```

Reboot and verify the binding:

```bash
lspci -nnk -d 10de:13c2
# want: Kernel driver in use: vfio-pci
```

If the group still holds devices you cannot pass (a shared root port), move the card to a different PCIe slot before considering the ACS override patch (`linux-zen` plus `pcie_acs_override=downstream,multifunction`), which weakens device isolation.

**Verify.** `cat /proc/cmdline` shows `intel_iommu=on` (Intel only), `ls /sys/kernel/iommu_groups/ | wc -l` is non-zero, `lspci -nnk` shows `Kernel driver in use: vfio-pci` for every non-bridge device in the target IOMMU group, and the VM starts with the GPU attached.

Sources: <https://wiki.archlinux.org/title/PCI_passthrough_via_OVMF> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/qemu/qemu/blob/master/hw/vfio/container-legacy.c>

---

## Fix the clock being hours off after booting Windows

`clock-wrong-after-dual-boot-windows` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `dual-boot`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** Every time I boot into Windows and come back to Arch/Omarchy, the clock is off by exactly my UTC offset. Fixing it in one OS breaks it in the other. Sometimes HTTPS sites then fail with certificate date errors.

**Cause.** Both systems read the same hardware (RTC) clock but interpret it differently: Linux treats it as UTC, Windows treats it as local time. Each one "corrects" it on boot and they fight. Since systemd 216, if the RTC is set to local time, systemd will never write back to it, which makes the drift worse.

> **Audit corrected this record.** Checked both cited wiki pages as raw wikitext and `man timedatectl` from systemd 261.2-1 on this workstation. The direction and the command are current and exact: the System_time page says configuring Windows for UTC is recommended rather than switching Linux to localtime, and the record's `reg add "HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /d 1 /t REG_DWORD /f` is byte-identical to the wiki's line. The cause's systemd 216 claim is supported word for word: since version 216, when the RTC is configured to local time systemd will never synchronize back to it. The danger holds on both halves, from the source and locally. The wiki gives DST over-correction across multiple operating systems and system time going backwards during the boot sequence for a localtime RTC, and `man timedatectl` here says maintaining the RTC in the local timezone is not fully supported, will create problems with time zone changes and daylight saving adjustments, and to keep the RTC in UTC if at all possible. The danger stays unchanged, as do severity `medium`, frequency `very-common`, the symptom and the verify. The timesyncd drop-in path `/etc/systemd/timesyncd.conf.d/local.conf`, the `[Time]` key, the four `*.arch.pool.ntp.org` hostnames and `timedatectl show-timesync --all` all match the Systemd-timesyncd page, and the three lines the verify field asks for appear verbatim in this machine's live `timedatectl status` output. One Omarchy 4 fact changes the fix. Confirmed on this machine: `/etc/adjtime` does not exist and is owned by no package, and it is absent from upstream's own fresh-install manifest in `omacom/omarchy-iso`. The wiki states that when `/etc/adjtime` is absent systemd already assumes the hardware clock is UTC, so `sudo rm /etc/adjtime` fails with 'No such file or directory' for most readers. Also confirmed here: `timedatectl status` already reports `RTC in local TZ: no` and `NTP service: active`, and the fresh-install manifest carries the `sysinit.target.wants/systemd-timesyncd.service` symlink, so timesyncd is enabled out of the box. The Linux half of the record therefore verifies state rather than fixing it, and a reader who runs it and sees nothing change may wrongly conclude the fix failed. The rewrite says that plainly, switches to `rm -f`, and moves `set-ntp true` ahead of any RTC write so `set-local-rtc 0`, which the man page notes also synchronises the RTC from the system clock, cannot push a still-wrong time into the RTC. Overlap checked against the corpus: `pgp-signature-invalid-wrong-system-clock` reaches the same registry key from the pacman signature symptom and `windows-update-takes-over-uefi-boot-order` is a different problem, firmware boot order rather than time, so this record stays the general clock one and the boundary holds. Not exercised: I have no sudo, so I ran no `timedatectl set-*`, no `hwclock` and no timesyncd restart, and I have no Windows install to test the registry value against.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `timedatectl set-local-rtc 1` is the wrong direction and is explicitly discouraged — it causes over-correction across DST changes and can make the system clock go backwards during boot. Only remove `/etc/adjtime` if you then immediately reset the hardware clock, or the next boot may come up with a wildly wrong time (which breaks TLS and pacman signature checks).

**Fix.**

The remedy is on the Windows side. Omarchy 4 already keeps the RTC in UTC with NTP on, so the Linux commands below mostly confirm that state rather than change it.

Check what Linux currently believes:

```bash
timedatectl status
cat /etc/adjtime 2>/dev/null || echo 'no /etc/adjtime, so systemd assumes the RTC is UTC'
```

On a stock Omarchy 4 install this already reports `RTC in local TZ: no` and `NTP service: active`, and `/etc/adjtime` does not exist. Linux is not the side that is wrong. The clock keeps moving because Windows writes local time into the same RTC.

Make Windows use UTC. In an Administrator Command Prompt on Windows:

```
reg add "HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /d 1 /t REG_DWORD /f
```

Should Windows later offer to update the clock for a DST change, let it. It leaves the RTC in UTC and only corrects the displayed time.

Back on Linux, set the time zone and get NTP synchronised **before** anything writes the RTC, so a correct system clock is what gets pushed out:

```bash
sudo timedatectl set-timezone Europe/London   # your zone
sudo timedatectl set-ntp true
timedatectl status                            # wait for 'System clock synchronized: yes'
```

Only if `timedatectl status` still reports `RTC in local TZ: yes` does the RTC standard need changing:

```bash
sudo timedatectl set-local-rtc 0
```

If `systemd-timesyncd` is not syncing, point it at the Arch pool via `/etc/systemd/timesyncd.conf.d/local.conf`:

```
[Time]
NTP=0.arch.pool.ntp.org 1.arch.pool.ntp.org 2.arch.pool.ntp.org 3.arch.pool.ntp.org
FallbackNTP=0.pool.ntp.org 1.pool.ntp.org
```

then:

```bash
sudo systemctl restart systemd-timesyncd.service
timedatectl show-timesync --all
```

If a stale drift value in `/etc/adjtime` is making the hardware clock jump, clear it and write the corrected time straight back. Use `rm -f`, because on Omarchy 4 the file is normally absent and a bare `rm` just errors:

```bash
sudo rm -f /etc/adjtime
sudo hwclock --systohc --utc
```

If both machines run a time client, disable synchronisation in Windows so the two do not each estimate RTC drift without knowing about the other.

**Verify.** `timedatectl status` shows `RTC in local TZ: no`, `System clock synchronized: yes`, `NTP service: active`. Reboot into Windows and back — the time is still correct.

Sources: <https://wiki.archlinux.org/title/System_time> · <https://wiki.archlinux.org/title/Systemd-timesyncd> · <https://github.com/omacom/omarchy-iso/blob/quattro/manifests/fresh-4-semantic.json>

---

## Fix CUPS not finding a network printer ("Unable to locate printer")

`cups-network-printer-not-found` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `avahi`, `cachyos`, `cups`, `endeavouros`, `manjaro`, `omarchy`, `printing`, `ufw`

**Symptom.** The printer is visible on the network from my phone, but CUPS at http://localhost:631 either does not list it or jobs fail with "Unable to locate printer". `/var/log/cups/error_log` shows lines like:

```
Cannot connect to remote printer ipp://HP079676.local
copy_model: empty PPD file
```

**Cause.** Modern printer discovery uses DNS-SD/mDNS over `.local` names. CUPS only supports Avahi for this — it cannot use systemd-resolved's mDNS for service discovery. Without `avahi-daemon` running and `nss-mdns` wired into `/etc/nsswitch.conf`, the `.local` hostname never resolves.

**Fix.**

```bash
sudo pacman -S cups cups-pdf avahi nss-mdns
sudo systemctl enable --now cups.service avahi-daemon.service
```

Wire mDNS into name resolution. Edit `/etc/nsswitch.conf` so the `hosts:` line reads:

```
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve [!UNAVAIL=return] files myhostname dns
```

Then restart CUPS so it re-scans:

```bash
sudo systemctl restart cups.service
```

If you would rather not rely on discovery, add the printer by its known address:

```bash
lpadmin -p MyPrinter -E -v ipp://192.168.1.50/ipp/print -m everywhere
lpstat -p -d
```

Also: a firewall or an active VPN will block mDNS/printer traffic. Temporarily disconnect the VPN, or allow mDNS through ufw:

```bash
sudo ufw allow 5353/udp
```

**Verify.** `avahi-browse -rt _ipp._tcp` lists the printer, `getent hosts HP079676.local` resolves, and `lpstat -p` shows the queue as idle. A test page prints.

Sources: <https://wiki.archlinux.org/title/CUPS> · <https://wiki.archlinux.org/title/CUPS/Troubleshooting>

---

## Diagnose a systemd unit that failed to start

`debug-failed-systemd-service` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `journald`, `manjaro`, `omarchy`, `systemd`

**Symptom.** Something silently does not work after boot. `systemctl status foo` says `Active: failed (Result: exit-code)` or the boot prints `Failed to start <something>. See 'systemctl status ...' for details.` Or an installer script aborted with `Failed to enable unit: Unit foo.service could not be found.`

**Cause.** Generic — but the diagnostic path is always the same, and most people never get past `systemctl status`, which truncates the log to a handful of lines. The "could not be found" variant is usually a script guessing a unit name that does not match what the package actually ships (e.g. Sunshine ships `app-dev.lizardbyte.app.Sunshine.service`, not `sunshine.service`).

**Fix.**

List everything that is broken first:

```bash
systemctl --failed
systemctl --user --failed
systemctl status <unit>
```

Read the unit's full log for the current boot:

```bash
journalctl -b -u <unit> --no-pager
journalctl --user-unit <unit> --no-pager   # user units
```

Errors only, across the whole boot:

```bash
journalctl -b -p err..alert --no-pager
```

Inspect what the unit actually runs and what it inherits:

```bash
systemctl cat <unit>
systemctl show <unit> -p ExecStart -p Environment
```

If a unit "could not be found", never guess the name — ask the package:

```bash
pacman -Ql <package> | grep -E '\.service$'
systemctl --user list-unit-files | grep -i <name>
```

For a short-lived service that logs nothing under its unit name, find the PID from the status output and query by PID instead — unit attribution is racy for processes that exit immediately:

```bash
journalctl -b _PID=123
```

After fixing, clear the failed state:

```bash
sudo systemctl reset-failed <unit>
sudo systemctl daemon-reload
sudo systemctl restart <unit>
```

Never edit unit files under `/usr/lib/systemd/` — package updates overwrite them. Use `sudo systemctl edit <unit>` instead.

**Verify.** `systemctl --failed` returns `0 loaded units listed`, and `systemctl is-active <unit>` prints `active`.

Sources: <https://wiki.archlinux.org/title/Systemd> · <https://wiki.archlinux.org/title/Systemd/Journal> · <https://github.com/basecamp/omarchy/issues/8582>

---

## Fix /dev/kvm missing ("Could not access KVM kernel module")

`dev-kvm-missing-virtualization-disabled` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `laptop`, `libvirt`, `manjaro`, `omarchy`

**Symptom.** virt-manager greys out KVM or warns the host does not support it, and starting a VM fails with:

```
Could not access KVM kernel module: No such file or directory
failed to initialize kvm: No such file or directory
```

`ls -l /dev/kvm` says `No such file or directory` and `lsmod | grep kvm` prints nothing (or only `kvm`, never `kvm_intel`/`kvm_amd`).

**Cause.** Either the CPU virtualization extensions are switched off in firmware (very common on prebuilt desktops and on laptops), or the `kvm_intel` / `kvm_amd` module never loaded. Arch kernels build both as modules and udev loads the matching one on boot. The trap is that when firmware has the switch off the kernel CLEARS the CPU feature flag, so the flag is missing in both cases. On Intel, `arch/x86/kernel/cpu/feat_ctl.c` prints `VMX (outside TXT) disabled by BIOS` and then calls `clear_cpu_cap(c, X86_FEATURE_VMX)`. On AMD, `arch/x86/kernel/cpu/amd.c` prints `SVM disabled (by BIOS) in MSR_VM_CR` and then calls `clear_cpu_cap(c, X86_FEATURE_SVM)`. An empty `grep -Eo 'vmx|svm' /proc/cpuinfo` therefore does not tell a CPU with no support apart from one whose firmware switch is off, and only the kernel log separates them. Permission on `/dev/kvm` is NOT the cause on Arch or Omarchy: systemd's udev rules create the node mode 0666, so every user can already open it. The group that gates anything is `libvirt`, and only for the libvirt daemon socket, not for `/dev/kvm`.

> **Audit corrected this record.** Confirmed on this machine (omarchy 4.0.2-1, kernel 7.1.9, systemd 261.2-1, libvirt 1:12.6.0-1, qemu-desktop 11.1.0-1, virt-manager 5.1.0-4) that the record's central access claim is false. `ls -l /dev/kvm` returns `crw-rw-rw- 1 root kvm 10, 232`, mode 0666, and `/usr/lib/udev/rules.d/50-udev-default.rules:116` from systemd sets `KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"`. Upstream systemd has `MODE="{{DEV_KVM_MODE}}"` on the same line, so 0666 is Arch's build value and I verified it locally rather than assuming it. The record's `Membership in kvm is what grants access to /dev/kvm` and its previous audit note's `/dev/kvm is root:kvm 0660 on Arch` are both wrong, and they send a reader to edit groups for a problem groups do not cause. The group that matters is `libvirt` for the libvirt read-write socket, per the Arch Libvirt wiki's `Using libvirt group` section, and that page also records that Arch's `/usr/share/polkit-1/rules.d/50-default.rules` already treats `wheel` members as administrators, so a stock Omarchy user gets a password prompt and needs no group change. Second defect, from the kernel sources: the quoted AMD message `kvm: no hardware support` does not exist. I searched `arch/x86/kvm/svm/svm.c`, `arch/x86/kvm/vmx/vmx.c`, `arch/x86/kvm/x86.c` and `virt/kvm/kvm_main.c` at master and found no such string. The real AMD firmware message is `SVM disabled (by BIOS) in MSR_VM_CR` at `arch/x86/kernel/cpu/amd.c:1116`, and `svm.c:500` prints `SVM not supported by CPU %d`. Third, the Intel string the record leads with is real (`vmx.c:2949`) but it sits behind `if (!this_cpu_has(X86_FEATURE_MSR_IA32_FEAT_CTL))`, and `feat_ctl.c` sets that capability for every CPU that has the MSR, so a modern laptop with VT-x off falls through to `vmx.c:2955`, `VMX not fully enabled on CPU %d.  Check kernel logs and/or BIOS`. Fourth and worst for a reader's time, the diagnostic order is misleading: `feat_ctl.c:189` calls `clear_cpu_cap(c, X86_FEATURE_VMX)` and `amd.c:1117` calls `clear_cpu_cap(c, X86_FEATURE_SVM)` when firmware disabled the feature, so an empty `grep -Eo 'vmx|svm' /proc/cpuinfo` is exactly what a firmware-disabled machine looks like, and the record's framing of that step as `establish whether the CPU claims support at all` plus its closing nested-virtualization paragraph tell the reader the opposite. On Omarchy specifically I confirmed that none of this stack is shipped: `omarchy-base.packages` and `omarchy-other.packages` carry only `qemu-user-static-binfmt`, and `grep -rn 'usermod|gpasswd|-aG' /usr/share/omarchy/` returns only an unrelated `input` group removal in `migrations/1787865477.sh`, so Omarchy adds the user to no kvm or libvirt group. What held: the symptom text, the module names, the firmware setting names, the log-out-not-newgrp point, and `libvirtd.service` still working (its unit describes itself as `libvirt legacy monolithic daemon` and carries `Also=virtlogd.socket` and `Also=virtlockd.socket`, confirmed with `systemctl cat`). I rewrote `danger` because the original firmware caution is unsourced and I could not exercise it, while the real hazard in the record's own commands is `-aG` versus `-G`, which `man usermod` on this machine states directly. I kept the firmware caution as a caution. Not exercised: I have no sudo, so I did not run `modprobe`, read `dmesg`, change any group, or touch libvirt, which hosts other work on this machine. I did not test an AMD host or a machine with virtualization disabled in firmware, so the message-to-cause mapping above is read from the kernel sources rather than observed. Severity and frequency left alone: firmware-disabled virtualization is genuinely very common on prebuilt hardware and nothing here is lost data.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Keep the `-a` in `sudo usermod -aG libvirt $USER`. `usermod -G libvirt $USER` REPLACES your supplementary groups instead of adding to them, which drops `wheel` and with it sudo, and recovering needs a root shell or a single-user boot. `man usermod` states it plainly: `-a, --append   Add the user to the supplementary group(s). Use only with the -G option.` On the firmware side, changing a virtualization setting can flip related security options and reorder boot devices on some vendors' setup screens, so note your current boot entry before you save so you can find Limine again.

**Fix.**

Read the kernel's verdict, do not guess from the CPU flags. Both vendors clear the flag when firmware has virtualization switched off, so an empty result below is ambiguous rather than a diagnosis:

```bash
LC_ALL=C.UTF-8 lscpu | grep -i Virtualization   # the line is ABSENT, not "none", once the flag is cleared
grep -Eo 'vmx|svm' /proc/cpuinfo | sort -u      # empty means no support OR firmware off
```

Load the module and read why it refused. `dmesg` needs root on Arch because `kernel.dmesg_restrict = 1`:

```bash
sudo modprobe kvm_intel      # or kvm_amd on AMD
sudo dmesg | grep -i -E 'kvm|vmx|svm|VM_CR|FEAT_CTL'
```

Match the message against the kernel sources:

Intel

- `VMX (outside TXT) disabled by BIOS` at boot, plus `VMX not fully enabled on CPU 0.  Check kernel logs and/or BIOS` from the modprobe. The firmware switch is off. This is the usual case on a laptop, and it is the message to expect on any CPU new enough to have `MSR_IA32_FEAT_CTL`.
- `VMX not enabled (by BIOS) in MSR_IA32_FEAT_CTL on CPU 0`. Same conclusion, but this branch is only reached on CPUs old enough to lack that MSR.
- `VMX not supported by CPU 0` with no `disabled by BIOS` line anywhere in the log. The CPU genuinely has no VT-x.

AMD

- `SVM disabled (by BIOS) in MSR_VM_CR` at boot. The firmware switch is off.
- `SVM not supported by CPU 0` from the modprobe together with that `MSR_VM_CR` boot line. Same cause, reported twice, because the boot path already cleared the flag.
- `SVM not supported by CPU 0` with no `MSR_VM_CR` line. The CPU genuinely has no AMD-V.

If the log says firmware, reboot into UEFI setup and enable it. It is called *Intel VT-x* / *Intel Virtualization Technology* / *SVM Mode* / *AMD-V*, usually under CPU or Advanced settings. On many boards it sits next to the overclocking options, and on some Lenovo and HP laptops there is a separate *VT-d* entry for IOMMU.

Access to the device needs nothing on Arch or Omarchy. `/dev/kvm` is world read-write:

```bash
ls -l /dev/kvm
# crw-rw-rw- 1 root kvm 10, 232 /dev/kvm
```

That mode comes from systemd's own rule, not from anything Omarchy sets:

```
# /usr/lib/udev/rules.d/50-udev-default.rules
KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"
```

So plain `qemu-system-x86_64 -enable-kvm` works with no group change. What group membership buys you is libvirt: members of `libvirt` get password-less access to the libvirt read-write socket, and on Arch anyone in `wheel` already gets a polkit password prompt for the same socket instead. On a stock Omarchy 4 install the user is in `wheel`, so virt-manager works with a prompt and no group edit at all. Add yourself to `libvirt` only if you want the prompt gone:

```bash
sudo usermod -aG libvirt "$USER"     # keep the -a, see the danger note
id -nG | tr ' ' '\n' | grep -E 'kvm|libvirt|wheel'
```

Log out of Hyprland and back in. Group membership is fixed when the session is created, so `newgrp` alone is not enough for the already-running session.

Start the daemon. Socket activation is the lighter path and needs no always-running daemon:

```bash
sudo systemctl enable --now libvirtd.socket virtlogd.socket
```

The monolithic daemon still works and its own unit calls itself `libvirt legacy monolithic daemon`. Enabling it pulls in `virtlogd.socket` and `virtlockd.socket` through `Also=`, so there is no need to enable those separately:

```bash
sudo systemctl enable --now libvirtd.service
```

Omarchy 4 installs none of this stack. `/usr/share/omarchy/install/omarchy-base.packages` carries only `qemu-user-static-binfmt`, and `qemu-desktop`, `libvirt` and `virt-manager` are yours to install. No Omarchy install script adds you to `kvm` or `libvirt` either, so all of the group work above is the user's.

If the boot log carries no `disabled by BIOS` and no `MSR_VM_CR` line, and the only message is `VMX not supported` or `SVM not supported`, then the CPU or the hypervisor above you is the limit. Check whether this machine is itself a guest, and if it is, enable nested virtualization on the outer host.

**Verify.** `ls -l /dev/kvm` shows `crw-rw-rw- 1 root kvm`, `lsmod | grep kvm` lists `kvm_intel` or `kvm_amd` alongside `kvm`, `sudo dmesg | grep -i -E 'vmx|svm'` shows no `disabled by BIOS` and no `MSR_VM_CR` line, and virt-manager opens a `qemu:///system` connection without warning that the host does not support KVM.

Sources: <https://wiki.archlinux.org/title/KVM> · <https://wiki.archlinux.org/title/Libvirt> · <https://wiki.archlinux.org/title/QEMU> · <https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/kvm/vmx/vmx.c> · <https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/kvm/svm/svm.c> · <https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/kernel/cpu/feat_ctl.c> · <https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/kernel/cpu/amd.c> · <https://raw.githubusercontent.com/systemd/systemd/main/rules.d/50-udev-default.rules.in>

---

## Fix Docker refusing --gpus all with "could not select device driver"

`docker-gpu-could-not-select-device-driver` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** Any GPU container fails immediately:

```
docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]].
```

`nvidia-smi` on the host works fine. Sometimes the container starts but then prints `Failed to initialize NVML: Unknown Error`.

**Cause.** Docker has no built-in NVIDIA support. `dockerd` registers its `nvidia` device driver only when one of the NVIDIA Container Toolkit hook binaries is on its PATH: moby's `daemon/devices_nvidia_linux.go` runs `exec.LookPath` for `nvidia-cdi-hook` and for `nvidia-container-runtime-hook`, and when it finds neither it returns no device driver at all, which is the `could not select device driver` message. On Arch those binaries come from `nvidia-container-toolkit`, a separate package that nothing pulls in. Omarchy 4 installs `docker`, `docker-buildx`, `docker-compose` and the NVIDIA driver, but never `nvidia-container-toolkit`, so an Omarchy machine with a working `nvidia-smi` still fails every GPU container. Registering an `nvidia` entry under `runtimes` in `/etc/docker/daemon.json` is a different feature: it is what `--runtime=nvidia` selects, and `--gpus` does not need it.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, kernel 7.1.9-arch1-2, docker 1:29.7.2-1, nvidia-open-dkms 610.57.04-1, RTX 3090) and against four primary sources. Confirmed on this machine: the problem is reproducible by construction, because `/usr/share/omarchy/install/omarchy-base.packages` lists docker, docker-buildx and docker-compose, `/usr/share/omarchy/install/hardware/nvidia.sh` installs nvidia-open-dkms and nvidia-utils when `lspci` sees an NVIDIA card, no Omarchy package list mentions nvidia-container-toolkit, `pacman -Q nvidia-container-toolkit` reports it is not installed, `/etc/cdi` does not exist, no hook binary is on PATH, and `nvidia-smi` works and reports the card. Two defects. First, the cause is wrong: `--gpus` does not require a `runtimes` entry in `/etc/docker/daemon.json`. moby's `daemon/devices_nvidia_linux.go` (read from the moby repo) registers its nvidia device driver purely from an `exec.LookPath` for `nvidia-cdi-hook` or `nvidia-container-runtime-hook` and returns nil when neither exists, and the Arch wiki says the same, that after installing the package you can use `--gpus` OR register the runtime. Second and worse on Omarchy 4: `/etc/docker/daemon.json` already exists and is owned by omarchy-settings 4.0.2-1 (confirmed with `pacman -Qo`), carrying `"dns": ["172.17.0.1"]` and `"bip": "172.17.0.1/16"`, so pasting the record's whole-file runtimes-only JSON deletes exactly the two keys that the corpus record docker-container-dns-blocked-by-ufw and `/usr/share/omarchy/install/config/firewall.sh` depend on, and breaks container DNS everywhere. That is correct generic Arch advice mis-applied to Omarchy 4, because on plain Arch the file does not exist. The `nvidia-ctk` path is safe: the toolkit's `pkg/config/engine/docker/option.go` loadConfig reads and json-decodes the existing daemon.json before AddRuntime merges the key, confirmed from source. Third, the verify is broken on stock Omarchy: `docker info` here prints `Server: permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` and `docker info | grep -i runtime` matches nothing, because `/usr/share/omarchy/install/config/docker.sh` deliberately leaves the user out of the docker group, so every docker command in the fix needs sudo. What held: all package paths are right, confirmed against the Arch package file list, which ships /usr/bin/nvidia-ctk, /usr/bin/nvidia-container-runtime, /usr/bin/nvidia-container-runtime-hook and /etc/nvidia-container-runtime/config.toml. The wiki supports the NVML `--device` workaround verbatim, and all three device nodes exist here. The Arch PKGBUILD and its nvidia-ctk-cdi.hook confirm the CDI file is generated automatically on install and refreshed on nvidia-utils upgrades, which is new information worth having in the fix. All four cited URLs return 200 and support their claims, so nothing is removed, but the BBS thread is a single post with no replies, so the Docker Desktop branch rests on one unanswered report and is now scoped as such. Severity and frequency left alone: the consequence is still a failed container, not a damaged machine, and the new destructive path belongs in `danger`. NOT exercised: I have no sudo, so I could not install the toolkit, restart dockerd, run `nvidia-ctk runtime configure`, or start any container. The merge behaviour of nvidia-ctk is read from its source rather than observed, and the NVML workaround is untested here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** On Omarchy 4 `/etc/docker/daemon.json` is owned by `omarchy-settings` and already sets `dns` and `bip`. Overwriting it with a runtimes-only file removes both and breaks DNS in every container, because Omarchy's ufw rules permit port 53 only to `172.17.0.1`. Use `sudo nvidia-ctk runtime configure --runtime=docker`, which merges into the existing file, or add the key by hand and keep everything else. Being a packaged file it can also arrive as a `.pacnew` during `omarchy update`, so a hand-edited copy has to be merged rather than ignored. Whatever you edit, the file must stay valid JSON. A stray trailing comma makes `docker.service` fail to start with every container down, so validate with `python3 -m json.tool /etc/docker/daemon.json` before restarting. dockerd also refuses to start if the same option is set both in `daemon.json` and as a flag in the unit.

**Fix.**

Install the toolkit and restart the daemon:

```bash
sudo pacman -S --needed nvidia-container-toolkit
sudo systemctl restart docker.service
```

That is the whole fix for `--gpus`. The package ships `/usr/bin/nvidia-container-runtime-hook` and `/usr/bin/nvidia-cdi-hook`, and its ALPM hook `/usr/share/libalpm/hooks/nvidia-ctk-cdi.hook` regenerates `/etc/cdi/nvidia.yaml` on install and on every `nvidia-utils` upgrade.

Omarchy does not put your user in the `docker` group, so run the client under `sudo` unless you opted in through Setup > Security > Sudoless Docker:

```bash
sudo docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
```

If you also want `--runtime=nvidia`, register the runtime with `nvidia-ctk` rather than by hand:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker.service
```

`nvidia-ctk` reads the existing `/etc/docker/daemon.json`, decodes it, and adds only the `runtimes` key, so the rest of the file survives.

**Do not paste a whole-file `daemon.json` over the top on Omarchy 4.** The file is shipped by `omarchy-settings` and already carries the daemon's DNS and bridge settings:

```bash
pacman -Qo /etc/docker/daemon.json     # omarchy-settings
cat /etc/docker/daemon.json
```

```json
{
    "log-driver": "json-file",
    "log-opts": { "max-size": "10m", "max-file": "5" },
    "dns": ["172.17.0.1"],
    "bip": "172.17.0.1/16"
}
```

Dropping `dns` and `bip` breaks name resolution in every container, because Omarchy's ufw rules allow port 53 only to `172.17.0.1`. Add the key and keep the rest:

```json
{
    "log-driver": "json-file",
    "log-opts": { "max-size": "10m", "max-file": "5" },
    "dns": ["172.17.0.1"],
    "bip": "172.17.0.1/16",
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
```

On plain Arch, EndeavourOS or CachyOS the file usually does not exist at all, and the Arch wiki's whole-file form is safe there.

If you get `Failed to initialize NVML: Unknown Error` instead, pass the device nodes explicitly:

```bash
sudo docker run --rm --gpus all \
  --device /dev/nvidiactl:/dev/nvidiactl \
  --device /dev/nvidia-uvm:/dev/nvidia-uvm \
  --device /dev/nvidia0:/dev/nvidia0 \
  nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
```

If you installed Docker Desktop yourself, which Omarchy does not ship, the same error can mean you are talking to Desktop's VM, and that VM has no host GPU:

```bash
docker context ls
docker context use default
```

**Verify.** `sudo docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi` prints your GPU. Do not use `docker info | grep -i runtimes` as the test. It reports the `--runtime=nvidia` registration rather than `--gpus` support, and on a stock Omarchy 4 install `docker info` cannot read the Server section at all, printing `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`, because your user is not in the `docker` group. Under sudo, `sudo docker info | grep -i runtimes` lists `nvidia` only if you ran `nvidia-ctk runtime configure`.

Sources: <https://wiki.archlinux.org/title/Docker> · <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html> · <https://bbs.archlinux.org/viewtopic.php?id=300693> · <https://archlinux.org/packages/extra/x86_64/nvidia-container-toolkit/files/> · <https://archlinux.org/packages/extra/x86_64/nvidia-container-toolkit/json/> · <https://github.com/moby/moby/blob/master/daemon/devices_nvidia_linux.go> · <https://github.com/NVIDIA/nvidia-container-toolkit/blob/main/pkg/config/engine/docker/option.go> · <https://github.com/NVIDIA/nvidia-container-toolkit/blob/main/pkg/config/engine/docker/docker.go> · <https://gitlab.archlinux.org/archlinux/packaging/packages/nvidia-container-toolkit/-/raw/main/PKGBUILD> · <https://gitlab.archlinux.org/archlinux/packaging/packages/nvidia-container-toolkit/-/raw/main/nvidia-ctk-cdi.hook>

---

## Grant a Flatpak app access to files it says do not exist

`flatpak-app-cannot-access-files` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `flatpak`, `manjaro`, `omarchy`

**Symptom.** Flatpak Firefox shows a "File not found" page when I open a local HTML file. Other Flatpak apps show empty folders or refuse to save into ~/Documents even though the files are clearly there.

**Cause.** The Flatpak sandbox only exposes the paths listed in the app's manifest plus any user overrides. Anything else simply is not visible inside the sandbox, so the app reports the file as missing rather than as a permission error.

> **Audit corrected this record.** Every command and identifier in this record checks out against current upstream documentation, so only the danger needed work. Confirmed from https://github.com/flatpak/flatpak/blob/main/doc/flatpak-override.xml that FILESYSTEM accepts `home`, `xdg-download`, an absolute path such as `/mnt/data` and a homedir-relative path like `~/dir`, that `:ro` is a valid suffix, and that `--reset` and `--show` are real options, so the fix and the verify line are correct current syntax. Confirmed `--show-permissions` from https://github.com/flatpak/flatpak/blob/main/doc/flatpak-info.xml. The Flathub app id `com.github.tchx84.Flatseal` still resolves to Flatseal today, and `flatpak install flathub ...` works without adding a remote first because Arch's flatpak 1.18.2-1 ships `usr/share/flatpak/remotes.d/flathub.flatpakrepo` and the Arch wiki says installation adds the Flathub repository system-wide. The cited Arch wiki Flatpak page supports the symptom and the cause almost word for word: it states that Flatpak Firefox shows a File not found error page for a local HTML file, and it describes the `~/.mozilla` profile trap. The danger was directionally right but vague where a specific consequence exists, so it is rewritten to name what `--filesystem=home` actually exposes. I read https://github.com/flatpak/flatpak/blob/main/common/flatpak-exports.c and the only never-export list is `dont_export_in[]` (`/.flatpak-info`, `/app`, `/dev`, `/etc`, `/proc`, `/run/flatpak`, `/run/host`, `/usr`), none of which is under `$HOME`, and the only home path Flatpak hides under a home grant is `~/.var/app`, which it tmpfs masks deliberately. So `~/.ssh` and `~/.gnupg` are exposed read-write and that is worth saying. Omarchy 4 note, confirmed on this workstation: flatpak is NOT installed and appears in no file under /usr/share/omarchy/install/*.packages. It is pulled in on demand by `omarchy-pkg-add flatpak` inside /usr/share/omarchy/bin/omarchy-install-gaming-geforce-now, and /usr/share/omarchy/default/omarchy/omarchy-menu.jsonc gates two menu entries on `flatpak info com.nvidia.geforcenow`. So Omarchy anticipates flatpak without shipping it, and keeping `omarchy` in applies_to is right: a user who hits this symptom on Omarchy necessarily installed flatpak already, so no install step is needed in the fix. What I could NOT exercise: with flatpak absent I ran no `flatpak` command at all, so the override, the Firefox profile behaviour and the Flatseal install rest on documentation and source reading, not on this machine. I deliberately left one documented option out of the record. The Arch wiki's first remedy is to exclude the host profile, which would be `flatpak override --user --filesystem=home --nofilesystem=~/.mozilla org.mozilla.firefox`, and flatpak-override.xml's own wording about `--nofilesystem` undoing a previous identical `--filesystem` and not preventing access to a more narrowly-scoped one is ambiguous about whether a narrow exclusion masks a broad grant in the same layer. Rather than ship a command I cannot run, the rewritten danger states the approach and recommends the narrow grant, which is unambiguous.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Granting `--filesystem=home` to Flatpak Firefox makes it find and load your host `~/.mozilla` profile instead of the sandboxed one, so your tabs and history appear to vanish. The Arch wiki gives the sandboxed profile as `~/.var/app/org.mozilla.firefox/cache/mozilla/` and two ways out: change the permission so the host profile is excluded, or copy the sandboxed profile to `~/.mozilla` first.

`--filesystem=home` is also a real security loosening and not only a Firefox annoyance. It is read-write access to the whole of `$HOME`, including `~/.ssh`, `~/.gnupg`, `~/.bashrc` and `~/.config`, so an app that is compromised or malicious can read private keys and gain persistence by writing to a shell startup file. Flatpak masks only `~/.var/app` (other apps' data) and `/.flatpak-info` under a home grant, nothing else. Grant the narrowest path that works, and add the `:ro` suffix when the app only needs to read:

```bash
flatpak override --user --filesystem=~/Documents:ro org.mozilla.firefox
```

**Fix.**

Inspect what the app currently has, then grant just the directory you need:

```bash
flatpak info --show-permissions org.mozilla.firefox
flatpak override --user --filesystem=~/Documents org.mozilla.firefox
```

Other useful values: `--filesystem=home`, `--filesystem=/mnt/data`, `--filesystem=xdg-download`, and a `:ro` suffix for read-only. To take a permission away: `--nofilesystem=home`. To start over:

```bash
flatpak override --user --reset org.mozilla.firefox
```

For a GUI, install Flatseal:

```bash
flatpak install flathub com.github.tchx84.Flatseal
```

**Verify.** `flatpak override --user --show org.mozilla.firefox` lists the new filesystem entry, and the app can now open/save in that directory.

Sources: <https://wiki.archlinux.org/title/Flatpak> · <https://docs.flatpak.org/en/latest/sandbox-permissions.html> · <https://github.com/flatpak/flatpak/blob/main/doc/flatpak-override.xml> · <https://github.com/flatpak/flatpak/blob/main/doc/flatpak-info.xml> · <https://github.com/flatpak/flatpak/blob/main/common/flatpak-exports.c> · <https://flathub.org/api/v2/appstream/com.github.tchx84.Flatseal> · <https://archlinux.org/packages/extra/x86_64/flatpak/>

---

## Force a Flatpak app off XWayland so it stops looking blurry

`flatpak-app-stuck-on-xwayland-blurry` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `flatpak`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Flatpak Electron/Chromium apps (Spotify, Signal, Obsidian, VS Code, Slack) look soft and fuzzy next to native apps on a fractionally scaled monitor, and text edges look smeared. `hyprctl clients` shows `xwayland: 1` for those windows while everything else is 0. If I set `ELECTRON_OZONE_PLATFORM_HINT=auto` the app instead refuses to start with `Failed to connect to Wayland display: No such file or directory`.

**Cause.** On a fractionally scaled output, an app running through XWayland is rendered at 1x and upscaled as a bitmap, which is the blur. The reason these apps land on XWayland is almost never a missing socket — current Flathub manifests for Spotify, Signal, Obsidian, VS Code and Chrome all grant --socket=wayland — it is that Electron/Chromium still default to the X11 ozone backend unless told otherwise, and --socket=fallback-x11 then hands them an X11 socket to fall back onto. The 'Failed to connect to Wayland display' case only applies to the minority of manifests that genuinely grant x11/fallback-x11 only; there, the hint must be paired with a socket grant.

> **Audit corrected this record.** Symptom and blur mechanism (XWayland rendered at 1x then bitmap-scaled) are real, and the fix works, but the stated cause is factually wrong for exactly the apps named. I pulled the live Flathub manifests: com.spotify.Client, com.visualstudio.code, com.google.Chrome, org.signal.Signal and md.obsidian.Obsidian all already declare --socket=wayland (Chrome declares both x11 and wayland; the others wayland + fallback-x11). So the Wayland socket IS present in the sandbox, and the claimed 'Failed to connect to Wayland display' failure from setting the Ozone hint alone will not happen on these apps. The operative fix is the Ozone hint, not the socket grant. Two smaller gaps: the desktop-entry copy path is only right for system-wide installs (a --user install exports to ~/.local/share/flatpak/exports/share/applications), and --nosocket=fallback-x11 will break apps whose Wayland backend is flaky with no way back. flatpak override --show / --reset / info --show-permissions are all valid.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Revoking `x11`/`fallback-x11` is the step that bites: apps with incomplete Wayland support lose global hotkeys, tray icons, or screen sharing, and some (older Electron builds) will not start at all. Add `--nosocket=x11` only after the app is verified working on Wayland, and be ready to `flatpak override --user --reset <app>`.

**Fix.**

Check what the app actually holds before changing anything:

```bash
flatpak info --show-permissions com.spotify.Client
```

If `--socket=wayland` is already listed (it is for Spotify, Signal, Obsidian, VS Code and Chrome today), the only change needed is the backend hint:

```bash
flatpak override --user --env=ELECTRON_OZONE_PLATFORM_HINT=auto com.spotify.Client
```

Only if the wayland socket is genuinely absent from `--show-permissions`, add it too:

```bash
flatpak override --user --socket=wayland <app-id>
```

For Chromium-based Flatpaks that ignore the Electron variable, pass the Ozone flags:

```bash
flatpak run com.google.Chrome --ozone-platform-hint=auto --enable-features=WaylandWindowDecorations
```

To make the flags stick for the launcher, copy the exported desktop entry — from `/var/lib/flatpak/exports/share/applications/` for a system install, or `~/.local/share/flatpak/exports/share/applications/` for a `--user` install — into `~/.local/share/applications/`, append the flags to `Exec=`, then `update-desktop-database ~/.local/share/applications`.

Verify with `hyprctl clients | grep -A2 xwayland` (want `xwayland: 0`). Only revoke X11 (`flatpak override --user --nosocket=x11 --nosocket=fallback-x11 <app-id>`) once the app is confirmed working natively, and keep `flatpak override --user --reset <app-id>` in mind as the undo.

**Verify.** Restart the app, then `hyprctl clients | grep -A15 'class: <app>'` shows `xwayland: 0`, and the window is crisp at your fractional scale.

Sources: <https://docs.flatpak.org/en/latest/sandbox-permissions.html> · <https://wiki.archlinux.org/title/Flatpak> · <https://wiki.archlinux.org/title/HiDPI> · <https://gist.github.com/unfuug/ce34d07b4223939e89ab25a48af24d5e>

---

## Fix "network 'default' is not active" when starting a VM

`libvirt-default-network-not-active` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `kvm`, `libvirt`, `manjaro`, `omarchy`, `qemu`, `ufw`

**Symptom.** Starting a VM in virt-manager fails with:

```
Error starting domain: Requested operation is not valid: network 'default' is not active
```

It worked before I rebooted.

**Cause.** libvirt's `default` NAT network is not started, and/or not marked to autostart, so it goes away on every boot. It also silently fails to start if `dnsmasq` is not installed, since the default network depends on it for DHCP/DNS.

> **Audit corrected this record.** The problem and the main commands are right (`virsh net-start default` / `net-autostart default`, dnsmasq being required for the default NAT network, and the ufw `route allow ... on virbr0` rules). The recreate path is wrong: `/usr/share/libvirt/networks/default.xml` does not exist in Arch's libvirt package — the shipped template is `/etc/libvirt/qemu/networks/default.xml` (verified against the package file list, which contains no `/usr/share/libvirt/networks` at all). Pasted as written, `virsh net-define` fails with 'failed to open file'.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

```bash
sudo pacman -S dnsmasq
sudo virsh net-list --all
sudo virsh net-start default
sudo virsh net-autostart default
```

If `default` is not listed at all, define it from the template Arch actually ships:

```bash
sudo virsh net-define /etc/libvirt/qemu/networks/default.xml
sudo virsh net-start default
sudo virsh net-autostart default
```

(The ufw rules for `virbr0` and the verify steps are correct as written.)

**Verify.** `sudo virsh net-list --all` shows `default  active  yes  yes`, `ip a show virbr0` shows the bridge with 192.168.122.1, and the VM starts and gets an IP.

Sources: <https://wiki.archlinux.org/title/Libvirt>

---

## Fix apps failing with "org.freedesktop.secrets was not provided by any .service files"

`secret-service-not-available-keyring` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `flatpak`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Anything that wants the system keyring fails. `docker login` prints:

```
Error saving credentials: error storing credentials - err: exit status 1, out: `The name org.freedesktop.secrets was not provided by any .service files`
```

Sometimes instead: `Cannot autolaunch D-Bus without X11 $DISPLAY`. `git push` over HTTPS re-asks for the password every time, `secret-tool store --label=test foo bar` hangs or errors, and Flatpak password managers cannot save anything.

**Cause.** `org.freedesktop.secrets` is provided by `gnome-keyring-daemon`'s secrets component. On a bare Wayland compositor there is no desktop environment starting it with the right components, and the session D-Bus may not know about the graphical environment at all, so it cannot even show an unlock prompt. Flatpak apps additionally need the Secret *portal* routed to gnome-keyring, which is only wired up for GNOME by default.

> **Audit corrected this record.** Cause and most of the fix are right, and the Omarchy-specific detail is verified precisely: install/login/sddm.sh really does `sed -i '/-auth.*pam_gnome_keyring\.so/d'` and the same for `-password` on /etc/pam.d/sddm, with a comment about the passwordless Default_keyring — and the /etc/pam.d/login block quoted for TTY logins matches the Hyprland wiki's own snippet. gnome-keyring ships usr/share/xdg-desktop-portal/portals/gnome-keyring.portal, so routing org.freedesktop.impl.portal.Secret=gnome-keyring in ~/.config/xdg-desktop-portal/hyprland-portals.conf is valid, and /usr/lib/git-core/git-credential-libsecret is genuinely shipped by Arch's git. The defect is the docker login section: it hands the reader `"credsStore": "secretservice"` while only vaguely saying to 'install a helper', and there is no docker-credential-secretservice in the official repos (I checked — it exists only in the AUR, alongside docker-credential-helpers and docker-credential-pass). Setting credsStore without that binary reproduces the exact error in the symptom. Also worth using the shipped gnome-keyring-daemon.service instead of only the hand-run daemon.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never delete files under `~/.local/share/keyrings/` to "start clean" — every stored secret is in those files and is unrecoverable without them. A passwordless keyring stores its contents unencrypted on disk; that is a deliberate Omarchy trade-off for autologin, but do not add a passwordless keyring to a machine where the disk is not encrypted. Adding `pam_gnome_keyring.so` to a PAM file with a typo can lock you out of logins — edit it from a root shell you already have open.

**Fix.**

Install the pieces and start the secrets component as documented (`gnome-keyring libsecret seahorse`, `dbus-update-activation-environment --systemd --all`, then `gnome-keyring-daemon --start --components=secrets` in your session startup — or simply `systemctl --user enable --now gnome-keyring-daemon.service`, which the package ships). Verify with `busctl --user list | grep secrets` and a `secret-tool store` / `lookup` round-trip. Git over HTTPS via `/usr/lib/git-core/git-credential-libsecret` is unchanged.

For **docker login**, the credential helper is not in the official repos — install it from the AUR before setting credsStore, otherwise you get the same 'error storing credentials' failure:

```bash
yay -S docker-credential-secretservice   # or docker-credential-pass for a GPG/pass-backed store
```

```json
{
  "credsStore": "secretservice"
}
```

Confirm the binary is on PATH first (`command -v docker-credential-secretservice`). If you would rather not install a helper at all, delete any `credsStore` line from `~/.docker/config.json` and accept the base64 plain-file store.

The Flatpak Secret-portal routing, the Omarchy keyring inspection (`ls -la ~/.local/share/keyrings/`, `cat ~/.local/share/keyrings/default`) and the /etc/pam.d/login lines for TTY logins all stand as written.

**Verify.** `busctl --user list | grep secrets` shows `org.freedesktop.secrets`, `secret-tool` stores and looks up a value, and `docker login` / `git push` stop re-prompting. `seahorse` opens and lists the keyring.

Sources: <https://wiki.archlinux.org/title/GNOME/Keyring> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://wiki.hypr.land/Useful-Utilities/Systemd-start/> · <https://raw.githubusercontent.com/basecamp/omarchy/master/install/login/sddm.sh>

---

## Fix CUPS "client-error-document-format-not-supported" / "Filter failed"

`cups-document-format-not-supported` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `cups`, `endeavouros`, `manjaro`, `omarchy`, `printing`

**Symptom.** The printer is added and shows as Idle, but every job instantly errors with:

```
Print-Job client-error-document-format-not-supported
```

or the queue stops with "Filter failed" and the job disappears.

**Cause.** CUPS has deprecated classic PPD drivers in favour of IPP Everywhere / driverless printing, which sends PDF to the printer. When the printer needs a conversion step, that work is done by the cups-filters chain (`cups-filters`, and on current Arch `libcupsfilters`/`libppd`) backed by `ghostscript`/`gsfonts`. If those are missing, or a legacy PPD was selected for a printer that has no matching filter, CUPS reports the job as an unsupported document format or stops the queue with 'Filter failed'. (`cups-pdf` is unrelated — it only adds a virtual PDF printer.)

> **Audit corrected this record.** The fix is broadly right (install the filter chain, raise LogLevel, re-enable the queue, re-add as driverless `-m everywhere`; `cups-filters`, `ghostscript`, `gsfonts`, `foomatic-db*` all exist in extra) and the LogLevel warning is a good catch. The cause is wrong on one point that changes what a reader installs: `cups-pdf` is not part of the print pipeline at all — it is a backend that adds a virtual 'PDF' printer writing files to `~/PDF`. Missing `cups-pdf` cannot cause `client-error-document-format-not-supported` or 'Filter failed' on a real printer. The conversion chain is `cups-filters` (plus `libcupsfilters`/`libppd` on current Arch) with `ghostscript`/`gsfonts` behind it.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Remember to set `LogLevel` back to `warn` in `/etc/cups/cupsd.conf` afterwards — debug logging fills `/var/log/cups/` quickly on a busy machine.

**Fix.**

Install the actual filter chain:

```bash
sudo pacman -S cups cups-filters ghostscript gsfonts
sudo systemctl restart cups.service
```

(`cups-pdf` is optional and only gives you a virtual PDF printer — install it if you want that, not to fix this error.) For non-IPP-Everywhere printers needing a legacy PPD, add `foomatic-db foomatic-db-engine foomatic-db-nonfree` as written.

The rest is correct as written: `LogLevel debug` in `/etc/cups/cupsd.conf` + `tail -f /var/log/cups/error_log` to read the real failure (then set it back to `warn`), `cupsenable`/`cupsaccept` to restart the queue, and `lpadmin -x` / `lpadmin -p ... -m everywhere` to re-add it driverless. Run the `lpadmin`/`cupsenable`/`cupsaccept` commands with administrative rights.

**Verify.** `lp -d MyPrinter /usr/share/cups/data/testprint` produces a page, and `lpstat -W completed -o` shows the job as completed rather than held.

Sources: <https://wiki.archlinux.org/title/CUPS> · <https://wiki.archlinux.org/title/CUPS/Troubleshooting>

---

## Make printers appear in a Flatpak app's print dialog

`flatpak-app-cannot-see-cups-printers` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `flatpak`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** The print dialog inside Flatpak LibreOffice / GIMP / Chrome / Inkscape shows "No printers found", or only offers "Print to File", while `lpstat -p -d` on the host lists the printer as idle and printing from a native app works fine.

**Cause.** CUPS is reached over the Unix socket `/run/cups/cups.sock`, which is not mounted inside the Flatpak sandbox unless the app holds the `cups` socket permission. With that permission Flatpak bind-mounts the host socket into the sandbox at `/var/run/cups/cups.sock`, the same file on Arch because `/var/run` is a symlink to `/run`. Apps that do not go through the Print portal see no CUPS server at all and report zero printers, and manifests vary in whether they request the permission. The permission only ever forwards a LOCAL socket. Flatpak looks at `$CUPS_SERVER`, then `~/.cups/client.conf`, then `/etc/cups/client.conf` on the host, but it accepts the value only when it is a filesystem path with no colon in it, so a network `ServerName host:631` is ignored and it falls back to the local socket.

> **Audit corrected this record.** The fix contains a command that cannot work, so this is corrected. `flatpak override --user --filesystem=/etc/cups:ro` is dead: `dont_export_in[]` in https://github.com/flatpak/flatpak/blob/main/common/flatpak-exports.c lists `/etc` among the paths Flatpak refuses to export, and any path with that prefix fails with `Path "/etc" is reserved by Flatpak`. https://github.com/flatpak/flatpak/blob/main/common/flatpak-context.c then routes that failure through `log_cannot_export_error`, which logs `Not sharing "..." with sandbox: ...` at message level and clears the error, so the app still launches and the reader believes a permission was granted that never existed. That is the worst shape of wrong advice and it is why this record could not stay `ok`. https://github.com/flatpak/flatpak/blob/main/common/flatpak-run-cups.c shows the second half of the same defect: `--socket=cups` resolves the server from `$CUPS_SERVER`, then `~/.cups/client.conf`, then `/etc/cups/client.conf` on the HOST, outside the sandbox, so in-sandbox visibility of the file was never the mechanism, and `flatpak_run_cups_check_server_is_socket` accepts the value only if it starts with `/` and contains no colon. A carried TODO comment says network CUPS servers are not supported and it falls back to `/var/run/cups/cups.sock`. So the record's remote-CUPS paragraph was wrong about the mechanism and wrong about the outcome, and it is replaced with the `lpadmin` route, whose flags and the `ipp://hostname:631/printers/queue_name` URI form both come from https://wiki.archlinux.org/title/CUPS. What held, and what I confirmed on this workstation (omarchy 4.0.2-1, kernel 7.1.9): `cups 2:2.4.19-1` is installed and listed in /usr/share/omarchy/install/omarchy-base.packages alongside cups-filters, cups-pk-helper and system-config-printer. `cups.service` and `cups.socket` are both enabled and active, and `cups.socket` listens on `/run/cups/cups.sock`, which exists with mode `srw-rw-rw-`, so the cause's socket path is right. `/var/run` is a symlink to `../run`, so Flatpak's sandbox target `/var/run/cups/cups.sock` is the same file. The portal claim holds and I confirmed it two ways. On this machine gtk.portal lists `org.freedesktop.impl.portal.Print` in its Interfaces and hyprland.portal does not, and https://wiki.archlinux.org/title/XDG_Desktop_Portal's backend table gives Print as yes for xdg-desktop-portal-gtk and no for both xdg-desktop-portal-hyprland and xdg-desktop-portal-wlr, the latter being the half I could not check locally because wlr is not installed. `cups` is a real socket name and both `--share` and `--env` are real override options per https://github.com/flatpak/flatpak/blob/main/doc/flatpak-override.xml, and `flatpak info --show-permissions` in the verify line is valid, so verify is left alone. The Omarchy 4 branch of the fix is new and is a real correction rather than a restyle: xdg-desktop-portal-gtk 1.15.3-1 is in omarchy-base.packages line 142, so it is always installed and the old `sudo pacman -S` step was a no-op that sent the reader down a dead end, and `hyprland-portals.conf` already names gtk as the fallback with `default=hyprland;gtk`, which is the mechanism documented on the Arch wiki portal page. All three portal user units are active here and both unit names in the record are correct, with xdg-desktop-portal-gtk.service being `static` and D-Bus activated. The danger is rewritten because it was pointed at the wrong thing. `--socket=cups` is listed under Standard permissions on https://docs.flatpak.org/en/latest/sandbox-permissions.html, which says those can be freely used, and the socket is world writable anyway, so calling it unfiltered access overstates it. The genuine hazard is the app-less global form the fix offers as a convenience, and the danger now leads with that. I did not assert what cupsd's default policy permits, because `/etc/cups/cupsd.conf` is mode `-rw-r-----` root:cups and I have no sudo, so I could not read it. On the cited issue: I read https://github.com/flatpak/xdg-desktop-portal/issues/341 in full, body and all three comments. It is still open, dated 2019 against flatpak 1.4.1 on Linux Mint 18.3, and it supports the SYMPTOM (LibreOffice, Scribus and GIMP seeing no CUPS printers) and the cause's point that non-portal apps enumerate printers their own way, which is exactly what hadess says in the thread. It never mentions `--socket=cups` and supports no part of the fix, so it is weak but not false and I left it in place rather than removing it. One comment there notes the reporter's remote printers had to be added locally, which happens to support the replacement advice. Omarchy 4 framing, confirmed here: flatpak is NOT installed and is in none of /usr/share/omarchy/install/*.packages. It is pulled in only by `omarchy-pkg-add flatpak` inside omarchy-install-gaming-geforce-now. Keeping `omarchy` in applies_to is still right, since anyone hitting this symptom installed flatpak themselves, but `frequency: common` is generous for the Omarchy slice of the audience, which needs flatpak plus a configured printer plus a non-portal app. I left it alone because applies_to also covers Arch, EndeavourOS, CachyOS and Manjaro, where it is fair. What I could NOT exercise: with no flatpak binary present I ran no flatpak command, so every override claim rests on the man page source and the C source rather than on this machine, and I could not reproduce the printing failure because `lpstat -p -d` reports no destinations here. I also left `--env=CUPS_SERVER=host:631` plus `--share=network` out of the fix, even though both options are documented and the Arch wiki documents CUPS_SERVER, because I could not test whether in-sandbox libcups picks it up and I was not going to replace one untested command with another.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Keep the override scoped to one app. `flatpak override --user --socket=cups` with no app id applies to every Flatpak app on the system, including ones you install months later, and there is nothing in the app's own listing to show where the permission came from.

`--socket=cups` itself is a modest grant rather than a hole. The local socket is already world writable on a stock install (`srw-rw-rw- /run/cups/cups.sock`), so the sandbox gets the same reach any ordinary host process already has, which is enumerating queues and submitting jobs, and upstream lists `cups` among the standard freely-usable permissions. The real exposure is that a sandboxed app can now send documents to a printer and read queue and job metadata. Administrative changes to cupsd are still subject to the authentication rules in `/etc/cups/cupsd.conf`.

Do not reach for `--filesystem=host-etc` or `--filesystem=home` to work around a printing problem. Both hand over far more than printing needs, and neither fixes this.

**Fix.**

Grant CUPS access to the specific app:

```bash
flatpak override --user --socket=cups org.libreoffice.LibreOffice
```

Omitting the app id applies the override to every Flatpak app you have now and every one you install later, so prefer the per-app form above:

```bash
flatpak override --user --socket=cups
```

Check that a portal backend implementing the Print portal is present and running. `xdg-desktop-portal-gtk` implements it, `xdg-desktop-portal-hyprland` and `xdg-desktop-portal-wlr` do not.

On Omarchy 4 it is already installed. `xdg-desktop-portal-gtk` is listed in `/usr/share/omarchy/install/omarchy-base.packages`, and `/usr/share/xdg-desktop-portal/hyprland-portals.conf` already names it as the fallback backend with `default=hyprland;gtk`, so check it is running rather than installing it:

```bash
systemctl --user is-active xdg-desktop-portal.service xdg-desktop-portal-gtk.service
systemctl --user restart xdg-desktop-portal.service xdg-desktop-portal-gtk.service
```

On plain Arch with Hyprland or another wlroots compositor it may be missing, so install it first:

```bash
sudo pacman -S --needed xdg-desktop-portal-gtk
systemctl --user restart xdg-desktop-portal.service xdg-desktop-portal-gtk.service
```

Confirm the host side is actually serving printers before blaming the sandbox:

```bash
systemctl status cups.service
lpstat -p -d
```

If your printers live on a remote CUPS server, `--socket=cups` will not reach them, because it forwards a local socket only and ignores a network `ServerName` in `/etc/cups/client.conf`. Do not try to bind that file in. `flatpak override --user --filesystem=/etc/cups:ro <app>` is accepted by the override command but can never take effect, because every path under `/etc` is on Flatpak's reserved list. At launch Flatpak prints `Not sharing "/etc/cups" with sandbox: Path "/etc" is reserved by Flatpak` on stderr and carries on without it, which a user launching from a desktop icon never sees. Add the remote queue to the local `cupsd` instead, then grant `--socket=cups`:

```bash
sudo lpadmin -p office -E -v "ipp://printserver.example:631/printers/office" -m everywhere
lpstat -p -d
```

Then fully quit and relaunch the Flatpak app, because overrides are only read at startup.

**Verify.** `flatpak info --show-permissions org.libreoffice.LibreOffice` lists `cups` under `[Context] sockets`, and the printer now appears in the app's own print dialog.

Sources: <https://docs.flatpak.org/en/latest/sandbox-permissions.html> · <https://github.com/flatpak/xdg-desktop-portal/issues/341> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://wiki.archlinux.org/title/CUPS> · <https://wiki.archlinux.org/title/Flatpak> · <https://github.com/flatpak/flatpak/blob/main/common/flatpak-run-cups.c> · <https://github.com/flatpak/flatpak/blob/main/common/flatpak-exports.c> · <https://github.com/flatpak/flatpak/blob/main/common/flatpak-context.c> · <https://github.com/flatpak/flatpak/blob/main/doc/flatpak-override.xml>

---

## Make Flatpak apps show up in the Omarchy launcher

`flatpak-apps-missing-from-omarchy-launcher` · severity: **medium** · frequency: **common** · applies to: `arch`, `flatpak`, `hyprland`, `omarchy`, `uwsm`, `wayland`

**Symptom.** I installed an app with `flatpak install flathub org.something.App` and it runs fine from the terminal with `flatpak run`, but pressing Super+Space (the Omarchy launcher / app menu) never shows it. Other GUI apps installed with pacman show up fine.

**Cause.** The graphical session's XDG_DATA_DIRS (as seen by the uwsm-started `wayland-wm@hyprland.desktop.service` and therefore by the launcher) lacks the Flatpak export dirs. Flatpak ships a systemd user-environment generator (`/usr/lib/systemd/user-environment-generators/60-flatpak`) that normally adds `/var/lib/flatpak/exports/share` and `$XDG_DATA_HOME/flatpak/exports/share`, but generators only run when the systemd user manager starts and cannot override a value the session explicitly sets — so a manager started before Flatpak was installed, or a session that exports its own XDG_DATA_DIRS, keeps the short value. `/etc/profile.d/flatpak.sh` only fixes login shells, which is why `bash -lc 'echo $XDG_DATA_DIRS'` looks right while the launcher does not.

> **Audit corrected this record.** Symptom and source check out: basecamp/omarchy#8650 exists and describes exactly this (uwsm session `XDG_DATA_DIRS=/usr/local/share:/usr/share`, Quickshell AppLibrary scanning only that). But the cause is incomplete and one command is wrong. Arch's flatpak package DOES ship `/usr/lib/systemd/user-environment-generators/60-flatpak` (verified in the package file list), whose whole job is adding the export dirs to the systemd user-manager environment — so 'profile.d is only sourced by login shells' is not the full story. And `systemctl --user import-environment XDG_DATA_DIRS` copies the value out of the *calling shell*; a terminal opened from the Omarchy session inherits the same broken value, so that step is a no-op at best and re-clobbers the drop-in at worst. The drop-in itself is fine (`${HOME}` expansion is supported by environment.d) and the danger note about keeping `/usr/local/share:/usr/share` is correct.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Setting XDG_DATA_DIRS explicitly overrides the default. If you omit `/usr/local/share:/usr/share` from the value, pacman-installed apps and icon themes will disappear from the launcher instead.

**Fix.**

1) Confirm the entries exist: `ls /var/lib/flatpak/exports/share/applications/`. 2) Check the session: `systemctl --user show-environment | grep XDG_DATA_DIRS`. 3) Log out of Hyprland and back in first — flatpak's `60-flatpak` user-environment generator re-runs when the user manager starts, and that alone fixes it on machines where Flatpak was installed after first boot. 4) Only if the variable is still short, add the drop-in:

```bash
mkdir -p ~/.config/environment.d
cat > ~/.config/environment.d/flatpak-data-dirs.conf <<'EOF'
XDG_DATA_DIRS=/var/lib/flatpak/exports/share:${HOME}/.local/share/flatpak/exports/share:/usr/local/share:/usr/share
EOF
```

then log out and back in again. Do NOT run `systemctl --user import-environment XDG_DATA_DIRS` from a session terminal — it imports that shell's (broken) value; if you want it applied without a re-login, use a login shell: `bash -lc 'systemctl --user import-environment XDG_DATA_DIRS && dbus-update-activation-environment --systemd XDG_DATA_DIRS'` and restart the shell/launcher.

**Verify.** `systemctl --user show-environment | grep XDG_DATA_DIRS` lists the two flatpak `exports/share` paths, and the app appears in the launcher after re-login. `ls /var/lib/flatpak/exports/share/applications/` shows the `.desktop` file the launcher should be picking up.

Sources: <https://github.com/basecamp/omarchy/issues/8650>

---

## Make links from Flatpak apps open in the browser on Hyprland/wlroots

`flatpak-links-dont-open-on-wlroots` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `flatpak`, `hyprland`, `omarchy`, `wayland`, `xdg-desktop-portal`

**Symptom.** Clicking a hyperlink inside a Flatpak app (Discord, Element, Signal, a Flatpak IDE) does nothing at all. No browser window, no error dialog. Other apps open links fine.

**Cause.** Flatpak apps open URIs through the `org.freedesktop.portal.OpenURI.OpenURI` D-Bus interface. The wlroots-family backends (`xdg-desktop-portal-wlr` and `xdg-desktop-portal-hyprland`) do not implement the OpenURI / App-chooser / FileChooser portals — they only cover ScreenCast, Screenshot and Global Shortcuts. With no backend implementing the interface, the call silently fails.

**Fix.**

Install the generic GTK backend to fill the gap and set it as the default fallback:

```bash
sudo pacman -S xdg-desktop-portal-gtk
mkdir -p ~/.config/xdg-desktop-portal
cat > ~/.config/xdg-desktop-portal/hyprland-portals.conf <<'EOF'
[preferred]
default=hyprland;gtk
org.freedesktop.impl.portal.FileChooser=gtk
org.freedesktop.impl.portal.OpenURI=gtk
org.freedesktop.impl.portal.ScreenCast=hyprland
org.freedesktop.impl.portal.Screenshot=hyprland
EOF
systemctl --user restart xdg-desktop-portal.service xdg-desktop-portal-gtk.service
```

Also make sure a default browser is registered:

```bash
xdg-settings set default-web-browser <your-browser>.desktop
```

**Verify.** Click a link in the Flatpak app — the browser opens. `busctl --user introspect org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop | grep OpenURI` shows the interface is present.

Sources: <https://wiki.archlinux.org/title/Flatpak> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal>

---

## Get the journal to survive reboots so you can read a crash's logs

`journal-lost-after-reboot-no-persistent-storage` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** After a freeze or hard reboot, `journalctl -b -1` prints only:

```
Specifying boot ID or boot offset has no effect, no persistent journal was found.
```

and shows the current boot instead. `journalctl --list-boots` lists exactly one boot, and `journalctl --disk-usage` reports usage under `/run/log/journal` rather than `/var/log/journal`. So there is no way to see what happened before the crash.

**Cause.** journald is only writing to the in-memory runtime journal, which is discarded on every boot. On Arch the default is `Storage=persistent` and `/var/log/journal/` ships with the `systemd` package — so this state almost always means the directory was deleted (often while reclaiming disk space, or by `rm -rf /var/log/journal`), or `Storage=` was set to `volatile`/`auto` in a config drop-in, or `/var/log` is on a tmpfs.

> **Audit corrected this record.** Everything of substance in this record held, on Omarchy 4 and on plain Arch, and the only defect is one command in the danger field that cannot run on Omarchy. Confirmed on this machine (omarchy 4.0.2-1, systemd 261.2-1): `systemd-analyze cat-config systemd/journald.conf` shows the package-stock file only, with `#Storage=persistent` as the compile-time default, and /etc/systemd/journald.conf.d does not exist, so Omarchy overrides nothing about journald and the record's drop-in advice neither duplicates nor fights it. `pacman -Qo /var/log/journal` returns "owned by systemd 261.2-1", and `pacman -Ql systemd` lists `/var/log/journal/`, confirming the cause's claim that the directory ships with the package and that its absence means somebody removed it. The journal is persistent here, which is the premise the record depends on: `journalctl --header` reports a file under /var/log/journal/2e5dbe305d304555aa01d578380cb2e8/, `journalctl --list-boots` lists three boots, `journalctl --disk-usage` reports 679.8M in the file system, and /run/log/journal is empty. The quoted error text is exact rather than paraphrased: "Specifying boot ID or boot offset has no effect, no persistent journal was found." appears at line 82 of the cited journalctl-util.c and byte-identically in `strings /usr/bin/journalctl` on systemd 261.2-1, so it has not drifted. The recovery sequence is right, and its choice of `systemd-tmpfiles --create --prefix /var/log/journal` over a hand-written chmod is better than the record claims, because on this btrfs root that prefix picks up both /usr/lib/tmpfiles.d/systemd.conf line 28 (`z /var/log/journal 2755 root systemd-journal`) and /usr/lib/tmpfiles.d/journal-nocow.conf line 25 (`h /var/log/journal - - - - +C`), restoring the NOCOW attribute as well as the mode. `--create`, `--prefix`, `--flush`, `--list-boots` and `--disk-usage` all exist on the installed versions, checked against `systemd-tmpfiles --help` and `journalctl --help`. `findmnt /var/log` is the right tmpfs check and on Omarchy 4 it usefully shows the `@log` subvolume the installer creates. All four cited URLs resolved: journald.conf(5) and journalctl(1) both returned real Arch manual pages, the raw journalctl-util.c returned HTTP 200, and Arch's Systemd/Journal page line 141 supports the Storage=persistent default while line 145 supports the 10% and 4 GiB soft cap quoted in the danger. The local `man 5 journald.conf` confirms the auto-is-the-trap explanation. Nothing was removed from sources. The one correction: the danger says an oversized journal "breaks `pacman -Syu`", and on Omarchy 4 that command never gets as far as a disk check, because /usr/share/libalpm/hooks/00-omarchy-update-guard.hook runs omarchy-update-pacman-guard with AbortOnFail and that script aborts whenever both S and u are present, identical at upstream tag v4.0.3. The real Omarchy symptom is omarchy-update-requires-free-space printing "You need at least 10 GiB free to safely update Omarchy." I rewrote the danger only and left symptom, cause, fix and verify untouched, since a rewrite of correct text would itself be a defect. Severity and frequency left alone. Not exercised: I have no sudo, so I did not delete /var/log/journal, did not run the recovery sequence, did not restart journald, and did not reboot to prove `journalctl -b -1` comes back. I also never observed the volatile failure state itself, only the healthy state it contrasts with.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Persistent journals grow. The default cap is 10% of the filesystem with a soft cap at 4 GiB, which is exactly how a small root partition fills up and starts blocking updates. On plain Arch that shows up as `pacman -Syu` failing on disk space. On Omarchy 4 you see `omarchy update` refuse with `You need at least 10 GiB free to safely update Omarchy.` instead, and `pacman -Syu` is no test either way, because Omarchy's update guard hook aborts it whatever the disk looks like. Set `SystemMaxUse=` at the same time as you enable persistence.

Do not reclaim space by deleting `/var/log/journal` itself, which is what turns persistence off in the first place. Trim the files and leave the directory in place:

```bash
sudo journalctl --rotate
sudo journalctl --vacuum-size=200M
```

**Fix.**

Check where you stand:

```bash
journalctl --list-boots
journalctl --disk-usage
ls -ld /var/log/journal
systemd-analyze cat-config systemd/journald.conf | grep -i -E '^Storage|^#Storage'
findmnt /var/log
```

Re-create the directory with the right ownership and mode, then tell journald to flush:

```bash
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo systemctl restart systemd-journald.service
sudo journalctl --flush
```

Be explicit about the mode so nothing can silently fall back again — use a drop-in rather than editing the packaged `journald.conf`:

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/00-persistent.conf >/dev/null <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=500M
SystemMaxFileSize=50M
EOF
sudo systemctl restart systemd-journald.service
```

`Storage=auto` is the trap: it behaves like `volatile` whenever `/var/log/journal` does not exist, so the mere absence of the directory silently disables persistence. `Storage=persistent` creates it.

Reboot once, then confirm the previous boot is readable:

```bash
journalctl --list-boots
journalctl -b -1 -p err..alert --no-pager
journalctl -b -1 -k --no-pager | tail -50
```

Useful follow-ups for an actual crash post-mortem:

```bash
journalctl -b -1 -u <suspect-unit> --no-pager
journalctl -b -1 --since '10 min ago' --until 'now'   # relative to that boot's end
coredumpctl list
```

**Verify.** `ls /var/log/journal/` contains a machine-id directory with `.journal` files, `journalctl --disk-usage` reports usage under `/var/log/journal`, and after a reboot `journalctl --list-boots` lists at least two boots and `journalctl -b -1` shows real log lines.

Sources: <https://man.archlinux.org/man/journald.conf.5.en> · <https://man.archlinux.org/man/journalctl.1.en> · <https://wiki.archlinux.org/title/Systemd/Journal> · <https://raw.githubusercontent.com/systemd/systemd/main/src/journal/journalctl-util.c> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-update-pacman-guard> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-update-requires-free-space>

---

## Fix Podman GPU containers after an NVIDIA driver update (stale CDI spec)

`podman-nvidia-cdi-spec-stale` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy`, `podman`

**Symptom.** `podman run --rm --device nvidia.com/gpu=all archlinux nvidia-smi -L` fails with `Error: setting up CDI devices: unresolvable CDI devices nvidia.com/gpu=all`, or the container starts but `nvidia-smi` inside it reports `Failed to initialize NVML: Driver/library version mismatch`. It worked before the last update.

**Cause.** Podman resolves nvidia.com/gpu=... through a CDI spec, on Arch /etc/cdi/nvidia.yaml, maintained by the nvidia-ctk-cdi pacman hook in nvidia-container-toolkit. The hook does fire on nvidia-utils/nvidia-container-toolkit/opencl-nvidia/egl-* install and upgrade, but when it detects a driver version change it does not regenerate the spec — it patches the old version string in place with sed and warns you to regenerate manually. So the spec is stale or mangled when that substitution went wrong, when the hook was skipped (pacman --nohooks, or a driver installed outside pacman / an out-of-band DKMS rebuild), or when the file was never generated. There is no nvidia-cdi-refresh.service on Arch to fix it up at boot.

> **Audit corrected this record.** The problem and the remedy are right — I confirmed nvidia-container-toolkit ships usr/share/libalpm/hooks/nvidia-ctk-cdi.hook and usr/share/libalpm/scripts/nvidia-ctk-cdi, and that the package contains no nvidia-cdi-refresh.service, so the Arch-specific framing holds and `nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml` is exactly what the hook's own warning tells you to run. But the cause misstates when the spec goes stale: I read the hook, and it triggers on Install AND Upgrade of nvidia-utils, nvidia-container-toolkit, opencl-nvidia, egl-gbm and egl-wayland, so 'the driver was installed after the toolkit' is precisely the case the hook does handle. The real fragility is that when the version changed the script does not regenerate — it rewrites /etc/cdi/nvidia.yaml with a plain `sed` string substitution of the old libcuda version, and prints a warning saying to regenerate by hand if problems appear.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A regenerated spec only matches the driver that is loaded *right now*. If you regenerate it after a `pacman -Syu` but before rebooting into the new kernel/driver, it will break again on reboot — regenerate after the reboot, or just let the pacman hook do it and reboot.

**Fix.**

Same commands, with one extra check first — compare the driver version baked into the spec against the running driver, because the pacman hook may have sed-patched it rather than regenerating:

```bash
nvidia-ctk cdi list
grep -m1 'libcuda.so' /etc/cdi/nvidia.yaml
readlink -f /usr/lib/libcuda.so
```

If those versions disagree, or the paths in the file do not exist, regenerate rather than patch:

```bash
sudo mkdir -p /etc/cdi
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
nvidia-ctk cdi list
```

Then test:

```bash
podman run --rm --device nvidia.com/gpu=all --security-opt=label=disable archlinux nvidia-smi -L
```

If `nvidia-ctk cdi generate` itself fails, the host driver is the problem (`nvidia-smi`, `lsmod | grep ^nvidia`, `pacman -Q nvidia-utils nvidia-container-toolkit`). `nvidia-ctk --debug cdi list` for names that still will not resolve. Do not combine CDI GPUs with `--userns nomap` or `--userns auto`.

**Verify.** `nvidia-ctk cdi list` shows `nvidia.com/gpu=all` plus one entry per GPU, and the test container prints your GPU's UUID line.

Sources: <https://wiki.archlinux.org/title/Podman> · <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html> · <https://archlinux.org/packages/extra/x86_64/nvidia-container-toolkit/files/>

---

## Set up rootless Docker on Arch (the upstream setuptool does not exist here)

`rootless-docker-setuptool-missing-on-arch` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Following Docker's rootless instructions fails at the first step:

```
bash: dockerd-rootless-setuptool.sh: command not found
```

or, after wiring something up by hand, `docker ps` still shows the root daemon's containers, or `rootlesskit` dies with `failed to setup UID/GID map: newuidmap ... : exit status 1`.

**Cause.** Arch's `docker` package does not ship upstream's `dockerd-rootless.sh` / `dockerd-rootless-setuptool.sh` wrappers. The rootless pieces live in the AUR package `docker-rootless-extras`, which instead provides `docker.service` and `docker.socket` as **user** units. And rootless mode needs a subordinate UID/GID range allocated to your user, which older accounts do not have.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, kernel 7.1.9-arch1-2, docker 1:29.7.2-1, shadow 4.20.0.arch1-1, systemd 261) and against all four cited sources, every one of which returns 200 and supports the claim it is cited for, so nothing is removed. Confirmed on this machine: `pacman -Ql docker` lists only `/usr/lib/systemd/system/docker.service` and `docker.socket`, with no `dockerd-rootless.sh` and no `dockerd-rootless-setuptool.sh`, so the `command not found` framing and the whole cause are right. The Arch wiki Docker page states the same in its Rootless Docker daemon note, gives the `/etc/subuid` and `/etc/subgid` 65536 form, the `docker context create` line with `unix:///run/user/$(id -u)/docker.sock`, and the lingering tip. Podman page lines 68 to 78 are the source of the `usermod --add-subuids 100000-165535` command and of the warning that this is the default range for the first account. Systemd/User is the source of `loginctl enable-linger` and of the warning about faking autologin that the record's `danger` reproduces. `cause` and `danger` are correct and are left untouched. Three defects in `fix`, all of them generic advice that misfires on Omarchy 4. First, `printf 'DOCKER_HOST=unix://%t/docker.sock'` into `~/.config/environment.d/` does not work. `man 5 environment.d` on systemd 261 says the right hand side may reference variables using `${OTHER_KEY}` and `$OTHER_KEY` and that no other elements of shell syntax are supported, and `%t` is a unit-file specifier that `environment.d` never sees, so DOCKER_HOST would be set to the literal string `unix://%t/docker.sock`. The wiki's own wording is `unix://$XDG_RUNTIME_DIR/docker.sock`. Second, `zgrep CONFIG_USER_NS_UNPRIVILEGED /proc/config.gz` returns nothing on this stock Arch kernel: `zgrep -E 'CONFIG_USER_NS(_UNPRIVILEGED)?=' /proc/config.gz` prints only `CONFIG_USER_NS=y`, because that symbol is a linux-hardened addition and is absent from mainline, so the check reads as a positive for a problem that is not there. The record's linux-hardened scoping is itself correct, confirmed from Arch's `linux-hardened` config.x86_64 line 270, `# CONFIG_USER_NS_UNPRIVILEGED is not set`, and the sibling check holds: `/proc/sys/kernel/unprivileged_userns_clone` does exist here and reads `1`. Third, the subuid step is already done on Omarchy 4. `/etc/subuid` and `/etc/subgid` here both hold `techluddite:100000:65536`, and `/etc/login.defs` sets `SUB_UID_COUNT 65536`, so the record's exact suggested range is the one already taken, and `man 8 usermod` states that `--add-subuids` performs no checks against SUB_UID_MIN, SUB_UID_MAX or SUB_UID_COUNT, which means running it anyway silently appends a duplicate line. Added the Omarchy-specific point that Omarchy enables the system `docker.socket` and deliberately keeps the user out of the `docker` group, so the root daemon is always up and the context check is the load-bearing step rather than a nicety, which is also why `verify` now leads with `docker context show`. Boundary against the two neighbouring ufw records: `docker-container-dns-blocked-by-ufw` and `docker-published-ports-bypass-ufw` are both about the system daemon's bridge and its nftables chains, and neither applies to this record, because a rootless daemon reads `~/.config/docker/daemon.json` rather than Omarchy's `/etc/docker/daemon.json` and publishes ports through rootlesskit in the user's own namespace. I did not add a claim about how ufw treats rootless published ports, because I could not verify it. Package facts rechecked: AUR `docker-rootless-extras` is at 29.8.0-1 with depends `docker>=1:29.5.0` and `rootlesskit>=3.0.0`, which the installed docker satisfies, and `rootlesskit` is 3.1.0-1 in `extra`, so the record's older audit note figure of 29.7.2-1 is stale but the record body never quoted a version. NOT exercised: I have no sudo and am not in the `docker` group, so I could not install the AUR package, enable a user unit, create a context, or start any container. The `%t` failure and the merge behaviour are read from the systemd and shadow manual pages rather than observed, and the linux-hardened behaviour is read from Arch's packaged config rather than run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Rootless Docker is a separate, empty daemon: existing images, volumes and containers under `/var/lib/docker` are invisible to it and are NOT migrated. It also cannot bind ports below 1024 by default and has no access to host devices. Do not run both daemons and then wonder which one `docker compose down -v` just wiped — check `docker context show` first. Enabling lingering keeps a daemon running after logout; do not use lingering to fake autologin, it breaks session permissions.

**Fix.**

Install the rootless extras. They depend on `rootlesskit`, which now lives in `extra` rather than the AUR, so this is one AUR build:

```bash
yay -S docker-rootless-extras
```

Check whether you already have a subordinate ID range before allocating one. On Omarchy 4, and on any account created by a current `archinstall`, `useradd` has already done it, because `/etc/login.defs` sets `SUB_UID_COUNT 65536`:

```bash
cat /etc/subuid /etc/subgid
grep -E 'SUB_(UID|GID)_(MIN|COUNT)' /etc/login.defs
```

One line per file of the form `yourname:100000:65536` is everything rootless mode needs, and there is nothing more to do. Only if your user has no line, add one. `usermod` does no overlap checking at all, so running it when the range is already present just gives you a second duplicate line:

```bash
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
```

Pick a free range out of `/etc/subuid` if `100000-165535` is taken. It is the default range for the first account on the machine, which on Omarchy is you.

Start the daemon as a user unit:

```bash
systemctl --user enable --now docker.socket
systemctl --user status docker.socket
```

Point the client at it with a persistent context. This matters more on Omarchy than on plain Arch, because Omarchy enables the system `docker.socket` at install time, so the root daemon is always running and is what an unconfigured client reaches:

```bash
docker context create rootless --description "Rootless mode" \
  --docker "host=unix:///run/user/$(id -u)/docker.sock"
docker context use rootless
docker context show
docker info | grep -E 'rootless|Docker Root Dir'
```

Or set the environment variable instead, somewhere user units and GUI apps can see it rather than only in `.bashrc`. Write `${XDG_RUNTIME_DIR}` and not `%t`: `%t` is a systemd unit-file specifier, and `environment.d` expands only `$VAR` and `${VAR}` references, so `%t` would be stored as those two literal characters:

```bash
mkdir -p ~/.config/environment.d
printf 'DOCKER_HOST=unix://${XDG_RUNTIME_DIR}/docker.sock\n' > ~/.config/environment.d/60-docker-rootless.conf
```

That file is read when your systemd user instance starts, so it takes effect at your next login. For the shell you are in now:

```bash
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
```

To have it running without an open session, so containers come back after a reboot:

```bash
loginctl enable-linger
loginctl list-users        # LINGER should say yes
```

If `rootlesskit` still fails, check whether unprivileged user namespaces are blocked:

```bash
sysctl kernel.unprivileged_userns_clone
```

On Omarchy 4's stock `linux` kernel that reads `1` and user namespaces are available. Do not use `zgrep CONFIG_USER_NS_UNPRIVILEGED /proc/config.gz` as the test. That symbol does not exist in the mainline Arch `linux` config, so the grep prints nothing on a machine where rootless mode works perfectly well. It is a `linux-hardened` symbol, and Arch's `linux-hardened` config carries `# CONFIG_USER_NS_UNPRIVILEGED is not set`, which is the kernel where rootless mode actually fails:

```bash
uname -r
zgrep '^CONFIG_USER_NS' /proc/config.gz
```

**Verify.** `docker context show` says `rootless`, then `docker info` shows `rootless` in the security options and `Docker Root Dir: /home/<you>/.local/share/docker`, and `docker run --rm hello-world` succeeds without sudo. Check the context first: Omarchy keeps the system `docker.socket` enabled and leaves your user out of the `docker` group, so a client still pointed at the default context prints `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` rather than anything about rootless mode.

Sources: <https://wiki.archlinux.org/title/Docker> · <https://aur.archlinux.org/packages/docker-rootless-extras> · <https://wiki.archlinux.org/title/Systemd/User> · <https://wiki.archlinux.org/title/Podman> · <https://archlinux.org/packages/extra/x86_64/rootlesskit/json/> · <https://gitlab.archlinux.org/archlinux/packaging/packages/linux-hardened/-/raw/main/config.x86_64>

---

## Recover a service stuck in "Start request repeated too quickly"

`unit-start-limit-hit-restart-loop` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** A service dies and then refuses to come back at all:

```
foo.service: Start request repeated too quickly.
foo.service: Failed with result 'start-limit-hit'.
Failed to start foo.service.
```

`systemctl restart foo.service` returns the same thing immediately, without even trying to run the binary. The journal shows the service starting and exiting five times in a few seconds just before this.

**Cause.** With `Restart=always`/`on-failure`, a service that fails instantly gets restarted instantly, and systemd's start rate limiter cuts in: more than `StartLimitBurst` starts inside `StartLimitIntervalSec` (5 in 10s by default on Arch) and the unit is refused any further start until the interval passes. The rate limit is the *symptom*; the real failure is whatever made the service exit in the first place, and once the limiter trips, `systemctl restart` no longer tells you anything about it.

> **Audit corrected this record.** Checked against man systemd.unit(5) and man systemctl(1) on this machine (systemd 261.2-1), systemd v261's own parser table, and live units here. What held: both quoted messages are real in v261 (`log_unit_warning(u, "Start request repeated too quickly.")` at src/core/unit.c:1882, and `[SERVICE_FAILURE_START_LIMIT_HIT] = "start-limit-hit"` at src/core/service.c:6296). The 5-starts-in-10s default is confirmed twice, from the commented `#DefaultStartLimitIntervalSec=10s` / `#DefaultStartLimitBurst=5` at /etc/systemd/system.conf:56-57 and from live `StartLimitIntervalUSec=10s StartLimitBurst=5` on sshd.service. Reset-failed flushing the start rate limit counter, StartLimit* being documented `[Unit]` keys, `0` disabling rate limiting, and drop-ins being preferred over editing packaged units are all confirmed in the man pages. The framing that the rate limit is the symptom and not the fault is right and is kept verbatim. Three defects, all confirmed on this machine. (1) `systemctl show -p StartLimitIntervalSec` and `-p RestartSec` return NOTHING: the D-Bus properties are `StartLimitIntervalUSec` and `RestartUSec`, and `systemctl show -p` silently skips a name it does not know, so the record's diagnostic line lost two of five properties and its `verify` step could not show the interval the reader had just set. That is the worst of the three because it sat in `verify`. (2) The claim that systemd warns about StartLimit* in `[Service]` is true for exactly one key. systemd v261's src/core/load-fragment-gperf.gperf.in still carries `Service.StartLimitBurst`, `Service.StartLimitInterval` and `Service.StartLimitAction` as compat entries writing into the same Unit fields, and has no `Service.StartLimitIntervalSec`. `systemd-analyze verify` on a throwaway file in /tmp confirmed it: only `StartLimitIntervalSec=` in `[Service]` warns, while `StartLimitBurst=`, `StartLimitInterval=` and `StartLimitAction=` there produce no message and are applied. So the record promised feedback that does not arrive for the key most likely to be misplaced, and the real trap is a burst applied over the default 10s window. (3) `man systemctl` says `systemctl edit` reloads configuration when the editor exits, so the record's extra `daemon-reload` was redundant. The `danger` was half wrong and contradicted the record's own `fix`: reset-failed clears the recorded exit status but does not touch the journal, so "capture the journal output before resetting" was unnecessary alarm, while the fix itself correctly ran journalctl after resetting. The unbounded-restart-loop half of the danger is sound and is kept. Added an Omarchy branch because the record claims `applies_to: omarchy` and had no Omarchy content: six user units under /usr/share/omarchy/default/systemd/user/ set `Restart=` with `RestartSec=2` or `5` and set no `StartLimit*`, and five of them are loaded here showing `StartLimitIntervalUSec=10s StartLimitBurst=5`. NOT exercised: I did not trip a real start limit, edit, reset or restart any unit on this machine, so the reset-failed-then-start recovery sequence is confirmed from the man page and the parser source rather than by running it. severity `medium` and frequency `common` left alone, both look right for a generic systemd shape.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `systemctl reset-failed` clears the recorded exit code and status that
`systemctl status` was reporting, and resets the start rate limit counter and the
service restart counter, so the previous failure stops being shown once the unit
is started again. It does not touch the journal: `journalctl -u foo.service -b`
still holds every line from the failed attempts, which is why reading the journal
after resetting is safe and is the order given above.

Raising `StartLimitBurst` or setting `StartLimitIntervalSec=0` on a service that
crashes on startup turns it into an unbounded restart loop that can spin a CPU
core and flood the journal. The start limiter is the one thing stopping that, so
widen the interval instead of removing it, and only after the underlying failure
is understood.

**Fix.**

Clear the counter so you can try again and see the real error:

```bash
sudo systemctl reset-failed foo.service
sudo systemctl start foo.service
sudo journalctl -u foo.service -b --no-pager -n 100
```

For a user unit:

```bash
systemctl --user reset-failed foo.service
systemctl --user start foo.service
journalctl --user -u foo.service -b --no-pager -n 100
```

Find out what it actually runs and with what limits before guessing. Mind the
property names: `systemctl show` reports the interval and the restart delay as
`StartLimitIntervalUSec` and `RestartUSec`, not with the `...Sec` spellings you
write in a unit file. `systemctl show -p` ignores a property name it does not
recognise and prints nothing for it instead of erroring, so asking for
`-p StartLimitIntervalSec` returns an empty result and looks like the unit has no
limit:

```bash
systemctl cat foo.service
systemctl show foo.service -p ExecStart -p Restart -p RestartUSec \
  -p StartLimitBurst -p StartLimitIntervalUSec -p StartLimitAction
```

Fix the underlying failure. If the service is legitimately expected to flap (a
network-dependent daemon, a tunnel), widen the window and slow the restarts down
so it backs off instead of burning through the limit, with a drop-in rather than
by editing the packaged unit:

```bash
sudo systemctl edit foo.service
```

```ini
[Unit]
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Restart=on-failure
RestartSec=15
```

`systemctl edit` reloads the manager itself once the editor exits, equivalent to
`systemctl daemon-reload`, so no separate reload is needed:

```bash
sudo systemctl restart foo.service
```

That allows 5 starts per 5 minutes with 15 seconds between attempts. To disable
rate limiting entirely (rarely a good idea) set `StartLimitIntervalSec=0`.

`StartLimit*` belong in `[Unit]`, and putting them in `[Service]` fails with
almost no feedback. Measured with `systemd-analyze verify` on systemd 261:

```
$ systemd-analyze verify ./t.service        # StartLimitIntervalSec in [Service]
./t.service:7: Unknown key 'StartLimitIntervalSec' in section [Service], ignoring.

$ systemd-analyze verify ./t.service        # StartLimitBurst in [Service]
                                            # no output at all
```

`StartLimitBurst=`, `StartLimitInterval=` (the old spelling, no `Sec`) and
`StartLimitAction=` are still accepted inside `[Service]` as backward-compatible
aliases and are applied silently, while `StartLimitIntervalSec=` is not a
`[Service]` key at all and is dropped with a warning. So the whole block pasted
into `[Service]` leaves you with the burst you asked for over the default 10
second window, and only one line in the journal hints at it. Put them in `[Unit]`
and confirm with the `systemctl show` line above.

The defaults live in `/etc/systemd/system.conf` as `DefaultStartLimitIntervalSec=`
and `DefaultStartLimitBurst=`, and in `/etc/systemd/user.conf` for user units.
Both ship commented out at their stock values of `10s` and `5`.

On Omarchy this is a live shape rather than a hypothetical. Six of the user units
Omarchy ships under `/usr/share/omarchy/default/systemd/user/` set `Restart=`
with a short `RestartSec=` and none of them set `StartLimit*`, so they all
inherit 5 starts per 10 seconds:

```bash
systemctl --user show omarchy-fcitx5.service omarchy-sleep-lock.service \
  omarchy-crash-watch.service omarchy-tailscale-receive.service bt-agent.service \
  -p Restart -p RestartUSec -p StartLimitBurst -p StartLimitIntervalUSec
```

With `RestartSec=2` against a 10 second window, a binary that fails immediately
exhausts the burst in roughly ten seconds, which is why one of these units going
bad shows up as `start-limit-hit` rather than as a visible crash loop.

**Verify.** `systemctl status foo.service` shows `active (running)` and the journal no longer
contains `start-limit-hit`. Confirm the drop-in took effect with the property
names `systemctl show` actually uses, because the `...Sec` spellings return
nothing:

```bash
systemctl show foo.service -p StartLimitBurst -p StartLimitIntervalUSec -p RestartUSec
```

On a system unit with a 300 second window and a 15 second restart delay that
prints `StartLimitBurst=5`, `StartLimitIntervalUSec=5min` and `RestartUSec=15s`.
`systemctl cat foo.service` should also list your drop-in file under the unit.

Sources: <https://man.archlinux.org/man/systemd.unit.5.en> · <https://wiki.archlinux.org/title/Systemd> · <https://wiki.archlinux.org/title/Systemd/User> · <https://man.archlinux.org/man/systemd.service.5.en> · <https://raw.githubusercontent.com/systemd/systemd/v261/src/core/load-fragment-gperf.gperf.in> · <https://raw.githubusercontent.com/systemd/systemd/v261/src/core/unit.c>

---

## Fix a systemd user unit that never starts in the Hyprland session

`user-unit-never-starts-graphical-session` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `systemd`, `wayland`

**Symptom.** `systemctl --user enable foo.service` reports success, but the service is never running: `systemctl --user status foo.service` says `inactive (dead)` after every login. `systemctl --user status graphical-session.target` may show `inactive` too. Enabling it with `--now` starts it once, and then it is gone again after a reboot.

**Cause.** Session-scoped user units are pulled in by graphical-session.target, a passive target that must be activated by something. Since Hyprland integrated systemd target handling, Hyprland itself starts hyprland-session.target and graphical-session.target — even when launched bare from a TTY — unless HYPRLAND_NO_SD_TARGET is set, which suppresses both. So an inactive target now points at that variable, at leftover manual target plumbing from older guides, or at a session started some other way, rather than at 'bare Hyprland cannot reach it'. The other two traps are unchanged and are the usual culprits: a unit with no [Install] section cannot be enabled into anything, and `enable` without `--now` only schedules it for the next login.

> **Audit corrected this record.** The fix steps are almost all right and match the current Hyprland wiki (uwsm + libnewt, the `uwsm check may-start` bash_profile snippet, `add-wants graphical-session.target` for units with no [Install], the After/PartOf drop-in, `systemctl --user revert hyprland-session.target`, deleting leftover systemctl calls from hyprland.lua, and preferring enabled units over exec-once). But the central cause claim is stale: the wiki's Systemd startup page now states hyprland-session.target 'previously required manual setup, but is now integrated into Hyprland and handled automatically', and its note says setting HYPRLAND_NO_SD_TARGET 'will avoid this, but also prevent starting hyprland-session.target and graphical-session.target in the first place'. So a bare Hyprland launched from a TTY does reach graphical-session.target on 0.55/0.56 — 'never reaches' was true of the pre-integration era and now sends readers to fix the wrong thing. HYPRLAND_NO_SD_TARGET itself is a real variable, correctly named.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** A single user is not expected to have two compositors running at once: exiting one Hyprland instance stops `graphical-session.target` and takes down every session unit bound to it, including in the other session.

**Fix.**

Check whether the target is actually reached:

```bash
systemctl --user status graphical-session.target
systemctl --user list-dependencies graphical-session.target
```

If it is inactive, the likely reasons on a current Hyprland are that the target start was suppressed or that leftover manual plumbing is interfering — Hyprland starts hyprland-session.target and graphical-session.target itself now:

```bash
systemctl --user show-environment | grep HYPRLAND_NO_SD_TARGET   # must be unset
systemctl --user revert hyprland-session.target                  # drop old manual target files
```

and delete any `systemctl --user start hyprland-session.target` / `stop graphical-session.target` calls from `hyprland.lua`. Launching through uwsm remains the most robust option and is what Omarchy does (`Exec=uwsm start -g -1 -e -D Hyprland hyprland.desktop`); from a TTY:

```bash
sudo pacman -S --needed uwsm libnewt
```

```bash
# ~/.bash_profile
if uwsm check may-start; then
    exec uwsm start hyprland.desktop
fi
```

With the target reachable, the unit-side fixes are as written: `systemctl --user daemon-reload` then `enable --now`; `systemctl --user add-wants graphical-session.target foo.service` when the unit has no [Install]; and a drop-in via `systemctl --user edit foo.service` adding `After=graphical-session.target` / `PartOf=graphical-session.target` rather than editing the shipped file. Prefer `systemctl --user enable hyprpaper.service` over an `exec_cmd("hyprpaper")` line.

**Verify.** After a fresh login, `systemctl --user status graphical-session.target` is `active`, and `systemctl --user status foo.service` is `active (running)` without you touching it.

Sources: <https://wiki.hypr.land/Useful-Utilities/Systemd-start/> · <https://wiki.archlinux.org/title/Systemd/User> · <https://raw.githubusercontent.com/basecamp/omarchy/master/default/wayland-sessions/omarchy.desktop> · <https://wiki.archlinux.org/title/Systemd>

---

## Fix a virtiofs shared folder that refuses to start or mount

`virtiofs-share-requires-shared-memory` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `laptop`, `libvirt`, `manjaro`, `omarchy`

**Symptom.** Adding a virtiofs filesystem to a VM makes it fail to boot:

```
error: unsupported configuration: 'virtiofs' requires shared memory
```

Or the VM starts but the guest cannot mount it: `mount: /mnt: unknown filesystem type 'virtiofs'`. With a 9p share instead, the guest fails at boot with `9pnet: Could not find request transport: virtio`.

**Cause.** virtiofs is a vhost-user device: the `virtiofsd` process needs the guest's RAM mapped as shared memory, and libvirt refuses to start the domain unless `<memoryBacking>` declares shared access (or every NUMA cell sets `memAccess='shared'`). `unknown filesystem type 'virtiofs'` in the guest means the guest kernel has no virtiofs support, which needs Linux 5.4 or later. On a current Arch guest it is built into the `linux` package (7.1.9), so that message points at an old or non-Arch guest kernel. Separately, the 9p transport module `9pnet_virtio` is not auto-loaded, so an `/etc/fstab` entry using `trans=virtio` fails during boot before anything can load it.

> **Audit corrected this record.** Checked the XML, the mount syntax, the session-mode ID mapping and the 9p module claim against the Arch wiki Libvirt and QEMU pages (raw wikitext), libvirt's virtiofs kbase page and formatdomain.html, and libvirt's own source. The error text is exact: qemu_validate.c reports "'%s' requires shared memory" with name "virtiofs" whenever <memoryBacking> lacks <access mode='shared'/> and no NUMA cell declares memAccess='shared'. The memfd + shared XML, the <filesystem> block, the mount tag note, the guest mount command and the fstab line all match the kbase page and the wiki word for word. The unprivileged claims hold: the kbase page says qemu:///session supports virtiofs with ID mapping since libvirt 10.0.0, guest root maps to the host user and other IDs go to /etc/subuid and /etc/subgid, and the wiki carries the same <idmap> example, and usermod 4.20 has --add-subuids and --add-subgids. The 9pnet_virtio modules-load fix and the trans=virtio,version=9p2000.L fstab line are verbatim from the wiki. The danger was wrong for the fix it accompanies: with <source type='memfd'/> libvirt builds memory-backend-memfd with no mem-path (qemu_command.c), so nothing is written under memory_backing_dir and no disk is consumed. Only <access mode='shared'/> with no <source> falls back to memory-backend-file under /var/lib/libvirt/qemu/ram (default confirmed in the installed /etc/libvirt/qemu.conf). The cause did not explain the 'unknown filesystem type virtiofs' symptom, which the kbase page attributes to guest kernels older than 5.4, and on Arch linux 7.1.9 virtiofs is built in. Package virtiofsd 1.14.0-1 exists in extra and is installed here alongside libvirt 12.6.0 and qemu-base 11.1.0.
>
> *The Cause above was rewritten on 2026-09-06 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `<access mode='shared'/>` makes the whole guest RAM allocation shareable with the `virtiofsd` process. With `<source type='memfd'/>` as in the fix, QEMU allocates it as `memory-backend-memfd`, which lives in RAM and writes nothing to disk. Only if you set shared access without a `<source>` element does libvirt fall back to `memory-backend-file`, which creates a file the size of the guest's RAM under `memory_backing_dir` (`/var/lib/libvirt/qemu/ram` by default in `/etc/libvirt/qemu.conf`, on disk unless you set `memory_backing_dir = "/dev/shm/"`). `accessmode='passthrough'` gives the guest the host user's permissions on the shared tree, so do not point it at your whole home directory. In a `qemu:///session` VM, a file the guest creates as an ordinary user shows up on the host owned by an ID from your subordinate range rather than by you.

**Fix.**

**Host — add the shared memory backend.** `virsh edit <vm-name>` and add, inside `<domain>`:

```xml
<memoryBacking>
  <source type='memfd'/>
  <access mode='shared'/>
</memoryBacking>
```

Then declare the share itself, inside `<devices>`:

```xml
<filesystem type='mount' accessmode='passthrough'>
  <driver type='virtiofs'/>
  <source dir='/home/you/vmshare'/>
  <target dir='vmshare'/>
</filesystem>
```

`target dir` is an arbitrary mount tag, not a path. Install the daemon on the host if it is missing:

```bash
sudo pacman -S --needed virtiofsd
```

**Guest — mount it:**

```bash
sudo mount -t virtiofs vmshare /mnt/vmshare
```

```
# /etc/fstab
vmshare  /mnt/vmshare  virtiofs  rw,noatime  0 0
```

If you are running a QEMU/KVM **user** session rather than the system session, the user that runs `virtiofsd` needs subordinate ID ranges:

```bash
cat /etc/subuid
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
```

By default guest root maps to your host user and other guest IDs map into that subordinate range; pin a specific mapping with `<idmap>` if file ownership comes out wrong:

```xml
<filesystem type='mount' accessmode='passthrough'>
  <idmap>
    <uid start="2000" target="1000" count="1"/>
    <gid start="2000" target="1000" count="1"/>
  </idmap>
</filesystem>
```

**If you are stuck on 9p** instead, preload the transport module in the guest so the fstab entry works at boot:

```bash
printf '9pnet_virtio\n' | sudo tee /etc/modules-load.d/9pnet_virtio.conf
```

```
# /etc/fstab (9p)
vmshare  /mnt/vmshare  9p  trans=virtio,version=9p2000.L  0 0
```

**Verify.** The VM starts without the shared-memory error, and in the guest `mount | grep virtiofs` shows the share and files created on either side appear on the other.

Sources: <https://wiki.archlinux.org/title/Libvirt> · <https://wiki.archlinux.org/title/QEMU> · <https://libvirt.org/kbase/virtiofs.html> · <https://libvirt.org/formatdomain.html> · <https://archlinux.org/packages/extra/x86_64/virtiofsd/> · <https://github.com/libvirt/libvirt/blob/master/src/qemu/qemu_validate.c> · <https://github.com/libvirt/libvirt/blob/master/src/qemu/qemu_command.c>

---

## Fix omarchy-windows-vm launch starting the container and never opening an RDP window

`windows-vm-launch-no-rdp-window-stale-log` · severity: **medium** · frequency: **common** · applies to: `arch`, `desktop`, `docker`, `freerdp`, `laptop`, `omarchy`, `windows`

**Symptom.** `omarchy-windows-vm launch` starts the Docker container and exits without drawing a window. From the desktop entry, which runs with `Terminal=false`, nothing appears at all and no error is visible. Reported on Omarchy 4.0.0-1 with Docker 29.7.2, freerdp 2:3.30.0-2 and `dockurr/windows` v5.16.

It happens on a container that has been used before and not removed:

```console
$ docker inspect omarchy-windows --format '{{.Created}} {{.State.StartedAt}}'
2026-08-13T14:49:54Z   2026-08-14T18:07:11Z

$ docker logs omarchy-windows 2>&1 | grep -ci "windows started successfully"
9
```

**Cause.** The readiness wait grepped the whole container log. `docker logs` keeps output across `docker stop` and `docker start` and is cleared only when the container is removed, so any container that has booted Windows once already contains a `Windows started successfully` line. The loop matched on its first iteration and `xfreerdp3` ran about a second after `docker compose up -d`, while the guest was still in firmware. On the reporter's machine the guest needs about 30 seconds to reach that line, so the client fired roughly 29 seconds too early.

A second path had nothing to do with stale logs: when the container was already running the readiness wait was skipped outright, and `dockurr/windows` restarts the guest inside a running container whenever Windows reboots or shuts down.

Two other causes produce the same "container starts, nothing happens" symptom and are worth ruling out. FreeRDP 3 tries Kerberos before NTLM, and Arch's `krb5` ships the upstream MIT sample `/etc/krb5.conf` with `default_realm = ATHENA.MIT.EDU`, so with no working internet each attempt blocked about 23 seconds and `xfreerdp3` sat in `CLOSE-WAIT` drawing nothing. A contributor measured a stock config never connecting offline against 36 seconds with a realm-less one. And a second reporter's case was neither: their Compose credentials and `~/.config/windows/credentials` had diverged and an auth-only check returned `STATUS_LOGON_FAILURE`.

> **Audit corrected this record.** Confirmed on this machine, omarchy 4.0.2-1: `/usr/share/omarchy/bin/omarchy-windows-vm` is a symlink to `/usr/bin/omarchy-windows-vm` owned by `omarchy 4.0.2-1`, line 915 is the anchored wait `docker logs --since "$started_at" "$CONTAINER" 2>&1 | grep -qi "windows started successfully"`, and lines 1441 to 1446 write `$HOME/.config/windows/krb5.conf` with `dns_lookup_kdc = false` and `dns_lookup_realm = false` and export `KRB5_CONFIG`. The version claim holds: I fetched `bin/omarchy-windows-vm` at the `v4.0.0`, `v4.0.1`, `v4.0.2`, `v4.0.3` and `quattro` refs, and `v4.0.0` has neither `docker logs --since` nor `KRB5_CONFIG` while every later ref has both. `v4.0.2`, `v4.0.3` and `quattro` are byte-identical to the installed file, md5 `b7827f13056a0e1132add721f71b66ec`, so nothing about this changed in the 2026-09-08 release. I read `omacom/omarchy#6882` in full with comments, and it supports the cause exactly, including the nine stale log matches, the roughly 30 second guest boot, the skipped wait on the already-running path, the ATHENA.MIT.EDU Kerberos hang measured at never versus 36 seconds, and davetist's credential-mismatch case. `omacom/omarchy#6882` is closed as completed and `omacom/omarchy#9515` is open with no comments, matching the record. Three things were wrong and I rewrote the fix. First, the manual workaround is broken as written: a plain `omarchy-windows-vm launch` whose RDP attempt fails runs `docker-compose -f "$COMPOSE_FILE" down` (line 351 of the `v4.0.0` script, line 1464 onward in the installed one), which removes the container, so the following `docker inspect` returns nothing, `$started` is empty, and the `until` loop polls a container that no longer exists. The first launch has to pass `--keep-alive`. Second, the workaround stopped at the log line, which issue 9515 shows is about 9 seconds short of RDP being reachable, so I added the in-container guest port probe that issue 6882 recommends and the warning that probing `127.0.0.1:3389` on the host is useless because docker-proxy accepts regardless. Third, the credential advice was version-wrong: on 4.0.0 there is no `~/.config/windows/credentials` at all and the launcher greps the compose file (lines 276 to 278 of the `v4.0.0` script), while on 4.0.1 and later the private file wins and compose is only a readable fallback (lines 1399 to 1406 installed), so "the two must agree" is the wrong check in both cases and the rewrite labels each branch. I also named `omacom/omarchy#5202`, confirmed open, because it is what turns a too-early connection into a destroyed VM. Not exercised: Docker and a `dockurr/windows` container are not set up on this workstation, so I could not run `omarchy-windows-vm launch`, reproduce the stale-log match, time a guest boot, or test the dnsmasq lease and `nc -z` probe, which come from issue 6882's suggested fix rather than from a run here.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

**Update.** Both the readiness wait and the Kerberos hang are fixed in the shipped script from 4.0.1 onward. The `v4.0.0` tag carries neither and `v4.0.1` and later carry both.

```bash
omarchy update
```

Confirmed in the installed script on omarchy 4.0.2-1: the wait anchors the log scan to the container's current start time and now runs whether or not the container was already up, and the launcher writes its own realm-less Kerberos config and points `KRB5_CONFIG` at it before calling `xfreerdp3`:

```bash
grep -n 'docker logs --since' /usr/share/omarchy/bin/omarchy-windows-vm
grep -n 'KRB5_CONFIG' /usr/share/omarchy/bin/omarchy-windows-vm
```

**If you cannot update yet**, wait for the guest yourself rather than trusting the launcher, using the container's current start time so stale lines cannot match. Pass `--keep-alive`, because a plain `launch` runs `docker-compose down` as soon as `xfreerdp3` exits, and that removes the container and leaves you nothing to inspect or poll:

```bash
omarchy-windows-vm launch --keep-alive   # run it from a terminal, so freerdp's error is visible
started=$(docker inspect omarchy-windows --format '{{.State.StartedAt}}')
until docker logs --since "$started" omarchy-windows 2>&1 | grep -qi 'windows started successfully'; do sleep 2; done
guest=$(docker exec omarchy-windows awk '{print $3}' /var/lib/misc/dnsmasq.leases | head -1)
until docker exec omarchy-windows nc -z "$guest" 3389; do sleep 2; done
omarchy-windows-vm launch --keep-alive   # the container is already up, so this connects straight away
```

The second loop matters because the log line means QEMU booted the guest, not that Windows is accepting RDP. Probe the guest from inside the container as above rather than `127.0.0.1:3389` on the host: docker-proxy accepts that connection whether or not the guest is listening.

**If the guest is up and the window still does not appear**, check the credentials rather than the timing. On 4.0.1 and later the launcher reads `~/.config/windows/credentials` first and falls back to the compose file only when that file is readable, so the one that has to match the account inside Windows is `~/.config/windows/credentials`. On 4.0.0 there is no such file and the launcher greps `USERNAME` and `PASSWORD` straight out of `~/.config/windows/docker-compose.yml`. Either way a mismatch shows as `STATUS_LOGON_FAILURE` in the terminal output.

One residual defect is still open upstream and is not fixed in the newest release. `omacom/omarchy#9515` reports the fixed wait returning about 9 seconds before the guest accepts RDP, so a launch can still connect too early, and `omacom/omarchy#5202`, also open, then tears the VM down when that client exits, which makes the next attempt another cold start. Launching with `--keep-alive` avoids the teardown so you can retry against a warm guest:

```bash
omarchy-windows-vm launch --keep-alive
```

**Verify.** ```bash
grep -n 'docker logs --since' /usr/share/omarchy/bin/omarchy-windows-vm   # the anchored wait is present
omarchy-windows-vm launch                                                 # from a terminal, an RDP window opens
```

Sources: <https://github.com/omacom/omarchy/issues/6882> · <https://github.com/omacom/omarchy/issues/9515> · <https://github.com/omacom/omarchy/issues/5202> · <https://github.com/omacom/omarchy/blob/v4.0.0/bin/omarchy-windows-vm> · <https://github.com/omacom/omarchy/blob/v4.0.1/bin/omarchy-windows-vm> · <https://github.com/omacom/omarchy/blob/v4.0.3/bin/omarchy-windows-vm>

---

## Set up zram so the desktop stops freezing under memory pressure

`zram-swap-oom-freezes` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `swap`, `zram`

**Symptom.** Compiling something large or opening too many browser tabs makes the whole desktop lock up for minutes — Hyprland stops repainting, the mouse stutters — and eventually a process is OOM-killed. `free -h` shows Swap: 0B.

**Cause.** No swap at all means the kernel has nowhere to push cold pages, so it thrashes the page cache and stalls before the OOM killer finally fires. zram gives compressed in-RAM swap, which absorbs this far better than no swap on a machine with an SSD you would rather not write to.

> **Audit corrected this record.** The generic Arch advice is sound (`zram-generator`, `[zram0]` with `zram-size`/`compression-algorithm`, `systemd-zram-setup@zram0.service`, the swappiness/watermark/page-cluster tuning, and the correct default of `min(ram / 2, 4096)`), and the danger note about hibernation needing real disk swap is right. It is wrong for Omarchy 4, which is in applies_to: Quattro already ships `/usr/lib/systemd/zram-generator.conf.d/90-omarchy.conf` (`zram-size = ram`, `zstd`, `swap-priority = 100`) and already enables `systemd-oomd.service` in `install/config/enable-services.sh` — so the stated symptom (`Swap: 0B`) should not occur there, and worse, the prescribed lever is the wrong one: zram-generator reads the main config file *first* and lets drop-ins override it, so a hand-written `/etc/systemd/zram-generator.conf` is silently overridden by Omarchy's shipped drop-in and the user's `min(ram / 2, 16384)` never takes effect.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** zram is volatile RAM — you cannot hibernate to it. If you rely on hibernate (Omarchy's `omarchy-hibernation-setup`), you still need a real disk swap file or partition with the correct `resume=` kernel parameter; adding zram does not replace it. `vm.swappiness=180` is only sensible when zram is the *only* swap — with a disk swap partition also active it will cause heavy disk swapping.

**Fix.**

Check what you already have before writing anything: `zramctl`, `swapon --show`, `cat /usr/lib/systemd/zram-generator.conf.d/*.conf /etc/systemd/zram-generator.conf* 2>/dev/null`.

**Plain Arch, no zram yet:** the record's steps are correct —

```bash
sudo pacman -S zram-generator
# /etc/systemd/zram-generator.conf
# [zram0]
# zram-size = min(ram / 2, 16384)
# compression-algorithm = zstd
sudo systemctl daemon-reload
sudo systemctl start systemd-zram-setup@zram0.service
```

**Omarchy 4:** zram is already configured (`zram-size = ram`, zstd, `swap-priority = 100`) and `systemd-oomd` is already enabled — do not create `/etc/systemd/zram-generator.conf`, it loses to the shipped drop-in. To change the size, add a drop-in that sorts after Omarchy's:

```bash
sudo mkdir -p /etc/systemd/zram-generator.conf.d
printf '[zram0]\nzram-size = min(ram / 2, 16384)\n' | sudo tee /etc/systemd/zram-generator.conf.d/99-local.conf
sudo systemctl daemon-reload
sudo systemctl restart systemd-zram-setup@zram0.service
```

The sysctl tuning and the hibernation warning (`omarchy-hibernation-setup` gives the disk swapfile priority 0; zram sits above it at 100 — `vm.swappiness=180` only suits a zram-only setup) stay as written.

**Verify.** `zramctl` shows `/dev/zram0` with your chosen size and `zstd` algorithm, `swapon --show` lists it, and `free -h` shows a non-zero Swap total. Under load the desktop stays responsive.

Sources: <https://wiki.archlinux.org/title/Zram> · <https://wiki.archlinux.org/title/Swap>

---

## Run docker-compose against Podman via the Docker-compatible socket

`docker-compose-against-podman-socket` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `podman`

**Symptom.** `docker compose up` or `docker-compose up` cannot reach a daemon. Two failures look alike and have different causes, so read the exact wording first.

Podman installed and no Docker daemon running:

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

Stock Omarchy 4, where Docker IS installed and `docker.socket` IS enabled, but the user is deliberately not in the `docker` group:

```
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

Or `podman compose` runs but builds fail with buildkit errors, or an image reference fails with `short-name "nginx" did not resolve to an alias and no unqualified-search-registries are defined in "/etc/containers/registries.conf"`.

**Cause.** Two separate causes behind similar text. On stock Omarchy 4 the daemon is there and the user is not allowed to talk to it: `/usr/share/omarchy/install/config/docker.sh` deliberately leaves the install user out of the `docker` group because that group is root-equivalent, and `/var/run/docker.sock` is `srw-rw---- root docker`, so the client gets a permission error rather than a missing daemon. Omarchy does not ship Podman at all, so a Podman setup on Omarchy is something the user installed. When Podman is the runtime, the cause is that Podman is daemonless, so nothing listens on a Docker socket until Podman's REST API socket is enabled. `docker-compose` speaks only to `$DOCKER_HOST`, and `podman compose` is a thin wrapper that shells out to whichever compose provider is installed. Separately, Arch's `podman` ships with no search registries configured, so unqualified image names never resolve.

> **Audit corrected this record.** Every Podman mechanic in this record holds, and I confirmed each against the Arch Podman wiki fetched as raw wikitext: the `podman.socket` user unit plus the `DOCKER_HOST` export (lines 222 to 224, and `usr/lib/systemd/user/podman.socket` is in podman 6.1.1-1's file list), `podman compose` as a thin wrapper with `docker-compose` taking precedence and `PODMAN_COMPOSE_PROVIDER` as the override (line 220), `DOCKER_BUILDKIT=0` (line 229), the `unqualified-search-registries` drop-in under `/etc/containers/registries.conf.d/` (lines 33 to 36 and 459 to 464, including the exact `short-name` error), `podman-docker` as the docker shim (line 21), lingering (line 418), and the record's `danger` about compose networks surviving `podman compose down` (line 555). I also checked that the BuildKit advice is not stale: `docker-compose` here is the Go plugin, not the old Python tool (Arch package `docker-compose` 5.5.0-1 with url `https://www.docker.com/`, shipping both `/usr/bin/docker-compose` and `/usr/lib/docker/cli-plugins/docker-compose`, and `docker-compose version` prints `Docker Compose version 5.5.0`), and that Go Compose still reads the variable: `DOCKER_BUILDKIT` appears 7 times in the binary's string table, `pkg/api/context.go` documents `BuildKitEnabled()` as checking it, and `pkg/compose/build_classic.go` still exists upstream. So I did not correct that. Three real defects, all Omarchy-specific. First, `~/.config/uwsm/env` is the Omarchy 3 path. Omarchy 4 retires it: `/usr/bin/omarchy-upgrade-to-quattro` copies it to a backup, migrates custom lines into `~/.config/uwsm/env.d/99-omarchy-upgrade-env`, then deletes the live file with the comment `never keep the active file` at line 1957, and `/usr/share/omarchy/default/uwsm/env.d/10-omarchy` tells users to override in `~/.config/uwsm/default` or `preferably, ~/.config/uwsm/env.d/*`. The quattro tree confirms it: `gh api repos/omacom/omarchy/git/trees/quattro?recursive=1` lists only `default/uwsm/default` and `default/uwsm/env.d/10-omarchy` and no `config/uwsm/env`. uwsm 0.26.7's own README (lines 639 to 643) does still source `uwsm/env`, so the old path works today, which is why this is a correction rather than a reject. Second, Omarchy 4 does not ship Podman at all: `pacman -Q podman` fails on this workstation and podman appears in neither `/usr/share/omarchy/install/omarchy-base.packages` nor `omarchy-other.packages`, which carry `docker`, `docker-buildx`, `docker-compose`, `lazydocker` and `ufw-docker` instead. Third and most costly for a reader, the record's headline error string sends an Omarchy user to the wrong cause. `/usr/share/omarchy/install/config/docker.sh` deliberately leaves the install user out of the `docker` group as root-equivalent, `install/config/enable-services.sh` enables `docker.socket`, and I confirmed locally that `getent group docker` is empty, `/var/run/docker.sock` is `srw-rw---- 1 root docker`, and `docker ps` as the unprivileged user returns `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` (docker 1:29.7.2-1). I split the symptom so both strings are matchable and added the Omarchy branch with `omarchy-setup-security-sudoless-docker`, whose own script text supplied the root-equivalence warning I put in `danger`. I also fixed `verify`, which claimed `with no Docker daemon installed`, a false premise on stock Omarchy 4, and changed the two bare `sudo pacman -S` lines to `-Syu` per the partial-upgrade rule. `sources_remove` drops `https://raw.githubusercontent.com/basecamp/omarchy/master/config/uwsm/env`. It still returns HTTP 200, so it resolves, but `master` is the Omarchy 3 tree and it does not support the Omarchy 4 claim the record now makes. Frequency lowered from `common` to `occasional` because Podman ships by default on none of the distros in `applies_to`, so this is a problem only for users who chose Podman. Severity left at `medium`: it blocks work and loses nothing. Not exercised: I have no sudo, so I did not enable `podman.socket`, install podman, write any registries drop-in, join the docker group, or start a container. The Branch B commands are read from the Arch wiki and the package contents, not observed running.

Corrected by hand on 2026-09-11 after the merge: this verdict's own fix wrote `sudo pacman -Syu podman` and `sudo pacman -Syu podman-docker`, which carry both a sync and a sysupgrade flag and are therefore exactly what `omarchy-update-pacman-guard` aborts, in the same fix that explains the guard. Both are now `pacman -S --needed`. Found by lint_corpus.py on the audit's output, which is what that lint is for.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `omarchy-setup-security-sudoless-docker` adds you to the `docker` group, and that group is equivalent to passwordless root: anything running as your user can then run `docker run -v /:/host alpine` and rewrite the whole host as root with no prompt. Omarchy leaves you out of it by default for exactly that reason, and the script prints the same warning before it acts. On the Podman side, `podman-compose` has known compatibility gaps with real compose files, so do not assume a working `docker-compose.yml` behaves identically. Networks created by a compose project are often not removed by `podman compose down`, so check `podman network ls` and clean up with `podman network rm` rather than assuming the environment is gone. `podman-docker` installs its own `/usr/bin/docker`, so it conflicts with the `docker` package Omarchy ships and pacman will ask you to remove one.

**Fix.**

First decide which problem you have, because the answers do not overlap.

Branch A, stock Omarchy 4 with Docker. Omarchy installs `docker`, `docker-buildx` and `docker-compose` and enables `docker.socket`, but leaves you out of the `docker` group on purpose, so Docker access goes through a prompt. Either elevate per command:

```bash
sudo docker compose up
```

or opt in to the group, behind Omarchy's own warning, and reboot:

```bash
omarchy-setup-security-sudoless-docker     # Setup > Security > Sudoless Docker
```

Read the danger note before you do that. To undo it:

```bash
omarchy-remove-security-sudoless-docker
```

Branch B, Podman instead of Docker. Podman is not part of Omarchy, so install it yourself first:

```bash
sudo pacman -S --needed podman
```

Enable Podman's Docker-compatible socket as a user unit and point the client at it:

```bash
systemctl --user enable --now podman.socket
systemctl --user status podman.socket
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
docker compose version
```

Make it permanent for shells, user units and GUI apps. On Omarchy 4 the graphical session environment is loaded by uwsm from `env.d` drop-ins, and the user's file goes in `~/.config/uwsm/env.d/`:

```bash
mkdir -p ~/.config/uwsm/env.d
cat > ~/.config/uwsm/env.d/50-podman-docker-host <<'EOF'
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
EOF
```

Do not use `~/.config/uwsm/env`. That was the Omarchy 3 path. uwsm still sources it, but Omarchy 4's upgrade tool retires it: `omarchy-upgrade-to-quattro` migrates custom lines into `~/.config/uwsm/env.d/99-omarchy-upgrade-env` and then deletes the file. Log out and back in for the change to take effect.

And for systemd user units:

```bash
mkdir -p ~/.config/environment.d
printf 'DOCKER_HOST=unix://%%t/podman/podman.sock\n' > ~/.config/environment.d/podman-docker.conf
```

BuildKit is not supported through the Podman socket, so turn it off:

```bash
export DOCKER_BUILDKIT=0
```

Configure search registries so plain `nginx` and `archlinux` resolve like they do with Docker:

```bash
sudo mkdir -p /etc/containers/registries.conf.d
sudo tee /etc/containers/registries.conf.d/10-unqualified-search-registries.conf >/dev/null <<'EOF'
unqualified-search-registries = ["docker.io"]
EOF
```

If you want the `docker` command itself to be Podman, install the shim. Note it conflicts with a real Docker install, so remove `docker` first if Omarchy put it there:

```bash
sudo pacman -S --needed podman-docker
```

To pick which compose implementation `podman compose` uses when both are installed (`docker-compose` wins by default):

```bash
export PODMAN_COMPOSE_PROVIDER=podman-compose
```

For containers to survive logout, enable lingering:

```bash
loginctl enable-linger
```

**Verify.** Branch A: `sudo docker compose version` and `sudo docker ps` work, or after `omarchy-setup-security-sudoless-docker` and a reboot the same two work with no `sudo` and `id -nG | tr ' ' '\n' | grep -w docker` matches. Branch B: with Docker's daemon absent or stopped, `docker compose version` and `docker ps` both work against `$DOCKER_HOST`, `podman ps` shows the same containers `docker ps` does, and `systemctl --user is-active podman.socket` reports `active`.

Sources: <https://wiki.archlinux.org/title/Podman> · <https://wiki.archlinux.org/title/Systemd/User> · <https://archlinux.org/packages/extra/x86_64/podman/> · <https://archlinux.org/packages/extra/x86_64/podman-docker/> · <https://archlinux.org/packages/extra/any/podman-compose/> · <https://archlinux.org/packages/extra/x86_64/docker-compose/> · <https://raw.githubusercontent.com/docker/compose/main/pkg/api/context.go> · <https://raw.githubusercontent.com/docker/compose/main/pkg/compose/build_classic.go> · <https://github.com/omacom/omarchy/tree/quattro/default/uwsm/env.d>

---

## Fix hostname.local names not resolving (mDNS off in resolved, or Avahi fighting it)

`mdns-local-hostname-not-resolving` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `ping nas.local` or `ping raspberrypi.local` fails with `Name or service not known`, `getent hosts nas.local` returns nothing, and a network printer or Home Assistant box that other devices reach by `.local` name is unreachable. The device answers fine by IP address. A related symptom in the same area is the machine's own hostname gaining a number (`myhost-2.local`, then `myhost-3.local`), which means two mDNS responders are fighting over it. One thing that looks like this symptom but is not: on Omarchy 4, `resolvectl query nas.local` returning `No appropriate name servers or networks for name found` is the expected reply even when `.local` resolution is working perfectly, because Omarchy disables systemd-resolved's mDNS and lets Avahi own it.

**Cause.** Two different mDNS stacks can serve `.local` names, and which one is in play decides everything. The record this replaces assumed systemd-resolved, which is wrong for Omarchy.

**Omarchy 4 gives mDNS to Avahi and preconfigures all of it.** `avahi` and `nss-mdns` ship in `/usr/share/omarchy/install/omarchy-base.packages`, `/usr/share/omarchy/install/config/enable-services.sh` runs `systemctl enable avahi-daemon.service`, and Omarchy replaces `/etc/nsswitch.conf` with its own copy whose `hosts:` line already carries `mdns_minimal [NOTFOUND=return]` ahead of `resolve`. Omarchy also ships `/etc/systemd/resolved.conf.d/10-disable-multicast.conf` setting `MulticastDNS=no` and `LLMNR=no`, so systemd-resolved is deliberately neither an mDNS resolver nor a responder. The visible consequence is that on a healthy Omarchy 4 box `getent hosts nas.local` succeeds while `resolvectl query nas.local` fails, and that is correct rather than broken. When `.local` genuinely fails on Omarchy the cause is normally `avahi-daemon` being down or its socket stuck, a firewall gap on unicast port 5353, or systemd-resolved answering the `SOA` query for the `local` domain, which makes `nss-mdns` stand down.

**On plain Arch and the other derivatives nothing is preconfigured, and two separate switches are off.** systemd-resolved's global `MulticastDNS=` does default to yes, but mDNS activates for a connection only when the network manager enables it per connection as well, and NetworkManager's `connection.mdns` default of `-1` leaves it off. Independently of that, glibc will not consult Avahi at all until `nss-mdns` is installed and named in the `hosts:` line.

The hostname-gaining-a-number symptom is the opposite fault, two responders on one interface, with Avahi and systemd-resolved both answering mDNS and fighting over the name. That is reachable on plain Arch and not on a stock Omarchy 4 install, where resolved's responder is already off. Avahi additionally has a long-standing hostname race of its own that can produce the same renaming even with a single responder.

> **Audit corrected this record.** The record's central framing is inverted for Omarchy 4, and I confirmed that on this workstation (omarchy 4.0.2-1, kernel 7.1.9, avahi 1:0.9rc5-1, nss-mdns 0.15.1-2). Omarchy ships `/etc/systemd/resolved.conf.d/10-disable-multicast.conf` with `MulticastDNS=no` and `LLMNR=no`, owned by `omarchy-settings 4.0.2-1` and shown as applied by `systemd-analyze cat-config systemd/resolved.conf`, so the claim that resolved's global `MulticastDNS=` is on by default and that per-connection NetworkManager enablement is the missing half is true on plain Arch and false here. Omarchy hands mDNS to Avahi and preconfigures every part: `avahi` and `nss-mdns` are in `install/omarchy-base.packages`, `install/config/enable-services.sh` enables `avahi-daemon.service`, and `/etc/nsswitch.conf` already reads `hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns` against the Arch stock line in `/usr/share/factory/etc/nsswitch.conf`, which has no `mdns_minimal`. Measured end to end against a real LAN device rather than reasoned about: `getent hosts truenas.local` and `avahi-resolve -n truenas.local` both return addresses while `resolvectl query truenas.local` fails with `No appropriate name servers or networks for name found`, so the record's Path A verify command reports a fault on a fully working machine, and a user acting on that reading would run Path A, disable `avahi-daemon`, and actually break both `.local` resolution and CUPS printer discovery, since the Arch CUPS wiki states DNS-SD is supported only through Avahi and never through resolved. `resolvectl query <own-hostname>.local` is a false pass on top of that, returning addresses tagged `Data from: synthetic` even with mDNS off. The most serious unflagged hazard is the nsswitch clobber: upstream `docs/file-layout.md` on `quattro` and the scriptlet at `/var/lib/pacman/local/omarchy-settings-4.0.2-1/install` both show `omarchy-settings` doing `cp -f /usr/share/omarchy/etc-overrides/nsswitch.conf /etc/nsswitch.conf` from `post_install` and `post_upgrade`, with an upstream comment saying customizations will be reset on every upgrade, so a hand edit vanishes with no `.pacnew`, no backup and nothing `pacdiff` can show. The `host -t SOA local` step cannot run as written, confirmed: `bind` is not installed and `command -v host` finds nothing. Everything generic in the record is source-backed and I kept it, checking each cited page in full: the Arch Avahi wiki gives the identical `hosts:` line including `[!UNAVAIL=return]`, the `NXDOMAIN` SOA precondition, the `mdns` plus `/etc/mdns.allow` fallback, the `mtr` and `traceroute` reverse-lookup breakage and a troubleshooting section for the incrementing hostname, the Systemd-resolved wiki gives the two-places activation rule and `MulticastDNS=resolve` for Avahi coexistence, and the nss-mdns README says plainly to test with `getent hosts` and not with `host` or `nslookup` because those bypass NSS. All three cited URLs resolve and support what the record draws from them, so nothing needs removing. I also checked tag v4.0.3 (`0534987`, 2026-09-08) and `etc/nsswitch.conf`, the resolved drop-in and `enable-services.sh` are unchanged there, so this holds on the newest release. Corrected symptom, cause, fix, verify and danger, and lowered frequency to `occasional` because on Omarchy the stack ships working so the condition is not commonly hit, while it stays genuine on the six other targets. On the boundary question, this record and `mdns-local-hostnames-fail-ufw-blocks-5353` are the same problem and the sibling is the better of the two, so I narrowed this one to the stack-ownership and responder-conflict question and cross-referenced the sibling for the firewall and nsswitch half rather than duplicating it. My recommendation is that a later pass merge them into one `network` record. Flagging separately that the sibling now needs its own re-audit, because stock ufw already accepts multicast mDNS: `/etc/ufw/before.rules` line 68 carries `-A ufw-before-input -p udp -d 224.0.0.251 --dport 5353 -j ACCEPT` and `before6.rules` line 136 the `ff02::fb` equivalent, both clean under `pacman -Qkk ufw`, and on this box `/etc/ufw/user.rules` opens only 53317 yet `avahi-browse` lists the whole LAN, which contradicts the sibling's claim that ufw drops mDNS replies until a rule is added. The sibling also tells users to reconcile a nsswitch `.pacnew` that will never appear. Not exercised, because I have no sudo: I did not disable `avahi-daemon`, did not switch to the resolved stack, did not add a ufw rule, did not read live `ufw status` output, and could not reproduce either the hostname-renaming loop or a unicast-5353 block.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not hand-edit `/etc/nsswitch.conf` on Omarchy 4 and expect the edit to last. The file belongs to the Arch `filesystem` package, so Omarchy cannot ship it through pacman without a conflict, and `omarchy-settings` instead runs `cp -f /usr/share/omarchy/etc-overrides/nsswitch.conf /etc/nsswitch.conf` from both its `post_install` and its `post_upgrade` scriptlet. Upstream's own comment on those lines states that users who customize the file will have their changes reset to Omarchy defaults on every upgrade. There is no `.pacnew`, no backup and nothing for `pacdiff` to offer, so the edit disappears silently at the next `omarchy update` that bumps `omarchy-settings`. You almost never need to touch it, because the shipped line already carries `mdns_minimal`.

Getting the `hosts:` line wrong breaks all name resolution system-wide, pacman included. Copy the file aside first with `sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.bak` and test with `getent hosts archlinux.org` before you log out or reboot.

Disabling `avahi-daemon.service` on Omarchy 4 is not a neutral cleanup. CUPS supports DNS-SD only through Avahi and never through systemd-resolved, so it removes network printer discovery on a distro that enables `cups.service` by default, and it strands the `mdns_minimal` entry that Omarchy's own `hosts:` line depends on. The mirror-image error is running Avahi and systemd-resolved as mDNS responders at the same time, which causes the hostname-conflict renaming loop. Run exactly one responder.

Using the full `mdns` module instead of `mdns_minimal` makes reverse lookups in `mtr` and `traceroute` time out rather than falling back to other DNS services.

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

A stuck `/run/avahi-daemon/socket` stops NSS forwarding lookups to mDNS, and restarting both units clears it. If service discovery is the part that fails rather than name lookup, the firewall and the `SOA` precondition are covered by the record `mdns-local-hostnames-fail-ufw-blocks-5353`. Use that one instead of repeating the work here.

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

**Verify.** `getent hosts nas.local` returns an address. That is the test that matters, because it is the path applications use and the only one that exercises the `hosts:` line in `/etc/nsswitch.conf`. Then `avahi-browse --all --ignore-local --resolve --terminate` lists services from other machines, and `ping nas.local` works. Do not verify with `resolvectl query` or with `host`. The `host` command bypasses NSS entirely and so bypasses `nss-mdns`, and `resolvectl` reports only systemd-resolved, so on a correctly working Omarchy 4 box it fails with `No appropriate name servers or networks for name found` while `getent hosts` succeeds. `resolvectl query <own-hostname>.local` is worse than useless as a check, because resolved synthesizes an answer for the local hostname and tags it `Data from: synthetic`, which passes even with mDNS switched off completely. Use `resolvectl query nas.local` as the check only if you deliberately switched to the systemd-resolved stack.

Sources: <https://wiki.archlinux.org/title/Systemd-resolved> · <https://wiki.archlinux.org/title/Avahi> · <https://wiki.archlinux.org/title/CUPS> · <https://github.com/avahi/nss-mdns/blob/master/README.md> · <https://github.com/omacom/omarchy/blob/quattro/docs/file-layout.md> · <https://github.com/omacom/omarchy/blob/v4.0.3/etc/nsswitch.conf> · <https://github.com/omacom/omarchy/blob/v4.0.3/etc/systemd/resolved.conf.d/10-disable-multicast.conf> · <https://github.com/omacom/omarchy/blob/v4.0.3/install/config/enable-services.sh>

---

## Fix omarchy-mise-install failing on an attestation error or a deprecated package name

`mise-stale-registry-attestation-install-failure` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `desktop`, `gh`, `laptop`, `mise`, `omarchy`, `opencode`

**Symptom.** Installing a coding agent or CLI tool through Omarchy's mise wrapper fails, in one of two shapes on Omarchy 4.

The attestation check fails, on `gh` and on any other tool that resolves to an aqua package:

```
HTTP error: error decoding response body
```

Or mise resolves a package name that has moved upstream, so the install fetches the wrong thing:

```console
$ mise registry opencode
aqua:sst/opencode
```

The reporter who chased the first one was on mise `2025.10.19`.

**Cause.** Two different root causes behind two similar-looking failures, and neither one is anything wired wrong in Omarchy.

The deprecated-package-name shape is a stale mise registry. The OpenCode package moved orgs upstream and mise's registry already followed it, so a current mise resolves `aqua:anomalyco/opencode` while an old one still resolves `aqua:sst/opencode`. That is the maintainer's own diagnosis in issue 6886, quoted there as "a stale mise registry rather than something wired wrong in Omarchy".

The attestation shape has a different diagnosis. The maintainer read issue 6887 as a transient failure of GitHub's attestations API rather than a resolution or packaging defect, because `HTTP error: error decoding response body` is the verification call failing and not the package failing to resolve. He closed it as not planned and asked for a repeat with timestamps. The stale-mise explanation for this shape comes from the reporter, who closed the thread saying that moving from mise `2025.10.19` to `2026.8.6` made the attestation step pass and `mise use -g gh` then installed `gh@2.97.0` with "GitHub artifact attestations verified". So for the attestation shape, retry first and update mise second.

The maintainer declined pinning the backend to `github:cli/cli` or `github:anomalyco/opencode` in both threads, for two reasons worth knowing before you reach for it yourself. It trades a transient network error for permanently disabled supply-chain verification, and changing the backend key orphans the existing `opencode = "latest"` entry in `~/.config/mise/config.toml` and forces a re-download for everyone.

> **Audit corrected this record.** Confirmed on this workstation (omarchy 4.0.2-1, mise-bin 2026.9.1-1) that `pacman -Qo /usr/bin/mise` reports `mise-bin 2026.9.1-1`, that `pacman -Si mise-bin` puts it in the `omarchy` repo served from `https://pkgs.omarchy.org/stable/$arch`, and that `omarchy update` reaches it, since `/usr/bin/omarchy-update` calls `omarchy-update-system-pkgs`, which is `pacman -Syu --noconfirm --overwrite '/usr/share/omarchy/*'`. So the record's supported-route claim holds. Also confirmed here: `mise registry opencode` returns `aqua:anomalyco/opencode`, `mise registry gh` returns `aqua:cli/cli asdf:bartlomiejdanek/asdf-github-cli`, `/usr/share/omarchy/install/user/mise.sh` really does ship `omarchy-mise-install gh` and `omarchy-mise-install opencode` as bare names on the aqua backend, and `mise settings --all` lists `aqua.github_attestations true`, which is the setting the maintainer gestured at. Three things were wrong. First, the fix said `mise self-update` "writes over /usr/bin/mise". It does not, because the Omarchy build has already disabled it, and `mise --version` on this machine prints `mise WARN  self-update is disabled for this install, update mise the same way you installed it`. The record reached the right conclusion from a mechanism that does not happen. Second, the fix and the verify block both treat `omarchy-mise-install gh` as the command that installs and prints the attestations line. Reading `/usr/bin/omarchy-mise-install` shows it only writes a shim into `~/.local/bin` and prints nothing, and the install plus verification fire on the shim's first run, so `mise use -g gh` is the real check. Third, the cause said the maintainer "diagnosed both threads the same way" as a stale registry. He did say exactly that in issue 6886, but in issue 6887 he said the opposite, "a transient failure of GitHub's attestations API rather than a packaging or resolution defect on our side", and closed it not planned asking for timestamps. The stale-mise reading of the attestation shape is the reporter's closing comment, not the maintainer's, which changes the first action from "update mise" to "retry". Both issues were re-read in full with comments today, 2026-09-11, and both are closed as not_planned and are issues rather than pull requests. I could not exercise the failure itself: this machine is already on a current mise with a current registry, I have no sudo so `omarchy update` was never run, and I did not run `mise use -g gh` or any command that installs, so the attestations-verified line is taken from the threads rather than reproduced. One loose end left flagged rather than guessed: the reporter of 6887 says `mise self-update` worked for them, which cannot be true of this packaged mise, so their mise was probably not the `omarchy` repo build or that build did not disable the command in August.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not switch a tool's backend to `github:` and do not set `aqua.github_attestations` to false to get past this. Either one permanently disables supply-chain verification for that install in order to work around what the maintainer reads as a transient upstream API error, and changing a backend key also orphans the matching entry in `~/.config/mise/config.toml` and forces a re-download.

**Fix.**

**Omarchy 4.** mise here is the pacman package `mise-bin`, served from Omarchy's own repo rather than from `extra`, so take a newer mise the supported way:

```bash
pacman -Qo /usr/bin/mise        # /usr/bin/mise is owned by mise-bin
pacman -Si mise-bin             # Repository : omarchy
omarchy update                  # omarchy-update-system-pkgs runs pacman -Syu, which covers that repo
mise --version
mise registry opencode          # aqua:anomalyco/opencode on a current registry
```

Upstream's advice in both threads is `mise self-update`, and that does not work on Omarchy 4. The package build has already disabled it, so the command refuses instead of overwriting the packaged binary:

```
mise WARN  self-update is disabled for this install, update mise the same way you installed it
```

`mise self-update --help` says the same thing from the other side: "Packagers can disable this command so that mise is updated through the package manager instead." Keep `mise self-update` for a machine where mise was not installed by a package manager.

For the attestation shape, retry before you update anything, because the maintainer reads it as a transient GitHub API failure. The install and the verification happen when the tool runs, not when the wrapper is created:

```bash
mise use -g gh                  # ends with: GitHub artifact attestations verified
```

`omarchy-mise-install gh` is not an install step and is not a test. Read `/usr/bin/omarchy-mise-install`: it only writes a shim to `~/.local/bin/gh` and prints nothing on success. The shim runs `mise use -g --quiet gh` on its first invocation, which is where the attestation check actually fires. Use it to put the stock wrapper back if you replaced it with a pinned backend:

```bash
omarchy-mise-install gh         # bare name, aqua backend, as /usr/share/omarchy/install/user/mise.sh ships it
gh --version                    # this first run is what installs and verifies
```

If the attestation failure turns out to be persistent rather than transient, the maintainer's named lever is a mise setting rather than a rewritten backend. Verification is on by default:

```bash
mise settings --all | grep attestations   # aqua.github_attestations  true
```

**Plain Arch** is the same shape. Update mise through whatever installed it, which for the `extra` repo package `mise` means `pacman -Syu`, then retry.

**Verify.** ```bash
pacman -Qo /usr/bin/mise        # owned by mise-bin
mise --version                  # 2026.9.1 or newer
mise registry opencode          # aqua:anomalyco/opencode
mise use -g gh                  # ends with: GitHub artifact attestations verified
```

`omarchy-mise-install gh` is not a verification step. It prints nothing on success and only writes `~/.local/bin/gh`.

Sources: <https://github.com/omacom/omarchy/issues/6887> · <https://github.com/omacom/omarchy/issues/6886>

---

## Fix an NTFS external drive that Files refuses to mount: "volume is dirty and \"force\" flag is not set"

`ntfs-external-drive-mount-fails-volume-dirty` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `desktop`, `intel`, `nautilus`, `ntfs`, `omarchy`, `udisks`

**Symptom.** A USB hard drive formatted NTFS (a WD Elements in the report) shows up in the sidebar of Files (Nautilus) but clicking it gives a generic mount error. The kernel log has the real reason:

```
$ sudo dmesg | tail -n 20
[  118.870318] ntfs3(sda1): It is recommended to use chkdsk.
[  118.934869] ntfs3(sda1): volume is dirty and "force" flag is not set!
```

Reported on Omarchy 4 on an Intel NUC13, one machine.

**Cause.** Omarchy mounts NTFS through udisks, which uses the kernel `ntfs3` driver. The volume carries the NTFS dirty flag because Windows did not detach it cleanly (Fast Startup, hibernation, or unplugging without Safely Remove), and `ntfs3` refuses a read/write mount of a dirty volume unless `force` is passed. Files shows only its generic message. The flag is bookkeeping and the files are normally intact. This diagnosis was posted by a helper who reproduced the error text on a test image, and the reporter confirmed the dmesg line and the fix on their drive.

> **Audit corrected this record.** Checked the dirty-flag claim against the kernel source, the Arch wiki, the Arch package index, the udisks API documentation and this workstation (omarchy 4.0.2-1, kernel 7.1.9, udisks2 2.11.2-1, udiskie 2.7.0-2). Confirmed from source: fs/ntfs3/super.c emits `It is recommended to use chkdsk.` when VOLUME_FLAG_DIRTY is set and then refuses the mount with `volume is dirty and "force" flag is not set!` only when the mount is not read-only and `force` is absent, which is exactly the record's two dmesg lines and which proves the read-only mount advice. The Arch wiki NTFS page independently states that udisks prefers the ntfs3 driver, quotes the same dmesg line, and names `ntfsfix --clear-dirty` as the remedy. The Arch package index confirms ntfsprogs is still 2026.7.7-1 in extra today, pkgbase ntfs-3g, and that it ships /usr/bin/ntfsfix. Confirmed on this machine: neither ntfsprogs nor ntfs-3g is installed, so the default driver really is kernel ntfs3, `udisksctl mount` does accept `-o, --options`, /usr/share/omarchy/bin/omarchy-pkg-add exists and runs `pacman -S --noconfirm --needed` with no `-Sy`, so it trips no partial upgrade and no ALPM guard (the guard in /usr/bin/omarchy-update-pacman-guard fires only when both a sync and a sysupgrade flag are present). Issue 8725, read in full with comments, supports the symptom, the cause and the fix, and the reporter confirmed ntfsfix worked. It is still open today, which the record does not misstate. One thing needed correcting. The record stops at the dirty flag, but the same thread shows the reporter then hit a root-owned mount caused by a leftover /etc/fstab entry written by the Disks app, and the udisks Filesystem API documentation confirms the mechanism: if a device is referenced in /etc/fstab, udisks calls mount directly as root and ignores the options given. That makes two of the record's own steps unreliable as written, the `-o ro` mount and the verify line promising a /run/media/<user> target, so I rewrote the fix to check fstab first and rewrote verify to name the three failure outputs. I also moved the package date from 2026-09-07 to 2026-09-11, the day I checked it. NOT exercised: I have no NTFS device and no sudo here, so I ran no mount, no dmesg and no ntfsfix. The dirty-flag behaviour and the fstab behaviour are taken from the kernel source, the udisks documentation and the thread.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `ntfsfix` is not chkdsk. It clears the dirty flag and repairs a few known inconsistencies, and if it reports errors it cannot fix, stop and let Windows chkdsk run on the drive. Copy irreplaceable data off through the read-only mount before clearing the flag.

**Fix.**

Confirm the cause first. Retry the mount in Files, then read the kernel log and look for the `volume is dirty` line:

```bash
sudo dmesg | tail -n 20
lsblk -f                       # find the NTFS partition if it is not /dev/sda1
```

Check for an `/etc/fstab` entry before anything else. udisks hands a device that is named in fstab straight to `mount` as root and ignores the options you pass it, so both the read-only mount below and the later mount from Files come back owned by root:

```bash
grep -n sda1 /etc/fstab
```

If that prints a line, delete it, reload, and unmount what is already there, so udisks manages the drive again:

```bash
sudo nvim /etc/fstab            # delete the sda1 line
sudo systemctl daemon-reload
sudo umount /mnt/sda1           # repeat until findmnt /mnt/sda1 prints nothing
```

If anything on the drive is irreplaceable, copy it off first. A read-only mount works while the flag is set, because `ntfs3` refuses only a read/write mount:

```bash
udisksctl mount -b /dev/sda1 -o ro
```

Clear the flag. `ntfsfix` is in the `ntfsprogs` package (a split package of the `ntfs-3g` pkgbase, extra repo, version 2026.7.7-1 on 2026-09-11), which Omarchy does not install by default.

Omarchy 4:

```bash
omarchy pkg add ntfsprogs
sudo ntfsfix --clear-dirty /dev/sda1
```

Plain Arch:

```bash
sudo pacman -S --needed ntfsprogs
sudo ntfsfix --clear-dirty /dev/sda1
```

Then mount from Files again, or unplug and replug so udiskie automounts it. Never put `sudo` in front of `udisksctl` for a removable drive. `ntfs3` has no SID to uid mapping and takes ownership from the `uid=` and `gid=` mount options udisks sets from the caller, so a mount made as root lands in `/run/media/root/<label>`, which your user cannot enter.

If you also use Windows, eject with Safely Remove and turn off Fast Startup (Control Panel, Hardware and Sound, Power Options, "Choose what the power buttons do", untick "Turn on fast startup"), which was offered as the alternative fix but not tested in the thread.

**Verify.** ```bash
sudo dmesg | tail -n 5          # no new 'volume is dirty' line after the mount
findmnt -no SOURCE,TARGET,FSTYPE,OPTIONS /dev/sda1
id -u; id -g
```

A mount made by Files lands under `/run/media/<user>/<label>` with `uid=` and `gid=` matching your own ids. Three other outputs mean the job is not finished. A `/run/media/root/<label>` target means something ran `udisksctl` or `mount` under `sudo`. A `/mnt/...` target with `uid=0,gid=0` means an `/etc/fstab` entry is still in play, which is what the reporter hit after clearing the flag. Two lines for the same target mean the device is mounted twice and needs unmounting until `findmnt` prints nothing. `ro` in the options is the read-only mount from the earlier step, so unmount and mount again without `-o ro`. The reporter confirmed the drive mounted and all files were readable after `ntfsfix --clear-dirty`.

Sources: <https://github.com/omacom/omarchy/issues/8725> · <https://archlinux.org/packages/extra/x86_64/ntfsprogs/> · <https://wiki.archlinux.org/title/NTFS> · <https://raw.githubusercontent.com/torvalds/linux/master/fs/ntfs3/super.c> · <https://storaged.org/doc/udisks2-api/latest/gdbus-org.freedesktop.UDisks2.Filesystem.html>

---

## Fix a scanner (or USB printer) the tools can see but cannot open

`scanner-not-detected-scanimage` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `cups`, `endeavouros`, `manjaro`, `omarchy`, `printing`, `sane`, `scanner`, `udev`, `usb`

**Symptom.** `scanimage -L` prints `No scanners were identified.` even though `lsusb` shows the device. Running `sudo scanimage -L` finds it, so it works as root. The same pattern hits USB printers: CUPS lists the device but the backend fails to open it.

**Cause.** Either the scanner is a modern driverless (eSCL/AirScan/WSD) device that needs `sane-airscan` (plus `ipp-usb` when connected by USB), or it is a permissions problem: the USB device node is only opened by root unless a udev rule tags it `libsane_matched` and gives it `MODE="664", GROUP="scanner"`, and unless your user is in the `scanner` group. Arch ships those rules in `/usr/lib/udev/rules.d/65-sane.rules`, generated from SANE's device database — a device missing from that database gets no rule at all.

> **Audit corrected this record.** The diagnosis and the driverless half are right (`sane`, `sane-airscan`, `ipp-usb` all exist; `ipp-usb.service` for USB models; `sane-find-scanner`; explicit `--device` when a webcam shadows the scanner). The permissions half is wrong in two ways, both verified against the packaging: Arch's `sane` generates `/usr/lib/udev/rules.d/65-sane.rules` from `sane-desc -m udev+hwdb` (the path the record cites is correct), whose access rule is `ENV{libsane_matched}=="yes", MODE="664", GROUP="scanner"` — so the group for scanners is `scanner`, not `lp`, and a hand-written rule using `GROUP="lp"` does not match how the shipped rules grant access. And the closing note that 'the `scanner` and `lp` groups are deprecated under systemd — do not add your user to them' is false: `scanner` (gid 96) is created by the `filesystem` package precisely for this, and membership in it is the intended way to open the device on Arch. Following that note leaves the user with no working access path.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Driverless scanners, unchanged:

```bash
sudo pacman -S sane sane-airscan ipp-usb
sudo systemctl enable --now ipp-usb.service   # USB-connected models only
scanimage -L
```

If `sudo scanimage -L` works but the unprivileged one does not, it is permissions. First join the group the shipped rules actually use, then log out and back in:

```bash
sudo usermod -aG scanner $USER
id -nG   # should list: scanner
```

If the device still is not matched, check whether it appears in `/usr/lib/udev/rules.d/65-sane.rules` (`lsusb` for the IDs, `sudo sane-find-scanner`), and if not, add `/etc/udev/rules.d/65-sane-missing-scanner.rules` using the **same group the shipped rules use**:

```
ATTRS{idVendor}=="03f0", ATTRS{idProduct}=="2504", MODE="0664", GROUP="scanner", ENV{libsane_matched}="yes"
```

Then `sudo udevadm control --reload-rules && sudo udevadm trigger` and re-plug. Verify with `scanimage -L` as your normal user and `ls -l /dev/bus/usb/<bus>/<dev>` showing group `scanner`. (For a *USB printer* the equivalent group is `lp`; do not mix the two.)

**Verify.** `scanimage -L` as your normal user lists the device, `ls -l /dev/bus/usb/<bus>/<dev>` shows group `lp` mode `0664`, and `scanimage --format=png --output-file test.png --progress` produces a real image.

Sources: <https://wiki.archlinux.org/title/SANE> · <https://wiki.archlinux.org/title/CUPS/Troubleshooting>

---

## Fix Grok Bot installed from Install > AI failing with HTTP 404 (omarchy/grok-bot 0.18.0 is too old)

`grok-bot-0-18-0-404-needs-package-bump` · severity: **medium** · frequency: **rare** · applies to: `grok-bot`, `omarchy`

**Symptom.** Grok Bot installed through the Omarchy menu (Install > AI > Grok Bot, which runs `omarchy-pkg-add grok-bot`) does not work. The 0.18.0 client's local daemon restart-loops and every request to Grok Bot's computer API returns `http_404`. There is no in-app updater on Linux. Reported on Omarchy 4.0.0-1 on 2026-08-24.

**Cause.** Named by the reporter and confirmed by the merged package bump. Cursor floors the Grok Bot desktop computer API at client 0.24.0 (`backend_min_version`) and changed the noVNC token scheme at 0.20.0, so the 0.18.0 build in the Omarchy package repository can no longer talk to the service. The Omarchy menu entry is correct. The package it installs was stale.

> **Audit corrected this record.** I read issue omacom/omarchy#8070 in full with comments and both cited pull requests. The issue supports the cause. Its body states Omarchy 4.0.0-1, names `https://pkgs.omarchy.org/stable/x86_64/grok-bot-0.18.0-1-x86_64.pkg.tar.zst`, and says 0.18.0 404s against the computer API because `backend_min_version` is 0.24.0 and Linux has no in-app updater. The reporter's first attempt, omarchy#8075, switched the menu to the AUR and he closed it himself as the wrong layer, which is exactly the record's line that the menu entry is correct and the package was stale. The issue itself is closed as NOT_PLANNED with the comment `Opened in error. Closing.`, so the record's note that nobody reported back in the thread is right. On the pull requests the record has the merge state right where the issue body does not: omarchy-pkgs#198 `Update grok-bot to 0.24.0` merged on 2026-08-24T19:52:10Z, while #201, the one the issue body links as the fix, is closed unmerged. The whole cause paragraph is a restatement of #198's body, including the 0.24.0 floor, the noVNC token change at 0.20.0 and `Unknown platform: linux-x64-user`, and its diff confirms the packaging claims: `pkgver` 0.18.0 to 0.24.0, `install -Dm755 "${srcdir}/grok-bot.sh" "${pkgdir}/usr/bin/grok-bot"` with `ln -s grok-bot "${pkgdir}/usr/bin/sand"`, and `grok-bot.desktop` installed. Both are still in the PKGBUILD on `master` today. Note the cause and the test evidence come from one person, the reporter and PR author, not from an independent confirmation.

Two things in the fix are wrong as of 2026-09-11. First the version. I fetched `https://pkgs.omarchy.org/stable/x86_64/omarchy.db` and it carries `grok-bot-0.29.0-1`, not the `0.24.0-1` the record reports, and the PKGBUILD on `master` is `pkgver=0.29.0`. The 0.24.0 figure was a dated observation and reads as a current claim on a published page. Second the plain Arch branch is false. The AUR does carry this app: `grok-bot-bin` and `grokbot-linux-port-bin` are both 0.47.0-1 and maintained, and the plain `grok-bot` AUR package is orphaned, flagged out of date, and pinned at 0.20.0-1, which is below the 0.24.0 floor and therefore still broken. That last one is a trap the record sends a reader straight into by saying the package exists only in the Omarchy repository. I rewrote the fix for both and added the ALPM guard and partial upgrade warnings, since the record gave a bare `omarchy update` with no note on what not to substitute.

Confirmed on this Omarchy 4.0.2-1 workstation: `/etc/pacman.conf` line 28 defines `[omarchy]` with `Server = https://pkgs.omarchy.org/stable/$arch`, so stable is the ring this machine tracks. `/usr/share/omarchy/bin/omarchy-update-system-pkgs` runs `sudo env LC_ALL=C OMARCHY_UPDATE_PACMAN=1 pacman -Syu --noconfirm`, so `omarchy update` really does sync and upgrade. The menu entry at `/usr/share/omarchy/default/omarchy/omarchy-menu.jsonc` line 235 now reads `omarchy-install-and-launch 'Grok Bot' grok-bot grok-bot` rather than calling `omarchy-pkg-add grok-bot` directly, but that wrapper `exec`s a shell running `omarchy-pkg-add grok-bot`, so the symptom's description still holds and I left it alone. I could not exercise any of this: grok-bot is not installed here, `pacman -Q grok-bot` finds nothing, I have no sudo, and I have no account to authenticate a client against the computer API, so the 404 itself and the PR's upgrade test are taken from the source.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

The fix is omarchy-pkgs PR #198, merged 2026-08-24, which repackages Grok Bot 0.24.0. The stable package repository has moved on since: `https://pkgs.omarchy.org/stable/x86_64/omarchy.db` carried `grok-bot-0.29.0-1` when fetched on 2026-09-11, and the PKGBUILD on `master` is at 0.29.0. Anything at 0.24.0 or above clears the `backend_min_version` floor, so an ordinary update is enough.

**Omarchy 4:**

```bash
omarchy update
```

That syncs and upgrades against the `[omarchy]` repository, which `/etc/pacman.conf` points at `https://pkgs.omarchy.org/stable/$arch`. Do not run `pacman -Syu` directly, because Omarchy's ALPM guard blocks it, and never `pacman -Sy grok-bot`, which is a partial upgrade. To take just this package now, sync and upgrade in one transaction:

```bash
OMARCHY_ALLOW_DIRECT_PACMAN=1 sudo pacman -Syu grok-bot
```

If Grok Bot was never installed, or you removed it, install it through Install > AI > Grok Bot, or directly:

```bash
omarchy-pkg-add grok-bot
```

0.24.0 renamed the binary from `sand` to `grok-bot`. The package keeps `/usr/bin/sand` as a compatibility symlink and ships `grok-bot.desktop`, so launcher entries keep working. Both are still in the PKGBUILD at 0.29.0.

**Plain Arch:** the Omarchy repository is not the only source. The AUR carries maintained builds, `grok-bot-bin` and `grokbot-linux-port-bin`, both at 0.47.0-1 on 2026-09-11:

```bash
yay -S --noconfirm aur/grok-bot-bin
```

Avoid the plain `grok-bot` AUR package. It is orphaned, flagged out of date, and sits at 0.20.0-1, which is below the 0.24.0 floor, so it has the same `http_404` failure the Omarchy 0.18.0 package had. Building the official Linux .deb yourself also works. PR #198 pins `https://downloads.cursor.com/grokbot/stable/<commit>/linux/x64/Grok_Bot_<version>.deb`, and that PKGBUILD is the reference for the Wayland wrapper flags and the `sand` compatibility symlink.

**Verify.** ```bash
pacman -Q grok-bot
ls -l /usr/bin/grok-bot /usr/bin/sand
```

`pacman -Q` prints `grok-bot 0.24.0-1` or newer. The PR's own test on Omarchy/Hyprland: after `pacman -U` over a live 0.18.0, the app reported `appVersion=0.24.0`, the local daemon stayed up, and no new `http_404` appeared in its logs. Nobody in the issue thread itself reported back after the bump.

Sources: <https://github.com/omacom/omarchy/issues/8070> · <https://github.com/omacom/omarchy-pkgs/pull/198> · <https://github.com/omacom/omarchy-pkgs/pull/201> · <https://pkgs.omarchy.org/stable/x86_64/omarchy.db> · <https://github.com/omacom/omarchy/pull/8075> · <https://github.com/omacom/omarchy-pkgs/blob/master/pkgbuilds/grok-bot/PKGBUILD> · <https://aur.archlinux.org/packages/grok-bot> · <https://aur.archlinux.org/packages/grok-bot-bin> · <https://aur.archlinux.org/packages/grokbot-linux-port-bin>

---

## Omawrite's Save File dialog opens larger than the screen at scale 2 (GTK 3 file chooser sizing bug)

`omawrite-save-dialog-oversized-gtk3-double-font-scale` · severity: **medium** · frequency: **rare** · applies to: `asahi`, `gtk3`, `hyprland`, `laptop`, `omarchy`, `omawrite`, `wayland`

**Symptom.** Omarchy 4.0.1-2 on a MacBook Air M2 (Asahi), Omawrite 0.5.0-1, GTK 3.24.52, built-in 2560x1664 panel at Hyprland scale 2 (1280x832 logical). Pressing `Ctrl+S` in Omawrite opens a `Save File` window of 1231x950 logical pixels at `(342, -45)`, clipped at the top, right and bottom, so the filename field and the Cancel and Save buttons are hard to reach. `hyprctl clients` shows class `omawrite`, title `Save File`, owned by the Omawrite PID rather than `xdg-desktop-portal-gtk`. Resetting `org.gtk.Settings.FileChooser window-size` to `(-1, -1)` does not help and `GDK_SCALE=1` reproduces the same size. Reported from one machine.

**Cause.** Established by the reporter and accepted upstream. Omawrite's Qt Quick `FileDialog` runs under Omarchy's `QT_QPA_PLATFORMTHEME=gtk3`, so it creates a GTK 3 file chooser inside the Omawrite process instead of calling the portal. In GTK 3's `find_good_size_from_style()`, `gtk_style_context_get(..., "font-size", ...)` already returns the computed CSS font size in pixels, but the chooser still multiplied it by `resolution / 72` as if it were points, so the default size came out roughly one third too large. The reporter reproduced it in a standalone `GtkFileChooserDialog` without Omawrite, Qt, Hyprland or Omarchy. GTK's merge request notes the same 1203x902 result was reported upstream with `GDK_SCALE=2`.

> **Audit corrected this record.** Checked the Lua rule and the window-rule API on this machine, and the GTK claims against GitLab's API. Confirmed here: `o.window(match, rules)` is real, it is Omarchy's own helper at `/usr/share/omarchy/default/hypr/helpers.lua:142`, it merges the match table and calls `hl.window_rule`, and `float`, `center` and `size = { w, h }` are all keys Omarchy's own shipped rules use, for example `/usr/share/omarchy/default/hypr/apps/steam.lua:2` and `apps/battlenet.lua:5`. A `{ class = ..., title = ... }` match table is also shipped, at `apps/steam.lua:2`, so the rule in the fix is valid Omarchy 4 Lua rather than hyprlang or a guess. `hyprctl reload` is a documented subcommand of the installed Hyprland 0.56.2. Placing the rule at the bottom of `~/.config/hypr/hyprland.lua` matches that file's own instruction to add personal configuration below the `require` lines, so the fix's placement is right. GitLab's API confirms merge request 10311, titled "filechooser: Avoid converting CSS font size twice", state merged into target branch `gtk-3-24` at 2026-09-01T14:50:36Z with merge commit `b30343717dc9b02cf157d2ea87da585d8d518845`, whose short id is `b3034371`. Its diff removes exactly the `font_size = font_size * resolution / 72.0 + 0.5` line from `find_good_size_from_style()` in `gtk/gtkfilechooserwidget.c`, which is the cause the record states. The merge request description also confirms the record's `1203x902` with `GDK_SCALE=2` detail, which it attributes to GTK issue 771. The newest GTK 3 tag is still 3.24.52 from 2026-03-22 and `archlinux.org` still reports `gtk3 1:3.24.52-1`, matching `pacman -Q gtk3` here, so the fix section's statement that the commit has not shipped holds today, 2026-09-11. Issue 9046 is closed as resolved upstream on 2026-09-01 and its body matches the symptom field line for line, including the `(342, -45)` position, the `1231x950` size, the reset of `org.gtk.Settings.FileChooser window-size` not helping, and `GDK_SCALE=1` reproducing. One thing is wrong. The verify block runs `grep -A6 'title: Save File'`, and `hyprctl clients` on this machine prints `size:` five lines before `title:`, so trailing context shows `initialClass`, `initialTitle`, `pid` and `xwayland` and never shows the size the check is looking for. Replaced with `-B6`, which covers `at:` through `title:`. Not exercised: I have no Asahi MacBook and no scale 2 display here, `omawrite 0.5.0-1` is installed but I did not open its Save dialog or apply the rule, so the measured 1231x950 and 875x600 numbers and the patched 908x707 come from the reporter and the merge request, not from this machine.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Fixed upstream in GTK merge request !10311, merged into the `gtk-3-24` branch on 2026-09-01 as commit `b3034371`. That commit is not in gtk3 3.24.52, which is what Arch ships as of 2026-09-07 (`gtk3 1:3.24.52-1`), so the fix arrives with the next gtk3 release through the normal update:

```bash
omarchy update
pacman -Q gtk3        # needs a version newer than 1:3.24.52-1
```

Until then, the reporter's Hyprland rule constrains only Omawrite's `Save File` window. It was verified on the one machine above and the size is chosen for that display, so adjust it for yours:

```lua
-- ~/.config/hypr/hyprland.lua, below the require lines
o.window(
  { class = "^omawrite$", title = "^Save File$" },
  { float = true, center = true, size = { 875, 600 } }
)
```

```bash
hyprctl reload
```

**Verify.** Open Omawrite, press `Ctrl+S`, then:

```bash
hyprctl clients | grep -B6 'title: Save File'    # size within the monitor's logical resolution
```

The context has to be taken before the match, not after. `hyprctl clients` prints `size:` five lines above `title:`, so `-A6` shows `initialClass`, `pid` and the rest and never shows the size. On the reporter's display the rule gave 875x600 at `(203, 130)`, and the patched GTK gave 908x707 with no rule.

Sources: <https://github.com/omacom/omarchy/issues/9046> · <https://gitlab.gnome.org/GNOME/gtk/-/merge_requests/10311> · <https://gitlab.gnome.org/GNOME/gtk/-/commit/b3034371> · <https://archlinux.org/packages/extra/x86_64/gtk3/>

---

## Fix emoji rendering as empty boxes or black-and-white outlines

`emoji-render-as-boxes-tofu` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `fontconfig`, `fonts`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Emoji show up as empty rectangles (tofu), question marks in boxes, or monochrome outlines in Chrome, my terminal and Waybar — while they render fine on my phone. Sometimes CJK text renders in the wrong (Chinese vs Japanese) glyphs too.

**Cause.** No emoji font in a supported bitmap/color format is installed, or one is installed but is not in the fontconfig fallback chain for the family the app requested. Qt apps in particular only load the first 255 fonts, so the emoji font must be an explicit preferred fallback.

> **Audit corrected this record.** The packages (`noto-fonts`, `noto-fonts-emoji`, `noto-fonts-cjk`, `ttf-nerd-fonts-symbols`), `fc-cache -fv` and the `fc-match emoji` verification are all correct, and the generic fontconfig `<prefer>` snippet is standard Arch advice. But the Omarchy guidance understates the damage and the fix collides with what Omarchy ships: `omarchy-font-set` does not 'fight' `~/.config/fontconfig/fonts.conf`, it **overwrites the whole file** (`cat > "$HOME/.config/fontconfig/fonts.conf"`), so a single `omarchy font set` deletes everything the record told the user to write. Omarchy 4 also already ships emoji fallback (`50-omarchy.conf` gives `sans-serif`, `serif` and `monospace` an `<accept>` of `Noto Color Emoji`) and `noto-fonts-emoji` in its base packages, and it `assign`s Liberation Sans/Serif and JetBrainsMono Nerd Font with `binding="strong"` — which beats the record's `<prefer>` aliases, so the snippet would also not do what the reader expects there. The 'Qt only loads the first 255 fonts' claim in the cause is folklore I could not verify.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** On Omarchy, `omarchy font set` rewrites the monospace redirect and will fight a hand-written `~/.config/fontconfig/fonts.conf`. Prefer changing the font through the Omarchy menu, or expect to reapply your fontconfig after using it.

**Fix.**

Install the fonts as written:

```bash
sudo pacman -S noto-fonts noto-fonts-emoji noto-fonts-cjk ttf-nerd-fonts-symbols
fc-cache -fv
```

On most systems that alone fixes tofu, because fontconfig's shipped generic rules already fall back to Noto Color Emoji — check with `fc-match emoji` before editing anything.

If you do need explicit fallbacks, write them as a **drop-in**, not as `fonts.conf`:

```bash
mkdir -p ~/.config/fontconfig/conf.d
# ~/.config/fontconfig/conf.d/99-emoji.conf  — same <alias>/<prefer> blocks as before
fc-cache -fv
```

This matters most on Omarchy: `omarchy font set` rewrites `~/.config/fontconfig/fonts.conf` from scratch, so anything you put in that file is lost the next time you change fonts, whereas `conf.d/` drop-ins survive. Omarchy 4 also already ships emoji fallback in its packaged `50-omarchy.conf` and installs `noto-fonts-emoji` by default, so on Quattro check `fc-match emoji` first and change the monospace family with `omarchy font set "<family>"` rather than by hand.

**Verify.** `fc-match emoji` returns `NotoColorEmoji.ttf`, and `fc-list | grep -i emoji` shows the font. Echo an emoji in your terminal and it renders in color.

Sources: <https://wiki.archlinux.org/title/Fonts> · <https://wiki.archlinux.org/title/Font_configuration>

---

## Fix Flatpak apps that ignore the system GTK theme

`flatpak-apps-ignore-system-gtk-theme` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `flatpak`, `gtk`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Every native app follows my dark theme, but Flatpak apps (Spotify, Bottles, Obsidian, Zen...) launch in bright white Adwaita light. Changing the Omarchy theme or running `gsettings set org.gnome.desktop.interface gtk-theme ...` does nothing for them.

**Cause.** Flatpak apps run in a sandbox that only sees themes inside their runtime, not `/usr/share/themes` or `~/.themes` on the host. Flatpak's own documentation acknowledges there is no ideal way to apply host themes; the app also has no read access to the host theme directory by default.

> **Audit corrected this record.** The sandbox explanation, the `/usr` reserved-path note, the `flatpak override`/`--reset` syntax and `stylepak-git` (present in the AUR, last updated 2025) are all correct. The defect is Option 1, presented as the 'cleanest' fix for GTK apps: `org.kde.KStyle.Adwaita` is a **Qt** KStyle extension and does nothing for GTK apps (Spotify, Obsidian, Zen and the other examples). The GTK equivalent is the `org.gtk.Gtk3theme.*` runtime extension family. Also worth stating: GTK4/libadwaita apps ignore `GTK_THEME` and host GTK themes entirely, so Option 2 will not darken them.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Option 1 (cleanest, GTK apps) — install the theme as a GTK runtime extension, not the Qt KStyle:

```bash
flatpak install flathub org.gtk.Gtk3theme.Adwaita-dark
# (search for others: flatpak search org.gtk.Gtk3theme)
```

Use `flatpak install flathub org.kde.KStyle.Adwaita` only for Qt/KDE Flatpaks. Option 2 (expose host themes + force by env var) and Option 3 (`stylepak-git`), and the cursor overrides, are correct as written. Caveat to add: GTK4/libadwaita apps do not read host GTK themes or `GTK_THEME`; they follow `org.gnome.desktop.interface color-scheme`, so for those set `flatpak override --user --env=GTK_THEME=` (unset) and rely on the portal's dark-preference setting instead.

**Verify.** Relaunch the app; it renders dark and the cursor matches the desktop. `flatpak override --user --show <app-id>` prints the overrides you set.

Sources: <https://wiki.archlinux.org/title/Flatpak> · <https://wiki.archlinux.org/title/GTK>

---

## Make the SSH agent visible to GUI apps in a Wayland session

`ssh-agent-not-seen-by-gui-apps` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `flatpak`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** `git push` works in the terminal but the same repo in VS Code, a JetBrains IDE, or a Flatpak Git client asks for the key passphrase every time or fails with `Permission denied (publickey)`. `ssh-add -l` in a terminal lists the key, but a shell spawned from the GUI app says `Could not open a connection to your authentication agent`. Every new terminal also starts its own `ssh-agent` process (`pgrep -c ssh-agent` climbs).

**Cause.** Applications and units started by the systemd user manager do not read `~/.bashrc`, so an agent started there, and the `SSH_AUTH_SOCK` it prints, is invisible to them. On Omarchy 4 the session itself is a user unit: Hyprland runs as `wayland-wm@hyprland.desktop.service` under uwsm, so every GUI app it launches inherits the user manager's environment rather than an interactive shell's. Omarchy's `default/hypr/autostart.lua` then runs `systemctl --user import-environment` and `dbus-update-activation-environment --systemd --all` exactly once, at `hyprland.start`, so a variable exported after that moment never reaches anything launched through a systemd user scope and apps already running keep the old value. The fix is to run one agent as a user unit and put `SSH_AUTH_SOCK` where the user manager sees it before the session starts, then log out and back in, rather than only where interactive shells see it.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, openssh 10.5p1-1, systemd 261.2-1, uwsm 0.26.7-1) and found one hard defect that makes the fix not work as written. Confirmed on this machine: `~/.config/environment.d/*.conf` does NOT expand `%t`. Running the real generator against a throwaway config under /tmp, `/usr/lib/systemd/user-environment-generators/30-systemd-environment-d-generator` emitted `A_PCT_T=%t/ssh-agent.socket` verbatim while `B_XDG=${XDG_RUNTIME_DIR}/ssh-agent.socket` expanded to `/run/user/1000/ssh-agent.socket`. `man 5 environment.d` (systemd 261.2-1) documents only `$VAR`, `${VAR}`, `${FOO:-D}`, `${FOO:+A}` and `$$`, and says 'No other elements of shell syntax are supported'. `%t` is a unit-file specifier, correct in `ssh-agent.socket`'s `ListenStream=%t/ssh-agent.socket` and wrong in environment.d, so the record's `printf 'SSH_AUTH_SOCK=%%t/ssh-agent.socket\n'` writes a path nothing can connect to, and its parenthetical '(`%t` expands to `$XDG_RUNTIME_DIR`.)' is false for that file. The previous audit note praised the escaping and missed the specifier. Also confirmed on this machine: the record is not noise, because Omarchy 4 sets up no agent at all. `grep -rniI 'ssh-agent|SSH_AUTH_SOCK|askpass' /usr/share/omarchy` returns nothing, `systemctl --user show-environment` has no `SSH_AUTH_SOCK`, `pgrep -c ssh-agent` is 0, and `gcr-ssh-agent.socket` is `disabled` and `inactive` even though `gnome-keyring 1:50.0-1` is in `/usr/share/omarchy/install/omarchy-base.packages` and `pam_gnome_keyring.so auto_start` is in `/etc/pam.d/sddm`. `gnome-keyring-daemon` runs here with `--components=pkcs11,secrets` and no ssh component, matching https://wiki.archlinux.org/title/GNOME/Keyring which records the move into gcr-4. Second correction, to the Omarchy branch: the record's `~/.config/uwsm/env` claim is sourced to `raw.githubusercontent.com/basecamp/omarchy/master/config/uwsm/env`, which still returns 200 but is the Omarchy 3 tree (it exports `OMARCHY_PATH=$HOME/.local/share/omarchy`), and `config/uwsm/env` is a 404 in `omacom/omarchy` at `ref=quattro`. On Omarchy 4 the shipped file is `/usr/share/uwsm/env.d/10-omarchy` (owned by omarchy-settings 4.0.2-1) and its own comment names `~/.config/uwsm/env.d/*` as the preferred user override. `~/.config/uwsm/` does not exist on this machine, so the audit note's 'Omarchy's ~/.config/uwsm/env is confirmed to exist' is wrong for Omarchy 4. The path still works, because the uwsm README sources `uwsm/env` and `uwsm/env.d/*` from `${XDG_CONFIG_HOME}`, so I kept it as an alternative under the name Omarchy documents. That README also disproves the record's reason for needing two files: uwsm adds the difference those files make to 'activation environment of systemd user manager and D-Bus', so `uwsm/env` does reach user units in a uwsm session. The environment.d file alone is sufficient, which I proved end to end: `~/.config/environment.d/omarchy-firefox-wayland.conf` contains `MOZ_ENABLE_WAYLAND=1`, that appears in `systemctl --user show-environment`, and a shell inside an app in this session sees `MOZ_ENABLE_WAYLAND=1`. Third correction, to the askpass step: `/usr/lib/gcr4-ssh-askpass` and `/usr/lib/gcr-ssh-askpass` are already installed here (gcr-4 4.4.0.1-1, gcr 3.41.2-2) but are internal helpers, not general askpass programs. `strings /usr/lib/gcr4-ssh-askpass` contains `GCR_SSH_ASKPASS_SOCKET` and `gcr4-ssh-askpass: this program is not meant to be run directly`, so the fix now warns against them instead of recommending them. The record's seahorse path survives: `seahorse 1:47.0.1-6` ships `usr/lib/seahorse/ssh-askpass` per the Arch package file list, though seahorse is not installed here so I did not exercise the dialog. Everything else held. `openssh 10.5p1-1` ships `/usr/lib/systemd/user/ssh-agent.service` and `ssh-agent.socket`, the socket listens on `%t/ssh-agent.socket`, the service has `Also=ssh-agent.socket` so `enable --now ssh-agent.service` covers both, and `man ssh-agent` on this machine documents the socket-activation mode used when `-D` is given with no `-a`. https://wiki.archlinux.org/title/SSH_keys supports the 9.4p1-3 floor, `$XDG_RUNTIME_DIR/ssh-agent.socket`, `AddKeysToAgent yes` (also confirmed in `man ssh_config` here) and the whole forwarding hazard including the literal `The agent has no identities` and the `if [[ -z "${SSH_CONNECTION}" ]]` guard, so the danger's substance is sourced. I sharpened the danger to scope the rc-file hazard correctly, since environment.d does not leak into an ssh session, and to name the verified `ExecStartPost=-/usr/bin/systemctl --user set-environment SSH_AUTH_SOCK=%t/gcr/ssh` in `gcr-ssh-agent.socket` as the concrete way two agents fight. https://wiki.archlinux.org/title/Systemd/User supports environment.d as the per-user mechanism. `--socket=ssh-auth` appears in the flatpak sandbox-permissions documentation I retrieved, but flatpak is not installed here so the override was not exercised. NOT exercised at all: enabling or starting any unit, adding a key to an agent, a log out and back in, a Flatpak client, and the seahorse dialog. I left severity `low` and frequency `very-common` alone, since the consequence is repeated passphrase prompts rather than data loss, and this is a common first-week complaint.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not set `SSH_AUTH_SOCK` in a shell rc file if you use agent forwarding. On a machine you SSH *into*, a locally set value overrides the forwarded socket and `ssh-add -l` on the remote reports `The agent has no identities`. Guard it with `if [[ -z "$SSH_CONNECTION" ]]` if you must use a shell rc file. `~/.config/environment.d/` does not have this problem, because an sshd session's environment comes from sshd and PAM and not from the systemd user manager. Running both `ssh-agent.service` and `gcr-ssh-agent.socket` leaves you guessing which agent holds which key, and they actively fight: `gcr-ssh-agent.socket` runs `systemctl --user set-environment SSH_AUTH_SOCK=%t/gcr/ssh` in its `ExecStartPost`, so it wins for everything started after it while your own value still applies to everything started before.

**Fix.**

Use the `ssh-agent.service` user unit shipped with `openssh` (in Arch's package since 9.4p1-3). It is socket activated, and `ssh-agent.socket` fixes the path at `$XDG_RUNTIME_DIR/ssh-agent.socket`:

```bash
systemctl --user enable --now ssh-agent.service   # Also= pulls in ssh-agent.socket
systemctl --user status ssh-agent.service
```

Set `SSH_AUTH_SOCK` in `~/.config/environment.d/`, which the systemd user manager reads through its environment generator before it starts anything, including the compositor:

```bash
mkdir -p ~/.config/environment.d
cat > ~/.config/environment.d/50-ssh-agent.conf <<'EOF'
SSH_AUTH_SOCK=${XDG_RUNTIME_DIR}/ssh-agent.socket
EOF
```

Write `${XDG_RUNTIME_DIR}`, never `%t`. `%t` is a unit-file specifier. `environment.d` expands only `$VAR` and `${VAR}` and supports no other shell syntax, so `SSH_AUTH_SOCK=%t/ssh-agent.socket` is stored verbatim as the string `%t/ssh-agent.socket` and nothing can connect to it. `%t` is correct inside a unit file, which is why `ssh-agent.socket` itself uses `ListenStream=%t/ssh-agent.socket`.

On Omarchy 4 that one file is enough for the whole graphical session, because Hyprland runs as the user unit `wayland-wm@hyprland.desktop.service` and inherits the user manager's environment. Omarchy uses the same mechanism itself for `/usr/lib/environment.d/10-omarchy-fcitx.conf`.

If you would rather use uwsm's own hook, Omarchy 4's `/usr/share/uwsm/env.d/10-omarchy` names `~/.config/uwsm/env.d/*` as the user override point, and uwsm adds the difference those files make to the activation environment of the systemd user manager and of D-Bus:

```bash
mkdir -p ~/.config/uwsm/env.d
echo 'export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"' > ~/.config/uwsm/env.d/50-ssh-agent
```

Pick one of the two files. Then log out and back in, because Omarchy's `/usr/share/omarchy/default/hypr/autostart.lua` runs `systemctl --user import-environment` and `dbus-update-activation-environment --systemd --all` once at `hyprland.start`, so a value exported after that point reaches nothing and apps already running keep the old one. Confirm:

```bash
systemctl --user show-environment | grep SSH_AUTH_SOCK
ssh-add -l
```

The value must be an absolute path such as `/run/user/1000/ssh-agent.socket`. A literal `%t/...` there is the mistake above.

Have keys added on first use instead of by hand:

```
# ~/.ssh/config
AddKeysToAgent yes
```

A passphrase prompt still needs a GUI askpass in a Wayland session, and `seahorse` provides one at `/usr/lib/seahorse/ssh-askpass`:

```bash
sudo pacman -S --needed seahorse
printf 'SSH_ASKPASS=/usr/lib/seahorse/ssh-askpass\nSSH_ASKPASS_REQUIRE=prefer\n' >> ~/.config/environment.d/50-ssh-agent.conf
```

Do not point `SSH_ASKPASS` at `/usr/lib/gcr-ssh-askpass` or `/usr/lib/gcr4-ssh-askpass` even though Omarchy 4 already installs `gcr` and `gcr-4`. Those are internal helpers of `gcr-ssh-agent`: they require `GCR_SSH_ASKPASS_SOCKET` and refuse to run with `this program is not meant to be run directly`. On plain Arch, `x11-ssh-askpass` is the other option, at `/usr/lib/ssh/x11-ssh-askpass`.

Remove any `eval $(ssh-agent)` from `~/.bashrc` or `~/.zshrc`. That is what was spawning an agent per terminal.

If you would rather have gnome-keyring hold the keys, use its agent instead of openssh's and do not set `SSH_AUTH_SOCK` yourself. The ssh component moved out of `gnome-keyring-daemon` into `gcr-ssh-agent`, and Omarchy 4 installs `gnome-keyring` but leaves `gcr-ssh-agent.socket` disabled, so nothing sets the variable until you enable it:

```bash
systemctl --user enable --now gcr-ssh-agent.socket
```

The socket's own `ExecStartPost` runs `systemctl --user set-environment SSH_AUTH_SOCK=%t/gcr/ssh`, which is why you must not set the variable yourself. Run only one of the two agents.

For a Flatpak app to reach the agent at all it needs the socket forwarded:

```bash
flatpak override --user --socket=ssh-auth com.visualstudio.code
```

**Verify.** `systemctl --user show-environment | grep SSH_AUTH_SOCK` prints an absolute path such as `/run/user/1000/ssh-agent.socket` and not a literal `%t/...`, `systemctl --user is-active ssh-agent.service` reports `active`, `pgrep -c ssh-agent` is 1, and `ssh-add -l` from a shell opened *inside* the GUI app lists your key.

Sources: <https://wiki.archlinux.org/title/SSH_keys> · <https://wiki.archlinux.org/title/GNOME/Keyring> · <https://wiki.archlinux.org/title/Systemd/User> · <https://github.com/Vladimir-csp/uwsm> · <https://archlinux.org/packages/extra/x86_64/seahorse/files/> · <https://gitlab.archlinux.org/archlinux/packaging/packages/openssh/-/raw/main/PKGBUILD> · <https://docs.flatpak.org/en/latest/sandbox-permissions.html>

---

## Get clipboard sharing and window auto-resize working in a Linux VM guest

`vm-guest-no-clipboard-or-auto-resize` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `kvm`, `laptop`, `libvirt`, `manjaro`, `omarchy`, `wayland`

**Symptom.** Copy/paste between host and a QEMU/KVM guest does nothing in either direction, and resizing the virt-manager/virt-viewer window leaves the guest stuck at 1024x768 with black bars instead of following the window. Installing `spice-vdagent` in the guest did not help.

**Cause.** Clipboard and resize are two different mechanisms with different requirements. Both need the VM to have a SPICE display plus the `com.redhat.spice.0` virtio-serial channel. Resize then works in a Wayland guest through the virtio-gpu display-info/EDID update: the host sends the new size, the guest's virtio-gpu DRM driver exposes a new preferred mode, and the compositor follows it — provided the video model is virtio and the guest's monitor config does not pin a mode. Clipboard, however, is done by spice-vdagent, which is X11-only by design (upstream describes it as a per-X-session process using X selections and Xrandr). In a bare Wayland guest such as Hyprland there is no X session for it to attach to, so host/guest copy-paste does not work no matter what is installed; wl-clipboard is a local CLI tool and is unrelated to the SPICE agent.

> **Audit corrected this record.** Two hard errors. (1) The Lua is invalid: hl.monitor takes a single table with the output as a key — the 0.55 wiki's own examples are `hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 2 })` and `hl.monitor({ output = "Unknown-1", disabled = true })`. `hl.monitor("", { ... })` passes a string where the table is expected and will throw a Hyprland type error, so the reader's monitor config silently does not apply. (2) The clipboard cause is wrong: spice-vdagent has no Wayland support. Upstream's README describes it as 'a per X-session process' whose features are X-session clipboard/selection and Xrandr resolution adjustment; installing wl-clipboard does not bridge it to a Wayland compositor's clipboard, so a Hyprland guest will still have no host/guest copy-paste after following this record — which is exactly the symptom the reader arrived with ('installing spice-vdagent in the guest did not help'). The host-side XML (spice graphics, virtio video, spicevmc channel with com.redhat.spice.0), the /dev/virtio-ports check, and the 'use virt-viewer not VNC' guidance are all correct and worth keeping.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

**Fix.**

Host side is unchanged: SPICE display, virtio video model, and the spicevmc channel targeting `com.redhat.spice.0` (virt-manager: Display Spice + Add Hardware > Channel > Spice agent), and connect with `virt-viewer`/`remote-viewer` rather than a VNC client.

**Resize (works on Wayland guests).** Install the agent and daemon in the guest for the mouse/resize plumbing:

```bash
sudo pacman -S --needed spice-vdagent
sudo systemctl enable --now spice-vdagentd.service
ls -l /dev/virtio-ports/          # expect com.redhat.spice.0
```

Then leave the guest output free to change mode — note the correct Lua call shape, a single table with `output` as a key:

```lua
-- ~/.config/hypr/hyprland.lua
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })
```

A hard-coded `mode = "1920x1080@60"` pins the guest and defeats auto-resize. Check with `hyprctl monitors`. If the mode never changes, confirm the guest is on virtio-gpu (`lsmod | grep virtio_gpu`) rather than QXL — QXL resize depends on the X11 agent.

**Clipboard.** spice-vdagent cannot do this in a Wayland session; do not expect wl-clipboard to help. Pick one:
- run the guest desktop as an X11 session (or a guest DE whose XWayland setup spice-vdagent can attach to) if SPICE clipboard is the requirement;
- or use a protocol with native Wayland clipboard support instead of SPICE for that guest — e.g. RDP into the guest (gnome-remote-desktop / a wlroots-compatible RDP or VNC server with clipboard support);
- or move data over a virtiofs share or ssh rather than the clipboard.

SPICE's own note still applies: QEMU's GTK display has no supported clipboard path in Arch's `qemu-ui-gtk` build.

**Verify.** In the guest, `systemctl --user status spice-vdagent.service` is active and `/dev/virtio-ports/com.redhat.spice.0` exists. Copying text in the host pastes in the guest, and dragging the viewer window changes the resolution reported by `hyprctl monitors`.

Sources: <https://wiki.archlinux.org/title/QEMU> · <https://wiki.archlinux.org/title/Libvirt> · <https://wiki.archlinux.org/title/KVM>

---

## Make a Flatpak app actually start at login on Hyprland

`flatpak-autostart-background-portal-missing` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `endeavouros`, `flatpak`, `hyprland`, `manjaro`, `omarchy`, `wayland`

**Symptom.** A Flatpak app's own "Launch on system startup" / "Start minimized at login" setting does nothing — the toggle either flips itself back off or stays on while the app never appears after a reboot. Nextcloud, Element, Telegram and ProtonMail Bridge all behave this way, and native (pacman) builds of the same apps autostart fine.

**Cause.** That toggle asks xdg-desktop-portal for the Background portal (`org.freedesktop.impl.portal.Background`), which is what writes the autostart entry on the app's behalf. None of the backends a Hyprland box normally has implement it: `xdg-desktop-portal-hyprland`, `xdg-desktop-portal-wlr` and `xdg-desktop-portal-gtk` all lack Background (only the gnome/kde/dde/xapp backends have it). With no implementation the request never completes and no autostart file is ever created.

**Fix.**

Confirm the gap first — this should print nothing:

```bash
grep -l Background /usr/share/xdg-desktop-portal/portals/*.portal
```

Then write the autostart entry yourself. Omarchy launches the session through uwsm (`uwsm start -g -1 -e -D Hyprland hyprland.desktop`), which activates `xdg-desktop-autostart.target`, so a plain XDG autostart file is honoured:

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/com.nextcloud.desktopclient.nextcloud.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Nextcloud
Exec=flatpak run --branch=stable --arch=x86_64 com.nextcloud.desktopclient.nextcloud --background
X-GNOME-Autostart-enabled=true
EOF
```

Use the app's real id and its real background flag (`flatpak run <id> --help`). Check it was picked up:

```bash
systemctl --user list-dependencies xdg-desktop-autostart.target
```

If you would rather have systemd supervise it, use a user unit instead of an autostart file:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/nextcloud.service <<'EOF'
[Unit]
Description=Nextcloud desktop client
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart=/usr/bin/flatpak run com.nextcloud.desktopclient.nextcloud --background
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now nextcloud.service
```

Installing `xdg-desktop-portal-gnome` just to get the Background portal is not worth it — it pulls in GNOME session pieces and competes with the Hyprland backend for other interfaces.

**Verify.** Log out and back in: the app is running (`flatpak ps` lists it), or `systemctl --user status nextcloud.service` is active. `ls ~/.config/autostart/` shows your entry.

Sources: <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://wiki.hypr.land/Useful-Utilities/Systemd-start/> · <https://raw.githubusercontent.com/basecamp/omarchy/master/default/wayland-sessions/omarchy.desktop> · <https://wiki.archlinux.org/title/Flatpak>

---

## Stop journald silently dropping a chatty service's log lines

`journald-rate-limit-suppressed-messages` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** Logs from one service have holes in them. The interesting lines are simply missing, and the journal contains entries from journald itself like:

```
systemd-journald[318]: Suppressed 4079 messages from nginx.service
```

Debugging a crash is impossible because the burst right before the failure is exactly the part that was dropped. Advice written for systemd older than version 240 quotes the control group path instead of the unit name (`Suppressed 4079 messages from /system.slice/nginx.service`) and is describing the same thing.

**Cause.** journald rate-limits per service: more than `RateLimitBurst` messages inside `RateLimitIntervalSec` (10000 in 30s by default) and everything else in that window is discarded, with only a summary line kept. The count is held in five separate buckets per service, grouped by priority, so a flood of `info` lines does not on its own suppress that service's `err` lines. The effective burst is additionally scaled by how much free disk space the journal has, using the base 2 logarithm of the space available, so a nearly-full disk gets roughly the nominal limit while a disk with tens of GB free gets five times it. That is why a nearly-full disk drops far more than the nominal figure suggests.

> **Audit corrected this record.** Checked on this workstation (omarchy 4.0.2-1, systemd 261.2-1, kernel 7.1.9) and against systemd's own source and man pages. Confirmed on this machine that Omarchy 4 sets nothing for journald: `/etc/systemd/journald.conf.d/` and `/usr/lib/systemd/journald.conf.d/` do not exist, `systemctl cat systemd-journald` shows no drop-in, `/etc/systemd/journald.conf` is owned by systemd 261.2-1 with `#RateLimitIntervalSec=30s` and `#RateLimitBurst=10000` both commented, and `grep -rniE 'journal' /usr/share/omarchy/` matches only an unrelated skill document and a reserved-usernames list. So the record does not tell the reader to change something Omarchy already sets, and it needs no Omarchy-versus-Arch branch. The core mechanics all held at systemd 261: `man journald.conf` here still says rate limiting is per-service, "Defaults to 10000 messages in 30s", "To turn off any kind of rate limiting, set either value to 0", and that the effective limit is multiplied by a base 2 logarithm factor with the table topping the excerpt out at 1 TB, and that `LogRateLimitIntervalSec=`/`LogRateLimitBurst=` in `systemd.exec(5)` override it. Source agrees: `src/journal/journald-rate-limit.c` has `if (rl_interval == 0 || rl_burst == 0) return 1;` and `burst_modulate()` computing `burst * (log2u64(available) - 16) / 4`, and `src/journal/journald-context.c` lines 187 to 190 seed the per-client limits from the global config and flag when a unit overrides them. Four corrections. First, the symptom quoted a message format that systemd has not produced since version 240: `src/journal/journald-manager.c` line 1294 logs "Suppressed %i messages from %s" with `c->unit`, which `journald-context.c` line 315 fills from `cg_path_get_unit()`, and that helper skips the slices and returns the bare unit name (`src/basic/cgroup-util.c`, `cg_path_get_unit_full`). So the line reads "from nginx.service", not "from /system.slice/nginx.service". I kept the old form as a labelled aside so a reader who found it in older advice recognises it. Second, the fix said "bypass the journal entirely and watch the process directly" and then gave a `journalctl -f` command, which is still the journal and still rate-limited, so it did not do what its own sentence promised. I kept the command with an honest label and added the real bypass: `man systemd.exec` states outright that "if you connect a service's stderr directly to a file via StandardOutput=file:... or a similar setting, the rate limiting will not be applied to messages written that way (but it will be enforced for messages generated via syslog(3) and similar functions)", so I gave the `append:` drop-in plus that caveat. `StandardError=` accepting the same values as `StandardOutput=` is confirmed in the same man page. Third, the fix claimed "the multiplier only reaches its maximum with tens of GB available". There is no maximum: `burst_modulate()` grows with `log2` of the free space without a ceiling, giving 4x at 4 GB, 5x at 64 GB and 6x at 1 TB, so tens of GB is only 5x and not a plateau. I replaced the clause with the actual figures. Fourth, the danger said nothing about `journalctl --vacuum-size=1G` permanently deleting archived journal files, which is a real data loss in a record whose whole subject is missing log lines. I added it. Two things I verified rather than corrected: `journalctl --rotate` before `--vacuum-size` is necessary and the record already had the order right, because `man journalctl` says vacuum "removes the oldest archived journal files" and the Arch wiki Systemd/Journal page says files "must have been rotated out and made inactive before they can be trimmed". The second is that `systemctl edit` already reloads configuration, so the record's extra `daemon-reload` was harmless, and I dropped it only because I was rewriting the block. One source-scope note without a removal: `wiki.archlinux.org/title/Systemd/Journal` resolves (HTTP 200) but says nothing about rate limiting anywhere, so it supports the drop-in directory pattern, the rotate-then-vacuum ordering and `SystemMaxUse=` but not the rate-limit claims it sat next to. `man.archlinux.org/man/journald.conf.5.en` resolves and carries the text quoted above. I left `severity: low` and `frequency: common` alone rather than manufacture a change. Not exercised: I have no sudo, so I could not write a drop-in, run `systemctl edit`, restart journald, or trigger a burst. `journalctl -b | grep -c 'Suppressed'` returns 0 on this boot, so I never saw a real suppression line on this machine and the message format finding rests on source reading, not observation.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Turning rate limiting off system-wide is how a single looping service fills the root filesystem in minutes and takes down `pacman`, Docker and anything else that needs to write. Prefer the per-unit `LogRateLimit*` override, keep `SystemMaxUse=` set, and revert the change once you have the logs you needed. `journalctl --rotate` followed by `journalctl --vacuum-size=1G` permanently deletes archived journal files, which can include the record of an earlier incident you have not read yet, so check `journalctl --disk-usage` and export anything you still need before vacuuming rather than after.

**Fix.**

See how much is being dropped and by whom:

```bash
journalctl -b | grep -i 'Suppressed .* messages from'
journalctl -b -u systemd-journald --no-pager
journalctl --disk-usage
df -h /var
```

Omarchy 4 ships no journald configuration of its own. There is no drop-in under `/etc/systemd/journald.conf.d/` or `/usr/lib/systemd/journald.conf.d/`, and `/etc/systemd/journald.conf` is systemd's stock file with every setting commented out, so what is in force are the compile time defaults. Confirm that before changing anything:

```bash
systemd-analyze cat-config systemd/journald.conf
```

Raise (or disable) the limit for the whole system with a drop-in:

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/10-ratelimit.conf >/dev/null <<'EOF'
[Journal]
RateLimitIntervalSec=30s
RateLimitBurst=50000
EOF
sudo systemctl restart systemd-journald.service
```

Better: lift it only for the one noisy unit, using its own per-service limits, so the rest of the system stays protected:

```bash
sudo systemctl edit nginx.service
```

```ini
[Service]
LogRateLimitIntervalSec=0
LogRateLimitBurst=0
```

```bash
sudo systemctl restart nginx.service
```

`LogRateLimit*` in the unit override the global `RateLimit*` for that service, and `0` for either value turns rate limiting off for it. `systemctl edit` reloads the configuration itself, so no separate `daemon-reload` is needed.

Because the effective burst is multiplied by a factor derived from the free space for the journal, free space up as well. The factor is the base 2 logarithm of the space available, so it keeps climbing rather than topping out: roughly 4 times the nominal burst at 4 GB free, 5 times at 64 GB, 6 times at 1 TB. Vacuuming only touches journal files that have already been rotated out, so rotate first:

```bash
sudo journalctl --rotate
sudo journalctl --vacuum-size=1G
```

To follow a unit live while you reproduce the problem:

```bash
sudo journalctl -u nginx.service -f -o short-precise
```

That is still the journal, so it is still subject to the rate limit. It shows the suppression line as it happens, which confirms the diagnosis, but it does not recover the dropped messages.

To take one unit out of the journal for a debugging session, send its output straight to a file. Rate limiting is not applied to what is written that way:

```bash
sudo systemctl edit nginx.service
```

```ini
[Service]
StandardOutput=append:/var/log/nginx-debug.log
StandardError=append:/var/log/nginx-debug.log
```

```bash
sudo systemctl restart nginx.service
tail -f /var/log/nginx-debug.log
```

That covers only what the process writes to stdout and stderr. A service that logs through `syslog(3)` or `sd_journal_send()` still goes through journald and is still rate-limited, so for those the per-unit `LogRateLimit*` override above is the only route. Remove whichever override you added once you have the logs you needed.

**Verify.** Reproduce the burst: `journalctl -b | grep -c 'Suppressed .* messages'` stays at its previous value (no new suppression lines) and the previously missing lines now appear in `journalctl -u <unit>`.

Sources: <https://man.archlinux.org/man/journald.conf.5.en> · <https://wiki.archlinux.org/title/Systemd/Journal> · <https://raw.githubusercontent.com/systemd/systemd/main/src/journal/journald-manager.c> · <https://man.archlinux.org/man/systemd.exec.5.en> · <https://raw.githubusercontent.com/systemd/systemd/main/src/journal/journald-rate-limit.c> · <https://raw.githubusercontent.com/systemd/systemd/main/src/journal/journald-context.c> · <https://raw.githubusercontent.com/systemd/systemd/main/src/basic/cgroup-util.c>

---

## Fix "cannot change locale" warnings from bash, perl and ssh

`locale-cannot-change-locale-warnings` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `containers`, `endeavouros`, `locale`, `manjaro`, `omarchy`, `ssh`

**Symptom.** Almost every command prints warnings like:

```
bash: warning: setlocale: LC_ALL: cannot change locale (en_US.UTF-8): No such file or directory
perl: warning: Setting locale failed.
perl: warning: Please check that your locale settings:
	LANGUAGE = (unset),
	LC_ALL = (unset),
	LANG = "en_US.UTF-8"
    are supported and installed on your system.
```

This shows up wherever the locale named in the environment was never generated: inside a container or chroot, after `/etc/locale.conf` is pointed at a locale missing from `/etc/locale.gen`, or over SSH on a server configured with an `AcceptEnv LANG LC_*` line when the client sends a locale the server does not have.

**Cause.** The locale named in `LANG`/`LC_*` has not been generated. Locales must be uncommented in `/etc/locale.gen` and built with `locale-gen` before they exist. Omarchy 4's installer already does this for `en_US.UTF-8`, so a stock Omarchy machine raises this only after the locale is changed by hand, inside a container or chroot that never ran `locale-gen`, or when a locale arrives from outside the machine. SSH is one such route but it is not a default anywhere on Arch or Omarchy: `sshd` copies no client environment variables into the session unless `AcceptEnv` names them, and openssh ships no `AcceptEnv` line, so a client's forwarded `LC_*` reaches the shell only on a server that was deliberately configured to accept it.

> **Audit corrected this record.** Checked every claim against the cited Arch wiki Locale page, fetched as raw wikitext, and against this Omarchy 4.0.2-1 workstation. Confirmed on this machine: `/etc/locale.gen` line 172 already reads `en_US.UTF-8 UTF-8` uncommented, `locale -a` lists `en_US.utf8`, `/etc/locale.conf` holds `LANG=en_US.UTF-8` and is owned by no package, and `/etc/profile.d/locale.sh` from `filesystem 2025.10.12-1` does check `$XDG_CONFIG_HOME/locale.conf` then `~/.config/locale.conf` before `/etc/locale.conf`. From the source: the wiki supports the `locale-gen` step, `localectl set-locale`, the per-user override, the `unset LANG` plus `source /etc/profile.d/locale.sh` quirk including the exact note that LANG must be unset first, the `LC_CTYPE` pin for unofficial locales, and the danger almost verbatim, since LC_ALL is the only LC_* variable that cannot be set in locale.conf and is meant only for testing. The danger is right and is the mistake people actually make, so it stays unchanged. Severity `low` also stays. Two claims did not survive. The frequency is wrong: upstream `omacom/omarchy-iso` hardcodes `"sys_lang": "en_US.UTF-8"` in `configs/airootfs/root/configurator`, and its own fresh-install manifest records `/etc/locale.conf` as `LANG=en_US.UTF-8`, so a stock Omarchy 4 install cannot raise this warning for the default locale and `very-common` overstates it. `common` is the honest rating, because changing to a non-US locale by hand and working in containers both remain frequent. The SSH mechanism in the cause is also not a default: `grep -niE 'sendenv|acceptenv'` across `/etc/ssh/ssh_config`, `/etc/ssh/sshd_config`, `/etc/ssh/ssh_config.d/` and `/etc/ssh/sshd_config.d/` returns nothing on openssh 10.5p1-1, `sshd_config(5)` documents the AcceptEnv default as accepting no environment variables, `ssh_config(5)` documents the SendEnv default as sending none, and `ssh -G localhost` prints no sendenv line, so a forwarded LC_* lands only on a server explicitly configured for it. The cited wiki page never mentions ssh at all, so that sentence was never sourced. The fix's `sed -i` is a no-op on Omarchy 4 because the line is already uncommented, so the rewrite makes the reader look first and labels the Omarchy 4 and plain Arch branches. It also adds one verified Omarchy 4 detail: `/usr/share/omarchy/default/bash/envs`, from `omarchy-settings 4.0.2-1` and reached through `default/bash/rc`, mirrors locale.sh for interactive non-login shells but sources `/etc/locale.conf` only, so a per-user `~/.config/locale.conf` is ignored over a plain `ssh host`. Not exercised: I have no sudo, so I ran no `locale-gen`, no `localectl set-locale` and edited neither file, and I tested neither a real SSH session with AcceptEnv set nor a container.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Never set `LC_ALL` in `/etc/locale.conf` — it is the one LC_* variable that cannot be set there and it overrides every other category, silently breaking per-category settings. It is meant only for temporary testing.

**Fix.**

First check whether the locale already exists, because on Omarchy 4 it usually does:

```bash
locale
locale -a
grep -n '^[^#]' /etc/locale.gen
cat /etc/locale.conf
```

**Omarchy 4:** the ISO configurator hardcodes `"sys_lang": "en_US.UTF-8"` into the archinstall config, so a fresh install already carries `en_US.UTF-8 UTF-8` uncommented in `/etc/locale.gen`, `en_US.utf8` in `locale -a`, and `LANG=en_US.UTF-8` in `/etc/locale.conf`. The `sed` below is therefore a no-op on a stock machine. Nothing in the `omarchy` or `omarchy-settings` packages rewrites either file and `/etc/locale.conf` is owned by no package, so a hand edit survives `omarchy update`. If the warning names `en_US.UTF-8` on such a machine, the locale is missing from a container or chroot, not from the host.

**Plain Arch, or any locale Omarchy did not generate:** uncomment the line in `/etc/locale.gen` and build it. Confirm the exact line first, because it may already be uncommented:

```bash
grep -n 'en_US.UTF-8' /etc/locale.gen
sudo sed -i 's/^#en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
sudo locale-gen
```

`locale-gen` also reruns on every `glibc` update, so a locale left uncommented in `/etc/locale.gen` stays generated.

Set it system-wide in `/etc/locale.conf`:

```
LANG=en_US.UTF-8
```

or equivalently:

```bash
sudo localectl set-locale LANG=en_US.UTF-8
```

Apply it in the current shell without logging out (LANG must be unset first or locale.sh will not update):

```bash
unset LANG
source /etc/profile.d/locale.sh
locale
```

To override just for your user, create `~/.config/locale.conf` with the same syntax. `/etc/profile.d/locale.sh` reads it ahead of `/etc/locale.conf`, but only for login shells. On Omarchy 4 an interactive non-login shell, which is what a plain `ssh host` gets, is handled instead by `/usr/share/omarchy/default/bash/envs`, and that file sources `/etc/locale.conf` only. A per-user `~/.config/locale.conf` is ignored there, so set the system file when you need the locale over SSH. A non-interactive `ssh host command` runs neither, so `LANG` is unset and the command lands in the C locale.

If you are using a custom or unofficial locale (for example `en_XX.UTF-8`) and dead keys or compose stop working, pin `LC_CTYPE` to a supported locale in `/etc/locale.conf`:

```
LANG=en_XX.UTF-8
LC_CTYPE=en_US.UTF-8
```

If the warnings only appear over SSH, the server was configured with an `AcceptEnv` line, because openssh accepts nothing by default. Either generate the locale the client sends, or narrow `SendEnv` in the client's `~/.ssh/config`. Check both ends:

```bash
grep -rniE 'sendenv|acceptenv' /etc/ssh/ssh_config /etc/ssh/sshd_config /etc/ssh/ssh_config.d/ /etc/ssh/sshd_config.d/
```

**Verify.** `locale` prints your locale with no warnings, `locale -a | grep -i en_US` lists `en_US.utf8`, and opening a new terminal produces no setlocale messages.

Sources: <https://wiki.archlinux.org/title/Locale> · <https://github.com/omacom/omarchy-iso/blob/quattro/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/quattro/manifests/fresh-4-semantic.json>

---

## Debug a systemd timer that never fires

`user-timer-oncalendar-never-fires` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** A timer is "enabled" but the job never runs. `systemctl --user list-timers` shows `NEXT` as `n/a` or `-`, or `LAST` never advances. Sometimes `systemctl --user enable foo.timer` was run and nothing happened at all until the next login, or the `OnCalendar=` expression turns out to mean something completely different from what was intended.

**Cause.** Four traps, and the first three are about how the timer is installed. (1) `systemctl enable` only creates the symlink. It does not start the timer, so nothing arms until the next boot or login, and `--now` does both. (2) A timer with no `WantedBy=timers.target` in `[Install]` cannot be enabled into anything. (3) `OnCalendar=` syntax is easy to get subtly wrong, and a malformed expression is logged and ignored, leaving the timer loaded with no trigger at all. (4) A timer built only from monotonic directives (`OnBootSec=`, `OnActiveSec=`, `OnStartupSec=`, `OnUnitActiveSec=`, `OnUnitInactiveSec=`) can end up with no next elapse and show `NEXT` as `-` indefinitely, and `Persistent=true` does not rescue it, because `Persistent=` only has an effect on timers configured with `OnCalendar=`.

> **Audit corrected this record.** Checked against `man systemd.timer`, `man systemd.time`, `man systemctl` and `man environment.d` on this workstation (systemd 261.2-1, omarchy 4.0.2-1), the systemd v261 source, and https://wiki.archlinux.org/title/Systemd/Timers. Nearly all of the record held, and I exercised every command in the fix on this machine. Confirmed here: `systemd-analyze calendar "*-*-* 04:00:00"` prints `Normalized form` and `Next elapse`, `--iterations=5 "Mon..Fri 22:30"` prints five iterations, `calendar weekly` normalizes to `Mon *-*-* 00:00:00`, `*-*-* 4:00:00` normalizes to `*-*-* 04:00:00`, and `Mon,Tue *-*-01..04 12:00:00` returns Mon 2026-11-02, Tue 2026-11-03, Tue 2026-12-01 and Mon 2027-01-04, which is exactly the "1st to 4th, but only if Mon or Tue" reading the record gives. A malformed expression errors with `Failed to parse calendar specification '*-*-* 25:00:00': Invalid argument` and exit 1. The stamp-file location is right and more precise than the Arch wiki, which says `~/.local/share/systemd/`: this machine has `~/.local/share/systemd/timers/stamp-omarchy-sync-stignore.timer`, zero bytes, mtime matching `LastTriggerUSec`. `WantedBy=timers.target`, `list-timers --all` and `enable --now` are all confirmed by the wiki and by `man systemd.timer`. Three corrections. First, the `danger` is wrong about why `WakeSystem=true` fails, and this record is about user timers. `man systemd.timer` (261.2-1) says of `WakeSystem=`: "Note that this functionality requires privileges and is thus generally only available in the system service manager." Hardware support is the secondary condition, not the primary one. The quoted error string `Failed to enter waiting state: Operation not supported` is also not what systemd 261 emits: `src/core/timer.c` at tag v261 logs `Failed to add monotonic event source: %m` or `Failed to add realtime event source: %m` and then falls through to `timer_enter_dead(t, TIMER_FAILURE_RESOURCES)`, and `TIMER_FAILURE_RESOURCES` maps to the string `resources`, so `Failed with result 'resources'` is real and the first half of the quote is not. I replaced the invented string rather than guess an errno, and I did not exercise this, because creating or starting a unit was out of scope. Second, the stamp-file step gives an undocumented `rm` as the method and follows it with `restart`. `man systemd.timer` says "Use `systemctl clean --what=state ...` on the timer unit to remove the timestamp file maintained by this option from disk", and `man systemctl` adds that "the specified units must be stopped to invoke this operation", which `restart` does not satisfy in the right order. The fix now gives stop, clean, start, and keeps the hand deletion as the equivalent with the path. Third, the record frames the cause as exactly three traps and the symptom explicitly includes `NEXT` as `-`, but this machine has a live counter-example none of the three explain: `omarchy-sync-stignore.timer` in `~/.config/systemd/user/` is `enabled` and `active` with `LastTriggerUSec=Sun 2026-09-06 01:50:36 PDT`, which predates the current boot at 2026-09-06 02:27:48, and it reports `NextElapseUSecMonotonic=infinity` with an empty `NextElapseUSecRealtime` after 5 days of uptime. It uses only `OnBootSec=3min` and `OnUnitActiveSec=1h` plus `Persistent=true` with no `OnCalendar=`, the service it triggers reports an empty `ActiveEnterTimestamp`, and `man systemd.timer` states that `Persistent=` "only has an effect on timers configured with `OnCalendar=`" and that the immediate-elapse-if-in-the-past rule applies to `OnBootSec=` and `OnStartupSec=` but "is not the case for timers defined in the other directives". I added that as a fourth trap and as a `show`-based diagnostic, and I deliberately did not assert a mechanism for why this particular timer lost its anchor, because I could not pin it down without creating units. I also made the `graphical-session.target` line concrete, since it was the one unsourced assertion in the record and it is the part that is Omarchy-specific. Confirmed on this machine: Hyprland runs as the user unit `wayland-wm@hyprland.desktop.service`, `/usr/share/omarchy/default/hypr/autostart.lua` imports the session environment once at `hyprland.start`, `systemctl --user show-environment` contains `WAYLAND_DISPLAY=wayland-1` and `OMARCHY_PATH=/usr/share/omarchy` during a graphical session, and Omarchy's own shipped units use exactly the `After=graphical-session.target` plus `PartOf=` plus `ConditionEnvironment=WAYLAND_DISPLAY` pattern with absolute `/usr/bin/omarchy-*` paths (`/usr/share/omarchy/default/systemd/user/omarchy-crash-watch.service`, `omarchy-fcitx5.service`, `omarchy-sleep-lock.service`). One nuance worth recording against the standing assumption that `OMARCHY_PATH` is only in `~/.bashrc`: it also comes from `/usr/share/uwsm/env.d/10-omarchy`, which sources `/usr/share/omarchy/default/bash/env-bootstrap`, so a user unit in a live graphical session does see it. It is absent in a lingering or SSH-started user manager, which is the case the fix now covers. NOT exercised: creating, enabling, starting or reloading any unit, `systemctl clean`, `loginctl enable-linger`, `WakeSystem=true`, and any system-scope timer. Left `symptom` as written, since every shape it describes is reproducible, and left severity `low` and frequency `common` alone: the failure is a job that silently does not run, with no data loss, and it is a common self-inflicted mistake rather than a distro defect.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `WakeSystem=true` requires privileges and is generally only available in the system service manager, so a `systemctl --user` timer cannot use it at all. Even in the system manager it needs hardware that supports a timed wake, because it switches the timer to `CLOCK_BOOTTIME_ALARM` or `CLOCK_REALTIME_ALARM`. When it fails, the timer does not merely skip a run, it goes dead: the journal shows a `Failed to add monotonic event source` or `Failed to add realtime event source` warning and then `Failed with result 'resources'`. Do not add it speculatively. Enabling lingering keeps your user instance and its services running after logout. It is not a substitute for autologin, and using it that way breaks anything that needs the session: a lingering user manager has no graphical session, so `WAYLAND_DISPLAY` and `OMARCHY_PATH` are unset and a unit that needs either starts and then fails instead of waiting.

**Fix.**

See what is actually armed, including inactive timers:

```bash
systemctl --user list-timers --all
systemctl list-timers --all          # system timers
systemctl --user cat foo.timer
```

A `NEXT` of `-` means the timer has no next elapse. Read the raw value to be sure, since the table abbreviates:

```bash
systemctl --user show foo.timer -p NextElapseUSecRealtime -p NextElapseUSecMonotonic -p LastTriggerUSec
```

`NextElapseUSecMonotonic=infinity` with an empty `NextElapseUSecRealtime` is the "never fires again" state.

Make sure the timer has an install target, and give it a calendar trigger rather than only monotonic ones if it must survive a restart of your user manager:

```ini
# ~/.config/systemd/user/foo.timer
[Unit]
Description=Run foo daily

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true
RandomizedDelaySec=10m
AccuracySec=1m
Unit=foo.service

[Install]
WantedBy=timers.target
```

`Persistent=true` catches up a run missed while the machine was off, but only for `OnCalendar=` timers. On a timer built from `OnBootSec=` and `OnUnitActiveSec=` alone it does nothing.

Then enable *and* start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now foo.timer
systemctl --user list-timers foo.timer
```

Test the calendar expression before trusting it. This is the single most useful command here:

```bash
systemd-analyze calendar "*-*-* 04:00:00"
systemd-analyze calendar --iterations=5 "Mon..Fri 22:30"
systemd-analyze calendar weekly
```

It prints `Normalized form` and the next elapse times. A syntax error is reported instead, and the command exits non-zero:

```
$ systemd-analyze calendar "*-*-* 25:00:00"
Failed to parse calendar specification '*-*-* 25:00:00': Invalid argument
```

The weekday field is optional, and if you use it you must name at least one weekday, so `*-*-* 4:00:00` normalizes to `*-*-* 04:00:00` and means every day at 4am, while `Mon,Tue *-*-01..04 12:00:00` means the 1st to the 4th of the month but only if that day is a Monday or a Tuesday.

Run the service by hand to prove the job itself works, independently of scheduling:

```bash
systemctl --user start foo.service
journalctl --user -u foo.service -n 50 --no-pager
```

If the timer has drifted or thinks it already ran, clear its stamp file. `systemctl clean` is the documented way, and it requires the unit to be stopped first:

```bash
systemctl --user stop foo.timer
systemctl --user clean --what=state foo.timer
systemctl --user start foo.timer
```

The stamp is a zero-length file whose mtime is the last trigger, so you can look at it and delete it by hand if you prefer:

```bash
ls -l ~/.local/share/systemd/timers/
rm ~/.local/share/systemd/timers/stamp-foo.timer
```

(System timers keep stamps in `/var/lib/systemd/timers/`.)

Remember that a **user** timer only exists while your user instance does. It stops at logout unless you enable lingering:

```bash
loginctl enable-linger
loginctl list-users
```

If the job needs the graphical session (a notification, a screenshot, a `hyprctl` call), the service needs the session's environment, not just a trigger. On Omarchy 4 that environment arrives late: `/usr/share/omarchy/default/hypr/autostart.lua` runs `systemctl --user import-environment` and `dbus-update-activation-environment --systemd --all` at `hyprland.start`, so `WAYLAND_DISPLAY` is absent from the user manager until the session is up and absent for good in a lingering or SSH-started user manager. Copy the shape Omarchy uses for its own units, which is to order the service after the target, tie its lifetime to it, and refuse to start without the variable:

```ini
# ~/.config/systemd/user/foo.service
[Unit]
After=graphical-session.target
PartOf=graphical-session.target
ConditionEnvironment=WAYLAND_DISPLAY
```

Keep the timer itself on `timers.target`, or move it to `WantedBy=graphical-session.target` if it should exist only while you are logged in.

Calling an `omarchy` command from a user unit needs one more check. During a graphical session `OMARCHY_PATH` is in the user manager environment, because `/usr/share/uwsm/env.d/10-omarchy` sources `/usr/share/omarchy/default/bash/env-bootstrap`, and `systemctl --user show-environment | grep OMARCHY_PATH` shows it. In a lingering or SSH-started user manager it is not there, and a unit sources no profile of its own. Use the absolute path, as Omarchy's own units do:

```ini
ExecStart=/usr/bin/omarchy-something
```

If the script genuinely needs the variable, use a login shell instead:

```ini
ExecStart=/bin/bash -lc 'omarchy-something'
```

**Verify.** `systemctl --user list-timers foo.timer` shows a concrete `NEXT` timestamp and, after it passes, a `LAST` timestamp; `journalctl --user -u foo.service` shows the run.

Sources: <https://wiki.archlinux.org/title/Systemd/Timers> · <https://wiki.archlinux.org/title/Systemd/User> · <https://wiki.archlinux.org/title/Systemd> · <https://github.com/systemd/systemd/blob/v261/src/core/timer.c>

---

## Fix "Redirect USB device" being greyed out in virt-manager

`virt-manager-redirect-usb-greyed-out` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `laptop`, `libvirt`, `manjaro`, `omarchy`

**Symptom.** In virt-manager's *Virtual Machine > Redirect USB device* menu the entry is greyed out, or the dialog opens but lists no devices, so a USB stick / YubiKey / phone plugged into the host never appears in the guest.

**Cause.** Two separate things are in play and the record's symptom covers both. The menu item's *greyed out* state depends only on the console type: in virt-manager 5.1.0, `/usr/share/virt-manager/virtManager/vmwindow.py` sets the item's sensitivity from `vmwindow_viewer_can_usb_redirect()`, and `/usr/share/virt-manager/virtManager/details/viewers.py` implements that as an unconditional `return False` for the VNC viewer and `return True` for the SPICE viewer whenever the SPICE session has a USB device manager. It is not gated on the domain's hardware at all, so a SPICE domain with no USB controller and no redirector shows a *selectable* menu item and then fails at connect time because there is no free redirection channel, which is the "lists no devices or will not connect" half of the symptom. So SPICE graphics are what make the item selectable, and a USB controller plus one `<redirdev bus='usb' type='spicevmc'/>` per simultaneous device are what make the redirection actually succeed. Neither the controller nor the redirector is part of a default domain definition.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, virt-manager 5.1.0-4, virt-viewer 11.0-4, spice-gtk 0.42-5, usbredir 0.15.0-1, qemu-desktop 11.1.0-1, libvirt 1:12.6.0-1) and against both cited wiki pages, fetched in full as raw wikitext. Both pages resolve and both support the record as written, so this is a case of the sources being stale rather than misread, and three things are wrong against what is actually installed. First, the cause is misattributed: I read the greying-out logic in `/usr/share/virt-manager/virtManager/vmwindow.py` (`_console_refresh_can_usbredir` sets sensitivity from `vmwindow_viewer_can_usb_redirect()`) and in `/usr/share/virt-manager/virtManager/details/viewers.py`, where the VNC viewer's `_has_usb_redirection` is an unconditional `return False` and the SPICE viewer's returns True whenever `_spice_session` and `_usbdev_manager` exist. Nothing in that path consults the domain for a controller or a `<redirdev>`, so the missing hardware is what makes redirection fail at connect time, not what greys the item out. The record's fix does the right things but buries the SPICE requirement in the middle, where it belongs at the top. Second, the virt-viewer path is dead: `strings -a /usr/bin/remote-viewer` shows the embedded `virt-viewer-menus.ui` has only `action-menu` and `machine-menu` with no File menu at all, and USB selection is a `win.usb-device-select` action on a toolbar and header-bar button opening a dialog titled "Select USB devices for redirection". The old *File > USB device selection* wording comes straight from the Arch QEMU page and has not been true for several virt-viewer releases. Third, the danger overstates the keyboard risk on Arch: `libspice-client-glib-2.0.so.8` carries the default filter string `0x03,-1,-1,-1,0|-1,-1,-1,-1,1`, which denies USB class 0x03, so the client refuses HID devices unless that filter is overridden, and the `<hostdev>` fallback is where the warning really bites. Confirmed unchanged and left alone: `*Add Hardware > Controller > USB*` exists (`addhardware.py:234` plus `DeviceController.TYPE_USB`), `*Add Hardware > USB Redirection*` exists (`addhardware.py:318`), `_Redirect USB device` is still the menu label (`ui/vmwindow.ui:99`), the `qemu-xhci` model with `ports='8'` is valid, the `<hostdev>` block and its detach command are correct, and the `qemu:///system` note holds. I also added the Omarchy install step, because Omarchy ships none of this: `/usr/share/omarchy/install/omarchy-base.packages` matches only `qemu-user-static-binfmt`, and `/usr/share/omarchy/bin/omarchy-update-pacman-guard` aborts only on a combined sync plus sysupgrade, so publishing `pacman -S --needed` is safe. The packages that provide the feature today are `qemu-hw-usb-redirect` and `qemu-chardev-spice` (both hard dependencies of `qemu-desktop`, read from `pacman -Qi`) and `spice-gtk`, a hard dependency of `virt-manager` which itself hard-depends on `usbredir`, so no package has been renamed or dropped and nothing needs installing by hand. NOT exercised: I have no sudo and was told to leave libvirt alone, so I did not define or edit a domain, did not open a console, and did not redirect a device, and the greying-out behaviour is read from virt-manager 5.1.0 source on this machine rather than observed in the UI.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A redirected device is taken away from the host until redirection stops, so unmount a USB disk on the host before redirecting it or you risk corrupting its filesystem. spice-gtk 0.42 ships a default redirection filter of `0x03,-1,-1,-1,0|-1,-1,-1,-1,1`, which denies USB class 0x03 and allows the rest, so the client refuses a keyboard or mouse rather than redirecting it. Do not override that filter: if you do redirect your keyboard or mouse you lose the input needed to reach the viewer's own menus and undo it, and the only way back is killing the viewer. The `<hostdev>` passthrough fallback has no such filter, so nothing there stops you making that mistake.

**Fix.**

Check the **display** first, because that alone decides whether the menu item is selectable. With `sudo virsh edit <vm-name>` the graphics must be SPICE:

```xml
<graphics type='spice' autoport='yes'/>
```

VNC has no redirection channel and virt-manager greys the item out unconditionally on a VNC console.

Then shut the VM down and give it the hardware redirection needs. In virt-manager: *Add Hardware > Controller > USB* (model USB3/qemu-xhci is fine), and *Add Hardware > USB Redirection* once per concurrent device you want. Equivalently, `sudo virsh edit <vm-name>` and add inside `<devices>`:

```xml
<controller type='usb' index='0' model='qemu-xhci' ports='8'/>
<redirdev bus='usb' type='spicevmc'/>
<redirdev bus='usb' type='spicevmc'/>
```

Boot the VM, open its console, then *Virtual Machine > Redirect USB device* in virt-manager. The client paths differ by tool: in `remote-viewer` from virt-viewer 11.0 there is **no File menu**, the control is the USB button on the toolbar or header bar and it opens a dialog titled *Select USB devices for redirection*. In `spicy` from spice-gtk it is *Input > Select USB Devices for redirection*. Use the **system** connection (`qemu:///system`) if the device needs privileged access.

If redirection still will not cooperate, attach the device directly instead. This works without redirectors but requires the VM to be running and the device to be present:

```bash
lsusb
sudo virsh attach-device <vm-name> --live --file /tmp/usb.xml
```

```xml
<!-- /tmp/usb.xml -->
<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='0x1050'/>
    <product id='0x0407'/>
  </source>
</hostdev>
```

Detach with `sudo virsh detach-device <vm-name> --live --file /tmp/usb.xml` when done.

**On Omarchy 4 none of this stack is installed.** `/usr/share/omarchy/install/omarchy-base.packages` carries only `qemu-user-static-binfmt`, which runs foreign-architecture binaries and is not a VM hypervisor. Install it first. The Omarchy ALPM guard aborts only when a sync and a sysupgrade flag appear in the same transaction, so a plain install is not blocked:

```bash
sudo pacman -S --needed qemu-desktop libvirt virt-manager virt-viewer dnsmasq
sudo systemctl enable --now libvirtd.socket virtlogd.socket
sudo usermod -aG libvirt "$USER"
```

Nothing extra is needed for redirection after that. `qemu-desktop` depends on `qemu-hw-usb-redirect` and `qemu-chardev-spice`, which are the QEMU side, and `virt-manager` depends on `spice-gtk`, which itself depends on `usbredir`, which is the client side.

**Verify.** The *Redirect USB device* menu item is selectable once the console is SPICE, and picking a device succeeds rather than erroring, which needs a USB controller and a free `<redirdev>`. After ticking one, `lsusb` inside the guest shows it. A keyboard or mouse will not be listed, because spice-gtk's default filter denies USB class 0x03.

Sources: <https://wiki.archlinux.org/title/Libvirt> · <https://wiki.archlinux.org/title/QEMU>

---

## Make Files (Nautilus) 'Set as Wallpaper' change the Omarchy background

`nautilus-set-as-wallpaper-does-nothing` · severity: **low** · frequency: **occasional** · applies to: `arch`, `hyprland`, `nautilus`, `omarchy`, `omarchy-shell`, `wayland`, `xdg-desktop-portal`

**Symptom.** Right-click an image in Files (Nautilus) and choose Set as Wallpaper (Set as Background on Nautilus 50). Nothing changes. `journalctl --user` shows:

```
org.gnome.Nautilus: Failed to set wallpaper via portal:
GDBus.Error:org.freedesktop.DBus.Error.UnknownMethod:
No such interface "org.freedesktop.portal.Wallpaper"
on object at path /org/freedesktop/portal/desktop
```

Reported on Omarchy 4.0.1-1 and 4.0.2-1 with Nautilus 50.2.2-1.

**Cause.** Nautilus 50 asks the XDG desktop portal to set the wallpaper. Its binary carries `xdp_portal_set_wallpaper` and the message `Failed to set wallpaper via portal: %s`, and the menu item is labelled `Set as Background` behind the action id `view.set-as-wallpaper`. The session's portal backends are `xdg-desktop-portal-hyprland` 1.4.1 (Screenshot, ScreenCast, GlobalShortcuts, InputCapture) and `xdg-desktop-portal-gtk` 1.15.3 (FileChooser, AppChooser, Print, Notification, Inhibit, Access, Account, Email, DynamicLauncher, Lockdown, Settings), with `/usr/share/xdg-desktop-portal/hyprland-portals.conf` setting `default=hyprland;gtk`. Neither implements `org.freedesktop.portal.Wallpaper`, so the call fails before anything is written, and introspecting the live portal confirms the interface is simply absent:

```bash
gdbus introspect --session --dest org.freedesktop.portal.Desktop \
  --object-path /org/freedesktop/portal/desktop | grep Wallpaper
```

Installing `xdg-desktop-portal-gnome` would not help. That backend sets `org.gnome.desktop.background picture-uri`, which nothing in Omarchy reads, and its `gnome.portal` file is marked `UseIn=gnome` while an Omarchy session reports `XDG_CURRENT_DESKTOP=Hyprland`. Omarchy's background is the `~/.local/state/omarchy/current/background` symlink, read by the shell's background plugin at `/usr/share/omarchy/shell/plugins/background/Background.qml` and written by `omarchy-theme-bg-set`. A commenter on the issue said a real fix would need Omarchy to either implement `org.freedesktop.impl.portal.Wallpaper` and hand the file to `omarchy theme bg set`, or hide the dead menu item. Neither had landed when the issue was closed on 2026-09-02, and neither is in v4.0.3, released 2026-09-08.

> **Audit corrected this record.** Checked every claim against this workstation (omarchy 4.0.2-1, nautilus 50.2.2-1, xdg-desktop-portal 1.22.1-2, xdg-desktop-portal-hyprland 1.4.1-1, xdg-desktop-portal-gtk 1.15.3-1, nautilus-python 4.1.0-3) and against issue 8311 read in full with comments. Confirmed on this machine: the two `.portal` files in /usr/share/xdg-desktop-portal/portals/ export exactly the interface lists the record gives and neither lists Wallpaper, hyprland-portals.conf says `default=hyprland;gtk`, `gdbus introspect` on the live org.freedesktop.portal.Desktop object shows no Wallpaper interface at all, the nautilus binary contains `xdp_portal_set_wallpaper` and the exact string `Failed to set wallpaper via portal: %s`, the only matching menu label in the binary is `Set as Background`, `nautilus-python` is line 85 of /usr/share/omarchy/install/omarchy-base.packages, the installed typelib is /usr/lib/girepository-1.0/Nautilus-4.1.typelib, Omarchy's own extensions already sit in ~/.local/share/nautilus-python/extensions/ as plain files, grep over /usr/share/omarchy finds no reference to org.gnome.desktop.background or picture-uri, /usr/share/omarchy/shell/plugins/background/Background.qml line 15 reads the current/background symlink, /usr/share/omarchy/bin/omarchy-theme-bg-set writes it with `ln -nsf`, and `omarchy theme bg set` with no argument routes correctly and printed its usage. From sources: xdg-desktop-portal-gnome's src/wallpaper.c sets picture-uri on org.gnome.desktop.background, and its gnome.portal.in is UseIn=gnome while this session reports XDG_CURRENT_DESKTOP=Hyprland, so that backend would neither be selected nor help. The issue does support the symptom, the cause and the extension. Two provenance errors needed fixing. The fix said the extension was confirmed by the reporter on 4.0.1-1, but 4.0.1-1 is the version on which the bug was reproduced by a different commenter, while the extension was posted and confirmed on 4.0.2-1 and the reporter confirmed it without naming a version. The cause credited the portal recommendation to a contributor, but the commenter who made it carries no repository association. I also updated the landing status: the issue closed 2026-09-02 with neither upstream fix merged, and the v4.0.3 release notes of 2026-09-08 add no wallpaper portal and no Files extension, with no wallpaper or portal path in the quattro tree. NOT exercised: I did not open Files, click the menu item or install the extension, so the end-to-end behaviour of the new context-menu entry is taken from the thread rather than reproduced here.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Add a Files context-menu item that calls Omarchy's own command. `nautilus-python` is in Omarchy's base package set (line 85 of `/usr/share/omarchy/install/omarchy-base.packages`), so no install is needed. This extension was posted in the issue thread by a commenter who confirmed it on 4.0.2-1, and the reporter confirmed it worked before closing the issue:

```bash
mkdir -p ~/.local/share/nautilus-python/extensions
cat > ~/.local/share/nautilus-python/extensions/omarchy-background.py <<'EOF'
import gi

gi.require_version("Nautilus", "4.1")
from gi.repository import Gio, GObject, Nautilus


class OmarchyBackgroundExtension(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, files):
        if len(files) != 1:
            return []

        selected = files[0]
        location = selected.get_location()
        path = location.get_path() if location else None
        mime_type = selected.get_mime_type() or ""
        if not path or not mime_type.startswith("image/"):
            return []

        item = Nautilus.MenuItem(
            name="OmarchyBackgroundExtension::set_background",
            label="Set as Omarchy Background",
        )
        item.connect("activate", self._set_background, path)
        return [item]

    def get_background_items(self, _current_folder):
        return []

    @staticmethod
    def _set_background(_item, path):
        Gio.Subprocess.new(
            ["omarchy", "theme", "bg", "set", path],
            Gio.SubprocessFlags.NONE,
        )
EOF
nautilus -q
```

That directory is the same one Omarchy already uses for its own Files extensions, and `gi.require_version("Nautilus", "4.1")` matches the typelib `nautilus-python` installs. Check both if the item does not appear:

```bash
ls ~/.local/share/nautilus-python/extensions/
ls /usr/lib/girepository-1.0/Nautilus-*.typelib
```

Reopen Files. Right-click an image and choose **Set as Omarchy Background**. The stock GNOME item, labelled **Set as Background** on Nautilus 50, stays in the menu and still does nothing.

Without the extension, set the background from a terminal:

```bash
omarchy theme bg set /path/to/image.jpg
```

**Verify.** The background changes at once, and `readlink ~/.local/state/omarchy/current/background` points at the chosen image.

Sources: <https://github.com/omacom/omarchy/issues/8311> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3> · <https://gitlab.gnome.org/GNOME/xdg-desktop-portal-gnome/-/raw/main/src/wallpaper.c> · <https://gitlab.gnome.org/GNOME/xdg-desktop-portal-gnome/-/raw/main/data/gnome.portal.in>

---

## Enable nested virtualization so a VM can run its own VMs

`nested-virtualization-not-available-in-guest` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `laptop`, `libvirt`, `manjaro`, `omarchy`

**Symptom.** Inside a KVM guest, `grep -Eo 'vmx|svm' /proc/cpuinfo` returns nothing, `ls /dev/kvm` fails, and anything needing hardware virtualization in the guest refuses to run — WSL2 or Hyper-V in a Windows guest, the Android Studio emulator, Docker Desktop, or another nested VM. The outer host has KVM working perfectly.

**Cause.** The `nested` module parameter is already on for both vendors on any current kernel, so the usual cause is the guest's virtual CPU rather than the host module. Linux defaults it to enabled: `arch/x86/kvm/vmx/vmx.c` has `static bool __read_mostly nested = 1;` and `arch/x86/kvm/svm/svm.c` has `static int __ro_after_init nested = true;`. What blocks nesting is a guest CPU model that carries neither `vmx` nor `svm`. QEMU's default for a hand-written domain with no `<cpu>` element is `qemu64`, which has neither flag. Both `host-model` and `host-passthrough` carry the flag on a host that has it, because `host-model` is a copy of the host-model CPU definition from the host's domain capabilities XML. The module parameter is the cause only on a host where somebody turned it off or on an old kernel, and because it is mode 0444 it can be changed only by reloading the module or at boot, never through `/sys`.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, kernel 7.1.9, Intel i9-9900K, libvirt 1:12.6.0-1, virt-manager 5.1.0-4, qemu-desktop 11.1.0-1) and against both cited wiki pages, which I fetched in full as raw wikitext. Two claims are wrong on Omarchy 4 and both were confirmed locally. First, the record's premise that nesting must be "explicitly turned on with the `nested` module parameter" is false: `/sys/module/kvm_intel/parameters/nested` reads `Y` on this machine with nothing in `/etc/modprobe.d/` or `/usr/lib/modprobe.d/` setting it (I grepped both), and mainline sets the default on for both vendors (`static bool __read_mostly nested = 1;` in vmx.c, `static int __ro_after_init nested = true;` in svm.c, both fetched from git.kernel.org). Second, the record says the "host-model CPU hides them", but `virsh -c qemu:///system domcapabilities` on this host reports `<feature policy='require' name='vmx'/>` plus 74 further vmx-* features inside the `host-model` block, the libvirt documentation shipped with 12.6.0 describes host-model as a copy of that same block, and the cited Arch Libvirt page itself says host-model **or** host-passthrough at its "Nested virtualization" section. So the record sends the reader through a module reload that risks their running VMs for nothing, and steers them away from the migratable CPU mode that works. Also confirmed locally: `modinfo kvm_intel` shows `parm: nested:bool` and `modinfo kvm_amd` shows `parm: nested:int`, which is why the readback differs by vendor, so the record's single "want Y" was wrong for AMD readers. `check='partial'` is valid per `/usr/share/libvirt/schemas/cputypes.rng:31`. virt-manager 5.1.0 defaults a new x86 KVM guest to `host-passthrough` via `_get_app_default_mode` in `/usr/share/virt-manager/virtinst/domain/cpu.py` gated on `supports_safe_host_passthrough`, which this host satisfies because its `host-passthrough` mode reports `hostPassthroughMigratable` values `on` and `off`. And `*CPUs > Model*` is still the right virt-manager path. Omarchy ships none of the virtualization stack, so I added the install step: `/usr/share/omarchy/install/omarchy-base.packages` matches only `qemu-user-static-binfmt`, and `/usr/share/omarchy/bin/omarchy-update-pacman-guard` aborts only when a sync and a sysupgrade flag appear together, so `pacman -S --needed` is safe to publish. Frequency dropped to `occasional` because the module parameter is on by default and virt-manager already writes host-passthrough, leaving only hand-written or imported domains. NOT exercised: I have no sudo and was told to leave libvirt alone, so I did not unload a module, did not write a modprobe file, and did not boot a guest to see `vmx` appear inside it. The AMD readback of `1` is inferred from the int parameter type rather than read off an AMD host, since this machine is Intel despite the orchestrator saying AMD.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do not reload the KVM module unless the `nested` parameter actually reads off, which on a current kernel it does not. `modprobe -r kvm_intel` or `modprobe -r kvm_amd` fails while any VM is running, and killing VMs to force the unload loses unsaved guest state, so this is a real risk taken for no gain. The parameter is mode 0444, so it can be set only by reloading the module or at boot. `host-passthrough` copies your exact CPU to the guest, so a saved or migrated VM may refuse to resume on different hardware. `host-model` avoids that and still carries `vmx` or `svm` wherever the host has it.

**Fix.**

First **read** the host parameter, because on a current kernel nesting is already on and there is nothing to change:

```bash
cat /sys/module/kvm_intel/parameters/nested     # Intel, want Y
cat /sys/module/kvm_amd/parameters/nested       # AMD, want 1 (the AMD parameter is an int, not a bool)
```

If it already reads `Y` or `1`, skip to the guest CPU step. The parameter is mode 0444, so it cannot be flipped through `/sys`. **Only** if it reads `N` or `0`, reload the module, with every VM shut down first because the module will not unload while one is running:

```bash
sudo modprobe -r kvm_intel && sudo modprobe kvm_intel nested=1   # Intel
sudo modprobe -r kvm_amd   && sudo modprobe kvm_amd   nested=1   # AMD
```

Persist it only if you actually had to change it:

```bash
printf 'options kvm_intel nested=1\n' | sudo tee /etc/modprobe.d/kvm_intel.conf   # Intel
printf 'options kvm_amd nested=1\n'   | sudo tee /etc/modprobe.d/kvm_amd.conf     # AMD
```

The usual real fix is the **guest's CPU mode**. A domain with no `<cpu>` element gets QEMU's `qemu64`, which carries neither `vmx` nor `svm`. Set `host-model`, which keeps the domain migratable, or `host-passthrough`:

```bash
sudo virt-xml <vm-name> --edit --cpu host-model
# or
sudo virt-xml <vm-name> --edit --cpu host-passthrough
```

The same thing through `sudo virsh edit <vm-name>`:

```xml
<cpu mode='host-model' check='partial'/>
```

In virt-manager the setting is *CPUs > Model*. virt-manager 5.1.0 already picks `host-passthrough` for a new x86 KVM guest on a host whose `host-passthrough` mode reports `hostPassthroughMigratable`, so a VM it created needs no change. With bare QEMU use `-cpu host -enable-kvm`.

Confirm the host really offers the flag under the mode you picked:

```bash
virsh -c qemu:///system domcapabilities | grep "name='vmx'"   # Intel
virsh -c qemu:///system domcapabilities | grep "name='svm'"   # AMD
```

Boot the guest and check inside it:

```bash
grep -Eo 'vmx|svm' /proc/cpuinfo | sort -u
ls -l /dev/kvm
```

**On Omarchy 4 none of this stack is installed.** `/usr/share/omarchy/install/omarchy-base.packages` carries only `qemu-user-static-binfmt`, which runs foreign-architecture binaries and is not a VM hypervisor. Install the host side first. The Omarchy ALPM guard aborts only when `-S` and `-u` appear in the same transaction, so a plain install is not blocked:

```bash
sudo pacman -S --needed qemu-desktop libvirt virt-manager virt-viewer dnsmasq
sudo systemctl enable --now libvirtd.socket virtlogd.socket
sudo usermod -aG libvirt "$USER"
```

**Verify.** On the host, `cat /sys/module/kvm_intel/parameters/nested` prints `Y` on Intel or `cat /sys/module/kvm_amd/parameters/nested` prints `1` on AMD, and `virsh -c qemu:///system domcapabilities` lists `<feature policy='require' name='vmx'/>` (or the `svm` equivalent) under the CPU mode the domain uses. Inside the guest, `grep -Eo 'vmx|svm' /proc/cpuinfo` returns the flag and `/dev/kvm` exists.

Sources: <https://wiki.archlinux.org/title/KVM> · <https://wiki.archlinux.org/title/Libvirt> · <https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/plain/arch/x86/kvm/vmx/vmx.c> · <https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/plain/arch/x86/kvm/svm/svm.c> · <https://libvirt.org/formatdomain.html>

---

## Zed install ends with '[WARN] Could not determine current Omarchy theme' from omazed

`omazed-could-not-determine-current-omarchy-theme` · severity: **low** · frequency: **occasional** · applies to: `arch`, `aur`, `desktop`, `laptop`, `omarchy`, `omazed`, `zed`

**Symptom.** Installing Zed from the Omarchy menu (Install > Editor > Zed, which runs `omarchy-install-editor-zed`) installs the `zed` and `omazed` packages, then `omazed setup` prints:

```
[INFO] Setting up Omazed for user: user

[INFO] Removed old omazed hook
[SUCCESS] ✓ Omarchy hook configured
[WARN] Could not determine current Omarchy theme
```

Zed opens with its default theme and does not follow the Omarchy theme. Running `omazed setup` again gives the same warning. Reported on a fresh Omarchy Quattro (4.0.0) install.

**Cause.** Named by the person who fixed it in the thread and confirmed against the omazed source. omazed 2.0.x read the active theme from `~/.config/omarchy/current/theme`, which is where Omarchy 3 kept it. At tag v2.0.1 the script sets that path on line 5 and warns `Could not determine current Omarchy theme` on line 319 when nothing is found there. Omarchy 4 keeps state under `~/.local/state/omarchy/`, so the current theme is `~/.local/state/omarchy/current/theme` and `~/.config/omarchy/current` does not exist at all. omazed commit 302cd396 (2026-08-15), one commit behind the v2.1.0 tag, added a `detect_omarchy_version` probe that reads `omarchy-version` and otherwise tests for the Omarchy 4 state directory, then selects the matching theme path with the Omarchy 3 path kept as a fallback.

The channel is what decides the fix, and it is pacman rather than the AUR. `omarchy-install-editor-zed` runs `omarchy-pkg-add zed omazed`, and `omarchy-pkg-add` is plain `sudo pacman -S --needed`, so omazed comes from the `[omarchy]` repository. That repository carried omazed 2.0.1-1 from 2026-05-29 and only moved to 2.1.0-2 on 2026-08-15. A fresh Omarchy 4.0.0 machine installs from the offline ISO and has no synced `[omarchy]` database, so `pacman -S omazed` installs whatever the stale database names, which is the 2.0.1-1 build with the Omarchy 3 path. The AUR also carries omazed, built from the same `v$pkgver` release tarball, so an AUR installation older than 2.1.0 has the same defect.

> **Audit corrected this record.** I read issue omacom/omarchy#7325 in full with comments. It supports the mechanism but not the channel. marijn070's comment gives exactly the path pair the record cites, and Thijzert123 confirmed the fix, so the cause is well sourced. I verified the mechanism against the omazed source itself: at tag v2.0.1 `omazed` line 5 is `OMARCHY_THEME_PATH="$HOME/.config/omarchy/current/theme"` and line 319 emits `Could not determine current Omarchy theme`, and all four lines the symptom quotes appear in that file at lines 126, 111, 122 and 319. At tag v2.1.0 lines 5 to 7 add `OMARCHY_THEME_PATH_V4="$HOME/.local/state/omarchy/current/theme"` and a `detect_omarchy_version` function that reads `omarchy-version` and otherwise tests for the Omarchy 4 state directory. Commit 302cd396 is dated 2026-08-15 and `gh api repos/aps6/omazed/compare/302cd396...v2.1.0` reports behind_by 0, so it is in v2.1.0 as the record says. Confirmed on this Omarchy 4.0.2-1 workstation: `~/.local/state/omarchy/current/theme/colors.toml` and `~/.local/state/omarchy/current/theme.name` exist, `theme.name` reads `gruvbox`, and `ls ~/.config/omarchy/current` returns `No such file or directory`. The keybinding in the verify block is right, `/usr/share/omarchy/default/hypr/bindings/utilities.lua` line 18 binds `SUPER + SHIFT + CTRL + SPACE` to the theme menu. What is wrong is the fix and the last sentence of the cause. The Omarchy menu does not install omazed from the AUR. On this machine `/usr/share/omarchy/bin/omarchy-install-editor-zed` runs `omarchy-pkg-add zed omazed`, and `/usr/share/omarchy/bin/omarchy-pkg-add` is plain `sudo pacman -S --noconfirm --needed`, which can only resolve from a repository. omazed is in the `[omarchy]` repository: `pacman -Si omarchy/omazed` here reports 2.1.0-2 and the stable `omarchy.db` I fetched on 2026-09-11 carries `omazed-2.1.2-1`. Its PKGBUILD history in omacom/omarchy-pkgs shows 2.0.1-1 from 2026-05-29 and 2.1.0-2 from 2026-08-15T18:34Z, which is the real reason the reporter hit it on 2026-08-17 on a fresh 4.0.0 install: the offline ISO leaves the `[omarchy]` database unsynced, so `pacman -S omazed` installed the old 2.0.1-1. So `yay -S aur/omazed` is the wrong layer. It happens to work, because the AUR PKGBUILD builds the same v$pkgver release tarball, but it replaces a repository-tracked package with a local build for no reason. I rewrote the fix around `omarchy update`, which I confirmed runs `pacman -Syu` in `/usr/share/omarchy/bin/omarchy-update-system-pkgs` and `yay -Sua` in `omarchy-update-aur-pkgs`, so it covers both channels. I could not exercise the bug: neither `zed` nor `omazed` is installed here (`pacman -Q omazed` errors), I have no sudo, and I did not run `omazed setup` or switch themes. The version floor and the 2.0.x to 2.1.0 diff come from the upstream git tags, not from a local install.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

**Fix.**

Update omazed, then run its setup again. omazed comes from the `[omarchy]` pacman repository, so the supported path is an ordinary Omarchy update, which syncs that repository's database and pulls the fixed build:

```bash
omarchy update
pacman -Q omazed          # 2.1.0 or newer
omazed setup
```

The `[omarchy]` repository shipped the fix as 2.1.0-2 and serves 2.1.2-1 as of 2026-09-11, so any current update clears the floor.

Do not run `pacman -Syu` directly, because Omarchy's ALPM guard blocks it, and never `pacman -Sy omazed`, which is a partial upgrade. If you want just this package now rather than a full Omarchy update, sync and upgrade in one transaction:

```bash
OMARCHY_ALLOW_DIRECT_PACMAN=1 sudo pacman -Syu omazed
omazed setup
```

If you installed omazed from the AUR rather than through the Zed menu entry, `omarchy update` still covers it, because it runs `yay -Sua` for foreign packages after the pacman pass. To rebuild that one package on its own:

```bash
yay -S --noconfirm aur/omazed
omazed setup
```

Plain Arch users of omazed are not affected unless they also run Omarchy 4.

**Verify.** ```bash
omazed setup              # ends without the [WARN] line
ls ~/.local/state/omarchy/current/theme/colors.toml
```

Change the Omarchy theme (Super+Ctrl+Shift+Space) and Zed's theme changes with it.

Sources: <https://github.com/omacom/omarchy/issues/7325> · <https://github.com/aps6/omazed/commit/302cd396> · <https://aur.archlinux.org/packages/omazed> · <https://github.com/aps6/omazed/commit/302cd396be88cf508a05d97edcdc7d48eafdc299> · <https://github.com/aps6/omazed/blob/v2.0.1/omazed> · <https://github.com/aps6/omazed/blob/v2.1.0/omazed> · <https://github.com/omacom/omarchy-pkgs/blob/master/pkgbuilds/omazed/PKGBUILD> · <https://github.com/omacom/omarchy-pkgs/commits/master/pkgbuilds/omazed/PKGBUILD> · <https://pkgs.omarchy.org/stable/x86_64/omarchy.db>

---

## Restore audio tweaks that stopped working after the WirePlumber 0.5 config change

`wireplumber-lua-config-ignored-after-0-5` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Custom audio behaviour silently reverted after an update: devices suspend again after a few seconds of silence, a disabled HDMI output is back, a renamed device shows its original name, or a headset auto-switch tweak stopped applying. Audio otherwise works and `systemctl --user status wireplumber` is active, so nothing looks broken. `~/.config/wireplumber/main.lua.d/` still contains the `.lua` files that used to do it.

The journal is where it shows up. WirePlumber 0.5.1 and later log one line per stale file plus a summary, so check there first:

```bash
journalctl --user -u wireplumber -b --no-pager | grep -iE "old configuration|NOT supported"
```

```
Old configuration file detected: /home/you/.config/wireplumber/main.lua.d/51-disable-suspension.lua
Lua configuration files are NOT supported in WirePlumber 0.5. You need to port them to the new format if you want to use them.
```

If those lines are absent and a tweak still is not applying, the cause is something else and this record does not apply.

**Cause.** WirePlumber 0.5 dropped Lua as a configuration language. Fragments in `main.lua.d/`, `policy.lua.d/` and `bluetooth.lua.d/` (under `~/.config/wireplumber/`, `/etc/wireplumber/` or `/usr/share/wireplumber/`) are no longer read, so every tweak you had reverts to stock behaviour. Configuration is now SPA-JSON files in a `wireplumber.conf.d/` directory. Lua is still WirePlumber's scripting language and 72 `.lua` scripts ship in `/usr/share/wireplumber/scripts/`, so the presence of Lua on the system is not the issue. Only Lua *configuration* is gone.

The change is not silent on any currently shipping version. 0.5.0 ignored the old files with no message, and 0.5.1 added a check that walks those three directories and logs `Old configuration file detected: <path>` per file followed by `Lua configuration files are NOT supported in WirePlumber 0.5.` Anything from 0.5.1 onwards tells you, in the journal, if you look. Omarchy 4 ships `wireplumber 0.5.15-1`, so the warning is always present there.

> **Audit corrected this record.** Pinned the version claim, which is the whole record. Installed here is `wireplumber 0.5.15-1` with `pipewire 1:1.6.8-1` on omarchy 4.0.2-1. Checked upstream's own docs at tag 0.5.15 rather than a forum post: docs/rst/daemon/configuration/conf_file.rst states "the Lua configuration files are no longer supported" and adds the nuance the record omitted, that Lua remains the scripting language and is only gone for configuration. That holds, and 72 `.lua` files still ship per `pacman -Ql wireplumber`. All three worked examples verify against upstream's own shipped examples in /usr/share/doc/wireplumber/examples/wireplumber.conf.d/: alsa.conf carries `session.suspend-timeout-seconds` annotated "0 disables suspend" in the node rules block, `device.disabled` in the device rules block and `node.description` in the node block, and bluetooth.conf carries `bluetooth.autoswitch-to-headset-profile` under `wireplumber.settings`. `wpctl settings` on this machine lists that key and `wpctl settings --help` documents `-s, --save`, so the settings-versus-config split is confirmed live. The shadowing claim I nearly marked wrong and did not, which is worth recording: upstream's docs/rst/daemon/locations.rst says fragments load from all locations and merge, which reads as a contradiction, but the implementation in lib/wp/base-dirs.c at 0.5.15 removes a same-named entry already collected from a lower priority directory under the comment "so that lower priority files can be shadowed". The record and the Arch wiki are right and upstream's prose is the misleading part, so that text and its danger clause are kept. Alphanumeric ordering is also confirmed, via `conffile_iterator_item_compare` on filename. Four defects. (1) The central framing was stale by fourteen point releases. NEWS.rst for 0.5.1 records "Added a check that prints a verbose warning when old-style 0.4.x Lua configuration files are found in the system. (#611)", and src/main.c at 0.5.15 has `warn_about_deprecated_config()` emitting `wp_notice("Old configuration file detected: %s")` per file then `wp_warning("Lua configuration files are NOT supported in WirePlumber 0.5...")`. Both strings are in the installed binaries, confirmed here with `strings /usr/bin/wireplumber` and `strings /usr/lib/libwireplumber-0.5.so.0.515.0`. So "ignored without any warning" and "There is no error" are false on every version anyone runs today, and the record was withholding the one journal line that identifies the problem. Rewrote cause and symptom around it. (2) The cleanup step removed `main.lua.d` and `bluetooth.lua.d` but not `policy.lua.d`, which `warn_about_deprecated_config` also scans, so the warning would have persisted. (3) The danger's first sentence was wrong and contradicted the record's own cited source. lib/wp/conf.c catches a fragment that fails to load with `wp_warning_object` then `continue`, so the daemon starts and only that fragment is skipped. bbs 305957, cited on the record, shows exactly that: the user's fragment failed to load and they still had a working graph. The quoted string `section '...' has no value` is genuine, confirmed in lib/wp/conf.c, so it is kept. Only a broken main wireplumber.conf is fatal. (4) Omarchy content was missing and it matters here, because Omarchy already ships a fragment into the exact directory the record tells the reader to create. `~/.config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf` exists on this machine, is byte identical to `/usr/share/omarchy/config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf` per `diff`, and `pacman -Qo` reports no package owns it. On ASUS hardware `/usr/share/omarchy/install/user/hardware/asus/fix-audio-mixer.sh` copies `alsa-soft-mixer.conf` there too. Given the shadowing rule the record correctly documents, those two names must not be reused and must not be deleted, and nothing would restore them. Also confirmed `/etc/wireplumber/` does not exist here, so the old `sudo rm -rf /etc/wireplumber/main.lua.d` was a blind recursive root delete of a normally absent path, which the first auditor flagged in audit_note and nobody acted on. Replaced with a guarded listing. Set `corrected_frequency` to `occasional`. `common` dated from the April 2024 transition, but Omarchy 4 has shipped 0.5.x from the start, so no fresh Omarchy install can reach this state and only someone carrying an old dotfiles or /etc audio config onto the machine hits it. severity `low` left alone, the consequence is reverted tweaks rather than lost audio. Sources all four resolve with HTTP 200 and each supports what it is cited for, so nothing removed. bbs 294454 is the verbatim origin of the suspend-timeout example and, being dated 2024-04-01 against 0.5.0, is also where the stale no-warning claim came from. NOT exercised: I did not create any fragment, did not restart wireplumber, did not run `wpctl settings --save`, and could not make the deprecation warning appear because there are no `*.lua.d` directories on this machine. The warning's existence and wording come from the installed binaries and the 0.5.15 source, not from observing it fire.
>
> *The Cause above was rewritten on 2026-09-11 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A `.conf` fragment that fails to parse is not fatal. WirePlumber logs
`failed to open '<path>': section '...' has no value` and skips that one file, so
the daemon still starts and you still have audio. The failure mode is that your
tweak silently does not apply, which looks exactly like the problem you were
fixing, so read the journal after every change rather than trusting that audio
still works. Only a broken main `wireplumber.conf` stops WirePlumber from
starting, and following this record you write fragments, not that file.

Add one fragment at a time and restart WirePlumber after each. Reusing the exact
filename of a fragment that already exists in a lower priority directory drops
that file rather than merging with it, which silently removes the stock rules it
contained and can disable device handling you still need. On Omarchy the two
names to avoid are `bluetooth-a2dp-autoconnect.conf` and `alsa-soft-mixer.conf`
in `~/.config/wireplumber/wireplumber.conf.d/`, which Omarchy installs itself and
which no package owns, so nothing will put them back.

**Fix.**

Confirm the version and find the stale files:

```bash
wireplumber --version
ls -d ~/.config/wireplumber/*.lua.d /etc/wireplumber/*.lua.d 2>/dev/null
journalctl --user -u wireplumber -b --no-pager | grep -iE "old configuration|NOT supported"
```

Rewrite each tweak as SPA-JSON under `wireplumber.conf.d/`. On Omarchy that
directory already exists and already holds a file Omarchy put there, so list it
before you add anything:

```bash
ls -l ~/.config/wireplumber/wireplumber.conf.d/
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

Old `51-disable-suspension.lua` becomes:

```conf
# ~/.config/wireplumber/wireplumber.conf.d/51-disable-suspension.conf
monitor.alsa.rules = [
  {
    matches = [
      { node.name = "~alsa_input.*" }
      { node.name = "~alsa_output.*" }
    ]
    actions = {
      update-props = {
        session.suspend-timeout-seconds = 0
      }
    }
  }
]
```

Disabling a device (for example GPU HDMI audio). Find the stable identifier first:

```bash
wpctl status
wpctl inspect <ID>        # use device.name or node.name, never device.id
```

```conf
# ~/.config/wireplumber/wireplumber.conf.d/50-alsa-disable.conf
monitor.alsa.rules = [
  {
    matches = [
      { device.name = "alsa_card.pci-0000_08_00.4" }
    ]
    actions = {
      update-props = {
        device.disabled = true
      }
    }
  }
]
```

Match a device property and you set `device.disabled`. Match a node property and
you set `node.disabled` instead.

Renaming a device:

```conf
# ~/.config/wireplumber/wireplumber.conf.d/50-rename.conf
monitor.alsa.rules = [
  {
    matches = [
      { node.name = "alsa_output.pci-0000_00_1f.3.analog-stereo" }
    ]
    actions = {
      update-props = {
        node.description = "Laptop speakers"
      }
    }
  }
]
```

Things that used to be Lua *settings* are now runtime settings. Set them with
`wpctl` rather than a config file. `wpctl settings` with no argument lists every
settable key with its description:

```bash
wpctl settings
wpctl settings --save bluetooth.autoswitch-to-headset-profile false
```

Apply and check:

```bash
systemctl --user restart wireplumber.service
journalctl --user -u wireplumber -b --no-pager | tail -20
wpctl status
```

Then remove the dead Lua fragments so the warning stops and they stop confusing
you later. There are three directories, not two, and `policy.lua.d` is the one
usually forgotten:

```bash
rm -rf ~/.config/wireplumber/main.lua.d \
       ~/.config/wireplumber/policy.lua.d \
       ~/.config/wireplumber/bluetooth.lua.d
```

`/etc/wireplumber/` does not exist on a stock Omarchy 4 install, so there is
normally nothing to clean up system-wide. Check before reaching for `rm -rf` as
root, and look at what is in there rather than deleting the directory blind:

```bash
ls -R /etc/wireplumber/ 2>/dev/null || echo "no /etc/wireplumber, nothing to do"
```

Two file layout rules matter. Within each `wireplumber.conf.d/` directory files
load in alphanumeric order, and across directories the fragments are collected
lowest priority first (`/usr/share/wireplumber`, then `/etc/wireplumber`, then
`~/.config/wireplumber`). A fragment whose *filename* already exists in a
higher priority directory is dropped in favour of the higher priority one rather
than merged with it, so
`~/.config/wireplumber/wireplumber.conf.d/50-alsa-config.conf` replaces
`/usr/share/wireplumber/wireplumber.conf.d/50-alsa-config.conf` entirely. Give
your own files distinct names.

On Omarchy that rule has two live names to avoid. Omarchy copies
`bluetooth-a2dp-autoconnect.conf` from
`/usr/share/omarchy/config/wireplumber/wireplumber.conf.d/` into
`~/.config/wireplumber/wireplumber.conf.d/`, and on ASUS hardware
`/usr/share/omarchy/install/user/hardware/asus/fix-audio-mixer.sh` copies
`alsa-soft-mixer.conf` there too. Neither is owned by a package. Do not reuse
either name and do not delete them while cleaning up, or you drop Omarchy's A2DP
auto-connect rule or its ALSA soft-mixer rule.

**Verify.** `journalctl --user -u wireplumber -b` shows no config parse errors, `wpctl inspect <ID>` reflects your changed property, and the behaviour you wanted (no suspend, device hidden, new name) is back after a reboot.

Sources: <https://wiki.archlinux.org/title/WirePlumber> · <https://bbs.archlinux.org/viewtopic.php?id=294454> · <https://bbs.archlinux.org/viewtopic.php?id=305957> · <https://wiki.archlinux.org/title/PipeWire> · <https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/conf_file.html> · <https://pipewire.pages.freedesktop.org/wireplumber/daemon/locations.html> · <https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/migration.html> · <https://gitlab.freedesktop.org/pipewire/wireplumber/-/raw/0.5.15/lib/wp/base-dirs.c> · <https://gitlab.freedesktop.org/pipewire/wireplumber/-/raw/0.5.15/lib/wp/conf.c> · <https://gitlab.freedesktop.org/pipewire/wireplumber/-/raw/0.5.15/src/main.c>

---
