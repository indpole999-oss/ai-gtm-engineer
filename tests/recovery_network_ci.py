"""Actual disposable Linux firewall test; never contacts a live project."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import recovery_host as host


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Disposable GitHub CI only')
    name = 'gaps-fixture-' + uuid.uuid4().hex
    network = name + '-net'
    result = {'status': 'BLOCKED', 'scope': 'synthetic_ci', 'actual_target_verified': False}
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            os.chmod(path, 0o755)
            host.command(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                          '-keyout', str(path / 'server.key'), '-out', str(path / 'ca.crt'),
                          '-subj', '/CN=' + host.HOST, '-addext', 'subjectAltName=DNS:' + host.HOST])
            os.chown(path / 'server.key', 999, 999)
            os.chmod(path / 'server.key', 0o600)
            host.command(['docker', 'network', 'create', '--internal', '--ipv6', '--subnet', '172.29.0.0/24',
                          '--subnet', 'fd73:ca17::/64', '--label', host.LABEL + '=true', network])
            host.command(['docker', 'run', '-d', '--name', name, '--network', network,
                          '-e', 'POSTGRES_PASSWORD=synthetic-ci-only', '--mount', f'type=bind,src={path},dst=/tls,readonly',
                          'postgres:17', '-c', 'ssl=on', '-c', 'ssl_cert_file=/tls/ca.crt', '-c', 'ssl_key_file=/tls/server.key'])
            for attempt in range(30):
                try:
                    host.command(['docker', 'exec', name, 'pg_isready', '-U', 'postgres'])
                    break
                except RuntimeError:
                    time.sleep(1)
            else:
                raise RuntimeError('Synthetic PostgreSQL unavailable')
            details = json.loads(host.command(['docker', 'inspect', name]))[0]
            address = details['NetworkSettings']['Networks'][network]['IPAddress']
            image = host.command(['docker', 'build', '-q', str(Path(__file__).parents[1] / 'recovery')]).strip()
            result = host.run(image, path / 'ca.crt', network, address)
            if not all(result['checks'].values()):
                raise RuntimeError('Isolation assertions failed')
    finally:
        for command in (['docker', 'rm', '-f', name], ['docker', 'network', 'rm', network]):
            try:
                host.command(command)
            except RuntimeError:
                result['cleanup_failed'] = True
        Path(args.evidence).write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
        print(json.dumps(result, sort_keys=True))
    return 0 if result.get('status') == 'PASS' and not result.get('cleanup_failed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
