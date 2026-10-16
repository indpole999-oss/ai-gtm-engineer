# Negative-runtime and browser acceptance — 16 October 2026

Base source: `b036689d052a81e73e45876d81fc714cb4fdec8b`. Export contents did not change for this milestone. Changes are test tooling, evidence and case-study layout CSS.

## Actual n8n fail-closed acceptance: PASS

n8n 2.25.7 on the authorized Windows device. Six disposable, inactive test copies generated from canonical exports using `n8n/tests/build-runtime-cases.py`. Copies inject malformed or tampered data at the named stage; canonical exports remain unchanged. Imported into the existing disposable **pack runtime DB**, not the original n8n DB. Broker 5685, loopback 127.0.0.1, no credentials/action nodes.

| Case | Expected validation reason observed | CLI exit |
|---|---|---:|
| CRM whitespace identity | invalid lead event | 1 |
| Calendar missing timezone | explicit timezone | 1 |
| Calendar duration zero | explicit timezone and integer duration 1–480 required | 1 |
| Prospect missing source | evidence requires claim and source | 1 |
| Outreach sent-state tampering | unsafe state | 1 |
| Journey approval bypass | unsafe draft state | 1 |

PASS means the workflow **rejected** the injected unsafe input. The six runs intentionally have error status, not successful business execution. Every log matched the expected validation reason and did not report a missing workflow. SQLite read-only check: eight baseline success executions + six error executions; zero active workflows, zero credentials. No real messages or provider writes.

An initial import failed because Windows PowerShell Set-Content UTF8 added a BOM; no workflow execution acceptance was inferred from those failed import attempts. Rewrote JSON as UTF-8 without BOM, import retry exit 0, then all six cases produced their expected errors. Logs remain local; do not publish raw execution/session data.

### Reproduction

```sh
python portfolio/n8n/tests/build-runtime-cases.py --output /absolute/new-disposable-test-folder
```

The generator refuses an existing output directory. It writes `workflows.json` (UTF-8 without BOM) and `manifest.json`. Point N8N_USER_FOLDER to a disposable test DB, configure an unused broker port and loopback binding, then import that JSON and execute each manifest ID with `n8n execute --id=<id> --rawOutput`. Capture each run in `<id>.log`. Expected CLI exit: 1. Do not run after failed import. Finally:

```sh
node portfolio/n8n/tests/check-runtime-errors.cjs /absolute/disposable-log-folder
```

The checker validates reason matches, not just nonzero exit. It reads UTF-8 and Windows UTF-16LE logs and prints a sanitized summary. It is complementary to the DB status check, not a replacement for it.

## Actual browser acceptance: PASS after one fix

Used existing Windows Chrome through installed Playwright with a disposable browser context; no regular browser profile, existing account cookies or public browser tunnel. Tested a transferred local copy of portfolio source, not a new Render deployment.

Nine pages: home, work, writing, resources, about, and all four case studies. Widths: 390, 768 and 1440 CSS pixels; height 900. **27 page/width checks passed**: nonempty title, one H1, one main landmark, zero page-level horizontal overflow, zero detected unlabeled form controls and zero images missing alt attributes. No JavaScript page errors.

At all three widths, actual browser interactions passed: high-fit Aster score 100, approval in memory, switching account hides old output and disables approval, Ridgeway score 0, MiraCare score 100, refresh clears the result, first keyboard Tab focuses the skip link. Full-page homepage screenshots were generated on the authorized device for local review; no demo video was recorded.

### Defect found and fixed

Account-research case study overflowed at 390px: grid content expanded to about 430.67px and extended beyond the viewport. Code-block intrinsic width prevented the grid column from shrinking. `pages.css` now uses a zero-minimum flexible column and permits case-body shrinking; long code remains scrollable within its own panel. The expanded nine-page browser suite passed after this change. No blanket overflow hiding applied.

### Reproduce browser checks

```sh
node portfolio/tests/browser-acceptance.cjs /absolute/portfolio
```

Requires Playwright and a browser executable. Optional environment variables PLAYWRIGHT_MODULE and CHROME_PATH select existing installations without installing new packages. The script saves homepage screenshots to the supplied test copy. Use a disposable copy to avoid adding generated images to source.

## Scope and remaining acceptance

Basic browser/layout/semantics, not full WCAG certification, contrast analysis, screen-reader testing or all browser engines. Local file rendering does not prove hosting headers or HTTP behavior. Previously verified six live Render pages returned 200; this milestone did not deploy changes. All source changes stay on the portfolio branch. Clay, HubSpot and Calendar sandbox readbacks remain unverified; no production data or paid API access used.
