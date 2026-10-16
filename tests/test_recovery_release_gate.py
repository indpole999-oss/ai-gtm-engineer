import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("recovery_gate", Path(__file__).parents[1] / "scripts/recovery_release_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def complete():
    data = {k: True for k in gate.FIELDS}
    data.update(source_project=gate.SOURCE, source_revision="20261009_0015", postgres_major=17,
                archive_sha256="a"*64, target_project=gate.TARGET, inflight_count=0,
                runtime_session_count=0, candidate_sha="b"*40,
                fallback_sha="dee8e80ec59611ab362897537a6e9e42854cfb3e", fallback_revision="20261011_0016")
    data['isolation'] = {key: True for key in gate.ISOLATION_FIELDS}
    data['isolation'].update(host_id='approved-test-host', target_project=gate.TARGET,
                             policy_sha256='d'*64, deny_probe_sha256='e'*64)
    data['executor_inventory'] = [dict(kind=kind, instance_count=0, running_count=0,
                                      inspected=True, restart_blocked=True, evidence_sha256='f'*64)
                                  for kind in sorted(gate.EXECUTOR_KINDS)]
    return data


@pytest.mark.parametrize("field", sorted(gate.FIELDS))
def test_missing_evidence_cannot_pass(field):
    data = complete()
    del data[field]
    assert not all(gate.evaluate(data).values())


@pytest.mark.parametrize("target", [gate.SOURCE, "qjkcqdiznthffbqmltrr", "postgresql://secret@host/db", "", "isolated_target"])
def test_unsafe_restore_target_rejected(target):
    data = complete()
    data["target_project"] = target
    assert not gate.evaluate(data)["independent_target"]


def test_truthy_strings_and_boolean_counters_fail():
    data = complete()
    data.update(restore_approved="true", inflight_count=False)
    checks = gate.evaluate(data)
    assert not checks["restore_authorized"] and not checks["executors_quiescent"]


def test_candidate_is_not_its_own_fallback():
    data = complete()
    data["fallback_sha"] = data["candidate_sha"]
    assert not gate.evaluate(data)["compatible_artifacts"]


def test_manifest_output_is_redacted_and_never_claims_recovery(tmp_path, capsys):
    import json
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(complete()))
    assert gate.main([str(path)]) == 0
    output = capsys.readouterr().out
    assert gate.TARGET not in output and "a"*64 not in output
    assert json.loads(output)["actual_recovery_verified"] is False
    path.write_text('{"secret":"private-password"}')
    assert gate.main([str(path)]) == 1
    assert "private-password" not in capsys.readouterr().out


@pytest.mark.parametrize('field', sorted(gate.ISOLATION_FIELDS))
def test_missing_isolation_evidence_rejected(field):
    data = complete()
    del data['isolation'][field]
    assert not gate.evaluate(data)['isolation_evidence']


@pytest.mark.parametrize('field,value', [('provider_egress_denied', 'true'),
    ('default_deny', False), ('source_production_denied', False), ('credentials_target_only', False),
    ('tls_verified', False), ('target_project', gate.SOURCE), ('policy_sha256', ''), ('host_id', 'https://secret@host')])
def test_unrestricted_or_unbound_network_policy_rejected(field, value):
    data = complete()
    data['isolation'][field] = value
    assert not gate.evaluate(data)['isolation_evidence']


@pytest.mark.parametrize('kind', sorted(gate.EXECUTOR_KINDS))
def test_omitted_executor_class_rejected(kind):
    data = complete()
    data['executor_inventory'] = [row for row in data['executor_inventory'] if row['kind'] != kind]
    assert not gate.evaluate(data)['executors_quiescent']


@pytest.mark.parametrize('field,value', [('instance_count', True), ('instance_count', -1),
    ('running_count', 1), ('restart_blocked', False), ('inspected', 'true'), ('evidence_sha256', '')])
def test_live_or_unverified_executor_rejected(field, value):
    data = complete()
    data['executor_inventory'][0][field] = value
    assert not gate.evaluate(data)['executors_quiescent']


def test_duplicate_classes_and_unknown_fallback_rejected():
    data = complete()
    data['executor_inventory'][1] = dict(data['executor_inventory'][0])
    data['fallback_sha'] = 'c'*40
    checks = gate.evaluate(data)
    assert not checks['executors_quiescent'] and not checks['compatible_artifacts']


def test_duplicate_approval_fields_are_not_overwritten(tmp_path, capsys):
    path = tmp_path / 'manifest.json'
    path.write_text('{"restore_approved":false,"restore_approved":true}')
    assert gate.main([str(path)]) == 1
    assert 'metadata_readable' in capsys.readouterr().out


@pytest.mark.parametrize('field,value', [('fallback_revision', '20261009_0015'),
    ('fallback_0016_rehearsed', False), ('fallback_sha', '237818dd3ba815411f9d1eed1961fff1a5a047f1')])
def test_old_or_unrehearsed_fallback_rejected(field, value):
    data = complete()
    data[field] = value
    assert not gate.evaluate(data)['compatible_artifacts']


def test_nested_unknown_fields_and_truthy_ingress_flags_rejected():
    data = complete()
    data['isolation']['secret'] = 'synthetic-secret-only'
    data['write_ingress_frozen'] = 'true'
    checks = gate.evaluate(data)
    assert not checks['isolation_evidence'] and not checks['executors_quiescent']
