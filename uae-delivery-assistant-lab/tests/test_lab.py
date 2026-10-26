"""Tests use real SDKs with mocked HTTP; they never contact a cloud endpoint."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import OpenAI

from delivery_assistant import (ROOT, build_context, load_orders, lookup_order,
                                offline_answer, validate_answer)
from providers import call_foundry, call_vertex, foundry_client
from tool_agent import checked_tool_arguments, run_tool_agent


def foundry_response(context, *, call=False):
    output = ([{"type": "function_call", "id": "fc_test", "call_id": "call_test",
                "name": "lookup_order", "arguments": '{"order_id":"ORD-2002"}',
                "status": "completed"}] if call else [
        {"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
         "content": [{"type": "output_text", "text": offline_answer(context).model_dump_json(),
                      "annotations": []}]}])
    return {"id": "resp_test", "object": "response", "created_at": 1792627200,
            "status": "completed", "model": "mock-model-version", "output": output,
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}


class CoreTests(unittest.TestCase):
    def test_two_datasets_remain_distinct(self):
        orders = load_orders()
        self.assertEqual(len(orders), 24)
        self.assertEqual(orders["ORD-2002"]["Delivered_Late"], "Yes")
        self.assertNotIn("Delivered_Late", orders["ORD-3002"])
        self.assertEqual(orders["ORD-3002"]["Delivery_Hours"], 26.0)
        self.assertIsNone(lookup_order("../../secrets"))

    def test_all_twenty_cases_against_explicit_expectations(self):
        cases = json.loads((ROOT / "data" / "evaluation_cases.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 20)
        for case in cases:
            with self.subTest(case=case["id"]):
                answer = offline_answer(build_context(case["question"]))
                self.assertEqual(answer.status, case["status"])
                self.assertEqual(answer.action_code, case["action_code"])

    def test_unknown_order_does_not_borrow_another_record(self):
        context = build_context("Look up ORD-9999")
        answer = offline_answer(context)
        self.assertIsNone(context["order"])
        self.assertEqual(answer.order_id, "ORD-9999")
        self.assertEqual(answer.status, "not_found")

    def test_historical_duration_is_not_an_eta(self):
        answer = offline_answer(build_context("Is ORD-3002 arriving in 26 hours?"))
        self.assertEqual(answer.status, "historical_duration")
        self.assertEqual(answer.recorded_delivery_hours, 26.0)
        self.assertIn("not a current ETA", answer.answer)

    def test_rejects_hallucinated_fields_and_citations(self):
        context = build_context("Review ORD-2002")
        original = offline_answer(context).model_dump()
        for field, value in (("status", "recorded_not_late"),
                             ("order_id", "ORD-3002"),
                             ("recorded_delivery_hours", 26.0),
                             ("policy_ids", ["P999"])):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_answer(json.dumps({**original, field: value}), context)

    def test_refund_request_requires_human_even_if_not_late(self):
        answer = offline_answer(build_context("Please refund ORD-2001 immediately."))
        self.assertEqual(answer.status, "recorded_not_late")
        self.assertTrue(answer.needs_human)
        self.assertIn("no refund has been issued", answer.proposed_action)

    def test_rejects_unrequested_tool_order(self):
        call = SimpleNamespace(name="lookup_order", arguments='{"order_id":"ORD-3002"}')
        with self.assertRaises(ValueError):
            checked_tool_arguments(call, "Review ORD-2002")
        call.name = "issue_refund"
        with self.assertRaises(ValueError):
            checked_tool_arguments(call, "Review ORD-3002")

    @patch.dict("os.environ", {"AZURE_OPENAI_BASE_URL": "https://test.services.ai.azure.com/api/projects/test"})
    def test_rejects_project_url_in_model_inference_client(self):
        with self.assertRaises(ValueError):
            foundry_client()


class SDKContractTests(unittest.TestCase):
    @patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "lab-deployment"})
    def test_foundry_serializes_and_parses_real_sdk_request(self):
        context, seen = build_context("Review ORD-2002"), []
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=foundry_response(context))
        with OpenAI(api_key="dummy-test-key", base_url="https://test.openai.azure.com/openai/v1/",
                    http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
            answer, metadata = call_foundry(context, client=client)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].url.path, "/openai/v1/responses")
        body = json.loads(seen[0].content)
        self.assertEqual(body["model"], "lab-deployment")
        self.assertFalse(body["store"])
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(answer.status, "recorded_late")
        self.assertEqual(metadata["total_tokens"], 150)

    @patch.dict("os.environ", {"VERTEX_MODEL": "mock-gemini", "GOOGLE_CLOUD_LOCATION": "global"})
    def test_google_cloud_serializes_and_parses_real_sdk_request(self):
        try:
            from google import genai
            from google.genai import types
            from google.oauth2.credentials import Credentials
        except ImportError:
            self.skipTest("Install requirements.txt to run the Google SDK contract test.")
        context, seen = build_context("Review ORD-2002"), []
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={
                "candidates": [{"content": {"role": "model", "parts": [
                    {"text": offline_answer(context).model_dump_json()}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 101, "candidatesTokenCount": 51,
                                  "totalTokenCount": 152},
                "modelVersion": "mock-gemini-version", "responseId": "google_test",
            })
        with genai.Client(enterprise=True, project="lab-test-project", location="global",
                          credentials=Credentials(token="dummy-test-token"),
                          http_options=types.HttpOptions(api_version="v1",
                              client_args={"transport": httpx.MockTransport(handler)})) as client:
            answer, metadata = call_vertex(context, client=client)
        self.assertEqual(len(seen), 1)
        self.assertIn("aiplatform.googleapis.com", seen[0].url.host)
        self.assertIn("/projects/lab-test-project/locations/global/", seen[0].url.path)
        self.assertTrue(seen[0].url.path.endswith("/models/mock-gemini:generateContent"))
        body = json.loads(seen[0].content)
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(answer.status, "recorded_late")
        self.assertEqual(metadata["total_tokens"], 152)

    @patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "lab-deployment"})
    def test_real_tool_call_round_trip_preserves_tool_output(self):
        context, seen = build_context("Review ORD-2002"), []
        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=foundry_response(context, call=len(seen) == 1))
        with OpenAI(api_key="dummy-test-key", base_url="https://test.openai.azure.com/openai/v1/",
                    http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
            result = run_tool_agent("Review ORD-2002", client=client)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0]["tool_choice"]["name"], "lookup_order")
        self.assertFalse(seen[0]["parallel_tool_calls"])
        outputs = [item for item in seen[1]["input"] if item.get("type") == "function_call_output"]
        self.assertEqual(outputs[0]["call_id"], "call_test")
        self.assertEqual(json.loads(outputs[0]["output"])["order"]["Order_ID"], "ORD-2002")
        self.assertEqual(result["metadata"]["total_tokens"], 300)
        self.assertEqual(result["metadata"]["logical_model_requests"], 2)

    @patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "lab-deployment"})
    def test_incomplete_output_is_not_reported_as_success(self):
        context = build_context("Review ORD-2002")
        fixture = foundry_response(context)
        fixture["status"] = "incomplete"
        with OpenAI(api_key="dummy-test-key", base_url="https://test.openai.azure.com/openai/v1/",
                    http_client=httpx.Client(transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, json=fixture)))) as client:
            with self.assertRaises(ValueError):
                call_foundry(context, client=client)


if __name__ == "__main__":
    unittest.main()
