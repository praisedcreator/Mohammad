"""Run the portfolio's credential-free checks from any working directory."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ("delivery_unit", "uae-delivery-assistant-lab", ["-m","unittest","discover","-s","tests","-v"]),
    ("delivery_offline_cases", "uae-delivery-assistant-lab", ["evaluate.py","--provider","offline"]),
    ("inventory_agent_unit", "inventory-agent", ["-m","unittest","-v","test_agent.py","test_subagents.py"]),
    ("inventory_mcp_unit", "inventory-mcp-starter", ["-m","unittest","-v","test_inventory.py"]),
    ("inventory_mcp_stdio", "inventory-mcp-starter", ["smoke_test.py"]),
    ("vector_rag_unit", "vector-rag-lab", ["-m","unittest","-v","test_rag.py"]),
    ("vector_retrieval_cases", "vector-rag-lab", ["rag.py","--evaluate"]),
]


def check_links():
    errors=[]
    excluded={".git",".venv","__pycache__",".runtime","results","runs"}
    for path in ROOT.rglob("*.md"):
        if excluded.intersection(path.relative_to(ROOT).parts):continue
        text=path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)",text):
            if "://" in target or target.startswith(("#","mailto:")):continue
            local=target.split("#")[0]
            if not (path.parent/local).exists():errors.append(f"{path.relative_to(ROOT)} -> {target}")
    if errors:raise ValueError("Broken relative links:\n"+"\n".join(errors))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    records=[]
    for name,folder,command in CHECKS:
        print(f"\nRunning {name}",flush=True)
        result=subprocess.run([sys.executable,*command],cwd=ROOT/folder,timeout=120)
        records.append({"check":name,"passed":result.returncode==0})
        if result.returncode:
            print(f"FAILED: {name}",file=sys.stderr)
            return result.returncode
    check_links()
    records.append({"check":"documentation_relative_links","passed":True})
    report={"checks":records,"all_passed":True,"actual_cloud_model_calls":False}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("\nAll portfolio checks passed.")
    return 0


if __name__=="__main__":raise SystemExit(main())
