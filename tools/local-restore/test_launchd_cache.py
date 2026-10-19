"""Native CoreFoundation mutation test; does not execute or emulate guest iOS."""
from copy import deepcopy
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

names = ['com.apple.voicemail.vmd', 'com.apple.CommCenter',
         'com.apple.CommCenterMobileHelper', 'com.apple.CommCenterRootHelper',
         'com.apple.locationd']
with tempfile.TemporaryDirectory() as folder:
    for fmt in (plistlib.FMT_BINARY, plistlib.FMT_XML):
        path = Path(folder) / ('binary.plist' if fmt == plistlib.FMT_BINARY else 'xml.plist')
        original = {'LaunchDaemons': {name: {'Label': name, 'ProgramArguments': ['/keep', name],
                    'KeepAlive': {'SuccessfulExit': False}} for name in names},
                    'Unrelated': {'Label': 'com.example.unchanged', 'Payload': b'\x00\xff', 'Number': 42}}
        expected = deepcopy(original)
        for name in names:
            expected['LaunchDaemons'][name]['Disabled'] = True
        initial = plistlib.dumps(original, fmt=fmt)
        path.write_bytes(initial)
        subprocess.run([sys.argv[1], str(path)], check=True)
        assert plistlib.loads(path.read_bytes()) == expected
        backup = Path(str(path) + '.inferno-original')
        assert backup.read_bytes() == initial
        subprocess.run([sys.argv[1], str(path)], check=True)
        assert plistlib.loads(path.read_bytes()) == expected
        assert backup.read_bytes() == initial
    for case in ('missing', 'duplicate', 'invalid'):
        path = Path(folder) / (case + '.plist')
        value = [{'Label': name} for name in names]
        if case == 'missing': value.pop()
        if case == 'duplicate': value.append({'Label': names[0]})
        initial = b'not a plist' if case == 'invalid' else plistlib.dumps(value)
        path.write_bytes(initial)
        assert subprocess.run([sys.argv[1], str(path)]).returncode != 0
        assert path.read_bytes() == initial
        assert not Path(str(path) + '.inferno-original').exists()
print('Native cache patch checks passed: binary/XML, unrelated values, idempotency, missing/duplicate/invalid rejection.')
