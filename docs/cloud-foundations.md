# Cloud and Automation Project Guide

These four projects extend the AI portfolio with infrastructure, operational troubleshooting and Python automation. Their validation is credential-free. Optional cloud deployment steps belong to a separately configured and authorized AWS/Azure environment.

| Topic | Project and business task | Inspect first |
| --- | --- | --- |
| AWS | Record upload metadata through a serverless event pipeline, with duplicate handling and failure capture | [Architecture and setup](../aws-file-intake/README.md), [SAM template](../aws-file-intake/template.yaml) |
| Azure | Build a private document-storage foundation with identity-based access and private DNS | [Architecture and setup](../azure-private-storage/README.md), [Bicep source](../azure-private-storage/main.bicep) |
| Linux | Report memory, disk and load warnings without changing the server | [Architecture and operations guide](../linux-healthcheck/README.md), [Bash script](../linux-healthcheck/healthcheck.sh) |
| Python | Turn normalized billing CSV rows into exact monthly/provider spend and budget reports | [Input contract and examples](../python-cloud-costs/README.md), [CLI](../python-cloud-costs/cost_report.py) |

## Demonstration sequence

1. Run the AWS metadata preview and inspect the decoded object key and stable event fingerprint. Compare a repeated event with a new object version in the tests.
2. Inspect the Azure architecture and run the compiled-template guardrails. Explain why both network connectivity and data-plane authorization are required.
3. Run the Linux fixture tests. Compare a warning threshold with missing data: invalid input must not become a healthy result.
4. Run the Python cost report. Reconcile provider totals with service/environment subtotals and explain the missing-budget status.

## Validation boundaries

AWS checks include the real Boto3 SDK with Stubber and `cfn-lint`. Azure checks include Microsoft Bicep compilation, source/compiled-template comparison and configuration guardrails. Linux tests execute the real Bash script with controlled metrics, including on Ubuntu CI. Python reporting tests cover malformed input, duplicates, exact arithmetic and threshold boundaries.

The [recorded local validation](cloud-validation-2026-10-26.json) is separate from the [live CI status](../.github/workflows/ci.yml). No AWS/Azure resource was created for these checks. Compilation and simulated requests do not establish deployed availability, account permissions, runtime cost or production performance.
