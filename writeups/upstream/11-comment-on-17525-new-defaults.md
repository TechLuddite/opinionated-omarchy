Comment for omacom/omarchy#17525, posted 2026-11-05 as https://github.com/omacom/omarchy/issues/17525#issuecomment-6658716765

Each of the two packages has a package-specific route onto an older install, though neither PR sets a general policy for defaults added later.

#15508, which added `fcitx5-table-extra` to the base list, says "Existing installs get the package on demand from `omarchy setup input cangjie5`." That command runs `omarchy-pkg-add` on the preset's packages before it adds the engine. The Input Methods picker in the menu runs `omarchy setup input` with no argument, which installs nothing, and that is where the `Install fcitx5-table-extra to use Hong Kong (Cangjie)` refusal comes from. The picker also has no terminal for the `sudo` that `omarchy-pkg-add` needs.

`superwhisper-bin` was added for fresh installs in #14625, which says "Existing users’ backend choices remain unchanged." Migration `1793667581.sh` from #17407, which is in 4.5.0, installs it on an existing machine only when Superwhisper is already the selected dictation backend and `~/.local/share/superwhisper/app/current` is absent. A machine with another backend or none does not get it from that migration.

The same gap shows on stable. On an x86_64 test VM updated from 4.0.5-1 to 4.5.0-3 on 2026-11-05, with no dictation backend configured, `pacman -T $(omarchy-pkg-defaults)` reported these two packages missing and no others, out of 162 defaults.

That leaves your broader question open for a maintainer: whether `omarchy update` should install defaults added after the first install, and how an edge machine picks them up while staying on edge.

Posted by Claude Opus 5.5 on behalf of TechLuddite. Tested on a libvirt VM on the stable channel. Revised after adversarial reviews by Grok 4.7 and GPT-6 Astra.
