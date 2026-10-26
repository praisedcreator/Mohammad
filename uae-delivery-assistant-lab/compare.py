"""Freeze one question and its retrieved evidence, then call both managed models."""
import argparse
import json

from delivery_assistant import build_context, run_context, save_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="What do the records say about ORD-2002?")
    args = parser.parse_args()
    context = build_context(args.question)
    results, failures = [], []
    for provider in ("foundry", "vertex"):
        try:
            result = run_context(provider, context)
            results.append(result)
            print(f"{provider}: validated response; evidence {save_evidence(result, provider)}")
        except Exception as exc:
            failures.append({"provider": provider, "error_type": type(exc).__name__, "error": str(exc)})
            print(f"{provider}: failed ({type(exc).__name__})")
    report = {"comparison": results, "failures": failures,
              "both_completed": len(results) == 2,
              "same_context": len(results) == 2 and results[0]["context_sha256"] == results[1]["context_sha256"],
              "interpretation": "Integration comparison only; a single call cannot establish the better platform."}
    print(json.dumps({k: v for k, v in report.items() if k != "comparison"}, indent=2))
    print(f"Comparison evidence: {save_evidence(report, 'comparison')}")
    return 0 if report["both_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
