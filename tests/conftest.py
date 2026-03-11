"""conftest.py — mcp-github-advanced testleri için paylaşılan pytest fixture'ları.

Tüm GitHub API isteklerini mocklamak için respx kullanılır — gerçek HTTP çağrısı yapılmaz.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from mcp_github_advanced.auth import AuthManager, AuthSettings
from mcp_github_advanced.cache import RedisCache
from mcp_github_advanced.github import GitHubClient


# ── Ortam değişkenleri ────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Tüm testler için varsayılan ortam değişkenlerini ayarlar."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_1234567890")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "Ov23test_client_id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test_client_secret_abcdef")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")


# ── Kimlik doğrulama ─────────────────────────────────────────────────
@pytest.fixture
def auth_settings() -> AuthSettings:
    """Test için kimlik doğrulama ayarları oluşturur."""
    return AuthSettings(
        github_token="ghp_test_token_1234567890",
        github_client_id="Ov23test_client_id",
        github_client_secret="test_client_secret_abcdef",
    )


@pytest.fixture
def auth_manager(auth_settings) -> AuthManager:
    """Test için kimlik doğrulama yöneticisi oluşturur."""
    return AuthManager(auth_settings)


# ── Önbellek (devre dışı) ────────────────────────────────────────────
@pytest.fixture
def no_cache() -> None:
    """Testlerde önbelleklemeyi devre dışı bırakmak için None döner."""
    return None


# ── GitHub İstemcisi ──────────────────────────────────────────────────
@pytest.fixture
async def github_client(auth_manager) -> GitHubClient:
    """Önbelleksiz, mocklanmış HTTP ile GitHubClient oluşturur."""
    client = GitHubClient(auth=auth_manager, cache=None)
    await client.start()
    yield client
    await client.close()


# ── respx mock yardımcıları ──────────────────────────────────────────
@pytest.fixture
def mock_github(respx_mock):
    """Yaygın GitHub API yanıtları ile önceden yapılandırılmış respx mock'u."""

    # GET /repos/owner/repo — repo bilgileri
    respx_mock.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(200, json={
            "name": "repo",
            "full_name": "owner/repo",
            "description": "Bir test reposu",
            "language": "Python",
            "stargazers_count": 100,
            "forks_count": 10,
            "open_issues_count": 5,
            "size": 1024,
            "default_branch": "main",
            "private": False,
            "html_url": "https://github.com/owner/repo",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-06-01T00:00:00Z",
            "topics": ["mcp", "github"],
            "license": {"spdx_id": "MIT"},
        })
    )

    # GET /repos/owner/repo/commits — commit listesi
    respx_mock.get("https://api.github.com/repos/owner/repo/commits").mock(
        return_value=httpx.Response(200, json=[
            {
                "sha": "abc1234567890",
                "commit": {
                    "message": "feat: ilk commit",
                    "author": {"name": "Test Kullanıcı", "date": "2024-01-01T00:00:00Z"},
                },
            },
        ])
    )

    # GET /repos/owner/repo/issues — issue listesi
    respx_mock.get("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=httpx.Response(200, json=[
            {
                "number": 1,
                "title": "Test Issue",
                "state": "open",
                "user": {"login": "testuser"},
                "labels": [{"name": "bug"}],
                "created_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/1",
            },
        ])
    )

    # GET /repos/owner/repo/pulls — PR listesi
    respx_mock.get("https://api.github.com/repos/owner/repo/pulls").mock(
        return_value=httpx.Response(200, json=[
            {
                "number": 42,
                "title": "Test PR",
                "state": "open",
                "user": {"login": "testuser"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_url": "https://github.com/owner/repo/pull/42",
                "labels": [],
            },
        ])
    )

    return respx_mock


# ── 401 Yetkisiz mock ────────────────────────────────────────────────
@pytest.fixture
def mock_github_401(respx_mock):
    """Tüm uç noktalar için 401 Yetkisiz döndüren mock."""
    respx_mock.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    return respx_mock


# ── 404 Bulunamadı mock ──────────────────────────────────────────────
@pytest.fixture
def mock_github_404(respx_mock):
    """404 Bulunamadı döndüren mock."""
    respx_mock.get("https://api.github.com/repos/owner/notfound").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    return respx_mock


# ── Rate Limit mock ──────────────────────────────────────────────────
@pytest.fixture
def mock_github_rate_limit(respx_mock):
    """Rate limit yanıtını simüle eden mock."""
    respx_mock.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1700000000",
            },
        )
    )
    return respx_mock
