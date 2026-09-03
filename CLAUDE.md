# CLAUDE.md

Orientation for an agent picking this project up. For current status and what's
outstanding, read [JOURNAL.md](JOURNAL.md).

## What this project is

A working directory for **Omarchy Linux** agent skills and supporting research. Omarchy
is DHH's opinionated Arch + Hyprland distro. Two things live here:

1. **Upstream skills**, downloaded from `basecamp/omarchy` — [omarchy/](omarchy/) (system
   customization: Hyprland, theming, keybindings) and [diagnose-crash/](diagnose-crash/)
   (crash diagnosis from systemd-coredump).
2. **A troubleshooting corpus** in [research/](research/) — 456 real Omarchy/Arch
   desktop+laptop problems with verified, copy-pasteable fixes, searchable by symptom.

This **is** a git repository: `TechLuddite/opinionated-omarchy`, work happening on
`claude/greenfield-repo-setup-l5fzae`. Everything below about what is tracked and what is
generated is enforced by [.gitignore](.gitignore) and [.gitattributes](.gitattributes).

## Layout

```
omarchy/                 upstream skill: system customization  (7 files)
diagnose-crash/          upstream skill: crash diagnosis       (2 files)
opinionated-omarchy/     where the skill this repo is building will live, nothing written yet
  CLAUDE.md              what belongs here and what it has to beat; read before writing
research/                the troubleshooting corpus + its tooling
  README.md              design, record schema, trust model — read this first
  data/problems.jsonl    SOURCE OF TRUTH, one JSON record per line
  data/problems.db       DERIVED index; NOT tracked, build it after cloning
  data/categories.json   category key -> display label
  docs/*.md              DERIVED per-category markdown; tracked, see the rule below
  raw/                   unprocessed workflow output, kept for provenance
  tools/                 build/search/ingest scripts + the three workflow scripts
    corpus.py            the record schema + the only corpus reader/writer
  tests/                 stdlib-unittest tests for the writers; ./tests/run.sh
  bench/                 skill-efficacy measurements; NOT corpus, NOT generated
  validation/            induce a problem on a test VM, apply a fix, assert; runs.jsonl
                         is an append-only log and NEVER feeds audit_status
  *.md, *.html, hc.cpp   loose Hyprland wiki pages the user downloaded; NOT corpus
skillbench/              the Skill Bench container — measures whether a skill helps
  app/                   FastAPI app: runner, graders, loader, themed UI
  benches/               16 bench specs (9 Omarchy, 5 controls, gauntlet, crash)
  benches/CLAUDE.md      the bench-spec schema — read before writing or editing a bench
  skills.yaml            skill bundle manifest, points at ../omarchy and ../diagnose-crash
  data/                  DERIVED SQLite results DB; NOT tracked
tools/                   host-side scripts, not part of the corpus
  make-test-vm.sh        build/rebuild a test VM, installed unattended
  view-test-vms.sh       open a VNC window per test VM
  provision-bench-vm.sh  make a VM an agentic bench target (autologin, no lock, mirror)
  install-bench-key.sh   generate + install the bench's own ssh key on a VM
  golden-test-vm.sh      save/reset a VM's disk as a golden image (btrfs reflink, ~1s)
writeups/                post-mortems worth keeping outside the journal
JOURNAL.md               where we stopped, what's left
```

`opinionated-omarchy/` is **the destination for the skill this repo exists to produce** —
the one that makes the corpus agent-consumable. It is still several steps out, so no skill
is written there yet, but the slot is not speculative. It now holds
[opinionated-omarchy/CLAUDE.md](opinionated-omarchy/CLAUDE.md), which records what the skill
has to be, the +29.3 pt / −2.3 pt baseline it has to beat, and the provenance it must not
launder — read that before writing anything there. (That file also replaced the zero-byte
`.gitkeep` that used to hold the directory open, since git tracks files, not directories.)

A second placeholder, `omarchy-old/`, was deleted on 2026-08-28: nobody could recall what it
was for, which is reason enough not to keep an empty directory around.

## Environment

**Omarchy 4.0.0.alpha, Hyprland 0.56.2, bash, Python 3.14, UTF-8 throughout.** The
machine this repo is developed on *is* the system the corpus is about: `/usr/share/omarchy`
is present, so the Omarchy 4 layout described under "Domain facts" can be read directly
rather than inferred.

