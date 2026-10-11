"""Credential-free PostgreSQL TLS/network probe. No application or restore code."""
import json
import signal
import socket
import ssl
import struct
import sys


def probe(config):
    address, port = config['address'], config['port']
    try:
        with socket.create_connection((address, port), timeout=2) as sock:
            if not config.get('tls'):
                return {'connected': True}
            sock.sendall(struct.pack('!II', 8, 80877103))  # PostgreSQL SSLRequest only.
            if sock.recv(1) != b'S':
                return {'connected': True, 'tls_verified': False}
            context = ssl.create_default_context(cafile='/opt/recovery/ca.crt')
            with context.wrap_socket(sock, server_hostname=config['hostname']):
                return {'connected': True, 'tls_verified': True}
    except ssl.SSLError:
        return {'connected': True, 'tls_verified': False}
    except OSError:
        return {'connected': False, 'tls_verified': False}


if __name__ == '__main__':
    if sys.argv[1:] == ['--idle']:
        signal.pause()  # No timers, listeners, workers, scheduler or integration imports.
    else:
        try:
            print(json.dumps(probe(json.load(sys.stdin)), sort_keys=True))
        except Exception:
            print(json.dumps({'probe_error': True}))
            sys.exit(1)
