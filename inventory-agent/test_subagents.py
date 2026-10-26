"""Offline checks for delegated scope, context, budget and unchanged approval gates."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent import Rejected, Runtime, run_vertex, simulate_execution
from services import FixtureServices
from subagents import PolicyDelegation, ReplayBlock, ReplayClient, SPECIALIST_SYSTEM


class BadChildClient:
    is_replay = True

    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        return SimpleNamespace(id="bad-child", stop_reason="tool_use",
                               content=[ReplayBlock("submit_proposal", {"quantity": 240}, "forbidden-child-call")],
                               usage=SimpleNamespace(input_tokens=0, output_tokens=0))


class SubagentTests(unittest.TestCase):
    def setUp(self):
        test_base = (Path(__file__).resolve().parent / "runs" / "test-tmp").resolve()
        test_base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_base)
        self.out = Path(self.temp.name)
        if not self.out.resolve().is_relative_to(test_base):
            raise RuntimeError("Test cleanup must stay within its workspace")
        self.addCleanup(self.temp.cleanup)
        self.runtime = Runtime(FixtureServices(), self.out)
        self.addCleanup(self.runtime.connection.close)
        self.client = ReplayClient()
        self.delegation = PolicyDelegation(self.runtime, self.client, "replay-model")

    def delegate(self, handler=None):
        return (handler or self.delegation).call(ReplayBlock(
            "delegate_policy_review", {"task": "Explain the transfer constraints."}, "parent-call"))

    def test_subagent_reports_advisory_evidence(self):
        result = self.delegate()
        self.assertFalse(result["is_error"])
        findings = json.loads(result["content"])
        self.assertEqual(findings["authority"], "advisory")
        self.assertTrue(findings["human_review_required"])
        self.assertEqual(findings["evidence"]["document_id"], "POL-DEMO-TRANSFER")
        self.assertIsNone(self.runtime.submitted)

    def test_child_has_separate_context_and_narrow_tools(self):
        self.delegate()
        first = self.client.requests[0]
        self.assertEqual(first["system"], SPECIALIST_SYSTEM)
        self.assertEqual({tool["name"] for tool in first["tools"]}, {"get_policy", "return_findings"})
        initial = json.loads(first["messages"][0]["content"])
        self.assertEqual(set(initial), {"authorized_case", "task"})
        self.assertEqual(initial["authorized_case"], self.runtime.case)

    def test_invented_child_write_tool_is_rejected(self):
        handler = PolicyDelegation(self.runtime, BadChildClient(), "replay", max_rounds=1)
        result = self.delegate(handler)
        self.assertTrue(result["is_error"])
        self.assertIsNone(self.runtime.submitted)
        self.assertFalse((self.out / "proposal.json").exists())
        trace = [json.loads(line) for line in (self.out / "trace.jsonl").read_text().splitlines()]
        denied = [row for row in trace if row["event"] == "subagent_tool_completed"]
        self.assertTrue(denied[0]["is_error"])

    def test_child_evidence_does_not_replace_parent_validation(self):
        self.delegate()
        self.assertEqual(self.runtime.seen, set())
        with self.assertRaises(Rejected):
            self.runtime.dispatch("submit_proposal", {"quantity": 240, "rationale": "Specialist advice",
                                                       "alternatives": ["Wait for a supplier quote."]})

    def test_delegation_budget_stops_additional_model_calls(self):
        handler = PolicyDelegation(self.runtime, self.client, "replay", max_delegations=1)
        self.assertFalse(self.delegate(handler)["is_error"])
        calls = len(self.client.requests)
        self.assertTrue(self.delegate(handler)["is_error"])
        self.assertEqual(len(self.client.requests), calls)

    def test_malformed_task_is_rejected_before_model_call(self):
        result = self.delegation.call(ReplayBlock("delegate_policy_review", {"task": "Read rules", "quantity": 240}, "bad-task"))
        self.assertTrue(result["is_error"])
        self.assertEqual(self.client.requests, [])

    def test_full_parent_child_flow_stops_for_human_review(self):
        result = run_vertex(self.runtime, client=self.client, delegation=self.delegation, model="replay-model")
        self.assertEqual(result["status_at_export"], "AWAITING_REVIEW")
        self.assertEqual(result["quantity"], 240)
        self.assertEqual(self.client.counts, {"parent": 4, "child": 2})
        with self.assertRaises(Rejected):
            simulate_execution(self.out, self.runtime.services)
        trace = [json.loads(line) for line in (self.out / "trace.jsonl").read_text().splitlines()]
        child_events = [row for row in trace if row["event"].startswith("subagent_")]
        self.assertTrue(child_events)
        self.assertEqual(len({row["child_id"] for row in child_events}), 1)
        requests = [row for row in trace if row["event"].endswith("model_requested")]
        self.assertTrue(all(row["actual_model_call"] is False for row in requests))


if __name__ == "__main__":
    unittest.main()
