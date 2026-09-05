#!/usr/bin/env bash
# Provision the agentic lane's model API key onto the test VMs.
#
#   tools/install-agent-key.sh 1 2
#
# WHY THIS EXISTS SEPARATELY FROM THE RUNNER. app/runner.py handles no credential at all,
# on purpose: a token passed through a command string lands in the VM's process table, and
# a bench that ships credential-moving code is harder to audit than one that does not.
# machine.run uses a LOGIN shell, so a key exported from the VM's profile is already
# present by the time an agent runs, and `HOME=... cmd` changes only that command's
# environment, which is what lets the skill arms use a scratch HOME without losing auth.
#
# WHAT IT TOUCHES. Writes ~/.config/omarchy-bench-agent.env (0600) on each VM and sources
# it from ~/.bash_profile, NOT ~/.bashrc. Omarchy's .bashrc returns early on line 5 for
# non-interactive shells, which is why it exports OMARCHY_PATH above that line. Anything
# appended below it is invisible to `bash -lc`, which is how the runner reaches the VM. The key is read from skillbench/secrets/zen.env, which is gitignored,
# and is never echoed, never passed on a command line, and never written to this repo.
#
# THESE VMS ARE DISPOSABLE. NAT-only, no real data, resettable from a golden image in about
# a second. That is what makes putting a key on them acceptable at all. It is still a real
# credential: rotate it at https://opencode.ai/auth if a VM is ever given a routable
# address, and re-run this afterwards.
#
# RE-SAVE THE GOLDENS AFTERWARDS. A `golden-test-vm.sh reset` restores the disk as it was
# when saved, which is exactly how NOPASSWD sudo went missing on 2026-09-01 and how both
# bench keys vanished on 2026-09-02.
set -euo pipefail

cd "$(dirname "$0")/.."
KEYFILE=skillbench/secrets/zen.env
REMOTE_ENV='~/.config/omarchy-bench-agent.env'
SSH_KEY=skillbench/secrets/bench_ed25519
USER=techluddite

[[ -f $KEYFILE ]] || { echo "no key at $KEYFILE" >&2; exit 1; }
# shellcheck disable=SC1090
KEY=$(. "$KEYFILE"; printf '%s' "${OPENCODE_API_KEY:-}")
[[ -n $KEY ]] || { echo "no OPENCODE_API_KEY in $KEYFILE" >&2; exit 1; }

(($#)) || { echo "usage: $0 <vm-number>..." >&2; exit 1; }

for n in "$@"; do
  domain="opinionated-omarchy-test$n"
  ip=$(sudo virsh domifaddr "$domain" 2>/dev/null |
       awk '/ipv4/{split($4,a,"/"); print a[1]; exit}')
  [[ -n ${ip:-} ]] || { echo "$domain: no IP (running?)" >&2; continue; }

  # The key goes over stdin, never in argv: an ssh command line is visible in the process
  # table on BOTH machines while it runs.
  # Single-quoted so the VM receives this verbatim. NOT a login shell: writing a file
  # needs no profile, and the nested quoting a login shell required was what broke this
  # the first time, silently, under set -e.
  # A trailing newline is required: without one `read` hits EOF, returns non-zero, and
  # `set -eu` on the far side kills the remote shell before it writes anything. That
  # failed silently and exited 1 with no output.
  printf '%s\n' "$KEY" | ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$USER@$ip" '
    set -eu
    IFS= read -r k || true
    umask 077
    mkdir -p ~/.config
    printf "export OPENCODE_API_KEY=%s\n" "$k" > ~/.config/omarchy-bench-agent.env
    chmod 600 ~/.config/omarchy-bench-agent.env
    grep -q omarchy-bench-agent ~/.bash_profile 2>/dev/null ||
      echo ". ~/.config/omarchy-bench-agent.env" >> ~/.bash_profile
    sed -i /omarchy-bench-agent/d ~/.bashrc
  '
  # Confirm by LENGTH, never by value.
  got=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$USER@$ip" \
        'bash -lc "printf %s \"\${OPENCODE_API_KEY:-}\" | wc -c"')
  if [[ $got == "${#KEY}" ]]; then
    echo "$domain ($ip): key installed, $got chars, exported from a login shell"
  else
    echo "$domain ($ip): FAILED, login shell exports $got chars (expected ${#KEY})" >&2
  fi
done

cat <<'EOF'

Next:
  tools/golden-test-vm.sh save 1     # ONE VM PER INVOCATION; `save 1 2` silently ignores the 2
  tools/golden-test-vm.sh save 2
EOF
