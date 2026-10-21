"""Persistent, full-duplex local guest console for bounded development commands.

Use only the serial port of the intended experimental guest. Commands execute
with that guest's shell privileges. This does not install a shell or jailbreak.
"""
import re
import secrets
import socket
import threading
import time


class GuestConsole:
    def __init__(self, port=5556):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=10)
        self.socket.settimeout(0.5)
        self.condition = threading.Condition()
        self.command_lock = threading.Lock()
        self.buffer = bytearray()
        self.closed = False
        self.error = None
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while not self.closed:
                try:
                    data = self.socket.recv(16384)
                except socket.timeout:
                    continue
                if not data:
                    raise ConnectionError('Guest serial connection closed')
                with self.condition:
                    self.buffer.extend(data)
                    if len(self.buffer) > 2*1024*1024:
                        del self.buffer[:len(self.buffer)-1024*1024]
                    self.condition.notify_all()
        except OSError as error:
            with self.condition:
                self.error = error
                self.condition.notify_all()

    def run(self, command, timeout=60, interval=0.015):
        if '\n' in command or '\r' in command or '\x00' in command:
            raise ValueError('Use one explicit shell command line')
        if not 0 < timeout <= 180 or not 0.001 <= interval <= 0.05:
            raise ValueError('Invalid bounded command timing')
        with self.command_lock:
            token = 'IFN' + secrets.token_hex(8)
            expression = command + "; printf '\\n" + token + "_%s_END\\n' \"$?\"\n"
            pattern = re.compile(rb'[\r\n]+' + token.encode() + rb'_(\d+)_END[\r\n]+')
            with self.condition:
                self.buffer.clear()
                if self.error or self.closed:
                    raise ConnectionError('Guest serial connection unavailable')
            # Reader remains active while we transmit, including during boot-log floods.
            for byte in expression.encode():
                self.socket.sendall(bytes([byte]))
                time.sleep(interval)
            deadline = time.monotonic()+timeout
            with self.condition:
                while True:
                    found = pattern.search(self.buffer)
                    if found:
                        code = int(found[1])
                        output = bytes(self.buffer[:found.start()])
                        del self.buffer[:found.end()]
                        return code, output
                    if self.error or self.closed:
                        raise ConnectionError('Guest serial connection lost')
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        # No retries: the command may still be running inside the guest.
                        raise TimeoutError('Guest command unconfirmed; do not repeat blindly')
                    self.condition.wait(min(remaining, 0.5))

    def close(self):
        self.closed = True
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()
        with self.condition:
            self.condition.notify_all()
        self.reader.join(timeout=2)

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
