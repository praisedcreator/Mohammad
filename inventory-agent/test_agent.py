"""Business-boundary tests; all services and model responses are local fakes."""

import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent import (Rejected, Runtime, canonical, digest, evaluate, load_proposal,
                   redact, review, run_demo, run_vertex, simulate_execution)
from services import FixtureServices


class Block:
    def __init__(self, name, arguments, identifier):
        self.type, self.name, self.input, self.id = "tool_use", name, arguments, identifier

    def model_dump(self, **kwargs):
        return {"type": self.type, "name": self.name, "input": self.input, "id": self.id}


class FakeClient:
    def __init__(self):
        self.requests = []
        self.messages = self
        self.script = [
            [Block("get_inventory", {}, "i"), Block("get_policy", {}, "p")],
            [Block("evaluate_transfer", {"quantity": 240}, "e")],
            [Block("submit_proposal", {"quantity": 240, "rationale": "Model-authored business rationale.",
                                        "alternatives": ["Ask procurement for an expedited supplier quote."]}, "s")],
        ]

    def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        blocks = self.script[len(self.requests) - 1]
        return SimpleNamespace(id=f"fake-response-{len(self.requests)}", stop_reason="tool_use",
                               content=blocks, usage=SimpleNamespace(input_tokens=10, output_tokens=10))


