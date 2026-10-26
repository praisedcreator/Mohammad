# Generative AI and Cloud Engineering Portfolio

Practical Python proofs of concept and technical enablement material by **Mohammad Khalique**. The projects connect LLM applications, retrieval-augmented generation (RAG), tool-using agents and cloud services with understandable business tasks.

## Projects

| Project | What it demonstrates | Implementation scope |
| --- | --- | --- |
| [Delivery support assistant](uae-delivery-assistant-lab/) | Python, local policy retrieval for RAG, structured answers, function calling and provider adapters | Training POC with Microsoft Foundry and Google Cloud adapters; local evaluation and mocked HTTP tests |
| [Inventory review agent](inventory-agent/) and [MCP toolkit](inventory-mcp-starter/) | Bounded tool orchestration, deterministic business checks, durable proposals and human review | Fictional inventory, offline replay and separate review/simulation; optional Claude-on-Vertex adapter |
| [Retail inventory dashboard](retail-dashboard-tutorial/) | Streamlit, BigQuery SQL, exception inspection, source drill-down and Docker configuration | Configurable cloud prototype with Gemini/Vertex AI integration |

## Start here

1. Read the project README before installing its dependencies. Each project uses its own virtual environment.
2. Start with an offline example or local test. Cloud accounts and model calls are optional and require your own configuration.
3. Inspect the source evidence, test scope and limitations before interpreting any output as a real business result.

### Run the inventory agent without credentials

```powershell
cd inventory-agent
python agent.py demo --out runs/my-demo
python -m unittest -v test_agent.py test_subagents.py
```

### Run the delivery assistant offline

```powershell
cd uae-delivery-assistant-lab
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe delivery_assistant.py --provider offline --question "What do the records say about ORD-2002?"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Engineering and enablement evidence

- **LLMs and RAG:** visible retrieval context, policy references, structured output and checks for missing information.
- **AI agents:** allowlisted tools, bounded loops, proposal persistence, human review and retry-safe operations.
- **Multi-cloud:** reusable Python logic with Microsoft Foundry and Google Cloud model adapters. AWS/Azure operational experience is described in the professional profile, not inferred from these prototypes.
- **APIs and containers:** provider integrations, HTTP adapter contracts, a real MCP server and a Streamlit Dockerfile.
- **Technical enablement:** guided labs, checkpoints, a workshop plan, architecture explanations and troubleshooting guidance.
- **Evaluation:** documented local test records with a clear distinction between offline checks and live model quality.

## Documentation

- [Architecture and design decisions](docs/architecture.md)
- [Evaluation evidence and limits](docs/evaluation.md)
- [Workshop and demonstration guide](docs/workshop-guide.md)
- [Deployment and troubleshooting guide](docs/deployment-guide.md)

These are educational prototypes, not production deployments. The included delivery records and inventory fixtures contain practice data. No live cloud success, customer savings or model-quality benchmark is claimed from an offline test. Credentials, local runtime state and private configuration are excluded.

[Professional portfolio](https://sites.google.com/view/mohammad-khalique-ai-training/home) · [LinkedIn](https://www.linkedin.com/in/mohammad-khalique-8398aa1a/)
