#!/usr/bin/env python3
"""What can this Zen key actually reach, and what does each model return?

    python3 skillbench/tools/probe_zen.py snapshot -o /tmp/zen-a.json
    python3 skillbench/tools/probe_zen.py diff /tmp/zen-a.json /tmp/zen-b.json

The Ollama-side equivalent is probe_models.py. This exists for the same reason: a model
that cannot be driven and a model that scores badly look identical in a results column, so
establish the terrain BEFORE designing runs around it.

THREE THINGS IT CHECKS, because they are three different failures.

1. LISTED. GET /v1/models. Note this is a catalogue and not an entitlement: ids appear here
   that return 500 on use, and ids on OpenCode's own Go page do not appear here at all.
2. REACHABLE. One tiny completion. A disabled or unavailable model returns HTTP 500 with a
   bare "Internal server error", which is indistinguishable from a real outage, so this is
   worth recording per model rather than discovering mid-run.
3. ANSWERS. Whether `message.content` actually contains anything. Most of the reachable
   models are reasoning models that put their output in `message.reasoning` and leave
   `content` null or empty on a short budget. app/runner.py reads content and would score
   every one of them zero while recording the case as ok, which is a silent false negative
   of exactly the kind this bench keeps catching itself on.

COST. Deliberately small: max_tokens is tiny and every `-pro`, `-opus`, `-max`, `-ultra`
and `-terra` rung is skipped unless --include-expensive is passed. Note that max_tokens is
honoured inconsistently across models here, so treat the cap as advisory: `ling` stopped at
exactly 24, while `big-pickle` returned 257 against a request for 8.

The key is read from skillbench/secrets/zen.env, which is gitignored, and is never printed
or passed on a command line.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KEYFILE = REPO / "skillbench" / "secrets" / "zen.env"
BASE = "https://opencode.ai/zen/v1"
PROMPT = "Say hi"
# The endpoint 403s Python-urllib's DEFAULT User-Agent specifically. Any named agent is
# accepted, including this one, so the fix is to identify ourselves rather than to
# impersonate a browser. Same family as the Anubis block on wiki.archlinux.org noted in
# CLAUDE.md: the request is fine and the client string is what gets refused. httpx, which
# app/runner.py uses, sends its own UA and is NOT affected; verified 200 from the container.
USER_AGENT = "opinionated-omarchy-skillbench/1.0"
MAX_TOKENS = 8
# Rungs skipped by default. Not a quality judgement: these are the priced tiers, and a
# probe should never be the thing that spends the balance.
EXPENSIVE = ("-pro", "-opus", "-max", "-ultra", "-terra", "-sol")


def api_key():
    if not KEYFILE.exists():
        raise SystemExit(f"no key at {KEYFILE}. See the one-liner in the session notes.")
    for line in KEYFILE.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            if k.strip().endswith("API_KEY"):
                return v.strip()
    raise SystemExit(f"no *_API_KEY line in {KEYFILE}")


def call(path, key, body=None, timeout=60):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8") if body else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": USER_AGENT},
        method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:                        # timeout, DNS, TLS: data, not a crash
        return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}


def err_of(payload):
    e = payload.get("error")
    if isinstance(e, dict):
        return (e.get("message") or "")[:80]
    return (str(e) or "")[:80] if e else ""


def snapshot(include_expensive, only):
    key = api_key()
    status, payload = call("/models", key)
    if status != 200:
        raise SystemExit(f"GET /models failed: HTTP {status} {err_of(payload)}")
    listed = sorted(m["id"] for m in payload.get("data", []))

    targets = [m for m in listed
               if include_expensive or not any(m.endswith(s) for s in EXPENSIVE)]
    if only:
        targets = [m for m in targets if any(o in m for o in only)]

    probes = {}
    for mid in targets:
        st, pl = call("/chat/completions", key, {
            "model": mid, "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": PROMPT}]})
        rec = {"http": st, "error": err_of(pl)}
        if st == 200 and pl.get("choices"):
            msg = pl["choices"][0].get("message") or {}
            content = msg.get("content")
            rec["answers"] = bool(content and content.strip())
            rec["content"] = "null" if content is None else ("empty" if not content.strip()
                                                             else "text")
            rec["reasoning"] = bool(msg.get("reasoning"))
            rec["total_tokens"] = (pl.get("usage") or {}).get("total_tokens")
            # max_tokens is advisory here; record the overrun so the bench can budget.
            rec["over_budget"] = bool((rec["total_tokens"] or 0) > MAX_TOKENS * 4)
        print(f"  {mid:<34} {st:<5} {rec.get('content') or rec['error'][:44]}",
              file=sys.stderr)
        probes[mid] = rec

    return {"listed": listed, "probed": probes,
            "counts": {
                "listed": len(listed),
                "probed": len(probes),
                "reachable": sum(1 for r in probes.values() if r["http"] == 200),
                "answers": sum(1 for r in probes.values() if r.get("answers")),
            }}


def diff(a, b):
    A, B = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (a, b))
    la, lb = set(A["listed"]), set(B["listed"])
    print(f"listed:    {len(la)} -> {len(lb)}")
    for m in sorted(lb - la):
        print(f"  + {m}")
    for m in sorted(la - lb):
        print(f"  - {m}")
    if la == lb:
        print("  (identical)")

    print(f"\nreachable: {A['counts']['reachable']} -> {B['counts']['reachable']}")
    moved = 0
    for m in sorted(set(A["probed"]) | set(B["probed"])):
        ra, rb = A["probed"].get(m), B["probed"].get(m)
        sa = ra["http"] if ra else None
        sb = rb["http"] if rb else None
        if sa != sb:
            print(f"  ~ {m:<34} {sa} -> {sb}")
            moved += 1
    if not moved:
        print("  (no model changed reachability)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--include-expensive", action="store_true",
                   help="also probe -pro/-opus/-max/-ultra/-terra/-sol rungs; costs money")
    s.add_argument("--only", nargs="*", default=None,
                   help="substrings to restrict the probe to, e.g. --only glm kimi")
    d = sub.add_parser("diff")
    d.add_argument("a")
    d.add_argument("b")
    args = ap.parse_args()

    if args.cmd == "diff":
        return diff(args.a, args.b)

    snap = snapshot(args.include_expensive, args.only)
    Path(args.out).write_text(
        json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    c = snap["counts"]
    print(f"\nlisted {c['listed']}, probed {c['probed']}, "
          f"reachable {c['reachable']}, actually answered {c['answers']}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
