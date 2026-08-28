export const meta = {
  name: 'omarchy-problem-harvest',
  description: 'Harvest real Omarchy/Arch desktop+laptop problems with verified fixes into discrete records, audited against primary sources.',
  whenToUse: 'Building or refreshing the Omarchy/Arch troubleshooting corpus in research/data.',
  phases: [
    { title: 'Harvest', detail: 'One searcher per problem category → discrete problem records' },
    { title: 'Audit', detail: 'Per-category technical audit against Arch/Hyprland wiki; flag wrong or dangerous fixes' },
    { title: 'Gapfill', detail: 'Second pass on categories the auditor found thin' },
  ],
}

// ── Record schema ────────────────────────────────────────────────────────────
// Each problem is a discrete, DB-loadable record. Fixes must be copy-pasteable.
const PROBLEM_ITEM = {
  type: "object",
  required: ["slug", "symptom", "cause", "fix", "applies_to", "sources", "severity", "frequency"],
  properties: {
    slug: { type: "string", description: "kebab-case stable id, e.g. nvidia-black-screen-after-suspend" },
    title: { type: "string", description: "short imperative problem title" },
    symptom: { type: "string", description: "how a USER would describe it, in their words, incl. exact error text if any" },
    cause: { type: "string", description: "root cause, technically accurate" },
    fix: { type: "string", description: "exact steps: shell commands, file paths, config snippets. Copy-pasteable. Use markdown fenced blocks." },
    verify: { type: "string", description: "how to confirm the fix worked" },
    applies_to: {
      type: "array", items: { type: "string" },
      description: "tags: omarchy, arch, endeavouros, cachyos, manjaro, hyprland, wayland, nvidia, amd, intel, laptop, desktop, systemd-boot, grub, pipewire, etc.",
    },
    severity: { enum: ["critical", "high", "medium", "low"], description: "critical = unbootable/dataloss; high = core function broken" },
    frequency: { enum: ["very-common", "common", "occasional", "rare"] },
    danger: { type: "string", description: "any risk in the fix (dataloss, bricking, partial-upgrade). Empty string if none." },
    sources: { type: "array", minItems: 1, items: { type: "string" }, description: "URLs. Prefer wiki.archlinux.org, wiki.hypr.land, github issues, forums." },
  },
}
const HARVEST_SCHEMA = {
  type: "object", required: ["category", "problems"],
  properties: {
    category: { type: "string" },
    notes: { type: "string", description: "coverage notes: what you could not find good sources for" },
    problems: { type: "array", minItems: 8, maxItems: 30, items: PROBLEM_ITEM },
  },
}
const AUDIT_SCHEMA = {
  type: "object", required: ["verdicts"],
  properties: {
    thin: { type: "boolean", description: "true if this category clearly has well-known problems that were missed" },
    missing_topics: { type: "array", items: { type: "string" }, description: "specific problems that should have been covered but were not" },
    verdicts: {
      type: "array",
      items: {
        type: "object", required: ["slug", "status", "reason"],
        properties: {
          slug: { type: "string" },
          status: { enum: ["ok", "corrected", "reject"], description: "reject = wrong, dangerous, obsolete, or fabricated" },
          reason: { type: "string" },
          corrected_fix: { type: "string", description: "ONLY if status=corrected: the fixed version of the fix field" },
          confidence: { enum: ["high", "medium", "low"] },
        },
      },
    },
  },
}

