#!/usr/bin/env python3
"""Run a corpus-validation scenario against a throwaway Omarchy VM.

    ./run.py scenarios/<slug>.yaml --vm 192.168.122.177
    ./run.py scenarios/<slug>.yaml --vm 192.168.122.177 --seed-only

Induces a problem on the VM, applies the scenario's `repair:` script, asserts on the
machine, and appends one record to runs.jsonl.

WHAT A GREEN RUN MEANS, AND WHAT IT DOES NOT. It means: this scenario's executable
reading of the record's prose produced the asserted end state, on this VM, on this
date, at this Omarchy version. It is NOT a source confirmation, and it must never
touch `audit_status` -- a fix can pass here by accident, or pass only on this
hardware. The corpus's trust model turns on `audit_status` meaning "checked against
its sources", and quietly widening it to "and it worked once in a VM" would destroy
the distinction. See README.md.

RUN THIS ONLY AGAINST A DISPOSABLE VM. Scenarios modify /etc and rebuild initramfs
as root, by design. Reset with `tools/golden-test-vm.sh reset <n>` afterwards.
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs.jsonl"
# Committed test-VM credential -- see CLAUDE.md. Guards nothing: NAT-only VMs with
# no real data. `sudo -S` because these runs are non-interactive.
SUDO_PW = "omarchytest"


def ssh(vm, user, script, timeout=600):
    """Run a script on the VM through a LOGIN shell.

    Two things here are load-bearing and neither is obvious.

    `bash -lc` is not optional: OMARCHY_PATH is exported from ~/.bashrc, so every
    `omarchy` subcommand fails in a plain non-interactive ssh with
    `find: '/themes/': No such file or directory`.

    Sudo authenticates through SUDO_ASKPASS, NOT `sudo -S`. There is no tty, so a
    password has to come from somewhere -- but `-S` reads it from stdin, which
    silently breaks every `... | sudo tee file` in a seed: tee then writes the
    PASSWORD into the file instead of the piped content, and the seed appears to
    succeed. An askpass helper leaves stdin alone.
    """
    preamble = (
        "export SUDO_ASKPASS=/tmp/.omarchy-validation-askpass\n"
        f"printf '#!/bin/sh\\necho %s\\n' {shlex.quote(SUDO_PW)} > \"$SUDO_ASKPASS\"\n"
        "chmod 700 \"$SUDO_ASKPASS\"\n"
        "sudo() { command sudo -A \"$@\"; }\n"
    )
    wrapped = preamble + script
    p = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         f"{user}@{vm}", "bash", "-lc", shlex.quote(wrapped)],
        capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check(vm, user, a, repair_out=""):
    """Evaluate one assertion. Returns (passed, note, raw_output).

    `repair_output_*` grades text the repair phase already produced. The
    alternative -- an assertion that re-runs the repair command to inspect its
    output -- makes grading a side effect, so a rebuild happens twice and the
    thing being measured is not the thing the repair did.
    """
    t = a["type"]
    if t.startswith("repair_output"):
        hit = re.search(a["pattern"], repair_out, re.M | re.S)
        if t == "repair_output_matches":
            return bool(hit), f"/{a['pattern']}/ {'matched' if hit else 'NOT matched'}", repair_out
        return not hit, f"/{a['pattern']}/ {'MATCHED (bad)' if hit else 'absent'}", repair_out
    rc, out = ssh(vm, user, a["command"])
    if t == "command_succeeds":
        return rc == 0, f"exit {rc}", out
    if t == "command_output_matches":
        ok = bool(re.search(a["pattern"], out, re.M | re.S))
        return ok, f"/{a['pattern']}/ {'matched' if ok else 'NOT matched'}", out
    if t == "command_output_not_matches":
        hit = re.search(a["pattern"], out, re.M | re.S)
        return not hit, f"/{a['pattern']}/ {'MATCHED (bad)' if hit else 'absent'}", out
    raise ValueError(f"unknown assertion type {t!r}")


def phase(vm, user, name, script, label):
    rc, out = ssh(vm, user, script)
    print(f"  {label:<10} exit {rc}")
    if rc != 0:
        print("    " + "\n    ".join(out.strip().splitlines()[-8:]))
    return rc, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--vm", required=True, help="IP of a DISPOSABLE test VM")
    ap.add_argument("--user", default="techluddite")
    ap.add_argument("--seed-only", action="store_true",
                    help="induce and stop, to inspect the broken state or hand it to an agent")
    ap.add_argument("--no-record", action="store_true", help="do not append to runs.jsonl")
    args = ap.parse_args()

    sc = yaml.safe_load(Path(args.scenario).read_text(encoding="utf-8"))
    print(f"scenario: {sc['slug']}  ->  {args.vm}")

    rc, ver = ssh(args.vm, args.user, "pacman -Q omarchy | awk '{print $2}'; uname -r")
    omarchy_v, kernel = (ver.split() + ["?", "?"])[:2]
    print(f"  target:    omarchy {omarchy_v}, kernel {kernel}")

    result = {
        "slug": sc["slug"], "scenario": Path(args.scenario).name,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vm": args.vm, "omarchy": omarchy_v, "kernel": kernel,
        "outcome": None, "asserts": [],
    }

    # ---- induce
    rc, _ = phase(args.vm, args.user, "seed", sc["seed"], "seed")
    if rc != 0:
        result["outcome"] = "seed-failed"
        return finish(result, args)
    for a in sc.get("seed_asserts", []):
        ok, note, _ = check(args.vm, args.user, a)
        print(f"    seed-check {'PASS' if ok else 'FAIL'}  {a['name']} ({note})")
        if not ok:
            result["outcome"] = "seed-failed"
            return finish(result, args)

    if args.seed_only:
        result["outcome"] = "seeded"
        print("  seeded and left broken (--seed-only)")
        return finish(result, args)

    # ---- repair
    repair_rc, repair_out = phase(args.vm, args.user, "repair", sc["repair"], "repair")

    # ---- assert
    print("  asserts:")
    passed = 0
    for a in sc["asserts"]:
        ok, note, _ = check(args.vm, args.user, a, repair_out)
        passed += ok
        print(f"    {'PASS' if ok else 'FAIL'}  {a['name']}  ({note})")
        result["asserts"].append({"name": a["name"], "passed": bool(ok), "note": note})

    total = len(sc["asserts"])
    result["outcome"] = ("pass" if passed == total and repair_rc == 0
                         else "repair-failed" if repair_rc != 0 else "fail")
    result["score"] = f"{passed}/{total}"
    print(f"  OUTCOME: {result['outcome']}  ({passed}/{total} asserts)")
    return finish(result, args)


def finish(result, args):
    if not args.no_record:
        with RUNS.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(f"  recorded -> {RUNS.relative_to(HERE.parent)}")
    return 0 if result["outcome"] in ("pass", "seeded") else 1


if __name__ == "__main__":
    sys.exit(main())
