---
name: github-mcp
description: Skill for working with the mcp-github-advanced MCP server codebase
---

# GitHub MCP Skill

This skill provides instructions for working with the `mcp-github-advanced` MCP server codebase.

## Overview

`mcp-github-advanced` is an MCP server that exposes 14 GitHub API tools via the Model Context Protocol. It supports:

- **GitHub REST API v3** — repositories, commits, PRs, issues, actions
- **GitHub GraphQL v4** — contributor statistics, complex queries
- **Redis caching** — with intelligent TTL strategy
- **PAT + OAuth 2.0** — dual authentication support
- **LLM integration** — via `gemini-2.0-flash` and `langchain-google-genai`

## Architecture

```
server.py  →  14 MCP tools (list_tools + call_tool)
  ├── github.py  →  REST + GraphQL client (httpx async)
  ├── auth.py    →  PAT + OAuth 2.0 authentication
  └── cache.py   →  Redis caching with TTL strategy
```

## Key Conventions

### 1. Versioned API Headers

**Every** GitHub API request must include:
```python
{
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
```

### 2. Rate Limiting

- Check `X-RateLimit-Remaining` after every response
- Sleep when remaining < 10
- Use `tenacity` retry for 429/403

### 3. Output Chunking

- Max output ≈ 30,000 characters (~8192 tokens)
- Use `_chunk_text()` for truncation
- Individual file patches capped at 5000 chars

### 4. Cache TTL Strategy

| Tool | TTL |
|------|-----|
| `get_repo_info` | 1 hour |
| `list_commits` | 5 min |
| `get_pr_diff` | 10 min |
| `get_workflow_logs` | 1 min |
| `get_file_content` | 30 min |
| Write operations | No cache |

### 5. Testing

- **Always** use `respx` for HTTP mocking
- **Never** hit real GitHub API in tests
- Test scenarios: success, 404, 401, rate limit

### 6. LLM

- Model: `gemini-2.0-flash`
- `temperature=0` for consistent code analysis
- `max_tokens=8192`
- Package: `langchain-google-genai`

## Common Tasks

- **Add a tool**: See `.agent/workflows/add-tool.md`
- **Publish**: See `.agent/workflows/publish-to-pypi.md`
- **Run tests**: `pytest` (with `asyncio_mode = "auto"`)
- **Lint**: `ruff check src/ tests/`

## File Map

| File | Purpose |
|------|---------|
| `server.py` | MCP server, 14 tool definitions, dispatch |
| `github.py` | GitHub API client (REST + GraphQL) |
| `auth.py` | PAT + OAuth 2.0 authentication |
| `cache.py` | Redis caching with TTL |
| `__init__.py` | Version string |
| `__main__.py` | `python -m` entry point |
