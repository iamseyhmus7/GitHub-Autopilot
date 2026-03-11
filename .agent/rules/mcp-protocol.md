---
description: mcp-github-advanced için MCP protokol kuralları ve konvansiyonları
---

# MCP Protokol Kuralları

## Sunucu Uygulaması

- Low-level `mcp.server.Server` kullanılır — `FastMCP` **KULLANILMAZ**
- Transport: `stdio` — `mcp.server.stdio.stdio_server` ile
- Araçlar `@app.list_tools()` ve `@app.call_tool()` dekoratörleri ile kaydedilir

## Araç Kaydı

- Tüm araçlar `server.py` içindeki `TOOLS` listesinde tanımlanır
- Her araçta şunlar gereklidir: `name`, `description`, `inputSchema`
- Giriş şeması JSON Schema formatını takip eder
- Zorunlu parametreler `"required"` dizisinde listelenir

## Araç Yanıt Formatı

- Her zaman `list[TextContent]` döndürülür
- Veri JSON olarak serileştirilir: `json.dumps(result, indent=2, ensure_ascii=False)`
- Hata durumunda: hata mesajı ile `TextContent` döndürülür (istisna fırlatılmaz)
- Çıktı 8192 token'ın altında tutulmak için kesilir

## Giriş Noktası

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

## Yaşam Döngüsü

1. `AuthManager`, `RedisCache`, `GitHubClient` başlatılır
2. `github_client.start()` ile HTTP bağlantıları açılır
3. `stdio_server()` bağlamı → `app.run()` çalıştırılır
4. Kapanışta: `github_client.close()` çağrılır

## Yeni Araç Ekleme

1. `github.py` içindeki `GitHubClient`'a yeni metod ekle
2. `server.py`'daki `TOOLS` listesine `Tool(...)` tanımı ekle
3. `_dispatch()` fonksiyonuna yeni `case` dalı ekle
4. Önbelleğe alınabilirse `cache.py`'ye TTL girişi ekle
5. `test_github.py` ve `test_server.py`'ye testler ekle

## LLM Entegrasyonu

- Model: `gemini-2.0-flash` — `langchain-google-genai` paketi ile
- `temperature=0` — tutarlı kod analizi için
- `max_tokens=8192` çıktı limiti
- Araç çıktıları bu limitin içinde kalmalıdır
