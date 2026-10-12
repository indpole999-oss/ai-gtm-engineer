# Authentication and workspace reliability — 2026-10-12

Baseline local/remote V2 commit: `0ff9f977b367dde39707c2ee1d43530c34101e3c`.
Reviewed auth provider, API client, login route, authenticated layout, workspace
provider, backend auth/workspace routers and their regression tests.

## Confirmed source defects

1. A profile endpoint failure, including 404/405 or unavailable network, set
   `authenticated` with a null user. Calling the original provider's refresh
   callback with a synthetic 404 reproduced `missing_profile_authorized=true`
   and `user=null`. Protected routes consequently lacked verified identity.
2. A pending sign-in could commit a token after logout. The original provider's
   sign-in/sign-out callbacks reproduced `late_login_restored_after_logout=true`
   and authenticated status after the delayed token response. Token comparison
   in profile loading did not fence the earlier login request itself.
3. An old HTTP 401 could sign out a newer session when its token string matched
   the old one (JWTs may be identical for same-user logins within one second).
   The API regression failed before the fix: expected `same-token`, actual null.
   A provider/API integration regression also reproduced an earlier profile 401
   clearing a newer verified refresh with the same token. Every auth transition
   now invalidates earlier API requests, including profile refreshes.

The callback reproductions used the actual old provider callbacks with isolated
hook/request adapters; no hosted account, password or token was used. A first
browser baseline attempt timed out during local Vite startup and is not counted
as a successful browser reproduction.

## Changes and security boundaries

- A tested auth-session lifecycle fences login, registration, profile refresh,
  logout, cross-tab identity changes and unmount with operation generations.
  Superseded operations cannot install a token, publish a stale profile or
  navigate successfully after their sign-in promise was rejected.
- Authentication requires a successful profile with identity and email fields.
  Missing, malformed or temporarily unavailable profiles hide customer routes
  and expose an explicit retry/back-to-sign-in state. Tokens may be retained for
  retry, but are never treated as verified identity. Invalid/expired profiles
  clear token, workspace and previous-user cache.
- API 401 session invalidation also requires the captured local session revision,
  preventing same-token races. Cross-tab auth events invalidate old requests.
- Workspace discovery cache and routed workspace state are scoped to verified
  user identity. Account transitions clear queries and remount workspace state;
  the stored workspace is restored only from the new account's authorized list.
- Backend login, active-user verification, membership filtering and tenant/role
  authorization were retained. No new backend defect was demonstrated.

Deterministic tests cover logout and late login, concurrent account requests,
same-token profile races, unavailable/malformed identity, cross-tab replacement
and logout, 401/403, and same-token stale API 401. Browser regressions cover
404/405/503 identity failures without customer UI, recovery, real local form
login to a second synthetic account, cache removal, account refresh persistence,
foreign-record 404 and cross-tab logout on desktop and mobile. Provider fixtures
remain explicitly synthetic and all databases are disposable local/CI targets.

## Scope of conclusions

Local frontend checks: **25 tests passed**, zero skipped, TypeScript passed and
targeted correctness lint passed with zero errors (three fast-refresh warnings).
Frontend build passed. Relevant backend auth/workspace tests: **18 passed**, zero
skipped. The combined local browser run passed desktop, including second-account
login/refresh/isolation; mobile timed out on an Outreach loading state before the
account-switch step. A serial mobile retry and exact committed CI results are
reported in the task response; no mobile PASS is inferred from the desktop run.

**Anil hosted mismatch: NOT REPRODUCED as a source root cause.** The controlled
staging browser showed a QA identity/workspace; no captured successful Anil
login/profile/workspace sequence links that observation to these defects. Anil's
existence and owner membership do not authenticate a browser. Staging still runs
older source, so these fixes are not deployed hosted acceptance evidence.

The remaining requirement is secure browser sign-in as Anil followed by a
successful identity response and an authorized Anil workspace visible in that
same controlled tab. No impersonation, password reset, hosted token creation,
customer membership changes, staging writes, deployment, migration or production
changes were done. Local browser tests use normal registration/login for clearly
synthetic accounts in disposable test databases.

Readiness remains **74/100 — NO-GO**, with zero extra points for these local
regressions. Existing checklist/generated-route edits and five untracked audits
are preserved and excluded from the intended commit. Final committed SHA, local
test results and exact post-push CI evidence are reported in the task response.
