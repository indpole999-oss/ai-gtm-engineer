"""Pinned shared-pooler IPv4/TLS check: no credentials, SQL or database startup.

This proves transport reachability only. The shared endpoint cannot establish
recovery-project identity, project-only egress, host isolation or recoverability.
Existing direct-target and sandbox gates remain mandatory and unchanged.
"""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
import struct
from datetime import datetime, timezone

from cryptography import x509

HOST = 'aws-0-ap-southeast-2.pooler.supabase.com'
PORT = 5432
TARGET = 'tyvqriqbfjnimtzageoj'
WRONG_HOST = 'incorrect-hostname.invalid'
SSL_REQUEST = struct.pack('!II', 8, 80877103)


def read_trust_anchor(path):
    # Bound the read and accept public CA certificates only. Use these exact
    # bytes for both the evidence hash and TLS, avoiding a second file read.
    with Path(path).open('rb') as stream:
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise ValueError('CA bundle too large')
    pem = data.decode('ascii')
    if not re.fullmatch(r'(?:\s*-----BEGIN CERTIFICATE-----[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----\s*)+', pem):
        raise ValueError('Public certificate PEM required')
    certificates = x509.load_pem_x509_certificates(data)
    if not certificates or not all(c.extensions.get_extension_for_class(x509.BasicConstraints).value.ca for c in certificates):
        raise ValueError('CA certificate required')
    return pem, hashlib.sha256(data).hexdigest()


def tls_probe(address, hostname, ca_pem=None):
    context = ssl.create_default_context(**({'cadata': ca_pem} if ca_pem is not None else {}))
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        return 'unsafe_tls_context'
    try:
        with socket.create_connection((address, PORT), timeout=5) as sock:
            sock.sendall(SSL_REQUEST)
            if sock.recv(1) != b'S':
                return 'tls_not_supported'
            # Close immediately after TLS: never send a StartupMessage, role,
            # project selector, password, query, restore or provider request.
            with context.wrap_socket(sock, server_hostname=hostname):
                return 'verified'
    except ssl.SSLCertVerificationError as error:
        if error.verify_code == 62:
            return 'hostname_rejected'
        if error.verify_code == 19:
            return 'self_signed_certificate_in_chain'
        return 'certificate_rejected'
    except ssl.SSLError:
        return 'tls_failed'
    except OSError:
        return 'network_unavailable'


def assess(ca_path=None):
    result = {'status': 'BLOCKED', 'scope': 'shared_pooler_transport_only',
              'host': HOST, 'port': PORT, 'requested_recovery_project': TARGET,
              'checks': {}, 'blockers': [], 'project_identity_verified': False,
              'project_isolation_verified': False, 'host_isolation_verified': False,
              'actual_recovery_verified': False}
    ca_pem = None
    if ca_path is not None:
        try:
            ca_pem, fingerprint = read_trust_anchor(ca_path)
            # Load/validate the trust store before any DNS or socket activity.
            context = ssl.create_default_context(cadata=ca_pem)
            if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
                raise ValueError('Unsafe TLS context')
        except Exception:
            result['blockers'].append('explicit_public_ca_unavailable_or_invalid')
            return result
        result['trust_anchor_sha256'] = fingerprint
        result['trust_source'] = 'explicit_public_ca'
        result['checks']['certificate_and_hostname_verification_required'] = True
    else:
        result['trust_source'] = 'platform_default_ca'
    try:
        addresses = sorted({row[4][0] for row in socket.getaddrinfo(
            HOST, PORT, family=socket.AF_INET, type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.IPv4Address(ip).is_global for ip in addresses):
            result['blockers'].append('public_ipv4_dns_required')
            return result
    except (OSError, ValueError):
        result['blockers'].append('ipv4_dns_unavailable')
        return result
    result['checks']['ipv4_dns'] = True
    result['ipv4_address_count'] = len(addresses)
    result['dns_addresses_sha256'] = hashlib.sha256(json.dumps(addresses).encode()).hexdigest()
    probes = []
    trust_args = (ca_pem,) if ca_pem is not None else ()
    for address in addresses:
        try:
            with socket.create_connection((address, PORT), timeout=5):
                pass
        except OSError:
            result['checks']['tcp_connectivity'] = False
            result['blockers'].append('ipv4_tcp_unavailable')
            return result
        positive = tls_probe(address, HOST, *trust_args)
        # Only test the incorrect name after validating the genuine chain/name.
        negative = tls_probe(address, WRONG_HOST, *trust_args) if positive == 'verified' else 'not_attempted'
        probes.append({'tls': positive, 'incorrect_hostname': negative})
    result['checks'].update(tcp_connectivity=True,
                            trusted_ca_hostname=all(p['tls'] == 'verified' for p in probes),
                            incorrect_hostname_rejected=all(p['incorrect_hostname'] == 'hostname_rejected' for p in probes))
    result['probes'] = probes  # Fixed enum outcomes only; no exception/peer data.
    if all(result['checks'].values()):
        result['status'] = 'PASS'
    elif any('network_unavailable' in p.values() for p in probes):
        result['blockers'].append('tls_probe_network_unavailable')
    else:
        result['status'] = 'FAIL'
        result['blockers'].append('tls_verification_or_hostname_negative_failed')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ca', help='Explicit public CA certificate PEM path; never a private key')
    args = parser.parse_args(argv)
    try:
        result = assess(args.ca)
    except Exception:
        # Exception text can contain arbitrary environment/provider details.
        result = {'status': 'BLOCKED', 'scope': 'shared_pooler_transport_only',
                  'blockers': ['preflight_unavailable'], 'actual_recovery_verified': False}
    result['observed_at_utc'] = datetime.now(timezone.utc).isoformat()
    result['evidence_sha256'] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    print(json.dumps(result, sort_keys=True))
    return {'PASS': 0, 'FAIL': 1, 'BLOCKED': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
