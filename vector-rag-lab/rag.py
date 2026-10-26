"""Chunk practice policies, search text vectors and return evidence with citations.

The default TF-IDF path is local and extractive. Bedrock dense embeddings and
LLM generation are optional and require --allow-cloud-calls in the CLI.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent / "uae-delivery-assistant-lab/data/policies.json"
STOPWORDS = set("a an and are as at be can could do does for from how i in is it me my of on or should that the this to was we what when which with would".split())


def tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", text.lower())
            if word not in STOPWORDS]


@dataclass(frozen=True)
class Chunk:
    id: str
    policy_id: str
    title: str
    text: str
    source: str
    start_word: int
    end_word: int


def chunk_documents(documents: list[dict], size: int = 55, overlap: int = 10) -> list[Chunk]:
    if isinstance(size, bool) or not isinstance(size, int) or size < 5:
        raise ValueError("Chunk size must be an integer of at least 5 words.")
    if isinstance(overlap, bool) or not isinstance(overlap, int) or not 0 <= overlap < size:
        raise ValueError("Overlap must be an integer between zero and size minus one.")
    seen = set()
    chunks = []
    for document in documents:
        policy_id = document["id"]
        if not isinstance(policy_id, str) or not policy_id.strip() or policy_id in seen:
            raise ValueError("Policy IDs must be unique, nonempty strings.")
        seen.add(policy_id)
        title, text = document["title"], document["text"]
        if not isinstance(title, str) or not isinstance(text, str) or not text.strip():
            raise ValueError("Policies need a title and nonempty text.")
        words = text.split()
        for start in range(0, len(words), size - overlap):
            end = min(start + size, len(words))
            chunks.append(Chunk(f"{policy_id}:{start:04d}", policy_id, title,
                                " ".join(words[start:end]),
                                f"uae-delivery-assistant-lab/data/policies.json#{policy_id}", start, end))
            if end == len(words):
                break
    if not chunks:
        raise ValueError("The corpus must contain at least one policy.")
    return chunks


def unit_vector(values: list[float]) -> list[float]:
    if not values or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("Vectors must contain finite numbers.")
    norm = math.hypot(*values)
    return [v / norm for v in values] if norm else [0.0] * len(values)


class LocalTfidf:
    """Small lexical vector baseline, not a pretrained semantic embedding model."""
    name = "local-tfidf"

    def __init__(self, texts: list[str]):
        if not texts:
            raise ValueError("At least one document is required.")
        counts = [Counter(tokens(text)) for text in texts]
        self.vocabulary = sorted({term for count in counts for term in count})
        if not self.vocabulary:
            raise ValueError("The corpus has no searchable words.")
        self.idf = {term: math.log((1 + len(texts)) / (1 + sum(term in c for c in counts))) + 1
                    for term in self.vocabulary}

    def embed(self, text: str) -> list[float]:
        counts = Counter(tokens(text))
        values = [(1 + math.log(counts[t])) * self.idf[t] if counts[t] else 0.0
                  for t in self.vocabulary]
        # Retain unknown-word mass in a separate coordinate. Dropping it would
        # turn an unrelated question with one shared word into a strong match.
        unseen_mass = sum(((1 + math.log(n)) * max(self.idf.values())) ** 2
                          for term, n in counts.items() if term not in self.idf)
        return unit_vector(values + [math.sqrt(unseen_mass)])


class VectorIndex:
    def __init__(self, chunks: list[Chunk], embedder):
        if not chunks:
            raise ValueError("Cannot index an empty corpus.")
        self.chunks, self.embedder = chunks, embedder
        self.vectors = [unit_vector(embedder.embed(c.title + " " + c.text)) for c in chunks]
        dimensions = {len(v) for v in self.vectors}
        if len(dimensions) != 1:
            raise ValueError("Embedding dimensions must be consistent.")
        self.dimensions = dimensions.pop()

    def search(self, query: str, k: int = 3, min_score: float = 0.18) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            raise ValueError("Use a nonempty question of at most 4000 characters.")
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 10:
            raise ValueError("k must be an integer from 1 to 10.")
        if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not math.isfinite(min_score) or not 0 <= min_score <= 1:
            raise ValueError("The score threshold must be between zero and one.")
        query_vector = unit_vector(self.embedder.embed(query))
        if len(query_vector) != self.dimensions:
            raise ValueError("Query and document embedding dimensions differ.")
        if not any(query_vector):
            return []
        hits = []
        for chunk, vector in zip(self.chunks, self.vectors):
            score = sum(a * b for a, b in zip(query_vector, vector))
            if score > 0 and score >= min_score:
                hits.append({"chunk": asdict(chunk), "score": round(score, 6)})
        return sorted(hits, key=lambda h: (-h["score"], h["chunk"]["id"]))[:k]


def answer_question(index: VectorIndex, question: str, generator=None, min_score: float = 0.18) -> dict:
    hits = index.search(question, min_score=min_score)
    if not hits:
        return {"status": "insufficient_evidence", "answer": "No sufficiently matching policy was found. Ask a human to review the question.",
                "citations": [], "retrieval_backend": index.embedder.name,
                "generation": "none", "hits": []}
    if generator is None:
        chosen = hits[0]["chunk"]
        response = {"answer": chosen["text"], "citations": [chosen["id"]]}
        generation = "extractive_local_demo"
    else:
        response = generator.generate(question, hits)
        generation = "bedrock_converse"
    allowed = {hit["chunk"]["id"] for hit in hits}
    if not isinstance(response, dict) or set(response) != {"answer", "citations"} or not isinstance(response["answer"], str) or not response["answer"].strip():
        raise ValueError("An answer must contain exactly answer and citations.")
    cited = response["citations"]
    if not isinstance(cited, list) or not cited or any(not isinstance(c, str) or c not in allowed for c in cited):
        raise ValueError("Citations must identify retrieved chunks.")
    evidence = [{"chunk_id": c, "source": next(h["chunk"]["source"] for h in hits if h["chunk"]["id"] == c)}
                for c in dict.fromkeys(cited)]
    return {"status": "answered", "answer": response["answer"], "citations": evidence,
            "retrieval_backend": index.embedder.name, "generation": generation,
            "free_text_requires_review": generator is not None, "hits": hits}


def make_index(backend: str = "local", allow_cloud_calls: bool = False, client=None) -> VectorIndex:
    documents = json.loads(CORPUS.read_text(encoding="utf-8"))
    chunks = chunk_documents(documents)
    if backend == "local":
        embedder = LocalTfidf([c.title + " " + c.text for c in chunks])
    elif backend == "bedrock":
        if not allow_cloud_calls:
            raise ValueError("Bedrock requires explicit --allow-cloud-calls.")
        from bedrock import TitanEmbeddings
        embedder = TitanEmbeddings(client=client)
    else:
        raise ValueError("Unknown retrieval backend.")
    return VectorIndex(chunks, embedder)


def evaluate(index: VectorIndex) -> dict:
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        result = answer_question(index, case["question"])
        actual = [hit["chunk"]["policy_id"] for hit in result["hits"]]
        passed = result["status"] == case["status"] and (case["policy_id"] is None or case["policy_id"] in actual)
        results.append({"id": case["id"], "passed": passed, "retrieved_policy_ids": actual})
    return {"backend": index.embedder.name, "cases": len(results), "passed": sum(r["passed"] for r in results),
            "criterion": "Expected policy appears in top 3, or the retriever abstains on the supplied out-of-scope case",
            "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(), "results": results,
            "live_model_answer_quality_measured": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="Can the assistant issue a refund?")
    parser.add_argument("--backend", choices=["local", "bedrock"], default="local")
    parser.add_argument("--generator", choices=["extractive", "bedrock"], default="extractive")
    parser.add_argument("--allow-cloud-calls", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    try:
        if args.generator == "bedrock" and not args.allow_cloud_calls:
            raise ValueError("Bedrock generation requires explicit --allow-cloud-calls.")
        if args.evaluate and args.generator != "extractive":
            raise ValueError("The retrieval evaluation uses extractive answers, not LLM generation.")
        index = make_index(args.backend, args.allow_cloud_calls)
        if args.evaluate:
            result = evaluate(index)
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] == result["cases"] else 1
        generator = None
        if args.generator == "bedrock":
            from bedrock import BedrockGenerator
            generator = BedrockGenerator()
        print(json.dumps(answer_question(index, args.question, generator), indent=2))
        return 0
    except (ValueError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
