# Skills and Implementation Evidence

This map helps reviewers find the code, checks and teaching material behind the portfolio. Operational AWS/Azure employment experience remains in the professional profile; a provider adapter alone does not establish a production deployment.

| Role requirement | Inspect | Evidence and scope |
| --- | --- | --- |
| Python application development | [Delivery assistant](../uae-delivery-assistant-lab/delivery_assistant.py), [vector search](../vector-rag-lab/rag.py) | CLI applications, structured data, validation and tests |
| LLM applications and RAG | [Provider adapters](../uae-delivery-assistant-lab/providers.py), [vector RAG](../vector-rag-lab/README.md) | Policy retrieval, context construction, chunking and cited answers; local and optional cloud paths |
| AI agents and tool calling | [Agent loop](../inventory-agent/agent.py), [function-calling lab](../uae-delivery-assistant-lab/tool_agent.py) | Bounded orchestration and explicit tool boundaries with scripted tests |
| MCP and integrations | [MCP server](../inventory-mcp-starter/server.py), [STDIO smoke client](../inventory-mcp-starter/smoke_test.py) | Six tools, real subprocess transport, persistence and separate review |
| AWS integration | [Bedrock adapters](../vector-rag-lab/bedrock.py), [contract tests](../vector-rag-lab/test_rag.py) | Titan V2 embeddings and Converse; AWS SDK stubs, no live AWS result claimed |
| Azure and Google Cloud integration | [Shared provider adapters](../uae-delivery-assistant-lab/providers.py) | Foundry and Google Cloud request/response contracts |
| Data and business applications | [Dashboard](../retail-dashboard-tutorial/app.py), [exception SQL](../retail-dashboard-tutorial/02_exception_view.sql) | Inventory exceptions, data-quality checks and purchase-order drill-down; configured cloud prototype |
| Containers and delivery | [Dockerfile](../retail-dashboard-tutorial/Dockerfile), [CI workflow](../.github/workflows/ci.yml) | Container definition and credential-free checks on Windows/Linux runners |
| Evaluation and troubleshooting | [Evaluation](evaluation.md), [deployment guide](deployment-guide.md), [AWS guide](aws-bedrock.md) | Reproducible checks with clear local, mocked and live distinctions |
| Workshops and enablement | [Workshop plan](workshop-guide.md), [guided demo](guided-demo.md) | Preparation, exercises, checkpoints and explanation prompts for technical/business audiences |
| Collaboration and documentation | [Contribution guide](../CONTRIBUTING.md), [architecture](architecture.md) | Reproduction steps, review expectations, diagrams and documented design choices |
