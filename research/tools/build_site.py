#!/usr/bin/env python3
"""Generate the public GitHub Pages site from the corpus.

    python3 tools/build_site.py          # writes ../docs/ at the repo root

WHY A SEPARATE OUTPUT DIRECTORY. This writes the REPO ROOT `docs/`, which is where GitHub
Pages publishes from. It is NOT `research/docs/`, which build_db.py unlinks and regenerates
on every corpus build -- a site written there would survive exactly until the next rebuild.

WHAT THE SITE IS FOR. Not 456 fixes; anyone can publish a tips page. The two things that are
unusual here are per-record PROVENANCE (every fix says how much scrutiny it survived, and the
ones nobody checked say so) and the MEASUREMENT (a bench with controls saying whether the
skill actually helps). Both are rendered, not buried.

DESIGN SYSTEM. The Control Room theme, transcribed in `work.handoffs` at
`2026-08/22-controlroom-clean-room-extraction` from the original `style.css`. The mapping
that makes it fit: a category is a GROUP with an accent, a record is a CARD, and
`audit_status` drives the status LED -- so the board reads the corpus's honesty at a glance.

The source theme's fifth motif, the phosphor trace, is deliberately ABSENT. It was fitted
to audit coverage per category, but that sits at 97-100% across all twelve, so the line was
flat at the ceiling and carried no information a reader could act on. The per-group
audited/corrected/unchecked meters do that job with the same phosphor treatment and actually
vary. Do not reinstate a chart here without a series that moves.

Fonts are the fallback stacks only. The source handoff is explicit that the real families
(Space Grotesk, IBM Plex Mono) must be SELF-HOSTED woff2 rather than pulled from a CDN at
build time, because a network blip yields a silently unstyled page. Vendoring them is a
follow-up; the stacks degrade to system fonts meanwhile.
"""
import html
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # research/
REPO = ROOT.parent
OUT = REPO / "docs"
JSONL = ROOT / "data" / "problems.jsonl"
CATS = ROOT / "data" / "categories.json"

# Accents from the Control Room group palette. Twelve categories over five accents, grouped
# so related subject matter shares a colour rather than cycling arbitrarily.
ACCENT = {
    "omarchy-core": "#46e0c0", "omarchy-theming": "#46e0c0",
    "hyprland-config": "#7aa2ff", "display-monitors": "#7aa2ff", "wayland-compat": "#7aa2ff",
    "gpu-drivers": "#c8a2ff", "boot-kernel": "#c8a2ff", "power-suspend": "#c8a2ff",
    "pacman-aur": "#f2b34b", "apps-services": "#f2b34b",
    "network": "#e879a6", "audio-input": "#e879a6",
}
FALLBACK_ACCENT = "#61707f"      # the slate the Control Room gives an unregistered container

# audit_status -> LED state. This is the whole point of the board: the colour IS the
# provenance. `corrected` is amber because the record was wrong once and an auditor rewrote
# it; `unaudited` is red because nobody has checked it at all.
LED = {
    "ok":                ("h-healthy",  "AUDITED",   "Audited against its sources and confirmed accurate."),
    "corrected":         ("h-starting", "CORRECTED", "An auditor found the fix wrong or incomplete and rewrote it."),
    "unaudited":         ("h-down",     "UNAUDITED", "No auditor ever returned a verdict. Treat as a lead, not an instruction."),
    "gapfill-unaudited": ("h-down",     "UNAUDITED", "Harvested in a gap-fill pass and never reviewed."),
}

e = html.escape


