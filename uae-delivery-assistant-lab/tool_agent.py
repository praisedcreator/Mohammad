"""Advanced exercise: a real model-requested function call followed by an answer."""
import argparse
import json
import time

from delivery_assistant import (SYSTEM_PROMPT, build_context, fingerprint, order_ids,
                                request_payload, save_evidence)
from providers import finish_foundry, foundry_client, foundry_format, required_env

TOOLS = [{
    "type": "function", "name": "lookup_order",
    "description": "Read one historical delivery record and retrieve its practice policies.",
    "strict": True,
    "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}},
                   "required": ["order_id"], "additionalProperties": False},
}]


def checked_tool_arguments(call, question: str) -> str:
    if call.name != "lookup_order":
        raise ValueError("The model requested an unknown tool.")
    args = json.loads(call.arguments)
    ids = order_ids(question)
    if (not isinstance(args, dict) or set(args) != {"order_id"}
            or len(ids) != 1 or args["order_id"] != ids[0]):
        raise ValueError("Tool arguments must match the one explicit order ID in the question.")
    return args["order_id"]


def run_tool_agent(question: str, client=None) -> dict:
    if len(order_ids(question)) != 1:
        raise ValueError("Use exactly one explicit order ID for this advanced exercise.")
    own_client = client is None
    client = client or foundry_client()
    start = time.perf_counter()
    instructions = SYSTEM_PROMPT + "\nUse lookup_order to obtain the record and policy evidence."
    history = [{"role": "user", "content": question}]
    try:
        first = client.responses.create(
            model=required_env("AZURE_OPENAI_DEPLOYMENT"), instructions=instructions,
            input=history, tools=TOOLS,
            tool_choice={"type": "function", "name": "lookup_order"},
            parallel_tool_calls=False, max_output_tokens=4096, store=False,
        )
        if first.status != "completed":
            raise ValueError("The tool-selection response was incomplete.")
        calls = [item for item in first.output if item.type == "function_call"]
        if len(calls) != 1:
            raise ValueError("Expected exactly one function call.")
        selected_id = checked_tool_arguments(calls[0], question)
        # build_context performs the actual lookup and policy retrieval in Python.
        context = build_context(question)
        history.extend(first.output)  # Preserve reasoning items too, when supplied.
        history.append({"type": "function_call_output", "call_id": calls[0].call_id,
                        "output": request_payload(context)})
        final = client.responses.create(
            model=required_env("AZURE_OPENAI_DEPLOYMENT"), instructions=instructions,
            input=history, tools=TOOLS, tool_choice="none", parallel_tool_calls=False,
            text=foundry_format(), max_output_tokens=4096, store=False,
        )
        answer, metadata = finish_foundry(final, context)
        metadata["logical_model_requests"] = 2
        metadata["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            first_usage = getattr(first.usage, field, None)
            last_usage = metadata[field]
            metadata[field] = first_usage + last_usage if first_usage is not None and last_usage is not None else None
        return {"provider": "foundry-tool-agent", "question": question,
                "answer": answer.model_dump(), "metadata": metadata, "context": context,
                "context_sha256": fingerprint(request_payload(context)),
                "instructions_sha256": fingerprint(instructions),
                "tool_trace": [{"tool": "lookup_order", "arguments": {"order_id": selected_id},
                                "result_found": context["order"] is not None}],
                "checks": {"schema_and_record_fields_valid": True,
                           "free_text_requires_human_review": True}}
    finally:
        if own_client:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="What do the records say about ORD-2002?")
    args = parser.parse_args()
    try:
        result = run_tool_agent(args.question)
    except Exception as exc:
        parser.exit(1, f"Tool-agent run failed ({type(exc).__name__}): {exc}\n")
    print(json.dumps(result["answer"], indent=2))
    print(f"Tool trace: {json.dumps(result['tool_trace'])}")
    print(f"Evidence: {save_evidence(result, 'tool-agent')}")


if __name__ == "__main__":
    main()
