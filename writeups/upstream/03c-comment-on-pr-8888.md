Thanks for putting a complete change together here. Updating `omarchy-hibernation-setup` and
`omarchy-hibernation-remove` in step, adding a migration and adding a test is more thorough than I
expected, and if the repositioning is wanted then this is the shape it should take.

My hesitation is upstream of the implementation: I am not convinced the ordering is load-bearing. I
have posted the detail on #8471, but the short version is that `/usr/lib/initcpio/init` runs every
`run_hook` at line 43 and only mounts root at line 67, `filesystems` and `fsck` have no runtime hook
at all, and `btrfs-overlayfs` is a `run_latehook`, so `resume` at position 15 is the next `run_hook`
to execute after `encrypt`. On an encrypted-root machine here the kernel log shows the resume attempt
landing after dm-crypt initialises and before the first mount of the root filesystem.

If that holds, this PR takes on migration and compatibility risk without a behaviour change to show
for it, which seems like the wrong trade even though the code is sound. If it does not hold, I would
rather be corrected here than have the maintainers act on my say-so, so please push back.

One thing worth doing either way, independent of ordering: #11791 reports that the enterprise Wi-Fi
path creates a fresh profile rather than reusing an existing one. Unrelated to this PR, but it is the
other place in the tree where a drop-in and a generated config disagree about who owns the value.
