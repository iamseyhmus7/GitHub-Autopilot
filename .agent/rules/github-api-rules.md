---
description: GitHub API rules and conventions for mcp-github-advanced
---

# GitHub API Rules

## Versioned Headers (MANDATORY)

Every GitHub API request MUST include these headers:

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
```

**Never** make a GitHub API request without these headers.

## Rate Limiting

- Authenticated: 5000 requests/hour (REST), 5000 points/hour (GraphQL)
- Check `X-RateLimit-Remaining` after every response
- When remaining < 10: sleep until `X-RateLimit-Reset`
- Use `tenacity` retry with exponential backoff for 429/403 responses

```python
remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
if remaining < 10:
    reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
    wait = reset_time - time.time()
    await asyncio.sleep(max(wait, 0))
```

## Output Limits

- MCP tool outputs MUST NOT exceed 8192 tokens (~30,000 characters)
- Large diffs (>1MB) must be chunked
- Use `_chunk_text()` helper for truncation

## REST API Patterns

- Base URL: `https://api.github.com`
- Timeout: 30 seconds
- Pagination: use `per_page` parameter (max 100)
- Error responses: raise `httpx.HTTPStatusError`

## GraphQL API

- Endpoint: `https://api.github.com/graphql`
- Use for: contributor stats, complex queries
- Check `data.errors` in response

## Token Scopes

- `repo`: Required for private repositories
- `read:user`: Required for user profile
- PAT: Works for own repos only
- OAuth: Can access other users' repos (with permission)

## Caching

- Cache key format: `github:{owner}:{repo}:{tool_name}`
- Never cache write operations (create_issue, create_pr_review)
- TTL values defined in `cache.py`
