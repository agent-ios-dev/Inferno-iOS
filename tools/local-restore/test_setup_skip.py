"""Exercise actual native CoreFoundation preference edits, not a Python copy."""
import pathlib
import plistlib
import subprocess
import sys
import tempfile

tool = str(pathlib.Path(sys.argv[1]).resolve(strict=True))
with tempfile.TemporaryDirectory() as folder:
    root = pathlib.Path(folder)
    for index, fmt in enumerate((plistlib.FMT_XML, plistlib.FMT_BINARY)):
        path = root / f'prefs{index}.plist'
        before = {'SetupDone': False, 'Keep': {'Language': 'ru', 'Array': [1, True, 'x']}}
        raw = plistlib.dumps(before, fmt=fmt)
        path.write_bytes(raw)
        subprocess.run([tool, str(path)], check=True)
        changed = plistlib.loads(path.read_bytes())
        assert changed == {**before, 'SetupDone': True, 'SetupFinishedAllSteps': True}
        backup = pathlib.Path(str(path) + '.inferno-before-setup-skip')
        assert backup.read_bytes() == raw
        first = path.read_bytes()
        subprocess.run([tool, str(path)], check=True)
        assert path.read_bytes() == first and backup.read_bytes() == raw
    fresh = root / 'new.plist'
    subprocess.run([tool, str(fresh)], check=True)
    assert plistlib.loads(fresh.read_bytes()) == {'SetupDone': True, 'SetupFinishedAllSteps': True}
    for index, data in enumerate((b'not a plist', plistlib.dumps(['wrong root']))):
        path = root / f'invalid{index}.plist'
        path.write_bytes(data)
        assert subprocess.run([tool, str(path)]).returncode != 0
        assert path.read_bytes() == data
    link = root / 'link.plist'
    link.symlink_to(fresh)
    assert subprocess.run([tool, str(link)]).returncode != 0
    print('Native XML/binary preservation, backup, idempotency and rejection checks passed.')
