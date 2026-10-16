# Disposable recovery execution boundary

Latest real-target capability attempt and conditional release authorization are
recorded in [the critical-path evidence](V2_CONTROLLED_RELEASE_CRITICAL_PATH_2026_10_11.md).
The no-cost public Linux runner has no IPv6 route to the real recovery project.
The evidence contract now distinguishes target TLS from full database identity:
`actual_target_verified` remains false until independent identity evidence exists.

Readiness remains **74/100, NO-GO**. No protected archive, original key, restore,
live database modification, provider execution or staging service change is authorized.

`scripts/recovery_host.py` creates a short-lived, credential-free Linux Docker
container, installs an nftables inet firewall in its network namespace before
network attachment, probes and destroys it. This is an execution sandbox on an
independently controlled dedicated host; it does not provision a cloud VM or
restrict a host administrator/Docker daemon. It does not fence deployed workers.
No application source, backup, key, database credentials, published ports,
scheduler, webhook listener or restart policy is installed. Only the public CA
certificate bundle is mounted. The immutable image ID must come from the reviewed
`recovery/Dockerfile` build context, never the repository root or an arbitrary image.

Required host: independently protected disposable Linux machine, root namespace
administration, Docker, nftables, nsenter, iproute2, IPv4/IPv6 routing and trusted
public CA certificates. Local Windows verification is BLOCKED: Docker unavailable
and WSL not installed. No host has been provisioned against the real project.

After separate host provisioning authorization, the credential-free verification
commands are:

```sh
docker build -q recovery
sudo python3 scripts/recovery_host.py --image sha256:<reviewed-build-image-id> \
  --ca /etc/ssl/certs/ca-certificates.crt --evidence recovery-network-evidence.json
```

The script pins direct DNS addresses for `db.tyvqriqbfjnimtzageoj.supabase.co`
and permits only TCP 5432 to those addresses. DNS resolution occurs on the control
host, before attachment. Overlap with resolved staging/production addresses fails
closed. No connections to staging or production leave the namespace: negative
tests require an observed firewall drop counter increase. All other ports,
addresses, UDP, DNS and provider HTTPS traffic are dropped. Both IP families have
default-drop policies. Required IPv6 transport that cannot complete under this
policy is BLOCKED; operators must not broaden rules to make a test pass.

TLS uses PostgreSQL SSLRequest only, trusted CA verification and the exact recovery
hostname. No login or SQL is executed. TLS proves endpoint certificate identity;
it does not prove SQL project contents, permissions or recovery compatibility.
Errors redact command output and produce BLOCKED. Unsuccessful probes produce
FAIL. Missing drop counters never count as PASS. Evidence hashes cover actual
kernel rule snapshots and results; they are integrity fingerprints, not signed
attestations. The approving operator must protect evidence and retain CI artifacts.

The isolated CI job uses a generated disposable certificate and PostgreSQL 17 on
an internal Docker bridge, with no host ports. Its synthetic endpoint shares the
expected certificate hostname but **is not the Supabase project**. CI firewall
and TLS acceptance is synthetic only; `actual_target_verified` and
`actual_recovery_verified` remain false. It cannot earn hosted recovery points.

Remaining prerequisites for a restore rehearsal:

1. Approve provisioning an independently controlled dedicated host and verify its
   control-plane/administrator boundary, both IP families and cleanup ownership.
2. Run real target certificate/network probes and retain non-secret evidence.
3. Approve read-only SQL identity/emptiness/permissions verification using a
   target-only role; this tool deliberately has no credentials or SQL client.
4. Independently verify protected archive inventory, integrity, original-key
   custody and PostgreSQL 17 restore compatibility. No access was performed here.
5. Separately approve protected material access and the exact isolated restore
   procedure. This probe-only image is not a restore runner. Any expanded runner
   needs another security review and the same namespace firewall tests.
6. Complete the existing migration/fallback, stopped-executor inventory and hosted
   customer acceptance gates. No synthetic test substitutes for those gates.

Docker runtime references: https://docs.docker.com/engine/containers/run/ and
https://docs.docker.com/engine/network/drivers/none/.

## Executed evidence

On code commit `af6a42be5e4461a024c373eb3b760d7ed784c66b`, the
[Linux CI isolation job](https://github.com/indpole999-oss/ai-gtm-engineer/actions/runs/38138376870/job/114466883209)
passed all 12 checks: target TLS, wrong hostname, untrusted CA, runtime restrictions,
no executors, staging/production address substitutes, provider HTTPS, other target
port, TCP DNS, UDP DNS and IPv6 denial. Negative address probes used reserved
synthetic addresses, never live staging or production endpoints. Every negative
network probe required an actual kernel drop-counter increase.

Non-secret evidence fingerprints from this run:

- Policy: `cff5595dfa764105825abeb92961b38a60d4263c22f94238bacb7ec10cd00bef`
- Denial probes: `bdd04dddde3c4c90e17f738d920b3280ce0be3f78b89a1d6f6a785539583dd10`
- Untrusted certificate control: `0d893353ca4ae1a22e0d9394c2d907073d9624954707eca68ae6758be3f89e05`
- Executed image: `sha256:9bdfd8d43390bd76cdfbe745ff7768cebf67b1f229cbcb9eac3ed0c71bf588d5`

The result explicitly records `scope=synthetic_ci`, `actual_target_verified=false`
and `actual_recovery_verified=false`. Initial CI failures in Docker network-none
attachment, missing internal IPv6 routes and process-inventory formatting were
reproduced and corrected; no failed attempt counted as acceptance. Local pure
regressions passed 81/81; local firewall execution remained BLOCKED.
