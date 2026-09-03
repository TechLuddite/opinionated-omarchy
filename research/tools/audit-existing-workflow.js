// Audit records that are ALREADY IN the corpus. This is the third workflow shape, and
// the one the other two do not cover:
//
//   harvest-workflow.js   writes a corpus from scratch
//   gapfill-workflow.js   HARVESTS NEW records against auditor-named gaps, and audits
//                         only those new records
//   this file             audits records already on disk, changing no record's identity
//
// That distinction cost a session to rediscover. `GAP_CATEGORIES` in gapfill-workflow.js
// drives its *harvest* phase, so pointing it at a category whose records need auditing
// re-harvests the same topics as `-2` suffixed duplicates and audits nothing that already
// exists. The only audit-existing path in that file is Track A, hardcoded to
// `apps-services`. Use this script instead.
//
// TO RETARGET: edit BATCHES below — that is the whole parameterisation. Keep batches at
// roughly 6-8 records so each agent has budget to actually fetch each record's sources.
// Slugs are listed explicitly, never derived at runtime, for two reasons: the run stays
// deterministic and resumable, and a verdict can never land on a record you did not name.
// That second one is load-bearing — see the filter in the pipeline below.
//
// Run it with the Workflow tool pointed at this file's scriptPath, then:
//   python3 tools/merge_gapfill.py raw/<your-result>.json && python3 tools/build_db.py
//
// First used 2026-09-01 for the 28 gapfill-unaudited records; result kept as
// raw/audit-28-result.json.

export const meta = {
  name: 'audit-existing',
  description: 'Audit records already in the corpus, in batches, without harvesting anything new.',
  whenToUse: 'Records carry `unaudited` or `gapfill-unaudited`, or an audit agent died mid-run. Not for adding coverage — use gapfill-workflow.js for that.',
  phases: [
    { title: 'Audit', detail: 'One auditor per batch of records' },
  ],
}

// Agents read the corpus off disk by absolute path rather than receiving it through
// `args`: these records carry long `fix` blocks and round-tripping them through the
// tool call would cost more than the audit itself.
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

// The 28 records whose `gapfillAudit` came back NONE. Hardcoded rather than derived
// so the script is deterministic and resumable, and so a verdict can never land on a
// record outside this set — merge_gapfill.py applies verdicts to EVERY record in a
// category, and an unexpected slug would overwrite an already-audited record.
const BATCHES = [
  { category: 'wayland-compat', slugs: [
    'chromium-electron-keyring-password-prompt-every-launch',
    'drag-drop-fails-across-xwayland-boundary',
    'electron-chromium-ime-no-wayland-text-input',
    'flatpak-app-silently-runs-under-xwayland',
    'gtk4-libadwaita-apps-stuck-in-light-theme',
    'middle-click-primary-paste-stopped-working',
  ]},
  { category: 'wayland-compat', slugs: [
    'obs-virtual-camera-not-listed-v4l2loopback',
    'screenshare-has-no-audio',
    'tray-icons-missing-no-sni-host',
    'vm-remote-desktop-steals-or-leaks-compositor-binds',
    'wine-proton-native-wayland-driver',
    'xwayland-apps-wrong-cursor-theme',
  ]},
  { category: 'network', slugs: [
    'bluetooth-headset-no-microphone-hfp-profile',
    'bluetooth-pairing-lost-every-windows-dualboot',
    'interface-renamed-orphans-networkmanager-profile',
    'mdns-local-hostnames-fail-ufw-blocks-5353',
    'mt7921e-dead-after-suspend-aspm',
    'networkmanager-wait-online-delays-boot',
    'no-secret-agent-wifi-password-prompt-never-appears',
    'pmtu-blackhole-large-transfers-hang',
  ]},
  { category: 'network', slugs: [
    'r8169-rtl8111-link-flapping-r8168-dkms',
    'rtw88-rtl8821ce-unstable-disable-aspm',
    'six-ghz-channels-missing-world-regdomain',
    'tailscale-docker-containers-unreachable-stateful-filtering',
    'tailscale-exit-node-no-internet-ufw-forward',
    'usb-tethering-renamed-wwan-networkmanager-ignores',
    'wifi-throughput-collapses-with-bluetooth-audio',
    'wpa3-sae-association-fails-no-psk-available',
  ]},
]

