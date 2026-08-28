#!/usr/bin/env bash
#
# Build a throwaway Omarchy test VM, installed unattended.
#
#   tools/make-test-vm.sh 1 [/path/to/omarchy.iso]
#
# The Omarchy ISO looks for a drive labelled `cidata` (the cloud-init NoCloud
# label) and, finding one, skips its interactive configurator and installs from
# the files on it -- see /usr/local/bin/omarchy-cidata-load on the ISO. We build
# that drive here with exactly the files the wizard would otherwise have
# written, so the install runs the ordinary code path against ordinary inputs.
#
# Destroys and recreates the named VM. It is a test VM; that is the point.

set -euo pipefail

N=${1:?usage: make-test-vm.sh <number> [iso]}
ISO=${2:-$HOME/Downloads/omarchy-4.0.1.iso}
VM="opinionated-omarchy-test$N"
HOSTNAME="$VM"

USERNAME=${OMARCHY_TEST_USER:-techluddite}
PASSWORD=${OMARCHY_TEST_PASSWORD:-omarchytest}
PUBKEY_FILE=${OMARCHY_TEST_PUBKEY:-$HOME/.ssh/id_ed25519.pub}

DISK_GIB=${OMARCHY_TEST_DISK_GIB:-60}
RAM_MIB=${OMARCHY_TEST_RAM_MIB:-4096}
VCPUS=${OMARCHY_TEST_VCPUS:-4}
POOL=/var/lib/libvirt/images

[[ -f $ISO ]]        || { echo "no ISO at $ISO" >&2; exit 1; }
[[ -f $PUBKEY_FILE ]]|| { echo "no public key at $PUBKEY_FILE" >&2; exit 1; }

# Partition geometry. These are BYTES, and they mirror the arithmetic in the
# ISO's own configurator: 1 MiB gap, a 2 GiB ESP, the rest btrfs, 1 MiB left at
# the end for the GPT backup header. Getting this wrong produces an install that
# fails late, inside archinstall, with a confusing error.
MIB=$((1024 * 1024)); GIB=$((MIB * 1024))
DISK_BYTES=$((DISK_GIB * GIB))
BOOT_START=$MIB
BOOT_SIZE=$((2 * GIB))
MAIN_START=$((BOOT_SIZE + BOOT_START))
MAIN_SIZE=$((DISK_BYTES - MAIN_START - MIB))

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
SEED=$WORK/seed; mkdir -p "$SEED"

HASH=$(printf '%s' "$PASSWORD" | openssl passwd -6 -stdin)

printf 'TechLuddite\n'             >"$SEED/user_full_name.txt"
printf 'techluddite@outlook.com\n' >"$SEED/user_email_address.txt"
printf 'false\n'                   >"$SEED/user_encrypt_installation.txt"
cat "$PUBKEY_FILE"                 >"$SEED/authorized_keys"

jq -n --arg h "$HASH" --arg u "$USERNAME" '{
  root_enc_password: $h,
  users: [ { enc_password: $h, groups: [], sudo: true, username: $u } ]
}' >"$SEED/user_credentials.json"