def read_records():
    recs = [json.loads(l) for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs.sort(key=lambda r: (r["category"], r["slug"]))
    return recs


def heading(r):
    """A readable heading for a record.

    150 of 456 records carry no `title`. build_db.py falls back to the raw slug, which is
    fine in a developer-facing markdown dump and looks like a database leak on a public
    page. This prettifies the slug for DISPLAY only -- the corpus is untouched, and filling
    those titles in properly is a content task on the backlog, not something to fake here.
    """
    t = (r.get("title") or "").strip()
    if t:
        return t
    words = r["slug"].replace("-", " ").strip()
    return words[:1].upper() + words[1:] if words else r["slug"]


def md_lite(text):
    """Just enough markdown for the corpus's own conventions: fenced blocks and `code`.

    Deliberately NOT a markdown library. Everything is escaped FIRST and only then are the
    two constructs re-introduced, so a record can never inject markup -- the clean-room
    handoff flags raw interpolation into innerHTML as a real defect in the original.
    """
    out, in_fence = [], False
    for line in (text or "").split("\n"):
        if line.strip().startswith("```"):
            out.append("</code></pre>" if in_fence else '<pre><code>')
            in_fence = not in_fence
            continue
        out.append(e(line) if in_fence else _inline(e(line)))
    if in_fence:
        out.append("</code></pre>")
    return "\n".join(out)


def _inline(s):
    parts, tick = s.split("&#x27;") if False else [s], False
    s = parts[0]
    res, buf = [], ""
    for chunk in s.split("`"):
        res.append(f"<code>{chunk}</code>" if tick else chunk)
        tick = not tick
    return "".join(res)


def page(title, body, depth=0, subtitle=""):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(subtitle or title)}">
<link rel="stylesheet" href="{up}style.css">
</head><body>
<div class="scan"></div>
{body}
<footer>OPINIONATED OMARCHY &middot; CORPUS IS RESEARCH, NOT A WARRANTY &middot;
<a href="https://github.com/TechLuddite/opinionated-omarchy">SOURCE</a> &middot;
<a href="https://github.com/TechLuddite/opinionated-omarchy/blob/HEAD/LICENSE">MIT</a> &middot;
SET IN <a href="{up}fonts/DepartureMono-LICENSE.txt">DEPARTURE MONO</a></footer>
</body></html>
"""


def masthead(recs, depth=0):
    up = "../" * depth
    st = Counter(r.get("audit_status") for r in recs)
    srcs = {s for r in recs for s in (r.get("sources") or [])}
    vitals = [("RECORDS", len(recs), ""), ("AUDITED", st["ok"] + st["corrected"], ""),
              ("UNCHECKED", st["unaudited"] + st["gapfill-unaudited"], ""),
              ("SOURCES", len(srcs), "")]
    cells = "".join(
        f'<div class="vital"><div class="v-num">{v}<small>{u}</small></div>'
        f'<div class="v-lab">{k}</div></div>' for k, v, u in vitals)
    return f"""<header class="mast">
  <div class="brand"><a href="{up}index.html" class="wordmark">OPINIONATED OMARCHY</a>
    <div class="sub">TROUBLESHOOTING CORPUS</div></div>
  <div class="vitals">{cells}</div>
  <div class="mast-status"><i></i>LIVE</div>
</header>"""


def record_page(r, cats, corpus):
    acc = ACCENT.get(r["category"], FALLBACK_ACCENT)
    cls, label, meaning = LED.get(r.get("audit_status"), LED["unaudited"])
    note = r.get("audit_note")
    reconciled = r.get("cause_reconciled")
    src = "".join(f'<li><a href="{e(s)}" rel="nofollow noopener">{e(s)}</a></li>'
                  for s in (r.get("sources") or []))
    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in (r.get("applies_to") or []))

    prov = f'<div class="prov {cls}"><span class="led"></span><b>{label}</b> {e(meaning)}</div>'
    if note:
        # The disclaimer under an audit note is conditional on cause_reconciled in ask.py and
        # in the generated markdown. Keep it conditional here too, or the site tells a reader
        # the cause "was not rewritten" about one that was.
        if r.get("audit_status") == "corrected":
            tail = (f"The cause above was rewritten on {e(reconciled)} to match this note; "
                    "the fix was corrected by the audit itself." if reconciled else
                    "The cause above was not rewritten and may still contain the error "
                    "described. The fix below is the corrected version.")
        else:
            tail = ""
        prov += f'<div class="note"><div class="n-lab">AUDIT NOTE</div>{md_lite(note)}'
        prov += f'<div class="n-tail">{tail}</div></div>' if tail else "</div>"

    danger = (f'<div class="danger"><div class="n-lab">RISK</div>{md_lite(r["danger"])}</div>'
              if r.get("danger") else "")
    verify = (f'<section><h2>Verify</h2>{md_lite(r["verify"])}</section>'
              if r.get("verify") else "")

    body = f"""{masthead(corpus, depth=1)}
