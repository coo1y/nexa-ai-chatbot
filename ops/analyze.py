"""Turn health + metrics JSON into actionable findings (used by ops/diagnose.sh)."""

import json
import sys
from pathlib import Path

# SLOs from ops/slo.md
SLO_TTFT_P95_MS = 2000
SLO_ERROR_RATE = 0.02

HINTS = {
    "upstream_unavailable": "Model provider unreachable or 5xx → check provider status page; retries are already applied (LLM_MAX_RETRIES). Consider a fallback LLM_BASE_URL.",
    "upstream_rate_limited": "Provider quota/rate limit → raise plan limits or lower RATE_LIMIT_CHAT_PER_MINUTE.",
    "upstream_misconfigured": "Provider rejected credentials → rotate/fix LLM_API_KEY (runbook: 'Invalid model credentials').",
    "upstream_bad_request": "Model rejected input → context too large for the model or unsupported content; lower CONTEXT_MAX_TOKENS.",
    "internal_error": "Application bug → search backend logs for the request_id and open an issue.",
}


def load(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    health_code, health_path, metrics_code, metrics_path = sys.argv[1:5]
    health, metrics = load(health_path), load(metrics_path)
    findings: list[str] = []
    if health_code == "000":
        findings.append("🔴 **Service unreachable** — container down, wrong URL, or proxy failure. Run `docker compose ps`.")
    elif health.get("database") == "unavailable":
        findings.append("🔴 **Database unavailable** — health is degraded (HTTP 503). See runbook 'Database unavailable'.")
    elif health.get("status") == "ok":
        findings.append(f"🟢 Service healthy (version {health.get('version')}, llm={health.get('llm_provider')}, search={health.get('search_provider')}).")

    if metrics_code.startswith("5"):
        code = (metrics.get("error") or {}).get("code", "unknown")
        findings.append(f"🔴 Metrics unavailable (HTTP {metrics_code}, `{code}`) — telemetry lives in the database.")
    elif metrics_code == "401":
        findings.append("🟡 Metrics require a valid OPS_TOKEN.")
    elif metrics:
        total = metrics.get("total_requests", 0)
        rate = metrics.get("error_rate", 0.0)
        p95 = (metrics.get("ttft_ms") or {}).get("p95")
        if total == 0:
            findings.append("⚪ No chat traffic in the window.")
        if rate > SLO_ERROR_RATE:
            findings.append(f"🔴 **Error rate {rate:.1%}** exceeds the {SLO_ERROR_RATE:.0%} SLO.")
        elif total:
            findings.append(f"🟢 Error rate {rate:.1%} within SLO ({total} requests).")
        for code, count in sorted((metrics.get("errors_by_code") or {}).items(), key=lambda kv: -kv[1]):
            findings.append(f"  - `{code}` × {count}: {HINTS.get(code, 'see logs')}")
        if p95 is not None:
            mark = "🔴" if p95 > SLO_TTFT_P95_MS else "🟢"
            findings.append(f"{mark} TTFT p95 {p95:.0f} ms (SLO {SLO_TTFT_P95_MS} ms).")
        retries = metrics.get("total_retries", 0)
        if total and retries / total > 0.2:
            findings.append(f"🟡 {retries} model retries for {total} requests — upstream instability is adding latency.")
        stopped = (metrics.get("by_status") or {}).get("stopped", 0)
        if total and stopped / total > 0.25:
            findings.append(f"🟡 {stopped} generations stopped by users — responses may be too slow or too long.")
        fb = metrics.get("feedback") or {}
        if fb.get("down", 0) > fb.get("up", 0) and fb.get("down", 0) >= 5:
            findings.append(f"🟡 Negative feedback dominates ({fb}) — review routing/model choice.")
    for line in findings or ["(no data)"]:
        print(f"- {line}" if not line.startswith("  -") else line)


if __name__ == "__main__":
    main()
