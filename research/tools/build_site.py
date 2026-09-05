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

Type is TWO vendored faces and one system stack, and nothing else. The source handoff is
explicit that a real family must be SELF-HOSTED woff2 rather than pulled from a CDN at build
time, because a network blip yields a silently unstyled page. Omarchy Font and Departure
Mono are vendored and shipped. Space Grotesk and IBM Plex Mono used to be NAMED at the head
of two stacks without ever being shipped, which is the worst of both: they rendered for a
visitor who happened to have them installed and fell back for everyone else, so the site's
type changed machine to machine. Both names are gone.
"""
import html
import json
import os
import re
import shutil
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

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


BULLET = re.compile(r"^\s*[-*]\s+")
# One or two digits only. An unanchored \d+ turns a line opening with a year, of which the
# corpus has several, into an ordered list.
NUMBERED = re.compile(r"^\s*\d{1,2}[.)]\s+")


def _block(lines):
    """One blank-line-delimited run of unfenced lines, as a paragraph or a list."""
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        return ""
    marker = BULLET if BULLET.match(lines[0]) else NUMBERED if NUMBERED.match(lines[0]) else None
    if marker is None:
        # A list often opens straight under its lead-in with no blank line ("You need at
        # minimum:" then the items). Split there rather than swallowing the items into the
        # paragraph, which is what made this worth fixing in the first place.
        for i, ln in enumerate(lines[1:], 1):
            if BULLET.match(ln) or NUMBERED.match(ln):
                return _block(lines[:i]) + _block(lines[i:])
        # Soft-wrapped prose joins with a space, which is what the browser already did to the
        # raw newlines this used to emit. Paragraphs are the only new break.
        return "<p>" + _inline(e(" ".join(ln.strip() for ln in lines))) + "</p>"
    items = []
    for ln in lines:
        if marker.match(ln):
            items.append(marker.sub("", ln).strip())
        elif items:
            items[-1] += " " + ln.strip()
        else:
            items.append(ln.strip())
    tag = "ul" if marker is BULLET else "ol"
    return f"<{tag}>" + "".join(f"<li>{_inline(e(i))}</li>" for i in items) + f"</{tag}>"


def md_lite(text):
    """Just enough markdown for the corpus's own conventions: fenced blocks, `code`,
    paragraphs and lists.

    Deliberately NOT a markdown library. Everything is escaped FIRST and only then are the
    constructs re-introduced, so a record can never inject markup -- the clean-room
    handoff flags raw interpolation into innerHTML as a real defect in the original.

    Paragraphs and lists are here because the corpus uses both and this dropped both. HTML
    collapses newlines, so emitting the raw lines ran every block together: 275 of 456
    records lose a paragraph break that way and 26 lose a bullet list, nearly all of them
    in `fix`, which is the field a reader came for.
    """
    out, buf = [], []
    in_fence = False

    def flush():
        if buf:
            block = _block(buf)
            buf.clear()
            if block:
                out.append(block)

    for line in (text or "").split("\n"):
        if line.strip().startswith("```"):
            if in_fence:
                out.append("</code></pre>")
            else:
                flush()
                out.append("<pre><code>")
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(e(line))
        elif line.strip():
            buf.append(line)
        else:
            flush()
    if in_fence:
        out.append("</code></pre>")
    flush()
    return "\n".join(out)


def _inline(s):
    parts, tick = s.split("&#x27;") if False else [s], False
    s = parts[0]
    res, buf = [], ""
    for chunk in s.split("`"):
        res.append(f"<code>{chunk}</code>" if tick else chunk)
        tick = not tick
    return "".join(res)


# The project docs rendered onto the site, so "how this was built" reads in place instead
# of bouncing a visitor to GitHub. Order is the order of the cards.
DOCS = [
    ("research-readme", "research/README.md",
     "The corpus, its schema and its trust model", "RESEARCH/README"),
    ("skillbench", "skillbench/README.md",
     "The bench that asks whether a skill actually helps", "SKILLBENCH"),
    ("models", "skillbench/MODELS.md",
     "Which local models can drive an agent loop, and why most cannot", "MODELS"),
    ("zen", "skillbench/ZEN.md",
     "What the cloud gateway serves, and six ways a run goes wrong", "ZEN"),
    ("writeups", "writeups/2026-09-01-merge-gapfill-silent-defects.md",
     "Post-mortems: defects found, and how they were caught", "WRITEUPS"),
    ("journal", "JOURNAL.md",
     "Every session so far, including the dead ends", "JOURNAL"),
]
DOC_BY_SOURCE = {src: slug for slug, src, _, _ in DOCS}
GH = "https://github.com/TechLuddite/opinionated-omarchy"

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_ITAL = re.compile(r"(?<![\*\w])\*([^*\n]+?)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def _href(target, source):
    """Resolve a markdown link target for a page rendered onto the site.

    A doc's own relative links point at repo paths. Those that name another rendered doc
    become local links; everything else goes to GitHub at HEAD, because a relative path
    into a repo means nothing to a browser sitting on a generated page.
    """
    if target.startswith(("http://", "https://", "#", "mailto:")):
        return target
    base = PurePosixPath(source).parent
    resolved = str(PurePosixPath(os.path.normpath(str(base / target))))
    if resolved in DOC_BY_SOURCE:
        return f"{DOC_BY_SOURCE[resolved]}.html"
    kind = "tree" if not PurePosixPath(resolved).suffix else "blob"
    return f"{GH}/{kind}/HEAD/{resolved}"


def _rich(text, source):
    """Inline markdown on ALREADY-ESCAPED text.

    Code spans are tokenised FIRST and nothing else is applied inside them, or a fenced
    `--force` would come back italicised and a path with asterisks would be mangled. Same
    escape-first rule as md_lite: no construct can introduce markup a record did not have.
    """
    # Code spans are lifted out to placeholders rather than emitted inline, so emphasis
    # can SPAN one. `**a `b` c**` is common in these docs and splitting on backticks first
    # left the asterisks stranded as literal text.
    spans, parts, tick = [], [], False
    for chunk in text.split("`"):
        if tick:
            parts.append(f"\x00{len(spans)}\x00")
            spans.append(chunk)
        else:
            parts.append(chunk)
        tick = not tick
    body = "".join(parts)
    body = _LINK.sub(
        lambda m: f'<a href="{e(_href(m.group(2), source))}">{m.group(1)}</a>', body)
    body = _BOLD.sub(r"<strong>\1</strong>", body)
    body = _ITAL.sub(r"<em>\1</em>", body)
    for n, code in enumerate(spans):
        body = body.replace(f"\x00{n}\x00", f"<code>{code}</code>")
    return body


def md_doc(text, source):
    """Enough markdown for this repo's own documents.

    Still not a markdown library, and still escape-first. It handles what these six files
    actually contain: headings, paragraphs, fenced code, inline code, bullet and numbered
    lists, pipe tables (64 rows across the docs), bold, italic, links and rules. Anything
    it does not know stays as escaped text rather than being dropped.
    """
    lines = (text or "").split("\n")
    out, i, in_fence = [], 0, False
    para, items, list_tag = [], [], None

    def flush_para():
        if para:
            out.append("<p>" + _rich(" ".join(para), source) + "</p>")
            para.clear()

    def flush_list():
        nonlocal list_tag
        if items:
            body = "".join(f"<li>{_rich(x, source)}</li>" for x in items)
            out.append(f"<{list_tag}>{body}</{list_tag}>")
            items.clear()
        list_tag = None

    def flush():
        flush_para()
        flush_list()

    while i < len(lines):
        raw = lines[i]
        line = e(raw)
        if raw.strip().startswith("```"):
            flush()
            in_fence = not in_fence
            out.append("<pre><code>" if in_fence else "</code></pre>")
            i += 1
            continue
        if in_fence:
            out.append(line)
            i += 1
            continue
        if not raw.strip():
            flush()
            i += 1
            continue
        if raw.strip() in ("---", "***", "___") and not para:
            flush()
            out.append("<hr>")
            i += 1
            continue
        if raw.lstrip().startswith("&gt;") or raw.lstrip().startswith(">"):
            flush()
            quote = []
            while i < len(lines) and (lines[i].lstrip().startswith(">") or
                                      (quote and lines[i].strip() and
                                       not lines[i].lstrip().startswith(("#", "-", "|")))):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + md_doc("\n".join(quote), source) + "</blockquote>")
            continue
        m = _HEAD.match(raw)
        if m:
            flush()
            # The page <h1> is the document title, which is stripped from the body, so
            # the doc's own ## is the top section level and maps straight to <h2>. Shifting
            # everything down one instead collapsed section headings to body size.
            lvl = min(max(len(m.group(1)), 2), 6)
            out.append(f"<h{lvl}>{_rich(e(m.group(2)), source)}</h{lvl}>")
            i += 1
            continue
        # A pipe table needs its separator row on the NEXT line, or a sentence containing
        # a pipe becomes a one-cell table.
        if _ROW.match(raw) and i + 1 < len(lines) and _SEP.match(lines[i + 1]):
            flush()
            head = [c.strip() for c in _ROW.match(raw).group(1).split("|")]
            i += 2
            rows = []
            while i < len(lines) and _ROW.match(lines[i]):
                rows.append([c.strip() for c in _ROW.match(lines[i]).group(1).split("|")])
                i += 1
            th = "".join(f"<th>{_rich(e(c), source)}</th>" for c in head)
            tb = "".join("<tr>" + "".join(f"<td>{_rich(e(c), source)}</td>" for c in r)
                         + "</tr>" for r in rows)
            out.append(f'<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>')
            continue
        if BULLET.match(raw) or NUMBERED.match(raw):
            flush_para()
            tag = "ul" if BULLET.match(raw) else "ol"
            if list_tag and list_tag != tag:
                flush_list()
            list_tag = tag
            marker = BULLET if tag == "ul" else NUMBERED
            items.append(e(marker.sub("", raw).strip()))
            i += 1
            continue
        if items:
            items[-1] += " " + line.strip()        # a wrapped list item
            i += 1
            continue
        para.append(line.strip())
        i += 1
    if in_fence:
        out.append("</code></pre>")
    flush()
    return "\n".join(x for x in out if x)


def doc_page(slug, source, title, recs):
    """One project document as a site page."""
    path = REPO / source
    text = path.read_text(encoding="utf-8")
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    if first.startswith("# "):
        # The H1 becomes the page title, so rendering it again puts the same sentence on
        # screen twice.
        heading = first[2:].strip()
        text = text.lstrip().split("\n", 1)[1] if "\n" in text.lstrip() else ""
    else:
        heading = title
    body = f"""{masthead(recs)}
