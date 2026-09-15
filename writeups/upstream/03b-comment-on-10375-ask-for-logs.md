Hi, and thanks for reporting this with a real observed symptom rather than a theoretical one, which
makes it the most useful of the three threads on this.

I have posted a longer comment on #8471 arguing that the hook landing last in `HOOKS` is probably
not the cause, with kernel-log evidence from a boot on an encrypted-root machine where `resume` runs
from position 15, after `encrypt` and before root is mounted. I will not repeat it here.

The part that would help most is a log from your machine after a failed resume:

```bash
journalctl -b -1 -k | grep -i "PM: hibernation"
```

Two different answers point in two different directions:

- `PM: Image not found` means the hook did not resolve the resume device, which is a real bug and
  worth chasing on its own terms.
- `PM: Image successfully loaded` followed by a driver error is the shape in #8352, where several
  machines read the image fine and then failed in NVIDIA's `pci_pm_freeze` returning `-5`.

Your ASUS ProArt P16 is an NVIDIA machine, so the second is worth ruling in or out before anything
is changed about hook ordering. Happy to help read the output if you post it.
