#!/usr/bin/env bash
# Tests for the corpus tooling. Stdlib unittest only -- no pytest, no container:
# CLAUDE.md keeps this tooling dependency-free so it runs on a bare box, and a
# suite that needed anything installed would be the first thing to break that.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 -m unittest discover -s tests "$@"
