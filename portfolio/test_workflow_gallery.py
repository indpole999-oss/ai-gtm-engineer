"""Pure standard-library tests for eight offline portfolio workflows."""
import unittest

from workflow_gallery import (
    SafeWorkspace, WORKFLOWS, run, crm_sync, calendar_scheduling,
    agent_orchestration, gtm_reporting,
)


class TestWorkflowGallery(unittest.TestCase):
    def test_eight_named_workflows_available(self):
        self.assertEqual(len(WORKFLOWS), 8)

    def test_every_workflow_runs_without_external_calls(self):
        for name in WORKFLOWS:
            with self.subTest(workflow=name):
                result = run(name, "aster")
                self.assertEqual(result["mode"], "OFFLINE_FICTIONAL_FIXTURE")
                self.assertEqual(result["external_calls"], 0)

    def test_mock_crm_upsert_is_idempotent(self):
        ctx = SafeWorkspace()
        first = crm_sync(ctx)
        second = crm_sync(ctx)
        self.assertEqual(first["record"], second["record"])
        self.assertEqual(len(ctx.records), 1)
        self.assertFalse(first["external_write"])

    def test_calendar_does_not_book(self):
        ctx = SafeWorkspace()
        preview = calendar_scheduling(ctx)["event"]
        self.assertEqual(preview["status"], "PREVIEW_ONLY_PENDING_APPROVAL")
        self.assertFalse(preview["external_event_created"])
        self.assertTrue(preview["start_utc"].endswith("+00:00"))

    def test_reporting_never_claims_revenue(self):
        ctx = SafeWorkspace()
        ctx.log("research", "test")
        report = gtm_reporting(ctx)
        self.assertEqual(report["events_recorded"], 1)
        self.assertIsNone(report["revenue_attributed"])

    def test_orchestrator_requires_review_and_no_side_effects(self):
        ctx = SafeWorkspace()
        out = agent_orchestration(ctx)
        self.assertEqual(len(out["steps"]), 6)
        self.assertTrue(out["pending_human_approval"])
        self.assertEqual(out["emails_sent"], 0)
        self.assertEqual(out["crm_external_writes"], 0)
        self.assertEqual(out["calendar_external_writes"], 0)
        self.assertEqual(out["external_calls"], 0)

    def test_unknown_workflow_is_rejected(self):
        with self.assertRaises(ValueError):
            run("external-send")

    def test_all_fixtures_run_orchestrator(self):
        for account in ("aster", "ridge", "mira"):
            with self.subTest(account=account):
                output = run("all", account)
                self.assertEqual(output["orchestration"]["external_calls"], 0)
                self.assertGreater(len(output["activity_log"]), 0)


if __name__ == "__main__":
    unittest.main()