<main class="board">
  <nav class="crumb"><a href="index.html">BOARD</a> / <span>{e(heading)}</span></nav>
  <article class="detail doc" style="--gaccent:#7aa2ff">
    <h1>{e(heading)}</h1>
    {md_doc(text, source)}
    <div class="slug">{e(source)} &middot; <a href="{GH}/blob/HEAD/{e(source)}">view on github</a></div>
  </article>
</main>"""
    return page(heading, body, depth=0, subtitle=title)


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


def dispute_url(r):
    """A pre-filled GitHub issue form for disputing one record.

    Issue FORMS prefill by field id (`?template=x.yml&record=...`), not by body text, so
    the ids here must track `.github/ISSUE_TEMPLATE/record-dispute.yml`. Every value is
    urlencoded: slugs are safe but `audit_status` and the title are not guaranteed to be.

    Carrying `status` matters as much as `record`. A dispute against a record that claimed
    `ok` is a different and more serious thing than one against a record that already said
    nobody had checked it, and asking the reporter to retype it invites a wrong answer.
    """
    q = urllib.parse.urlencode({
        "template": "record-dispute.yml",
        "title": f"[record] {heading(r)}",
        "record": r["slug"],
        "status": r.get("audit_status") or "unknown",
    })
    return f"https://github.com/TechLuddite/opinionated-omarchy/issues/new?{q}"


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
      <a class="dispute" href="{e(dispute_url(r))}" rel="nofollow noopener"
         title="Report that this record is wrong, dangerous or out of date">DISPUTE</a>
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
                f'<div class="c-head"><span class="c-name">{e(heading(r))}</span></div>'
                f'<div class="c-meta">'
                f'<span class="c-lab"><span class="led"></span>{label}</span>'
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
            # <details> rather than a JS toggle: keyboard accessible, survives with
            # scripting off, and the open/closed state is the element's own. Closed on
            # load, so the board opens as twelve headings instead of 456 cards.
            f'<details class="group" style="--gaccent:{acc}">'
            f'<summary class="g-head"><span class="caret"></span><i></i>{e(cats.get(cat, cat))}'
            f'<span class="g-count">{n}</span>{meter}</summary>'
            f'<div class="grid">{"".join(cards)}</div></details>')

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

    <h2 class="g-head intro-head" style="--gaccent:#7aa2ff"><i></i>How this was built<span
      class="g-count">READ MORE</span></h2>
    <div class="grid links">
      {"".join(f'''<a class="card" href="{slug}.html">
        <div class="c-head"><span class="c-name">{e(title)}</span></div>
        <div class="c-meta"><span class="c-lab">{e(label)}</span></div></a>'''
                for slug, _src, title, label in DOCS)}
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
    led_map = json.dumps({k: [v[0], v[1]] for k, v in LED.items()}, separators=(",", ":"))
    w(OUT / "search.js", SEARCH_JS.replace("__LED_MAP__", led_map))
    w(OUT / "search.json", json.dumps(search_index(recs), ensure_ascii=False, separators=(",", ":")))
    w(OUT / ".nojekyll", "")          # serve records/ verbatim; no Jekyll processing

    # OFL clause 2: every copy must carry the copyright notice and the licence, so the
    # licence ships WITH the font rather than only living in the repo.
    fonts = OUT / "fonts"
    fonts.mkdir()
    src = ROOT / "assets" / "fonts"
    for f in ("DepartureMono-Regular.woff2", "DepartureMono-LICENSE.txt",
              "OmarchyFont.woff2", "OmarchyFont-LICENSE.txt"):
        shutil.copy2(src / f, fonts / f)
    for slug, src, title, _label in DOCS:
        w(OUT / f"{slug}.html", doc_page(slug, src, title, recs))
    for r in recs:
        w(OUT / "records" / f"{r['slug']}.html", record_page(r, cats, recs))

    kb = sum(f.stat().st_size for f in OUT.rglob("*")) / 1024
    print(f"built {OUT.relative_to(REPO)}: {len(recs)} records, {kb:.0f} KB total")
    print(f"  search.json {(OUT/'search.json').stat().st_size/1024:.0f} KB")


STYLE = r"""/* Two vendored faces, both self-hosted on purpose: a CDN fetch that fails yields a
   silently unstyled page.

   Omarchy Font -- MIT, (c) 2026 Mark Cuda. The actual Omarchy wordmark as a typeface. It
   carries the wordmark and the group headings: short, all-caps, letter-spaced runs where
   the letterforms are the point. It is a block-built DISPLAY face and it is PROPORTIONAL,
   so it stays off everything else, and the boundary was found by rendering rather than
   assumed. At 11px the letterforms close up, lowercase suffers, and paths like
   ~/.config/hypr lose their shape. A record h1 was tried and reverted: a twelve-word
   sentence in a display face makes the line that tells a reader whether they are on the
   right page the hardest one to scan. And the instrument look depends on every number
   being monospaced with tabular figures, which a proportional face cannot give.

   Departure Mono -- SIL OFL 1.1, (c) 2022-2024 Helena Zhang. Keeps the micro-chrome: the
   recessive labels that are small on purpose, which is the one job its 11px grid suits.

   Both licences ship beside their font, and CI fails the build if either pair is broken. */
