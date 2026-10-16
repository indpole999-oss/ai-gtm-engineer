"""Deterministic checks are not real pooler/isolated recovery acceptance."""
import importlib.util
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import ssl

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

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


@pytest.mark.parametrize('ca_pem', [None, 'synthetic-public-ca'])
def test_tls_sends_only_ssl_request_and_requires_trust_and_hostname(monkeypatch, ca_pem):
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
    def context(**kwargs):
        assert kwargs == ({'cadata': ca_pem} if ca_pem is not None else {})
        return Context()
    monkeypatch.setattr(probe.ssl, 'create_default_context', context)
    assert probe.tls_probe('8.8.8.8', probe.HOST, ca_pem) == 'verified'


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


def certificate(ca=True):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic public CA')])
    now = datetime.now(timezone.utc)
    return (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))


def test_explicit_ca_is_loaded_and_identical_for_both_hostnames(tmp_path, monkeypatch):
    data = certificate()
    path = tmp_path / 'public-ca.pem'
    path.write_bytes(data)
    pem, digest = probe.read_trust_anchor(path)
    assert digest == hashlib.sha256(data).hexdigest()
    context = ssl.create_default_context(cadata=pem)
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert len(context.get_ca_certs()) == 1
    dns(monkeypatch)
    monkeypatch.setattr(probe.socket, 'create_connection', lambda *args, **kwargs: Connection())
    calls = []
    def tls(address, hostname, ca_pem):
        calls.append((hostname, ca_pem))
        return 'verified' if hostname == probe.HOST else 'hostname_rejected'
    monkeypatch.setattr(probe, 'tls_probe', tls)
    result = probe.assess(path)
    assert result['status'] == 'PASS'
    assert result['trust_anchor_sha256'] == digest
    assert calls == [(probe.HOST, pem), (probe.WRONG_HOST, pem)]
    assert str(path) not in json.dumps(result) and pem not in json.dumps(result)
    assert result['actual_recovery_verified'] is False


@pytest.mark.parametrize('kind', ['private_key', 'malformed', 'oversized', 'missing', 'non_ca'])
def test_bad_trust_anchor_blocks_before_dns_or_connections(tmp_path, monkeypatch, kind):
    path = tmp_path / 'private-path-never-echoed.pem'
    if kind == 'non_ca':
        path.write_bytes(certificate(ca=False))
    elif kind != 'missing':
        path.write_bytes({'private_key': b'-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----',
                          'malformed': b'-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----',
                          'oversized': b'x' * (256 * 1024 + 1)}[kind])
    monkeypatch.setattr(probe.socket, 'getaddrinfo', lambda *args, **kwargs: pytest.fail('No DNS with bad trust anchor'))
    monkeypatch.setattr(probe.socket, 'create_connection', lambda *args, **kwargs: pytest.fail('No connection with bad trust anchor'))
    result = probe.assess(path)
    assert result['status'] == 'BLOCKED'
    assert result['blockers'] == ['explicit_public_ca_unavailable_or_invalid']
    assert 'secret' not in json.dumps(result) and str(path) not in json.dumps(result)
