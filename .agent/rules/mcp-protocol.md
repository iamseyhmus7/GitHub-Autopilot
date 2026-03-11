---
description: MCP protocol rules and conventions for mcp-github-advanced
---

# MCP Protocol Rules

## Server Implementation

- Use low-level `mcp.server.Server` — NOT `FastMCP`
- Transport: `stdio` via `mcp.server.stdio.stdio_server`
- Register tools with `@app.list_tools()` and `@app.call_tool()` decorators

## Tool Registration

- All tools must be in the `TOOLS` list in `server.py`
- Each tool needs: `name`, `description`, `inputSchema`
- Input schema follows JSON Schema format
- Required parameters listed in `"required"` array

## Tool Response Format

- Always return `list[TextContent]`
- Serialize data as JSON with `json.dumps(result, indent=2, ensure_ascii=False)`
- On error: return `TextContent` with error message (don't raise)
- Truncate output to stay under 8192 tokens

## Entry Point

```python
# pyproject.toml
[project.scripts]
mcp-github-advanced = "mcp_github_advanced.server:main"
```

```python
# server.py
def main() -> None:
    asyncio.run(_run())
```

## Lifecycle

1. Initialize `AuthManager`, `RedisCache`, `GitHubClient`
2. Call `github_client.start()` to open HTTP connections
3. Run `stdio_server()` context → `app.run()`
4. On shutdown: `github_client.close()`

## Adding New Tools

1. Add method to `GitHubClient` in `github.py`
2. Add `Tool(...)` definition to `TOOLS` list in `server.py`
3. Add `case` branch in `_dispatch()` function
4. Add TTL entry in `cache.py` if cacheable
5. Add tests in `test_github.py` and `test_server.py`

## LLM Integration

- Model: `gemini-2.0-flash` via `langchain-google-genai`
- `temperature=0` for deterministic code analysis
- `max_tokens=8192` output limit
- Tool outputs must fit within this limit
