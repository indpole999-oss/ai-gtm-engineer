"""Validate non-secret operator evidence metadata; never restore or read key/archive bytes.

This validates an evidence manifest, not infrastructure truth or authorization.
Do not include credentials, key material, connection URLs or archive contents.
"""
import argparse
import json
import re

SOURCE = "xhjkahbtckrrhuzamysr"
TARGET = "tyvqriqbfjnimtzageoj"
FALLBACKS = {"dee8e80ec59611ab362897537a6e9e42854cfb3e", "0dd2e82df064bac2811f9f87e9aa0fc978620da9"}
EXECUTOR_KINDS = {"embedded_api", "standalone_worker", "api_writes", "inbound_webhooks", "schedulers", "render_deploys", "external_supervisors"}
ISOLATION_FIELDS = {"host_id", "target_project", "default_deny", "provider_egress_denied", "source_production_denied", "credentials_target_only", "tls_verified", "policy_sha256", "deny_probe_sha256"}
INVENTORY_FIELDS = {"kind", "instance_count", "running_count", "inspected", "restart_blocked", "evidence_sha256"}
FORBIDDEN = {SOURCE, "qjkcqdiznthffbqmltrr"}
FIELDS = {"source_project", "source_revision", "postgres_major", "archive_sha256",
          "archive_integrity_verified", "backup_scope_verified", "original_key_custody_verified",
          "target_project", "target_empty_verified", "target_isolation_verified",
          "target_identity_verified", "inventory_complete", "old_executors_stopped",
          "restart_prevented", "inflight_count", "runtime_session_count", "providers_paused",
          "candidate_sha", "fallback_sha", "fallback_0016_rehearsed", "restore_approved",
          "release_approved", "isolation", "executor_inventory", "write_ingress_frozen", "fallback_revision"}


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
        "independent_target": target == TARGET and yes("target_empty_verified")
            and yes("target_isolation_verified") and yes("target_identity_verified"),
        "isolation_evidence": isolation_complete(evidence.get("isolation")),
        "executors_quiescent": yes("inventory_complete") and yes("old_executors_stopped")
            and yes("restart_prevented") and zero("inflight_count") and zero("runtime_session_count")
            and yes("write_ingress_frozen") and inventory_complete(evidence.get("executor_inventory")),
        "providers_paused": yes("providers_paused"),
        "compatible_artifacts": sha(evidence.get("candidate_sha"), 40)
            and sha(evidence.get("fallback_sha"), 40)
            and evidence.get("candidate_sha") != evidence.get("fallback_sha")
            and evidence.get("fallback_sha") in FALLBACKS
            and evidence.get("fallback_revision") == "20261011_0016"
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
            checks = evaluate(json.load(stream, object_pairs_hook=unique_object))
    except Exception:
        checks = {"metadata_readable": False}
    # No input values/paths/exceptions are echoed. No command execution follows.
    passed = all(checks.values())
    print(json.dumps({"checks": checks, "metadata_complete": passed,
                      "actual_recovery_verified": False}, sort_keys=True))
    return 0 if passed else 1


def isolation_complete(value):
    if not isinstance(value, dict) or set(value) != ISOLATION_FIELDS:
        return False
    host = value.get("host_id")
    return (isinstance(host, str) and bool(re.fullmatch(r"[a-zA-Z0-9_-]{3,80}", host))
            and value.get("target_project") == TARGET
            and all(value.get(key) is True for key in
                    ("default_deny", "provider_egress_denied", "source_production_denied", "credentials_target_only", "tls_verified"))
            and sha(value.get("policy_sha256"), 64) and sha(value.get("deny_probe_sha256"), 64))


def inventory_complete(value):
    if not isinstance(value, list) or len(value) != len(EXECUTOR_KINDS):
        return False
    kinds = []
    for item in value:
        if not isinstance(item, dict) or set(item) != INVENTORY_FIELDS:
            return False
        count, running = item.get("instance_count"), item.get("running_count")
        if (type(count) is not int or count < 0 or type(running) is not int or running != 0
                or item.get("inspected") is not True or item.get("restart_blocked") is not True
                or not sha(item.get("evidence_sha256"), 64) or not isinstance(item.get("kind"), str)):
            return False
        kinds.append(item["kind"])
    return set(kinds) == EXECUTOR_KINDS and len(set(kinds)) == len(kinds)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate metadata field")
        result[key] = value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