<main class="board" style="--gaccent:{acc}">
  <nav class="crumb"><a href="../index.html">BOARD</a> / <span>{e(cats.get(r['category'], r['category']))}</span></nav>
  <article class="detail">
    <div class="d-head">
      <span class="abbr">{e(r['category'])}</span>
      <span class="sev">{e(r.get('severity',''))}</span>
      <span class="sev">{e(r.get('frequency',''))}</span>
    </div>
    <h1>{e(heading(r))}</h1>
    <div class="tags">{tags}</div>
    {prov}
    {danger}
    <section><h2>Symptom</h2>{md_lite(r.get('symptom'))}</section>
    <section><h2>Cause</h2>{md_lite(r.get('cause'))}</section>
    <section><h2>Fix</h2>{md_lite(r.get('fix'))}</section>
    {verify}
    <section><h2>Sources</h2><ul class="src">{src}</ul></section>
    <div class="slug">{e(r['slug'])}</div>
  </article>
</main>"""
    return page(heading(r), body, depth=1,
                subtitle=(r.get("symptom") or "")[:150])


def index_page(recs, cats):
    by = defaultdict(list)
    for r in recs:
        by[r["category"]].append(r)
    groups = []
    for cat in sorted(by):
        acc = ACCENT.get(cat, FALLBACK_ACCENT)
        cards = []
        for r in by[cat]:
            cls, label, _ = LED.get(r.get("audit_status"), LED["unaudited"])
            cards.append(
                f'<a class="card {cls}" href="records/{e(r["slug"])}.html">'
                f'<div class="c-head"><span class="led"></span>'
                f'<span class="c-name">{e(heading(r))}</span></div>'
                f'<div class="c-meta"><span class="c-lab">{label}</span>'
                f'<span class="c-sev">{e(r.get("severity",""))}</span></div></a>')
        n = len(by[cat])
        ok = sum(1 for r in by[cat] if r.get("audit_status") == "ok")
        co = sum(1 for r in by[cat] if r.get("audit_status") == "corrected")
        un = n - ok - co
        meter = (f'<span class="meter" title="{ok} audited, {co} corrected, {un} unchecked">'
                 f'<span class="m-ok" style="width:{100*ok/n:.1f}%"></span>'
                 f'<span class="m-corr" style="width:{100*co/n:.1f}%"></span>'
                 f'<span class="m-un" style="width:{100*un/n:.1f}%"></span></span>')
        groups.append(
            f'<section class="group" style="--gaccent:{acc}">'
            f'<h2 class="g-head"><i></i>{e(cats.get(cat, cat))}'
            f'<span class="g-count">{n}</span>{meter}</h2>'
            f'<div class="grid">{"".join(cards)}</div></section>')

    st = Counter(r.get("audit_status") for r in recs)
    corrected_n = st["corrected"]
    gh = "https://github.com/TechLuddite/opinionated-omarchy"
    body = f"""{masthead(recs)}