@font-face{
  font-family:'Omarchy';
  src:url('fonts/OmarchyFont.woff2') format('woff2');
  font-weight:400; font-style:normal; font-display:swap;
}
@font-face{
  font-family:'Departure Mono';
  src:url('fonts/DepartureMono-Regular.woff2') format('woff2');
  font-weight:400; font-style:normal; font-display:swap;
}
:root{
  --bg:#0a0e13; --panel:#10161f; --panel-2:#0c1119; --line:#1b2531; --line-2:#26374a;
  --ink:#d2dcea; --dim:#8996a6; --muted:#6b7c8e; --faint:#516072;
  --signal:#46e0c0; --signal-soft:rgba(70,224,192,.14);
  --alert:#ff5d73; --gaccent:var(--signal);
  /* CORRECTED was the source palette's amber (#f2b34b). Moved to an electric blue, and
     the swap improves both axes rather than trading one for the other: worst-case
     colour-vision-deficiency separation from the other two statuses goes 0.10 -> 0.28,
     and the closest normal-vision pair goes 96 -> 111 (amber sat too near --alert red).
     Contrast on --bg is 7.28:1. The palette's amber is retired rather than left declared
     and unused, which is the cruft the source handoff flagged in --raise and --mem. */
  --corrected:#00a6ff;
  /* ONE text face. This used to be three: --mono named 'IBM Plex Mono' and --disp named
     'Space Grotesk', neither of which is shipped, so both rendered only for a visitor who
     happened to have them installed and fell back to something else for everyone else.
     A site whose type changes machine to machine is not a design. Both names are gone and
     the system monospace stack, which is good on all three platforms and costs no third
     party, carries every readout, every label and all the prose. */
  --mono:ui-monospace,'SF Mono','Cascadia Mono','JetBrains Mono',
         'DejaVu Sans Mono','Liberation Mono',Menlo,Consolas,monospace;
  /* The brand face, on the two jobs where letterforms are the point: the wordmark, and
     the headings that structure a page. It is proportional and block-built, so it is kept
     off anything that must align in a column or be read at micro sizes. */
  --omarchy:'Omarchy',var(--mono);
  /* The CRT face is now micro-chrome only: the recessive labels that are deliberately
     small. It is designed on an 11px grid, which is exactly why it keeps the sizes that
     did not grow rather than being stretched off it. */
  --crt:'Departure Mono',var(--mono);
}
/* A pixel font must not be smoothed into mush, and Departure Mono is designed on an 11px
   grid -- its own README: "For pixel-perfect results, set the font size to increments of
   11px." Every rule below therefore sits at 11px. The transcribed spec's 8.5-10px labels
   were both OFF-GRID and genuinely too small to read; snapping to the grid fixes
   legibility and crispness with one change. Do not reintroduce 8/9/10px here -- it will
   look soft as well as tiny.

   This list is SHORTER than it was: the wordmark and the group headings moved to the
   Omarchy face, and both had to leave, because smoothing-disabled is a pixel-grid rule
   and applying it to a block-built face aliases its curves. What is left is the micro
   chrome, which is small ON PURPOSE and so is the one thing the 11px floor does not
   fight. Everything that grew is on --mono or --omarchy instead. */
