Thank you, this is better than what I sketched and it sent me to read things I should have read
first. One correction to my own concession, then the answer to your measurement question, which the
source settles.

## My sourcing sketch was wrong, but not for the reason I first agreed to

I was about to concede that sourcing pulls variables into the guard's scope and could collide with
something. That is not true: the sketch was `esp_path=$( . /etc/default/limine; echo "${ESP_PATH:-/boot}" )`,
a command substitution, so the subshell's variables never reach the caller.

The real hazard is the one your approach avoids anyway, and it is worth stating properly: **`sed`
reads the file, sourcing executes it**, and that file is not guaranteed to parse as bash. The
subshell inherits `set -e` and `esp_path=$(...)` is the last command of the `&&` list, so a parse
error exits the guard. Limine itself never requires the file to be bash: `load_key_value_config()`
in `limine-common-functions` regex-parses it, and the Java tool has its own parser. The README's own
example line

```
KERNEL_CMDLINE[kernel-6.10.1]="quiet splash"
```

is enough to kill a `source`, because bash evaluates the subscript arithmetically and
`kernel-6.10.1` is not valid arithmetic. So your `sed` version is correct, and mine was fragile.
Good catch.

## The copy is onto the existing path, so the multiplier is 1

The source answers this. `limine-entry-tool` is at `https://gitlab.com/Zesko/limine-entry-tool`, and
at tag 1.37.1:

- `src/main/java/org/limine/entry/tool/processes/LimineManager.java:256` in `addUki()`:
  `Utility.copyFileIfMissingOrDifferent(ukiFilePath, targetUkiPath)`, where `targetUkiPath` is
  `$ESP_PATH/EFI/Linux/omarchy_linux.efi`.
- `processes/Utility.java:200` `copyFileIfMissingOrDifferent()` blake2-hashes both sides and returns
  without writing if they match, otherwise calls `copyFile()`.
- `processes/Utility.java:185` `copyFile()` is
  `Files.copy(source, target, StandardCopyOption.REPLACE_EXISTING)`.

No temp name beside it, no rename. `REPLACE_EXISTING` unlinks the target before the new file is
created, so the old UKI's blocks are freed before the first byte of the new one lands. **Peak ESP
demand is one UKI, not two.** The only rename in the tool is `LimineWriter.save()` doing
`limine.conf.tmp` then `Files.move`, which is the atomic-config-write the README mentions and is
unrelated to the UKI.

Two riders on that:

- An `ENOSPC` part-way through leaves the ESP with **no** UKI at all, since the old one is already
  gone. That is a worse end state than a refused update, which strengthens the case for checking up
  front rather than relying on the copy to fail cleanly.
- `limine-snapper-sync` landing a snapshot kernel in the same window still moves the number, exactly
  as you said. The multiplier being 1 for the UKI does not remove the need for headroom.

## Two practical notes on the patch

`esp_path()` cannot be sourced from the guard. `bin/omarchy-provision-owner` runs under
`set -euo pipefail` and exits early unless it is root with `/var/lib/omarchy/provisioning/pending`
present, so reuse here means copying the seven lines rather than importing them. Still the right
seven lines.

The `stat`-derived threshold needs a privilege the guard does not have. `/etc/fstab:18` mounts
`/boot` with `fmask=0077,dmask=0077`, and the guard runs as the user (`omarchy-update` escalates per
step). On this machine:

```
$ stat -c '%s' /boot/EFI/Linux/*.efi
stat: cannot statx '/boot/EFI/Linux/*.efi': Permission denied
$ df --output=avail --block-size=1 /boot
1694658560
```

`df` is `statfs` and works unprivileged; `stat` on the file does not. Both call sites you cited run
as root (`omarchy-setup-direct-boot:41` is `sudo find ...`, and it globs `omarchy*.efi` rather than
`omarchy_linux*.efi`). So a size-derived threshold either wants a `sudo` the guard currently avoids,
or a fixed floor with the UKI size as a later refinement. Your instinct to stop maintaining a magic
number is right, it just needs that one extra step.

And yes, the stub: `write_stub df` never reads `$1`, so both calls return the same figure and an ESP
assertion cannot fail until it does.

## How this was produced

The issue was drafted and verified with Claude Opus 5 and adversarially reviewed by a separate Opus 5
instance before filing, which is what removed a claim about snapshots filling the ESP that turned out
to be false. This reply went through the same process with Claude Fable 5.1, and that review is what
caught my incorrect `set -e` concession above and found the `Files.copy` answer. Worth stating, since
you are being handed a source trace and should know how much of it was machine-derived.

If there is a trick to finding helpers like `esp_path()` in this tree quickly, I would take it. I
wrote a worse version of a function that already existed.
