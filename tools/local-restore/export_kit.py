"""Export a privately delivered, verified installed VM for the iPhone app.

Requires saved visible-UI and cold-boot evidence and stopped writable VM mounts.
Converts the raw root to compressed qcow2, then compares all guest sectors.
Never includes IPSW, restore logs, memory snapshots or private analysis files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from new_attempt import DISKS


def normalized(path):
    return str(path).replace('\\', '/').lower().rstrip('/')


def export(vm, destination, proof_path, image):
    vm = vm.resolve(strict=True)
    destination = destination.resolve()
    proof = json.loads(proof_path.read_text())
    if not (proof.get('visible_springboard_confirmed') is True or
            proof.get('visible_setup_confirmed') is True):
        raise ValueError('A real guest UI must be visually confirmed')
    if not all(proof.get(key) is True for key in (
        'springboard_process_seen', 'backboardd_process_seen',
        'cold_boot_without_restore_confirmed')):
        raise ValueError('Visible working UI and separate cold boot are not confirmed')
    if not re.fullmatch(r'[0-9a-f]{40}', proof.get('backend_commit', '')):
        raise ValueError('Proof must identify the exact tested backend commit')
    configuration = proof.get('boot_configuration', {})
    if (configuration.get('total_cores') not in range(2, 8)
            or configuration.get('memory') not in ('2G', '3G', '4G')
            or configuration.get('restore_ramdisk_attached') is not False):
        raise ValueError('Proof must record tested CPU/memory settings and no restore RAMdisk')
    if destination.exists() or destination == vm or vm in destination.parents:
        raise ValueError('Use a new output folder outside the VM')
    if any((parent / '.git').exists() for parent in [destination, *destination.parents]):
        raise ValueError('Never export guest assets inside a Git repository')
    archive = destination.with_suffix('.zip')
    if archive.exists():
        raise ValueError('Refusing to replace an existing delivery archive')
    running = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
    if running:
        containers = json.loads(subprocess.check_output(['docker', 'inspect', *running], text=True))
        for container in containers:
            for mount in container.get('Mounts', []):
                mounted, current = normalized(mount.get('Source', '')), normalized(vm)
                if mount.get('RW') and (mounted == current or mounted.startswith(current + '/')
                                       or current.startswith(mounted + '/')):
                    raise ValueError('Stop all containers with writable VM mounts before export')
    prepared = json.loads((vm / 'prepare.json').read_text())
    if prepared.get('profile') != 'iphone12,1-18A5351d-v1':
        raise ValueError('Unexpected guest profile')
    files = ['AppleSEPROM-Cebu-B1', 'InfernoData/root_ticket.der',
             'InfernoData/sep_root_ticket.der', 'InfernoData/sep-firmware.n104.RELEASE.new.img4',
             'InfernoData/Restore/BuildManifest.plist', 'InfernoData/Restore/Restore.plist']
    files += ['InfernoData/' + name for name in DISKS if name != 'root']
    for key in ('kernel', 'device_tree', 'trustcache'):
        value = prepared[key]
        if Path(value).is_absolute() or '..' in Path(value).parts or '\\' in value:
            raise ValueError('Unsafe boot component path')
        files.append('InfernoData/Restore/' + value)
    root_name = 'root.qcow2' if (vm / 'InfernoData/root.qcow2').is_file() else 'root'
    root_format = 'qcow2' if root_name.endswith('.qcow2') else 'raw'
    for name in [*files, 'InfernoData/' + root_name]:
        path = vm / name
        if path.resolve(strict=True) != path.absolute() or not path.is_file():
            raise ValueError('Missing regular VM input: ' + name)
    for name, size in DISKS.items():
        if name == 'root' and root_format == 'qcow2':
            continue
        if (vm / 'InfernoData' / name).stat().st_size != size:
            raise ValueError('Unexpected disk size: ' + name)
    destination.mkdir(parents=True)
    (destination / 'InfernoData').mkdir()
    docker = ['docker', 'run', '--rm', '--memory', '1g',
              '--mount', f'type=bind,source={vm},target=/source,readonly',
              '--mount', f'type=bind,source={destination},target=/output', image,
              '/opt/inferno/build/qemu-img']
    root_source = '/source/InfernoData/' + root_name
    info = json.loads(subprocess.check_output([*docker, 'info', '--output=json', root_source], text=True))
    if info.get('format') != root_format or info.get('virtual-size') != DISKS['root'] or info.get('backing-filename'):
        raise ValueError('Root must be a standalone disk of the expected virtual size')
    subprocess.run([*docker, 'convert', '-p', '-f', root_format, '-O', 'qcow2', '-c',
                    root_source, '/output/InfernoData/root.qcow2'], check=True)
    subprocess.run([*docker, 'check', '-f', 'qcow2', '/output/InfernoData/root.qcow2'], check=True)
    subprocess.run([*docker, 'compare', '-f', root_format, '-F', 'qcow2',
                    root_source, '/output/InfernoData/root.qcow2'], check=True)
    for name in files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(vm / name, target)
        with (vm / name).open('rb') as a, target.open('rb') as b:
            if hashlib.file_digest(a, 'sha256').digest() != hashlib.file_digest(b, 'sha256').digest():
                raise ValueError('Copied component hash mismatch: ' + name)
    files.append('InfernoData/root.qcow2')
    hashes = {}
    for name in files:
        with (destination / name).open('rb') as stream:
            hashes[name] = {'bytes': (destination / name).stat().st_size,
                            'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
    metadata = {'profile': prepared['profile'], 'backend_commit': proof['backend_commit'],
                'boot_configuration': configuration,
                'root_virtual_bytes': DISKS['root'], 'root_sector_comparison_passed': True,
                'files': hashes, 'boot_evidence': proof,
                'physical_iphone_boot_verified': proof.get('physical_iphone_boot_verified', False)}
    (destination / 'Inferno-VM.json').write_text(json.dumps(metadata, indent=2))
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as output:
        for name in [*files, 'Inferno-VM.json']:
            output.write(destination / name, name)
    print('Private installed VM kit exported; physical iPhone verification remains separate.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vm', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--image', default='inferno-local:sep-status')
    args = parser.parse_args()
    export(args.vm, args.destination, args.proof, args.image)
