"""Create a separate boot trust cache for explicitly supplied signed test binaries.

Never overwrites the original Apple cache. Output contains original cache entries
and belongs with private VM files, not in the public source repository.
"""
import hashlib
from pathlib import Path
import struct
import uuid


def der_item(data, offset=0):
    start = offset
    tag = data[offset]; offset += 1
    length = data[offset]; offset += 1
    if length & 128:
        count = length & 127
        if not 1 <= count <= 4: raise ValueError('Unsupported DER length')
        length = int.from_bytes(data[offset:offset+count], 'big'); offset += count
    end = offset+length
    if end > len(data) or offset > end: raise ValueError('Truncated DER')
    return tag, data[offset:end], end


def cache_payload(data):
    if data[:4] == b'\x01\0\0\0': return data
    tag, sequence, end = der_item(data)
    if tag != 0x30 or end != len(data): raise ValueError('Expected raw cache or IM4P')
    children = []; offset = 0
    while offset < len(sequence):
        tag, child, offset = der_item(sequence, offset); children.append((tag, child))
    if len(children) < 4 or children[0][1] != b'IM4P' or children[1][1] not in (b'rtsc', b'trst') or children[3][0] != 4:
        raise ValueError('Unexpected trust cache IM4P')
    return children[3][1]


def code_hashes(data):
    if data[:4] != b'\xcf\xfa\xed\xfe': raise ValueError('Expected thin signed 64-bit Mach-O')
    count = struct.unpack_from('<I', data, 16)[0]
    if count > 1024: raise ValueError('Invalid command count')
    offset = 32; signature = None
    for _ in range(count):
        command, size = struct.unpack_from('<II', data, offset)
        if size < 8 or offset+size > len(data): raise ValueError('Invalid load command')
        if command == 0x1d:
            begin, length = struct.unpack_from('<II', data, offset+8)
            signature = data[begin:begin+length]
            if len(signature) != length: raise ValueError('Truncated signature')
        offset += size
    if signature is None or len(signature) < 12: raise ValueError('Missing signature')
    magic, length, count = struct.unpack_from('>III', signature)
    if magic != 0xfade0cc0 or length > len(signature) or count > 64: raise ValueError('Invalid SuperBlob')
    hashes = []
    for index in range(count):
        slot, begin = struct.unpack_from('>II', signature, 12+index*8)
        if slot != 0 and not 0x1000 <= slot <= 0x1005: continue
        magic, size = struct.unpack_from('>II', signature, begin)
        directory = signature[begin:begin+size]
        if magic != 0xfade0c02 or len(directory) != size or size < 40: raise ValueError('Invalid CodeDirectory')
        kind = directory[37]
        algorithm = {1: 'sha1', 2: 'sha256', 3: 'sha256', 4: 'sha384'}.get(kind)
        if not algorithm: raise ValueError('Unsupported code hash')
        hashes.append(hashlib.new(algorithm, directory).digest()[:20] + bytes([kind, 0]))
    if not hashes: raise ValueError('No CodeDirectory hashes')
    return hashes


def build(original, binaries):
    cache = cache_payload(original)
    version, = struct.unpack_from('<I', cache)
    count, = struct.unpack_from('<I', cache, 20)
    if version != 1 or len(cache) != 24+count*22: raise ValueError('Expected exact v1 cache')
    entries = {cache[offset:offset+22] for offset in range(24, len(cache), 22)}
    old = len(entries)
    for binary in binaries: entries.update(code_hashes(binary))
    entries = sorted(entries)
    result = struct.pack('<I', 1) + uuid.uuid4().bytes + struct.pack('<I', len(entries)) + b''.join(entries)
    return result, len(entries)-old


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('binaries', nargs='+', type=Path)
    args = parser.parse_args()
    result, count = build(args.original.read_bytes(), [p.read_bytes() for p in args.binaries])
    with args.output.open('xb') as output: output.write(result)
    print(f'Separate probe trust cache written; {count} explicit new code hashes; guest not booted')
