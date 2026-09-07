export const meta = {
  name: 'omarchy-gapfill',
  description: 'Close the two holes left by the spend-limited harvest: audit apps-services, and fill the 117 gaps the auditors named.',
  whenToUse: 'After a harvest run left categories unaudited or gap-fill agents failed.',
  phases: [
    { title: 'AuditExisting', detail: 'Audit the apps-services records that were never reviewed' },
    { title: 'Gapfill', detail: 'One harvester per category, working the auditor-named misses' },
    { title: 'AuditNew', detail: 'Audit every newly harvested record — no unaudited records this time' },
  ],
}

// Agents read the corpus off disk by absolute path rather than receiving it
// through `args`: the apps-services records alone are ~50KB, and round-tripping
// them through the tool call would cost more than the audit itself.
// The corpus path, supplied by the caller. Pass it as the Workflow tool's `args`:
//     Workflow({ scriptPath: "...", args: { root: "/abs/path/to/research" } })
// This was a hardcoded absolute path under one developer's home directory, which is both
// unportable in a public clone and a silent failure: agents read the corpus off disk, so a
// wrong root produces "file not found" inside an agent rather than an error here. Failing
// loudly at launch is the whole point.
const ROOT = (typeof args === 'object' && args && args.root) || (() => {
  throw new Error("pass args { root: '/abs/path/to/research' } -- see the note above")
})()
const JSONL = ROOT + '/data/problems.jsonl'
const TODO = ROOT + '/raw/gapfill-todo.json'
const BRIEF = ROOT + '/tools/reaudit-brief.md'

// O2 (2026-09-06): fifteen of fifteen `ok` records checked against what Omarchy 4
// actually ships were wrong. The facts that catch them live in tools/reaudit-brief.md,
// and every harvester and auditor reads that file before writing a word.
const OMARCHY4 = (brief) =>
  "### Before anything else: what Omarchy 4 actually ships\n" +
  "Read `" + brief + "` in full and hold every claim to it. A record that matches the Arch wiki " +
  "but not that file is WRONG for this corpus. The shapes that caught the most records so far:\n" +
  "- `mkinitcpio -P` has no presets on Omarchy 4 (`/etc/mkinitcpio.d/` is empty). The rebuild is " +
  "`limine-mkinitcpio`, or `pacman -S linux`. There is NO fallback initramfs or fallback boot entry.\n" +
  "- The kernel is a UKI at `/boot/EFI/Linux/omarchy_linux.efi`; `/boot/vmlinuz-linux` does not exist. " +
  "The command line is inside the UKI, so kernel parameters go in `/etc/limine-entry-tool.d/*.conf`, " +
  "never `/boot/limine.conf`, which `limine-entry-tool` regenerates.\n" +
  "- `HOOKS` is assigned wholesale by `/etc/mkinitcpio.conf.d/omarchy_hooks.conf`; edits to " +
  "`/etc/mkinitcpio.conf` are overridden. Root is btrfs with subvolumes `@ @home @log @pkg`, ESP at `/boot`.\n" +
  "- `sudo pacman -Syu` is refused by the ALPM guard (it aborts any transaction carrying both `-S` " +
  "and `-u`). The path is `omarchy update`, or `OMARCHY_ALLOW_DIRECT_PACMAN=1` for one transaction. " +
  "A bare `pacman -Sy <pkg>` is a partial upgrade and a defect anywhere.\n" +
  "- Hyprland config is Lua: `hl.config({ section = { key = v } })`, `hl.window_rule`, `hl.monitor`. " +
  "`hl.set` does not exist. `hyprctl dispatch` takes Lua, not a bare dispatcher name.\n" +
  "- `sudo omarchy-<cmd>` breaks because sudo strips `OMARCHY_PATH`; the scripts call sudo themselves.\n" +
  "- `/etc/default/limine` is owned by no package and cannot get a `.pacnew`; the template is " +
  "`/etc/limine-entry-tool.conf`.\n" +
  "Where a fix differs between Omarchy 4 and plain Arch, write BOTH branches and label them. Use the " +
  "brief's fetching section for the Arch wiki (Anubis), the Hyprland wiki (JS-only) and the `quattro` " +
  "branch. Return verdicts through the structured output, not as files.\n\n"