<main class="board">
  <section class="intro">
    <p class="lede">Real Omarchy and Arch desktop problems with verified, copy-pasteable
    fixes. Every one of them carries a record of how much scrutiny it survived.</p>

    <p class="body">Omarchy is DHH's opinionated Arch + Hyprland distribution. It moves
    fast, and most of the advice you will find for it was written for Omarchy&nbsp;3 or for
    Hyprland before 0.55. That advice sends you to a git checkout that no longer exists,
    or to config syntax that was deprecated. Every record here was researched against primary
    sources, then <b>audited adversarially by a second pass</b> whose job was to find the
    command that does not exist, the path that moved, and the confident specific the source
    never supported. {corrected_n} of them failed that audit and were rewritten. The
    auditor's objection is published with the record.</p>

    <div class="legend">
      <span class="h-healthy"><i class="led"></i>AUDITED {st['ok']}</span>
      <span class="h-starting"><i class="led"></i>CORRECTED {st['corrected']}</span>
      <span class="h-down"><i class="led"></i>UNCHECKED {st['unaudited'] + st['gapfill-unaudited']}</span>
    </div>
    <p class="fine">A <b>corrected</b> record was wrong once: an auditor found the fix
    wrong or incomplete and rewrote it, and the objection is published with the record. An
    <b>unchecked</b> record was never reviewed by anyone and says so. <b>And
    <i>audited</i> means checked against its sources, not guaranteed true on your
    machine</b>: one clean record, exercised on a real VM, turned out to quote two
    .pacnew files that cannot occur on Omarchy&nbsp;4 at all. Nothing here is a warranty. Anything
    touching pacman, the bootloader, initramfs or partitions deserves a look at the cited
    source before it runs as root.</p>

    <h2 class="g-head" style="--gaccent:#7aa2ff"><i></i>How this was built<span
      class="g-count">READ MORE</span></h2>
    <div class="grid links">
      <a class="card" href="{gh}/blob/HEAD/research/README.md">
        <div class="c-head"><span class="c-name">The corpus, its schema and its trust model</span></div>
        <div class="c-meta"><span class="c-lab">RESEARCH/README</span></div></a>
      <a class="card" href="{gh}/blob/HEAD/skillbench/README.md">
        <div class="c-head"><span class="c-name">The bench that asks whether a skill actually helps</span></div>
        <div class="c-meta"><span class="c-lab">SKILLBENCH</span></div></a>
      <a class="card" href="{gh}/blob/HEAD/skillbench/MODELS.md">
        <div class="c-head"><span class="c-name">Which local models can drive an agent loop, and why most cannot</span></div>
        <div class="c-meta"><span class="c-lab">MODELS</span></div></a>
      <a class="card" href="{gh}/tree/HEAD/writeups">
        <div class="c-head"><span class="c-name">Post-mortems: defects found, and how they were caught</span></div>
        <div class="c-meta"><span class="c-lab">WRITEUPS</span></div></a>
      <a class="card" href="{gh}/blob/HEAD/JOURNAL.md">
        <div class="c-head"><span class="c-name">Every session so far, including the dead ends</span></div>
        <div class="c-meta"><span class="c-lab">JOURNAL</span></div></a>
      <a class="card" href="{gh}">
        <div class="c-head"><span class="c-name">Source, licence and how to rebuild all of this</span></div>
        <div class="c-meta"><span class="c-lab">GITHUB</span></div></a>
    </div>
  </section>
  <div class="searchbar">
    <input id="q" type="search" placeholder="SEARCH BY SYMPTOM, e.g. screen share is a black rectangle"
           autocomplete="off" spellcheck="false">
    <div id="qcount" class="qcount"></div>
  </div>
  <div id="results" class="grid hide"></div>
  <div id="groups">{''.join(groups)}</div>
