# Disposable recovery execution boundary

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
