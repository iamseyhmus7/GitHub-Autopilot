---
description: Python style and formatting rules for mcp-github-advanced
---

# Python Style Rules

## General
- Python 3.10+ with `from __future__ import annotations`
- Line length: 100 characters max (configured in `pyproject.toml`)
- Use `ruff` for linting: `ruff check src/ tests/`

## Formatting
- 4 spaces for indentation (no tabs)
- Double quotes for strings
- Trailing commas in multi-line structures
- f-strings preferred over `.format()` or `%`

## Type Hints
- Use type hints for all function signatures
- Use `Optional[T]` or `T | None` for nullable types
- Use `dict[str, Any]` instead of `Dict[str, Any]` (lowercase generics)

## Imports
- Group imports: stdlib → third-party → local
- Use `ruff` import sorting (`select = ["I"]` in pyproject.toml)
- Prefer absolute imports

## Naming
- `snake_case` for functions, variables, modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants
- Prefix private methods/attributes with `_`

## Async
- All GitHub API interactions MUST be async (`async def`)
- Use `httpx.AsyncClient` (not `requests`)
- Use `asyncio.run()` only at entry points

## Docstrings
- Google-style docstrings for all public functions/classes
- Include `Args:`, `Returns:`, `Raises:` sections as needed

## Error Handling
- Never silently swallow exceptions
- Log warnings for non-critical failures (e.g., cache misses)
- Raise specific exceptions, not generic `Exception`