</main>
<script src="search.js"></script>"""
    return page("Opinionated Omarchy troubleshooting corpus", body,
                subtitle=f"{len(recs)} verified Omarchy/Arch fixes, each labelled with "
                         "how much scrutiny it survived.")


def search_index(recs):
    """Compact: what a symptom search needs and nothing else. Read by search.js in the
    browser; the AGENT-side path is FTS5 over problems.db, which ranks instead of filtering."""
    return [{"s": r["slug"], "t": heading(r), "c": r["category"],
             "a": r.get("audit_status"), "y": (r.get("symptom") or "")[:220],
             "g": " ".join(r.get("applies_to") or [])} for r in recs]


def main():
    recs = read_records()
    cats = json.loads(CATS.read_text(encoding="utf-8")) if CATS.exists() else {}
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "records").mkdir(parents=True)

    w = lambda p, s: p.write_text(s, encoding="utf-8", newline="\n")
    w(OUT / "index.html", index_page(recs, cats))
    w(OUT / "style.css", STYLE)
    w(OUT / "search.js", SEARCH_JS)
    w(OUT / "search.json", json.dumps(search_index(recs), ensure_ascii=False, separators=(",", ":")))
    w(OUT / ".nojekyll", "")          # serve records/ verbatim; no Jekyll processing

    # OFL clause 2: every copy must carry the copyright notice and the licence, so the
    # licence ships WITH the font rather than only living in the repo.
    fonts = OUT / "fonts"
    fonts.mkdir()
    src = ROOT / "assets" / "fonts"
    for f in ("DepartureMono-Regular.woff2", "DepartureMono-LICENSE.txt"):
        shutil.copy2(src / f, fonts / f)
    for r in recs:
        w(OUT / "records" / f"{r['slug']}.html", record_page(r, cats, recs))

    kb = sum(f.stat().st_size for f in OUT.rglob("*")) / 1024
    print(f"built {OUT.relative_to(REPO)}: {len(recs)} records, {kb:.0f} KB total")
    print(f"  search.json {(OUT/'search.json').stat().st_size/1024:.0f} KB")


STYLE = r"""/* Departure Mono -- SIL OFL 1.1, (c) 2022-2024 Helena Zhang. Licence ships at
   fonts/DepartureMono-LICENSE.txt, as OFL clause 2 requires. Self-hosted on purpose:
   a CDN fetch that fails yields a silently unstyled page. */
@font-face{
  font-family:'Departure Mono';
  src:url('fonts/DepartureMono-Regular.woff2') format('woff2');
  font-weight:400; font-style:normal; font-display:swap;
}
:root{
  --bg:#0a0e13; --panel:#10161f; --panel-2:#0c1119; --line:#1b2531; --line-2:#26374a;
  --ink:#d2dcea; --dim:#8996a6; --muted:#6b7c8e; --faint:#516072;
  --signal:#46e0c0; --signal-soft:rgba(70,224,192,.14);
  --warn:#f2b34b; --alert:#ff5d73; --gaccent:var(--signal);
  --mono:'IBM Plex Mono',ui-monospace,'SF Mono','Cascadia Mono','JetBrains Mono',
         'DejaVu Sans Mono','Liberation Mono',Menlo,Consolas,monospace;
  --disp:'Space Grotesk',ui-sans-serif,system-ui,'Segoe UI',Roboto,sans-serif;
  --body:ui-sans-serif,system-ui,'Segoe UI',Roboto,sans-serif;
  /* The CRT face carries CHROME only -- labels, wordmark, group headings. Anything a
     reader must actually parse (readouts, code, sources) stays on --mono, which is
     legible at these sizes on all three platforms and costs no third party. */
  --crt:'Departure Mono',var(--mono);
}
/* A pixel font must not be smoothed into mush, and Departure Mono is designed on an 11px
   grid -- its own README: "For pixel-perfect results, set the font size to increments of
   11px." Every rule below therefore sits at 11px (22px for the wordmark). The transcribed
   spec's 8.5-10px labels were both OFF-GRID and genuinely too small to read; snapping to
   the grid fixes legibility and crispness with one change. Do not reintroduce 8/9/10px
   here -- it will look soft as well as tiny. */
