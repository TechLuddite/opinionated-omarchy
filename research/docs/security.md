# Security and disclosure

16 problems. Sorted by severity, then by how often users hit it.

## A LUKS keyfile stored on the boot ESP defeats the encryption it is meant to unlock

`luks-keyfile-on-esp-defeats-encryption` · severity: **high** · frequency: **occasional** · applies to: `arch`, `desktop`, `laptop`, `luks`, `omarchy`, `uefi`

**Symptom.** Looking for a way to skip typing the LUKS passphrase on every boot, and finding instructions online for an auto-unlock keyfile embedded in the initramfs or kept on the boot partition. The question worth asking before doing it: is it actually safe to keep the key that unlocks an encrypted disk on the same disk, in a partition nothing has to authenticate to read.

**Cause.** Omarchy unlocks the root volume in the initramfs with mkinitcpio's busybox `encrypt` hook (confirmed in `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`: `HOOKS=(... block encrypt filesystems fsck btrfs-overlayfs)`), driven by `cryptdevice=PARTUUID=...:root` in `/etc/limine-entry-tool.d/omarchy-uki.conf`, and prompts for the passphrase before root is mounted. The Arch wiki's instructions for removing that prompt with a keyfile embedded in the initramfs open with a warning that names two conditions. The first: "Using some form of authentication earlier in the boot process. Otherwise auto-decryption will occur, defeating completely the purpose of block device encryption." The second: "/boot is encrypted. Otherwise root on a different installation (including the live environment) can extract your key from the initramfs, and unlock the device without any other authentication."

On an encrypted Omarchy install neither condition can be met. The installer mounts the EFI System Partition at `/boot` whenever encryption is on (`esp_mount_in_target=/boot` in the ISO configurator, confirmed here: `findmnt /boot` shows a `vfat` partition), Limine loads a UKI from `/boot/EFI/Linux/omarchy_linux.efi` with the initramfs inside it, and a UEFI system partition is FAT and cannot be LUKS-encrypted. Nothing authenticates earlier either: the UKI is the first thing in the boot that asks for anything. A keyfile embedded in the initramfs, or kept as a file on the ESP, therefore sits in the one partition on the disk that is never behind the passphrase it removes. The ESP is mounted `dmask=0077`, so other accounts on the running system cannot read it, but anyone holding the disk can.

> **Audit corrected this record.** Gate 2 held for the cause: the Arch wiki Dm-crypt/Device_encryption warning under 'With a keyfile embedded in the initramfs' says exactly what the record leans on, with two conditions, earlier authentication or an encrypted /boot, and the record paraphrased only the second, now both are quoted. The ESP-at-/boot claim was checked against how Omarchy installs, not how Arch can: the ISO configurator sets esp_mount_in_target=/boot when encryption is on and /efi when it is off, so on every encrypted install /boot is the vfat ESP, confirmed here by findmnt /boot. The record's 'always' is now scoped to encrypted installs, the only ones a LUKS keyfile applies to. The fix was wrong on Omarchy and its own cited source says so: it enrolls a TPM2 token with systemd-cryptenroll and adds tpm2-device=auto to /etc/crypttab, but Omarchy's initramfs uses the busybox encrypt hook (omarchy_hooks.conf) driven by cryptdevice= in /etc/limine-entry-tool.d/omarchy-uki.conf. Dm-crypt/System_configuration states that /etc/crypttab is read after the system has booted and is not a replacement for early-userspace unlocking, that the encrypt hook does not support crypttab options, and puts TPM2 unlocking under the sd-encrypt hook via rd.luks.options or x-initrd.attach. Following the record leaves the passphrase prompt in place at best. The fix also never closed the hole for someone who already has a keyfile: no keyslot removal, no UKI rebuild. Rewritten as: do not do it, and if done, find the cryptkey=/FILES= wiring, remove the keyslot (luksRemoveKey, positional keyfile per the local cryptsetup-luksRemoveKey man page), delete the file, rebuild with limine-mkinitcpio, with the sd-encrypt requirement stated and not walked through. verify and danger rewritten to match. Trusted_Platform_Module and the systemd-cryptenroll man page removed as sources because nothing now leans on them, and the configurator is added at a pinned sha. Severity high stands under the brief's scale: possession of the disk yields the credential that unlocks all private data. Not exercised: no keyfile, keyslot, UKI or ESP was touched, and the removal commands were checked against man pages, not run.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** This mistake does not fail loudly. The machine keeps booting with no passphrase prompt, so it stays invisible until the drive is lost, stolen or imaged, at which point the encryption protects nothing: the key sits next to the data in the one partition every recovery tool and every other OS can read. Do not "fix" it by moving the keyfile to `/boot`. On an encrypted Omarchy install `/boot` is the ESP, the same partition.

When undoing it, remove the keyslot as well as the file, or any surviving copy of the file still unlocks the volume. Test the passphrase with `cryptsetup open --test-passphrase` before removing a slot, and never remove the last one: a LUKS volume with no remaining keyslot cannot be opened again. Rebuild the UKI after deleting the file, or the old image on the ESP still carries the key.

**Fix.**

Do not store a LUKS keyfile for the root volume on the ESP, and do not embed one in the initramfs, on an Omarchy install. The passphrase prompt is the only authentication in that boot path.

If you already did, take it back out. Everything below runs from the booted system with the passphrase you still have.

First find where it was wired in. The `encrypt` hook reads `cryptkey=` from the kernel command line, or `/crypto_keyfile.bin` from the initramfs when no parameter is given, and a file gets into the initramfs through a `FILES=` entry:

```sh
grep -n cryptkey /etc/default/limine /etc/limine-entry-tool.d/*.conf
grep -n FILES /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf
sudo find /boot -name '*.key' -o -name '*keyfile*'
```

Remove the `cryptkey=` parameter and the `FILES=` entry you added. Leave `/etc/mkinitcpio.conf.d/omarchy_hooks.conf` alone: its `FILES+=(/etc/vconsole.conf)` line is Omarchy's own and is not a key.

Then remove the keyslot the keyfile unlocks, so a copy of the file that still exists somewhere (an old UKI, a backup, a snapshot) no longer opens the volume. Confirm your passphrase works before you remove anything:

```sh
sudo cryptsetup open --test-passphrase /dev/<your LUKS partition, from lsblk>
sudo cryptsetup luksDump /dev/<your LUKS partition>
sudo cryptsetup luksRemoveKey /dev/<your LUKS partition> /path/to/the/keyfile
```

Then delete the keyfile and rebuild the UKI, so the copy inside the old image on the ESP is replaced:

```sh
sudo rm -f /path/to/the/keyfile
sudo limine-mkinitcpio
```

If what you wanted was an unlock with no typing, Omarchy's boot path cannot do it safely as shipped. A TPM2 unlock needs the systemd initramfs, the `sd-encrypt` hook with `rd.luks.name=` and `rd.luks.options=...=tpm2-device=auto`, because the busybox `encrypt` hook does not support crypttab options and `/etc/crypttab` is read after root is already mounted. Omarchy assigns `HOOKS` wholesale in `omarchy_hooks.conf` and its kernel command line uses `cryptdevice=`, so that is a conversion of the boot path rather than a setting, and this record does not walk through it.

**Verify.** `sudo cryptsetup luksDump /dev/<your LUKS partition>` lists only the keyslots you mean to keep, the two `grep` commands in the fix return nothing, `sudo find /boot -name '*.key'` returns nothing, and the next boot asks for the passphrase.

Sources: <https://wiki.archlinux.org/title/Dm-crypt/Device_encryption> · <https://wiki.archlinux.org/title/Dm-crypt/System_configuration> · <https://github.com/omacom/omarchy-iso/blob/7cfb7111a06873d61c45d37034577d4ba08d3f4f/configs/airootfs/root/configurator>

---

## Confirm a suspend actually locked the screen, since a stalled lock latches as locked with nothing engaged

`stalled-lock-latch-suspends-unlocked` · severity: **high** · frequency: **occasional** · applies to: `omarchy`

**Symptom.** A lock that should have happened did not, and the shell says it did. The idle timer fires, or the lid closes, or `omarchy system lock` or Super+Ctrl+L is used, and no lock screen appears: the desktop stays where it was. `omarchy-shell lock isLocked` prints `true` all the same, `omarchy-shell lock status` shows `"requested":true` with `"sessionLocked":false` and `"secure":false` and never moves off `lock-pending: screen-stabilizing`, and every later lock request from any of those paths returns `ok` and does nothing, for hours. The screensaver stops appearing on idle as well, because it is gated on the same answer. Closing the lid then suspends the machine with the session unlocked, and the critical notification "Screen did not lock before suspend" is waiting on resume. The reporter on issue #10299 resumed into Hyprland's crashed-lockscreen failsafe rather than a password prompt, and it cleared on its own a few seconds later. A second reporter, whose shell had latched the same way after a stranded-lock recovery stalled, sat at an unlocked desktop for eight hours with `isLocked` reporting `true` throughout and two idle locks reported as exit 0.

**Cause.** Confirmed by reading `/usr/share/omarchy/shell/plugins/lock/Service.qml` on omarchy 4.0.2-1 and again on 4.0.4-1, byte-identical to the file at the v4.0.2 tag, commit 346e69e1cec6c4e8924531874af6ba010a1bc99e, and also byte-identical at the v4.0.3 and v4.0.4 tags. The shell's `locked` property at line 37 is true as soon as a lock is requested (`lockRequested`, set true inside `beginLock()` at line 135), before the compositor has confirmed anything. `requestSessionLock()`, lines 63 to 77, clears its own retry timer and marks the request done the moment it asks Hyprland for the lock, at lines 74 to 76, rather than when Hyprland confirms it. If that one request is declined or stalls, nothing retries it and nothing times out. From then on the `lock` IPC method sees `root.locked` already true and returns `ok` without doing anything, lines 513 to 516, and `isLocked` reports `true` off the same latched property, lines 519 to 521. The idle service gates the screensaver on that answer at `shell/plugins/services/idle/Service.qml` line 69 on 4.0.4 (line 68 on 4.0.2), so idling stops producing a screensaver too. Only two places ever clear `lockRequested` again, `finishUnlock()` at line 151 and the compositor's own `onLockStateChanged` at line 255, and both need a lock Hyprland has already confirmed, so a stall that happens before that confirmation cannot correct itself.

`omarchy-system-lock`, run by the lid switch through `omarchy-system-lid-close` (`default/hypr/bindings/utilities.lua` line 34) and by Super+Ctrl+L (line 126), discards the reply from the lock IPC at its line 8 and exits with the status of a trailing `|| true`, so nothing downstream can tell a real lock from a latched one. `omarchy-system-sleep-lock`, run from the suspend path by `omarchy-system-sleep-monitor`, maps `requested: true` with `secure: false` to `locking` and deliberately leaves it alone, then gives up after its budget, 12 seconds on the shipped `InhibitDelayMaxSec=15`, and lets the suspend proceed, because a delay inhibitor is a timer rather than a veto and the alternative is a laptop that stays awake in a closed bag. The only signal on wake is a critical desktop notification.

Established in issue #10299, opened 2026-09-05 by a user unconnected to this corpus. A collaborator comment on the thread confirmed the latch line by line and produced the same status output on a test VM by simulating the stall, and a second reporter reached the same latched state through a stalled stranded-lock recovery. What makes the original request stall, a declined or slow response from the compositor, is not established there or here, and nobody has triggered it on demand. The issue is open as of 2026-09-19. Fixes have been proposed and none has merged: PR #11811 (2026-09-14) added an acquire timeout and was folded into #12064, and both were closed unmerged, #11811 on 2026-09-16 and #12064 on 2026-09-17. Their work continues in #12245, open and unmerged as of 2026-09-19. The 4.0.3 and 4.0.4 releases changed the shell's plugin and lock code around this file, keeping the lock service out of third-party plugins' reach and loaded across plugin reloads, but neither touched the latch. `shell/plugins/lock/Service.qml` on `quattro` at commit e38c1d1289252d2adb96372eeac48d02e489c5b7 (2026-09-19) has since gained video wallpaper handling and still carries the latch at the same three places, shifted to lines 45, 86 and 585.

> **Audit corrected this record.** Held every mechanical claim against /usr/share/omarchy on omarchy 4.0.2-1: Service.qml lines 37, 63 to 77, 135, 151, 255 and 513 to 521, omarchy-system-lock line 8 and its trailing || true, omarchy-system-sleep-lock lines 11 to 35 and 79 to 124, omarchy-hyprland-session-locked, omarchy-restart-shell lines 28 to 37, omarchy-system-lid-close line 17, utilities.lua lines 34 and 126, idle Service.qml line 68, and busctl reporting InhibitDelayMaxUSec 15000000, which derives the 12 s budget. All six cited blobs were fetched at the pinned sha and are byte-identical to the installed files, and Service.qml and the four scripts are also byte-identical at the v4.0.3 and v4.0.4 tags, so the latch ships in every 4.0.x release. Gate 1 holds: issue #10299 was opened 2026-09-05 by mchldotdev, no one connected to this repository, and its body and the collaborator comment contain every mechanism the record states. Gate 3 holds: the trigger is unknown to everyone and the record gives none. Four things were wrong. The symptom said the machine wakes straight to the desktop, but the reporter resumed into Hyprland's crashed-lockscreen failsafe and the unlocked-desktop observation belongs to the second reporter's idle and manual locks, so the symptom now follows the sources. The cause said no fix was proposed, but PR #11811 (2026-09-14) was, folded into #12064 and then into #12245, which is open and unmerged, so the record now says that. The fix and verify told the reader to run omarchy-hyprland-session-locked after a suspend or lock, which means from a TTY or ssh, where hyprctl exits with HYPRLAND_INSTANCE_SIGNATURE not set (hyprctl/src/main.cpp at v0.56.2, lines 512 to 516) and the script therefore returns 2 every time. The corrected fix exports the signature the way omarchy-restart-shell does, and separates the exit 0 case, which is a stranded lock and belongs to the existing record plugin-file-write-while-locked-strands-session, from the latch. The danger claimed there was no way back over ssh, which the corpus's own stranded-lock record contradicts, so it now says you cannot authenticate out of it from there. Severity stays high, against the brief's scale: the consequence is a session left unlocked while every check reports it locked, which is private data exposed to anyone with physical access, and critical is reserved for an unauthenticated remote or radio-range path. It is not medium, because the control is not merely off, it is reported present while absent. Frequency stays occasional: two reporters, no reproduction on demand. Nothing was exercised: no lock, no shell restart, no hyprctl beyond a read-only -j monitors to confirm solitaryBlockedBy exists on Hyprland 0.56.2. Re-checked against 4.0.4-1 2026-09-19: Re-checked on omarchy 4.0.4-1 (pacman -Q) against the v4.0.4 tag, commit c668141e9c42b13c80c9ca4ea108e11708c5e8a5. The latch is still present: /usr/share/omarchy/shell/plugins/lock/Service.qml is byte-identical to the v4.0.4 tag and has the same git blob (9ecb1cc) at v4.0.2 and v4.0.3, and the v4.0.2...v4.0.4 compare does not touch it. Traced in the QML: locked at line 37 is lockRequested OR the compositor's answer, beginLock sets lockRequested at line 135, the lock IPC at lines 513 to 516 returns ok without calling beginLock again while locked is true, isLocked at 519 to 521 reads the same property, and only finishUnlock (151) and onLockStateChanged (255) clear it, so one stalled request still makes every later lock request report success without locking. omarchy-system-lock, omarchy-system-sleep-lock, omarchy-restart-shell, omarchy-hyprland-session-locked and omarchy-system-lid-close are unchanged between the tags and match the installed files, and the restart-shell relock logic at lines 28 to 37 still behaves as the fix and danger describe. What 4.0.3 changed near this (the plugin authentication boundary in PR #10733, keepLoaded for the lock service across plugin reloads, and PATH hardening in omarchy-apply-lock) does not touch the latch, and no code calls the lock service through the shell's service map, so moving it out of that map changed nothing here. Three things needed updating. The idle service's screensaver gate moved from line 68 to line 69, because 4.0.3 rewrote two lines above it. PRs #11811 and #12064 are now closed unmerged, not only folded, and #12245 is still open. And quattro's Service.qml at e38c1d1 is no longer identical to v4.0.4, because video wallpaper support landed there, but the three latch sites are unchanged at lines 45, 86 and 585. Issue #10299 is open as of 2026-09-19. Nothing was exercised: no lock, no shell restart, no lock IPC call, no suspend.
>
> *The Cause above was rewritten on 2026-09-19 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** Do not mute or dismiss the critical "Screen did not lock before suspend" notification that `omarchy-system-sleep-lock` sends. It is the only signal this bug gives before a laptop that looked suspended turns out to have been sitting unlocked. `omarchy-restart-shell` behaves differently depending on what `omarchy-hyprland-session-locked` reports at the moment it runs. When Hyprland holds a lock and the shell does not report one, for example a stale locker left behind by a crashed shell, the restart relocks the session, and over ssh that leaves you with a lock you cannot authenticate out of from there. Check that exit code first, and run the restart from the machine itself when you cannot. `omarchy-system-sleep-lock` fails open on purpose and caps its own wait at 12 seconds, so raising `InhibitDelayMaxSec` does not turn the lock into a veto on suspend.

**Fix.**

No upstream fix has merged as of 2026-09-19. `shell/plugins/lock/Service.qml` is byte-identical at the v4.0.2, v4.0.3 and v4.0.4 tags. The fix PRs #11811 and #12064 were closed unmerged, and #12245, which carries their work, is still open. Until one lands, treat `omarchy-shell lock isLocked`, `omarchy-shell lock status` and a zero exit from `omarchy-system-lock` or `omarchy-system-sleep-lock` as unproven, and ask the compositor instead.

The visible test comes first: a lock that took shows a password field. If the desktop is still on screen after a lock request, confirm the latch from a terminal in the session:

```bash
omarchy-shell lock status | jq '{requested, sessionLocked, secure, lastEvent}'
omarchy-hyprland-session-locked; echo $?
```

`requested: true` with `sessionLocked: false` and `secure: false` that does not change within a second or two is the latched state. Exit 0 from `omarchy-hyprland-session-locked` means Hyprland itself holds an `ext-session-lock`. Exit 1 means it does not, whatever the shell says. Exit 2 means it could not tell, which happens when a monitor has no workspace yet or when `hyprctl` cannot reach the compositor, and is not a verdict either way.

From a TTY or over ssh `hyprctl` has no instance to talk to, so the check exits 2 every time. Give it the running instance first, the same way `omarchy-restart-shell` does, and run the `omarchy` commands from a login shell (`bash -l`) so `OMARCHY_PATH` is set:

```bash
export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t "${XDG_RUNTIME_DIR:-/run/user/$UID}/hypr" | head -n 1)
omarchy-hyprland-session-locked; echo $?
```

If the compositor reports not locked (exit 1) while the shell claims otherwise, clear the latch by replacing the shell, then lock again:

```bash
omarchy-restart-shell
omarchy system lock
```

