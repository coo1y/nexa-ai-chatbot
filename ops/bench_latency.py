"""Latency benchmark for the chat pipeline: client-observed time-to-first-token and total time.

Usage: uv run --project backend python ops/bench_latency.py --url http://localhost:8080 -n 30 [-c 4]
The per-client rate limit (default 30/min) applies; for a benchmark run raise it, e.g.
  RATE_LIMIT_CHAT_PER_MINUTE=100000 docker compose up -d backend
With LLM_PROVIDER=mock this measures the platform overhead (routing, safety, context assembly,
tools, streaming, proxy); with a real provider it measures end-to-end user-perceived latency.
"""

import argparse
import asyncio
import statistics
import time

import httpx

PROMPTS = [
    ("plain", "Hello! Give me one tip for better sleep."),
    ("tool", "Please calculate (1234 * 5678) / 3"),
    ("search", "What is the latest news about renewable energy?"),
    ("code", "Write a python function that adds two numbers"),
]


async def one(client: httpx.AsyncClient, url: str, prompt: str) -> tuple[float | None, float, bool]:
    payload = {"conversation_id": "bench", "messages": [{"id": "b1", "role": "user", "content": prompt}]}
    started = time.perf_counter()
    ttft = None
    ok = False
    async with client.stream("POST", f"{url}/api/v1/chat/stream", json=payload, headers={"X-Client-Id": "bench-client-01"}) as resp:
        if resp.status_code != 200:
            return None, (time.perf_counter() - started) * 1000, False
        async for line in resp.aiter_lines():
            if line.startswith("event: delta") and ttft is None:
                ttft = (time.perf_counter() - started) * 1000
            if line.startswith("event: done"):
                ok = True
    return ttft, (time.perf_counter() - started) * 1000, ok


def pct(values: list[float], q: int) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[q - 1]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("-n", type=int, default=20, help="requests per prompt type")
    parser.add_argument("-c", type=int, default=1, help="concurrency")
    args = parser.parse_args()
    async with httpx.AsyncClient(timeout=120) as client:
        health = (await client.get(f"{args.url}/api/v1/health")).json()
        print(f"# Latency benchmark\n\n- Target: `{args.url}` · llm={health['llm_provider']} · search={health['search_provider']}")
        print(f"- {args.n} requests per scenario, concurrency {args.c}\n")
        print("| Scenario | OK | TTFT p50 (ms) | TTFT p95 (ms) | Total p50 (ms) | Total p95 (ms) |")
        print("|---|---|---|---|---|---|")
        semaphore = asyncio.Semaphore(args.c)

        async def guarded(prompt: str) -> tuple[float | None, float, bool]:
            async with semaphore:
                return await one(client, args.url, prompt)

        for name, prompt in PROMPTS:
            results = await asyncio.gather(*(guarded(prompt) for _ in range(args.n)))
            ttfts = [r[0] for r in results if r[0] is not None]
            totals = [r[1] for r in results]
            ok = sum(r[2] for r in results)
            print(
                f"| {name} | {ok}/{args.n} | {pct(ttfts, 50):.1f} | {pct(ttfts, 95):.1f} | {pct(totals, 50):.1f} | {pct(totals, 95):.1f} |"
            )


if __name__ == "__main__":
    asyncio.run(main())