.crt,.wordmark,.sub,.v-lab,.mast-status,.g-head,.c-lab,.c-sev,.sev,.n-lab,.crumb,
footer,.tag,.slug,.qcount,.abbr,.legend{
  font-family:var(--crt);
  -webkit-font-smoothing:none; -moz-osx-font-smoothing:unset; font-smooth:never;
}
*{box-sizing:border-box}
body{margin:0;background:
  radial-gradient(1200px 600px at 80% -10%,#0e1620 0%,transparent 60%),
  radial-gradient(900px 500px at -10% 0%,#0d141d 0%,transparent 55%),
  var(--bg);
  color:var(--ink);font:14px/1.4 var(--body);-webkit-font-smoothing:antialiased;
  min-height:100vh}
/* Motif 1: scanline + vignette. 1% white at one line in three reads as texture, not stripes. */
.scan{position:fixed;inset:0;pointer-events:none;z-index:1;
  background:repeating-linear-gradient(0deg,rgba(255,255,255,.010) 0 1px,transparent 1px 3px);
  mix-blend-mode:overlay;opacity:.5}
.scan::after{content:"";position:absolute;inset:0;box-shadow:inset 0 0 260px rgba(0,0,0,.55)}
a{color:inherit;text-decoration:none}

.mast{position:sticky;top:0;z-index:5;display:grid;grid-template-columns:auto 1fr auto;
  gap:20px;align-items:center;padding:12px 22px;border-bottom:1px solid var(--line);
  background:rgba(10,14,19,.82);backdrop-filter:blur(8px)}
.wordmark{font:22px/1 var(--crt);letter-spacing:.20em;color:var(--ink)}
.sub{font:11px/1.4 var(--crt);letter-spacing:.40em;color:var(--signal)}
.vitals{display:flex;gap:26px;justify-content:center}
.v-num{font:600 19px/1 var(--mono);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.v-num small{font:11px var(--mono);color:var(--dim);margin-left:2px}
.v-lab{font:11px var(--crt);letter-spacing:.22em;color:var(--muted);margin-top:4px}
.meter{display:flex;height:3px;border-radius:2px;overflow:hidden;flex:0 0 84px;
  background:var(--line)}
.meter span{display:block;height:100%}
.m-ok{background:var(--signal);box-shadow:0 0 6px rgba(70,224,192,.7)}
.m-corr{background:var(--warn)}
.m-un{background:var(--alert)}
.mast-status{display:flex;align-items:center;gap:7px;font:11px var(--crt);
  letter-spacing:.24em;color:var(--signal)}
.mast-status i{width:8px;height:8px;border-radius:50%;background:var(--signal);
  box-shadow:0 0 7px rgba(70,224,192,.8);animation:pulse 2.4s infinite}
@keyframes pulse{50%{opacity:.35}}

.board{position:relative;z-index:2;max-width:1500px;margin:0 auto;padding:20px 22px 60px}
.intro{max-width:720px;margin:14px 0 22px}
.lede{font:16px/1.55 var(--body);color:var(--ink);margin:0 0 14px}
.fine{font:12px/1.6 var(--body);color:var(--dim);margin:12px 0 0}
.intro .body{font:13.5px/1.65 var(--body);color:var(--dim);margin:0 0 14px}
.intro .body b{color:var(--ink);font-weight:600}
/* The link grid wants the full board width; the PROSE does not. A 1440px line is roughly
   200 characters, which is unreadable for the same reason 8px type was. Constrain the text
   blocks to a reading measure and let only the cards span. */
.intro{max-width:none}
.intro .lede,.intro .body,.intro .fine,.intro .legend{max-width:78ch}
.links{margin-bottom:6px}
.links .card{min-height:0}
.links .c-name{font-size:12.5px}
.links .c-meta{margin-top:8px}
.legend{display:flex;gap:18px;flex-wrap:wrap;font:11px var(--crt);letter-spacing:.14em;
  color:var(--muted);margin:10px 0}
.legend span{display:flex;align-items:center;gap:6px}

.searchbar{display:flex;align-items:center;gap:12px;margin:8px 0 18px}
#q{flex:1;background:var(--panel-2);border:1px solid var(--line);border-radius:8px;
  padding:11px 13px;color:var(--ink);font:12px var(--mono);letter-spacing:.02em}
#q::placeholder{color:var(--faint)}
#q:focus{outline:none;border-color:var(--line-2);box-shadow:0 0 0 3px rgba(70,224,192,.10)}
.qcount{font:11px var(--crt);letter-spacing:.14em;color:var(--muted);white-space:nowrap}

.group{margin-top:26px}
.group:first-child{margin-top:8px}
.g-head{display:flex;align-items:center;gap:10px;margin:0 0 11px;
  font:11px var(--crt);letter-spacing:.24em;color:var(--dim);text-transform:uppercase}
.g-head i{width:9px;height:9px;transform:rotate(45deg);background:var(--gaccent)}
.g-head::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--line),transparent)}
.g-head .meter{margin-left:2px}
.g-count{font:11px var(--crt);letter-spacing:.14em;color:var(--muted)}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(224px,1fr));gap:11px}
.grid.hide{display:none}
.card{position:relative;display:block;border:1px solid var(--line);border-radius:8px;
  padding:11px 12px 10px;background:linear-gradient(var(--panel),var(--panel-2));
  transition:transform .15s,border-color .15s,box-shadow .15s}
