# security category: curated harvest topic list (draft, 2026-09-16)

41 topics kept from 48 candidates, after an adversarial review corrected five of them.
Every topic must pass the three gates in research/README.md before a record is written. Tier 1 harvests first. Every entry needs a fetched
source before a record is written. Slugs are indicative, the harvester picks the final one.

## A. Omarchy-specific (13). Source: omacom/omarchy quattro HEAD plus a public issue.

| # | Topic | Tier | Note |
|---|---|---|---|
| OM1 | LocalSend ufw rule opens 53317 to routable IPv6 on a stock install | 1 | installer opens it, not the user. #11560 |
| OM2 | omarchy-remove-security-sshd under sudo edits /root/.ssh, not yours | 1 | user believes SSH torn down. #9572 |
| OM3 | sshd once enabled binds 0.0.0.0 and ::, no scoped option | 2 | opt-in, lowers severity. #8248 |
| OM4 | one stalled lock latches lockRequested, later locks report ok without locking | 1 | suspends unlocked. #10299 |
| OM5 | plugins run unsandboxed in the long-lived omarchy-shell process | 1 | documented trust model, not a bug |
| OM6 | omarchy-debug captures unredacted LAN MACs and IPs, template asks you to attach it | 1 | #10255 |
| OM7 | default passwordless keyring destroyed by a multi-line secret, autologin cannot unlock | 1 | #11159 |
| OM8 | autologin deliberately enabled on LUKS installs | 2 | intentional tradeoff, pairs with OM4 |
| OM9 | omarchy-sudo-passwordless grants any process running as you full root for N minutes | 1 | script confirmed at /usr/share/omarchy/bin on 4.0.2-1 and at HEAD |
| OM10 | omarchy-refresh-config writes outside ~/.config given .. or an absolute path | 2 | #8423 |
| OM11 | menu password change never touches the separately created root password | 2 | #7539, menu shape corroborated only |
| OM12 | cancelling sudo during service removal still reports success | 2 | #9526 |

## B. Package and key trust (5)

| # | Topic | Tier | Note |
|---|---|---|---|
| PK1 | marginal or unknown trust signature blocks an update | 1 | bad fix SigLevel=TrustAll must be named as a trap |
| PK2 | archlinux-keyring chicken-and-egg after a long gap | 1 | the thread's own fix is a partial upgrade, do not reproduce |
| PK3 | omarchy-update-keyring reported success when key ops failed | 2 | FIXED by PR #7807 merged 2026-09-15. Dated record, needs checked_against |
| PK4 | AUR has shipped real malware, twice | 1 | Arch's own advisory |
| PK5 | what reviewing a PKGBUILD actually means | 1 | helper diffs miss reordered logic |

## C. Privilege, keys and local trust (6)

| # | Topic | Tier | Note |
|---|---|---|---|
| PR1 | hand-edited sudoers syntax error plus wrong mode locks sudo out | 1 | recovery needs root or rescue |
| PR2 | polkit rule silently no-ops because umask left it unreadable by polkitd | 1 | |
| PR3 | polkit auth_admin accepts any admin password, not the acting user's | 2 | surprising, documented |
| PR4 | unsafe permissions on ~/.gnupg | 2 | |
| PR5 | gpg keyserver receive failed | 3 | cause not settled, confirm before writing |
| PR6 | systemd-analyze security score mistaken for a compromise | 2 | answering it wrong gets a service disabled |

## D. Boot integrity and encryption (3)

| # | Topic | Tier | Note |
|---|---|---|---|
| BT1 | Secure Boot violation after a limine-only update, BOOTX64.EFI never re-signed | 1 | case-sensitive hook glob. #10945. Breaks boot |
| BT2 | Secure Boot re-enrolment needed after an Omarchy update | 2 | discussion 2296, medium confidence |
| BT3 | LUKS keyfile on the unencrypted ESP defeats the encryption | 1 | the common convenience tip is the defect |

## E. SSH (2)

| # | Topic | Tier | Note |
|---|---|---|---|
| SSH1 | REMOTE HOST IDENTIFICATION HAS CHANGED after an algorithm-order change | 1 | fix must stay narrow, not StrictHostKeyChecking=no |
| SSH2 | legacy kex or ssh-rsa refused after an upgrade | 1 | re-enabling must be scoped to one Host block |

## F. Network security (14)

