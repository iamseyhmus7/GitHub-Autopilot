"""github.py — GitHub REST v3 + GraphQL v4 async istemcisi.

Tüm istekler AGENTS.md gereği versiyonlu header'lar kullanır:
    Authorization: Bearer {token}
    Accept: application/vnd.github+json
    X-GitHub-Api-Version: 2022-11-28

Rate limit yönetimi: X-RateLimit-Remaining < 10 olduğunda
istemci sıfırlama penceresine kadar bekler.

Büyük diff ve loglar 8192 token'ı aşmamak için chunk'lanır.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mcp_github_advanced.auth import AuthManager, get_auth_headers
from mcp_github_advanced.cache import RedisCache

logger = logging.getLogger(__name__)

# ── Sabitler ──────────────────────────────────────────────────────────
GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"
MAX_OUTPUT_CHARS = 30_000  # ≈ 8192 token (~3.7 karakter/token)
REQUEST_TIMEOUT = 30.0


# ── Yardımcılar ──────────────────────────────────────────────────────
def _chunk_text(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Gemini 8192 token çıktı limitinin altında kalmak için metni keser."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n... [kesildi — çıktı 8192 token limitini aşıyor]"


class RateLimitError(Exception):
    """GitHub API rate limit'e ulaşıldığında fırlatılır (HTTP 429 / 403)."""


