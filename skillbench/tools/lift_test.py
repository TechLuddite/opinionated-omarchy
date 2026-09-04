#!/usr/bin/env python3
"""Is a measured lift bigger than noise? Permutation test over a run's cases.

    python3 skillbench/tools/lift_test.py <omarchy_run_id> [control_run_id]

WHY THIS EXISTS. Runs 23/24 reported +11.1 pt on an Omarchy bench against +5.6 pt on the
control and the honest answer was "cannot tell" -- at n=3 the control's entire lift was ONE
assertion flipping. Comparing two percentages by eye cannot distinguish a real effect from
that, and the bench's whole argument rests on the Omarchy/control gap being real.

THE UNIT IS THE CASE, NOT THE ASSERTION. The 6 post assertions inside one case are heavily
correlated -- an agent that edits the right file usually satisfies three at once -- so
treating 60 assertions as 60 independent samples would overstate significance badly. Each
case contributes one score in [0,1] (post_passed / post_total).

NO SCIPY. A permutation test needs only the stdlib, matches the repo's dependency-free
tooling, and makes no normality assumption -- which matters because these scores are
clumped at a handful of discrete values (4/6, 6/6), not remotely bell-shaped.

Reports, per bench: the lift, a bootstrap 95% CI, and a two-sided permutation p-value.
With both runs it also reports the DIFFERENCE IN DIFFERENCES -- Omarchy lift minus control
lift -- which is the number the controls exist to produce. A skill that merely makes an
agent try harder lifts both, and only the DiD exposes that.
"""
import random, sqlite3, statistics, sys

DB = "skillbench/data/skillbench.db"
N_PERM = 20000
N_BOOT = 10000
random.seed(20260902)          # reproducible; re-runs give the same p


