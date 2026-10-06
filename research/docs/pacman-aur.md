# pacman & AUR

59 problems. Sorted by severity, then by how often users hit it.

## DKMS module fails to build during a kernel upgrade, leaving a kernel with no working module

`dkms-module-build-fails-on-kernel-upgrade` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** During `omarchy update` (Omarchy 4) or `pacman -Syu` (plain Arch):
```
(3/9) Install DKMS modules
==> dkms install --no-depmod nvidia/580.95.05 -k 7.1.10-arch1-1
Error! Bad return status for module build on kernel: 7.1.10-arch1-1 (x86_64)
Consult /var/lib/dkms/nvidia/580.95.05/build/make.log for more information.
error: command failed to execute correctly
```
pacman still exits 0 and `omarchy update` carries on as if nothing happened.

After rebooting on plain Arch, or on Omarchy 4 for a module that is not early-loaded (VirtualBox, tuxedo, yt6801): no graphical session, or
```
modprobe: FATAL: Module nvidia not found in directory /lib/modules/7.1.10-arch1-1
```
VirtualBox users see: `Kernel driver not installed (rc=-1908)`.

On Omarchy 4 with NVIDIA the transcript continues with `==> ERROR: module not found: 'nvidia'` (four times) and `mkinitcpio failed for kernel 7.1.10-arch1-1, skipping.`, the boot image on the ESP is never replaced, and a reboot lands on the OLD kernel with a NEW `nvidia-utils`: black screen or an SDDM login loop instead of the modprobe error. That path is the record `nvidia-modules-missing-from-initramfs-black-screen`.

**Cause.** Two distinct causes.

**(a) Missing or mismatched headers.** DKMS builds against `/usr/lib/modules/<kernelver>/build`, which the *matching* headers package owns (`pacman -Qo /usr/lib/modules/$(uname -r)/build` reports `linux-headers`). If you run `linux-lts` but only have `linux-headers` and not `linux-lts-headers`, DKMS has nothing to compile against for that kernel. On Omarchy 4 this only happens for a kernel you added yourself: the installer puts `linux-headers` next to `linux`, and `install/hardware/nvidia.sh` adds the `-headers` package matching whichever of `linux`, `linux-zen`, `linux-lts`, `linux-hardened`, `linux-t2` or `linux-ptl` it finds. On plain Arch nothing installs headers for you.

**(b) The out-of-tree source genuinely does not compile against the new kernel.** Common with the NVIDIA driver on a freshly released mainline kernel. The Arch package is `nvidia-open-dkms` (`nvidia-dkms` no longer exists in the repos, `nvidia-open-dkms` provides that name), and Omarchy installs `nvidia-open-dkms` for GSP-capable cards or `nvidia-580xx-dkms` from its own `[omarchy]` repo for older ones. Both register the DKMS module as plain `nvidia`, so the log is `/var/lib/dkms/nvidia/<version>/build/make.log`. The other variant of (b) is a stale toolchain earlier in `PATH` (classically `/opt/cuda/bin` supplying an old gcc) being picked up instead of the system gcc, producing errors like `gcc: error: unrecognized command-line option '-fmin-function-alignment=16'`.

Two Omarchy 4 details change what you see afterwards. Omarchy installs `kernel-modules-hook`, whose pacman hooks save the running kernel's module tree before the transaction and restore it after, so the kernel you are on keeps its modules and you can still `modprobe` while you repair. And on an NVIDIA machine the four nvidia modules are in `MODULES` via `/etc/mkinitcpio.conf.d/nvidia.conf`, so when the build fails mkinitcpio errors, `limine-mkinitcpio-install` skips installing the new UKI, and the boot image on the ESP stays at the old kernel.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (linux 7.1.9.arch1-2, linux-headers 7.1.9.arch1-2, no linux-lts, dkms 3.4.3-2, kernel-modules-hook 0.1.7-3, nvidia-open-dkms 610.57.04-1, limine-mkinitcpio-hook 1.37.1-1) and against install/hardware/nvidia.sh and install/omarchy-base.packages fetched from quattro. What held: DKMS builds against /usr/lib/modules/<kver>/build, which pacman -Qo shows is owned by linux-headers here. The make.log path holds because nvidia-open-dkms registers the module as plain nvidia (dkms status prints nvidia/610.57.04, 7.1.9-arch1-2, x86_64: installed, and /usr/src holds nvidia-610.57.04). The hook text Install DKMS modules and the dkms install --no-depmod <mod>/<ver> -k <kver> line match /usr/share/libalpm/hooks/70-dkms-install.hook and line 150 of /usr/share/libalpm/scripts/dkms. The linux-lts module directory really ends in -lts (6.18.49-3-lts per the package file list), so the basename glob in step 6 works. The stale-toolchain cause and the -fmin-function-alignment error are exactly what BBS thread 295952 shows, with /opt/cuda/bin/gcc from a .zshenv PATH export. What was wrong: nvidia-dkms no longer exists in the Arch repos (the package page 404s and the search API returns nothing), so both the cause and the danger named a package nobody can install. Omarchy installs nvidia-open-dkms for GSP cards and nvidia-580xx-dkms from its own [omarchy] repo for older ones, never nvidia-open. dkms 3.4.3 autoinstall with no -k acts on the running kernel only (kernelver[0]=$(uname -r) at line 413 of /usr/bin/dkms and have_one_kernel rejects a second -k), so the previous audit note claiming it iterates every kernel was wrong and the per-kernel loop in step 3 is required, not redundant. Omarchy 4 installs linux-headers alongside linux (install/omarchy-other.packages) and nvidia.sh adds the -headers package matching whichever of linux, linux-zen, linux-lts, linux-hardened, linux-t2 or linux-ptl it finds, so on Omarchy the missing-headers cause only applies to a kernel the user added later. Omarchy 4 installs kernel-modules-hook (line 66 of /usr/share/omarchy/install/omarchy-base.packages, same file on quattro), whose 10-linux-modules-pre and -post hooks keep the running kernel's module tree through the transaction, which is why an in-place reload can work on Omarchy and not on plain Arch, consistent with the 2026-09-06 correction to nvidia-modules-missing-from-initramfs-black-screen. sudo mkinitcpio -P cannot work on Omarchy 4: /etc/mkinitcpio.d is empty here, so /usr/bin/mkinitcpio stops with No presets found, and the /usr/local/bin/mkinitcpio wrapper that limine-mkinitcpio-hook installs only prints a warning offering limine-mkinitcpio. The record's limine-mkinitcpio && limine-update pair is redundant: /usr/bin/limine-update runs limine-install and then limine-mkinitcpio itself, and limine-mkinitcpio-install already adds the entry with limine-entry-tool --add-uki, so the UKI got built twice. The after-reboot symptom also differed on Omarchy with NVIDIA: nvidia.sh puts the four nvidia modules in MODULES, mkinitcpio then exits non-zero, limine-mkinitcpio-install prints mkinitcpio failed for kernel ..., skipping and leaves the old UKI in place, so a reboot lands on the old kernel with a driver and userspace mismatch (the other record) rather than the module not found line, which only appears for modules outside MODULES such as vboxdrv and on plain Arch. NOT exercised: no DKMS failure was induced, nothing was rebuilt or rebooted, and dkms autoinstall was not run. The kernel-modules-hook behaviour is read from the hook files, not observed during an upgrade.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Rebooting with a failed DKMS build on an NVIDIA-only machine gives you a black screen or a bare text console with no compositor, and no network manager GUI to fetch a fix with. On Omarchy 4 do not reboot while the update transcript says `mkinitcpio failed for kernel ..., skipping.`: the UKI on the ESP is stale and the reboot lands on the old kernel with a mismatched `nvidia-utils`. Keep `linux-lts` + `linux-lts-headers` installed and selectable in the boot menu before you reboot. Never try to fix this with `pacman -Sy nvidia-open-dkms`: a `-Sy` without `-u` creates a partial upgrade and makes it strictly worse. Always do a full upgrade (`omarchy update` on Omarchy, `pacman -Syu` on Arch). Do not delete `/var/lib/dkms` to "start clean": that loses the build state for every module including ones that currently work.

**Fix.**

**1. See what you actually have:**

```bash
pacman -Q linux linux-lts linux-zen 2>/dev/null
pacman -Q linux-headers linux-lts-headers linux-zen-headers 2>/dev/null
dkms status
uname -r
ls /usr/lib/modules/
```

`dkms status` prints one line per module and kernel, `nvidia/580.95.05, 7.1.10-arch1-1, x86_64: installed`, and must say `installed` for **every** kernel version present in `/usr/lib/modules`.

**2. Install one headers package per installed kernel** (the fix in the majority of cases on plain Arch, and for any second kernel you added on Omarchy 4):

```bash
sudo pacman -S --needed linux-headers
# add these only for kernels you actually have:
# sudo pacman -S --needed linux-lts-headers linux-zen-headers
```

This passes Omarchy's pacman guard, which only stops commands carrying both `-S` and `-u`. Installing headers also fires the DKMS pacman hook, so the module may already be rebuilt when this returns.

**3. Rebuild for every installed kernel.** `dkms autoinstall` with no `-k` only builds for the kernel you are running (dkms 3.x), so the new kernel needs its own call:

```bash
sudo dkms autoinstall                       # running kernel
for d in /usr/lib/modules/*/; do
  kver=$(basename "$d")
  [ -d "$d/build" ] && sudo dkms autoinstall -k "$kver"
done
dkms status
```

**4. If it still fails, read the real compiler error.** The pacman output only points at it:

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
```

On Omarchy 4 installing `linux-lts` already runs the DKMS hook and then the Limine hook, which builds a UKI for it and adds a boot entry. Run step 7 anyway so you have read the output yourself.

**7. Rebuild the boot image last**, so the freshly built module actually gets bundled:

```bash
# Omarchy 4 (Limine + UKI): the wrapper builds the UKI and updates the Limine entry
sudo limine-mkinitcpio

# plain Arch with a normal initramfs:
sudo mkinitcpio -P
```

Do not use `mkinitcpio -P` on Omarchy 4: `/etc/mkinitcpio.d` is empty there, so it stops with `No presets found` and the UKI on the ESP is never replaced. `limine-update` is not needed after `limine-mkinitcpio`, it just reinstalls the bootloader and runs `limine-mkinitcpio` a second time. The output must contain no `module not found:` lines and no `mkinitcpio failed for kernel ..., skipping.` before you reboot.

**Verify.** `dkms status` shows `installed` for the running kernel *and* every other kernel in `/usr/lib/modules`. `modinfo nvidia | head -3` (or `modinfo vboxdrv`) resolves without error. After reboot `lsmod | grep -E 'nvidia|vboxdrv'` is non-empty and `nvidia-smi` prints a driver version.

Sources: <https://wiki.archlinux.org/title/Dynamic_Kernel_Module_Support> · <https://bbs.archlinux.org/viewtopic.php?id=295952> · <https://archlinux.org/packages/extra/any/dkms/files/> · <https://man.archlinux.org/man/alpm-hooks.5> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/blob/quattro/install/hardware/nvidia.sh> · <https://github.com/basecamp/omarchy/blob/quattro/install/omarchy-base.packages> · <https://archlinux.org/packages/extra/x86_64/nvidia-open-dkms/> · <https://archlinux.org/packages/core/x86_64/linux-lts/>

---

## Recover from a partial upgrade that broke shared libraries

`partial-upgrade-broken-shared-libraries` · severity: **critical** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** After running `pacman -Sy something` or `pacman -S something` without a full upgrade, programs start dying with things like:
```
foo: error while loading shared libraries: libbar.so.5: cannot open shared object file: No such file or directory
```
Sometimes pacman or sudo itself stops working.

**Cause.** Arch is a rolling release with no version pinning. `pacman -Sy` refreshes the sync database but installs nothing, so the next `pacman -S pkg` pulls in a *new* library while the rest of the system still links against the *old* soname. Partial upgrades are explicitly unsupported. `pacman -Syuw` and aggressive `IgnorePkg`/`IgnoreGroup` cause the same damage.

On Omarchy 4 the same rule holds, with three local details. `omarchy update` itself runs `sudo pacman -Sy --noconfirm archlinux-keyring` (in `omarchy-update-keyring`) immediately before `pacman -Syu` (in `omarchy-update-system-pkgs`), so an update that dies between those two steps leaves the database refreshed and nothing upgraded, which is this state. `omarchy pkg add` runs `pacman -S --noconfirm --needed`, which is safe only while the database has not been refreshed since the last full upgrade. Omarchy's shipped `/etc/pacman.conf` sets no `IgnorePkg` or `IgnoreGroup`, and `omarchy-refresh-pacman` overwrites that file, so an `IgnorePkg` you added is both a partial-upgrade risk and something a refresh silently removes.

> **Audit corrected this record.** Checked against the Arch wiki System maintenance page (partial upgrades section), the FAQ (single version of each shared library) and the Pacman page (pacman-static section), pacman's hook.c and the alpm-hooks(5) and pacman.conf(5) man pages, the AUR RPC record for pacman-static, and on this Omarchy 4 workstation the guard hook, `/usr/bin/omarchy-update-pacman-guard`, `omarchy-update`, `omarchy-update-keyring`, `omarchy-update-system-pkgs`, `omarchy-pkg-add`, `/etc/pacman.conf` and `/usr/share/omarchy/install/omarchy-base.packages`. What held: the cause, the `-Syuw` and `IgnorePkg`/`IgnoreGroup` warnings, the symlink warning, the `checkupdates -d` advice and the rule to finish `-Su` after `-Sy` all match the wiki wording. The pacman-static URL still answers 200 (file dated 2022-02-20) and the wiki still lists it, calling it outdated. `pacman -Qkk` output here is `bash: 270 total files, 0 altered files`, so the verify grep works. Omarchy's shipped pacman.conf sets no `IgnorePkg` or `IgnoreGroup`. What was wrong: every `sudo pacman -Syu` in the fix and verify is refused on Omarchy 4 by `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook`, which aborts any pacman command line carrying both `-S` and `-u` unless OMARCHY_UPDATE_PACMAN=1 or OMARCHY_ALLOW_DIRECT_PACMAN=1 is set. `omarchy-update-system-pkgs` runs `sudo env LC_ALL=C OMARCHY_UPDATE_PACMAN=1 pacman -Syu --noconfirm --overwrite '/usr/share/omarchy/*'`, so `omarchy update` is the Omarchy form of the wiki's recovery. The guard applies to `pacman-static` too, since the hook lives in the system hook directory that pacman.conf(5) says is always searched, and the guard is a bash script marked AbortOnFail (hook.c line 656 returns -1 on failure), so on a system where bash cannot start the hook itself aborts the transaction even with the bypass set. `omarchy-update-keyring` runs `pacman -Sy archlinux-keyring` right before the full upgrade, so an interrupted `omarchy update` produces this exact state. `pacman-contrib` is in Omarchy's base package list, so the `pacman -S pacman-contrib` line is a plain-Arch step. Sources unchanged. Not exercised: no partial upgrade was induced, the pacman-static binary was not run, and the hook-aborts-when-bash-is-broken path is read from the source, not reproduced.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Do NOT 'fix' a missing soname by symlinking libbar.so.5 -> libbar.so.6. Soname bumps mean the ABI is incompatible. The symlink will produce silent memory corruption and crashes. Also, once `-Sy` has run you must finish the `-Su` before doing any other package operation. On Omarchy 4, moving the guard hook aside removes the only thing that stops a direct `pacman -Syu` from bypassing `omarchy update`'s snapshot, keyring and migration steps, so put it back as soon as the transaction is done.

**Fix.**

Complete the upgrade you started. This is the fix, not a workaround.

**Plain Arch:**

```bash
sudo pacman -Syu
```

**Omarchy 4:** a direct `pacman -Syu` is refused by the update guard hook (`/usr/share/libalpm/hooks/00-omarchy-update-guard.hook`, which aborts any pacman command line carrying both `-S` and `-u`). Use the supported path, which runs `pacman -Syu` with the guard's own variable set:

```bash
omarchy update
```

or bypass the guard for one transaction:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
```

If pacman itself is broken by the missing library, use the static build. The Arch wiki calls this binary outdated (the server dates it 2022-02-20) but still points at it, because the AUR `pacman-static` package needs a working `makepkg`, which a broken system may not have:

```bash
curl -LO https://pkgbuild.com/~morganamilo/pacman-static/x86_64/bin/pacman-static
chmod +x pacman-static
sudo ./pacman-static -Syu pacman                                       # plain Arch
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 ./pacman-static -Syu pacman    # Omarchy 4
```

The guard applies to `pacman-static` as well: hooks in `/usr/share/libalpm/hooks/` run for any pacman that reads the system configuration, and the guard inspects the calling command line for `-S` and `-u`. The guard is a bash script with `AbortOnFail`, so if bash itself cannot start on the broken system the hook fails and pacman aborts the transaction even with the variable set. Move the hook out of the way for that one transaction:

```bash
sudo mv /usr/share/libalpm/hooks/00-omarchy-update-guard.hook /root/
sudo ./pacman-static -Syu pacman
ls /usr/share/libalpm/hooks/00-omarchy-update-guard.hook || sudo mv /root/00-omarchy-update-guard.hook /usr/share/libalpm/hooks/
```

The hook belongs to the `omarchy` package, so if the upgrade replaced that package the hook is already back and the last line does nothing.

If even `pacman-static` will not run, boot the Arch ISO and run its pacman with `--sysroot` against the mounted system (Arch wiki, Pacman, "Using an external pacman"). On Omarchy the guard hook runs inside the sysroot too, so the same variable or hook move applies.

To check for updates safely in future without touching the sync DB, use `checkupdates`. Omarchy 4 ships it: `pacman-contrib` is in its base package set and `omarchy-update-available` uses it. On plain Arch install it after the upgrade above has completed, not before:

```bash
sudo pacman -S --needed pacman-contrib
checkupdates          # safe, does not sync the live database
checkupdates -d       # pre-download pending updates to the cache
```

Never use `pacman -Sy pkg`. Always `pacman -Syu` or `pacman -Syu pkg` on plain Arch, and `omarchy update` then `omarchy pkg add pkg` on Omarchy 4. To confirm nothing is pending afterwards, use `checkupdates` (prints nothing when the system is current) rather than `sudo pacman -Syu`, which the guard refuses.

**Verify.** `sudo pacman -Syu` reports nothing to do, and the previously broken binary runs. `sudo pacman -Qkk $(pacman -Qsq) | grep -v ' 0 altered files'` shows no missing library files.

Sources: <https://wiki.archlinux.org/title/System_maintenance> · <https://wiki.archlinux.org/title/Frequently_asked_questions> · <https://wiki.archlinux.org/title/Pacman> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/hook.c> · <https://pkgbuild.com/~morganamilo/pacman-static/x86_64/bin/pacman-static> · <https://aur.archlinux.org/rpc/v5/info?arg[]=pacman-static>

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
`df -h /boot` shows a 260 MB to 512 MB FAT32 partition at 100%. The kernel package is registered as installed but there is no usable vmlinuz/initramfs to boot.

**Cause.** The ESP is mounted at `/boot` and every installed kernel writes `vmlinuz-*` plus `initramfs-*.img` (plus a fallback image on older installs, plus microcode) into it. Omarchy 4 is worse: `limine-entry-tool` is configured with `ENABLE_UKI=yes`, so each kernel becomes a single 100 to 200 MB Unified Kernel Image at `/boot/EFI/Linux/omarchy_linux.efi`, and snapshots multiply that. FAT32 has no reserved blocks, pacman's `CheckSpace` estimate is only approximate, and the UKI/initramfs is written by a **PostTransaction** hook, i.e. after pacman has already committed. Arch recommends a 1 GiB ESP. 260 MiB is merely the FAT32 formatting minimum on a 4Kn drive, not a working size.