This is a Linux-native repository and nothing in it targets another platform. Two
conventions are enforced throughout, and both are load-bearing:

- **Generated files are written LF, explicitly.** Every `write_text` / `open("w")` in
  `research/tools/` passes `newline="\n"`, and `.gitattributes` normalises on top. Since
  `research/docs/` is tracked *and* fully regenerated on every build, anything that writes
  native line endings turns a rebuild into a ~1.5 MB whitespace-only diff.
- **Every read and write pins `encoding="utf-8"`.** Never rely on the ambient locale; the
  corpus contains typography, box drawing, arrows and a Nerd Font glyph, and a build that
  silently depended on `LANG` would be reproducible only by accident.

Scripts in `research/tools/` carry `#!/usr/bin/env python3` and are executable, so both
`./tools/ask.py …` and `python3 tools/ask.py …` work. Prefer `python3` over `python` in
anything written here: on Arch they are the same binary, but on a bare container often
only `python3` exists.

Python is not version-pinned — 3.11 through 3.14 all run the tooling, and every one of
them bundles a `sqlite3` with FTS5. A standalone `sqlite3` CLI exists on this machine but
nothing requires it; query through Python so the tooling stays self-contained.

### Verifying against a real install

Fixes can now be *checked*, not only cited. That happens in the throwaway VMs described
under "Test VMs" below, never on this workstation, so a fix that breaks boot or eats a
partition costs a rebuild instead of a machine.

Mind the version skew: `pacman -Q omarchy` reports **4.0.1-1** in the VMs and **4.0.0-1**
on this workstation, so a VM is not a mirror of the dev box and a difference between them
may be a release change rather than a bug. Read that from pacman, not from
`/usr/share/omarchy/version` — that file says `4.0.0.alpha` on *both* and is branding, not
the package version.

It does not change the corpus's trust model. `audit_status` records how a record was
verified **against its sources**, and one VM agreeing is not the same as a source
confirming — a fix can work by accident, or work only on that hardware. If you validate a
record live, say so explicitly in the record rather than silently upgrading its status.

## Test VMs

Two throwaway libvirt VMs. They do two jobs: verifying corpus fixes against a real
Omarchy install without risking the workstation, and serving as the targets the Skill
Bench's **agentic lane** drives. They are **disposable by design** — break one, delete it
and rebuild with `tools/make-test-vm.sh`, then re-provision:

```sh
tools/install-bench-key.sh 1 2     # the bench's own ssh key (never your ~/.ssh key)
                                   # provision also installs NOPASSWD sudo — without it
                                   # the agentic lane cannot seed, perform or assert
                                   # anything needing root, because it drives ssh with
                                   # no tty and nothing can answer a password prompt
tools/provision-bench-vm.sh 1 2    # autologin, never lock/blank/suspend, tmux mirror,
                                   # and pi pointed at the host's Ollama
tools/golden-test-vm.sh save 1     # capture that good state (VM must be shut off)
tools/golden-test-vm.sh save 2     # ONE VM PER INVOCATION — see below
```

**`golden-test-vm.sh` takes a single VM number; the other two take a list.** `save 1 2`
does not error — it saves VM 1 and silently ignores the `2`. Same for `reset`. That is how
both golden images went stale on 2026-09-02: a `reset` restored disks to a state captured
before `install-bench-key.sh` had ever run, so the pool came back with no bench key and no
tmux units and `/readyz` reported `ready:false` on both machines.

**Save the golden AFTER provisioning, not before**, and verify with a reboot — the units
are user-level and the honest test is that they come back on their own:

```sh
sudo virsh reboot opinionated-omarchy-test1
curl -s http://127.0.0.1:8878/readyz     # both VMs must be ready:true, tmux:true
```

Both are **provisioned to autologin and never lock**, which is not cosmetic — see the
lock trap under "Domain facts".

