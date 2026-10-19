"""Copy one running local VM at a coordinated disk checkpoint, then resume it.

QMP stop drains and flushes block devices in this pinned QEMU. This is a
crash-consistent disk copy, not a clean guest shutdown or a verified boot kit.
Never resets, quits, or replaces the user's VM. Cold-test the independent copy.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from backup_windows import digest
from new_attempt import DISKS
from qmp import execute


def copy(vm, destination, container):
    if os.name != 'nt':
        raise ValueError('This sparse-copy implementation requires Windows')
    vm = vm.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists() or destination == vm or vm in destination.parents:
        raise ValueError('Destination must be new and outside the live VM')
    if any((p / '.git').exists() for p in (destination, *destination.parents)):
        raise ValueError('Guest disks must remain outside Git repositories')
    if shutil.disk_usage(destination.parent).free < 40 << 30:
        raise ValueError('Reserve at least40GiB for the temporary disk checkpoint')
    details = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    if not details['State']['Running']:
        raise ValueError('Expected live container')
    mounts = [m for m in details['Mounts'] if m['Destination'] == '/vm' and m['RW']]
    norm = lambda p: str(p).replace('\\', '/').lower().rstrip('/')
    if len(mounts) != 1 or norm(mounts[0]['Source']) != norm(vm):
        raise ValueError('Live container must mount the exact requested VM')
    block = execute('query-block')
    paths = {b.get('inserted', {}).get('file') for b in block}
    expected = {'/vm/InfernoData/' + name for name in DISKS}
    if paths != expected or not execute('query-status').get('running'):
        raise ValueError('QMP does not identify the expected running nine-disk VM')
    for name, size in DISKS.items():
        path = vm / 'InfernoData' / name
        if path.is_symlink() or path.stat().st_size != size:
            raise ValueError('Unexpected source disk: ' + name)
    immutable = ['prepare.json', 'AppleSEPROM-Cebu-B1',
                 'InfernoData/root_ticket.der', 'InfernoData/sep_root_ticket.der',
                 'InfernoData/sep-firmware.n104.RELEASE.new.img4']
    for name in [*immutable, 'InfernoData/Restore', 'qemu-data']:
        path = vm / name
        if not path.exists() or path.is_symlink() or (path.is_dir() and any(p.is_symlink() for p in path.rglob('*'))):
            raise ValueError('Missing or linked immutable input: ' + name)
    destination.mkdir(parents=True)
    data = destination / 'InfernoData'
    data.mkdir()
    hashes = {}
    started = time.monotonic()
    def deadline():
        if time.monotonic() - started > 300:
            raise TimeoutError('Pause-copy budget exceeded; copy is incomplete')
    try:
        execute('stop')
        if execute('query-status').get('status') != 'paused':
            raise ValueError('QMP did not acknowledge paused state')
        print('Guest paused and disks drained; copying all nine disks.', flush=True)
        for name, size in DISKS.items():
            deadline()
            source, target = vm / 'InfernoData' / name, data / name
            if name == 'root':
                ranges = subprocess.check_output(['fsutil', 'sparse', 'queryrange', str(source)], text=True)
                extents = [(int(a, 16), int(b, 16)) for a, b in re.findall(
                    r'Offset:\s*(0x[0-9a-fA-F]+)\s+Length:\s*(0x[0-9a-fA-F]+)', ranges)]
                if not extents or any(a < 0 or b <= 0 or a + b > size for a, b in extents):
                    raise ValueError('Invalid allocated ranges')
                target.touch()
                subprocess.run(['fsutil', 'sparse', 'setflag', str(target)], check=True)
                with source.open('rb') as reader, target.open('r+b') as writer:
                    writer.seek(size - 1)
                    writer.write(b'\0')
                    for offset, length in extents:
                        reader.seek(offset)
                        writer.seek(offset)
                        while length:
                            deadline()
                            chunk = reader.read(min(16 << 20, length))
                            if not chunk:
                                raise EOFError('Source shortened')
                            writer.write(chunk)
                            length -= len(chunk)
                    writer.flush()
                    os.fsync(writer.fileno())
            else:
                shutil.copyfile(source, target)
            hashes[name] = {'size': size, 'sha256': digest(source)}
            print('Captured ' + name, flush=True)
        deadline()
        if execute('query-status').get('status') != 'paused':
            raise ValueError('Guest resumed during disk capture; reject copy')
        (destination / 'captured-source-hashes.json').write_text(json.dumps(hashes, indent=2))
    finally:
        # Resume even when copying or validation fails. Never quit/reset it.
        execute('cont')
        print('Original guest resumed: ' + str(execute('query-status').get('running')), flush=True)
    for name, evidence in hashes.items():
        target = data / name
        if target.stat().st_size != evidence['size'] or digest(target) != evidence['sha256']:
            raise ValueError('Copied disk hash mismatch: ' + name)
    for name in immutable:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(vm / name, target)
    for name in ('InfernoData/Restore', 'qemu-data'):
        shutil.copytree(vm / name, destination / name)
    (data / 'verified.json').write_text(json.dumps(hashes, indent=2))
    (destination / 'cold-copy.json').write_text(json.dumps({
        'capture': 'paused-drained-disk-checkpoint',
        'all_mutable_disks_copied_and_hash_verified': True,
        'original_guest_resumed': True, 'cold_boot_tested': False,
        'visible_springboard_confirmed': False}, indent=2))
    print('Independent disk checkpoint verified; cold boot still required.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vm', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--container', default='inferno-local-restore')
    args = parser.parse_args()
    copy(args.vm, args.destination, args.container)
