Issue for omacom/omarchy

Title: Nothing in the update path measures ESP free space, including the post-transaction hook that
writes the UKI

Body:

Thanks for the pre-flight space check, it is a good addition and I can see #9893 is already making
it more helpful. This is about a filesystem it does not cover rather than a problem with the check
itself.

Versions: omarchy 4.0.2-1, omarchy-settings 4.0.2-1, limine 12.6.0-1, limine-snapper-sync 1.31.0-1,
limine-mkinitcpio-hook 1.37.1-1, snapper 0.13.1-3.

## What the guard measures

`bin/omarchy-update-requires-free-space` checks the root filesystem and nothing else:

```bash
read -r available_bytes < <(df --output=avail --block-size=1 / 2>/dev/null | tail -n 1) &&
  [[ $available_bytes =~ ^[0-9]+$ ]] &&
  (( available_bytes < 10 * 1024 * 1024 * 1024 ))
```

The ESP is a separate, much smaller filesystem, and it is where the kernel and the UKI end up. Here
it is 2 GiB:

```bash
findmnt -no SOURCE,TARGET,FSTYPE,SIZE,USED,AVAIL /boot
# /dev/nvme0n1p1 /boot vfat 2G 427.8M 1.6G
```

## Credit where it is due: snapshots are already handled

I want to be clear that I went looking for an unbounded-growth bug here and did not find one. Three
things already keep snapshot kernels from filling the ESP, and they look deliberate:

- `/etc/limine-snapper-sync.conf` ships `LIMIT_USAGE_PERCENT=85`, which refuses to add new Limine
  entries past that ceiling and notifies the user.
- `etc/limine-entry-tool.d/omarchy-defaults.conf` pins `MAX_SNAPSHOT_ENTRIES=6`, with a comment
  explaining it is Snapper's `NUMBER_LIMIT="5"` plus one for the creation window.
- `limine-snapper-sync` deduplicates snapshot kernels by hash and stores them compressed, so the ESP
  grows with distinct kernel versions rather than with snapshot count.

On this machine that works exactly as intended: 2 snapshot entries, one installed kernel, no
fallback UKI, `/boot` at 21% used.

## The gap

`LIMIT_USAGE_PERCENT=85` is a ceiling that `limine-snapper-sync` is entitled to grow **up to**. On a
2 GiB ESP that leaves roughly 307 MiB, and nothing downstream checks whether the UKI about to be
written fits in it.

The ordering is what makes this worth raising. Tracing an update end to end:

1. `omarchy-update` runs `omarchy-update-requires-free-space`, which measures `/`.
2. `omarchy-update-pkg-prune` runs `paccache -rk2`, which frees space on `/`.
3. `omarchy-snapshot create` runs, and the snapper plugin syncs a Limine entry to the ESP. This is
   the step `LIMIT_USAGE_PERCENT` governs.
4. `omarchy-update-system-pkgs` runs `pacman -Syu`. **The transaction commits here.**
5. `/etc/pacman.d/hooks/90-mkinitcpio-install.hook`, `When = PostTransaction`, runs
   `/usr/share/libalpm/scripts/limine-mkinitcpio-install`, which builds the UKI in a temporary
   directory and copies it to the ESP.

Step 5 is the only step that writes a UKI, it happens after the transaction has committed, and it
has no space check. Grepping `limine-common-functions`, `limine-mkinitcpio`, `limine-update`,
`limine-install` and `limine-mkinitcpio-install` for `df`, `avail`, `space` or `stat -f` returns
nothing, and `strings /usr/lib/limine/limine-entry-tool` shows FAT32 validity messages but no free
space pre-check.

So if the ESP is short at step 5, for whatever reason, the failure lands in a post-transaction hook
rather than in the guard that exists to catch exactly this class of problem. That is a worse place
to be told than up front.

## Suggested fix

Extend the existing guard to the ESP. `/boot` should not be hardcoded, because
`limine-common-functions:77` `find_boot_partition()` searches `/efi`, `/boot`, `/boot/efi` and
`/limine`, and there are installs in the tracker that are not at `/boot` (#7410, #8358, #7867).
Reading `ESP_PATH` from `/etc/default/limine` keeps it correct on those:

```bash
if [[ ${OMARCHY_UPDATE_FORCE:-0} == "1" ]]; then
  exit 0
fi

check_free() { # $1 mountpoint, $2 required bytes, $3 label
  local avail
  read -r avail < <(df --output=avail --block-size=1 "$1" 2>/dev/null | tail -n 1) || return 0
  [[ $avail =~ ^[0-9]+$ ]] || return 0
  if (( avail < $2 )); then
    echo "You need at least $3 free on $1 to safely update Omarchy."
    exit 1
  fi
}

esp_path="/boot"
[[ -r /etc/default/limine ]] && esp_path=$( . /etc/default/limine; echo "${ESP_PATH:-/boot}" )

check_free / $((10 * 1024 * 1024 * 1024)) "10 GiB"
check_free "$esp_path" $((300 * 1024 * 1024)) "300 MiB"
```

`df` on a missing mountpoint exits non-zero and prints nothing, so `read` fails and `|| return 0`
skips the check rather than tripping `set -e`. If the ESP is not a separate mount, `df` returns the
root figure and the second check passes trivially.

I have not benchmarked the right ESP threshold. It wants to be about one UKI plus margin, and
whoever knows the expected UKI size can pick a better number than I can. Worth noting that
`test/shell.d/update-disk-space-test.sh`'s `df` stub ignores its argument and returns a single
global, so it would need a small change to cover a second call.

## What I checked and what I did not

Checked on a live 4.0.2-1 install: the guard's contents are byte-identical to `quattro`, the update
path above was traced through each script, the ESP is a separate vfat mount, `ESP_PATH="/boot"`, and
the three snapshot guards above are present and working.

Not checked: I have not filled an ESP and run `omarchy update` to watch it fail. The gap is that
nothing measures the ESP before the hook that writes to it, which is verifiable by reading the
scripts. Whether a user realistically reaches that state is a separate question and I have no field
evidence for it, so treat this as a missing guard rather than a reported failure. Happy to reproduce
it in a VM if that would be more useful than the trace.
