---
name: github-mcp
description: mcp-github-advanced MCP sunucu kod tabanı ile çalışma becerisi
---

# GitHub MCP Becerisi

Bu beceri, `mcp-github-advanced` MCP sunucu kod tabanı ile çalışmak için talimatlar sağlar.

## Genel Bakış

`mcp-github-advanced`, Model Context Protocol üzerinden 14 GitHub API aracını sunan bir MCP sunucusudur. Desteklediği özellikler:

- **GitHub REST API v3** — repolar, commit'ler, PR'lar, issue'lar, actions
- **GitHub GraphQL v4** — katkıda bulunan istatistikleri, karmaşık sorgular
- **Redis önbellekleme** — akıllı TTL stratejisi ile
- **PAT + OAuth 2.0** — çift kimlik doğrulama desteği
- **LLM entegrasyonu** — `gemini-2.5-flash` ve `langchain-google-genai` ile

## Mimari

```
server.py  →  14 MCP aracı (list_tools + call_tool)
  ├── github.py  →  REST + GraphQL istemcisi (httpx async)
  ├── auth.py    →  PAT + OAuth 2.0 kimlik doğrulama
  └── cache.py   →  TTL stratejili Redis önbellekleme
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
| Yazma işlemleri | Önbellek yok |

### 5. Test Etme

- HTTP mocklama için **her zaman** `respx` kullanılır
- Testlerde **asla** gerçek GitHub API'ye istek gönderilmez
- Test senaryoları: başarılı, 404, 401, rate limit

### 6. LLM

- Model: `gemini-2.5-flash`
- `temperature=0` — tutarlı kod analizi için
- `max_tokens=8192`
- Paket: `langchain-google-genai`

## Sık Yapılan İşlemler

- **Araç ekle**: Bkz. `.agent/workflows/add-tool.md`
- **Yayınla**: Bkz. `.agent/workflows/publish-to-pypi.md`
- **Test çalıştır**: `pytest` (`asyncio_mode = "auto"` ile)
- **Lint**: `ruff check src/ tests/`

## Dosya Haritası

| Dosya | Amacı |
|-------|-------|
| `server.py` | MCP sunucusu, 14 araç tanımı, yönlendirici |
| `github.py` | GitHub API istemcisi (REST + GraphQL) |
| `auth.py` | PAT + OAuth 2.0 kimlik doğrulama |
| `cache.py` | TTL'li Redis önbellekleme |
| `__init__.py` | Versiyon bilgisi |
| `__main__.py` | `python -m` giriş noktası |
