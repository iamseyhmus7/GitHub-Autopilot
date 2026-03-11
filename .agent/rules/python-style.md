---
description: mcp-github-advanced için Python stil ve formatlama kuralları
---

# Python Stil Kuralları

## Genel
- Python 3.10+ ile `from __future__ import annotations` kullanılır
- Satır uzunluğu: en fazla 100 karakter (`pyproject.toml`'de yapılandırılır)
- Lint için `ruff` kullanılır: `ruff check src/ tests/`

## Formatlama
- Girintileme: 4 boşluk (tab yok)
- String'ler için çift tırnak kullanılır
- Çok satırlı yapılarda sondaki virgül yazılır
- `.format()` veya `%` yerine f-string tercih edilir

## Tür İpuçları (Type Hints)
- Tüm fonksiyon imzalarında tür ipucu kullanılır
- Nullable türler için `Optional[T]` veya `T | None` kullanılır
- Büyük harfli jenerikler yerine küçük harfli kullanılır: `dict[str, Any]` (`Dict[str, Any]` değil)

## İçe Aktarmalar (Imports)
- Gruplandırma sırası: stdlib → üçüncü parti → yerel
- `ruff` ile otomatik sıralama yapılır (`select = ["I"]` pyproject.toml'de)
- Mutlak import tercih edilir

## İsimlendirme
- `snake_case` → fonksiyonlar, değişkenler, modüller
- `PascalCase` → sınıflar
- `UPPER_SNAKE_CASE` → sabitler
- Özel (private) metod ve nitelikler `_` ile başlar

## Asenkron (Async)
- Tüm GitHub API etkileşimleri async olmalıdır (`async def`)
- `requests` yerine `httpx.AsyncClient` kullanılır
- `asyncio.run()` yalnızca giriş noktalarında kullanılır

## Docstring'ler
- Tüm public fonksiyon ve sınıflar için Google-stil docstring yazılır
- Gerektiğinde `Args:`, `Returns:`, `Raises:` bölümleri eklenir

## Hata Yönetimi
- İstisnalar sessizce yutulmaz
- Kritik olmayan hatalar için uyarı loglanır (örn: önbellek ıskalamaları)
- Genel `Exception` yerine spesifik istisnalar fırlatılır
