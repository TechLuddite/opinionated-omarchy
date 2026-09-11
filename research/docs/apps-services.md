# Apps, containers & services

59 problems. Sorted by severity, then by how often users hit it.

## Fix btrfs "No space left on device" while df still shows free space

`btrfs-no-space-left-with-free-space` · severity: **critical** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `snapper`

**Symptom.** Writes fail with `No space left on device` and pacman refuses to install anything, but `df -h /` shows several GB free. Deleting files barely helps.

**Cause.** Btrfs allocates disk in chunks for data and metadata separately. Once all raw space is allocated to chunks, a write can fail even though the chunks are half-empty. `df` reports file-level free space and does not account for chunk allocation or metadata, so it lies about this situation.

> ⚠️ **Risk.** A full `btrfs balance` rewrites every chunk on the filesystem — it can take hours, hammers the disk, and must not be interrupted by a hard power-off. Always start with `-dusage=10`. If the filesystem is so full that balance itself cannot allocate, free space by deleting snapshots first. Deleting snapshots is irreversible.

**Fix.**

Look at the real picture first:

```bash
sudo btrfs filesystem usage /
btrfs filesystem df /
```

If `Device allocated` is close to `Device size` while `Free (estimated)` is much larger, reclaim mostly-empty chunks by rebalancing only lightly-used ones (fast, low IO):

```bash
sudo btrfs balance start -dusage=10 -musage=10 /
sudo btrfs balance status /
```

If that is not enough, raise the threshold gradually:

```bash
sudo btrfs balance start -dusage=50 /
```

Or run a full background balance:

```bash
sudo btrfs balance start --bg /
sudo btrfs balance status /
```

On a snapshotted system, old snapshots are usually the real space consumers — delete some before rebalancing:

```bash
sudo btrfs subvolume list /
sudo snapper -c root list
sudo snapper -c root delete <number>
```

**Verify.** `sudo btrfs filesystem usage /` shows `Device allocated` meaningfully below `Device size`, and writes/`pacman -Syu` succeed again.

Sources: <https://wiki.archlinux.org/title/Btrfs> · <https://wiki.archlinux.org/title/Snapper>

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

## Reclaim a full root filesystem from journal logs and the pacman cache

`disk-full-journal-and-pacman-cache` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `pacman`, `systemd`

**Symptom.** `pacman -Syu` fails with `error: Partition /var too full` or `not enough free disk space`, and `df -h` shows `/` at 100%. I have not knowingly installed anything huge.

**Cause.** Two directories grow unbounded on Arch by default: `/var/cache/pacman/pkg/` keeps every downloaded package version forever, and `/var/log/journal/` grows until it hits its default cap (or whatever `SystemMaxUse` says, which is unset by default).

> ⚠️ **Risk.** `paccache -rk0` (keeping zero versions) removes your ability to downgrade a package offline after a bad update — keep at least one. `pacman -Qtdq | pacman -Rns -` removes anything not required by an explicitly installed package; read the list before confirming, since it can pull out things you actually use if they were originally installed as dependencies.

**Fix.**

Find out where it went:

```bash
sudo du -xh --max-depth=1 /var | sort -h | tail
journalctl --disk-usage
du -sh /var/cache/pacman/pkg
```

Trim the journal (files must be rotated before vacuum can touch them):

```bash
sudo journalctl --rotate
sudo journalctl --vacuum-size=200M
```

Cap it permanently with a drop-in at `/etc/systemd/journald.conf.d/00-journal-size.conf`:

```
[Journal]
SystemMaxUse=200M
```

then `sudo systemctl restart systemd-journald.service`.

Trim the pacman cache (keeps the 3 most recent versions of each package):

```bash
sudo pacman -S pacman-contrib
sudo paccache -r
sudo paccache -ruk0          # drop ALL cached versions of uninstalled packages
sudo systemctl enable --now paccache.timer
```

And remove orphans:

```bash
pacman -Qtdq | sudo pacman -Rns -
```

**Verify.** `df -h /` shows free space again, `journalctl --disk-usage` is under your cap, and `pacman -Syu` completes. `systemctl is-enabled paccache.timer` reports `enabled`.

Sources: <https://wiki.archlinux.org/title/Systemd/Journal> · <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/System_maintenance>

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

**Symptom.** An update broke the desktop and every guide says "boot the snapshot from the boot menu", but there are no snapshot entries — the machine uses GRUB or systemd-boot, or the root filesystem is ext4, or this is a plain Arch/EndeavourOS install rather than Omarchy. `snapper -c root list` errors with `Unknown config` or the command is not installed at all.

**Cause.** Bootable snapshot rollback is not a kernel feature — it needs btrfs subvolumes, a snapshot tool (snapper), and a bootloader integration that writes menu entries for those snapshots. Omarchy gets that from Limine plus `limine-snapper-sync`. On GRUB you need `grub-btrfs`, on rEFInd `refind-btrfs`, and on a non-btrfs root none of it applies — you need file-level backups instead.

> ⚠️ **Risk.** Converting an existing installation to a snapshot-friendly btrfs layout means moving subvolumes and reinstalling/reconfiguring the bootloader — get it wrong and the machine does not boot. In particular, if `genfstab` wrote a `subvolid=` option for `/` or `/home`, remove it or you will be unable to boot *after* restoring a snapshot. Do that work from a live ISO with a full backup already taken, never on a machine you need working in an hour. `timeshift --restore` overwrites system files in place; read the excluded/included paths in `/etc/timeshift/timeshift.json` before running it, and note that Timeshift in btrfs mode ignores the `exclude` list entirely.

**Fix.**

**Recover first, then build the net.** With no snapshot to boot, roll back the specific breakage from the pacman cache:

```bash
ls /var/cache/pacman/pkg/ | grep <package>
sudo pacman -U /var/cache/pacman/pkg/<package>-<older-version>-x86_64.pkg.tar.zst
```

If the system will not boot at all, use the Arch ISO, mount and `arch-chroot` in, and do the same from there.

**Then set up rollback properly.** Which path depends on the filesystem:

```bash
findmnt -no FSTYPE /
cat /proc/cmdline | tr ' ' '\n' | grep -E 'rootflags|subvol'
bootctl status 2>/dev/null | head -5
```

*btrfs root + GRUB* — snapshots in the GRUB menu:

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

*btrfs root + Limine* (the Omarchy arrangement, if you built the system yourself):

```bash
yay -S limine-snapper-sync
sudo pacman -S --needed snapper snap-pac
```

