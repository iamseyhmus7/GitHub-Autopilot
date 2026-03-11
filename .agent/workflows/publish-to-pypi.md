---
description: How to publish mcp-github-advanced to PyPI
---

# Publish to PyPI

## Prerequisites

- PyPI account with API token
- `build` and `twine` packages installed

## Steps

### 1. Update Version

Edit `src/mcp_github_advanced/__init__.py`:

```python
__version__ = "0.1.1"  # bump version
```

### 2. Clean Previous Builds

```bash
rm -rf dist/ build/ *.egg-info
```

### 3. Build Package

```bash
pip install build
python -m build
```

This creates:
- `dist/mcp_github_advanced-0.1.1.tar.gz`
- `dist/mcp_github_advanced-0.1.1-py3-none-any.whl`

### 4. Check Package

```bash
pip install twine
twine check dist/*
```

### 5. Upload to Test PyPI (Optional)

```bash
twine upload --repository testpypi dist/*
```

Verify: `pip install -i https://test.pypi.org/simple/ mcp-github-advanced`

### 6. Upload to PyPI

```bash
twine upload dist/*
```

You'll be prompted for:
- Username: `__token__`
- Password: your PyPI API token (`pypi-...`)

### 7. Verify Installation

```bash
pip install mcp-github-advanced
uvx mcp-github-advanced --help
```

### 8. Create Git Tag

```bash
git tag -a v0.1.1 -m "Release v0.1.1"
git push origin v0.1.1
```

### 9. Create GitHub Release

Create a release on GitHub from the tag with changelog.

## CI/CD Automation (Optional)

Add to `.github/workflows/publish.yml` for automated releases on tag push:

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
