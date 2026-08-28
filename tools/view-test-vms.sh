#!/usr/bin/env bash
#
# Open a VNC window for each test VM.
#
#   tools/view-test-vms.sh          # both
#   tools/view-test-vms.sh 1        # just test1
#
# The VNC servers listen on 127.0.0.1 only, so these windows are the whole of
# the access path -- nothing on the LAN can reach them. The .vv files carry the
# VNC password so remote-viewer does not prompt; they are chmod 600 for that
# reason. Regenerate them with tools/make-test-vm.sh if the password changes.

set -euo pipefail
CONF_DIR="$HOME/.local/share/opinionated-omarchy"

for N in "${@:-1 2}"; do
  vv="$CONF_DIR/test$N.vv"
  [[ -f $vv ]] || { echo "no connection file at $vv" >&2; exit 1; }
  if ! sudo virsh domstate "opinionated-omarchy-test$N" 2>/dev/null | grep -q running; then
    echo "opinionated-omarchy-test$N is not running; starting it" >&2
    sudo virsh start "opinionated-omarchy-test$N" >/dev/null
  fi
  remote-viewer "$vv" >/dev/null 2>&1 &
  echo "opened viewer for opinionated-omarchy-test$N"
done
wait
