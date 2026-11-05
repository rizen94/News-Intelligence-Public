#!/bin/bash
set -euo pipefail

echo "=== STEP 0: Create VM disk image (40GB qcow2) ==="
qemu-img create -f qcow2 /tmp/kvm-setup/ni-dev-vm1.qcow2 40G
echo "Disk created: $(ls -lh /tmp/kvm-setup/ni-dev-vm1.qcow2 | awk '{print $5, $NF}')"

echo "=== STEP 1: Generate proper cloud-init ISO ==="
ISO_DIR="/tmp/kvm-setup/cloudinit-new"
mkdir -p "${ISO_DIR}"
cd "${ISO_DIR}"

# Build flat ISO source tree — cloud-init expects 'user-data' and 'meta-data' at root
rm -rf iso-src && mkdir iso-src
cd iso-src

cat > meta-data <<'EOF'
instance-id: ni-dev-vm1
local-hostname: ni-dev
EOF

SSH_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIH8a4t2mm/Aq/Ws1FtvqJecYDzT34Q33SFAZNoL+mZx2 peteshipman@gmail.com"

cat > user-data <<USEREOF
#cloud-config
password: ubuntu
chpasswd:
  expire: false
ssh_pw_auth: true
hostname: ni-dev
users:
  - name: ubuntu
    groups: sudo,wheel,docker
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    ssh_authorized_keys:
      - ${SSH_KEY}
runcmd:
  - systemctl enable ssh
  - echo "VM initialized on \$(date)" > /var/log/vm-init.log
  - apt-get update -qq && apt-get install -y -qq qemu-guest-agent && systemctl enable --now qemu-guest-agent
network:
  version: 2
  ethernets:
    ens3:
      dhcp4: true
USEREOF

# Build ISO with proper volume ID "cidata" (required by cloud-init)
xorriso -as mkisofs \
  -iso-level 3 \
  -full-iso9660-filenames \
  -volid "cidata" \
  -joliet \
  -rock \
  -sysid "LINUX_64" \
  -o /tmp/kvm-setup/ni-dev-vm1-cloud-init.iso \
  .

echo "ISO created: $(ls -lh /tmp/kvm-setup/ni-dev-vm1-cloud-init.iso | awk '{print $5, $NF}')"

# Verify ISO volume label (skip el-torito since this is a data-only ISO)
xorriso -indev /tmp/kvm-setup/ni-dev-vm1-cloud-init.iso \
  -find / type f -exec report _as_mkisofs {} + 2>/dev/null || true

# Ensure it's readable by libvirt-qemu (pool target is already mode 0777)
chmod 644 /tmp/kvm-setup/ni-dev-vm1-cloud-init.iso

echo "=== STEP 2: Create fixed VM XML (4GB RAM, 4 vCPU) ==="

cat > "${ISO_DIR}/vm-fix.xml" <<'XMLEOF'
<domain type="qemu">
  <name>ni-dev-vm1</name>
  <memory unit="GiB">4</memory>
  <vcpu placement="static">4</vcpu>
  <os>
    <type arch="x86_64" machine="q35">hvm</type>
    <boot dev="hd"/>
  </os>
  <devices>
    <disk type="file" device="disk">
      <driver name="qemu" type="qcow2" cache="none"/>
      <source file="/tmp/kvm-setup/ni-dev-vm1.qcow2"/>
      <target dev="vda" bus="virtio"/>
    </disk>
    <disk type="file" device="cdrom">
      <driver name="qemu" type="raw" cache="none"/>
      <source file="/tmp/kvm-setup/ni-dev-vm1-cloud-init.iso"/>
      <target dev="sda" bus="sata"/>
    </disk>
    <interface type="bridge">
      <source bridge="ni-dev-net"/>
      <model type="virtio"/>
    </interface>
    <console type="pty">
      <target type="serial" port="0"/>
    </console>
  </devices>
</domain>
XMLEOF

echo "=== STEP 3: Redefine VM ==="
virsh undefine ni-dev-vm1 --nvram 2>/dev/null || true
virsh define "${ISO_DIR}/vm-fix.xml"
virsh start ni-dev-vm1

echo ""
echo "=== STEP 4: Verify ==="
sleep 3
virsh domstate ni-dev-vm1
virsh dumpxml ni-dev-vm1 | grep -E "<memory|<vcpu|<source file"

echo "=== DONE ==="