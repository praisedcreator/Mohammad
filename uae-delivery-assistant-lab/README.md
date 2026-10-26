# UAE Delivery Assistant Hands On Lab

Build an assistant that helps a support employee read delivery records and choose a sensible next step. Use Microsoft Foundry for the main AI application, then send the same task to Google Cloud to see what changes when you switch providers.

The explanations assume you are new to AI application development. Allow about 3 to 5 hours if your cloud accounts are ready. Commands below use Windows PowerShell and Python 3.10 or newer.

By the end, you should have a working Foundry prototype, one saved successful Google Cloud response, and a written platform-choice rationale based on your evidence.

## What you are building

Imagine a support employee who has two things on their desk: an order register and a small policy handbook. Your program finds the correct order, opens the relevant handbook sections, and gives those facts to the AI. The AI writes a clear explanation. Python checks important fields before showing the answer.

For example, a customer asks, **"Where is ORD-2002?"** The assistant can see that the practice record says Abu_Dhabi, stock not ready, and delivered late. It should answer along these lines:

> ORD-2002 was recorded as late. Ask dispatch to review the delivery, and check stock availability before offering a new estimate. These records do not show the current location or arrival time.

The program does not contact dispatch. It gives a support employee advice about what to do next.

```text
Question
   |
Python looks up the order and retrieves relevant practice policies
   |
Managed AI model in Microsoft Foundry, or the equivalent Google Cloud call
   |
Python checks the response fields and policy references
   |
Answer for a support employee + a saved evidence file
```

The AI model runs in the cloud. The Python application and small policy search run on your computer. This lab uses managed model inference; it does not deploy a separate hosted agent or a managed search index.

## The terms in everyday language

| Term | Plain meaning | Example in this lab |
| --- | --- | --- |
| Model | The AI service that reads instructions and writes an answer | A text model you select in Foundry |
| Deployment | Your named way to access a particular model configuration | `delivery-assistant` |
| API call | Your program asking a service to do a job | Send the order facts and request an answer |
| Endpoint | The service's web address | A URL ending in `/openai/v1/` |
| Prompt | The job instructions you give the AI | Use only the supplied record and policies |
| RAG | Find useful reference material before asking the AI to answer | Retrieve the late-delivery policy |
| Tool | An ordinary function the application can run | `lookup_order("ORD-2002")` |
| JSON schema | A form defining the fields an answer must contain | Always return `order_id`, `status`, and `policy_ids` |
| Tokens | The pieces of text the model processes | Input and output usage contributes to inference cost |
| Evaluation | Checking answers against cases with known expectations | An unknown order must return `not_found` |

## Step 1 Understand the supplied data

The `data` folder contains exact copies of your two CSVs, with 12 records each.

| File | Meaning of its last column | Example |
| --- | --- | --- |
| `uae_delivery_classification.csv` | `Delivered_Late` is a recorded Yes or No outcome | ORD-2002: Yes |
| `uae_delivery_regression.csv` | `Delivery_Hours` is a recorded duration | ORD-3002: 26.0 hours |

ORD-2002 and ORD-3002 are different records. Their matching final digits do not authorize joining them. The duration file supplies no promised deadline, so 26 hours alone does not establish whether a delivery was late.

These files have no current GPS position or live ETA. This is a record-interpretation lab, not a model-training or delivery-prediction exercise. The small datasets are useful for learning lookup, grounding, structured output and testing.

Open `data/policies.json`. It contains ten **fictional policies written for this lab**, not UAE law or an actual company's service commitments. For example:

* P002: For an order recorded as late, recommend a dispatch review.
* P003: If stock was not ready, check availability before proposing a new estimate.
* P005: Recorded hours are historical; they are not a live arrival estimate.
* P007: Refund requests require human review; the assistant cannot issue refunds.

**Checkpoint:** Explain why ORD-2002 can be called "recorded late" but ORD-3002 cannot automatically be called late.

## Step 2 Prepare Python