const AUDIT_SCHEMA = {
  type: 'object',
  required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        required: ['slug', 'status', 'reason', 'confidence'],
        properties: {
          slug: { type: 'string', description: 'the exact slug audited' },
          status: { enum: ['ok', 'corrected', 'reject'] },
          reason: { type: 'string', description: 'what you checked, against which source, and what you found' },
          corrected_fix: { type: 'string', description: 'ONLY if status=corrected — the full replacement fix, markdown fenced' },
          corrected_cause: { type: 'string', description: 'ONLY if the CAUSE is also wrong — the corrected cause' },
          confidence: { enum: ['high', 'medium', 'low'] },
        },
      },
    },
  },
}

// Same verdict rules the rest of the corpus was audited under, so these 28 are held
// to the standard their category-mates already met.
const AUDIT_RULES =
  '### Verdict rules\n' +
  '- **reject** if: the command/package/path does not exist or is misspelled; the advice is obsolete ' +
  '(pre-PipeWire pulseaudio advice, `pacman -Sy` alone causing a partial upgrade, pre-Quattro Omarchy layout); ' +
  'it is dangerous without warning; the cited source does not support it; the problem is fabricated; the fix is vague.\n' +
  '- **corrected** if the problem is real but the fix is wrong or incomplete — supply `corrected_fix` as the FULL ' +
  'replacement fix, not a diff or a note.\n' +
  '- **ok** if accurate, current, and actionable.\n\n' +
  '**If the `cause` is ALSO wrong, supply `corrected_cause` as well.** Do not leave a cause standing that you just ' +
  'disproved in your reason — a reader trusts the cause to decide whether the record even applies to them.\n\n' +
  '### Two failure modes that dominated the last audit — look for both\n' +
  '- **Stale Omarchy 3 assumptions.** A cause or fix asserting a git checkout at `~/.local/share/omarchy` that ' +
  '`omarchy update` hard-syncs. Omarchy 4 is pacman-owned at `/usr/share/omarchy`; edits there vanish on package ' +
  'upgrade, and user config belongs in `~/.config/`.\n' +
  '- **Fabricated precision.** A confident specific the source does not support — an invented driver-version ' +
  'boundary, a package that does not exist on Arch, a config filename nobody can find, a systemd unit not in the ' +
  'repo. These read as MORE authoritative than the vague text around them, which makes them worse than vagueness. ' +
  'If you cannot confirm a specific, say so and correct it to what the source does support.\n\n' +
  '### Verify against primary sources, not memory\n' +
  'Check exact package names, current option names, and current file paths. Do not approve version-sensitive ' +
  'claims from memory.\n' +
  '- **`wiki.archlinux.org` sits behind Anubis anti-bot and WebFetch gets "Access Denied".** Use ' +
  '`https://wiki.archlinux.org/index.php?title=PAGE&action=raw` or `https://wiki.archlinux.org/rest.php/v1/page/PAGE`. ' +
  'Cite the canonical `/title/` URL regardless.\n' +
  '- **`wiki.hypr.land` is JS-only.** Fetch the markdown from the `hyprwm/hyprland-wiki` repo (`content/...`), ' +
  'e.g. via the `gh` API. `gh` is authenticated.\n' +
  '- `basecamp/omarchy`\'s default branch is **`quattro`**, not `master` — `master` is the Omarchy 3 tree and many ' +
  'raw URLs 404 against it.\n\n' +
  'Environment the corpus targets: Omarchy 4 ("Quattro"), Hyprland 0.56, PipeWire, NetworkManager, ufw. ' +
  'Hyprland config is **Lua** (`hyprland.lua`) since 0.55 deprecated hyprlang. Direct `pacman -Syu` is blocked by ' +
  'an ALPM guard in favour of `omarchy update`. Be strict about `pacman -Sy foo` (must be `-Syu` — a bare `-Sy` is ' +
  'a partial upgrade and is a defect) and about any `rm -rf` on a system path.\n\n' +
  'Structured output only. Return exactly one verdict per slug you were assigned, using the slug verbatim.'

