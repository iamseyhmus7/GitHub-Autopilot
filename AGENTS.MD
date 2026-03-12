# AGENTS.md — mcp-github-advanced

## 🎯 Proje Amacı

Bu proje **GitHub API v3 (REST) + v4 (GraphQL)** entegrasyonunu
**MCP (Model Context Protocol)** üzerinden AI asistanlarına ve
LangChain/LangGraph agent'larına sunan production-grade bir sunucudur.

Herhangi bir GitHub kullanıcısının veya organizasyonunun repolarını
analiz edebilir, PR/Issue yönetimi yapabilir, CI/CD durumunu izleyebilir
ve otomatik code review yazabilir.

Bu server bir **web uygulamasının backend'i** olarak tasarlanmıştır:
- Frontend: Next.js / React (FAZ 3-4 Planlanıyor)
- Backend: FastAPI (Yakında)
- Agent: **LangChain + LangGraph (9-Agent HR Sistemi Aktif)**
- LLM: **Google Gemini Flash** (`gemini-2.5-flash`)
- MCP: mcp-github-advanced (bu proje)

---

## 🏗️ Mimari Genel Bakış

```
┌─────────────────────────────────────────────┐
│              server.py                       │
│         14 MCP Aracı (list_tools)           │
│         call_tool() yönlendirici            │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐    ┌─────────────────────┐
│   github.py   │    │      auth.py         │
│  REST Client  │    │  OAuth + PAT         │
│  GraphQL      │    │  Token yönetimi      │
│  Rate limiter │    │  Scope kontrolü      │
└───────┬───────┘    └─────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│           GitHub API                     │
│  REST v3:    api.github.com/...          │
│  GraphQL v4: api.github.com/graphql      │
│  Webhooks:   github.com/settings/hooks   │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│           cache.py                       │
│  Redis — API yanıtlarını önbellekle      │
│  Rate limit aşımını engelle              │
│  TTL: repo_info=1saat, commits=5dk      │
└─────────────────────────────────────────┘
```

---

## 🤖 AI Ajan Mimarisi (LangGraph 9-Agent HR) 

`src/main.py` ve `src/multi_agent.py` içindeki sistem **9 adet ajan düğümü (node)** barındırır.
Sırasıyla: (1) Repo Explorer, (2) Dependency Analyst, (3) Architecture Reviewer, (4) Code Quality Inspector, (5) Security Agent, (6) Git Historian, (7) DevOps Evaluator, (8) PR Manager, (9) HR Synthesizer.

**LangGraph Optimizasyon Kuralları (Maliyet Koruma):**
1. **Tool Filtering (Araç Filtreleme):** Tüm araçlar (14 şema) ajana YÜKLENMEMELİDİR. `allowed_tools=["search_code"]` argümanıyla sadece ilgili araçlar LLM'ye iletilir.
2. **Context Memory Bloat Koruması:** `HRGraphState` kullanılırken `checkpointer` (SqliteSaver) eski mülakatları hatırlamaması için `thread_id` değerleri **her yeni aday analizinde UUID ile benzersiz (unique)** üretilmelidir. (Örn: `hr_session_{owner}_{repo}_{uuid.uuid4().hex[:8]}`)
3. **Iteration Limit:** Ajanların takılıp kalmaması için LLM döngülerinde `max_iterations=2` sınırı tavsiye edilir.

---

## 📦 Teknoloji Yığını

| Katman | Teknoloji | Versiyon | Neden? |
|--------|-----------|----------|--------|
| MCP Protokolü | `mcp` | ≥1.19.0 | Resmi Python SDK |
| HTTP | `httpx` | ≥0.28.0 | Async, REST + GraphQL |
| Auth | `authlib` | ≥1.3.0 | OAuth 2.0 akışı |
| Cache | `redis[hiredis]` | ≥5.0.0 | Rate limit koruması |
| Retry | `tenacity` | ≥8.0.0 | GitHub API 429 yönetimi |
| Env | `python-dotenv` | ≥1.0.0 | Token yönetimi |
| Paketleme | `hatchling` | latest | Modern build backend |
| Test | `pytest` + `pytest-asyncio` | ≥8.3.0 | Async test |
| Mock | `respx` | ≥0.21.0 | HTTP mock |
| Linter | `ruff` | ≥0.8.0 | Hızlı linter |

---

## 📁 Klasör Yapısı