.card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:var(--gaccent);opacity:.5;border-radius:8px 0 0 8px}
.card:hover{transform:translateY(-1px);border-color:var(--line-2);
  box-shadow:0 6px 20px rgba(0,0,0,.35)}
.c-head{display:flex;align-items:flex-start;gap:8px}
.c-name{font:500 13.5px/1.35 var(--disp);color:var(--ink)}
.c-meta{display:flex;justify-content:space-between;margin-top:9px;padding-top:8px;
  border-top:1px solid var(--line)}
.c-lab,.c-sev{font:11px var(--crt);letter-spacing:.14em;color:var(--muted)}

/* Motif 4: glowing LEDs. The colour IS the provenance. */
.led{flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:var(--muted);margin-top:4px}
.h-healthy .led,.h-healthy>.led{background:var(--signal);box-shadow:0 0 7px rgba(70,224,192,.8)}
.h-starting .led,.h-starting>.led{background:var(--warn);box-shadow:0 0 7px rgba(242,179,75,.8)}
.h-down .led,.h-down>.led{background:var(--alert);box-shadow:0 0 7px rgba(255,93,115,.8)}
.h-down.card{opacity:.72}

.crumb{font:11px var(--crt);letter-spacing:.22em;color:var(--muted);margin:6px 0 16px}
.crumb a{color:var(--signal)}
.detail{max-width:860px;border:1px solid var(--line);border-radius:8px;padding:22px 24px 26px;
  background:linear-gradient(var(--panel),var(--panel-2));position:relative}
