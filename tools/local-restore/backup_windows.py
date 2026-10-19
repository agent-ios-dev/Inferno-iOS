"""Copy stopped VM disks using NTFS allocated ranges; verify full disk hashes.

The caller must stop QEMU first. Only resumes the explicit incomplete backup
directory created by the local recovery operation; never hard-links disks.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from new_attempt import DISKS


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vm', type=Path)
    parser.add_argument('--destination', type=Path,
                        help='New directory for a separate cold-test disk set')
    args = parser.parse_args()
    if os.name != 'nt':
        raise SystemExit('NTFS backup requires Windows')
    vm = args.vm.resolve(strict=True)
    running = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
    if running:
        containers = json.loads(subprocess.check_output(['docker', 'inspect', *running], text=True))
        vm_path = str(vm).replace('\\', '/').lower().rstrip('/')
        for container in containers:
            for mount in container.get('Mounts', []):
                mounted = mount.get('Source', '').replace('\\', '/').lower().rstrip('/')
                if mount.get('RW') and (mounted == vm_path or mounted.startswith(vm_path + '/')
                                        or vm_path.startswith(mounted + '/')):
                    raise SystemExit('Stop containers with writable VM mounts before taking a backup')
    destination = (args.destination.resolve() if args.destination else vm / 'pre-patch-backup')
    if args.destination and destination.exists():
        raise SystemExit('Cold-test destination must be new; refusing to overwrite it')
    destination.mkdir(exist_ok=True)
    if (destination / 'verified.json').exists():
        raise SystemExit('Backup is already verified; refusing replacement')
    result = {}
    for name, size in DISKS.items():
        source = vm / 'InfernoData' / name
        target = destination / name
        if source.is_symlink() or target.is_symlink() or source.stat().st_size != size:
            raise ValueError('Unexpected disk input: ' + name)
        if name == 'root':
            ranges = subprocess.check_output(['fsutil', 'sparse', 'queryrange', str(source)], text=True)
            extents = [(int(a, 16), int(b, 16)) for a, b in re.findall(
                r'Offset:\s*(0x[0-9a-fA-F]+)\s+Length:\s*(0x[0-9a-fA-F]+)', ranges)]
            if not extents or any(a < 0 or b <= 0 or a + b > size for a, b in extents):
                raise ValueError('Cannot validate allocated ranges')
            target.touch(exist_ok=True)
            subprocess.run(['fsutil', 'sparse', 'setflag', str(target)], check=True)
            with source.open('rb') as reader, target.open('r+b') as writer:
                # Avoid the Windows CRT truncate extension, which writes zeros.
                writer.seek(size - 1)
                writer.write(b'\0')
                for offset, length in extents:
                    reader.seek(offset)
                    writer.seek(offset)
                    remaining = length
                    while remaining:
                        chunk = reader.read(min(16 << 20, remaining))
                        if not chunk:
                            raise EOFError('Source disk shortened')
                        writer.write(chunk)
                        remaining -= len(chunk)
                writer.flush()
                os.fsync(writer.fileno())
        else:
            shutil.copyfile(source, target)
        print('Verifying ' + name, flush=True)
        before, after = digest(source), digest(target)
        if source.stat().st_size != target.stat().st_size or before != after:
            raise ValueError('Backup hash mismatch: ' + name)
        result[name] = {'size': size, 'sha256': before}
        print('Verified ' + name, flush=True)
    (destination / 'verified.json').write_text(json.dumps(result, indent=2))
    print('All mutable VM disks copied and SHA-256 verified.', flush=True)


if __name__ == '__main__':
    main()
