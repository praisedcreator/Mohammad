"""Boundary, retrieval and real AWS SDK contract checks; no network calls."""
from contextlib import contextmanager
from io import BytesIO
import json
import math
import unittest
from unittest.mock import patch

from rag import Chunk, LocalTfidf, VectorIndex, answer_question, chunk_documents, evaluate, make_index, unit_vector
from bedrock import BedrockGenerator, TitanEmbeddings, runtime_client


class RetrievalTests(unittest.TestCase):
    def test_chunk_overlap_and_source_offsets(self):
        chunks = chunk_documents([{"id":"T1","title":"Title","text":"one two three four five six seven eight nine ten eleven twelve"}], 5, 2)
        self.assertEqual([(c.start_word,c.end_word) for c in chunks],[(0,5),(3,8),(6,11),(9,12)])
        self.assertEqual(chunks[1].text,"four five six seven eight")
        self.assertTrue(chunks[0].source.endswith("#T1"))
        self.assertEqual(len(set(c.id for c in chunks)),4)

    def test_invalid_chunk_settings(self):
        for size, overlap in [(4,0),(5,5),(True,0),(5,-1),(5,False)]:
            with self.subTest(size=size,overlap=overlap), self.assertRaises(ValueError):
                chunk_documents([{"id":"T","title":"x","text":"some text"}],size,overlap)

    def test_duplicate_policy_ids_rejected(self):
        with self.assertRaises(ValueError):
            chunk_documents([{"id":"T","title":"x","text":"some text"}]*2)

    def test_bad_corpus_rejected(self):
        for docs in [[],[{"id":"T","title":"x","text":""}]]:
            with self.subTest(docs=docs),self.assertRaises(ValueError):chunk_documents(docs)

    def test_vectors_normalize_and_reject_invalid_numbers(self):
        self.assertEqual(unit_vector([3,4]),[0.6,0.8])
        self.assertEqual(unit_vector([0,0]),[0,0])
        for vector in [[],[True],[float("nan")],[float("inf")],["bad"]]:
            with self.subTest(vector=vector),self.assertRaises(ValueError):unit_vector(vector)

    def test_all_explicit_retrieval_cases(self):
        result=evaluate(make_index())
        self.assertEqual(result["passed"],result["cases"],result)

    def test_extracts_actual_evidence_and_valid_source(self):
        result=answer_question(make_index(),"Can the assistant issue a refund?")
        self.assertEqual(result["generation"],"extractive_local_demo")
        self.assertIn("human",result["answer"].lower())
        self.assertTrue(result["citations"][0]["chunk_id"].startswith("P007:"))
        self.assertEqual(result["answer"],result["hits"][0]["chunk"]["text"])

    def test_out_of_scope_does_not_call_generator(self):
        class ForbiddenGenerator:
            def generate(self,*args):raise AssertionError("must not call model")
        result=answer_question(make_index(),"Explain photosynthesis chlorophyll sunlight.",ForbiddenGenerator())
        self.assertEqual(result["status"],"insufficient_evidence")
        self.assertEqual(result["citations"],[])

    def test_unknown_words_are_not_silently_discarded(self):
        e=LocalTfidf(["refund refund policy"])
        pure=e.embed("refund")
        other=e.embed("refund chlorophyll photosynthesis sunlight")
        self.assertLess(other[e.vocabulary.index("refund")],pure[e.vocabulary.index("refund")])
        self.assertGreater(other[-1],0)

    def test_input_limits(self):
        index=make_index()
        for question in ["", " "*3,"x"*4001,None]:
            with self.subTest(question=question),self.assertRaises(ValueError):index.search(question)
        for kwargs in [{"k":True},{"k":0},{"k":11},{"min_score":float("nan")},{"min_score":True},{"min_score":1.2}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):index.search("refund",**kwargs)

    def test_inconsistent_embedding_dimensions_rejected(self):
        class BrokenEmbedder:
            def embed(self,text):return [1] if text.startswith("one") else [1,0]
        chunks=[Chunk("a","a","one","x","s",0,1),Chunk("b","b","two","x","s",0,1)]
        with self.assertRaises(ValueError):VectorIndex(chunks,BrokenEmbedder())

    def test_query_dimension_mismatch_rejected(self):
        class ChangingEmbedder:
            def embed(self,text):return [1,0] if text.startswith("title") else [1]
        index=VectorIndex([Chunk("a","a","title","x","s",0,1)],ChangingEmbedder())
        with self.assertRaises(ValueError):index.search("query")

    def test_generated_citations_cannot_invent_source(self):
        class BadGenerator:
            def generate(self,*args):return {"answer":"Invented","citations":["P999:0000"]}
        with self.assertRaises(ValueError):answer_question(make_index(),"refund",BadGenerator())

    def test_invalid_generated_shapes_rejected(self):
        for payload in [{"answer":"x","citations":[]},{"answer":"x","citations":"P007:0000"},{"answer":"","citations":["P007:0000"]},{"answer":"x","citations":["P007:0000"],"extra":1}]:
            class Generator:
                def generate(self,*args):return payload
            with self.subTest(payload=payload),self.assertRaises(ValueError):answer_question(make_index(),"refund",Generator())

    def test_aws_backend_requires_explicit_cloud_opt_in(self):
        with patch("bedrock.runtime_client",side_effect=AssertionError("no AWS client")):
            with self.assertRaises(ValueError):make_index("bedrock")


