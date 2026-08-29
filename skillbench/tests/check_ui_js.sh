#!/usr/bin/env bash
# Syntax-check the UI's inline JavaScript.
#
# The script is one big string inside ui.py, so Python's own syntax check says nothing
# about it: a JS error there produces a page that serves 200, renders its static chrome,
# and populates nothing. That failure looks like a backend problem and is not one.
# This caught a real `const` redeclaration during the build.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY' > /tmp/skillbench-ui.js
import re, sys
sys.path.insert(0, ".")
from app import ui
print(ui.JS)
PY
node --check /tmp/skillbench-ui.js && echo "UI JavaScript OK"