.crt,.sub,.v-lab,.mast-status,.c-lab,.c-sev,.sev,.n-lab,.crumb,.detail h2,
footer,.tag,.slug,.qcount,.abbr,.legend{
  font-family:var(--crt);
  -webkit-font-smoothing:none; -moz-osx-font-smoothing:unset; font-smooth:never;
}
*{box-sizing:border-box}
body{margin:0;background:
  radial-gradient(1200px 600px at 80% -10%,#0e1620 0%,transparent 60%),
  radial-gradient(900px 500px at -10% 0%,#0d141d 0%,transparent 55%),
  var(--bg);
  color:var(--ink);font:16px/1.6 var(--mono);-webkit-font-smoothing:antialiased;
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
/* Not smoothing-disabled: that rule exists for Departure Mono's pixel grid, and applying
   it to block-built curves would alias them. 26px is chosen to sit with the rest of the
   masthead, not from a grid. */
.wordmark{font:26px/1 var(--omarchy);letter-spacing:.12em;color:var(--ink);
  -webkit-font-smoothing:antialiased}
.sub{font:11px/1.4 var(--crt);letter-spacing:.40em;color:var(--signal)}
.vitals{display:flex;gap:26px;justify-content:center}
.v-num{font:600 24px/1 var(--mono);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.v-num small{font:11px var(--mono);color:var(--dim);margin-left:2px}
.v-lab{font:11px var(--crt);letter-spacing:.22em;color:var(--muted);margin-top:4px}
.meter{display:flex;height:3px;border-radius:2px;overflow:hidden;flex:0 0 84px;
  background:var(--line)}
.meter span{display:block;height:100%}
.m-ok{background:var(--signal);box-shadow:0 0 6px rgba(70,224,192,.7)}
.m-corr{background:var(--corrected)}
.m-un{background:var(--alert)}
.mast-status{display:flex;align-items:center;gap:7px;font:11px var(--crt);
  letter-spacing:.24em;color:var(--signal)}
.mast-status i{width:8px;height:8px;border-radius:50%;background:var(--signal);
  box-shadow:0 0 7px rgba(70,224,192,.8);animation:pulse 2.4s infinite}
@keyframes pulse{50%{opacity:.35}}

.board{position:relative;z-index:2;max-width:1500px;margin:0 auto;padding:20px 22px 60px}
.intro{max-width:720px;margin:14px 0 22px}
.lede{font:20px/1.55 var(--mono);color:var(--ink);margin:0 0 16px}
.fine{font:14px/1.65 var(--mono);color:var(--dim);margin:14px 0 0}
.intro .body{font:15.5px/1.7 var(--mono);color:var(--dim);margin:0 0 14px}
.intro .body b{color:var(--ink);font-weight:600}
/* The link grid wants the full board width; the PROSE does not. A 1440px line is roughly
   200 characters, which is unreadable for the same reason 8px type was. Constrain the text
   blocks to a reading measure and let only the cards span. */
.intro{max-width:none}
.intro .lede,.intro .body,.intro .fine,.intro .legend{max-width:78ch}
/* The fine print ran straight into this heading. .g-head carries no top margin because in
   a .group the parent supplies it, and .intro is not a .group. */
.intro .intro-head{margin-top:36px}
.links{margin-bottom:6px}
.links .card{min-height:0}
.links .c-name{font-size:14px}
.links .c-meta{margin-top:8px}
.legend{display:flex;gap:18px;flex-wrap:wrap;font:11px var(--crt);letter-spacing:.14em;
  color:var(--muted);margin:10px 0}
.legend span{display:flex;align-items:center;gap:6px}

.searchbar{display:flex;align-items:center;gap:12px;margin:8px 0 18px}
#q{flex:1;background:var(--panel-2);border:1px solid var(--line);border-radius:8px;
  padding:12px 14px;color:var(--ink);font:14px var(--mono);letter-spacing:.02em}
#q::placeholder{color:var(--faint)}
#q:focus{outline:none;border-color:var(--line-2);box-shadow:0 0 0 3px rgba(70,224,192,.10)}
.qcount{font:11px var(--crt);letter-spacing:.14em;color:var(--muted);white-space:nowrap}

.group{margin-top:26px}
.group:first-child{margin-top:8px}
.group>summary::-webkit-details-marker{display:none}
.group>summary{list-style:none;cursor:pointer;user-select:none}
/* The caret is the only affordance that a heading is a control, so it must not be subtle.
   It is its OWN element rather than ::after: .g-head::after is already the fading rule
   line, and the more specific selector was quietly replacing it. */
.caret{order:-1;flex:0 0 auto;width:11px;color:var(--muted);font:11px var(--crt)}
.caret::after{content:"+"}
.group[open] .caret::after{content:"\2212"}
.group>summary:hover{color:var(--ink)}
.group>summary:hover .caret{color:var(--signal)}
.group>summary:focus-visible{outline:2px solid var(--signal);outline-offset:3px;border-radius:3px}
.g-head{display:flex;align-items:center;gap:10px;margin:0 0 12px;
  font:16px var(--omarchy);letter-spacing:.16em;color:var(--dim);text-transform:uppercase}
.g-head i{width:9px;height:9px;transform:rotate(45deg);background:var(--gaccent)}
.g-head::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--line),transparent)}
.g-head .meter{margin-left:2px}
.g-count{font:13px var(--mono);letter-spacing:.10em;color:var(--muted)}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(224px,1fr));gap:11px}
.grid.hide{display:none}
.card{position:relative;display:block;border:1px solid var(--line);border-radius:8px;
  padding:11px 12px 10px;background:linear-gradient(var(--panel),var(--panel-2));
  transition:transform .15s,border-color .15s,box-shadow .15s}
