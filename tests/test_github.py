"""test_github.py — GitHubClient testleri.

Tüm testler respx mock'ları kullanır — gerçek GitHub API isteği yapılmaz.
Test senaryoları: başarılı, 404 bulunamadı, 401 yetkisiz.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_github_advanced.github import GitHubClient, _chunk_text


# ══════════════════════════════════════════════════════════════════════
#  Metin kesme yardımcısı
# ══════════════════════════════════════════════════════════════════════

class TestChunkText:
    def test_kisa_metin_degismez(self):
        """Kısa metin olduğu gibi kalmalı."""
        text = "Merhaba, dünya!"
        assert _chunk_text(text) == text

    def test_uzun_metin_kesilir(self):
        """Uzun metin belirtilen limitte kesilmeli."""
        text = "x" * 50_000
        result = _chunk_text(text, max_chars=100)
        assert len(result) < 200
        assert "kesildi" in result


# ══════════════════════════════════════════════════════════════════════
#  get_repo_info — Repo bilgisi
# ══════════════════════════════════════════════════════════════════════

class TestGetRepoInfo:
    @respx.mock
    async def test_basarili(self, github_client: GitHubClient):
        """Başarılı repo bilgisi getirme testi."""
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={
                "name": "repo",
                "full_name": "owner/repo",
                "description": "Test",
                "language": "Python",
                "stargazers_count": 42,
                "forks_count": 5,
                "open_issues_count": 3,
                "size": 512,
                "default_branch": "main",
                "private": False,
                "html_url": "https://github.com/owner/repo",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-06-01T00:00:00Z",
                "topics": ["test"],
                "license": {"spdx_id": "MIT"},
            })
        )
        result = await github_client.get_repo_info("owner", "repo")
        assert result["name"] == "repo"
        assert result["stargazers_count"] == 42
        assert result["language"] == "Python"
        assert result["license"] == "MIT"

    @respx.mock
    async def test_404_bulunamadi(self, github_client: GitHubClient):
        """Repo bulunamadığında 404 hatası fırlatmalı."""
        respx.get("https://api.github.com/repos/owner/notfound").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await github_client.get_repo_info("owner", "notfound")

    @respx.mock
    async def test_401_yetkisiz(self, github_client: GitHubClient):
        """Geçersiz token ile 401 hatası fırlatmalı."""
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(401, json={"message": "Bad credentials"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await github_client.get_repo_info("owner", "repo")


# ══════════════════════════════════════════════════════════════════════
#  list_commits — Commit listesi
# ══════════════════════════════════════════════════════════════════════

class TestListCommits:
    @respx.mock
    async def test_basarili(self, github_client: GitHubClient):
        """Başarılı commit listesi getirme testi."""
        respx.get("https://api.github.com/repos/owner/repo/commits").mock(
            return_value=httpx.Response(200, json=[
                {
                    "sha": "abc1234567890",
                    "commit": {
                        "message": "feat: özellik eklendi",
                        "author": {"name": "Geliştirici", "date": "2024-01-01T00:00:00Z"},
                    },
                },
            ])
        )
        commits = await github_client.list_commits("owner", "repo")
        assert len(commits) == 1
        assert commits[0]["sha"] == "abc1234"
        assert commits[0]["message"] == "feat: özellik eklendi"


# ══════════════════════════════════════════════════════════════════════
#  get_commit_diff — Commit diff'i
# ══════════════════════════════════════════════════════════════════════

class TestGetCommitDiff:
    @respx.mock
    async def test_basarili(self, github_client: GitHubClient):
        """Başarılı commit diff getirme testi."""
        respx.get("https://api.github.com/repos/owner/repo/commits/abc123").mock(
            return_value=httpx.Response(200, json={
                "sha": "abc123",
                "commit": {
                    "message": "fix: yama",
                    "author": {"name": "Geliştirici", "date": "2024-01-01T00:00:00Z"},
                },
                "stats": {"total": 10, "additions": 7, "deletions": 3},
                "files": [
                    {
                        "filename": "src/main.py",
                        "status": "modified",
                        "additions": 7,
                        "deletions": 3,
                        "patch": "@@ -1 +1 @@\n-eski\n+yeni",
                    }
                ],
            })
        )
        result = await github_client.get_commit_diff("owner", "repo", "abc123")
        assert result["sha"] == "abc123"
        assert len(result["files"]) == 1
        assert result["files"][0]["filename"] == "src/main.py"


# ══════════════════════════════════════════════════════════════════════
#  list_pull_requests — PR listesi
# ══════════════════════════════════════════════════════════════════════

class TestListPullRequests:
    @respx.mock
    async def test_basarili(self, github_client: GitHubClient):
        """Başarılı PR listesi getirme testi."""
        respx.get("https://api.github.com/repos/owner/repo/pulls").mock(
            return_value=httpx.Response(200, json=[
                {
                    "number": 42,
                    "title": "Özellik eklendi",
                    "state": "open",
                    "user": {"login": "gelistirici"},
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "html_url": "https://github.com/owner/repo/pull/42",
                    "labels": [{"name": "enhancement"}],
                },
            ])
        )
        prs = await github_client.list_pull_requests("owner", "repo")
        assert len(prs) == 1
        assert prs[0]["number"] == 42
        assert prs[0]["labels"] == ["enhancement"]


# ══════════════════════════════════════════════════════════════════════
#  list_issues — Issue listesi
# ══════════════════════════════════════════════════════════════════════

class TestListIssues:
    @respx.mock
    async def test_basarili(self, github_client: GitHubClient):
        """Başarılı issue listesi getirme testi."""
        respx.get("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(200, json=[
                {
                    "number": 1,
                    "title": "Hata raporu",
                    "state": "open",
                    "user": {"login": "raporci"},
                    "labels": [{"name": "bug"}],
                    "created_at": "2024-01-01T00:00:00Z",
                    "html_url": "https://github.com/owner/repo/issues/1",
                },
            ])
        )
        issues = await github_client.list_issues("owner", "repo")
        assert len(issues) == 1
        assert issues[0]["title"] == "Hata raporu"
        assert "bug" in issues[0]["labels"]

    @respx.mock
    async def test_pr_lari_haric_tutar(self, github_client: GitHubClient):
        """Issues endpoint'i PR'ları da döner — bunlar filtrelenmeli."""
        respx.get("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(200, json=[
                {
                    "number": 1,
                    "title": "Issue",
                    "state": "open",
                    "user": {"login": "dev"},
                    "labels": [],
                    "created_at": "2024-01-01T00:00:00Z",
                    "html_url": "https://github.com/owner/repo/issues/1",
                },
                {
                    "number": 2,
                    "title": "PR",
                    "state": "open",
                    "user": {"login": "dev"},
                    "labels": [],
                    "created_at": "2024-01-01T00:00:00Z",
                    "html_url": "https://github.com/owner/repo/pull/2",
                    "pull_request": {"url": "..."},
                },
            ])
        )
        issues = await github_client.list_issues("owner", "repo")
        assert len(issues) == 1
        assert issues[0]["number"] == 1


# ══════════════════════════════════════════════════════════════════════
#  get_workflow_runs — İş akışı çalıştırmaları
# ══════════════════════════════════════════════════════════════════════

class TestGetWorkflowRuns:
    @respx.mock
    async def test_basarili(self, github_client: GitHubClient):
        """Başarılı iş akışı çalıştırma listesi testi."""
        respx.get("https://api.github.com/repos/owner/repo/actions/runs").mock(
            return_value=httpx.Response(200, json={
                "total_count": 1,
                "workflow_runs": [
                    {
                        "id": 99,
                        "name": "CI",
                        "status": "completed",
                        "conclusion": "success",
                        "event": "push",
                        "created_at": "2024-01-01T00:00:00Z",
                        "html_url": "https://github.com/owner/repo/actions/runs/99",
                        "head_branch": "main",
                    },
                ],
            })
        )
        runs = await github_client.get_workflow_runs("owner", "repo")
        assert len(runs) == 1
        assert runs[0]["conclusion"] == "success"


# ══════════════════════════════════════════════════════════════════════
#  get_contributor_stats — Katkıda bulunan istatistikleri
# ══════════════════════════════════════════════════════════════════════

class TestGetContributorStats:
    @respx.mock
    async def test_basarili(self, github_client: GitHubClient):
        """Başarılı katkıda bulunan istatistikleri testi."""
        respx.get("https://api.github.com/repos/owner/repo/contributors").mock(
            return_value=httpx.Response(200, json=[
                {
                    "login": "dev1",
                    "contributions": 150,
                    "avatar_url": "https://avatars.githubusercontent.com/u/1",
                    "html_url": "https://github.com/dev1",
                },
                {
                    "login": "dev2",
                    "contributions": 50,
                    "avatar_url": "https://avatars.githubusercontent.com/u/2",
                    "html_url": "https://github.com/dev2",
                },
            ])
        )
        stats = await github_client.get_contributor_stats("owner", "repo")
        assert len(stats) == 2
        assert stats[0]["login"] == "dev1"
        assert stats[0]["contributions"] == 150
