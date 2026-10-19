"""Send one explicit QMP command to the local experiment; no implicit reset."""
import argparse
import json
import os
import socket


def execute(command, arguments=None):
    port = int(os.environ.get('INFERNO_QMP_PORT', '4444'))
    if not 1 <= port <= 65535:
        raise ValueError('Invalid local QMP port')
    with socket.create_connection(('127.0.0.1', port), timeout=15) as sock:
        stream = sock.makefile('rwb')
        if 'QMP' not in json.loads(stream.readline()):
            raise RuntimeError('Missing QMP greeting')
        def request(name, args, ident):
            value = {'execute': name, 'id': ident}
            if args is not None:
                value['arguments'] = args
            stream.write(json.dumps(value).encode() + b'\n')
            stream.flush()
            while True:
                line = stream.readline()
                if not line:
                    raise ConnectionError('QMP disconnected')
                reply = json.loads(line)
                if reply.get('id') != ident:
                    continue
                if 'error' in reply:
                    raise RuntimeError(reply['error'])
                return reply['return']
        request('qmp_capabilities', None, 0)
        return request(command, arguments, 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command')
    parser.add_argument('arguments', nargs='?', type=json.loads)
    args = parser.parse_args()
    print(json.dumps(execute(args.command, args.arguments)))
