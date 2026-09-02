#!/usr/bin/env bash
#
# Make an Omarchy test VM usable as an agentic bench target.
#
#   tools/provision-bench-vm.sh 1 [2 ...]
#
# Idempotent: safe to re-run, and re-run after a rebuild. Four things get set up.
#
# 1. UNATTENDED CONSOLE. Autologin, and never lock, blank or suspend. A bench VM sits
#    on a screen being watched; a lock screen hides the very thing it is there to show.
#    That matters more than it sounds: Omarchy 4's lock is an ext-session-lock surface
#    owned by omarchy-shell, it exposes lock() but deliberately NO unlock(), and it
#    SURVIVES its client's death. Once locked, a headless machine cannot be unlocked --
#    only prevention works, which is what this does.
#
# 2. THE MIRROR. A long-lived tmux session named by SESSION, and a terminal on the VM's
#    own console attached to it READ-ONLY. The bench opens one tmux window per case over
#    ssh, so the console shows each agent run live while the runner captures the same
#    bytes. Read-only is deliberate: a watcher cannot type into a case and corrupt it.
#
# 3. pi -> OLLAMA. A models.json pointing at the host's Ollama across the VM bridge.
#    supportsDeveloperRole=false because Ollama rejects the `developer` role pi would
#    otherwise send to reasoning-capable models.
#
# 4. THE BENCH KEY. Nothing here installs it -- skillbench/secrets/bench_ed25519.pub is
#    put in place by tools/install-bench-key.sh, so this script needs no secret.

set -euo pipefail

SESSION=${SB_TMUX_SESSION:-bench}
OLLAMA_HOST=${SB_OLLAMA_HOST:-192.168.122.1}
# Every tool-capable model the host's Ollama serves, unless overridden.
#
# This used to be a hardcoded list of four, and that silently skewed comparisons. pi
# still RUNS a model that is missing from models.json -- it warns "not found for
# provider ollama. Using custom model id" and carries on -- but it then applies its own
# defaults rather than the entry here. So a benched model absent from this list is not
# configured the same as one present in it, and the difference never surfaces as an
# error. Deriving the list means adding a model to Ollama is enough; you only have to
# remember to RE-PROVISION, not to edit this file.
#
# Models without tool support are excluded on purpose: pi cannot drive them at all
# (HTTP 400 "does not support tools"), so listing them would only add dead entries.
default_models() {
  curl -fsS --max-time 10 "http://${OLLAMA_HOST}:11434/api/tags" 2>/dev/null | python3 -c '
import json,sys,urllib.request
try: tags=json.load(sys.stdin)["models"]
except Exception: sys.exit(1)
out=[]
for m in tags:
    n=m["name"]
    if "embed" in n: continue
    try:
        req=urllib.request.Request("http://'"${OLLAMA_HOST}"':11434/api/show",
            data=json.dumps({"model":n}).encode(),
            headers={"Content-Type":"application/json"})
        if "tools" in (json.load(urllib.request.urlopen(req,timeout=15)).get("capabilities") or []):
            out.append(n)
    except Exception: pass
print(",".join(sorted(out)))
' 2>/dev/null
}
MODELS=${SB_VM_MODELS:-$(default_models)}
MODELS=${MODELS:-qwen2.5:latest,qwen2.5-coder:14b,gpt-oss:20b,devstral-small-2:24b}
USER_NAME=${OMARCHY_TEST_USER:-techluddite}
PASSWORD=${OMARCHY_TEST_PASSWORD:-omarchytest}

