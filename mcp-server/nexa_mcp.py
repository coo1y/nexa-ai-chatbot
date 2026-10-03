"""Nexa MCP server — project tools for coding agents (Claude Code, Codex, Cursor...).

Exposes READ-ONLY capabilities an agent needs while working on this repository:

* the OpenAPI contract (list operations, fetch a schema),
* contract drift detection against a running backend,
* service health and aggregated metrics (operational diagnosis),
* a chat probe that shows how the assistant routes and which tools it uses.

Guardrails: requests only go to allow-listed base URLs (default: localhost), the ops token
is read from the environment and never returned, and no tool mutates server state beyond
the telemetry row a chat probe creates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = Path(os.environ.get("NEXA_OPENAPI_PATH", REPO_ROOT / "openapi.yaml"))
DEFAULT_BASE_URL = os.environ.get("NEXA_BASE_URL", "http://localhost:8000")
ALLOWED_HOSTS = {h.strip() for h in os.environ.get("NEXA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()}
TIMEOUT = httpx.Timeout(30.0, connect=5.0)
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

mcp = MCPServer(
    "nexa",
    instructions=(
        "Tools for the Nexa AI assistant repository. Use contract tools before changing the API, "
        "health/metrics for diagnosing a running stack, and chat_probe to observe routing and tool use."
    ),
)


class GuardrailError(ValueError):
    pass


# --- helpers (plain functions so they are unit-testable) -----------------------------------


def resolve_base_url(base_url: str | None) -> str:
    url = (base_url or DEFAULT_BASE_URL).rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise GuardrailError(f"invalid base URL: {url!r}")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise GuardrailError(
            f"host {parsed.hostname!r} is not allow-listed (NEXA_ALLOWED_HOSTS={','.join(sorted(ALLOWED_HOSTS))})"
        )
    return url


def load_contract(path: Path = OPENAPI_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def list_operations(spec: dict[str, Any]) -> list[dict[str, str]]:
    operations = []
    for route, item in spec.get("paths", {}).items():
        for method, op in item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                operations.append(
                    {
                        "method": method.upper(),
                        "path": route,
                        "operationId": op.get("operationId", ""),
                        "summary": op.get("summary", ""),
                    }
                )
    return operations


def compare_contract(contract: dict[str, Any], implemented: dict[str, Any], prefix: str = "/api/v1") -> dict[str, Any]:
    def ops(spec: dict[str, Any], strip: str = "") -> set[tuple[str, str]]:
        return {
            (method.upper(), route.removeprefix(strip))
            for route, item in spec.get("paths", {}).items()
            for method in item
            if method in {"get", "post", "put", "patch", "delete"}
        }

    declared, served = ops(contract), ops(implemented, prefix)
    schema_diffs = {}
    contract_schemas = contract.get("components", {}).get("schemas", {})
    served_schemas = implemented.get("components", {}).get("schemas", {})
    for name, schema in contract_schemas.items():
        if name in served_schemas and "properties" in schema:
            a, b = set(schema["properties"]), set(served_schemas[name].get("properties", {}))
            if a != b:
                schema_diffs[name] = {"only_in_contract": sorted(a - b), "only_in_backend": sorted(b - a)}
    return {
        "in_sync": declared == served and not schema_diffs,
        "missing_in_backend": sorted(f"{m} {p}" for m, p in declared - served),
        "undocumented_in_contract": sorted(f"{m} {p}" for m, p in served - declared),
        "schema_property_mismatches": schema_diffs,
    }


def summarize_stream(body: str) -> dict[str, Any]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name and data is not None:
            events.append((name, data))
    summary: dict[str, Any] = {
        "events": [n for n, _ in events],
        "text": "",
        "tools": [],
        "sources": [],
        "routing": None,
    }
    for name, data in events:
        if name == "start":
            summary["routing"] = data.get("routing")
        elif name == "delta":
            summary["text"] += data.get("text", "")
        elif name == "tool_result":
            summary["tools"].append({k: data.get(k) for k in ("name", "status", "summary")})
        elif name == "sources":
            summary["sources"] = [{"id": s["id"], "url": s["url"]} for s in data.get("sources", [])]
        elif name in {"error", "safety", "done"}:
            summary[name] = data
    summary["text"] = summary["text"][:4000]
    return summary


def _ops_headers() -> dict[str, str]:
    token = os.environ.get("NEXA_OPS_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


# --- tools -------------------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def contract_operations() -> list[dict[str, str]]:
    """List every operation declared in openapi.yaml (method, path, operationId, summary)."""
    return list_operations(load_contract())


@mcp.tool(annotations=READ_ONLY)
def contract_schema(name: str) -> dict[str, Any]:
    """Return one component schema from openapi.yaml, e.g. 'ChatRequest' or 'DoneEvent'."""
    schemas = load_contract().get("components", {}).get("schemas", {})
    if name not in schemas:
        raise ValueError(f"unknown schema {name!r}; available: {', '.join(sorted(schemas))}")
    return schemas[name]


@mcp.tool(annotations=READ_ONLY)
async def contract_drift(base_url: str | None = None) -> dict[str, Any]:
    """Compare openapi.yaml with the OpenAPI document served by a running backend."""
    url = resolve_base_url(base_url)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{url}/api/v1/openapi.json")
        response.raise_for_status()
    return compare_contract(load_contract(), response.json())


@mcp.tool(annotations=READ_ONLY)
async def service_health(base_url: str | None = None) -> dict[str, Any]:
    """GET /api/v1/health of a running Nexa stack (status, version, database, providers)."""
    url = resolve_base_url(base_url)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{url}/api/v1/health")
    return {"http_status": response.status_code, **response.json()}


@mcp.tool(annotations=READ_ONLY)
async def service_metrics(window_minutes: int = 60, base_url: str | None = None) -> dict[str, Any]:
    """Aggregated, content-free metrics: request counts, error codes, retries, TTFT percentiles, feedback."""
    url = resolve_base_url(base_url)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(
            f"{url}/api/v1/metrics", params={"window_minutes": window_minutes}, headers=_ops_headers()
        )
    if response.status_code != 200:
        return {"http_status": response.status_code, "error": response.json().get("error")}
    return response.json()


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False))
async def chat_probe(
    message: str, capability: str = "auto", web_search: bool = False, base_url: str | None = None
) -> dict[str, Any]:
    """Send one message to the assistant and summarise the stream: routing decision, tools, sources, text.

    Useful to verify routing/tool/safety behaviour after a change. Creates one telemetry row.
    """
    if len(message) > 4000:
        raise GuardrailError("probe messages are limited to 4000 characters")
    if capability not in {"auto", "fast", "reasoning", "vision"}:
        raise GuardrailError("capability must be auto, fast, reasoning or vision")
    url = resolve_base_url(base_url)
    payload = {
        "conversation_id": "mcp_probe",
        "messages": [{"id": "probe", "role": "user", "content": message}],
        "capability": capability,
        "web_search": web_search,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{url}/api/v1/chat/stream", json=payload, headers={"X-Client-Id": "mcp-probe-client"}
        )
    if response.status_code != 200:
        return {"http_status": response.status_code, "error": response.json().get("error")}
    return summarize_stream(response.text)


@mcp.resource("nexa://openapi.yaml", name="openapi", mime_type="application/yaml")
def openapi_resource() -> str:
    """The API contract (source of truth for frontend and backend)."""
    return OPENAPI_PATH.read_text()


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
