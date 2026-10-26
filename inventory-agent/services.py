"""Read-only service adapters. Fixture data is fictional; HTTP contracts are examples."""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def read_json(request):
    with urlopen(request, timeout=20) as response:
        raw = response.read(200_001)
        if len(raw) > 200_000:
            raise ValueError("Service response exceeds size limit")
        return json.loads(raw)


class FixtureServices:
    """A demo-only snapshot refreshed in memory; this is not live inventory."""

    def __init__(self):
        fixture = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
        self.case = fixture["case"]
        self.inventory = fixture["inventory"]
        self.policy = fixture["policy"]

    def get_inventory(self):
        return {**copy.deepcopy(self.inventory), "as_of": utcnow()}

    def get_policy(self):
        return {**copy.deepcopy(self.policy), "as_of": utcnow()}


class HttpServices:
    """Map your existing services to these contracts; no arbitrary SQL or URLs.

    ADC signs ID tokens for Cloud Run services using their base URL as audience.
    The service must enforce tenant/warehouse scope and return fresh versioned data.
    The live example currently supports the same constant-demand calculator as the
    fixture. Replace that calculator with your analytics projection for production.
    """

    def __init__(self, case):
        self.case = case
        self.analytics_url = os.environ["ANALYTICS_BASE_URL"].rstrip("/")
        self.retrieval_url = os.environ["RETRIEVAL_BASE_URL"].rstrip("/")
        for base in (self.analytics_url, self.retrieval_url):
            parsed = urlparse(base)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Service base URLs must be configured HTTPS URLs without credentials or query parameters")

    def _get(self, base, path):
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2.id_token import fetch_id_token
        token = fetch_id_token(GoogleRequest(), base)
        query = urlencode(self.case)
        return read_json(Request(base + path + "?" + query,
                                 headers={"Authorization": "Bearer " + token}))

    def get_inventory(self):
        return self._get(self.analytics_url, "/inventory/context")

    def get_policy(self):
        # Structured limits must come from a trusted policy store, alongside RAG
        # excerpts; do not let model-extracted prose become enforceable policy.
        return self._get(self.retrieval_url, "/policies/transfer")


def public_logistics_search():
    """Perplexity Search, with a fixed public query and no inventory sent outside.

    This research is context only. It never authorizes a transfer or establishes
    inventory, confirmed delivery, or authoritative procurement policy.
    """
    query = "UAE intercity road freight disruption official transport advisories"
    body = json.dumps({"query": query, "max_results": 3,
                       "max_tokens": 1500, "max_tokens_per_page": 500}).encode()
    result = read_json(Request("https://api.perplexity.ai/search", data=body, method="POST",
                              headers={"Authorization": "Bearer " + os.environ["PERPLEXITY_API_KEY"],
                                       "Content-Type": "application/json"}))
    return {"as_of": utcnow(), "authority": "untrusted_public_context_only", "query": query,
            "sources": [{key: item.get(key) for key in ("title", "url", "snippet", "date")}
                        for item in result.get("results", [])[:3]]}
