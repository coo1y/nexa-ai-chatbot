#!/usr/bin/env python3
"""PreToolUse guardrail: stop an agent from writing secrets into the repository.

Blocks (exit 2, reason on stderr — shown to the agent):
  * writes/edits to real environment or key files (.env, *.pem, id_rsa...);
  * content containing API-key-shaped strings (Groq, OpenAI-style, Anthropic, Tavily,
    AWS, GitHub tokens, private key blocks, hard-coded credential assignments).

Stdlib only, so it runs anywhere the agent runs.
"""

import json
import re
import sys
from pathlib import PurePath

SECRET_PATTERNS = {
    "Groq API key": r"\bgsk_[A-Za-z0-9]{20,}",
    "Anthropic API key": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "OpenAI-style API key": r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}",
    "Tavily API key": r"\btvly-[A-Za-z0-9]{20,}",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{36,}",
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "hard-coded credential": r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*[\"'][A-Za-z0-9_\-+/=]{20,}[\"']",
}
BLOCKED_FILES = re.compile(r"(^|/)(\.env(\.[^/]*)?|id_rsa|id_ed25519|[^/]*\.pem|[^/]*\.key)$")
ALLOWED_FILES = re.compile(r"(^|/)\.env\.example$")


def collect_content(tool_input: dict) -> str:
    parts = [tool_input.get("content", ""), tool_input.get("new_string", "")]
    for edit in tool_input.get("edits", []) or []:
        parts.append(edit.get("new_string", ""))
    return "\n".join(p for p in parts if isinstance(p, str))


def check(event: dict) -> str | None:
    tool_input = event.get("tool_input") or {}
    path = str(tool_input.get("file_path", ""))
    if path and BLOCKED_FILES.search(path) and not ALLOWED_FILES.search(path):
        return f"Refusing to write {PurePath(path).name}: secrets and environment files are managed by humans, not agents."
    content = collect_content(tool_input)
    for label, pattern in SECRET_PATTERNS.items():
        if re.search(pattern, content):
            return (
                f"Blocked: the content looks like it contains a {label}. Never commit secrets — "
                "reference an environment variable (see .env.example) instead."
            )
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = check(event)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
