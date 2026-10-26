# Amazon Bedrock Setup and Troubleshooting

The [Vector RAG lab](../vector-rag-lab/README.md) adds an AWS integration alongside the existing Microsoft Foundry and Google Cloud examples. It implements Titan Text Embeddings V2 and Converse. The adapters have SDK contract tests; this portfolio contains no verified live AWS inference or deployment result.

## Account preparation

Use an existing AWS account and an approved Bedrock region. Authenticate through AWS SSO or the normal Boto3 credential chain. Select a Converse-compatible model or inference profile available to that account. Check provider requirements and availability in the console before running the example. Do not put credentials in source files or commit a populated `.env`.

For a policy, scope `bedrock:InvokeModel` to the selected Titan model and generation model. If using an inference profile, follow the AWS guidance for the profile and the underlying model resources/regions. The example does not need permission to create infrastructure, edit IAM, write S3 objects or execute inventory changes.

Set `AWS_REGION` and `BEDROCK_MODEL_ID`. The embedding adapter deliberately targets `amazon.titan-embed-text-v2:0` with 256 dimensions; changing to another embedding family requires an adapter change and new contract tests. Do not send private customer documents to this practice lab.

## Verify locally before using AWS

```powershell
cd vector-rag-lab
python -m pip install -r requirements-aws.txt
python -m unittest -v test_rag.py
python rag.py --evaluate
```

Stubber intercepts the AWS SDK requests before HTTP. Passing these tests confirms request and response handling, not model availability, account permissions, live quality, latency or spend. An access-denied test intentionally returns a simulated service error.

## Run and inspect

Use the explicit `--allow-cloud-calls` option shown in the project README. Inspect the returned retrieved passages, citation IDs, answer and generation label. The default run is local and requires no AWS configuration.

For a live comparison, keep the corpus and questions fixed. Record the model ID/inference profile, region, SDK versions, actual request/token usage, latency and a manual review of source support. Save failed examples as well as successful ones. Keep cloud observations separate from the [local test record](validation-enhanced-2026-10-26.json).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing region or model error | Set the environment variables; replace all `YOUR-...` placeholders |
| SDK not installed | Install `requirements-aws.txt` in the Python environment running the lab |
| No credentials | Refresh the approved AWS SSO/profile session |
| Access denied | Check `bedrock:InvokeModel`, region, model access and inference-profile resource scope |
| Model not available | Choose a supported Converse model/profile in the selected region |
| Invalid embedding dimension | Keep document and query embeddings on the same Titan V2 configuration |
| Incomplete or non-JSON answer | The adapter rejects truncation, tool output and non-JSON replies; review the failed response and model configuration |
| Unhelpful retrieval | Inspect chunk text and scores; tune on labelled cases rather than interpreting similarity as confidence |

## Official references

- [Titan embedding request and response format](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html)
- [Boto3 Converse API](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html)
- [AWS SDK credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
- [Inference profile permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-prereq.html)
