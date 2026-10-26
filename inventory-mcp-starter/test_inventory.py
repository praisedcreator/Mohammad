"""Business rules, persistence, review boundary and portable client configuration."""
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import configure_client
from business import Rejected, canonical, digest, evaluate
from store import InventoryStore, ROOT


class InventoryTests(unittest.TestCase):
    def setUp(self):
        test_root = (ROOT / ".runtime" / "tests").resolve()
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="inventory-test-", dir=test_root)
        if not Path(self.temp.name).resolve().is_relative_to(test_root):
            raise RuntimeError("Test cleanup must remain in this project's test workspace")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.fixture = self.folder / "fixtures.json"
        self.fixture.write_text((ROOT / "fixtures.json").read_text(encoding="utf-8"), encoding="utf-8")
        self.store = InventoryStore(self.folder / "state.sqlite", self.fixture)

    def proposal(self, **changes):
        arguments = {"quantity": 240, "rationale": "Cover the Dubai shortage.",
                     "alternatives": ["Request an expedited supplier quote."], "request_id": "test-request-001"}
        return self.store.create(**{**arguments, **changes})

    def approve(self, proposal):
        return self.store.review(proposal["proposal_id"], proposal["proposal_hash"], "approve", "demo-reviewer", "Demo approved")

    def test_arrival_calculation(self):
        case, stock, policy = self.store.evidence()
        result = evaluate(240, stock, policy, case)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["destination_units_before_arrival"], 40)
        self.assertEqual(result["destination_cover_days_after_arrival"], 7)
        self.assertEqual(result["source_cover_days_after_arrival"], 11)

    def test_invalid_types_and_pack_size(self):
        for quantity in (True, 240.0, 0, -10, 241):
            with self.subTest(quantity=quantity), self.assertRaises(Rejected):
                self.proposal(quantity=quantity)

    def test_source_floor_breach_creates_no_proposal(self):
        with self.assertRaisesRegex(Rejected, "source_floor_breached"):
            self.proposal(quantity=400)
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0], 0)

    def test_saved_state_survives_restart(self):
        proposal = self.proposal()
        reloaded = InventoryStore(self.store.path, self.fixture).get(proposal["proposal_id"])
        self.assertEqual(reloaded["proposal_hash"], proposal["proposal_hash"])
        self.assertEqual(reloaded["status"], "AWAITING_REVIEW")

    def test_retries_do_not_duplicate_proposals(self):
        first, retry = self.proposal(), self.proposal()
        self.assertEqual(first["proposal_id"], retry["proposal_id"])
        self.assertTrue(retry["idempotent_retry"])
        with self.assertRaisesRegex(Rejected, "different proposal content"):
            self.proposal(rationale="Changed content with the old ID")

    def test_review_requires_exact_hash(self):
        proposal = self.proposal()
        with self.assertRaisesRegex(Rejected, "hash"):
            self.store.review(proposal["proposal_id"], "wrong-hash", "approve", "reviewer", "Reviewed")
        self.assertEqual(self.store.get(proposal["proposal_id"])["status"], "AWAITING_REVIEW")

    def test_missing_approval_and_rejection_block_simulation(self):
        proposal = self.proposal()
        with self.assertRaisesRegex(Rejected, "approved proposal"):
            self.store.simulate(proposal["proposal_id"])
        self.store.review(proposal["proposal_id"], proposal["proposal_hash"], "reject", "reviewer", "Need new assumptions")
        with self.assertRaisesRegex(Rejected, "approved proposal"):
            self.store.simulate(proposal["proposal_id"])

    def test_simulation_is_idempotent_and_does_not_change_stock(self):
        proposal = self.proposal()
        before = self.fixture.read_bytes()
        self.approve(proposal)
        first = self.store.simulate(proposal["proposal_id"])
        repeat = self.store.simulate(proposal["proposal_id"])
        self.assertEqual(first["simulation_receipt"], repeat["simulation_receipt"])
        self.assertFalse(first["simulation_receipt"]["real_stock_moved"])
        self.assertEqual(self.fixture.read_bytes(), before)

    def test_changed_inventory_requires_new_review(self):
        proposal = self.proposal()
        self.approve(proposal)
        fixture = json.loads(self.fixture.read_text(encoding="utf-8"))
        fixture["inventory"]["source"]["on_hand"] -= 10
        self.fixture.write_text(json.dumps(fixture), encoding="utf-8")
        with self.assertRaisesRegex(Rejected, "changed"):
            self.store.simulate(proposal["proposal_id"])

    def test_expired_proposal_cannot_be_approved(self):
        proposal = self.proposal()
        with self.store.connection(write=True) as db:
            row, payload = self.store._read(db, proposal["proposal_id"])
            payload["expires_at"] = "2000-01-01T00:00:00+00:00"
            expected_hash = digest(payload)
            db.execute("UPDATE proposals SET payload=?,payload_hash=? WHERE id=?",
                       (canonical(payload), expected_hash, proposal["proposal_id"]))
        with self.assertRaisesRegex(Rejected, "expired"):
            self.store.review(proposal["proposal_id"], expected_hash, "approve", "reviewer", "Reviewed")

    def test_proposal_tampering_is_detected(self):
        proposal = self.proposal()
        with self.store.connection(write=True) as db:
            row, payload = self.store._read(db, proposal["proposal_id"])
            payload["quantity"] = 999
            db.execute("UPDATE proposals SET payload=? WHERE id=?", (canonical(payload), proposal["proposal_id"]))
        with self.assertRaisesRegex(Rejected, "hash"):
            self.store.get(proposal["proposal_id"])

    def test_proposal_and_review_have_persisted_events(self):
        proposal = self.proposal()
        self.approve(proposal)
        events = self.store.traces(proposal["proposal_id"])
        self.assertEqual([row["event"] for row in events], ["proposal_created", "human_review_demo"])
        self.assertEqual(events[0]["details"]["proposal_hash"], proposal["proposal_hash"])

    def test_client_configs_and_skill_copies_are_valid_and_repeatable(self):
        project = self.folder / "A project with spaces"
        with patch.object(configure_client, "ROOT", project):
            configure_client.configure("both")
            configure_client.configure("both")
        codex = tomllib.loads((project / ".codex" / "config.toml").read_text(encoding="utf-8"))
        claude = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(codex["mcp_servers"]["inventory-review"]["args"], [str(project / "server.py")])
        self.assertEqual(claude["mcpServers"]["inventory-review"]["env"]["INVENTORY_DB"], str(project / ".runtime" / "inventory.sqlite"))
        for location in (".agents", ".claude"):
            self.assertEqual((project / location / "skills" / "inventory-review" / "SKILL.md").read_bytes(),
                             (ROOT / "skills" / "inventory-review" / "SKILL.md").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
