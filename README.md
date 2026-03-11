# 🚀 mcp-github-advanced

[![PyPI](https://img.shields.io/pypi/v/mcp-github-advanced)](https://pypi.org/project/mcp-github-advanced/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)

**Advanced GitHub MCP server** — repo analysis, PR management, automated code review, CI/CD monitoring via GitHub REST v3 + GraphQL v4 API.

Built for AI assistants and LangChain/LangGraph agents using the [Model Context Protocol](https://modelcontextprotocol.io).

---

## ✨ Features

| Category | Tools | Description |
|----------|-------|-------------|
| 📁 **Repo** | `get_repo_info`, `get_file_content`, `list_repo_files`, `search_code` | Repository metadata, file contents, directory tree, code search |
| 📝 **Commit** | `list_commits`, `get_commit_diff`, `get_contributor_stats` | Commit history, diffs, contributor statistics |
| 🔀 **PR** | `list_pull_requests`, `get_pr_diff`, `create_pr_review` | PR management and AI-powered code reviews |
| 🐛 **Issue** | `list_issues`, `create_issue` | Issue tracking and creation |
| ⚙️ **CI/CD** | `get_workflow_runs`, `get_workflow_logs` | GitHub Actions monitoring and log analysis |

**14 tools** in total, all with:
- 🔒 Versioned API headers (`X-GitHub-Api-Version: 2022-11-28`)
- ⚡ Redis caching with intelligent TTL strategy
- 🔄 Automatic retry with exponential backoff
- 📏 Output chunking for LLM token limits (8192 tokens)
- 🔑 PAT + OAuth 2.0 authentication

---

## 📦 Installation

```bash
pip install mcp-github-advanced
```

Or with `uvx` (recommended for MCP):

```bash
uvx mcp-github-advanced
```

### Development Install

```bash
git clone https://github.com/iamseyhmus7/mcp-github-advanced.git
cd mcp-github-advanced
pip install -e ".[dev]"
```

---

## ⚙️ Configuration

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```bash
# GitHub Auth (at least one required)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx      # Personal Access Token
GITHUB_CLIENT_ID=Ov23xxxxxxxxxxxxx         # OAuth App (optional)
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxx      # OAuth App (optional)

# Redis (optional — disables caching if unavailable)
REDIS_URL=redis://localhost:6379/0

# Server
MCP_SERVER_NAME=mcp-github-advanced
LOG_LEVEL=INFO

# LLM
GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXX
```

### 2. GitHub Token Scopes

For full functionality, your PAT needs these scopes:
- `repo` — Access private repositories
- `read:user` — Read user profile

### 3. MCP Client Configuration

#### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github-advanced": {
      "command": "uvx",
      "args": ["mcp-github-advanced"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

#### Cursor / VS Code

Add to `.cursor/mcp.json` or equivalent:

```json
{
  "mcpServers": {
    "github-advanced": {
      "command": "uvx",
      "args": ["mcp-github-advanced"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

---

## 🛠️ Usage Examples

Once connected to an MCP client, you can use natural language:

> "Analyze the repository `owner/repo` — show me stars, language, and recent commits."

> "List open pull requests in `owner/repo` and review PR #42."

> "Check the latest CI/CD runs for `owner/repo` and show me failed job logs."

> "Search for `TODO` comments in `owner/repo`."

> "Create an issue titled 'Fix login bug' with label 'bug' in `owner/repo`."

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│              server.py                    │
│         14 MCP Tools (list_tools)        │
│         call_tool() dispatcher           │
└──────────────┬───────────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
┌───────────┐    ┌─────────────────┐
│ github.py │    │    auth.py       │
│ REST + GQL│    │ OAuth + PAT     │
│ Rate limit│    │ Token mgmt      │
└─────┬─────┘    └─────────────────┘
      │
      ▼
┌───────────────────────────────────┐
│          cache.py                  │
│  Redis — TTL-based caching        │
│  Graceful degradation             │
└───────────────────────────────────┘
```

---

## 🧪 Testing

All tests use `respx` mocks — **no real GitHub API calls**:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=mcp_github_advanced

# Lint
ruff check src/ tests/
```

---

## 🌍 Deployment

### PyPI

```bash
pip install mcp-github-advanced
```

### Smithery.ai

Deploy via [`smithery.yaml`](smithery.yaml):

```bash
npx @anthropic/smithery publish
```

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/amazing-feature`
3. Commit: `git commit -m 'feat: add amazing feature'`
4. Push: `git push origin feat/amazing-feature`
5. Open a Pull Request

Follow the [commit conventions](AGENTS.md#-git-commit-kuralları) defined in AGENTS.md.

---

## 👤 Author

**Şeyhmus OK** — [@iamseyhmus7](https://github.com/iamseyhmus7)
