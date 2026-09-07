#!/usr/bin/env python3
"""List Omarchy issues worth harvesting, from the tracker rather than the web.

    python3 tools/issue_candidates.py --since 2026-08-14 --out raw/issue-candidates.json
    python3 tools/issue_candidates.py --since 2026-08-14 --min-comments 2 --open-min-comments 4

Option O4 from the 2026-09-06 session. Six corpus records cited GitHub issues that did not
support them, and thirty-seven of thirty-seven `ok` records checked against Omarchy 4
were wrong, so the next records come from the tracker itself: an issue whose thread
holds a fix a maintainer or a second reporter confirmed. This script only selects; the
reading is done by the harvesters (`tools/issue-harvest-brief.md`).

Needs an authenticated `gh`. The repository moved from basecamp/omarchy to
omacom/omarchy; GitHub's search API does not follow the redirect, so the new name is
used here and the old one still works for `gh issue view`.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = "omacom/omarchy"


def search(query, limit=300):
    """Every issue matching a GitHub search query, newest first, up to `limit`."""
    out, page = [], 1
    while len(out) < limit:
        url = ("search/issues?q=repo:" + REPO + "+" + query.replace(" ", "+")
               + "&sort=comments&order=desc&per_page=100&page=" + str(page))
        res = subprocess.run(["gh", "api", url], capture_output=True, text=True, check=True)
        items = json.loads(res.stdout)["items"]
        if not items:
            break
        for it in items:
            out.append({
                "number": it["number"],
                "title": it["title"],
                "state": it["state"],
                "labels": [l["name"] for l in it.get("labels", [])],
                "comments": it["comments"],
                "created_at": it["created_at"][:10],
                "closed_at": (it.get("closed_at") or "")[:10] or None,
                "url": it["html_url"],
            })
        page += 1
    return out[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-14", help="created on or after (Omarchy 4.0.0 shipped 2026-08-14)")
    ap.add_argument("--min-comments", type=int, default=2, help="closed issues need this many comments")
    ap.add_argument("--open-min-comments", type=int, default=4, help="open issues need this many comments")
    ap.add_argument("--open-limit", type=int, default=60, help="cap on open issues, most-discussed first")
    ap.add_argument("--out", default=None, help="write JSON here (default: print a summary only)")
    a = ap.parse_args()

    closed = search(f"is:issue is:closed created:>={a.since} comments:>={a.min_comments}")
    opened = search(f"is:issue is:open created:>={a.since} comments:>={a.open_min_comments}", a.open_limit)
    skip = {"enhancement", "question", "duplicate", "invalid", "wontfix"}
    keep = [c for c in closed + opened if not (skip & set(c["labels"]))]
    keep.sort(key=lambda c: (-c["comments"], c["number"]))
    print(f"closed>={a.min_comments} comments: {len(closed)}, open>={a.open_min_comments}: {len(opened)}, "
          f"after label filter: {len(keep)}")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"repo": REPO, "since": a.since, "candidates": keep}, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {len(keep)} candidates to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
