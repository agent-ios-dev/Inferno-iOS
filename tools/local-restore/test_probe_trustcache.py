"""Check code hashes against codesign when available and reject malformed inputs."""
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from probe_trustcache import build, cache_payload, code_hashes

directory = Path(sys.argv[1])
names = ('inferno-probe', 'inferno-probe.dylib')
binaries = [(directory / name).read_bytes() for name in names]
for name, binary in zip(names, binaries):
    entries = code_hashes(binary)
    assert entries and all(len(entry) == 22 for entry in entries)
    if shutil.which('codesign'):
        result = subprocess.run(['codesign', '-d', '--verbose=4', str(directory/name)],
                                capture_output=True, text=True, check=True)
        expected = re.search(r'^CDHash=([0-9a-f]{40})$', result.stderr, re.M)[1]
        assert expected in [entry[:20].hex() for entry in entries]
    for malformed in (b'', binary[:40], b'not Mach-O'):
        try: code_hashes(malformed)
        except (ValueError, IndexError, struct.error): pass
        else: raise AssertionError('Malformed signature accepted')
original_entry = b'\x11'*20 + b'\x02\0'
original = struct.pack('<I', 1) + b'\0'*16 + struct.pack('<I', 1) + original_entry
result, count = build(original, binaries+binaries)
assert count == 2 and len(result) == 24+3*22
assert original_entry in [result[i:i+22] for i in range(24, len(result), 22)]
again, added = build(result, binaries)
assert added == 0 and result[20:] == again[20:]
assert cache_payload(result) == result
for malformed in (b'not DER', original[:-1], struct.pack('<I', 9)+original[4:]):
    try: build(malformed, binaries)
    except (ValueError, IndexError, struct.error): pass
    else: raise AssertionError('Malformed cache accepted')
print('Probe trust cache checks passed: codesign hash match, original entries preserved, duplicates and malformed input rejected')
