#!/bin/bash
# Script to define and start ni-dev-vm1 on Widow (192.168.93.101)
# NOTE: XML uses type="qemu" because this host's libvirt doesn't report kvm support,
# but /dev/kvm exists so QEMU will auto-detect KVM acceleration at runtime.

VMXML="/tmp/ni-dev-vm1.xml"
REMOTE="pete@192.168.93.101"

cat > "$VMXML" << 'XMLEOF'
<domain type="qemu">
  <name>ni-dev-vm1</name>
  <memory unit="MiB">8192000</memory>
  <vcpu placement="static">12</vcpu>
  <maxvcpus>64</maxvcpus>
  <os>
    <type arch="x86_64" machine="q35">hvm</type>
  </os>
  <clock offset="utc">
    <timer name="pit" tickpolicy="delay"/>
    <timer name="rtc" tickpolicy="catchup"/>
  </clock>
  <features>
    <acpi/>
  </features>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type="file" device="disk">
      <driver name="qemu" type="raw" cache="none" io="native" num_queues="12"/>
      <source file="/var/lib/libvirt/images/ubuntu-24.04-server-cloudimg-amd64.img"/>
      <target dev="vda" bus="virtio"/>
      <boot order="1"/>
    </disk>
    <console type="pty">
      <target port="0" type="serial"/>
    </console>
    <interface type="network">
      <source network="ni-dev-net"/>
      <mac address="52:54:00:ab:cd:ef"/>
      <model type="virtio"/>
    </interface>
    <graphics type="vnc" autoport="yes" keymap="en-us">
      <listen type="address"/>
    </graphics>
    <video>
      <model type="none"/>
    </video>
    <rng model="virtio">
      <backend model="random" type="file">
        <source path="/dev/urandom"/>
      </backend>
    </rng>
  </devices>
</domain>
XMLEOF

echo "XML generated: $(wc -c < "$VMXML") bytes"

# SCP to remote and define/start
scp "$VMXML" "${REMOTE}:/tmp/ni-dev-vm1.xml"
if [ $? -ne 0 ]; then
    echo "FAILED to SCP XML"
    exit 1
fi

echo "--- Defining VM ---"
ssh "$REMOTE" "virsh define /tmp/ni-dev-vm1.xml 2>&1"

echo "--- Starting VM ---"
ssh "$REMOTE" "virsh start ni-dev-vm1 2>&1"

echo "--- VM Status ---"
ssh "$REMOTE" "virsh list --all"