# ── GitHub İstemcisi ──────────────────────────────────────────────────
class GitHubClient:
    """Önbellekleme ve rate-limit yönetimi ile async GitHub REST + GraphQL istemcisi."""

    def __init__(
        self,
        auth: AuthManager,
        cache: Optional[RedisCache] = None,
    ) -> None:
        self.auth = auth
        self.cache = cache
        self._client: Optional[httpx.AsyncClient] = None

    # ── yaşam döngüsü ──
    async def start(self) -> None:
        """HTTP istemcisini başlatır ve Redis bağlantısını kurar."""
        self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        if self.cache:
            await self.cache.connect()

    async def close(self) -> None:
        """HTTP istemcisini ve Redis bağlantısını kapatır."""
        if self._client:
            await self._client.aclose()
        if self.cache:
            await self.cache.close()

    @property
    def headers(self) -> dict[str, str]:
        """Aktif token için kimlik doğrulama header'larını döndürür."""
        return self.auth.get_headers()

    # ── rate limit yönetimi ──
    async def _handle_rate_limit(self, resp: httpx.Response) -> None:
        """Rate limit kalan istek sayısı tehlikeli seviyedeyse bekler."""
        remaining = int(resp.headers.get("X-RateLimit-Remaining", 100))
        if remaining < 10:
            reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = reset_ts - time.time()
            if wait > 0:
                logger.warning(
                    "Rate limit düşük (%d kalan), %.1f sn bekleniyor", remaining, wait
                )
                await asyncio.sleep(wait)

    # ── düşük seviye HTTP ──
    @retry(
        retry=retry_if_exception_type((RateLimitError, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        """GitHub API'ye GET isteği gönderir. Retry ve rate-limit dahildir."""
        assert self._client is not None, "Önce start() çağrılmalı"
        resp = await self._client.get(url, headers=self.headers, params=params)
        await self._handle_rate_limit(resp)
        if resp.status_code in (429, 403) and "rate limit" in resp.text.lower():
            raise RateLimitError(resp.text)
        resp.raise_for_status()
        return resp

    @retry(
        retry=retry_if_exception_type((RateLimitError, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
    )
    async def _post(self, url: str, json_body: dict) -> httpx.Response:
        """GitHub API'ye POST isteği gönderir. Retry ve rate-limit dahildir."""
        assert self._client is not None, "Önce start() çağrılmalı"
        resp = await self._client.post(url, headers=self.headers, json=json_body)
        await self._handle_rate_limit(resp)
        if resp.status_code in (429, 403) and "rate limit" in resp.text.lower():
            raise RateLimitError(resp.text)
        resp.raise_for_status()
        return resp

    async def _graphql(self, query: str, variables: dict) -> dict:
        """GitHub GraphQL API'ye sorgu gönderir ve veriyi döndürür."""
        resp = await self._post(GITHUB_GRAPHQL, {"query": query, "variables": variables})
        data = resp.json()
        if "errors" in data:
            raise ValueError(f"GraphQL hataları: {data['errors']}")
        return data["data"]

    # ──────────────────────────────────────────────────────────────────
    #  📁 Repo Araçları
    # ──────────────────────────────────────────────────────────────────

    async def get_repo_info(self, owner: str, repo: str) -> dict:
        """GET /repos/{owner}/{repo} — repo meta verileri (yıldız, fork, dil vb.)."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "get_repo_info")
            if cached:
                return cached

        resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}")
        data = resp.json()
        result = {
            "name": data["name"],
            "full_name": data["full_name"],
            "description": data.get("description"),
            "language": data.get("language"),
            "stargazers_count": data.get("stargazers_count", 0),
            "forks_count": data.get("forks_count", 0),
            "open_issues_count": data.get("open_issues_count", 0),
            "size": data.get("size", 0),
            "default_branch": data.get("default_branch", "main"),
            "private": data.get("private", False),
            "html_url": data.get("html_url"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "topics": data.get("topics", []),
            "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
        }

        if self.cache:
            await self.cache.set(owner, repo, "get_repo_info", result)
        return result

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None,
    ) -> dict:
        """GET /repos/{owner}/{repo}/contents/{path} — dosya içeriği."""
        cache_extra = f"{path}:{ref or 'default'}"
        if self.cache:
            cached = await self.cache.get(owner, repo, "get_file_content", extra=cache_extra)
            if cached:
                return cached

        params: dict[str, str] = {}
        if ref:
            params["ref"] = ref

        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}", params=params
        )
        data = resp.json()

        import base64

        content = ""
        if data.get("encoding") == "base64" and data.get("content"):
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")

        result = {
            "name": data.get("name"),
            "path": data.get("path"),
            "size": data.get("size"),
            "sha": data.get("sha"),
            "content": _chunk_text(content),
        }

        if self.cache:
            await self.cache.set(owner, repo, "get_file_content", result, extra=cache_extra)
        return result

    async def list_repo_files(
        self, owner: str, repo: str, ref: Optional[str] = None,
    ) -> list[dict]:
        """GET /repos/{owner}/{repo}/git/trees/{ref}?recursive=1 — dizin ağacı."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "list_repo_files")
            if cached:
                return cached

        branch = ref or "HEAD"
        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
        )
        data = resp.json()
        tree = [
            {"path": item["path"], "type": item["type"], "size": item.get("size", 0)}
            for item in data.get("tree", [])
        ]

        if self.cache:
            await self.cache.set(owner, repo, "list_repo_files", tree)
        return tree

    async def search_code(
        self, owner: str, repo: str, query: str,
    ) -> list[dict]:
        """GET /search/code?q={query}+repo:{owner}/{repo} — kod araması."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "search_code", extra=query)
            if cached:
                return cached

        resp = await self._get(
            f"{GITHUB_API}/search/code",
            params={"q": f"{query} repo:{owner}/{repo}"},
        )
        data = resp.json()
        items = [
            {"name": i["name"], "path": i["path"], "html_url": i["html_url"]}
            for i in data.get("items", [])
        ]

        if self.cache:
            await self.cache.set(owner, repo, "search_code", items, extra=query)
        return items

    # ──────────────────────────────────────────────────────────────────
    #  📝 Commit Araçları
    # ──────────────────────────────────────────────────────────────────

    async def list_commits(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
        sha: Optional[str] = None,
    ) -> list[dict]:
        """GET /repos/{owner}/{repo}/commits — commit geçmişi."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "list_commits")
            if cached:
                return cached

        params: dict[str, Any] = {"per_page": per_page}
        if sha:
            params["sha"] = sha

        resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}/commits", params=params)
        commits = [
            {
                "sha": c["sha"][:7],
                "full_sha": c["sha"],
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            }
            for c in resp.json()
        ]

        if self.cache:
            await self.cache.set(owner, repo, "list_commits", commits)
        return commits

    async def get_commit_diff(self, owner: str, repo: str, sha: str) -> dict:
        """GET /repos/{owner}/{repo}/commits/{sha} — tek commit diff'i."""
        cache_extra = sha
        if self.cache:
            cached = await self.cache.get(owner, repo, "get_commit_diff", extra=cache_extra)
            if cached:
                return cached

        resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}")
        data = resp.json()

        files = []
        for f in data.get("files", []):
            files.append({
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "patch": _chunk_text(f.get("patch", ""), max_chars=5000),
            })

        result = {
            "sha": data["sha"],
            "message": data["commit"]["message"],
            "author": data["commit"]["author"]["name"],
            "date": data["commit"]["author"]["date"],
            "stats": data.get("stats", {}),
            "files": files,
        }

        if self.cache:
            await self.cache.set(owner, repo, "get_commit_diff", result, extra=cache_extra)
        return result

    async def get_contributor_stats(self, owner: str, repo: str) -> list[dict]:
        """Katkıda bulunan istatistikleri — REST API kullanır."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "get_contributor_stats")
            if cached:
                return cached

        # REST: /repos/{owner}/{repo}/contributors
        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
            params={"per_page": 30},
        )
        contributors = [
            {
                "login": c["login"],
                "contributions": c["contributions"],
                "avatar_url": c["avatar_url"],
                "html_url": c["html_url"],
            }
            for c in resp.json()
        ]

        if self.cache:
            await self.cache.set(owner, repo, "get_contributor_stats", contributors)
        return contributors

    # ──────────────────────────────────────────────────────────────────
    #  🔀 PR Araçları
    # ──────────────────────────────────────────────────────────────────

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict]:
        """GET /repos/{owner}/{repo}/pulls — PR listesi."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "list_pull_requests", extra=state)
            if cached:
                return cached

        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page},
        )
        prs = [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "user": pr["user"]["login"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "html_url": pr["html_url"],
                "labels": [lb["name"] for lb in pr.get("labels", [])],
            }
            for pr in resp.json()
        ]

        if self.cache:
            await self.cache.set(owner, repo, "list_pull_requests", prs, extra=state)
        return prs

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> dict:
        """GET /repos/{owner}/{repo}/pulls/{pr_number} — PR diff'i."""
        cache_extra = str(pr_number)
        if self.cache:
            cached = await self.cache.get(owner, repo, "get_pr_diff", extra=cache_extra)
            if cached:
                return cached

        # PR meta verilerini al
        resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}")
        pr_data = resp.json()

        # PR dosyalarını al (diff)
        files_resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        )
        files = [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "patch": _chunk_text(f.get("patch", ""), max_chars=5000),
            }
            for f in files_resp.json()
        ]

        result = {
            "number": pr_data["number"],
            "title": pr_data["title"],
            "state": pr_data["state"],
            "user": pr_data["user"]["login"],
            "body": _chunk_text(pr_data.get("body") or ""),
            "files": files,
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "changed_files": pr_data.get("changed_files", 0),
        }

        if self.cache:
            await self.cache.set(owner, repo, "get_pr_diff", result, extra=cache_extra)
        return result

    async def create_pr_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
    ) -> dict:
        """POST /repos/{owner}/{repo}/pulls/{pr_number}/reviews — review oluşturur."""
        resp = await self._post(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            {"body": body, "event": event},
        )
        data = resp.json()
        return {
            "id": data["id"],
            "state": data["state"],
            "html_url": data.get("html_url"),
            "submitted_at": data.get("submitted_at"),
        }

    # ──────────────────────────────────────────────────────────────────
    #  🐛 Issue Araçları
    # ──────────────────────────────────────────────────────────────────

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict]:
        """GET /repos/{owner}/{repo}/issues — issue listesi."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "list_issues", extra=state)
            if cached:
                return cached

        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": per_page},
        )
        issues = [
            {
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "user": i["user"]["login"],
                "labels": [lb["name"] for lb in i.get("labels", [])],
                "created_at": i["created_at"],
                "html_url": i["html_url"],
            }
            for i in resp.json()
            if "pull_request" not in i  # PR'ları hariç tut
        ]

        if self.cache:
            await self.cache.set(owner, repo, "list_issues", issues, extra=state)
        return issues

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[list[str]] = None,
        assignees: Optional[list[str]] = None,
    ) -> dict:
        """POST /repos/{owner}/{repo}/issues — yeni issue oluşturur."""
        payload: dict[str, Any] = {"title": title}
        if body:
            payload["body"] = body
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees

        resp = await self._post(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues", payload
        )
        data = resp.json()
        return {
            "number": data["number"],
            "title": data["title"],
            "html_url": data["html_url"],
            "state": data["state"],
        }

    # ──────────────────────────────────────────────────────────────────
    #  ⚙️ Actions / CI Araçları
    # ──────────────────────────────────────────────────────────────────

    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        per_page: int = 10,
    ) -> list[dict]:
        """GET /repos/{owner}/{repo}/actions/runs — iş akışı çalıştırmaları."""
        if self.cache:
            cached = await self.cache.get(owner, repo, "get_workflow_runs")
            if cached:
                return cached

        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs",
            params={"per_page": per_page},
        )
        data = resp.json()
        runs = [
            {
                "id": r["id"],
                "name": r.get("name"),
                "status": r["status"],
                "conclusion": r.get("conclusion"),
                "event": r["event"],
                "created_at": r["created_at"],
                "html_url": r["html_url"],
                "head_branch": r.get("head_branch"),
            }
            for r in data.get("workflow_runs", [])
        ]

        if self.cache:
            await self.cache.set(owner, repo, "get_workflow_runs", runs)
        return runs

    async def get_workflow_logs(
        self, owner: str, repo: str, run_id: int,
    ) -> dict:
        """GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs — iş logları."""
        cache_extra = str(run_id)
        if self.cache:
            cached = await self.cache.get(owner, repo, "get_workflow_logs", extra=cache_extra)
            if cached:
                return cached

        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        )
        data = resp.json()

        jobs = []
        for job in data.get("jobs", []):
            steps = [
                {
                    "name": s["name"],
                    "status": s["status"],
                    "conclusion": s.get("conclusion"),
                }
                for s in job.get("steps", [])
            ]
            jobs.append({
                "id": job["id"],
                "name": job["name"],
                "status": job["status"],
                "conclusion": job.get("conclusion"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "steps": steps,
            })

        result = {
            "run_id": run_id,
            "total_jobs": len(jobs),
            "jobs": jobs,
        }

        if self.cache:
            await self.cache.set(owner, repo, "get_workflow_logs", result, extra=cache_extra)
        return result
