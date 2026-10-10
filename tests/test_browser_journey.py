"""Opt-in real Chromium -> frontend -> HTTP API -> disposable SQLite journey.

Run RUN_BROWSER_E2E=1 python -m pytest -q tests/test_browser_journey.py.
Only external boundaries use deterministic fixtures; never targets hosted staging.
"""
import os
import shutil
import socket
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import uvicorn
from backend.main import app
from backend import research_readiness
from test_research import fake_research  # noqa: F401
from test_outreach import provider, post, get_message  # noqa: F401
from test_workspace_security import signup
from test_company_brain import PROFILE
from test_outcomes import run
from test_inbox import ingest, event

pytestmark = pytest.mark.skipif(os.environ.get("RUN_BROWSER_E2E") != "1", reason="opt-in local browser journey")
ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def browser_evidence(directory):
    state = {}
    try:
        yield state
    except Exception:
        if "page" in state:
            state["page"].screenshot(path=str(directory / "failure.png"), full_page=True)
            (directory / "failure.html").write_text(state["page"].content(), encoding="utf-8")
        raise
    finally:
        if "context" in state:
            state["context"].tracing.stop(path=str(directory / "journey.zip"))


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize("viewport", [(1280, 900), (390, 844)], ids=["desktop", "mobile"])
def test_browser_customer_journey(client, fake_research, provider, monkeypatch, tmp_path, viewport):
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    assert os.environ["APP_ENV"] == "test"
    monkeypatch.setenv("GTM_HOSTED_AI_ENABLED", "false")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ-API-KEY", raising=False)
    async def readiness():
        return {"provider": "deterministic-test", "state": "model_available", "can_attempt": True,
                "message": "Synthetic fixture; no live AI provider."}
    monkeypatch.setattr(research_readiness, "model_readiness", readiness)
    headers = signup(client, "browser-journey@example.com")
    api_port, web_port = port(), port()
    api_url, web_url = f"http://127.0.0.1:{api_port}", f"http://localhost:{web_port}"
    # Existing CORS middleware reads its list when first building the stack.
    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    monkeypatch.setitem(cors.kwargs, "allow_origins", [*cors.kwargs["allow_origins"], web_url])
    app.middleware_stack = None
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port, lifespan="off", log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    env = {**os.environ, "VITE_API_BASE_URL": api_url}
    log = open(tmp_path / "frontend.log", "w", encoding="utf-8")
    frontend = subprocess.Popen([shutil.which("node"), "node_modules/vite/bin/vite.js", "--host", "localhost", "--port", str(web_port), "--strictPort"], cwd=ROOT / "frontend", env=env, stdout=log, stderr=log)
    try:
        import httpx
        deadline = time.monotonic() + 90
        while True:
            assert frontend.poll() is None, (tmp_path / "frontend.log").read_text()
            try:
                if server.started and httpx.get(web_url, timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            assert time.monotonic() < deadline, "Local application startup timed out: " + (tmp_path / "frontend.log").read_text(encoding="utf-8")
            time.sleep(0.2)
        with sync_playwright() as pw, browser_evidence(tmp_path) as evidence:
            browser = pw.chromium.launch(channel="chromium")
            context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            evidence["context"] = context
            # Fail if the browser tries an external network request.
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith((api_url, web_url)) else route.abort())
            context.add_init_script(f"if (location.origin === '{web_url}') {{ localStorage.setItem('gtm.access_token', '{headers['Authorization'][7:]}'); localStorage.setItem('gaps_ai_workspace_id', '{headers['X-Workspace-ID']}'); }}")
            page = context.new_page()
            evidence["page"] = page
            page.set_default_timeout(20000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            def go(path):
                page.goto(web_url + path)
                expect(page.locator("main")).to_be_visible(timeout=60000)
                expect(page.get_by_role("status", name="Loading workspace data")).to_have_count(0)
            def click(name):
                try:
                    page.get_by_role("button", name=name, exact=True).click()
                except Exception:
                    print(page.locator("body").inner_text())
                    print(page.locator("button").evaluate_all("els => els.map(e => e.outerHTML)"))
                    (tmp_path / "failure.html").write_text(page.content(), encoding="utf-8")
                    page.screenshot(path=str(tmp_path / "failure.png"), full_page=True)
                    raise
            def saved(path):
                response = client.get(path, headers=headers)
                assert response.status_code == 200, response.text
                return response.json()
            go("/settings")
            page.get_by_role("button", name="Open working draft", exact=True).click()
            labels = {"company": "Company", "product_service": "Product or service", "value_proposition": "Value proposition", "icp": "Ideal customer", "buyer_personas": "Buyer personas", "gtm_objectives": "GTM objectives"}
            for key, label in labels.items():
                page.get_by_label(label, exact=True).fill(PROFILE[key])
            page.get_by_role("button", name="3. Claims", exact=True).click()
            page.get_by_label("Claim", exact=True).fill("Reviewed promise for synthetic QA")
            page.get_by_role("button", name="Add claim to draft", exact=True).click()
            with page.expect_response(lambda r: "/company-brain/versions/" in r.url and r.request.method == "PUT") as response:
                page.get_by_role("button", name="Save draft", exact=True).click()
            assert response.value.status == 200
            page.get_by_role("button", name="4. Review and publish", exact=True).click()
            page.get_by_label("I have reviewed this saved version and its claims.").check()
            with page.expect_response(lambda r: r.url.endswith("/publish")) as response:
                page.get_by_role("button", name="Publish reviewed version", exact=True).click()
            assert response.value.status == 200
            brain = response.value.json()
            assert saved("/api/v1/company-brain")["versions"][0]["id"] == brain["id"]
            go("/prospects")
            page.get_by_text("Add an account", exact=True).click()
            page.get_by_label("Company name", exact=True).fill("Acme browser fixture")
            page.get_by_label("Domain", exact=True).fill("example.com")
            with page.expect_response(lambda r: r.url.endswith("/companies/") and r.request.method == "POST") as response:
                click("Add account")
            account = response.value.json()
            page.get_by_role("button", name="Explore account & evidence →", exact=True).click()
            page.get_by_label("Company Brain version").select_option(brain["id"])
            page.get_by_label("Source URLs (up to three public HTTPS pages, one per line)").fill("https://example.com/")
            with page.expect_response(lambda r: r.url.endswith("/plans") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Propose research plan", exact=True).click()
            plan = response.value.json()
            assert provider.calls == 0 and not run(client, headers)
            page.get_by_role("link", name="Open command center", exact=True).click()
            page.reload()
            page.get_by_label("I reviewed this saved plan, targets, constraints and risks.").check()
            with page.expect_response(lambda r: r.url.endswith("/approve")) as response:
                page.get_by_role("button", name="Approve and queue plan", exact=True).click()
            assert response.value.status == 201, response.value.text()
            assert run(client, headers)
            job = saved("/api/v1/research/jobs")[0]
            report = saved("/api/v1/research/jobs/" + job["id"])
            assert report["status"] == "completed" and report["intelligence"]["brain_hash"] == brain["content_hash"]
            go("/prospects")
            expect(page.get_by_text("qualified", exact=True)).to_be_visible()
            page.get_by_role("button", name="Explore account & evidence →", exact=True).click()
            expect(page.get_by_text("Jane Buyer · VP Revenue", exact=True)).to_be_visible()
            page.get_by_text("Add a contact", exact=True).click()
            for label, value in [("First name", "Jane"), ("Last name", "Buyer"), ("Email", "jane@example.com"), ("Job title", "VP Revenue")]:
                page.get_by_label(label, exact=True).fill(value)
            with page.expect_response(lambda r: r.url.endswith("/contacts/") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Save contact", exact=True).click()
            contact = response.value.json()
            # Sender connection is an external boundary, provisioned test-only.
            sender = post(client, headers, "/senders", {"email": "sender@example.com", "provider": "fake"})
            other = client.post("/api/v1/companies/", headers=headers, json={"name": "Unrelated account"}).json()
            other_contact = client.post("/api/v1/contacts/", headers=headers, json={"company_id": other["id"], "first_name": "Other", "last_name": "Buyer", "email": "other@example.com"}).json()
            go("/outreach")
            page.get_by_role("button", name="Approval queue", exact=True).click()
            expect(page.get_by_text("No drafts awaiting approval", exact=True)).to_be_visible()
            page.get_by_role("button", name="Campaigns & sequences", exact=True).click()
            page.get_by_label("Campaign name", exact=True).fill("Browser campaign")
            with page.expect_response(lambda r: r.url.endswith("/campaigns") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Create campaign", exact=True).click()
            campaign = response.value.json()
            page.locator('select[name="campaign_id"]').select_option(campaign["id"])
            page.get_by_label("Sequence name", exact=True).fill("Browser sequence")
            with page.expect_response(lambda r: r.url.endswith("/sequences") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Create sequence", exact=True).click()
            sequence = response.value.json()
            page.locator('select[name="sequence"]').select_option(sequence["id"])
            page.get_by_label("Step purposes (one per line, up to ten)").fill("Introduction")
            with page.expect_response(lambda r: r.url.endswith("/versions") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Create immutable version", exact=True).click()
            version = response.value.json()
            page.get_by_role("button", name="Enrollments", exact=True).click()
            research_select = page.locator('select[name="research_job_id"]')
            expect(research_select).to_be_disabled()
            page.locator('select[name="contact_id"]').select_option(contact["id"])
            page.locator('select[name="version_id"]').select_option(version["id"])
            page.locator('select[name="sender_id"]').select_option(sender["id"])
            research_select.select_option(job["id"])
            page.locator('select[name="contact_id"]').select_option(other_contact["id"])
            expect(research_select).to_have_value("")
            expect(research_select.locator("option")).to_have_count(1)
            page.locator('select[name="contact_id"]').select_option(contact["id"])
            research_select.select_option(job["id"])
            with page.expect_response(lambda r: r.url.endswith("/enrollments") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Enroll contact", exact=True).click()
            assert response.value.status == 201
            page.get_by_role("button", name="Messages", exact=True).click()
            with page.expect_response(lambda r: r.url.endswith("/drafts") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Prepare draft", exact=True).click()
            assert response.value.status == 201
            assert not run(client, headers) and provider.calls == 0
            with page.expect_response(lambda r: r.url.endswith("/submit")) as response:
                page.get_by_role("button", name="Submit for approval", exact=True).click()
            assert response.value.status == 200
            assert not run(client, headers) and provider.calls == 0
            page.reload()
            page.get_by_role("button", name="Approval queue", exact=True).click()
            page.get_by_role("button", name="Review message", exact=True).click()
            page.get_by_label("I reviewed this recipient, exact message and supporting evidence.").check()
            with page.expect_response(lambda r: r.url.endswith("/approve")) as response:
                page.get_by_role("button", name="Approve message only", exact=True).click()
            reviewed = response.value.json()
            assert not run(client, headers) and provider.calls == 0
            expect(page.get_by_text("No drafts awaiting approval", exact=True)).to_be_visible()
            page.get_by_role("button", name="Messages", exact=True).click()
            page.get_by_role("button", name="Review separate delivery authorization", exact=True).click()
            page.get_by_label("I reviewed the exact saved content, target, plan and risks above.").check()
            with page.expect_response(lambda r: r.url.endswith("/approve")) as response:
                page.get_by_role("button", name="Approve execution plan", exact=True).click()
            assert response.value.status == 201 and run(client, headers)
            outbound = get_message(client, headers, reviewed)
            assert provider.calls == 1 and outbound["provider_message_id"]
            page.reload()
            expect(page.get_by_text("Provider-confirmed sent", exact=True).last).to_be_visible()
            assert not run(client, headers) and provider.calls == 1
            incoming = ingest(client, headers, {"sender": sender}, event(outbound, body="Let's schedule a meeting."))
            assert run(client, headers)
            assert saved("/api/v1/inbox/messages/" + incoming["id"])["classification"]["category"] == "meeting_intent"
            go("/inbox")
            page.get_by_role("button", name="Conversation 1", exact=False).click()
            expect(page.get_by_text("Let's schedule a meeting.", exact=True)).to_be_visible()
            page.reload()
            page.get_by_role("button", name="Conversation 1", exact=False).click()
            expect(page.get_by_text("Let's schedule a meeting.", exact=True)).to_be_visible()
            go("/pipeline")
            expect(page.get_by_text("Jane Buyer", exact=True).first).to_be_visible()
            rows = saved("/api/v1/outcomes/pipeline")
            assert any(r["contact_id"] == contact["id"] and r["stage"] == "interested" for r in rows)
            go("/insights")
            expect(page.get_by_text("1 sent · 1/1 replied", exact=False)).to_be_visible()
            page.reload()
            expect(page.get_by_text("1 sent · 1/1 replied", exact=False)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Insights overflows the viewport"
            page.screenshot(path=str(tmp_path / "insights.png"), full_page=True)
            assert saved("/api/v1/gtm/plans/" + plan["id"])["content_hash"] == plan["content_hash"]
            assert provider.calls == 1
            assert not errors, errors
    finally:
        frontend.terminate()
        frontend.wait(timeout=15)
        log.close()
        server.should_exit = True
        thread.join(timeout=15)
        app.middleware_stack = None