| | |
| --- | --- |
| Domains | `opinionated-omarchy-test1`, `opinionated-omarchy-test2` |
| Version | omarchy `4.0.1-1` (workstation is `4.0.0-1`) |
| Spec | 4 GiB RAM, 4 vCPU, 60 GiB btrfs on virtio, UEFI (Limine needs an ESP) |
| Network | libvirt `default` NAT, `virbr0`, 192.168.122.0/24, DHCP |
| Console | VNC on `127.0.0.1:5901` / `:5902` |
| Disk encryption | **off**, deliberately: LUKS would prompt for a passphrase on every boot and make headless use impossible |

### Credentials

These are **test-VM credentials committed in plain text on purpose.** They guard nothing:
the VMs are NAT-only, the VNC servers listen on loopback, and there is no real data on
them. Do not reuse this password anywhere, and change it before giving these machines a
routable address.

```
user / password : techluddite / omarchytest      (sudo via wheel, password required)
root password   : omarchytest
VNC password    : omarchy1                       (VNC truncates to 8 characters)
```

SSH is key-only-ready and works out of the box for `~/.ssh/id_ed25519` on this
workstation; password auth is still enabled as a fallback.

```sh
sudo virsh list --all                     # what exists
sudo virsh net-dhcp-leases default        # current IPs — DHCP, they change
ssh techluddite@<ip>
tools/view-test-vms.sh                    # open a VNC window for each
```

### Golden disk images beat snapshots here

`/var/lib/libvirt/images` is btrfs with no `NOCOW` flag, so `cp --reflink=always` shares
extents instead of copying bytes: capturing or restoring a 6.8 GiB VM disk takes **about a
second and charges no additional space** until one side is written. That is why
`tools/golden-test-vm.sh` exists and why libvirt snapshots — awkward on these UEFI/pflash
domains — were dropped rather than fought.

Measured, with a marker file to prove the reset was real: reset 1 s, boot to ssh 14 s, a
full cycle about 30 s, against *minutes* for a rebuild from the 5.9 GB ISO. The VM must be
**shut off** for both save and reset; a copy from a running domain is only crash-consistent.
`virsh shutdown` (ACPI) is ignored by these VMs — use `ssh <vm> 'sudo systemctl poweroff'`.

### The host firewall has to allow the VM bridge

Omarchy runs `ufw` with default-deny incoming and an `INPUT` policy of `DROP`. libvirt's
nftables table only manages the `forward` hook, so **nothing opens DHCP on the host** and
guests sit there retrying DHCP forever with no lease and no IP. Three rules fix it, and
they are scoped to `virbr0` so nothing is opened on the real network:

```sh
sudo ufw allow in on virbr0 to any port 67 proto udp   # DHCP
sudo ufw allow in on virbr0 to any port 53             # DNS
sudo ufw route allow in on virbr0 out on <wan-iface>   # NAT egress
```

This bites *after* a successful install rather than during one, which is confusing: the
5.9 GB ISO carries an offline package set, so the install completes perfectly with no
network at all and the machine only looks broken once it boots.

**The same gap catches Docker containers reaching Ollama**, and it is worth recognising as
one family rather than two incidents: libvirt and Docker both manage only forwarding, so
neither opens anything on the host's `INPUT` chain, which is `DROP`. The Skill Bench pins
its compose network to a fixed subnet precisely so the rule can name it — without that,
Compose allocates a fresh bridge whose name and range move, and an interface-scoped rule
silently stops matching:

```sh
sudo ufw allow from 172.28.7.0/24 to any port 11434 proto tcp \
  comment 'ollama api - omarchy skillbench container'
```

Symptom: `/readyz` reports `{"db":true,"ollama":false}` with an empty error string — a
connect timeout rather than a refusal.

### The VMs have no pacman sync databases

A consequence of that offline install: `pacman -Q` works but `pacman -S` cannot resolve
anything until the databases are fetched. Run `omarchy update` in the VM first. Do not
reach for `pacman -Sy` — see "Domain facts" below.

### How they were built

Not by hand. The Omarchy ISO supports unattended install from a drive labelled `cidata`
(the cloud-init NoCloud convention). `/usr/local/bin/omarchy-cidata-load` on the ISO looks
for one and, finding it, skips the `gum` configurator entirely and installs from the files
it carries — the same files the wizard would have written:

```
user_configuration.json     archinstall config + an omarchy_install section
user_credentials.json       username + SHA-512 password hashes
user_full_name.txt          \
user_email_address.txt       > optional, wizard-equivalent
user_encrypt_installation.txt/
authorized_keys             public keys; the installer writes them, runs
                            `systemctl enable sshd.service`, AND opens port 22
                            in the target's ufw — which is default-deny, so
                            without that last step sshd would be unreachable
```

`tools/make-test-vm.sh` generates that drive and defines the domain. Rebuild through it
rather than clicking the installer: the schema is unforgiving — partition sizes are
**bytes**, and the layout must match what the ISO's own configurator emits or archinstall
fails late with an unhelpful error.

Two notes on the domain definition. Boot order is HD-then-CD, so the empty disk falls
through to the installer on first boot and boots the installed system afterwards with no
need to eject anything. And the VMs were converted from SPICE to VNC afterwards — if you
do that yourself, `<channel type='spicevmc'>`, the USB `<redirdev>`s and
`<audio type='spice'>` all have to go at the same time, because libvirt refuses a domain
that keeps any of them without SPICE graphics.

## The Skill Bench

[skillbench/](skillbench/) is a self-contained container that answers one question with a
number: **does the Omarchy skill measurably improve a model, and at what cost in
context?** It has **two lanes**, and a bench declares which with `lane:`.

```sh
cd skillbench && docker compose up -d --build     # http://127.0.0.1:8878
./tests/run.sh                                    # 43 unit tests
```

Read [skillbench/README.md](skillbench/README.md) before changing it. The things that are
load-bearing:

- **The chat lane grades what a model *says*.** Tasks ask for commands; checks look for
  the right tool and the trap avoided. A real ceiling, not an oversight.
- **The agentic lane grades what an agent *does*.** It runs `pi` on a real test VM, lets
  it act, then asserts on the machine via each task's `post:` block. Concurrency there is
  the size of the VM pool, not `SB_CONCURRENCY`, because a case owns the machine it runs
  on. The UI keeps the two graders apart as QUALITY (transcript) and STATE (the VM):
  collapsing them would hide a model that describes the right edit and never makes it.
- **It runs on the HOST network** (`network_mode: host`). libvirt rejects every new
  forwarded connection into `192.168.122.0/24`, so a bridged container cannot reach the
  test VMs at all — and nothing in ufw can override it, because in nftables only
  `reject`/`drop` are terminal. This also removed the old pinned-subnet ufw rule for
  Ollama entirely; the app binds `127.0.0.1:8878` itself.
- **Five benches are controls** (`linux-disk-full`, `-runaway-process`,
  `-boot-partition-full`, `-pacman-keyring`, and `-agentic-triage` for the agentic lane),
  flagged `control: true`. They are general Linux the skill says nothing about, so the
  skill should barely move them. If a change lifts the controls as much as the Omarchy
  benches, it is measuring answer length rather than skill efficacy. **Do not delete them
  to tidy the suite** — they are the evidence, and every lane needs at least one (a test
  enforces this).
- **Everything is sha-pinned.** Edit a bench and the next run is a new series; edit a skill
  and resume refuses. Regrade re-scores from stored output with zero model calls.

### What the local models can actually do — check before designing a bench around them

Three independent gates decide whether a model can be measured on the agentic lane at
all, and they fail in different ways. `skillbench/tools/probe_models.py` reports the two
that are static; only a run answers the third. The full ladder, and which models sit
where, is [skillbench/MODELS.md](skillbench/MODELS.md) — **read it before concluding a
bench is too easy**, because "no lift" and "the model cannot drive the loop" look
identical in the score column.

The host settings that make any of it reproducible are on the **ollama systemd unit**,
not in this repo, so they are easy to lose:

```sh
systemctl show ollama -p Environment      # OLLAMA_CONTEXT_LENGTH, KV cache type, ...
```

- **`OLLAMA_CONTEXT_LENGTH=32768`** is the number that matters, and it is a *server* cap
  applied to every model. Ollama's own default is 4096. `pi --list-models` on a VM
  cheerfully reports `128K` — that is pi's client-side belief and it is **cosmetic**,
  because pi talks OpenAI-compat (`/v1`), which has no way to set `num_ctx`. Trust the
  server, not the client. At 32K the `omarchy` skill body (~3.1k tokens) is about 10% of
  the budget and `omarchy-full` (~6.6k) about 20%.
