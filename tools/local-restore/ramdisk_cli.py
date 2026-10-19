"""Generate a Linux Swift CLI from the application's unchanged HFS+ editor.

Only the program-resource lookup and Linux Foundation compatibility are adapted.
The HFS+ implementation itself remains identical to the tested app source.
"""
import argparse
from pathlib import Path
import zipfile


def generate(app, ipa, output):
    output.mkdir(parents=True, exist_ok=True)
    guest = output / 'guest'
    guest.mkdir(exist_ok=True)
    with zipfile.ZipFile(ipa) as archive:
        for name in ('inferno_patcher', 'inferno_fs_patcher'):
            matches = [item for item in archive.namelist()
                       if item.startswith('Payload/') and item.endswith('/guest/' + name)]
            if len(matches) != 1:
                raise ValueError('Expected exactly one guest helper: ' + name)
            (guest / name).write_bytes(archive.read(matches[0]))
    source = (app / 'app/Sources/RestoreRamdisk.swift').read_text(encoding='utf-8')
    lookup = 'let bundle = (Bundle.main.resourceURL ?? Bundle.main.bundleURL).appendingPathComponent("guest")'
    if source.count(lookup) != 1:
        raise ValueError('Resource lookup changed; inspect source before adapting')
    source = source.replace(lookup, 'let bundle = URL(fileURLWithPath: CommandLine.arguments[3])')
    compatibility = '''
func L(_ format: String, _ arguments: CVarArg...) -> String {
    String(format: format, arguments: arguments)
}
func autoreleasepool<T>(invoking body: () throws -> T) rethrows -> T { try body() }
'''
    entry = '''
guard CommandLine.arguments.count == 4 else {
    fatalError("usage: ramdisk stock.im4p patched.im4p guest-directory")
}
try RestoreRamdisk.build(stock: URL(fileURLWithPath: CommandLine.arguments[1]),
    into: URL(fileURLWithPath: CommandLine.arguments[2]), note: { print($0) })
'''
    (output / 'main.swift').write_text(source + compatibility + entry, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    parser.add_argument('ipa', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    generate(args.app, args.ipa, args.output)