def cases(run_id, model=None):
    """One score per case: fraction of post assertions passed. Cases with no post
    assertions are dropped -- they carry no state signal."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = c.execute("""
        SELECT c.variant, c.task_id, c.status, c.output_source,
          (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='post') n,
          (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='post' AND g.passed=1) k,
          (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='check') cn,
          (SELECT count(*) FROM grade g WHERE g.case_id=c.id AND g.grader='check' AND g.passed=1) ck
        FROM case_result c WHERE c.run_id=?"""
        + (" AND c.model=?" if model else ""),
        (run_id, model) if model else (run_id,)).fetchall()
    out = {}
    for r in rows:
        # BOTH LANES. 'post' grades the machine and exists only on the agentic lane;
        # 'check' grades the transcript and is what the chat lane produces. Counting post
        # alone silently returned zero cases for every chat run, which reads as "need both
        # variants" rather than as "this tool does not handle that lane".
        n, k = (r["n"], r["k"]) if r["n"] else (r["cn"], r["ck"])
        if not n:
            continue
        # A gateway returns a bare 500 for a model the account cannot reach. That is a
        # configuration failure, not a score, and averaging it in would drag a variant
        # down for a reason that has nothing to do with the skill.
        if r["status"] == "unavailable":
            continue
        # A response truncated before it emitted any text cannot be graded ON its text.
        # Scoring it zero conflates "wrong" with "did not finish", and the conflation is
        # VARIANT-CORRELATED: on deepseek-v4-pro 81% of bare cases truncated against 19%
        # of skilled ones, because the skill makes answers shorter. Left in, that alone
        # manufactured a +37.1 pt Omarchy lift which is +9.1 once removed.
        if r["output_source"] == "empty":
            continue
        out.setdefault(r["variant"], []).append((r["task_id"], k / n))
    bench = c.execute("SELECT b.name FROM bench_run r JOIN bench b ON b.id=r.bench_id"
                      " WHERE r.id=?", (run_id,)).fetchone()[0]
    return bench, out


# linux-desktop-gauntlet mixes six Omarchy tasks with four general-Linux ones, so it
# carries its own control and a difference-in-differences can be computed WITHIN one run
# rather than needing a paired control run. Splitting here is not a convenience: averaging
# the two groups together reports a lift that is neither.
SPLITS = {
    "linux-desktop-gauntlet": {
        "omarchy": {"monitor-config", "shell-bar", "theme-customize", "wrong-tree-edit",
                    "privilege-escalation", "command-discovery"},
        "control": {"disk-full", "runaway-process", "boot-partition-full",
                    "pacman-keyring"},
    },
}


def perm_p(a, b):
    """Two-sided permutation test on the difference of means."""
    obs = statistics.mean(b) - statistics.mean(a)
    pool, na = a + b, len(a)
    hits = 0
    for _ in range(N_PERM):
        random.shuffle(pool)
        if abs(statistics.mean(pool[na:]) - statistics.mean(pool[:na])) >= abs(obs) - 1e-12:
            hits += 1
    return obs, (hits + 1) / (N_PERM + 1)


def boot_ci(a, b):
    diffs = []
    for _ in range(N_BOOT):
        ra = [random.choice(a) for _ in a]
        rb = [random.choice(b) for _ in b]
        diffs.append(statistics.mean(rb) - statistics.mean(ra))
    diffs.sort()
    return diffs[int(.025 * N_BOOT)], diffs[int(.975 * N_BOOT) - 1]


def _line(label, none, skill):
    obs, p = perm_p(list(none), list(skill))
    lo, hi = boot_ci(none, skill)
    print(f"  {label:<9} none n={len(none):<4} {statistics.mean(none):.3f} | "
          f"skill n={len(skill):<4} {statistics.mean(skill):.3f} | "
          f"lift {obs*100:+6.1f} pt  CI [{lo*100:+.1f}, {hi*100:+.1f}]  p={p:.4f}"
          f"  {'SIG' if p < 0.05 else '-'}")
    return obs


def report(run_id, model=None):
    bench, by = cases(run_id, model)
    none = by.get("none", [])
    skill = by.get("skill:omarchy", [])
    if not none or not skill:
        print(f"run {run_id} ({bench}): need both variants, got {list(by)}")
        return None
    head = f"run {run_id}  {bench}" + (f"  [{model}]" if model else "")
    print(head)
    obs = _line("overall", [x[1] for x in none], [x[1] for x in skill])

    # A mixed bench carries its own control, so the difference-in-differences comes out of
    # ONE run. Reporting only the pooled figure would state a lift that belongs to neither
    # group: on run 34 the pooled +18.6 pt was +28.8 on Omarchy tasks and +3.4 on controls.
    split = SPLITS.get(bench)
    if split:
        lifts = {}
        for name, ids in split.items():
            a = [sc for t, sc in none if t in ids]
            b = [sc for t, sc in skill if t in ids]
            if a and b:
                lifts[name] = _line(name, a, b)
        if len(lifts) == 2:
            did = lifts["omarchy"] - lifts["control"]
            print(f"  {'DiD':<9} {did*100:+6.1f} pt   (omarchy lift minus control lift)")
    return [x[1] for x in none], [x[1] for x in skill], obs


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    model = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--model=")), None)
    a = report(int(args[0]), model)
    if len(args) < 2:
        return
    print()
    b = report(int(args[1]), model)
    if not (a and b):
        return
    # Difference in differences: is the Omarchy lift bigger than the control's?
    # Permute variant labels within each bench independently, so the null is
    # "the skill does nothing different on Omarchy tasks than on general Linux".
    (an, ask, alift), (bn, bsk, blift) = a, b
    did = alift - blift
    hits = 0
    for _ in range(N_PERM):
        pa, pb = an + ask, bn + bsk
        random.shuffle(pa); random.shuffle(pb)
        da = statistics.mean(pa[len(an):]) - statistics.mean(pa[:len(an)])
        db = statistics.mean(pb[len(bn):]) - statistics.mean(pb[:len(bn)])
        if abs(da - db) >= abs(did) - 1e-12:
            hits += 1
    p = (hits + 1) / (N_PERM + 1)
    print(f"\nDIFFERENCE IN DIFFERENCES (omarchy lift - control lift)")
    print(f"  {did*100:+.1f} pt   p = {p:.4f}   "
          f"{'the skill helps Omarchy tasks MORE than general Linux' if p < 0.05 else 'NOT separable from the control -- could be answer length'}")


if __name__ == "__main__":
    main()
