"""Make a new local restore attempt without overwriting a failed machine.

Only immutable firmware inputs are hard linked. Every mutable VM disk is new.
On Windows, mark new disks sparse before extending them to avoid allocating32GiB
of zeros through a Docker bind mount. Never use this to clone an installed VM.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil

DISKS = {'root': 32 << 30, 'firmware': 8 << 20, 'syscfg': 128 << 10,
         'ctrl_bits': 8 << 10, 'nvram': 8 << 10, 'effaceable': 4 << 10,
         'panic_log': 1 << 20, 'sep_nvram': 64 << 10, 'sep_ssc': 128 << 10}


def new_attempt(source, destination):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists() or destination == source:
        raise ValueError('Destination must be a new directory')
    required = ['restore.ipsw', 'ticket.shsh2', 'AppleSEPROM-Cebu-B1',
                'prepare.json', 'patched-ramdisk.im4p', 'InfernoData/root_ticket.der',
                'InfernoData/sep_root_ticket.der',
                'InfernoData/sep-firmware.n104.RELEASE.new.img4']
    for name in required:
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing regular firmware input: ' + name)
    if json.loads((source / 'prepare.json').read_text())['profile'] != 'iphone12,1-18A5351d-v1':
        raise ValueError('Unexpected preparation profile')
    restore = source / 'InfernoData/Restore'
    if restore.is_symlink() or any(p.is_symlink() for p in restore.rglob('*')):
        raise ValueError('Symlink in firmware input')
    destination.mkdir()
    (destination / 'InfernoData').mkdir()
    shutil.copytree(restore, destination / 'InfernoData/Restore', copy_function=os.link)
    shutil.copytree(source / 'qemu-data', destination / 'qemu-data', copy_function=os.link)
    for name in required:
        os.link(source / name, destination / name)
    for name, size in DISKS.items():
        with (destination / 'InfernoData' / name).open('xb') as stream:
            if os.name == 'nt':
                import msvcrt
                from ctypes import wintypes
                returned = wintypes.DWORD()
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                ioctl = kernel.DeviceIoControl
                ioctl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
                ioctl.restype = wintypes.BOOL
                if not ioctl(wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno())),
                             0x000900C4, None, 0, None, 0, ctypes.byref(returned), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                # The Windows CRT's _chsize_s writes zeros when extending.
                # Use the native EOF operation to preserve the sparse hole.
                seek = kernel.SetFilePointerEx
                seek.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
                seek.restype = wintypes.BOOL
                eof = kernel.SetEndOfFile
                eof.argtypes = [wintypes.HANDLE]
                eof.restype = wintypes.BOOL
                handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
                if not seek(handle, size, None, 0) or not eof(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                stream.truncate(size)
    (destination / 'new-attempt.json').write_text(json.dumps({
        'firmware_reused': True, 'all_mutable_disks_created_blank': True,
        'installed_machine': False}, indent=2))
    print('New blank disk set created; failed VM remains unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    new_attempt(args.source, args.destination)