*Non-btrfs root (ext4, xfs)* — snapshots are not possible; use rsync-mode Timeshift, which works on any filesystem:

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
sudo snapper -c root create --description "before upgrade"
# or
sudo timeshift --create --comments "before upgrade"
```

Installing `snap-pac` makes pacman take pre/post snapshots around every transaction automatically.

Note that neither approach protects `/home` unless you configure it separately — a system rollback leaves your data as it is, which is usually what you want but is not a backup. Pair it with restic/borg for actual data backup.

**Verify.** `sudo snapper -c root list` (or `sudo timeshift --list`) shows snapshots, and — for the btrfs paths — rebooting presents a snapshot submenu in the bootloader that actually boots.

Sources: <https://wiki.archlinux.org/title/Snapper> · <https://wiki.archlinux.org/title/Timeshift> · <https://wiki.archlinux.org/title/Restic>

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

## Fix a scheduled restic/borg backup that skips runs and then fails on a stale lock

`scheduled-backup-skipped-and-repo-locked` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** A nightly backup timer set for 03:00 has not run in days on a laptop — `systemctl list-timers` shows a `NEXT` time but `LAST` is `n/a` or weeks old. When it does eventually run it fails with restic's

```
Fatal: unable to create lock in backend: repository is already locked exclusively by PID 1234 on host by user (UID 0, GID 0)
```

or borg's `Failed to create/acquire the lock`, and every subsequent run fails the same way.

**Cause.** Two compounding problems. A realtime `OnCalendar=` timer without `Persistent=true` simply skips any occurrence when the machine was off or suspended — a laptop that is closed at 03:00 never backs up. And when a run is cut short (suspend, shutdown, OOM kill, unplugged drive) the repository lock it created is never released, so every later run is refused by a lock whose owning process is long gone.

> ⚠️ **Risk.** `restic unlock --remove-all` and `borg break-lock` remove locks belonging to processes that may still be running — doing that while a backup or prune is genuinely in progress can corrupt the repository. Confirm nothing is running on any host that touches the repo first. `restic forget --prune` permanently deletes snapshots: test your retention flags with `restic forget --dry-run` before putting them in a timer. And note that an automated backup necessarily has the repository password available to root in plain text (the `--password-command` script) — protect it with `chmod 700` and remember that anyone with root can read your backups.

**Fix.**

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

`Persistent=true` triggers the job immediately after boot/resume if the last scheduled time was missed.

Stop the run being cut short in the middle, and clear a stale lock before starting — this is what the recommended wrapper script does:

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

To clear a stuck lock by hand:

```bash
# restic
restic -r /mnt/restic unlock
restic -r /mnt/restic unlock --remove-all      # only if you are certain nothing is running

# borg
borg break-lock /mnt/borgrepo
```

Check for a run in progress on any machine that shares the repository before breaking a lock:

```bash
pgrep -a -f 'restic|borg'
systemctl is-active restic-backup.service
```

If the destination is an external drive that is not always attached, gate the service on the mount rather than letting it fail:

```ini
[Unit]
RequiresMountsFor=/mnt/restic

