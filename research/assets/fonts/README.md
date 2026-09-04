# Vendored fonts

Two faces, with one job each.

## DepartureMono-Regular.woff2: 22 KB, SIL Open Font License 1.1

Copyright 2022–2024 Helena Zhang (helenazhang.com).
Upstream: <https://github.com/rektdeckard/departure-mono> (v1.500)

**Committed rather than fetched.** The Control Room handoff is explicit that pulling
webfonts from a CDN at build time yields a *silently unstyled* page when the network
blips. The original Dockerfile curled five woff2 files with `|| true` on each. 22 KB in
git removes that failure mode and every runtime third party at once.

**OFL obligations, and they are met here:** clause 2 requires that each copy carries the
copyright notice and the licence, so `DepartureMono-LICENSE.txt` sits beside the font and
`build_site.py` copies **both** into the published site. No Reserved Font Name is declared,
so redistributing the unmodified file needs nothing further. Do not rename the font file
and do not modify the glyphs without re-reading clause 3.

Note the upstream repository's GitHub metadata reports **MIT**, which is wrong; the
bundled `LICENSE` is OFL 1.1 and that is the one that governs.

## OmarchyFont.woff2, 2.4 KB, MIT

Copyright 2026 Mark Cuda. Upstream: <https://github.com/markcuda/Omarchy-Font>

The Omarchy wordmark as a real typeface. It carries **the wordmark and the group
headings**: short, all-caps, letter-spaced runs where the letterforms are the point.

Where it stops was found by rendering rather than assumed, and two of the limits were
found by trying them and reverting. It is a block-built **display** face and it is
**proportional**. At 11px the letterforms close up, lowercase suffers, and a path like
`~/.config/hypr` loses its shape. A record `h1` was set in it at 30px and put back: a
twelve-word sentence in a display face makes the one line that tells a reader whether they
are on the right page the hardest line on the page to scan. The section labels
(`SYMPTOM`, `CAUSE`, `FIX`) were tried at 16px and put back too, because at low contrast
the block-built forms muddy at that size. And the instrument look depends on every number
being monospaced with tabular figures, which a proportional face cannot provide at any
size.

It is also the one rule that must **not** inherit the smoothing-disabled block below.
That exists for Departure Mono's pixel grid; applying it to block-built curves aliases
them.

## Why the chrome stays on Departure Mono

Departure Mono is a **pixel** face and keeps the **micro-chrome**: status chips, section
labels, tags, the crumb, the footer. Everything else, readouts and code and all the prose,
is on the system `ui-monospace` stack, which is good on all three platforms and costs
nothing. Vendoring a third family for that would add licensing surface to no benefit.

That list is shorter than it was. The group headings moved to the Omarchy face when the
type sizes went up, and the reason is the grid below: a heading that needs to grow cannot
grow on `--crt`, because the next step up from 11px is 22px.

**Departure Mono is designed on an 11px grid, and this is not optional.** Its own README
says: *"For pixel-perfect results, set the font size to increments of 11px."* So every rule
using `--crt` is **11px**. Nothing else. That constraint is exactly why `--crt` is now
confined to labels that are meant to be small: they are the only text the floor does not
fight.

That single rule fixed two problems at once. The transcribed Control Room spec uses 8.5px
and 9.5px micro-labels, which were *both* off-grid (so they rendered soft) **and simply
too small to read**, which the operator flagged on seeing the first build. Snapping to the
grid made them crisp and legible in one change.

**Do not reintroduce 8, 9, 10 or 12px on a `--crt` rule.** It will look mushy as well as
tiny, and the mushiness is the harder of the two to diagnose because it reads as a
rendering problem rather than a CSS one.

Tracking is exempt: `letter-spacing` is spacing between glyphs, not glyph size, so it can
be tuned freely. That is how the wordmark fits a 400px viewport. At `≤420px` its tracking
drops from `.12em` to `.02em` while the size stays 26px. The wordmark is on the Omarchy
face rather than `--crt`, so the 11px grid does not bind it; the tracking trick is about
width, not the grid.