- **`OLLAMA_KV_CACHE_TYPE=q8_0` and `OLLAMA_FLASH_ATTENTION=1`** keep the KV cache small
  enough that a 30B Q4 model fits. Without them the same model spills to CPU.
- **`OLLAMA_MAX_LOADED_MODELS=1`** is why the runner finishes an entire suite on one model
  before touching the next — interleaving would evict and reload weights every case.
- **The card is a 24 GiB RTX 3090, and the 30B class already uses ~20.2 GiB at 32K.**
  That is the real ceiling: a 32B model may not fit, and a model that does not fit does
  not fail cleanly — it spills to CPU and the case dies on the agent timeout, which reads
  as a capability failure rather than a memory one. Check with `curl -s
  localhost:11434/api/ps` while a case is running.

The prior measurements this was built against — 911 graded cases from the lab's own bench,
on a byte-identical copy of `omarchy/SKILL.md` — are in
[research/bench/](research/bench/). That directory is hand-written and **not** generated:
`build_db.py` deletes every `*.md` in `research/docs/` on each build, so a hand-written
page cannot live there.

## Working with the corpus

```sh
cd research
python3 tools/ask.py "zoom screen share is a black rectangle"   # search by symptom
python3 tools/ask.py --tag nvidia --tag laptop --list           # filter by tag
python3 tools/ask.py --slug some-problem-slug -v                # exact lookup + sources
python3 tools/build_db.py                                       # rebuild DB + docs from JSONL
./tests/run.sh                                                  # 13 tests, stdlib only
```

**The JSONL is authoritative; the `.db` and `docs/` are derived.** Edit the JSONL, then
re-run `build_db.py`. Never hand-edit the database or the generated markdown, because the
build deletes and regenerates both.

The two derived artefacts are treated differently by git, and the difference is the whole
of the process:

- **`data/problems.db` is not tracked.** It is a 4 MB binary that is rewritten in full on
  every build, so committing it would put a new multi-megabyte blob in history each time.
  A fresh clone has no index. `ask.py` exits with `no database at ... Run: python
  tools/build_db.py`, so nothing fails silently, but **build it once after cloning.**
- **`docs/*.md` is tracked.** The point of that directory is that a human or an agent can
  read a category page straight out of the clone with no Python and no build step. That
  only holds if it is in the clone.

Which gives one rule: **a commit that changes `data/problems.jsonl` must change
`research/docs/` in the same commit.** Run the build before you stage anything, and check
that nothing is left over:

```sh
cd research && python3 tools/build_db.py
git diff --exit-code research/docs/     # must be clean once the build output is staged
```

There is no refresh cadence, and inventing one would be dishonest about what this is. The
corpus is a dated snapshot, not a feed. Rebuild when the JSONL changes; re-run a harvest
workflow only when there is a reason, such as an Omarchy release that changes the
underlying facts. Every record has now been audited except the 4 `unaudited` ones the
auditors never returned a verdict for. See [JOURNAL.md](JOURNAL.md).

Two ingest paths, and picking the wrong one destroys work:

- `tools/ingest.py` **replaces** the corpus from a full harvest result.
- `tools/merge_gapfill.py` **extends** it in place, and also applies audit verdicts to
  records already in the corpus. Use this for incremental work.

`merge_gapfill.py` has one behaviour worth knowing before you point it at anything: when a
result carries an `audit` block for a category, **it walks every record in that category**,
not only the ones you meant to audit. Records with no verdict keep their existing status,
so this is safe *provided the verdict set is scoped to the slugs you intended*. A stray or
hallucinated slug silently overwrites an already-audited record. Scope the verdicts, and
dry-run against a copy before pointing it at `data/problems.jsonl`.

Every record carries an `audit_status` (`ok` / `corrected` / `unaudited` /
`gapfill-unaudited`) recording how much scrutiny it survived. Unaudited records are
flagged in both the CLI and the markdown. **Preserve that honesty** — if you add records,
mark their provenance rather than letting them blend in with audited ones. As of
2026-09-01 no record carries `gapfill-unaudited`; the status stays reachable because
`merge_gapfill.py` still assigns it when an audit agent dies.

