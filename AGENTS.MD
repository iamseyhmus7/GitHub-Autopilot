# AGENTS.md — mcp-github-advanced

## 🎯 Proje Amacı

Bu proje **GitHub API v3 (REST) + v4 (GraphQL)** entegrasyonunu
**MCP (Model Context Protocol)** üzerinden AI asistanlarına ve
LangChain/LangGraph agent'larına sunan production-grade bir sunucudur.

Herhangi bir GitHub kullanıcısının veya organizasyonunun repolarını
analiz edebilir, PR/Issue yönetimi yapabilir, CI/CD durumunu izleyebilir
ve otomatik code review yazabilir.

Bu server bir **web uygulamasının backend'i** olarak tasarlanmıştır:
- Frontend: **Next.js / React** (Aktif — Premium Dark UI)
- Backend: **FastAPI** (Aktif — SSE Streaming + REST API)
- Agent: **LangChain + LangGraph (10+1 Agent HR Sistemi Aktif — Paralel Fan-out/Fan-in)**
- LLM: **Google Gemini Flash** (`gemini-2.5-flash`)
- MCP: mcp-github-advanced (bu proje)

---

## 🏗️ Mimari Genel Bakış

```
┌─────────────────────────────────────────────┐
│              server.py                       │
│         15 MCP Aracı (@mcp.tool)            │
│         FastMCP dekoratör tabanlı            │
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

## 🤖 AI Ajan Mimarisi (LangGraph 10+1 Agent HR — Paralel)

`src/main.py`, `src/multi_agent.py` ve `src/api/main.py` içindeki sistem **10+1 ajan düğümü (node)** barındırır.

### Ajan Listesi
| # | Ajan | Dosya | Görev |
|---|------|-------|-------|
| 0 | **Smart Profiler** | `api/main.py` | İş ilanına en uygun projeyi seçer (repo_name boşsa) |
| 1 | Repo Explorer | `agents/discovery.py` | Proje haritası, kritik dosyalar |
| 2 | Dependency Analyst | `agents/discovery.py` | Teknoloji yığını ve kütüphane analizi |
| 3 | Architecture Reviewer | `agents/engineering.py` | Mimari kalıp tespiti (MVC, Clean vb.) |
| 4 | Code Quality Inspector | `agents/engineering.py` | SOLID, okunabilirlik, kod gözden geçirme |
| 5 | Security Agent | `agents/engineering.py` | Hardcoded secret ve zafiyet taraması |
| 6 | Git Historian | `agents/process.py` | Kopya/gerçek emek, commit analizi |
| 7 | DevOps Evaluator | `agents/process.py` | CI/CD, test altyapısı |
| 8 | PR Manager | `agents/process.py` | Branch, PR, issue kullanım kalitesi |
| 9 | History Analyzer | `agents/history.py` | Geçmiş analizlerle karşılaştırma (Kalıcı Bellek) |
| 10 | HR Synthesizer | `agents/synthesis.py` | Nihai İK Skor Kartı + Mülakat Soruları |
| — | Q&A Agent | `agents/qa_agent.py` | Rapor hakkında soru-cevap (bağımsız) |

### Paralel Çalışma Grafiği (Fan-out / Fan-in)
```
START ──▶ repo_explorer ──▶ dependency_analyst ──┬──▶ architecture_reviewer ──┐
                                                  ├──▶ code_quality ──────────┤
                                                  ├──▶ security ─────────────┤
                                                  ├──▶ git_historian ─────────┤
                                                  ├──▶ devops ────────────────┤
                                                  ├──▶ pr_manager ────────────┤
                                                  └──▶ history_analyzer ──────┘
                                                                              │
                                                                              ▼
                                                                       hr_synthesizer ──▶ END
