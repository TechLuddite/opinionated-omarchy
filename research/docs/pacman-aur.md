# pacman & AUR

35 problems. Sorted by severity, then by how often users hit it.

## DKMS module fails to build during a kernel upgrade, leaving a kernel with no working module

`dkms-module-build-fails-on-kernel-upgrade` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** During `pacman -Syu` / `omarchy update`:
```
(3/9) Install DKMS modules
==> dkms install --no-depmod nvidia/580.95.05 -k 7.1.10-arch1-1
Error! Bad return status for module build on kernel: 7.1.10-arch1-1 (x86_64)
Consult /var/lib/dkms/nvidia/580.95.05/build/make.log for more information.
error: command failed to execute correctly
```
After rebooting: no graphical session, or
```
modprobe: FATAL: Module nvidia not found in directory /lib/modules/7.1.10-arch1-1
```
VirtualBox users see: `Kernel driver not installed (rc=-1908)`.

**Cause.** Two distinct causes. **(a) Missing or mismatched headers** — DKMS builds against `/usr/lib/modules/<kernelver>/build`, which is supplied by the *matching* headers package. If `linux-headers` was never installed, or you run `linux-lts` but only have `linux-headers` (not `linux-lts-headers`), DKMS has nothing to compile against. **(b) The out-of-tree source genuinely does not compile against the new kernel** — extremely common with `nvidia-dkms` on a freshly released mainline kernel — or a stale toolchain earlier in `PATH` (classically `/opt/cuda/bin` supplying an old gcc) is picked up instead of the system gcc, producing errors like `gcc: error: unrecognized command-line option '-fmin-function-alignment=16'`.

> ⚠️ **Risk.** Rebooting with a failed DKMS build on an NVIDIA-only machine gives you a black screen or a bare text console with no compositor, and no network manager GUI to fetch a fix with. Keep `linux-lts` + `linux-lts-headers` installed and selectable in the boot menu before you reboot. Never try to fix this with `pacman -Sy nvidia-dkms` — a `-Sy` without `-u` creates a partial upgrade and makes it strictly worse. Always do a full `pacman -Syu` (`omarchy update` on Omarchy). Do not delete `/var/lib/dkms` to "start clean": that loses the build state for every module including ones that currently work.

**Fix.**

**1. See what you actually have:**

```bash
pacman -Q linux linux-lts linux-zen 2>/dev/null
pacman -Q linux-headers linux-lts-headers linux-zen-headers 2>/dev/null
dkms status
uname -r
```

`dkms status` must list your module as `installed` for **every** kernel version present in `/usr/lib/modules`.

**2. Install one headers package per installed kernel** (this is the fix in the majority of cases):

```bash
sudo pacman -S --needed linux-headers
# add these only for kernels you actually have:
# sudo pacman -S --needed linux-lts-headers linux-zen-headers
```

**3. Rebuild for every installed kernel:**

```bash
sudo dkms autoinstall                       # running kernel
for d in /usr/lib/modules/*/; do
  kver=$(basename "$d")
  [ -d "$d/build" ] && sudo dkms autoinstall -k "$kver"
done
dkms status
```

**4. If it still fails, read the real compiler error** — the pacman output only points at it:

```bash
dkms status                                  # gives you <module>/<version>
sudo tail -n 80 /var/lib/dkms/nvidia/*/build/make.log     # substitute your module
```

**5. Stale compiler in PATH** (the `unrecognized command-line option` class):

```bash
gcc --version                # must be the system gcc, not a CUDA/toolchain copy
sudo env -i PATH=/usr/bin:/usr/sbin HOME=/root dkms autoinstall
```
Remove the offending `export PATH="/opt/cuda/bin:$PATH"` from `~/.bashrc` / `~/.zshenv` and re-run.

**6. If upstream is simply not compatible with the new kernel yet, sit on LTS until it is:**

```bash
sudo pacman -S --needed linux-lts linux-lts-headers
sudo dkms autoinstall -k "$(basename /usr/lib/modules/*-lts)"
sudo mkinitcpio -P
# Omarchy: regenerate the UKI + boot entries so linux-lts is selectable
sudo limine-mkinitcpio && sudo limine-update
```

**7. Rebuild the initramfs last**, so the freshly built module actually gets bundled:

```bash
sudo mkinitcpio -P          # Omarchy: sudo limine-mkinitcpio && sudo limine-update
```

**Verify.** `dkms status` shows `installed` for the running kernel *and* every other kernel in `/usr/lib/modules`; `modinfo nvidia | head -3` (or `modinfo vboxdrv`) resolves without error; after reboot `lsmod | grep -E 'nvidia|vboxdrv'` is non-empty and `nvidia-smi` prints a driver version.

Sources: <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://bbs.archlinux.org/viewtopic.php?id=295952> · <https://archlinux.org/packages/extra/any/dkms/files/> · <https://man.archlinux.org/man/alpm-hooks.5> · <https://wiki.archlinux.org/title/Limine>

---

## Recover from a partial upgrade that broke shared libraries

`partial-upgrade-broken-shared-libraries` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** After running `pacman -Sy something` or `pacman -S something` without a full upgrade, programs start dying with things like:
```
foo: error while loading shared libraries: libbar.so.5: cannot open shared object file: No such file or directory
```
Sometimes pacman or sudo itself stops working.

**Cause.** Arch is a rolling release with no version pinning. `pacman -Sy` refreshes the sync database but installs nothing, so the next `pacman -S pkg` pulls in a *new* library while the rest of the system still links against the *old* soname. Partial upgrades are explicitly unsupported. `pacman -Syuw` and aggressive `IgnorePkg`/`IgnoreGroup` cause the same damage.

> ⚠️ **Risk.** Do NOT 'fix' a missing soname by symlinking libbar.so.5 -> libbar.so.6. Soname bumps mean the ABI is incompatible; the symlink will produce silent memory corruption and crashes. Also, once `-Sy` has run you must finish the `-Su` before doing any other package operation.

**Fix.**

Complete the upgrade you started — this is the fix, not a workaround:

```bash
sudo pacman -Syu
```

If pacman itself is broken by the missing library, use the static build:

```bash
curl -LO https://pkgbuild.com/~morganamilo/pacman-static/x86_64/bin/pacman-static
chmod +x pacman-static
sudo ./pacman-static -Syu
```

To check for updates safely in future without touching the sync DB, use `checkupdates` from pacman-contrib:

```bash
sudo pacman -S --needed pacman-contrib
checkupdates          # safe, does not sync the live database
checkupdates -d       # pre-download pending updates to the cache
```

Never use `pacman -Sy pkg`. Always `pacman -Syu` or `pacman -Syu pkg`.

**Verify.** `sudo pacman -Syu` reports nothing to do, and the previously broken binary runs. `sudo pacman -Qkk $(pacman -Qsq) | grep -v ' 0 altered files'` shows no missing library files.

Sources: <https://wiki.archlinux.org/title/System_maintenance> · <https://wiki.archlinux.org/title/Frequently_asked_questions> · <https://wiki.archlinux.org/title/Pacman>

---

## /boot or the ESP runs out of space mid-kernel-upgrade

`esp-full-during-kernel-upgrade` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Either pacman refuses to start:
```
error: Partition /boot too full: 51200 blocks needed, 3184 blocks free
error: not enough free disk space
```
or the transaction commits and the hook dies afterwards:
```
==> Creating gzip-compressed initcpio image: '/boot/initramfs-linux.img'
bsdtar: Write error
==> ERROR: Image generation FAILED: 'bsdtar' reported an error
error: command failed to execute correctly
```
`df -h /boot` shows a 260 MB–512 MB FAT32 partition at 100%. The kernel package is registered as installed but there is no usable vmlinuz/initramfs to boot.

**Cause.** The ESP is mounted at `/boot` and every installed kernel writes `vmlinuz-*` plus `initramfs-*.img` (plus a fallback image on older installs, plus microcode) into it. Omarchy 4 is worse: `limine-entry-tool` is configured with `ENABLE_UKI=yes`, so each kernel becomes a single 100–200 MB Unified Kernel Image at `/boot/EFI/Linux/omarchy_linux.efi`, and snapshots multiply that. FAT32 has no reserved blocks, pacman's `CheckSpace` estimate is only approximate, and the UKI/initramfs is written by a **PostTransaction** hook — i.e. after pacman has already committed. Arch recommends a 1 GiB ESP; 260 MiB is merely the FAT32 formatting minimum on a 4Kn drive, not a working size.

