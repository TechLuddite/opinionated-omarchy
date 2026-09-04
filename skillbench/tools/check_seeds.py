#!/usr/bin/env python3
"""Exercise every agentic bench seed repeatedly on a real VM, before spending hours on a run.

    python3 skillbench/tools/check_seeds.py                 # every agentic bench, 3 cycles
    python3 skillbench/tools/check_seeds.py --cycles 5 --bench linux-agentic-deep-triage

WHY THIS EXISTS. Run 30 lost 51 of 124 cases to `mount` exit 32 and took four hours to say
so. The cause was a seed whose teardown worked the FIRST time and failed every time after:
it unmounted before the previous holder had released its fd, deleted the image anyway, and
left a loop device attached to a dead inode. Run 27 lost a case to the same shape of bug, a
transient systemd unit left in FAILED state that `stop` does not clear.

Both were invisible to the way benches were being checked. The schema doc says to
hand-verify a seed on a VM, and that was done, ONCE. A seed is not a one-shot script: the
runner fires it before every case, so **the second cycle is the one that matters**. This
runs it N times and fails loudly on the first repeat that breaks.

It deliberately does NOT grade anything. Assertion discrimination is a separate question,
checked by hand against the shipped templates; this answers only "can the runner pose this
question over and over".
"""
import argparse
import glob
import os
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.path.join(ROOT, "secrets", "bench_ed25519")
SSH = ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
       "-o", "ConnectTimeout=10"]


def vms():
    """Hosts from SB_VMS in compose.yaml, so this checks the machines the runner uses."""
    with open(os.path.join(ROOT, "compose.yaml"), encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    env = (raw["services"]["skillbench"].get("environment") or {})
    spec = env.get("SB_VMS", "")
    out = []
    for part in spec.split(","):
        if "=" in part:
            name, host = part.split("=", 1)
            out.append((name.strip(), host.strip()))
    return out


def run_seed(host, seed, timeout=240):
    """Invoke the seed the way the RUNNER does, which means a LOGIN shell.

    Getting this wrong makes the checker worse than useless. A first draft used plain
    `bash -s` and reported omarchy-agentic-config/theme-switch as broken; it is fine. The
    seed calls `omarchy theme set`, and OMARCHY_PATH is exported from ~/.bashrc, so without
    `-l` every omarchy subcommand fails with `find: '/themes/': No such file or directory`.
    A checker that does not match vm.run() invents failures and hides real ones.
    """
    script = "set -euo pipefail\n" + seed
    p = subprocess.run(SSH + [f"techluddite@{host}", "bash -l -s"],
                       input=script, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=3,
                    help="times to run each seed back to back (default 3; 1 proves nothing)")
    ap.add_argument("--bench", help="limit to one bench name")
    args = ap.parse_args()

    targets = vms()
    if not targets:
        sys.exit("no VMs in compose.yaml SB_VMS")
    name, host = targets[0]
    print(f"host: {name} ({host})   cycles: {args.cycles}\n")

    failures = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "benches", "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
        if spec.get("lane") != "agentic":
            continue
        if args.bench and spec["name"] != args.bench:
            continue
        for task in spec.get("tasks") or []:
            seed = task.get("seed")
            if not seed:
                continue
            label = f"{spec['name']}/{task['id']}"
            ok = True
            for i in range(1, args.cycles + 1):
                try:
                    rc, out = run_seed(host, seed)
                except subprocess.TimeoutExpired:
                    rc, out = 124, "timed out"
                if rc != 0:
                    ok = False
                    failures += 1
                    print(f"  FAIL  {label}  cycle {i}/{args.cycles}  exit {rc}")
                    for line in out.splitlines()[-6:]:
                        print(f"          {line}")
                    break
            if ok:
                print(f"  ok    {label}  {args.cycles}/{args.cycles} cycles")

    print()
    if failures:
        print(f"{failures} seed(s) failed on repeat. A seed runs before EVERY case; "
              f"one that only works once will lose most of a run.")
        return 1
    print("all agentic seeds are repeatable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
