#!/usr/bin/env python3
"""Probe the local Ollama for agentic-lane feasibility, model by model.

Three independent gates decide whether a model can be measured on the agentic lane,
and they fail in different ways. This reports the two that are cheap to check
statically; the third (does it actually drive the loop) only a bench run answers.

  1. TOOLS      -- `capabilities` must include "tools". Without it pi errors out
                   immediately: `does not support tools`, HTTP 400.
  2. VRAM       -- the weights plus a 32K KV cache must fit the card, or Ollama
                   spills to CPU and the case times out rather than failing.
  3. AGENTIC    -- declared tool support is NOT competence. Models that pass gate 1
                   still emit tool calls as prose, or never look outside $PWD.
                   Only `omarchy-agentic-root-config` distinguishes these.

Usage:  python3 skillbench/tools/probe_models.py [--json]
"""
import json, sys, urllib.request

BASE = "http://127.0.0.1:11434"


def api(path, payload=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def probe():
    out = []
    for m in sorted(api("/api/tags")["models"], key=lambda x: -x["size"]):
        name = m["name"]
        if "embed" in name:          # served for a different job entirely
            continue
        try:
            d = api("/api/show", {"model": name})
            caps = d.get("capabilities", []) or []
            info = d.get("model_info") or {}
            ctx = next((v for k, v in info.items() if k.endswith(".context_length")), None)
        except Exception as e:
            caps, ctx = [f"error: {e}"], None
        det = m.get("details") or {}
        out.append({
            "model": name,
            "gb": round(m["size"] / 1e9, 1),
            "params": det.get("parameter_size"),
            "quant": det.get("quantization_level"),
            "declared_ctx": ctx,
            "tools": "tools" in caps,
        })
    return out


def loaded():
    """What Ollama has resident right now -- the only honest source of real VRAM cost,
    since it reflects the server's actual context allocation rather than the model's max."""
    try:
        return {m["name"]: {"ctx": m.get("context_length"),
                            "vram_gb": round(m.get("size_vram", 0) / 1e9, 1)}
                for m in api("/api/ps").get("models", [])}
    except Exception:
        return {}


def main():
    rows, live = probe(), loaded()
    if "--json" in sys.argv:
        for r in rows:
            r.update(live.get(r["model"], {}))
        print(json.dumps(rows, indent=2))
        return
    print(f"{'model':26} {'size':>7} {'params':>8} {'quant':>8} {'max ctx':>9}  {'tools':<5} {'resident':>16}")
    print("-" * 88)
    for r in rows:
        l = live.get(r["model"])
        res = f"{l['vram_gb']}GB @ {l['ctx']}" if l else ""
        print(f"  {r['model']:24} {r['gb']:5.1f}GB {str(r['params']):>8} {str(r['quant']):>8} "
              f"{str(r['declared_ctx']):>9}  {'yes' if r['tools'] else 'NO':<5} {res:>16}")
    no = [r["model"] for r in rows if not r["tools"]]
    if no:
        print(f"\n  gate 1 FAILED (no tool support, cannot run the agentic lane): {', '.join(no)}")
    print("\n  Declared max ctx is the MODEL's ceiling, not what it gets. The server caps every")
    print("  model at OLLAMA_CONTEXT_LENGTH; check `systemctl show ollama -p Environment`.")


if __name__ == "__main__":
    main()
