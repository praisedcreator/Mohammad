"""Run the supplied 20 cases and save automated checks plus a human-review worksheet."""
import argparse
import json
from statistics import median

from delivery_assistant import ROOT, build_context, run_context, save_evidence


def evaluate(provider: str, limit: int | None = None) -> dict:
    cases = json.loads((ROOT / "data" / "evaluation_cases.json").read_text(encoding="utf-8"))
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be positive.")
        cases = cases[:limit]
    rows = []
    for case in cases:
        row = {"case_id": case["id"], "question": case["question"],
               "manual_check": case["manual_check"], "human_review_pass": None,
               "human_notes": ""}
        try:
            result = run_context(provider, build_context(case["question"]))
            actual = result["answer"]
            passed = all(actual[key] == case[key] for key in ("status", "action_code"))
            row.update(automated_contract_pass=passed, result=result)
        except Exception as exc:
            row.update(automated_contract_pass=False, error_type=type(exc).__name__, error=str(exc))
        rows.append(row)
        print(f"{case['id']}: {'PASS' if row['automated_contract_pass'] else 'FAIL'}")
    latencies = [r["result"]["metadata"]["latency_ms"] for r in rows
                 if "result" in r and "latency_ms" in r["result"]["metadata"]]
    passed_count = sum(r["automated_contract_pass"] for r in rows)
    return {"provider": provider, "mode": "offline" if provider == "offline" else "live",
            "cases": len(rows), "automated_pass_count": passed_count,
            "automated_pass_rate": passed_count / len(rows),
            "median_valid_response_latency_ms": median(latencies) if latencies else None,
            "human_review_complete": False,
            "interpretation": "Automated schema, record fields and citation-ID checks only. Review prose and policy support separately. Offline success is not cloud-model evidence.",
            "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["offline", "foundry", "vertex"], default="offline")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    report = evaluate(args.provider, args.limit)
    print(f"Automated checks: {report['automated_pass_count']}/{report['cases']}")
    print(f"Report and human-review worksheet: {save_evidence(report, 'evaluation-' + args.provider)}")
    return 0 if report["automated_pass_count"] == report["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
