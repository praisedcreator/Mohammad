# Generative AI and Cloud Engineering Portfolio

[![Portfolio checks](https://github.com/praisedcreator/Mohammad/actions/workflows/ci.yml/badge.svg)](https://github.com/praisedcreator/Mohammad/actions/workflows/ci.yml)

Practical Python proofs of concept and technical enablement material by **Mohammad Khalique**. Explore LLM applications, RAG, tool-using agents and cloud integrations through source code, guided demonstrations and reproducible checks.

![Portfolio architecture overview](docs/assets/overview.svg)

**Reviewer shortcuts:** [Skills and code evidence](docs/skills-evidence.md) · [Guided demo](docs/guided-demo.md) · [Architecture](docs/architecture.md) · [Evaluation](docs/evaluation.md)

## Projects

| Project | What it demonstrates | Implementation scope |
| --- | --- | --- |
| [Delivery support assistant](uae-delivery-assistant-lab/) | Python, local policy retrieval for RAG, structured answers, function calling and provider adapters | Training POC with Microsoft Foundry and Google Cloud adapters; local evaluation and mocked HTTP tests |
| [Inventory review agent](inventory-agent/) and [MCP toolkit](inventory-mcp-starter/) | Bounded tool orchestration, deterministic business checks, durable proposals and human review | Fictional inventory, offline replay and separate review/simulation; optional Claude-on-Vertex adapter |
| [Retail inventory dashboard](retail-dashboard-tutorial/) | Streamlit, BigQuery SQL, exception inspection, source drill-down and Docker configuration | Configurable cloud prototype with Gemini/Vertex AI integration |
| [Vector RAG and AWS Bedrock](vector-rag-lab/) | Chunking, cosine search, source citations, abstention, Titan V2 dense embeddings and Converse | Credential-free TF-IDF demo; optional AWS adapters with real SDK stub tests |

## Start here

Run a guided local example with Python 3.12, from the repository root:

```powershell
python tools/demo.py
```

It shows a cited policy answer and an unrelated question that returns insufficient evidence. This command requires no packages, credentials or cloud requests. Read the [walkthrough](docs/guided-demo.md) for expected behavior and the other project demonstrations.

### Run all checks

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r uae-delivery-assistant-lab/requirements.txt -r inventory-mcp-starter/requirements.txt -r vector-rag-lab/requirements-aws.txt
.\.venv\Scripts\python.exe tools/run_checks.py
```

On macOS/Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`. The workflow runs unit tests, mocked provider/SDK contracts, offline retrieval cases, a real MCP STDIO integration check and documentation link checks. GitHub Actions runs the same command on Windows and Linux; the badge above shows its actual current status.

Read each project README before using a cloud path. Model calls require your own account configuration. Inspect the evidence and limitations before interpreting an output as a real business result.

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

- **LLMs and RAG:** keyword and vector baselines, document chunks, visible context, policy references, cited answers and insufficient-evidence handling.
- **AI agents:** allowlisted tools, bounded loops, proposal persistence, human review and retry-safe operations.
- **Multi-cloud:** Microsoft Foundry and Google Cloud adapters, plus AWS Bedrock embedding and generation adapters. AWS/Azure operational employment experience remains separate from these prototypes.
- **APIs and containers:** provider integrations, HTTP adapter contracts, a real MCP server and a Streamlit Dockerfile.
- **Technical enablement:** guided labs, checkpoints, a workshop plan, architecture explanations and troubleshooting guidance.
- **Evaluation:** documented local test records with a clear distinction between offline checks and live model quality.

## Documentation

- [Architecture and design decisions](docs/architecture.md)
- [Evaluation evidence and limits](docs/evaluation.md)
- [Workshop and demonstration guide](docs/workshop-guide.md)
- [Deployment and troubleshooting guide](docs/deployment-guide.md)
- [Job requirements mapped to code and evidence](docs/skills-evidence.md)
- [Guided portfolio demonstration](docs/guided-demo.md)
- [AWS Bedrock setup](docs/aws-bedrock.md)
- [Contribution guide](CONTRIBUTING.md)

These are educational prototypes, not production deployments. The delivery records and inventory fixtures contain practice data. Cloud request contracts are tested with stubs/mocks; no live cloud success, customer savings or model-quality benchmark is inferred from them. Credentials, runtime state and private configuration are excluded.

## License

The original code and documentation are available under the [MIT license](LICENSE). Dependencies, third-party models, SDKs and linked resources retain their own terms.

[Professional portfolio](https://sites.google.com/view/mohammad-khalique-ai-training/home) · [LinkedIn](https://www.linkedin.com/in/mohammad-khalique-8398aa1a/)