```
mcp-github-advanced/
├── AGENTS.md                          ← Bu dosya
├── README.md                          ← Kullanıcı dokümantasyonu
├── smithery.yaml                      ← Smithery.ai deployment
├── pyproject.toml                     ← Paket tanımı
├── .env.example                       ← Ortam değişkenleri
│
├── src/
│   └── mcp_github_advanced/
│       ├── __init__.py                ← __version__ = "0.1.0"
│       ├── __main__.py                ← python -m girişi
│       ├── server.py                  ← 14 MCP aracı
│       ├── github.py                  ← GitHub REST + GraphQL client
│       ├── auth.py                    ← OAuth + PAT yönetimi
│       └── cache.py                   ← Redis önbellekleme
│
├── tests/
│   ├── conftest.py                    ← Test fixtures
│   ├── test_github.py                 ← GitHub client testleri
│   ├── test_auth.py                   ← Auth testleri
│   └── test_server.py                 ← MCP araç testleri
│
└── .agent/
    ├── rules/
    │   ├── python-style.md
    │   ├── github-api-rules.md        ← GitHub API kuralları
    │   └── mcp-protocol.md
    ├── workflows/
    │   ├── add-tool.md
    │   └── publish-to-pypi.md
    └── skills/
        └── github-mcp/
            └── SKILL.md
```

---

## 🛠️ 14 MCP Aracı

### 📁 Repo Araçları

| Araç | Açıklama | Zorunlu Parametre |
|------|----------|-------------------|
| `get_repo_info` | Repo metadata: yıldız, fork, dil, boyut | `owner`, `repo` |
| `get_file_content` | Herhangi bir dosyanın içeriği | `owner`, `repo`, `path` |
| `list_repo_files` | Repo dizin yapısı (tree) | `owner`, `repo` |
| `search_code` | Repo içinde kod/string arama | `owner`, `repo`, `query` |

### 📝 Commit Araçları

| Araç | Açıklama | Zorunlu Parametre |
|------|----------|-------------------|
| `list_commits` | Commit geçmişi + mesajlar | `owner`, `repo` |
| `get_commit_diff` | Tek commit'in tüm değişiklikleri | `owner`, `repo`, `sha` |
| `get_contributor_stats` | Kim ne kadar katkı yaptı | `owner`, `repo` |

### 🔀 PR Araçları

| Araç | Açıklama | Zorunlu Parametre |
|------|----------|-------------------|
| `list_pull_requests` | Açık/kapalı PR listesi | `owner`, `repo` |
| `get_pr_diff` | PR'ın tüm değişiklikleri (diff) | `owner`, `repo`, `pr_number` |
| `create_pr_review` | PR'a AI review yorumu yaz | `owner`, `repo`, `pr_number`, `body` |

### 🐛 Issue Araçları

| Araç | Açıklama | Zorunlu Parametre |
|------|----------|-------------------|
| `list_issues` | Issue listesi + etiketler | `owner`, `repo` |
| `create_issue` | Yeni issue aç | `owner`, `repo`, `title` |

### ⚙️ Actions/CI Araçları

| Araç | Açıklama | Zorunlu Parametre |
|------|----------|-------------------|
| `get_workflow_runs` | CI/CD çalışma geçmişi | `owner`, `repo` |
| `get_workflow_logs` | Başarısız run'ın hata logları | `owner`, `repo`, `run_id` |

---

## 🔑 Auth Yönetimi

### Personal Access Token (PAT)
```python
# .env dosyasında
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# github.py içinde
headers = {
    "Authorization": f"Bearer {settings.github_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
```

### OAuth 2.0 Akışı
```python
# 1. Kullanıcıyı GitHub'a yönlendir
auth_url = (
    "https://github.com/login/oauth/authorize"
    f"?client_id={CLIENT_ID}"
    f"&scope=repo,read:user"
    f"&state={csrf_token}"
)

# 2. Callback'te token al
token = await exchange_code_for_token(code)

# 3. Her istekte kullan
headers["Authorization"] = f"Bearer {token}"
```

---

## 🔑 Değişmez Kod Kuralları

### GitHub REST API
```python
# ✅ DOĞRU — her zaman versiyonlu header kullan
async with httpx.AsyncClient() as client:
    resp = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30.0,
    )
    resp.raise_for_status()

# ❌ YANLIŞ — header'sız istek
resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}")
```