```

**LangGraph Optimizasyon Kuralları (Maliyet Koruma):**
1. **Tool Filtering (Araç Filtreleme):** Tüm araçlar (15 şema) ajana YÜKLENMEMELİDİR. `allowed_tools=["search_code"]` argümanıyla sadece ilgili araçlar LLM'ye iletilir.
2. **Context Memory Bloat Koruması:** `HRGraphState` kullanılırken `checkpointer` (SqliteSaver) eski mülakatları hatırlamaması için `thread_id` değerleri **her yeni aday analizinde UUID ile benzersiz (unique)** üretilmelidir. (Örn: `hr_session_{owner}_{repo}_{uuid.uuid4().hex[:8]}`)
3. **Iteration Limit:** Ajanların takılıp kalmaması için LLM döngülerinde `max_iterations=2` sınırı tavsiye edilir.
4. **Timeout Koruması:** LLM çağrıları için **90 saniyelik**, araç (tool) çağrıları için **45 saniyelik** zaman sınırı uygulanır. Takılma (hang) riski ortadan kaldırılır.
5. **Global Tool Semaphore:** Paralel ajanlar aynı anda MCP aracı çağırabilir. `asyncio.Semaphore` ile eşzamanlı araç çağrısı sayısı sınırlanarak race condition önlenir.

---

## 📦 Teknoloji Yığını

| Katman | Teknoloji | Versiyon | Neden? |
|--------|-----------|----------|--------|
| MCP Protokolü | `mcp` | ≥1.19.0 | Resmi Python SDK |
| MCP Çerçeve | `fastmcp` | ≥2.0.0 | Dekoratör tabanlı sunucu + SSE transport |
| HTTP | `httpx` | ≥0.28.0 | Async, REST + GraphQL |
| Auth | `authlib` | ≥1.3.0 | OAuth 2.0 akışı |
| Cache | `redis[hiredis]` | ≥5.0.0 | Rate limit koruması |
| Retry | `tenacity` | ≥8.0.0 | GitHub API 429 yönetimi |
| Env | `python-dotenv` | ≥1.0.0 | Token yönetimi |
| Paketleme | `hatchling` | latest | Modern build backend |
| Test | `pytest` + `pytest-asyncio` | ≥8.3.0 | Async test |
| Mock | `respx` | ≥0.21.0 | HTTP mock |
| Linter | `ruff` | ≥0.8.0 | Hızlı linter |
| Web API | `fastapi` | latest | SSE Streaming + REST |
| Agent Orchestration | `langgraph` | latest | Paralel multi-agent graf |
| LLM | `langchain-google-genai` | latest | Gemini 2.5 Flash entegrasyonu |
| PDF | `fpdf2` | latest | DNA Rapor PDF dışa aktarımı |
| Frontend | `next.js` + `react` | 15.x | Premium İK Dashboard |
| Animasyon | `framer-motion` | latest | Mikro-animasyonlar |
| Markdown | `react-markdown` | latest | Rapor render |

---

## 📁 Klasör Yapısı

```
mcp-github-advanced/
├── AGENTS.md                          ← Bu dosya
├── README.md                          ← Kullanıcı dokümantasyonu
├── smithery.yaml                      ← Smithery.ai deployment
├── pyproject.toml                     ← Paket tanımı
├── .env.example                       ← Ortam değişkenleri
├── checkpoints.sqlite                 ← LangGraph kalıcı hafıza DB
│
├── src/
│   ├── main.py                        ← CLI giriş noktası (tek analiz)
│   ├── mcp_client.py                  ← MCP bağlantı yöneticisi
│   ├── multi_agent.py                 ← LangGraph paralel graf yapısı
│   ├── state.py                       ← HRGraphState (TypedDict şeması)
│   │
│   ├── agents/                        ← 10+1 Ajan Modülleri
│   │   ├── discovery.py               ← Ajan 1-2: Repo Explorer + Dependency Analyst
│   │   ├── engineering.py             ← Ajan 3-5: Architecture + Code Quality + Security
│   │   ├── process.py                 ← Ajan 6-8: Git Historian + DevOps + PR Manager
│   │   ├── history.py                 ← Ajan 9: History Analyzer (Kalıcı Bellek)
│   │   ├── synthesis.py               ← Ajan 10: HR Synthesizer (Nihai Rapor)
│   │   ├── qa_agent.py                ← Q&A Agent (Rapor hakkında soru-cevap)
│   │   └── llm_utils.py               ← LLM yardımcı fonksiyonları + timeout
│   │
│   ├── api/                           ← FastAPI Web Servisi
│   │   ├── __init__.py
│   │   ├── main.py                    ← 3 endpoint: analyze-stream, chat, pdf
│   │   └── schemas.py                 ← Pydantic request/response modelleri
│   │
│   └── mcp_github_advanced/           ← MCP Sunucu Paketi (PyPI)
│       ├── __init__.py                ← __version__
│       ├── __main__.py                ← python -m girişi
│       ├── server.py                  ← 15 MCP aracı
│       ├── github.py                  ← GitHub REST + GraphQL client
│       ├── auth.py                    ← OAuth + PAT yönetimi
│       └── cache.py                   ← Redis önbellekleme
│
├── frontend/                          ← Next.js Premium Dashboard
│   ├── src/app/
│   │   ├── page.tsx                   ← Ana sayfa (form + SSE + rapor + chat)
│   │   ├── layout.tsx                 ← Root layout + Inter font
│   │   ├── globals.css                ← Dark theme + glassmorphism
│   │   └── Landing.module.css         ← Hero + form + dashboard stilleri
│   └── src/components/
│       ├── AgentGrid.tsx              ← 10 ajan kartı (canlı durum)
│       ├── AgentCard.module.css       ← Ajan kart stilleri
│       ├── ScoreCard.tsx              ← Dairesel puan barları
│       └── ScoreCard.module.css       ← Skor kart stilleri
│
├── tests/
│   ├── conftest.py                    ← Test fixtures
│   ├── test_github.py                 ← GitHub client testleri
│   ├── test_auth.py                   ← Auth testleri
│   └── test_server.py                 ← MCP araç testleri
│
└── .agent/
    ├── rules/
    ├── workflows/
    │   ├── add-tool.md
    │   └── publish-to-pypi.md
    └── skills/
        └── github-mcp/
            └── SKILL.md
```

---

## 🛠️ 15 MCP Aracı

### 📁 Repo Araçları

| Araç | Açıklama | Zorunlu Parametre |
|------|----------|-------------------|
| `list_user_repos` | Bir kullanıcının tüm genel repolarını listeler | `username` |
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
    "list_user_repos":     3600,   # 1 saat
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

# LLM (Gemini)
GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXX  # Zorunlu — Multi-Agent LLM
```

---

## 🌐 FastAPI Endpoint'leri

| Endpoint | Metot | Açıklama |
|----------|-------|----------|
| `/api/v1/analyze-stream` | `POST` | SSE ile canlı 10-ajan analiz akışı |
| `/api/chat` | `POST` | Rapor hakkında Q&A (thread_id + query) |
| `/api/report/pdf/{thread_id}` | `GET` | DNA Raporunu PDF olarak indir |

### SSE Akış Formatı
```json
{"type": "system", "message": "📦 Aday profili taranıyor..."}
{"type": "agent_update", "node": "repo_explorer", "agent": "Repo Explorer", "status": "completed"}
{"type": "final_report", "report": "## Nihai İK Skor Kartı..."}
{"type": "error", "message": "Hata açıklaması"}
```

### FastAPI Başlatma
```bash
uvicorn src.api.main:app --reload --port 8000
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

> **SSE Transport ile çalıştırma:**
> ```bash
> fastmcp run src/mcp_github_advanced/server.py:mcp --transport sse --port 8080
> ```

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