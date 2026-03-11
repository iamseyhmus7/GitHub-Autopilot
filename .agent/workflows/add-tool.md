---
description: How to add a new MCP tool to the server
---

# Add a New MCP Tool

Follow these steps to add a new tool to `mcp-github-advanced`.

## 1. Implement the GitHub Client Method

In `src/mcp_github_advanced/github.py`, add a new async method to `GitHubClient`:

```python
async def new_tool_name(self, owner: str, repo: str, ...) -> dict:
    """Docstring explaining what this tool does."""
    # Check cache
    if self.cache:
        cached = await self.cache.get(owner, repo, "new_tool_name")
        if cached:
            return cached

    # Make API call with versioned headers (automatic via self.headers)
    resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}/endpoint")
    data = resp.json()

    # Transform response
    result = { ... }

    # Chunk large outputs
    if "content" in result:
        result["content"] = _chunk_text(result["content"])

    # Cache result
    if self.cache:
        await self.cache.set(owner, repo, "new_tool_name", result)
    return result
```

## 2. Add TTL in Cache

In `src/mcp_github_advanced/cache.py`, add TTL entry:

```python
TTL = {
    ...
    "new_tool_name": 300,  # 5 minutes (or appropriate TTL)
}
```

## 3. Register the Tool

In `src/mcp_github_advanced/server.py`, add to the `TOOLS` list:

```python
Tool(
    name="new_tool_name",
    description="Description of what the tool does",
    inputSchema={
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            # ... additional parameters
        },
        "required": ["owner", "repo"],
    },
),
```

## 4. Add Dispatch Case

In the `_dispatch()` function in `server.py`:

```python
case "new_tool_name":
    return await gh.new_tool_name(owner, repo, ...)
```

## 5. Write Tests

In `tests/test_github.py`:

```python
class TestNewToolName:
    @respx.mock
    async def test_success(self, github_client):
        respx.get("https://api.github.com/repos/owner/repo/endpoint").mock(
            return_value=httpx.Response(200, json={...})
        )
        result = await github_client.new_tool_name("owner", "repo")
        assert result[...] == expected

    @respx.mock
    async def test_404(self, github_client):
        # Test 404 scenario
        ...

    @respx.mock
    async def test_401(self, github_client):
        # Test unauthorized scenario
        ...
```

## 6. Update Documentation

- Add tool to the table in `AGENTS.md`
- Add tool to `README.md` features table
- Increment version in `__init__.py` if needed

## 7. Commit

```bash
git add .
git commit -m "feat: add new_tool_name tool"
```
