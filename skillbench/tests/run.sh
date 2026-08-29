#!/usr/bin/env bash
# Run the unit tests against the built image, with the source and benches mounted :ro.
# pytest is not in the runtime image; it is installed into a throwaway container.
set -euo pipefail
cd "$(dirname "$0")/.."
bash tests/check_ui_js.sh

exec docker run --rm \
  -v "$PWD/app:/app/app:ro" \
  -v "$PWD/tests:/app/tests:ro" \
  -v "$PWD/benches:/benches:ro" \
  -v "$PWD/skills.yaml:/app/skills.yaml:ro" \
  -v "$PWD/../omarchy:/skills/omarchy:ro" \
  -v "$PWD/../diagnose-crash:/skills/diagnose-crash:ro" \
  -w /app --entrypoint sh opinionated-omarchy/skillbench \
  -c "pip install --quiet --disable-pip-version-check pytest >/dev/null && python -m pytest tests -q -p no:cacheprovider"
