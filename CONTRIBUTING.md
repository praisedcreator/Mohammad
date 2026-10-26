# Contributing

Small, reproducible improvements to these teaching projects are welcome. Start an issue describing the problem, affected project, expected behavior and a short example. Use practice data when reporting a problem.

## Development setup

Use Python 3.12 and a dedicated virtual environment. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r uae-delivery-assistant-lab/requirements.txt -r inventory-mcp-starter/requirements.txt -r vector-rag-lab/requirements-aws.txt
.\.venv\Scripts\python.exe tools/run_checks.py
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`. The checks use local fixtures, scripted models and SDK stubs; cloud credentials are not required.

## Pull requests

Explain the problem and resulting behavior. Include the commands you ran and their results. Add tests when changing retrieval, business rules, proposal state, citations or provider request handling. Update setup instructions when dependencies or configuration change.

Preserve the distinction between offline demonstrations, mocked API contracts and verified live integrations. Do not turn a practice-data result into a production-performance claim. Include failed examples when proposing a retrieval threshold change.

Keep credentials, personal data, runtime databases and generated traces out of commits. Dependency and third-party model licenses remain their own. Contributions to this repository are made under the [MIT license](LICENSE).
