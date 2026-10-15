"""Unit tests for the isolated, deterministic, side-effect-free demo."""
import unittest

from demo_workflow import FIXTURES, approve_sample, qualify, research_account, run_workflow


class TestOfflineGtmFlow(unittest.TestCase):
    def test_expected_scores(self):
        self.assertEqual(run_workflow("aster")["qualification"]["score"], 100)
        self.assertEqual(run_workflow("ridge")["qualification"]["score"], 0)
        self.assertEqual(run_workflow("mira")["qualification"]["score"], 100)

    def test_no_side_effects_for_all_fixtures(self):
        for key in FIXTURES:
            with self.subTest(key=key):
                result = run_workflow(key)
                self.assertEqual(result["external_network_calls"], 0)
                self.assertEqual(result["emails_sent"], 0)
                self.assertEqual(result["crm_writes"], 0)
                self.assertEqual(result["calendar_events_created"], 0)
                self.assertFalse(result["draft"]["sent"])
                self.assertEqual(result["draft"]["approval_state"], "PENDING_REVIEW")
                self.assertFalse(result["enrichment"]["verified_real_world"])

    def test_rejects_unknown_account(self):
        with self.assertRaises(ValueError):
            research_account("nonexistent")

    def test_approval_is_only_in_memory(self):
        original = run_workflow("aster")
        approved = approve_sample(original, "Demo reviewer")
        self.assertEqual(original["draft"]["approval_state"], "PENDING_REVIEW")
        self.assertEqual(approved["draft"]["approval_state"], "APPROVED_IN_MEMORY_ONLY")
        self.assertEqual(approved["emails_sent"], 0)
        self.assertEqual(approved["crm_writes"], 0)
        with self.assertRaises(ValueError):
            approve_sample(original, "  ")

    def test_fixture_mutation_does_not_leak(self):
        a = research_account("aster")
        a["evidence"].clear()
        b = research_account("aster")
        self.assertEqual(len(b["evidence"]), 2)

    def test_deterministic_execution(self):
        for key in FIXTURES:
            self.assertEqual(run_workflow(key), run_workflow(key))

    def test_evidence_scoring_requires_source_coverage(self):
        account = research_account("aster")
        account["evidence"].pop()
        quality = qualify(account)
        self.assertFalse(quality["checks"]["evidence_completeness"])
        self.assertEqual(quality["score"], 85)


if __name__ == "__main__":
    unittest.main()
