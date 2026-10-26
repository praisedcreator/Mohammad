"""A credential-free guided demonstration; run from any directory."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"vector-rag-lab"))
from rag import answer_question,make_index


def main():
    index=make_index()
    print("Vector RAG demo | local TF-IDF | no cloud requests\n")
    for question in ["Can the assistant issue a refund?","Explain photosynthesis chlorophyll sunlight."]:
        result=answer_question(index,question)
        print(json.dumps({"question":question,"status":result["status"],"answer":result["answer"],
                          "citations":result["citations"],"generation":result["generation"]},indent=2))
    print("\nNext: inspect vector-rag-lab/rag.py or run python tools/run_checks.py after installing test dependencies.")
    return 0


if __name__=="__main__":raise SystemExit(main())
