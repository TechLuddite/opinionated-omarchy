Comment for omacom/omarchy#12392, posted 2026-10-19 as https://github.com/omacom/omarchy/issues/12392#issuecomment-6282898451

@Azonnali, one addition to your proposal (2), from 4.0.5.

Since #14551 put `[omarchy]` first in `pacman.conf`, installing steam without the lib32 driver first, as a plain `omarchy pkg add steam` does, resolves to Omarchy's legacy NVIDIA userspace instead of Arch's. On a test VM (virtio GPU, `omarchy 4.0.5-1`, sync databases refreshed 2026-10-19, read-only `pacman -Sp`):

```
$ pacman -Sp --print-format '%r/%n %v' --noconfirm steam | grep -Ei 'nvidia|vulkan'
omarchy/nvidia-580xx-utils 580.178.04-1.1
omarchy/lib32-nvidia-580xx-utils 580.178.04-1.1
multilib/lib32-vulkan-icd-loader 1.4.363.0-1
```

With the same databases and only `[omarchy]` moved back to the end, its pre-4.0.5 position, the pick is `extra/nvidia-utils 615.78.08-1` and `multilib/lib32-nvidia-utils 615.78.08-1`. `nvidia-580xx-utils` provides `vulkan-driver nvidia-utils opengl-driver nvidia-libgl` and conflicts with `nvidia-utils`.

So an Intel or AMD machine bitten this way on 4.0.5 or later carries `lib32-nvidia-580xx-utils`, because `vulkan.sh` already installed the 64-bit driver. A machine with no 64-bit Vulkan driver, like this virtio VM (#14427), gets `nvidia-580xx-utils` as well. If your migration is widened beyond machines bitten before the 2026-09-19 steam fix, it needs the 580xx names alongside `nvidia-utils` and `lib32-nvidia-utils`, with the same hardware and dry-run guards.

Your proposal (1) checks out here. With `vulkan-intel` and `lib32-vulkan-intel` recorded as installed, steam resolves (exit 0) with no NVIDIA package, and the same for the radeon pair. With `vulkan-intel` alone it still pulls `omarchy/lib32-nvidia-580xx-utils`.

v4.0.6 changes no pacman, Vulkan or gaming files. We have not run it there.

---

Posted by Claude Opus 5.5 on behalf of TechLuddite. Every command ran against a copy of `/var/lib/pacman` passed with `--dbpath` (installed packages recorded with `-S --dbonly`), so nothing on the VM changed. Claude Opus 5.5 drafted this and ran the tests. Claude Fable 5.1 and GPT-6 Astra reviewed it.
