Comment for omacom/omarchy#17705, posted 2026-11-05 as https://github.com/omacom/omarchy/issues/17705#issuecomment-6658716388

I could not reproduce this on stable with the default repository configuration, so it may be worth checking how this machine got hyprland 0.57.1-1 before stable gets the edge titlebars build.

On an x86_64 test VM on the stable channel, whose `/etc/pacman.d/mirrorlist` is the stock `stable-mirror.omarchy.org` line, `omarchy update -y` took omarchy 4.0.5-1 to 4.5.0-3 and exited 0. Migration 1791403310.sh installed `omarchy-hyprland-titlebars 0.2.2-2` next to `hyprland 0.56.2-4`. I ran it twice on 2026-11-05, restoring the same pre-update disk image in between, with the same result.

The omarchy-mirror README says the stable mirror "serves the Arch snapshot the current Omarchy release was tested against" and that "stable never syncs from upstream itself". I read `extra.db` from each mirror on 2026-11-05. `stable-mirror.omarchy.org`, `stable-mirror.omarchy.cn` (which the cn region profile adds) and `rc-mirror.omarchy.org` all list `hyprland 0.56.2-4`. The edge mirror `mirror.omarchy.org` and the Arch mirror `geo.mirror.pkgbuild.com` list `0.57.1-1`. So the stable mirrors and the stable `[omarchy]` repo agree with each other today, and 0.57.1 reached this machine some other way. A different `[extra]` server is one possibility. Earlier time on edge, an interrupted channel switch, or a package installed by hand would also do it.

The route matters for the fix. `omarchy-update-system-pkgs` upgrades with `pacman -Syu`, which never downgrades, so a machine that already has 0.57.1-1 installed keeps failing this migration even after its mirrorlist is corrected. That machine needs hyprland moved back to the stable version, or a stable titlebars build that accepts 0.57.1.

@LIghtJUNction, could you share the output of these commands? They would narrow it down.

```sh
pacman -Q hyprland
pacman-conf --repo-list
pacman-conf --repo=extra Server
grep -E '\] \[ALPM\] (installed|upgraded|downgraded|reinstalled) hyprland ' /var/log/pacman.log | tail -5
grep -E "\[PACMAN\] Running '.*(-Syyuu|-Suu| -U )" /var/log/pacman.log | tail -5
```

On the workaround: once 1791403310.sh is marked as done it does not run again, so titlebars stays uninstalled until it is added by hand with `omarchy-pkg-add omarchy-hyprland-titlebars`. On a machine where the update goes through, it is not needed.

Posted by Claude Opus 5.5 on behalf of TechLuddite. Tested on a libvirt VM on the stable channel. Revised after adversarial reviews by Grok 4.7 and GPT-6 Astra.
