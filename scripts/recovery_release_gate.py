"""Validate non-secret operator evidence metadata; never restore or read key/archive bytes.

This validates an evidence manifest, not infrastructure truth or authorization.
Do not include credentials, key material, connection URLs or archive contents.
"""
import argparse
import json
import re

SOURCE = "xhjkahbtckrrhuzamysr"
FORBIDDEN = {SOURCE, "qjkcqdiznthffbqmltrr"}
FIELDS = {"source_project", "source_revision", "postgres_major", "archive_sha256",
          "archive_integrity_verified", "backup_scope_verified", "original_key_custody_verified",
          "target_project", "target_empty_verified", "target_isolation_verified",
          "target_identity_verified", "inventory_complete", "old_executors_stopped",
          "restart_prevented", "inflight_count", "runtime_session_count", "providers_paused",
          "candidate_sha", "fallback_sha", "fallback_0016_rehearsed", "restore_approved",
          "release_approved"}


def sha(value, length):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value))


def evaluate(evidence):
    if not isinstance(evidence, dict) or set(evidence) - FIELDS:
        return {"metadata_schema": False}
    yes = lambda name: evidence.get(name) is True
    zero = lambda name: type(evidence.get(name)) is int and evidence[name] == 0
    target = evidence.get("target_project")
    return {
        "source_identity": evidence.get("source_project") == SOURCE,
        "source_revision": evidence.get("source_revision") == "20261009_0015",
        "postgres_17": type(evidence.get("postgres_major")) is int and evidence["postgres_major"] == 17,
        "archive_metadata": sha(evidence.get("archive_sha256"), 64)
            and yes("archive_integrity_verified") and yes("backup_scope_verified"),
        "original_key_custody": yes("original_key_custody_verified"),
        "independent_target": isinstance(target, str) and bool(re.fullmatch(r"[a-z0-9_-]{8,64}", target))
            and target not in FORBIDDEN and yes("target_empty_verified")
            and yes("target_isolation_verified") and yes("target_identity_verified"),
        "executors_quiescent": yes("inventory_complete") and yes("old_executors_stopped")
            and yes("restart_prevented") and zero("inflight_count") and zero("runtime_session_count"),
        "providers_paused": yes("providers_paused"),
        "compatible_artifacts": sha(evidence.get("candidate_sha"), 40)
            and sha(evidence.get("fallback_sha"), 40)
            and evidence.get("candidate_sha") != evidence.get("fallback_sha")
            and yes("fallback_0016_rehearsed"),
        "restore_authorized": yes("restore_approved"),
        "release_authorized": yes("release_approved"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="Non-secret evidence JSON only")
    args = parser.parse_args(argv)
    try:
        with open(args.manifest, encoding="utf-8") as stream:
            checks = evaluate(json.load(stream))
    except Exception:
        checks = {"metadata_readable": False}
    # No input values/paths/exceptions are echoed. No command execution follows.
    passed = all(checks.values())
    print(json.dumps({"checks": checks, "metadata_complete": passed,
                      "actual_recovery_verified": False}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
