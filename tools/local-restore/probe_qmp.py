"""Start a paused machine to test QMP without running a guest or touching its disks.

Mount the prepared VM read-only. Only small temporary host probe disks are used.
"""
import json
from pathlib import Path
import os

root = Path('/vm')
data = root / 'InfernoData'
prepared = json.loads((root / 'prepare.json').read_text())
for name, size in [('probe', 1 << 20), ('nvram', 8 << 10), ('sep_nvram', 64 << 10), ('sep_ssc', 128 << 10)]:
    with Path('/tmp', name).open('xb') as stream:
        stream.truncate(size)
machine = ','.join(['t8030', 'trustcache=' + str(data / 'Restore' / prepared['trustcache']),
    'ticket=' + str(data / 'root_ticket.der'),
    'sep-fw=' + str(data / 'sep-firmware.n104.RELEASE.new.img4'),
    'sep-rom=' + str(root / 'AppleSEPROM-Cebu-B1'), 'kaslr-off=true',
    'boot-mode=enter_recovery'])
command = ['qemu-system-aarch64', '-M', machine, '-S', '-display', 'none',
    '-m', '3G', '-smp', '7', '-qmp', 'tcp:0.0.0.0:4444,server=on,wait=off',
    '-kernel', str(data / 'Restore' / prepared['kernel']),
    '-dtb', str(data / 'Restore' / prepared['device_tree']),
    '-initrd', str(root / 'patched-ramdisk.im4p'),
    '-drive', 'file=/tmp/probe,if=none,format=raw,id=probe',
    '-drive', 'file=/tmp/sep_nvram,if=pflash,format=raw',
    '-drive', 'file=/tmp/sep_ssc,if=pflash,format=raw',
    '-drive', 'file=/tmp/nvram,if=none,format=raw,id=nvram',
    '-device', 'apple-nvram,drive=nvram,bus=nvme-bus.0,nsid=5,nstype=5,id=nvram,logical_block_size=4096,physical_block_size=4096']
os.execvp(command[0], command)