.card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:var(--gaccent);opacity:.5;border-radius:8px 0 0 8px}
.card:hover{transform:translateY(-1px);border-color:var(--line-2);
  box-shadow:0 6px 20px rgba(0,0,0,.35)}
.c-name{font:15px/1.45 var(--mono);color:var(--ink)}
.c-meta{display:flex;justify-content:space-between;margin-top:9px;padding-top:8px;
  border-top:1px solid var(--line)}
.c-lab,.c-sev{font:11px var(--crt);letter-spacing:.14em;color:var(--muted)}
/* The status dot sits with the status WORD rather than the title, so the colour and the
   label it encodes are read together. Either child can host it: .c-lab carries the status
   on a board card, .c-sev carries it on a search result. The global .led margin-top exists
   to seat a dot against the first line of a wrapped title and is wrong here. */
.c-meta>span{display:inline-flex;align-items:center;gap:6px}
.c-meta .led{margin-top:0}

/* Motif 4: glowing LEDs. The colour IS the provenance. */
.led{flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:var(--muted);margin-top:4px}
.h-healthy .led,.h-healthy>.led{background:var(--signal);box-shadow:0 0 7px rgba(70,224,192,.8)}
.h-starting .led,.h-starting>.led{background:var(--corrected);box-shadow:0 0 7px rgba(0,166,255,.8)}
.h-down .led,.h-down>.led{background:var(--alert);box-shadow:0 0 7px rgba(255,93,115,.8)}
.h-down.card{opacity:.72}

