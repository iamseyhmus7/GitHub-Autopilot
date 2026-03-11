---
description: Sunucuya yeni bir MCP aracı nasıl eklenir
---

# Yeni MCP Aracı Ekleme

`mcp-github-advanced` sunucusuna yeni bir araç eklemek için şu adımları izleyin.

## 1. GitHub İstemci Metodunu Uygula

`src/mcp_github_advanced/github.py` dosyasında `GitHubClient`'a yeni bir async metod ekleyin:

```python
async def yeni_arac_adi(self, owner: str, repo: str, ...) -> dict:
    """Bu aracın ne yaptığını açıklayan docstring."""
    # Önbellekten kontrol et
    if self.cache:
        cached = await self.cache.get(owner, repo, "yeni_arac_adi")
        if cached:
            return cached

    # Versiyonlu header'lar ile API isteği gönder (self.headers ile otomatik)
    resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}/endpoint")
    data = resp.json()

    # Yanıtı dönüştür
    result = { ... }

    # Büyük çıktıları kes
    if "content" in result:
        result["content"] = _chunk_text(result["content"])

    # Sonucu önbelleğe al
    if self.cache:
        await self.cache.set(owner, repo, "yeni_arac_adi", result)
    return result
```

## 2. Önbellek TTL'si Ekle

`src/mcp_github_advanced/cache.py` dosyasına TTL girişi ekleyin:

```python
TTL = {
    ...
    "yeni_arac_adi": 300,  # 5 dakika (veya uygun TTL değeri)
}
```

## 3. Aracı Kaydet

`src/mcp_github_advanced/server.py` dosyasındaki `TOOLS` listesine ekleyin:

```python
Tool(
    name="yeni_arac_adi",
    description="Aracın ne yaptığının açıklaması",
    inputSchema={
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Repo sahibi"},
            "repo": {"type": "string", "description": "Repo adı"},
            # ... ek parametreler
        },
        "required": ["owner", "repo"],
    },
),
```

## 4. Yönlendirme Dalı Ekle

`server.py`'deki `_dispatch()` fonksiyonuna:

```python
case "yeni_arac_adi":
    return await gh.yeni_arac_adi(owner, repo, ...)
```

## 5. Testleri Yaz

`tests/test_github.py` dosyasına:

```python
class TestYeniAracAdi:
    @respx.mock
    async def test_basarili(self, github_client):
        respx.get("https://api.github.com/repos/owner/repo/endpoint").mock(
            return_value=httpx.Response(200, json={...})
        )
        result = await github_client.yeni_arac_adi("owner", "repo")
        assert result[...] == beklenen_deger

    @respx.mock
    async def test_404_bulunamadi(self, github_client):
        # 404 senaryosunu test et
        ...

    @respx.mock
    async def test_401_yetkisiz(self, github_client):
        # Yetkisiz erişim senaryosunu test et
        ...
```

## 6. Dokümantasyonu Güncelle

- `AGENTS.md` içindeki araç tablosuna ekle
- `README.md` özellikler tablosuna ekle
- Gerekirse `__init__.py`'deki versiyonu artır

## 7. Commit At

```bash
git add .
git commit -m "feat: yeni_arac_adi araci eklendi"
```
