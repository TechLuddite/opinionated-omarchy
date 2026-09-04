#!/usr/bin/env python3
"""What will a paired run cost on a pay-as-you-go gateway?

    python3 skillbench/tools/estimate_cost.py omarchy-wrong-tree-edit --repeats 31
    python3 skillbench/tools/estimate_cost.py --all --repeats 31 --budget 5

WHY THIS EXISTS. Local compute is electricity and nobody counted it, so the bench has
never had a cost model. On Zen it turned out that **API calls bill the pay-as-you-go
balance per token**, confirmed by watching the balance move 2 cents during a probe
session. The Go plan's request-per-5-hour caps govern its own routing, not this endpoint,
so the scarce resource for the bench is tokens after all.

That inversion matters: output is priced three to five times input, and the models worth
testing are reasoning models that emit long traces before answering. A run that looks
cheap on input can be dominated by output.

WHERE THE NUMBERS COME FROM. Per-case token use is MEASURED, not assumed: 272 banked
chat-lane cases carry real `prompt_tokens` and `completion_tokens`. Prices are the
published Zen per-million rates.

WHAT IT CANNOT KNOW. Every measured case ran against a LOCAL model, and most local models
are not reasoning models. Several Zen models spend 200 to 700 tokens reasoning before
producing any content, so real output may be well above the measured mean. `--reasoning`
applies a multiplier to output tokens; the default of 1.0 is the optimistic case and
should be read as a floor rather than an estimate.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCHES = REPO / "skillbench" / "benches"

# Measured from the 272 banked chat-lane cases that carry usage. See results/cases.jsonl.
MEASURED = {
    "none":          {"in": 127,  "out": 654},
    "skill:omarchy": {"in": 3286, "out": 320},
    # The full bundle is roughly 9k of input per case; kept for sizing a heavier variant.
    "skill:full":    {"in": 9018, "out": 317},
}

# Published Zen rates, USD per million tokens, input/output.
PRICES = {
    "glm-5":              (1.00, 3.20),
    "glm-5.1":            (1.40, 4.40),
    "glm-5.2":            (1.40, 4.40),
    "kimi-k2.5":          (0.60, 3.00),
    "kimi-k3":            (3.00, 15.00),
    "minimax-m2.5":       (0.30, 1.20),
    "minimax-m3":         (0.30, 1.20),
    "qwen3.5-plus":       (0.20, 1.20),
    "qwen3.6-plus":       (0.50, 3.00),
    "deepseek-v4-flash":  (0.22, 0.66),
    "deepseek-v4-pro":    (0.66, 1.98),
    # Free while OpenCode is running them. Priced at zero, flagged in the output, because
    # "free for a limited time" is not a rate you should build a run plan on.
    "big-pickle":                     (0.0, 0.0),
    "mimo-v2.5-free":                 (0.0, 0.0),
    "ling-3.0-flash-fin-free":        (0.0, 0.0),
    "nemotron-3-ultra-free":          (0.0, 0.0),
    "nemotron-3.5-lightning-free":    (0.0, 0.0),
    "laguna-s-2.1-free":              (0.0, 0.0),
}
FREE = {m for m, (i, o) in PRICES.items() if i == 0 and o == 0}


def bench_tasks(name):
    """Task count for a chat-lane bench. yaml is not imported: the loader lives in the
    container and this has to run from a bare clone, so the count is read by hand."""
    path = BENCHES / f"{name}.yaml"
    if not path.exists():
        raise SystemExit(f"no bench at {path}")
    tasks, lane = 0, "chat"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("lane:"):
            lane = line.split(":", 1)[1].strip().strip("\"'")
        if line.startswith("  - id:"):
            tasks += 1
    return tasks, lane


def cost(model, cases_per_variant, variants, reasoning):
    pin, pout = PRICES[model]
    tin = tout = 0
    for v in variants:
        m = MEASURED[v]
        tin += cases_per_variant * m["in"]
        tout += cases_per_variant * m["out"] * reasoning
    return (tin / 1e6) * pin + (tout / 1e6) * pout, tin, tout


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bench", nargs="?", help="bench name, or use --all")
    ap.add_argument("--all", action="store_true", help="every chat-lane bench")
    ap.add_argument("--repeats", type=int, default=31,
                    help="the power calculation from run 25 asked for 31 (default)")
    ap.add_argument("--reasoning", type=float, default=1.0,
                    help="multiplier on output tokens; 1.0 is the optimistic floor")
    ap.add_argument("--budget", type=float, default=None, help="flag models over this, USD")
    ap.add_argument("--variants", nargs="*", default=["none", "skill:omarchy"])
    args = ap.parse_args()

    if args.all:
        names = sorted(p.stem for p in BENCHES.glob("*.yaml"))
    elif args.bench:
        names = [args.bench]
    else:
        raise SystemExit("name a bench or pass --all")

    total_tasks = 0
    for n in names:
        tasks, lane = bench_tasks(n)
        if lane != "chat":
            continue
        total_tasks += tasks
        if not args.all:
            print(f"{n}: {tasks} tasks, {args.repeats} repeats, "
                  f"{len(args.variants)} variants "
                  f"= {tasks * args.repeats * len(args.variants)} cases")

    if args.all:
        print(f"all chat-lane benches: {total_tasks} tasks, {args.repeats} repeats, "
              f"{len(args.variants)} variants "
              f"= {total_tasks * args.repeats * len(args.variants)} cases")

    per_variant = total_tasks * args.repeats
    print(f"\noutput multiplier {args.reasoning}x  "
          f"(1.0 is the optimistic floor; reasoning models emit far more)\n")
    print(f"  {'model':<28} {'USD':>8}  {'in':>10} {'out':>10}")
    rows = []
    for m in PRICES:
        usd, tin, tout = cost(m, per_variant, args.variants, args.reasoning)
        rows.append((usd, m, tin, tout))
    for usd, m, tin, tout in sorted(rows):
        flag = "  free for now" if m in FREE else ("  OVER BUDGET" if args.budget
                                                  and usd > args.budget else "")
        print(f"  {m:<28} {usd:>8.2f}  {tin:>10,} {tout:>10,}{flag}")


if __name__ == "__main__":
    main()
