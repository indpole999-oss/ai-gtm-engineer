"""Pure checks do not count as firewall enforcement evidence."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('recovery_host', Path(__file__).parents[1] / 'scripts/recovery_host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


@pytest.mark.parametrize('allowed,denied', [([], ['8.8.8.8']), (['8.8.8.8'], []),
    (['8.8.8.8'], ['8.8.8.8']), (['127.0.0.1'], ['8.8.8.8']),
    (['10.1.1.1'], ['8.8.8.8']), (['::'], ['8.8.8.8']), (['1; accept'], ['8.8.8.8'])])
def test_reject_unsafe_targets(allowed, denied):
    with pytest.raises(ValueError):
        host.validate_addresses(allowed, denied)


def test_policy_has_no_general_output_allow():
    value = host.policy(['8.8.8.8', '2606:4700::1111'])
    assert value.count('policy drop') == 3
    assert value.count('tcp dport 5432 counter accept') == 2
    output = value.split('chain output')[1]
    assert 'established' not in output
    assert 'udp' not in output
    assert 'recovery_default_deny' in output


def test_missing_supported_host_fails_before_commands(monkeypatch):
    monkeypatch.setattr(host.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(host, 'command', lambda *args: pytest.fail('must not execute'))
    with pytest.raises(RuntimeError, match='prerequisite'):
        host.run('sha256:' + 'a' * 64, 'unused')


def test_missing_firewall_counter_is_not_evidence():
    with pytest.raises(ValueError):
        host.dropped({'nftables': []})
