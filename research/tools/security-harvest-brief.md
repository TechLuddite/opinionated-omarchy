# Security-harvest brief: records for the `security` category

Read this in full, then read [`reaudit-brief.md`](reaudit-brief.md) for what Omarchy 4
actually ships. From that brief you want **"The environment you are on"** and **"Fetching
sources"**. Ignore its **"Verdict"** section, which is for auditing existing records and not
for this job. Both briefs apply, and a record that satisfies this one while contradicting
that one is still wrong.

This category differs from the other twelve in one way. The corpus is published at
<https://techluddite.github.io/opinionated-omarchy/>, so a security record is a disclosure
whatever else it is. The other twelve tell a reader how to fix a broken machine. This one
tells them where machines are weak, and the same document reaches a different reader.

## The three gates

The full statement is in [`../README.md`](../README.md) under "Security records and
disclosure". This is the working summary.

**Gate 1 decides whether you may write the topic at all. Gates 2 and 3 decide what the
record may say**, so a draft that fails one of those gets rewritten, not reported back.

1. **The weakness is already public, and we are not the ones who made it public.** Either it
   appears in an upstream issue, an upstream code discussion, or a third party's report that
   predates anything this repository wrote, **or** the behaviour is the documented default,
   stated in the software's own documentation, its manual page, or the Arch wiki, and cited.
   Our own earlier publication counts as neither.
2. **No field states a condition, input or sequence that its cited source does not.** The
   bound covers `symptom`, `title`, `cause`, `fix`, `verify` and `danger`, not `cause` alone.
   Mechanism means the conditions or steps by which the weakness is used. One sentence of
   consequence in general terms, who can do what, is not mechanism.
3. **Mitigation, not reproduction.** Name the setting that is missing, the port that is open,
   the code path that does not validate its input. Never a walkthrough, never a working
   exploit, never a step that only helps somebody attacking a machine they do not own.

## Verifying is reading, never exercising

**Check a security claim by reading the setting or reading the code. Never by exercising the
weakness.** This holds on the workstation and on the test VMs equally. Do not stand up a
rogue access point, do not pass a traversal path to a command to see what happens, do not
capture a credential. If a claim cannot be settled by reading, say so and lower your
confidence.

`verify` follows the same rule. It confirms **the control is now present**, not that an
attack now fails. `nmcli -f 802-1x.ca-cert connection show "<SSID>"` is a verify. "Connect to
a spoofed SSID and confirm refusal" is not.

## What belongs here, and what belongs in another category

Three kinds of record belong in `security`:

1. **A control that is absent.** The software does the job and never checks something it
   should. An 802.1X profile that connects to any access point claiming the SSID.
2. **A control that is silently off.** Present, configurable, and not doing anything.
   `DNSOverTLS=opportunistic` falling back to plaintext without a warning.
3. **A failure whose common fix disables a control.** The symptom is ordinary breakage. The
   reason it belongs here is that the advice people find turns a protection off. A changed
   SSH host key fixed with `StrictHostKeyChecking=no`. A signature error fixed with
   `SigLevel = TrustAll`.

Kind 3 is the one that will feel wrong, because the symptom is "it does not work". File it
here anyway when the record's real content is the trap.

Everything else stays where it is. A profile that will not associate is a `network` record. A
machine that will not boot is `boot-kernel`.

## Check the existing corpus first, and expect hits

505 records already exist and several carry security content, sometimes in a `danger` field
rather than as their own record. **A slug collision is suffixed `-2` on merge rather than
refused**, so a duplicate you miss will land silently.

```sh
grep -n '"slug": "<guess>"' data/problems.jsonl
python3 tools/ask.py "<symptom text>"        # needs data/problems.db, build it first
python3 tools/build_db.py                    # if ask.py says there is no database
```

Known overlaps, confirmed present. Do not re-file these. Propose an edit to the named record
instead, and say which field:

| Topic | Already covered by |
| --- | --- |
| Marginal or unknown trust signature | `signature-unknown-trust-keyring-out-of-date`, whose `danger` already names the `SigLevel = TrustAll` trap |
| Keyring chicken-and-egg | `archlinux-keyring-outdated-blocks-every-upgrade`, whose `danger` already says never stop after `pacman -Sy`, and `omarchy-keyring-signature-unknown-trust` |
| WireGuard DNS leak | `wireguard-dns-resolvconf-missing`, whose `danger` already names the leak |
| mDNS and Avahi | `mdns-local-hostname-not-resolving`, which already names Avahi as the Omarchy 4 mDNS stack |
| 802.1X with no CA certificate | `wpa2-enterprise-8021x-connect-from-cli`. **This one fails gate 1**: the mechanism was published by this repository first. An edit to that record is the only legitimate outcome. Do not write a new record. |

## Read the code, not the issue state

An open issue is not evidence that a problem is current. Two of the first fourteen candidates
were already fixed in shipped code while their issues stayed open:

- `omarchy setup security sshd` leaving password auth on and opening the port before a key
  exists, issue #8363, fixed by PRs #9267 and #9255 plus a migration.
- The `[omarchy]` repo carrying `SigLevel = Optional TrustAll`, issue #9199. Current
  `pacman-stable.conf` and `pacman-edge.conf` carry no per-repo override, so it inherits
  `Required DatabaseOptional`. The issue is still open. Note that `/etc/pacman.conf` is owned
  by `pacman` and not by `omarchy-settings`, so a machine upgraded from Omarchy 3 may still
  hold the old line. Say so if you write this.

The reverse happens too. A fix can merge the day before you write, making the record true on
the installed version and false on the next release. Say which.

**Cite a pinned commit, not a moving branch.** A `sources` URL must carry a sha, for example
`https://github.com/omacom/omarchy/blob/<sha>/bin/foo`. `blob/quattro/...` moves under the
reader and the record stops meaning anything.

## `checked_against`

`"<pacman package version> <YYYY-MM-DD>"`, for example `"4.0.2-1 2026-09-17"`. Read the
version from `pacman -Q omarchy`, never from `/usr/share/omarchy/version`, which says
`4.0.0.alpha` and is branding. Leave it absent if you only read sources.

`audit_status: ok` means the record matches what it cites. `checked_against` means somebody
held it against a machine. Do not blur them.

## Severity, for this category

The usual scale is written for "it does not work" and does not fit. Use these:

- `critical`: unauthenticated remote or radio-range attacker reaches credentials, root, or
  arbitrary code, on a default install.
- `high`: a default leaves a credential, a privilege boundary or private data exposed, but
  the attacker needs proximity, a specific network, or a user action.
- `medium`: a hardening control is off or a default is weaker than the norm, with no direct
  path to credentials or code execution.
- `low`: information disclosure with no credential value, or a weakness needing an already
  compromised local account.

## The record

Same schema as every other category. The fields that behave differently here:

- `symptom` is what a user types into a search box. Often a question rather than an error:
  "is it safe that", "why can anyone on the network see". Keep their words.
- `fix` is copy-pasteable and closes the hole. "Review your configuration" is not a fix.
- `danger` is filled whenever the fix can lose data, break boot, or cause a partial upgrade,
  **and additionally whenever the obvious wrong fix disables a control.** This overrides the
  narrower rule in `issue-harvest-brief.md` for this category only. When naming a trap
  command, write it so `lint_corpus.py` does not flag it: it scans `danger` too, and a bare
  `pacman -Sy` matches even when the sentence says never to run it. Describe it in prose or
  include the `-u`.
- `applies_to`: include `omarchy` only when the record is true on a stock Omarchy install.
  Samba and cups-browsed are not installed by default, so those records say so in `symptom`
  and do not claim to apply to a machine that does not have them.

## Output

One file per batch, `raw/security-harvest-<batch>.json`, UTF-8, LF:

```json
{"records": [ {"slug": "...", "title": "...", "category": "security",
               "symptom": "...", "cause": "...", "fix": "...", "verify": "...",
               "applies_to": ["omarchy"], "severity": "...", "frequency": "...",
               "danger": "", "sources": ["https://..."],
               "checked_against": "4.0.2-1 2026-09-17"} ],
 "existing": [ {"topic": "PK1", "slug": "<existing slug>", "field": "danger",
                "suggestion": "..."} ],
 "skipped":  [ {"topic": "NET5", "reason": "no primary source, blog only"} ]}
```

`category` is the literal string `security` on every record. The operator adds that key to
`data/categories.json` at merge time, and `build_db.py` refuses the build until they do, so
do not add it yourself and do not worry that it is missing.

## If a topic fails gate 1

Some topic will turn out to be a weakness nobody has published. When that happens:

- **Write nothing about the mechanism.** Not in the record, not in `skipped`, not in your
  notes, not in your reply.
- Put it in `skipped` as exactly this and no more: the topic id, the URLs you searched, and
  `"reason": "no public source found, operator to review"`.
- Stop working that topic and move to the next one.
- **Do not report it upstream yourself**, do not open an issue, do not look for a security
  contact. That is the operator's job and it has a procedure you are not running.

## Writing rules

Follow `writing-and-responding`, as the rest of the corpus does. The ones broken most here:

- No em dashes, no en dashes, no semicolons, no spaced hyphens as punctuation. Rebuild the
  sentence rather than swapping one banned mark for another.
- Reproduce quoted source material exactly, punctuation included. A dash inside a quoted wiki
  sentence, manual page or issue title stays.
- Plain, specific words. None of the vocabulary security writing attracts. Say what the
  setting is and what happens without it.
- Do not imply the upstream author was careless. A missing default is an oversight until
  somebody shows otherwise, and a record does not need an opinion about it.