// ── Categories ───────────────────────────────────────────────────────────────
const CATEGORIES = [
  { key: "omarchy-core", label: "Omarchy core", focus: "Omarchy installation and first boot failures, omarchy-update breaking things, omarchy migrations, omarchy-shell, the omarchy-* CLI commands and TUI menu, plugin system, config drift after update, Omarchy on VMs/bare metal, uninstalling/recovering. Search basecamp/omarchy GitHub issues+discussions, learn.omacom.io manual, r/omarchy." },
  { key: "omarchy-theming", label: "Omarchy theming & bar", focus: "Omarchy themes not applying, custom theme creation, waybar config/modules/CSS breakage, walker launcher issues, wallpapers, terminal (alacritty/ghostty/kitty) styling, fonts and nerd-font icons rendering as boxes, per-app theming, theme lost after omarchy-update." },
  { key: "hyprland-config", label: "Hyprland configuration", focus: "Hyprland config syntax errors and won't-start, window rules not matching, keybinding conflicts and submaps, workspace rules, animations/blur/opacity performance, gaps and borders, hyprctl, plugin/hyprpm breakage after Hyprland update, crash on reload, autostart/exec-once ordering." },
  { key: "display-monitors", label: "Displays & monitors", focus: "Multi-monitor setup in Hyprland, fractional scaling and blurry apps, HiDPI, refresh rate and VRR/adaptive sync, monitor hotplug not detected, external display over USB-C/DisplayPort/HDMI, docking stations, monitor ordering/position, laptop lid + external screen, wrong resolution, screen tearing." },
  { key: "wayland-compat", label: "Wayland app compatibility", focus: "XWayland apps blurry or broken, screen sharing and screencast failing (xdg-desktop-portal-hyprland), Zoom/Teams/Discord/OBS screen share, Electron and Chromium/Firefox Wayland flags, clipboard not persisting (wl-clipboard/cliphist), screenshots, Steam and games, Java/Qt/GTK apps, global hotkeys, drag-and-drop." },
  { key: "pacman-aur", label: "pacman & AUR", focus: "pacman errors: invalid or corrupted package, signature from unknown trust, keyring out of date, database lock, conflicting files exists in filesystem, partial upgrade breakage, mirror problems and 404s, AUR build failures with yay/paru, downgrading a package, .pacnew/.pacsave handling, cache filling the disk, unable to lock database." },
  { key: "boot-kernel", label: "Boot, kernel & initramfs", focus: "System won't boot after update, kernel panic, mkinitcpio hooks and missing firmware warnings, /boot partition full, systemd-boot vs GRUB entries missing, UEFI/ESP problems, dual-boot with Windows, LUKS encryption unlock, fstab errors dropping to emergency shell, rolling back a kernel, chroot recovery from live USB, secure boot." },
  { key: "gpu-drivers", label: "GPU & drivers", focus: "NVIDIA on Wayland/Hyprland (black screen, flicker, cursor artifacts, nvidia-drm modeset, env vars), hybrid graphics/Optimus and PRIME offload, AMD GPU issues, Intel graphics, driver install and DKMS build failures after kernel update, hardware video acceleration (VA-API), gaming performance, external GPU." },
  { key: "power-suspend", label: "Power, suspend & thermal", focus: "Suspend/resume failures, wake immediately after suspend, hibernation setup and swap sizing, poor battery life on Arch laptops, TLP vs power-profiles-daemon conflicts, CPU governors, fan noise and thermals, hypridle and hyprlock behavior, lid close actions, screen not waking, s2idle vs deep sleep." },
  { key: "audio-input", label: "Audio & input devices", focus: "PipeWire/WirePlumber no sound, wrong default sink, crackling or popping audio, Bluetooth headset profile and codec issues, microphone not detected, HDMI audio, touchpad gestures and tap-to-click, keyboard layout and remapping, input methods/IME for CJK, fingerprint reader, webcam." },
  { key: "network", label: "Networking", focus: "Wi-Fi not working or specific chipsets (Broadcom, Realtek, Intel), NetworkManager vs iwd, Wi-Fi slow or dropping, Bluetooth pairing failures, DNS resolution and systemd-resolved, VPN (WireGuard/OpenVPN) and split DNS, hotspot, ethernet, NFS/Samba mounts hanging, firewall." },
  { key: "apps-services", label: "Apps, containers & services", focus: "Flatpak apps unthemed or broken portals, Flatpak permissions, Docker/Podman on Arch, virtualization KVM/libvirt/VirtualBox, printing with CUPS, scanners, fonts and emoji rendering, filesystem full or btrfs snapshots, systemd service failures and journal debugging, time sync, locale errors, swap/zram." },
]

