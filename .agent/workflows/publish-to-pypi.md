---
description: mcp-github-advanced paketini PyPI'ye nasıl yayınlanır
---

# PyPI'ye Yayınlama

## Ön Koşullar

- API token'ı olan bir PyPI hesabı
- `build` ve `twine` paketlerinin kurulu olması

## Adımlar

### 1. Versiyonu Güncelle

`src/mcp_github_advanced/__init__.py` dosyasını düzenleyin:

```python
__version__ = "0.1.1"  # versiyonu artır
```

### 2. Önceki Derleme Dosyalarını Temizle

```bash
rm -rf dist/ build/ *.egg-info
```

### 3. Paketi Derle

```bash
pip install build
python -m build
```

Bu şunları oluşturur:
- `dist/mcp_github_advanced-0.1.1.tar.gz`
- `dist/mcp_github_advanced-0.1.1-py3-none-any.whl`

### 4. Paketi Kontrol Et

```bash
pip install twine
twine check dist/*
```

### 5. Test PyPI'ye Yükle (Opsiyonel)

```bash
twine upload --repository testpypi dist/*
```

Doğrulama: `pip install -i https://test.pypi.org/simple/ mcp-github-advanced`

### 6. PyPI'ye Yükle

```bash
twine upload dist/*
```

Şunlar sorulacaktır:
- Kullanıcı adı: `__token__`
- Şifre: PyPI API token'ınız (`pypi-...`)

### 7. Kurulumu Doğrula

```bash
pip install mcp-github-advanced
uvx mcp-github-advanced --help
```

### 8. Git Etiketi Oluştur

```bash
git tag -a v0.1.1 -m "Sürüm v0.1.1"
git push origin v0.1.1
```

### 9. GitHub Sürümü Oluştur

Etiketten bir GitHub sürümü oluşturun ve değişiklik günlüğünü ekleyin.

## CI/CD Otomasyonu (Opsiyonel)

Etiket push'unda otomatik yayınlama için `.github/workflows/publish.yml` ekleyin:

```yaml
on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```
