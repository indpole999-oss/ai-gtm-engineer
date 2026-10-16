# Recovery Session Pooler IPv4 preflight — 2026-10-12

User-verified dashboard endpoint: `aws-0-ap-southeast-2.pooler.supabase.com:5432`.
Requested recovery project: `tyvqriqbfjnimtzageoj`. Baseline remote/local V2 HEAD:
`24d8695a80366205c3f46163cb9b38aed72098ed`.

Executed `python scripts/recovery_pooler_preflight.py` with no credentials. The
only protocol payload is PostgreSQL's eight-byte SSLRequest; TLS closes before
any StartupMessage, project selector, authentication or SQL. No staging or
production endpoint was contacted and no live configuration was changed.

| Check | Actual result |
| --- | --- |
| IPv4 DNS | PASS: three public IPv4 addresses resolved |
| TCP 5432 | PASS: all three accepted TCP connections |
| Trusted certificate and correct hostname | FAIL: all three rejected with OpenSSL verification code 19, self-signed certificate in chain |
| Incorrect TLS hostname rejection | BLOCKED: not attempted after the valid-host trust check failed; a trust-chain failure cannot count as hostname rejection |
| Project identity/isolation and recovery | UNVERIFIED: shared-pooler transport cannot prove any of these |

Final observation: `2026-10-12T04:50:17.863672+00:00`. Redacted evidence SHA256:
`a905abdf0d751672507b9252319b8bdd796848f084cb4e5451672fdc78dcc116`.
The local ignored evidence file is `.venv/pooler-ipv4-preflight.json`.
Addresses are represented by a hash rather than printed. Exceptions and peer
certificate contents are never printed.

The platform TLS context had certificate verification required, hostname
checking enabled and 57 CA certificates. A bounded diagnostic also tried the
already-installed Mozilla/certifi bundle against one resolved address: code 19
again. No certificate was fetched from an unverified handshake and trusted; no
validation was disabled. These observations do not determine whether the
untrusted chain originates at the endpoint or an intervening network layer.

Focused tests: **14 passed, zero skipped, 0.10 seconds**. They verify pinned
IPv4-only DNS, public-address restrictions, credential-free SSLRequest payload,
required trust/hostname settings, specific hostname-error classification,
network-failure redaction and false project/recovery-isolation flags even when
the transport check passes. Existing recovery scripts remain unchanged.

Next prerequisite for completing TLS acceptance is an independently authenticated
public CA bundle valid for this observed pooler chain, or a supported execution
environment whose trusted CA store validates the endpoint. Do not trust an
unverified peer certificate or disable verification. Once valid-host verification
passes, run the incorrect-hostname negative check with the same trusted roots.

Even a successful shared-pooler TLS check does not clear the independent recovery
host/egress-isolation gate: a shared IP/port is not a project-only destination.
Original backup integrity, original-key custody, separately authorized isolated
restore, compatible fallback rehearsal, and executor/restart-prevention evidence
remain required. None were attempted in this task. Readiness remains **74/100,
NO-GO; zero connectivity points awarded**. No full CI or infrastructure research
was repeated; only the focused tests and bounded endpoint checks were run.

## Explicit Supabase CA follow-up — PASS

The user supplied the public CA downloaded from the recovery project's Database
Settings. The file contains one CA certificate and no private key. It remains
outside the repository; its bytes and local path are not in emitted evidence.
CA SHA256: `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`.

`python scripts/recovery_pooler_preflight.py --ca <downloaded-public-CA-path>` now
accepts this explicitly selected trust anchor. Only bounded public certificate
PEM is accepted, with CA BasicConstraints required. Invalid, missing, oversized,
non-CA or private-key input blocks before DNS/socket activity. The same loaded
bytes supply both TLS handshakes and the evidence hash, without rereading the
file. Certificate verification is CERT_REQUIRED and hostname checking stays on.

Actual observation `2026-10-12T04:58:28.066420+00:00`: **PASS**, all three IPv4
addresses passed TCP and correct-host trusted certificate/hostname verification.
All three incorrect-hostname handshakes failed specifically with verification
code 62 (hostname mismatch). No authentication/StartupMessage, project selector,
SQL or credentials were sent. This supersedes the preceding TLS trust blocker
for this explicitly supplied CA; the platform-default trust result is retained
as historical evidence.

Redacted evidence SHA256:
`4ba833a7ac14d0720b4a3532adb64d8291836ecd506164649c60cf1900932fc3`.
Ignored local evidence: `.venv/pooler-explicit-ca-preflight.json`.
Focused regression suite: **21 passed, zero skipped, 0.21 seconds**. An initial
run had six temporary-directory setup permission errors; the workspace-local
temporary-directory rerun passed all tests. No broad CI was manually rerun.

This clears only shared-pooler TLS trust acceptance. Project identity, exclusive
project egress, host isolation and actual recovery remain unverified and false
in the evidence. Backup/key custody, authorized restore, fallback and release
shutdown gates remain outstanding. Score stays **74/100; NO-GO**, with no points
awarded for this TLS result. No restore, migration, deployment or live-service
modification occurred.
