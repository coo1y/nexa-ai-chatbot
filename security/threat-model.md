# Threat model (STRIDE-lite)

**Assets**: provider API keys; uploaded documents/images (may contain personal data);
availability and cost of the model provider; integrity of answers (citations); the
operator's infrastructure.

**Trust boundaries**: browser ⇄ edge (nginx / Render) ⇄ backend ⇄ {database, model provider,
search provider}. Everything from the browser, from uploaded files and from search results is
untrusted. Model output is untrusted too (it can be steered by injected content).

| Threat | Vector | Mitigations | Tests / evidence |
|---|---|---|---|
| Prompt injection via documents or web pages | Instructions hidden in a PDF or search snippet | Content fenced in `<document>` / `<search_results>` with an explicit "untrusted data" system rule; **all tools are read-only** and cannot reach user-chosen URLs, so a successful injection cannot exfiltrate or mutate anything; prompt-injection attempts in user text trigger guidance | `test_context.py`, `test_safety.py` |
| Harmful assistance | Requests for weapons, malware, CSAM | Pre-model block rules; tool-call re-check; optional guard model; provider-side model safety | `test_safety.py`, `test_blocked_request` |
| Exfiltration / SSRF through tools | Model asked to fetch internal URLs | No URL-fetching tool; search providers are fixed endpoints; MCP server host allow-list | `test_base_url_allow_list` |
| Cost/availability abuse | Scripted flooding, huge payloads, long generations | Per-client + per-IP rate limits; body-size limit; `MAX_OUTPUT_TOKENS`; tool iteration cap; tool timeouts; upload size/type limits | `test_rate_limiting`, `test_oversized_bodies…` |
| Rate-limit evasion | Spoofed `X-Forwarded-For` | nginx overwrites the header | config + PR audit #2 |
| Malicious uploads | Zip bombs, decompression bombs, polyglots, path traversal in names | Extension allowlist + magic checks; uncompressed-size cap; `MAX_IMAGE_PIXELS`; re-encoding images; filename sanitising; never served back as files | `test_files_service.py` |
| Cross-user data access | Guessing file ids | File ids are UUIDv4 and scoped to the uploader's client id | `test_files_are_private_to_their_client` |
| XSS through model output | Model emits HTML/JS | react-markdown without raw HTML; URL sanitising; strict CSP (`script-src 'self'`) | header checks |
| Clickjacking / sniffing | Framing the app | `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff` | `curl -I` |
| Secret leakage | Keys in code, logs or errors | Env-only configuration; `SecretStr`; generic error messages; gitleaks in CI; agent secret-guard hook | gitleaks, hook tests |
| Privacy of conversations | Server-side storage of chats | Chats are never stored server-side; telemetry is content-free; uploads auto-deleted after 24 h and on conversation delete; EXIF/GPS stripped | data policy |
| Supply chain | Vulnerable/compromised dependencies | Lockfiles (`uv.lock`, `package-lock.json`), pip-audit, npm audit, trivy; weekly scans; hooks block lockfile edits outside package managers | CI security workflow |
| Agent misuse (developer tooling) | Coding agent prompt-injected via repo content | Deny network tools, secret files; hooks for destructive commands; MCP tools read-only + allow-listed | `security/agent-extension-security.md` |
