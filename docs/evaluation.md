# Evaluation Evidence and Limits

## Latest local verification

[Verification record dated 26 October 2026](validation-2026-10-26.json): 48 unit, business-rule and mocked-HTTP tests passed across the delivery assistant, inventory agent and MCP toolkit. The delivery assistant also passed 20 deterministic offline cases, and the MCP server passed a separate STDIO integration check. These checks use practice data and make no live model calls; they do not measure live model quality or production performance.

## Recorded project checks

| Project | Available evidence | What it establishes |
| --- | --- | --- |
| Delivery assistant | [Local verification](../uae-delivery-assistant-lab/examples/local_verification.json): 12 unit/mocked-HTTP tests and 20 offline evaluation cases passed | Local schema, selected record fields, policy-reference IDs and SDK request serialization |
| Inventory MCP toolkit | [Release validation](../inventory-mcp-starter/VALIDATION.json): 13 business/configuration tests; STDIO integration and review CLI checks passed | Deterministic business rules, proposal persistence, review boundaries and protocol integration |
| Inventory agent | Reproducible local tests in `test_agent.py` and `test_subagents.py` | Business rules and scripted/fake-model tool-loop boundaries |
| Retail dashboard | SQL and application source with explicit data-quality and demand-source flags | Reviewable implementation; no live cloud or trained-forecast result is included |

The JSON records are retained evidence from the original project validation. They are not a fresh live cloud benchmark. All included examples are offline or mocked. Human review of generated prose and live service quality is still a separate evaluation task.

## Live evaluation procedure

1. Freeze the same questions, source evidence and expected answer criteria for each provider.
2. Record model/deployment, processing location, request duration, token usage, retries and validation failures.
3. Review factual claims and citation support, including missing records and conflicting or insufficient policy evidence.
4. Measure accepted-answer rate and latency over repeated cases. Reconcile cost with actual provider billing.
5. Record failed cases and changes before rerunning the same evaluation set.

Do not infer time saved, cost savings or superior quality from a single response. No such figures are invented in this portfolio.
