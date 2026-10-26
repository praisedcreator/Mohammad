# Inventory Review Agent

A Python proof of concept that turns an inventory exception into a reviewable transfer proposal. The model may request approved read/check tools; Python enforces business rules and records the proposal. A separate human review precedes a local simulation.

## Architecture

```text
Exception -> Python runtime -> inventory and policy tools
          -> optional Claude model on Vertex AI
          -> validated proposal + SQLite state + operational trace
          -> separate human review -> local transfer simulation
```

## Quick start

```powershell
python agent.py demo --out runs/my-demo
python -m unittest -v test_agent.py test_subagents.py
```

The demo requires only Python's standard library. It replays scripted model behaviour against fictional evidence. It does not call a cloud model or write to an ERP.

The optional live adapter, trusted HTTP service contracts, calculation assumptions and review workflow are explained in [the full guide](README.txt). The optional read-only policy specialist is explained in [SUBAGENTS.txt](SUBAGENTS.txt).

See also the separately packaged [MCP server](../inventory-mcp-starter/) and [evaluation notes](../docs/evaluation.md).