.crumb{font:11px var(--crt);letter-spacing:.22em;color:var(--muted);margin:6px 0 16px}
.crumb a{color:var(--signal)}
.detail{max-width:860px;border:1px solid var(--line);border-radius:8px;padding:22px 24px 26px;
  background:linear-gradient(var(--panel),var(--panel-2));position:relative}
.detail::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:var(--gaccent);opacity:.5;border-radius:8px 0 0 8px}
.d-head{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
/* Pushed to the right of the header row so it sits with the record's own metadata rather
   than competing with the title. Muted until hover: a corpus that invites correction should
   not look like it is asking for complaints. */
.dispute{margin-left:auto;font:11px var(--crt);letter-spacing:.14em;color:var(--muted);
  border:1px solid var(--line);border-radius:4px;padding:4px 9px;
  transition:color .15s,border-color .15s}
.dispute:hover{color:var(--alert);border-color:var(--alert)}
.dispute::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;
  background:currentColor;margin-right:7px;vertical-align:middle}
.abbr{font:11px var(--crt);letter-spacing:.06em;color:var(--gaccent);padding:3px 7px;
  border-radius:4px;border:1px solid color-mix(in srgb,var(--gaccent) 40%,var(--line));
  background:color-mix(in srgb,var(--gaccent) 8%,transparent)}