[Service]
ExecCondition=/usr/bin/mountpoint -q /mnt/restic
```

Use a **system** timer (under `/etc/systemd/system/`) for a whole-system backup — a user timer only exists while your user instance does, unless you `loginctl enable-linger`.

**Verify.** `systemctl list-timers restic-backup.timer` shows a `LAST` timestamp that advances daily even across suspends, `restic -r /mnt/restic snapshots` lists a new snapshot per day, and `journalctl -u restic-backup.service -n 50` shows clean runs with no lock errors.

Sources: <https://wiki.archlinux.org/title/Restic> · <https://wiki.archlinux.org/title/Systemd/Timers> · <https://borgbackup.readthedocs.io/en/stable/faq.html> · <https://wiki.archlinux.org/title/Borg_backup> · <https://wiki.archlinux.org/title/Systemd/User>

---

## Stop automatic snapshots from filling the disk

`snapper-snapshots-eating-the-disk` · severity: **high** · frequency: **common** · applies to: `arch`, `btrfs`, `cachyos`, `endeavouros`, `manjaro`, `omarchy`, `snapper`, `systemd`

**Symptom.** My root filesystem keeps filling up over weeks even though I have not added files. `sudo btrfs filesystem usage /` shows most of the disk in use and `snapper -c root list` shows dozens or hundreds of snapshots going back months.

**Cause.** Snapper's default timeline keeps 10 hourly, 10 daily, 10 monthly and 10 yearly snapshots per config, and the cleanup timer is not enabled automatically. Every package update also adds a pre/post pair. On a busy root subvolume this accumulates fast, and each snapshot pins the blocks of every file that has since changed.

> ⚠️ **Risk.** Deleting snapshots is permanent — you lose the ability to roll back to those points. Do not delete the snapshot you are currently booted into. If you also run a cron daemon alongside the systemd timers you will get duplicate snapshots; enable one mechanism, not both.

**Fix.**

See what you have and how much it costs:

```bash
sudo snapper -c root list
sudo btrfs filesystem usage /
```

Delete a range you do not need (irreversible):

```bash
sudo snapper -c root delete 20-140
```

Tighten the retention policy in `/etc/snapper/configs/root`:

```
TIMELINE_MIN_AGE="1800"
TIMELINE_LIMIT_HOURLY="5"
TIMELINE_LIMIT_DAILY="7"
TIMELINE_LIMIT_WEEKLY="0"
TIMELINE_LIMIT_MONTHLY="0"
TIMELINE_LIMIT_YEARLY="0"
```

Make sure the timers that actually create and reap snapshots are running:

```bash
sudo systemctl enable --now snapper-timeline.timer snapper-cleanup.timer
systemctl list-timers 'snapper*'
```

If you do not want timeline snapshots at all (only pre/post around package updates), set in the same config:

```
TIMELINE_CREATE="no"
```

**Verify.** `sudo snapper -c root list` shows only the number of snapshots your policy allows after the cleanup timer runs, and `sudo btrfs filesystem usage /` shows free space recovered.

Sources: <https://wiki.archlinux.org/title/Snapper> · <https://wiki.archlinux.org/title/Btrfs>

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

## Fix VFIO GPU passthrough failing with "group is not viable"

`vfio-gpu-passthrough-group-not-viable` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `libvirt`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** Starting the VM with a passed-through GPU fails with:

```
vfio: error, group 13 is not viable, please ensure all devices within the iommu_group are bound to their vfio bus driver.
```

Or `/sys/kernel/iommu_groups/` is empty, or `lspci -nnk` still shows `Kernel driver in use: nvidia` / `amdgpu` for the card you meant to pass through.

**Cause.** An IOMMU group is the smallest unit that can be handed to a VM. Every device in the group must be bound to `vfio-pci` — if the GPU's HDMI audio function, a USB controller, or a PCIe root port shares the group and is still on its normal driver, the group is "not viable". An empty `iommu_groups` directory means IOMMU (Intel VT-d / AMD-Vi) is not enabled at all.

> ⚠️ **Risk.** This is the record most likely to leave you staring at a black screen. Once `vfio-pci` claims a GPU it is unusable by the host — if you bind the only GPU, or the one your monitor is plugged into, the desktop will not come up after reboot. Set your motherboard to display from the *host* GPU first, and keep a way in (SSH from another machine, or a known-good Limine/GRUB fallback entry with the modprobe file renamed). Since kernel 6.0 the framebuffer freezes once VFIO loads and before GPU drivers do, which hides the LUKS passphrase prompt on encrypted systems — if you use disk encryption, add your host GPU driver to the initramfs too or use the modprobe.d method rather than initramfs. The ACS override patch deliberately breaks PCIe isolation and has real security implications.

**Fix.**

First confirm IOMMU is on:

```bash
sudo dmesg | grep -i -e DMAR -e IOMMU | head
ls /sys/kernel/iommu_groups/ | wc -l
```

If empty: enable VT-d / AMD-Vi in firmware, and for Intel add the kernel parameter `intel_iommu=on` (AMD needs no parameter — the kernel enables AMD-Vi automatically when the firmware advertises it). Apply it where your bootloader keeps kernel parameters:
- Limine: the `cmdline:` line in `/boot/limine.conf`
- systemd-boot: the `options` line in `/boot/loader/entries/*.conf`
- GRUB: `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`

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

Every non-bridge device in the target group must go to `vfio-pci`. Take the `[vendor:device]` IDs from that output (e.g. `10de:13c2` for the GPU and `10de:0fbb` for its audio function) and bind them early:

```bash
sudo tee /etc/modprobe.d/vfio.conf >/dev/null <<'EOF'
options vfio-pci ids=10de:13c2,10de:0fbb
softdep drm pre: vfio-pci
EOF
```

If the proprietary NVIDIA driver is installed, use `softdep nvidia pre: vfio-pci` instead of `softdep drm pre: vfio-pci`. Do **not** bind a PCIe root port or bridge that happens to be in the group — it must stay on the host.

For a stronger guarantee, put the modules in the initramfs as well:

```bash
sudo tee /etc/mkinitcpio.conf.d/vfio.conf >/dev/null <<'EOF'
MODULES+=(vfio_pci vfio vfio_iommu_type1)
EOF
sudo mkinitcpio -P
```

Make sure `modconf` is in your `HOOKS`. Reboot and verify the binding:

```bash
lspci -nnk -d 10de:13c2
# want: Kernel driver in use: vfio-pci
```

If the group still contains devices you cannot pass (a shared root port), move the card to a different PCIe slot before considering the ACS override patch (`linux-zen` + `pcie_acs_override=downstream,multifunction`), which weakens device isolation.

**Verify.** `lspci -nnk` shows `Kernel driver in use: vfio-pci` for every device in the target IOMMU group, and the VM starts with the GPU attached.

Sources: <https://wiki.archlinux.org/title/PCI_passthrough_via_OVMF> · <https://wiki.archlinux.org/title/KVM> · <https://wiki.archlinux.org/title/Libvirt>

---

## Fix the clock being hours off after booting Windows

`clock-wrong-after-dual-boot-windows` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `dual-boot`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** Every time I boot into Windows and come back to Arch/Omarchy, the clock is off by exactly my UTC offset. Fixing it in one OS breaks it in the other. Sometimes HTTPS sites then fail with certificate date errors.

**Cause.** Both systems read the same hardware (RTC) clock but interpret it differently: Linux treats it as UTC, Windows treats it as local time. Each one "corrects" it on boot and they fight. Since systemd 216, if the RTC is set to local time, systemd will never write back to it, which makes the drift worse.

> ⚠️ **Risk.** `timedatectl set-local-rtc 1` is the wrong direction and is explicitly discouraged — it causes over-correction across DST changes and can make the system clock go backwards during boot. Only remove `/etc/adjtime` if you then immediately reset the hardware clock, or the next boot may come up with a wildly wrong time (which breaks TLS and pacman signature checks).

**Fix.**

The recommended direction is to make Windows use UTC. In an Administrator Command Prompt on Windows:

```
reg add "HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /d 1 /t REG_DWORD /f
```

On the Linux side, make sure the RTC is treated as UTC and NTP is on:

```bash
sudo timedatectl set-local-rtc 0
sudo timedatectl set-ntp true
sudo timedatectl set-timezone Europe/London   # your zone
timedatectl status
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

If the hardware clock keeps drifting in large jumps, clear a bad drift value:

```bash
sudo rm /etc/adjtime
sudo hwclock --systohc --utc
```

**Verify.** `timedatectl status` shows `RTC in local TZ: no`, `System clock synchronized: yes`, `NTP service: active`. Reboot into Windows and back — the time is still correct.

Sources: <https://wiki.archlinux.org/title/System_time> · <https://wiki.archlinux.org/title/Systemd-timesyncd>

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

**Cause.** Either the CPU virtualization extensions are switched off in firmware (very common on laptops and on prebuilt desktops), or the `kvm_intel`/`kvm_amd` module never got loaded. Arch kernels build both as modules and udev normally loads them on boot — if the firmware bit is clear, the module refuses to load and logs why.

> ⚠️ **Risk.** On some firmware, enabling virtualization also toggles related security settings and can reset the boot order — note your current boot entry before you save, so you can find Limine/GRUB again if the firmware reorders devices.

**Fix.**

Establish whether the CPU claims support at all:

```bash
LC_ALL=C.UTF-8 lscpu | grep Virtualization
grep -Eo 'vmx|svm' /proc/cpuinfo | sort -u
```

Try to load the module and read the reason it failed:

```bash
sudo modprobe kvm_intel      # or kvm_amd
sudo dmesg | grep -i -E 'kvm|vmx|svm' | tail -20
```

A line like `kvm: VMX not enabled (by BIOS) in MSR_IA32_FEAT_CTL on CPU 0` (Intel) or `kvm: SVM not supported by CPU` / `kvm: no hardware support` (AMD) means the firmware switch is off. Reboot into UEFI setup and enable it — it is called *Intel VT-x* / *Intel Virtualization Technology* / *SVM Mode* / *AMD-V*, usually under CPU or Advanced settings. On many machines it lives next to overclocking options, and on some Lenovo/HP laptops there is a separate *VT-d* entry too.

Once `lsmod | grep kvm` shows `kvm_intel` or `kvm_amd`, make sure you may use the device. Membership in `kvm` is what grants access to `/dev/kvm`:

```bash
ls -l /dev/kvm
sudo usermod -aG kvm,libvirt $USER
```

Log out of Hyprland and back in (group membership is picked up at session start, not by `newgrp` alone), then:

```bash
id -nG | tr ' ' '\n' | grep -E 'kvm|libvirt'
sudo systemctl enable --now libvirtd.service
```

If `lscpu` shows no `vmx`/`svm` at all even after the firmware change, and the machine is itself a virtual machine, you need nested virtualization enabled on the *outer* host instead.

**Verify.** `ls -l /dev/kvm` shows a character device owned by `root:kvm`, `lsmod | grep kvm` lists `kvm_intel` or `kvm_amd`, and virt-manager no longer warns about KVM.

Sources: <https://wiki.archlinux.org/title/KVM> · <https://wiki.archlinux.org/title/Libvirt> · <https://wiki.archlinux.org/title/QEMU> · <https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/kvm/vmx/vmx.c>

---

## Fix Docker refusing --gpus all with "could not select device driver"

`docker-gpu-could-not-select-device-driver` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** Any GPU container fails immediately:

```
docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]].
```

`nvidia-smi` on the host works fine. Sometimes the container starts but then prints `Failed to initialize NVML: Unknown Error`.

**Cause.** Docker itself has no idea how to expose an NVIDIA GPU — that comes from `nvidia-container-toolkit`, which has to be installed and registered as a runtime in `/etc/docker/daemon.json` before dockerd will accept `--gpus`. On Arch the toolkit is a separate package that nothing pulls in, and the daemon must be restarted after registration.

> ⚠️ **Risk.** `/etc/docker/daemon.json` must stay valid JSON — a stray trailing comma makes `docker.service` fail to start with every container down. If you edited it by hand, validate with `python -m json.tool /etc/docker/daemon.json` before restarting. Note also that dockerd refuses to start if the same option is set both in `daemon.json` and as a flag in the unit.

**Fix.**

Install the toolkit and register it with the daemon:

```bash
sudo pacman -S --needed nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker.service
```

That writes the runtime into `/etc/docker/daemon.json`; if you prefer to do it by hand:

```json
{
  "runtimes": {
    "nvidia": {
      "path": "/usr/bin/nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
```

Check the daemon actually loaded it, then test:

```bash
docker info | grep -i runtimes
sudo docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
```

If you get `Failed to initialize NVML: Unknown Error` instead, pass the device nodes explicitly — a known toolkit quirk:

```bash
sudo docker run --rm --gpus all \
  --device /dev/nvidiactl:/dev/nvidiactl \
  --device /dev/nvidia-uvm:/dev/nvidia-uvm \
  --device /dev/nvidia0:/dev/nvidia0 \
  nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
```

If you have Docker Desktop installed alongside the system daemon, the error can also mean you are talking to the wrong daemon — Desktop's VM has no host GPU:

```bash
docker context ls
docker context use default
```

**Verify.** `docker info | grep -i runtimes` lists `nvidia`, and `docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi` prints your GPU.

Sources: <https://wiki.archlinux.org/title/Docker> · <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html> · <https://bbs.archlinux.org/viewtopic.php?id=300693> · <https://archlinux.org/packages/extra/x86_64/nvidia-container-toolkit/files/>

---

## Grant a Flatpak app access to files it says do not exist

`flatpak-app-cannot-access-files` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `endeavouros`, `flatpak`, `manjaro`, `omarchy`

**Symptom.** Flatpak Firefox shows a "File not found" page when I open a local HTML file. Other Flatpak apps show empty folders or refuse to save into ~/Documents even though the files are clearly there.

**Cause.** The Flatpak sandbox only exposes the paths listed in the app's manifest plus any user overrides. Anything else simply is not visible inside the sandbox, so the app reports the file as missing rather than as a permission error.

> ⚠️ **Risk.** Granting `--filesystem=home` to Flatpak Firefox makes it find and load your host `~/.mozilla` profile instead of the sandboxed one at `~/.var/app/org.mozilla.firefox/`, so your tabs and history appear to vanish. Either scope the permission narrowly or copy the sandboxed profile to `~/.mozilla` first. Broad home access also defeats the point of the sandbox.

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

Sources: <https://wiki.archlinux.org/title/Flatpak>

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

## Run docker-compose against Podman via the Docker-compatible socket

`docker-compose-against-podman-socket` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `docker`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `podman`

**Symptom.** Podman itself works, but `docker compose up` or `docker-compose up` fails with:

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

Or `podman compose` runs but builds fail with buildkit errors, or an image reference fails with `short-name "nginx" did not resolve to an alias and no unqualified-search registries are defined in "/etc/containers/registries.conf"`.

**Cause.** Podman is daemonless, so nothing listens on the Docker socket until you enable Podman's REST API socket. `docker-compose` speaks only to `$DOCKER_HOST`, and `podman compose` is just a thin wrapper that shells out to whichever compose provider is installed. Separately, Arch's `podman` ships with no search registries configured, so unqualified image names never resolve.

> ⚠️ **Risk.** `podman-compose` has known compatibility gaps with real compose files; do not assume a working `docker-compose.yml` behaves identically. Also note that networks created by a compose project are often not removed by `podman compose down` — check `podman network ls` and clean up with `podman network rm` rather than assuming the environment is gone.

**Fix.**

Enable Podman's Docker-compatible socket as a user unit and point the client at it:

```bash
systemctl --user enable --now podman.socket
systemctl --user status podman.socket
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
docker compose version
```

Make it permanent for shells, user units and GUI apps. On Omarchy add it to the uwsm environment (it is sourced for the whole graphical session):

```bash
# ~/.config/uwsm/env
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
```

And for systemd user units:

```bash
mkdir -p ~/.config/environment.d
printf 'DOCKER_HOST=unix://%%t/podman/podman.sock\n' > ~/.config/environment.d/podman-docker.conf
```

BuildKit is not supported through this socket — turn it off:

```bash
export DOCKER_BUILDKIT=0
```

Configure search registries so plain `nginx` / `archlinux` resolve like they do with Docker:

```bash
sudo mkdir -p /etc/containers/registries.conf.d
sudo tee /etc/containers/registries.conf.d/10-unqualified-search-registries.conf >/dev/null <<'EOF'
unqualified-search-registries = ["docker.io"]
EOF
```

If you want the `docker` command itself to be Podman, install the shim:

```bash
sudo pacman -S podman-docker
```

To pick which compose implementation `podman compose` uses when both are installed (`docker-compose` wins by default):

```bash
export PODMAN_COMPOSE_PROVIDER=podman-compose
```

For containers to survive logout, enable lingering:

```bash
loginctl enable-linger
```

**Verify.** `docker compose version` and `docker ps` both work with no Docker daemon installed, and `podman ps` shows the same containers `docker ps` does.

Sources: <https://wiki.archlinux.org/title/Podman> · <https://wiki.archlinux.org/title/Systemd/User> · <https://raw.githubusercontent.com/basecamp/omarchy/master/config/uwsm/env>

---

## Make printers appear in a Flatpak app's print dialog

`flatpak-app-cannot-see-cups-printers` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `flatpak`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** The print dialog inside Flatpak LibreOffice / GIMP / Chrome / Inkscape shows "No printers found", or only offers "Print to File", while `lpstat -p -d` on the host lists the printer as idle and printing from a native app works fine.

**Cause.** CUPS is reached over the Unix socket `/run/cups/cups.sock`, which is not mounted inside the Flatpak sandbox unless the app holds the `cups` socket permission. Apps that do not go through the Print portal see no CUPS server at all and report zero printers. Manifests vary wildly in whether they request it.

> ⚠️ **Risk.** `--socket=cups` gives the app unfiltered access to the CUPS control socket, which can enqueue jobs and read printer configuration. Prefer granting it per app rather than globally.

**Fix.**

Grant CUPS access to the specific app:

```bash
flatpak override --user --socket=cups org.libreoffice.LibreOffice
```

Or for every Flatpak app at once (omit the app id):

```bash
flatpak override --user --socket=cups
```

If your printers are served by a remote CUPS server declared in `/etc/cups/client.conf`, the sandbox also needs to read that file:

```bash
flatpak override --user --filesystem=/etc/cups:ro org.libreoffice.LibreOffice
```

Make sure a portal backend that implements the Print portal is installed — `xdg-desktop-portal-hyprland` and `xdg-desktop-portal-wlr` do not, `xdg-desktop-portal-gtk` does:

```bash
sudo pacman -S --needed xdg-desktop-portal-gtk
systemctl --user restart xdg-desktop-portal.service xdg-desktop-portal-gtk.service
```

Confirm the host side is actually serving printers before blaming the sandbox:

```bash
systemctl status cups.service
lpstat -p -d
```

Then fully quit and relaunch the Flatpak app — overrides are only read at startup.

**Verify.** `flatpak info --show-permissions org.libreoffice.LibreOffice` lists `cups` under `[Context] sockets`, and the printer now appears in the app's own print dialog.

Sources: <https://docs.flatpak.org/en/latest/sandbox-permissions.html> · <https://github.com/flatpak/xdg-desktop-portal/issues/341> · <https://wiki.archlinux.org/title/XDG_Desktop_Portal> · <https://wiki.archlinux.org/title/CUPS> · <https://wiki.archlinux.org/title/Flatpak>

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

> ⚠️ **Risk.** Persistent journals grow: the default cap is 10% of the filesystem, soft-capped at 4 GiB, which is exactly how a small root partition fills up and breaks `pacman -Syu`. Set `SystemMaxUse=` at the same time as you enable persistence. Do not "fix" a full disk by deleting `/var/log/journal` itself — use `journalctl --rotate && journalctl --vacuum-size=200M`, which trims the files and leaves the directory in place.

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

Sources: <https://man.archlinux.org/man/journald.conf.5.en> · <https://man.archlinux.org/man/journalctl.1.en> · <https://wiki.archlinux.org/title/Systemd/Journal> · <https://raw.githubusercontent.com/systemd/systemd/main/src/journal/journalctl-util.c>

---

## Fix hostname.local names not resolving (mDNS off in resolved, or Avahi fighting it)

`mdns-local-hostname-not-resolving` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `ping raspberrypi.local` fails with `Name or service not known`, a network printer or Home Assistant box that other devices reach by `.local` name is unreachable, and `resolvectl query nas.local` returns `nas.local: Name 'nas.local' not found`. The device answers fine by IP address. Sometimes the machine's own hostname also keeps gaining a number (`myhost-2.local`).

**Cause.** mDNS has to be enabled in two places: systemd-resolved's global `MulticastDNS=` (on by default) *and* per-connection in NetworkManager, whose `connection.mdns` default is effectively off. So `.local` never gets resolved even though resolved supports it. The renaming-with-numbers symptom is the opposite problem — Avahi and resolved are both answering mDNS on the same interface and fighting over the hostname.

> ⚠️ **Risk.** Running Avahi and systemd-resolved as mDNS *responders* at the same time causes the hostname-conflict renaming loop, so pick one and disable the other's responder — do not enable both. Editing the `hosts:` line in `/etc/nsswitch.conf` incorrectly breaks all name resolution system-wide, including for pacman: copy the file aside first (`sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.bak`) and test with `getent hosts archlinux.org` before rebooting. Using the full `mdns` module rather than `mdns_minimal` makes reverse lookups in `mtr`/`traceroute` time out.

**Fix.**

See what is actually enabled:

```bash
resolvectl status
resolvectl mdns
nmcli -f connection.mdns connection show "$(nmcli -t -f NAME connection show --active | head -1)"
systemctl is-active avahi-daemon.service systemd-resolved.service
```

**Path A — use systemd-resolved for mDNS** (simplest if you do not need service discovery). Turn it on for the connection:

```bash
nmcli connection modify "<connection-name>" connection.mdns yes
nmcli connection up "<connection-name>"
```

Or set it as the default for all connections:

```bash
sudo mkdir -p /etc/NetworkManager/conf.d
sudo tee /etc/NetworkManager/conf.d/10-mdns.conf >/dev/null <<'EOF'
[connection]
connection.mdns=2
EOF
sudo systemctl restart NetworkManager
```

(`2` = yes/resolve-and-respond, `1` = resolve only, `0` = no.) Then make sure Avahi is not competing:

```bash
sudo systemctl disable --now avahi-daemon.service avahi-daemon.socket
resolvectl query raspberrypi.local
```

**Path B — use Avahi** (needed for DNS-SD service discovery, e.g. CUPS printer browsing). Install the NSS module and let Avahi own mDNS:

```bash
sudo pacman -S --needed avahi nss-mdns
sudo systemctl enable --now avahi-daemon.service
```

```
# /etc/nsswitch.conf — mdns_minimal must come BEFORE resolve and dns
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve [!UNAVAIL=return] files myhostname dns
```

And have resolved cache but not respond, so the two do not collide:

```bash
sudo mkdir -p /etc/systemd/resolved.conf.d
sudo tee /etc/systemd/resolved.conf.d/10-mdns.conf >/dev/null <<'EOF'
[Resolve]
MulticastDNS=resolve
EOF
sudo systemctl restart systemd-resolved.service
```

`nss-mdns` only works if your upstream DNS returns `NXDOMAIN` for the `local` domain — check:

```bash
host -t SOA local
```

If it does not return NXDOMAIN, use the full `mdns` module scoped to `.local` only:

```
# /etc/nsswitch.conf
hosts: mymachines mdns [NOTFOUND=return] resolve [!UNAVAIL=return] files myhostname dns
```

```
# /etc/mdns.allow
.local.
.local
```

Either way, mDNS needs UDP 5353 open:

```bash
sudo ufw allow 5353/udp comment 'mDNS'
```

**Verify.** `resolvectl query nas.local` returns an address (Path A) or `avahi-resolve -n nas.local` does (Path B), `ping nas.local` works, and `avahi-browse -at` lists services on the LAN if you took Path B.

Sources: <https://wiki.archlinux.org/title/Systemd-resolved> · <https://wiki.archlinux.org/title/Avahi> · <https://wiki.archlinux.org/title/CUPS>

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

> ⚠️ **Risk.** Rootless Docker is a separate, empty daemon: existing images, volumes and containers under `/var/lib/docker` are invisible to it and are NOT migrated. It also cannot bind ports below 1024 by default and has no access to host devices. Do not run both daemons and then wonder which one `docker compose down -v` just wiped — check `docker context show` first. Enabling lingering keeps a daemon running after logout; do not use lingering to fake autologin, it breaks session permissions.

**Fix.**

Install the rootless extras (they pull in `rootlesskit`):

```bash
yay -S docker-rootless-extras
```

Allocate a subordinate ID range of at least 65536 (check `/etc/subuid` first so you do not collide):

```bash
cat /etc/subuid /etc/subgid
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
```

Start the daemon as a user unit:

```bash
systemctl --user enable --now docker.socket
systemctl --user status docker.socket
```

Point the client at it with a persistent context:

```bash
docker context create rootless --description "Rootless mode" \
  --docker "host=unix:///run/user/$(id -u)/docker.sock"
docker context use rootless
docker info | grep -E 'rootless|Docker Root Dir'
```

Or set the environment variable instead — put it where user units and GUI apps see it, not only in `.bashrc`:

```bash
mkdir -p ~/.config/environment.d
printf 'DOCKER_HOST=unix://%%t/docker.sock\n' > ~/.config/environment.d/docker-rootless.conf
```

To have it running without an open session (so containers come back after a reboot):

```bash
loginctl enable-linger
loginctl list-users        # LINGER should say yes
```

If `rootlesskit` still fails, unprivileged user namespaces are blocked (this is the default on `linux-hardened`):

```bash
sysctl kernel.unprivileged_userns_clone
zgrep CONFIG_USER_NS_UNPRIVILEGED /proc/config.gz
```

**Verify.** `docker info` shows `rootless` in the security options and `Docker Root Dir: /home/<you>/.local/share/docker`, and `docker run --rm hello-world` succeeds without sudo and without you being in the `docker` group.

Sources: <https://wiki.archlinux.org/title/Docker> · <https://aur.archlinux.org/packages/docker-rootless-extras> · <https://wiki.archlinux.org/title/Systemd/User> · <https://wiki.archlinux.org/title/Podman>

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

> ⚠️ **Risk.** `systemctl reset-failed` usually unloads the unit, which makes `systemctl status` stop reporting the previous failure and its logs — capture the journal output *before* resetting if you still need to diagnose it. Raising `StartLimitBurst` or setting `StartLimitIntervalSec=0` on a service that crashes on startup turns it into an unbounded restart loop that can spin a CPU core and flood the journal.

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

Find out what it actually runs and with what environment before guessing:

```bash
systemctl cat foo.service
systemctl show foo.service -p ExecStart -p Restart -p RestartSec -p StartLimitBurst -p StartLimitIntervalSec
```

Fix the underlying failure. If the service is legitimately expected to flap (a network-dependent daemon, a tunnel), slow the restarts down so it backs off instead of burning through the limit — with a drop-in, not by editing the packaged unit:

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

```bash
sudo systemctl daemon-reload
sudo systemctl restart foo.service
```

That allows 5 restarts per 5 minutes with 15 seconds between attempts. To disable rate limiting entirely (rarely a good idea) set `StartLimitIntervalSec=0`.

Note `StartLimit*` belong in `[Unit]`, not `[Service]` — putting them in `[Service]` is a common mistake and systemd will warn about the unknown key in the journal. The system-wide defaults live in `/etc/systemd/system.conf` as `DefaultStartLimitIntervalSec=` / `DefaultStartLimitBurst=`.

**Verify.** `systemctl status foo.service` shows `active (running)` and the journal no longer contains `start-limit-hit`. `systemctl show foo.service -p StartLimitBurst -p StartLimitIntervalSec` reflects your drop-in.

Sources: <https://man.archlinux.org/man/systemd.unit.5.en> · <https://wiki.archlinux.org/title/Systemd> · <https://wiki.archlinux.org/title/Systemd/User>

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

## Fix "cannot change locale" warnings from bash, perl and ssh

`locale-cannot-change-locale-warnings` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `containers`, `endeavouros`, `locale`, `manjaro`, `omarchy`, `ssh`

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

This often starts after SSHing in from another machine, or inside a container/chroot.

**Cause.** The locale named in `LANG`/`LC_*` has not been generated. Locales must be uncommented in `/etc/locale.gen` and built with `locale-gen` before they exist. When SSH forwards the client's `LC_*` variables, a locale that exists on the client but not on the server triggers this on every command.

> ⚠️ **Risk.** Never set `LC_ALL` in `/etc/locale.conf` — it is the one LC_* variable that cannot be set there and it overrides every other category, silently breaking per-category settings. It is meant only for temporary testing.

**Fix.**

Generate the locale you actually want. Uncomment the line in `/etc/locale.gen`:

```bash
sudo sed -i 's/^#en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
sudo locale-gen
```

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

To override just for your user, create `~/.config/locale.conf` with the same syntax.

If you are using a custom/unofficial locale (e.g. `en_XX.UTF-8`) and dead keys or compose stop working, pin `LC_CTYPE` to a supported locale in `/etc/locale.conf`:

```
LANG=en_XX.UTF-8
LC_CTYPE=en_US.UTF-8
```

**Verify.** `locale` prints your locale with no warnings, `locale -a | grep -i en_US` lists `en_US.utf8`, and opening a new terminal produces no setlocale messages.

Sources: <https://wiki.archlinux.org/title/Locale>

---

## Make the SSH agent visible to GUI apps in a Wayland session

`ssh-agent-not-seen-by-gui-apps` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `flatpak`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `wayland`

**Symptom.** `git push` works in the terminal but the same repo in VS Code, a JetBrains IDE, or a Flatpak Git client asks for the key passphrase every time or fails with `Permission denied (publickey)`. `ssh-add -l` in a terminal lists the key, but a shell spawned from the GUI app says `Could not open a connection to your authentication agent`. Every new terminal also starts its own `ssh-agent` process (`pgrep -c ssh-agent` climbs).

**Cause.** Units and applications launched by the compositor / systemd user instance do not inherit anything from `~/.bashrc` or `~/.profile`, so an agent started there — and the `SSH_AUTH_SOCK` it prints — is invisible to them. The fix is to run one agent as a user unit and export `SSH_AUTH_SOCK` where the *session* can see it, not only where interactive shells can.

> ⚠️ **Risk.** Do not set `SSH_AUTH_SOCK` unconditionally if you use agent forwarding — on a machine you SSH *into*, a locally set value overrides the forwarded socket and `ssh-add -l` on the remote reports `The agent has no identities`. Guard it with `if [[ -z "$SSH_CONNECTION" ]]` in shell rc files. Running both `ssh-agent.service` and `gcr-ssh-agent.socket` leaves you guessing which agent holds which key.

**Fix.**

Use the `ssh-agent.service` user unit shipped with `openssh` (since 9.4p1-3):

```bash
systemctl --user enable --now ssh-agent.service
systemctl --user status ssh-agent.service
```

Export its socket into the graphical session. On Omarchy, `~/.config/uwsm/env` is sourced for the whole uwsm session:

```bash
# ~/.config/uwsm/env
export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"
```

Also set it for systemd user units (which do not read that file):

```bash
mkdir -p ~/.config/environment.d
printf 'SSH_AUTH_SOCK=%%t/ssh-agent.socket\n' > ~/.config/environment.d/ssh-agent.conf
```

(`%t` expands to `$XDG_RUNTIME_DIR`.) Log out and back in, then confirm the session knows:

```bash
systemctl --user show-environment | grep SSH_AUTH_SOCK
ssh-add -l
```

Have keys added on first use instead of by hand:

```
# ~/.ssh/config
AddKeysToAgent yes
```

A passphrase prompt still needs a GUI askpass in a Wayland session:

```bash
sudo pacman -S --needed seahorse
printf 'SSH_ASKPASS=/usr/lib/seahorse/ssh-askpass\nSSH_ASKPASS_REQUIRE=prefer\n' >> ~/.config/environment.d/ssh-agent.conf
```

Remove any `eval $(ssh-agent)` from `~/.bashrc` / `~/.zshrc` — that is what was spawning an agent per terminal.

If you would rather have gnome-keyring hold the keys, use its agent instead of openssh's and do not set `SSH_AUTH_SOCK` yourself:

```bash
systemctl --user enable --now gcr-ssh-agent.socket
```

Run only one of the two. For a Flatpak app to reach the agent at all it needs the socket forwarded:

```bash
flatpak override --user --socket=ssh-auth com.visualstudio.code
```

**Verify.** `systemctl --user show-environment | grep SSH_AUTH_SOCK` points at `$XDG_RUNTIME_DIR/ssh-agent.socket`, `pgrep -c ssh-agent` is 1, and `ssh-add -l` from a shell opened *inside* the GUI app lists your key.

Sources: <https://wiki.archlinux.org/title/SSH_keys> · <https://wiki.archlinux.org/title/GNOME/Keyring> · <https://wiki.archlinux.org/title/Systemd/User> · <https://raw.githubusercontent.com/basecamp/omarchy/master/config/uwsm/env>

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

**Symptom.** Logs from one service have holes in them — the interesting lines are simply missing — and the journal contains entries from journald itself like:

```
systemd-journald[318]: Suppressed 4079 messages from /system.slice/nginx.service
```

Debugging a crash is impossible because the burst right before the failure is exactly the part that was dropped.

**Cause.** journald rate-limits per service: more than `RateLimitBurst` messages inside `RateLimitIntervalSec` (10000 in 30s by default) and everything else in that window is discarded, with only a summary line kept. The effective burst is additionally scaled down by how little free disk space the journal has, so a nearly-full disk drops far more than the nominal limit suggests.

> ⚠️ **Risk.** Turning rate limiting off system-wide is how a single looping service fills the root filesystem in minutes and takes down `pacman`, Docker and anything else that needs to write. Prefer the per-unit `LogRateLimit*` override, keep `SystemMaxUse=` set, and revert the change once you have the logs you needed.

**Fix.**

See how much is being dropped and by whom:

```bash
journalctl -b | grep -i 'Suppressed .* messages from'
journalctl -b -u systemd-journald --no-pager
journalctl --disk-usage
df -h /var
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
sudo systemctl daemon-reload
sudo systemctl restart nginx.service
```

`LogRateLimit*` in the unit override the global `RateLimit*` for that service; `0` for either value turns rate limiting off for it.

Because the effective burst is multiplied by a factor derived from free space for the journal, free space up as well — the multiplier only reaches its maximum with tens of GB available:

```bash
sudo journalctl --rotate
sudo journalctl --vacuum-size=1G
```

For a short debugging session it is often cleaner to bypass the journal entirely and watch the process directly:

```bash
sudo journalctl -u nginx.service -f -o short-precise
```

Remember to remove the override when you are done.

**Verify.** Reproduce the burst: `journalctl -b | grep -c 'Suppressed .* messages'` stays at its previous value (no new suppression lines) and the previously missing lines now appear in `journalctl -u <unit>`.

Sources: <https://man.archlinux.org/man/journald.conf.5.en> · <https://wiki.archlinux.org/title/Systemd/Journal> · <https://raw.githubusercontent.com/systemd/systemd/main/src/journal/journald-manager.c>

---

## Enable nested virtualization so a VM can run its own VMs

`nested-virtualization-not-available-in-guest` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `laptop`, `libvirt`, `manjaro`, `omarchy`

**Symptom.** Inside a KVM guest, `grep -Eo 'vmx|svm' /proc/cpuinfo` returns nothing, `ls /dev/kvm` fails, and anything needing hardware virtualization in the guest refuses to run — WSL2 or Hyper-V in a Windows guest, the Android Studio emulator, Docker Desktop, or another nested VM. The outer host has KVM working perfectly.

**Cause.** KVM does not expose the CPU's virtualization extensions to guests unless nesting is explicitly turned on with the `nested` module parameter, and the guest's virtual CPU model must actually pass the host feature flags through (the default `qemu64`/host-model CPU hides them).

> ⚠️ **Risk.** `modprobe -r kvm_intel` fails while any VM is running, and force-killing VMs to unload it loses unsaved guest state — shut guests down cleanly first. `host-passthrough` exposes your exact CPU to the guest, which means a saved/migrated VM may refuse to resume on different hardware.

**Fix.**

On the **host**, enable nesting. Live (all VMs must be shut down, the module cannot unload otherwise):

```bash
sudo modprobe -r kvm_intel
sudo modprobe kvm_intel nested=1
cat /sys/module/kvm_intel/parameters/nested     # want Y
```

For AMD, substitute `kvm_amd` everywhere. Make it permanent:

```bash
# Intel
printf 'options kvm_intel nested=1\n' | sudo tee /etc/modprobe.d/kvm_intel.conf
# AMD
printf 'options kvm_amd nested=1\n' | sudo tee /etc/modprobe.d/kvm_amd.conf
```

Then pass the CPU features through to the guest. With libvirt:

```bash
sudo virsh edit <vm-name>
```

```xml
<cpu mode='host-passthrough' check='partial'/>
```

Or non-interactively:

```bash
sudo virt-xml <vm-name> --edit --cpu host-passthrough
```

In virt-manager the same setting is *CPUs > Model > host-passthrough*. With bare QEMU, add `-cpu host` (and `-enable-kvm`).

Boot the guest and check inside it:

```bash
grep -Eo 'vmx|svm' /proc/cpuinfo | sort -u
ls -l /dev/kvm
```

**Verify.** `cat /sys/module/kvm_intel/parameters/nested` prints `Y` on the host, and inside the guest `grep -Eo 'vmx|svm' /proc/cpuinfo` returns the flag and `/dev/kvm` exists.

Sources: <https://wiki.archlinux.org/title/KVM> · <https://wiki.archlinux.org/title/Libvirt>

---

## Debug a systemd timer that never fires

`user-timer-oncalendar-never-fires` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `systemd`

**Symptom.** A timer is "enabled" but the job never runs. `systemctl --user list-timers` shows `NEXT` as `n/a` or `-`, or `LAST` never advances. Sometimes `systemctl --user enable foo.timer` was run and nothing happened at all until the next login, or the `OnCalendar=` expression turns out to mean something completely different from what was intended.

**Cause.** Three separate traps. (1) `systemctl enable` only creates the symlink — it does not start the timer, so nothing arms until the next boot/login; `--now` does both. (2) A timer with no `WantedBy=timers.target` in `[Install]` cannot be enabled into anything. (3) `OnCalendar=` syntax is easy to get subtly wrong, and a malformed expression leaves the timer loaded but never elapsing.

> ⚠️ **Risk.** `WakeSystem=true` needs hardware support and will otherwise stop the timer outright with `Failed to enter waiting state: Operation not supported` and `Failed with result 'resources'` — do not add it speculatively. Enabling lingering keeps your user instance and its services running after logout; it is not a substitute for autologin and using it that way breaks session permissions.

**Fix.**

See what is actually armed, including inactive timers:

```bash
systemctl --user list-timers --all
systemctl list-timers --all          # system timers
systemctl --user cat foo.timer
```

Make sure the timer has an install target:

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

Then enable *and* start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now foo.timer
systemctl --user list-timers foo.timer
```

Test the calendar expression before trusting it — this is the single most useful command here:

```bash
systemd-analyze calendar "*-*-* 04:00:00"
systemd-analyze calendar --iterations=5 "Mon..Fri 22:30"
systemd-analyze calendar weekly
```

It prints `Normalized form` and the next elapse times; a syntax error is reported instead. Watch out for the rule that when you use the day-of-week field you must name at least one weekday, so `*-*-* 4:00:00` is "every day at 4am" while `Mon,Tue *-*-01..04 12:00:00` is "the 1st-4th of the month, but only if Mon or Tue".

Run the service by hand to prove the job itself works, independently of scheduling:

```bash
systemctl --user start foo.service
journalctl --user -u foo.service -n 50 --no-pager
```

If the timer has drifted or thinks it already ran, delete its stamp file:

```bash
ls ~/.local/share/systemd/timers/
rm ~/.local/share/systemd/timers/stamp-foo.timer
systemctl --user restart foo.timer
```

(System timers keep stamps in `/var/lib/systemd/timers/`.)

Remember that a **user** timer only exists while your user instance does — it stops at logout unless you enable lingering:

```bash
loginctl enable-linger
loginctl list-users
```

If the job needs the graphical session (a notification, a screenshot), it belongs on `graphical-session.target` rather than `timers.target`.

**Verify.** `systemctl --user list-timers foo.timer` shows a concrete `NEXT` timestamp and, after it passes, a `LAST` timestamp; `journalctl --user -u foo.service` shows the run.

Sources: <https://wiki.archlinux.org/title/Systemd/Timers> · <https://wiki.archlinux.org/title/Systemd/User> · <https://wiki.archlinux.org/title/Systemd>

---

## Fix "Redirect USB device" being greyed out in virt-manager

`virt-manager-redirect-usb-greyed-out` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `kvm`, `laptop`, `libvirt`, `manjaro`, `omarchy`

**Symptom.** In virt-manager's *Virtual Machine > Redirect USB device* menu the entry is greyed out, or the dialog opens but lists no devices, so a USB stick / YubiKey / phone plugged into the host never appears in the guest.

**Cause.** SPICE USB redirection needs two pieces of virtual hardware that are not part of the default VM definition: a USB controller, and at least one USB redirector channel (one per device you want to redirect simultaneously). Without a redirector, virt-manager has nothing to hand the device to.

> ⚠️ **Risk.** A redirected device is taken away from the host until redirection stops — never redirect your keyboard or mouse, or you will lose the ability to reach the viewer's own menus to undo it. Redirecting a mounted USB disk without unmounting it on the host first can corrupt the filesystem.

**Fix.**

Shut the VM down, then in virt-manager: *Add Hardware > Controller > USB* (model USB3/qemu-xhci is fine), and *Add Hardware > USB Redirection* once per concurrent device you want.

Equivalently, `sudo virsh edit <vm-name>` and add inside `<devices>`:

```xml
<controller type='usb' index='0' model='qemu-xhci' ports='8'/>
<redirdev bus='usb' type='spicevmc'/>
<redirdev bus='usb' type='spicevmc'/>
```

The display must be SPICE (VNC has no redirection channel):

```xml
<graphics type='spice' autoport='yes'/>
```

Boot the VM, connect with `virt-viewer`/`remote-viewer` or virt-manager's console, then *File > USB device selection* (remote-viewer) or *Virtual Machine > Redirect USB device* (virt-manager). Make sure you are on the **system** session connection (`qemu:///system`) if the device needs privileged access.

If redirection still will not cooperate, attach the device directly instead — this works without redirectors but requires the VM to be running and the device to be present:

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

**Verify.** The *Redirect USB device* menu item is selectable and lists your host devices; after ticking one, `lsusb` inside the guest shows it.

Sources: <https://wiki.archlinux.org/title/Libvirt> · <https://wiki.archlinux.org/title/QEMU>

---

## Restore audio tweaks that stopped working after the WirePlumber 0.5 config change

`wireplumber-lua-config-ignored-after-0-5` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `hyprland`, `laptop`, `manjaro`, `omarchy`, `pipewire`, `wayland`

**Symptom.** Custom audio behaviour silently reverted after an update: devices suspend again after a few seconds of silence, a disabled HDMI output is back, a renamed device shows its original name, or a headset auto-switch tweak stopped applying. There is no error — `systemctl --user status wireplumber` is active and audio otherwise works. `~/.config/wireplumber/main.lua.d/` still contains the `.lua` files that used to do it.

**Cause.** WirePlumber 0.5 dropped Lua configuration entirely. Fragments in `main.lua.d/` (and `/etc/wireplumber/main.lua.d/`) are no longer read at all — they are ignored without any warning, so every tweak you had silently reverts to stock behaviour. Configuration is now SPA-JSON files in a `wireplumber.conf.d/` directory.

> ⚠️ **Risk.** A syntax error in a `.conf` fragment can stop WirePlumber from starting, which means no audio at all (the journal reports it as something like `section '...' has no value`). Add one fragment at a time and restart WirePlumber after each. Shadowing a stock file by reusing its exact name silently removes the stock rules it contained, which can disable device detection you still need.

**Fix.**

Confirm the version and that the old files are dead weight:

```bash
wireplumber --version
ls ~/.config/wireplumber/ /etc/wireplumber/ 2>/dev/null
journalctl --user -u wireplumber -b --no-pager | tail -30
```

Rewrite each tweak as SPA-JSON under `wireplumber.conf.d/`. Old `51-disable-suspension.lua` becomes:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

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

Disabling a device (e.g. GPU HDMI audio) — find the stable identifier first:

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

Things that used to be Lua *settings* are now runtime settings — set them with `wpctl` instead of a config file:

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

Then delete the dead Lua fragments so they stop confusing you later:

```bash
rm -rf ~/.config/wireplumber/main.lua.d ~/.config/wireplumber/bluetooth.lua.d
sudo rm -rf /etc/wireplumber/main.lua.d
```

Note the file layout rules: within each `wireplumber.conf.d/` directory files load in alphanumeric order, and a user file *shadows* a system file of the same name rather than merging with it — so `~/.config/wireplumber/wireplumber.conf.d/50-alsa-config.conf` replaces `/usr/share/wireplumber/wireplumber.conf.d/50-alsa-config.conf` entirely. Give your own files distinct names.

**Verify.** `journalctl --user -u wireplumber -b` shows no config parse errors, `wpctl inspect <ID>` reflects your changed property, and the behaviour you wanted (no suspend, device hidden, new name) is back after a reboot.

Sources: <https://wiki.archlinux.org/title/WirePlumber> · <https://bbs.archlinux.org/viewtopic.php?id=294454> · <https://bbs.archlinux.org/viewtopic.php?id=305957> · <https://wiki.archlinux.org/title/PipeWire>

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
