#!/usr/bin/env bash
#
# Save or restore a test VM's disk as a golden image.
#
#   tools/golden-test-vm.sh save 1      # capture the VM's current disk
#   tools/golden-test-vm.sh reset 1     # throw the VM back to that disk
#   tools/golden-test-vm.sh status      # what exists, and how old
#
# This is the cheap alternative to libvirt snapshots, which these domains make
# awkward: they are UEFI, and libvirt has historically refused internal
# snapshots on pflash domains.
#
# It is cheap because /var/lib/libvirt/images is btrfs, so `cp --reflink` shares
# extents instead of copying bytes. A 6.8 GiB disk image "copies" in well under a
# second and charges ~0 additional space until one side is written to. Check
# before assuming that holds:
#
#   stat -f -c %T /var/lib/libvirt/images     # must say btrfs
#   lsattr <disk>.qcow2                       # a 'C' (NOCOW) flag defeats reflink
#
# The VM must be SHUT OFF at both save and reset. A copy taken from a running
# domain is only crash-consistent: usually bootable, but "usually" is not a
# property to build a bench on. We refuse rather than let that be silent.

set -euo pipefail

ACTION=${1:?usage: golden-test-vm.sh <save|reset|status> [number]}
POOL=/var/lib/libvirt/images

vm_name()   { echo "opinionated-omarchy-test$1"; }
disk_path() { echo "$POOL/$(vm_name "$1").qcow2"; }
gold_path() { echo "$POOL/golden-test$1.qcow2"; }

# libvirt hands the disk back to root when a domain stops and re-chowns it on
# start, so a freshly restored file only has to be readable by libvirt, not
# owned by any particular user. We match the pool's own ownership anyway.
restore_ownership() {
  sudo chown --reference="$POOL" "$1" 2>/dev/null || true
}

require_off() {
  local vm=$1
  local state
  state=$(sudo virsh domstate "$vm" 2>/dev/null || echo "missing")
  if [[ $state != "shut off" ]]; then
    echo "$vm is '$state'; it must be shut off." >&2
    echo "  sudo virsh shutdown $vm    # ACPI, which Omarchy may ignore" >&2
    echo "  ssh <vm> 'sudo systemctl poweroff'   # more reliable here" >&2
    exit 1
  fi
}

reflink_copy() {
  local src=$1 dst=$2
  # --reflink=always, never 'auto': if the filesystem cannot share extents we
  # want to hear about it, not silently spend minutes and gigabytes.
  sudo rm -f "$dst"
  if ! sudo cp --reflink=always "$src" "$dst"; then
    echo "reflink copy failed: is $POOL still btrfs, and the file free of the NOCOW flag?" >&2
    exit 1
  fi
  restore_ownership "$dst"
}

case $ACTION in
  save)
    N=${2:?usage: golden-test-vm.sh save <number>}
    VM=$(vm_name "$N"); DISK=$(disk_path "$N"); GOLD=$(gold_path "$N")
    [[ -f $DISK ]] || { echo "no disk at $DISK" >&2; exit 1; }
    require_off "$VM"
    echo "saving $DISK -> $GOLD"
    reflink_copy "$DISK" "$GOLD"
    echo "saved. $(sudo du -sh "$GOLD" | cut -f1) of extents, shared with the live disk until either is written."
    ;;

  reset)
    N=${2:?usage: golden-test-vm.sh reset <number>}
    VM=$(vm_name "$N"); DISK=$(disk_path "$N"); GOLD=$(gold_path "$N")
    [[ -f $GOLD ]] || { echo "no golden image at $GOLD -- run 'save $N' first" >&2; exit 1; }
    require_off "$VM"
    echo "resetting $VM from $GOLD"
    reflink_copy "$GOLD" "$DISK"
    echo "reset. start it with: sudo virsh start $VM"
    ;;

  status)
    printf '%-32s %-10s %s\n' DOMAIN STATE GOLDEN
    for N in 1 2; do
      VM=$(vm_name "$N"); GOLD=$(gold_path "$N")
      state=$(sudo virsh domstate "$VM" 2>/dev/null || echo missing)
      if [[ -f $GOLD ]]; then
        golden="$(sudo stat -c '%y' "$GOLD" | cut -d. -f1) ($(sudo du -sh "$GOLD" | cut -f1))"
      else
        golden="-"
      fi
      printf '%-32s %-10s %s\n' "$VM" "$state" "$golden"
    done
    ;;

  *)
    echo "usage: golden-test-vm.sh <save|reset|status> [number]" >&2
    exit 1
    ;;
esac
