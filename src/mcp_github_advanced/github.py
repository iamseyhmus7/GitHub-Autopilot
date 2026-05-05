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
import re
import time
from collections import Counter, defaultdict
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

    async def _try_read_file(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None,
    ) -> Optional[str]:
        """Dosya içeriğini okumayı dener, dosya yoksa (404) None döner."""
        try:
            result = await self.get_file_content(owner, repo, path, ref)
            return result.get("content", "")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ──────────────────────────────────────────────────────────────────
    #  📁 Repo Araçları
    # ──────────────────────────────────────────────────────────────────

    async def list_user_repos(
        self, username: str, per_page: int = 100, sort: str = "updated"
    ) -> list[dict]:
        """GET /users/{username}/repos — kullanıcının tüm genel repolarını listeler."""
        if self.cache:
            cached = await self.cache.get(username, "repos", "list_user_repos", extra=sort)
            if cached:
                return cached

        resp = await self._get(
            f"{GITHUB_API}/users/{username}/repos",
            params={"per_page": per_page, "sort": sort},
        )
        repos = [
            {
                "name": r["name"],
                "description": r.get("description"),
                "stargazers_count": r.get("stargazers_count", 0),
                "fork": r.get("fork", False),
                "language": r.get("language"),
                "updated_at": r.get("updated_at"),
            }
            for r in resp.json()
        ]

        if self.cache:
            await self.cache.set(username, "repos", "list_user_repos", repos, extra=sort)
        return repos

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

    # ──────────────────────────────────────────────────────────────────
    #  🧠 Derin Analiz Araçları (Deep Repository Intelligence)
    # ──────────────────────────────────────────────────────────────────

    async def analyze_architecture(self, owner: str, repo: str) -> dict:
        """Projenin mimari yapısını derinlemesine analiz eder:
        katman tespiti, desen tanıma, framework algılama, Mermaid diyagramı."""

        if self.cache:
            cached = await self.cache.get(owner, repo, "analyze_architecture")
            if cached:
                return cached

        tree = await self.list_repo_files(owner, repo)
        repo_info = await self.get_repo_info(owner, repo)

        source_exts = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.rb', '.cs'}
        dir_stats: dict[str, dict] = {}
        config_files: list[str] = []
        test_files: list[str] = []
        all_files: list[str] = []

        known_configs = {
            'package.json', 'pyproject.toml', 'Cargo.toml', 'pom.xml', 'build.gradle',
            'go.mod', 'Gemfile', 'requirements.txt', 'setup.py', 'Pipfile',
            'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
            'Makefile', 'tsconfig.json', 'webpack.config.js', 'vite.config.ts',
            'next.config.js', 'next.config.mjs', '.env.example', 'smithery.yaml',
        }

        for item in tree:
            if item['type'] != 'blob':
                continue
            path = item['path']
            all_files.append(path)
            basename = path.split('/')[-1]

            if basename in known_configs:
                config_files.append(path)
            if any(x in path.lower() for x in ['/test', '/spec', '/__tests__', '_test.', '.test.', '.spec.']):
                test_files.append(path)

            parts = path.split('/')
            if len(parts) > 1:
                top = parts[0]
                if top not in dir_stats:
                    dir_stats[top] = {'total': 0, 'source': 0}
                dir_stats[top]['total'] += 1
                ext = ('.' + basename.rsplit('.', 1)[-1]) if '.' in basename else ''
                if ext in source_exts:
                    dir_stats[top]['source'] += 1

        # ── Katman tespiti ──
        layer_map = {
            'API / Routes': ['api', 'routes', 'endpoints', 'controllers', 'views', 'handlers'],
            'Business Logic': ['services', 'usecases', 'domain', 'core', 'business'],
            'Data / Models': ['models', 'entities', 'schemas', 'repositories', 'db', 'database'],
            'AI / Agents': ['agents', 'llm', 'ai', 'chains', 'prompts'],
            'Infrastructure': ['infra', 'config', 'utils', 'helpers', 'lib', 'common'],
            'Frontend': ['frontend', 'client', 'ui', 'components', 'pages', 'public'],
            'Tests': ['tests', 'test', '__tests__', 'spec'],
        }
        layers = []
        for layer_name, keywords in layer_map.items():
            for dirname, stats in dir_stats.items():
                if dirname.lower() in keywords:
                    layers.append({
                        'name': layer_name, 'path': f'{dirname}/',
                        'files': stats['total'], 'source_files': stats['source'],
                    })

        # ── Framework tespiti ──
        framework_parts = []
        configs_read: dict[str, str] = {}
        for cfg in ['package.json', 'pyproject.toml', 'go.mod', 'Cargo.toml', 'requirements.txt']:
            if cfg in config_files or any(f.endswith(cfg) for f in config_files):
                content = await self._try_read_file(owner, repo, cfg)
                if content:
                    configs_read[cfg] = content

        py_cfg = configs_read.get('pyproject.toml', '') + configs_read.get('requirements.txt', '')
        for fw, kw in [('FastAPI', 'fastapi'), ('Django', 'django'), ('Flask', 'flask'),
                       ('LangChain/LangGraph', 'langgraph'), ('MCP', 'fastmcp')]:
            if kw in py_cfg.lower():
                framework_parts.append(fw)

        js_cfg = configs_read.get('package.json', '')
        for fw, kw in [('Next.js', '"next"'), ('React', '"react"'), ('Vue.js', '"vue"'),
                       ('Express', '"express"'), ('Vite', '"vite"')]:
            if kw in js_cfg.lower():
                framework_parts.append(fw)

        framework = ' + '.join(dict.fromkeys(framework_parts)) or "Custom / Unknown"

        # ── Mimari desen tespiti ──
        dn = {d.lower() for d in dir_stats}
        pattern, evidence = "Monolith", []
        if {'models', 'views', 'controllers'} & dn:
            pattern, evidence = "MVC", ["models/views/controllers dizin yapısı"]
        if {'domain', 'usecases'} & dn or {'core', 'adapters', 'ports'} & dn:
            pattern, evidence = "Clean Architecture", ["domain/usecases katmanları"]
        if len(layers) >= 3:
            pattern, evidence = "Layered Architecture", ["Çoklu katman ayrımı mevcut"]
        compose = await self._try_read_file(owner, repo, 'docker-compose.yml')
        if compose and compose.count('build:') > 2:
            pattern, evidence = "Microservices", ["docker-compose'da çoklu servis"]

        # ── Test yapısı ──
        test_fw = "Unknown"
        if 'pytest' in py_cfg.lower():
            test_fw = "pytest"
        elif 'jest' in js_cfg.lower():
            test_fw = "Jest"
        test_dir = next((d for d in dir_stats if d.lower() in ('tests', 'test', '__tests__')), None)

        # ── Mermaid diyagramı ──
        ml = ['graph TD']
        nmap = {}
        for i, layer in enumerate(layers):
            nid = f'L{i}'
            ml.append(f'    {nid}["{layer["name"]} — {layer["path"]} ({layer["files"]} dosya)"]')
            nmap[layer['name']] = nid
        edges = [('API / Routes', 'Business Logic'), ('API / Routes', 'AI / Agents'),
                 ('Business Logic', 'Data / Models'), ('AI / Agents', 'Infrastructure'),
                 ('Frontend', 'API / Routes')]
        for a, b in edges:
            if a in nmap and b in nmap:
                ml.append(f'    {nmap[a]} --> {nmap[b]}')

        result = {
            'pattern': pattern, 'pattern_evidence': evidence,
            'framework': framework,
            'primary_language': repo_info.get('language', 'Unknown'),
            'layers': layers, 'config_files': config_files,
            'test_structure': {
                'has_tests': len(test_files) > 0, 'test_count': len(test_files),
                'framework': test_fw, 'test_dir': test_dir,
            },
            'directory_summary': {
                n: {'total': s['total'], 'source': s['source']}
                for n, s in sorted(dir_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:15]
            },
            'mermaid_diagram': '\n'.join(ml),
            'key_observations': [
                f"Toplam {len(all_files)} dosya, {len(dir_stats)} üst dizin",
                f"Framework: {framework}", f"Mimari desen: {pattern}",
                f"Test dosyası: {len(test_files)}, Konfig dosyası: {len(config_files)}",
            ],
        }
        if self.cache:
            await self.cache.set(owner, repo, "analyze_architecture", result)
        return result

    async def analyze_dependencies(self, owner: str, repo: str) -> dict:
        """Teknoloji yığını ve modüller arası bağımlılık grafiği çıkarır.
        Manifest dosyalarını parse eder, import ifadelerinden iç bağımlılık haritası oluşturur."""

        if self.cache:
            cached = await self.cache.get(owner, repo, "analyze_dependencies")
            if cached:
                return cached

        tree = await self.list_repo_files(owner, repo)
        repo_info = await self.get_repo_info(owner, repo)

        # ── Dil dağılımı (uzantı bazlı) ──
        ext_map = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'TypeScript',
            '.jsx': 'JavaScript', '.java': 'Java', '.go': 'Go', '.rs': 'Rust',
            '.rb': 'Ruby', '.cs': 'C#', '.cpp': 'C++', '.c': 'C',
            '.css': 'CSS', '.html': 'HTML', '.scss': 'SCSS',
        }
        lang_counts: dict[str, int] = defaultdict(int)
        source_files: list[dict] = []

        for item in tree:
            if item['type'] != 'blob':
                continue
            path = item['path']
            basename = path.split('/')[-1]
            ext = ('.' + basename.rsplit('.', 1)[-1]) if '.' in basename else ''
            lang = ext_map.get(ext)
            if lang:
                lang_counts[lang] += 1
                source_files.append({'path': path, 'size': item.get('size', 0), 'lang': lang})

        total_source = sum(lang_counts.values()) or 1
        languages = {k: round(v / total_source * 100) for k, v in
                     sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)}

        # ── Manifest dosyalarını bul ve oku ──
        manifest_map = {
            'pyproject.toml': 'Python', 'requirements.txt': 'Python', 'setup.py': 'Python',
            'Pipfile': 'Python', 'package.json': 'JavaScript/TypeScript',
            'go.mod': 'Go', 'Cargo.toml': 'Rust', 'Gemfile': 'Ruby',
            'pom.xml': 'Java', 'build.gradle': 'Java',
        }
        all_paths = {item['path'] for item in tree if item['type'] == 'blob'}
        manifests_found = []
        key_deps: list[dict] = []

        for mf, lang in manifest_map.items():
            if mf not in all_paths:
                continue
            content = await self._try_read_file(owner, repo, mf)
            if not content:
                continue
            manifests_found.append({'file': mf, 'language': lang})

            # pyproject.toml bağımlılıkları
            if mf == 'pyproject.toml':
                for m in re.finditer(r'"([a-zA-Z0-9_-]+)(?:\[.*?\])?([><=!~]+[^"]*)"', content):
                    name, ver = m.group(1), m.group(2)
                    cat = 'dev' if 'dev' in content[max(0, m.start()-100):m.start()].lower() else 'core'
                    key_deps.append({'name': name, 'version': ver.strip(), 'category': cat})

            # requirements.txt
            elif mf == 'requirements.txt':
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = re.split(r'[><=!~]', line, maxsplit=1)
                        name = parts[0].strip()
                        ver = line[len(name):].strip() if len(parts) > 1 else ''
                        key_deps.append({'name': name, 'version': ver, 'category': 'core'})

            # package.json
            elif mf == 'package.json':
                for section, cat in [('dependencies', 'core'), ('devDependencies', 'dev')]:
                    for m in re.finditer(rf'"{section}"\s*:\s*\{{([^}}]*)\}}', content, re.DOTALL):
                        block = m.group(1)
                        for dep in re.finditer(r'"([^"]+)"\s*:\s*"([^"]*)"', block):
                            key_deps.append({'name': dep.group(1), 'version': dep.group(2), 'category': cat})

        # ── İç modül bağımlılık grafiği (en büyük 15 kaynak dosya) ──
        top_files = sorted(source_files, key=lambda x: x['size'], reverse=True)[:15]
        internal_graph: dict[str, list[str]] = {}

        for sf in top_files:
            content = await self._try_read_file(owner, repo, sf['path'])
            if not content:
                continue
            imports = []
            # Python importları
            if sf['lang'] == 'Python':
                for m in re.finditer(r'(?:from|import)\s+([\w.]+)', content):
                    imp = m.group(1)
                    if not imp.startswith(('os', 'sys', 'json', 'time', 'typing', 're', 'asyncio',
                                           'logging', 'pathlib', 'collections', 'dataclasses')):
                        imports.append(imp)
            # JS/TS importları
            elif sf['lang'] in ('JavaScript', 'TypeScript'):
                for m in re.finditer(r"(?:import|require)\s*\(?['\"]([./][^'\"]+)['\"]", content):
                    imports.append(m.group(1))

            if imports:
                internal_graph[sf['path']] = list(dict.fromkeys(imports))[:10]

        # ── Altyapı tespiti ──
        infra = []
        if any('Dockerfile' in p for p in all_paths):
            infra.append('Docker')
        if any('.github/workflows' in p for p in all_paths):
            infra.append('GitHub Actions')
        if any('redis' in d.get('name', '').lower() for d in key_deps):
            infra.append('Redis')
        if any('postgres' in d.get('name', '').lower() or 'sqlalchemy' in d.get('name', '').lower()
               for d in key_deps):
            infra.append('PostgreSQL/SQL')

        # ── Mermaid diyagramı ──
        ml = ['graph LR']
        shown = set()
        for src, deps in list(internal_graph.items())[:8]:
            src_short = src.split('/')[-1].replace('.', '_')
            for dep in deps[:5]:
                dep_short = dep.split('.')[-1].replace('/', '_').replace('.', '_')
                edge = f'{src_short}_{dep_short}'
                if edge not in shown:
                    ml.append(f'    {src_short}["{src.split("/")[-1]}"] --> {dep_short}["{dep.split(".")[-1]}"]')
                    shown.add(edge)

        result = {
            'primary_language': repo_info.get('language', 'Unknown'),
            'languages': languages,
            'dependency_manifests': manifests_found,
            'key_dependencies': key_deps[:30],
            'internal_module_graph': internal_graph,
            'infrastructure': infra,
            'mermaid_diagram': '\n'.join(ml),
        }
        if self.cache:
            await self.cache.set(owner, repo, "analyze_dependencies", result)
        return result

    async def detect_entry_points(self, owner: str, repo: str) -> dict:
        """Projenin giriş noktalarını tespit eder:
        CLI komutları, API rotaları, main dosyaları, Docker CMD, CI/CD tetikleyicileri."""

        if self.cache:
            cached = await self.cache.get(owner, repo, "detect_entry_points")
            if cached:
                return cached

        tree = await self.list_repo_files(owner, repo)
        all_paths = [item['path'] for item in tree if item['type'] == 'blob']

        cli_entry_points: list[dict] = []
        api_routes: list[dict] = []
        main_files: list[dict] = []
        docker_commands: list[str] = []
        ci_triggers: list[str] = []

        # ── pyproject.toml → console_scripts ──
        pyproject = await self._try_read_file(owner, repo, 'pyproject.toml')
        if pyproject:
            for m in re.finditer(r'(\S+)\s*=\s*"([^"]+)"', pyproject):
                if ':' in m.group(2) and ('scripts' in pyproject[max(0, m.start()-200):m.start()].lower()):
                    cli_entry_points.append({
                        'command': m.group(1), 'target': m.group(2), 'source': 'pyproject.toml',
                    })

        # ── package.json → scripts, bin, main ──
        pkg = await self._try_read_file(owner, repo, 'package.json')
        if pkg:
            for m in re.finditer(r'"(bin|main|module)"\s*:\s*"([^"]*)"', pkg):
                cli_entry_points.append({
                    'command': m.group(1), 'target': m.group(2), 'source': 'package.json',
                })
            scripts_match = re.search(r'"scripts"\s*:\s*\{([^}]*)\}', pkg, re.DOTALL)
            if scripts_match:
                for m in re.finditer(r'"([^"]+)"\s*:\s*"([^"]*)"', scripts_match.group(1)):
                    cli_entry_points.append({
                        'command': f'npm run {m.group(1)}', 'target': m.group(2), 'source': 'package.json',
                    })

        # ── Main / entry dosyalarını bul ──
        entry_patterns = [
            'main.py', 'app.py', 'server.py', 'cli.py', '__main__.py', 'manage.py', 'wsgi.py',
            'index.ts', 'index.js', 'main.ts', 'main.js', 'app.ts', 'app.js', 'server.ts', 'server.js',
        ]
        for path in all_paths:
            basename = path.split('/')[-1]
            if basename in entry_patterns:
                ftype = 'CLI runner' if 'cli' in basename or 'main' in basename else \
                        'Web server' if 'server' in basename or 'app' in basename else \
                        'Module entry' if '__main__' in basename else 'Entry point'
                main_files.append({'path': path, 'type': ftype})

        # ── API rotalarını tespit et (en fazla 5 dosya oku) ──
        route_files = [p for p in all_paths if any(kw in p.lower() for kw in
                       ['routes', 'router', 'api/', 'endpoints', 'views', 'server.py', 'app.py', 'main.py'])]
        for rf in route_files[:5]:
            content = await self._try_read_file(owner, repo, rf)
            if not content:
                continue
            # FastAPI / Flask rotaları
            for m in re.finditer(r'@\w+\.(get|post|put|delete|patch)\(["\']([^"\']+)', content):
                api_routes.append({
                    'method': m.group(1).upper(), 'path': m.group(2), 'file': rf,
                })
            # Express.js rotaları
            for m in re.finditer(r'\.(get|post|put|delete|patch)\(["\']([^"\']+)', content):
                if m.group(2).startswith('/'):
                    api_routes.append({
                        'method': m.group(1).upper(), 'path': m.group(2), 'file': rf,
                    })

        # ── Dockerfile → CMD / ENTRYPOINT ──
        dockerfile = await self._try_read_file(owner, repo, 'Dockerfile')
        if dockerfile:
            for m in re.finditer(r'(?:CMD|ENTRYPOINT)\s+(.+)', dockerfile):
                docker_commands.append(m.group(1).strip())

        # ── GitHub Actions → tetikleyiciler ──
        wf_files = [p for p in all_paths if p.startswith('.github/workflows/') and p.endswith(('.yml', '.yaml'))]
        for wf in wf_files[:3]:
            content = await self._try_read_file(owner, repo, wf)
            if content:
                for m in re.finditer(r'on:\s*\n((?:\s+\w+.*\n)*)', content):
                    triggers = re.findall(r'(\w+):', m.group(1))
                    ci_triggers.extend(triggers)

        result = {
            'cli_entry_points': cli_entry_points,
            'api_routes': api_routes[:20],
            'main_files': main_files,
            'docker_commands': docker_commands,
            'ci_cd_triggers': list(dict.fromkeys(ci_triggers)),
            'total_entry_points': len(cli_entry_points) + len(main_files),
        }
        if self.cache:
            await self.cache.set(owner, repo, "detect_entry_points", result)
        return result

    async def analyze_codebase_complexity(self, owner: str, repo: str) -> dict:
        """Kod tabanının karmaşıklığını analiz eder:
        kritik dosyalar, tasarım desenleri, hotspot dizinler, karmaşıklık skoru."""

        if self.cache:
            cached = await self.cache.get(owner, repo, "analyze_codebase_complexity")
            if cached:
                return cached

        tree = await self.list_repo_files(owner, repo)

        source_exts = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.rb', '.cs'}
        source_files: list[dict] = []
        dir_file_count: dict[str, int] = defaultdict(int)
        total_files = 0
        max_depth = 0

        for item in tree:
            if item['type'] != 'blob':
                continue
            total_files += 1
            path = item['path']
            basename = path.split('/')[-1]
            ext = ('.' + basename.rsplit('.', 1)[-1]) if '.' in basename else ''
            depth = path.count('/')
            max_depth = max(max_depth, depth)

            if ext in source_exts:
                source_files.append({
                    'path': path, 'size': item.get('size', 0),
                    'estimated_lines': item.get('size', 0) // 35,
                })
            parts = path.split('/')
            if len(parts) > 1:
                dir_file_count['/'.join(parts[:-1])] += 1

        # ── En büyük dosyalar ──
        largest = sorted(source_files, key=lambda x: x['size'], reverse=True)[:10]

        # ── Hotspot dizinler ──
        hotspots = [
            {'path': d, 'file_count': c, 'label': 'Yüksek yoğunluk — potansiyel karmaşıklık'}
            for d, c in sorted(dir_file_count.items(), key=lambda x: x[1], reverse=True)[:5]
            if c >= 3
        ]

        # ── Tasarım desenleri tespiti (en büyük 5 dosyayı oku) ──
        patterns_found: list[dict] = []
        data_flow: list[str] = []

        for sf in largest[:5]:
            content = await self._try_read_file(owner, repo, sf['path'])
            if not content:
                continue

            fname = sf['path'].split('/')[-1]

            # Decorator deseni
            if re.search(r'@\w+\.\w+\(', content):
                patterns_found.append({
                    'pattern': 'Decorator', 'evidence': f'{fname} içinde dekoratör kullanımı',
                    'file': sf['path'],
                })
            # Singleton deseni
            if re.search(r'_instance\s*[:=]|__new__\s*\(', content):
                patterns_found.append({
                    'pattern': 'Singleton', 'evidence': f'{fname} içinde singleton kalıbı',
                    'file': sf['path'],
                })
            # Factory deseni
            if re.search(r'def\s+create_|def\s+build_|Factory', content):
                patterns_found.append({
                    'pattern': 'Factory', 'evidence': f'{fname} içinde factory metodu',
                    'file': sf['path'],
                })
            # Strategy / Plugin deseni
            if re.search(r'def\s+\w+_node\s*\(|async\s+def\s+\w+_node\s*\(', content):
                patterns_found.append({
                    'pattern': 'Strategy/Plugin', 'evidence': f'{fname} içinde düğüm (node) tabanlı strateji',
                    'file': sf['path'],
                })
            # Observer / Event deseni
            if re.search(r'on_\w+|emit\(|addEventListener|\.subscribe\(', content):
                patterns_found.append({
                    'pattern': 'Observer/Event', 'evidence': f'{fname} içinde olay dinleyici',
                    'file': sf['path'],
                })

            # Veri akışı tespiti (import zincirleri)
            imports = re.findall(r'(?:from|import)\s+([\w.]+)', content)
            if imports:
                local_imports = [i for i in imports if not i.startswith(('os', 'sys', 'json', 'typing'))][:3]
                if local_imports:
                    flow = f"{fname} → {', '.join(local_imports)}"
                    data_flow.append(flow)

        # Desenleri tekilleştir
        unique_patterns = list({p['pattern']: p for p in patterns_found}.values())

        # ── Karmaşıklık skoru (1-10) ──
        score = min(10, round(
            (len(source_files) / 50) * 2 +      # Dosya sayısı etkisi
            (max_depth / 5) * 2 +                 # Derinlik etkisi
            (len(unique_patterns) / 3) * 2 +      # Desen çeşitliliği
            (largest[0]['size'] / 20000) * 2 if largest else 0 +  # En büyük dosya
            (len(hotspots) / 3) * 2               # Hotspot sayısı
        , 1))

        # ── Mermaid diyagramı ──
        ml = ['graph TD']
        for i, flow in enumerate(data_flow[:6]):
            parts = flow.split(' → ')
            if len(parts) == 2:
                src = parts[0].replace('.', '_')
                targets = parts[1].split(', ')
                for t in targets[:2]:
                    tgt = t.replace('.', '_')
                    ml.append(f'    {src}["{parts[0]}"] --> {tgt}["{t}"]')

        result = {
            'total_files': total_files,
            'total_source_files': len(source_files),
            'max_nesting_depth': max_depth,
            'largest_files': largest,
            'hotspot_directories': hotspots,
            'design_patterns': unique_patterns,
            'data_flow': data_flow,
            'complexity_score': score,
            'mermaid_diagram': '\n'.join(ml),
        }
        if self.cache:
            await self.cache.set(owner, repo, "analyze_codebase_complexity", result)
        return result

    async def analyze_commit_patterns(self, owner: str, repo: str) -> dict:
        """Commit geçmişini derinlemesine analiz eder:
        frekans, mesaj kalitesi, yazar dağılımı, orijinallik değerlendirmesi."""

        if self.cache:
            cached = await self.cache.get(owner, repo, "analyze_commit_patterns")
            if cached:
                return cached

        commits = await self.list_commits(owner, repo, per_page=100)
        contributors = await self.get_contributor_stats(owner, repo)

        if not commits:
            return {
                'total_commits_analyzed': 0,
                'development_pattern': 'Veri bulunamadı — repo boş veya erişilemez',
                'originality_assessment': 'Değerlendirilemedi',
            }

        # ── Zaman analizi ──
        from datetime import datetime
        dates = []
        for c in commits:
            try:
                dt = datetime.fromisoformat(c['date'].replace('Z', '+00:00'))
                dates.append(dt)
            except (ValueError, KeyError):
                pass

        days_of_week = Counter()
        hours = Counter()
        for dt in dates:
            days_of_week[dt.strftime('%A')] += 1
            hours[dt.hour] += 1

        span_days = 0
        avg_per_week = 0
        if len(dates) >= 2:
            span = max(dates) - min(dates)
            span_days = max(span.days, 1)
            avg_per_week = round(len(commits) / max(span_days / 7, 1), 1)

        most_active_day = days_of_week.most_common(1)[0][0] if days_of_week else 'N/A'

        # ── Burst tespiti (24 saat içinde 10+ commit varsa) ──
        burst_detected = False
        if len(dates) >= 2:
            sorted_dates = sorted(dates)
            for i in range(len(sorted_dates) - 1):
                window = [d for d in sorted_dates[i:] if (d - sorted_dates[i]).total_seconds() <= 86400]
                if len(window) >= 10:
                    burst_detected = True
                    break

        # ── Yazar analizi ──
        author_counts = Counter(c.get('author', 'Unknown') for c in commits)
        total = len(commits) or 1
        authors = [
            {'name': name, 'commits': count, 'percentage': round(count / total * 100)}
            for name, count in author_counts.most_common(10)
        ]

        # ── Mesaj kalitesi ──
        conv_prefixes = {'feat', 'fix', 'chore', 'docs', 'style', 'refactor', 'perf', 'test', 'ci', 'build'}
        categories: dict[str, int] = defaultdict(int)
        msg_lengths = []
        conventional_count = 0

        for c in commits:
            msg = c.get('message', '')
            msg_lengths.append(len(msg))
            first_word = msg.split(':')[0].split('(')[0].strip().lower() if ':' in msg else ''
            if first_word in conv_prefixes:
                conventional_count += 1
                categories[first_word] += 1
            else:
                categories['other'] += 1

        conv_pct = round(conventional_count / total * 100)
        avg_msg_len = round(sum(msg_lengths) / total) if msg_lengths else 0

        # ── Dosya churn analizi (son 5 commit'in diff'lerini örnekle) ──
        file_changes: dict[str, int] = Counter()
        sample_commits = commits[:5]
        for sc in sample_commits:
            try:
                diff = await self.get_commit_diff(owner, repo, sc.get('full_sha', sc.get('sha', '')))
                for f in diff.get('files', []):
                    file_changes[f['filename']] += 1
            except Exception:
                pass

        file_churn = [
            {'path': path, 'change_count': count,
             'label': 'Yüksek churn — potansiyel kararsızlık' if count >= 3 else 'Normal'}
            for path, count in file_changes.most_common(10)
        ]

        # ── Geliştirme deseni ve orijinallik ──
        is_solo = len(authors) == 1
        is_sustained = span_days >= 14 and not burst_detected
        is_incremental = conv_pct >= 30 or avg_msg_len >= 20

        if is_sustained and is_incremental:
            dev_pattern = f"{'Tek geliştirici' if is_solo else 'Takım'} — sürdürülebilir, organik geliştirme ({span_days} gün)"
            originality = "Yüksek — commit'ler kademeli özellik geliştirme gösteriyor, toplu içe aktarım değil"
        elif burst_detected:
            dev_pattern = f"Patlama kalıbı — kısa sürede yoğun commit (burst detected)"
            originality = "Şüpheli — kısa sürede çok sayıda commit, kopya olabilir"
        else:
            dev_pattern = f"{'Tek geliştirici' if is_solo else 'Takım'} — {span_days} gün boyunca geliştirme"
            originality = "Orta — daha fazla veri gerekiyor"

        result = {
            'total_commits_analyzed': len(commits),
            'commit_span_days': span_days,
            'authors': authors,
            'commit_frequency': {
                'avg_per_week': avg_per_week,
                'most_active_day': most_active_day,
                'burst_detected': burst_detected,
            },
            'message_quality': {
                'conventional_commits_pct': conv_pct,
                'avg_message_length': avg_msg_len,
                'categories': dict(categories),
            },
            'file_churn': file_churn,
            'development_pattern': dev_pattern,
            'originality_assessment': originality,
        }
        if self.cache:
            await self.cache.set(owner, repo, "analyze_commit_patterns", result)
        return result
