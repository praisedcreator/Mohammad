# Inventory MCP server and procurement review skill

Version **1.0.0**. A working local Python MCP server, a portable Agent Skills package, saved proposals, operational traces, and a separate human-review demonstration. Use **Codex or Claude Code** as the coding client. The server uses the official **MCP Python SDK 2.3.0**.

All inventory is fictional. This package makes no model API calls and no ERP writes. Your coding client supplies the AI model when you interact with its tools. The automated smoke test is a scripted MCP client, not an AI decision-making test.

## Start here: Windows / PowerShell

Extract the ZIP and open a terminal in the `inventory-mcp-starter` folder. Python 3.11+ is required; the included lock was tested on Windows with Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v test_inventory.py
.\.venv\Scripts\python.exe smoke_test.py
```

The smoke test launches a real MCP server subprocess, discovers its six tools, evaluates a valid and invalid transfer, saves a proposal, verifies safe retries and reads its trace. Default test data is temporary. For an inspectable saved run:

```powershell
.\.venv\Scripts\python.exe smoke_test.py --db .runtime\inventory.sqlite --report .runtime\latest-demo.json
```

On macOS/Linux, use `python3` and `.venv/bin/python` in place of the Windows interpreter path. The Windows-only `pywin32` dependency has a platform marker in the lock file. Only Windows was exercised for this release.

## Connect Codex

```powershell
.\.venv\Scripts\python.exe configure_client.py codex
```

This creates project-local `.codex/config.toml` and copies the skill into `.agents/skills/inventory-review`. Open **this project folder** in Codex, trust the project when prompted by the client, and reload its MCP connections. The connection starts `server.py` over STDIO using your virtual environment. Global Codex settings are unchanged.

Try this in the coding client's chat:

> Use $inventory-review to investigate the demo Dubai shortage. Check the inventory and procurement policy, evaluate a suitable transfer, and save a proposal for human review. Show the proposal ID, hash, calculations and status.

Codex may prefix tool names with the MCP server name. Verify the `inventory-review` server is connected in the client's MCP settings. If your client version does not load project settings, add the same command and arguments shown in `.codex/config.toml` through its MCP settings UI.

## Connect Claude Code

```powershell
.\.venv\Scripts\python.exe configure_client.py claude
```

This creates project-local `.mcp.json` and copies the skill into `.claude/skills/inventory-review`. Start Claude Code in this folder and enable the project's MCP connection when the client asks. Invoke `/inventory-review`, or request the same inventory review in plain language. Use `configure_client.py both` to prepare both clients.

Run the configuration script again after moving the project, using its new virtual environment. Generated settings contain absolute paths and are excluded from source control. If a generated file already differs, the script asks you to review it instead of overwriting it.

## What each tool does

| Tool | Purpose |
|---|---|
| `get_inventory()` | Read stock, reservations, demand, route and supplier lead time for the fixed demo case |
| `get_policy()` | Read structured policy limits and the supporting excerpt |
| `evaluate_transfer(quantity)` | Check coverage, source protection, pack size and cost |
| `create_transfer_proposal(quantity, rationale, alternatives, request_id)` | Recheck the rules and save an `AWAITING_REVIEW` proposal |
| `get_transfer_proposal(proposal_id)` | Read the exact saved proposal and current status |
| `get_trace(limit=50, proposal_id="")` | Read recent tool activity and review events |

The server also provides the `inventory://transfer-policy` MCP resource. Every tool returns structured JSON. Read tools log their activity. Inputs are typed and bounded; a retry with the same `request_id` and identical content returns the same proposal. Changed content needs a new ID. The six-tool registry contains no approval or execution tools.

## The layman's example

Dubai has **80 available units** and uses **40 a day**. Abu Dhabi has **600 available** and uses **30 a day**. A transfer takes one day and costs AED 300. Policy requires seven days of stock at Dubai after arrival and at least seven days at Abu Dhabi.

For **240 units**, Dubai has `80 - 40 + 240 = 280` units at arrival: **seven days**. Abu Dhabi has `600 - 240 - 30 = 330`: **eleven days**. The proposal passes the stock and AED 500 cost limits, then waits for procurement review. A 400-unit transfer fails source protection and destination overstock checks.

The calculator assumes constant demand and no inbound receipts. Fixed fixture timestamps mean “read at”, not “fresh live inventory”. See the skill's `references/transfer-policy.md` for the supported scope.

## Human review and local simulation

