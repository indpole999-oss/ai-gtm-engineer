"""Create, probe, then destroy a credential-free Linux recovery container.

Requires an independently controlled Linux Docker host and root nft/nsenter.
Never mounts backup/key/app material, restores data or executes SQL/provider APIs.
The container is network-none until its namespace firewall is installed.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import uuid

TARGET = 'tyvqriqbfjnimtzageoj'
HOST = f'db.{TARGET}.supabase.co'
FORBIDDEN_HOSTS = ('db.xhjkahbtckrrhuzamysr.supabase.co', 'db.qjkcqdiznthffbqmltrr.supabase.co')
LABEL = 'gaps.recovery.disposable'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def addresses(host):
    return sorted({str(ipaddress.ip_address(row[4][0])) for row in socket.getaddrinfo(host, 5432, type=socket.SOCK_STREAM)})


def validate_addresses(allowed, denied, fixture=False):
    if not allowed or not denied or set(allowed) & set(denied):
        raise ValueError('Missing or overlapping endpoint identities')
    for value in allowed + denied:
        address = ipaddress.ip_address(value)
        if address.is_loopback or address.is_multicast or address.is_unspecified:
            raise ValueError('Unsafe endpoint')
        if not fixture and not address.is_global:
            raise ValueError('Real target requires public direct addresses')


def policy(allowed):
    # ip_address validation prevents nft syntax injection. No DNS/loopback/UDP allow.
    rules = ['table inet gaps_recovery {',
             'chain input { type filter hook input priority 0; policy drop; ct state established,related accept; }',
             'chain forward { type filter hook forward priority 0; policy drop; }',
             'chain output { type filter hook output priority 0; policy drop;']
    for value in allowed:
        address = ipaddress.ip_address(value)
        family = 'ip' if address.version == 4 else 'ip6'
        rules.append(f'{family} daddr {address} tcp dport 5432 counter accept')
    rules += ['counter drop comment "recovery_default_deny"', '}', '}']
    return '\n'.join(rules)


def command(args, input=None):
    result = subprocess.run(args, input=input, text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Host command failed')  # Never echo arbitrary command output.
    return result.stdout


def firewall(pid):
    return json.loads(command(['nsenter', '-t', str(pid), '-n', 'nft', '-j', 'list', 'table', 'inet', 'gaps_recovery']))


def dropped(snapshot):
    for item in snapshot['nftables']:
        rule = item.get('rule', {})
        if rule.get('comment') == 'recovery_default_deny':
            return next(part['counter']['packets'] for part in rule['expr'] if 'counter' in part)
    raise ValueError('Missing enforced drop counter')


def runtime_secure(value):
    host, config = value['HostConfig'], value['Config']
    return (host['ReadonlyRootfs'] is True and host['Privileged'] is False
            and not host.get('CapAdd') and not host.get('Devices') and not config.get('Healthcheck')
            and all(item.split('=', 1)[0] in {'PATH', 'LANG', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_SHA256', 'PYTHONDONTWRITEBYTECODE'} for item in config.get('Env', []))
            and host['CapDrop'] == ['ALL'] and host['RestartPolicy']['Name'] == 'no'
            and 'no-new-privileges' in host['SecurityOpt'] and not host.get('PortBindings')
            and config['User'] == '65534:65534'
            and config['Entrypoint'] == ['python', '/opt/recovery/probe.py', '--idle']
            and not config.get('Cmd')
            and len(value['Mounts']) == 1 and value['Mounts'][0]['Destination'] == '/opt/recovery/ca.crt'
            and value['Mounts'][0]['RW'] is False)


def run(image, ca, fixture_network=None, fixture_address=None):
    if platform.system() != 'Linux' or os.geteuid() != 0 or any(not shutil.which(tool) for tool in ('docker', 'nft', 'nsenter', 'ip')):
        raise RuntimeError('Linux root Docker/nft/nsenter prerequisite missing')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Image must be pinned to a locally built digest')
    ca = Path(ca).resolve(strict=True)
    if not ca.is_file():
        raise ValueError('Public CA certificate bundle required')
    certificate = ca.read_bytes()
    if b'PRIVATE KEY' in certificate or b'-----BEGIN CERTIFICATE-----' not in certificate:
        raise ValueError('Only public PEM certificates may be mounted')
    fixture = fixture_network is not None
    if fixture:
        if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('GITHUB_RUN_ID', '').isdigit():
            raise ValueError('Synthetic fixture mode is isolated CI only')
        network = json.loads(command(['docker', 'network', 'inspect', fixture_network]))[0]
        if not network['Internal'] or network.get('Labels', {}).get(LABEL) != 'true':
            raise ValueError('Fixture network must be independently internal and labeled')
        allowed, denied = [fixture_address], ['198.51.100.1', '203.0.113.1']
    else:
        allowed = addresses(HOST)
        denied = sorted({ip for host in FORBIDDEN_HOSTS for ip in addresses(host)})
    validate_addresses(allowed, denied, fixture)
    name = 'gaps-recovery-' + uuid.uuid4().hex
    own_network = None
    interface = None
    try:
        command(['docker', 'run', '-d', '--name', name, '--label', LABEL + '=true',
                 '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                 '--security-opt', 'no-new-privileges', '--restart', 'no', '--pids-limit', '8',
                 '--memory', '128m', '--cpus', '0.5', '--mount', f'type=bind,src={ca},dst=/opt/recovery/ca.crt,readonly', image])
        details = json.loads(command(['docker', 'inspect', name]))[0]
        if not runtime_secure(details):
            raise ValueError('Unexpected runtime privileges or mounts')
        pid = details['State']['Pid']
        command(['nsenter', '-t', str(pid), '-n', 'nft', '-f', '-'], policy(allowed))
        initial = firewall(pid)
        # Attach only after enforcing drop-all. No host firewall or other container is modified.
        if not fixture:
            own_network = name + '-net'
            command(['docker', 'network', 'create', '--ipv6', '--subnet', 'fd73:' + uuid.uuid4().hex[:4] + '::/64', '--label', LABEL + '=true', own_network])
        network = json.loads(command(['docker', 'network', 'inspect', fixture_network or own_network]))[0]
        if network['Driver'] != 'bridge':
            raise ValueError('Dedicated bridge required')
        # Docker forbids connecting a network-none container. Attach our own veth
        # only after nft is installed; never relax isolation to work around this.
        bridge = network.get('Options', {}).get('com.docker.network.bridge.name') or 'br-' + network['Id'][:12]
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}', bridge):
            raise ValueError('Unsafe bridge identity')
        interface = 'gr' + uuid.uuid4().hex[:10]
        peer = 'gp' + uuid.uuid4().hex[:10]
        command(['ip', 'link', 'add', interface, 'type', 'veth', 'peer', 'name', peer])
        command(['ip', 'link', 'set', peer, 'netns', str(pid)])
        command(['ip', 'link', 'set', interface, 'master', bridge])
        command(['ip', 'link', 'set', interface, 'up'])
        command(['nsenter', '-t', str(pid), '-n', 'ip', 'link', 'set', peer, 'up'])
        for item in network['IPAM']['Config']:
            subnet = ipaddress.ip_network(item['Subnet'])
            address = subnet.network_address + subnet.num_addresses - 3
            command(['nsenter', '-t', str(pid), '-n', 'ip', 'addr', 'add', f'{address}/{subnet.prefixlen}', 'dev', peer]
                    + (['nodad'] if subnet.version == 6 else []))
        gateways = [item.get('Gateway') or (str(ipaddress.ip_network(item['Subnet']).network_address + 1) if fixture else None)
                    for item in network['IPAM']['Config']]
        gateways = [gateway for gateway in gateways if gateway]
        # Routes are installed only inside the already-firewalled namespace.
        for gateway in gateways:
            family = '-6' if ipaddress.ip_address(gateway).version == 6 else '-4'
            if family == '-6':
                # No broad ICMPv6 exception: pin the independently inspected
                # dedicated bridge neighbor so only allowed TCP can leave.
                mac = Path('/sys/class/net', bridge, 'address').read_text().strip()
                if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac):
                    raise ValueError('Invalid dedicated bridge neighbor')
                command(['nsenter', '-t', str(pid), '-n', 'ip', '-6', 'neigh', 'replace', gateway,
                         'lladdr', mac, 'dev', peer, 'nud', 'permanent'])
            command(['nsenter', '-t', str(pid), '-n', 'ip', family, 'route', 'replace', 'default', 'via', gateway])
        if not any(ipaddress.ip_address(gateway).version == 6 for gateway in gateways):
            raise ValueError('IPv6 enforcement probes require an IPv6 route')
        def probe(address, port, hostname=HOST, tls=False, udp=False):
            value = {'address': address, 'port': port, 'hostname': hostname, 'tls': tls, 'udp': udp}
            return json.loads(command(['docker', 'exec', '-i', name, 'python', '/opt/recovery/probe.py'], json.dumps(value)))
        checks = {'runtime_restricted': True}
        checks['target_tls'] = all(probe(address, 5432, tls=True).get('tls_verified') is True for address in allowed)
        wrong_names = [probe(address, 5432, hostname='wrong.invalid', tls=True) for address in allowed]
        checks['wrong_certificate_name_rejected'] = all(value.get('connected') is True and value.get('tls_verified') is False for value in wrong_names)
        for label, address, port in [('staging_denied', denied[0], 5432), ('production_denied', denied[-1], 5432),
                                     ('providers_https_denied', '1.1.1.1', 443), ('dns_denied', '1.1.1.1', 53),
                                     ('other_target_port_denied', allowed[0], 443), ('ipv6_other_denied', '2606:4700:4700::1111', 443)]:
            before = dropped(firewall(pid))
            result = probe(address, port)
            checks[label] = result.get('connected') is False and dropped(firewall(pid)) > before
        before = dropped(firewall(pid))
        result = probe('1.1.1.1', 53, udp=True)
        checks['dns_udp_denied'] = result.get('connected') is False and dropped(firewall(pid)) > before
        # Recheck enforced rules after Docker network attachment, and single idle process.
        process_lines = command(['docker', 'top', name, '-eo', 'pid,args']).splitlines()
        checks['no_executors'] = len(process_lines) == 2 and 'probe.py --idle' in process_lines[1]
        final = firewall(pid)
        return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'scope': 'synthetic_ci' if fixture else 'recovery_target_tls_only', 'checks': checks,
                'policy_sha256': digest(initial), 'deny_probe_sha256': digest({'checks': checks, 'firewall': final}),
                'image_id': image,
                'target_tls_verified': not fixture and checks['target_tls'],
                'network_boundary_scope': 'container_namespace',
                # TLS cannot attest SQL project contents, credentials or host custody.
                'actual_target_verified': False, 'actual_recovery_verified': False}
    finally:
        cleanup_failed = False
        if interface and Path('/sys/class/net', interface).exists():
            try:
                command(['ip', 'link', 'delete', interface])
            except RuntimeError:
                cleanup_failed = True
        for cleanup in ([['docker', 'rm', '-f', name]] + ([['docker', 'network', 'rm', own_network]] if own_network else [])):
            try:
                command(cleanup)
            except RuntimeError:
                cleanup_failed = True
        if cleanup_failed:
            raise RuntimeError('Disposable resource cleanup incomplete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--ca', default='/etc/ssl/certs/ca-certificates.crt')
    parser.add_argument('--fixture-network')
    parser.add_argument('--fixture-address')
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    try:
        result = run(args.image, args.ca, args.fixture_network, args.fixture_address)
    except Exception:
        result = {'status': 'BLOCKED', 'actual_target_verified': False, 'actual_recovery_verified': False}
    Path(args.evidence).write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get('checks') and all(result['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