const PROMPT = (cat, slugs, n) =>
  '## Technical Auditor: ' + cat + ' (batch ' + n + ')\n\n' +
  'These troubleshooting records were harvested into the corpus but **never audited** — the audit agent died on an ' +
  'API streaming error, and they have carried a `gapfill-unaudited` flag ever since. You are the audit they missed.\n\n' +
  'Users COPY-PASTE these commands into a root shell. A wrong command breaks someone\'s machine.\n\n' +
  '### Load the records\n' +
  'Read `' + JSONL + '` (JSON Lines, one JSON record per line) and take **only** these ' + slugs.length + ' slugs:\n' +
  slugs.map(s => '- `' + s + '`').join('\n') + '\n\n' +
  'A shell one-liner works well, e.g.:\n' +
  '```bash\n' +
  'python3 - <<\'PY\'\n' +
  'import json\n' +
  'want = set("""' + slugs.join(' ') + '""".split())\n' +
  'for line in open("' + JSONL + '", encoding="utf-8"):\n' +
  '    line = line.strip()\n' +
  '    if not line: continue\n' +
  '    r = json.loads(line)\n' +
  '    if r["slug"] in want:\n' +
  '        print(json.dumps(r, indent=2, ensure_ascii=False))\n' +
  'PY\n' +
  '```\n\n' +
  'Audit every one of those ' + slugs.length + ' adversarially — read each record\'s own `sources` and check the ' +
  'claims against them, plus the primary wikis below.\n\n' +
  'Do NOT audit any other record, and do NOT propose new records. Exactly ' + slugs.length + ' verdicts.\n\n' +
  AUDIT_RULES

phase('Audit')

const audited = await parallel(BATCHES.map((b, i) => () =>
  agent(PROMPT(b.category, b.slugs, i + 1), {
    label: 'audit:' + b.category + ':' + b.slugs.length,
    phase: 'Audit',
    schema: AUDIT_SCHEMA,
  })
    .then(r => {
      // Belt and braces: keep only verdicts for slugs this batch was assigned, so a
      // hallucinated or duplicated slug can never reach merge_gapfill.py and overwrite
      // an already-audited record's status.
      const want = new Set(b.slugs)
      const kept = (r.verdicts || []).filter(v => want.has(v.slug))
      const dropped = (r.verdicts || []).length - kept.length
      const missing = b.slugs.filter(s => !kept.some(v => v.slug === s))
      if (dropped) log('batch ' + (i + 1) + ' (' + b.category + '): dropped ' + dropped + ' out-of-scope verdict(s)')
      if (missing.length) log('batch ' + (i + 1) + ' (' + b.category + '): NO VERDICT for ' + missing.join(', '))
      log('batch ' + (i + 1) + ' (' + b.category + '): ' + kept.length + '/' + b.slugs.length + ' verdicts')
      return { category: b.category, verdicts: kept }
    })
    .catch(e => { log('batch ' + (i + 1) + ' (' + b.category + ') FAILED: ' + (e.message || e)); return null })
))

// Merge the per-batch verdicts back into one entry per category, which is the shape
// merge_gapfill.py's first stage consumes: results[].audit.verdicts
const byCat = {}
for (const r of audited.filter(Boolean)) {
  if (!byCat[r.category]) byCat[r.category] = []
  byCat[r.category].push(...r.verdicts)
}
const results = Object.keys(byCat).map(c => ({ category: c, audit: { verdicts: byCat[c] } }))

const all = results.flatMap(r => r.audit.verdicts)
const tally = all.reduce((a, v) => { a[v.status] = (a[v.status] || 0) + 1; return a }, {})
const causes = all.filter(v => v.corrected_cause).length
log('DONE: ' + all.length + '/28 verdicts — ' + JSON.stringify(tally) + ', ' + causes + ' with corrected_cause')

return { results, total: all.length, tally, corrected_causes: causes }