`omarchy-restart-shell` runs the same compositor check itself. On exit 1 it does not relock, so it only replaces the stuck shell with a fresh one whose lock service starts clean, and the `omarchy system lock` that follows is the real lock. A password field should now be on screen, and from a TTY or ssh `omarchy-shell lock status` should show `"sessionLocked":true,"secure":true`.

If instead the compositor reports locked (exit 0) and no password field is on screen, this is not the latch but a stranded lock: Hyprland is holding a lock whose client is gone. `omarchy-restart-shell` refuses while the shell still reports `requested` or `secure`, and relocks a fresh shell when it does not. That recovery, with its own risks, is the record `plugin-file-write-while-locked-strands-session`.

**Verify.** After a lock, from a TTY or over ssh as the session user, in a login shell:

```bash
export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t "${XDG_RUNTIME_DIR:-/run/user/$UID}/hypr" | head -n 1)
omarchy-hyprland-session-locked; echo $?
omarchy-shell lock status | jq '.sessionLocked, .secure'
```

Exit 0 together with `true` and `true` means the compositor holds the lock and the shell's locker is live behind it, the only state in which the desktop is not exposed. Exit 1 or 2, or `requested: true` with both values false, means the session is not secured, whatever `isLocked` says.

Sources: <https://github.com/omacom/omarchy/issues/10299> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/shell/plugins/lock/Service.qml> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-system-lock> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-system-sleep-lock> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-hyprland-session-locked> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-restart-shell> · <https://github.com/omacom/omarchy/pull/11811> · <https://github.com/omacom/omarchy/pull/12064> · <https://github.com/omacom/omarchy/pull/12245> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/shell/plugins/lock/Service.qml> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-system-sleep-lock> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-restart-shell> · <https://github.com/hyprwm/Hyprland/blob/v0.56.2/hyprctl/src/main.cpp> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/shell/plugins/services/idle/Service.qml> · <https://github.com/omacom/omarchy/blob/e38c1d1289252d2adb96372eeac48d02e489c5b7/shell/plugins/lock/Service.qml> · <https://github.com/omacom/omarchy/compare/v4.0.2...v4.0.4>

---

## LocalSend's firewall rule on Omarchy opens port 53317 to any address, not just the LAN

`localsend-firewall-rule-open-to-anywhere-ipv6` · severity: **medium** · frequency: **very-common** · applies to: `desktop`, `laptop`, `omarchy`

**Symptom.** is it safe that LocalSend opens port 53317 on my firewall. `sudo ufw status verbose` lists 53317/tcp and 53317/udp allowed from Anywhere, including the (v6) rows, on a fresh install and on one where LocalSend has never been opened.

**Cause.** `install/config/firewall.sh`, run during installation, adds one rule per protocol with no `from` clause:

```bash
ufw allow 53317/udp
ufw allow 53317/tcp
```

A bare `ufw allow` with no `from` clause matches Anywhere on both IPv4 and IPv6. LocalSend ships in `omarchy-base.packages`, so the rule lands on every stock install whether or not LocalSend is ever launched. Many home ISPs and mobile carriers hand a machine a globally routable IPv6 address directly, with no NAT boundary the way IPv4 usually has one, so the rule reaches the public internet rather than only the LAN a file sharing tool like this is meant for. On a shared network such as a hotel, conference, or coworking Wi-Fi, the same rule reaches every other guest on that segment too, because a private (RFC1918) range is not the same thing as a trusted one.

> **Audit corrected this record.** Gate 1 holds: the rule was published by third parties before this repository wrote anything about it, in PR 10766 (danjonesio, 2026-09-08), issue 11560 (CRTFD-DVLPR, 2026-09-12) and PRs 11561 and 11565, none of them authored by the account this repository uses, and the rule itself is two lines of public installer code. All three PRs are open and unmerged at the pinned sha d174d4a, which is the quattro tip as of 2026-09-18, so the defect is current. Gate 2 holds: every condition in symptom, cause and fix traces to the issue body, the 2026-09-14 comment, firewall.sh or omarchy-base.packages line 75, and the record repeats none of the comment's avahi-browse detail. Gate 3 holds, the record is a mitigation. Confirmed on this workstation: /usr/share/omarchy/install/config/firewall.sh is byte-identical to the pinned sha, IPV6=yes at /etc/default/ufw line 7, and /etc/ufw/user.rules lines 20 to 24 and /etc/ufw/user6.rules lines 20 to 24 carry the four 53317 ACCEPT tuples from 0.0.0.0/0 and ::/0. Nothing else under /usr/share/omarchy mentions 53317, so no migration puts the rule back after a user removes it. Two defects. First, verify is wrong: a rule with an IPv4 from address is an IPv4-only rule (ufw parser.py sets the rule type to v4 and frontend.py calls set_v6(False) for it), so after the fix there is no (v6) row for 53317 at all, and a reader told to expect scoped (v6) rows would conclude the fix failed. The fix's delete step is correct: ufw(8) says a delete that repeats the original rule removes both the IPv4 and the IPv6 entry. Second, severity high does not meet the brief's scale. With LocalSend closed nothing listens, and with it open LocalSend's own defaults (HTTPS on, persistence_provider.dart line 494, quick save defaulting to paired devices only, line 458) mean a stranger gets the device alias and model from the info endpoint and can offer a transfer the user must accept. No credential, privilege boundary or private data is exposed by default, so this is a default weaker than the norm, which the scale calls medium. Danger was empty and now names the two ways the fix itself bites: LocalSend stops receiving until the rules are back, and the scoped rules are IPv4-only. The title's phrase the whole internet overstates a rule that only reaches the internet on a machine with a globally routable address, but the verdict schema has no corrected_title. Not exercised: no ufw command was run and nothing on the network was probed. Re-checked against 4.0.4-1 2026-09-19: Re-checked on 2026-09-19 against Omarchy 4.0.4-1 on this workstation and against the v4.0.4 tag, sha c668141. install/config/firewall.sh at v4.0.4 is byte-identical to the installed copy and to the previously pinned d174d4a, and still carries ufw allow 53317/udp and ufw allow 53317/tcp with no from clause. localsend is still line 75 of install/omarchy-base.packages. Confirmed on this machine by reading files only: IPV6=yes at /etc/default/ufw line 7, and the four 53317 ACCEPT tuples from 0.0.0.0/0 and ::/0 at /etc/ufw/user.rules lines 20 to 24 and /etc/ufw/user6.rules lines 20 to 24. The v4.0.2 to v4.0.4 compare touches neither firewall.sh nor the packages list, and no migration in v4.0.4 mentions 53317, so omarchy update still does not put the wide rule back. The only other code path that runs firewall.sh is omarchy-upgrade-to-quattro, the one-time Omarchy 3 to 4 upgrade, which means a machine upgraded from Omarchy 3 also carries the rule, consistent with the record's every stock install. Issue 11560 and PRs 10766, 11561 and 11565 are all still open and unmerged. PR 11561 gained a migration on 2026-09-15 that would scope existing rules, and nothing of it has shipped. manual/48-security.md line 6 and manual/35-networking.md line 31 at v4.0.4 state port 53317 is the one inbound exception, which adds a documented-default source for gate 1. The manual is not installed under /usr/share/omarchy, so the record's claim that nothing there but firewall.sh mentions 53317 still holds. Severity medium and frequency very-common still fit the brief's scale. Gates 1, 2 and 3 still hold. Not exercised: no ufw command was run and nothing on the network was probed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** Deleting the rules stops LocalSend from receiving on any network until they are added back, and the scoped rules are IPv4-only, so a peer that can reach you only over IPv6 cannot send to you. Do not answer either by turning the firewall off with `sudo ufw disable`, which drops the default deny along with everything else.

**Fix.**

Replace the blanket rule with rules scoped to the private IPv4 ranges. Deleting by repeating the original rule removes the IPv4 and the IPv6 entry together:

```bash
sudo ufw delete allow 53317/udp
sudo ufw delete allow 53317/tcp
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do
  sudo ufw allow from "$net" to any port 53317 proto tcp
  sudo ufw allow from "$net" to any port 53317 proto udp
done
```

This closes the globally routable IPv6 case, the more serious one, because a public IPv6 address is in none of those ranges. Nothing in `/usr/share/omarchy` other than the installer's `firewall.sh` mentions port 53317, so `omarchy update` does not put the wide rule back.

It does not make a shared private network trustworthy. A hotel, conference or coworking network hands out addresses inside those ranges too. Before joining one, remove the scoped rules as well, and add them back only while you are actually transferring a file:

```bash
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do
  sudo ufw delete allow from "$net" to any port 53317 proto tcp
  sudo ufw delete allow from "$net" to any port 53317 proto udp
done
```

**Verify.** `sudo ufw status verbose` lists `53317/tcp` and `53317/udp` as ALLOW IN from `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16`, and shows no `Anywhere` row and no `(v6)` row for 53317. A rule with an IPv4 `from` address is IPv4-only, so the absence of `(v6)` rows is the expected result, not a failure. After you have closed the port for an untrusted network, no rule for 53317 is listed at all.

Sources: <https://github.com/omacom/omarchy/issues/11560> · <https://github.com/omacom/omarchy/blob/d174d4aa279ea7393d4fad4a80fed147866106b9/install/config/firewall.sh> · <https://github.com/omacom/omarchy/blob/d174d4aa279ea7393d4fad4a80fed147866106b9/install/omarchy-base.packages> · <https://github.com/omacom/omarchy/pull/10766> · <https://github.com/localsend/localsend/blob/230fb692962668ca22ce0e61a8f53ce1cfd32102/app/lib/provider/persistence_provider.dart> · <https://github.com/localsend/protocol/blob/62bd3406ec80d62f2ed46269cdc06c4dcc391083/README.md> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/install/config/firewall.sh> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/manual/48-security.md>

---

## What reviewing a PKGBUILD before installing from the AUR actually means

`pkgbuild-review-before-building-from-aur` · severity: **medium** · frequency: **common** · applies to: `arch`, `desktop`, `laptop`, `omarchy`

**Symptom.** how do I actually review an AUR package before installing it, does yay show me anything automatically or do I have to do it by hand

**Cause.** Arch's own wiki lists verifying the PKGBUILD as the most important step in installing anything from the AUR, and is specific about what that means: check the PKGBUILD itself, any `.install` files, and any other files in the package's repository, "particularly for sections that may pull software code from outside the repositories," because, in the wiki's own words, "malicious code may be signed, therefore you must vet the PKGBUILD." Omarchy installs yay, not paru, from its base package list. yay automates part of this review through two settings that most people never look at, and the two do not behave the same way. `diffmenu` defaults to true, confirmed by reading yay v13.0.1's own `DefaultConfig` in `pkg/settings/config.go`. `editmenu` defaults to false in the same struct. yay's diff menu, read in `pkg/menus/diff_menu.go`, diffs against git's empty tree when a package base has never been reviewed before, so a first time install is shown as one large "everything added" diff, and diffs against the last reviewed commit on every later update, skipping a package outright if nothing changed since. The edit menu, which actually opens the files in an editor, only runs if you turn it on. Both settings can also be set from `~/.config/yay/init.lua`, which yay 13.0.1 overlays on `config.json`.

> **Audit corrected this record.** The sharp claim holds, read at the pinned commit and never run. 02fb6ba9 is the commit the v13.0.1 tag resolves to and pacman -Q yay is 13.0.1-1 here, so the source and the installed binary match. pkg/settings/args.go maps --noconfirm to settings.NoConfirm, pkg/sync/workdir/preparer.go registers menus.DiffFn only when cfg.DiffMenu is true, DiffFn calls selectionMenu with settings.NoConfirm and run.Cfg.AnswerDiff, whose DefaultConfig value is the empty string, GetInput in pkg/text/input.go returns the default at once when noConfirm is true, ParseNumberMenu in pkg/intrange/intrange.go turns the empty string into no words, selectionMenu in pkg/menus/menu.go then selects nothing, and DiffFn returns before any git diff when toDiff is empty. The record cited input.go for a chain that mostly lives in menu.go, intrange.go, args.go and preparer.go, so those are appended. DefaultConfig confirmed DiffMenu true and EditMenu false, diff_menu.go confirmed the empty-tree and AUR_SEEN behaviour, and doc/yay.8 confirmed --editmenu and --diffmenu. Three gate 2 defects. The cause says the wiki calls review 'the single most important step', the wiki says 'the most important step'. The fix says .install functions 'run as root under pacman -U', which neither cited source states, so the sentence now says what the PKGBUILD wiki page says, that pacman runs the four functions at install time, and that pacman -U is a root command per the wiki's own install step. The verify says no config.json key means the built in default, but doc/lua.md at the same commit says init.lua overlays config.json and can set diff_menu and edit_menu, so the verify now reads yay -Pg, which prints the loaded configuration as JSON via Configuration.String. The danger names dotfiles scripts and misses that on Omarchy 4.0.2-1 the stock AUR installer bin/omarchy-pkg-aur-install ends in yay -S --noconfirm and bin/omarchy-update-aur-pkgs runs yay -Sua --noconfirm, both byte-identical to the v4.0.2 tag commit, so the stock paths are the main case, and the picker's alt-b PKGBUILD preview is the review point on that path. A sentence was added so the fix does not read as making a package safe. Severity medium stands: the control is on by default and off only on paths that pass --noconfirm, and a malicious package still needs the user to pick it. Not exercised: no yay install, no --noconfirm run, no AUR clone, and the Lua overlay order relative to -Pg was read from doc/lua.md rather than traced through pkg/runtime. Re-checked against 4.0.4-1 2026-09-19: Rechecked on omarchy 4.0.4-1, read and never run. The installed /usr/bin/omarchy-pkg-aur-install and /usr/bin/omarchy-update-aur-pkgs are byte-identical to the v4.0.4 tag, c668141e9c42b13c80c9ca4ea108e11708c5e8a5. omarchy-pkg-aur-install line 26 still ends in xargs yay -S --noconfirm, and omarchy-update-aur-pkgs line 8 still runs yay -Sua --noconfirm with --cleanafter and --ignore gcc14,gcc14-libs. Neither passes --answerdiff, --diffmenu or --editmenu, and nothing under /usr/share/omarchy ships a yay configuration. The only change to either script between v4.0.2 and v4.0.4 is the updatedb line in omarchy-pkg-aur-install (pull request 10579), which does not touch the yay call. /usr/bin/omarchy-update line 50 still calls omarchy-update-aur-pkgs, the menu's install.aur entry still runs omarchy-pkg-aur-install, and the picker still binds alt-b to yay -Gpa. pacman -Q yay is still 13.0.1-1, which is still yay's latest release, and the v13.0.1 tag still resolves to 02fb6ba9. Re-read at that commit: DefaultConfig keeps DiffMenu true, EditMenu false and AnswerDiff empty, and GetInput in pkg/text/input.go returns the default at once when noConfirm is true, so the danger holds unchanged. The only defect is the version labels: the danger and verify named 4.0.2-1 alone, which reads as if 4.0.3 or 4.0.4 changed it. Both now say 4.0.2-1 through 4.0.4-1, and v4.0.4 sources are appended. Not exercised: no yay run, no AUR install, and yay -Pg was not run because the claim does not depend on this machine's yay configuration.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** `--noconfirm` silently removes the diff review, and on Omarchy 4.0.2-1 through 4.0.4-1 both stock AUR paths use it: `omarchy-pkg-aur-install`, which the menu's Install then AUR entry runs, ends in `yay -S --noconfirm`, and `omarchy-update-aur-pkgs`, which `omarchy update` calls, runs `yay -Sua --noconfirm`. Read from yay v13.0.1's own source: `--noconfirm` sets `settings.NoConfirm` (`pkg/settings/args.go`), the diff selection prompt calls `GetInput(defaultAnswer, noConfirm)` (`pkg/menus/menu.go`), and when `noConfirm` is true `GetInput` in `pkg/text/input.go` returns the default answer immediately with no prompt shown at all. The default answer for the diff menu, `answerdiff`, is an empty string, and an empty selection picks zero packages to diff, so `yay -S --noconfirm <pkgname>`, the two Omarchy scripts, or any dotfiles script, provisioning tool, or shell alias that adds `--noconfirm` to an AUR install, builds and installs with no diff ever printed and no chance to abort, even though diffmenu is on. Script an unattended AUR install by fetching and diffing the PKGBUILD yourself first, not by trusting `--noconfirm` to still show it to you.

**Fix.**

Acquire the build files and read them before running `makepkg` or letting a helper run it for you:

```bash
git clone https://aur.archlinux.org/<pkgname>.git
cd <pkgname>
less PKGBUILD
```

Read every `.install` file too. pacman runs its `pre_install`, `post_install`, `pre_upgrade` and `post_upgrade` functions while it installs the package, and the install step, `pacman -U`, is a root command, so nothing in those functions is confined to your own account. Look specifically at the `source=()` array, `prepare()` and `build()` for anything that pulls code from outside the AUR's own repository, and at `validpgpkeys` if the package checks a signature, since a signed package can still be malicious.

On an update, diff against what you last reviewed instead of rereading the whole file:

```bash
git show
# or, to see the full file with change markers inline
git difftool @~..@ --tool=vimdiff
```

yay does the diff step for you by default when you run it yourself, both on first install (against an empty tree, so you see everything) and on every update after that (against your last reviewed commit). It does not open the files for you to actually read, because `editmenu` defaults to off. Turn it on for a run you want to look at closely:

```bash
yay --editmenu -S <pkgname>
```

or persist it by adding `"editmenu": true` to `~/.config/yay/config.json`.

On Omarchy, the menu's Install then AUR entry and `omarchy update` both run yay with `--noconfirm`, so neither shows a diff. In the installer's picker press `alt-b` to read the PKGBUILD in the preview pane before you select the package. For updates, run `yay -Sua` yourself when you want the diff.

A review lowers the risk. It does not make a package safe: a PKGBUILD you understood can still fetch a compromised upstream archive.

**Verify.** Print the configuration yay is actually running with. This reflects `~/.config/yay/config.json` and `~/.config/yay/init.lua`, which overlays it, and a dotfiles repo can have changed either:

```bash
yay -Pg | grep -E '"(diffmenu|editmenu)"'
```

yay 13.0.1's built in defaults are diffmenu true and editmenu false. Then confirm which Omarchy paths skip the diff regardless. On 4.0.2-1 through 4.0.4-1 expect two hits:

```bash
grep -n -- '--noconfirm' /usr/share/omarchy/bin/omarchy-pkg-aur-install /usr/share/omarchy/bin/omarchy-update-aur-pkgs
```

Sources: <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/pkg/settings/config.go> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/pkg/menus/diff_menu.go> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/pkg/text/input.go> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/doc/yay.8> · <https://wiki.archlinux.org/title/PKGBUILD> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/pkg/menus/menu.go> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/pkg/intrange/intrange.go> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/pkg/settings/args.go> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/pkg/sync/workdir/preparer.go> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/doc/lua.md> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-pkg-aur-install> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-update-aur-pkgs> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/default/omarchy/omarchy-menu.jsonc> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-pkg-aur-install> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-update-aur-pkgs> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-update> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/default/omarchy/omarchy-menu.jsonc>

