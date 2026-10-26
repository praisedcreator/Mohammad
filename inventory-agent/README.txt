MODEL-LED INVENTORY EXCEPTION AGENT

This starter uses one orchestration model: Claude called through Google Vertex AI.
Perplexity Search is a tool for public research. Python dispatches approved read
tools, validates business rules, stores a proposal, and records an operational
trace. A separate human review step precedes a local transfer simulation.

The included example uses fictional inventory, a scripted offline replay, and
demo reviewer identities. No real model call or ERP write happens in demo mode.
The optional live model adapter and HTTP service adapter need your configuration.

ARCHITECTURE

Exception event -> Python runtime <-> Claude on Vertex AI
Claude chooses: get_inventory, get_policy, evaluate_transfer,
                optional search_public_logistics, submit_proposal.
Python validates -> proposal + SQLite state + JSONL trace -> WAITING FOR REVIEW.
Separate review -> approve/reject exact proposal hash.
Approved + fresh evidence -> local simulation, with an idempotent mock receipt.
There is no approve or execute tool in the model's tool registry.

FILES

agent.py          Explicit tool schemas, bounded tool loop, checks, proposal,
                  SQLite state, review and simulated procurement transfer.
services.py       Fictional services, example read-only HTTP adapters, and the
                  Perplexity Search REST call. All service URLs are configured
                  by the application, never supplied by the model.
fixtures.json     Example case, stock, route, cost and versioned procurement policy.
test_agent.py     Offline protocol and business-boundary tests.
examples/...      Generated proposal and trace; initial state is AWAITING_REVIEW.

RUN WITHOUT CREDENTIALS (Python 3.10+; only the standard library is required)

Run these commands from the inventory-agent directory:

  python agent.py demo --out runs/demo-001

Inspect runs/demo-001/proposal.json and runs/demo-001/trace.jsonl. The proposal
expires after one hour. Run another demo in a new output directory to refresh it.
The JSON export describes state at export; SQLite is the current state store.

To demonstrate the review boundary in PowerShell:

  $proposalHash = (Get-Content runs/demo-001/proposal.json -Raw | ConvertFrom-Json).proposal_hash
  python agent.py review --out runs/demo-001 --decision approve --reviewer demo-procurement-reviewer --expected-hash $proposalHash --comment "Demo review only"
  python agent.py simulate-execution --out runs/demo-001

Use --decision reject to demonstrate rejection. Re-running simulate-execution
returns the same local receipt. It does not create an ERP document or move stock.
The CLI simulation uses fixtures; production HTTP runs need a real separately
authorized executor and must not be connected to this fixture-only CLI path.

CLI reviewer names and groups are deliberately demo-only. In production, derive
identity and procurement role from a verified Google IAP/OIDC/SSO session; never
trust a reviewer ID or roles sent in a request body. Protect review and execution
as separate services with their own service accounts.

LIVE CLAUDE THROUGH VERTEX (fixture analytics first)

1. Choose a Google Cloud project with billing and Vertex AI enabled. Enable an
   available Claude model in Model Garden and check its supported endpoint/region.
2. Install the SDK in a local virtual environment:

     python -m venv .venv
     .venv/Scripts/python.exe -m pip install -r requirements.txt

   The requirements file intentionally leaves SDK selection to installation;
   pin your evaluated dependency versions before deploying.
3. Authenticate locally with Google Application Default Credentials:

     gcloud auth application-default login

   For a deployed workload, attach a minimally privileged service account.
   The Claude-on-Vertex client uses Google credentials, not an Anthropic API key.
4. Set these environment variables in PowerShell:

     $env:GOOGLE_CLOUD_PROJECT = "your-project-id"
     $env:GOOGLE_CLOUD_LOCATION = "your-supported-region-or-global"
     $env:VERTEX_MODEL = "your-enabled-claude-model-id"

5. Call the actual model, while keeping the inventory fixture:

     .venv/Scripts/python.exe agent.py run --services fixture --out runs/vertex-001

Model output is not accepted as a proposal unless it calls submit_proposal and
passes the runtime's checks. The loop permits ten model rounds and at most 24
tool calls. SDK timeouts/retries and usage/latency traces are configured. Add
an end-to-end deadline and project-specific token/cost ceilings for deployment.

OPTIONAL PERPLEXITY RESEARCH

Set PERPLEXITY_API_KEY securely in the process environment or Secret Manager;
do not paste a key into source files or chat. Set ENABLE_PUBLIC_SEARCH=1.
The runtime then advertises search_public_logistics to Claude. The application
calls POST https://api.perplexity.ai/search, with a fixed public advisory query.
No SKU, quantities, sites, private document text or model-selected query is sent.
Search results retain title, URL, date and snippet; the retrieval time is logged.
Public pages are untrusted context, never authoritative stock or policy evidence.
This uses the Search API, so a second decision-making model is not required.

CONNECT YOUR ANALYTICS AND RETRIEVAL SERVICES

The sibling retail-dashboard-tutorial/02_exception_view.sql already defines
retail_demo.inventory_exceptions in BigQuery. Wrap parameterized reads of that
view and the related daily forecasts/orders behind get_inventory. Preserve its
data-quality flags, reservations, blocked stock, forecast source, confirmed
receipt timing, stock snapshot date and version. The existing dashboard is a
separate example; this starter does not modify it or assume it is deployed.

