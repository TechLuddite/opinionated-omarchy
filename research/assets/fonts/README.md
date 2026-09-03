# Vendored fonts

## DepartureMono-Regular.woff2 — 22 KB, SIL Open Font License 1.1

Copyright 2022–2024 Helena Zhang (helenazhang.com).
Upstream: <https://github.com/rektdeckard/departure-mono> (v1.500)

**Committed rather than fetched.** The Control Room handoff is explicit that pulling
webfonts from a CDN at build time yields a *silently unstyled* page when the network
blips — the original Dockerfile curled five woff2 files with `|| true` on each. 22 KB in
git removes that failure mode and every runtime third party at once.

**OFL obligations, and they are met here:** clause 2 requires that each copy carries the
copyright notice and the licence, so `DepartureMono-LICENSE.txt` sits beside the font and
`build_site.py` copies **both** into the published site. No Reserved Font Name is declared,
so redistributing the unmodified file needs nothing further. Do not rename the font file
and do not modify the glyphs without re-reading clause 3.

Note the upstream repository's GitHub metadata reports **MIT**, which is wrong — the
bundled `LICENSE` is OFL 1.1 and that is the one that governs.

## Why only one font is vendored

Departure Mono is a **pixel** face: it carries the CRT chrome (wordmark, micro-labels,
group headings) where letterforms are decoration. Readouts, code blocks and anything a
reader must actually parse stay on the system `ui-monospace` stack, which is good on all
three platforms and costs nothing. Vendoring a second family for that would double the
licensing surface to no benefit.

**Departure Mono is designed on an 11px grid, and this is not optional.** Its own README
says: *"For pixel-perfect results, set the font size to increments of 11px."* So every rule
using `--crt` is **11px**, and the wordmark is **22px**. Nothing else.

That single rule fixed two problems at once. The transcribed Control Room spec uses 8.5px
and 9.5px micro-labels, which were *both* off-grid — so they rendered soft — **and simply
too small to read**, which the operator flagged on seeing the first build. Snapping to the
grid made them crisp and legible in one change.

**Do not reintroduce 8, 9, 10 or 12px on a `--crt` rule.** It will look mushy as well as
tiny, and the mushiness is the harder of the two to diagnose because it reads as a
rendering problem rather than a CSS one.

Tracking is exempt: `letter-spacing` is spacing between glyphs, not glyph size, so it can
be tuned freely. That is how the wordmark fits a 400px viewport — at `≤420px` its tracking
drops from `.20em` to `.06em` while the size stays 22px and on-grid.
