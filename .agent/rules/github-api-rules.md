---
description: mcp-github-advanced için GitHub API kuralları ve konvansiyonları
---

# GitHub API Kuralları

## Versiyonlu Header'lar (ZORUNLU)

Her GitHub API isteğinde şu header'lar **mutlaka** bulunmalıdır:

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
```

Bu header'lar olmadan **asla** GitHub API isteği gönderilmez.

## Rate Limit (İstek Sınırı)

- Kimlik doğrulamalı: 5000 istek/saat (REST), 5000 puan/saat (GraphQL)
- Her yanıttan sonra `X-RateLimit-Remaining` kontrol edilir
- Kalan < 10 olduğunda: `X-RateLimit-Reset` zamanına kadar beklenir
- 429/403 yanıtları için `tenacity` ile üstel geri çekilme (exponential backoff) uygulanır

```python
remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
if remaining < 10:
    reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
    wait = reset_time - time.time()
    await asyncio.sleep(max(wait, 0))
```

## Çıktı Sınırları

- MCP araç çıktıları **8192 token'ı (~30.000 karakter) aşmamalıdır**
- Büyük diff'ler (>1MB) chunk'lara bölünmelidir
- Kısaltma için `_chunk_text()` yardımcı fonksiyonu kullanılır

## REST API Kalıpları

- Temel URL: `https://api.github.com`
- Zaman aşımı: 30 saniye
- Sayfalama: `per_page` parametresi kullanılır (maks. 100)
- Hata yanıtları: `httpx.HTTPStatusError` fırlatılır

## GraphQL API

- Uç nokta: `https://api.github.com/graphql`
- Şu durumlarda kullanılır: katkıda bulunan istatistikleri, karmaşık sorgular
- Yanıtta `data.errors` kontrol edilir

## Token İzinleri (Scopes)

- `repo`: Özel (private) repolar için gerekli
- `read:user`: Kullanıcı profili için gerekli
- PAT: Yalnızca kendi repoları için çalışır
- OAuth: Başka kullanıcıların repolarına da erişebilir (izin ile)

## Önbellekleme (Caching)

- Önbellek anahtar formatı: `github:{owner}:{repo}:{tool_name}`
- Yazma işlemleri **asla** önbelleğe alınmaz (create_issue, create_pr_review)
- TTL değerleri `cache.py` içinde tanımlıdır
