"""Fetch the exact utility bootstrap documented by Inferno; never a firmware image."""
import hashlib
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request
import sys

URL = 'https://assets.checkra.in/loader/ios/core/3bda4c4ddb50d7c89eec6260f42f7ba91535de64/strap.tar.lzma'
SHA512 = '76565c01d8d64ab05459ed0943666283c4c230e0f31954ca6ba235902d7078e7aba464b9fd0a908b35b5f1eb1ea8ab6ba22a738ee998aaf67a7929b63d22e26b'

def validate(path):
    assert hashlib.sha512(path.read_bytes()).hexdigest() == SHA512, 'Bootstrap digest mismatch'
    with tarfile.open(path, 'r:*') as archive:
        members = archive.getmembers()
        assert len(members) < 5000
        assert sum(m.size for m in members) < 128 * 1024 * 1024
        for m in members:
            p = PurePosixPath(m.name)
            assert not p.is_absolute() and '..' not in p.parts and p.parts
            assert p.parts[0] in ('bin', 'sbin', 'usr', 'Library', 'private', 'etc', 'var') or (
                m.isdir() and p.parts[0] in ('Applications', 'System', 'boot', 'dev', 'lib', 'mnt')), m.name
            assert m.isfile() or m.isdir() or m.issym(), m.name
    return len(members)

if __name__ == '__main__':
    directory = Path(sys.argv[1]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    payload = directory / 'strap.tar.lzma'
    if not payload.exists():
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read(20 * 1024 * 1024 + 1)
        assert len(data) <= 20 * 1024 * 1024
        payload.write_bytes(data)
    count = validate(payload)
    # Mach-O symbols are relocated by the loader along with the executable.
    escaped = payload.as_posix().replace('\\', '\\\\').replace('"', '\\"')
    (directory / 'strap.S').write_text('.section __DATA,__strap\n.globl _inferno_strap_start\n'
        '_inferno_strap_start:\n.incbin "' + escaped + '"\n.globl _inferno_strap_end\n_inferno_strap_end:\n')
    print(f'Pinned utility bootstrap verified: {count} entries; no guest firmware included')
