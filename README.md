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
| 📁 **Repo** | `list_user_repos`, `get_repo_info`, `get_file_content`, `list_repo_files`, `search_code` | User profiles, repository metadata, file contents, directory tree, code search |
| 📝 **Commit** | `list_commits`, `get_commit_diff`, `get_contributor_stats` | Commit history, diffs, contributor statistics |
| 🔀 **PR** | `list_pull_requests`, `get_pr_diff`, `create_pr_review` | PR management and AI-powered code reviews |
| 🐛 **Issue** | `list_issues`, `create_issue` | Issue tracking and creation |
| ⚙️ **CI/CD** | `get_workflow_runs`, `get_workflow_logs` | GitHub Actions monitoring and log analysis |

**15 tools** in total, all with:
- 🔒 Versioned API headers (`X-GitHub-Api-Version: 2022-11-28`)
- ⚡ Redis caching with intelligent TTL strategy
- 🔄 Automatic retry with exponential backoff
- 📏 Output chunking for LLM token limits (8192 tokens)
- 🔑 PAT + OAuth 2.0 authentication

---

## 📦 Installation

### Package Kurulumu (Kullanıcılar İçin)

```bash
pip install mcp-github-advanced
```

Veya MCP sunucuları için önerildiği gibi `uvx` kullanarak doğrudan çalıştırabilirsiniz:

```bash
uvx mcp-github-advanced
```

### Kaynak Koddan Kurulum (Geliştiriciler İçin)

Projeyi kendi bilgisayarınıza klonlayıp o şekilde kullanmak (veya geliştirmek) isterseniz:

```bash
git clone https://github.com/iamseyhmus7/GitHub-Autopilot.git
cd GitHub-Autopilot
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

## 🎮 Kullanım (AI Asistanlarına Ekleme)

Bu server, standart bir stdio altyapısı kullanarak JSON-RPC 2.0 mimarisini destekler. AI istemcileriniz için (örn: Claude Desktop, Cursor, Antigravity) konfigürasyon dosyasına (`claude_desktop_config.json` veya IDE `mcp_config.json`) kullanım yönteminize göre aşağıdaki bloklardan birini eklemeniz yeterlidir:

### 1. PyPI Üzerinden Pip Install Sonrası:

```json
{
  "mcpServers": {
    "mcp-github-advanced": {
      "command": "mcp-github-advanced",
      "env": {"GITHUB_TOKEN": "ghp_..."}
    }
  }
}
```

### 2. UVX ile (Sıfır Kurulum, Anında Çalıştırma):

```json
{
  "mcpServers": {
    "mcp-github-advanced": {
      "command": "uvx",
      "args": ["mcp-github-advanced"],
      "env": {"GITHUB_TOKEN": "ghp_..."}
    }
  }
}
```

### 3. GitHub Kaynak Kodundan Çalıştırma:

```json
{
  "mcpServers": {
    "mcp-github-advanced": {
      "command": "python",
      "args": ["-m", "mcp_github_advanced"],
      "env": {"GITHUB_TOKEN": "ghp_..."}
    }
  }
}
```

💡 **İpucu:** Kurulumu yaptıktan sonra asistanınızın "iamseyhmus7/GitHub-Autopilot reposunun bilgilerini getir" gibi komutları anlayabildiğini görebilirsiniz!

---

## 🤖 AI HR Assistant (9-Agent Multi-Agent System)

Bu repo sadece bir MCP sunucusu olmakla kalmaz, aynı zamanda bu sunucuyu kullanan **gelişmiş bir İK (HR) Aday İnceleme Ajanı** barındırır. `src/main.py` ve `src/api/main.py` üzerinden çalışan bu sistem, bir GitHub profilini **10 (9+1) farklı sanal uzman** ile analiz eder:

1. **Agent 0 (Smart Profiler):** `repo_name` girilmediğinde adayın tüm profilini tarayıp en kaliteli projesini seçer.
2. **Repo Explorer:** Proje haritasını çıkarır.
2. **Dependency Analyst:** Kullanılan teknolojileri ve kütüphaneleri bulur.
3. **Architecture Reviewer:** Temiz mimari (Clean Architecture/MVC vb.) kullanımını inceler.
4. **Code Quality Inspector:** Kod okunabilirliğini ve SOLID prensiplerini denetler.
5. **Security Agent:** Hardcoded şifreleri veya güvenlik zaaflarını tarar.
6. **Git Historian:** Commit geçmişini inceleyip projenin kopyala-yapıştır olup olmadığını teyit eder.
7. **DevOps Evaluator:** CI/CD süreçlerini ve Unit Test'leri kontrol eder.
8. **PR Manager:** Takım çalışması, Issue ve Branch kullanımını değerlendirir.
9. **HR Synthesizer:** Tüm bu teknik raporları harmanlayıp, teknik olmayan İK profesyonelleri için "Puanlı Aday Skor Kartı" çıkarır.

**Performans & Optimizasyon:**
- LangGraph kullanılarak inşa edilmiştir.
- Her ajan **sadece uzmanlık alanına giren MCP araçlarına** filtreli şekilde erişir (Context Optimizasyonu).
- Global bir AIO Sqlite Checkpointer kullanılarak, farklı mülakat oturumları (`thread_id`) kalıcı hafızada tutulur.
- Tek bir Github profil analizi ortalama *15 API İsteği* ve *71.000 Token* maliyeti ile (son derece optimize edilmiş olarak) tamamlanır.

**Çalıştırmak için:**
```bash
python src/main.py
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

---## 📝 License

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