> **Audit corrected this record.** Cause and steps 1-4 are verified correct — impressively so. Omarchy really does ship /etc/limine-entry-tool.d/omarchy-uki.conf containing `ENABLE_UKI=yes` and omarchy-defaults.conf containing `CUSTOM_UKI_NAME="omarchy"`, which makes /boot/EFI/Linux/omarchy_linux.efi the exact real path (omarchy-refresh-limine references that literal filename). `limine-entry-tool --remove-uki "<kernel name>"` is a real documented subcommand. MKINITCPIO_FALLBACK accepts (yes|no|<kernel-name>) so `MKINITCPIO_FALLBACK=no` is valid, and /etc/limine-entry-tool.d/*.conf is the correct drop-in directory. The fallback claim is right: upstream mkinitcpio's mkinitcpio.d/hook.preset now ships PRESETS=('default') with #PRESETS=('default' 'fallback') commented, and the CHANGELOG says 'The default kernel preset files no longer includes the fallback image' — the record's preset edit matches the real template verbatim, including `#fallback_options="-S autodetect"`.

Step 5 is the problem and it is the kind that leaves a machine unbootable. Three defects: (a) it tells you to add a /efi line to fstab but never to remove the existing /boot line, so `mount -a` just remounts the ESP at /boot and nothing changes; (b) once the ESP is unmounted, /boot on the root filesystem is empty, and `mkinitcpio -P` writes only initramfs — it does NOT write vmlinuz or microcode, both of which come from packages, so the machine has no kernel to boot until those are reinstalled, and the bootloader is never reinstalled at the new path either; (c) on Omarchy the step does not work at all as a remedy — with ENABLE_UKI=yes the UKI is written to $ESP_PATH/EFI/Linux/ by definition, so moving ESP_PATH to /efi relocates the problem rather than solving it, and /etc/default/limine is a file Omarchy manages (it ships default/limine/default.conf with ESP_PATH="/boot"), so a hand edit there can be overwritten. Steps 1-4 stand as written.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not reboot while /boot is full or an initramfs/UKI is truncated — you will land in an emergency shell or the firmware will find no boot entry, and recovery needs a live USB. NEVER `rm -rf /boot/*`: that deletes the bootloader itself (limine/GRUB/systemd-boot), not just kernels, and on a dual-boot machine it deletes `/boot/EFI/Microsoft` and the `/boot/EFI/BOOT/BOOTX64.EFI` removable-media fallback too. Removing the fallback initramfs removes your one non-autodetect rescue image; keep an Arch ISO on a USB stick. Changing the ESP mount point rewrites fstab and bootloader paths — do it with a live USB within reach.

**Fix.**

Replace step 5 with the following; steps 1-4 are unchanged.

**5a. Omarchy 4 — do NOT try to move the ESP.** With `ENABLE_UKI=yes` the UKI is written to `$ESP_PATH/EFI/Linux/` by definition, so relocating the ESP relocates the problem. On Omarchy the space is consumed by *snapshot* boot entries, so cap those instead:

```bash
ls -lhS /boot/EFI/Linux/          # one UKI per kernel, plus one per snapshot entry
sudo limine-entry-tool --remove-uki "<kernel name>"   # e.g. linux-zen, for kernels you removed
```

Trim snapshots and the entries built from them:
```bash
sudo snapper -c root list
sudo snapper -c root delete <oldest ranges>
sudo limine-snapper-sync
```
To keep fewer snapshot boot entries permanently, add a drop-in (never edit `/etc/default/limine`, which Omarchy owns):
```bash
sudo tee /etc/limine-entry-tool.d/98-fewer-entries.conf >/dev/null <<'EOF'
MAX_SNAPSHOT_ENTRIES=3
EOF
sudo limine-update
```
and lower `NUMBER_LIMIT` in `/etc/snapper/configs/root` to match.

**5b. Plain Arch / EndeavourOS / CachyOS with a genuinely undersized ESP (<512 MiB): move the ESP to `/efi` and keep `/boot` on the root filesystem.** This only works with a bootloader that can read your root filesystem (GRUB, limine without UKI). Do it in this order, and have installation media on hand:

```bash
# 1. Note the ESP UUID BEFORE unmounting
findmnt -no SOURCE,UUID /boot
```

```bash
# 2. Edit fstab: DELETE or comment the existing /boot line, then add the /efi line
sudoedit /etc/fstab
```
```
# /boot line removed - /boot now lives on the root filesystem
UUID=XXXX-XXXX  /efi  vfat  fmask=0137,dmask=0027  0 2
```

```bash
# 3. Remount
sudo mkdir -p /efi
sudo umount /boot
sudo mount -a
findmnt /efi /boot      # /efi = vfat; /boot must NOT appear as a separate mount
```

```bash
# 4. /boot is now empty. Reinstall the kernel and microcode to repopulate vmlinuz + initramfs.
#    mkinitcpio alone is NOT enough - it does not write vmlinuz.
sudo pacman -S linux linux-firmware
sudo pacman -S amd-ucode      # or intel-ucode, whichever you have
ls -l /boot                   # must now show vmlinuz-linux and initramfs-linux.img
```

```bash
# 5. Reinstall the bootloader at the new ESP path, or it still looks in the old one.
# GRUB:
sudo grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=GRUB
sudo grub-mkconfig -o /boot/grub/grub.cfg
# systemd-boot:
sudo bootctl --esp-path=/efi install
```

Verify `/boot/vmlinuz-*` and `/boot/initramfs-*.img` exist and the bootloader config points at them **before** rebooting.

**Verify.** `df -h /boot` shows free space; `ls -l --time-style=full-iso /boot/vmlinuz-linux /boot/initramfs-linux.img` (or `/boot/EFI/Linux/omarchy_linux.efi`) shows a non-zero size with a timestamp from the last minute; `sudo pacman -S linux` completes with no `command failed to execute correctly`.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=278308> · <https://wiki.archlinux.org/title/EFI_system_partition> · <https://wiki.archlinux.org/title/Mkinitcpio> · <https://wiki.archlinux.org/title/Limine> · <https://gitlab.com/Zesko/limine-entry-tool/-/blob/master/README.md> · <https://github.com/basecamp/omarchy/discussions/3700>

---

## "error: command failed to execute correctly" from a pacman hook after the transaction already committed

`hook-failed-command-failed-to-execute-correctly` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** An upgrade appears to succeed, then prints a red error at the very end:
```
(6/9) Install DKMS modules
(7/9) Updating linux initcpios...
==> Building image from preset: /etc/mkinitcpio.d/linux.preset: 'default'
==> ERROR: '/usr/lib/modules/7.1.10-arch1-1' is not a valid kernel module directory
error: command failed to execute correctly
(8/9) Arming ConditionNeedsUpdate...
```
Users ask: "pacman said the packages installed but printed `error: command failed to execute correctly`. Did the update work? Is it safe to reboot?"

**Cause.** `error: command failed to execute correctly` is pacman's generic message for "an alpm hook exited non-zero". Per alpm-hooks(5), `AbortOnFail` applies **only to PreTransaction hooks** — and every kernel, initramfs, DKMS and bootloader hook is a *PostTransaction* hook. So by the time one of these fails, pacman has already unpacked the new packages onto disk and nothing is rolled back. The package database says the new kernel is installed while /boot may hold a stale, truncated or zero-length image. Some hooks (font caches, icon caches, desktop database, man-db) are purely cosmetic; the boot-critical ones are not, and pacman's output does not distinguish them.

> ⚠️ **Risk.** A failed mkinitcpio or UKI hook can leave a zero-length or truncated initramfs while the package database happily reports the new kernel as installed. Rebooting then drops you at `ERROR: device 'UUID=...' not found. Skipping fs check` and an initramfs emergency shell, and recovery requires a live USB. Never reboot on an unresolved mkinitcpio, DKMS or bootloader hook failure. Have an Arch ISO on a USB stick before you start poking at this.

**Fix.**

**1. Identify which hook failed.** The `(n/m) <Description>` line immediately above the error names it.

```bash
sudo tail -n 200 /var/log/pacman.log
ls /usr/share/libalpm/hooks/ /etc/pacman.d/hooks/ 2>/dev/null
```

**2. Classify it.** Cosmetic — reboot is safe, fix at leisure:
`fontconfig`, `gtk-update-icon-cache`, `update-desktop-database`, `texinfo-install`, `man-db`, `dbus-reload`, `glib-compile-schemas`, `30-systemd-update.hook`.

Boot-critical — **do not reboot until it succeeds**:

| Hook file | Package |
|---|---|
| `70-dkms-install.hook`, `70-dkms-upgrade.hook`, `71-dkms-remove.hook` | `dkms` |
| `60-mkinitcpio-remove.hook`, `90-mkinitcpio-install.hook` | `mkinitcpio` |
| limine / GRUB / systemd-boot entry hooks | bootloader integration |

**3. Re-run the critical hook by hand — this time the real error is on your screen, not buried in scrollback:**

```bash
# DKMS
sudo dkms status
sudo dkms autoinstall

# initramfs — Arch / EndeavourOS / CachyOS / Manjaro
sudo mkinitcpio -P

# Omarchy 4 (limine + UKI) — these are the wrappers the hook actually calls
sudo limine-mkinitcpio
sudo limine-update
```

**4. Prove the files were really written** (a hook can "succeed" after writing a truncated image):

```bash
ls -l --time-style=full-iso /boot/vmlinuz-* /boot/initramfs-*.img 2>/dev/null
ls -l --time-style=full-iso /boot/EFI/Linux/          # Omarchy UKI lives here
pacman -Q linux; uname -r
```

**5. Sledgehammer that re-fires every kernel hook** — reinstalling the kernel package re-triggers the whole chain:

```bash
sudo pacman -S linux          # or linux-lts / linux-zen
```

On Omarchy the update guard blocks `-Syu` but not a plain `-S`. If it fires anyway:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -S linux
```

**Verify.** `sudo mkinitcpio -P` (or `sudo limine-mkinitcpio && sudo limine-update` on Omarchy) exits 0 with no `==> ERROR` lines; `ls -l /boot/initramfs-linux.img` (or `/boot/EFI/Linux/omarchy_linux.efi`) shows a multi-megabyte file with a timestamp from the last minute; a second `sudo pacman -S linux` runs clean end to end.

Sources: <https://man.archlinux.org/man/alpm-hooks.5> · <https://wiki.archlinux.org/title/Pacman> · <https://bbs.archlinux.org/viewtopic.php?id=291242> · <https://archlinux.org/packages/core/any/mkinitcpio/files/> · <https://archlinux.org/packages/extra/any/dkms/files/> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/discussions/3700>

---

## Recover a system left unbootable by an interrupted pacman upgrade

`interrupted-upgrade-unbootable-pacman-broken` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** Power was lost, the machine froze, or the terminal was killed in the middle of `pacman -Syu`. Now the system will not boot, or it boots but `pacman` itself is broken: `pacman: command not found`, or `pacman: error while loading shared libraries: libalpm.so.16`.

**Cause.** pacman was midway through replacing files. Half the transaction is on disk, the database is inconsistent, and if pacman's own libraries or binary were in flight, there is no working tool left to repair with. Symlinking /var/cache/pacman/pkg (which pacman recreates as a directory during self-upgrade) is a known way to trigger the `pacman: command not found` variant.

> **Audit corrected this record.** Mostly sound — pacman-static, the chroot, and replaying the interrupted transaction from the log (the cut -d ' ' -f4 does land on the package name given pacman's log format) are all correct. Two problems. First, the fallback `pacman --root=/mnt --cachedir=... -Syu` omits --dbpath: whether that operates on /mnt's database or the live ISO's depends on whether DBPath is commented out in the ISO's pacman.conf, and if it resolves to the ISO's database pacman will make decisions from the wrong package set. Always pass --dbpath explicitly. Second, it says to rebuild 'initramfs and bootloader entries' but gives no bootloader command, which on an unbootable machine is the step that matters; and the root-run pacman-static should be signature-verified.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Manually extracting package tarballs over / with tar is the last-resort option in the wiki and the wiki itself warns it is extremely easy to make things worse — always use the `w` (interactive) flag and extract dependencies in order. Never symlink /var/cache/pacman/pkg; use the `CacheDir` option in pacman.conf or a bind mount instead. Back up /var/lib/pacman before any repair attempt.

**Fix.**

**If the system still boots:** pacman-static is statically linked and works with a broken library set. Verify it before running it as root:

```bash
curl -LO https://pkgbuild.com/~morganamilo/pacman-static/x86_64/bin/pacman-static
curl -LO https://pkgbuild.com/~morganamilo/pacman-static/x86_64/bin/pacman-static.sig
gpg --verify pacman-static.sig pacman-static
chmod +x pacman-static
sudo ./pacman-static -Syu pacman
sudo pacman -Syu
```

**If it does not boot:** boot the Arch install ISO, mount and chroot (arch-chroot, not --root):

```bash
lsblk -f
sudo mount /dev/nvme0n1p2 /mnt
sudo mount /dev/nvme0n1p1 /mnt/boot     # your ESP
sudo arch-chroot /mnt
```

Inside the chroot, replay the exact package set from the interrupted transaction so the right hooks and scriptlets run. Find the timestamp of the failed run and substitute it:

```bash
tail -50 /var/log/pacman.log
pacman -Syu $(grep "\[2026-08-20T09.*\] \[ALPM\] upgraded" /var/log/pacman.log | cut -d ' ' -f4 | tr '\n' ' ')
```

Then rebuild the initramfs **and** the bootloader before rebooting — use the one your system actually has:

```bash
mkinitcpio -P
grub-mkconfig -o /boot/grub/grub.cfg     # GRUB
# systemd-boot:  bootctl update
# Omarchy/limine: limine-update
exit
sudo umount -R /mnt
reboot
```

Only if pacman cannot run inside the chroot at all, drive it from outside — and pass **both** --root and --dbpath, otherwise pacman may operate against the live ISO's database instead of the installed system's:

```bash
sudo pacman --root=/mnt --dbpath=/mnt/var/lib/pacman \
            --cachedir=/mnt/var/cache/pacman/pkg -Syu
```

Check for zero-length (truncated) libraries left behind and reinstall whatever owns them:

```bash
find /mnt/usr/lib -size 0
```

**Verify.** The system boots to a login/greeter, `pacman -Syu` reports nothing to do, and `sudo pacman -Qkk $(pacman -Qsq) | grep -v ' 0 altered files'` produces no library-related output.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/Pacman/Tips_and_tricks> · <https://man.archlinux.org/man/pacman.8>

---

## Rebuild a corrupted local pacman database

`local-package-database-corrupted` · severity: **critical** · frequency: **rare** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `pacman -Q` prints nothing at all, or `pacman -Syu` claims the system is up to date on a machine that clearly is not, or `pacman -S somepkg` lists dependencies as "already satisfied" and refuses to install anything. May also show `error: could not open file /var/lib/pacman/local/<pkg>/desc: No such file or directory`.

**Cause.** /var/lib/pacman/local — pacman's record of what is installed — has been deleted, truncated, or corrupted (a full disk mid-transaction, a bad `rm`, a filesystem error, or restoring / from an incomplete backup). The files on disk are fine; pacman just no longer knows about them.

> ⚠️ **Risk.** This procedure uses `--dbonly --overwrite '*' --nodeps`, the most dangerous flag combination pacman has. Run it ONLY for database reconstruction, exactly as written. Get it wrong and you will need a full reinstall. Back up /var/lib/pacman and /var/log/pacman.log before starting. If /var/log/pacman.log is also gone, this method cannot be used.

**Fix.**

You need /var/log/pacman.log to be intact. Check first:

```bash
ls -l /var/log/pacman.log
```

Install pacman-contrib for `paclog-pkglist`, then rebuild the list of what should be installed:

```bash
sudo pacman -S --needed pacman-contrib expac
cat > /tmp/pacrecover <<'EOF'
#!/bin/bash -e
. /etc/makepkg.conf
PKGCACHE=$( (grep -m 1 '^CacheDir' /etc/pacman.conf || echo 'CacheDir = /var/cache/pacman/pkg') | sed 's/CacheDir = //')
pkgdirs=("$@" "$PKGDEST" "$PKGCACHE")
while read -r -a parampart; do
  for pkgdir in "${pkgdirs[@]}"; do
    for i in "$pkgdir"/"${parampart[0]}"-"${parampart[1]}"-*.pkg.tar.{xz,zst}; do
      [ -f "${i}" ] && { echo "${i}" ; continue 3; }
    done
  done || echo "${parampart[0]}" 1>&2
done
EOF
chmod +x /tmp/pacrecover
cd /tmp
paclog-pkglist /var/log/pacman.log | ./pacrecover >files.list 2>pkglist.orig
{ cat pkglist.orig; pacman -Slq; } | sort | uniq -d > pkglist
comm -23 <({ echo base; expac -l '\n' '%E' base; } | sort) pkglist.orig >> pkglist
```

Then reconstruct the database only (no files are touched):

```bash
recovery-pacman() { sudo pacman "$@" --log /dev/null --noscriptlet --dbonly --overwrite '*' --nodeps --needed; }
sudo pacman -Sy
recovery-pacman -U $(< /tmp/files.list)
recovery-pacman -S $(< /tmp/pkglist)
sudo pacman -D --asdeps $(pacman -Qq)
sudo pacman -D --asexplicit $(pacman -Qtq)
sudo pacman -Su
```

If you get `failed to initialise alpm library`, run `sudo pacman-db-upgrade` then `sudo pacman -Sy` and retry.

**Prevention** — back the database up regularly:
```bash
sudo tar -cjf ~/pacman_database.tar.bz2 /var/lib/pacman/local
```

**Verify.** `pacman -Q | wc -l` returns a plausible package count, `pacman -Qtdq` lists only genuine orphans, and `sudo pacman -Syu` behaves normally. `pacman -Qk` reports few or no missing files.

Sources: <https://wiki.archlinux.org/title/Pacman/Restore_local_database> · <https://wiki.archlinux.org/title/Pacman/Tips_and_tricks> · <https://man.archlinux.org/man/pacman.8>

---

## Rebuild AUR packages after a soname bump blocks the upgrade

`aur-package-needs-rebuild-after-soname-bump` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `sudo pacman -Syu` or `yay -Syu` aborts with something like:
```
error: failed to prepare transaction (could not satisfy dependencies)
:: unable to satisfy dependency 'libfoo.so=5-64' required by my-aur-package
```
or an AUR-installed program stops launching after a system upgrade with a `cannot open shared object file` error.

**Cause.** Repo packages get mass-rebuilt against new library sonames by Arch's build infrastructure. Locally built AUR packages do not — you are responsible for rebuilding them. The versioned `.so` dependency recorded in your local AUR package no longer exists.

> **Audit corrected this record.** Diagnosis is right and pacman -Qmq / the deleted-package comm check against aur.archlinux.org/packages.gz are correct. But the headline command is the wrong shape: `yay -S --rebuildall $(pacman -Qmq)` is a plain -S with no -u, so it does not advance the blocked upgrade — and rebuilding an AUR package before the repo upgrade lands means rebuilding against the *old* libraries, which is the exact state that broke. The rebuild has to happen in the same transaction as the upgrade (or after it).
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not solve this by adding the AUR package to `IgnorePkg` — that just freezes you into a permanent partial-upgrade state.

**Fix.**

Identify your foreign (AUR / locally built) packages:

```bash
pacman -Qmq                      # list all foreign packages
```

Upgrade the system and rebuild every AUR package in one transaction — this is what unblocks the dependency error:

```bash
yay -Syu --rebuildall            # or: paru -Syu --rebuild
```

Just the offending package (after the repo upgrade has gone through):

```bash
yay -S --rebuild my-aur-package
```

Without a helper — as a normal user, never root (makepkg refuses to run as root):

```bash
sudo pacman -Syu                 # complete the repo upgrade first if it is not blocked
cd /tmp && git clone https://aur.archlinux.org/my-aur-package.git
cd my-aur-package && makepkg -si
```

If an AUR package blocks the whole upgrade and you do not need it:

```bash
sudo pacman -Rns my-aur-package
sudo pacman -Syu
yay -S my-aur-package
```

Also check whether the package still exists upstream — deleted ones will never build again:

```bash
comm -23 <(pacman -Qqm | sort) <(curl -s https://aur.archlinux.org/packages.gz | gzip -cd | sort)
```

**Verify.** `sudo pacman -Syu` completes, and `pacman -Qmq` packages all launch. `yay -Qua` shows no pending AUR updates.

Sources: <https://wiki.archlinux.org/title/System_maintenance> · <https://wiki.archlinux.org/title/Frequently_asked_questions> · <https://wiki.archlinux.org/title/Arch_User_Repository>

---

## Resolve a 'conflicting files, exists in filesystem' upgrade abort

`conflicting-files-exists-in-filesystem` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** An upgrade aborts with:
```
error: failed to commit transaction (conflicting files)
some-package: /usr/lib/something.so exists in filesystem
Errors occurred, no packages were upgraded.
```

**Cause.** pacman never overwrites a file it does not own. The file was either put there by `make install` / a manually extracted tarball / a curl-installed tool, or the package's own file list at /var/lib/pacman/local/<pkg>-<ver>/files is corrupt or empty.

> ⚠️ **Risk.** `pacman --overwrite '*'` (or `--overwrite '/*'`) is the classic way to destroy an Arch install — it can clobber the initramfs and kernel files and leave the machine with "Unable to find root device" at boot. Always scope the glob to the exact path in the error.

**Fix.**

Find out who owns the offending file before touching anything:

```bash
pacman -Qo /usr/lib/something.so
```

**Case A — "No package owns" (a stray file you or a script installed):** rename it out of the way and re-run the upgrade.

```bash
sudo mv /usr/lib/something.so /usr/lib/something.so.bak
sudo pacman -Syu
# once the upgrade succeeds and things work:
sudo rm /usr/lib/something.so.bak
```

**Case B — the file is owned by the very package being upgraded** (corrupt local file list). Only then use a narrowly scoped overwrite:

```bash
sudo pacman -S --overwrite '/usr/lib/something.so' some-package
```

**Case C — a *different* installed package owns it.** That is a packaging bug; report it and do not force. Use `--overwrite` never with a bare `*`.

**Verify.** `sudo pacman -Syu` completes with no "conflicting files" errors, and `pacman -Qkk some-package` reports 0 missing / 0 altered files.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/System_maintenance> · <https://man.archlinux.org/man/pacman.8>

---

## Fix 'signature is unknown trust' from an out-of-date keyring

`signature-unknown-trust-keyring-out-of-date` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Every package in an update fails verification:
```
error: tzdata: signature from "Andreas Radke <andyrtr@archlinux.org>" is unknown trust
:: File /var/cache/pacman/pkg/tzdata-2025c-1-x86_64.pkg.tar.zst is corrupted (invalid or corrupted package (PGP signature)).
Do you want to delete it? [Y/n]
error: failed to commit transaction (invalid or corrupted package (PGP signature))
```
Typically on a machine that has not been updated for weeks or months, or on a fresh install from an older ISO.

**Cause.** The local pacman keyring (/etc/pacman.d/gnupg) predates the packager keys that signed the new packages, or a trusted key expired. archlinux-keyring is itself a package, so a long-stale system cannot verify the very keyring update it needs.

> ⚠️ **Risk.** Do NOT "fix" this by setting `SigLevel = Never` or `TrustAll` in /etc/pacman.conf — that disables signature verification system-wide and lets a hostile or corrupted mirror install anything. Deleting /etc/pacman.d/gnupg also destroys any locally signed third-party repo keys (Chaotic-AUR, CachyOS, omarchy-keyring); you will have to re-import and re-lsign them.

**Fix.**

Step 1 — sync the DB and update ONLY the keyring, then upgrade (this exact form is not a partial upgrade):

```bash
sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su
```

Step 2 — if that still fails, clear the half-downloaded/unverifiable cache and retry:

```bash
sudo rm -f /var/cache/pacman/pkg/*.part
sudo pacman -Sc
sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su
```

Step 3 — last resort, rebuild the keyring from scratch:

```bash
sudo rm -rf /etc/pacman.d/gnupg
sudo pacman-key --init
sudo pacman-key --populate archlinux
sudo pacman -Sy archlinux-keyring
sudo pacman -Su
```

On **Omarchy** there is a second keyring (omarchy-keyring). Use the shipped helper, which also lsigns Omarchy's key:

```bash
omarchy-update-keyring
# equivalent to, if the helper is missing:
sudo pacman-key --recv-keys 40DFB630FF42BCFFB047046CF0134EE680CAC571 --keyserver keys.openpgp.org
sudo pacman-key --lsign-key 40DFB630FF42BCFFB047046CF0134EE680CAC571
sudo pacman -Sy --noconfirm archlinux-keyring
```

Prevention: keep `archlinux-keyring-wkd-sync.timer` enabled — it pulls refreshed signatures weekly and prevents most "marginal trust" breakage.

```bash
systemctl enable --now archlinux-keyring-wkd-sync.timer
```

**Verify.** `sudo pacman -Syu` downloads and installs without any "unknown trust" or "invalid or corrupted package (PGP signature)" lines. `sudo pacman-key --list-keys | head` shows a populated keyring.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://wiki.archlinux.org/title/Pacman> · <https://github.com/basecamp/omarchy/issues/4197> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update-keyring>

---

## Full filesystem during an upgrade: download-phase write errors vs commit-phase CheckSpace abort

`filesystem-full-during-pacman-transaction` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Two distinct failures depending on which phase you are in.

Download phase (no space to write the .zst files):
```
error: failed retrieving file 'chromium-...-x86_64.pkg.tar.zst' from mirror : Failed writing received data to disk/application
warning: failed to retrieve some files
error: failed to commit transaction (failed to retrieve some files)
```
Commit phase (`CheckSpace` catching it before extraction):
```
error: Partition /var too full: 1450000 blocks needed, 12000 blocks free
error: not enough free disk space
```
On Omarchy: `You need at least 10 GiB free to safely update Omarchy.`
Worst case `df -h /` shows 100% and even `sudo pacman -Sc` fails.

**Cause.** pacman needs room twice: once for the downloaded `.zst` packages in `/var/cache/pacman/pkg`, and again for the extracted files at commit time. `CheckSpace` (enabled by default in Arch's and Omarchy's `pacman.conf`) catches the second case and aborts cleanly before touching anything; the first case dies mid-download and leaves `.part` files behind, wasting more space. On btrfs — the default on Omarchy and CachyOS — `df` can report free space while the metadata chunk is exhausted, and every snapper snapshot pins the old version of every file an update replaced, so a few updates with `NUMBER_LIMIT=5` can consume the root subvolume.

> ⚠️ **Risk.** `pacman -Scc` empties the cache including the versions currently installed — no offline reinstall and no downgrade path afterwards. `journalctl --vacuum-size=0` destroys every boot log, including the ones needed to diagnose why the disk filled. Deleting snapper snapshots is irreversible and removes your rollback points — delete the oldest first and never the snapshot matching your last known-good boot, and remember that on Omarchy those snapshots are also the Limine boot-menu rollback entries. `btrfs balance` on a nearly-full filesystem can itself fail with ENOSPC and must never be interrupted; free something else first and let it finish. Never delete anything under `/var/lib/pacman` — that is the package database, and losing it means pacman no longer knows what is installed.

**Fix.**

**Reclaim in this order — least destructive first.** Start by measuring:

```bash
df -h / /var /boot
sudo du -xhd1 /var | sort -h | tail
sudo btrfs filesystem usage /        # btrfs: look at Metadata and Unallocated
```

**1. Journal — biggest instant win, always safe:**
```bash
journalctl --disk-usage
sudo journalctl --vacuum-size=200M
```

**2. Package cache — keep 2 versions so you can still downgrade:**
```bash
sudo pacman -S --needed pacman-contrib
sudo paccache -rk2
sudo paccache -ruk0            # drop everything for packages you no longer have
```

**3. Interrupted-download leftovers:**
```bash
sudo find /var/cache/pacman/pkg -name '*.part' -delete
```

**4. Build and user caches:**
```bash
yay -Sc
rm -rf ~/.cache/yay/* ~/.cache/paru/clone/* ~/.cache/thumbnails ~/.cache/mesa_shader_cache*
```

**5. Btrfs snapshots — this is what actually frees a full Omarchy root:**
```bash
sudo snapper -c root list
sudo snapper -c root delete 12-18          # oldest ranges first
sudo btrfs balance start -dusage=50 /
sudo btrfs filesystem usage /
```

**6. Old kernels / UKIs on a full `/boot`:** see the ESP-full record.

**Escape hatch when nothing can be freed** — download to another disk for this one transaction:
```bash
sudo mkdir -p /run/media/$USER/BIGDISK/pkgcache
sudo pacman -Syu --cachedir /run/media/$USER/BIGDISK/pkgcache
```

**Then retry:**
```bash
sudo pacman -Syu
# Omarchy:
omarchy update
```

**Verify.** `df -h /` shows more than 10 GiB free (Omarchy's own hard threshold in `omarchy-update-requires-free-space`); `sudo btrfs filesystem usage /` shows non-zero `Device unallocated`; `sudo pacman -Syu` or `omarchy update` runs to completion with no `too full` or `Failed writing received data` errors.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://man.archlinux.org/man/pacman.conf.5> · <https://wiki.archlinux.org/title/System_maintenance> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-requires-free-space> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf>

---

## IgnorePkg / IgnoreGroup / HoldPkg holding packages back and the partial upgrade that follows

`ignorepkg-holdpkg-blocking-upgrade` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
warning: linux: ignoring package upgrade (7.1.9.arch1-1 => 7.1.10.arch1-1)
warning: nvidia-dkms: ignoring package upgrade (580.95.05-1 => 580.105.08-1)
:: The following package cannot be upgraded due to unresolvable dependencies:
      nvidia-utils
:: Do you want to skip the above package for this upgrade? [y/N]
```
or, when something tries to replace a held package:
```
:: pacman is designated as a HoldPkg. Remove anyway? [y/N]
error: failed to prepare transaction (user aborted the operation)
```
Weeks later, on a system that reports itself fully updated: `libfoo.so.6: cannot open shared object file: No such file or directory`.

**Cause.** A package listed in `IgnorePkg`/`IgnoreGroup` in `/etc/pacman.conf` (or passed via `--ignore`) is skipped by `-Syu`, but pacman upgrades everything *around* it. That is a partial upgrade, which Arch does not support: the held package is now linked against library sonames that no longer exist. `HoldPkg` is a different mechanism — it only makes pacman ask for confirmation before **removing** those packages. Omarchy ships `HoldPkg = pacman glibc` in `/etc/pacman.conf` as a safety net; it never blocks an upgrade.

> ⚠️ **Risk.** Lifting a kernel or GPU hold and upgrading can pull in the exact regression you were avoiding — a kernel that breaks a DKMS module, an NVIDIA driver that breaks your display. Before removing such a hold, make sure `linux-lts` is installed and selectable in the boot menu and that the old packages are still in `/var/cache/pacman/pkg` so you can roll back. Never leave `IgnorePkg = glibc` or `IgnorePkg = pacman` in place: that guarantees a partial upgrade you cannot recover from with pacman itself. If a partial upgrade has already broken things, never "fix" it by symlinking `libfoo.so.5` to `libfoo.so.6` — soname bumps mean the ABI is incompatible, and you will get silent memory corruption instead of a clean error.

**Fix.**

**1. Find out what is actually held:**

```bash
grep -nE '^\s*(IgnorePkg|IgnoreGroup|HoldPkg)' /etc/pacman.conf
grep -rnE '^\s*(IgnorePkg|IgnoreGroup)' /etc/pacman.d/ 2>/dev/null
sudo grep -E 'ignoring package upgrade' /var/log/pacman.log | tail -20
```

**2. Almost always the right move — remove the holds and take the whole upgrade:**

```bash
sudoedit /etc/pacman.conf          # delete or comment the IgnorePkg/IgnoreGroup lines
sudo pacman -Syu
# Omarchy:
omarchy update
```

**3. If you are holding a package for a real reason (a driver regression), pin the whole version-locked set, not one package, and treat it as temporary:**

```
# /etc/pacman.conf  [options]
IgnorePkg = linux linux-headers nvidia-dkms nvidia-utils lib32-nvidia-utils
```

**4. To skip for exactly one transaction instead of permanently:**

```bash
sudo pacman -Syu --ignore linux,linux-headers
```

**5. If you already created a partial upgrade and things are broken, complete it — do not symlink libraries or reinstall pieces:**

```bash
sudo pacman -Syu
sudo pacman -S $(pacman -Qqn)      # last resort: reinstall every repo package
yay -S --rebuildall $(pacman -Qqm | tr '\n' ' ')   # rebuild AUR pkgs after soname bumps
```

**6. HoldPkg prompt:** answer `y` only inside a `-S`/`-Syu` transaction that installs the replacement in the same step. Never `pacman -Rdd glibc`.

**Omarchy note:** `omarchy update` runs pacman with `--noconfirm`, so a "skip the above package" or HoldPkg prompt is auto-answered **No** and the upgrade quietly does less than you think. Always check afterwards:
```bash
sudo grep -E 'ignoring package upgrade|HoldPkg' /var/log/pacman.log | tail
pacman -Qu                          # anything still pending?
```

**Verify.** `sudo pacman -Syu` reports "there is nothing to do" with no `ignoring package upgrade` warnings; `grep -nE '^\s*(IgnorePkg|IgnoreGroup)' /etc/pacman.conf` returns nothing uncommented; `pacman -Qu` prints nothing.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://man.archlinux.org/man/pacman.conf.5> · <https://wiki.archlinux.org/title/System_maintenance> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf>

---

## Fix the linux-firmware-nvidia file conflict during an upgrade

`linux-firmware-nvidia-exists-in-filesystem` · severity: **high** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** `sudo pacman -Syu` fails on the linux-firmware update with:
```
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad103 exists in filesystem
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad104 exists in filesystem
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad106 exists in filesystem
linux-firmware-nvidia: /usr/lib/firmware/nvidia/ad107 exists in filesystem
error: failed to commit transaction (conflicting files)
```
Hits anyone who had not upgraded since June 2025.

**Cause.** linux-firmware was split into per-vendor subpackages (linux-firmware-nvidia etc.) in 20250613.12fe085f-5. Upgrading from 20250508.788aadc8-2 or earlier makes the new subpackage collide with directories still owned by the monolithic package. Announced as a required manual intervention on archlinux.org.

> ⚠️ **Risk.** `pacman -Rdd` removes the package with no dependency checks — between the two commands you have NO firmware installed. If you reboot or lose power in that window the machine may come up with no Wi-Fi, no GPU acceleration, or fail to boot. Run both commands back to back.

**Fix.**

Run exactly this, as documented in the Arch news item:

```bash
sudo pacman -Rdd linux-firmware
sudo pacman -Syu linux-firmware
```

Do not reboot between the two commands. After it completes, regenerate the initramfs if anything looks off:

```bash
sudo mkinitcpio -P
```

**Verify.** `pacman -Q | grep linux-firmware` lists the new split packages, and `ls /usr/lib/firmware/nvidia/` is populated. Reboot and confirm the GPU/Wi-Fi still initialise.

Sources: <https://archlinux.org/news/linux-firmware-2025061312fe085f-5-upgrade-requires-manual-intervention/> · <https://archlinux.org/news/> · <https://wiki.archlinux.org/title/Pacman>

---

## Work around an Omarchy mirror outage returning TLS errors or 404s

`omarchy-mirror-outage-tls-404-sig` · severity: **high** · frequency: **common** · applies to: `arch`, `desktop`, `laptop`, `omarchy`

**Symptom.** On Omarchy only, updates fail against Omarchy's own servers:
```
error: failed retrieving file 'chromium-143.0.7499.192-1-x86_64.pkg.tar.zst' from stable-mirror.omarchy.org : TLS connect error: error:0A000126:SSL routines::unexpected eof while reading
```
or
```
error: failed retrieving file 'sshfs-3.7.3-3-x86_64.pkg.tar.zst.sig' from stable-mirror.omarchy.org : Exceeded the maximum allowed file size (16384) with 16384 bytes
```
or `error: failed retrieving file 'visual-studio-code-bin-...pkg.tar.zst' from pkgs.omarchy.org : The requested URL returned error: 404`.

**Cause.** Omarchy ships a single-server mirrorlist (`Server = https://stable-mirror.omarchy.org/$repo/os/$arch`) plus its own `[omarchy]` repo at `https://pkgs.omarchy.org/stable/$arch`. There is no mirror redundancy, so any CDN/TLS glitch, stale sync, or missing artefact on Omarchy's side stops all updates for everyone.

> **Audit corrected this record.** The cause is verified exactly: default/pacman/mirrorlist-stable in master contains the single line `Server = https://stable-mirror.omarchy.org/$repo/os/$arch`, and pacman-stable.conf carries `[omarchy] / SigLevel = Optional TrustAll / Server = https://pkgs.omarchy.org/stable/$arch`. What is missing is the consequence: Omarchy's stable channel is a pinned snapshot, so repointing core/extra/multilib at rolling Arch mirrors pulls packages *newer* than the snapshot the [omarchy] repo was built against, and the restore step (`omarchy-refresh-pacman stable`, which really does run `pacman -Syyuu --noconfirm`) then has to downgrade them all again — a messy state to land in for what is often a transient CDN error. The fix also needs -Syy after a mirror change, and -uu should not be used on the way out.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Running Omarchy packages against pure Arch mirrors mixes epochs: `omarchy-refresh-pacman` finishes with `pacman -Syyuu`, which will force-DOWNGRADE anything newer than Omarchy's mirror offers. Snapshot first (`omarchy-snapshot create`) if you have snapper/limine set up. Disabling the `[omarchy]` repo while installed omarchy-* packages remain will also make them show as orphaned/foreign until you re-enable it.

**Fix.**

A TLS 'unexpected eof' or a one-off 404 is usually transient — retry once before changing any config:

```bash
sudo pacman -Syu
```

Only if the outage persists, temporarily point core/extra/multilib at official Arch mirrors. **Understand the trade-off first:** Omarchy's stable channel is a pinned snapshot; rolling Arch mirrors are ahead of it, so this pulls packages newer than the ones the `[omarchy]` repo was built against, and restoring will have to downgrade them. Treat it as a short-lived workaround.

```bash
sudo cp /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.omarchy
sudo tee /etc/pacman.d/mirrorlist >/dev/null <<'EOF'
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch
EOF
sudo pacman -Syyu     # -Syy is required after a mirror change; keep a single -u
```

If it is specifically `pkgs.omarchy.org` (the `[omarchy]` repo) 404ing, leave the mirrorlist alone and comment that repo out in `/etc/pacman.conf` for the duration:

```ini
#[omarchy]
#SigLevel = Optional TrustAll
#Server = https://pkgs.omarchy.org/stable/$arch
```

When Omarchy's servers are healthy again, restore the shipped configuration:

```bash
omarchy-refresh-pacman stable
```

This copies `/etc/pacman.conf` and `/etc/pacman.d/mirrorlist` to `.bak` (overwriting any previous `.bak`), rewrites both from Omarchy defaults, then runs `pacman -Syyuu` — the `-uu` is what downgrades anything you pulled ahead of the snapshot, so expect a large transaction and read it before confirming.

**Verify.** `sudo pacman -Syu` completes with no retrieval errors; after `omarchy-refresh-pacman stable`, `grep Server /etc/pacman.d/mirrorlist` shows stable-mirror.omarchy.org again.

Sources: <https://github.com/basecamp/omarchy/issues/4384> · <https://github.com/basecamp/omarchy/issues/5083> · <https://github.com/basecamp/omarchy/issues/6191> · <https://raw.githubusercontent.com/basecamp/omarchy/master/default/pacman/pacman-stable.conf> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-refresh-pacman>

---

## Conflict and provider prompts during -Syu, and what happens when you answer wrong

`package-conflict-and-provider-prompts-during-upgrade` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** An upgrade stops on a question:
```
:: pipewire-jack and jack2 are in conflict (jack). Remove jack2? [y/N]
```
or asks you to pick:
```
:: There are 2 providers available for jack:
:: Repository extra
   1) jack2  2) pipewire-jack
Enter a number (default=1):
```
or aborts outright:
```
:: pipewire-jack-1:1.4.7-1 and jack2-1.9.22-1 are in conflict
error: unresolvable package conflicts detected
error: failed to prepare transaction (conflicting dependencies)
```
On Omarchy 4 you instead see: `A package conflict stopped this upgrade. Running it again so you can answer:` or `This upgrade needs an answer. Run omarchy update interactively to give it.`

**Cause.** Two packages `Provides` the same virtual name (`jack`, `pipewire-session-manager`, `libjack.so`) and pacman will not keep both. Answering **N**, or running under `--noconfirm` (which auto-answers N), aborts the entire transaction — so one retired package silently blocks every other upgrade behind it. Answering **y** on the wrong prompt makes pacman drop the conflicting package *and everything that depends on it*, which is the classic way to remove half a desktop with one keystroke. Omarchy hits this constantly because `omarchy-update-system-pkgs` runs `pacman -Syu --noconfirm`.

> ⚠️ **Risk.** Running `pacman -R jack2` (or worse, `-Rns` / `-Rdd`) *before* the replacement is installed cascades: it takes ffmpeg, mpv, fluidsynth and everything downstream, which on a desktop can strip your browser, media player and parts of the compositor's dependency tree. Always let the conflict be resolved inside a single `-S`/`-Syu` transaction so the replacement goes in as the old package comes out. `-Rdd` skips dependency checks entirely and leaves an unbootable or unusable system — never use it to "win" a conflict prompt.

**Fix.**

**Never answer blind. In a second terminal, find out what depends on the package being removed:**

```bash
sudo pacman -S --needed pacman-contrib
pactree -r jack2                    # what needs it
pacman -Qi jack2 | grep -i 'required by'
```

**The answers that hold in practice:**

- `pipewire-jack` vs `jack2` → answer **y** on any modern PipeWire desktop (Omarchy, Arch, EndeavourOS, CachyOS). `pipewire-jack` provides `jack libjack.so libjackserver.so libjacknet.so`, so ffmpeg/mpv/fluidsynth keep working. Keep `jack2` **only** if you deliberately run a real JACK server (Ardour with jackd, Bitwig).
- `wireplumber` vs `pipewire-media-session` → choose **wireplumber**. `pipewire-media-session` is deprecated and no longer recommended.
- A provider prompt offering an AUR `-git` variant of something in the repos → pick the repo one unless you installed the `-git` on purpose.

**Make the choice explicitly instead of answering a prompt, in one transaction:**

```bash
sudo pacman -Syu pipewire-jack      # pacman removes jack2 as part of the same upgrade
sudo pacman -Syu wireplumber
```

**Omarchy 4:** the `--noconfirm` upgrade answers No and stops. Omarchy detects `unresolvable package conflicts detected` and re-runs the upgrade interactively — but only if it has a real TTY. Run it from an actual terminal:

```bash
omarchy update
```
or take it yourself:
```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
```

**Read the removal list before pressing y.** If the `Packages (n) To remove:` block is longer than a line or two, answer N and investigate first.

**Verify.** `sudo pacman -Syu` completes with no conflict prompt remaining and reports "there is nothing to do" on a second run. For the audio case: `pacman -Q pipewire-jack` succeeds, `pactree -r jack2` errors with "package not found", `wpctl status` still lists your sinks and sources, and audio still plays.

Sources: <https://forum.endeavouros.com/t/pipewire-jack-and-jack2-are-in-conflict-jack/22882> · <https://wiki.archlinux.org/title/PipeWire> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-system-pkgs-when-conflicted> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-system-pkgs> · <https://wiki.archlinux.org/title/Pacman>

---

## Signature failures for chaotic-aur / CachyOS / Omarchy repos that archlinux-keyring cannot fix

`third-party-repo-keyring-untrusted` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
error: chaotic-aur: signature from "<maintainer>" is unknown trust
error: failed to synchronize all databases (invalid or corrupted database (PGP signature))
```
or on CachyOS:
```
error: cachyos-core-znver4: signature from "CachyOS <admin@cachyos.org>" is invalid
error: cachyos-extra-znver4: signature from "CachyOS <admin@cachyos.org>" is invalid
```
Updating `archlinux-keyring` and running `pacman-key --populate archlinux` change nothing, because the offending key is not an Arch key.

**Cause.** Every unofficial repository is signed by its own key, which lives in that project's own keyring package — `chaotic-keyring`, `cachyos-keyring`, `omarchy-keyring`, `archlinuxcn-keyring`, `alhp-keyring` — never in `archlinux-keyring`. Until that key is both **imported** and **locally signed**, pacman under the default `SigLevel = Required DatabaseOptional` refuses the repo. The same error also appears when a project rotates its key or lets a signing subkey expire (CachyOS's `882DCFE4…8DB35A47` had an encryption subkey expire and shipped a stale `cachyos-keyring` for over a year) and your installed keyring package predates the rotation.

> **Audit corrected this record.** The cause is correct and the key material is verified. Chaotic-AUR's key 3056513887B78AEB matches the upstream installer script (`sudo pacman-key --recv-key 3056513887B78AEB --keyserver hkp://keyserver.ubuntu.com:80` / `--lsign-key 3056513887B78AEB`). CachyOS fingerprint 882DCFE48E2051D48E2562ABF3B607488DB35A47 is confirmed as the DB signing key, along with the expired-subkey story behind the 'signature ... is invalid' variant. The Omarchy block is exactly right — bin/omarchy-update-keyring uses fingerprint 40DFB630FF42BCFFB047046CF0134EE680CAC571 with `--keyserver keys.openpgp.org`, then lsign, then installs omarchy-keyring, and `omarchy-update-keyring` is the correct command to run (it invokes sudo internally). The SigLevel claim is right too: Omarchy's default/pacman/pacman-stable.conf carries the global `SigLevel = Required DatabaseOptional`, and per pacman.conf(5) a repo section's own SigLevel overrides it. Verifying the fingerprint before lsign is the correct and often-omitted safety step.

Two commands are the wrong form and both create partial-upgrade exposure. `sudo pacman -Sy cachyos-keyring` refreshes the databases and then installs a single package against them, leaving every other installed package at a version older than the synced databases — the textbook partial upgrade. And the closing `sudo pacman -Syy` refreshes databases with no upgrade at all, which leaves the system parked in exactly that state until the user happens to run -Syu; -Syy is also the force-refresh form, needed only after a mirror change, so it re-downloads every database for no reason here. The keyring exception people cite (Omarchy's own script does `pacman -Sy`) only holds when a full `-Syu` follows immediately in the same script — which is not what a user copy-pasting these lines will do.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `SigLevel = Never` or `TrustAll` on a third-party repo disables signature checking for that repo completely — you are then trusting whatever any mirror serves you, with root install rights. Never set it globally and never as a permanent fix. Do not use `pacman-key --refresh-keys` as a shotgun: it is slow, frequently fails, and can pull in revoked or superseded key material. Do not `rm -rf /etc/pacman.d/gnupg` unless you are prepared to re-run `pacman-key --init && pacman-key --populate` and re-import every third-party key, including on a machine you may not be able to update afterwards.

**Fix.**

Everything is unchanged except the two commands below.

**CachyOS** (the expired/rotated admin key — the `is invalid` variant) — install the keyring as part of a full upgrade, not on its own:
```bash
sudo pacman-key --recv-keys 882DCFE48E2051D48E2562ABF3B607488DB35A47 --keyserver keyserver.ubuntu.com
pacman-key --finger 882DCFE48E2051D48E2562ABF3B607488DB35A47   # check against CachyOS's published fingerprint
sudo pacman-key --lsign-key 882DCFE48E2051D48E2562ABF3B607488DB35A47
sudo pacman -Syu cachyos-keyring
```

**Then refresh and upgrade in one step.** Do not stop at a bare `-Sy`/`-Syy`: refreshing databases without upgrading leaves the system in a partial-upgrade state.
```bash
sudo pacman -Syu
```
Only if pacman still reports a stale or corrupt database do you need the force-refresh form — and it must still carry the `u`:
```bash
sudo pacman -Syyu
```
On Omarchy, run `omarchy update` instead of either.

**Verify.** `sudo pacman -Syy` syncs every database with no signature error; `pacman-key --list-keys <KEYID>` shows the key present with a local signature; `pacman -Sl chaotic-aur | head` (or `pacman -Sl omarchy | head`) lists packages.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://wiki.archlinux.org/title/Unofficial_user_repositories> · <https://github.com/SharafatKarim/chaotic-AUR-installer/blob/main/install.bash> · <https://github.com/CachyOS/distribution/issues/443> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-keyring> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf>

---

## Fix yay or paru dying on a libalpm.so version mismatch

`yay-paru-libalpm-so-mismatch` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Right after a pacman upgrade, every AUR helper invocation dies:
```
yay: error while loading shared libraries: libalpm.so.15: cannot open shared object file: No such file or directory
```
(or `libalpm.so.14`, `libalpm.so.16` — the number moves). `paru` shows the same. On Omarchy the update script fails at the "Update AUR packages" step and the whole `omarchy-update` aborts.

**Cause.** yay and paru link against libalpm from the pacman package. When pacman bumps libalpm's soname, the prebuilt helper binary is instantly broken and cannot be used to rebuild itself — a deadlock. It is usually a lag between the pacman release and a tagged alpm.rs release the helpers can build against.

> ⚠️ **Risk.** A widely-copied workaround is `ln -s /usr/lib/libalpm.so.16 /usr/lib/libalpm.so.15`. That makes yay run against an ABI-incompatible library and can corrupt the pacman database when yay writes to it. If you must use it to bootstrap, remove both symlinks immediately after rebuilding yay: `sudo unlink /usr/lib/libalpm.so.15 && sudo unlink /usr/lib/libalpm.so.15.0.0`. On Omarchy, a hand-built yay from the AUR will later be replaced by Omarchy's own yay package on the next update.

**Fix.**

Rebuild yay from the AUR by hand with makepkg (no AUR helper required):

```bash
sudo pacman -Syu --needed git base-devel go
cd /tmp && rm -rf yay
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
```

Or sidestep compilation entirely with the prebuilt package:

```bash
cd /tmp && rm -rf yay-bin
git clone https://aur.archlinux.org/yay-bin.git
cd yay-bin
makepkg -si
```

For paru, substitute `https://aur.archlinux.org/paru.git` (or `paru-bin.git`).

On Omarchy, re-run the update afterwards:

```bash
omarchy-update
```

**Verify.** `yay --version` prints a version instead of the loader error, and `yay -Sua` runs.

Sources: <https://github.com/basecamp/omarchy/issues/3877> · <https://github.com/basecamp/omarchy/issues/3902> · <https://github.com/archlinux/alpm.rs/issues/59> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update-aur-pkgs>

---

## Roll the whole system back to how it was on a given date

`restore-whole-system-to-earlier-date-ala` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `omarchy`, `systemd-boot`

**Symptom.** "My system is broken after an update from a few weeks ago and I don't know which package did it — I want to go back to how it was on a specific date."

**Cause.** No single package is identifiable as the culprit, so individual downgrades are impractical. The Arch Linux Archive keeps daily snapshots of the whole repository set.

> ⚠️ **Risk.** This is the highest-risk operation in this list. Mass-downgrading glibc, systemd, the kernel and the bootloader can leave an unbootable system; the wiki explicitly warns it is unsafe to mix Archive and live mirrors, because a single download failure falls back to a current package and leaves you with mixed epochs. Downgrades do not undo config-file migrations, so /etc may be newer than the binaries. Take a filesystem snapshot or a full backup first, keep a live USB ready, and never leave the Archive mirror configured permanently.

**Fix.**

Point pacman at a dated snapshot in `/etc/pacman.conf`. Replace the `Include = /etc/pacman.d/mirrorlist` lines for core/extra/multilib, or set the date in the mirrorlist itself:

```bash
sudo cp /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.bak
sudo tee /etc/pacman.d/mirrorlist >/dev/null <<'EOF'
Server = https://archive.archlinux.org/repos/2026/07/01/$repo/os/$arch
EOF
sudo pacman -Syyuu
```
`-uu` is what permits the downgrades.

If signature errors appear during the rollback, update these two first:

```bash
sudo pacman -Sy archlinux-keyring ca-certificates
sudo pacman -Syyuu
```

To return to normal afterwards:

```bash
sudo cp /etc/pacman.d/mirrorlist.bak /etc/pacman.d/mirrorlist
sudo pacman -Syyu
```

**On Omarchy** prefer the built-in snapshot mechanism if snapper/limine is configured — it is far safer:
```bash
omarchy-snapshot restore     # runs limine-snapper-restore
```

**Verify.** `pacman -Qi linux | grep Version` (and other key packages) show versions from the target date; the system boots and the regression is gone.

Sources: <https://wiki.archlinux.org/title/Arch_Linux_Archive> · <https://wiki.archlinux.org/title/Downgrading_packages> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-snapshot>

---

## Import the key an AUR build needs when signature verification fails

`aur-pgp-signature-could-not-be-verified` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A `makepkg`/`yay`/`paru` build stops at the source verification stage:
```
==> Verifying source file signatures with gpg...
    foo-1.2.tar.xz ... FAILED (unknown public key ABCDEF0123456789)
==> ERROR: One or more PGP signatures could not be verified!
```

**Cause.** makepkg verifies upstream release signatures against YOUR user keyring (~/.gnupg), not pacman's keyring. The upstream developer's public key is simply not in it. This is unrelated to archlinux-keyring.

> ⚠️ **Risk.** `--skippgpcheck` disables the only check that the upstream tarball is genuinely from the developer. Importing a key ID you found in a random comment rather than in the PKGBUILD's validpgpkeys array defeats the purpose entirely.

**Fix.**

Read the PKGBUILD's `validpgpkeys` array to get the exact key ID, then import it:

```bash
grep validpgpkeys PKGBUILD
gpg --recv-keys ABCDEF0123456789
# if the default keyserver is unreachable:
gpg --keyserver hkps://keyserver.ubuntu.com --recv-keys ABCDEF0123456789
```

Some PKGBUILDs ship the key locally — import it from the repo instead:

```bash
gpg --import keys/pgp/ABCDEF0123456789.asc
```

Then rebuild:

```bash
makepkg -si          # or: yay -S foo
```

Only if you have independently verified the source and accept the risk, skip the check for one build:

```bash
makepkg -si --skippgpcheck
# yay equivalent:
yay -S foo --mflags --skippgpcheck
```

**Verify.** `gpg --list-keys ABCDEF0123456789` shows the key, and the build proceeds past "Verifying source file signatures".

Sources: <https://wiki.archlinux.org/title/Makepkg> · <https://wiki.archlinux.org/title/Arch_User_Repository>

---

## Fix 404s from a stale mirror during an upgrade

`failed-retrieving-file-404-stale-mirror` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
error: failed retrieving file 'foo-1.2-1-x86_64.pkg.tar.zst' from mirror.example.org : The requested URL returned error: 404
warning: failed to retrieve some files
error: failed to commit transaction (failed to retrieve some files)
```
or `error: target not found: foo` for a package you can clearly see on archlinux.org/packages.

**Cause.** Your sync database lists a package version the mirror no longer carries (mirror is behind, or it has already rotated to a newer version), the mirror is broken, or the repository containing the package (e.g. multilib) is not enabled in /etc/pacman.conf.

> ⚠️ **Risk.** After switching to a different mirror you may hold packages newer than the new mirror offers. The wiki's remedy is `sudo pacman -Syyuu` to force-downgrade back into sync — that downgrade can revert a kernel or glibc, so reboot afterwards and be prepared to regenerate the initramfs.

**Fix.**

First force a real database refresh against your current mirrors:

```bash
sudo pacman -Syyu
```

If that does not fix it, the mirror is the problem. Re-rank mirrors with reflector:

```bash
sudo pacman -S --needed reflector
sudo reflector --latest 20 --protocol https --sort rate --save /etc/pacman.d/mirrorlist
sudo pacman -Syyu
```

Or hand-write a known-good mirrorlist:

```bash
sudo cp /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.bak
sudo tee /etc/pacman.d/mirrorlist >/dev/null <<'EOF'
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch
EOF
sudo pacman -Syyu
```

If the package is 32-bit (lib32-*) or a Steam dependency, enable multilib in `/etc/pacman.conf`:

```ini
[multilib]
Include = /etc/pacman.d/mirrorlist
```
then `sudo pacman -Syu`.

**Verify.** `sudo pacman -Syu` downloads everything; `pacman -Ss foo` finds the package in the expected repo.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/Mirrors> · <https://wiki.archlinux.org/title/Reflector>

---

## "Running makepkg as root is not allowed" and the user/sudo setup AUR builds require

`makepkg-as-root-not-allowed` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
==> ERROR: Running makepkg as root is not allowed as it can cause permanent,
catastrophic damage to your system.
```
(makepkg exits with status 10.) With a helper:
```
Avoid running yay as root/sudo.
```
Usually hit when logged in as root on a fresh install with no ordinary user yet, inside a rescue chroot or container, or by habitually prefixing everything with `sudo`.

**Cause.** makepkg refuses to run with EUID 0 by design. A PKGBUILD is arbitrary shell executed at build time; as root it ignores every file permission and can write anywhere on the system. makepkg is built to run *unprivileged* and to escalate via sudo only for the specific `pacman` calls it makes (installing build dependencies, installing the finished package). So it needs a normal user with working sudo — the inverse of what people try.

> **Audit corrected this record.** The error text and cause are exact. pacman's scripts/makepkg.sh.in line 1122 is `if (( EUID == 0 ))` followed by the gettext string 'Running %s as root is not allowed as it can cause permanent,\ncatastrophic damage to your system.' and `exit $E_ROOT`, and libmakepkg/util/error.sh.in defines E_ROOT=10 — the record's exit status is right. Steps 1, 2, 3, 5 and 6 are all correct, and the Omarchy claim is verified: bin/omarchy-pkg-aur-install runs `yay -S --noconfirm` as the invoking user with only a sudo-keepalive, never `sudo yay`.

Step 4 is the defect. `runuser -u nobody -- makepkg` will abort before building on almost any real PKGBUILD, because makepkg checks dependencies and — running as an unprivileged user with no sudo rights — cannot install them, so it exits with 'Missing dependencies'. The record installs no build dependencies anywhere in that path. Second, nobody's home directory is `/`, which is not writable, so any PKGBUILD carrying `validpgpkeys` fails source verification when gpg cannot create a keyring. Third, the framing overstates provenance: I could not find the nobody technique documented on the ArchWiki Makepkg or Arch User Repository pages, so 'the Arch-sanctioned escape hatch' is not supportable — it is a container convention, and the ArchWiki's actual position (Makepkg, 'Running makepkg itself as root is disallowed') points at a normal build user.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not "solve" this by adding `%wheel ALL=(ALL) NOPASSWD: ALL` to sudoers just to quiet an AUR helper — that hands every PKGBUILD you build unattended full root. Only chown paths inside your own home; chowning system directories to fix build errors will break package ownership. Building as `nobody` in a shared `/tmp` directory means anyone on the box can tamper with the sources between download and build; use it only in a single-user container or chroot.

**Fix.**

Steps 1, 2, 3, 5 and 6 are unchanged. Replace step 4 with:

**4. Truly account-less environment (container, chroot).** The reliable pattern is a throwaway build user with passwordless sudo — this is what the official Arch container images do, and it is preferred over `nobody` because makepkg must be able to install build dependencies:

```bash
pacman -Sy --needed --noconfirm base-devel git sudo
useradd -m builder
echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder
chmod 0440 /etc/sudoers.d/builder

su - builder -c '
  git clone https://aur.archlinux.org/PKGNAME.git ~/PKGNAME &&
  cd ~/PKGNAME && makepkg -s --noconfirm
'
pacman -U /home/builder/PKGNAME/*.pkg.tar.zst

# clean up when the image is finished
rm -f /etc/sudoers.d/builder && userdel -r builder
```

If you genuinely cannot create a user, the `nobody` route works only if you install the build dependencies as root first and give nobody a writable HOME — otherwise makepkg aborts on missing dependencies, and gpg source verification fails because nobody's home is `/`:

```bash
# read the PKGBUILD's depends/makedepends and install them AS ROOT first
install -d -o nobody -g nobody /tmp/build /tmp/build/home
cd /tmp/build
curl -LO https://aur.archlinux.org/cgit/aur.git/snapshot/PKGNAME.tar.gz
tar xf PKGNAME.tar.gz
chown -R nobody:nobody PKGNAME
cat PKGNAME/PKGBUILD          # read depends= and makedepends=, then:
pacman -S --needed --noconfirm <those packages>

cd PKGNAME
runuser -u nobody -- env HOME=/tmp/build/home makepkg --nodeps --noconfirm
pacman -U ./*.pkg.tar.zst
```

`--nodeps` is required here: nobody has no sudo, so makepkg cannot install anything itself — which is exactly why you installed the dependencies as root above.

**Verify.** `makepkg -si` gets past source download into `==> Starting build()...` and finishes with `==> Finished making: PKGNAME`; `pacman -Qi PKGNAME` shows it installed; `ls -l` in the build directory shows files owned by your user, not root.

Sources: <https://wiki.archlinux.org/title/Makepkg> · <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://man.archlinux.org/man/makepkg.8> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-pkg-aur-install>

---

## Reclaim a disk filled by the pacman package cache

`pacman-cache-filling-disk` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `df -h` shows / or /var nearly full; `du -sh /var/cache/pacman/pkg` reports tens of gigabytes. Eventually pacman refuses to work:
```
error: Partition /var too full: 1234567 blocks needed, 1000 blocks free
error: failed to commit transaction (not enough free disk space)
```

**Cause.** pacman keeps every package it ever downloaded in /var/cache/pacman/pkg/ and never prunes it automatically. On a rolling release with frequent kernel/browser/electron updates this grows without bound. AUR helper build caches (~/.cache/yay, ~/.cache/paru) add to it.

> ⚠️ **Risk.** `pacman -Scc` empties the cache completely, including the currently installed versions. After that you cannot downgrade or reinstall anything offline — every recovery requires a working network and mirror. Prefer `paccache -r`.

**Fix.**

Keep the last 3 versions of each package (safe default, still allows downgrading):

```bash
sudo pacman -S --needed pacman-contrib
sudo paccache -r
```

More aggressive — keep 1 version, and drop all cached versions of packages you no longer have installed:

```bash
sudo paccache -rk1
sudo paccache -ruk0
```

Automate it weekly:

```bash
sudo systemctl enable --now paccache.timer
# tune retention:
echo "PACCACHE_ARGS='-k2'" | sudo tee /etc/conf.d/pacman-contrib
```

Clear AUR helper build caches too:

```bash
yay -Sc          # or: paru -Sc
rm -rf ~/.cache/yay/*
```

Check the result:
```bash
du -sh /var/cache/pacman/pkg ~/.cache/yay
```

**Verify.** `du -sh /var/cache/pacman/pkg` drops substantially and `df -h /` shows free space; `sudo pacman -Syu` no longer reports insufficient disk space.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/System_maintenance> · <https://man.archlinux.org/man/pacman.8>

---

## Clear a stale pacman lock after 'unable to lock database'

`pacman-unable-to-lock-database` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** pacman refuses to do anything: `error: failed to init transaction (unable to lock database)` followed by `error: could not lock database: File exists  if you're sure a package manager is not already running, you can remove /var/lib/pacman/db.lck`. Often happens after closing a terminal mid-update, after a crash, or when a GUI updater / omarchy-update is running in the background.

**Cause.** pacman creates /var/lib/pacman/db.lck before it alters the package database, so two instances cannot write at once. If pacman is killed or the machine loses power mid-transaction, the lock file is left behind and every later run refuses to start.

> ⚠️ **Risk.** Deleting db.lck while pacman really is running will let a second instance write the database at the same time and can corrupt /var/lib/pacman/local, leaving an unrecoverable package database. Always run `fuser` first.

**Fix.**

First confirm nothing is actually using the lock — this is the step people skip and it is why systems get corrupted:

```bash
sudo fuser /var/lib/pacman/db.lck
# also check for a running package manager
ps aux | grep -E '[p]acman|[y]ay|[p]aru'
```

If `fuser` prints nothing and no pacman/yay/paru process exists, delete the stale lock:

```bash
sudo rm /var/lib/pacman/db.lck
sudo pacman -Syu
```

If `fuser` DOES print a PID, wait for that process to finish (or on Omarchy, wait for `omarchy-update` to complete) instead of deleting the file.

**Verify.** `sudo pacman -Syu` starts resolving dependencies instead of erroring, and `ls /var/lib/pacman/db.lck` reports no such file when pacman is idle.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://man.archlinux.org/man/pacman.8>

---

## Find and merge the .pacnew files an upgrade left behind

`pacnew-files-left-unmerged` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Update output scrolls past lines like:
```
warning: /etc/pacman.conf installed as /etc/pacman.conf.pacnew
warning: /etc/ssh/sshd_config installed as /etc/ssh/sshd_config.pacnew
```
Weeks later something breaks for no obvious reason — sshd refuses to start, sudo behaves oddly, a service silently uses stale defaults.

**Cause.** When a package ships a new version of a config file you have modified, pacman refuses to overwrite it and drops the new version alongside as `.pacnew`. Nothing merges it for you. Over time your live config drifts behind upstream defaults and eventually contains directives the new binary no longer understands.

> **Audit corrected this record.** The problem and the find/grep commands are fine, but the pacdiff invocation is broken as written. `sudo DIFFPROG=nvim -E pacdiff` fails: sudo stops option parsing at the VAR=value assignment, so `-E` is taken as the command to execute ('sudo: -E: command not found'). Separately, pacdiff(8) documents the default DIFFPROG as `vim -d` (or `nvim -d` when EDITOR=nvim) — bare `nvim` opens two buffers rather than a diff — and modern pacdiff has a `--sudo` flag that is the intended way to run it unprivileged. The suggested `pacdiff-pacman-hook-git` AUR package could not be verified and should not be recommended blind.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Never blanket-`mv *.pacnew` over the live files. Overwriting /etc/passwd, /etc/shadow, /etc/group, /etc/fstab or /etc/sudoers with a .pacnew will lock you out of your account, out of sudo, or make the system unbootable. Always diff each file individually.

**Fix.**

Find every outstanding file:

```bash
sudo find /etc -name '*.pacnew' -o -name '*.pacsave'
```

Merge them interactively with pacdiff from pacman-contrib. pacdiff's default DIFFPROG is already `vim -d` (`nvim -d` when EDITOR=nvim), so run it as your normal user and let it elevate only where it needs to:

```bash
sudo pacman -S --needed pacman-contrib
pacdiff --sudo
```

With an explicit diff tool — note the `-d`, a bare `nvim` opens two buffers instead of a diff:

```bash
DIFFPROG='nvim -d' pacdiff --sudo
# or, if your pacdiff predates --sudo:
DIFFPROG=meld sudo -E pacdiff
```

Do NOT use `sudo DIFFPROG=nvim -E pacdiff` — sudo stops parsing options at the `VAR=value` assignment and then tries to run `-E` as the command.

pacdiff shows each pair and offers view / merge / keep-old / use-new / remove. To review history of everything that ever produced one:

```bash
grep -E '\.pacnew|\.pacsave' /var/log/pacman.log | tail -20
```

Make it a habit: run `pacdiff --sudo` after every upgrade.

**Verify.** `sudo find /etc -name '*.pacnew'` returns nothing, and affected services restart cleanly (`systemctl restart sshd && systemctl status sshd`).

Sources: <https://wiki.archlinux.org/title/Pacman/Pacnew_and_Pacsave> · <https://wiki.archlinux.org/title/System_maintenance>

---

## Fix AUR builds failing because base-devel is missing

`aur-build-fails-missing-base-devel` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** AUR builds fail immediately with things like `bash: makepkg: command not found`, `==> ERROR: Cannot find the fakeroot binary`, `==> ERROR: Cannot find the strip binary required for object file stripping`, or a compiler/`patch`/`autoconf` not found error — on a system that used to build AUR packages fine.

**Cause.** base-devel was converted from a package *group* to a *meta package* in February 2023. Users who installed the group before that have the old members but never receive newly added ones, so tools quietly go missing. Fresh minimal installs simply never had it.

**Fix.**

Install the meta package explicitly, exactly as the Arch news item instructs:

```bash
sudo pacman -Syu base-devel
```

Also ensure git is present for AUR clones:

```bash
sudo pacman -S --needed git base-devel
```

Verify the toolchain:

```bash
pacman -Qi base-devel >/dev/null && echo 'base-devel installed as a package'
which makepkg fakeroot gcc make patch
```

**Verify.** `pacman -Qi base-devel` returns package info (not "error: package 'base-devel' was not found"), and `makepkg -si` runs in any AUR clone.

Sources: <https://archlinux.org/news/switch-to-the-base-devel-meta-package-requires-manual-intervention/> · <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://archlinux.org/news/>

---

## An installed AUR package no longer exists upstream: "target not found" / "Could not find all required packages"

`aur-package-deleted-merged-or-renamed` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
$ yay -Syu
:: Searching AUR for updates...
 -> Could not find all required packages:
	spotify-adblock (Target)
```
or
```
$ sudo pacman -S my-package
error: target not found: my-package
```
`pacman -Qm` still lists it as installed, but https://aur.archlinux.org/packages/<name> returns 404 or redirects to a differently-named package. Every subsequent update run repeats the same complaint.

**Cause.** AUR packages get deleted (submission-rule violation, dead upstream), merged into another package base, renamed by the maintainer, or adopted into the official `extra` repository. Your locally-built copy stays installed forever, receives no updates, and every helper run flags it. Separately, `pacman -S` says `target not found` for anything that only ever existed in the AUR — pacman searches only configured repositories, never the AUR.

> ⚠️ **Risk.** `pacman -Rns` on a package other things depend on cascades — always run `pactree -r PKGNAME` first and read the removal list. Never edit `/var/lib/pacman/local` by hand to silence the helper; that corrupts the package database. A deleted AUR package was often deleted for a reason (unmaintained, licensing, malware report) — check the aur-requests mailing list archive before rebuilding it from an old git clone and running its PKGBUILD, which executes arbitrary code on your machine.

**Fix.**

**1. List every foreign (non-repo) package and check which ones are gone** — the ArchWiki one-liner:

```bash
pacman -Qqm
comm -23 <(pacman -Qqm | sort) <(curl -s https://aur.archlinux.org/packages.gz | gzip -cd | sort)
```
Anything printed no longer exists in the AUR.

**2. For one package, ask the AUR RPC directly** — an empty `results` array means it is gone:

```bash
curl -s 'https://aur.archlinux.org/rpc/v5/info?arg[]=PKGNAME' | head -c 400
```

**3. Work out where it went:**

```bash
# (a) adopted into the official repos
pacman -Ss '^PKGNAME$'
sudo pacman -S PKGNAME          # the repo version replaces your local build

# (b) renamed or merged — search by name, then by what it provides
curl -s 'https://aur.archlinux.org/rpc/v5/search/PARTIALNAME?by=name' | head -c 800
curl -s 'https://aur.archlinux.org/rpc/v5/search/PKGNAME?by=provides' | head -c 800
```

**4. Migrate — install the successor, then drop the stale one:**

```bash
sudo pacman -S --needed pacman-contrib
pactree -r OLD-PKGNAME          # check nothing else needs it FIRST
yay -S NEW-PKGNAME
sudo pacman -Rns OLD-PKGNAME
```

**5. If nothing replaced it and you still want it**, the git repo of a deleted AUR package usually survives — clone it and maintain it yourself:

```bash
git clone https://aur.archlinux.org/PKGNAME.git
cd PKGNAME && makepkg -si
```

**6. If you just want the noise to stop:**

```bash
sudo pacman -Rns PKGNAME
```

**Omarchy note:** `omarchy update` runs `omarchy-update-aur-pkgs`, which skips the AUR entirely when it is unreachable (`omarchy-pkg-aur-accessible`). A package that is *deleted* rather than merely unreachable will keep being reported on every single update until you migrate or remove it.

**Verify.** `comm -23 <(pacman -Qqm | sort) <(curl -s https://aur.archlinux.org/packages.gz | gzip -cd | sort)` prints nothing (or only packages you deliberately build locally), and `yay -Syu` completes without `Could not find all required packages`.

Sources: <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://aur.archlinux.org/rpc/v5/info?arg[]=yay> · <https://aur.archlinux.org/packages.gz> · <https://wiki.archlinux.org/title/System_maintenance>

---

## Fix an AUR build failing its sha256sums validity check

`aur-validity-check-failed-checksums` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
==> Validating source files with sha256sums...
    foo-1.2.tar.gz ... FAILED
==> ERROR: One or more files did not pass the validity check!
```
Often after the AUR maintainer bumped pkgver, or when upstream silently re-rolled a release tarball.

**Cause.** The `sha256sums`/`b2sums` array in the PKGBUILD no longer matches the file actually downloaded. Either the PKGBUILD is stale, upstream replaced the tarball in place, or a stale copy is sitting in your build cache.

> ⚠️ **Risk.** Running `updpkgsums` blindly makes the checksum match WHATEVER you downloaded — including a tampered or MITM'd tarball. Only do this after independently confirming the source is legitimate; never as a reflex to get a build to pass.

**Fix.**

First rule out a stale cached download:

```bash
rm -rf ~/.cache/yay/foo        # or ~/.cache/paru/clone/foo
yay -S foo
```

If it still fails and you have verified the download is legitimate (checked the upstream release page / signature yourself), regenerate the checksums locally:

```bash
sudo pacman -S --needed pacman-contrib
cd /tmp && git clone https://aur.archlinux.org/foo.git && cd foo
updpkgsums          # rewrites the sums arrays in place using makepkg --geninteg
makepkg -si
```

Then tell the maintainer — leave a comment on the AUR page with the error. If the package is flagged out-of-date and you only need a version bump, edit `pkgver` in the PKGBUILD and run `updpkgsums` before building.

**Verify.** `makepkg` gets past "Validating source files" and produces a .pkg.tar.zst; `pacman -Qi foo` shows the new version.

Sources: <https://wiki.archlinux.org/title/Makepkg> · <https://wiki.archlinux.org/title/Arch_User_Repository>

---

## Get back a package that automatic orphan removal deleted

`automatic-orphan-removal-removes-wanted-packages` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** After an update (notably `omarchy-update`, which removes orphans automatically), a program you use is gone — an optional dependency, a font, a codec, or a package you originally installed as a dependency of something you later removed. `pacman -Q thepackage` says it is not installed.

**Cause.** `pacman -Qtdq` lists packages installed as dependencies that nothing currently requires. Piping that into `pacman -Rns` also removes optional dependencies of packages that are staying, and anything you installed with `-S --asdeps` or that was pulled in as a makedepend. Omarchy's `omarchy-update-orphan-pkgs` runs `sudo pacman -Rs --noconfirm` over every orphan on each update.

> **Audit corrected this record.** The Omarchy claim is verified — bin/omarchy-update-orphan-pkgs collects `pacman -Qtdq` and loops `sudo pacman -Rs --noconfirm "$pkg"` over each, unattended, exactly as described. But the central safety recommendation is wrong: it says to 'prefer -Rn over -Rns so optional deps of surviving packages are spared'. -n is --nosave, which has nothing to do with dependencies — it *deletes* config backups instead of leaving .pacsave files, so the suggested flag is strictly more destructive than plain -R. The safety comes entirely from dropping -s (no recursion). Also `pacman -D --asexplicit $(pacman -Qtdq)` errors out when there are no orphans.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Blindly running `pacman -Qdtq | pacman -Rns -` can cascade: removing one orphan orphans its dependencies, and `-s` follows the chain. On a system where install reasons were never curated this can strip out drivers, firmware, or the display stack. Always read the list before confirming.

**Fix.**

Reinstall what you lost and mark it explicit so it is never treated as an orphan again:

```bash
sudo pacman -S thepackage
sudo pacman -D --asexplicit thepackage
```

Find what was removed from the log:

```bash
grep "\[ALPM\] removed" /var/log/pacman.log | tail -40
```

Audit before any future orphan sweep. Review the list, then remove only those packages — dropping `-s` is what stops the recursion into optional dependencies of surviving packages. Do **not** add `-n`: that is `--nosave`, which deletes your config backups instead of leaving `.pacsave` files, and has nothing to do with dependency handling.

```bash
pacman -Qtdq                      # review this list first
pacman -Qtdq | sudo pacman -R -   # no -s recursion, keeps .pacsave backups
```

Protect anything you care about up front (guarded so it does not error when nothing is orphaned):

```bash
orphans=$(pacman -Qtdq) && [ -n "$orphans" ] && sudo pacman -D --asexplicit $orphans
```

On Omarchy, if you do not want unattended orphan removal, run the update steps individually instead of `omarchy-update`:

```bash
omarchy-update-keyring
omarchy-update-system-pkgs
omarchy-update-aur-pkgs
```

**Verify.** `pacman -Qi thepackage | grep 'Install Reason'` reports "Explicitly installed", and it survives the next update.

Sources: <https://wiki.archlinux.org/title/Pacman/Tips_and_tricks> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update-orphan-pkgs> · <https://wiki.archlinux.org/title/System_maintenance>

---

## Clear corrupted packages and .part files from the pacman cache

`corrupted-package-checksum-part-files` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
:: File /var/cache/pacman/pkg/foo-1.2-1-x86_64.pkg.tar.zst is corrupted (invalid or corrupted package (checksum)).
Do you want to delete it? [Y/n]
```
Answering Y and retrying just downloads the same broken file again, in an endless loop.

**Cause.** Two distinct causes. (1) Partially downloaded `.part` files left in the cache by an interrupted download or a custom `XferCommand`. (2) The local sync database holds a checksum for a package that the server has since rebuilt under the same name and version — `pacman -Sy` considers the DB fresh and never re-downloads it, so the stale checksum keeps rejecting the correct file. Omarchy hit exactly this because its package server rebuilds packages without bumping pkgrel.

> ⚠️ **Risk.** Emptying /var/cache/pacman/pkg removes your only offline copies of previously installed package versions, so you lose the ability to downgrade without re-downloading from the Arch Linux Archive.

**Fix.**

Clear partials and force a genuine database re-download (two `y`, not one):

```bash
sudo find /var/cache/pacman/pkg/ -iname '*.part' -delete
sudo rm -f /var/cache/pacman/pkg/foo-*.pkg.tar.zst
sudo pacman -Syy
sudo pacman -Su
```

If it still loops, nuke the cache entry set entirely and retry:

```bash
sudo rm -rf /var/cache/pacman/pkg/*
sudo pacman -Syyu
```

On **Omarchy**, `omarchy-refresh-pacman` does the equivalent (it rewrites pacman.conf + mirrorlist and runs `pacman -Syyuu`):

```bash
omarchy-refresh-pacman stable
```

**Verify.** The package downloads and installs; `sudo pacman -Syu` reports "there is nothing to do" or completes cleanly.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://github.com/basecamp/omarchy/issues/6576> · <https://github.com/basecamp/omarchy/issues/4197> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-refresh-pacman>

---

## Downgrade a package that an update broke

`downgrade-a-broken-package` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** An update breaks something — the browser won't start, audio dies, a driver regresses — and you want the previous version back. `pacman -S foo` only ever installs the newest one.

**Cause.** pacman has no built-in rollback. Older versions live either in your local cache or in the Arch Linux Archive.

> ⚠️ **Risk.** Downgrading a package whose dependencies moved forward creates a partial upgrade — if a soname changed you must downgrade or rebuild the dependants too. Leaving a package in `IgnorePkg` long-term guarantees eventual breakage. Downgrading the kernel without also downgrading matching out-of-tree modules (nvidia, virtualbox-host-modules) will leave you with no graphics; always regenerate the initramfs afterwards.

**Fix.**

**From the local cache (fastest, if you have not cleaned it):**

```bash
ls /var/cache/pacman/pkg/ | grep '^foo-'
sudo pacman -U file:///var/cache/pacman/pkg/foo-1.2.3-1-x86_64.pkg.tar.zst
```

**From the Arch Linux Archive** (pacman fetches the .sig and verifies it automatically):

```bash
sudo pacman -U https://archive.archlinux.org/packages/f/foo/foo-1.2.3-1-x86_64.pkg.tar.zst
```
Browse available versions at `https://archive.archlinux.org/packages/f/foo/`.

**Pin it** so the next `-Syu` does not immediately re-upgrade it — in `/etc/pacman.conf` under `[options]`:

```ini
IgnorePkg = foo
```
Remove that line once upstream fixes the bug.

**Kernel specifically** — downgrade linux and its headers together, plus any out-of-tree modules:

```bash
sudo pacman -U file:///var/cache/pacman/pkg/linux-6.16.1.arch1-1-x86_64.pkg.tar.zst \
               file:///var/cache/pacman/pkg/linux-headers-6.16.1.arch1-1-x86_64.pkg.tar.zst
sudo mkinitcpio -P
```

**Automation:** the `downgrade` AUR package wraps both sources:
```bash
yay -S downgrade
sudo downgrade foo
```

**Verify.** `pacman -Qi foo | grep Version` shows the old version and the broken behaviour is gone. For a kernel downgrade, reboot and check `uname -r`.

Sources: <https://wiki.archlinux.org/title/Downgrading_packages> · <https://wiki.archlinux.org/title/Arch_Linux_Archive> · <https://wiki.archlinux.org/title/Pacman>

---

## Fix 'GPGME error: No data' behind a captive portal or proxy

`gpgme-error-no-data-captive-portal` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
error: GPGME error: No data
error: failed to synchronize all databases (invalid or corrupted database (PGP signature))
```
Common on hotel/airport/campus Wi-Fi, or behind a corporate proxy.

**Cause.** A captive portal or proxy intercepted the HTTPS request and returned an HTML login page. pacman saved that HTML as core.db / core.db.sig, so the signature parse fails and keeps failing because the bogus files are cached.

> **Audit corrected this record.** Cause and the `file /var/lib/pacman/sync/*` sanity check are exactly right, and insisting on completing the captive-portal login before re-syncing is the part people skip. But the cleanup is sloppy in a way that matters for copy-paste-into-root: `sudo rm -f .../sync/*.sig` is immediately made redundant by `sudo rm -rf /var/lib/pacman/sync/`, and an `rm -rf` on a directory under /var/lib/pacman is one stray space away from destroying the local package database next to it. Delete the poisoned files, not the directory.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting /var/lib/pacman/sync is safe (it only holds downloadable repo indexes) — do NOT confuse it with /var/lib/pacman/local, which is your irreplaceable installed-package database.

**Fix.**

Confirm the sync files are actually junk:

```bash
file /var/lib/pacman/sync/*
# healthy output says 'gzip compressed data' / 'Zstandard compressed data'
# a captive portal leaves 'HTML document text'
```

Get onto a real network (complete the captive-portal login first), then delete only the poisoned database files — do not `rm -rf` the directory, /var/lib/pacman/local sits right next to it:

```bash
sudo rm -f /var/lib/pacman/sync/*.db /var/lib/pacman/sync/*.db.sig \
           /var/lib/pacman/sync/*.files /var/lib/pacman/sync/*.files.sig
sudo pacman -Syyu
```

If you must stay behind a proxy, also let dirmngr honour it — add to both `/etc/gnupg/dirmngr.conf` and `/etc/pacman.d/gnupg/dirmngr.conf`:

```
honor-http-proxy
```

and pass the variables through sudo:

```bash
sudo -E env http_proxy="$http_proxy" https_proxy="$https_proxy" pacman -Syu
```

**Verify.** `file /var/lib/pacman/sync/*` reports compressed data for every file, and `sudo pacman -Syu` syncs without GPGME errors.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/Pacman/Package_signing>

---

## Stop omarchy-update wiping custom repositories from pacman.conf

`omarchy-update-overwrites-pacman-conf` · severity: **medium** · frequency: **common** · applies to: `arch`, `desktop`, `laptop`, `omarchy`

**Symptom.** Custom repositories you added (Chaotic-AUR, CachyOS, a local repo) silently vanish after running `omarchy-update`. Users report: "I have added CachyOS repos into pacman.conf and mirrorlist, but Omarchy-Update just replaced it out of a sudden!" Packages installed from those repos then show as foreign/orphaned.

**Cause.** `omarchy-refresh-pacman` — invoked during channel switches and refreshes — does `sudo cp -f $OMARCHY_PATH/default/pacman/pacman-$channel.conf /etc/pacman.conf` and `sudo cp -f .../mirrorlist-$channel /etc/pacman.d/mirrorlist`. It is a wholesale overwrite, not a merge. It does take a backup first.

> ⚠️ **Risk.** Only ONE level of backup is kept — the .bak files are overwritten on the next refresh. If you run omarchy-refresh-pacman twice you lose the original. Also, mixing third-party repos (CachyOS/Chaotic) with Omarchy's own mirror can produce packages from different epochs and cause partial-upgrade breakage.

**Fix.**

Your previous config is not lost — it is in the .bak files the script writes:

```bash
sudo diff -u /etc/pacman.conf /etc/pacman.conf.bak
sudo diff -u /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.bak
```

Re-append your custom repo section to the freshly written pacman.conf:

```bash
sudo tee -a /etc/pacman.conf >/dev/null <<'EOF'

[chaotic-aur]
Include = /etc/pacman.d/chaotic-mirrorlist
EOF
sudo pacman -Syu
```

To make this survivable, keep your additions in a versioned snippet and re-apply after every update:

```bash
mkdir -p ~/.config/omarchy
cat > ~/.config/omarchy/extra-repos.conf <<'EOF'

[chaotic-aur]
Include = /etc/pacman.d/chaotic-mirrorlist
EOF
# after each omarchy-update:
grep -q '^\[chaotic-aur\]' /etc/pacman.conf || sudo tee -a /etc/pacman.conf < ~/.config/omarchy/extra-repos.conf
```

**Verify.** `pacman-conf --repo-list` lists your custom repo alongside core/extra/multilib/omarchy, and `sudo pacman -Syu` syncs its database.

Sources: <https://github.com/basecamp/omarchy/issues/3497> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-refresh-pacman> · <https://raw.githubusercontent.com/basecamp/omarchy/master/default/pacman/pacman-stable.conf>

---

## Fix invalid PGP signatures caused by a wrong system clock

`pgp-signature-invalid-wrong-system-clock` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** On a fresh install, a dual-boot machine, or after a dead CMOS battery:
```
error: PackageName: signature from "User <email@archlinux.org>" is invalid
error: failed to commit transaction (invalid or corrupted package (PGP signature))
Errors occurred, no packages were upgraded.
```
Reinstalling the keyring does not help.

**Cause.** pacman-key/GnuPG validates signatures against the system clock. If the clock is in the past or the future, valid keys look expired or not-yet-valid, and TLS certificate checks on HTTPS mirrors fail too. Windows dual-boot writing localtime to the RTC is the usual culprit.

**Fix.**

```bash
timedatectl                      # look at 'System clock synchronized' and 'RTC in local TZ'
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd
timedatectl                      # confirm the time is now correct
sudo hwclock --systohc           # write the corrected time back to the RTC in UTC
sudo pacman -Syu
```

If you dual-boot Windows, make Windows use UTC as well rather than switching Linux to localtime — in an elevated Windows cmd:

```
reg add "HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /t REG_DWORD /d 1 /f
```

**Verify.** `timedatectl` shows `System clock synchronized: yes` and the correct date; `sudo pacman -Syu` no longer reports invalid signatures.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://wiki.archlinux.org/title/Mirrors>

---

## Stop mise shims breaking AUR builds that need Python, Node or Go

`mise-shims-break-aur-builds` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `desktop`, `laptop`, `omarchy`

**Symptom.** On Omarchy (which ships mise), AUR builds that need Python, Node or Go fail with errors like:
```
/home/user/.local/share/mise/installs/python/3.14.0/bin/python: No module named build
```
The same PKGBUILD builds fine on a plain Arch box.

**Cause.** mise injects its shim directory ahead of /usr/bin in PATH. makepkg inherits that environment, so the build calls mise's managed Python/Node/Go instead of the system interpreter the PKGBUILD's makedepends installed, and the required build modules are absent.

**Fix.**

Build with mise deactivated for that shell:

```bash
mise deactivate
yay -S the-package
```

Or strip the shims from PATH for a single build:

```bash
env PATH="$(echo "$PATH" | tr ':' '\n' | grep -v mise | paste -sd:)" yay -S the-package
```

The durable fix is to build in a clean chroot, which has no user environment at all:

```bash
sudo pacman -S --needed devtools
cd /tmp && git clone https://aur.archlinux.org/the-package.git && cd the-package
extra-x86_64-build
sudo pacman -U the-package-*.pkg.tar.zst
```

**Verify.** `which python` inside the build shell resolves to /usr/bin/python, and the build completes and installs.

Sources: <https://github.com/basecamp/omarchy/issues/3528> · <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://wiki.archlinux.org/title/Makepkg>

---

## Fix a local or file:// repository after the pacman 7.0.0 upgrade

`pacman7-local-repo-alpm-download-user` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** After the pacman 7.0.0 upgrade, a local or file:// repository stops working — pacman cannot read the packages it could read yesterday, with permission-denied style retrieval failures against your own repo directory.

**Cause.** pacman 7.0.0 introduced `DownloadUser = alpm`, downloading as an unprivileged user. That user has no access to a local repo directory owned solely by root or by your user with restrictive permissions. Announced as a required manual intervention on archlinux.org.

**Fix.**

Grant the alpm group read access to the repo and make sure directories are traversable:

```bash
sudo chown :alpm -R /path/to/local/repo
sudo chmod -R a+rX /path/to/local/repo
sudo pacman -Syu
```

Also merge the pacman.conf.pacnew that shipped with pacman 7 so you pick up the new defaults:

```bash
sudo pacman -S --needed pacman-contrib
sudo DIFFPROG=nvim -E pacdiff
```

If you must, you can disable the feature by commenting `DownloadUser` out in `/etc/pacman.conf`, but fixing permissions is the correct fix.

**Verify.** `sudo pacman -Sy` syncs the local repo database and `sudo pacman -S <pkg-from-local-repo>` installs it; `namei -l /path/to/local/repo/repo.db` shows the alpm group can traverse every component.

Sources: <https://archlinux.org/news/manual-intervention-for-pacman-700-and-local-repositories-required/> · <https://archlinux.org/news/> · <https://wiki.archlinux.org/title/Pacman>

---

## Finding truncated or missing package files after a crash or bad disk with pacman -Qkk / paccheck

`verify-installed-files-against-package-database` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** "The machine hard-locked / the disk threw errors / I pulled the plug during an update. It mostly boots, but random things segfault, an icon theme is half missing, and a binary is 0 bytes." Typical runtime fallout:
```
/usr/bin/foo: error while loading shared libraries: libbar.so.5: file too short
bash: /usr/bin/foo: cannot execute binary file: Exec format error
```
`pacman -Syu` says the system is fully up to date and refuses to help.

**Cause.** A crash, a filesystem that filled mid-write, or a failing SSD can leave files that pacman installed truncated, zero-length or missing entirely, while `/var/lib/pacman/local` still records the package as installed at the current version. `pacman -Syu` only compares *versions*; it never looks at the files on disk, so it will never notice and never re-extract them.

> ⚠️ **Risk.** If the local database itself was damaged (`/var/lib/pacman/local`), `-Qkk` reports nonsense and reinstalling on top of it makes things worse — restore the database first. Do not run a blanket `pacman -Qqn | pacman -S -` on a system whose disk is still failing; you will only write more corrupt files. Reinstalling packages overwrites files under `/etc` that the package owns and does not list as backup files, so read the reinstall list first. If you suspect a compromise rather than a crash, run these checks from a live USB against hashes from an independent source — a rootkit can rewrite the local mtree data that `-Qkk` and `paccheck` compare against.

**Fix.**

**1. Find missing files across every installed package:**

```bash
sudo pacman -Qk $(pacman -Qsq) | grep -v ' 0 missing files'
```
Output looks like `foo: 231 total files, 3 missing file(s)`. Nothing printed means nothing is missing.

**2. Find altered files too** (size, mtime, permissions) — this is what catches truncation:

```bash
sudo pacman -Qkk $(pacman -Qsq) | grep -v ' 0 altered files'
```
Expect false positives under `/etc` — those are your own edits.

**3. Real content verification against the packaged hashes**, using `paccheck` from `pacutils`:

```bash
sudo pacman -S --needed pacutils
sudo paccheck --sha256sum --quiet
sudo paccheck --files --file-properties --sha256sum --quiet   # thorough
```

**4. Reinstall everything that came back damaged:**

```bash
sudo bash -c 'LC_ALL=C.UTF-8 pacman -Qk 2>/dev/null | grep -v " 0 missing files" | cut -d: -f1 | \
  while read -r p; do pacman -S --noconfirm "$p"; done'
```
On Omarchy the update guard blocks `-Syu`, not `-S`; if it fires anyway, prefix the command with `env OMARCHY_ALLOW_DIRECT_PACMAN=1`.

**5. Foreign (AUR) packages are in no repo and must be rebuilt:**

```bash
pacman -Qqm                                    # list them
yay -S --rebuildall $(pacman -Qqm | tr '\n' ' ')
```

**6. Check the hardware before you trust the repair:**

```bash
sudo pacman -S --needed smartmontools
sudo smartctl -a /dev/nvme0n1 | grep -iE 'health|media|error'
sudo btrfs scrub start -B /                    # btrfs root
sudo btrfs device stats /
```

**Verify.** A second `sudo pacman -Qk $(pacman -Qsq) | grep -v ' 0 missing files'` prints nothing, and `sudo paccheck --sha256sum --quiet` prints nothing. `sudo btrfs scrub status /` reports 0 uncorrectable errors.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/Pacman/Tips_and_tricks> · <https://man.archlinux.org/man/paccheck.1> · <https://wiki.archlinux.org/title/System_maintenance>

---
