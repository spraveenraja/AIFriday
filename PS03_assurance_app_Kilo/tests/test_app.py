import json
import tempfile
import unittest
from pathlib import Path

import app


class AssuranceAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "demo.sqlite3"
        app.seed_database(path=self.database)
        self.repo = app.DemoRepository(self.database)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_seeded_case_facts_reconcile(self) -> None:
        self.assertEqual(app.validate_dataset(self.repo), [])
        self.assertEqual(self.repo.get_portfolio_summary()["engagements"], 28)
        self.assertEqual(len(self.repo.get_business_units()), 5)

    def test_database_repository_uses_configured_path(self) -> None:
        with self.repo.connection() as connection:
            connection.execute(
                "INSERT INTO settings(key, value) VALUES ('test-path', 'isolated')"
            )
        self.assertEqual(self.repo.get_setting("test-path"), "isolated")
        self.assertNotEqual(self.database, app.DB_PATH)

    def test_seed_migration_preserves_existing_demo_records(self) -> None:
        with self.repo.connection() as connection:
            connection.execute(
                "UPDATE settings SET value = '3' WHERE key = 'seed_version'"
            )
            connection.execute(
                "UPDATE settings SET value = 'Auditor / Control Reviewer' "
                "WHERE key = 'current_role'"
            )
            connection.execute(
                "UPDATE actions SET status = 'Completed' WHERE id = 'ACT-004'"
            )
        app.seed_database(path=self.database)
        with self.repo.connection() as connection:
            engagement_count = connection.execute(
                "SELECT COUNT(*) AS count FROM engagements"
            ).fetchone()["count"]
            action_status = connection.execute(
                "SELECT status FROM actions WHERE id = 'ACT-004'"
            ).fetchone()["status"]
        self.assertEqual(engagement_count, 28)
        self.assertEqual(
            self.repo.get_setting("current_role"), "Auditor / Control Reviewer"
        )
        self.assertEqual(action_status, "Owner Reported Complete")

    def test_threshold_boundaries_and_unknown_handling(self) -> None:
        self.assertEqual(app.rate_delivery_predictability(95), "Amber")
        self.assertEqual(app.rate_delivery_predictability(95.01), "Green")
        self.assertEqual(app.rate_evidence_traceability(60), "Amber")
        self.assertEqual(app.rate_evidence_traceability(59.99), "Red")
        self.assertEqual(app.rate_release_failure(20), "Amber")
        self.assertEqual(app.rate_release_failure(20.01), "Red")
        self.assertEqual(
            app.rate_service_stability(99, "Critical", 1, 0), "Red"
        )
        self.assertEqual(app.rate_service_stability(99, "Noncritical", 1), "Amber")
        self.assertEqual(app.rate_service_stability(99, None, 0, 100), "Red")
        self.assertEqual(
            app.rate_service_stability(99, None, 0, evidence_verified=False),
            "Unknown",
        )
        with self.assertRaises(ValueError):
            app.rate_delivery_predictability(101)

    def test_recommendation_requires_approval_to_activate_action(self) -> None:
        with self.repo.connection() as connection:
            before = connection.execute(
                "SELECT status FROM actions WHERE id = 'ACT-001'"
            ).fetchone()["status"]
        self.assertEqual(before, "Draft")

        with self.assertRaises(PermissionError):
            self.repo.update_recommendation_state(
                "REC-001", "Approved", "Engineering Manager"
            )
        with self.repo.connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT status FROM actions WHERE id = 'ACT-001'"
                ).fetchone()["status"],
                "Draft",
            )

        self.repo.update_recommendation_state(
            "REC-001", "Approved", "Delivery Assurance Leader"
        )
        with self.repo.connection() as connection:
            action = connection.execute(
                "SELECT * FROM actions WHERE id = 'ACT-001'"
            ).fetchone()
        status = action["status"]
        self.assertEqual(status, "Approved")
        recommendation = next(
            row for row in self.repo.get_recommendations() if row["id"] == "REC-001"
        )
        self.assertEqual(action["title"], recommendation["title"])
        self.assertEqual(action["accountable_owner"], recommendation["proposed_owner"])
        events = self.repo.get_review_events("REC-001")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["actor_role"], "Delivery Assurance Leader")
        with self.assertRaises(ValueError):
            self.repo.update_recommendation_state(
                "REC-001", "Approved", "Delivery Assurance Leader"
            )

    def test_edit_updates_draft_action_and_audits_changes(self) -> None:
        fields: dict[str, str | int] = {
            "title": "Revise release readiness checklist",
            "proposed_owner": "Engineering Manager",
            "contributors": "Delivery Assurance Leader",
            "horizon_days": 60,
            "due_date": "2026-12-01",
            "expected_outcome": "Release evidence is reviewed before deployment.",
            "success_measure": "All pilot releases have an approved checklist.",
        }
        self.repo.update_recommendation_details(
            "REC-001", fields, "Delivery Assurance Leader"
        )
        recommendation = next(
            row for row in self.repo.get_recommendations() if row["id"] == "REC-001"
        )
        action = next(
            row for row in self.repo.get_actions() if row["id"] == "ACT-001"
        )
        self.assertEqual(recommendation["state"], "Pending Human Review")
        self.assertEqual(recommendation["proposed_owner"], "Engineering Manager")
        self.assertEqual(action["status"], "Draft")
        self.assertEqual(action["accountable_owner"], "Engineering Manager")
        event = self.repo.get_review_events("REC-001")[0]
        self.assertEqual(event["event_type"], "Proposal edited")
        self.assertIn("before", json.loads(event["details"]))

    def test_rejected_proposal_does_not_activate_action(self) -> None:
        self.repo.update_recommendation_state(
            "REC-002", "Rejected", "President / Executive Sponsor"
        )
        action = next(
            row for row in self.repo.get_actions() if row["id"] == "ACT-002"
        )
        self.assertEqual(action["status"], "Rejected")
        recommendation = next(
            row for row in self.repo.get_recommendations() if row["id"] == "REC-002"
        )
        self.assertEqual(recommendation["state"], "Rejected")

    def test_action_lifecycle_separates_owner_report_from_verification(self) -> None:
        self.repo.update_recommendation_state(
            "REC-001", "Approved", "Delivery Assurance Leader"
        )
        self.repo.transition_action(
            "ACT-001", "In Progress", "Engineering Manager"
        )
        with self.assertRaises(PermissionError):
            self.repo.transition_action("ACT-001", "Verified", "Engineering Manager", "checked")
        with self.assertRaises(ValueError):
            self.repo.transition_action(
                "ACT-001", "Owner Reported Complete", "Engineering Manager"
            )

        self.repo.transition_action(
            "ACT-001",
            "Owner Reported Complete",
            "Engineering Manager",
            "Synthetic release checklist and defect-triage record attached.",
        )
        with self.repo.connection() as connection:
            owner_report = connection.execute(
                "SELECT * FROM actions WHERE id = 'ACT-001'"
            ).fetchone()
        self.assertEqual(owner_report["status"], "Owner Reported Complete")
        self.assertEqual(
            owner_report["verified_effectiveness"],
            "Pending independent verification",
        )
        self.repo.transition_action(
            "ACT-001",
            "Verified",
            "Auditor / Control Reviewer",
            "Independent sample confirmed the checklist and outcome measure.",
        )
        with self.repo.connection() as connection:
            verified = connection.execute(
                "SELECT * FROM actions WHERE id = 'ACT-001'"
            ).fetchone()
        self.assertEqual(verified["status"], "Verified")
        self.assertIn("Independent sample", verified["verified_effectiveness"])
        self.assertEqual(len(self.repo.get_action_events("ACT-001")), 4)


if __name__ == "__main__":
    unittest.main()
