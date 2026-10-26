"""Separate local demo reviewer, simulator and JSON/JSONL exporter."""
from __future__ import annotations

import argparse
import json
import os
import sys

from business import Rejected
from store import InventoryStore, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("INVENTORY_DB", str(ROOT / ".runtime" / "inventory.sqlite")))
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show", help="Read a saved proposal")
    show.add_argument("proposal_id")
    review = commands.add_parser("review", help="Record a demo-only human review; does not move stock")
    review.add_argument("proposal_id")
    review.add_argument("--decision", required=True, choices=["approve", "reject"])
    review.add_argument("--expected-hash", required=True)
    review.add_argument("--reviewer", required=True, help="Demo label, not authenticated identity")
    review.add_argument("--comment", required=True)
    simulate = commands.add_parser("simulate", help="Create a local receipt after approval; never changes stock")
    simulate.add_argument("proposal_id")
    trace = commands.add_parser("trace", help="Print recent operational events as JSONL")
    trace.add_argument("--proposal-id")
    trace.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    store = InventoryStore(args.db)
    try:
        if args.command == "show":
            result = store.get(args.proposal_id)
        elif args.command == "review":
            result = store.review(args.proposal_id, args.expected_hash, args.decision, args.reviewer, args.comment)
        elif args.command == "simulate":
            result = store.simulate(args.proposal_id)
        else:
            for event in store.traces(args.proposal_id, args.limit):
                print(json.dumps(event, ensure_ascii=False))
            return 0
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Rejected as exc:
        store.event("review_cli_" + args.command, "error", {"message": str(exc)}, getattr(args, "proposal_id", None))
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