(($# > 0)) || { echo "usage: provision-bench-vm.sh <number> [number ...]" >&2; exit 1; }

vm_ip() {
  local mac_name="opinionated-omarchy-test$1"
  sudo virsh net-dhcp-leases default 2>/dev/null |
    awk -v n="$mac_name" '$0 ~ n {split($5,a,"/"); print a[1]; exit}'
}

for N in "$@"; do
  VM="opinionated-omarchy-test$N"
  IP=$(vm_ip "$N")
  [[ -n $IP ]] || { echo "no DHCP lease for $VM -- is it running?" >&2; exit 1; }
  echo "== $VM ($IP) =="

  # The remote half runs as one script so a half-applied VM is not a state we can reach.
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$USER_NAME@$IP" \
      "SESSION=$SESSION OLLAMA_HOST=$OLLAMA_HOST MODELS='$MODELS' PASSWORD='$PASSWORD' bash -s" <<'REMOTE'
set -euo pipefail

# ---- 1. never lock, blank or suspend ---------------------------------------
omarchy-toggle-idle stay-awake >/dev/null
omarchy-toggle screensaver-off on

echo "$PASSWORD" | sudo -S -v 2>/dev/null       # cache sudo; heredocs below need stdin

# ---- 1a. passwordless sudo, without which the agentic lane cannot test root ---
# The bench drives this VM over ssh with no tty: seeds, post assertions and the
# agent itself all run through `bash -lc` with nothing on stdin to answer a
# password prompt. So WITHOUT this, the agentic lane can only ever exercise
# things reachable as an unprivileged user -- which is every ~/.config task it
# currently has, and a large part of why it is saturated. Every hard Omarchy
# trap (boot config, pacman, the packaged system tree) lives behind sudo.
#
# This is safe HERE and nowhere else: these VMs are disposable, NAT-only, carry
# no real data, and their password is committed in plain text in CLAUDE.md
# already. It does let a misbehaving agent break the machine -- which is what
# `tools/golden-test-vm.sh reset` is for. Never do this to a VM with a routable
# address.
# `id -un`, not $USER: $USER is set by login(1) and is frequently EMPTY in a
# non-interactive ssh shell, which would write a sudoers rule granting NOPASSWD
# to everyone parsed as a syntax error -- or worse, silently to the wrong name.
sudo tee /etc/sudoers.d/99-bench-nopasswd >/dev/null <<EOF
$(id -un) ALL=(ALL) NOPASSWD: ALL
EOF
sudo chmod 0440 /etc/sudoers.d/99-bench-nopasswd
sudo visudo -c -f /etc/sudoers.d/99-bench-nopasswd >/dev/null   # refuse to ship a broken sudoers

sudo tee /etc/sddm.conf.d/95-autologin.conf >/dev/null <<'EOF'
# Bench VM: log straight in, and log back in if the session ever exits.
# Session names a file in /usr/share/wayland-sessions/.
[Autologin]
User=techluddite
Session=hyprland-uwsm.desktop
Relogin=true
EOF

sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1

sudo mkdir -p /etc/systemd/logind.conf.d
sudo tee /etc/systemd/logind.conf.d/95-bench-no-idle.conf >/dev/null <<'EOF'
[Login]
IdleAction=ignore
IdleActionSec=0
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
EOF

# ---- 2. the mirror: tmux session + a read-only console viewer ---------------
# Both are user units so they come back after a reboot without a desktop autostart
# file, and so `systemctl --user status` says plainly whether the mirror is up.
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/bench-tmux.service <<EOF
[Unit]
Description=Long-lived tmux session the bench opens one window per case in
After=graphical-session.target

[Service]
Type=forking
# -A: attach-or-create, so a restart never duplicates the session.
ExecStart=/usr/bin/tmux new-session -d -A -s $SESSION -x 200 -y 50
ExecStop=/usr/bin/tmux kill-session -t $SESSION
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF

cat > ~/.config/systemd/user/bench-mirror.service <<EOF
[Unit]
Description=Console terminal mirroring the bench tmux session, read-only
After=bench-tmux.service graphical-session.target
Requires=bench-tmux.service

[Service]
# foot talks to the compositor directly; no hyprctl dispatch needed, which also
# sidesteps Hyprland 0.56's Lua dispatch syntax entirely.
Environment=WAYLAND_DISPLAY=wayland-1
# -r attaches READ-ONLY: a watcher can never type into a running case. It also means
# the bench must not use 'tmux send-keys' -- tmux refuses it while a read-only client
# is attached. Launching each case as its own window is the supported path.
ExecStart=/usr/bin/foot -T "bench mirror" -e /usr/bin/tmux attach -t $SESSION -r
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now bench-tmux.service >/dev/null 2>&1 || true
systemctl --user enable --now bench-mirror.service >/dev/null 2>&1 || true

# ---- 3. pi -> the host's Ollama --------------------------------------------
mkdir -p ~/.pi/agent
{
  printf '{\n  "providers": {\n    "ollama": {\n'
  printf '      "baseUrl": "http://%s:11434/v1",\n' "$OLLAMA_HOST"
  printf '      "api": "openai-completions",\n      "apiKey": "ollama",\n'
  # Ollama rejects the `developer` role, and reasoning_effort with it.
  printf '      "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false },\n'
  printf '      "models": [\n'
  IFS=','; first=1
  for m in $MODELS; do
    [[ $first == 1 ]] || printf ',\n'
    printf '        { "id": "%s" }' "$m"
    first=0
  done
  unset IFS
  printf '\n      ]\n    }\n  }\n}\n'
} > ~/.pi/agent/models.json

echo "  idle:    $(omarchy-toggle-enabled screensaver-off && echo 'screensaver off' || echo '?'), stay-awake $(test -f ~/.local/state/omarchy/indicators/stay-awake && echo set || echo MISSING)"
echo "  tmux:    $(systemctl --user is-active bench-tmux.service)"
echo "  mirror:  $(systemctl --user is-active bench-mirror.service)"
echo "  pi:      $(pi --list-models 2>/dev/null | tail -n +2 | wc -l) model(s) configured"
REMOTE
done

echo
echo "Provisioned. A reboot is not required, but is the honest test:"
echo "  sudo virsh reboot <domain>   # autologin + both user units should come back"