@contextmanager
def stubbed_client():
    import boto3
    from botocore.stub import Stubber
    # Public dummy values only; Stubber intercepts the requests before HTTP.
    client=boto3.client("bedrock-runtime",region_name="us-east-1",
                        aws_access_key_id="unit-test",aws_secret_access_key="unit-test")
    with Stubber(client) as stub:
        yield client,stub
        stub.assert_no_pending_responses()


class BedrockContractTests(unittest.TestCase):
    def test_titan_v2_real_sdk_request_and_response(self):
        vector=[1.0]+[0.0]*255
        with stubbed_client() as (client,stub):
            stub.add_response("invoke_model",{"body":BytesIO(json.dumps({"embedding":vector,"inputTextTokenCount":2}).encode()),"contentType":"application/json"},
                              {"modelId":"amazon.titan-embed-text-v2:0","contentType":"application/json","accept":"application/json","body":json.dumps({"inputText":"refund policy","dimensions":256,"normalize":True})})
            self.assertEqual(TitanEmbeddings(client).embed("refund policy"),vector)

    def test_titan_rejects_wrong_dimensions(self):
        with stubbed_client() as (client,stub):
            stub.add_response("invoke_model",{"body":BytesIO(b'{"embedding":[1,2]}'),"contentType":"application/json"})
            with self.assertRaises(ValueError):TitanEmbeddings(client).embed("refund")

    def test_titan_rejects_zero_vectors(self):
        with stubbed_client() as (client,stub):
            stub.add_response("invoke_model",{"body":BytesIO(json.dumps({"embedding":[0]*256}).encode()),"contentType":"application/json"})
            with self.assertRaises(ValueError):TitanEmbeddings(client).embed("refund")

    def test_titan_rejects_invalid_dimension_config(self):
        with self.assertRaises(ValueError):TitanEmbeddings(client=object(),dimensions=128)

    def test_titan_service_error_propagates(self):
        from botocore.exceptions import ClientError
        with stubbed_client() as (client,stub):
            stub.add_client_error("invoke_model",service_error_code="AccessDeniedException")
            with self.assertRaises(ClientError):TitanEmbeddings(client).embed("refund")

    def test_converse_real_sdk_contract(self):
        from botocore.stub import ANY
        payload={"answer":"A human must review refunds.","citations":["P007:0000"]}
        response={"output":{"message":{"role":"assistant","content":[{"text":json.dumps(payload)}]}},"stopReason":"end_turn",
                  "usage":{"inputTokens":10,"outputTokens":8,"totalTokens":18},"metrics":{"latencyMs":12}}
        hit={"chunk":{"id":"P007:0000","title":"Refund","text":"Human review required."}}
        with stubbed_client() as (client,stub):
            stub.add_response("converse",response,{"modelId":"test-model","system":ANY,"messages":[{"role":"user","content":[{"text":json.dumps({"question":"refund?","evidence":[{"id":"P007:0000","title":"Refund","text":"Human review required."}]})}]}],"inferenceConfig":{"maxTokens":700,"temperature":0.0}})
            self.assertEqual(BedrockGenerator(client,"test-model").generate("refund?",[hit]),payload)

    def test_truncated_model_response_rejected(self):
        class FakeClient:
            def converse(self,**kwargs):return {"stopReason":"max_tokens"}
        with self.assertRaises(ValueError):BedrockGenerator(FakeClient(),"test-model").generate("q",[{"chunk":{"id":"P1","title":"t","text":"x"}}])

    def test_missing_model_configuration_rejected(self):
        with patch.dict("os.environ",{"BEDROCK_MODEL_ID":""}):
            with self.assertRaises(ValueError):BedrockGenerator(client=object())

    def test_missing_region_configuration_rejected(self):
        with patch.dict("os.environ",{"AWS_REGION":"","AWS_DEFAULT_REGION":""}):
            with self.assertRaises(ValueError):runtime_client()


if __name__ == "__main__":unittest.main()