jq -n --arg host "$HOSTNAME" --arg dev /dev/vda \
      --arg tz "$(timedatectl show -p Timezone --value)" \
      --argjson bs "$BOOT_START" --argjson bz "$BOOT_SIZE" \
      --argjson ms "$MAIN_START" --argjson mz "$MAIN_SIZE" '
{
  "app_config": null, "archinstall-language": "English", "auth_config": {},
  "audio_config": { "audio": "pipewire" },
  "bootloader_config": { "bootloader": "Limine", "uki": false, "removable": false },
  "custom_commands": [],
  "omarchy_install": {
    "mode": "full_disk", "defer_provisioning": false, "target_mount": "/mnt",
    "boot": { "esp_mount": "/boot", "esp_path": "/EFI/limine",
              "efi_binary": "limine_x64.efi", "enable_fallback": true },
    "storage": { "kernel": "linux" }
  },
  "disk_config": {
    "config_type": "default_layout",
    "device_modifications": [ {
      "device": $dev, "wipe": true,
      "partitions": [
        { "btrfs": [], "dev_path": null, "flags": ["boot","esp"], "fs_type": "fat32",
          "mount_options": [], "mountpoint": "/boot",
          "obj_id": "ea21d3f2-82bb-49cc-ab5d-6f81ae94e18d",
          "size":  { "sector_size": {"unit":"B","value":512}, "unit":"B", "value": $bz },
          "start": { "sector_size": {"unit":"B","value":512}, "unit":"B", "value": $bs },
          "status": "create", "type": "primary" },
        { "btrfs": [ {"mountpoint":"/","name":"@"}, {"mountpoint":"/home","name":"@home"},
                     {"mountpoint":"/var/log","name":"@log"},
                     {"mountpoint":"/var/cache/pacman/pkg","name":"@pkg"} ],
          "dev_path": null, "flags": [], "fs_type": "btrfs",
          "mount_options": ["compress=zstd"], "mountpoint": null,
          "obj_id": "8c2c2b92-1070-455d-b76a-56263bab24aa",
          "size":  { "sector_size": {"unit":"B","value":512}, "unit":"B", "value": $mz },
          "start": { "sector_size": {"unit":"B","value":512}, "unit":"B", "value": $ms },
          "status": "create", "type": "primary" }
      ] } ]
  },
  "hostname": $host, "kernels": ["linux"], "network_config": {"type":"iso"},
  "ntp": true, "parallel_downloads": 8, "script": null, "services": [], "swap": true,
  "timezone": $tz,
  "locale_config": { "kb_layout": "us", "sys_enc": "UTF-8", "sys_lang": "en_US.UTF-8" },
  "mirror_config": { "custom_repositories": [],
    "custom_servers": [ {"url":"https://mirror.omarchy.org/$repo/os/$arch"},
                        {"url":"https://mirror.rackspace.com/archlinux/$repo/os/$arch"},
                        {"url":"https://geo.mirror.pkgbuild.com/$repo/os/$arch"} ],
    "mirror_regions": {}, "optional_repositories": [] },
  "packages": ["base-devel","git","omarchy-keyring","omarchy-settings","omarchy"],
  "profile_config": { "gfx_driver": null, "greeter": null, "profile": {} },
  "version": "3.0.9"
}' >"$SEED/user_configuration.json"

xorrisofs -quiet -V CIDATA -J -r -o "$WORK/cidata.iso" "$SEED"

sudo cp "$WORK/cidata.iso" "$POOL/cidata$N.iso"
sudo chmod 644 "$POOL/cidata$N.iso"
[[ -f $POOL/$(basename "$ISO") ]] || sudo cp "$ISO" "$POOL/"
sudo chmod 644 "$POOL/$(basename "$ISO")"

if sudo virsh dominfo "$VM" &>/dev/null; then
  sudo virsh destroy "$VM" &>/dev/null || true
  sudo virsh undefine "$VM" --nvram --remove-all-storage &>/dev/null || true
fi

# Boot order is hd,cdrom on purpose: the empty disk has no EFI loader so the
# firmware falls through to the installer now, and boots the installed system
# once there is one. No need to eject the ISO afterwards.
sudo virt-install \
  --name "$VM" \
  --memory "$RAM_MIB" --vcpus "$VCPUS" --cpu host-passthrough \
  --machine q35 --boot uefi \
  --disk "path=$POOL/$VM.qcow2,size=$DISK_GIB,format=qcow2,bus=virtio" \
  --disk "path=$POOL/$(basename "$ISO"),device=cdrom,readonly=on" \
  --disk "path=$POOL/cidata$N.iso,device=cdrom,readonly=on" \
  --network network=default,model=virtio \
  --graphics spice --video virtio --channel spicevmc \
  --osinfo archlinux \
  --noautoconsole --import

echo "$VM building. Watch with: sudo virsh net-dhcp-leases default"
