"""Create a separate cold-test copy of a stopped installed VM on Windows.

Does not run a guest, reset a machine, erase disks, export a delivery archive or
assert successful boot. All mutable disks are independently copied and hashed.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def clone(source, destination):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists() or destination == source or source in destination.parents:
        raise ValueError('Use a new cold-test directory outside the original VM')
    if any((parent / '.git').exists() for parent in [destination, *destination.parents]):
        raise ValueError('Guest disks cannot be copied into a Git repository')
    immutable = ['prepare.json', 'AppleSEPROM-Cebu-B1',
                 'InfernoData/root_ticket.der', 'InfernoData/sep_root_ticket.der',
                 'InfernoData/sep-firmware.n104.RELEASE.new.img4']
    for name in immutable:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing regular boot input: ' + name)
    destination.mkdir(parents=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name('backup_windows.py')),
                    str(source), '--destination', str(destination / 'InfernoData')], check=True)
    for name in immutable:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    for name in ('InfernoData/Restore', 'qemu-data'):
        if any(p.is_symlink() for p in (source / name).rglob('*')):
            raise ValueError('Symlink in boot inputs')
        shutil.copytree(source / name, destination / name)
    (destination / 'cold-copy.json').write_text(json.dumps({
        'all_mutable_disks_copied_and_hash_verified': True,
        'restore_client_or_ramdisk_required_for_normal_boot': False,
        'cold_boot_tested': False, 'visible_springboard_confirmed': False}, indent=2))
    print('Independent installed disk set ready for cold testing; no UI success inferred.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    clone(args.source, args.destination)