---

## Re-enable a legacy SSH key exchange or ssh-rsa for one host, not every connection

`ssh-legacy-kex-or-rsa-refused-after-upgrade` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ssh refuses a server it used to reach, with `Unable to negotiate with <host> port 22: no matching key exchange method found` or `Unable to negotiate with <host> port 22: no matching host key type found`, each followed by `Their offer:` and the list the server proposed, right after an OpenSSH update. The advice that turns up online is to drop a `PubkeyAcceptedAlgorithms`, `HostKeyAlgorithms` or `KexAlgorithms` line into `/etc/ssh/ssh_config` so it stops happening again.

**Cause.** OpenSSH has turned off or removed several algorithms across a series of releases, each documented in that release's own notes: release 7.0 (2015) disabled the 1024-bit `diffie-hellman-group1-sha1` key exchange and `ssh-dss` keys by default, release 8.2 (2020) removed `diffie-hellman-group14-sha1` from the default key exchange proposal and dropped `ssh-rsa` from the accepted certificate signature algorithms, and release 8.8 (2021) disabled the SHA-1 `ssh-rsa` signature for host and user authentication by default. Release 10.0 (2025) then removed DSA entirely. On this machine, openssh 10.5p1-1, `ssh -Q kex` still lists `diffie-hellman-group1-sha1` and `diffie-hellman-group14-sha1`, and `ssh -Q HostKeyAlgorithms` and `ssh -Q PubkeyAcceptedAlgorithms` still list `ssh-rsa`, so those three are only left out of what the client offers by default and can be added back. `ssh -Q key` lists no `ssh-dss` at all, so a server that offers only DSA host keys cannot be reached from this client by any configuration. A server that has not been reconfigured or upgraded since one of those releases, common on older network gear and appliances, ends up with no algorithm in common with a current client, and the client says so, naming what the server proposed: `Unable to negotiate with <host> port <port>: <reason>. Their offer: <list>`. `PubkeyAcceptedAlgorithms` is the current name of the option, renamed from `PubkeyAcceptedKeyTypes` in release 8.5. The old name is still read as an alias on 10.5p1, but the manual on this machine documents only the new one.

> **Audit corrected this record.** Held against openssh 10.5p1-1 on omarchy 4.0.2-1 by reading only: man 5 ssh_config on this machine, ssh -Q kex, key, sig, HostKeyAlgorithms and PubkeyAcceptedAlgorithms, ssh -G against a placeholder host, and the OpenSSH 7.0, 8.2, 8.5, 8.8 and 10.0 release notes plus the pinned packet.c, ssherr.c, readconf.c and sshconnect2.c. The fix holds: the + append syntax, the option names HostKeyAlgorithms, PubkeyAcceptedAlgorithms and KexAlgorithms, and first-value-wins ordering are all in the installed manual, the Host old-host stanza is the 8.8 release notes' own example, and readconf.c dump_client_config expands HostKeyAlgorithms so the verify's ssh -G check shows the appended algorithm. PubkeyAcceptedAlgorithms is the right name: renamed from PubkeyAcceptedKeyTypes in 8.5, the old name is still read as an obsolete alias in readconf.c and the manual on this machine documents only the new one. Wrong: the cause says none of the algorithms were deleted from what the binary can do, but release 10.0 removed DSA entirely and ssh -Q key on 10.5p1-1 lists no ssh-dss, so a server offering only DSA host keys cannot be reached by any configuration. Wrong: ssh -Q key lists key types, not signature algorithms, so it is the wrong list to cite for ssh-rsa, though ssh -Q HostKeyAlgorithms and ssh -Q PubkeyAcceptedAlgorithms do list it. Wrong: the quoted error omits the port, packet.c prints Unable to negotiate with <addr> port <port>: <reason>. Their offer: <list>, and the reason strings match ssherr.c. Wrong: the danger says both DH groups were removed in 'those same two releases' right after naming 8.2 and 8.8, and group1-sha1 was 7.0. Symptom, cause and danger rewritten, fix kept as is, severity lowered to medium: no default is weak, the control is the algorithm list and a scoped + line weakens one host by a SHA-1 collision that needs an on-path attacker with substantial compute, which is the brief's medium. Gate 1 passes on release notes and the manual, gate 3 passes. No overlap in problems.jsonl: no record mentions KexAlgorithms, HostKeyAlgorithms, PubkeyAccepted or either negotiate error.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** A `HostKeyAlgorithms`, `PubkeyAcceptedAlgorithms` or `KexAlgorithms` line placed under `Host *`, or written without the leading `+` so it replaces the default list rather than extending it, weakens every SSH connection the machine makes, not only the one that needed it. `ssh-rsa` signs with SHA-1, which OpenSSH's own release 8.2 and 8.8 notes say can be forged with a chosen-prefix collision for under USD 50,000, and that is the stated reason OpenSSH stopped offering it by default. `diffie-hellman-group1-sha1` was removed from the default key exchange proposal in release 7.0 and `diffie-hellman-group14-sha1` in release 8.2, and both hash with the same SHA-1. A replacing `HostKeyAlgorithms` list has a second cost: the client stops preferring the key types it already holds in `known_hosts` for a host, which is one way to earn the changed-host-key warning covered by `ssh-host-key-warning-after-algorithm-order-change`. A `+` line keeps that preference.

**Fix.**

Re-enable the one algorithm the old server needs, for that one server, in `~/.ssh/config`, using the `+` syntax OpenSSH documents for exactly this purpose: appending to the default set rather than replacing it. This is the same shape OpenSSH's own release 8.8 notes give as the recommended stopgap:

```
# ~/.ssh/config
Host old-host
    HostKeyAlgorithms +ssh-rsa
    PubkeyAcceptedAlgorithms +ssh-rsa
```

For a key exchange failure, append the specific algorithm the server offered instead, read from the client's own error message rather than guessed:

```
# ~/.ssh/config
Host old-host
    KexAlgorithms +diffie-hellman-group14-sha1
```

Put this under a `Host` block naming the one server, placed before any wider `Host *` block. `man 5 ssh_config` says the file is read in order and the first value given for a directive wins, so a narrow block has to come first to take effect. Never write a `+`-less, replacing `HostKeyAlgorithms`, `PubkeyAcceptedAlgorithms` or `KexAlgorithms` line, and never place any of the three under `Host *` or directly in `/etc/ssh/ssh_config` with no `Host` restriction. Either mistake re-enables the weak algorithm for every host the machine ever connects to, not only the one that still needs it. Treat the re-enabled line as temporary: OpenSSH's own notes recommend it only until the remote side can be upgraded or reconfigured with a current key type.

**Verify.** `ssh -G old-host | grep -i 'hostkeyalgorithms\|kexalgorithms\|pubkeyacceptedalgorithms'` lists the legacy algorithm in the output for that one host, and the same command run against an unrelated host on the same machine does not list it, confirming the change stayed inside the `Host old-host` block instead of reaching `Host *`.

Sources: <https://man.openbsd.org/ssh_config.5> · <https://www.openssh.com/txt/release-7.0> · <https://www.openssh.com/txt/release-8.2> · <https://www.openssh.com/txt/release-8.8> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/packet.c> · <https://www.openssh.com/txt/release-8.5> · <https://www.openssh.com/txt/release-10.0> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/ssherr.c> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/readconf.c> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/sshconnect2.c>

---

## Arch's own advisory: AUR packages have shipped real malware more than once

`aur-has-shipped-malware-more-than-once` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `desktop`, `laptop`, `omarchy`

**Symptom.** is it safe to install packages from the AUR, has the AUR actually ever shipped malware or is that just a rumour

**Cause.** The AUR is unmoderated user submitted content, and Arch says so on its own wiki: "AUR packages are user-produced content. These PKGBUILDs are completely unofficial and have not been thoroughly vetted. Any use of the provided files is at your own risk." That is not a hypothetical. Arch's own aur-general mailing list and its own news page record real, dated incidents, not a single one. A package named acroread was reported compromised on 2018-07-08. Three packages, named firefox-patch-bin, librewolf-fix-bin and zen-browser-patched-bin, were uploaded on 2025-07-16, reported on the list on 2025-07-18 as installing a remote access trojan, and deleted the same day. Arch published its own advisory, titled "Active AUR malicious packages incident" and dated 2026-06-12, stating: "We are currently experiencing a high volume of malicious package adoptions and updates in the Arch User Repository," and warned that while it worked on a more permanent solution users "may see issues with" creating new AUR accounts, pushing package updates, and adopting or creating new packages. The wiki's own warning links seven such threads. Omarchy installs yay, an AUR helper, from its own base package list (install/omarchy-base.packages) on every stock install, so a stock Omarchy desktop already has the tool that reaches this content. The stock install itself carries no AUR package (`pacman -Qm` is empty on a fresh 4.0.2-1), so AUR content reaches a machine only when the user asks for it, and two of the stock ways of asking, the Omarchy menu's Install then AUR entry and `omarchy update`, run yay with `--noconfirm`, which skips yay's diff menu entirely.

> **Audit corrected this record.** All three incident dates hold against their primary sources, read in full: the acroread thread is dated July 8, 2018 on lists.archlinux.org, the RAT thread is dated July 18, 2025 and says the uploads happened on 16 July and the packages were deleted on 18 July, and the news post carries datePublished 2026-06-12 by Campbell Jones. The wiki warning is quoted verbatim from the Arch_User_Repository page, which also names aur-general as used for security warnings and links seven incident threads, so the record understates rather than overstates. Gate 2 fails on the advisory: the record says Arch 'temporarily disabled' new accounts, updates and adoption, and the danger calls it 'a temporary lockdown on the AUR itself', but the advisory says only that 'users may see issues with the following' while a more permanent solution is built, and never says disabled. The danger's claim that Arch's response to each incident was 'a mailing list post and a temporary lockdown' is unsupported for 2018 and 2025, where the thread records deletion of the packages and no lockdown. Omarchy ships yay and not paru: pacman -Q yay is 13.0.1-1 here, paru is not installed, and install/omarchy-base.packages carries yay at line 147 on this machine and byte-identical at the v4.0.2 tag commit 346e69e1. The line number was removed from the prose because quattro HEAD already has it at line 150. The record misses the Omarchy-specific fact that matters: bin/omarchy-pkg-aur-install, which the menu's Install then AUR entry runs, ends in yay -S --noconfirm, and bin/omarchy-update-aur-pkgs runs yay -Sua --noconfirm, both identical between this machine and the v4.0.2 commit, so on both stock paths yay's diff menu never appears whatever diffmenu is set to, and the verify's config.json check answered the wrong question. The picker does offer the PKGBUILD by alt-b through yay -Gpa before selection, and the corrected fix says so. yay 13.0.1 also overlays init.lua on config.json per doc/lua.md, so the verify now reads yay -Pg. Severity moved to medium: pacman -Qm is empty on this stock install, no default reaches the AUR, and a malicious package needs the user to pick it, so no default leaves a credential or privilege boundary exposed. Gate 1 passes on Arch's own advisory and list, gate 3 passes because the record names deleted packages and reproduces neither the compromised commit the 2018 thread links nor how either payload worked. Nothing was exercised: no package was fetched or built and no yay command was run beyond --version.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** A high vote count, a quiet comment section, or a maintainer name that sounds familiar are not security signals. None of them are cryptographic, and none of them stopped the incidents this record cites. Each was caught after the fact by a person reading the package and writing to aur-general, and Arch's 2026 advisory asks users to keep doing exactly that. On Omarchy the two stock paths, the menu's AUR installer and `omarchy update`, both run yay with `--noconfirm`, so yay's own diff review never appears there whatever your yay configuration says, and a package you did not read before selecting it is a package you did not read.

**Fix.**

Read the PKGBUILD and any `.install` files yourself before every AUR install or update, rather than trusting a vote count or an empty comment section. The companion record `pkgbuild-review-before-building-from-aur` covers exactly what to look at and what yay's diff and edit menus do and do not show you by default.

On Omarchy, know which of the stock paths shows you anything. The menu's Install then AUR entry runs `omarchy-pkg-aur-install`, whose picker has an `alt-b` binding that prints the package's PKGBUILD in the preview pane (`yay -Gpa`). Read it there, because the install that follows your selection is `yay -S --noconfirm` and prints no diff. `omarchy update` runs `yay -Sua --noconfirm` for every installed AUR package and prints no diff either. To see a diff before an update, run yay yourself:

```bash
yay -Sua
```

Subscribe to the channel Arch's own wiki names as the one used for security warnings in the past:

https://lists.archlinux.org/mailman3/lists/aur-general.lists.archlinux.org/

Do not treat a package that just changed maintainer through "adoption" as more trustworthy than a brand new one. Arch's 2026-06-12 advisory named "malicious package adoptions and updates" as the problem and said: "We continue to encourage all users of AUR packages to review all PKGBUILD and install script changes when updating, especially during this time." A freshly adopted package gets the same review as a package you have never seen before, not less.

A review lowers the risk. It does not make the package safe: a PKGBUILD you read and understood can still fetch a compromised upstream archive, which is why the wiki tells you to look hardest at the parts that "pull software code from outside the repositories."

**Verify.** Confirm which of your install paths will show you a diff, since the fix above depends on knowing that. On Omarchy 4.0.2-1 both stock scripts pass `--noconfirm`, so expect two hits:

```bash
grep -n -- '--noconfirm' /usr/share/omarchy/bin/omarchy-pkg-aur-install /usr/share/omarchy/bin/omarchy-update-aur-pkgs
```

For yay run by hand, print the configuration yay is actually using. This reflects `~/.config/yay/config.json` and `~/.config/yay/init.lua`, which overlays it:

```bash
yay -Pg | grep -E '"(diffmenu|editmenu)"'
```

yay 13.0.1's built in defaults are diffmenu true and editmenu false. See the companion PKGBUILD review record for what that default does and does not catch.

Sources: <https://archlinux.org/news/active-aur-malicious-packages-incident/> · <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://lists.archlinux.org/archives/list/aur-general@lists.archlinux.org/thread/FFCMZGL4UQODYKZGUY7KTN3UBF3XN66P/> · <https://lists.archlinux.org/archives/list/aur-general@lists.archlinux.org/thread/7EZTJXLIAQLARQNTMEW2HBWZYE626IFJ/> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/install/omarchy-base.packages> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-pkg-aur-install> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/bin/omarchy-update-aur-pkgs> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/default/omarchy/omarchy-menu.jsonc> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/doc/lua.md> · <https://github.com/Jguer/yay/blob/02fb6ba948720d2d7eae6e5989168a297710a3e4/doc/yay.8>

---

## omarchy-sudo-passwordless grants root to everything running as you, not just the tool that asked

`omarchy-sudo-passwordless-grants-root-to-every-process` · severity: **medium** · frequency: **occasional** · applies to: `omarchy`

**Symptom.** Is it safe to run `omarchy-sudo-passwordless` so an AI agent or a one-off script can call sudo without typing a password? Does the grant apply only to that tool, or to anything else running under my account until it expires?

**Cause.** `omarchy-sudo-passwordless` writes `/etc/sudoers.d/99-omarchy-nopasswd-<user>` containing `<user> ALL=(ALL) NOPASSWD: ALL` and arms a transient `systemd-run --on-active=<minutes>m` timer to delete that file, 15 minutes by default when no argument is given. A sudoers rule is scoped to the user, not to the process that asked for it, so every process already running as that user, a browser tab, a background daemon, a compromised dependency, can run `sudo` with no password for the whole window. The script's own confirmation prompt says this before you agree, printing the number of minutes in place of `${MINUTES}`: "This will allow ANY process running as your user to" "execute ANY command as root WITHOUT a password for ${MINUTES} minutes." and "Anyone or anything with access to your user account gets full root." On 4.0.2-1 and earlier the timer is the only thing that ends the grant on its own, and it is a transient unit that does not survive a reboot while the sudoers file does. The 4.0.2-1 script says so after enabling: "Note: if you restart before then, run omarchy-sudo-passwordless again to disable it." On 4.0.3 and later, 4.0.4-1 included, the grant also ends at the next boot, because `/etc/tmpfiles.d/omarchy-nopasswd-sudo.conf` removes any `99-omarchy-nopasswd-*` file during boot, and the script revokes the grant at once if it cannot arm the timer. The 4.0.4-1 script says after enabling: "A restart removes the passwordless sudo rule as well." Neither change narrows the grant. While it lasts it is still `NOPASSWD: ALL` for every process running as that user.

