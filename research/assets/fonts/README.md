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

**Pixel fonts need integer sizes.** The original design uses 8.5px and 9.5px labels;
fractional sizes make a pixel font blur into mush, so every rule that switches to
Departure Mono rounds to a whole pixel. That is why the CRT sizes differ slightly from the
transcribed spec.