const PROBLEM_ITEM = {
  type: "object",
  required: ["slug", "symptom", "cause", "fix", "applies_to", "sources", "severity", "frequency"],
  properties: {
    slug: { type: "string", description: "kebab-case stable id, unique" },
    title: { type: "string" },
    symptom: { type: "string", description: "how a USER would describe it, incl. literal error text" },
    cause: { type: "string" },
    fix: { type: "string", description: "exact copy-pasteable commands / config, markdown fenced" },
    verify: { type: "string" },
    applies_to: { type: "array", items: { type: "string" } },
    severity: { enum: ["critical", "high", "medium", "low"] },
    frequency: { enum: ["very-common", "common", "occasional", "rare"] },
    danger: { type: "string", description: "risk in the fix; empty string if none" },
    sources: { type: "array", minItems: 1, items: { type: "string" } },
  },
}
const HARVEST_SCHEMA = {
  type: "object", required: ["category", "problems"],
  properties: {
    category: { type: "string" },
    notes: { type: "string" },
    problems: { type: "array", minItems: 5, maxItems: 30, items: PROBLEM_ITEM },
  },
}
const AUDIT_SCHEMA = {
  type: "object", required: ["verdicts"],
  properties: {
    missing_topics: { type: "array", items: { type: "string" } },
    verdicts: {
      type: "array",
      items: {
        type: "object", required: ["slug", "status", "reason"],
        properties: {
          slug: { type: "string" },
          status: { enum: ["ok", "corrected", "reject"] },
          reason: { type: "string" },
          corrected_fix: { type: "string", description: "ONLY if status=corrected" },
          corrected_cause: { type: "string", description: "ONLY if the CAUSE is also wrong: the full replacement cause" },
          corrected_symptom: { type: "string", description: "ONLY if the symptom quotes a file, path or message that cannot occur: the full replacement" },
          corrected_danger: { type: "string", description: "ONLY if the danger is wrong or overstated for Omarchy 4: the full replacement" },
          corrected_verify: { type: "string", description: "ONLY if the verify step names something that does not exist on Omarchy 4: the full replacement" },
          sources: { type: "array", items: { type: "string" }, description: "every URL you actually retrieved and relied on for this verdict" },
          confidence: { enum: ["high", "medium", "low"] },
        },
      },
    },
  },
}

// The previous run's audit rewrote `fix` but left a wrong `cause` in place, so
// corrected records still carried the error the auditor had just identified.
// This prompt asks for `corrected_cause` too.
const AUDIT_RULES =
  OMARCHY4(BRIEF) +
  "### Verdict rules\n" +
  "- **reject** if: the command/package/path does not exist or is misspelled; the advice is obsolete " +
  "(pre-PipeWire pulseaudio advice, `pacman -Sy` alone causing a partial upgrade, pre-Quattro Omarchy layout); " +
  "it is dangerous without warning; the cited source does not support it; the problem is fabricated; the fix is vague.\n" +
  "- **corrected** if the problem is real but the fix is wrong or incomplete — supply `corrected_fix`.\n" +
  "- **ok** if accurate, current, and actionable.\n\n" +
  "**If the `cause` is ALSO wrong, supply `corrected_cause` as well.** Do not leave a cause standing that you just " +
  "disproved in your reason — a reader trusts the cause to decide whether the record even applies to them. " +
  "The same for `corrected_symptom`, `corrected_danger` and `corrected_verify`, and list the `sources` you relied on.\n\n" +
  "Verify specifics against wiki.archlinux.org and wiki.hypr.land — exact package names, current option names, " +
  "current file paths. Do not approve version-sensitive claims from memory.\n\n" +
  "Context that matters: **Omarchy 4 ('Quattro') is pacman-packaged at /usr/share/omarchy**, not a git checkout at " +
  "~/.local/share/omarchy; its Hyprland config is **Lua** (`hyprland.lua`), since Hyprland 0.55 deprecated hyprlang; " +
  "and direct `pacman -Syu` is blocked by an ALPM guard in favour of `omarchy update`. Records written against " +
  "Omarchy 3 assumptions are stale.\n\n" +
  "Be strict about `pacman -Sy foo` (should be `-Syu`) and any `rm -rf` on system paths.\n\n" +
  "Structured output only. One verdict per record, using the exact slug."