> **Audit corrected this record.** Read the installed /usr/bin/omarchy-sudo-passwordless on omarchy 4.0.2-1 and diffed it against upstream commit d2a4cc0c: byte-identical, and its safety block only removes a stale sudoers file on the next run, so the reboot claim holds for this version. Read commit 945af75 (2026-08-31 15:24 UTC, head of branch security/nopasswd-expiry-fail-closed), its tmpfiles rule and arm_expiry function, and PR 9387, which merged to quattro on 2026-09-07 and is in the v4.0.3 tag of 2026-09-08 whose release notes list it. The record's central claim that 4.0.2-1 is the latest released package on 2026-09-18 is false: the stable pacman repository at pkgs.omarchy.org carried omarchy and omarchy-settings 4.0.4-1, built 2026-09-15 21:04 UTC, and extracting both packages showed the 945af75 script and /etc/tmpfiles.d/omarchy-nopasswd-sudo.conf inside them. The harvester most likely read this workstation's sync database, last refreshed 2026-09-05. The build date is 2026-08-31 03:11 UTC, which pacman shows as 30 August in a Pacific timezone, so the fix landed about twelve hours after the build, not a day. The original verify was wrong on its own terms: an empty timer list is exactly the post-reboot state the danger warns about, so verify now checks for the file. The fix omitted that running the tool to clean up a stale file falls through to the enable prompt, and gum confirm's Default option is true (read from confirm/options.go in charmbracelet/gum), so Enter re-enables the grant. Gate 1 passes because the shipped script itself prints the reboot caveat and the upstream commit states it. Gates 2 and 3 pass. Severity lowered to medium: this is a user-invoked command with a printed warning, not a default, and the defect is the expiry control silently off after a reboot, reachable only by code already running as that user. Nothing was exercised: the tool was not run and no sudoers file was touched. Re-checked against 4.0.4-1 2026-09-19: Rechecked on omarchy 4.0.4-1, read and never run. /usr/bin/omarchy-sudo-passwordless (omarchy 4.0.4-1) and /etc/tmpfiles.d/omarchy-nopasswd-sudo.conf (omarchy-settings 4.0.4-1) are byte-identical to the v4.0.4 tag c668141e9c42b13c80c9ca4ea108e11708c5e8a5, to v4.0.3 and to commit 945af75a. The v4.0.3 to v4.0.4 compare touches neither file, so the record's account of the 4.0.3 change still describes 4.0.4. The 4.0.4 script still writes `<user> ALL=(ALL) NOPASSWD: ALL`, still defaults to 15 minutes, still prints the two quoted warnings, and arm_expiry at lines 16 to 27 removes the grant if systemd-run fails. The tmpfiles rule is `r! /etc/sudoers.d/99-omarchy-nopasswd-*`, and systemd-tmpfiles-setup.service on systemd 261.2-1 runs --create --remove --boot before sysinit.target, so removal is boot-only and does not depend on an age cleanup or the clean timer. test/shell.d/nopasswd-sudo-expiry-test.sh covers the two fail-closed paths and the boot-only rule against a disposable root. One claim was wrong for 4.0.4: the cause said the timer is the only thing that ends the grant, which is now false because boot also ends it, and it quoted only the 4.0.2-1 closing note, which 4.0.4 replaced with "A restart removes the passwordless sudo rule as well." The cause now labels both branches. The danger said "the installed 4.0.2-1 script", which is no longer what is installed, and now names PR 7990 (Adolanium, 2026-08-24, the first public statement of the reboot gap) and the credit commit b9657b63. gum is now 2.0.0-1, so the fix's Enter-defaults-to-Yes claim was re-read at gum v2.0.0 (4d089f95): confirm Default is still true, and the moving main-branch URL is removed. Title, fix, verify and severity still hold. Not exercised: the tool was not run, no sudoers file was read or touched, and no reboot was performed.
>
> *The Cause above was rewritten on 2026-09-19 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** On 4.0.2-1 and earlier, a reboot before the timer fires does not clear the grant. The 4.0.2-1 package's script is byte-identical to upstream commit d2a4cc0c4d60cd3bce866f65643f89f7d2978d5e. The transient systemd-run timer does not survive a reboot, and the script only removes a stale sudoers file the next time you run it yourself, so `/etc/sudoers.d/99-omarchy-nopasswd-<user>` stays in place and every process as that user keeps passwordless root until you remove the file as root or run the command again. Upstream changed this in commit 945af75aa2c0bf5b40a0155500f0774f06db6721 on 2026-08-31 at 15:24 UTC, about twelve hours after the 4.0.2-1 package was built at 03:11 UTC that day, a time `pacman -Qi` shows as 30 August in a Pacific timezone. It adds `/etc/tmpfiles.d/omarchy-nopasswd-sudo.conf`, which removes any leftover `99-omarchy-nopasswd-*` file during boot, and it revokes the grant immediately if the expiry timer cannot be armed. That change merged as pull request 9387 and is in the v4.0.3 tag of 2026-09-08, whose release notes list it. On 2026-09-18 the stable package repository carried omarchy and omarchy-settings 4.0.4-1, built 2026-09-15, and those packages contain the changed script and the tmpfiles rule. A machine that has not run `omarchy update` since 2026-09-08 still has the 4.0.2-1 behaviour, and a stale file present when you update is removed at the next boot, not at update time. The reboot gap was first raised publicly in pull request 7990 on 2026-08-24, and upstream credits _SiCk // afflicted.sh for independently reproducing it. On 4.0.4-1 the installed script and tmpfiles rule are byte-identical to 4.0.3 and to the v4.0.4 tag, c668141e9c42b13c80c9ca4ea108e11708c5e8a5. Do not clear a leftover grant by editing `/etc/sudoers` or the drop-in by hand. A syntax error in either locks every sudo call out. Delete the drop-in instead.

**Fix.**

Treat the window as a full root session for the account, not a scoped grant for one tool. Ask for the fewest minutes the task actually needs rather than accepting the 15-minute default:

```bash
omarchy-sudo-passwordless 2
```

Turn it off the moment the task finishes instead of waiting out the timer. While the grant is live, running the command with no argument removes the sudoers file and stops the timer:

```bash
omarchy-sudo-passwordless
```

If the machine rebooted while a grant was live on 4.0.2-1 or earlier, the timer is gone and the sudoers file is still there. Delete it directly. Removing a drop-in from `/etc/sudoers.d/` cannot lock you out, because the `wheel` rule that gives you sudo lives in `/etc/sudoers`, and this never involves editing a sudoers file by hand:

```bash
sudo rm -f /etc/sudoers.d/99-omarchy-nopasswd-$USER
```

Running `omarchy-sudo-passwordless` after the reboot also removes the stale file, but it then falls through to the enable prompt, and that `gum confirm` prompt selects Yes by default, so pressing Enter hands out a fresh 15-minute grant. Answer No if you go that way.

Then update. The change that removes leftover grants during boot shipped in 4.0.3, and the stable package repository carried 4.0.4-1 on 2026-09-18:

```bash
omarchy update
```

**Verify.** List the expiry timer while the grant is live. It shows when it will fire:

```bash
systemctl list-timers 'omarchy-nopasswd-expire-*'
```

An empty list does not prove there is no grant: after a reboot on 4.0.2-1 the timer is gone and the file remains. Check for the file itself, which needs root because `/etc/sudoers.d` is mode 750:

```bash
sudo ls /etc/sudoers.d/ | grep 99-omarchy-nopasswd
```

No output means no grant file exists. On 4.0.3 and later, confirm the boot-time cleanup rule is installed:

```bash
cat /etc/tmpfiles.d/omarchy-nopasswd-sudo.conf
```

Sources: <https://github.com/omacom/omarchy/blob/d2a4cc0c4d60cd3bce866f65643f89f7d2978d5e/bin/omarchy-sudo-passwordless> · <https://github.com/omacom/omarchy/blob/945af75aa2c0bf5b40a0155500f0774f06db6721/bin/omarchy-sudo-passwordless> · <https://github.com/omacom/omarchy/blob/945af75aa2c0bf5b40a0155500f0774f06db6721/etc/tmpfiles.d/omarchy-nopasswd-sudo.conf> · <https://github.com/omacom/omarchy/pull/9387> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-sudo-passwordless> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/etc/tmpfiles.d/omarchy-nopasswd-sudo.conf> · <https://pkgs.omarchy.org/stable/x86_64/omarchy.db> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/test/shell.d/nopasswd-sudo-expiry-test.sh> · <https://github.com/omacom/omarchy/pull/7990> · <https://github.com/omacom/omarchy/commit/b9657b631361ccbece50d0ecc278be7ad2f6cd22> · <https://github.com/charmbracelet/gum/blob/4d089f95507708a71f64dacfe7ca513219dd5267/confirm/options.go>

---

## A polkit rule with the wrong permissions is ignored, and polkit.service still reports healthy

`polkit-rule-wrong-permissions-silently-ignored` · severity: **medium** · frequency: **occasional** · applies to: `omarchy`

**Symptom.** A custom rule dropped into `/etc/polkit-1/rules.d/` does not change any authentication prompt. `systemctl status polkit` shows the service active the whole time, with nothing to say why the rule had no effect.

**Cause.** `polkitd`'s script loader (`load_scripts` in `polkitbackendduktapeauthority.c`) lists every `*.rules` file in each rules directory, sorts them, and hands each one to `execute_script_with_runaway_killer`. That runs `runaway_killer_thread_execute_js`, which reads the file with `g_file_load_contents`. When the read fails, for example because the file is owned `root:root` with mode 600 and the daemon runs as the unprivileged `polkitd` user, it logs "Error loading script <file>" at error level and returns, and `load_scripts` moves on to the next file rather than stopping. The message reaches the journal, because `polkit_backend_authority_log` passes anything at or above the configured level to `syslog()`, but nothing fails the systemd unit over it. What loaded successfully is logged per file at debug level and summarised at info level ("Finished loading, compiling and executing %d rules"), and the Arch package's `polkit.service`, which is upstream's own `data/polkit.service.in` unchanged, starts the daemon with `--no-debug --log-level=notice`, so both of those messages are dropped and only the per-file error survives. The daemon's directory monitor reloads rules only when a file is created, deleted or finished being written, so fixing the permissions with `chmod` or `chown` alone does not make it re-read the file. The Arch wiki's polkit page states the requirement this trips: "Rules must have root:polkitd ownership." A file created through `sudo` inherits at least the calling user's umask, because sudo takes the union of the user's umask and its own default of 0022 and never lowers it, so a umask of 077 produces a `root:root` mode 600 file that polkitd cannot read whatever the rule says. Upstream's own issue tracker carries this exact framing, still open: "even when no rules are loaded (permission denied), polkit.service succeeds in journal."

> **Audit corrected this record.** Fetched all five cited sources. The pinned sha 9e4894c is the commit tagged 127 ("Release 127", 2025-12-17), matching the installed polkit 127-3. In polkitbackendduktapeauthority.c, load_scripts lists *.rules files and calls execute_script_with_runaway_killer, but the "Error loading script" message is emitted in runaway_killer_thread_execute_js when g_file_load_contents fails, which the record misplaced. Per-file success is logged at LOG_LEVEL_DEBUG, the summary at LOG_LEVEL_INFO, the error at LOG_LEVEL_ERROR. polkit_backend_authority_log drops anything above the configured level and passes the rest to syslog(), and the enum mirrors syslog priorities, so the shipped --log-level=notice hides info and debug and passes err, which makes the record's journal claim and the verify's -p err filter correct. data/polkit.service.in and the installed /usr/lib/systemd/system/polkit.service (owned by polkit 127-3) both carry --no-debug --log-level=notice and Type=notify-reload, and polkitd.c handles SIGHUP with a reload, so systemctl reload polkit is valid. polkitbackendcommon.c shows the directory monitor reloads only on CREATED, DELETED and CHANGES_DONE_HINT, so a chown or chmod alone does not trigger a reload, which the record's fix relied on without saying. The Arch wiki sentence "Rules must have root:polkitd ownership." is verbatim. GitHub issue 178 is open and its body is only a link to GitLab issue 177, whose description is empty, so the issue's whole content is its title, which the record quotes exactly. The claim that unreadable files are "most commonly" a umask problem had no source and is softened to an example, backed by the sudoers manual's statement that sudo takes the union of the user's umask and 0022. Locally /etc/polkit-1/rules.d is root:polkitd mode 750 and the unit runs as User=polkitd, read without root. Gate 1 passes on the open upstream issue and the documented wiki requirement, gates 2 and 3 pass, severity medium matches the brief's scale. applies_to says omarchy but this is generic Arch polkit behaviour that happens to be true on Omarchy. No rule file was installed and nothing was exercised.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** `systemctl status polkit` reports the unit healthy whether or not any given rule file actually loaded. The loader skips a script it cannot open and continues rather than failing the unit, confirmed by reading `load_scripts()` in `polkitbackendduktapeauthority.c` at the tag matching the installed `polkit 127-3` package. A permission mistake in one rule file does not surface as a service problem, only as a rule that quietly does not apply, so checking that polkit is running tells you nothing about whether your rule is in effect.

**Fix.**

Give the rule file group `polkitd` and group read, or make it world readable. Set the permissions explicitly rather than relying on whatever umask was active when the file was created:

```bash
sudo chown root:polkitd /etc/polkit-1/rules.d/<name>.rules
sudo chmod 640 /etc/polkit-1/rules.d/<name>.rules
```

Then reload polkit. This step is required: polkitd re-reads the directory on its own when a rule file is created, deleted or written, but not when only its owner or mode changes. The unit is `Type=notify-reload`, so `reload` sends the SIGHUP the daemon answers by loading every rule again:

```bash
sudo systemctl reload polkit
```

**Verify.** Check the file's actual mode and owner rather than trusting how it was created:

```bash
sudo stat -c '%a %U:%G' /etc/polkit-1/rules.d/<name>.rules
```

Then confirm the daemon did not log a load failure for it, since the service itself will report active either way:

```bash
journalctl -u polkit -p err -b | grep 'Error loading script'
```

No line naming the file means it was at least readable when polkit last loaded rules.

Sources: <https://github.com/polkit-org/polkit/blob/9e4894c969eecf26a3ba762f4f7a268aa0fb3e51/src/polkitbackend/polkitbackendduktapeauthority.c> · <https://github.com/polkit-org/polkit/blob/9e4894c969eecf26a3ba762f4f7a268aa0fb3e51/src/polkitbackend/polkitbackendauthority.c> · <https://github.com/polkit-org/polkit/blob/9e4894c969eecf26a3ba762f4f7a268aa0fb3e51/data/polkit.service.in> · <https://github.com/polkit-org/polkit/issues/178> · <https://wiki.archlinux.org/title/Polkit> · <https://github.com/polkit-org/polkit/blob/9e4894c969eecf26a3ba762f4f7a268aa0fb3e51/src/polkitbackend/polkitbackendcommon.c> · <https://github.com/polkit-org/polkit/blob/9e4894c969eecf26a3ba762f4f7a268aa0fb3e51/src/polkitbackend/polkitd.c> · <https://github.com/polkit-org/polkit/blob/9e4894c969eecf26a3ba762f4f7a268aa0fb3e51/src/polkitbackend/polkitbackendauthority.h> · <https://www.sudo.ws/docs/man/sudoers.man/>

---

## Secure Boot Violation after a Limine-only update, with Secure Boot enforced

`secure-boot-violation-after-limine-only-update` · severity: **medium** · frequency: **occasional** · applies to: `limine`, `omarchy`, `secure-boot`, `uefi`

**Symptom.** On a machine with Secure Boot enforced and sbctl custom keys enrolled, an `omarchy update` that upgrades the `limine` package, with or without a kernel in the same transaction, leaves the machine unable to boot. The firmware reports a Secure Boot Violation before Limine, the LUKS prompt or Plymouth runs. `sudo sbctl verify`, run before the reboot or from a chroot afterwards, lists `/boot/EFI/limine/limine_x64.efi` as not signed.

**Cause.** Three pacman hooks run on a `limine` upgrade, and their order is the defect.

