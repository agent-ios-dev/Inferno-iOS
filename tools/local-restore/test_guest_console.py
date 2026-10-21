"""Exercise real sockets with echoed commands, split replies and log traffic."""
import re
import socket
import threading
import time
import unittest
from guest_console import GuestConsole


class ConsoleTest(unittest.TestCase):
    def test_full_duplex_echo_and_split_reply(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0)); listener.listen()
        port = listener.getsockname()[1]
        errors = []

        def guest():
            try:
                with listener.accept()[0] as connection:
                    connection.settimeout(5)
                    for code in (0, 7):
                        # Logs are produced before the line has finished arriving.
                        connection.sendall(b'boot log\r\n'*4000)
                        line = b''
                        while not line.endswith(b'\n'):
                            data = connection.recv(7)
                            if not data: raise ConnectionError('Missing command')
                            line += data
                        connection.sendall(line)  # echo must not count as a result
                        token = re.search(rb'IFN[0-9a-f]{16}', line)[0]
                        response = b'\r\n' + token + b'_' + str(code).encode() + b'_END\r\n'
                        for byte in response:
                            connection.sendall(bytes([byte])); time.sleep(.001)
            except Exception as error:
                errors.append(error)
            finally:
                listener.close()

        worker = threading.Thread(target=guest); worker.start()
        with GuestConsole(port) as console:
            self.assertEqual(console.run('echo one', timeout=5, interval=.001)[0], 0)
            self.assertEqual(console.run('echo two', timeout=5, interval=.001)[0], 7)
            with self.assertRaises(ValueError): console.run('one\ntwo')
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])

    def test_echo_without_execution_times_out(self):
        listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen()
        port = listener.getsockname()[1]
        def guest():
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                line = b''
                while not line.endswith(b'\n'): line += connection.recv(128)
                connection.sendall(line)
                time.sleep(.4)
            listener.close()
        worker = threading.Thread(target=guest); worker.start()
        with GuestConsole(port) as console:
            with self.assertRaises(TimeoutError): console.run('echo test', timeout=.1, interval=.001)
        worker.join(timeout=3)


if __name__ == '__main__': unittest.main()