const AUDIT_EXISTING_PROMPT =
  "## Technical Auditor: Apps, containers & services\n\n" +
  "These troubleshooting records were harvested but never audited — the audit agent died before it ran. " +
  "Users will COPY-PASTE these commands into a root shell. A wrong command breaks someone's machine.\n\n" +
  "### Load the records\n" +
  "Read `" + JSONL + "` (JSON Lines, one record per line) and take **only** the records where " +
  "`\"category\": \"apps-services\"` — there are 26 of them. Use a shell one-liner or read the file directly.\n\n" +
  "Audit every one of those 26 adversarially.\n\n" + AUDIT_RULES + "\n\n" +
  "Also list `missing_topics`: well-known problems in this category (Flatpak portals/permissions, Docker/Podman, " +
  "KVM/libvirt, CUPS printing, fonts/emoji, btrfs snapshots, systemd/journal debugging, locale, zram) that the " +
  "26 records fail to cover."

// `topics` is supplied only for apps-services, whose gap list is produced by this
// same run and so is not yet on disk. Every other category reads its own list
// from TODO, keeping the prompt short.
const GAPFILL_PROMPT = (cat, topics) =>
  "## Gap-fill Harvester: " + cat + "\n\n" +
  "You are extending a practical troubleshooting corpus for **Omarchy Linux** (Arch + Hyprland) and other " +
  "Arch-based distros (Arch, EndeavourOS, CachyOS, Manjaro) on desktops and laptops.\n\n" +
  "### Your assignment\n" +
  (topics && topics.length
    ? "Work this list of missing topics:\n" + topics.map(m => "- " + m).join("\n") + "\n\nThose are "
    : "Read `" + TODO + "` — a JSON object mapping category -> list of missing topics. Take the list under the key " +
      "**`" + cat + "`**. Those are ") +
  "problems a prior auditor confirmed are well-known, commonly hit, and absent from " +
  "the corpus. Research each and write a record for it.\n\n" +
  "### Avoid duplicating what exists\n" +
  "Records already in the corpus live in `" + JSONL + "` under `\"category\": \"" + cat + "\"`. Skim their `slug` " +
  "and `symptom` fields first and do NOT re-file a problem that is already covered — the point is new coverage.\n\n" +
  OMARCHY4(BRIEF) +
  "### Standard for every record\n" +
  "1. It is a problem real users hit and report — not one you invented.\n" +
  "2. `symptom` is in a user's words, with the literal error message where there is one.\n" +
  "3. `fix` is copy-pasteable: real commands, real paths, real config in fenced blocks. Never 'check your config'.\n" +
  "4. `sources` are URLs you actually fetched. **Never invent a URL.** Prefer wiki.archlinux.org, wiki.hypr.land, " +
  "github.com/basecamp/omarchy, github.com/hyprwm/Hyprland, bbs.archlinux.org, forum.endeavouros.com.\n" +
  "5. `danger` is filled in wherever the fix can lose data, break boot, or cause a partial upgrade.\n" +
  "6. `slug` is unique and kebab-case. Prefix nothing — just describe the problem.\n\n" +
  "Current-state notes: Omarchy 4 ('Quattro') is pacman-packaged at /usr/share/omarchy; Hyprland config is **Lua** " +
  "(`hyprland.lua`) since 0.55 deprecated hyprlang; direct `pacman -Syu` is blocked in favour of `omarchy update`.\n\n" +
  "Cover every topic in your list that you can source properly. Accuracy over volume — skip one you cannot verify " +
  "rather than guessing at its fix.\n\nStructured output only."

