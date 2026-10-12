"""Pinned shared-pooler IPv4/TLS check: no credentials, SQL or database startup.

This proves transport reachability only. The shared endpoint cannot establish
recovery-project identity, project-only egress, host isolation or recoverability.
Existing direct-target and sandbox gates remain mandatory and unchanged.
"""
import hashlib
import ipaddress
import json
import socket
import ssl
import struct
from datetime import datetime, timezone

HOST = 'aws-0-ap-southeast-2.pooler.supabase.com'
PORT = 5432
TARGET = 'tyvqriqbfjnimtzageoj'
WRONG_HOST = 'incorrect-hostname.invalid'
SSL_REQUEST = struct.pack('!II', 8, 80877103)


def tls_probe(address, hostname):
    context = ssl.create_default_context()
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


def assess():
    result = {'status': 'BLOCKED', 'scope': 'shared_pooler_transport_only',
              'host': HOST, 'port': PORT, 'requested_recovery_project': TARGET,
              'checks': {}, 'blockers': [], 'project_identity_verified': False,
              'project_isolation_verified': False, 'host_isolation_verified': False,
              'actual_recovery_verified': False}
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
    for address in addresses:
        try:
            with socket.create_connection((address, PORT), timeout=5):
                pass
        except OSError:
            result['checks']['tcp_connectivity'] = False
            result['blockers'].append('ipv4_tcp_unavailable')
            return result
        positive = tls_probe(address, HOST)
        # Only test the incorrect name after validating the genuine chain/name.
        negative = tls_probe(address, WRONG_HOST) if positive == 'verified' else 'not_attempted'
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


def main():
    try:
        result = assess()
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