A second provenance field, `cause_reconciled` (a date, or absent), exists because the
first harvest's auditors could rewrite only `fix`. A `corrected` record from that pass
could therefore keep a `cause` its own `audit_note` disproved. All 130 such records were
read on 2026-08-30 and the 22 that were genuinely wrong were rewritten from their notes.
A further 7 were stamped on 2026-09-01 by the audit of the last unaudited records, so
**29 records carry the stamp across two dates**. **The disclaimer printed under the audit
note is conditional on this field** in both `ask.py` and the generated markdown — if you
reconcile more causes, set the field rather than editing the cause silently, or you
destroy the distinction between "checked and correct" and "never revisited".
`merge_gapfill.py` now sets it automatically whenever it applies a `corrected_cause`;
it did not always, and the consequences are written up in
[writeups/2026-09-01-merge-gapfill-silent-defects.md](writeups/2026-09-01-merge-gapfill-silent-defects.md).

### The record schema has one definition, and it is tested

Both corpus writers used to keep a **private copy** of the field list they project
records onto, so a field missing from that copy was dropped with no error and no
warning. `cause_reconciled` reached `schema.sql`, `build_db.py` and `ask.py` on
2026-08-30 and never reached `ingest.py`'s copy — the replace path would have thrown the
provenance away silently.

There is now one definition, in **[research/tools/corpus.py](research/tools/corpus.py)**,
and `ingest.py` and `merge_gapfill.py` both import it. Read that file before touching
either. Three rules it enforces:

- **`FIELDS` order is load-bearing.** It is the key order of all 456 lines on disk.
  Append; never reorder, or the next merge becomes a whole-corpus diff that hides the
  records actually touched.
- **`read_jsonl` / `write_jsonl` are the only ways in and out.** They pin `newline="\n"`
  and `encoding="utf-8"` in one place instead of at each call site.
- **An unrecognised key raises.** Harvest chaff the corpus deliberately drops
  (`cause_note`, `cause_extra`, `verify_note`) is enumerated in `WORKFLOW_ONLY`; anything
  else is an unfinished schema change and fails loudly.

Adding a field to the schema still touches **four** consumers — `schema.sql`,
`build_db.py`, `ask.py`, `corpus.py` — but two of those are now checked automatically.
`research/tests/` asserts `FIELDS` against `schema.sql` and against the live corpus, so
the 2026-08-30 mistake fails the suite instead of destroying data. Run it before
committing anything that touches the tooling:

```sh
cd research && ./tests/run.sh
```

## Domain facts that are load-bearing

Get these wrong and you will write fixes that break machines. They were all verified
against primary sources during the research and repeatedly caught stale advice.

- **`basecamp/omarchy`'s default branch is `quattro`, not `master`.** `master` is still
  the Omarchy 3 tree; several raw URLs 404 against it. Fetch from `quattro`.
- **Omarchy 4 ("Quattro") is pacman-packaged at `/usr/share/omarchy`**, with state in
  `~/.local/state/omarchy`. It is *not* a git checkout at `~/.local/share/omarchy` —
  that was Omarchy 3, and most advice online still assumes it.
- **Hyprland 0.55+ deprecated hyprlang in favour of Lua.** Config is `hyprland.lua` using
  the `hl.*` API (`hl.bind`, `hl.monitor`, `hl.window_rule`). Old `hyprland.conf` syntax
  still works but is not what Omarchy 4 ships. The 0.54 wiki has the old syntax.
- **Direct `pacman -Syu` is blocked** on Omarchy by an ALPM guard; the supported path is
  `omarchy update`. Bypass for one transaction with `OMARCHY_ALLOW_DIRECT_PACMAN=1`.
- **`pacman -Sy <pkg>` alone is a partial upgrade** and a classic way to break a system.
  Always `-Syu`. Treat any fix containing bare `-Sy` as a defect.
