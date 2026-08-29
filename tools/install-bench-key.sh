#!/usr/bin/env bash
#
# Install the Skill Bench's dedicated SSH public key on a test VM.
#
#   tools/install-bench-key.sh 1 [2 ...]
#
# The agentic lane drives the VMs over ssh from inside a container, so the container
# needs a private key. It gets its OWN key, never the operator's ~/.ssh/id_ed25519:
# the container is unprivileged and local-only, but a key mounted into a container is
# a key that can leave with the image, and this one guards nothing but two disposable
# test VMs. Generated on first run if missing.

set -euo pipefail
cd "$(dirname "$0")/.."
KEY=skillbench/secrets/bench_ed25519
USER_NAME=${OMARCHY_TEST_USER:-techluddite}

(($# > 0)) || { echo "usage: install-bench-key.sh <number> [number ...]" >&2; exit 1; }

if [[ ! -f $KEY ]]; then
  mkdir -p "$(dirname "$KEY")"; chmod 700 "$(dirname "$KEY")"
  ssh-keygen -t ed25519 -N '' -C 'omarchy-skillbench agentic lane' -f "$KEY" >/dev/null
  echo "generated $KEY"
fi
chmod 600 "$KEY"
PUB=$(cat "$KEY.pub")

for N in "$@"; do
  IP=$(sudo virsh net-dhcp-leases default 2>/dev/null |
       awk -v n="opinionated-omarchy-test$N" '$0 ~ n {split($5,a,"/"); print a[1]; exit}')
  [[ -n $IP ]] || { echo "no DHCP lease for test$N -- is it running?" >&2; exit 1; }
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$USER_NAME@$IP" "
    mkdir -p ~/.ssh && chmod 700 ~/.ssh
    grep -qF '$PUB' ~/.ssh/authorized_keys 2>/dev/null || echo '$PUB' >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys"
  ssh -i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes "$USER_NAME@$IP" \
      'echo "  bench key OK on $(hostname)"'
done
