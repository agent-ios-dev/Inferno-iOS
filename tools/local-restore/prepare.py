"""Prepare a NEW local VM, never mistake preparation for a completed restore.

Run inside inferno-local with /vm, /app-source and /guide mounts.
Existing disks/tickets are protected: a completed prepare.json is reusable;
an incomplete preparation must be inspected instead of silently overwritten.
"""
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import urllib.request
import zipfile

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pyasn1.codec.der.decoder import decode
from pyasn1.codec.der.encoder import encode
from pyasn1.type import char, univ, tag

ROOT = Path('/vm')
DATA = ROOT / 'InfernoData'
GUIDE = Path('/guide/public/Extras/Inferno')
APP = Path('/app-source')
PROFILE = 'iphone12,1-18A5351d-v1'
DISKS = {'root': 32 << 30, 'firmware': 8 << 20, 'syscfg': 128 << 10,
         'ctrl_bits': 8 << 10, 'nvram': 8 << 10, 'effaceable': 4 << 10,
         'panic_log': 1 << 20, 'sep_nvram': 64 << 10, 'sep_ssc': 128 << 10}


def sequence(*items):
    result = univ.Sequence()
    for index, item in enumerate(items):
        result.setComponentByPosition(index, item)
    return result


def prepare():
    complete = ROOT / 'prepare.json'
    if complete.exists():
        raise SystemExit('Preparation already exists; use the saved VM without regenerating tickets.')
    if DATA.exists() and any(DATA.iterdir()):
        raise SystemExit('Refusing to overwrite existing VM files; inspect the partial preparation.')
    archive = ROOT / 'restore.ipsw'
    if archive.stat().st_size != 5507405643:
        raise ValueError('IPSW download incomplete')
    ticket = ROOT / 'ticket.shsh2'
    expected = '4380ca55889c4ddd08567496fc573f22ec6f4a66192751eee2f701913419db90'
    if hashlib.sha256(ticket.read_bytes()).hexdigest() != expected:
        raise ValueError('Ticket template checksum mismatch')
    with zipfile.ZipFile(archive) as ipsw:
        manifest = plistlib.loads(ipsw.read('BuildManifest.plist'))
        if manifest.get('ProductBuildVersion') != '18A5351d':
            raise ValueError('Unexpected firmware build')
        identities = [item for item in manifest['BuildIdentities']
                      if item['Info'].get('DeviceClass') == 'n104ap'
                      and item['Info'].get('RestoreBehavior') == 'Erase']
        if len(identities) != 1:
            raise ValueError('Expected exactly one n104ap erase identity')
        identity = identities[0]['Manifest']
        DATA.mkdir(parents=True, exist_ok=True)
        restore = DATA / 'Restore'
        restore.mkdir()
        # idevicerestore streams the OS directly from the original IPSW.
        needed = {'BuildManifest.plist', 'Restore.plist'}
        for component in ('KernelCache', 'DeviceTree', 'RestoreRamDisk', 'RestoreTrustCache', 'SEP'):
            needed.add(identity[component]['Info']['Path'])
        for name in sorted(needed):
            parts = Path(name)
            if parts.is_absolute() or '..' in parts.parts or '\\' in name:
                raise ValueError('Unsafe IPSW member')
            target = restore / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with ipsw.open(name) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, 8 << 20)
    for script, destination in [('create_apticket.py', 'root_ticket.der'),
                                ('create_septicket.py', 'sep_root_ticket.der')]:
        subprocess.run(['python3', str(GUIDE / script), 'n104ap',
                        str(restore / 'BuildManifest.plist'), str(ticket),
                        str(DATA / destination)], check=True, stdout=subprocess.DEVNULL)
    profile = (APP / 'app/Sources/AutomaticSetupProfile.swift').read_text()
    expression = re.search(r'static let sepKey = ([^\n]+)', profile).group(1)
    key = bytes.fromhex(''.join(re.findall(r'"([0-9a-f]+)"', expression)))
    if len(key) != 48:
        raise ValueError('Invalid profile SEP key')
    original, remaining = decode((restore / identity['SEP']['Info']['Path']).read_bytes())
    if remaining or str(original[0]) != 'IM4P':
        raise ValueError('Invalid SEP container')
    payload = original[3].asOctets()
    decryptor = Cipher(algorithms.AES(key[16:]), modes.CBC(key[:16])).decryptor()
    plaintext = decryptor.update(payload) + decryptor.finalize()
    im4p = sequence(char.IA5String('IM4P'), char.IA5String('rsep'),
                    char.IA5String('none'), univ.OctetString(plaintext))
    sep_ticket, remaining = decode((DATA / 'sep_root_ticket.der').read_bytes())
    if remaining or str(sep_ticket[0]) != 'IM4M':
        raise ValueError('Invalid SEP ticket')
    wrapped = sep_ticket.subtype(explicitTag=tag.Tag(tag.tagClassContext,
                                tag.tagFormatConstructed, 0), cloneValueFlag=True)
    (DATA / 'sep-firmware.n104.RELEASE.new.img4').write_bytes(
        encode(sequence(char.IA5String('IMG4'), im4p, wrapped)))
    rom = ROOT / 'AppleSEPROM-Cebu-B1'
    if not rom.exists():
        urllib.request.urlretrieve('https://securerom.fun/resources/SEPROM/AppleSEPROM-Cebu-B1', rom)
    if hashlib.sha256(rom.read_bytes()).hexdigest() != 'e3b11f624e3382a203c1f781b889b407554668936c86b0e2d41d229976317a1b':
        raise ValueError('SEP ROM checksum mismatch')
    for name, size in DISKS.items():
        with (DATA / name).open('xb') as disk:
            disk.truncate(size)
    complete.write_text(json.dumps({'profile': PROFILE, 'prepared_only': True,
        'kernel': identity['KernelCache']['Info']['Path'],
        'device_tree': identity['DeviceTree']['Info']['Path'],
        'trustcache': identity['RestoreTrustCache']['Info']['Path'],
        'ramdisk': identity['RestoreRamDisk']['Info']['Path']}, indent=2))
    print('Boot files prepared; disks are blank. Actual restore and filesystem patching still required.')


if __name__ == '__main__':
    prepare()