const HARVEST_PROMPT = (c) =>
  "## Problem Harvester: " + c.label + "\n\n" +
  "You are building a practical troubleshooting corpus for users of **Omarchy Linux** (DHH's opinionated Arch + Hyprland distro) " +
  "and other Arch-based distros (Arch, EndeavourOS, CachyOS, Manjaro) on desktops and laptops.\n\n" +
  "### Your category\n**" + c.label + "**\n" + c.focus + "\n\n" +
  "### Task\n" +
  "Run SEVERAL WebSearch queries (at least 4-6 distinct ones, varying phrasing — use the words real users type, " +
  "including verbatim error strings) and WebFetch the highest-signal pages. Prioritize these sources:\n" +
  "- wiki.archlinux.org (authoritative — use it to get fixes exactly right)\n" +
  "- wiki.hypr.land / hyprland.org and github.com/hyprwm/Hyprland issues\n" +
  "- github.com/basecamp/omarchy issues and discussions, learn.omacom.io\n" +
  "- bbs.archlinux.org, forum.endeavouros.com, r/archlinux, r/hyprland, r/omarchy, r/linuxquestions\n\n" +
  "Extract **15-25 DISTINCT real problems**. Quality bar for every record:\n" +
  "1. It is a problem real users actually hit and report — not a hypothetical you invented.\n" +
  "2. `symptom` is written the way a user would describe it, and includes the literal error message when there is one.\n" +
  "3. `fix` is CONCRETE and copy-pasteable: real commands, real file paths, real config snippets in fenced code blocks. " +
  "   Never write vague advice like 'check your configuration' or 'reinstall the driver'. If a fix needs a config file, show the lines.\n" +
  "4. `sources` are real URLs you actually retrieved. **Do not invent URLs.** If you did not fetch it, do not cite it.\n" +
  "5. `danger` is filled in whenever the fix can lose data, break boot, or cause a partial upgrade.\n" +
  "6. `slug` is unique, kebab-case, and descriptive.\n\n" +
  "Prefer problems that are COMMON over exotic ones, but do include the well-known nasty ones (they are high value).\n" +
  "Distinguish Omarchy-specific behaviour from generic Arch behaviour in `applies_to`.\n\n" +
  "Accuracy over volume: 15 correct records beat 25 with three wrong commands in them.\n\nStructured output only."

const AUDIT_PROMPT = (c, batch) =>
  "## Technical Auditor: " + c.label + "\n\n" +
  "Below are harvested troubleshooting records for Arch/Omarchy Linux. Users will COPY-PASTE these commands into a root shell. " +
  "A wrong command here breaks someone's machine. Audit them adversarially.\n\n" +
  "### Records\n" +
  batch.problems.map((p, i) =>
    "#### [" + i + "] " + p.slug + "\n" +
    "Symptom: " + p.symptom + "\n" +
    "Cause: " + p.cause + "\n" +
    "Fix: " + p.fix + "\n" +
    "Applies to: " + (p.applies_to || []).join(", ") + "\n" +
    "Sources: " + (p.sources || []).join(", ") + "\n"
  ).join("\n") + "\n\n" +
  "### For EACH record return a verdict\n" +
  "- **reject** if: the command/package/path does not exist or is misspelled; the advice is obsolete " +
  "(e.g. pre-PipeWire pulseaudio advice, old nvidia-drm flags, `pacman -Sy` alone causing partial upgrade); " +
  "it is dangerous without warning; the cited source does not plausibly exist or does not support it; " +
  "the 'problem' is fabricated or not a real reported issue; the fix is vague hand-waving.\n" +
  "- **corrected** if the problem is real but the fix is wrong or incomplete — supply `corrected_fix` with the right commands.\n" +
  "- **ok** if it is accurate, current, and actionable.\n\n" +
  "Use WebSearch/WebFetch against wiki.archlinux.org and wiki.hypr.land to CHECK specifics: exact package names, " +
  "current option names, current file paths. Do not approve from memory alone for anything version-sensitive.\n" +
  "Be strict about `pacman -Sy foo` (partial upgrade — should be `pacman -Syu foo`) and about any `rm -rf` on system paths.\n\n" +
  "Also flag whether the category is `thin` and list `missing_topics` — well-known problems in this category that were not covered.\n\n" +
  "Structured output only. One verdict per record, using the exact slug."

