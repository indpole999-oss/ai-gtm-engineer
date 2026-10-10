# Workspace integration foundation

Connections are workspace-owned; the creating user remains attributable. Owners
and admins manage/test/revoke credentials; other members can read safe connection
metadata. Connection status is server-controlled, not a client assertion.

Supported contracts: Google Calendar OAuth, HubSpot private app/bearer tokens,
Salesforce authorized tokens plus a validated `*.my.salesforce.com` origin,
Gmail/Outlook authorized mailbox tokens, Resend, Serper, and Apollo API keys.
No arbitrary provider URL or deployment-global customer token is accepted.
Unsupported old UI providers have been removed from the connection picker.

Google Calendar has an interactive authorization-code flow with S256 PKCE. State
is random, hashed in the database, expires after ten minutes and is atomically
consumed before exchange. The encrypted verifier survives process restart.
Callbacks revalidate active user/workspace/admin membership before and after
exchange. Reconnect targets an explicit workspace-owned integration ID and
preserves the existing refresh token when Google does not issue another one.
Refresh tokens and expiries are persisted under a connection row lock.

The callback redirects to the server-configured FRONTEND_URL settings page without
putting tokens in URLs. Declined consent returns a failure message; invalid/expired
capabilities are rejected. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
GOOGLE_REDIRECT_URI, FRONTEND_URL, and a stable INTEGRATION_ENCRYPTION_KEY on staging
before a live smoke test. Never rotate the encryption key without a re-encryption
and recovery plan. No staging/live credentials were needed or used in unit tests.

All new credential writes are encrypted. Existing plaintext records remain a
manual production review item until reconnected/re-encrypted; do not expose them
through the Data API. Provider response bodies and exceptions are never returned
to customers or recorded in audit events. Audit records retain action, workspace,
connection, user and timestamp, even after the connection is deleted.

Gmail, Outlook and Salesforce currently use customer-supplied authorized tokens;
they require reconnect when expired. Interactive OAuth for these providers is not
implemented. Serper has no free identity probe in this implementation: saving a
key yields configured/unverified, not connected. Research execution may use it
only under the later plan/budget policy. No search credits are spent by health tests.

Google revoke calls the provider before clearing credentials. Other providers
support local disconnect and explicitly instruct the customer to revoke the
token in the provider console; local deletion never claims provider revocation.

Migration `20260922_0005` only adds connection metadata, OAuth attempts and audit
tables. It does not exchange tokens, contact a provider, or rewrite legacy data.
Retention cleanup for expired OAuth capabilities must preserve the audit trail
and be reviewed before production. Never log raw OAuth query strings.

Provider references used for the contracts:
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.hubspot.com/docs/api-reference/legacy/account/account-information/guide
- https://developer.salesforce.com/docs/platform/api-rest/guide/resources-limits.html

Validation uses injected fake OAuth/provider adapters, exercising actual API,
database, encryption, ownership and state transitions. Live provider credential
and consent-screen verification remains a final staging gate, not a claim made
by fake-provider tests.
