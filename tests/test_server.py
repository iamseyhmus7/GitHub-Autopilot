"""test_server.py — MCP sunucu araç kaydı ve yönlendirme testleri.

15 aracın doğru kaydedildiğini, call_tool'un doğru yönlendirdiğini
ve yanıtların string olarak formatlandığını doğrular.
Tüm testler respx mock'ları kullanır — gerçek GitHub API isteği yapılmaz.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mcp_github_advanced.server import mcp, _get_github, _to_json
import mcp_github_advanced.server as srv


# ══════════════════════════════════════════════════════════════════════
#  Yardımcı — Test ortamı için GitHubClient kurulumu
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
async def setup_github():
    """Test için GitHubClient'ı oluşturup bağlar, test sonunda kapatır."""
    from mcp_github_advanced.auth import AuthManager, AuthSettings
    from mcp_github_advanced.github import GitHubClient

    settings = AuthSettings(github_token="ghp_test")
    auth = AuthManager(settings)
    srv._github = GitHubClient(auth=auth, cache=None)
    await srv._github.start()
    yield
    await srv._github.close()
    srv._github = None


# ══════════════════════════════════════════════════════════════════════
#  Araç Kaydı — 15 aracın doğru tanımlandığını doğrular
# ══════════════════════════════════════════════════════════════════════

class TestToolRegistration:
    async def test_15_arac_kayitli(self):
        """FastMCP'de tam olarak 15 araç kayıtlı olmalı."""
        tools = await mcp.list_tools()
        assert len(tools) == 15

    async def test_tum_arac_isimleri(self):
        """Tüm beklenen araç isimleri mevcut olmalı."""
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        expected = {
            "list_user_repos",
            "get_repo_info",
            "get_file_content",
            "list_repo_files",
            "search_code",
            "list_commits",
            "get_commit_diff",
            "get_contributor_stats",
            "list_pull_requests",
            "get_pr_diff",
            "create_pr_review",
            "list_issues",
            "create_issue",
            "get_workflow_runs",
            "get_workflow_logs",
        }
        assert names == expected

    async def test_tum_araclar_aciklama_var(self):
        """Her aracın açıklaması (description) olmalı."""
        tools = await mcp.list_tools()
        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10


# ══════════════════════════════════════════════════════════════════════
#  Araç Yönlendirme — doğru metoda yönlendiriyor mu?
# ══════════════════════════════════════════════════════════════════════

class TestToolDispatch:
    @respx.mock
    async def test_get_repo_info_yonlendirme(self, setup_github):
        """get_repo_info doğru çalışmalı."""
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={
                "name": "repo",
                "full_name": "owner/repo",
                "description": "Test reposu",
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
                "topics": ["mcp"],
                "license": {"spdx_id": "MIT"},
            })
        )

        # Doğrudan fonksiyonu çağır (FastMCP dekoratörler fonksiyonu korur)
        from mcp_github_advanced.server import get_repo_info
        result = await get_repo_info(owner="owner", repo="repo")
        data = json.loads(result)
        assert data["name"] == "repo"
        assert data["stargazers_count"] == 100

    @respx.mock
    async def test_list_commits_yonlendirme(self, setup_github):
        """list_commits doğru çalışmalı."""
        respx.get("https://api.github.com/repos/owner/repo/commits").mock(
            return_value=httpx.Response(200, json=[
                {
                    "sha": "abc1234567890",
                    "commit": {
                        "message": "feat: test",
                        "author": {"name": "Dev", "date": "2024-01-01T00:00:00Z"},
                    },
                },
            ])
        )

        from mcp_github_advanced.server import list_commits
        result = await list_commits(owner="owner", repo="repo")
        data = json.loads(result)
        assert isinstance(data, list)
        assert data[0]["sha"] == "abc1234"

    @respx.mock
    async def test_create_issue_yonlendirme(self, setup_github):
        """create_issue yazma işlemi doğru çalışmalı."""
        respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={
                "number": 99,
                "title": "Yeni Hata",
                "html_url": "https://github.com/owner/repo/issues/99",
                "state": "open",
            })
        )

        from mcp_github_advanced.server import create_issue
        result = await create_issue(owner="owner", repo="repo", title="Yeni Hata")
        data = json.loads(result)
        assert data["number"] == 99
        assert data["title"] == "Yeni Hata"


# ══════════════════════════════════════════════════════════════════════
#  Yardımcı Fonksiyon Testleri
# ══════════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_to_json_normal(self):
        """Normal boyuttaki veri kesim yapılmadan JSON'a çevrilmeli."""
        data = {"name": "test", "count": 42}
        result = _to_json(data)
        parsed = json.loads(result)
        assert parsed["name"] == "test"

    def test_to_json_truncation(self):
        """Büyük veri 8192 token sınırına göre kesilmeli."""
        big_data = {"content": "x" * 40_000}
        result = _to_json(big_data)
        assert "kesildi" in result
        assert len(result) < 35_000