> **Audit corrected this record.** Cause and steps 1-4 are verified correct, impressively so. Omarchy really does ship /etc/limine-entry-tool.d/omarchy-uki.conf containing `ENABLE_UKI=yes` and omarchy-defaults.conf containing `CUSTOM_UKI_NAME="omarchy"`, which makes /boot/EFI/Linux/omarchy_linux.efi the exact real path (omarchy-refresh-limine references that literal filename). `limine-entry-tool --remove-uki "<kernel name>"` is a real documented subcommand. MKINITCPIO_FALLBACK accepts (yes|no|<kernel-name>) so `MKINITCPIO_FALLBACK=no` is valid, and /etc/limine-entry-tool.d/*.conf is the correct drop-in directory. The fallback claim is right: upstream mkinitcpio's mkinitcpio.d/hook.preset now ships PRESETS=('default') with #PRESETS=('default' 'fallback') commented, and the CHANGELOG says 'The default kernel preset files no longer includes the fallback image'. The record's preset edit matches the real template verbatim, including `#fallback_options="-S autodetect"`.

Step 5 is the problem and it is the kind that leaves a machine unbootable. Three defects. (a) It tells you to add a /efi line to fstab but never to remove the existing /boot line, so `mount -a` just remounts the ESP at /boot and nothing changes. (b) Once the ESP is unmounted, /boot on the root filesystem is empty, and `mkinitcpio -P` writes only initramfs: it does NOT write vmlinuz or microcode, both of which come from packages, so the machine has no kernel to boot until those are reinstalled, and the bootloader is never reinstalled at the new path either. (c) On Omarchy the step does not work at all as a remedy: with ENABLE_UKI=yes the UKI is written to $ESP_PATH/EFI/Linux/ by definition, so moving ESP_PATH to /efi relocates the problem rather than solving it, and /etc/default/limine is a file Omarchy manages (it ships default/limine/default.conf with ESP_PATH="/boot"), so a hand edit there can be overwritten. Steps 1-4 stand as written.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not reboot while /boot is full or an initramfs/UKI is truncated. You will land in an emergency shell or the firmware will find no boot entry, and recovery needs a live USB. NEVER `rm -rf /boot/*`: that deletes the bootloader itself (limine/GRUB/systemd-boot), not just kernels, and on a dual-boot machine it deletes `/boot/EFI/Microsoft` and the `/boot/EFI/BOOT/BOOTX64.EFI` removable-media fallback too. Removing the fallback initramfs removes your one non-autodetect rescue image. Keep an Arch ISO on a USB stick. Changing the ESP mount point rewrites fstab and bootloader paths, so do it with a live USB within reach.

**Fix.**

Replace step 5 with the following. Steps 1-4 are unchanged.

**5a. Omarchy 4: do NOT try to move the ESP.** With `ENABLE_UKI=yes` the UKI is written to `$ESP_PATH/EFI/Linux/` by definition, so relocating the ESP relocates the problem. On Omarchy the space is consumed by *snapshot* boot entries, so cap those instead:

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

**Verify.** `df -h /boot` shows free space. `ls -l --time-style=full-iso /boot/vmlinuz-linux /boot/initramfs-linux.img` (or `/boot/EFI/Linux/omarchy_linux.efi`) shows a non-zero size with a timestamp from the last minute. `sudo pacman -S linux` completes with no `command failed to execute correctly`.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=278308> · <https://wiki.archlinux.org/title/EFI_system_partition> · <https://wiki.archlinux.org/title/Mkinitcpio> · <https://wiki.archlinux.org/title/Limine> · <https://gitlab.com/Zesko/limine-entry-tool/-/blob/master/README.md> · <https://github.com/basecamp/omarchy/discussions/3700>

---

## "error: command failed to execute correctly" from a pacman hook after the transaction already committed

`hook-failed-command-failed-to-execute-correctly` · severity: **critical** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A pacman transaction prints a red `error: command failed to execute correctly` right after a hook's `(n/m) <Description>` line. What it means depends on which hook, and Omarchy 4 has two shapes plain Arch never shows.

Omarchy 4, before anything is installed, after a direct `sudo pacman -Syu`:
```
:: Running pre-transaction hooks...
(1/2) Checking Omarchy update entrypoint...

Woah partner...

This looks like a direct pacman system upgrade. Omarchy updates should normally
run through:

  omarchy update
error: command failed to execute correctly
error: failed to commit transaction (failed to run transaction hooks)
Errors occurred, no packages were upgraded.
```

Omarchy 4, after the packages are on disk, when `/boot` is not mounted:
```
(7/9) Updating linux initcpios...
ERROR: Boot path '/boot' is not a mounted FAT32 boot partition.
error: command failed to execute correctly
(8/9) Arming ConditionNeedsUpdate...
```

Plain Arch, after the packages are on disk, when mkinitcpio itself fails:
```
(7/9) Updating linux initcpios...
==> Building image from preset: /etc/mkinitcpio.d/linux.preset: 'default'
==> ERROR: '/usr/lib/modules/7.2.3-arch1-3' is not a valid kernel module directory
error: command failed to execute correctly
(8/9) Arming ConditionNeedsUpdate...
```
Users ask: "pacman said the packages installed but printed `error: command failed to execute correctly`. Did the update work? Is it safe to reboot?"

**Cause.** `error: command failed to execute correctly` is libalpm's message for any hook `Exec` that exited non-zero (`lib/libalpm/util.c`). What it means depends on when the hook ran. Per alpm-hooks(5), `AbortOnFail` applies only to PreTransaction hooks, and on an Omarchy 4 install exactly one hook sets it: Omarchy's own `00-omarchy-update-guard.hook`. So there are two cases.

**1. The Omarchy update guard.** `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` runs `/usr/bin/omarchy-update-pacman-guard` before every transaction that upgrades a package, with `AbortOnFail`. The script exits 1 when the pacman command line carries both `-S` and `-u` (`-Syu`, `-Su`, `--sync --sysupgrade`) and neither `OMARCHY_UPDATE_PACMAN=1` nor `OMARCHY_ALLOW_DIRECT_PACMAN=1` is set. pacman then prints `error: failed to commit transaction (failed to run transaction hooks)` and `Errors occurred, no packages were upgraded.` Nothing was installed. This is the most common way to see the message on Omarchy and it is harmless: the `Woah partner...` banner above it is the tell.

**2. Every other hook.** None of the kernel, initramfs, DKMS or bootloader hooks sets `AbortOnFail`. The ones that build things are PostTransaction (`90-mkinitcpio-install`, `70-dkms-install`, `80-limine-efi-deploy`, `99-omarchy-limine`), and the PreTransaction ones (`60-mkinitcpio-remove`, `70-dkms-upgrade`, `60-limine-mkinitcpio-remove-pre`, `10-linux-modules-pre`) cannot abort either. So when one of these fails the packages are already unpacked and the database already says the new kernel is installed, and nothing is rolled back.

Which hook produced the error matters more than the error itself:

- On plain Arch, mkinitcpio's `90-mkinitcpio-install.hook` passes mkinitcpio's exit status through, so a broken initramfs build is the classic source and `/boot` can hold a stale or truncated image.
- On Omarchy 4 that hook is overridden by `limine-mkinitcpio-hook`'s `/etc/pacman.d/hooks/90-mkinitcpio-install.hook` (same file name in a higher-priority hook directory, which alpm-hooks(5) defines as an override). It runs `/usr/share/libalpm/scripts/limine-mkinitcpio-install`, which exits non-zero only when its ESP check fails (`/boot` missing, not a mountpoint, or not vfat) or a `/etc/boot/hooks/*.d` hook exits 100 or above. A failed mkinitcpio build inside it prints `ERROR: mkinitcpio failed for kernel <ver>, skipping.` and exits 0, so pacman prints no error for it at all. The UKI is built in `/tmp` and installed afterwards, so a failed build leaves the previous `/boot/EFI/Linux/omarchy_linux.efi` in place rather than a truncated one.
- The DKMS hook script `/usr/share/libalpm/scripts/dkms` prints `==> ERROR: Missing <ver> kernel headers for module ...` when a module cannot be built and still returns 0, so a missing NVIDIA module never produces this pacman error either.
- Cosmetic hooks (font, icon, MIME and desktop caches, man-db, dbus, systemd catalog) fail the same way and mean nothing for boot.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (omarchy 4.0.2-1, limine-mkinitcpio-hook 1.37.1-1, mkinitcpio 41.1-1, dkms 3.4.3-2, pacman 7.1.0) by listing every hook in /usr/share/libalpm/hooks and /etc/pacman.d/hooks with its owner and reading the Omarchy ones: 00-omarchy-update-guard (PreTransaction, AbortOnFail, /usr/bin/omarchy-update-pacman-guard), the 10/90 omarchy-hyprland-reload pause/resume pair (every failure path in /usr/bin/omarchy-hyprland-reload-guard is swallowed), 10-limine-snapper-lock, kernel-modules-hook's 10-linux-modules-pre/post, limine-mkinitcpio-hook's 60/80/90 hooks plus its /etc/pacman.d/hooks/90-mkinitcpio-install.hook override, the unowned /etc/pacman.d/hooks/99-omarchy-limine.hook, and the dkms trio. alpm-hooks(5) (local man page, pacman 7.1.0) confirms AbortOnFail is PreTransaction only and that a same-named file in a higher-priority hook directory overrides. libalpm sources confirm the strings: util.c prints `command failed to execute correctly` on any non-zero hook exit, trans.c returns ALPM_ERR_TRANS_HOOK_FAILED when a PreTransaction AbortOnFail hook fails, and src/pacman/sync.c at v7.1.0 prints `failed to commit transaction (%s)` and `Errors occurred, no packages were upgraded.` What was wrong: the record does not know that on Omarchy the commonest source of this exact error is the update guard, which fires BEFORE the transaction and installs nothing, so its title and cause (`after the transaction already committed`, `nothing is rolled back`) are the opposite of the usual Omarchy case. Its claim that every kernel, DKMS and bootloader hook is PostTransaction is false (60-mkinitcpio-remove, 70-dkms-upgrade, 60-limine-mkinitcpio-remove-pre and 10-linux-modules-pre are PreTransaction), though the conclusion survives because none sets AbortOnFail. Its sample output cannot occur on Omarchy 4: /etc/mkinitcpio.d/ is empty here (no preset line), and /usr/share/libalpm/scripts/limine-mkinitcpio-install swallows mkinitcpio failures (`process_kernel ... || true`, `process_uki_kernel || return 0`) and exits non-zero only when check_boot_partition in /usr/lib/limine/limine-common-functions fails or a /etc/boot/hooks hook exits 100 or above, so on Omarchy the error at `Updating linux initcpios...` means an ESP problem, not a bad build. The DKMS hook script ends in `return 0` after printing its ERROR lines, so DKMS failures never produce this pacman error on either distribution, which the record's table implied. Fix corrections: `ls /boot/EFI/Linux/` needs sudo (dmask=0077, confirmed by a permission error as the user and a sudo listing showing a 144 MB omarchy_linux.efi dated 2026-09-06), `sudo limine-mkinitcpio` followed by `sudo limine-update` runs limine-mkinitcpio twice because limine-update already calls it (read /usr/bin/limine-update), `sudo mkinitcpio -P` on Omarchy 4 dies on `No presets found` (/usr/bin/mkinitcpio line 986) before the /usr/local/bin wrapper offers limine-mkinitcpio, the cosmetic list named 30-systemd-update.hook where systemd 261.2-1 ships 35-systemd-update.hook, and `pacman -S linux` when a newer kernel is available is a lone kernel upgrade that strands linux-headers (installed from omarchy-other.packages) and nvidia-open-dkms. The `if it fires anyway` bypass was dropped because the guard script cannot fire on `-S linux`. Danger corrected for Omarchy: the UKI is built in /tmp and installed by limine-entry-tool afterwards, no fallback UKI exists (MKINITCPIO_FALLBACK unset in /etc/limine-entry-tool.conf, /etc/limine-entry-tool.d/*.conf and /etc/default/limine, and /boot/EFI/Linux holds only omarchy_linux.efi), and /boot/limine.conf carries a Snapshots submenu with per-snapshot UKI copies under limine_history. Sources: bbs 291242 supports only that the error follows a non-zero mkinitcpio hook on plain Arch. GitHub discussion 3700 (now under omacom/omarchy) rendered only its title through curl, so its body was not checked. Not exercised: no hook was made to fail, no transaction was run, and the guard output shape was assembled from the hook script's banner and the pacman source strings rather than observed.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** On plain Arch a failed mkinitcpio hook can leave a zero-length or truncated initramfs while the package database happily reports the new kernel as installed. Rebooting then drops you at `ERROR: device 'UUID=...' not found. Skipping fs check` and an initramfs emergency shell, and recovery requires a live USB. On Omarchy 4 a failed UKI build leaves the previous `/boot/EFI/Linux/omarchy_linux.efi` in place and `kernel-modules-hook` restores the running kernel's modules after the transaction, so the previous kernel still boots, but there is no fallback UKI (`MKINITCPIO_FALLBACK` is unset) and the previous kernel's modules are gone once the new one has booted. The Limine boot menu's `Snapshots` submenu boots the last five `omarchy update` snapshots with the kernel each one had, which is the recovery path if the new UKI turns out bad. Never reboot on an unresolved mkinitcpio, limine or DKMS failure. Have an Arch ISO on a USB stick before you start poking at this.

**Fix.**

**1. Identify which hook failed.** The `(n/m) <Description>` line immediately above the error names it. Find the file by its description and read its `Exec =` line:

```bash
sudo tail -n 200 /var/log/pacman.log
grep -l 'Description = Updating linux initcpios' /usr/share/libalpm/hooks/*.hook /etc/pacman.d/hooks/*.hook
pacman -Qo /etc/pacman.d/hooks/90-mkinitcpio-install.hook     # which package owns it
cat /etc/pacman.d/hooks/90-mkinitcpio-install.hook             # the Exec line is what to rerun
```

A file in `/etc/pacman.d/hooks/` overrides a file of the same name in `/usr/share/libalpm/hooks/`. On Omarchy 4 both `90-mkinitcpio-install.hook` files exist and the `/etc` one (from `limine-mkinitcpio-hook`) is the one that ran.

**2. Classify it.**

Omarchy update guard, nothing installed, reboot is irrelevant: the output carries `Woah partner...` and `Errors occurred, no packages were upgraded.` Run the supported path instead:

```bash
omarchy update
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu     # one transaction, if you really mean to bypass it
```

Cosmetic, reboot is safe, fix at leisure: `fontconfig.hook`, `gtk-update-icon-cache.hook`, `update-desktop-database.hook`, `texinfo-install.hook`, `man-db-remove-cache.hook`, `dbus-reload.hook`, `glib-compile-schemas.hook`, `35-systemd-update.hook`.

Boot-critical, do not reboot until it succeeds:

| Description | Hook file | Package | Runs |
|---|---|---|---|
| Updating linux initcpios... | `90-mkinitcpio-install.hook` in `/usr/share/libalpm/hooks/` | `mkinitcpio` | `mkinitcpio -P` (plain Arch) |
| Updating linux initcpios... | `90-mkinitcpio-install.hook` in `/etc/pacman.d/hooks/` | `limine-mkinitcpio-hook` | `limine-mkinitcpio-install` (Omarchy 4, builds the UKI and the Limine entry) |
| Deploying Limine after upgrade... | `80-limine-efi-deploy.hook` | `limine-mkinitcpio-hook` | `limine-install` |
| Deploying Omarchy Limine after upgrade... | `99-omarchy-limine.hook` in `/etc/pacman.d/hooks/` | none (written at install time) | `cp /usr/share/limine/BOOTX64.EFI /boot/EFI/limine/limine_x64.efi` |
| Install DKMS modules | `70-dkms-install.hook` | `dkms` | `dkms install` per module and kernel, always exits 0 |

**3. Re-run the critical hook by hand, so the real error is on your screen.**

Omarchy 4. Every `limine-*` failure above starts with the ESP check, so mount `/boot` first if it was not mounted, then rebuild everything with one command. `limine-update` runs `limine-install --no-efi-register` and then `limine-mkinitcpio`, so there is no need to run both:

```bash
findmnt /boot || sudo mount /boot
sudo limine-update
```

Do not reach for `sudo mkinitcpio -P` on Omarchy 4: `/etc/mkinitcpio.d/` is empty, so `/usr/bin/mkinitcpio -P` dies with `No presets found in /etc/mkinitcpio.d`, and the `/usr/local/bin/mkinitcpio` wrapper only offers to run `limine-mkinitcpio` afterwards.

Plain Arch, EndeavourOS, CachyOS, Manjaro:

```bash
sudo mkinitcpio -P
```

DKMS, any distribution. `nvidia-open-dkms` needs `linux-headers` at the same version as `linux`:

```bash
dkms status
pacman -Q linux linux-headers
sudo dkms autoinstall
```

**4. Prove the files were really written.** `/boot` is mounted `dmask=0077` on Omarchy 4, so listing it needs root:

```bash
sudo ls -l --time-style=full-iso /boot/EFI/Linux/                   # Omarchy 4: omarchy_linux.efi, over 100 MB, dated now
ls -l --time-style=full-iso /boot/vmlinuz-* /boot/initramfs-*.img    # plain Arch
pacman -Q linux; uname -r
```

**5. Sledgehammer that re-fires every kernel hook.** Reinstalling the kernel package re-triggers the whole chain (`10-linux-modules-*`, `70-dkms-install`, `90-mkinitcpio-install`). The Omarchy update guard passes `-S linux`, because it only aborts on `-S` together with `-u`. Only do this when pacman says it is a reinstall:

```bash
sudo pacman -S linux          # or linux-lts / linux-zen
```

```
warning: linux-7.1.9.arch1-2 is up to date -- reinstalling
```

If it offers a newer version instead, stop and run `omarchy update`. A lone kernel upgrade leaves `linux-headers` behind, `nvidia-open-dkms` then reports `Missing ... kernel headers` and builds nothing, and the hook's exit code does not tell you.

**Verify.** `sudo limine-update` on Omarchy 4 (or `sudo mkinitcpio -P` on plain Arch) exits 0 with no `ERROR` lines. `sudo ls -l /boot/EFI/Linux/omarchy_linux.efi` (or `ls -l /boot/initramfs-linux.img`) shows a file over 100 MB (or several MB) with a timestamp from the last minute. `pacman -Q linux` and `uname -r` agree after the reboot. A second `sudo pacman -S linux` runs clean end to end.

Sources: <https://man.archlinux.org/man/alpm-hooks.5> · <https://wiki.archlinux.org/title/Pacman> · <https://bbs.archlinux.org/viewtopic.php?id=291242> · <https://archlinux.org/packages/core/any/mkinitcpio/files/> · <https://archlinux.org/packages/extra/any/dkms/files/> · <https://wiki.archlinux.org/title/Limine> · <https://github.com/basecamp/omarchy/discussions/3700> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/util.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/hook.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/lib/libalpm/trans.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/src/pacman/sync.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/src/pacman/pacman.c> · <https://archlinux.org/packages/core/x86_64/linux/json/>

---

## Recover a system left unbootable by an interrupted pacman upgrade

`interrupted-upgrade-unbootable-pacman-broken` · severity: **critical** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** Power was lost, the machine froze, or the terminal was killed in the middle of `pacman -Syu`. Now the system will not boot, or it boots but `pacman` itself is broken: `pacman: command not found`, or `pacman: error while loading shared libraries: libalpm.so.16`.

**Cause.** pacman was midway through replacing files. Half the transaction is on disk, the database is inconsistent, and if pacman's own libraries or binary were in flight, there is no working tool left to repair with. Symlinking /var/cache/pacman/pkg (which pacman recreates as a directory during self-upgrade) is a known way to trigger the `pacman: command not found` variant.

> **Audit corrected this record.** Mostly sound: pacman-static, the chroot, and replaying the interrupted transaction from the log (the cut -d ' ' -f4 does land on the package name given pacman's log format) are all correct. Two problems. First, the fallback `pacman --root=/mnt --cachedir=... -Syu` omits --dbpath: whether that operates on /mnt's database or the live ISO's depends on whether DBPath is commented out in the ISO's pacman.conf, and if it resolves to the ISO's database pacman will make decisions from the wrong package set. Always pass --dbpath explicitly. Second, it says to rebuild 'initramfs and bootloader entries' but gives no bootloader command, which on an unbootable machine is the step that matters, and the root-run pacman-static should be signature-verified.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Manually extracting package tarballs over / with tar is the last-resort option in the wiki and the wiki itself warns it is extremely easy to make things worse. Always use the `w` (interactive) flag and extract dependencies in order. Never symlink /var/cache/pacman/pkg. Use the `CacheDir` option in pacman.conf or a bind mount instead. Back up /var/lib/pacman before any repair attempt.

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

Then rebuild the initramfs **and** the bootloader before rebooting. Use the one your system actually has:

```bash
mkinitcpio -P
grub-mkconfig -o /boot/grub/grub.cfg     # GRUB
# systemd-boot:  bootctl update
# Omarchy/limine: limine-update
exit
sudo umount -R /mnt
reboot
```

Only if pacman cannot run inside the chroot at all, drive it from outside, and pass **both** --root and --dbpath, otherwise pacman may operate against the live ISO's database instead of the installed system's:

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

**Cause.** /var/lib/pacman/local, pacman's record of what is installed, has been deleted, truncated, or corrupted (a full disk mid-transaction, a bad `rm`, a filesystem error, or restoring / from an incomplete backup). The files on disk are fine, but pacman just no longer knows about them.

> **Audit corrected this record.** Checked the wiki procedure against Pacman/Restore_local_database (raw wikitext, fetched 2026-09-06) and the pacman 7.1.0 source, and checked every Omarchy claim on this Omarchy 4 workstation (omarchy 4.0.2-1, pacman 7.1.0.r9.g54d9411-2). What held: the symptoms, the pacrecover script, the recovery-pacman flags, the ALPM_DB_VERSION note (the file exists here and contains 9, and /usr/bin/pacman-db-upgrade still ships and writes 9), and the tar prevention. What was wrong for Omarchy 4: the closing `sudo pacman -Su` is aborted by 00-omarchy-update-guard.hook, whose script /usr/bin/omarchy-update-pacman-guard treats the single argument -Su as both sync and sysupgrade (read on this machine), so the fix now ends with `omarchy update` or the OMARCHY_ALLOW_DIRECT_PACMAN=1 bypass, and the verify line no longer tells Omarchy users to run `pacman -Syu`. The record also ignored the better first recovery on Omarchy: `omarchy update` runs `omarchy-snapshot create` before every upgrade (read /usr/share/omarchy/bin/omarchy-update and omarchy-snapshot), the Snapper config is SUBVOLUME=/ with NUMBER_LIMIT=5 and TIMELINE_CREATE=no (/etc/snapper/configs/root and /usr/share/omarchy/default/snapper/root), and `sudo snapper list` here shows snapshots 1 and 2, with /.snapshots/2/snapshot/var/lib/pacman/local holding 1185 entries against 1188 live, while /.snapshots/2/snapshot/var/log is empty because /var/log is the separate @log subvolume (findmnt and btrfs subvolume list). The corrected fix adds that copy as the Omarchy first step and keeps the log-driven pass to close the gap, since the snapshot database predates the last update. Two defects that apply on plain Arch too: `expac -l '\n' '%E' base` without -S reads the local database being rebuilt (expac(1): -S searches the sync databases), and `pacman -S --needed pacman-contrib expac` against an empty database pulls the whole dependency tree into file conflicts, so the install now uses -dd --overwrite (pacman(8): -d twice skips all dependency checks). On Omarchy both tools are already installed from omarchy-base.packages. Confirmed from src/pacman/pacman.c at tag v7.1.0 that --dbonly sets NOSCRIPTLET and NOHOOKS, so no hook, including the guard, runs during the recovery-pacman steps. Added the single-package `pacman -S --overwrite` branch from the Pacman page and a yay build-directory argument for AUR packages (yay -Pg reports buildDir ~/.cache/yay here). Not exercised: no database was damaged or restored, no snapshot copy was made, and the recovery commands were not run. The snapshot copy and the -dd install are derived from the sources named, not from a live run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** This procedure uses `--dbonly --overwrite '*' --nodeps`, the most dangerous flag combination pacman has. Run it ONLY for database reconstruction, exactly as written. Get it wrong and you will need a full reinstall. Back up /var/lib/pacman and /var/log/pacman.log before starting. If /var/log/pacman.log is also gone, the log-driven method cannot be used. A database copied out of a Snapper snapshot is older than the files on disk. Stopping after the copy leaves pacman believing older versions are installed, and the next upgrade rewrites every package changed since the snapshot. `omarchy-snapshot restore` rolls back the whole root subvolume, not only the database, and discards every change made on / since that snapshot.

**Fix.**

`pacman -Q` reads only `/var/lib/pacman/local`. The package files on disk and `/var/log/pacman.log` are intact, and both recoveries below lean on the log, so check it is there first:

```bash
ls -l /var/log/pacman.log
```

**Omarchy 4: copy the database out of the last Snapper snapshot.** `omarchy update` takes a Snapper snapshot of the root subvolume before every upgrade (`omarchy-snapshot create`, retention `NUMBER_LIMIT="5"`, timeline snapshots off), and `/var/lib/pacman` lives on that subvolume, so the newest snapshot holds a complete local database as it stood before the last update. `/var/log` is its own subvolume (`@log`) and is not in the snapshot, which is why the log survives whatever happened to the database.

```bash
sudo snapper list                                   # pick the newest number, N
sudo mv /var/lib/pacman/local /var/lib/pacman/local.broken
sudo cp -a /.snapshots/N/snapshot/var/lib/pacman/local /var/lib/pacman/local
pacman -Q | wc -l                                   # a full Omarchy install is over 1,000
```

That database is older than the files on disk: every package upgraded or installed since the snapshot is missing or recorded at the wrong version. Do not stop here. Continue with the log-driven pass below, which with `--needed` only touches those packages.

If more than the database is damaged, `omarchy-snapshot restore` rolls the whole root subvolume back to a snapshot, and the Limine boot menu lists the same snapshots under "Snapshots" with the kernel each one had. That returns `/usr` and the database to a matching state at the cost of everything changed on `/` since. `/home` is its own subvolume and is untouched. Run it as `omarchy-snapshot restore`, not under `sudo`: the script calls `sudo` itself.

**All systems: rebuild the database from the log.** `paclog-pkglist` (pacman-contrib) and `expac` are both in Omarchy's base package set, so on Omarchy they are already on disk and this install changes nothing. On plain Arch with an empty database a normal `pacman -S` would try to install their whole dependency tree and stop on file conflicts, so skip dependency checks and let it overwrite:

```bash
sudo pacman -S -dd --needed --overwrite '*' pacman-contrib expac
```

Create the recovery script. Any extra directory holding package files can be passed as an argument. yay's build directory (`~/.cache/yay`) matters for AUR packages, which are in no repository and can only come back from a cached file:

```bash
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
paclog-pkglist /var/log/pacman.log | ./pacrecover ~/.cache/yay/*/ >files.list 2>pkglist.orig
{ cat pkglist.orig; pacman -Slq; } | sort | uniq -d > pkglist
comm -23 <({ echo base; expac -S -l '\n' '%E' base; } | sort) pkglist.orig >> pkglist
```

`expac -S` reads the sync databases. Without `-S` expac reads the local database you are trying to rebuild and returns nothing for `base`.

Then reconstruct the database only. `--dbonly` also implies `--noscriptlet` and `--nohooks`, so no hook runs during these steps, including Omarchy's update guard:

```bash
recovery-pacman() { sudo pacman "$@" --log /dev/null --noscriptlet --dbonly --overwrite '*' --nodeps --needed; }
sudo pacman -Sy
recovery-pacman -U $(< /tmp/files.list)
recovery-pacman -S $(< /tmp/pkglist)
sudo pacman -D --asdeps $(pacman -Qq)
sudo pacman -D --asexplicit $(pacman -Qtq)
```

The two `pacman -D` lines recompute the install reason of every package. Skip them if you restored from a snapshot, which already carried the right reasons.

If you get `failed to initialise alpm library`, check for `/var/lib/pacman/local/ALPM_DB_VERSION` (pacman 7 writes `9` there). If it is missing, run `sudo pacman-db-upgrade`, then `sudo pacman -Sy`, and retry.

Finish with a full upgrade. On Omarchy the update guard aborts any pacman command line that carries both `-S` and `-u`, and `-Su` counts, so use the supported path or the one-transaction bypass:

```bash
omarchy update                                       # Omarchy 4
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Su    # Omarchy 4, one transaction only
sudo pacman -Su                                      # plain Arch
```

**One damaged entry rather than the whole directory.** If the error names a single package (`could not open file /var/lib/pacman/local/<pkg>-<ver>/desc`, or `file exists in filesystem` for one package because its `files` list is empty or missing), the Pacman wiki's fix is to reinstall only that package with `--overwrite`:

```bash
sudo pacman -S --overwrite '*' <pkg>
```

**Prevention.** `omarchy update` already snapshots the root subvolume before each upgrade, so on Omarchy the last five updates are recoverable without any extra step. A tarball still covers the case where the snapshots are gone too:

```bash
sudo tar -cjf ~/pacman_database.tar.bz2 /var/lib/pacman/local
```

**Verify.** `pacman -Q | wc -l` returns a plausible package count, `pacman -Qtdq` lists only genuine orphans, and a full upgrade behaves normally: `omarchy update` on Omarchy 4, `sudo pacman -Syu` on plain Arch. `pacman -Qk` reports few or no missing files. If you copied the database from a snapshot, `pacman -Qkk` reports no size or checksum mismatches once the log-driven pass has run.

Sources: <https://wiki.archlinux.org/title/Pacman/Restore_local_database> · <https://wiki.archlinux.org/title/Pacman/Tips_and_tricks> · <https://man.archlinux.org/man/pacman.8> · <https://wiki.archlinux.org/title/Pacman> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/src/pacman/pacman.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/trans.c>

---

## Rebuild AUR packages after a soname bump blocks the upgrade

`aur-package-needs-rebuild-after-soname-bump` · severity: **high** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `sudo pacman -Syu` or `yay -Syu` aborts with something like:
```
error: failed to prepare transaction (could not satisfy dependencies)
:: unable to satisfy dependency 'libfoo.so=5-64' required by my-aur-package
```
or an AUR-installed program stops launching after a system upgrade with a `cannot open shared object file` error.

**Cause.** Repo packages get mass-rebuilt against new library sonames by Arch's build infrastructure. Locally built AUR packages do not, so you are responsible for rebuilding them. The versioned `.so` dependency recorded in your local AUR package no longer exists.

> **Audit corrected this record.** Diagnosis is right and pacman -Qmq / the deleted-package comm check against aur.archlinux.org/packages.gz are correct. But the headline command is the wrong shape: `yay -S --rebuildall $(pacman -Qmq)` is a plain -S with no -u, so it does not advance the blocked upgrade, and rebuilding an AUR package before the repo upgrade lands means rebuilding against the *old* libraries, which is the exact state that broke. The rebuild has to happen in the same transaction as the upgrade (or after it).
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not solve this by adding the AUR package to `IgnorePkg`, because that just freezes you into a permanent partial-upgrade state.

**Fix.**

Identify your foreign (AUR / locally built) packages:

```bash
pacman -Qmq                      # list all foreign packages
```

Upgrade the system and rebuild every AUR package in one transaction. This is what unblocks the dependency error:

```bash
yay -Syu --rebuildall            # or: paru -Syu --rebuild
```

Just the offending package (after the repo upgrade has gone through):

```bash
yay -S --rebuild my-aur-package
```

Without a helper, as a normal user and never as root (makepkg refuses to run as root):

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

Also check whether the package still exists upstream, since deleted ones will never build again:

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

> **Audit corrected this record.** Checked against the Arch wiki Pacman page section 'Failed to commit transaction (conflicting files)', the System_maintenance page ('Generally avoid using the --overwrite option', glob argument), the pacman(8) man page on this machine (`--overwrite <glob>`, comma-separated patterns, may be repeated, negation with `!`), and pacman source: src/pacman/sync.c prints `pkg: /path exists in filesystem` for an unowned file and `... exists in filesystem (owned by other)` when another package owns it, and lib/libalpm/conflict.c line 533 treats a path listed in the local db entry of the same package as not a conflict. That last point is what breaks the record's Case B: a file that `pacman -Qo` attributes to the very package being upgraded cannot produce this error, and when the package's `/var/lib/pacman/local/<pkg>-<ver>/files` list is empty or corrupt (the record's own cause), `-Qo` reports 'No package owns' exactly as in Case A, because `-Qo` reads that same list. The corrected fix tells Case A and Case B apart with `pacman -Ql some-package` and the local db files list, and Case C by the '(owned by ...)' suffix. Second defect: every upgrade command in the fix and the verify is `sudo pacman -Syu`, which the `00-omarchy-update-guard.hook` PreTransaction hook (read at /usr/share/libalpm/hooks/) aborts on Omarchy 4. Third, Omarchy 4 already handles part of this case and the record does not say so: `/usr/share/omarchy/bin/omarchy-update-system-pkgs` (read here, omarchy 4.0.2-1) runs `pacman -Syu --noconfirm --overwrite '/usr/share/omarchy/*'`, and on failure hands the error report to `omarchy-update-system-pkgs-when-conflicted`, which moves unowned paths reported for `omarchy`, `omarchy-dev`, `omarchy-settings` or `omarchy-settings-dev` to `/var/lib/omarchy/replaced/<path>` and retries, but only when every 'exists in filesystem' line is one of those. Conflicts from any other package stop `omarchy update`. The scoped-glob advice and the single-quoting are correct and kept. `pacman -S --overwrite ... pkg` without -u is not blocked by the guard, confirmed by reading `omarchy-update-pacman-guard`. Not exercised: no conflict was induced on this machine and `pacman -Ql` on a package with an emptied files list was not run, so that -Ql prints nothing in that state is inferred from -Qo and -Ql reading the same local db list.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `pacman --overwrite '*'` (or `--overwrite '/*'`) is the classic way to destroy an Arch install. It can clobber the initramfs and kernel files and leave the machine with "Unable to find root device" at boot. Always scope the glob to the exact path in the error.

**Fix.**

Find out who owns the offending file before touching anything, and read the error line carefully: an unowned file prints `pkg: /path exists in filesystem`, a file owned by another package prints `pkg: /path exists in filesystem (owned by other-pkg)`.

```bash
pacman -Qo /usr/lib/something.so
pacman -Ql some-package | head
```

**Omarchy 4 first:** `omarchy update` already runs pacman with `--overwrite '/usr/share/omarchy/*'`, and when every conflicting path is unowned and reported for `omarchy`, `omarchy-settings` or their `-dev` variants, its conflict handler (`omarchy-update-system-pkgs-when-conflicted`) moves them to `/var/lib/omarchy/replaced/<original path>` and retries by itself. So if this error survives `omarchy update`, the file belongs to some other package's path. Resolve it with one of the cases below, then rerun `omarchy update`. Do not rerun with `sudo pacman -Syu`: the Omarchy update guard hook aborts it.

**Case A: `No package owns` and `pacman -Ql some-package` still lists files.** A stray file that `make install`, a tarball or a curl-installed tool put there. Rename it out of the way and rerun the upgrade.

```bash
sudo mv /usr/lib/something.so /usr/lib/something.so.bak
omarchy update                 # Omarchy 4
sudo pacman -Syu               # plain Arch
# once the upgrade succeeds and things work:
sudo rm /usr/lib/something.so.bak
```

**Case B: `No package owns` but `pacman -Ql some-package` prints nothing, or `/var/lib/pacman/local/some-package-<ver>/files` is empty or missing.** The package's own file list is corrupt, so pacman no longer knows it owns those files and reports every one of them as conflicting. `-Qo` cannot tell this apart from Case A because it reads the same list. Reinstall the package with an overwrite scoped to exactly the paths in the error. Single quotes stop the shell expanding the glob. Several paths are comma-separated or given with repeated `--overwrite`:

```bash
sudo pacman -S --overwrite '/usr/lib/something.so' some-package
sudo pacman -S --overwrite '/usr/lib/something.so,/usr/lib/other.so' some-package
```

This is a plain `-S` with no `-u`, so the Omarchy guard does not block it, and it does not refresh the sync database, so it is not a partial upgrade.

**Case C: the line ends in `(owned by other-package)`.** Two packages ship the same path. That is a packaging bug: check the Arch news and the package's bug tracker, report it, and do not force it. Never use `--overwrite` with a bare `'*'` or `'/*'`.

**Verify.** The upgrade completes with no `conflicting files` errors (`omarchy update` on Omarchy 4, `sudo pacman -Syu` on plain Arch), and `pacman -Qkk some-package` reports 0 missing and 0 altered files.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/System_maintenance> · <https://man.archlinux.org/man/pacman.8> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/conflict.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/sync.c>

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

> **Audit corrected this record.** Symptom and cause hold. The tzdata line is quoted verbatim from basecamp/omarchy issue 4197 (Omarchy 3.3.3, closed), read in full with comments: dhh suggested omarchy-refresh-pacman and clearing the cache, and the reporter resolved it with pacman-key --init, --populate archlinux, pacman -Sy archlinux-keyring, then the update, so the issue supports the record. The Arch wiki Pacman/Package signing page, fetched as raw wikitext today, still gives exactly `pacman -Sy --needed archlinux-keyring && pacman -Su` under Upgrade system regularly and states it is not considered a partial upgrade, lists the three causes of unknown trust the record's cause describes, and adds one thing the record predates: since pacman 7.1 (this machine has 7.1.0) pacman refreshes an expired known key from WKD by itself, so the expired-key case is now mostly self-healing. What is wrong is the Omarchy 4 side. Read on this machine, /usr/bin/omarchy-update-pacman-guard aborts any pacman command line carrying both S and u unless OMARCHY_ALLOW_DIRECT_PACMAN=1 or OMARCHY_UPDATE_PACMAN=1 is set, so the `sudo pacman -Su` half of steps 1 to 3 and the `sudo pacman -Syu` in verify are refused on Omarchy 4. `pacman -Sy --needed archlinux-keyring` alone passes, because it has no u. The right Omarchy form is `omarchy update`, which already does the wiki's sequence: /usr/share/omarchy/bin/omarchy-update (omarchy 4.0.2-1, identical on quattro) runs omarchy-update-keyring immediately before omarchy-update-system-pkgs, and that helper re-imports and lsigns 40DFB630FF42BCFFB047046CF0134EE680CAC571 from keys.openpgp.org only if omarchy-keyring or the key is missing, then always runs `pacman -Sy --noconfirm archlinux-keyring`, and system-pkgs runs `pacman -Syu` with OMARCHY_UPDATE_PACMAN=1. /var/log/pacman.log on this machine shows that reinstall on 2026-09-06 during an update. The record presents omarchy-update-keyring as a standalone fix, which leaves the machine after a bare -Sy with no upgrade, the state the script's own comment says is only acceptable because the full upgrade follows. The key is present here (pacman-key --list-keys shows Omarchy <pkgs@omarchy.org>, ed25519, 2025-08-28, full trust) and omarchy-keyring 20251027-1 ships /usr/share/pacman/keyrings/omarchy.gpg, omarchy-trusted and omarchy-revoked, so after wiping /etc/pacman.d/gnupg a bare `pacman-key --populate` restores the Omarchy key from disk, which the danger text says needs a manual re-import and re-lsign. archlinux-keyring-wkd-sync.timer exists here, owned by archlinux-keyring 20260727-1, static, active (waiting), OnCalendar=weekly, next trigger 2026-09-12, wired by the package's own /usr/lib/systemd/system/timers.target.wants/ symlink and with no [Install] section, so the record's `systemctl enable --now` is unnecessary and, being a static unit, is not something systemctl enable is meant for. The wiki also scopes the timer to marginal trust, not to a missing new packager key, which the record slightly overstates. The record's master raw URL for omarchy-update-keyring returns 200 and matches quattro byte for byte, so that source is valid. Not exercised: no machine here has a stale keyring, so the recovery sequence was verified against the wiki and the scripts, not run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do NOT "fix" this by setting `SigLevel = Never` or `TrustAll` in /etc/pacman.conf. That disables signature verification system-wide and lets a hostile or corrupted mirror install anything. Deleting /etc/pacman.d/gnupg destroys every locally signed key. Keys that came from a keyring package (`archlinux-keyring`, and on Omarchy 4 `omarchy-keyring`) come back with `pacman-key --populate`, but keys you imported and lsigned by hand (Chaotic-AUR, CachyOS, a private repo) have to be re-imported and re-lsigned. On Omarchy 4 the next `omarchy update` re-imports the Omarchy key by itself if it is missing.

**Fix.**

**Plain Arch / EndeavourOS / CachyOS**

Step 1. Sync the database and upgrade only the keyring, then upgrade everything. The Arch wiki gives this exact form and states it is not a partial upgrade, because the full upgrade follows immediately:

```bash
sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su
```

Step 2. If that still fails, clear the half-downloaded and unverifiable packages from the cache and retry:

```bash
sudo rm -f /var/cache/pacman/pkg/*.part
sudo pacman -Sc
sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su
```

Step 3. Last resort, reset the keyring and repopulate it from the installed keyring packages:

```bash
sudo rm -rf /etc/pacman.d/gnupg
sudo pacman-key --init
sudo pacman-key --populate
sudo pacman -Sy --needed archlinux-keyring && sudo pacman -Su
```

**Omarchy 4**

Do not run `pacman -Su` or `pacman -Syu` directly. Both carry `-S` and `-u`, so `/usr/bin/omarchy-update-pacman-guard` aborts the transaction. `omarchy update` already does the wiki's sequence itself: it runs `omarchy-update-keyring` right before the system upgrade, and that helper re-imports and locally signs Omarchy's packaging key `40DFB630FF42BCFFB047046CF0134EE680CAC571` from `keys.openpgp.org` if it is missing, installs `omarchy-keyring` if it is missing, then always reinstalls `archlinux-keyring` with `pacman -Sy --noconfirm archlinux-keyring` and goes straight into the full upgrade:

```bash
omarchy update
```

If the update still fails on signatures, clear the cache first and rerun it:

```bash
sudo rm -f /var/cache/pacman/pkg/*.part
sudo pacman -Sc
omarchy update
```

Last resort, reset the keyring. `omarchy-keyring` ships `/usr/share/pacman/keyrings/omarchy.gpg`, so a bare `pacman-key --populate` restores the Omarchy key alongside the Arch keys with no keyserver round trip, and `omarchy update` then refreshes `archlinux-keyring` and upgrades:

```bash
sudo rm -rf /etc/pacman.d/gnupg
sudo pacman-key --init
sudo pacman-key --populate
omarchy update
```

Do not run `omarchy-update-keyring` on its own as the fix. It ends with a bare `pacman -Sy` and relies on the full upgrade that `omarchy update` runs right after it. Stopped there, the machine has synced databases and un-upgraded packages, which is the partial-upgrade state.

Prevention: `archlinux-keyring-wkd-sync.timer` refreshes the signatures on already trusted keys weekly, which prevents the related "marginal trust" failure. The `archlinux-keyring` package wires it in itself through `/usr/lib/systemd/system/timers.target.wants/`, the unit is `static`, and it needs no `systemctl enable`. Check that it is waiting:

```bash
systemctl list-timers --all | grep keyring
```

**Verify.** `sudo pacman -Syu` downloads and installs without any "unknown trust" or "invalid or corrupted package (PGP signature)" lines. `sudo pacman-key --list-keys | head` shows a populated keyring.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://wiki.archlinux.org/title/Pacman> · <https://github.com/basecamp/omarchy/issues/4197> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update-keyring> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-keyring> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pacman-guard> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-pacman> · <https://archlinux.org/packages/core/any/archlinux-keyring/json/>

---

## Full filesystem during an upgrade: download-phase write errors vs commit-phase CheckSpace abort

`filesystem-full-during-pacman-transaction` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Two distinct failures, and with `CheckSpace` on (the Arch and Omarchy default) pacman usually stops before either one writes anything.

Before download or before commit (`CheckSpace` measuring the cache directory, then the install targets):
```
error: Partition / too full: 1450000 blocks needed, 12000 blocks free
error: not enough free disk space
error: failed to commit transaction (not enough free disk space)
```
The mount point named is the one that ran out. On Omarchy 4 the package cache is its own subvolume, so the download check names `/var/cache/pacman/pkg` and the commit check names `/`. Both live on the same btrfs, so the free figure is shared.

Mid-download (space ran out while downloading, or `CheckSpace` is commented out):
```
error: failed retrieving file 'chromium-...-x86_64.pkg.tar.zst' from mirror : Failed writing received data to disk/application
warning: failed to retrieve some files
error: failed to commit transaction (failed to retrieve some files)
```

On Omarchy 4, `omarchy update` refuses to start at all below 10 GiB free on `/`:
```
You need at least 10 GiB free to safely update Omarchy.
```

Worst case `df -h /` shows 100% and even `sudo pacman -Sc` fails with `failed to init transaction (unable to lock database)`, because pacman cannot create `/var/lib/pacman/db.lck`.

**Cause.** pacman needs room twice: once for the downloaded `.zst` packages in `/var/cache/pacman/pkg`, and again for the extracted files at commit time. With `CheckSpace` enabled (it is, in Arch's stock `pacman.conf` and in Omarchy's `default/pacman/pacman-stable.conf`) libalpm checks both: the total download size against the cache directory's mount point before downloading, and the installed size against every affected mount point before commit, with a cushion of 5% of the filesystem or 20 MiB, whichever is smaller. A `Failed writing received data` error mid-download therefore means space vanished during the download (another process writing, or btrfs metadata exhaustion that `statvfs` does not see) or `CheckSpace` was turned off. An interrupted download leaves `.part` files behind, on pacman 7 inside a `download-XXXXXX` directory in the cache.

On btrfs, the default on Omarchy and CachyOS, `df` can report free space while the metadata chunks are exhausted, and snapshots pin the old version of every file an update replaced. Omarchy 4 installs one btrfs filesystem with subvolumes `@` on `/`, `@home`, `@log` on `/var/log` and `@pkg` on `/var/cache/pacman/pkg`. Snapper's only config, `root`, snapshots `@`, so a snapshot pins `/usr`, `/opt` and `/var/lib` but not the package cache and not the journal: pruning those two frees space immediately, deleting a file under `/usr` frees nothing until every snapshot holding it is gone. `omarchy update` creates one `number` snapshot per run and keeps `NUMBER_LIMIT="5"`, so five updates' worth of replaced files stay allocated on a stock install.

> **Audit corrected this record.** Read libalpm sync.c, diskspace.c, util.c, handle.c and error.c from gitlab.archlinux.org. CheckSpace guards both phases, not only commit: sync.c calls _alpm_check_downloadspace against the cache directory before any download starts (line 797) and _alpm_check_diskspace before commit (line 1319), both printing 'Partition <mountpoint> too full: N blocks needed, N blocks free' then 'not enough free disk space'. The record's claim that the download phase 'dies mid-download' is only true when CheckSpace is off or space vanishes during the download, so the cause was rewritten. Omarchy 4 layout confirmed from /etc/fstab here and tools/make-test-vm.sh (the ISO configurator layout): one btrfs with @ on /, @home, @log on /var/log and @pkg on /var/cache/pacman/pkg. /var is not a separate mount, so the example 'Partition /var too full' was generalised. Snapper's only config is root with SUBVOLUME="/" (default/snapper/root, identical upstream and local), so snapshots pin /usr and /var/lib but never the package cache or the journal, which the record did not say. The 10 GiB string is verbatim from bin/omarchy-update-requires-free-space (identical to quattro), and bin/omarchy-update calls it BEFORE omarchy-update-pkg-prune and omarchy-snapshot, so under 10 GiB omarchy update refuses without pruning anything. Added the manual prune (omarchy-update-pkg-prune, which is sudo paccache -rk2, matching the record's -rk2 advice) and the OMARCHY_UPDATE_FORCE=1 bypass. Snapshot count: omarchy-snapshot create runs snapper create -c number then cleanup number with NUMBER_LIMIT=5, and snapper-cleanup.timer is enabled here, so a stock install holds at most 5 snapshots (6 briefly, per etc/limine-entry-tool.d/omarchy-defaults.conf). Snapshots are Limine boot entries: limine-snapper-sync 1.31.0-1 is installed and BOOT_ORDER contains Snapshots. Added --sync from the Snapper wiki so freed space shows immediately. The escape hatch and the retry used sudo pacman -Syu, which the Omarchy guard rejects, so both now carry OMARCHY_ALLOW_DIRECT_PACMAN=1 in a labelled branch. pacman 7 with DownloadUser=alpm creates a download-XXXXXX subdirectory chowned to alpm inside the cache dir (util.c _alpm_download_dir_setup), so a root-owned --cachedir works. The 'even pacman -Sc fails' line is now explained rather than asserted: -Sc takes the database lock (src/pacman/sync.c line 910) by creating /var/lib/pacman/db.lck, which can fail on a full filesystem as 'failed to init transaction (unable to lock database)'. That failure was reasoned from source, not reproduced. btrfs filesystem usage, btrfs filesystem df and balance advice match the Btrfs wiki page. Not exercised: filling a filesystem on a VM.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `pacman -Scc` empties the cache including the versions currently installed, so no offline reinstall and no downgrade path afterwards. `journalctl --vacuum-size=0` destroys every boot log, including the ones needed to diagnose why the disk filled. Deleting snapper snapshots is irreversible and removes your rollback points: delete the oldest first and never the snapshot matching your last known-good boot, and remember that on Omarchy those snapshots are also the Limine boot-menu rollback entries. `OMARCHY_UPDATE_FORCE=1` skips the 10 GiB check only, the update still needs room for the download and the commit, and a snapshot taken on a nearly full filesystem can itself push it to full. `btrfs balance` on a nearly-full filesystem can itself fail with ENOSPC and must never be interrupted: free something else first and let it finish, or temporarily add a device as the Btrfs wiki describes. `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu` upgrades packages without Omarchy's snapshot, migrations or post-update hooks, so run `omarchy update` afterwards. Never delete anything under `/var/lib/pacman`: that is the package database, and losing it means pacman no longer knows what is installed.

**Fix.**

**Reclaim in this order, least destructive first.** Start by measuring:

```bash
df -h / /boot
sudo du -xhd1 /var | sort -h | tail
sudo btrfs filesystem usage /        # btrfs: look at Metadata and Unallocated
btrfs filesystem df /                # same numbers without root
```

**Omarchy 4 first:** `omarchy update` checks for 10 GiB free on `/` before it prunes the cache or takes a snapshot, so below that it refuses and frees nothing. Prune by hand, then retry:

```bash
omarchy-update-pkg-prune            # runs: sudo paccache -rk2 (do not prefix with sudo)
omarchy update
```
To run an update anyway with less than 10 GiB free:

```bash
OMARCHY_UPDATE_FORCE=1 omarchy update
```

**1. Journal, biggest instant win, always safe:**
```bash
journalctl --disk-usage
sudo journalctl --vacuum-size=200M
```

**2. Package cache, keep 2 versions so you can still downgrade** (this is exactly what `omarchy update` does on every run):
```bash
sudo pacman -S --needed pacman-contrib
sudo paccache -rk2
sudo paccache -ruk0            # drop everything for packages you no longer have
```

**3. Interrupted-download leftovers** (pacman 7 puts them in a `download-XXXXXX` subdirectory, the find recurses into it):
```bash
sudo find /var/cache/pacman/pkg -name '*.part' -delete
```

**4. Build and user caches:**
```bash
yay -Sc
rm -rf ~/.cache/yay/* ~/.cache/paru/clone/* ~/.cache/thumbnails ~/.cache/mesa_shader_cache*
```

**5. Btrfs snapshots, what actually frees a full Omarchy root.** A stock Omarchy 4 keeps at most 5 (`NUMBER_LIMIT="5"` in `/etc/snapper/configs/root`, cleaned by `snapper-cleanup.timer`), so more than that means the timer is off or the config was changed. Delete the oldest, never the newest, and use `--sync` so the space is returned before you measure again:
```bash
sudo snapper -c root list
sudo snapper -c root delete --sync 12-14   # oldest numbers first, keep the latest
sudo btrfs balance start -dusage=50 /
sudo btrfs filesystem usage /
```
On Omarchy those snapshots are also Limine boot entries (`limine-snapper-sync`, `BOOT_ORDER="*, *fallback, Snapshots"`), and `limine-snapper-sync.service` drops the entry when the snapshot goes.

**6. Old kernels / UKIs on a full `/boot`:** see the ESP-full record.

**Escape hatch when nothing can be freed:** download to another disk for this one transaction. pacman 7 creates an `alpm`-owned `download-XXXXXX` directory inside the path you give, so a root-owned directory is fine.

Plain Arch:
```bash
sudo mkdir -p /run/media/$USER/BIGDISK/pkgcache
sudo pacman -Syu --cachedir /run/media/$USER/BIGDISK/pkgcache
```
Omarchy 4 (the update guard rejects a bare `pacman -Syu`, and this bypasses `omarchy update`'s snapshot and migrations, so run `omarchy update` afterwards):
```bash
sudo mkdir -p /run/media/$USER/BIGDISK/pkgcache
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --cachedir /run/media/$USER/BIGDISK/pkgcache
omarchy update
```

**Then retry:**

Plain Arch:
```bash
sudo pacman -Syu
```
Omarchy 4:
```bash
omarchy update
```

**Verify.** `df -h /` shows more than 10 GiB free (Omarchy's own hard threshold in `omarchy-update-requires-free-space`). `sudo btrfs filesystem usage /` shows non-zero `Device unallocated`. `sudo pacman -Syu` or `omarchy update` runs to completion with no `too full` or `Failed writing received data` errors.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://man.archlinux.org/man/pacman.conf.5> · <https://wiki.archlinux.org/title/System_maintenance> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-requires-free-space> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf> · <https://wiki.archlinux.org/title/Btrfs> · <https://wiki.archlinux.org/title/Snapper> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/sync.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/diskspace.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/util.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/handle.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/error.c> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pkg-prune> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-snapshot> · <https://github.com/basecamp/omarchy/blob/quattro/default/snapper/root> · <https://github.com/basecamp/omarchy/blob/quattro/install/config/snapper.sh> · <https://github.com/basecamp/omarchy/blob/quattro/etc/limine-entry-tool.d/omarchy-defaults.conf> · <https://github.com/basecamp/omarchy/blob/quattro/test/shell.d/update-pkg-prune-test.sh>

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
Under `--noconfirm` (which is how `omarchy update` runs pacman) that question is answered No and the run stops with `error: failed to prepare transaction (could not satisfy dependencies)`.

Or, when you try to remove a held package with `pacman -R`:
```
warning: pacman is designated as a HoldPkg.
:: HoldPkg was found in target list. Do you want to continue? [y/N]
```
Weeks later, on a system that reports itself fully updated: `libfoo.so.6: cannot open shared object file: No such file or directory`.

**Cause.** A package listed in `IgnorePkg`/`IgnoreGroup` in `/etc/pacman.conf` (or passed via `--ignore`) is skipped by `-Syu`, but pacman upgrades everything *around* it. That is a partial upgrade, which Arch does not support: the held package is now linked against library sonames that no longer exist. `HoldPkg` is a different mechanism: it is checked only by `pacman -R` (src/pacman/remove.c), which asks for confirmation before removing a listed package. It never blocks an upgrade, and a `-S` transaction that removes a held package through a conflict or a replacement does not prompt at all. Omarchy ships `HoldPkg = pacman glibc` in `/etc/pacman.conf` as a safety net and no `IgnorePkg`. Two Omarchy 4 specifics: the `ignoring package upgrade` warning is printed to stderr only and never written to `/var/log/pacman.log`, and `omarchy refresh pacman` (also run by `omarchy reinstall pkgs`) overwrites `/etc/pacman.conf` with the channel template from `/usr/share/omarchy/default/pacman/`, so a hold added by hand disappears and the held package is upgraded in that same run.

> **Audit corrected this record.** Checked /etc/pacman.conf on this Omarchy 4 workstation: `HoldPkg = pacman glibc`, no IgnorePkg, byte-identical to /usr/share/omarchy/default/pacman/pacman-stable.conf and to the quattro copy fetched via gh. `pacman -Qo` says it is owned by pacman 7.1.0.r9.g54d9411-2 and `pacman -Qii pacman` lists it as a backup file, so hand edits get a .pacnew rather than being overwritten on plain Arch. What was wrong, from source: the HoldPkg symptom block quoted a prompt pacman never prints. src/pacman/remove.c prints `warning: %s is designated as a HoldPkg.` then `:: HoldPkg was found in target list. Do you want to continue? [y/N]`, and that is the only HoldPkg check in pacman (config->holdpkg is set in src/pacman/conf.c and read nowhere else), so it fires only in `pacman -R`, never when a `-S` transaction replaces a held package as the record and its step 6 claimed. `alpm_error.c` has no "user aborted the operation" string. Step 1's `grep 'ignoring package upgrade' /var/log/pacman.log` can never match: lib/libalpm/sync.c check_literal emits it via `_alpm_log` only, with no `alpm_logaction`, and pacman's cb_log writes that to stderr (compare add.c, whose `directory permissions differ` warning does call alpm_logaction and is the only `[ALPM] warning:` shape in this machine's pacman.log). `pacman -Qu` marks held packages `[ignored]` (src/pacman/query.c) and replaces it. The Omarchy note was wrong in the other direction: the skip question uses `noyes` in src/pacman/callback.c, so `--noconfirm` answers No, libalpm returns ALPM_ERR_UNSATISFIED_DEPS and pacman aborts. Read /usr/share/omarchy/bin/omarchy-update-system-pkgs and -when-conflicted here, which retry only on `unresolvable package conflicts detected` or `exists in filesystem`, so the update stops with the ERR trap banner from omarchy-update rather than "quietly doing less". Steps 4 and 5 ran bare `sudo pacman -Syu`, which /usr/bin/omarchy-update-pacman-guard aborts (both -S and -u present, no env var). A grep of /usr/share/omarchy/bin found no IgnorePkg or --ignore handling, so the Omarchy branch is the OMARCHY_ALLOW_DIRECT_PACMAN=1 bypass. Biggest Omarchy 4 miss: /usr/share/omarchy/bin/omarchy-refresh-pacman (called by omarchy-reinstall-pkgs) does `cp -f $OMARCHY_PATH/default/pacman/pacman-$channel.conf /etc/pacman.conf`, runs the `pre-refresh-pacman` hook, then `pacman -Syyuu --noconfirm`, so a hand-added IgnorePkg is dropped and the held package upgraded in one run. The shipped sample ~/.config/omarchy/hooks/pre-refresh-pacman.d/add-custom-repo.sample names extra IgnorePkg lines as its use case, and pacman.conf(5) confirms `Include` accepts general options, which is the drop-in route. omarchy-update itself never rewrites pacman.conf (the three migrations touching it use targeted sed). Confirmed on this machine: /tmp/omarchy-update.log is absent after reboot, paccache -rk2 in omarchy-update-pkg-prune. Not exercised: no IgnorePkg was set and no upgrade was run, so the abort path was traced in source and scripts, not observed.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Lifting a kernel or GPU hold and upgrading can pull in the exact regression you were avoiding: a kernel that breaks a DKMS module, an NVIDIA driver that breaks your display. Before removing such a hold, make sure `linux-lts` is installed and selectable in the boot menu and that the old packages are still in `/var/cache/pacman/pkg` so you can roll back (Omarchy runs `paccache -rk2` before every update, so the previous version is normally still there). Never leave `IgnorePkg = glibc` or `IgnorePkg = pacman` in place: that guarantees a partial upgrade you cannot recover from with pacman itself. On Omarchy 4, `omarchy refresh pacman` and `omarchy reinstall pkgs` replace `/etc/pacman.conf` with the channel template and then upgrade everything, so a hold you set by hand is silently dropped and the held package is upgraded in that run unless a `pre-refresh-pacman` hook puts it back. If a partial upgrade has already broken things, never "fix" it by symlinking `libfoo.so.5` to `libfoo.so.6`: soname bumps mean the ABI is incompatible, and you will get silent memory corruption instead of a clean error.

**Fix.**

**1. Find out what is actually held:**

```bash
grep -nE '^\s*(IgnorePkg|IgnoreGroup|HoldPkg)' /etc/pacman.conf
grep -rnE '^\s*(IgnorePkg|IgnoreGroup)' /etc/pacman.d/ 2>/dev/null
pacman -Qu                          # held packages are listed with a trailing [ignored]
```
Do not grep `/var/log/pacman.log` for `ignoring package upgrade`: pacman prints that warning to stderr only and never logs it. On Omarchy the update transcript `/tmp/omarchy-update.log` has it, until the next reboot clears `/tmp`.

**2. Almost always the right move, remove the holds and take the whole upgrade:**

```bash
sudoedit /etc/pacman.conf          # delete or comment the IgnorePkg/IgnoreGroup lines
# Arch:
sudo pacman -Syu
# Omarchy:
omarchy update
```
`/etc/pacman.conf` is owned by the `pacman` package and is one of its backup files, so a pacman upgrade leaves your edits alone and writes a `.pacnew` instead.

**3. If you are holding a package for a real reason (a driver regression), pin the whole version-locked set, not one package, and treat it as temporary:**

```
# /etc/pacman.conf  [options]
IgnorePkg = linux linux-headers nvidia-dkms nvidia-utils lib32-nvidia-utils
```
On Omarchy 4 that line does not survive `omarchy refresh pacman` or `omarchy reinstall pkgs`: both copy `/usr/share/omarchy/default/pacman/pacman-<channel>.conf` over `/etc/pacman.conf` (the old file goes to `/etc/pacman.conf.bak`), then run `pacman -Syyuu --noconfirm`, which upgrades the package you were holding. The supported place to re-apply it is a `pre-refresh-pacman` hook, which runs between the copy and the upgrade. The shipped sample `~/.config/omarchy/hooks/pre-refresh-pacman.d/add-custom-repo.sample` names extra `IgnorePkg` lines as a use case. A minimal hook:

```bash
#!/bin/bash
# ~/.config/omarchy/hooks/pre-refresh-pacman.d/ignorepkg   (any name without .sample)
grep -q '^IgnorePkg = linux ' /etc/pacman.conf ||
  sudo sed -i '0,/^\[core\]/s||IgnorePkg = linux linux-headers nvidia-dkms nvidia-utils lib32-nvidia-utils\n\n[core]|' /etc/pacman.conf
```
`omarchy update` itself does not rewrite `/etc/pacman.conf`, so a hold survives ordinary updates.

**4. To skip for exactly one transaction instead of permanently:**

```bash
# Arch:
sudo pacman -Syu --ignore linux,linux-headers
# Omarchy: the update guard blocks any pacman line carrying both -S and -u, and
# omarchy update has no --ignore passthrough, so bypass it for this one run.
# You skip the snapshot, keyring refresh and migrations that omarchy update does.
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --ignore linux,linux-headers
```

**5. If you already created a partial upgrade and things are broken, complete it. Do not symlink libraries or reinstall pieces:**

```bash
sudo pacman -Syu                   # Arch
omarchy update                     # Omarchy
sudo pacman -S $(pacman -Qqn)      # last resort: reinstall every repo package
yay -S --rebuildall $(pacman -Qqm | tr '\n' ' ')   # rebuild AUR pkgs after soname bumps
```

**6. HoldPkg prompt:** it appears only in `pacman -R`. Answer `y` only when you are deliberately replacing the package in the same step. Never `pacman -Rdd glibc`.

**Omarchy note:** `omarchy update` runs `pacman -Syu --noconfirm`, so the "skip the above package" question is answered No and pacman aborts with `failed to prepare transaction (could not satisfy dependencies)`. `omarchy-update-system-pkgs-when-conflicted` retries only for `unresolvable package conflicts detected` and `exists in filesystem` errors, so an IgnorePkg dependency clash ends the update with the red "Something went wrong during the update!" banner and nothing is upgraded. Fix the hold (step 2 or 3) and run `omarchy update` again. Afterwards:
```bash
pacman -Qu                          # anything still pending? [ignored] marks a hold
```

**Verify.** `sudo pacman -Syu` reports "there is nothing to do" with no `ignoring package upgrade` warnings. `grep -nE '^\s*(IgnorePkg|IgnoreGroup)' /etc/pacman.conf` returns nothing uncommented. `pacman -Qu` prints nothing.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://man.archlinux.org/man/pacman.conf.5> · <https://wiki.archlinux.org/title/System_maintenance> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/doc/pacman.conf.5.asciidoc> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/remove.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/callback.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/util.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/query.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/conf.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/sync.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/sync.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/log.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/add.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/error.c> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-pacman>

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

> **Audit corrected this record.** The cited news item is real and is the right one: https://archlinux.org/news/linux-firmware-2025061312fe085f-5-upgrade-requires-manual-intervention/ (2025-06-21, Jan Alexander Steffens), listed on https://archlinux.org/news/ and fetched as HTML. It confirms the split in 20250613.12fe085f-5, the 20250508.788aadc8-2 or earlier floor, the four ad103 to ad107 error lines verbatim, and the two-command remedy, so symptom and cause hold. The split is current on this machine: pacman -Q shows linux-firmware 20260810-2 as an empty package whose Depends On lists the ten vendor packages, pacman -Qii linux-firmware shows Required By none and Optional For linux, and ls -l /usr/lib/firmware/nvidia/ shows ad103, ad104, ad106 and ad107 as symlinks to ad102 owned by linux-firmware-nvidia, which is the layout change that makes pacman abort. The fix is wrong for Omarchy 4. Read on this machine, /usr/share/libalpm/hooks/00-omarchy-update-guard.hook fires on Operation = Upgrade, PreTransaction, AbortOnFail, and /usr/bin/omarchy-update-pacman-guard exits 1 whenever the pacman command line carries both S and u unless OMARCHY_ALLOW_DIRECT_PACMAN=1 or OMARCHY_UPDATE_PACMAN=1 is set, so the second command, sudo pacman -Syu linux-firmware, is refused on a machine that has anything else to upgrade, which by definition this one has. The first command, pacman -Rdd, is a Remove operation the hook never triggers on, so it passes. Routing the second step through omarchy update instead would leave the machine with no firmware, because nothing requires linux-firmware and a plain -Syu does not reinstall a removed optional dependency. The manual mkinitcpio -P is redundant on both platforms (the initramfs hook, on Omarchy /etc/pacman.d/hooks/90-mkinitcpio-install.hook from limine-mkinitcpio-hook 1.37.1-1, triggers on usr/lib/firmware/* and runs limine-mkinitcpio-install) and on Omarchy 4 it is the wrong command: /usr/local/bin/mkinitcpio wraps it and warns that -P does not update Limine boot entries, offering limine-mkinitcpio. This record is a duplicate of linux-firmware-split-exists-in-filesystem in boot-kernel, corrected on 2026-09-06 with the same news item, the same four symptom lines, the same cause and the same Omarchy 4 fix. The nvidia subpackage is not a distinct problem: the news item names linux-firmware-nvidia as the only package that conflicts, so every hit of the split looks exactly like this one. Reconcile rather than reject: the problem is real, but the corpus should carry one record for it, or this pacman-aur entry should point at the boot-kernel one. The remedy itself was not exercised, since no machine here has a pre-split linux-firmware to upgrade from.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `pacman -Rdd` removes the package with no dependency checks. Between the two commands you have NO firmware installed. If you reboot or lose power in that window the machine may come up with no Wi-Fi, no GPU acceleration, or fail to boot. Run both commands back to back.

**Fix.**

Run the two commands from the Arch news item back to back. Do not reboot between them.

**Plain Arch / EndeavourOS / CachyOS:**

```bash
sudo pacman -Rdd linux-firmware
sudo pacman -Syu linux-firmware
```

**Omarchy 4:** `pacman -Rdd` is a Remove operation and passes Omarchy's pacman guard untouched, but `pacman -Syu` carries both `-S` and `-u`, so `/usr/bin/omarchy-update-pacman-guard` aborts it. Bypass the guard for that one transaction and name the package explicitly. Nothing depends on `linux-firmware` (the kernel lists it only as an optional dependency), so an `omarchy update` after the removal would finish with no firmware installed:

```bash
sudo pacman -Rdd linux-firmware
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu linux-firmware
```

The mkinitcpio pacman hook triggers on `usr/lib/firmware/*`, so the initramfs (on Omarchy 4, the Limine UKI) is rebuilt inside the same transaction. Look for `Updating linux initcpios...` in the output. Only if that line is missing, rebuild by hand:

```bash
sudo mkinitcpio -P          # Arch / EndeavourOS / CachyOS
sudo limine-mkinitcpio      # Omarchy 4: mkinitcpio -P alone does not update the Limine UKI
```

**Verify.** `pacman -Q | grep linux-firmware` lists the new split packages, and `ls /usr/lib/firmware/nvidia/` is populated. Reboot and confirm the GPU/Wi-Fi still initialise.

Sources: <https://archlinux.org/news/linux-firmware-2025061312fe085f-5-upgrade-requires-manual-intervention/> · <https://archlinux.org/news/> · <https://wiki.archlinux.org/title/Pacman> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pacman-guard> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-keyring>

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

> **Audit corrected this record.** The cause is verified exactly: default/pacman/mirrorlist-stable in master contains the single line `Server = https://stable-mirror.omarchy.org/$repo/os/$arch`, and pacman-stable.conf carries `[omarchy] / SigLevel = Optional TrustAll / Server = https://pkgs.omarchy.org/stable/$arch`. What is missing is the consequence: Omarchy's stable channel is a pinned snapshot, so repointing core/extra/multilib at rolling Arch mirrors pulls packages *newer* than the snapshot the [omarchy] repo was built against, and the restore step (`omarchy-refresh-pacman stable`, which really does run `pacman -Syyuu --noconfirm`) then has to downgrade them all again, a messy state to land in for what is often a transient CDN error. The fix also needs -Syy after a mirror change, and -uu should not be used on the way out.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Running Omarchy packages against pure Arch mirrors mixes epochs: `omarchy-refresh-pacman` finishes with `pacman -Syyuu`, which will force-DOWNGRADE anything newer than Omarchy's mirror offers. Snapshot first (`omarchy-snapshot create`) if you have snapper/limine set up. Disabling the `[omarchy]` repo while installed omarchy-* packages remain will also make them show as orphaned/foreign until you re-enable it.

**Fix.**

A TLS 'unexpected eof' or a one-off 404 is usually transient. Retry once before changing any config:

```bash
sudo pacman -Syu
```

Only if the outage persists, temporarily point core/extra/multilib at official Arch mirrors. **Understand the trade-off first:** Omarchy's stable channel is a pinned snapshot. Rolling Arch mirrors are ahead of it, so this pulls packages newer than the ones the `[omarchy]` repo was built against, and restoring will have to downgrade them. Treat it as a short-lived workaround.

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

This copies `/etc/pacman.conf` and `/etc/pacman.d/mirrorlist` to `.bak` (overwriting any previous `.bak`), rewrites both from Omarchy defaults, then runs `pacman -Syyuu`. The `-uu` is what downgrades anything you pulled ahead of the snapshot, so expect a large transaction and read it before confirming.

**Verify.** `sudo pacman -Syu` completes with no retrieval errors. After `omarchy-refresh-pacman stable`, `grep Server /etc/pacman.d/mirrorlist` shows stable-mirror.omarchy.org again.

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
On Omarchy 4 `omarchy update` prints those pacman error lines and then, for the conflict case only, `A package conflict stopped this upgrade. Running it again so you can answer:` or `This upgrade needs an answer. Run omarchy update interactively to give it.` A provider question never shows up in `omarchy update` at all: pacman answers it with the default and carries on.

**Cause.** Two packages `Provides` the same virtual name (`jack`, `pipewire-session-manager`, `libjack.so`) and pacman will not keep both. pacman asks three different questions here, and `--noconfirm` answers each with its default:

- **Conflict** (`X and Y are in conflict. Remove Y? [y/N]`): default **No**. Under `--noconfirm` pacman answers No and aborts the whole transaction with `unresolvable package conflicts detected`, so one retired package blocks every other upgrade behind it. Answering **y** on the wrong prompt makes pacman drop the conflicting package *and everything that depends on it*, which is the classic way to remove half a desktop with one keystroke.
- **Provider** (`There are 2 providers available for jack ... Enter a number (default=1)`): default **1**, the first provider in repository order then alphabetical order. Under `--noconfirm` pacman takes it silently, so a script can install `jack2` where you wanted `pipewire-jack` and nothing reports it. pacman only asks when no provider is installed yet, which is why this prompt is rare on an existing desktop and common on a fresh install or after a removal.
- **Replace** (`Replace X with extra/Y? [Y/n]`): default **Yes**. This is the repository telling you a package was renamed or absorbed. It is not a conflict, and accepting it is the normal path.

Omarchy 4 runs pacman non-interactively in two places: `omarchy-update-system-pkgs` runs `pacman -Syu --noconfirm`, and `omarchy-pkg-add` runs `pacman -S --noconfirm --needed`. So on Omarchy a conflict stops the upgrade and gets handed back to you, a provider question gets the first provider, and a replace goes through. pacman also has an undocumented `--ask <bitmask>` that flips the default for the question types in the mask (`4` is the conflict question), which is how a script can say Yes without answering every other prompt.

> **Audit corrected this record.** Checked against pacman 7.1.0 source at tag v7.1.0 (src/pacman/callback.c, src/pacman/util.c, lib/libalpm/deps.c, lib/libalpm/alpm.h), the pacman(8) man page on this machine, /usr/share/omarchy/bin/omarchy-update, omarchy-update-system-pkgs, omarchy-update-system-pkgs-when-conflicted, omarchy-update-pacman-guard and omarchy-pkg-add, and the Arch package JSON for pipewire-jack, jack2 and pipewire-media-session. What held: under --noconfirm question() returns its preset, the conflict question uses noyes() so the preset is No and the transaction aborts with unresolvable package conflicts detected, which is exactly what the Omarchy handler greps for, and both quoted Omarchy strings are verbatim. The handler re-runs pacman without --noconfirm only when stdin and stderr are terminals and OMARCHY_UPDATE_UNATTENDED is unset. pipewire-jack 1:1.6.8-1 provides jack and the three libjack sonames and conflicts jack, jack2 and pipewire-jack-client. pacman-contrib is in omarchy-base.packages and installed here. What was wrong: the record treats the provider prompt and the conflict prompt as the same failure, and they are not. select_question() under --noconfirm returns the default 1, so inside omarchy update (and omarchy-pkg-add, which runs pacman -S --noconfirm --needed) a provider question is answered silently with the first provider in repo order then alphabetical order (jack2 sorts before pipewire-jack), nothing aborts, and the Omarchy conflict handler never sees it. deps.c also returns early without asking when a provider is already installed, which is why this prompt is rare on an installed desktop. The Replace X with Y? question uses yesno(), so it defaults to Yes under --noconfirm and is not a conflict at all. pacman(8) documents --noconfirm and --confirm but has no --ask entry: --ask <bitmask> exists only in pacman.c and flips the default for the question types in the mask (4 is ALPM_QUESTION_CONFLICT_PKG), so it belongs in the record as the way to script a Yes. The fix's sudo pacman -Syu pipewire-jack and the verify's sudo pacman -Syu are both stopped by omarchy-update-pacman-guard on Omarchy 4, which aborts whenever the command line carries both -S and -u without OMARCHY_ALLOW_DIRECT_PACMAN=1 or OMARCHY_UPDATE_PACMAN=1. The symptom said Omarchy shows its message instead of pacman's lines, but omarchy-update-system-pkgs replays the captured stderr first (cat "$errors" >&2), so pacman's error lines come first and the Omarchy line after. omarchy update -y never re-runs interactively, which the record did not say. pipewire-media-session is still in extra (1:0.4.3-1, described as deprecated), so the earlier audit note calling it dropped was wrong and the wireplumber advice stands. Omarchy installs wireplumber, so that prompt does not fire on a stock install. NOT exercised: no conflict was induced, no upgrade was run, and the interactive re-run was not observed.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Running `pacman -R jack2` (or worse, `-Rns` / `-Rdd`) *before* the replacement is installed cascades: it takes ffmpeg, mpv, fluidsynth and everything downstream, which on a desktop can strip your browser, media player and parts of the compositor's dependency tree. Always let the conflict be resolved inside a single `-S`/`-Syu` transaction so the replacement goes in as the old package comes out. `-Rdd` skips dependency checks entirely and leaves an unbootable or unusable system. Never use it to "win" a conflict prompt.

**Fix.**

**Never answer blind. In a second terminal, find out what depends on the package being removed:**

```bash
sudo pacman -S --needed pacman-contrib    # already installed on Omarchy 4
pactree -r jack2                          # what needs it
pacman -Qi jack2 | grep -i 'required by'
```

**The answers that hold in practice:**

- `pipewire-jack` vs `jack2`: answer **y** on any modern PipeWire desktop (Omarchy, Arch, EndeavourOS, CachyOS). `pipewire-jack` provides `jack libjack.so libjackserver.so libjacknet.so`, so ffmpeg/mpv/fluidsynth keep working. Keep `jack2` **only** if you deliberately run a real JACK server (Ardour with jackd, Bitwig).
- `wireplumber` vs `pipewire-media-session`: choose **wireplumber**. `pipewire-media-session` is still in the repos but marked deprecated, and Omarchy installs `wireplumber`.
- A provider prompt offering an AUR `-git` variant of something in the repos: pick the repo one unless you installed the `-git` on purpose.
- `Replace X with extra/Y? [Y/n]`: answer **y**. That is a rename, not a conflict.

**Make the choice explicitly instead of answering a prompt, in one transaction:**

```bash
# plain Arch
sudo pacman -Syu pipewire-jack      # pacman removes jack2 as part of the same upgrade
sudo pacman -Syu wireplumber

# Omarchy 4: the pacman guard stops any command carrying both -S and -u
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu pipewire-jack
```

**Omarchy 4, conflict case:** the `--noconfirm` upgrade answers No and stops. `omarchy update` detects `unresolvable package conflicts detected` and re-runs pacman without `--noconfirm` so you get the `[y/N]` prompt, but only when stdin and stderr are a real terminal and you did not pass `-y`. Run it from an actual terminal:

```bash
omarchy update
```
`omarchy update -y` promises not to ask and prints `This upgrade needs an answer. Run omarchy update interactively to give it.` instead.

**Omarchy 4, provider case:** `omarchy update` and `omarchy pkg add` take provider 1 without telling you. If a fresh install or a script pulled in `jack2`, swap it in one transaction with the `env OMARCHY_ALLOW_DIRECT_PACMAN=1` command above and answer **y** to removing `jack2`.

**Read the removal list before pressing y.** If the `Packages (n) To remove:` block is longer than a line or two, answer N and investigate first.

**Verify.** `sudo pacman -Syu` completes with no conflict prompt remaining and reports "there is nothing to do" on a second run. For the audio case: `pacman -Q pipewire-jack` succeeds, `pactree -r jack2` errors with "package not found", `wpctl status` still lists your sinks and sources, and audio still plays.

Sources: <https://forum.endeavouros.com/t/pipewire-jack-and-jack2-are-in-conflict-jack/22882> · <https://wiki.archlinux.org/title/PipeWire> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-system-pkgs-when-conflicted> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-system-pkgs> · <https://wiki.archlinux.org/title/Pacman> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/src/pacman/callback.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/src/pacman/util.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/lib/libalpm/deps.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/v7.1.0/lib/libalpm/alpm.h> · <https://archlinux.org/packages/extra/x86_64/pipewire-jack/> · <https://archlinux.org/packages/extra/x86_64/jack2/> · <https://archlinux.org/packages/extra/x86_64/pipewire-media-session/>

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

**Cause.** Every unofficial repository is signed by its own key, which lives in that project's own keyring package (`chaotic-keyring`, `cachyos-keyring`, `omarchy-keyring`, `archlinuxcn-keyring`, `alhp-keyring`), never in `archlinux-keyring`. Until that key is both **imported** and **locally signed**, pacman under the default `SigLevel = Required DatabaseOptional` refuses the repo. The same error also appears when a project rotates its key or lets a signing subkey expire (CachyOS's `882DCFE4…8DB35A47` had an encryption subkey expire and shipped a stale `cachyos-keyring` for over a year) and your installed keyring package predates the rotation.

> **Audit corrected this record.** The cause is correct and the key material is verified. Chaotic-AUR's key 3056513887B78AEB matches the upstream installer script (`sudo pacman-key --recv-key 3056513887B78AEB --keyserver hkp://keyserver.ubuntu.com:80` / `--lsign-key 3056513887B78AEB`). CachyOS fingerprint 882DCFE48E2051D48E2562ABF3B607488DB35A47 is confirmed as the DB signing key, along with the expired-subkey story behind the 'signature ... is invalid' variant. The Omarchy block is exactly right: bin/omarchy-update-keyring uses fingerprint 40DFB630FF42BCFFB047046CF0134EE680CAC571 with `--keyserver keys.openpgp.org`, then lsign, then installs omarchy-keyring, and `omarchy-update-keyring` is the correct command to run (it invokes sudo internally). The SigLevel claim is right too: Omarchy's default/pacman/pacman-stable.conf carries the global `SigLevel = Required DatabaseOptional`, and per pacman.conf(5) a repo section's own SigLevel overrides it. Verifying the fingerprint before lsign is the correct and often-omitted safety step.

Two commands are the wrong form and both create partial-upgrade exposure. `sudo pacman -Sy cachyos-keyring` refreshes the databases and then installs a single package against them, leaving every other installed package at a version older than the synced databases, which is the textbook partial upgrade. And the closing `sudo pacman -Syy` refreshes databases with no upgrade at all, which leaves the system parked in exactly that state until the user happens to run -Syu. -Syy is also the force-refresh form, needed only after a mirror change, so it re-downloads every database for no reason here. The keyring exception people cite (Omarchy's own script does `pacman -Sy`) only holds when a full `-Syu` follows immediately in the same script, which is not what a user copy-pasting these lines will do.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** `SigLevel = Never` or `TrustAll` on a third-party repo disables signature checking for that repo completely. You are then trusting whatever any mirror serves you, with root install rights. Never set it globally and never as a permanent fix. Do not use `pacman-key --refresh-keys` as a shotgun: it is slow, frequently fails, and can pull in revoked or superseded key material. Do not `rm -rf /etc/pacman.d/gnupg` unless you are prepared to re-run `pacman-key --init && pacman-key --populate` and re-import every third-party key, including on a machine you may not be able to update afterwards.

**Fix.**

Everything is unchanged except the two commands below.

**CachyOS** (the expired/rotated admin key, the `is invalid` variant): install the keyring as part of a full upgrade, not on its own:
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
Only if pacman still reports a stale or corrupt database do you need the force-refresh form, and it must still carry the `u`:
```bash
sudo pacman -Syyu
```
On Omarchy, run `omarchy update` instead of either.

**Verify.** `sudo pacman -Syy` syncs every database with no signature error. `pacman-key --list-keys <KEYID>` shows the key present with a local signature. `pacman -Sl chaotic-aur | head` (or `pacman -Sl omarchy | head`) lists packages.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://wiki.archlinux.org/title/Unofficial_user_repositories> · <https://github.com/SharafatKarim/chaotic-AUR-installer/blob/main/install.bash> · <https://github.com/CachyOS/distribution/issues/443> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-keyring> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf>

---

## Fix yay or paru dying on a libalpm.so version mismatch

`yay-paru-libalpm-so-mismatch` · severity: **high** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Right after a pacman upgrade, every AUR helper invocation dies:
```
yay: error while loading shared libraries: libalpm.so.15: cannot open shared object file: No such file or directory
```
(or `libalpm.so.14` or `libalpm.so.16`, the number moves). `paru` shows the same. This is a yay 12.5.x or older, or a paru, problem: yay 12.6.0 and later, including the yay 13.0.1 Omarchy 4 ships, load libalpm at runtime and do not fail this way. On Omarchy, if any AUR package is installed (`pacman -Qem` prints something), the "Update AUR packages" step of `omarchy update` prints the loader error and the update carries on without touching the AUR packages, because `omarchy-update-aur-pkgs` ends with an `echo` and exits 0 whatever yay returned. With no AUR packages installed that step never runs yay, so the update completes and only direct yay use fails.

**Cause.** yay up to 12.5.x was linked at build time against a specific libalpm soname (cgo), and paru still is (its AUR PKGBUILD depends on `libalpm.so>=14`). When pacman bumps that soname, as pacman 7.1.0 did on 2025-12-13 by moving to `libalpm.so=16-64`, a helper built against the old one cannot start, and because it is the tool you would use to rebuild itself, you are stuck. For paru the wait was for the Rust `alpm` crate to support libalpm 16 (archlinux/alpm.rs issue 59). For yay the wait was for a rebuilt release. On Omarchy 3 in December 2025 the yay in Omarchy's own repo was still built against `libalpm.so.15` while pacman came from Arch core with `.16`, which is what omacom/omarchy issues 3877 and 3902 record.

Since yay 12.6.0 (2026-06-07) yay no longer links libalpm at all. It loads `libalpm.so.16` at runtime through dyalpm and falls back to the unversioned `/usr/lib/libalpm.so` that the pacman package always installs, so `ldd /usr/bin/yay` lists only libc. Omarchy 4 ships yay 13.0.1 from its `[omarchy]` repo, and that build cannot produce this loader error. If you see it on Omarchy 4, the machine is still running an older yay or you are running paru.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation: yay 13.0.1-1 is installed from the [omarchy] repo (pacman -Si yay reports Repository: omarchy, pacman -Sl omarchy lists yay and yay-debug, and yay is line 147 of /usr/share/omarchy/install/omarchy-base.packages), paru is not installed, and pacman 7.1.0.r9.g54d9411-2 ships libalpm.so.16 and libalpm.so.16.0.1 plus the unversioned /usr/lib/libalpm.so. ldd /usr/bin/yay lists only libc: yay 12.6.0 (2026-06-07) switched to dyalpm, which dlopens libalpm.so.16 and falls back to libalpm.so (Jguer/dyalpm internal/lib/loader.go at v0.1.4, the version yay 13.0.1's go.mod pins), so the record's loader error cannot come from the yay Omarchy 4 ships. The error is real for yay 12.5.x and earlier and for paru, whose AUR PKGBUILD still depends on libalpm.so>=14. The cited issues 3877 and 3902 (both December 2025, Omarchy 3.2.3, yay 12.5.x, both closed) support the symptom and show it was Omarchy's own repo shipping a yay built against libalpm.so.15 while core moved to .16, which the cause did not say. alpm.rs issue 59 is about paru only, so 'a lag against alpm.rs' is the wrong cause for yay. The fix opened with sudo pacman -Syu, which the ALPM guard (/usr/bin/omarchy-update-pacman-guard, aborts on -S plus -u without OMARCHY_UPDATE_PACMAN=1 or OMARCHY_ALLOW_DIRECT_PACMAN=1) blocks on Omarchy 4. The original claim that omarchy-update aborts at 'Update AUR packages' was accepted here at first and is wrong: /usr/share/omarchy/bin/omarchy-update-aur-pkgs runs yay inside an if-body whose last command is echo, so the script exits 0 whatever yay returned and omarchy-update continues. Corrected 2026-09-07 after a sibling audit (aur-package-deleted-merged-or-renamed) read the script. The symptom now says the AUR step prints the error and is skipped over. The danger's claim that Omarchy replaces a hand-built yay on the next update is only true for the yay package name, and omarchy-reinstall-pkgs conflicts with yay-bin. The omarchy-pkgs yay PKGBUILD is byte-identical to the AUR one. Not exercised: I did not break libalpm or rebuild yay or paru here, and I did not test what yay 13 prints if libalpm.so.16 is absent.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** A widely copied workaround is `ln -s /usr/lib/libalpm.so.16 /usr/lib/libalpm.so.15`. That makes the helper run against an ABI-incompatible library and can corrupt the pacman database when it writes to it. If you must use it to bootstrap, remove both symlinks immediately after rebuilding: `sudo unlink /usr/lib/libalpm.so.15 && sudo unlink /usr/lib/libalpm.so.15.0.0`. On Omarchy, a `yay` built from the AUR PKGBUILD has the same package name and version as the `[omarchy]` repo one, so the next repo version bump upgrades it in place. `yay-bin` does not get that treatment: it stays a foreign package, `omarchy update` hands it to `yay -Sua`, and `omarchy-reinstall-pkgs` fails on the `yay` versus `yay-bin` conflict because it runs pacman with `--noconfirm`.

**Fix.**

First confirm which helper and which build you have:

```bash
pacman -Qi yay | grep -E '^(Version|Packager)'
pacman -Ql pacman | grep libalpm.so
ldd /usr/bin/yay | grep alpm || echo "yay loads libalpm at runtime"
```

**Omarchy 4.** yay comes from the `[omarchy]` repo, not the AUR, and the current build loads libalpm at runtime. Bring the system current through the supported path, which also refreshes the repo's yay:

```bash
omarchy update
```

If yay is still an older build that `ldd` shows linked to a missing `libalpm.so.N`, reinstall the repo package (no `-u`, so the update guard does not fire):

```bash
sudo pacman -S yay
```

Only if the repo build is also broken, build the AUR `yay` package by hand. Do not use `pacman -Syu` here: the ALPM guard aborts it. Install the build tools with a plain `-S` after `omarchy update` has already synced the databases:

```bash
sudo pacman -S --needed git base-devel go
cd /tmp && rm -rf yay
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
```

Prefer `yay` over `yay-bin` on Omarchy so the package name matches the repo one. Then re-run the update:

```bash
omarchy update
```

**Plain Arch.** Rebuild the helper from the AUR with makepkg, which needs no AUR helper:

```bash
sudo pacman -Syu --needed git base-devel go
cd /tmp && rm -rf yay
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
```

Or skip compilation with the prebuilt package:

```bash
cd /tmp && rm -rf yay-bin
git clone https://aur.archlinux.org/yay-bin.git
cd yay-bin
makepkg -si
```

For paru substitute `https://aur.archlinux.org/paru.git` (or `paru-bin.git`). The paru PKGBUILD runs `cargo update alpm alpm-utils` during the build, so it picks up the crate release that matches the installed libalpm.

**Verify.** `yay --version` prints a version instead of the loader error, and `yay -Sua` runs.

Sources: <https://github.com/basecamp/omarchy/issues/3877> · <https://github.com/basecamp/omarchy/issues/3902> · <https://github.com/archlinux/alpm.rs/issues/59> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-update-aur-pkgs> · <https://github.com/omacom/omarchy/issues/3877> · <https://github.com/omacom/omarchy/issues/3902> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-aur-pkgs> · <https://github.com/omacom/omarchy-pkgs/blob/master/pkgbuilds/yay/PKGBUILD> · <https://github.com/omacom/omarchy-pkgs/blob/master/README.md> · <https://github.com/Jguer/yay/releases> · <https://github.com/Jguer/yay/blob/next/go.mod> · <https://github.com/Jguer/dyalpm/blob/v0.1.4/internal/lib/loader.go> · <https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=yay> · <https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=yay-bin> · <https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=paru> · <https://archlinux.org/packages/core/x86_64/pacman/>

---

## Remove the dead [community] repository after 'failed retrieving file community.db'

`community-repo-removed-community-db-404` · severity: **high** · frequency: **occasional** · applies to: `arch`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Every sync stops on the community database, on every mirror in the list:

```
:: Synchronizing package databases...
 core downloading...
 extra downloading...
 community downloading...
error: failed retrieving file 'community.db' from arch.mirror.constant.com : The requested URL returned error: 404
error: failed retrieving file 'community.db' from us.mirrors.cicku.me : The requested URL returned error: 404
error: failed to synchronize all databases (failed to retrieve some files)
```

Nothing was changed on the machine. It just stopped updating one day, usually on a box that had not been updated for a long time or a distro that stopped shipping config updates.

**Cause.** Arch merged [community] into [extra] in 2023 and kept the old repository online but empty. On 2025-03-01 Arch deleted [community], [community-testing], [testing], [testing-debug], [staging] and [staging-debug] from the mirrors. A pacman.conf that still lists any of them now asks every mirror for a file that no longer exists, and pacman aborts the whole sync. The replacement pacman.conf without those sections shipped as /etc/pacman.conf.pacnew with pacman 6.0.2-7, so systems that never merged that .pacnew are the ones that break.

> **Audit corrected this record.** Cause, date and repository list confirmed against the Arch news post of 2025-02-17, which names the six repositories, the 2025-03-01 removal and the .pacnew shipped with pacman>=6.0.2-7. The forum thread carries the exact symptom. Omarchy's pacman-stable.conf was read locally and on the quattro branch: it lists only [core], [extra], [multilib] and [omarchy]. The defect is the Omarchy branch: it says 'delete the section as above', which leads the reader to the plain-Arch `sudo pacman -Syu` that the ALPM guard refuses, and it refers to 'the second command' when the block has one. Read on 4.0.4-1: omarchy-refresh-pacman saves .bak copies, copies the channel's pacman.conf and mirrorlist, runs the pre-refresh-pacman hook, then runs `pacman -Syyuu --noconfirm`, which can downgrade packages as well as upgrade them. The fix now gives a separate Omarchy procedure and states what the refresh actually does. Nothing was run. Second audit confirmed the corrected text: Arch news of 2025-02-17 (retrieved) names the six repositories, the 2025-03-01 removal and the .pacnew shipped with pacman>=6.0.2-7, matching the cause. Forum thread 303841 carries the exact 404 output and the fix of removing [community]. On this machine /etc/pacman.conf and /usr/share/omarchy/default/pacman/pacman-stable.conf list only [core], [extra], [multilib] and [omarchy]. Read /usr/share/omarchy/bin/omarchy-refresh-pacman on 4.0.4-1: it writes /etc/pacman.conf.bak and /etc/pacman.d/mirrorlist.bak, copies the channel files, runs the pre-refresh-pacman hook, then `sudo env OMARCHY_UPDATE_PACMAN=1 pacman -Syyuu --noconfirm`, exactly as the fix and danger say. The ALPM guard (/usr/share/libalpm/hooks/00-omarchy-update-guard.hook, /usr/bin/omarchy-update-pacman-guard) refuses -S with -u, so the Omarchy branch correctly routes through `omarchy update`. Minor: the pacdiff example uses DIFFPROG='nvim -d', which a plain Arch reader may not have installed. Nothing was run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** `omarchy refresh pacman` replaces /etc/pacman.conf and /etc/pacman.d/mirrorlist wholesale, dropping any third-party repositories you added (backups are written to /etc/pacman.conf.bak and /etc/pacman.d/mirrorlist.bak).

**Fix.**

Find the dead sections:

```bash
grep -n -A2 -E '^\[(community|community-testing|testing|testing-debug|staging|staging-debug)\]' /etc/pacman.conf
ls -l /etc/pacman.conf.pacnew 2>/dev/null
```

**Plain Arch, EndeavourOS, Manjaro.** Back up, then delete each matched section header together with its `Include =` line:

```bash
sudo cp /etc/pacman.conf /etc/pacman.conf.bak
sudoedit /etc/pacman.conf
```

Remove blocks like these entirely:

```ini
[community]
Include = /etc/pacman.d/mirrorlist
```

If a `.pacnew` exists, merge it instead of hand-editing, since it carries the other changes you also missed:

```bash
sudo pacman -S --needed pacman-contrib
sudo DIFFPROG='nvim -d' pacdiff
```

Then do a full upgrade, never a bare `-Sy`:

```bash
sudo pacman -Syu
```

**Omarchy 4.** The pacman.conf Omarchy installs (`/usr/share/omarchy/default/pacman/pacman-stable.conf`) lists only `[core]`, `[extra]`, `[multilib]` and `[omarchy]`, so this only happens if an old pacman.conf was restored over it. Either delete the dead sections with the same backup and `sudoedit` steps above and then update through Omarchy (direct `sudo pacman -Syu` is refused by Omarchy's ALPM guard):

```bash
omarchy update
```

or put Omarchy's own file back. This saves `/etc/pacman.conf.bak` and `/etc/pacman.d/mirrorlist.bak`, overwrites both files with the stable channel's copies (dropping every third-party repository you added), then runs `pacman -Syyuu --noconfirm`, which can downgrade packages to the channel's versions as well as upgrade them:

```bash
omarchy refresh pacman
```

**Verify.** `pacman-conf --repo-list` no longer prints `community`, and the next full upgrade synchronizes every database without a 404.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=303841> · <https://archlinux.org/news/cleaning-up-old-repositories/>

---

## Fix 'missing required signature' on repositories that do not sign their databases

`database-signature-required-repo-publishes-none` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** After hardening pacman's `SigLevel`, or after adding a third-party repository with a `SigLevel` line copied from somewhere, syncing fails:

```
error: failed retrieving file 'omarchy.db.sig' from pkgs.omarchy.org : The requested URL returned error: 404
error: failed to synchronize all databases (...)
```

or, when a database is already on disk without its signature:

```
error: omarchy: missing required signature
error: failed to synchronize all databases (invalid or corrupted database (PGP signature))
```

and later `error: database 'core' is not valid (invalid or corrupted database (PGP signature))`. Every repo can fail at once, including core and extra, and refreshing keyrings changes nothing.

**Cause.** `SigLevel = Required` means signatures are required on packages and on databases (pacman.conf(5)). Arch's official repositories sign packages but not databases, which is why the stock line is `SigLevel = Required DatabaseOptional` and why the Arch wiki says that if `Required` is set, `DatabaseOptional` should also be set. When the database level is required, libalpm downloads `<repo>.db.sig` as a mandatory file, so a 404 fails the sync. A database already on disk without its signature fails `_alpm_check_pgp_helper` with `missing required signature`, reported as `invalid or corrupted database (PGP signature)`.

Checked on 2026-10-05 with HEAD requests: `core.db.sig` on an Arch mirror and on Omarchy's `stable-mirror.omarchy.org`, and `omarchy.db.sig` on `pkgs.omarchy.org`, all return 404, while CachyOS's `cachyos.db.sig` returns 200. On Omarchy 4 the [omarchy], [core], [extra] and [multilib] sections carry no `SigLevel` of their own (`pacman-conf -r omarchy SigLevel` prints nothing), so they all inherit the global line, and changing the global line to plain `Required` breaks all four. A `SigLevel` line in a repo section starts from the global value and then overrides it option by option, so a copied `SigLevel = Required` under one repo makes that repo's database required and breaks only that repo.

> **Audit corrected this record.** Mechanism confirmed in libalpm be_sync.c: `download_signature = siglevel & ALPM_SIG_DATABASE` and `signature_optional = siglevel & ALPM_SIG_DATABASE_OPTIONAL`. With database Required, a 404 on `.db.sig` is therefore a hard download error, and signing.c prints `%s: missing required signature` when the siglist is empty and not optional. HEAD requests on 2026-10-05: omarchy.db.sig on pkgs.omarchy.org, core.db.sig on stable-mirror.omarchy.org and on geo.mirror.pkgbuild.com all return 404, and cachyos.db.sig returns 200. On this machine, /etc/pacman.conf line 15 is `SigLevel = Required DatabaseOptional`, and `pacman-conf -r <repo> SigLevel` prints nothing for core, extra, multilib and omarchy. The three templates in /usr/share/omarchy/default/pacman carry the same line, and omarchy-refresh-pacman, which omarchy-channel-set calls, copies them over /etc/pacman.conf. Two errors. pacman.conf(5) says a repo SigLevel starts from the [options] value and later options supplement it, so `SigLevel = PackageRequired` under a repo leaves the database level at whatever the global line says. Under a hardened global `Required`, it fixes nothing. The fix now uses an explicit `Required DatabaseOptional` per repo. The danger says `Optional` and `TrustAll` turn off package signature checking, but pacman.conf(5) says Optional still checks signatures when present and TrustAll still requires the key in the keyring. Cause and danger rewritten. The pre-refresh-pacman hook (~/.config/omarchy/hooks/pre-refresh-pacman.d) is mentioned as the supported way to keep a custom pacman.conf. Not exercised: no sync was run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Fix this by relaxing only the database level. Do not reach for `SigLevel = Never` on a repo, which turns off signature checking for its packages too. `Optional` still checks a signature that is present but accepts unsigned packages, and `TrustAll` accepts signatures from keys in the keyring that are not fully trusted. Both weaken package verification more than this problem needs. Do not follow a bare `pacman -Sy` after editing pacman.conf, because it is a partial upgrade.

**Fix.**

See what each repository is actually asked for:

```bash
pacman-conf SigLevel                       # the global level
for r in $(pacman-conf --repo-list); do echo "[$r] $(pacman-conf -r "$r" SigLevel | tr '\n' ' ')"; done
```

A repo listed with `DatabaseRequired`, or with nothing when the global level shows `DatabaseRequired`, is the one to fix. Restore the stock global line in `/etc/pacman.conf`:

```ini
[options]
SigLevel = Required DatabaseOptional
```

For a third-party repository that signs packages but not its database, spell out both levels in its section. A repo line starts from the global value, so naming only the package level would leave a hardened global database level in force:

```ini
[somerepo]
SigLevel = Required DatabaseOptional
Include = /etc/pacman.d/somerepo-mirrorlist
```

Then sync and upgrade together.

Omarchy 4:

```bash
omarchy update
```

Plain Arch:

```bash
sudo pacman -Syu
```

Omarchy 4 note: `omarchy refresh pacman` and `omarchy channel set` copy `/usr/share/omarchy/default/pacman/pacman-<channel>.conf` over `/etc/pacman.conf` (keeping the old file as `/etc/pacman.conf.bak`), and those templates ship `SigLevel = Required DatabaseOptional`. So a channel switch also undoes a hand-hardened SigLevel, along with any custom repositories. To re-apply your own changes automatically, put a script in `~/.config/omarchy/hooks/pre-refresh-pacman.d/`, which runs after the copy and before the upgrade.

**Verify.** `pacman-conf SigLevel` shows `DatabaseOptional`. `omarchy update` (or `sudo pacman -Syu`) syncs every database with no `missing required signature` and no `.db.sig` 404.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://man.archlinux.org/man/pacman.conf.5> · <https://gitlab.archlinux.org/pacman/pacman/-/blob/master/lib/libalpm/signing.c> · <https://gitlab.archlinux.org/pacman/pacman/-/blob/master/lib/libalpm/be_sync.c>

---

## Roll the whole system back to how it was on a given date

`restore-whole-system-to-earlier-date-ala` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `omarchy`, `systemd-boot`

**Symptom.** "My system is broken after an update from a few weeks ago and I don't know which package did it. I want to go back to how it was on a specific date."

**Cause.** No single package is identifiable as the culprit, so individual downgrades are impractical. The Arch Linux Archive keeps daily snapshots of the Arch repositories, but not of the `[omarchy]` repo. Omarchy 4 takes a Snapper snapshot of the root subvolume before every `omarchy update` and lists the last few as bootable entries in Limine, which rolls back everything at once, including the `[omarchy]` packages.

> **Audit corrected this record.** Checked the Arch wiki Arch Linux Archive page (raw wikitext, 2026-09-06), the live archive, pkgs.omarchy.org, the Omarchy manual page manual/47-system-snapshots.md on the quattro branch, and this Omarchy 4 workstation. What held: the wiki still gives exactly `Server = https://archive.archlinux.org/repos/YYYY/MM/DD/$repo/os/$arch` followed by `pacman -Syyuu`, with archlinux-keyring and ca-certificates first on signature errors and the warning against mixing archive and live mirrors. https://archive.archlinux.org/repos/2026/09/05/ lists core, extra, multilib and the testing and staging repos, and the record's 2026/07/01 date serves core.db (HTTP 200). What was wrong for Omarchy 4: (1) `pacman -Syyuu` carries both -S and -u, so /usr/bin/omarchy-update-pacman-guard (read here, hooked by 00-omarchy-update-guard.hook with AbortOnFail) aborts it. It needs `sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1`, and `omarchy update` is not a substitute because omarchy-update-system-pkgs runs plain `pacman -Syu`, which never downgrades. (2) pkgs.omarchy.org has no archive: /archive/, /repos/, /snapshots/, /old/ and /history/ all return 404, the repo db lists one version per package, and only the current and previous package files are served (omarchy-4.0.2-1 and 4.0.1-1 return 200, 4.0.0-1 returns 404). The `[omarchy]` repo has its own `Server =` line in /etc/pacman.conf rather than the mirrorlist, so the record's recipe rolls core, extra and multilib back while 30 installed packages here (omarchy, omarchy-settings, omarchy-keyring, limine-snapper-sync, limine-mkinitcpio-hook, yay and others) stay built against current Arch. (3) Omarchy's default mirror stable-mirror.omarchy.org reported lastsync 2026-08-25 while the archive reported 2026-09-06, so an archive date is not the same package set Omarchy served on that date. (4) Snapshot rollback is not conditional on Omarchy 4: the omarchy package depends on limine, limine-snapper-sync and snapper, omarchy-update calls `omarchy-snapshot create` before every update with NUMBER_LIMIT=5 in /usr/share/omarchy/default/snapper/root, and /etc/limine-entry-tool.d/omarchy-defaults.conf puts a Snapshots entry in the Limine boot order with MAX_SNAPSHOT_ENTRIES=6. The manual says restore is done by booting the snapshot from Limine and then running `omarchy-snapshot restore` (which is `sudo limine-snapper-restore`, confirmed in /usr/share/omarchy/bin/omarchy-snapshot), and that it restores root but not /home. The fix now leads with that and keeps the archive recipe as the plain Arch branch. (5) The record cited the master branch copy of omarchy-snapshot, which is the Omarchy 3 script (it sets OMARCHY_PATH to ~/.local/share/omarchy). Not exercised: no rollback or restore was run on this machine, and /.snapshots and /boot are not readable without root. Post-merge correction 2026-09-07 by the corpus lint: the rewritten text said `sudo omarchy-snapshot create`, but /usr/share/omarchy/bin/omarchy-snapshot calls sudo itself and reads OMARCHY_PATH, which sudo strips, so it is run as the user.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** This is the highest-risk operation in this list. Mass-downgrading glibc, systemd, the kernel and the bootloader can leave an unbootable system, and the wiki explicitly warns it is unsafe to mix Archive and live mirrors, because a single download failure falls back to a current package and leaves you with mixed epochs. On Omarchy 4 the `[omarchy]` repo cannot be rolled back at all: it has no archive, and the recipe leaves its packages built against libraries newer than the ones you restore, so prefer the Snapper snapshot and treat the archive as the last resort. Downgrades do not undo config-file migrations, so `/etc` may be newer than the binaries, and a snapshot restore leaves `/home` untouched, so `~/.config` and Omarchy's migration markers stay at the newer state. Run `omarchy-snapshot create` or take a full backup before the archive route, keep a live USB ready, and never leave the Archive mirror configured permanently.

**Fix.**

**Omarchy 4: restore the pre-update snapshot.** `omarchy update` runs `omarchy-snapshot create` before it upgrades anything, and Limine lists those snapshots under a **Snapshots** entry in the boot menu. This is the rollback that also covers the `[omarchy]` packages, which the Arch Linux Archive does not hold.

1. Reboot into Limine. If the machine boots straight to the decryption screen, pick Limine from the firmware boot menu first (the manual's *Setup > Direct Boot* toggle removes the direct entry again).
2. Open **Snapshots** and boot the entry dated before the update that broke things. Snapper keeps the last 5 update snapshots, and Limine shows up to 6.
3. Inside the booted snapshot, click the restore notification, or run:

```bash
omarchy-snapshot restore     # runs sudo limine-snapper-restore
```

4. Reboot into the normal entry and confirm with `pacman -Qi linux | grep Version` and `snapper list`.

This restores the root subvolume only. `/home`, including `~/.config` and Omarchy's migration markers in `~/.local/state/omarchy/migrations`, is left as it is. If nothing is listed under Snapshots, no snapshot exists to restore, and only the archive recipe below remains.

**Plain Arch, or an Omarchy install with no usable snapshot: the Arch Linux Archive.** Point core, extra and multilib at a dated snapshot by replacing the mirrorlist:

```bash
sudo cp /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.bak
sudo tee /etc/pacman.d/mirrorlist >/dev/null <<'EOF'
Server = https://archive.archlinux.org/repos/2026/07/01/$repo/os/$arch
EOF
```

Then force the downgrade. `-uu` is what permits downgrades. On Omarchy the update guard aborts any pacman command carrying both `-S` and `-u`, so the bypass variable is required, and `omarchy update` cannot do this because it runs `pacman -Syu` without the second `u`:

```bash
# plain Arch
sudo pacman -Syyuu

# Omarchy 4
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syyuu
```

If signature errors appear, update the keyring and CA bundle from the archive date first, then immediately run the full downgrade again so nothing is left partially upgraded:

```bash
sudo pacman -Sy archlinux-keyring ca-certificates && sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syyuu
```

On Omarchy the `[omarchy]` repo has its own `Server = https://pkgs.omarchy.org/stable/$arch` line in `/etc/pacman.conf` and is not affected by the mirrorlist, so omarchy, omarchy-settings, limine-snapper-sync, limine-mkinitcpio-hook, yay and the other packages from it stay at their current versions, built against the Arch libraries you just rolled back. Expect breakage there. Omarchy's stock mirror (`stable-mirror.omarchy.org`) also lags Arch by days, so an archive date is newer than what Omarchy served on that date.

To return to normal afterwards:

```bash
sudo cp /etc/pacman.d/mirrorlist.bak /etc/pacman.d/mirrorlist
# plain Arch
sudo pacman -Syyu
# Omarchy 4
omarchy update
```

**Verify.** `pacman -Qi linux | grep Version` (and other key packages) show versions from the target date. The system boots and the regression is gone.

Sources: <https://wiki.archlinux.org/title/Arch_Linux_Archive> · <https://wiki.archlinux.org/title/Downgrading_packages> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-snapshot> · <https://archive.archlinux.org/> · <https://archive.archlinux.org/repos/2026/09/05/> · <https://archive.archlinux.org/repos/2026/07/01/core/os/x86_64/core.db> · <https://pkgs.omarchy.org/stable/x86_64/omarchy.db> · <https://pkgs.omarchy.org/stable/x86_64/omarchy-4.0.1-1-any.pkg.tar.zst> · <https://stable-mirror.omarchy.org/lastsync> · <https://github.com/basecamp/omarchy/blob/quattro/manual/47-system-snapshots.md> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-snapshot> · <https://github.com/basecamp/omarchy/blob/quattro/install/config/snapper.sh> · <https://github.com/basecamp/omarchy/blob/quattro/default/snapper/root>

---

## Replace sync databases that pacman reports as 'Unrecognized archive format'

`sync-db-unrecognized-archive-format-html` · severity: **high** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** pacman refuses to read its own repository databases:

```
error: could not open file /var/lib/pacman/sync/core.db: Unrecognized archive format
error: could not open file /var/lib/pacman/sync/extra.db: Unrecognized archive format
```

Deleting `/var/lib/pacman/sync/*` and syncing again can bring the same error straight back. Opening one of the `.db` files shows it is a web page.

**Cause.** The `.db` files are not archives. The mirror, a redirect, a proxy or a captive portal answered the database request with an HTML page (a parking page, a login page, a moved-permanently target), and pacman saved that page as `core.db`. When the database signature is checked first the same fault shows as `GPGME error: No data`, which is a separate record. Here the unsigned database (Arch sets `SigLevel = Required DatabaseOptional`) is opened directly and the archive library rejects it. Re-syncing against the same bad server fetches the same HTML again.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Run a full upgrade after re-syncing. Re-syncing the databases and then installing a single package with `pacman -S` is a partial upgrade.

**Fix.**

Confirm the files are HTML, not compressed data:

```bash
file /var/lib/pacman/sync/*.db
```

A healthy database reads as `gzip compressed data` or `Zstandard compressed data`. `HTML document` confirms this fault. Find the server pacman is using and see what it actually returns:

```bash
pacman-conf -r core | grep Server
curl -IL 'https://<mirror>/core/os/x86_64/core.db'
```

A `301` to an unrelated site, a login page or a `text/html` content type means that server is the problem. Log in to any captive portal, or comment that `Server` line out of `/etc/pacman.d/mirrorlist` (plain Arch) so pacman uses the next one.

Then delete the bad files and do a full sync and upgrade:

```bash
sudo rm -f /var/lib/pacman/sync/*.db /var/lib/pacman/sync/*.db.sig
```

**Omarchy 4:**

```bash
omarchy update
```

**Plain Arch:**

```bash
sudo pacman -Syu
```

On Omarchy 4 the mirrorlist has a single server, `https://stable-mirror.omarchy.org/$repo/os/$arch`, so there is no second mirror to fall back to. If that server is what returns HTML, wait for it to recover rather than editing the mirrorlist, because `omarchy refresh pacman` puts it back.

**Verify.** `file /var/lib/pacman/sync/*.db` reports compressed data for every repository, and `pacman -Ss linux` returns results without the error.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=268183> · <https://wiki.archlinux.org/title/Pacman>

---

## Fix 'GPGME error: General error' caused by an empty DISPLAY variable

`gpgme-general-error-blank-display` · severity: **high** · frequency: **rare** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Every package fails signature verification in one terminal but works in another:

```
error: GPGME error: General error
:: File /var/cache/pacman/pkg/archlinux-keyring-20241015-1-any.pkg.tar.zst is corrupted (invalid or corrupted package (PGP signature)).
Do you want to delete it? [Y/n]
```

`pacman --debug` shows `gpg error: Invalid crypto engine`. Refreshing the keyring, `pacman-key --init` and `--populate` change nothing, and the same command works from a fresh login or a different terminal.

**Cause.** pacman verifies signatures through GPGME, which starts gpg with the caller's environment. When `DISPLAY` is set but empty (`DISPLAY=`), gpg's setup fails and GPGME reports a general error, which pacman presents as a corrupted signature. An unset DISPLAY or any non-empty value works. The empty value usually comes from a shell profile, a terminal multiplexer, or a script that exports DISPLAY from a variable that can be blank. The Arch wiki documents this, and the forum thread reproduced it with `DISPLAY= pacman -S archlinux-keyring`.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Check for an empty-but-set DISPLAY in the shell that runs pacman:

```bash
[[ -v DISPLAY && -z $DISPLAY ]] && echo 'DISPLAY is set but empty'
```

Run pacman without it:

```bash
unset DISPLAY
omarchy update                                  # Omarchy 4
sudo env -u DISPLAY pacman -Syu                  # plain Arch
```

Then find what sets it to empty and fix that, so it does not come back:

```bash
grep -n 'DISPLAY' ~/.bashrc ~/.bash_profile ~/.profile ~/.zshrc ~/.config/uwsm/env* 2>/dev/null
```

Answer `n` to `Do you want to delete it?` while diagnosing. The cached file is fine, and keeping it saves a re-download.

**Verify.** `env | grep '^DISPLAY='` shows no empty assignment in the shell you update from, and an upgrade passes the `checking package integrity` step.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://bbs.archlinux.org/viewtopic.php?pid=2204786> · <https://raw.githubusercontent.com/sudo-project/sudo/main/plugins/sudoers/env.c>

---

## Unwedge an update blocked by thousands of '/usr/lib/modules/<kver>/... exists in filesystem'

`kernel-modules-hook-unowned-tree-exists-in-filesystem` · severity: **high** · frequency: **rare** · applies to: `arch`, `desktop`, `kernel-modules-hook`, `laptop`, `limine`, `omarchy`

**Symptom.** `omarchy update` (or `pacman -Syu`) aborts before installing anything, with thousands of conflict lines, all inside one kernel version's module directory:

```
error: failed to commit transaction (conflicting files)
linux: /usr/lib/modules/7.1.9-arch1-2/kernel/... exists in filesystem
linux: /usr/lib/modules/7.1.9-arch1-2/modules.order exists in filesystem
...
Errors occurred, no packages were upgraded.
```

Omarchy prints only `Something went wrong during the update!`. Every later update fails the same way until something changes.

**Cause.** Omarchy installs `kernel-modules-hook`. Its pre and post transaction hooks save the running kernel's module tree before a kernel package changes and copy it back afterwards, so a running system keeps working modules. When the kernel package is downgraded while that kernel is running (a channel switch or a release migration can do this), the hook restores the running version's whole tree, which now belongs to no package. If the repositories later offer that same kernel version again and you have not rebooted, pacman's file conflict check sees every file of the package already on disk, unowned, and refuses. The check runs before any PreTransaction hook, so the hook never gets the chance to move the tree. The hook's `linux-modules-cleanup.service`, which runs at boot, deliberately skips the running kernel's tree. Omarchy's conflict handler (`omarchy-update-system-pkgs-when-conflicted` on 4.0.4) only clears unowned paths reported against the `omarchy` packages, so it does not clear this one. Upstream issue #9142 and its fix PR #9285 were still open on 2026-10-04.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** `--overwrite` replaces files without asking. Use it only after confirming every conflict is under `/usr/lib/modules/$(uname -r)/` and that path is unowned. A wider glob can overwrite files that belong to another package. Running pacman directly with OMARCHY_ALLOW_DIRECT_PACMAN=1 skips Omarchy's snapshot, keyring and migration steps, which is why `omarchy update` is run immediately afterwards.

**Fix.**

Confirm it is this case: every conflict is under the running kernel's directory and that directory is unowned.

```bash
uname -r
pacman -Qo /usr/lib/modules/$(uname -r)
grep 'exists in filesystem' /tmp/omarchy-update.log | grep -vc "/usr/lib/modules/$(uname -r)/"
```

`No package owns` from the second command and `0` from the third mean it matches. (`/tmp/omarchy-update.log` is Omarchy's transcript. On plain Arch, read the pacman output.)

**Option 1, preferred: reboot first.** You boot the kernel that is actually installed, `linux-modules-cleanup.service` moves the now non-running unowned tree into `/usr/lib/modules/.old/` (a tmpfiles rule purges it after 4 weeks), and the update goes through:

```bash
systemctl reboot
# after logging back in
omarchy update          # Omarchy 4
sudo pacman -Syu        # plain Arch
```

**Option 2, no reboot.** Let pacman take ownership of that one tree in a full upgrade. Scope the overwrite to the running kernel's directory only:

```bash
# Omarchy 4: one guarded bypass, then let omarchy update run its remaining steps
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu --overwrite "/usr/lib/modules/$(uname -r)/*"
omarchy update

# plain Arch with kernel-modules-hook
sudo pacman -Syu --overwrite "/usr/lib/modules/$(uname -r)/*"
```

**Verify.** `pacman -Qo /usr/lib/modules/$(uname -r)` names the kernel package, and `omarchy update` (or `pacman -Syu`) completes with no conflicting files.

Sources: <https://github.com/omacom/omarchy/issues/9142> · <https://github.com/omacom/omarchy/pull/9285> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-system-pkgs-when-conflicted>

---

## Import the key an AUR build needs when signature verification fails

`aur-pgp-signature-could-not-be-verified` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** A `makepkg`/`yay`/`paru` build stops at the source verification stage:
```
==> Verifying source file signatures with gpg...
    foo-1.2.tar.xz ... FAILED (unknown public key ABCDEF0123456789)
==> ERROR: One or more PGP signatures could not be verified!
```

**Cause.** makepkg verifies upstream release signatures against YOUR user keyring (~/.gnupg), not pacman's keyring, so this is unrelated to archlinux-keyring. With plain `makepkg` or `paru` the upstream developer's public key is simply not in that keyring. With `yay` (13.x, the helper Omarchy 4 installs) the story is different: `pgpfetch` is on by default, so before running makepkg yay checks every key in the PKGBUILD's `validpgpkeys` with `gpg --list-keys` and offers to `gpg --recv-keys` the missing ones. Omarchy's own AUR commands (`omarchy-pkg-aur-install`, `omarchy-pkg-aur-add`, `omarchy-update-aur-pkgs`) run yay with `--noconfirm`, which answers that prompt yes, so on that path a missing key is fetched silently and the usual failure is yay's `problem importing keys` (keyserver unreachable, or the key is not on it) before makepkg starts. The makepkg message in the symptom appears under yay only when the key was imported and still does not verify the tarball, or when you ran makepkg yourself.

> **Audit corrected this record.** Checked the Makepkg wiki (Signature checking: makepkg uses the user keyring, validpgpkeys, keys/pgp/ subdirectory, --skippgpcheck) and the AUR wiki FAQ entry, and both support the cause and the makepkg parts of the fix. Two things did not hold. First, the fallback keyserver in the fix is hkps://keyserver.ubuntu.com, which is the built-in default of the gnupg 2.4.9-3 installed here (confirmed on this machine with gpgconf --list-options dirmngr and man dirmngr, which says dirmngr uses keyserver.ubuntu.com when none is configured), so the line labelled 'if the default keyserver is unreachable' retries the same server. The GnuPG wiki gives hkps://keys.openpgp.org as the temporary alternative and puts the permanent keyserver line in ~/.gnupg/dirmngr.conf, not gpg.conf. Second, the record ignores what yay does on Omarchy. Read on this machine: /usr/share/omarchy/bin/omarchy-pkg-aur-install, omarchy-pkg-aur-add and omarchy-update-aur-pkgs all run yay with --noconfirm, and yay 13.0.1-1 (installed) ships pgpfetch true and gpgflags empty (yay -Pg). In the v13.0.1 source (pkg/sync/sync.go, pkg/sync/srcinfo/pgp/keys.go, pkg/text/input.go) yay runs gpg --list-keys on every validpgpkeys entry before makepkg and, when --noconfirm is set, ContinueTask returns the preset true so gpg --recv-keys runs without asking. On the Omarchy path a missing key is therefore fetched silently, and the failure a user sees is yay's 'problem importing keys' before makepkg starts, unless the key was imported and still does not verify the tarball, which is the only way the record's makepkg message appears under yay. A grep of every non-test .go file at v13.0.1 found PGPFetch set by the config parser and read nowhere else, so --nopgpfetch likely does not disable the check in yay 13.0.1 (likely, not exercised). Also confirmed: yay's man page documents --mflags with the exact example yay -S foo --mflags "--skipchecksums --skippgpcheck", and yay's clone dir here is ~/.cache/yay (buildDir), so the keys/pgp/ file lives under ~/.cache/yay/foo/. Not exercised: no build was run and no key was fetched on this machine, and paru is not installed here.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `--skippgpcheck` disables the only check that the upstream tarball is genuinely from the developer. Importing a key ID you found in a random comment rather than in the PKGBUILD's validpgpkeys array defeats the purpose entirely.

**Fix.**

Read the PKGBUILD's `validpgpkeys` array to get the exact key ID, then import it. gnupg 2.4 already defaults to `hkps://keyserver.ubuntu.com`, so name a different server when retrying:

```bash
grep validpgpkeys PKGBUILD
gpg --recv-keys ABCDEF0123456789
# if the default keyserver (keyserver.ubuntu.com) fails or lacks the key:
gpg --keyserver hkps://keys.openpgp.org --recv-keys ABCDEF0123456789
```

To change the keyserver permanently, put it in `~/.gnupg/dirmngr.conf` (not `gpg.conf`):

```
keyserver hkps://keys.openpgp.org
```

Some PKGBUILDs ship the key in the repo under `keys/pgp/`, named by full fingerprint. Import it from there instead. With yay the clone lives in `~/.cache/yay/<pkg>/`, with paru in `~/.cache/paru/clone/<pkg>/`:

```bash
gpg --import keys/pgp/*.asc
```

Then rebuild:

```bash
makepkg -si          # or: yay -S foo
```

Omarchy 4: `omarchy-pkg-aur-install` and `omarchy-pkg-aur-add` run `yay -S --noconfirm`, and yay's `pgpfetch` default makes it run `gpg --recv-keys` for missing `validpgpkeys` without asking. If that step fails you see `problem importing keys` from yay rather than the makepkg error. Import the key by hand as above, or with the alternative keyserver, then rerun the Omarchy command.

Only if you have independently verified the source and accept the risk, skip the check for one build:

```bash
makepkg -si --skippgpcheck
# yay equivalent:
yay -S foo --mflags --skippgpcheck
```

**Verify.** `gpg --list-keys ABCDEF0123456789` shows the key, and the build proceeds past "Verifying source file signatures".

Sources: <https://wiki.archlinux.org/title/Makepkg> · <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://wiki.archlinux.org/title/GnuPG> · <https://github.com/Jguer/yay/blob/v13.0.1/pkg/sync/srcinfo/pgp/keys.go> · <https://github.com/Jguer/yay/blob/v13.0.1/pkg/text/input.go> · <https://github.com/Jguer/yay/blob/v13.0.1/pkg/sync/sync.go> · <https://github.com/Jguer/yay/blob/v13.0.1/pkg/settings/config.go> · <https://github.com/Jguer/yay/blob/v13.0.1/doc/yay.8> · <https://github.com/Jguer/yay/releases/tag/v13.0.0> · <https://github.com/Morganamilo/paru/blob/master/src/config.rs>

---

## Fix 404s from a stale mirror during an upgrade

`failed-retrieving-file-404-stale-mirror` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** ```
error: failed retrieving file 'foo-1.2-1-x86_64.pkg.tar.zst' from mirror.example.org : The requested URL returned error: 404
warning: failed to retrieve some files
error: failed to commit transaction (failed to retrieve some files)
```
or `error: target not found: foo` for a package you can clearly see on archlinux.org/packages.

**Cause.** Your sync database lists a package version the mirror no longer carries (the mirror is behind, or it has already rotated to a newer version), the mirror is broken, or the repository containing the package (for example multilib) is not enabled in `/etc/pacman.conf`.

On Omarchy 4 the mirror is not one you picked. `/etc/pacman.d/mirrorlist` holds a single line, `Server = https://stable-mirror.omarchy.org/$repo/os/$arch` (`rc-mirror` and `mirror` for the other channels), and core, extra and multilib all use it. That mirror is a snapshot of Arch that Omarchy advances on its own release schedule, so it can sit days behind the official mirrors, and packages in the `[omarchy]` repo at pkgs.omarchy.org are built against that snapshot. A 404 there means your local database and the snapshot have drifted, usually because a package was rotated, or because the mirrorlist was replaced with Arch mirrors (a merged `mirrorlist.pacnew` from the pacman-mirrorlist package, or reflector) and the databases now describe packages the snapshot does not have.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation: /etc/pacman.d/mirrorlist is one line, `Server = https://stable-mirror.omarchy.org/$repo/os/$arch`, copied from /usr/share/omarchy/default/pacman/mirrorlist-stable by install/post-install/pacman.sh, with rc and edge variants beside it, and core, extra and multilib all Include it. Neither reflector nor rate-mirrors is installed and nothing under /usr/share/omarchy references either. Omarchy's mirror tool is /usr/share/omarchy/bin/omarchy-refresh-pacman, which backs up pacman.conf and mirrorlist to .bak, copies the channel defaults, runs the pre-refresh-pacman hook, then runs `sudo env OMARCHY_UPDATE_PACMAN=1 pacman -Syyuu --noconfirm`. omarchy-update and omarchy-update-keyring do not touch the mirrorlist. The stable mirror is a pinned snapshot: its lastupdate file read 2026-08-25 while geo.mirror.pkgbuild.com read 2026-09-06, and omacom/omarchy issue 9064 documents the same lag. In issue 3825 dhh says not to run reflector because new mirrors will not be in sync with Omarchy's release schedule, and to use omarchy-refresh-pacman. The record's `sudo pacman -Syyu` and `-Syyuu` both carry -S and -u, so the ALPM guard (/usr/bin/omarchy-update-pacman-guard) aborts them on Omarchy unless OMARCHY_ALLOW_DIRECT_PACMAN=1 is set. The mirrorlist is owned by pacman-mirrorlist 20260610-1, so a pacman-mirrorlist upgrade will leave a mirrorlist.pacnew holding the Arch list, and merging it moves the machine off the snapshot. That is inferred from package ownership, I did not observe a pacnew here. Against the Arch wiki Pacman page (Packages cannot be retrieved on installation), Mirrors (Force pacman to refresh the package lists) and Reflector, the plain Arch advice, the -Syyuu downgrade warning and the reflector invocation all held, and reflector 2023-5 is in extra. Not exercised: I did not run any pacman sync or mirror change here.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** After switching to a different mirror you may hold packages newer than the new mirror offers. The wiki's remedy is `sudo pacman -Syyuu` to force-downgrade back into sync. That downgrade can revert a kernel or glibc, so reboot afterwards and be prepared to regenerate the initramfs. On Omarchy 4 `omarchy-refresh-pacman` runs exactly that `-Syyuu` for you, so expect downgrades if you had moved ahead of the snapshot on Arch mirrors. A direct `sudo pacman -Syyuu` is blocked by the update guard on Omarchy. Merging a `/etc/pacman.d/mirrorlist.pacnew` from the pacman-mirrorlist package replaces Omarchy's one-line mirrorlist with the Arch mirror list, which is the same drift by another route: keep the Omarchy line, or run `omarchy-refresh-pacman` afterwards.

**Fix.**

**Omarchy 4.** Do not run reflector or hand-pick Arch mirrors: they put you ahead of Omarchy's snapshot and out of step with the `[omarchy]` repo. Put the Omarchy defaults back and re-sync against them. This backs up `/etc/pacman.conf` and `/etc/pacman.d/mirrorlist` to `.bak`, restores the channel's `pacman.conf` and one-line mirrorlist, and runs `pacman -Syyuu` with the update guard satisfied, so anything newer than the snapshot is downgraded to match:

```bash
omarchy-refresh-pacman            # stable channel
omarchy-refresh-pacman rc         # or: edge
```

Then run the normal update:

```bash
omarchy update
```

If the Omarchy mirror itself is stale, `omarchy update` reports every repo as up to date while `pacman -Ss` cannot see packages added to Arch after the snapshot date. Compare the mirror's `lastupdate` against an official mirror before blaming your machine:

```bash
curl -s https://stable-mirror.omarchy.org/lastupdate; echo
curl -s https://geo.mirror.pkgbuild.com/lastupdate; echo
```

Those are epoch seconds. If the Omarchy value is old and the package you need was published after it, wait for the snapshot to advance rather than switching mirrors. Do not run `sudo pacman -Syyu` directly: the update guard aborts any pacman command carrying both `-S` and `-u`. For one deliberate bypass:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syyu
```

**Plain Arch.** First force a real database refresh against your current mirrors:

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

**Both.** If the package is 32-bit (lib32-*) or a Steam dependency, check that multilib is enabled in `/etc/pacman.conf`. Omarchy's shipped `pacman.conf` already has it:

```ini
[multilib]
Include = /etc/pacman.d/mirrorlist
```
then `sudo pacman -Syu` on Arch, or `omarchy update` on Omarchy.

**Verify.** `sudo pacman -Syu` downloads everything. `pacman -Ss foo` finds the package in the expected repo.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/Mirrors> · <https://wiki.archlinux.org/title/Reflector> · <https://github.com/omacom/omarchy/issues/3825> · <https://github.com/omacom/omarchy/issues/9064> · <https://github.com/omacom/omarchy/issues/6162> · <https://github.com/omacom/omarchy-pkgs/blob/master/README.md> · <https://archlinux.org/packages/extra/any/reflector/> · <https://stable-mirror.omarchy.org/lastupdate> · <https://geo.mirror.pkgbuild.com/lastupdate>

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

**Cause.** makepkg refuses to run with EUID 0 by design. A PKGBUILD is arbitrary shell executed at build time. As root it ignores every file permission and can write anywhere on the system. makepkg is built to run *unprivileged* and to escalate via sudo only for the specific `pacman` calls it makes (installing build dependencies, installing the finished package). So it needs a normal user with working sudo, the inverse of what people try.

> **Audit corrected this record.** The error text and cause are exact. pacman's scripts/makepkg.sh.in line 1122 is `if (( EUID == 0 ))` followed by the gettext string 'Running %s as root is not allowed as it can cause permanent,\ncatastrophic damage to your system.' and `exit $E_ROOT`, and libmakepkg/util/error.sh.in defines E_ROOT=10. The record's exit status is right. Steps 1, 2, 3, 5 and 6 are all correct, and the Omarchy claim is verified: bin/omarchy-pkg-aur-install runs `yay -S --noconfirm` as the invoking user with only a sudo-keepalive, never `sudo yay`.

Step 4 is the defect. `runuser -u nobody -- makepkg` will abort before building on almost any real PKGBUILD, because makepkg checks dependencies and, running as an unprivileged user with no sudo rights, cannot install them, so it exits with 'Missing dependencies'. The record installs no build dependencies anywhere in that path. Second, nobody's home directory is `/`, which is not writable, so any PKGBUILD carrying `validpgpkeys` fails source verification when gpg cannot create a keyring. Third, the framing overstates provenance: I could not find the nobody technique documented on the ArchWiki Makepkg or Arch User Repository pages, so 'the Arch-sanctioned escape hatch' is not supportable. It is a container convention, and the ArchWiki's actual position (Makepkg, 'Running makepkg itself as root is disallowed') points at a normal build user.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Do not "solve" this by adding `%wheel ALL=(ALL) NOPASSWD: ALL` to sudoers just to quiet an AUR helper. That hands every PKGBUILD you build unattended full root. Only chown paths inside your own home. Chowning system directories to fix build errors will break package ownership. Building as `nobody` in a shared `/tmp` directory means anyone on the box can tamper with the sources between download and build. Use it only in a single-user container or chroot.

**Fix.**

Steps 1, 2, 3, 5 and 6 are unchanged. Replace step 4 with:

**4. Truly account-less environment (container, chroot).** The reliable pattern is a throwaway build user with passwordless sudo. This is what the official Arch container images do, and it is preferred over `nobody` because makepkg must be able to install build dependencies:

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

If you genuinely cannot create a user, the `nobody` route works only if you install the build dependencies as root first and give nobody a writable HOME. Otherwise makepkg aborts on missing dependencies, and gpg source verification fails because nobody's home is `/`:

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

`--nodeps` is required here: nobody has no sudo, so makepkg cannot install anything itself, which is exactly why you installed the dependencies as root above.

**Verify.** `makepkg -si` gets past source download into `==> Starting build()...` and finishes with `==> Finished making: PKGNAME`. `pacman -Qi PKGNAME` shows it installed. `ls -l` in the build directory shows files owned by your user, not root.

Sources: <https://wiki.archlinux.org/title/Makepkg> · <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://man.archlinux.org/man/makepkg.8> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-pkg-aur-install>

---

## Reclaim a disk filled by the pacman package cache

`pacman-cache-filling-disk` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** `df -h` shows / nearly full and `sudo du -sh /var/cache/pacman/pkg` reports tens of gigabytes. On Omarchy 4 the first sign is usually `omarchy update` stopping at once with:
```
You need at least 10 GiB free to safely update Omarchy.
```
On plain Arch, or when bypassing that check, pacman itself refuses:
```
error: Partition /var too full: 1234567 blocks needed, 1000 blocks free
error: failed to commit transaction (not enough free disk space)
```

**Cause.** pacman keeps every package it downloads in /var/cache/pacman/pkg/ and never prunes it on its own. On a rolling release with frequent kernel, browser and Electron updates that grows without bound. AUR helper build directories (~/.cache/yay for yay 13, ~/.cache/paru) add to it. Omarchy 4 is different: `omarchy update` runs `paccache -rk2` before every update (`omarchy-update-pkg-prune`) and cleans yay's untracked build files with `--cleanafter`, so the cache only runs away on a machine that has not updated for a long time, or when the disk fills for another reason. It then bites twice, because `omarchy update` refuses to start with less than 10 GiB free on / and that check runs before the prune step. On a stock Omarchy 4 install /var/cache/pacman/pkg is its own btrfs subvolume (`@pkg`), so snapper snapshots of / do not hold on to deleted cache files.

> **Audit corrected this record.** Generic Arch content checked against the raw Arch wiki Pacman page (Cleaning the package cache) and `man 8 paccache` from pacman-contrib 1.13.1 on this machine: the default keep of 3, `-rk1`, `-ruk0`, the weekly `paccache.timer` and `PACCACHE_ARGS` in /etc/conf.d/pacman-contrib all hold, and the timer is present and disabled here. The two error strings were confirmed in pacman's lib/libalpm/diskspace.c and error.c. yay 13.0.1 on this machine reports `buildDir: /home/techluddite/.cache/yay` via `yay -Pg` and its man page says `-Sc` cleans the AUR cache and untracked files, so the yay advice holds. Wrong for Omarchy 4: the cause says nothing prunes the cache automatically, but /usr/share/omarchy/bin/omarchy-update-pkg-prune runs `sudo paccache -rk2` at the start of every `omarchy update` (commit fd23ca02, 2026-08-12, PR #6734, shipped in 4.0.2 here), pacman-contrib is a hard dependency of the omarchy package so `pacman -S --needed pacman-contrib` is a no-op, and `omarchy-update-aur-pkgs` runs yay with `--cleanafter`. Also missed: /usr/share/omarchy/bin/omarchy-update-requires-free-space refuses to run the update with under 10 GiB free on / and prints `You need at least 10 GiB free to safely update Omarchy.`, and that check runs before the prune, so a full disk blocks the update that would have pruned it. The verify step's `sudo pacman -Syu` is aborted by the ALPM update guard on Omarchy 4. Plain Arch defect: `pacman -Qii pacman-contrib` shows `Backup Files: None` and the PKGBUILD has no backup array, so `/etc/conf.d/pacman-contrib` is replaced on the next pacman-contrib upgrade and a `-k2` written there is lost. On this machine and in the stock install layout /var/cache/pacman/pkg is its own btrfs subvolume (@pkg, confirmed with findmnt and this repo's tools/make-test-vm.sh), so snapper snapshots of / do not pin deleted cache files and paccache frees space immediately. Not exercised: I ran no paccache, did not run the timer, and did not retrieve the ISO configurator to confirm @pkg from upstream.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `pacman -Scc` empties the cache completely, including the currently installed versions. After that you cannot downgrade or reinstall anything offline, every recovery needs a working network and mirror. Prefer `paccache -r`. On Omarchy 4 the cache is the only offline downgrade path after a snapper rollback, and `omarchy update` already keeps 2 versions, so `paccache -rk1` leaves you with only what is installed. `OMARCHY_UPDATE_FORCE=1` skips the 10 GiB check but does not make the update fit, and a pacman transaction that dies mid-way for lack of space can leave the system half upgraded.

**Fix.**

`paccache` comes from pacman-contrib. Omarchy 4 depends on it, on plain Arch install it (`-S` without `-u` is not blocked by the Omarchy update guard):

```bash
sudo pacman -S --needed pacman-contrib
```

Keep the last 3 versions of each package (default, still allows downgrading):

```bash
sudo paccache -r
```

More aggressive: keep 1 version, and drop every cached version of packages no longer installed:

```bash
sudo paccache -rk1
sudo paccache -ruk0
```

Omarchy 4: once enough is free, run the update, which prunes to 2 versions itself each time:

```bash
omarchy update
```

Automate it weekly (plain Arch, or an Omarchy machine that is rarely updated):

```bash
sudo systemctl enable --now paccache.timer
```

To change the retention the timer uses, do not edit `/etc/conf.d/pacman-contrib`: it is not a pacman backup file, so the next pacman-contrib upgrade overwrites it. Override the unit instead:

```bash
sudo systemctl edit paccache.service
```

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/paccache -rk2
```

Clear AUR helper build caches too (yay 13 builds in ~/.cache/yay):

```bash
yay -Sc          # plain Arch with paru: paru -Sc
rm -rf ~/.cache/yay/*
```

Check the result (sudo, because pacman 7 leaves alpm-owned download directories `du` cannot read as your user):

```bash
sudo du -sh /var/cache/pacman/pkg
du -sh ~/.cache/yay
df -h /
```

**Verify.** `du -sh /var/cache/pacman/pkg` drops substantially and `df -h /` shows free space. `sudo pacman -Syu` no longer reports insufficient disk space.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/System_maintenance> · <https://man.archlinux.org/man/pacman.8> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/diskspace.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/error.c> · <https://gitlab.archlinux.org/archlinux/packaging/packages/pacman-contrib/-/raw/main/PKGBUILD> · <https://archlinux.org/packages/extra/x86_64/pacman-contrib/> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-pkg-prune> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update> · <https://github.com/basecamp/omarchy/blob/quattro/test/shell.d/update-pkg-prune-test.sh>

---

## Clear a stale pacman lock after 'unable to lock database'

`pacman-unable-to-lock-database` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** pacman refuses to do anything:

```
error: failed to init transaction (unable to lock database)
error: could not lock database: File exists
  if you're sure a package manager is not already
  running, you can remove /var/lib/pacman/db.lck
```

Often happens after closing a terminal mid-update, after a crash or power loss, or while another package manager (yay, paru, a GUI updater, or `omarchy update`) is still running in the background. On Omarchy 4 a second `omarchy update` prints a different message, `An Omarchy update is already running.`, which is not a pacman lock at all (see the fix).

**Cause.** pacman creates /var/lib/pacman/db.lck before it alters the package database, so two instances cannot write at once. If pacman is killed or the machine loses power mid-transaction, the lock file is left behind and every later run refuses to start.

> **Audit corrected this record.** Lock path confirmed on this machine: `pacman -Qv` prints `Lock File : /var/lib/pacman/db.lck` on pacman 7.1.0 (libalpm 16.0.1), and the Arch wiki Pacman page section 'Failed to init transaction (unable to lock database)' gives the same path, the `rm`, and the `fuser` tip. Mechanism confirmed from pacman source (lib/libalpm/handle.c `_alpm_handle_lock`: `open(O_WRONLY|O_CREAT|O_EXCL)`, fd kept open for the transaction, unlinked in `alpm_unlock`, and src/pacman/util.c prints the 'if you're sure a package manager is not already running, you can remove' hint). The cause is correct. Two things were wrong for Omarchy 4. First, the fix and the verify both run `sudo pacman -Syu`, which `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` (PreTransaction, AbortOnFail, read on this machine) aborts whenever the pacman command line carries both -S and -u without OMARCHY_UPDATE_PACMAN=1 or OMARCHY_ALLOW_DIRECT_PACMAN=1, so on Omarchy the recovery command fails with 'Woah partner'. Second, the record folds `omarchy-update` into the pacman lock case, but `omarchy update` holds its own lock: `/usr/share/omarchy/bin/omarchy-update-lock` (read here, omarchy 4.0.2-1) takes a kernel `flock -n` on `$XDG_RUNTIME_DIR/omarchy-update.lock`, which the kernel releases when the holder dies, so that lock cannot go stale and 'An Omarchy update is already running.' always means a live process. That is a distinct case and the corrected fix separates it. Also checked: `omarchy-update-available` runs `checkupdates`, which uses its own `--dbpath` copy and never takes db.lck, so the update notifier is not a lock holder. `fuser` is present (psmisc 23.7-2). Symptom text was tidied to the real two-line pacman message. Not exercised: no stale lock was created or removed on this machine (no sudo), so the fuser and rm steps are confirmed from source and the wiki only.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Deleting db.lck while pacman really is running will let a second instance write the database at the same time and can corrupt /var/lib/pacman/local, leaving an unrecoverable package database. Always run `fuser` first.

**Fix.**

First confirm nothing is actually using the lock. This is the step people skip and it is why systems get corrupted. pacman keeps the lock file open for the whole transaction, so `fuser` sees the holder (it needs sudo because pacman runs as root):

```bash
sudo fuser /var/lib/pacman/db.lck
# also check for a running package manager
ps aux | grep -E '[p]acman|[y]ay|[p]aru|[o]marchy-update'
```

If `fuser` DOES print a PID, wait for that process to finish instead of deleting the file. On Omarchy, `omarchy update` runs pacman as `sudo env OMARCHY_UPDATE_PACMAN=1 pacman -Syu`, so it shows up in that `ps` output, and its transcript is in `/tmp/omarchy-update.log`.

If `fuser` prints nothing and no package manager process exists, delete the stale lock and rerun the upgrade through the supported path.

**Omarchy 4:**

```bash
sudo rm /var/lib/pacman/db.lck
omarchy update
```

Do not rerun with `sudo pacman -Syu` here: the `00-omarchy-update-guard.hook` pacman hook aborts any direct `-Syu` with `Woah partner...`. If you really want one direct transaction:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu
```

**Plain Arch:**

```bash
sudo rm /var/lib/pacman/db.lck
sudo pacman -Syu
```

**`An Omarchy update is already running.` is a different lock.** `omarchy update` takes a kernel `flock` on `$XDG_RUNTIME_DIR/omarchy-update.lock` (normally `/run/user/<uid>/omarchy-update.lock`) through `omarchy-update-lock`. The kernel drops that lock when the holding process exits, so it cannot be left behind by a crash and there is nothing to delete. The message means an update is genuinely still running. Find it and watch it:

```bash
pgrep -af omarchy-update
tail -f /tmp/omarchy-update.log
```

If `pgrep` finds nothing, the lock is already free and `omarchy update` will start.

**Verify.** On Omarchy, `omarchy update` reaches `Update system packages` and pacman starts resolving dependencies instead of printing `unable to lock database`. On plain Arch, `sudo pacman -Syu` starts resolving. In both cases `ls /var/lib/pacman/db.lck` reports no such file once pacman is idle.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://man.archlinux.org/man/pacman.8> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/handle.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/util.c>

---

## Find and merge the .pacnew files an upgrade left behind

`pacnew-files-left-unmerged` · severity: **medium** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Update output scrolls past lines like:
```
warning: /etc/pacman.conf installed as /etc/pacman.conf.pacnew
warning: /etc/ssh/sshd_config installed as /etc/ssh/sshd_config.pacnew
```
Weeks later something breaks for no obvious reason: sshd refuses to start, sudo behaves oddly, a service silently uses stale defaults.

**Cause.** When a package ships a new version of a config file you have modified, pacman refuses to overwrite it and drops the new version alongside as `.pacnew`. Nothing merges it for you. Over time your live config drifts behind upstream defaults and eventually contains directives the new binary no longer understands.

> **Audit corrected this record.** The problem and the find/grep commands are fine, but the pacdiff invocation is broken as written. `sudo DIFFPROG=nvim -E pacdiff` fails: sudo stops option parsing at the VAR=value assignment, so `-E` is taken as the command to execute ('sudo: -E: command not found'). Separately, pacdiff(8) documents the default DIFFPROG as `vim -d` (or `nvim -d` when EDITOR=nvim), so bare `nvim` opens two buffers rather than a diff, and modern pacdiff has a `--sudo` flag that is the intended way to run it unprivileged. The suggested `pacdiff-pacman-hook-git` AUR package could not be verified and should not be recommended blind.
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

With an explicit diff tool. Note the `-d`, because a bare `nvim` opens two buffers instead of a diff:

```bash
DIFFPROG='nvim -d' pacdiff --sudo
# or, if your pacdiff predates --sudo:
DIFFPROG=meld sudo -E pacdiff
```

Do NOT use `sudo DIFFPROG=nvim -E pacdiff`, because sudo stops parsing options at the `VAR=value` assignment and then tries to run `-E` as the command.

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

**Symptom.** AUR builds fail immediately with things like `bash: makepkg: command not found`, `==> ERROR: Cannot find the fakeroot binary`, `==> ERROR: Cannot find the strip binary required for object file stripping`, or a compiler/`patch`/`autoconf` not found error, on a system that used to build AUR packages fine.

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

**Symptom.** An installed AUR package that no longer exists in the AUR is reported on every update. With yay 13 (Omarchy 4 ships 13.0.1) the wording is a warning, not an error:
```
:: Searching AUR for updates...
 -> Packages not in AUR:  spotify-adblock
```
You see it from `yay -Sua`, from `yay -Syu` on plain Arch, and on Omarchy inside `omarchy update` under the `Update AUR packages` heading, which then carries on. Older yay releases printed `Could not find all required packages:` with the name and `(Target)`. Asking yay for the package by name fails outright:
```
$ yay -S my-package
 -> No AUR package found for  my-package
```
and pacman never searches the AUR at all:
```
$ sudo pacman -S my-package
error: target not found: my-package
```
`pacman -Qm` still lists the package as installed, but https://aur.archlinux.org/packages/<name> returns 404 or lands on a differently named package. On Omarchy 4 `yay -Syu` itself stops with `Woah partner...` from the pacman update guard before it gets far, because yay runs `pacman -S -y -u` underneath. Use `omarchy update` or `yay -Sua` there.

**Cause.** AUR packages get deleted (submission-rule violation, dead upstream, a malware or licence report), merged into another package base, renamed by the maintainer, or adopted into the official `extra` repository. Your locally built copy stays installed forever, receives no updates, and every helper run flags it: yay asks the AUR RPC for every foreign package and warns `Packages not in AUR:` for any name the RPC does not return. Separately, `pacman -S` says `target not found` for anything that only ever existed in the AUR, because pacman searches only the configured repositories, never the AUR. On Omarchy 4 the AUR step of `omarchy update` (`omarchy-update-aur-pkgs`) runs `yay -Sua --noconfirm` only when `pacman -Qem` lists an explicitly installed foreign package, and it ignores yay's exit status, so the warning repeats on every update but the update completes. If the AUR is unreachable that step is skipped entirely with `AUR is unavailable (so skipping updates)` (`omarchy-pkg-aur-accessible`), so a package that is unreachable and one that is deleted look different.

> **Audit corrected this record.** Checked the four RPC calls live: rpc/v5/info?arg[]=yay&arg[]=nonexistent-pkg-xyz123 returned resultcount 1 with only yay, rpc/v5/search/yay?by=name returned 19 results, and packages.gz serves a bare sorted name list, so the comm one-liner, which is verbatim from the Arch User Repository wiki page, works. The symptom text is wrong for the yay this system ships: the strings 'Could not find all required packages' and '(Target)' do not exist anywhere in the yay v13.0.1 source (the version installed here, pacman -Q yay = 13.0.1-1). pkg/query/aur_warnings.go prints the non-fatal warning 'Packages not in AUR:' for an installed foreign package the RPC no longer knows, and pkg/dep/dep_graph.go prints 'No AUR package found for' when you ask yay -S for a name that is gone. On Omarchy 4 the symptom's opening command, yay -Syu, is blocked: yay formats its pacman call as separate -S -y -u flags (pkg/settings/parser/parser.go) and /usr/bin/omarchy-update-pacman-guard aborts any pacman command line carrying both S and u, so the record needed an Omarchy branch (omarchy update, or yay -Sua which in AUR-only mode never calls pacman -S, cmd.go line 446). The Omarchy note was also wrong about what happens: /usr/share/omarchy/bin/omarchy-update-aur-pkgs (byte-identical to quattro) only runs yay when pacman -Qem lists an explicitly installed foreign package, and its if-body ends in echo, so the script exits 0 whatever yay returned. omarchy update therefore prints the warning and continues, it does not abort at the AUR step. A sibling verdict in this batch claims the opposite (that omarchy-update-aur-pkgs returns yay's exit code) and is wrong. pacman -Qm is the right list of foreign packages (System_maintenance wiki and pacman -Qm here, which is empty on this workstation, so no live yay output could be observed). pacman -S, pacman -S --needed, pacman -Rns and pacman -Ss pass the guard because none carries -u. pactree comes from pacman-contrib, which omarchy-base.packages installs and which is Required By omarchy here. Not exercised: an actual deleted package on a live yay run, and the git clone of a deleted package's repo (the wiki says the repo typically remains).
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** `pacman -Rns` on a package other things depend on cascades, so always run `pactree -r PKGNAME` first and read the removal list. Never edit `/var/lib/pacman/local` by hand to silence the helper. That corrupts the package database. A deleted AUR package was often deleted for a reason (unmaintained, licensing, malware report). Check the aur-requests mailing list archive before rebuilding it from an old git clone and running its PKGBUILD, which executes arbitrary code on your machine.

**Fix.**

**1. List every foreign (non-repo) package and check which ones are gone.** The one-liner is from the Arch User Repository wiki page:

```bash
pacman -Qqm
comm -23 <(pacman -Qqm | sort) <(curl -s https://aur.archlinux.org/packages.gz | gzip -cd | sort)
```
Anything printed no longer exists in the AUR. Packages you built yourself from a local PKGBUILD will be listed too.

**2. For one package, ask the AUR RPC directly.** An empty `results` array (`resultcount: 0`) means it is gone:

```bash
curl -s 'https://aur.archlinux.org/rpc/v5/info?arg[]=PKGNAME' | head -c 400
```

**3. Work out where it went:**

```bash
# (a) adopted into the official repos
pacman -Ss '^PKGNAME$'
```
If it is there, refresh and upgrade first so the sync database is current, then install the repo build over your local one. On Omarchy 4 the refresh is `omarchy update` (a direct `pacman -Syu` is blocked by the update guard), on plain Arch it is `sudo pacman -Syu`. Then:

```bash
sudo pacman -S PKGNAME          # the repo version replaces your local build
```

```bash
# (b) renamed or merged: search by name, then by what it provides
curl -s 'https://aur.archlinux.org/rpc/v5/search/PARTIALNAME?by=name' | head -c 800
curl -s 'https://aur.archlinux.org/rpc/v5/search/PKGNAME?by=provides' | head -c 800
```

**4. Migrate: install the successor, then drop the stale one.** `pactree` is in `pacman-contrib`, which Omarchy installs by default:

```bash
sudo pacman -S --needed pacman-contrib
pactree -r OLD-PKGNAME          # check nothing else needs it FIRST
yay -S NEW-PKGNAME
sudo pacman -Rns OLD-PKGNAME
```

**5. If nothing replaced it and you still want it**, the git repo of a deleted AUR package usually survives. Clone it and maintain it yourself:

```bash
git clone https://aur.archlinux.org/PKGNAME.git
cd PKGNAME && makepkg -si
```

**6. If you just want the noise to stop:**

```bash
sudo pacman -Rns PKGNAME
```

**Omarchy 4 note:** `omarchy update` runs `omarchy-update-aur-pkgs`, which calls `yay -Sua --noconfirm` only when `pacman -Qem` lists an explicitly installed foreign package, and skips the AUR entirely when `omarchy-pkg-aur-accessible` cannot reach the RPC. The `Packages not in AUR:` warning does not stop the update, so a deleted package is reported on every run until you migrate or remove it. Do not use `yay -Syu` on Omarchy: the pacman update guard rejects the `pacman -S -y -u` it runs underneath. `yay -Sua` (AUR only, no pacman sync) is fine.

**Verify.** `comm -23 <(pacman -Qqm | sort) <(curl -s https://aur.archlinux.org/packages.gz | gzip -cd | sort)` prints nothing (or only packages you deliberately build locally), and `yay -Syu` completes without `Could not find all required packages`.

Sources: <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://aur.archlinux.org/rpc/v5/info?arg[]=yay> · <https://aur.archlinux.org/packages.gz> · <https://wiki.archlinux.org/title/System_maintenance> · <https://wiki.archlinux.org/title/Aurweb_RPC_interface> · <https://aur.archlinux.org/rpc/v5/info?arg[]=yay&arg[]=nonexistent-pkg-xyz123> · <https://aur.archlinux.org/rpc/v5/search/yay?by=name> · <https://github.com/Jguer/yay/blob/v13.0.1/pkg/query/aur_warnings.go> · <https://github.com/Jguer/yay/blob/v13.0.1/pkg/dep/dep_graph.go> · <https://github.com/Jguer/yay/blob/v13.0.1/pkg/settings/parser/parser.go> · <https://github.com/Jguer/yay/blob/v13.0.1/cmd.go> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update-aur-pkgs> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-pkg-aur-accessible> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update>

---

## Handle the sudo password prompt that appears during the AUR step of omarchy update

`aur-sudo-password-prompt-mid-omarchy-update` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** `omarchy update` asked for the password once at the start, ran for a while, and then stopped again at the AUR step:

```
Update AUR packages
...
[sudo] password for <user>:
```

If nobody is at the keyboard (including `omarchy update -y`), the prompt sits there until sudo gives up, and the AUR package is never installed. With plain `yay -Syu`-style long builds outside Omarchy the same thing happens: yay builds for twenty minutes, then asks for the password at the install step.

**Cause.** sudo caches a successful authentication for `timestamp_timeout` minutes, and the default is 5 (sudoers(5)). A long AUR build easily outlasts that, so the `sudo pacman -U` yay runs after building finds no valid timestamp and prompts. sudo's own `passwd_timeout` is also 5 minutes by default, after which the prompt fails and yay reports `error making` or an install failure.

Omarchy 4.0.4 (the current release as of 2026-10-04): `omarchy-update` runs plain `sudo` in each helper with no keepalive, and the AUR step is `yay -Sua --noconfirm --cleanafter --ignore gcc14,gcc14-libs` with no `--sudoloop`. Any yay setting you saved yourself is honoured.

Omarchy `quattro` after PR #13323 (merged 2026-09-26, not yet in a release): the update asks once and keeps that timestamp alive with a background `sudo -n /usr/bin/true` every minute, but it deliberately revokes it before AUR, because PKGBUILDs are third-party code. AUR then runs last with `yay --sudo <no-update wrapper> --sudoloop=false`, and the wrapper is `sudo -N`, which never writes a timestamp. So on that code every sudo call yay makes prompts, by design, and a saved `sudoloop` is overridden.

> **Audit corrected this record.** The mechanism holds. Read /usr/share/omarchy/bin/omarchy-update and omarchy-update-aur-pkgs on 4.0.4-1: the AUR step is exactly `yay -Sua --noconfirm --cleanafter --ignore gcc14,gcc14-libs` with no sudoloop. omarchy-sudo-keepalive exists, but only omarchy-pkg-install and omarchy-pkg-aur-install source it, not the update. PR #13323 was read in full: it merged 2026-09-26 and adds a one-time `sudo /usr/bin/true` with a `sudo -n /usr/bin/true` keepalive every 60 s. On quattro, bin/omarchy-update revokes before AUR, and bin/omarchy-update-aur-pkgs passes `--sudo <wrapper> --sudoloop=false`. The wrapper default/omarchy/sudo-no-update/sudo execs `/usr/bin/sudo -N`. The latest release is still v4.0.4 (2026-09-15), so 'not yet in a release' holds. yay's cmd_builder.go confirms the sudoloop is `sudo -v` every 241 s. Omarchy ships only `passwd_tries=10` and does not change timestamp_timeout. Two defects in the fix. The post-#13323 advice says 'let the update skip nothing and then run the AUR step yourself', which is garbled. And the sudoers recipe uses a `<user>` placeholder where `$USER` works. I also added the interaction with `verifypw=any` from the sibling record: a passwordless `sudo -v` writes no timestamp, so with that setting the sudoloop keeps nothing alive. Not exercised: no update or build was run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A longer timestamp_timeout means any process running as you can use sudo without a password for that long, which is exactly the exposure Omarchy's #13323 change avoids for AUR builds. A sudoers drop-in with a syntax error can lock you out of sudo: always run `sudo visudo -c` before closing the root shell you edited it from.

**Fix.**

Check what happened in the last run:

```bash
grep -nE 'Update AUR packages|password for|timed out|error making' /tmp/omarchy-update.log
yay -Qua          # AUR updates still pending
```

Omarchy 4.0.4 and plain Arch: make yay keep the timestamp alive during builds. `--save` writes it to `~/.config/yay/config.json`, so `omarchy update` picks it up too:

```bash
yay --sudoloop --save
```

The sudoloop runs `sudo -v` once at the start (you type the password then) and repeats it in the background every four minutes until yay exits. If your `sudo -v` prompts even with passwordless sudo, see the record on `verifypw`. If you set `verifypw=any` from that record, `sudo -v` succeeds without authenticating and writes no timestamp, so the sudoloop then keeps nothing alive for a user who is not fully passwordless.

To finish the skipped AUR updates now, run the same command the updater uses, with the loop:

```bash
yay -Sua --sudoloop --cleanafter --ignore gcc14,gcc14-libs
```

Omarchy after PR #13323 reaches a release: the extra prompts during the AUR step are the intended security boundary, and the updater passes `--sudoloop=false`, which overrides a saved sudoloop. Run `omarchy update` while you are at the keyboard. If the AUR step was skipped or failed unattended, run the command above yourself afterwards.

Do not raise `timestamp_timeout` globally to paper over this. If you must, scope it to your user with a validated drop-in:

```bash
echo "Defaults:$USER timestamp_timeout=30" | sudo tee /etc/sudoers.d/90-timestamp >/dev/null
sudo chmod 0440 /etc/sudoers.d/90-timestamp
sudo visudo -c
```

**Verify.** `yay -Qua` prints nothing after the next update. The new log has an `Update AUR packages` section with no `password for` line after the first prompt (4.0.4 with sudoloop saved). `jq .sudoloop ~/.config/yay/config.json` prints `true`.

Sources: <https://github.com/omacom/omarchy/pull/13323> · <https://github.com/omacom/omarchy/issues/13319> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-aur-pkgs> · <https://github.com/Jguer/yay/blob/next/doc/yay.8> · <https://github.com/Jguer/yay/blob/next/pkg/settings/exe/cmd_builder.go> · <https://man.archlinux.org/man/sudoers.5> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update> · <https://github.com/omacom/omarchy/blob/quattro/default/omarchy/sudo-no-update/sudo>

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

> **Audit corrected this record.** Checked the Makepkg wiki section Generate new checksums, which says to install pacman-contrib and run updpkgsums in the PKGBUILD directory and that updpkgsums calls makepkg --geninteg. That matches the fix. Confirmed on this machine that pacman-contrib 1.13.1-1 is installed and provides /usr/bin/updpkgsums (pacman -Ql pacman-contrib), and that it is a hard dependency of the omarchy 4.0.2-1 package (pacman -Qi omarchy, Depends On) and listed in /usr/share/omarchy/install/omarchy-base.packages line 98. So on Omarchy 4 the fix's `sudo pacman -S --needed pacman-contrib` is a no-op and the record should say the tool is already present, which is the mis-specialisation corrected here. That command is not caught by the update guard, which only aborts on -S with -u, and it is not a bare -Sy, so it stays correct for plain Arch. Cache paths held: yay's buildDir here is /home/techluddite/.cache/yay (yay -Pg), so a package's clone and its downloaded tarball sit in ~/.cache/yay/foo because SRCDEST is commented out in /etc/makepkg.conf and no user makepkg.conf exists. paru is not installed here, but paru's src/config.rs builds its clone dir as the cache dir joined with paru and then clone, which gives ~/.cache/paru/clone. Also read: omarchy-update-aur-pkgs runs yay -Sua --noconfirm --cleanafter, which removes the build dir after a successful update, while omarchy-pkg-aur-install runs yay -S --noconfirm without --cleanafter and yay's cleanAfter default is false, so a stale clone can persist for packages installed through the TUI. yay's man page documents --mflags with the example --mflags "--skipchecksums --skippgpcheck", which the record correctly does not recommend. Danger text holds. Not exercised: no build or updpkgsums run was performed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Running `updpkgsums` blindly makes the checksum match WHATEVER you downloaded, including a tampered or MITM'd tarball. Only do this after independently confirming the source is legitimate, never as a reflex to get a build to pass.

**Fix.**

First rule out a stale cached download:

```bash
rm -rf ~/.cache/yay/foo        # or ~/.cache/paru/clone/foo
yay -S foo
```

If it still fails and you have verified the download is legitimate (checked the upstream release page / signature yourself), regenerate the checksums locally. `updpkgsums` comes from `pacman-contrib`. On Omarchy 4 it is already installed, because `pacman-contrib` is a dependency of the `omarchy` package. On plain Arch install it first:

```bash
sudo pacman -S --needed pacman-contrib    # plain Arch only, already present on Omarchy 4
cd /tmp && git clone https://aur.archlinux.org/foo.git && cd foo
updpkgsums          # rewrites the sums arrays in place using makepkg --geninteg
makepkg -si
```

Then tell the maintainer: leave a comment on the AUR page with the error. If the package is flagged out-of-date and you only need a version bump, edit `pkgver` in the PKGBUILD and run `updpkgsums` before building.

**Verify.** `makepkg` gets past "Validating source files" and produces a .pkg.tar.zst. `pacman -Qi foo` shows the new version.

Sources: <https://wiki.archlinux.org/title/Makepkg> · <https://wiki.archlinux.org/title/Arch_User_Repository> · <https://github.com/Jguer/yay/blob/v13.0.1/doc/yay.8> · <https://github.com/Morganamilo/paru/blob/master/src/config.rs>

---

## Get back a package that automatic orphan removal deleted

`automatic-orphan-removal-removes-wanted-packages` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** After an update (notably `omarchy-update`, which removes orphans automatically), a program you use is gone: an optional dependency, a font, a codec, or a package you originally installed as a dependency of something you later removed. `pacman -Q thepackage` says it is not installed.

**Cause.** `pacman -Qtdq` lists packages installed as dependencies that nothing currently requires. Piping that into `pacman -Rns` also removes optional dependencies of packages that are staying, and anything you installed with `-S --asdeps` or that was pulled in as a makedepend. Omarchy's `omarchy-update-orphan-pkgs` runs `sudo pacman -Rs --noconfirm` over every orphan on each update.

> **Audit corrected this record.** The Omarchy claim is verified: bin/omarchy-update-orphan-pkgs collects `pacman -Qtdq` and loops `sudo pacman -Rs --noconfirm "$pkg"` over each, unattended, exactly as described. But the central safety recommendation is wrong: it says to 'prefer -Rn over -Rns so optional deps of surviving packages are spared'. -n is --nosave, which has nothing to do with dependencies. It *deletes* config backups instead of leaving .pacsave files, so the suggested flag is strictly more destructive than plain -R. The safety comes entirely from dropping -s (no recursion). Also `pacman -D --asexplicit $(pacman -Qtdq)` errors out when there are no orphans.
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

Audit before any future orphan sweep. Review the list, then remove only those packages. Dropping `-s` is what stops the recursion into optional dependencies of surviving packages. Do **not** add `-n`: that is `--nosave`, which deletes your config backups instead of leaving `.pacsave` files, and has nothing to do with dependency handling.

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

On Omarchy 4 the question is usually not asked, because `omarchy update` and `omarchy-refresh-pacman` run pacman with `--noconfirm`. The transaction aborts instead:

```
:: File /var/cache/pacman/pkg/foo-1.2-1-x86_64.pkg.tar.zst is corrupted (invalid or corrupted package (checksum)).
error: failed to commit transaction (invalid or corrupted package (checksum))
Errors occurred, no packages were upgraded.
```

**Cause.** Two distinct causes. (1) Partially downloaded `.part` files left in the cache by an interrupted download or a custom `XferCommand`. On pacman 7 with `DownloadUser = alpm`, which Omarchy 4 ships in `/etc/pacman.conf`, pacman downloads into a `download-XXXXXX/` directory it creates inside `/var/cache/pacman/pkg/` and chowns to the `alpm` user, then moves any finished file or leftover `.part` back into `/var/cache/pacman/pkg/` so the next run can resume. The cache directory itself stays `root:root 0755` and must stay traversable by `alpm`: a cache directory tightened to `0700` fails with a permission error rather than this checksum error. (2) The local sync database holds a checksum for a package that the server has since rebuilt under the same name and version. `pacman -Sy` keeps a database it believes is current, so the stale checksum keeps rejecting the correct file, and deleting the cached copy changes nothing because the stale data is in the database. Omarchy hit exactly this during the Omarchy 3 to 4 upgrade: the quattro package server rebuilt some `omarchy-*` packages under the same name and version as the legacy repo, and `omarchy-upgrade-to-quattro` now runs `pacman -Syy` for that reason. A third variant reads `(PGP signature)` instead of `(checksum)`, often with `signature from ... is unknown trust` above it. That is a keyring problem, not a cache problem: on Omarchy 4 `omarchy update` refreshes `archlinux-keyring` and `omarchy-keyring` before upgrading, and on plain Arch upgrade `archlinux-keyring` first (Arch wiki, Pacman/Package signing).

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (pacman 7.1.0, /etc/pacman.conf identical to /usr/share/omarchy/default/pacman/pacman-stable.conf, DownloadUser = alpm) and against pacman's own source (dload.c, util.c, NEWS from gitlab.archlinux.org), the Arch wiki Pacman page, basecamp/omarchy issues 6576 and 4197, and the installed /usr/share/omarchy/bin/omarchy-refresh-pacman, which is byte-identical to the quattro branch copy. What held: the wiki still gives `find /var/cache/pacman/pkg/ -iname "*.part" -delete`, not `pacman -Scc`, for this error. On pacman 7 the download runs in a `download-XXXXXX/` directory pacman creates inside the cache and chowns to `alpm`, and `finalize_download_locations` moves any `.part` back into `/var/cache/pacman/pkg/` (chowned to root) so the next run can resume, so `.part` files still land where the record says. `/var/cache/pacman/pkg` here is `root:root 0755` with no `.part` files, and downloads work at that ownership, so the cache does not need to be alpm-owned, only traversable. Cause (2) is confirmed by issue 6576 and by the comment at lines 439 to 448 of the installed `omarchy-upgrade-to-quattro`, which now runs `-Syy` for exactly that reason. What was wrong: `sudo pacman -Su`, `pacman -Syyu` and `pacman -Syu` in the fix and verify are refused on Omarchy 4 by `/usr/share/libalpm/hooks/00-omarchy-update-guard.hook` (aborts any pacman command line with both `-S` and `-u` unless OMARCHY_UPDATE_PACMAN=1 or OMARCHY_ALLOW_DIRECT_PACMAN=1 is set), while a bare `pacman -Syy` passes. The record called `omarchy-refresh-pacman` the equivalent of the whole fix, but the installed script only copies the channel's pacman.conf and mirrorlist over `/etc` (backups at `.bak`), runs the `pre-refresh-pacman` hook and then `pacman -Syyuu --noconfirm`. It never touches the cache, `--noconfirm` makes a corrupted cached file abort instead of prompting, and `-uu` can downgrade. Issue 4197 is an Omarchy 3.3.3 `(PGP signature)` failure with `unknown trust`, a keyring problem, and supports only dhh's `rm -rf /var/cache/pacman/pkg/*` and `omarchy-refresh-pacman` advice, not the checksum loop. The cited raw URL for omarchy-refresh-pacman is on `master` (Omarchy 3) and differs from the installed script. Not exercised: no download was interrupted or database corrupted here, and the `--noconfirm` abort wording comes from issue 6576's log rather than a reproduction.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Emptying /var/cache/pacman/pkg removes your only offline copies of previously installed package versions, so you lose the ability to downgrade without re-downloading from the Arch Linux Archive. On Omarchy 4, `omarchy-refresh-pacman` overwrites `/etc/pacman.conf` and `/etc/pacman.d/mirrorlist` with Omarchy's defaults (backups at `.bak`) and runs `pacman -Syyuu`, which will also downgrade packages to whatever the Omarchy mirrors carry.

**Fix.**

Delete the partial and the rejected file first, then force a genuine database re-download (two `y`, not one). Deleting only the cached package is not enough for cause (2), because the stale checksum is in the database:

```bash
sudo find /var/cache/pacman/pkg/ -iname '*.part' -delete
sudo rm -f /var/cache/pacman/pkg/foo-*.pkg.tar.zst*
sudo pacman -Syy
```

Then finish the upgrade.

**Plain Arch:**

```bash
sudo pacman -Su
```

**Omarchy 4:** `pacman -Syy` on its own is allowed, but `pacman -Su` and `pacman -Syyu` are refused by the update guard hook with `Woah partner...`. Use the supported path, which runs `pacman -Syu` with the guard's own variable set:

```bash
omarchy update
```

or bypass the guard for one transaction:

```bash
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syyu
```

If it still loops, empty the cache and retry. This also removes any stale `download-XXXXXX/` directory a killed pacman 7 left behind:

```bash
sudo rm -rf /var/cache/pacman/pkg/*
sudo pacman -Syy
```

then `sudo pacman -Su` on plain Arch, or `omarchy update` (or the bypass above) on Omarchy 4.

On **Omarchy 4**, `omarchy-refresh-pacman` covers the database half only. It copies Omarchy's `pacman.conf` and `mirrorlist` for the channel over `/etc/pacman.conf` and `/etc/pacman.d/mirrorlist` (backups at `/etc/pacman.conf.bak` and `/etc/pacman.d/mirrorlist.bak`), runs the `pre-refresh-pacman` hook, then `pacman -Syyuu --noconfirm`. It does not touch the cache, so delete the bad file before running it, and expect any repos or `IgnorePkg` lines you added to `pacman.conf` to be gone afterwards:

```bash
omarchy-refresh-pacman stable
```

To confirm nothing is pending afterwards, use `checkupdates` (installed on Omarchy with `pacman-contrib`, prints nothing when the system is current) rather than `sudo pacman -Syu`, which the guard refuses.

**Verify.** The package downloads and installs. `sudo pacman -Syu` reports "there is nothing to do" or completes cleanly.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://github.com/basecamp/omarchy/issues/6576> · <https://github.com/basecamp/omarchy/issues/4197> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-refresh-pacman> · <https://raw.githubusercontent.com/basecamp/omarchy/quattro/bin/omarchy-refresh-pacman> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/dload.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/util.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/NEWS> · <https://archlinux.org/news/manual-intervention-for-pacman-700-and-local-repositories-required/>

---

## Downgrade a package that an update broke

`downgrade-a-broken-package` · severity: **medium** · frequency: **common** · applies to: `amd`, `arch`, `cachyos`, `desktop`, `endeavouros`, `intel`, `laptop`, `manjaro`, `nvidia`, `omarchy`

**Symptom.** An update breaks something (the browser won't start, audio dies, a driver regresses) and you want the previous version back. `pacman -S foo` only ever installs the newest one.

**Cause.** pacman has no built-in rollback. Older versions live either in your local cache or in the Arch Linux Archive.

> **Audit corrected this record.** Checked the Arch wiki Downgrading packages and Arch Linux Archive pages (raw wikitext, retrieved 2026-09-06), the live archive layout, the downgrade(8) man page source, and this Omarchy 4 workstation. What held: the cache path and `pacman -U file:///var/cache/pacman/pkg/...` match the wiki, the archive layout is `packages/<first letter>/<name>/` (confirmed by listing https://archive.archlinux.org/packages/x/xz/, which holds versioned .pkg.tar.zst files with detached .sig files), pacman fetching the .sig for a remote -U is what the wiki says, `IgnorePkg = foo` under [options] is the wiki's syntax, and the wiki's Automation section still recommends the AUR `downgrade` package, whose `--ignore` option defaults to prompting to add the package to IgnorePkg. `pacman -U` carries neither -S nor -u, so the Omarchy ALPM guard (/usr/bin/omarchy-update-pacman-guard, read on this machine) does not block it. What was wrong for Omarchy 4: (1) `sudo mkinitcpio -P` hits the /usr/local/bin/mkinitcpio wrapper installed by limine-mkinitcpio-hook, which warns that it does not update Limine entries and prompts to run limine-mkinitcpio, and it is redundant anyway because /etc/pacman.d/hooks/90-mkinitcpio-install.hook fires on usr/lib/modules/*/pkgbase and rebuilds the UKI, so the Omarchy branch now says to let the hook run or use `sudo limine-update`. (2) Nothing snapshots before a manual `pacman -U` on Omarchy 4: there is no snap-pac, and the only snapshot call is `omarchy-snapshot create` inside omarchy-update, so the fix now says to run it first. (3) The [omarchy] repo is not in the Arch Linux Archive and keeps only the current and previous package file (HEAD on pkgs.omarchy.org returned 200 for omarchy-4.0.2-1 and 4.0.1-1, 404 for 4.0.0-1), so downgrading one of its 30 installed packages here works only from the local cache. (4) Omarchy 4 installs nvidia-open-dkms (install/hardware/nvidia.sh, and installed here with dkms 3.4.3-2 and its 70-dkms-*.hook files), so the kernel danger text was overstated for Omarchy and understated the headers requirement, and the danger now says both. Not exercised: no package was downgraded on this machine, and the `downgrade` script was not run. Post-merge correction 2026-09-07 by the corpus lint: the rewritten text said `sudo omarchy-snapshot create`, but /usr/share/omarchy/bin/omarchy-snapshot calls sudo itself and reads OMARCHY_PATH, which sudo strips, so it is run as the user.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** Downgrading a package whose dependencies moved forward creates a partial upgrade. If a soname changed you must downgrade or rebuild the dependants too. Leaving a package in `IgnorePkg` long-term guarantees eventual breakage. On Omarchy 4 the `[omarchy]` repo is built against current Arch, so downgrading a library those packages link to can break them, and the archive holds no older `[omarchy]` packages to fall back to. Downgrading the kernel without the matching `linux-headers` leaves DKMS modules (Omarchy's `nvidia-open-dkms`) unbuilt, and downgrading it without matching prebuilt modules (`nvidia`, `virtualbox-host-modules-arch` on plain Arch) leaves you with no graphics. On Omarchy the UKI is regenerated by the pacman hook, and running `mkinitcpio -P` by hand does not update the Limine boot entries.

**Fix.**

**On Omarchy 4, snapshot first.** A manual `pacman -U` gets no automatic snapshot (only `omarchy update` takes one), and a Snapper snapshot is the way back if the downgrade makes things worse:

```bash
omarchy-snapshot create
```

**From the local cache (fastest, if you have not cleaned it):**

```bash
ls /var/cache/pacman/pkg/ | grep '^foo-'
sudo pacman -U file:///var/cache/pacman/pkg/foo-1.2.3-1-x86_64.pkg.tar.zst
```

`pacman -U` carries neither `-S` nor `-u`, so the Omarchy update guard lets it through without any environment variable.

**From the Arch Linux Archive** (pacman fetches the .sig and verifies it automatically):

```bash
sudo pacman -U https://archive.archlinux.org/packages/f/foo/foo-1.2.3-1-x86_64.pkg.tar.zst
```
Browse available versions at `https://archive.archlinux.org/packages/f/foo/` (first letter of the package name, then the package name).

**Packages from the `[omarchy]` repo** (`pacman -Si foo | grep Repository` says `omarchy`: for example omarchy, omarchy-settings, limine-snapper-sync, yay) are not in the Arch Linux Archive, and `https://pkgs.omarchy.org/stable/x86_64/` keeps only the current and the previous package file. Use the local cache for those.

**Pin it** so the next upgrade does not immediately re-upgrade it. In `/etc/pacman.conf` under `[options]`:

```ini
IgnorePkg = foo
```
Remove that line once upstream fixes the bug.

**Kernel specifically.** Downgrade `linux` and `linux-headers` together, plus any prebuilt out-of-tree modules:

```bash
sudo pacman -U file:///var/cache/pacman/pkg/linux-6.16.1.arch1-1-x86_64.pkg.tar.zst \
               file:///var/cache/pacman/pkg/linux-headers-6.16.1.arch1-1-x86_64.pkg.tar.zst
```

- Omarchy 4: the pacman hook `90-mkinitcpio-install.hook` from limine-mkinitcpio-hook rebuilds the UKI (`/boot/EFI/Linux/omarchy_linux.efi`) and the Limine entries in the same transaction. Do not run `mkinitcpio -P` by hand: on Omarchy `/usr/local/bin/mkinitcpio` is a wrapper that warns it does not update Limine entries. If you need to regenerate manually, use `sudo limine-update`. Omarchy's NVIDIA driver is `nvidia-open-dkms`, which rebuilds against the downgraded kernel through the dkms hooks as long as the matching `linux-headers` was installed in the same transaction.
- Plain Arch: the mkinitcpio pacman hook regenerates the initramfs. Run `sudo mkinitcpio -P` only if you use no hook. A prebuilt `nvidia` package must be downgraded to the version built for that kernel.

**Automation:** the `downgrade` AUR package wraps both sources and offers to add the package to `IgnorePkg` when it finishes:
```bash
yay -S downgrade
sudo downgrade foo
```

**Verify.** `pacman -Qi foo | grep Version` shows the old version and the broken behaviour is gone. For a kernel downgrade, reboot and check `uname -r`.

Sources: <https://wiki.archlinux.org/title/Downgrading_packages> · <https://wiki.archlinux.org/title/Arch_Linux_Archive> · <https://wiki.archlinux.org/title/Pacman> · <https://archive.archlinux.org/packages/x/xz/> · <https://raw.githubusercontent.com/archlinux-downgrade/downgrade/main/doc/downgrade.8.ronn> · <https://aur.archlinux.org/rpc/v5/info?arg[]=downgrade> · <https://pkgs.omarchy.org/stable/x86_64/omarchy-4.0.1-1-any.pkg.tar.zst>

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

> ⚠️ **Risk.** Deleting /var/lib/pacman/sync is safe (it only holds downloadable repo indexes). Do NOT confuse it with /var/lib/pacman/local, which is your irreplaceable installed-package database.

**Fix.**

Confirm the sync files are actually junk:

```bash
file /var/lib/pacman/sync/*
# healthy output says 'gzip compressed data' / 'Zstandard compressed data'
# a captive portal leaves 'HTML document text'
```

Get onto a real network (complete the captive-portal login first), then delete only the poisoned database files. Do not `rm -rf` the directory, /var/lib/pacman/local sits right next to it:

```bash
sudo rm -f /var/lib/pacman/sync/*.db /var/lib/pacman/sync/*.db.sig \
           /var/lib/pacman/sync/*.files /var/lib/pacman/sync/*.files.sig
sudo pacman -Syyu
```

If you must stay behind a proxy, also let dirmngr honour it. Add to both `/etc/gnupg/dirmngr.conf` and `/etc/pacman.d/gnupg/dirmngr.conf`:

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

## Stop AUR builds failing on debugedit or producing -debug packages

`makepkg-debug-option-debugedit-and-debug-packages` · severity: **medium** · frequency: **common** · applies to: `arch`, `aur`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `paru`, `yay`

**Symptom.** An AUR update that worked last month now fails in the packaging step:

```
==> ERROR: Cannot find the debugedit binary required for including source files in debug packages.
 -> error making: davinci-resolve-exit status 15
```

Or the build succeeds but every AUR package now comes with a `foo-debug` twin, builds take noticeably longer, and `pacman -Qtdq` lists a pile of `-debug` packages as orphans.

**Cause.** The `makepkg.conf` shipped by pacman enables `debug` (and `lto`) in `OPTIONS`. With `debug` on, makepkg compiles with debug flags and splits the symbols into an extra `<pkgname>-debug` package, and it needs the `debugedit` binary to do that. A system whose build tools came from the old base-devel group rather than the current base-devel meta package may not have debugedit, so the build stops. Where debugedit is present, the build succeeds and produces the extra package. Omarchy 4 ships this stock configuration: `/etc/makepkg.conf` has `OPTIONS=(strip docs !libtool !staticlibs emptydirs zipman purge debug lto)`, and base-devel (which pulls in debugedit) is installed, so on Omarchy you get the `-debug` packages and slower builds rather than the error.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Debug packages are only useful if you intend to debug that program. Turn the option off for your own builds in the per-user config, which makepkg reads after `/etc/makepkg.conf` and `/etc/makepkg.conf.d/*.conf`, so package updates never overwrite it:

```bash
mkdir -p ~/.config/pacman
echo 'OPTIONS+=(!debug)' >> ~/.config/pacman/makepkg.conf
```

The last occurrence of an option in the array wins, so appending `!debug` overrides the `debug` earlier in the system file. Add `!lto` the same way if long link times are the complaint.

Then rerun the AUR update (`omarchy update` on Omarchy 4, `yay -Sua` elsewhere).

If you do want debug packages, install the missing tool instead:

```bash
sudo pacman -S --needed base-devel
```

Remove `-debug` packages that were already installed (check the list before confirming):

```bash
pacman -Qq | grep -- '-debug$'
sudo pacman -Rns $(pacman -Qq | grep -- '-debug$')
```

**Verify.** `bash -c 'source /etc/makepkg.conf; source ~/.config/pacman/makepkg.conf; echo ${OPTIONS[@]}'` ends in `!debug`, and the next AUR build produces no `-debug` package in its output.

Sources: <https://forum.endeavouros.com/t/aur-update-failure-cannot-find-the-debugedit-binary/53062> · <https://wiki.archlinux.org/title/Makepkg> · <https://man.archlinux.org/man/makepkg.conf.5>

---

## Stop omarchy-update wiping custom repositories from pacman.conf

`omarchy-update-overwrites-pacman-conf` · severity: **medium** · frequency: **common** · applies to: `arch`, `desktop`, `laptop`, `omarchy`

**Symptom.** Custom repositories you added to /etc/pacman.conf (CachyOS, Chaotic-AUR, a local repo) and your mirror list vanish after `omarchy refresh pacman` or `omarchy channel set <stable|rc|edge>` (Omarchy 4), or after an `omarchy-update` whose migration reset pacman (Omarchy 3, issue 3497 on 3.2.0: "I have added CachyOS repos into pacman.conf and mirrorlist, but Omarchy-Update just replaced it out of a sudden!"). Packages installed from those repos then show as foreign in `pacman -Qm` and no longer update. A plain `omarchy update` on Omarchy 4 does not touch /etc/pacman.conf.

**Cause.** `/usr/share/omarchy/bin/omarchy-refresh-pacman` copies `/etc/pacman.conf` to `/etc/pacman.conf.bak` and `/etc/pacman.d/mirrorlist` to `/etc/pacman.d/mirrorlist.bak`, then does `sudo cp -f $OMARCHY_PATH/default/pacman/pacman-<channel>.conf /etc/pacman.conf` and the same for `mirrorlist-<channel>`. It is a wholesale overwrite, not a merge. On Omarchy 4 it runs only from `omarchy refresh pacman` and `omarchy channel set` (which calls it and then `omarchy update -y`). `omarchy update` itself never calls it and no shipped 4.x migration does. On Omarchy 3 several migrations called it, so a routine `omarchy-update` could reset the file. `/etc/pacman.conf` is owned by the pacman package as a backup file, so a package upgrade produces `/etc/pacman.conf.pacnew` instead of overwriting, and omarchy-settings owns nothing under `/etc/pacman*`. Since 2026-05-11 the script runs the user hook `~/.config/omarchy/hooks/pre-refresh-pacman` (and `pre-refresh-pacman.d/*`) after the copy and before `pacman -Syyuu`, which is where custom repositories are meant to be re-added.

> **Audit corrected this record.** Checked on this Omarchy 4.0.2 machine: `pacman -Qo /etc/pacman.conf` reports pacman 7.1.0 owns it and `pacman -Qii pacman` lists it as a backup file marked [modified], so a pacman package upgrade writes a .pacnew and never overwrites it. omarchy-settings 4.0.2 owns no file under /etc/pacman* (its only backup file is /etc/fastfetch/config.jsonc), it ships the templates in /usr/share/omarchy/default/pacman/ and the hook sample. Read /usr/share/omarchy/bin/omarchy-update, omarchy-update-system-pkgs, omarchy-channel-set and omarchy-refresh-pacman locally and against the quattro tree: `omarchy update` never calls omarchy-refresh-pacman, only `omarchy refresh pacman` and `omarchy channel set` do, and none of the 96 migrations shipped in 4.0.2 nor the 13 newer ones on quattro call it (two migrations sed-edit the [omarchy] section only). The record's symptom is the Omarchy 3 behaviour: on the master branch six migrations call omarchy-refresh-pacman, which is what issue 3497 (Omarchy 3.2.0, 2025-11-21) hit, so that issue supports the claim for Omarchy 3 only. Commit c8661403 (2025-11-22) added the .bak copies, and commit c4dbf129 (2026-05-11, PR #5681) added the `omarchy-hook pre-refresh-pacman` call between the copy and `pacman -Syyuu`, with a sample at ~/.config/omarchy/hooks/pre-refresh-pacman.d/add-custom-repo.sample that Omarchy installs from /etc/skel (present in this home). That hook is the supported way to keep a custom repo, and the record's ~/.config/omarchy/extra-repos.conf plus manual grep/tee is an invented mechanism nothing reads. The record's `sudo pacman -Syu` is blocked by the ALPM update guard on Omarchy 4 and is redundant anyway because omarchy-refresh-pacman runs `pacman -Syyuu` itself after the hook. The cited master raw URLs still return 200 but are the Omarchy 3 tree. Not exercised: I did not run omarchy-refresh-pacman or the hook, no .bak exists on this machine, and the exact sed placement was read from the sample, not executed.
>
> *The Cause above was rewritten on 2026-09-07 to match this note. The Fix was corrected by the audit itself.*

> ⚠️ **Risk.** Only ONE level of backup is kept: `omarchy-refresh-pacman` overwrites `/etc/pacman.conf.bak` and `/etc/pacman.d/mirrorlist.bak` on every run, and `omarchy channel set` runs it every time, so a second refresh loses the original. `omarchy-hook` prints `Hook failed: <path>` and carries on when a hook exits non-zero, so a broken hook lets `pacman -Syyuu` run without your repositories and packages from them stop updating silently. Mixing third-party repos (CachyOS, Chaotic-AUR) with Omarchy's own mirror can deliver packages from different snapshots and cause partial-upgrade breakage, and a repo included above `[core]` wins over core for same-named packages.

**Fix.**

Recover what was there. The script keeps one backup of each file:

```bash
sudo diff -u /etc/pacman.conf.bak /etc/pacman.conf
sudo diff -u /etc/pacman.d/mirrorlist.bak /etc/pacman.d/mirrorlist
```

Omarchy 4: keep your repositories in a snippet and let the shipped hook re-add them on every refresh or channel switch. Put the repo sections in `/etc/pacman.d/custom-repos.conf`:

```bash
sudo tee /etc/pacman.d/custom-repos.conf >/dev/null <<'EOF'
[chaotic-aur]
Include = /etc/pacman.d/chaotic-mirrorlist
EOF
```

Enable the sample hook Omarchy installed in your home (it inserts `Include = /etc/pacman.d/custom-repos.conf` above `[core]`, so those repos take priority. Edit the `sed` line in the hook if you want them after `[omarchy]` instead):

```bash
cd ~/.config/omarchy/hooks/pre-refresh-pacman.d
mv add-custom-repo.sample add-custom-repo
chmod +x add-custom-repo
```

If the sample is missing, copy it from `/usr/share/omarchy/config/omarchy/hooks/pre-refresh-pacman.d/add-custom-repo.sample`. Apply it now without waiting for the next refresh:

```bash
bash ~/.config/omarchy/hooks/pre-refresh-pacman.d/add-custom-repo
omarchy update
```

Do not run `sudo pacman -Syu` on Omarchy 4: the update guard aborts it, and `omarchy refresh pacman` already runs `pacman -Syyuu` after the hook.

Omarchy 3 or plain Arch (no hook mechanism): re-append the section to the fresh file and sync:

```bash
sudo tee -a /etc/pacman.conf >/dev/null <<'EOF'

[chaotic-aur]
Include = /etc/pacman.d/chaotic-mirrorlist
EOF
sudo pacman -Syu
```

**Verify.** `pacman-conf --repo-list` lists your custom repo alongside core/extra/multilib/omarchy, and `sudo pacman -Syu` syncs its database.

Sources: <https://github.com/basecamp/omarchy/issues/3497> · <https://raw.githubusercontent.com/basecamp/omarchy/master/bin/omarchy-refresh-pacman> · <https://raw.githubusercontent.com/basecamp/omarchy/master/default/pacman/pacman-stable.conf> · <https://github.com/basecamp/omarchy/commit/c86614039e3184c300cb8cfce5ba139a83eb1656> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-refresh-pacman> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-channel-set> · <https://github.com/basecamp/omarchy/blob/quattro/bin/omarchy-update> · <https://github.com/basecamp/omarchy/blob/quattro/config/omarchy/hooks/pre-refresh-pacman.d/add-custom-repo.sample> · <https://github.com/basecamp/omarchy/blob/quattro/default/pacman/pacman-stable.conf> · <https://github.com/basecamp/omarchy/blob/quattro/install/post-install/pacman.sh> · <https://github.com/basecamp/omarchy/blob/master/bin/omarchy-update>

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

If you dual-boot Windows, make Windows use UTC as well rather than switching Linux to localtime. In an elevated Windows cmd:

```
reg add "HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /t REG_DWORD /d 1 /f
```

**Verify.** `timedatectl` shows `System clock synchronized: yes` and the correct date. `sudo pacman -Syu` no longer reports invalid signatures.

Sources: <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://wiki.archlinux.org/title/Mirrors>

---

## Handle 'removing X breaks dependency Y required by Z'

`removing-package-breaks-dependency` · severity: **medium** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Uninstalling something is refused:

```
$ sudo pacman -Rs krunner5
checking dependencies...
error: failed to prepare transaction (could not satisfy dependencies)
:: removing krunner5 breaks dependency 'krunner' required by akonadi-search
:: removing krunner5 breaks dependency 'krunner5' required by milou
```

On Omarchy 4 it can name Omarchy itself, for example `:: removing snapper breaks dependency 'snapper' required by omarchy`. It also turns up mid-upgrade, when a package dropped from the repositories has to go before the upgrade can continue.

**Cause.** pacman will not remove a package that another installed package declares as a dependency, because the dependent would break. `-s` only removes dependencies nobody else needs. It never removes the packages that depend on your target. On Omarchy 4 the `omarchy` package itself depends on its core components (`hyprland`, `quickshell`, `uwsm`, `sddm`, `limine`, `limine-mkinitcpio-hook`, `limine-snapper-sync`, `snapper`, `pipewire`, `wireplumber` and more, see `pacman -Qi omarchy`), so removing one of those means removing Omarchy. In the upgrade case, an old package left behind by a repository split still satisfies something, and its replacement is not yet installed.

> **Audit corrected this record.** Thread 295233 has the exact krunner5 output, loqs's `pacman -Syu krunner` and Lone_Wolf's TTY `pacman -Rdd krunner5` then `pacman -Syu`. Thread 254564 shows the 'breaks dependency ... required by' refusal. Confirmed locally on 4.0.4-1: `pacman -Qi omarchy` depends on hyprland, quickshell, uwsm, sddm, limine, limine-mkinitcpio-hook, limine-snapper-sync, snapper, pipewire, wireplumber and pacman-contrib (so pactree is present). omarchy-menu.jsonc has a 'Remove' menu, and omarchy-remove-* commands exist in /usr/share/omarchy/bin. The ALPM guard refuses -S plus -u unless OMARCHY_ALLOW_DIRECT_PACMAN=1, so the Omarchy branches are right. The defect is in the danger field. It covers -Rdd but not `pacman -Rsc`, which the fix offers before the Omarchy branch. Cascade removal of any core component (snapper, limine, hyprland and so on) removes the `omarchy` package itself, and with it /usr/share/omarchy and everything that requires it. Here that includes flea-bin, which `pacman -Qi omarchy` lists under Required By. The danger is corrected to cover it. Nothing was removed.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** `pacman -Rsc` removes every package that depends on the target, recursively. On Omarchy 4, if the target is one of Omarchy's core components (`pacman -Qi omarchy` lists them), that includes the `omarchy` package itself, which takes `/usr/share/omarchy` and every Omarchy command with it. Always run `pacman -Rsc --print <package>` first and stop if `omarchy` or `omarchy-settings` is in the list. `pacman -Rdd` removes a package while other installed packages still depend on it. Until the upgrade that follows completes, those dependents can fail to start. Run both commands back to back from a TTY. On Omarchy 4, never follow `-Rdd` with a bare `sudo pacman -Syu`: the update guard refuses it and leaves the system with the package removed and nothing upgraded.

**Fix.**

See who needs the package:

```bash
pacman -Qi <package> | grep 'Required By'
pactree -r <package>            # full reverse tree, from pacman-contrib
```

**You want the dependents gone too.** Preview, then remove the package and everything that depends on it. Read the list before confirming:

```bash
pacman -Rsc --print <package>
sudo pacman -Rsc <package>
```

**The dependent is `omarchy` (Omarchy 4).** Stop. That component is part of the system. Use Omarchy's own remover for optional software (`Super + Space` > Remove, or the `omarchy-remove-*` commands) and leave the core packages installed.

**Mid-upgrade, an obsolete package blocks it.** Install the replacement in the same full upgrade so the old one can be replaced:

```bash
sudo pacman -Syu krunner                                       # plain Arch
sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syu krunner      # Omarchy 4, then run: omarchy update
```

Only as a last resort, from a TTY rather than the desktop, remove the single obsolete package ignoring dependencies and upgrade immediately. Plain Arch:

```bash
sudo pacman -Rdd krunner5
sudo pacman -Syu
```

Omarchy 4, where a direct `pacman -Syu` is refused by the update guard:

```bash
sudo pacman -Rdd krunner5
omarchy update
```

**Verify.** `pacman -Dk` reports no missing dependencies after the change.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=295233> · <https://bbs.archlinux.org/viewtopic.php?id=254564> · <https://wiki.archlinux.org/title/Pacman>

---

## Get a large AUR build past 'Killed signal terminated program cc1plus'

`aur-build-killed-out-of-memory` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `aur`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `paru`, `yay`

**Symptom.** Building a big C++ project from the AUR (a browser, an Electron app, a game engine, a CAD tool) runs for a long time, the desktop crawls, then:

```
c++: fatal error: Killed signal terminated program cc1plus
compilation terminated.
==> ERROR: A failure occurred in build().
    Aborting...
 -> error making: <package>
```

and `journalctl -k` shows `Out of memory: Killed process ... (cc1plus)`.

On Omarchy 4 the terminal window running the build can instead close outright, taking `yay` or `omarchy update` with it, and `journalctl -k` shows nothing. In that case systemd-oomd killed the terminal, and the kill is logged by `systemd-oomd`.

**Cause.** Memory ran out. Large C++ translation units can each need gigabytes of RAM, and the build runs many in parallel. Setting `MAKEFLAGS=-j1` only limits builds driven by make. CMake with Ninja, Meson, Rust's cargo and Mozilla's mach pick their own job count, usually one per CPU thread, and ignore MAKEFLAGS. Link-time optimisation, which makepkg enables by default (`lto` in `OPTIONS` in `/etc/makepkg.conf`), raises peak memory further at the link step.

What kills the build differs. On plain Arch it is usually the kernel's OOM killer taking a compiler process. Omarchy 4 also runs systemd-oomd. `omarchy-settings` ships `/etc/systemd/oomd.conf.d/10-omarchy.conf` (act when memory pressure stays above 50% for 20 seconds) and `/usr/lib/systemd/user/app.slice.d/10-oomd.conf`, which makes everything in the user's `app.slice` a kill candidate. A terminal started from the desktop lives in `app.slice`, so oomd can kill the whole terminal and every build process inside it before the kernel OOM killer ever acts. Omarchy 4 also swaps to zram sized to RAM (`/usr/lib/systemd/zram-generator.conf.d/90-omarchy.conf`). That helps, but it cannot cover a build that needs several times the physical memory.

> **Audit corrected this record.** The kernel OOM part is right for plain Arch. The forum thread (231534) shows MAKEFLAGS=-j1 ignored by mach, with -bin and swap as the answers. /etc/makepkg.conf has `lto` in OPTIONS and makepkg sources the user file after it. The record misses the Omarchy 4 mechanism its own cited sources describe. Confirmed locally: omarchy-settings 4.0.4-1 owns /etc/systemd/oomd.conf.d/10-omarchy.conf (50% pressure for 20s) and /usr/lib/systemd/user/app.slice.d/10-oomd.conf (ManagedOOMMemoryPressure=kill, ManagedOOMSwap=kill), and systemd-oomd is enabled and active. A terminal launched by uwsm-app runs in app.slice, so on Omarchy the more likely outcome is that oomd kills the terminal's whole scope, taking yay or omarchy update with it. That leaves nothing in `journalctl -k`, so the record's symptom and verify step miss it. zram is confirmed (zram-size = ram, zstd, from 90-omarchy.conf owned by omarchy-settings). The fix also said nothing about CMake, which honours CMAKE_BUILD_PARALLEL_LEVEL for `cmake --build` (CMake docs, and PR #12778 uses it). Its 'add disk swap' was vague, and on a btrfs root a swapfile must sit in its own subvolume. Cause, symptom, fix and verify are corrected. Not reproduced.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

First check whether a prebuilt package exists. It removes the build entirely:

```bash
yay -Ss <name>-bin
```

If you must build, cap parallelism and LTO in your per-user makepkg config. makepkg reads it after `/etc/makepkg.conf`, and `omarchy update` builds AUR packages through the same makepkg, so it applies there too:

```bash
mkdir -p ~/.config/pacman
cat >> ~/.config/pacman/makepkg.conf <<'EOF'
MAKEFLAGS="-j2"
OPTIONS+=(!lto)
EOF
```

For build systems that ignore MAKEFLAGS, set their own variable in the shell you build from:

```bash
export CARGO_BUILD_JOBS=2             # Rust / cargo
export CMAKE_BUILD_PARALLEL_LEVEL=2   # CMake, when the PKGBUILD builds with cmake --build
yay -S <package>
```

Ninja and Meson have no environment variable for job count. For a PKGBUILD that calls `ninja` or `meson compile` directly, edit `build()` to pass `-j2` (`yay -S --editmenu <package>`).

If a build still runs out of memory, add disk swap for the duration of the build.

**Omarchy 4 (btrfs root).** Put the swapfile in its own subvolume, as Omarchy's hibernation setup does with `/swap`, because btrfs cannot snapshot a subvolume that holds an active swapfile and snapper snapshots `@`:

```bash
sudo btrfs subvolume create /swap-build
sudo btrfs filesystem mkswapfile --size 16g /swap-build/swapfile
sudo swapon /swap-build/swapfile
# build, then remove it
sudo swapoff /swap-build/swapfile
sudo btrfs subvolume delete /swap-build
```

**Plain Arch (ext4 root):**

```bash
sudo mkswap -U clear --size 16G --file /swapfile
sudo swapon /swapfile
# build, then remove it
sudo swapoff /swapfile
sudo rm /swapfile
```

Otherwise build on a bigger machine.

**Verify.** No new kill during the rebuild: `journalctl -k -b | grep -i 'out of memory'` prints nothing new, and on Omarchy 4 `journalctl -u systemd-oomd -b | grep -i killed` prints nothing new. `pacman -Q <package>` shows the new version.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=231534> · <https://wiki.archlinux.org/title/Makepkg> · <https://github.com/omacom/omarchy/blob/quattro/etc/systemd/oomd.conf.d/10-omarchy.conf> · <https://github.com/omacom/omarchy/blob/quattro/default/systemd/user/app.slice.d/10-oomd.conf> · <https://man.archlinux.org/man/systemd-oomd.service.8> · <https://github.com/omacom/omarchy/pull/12778> · <https://cmake.org/cmake/help/latest/envvar/CMAKE_BUILD_PARALLEL_LEVEL.html>

---

## Stop large AUR builds failing with 'No space left on device' on a tmpfs /tmp

`aur-build-no-space-left-tmpfs-tmp` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** A big AUR package (a browser, an Electron app, a Rust or Go project, a toolchain) fails partway through compiling or packaging with one of these:

```
... Disk quota exceeded
==> ERROR: A failure occurred in build().
    Aborting...
 -> error making: <pkgname>
```

```
... No space left on device
==> ERROR: A failure occurred in build().
    Aborting...
 -> error making: <pkgname>
```

Small packages build fine. `df -h /` shows plenty of free disk, but `df -h /tmp` climbs while the build runs and frees itself the moment the build dies. On systemd 258 and later, Omarchy 4 included, the usual message is `Disk quota exceeded` with /tmp only about 80% full, because the per-user quota on /tmp runs out before the tmpfs does.

**Cause.** `/tmp` is a tmpfs on Arch and Omarchy 4, mounted by systemd's `tmp.mount` with `size=50%`, so its ceiling is half of RAM (16G on a 32 GB machine, checked on Omarchy 4.0.4-1 with `df -h /tmp` and `systemctl cat tmp.mount`). It is not a disk. Since systemd v258, /tmp is also mounted with `usrquota` (present on Omarchy 4.0.4-1, systemd 261), and the Arch wiki says each user gets 80% of the tmpfs size. A build running as your user therefore fails with `Disk quota exceeded` when its files reach about 40% of RAM, before the tmpfs itself is full.

An AUR build only lands there when something points it there:

1. `BUILDDIR=/tmp/makepkg` in `/etc/makepkg.conf`, a drop-in under `/etc/makepkg.conf.d/`, or a user `makepkg.conf`. The Arch wiki suggests exactly this for speed and warns to avoid it for large packages. makepkg then puts `src/` and `pkg/` under `$BUILDDIR`, whichever helper called it.
2. An AUR helper whose build directory was moved to `/tmp` (`yay --builddir`, `AURDEST`, paru's `CloneDir`).
3. Build tools that write their own scratch files under `$TMPDIR` (default `/tmp`) even when the source tree is on disk.

yay's own default is `$XDG_CACHE_HOME/yay`, falling back to `~/.cache/yay`, which is on disk. A stock Omarchy 4 `/etc/makepkg.conf` ships `#BUILDDIR=/tmp/makepkg` commented out, so a stock machine only hits this through case 3 or a setting the user added.

> **Audit corrected this record.** What held, checked on this machine: /tmp is tmpfs from systemd's tmp.mount with `size=50%%` (16G on 31 GiB RAM), /etc/makepkg.conf line 79 is `#BUILDDIR=/tmp/makepkg`, and /etc/makepkg.conf.d holds only fortran.conf and rust.conf. makepkg(8) lists BUILDDIR as an environment override. makepkg.conf(5) gives the user config order ($XDG_CONFIG_HOME/pacman/makepkg.conf after the system file). yay.8 documents --builddir and AURDEST, and yay's dirs.go defaults to $XDG_CACHE_HOME/yay. The Makepkg wiki has the BUILDDIR=/tmp/makepkg tip and its warning about large packages, and the Tmpfs wiki has the remount commands. What the record misses: systemd 261 on this machine mounts /tmp with `usrquota` (findmnt shows it, and tmp.mount carries `x-systemd.graceful-option=usrquota`). The Tmpfs wiki says that since systemd v258 each user gets a quota of 80% of the tmpfs size, and that remounting larger does not raise it. So on Omarchy 4 the build usually fails with `Disk quota exceeded` at about 80% full, not at 100% with `No space left on device`. The record's resize recipe also does not help unless the quota is raised too. Symptom, cause, fix and danger are rewritten to cover the quota. Not exercised: I did not read my user's actual quota value, because quota-tools is not installed, and I ran no build.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Do not `mount -o remount` a smaller size onto a /tmp that is in use, and do not `mount -a` after editing fstab with files in /tmp: running programs lose their lock and socket files there. Growing the tmpfs or raising the /tmp quota lets a build consume RAM and swap, which on a small machine trades this error for an out-of-memory kill. Set any `setquota` limit below the tmpfs size you mounted.

**Fix.**

Find which of the three it is:

```bash
findmnt /tmp                     # FSTYPE tmpfs, and whether usrquota is set
df -h /tmp /home
grep -nE '^\s*BUILDDIR' /etc/makepkg.conf /etc/makepkg.conf.d/*.conf \
  ~/.config/pacman/makepkg.conf ~/.makepkg.conf 2>/dev/null
grep -n builddir ~/.config/yay/config.json 2>/dev/null
echo "AURDEST=$AURDEST TMPDIR=$TMPDIR"
```

If a `BUILDDIR` under `/tmp` turns up, the simplest fix is to comment it out where you set it. To keep it for small packages but build one large package on disk, override it for that run only:

```bash
mkdir -p ~/.cache/makepkg-build
BUILDDIR=$HOME/.cache/makepkg-build yay -S <pkgname>
```

To move it permanently for your user without touching `/etc`, set it in the user config, which makepkg reads after the system file:

```bash
mkdir -p ~/.config/pacman ~/.cache/makepkg-build
echo 'BUILDDIR="$HOME/.cache/makepkg-build"' >> ~/.config/pacman/makepkg.conf
```

If it is the build tool's scratch space (case 3), point `TMPDIR` at disk for that build:

```bash
mkdir -p ~/.cache/tmp-build
TMPDIR=$HOME/.cache/tmp-build yay -S <pkgname>
rm -rf ~/.cache/tmp-build
```

Moving the build to disk avoids both the tmpfs size and the per-user quota, and is the fix to prefer.

Growing the tmpfs instead is a temporary change until the next reboot. It uses RAM and swap, so only do it on a machine with memory to spare. On systemd 258 and later (Omarchy 4), a remount does not raise the per-user quota, so a larger /tmp alone does not stop `Disk quota exceeded`. The Arch wiki Tmpfs page raises the quota with `setquota` from `quota-tools`. Keep the limit below the new tmpfs size:

```bash
findmnt -no OPTIONS /tmp | tr , '\n' | grep quota    # usrquota: a per-user limit applies
sudo mount -o remount,size=80% /tmp
sudo pacman -S quota-tools
sudo setquota -u "$USER" 20G 20G 0 0 /tmp
```

Omarchy 4: `omarchy update` runs `yay -Sua` with your user's environment and makepkg configuration, so a persistent fix belongs in `~/.config/pacman/makepkg.conf`. An exported `TMPDIR` in one terminal does not reach a later update. Retry the failed package with `yay -S <pkgname>` after the change.

**Verify.** Re-run the build and watch `df -h /tmp` in a second terminal: it should stay flat. The package installs and `pacman -Q <pkgname>` shows the new version.

Sources: <https://wiki.archlinux.org/title/Makepkg> · <https://wiki.archlinux.org/title/Tmpfs> · <https://man.archlinux.org/man/makepkg.conf.5> · <https://github.com/Jguer/yay/blob/next/doc/yay.8>

---

## Fix Go AUR rebuilds failing on 'rm: cannot remove ... Permission denied'

`aur-go-module-cache-permission-denied` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `aur`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `paru`, `yay`

**Symptom.** Updating a Go program from the AUR fails before it even compiles, with thousands of lines like:

```
==> Removing existing $srcdir/ directory...
rm: cannot remove '/home/user/.cache/yay/hyprmoncfg/src/go-mod/github.com/!make!now!just/heredoc@v1.0.0/LICENSE': Permission denied
==> ERROR: An unknown error has occurred. Exiting...
 -> error making: hyprmoncfg-signal: user defined signal 1
 -> Failed to install the following packages. Manual intervention is required:
```

On Omarchy's edge channel, whose AUR step exits non-zero when yay fails, `omarchy update` then ends with `Something went wrong during the update!` even though the system packages and migrations already finished. On stable 4.0.4 the same yay error is printed in the middle of the run and the update carries on to its remaining steps.

**Cause.** Go makes every directory and file in its module cache read-only on purpose. A PKGBUILD that points the cache inside the build tree (for example `GOMODCACHE="${srcdir}/go-mod"`) without passing `-modcacherw` to `go build` leaves a read-only tree behind in the AUR helper's build directory. The first build works. The next build fails because makepkg starts by deleting the old `$srcdir`, and `rm` running as the user cannot delete the contents of read-only directories. `yay --cleanafter`, which Omarchy's AUR update step passes, does not remove it either. How the failure surfaces in `omarchy update` depends on the version. On the `quattro` branch (the edge channel) `omarchy-update-aur-pkgs` runs `yay ... || exit 1`, so one broken AUR package marks the whole update as failed. The stable 4.0.4 script has no `|| exit 1` and ends on an `echo`, so the step returns success and the update continues.

> **Audit corrected this record.** Issue #13334 (open) has the exact output, the GOMODCACHE cause and the chmod plus rm workaround. Manjaro pamac issue 1114 shows the same read-only Go cache failure with go-yq. The fix is correct. The Omarchy claim is version-dependent and wrong for the current stable release. The reporter ran edge (4.0.0.r2304), and the quattro branch's omarchy-update-aur-pkgs ends the yay call with `|| exit 1`. The installed 4.0.4-1 script on this machine (upstream latest is v4.0.4) has no `|| exit 1` and no `set -e`, and its last command is `echo`. On stable 4.0.4 a yay failure is therefore printed and the update carries on to its later steps without the 'Something went wrong' message. Symptom and cause are corrected to say which channel ends the update. Not reproduced. Second audit confirmed the corrected text: Second pass on the record as corrected on 2026-10-04, whose channel distinction still holds. Issue #13334 (open) has the exact output, the GOMODCACHE=${srcdir}/go-mod cause, the -modcacherw remedy and the chmod plus rm workaround, on edge 4.0.0.r2304. Confirmed locally: the 4.0.4-1 omarchy-update-aur-pkgs has no `|| exit 1` and ends with `echo`, and omarchy-update runs under `set -e` with an ERR trap that prints 'Something went wrong during the update!', so on stable a yay failure does not trip it. The quattro copy fetched today ends the yay call with `|| exit 1`, so on edge it does. Manjaro pamac issue 1114 shows the same read-only Go module cache failure with go-yq. yay's build directory ~/.cache/yay/<pkg> holding makepkg's src/ matches the reporter's path. The rm -rf is scoped to a user cache directory. Not reproduced.
>
> *The Cause above was rewritten on 2026-10-04 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Make the old tree writable and delete it, then rerun the update. Replace `hyprmoncfg` with the failing package's directory:

```bash
chmod -R u+w ~/.cache/yay/hyprmoncfg/src
rm -rf ~/.cache/yay/hyprmoncfg/src
```

paru keeps its build trees in `~/.cache/paru/clone/<package>/` instead. A build run by hand with makepkg keeps it in the PKGBUILD's own `src/`.

**Omarchy 4:** `omarchy update`. **Elsewhere:** `yay -Sua`.

The real fix belongs in the PKGBUILD: build with `go build -modcacherw ...` or set `export GOFLAGS="-modcacherw"` in `build()`. Leave a comment on the package's AUR page so the maintainer adds it. It recurs on every update until then.

**Verify.** `ls ~/.cache/yay/<package>/src` no longer exists before the build, and the AUR update completes with the package at its new version in `pacman -Q <package>`.

Sources: <https://github.com/omacom/omarchy/issues/13334> · <https://gitlab.manjaro.org/applications/pamac/-/issues/1114> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-aur-pkgs>

---

## Fix 'could not register database (database already registered)'

`could-not-register-database-already-registered` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `garuda`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Every pacman or AUR helper command starts with an error, and some refuse to run:

```
error: could not register 'multilib' database (database already registered)
```

The repository name varies: `multilib`, `chaotic-aur`, `sublime-text`, or any third-party repo. It often starts right after following a guide that said to add a repository.

**Cause.** The same repository section appears twice in `/etc/pacman.conf`, or once in pacman.conf and again in a file it pulls in with `Include =`. Since pacman 4.2 a duplicate section name is rejected rather than silently merged. A common way to get here is adding `[multilib]` from the Arch wiki to a pacman.conf that already enables it (Omarchy 4's pacman.conf already has `[multilib]` enabled), or running a repository setup script twice.

> **Audit corrected this record.** Thread 191802: Trilby says the error only occurs when a repository is listed twice and Allan says pacman 4.2 got stricter about it, which supports the cause. Omarchy 4's /etc/pacman.conf enables [multilib] (confirmed locally), and omarchy-refresh-pacman replaces the whole file (read on 4.0.4-1). The diagnosis step is still incomplete. pacman.conf allows globs in `Include =`, and the record's `xargs -r grep` passes the glob through literally, so a duplicate brought in by `Include = /etc/pacman.d/*.conf` is never shown, with the error hidden by `2>/dev/null`. Tested here on a copy of pacman.conf with a glob Include carrying a second [multilib]: the record's command printed nothing. A shell loop with an unquoted variable expands the glob and found it. `pacman-conf --config <copy> --repo-list` does not refuse duplicates. It printed multilib twice, so `pacman-conf --repo-list | sort | uniq -d` names the duplicate directly and is now the first step. Nothing was edited on the live file.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Name the duplicated repository. `pacman-conf` reads pacman.conf and every file it includes, globs too, and lists a duplicate twice instead of refusing it:

```bash
pacman-conf --repo-list | sort | uniq -d
```

Find where each copy is defined, in pacman.conf and in every included file (the loop expands glob `Include =` lines, which `xargs` would not):

```bash
grep -n '^\[' /etc/pacman.conf
for inc in $(sed -n 's/^[[:space:]]*Include[[:space:]]*=[[:space:]]*//p' /etc/pacman.conf | sort -u); do grep -Hn '^\[' $inc; done 2>/dev/null
```

Back up the file, then delete one complete copy of that section (its `[name]` line and the `Include =` or `Server =` and `SigLevel =` lines under it). Keep the one in the position you want, because order sets repository priority. If the second copy sits inside an included file, remove it there, or remove the `Include =` line that pulls it in:

```bash
sudo cp /etc/pacman.conf /etc/pacman.conf.bak
sudoedit /etc/pacman.conf
```

Then confirm that the first command prints nothing, and upgrade:

```bash
pacman-conf --repo-list | sort | uniq -d
```

**Omarchy 4:** `omarchy update`. **Plain Arch:** `sudo pacman -Syu`.

On Omarchy 4, `omarchy refresh pacman` also clears duplicates because it replaces the whole file, but it drops every third-party repository too.

**Verify.** `pacman-conf --repo-list` lists each repository exactly once and pacman commands run without the error.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=191802> · <https://man.archlinux.org/man/pacman.conf.5>

---

## Stop pacman aborting downloads with 'Operation too slow'

`download-operation-too-slow-timeout` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Downloads die after a few seconds even though the connection is fine, often on a large package:

```
error: failed retrieving file 'foo-1.2-1-x86_64.pkg.tar.zst' from mirror.example.org : Operation too slow. Less than 1 bytes/sec transferred the last 10 seconds
warning: failed to retrieve some files
error: failed to commit transaction (failed to retrieve some files)
```

Sometimes followed by `HTTP server doesn't seem to support byte ranges. Cannot resume.` as it moves to the next mirror.

**Cause.** pacman's built-in downloader applies a low-speed limit: a transfer that moves less than 1 byte per second for 10 seconds is aborted. A server or proxy that is slow to start sending (a cold cache, a security gateway scanning the file, a congested mirror, a VM NAT) trips it while the real throughput would have been fine. With several mirrors pacman retries the next one. On Omarchy 4 the mirrorlist holds exactly one server, so one stalled transfer fails the whole download step.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Delete any partial file for the failing package first, then retry:

```bash
sudo find /var/cache/pacman/pkg -name '*.part' -delete
```

**Plain Arch, one transaction:**

```bash
sudo pacman -Syu --disable-download-timeout
```

**Permanently, any distro.** Add the option under `[options]` in `/etc/pacman.conf`:

```ini
[options]
DisableDownloadTimeout
```

**Omarchy 4.** `omarchy update` does not pass extra flags to pacman, so use the config option above and then run `omarchy update`. `omarchy refresh pacman` and `omarchy channel set` overwrite `/etc/pacman.conf`, so re-apply it from the hook Omarchy runs right after that copy:

```bash
mkdir -p ~/.config/omarchy/hooks/pre-refresh-pacman.d
cat > ~/.config/omarchy/hooks/pre-refresh-pacman.d/50-download-timeout <<'EOF'
grep -q '^DisableDownloadTimeout' /etc/pacman.conf || sudo sed -i '/^\[options\]/a DisableDownloadTimeout' /etc/pacman.conf
EOF
```

If transfers are genuinely slow rather than slow to start, rank mirrors (plain Arch) instead of only lifting the timeout.

**Verify.** `pacman-conf DisableDownloadTimeout` prints the option name when it is set, and the next upgrade downloads the package that previously aborted.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=173909> · <https://man.archlinux.org/man/pacman.conf.5>

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

## Fix a package that exists in both [omarchy] and the AUR updating from the wrong source

`omarchy-repo-shadows-aur-package` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `laptop`, `omarchy`

**Symptom.** One of these, for a package such as `visual-studio-code-bin`, `cursor-bin` or `localsend-bin`:

- You installed it from the AUR to get a newer version, and now every update prints
```
warning: visual-studio-code-bin: local (1.140.0-1) is newer than omarchy (1.138.0-1)
```
and the package never moves again, even when the AUR has a newer release. `yay -Qua` does not list it.
- `yay -S visual-studio-code-bin`, or Install > AUR in the Omarchy menu on older releases, downloaded the [omarchy] build instead of the AUR one (issue #4577).
- A package you built from the AUR was silently replaced by the [omarchy] build at the next `omarchy update`.

**Cause.** pacman does not record which repository or AUR build a package came from. It matches by name. If a sync repository carries a package with the same name, the installed copy is treated as that repo's package: `pacman -Syu` upgrades it from the repo when the repo version is higher, and only warns `local (...) is newer than omarchy (...)` when it is lower (libalpm `check_literal`, which downgrades only with `-uu`).

yay decides what is an AUR package the same way: any installed package whose name is found in a sync database is a repo package, and only the rest are foreign (yay `getPackageNamesBySource`). So `yay -Sua`, which is what `omarchy update` runs for AUR, skips it forever. A bare name in `yay -S` also resolves to the repo first.

The [omarchy] repository carries many AUR names (`pacman -Slq omarchy | grep -E -- '-(bin|git)$'`). An Omarchy maintainer says in issue #4577 that it is rebuilt from the AUR every 6 hours, so it is usually close behind the AUR rather than far behind on purpose. On 2026-10-05 the live stable repo had `visual-studio-code-bin 1.140.0-1`, the same as the AUR, and `cursor-bin 3.23.12-1` against the AUR's `3.23.23-1`. Any window where the AUR is ahead, or a local sync database that has not been refreshed, is enough for a hand-built AUR copy to be stranded or replaced.

> **Audit corrected this record.** The mechanism holds. libalpm sync.c check_literal upgrades when the repo version is higher and downgrades only with enable_downgrade. yay's getPackageNamesBySource in high_level.go treats any installed name found in a sync DB as a repo package. AUR builds show `Validated By : None` on this machine, the awk|comm listing runs cleanly, and the ALPM guard (omarchy-update-pacman-guard) blocks only -S together with -u, so `pacman -S omarchy/<pkg>` is allowed. Issue #4577 supports the menu symptom and the edge-channel suggestion. The cause's numbers are wrong. They came from this workstation's stale sync DB, dated 2026-09-18, not from the live repo. Fetching https://pkgs.omarchy.org/stable/x86_64/omarchy.db on 2026-10-05 gave 254 packages, with visual-studio-code-bin 1.140.0-1 (equal to the AUR) and cursor-bin 3.23.12-1 (AUR 3.23.23-1). The claim that the repo 'lags the AUR on purpose' is unsupported: in #4577 an Omarchy maintainer says it is rebuilt from the AUR every 6 hours and treated the lag as a bug. Cause rewritten, and frequency lowered to occasional because the repo tracks the AUR closely. The fix gains a note that the edge channel swaps in omarchy-dev and omarchy-settings-dev (omarchy-channel-set).
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Option 1 can downgrade the package. For editors and browsers that is usually harmless, but an application that migrated its profile or settings format in the newer version may not read it after a downgrade. Close the application first and back up its config directory if it matters.

**Fix.**

List every installed package that was built locally (from the AUR) but has the same name as a repo package. `Validated By: None` marks a package installed from a local file:

```bash
LC_ALL=C pacman -Qi \
  | awk -F' *: ' '/^Name/{n=$2} /^Validated By/{if($2=="None") print n}' \
  | sort | comm -12 - <(pacman -Slq | sort -u)
```

For each one, compare the three versions:

```bash
pkg=visual-studio-code-bin
pacman -Q "$pkg"
pacman -Si "omarchy/$pkg" | grep -E '^(Repository|Version)'
yay -Si "aur/$pkg" | grep -E '^(Repository|Version)'
```

Option 1, recommended: go back to the [omarchy] build so `omarchy update` maintains it. An explicit `-S` of a repo package is allowed by the update guard and will downgrade if the repo is behind, printing `warning: downgrading package ...`:

```bash
sudo pacman -S "omarchy/$pkg"
```

If you need newer versions from Omarchy itself, the Update > Channel menu offers the edge channel (issue #4577). Switching channel rewrites `/etc/pacman.conf` and the mirrorlist, and edge also replaces `omarchy` and `omarchy-settings` with `omarchy-dev` and `omarchy-settings-dev`, so treat it as a change of release track and not a per-package setting.

Option 2: keep the AUR build and update it by hand, because no automatic path will:

```bash
yay -S "aur/$pkg"
```

The `aur/` prefix forces the AUR. Expect `omarchy update` to swap it back to the [omarchy] build whenever the repo version passes yours.

Plain Arch with another unofficial repo (chaotic-aur, CachyOS) has the same shadowing. The listing above finds it there too.

**Verify.** `pacman -Qi <pkg> | grep 'Validated By'` shows a signature or checksum (repo build) for Option 1. The awk listing above prints nothing, or only the packages you chose to keep on Option 2. The `is newer than omarchy` warning no longer appears in `/tmp/omarchy-update.log`.

Sources: <https://github.com/omacom/omarchy/issues/4577> · <https://github.com/Jguer/yay/blob/next/pkg/db/ialpm/high_level.go> · <https://gitlab.archlinux.org/pacman/pacman/-/blob/master/lib/libalpm/sync.c> · <https://aur.archlinux.org/packages/visual-studio-code-bin> · <https://pkgs.omarchy.org/stable/x86_64/omarchy.db> · <https://aur.archlinux.org/rpc/v5/info?arg[]=visual-studio-code-bin&arg[]=cursor-bin&arg[]=localsend-bin>

---

## Fix a local or file:// repository after the pacman 7.0.0 upgrade

`pacman7-local-repo-alpm-download-user` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** After the pacman 7.0.0 upgrade, a local or file:// repository stops working: pacman cannot read the packages it could read yesterday, with permission-denied style retrieval failures against your own repo directory.

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

**Verify.** `sudo pacman -Sy` syncs the local repo database and `sudo pacman -S <pkg-from-local-repo>` installs it. `namei -l /path/to/local/repo/repo.db` shows the alpm group can traverse every component.

Sources: <https://archlinux.org/news/manual-intervention-for-pacman-700-and-local-repositories-required/> · <https://archlinux.org/news/> · <https://wiki.archlinux.org/title/Pacman>

---

## Fix 'signature is invalid' on a signed repo database caused by a mirror mid-sync

`signed-repo-database-signature-invalid-mirror-mismatch` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** A third-party repository that signs its databases (CachyOS is one) suddenly fails to sync, with a key that worked yesterday:

```
error: cachyos: signature from "CachyOS <admin@cachyos.org>" is invalid
error: failed to synchronize all databases (invalid or corrupted database (PGP signature))
```

The keyring is current, `pacman-key --list-keys` shows the key locally signed, and nothing changed on your side. Sometimes it clears by itself an hour later.

**Cause.** pacman verifies `<repo>.db` against `<repo>.db.sig` whenever the signature is present. That is true at the stock `SigLevel = Required DatabaseOptional` as well as at `DatabaseRequired`, because pacman.conf(5) treats an invalid signature as fatal even when the level is Optional. If the mirror is mid-sync, or a CDN cached one file longer than the other, you get a new database with the old signature (or the reverse), and GnuPG reports a bad signature, which libalpm prints as `signature from "..." is invalid` (`ALPM_SIGSTATUS_INVALID`). The key is fine. pacman marks the database invalid, and the next sync force-downloads it again: libalpm's `be_sync.c` does this explicitly "to fix potential mismatched database/signature". So a retry against a mirror that has finished syncing clears it.

This is a different fault from a missing, untrusted or expired key (`is unknown trust`, `key ... is unknown`, `is expired`), and from a captive portal returning HTML (`GPGME error: No data`). Those have their own records and their own fixes.

> **Audit corrected this record.** The libalpm claims were checked against source. be_sync.c line 181 has the comment 'force update of invalid databases to fix potential mismatched database/signature' and sets dbforce. sync_db_validate runs at registration (_alpm_db_register_sync), so a database that failed validation in a previous run is re-downloaded on the next sync. signing.c maps GPG_ERR_BAD_SIGNATURE (and the default case) to ALPM_SIGSTATUS_INVALID, which prints `%s: signature from "%s" is invalid`. pacman-key's verify_sig pairs `<file>.sig` with `<file>` and runs gpg --verify, so `BAD signature` and `Good signature` come from gpg as the record says. cachyos.db.sig returns 200, so CachyOS does sign its databases. One cause sentence is wrong for the common case. The record says this happens 'with a database signature required', but the stock global level on Arch and Omarchy 4 (/etc/pacman.conf line 15 here) is `Required DatabaseOptional`. pacman.conf(5) says Optional still checks a signature that is present and treats an invalid one as fatal. So a mismatched pair fails on a stock configuration as well. Cause rewritten to say that. Fix, verify and danger hold. Not exercised: no CachyOS repository is configured here, and no sync was run.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Do not delete /var/lib/pacman/sync with a wildcard that could reach /var/lib/pacman/local, the installed-package database. Do not set the repo to `SigLevel = Never` or `DatabaseNever` to get past it: a mismatch is temporary, and disabling verification is permanent until you remember to undo it.

**Fix.**

Tell a mismatch from a key problem before touching the keyring:

```bash
ls -l /var/lib/pacman/sync/cachyos.db /var/lib/pacman/sync/cachyos.db.sig
sudo pacman-key --verify /var/lib/pacman/sync/cachyos.db.sig
```

`BAD signature from ...` with the key known means the two files do not match: this record. `No public key` or `Can't check signature` means a key problem: use the third-party keyring record instead.

Retry the sync. pacman re-downloads an invalid database on its own.

Omarchy 4:

```bash
omarchy update
```

Plain Arch:

```bash
sudo pacman -Syu
```

If the same mirror keeps serving a mismatched pair, see which server it is and move a different one to the top of the mirrorlist that the repo's `Include` line names:

```bash
pacman-conf -r cachyos Server | head -3
grep -n Include <(sed -n '/^\[cachyos\]/,/^\[/p' /etc/pacman.conf)
sudoedit /etc/pacman.d/<that-mirrorlist>
```

Then retry as above.

**Verify.** `sudo pacman-key --verify /var/lib/pacman/sync/<repo>.db.sig` reports `Good signature`, and the update syncs every database without a PGP error.

Sources: <https://gitlab.archlinux.org/pacman/pacman/-/blob/master/lib/libalpm/be_sync.c> · <https://gitlab.archlinux.org/pacman/pacman/-/blob/master/lib/libalpm/signing.c> · <https://man.archlinux.org/man/pacman-key.8> · <https://wiki.archlinux.org/title/Pacman/Package_signing> · <https://man.archlinux.org/man/pacman.conf.5> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/scripts/pacman-key.sh.in>

---

## Fix omarchy update and yay --sudoloop prompting for a password despite NOPASSWD sudo

`sudo-v-prompts-despite-nopasswd-verifypw` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** You enabled passwordless sudo (with `omarchy sudo passwordless`, or your own `NOPASSWD: ALL` drop-in), and `sudo pacman -S foo` indeed runs without a password. But `omarchy update` still stops at:

```
[sudo] password for <user>:
```

and an unattended `omarchy update -y` hangs there for five minutes, then aborts after the pre-update snapshot was already taken. `yay --sudoloop` prompts at start for the same reason. Some setups end with `sudo: a password is required` instead.

**Cause.** Those prompts come from `sudo -v`, not from running a command. `sudo -v` is governed by the sudoers option `verifypw`, whose default is `all`: every sudoers entry matching the user on this host must carry `NOPASSWD`, or `-v` asks for a password. A stock install still has the password-requiring `%wheel` rule (or a per-user `ALL=(ALL) ALL` file) alongside the new `NOPASSWD` drop-in, so commands run passwordless while validation does not.

On Omarchy 4.0.4 the call is in `omarchy-update-stay-awake` (line 95, `sudo -v`), which `omarchy update` reaches because it runs under `script`, so `[[ -t 0 ]]` is true even unattended (issue #9066, open). yay's sudoloop is also `sudo -v` in a loop. PR #13323 on `quattro` (not yet released) switches the update's own authorization to `sudo /usr/bin/true` for this reason.

> **Audit corrected this record.** Cause confirmed. omarchy-update-stay-awake line 95 is `sudo -v` under `[[ -t 0 ]]` on 4.0.4-1. Issue #9066 is open and shows the same cause, with `verifypw=any` as its verified workaround. #10352 was closed as a duplicate and offers editing the existing rule. PR #13323 switched to `sudo /usr/bin/true` for this reason. sudoers(5) gives verifypw all/any/always/never with default all, and omarchy-sudo-passwordless writes `${USER} ALL=(ALL) NOPASSWD: ALL` to /etc/sudoers.d/99-omarchy-nopasswd-$USER. The danger is wrong. In sudo's plugins/sudoers/check.c, when authentication is disabled (NOPASSWD, or verifypw never/any satisfied), check_user jumps to success with no timestamp cookie, and timestamp_update returns early on a NULL cookie. So a passwordless `sudo -v` writes no timestamp and hands out no password-free sudo. The record also misses a real side effect. omarchy-settings 4.0.4-1 ships `%wheel ALL=(root) NOPASSWD:` rules (omarchy-dns, omarchy-theme-set-browser-policy, timedatectl set-timezone), which I read from the cached package. With `verifypw=any`, every wheel user's `sudo -v` therefore succeeds without a password even when they have no general NOPASSWD grant. The `omarchy sudo passwordless` grant expires and tmpfiles removes it at boot, but the verifypw drop-in stays. After expiry, `sudo -v` stops priming the timestamp and yay's sudoloop keeps nothing alive. The fix now says this and offers `Defaults:<user> !authenticate` for a permanent passwordless user. Not exercised: no sudoers file was changed, and /etc/sudoers is not readable unprivileged.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A sudoers file with a syntax error or wrong mode disables sudo for everyone: keep a root shell open and run `sudo visudo -c` before closing it. `Defaults:<user> !authenticate` makes every sudo command passwordless for that user, so use it only where that is already the intent. `verifypw=any` or `never` does not create a sudo timestamp, but it makes `sudo -v` report success without checking anything, so scripts that use `sudo -v` as a gate or a keepalive (yay's sudoloop) stop doing their job.

**Fix.**

Confirm it is validation and not commands:

```bash
sudo -n true && echo 'commands: passwordless'
sudo -n -v   && echo 'validate: passwordless' || echo 'validate: needs a password'
sudo -l | sed -n '/may run/,$p'      # the matching entries, NOPASSWD or not
```

If your passwordless sudo is permanent (your own `NOPASSWD: ALL` drop-in), the cleanest fix is to put `NOPASSWD:` into the rule file that already matches you instead of keeping a second file, as issue #10352 suggests:

```bash
sudo grep -rn "$USER\|%wheel" /etc/sudoers /etc/sudoers.d/
```

Then edit the matching line with `sudo visudo -f <file>`. Omarchy's own `%wheel ... NOPASSWD: /usr/bin/omarchy-dns ...` style rules can stay, because they already carry NOPASSWD.

An equivalent for a user who is meant to be passwordless everywhere is to turn authentication off for that user, which also covers `sudo -v`:

```bash
echo "Defaults:$USER !authenticate" | sudo tee /etc/sudoers.d/90-noauth >/dev/null
sudo chmod 0440 /etc/sudoers.d/90-noauth
sudo visudo -c
```

The narrower workaround from issue #9066 lets validation succeed when at least one of your entries is `NOPASSWD`:

```bash
echo "Defaults:$USER verifypw=any" | sudo tee /etc/sudoers.d/90-verifypw >/dev/null
sudo chmod 0440 /etc/sudoers.d/90-verifypw
sudo visudo -c
```

Know its side effect on Omarchy 4 before using it. omarchy-settings ships several `%wheel` rules with `NOPASSWD`, so with `verifypw=any` your `sudo -v` never prompts, even after a temporary `omarchy sudo passwordless` grant has expired. A `sudo -v` that skips authentication writes no timestamp, so after that point `sudo -v` no longer primes the cache and `yay --sudoloop` keeps nothing alive. Remove `/etc/sudoers.d/90-verifypw` when you stop using passwordless sudo.

Re-run `omarchy update` afterwards. Omarchy after PR #13323 reaches a release authorizes with `sudo /usr/bin/true` instead of `sudo -v`, so none of this is needed there.

**Verify.** `sudo -k; sudo -n -v && echo ok` prints `ok`. `omarchy update -y` runs through the stay-awake step without a prompt.

Sources: <https://github.com/omacom/omarchy/issues/9066> · <https://github.com/omacom/omarchy/issues/10352> · <https://github.com/omacom/omarchy/pull/13323> · <https://man.archlinux.org/man/sudoers.5> · <https://github.com/Jguer/yay/blob/next/pkg/settings/exe/cmd_builder.go> · <https://wiki.archlinux.org/title/Sudo> · <https://raw.githubusercontent.com/sudo-project/sudo/main/plugins/sudoers/check.c> · <https://raw.githubusercontent.com/sudo-project/sudo/main/plugins/sudoers/timestamp.c>

---

## Finding truncated or missing package files after a crash or bad disk with pacman -Qkk / paccheck

`verify-installed-files-against-package-database` · severity: **medium** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** "The machine hard-locked / the disk threw errors / I pulled the plug during an update. It mostly boots, but random things segfault, an icon theme is half missing, and a binary is 0 bytes." Typical runtime fallout:
```
/usr/bin/foo: error while loading shared libraries: libbar.so.5: file too short
bash: /usr/bin/foo: cannot execute binary file: Exec format error
```
`pacman -Syu` says the system is fully up to date and refuses to help.

**Cause.** A crash, a filesystem that filled mid-write, or a failing SSD can leave files that pacman installed truncated, zero-length or missing entirely, while `/var/lib/pacman/local` still records the package as installed at the current version. `pacman -Syu` only compares *versions*. It never looks at the files on disk, so it will never notice and never re-extract them.

> **Audit corrected this record.** Checked on this Omarchy 4 workstation (pacman 7.1.0.r9.g54d9411-2, omarchy-settings 4.0.2-1): `pacman -Qk omarchy-settings` prints `omarchy-settings: 628 total files, 4 missing files` and `-Qkk` prints `629 total files, 4 altered files`, both with `(Permission denied)` warnings for the four `/etc/sudoers.d/omarchy-*` files when run unprivileged, so the `' 0 missing files'` and `' 0 altered files'` filters match the real strings (also confirmed in src/pacman/check.c, which uses the `_n` plural forms). `pacman -Qkk pacman` on this fresh install already prints three `backup file: pacman: /etc/pacman.conf (...)` mismatch lines with `0 altered files`, because Omarchy's post-install copies its channel template over that file: the record's 'those are your own edits' is wrong on Omarchy 4, so the /etc caveat was rewritten, and the difference between a `backup file:` line and a real altered file is now spelled out. pacutils is in extra at 0.15.0-2 and NOT installed here, and paccheck(1) from man.archlinux.org documents --sha256sum, --files, --file-properties and --quiet as used. The guard claim held: /usr/share/libalpm/hooks/00-omarchy-update-guard.hook fires on Operation = Upgrade (which includes a reinstall, per lib/libalpm/hook.c oldpkg matching), but /usr/bin/omarchy-update-pacman-guard exits 0 unless the pacman command line has both -S and -u, so per-package `pacman -S` is not blocked. Added one precondition to step 4: `omarchy-update-keyring` runs `pacman -Sy` before the -Syu, so if the update stops afterwards the sync databases are ahead of the system and a single-package `pacman -S` becomes a partial upgrade. `checkupdates` is available (pacman-contrib 1.13.1-1 is installed here). `yay --rebuildall` confirmed in yay 13.0.1 help. Not exercised: paccheck itself (not installed, no sudo), the reinstall loop, smartctl and btrfs scrub.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> ⚠️ **Risk.** If the local database itself was damaged (`/var/lib/pacman/local`), `-Qkk` reports nonsense and reinstalling on top of it makes things worse. Restore the database first. Do not run a blanket `pacman -Qqn | pacman -S -` on a system whose disk is still failing. You will only write more corrupt files. Reinstalling packages overwrites files under `/etc` that the package owns and does not list as backup files, so read the reinstall list first. If you suspect a compromise rather than a crash, run these checks from a live USB against hashes from an independent source. A rootkit can rewrite the local mtree data that `-Qkk` and `paccheck` compare against.

**Fix.**

**1. Find missing files across every installed package:**

```bash
sudo pacman -Qk $(pacman -Qsq) | grep -v ' 0 missing files'
```
Output looks like `foo: 231 total files, 3 missing files`. Nothing printed means nothing is missing. Run it with `sudo`: as an unprivileged user every root-only file (for example `/etc/sudoers.d/*`) prints a `(Permission denied)` warning and is counted as missing.

**2. Find altered files too** (size, mtime, permissions). This is what catches truncation:

```bash
sudo pacman -Qkk $(pacman -Qsq) | grep -v ' 0 altered files'
```
Expect false positives under `/etc`. Config files are `backup file:` lines, reported but not counted as altered, and they mismatch whenever anything edited them. On Omarchy 4 that includes the installer and migrations, so a fresh install already prints:
```
backup file: pacman: /etc/pacman.conf (Modification time mismatch)
backup file: pacman: /etc/pacman.conf (Size mismatch)
backup file: pacman: /etc/pacman.conf (SHA256 checksum mismatch)
pacman: 426 total files, 0 altered files
```
A `backup file:` line is not damage. A non-backup line such as `foo: /usr/lib/libbar.so.5 (Size mismatch)` is.

**3. Real content verification against the packaged hashes**, using `paccheck` from `pacutils` (extra, not installed by default on Omarchy):

```bash
sudo pacman -S --needed pacutils
sudo paccheck --sha256sum --quiet
sudo paccheck --files --file-properties --sha256sum --quiet   # thorough
```

**4. Reinstall everything that came back damaged.** First make sure the sync databases are not ahead of the installed system, or a single-package `pacman -S` pulls a newer version and creates a partial upgrade:

```bash
checkupdates              # must print nothing; if it prints anything, run omarchy update (Arch: sudo pacman -Syu) first
```
Then:

```bash
sudo bash -c 'LC_ALL=C.UTF-8 pacman -Qk 2>/dev/null | grep -v " 0 missing files" | cut -d: -f1 | \
  while read -r p; do pacman -S --noconfirm "$p"; done'
```
On Omarchy the update guard hook (`/usr/share/libalpm/hooks/00-omarchy-update-guard.hook`) runs on every reinstall, but `/usr/bin/omarchy-update-pacman-guard` aborts only when the pacman command line carries both `-S` and `-u`, so plain `pacman -S pkg` goes through. If it fires anyway, prefix the command with `env OMARCHY_ALLOW_DIRECT_PACMAN=1`.

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

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://wiki.archlinux.org/title/Pacman/Tips_and_tricks> · <https://man.archlinux.org/man/paccheck.1> · <https://wiki.archlinux.org/title/System_maintenance> · <https://archlinux.org/packages/extra/x86_64/pacutils/> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/src/pacman/check.c> · <https://gitlab.archlinux.org/pacman/pacman/-/raw/master/lib/libalpm/hook.c>

---

## Fix 'landlock is not supported by the kernel' from pacman's download sandbox

`pacman-landlock-not-supported-sandbox` · severity: **medium** · frequency: **rare** · applies to: `apparmor`, `arch`, `cachyos`, `desktop`, `endeavouros`, `grub`, `laptop`, `limine`, `manjaro`, `omarchy`, `systemd-boot`

**Symptom.** After pacman 7 arrived, syncing or downloading prints:

```
error: restricting filesystem access failed because Landlock is not supported by the kernel!
```

(pacman 7.0 spelled it `landlock` in lower case, pacman 7.1 capitalises it.) The kernel is a stock one built with `CONFIG_SECURITY_LANDLOCK=y`, so the message looks wrong. It typically starts after setting up AppArmor or another security module, on a custom or ARM board kernel, or inside a container.

**Cause.** pacman 7 downloads as the unprivileged `alpm` user inside a sandbox that uses Landlock to restrict which paths it may write. Landlock has to be enabled at boot. A kernel compiled with Landlock support still leaves it off if the `lsm=` kernel parameter lists security modules and omits `landlock`, which older AppArmor guides did, or if the kernel's built-in `CONFIG_LSM` list omits it. Containers and some board kernels lack it entirely. The current Arch wiki AppArmor line is `lsm=landlock,lockdown,yama,integrity,apparmor,bpf`. Omarchy 4 does not set `lsm=` and its kernel enables Landlock by default (`/sys/kernel/security/lsm` reads `lockdown,capability,landlock,yama,bpf` on 4.0.4), so on Omarchy this only follows a user-added `lsm=`.

> **Audit corrected this record.** The mechanism and fix hold. Confirmed locally on 4.0.4-1: /sys/kernel/security/lsm reads exactly `lockdown,capability,landlock,yama,bpf`, /proc/cmdline has no lsm=, the running linux-omarchy kernel has CONFIG_SECURITY_LANDLOCK=y and CONFIG_LSM="landlock,lockdown,yama,integrity,bpf", and /etc/limine-entry-tool.d/omarchy-defaults.conf and omarchy-uki.conf are owned by omarchy-settings 4.0.4-1 and set no lsm=. /usr/lib/limine/limine-common-functions loads /etc/limine-entry-tool.d/*.conf and then /etc/default/limine last, so the grep over both paths is the right check. limine-mkinitcpio exists. `man pacman.conf` for pacman 7.1.0 documents DisableSandboxFilesystem for Landlock failures. The Arch wiki AppArmor page gives `lsm=landlock,lockdown,yama,integrity,apparmor,bpf`. The CachyOS thread shows the error with CONFIG_SECURITY_LANDLOCK=y and landlock missing from lsm=. The EndeavourOS thread was not re-read. One wording defect: the symptom quotes pacman 7.0's lowercase string. The installed libalpm (pacman 7.1.0) prints 'because Landlock is not supported by the kernel!', so a reader grepping case-sensitively for the quoted text misses it. The symptom is corrected. Nothing touching the boot configuration was run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** A malformed kernel command line can stop the machine booting. On Omarchy 4 a broken UKI can be bypassed from the Limine menu's Snapshots entries. Disabling the sandbox removes a protection for the download process, so prefer fixing `lsm=`.

**Fix.**

Check what is active and whether you set `lsm=`:

```bash
cat /sys/kernel/security/lsm
tr ' ' '\n' < /proc/cmdline | grep '^lsm='
```

If `landlock` is missing from the first, add it to the front of your `lsm=` value.

**Omarchy 4 (Limine UKI).** The command line lives in the UKI and comes from `/etc/limine-entry-tool.d/*.conf`. Find the file that sets `lsm=` (do not edit the `omarchy-*.conf` files, which `omarchy-settings` owns) and change it, or create your own drop-in:

```bash
grep -rn 'lsm=' /etc/limine-entry-tool.d/ /etc/default/limine 2>/dev/null
echo 'KERNEL_CMDLINE[default]+=" lsm=landlock,lockdown,yama,integrity,apparmor,bpf"' | sudo tee /etc/limine-entry-tool.d/90-lsm.conf
sudo limine-mkinitcpio
```

Remove the old `lsm=` wherever grep found it, so only one remains.

**Plain Arch with GRUB.** Edit `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` the same way, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`. **systemd-boot.** Edit the `options` line in `/boot/loader/entries/*.conf`.

Reboot and re-check `/sys/kernel/security/lsm`.

**Kernel that cannot do Landlock (container, board kernel).** Disable only the filesystem part of the sandbox in `/etc/pacman.conf` (pacman 7.1):

```ini
[options]
DisableSandboxFilesystem
```

**Verify.** `cat /sys/kernel/security/lsm` includes `landlock`, and `omarchy update` (Omarchy) or `sudo pacman -Syu` (Arch) syncs with no landlock error.

Sources: <https://discuss.cachyos.org/t/pacman-7-0-0-r7-g1f38429-2-landlock-error-despite-config-security-landlock-y/17707> · <https://forum.endeavouros.com/t/odroid-n2-and-pinebook-pro-have-a-problem-with-pacman-7-0/60760> · <https://wiki.archlinux.org/title/AppArmor>

---

## Install Python packages despite 'error: externally-managed-environment'

`pip-externally-managed-environment` · severity: **low** · frequency: **very-common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `python`

**Symptom.** `pip install` stopped working, with or without `--user` or sudo:

```
$ pip install requests
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try 'pacman -S
    python-xyz', where xyz is the package you are trying to
    install.
```

**Cause.** Arch's python package ships the marker file `/usr/lib/python3.14/EXTERNALLY-MANAGED` (the version in the path follows the installed python), as defined by PEP 668. pip refuses to install into an interpreter carrying it, including into `~/.local`, because modules installed there land on the system Python's import path and can break pacman-installed Python tools. This is upstream pip behaviour that Arch enabled, not a fault on your system.

> **Audit corrected this record.** The cause holds. Confirmed locally: /usr/lib/python3.14/EXTERNALLY-MANAGED is owned by python 3.14.7-1, and its text matches the symptom and names `python -m venv` and python-pipx. Forum thread 286788 shows the same error, and the Arch wiki Python page describes the PEP 668 marking and lists pipx and uv. python-pipx (1.15.0) and uv (0.12.23) are both in extra per archlinux.org. `omarchy install dev-env python` exists, runs `mise use --global python@latest` and installs uv from astral.sh. One claim is fabricated precision: 'uv ... (Omarchy 4 has it installed)'. uv is in no *.packages file in /usr/share/omarchy/install or in the quattro tree. On this workstation /var/log/pacman.log shows it arriving after the Omarchy install, in a manual `pacman -S ... protontricks gamemode ... uv`. A stock Omarchy 4 has no `uv`, so `uv tool install` fails with command not found. The fix is corrected to install it first.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** `pip install --break-system-packages` (or deleting EXTERNALLY-MANAGED) can overwrite modules that pacman-installed tools depend on and break them, and pacman will later report file conflicts in /usr/lib/python3.x.

**Fix.**

Pick by what you are installing.

**A library or tool Arch packages.** Install it with pacman:

```bash
pacman -Ss '^python-requests$'
sudo pacman -S python-requests
```

**A command-line application from PyPI.** Install it in its own environment. `uv` and `pipx` are both in the Arch repositories. Neither is installed by default on Omarchy 4, so install one first:

```bash
sudo pacman -S uv && uv tool install httpie
# or
sudo pacman -S python-pipx && pipx install httpie
```

**Dependencies for a project.** Use a virtual environment:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Omarchy 4.** `omarchy install dev-env python` installs a separate Python with mise, plus `uv` from astral.sh into your home directory, intended for development work. Use that for projects and keep `/usr/bin/python` for system tools.

Avoid `--break-system-packages`.

**Verify.** The tool runs from its environment (`uv tool list` or `pipx list` shows it, or `.venv/bin/python -c 'import requests'` succeeds), and `pacman -Qkk python` reports no altered files.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=286788> · <https://wiki.archlinux.org/title/Python> · <https://archlinux.org/packages/extra/x86_64/uv/> · <https://archlinux.org/packages/extra/any/python-pipx/>

---

## Fix 'error: target not found' for a package that exists

`target-not-found-wrong-repo-or-aur` · severity: **low** · frequency: **very-common** · applies to: `arch`, `aur`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `multilib`, `omarchy`, `yay`

**Symptom.** A package you can see on archlinux.org, the AUR website or in a guide will not install:

```
$ sudo pacman -S steam
error: target not found: steam
```

Re-running with `sudo pacman -Syy` changes nothing. Common with `steam`, `lib32-*` packages, AUR packages like `visual-studio-code-bin`, and packages that were renamed.

**Cause.** pacman only searches the repositories enabled in `/etc/pacman.conf`, using the database copies it last downloaded. Four different causes produce the same message. (1) The package is in the AUR, which pacman does not read at all. (2) It is in `[multilib]`, which plain Arch ships disabled. (3) The local databases are stale, so they lack a package or version that was added after the last sync. (4) The name changed, was merged into another package, or does not exist for your architecture (Omarchy's install menu offers some x86_64-only packages on aarch64, upstream issue #8645).

> **Audit corrected this record.** The four causes are sound, and Omarchy enabling [multilib] is confirmed locally. Two defects. First, the record's AUR example is visual-studio-code-bin, but on Omarchy 4 that package is in the [omarchy] pacman repository (`pacman -Si visual-studio-code-bin` reports Repository: omarchy, 1.138.0-1). So pacman installs it on Omarchy and the example sends the reader to the AUR for nothing. Second, cited issue #6191 does not show 'target not found'. It is an Omarchy 3.8.2 download 404 from stale metadata, closed after the reporter ran a bare `sudo pacman -Sy`, which is the partial-upgrade step this corpus forbids. The aarch64 claim actually comes from issue #8645 (open), which the cause names but the record did not cite. Fix and sources are corrected. Second audit confirmed the corrected text: Second pass on the record as corrected on 2026-10-04. Its two findings still hold: visual-studio-code-bin is in the [omarchy] repository (`pacman -Si` reports Repository: omarchy, 1.138.0-1), and the aarch64 claim comes from issue #8645, still open and titled 'Install menu offers x86_64-only packages on aarch64: every entry fails with `target not found`'. Confirmed locally: `pacman-conf --repo-list` prints core, extra, multilib, omarchy, so the claim that Omarchy enables multilib holds, and `pacman -Si steam` reports multilib. Forum thread 258910 is exactly the steam / `pacman -Syy` / enable multilib case. Every sync in the fix is a full upgrade, with omarchy update on Omarchy, and `pacman -Fy` syncs only the file database, so it is not a partial upgrade. No install was run.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Fixing it with `sudo pacman -Sy <package>` is a partial upgrade and can break shared libraries. Always sync and upgrade together.

**Fix.**

Work out which cause applies:

```bash
pacman -Ss '^steam$'            # in an enabled repo?
yay -Ss steam                   # in the AUR?
pacman-conf --repo-list         # which repos are enabled
pacman -F libfoo.so             # which package ships a file (after: sudo pacman -Fy)
```

**In the AUR.** Install with the helper instead of pacman. Omarchy 4 ships yay:

```bash
yay -S <package>
```

On Omarchy 4, check `pacman -Si <package>` first. The `[omarchy]` repository carries some packages that are AUR-only on plain Arch, `visual-studio-code-bin` among them, and those install with `sudo pacman -S`.

**In multilib, plain Arch.** Uncomment both lines in `/etc/pacman.conf`:

```ini
[multilib]
Include = /etc/pacman.d/mirrorlist
```

then `sudo pacman -Syu` followed by `sudo pacman -S steam`. Omarchy 4 already enables `[multilib]`, so skip this there.

**Stale databases.** Sync and upgrade together, then install. Never `pacman -Sy <pkg>` or a bare `pacman -Sy` on its own:

```bash
omarchy update                  # Omarchy 4
sudo pacman -Syu                # plain Arch
sudo pacman -S <package>
```

**Renamed, merged or wrong architecture.** Look the package up on archlinux.org or the AUR page, which states replacements, or search by description with `pacman -Ss <keyword>`. On aarch64, packages built only for x86_64 do not exist at all, and Omarchy's install menu still offers some of them (issue #8645).

**Verify.** `pacman -Si <package>` (repo) or `yay -Si <package>` (AUR) prints the package details, and the install proceeds.

Sources: <https://wiki.archlinux.org/title/Pacman> · <https://bbs.archlinux.org/viewtopic.php?id=258910> · <https://github.com/omacom/omarchy/issues/8645>

---

## Fix 'warning: directory permissions differ' during an upgrade

`directory-permissions-differ-warning` · severity: **low** · frequency: **common** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** An upgrade prints a warning and carries on:

```
(1/4) upgrading openssl
warning: directory permissions differ on /etc/ssl/private/
filesystem: 755  package: 700
```

Another reported case is `/var/lib/AccountsService/users/` after an accountsservice upgrade. It repeats every time that package is upgraded. Users ask whether to fix it or ignore it.

**Cause.** pacman never changes the mode of a directory that already exists, so when a package changes the permissions it ships for a directory (or an admin or a program changed them on disk), pacman only reports the difference. The openssl case is a deliberate packaging change: Arch's openssl package restricted `/etc/ssl/private` to 0700 in June 2026, and existing systems keep their old 0755 directory until it is changed by hand. A wider mode on a private-key directory lets other local users list what it holds.

> **Audit corrected this record.** The openssl case holds. The EndeavourOS thread of 2026-06-09 shows the warning on openssl 3.6.2-2 to 3.6.3-1 and links the packaging commit. The Arch GitLab API shows commit b8cf05c2 'restrict /etc/ssl/private to 0700; closes #1' dated 2026-04-20, released in June 2026, so the cause's month is right for the shipped package. On this machine /etc/ssl/private is 700. libalpm.so.16 contains the two-line `directory permissions differ on %s` / `filesystem: %o  package: %o` message as quoted. pacman.log shows /boot 700 against 755 and /var/log/swtpm/libvirt/qemu 730 against 755. `pacman -Qkk` prints `(Permissions mismatch)`, and /boot is vfat mounted with dmask=0077. Thread 245014 supports /var/lib/AccountsService/users/. The one defect is in the symptom: it names /root/ as a common case, which neither source mentions. /root is 750 here and owned by filesystem 2025.10.12-1 with no mismatch, so that example is unsupported and is removed. Nothing was chmodded.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Tightening a directory that a service relies on reading as another user can stop that service. Use the mode the package itself declares, not a guess.

**Fix.**

Set the directory named in the warning to the mode the package ships, which is the `package:` value:

```bash
sudo chmod 700 /etc/ssl/private
stat -c '%a %n' /etc/ssl/private
```

To see every permission mismatch pacman knows about, list them for review:

```bash
sudo pacman -Qkk 2>&1 | grep -i 'permissions mismatch'
```

Do not chmod everything that command prints. Change a path only when the package made it stricter and the warning appeared during an upgrade, as with `/etc/ssl/private`. Leave these alone:

- Mount points, whose mode comes from the mount options. On Omarchy 4, `/boot` is a vfat ESP mounted with `dmask=0077`, so it always reads 700 against the package's 755, and chmod cannot change it.
- Directories a service manages and resets itself, such as `/var/log/swtpm/libvirt/qemu` (libvirt) or `/var/cache/pacman/pkg`.
- Anything you widened or tightened on purpose. That warning then repeats on every upgrade of that package, which is harmless.

**Verify.** `stat -c '%a %n' /etc/ssl/private` prints `700 /etc/ssl/private`, and the next upgrade of that package prints no warning.

Sources: <https://forum.endeavouros.com/t/warning-directory-permissions-differ-on-etc-ssl-private/80073> · <https://bbs.archlinux.org/viewtopic.php?id=245014> · <https://gitlab.archlinux.org/archlinux/packaging/packages/openssl/-/commit/b8cf05c2a9c5200c624c720ab80444bfd533005d>

---

## Make yay (and omarchy update) actually update -git AUR packages

`yay-git-packages-never-update-devel` · severity: **low** · frequency: **common** · applies to: `arch`, `aur`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`, `yay`

**Symptom.** An AUR package ending in `-git` (built from the latest upstream commit) never updates. `yay -Syu` and `omarchy update` both say there is nothing to do for it, while upstream has had dozens of commits and the installed version string is months old.

**Cause.** A `-git` package's version in the AUR only changes when the maintainer edits the PKGBUILD, which is rare, because the real version comes from upstream at build time. yay only checks upstream for new commits when development checking is enabled with `--devel`, and it compares against a commit hash it recorded when it installed the package. Without `--devel`, or for packages installed by makepkg or another helper (so yay has no recorded hash), yay never rebuilds them. On Omarchy 4 the AUR step of `omarchy update` (`/usr/share/omarchy/bin/omarchy-update-aur-pkgs`) runs `yay -Sua --noconfirm --cleanafter --ignore gcc14,gcc14-libs` when foreign packages are installed. It does not pass `--devel`, so `-git` packages are not rebuilt unless devel checking is saved in yay's config.

> **Audit corrected this record.** The yay README confirms `yay -Y --gendb`, `yay -Syu --devel` and `yay -Y --devel --save`. The local `yay --help` for 13.0.1 lists --devel, --save, --gendb and --rebuild. The mechanism and fix are correct. The cause misquotes Omarchy's AUR step. On 4.0.4-1, /usr/share/omarchy/bin/omarchy-update-aur-pkgs runs `yay -Sua --noconfirm --cleanafter --ignore gcc14,gcc14-libs`, only when `pacman -Qem` finds foreign packages and the AUR is reachable. The cause is corrected to the exact command. The conclusion stands, because no --devel is passed and a saved devel setting in ~/.config/yay/config.json still applies to that call. Second audit confirmed the corrected text: Second pass on the record as corrected on 2026-10-04, whose finding (the cause now quotes the real AUR step) still holds. Confirmed on this machine: /usr/share/omarchy/bin/omarchy-update-aur-pkgs on 4.0.4-1 runs `yay -Sua --noconfirm --cleanafter --ignore gcc14,gcc14-libs` only when `pacman -Qem` finds foreign packages and the AUR is reachable, with no --devel. The quattro branch adds a --sudo wrapper and `|| exit 1` but still passes no --devel, so the cause holds on edge too. The yay README (Jguer/yay) documents `yay -Y --gendb`, `yay -Syu --devel` and `yay -Y --devel --save`, and its FAQ says packages not installed through yay are missing from the hash cache until --gendb. Local `man yay` (yay 13.0.1-1) documents --devel as a git ls-remote check against the hash recorded at install time, lists -Qu among the operations extended to the AUR (so `yay -Qua` is valid), and gives `yay --devel --save` as setting devel to true in the config. --rebuild and --cleanafter exist in `yay --help`. Nothing was executed against the AUR.
>
> *The Cause above was rewritten on 2026-10-04 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Record the current commit of every installed development package once, so yay has something to compare with:

```bash
yay -Y --gendb
```

Then turn development checking on permanently. This writes `~/.config/yay/config.json`, so every later `yay`, `yay -Syu` and the `yay -Sua` inside `omarchy update` checks `-git` packages:

```bash
yay -Y --devel --save
```

Or check once without saving the setting:

```bash
yay -Sua --devel
```

Force one package to rebuild now regardless:

```bash
yay -S --rebuild <package>-git
```

Development checking runs `git ls-remote` against every `-git` package's upstream on each update, which adds time proportional to how many you have.

**Verify.** `grep '"devel"' ~/.config/yay/config.json` shows `true`, and `yay -Qua` lists a `-git` package after its upstream gets a new commit.

Sources: <https://github.com/Jguer/yay> · <https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-update-aur-pkgs>

---

## Get past an AUR build that fails in its check() test suite

`aur-build-fails-in-check-function` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `omarchy`

**Symptom.** Compilation finishes, then the build stops while running the package's tests:

```
==> Starting check()...
...
FAILED: 2 of 431 tests
==> ERROR: A failure occurred in check().
    Aborting...
 -> error making: <pkgname>
```

The package itself would probably work. During `omarchy update` the AUR step fails on that one package and it stays at the old version.

**Cause.** makepkg runs a PKGBUILD's `check()` function after `build()` whenever the `check` option is enabled in `BUILDENV`, and it is enabled by default (`BUILDENV=(!distcc color !ccache check !sign)` in `/etc/makepkg.conf` on Omarchy 4.0.4-1). Test suites in AUR packages often fail for reasons unrelated to the built binary: tests that need network access, a display, a specific locale or timezone, more file descriptors, or tests that broke against a newer library before the maintainer updated the PKGBUILD. A non-zero exit from `check()` aborts the build.

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Skipping tests means installing a build whose own test suite failed. If the failures are in core functionality rather than network or environment tests, the package may really be broken, so read the output before reaching for --nocheck, and prefer the per-package flag over disabling check globally.

**Fix.**

Read the failing tests first. If they are network, sandbox or flaky timing failures, skip the test stage for this one build. `--nocheck` tells makepkg not to run `check()` or handle `checkdepends`, and yay passes it through with `--mflags`:

```bash
yay -S <pkgname> --mflags --nocheck
```

With makepkg directly:

```bash
makepkg -si --nocheck
```

Report the failure on the package's AUR page comments with the test output, so the maintainer can fix or disable the test.

To skip tests for all your AUR builds instead, disable the option in your user config, copying your system `BUILDENV` and changing only `check`:

```bash
mkdir -p ~/.config/pacman
grep -E '^BUILDENV=' /etc/makepkg.conf
echo 'BUILDENV=(!distcc color !ccache !check !sign)' >> ~/.config/pacman/makepkg.conf
```

Omarchy 4: `omarchy update` runs `yay -Sua` with no extra flags, so a package that fails `check()` fails there every time until you either build it once with `--nocheck` as above or set `!check` in the user config.

**Verify.** `pacman -Q <pkgname>` shows the new version and the next `omarchy update` (or `yay -Sua`) no longer reports `error making: <pkgname>`.

Sources: <https://man.archlinux.org/man/makepkg.8> · <https://man.archlinux.org/man/makepkg.conf.5> · <https://github.com/Jguer/yay/blob/next/doc/yay.8> · <https://raw.githubusercontent.com/Jguer/yay/next/pkg/settings/parser/parser.go>

---

## Clear the 'will NOT be used by the installed perl interpreter' warning

`detect-old-perl-modules-warning` · severity: **low** · frequency: **occasional** · applies to: `arch`, `aur`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** After an upgrade that touched perl, the transaction ends with:

```
(5/9) Checking for old perl modules...
WARNING: '/usr/lib/perl5/5.40' contains data from at least 3 packages which will NOT be used by the installed perl interpreter.
 -> Run the following command to get a list of affected packages: pacman -Qqo '/usr/lib/perl5/5.40'
```

Sometimes also `WARNING: 12 file(s) in /usr/lib/perl5/5.40 are not tracked by pacman and need to be rebuilt.` Perl scripts or tools that use those modules start failing with `Can't locate Foo/Bar.pm in @INC`.

**Cause.** Arch installs perl modules into a directory named for the perl major version, such as `/usr/lib/perl5/5.42/`, and the interpreter only reads its own version's directory. The `detect-old-perl-modules.hook`, shipped by the perl package, warns about every other version directory under `/usr/lib/perl5` that still holds files. That happens two ways. Usually the directory is OLDER than the running perl: repository packages were rebuilt by Arch, and what remains is AUR or other foreign perl packages built against the old perl, or files installed by `cpan`. Sometimes the directory is NEWER than the running perl: perl itself is held back (`IgnorePkg`, `--ignore perl`, or a package that requires an older perl) while every module package moved on, so the warning names the new directory and lists ordinary repository packages.

> **Audit corrected this record.** The hook and messages are confirmed on this machine: /usr/share/libalpm/hooks/detect-old-perl-modules.hook is owned by perl 5.42.2-2, and /usr/share/libalpm/scripts/detect-old-perl-modules.sh prints both quoted WARNING lines and the unowned-files find command used in the fix. `yay --help` lists --rebuild. The defect is the held-back case, which is the case the record's only source (thread 270501) actually documents. The script warns about every /usr/lib/perl5 directory that is not the running perl's version. When perl is held back, that is the NEWER directory: in the thread perl stayed at 5.32 and the warning named 5.34 with 42 repository packages. The record's cause describes only an old directory, and its fix tells the reader to look for `perl` in `pacman -Qqo` output, which perl never appears in for that case, using a hard-coded 5.40 that will not match most readers. The thread also shows the next obstacle, an AUR package requiring `perl<5.33` that blocks the perl upgrade. The full update command was missing for Omarchy, where `pacman -Syu` is refused by the ALPM guard. Nothing was rebuilt or removed.
>
> *The Cause above was rewritten on 2026-10-05 to match this note. The Fix was corrected by the audit itself.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

**Fix.**

Compare the directory the WARNING names with the running perl:

```bash
perl -e 'print "$^V\n"'
ls /usr/lib/perl5/
```

Set `dir` to the directory the WARNING names. The example below uses 5.40:

```bash
dir=/usr/lib/perl5/5.40
pacman -Qqo "$dir"
```

**The named directory is NEWER than the running perl.** perl is held back. Check for it in `IgnorePkg`:

```bash
pacman-conf IgnorePkg
```

Remove `perl` from `IgnorePkg` with `sudoedit /etc/pacman.conf`, then do a full upgrade:

```bash
# Omarchy 4
omarchy update
# Plain Arch
sudo pacman -Syu
```

If the upgrade stops with `installing perl (...) breaks dependency 'perl<5.xx' required by <package>`, that package (usually from the AUR) pins the old perl. Rebuild it against the new perl or remove it, then run the upgrade again.

**The named directory is OLDER than the running perl.** Rebuild each listed foreign package against the new perl:

```bash
pacman -Qqm | grep -xFf <(pacman -Qqo "$dir")
yay -S --rebuild <package> <package>
```

A repository package in `pacman -Qqo "$dir"` that is not in that foreign list means the system is not fully updated: run the full upgrade above. Remove any listed package you no longer use with `sudo pacman -Rns <package>`.

For files no package owns (installed with `cpan`), list them and reinstall those modules with cpan, or delete them:

```bash
LC_ALL=C find "$dir" -type f -exec pacman -Qqo {} + |& sed -n 's/^error: No package owns \(.*\)$/\1/p'
```

**Verify.** `pacman -Qqo "$dir"` lists no packages for the directory the warning named, `perl -e 'print "$^V\n"'` matches the newest directory in `ls /usr/lib/perl5/`, and the hook prints no WARNING on the next transaction.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=270501>

---

## Silence 'ldconfig: ... is not a symbolic link' after every upgrade

`ldconfig-is-not-a-symbolic-link` · severity: **low** · frequency: **occasional** · applies to: `arch`, `cachyos`, `desktop`, `endeavouros`, `laptop`, `manjaro`, `omarchy`

**Symptom.** Every pacman transaction that installs anything prints, just before `Running post-transaction hooks...`:

```
ldconfig: /usr/lib/libicudata.so.75 is not a symbolic link
ldconfig: /usr/lib/libicuuc.so.75 is not a symbolic link
ldconfig: /usr/lib/libxml2.so.2 is not a symbolic link
```

The upgrade itself completes. Running `sudo ldconfig` by hand prints the same lines.

**Cause.** ldconfig expects a library's soname (`libfoo.so.N`) to be a symlink to the real versioned file. When a regular file sits at that name instead, ldconfig warns. The usual origin is a library copied into `/usr/lib` by hand, or by a vendor installer, to fix some earlier breakage. That file is owned by no package, so pacman never updates or removes it, and the warning repeats forever. Less often the file is owned by a package that ships it that way, which is a packaging quirk and harmless.

> **Audit corrected this record.** Thread 305501 supports the diagnosis: `pacman -Qo` showed all three files unowned, left by a manual `pacman -U` of an old libxml2, and deleting them silenced ldconfig. Two defects remain in the current text. First, it states that libxml2.so.2 belongs to no current Arch package. That is false: [extra] ships libxml2-legacy 2.13.9-2, whose file list (archlinux.org, retrieved) contains /usr/lib/libxml2.so.2, and the AUR has icu75 for libicudata.so.75. The earlier audit inferred this from a local `pacman -Qo`, which only proves the file is unowned on that one machine. A program still linked to libxml2.so.2 is exactly why such a stray copy gets made, so the reader needs to know the packaged replacement exists. Second, the delete step is a copy-paste `sudo rm` of the three example paths, and the in-use check greps only libxml2.so.2, despite the sentence telling the reader not to act on the example names. The corrected fix builds the list from ldconfig's own output, skips anything pacman owns, and moves rather than deletes, so a mistake is reversible. The parsing sed and the `pacman -Qo` exit codes were tested here (libxml2.so.2 unowned rc=1, libxml2.so.16 owned rc=0). ldconfig and the move were not run, since they need root.
>
> *The Cause above was not rewritten and may still contain the error described. The Fix below is the corrected version.*

> *Checked against Omarchy omarchy 4.0.4-1 on 2026-10-05.*

> ⚠️ **Risk.** Moves files out of /usr/lib. The loop skips anything `pacman -Qo` reports as owned, and moves rather than deletes, so a library a program still needs can be put back from /root/stray-libs or replaced by its packaged equivalent (libxml2-legacy for libxml2.so.2). Run it only after a full system update.

**Fix.**

Find out who owns each file ldconfig complains about. Use `pacman -Qo` (the local database), not `pacman -F`, which searches the files database and can be stale:

```bash
sudo ldconfig 2>&1 | sed -n 's/^ldconfig: \(.*\) is not a symbolic link$/\1/p' | xargs -r pacman -Qo
```

Each path prints either `is owned by <package>` or `error: No package owns <path>`.

**Unowned files.** These are stray copies, usually left by copying a library in by hand or by installing an old package file with `pacman -U`. Update the system fully first:

```bash
# Omarchy 4
omarchy update
# Plain Arch
sudo pacman -Syu
```

Then move every unowned file ldconfig names out of the library path. Owned files are skipped. Moving instead of deleting keeps a copy you can put back:

```bash
sudo mkdir -p /root/stray-libs
for f in $(sudo ldconfig 2>&1 | sed -n 's/^ldconfig: \(.*\) is not a symbolic link$/\1/p'); do
  pacman -Qo "$f" >/dev/null 2>&1 || sudo mv -v "$f" /root/stray-libs/
done
sudo ldconfig
```

A silent `sudo ldconfig` confirms the fix. If a program then fails with `error while loading shared libraries: libxml2.so.2: cannot open shared object file`, it still needs the old soname. Install the packaged copy rather than restoring the stray one:

```bash
sudo pacman -S libxml2-legacy
```

`libxml2-legacy` is in [extra] and ships `/usr/lib/libxml2.so.2`. For an old ICU soname such as `libicudata.so.75`, the AUR package `icu75` is the packaged equivalent. Once nothing breaks, delete the backup with `sudo rm -r /root/stray-libs`.

**Owned by a package.** Check whether its files still match the package, and reinstall it after a full update if they do not:

```bash
pacman -Qkk <package>
sudo pacman -S <package>
```

If it still warns after a reinstall, the package ships a regular file at the soname. That is harmless and can be reported to the packager.

**Verify.** `sudo ldconfig` prints nothing.

Sources: <https://bbs.archlinux.org/viewtopic.php?id=305501> · <https://archlinux.org/packages/extra/x86_64/libxml2-legacy/files/> · <https://aur.archlinux.org/packages/icu75>

---
