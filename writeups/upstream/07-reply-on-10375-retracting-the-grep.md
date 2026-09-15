One more note after saying I would leave this with you, because it is a correction to something I
handed you rather than a reopening of the argument.

**The grep I gave you was broken, and I am sorry.** I suggested
`journalctl -b -1 -k | grep -i "PM: hibernation"`. That line cannot match the message that matters.
The kernel prints it from `kernel/power/swap.c` under `pr_fmt "PM: "`, so it reads
`PM: Image not found (code -22)`, with no "hibernation" in it. On this machine, where the hook
demonstrably did run (the kernel logged exactly that line, between `device-mapper: ioctl ...
initialised` and `BTRFS info (device dm-0): first mount of filesystem`), my own grep returns nothing
at all.

So "no resume attempt logged at all" is also what my instruction produces on a machine where the
attempt happened. I may have handed you a false negative and then leaned on it.

There are three things that produce that silence and only one of them is hook position:

1. The grep missing `PM: Image not found`, as above.
2. `systemd-hibernate-resume` bailing out before it writes. On systemd 255 and newer the hook execs
   that binary rather than writing `/sys/power/resume` itself, and it logs to the console, not the
   journal, so with `quiet splash` an early exit leaves no trace anywhere.
3. `resume` genuinely not in the image.

**A zero-risk way to tell them apart, if you are curious.** Omarchy keeps a persistent journal, so
your pre-fix failed boot is probably still on disk. No rebuild, no hibernate, nothing to revert:

```bash
journalctl --list-boots
journalctl -b <ID-of-the-failed-boot> -k | grep -E "PM: |resume|hibernat"
```

`PM: Image not found` means the hook ran and found nothing at the offset. `PM: hibernation: resume
from hibernation` means it ran and found the image. Nothing at all points at 2 or 3.

**And a retraction.** I had a theory that the rebuild rather than the reorder was the fix. It does
not hold: `omarchy-hibernation-setup` writes the drop-in at line 89 and runs `sudo limine-mkinitcpio`
at line 125 in the same invocation, so your image was rebuilt either way and a stale UKI was never a
plausible explanation. Scratch that one.

**On the NVIDIA half, one refinement to a finding I think is correct.** `/proc/driver/nvidia/suspend`
is missing on `nvidia-open-dkms` here too, but the driver flavour is not why. `nv-procfs.c` skips
creating it when `NVreg_UseKernelSuspendNotifiers=1`, which `nvidia-utils` sets by default in
`/usr/lib/modprobe.d/nvidia-sleep.conf`. The refusal you hit is in `nv.c`: with preservation on, the
freeze has to arrive via the procfs or notifier path, and the notifier handles
`PM_SUSPEND_PREPARE` and `PM_HIBERNATION_PREPARE` but not `PM_RESTORE_PREPARE`, which is what the
kernel fires before loading an image. So a restore from the initramfs trips it every time. Your
`NVreg_PreserveVideoMemoryAllocations=0` is the right fix regardless, and on Omarchy the `=1` comes
from `gpu-screen-recorder`'s `/usr/lib/modprobe.d/gsr-nvidia.conf` rather than from anything you set.
Nobody in #8352 had reported a working setting, so that is a genuinely useful result.

The thread is still yours, and my earlier hand-off stands.

For transparency on method: my comments here were drafted and verified with Claude Opus 5 and
reviewed by a separate instance, and this one went through Claude Fable 5.1, which is what caught
the broken grep and the rebuild theory above. Your approach of going and reading the logs settled in
one pass what my source-reading got wrong twice, which is the more reliable method of the two.
