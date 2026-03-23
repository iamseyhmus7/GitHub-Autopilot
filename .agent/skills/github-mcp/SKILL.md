---
name: github-mcp
description: mcp-github-advanced MCP sunucu kod tabanı ile çalışma becerisi
---

# GitHub MCP Becerisi

Bu beceri, `mcp-github-advanced` MCP sunucu kod tabanı ile çalışmak için talimatlar sağlar.

## Genel Bakış

`mcp-github-advanced`, Model Context Protocol üzerinden 15 GitHub API aracını sunan bir MCP sunucusudur. Ayrıca **10+1 Ajanlı Paralel İK Analiz Platformu** barındırır. Desteklediği özellikler:

- **GitHub REST API v3** — repolar, commit'ler, PR'lar, issue'lar, actions
- **GitHub GraphQL v4** — katkıda bulunan istatistikleri, karmaşık sorgular
- **Redis önbellekleme** — akıllı TTL stratejisi ile
- **PAT + OAuth 2.0** — çift kimlik doğrulama desteği
- **LLM entegrasyonu** — `gemini-2.5-flash` ve `langchain-google-genai` ile
- **Paralel Multi-Agent** — LangGraph fan-out/fan-in mimarisi (10+1 ajan)
- **FastAPI Backend** — SSE streaming + REST API
- **Next.js Frontend** — Premium dark theme İK dashboard

## Mimari

```
server.py  →  15 MCP aracı (FastMCP @mcp.tool dekoratörleri)
              Hem stdio hem SSE (HTTP) transport destekler
  ├── github.py  →  REST + GraphQL istemcisi (httpx async)
  ├── auth.py    →  PAT + OAuth 2.0 kimlik doğrulama
  └── cache.py   →  TTL stratejili Redis önbellekleme

multi_agent.py →  LangGraph paralel graf (fan-out/fan-in)
  ├── agents/discovery.py     →  Repo Explorer + Dependency Analyst
  ├── agents/engineering.py   →  Architecture + Code Quality + Security
  ├── agents/process.py       →  Git Historian + DevOps + PR Manager
  ├── agents/history.py       →  History Analyzer (Kalıcı Bellek)
  ├── agents/synthesis.py     →  HR Synthesizer (Nihai Rapor)
  ├── agents/qa_agent.py      →  Rapor hakkında Q&A
  └── agents/llm_utils.py     →  LLM yardımcıları + timeout

api/main.py →  FastAPI Web Servisi
  ├── POST /api/v1/analyze-stream  →  SSE canlı analiz akışı
  ├── POST /api/chat               →  Rapor Q&A
  └── GET  /api/report/pdf/{id}    →  PDF DNA Raporu dışa aktarım
```

## Temel Konvansiyonlar

### 1. Versiyonlu API Header'ları

**Her** GitHub API isteğinde şunlar bulunmalıdır:
```python
{
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
```

### 2. Rate Limit (İstek Sınırı)

- Her yanıttan sonra `X-RateLimit-Remaining` kontrol edilir
- Kalan < 10 olduğunda bekle
- 429/403 için `tenacity` retry kullan

### 3. Çıktı Kesme (Chunking)

- Maksimum çıktı ≈ 30.000 karakter (~8192 token)
- Kısaltma için `_chunk_text()` kullanılır
- Tek dosya yama (patch) çıktısı 5000 karakterle sınırlıdır

### 4. Önbellek TTL Stratejisi

| Araç | TTL |
|------|-----|
| `get_repo_info` | 1 saat |
| `list_commits` | 5 dk |
| `get_pr_diff` | 10 dk |
| `get_workflow_logs` | 1 dk |
| `get_file_content` | 30 dk |
| `list_user_repos` | 1 saat |
| Yazma işlemleri | Önbellek yok |

### 5. Timeout & Eşzamanlılık Kuralları

- LLM çağrıları: **90 saniye** timeout
- Araç (tool) çağrıları: **45 saniye** timeout
- Paralel ajanlar için `asyncio.Semaphore` ile eşzamanlı araç çağrısı sınırlandırılır
- Her ajan `max_iterations=2` sınırıyla çalışır

### 6. Test Etme

- HTTP mocklama için **her zaman** `respx` kullanılır
- Testlerde **asla** gerçek GitHub API'ye istek gönderilmez
- Test senaryoları: başarılı, 404, 401, rate limit

### 7. LLM

- Model: `gemini-2.5-flash`
- `temperature=0` — tutarlı kod analizi için
- `max_tokens=8192`
- Paket: `langchain-google-genai`

## Sık Yapılan İşlemler

- **Araç ekle**: Bkz. `.agent/workflows/add-tool.md`
- **Yayınla**: Bkz. `.agent/workflows/publish-to-pypi.md`
- **Test çalıştır**: `pytest` (`asyncio_mode = "auto"` ile)
- **Lint**: `ruff check src/ tests/`
- **Backend başlat**: `uvicorn src.api.main:app --reload --port 8000`
- **SSE MCP başlat**: `fastmcp run src/mcp_github_advanced/server.py:mcp --transport sse --port 8080`
- **Frontend başlat**: `cd frontend && npm run dev`

## Dosya Haritası

| Dosya | Amacı |
|-------|-------|
| `server.py` | MCP sunucusu, 15 araç tanımı, yönlendirici |
| `github.py` | GitHub API istemcisi (REST + GraphQL) |
| `auth.py` | PAT + OAuth 2.0 kimlik doğrulama |
| `cache.py` | TTL'li Redis önbellekleme |
| `__init__.py` | Versiyon bilgisi |
| `__main__.py` | `python -m` giriş noktası |
| `main.py` | CLI giriş noktası (tek analiz) |
| `multi_agent.py` | LangGraph paralel graf yapısı |
| `state.py` | HRGraphState (TypedDict şeması) |
| `agents/discovery.py` | Repo Explorer + Dependency Analyst |
| `agents/engineering.py` | Architecture + Code Quality + Security |
| `agents/process.py` | Git Historian + DevOps + PR Manager |
| `agents/history.py` | History Analyzer (Kalıcı Bellek) |
| `agents/synthesis.py` | HR Synthesizer (Nihai Rapor) |
| `agents/qa_agent.py` | Q&A Agent (Rapor soru-cevap) |
| `agents/llm_utils.py` | LLM yardımcı fonksiyonları + timeout |
| `api/main.py` | FastAPI Web Servisi (3 endpoint) |
| `api/schemas.py` | Pydantic request/response modelleri |
| `frontend/src/app/page.tsx` | Ana sayfa (form + SSE + rapor + chat) |
| `frontend/src/components/AgentGrid.tsx` | 10 ajan kartı (canlı durum) |
| `frontend/src/components/ScoreCard.tsx` | Dairesel puan barları |