1. `/usr/share/libalpm/hooks/80-limine-efi-deploy.hook`, owned by `limine-mkinitcpio-hook` (not by `limine` as the issue's reporter wrote, confirmed with `pacman -Qo` at 1.37.1-1), runs `/usr/bin/limine-install`, which copies `/usr/share/limine/BOOTX64.EFI` to `/boot/EFI/limine/limine_x64.efi` and signs it through `sb_sign()` in `/usr/lib/limine/limine-common-functions`. That function calls `sbctl sign "$file_path"` with no `-s`/`--save` flag, identical on this workstation and in the upstream 1.37.1 tag, so the file is signed but never registered in sbctl's file database.

2. `/etc/pacman.d/hooks/99-omarchy-limine.hook`, owned by no package, is written by the Omarchy ISO installer (`_write_limine_pacman_hook` in `omarchy-iso`'s `phases_impl.py`, still present in the current installer) and triggers on `Operation = Upgrade` of `limine` only. It runs after hook 1 and copies the raw, unsigned package binary over the file hook 1 just signed:

```
Exec = /bin/sh -c "/usr/bin/cp /usr/share/limine/BOOTX64.EFI /boot/EFI/limine/limine_x64.efi"
```

3. `zz-sbctl.hook`, from the `sbctl` package, runs `sbctl sign-all -g` and is the safety net meant to catch this. It cannot, for two independent reasons. `sign-all` only iterates files already in sbctl's database (`SignAll()` reads the database and signs each entry), and step 1 never put this file there. And pacman matches the hook's path triggers with `fnmatch()` and no case folding, so on a transaction that upgrades only `limine`, whose sole EFI file is `usr/share/limine/BOOTX64.EFI`, the lowercase `usr/share/**/*.efi*` trigger never matches and the hook does not run at all. On a transaction that also bumps the kernel the hook does run, because `usr/lib/modules/*/vmlinuz` matches, and still signs nothing for this file.

The case-sensitive glob was found by the issue's reporter. The missing `--save`, which is what makes the glob beside the point, was found by the second reporter in the same thread, who hit the failure on a combined Omarchy 4.0.2 to 4.0.3 update with a kernel bump. Both are in omacom/omarchy#10945, open as of 2026-09-18. An upstream pull request, #12242, that deletes the installer hook by migration was closed without merging, and no such migration exists in 4.0.2-1, so every `limine` upgrade repeats the overwrite.

If you have set `ENABLE_ENROLL_LIMINE_CONFIG=yes` in `/etc/default/limine` (off by default, and unset on this workstation), the overwrite also discards the enrolled config checksum, so re-signing alone leaves Limine stopping on a config hash mismatch.

> **Audit corrected this record.** Checked on omarchy 4.0.2-1 (limine 12.6.0-1, limine-mkinitcpio-hook 1.37.1-1, sbctl NOT installed here, so every sbctl claim is from source). Held: sb_sign() in /usr/lib/limine/limine-common-functions calls sbctl sign with no -s and is byte-identical to the upstream 1.37.1 tag. sbctl.go Sign() only writes the file database when the enroll flag is set, and SignAll() iterates only that database. pacman matches hook targets with fnmatch(pattern, path, 0), so the glob is case-sensitive as the reporter said. /etc/pacman.d/hooks/99-omarchy-limine.hook is present here, owned by no package, and _write_limine_pacman_hook still writes it at omarchy-iso 1daf120. Wrong or missing: (1) the record credits the missing --save to itself. The second reporter (dot3x3q, 2026-09-14 comment) found it, and the record must say so for gate 1. (2) The 80 hook is owned by limine-mkinitcpio-hook (pacman -Qo), so the harvester was right that the reporter misattributed it, but the omission was wrong: the harvester compared the wrong upstream copy, install/arch-linux/limine-entry-tool/. The copy the package ships, install/arch-linux/limine-mkinitcpio-hook/usr/share/libalpm/hooks/80-limine-efi-deploy.hook at the same tag, is byte-identical to the installed file and is now cited. (3) The symptom and fix say any update touching limine or limine-mkinitcpio-hook. The installer hook triggers on Upgrade of limine only, so a limine-mkinitcpio-hook-only transaction leaves the file signed. (4) The title says Limine-only, and the second report is a kernel-bump transaction. (5) The fix claims -s makes sign-all cover the file on future updates. zz-sbctl.hook still does not fire on a limine-only transaction, so the check stays necessary, and the durable mitigation both reporters reached, disabling the installer hook, was missing. (6) danger claims the reporter had to sbctl create-keys. The issue says disabling Secure Boot can also mean re-doing custom key enrollment, nothing about new keys. The Option ROM warning was uncited. It is in docs/sbctl.8.txt at the pinned sha and is now cited. (7) Missing from the record: ENABLE_ENROLL_LIMINE_CONFIG=yes makes sbctl sign -s alone insufficient (second reporter), and upstream PR #12242, which removes the hook by migration, was closed unmerged, so 4.0.2-1 has no migration. Severity lowered to medium against the brief's scale: nothing is exposed by the defect, the harm is a hardening control (Secure Boot) left off by the obvious wrong fix. Not exercised: no sbctl, no hook, no ESP or firmware state was touched, and the chroot recovery was not run.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** Do not answer the Secure Boot Violation by turning Secure Boot off in firmware setup and leaving it off. The issue's reporter writes that on their ASUS board disabling it can also mean redoing custom key enrollment from scratch, and until it is back on the machine has no pre-boot integrity check at all. Re-sign the file from a live system or chroot instead. If you do have to enroll again, keep `-m`: sbctl's manual says some devices have firmware that is signed and validated when Secure Boot is enabled, that failing to validate it could brick devices, and that it is recommended to enroll your own keys with Microsoft certificates.

If `ENABLE_ENROLL_LIMINE_CONFIG=yes` is set, `sbctl sign -s` on its own is not enough: the overwrite also dropped the enrolled config checksum and Limine stops on a config hash mismatch. Run `sudo limine-enroll-config` first.

When disabling the installer hook, do not touch `80-limine-efi-deploy.hook` by mistake. It is the one that deploys and signs the loader on every `limine` and `limine-mkinitcpio-hook` upgrade.

**Fix.**

After any update that upgraded `limine`, check before rebooting:

```sh
sudo sbctl verify
```

If `/boot/EFI/limine/limine_x64.efi` is listed as not signed, sign it and register it in sbctl's database in the same step:

```sh
sudo sbctl sign -s /boot/EFI/limine/limine_x64.efi
sudo sbctl verify
```

`-s` is the flag the packaged signing path omits. Once the file is in the database, the plain `sbctl sign` that `limine-install` runs keeps it there, and `sbctl sign-all` covers it whenever `zz-sbctl.hook` fires. That hook still does not fire on a transaction that upgrades only `limine`, so the check above stays necessary after every such update for as long as `99-omarchy-limine.hook` exists.

To stop the overwrite instead of repairing after it, take the installer hook out of pacman's path. `80-limine-efi-deploy.hook` already deploys and signs the same file, which is the fix the issue's reporter proposed and the second reporter applied:

```sh
sudo mv /etc/pacman.d/hooks/99-omarchy-limine.hook /etc/pacman.d/hooks/99-omarchy-limine.hook.disabled
```

pacman reads only files ending in `.hook`, and no package owns this one, so nothing reinstalls it. If a later Omarchy migration removes it first, the `mv` finds nothing and that is fine.

If `/etc/default/limine` has `ENABLE_ENROLL_LIMINE_CONFIG=yes`, run `sudo limine-enroll-config` before `sbctl sign -s`, so the config checksum is enrolled again before the binary is signed.

If the machine is already locked out, boot the Omarchy ISO or any live Linux, switch to a second console, and run the same command from a chroot, since sbctl's keys live in `/var/lib/sbctl/keys` on the encrypted root:

```sh
cryptsetup open /dev/<your LUKS partition, from lsblk> root
mount -o subvol=@ /dev/mapper/root /mnt
mount /dev/<your ESP, the vfat partition from lsblk> /mnt/boot
arch-chroot /mnt
sbctl sign -s /boot/EFI/limine/limine_x64.efi
sbctl verify
```

**Verify.** `sudo sbctl verify` lists `/boot/EFI/limine/limine_x64.efi` as signed, `sudo sbctl list-files` includes it, and the machine boots with Secure Boot enforced. If you disabled the installer hook, `ls /etc/pacman.d/hooks/` shows `99-omarchy-limine.hook.disabled` and no `99-omarchy-limine.hook`.

Sources: <https://github.com/omacom/omarchy/issues/10945> · <https://github.com/omacom/omarchy-iso/blob/1daf1202d49147223341c8e88ed2cb5a65b75bed/configs/airootfs/usr/share/omarchy-iso/orchestrator/phases_impl.py> · <https://gitlab.com/Zesko/limine-entry-tool/-/raw/26b1879c862a55bae4e8777d48b2f917c68ef347/install/arch-linux/limine-entry-tool/usr/lib/limine/limine-common-functions> · <https://github.com/Foxboron/sbctl/blob/6f234197abc07b56092e0043b448f8b630dea7e4/cmd/sbctl/sign.go> · <https://github.com/Foxboron/sbctl/blob/6f234197abc07b56092e0043b448f8b630dea7e4/cmd/sbctl/sign-all.go> · <https://github.com/Foxboron/sbctl/blob/71ce775145dc4d01ef419804f445873ee2c837a7/contrib/pacman/ZZ-sbctl.hook> · <https://github.com/omacom/omarchy/pull/12242> · <https://gitlab.com/Zesko/limine-entry-tool/-/raw/26b1879c862a55bae4e8777d48b2f917c68ef347/install/arch-linux/limine-mkinitcpio-hook/usr/share/libalpm/hooks/80-limine-efi-deploy.hook> · <https://github.com/Foxboron/sbctl/blob/6f234197abc07b56092e0043b448f8b630dea7e4/sbctl.go> · <https://github.com/Foxboron/sbctl/blob/6f234197abc07b56092e0043b448f8b630dea7e4/docs/sbctl.8.txt> · <https://gitlab.archlinux.org/pacman/pacman/-/blob/master/lib/libalpm/util.c>

---

## Know that a shell plugin runs unsandboxed with your full account access, not as a config file

`shell-plugins-run-unsandboxed` · severity: **medium** · frequency: **occasional** · applies to: `omarchy`

**Symptom.** Is it safe to add a shell plugin from GitHub. What can a plugin actually reach once it is enabled, and could a bad one get at passwords, ssh keys, or anything else the desktop session can touch.

**Cause.** Documented in the Omarchy manual at `manual/32-shell-plugins.md` in the upstream repository, at the v4.0.2 tag, commit 346e69e1cec6c4e8924531874af6ba010a1bc99e, and at the v4.0.4 tag, commit c668141e9c42b13c80c9ca4ea108e11708c5e8a5, and confirmed by reading `shell/plugins/README.md`, which the omarchy 4.0.4-1 package installs at `/usr/share/omarchy/shell/plugins/README.md` byte-identical to the v4.0.4 tag. The manual itself is not installed by the package. The whole Omarchy desktop, not only the bar, runs as plugins inside one long-lived Quickshell process called `omarchy-shell`: the bar, its panels, the emoji picker, the clipboard manager, the Omarchy menu, the lock screen and the polkit agent that approves privileged actions. A third-party plugin added with `omarchy plugin add <url>` is cloned into `~/.config/omarchy/plugins/<id>/` and, once enabled, runs as QML inside that same process with everything the user account can reach.

The manual states this at the point where a plugin is added: "Before it does anything, it tells you plainly that plugins run as arbitrary, unsandboxed code inside your long-lived shell process, shows you the URL, and asks you to confirm." And: "A plugin isn't a config file — it's code that runs for as long as your session does, with everything your user account can reach." The warning is printed by `omarchy-plugin-add` at add time and skipped by `--yes`. `omarchy plugin update` shows the diff and asks before a fast-forward pull, also skipped by `--yes`, but repeats no warning, and the shell reloads a changed plugin directory on its own, so new code runs as soon as the pull lands. From 4.0.3 on there is one exception: a service plugin whose manifest sets `keepLoaded: true` keeps its running instance across that reload, and its new code starts with the next shell start.

Which version matters here. On 4.0.2 the manual says first-party and third-party plugins are "discovered the same way at startup; the only difference is where they sit on disk". Omarchy 4.0.3, released 2026-09-08, changed that. PR #9618, "Restrict third-party plugin access to authentication services", merged to `quattro`, and it shipped in 4.0.3 through the backport PR #10733, merge commit cf6fedc9f5a8d73fd2654695703fe5b2f977b4b6, listed in the release notes as "Restrict plugin access to authentication services". It adds `shell/services/AuthServiceStore.js`, which holds the lock and polkit services outside the shell's public service map with no parent object, and per-plugin API objects, so a third-party plugin is handed a limited interface instead of the trusted shell interfaces. The manual from that release says "The third-party plugin interface does not directly expose authentication services", and also "Visual plugins still share the shell's QML scene and can walk ordinary parent objects, while all plugin code runs with everything your user account can reach." So on 4.0.3 and 4.0.4 the lock and polkit services are kept out of a third-party plugin's reach inside the shell's own object graph, and the rest of this record still holds on every release: the plugin is unsandboxed code running as the user.

> **Audit corrected this record.** Gate 1 holds on the documented-default clause: both quoted sentences are in manual/32-shell-plugins.md at the pinned v4.0.2 sha, line 40, verbatim, and the same warning is printed by omarchy-plugin-add lines 104 to 112 on the installed 4.0.2-1. Gate 2 holds: every mechanism the record states, one process, full account reach, clone path, no code shown at add time, is in the manual or the README, and nothing beyond them was added. Gate 3 holds: the record names no way to abuse a plugin. Checked on 4.0.2-1: shell/plugins/README.md is byte-identical to the pinned tag, omarchy-plugin-add, -update, -remove, -validate and -list do what the record says (validate line 53 reserves omarchy.*, remove lines 87 to 115 delete a git checkout and back up a plain folder, update lines 53 to 65 show the diff and confirm), and shell.qml lines 331, 597 and 676 with PluginRegistry.isEnabled confirm that a disabled third-party plugin's QML is never instantiated, which the fix's read-before-enable advice depends on. Three things were wrong. First, the manual is not installed by the package, so "matching omarchy 4.0.2-1 installed here" was only true of the README. Second, and the one that matters, the record said first- and third-party plugins load with no distinction and that upstream treats the absence of a sandbox as settled. That was true at v4.0.2 and false from v4.0.3 (2026-09-08): commit 1702cf0bee, in the v4.0.3 release notes as "Restrict plugin access to authentication services", adds AuthServiceStore.js and per-plugin API objects, and the manual at v4.0.3 and v4.0.4 says third-party plugins get a limited interface with no direct access to authentication services while still running with everything the user can reach. The cause and fix now state the version boundary. Third, without --enable the add command asks whether to enable now, so "leaving off --enable" is not enough on its own, and the cause's "nothing re-confirms it later" ignored the diff-and-confirm step in update, both now fixed. Severity lowered from high to medium against the brief's scale: no default exposes a credential or private data on its own, the exposure needs the user to install third-party code, the add command warns before doing so, and running unsandboxed as the user is the norm for desktop shell extensions rather than weaker than it. High would make every AUR package and curl-pipe-bash install high. Nothing was exercised: no plugin was added, enabled or removed. Re-checked against 4.0.4-1 2026-09-19: Re-checked on omarchy 4.0.4-1 (pacman -Q) against the v4.0.4 tag, commit c668141e9c42b13c80c9ca4ea108e11708c5e8a5, whose shell.qml, PluginRegistry.qml, shell/plugins/README.md and plugin scripts are byte-identical to the installed files. The record's substance holds on 4.0.4: the add warning, the diff-and-confirm update, remove, validate, list and the enable-only-when-listed rule come from omarchy-plugin-* scripts that did not change between v4.0.2 and v4.0.4, and the manual at v4.0.4 still says all plugin code runs with everything the user account can reach. Traced the boundary in code: AuthServiceStore.js keeps the lock and polkit instances out of the public service map and unparented (shell.qml ensureService), a third-party plugin receives a PluginShellApi and PluginRegistryApi facade instead of the host, publicPluginManifest strips the trust fields, and only first-party manifests can declare the authentication capability. Held against the boundary-moved test, it does what it claims and no more: it protects the authentication objects inside the process, and the manual itself says visual plugins can still walk ordinary parent objects and that this is not a sandbox, which the record already says. Two things were wrong. The record credited 4.0.3's change to commit 1702cf0bee, which is on quattro's history but is not an ancestor of the v4.0.3 or v4.0.4 tags. The release carries PR #9618 as a cherry-pick merged through backport PR #10733 (merge cf6fedc9), so the cause now cites the PRs. Second, the claim that updated code runs as soon as the pull lands is no longer true for every plugin: the #9485 backport in 4.0.3 keeps a service with keepLoaded true loaded across a plugin reload (shell.qml unloadPluginServices and _syncServices, lines 974 to 978 and 1033 to 1049), with no first-party check, so such a service runs its new code only after the shell restarts. The cause and fix now say so, and the 4.0.4 manual wording on parent-object reach is quoted. Severity medium and frequency occasional stand. Nothing was exercised: no plugin was added, enabled, updated or removed, and no shell IPC was called.
>
> *The Cause above was rewritten on 2026-09-19 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** `omarchy plugin remove` deletes a git-checked-out plugin outright (the upstream repository is unaffected), so local edits and local commits that were never pushed are lost with it. Only a hand-made plugin folder with no git repo is preserved, moved to a timestamped backup inside the plugins directory. `--yes` on `omarchy plugin add` and on `omarchy plugin update` skips the warning, the diff and the confirmation, so a script that passes it installs and updates code nobody has read.

**Fix.**

There is no setting that sandboxes a plugin. What can be controlled is which code gets into the process, and when.

Read a plugin's source before enabling it, not only its README. `omarchy plugin add <url>` shows the clone URL and asks for confirmation, but it does not show the code, and `omarchy plugin validate <path>` checks the manifest's shape, its entry-point paths and the absence of symlinks, not what the plugin does with the session.

Add without enabling:

```bash
omarchy plugin add https://github.com/<owner>/<repo>.git
```

Without `--enable` the command clones into `~/.config/omarchy/plugins/<id>/`, validates the manifest, and then asks whether to enable the plugin now. Answer no. The shell creates QML components only for plugins it considers enabled, and a third-party plugin is enabled only when its id appears in `~/.config/omarchy/shell.json`, so the checkout can be read before `omarchy plugin enable <id>` runs any of it. Do not pass `--yes` on a plugin you have not read: it skips the warning as well as the question.

Before accepting `omarchy plugin update`, read the diff it prints. An update is as consequential as the first install, and the shell reloads the plugin as soon as the fast-forward lands, except a service that sets `keepLoaded: true`, which runs the new code from the next shell start. `omarchy plugin update --yes` skips the diff and the question.

Check what is enabled now:

```bash
omarchy plugin list
```

and remove anything that cannot be accounted for with `omarchy plugin remove <id>`.

The `omarchy.` id prefix is reserved for first-party plugins, so a third-party plugin cannot claim it, but that only stops a name collision. It says nothing about whether an unreserved id belongs to code worth trusting.

On 4.0.3 and later the shell keeps its authentication services out of a third-party plugin's reach. Update to get that boundary, and treat it as a boundary inside the shell rather than a sandbox: the plugin still runs as your user.

**Verify.** ```bash
omarchy plugin list --json
```

Shows which plugins are actually enabled right now, first-party and third-party together, so the unsandboxed surface being relied on matches what was meant to be installed rather than what is remembered.

Sources: <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/manual/32-shell-plugins.md> · <https://github.com/omacom/omarchy/blob/346e69e1cec6c4e8924531874af6ba010a1bc99e/shell/plugins/README.md> · <https://github.com/omacom/omarchy/blob/0534987009061cbe2dacdde4ad564092ab698d12/manual/32-shell-plugins.md> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/manual/32-shell-plugins.md> · <https://github.com/omacom/omarchy/commit/1702cf0bee025aa32eddac391c4f9ac32244cfeb> · <https://github.com/omacom/omarchy/commit/094c913065315082c0cbf353a169c0245779c427> · <https://github.com/omacom/omarchy/releases/tag/v4.0.3> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-plugin-add> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-plugin-update> · <https://github.com/omacom/omarchy/pull/9618> · <https://github.com/omacom/omarchy/pull/10733> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/shell/services/AuthServiceStore.js> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/shell/shell.qml> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/shell/plugins/README.md>

---

## Tell a real changed SSH host key from an algorithm order false alarm

`ssh-host-key-warning-after-algorithm-order-change` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ssh refuses a server you connect to all the time with `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`, right after an OpenSSH update, a fresh set of dotfiles, or a new `~/.ssh/config`, and nothing else about the server changed. Is this an attack, or did the update just change which key ssh checks.

**Cause.** OpenSSH picks the host key type to check from `HostKeyAlgorithms`, an ordered list, and `man 5 ssh_config` on openssh 10.5p1 says that when host keys are already known for the destination the default is modified to prefer their algorithms. The client source (`sshconnect2.c`, `order_hostkeyalgs`) applies that only when `HostKeyAlgorithms` is unset or starts with `+` or `-`. A replacing list with no prefix, a `^` list, or a server that no longer offers the type you hold, each make the client negotiate a key type for which `known_hosts` has no entry. What turns that into the changed-key warning is `hostfile.c`: any recorded key for the host that is not equal to the offered one counts as a change, whatever its type. So a `known_hosts` that holds only an RSA key for a server now negotiated with ED25519 prints `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!` exactly as a rotated key would. The common trigger after an update is in the OpenSSH 8.8 release notes: the client stopped offering the SHA-1 `ssh-rsa` signature, so a server that can only sign RSA with SHA-1 is negotiated with a different key type instead. `UpdateHostKeys`, on by default since release 8.5, normally learns a server's other key types over an authenticated connection and heads this off, but the 8.5 notes list its preconditions: the key matched in `UserKnownHostsFile` and not `GlobalKnownHostsFile`, the same key not recorded under another name, no certificate host key, and no wildcard pattern in `known_hosts`. A host that fails one of those keeps the single entry it started with. The warning prints the two facts that separate the cases: `The fingerprint for the %s key sent by the remote host is` names the type actually offered, and `Offending %s key in %s:%lu` names one recorded entry and its line, the last non-matching one in file order, which is not always the same type. Both types print in capitals, `RSA`, `ECDSA` or `ED25519`. Arch and Omarchy 4.0.2-1 ship no `HostKeyAlgorithms` line in `/etc/ssh/ssh_config` or `/etc/ssh/ssh_config.d/`, so a list on this system is one you or a tool added.

> **Audit corrected this record.** Held against openssh 10.5p1-1 on omarchy 4.0.2-1 by reading only: man 5 ssh_config on this machine, ssh -G and ssh -Q output, /etc/ssh/ssh_config and its three drop-ins, and the pinned openssh-portable sources sshconnect.c, hostfile.c, sshconnect2.c and clientloop.c. The premise is real, not folk: hostfile.c check_hostkeys_by_key_or_type returns HOST_CHANGED for any recorded key of the host that is not equal to the offered one, with no key-type comparison, so a known_hosts holding only an RSA entry for a server now negotiated with ED25519 prints the full changed-key warning. All three quoted strings match sshconnect.c exactly. Wrong: UpdateHostKeys was enabled by default in release 8.5, not 8.8, and its preconditions are misquoted. Wrong: sshconnect2.c keeps the prefer-known-types ordering for a HostKeyAlgorithms list prefixed with plus or minus and drops it only for a replacing or ^ list, so 'an explicit line' overstates. Wrong: the fix example prints ed25519 where sshkey_type prints ED25519, and the diagnostic in step 3 cannot be applied, because the Offending line names the last non-matching entry in file order, not the entry of the offered type. Wrong: the prose says remove the one offending line and the command given is ssh-keygen -R, which man 1 ssh-keygen says removes all keys for the hostname, so in the algorithm-order case it deletes the very entries that were still correct. Wrong: verify demands exactly one entry per host and compares it against the first entry of ssh -G hostkeyalgorithms, which is ssh-ed25519-cert-v01@openssh.com, a certificate algorithm that never appears as a known_hosts key type, and ssh -G does not apply the known-hosts ordering anyway. Rewritten cause, fix and verify give the reader the local test, offered type versus recorded types from ssh-keygen -lF, and a repair for each branch: confirm out of band then ssh-keygen -R when the same type differs, or connect with the held type placed first via the ^ prefix so UpdateHostKeys learns the rest when no entry of the offered type exists. The ^ branch is read from clientloop.c and sshconnect.c hostkey_accepted_by_hostkeyalgs, not exercised, which is why confidence is medium. Gate 1 passes on documented defaults and release notes, gate 3 passes, no attack step anywhere. Severity lowered to medium: StrictHostKeyChecking defaults to ask, no default exposes anything, and the exposure exists only if the reader applies the advice the record warns against. No overlap in problems.jsonl: the only slug containing ssh is ssh-agent-not-seen-by-gui-apps and no record mentions known_hosts, StrictHostKeyChecking or the warning text. Arch and Omarchy ship no HostKeyAlgorithms line, confirmed by reading /etc/ssh/ssh_config and /etc/ssh/ssh_config.d/.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** Setting `StrictHostKeyChecking no`, `UserKnownHostsFile=/dev/null`, or removing a key without confirming it out of band all have the same effect: ssh accepts whatever key is offered for that host from then on with no warning, which is exactly the check this message exists to make. A wildcard `Host` pattern, `Host *` or a whole subnet the way the Arch wiki's own private-network example writes it, turns a fix meant for one server into no host key checking for many.

**Fix.**

Do not silence the warning with `StrictHostKeyChecking no` and do not start with `ssh-keygen -R`. Read two lines of the warning first: the type on `The fingerprint for the <TYPE> key sent by the remote host is`, and the fingerprint under it.

1. Without connecting, list what `known_hosts` already holds for the host, with types and fingerprints. Write `[host]:port` in place of `host` if the server is on a port other than 22:

```bash
ssh-keygen -lF <host> -f ~/.ssh/known_hosts
```

2. Compare the offered type with those entries.

If an entry of the offered type exists, the key of that type differs from your record: either the server rotated it or something is between you and it. Confirm the fingerprint the warning printed through a channel that is not this connection: the machine's own console (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` there), a configuration management record, or the administrator. Only when it matches, remove the entries for that one host and accept the new key on the next connection. `ssh-keygen -R` removes every entry for the hostname given, all key types, and nothing else:

```bash
ssh-keygen -R <host> -f ~/.ssh/known_hosts
```

If no entry of the offered type exists, nothing you hold has been contradicted: the client negotiated a type it has never recorded for this host. Connect once with the type you already hold placed first, so the host is authenticated by the key you already trust and `UpdateHostKeys` can learn the others over that authenticated connection. Use `rsa-sha2-512,rsa-sha2-256` for an `ssh-rsa` entry, `ecdsa-sha2-nistp256` for an `ecdsa-sha2-nistp256` entry, `ssh-ed25519` for an `ssh-ed25519` entry:

```bash
ssh -o 'HostKeyAlgorithms=^rsa-sha2-512,rsa-sha2-256' <host>
```

The `^` prefix puts those first without removing anything else from the list, which is what lets the other types be learned. If that connection succeeds, run step 1 again and the offered type should now be listed. If it fails with `no matching host key type found`, the server no longer offers a type you hold, so confirm the offered fingerprint out of band exactly as above, then record it without touching the other entries:

```bash
ssh-keyscan -t ed25519 <host> > /tmp/hostkey   # or ecdsa or rsa, add -p <port> if needed
ssh-keygen -lf /tmp/hostkey                    # must match the confirmed fingerprint
cat /tmp/hostkey >> ~/.ssh/known_hosts
```

3. If you have a replacing `HostKeyAlgorithms` line, one with no `+`, `-` or `^` prefix, find it and change it to a `+` or `-` form or delete it, or the client keeps ignoring what `known_hosts` holds for every host it covers:

```bash
grep -n HostKeyAlgorithms ~/.ssh/config /etc/ssh/ssh_config /etc/ssh/ssh_config.d/*.conf 2>/dev/null
```

Never add `StrictHostKeyChecking no` or `UserKnownHostsFile /dev/null` to a `Host` block to make the warning stop. That removes the check for those hosts permanently rather than resolving this one instance.

**Verify.** `ssh-keygen -lF <host> -f ~/.ssh/known_hosts` lists an entry whose type matches the one the warning named on its `The fingerprint for the <TYPE> key sent by the remote host is` line, and `grep -n 'StrictHostKeyChecking\|UserKnownHostsFile' ~/.ssh/config /etc/ssh/ssh_config /etc/ssh/ssh_config.d/*.conf 2>/dev/null` prints nothing you added. On Omarchy 4.0.2-1 the only stock hits are in systemd's `20-systemd-ssh-proxy.conf`, which disables the check for its `unix/*`, `vsock/*` and `machine/*` proxy addresses only.

Sources: <https://man.openbsd.org/ssh_config.5> · <https://www.openssh.com/txt/release-8.8> · <https://wiki.archlinux.org/title/OpenSSH> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/sshconnect.c> · <https://www.openssh.com/txt/release-8.5> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/hostfile.c> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/sshconnect2.c> · <https://github.com/openssh/openssh-portable/blob/bc41d062cc0f305e49d58430b467c3ce8c822a87/clientloop.c>

---

## A hand-edited /etc/sudoers locks you out of sudo: wrong owner or mode refuses everyone, a syntax error drops the broken line

`sudoers-syntax-error-or-mode-locks-out-sudo` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `omarchy`

**Symptom.** After editing `/etc/sudoers`, or a file under `/etc/sudoers.d/`, with a plain editor instead of `visudo`, or after a `chmod` or `chown` touched it, `sudo` fails. With the wrong owner or mode it fails for every user, with a message such as `/etc/sudoers is owned by uid 1000, should be 0` or `/etc/sudoers is world writable`, followed by `sudo: unable to initialize policy plugin`. With a syntax error it prints the file, line and column, for example `/etc/sudoers:12:9: syntax error`, and then either tells you that you are not in the sudoers file, if your grant was on the broken line, or keeps working while printing the error on every run.

**Cause.** `sudo` opens and parses `/etc/sudoers` on every invocation, for every user including root, with no cache. Before it reads a rule it checks the file (sudo 1.9.17p2, the version installed here, in `lib/util/secure_path.c` with the messages in `plugins/sudoers/sudoers.c`): it must be a regular file, owned by uid 0, not world-writable, and not group-writable unless its group is the compiled-in sudoers group, which is root here (`ls -l /etc/sudoers` shows `-r--r----- 1 root root`, the `0440` that `sudoers(5)` gives as the default mode). Any of those failing is logged as a parse error, the file is never opened, and with no other sudoers source configured `sudo` stops with `unable to initialize policy plugin`. That refusal is for everyone, because the check comes before any rule is read.

A syntax error behaves differently on this version. Since sudo 1.9.3 the `error_recovery` plugin option defaults to true, and `sudoers(5)` describes it as: "sudoers will try to recover from a syntax error by discarding the portion of the line that contains the error until the end of the line." `sudo_file_parse()` in `plugins/sudoers/file.c` returns the parsed policy when recovery is on, so the rules on the other lines still apply. Whether you are locked out depends on which line you broke: a typo in your own `%wheel ALL=(ALL:ALL) ALL` line drops that grant, a typo elsewhere leaves sudo working with the error printed every time. The older behaviour, where any syntax error refused everyone, is what most guides still describe.

`visudo` exists to prevent both failure modes. It locks the file, parses it before saving and refuses to save a syntax error, and unless you name an alternate file it applies `-O` and `-P` by default, restoring the default owner and mode on save. A plain editor, or a stray `chmod` or `chown`, bypasses all of that.

> **Audit corrected this record.** Checked against sudo 1.9.17p2 source at the pinned sha, which is the v1.9.17p2 tag and matches the installed 1.9.17.p2-6. Held: the owner and mode checks (lib/util/secure_path.c, messages in plugins/sudoers/sudoers.c) refuse before any rule is read, so a wrong owner or a world-writable file locks out everyone, and chmod 777 does not get sudo working, as danger says. Wrong: the record's claim that a syntax error leaves no valid source and prints 'no valid sudoers sources found, quitting'. plugins/sudoers/file.c returns the parse tree when parse_error is set and error recovery is on, sudoers(5) says error_recovery defaults to true since 1.9.3 and discards only the rest of the offending line, and that message is printed only when more than one sudoers source is configured. On this version a syntax error drops the broken line and the lockout is partial. Wrong: 'group- or world-writable' in danger. secure_path.c allows group write when the group is the sudoers gid (root here). Wrong on Omarchy: the recovery path hedges on whether a root password exists. The ISO configurator writes root_enc_password with the same hash as the user, the first-boot form says the password is used for user and root, and omarchy-provision-owner runs chpasswd for both, so `su -` is the primary recovery on a stock install. Missing: visudo's compiled-in fallback editor is /usr/bin/vi (in the binary, and the man page names --with-editor), Omarchy installs neovim only and no /usr/bin/vi exists here, and sudo strips EDITOR/VISUAL/SUDO_EDITOR except for the visudo env_keep line in the stock sudoers template, so visudo from `su -` or a chroot needs EDITOR=nvim or it stops with 'no editor found'. The ISO route was under-specified: the Omarchy ISO is seeded from archiso's releng profile (build-iso.sh), which ships arch-install-scripts and cryptsetup, autologs root on tty1 where the installer runs, and gives root an empty password, so a second console is the way to a shell. Stated from those sources, not tested. Severity lowered to medium under the brief's scale: the lockout exposes nothing, and the chmod 777 trap gives root only to code already running as a local account. Not exercised: no sudoers file, mode, su, visudo or chroot was run on this workstation. The title also overstates: merge_gapfill has no corrected_title, so the operator should retitle by hand to 'A hand-edited /etc/sudoers locks you out of sudo: wrong owner or mode refuses everyone, a syntax error drops the broken line'.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** The panic fix to avoid is loosening the file instead of correcting it. `chmod 777 /etc/sudoers`, or a `chmod -R` run one directory too high, does not get sudo working: sudo checks the mode before reading a rule and refuses while the file is writable by anyone other than root (world-writable, or group-writable by a group other than root). It does hand root to anything on the machine that can now write the file, because the next line appended is one sudo will honour as soon as the mode is put back. Restore `root:root` and `0440`, or let `visudo` do it on save.

The `su -` route works because Omarchy's installer gives root your account password. If you have since set a different root password, or locked the account, use the ISO route.

**Fix.**

Edit `/etc/sudoers` and anything under `/etc/sudoers.d/` with `visudo` only:

```sh
sudo visudo
sudo visudo -f /etc/sudoers.d/<file>
```

The stock sudoers template keeps `SUDO_EDITOR`, `EDITOR` and `VISUAL` for `visudo` (`Defaults!/usr/bin/visudo env_keep += "SUDO_EDITOR EDITOR VISUAL"`), so it opens in the editor Omarchy's shell exports.

If sudo is already broken, `sudo visudo` is broken the same way, and you need a root shell that does not go through sudo. On Omarchy that shell is one command away: the installer sets the root password to the same password as your account (`root_enc_password` in the ISO configurator, and `omarchy-provision-owner` runs `chpasswd` for both), so unless you changed it:

```sh
su -
EDITOR=nvim visudo
```

`EDITOR=nvim` matters. `visudo`'s compiled-in fallback editor is `/usr/bin/vi`, which Omarchy does not install, and root's login shell exports no editor, so a bare `visudo` there stops with `no editor found (editor path = /usr/bin/vi)`.

If the root password is not usable, boot the Omarchy ISO. It runs the installer on the first console, so switch to a second one with `Ctrl+Alt+F2` and log in as `root` with an empty password, which the Arch releng profile the ISO is built on provides. Then unlock and mount the installed root and chroot into it:

```sh
cryptsetup open /dev/<your LUKS partition, from lsblk> root   # skip on an unencrypted install
mount -o subvol=@ /dev/mapper/root /mnt                       # the root partition itself if unencrypted
arch-chroot /mnt
EDITOR=nvim visudo
```

`visudo` reports the line and column of a syntax error, refuses to save until the file parses, and puts the owner and mode back to `root:root` and `0440` on save. If the damage is in a file under `/etc/sudoers.d/`, open that one with `visudo -f`. Then `exit` the chroot and reboot.

**Verify.** `sudo -l` lists your privileges with no error printed above them, `sudo visudo -c` reports `/etc/sudoers: parsed OK` and the same for each file under `/etc/sudoers.d/`, and `ls -l /etc/sudoers` shows `-r--r----- 1 root root`.

Sources: <https://man.archlinux.org/man/visudo.8> · <https://man.archlinux.org/man/sudoers.5> · <https://github.com/sudo-project/sudo/blob/d1b48c651cec19fe37d1f0d3299d2283fb0f88e4/plugins/sudoers/sudoers.c> · <https://github.com/sudo-project/sudo/blob/d1b48c651cec19fe37d1f0d3299d2283fb0f88e4/plugins/sudoers/gram.y> · <https://wiki.archlinux.org/title/Chroot> · <https://github.com/sudo-project/sudo/blob/d1b48c651cec19fe37d1f0d3299d2283fb0f88e4/plugins/sudoers/file.c> · <https://github.com/sudo-project/sudo/blob/d1b48c651cec19fe37d1f0d3299d2283fb0f88e4/plugins/sudoers/sudoers.in> · <https://github.com/sudo-project/sudo/blob/d1b48c651cec19fe37d1f0d3299d2283fb0f88e4/plugins/sudoers/visudo.c> · <https://github.com/sudo-project/sudo/blob/d1b48c651cec19fe37d1f0d3299d2283fb0f88e4/lib/util/secure_path.c> · <https://github.com/omacom/omarchy-iso/blob/7cfb7111a06873d61c45d37034577d4ba08d3f4f/configs/airootfs/root/configurator> · <https://github.com/omacom/omarchy-iso/blob/7cfb7111a06873d61c45d37034577d4ba08d3f4f/builder/build-iso.sh> · <https://github.com/omacom/omarchy/blob/d174d4aa279ea7393d4fad4a80fed147866106b9/bin/omarchy-provision-owner> · <https://gitlab.archlinux.org/archlinux/archiso/-/blob/1e534fe4cf3a5abff332ff4287c6e71e89c6ab56/configs/releng/packages.x86_64> · <https://gitlab.archlinux.org/archlinux/archiso/-/blob/1e534fe4cf3a5abff332ff4287c6e71e89c6ab56/configs/releng/airootfs/etc/shadow>

---

## WireGuard through NetworkManager has no kill switch, so a dropped tunnel leaks the real IP

`wireguard-networkmanager-no-kill-switch` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A privacy guide or VPN provider says WireGuard has no kill switch, or a full tunnel WireGuard connection added through NetworkManager was off for a moment (it failed to activate at boot or on a new Wi-Fi network, was switched off to change to another profile, or was taken down with `nmcli connection down`) and during that time traffic left over the ordinary connection carrying the machine's real IP address instead of stopping. Nothing on a stock Omarchy install sets up a tunnel: `wireguard-tools` is not installed, Omarchy ships no NetworkManager GUI, and none of its own scripts mention WireGuard. Nothing needs installing to add one, though. The Arch kernel ships the `wireguard` module and NetworkManager configures it directly, so this applies as soon as a profile exists, for example after `nmcli connection import type wireguard file <name>.conf`. NetworkManager is the only network manager Omarchy runs, and systemd-networkd is disabled.

**Cause.** WireGuard is a network interface, and neither the protocol, `wg-quick` nor NetworkManager ships a kill switch, meaning a firewall rule that blocks ordinary traffic whenever the tunnel is not carrying it. `wg-quick(8)` is explicit that the kill switch is something the user adds: it describes it as an optional `PostUp` line, `iptables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT`, that works together with the fwmark. The only firewall rules `wg-quick` installs on its own, in `add_default()` of `src/wg-quick/linux.bash`, drop inbound packets that arrive on another interface addressed to the tunnel's own IP and connmark the tunnel's UDP handshake traffic. Neither is an egress block. A NetworkManager WireGuard profile has no `PostUp` at all, so not even the optional rule can travel with the profile.

What NetworkManager does provide is the routing half. `wireguard.ip4-auto-default-route` and `wireguard.ip6-auto-default-route`, on by default whenever a peer's `allowed-ips` carries a `/0` route, put the tunnel's default route in a dedicated table with two policy rules, which the settings documentation says corresponds to what `wg-quick` does with `Table=auto`. While the profile is active that routing keeps sending traffic into the tunnel interface even when the tunnel cannot deliver it, so a peer that stops answering or a Wi-Fi handoff does not by itself put packets on the ordinary route. Suspend does not undo it on NetworkManager either: `do_sleep_wake()` in `src/core/nm-manager.c` skips software devices when the system suspends, with a comment that it does not want to destroy them for an external event such as a system suspend, so the WireGuard interface and its routes survive sleep. The Arch wiki's warning that resuming from suspend can expose the public IP unless a kill switch is configured is about systemd-networkd after the systemd 253 change to `ManageForeignRoutingPolicyRules`, and Omarchy does not run systemd-networkd.

The leak window on NetworkManager is whenever the profile is not active: before it activates at boot or on a fresh network, after it fails to activate or is deactivated, and the gap while switching from one profile to another. Both halves are reported upstream. NetworkManager issue 1503 describes the real IP appearing while switching between two WireGuard profiles, and issue 1515 is an open feature request for a kill switch that blocks until the VPN is up and again the moment it goes down. Neither has been implemented as of NetworkManager 1.58.1, and the NEWS file for 1.58 lists no such change.

> **Audit corrected this record.** The record's central claim is wrong and its suspend framing is unsourced, so the cause, symptom, fix, verify and danger are rewritten. Checked `add_default()` in `src/wg-quick/linux.bash` at tag v1.0.20250521: the firewall rules wg-quick installs are a raw-table PREROUTING drop of packets arriving on a non-tunnel interface addressed to the tunnel's own IP, plus CONNMARK save and restore for the UDP handshake. That is an inbound anti-spoofing rule, not the egress drop the record describes, so wg-quick has the same gap NetworkManager has. `wg-quick(8)` at the same tag says so: the kill switch is an optional `PostUp` iptables REJECT the user adds, and the man page notes DHCP survives it only through packet sockets. The routing half held: the NetworkManager settings page and the installed `nm-settings-nmcli(5)` say `ip4-auto-default-route` corresponds to `Table=auto` and is on by default with a `/0` allowed-ips. The suspend trigger did not hold: `do_sleep_wake()` in `src/core/nm-manager.c` at 1.58.0 skips software devices when suspending and only renews their dynamic IP on wake, so the WireGuard interface and its policy routes survive sleep. The Arch wiki sentence the record leaned on is inside the systemd-networkd troubleshooting section and is about the systemd 253 `ManageForeignRoutingPolicyRules` change, and Omarchy does not run networkd. The peer-stops-answering trigger was also unsourced, and with the policy routes in place traffic keeps entering the tunnel interface rather than the ordinary route. Gate 1 now passes on positive evidence rather than silence: NetworkManager issues 1503 (2024-03-26, IP leak when switching WireGuard profiles) and 1515 (2024-04-07, open feature request for a kill switch), both third party and both still open, plus the wg-quick manual documenting the kill switch as opt-in. The 1.58.0 NEWS file lists no kill switch. Confirmed on this workstation, omarchy 4.0.2-1 on 2026-09-18: networkmanager 1.58.1-1 enabled and active, systemd-networkd disabled and inactive, ufw 0.36.2-7 enabled and active with `DEFAULT_OUTPUT_POLICY=ACCEPT` and `IPV6=yes`, `wireguard-tools` absent, the `wireguard` module present under `/usr/lib/modules/7.1.9-arch1-2`, no NM GUI package installed, and no file under `/usr/share/omarchy` mentions wireguard, so the symptom's reference to a settings panel was wrong for Omarchy. `nm-device-wireguard.c` changes the link over `nm_platform_link_wireguard_change` with no spawn of `wg`, and resolves hostname endpoints with GResolver, which is why the fix now requires an IP endpoint. The fix's own claims were wrong in three places: an inbound ssh session does not die, because `before.rules` accept `RELATED,ESTABLISHED` output, while mirrors and NTP do not need rules because they route through the tunnel, and what actually breaks is LAN and multicast traffic, including Avahi's queries on a distro that ships Avahi. The connectivity probe finding comes from `nm-connectivity.c` setting `CURLOPT_INTERFACE` to `if!<iface>`. `nmcli -f wireguard.peers` and `-g wireguard.peers` were accepted by nmcli on the loopback profile, which is read-only. Severity lowered from high to medium: no credential, privilege boundary or code path is exposed, the tool is one the user installs and configures, and the exposure is the machine's real IP and traffic path while the profile is inactive, which is the brief's hardening-control-off case. Not exercised: no tunnel was brought up, no ufw rule was added, the machine was not suspended, and whether NetworkManager's built-in DHCP client renews through a UDP socket that the deny would catch was not checked, which is why the DHCP allow rule is included as a precaution. The title is unchanged because the schema has no corrected_title, and it remains accurate for a deactivated profile.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.2-1 on 2026-09-18.*

> ⚠️ **Risk.** `ufw default deny outgoing` applies to the whole machine, not only the tunnel. Add the allow rules first, in the order above, or every new outgoing connection stops at once. An ssh session already open into the machine survives, because ufw's shipped `before.rules` accept `RELATED,ESTABLISHED` output, but nothing new leaves. Package mirrors, NTP and DNS keep working while the tunnel is up because they are routed through it. What stops is everything that goes outside the tunnel on purpose: the local printer, NAS and other LAN devices, LocalSend, KDE Connect, and Avahi's own multicast queries, so `.local` names and printer discovery stop working on Omarchy while the block is on. Each one you want back needs its own scoped `ufw allow out` rule, and each is traffic that leaves outside the tunnel on whatever network you are on. A profile whose endpoint is a hostname cannot come up once the default is deny, because the name has to be resolved through the tunnel that is not established, and the failure looks like a profile that never activates rather than a firewall block. NetworkManager's connectivity probe of `http://ping.archlinux.org/nm-check.txt` is bound to the Wi-Fi or Ethernet device, so the block stops it too and `nmcli networking connectivity` may report `limited`. That is the probe failing, not the tunnel. To use the machine without the tunnel, run `sudo ufw default allow outgoing`, and remember the protection is off until you set deny again. The wrong fix is to leave outgoing open and trust the routing: it holds while the profile is active and offers nothing when it is not, which is the state this record is about.

**Fix.**

There is no NetworkManager setting that adds this protection, and a NetworkManager profile cannot carry the `PostUp` rule that `wg-quick(8)` documents. Build the block with `ufw`, which Omarchy ships enabled with `default allow outgoing`. Three kinds of traffic have to stay allowed: the tunnel interface itself, the encrypted handshake to the peer's endpoint, which leaves through the ordinary interface, and DHCP to the local router. Read the interface name and the endpoint from the profile first:

```bash
nmcli connection show --active | grep wireguard
nmcli -g wireguard.peers connection show <connection-name>
```

The peer line carries `endpoint=<ip>:<port>`. If it carries a hostname rather than an IP address, re-import the profile from a config whose `Endpoint =` line uses the address before going further, because once outgoing traffic is denied the name can only be resolved through the tunnel that is not up yet. Then add the allow rules before switching the default, in this order:

```bash
sudo ufw allow out on <tunnel-interface> comment 'wireguard tunnel'
sudo ufw allow out proto udp to <endpoint-ip> port <endpoint-port> comment 'wireguard handshake'
sudo ufw allow out proto udp to any port 67 comment 'dhcp'
sudo ufw default deny outgoing
```

`ufw default` takes effect at once while ufw is active and is written to `/etc/default/ufw`, so it holds across reboots. That is what makes this a kill switch rather than a rule that only exists while the tunnel is up: at boot, on a new network and after a failed activation, nothing leaves until the profile is active again. `IPV6=yes` in `/etc/default/ufw` means the deny covers IPv6 too, so traffic with no route into the tunnel is blocked rather than sent in clear. The DHCP rule is there because ufw's shipped `before.rules` accept DHCP replies in and allow nothing out, and `wg-quick(8)` notes that DHCP survives its own rule only because most clients use packet sockets that bypass Netfilter.

To use the machine without the tunnel, switch the default back and leave the allow rules in place:

```bash
sudo ufw default allow outgoing
```

**Verify.** `sudo ufw status verbose` shows `Default: deny (outgoing)` plus an `ALLOW OUT` line for the tunnel interface, one for the endpoint address and port, and one for `67/udp`. `nmcli -g wireguard.peers connection show <connection-name>` shows the endpoint as an IP address rather than a hostname. `ip link show` lists the WireGuard device under the same name the rule uses, since a name that does not match leaves the rule matching nothing. The check is that the rules exist, not that traffic is dropped, so nothing here needs the tunnel taken down.

Sources: <https://wiki.archlinux.org/title/WireGuard> · <https://networkmanager.dev/docs/api/latest/settings-wireguard.html> · <https://git.zx2c4.com/wireguard-tools/tree/src/man/wg-quick.8?h=v1.0.20250521> · <https://git.zx2c4.com/wireguard-tools/tree/src/wg-quick/linux.bash?h=v1.0.20250521> · <https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/issues/1515> · <https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/issues/1503> · <https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/blob/1.58.0/src/core/nm-manager.c> · <https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/blob/1.58.0/NEWS> · <https://git.launchpad.net/ufw/plain/conf/before.rules>

---

## omarchy-remove-security-sshd under sudo or pkexec checks root's authorized_keys, not yours

`omarchy-remove-security-sshd-edits-root-authorized-keys` · severity: **medium** · frequency: **rare** · applies to: `desktop`, `laptop`, `omarchy`

**Symptom.** I ran omarchy-remove-security-sshd, or an agent ran it for me, to pull my SSH access. sshd stopped and the firewall port closed, but did it actually clear my authorized_keys?

**Cause.** `bin/omarchy-remove-security-sshd` resolves the keys file with no derivation of the invoking user:

```bash
AUTHORIZED_KEYS="$HOME/.ssh/authorized_keys"
```

The sibling privileged command `omarchy-apply-lock` derives the real target user first (`OMARCHY_INSTALL_USER`, then `SUDO_USER`, then a lookup on `PKEXEC_UID`) before it touches a path under that user's home. `omarchy-remove-security-sshd` does not. Under either `sudo` or `pkexec`, `$HOME` is `/root` for the whole script: `sudo` resets it to the target user's home under the default `env_reset`, and `pkexec` builds a fixed environment with `HOME` set to root's home directory. The removal prompt therefore inspects root's `authorized_keys` instead of the invoking user's. Root usually has none, so `[[ -s $AUTHORIZED_KEYS ]]` is false, the prompt is silently skipped, and the invoking user's real key is never touched. If root does have an `authorized_keys`, the prompt offers to delete root's keys instead. sshd is genuinely stopped and the firewall port genuinely closed in the same run, so it looks like it worked, but the key stays valid in the user's own `~/.ssh/authorized_keys` and is live again the moment sshd is re-enabled.

No shipped path wraps the command. The omarchy menu launches it plain, `omarchy-launch-floating-terminal-with-presentation omarchy-remove-security-sshd`, in `default/omarchy/omarchy-menu.jsonc`. The `omarchy` CLI execs the binary with no wrapper. The script's `omarchy:requires-sudo=true` header is metadata that `omarchy commands --json` reports and nothing acts on. `default/agents/skills/omarchy/SKILL.md` tells an agent with no terminal to use `pkexec` for privileged work and, in the same sentence, not to wrap commands that already manage their own elevation, which this script does by calling `sudo` itself. The gap is reached only by prefixing the command with `sudo` at a terminal, or by an agent or script running it under `pkexec` against that instruction.

> **Audit corrected this record.** Gate 1 holds: issue 9572 and its fix PR 9573 were opened by shaynhornik on 2026-09-01, not by the account this repository uses, and the PR is still open and unmerged at the pinned sha d174d4a, the quattro tip as of 2026-09-18. Confirmed on this workstation: /usr/share/omarchy/bin/omarchy-remove-security-sshd is byte-identical to the pinned sha and line 8 reads AUTHORIZED_KEYS="$HOME/.ssh/authorized_keys" with no derivation of the invoking user. pkexec sets HOME to the target user's home directory and PATH to a fixed root PATH (polkit src/programs/pkexec.c lines 984 to 991), and /usr/bin/omarchy-cmd-present exists, so under pkexec the firewall step still runs. sudoers(5) says env_reset, on by default, sets HOME to the target user's home. I could not read /etc/sudoers or the four omarchy-settings drop-ins under /etc/sudoers.d, so an env_keep of HOME on this machine is not excluded, only unlikely. Gate 3 holds. Gate 2 fails in one place, and it is the record's central claim about how the bad invocation happens: the cause says the Omarchy skill tells an agent to run this command under pkexec. It does not. default/agents/skills/omarchy/SKILL.md line 53, at the pinned sha and as installed, says to use pkexec when no terminal is available and then, in the same sentence, Do not wrap commands that already manage privilege elevation themselves. This script manages its own elevation, calling sudo at lines 13, 17 and 18, so an agent following the skill runs it unwrapped. The requires-sudo=true header is metadata the omarchy CLI only reports through omarchy commands --json (bin/omarchy line 677), and the CLI itself execs the binary with no wrapper (line 1044), as does the menu entry at omarchy-menu.jsonc line 286 as installed. The defect is real, but it needs a person or an agent to type sudo or pkexec in front of a command that does not ask for it. The issue also states the second branch the record omits: when root does have an authorized_keys, the prompt offers to delete root's keys instead. Severity high does not meet the scale: sshd is disabled and the port closed in the same run, so the leftover key is reachable only if sshd is enabled again later. No credential or privilege boundary is exposed by the run itself, which is a control that failed silently, medium. Frequency drops to rare for the same reason, the menu, the CLI and the skill's own rule all produce the unwrapped invocation. The cited omarchy-apply-lock differs on disk from the pinned sha (the installed 4.0.2-1 copy lacks the EUID PATH block) but both derive the target user the same way. The sed line in the fix used a made-up pattern beginning AAAA, which is the prefix of every key's base64 body, so a reader who kept it would match nothing or, editing it wrong, every key. Not exercised: the command was not run under any wrapper, and no authorized_keys file was touched. Re-checked against 4.0.4-1 2026-09-19: Re-checked on 2026-09-19 against Omarchy 4.0.4-1 on this workstation and against the v4.0.4 tag, sha c668141. bin/omarchy-remove-security-sshd at v4.0.4 is byte-identical to the installed copy and to the previously pinned d174d4a. Line 8 still reads AUTHORIZED_KEYS="$HOME/.ssh/authorized_keys" with no derivation of the invoking user, and sudo is still called by the script itself at lines 13, 17 and 18. bin/omarchy-apply-lock still derives the target user from OMARCHY_INSTALL_USER, then SUDO_USER, then PKEXEC_UID. Its only v4.0.3 or v4.0.4 change is a fixed PATH when run as root, which does not touch that derivation. The menu entry, now at default/omarchy/omarchy-menu.jsonc line 294 because entries were added above it, still launches the command unwrapped. bin/omarchy still reads requires-sudo only as metadata and execs the binary directly. default/agents/skills/omarchy/SKILL.md line 53 still says not to wrap commands that manage their own elevation. Issue 9572 and fix PR 9573 are open and unmerged. Open PR 10717 edits the same script but only stops it continuing after a failed systemctl disable, and does not change how the keys path is resolved. Nothing in the v4.0.2 to v4.0.4 compare touches the script. Severity medium and frequency rare still fit the brief's scale. Gates 1, 2 and 3 still hold. Not exercised: the command was not run with or without a wrapper, and no authorized_keys file was touched.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** Running the command under sudo or pkexec still stops sshd and closes the firewall port, so the session looks successful. The key left behind is the one piece the run was supposed to remove, and it becomes reachable again the moment sshd is re-enabled, for example by a later omarchy-setup-security-sshd. Do not treat a clean run of omarchy-remove-security-sshd as proof that one specific key is gone. Check ~/.ssh/authorized_keys directly.

**Fix.**

Invoke the command the way the omarchy menu does, plain and unwrapped, so `$HOME` stays yours. The `systemctl` and `ufw` calls inside it call `sudo` themselves and prompt for a password on their own:

```bash
omarchy-remove-security-sshd
```

Whichever way it was run, read your own file afterwards rather than trusting the prompt:

```bash
cat ~/.ssh/authorized_keys
```

If a key you meant to revoke is still listed, delete its line by the comment at the end of the line, which is usually `user@host`:

```bash
sed -i '/ user@host$/d' ~/.ssh/authorized_keys
```

or empty the file if you keep no other keys in it:

```bash
: > ~/.ssh/authorized_keys
```

**Verify.** `cat ~/.ssh/authorized_keys` no longer lists the key you meant to revoke, and `systemctl is-enabled sshd` reports disabled or fails.

Sources: <https://github.com/omacom/omarchy/issues/9572> · <https://github.com/omacom/omarchy/blob/d174d4aa279ea7393d4fad4a80fed147866106b9/bin/omarchy-remove-security-sshd> · <https://github.com/omacom/omarchy/blob/d174d4aa279ea7393d4fad4a80fed147866106b9/bin/omarchy-apply-lock> · <https://github.com/omacom/omarchy/blob/d174d4aa279ea7393d4fad4a80fed147866106b9/default/agents/skills/omarchy/SKILL.md> · <https://github.com/omacom/omarchy/blob/d174d4aa279ea7393d4fad4a80fed147866106b9/default/omarchy/omarchy-menu.jsonc> · <https://github.com/omacom/omarchy/pull/9573> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-remove-security-sshd> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/default/agents/skills/omarchy/SKILL.md>

---

## omarchy-debug bundles unredacted LAN MAC and IP addresses, and the bug template asks you to attach it

`omarchy-debug-exposes-lan-macs-and-ips` · severity: **low** · frequency: **occasional** · applies to: `omarchy`

**Symptom.** You are about to attach the log from omarchy-debug to a bug report, because the issue template asks you to "attach the output of omarchy-debug if possible," and you want to know what is actually in it before pasting it somewhere public.

**Cause.** bin/omarchy-debug writes `sudo dmesg` and `journalctl -b -p 4..1` into the log with no filtering. ufw's default is `LOGLEVEL=low` (`/etc/ufw/ufw.conf`, and `man ufw` says ufw defaults to a loglevel of 'low'), Omarchy's installer enables ufw, and the `[UFW BLOCK]` LOG rules set no log level, so every blocked packet is logged by the kernel at warning level as a `[UFW BLOCK]` line carrying the source and destination MAC and IP addresses of devices on the local network. The journal section reproduces the same lines because `-p 4..1` includes warnings. On a laptop that has associated to Wi-Fi that boot, the kernel's own association messages in both sections carry the access point's BSSID, which public wardriving databases can resolve to a physical location. Outside the firewall lines the same sections carry the addresses of paired Bluetooth devices, which BlueZ prints in uppercase where the kernel prints lowercase, and any address a service put in a warning, such as the DNS server in a systemd-resolved message. The hostname is written twice over: once on the `Hostname:` line the script adds itself, and again as the prefix of every journal line, because the script uses journalctl's default output format. The `inxi -Farz` call in the same script is filtered, since `-z` masks IP addresses, serial numbers and MAC addresses in its own section, so the smallest section of the log is redacted and the two largest are not.

> **Audit corrected this record.** Gate 1 holds: issue #10255 (wbnns, 2026-09-04) and PR #10257 (open, unmerged as of 2026-09-18) are by a third party and predate anything here. Gate 2 held on the cause but not on the fix: the record is scoped to MAC addresses and [UFW BLOCK] lines while its own sources go further. The issue names the hostname on the Hostname: line and the PR review measured it 41 times in one run through the journal prefix, the PR review found a real IPv6 address in a systemd-resolved warning outside the firewall lines, and a reviewer found the lowercase-only MAC pattern the record uses misses the uppercase form BlueZ prints, so the record's verify reports a clean file that is not. The record's danger argues against masking dotted quads because of version strings, which the PR author retracted in the PR itself: it is true of the whole file and false of the two sections the leak lives in, so the fix is rewritten to scope every substitution to the DMESG and JOURNALCTL sections with a sed range, mask the hostname where the script writes it, keep loopback, link-local and unspecified addresses, and surface IPv6 candidates for review rather than pretend a paste-sized pattern handles them. The rewritten recipe was tested on a synthetic log in a scratch directory, never on this machine's output. Confirmed on this machine: /usr/bin/omarchy-debug (omarchy-settings 4.0.2-1) is byte-identical to the pinned blob and to current quattro, so the fix applies to the installed version, /etc/ufw/ufw.conf carries LOGLEVEL=low and man ufw says low is the default, and the [UFW BLOCK] LOG rules in /etc/ufw/user.rules set no --log-level, which is consistent with the warning level the issue reports but was not checked against kernel source. The script also leaves the unscrubbed file at /tmp/omarchy-debug.log with mode 0644, which the fix now removes. Gate 3 holds. Severity lowered from high to low: the brief's low level is information disclosure with no credential value, which is exactly this. Nothing on the machine is exposed to anyone by the default, no attacker acts against the machine, and the only path to a reader is the user attaching the file, which is the step the record intervenes in. The BSSID-to-location consequence is why the record exists, and it is still disclosure without credential value. Not exercised: omarchy-debug was not run here. Re-checked against 4.0.4-1 2026-09-19: Re-checked against 4.0.4-1 on 2026-09-19. /usr/bin/omarchy-debug (omarchy-settings 4.0.4-1) is byte-identical to the v4.0.4 tag (c668141e9c42b13c80c9ca4ea108e11708c5e8a5) and to the pinned blob at 9174fbf, and the quattro history for bin/omarchy-debug has no commit after 9174fbf, so every line the cause and fix rely on still holds: the fixed /tmp/omarchy-debug.log path, unfiltered `sudo dmesg` and `journalctl -b -p 4..1`, the `Hostname:` line, filtered `inxi -Farz`, and the section headers the sed ranges key on. The bug template at the v4.0.4 tag is byte-identical to the pinned 14f8038 blob and still asks for `omarchy-debug` output on line 22. On this machine /etc/ufw/ufw.conf still carries LOGLEVEL=low and the [UFW BLOCK] LOG rules in /etc/ufw/user.rules still set no --log-level. Issue #10255 and PR #10257 are both still open, and neither changed after 2026-09-08. None of the 145 files in the v4.0.2...v4.0.4 compare touches the script, the template or ufw. The only text change is the dated currency claim in fix, now 2026-09-19 with the version range named. PR #7995 (open, 2026-08-24, third party) independently describes the fixed /tmp path and its 0644 mode, so it is added as a source for that sentence. Other open PRs touch the script without redacting anything (#10548 swaps hostname for uname -n, #9477 and #8828 change collectors). If #10548 merges, the fix still works because `uname -n` and `hostname` return the same nodename. Not exercised: omarchy-debug was not run and nothing was uploaded.
>
> *The Cause above was rewritten on 2026-09-18 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** Do not scrub the whole file with a broad address pattern. Outside the `DMESG` and `JOURNALCTL` sections every dotted-quad string is a version number, `inxi 3.3.41.1` and every package in the list, and masking those corrupts the parts of the report that are actually diagnostic, so scope the substitutions to the two sections as above. Do not treat a zero count from a lowercase-only MAC pattern as clean: the kernel prints MAC addresses in lowercase and BlueZ prints them in uppercase, and a lowercase-only check reported the first version of PR #10257 clean while a paired Bluetooth device's address remained. The script writes the unscrubbed original to `/tmp/omarchy-debug.log` on every run, so remove it each time.

**Fix.**

There is no flag that redacts the kernel and journal sections, and the upstream change that would do it, PR #10257, is open and unmerged as of 2026-09-19, and `bin/omarchy-debug` is unchanged from 4.0.2-1 through 4.0.4-1. `--no-sudo` skips dmesg entirely but leaves the journal untouched, and the bug template does not mention it. Before attaching a debug log anywhere public, generate it, remove the unscrubbed copy the script leaves at `/tmp/omarchy-debug.log` (mode 0644, readable by every local account), and scrub the two unfiltered sections. The script asks for your sudo password for `dmesg`.

```bash
omarchy-debug --print > ~/omarchy-debug-review.log
rm -f /tmp/omarchy-debug.log
```

Mask the hostname where the script writes it, on the `Hostname:` line and as the prefix of every journal line:

```bash
sed -i -E -e 's/^Hostname: .*/Hostname: <host>/' \
  -e "/^JOURNALCTL/,/^INSTALLED PACKAGES\$/ s/^([A-Z][a-z]{2} [ 0-9][0-9] [0-9:]{8}) $(hostname) /\1 <host> /" \
  ~/omarchy-debug-review.log
```

Then, only between the `DMESG` and `INSTALLED PACKAGES` headers so the inxi report and the package list are never touched, drop the firewall lines and mask MAC addresses in either case and IPv4 addresses. Loopback, link-local and the unspecified address are kept because they identify nobody and a failed DHCP lease shows as `169.254.x.x`:

```bash
sed -i -E '/^DMESG$/,/^INSTALLED PACKAGES$/{
/\[UFW BLOCK\]/d
s/(^|[^0-9A-Za-z:])([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}($|[^0-9A-Za-z:]|:($|[^0-9A-Fa-f]))/\1<mac>\3/g
s/(^|[^0-9A-Za-z:])([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}($|[^0-9A-Za-z:]|:($|[^0-9A-Fa-f]))/\1<mac>\3/g
s/(^|[^0-9.])(127|0|169)\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})/\1\2_\3_\4_\5/g
s/(^|[^0-9.])([0-9]{1,3}\.){3}[0-9]{1,3}($|[^0-9.])/\1<ip>\3/g
s/(^|[^0-9.])([0-9]{1,3}\.){3}[0-9]{1,3}($|[^0-9.])/\1<ip>\3/g
s/(^|[^0-9.])(127|0|169)_([0-9]{1,3})_([0-9]{1,3})_([0-9]{1,3})/\1\2.\3.\4.\5/g
}' ~/omarchy-debug-review.log
```

The MAC and IPv4 rules each run twice so two addresses one character apart are both caught. A four-number version string inside those two sections, such as a firmware version, can come out as `<ip>`, which costs nothing. IPv6 addresses are not masked automatically: a pattern short enough to paste here also matches timestamps and C++ names such as `Foo::bar`, so list the candidates and mask any real address by hand:

```bash
grep -nE '[0-9A-Fa-f]{1,4}(:[0-9A-Fa-f]{1,4}){3,}|[0-9A-Fa-f]{1,4}::|::[0-9A-Fa-f]' ~/omarchy-debug-review.log
```

Attach `~/omarchy-debug-review.log`, not the original.

**Verify.** Confirm the firewall lines and the hostname are gone from the review copy, and review what remains rather than assuming it is clean:

```bash
grep -c '\[UFW BLOCK\]' ~/omarchy-debug-review.log
grep -Eic '([0-9a-f]{2}:){5}[0-9a-f]{2}' ~/omarchy-debug-review.log
grep -nF "$(hostname)" ~/omarchy-debug-review.log
```

The first reads 0. The second counts case-insensitively, which is what catches the uppercase form BlueZ prints, and reads 0 unless a colon-separated fingerprint such as `SHA256:aa:bb:...` remains, which is not an address. The third prints nothing, and any line it does print, for example an Avahi `Host name is ...` message, is masked by hand before you attach the file.

Sources: <https://github.com/omacom/omarchy/issues/10255> · <https://github.com/omacom/omarchy/pull/10257> · <https://github.com/omacom/omarchy/blob/9174fbf8515f4c057c91071ec39af731602adb92/bin/omarchy-debug> · <https://github.com/omacom/omarchy/blob/14f803857cf9965fac0cb480b8dad345c7f0065c/.github/ISSUE_TEMPLATE/bug.yml> · <https://github.com/omacom/omarchy/pull/7995> · <https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/bin/omarchy-debug>

---

## A multi-line Secret Service value destroys Omarchy's passwordless default keyring, and autologin can never unlock what replaces it

`omarchy-default-keyring-corrupted-by-multiline-secret` · severity: **low** · frequency: **occasional** · applies to: `omarchy`

**Symptom.** After autologin, an "Authentication required, An application wants access to the keyring Default Keyring, but it is locked" prompt starts appearing on every boot, for no configuration change you made. Chrome, Chromium, VS Code, Slack, gh, or other Secret Service clients may also stop finding credentials they had before.

**Cause.** Omarchy's default keyring is cleartext by design: `install/user/default-keyring.sh` writes `~/.local/share/keyrings/Default_keyring.keyring` with a `[keyring]` header and no password, and writes the `default` pointer file naming it. `install/login/sddm.sh` deletes the `-auth` and `-password` `pam_gnome_keyring.so` lines from `/etc/pam.d/sddm` so that a password login cannot create an encrypted login keyring that competes with the passwordless one. The `-session ... auto_start` line stays, and `/etc/pam.d/sddm-autologin`, the service an autologin session actually goes through, is not edited at all and still carries the `-auth` line, which is why the journal shows `gkr-pam: no password is available for user` on every boot. Both scripts are unchanged from 4.0.2-1 through 4.0.4-1, and PR #10396, which applies the same edit to `/etc/pam.d/sddm-autologin`, is open and unmerged as of 2026-09-19.

The cleartext format is a GLib key file. In gnome-keyring's `pkcs11/secret-store/gkm-secret-textual.c` a secret is written with `g_key_file_set_value()`, which does no escaping, and read back with `g_key_file_get_string()`, which unescapes. A Secret Service client that stores a value containing a raw newline, reported on the issue for Ente Auth through `flutter_secure_storage_linux` and for Proton VPN's SSO session item, which embeds PEM certificates, therefore writes physical line breaks into the `secret=` line. The daemon keeps serving the value from memory for the rest of that session, then rejects the whole file at the next start with `keyring was in an invalid or unrecognized format`. Every other secret in the file goes with it: Chromium's `Chromium Safe Storage` key, `gh`, Slack, VS Code and Proton were all reported lost this way. With no loadable default keyring, the next client to ask for a secret triggers gnome-keyring's create-a-keyring prompt, the keyring it creates is password-protected, `default` is repointed at it, and from then on autologin gives PAM nothing to unlock it with, so the locked-keyring prompt returns on every boot. A newline in a secret is legal in the Secret Service API and the password-protected format stores bytes opaquely, so the fault is specific to the cleartext format chosen for autologin, and any client can trigger it. The daemon side is unfixed upstream: `gkm-secret-textual.c` has not changed since 2014, gnome-keyring 1:50.0-1 is what Arch and Omarchy 4.0.4 install, the 51.0 and 51.1 releases leave that file alone, and merge request 111, which writes the value with `g_key_file_set_string()` so GLib escapes the newline, is open.

> **Audit corrected this record.** Gate 1 holds: issue #11159 (duckzooka, 2026-09-10, with three independent reproductions), gnome-keyring issues 103 (2022) and 147 (2024) and ProtonVPN/python-proton-keyring-linux issue 5 (2026-08-26) all predate this repository, and the cleartext default is written by a shipped script. Gate 2 mostly held, with two defects in the cause. The record says sddm.sh strips pam_gnome_keyring from /etc/pam.d/sddm because autologin never gives PAM a password, but the script's own comment gives a different reason, preventing a password login from creating an encrypted login keyring, and it deletes only the -auth and -password lines: /etc/pam.d/sddm on this machine still has the -session auto_start line, and /etc/pam.d/sddm-autologin, the service an autologin session actually uses, is not edited at all and still carries the -auth line, which is the source of the gkr-pam messages quoted in the issue. The write-without-escaping claim was checked against gnome-keyring's gkm-secret-textual.c, where the secret is written with g_key_file_set_value and read with g_key_file_get_string, so it is confirmed from code rather than only from a comment. The fix was the real problem. Its cp backup is a one-shot snapshot that goes stale the moment any client stores a secret, the record never says how to use it, and restoring it over a live daemon would be the wrong move anyway, so it neither prevents the corruption nor recovers from it. The corrected fix gives the Proton override, checked against python-proton-core's loader (it reads PROTON_LOADER_OVERRIDES, and the json entry point exists in that package's setup.py), and a recovery that does what PR #11697 does: move the unparseable and password-protected files aside, rewrite the stub from default-keyring.sh, repoint default, then log out. That recipe was not exercised on this machine or a VM, which is why confidence is medium. It cannot destroy stored secrets because nothing is deleted, and danger now says plainly that it does not put them back either. Confirmed on 4.0.2-1: default-keyring.sh and sddm.sh are byte-identical to the pinned blobs, /usr/bin/omarchy-keyring-repair does not exist and is not in current quattro, PR #11697 is open and unmerged as of 2026-09-18, and the default pointer file is a bare name. The existing record keyring-reset-after-update-logins-cleared covers the same end state by a different mechanism, and its repoint-only recipe cannot work here, which the fix now says. Gate 3 holds. Severity lowered from medium to low. The record's mechanism is an integrity failure with no attacker: nobody reaches a credential, crosses a privilege boundary or runs code. The only security default in it, secrets stored in cleartext at rest, is readable only by the user's own account or by whoever already holds the disk, which is the brief's low level, a weakness needing an already compromised local account, and on the default LUKS install the disk is encrypted. The operator may prefer apps-services for this record. The harvester's quoted dialog text drops the source's punctuation but the words match the issue. Re-checked against 4.0.4-1 2026-09-19: Re-checked against 4.0.4-1 on 2026-09-19. install/user/default-keyring.sh and install/login/sddm.sh are byte-identical between the pinned 75cb4f7 blobs, the v4.0.4 tag (c668141e9c42b13c80c9ca4ea108e11708c5e8a5) and the installed copies under /usr/share/omarchy/install (omarchy 4.0.4-1), and neither has a quattro commit after 75cb4f7. On this machine /etc/pam.d/sddm still has only the `-session ... auto_start` gnome-keyring line and /etc/pam.d/sddm-autologin (owned by sddm 0.21.0-7) still has the `-auth` and `-session` lines. /usr/bin/omarchy-keyring-repair does not exist and no such file is in the v4.0.4 tree. None of the 145 files in the v4.0.2...v4.0.4 compare touches the keyring or PAM. The one migration mentioning a keyring, 1787589206.sh, is the pacman packaging key and unrelated. Issue #11159, PR #11697 and PR #10396 are all open. The issue's newest comment, 2026-09-16, reproduces the fault on gnome-keyring 1:50.0. Package side: gnome-keyring 1:50.0-1 and libsecret 0.21.7-1 are installed, both since 2026-08-22, and neither moved with the Omarchy upgrade. Arch extra still ships gnome-keyring 1:50.0-1. libsecret is 0.21.8.2-1 in Arch core, but it is the client library and the fault is in the daemon's file writer. Upstream gnome-keyring is unfixed: gkm-secret-textual.c was last changed in 2014, the 50.0 to 51.1 compare does not touch it, issues 103 and 147 are open, and merge request 111 (opened 2026-08-25 by a third party) is the open fix, so the cause gains one sentence saying so and the source. Text changes are the version and date in cause and fix, the open PR #10396 in cause, and the upstream status. `omarchy logout` still resolves on 4.0.4-1 through the alias in /usr/bin/omarchy-system-logout. Confidence stays medium because the recovery recipe has still not been exercised on this machine or a VM. The keyring was not read or changed.
>
> *The Cause above was rewritten on 2026-09-19 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy 4.0.4-1 on 2026-09-19.*

> ⚠️ **Risk.** Do not delete `~/.local/share/keyrings/` or any file in it to clear the prompt. Every secret it holds, including ones unrelated to whatever broke the file, is gone with it. The recovery above moves files aside for the same reason. It does not put the secrets back: every application has to be signed into again, and anything an application encrypted with a key it kept in the keyring, such as Chromium's saved passwords and cookies under `Chromium Safe Storage`, is unreadable to it after the reset unless that one item is restored by hand from the moved-aside file. Typing a password into the unlock dialog does not fix anything either: it opens the password-protected replacement for one session, and autologin cannot open it at the next boot, so the prompt returns. Do not answer it by adding an `auth` `pam_gnome_keyring.so` line to a PAM file: an autologin session goes through `/etc/pam.d/sddm-autologin`, which still has that line and no password to give it.

**Fix.**

There is no shipped repair as of 4.0.4-1: `/usr/bin/omarchy-keyring-repair` does not exist, and PR #11697, which adds it as an early user unit that moves a corrupt or password-protected default aside and rewrites the cleartext stub, is open and unmerged as of 2026-09-19. Two things you can do now.

**Keep an application that writes multi-line values out of gnome-keyring, where it lets you.** python-proton-core's loader reads `PROTON_LOADER_OVERRIDES`, and `keyring=json` selects its own JSON-file backend under `~/.config/Proton/`, so Proton VPN never touches the keyring. `environment.d` is read by the user manager at login, so log out and in afterwards:

```bash
mkdir -p ~/.config/environment.d
echo 'PROTON_LOADER_OVERRIDES=keyring=json' > ~/.config/environment.d/proton-vpn.conf
```

Ente Auth has no equivalent switch, so this closes the hole only for clients that have one.

**Recover once the prompt has appeared.** Do it the way PR #11697 does, by moving files aside rather than deleting anything. See what is there and which keyring `default` names now:

```bash
ls -la ~/.local/share/keyrings/
cat ~/.local/share/keyrings/default
```

Move the replacement keyring and the unparseable cleartext one aside, write a fresh stub identical to what `install/user/default-keyring.sh` writes, and point `default` back at it:

```bash
cd ~/.local/share/keyrings
stamp=$(date +%Y%m%d%H%M%S)
cur=$(tr -d '[:space:]' < default)
[[ $cur != Default_keyring && -f $cur.keyring ]] && mv -- "$cur.keyring" "$cur.keyring.broken-$stamp"
[[ -f Default_keyring.keyring ]] && mv -- Default_keyring.keyring "Default_keyring.keyring.broken-$stamp"
cat > Default_keyring.keyring <<EOF
[keyring]
display-name=Default keyring
ctime=$(date +%s)
mtime=0
lock-on-idle=false
lock-after=false
EOF
printf 'Default_keyring\n' > default
chmod 700 . && chmod 600 Default_keyring.keyring && chmod 644 default
```

Then log out straight away with `omarchy logout`, without starting another application, because the running daemon still holds the old keyring in memory and can write it back. After the next login the empty cleartext keyring is the default and the prompt is gone. Sign in again to each application that had a secret. The moved-aside cleartext file still holds its values on `secret=` lines and can be read for re-entry. The issue describes a lossless alternative, folding each stray continuation line back into its `secret=` line as a literal `\n`, which is what `g_key_file_get_string()` expects, but no shipped script does it as of 4.0.4-1.

The repoint-only recipe in `keyring-reset-after-update-logins-cleared` does not work here: `Default_keyring.keyring` itself is unparseable, so pointing `default` back at it reproduces the rejection.

**Verify.** After the next login, confirm the daemon loaded the cleartext keyring and the pointer is back on it:

```bash
cat ~/.local/share/keyrings/default
head -1 ~/.local/share/keyrings/Default_keyring.keyring
journalctl -b -g 'invalid or unrecognized format'
```

The first prints `Default_keyring`, the second `[keyring]`, and the third prints nothing for this boot. For Proton VPN, confirm the override reached the session:

```bash
systemctl --user show-environment | grep PROTON_LOADER_OVERRIDES
```

Sources: <https://github.com/omacom/omarchy/issues/11159> · <https://github.com/omacom/omarchy/pull/11697> · <https://github.com/omacom/omarchy/blob/75cb4f7195cfc064d05cd30623b3254c9541ba3c/install/user/default-keyring.sh> · <https://github.com/omacom/omarchy/blob/75cb4f7195cfc064d05cd30623b3254c9541ba3c/install/login/sddm.sh> · <https://gitlab.gnome.org/GNOME/gnome-keyring/-/blob/165f0e3210e32538c847be91896736c17a1f6ad6/pkcs11/secret-store/gkm-secret-textual.c> · <https://gitlab.gnome.org/GNOME/gnome-keyring/-/issues/103> · <https://gitlab.gnome.org/GNOME/gnome-keyring/-/issues/147> · <https://github.com/ProtonVPN/python-proton-keyring-linux/issues/5> · <https://github.com/ProtonVPN/python-proton-core/blob/53202abdc1a64587884110192e02c31c2c8de04e/proton/loader/loader.py> · <https://github.com/omacom/omarchy/pull/10396> · <https://gitlab.gnome.org/GNOME/gnome-keyring/-/merge_requests/111>

---
