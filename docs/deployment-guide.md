# Deployment and Troubleshooting Guide

## Implemented scope

The delivery assistant and inventory agent run as local Python applications. Their cloud adapters need the user's own account configuration. The MCP server runs locally over STDIO. The retail dashboard includes a Dockerfile; deployment to Cloud Run or another host is a later configured action, not a completed deployment in this repository.

## Before connecting cloud services

Use project-specific permissions, an approved identity and a supported model/region. Keep credentials outside source control. Prefer workload identity or the provider's recommended keyless route for hosted applications. Review data handling, logging and spending before using real records. Each component's README describes its actual environment variables and startup commands.

## Troubleshooting

| Symptom | Checks |
| --- | --- |
| Missing module | Activate the component's virtual environment and install its own requirements |
| Authentication error | Check the intended tenant/project, identity, permission scope and inference endpoint |
| Model not found | Confirm the model/deployment identifier, location and account availability |
| Invalid answer fields | Inspect the selected record, retrieved policies, expected schema and validation error |
| No dashboard rows | Check SQL setup, dataset/project, view results and selected store filters |
| Invalid stock projection | Inspect inventory, receipt timing, missing days and demand-source flags |
| MCP connection fails | Check the interpreter path, STDIO transport, project trust and local client configuration |
| Repeated proposal request | Reuse the request identifier only for identical content and inspect the saved proposal/state |

## Handover checklist

Document the environment, configuration names, startup/test commands, evidence sources, operational owner, rollback approach and known limits. Share a reproducible example and a failure case with both technical and business reviewers.
