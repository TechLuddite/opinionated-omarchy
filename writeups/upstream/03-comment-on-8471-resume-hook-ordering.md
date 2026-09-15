Comment for omacom/omarchy#8471 (with shorter pointers to #10375 and #8888)

Thank you for this. It is one of the most carefully written issues I have read on this tracker, and
the line where you say you have not been able to demonstrate a resume failure attributable to the
ordering in isolation is exactly the right thing to have written. I went looking to confirm the
defect on my own machine, expected to find it, and came away thinking the ordering is not the
problem. Everything below is checkable in a couple of minutes and I would like to be corrected if I
have this wrong.

Versions: omarchy-settings 4.0.2-1, mkinitcpio 41.1-1, limine-mkinitcpio-hook 1.37.1-1,
systemd 261.2-1, linux 7.1.9.arch1-2.

## The array does end with `resume`, exactly as you describe

No argument here. `/usr/bin/mkinitcpio:1121` collects the drop-ins with `sort -zVu`, so the `+=`
lands last and `resume` is position 15. Your reproducer gives me the same shape it gives you.

## The claim I think does not hold

The load-bearing sentence is this one:

> By the time `/usr/lib/initcpio/hooks/resume` writes to `/sys/power/resume`, `filesystems` has
> already mounted root (`rw` is on the cmdline).

`/usr/lib/initcpio/init` runs **every** `run_hook` before it mounts anything:

```
43:  run_hookfunctions 'run_hook' 'hook' $HOOKS
64:  fsck_root
67:  "$mount_handler" /new_root
```

`run_hookfunctions` (`/usr/lib/initcpio/init_functions:88-103`) is a plain loop with no early exit
and it discards each hook's return code, so no hook can prevent a later one from running.

Two details make the gap between position 11 and position 15 narrower than it looks:

- `filesystems` and `fsck` have **no runtime hook at all**. Neither has a file in
  `/usr/lib/initcpio/hooks/`, and `grep -c run_hook` is 0 for both
  `/usr/lib/initcpio/install/filesystems` and `/usr/lib/initcpio/install/fsck`. They contribute
  `build()` only. Nothing mounts root at position 12.
- `btrfs-overlayfs` at position 14 defines `run_latehook`, not `run_hook`
  (`/usr/lib/initcpio/hooks/btrfs-overlayfs:3`), and late hooks run at `init:71`, after the mount.

So on this array, `resume` at 15 is the **next `run_hook` to execute after `encrypt`**. Positions 12
and 15 are behaviourally identical.

## Evidence from a boot on this machine

Encrypted root, `resume=/dev/mapper/root`, hibernation configured. From the current boot's kernel
log, in order:

```
[24181.978319] Freeing unused kernel image (initmem) memory: 4908K
[24181.984723] device-mapper: ioctl: 4.50.0-ioctl (2025-04-28) initialised
[24181.984741] PM: Image not found (code -22)
[24181.984752] BTRFS info (device dm-0): first mount of filesystem 974cda7f-...
```

`PM: Image not found` is the kernel's response to a userspace write to `/sys/power/resume`. It lands
**after** dm-crypt initialises and **before** the first mount of `dm-0`, and it is a hundred-odd
lines after initcalls finish, so it is not the kernel's own late resume attempt either. That is the
`resume` hook running from position 15, after `encrypt`, before root is mounted.

Supporting reading, though weaker on its own than the log ordering:

```bash
cat /sys/power/resume   # 253:0
lsblk -o NAME,MAJ:MIN | grep root   #   └─root 253:0
```

`/dev/mapper/root` does not exist when the kernel parses its cmdline, so that value was resolved by
something in the initramfs. (Nothing has hibernated or suspended on this boot, and uptime is nine
days, so `systemd-sleep` did not write it later.)

## What the Arch wiki actually requires

The "Configure the initramfs" section of `Power_management/Suspend_and_hibernate` gives this example:

```
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems resume fsck)
```

`resume` is after `filesystems` in upstream's own example. The only ordering requirements stated are
that `resume` must follow `udev` and must follow `encrypt` or `lvm2`. There is no "before
`filesystems`" requirement on the page. The nearby sentence about the hibernate location being
"available to the initramfs, i.e. before the root file system is mounted" is about `resume=` and
`resume_offset=`, and both are satisfied here.

## #8352 is the strongest evidence, and it points somewhere else

You already reference #8352, and I think it settles more than it appears to. Its logs, from several
machines, show this:

```
PM: hibernation: Read 5545216 kbytes in 4.07 seconds (1362.46 MB/s)
PM: Image successfully loaded
nvidia 0000:01:00.0: PM: pci_pm_freeze(): nv_pmops_freeze [nvidia] returns -5
PM: hibernation: Failed to load image, recovering.
PM: hibernation: resume failed (-5)
```

The hook ran from last position, found the image, and read five gigabytes of it. Resume then failed
in NVIDIA's `pci_pm_freeze` callback returning `-EIO`. On those machines the ordering demonstrably
was not the blocker, and the cause is visible in the log.

@jorgenfoss in #10375 reports an actual observed failure rather than a theoretical one, which is the
case most worth chasing. If you still have that machine, `journalctl -b -1 -k | grep -i "PM: hibernation"`
after a failed resume would say whether the image was found and read. If it reads
`PM: Image not found`, the hook is not resolving the device and that is a real bug, though a
different one from ordering. If it reads `Image successfully loaded` followed by a driver error, it
is the #8352 shape.

One diagnostic correction while I am here: on systemd 255 and newer the hook does not take its own
`printf > /sys/power/resume` path at all. `/usr/lib/initcpio/hooks/resume:14-18` execs
`/usr/lib/systemd/systemd-hibernate-resume` and returns, so the error text on an affected machine
comes from that binary rather than from the shell hook.

## On the suggested fixes

Your positioning drop-in is a clean piece of shell and I have no complaint with it as code. Same for
#8888, which keeps `omarchy_resume.conf`, updates `omarchy-hibernation-setup` and
`omarchy-hibernation-remove` together, and adds a migration and a test. That is a more complete
change than I expected to find and it addresses the coupling properly.

My only hesitation is that if the ordering is not load-bearing, both changes take on risk for no
benefit. `omarchy-hibernation-available:15` requires `/etc/mkinitcpio.conf.d/omarchy_resume.conf` to
exist and `omarchy-hibernation-remove:9` greps it for `^HOOKS+=(resume)$`, and
`omarchy-menu.jsonc:34` gates the Hibernate menu item on the first of those. #8888 handles all of
that deliberately. The alternative you raise at the end, folding `resume` into `omarchy_hooks.conf`
and toggling it, would need the same care and would also have to survive `omarchy-settings` being
reinstalled over it.

## What I have not done

I have not run a hibernate and power-on cycle on this machine, so I have not proven resume works end
to end here. What I believe is shown is narrower: the hook executes, after `encrypt` and before the
root mount, from last position, which is the step reported as impossible. And I could not read the
UKI to confirm its contents directly, because `/boot` is root-only and I did not want to use sudo to
check.

Thanks again for the depth of the original report, and sorry to arrive with a disagreement rather
than a confirmation.