The following is a **demo-only** review workflow. The reviewer name is a label supplied at the command line, not an authenticated identity. These commands are intended for a person inspecting the proposal. A coding agent should run a review or simulation only when explicitly instructed by the user.

After saving the inspectable smoke-test run above:

```powershell
$demoRun = Get-Content -LiteralPath .runtime\latest-demo.json -Raw | ConvertFrom-Json
$proposalId = $demoRun.proposal.proposal_id
$proposalHash = $demoRun.proposal.proposal_hash

# Inspect the saved proposal before deciding.
.\.venv\Scripts\python.exe manage.py show $proposalId

# A human reviewer chooses approve or reject for this exact hash.
.\.venv\Scripts\python.exe manage.py review $proposalId --decision approve --expected-hash $proposalHash --reviewer demo-procurement-reviewer --comment "Reviewed the demo evidence and assumptions"

# Optional: create a local receipt after approval; real inventory is unchanged.
.\.venv\Scripts\python.exe manage.py simulate $proposalId

# Export recent operational events.
.\.venv\Scripts\python.exe manage.py trace | Set-Content -Encoding utf8 .runtime\trace.jsonl
```

Use `--decision reject` to demonstrate rejection. Simulation requires approval of the exact unexpired proposal. Changed inventory or policy requires a new proposal and review. Repeated simulation returns the same receipt. There is no external stock movement or stock reservation. Local SQLite and JSONL records are editable demo logs, not tamper-proof production audit storage.

## Where data is saved

Default database: `.runtime/inventory.sqlite`, resolved from the server's own folder, independent of the client's working directory. Set `INVENTORY_DB` to override it, or use `manage.py --db <path> ...`. Proposals and event logs persist across server restarts. `manage.py show` exports a proposal as JSON; `manage.py trace` exports up to 500 recent events as JSONL.

`examples/mcp-smoke.json` and `examples/mcp-legacy.json` capture the tested tool results. `examples/cli-review.json` records an automated demonstration of the review CLI; it is not an authenticated human approval. These are historical demonstrations: their one-hour proposal expiry is intentional. Run a fresh smoke test before trying the review commands. The source bundle does not include a live database or credentials.

`VALIDATION.json` records the release checks: 13 business/configuration tests, skill validation, current and legacy STDIO integration, and the local review CLI. The MCP connection was exercised with the SDK client. Interactive Codex/Claude Code model sessions, real service adapters and cloud deployment were not tested.

## Source layout and versioning

- `server.py`: MCP tool registration and structured responses.
- `business.py`: deterministic checks reused from the earlier inventory-agent example.
- `store.py`: SQLite proposal/trace storage, review and local simulation.
- `manage.py`: separate demo reviewer and exporter.
- `configure_client.py`: portable project-local client setup.
- `skills/inventory-review/`: canonical `SKILL.md` and policy reference.
- `requirements.txt` and `requirements.lock.txt`: pinned SDK and tested dependency versions.
- `test_inventory.py`, `smoke_test.py`: business checks and real STDIO integration test.
- `VERSION`, `CHANGELOG.md`: release identification.

This source release is committed in a local Git repository and tagged `v1.0.0`. The sibling `inventory-mcp-v1.0.0.bundle` preserves that commit and tag. To restore Git history from the release ZIP:

```powershell
git clone ..\inventory-mcp-v1.0.0.bundle ..\inventory-mcp-history
```

For a new release, update `VERSION`, the skill metadata and changelog; run the tests, commit and tag the new version. Client configuration is generated locally instead of embedding another computer's paths in the release.

## Extending the demo to your existing systems

Replace `InventoryStore.evidence()` with your authorized analytics/retrieval adapters, and replace the constant-demand calculator with your existing inventory projection service. Preserve typed fields, authoritative policy limits, evidence IDs/versions/timestamps and freshness checks. Keep proposal storage and trace capture durable. A live executor needs authenticated procurement review, scoped service accounts, stock reservation/concurrency checks and an idempotent ERP integration; the sample CLI is not that service.

Use Codex or Claude Code to build and try this package. Google Cloud's Vertex AI services / Gemini Enterprise Agent Platform can host a later managed agent. Perplexity Search can be an optional tool for public research; stock and approval evidence should come from your internal systems. No Google, Anthropic, OpenAI or Perplexity credentials are bundled or required for the server tests.

## Format and API references

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Agent Skills documented format](https://agentskills.io/specification)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Codex skill discovery](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Google Cloud agent platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview)
- [Perplexity APIs](https://docs.perplexity.ai/docs/getting-started/overview)