| # | Topic | Tier | Note |
|---|---|---|---|
| NET1 | 802.1X profile with no CA cert and no domain-suffix-match connects anyway | 1 | merge of two candidates. Overlaps the danger field of wpa2-enterprise-8021x-connect-from-cli |
| NET2 | libvirt FORWARD rules are invisible to ufw's INPUT view | 1 | this project's own VMs |
| NET3 | WireGuard has no kill switch, suspend and resume leaks the real IP | 1 | |
| NET4 | wg-quick DNS silently reverted by NetworkManager or a DHCP client | 1 | tunnel healthy, DNS in the clear |
| NET5 | IPv6 leaks around a v4-only commercial VPN config | 2 | blog-tier source, needs a primary |
| NET6 | systemd-resolved DNSSEC off by default and incomplete when on | 2 | |
| NET7 | DNSOverTLS=opportunistic falls back to plaintext silently | 2 | NOT a default. omarchy-dns writes it only when the user picks Cloudflare or Google |
| NET8 | resolv.conf is not the stub symlink, so resolved policy has no effect | 2 | |
| NET9 | avahi advertises this host on a hotel or cafe network | 1 | must name avahi, NOT systemd-resolved. avahi installed and enabled on 4.0.2-1 |
| NET11 | Samba example config shares $HOME writable to the LAN | 2 | samba not installed on a stock box, record must say so |
| NET12 | cups-browsed auto-creates queues for anything advertised | 2 | cups-browsed not installed on a stock box, record must say so |
| NET13 | Bluetooth re-powers on resume, DiscoverableTimeout=0 never times out | 2 | the wiki itself suggests the bad setting |
| NET14 | NetworkManager connectivity check is a plaintext beacon | 3 | privacy rather than security, wiki flags it |

## Dropped, with the reason

- Google OAuth client ID and secret committed in the repo (#9118). The only record possible
  would be an accusation with no action for the reader, and this corpus is fixes. The test is
  "is there something the reader can do", not "is there a command to paste", which is why
  OM5, PK4 and PK5 survive it and this does not.
- systemd user units cannot be meaningfully sandboxed. Sourced only from a search snippet,
  never fetched. Refetch or leave out.
- pkexec CVE-2021-4034. Patched for years. Only reachable on a neglected system.
- Docker published ports bypass ufw. Already in the corpus as
  apps-services/docker-published-ports-bypass-ufw, which even notes Omarchy ships ufw-docker.
- systemd-resolved split DNS sending queries to the wrong link. High overlap with
  network/resolved-dns-override-breaks-vpn-split-dns. Better as a correction to that record
  than as a new one.
- SSDP and UPnP, and CVE-2024-47176. No primary source, and a 2024 CVE on a rolling distro is
  stale until someone checks.

## Two things already fixed upstream while the issue stays open

Do not cite either as a current problem. Both were caught by checking the code rather than
the issue state.

- omarchy setup security sshd leaving password auth on and opening the port before a key
  exists, #8363. Fixed by PRs #9267 and #9255 plus migration 1788124236.sh.
- The [omarchy] repo carrying SigLevel = Optional TrustAll, #9199. Current pacman-*.conf
  files carry no per-repo override, so it inherits Required DatabaseOptional. Issue still OPEN.

## Corrections the adversarial review made, kept so the same errors are not reintroduced

Verified on this workstation at omarchy 4.0.2-1 on 2026-09-16.

- **LLMNR dropped outright.** `/etc/systemd/resolved.conf.d/10-disable-multicast.conf`, owned
  by `omarchy-settings 4.0.2-1`, sets `LLMNR=no` and `MulticastDNS=no`. The topic was false
  for Omarchy 4. The same file is why NET9 has to be about avahi instead.
- **NET7 was not a default.** `omarchy-dns` writes `DNSOverTLS=opportunistic` when the user
  picks a provider. Nothing under `install/` calls it.
- **OM13 moved out of the Omarchy section and then dropped as duplicative of plain Arch
  advice.** Neither `/usr/lib/sysctl.d/10-arch.conf` nor `/etc/sysctl.d/99-omarchy-sysctl.conf`
  sets `kptr_restrict`, so the 0 is the kernel default and not an Omarchy choice.
- **The review was itself wrong once.** It reported no `NOPASSWD` in `/usr/share/omarchy` and
  concluded OM9 was generic sudo behaviour. `bin/omarchy-sudo-passwordless` is present on the
  installed system and at HEAD. OM9 stays. The review was right that the note attached to it
  was wrong, because `tools/provision-bench-vm.sh:110` writes its own sudoers line and never
  calls that command.