const AUDIT_NEW_PROMPT = (cat, batch) =>
  "## Technical Auditor: " + cat + " (newly harvested records)\n\n" +
  "Audit these freshly harvested records adversarially before they enter the corpus. " +
  "Users will COPY-PASTE these commands into a root shell.\n\n" +
  "### Records\n" +
  batch.problems.map((p, i) =>
    "#### [" + i + "] " + p.slug + "\n" +
    "Symptom: " + p.symptom + "\n" +
    "Cause: " + p.cause + "\n" +
    "Fix: " + p.fix + "\n" +
    "Applies to: " + (p.applies_to || []).join(", ") + "\n" +
    "Sources: " + (p.sources || []).join(", ") + "\n"
  ).join("\n") + "\n\n" + AUDIT_RULES

// ── Track A: apps-services — audit what exists, fill its gaps, audit those ──
async function appsServices() {
  const audit = await agent(AUDIT_EXISTING_PROMPT, {
    label: "audit:apps-services", phase: "AuditExisting", schema: AUDIT_SCHEMA,
  }).catch(e => { log("apps audit failed: " + (e.message || e)); return null })
  if (!audit) return { category: "apps-services", audit: null }
  log("apps-services: " + audit.verdicts.length + " verdicts, " +
      ((audit.missing_topics || []).length) + " gaps named")

  const missing = audit.missing_topics || []
  if (!missing.length) return { category: "apps-services", audit }

  // Its gap list only exists now, so hand it over directly rather than via the file.
  const gf = await agent(GAPFILL_PROMPT("apps-services", missing), {
    label: "gapfill:apps-services", phase: "Gapfill", schema: HARVEST_SCHEMA,
  }).catch(() => null)
  if (!gf || !gf.problems.length) return { category: "apps-services", audit }

  const ga = await agent(AUDIT_NEW_PROMPT("apps-services", gf), {
    label: "auditnew:apps-services", phase: "AuditNew", schema: AUDIT_SCHEMA,
  }).catch(() => null)
  return { category: "apps-services", audit, gapfill: gf, gapfillAudit: ga }
}

// ── Track B: the 11 categories with a saved gap list ──
const GAP_CATEGORIES = [
  "omarchy-core", "omarchy-theming", "hyprland-config", "display-monitors",
  "wayland-compat", "pacman-aur", "boot-kernel", "gpu-drivers",
  "power-suspend", "audio-input", "network",
]

async function gapCategories() {
  // Pipelined: each category is audited the moment its harvest lands, so a slow
  // category never holds up the rest.
  return pipeline(
    GAP_CATEGORIES,
    cat => agent(GAPFILL_PROMPT(cat), {
      label: "gapfill:" + cat, phase: "Gapfill", schema: HARVEST_SCHEMA,
    }).then(r => {
      if (!r) { log("gapfill failed: " + cat); return null }
      log(cat + ": " + r.problems.length + " new records")
      return { category: cat, gapfill: r }
    }).catch(e => { log("gapfill failed: " + cat + " — " + (e.message || e)); return null }),

    (got, cat) => {
      if (!got || !got.gapfill.problems.length) return got
      return agent(AUDIT_NEW_PROMPT(cat, got.gapfill), {
        label: "auditnew:" + cat, phase: "AuditNew", schema: AUDIT_SCHEMA,
      }).then(a => ({ ...got, gapfillAudit: a }))
        // An audit failure must not discard the harvest — the records are still
        // useful, they just carry an honest "unaudited" flag downstream.
        .catch(e => { log("audit failed: " + cat + " — " + (e.message || e)); return got })
    }
  )
}

const [apps, gaps] = await parallel([appsServices, gapCategories])

const results = [apps, ...(gaps || [])].filter(Boolean)
const newCount = results.reduce((n, r) => n + ((r.gapfill && r.gapfill.problems.length) || 0), 0)
log("DONE: " + newCount + " new records across " + results.length + " categories")

return { results, newCount }
