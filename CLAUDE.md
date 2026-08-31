# CLAUDE.md

Orientation for an agent picking this project up. For current status and what's
outstanding, read [JOURNAL.md](JOURNAL.md).

## What this project is

A working directory for **Omarchy Linux** agent skills and supporting research. Omarchy
is DHH's opinionated Arch + Hyprland distro. Two things live here:

1. **Upstream skills**, downloaded from `basecamp/omarchy` — [omarchy/](omarchy/) (system
   customization: Hyprland, theming, keybindings) and [diagnose-crash/](diagnose-crash/)
   (crash diagnosis from systemd-coredump).
2. **A troubleshooting corpus** in [research/](research/) — 457 real Omarchy/Arch
   desktop+laptop problems with verified, copy-pasteable fixes, searchable by symptom.

This **is** a git repository: `TechLuddite/opinionated-omarchy`, work happening on
`claude/greenfield-repo-setup-l5fzae`. Everything below about what is tracked and what is
generated is enforced by [.gitignore](.gitignore) and [.gitattributes](.gitattributes).

## Layout

```
omarchy/                 upstream skill: system customization  (7 files)
diagnose-crash/          upstream skill: crash diagnosis       (2 files)
opinionated-omarchy/     where the skill this repo is building will live, nothing written yet
research/                the troubleshooting corpus + its tooling
  README.md              design, record schema, trust model — read this first
  data/problems.jsonl    SOURCE OF TRUTH, one JSON record per line
  data/problems.db       DERIVED index; NOT tracked, build it after cloning
  data/categories.json   category key -> display label
  docs/*.md              DERIVED per-category markdown; tracked, see the rule below
  raw/                   unprocessed workflow output, kept for provenance
  tools/                 build/search/ingest scripts + the two workflow scripts
  bench/                 skill-efficacy measurements; NOT corpus, NOT generated
  *.md, *.html, hc.cpp   loose Hyprland wiki pages the user downloaded; NOT corpus
skillbench/              the Skill Bench container — measures whether a skill helps
  app/                   FastAPI app: runner, graders, loader, themed UI
  benches/               12 bench specs (6 Omarchy, 4 controls, gauntlet, crash)
  skills.yaml            skill bundle manifest, points at ../omarchy and ../diagnose-crash
  data/                  DERIVED SQLite results DB; NOT tracked
tools/                   host-side scripts, not part of the corpus
  make-test-vm.sh        build/rebuild a test VM, installed unattended
  view-test-vms.sh       open a VNC window per test VM
  provision-bench-vm.sh  make a VM an agentic bench target (autologin, no lock, mirror)
  install-bench-key.sh   generate + install the bench's own ssh key on a VM
  golden-test-vm.sh      save/reset a VM's disk as a golden image (btrfs reflink, ~1s)
JOURNAL.md               where we stopped, what's left
```

`opinionated-omarchy/` holds a zero-byte `.gitkeep`. Git tracks files, not directories, so
an empty directory cannot be committed and would simply vanish from a clone; the `.gitkeep`
is the conventional way to hold the slot open. Delete it when real content lands.

That directory is **the destination for the skill this repo exists to produce** — the one
that makes the corpus agent-consumable. It is still several steps out, so nothing is written
there yet, but the slot is not speculative. (A second placeholder, `omarchy-old/`, was
deleted on 2026-08-28: nobody could recall what it was for, which is reason enough not to
keep an empty directory around.)

## Environment

**Omarchy 4.0.0.alpha, Hyprland 0.56.2, bash, Python 3.14, UTF-8 throughout.** The
machine this repo is developed on *is* the system the corpus is about: `/usr/share/omarchy`
is present, so the Omarchy 4 layout described under "Domain facts" can be read directly
rather than inferred.

This repository was previously developed on Windows and has been converted. Nothing here
targets Windows any more, and the concessions it required — ASCII-only stdout, a cp1252
console, `python` rather than `python3` — are gone. Two habits from that era were kept
because they are good practice independent of platform, and both are load-bearing:

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
tools/provision-bench-vm.sh 1 2    # autologin, never lock/blank/suspend, tmux mirror,
                                   # and pi pointed at the host's Ollama
tools/golden-test-vm.sh save 1 2   # capture that good state (VM must be shut off)
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
- **Four benches are controls** (`linux-disk-full`, `-runaway-process`,
  `-boot-partition-full`, `-pacman-keyring`), flagged `control: true`. They are general
  Linux the skill says nothing about, so the skill should barely move them. If a change
  lifts the controls as much as the Omarchy benches, it is measuring answer length rather
  than skill efficacy. **Do not delete them to tidy the suite** — they are the evidence.
- **Everything is sha-pinned.** Edit a bench and the next run is a new series; edit a skill
  and resume refuses. Regrade re-scores from stored output with zero model calls.

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
workflow only when there is a reason, such as the 28 records still awaiting audit or an
Omarchy release that changes the underlying facts. See [JOURNAL.md](JOURNAL.md).

Two ingest paths, and picking the wrong one destroys work:

- `tools/ingest.py` **replaces** the corpus from a full harvest result.
- `tools/merge_gapfill.py` **extends** it in place. Use this for incremental work.

Every record carries an `audit_status` (`ok` / `corrected` / `unaudited` /
`gapfill-unaudited`) recording how much scrutiny it survived. Unaudited records are
flagged in both the CLI and the markdown. **Preserve that honesty** — if you add records,
mark their provenance rather than letting them blend in with audited ones.

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

Both workflow scripts live in `research/tools/` and run via the `Workflow` tool pointed
at their `scriptPath`:

- `harvest-workflow.js` — full harvest from scratch: one harvester per category, each
  audited, plus a gap-fill pass. ~35 agents, expensive.
- `gapfill-workflow.js` — extend an existing corpus: audit unaudited categories and fill
  auditor-named gaps. ~25 agents.

These consume a lot of budget (the first harvest died partway through on a spend limit).
Check `/usage-credits` before launching, and prefer trimming a workflow's category list
over re-running everything. `resumeFromRunId` did **not** behave well here — see
[JOURNAL.md](JOURNAL.md).
