# Early Access acceptance evidence

## Scope — 2026-10-03

Baseline `5aecd6d` CI run `37029464204` passed all jobs. Application `38edc63`
is deployed to both existing Free staging services. This continuation exercises
remaining browser permission/recovery gates without repeating the completed
backend journey or calling hosted AI. Main and production remain untouched.

## Browser authorization and recovery matrix

The following results use the real V2 frontend/API with a disposable local SQLite
database, two synthetic users and two synthetic workspaces. Inherited provider
credentials and dotenv files are excluded. Hosted AI and workers are disabled.
This is local browser evidence, not live PostgreSQL or external-provider evidence.
Existing CI separately covers PostgreSQL isolation and migration/restore behavior.

| Scenario | Result |
| --- | --- |
| Admin switches Alpha → viewer Beta | PASS: Alpha prospect disappears, only Beta prospect is shown; create controls disappear. |
| Refresh in Beta | PASS: authorized Beta selection and viewer restrictions restore. |
| Owner/admin operational inventory | PASS: shown for Alpha admin, absent for Beta viewer. |
| Downgrade open Alpha page from admin to viewer | PASS: membership polling removes admin inventory and updates role without reload. |
| Revoke active workspace membership | PASS: routed view is removed; only the other authorized workspace is offered. |
| All actor memberships revoked | PASS: no-workspace screen, no customer data rendered. |
| Back to sign in from no-workspace screen | Initially FAIL: active token redirected user back to dashboard. Fixed by invoking existing sign-out/cache clearing; browser now reaches Sign in. |
| Different user signs in after recovery | PASS: Synthetic Owner identity loads; Synthetic Actor is absent. |
| Ordinary logout and direct protected-route navigation | PASS: Sign in shown; private page does not render. |
| Prospect search has zero matches | Initially blank; fixed with an explicit no-match state and Clear search. Browser confirms account returns on clear. |

Role updates were made only to the disposable fixture database. No real staging
memberships, accounts, roles, credentials or customer records were modified.

## Reused hosted-staging evidence

At `38edc63`: real sign-in; authorized workspace restoration; published Brain
visible; existing synthetic guided plan restores after refresh; approval remains
unchecked/disabled; execution selection shows its associated approved plan;
unsaved edits block switching/approval and can be discarded. Owner inventory and
manual refresh work. Desktop 1280px and mobile 390px show no horizontal overflow.
The mobile workspace control is present. Both services report live; health and
readiness returned 200. Details and deploy IDs are in V2_EARLY_ACCESS_BACKLOG.md.

## Primary release journey

| Stage | Acceptance status |
| --- | --- |
| Login → workspace | PASS in hosted staging; additional user/role recovery proven locally. |
| Company Brain | Published version visible in staging; creation/version/publication covered by existing API tests. |
| Goal → guided plan → review → refresh | PASS in staging with synthetic draft. This is a template, not an AI-generated plan. |
| Real AI planning and research | BLOCKED: hosted AI explicitly paused; no live model quality claim. |
| Approval → durable execution → evidence/qualification | Existing fake-provider API journey passes; hosted execution deliberately not exercised. |
| Personalized outreach draft → review | Existing synthetic API journey passes; real-model/browser evidence remains open. |
| Delivery → inbound reply → calendar → CRM | Fake-provider API evidence only. Live writes disabled; dedicated provider implementation/authorization and contract tests required. |
| Outcomes → gaps → next approved cycle | Existing continuous fake-provider API journey passes; live journey remains open. |

## Release decision

**HOLD Early Access release acceptance.** The available UI and offline acceptance
work is progressing, but live model/provider quality, worker operational rehearsal,
live PostgreSQL multi-user browser validation and privacy/retention decisions
remain open. No real delivery, live CRM/calendar readiness or production readiness
is implied. Keep `GTM_HOSTED_AI_ENABLED=false` and `EMBEDDED_EXECUTION_WORKER=false`.

No retention duration is approved for evidence, inbox, audit or backups. No purge
or destructive deletion is introduced. See V2_PRODUCTION_READINESS.md and
V2_STAGING_VALIDATION.md for the remaining release decisions and integration setup.
