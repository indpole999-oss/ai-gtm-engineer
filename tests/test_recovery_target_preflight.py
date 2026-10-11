import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import recovery_target_preflight as preflight


def environment(tmp_path):
    event = tmp_path / 'event.json'
    event.write_text(json.dumps({'repository': {'private': False}}))
    return {'GITHUB_REPOSITORY': preflight.REPOSITORY, 'GITHUB_REF': preflight.BRANCH,
            'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
            'GITHUB_EVENT_PATH': str(event)}


def test_wrong_branch_never_probes(tmp_path, monkeypatch):
    env = environment(tmp_path)
    env['GITHUB_REF'] = 'refs/heads/main'
    monkeypatch.setattr(preflight.host, 'addresses', lambda _: (_ for _ in ()).throw(AssertionError('No probe')))
    assert preflight.assess(env)['blockers'] == ['authorized_public_standard_runner_required']


def test_private_repository_does_not_provision(tmp_path):
    env = environment(tmp_path)
    Path(env['GITHUB_EVENT_PATH']).write_text('{"repository":{"private":true}}')
    assert preflight.assess(env)['blockers'] == ['no_cost_eligibility_unverified']


def test_missing_ipv6_route_blocks_before_build_or_tls(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(preflight.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(preflight.shutil, 'which', lambda _: '/tool')
    monkeypatch.setattr(preflight.host, 'addresses', lambda _: ['2606:4700::1111'])
    calls = []
    def command(args):
        calls.append(args)
        raise RuntimeError('secret URL must never appear')
    monkeypatch.setattr(preflight.host, 'command', command)
    result = preflight.assess(environment(tmp_path))
    assert result['blockers'] == ['no_host_ipv6_route_to_direct_recovery']
    assert result['tls_probe_attempted'] is False
    assert result['actual_recovery_verified'] is False
    assert len(calls) == 1 and calls[0][0] == 'ip'
    assert 'secret' not in json.dumps(result)