.sev{font:11px var(--crt);letter-spacing:.14em;color:var(--muted);text-transform:uppercase}
/* NOT the Omarchy face, and this was tried rather than assumed. It carries the wordmark
   and the group headings well, because those are short, all-caps and letter-spaced. A
   record title is a twelve-word sentence, and a proportional block-built display face
   makes the one line that tells a reader whether they are on the right page the hardest
   line on it to scan. */
.detail h1{font:600 26px/1.3 var(--mono);letter-spacing:-.01em;margin:0 0 12px}
.detail h2{font:11px var(--crt);letter-spacing:.28em;color:var(--dim);
  text-transform:uppercase;margin:28px 0 10px}
/* md_lite emits <p>, <ul> and <ol> now. Without these the blocks it separates would still
   read as one wall: the browser's default 1em on a <p> is too loose here, and a <ul> with
   no padding loses its markers off the left edge. .src is the sources list and keeps its
   own rule, so it is excluded rather than restyled. */
.detail section>p,.note>p,.danger>p{margin:0 0 9px}
.detail section>p:last-child,.note>p:last-child,.danger>p:last-child{margin-bottom:0}
.detail section>ul:not(.src),.detail section>ol,
.note>ul,.note>ol,.danger>ul,.danger>ol{margin:0 0 9px;padding-left:20px}
.detail section>ul:not(.src)>li,.detail section>ol>li,
.note li,.danger li{margin:3px 0}
/* Rendered project docs. Wider than a record because these carry tables and code, and
   the reading measure is set by the container rather than by the prose. */
