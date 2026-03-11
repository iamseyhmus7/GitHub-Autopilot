"""test_server.py — MCP sunucu araç kaydı ve yönlendirme testleri.

14 aracın doğru kaydedildiğini, call_tool'un doğru yönlendirdiğini
ve yanıtların TextContent olarak formatlandığını doğrular.
Tüm testler respx mock'ları kullanır — gerçek GitHub API isteği yapılmaz.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mcp_github_advanced.server import TOOLS, handle_call_tool, handle_list_tools


# ══════════════════════════════════════════════════════════════════════
#  Araç Kaydı — 14 aracın doğru tanımlandığını doğrular
# ══════════════════════════════════════════════════════════════════════

class TestToolRegistration:
    async def test_14_arac_dondurur(self):
        """list_tools() tam olarak 14 araç döndürmeli."""
        tools = await handle_list_tools()
        assert len(tools) == 14

    async def test_tum_arac_isimleri(self):
        """Tüm beklenen araç isimleri mevcut olmalı."""
        tools = await handle_list_tools()
        names = {t.name for t in tools}
        expected = {
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

    async def test_tum_araclar_giris_semasi_var(self):
        """Her aracın inputSchema tanımı olmalı."""
        tools = await handle_list_tools()
        for tool in tools:
            assert tool.inputSchema is not None
            assert "properties" in tool.inputSchema
            assert "required" in tool.inputSchema

    async def test_tum_araclar_aciklama_var(self):
        """Her aracın açıklaması (description) olmalı."""
        tools = await handle_list_tools()
        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10


# ══════════════════════════════════════════════════════════════════════
#  Araç Yönlendirme — call_tool() doğru metoda yönlendiriyor mu?
# ══════════════════════════════════════════════════════════════════════

class TestToolDispatch:
    async def test_bilinmeyen_arac(self):
        """Bilinmeyen araç hata mesajı döndürmeli, istisna fırlatmamalı."""
        from mcp_github_advanced.auth import AuthManager, AuthSettings
        from mcp_github_advanced.github import GitHubClient
        import mcp_github_advanced.server as srv

        settings = AuthSettings(github_token="ghp_test")
        auth = AuthManager(settings)
        srv._github = GitHubClient(auth=auth, cache=None)
        await srv._github.start()

        try:
            result = await handle_call_tool("olmayan_arac", {})
            assert len(result) == 1
            assert "Bilinmeyen araç" in result[0].text
        finally:
            await srv._github.close()
            srv._github = None

    @respx.mock
    async def test_get_repo_info_yonlendirme(self):
        """get_repo_info sunucu üzerinden doğru yönlendirilmeli."""
        from mcp_github_advanced.auth import AuthManager, AuthSettings
        from mcp_github_advanced.github import GitHubClient
        import mcp_github_advanced.server as srv

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

        settings = AuthSettings(github_token="ghp_test")
        auth = AuthManager(settings)
        srv._github = GitHubClient(auth=auth, cache=None)
        await srv._github.start()

        try:
            result = await handle_call_tool(
                "get_repo_info", {"owner": "owner", "repo": "repo"}
            )
            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["name"] == "repo"
            assert data["stargazers_count"] == 100
        finally:
            await srv._github.close()
            srv._github = None

    @respx.mock
    async def test_list_commits_yonlendirme(self):
        """list_commits sunucu üzerinden doğru yönlendirilmeli."""
        from mcp_github_advanced.auth import AuthManager, AuthSettings
        from mcp_github_advanced.github import GitHubClient
        import mcp_github_advanced.server as srv

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

        settings = AuthSettings(github_token="ghp_test")
        auth = AuthManager(settings)
        srv._github = GitHubClient(auth=auth, cache=None)
        await srv._github.start()

        try:
            result = await handle_call_tool(
                "list_commits", {"owner": "owner", "repo": "repo"}
            )
            data = json.loads(result[0].text)
            assert isinstance(data, list)
            assert data[0]["sha"] == "abc1234"
        finally:
            await srv._github.close()
            srv._github = None

    @respx.mock
    async def test_create_issue_yonlendirme(self):
        """create_issue yazma işlemi sunucu üzerinden çalışmalı."""
        from mcp_github_advanced.auth import AuthManager, AuthSettings
        from mcp_github_advanced.github import GitHubClient
        import mcp_github_advanced.server as srv

        respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={
                "number": 99,
                "title": "Yeni Hata",
                "html_url": "https://github.com/owner/repo/issues/99",
                "state": "open",
            })
        )

        settings = AuthSettings(github_token="ghp_test")
        auth = AuthManager(settings)
        srv._github = GitHubClient(auth=auth, cache=None)
        await srv._github.start()

        try:
            result = await handle_call_tool(
                "create_issue",
                {"owner": "owner", "repo": "repo", "title": "Yeni Hata"},
            )
            data = json.loads(result[0].text)
            assert data["number"] == 99
            assert data["title"] == "Yeni Hata"
        finally:
            await srv._github.close()
            srv._github = None

    @respx.mock
    async def test_hata_yonetimi(self):
        """Hata fırlatan araç çağrısı hata metni döndürmeli, çökmemeli."""
        from mcp_github_advanced.auth import AuthManager, AuthSettings
        from mcp_github_advanced.github import GitHubClient
        import mcp_github_advanced.server as srv

        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(500, json={"message": "Internal Server Error"})
        )

        settings = AuthSettings(github_token="ghp_test")
        auth = AuthManager(settings)
        srv._github = GitHubClient(auth=auth, cache=None)
        await srv._github.start()

        try:
            result = await handle_call_tool(
                "get_repo_info", {"owner": "owner", "repo": "repo"}
            )
            assert len(result) == 1
            assert "Hata" in result[0].text
        finally:
            await srv._github.close()
            srv._github = None


# ══════════════════════════════════════════════════════════════════════
#  Araç Şema Doğrulama — inputSchema'ların doğruluğu
# ══════════════════════════════════════════════════════════════════════

class TestToolSchemas:
    def test_repo_araclari_owner_repo_zorunlu(self):
        """Repo araçları owner ve repo parametrelerini zorunlu kılmalı."""
        repo_tools = ["get_repo_info", "list_repo_files", "search_code"]
        for tool in TOOLS:
            if tool.name in repo_tools:
                assert "owner" in tool.inputSchema["required"]
                assert "repo" in tool.inputSchema["required"]

    def test_commit_araclari_owner_repo_zorunlu(self):
        """Commit araçları owner ve repo parametrelerini zorunlu kılmalı."""
        commit_tools = ["list_commits", "get_commit_diff", "get_contributor_stats"]
        for tool in TOOLS:
            if tool.name in commit_tools:
                assert "owner" in tool.inputSchema["required"]
                assert "repo" in tool.inputSchema["required"]

    def test_get_commit_diff_sha_zorunlu(self):
        """get_commit_diff aracı sha parametresini zorunlu kılmalı."""
        for tool in TOOLS:
            if tool.name == "get_commit_diff":
                assert "sha" in tool.inputSchema["required"]

    def test_create_pr_review_body_zorunlu(self):
        """create_pr_review aracı body ve pr_number zorunlu kılmalı."""
        for tool in TOOLS:
            if tool.name == "create_pr_review":
                assert "body" in tool.inputSchema["required"]
                assert "pr_number" in tool.inputSchema["required"]

    def test_create_issue_title_zorunlu(self):
        """create_issue aracı title parametresini zorunlu kılmalı."""
        for tool in TOOLS:
            if tool.name == "create_issue":
                assert "title" in tool.inputSchema["required"]

    def test_get_workflow_logs_run_id_zorunlu(self):
        """get_workflow_logs aracı run_id parametresini zorunlu kılmalı."""
        for tool in TOOLS:
            if tool.name == "get_workflow_logs":
                assert "run_id" in tool.inputSchema["required"]
