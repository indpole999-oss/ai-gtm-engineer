"""Credential-free real-target capability check on a standard public CI runner.

No fallback to shared poolers, paid networking, backups, keys or SQL. A missing
route is BLOCKED, not a successful negative firewall probe.
"""
import ipaddress
import json
import os
from pathlib import Path
import platform
import shutil

import recovery_host as host

REPOSITORY = 'indpole999-oss/ai-gtm-engineer'
BRANCH = 'refs/heads/codex/ai-gtm-engineer-v2-full-build'


def assess(env):
    result = {'status': 'BLOCKED', 'scope': 'real_target_host_capability',
              'target_project': host.TARGET, 'checks': {}, 'blockers': [],
              'tls_probe_attempted': False, 'host_isolation_verified': False,
              'actual_target_verified': False, 'actual_recovery_verified': False}
    if (env.get('GITHUB_REPOSITORY') != REPOSITORY or env.get('GITHUB_REF') != BRANCH
            or env.get('RUNNER_ENVIRONMENT') != 'github-hosted'
            or env.get('GITHUB_ACTIONS') != 'true'):
        result['blockers'].append('authorized_public_standard_runner_required')
        return result
    try:
        event = json.loads(Path(env['GITHUB_EVENT_PATH']).read_text())
        public = event['repository']['private'] is False
    except (KeyError, OSError, ValueError):
        public = False
    result['checks']['public_repository'] = public
    if not public:
        result['blockers'].append('no_cost_eligibility_unverified')
        return result
    supported = platform.system() == 'Linux' and os.geteuid() == 0 and all(
        shutil.which(name) for name in ('docker', 'nft', 'nsenter', 'ip'))
    result['checks']['linux_namespace_tools'] = bool(supported)
    if not supported:
        result['blockers'].append('linux_root_namespace_tools_required')
        return result
    try:
        addresses = host.addresses(host.HOST)
        if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
            raise ValueError('Invalid direct target')
    except (OSError, ValueError):
        result['blockers'].append('direct_recovery_dns_unavailable')
        return result
    result['checks']['direct_target_dns'] = True
    for family in (4, 6):
        targets = [value for value in addresses if ipaddress.ip_address(value).version == family]
        result['checks'][f'target_has_ipv{family}'] = bool(targets)
        if not targets:
            continue
        routes = []
        for address in targets:
            try:
                route = json.loads(host.command(['ip', '-j', f'-{family}', 'route', 'get', address]))
                routes.append(bool(route) and all(item.get('dev') and item.get('type', 'unicast') == 'unicast' for item in route))
            except (RuntimeError, ValueError):
                routes.append(False)
        result['checks'][f'host_ipv{family}_route'] = all(routes)
        if not all(routes):
            result['blockers'].append(f'no_host_ipv{family}_route_to_direct_recovery')
    if result['blockers']:
        return result
    # Only a reviewed immutable probe image is built. No application build/start.
    try:
        image = host.command(['docker', 'build', '-q', str(Path(__file__).parents[1] / 'recovery')]).strip()
        result['tls_probe_attempted'] = True
        result['namespace_evidence'] = host.run(image, '/etc/ssl/certs/ca-certificates.crt')
    except Exception:
        result['blockers'].append('isolated_probe_setup_or_execution_failed')
        return result
    # A runner's route and container firewall never attest independent host custody.
    result['blockers'].append('independent_recovery_host_custody_not_verified')
    return result


def main():
    result = assess(os.environ)
    result['evidence_sha256'] = host.digest(result)
    encoded = json.dumps(result, sort_keys=True)
    print(encoded)
    # Logs and summaries avoid new artifact/cache storage charges.
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write('### Actual recovery-target preflight\n\n```json\n' + encoded + '\n```\n')
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