### GitHub GraphQL API
```python
# ✅ Commit istatistikleri için GraphQL kullan
query = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 10) {
            nodes {
              message
              committedDate
              author { name email }
            }
          }
        }
      }
    }
  }
}
"""

resp = await client.post(
    "https://api.github.com/graphql",
    json={"query": query, "variables": {"owner": owner, "repo": repo}},
    headers=headers,
)
```

### Rate Limiting
```python
# GitHub: 5000 istek/saat (authenticated)
# ✅ Rate limit kontrolü her istekten önce
remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
if remaining < 10:
    reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
    wait = reset_time - time.time()
    await asyncio.sleep(max(wait, 0))
```

### Redis Cache
```python
# ✅ Cache key formatı
cache_key = f"github:{owner}:{repo}:{tool_name}"

# ✅ TTL stratejisi
TTL = {
    "get_repo_info":       3600,   # 1 saat
    "list_commits":         300,   # 5 dakika
    "get_pr_diff":          600,   # 10 dakika
    "get_workflow_logs":     60,   # 1 dakika
    "get_file_content":    1800,   # 30 dakika
}
```

---

## 🌍 Ortam Değişkenleri (.env.example)

```bash
# GitHub Auth
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx      # PAT
GITHUB_CLIENT_ID=Ov23xxxxxxxxxxxxx         # OAuth App
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxx      # OAuth App

# Redis
REDIS_URL=redis://localhost:6379/0

# Server
MCP_SERVER_NAME=mcp-github-advanced
LOG_LEVEL=INFO
```

---

## 🧪 Test Kuralları

- Testlerde **asla gerçek GitHub API'ye istek atma** → `respx` mock kullan
- Her araç için: başarılı senaryo + 404 not found + 401 unauthorized + rate limit
- OAuth flow için: mock authorization code exchange

```python
# Test fixture şablonu
@pytest.fixture
def mock_github(respx_mock):
    respx_mock.get(
        "https://api.github.com/repos/owner/repo"
    ).mock(return_value=httpx.Response(200, json={
        "name": "repo",
        "stargazers_count": 100,
        "language": "Python",
    }))
    return respx_mock
```

---

## 🌍 Yayın Platformları

```
1. PyPI          → pip install mcp-github-advanced
2. Smithery.ai   → smithery.yaml ile
3. awesome-mcp-servers → PR: Developer Tools kategorisi
4. modelcontextprotocol/servers → PR: Community Servers
```

```yaml
# smithery.yaml
name: mcp-github-advanced
description: >
  Advanced GitHub MCP server. Repo analysis, PR management,
  code review, CI/CD monitoring and release management
  via GitHub REST + GraphQL API.
categories:
  - developer-tools
  - github
  - code-review
license: MIT
startCommand:
  type: stdio
  command: uvx
  args: ["mcp-github-advanced"]
```

---

## ⚠️ Önemli Kısıtlar

- **Rate Limit:** GitHub authenticated: 5000 istek/saat, GraphQL: 5000 puan/saat
- **Token Scope:** `repo` scope olmadan private repo'lara erişilemez
- **Diff Boyutu:** Çok büyük diff'ler (>1MB) chunk'lara bölünmeli
- **Webhook:** Sadece repo admin'i webhook ekleyebilir
- **PAT vs OAuth:** PAT sadece kendi repo'ları, OAuth başkasının repo'larına da erişir

---

## 📝 Git Commit Kuralları

```
feat: yeni araç veya özellik
fix: hata düzeltme
test: test ekleme
docs: dokümantasyon
chore: bağımlılık / versiyon
perf: rate limit veya cache iyileştirmesi
security: token/auth güvenlik düzeltmesi
```

---

## 🤖 LLM — Google Gemini Flash

**Model:** `gemini-2.5-flash`

```python
# LangChain entegrasyonu — bu şekilde kullan
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,
    max_tokens=8192,
)
```

| Özellik | Değer |
|---------|-------|
| Context Window | 1M token |
| Max Output | 8192 token |
| Tool Calling | ✅ LangChain ile uyumlu |
| Async | ✅ Destekli |

**Kritik Kurallar:**
- MCP araç çıktıları **8192 token'ı geçmemeli** → büyük diff ve logları chunk'la
- `.env` dosyasına `GOOGLE_API_KEY` eklenmeli
- `temperature=0` zorunlu — kod analizinde tutarsızlık olmasın
- `langchain-google-genai` paketi kurulu olmalı