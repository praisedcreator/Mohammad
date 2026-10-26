"""Exercise the real MCP server through a separate STDIO subprocess.

This is a scripted tool client, not an AI/model test. It needs no model API key.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import uuid
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent


async def exercise(db_path, mode="auto"):
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")],
                                  cwd=str(ROOT), env={"INVENTORY_DB": str(Path(db_path).resolve())})
    async with Client(params, mode=mode, read_timeout_seconds=15) as client:
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        expected = {"get_inventory", "get_policy", "evaluate_transfer", "create_transfer_proposal",
                    "get_transfer_proposal", "get_trace"}
        assert names == expected, names
        async def call(name, arguments=None):
            result = await client.call_tool(name, arguments or {})
            assert not result.is_error, result.content
            assert result.structured_content is not None, result.content
            return result.structured_content
        inventory = await call("get_inventory")
        policy = await call("get_policy")
        assert inventory["inventory"]["sku"] == "SKU-DEMO-100"
        assert policy["policy"]["pack_size"] == 10
        allowed = await call("evaluate_transfer", {"quantity": 240})
        assert allowed["allowed"] and allowed["source_cover_days_after_arrival"] == 11
        unsafe = await call("evaluate_transfer", {"quantity": 400})
        assert not unsafe["allowed"] and "source_floor_breached" in unsafe["violations"]
        invalid = await client.call_tool("evaluate_transfer", {"quantity": True})
        assert invalid.is_error, "Boolean quantities must not be treated as one unit"
        request = {"quantity": 240,
                   "rationale": "A one-day transfer gives Dubai seven days of cover while preserving eleven days at Abu Dhabi.",
                   "alternatives": ["Standard supplier replenishment takes ten days; request a confirmed expedited quote."],
                   "request_id": "smoke-" + str(uuid.uuid4())}
        proposal = await call("create_transfer_proposal", request)
        assert proposal["status"] == "AWAITING_REVIEW" and not proposal["execution_performed"]
        retry = await call("create_transfer_proposal", request)
        assert retry["proposal_id"] == proposal["proposal_id"] and retry["idempotent_retry"]
        blocked = await client.call_tool("create_transfer_proposal", {**request, "quantity": 400})
        assert blocked.is_error, "Changed content must not reuse an idempotency key"
        missing = await client.call_tool("approve_transfer", {})
        assert missing.is_error, "No approval tool may be available"
        fetched = await call("get_transfer_proposal", {"proposal_id": proposal["proposal_id"]})
        assert fetched["proposal_hash"] == proposal["proposal_hash"]
        trace = await call("get_trace", {"limit": 100})
        assert any(event["event"] == "proposal_created" for event in trace["events"])
        resources = await client.list_resources()
        assert any(str(item.uri) == "inventory://transfer-policy" for item in resources.resources)
        await client.read_resource("inventory://transfer-policy")
        return {"result": "PASS", "transport": "stdio subprocess", "client_mode": mode, "protocol_version": client.protocol_version,
                "sdk_version": __import__("importlib.metadata", fromlist=["version"]).version("mcp"),
                "tools": sorted(names), "actual_model_call": False, "proposal": proposal, "trace": trace["events"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Persist into this database; otherwise use a temporary test database")
    parser.add_argument("--report", type=Path, help="Save full JSON evidence including the proposal and trace")
    parser.add_argument("--mode", choices=["auto", "legacy"], default="auto", help="Also verify older MCP client compatibility")
    args = parser.parse_args()
    if args.db:
        result = asyncio.run(exercise(args.db, args.mode))
    else:
        test_root = (ROOT / ".runtime" / "tests").resolve()
        test_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="inventory-mcp-", dir=test_root) as directory:
            if not Path(directory).resolve().is_relative_to(test_root):
                raise RuntimeError("Test cleanup must remain in this project's test workspace")
            result = asyncio.run(exercise(Path(directory) / "inventory.sqlite", args.mode))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("result", "transport", "protocol_version", "sdk_version", "tools", "actual_model_call")}, indent=2))


if __name__ == "__main__":
    main()