const GAPFILL_PROMPT = (c, missing) =>
  "## Gap-fill Harvester: " + c.label + "\n\n" +
  "A prior pass over this category missed these specific problems:\n" +
  missing.map(m => "- " + m).join("\n") + "\n\n" +
  "Research and produce records for these (and any closely-related common problems you find), using the same standard:\n" +
  "concrete copy-pasteable fixes with real commands and file paths, real fetched source URLs, no invented citations.\n" +
  "Verify specifics against wiki.archlinux.org / wiki.hypr.land before writing the fix.\n\n" +
  "Return 8-20 records.\n\nStructured output only."

// ── Run: harvest → audit (pipelined per category, no barrier) ────────────────
const results = await pipeline(
  CATEGORIES,

  c => agent(HARVEST_PROMPT(c), {
    label: "harvest:" + c.key, phase: "Harvest", schema: HARVEST_SCHEMA,
  }).then(r => {
    if (!r) { log("harvest failed: " + c.key); return null }
    log(c.key + ": harvested " + r.problems.length)
    return { c, batch: r }
  }),

  (harvested, c) => {
    if (!harvested) return null
    return agent(AUDIT_PROMPT(c, harvested.batch), {
      label: "audit:" + c.key, phase: "Audit", schema: AUDIT_SCHEMA,
    }).then(a => ({ ...harvested, audit: a }))
      .catch(e => { log("audit failed: " + c.key + " — " + (e.message || e)); return { ...harvested, audit: null } })
  },

  (audited, c) => {
    if (!audited) return null
    const a = audited.audit
    const missing = (a && a.missing_topics) || []
    // Only spend a gap-fill agent where the auditor found real, named holes.
    if (!missing.length) return audited
    log(c.key + ": gap-filling " + missing.length + " missed topics")
    return agent(GAPFILL_PROMPT(c, missing.slice(0, 12)), {
      label: "gapfill:" + c.key, phase: "Gapfill", schema: HARVEST_SCHEMA,
    }).then(g => ({ ...audited, gapfill: g }))
      .catch(() => audited)
  }
)

// ── Merge: apply audit verdicts, drop rejects, fold in gap-fill ──────────────
const kept = []
const rejected = []
const stats = []

for (const r of results.filter(Boolean)) {
  const verdictBySlug = new Map()
  for (const v of (r.audit && r.audit.verdicts) || []) verdictBySlug.set(v.slug, v)

  let ok = 0, corrected = 0, rej = 0
  for (const p of r.batch.problems) {
    const v = verdictBySlug.get(p.slug)
    // No verdict (auditor failed or missed it) → keep but mark unaudited.
    if (!v) { kept.push({ ...p, category: r.c.key, audit_status: "unaudited", audit_confidence: "low" }); continue }
    if (v.status === "reject") { rejected.push({ slug: p.slug, category: r.c.key, reason: v.reason }); rej++; continue }
    if (v.status === "corrected" && v.corrected_fix) {
      kept.push({ ...p, fix: v.corrected_fix, category: r.c.key, audit_status: "corrected", audit_note: v.reason, audit_confidence: v.confidence || "medium" })
      corrected++
    } else {
      kept.push({ ...p, category: r.c.key, audit_status: "ok", audit_confidence: v.confidence || "medium" })
      ok++
    }
  }
  // Gap-fill records are unaudited by construction — mark them honestly.
  for (const p of ((r.gapfill && r.gapfill.problems) || [])) {
    kept.push({ ...p, category: r.c.key, audit_status: "gapfill-unaudited", audit_confidence: "low" })
  }
  stats.push({
    category: r.c.key, harvested: r.batch.problems.length,
    ok, corrected, rejected: rej,
    gapfill: ((r.gapfill && r.gapfill.problems) || []).length,
    thin: !!(r.audit && r.audit.thin),
    notes: r.batch.notes || "",
  })
}

// Slug collisions across categories: suffix rather than drop, so nothing is lost.
const slugSeen = new Map()
for (const p of kept) {
  const base = p.slug
  const n = slugSeen.get(base) || 0
  slugSeen.set(base, n + 1)
  if (n > 0) p.slug = base + "-" + (n + 1)
}

log("TOTAL kept " + kept.length + " · rejected " + rejected.length + " across " + stats.length + " categories")

return { problems: kept, rejected, stats, categories: CATEGORIES.map(c => ({ key: c.key, label: c.label })) }
