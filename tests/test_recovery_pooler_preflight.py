"""Deterministic checks are not real pooler/isolated recovery acceptance."""
import importlib.util
import json
from pathlib import Path
import socket
import ssl

import pytest

spec = importlib.util.spec_from_file_location('pooler_preflight', Path(__file__).parents[1] / 'scripts/recovery_pooler_preflight.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def dns(monkeypatch, address='8.8.8.8'):
    def resolve(host, port, **kwargs):
        assert (host, port) == (probe.HOST, 5432)
        assert kwargs == {'family': socket.AF_INET, 'type': socket.SOCK_STREAM}
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, port))]
    monkeypatch.setattr(probe.socket, 'getaddrinfo', resolve)


def test_pass_never_asserts_project_or_recovery_isolation(monkeypatch):
    dns(monkeypatch)
    monkeypatch.setattr(probe.socket, 'create_connection', lambda *args, **kwargs: Connection())
    calls = []
    def tls(address, hostname):
        calls.append((address, hostname))
        return 'verified' if hostname == probe.HOST else 'hostname_rejected'
    monkeypatch.setattr(probe, 'tls_probe', tls)
    result = probe.assess()
    assert result['status'] == 'PASS' and all(result['checks'].values())
    assert calls == [('8.8.8.8', probe.HOST), ('8.8.8.8', probe.WRONG_HOST)]
    assert not any(result[key] for key in ('project_identity_verified', 'project_isolation_verified', 'host_isolation_verified', 'actual_recovery_verified'))
    assert '8.8.8.8' not in json.dumps(result)


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.1', '::1'])
def test_non_public_or_non_ipv4_dns_never_connects(monkeypatch, address):
    dns(monkeypatch, address)
    monkeypatch.setattr(probe.socket, 'create_connection', lambda *args, **kwargs: pytest.fail('No connection permitted'))
    assert probe.assess()['status'] == 'BLOCKED'


def test_network_failure_redacts_exception(monkeypatch):
    dns(monkeypatch)
    def fail(*args, **kwargs):
        raise OSError('private-environment-detail')
    monkeypatch.setattr(probe.socket, 'create_connection', fail)
    result = probe.assess()
    assert result['status'] == 'BLOCKED'
    assert 'private-environment-detail' not in json.dumps(result)


@pytest.mark.parametrize('positive,negative,status', [
    ('certificate_rejected', 'not_attempted', 'FAIL'),
    ('verified', 'verified', 'FAIL'),
    ('verified', 'certificate_rejected', 'FAIL'),
    ('verified', 'network_unavailable', 'BLOCKED'),
])
def test_certificate_failure_or_timeout_is_not_hostname_rejection(monkeypatch, positive, negative, status):
    dns(monkeypatch)
    monkeypatch.setattr(probe.socket, 'create_connection', lambda *args, **kwargs: Connection())
    monkeypatch.setattr(probe, 'tls_probe', lambda address, name: positive if name == probe.HOST else negative)
    assert probe.assess()['status'] == status


def test_tls_sends_only_ssl_request_and_requires_trust_and_hostname(monkeypatch):
    class Wire(Connection):
        def sendall(self, data):
            assert data == probe.SSL_REQUEST and len(data) == 8

        def recv(self, count):
            assert count == 1
            return b'S'
    class Context:
        verify_mode = ssl.CERT_REQUIRED
        check_hostname = True

        def wrap_socket(self, sock, server_hostname):
            assert server_hostname == probe.HOST
            return Connection()
    monkeypatch.setattr(probe.socket, 'create_connection', lambda address, timeout: Wire())
    monkeypatch.setattr(probe.ssl, 'create_default_context', lambda: Context())
    assert probe.tls_probe('8.8.8.8', probe.HOST) == 'verified'


@pytest.mark.parametrize('code,expected', [(62, 'hostname_rejected'), (19, 'self_signed_certificate_in_chain'), (20, 'certificate_rejected')])
def test_wrong_hostname_requires_specific_certificate_error(monkeypatch, code, expected):
    class Wire(Connection):
        def sendall(self, data):
            assert data == probe.SSL_REQUEST

        def recv(self, count):
            return b'S'
    class Context:
        verify_mode = ssl.CERT_REQUIRED
        check_hostname = True

        def wrap_socket(self, sock, server_hostname):
            error = ssl.SSLCertVerificationError('private-certificate-detail')
            error.verify_code = code
            raise error
    monkeypatch.setattr(probe.socket, 'create_connection', lambda address, timeout: Wire())
    monkeypatch.setattr(probe.ssl, 'create_default_context', lambda: Context())
    assert probe.tls_probe('8.8.8.8', probe.WRONG_HOST) == expected


def test_unsafe_tls_context_never_connects(monkeypatch):
    class Context:
        verify_mode = ssl.CERT_NONE
        check_hostname = False
    monkeypatch.setattr(probe.ssl, 'create_default_context', lambda: Context())
    monkeypatch.setattr(probe.socket, 'create_connection', lambda *args, **kwargs: pytest.fail('No unsafe TLS'))
    assert probe.tls_probe('8.8.8.8', probe.HOST) == 'unsafe_tls_context'