Extract the ZIP, open PowerShell in the extracted `uae-delivery-assistant-lab` folder, and run:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$labPython = ".\.venv\Scripts\python.exe"
```

The virtual environment is a separate toolbox for this project. These commands do not require changing PowerShell's execution policy. If `py` is unavailable but `python --version` works, use `python` in the first two commands.

The `$labPython` variable is a shortcut for the project's Python executable. If you open a new PowerShell window, set it again after returning to the project folder.

Useful project files:

```text
delivery_assistant.py     Lookup, policy retrieval, answer checks, and command line
providers.py              Foundry and Google Cloud model calls
tool_agent.py             Advanced model-requested function call exercise
compare.py                Run both providers with the same retrieved evidence
evaluate.py               Run the 20 supplied evaluation cases
data/                    Your CSVs, fictional policies, and evaluation cases
tests/                   Local tests with mocked cloud HTTP responses
examples/                Offline example outputs, clearly labelled
.env.example             Configuration template
```

## Step 3 Practise without a cloud account

```powershell
& $labPython delivery_assistant.py --provider offline --question "What do the records say about ORD-2002?"
```

The program prints `Mode: offline`, an answer, and the path to a JSON evidence file in `results`. Offline mode uses ordinary Python rules. It makes zero AI model calls and is not evidence of a successful cloud connection.

The important output fields should be:

```json
{
  "order_id": "ORD-2002",
  "status": "recorded_late",
  "action_code": "contact_dispatch",
  "recorded_delivery_hours": null,
  "needs_human": true,
  "policy_ids": ["P001", "P002", "P003"]
}
```

`null` means no value is available for that field. `contact_dispatch` is a proposed next step, not a statement that someone has been contacted.

Try these questions:

```powershell
& $labPython delivery_assistant.py --question "Is ORD-3002 arriving in 26 hours?"
& $labPython delivery_assistant.py --question "Look up ORD-9999."
& $labPython delivery_assistant.py --question "Where is my order?"
```

| Question | Expected lesson |
| --- | --- |
| ORD-3002 arriving in 26 hours? | 26.0 is a past recorded duration, not time remaining |
| ORD-9999 | Say not found; do not create an order |
| Where is my order? | Ask for an order ID |

## Step 4 See how lookup and retrieval work

```powershell
& $labPython delivery_assistant.py --question "What should support do about ORD-2002?" --show-context
```

"Context" means the facts handed to the AI. You should see the ORD-2002 record and policies P001, P002 and P003. This command makes no model call, regardless of the selected provider.

The two useful Python functions are:

```python
from delivery_assistant import lookup_order, search_policy

print(lookup_order("ORD-2002"))
print(search_policy("stock not ready late delivery", limit=3))
```

For the complete request, `build_context()` includes rules required by the record's fields, then adds relevant supplementary keyword-search results. Think of this as opening the right handbook pages before asking someone to explain them.

This is a small local retrieval baseline. It uses rules and word matching, not embeddings or Azure AI Search. You can inspect the retrieved evidence directly instead of treating retrieval as a hidden step.

## Step 5 Set up Microsoft Foundry

1. Open the [Foundry portal](https://ai.azure.com/) and select your Azure subscription.
2. Create or use a Foundry resource and project for this lab. A convenient project name is `uae-delivery-lab`.
3. In the model catalog, choose an available Azure OpenAI text model that supports **Responses API, structured outputs and function calling**. A small supported model is suitable. Confirm the model's capabilities, region, deployment type and displayed price in your account.
4. Deploy it with a name such as `delivery-assistant`. The code needs this **deployment name**, which can differ from the underlying model name.
5. Copy the resource's model inference address. This lab expects a base URL such as `https://YOUR-RESOURCE.openai.azure.com/openai/v1/`. Do not paste the project URL ending in `/api/projects/...`.

For this route, Microsoft documents model deployments and the `/openai/v1/` inference address separately from project APIs. [Deployment guidance](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/create-model-deployments), [inference endpoints](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/endpoints).

Copy the configuration template:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your editor and fill these values:

```text
AZURE_OPENAI_BASE_URL=https://YOUR-RESOURCE.openai.azure.com/openai/v1/
AZURE_OPENAI_DEPLOYMENT=delivery-assistant
AZURE_OPENAI_REGION=YOUR-ACTUAL-RESOURCE-REGION
AZURE_OPENAI_API_KEY=
```

Use one authentication route:

* **Microsoft Entra ID:** Leave the key blank, install the Azure CLI if needed, and run `az login`. An administrator must grant the appropriate inference role on the Foundry resource; the current keyless guide specifies Cognitive Services User. Creating deployments needs separate management permission. [Keyless setup](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/configure-entra-id).
* **Local lab key:** Put your own resource key in `AZURE_OPENAI_API_KEY` if key authentication is enabled for your resource. Keep `.env` local; do not include it in submitted evidence or shared code. Microsoft recommends Entra ID for production inference. [Authentication options](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/endpoints).

**Checkpoint:** The template values have been replaced, and you can identify your model deployment name and model inference base URL.

## Step 6 Run the Foundry assistant

```powershell
& $labPython delivery_assistant.py --provider foundry --question "What should support do about ORD-2002?"
```

This time you should see `Mode: live`. The evidence file contains the answer, retrieved record, policies, model information, token usage and request duration. A successful run exits without an error and has `schema_and_record_fields_valid: true`.

The essential model call in `providers.py` is:

```python
response = client.responses.create(
    model=deployment_name,
    instructions=SYSTEM_PROMPT,
    input=request_payload(context),
    text=foundry_format(),
    max_output_tokens=4096,
    store=False,
)
```

In everyday language: "Use my deployed model, read these instructions and facts, and fill in the answer form." `client`, `deployment_name` and `context` are prepared by the supplied adapter; this excerpt is an explanation, not a separate script to run.

Foundry's Responses API accepts a JSON schema under `text.format`. [Structured output syntax](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs).

The program checks the order ID, historical status, duration, action code, human-review flag and citation IDs. A well-formed JSON answer can still contain misleading prose, so read the actual sentences too.

**Example to inspect:** "Stock was not ready" is a recorded fact. "Stock shortage definitely caused the delay" is an unsupported conclusion. The answer must preserve that difference.

## Step 7 Add a model-requested tool call

```powershell
& $labPython tool_agent.py --question "What should support do about ORD-2002?"
```

In Step 6, Python performs retrieval before asking the model to write. Here, the model first requests `lookup_order` with an order ID. Python checks that the requested ID matches the question, performs the lookup, and returns the record and policies. The model then writes its answer.

Think of the AI saying, **"Please open the file for ORD-2002,"** and Python acting as the clerk who opens it. The AI does not gain permission to open arbitrary files or perform refunds.

You should see a tool trace resembling:

```json
{
  "tool": "lookup_order",
  "arguments": {"order_id": "ORD-2002"},
  "result_found": true
}
```

The exercise deliberately forces one lookup so you can observe the complete function-call cycle. It makes two logical model requests, while the basic assistant makes one. The supplied code preserves tool-call identifiers and any reasoning items when sending the follow-up. [Microsoft function-call example](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses).

**Checkpoint:** Point to the tool arguments, the Python lookup, the returned evidence and the final answer in the saved file.

## Step 8 Make the equivalent Google Cloud call

The equivalent exercise uses the same question, retrieved record, policies, instructions and response schema. The provider and selected model change; the task stays the same.

Google's current documentation calls this Cloud route **Gemini Enterprise Agent Platform**, formerly Vertex AI. The tested SDK accepts both `enterprise` and `vertexai`; this project uses the current `enterprise=True` form. It selects the Google Cloud backend, not a standalone Gemini Developer API key route. [Google SDK client setup](https://github.com/googleapis/python-genai#readme).

1. In Google Cloud, select or create a project with billing enabled.
2. Enable the API for this route. The service identifier remains `aiplatform.googleapis.com`.
3. Ensure your account has permission to call models. Google's quickstart specifies `roles/aiplatform.user` or equivalent permissions.
4. Install the Google Cloud CLI and authenticate for local application use:

```powershell
gcloud init
gcloud config set project YOUR-GOOGLE-CLOUD-PROJECT-ID
gcloud services enable aiplatform.googleapis.com
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR-GOOGLE-CLOUD-PROJECT-ID
```

`application-default login` gives your Python client an identity it can use. It is a separate credential setup from signing the CLI in. [Google authentication guide](https://docs.cloud.google.com/docs/authentication/provide-credentials-adc), [Cloud model quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/start).

Fill the remaining `.env` values:

```text
GOOGLE_CLOUD_PROJECT=YOUR-ACTUAL-PROJECT-ID
GOOGLE_CLOUD_LOCATION=global
VERTEX_MODEL=YOUR-AVAILABLE-GEMINI-MODEL-ID
```

Choose a text model with structured-output support that is available in that project and location. Copy its model ID from the current console. `global` is convenient for this practice exercise; choose a location and processing arrangement that meets your requirements before using real customer data.

```powershell
& $labPython delivery_assistant.py --provider vertex --question "What should support do about ORD-2002?"
```

The core Google call in the adapter is:

```python
from google import genai
from google.genai import types

client = genai.Client(
    enterprise=True,
    project=project_id,
    location=location,
    http_options=types.HttpOptions(api_version="v1"),
)
response = client.models.generate_content(
    model=model_id,
    contents=request_payload(context),
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_json_schema=DeliveryAnswer.model_json_schema(),
        automatic_continuation=False,
    ),
)
```

The supplied `providers.py` includes the imports, environment loading, timeouts, retry settings, validation and cleanup around this explanation. [Google JSON schema examples](https://github.com/googleapis/python-genai#json-response-schema).

Now compare the providers against one frozen context:

```powershell
& $labPython compare.py --question "What should support do about ORD-2002?"
```

**Checkpoint:** Save a comparison file with `both_completed: true` and `same_context: true`. Different wording is acceptable; the order facts and policy meaning must agree. One successful call proves integration, not that either platform is better overall.

## Step 9 Test normal and difficult questions

First check the local program:

```powershell
& $labPython -m unittest discover -s tests -v
& $labPython evaluate.py --provider offline
```

The package was checked with Python 3.12.5: 12 tests passed, including real SDK serialization through mocked HTTP, and all 20 offline evaluation cases passed. Mocked HTTP supplies a pretend service response without contacting a cloud model.

Start cloud evaluation with three cases, then run the full set when ready. Each basic case sends one logical model request, with possible SDK retries:

```powershell
& $labPython evaluate.py --provider foundry --limit 3
& $labPython evaluate.py --provider vertex --limit 3
& $labPython evaluate.py --provider foundry
& $labPython evaluate.py --provider vertex
```

The report includes a review prompt for each answer. Automated checks cover the answer form, selected record fields and citation IDs. They do not establish that every sentence is true or that every citation supports the prose.

Read each answer and record a human pass or fail in the worksheet:

* Are all factual claims supported by the selected order and policies?
* Does it distinguish a historical duration from a current ETA?
* Does it avoid claiming that a message was sent or a refund was issued?
* Does it say when information is missing?
* Is the next step understandable to a support employee?

For example, E19 asks the assistant to claim that a refund has already been issued. A correct answer must resist that instruction and recommend human review.

## Step 10 Write the platform-choice rationale

For this lab, **Microsoft Foundry is the primary platform and Google Cloud is the portability comparison**. Keep that learning-design decision separate from a production recommendation.

Use this worked rationale as your starting point:

> I selected Microsoft Foundry for the primary UAE delivery assistant because the lab needs a managed model endpoint and a clear path to agent development, evaluation and tracing. The application keeps order lookup, policy retrieval and factual checks in Python, which makes the business logic easy to inspect and reuse. I used Google Cloud for an equivalent model-call exercise with the same retrieved evidence and response schema. This tests how much application code can be reused across providers. For production, I would compare task quality, cost per accepted answer, response time, identity integration and approved processing locations. I would not claim a platform is cheaper, faster or more accurate from one call.

Foundry's broader models, agents and observability capabilities are documented by Microsoft. Whether those capabilities reduce work for your organization is an architectural judgment to test against your own environment. [Foundry overview](https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry).

Complete this worksheet using your live evidence. Mark unmeasured items as "not measured".

| Criterion | Foundry evidence | Google Cloud evidence | How to decide |
| --- | --- | --- | --- |
| Task quality | Automated checks plus human-approved answers | Same cases and human review | Prefer correct, supported answers |
| Cost | Selected model's current rates and actual billable usage | Same calculation using its own rates | Compare cost per accepted task, not raw token counts |
| Latency | Median recorded duration over the shared cases | Same measurement method | Test from the same machine; repeat before making a broad claim |
| Identity and integration | Work needed to connect Azure identities and existing systems | Work needed to connect Google identities and existing systems | Prefer the route that fits the actual operating environment |
| Data location | Selected region and deployment processing terms | Selected location and processing terms | Meet the required location constraints first |
| Portability | Shared lookup, policies, schema and test cases | Changes required in the provider adapter | Identify provider-specific features that would need replacement |

For a simple token-priced inference estimate:

```text
Estimated cost = billable input tokens / 1,000,000 * applicable input rate
               + billable output tokens / 1,000,000 * applicable output rate

Cost per accepted task = total applicable cost / number of human-accepted answers
```

Use the selected models' current billing definitions, including any cache or reasoning-token treatment. Logs from successful requests alone do not capture every possible charge from failed calls, retries or additional services; reconcile with provider billing for a real cost comparison. If no answer passes review, cost per accepted task is undefined.

Finish your own rationale with this evidence sentence:

> On the shared ___ cases, Foundry produced ___ human-accepted answers and Google Cloud produced ___. Median valid-response durations were ___ and ___. Estimated cost per accepted task was ___ and ___, using rates checked on ___. I recommend ___ because ___; the remaining uncertainty is ___.

The blanks intentionally contain no invented benchmark results.

## Step 11 Submit evidence and clean up

Your submission should include:

1. A successful Foundry answer and, for the advanced exercise, its tool trace.
2. A successful Google Cloud answer or a comparison file showing both calls completed.
3. The evaluation report with your human-review notes.
4. Your completed platform-choice rationale, naming actual models and locations.

Live cloud calls were not performed when this starter was prepared. The included examples are offline outputs. Complete Steps 6 and 8 to obtain your own successful cloud-call evidence.

When finished, review and remove only the cloud resources you created specifically for this lab and no longer need. Check for any continuing search, storage, hosting or provisioned-capacity charges if you added extra services. Keep the original CSVs and your learning evidence.

## Troubleshooting

| Symptom | What it usually means | Next step |
| --- | --- | --- |
| `Fill ... in .env` | A placeholder or required setting is still missing | Check the named setting and rerun |
| Foundry 401 or 403 | Wrong key, missing role, wrong tenant or blocked endpoint access | Check authentication, resource scope and your network configuration |
| Foundry 404 | Deployment name or inference URL does not match your resource | Copy both from the actual deployment |
| Unsupported model or schema | The selected deployment lacks a required feature | Select a model supporting Responses, structured output and function calling |
| Google default credentials error | Python has no usable application credentials | Run `gcloud auth application-default login` |
| Google permission or project error | Wrong project, API disabled, missing role or quota-project permission | Check the active project, API and access roles |
| 429 or temporary service failure | A quota or capacity limit was reached | Reduce test volume; the adapters have bounded retries, then report failure |
| Incomplete model response | Output budget was exhausted or generation was blocked | Inspect the service response; if appropriate, adjust the output budget or selected model |
| Factual validation fails | The model contradicted a checked record field or citation requirement | Review the context and prompt; do not treat the failed output as a successful answer |

## Further advanced practice

After the core lab works, replace keyword retrieval with an approved managed search service, compare retrieval methods on the same cases, add tracing, or connect a real order service through a read-only tool. Keep the small local implementation as a baseline so you can tell whether an extra service improves the result.

Sources and API examples were checked on 22 October 2026. Model availability and portal labels can vary by account and region; the code deliberately keeps model IDs and deployment names in your configuration.
