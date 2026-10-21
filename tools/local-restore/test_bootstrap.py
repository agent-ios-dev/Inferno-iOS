"""Exercise the native extractor and actual CoreFoundation job mutation."""
from pathlib import Path
import io
import plistlib
import subprocess
import sys
import tarfile
import tempfile

extractor, editor, payload = sys.argv[1:]
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    installed = root / 'installed'
    installed.mkdir()
    subprocess.run([extractor, str(installed), payload], check=True)
    assert (installed / 'bin/bash').stat().st_size > 4096
    assert (installed / 'usr/bin/dpkg').exists()
    for index, name in enumerate(('../escaped', '/absolute')):
        bad = root / f'bad-{index}.tar'
        with tarfile.open(bad, 'w') as archive:
            member = tarfile.TarInfo(name); member.size = 3
            archive.addfile(member, io.BytesIO(b'bad'))
        assert subprocess.run([extractor, str(installed), str(bad)]).returncode != 0
        assert not (root / 'escaped').exists()
    for fmt in (plistlib.FMT_BINARY, plistlib.FMT_XML):
        path = root / f'cache-{fmt.name}.plist'
        original = {'LaunchDaemons': {'existing': {'Label': 'keep', 'Disabled': True}},
                    'Other': {'Blob': b'\0\xff', 'Number': 42}}
        initial = plistlib.dumps(original, fmt=fmt); path.write_bytes(initial)
        subprocess.run([editor, str(path)], check=True)
        value = plistlib.loads(path.read_bytes())
        key = '/System/Library/LaunchDaemons/com.inferno.console.plist'
        job = value['LaunchDaemons'].pop(key)
        assert value == original
        assert job['UserName'] == 'root' and job['RunAtLoad']
        assert job['ProgramArguments'] == ['/bin/bash', '--noprofile', '--norc', '-i']
        backup = Path(str(path)+'.inferno-before-bootstrap')
        assert backup.read_bytes() == initial
        once = path.read_bytes()
        subprocess.run([editor, str(path)], check=True)
        assert plistlib.loads(path.read_bytes()) == plistlib.loads(once)
        assert backup.read_bytes() == initial
    for index, value in enumerate(({'LaunchDaemons': []}, {}, [], {'LaunchDaemons': {
            '/System/Library/LaunchDaemons/com.inferno.console.plist': {'Label': 'unrelated'}}})):
        path = root / f'invalid-{index}.plist'
        before = plistlib.dumps(value); path.write_bytes(before)
        assert subprocess.run([editor, str(path)]).returncode != 0
        assert path.read_bytes() == before
print('Bootstrap native checks passed: real pinned archive, traversal rejection, binary/XML preservation, idempotence and conflict rejection')