.detail::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:var(--gaccent);opacity:.5;border-radius:8px 0 0 8px}
.d-head{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.abbr{font:11px var(--crt);letter-spacing:.06em;color:var(--gaccent);padding:3px 7px;
  border-radius:4px;border:1px solid color-mix(in srgb,var(--gaccent) 40%,var(--line));
  background:color-mix(in srgb,var(--gaccent) 8%,transparent)}
.sev{font:11px var(--crt);letter-spacing:.14em;color:var(--muted);text-transform:uppercase}
.detail h1{font:700 22px/1.3 var(--disp);margin:0 0 10px}
.detail h2{font:11px var(--crt);letter-spacing:.28em;color:var(--dim);
  text-transform:uppercase;margin:26px 0 8px}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.tag{font:11px var(--crt);letter-spacing:.1em;color:var(--muted);border:1px solid var(--line);
  border-radius:3px;padding:2px 6px}
.prov{border:1px solid var(--line);border-radius:6px;padding:11px 13px;margin:14px 0;
  display:flex;align-items:flex-start;gap:9px;font:12px var(--mono);letter-spacing:.06em;
  color:var(--dim);flex-wrap:wrap}
.prov b{letter-spacing:.16em;color:var(--ink)}
.note,.danger{border-left:2px solid var(--warn);background:rgba(242,179,75,.05);
  padding:10px 13px;margin:12px 0;border-radius:0 6px 6px 0;font:12px/1.6 var(--body);color:var(--dim)}
.danger{border-left-color:var(--alert);background:rgba(255,93,115,.06)}
.n-lab{font:11px var(--crt);letter-spacing:.22em;color:var(--muted);margin-bottom:5px}
.n-tail{margin-top:8px;font-style:italic;color:var(--muted)}
pre{background:#070b10;border:1px solid var(--line);border-radius:6px;padding:12px 14px;
  overflow-x:auto;margin:10px 0}
code{font:12px/1.55 var(--mono);color:var(--ink);font-variant-numeric:tabular-nums}
:not(pre)>code{background:rgba(70,224,192,.08);border:1px solid var(--line);border-radius:3px;
  padding:1px 5px;color:var(--signal)}
.src{margin:8px 0;padding-left:18px}
.src a{color:var(--signal);font:11px var(--mono);word-break:break-all}
.slug{margin-top:24px;padding-top:12px;border-top:1px solid var(--line);
  font:11px var(--crt);letter-spacing:.14em;color:var(--faint)}
footer{position:relative;z-index:2;text-align:center;padding:26px 20px 34px;
  border-top:1px solid var(--line);font:11px var(--crt);letter-spacing:.14em;color:var(--muted)}
footer a{color:var(--signal)}

@media(max-width:760px){
  .mast{position:static;grid-template-columns:1fr;gap:12px}
  .vitals{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
}
@media(max-width:420px){
  .vitals{grid-template-columns:repeat(2,1fr)}
  /* 22px x 19 characters at .20em overruns a phone. Tracking is spacing, not glyph size,
     so tightening it keeps the wordmark ON the 11px grid -- dropping to 11px would fit but
     would make the masthead read as a caption. */
  .wordmark{letter-spacing:.06em}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

SEARCH_JS = r"""// Client-side symptom search over search.json.
//
// This is the BROWSER half of the retrieval story and it is deliberately simple: substring
// scoring over ~100 KB. The AGENT half is FTS5 + bm25 over problems.db, which RANKS rather
// than filters -- and that difference is the one that matters at scale. Measured on this
// corpus, an unranked match for "boot" returns 94 of 456 records; ranking is what keeps a
// broad query useful as the corpus grows.
(function () {
  var q = document.getElementById('q'), out = document.getElementById('results'),
      groups = document.getElementById('groups'), count = document.getElementById('qcount'),
      DATA = null, LED = {ok:'h-healthy', corrected:'h-starting'};

  fetch('search.json').then(function (r) { return r.json(); }).then(function (d) {
    DATA = d; count.textContent = d.length + ' RECORDS';
  });

  function score(rec, terms) {
    var t = (rec.t || '').toLowerCase(), y = (rec.y || '').toLowerCase(),
        g = (rec.g || '').toLowerCase(), c = (rec.c || '').toLowerCase(), s = 0;
    for (var i = 0; i < terms.length; i++) {
      var w = terms[i], hit = 0;
      if (t.indexOf(w) >= 0) { s += 10; hit = 1; }
      if (y.indexOf(w) >= 0) { s += 4; hit = 1; }
      if (c.indexOf(w) >= 0) { s += 3; hit = 1; }
      if (g.indexOf(w) >= 0) { s += 2; hit = 1; }
      if (!hit) return 0;                 // every term must appear somewhere
    }
    return s;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function render() {
    var v = q.value.trim().toLowerCase();
    if (!DATA || v.length < 2) {
      out.className = 'grid hide'; groups.style.display = '';
      count.textContent = DATA ? DATA.length + ' RECORDS' : ''; return;
    }
    var terms = v.split(/\s+/), hits = [];
    for (var i = 0; i < DATA.length; i++) {
      var s = score(DATA[i], terms);
      if (s > 0) hits.push([s, DATA[i]]);
    }
    hits.sort(function (a, b) { return b[0] - a[0]; });
    hits = hits.slice(0, 60);
    out.innerHTML = hits.map(function (h) {
      var r = h[1], cls = LED[r.a] || 'h-down';
      return '<a class="card ' + cls + '" href="records/' + esc(r.s) + '.html">' +
             '<div class="c-head"><span class="led"></span>' +
             '<span class="c-name">' + esc(r.t) + '</span></div>' +
             '<div class="c-meta"><span class="c-lab">' + esc(r.c) + '</span>' +
             '<span class="c-sev">' + esc((r.a || '').toUpperCase()) + '</span></div></a>';
    }).join('');
    out.className = 'grid';
    groups.style.display = 'none';
    count.textContent = hits.length + (hits.length === 60 ? '+ MATCHES' : ' MATCHES');
  }

  q.addEventListener('input', render);
})();
"""

if __name__ == "__main__":
    main()