The HTTP adapter illustrates these JSON contracts:
  GET ANALYTICS_BASE_URL/inventory/context?exception_id=...&sku=...&destination=...&source=...
      -> inventory object shaped like fixtures.json, plus timezone-aware as_of.
  GET RETRIEVAL_BASE_URL/policies/transfer?same-authorized-case-fields
      -> policy object shaped like fixtures.json, plus timezone-aware as_of.

Configure ANALYTICS_BASE_URL and RETRIEVAL_BASE_URL as trusted HTTPS base URLs.
Save an authorized case JSON with exception_id, sku, destination and source.
Run agent.py run --services http --case case.json --out runs/http-001.

Cloud Run service ID tokens in this adapter are minted with the base URL as
audience. Run it with a suitable workload identity/attached service account and
invoker permissions. Local user ADC alone may not mint service-to-service ID
tokens through this helper; use an appropriate impersonation transport for local
integration tests. Never give the model an arbitrary URL, SQL, shell or ERP tool.

Structured policy limits must be authoritative service data, not a model's
interpretation of retrieved prose. Store the policy document ID, version and
excerpt beside those limits so a reviewer can inspect the supporting rule.

CALCULATION SCOPE AND EXAMPLE

The example calculator deliberately supports DEMO_CONSTANT_DEMAND, EA units,
and no inbound receipts. It refuses other forecast sources and nonzero aggregate
inbound supply because those require a time-phased simulation. Replace evaluate
with your existing analytics projection before using real stock or forecasts.
Include demand uncertainty, forecast quality, safety stock, expiry, route dates,
units/packs, confirmed receipts, reservations, and each site's own replenishment.
This example treats daily demand as additional consumption of sellable inventory.

Dubai: on hand 100 - reserved 20 = 80 available; demand 40/day.
Abu Dhabi: on hand 660 - reserved 60 = 600 available; demand 30/day.
Route: one day; transport cost AED 300. Supplier lead time: ten days.
Target: seven days at destination after arrival; source floor: seven days.

Destination at arrival = 80 - 40 = 40.
Required transfer = 7*40 - 40 = 240 units (pack size 10).
Destination after arrival = 40 + 240 = 280 -> seven days of cover.
Source at arrival = 600 - 240 - 30 = 330 -> eleven days of cover.
Cost AED 300 <= policy cap AED 500. Proposal goes to procurement for approval.
A supplier order alone arrives after current destination stock would deplete;
an expedited supplier alternative needs a confirmed quote and lead time.

HUMAN REVIEW AND PRODUCTION EXECUTION

Show the reviewer action/SKU/from/to/quantity/unit, arrival date, demand assumptions,
source/destination projections, cost/currency, evidence IDs/versions/timestamps,
alternatives and the proposal hash. Review actions are approve, reject, or request
a new proposal. Edited quantity/cost/site means a new proposal and new approval.

The starter checks proposal age, exact reviewed hash, procurement role, safe
calculations and unchanged evidence before a simulation. For a real executor:
validate an authenticated approval, re-read current stock and policy, and ask the
ERP to atomically check versions/availability and reserve stock while creating
the transfer request. Use the proposal hash as an idempotency key. Handle ERP
timeouts by checking that key before retrying. Revalidation alone cannot prevent
a concurrent stock change between reading evidence and writing to the ERP.
Creating a request, dispatching goods and receiving stock are distinct ERP events.

Use Cloud Run for the Python service, Pub/Sub for exception events, your existing
BigQuery/retrieval layer for evidence, Cloud SQL/Firestore for proposal/review
state, and structured Cloud Logging/OpenTelemetry for traces. This is a design
mapping, not a deployment created by this starter. Deduplicate exception events
and use transactional state transitions/outbox handling in a deployed service.

TRACE

Events include run ID, tool name/arguments/results, call ID, timestamps, service
latency, model response ID, token usage, versioned evidence, policy checks,
proposal hash, review decision and mock receipt. These are observable business
facts and short rationales, not hidden chain-of-thought. Demo traces explicitly
say actual_model_call=false. The traces contain commercially sensitive evidence:
restrict access/retention, redact organization-specific fields, and never log
credentials. Local JSONL and SQLite are demonstration stores, not immutable or
tamper-proof audit systems; use a protected audit sink/outbox in production.

OPTIONAL SUB-AGENT EXAMPLE

See SUBAGENTS.txt and subagents.py for a parent inventory agent that can delegate
policy research to a separate, read-only specialist session using the same Claude
model API. The original agent stays the default. To run a scripted offline replay:

  python subagents.py --demo --out runs/subagent-demo-001

The specialist reports advice and policy references. The parent performs the
canonical checks and proposal submission, followed by the same human review gate.

TESTS

  python -m unittest -v test_agent.py

Tests exercise business calculations, stale/invalid data, policy protection,
allowlisted tools, missing approval, reviewer authority/hash, rejection, expiry,
changed evidence, idempotency, bounded model calls and Claude's tool-result
protocol using a fake model. Live APIs are not covered by those offline tests.

OFFICIAL REFERENCES (checked 2026-10-15)

https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai
https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/use-claude
https://docs.perplexity.ai/docs/search/quickstart
