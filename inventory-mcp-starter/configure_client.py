"""Create project-local MCP settings and install the bundled skill for a coding client.

Run with the Python interpreter where requirements.txt was installed.
Only this extracted project's files are changed; global settings are untouched.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "skills" / "inventory-review"


def write_new_or_same(path, content):
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise SystemExit(f"Existing file differs; review it before replacing: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def configure(client):
    targets = []
    if client in {"codex", "both"}:
        targets.append(ROOT / ".agents" / "skills" / "inventory-review")
        quote = json.dumps
        config = (
            "# Generated project-local MCP connection. Re-run after moving this folder.\n"
            "[mcp_servers.inventory-review]\n"
            f"command = {quote(sys.executable)}\n"
            f"args = [{quote(str(ROOT / 'server.py'))}]\n"
            f"cwd = {quote(str(ROOT))}\n"
            "startup_timeout_sec = 30\n"
            "tool_timeout_sec = 60\n"
            "\n[mcp_servers.inventory-review.env]\n"
            f"INVENTORY_DB = {quote(str(ROOT / '.runtime' / 'inventory.sqlite'))}\n"
        )
        write_new_or_same(ROOT / ".codex" / "config.toml", config)
    if client in {"claude", "both"}:
        targets.append(ROOT / ".claude" / "skills" / "inventory-review")
        path = ROOT / ".mcp.json"
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"mcpServers": {}}
        entry = {"type": "stdio", "command": sys.executable, "args": [str(ROOT / "server.py")],
                 "env": {"INVENTORY_DB": str(ROOT / ".runtime" / "inventory.sqlite")}}
        existing = config.setdefault("mcpServers", {}).get("inventory-review")
        if existing is not None and existing != entry:
            raise SystemExit(f"Existing inventory-review connection differs; review it: {path}")
        config["mcpServers"]["inventory-review"] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
    for target in targets:
        for source in SKILL.rglob("*"):
            if source.is_file():
                write_new_or_same(target / source.relative_to(SKILL), source.read_text(encoding="utf-8"))
    return targets


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", choices=["codex", "claude", "both"])
    args = parser.parse_args()
    installed = configure(args.client)
    print(f"Project-local {args.client} connection configured with {sys.executable}")
    for path in installed:
        print(f"Skill: {path}")
    print("Open this folder in your coding client and reload its MCP connections.")