- The Omarchy menu is **Super+Space**; Super+Alt+Space is the Apps menu.
- **`hyprctl dispatch` takes Lua now, not a bare dispatcher name.** `hyprctl dispatch exec
  foo` fails on 0.56 with `')' expected near 'foo'`; the input is evaluated as
  `hl.dispatch(<your text>)`. Correct forms are `hl.dsp.exec_cmd("foo")` and
  `hl.dsp.dpms({ action = "on" })`. To launch a GUI app on a VM's session from ssh it is
  simpler to skip hyprctl entirely and set `WAYLAND_DISPLAY=wayland-1`.
- **`OMARCHY_PATH` is exported from `~/.bashrc`, so it is unset in a non-interactive ssh.**
  Every `omarchy` subcommand then fails with `find: '/themes/': No such file or directory`.
  Anything driving a VM over ssh must use a **login shell** (`bash -lc`). This also catches
  tmux: a window inherits the tmux *server's* environment, and a server started by a
  systemd user unit has no profile sourced at all.
- **Omarchy 4's lock screen cannot be released headlessly, and it outlives its client.**
  It is an `ext-session-lock` surface drawn by `omarchy-shell` (Quickshell) — `hyprlock` is
  not even installed. Its IPC exposes `lock()`, `status()`, `isLocked()` and deliberately
  **no `unlock()`**, so the only ways back in are typing the password (`virsh send-key`) or
  a rebuild. `pkill`ing the lock client makes it worse: the compositor stays locked with a
  stale frame, which `omarchy-hyprland-session-locked` documents as the case worth
  detecting (`LOCK` in `solitaryBlockedBy`). Prevention is the only real fix —
  `omarchy-toggle-idle stay-awake`, as `tools/provision-bench-vm.sh` does.

## Fetching sources

- **`wiki.archlinux.org` sits behind Anubis anti-bot.** `WebFetch` returns "Access
  Denied". Use `index.php?title=X&action=raw` or `rest.php/v1/page/X`, or `curl` with a
  browser user-agent. Cite the canonical `/title/` URL regardless.
- **`wiki.hypr.land` is JS-only.** Fetch the markdown source from the
  `hyprwm/hyprland-wiki` repo instead (`content/...`), e.g. via the `gh` API.
- `gh` CLI is authenticated and works for GitHub API queries.

## Conventions

- Never invent a source URL. A record cites only pages actually retrieved; `build_db.py`
  filters anything that isn't `http(s)://` and warns on records with no usable source.
- Fixes must be concrete — real commands, real paths, real config in fenced blocks. "Check
  your configuration" is not a fix and the audit rejects it.
- Fill `danger` whenever a fix can lose data, break boot, or cause a partial upgrade.
- The corpus is research, not a warranty. Anything touching pacman, the bootloader,
  initramfs, or partitions deserves a confirmation against the cited source before it
  runs as root.

## Regenerating the corpus

All three workflow scripts live in `research/tools/` and run via the `Workflow` tool
pointed at their `scriptPath`. **Pass the corpus root in `args`** — the path used to be
hardcoded to one developer's home directory, and a wrong root fails *inside an agent* as a
missing file rather than at launch:

```js
Workflow({ scriptPath: "research/tools/audit-existing-workflow.js",
           args: { root: "/abs/path/to/research" } })
```

**They do different jobs and the difference is not obvious from the names:**

- `harvest-workflow.js` — full harvest from scratch: one harvester per category, each
  audited, plus a gap-fill pass. ~35 agents, expensive.
- `gapfill-workflow.js` — **harvests new records** against auditor-named gaps and audits
  only those new records. ~25 agents. Its `GAP_CATEGORIES` list drives the *harvest*
  phase; its only audit-existing path is Track A, hardcoded to `apps-services`.
- `audit-existing-workflow.js` — **audits records already in the corpus** and harvests
  nothing. Retarget by editing `BATCHES`. ~1 agent per 6-8 records.

Pick by what the records need, not by category. Records that exist but are unaudited need
the third script; pointing `GAP_CATEGORIES` at their category re-harvests the same topics
as `-2` suffixed duplicates and audits nothing that already exists. That mistake was
written into JOURNAL.md as the recipe for a whole session before anyone caught it.

These consume a lot of budget (the first harvest died partway through on a spend limit).
Check `/usage-credits` before launching, and prefer trimming a workflow's category list
over re-running everything. `resumeFromRunId` did **not** behave well here — see
[JOURNAL.md](JOURNAL.md).
