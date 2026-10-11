import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("recovery_gate", Path(__file__).parents[1] / "scripts/recovery_release_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def complete():
    data = {k: True for k in gate.FIELDS}
    data.update(source_project=gate.SOURCE, source_revision="20261009_0015", postgres_major=17,
                archive_sha256="a"*64, target_project="isolated_target", inflight_count=0,
                runtime_session_count=0, candidate_sha="b"*40, fallback_sha="c"*40)
    return data


@pytest.mark.parametrize("field", sorted(gate.FIELDS))
def test_missing_evidence_cannot_pass(field):
    data = complete()
    del data[field]
    assert not all(gate.evaluate(data).values())


@pytest.mark.parametrize("target", [gate.SOURCE, "qjkcqdiznthffbqmltrr", "postgresql://secret@host/db", ""])
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
    assert "isolated_target" not in output and "a"*64 not in output
    assert json.loads(output)["actual_recovery_verified"] is False
    path.write_text('{"secret":"private-password"}')
    assert gate.main([str(path)]) == 1
    assert "private-password" not in capsys.readouterr().out
