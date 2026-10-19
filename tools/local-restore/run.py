"""Start a prepared local VM with private serial log and loopback VNC/QMP.

Restoration runs through the independent Python usbmux host and idevicerestore.
Normal boot never starts the restore client or attaches the restore ramdisk.
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import signal
import socket
import struct
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    root = Path('/vm')
    data = root / 'InfernoData'
    prepared = json.loads((root / 'prepare.json').read_text())
    if not (root / 'qemu-data/keymaps/en-us').is_file():
        raise ValueError('VNC keymaps missing from prepared VM inputs')
    logs = root / ('restore-logs' if args.restore else 'boot-logs')
    logs.mkdir(exist_ok=True)
    if args.restore and not (root / 'patched-ramdisk.im4p').is_file():
        raise ValueError('Patched restore ramdisk missing')
    machine = ['t8030', 'usb-uplink-type=inferno', 'usb-uplink-addr=unix:/tmp/iusb.sock',
        'trustcache=' + str(data / 'Restore' / prepared['trustcache']),
        'ticket=' + str(data / 'root_ticket.der'),
        'sep-fw=' + str(data / 'sep-firmware.n104.RELEASE.new.img4'),
        'sep-rom=' + str(root / 'AppleSEPROM-Cebu-B1'), 'kaslr-off=true',
        'boot-mode=' + ('enter_recovery' if args.restore else 'exit_recovery'),
        'disp-width=828', 'disp-height=1792', 'disp-scale=2']
    command = ['qemu-system-aarch64', '-L', '/vm/qemu-data', '-M', ','.join(machine),
        '-kernel', str(data / 'Restore' / prepared['kernel']),
        '-dtb', str(data / 'Restore' / prepared['device_tree']),
        '-append', 'tlto_us=-1 agm-genuine=1 agm-authentic=1 agm-trusted=1 serial=3 wdt=-1 launchd_unsecure_cache=1 -vm_compressor_wk_sw',
        '-smp', '7', '-m', '3G', '-accel', 'tcg,thread=multi',
        '-display', 'none', '-vnc', '0.0.0.0:0',
        '-qmp', 'tcp:0.0.0.0:4444,server=on,wait=off',
        '-chardev', 'socket,id=serial0,host=0.0.0.0,port=5555,server=on,wait=off,logfile=' + str(logs / 'guest-console.log'),
        '-serial', 'chardev:serial0',
        '-audiodev', 'none,id=quiet', '-global', 'driver=apple.mca,property=audiodev,value=quiet']
    for name in ('sep_nvram', 'sep_ssc'):
        command += ['-drive', f'file={data / name},if=pflash,format=raw']
    for name, nsid, nstype in [('root', 1, 1), ('firmware', 2, 2), ('syscfg', 3, 3),
                             ('ctrl_bits', 4, 4), ('effaceable', 6, 6), ('panic_log', 7, 8)]:
        command += ['-drive', f'file={data / name},format=raw,if=none,id={name}',
            '-device', f'nvme-ns,drive={name},bus=nvme-bus.0,nsid={nsid},nstype={nstype},logical_block_size=4096,physical_block_size=4096']
    command += ['-drive', f'file={data / "nvram"},if=none,format=raw,id=nvram',
        '-device', 'apple-nvram,drive=nvram,bus=nvme-bus.0,nsid=5,nstype=5,id=nvram,logical_block_size=4096,physical_block_size=4096']
    if args.restore:
        command += ['-initrd', str(root / 'patched-ramdisk.im4p'),
            '-global', 'driver=apple-smc,property=hold-reset,value=on']
    children = []
    handles = []
    def start(argv, name, **kwargs):
        handle = (logs / name).open('ab', buffering=0)
        handles.append(handle)
        proc = subprocess.Popen(argv, stdout=handle, stderr=subprocess.STDOUT, **kwargs)
        children.append(proc)
        return proc
    def stop(*unused):
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        raise SystemExit(130)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        start(['python3', '-u', '/app-source/netlab/muxd.py', '--usb', '/tmp/iusb.sock',
               '--socket', '/tmp/inferno-usbmuxd'], 'mux.log')
        deadline = time.monotonic() + 20
        while not Path('/tmp/iusb.sock').exists():
            if time.monotonic() > deadline or children[0].poll() is not None:
                raise RuntimeError('USB host failed to listen')
            time.sleep(0.1)
        qemu = start(command, 'qemu.log', cwd=root)
        (logs / 'host-status.json').write_text(json.dumps({'qemu_pid': qemu.pid,
            'restore_requested': args.restore, 'springboard_confirmed': False}))
        if args.restore:
            # The guest has to finish booting and USB enumeration first.
            # idevicerestore otherwise exits before a device can be discovered.
            deadline = time.monotonic() + 180
            ready = False
            while time.monotonic() < deadline and qemu.poll() is None:
                try:
                    with socket.socket(socket.AF_UNIX) as client:
                        client.settimeout(2)
                        client.connect('/tmp/inferno-usbmuxd')
                        payload = plistlib.dumps({'MessageType': 'ListDevices',
                            'ClientVersionString': 'Inferno local restore', 'ProgName': 'inferno-local'})
                        client.sendall(struct.pack('<IIII', len(payload) + 16, 1, 8, 1) + payload)
                        def receive(count):
                            result = b''
                            while len(result) < count:
                                chunk = client.recv(count - len(result))
                                if not chunk:
                                    raise ConnectionError('USB host disconnected')
                                result += chunk
                            return result
                        length, version, message, ident = struct.unpack('<IIII', receive(16))
                        if length < 16 or length > 1 << 20:
                            raise ValueError('Invalid usbmux reply length')
                        ready = bool(plistlib.loads(receive(length - 16)).get('DeviceList'))
                        if ready:
                            break
                except (OSError, ConnectionError):
                    pass
                time.sleep(1)
            if not ready:
                raise RuntimeError('Guest USB device did not enumerate; inspect USB and console logs')
            environment = dict(os.environ, USBMUXD_SOCKET_ADDRESS='UNIX:/tmp/inferno-usbmuxd')
            start(['idevicerestore', '--erase', '--restore-mode', '-i', '0x1122334455667788',
                   str(root / 'restore.ipsw'), '-T', str(data / 'root_ticket.der')],
                  'idevicerestore.log', env=environment, cwd=root)
        result = qemu.wait()
        raise RuntimeError(f'QEMU exited with status {result}; inspect private logs')
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    main()