.doc{max-width:980px}
.doc blockquote{border-left:2px solid var(--corrected);background:rgba(0,166,255,.05);
  padding:10px 14px;margin:14px 0;border-radius:0 6px 6px 0;color:var(--dim)}
.doc blockquote p:last-child{margin-bottom:0}
.doc h2{font:600 20px/1.35 var(--mono);color:var(--ink);letter-spacing:-.01em;
  margin:34px 0 10px;padding-top:14px;border-top:1px solid var(--line);
  text-transform:none}
.doc h3{font:600 16px/1.4 var(--mono);color:var(--ink);margin:24px 0 8px;text-transform:none}
.doc h4,.doc h5,.doc h6{font:600 15px/1.4 var(--mono);color:var(--dim);margin:18px 0 6px;
  text-transform:none}
.doc p{margin:0 0 12px}
.doc ul,.doc ol{margin:0 0 12px;padding-left:22px}
.doc li{margin:4px 0}
.doc strong{color:var(--ink)}
.doc em{color:var(--dim)}
.doc a{color:var(--signal);text-decoration:underline;text-underline-offset:2px}
.doc hr{border:0;border-top:1px solid var(--line);margin:22px 0}
.doc table{border-collapse:collapse;margin:14px 0;font-size:14px;display:block;
  overflow-x:auto;max-width:100%}
.doc th,.doc td{border:1px solid var(--line);padding:7px 11px;text-align:left;
  vertical-align:top}
.doc th{background:var(--panel-2);color:var(--dim);font-weight:600;white-space:nowrap}
.doc .slug a{color:var(--signal)}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.tag{font:11px var(--crt);letter-spacing:.1em;color:var(--muted);border:1px solid var(--line);
  border-radius:3px;padding:2px 6px}
.prov{border:1px solid var(--line);border-radius:6px;padding:11px 13px;margin:14px 0;
  display:flex;align-items:flex-start;gap:9px;font:14px var(--mono);letter-spacing:.04em;
  color:var(--dim);flex-wrap:wrap}
.prov b{letter-spacing:.16em;color:var(--ink)}
.note,.danger{border-left:2px solid var(--corrected);background:rgba(0,166,255,.05);
  padding:12px 14px;margin:14px 0;border-radius:0 6px 6px 0;font:14.5px/1.65 var(--mono);color:var(--dim)}
.danger{border-left-color:var(--alert);background:rgba(255,93,115,.06)}
.n-lab{font:11px var(--crt);letter-spacing:.22em;color:var(--muted);margin-bottom:5px}
.n-tail{margin-top:8px;font-style:italic;color:var(--muted)}
pre{background:#070b10;border:1px solid var(--line);border-radius:6px;padding:12px 14px;
  overflow-x:auto;margin:10px 0}
code{font:14px/1.55 var(--mono);color:var(--ink);font-variant-numeric:tabular-nums}
:not(pre)>code{background:rgba(70,224,192,.08);border:1px solid var(--line);border-radius:3px;
  padding:1px 5px;color:var(--signal)}
.src{margin:8px 0;padding-left:18px}
.src a{color:var(--signal);font:13px var(--mono);word-break:break-all}
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
  /* 26px x 19 characters overruns a phone. Tracking is spacing rather than glyph size, so
     tightening it keeps the wordmark at full size; shrinking it instead would make the
     masthead read as a caption. */
  .wordmark{letter-spacing:.02em}
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
      DATA = null,
      // Generated from the LED table in build_site.py, so the status a record shows in a
      // search result cannot drift from the one it shows on the board or its own page.
      // It used to carry the class only and uppercase the raw audit_status for the label,
      // which is why the same record read AUDITED on the board and OK here.
      LED = __LED_MAP__;

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
      var r = h[1], led = LED[r.a] || LED.unaudited;
      return '<a class="card ' + led[0] + '" href="records/' + esc(r.s) + '.html">' +
             '<div class="c-head"><span class="c-name">' + esc(r.t) + '</span></div>' +
             '<div class="c-meta"><span class="c-lab">' + esc(r.c) + '</span>' +
             '<span class="c-sev"><span class="led"></span>' +
             led[1] + '</span></div></a>';
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