class AgentTests(unittest.TestCase):
    def setUp(self):
        test_base = (Path(__file__).resolve().parent / "runs" / "test-tmp").resolve()
        test_base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_base)
        self.out = Path(self.temp.name)
        if not self.out.resolve().is_relative_to(test_base):
            raise RuntimeError("Test cleanup must remain within the test workspace")
        self.addCleanup(self.temp.cleanup)
        self.services = FixtureServices()
        self.runtime = Runtime(self.services, self.out)
        self.addCleanup(self.runtime.connection.close)

    def proposal(self):
        return run_demo(self.runtime)

    def approve(self, proposal):
        return review(self.out, "approve", "demo-procurement-reviewer", {"procurement"}, proposal["proposal_hash"])

    def test_arrival_math_accounts_for_consumption_in_transit(self):
        result = evaluate(240, self.services.get_inventory(), self.services.get_policy(), self.services.case)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["destination_units_before_arrival"], 40)
        self.assertEqual(result["destination_units_after_arrival"], 280)
        self.assertEqual(result["destination_cover_days_after_arrival"], 7)
        self.assertEqual(result["source_cover_days_after_arrival"], 11)
        self.assertEqual(result["transport_cost_minor"], 30000)

    def test_source_protection_blocks_unsafe_quantity(self):
        result = evaluate(400, self.services.get_inventory(), self.services.get_policy(), self.services.case)
        self.assertFalse(result["allowed"])
        self.assertIn("source_floor_breached", result["violations"])

    def test_quantity_type_and_pack_size(self):
        for quantity in (True, 240.0, -1, 0):
            with self.assertRaises(Rejected):
                evaluate(quantity, self.services.get_inventory(), self.services.get_policy(), self.services.case)
        result = evaluate(241, self.services.get_inventory(), self.services.get_policy(), self.services.case)
        self.assertIn("invalid_pack_multiple", result["violations"])

    def test_invalid_and_stale_data_fail_closed(self):
        inventory = self.services.get_inventory()
        inventory["inventory_valid"] = False
        with self.assertRaises(Rejected):
            evaluate(240, inventory, self.services.get_policy(), self.services.case)
        inventory = self.services.get_inventory()
        inventory["as_of"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with self.assertRaises(Rejected):
            evaluate(240, inventory, self.services.get_policy(), self.services.case)

    def test_aggregate_receipts_need_time_phased_simulation(self):
        inventory = self.services.get_inventory()
        inventory["destination"]["confirmed_inbound_before_arrival"] = 10
        with self.assertRaises(Rejected):
            evaluate(240, inventory, self.services.get_policy(), self.services.case)

    def test_no_execution_or_approval_tools(self):
        names = {item["name"] for item in self.runtime.tools()}
        self.assertNotIn("approve", names)
        self.assertNotIn("execute_transfer", names)
        result = self.runtime.call("execute_transfer", {}, "forbidden")
        self.assertTrue(result["is_error"])
        self.assertFalse((self.out / "proposal.json").exists())

    def test_evidence_required_before_submission(self):
        with self.assertRaises(Rejected):
            self.runtime.dispatch("submit_proposal", {"quantity": 240, "rationale": "No evidence",
                                                       "alternatives": ["Wait"]})

    def test_approval_required(self):
        self.proposal()
        with self.assertRaises(Rejected):
            simulate_execution(self.out, self.services)

    def test_review_requires_authority_and_exact_hash(self):
        proposal = self.proposal()
        with self.assertRaises(Rejected):
            review(self.out, "approve", "viewer", {"viewer"}, proposal["proposal_hash"])
        with self.assertRaises(Rejected):
            review(self.out, "approve", "reviewer", {"procurement"}, "wrong-hash")

    def test_rejection_cannot_be_executed(self):
        proposal = self.proposal()
        review(self.out, "reject", "reviewer", {"procurement"}, proposal["proposal_hash"])
        with self.assertRaises(Rejected):
            simulate_execution(self.out, self.services)

    def test_changed_inventory_requires_new_review(self):
        proposal = self.proposal()
        self.approve(proposal)
        # Still numerically safe, but the reviewer approved a different snapshot.
        self.services.inventory["source"]["on_hand"] -= 10
        with self.assertRaises(Rejected):
            simulate_execution(self.out, self.services)

    def test_simulation_is_idempotent(self):
        proposal = self.proposal()
        self.approve(proposal)
        first = simulate_execution(self.out, self.services)
        second = simulate_execution(self.out, self.services)
        self.assertEqual(first, second)
        self.assertFalse(first["real_erp_write"])
        events = [json.loads(line)["event"] for line in (self.out / "trace.jsonl").read_text().splitlines()]
        self.assertEqual(events.count("transfer_simulated"), 1)

    def test_expired_proposal_requires_new_proposal(self):
        self.proposal()
        row, payload = load_proposal(self.runtime.connection)
        payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        new_hash = digest(payload)
        with self.runtime.connection:
            self.runtime.connection.execute("UPDATE proposal SET payload=?, hash=? WHERE id=?",
                                            (canonical(payload), new_hash, row["id"]))
        with self.assertRaises(Rejected):
            review(self.out, "approve", "reviewer", {"procurement"}, new_hash)

    def test_real_tool_loop_protocol_with_fake_model(self):
        fake = FakeClient()
        with patch.dict(os.environ, {"VERTEX_MODEL": "fake-model-for-test", "ENABLE_PUBLIC_SEARCH": "0"}):
            result = run_vertex(self.runtime, client=fake)
        self.assertEqual(result["status_at_export"], "AWAITING_REVIEW")
        self.assertEqual(len(fake.requests), 3)
        results = fake.requests[1]["messages"][-1]
        self.assertEqual(results["role"], "user")
        self.assertEqual([block["tool_use_id"] for block in results["content"]], ["i", "p"])

    def test_model_round_budget_stops_without_proposal(self):
        with patch.dict(os.environ, {"VERTEX_MODEL": "fake", "ENABLE_PUBLIC_SEARCH": "0"}):
            with self.assertRaises(Rejected):
                run_vertex(self.runtime, client=FakeClient(), max_rounds=1)
        self.assertIsNone(self.runtime.submitted)

    def test_secret_keys_are_redacted(self):
        self.assertEqual(redact({"Authorization": "secret", "nested": {"api_key": "secret"}}),
                         {"Authorization": "[REDACTED]", "nested": {"api_key": "[REDACTED]"}})


if __name__ == "__main__":
    unittest.main()
