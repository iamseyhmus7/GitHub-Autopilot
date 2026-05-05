"""server.py — 17 GitHub aracını MCP protokolü üzerinden sunan ana sunucu.

FastMCP kullanır — hem stdio hem SSE (HTTP) transport destekler.
Her araç @mcp.tool() dekoratörü ile tanımlanır.

Araçlar şu şekilde gruplandırılmıştır:
  📁 Repo:    list_user_repos, get_repo_info, get_file_content, list_repo_files, search_code
  📝 Commit:  list_commits, get_commit_diff, get_contributor_stats
  🔀 PR:      list_pull_requests, get_pr_diff
  🐛 Issue:   list_issues
  ⚙️ CI/CD:   get_workflow_runs
  🧠 Derin:   analyze_architecture, analyze_dependencies, detect_entry_points,
              analyze_codebase_complexity, analyze_commit_patterns

Çalıştırma:
  stdio:  python -m mcp_github_advanced
  SSE:    fastmcp run src/mcp_github_advanced/server.py:mcp --transport sse --port 8080
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from mcp_github_advanced.auth import AuthManager, AuthSettings
from mcp_github_advanced.cache import RedisCache
from mcp_github_advanced.github import GitHubClient

from pathlib import Path
# .env dosyasını projenin kök dizininde bulmaya çalış (src/../.env)
dotenv_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path, override=True)

# ── Loglama ayarları ─────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ── Paylaşılan durum ─────────────────────────────────────────────────
_github: GitHubClient | None = None

MAX_OUTPUT_CHARS = 30_000


def _get_github() -> GitHubClient:
    """GitHub istemcisini döndürür. Başlatılmamışsa hata fırlatır."""
    assert _github is not None, "GitHubClient henüz başlatılmadı"
    return _github


def _to_json(data: object) -> str:
    """Sonucu JSON string'e çevirir, çıktıyı 8192 token limitine göre keser."""
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + "\n\n... [kesildi — 8192 token limitini aşıyor]"
    return text


# ── Lifespan — sunucu başlarken/kapanırken çalışır ───────────────────
@asynccontextmanager
async def lifespan(app):
    """Sunucu başlarken GitHubClient'ı başlatır, kapanırken kapatır."""
    global _github
    settings = AuthSettings()
    auth = AuthManager(settings)
    cache = RedisCache()
    _github = GitHubClient(auth=auth, cache=cache)
    await _github.start()
    logger.info("GitHubClient başlatıldı")
    try:
        yield
    finally:
        await _github.close()
        logger.info("GitHubClient kapatıldı")


# ── FastMCP Sunucu Örneği ────────────────────────────────────────────
server_name = os.getenv("MCP_SERVER_NAME", "mcp-github-advanced")
mcp = FastMCP(server_name, lifespan=lifespan)


# ══════════════════════════════════════════════════════════════════════
#  📁 REPO ARAÇLARI
# ══════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_user_repos(
    username: str,
    per_page: int = 100,
    sort: str = "updated",
) -> str:
    """Bir kullanıcının tüm genel repolarını listeler (isim, açıklama, yıldız sayısı, dil)"""
    gh = _get_github()
    result = await gh.list_user_repos(username, per_page, sort)
    return _to_json(result)


@mcp.tool()
async def get_repo_info(owner: str, repo: str) -> str:
    """Repo meta verilerini getirir: yıldız, fork, dil, boyut, konular"""
    gh = _get_github()
    result = await gh.get_repo_info(owner, repo)
    return _to_json(result)


@mcp.tool()
async def get_file_content(
    owner: str,
    repo: str,
    path: str,
    ref: Optional[str] = None,
) -> str:
    """Repodaki bir dosyanın içeriğini getirir"""
    gh = _get_github()
    result = await gh.get_file_content(owner, repo, path, ref)
    return _to_json(result)


@mcp.tool()
async def list_repo_files(
    owner: str,
    repo: str,
    ref: Optional[str] = None,
) -> str:
    """Repodaki tüm dosyaları listeler (dizin ağacı)"""
    gh = _get_github()
    result = await gh.list_repo_files(owner, repo, ref)
    return _to_json(result)


@mcp.tool()
async def search_code(owner: str, repo: str, query: str) -> str:
    """Repo içinde kod veya metin arar"""
    gh = _get_github()
    result = await gh.search_code(owner, repo, query)
    return _to_json(result)


# ══════════════════════════════════════════════════════════════════════
#  📝 COMMIT ARAÇLARI
# ══════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_commits(
    owner: str,
    repo: str,
    per_page: int = 30,
    sha: Optional[str] = None,
) -> str:
    """Commit geçmişini mesajları ve yazarlarıyla birlikte listeler"""
    gh = _get_github()
    result = await gh.list_commits(owner, repo, per_page, sha)
    return _to_json(result)


@mcp.tool()
async def get_commit_diff(owner: str, repo: str, sha: str) -> str:
    """Tek bir commit'in tüm değişikliklerini (diff) getirir"""
    gh = _get_github()
    result = await gh.get_commit_diff(owner, repo, sha)
    return _to_json(result)


@mcp.tool()
async def get_contributor_stats(owner: str, repo: str) -> str:
    """Katkıda bulunan istatistiklerini getirir — kim ne kadar katkı yaptı"""
    gh = _get_github()
    result = await gh.get_contributor_stats(owner, repo)
    return _to_json(result)


# ══════════════════════════════════════════════════════════════════════
#  🔀 PR ARAÇLARI
# ══════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_pull_requests(
    owner: str,
    repo: str,
    state: str = "open",
    per_page: int = 30,
) -> str:
    """Açık/kapalı pull request'leri listeler"""
    gh = _get_github()
    result = await gh.list_pull_requests(owner, repo, state, per_page)
    return _to_json(result)


@mcp.tool()
async def get_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """Bir pull request'in tüm değişikliklerini ve değişen dosyaları getirir"""
    gh = _get_github()
    result = await gh.get_pr_diff(owner, repo, pr_number)
    return _to_json(result)


# ══════════════════════════════════════════════════════════════════════
#  🐛 ISSUE ARAÇLARI
# ══════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    per_page: int = 30,
) -> str:
    """Repodaki issue'ları etiketleriyle birlikte listeler"""
    gh = _get_github()
    result = await gh.list_issues(owner, repo, state, per_page)
    return _to_json(result)


# ══════════════════════════════════════════════════════════════════════
#  ⚙️ CI/CD ARAÇLARI
# ══════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_workflow_runs(
    owner: str,
    repo: str,
    per_page: int = 10,
) -> str:
    """CI/CD iş akışı çalıştırmalarını listeler — durum, sonuç, dal bilgisi"""
    gh = _get_github()
    result = await gh.get_workflow_runs(owner, repo, per_page)
    return _to_json(result)


# ══════════════════════════════════════════════════════════════════════
#  🧠 DERİN ANALİZ ARAÇLARI (Deep Repository Intelligence)
# ══════════════════════════════════════════════════════════════════════

@mcp.tool()
async def analyze_architecture(owner: str, repo: str) -> str:
    """Projenin mimari yapısını derinlemesine analiz eder.

    Döndürür: katman tespiti, mimari desen (MVC, Clean Architecture vb.),
    framework algılama, test yapısı, dizin özeti ve Mermaid diyagramı.
    Tek çağrıda tam mimari haritayı sunar — dosya ağacını ve konfigürasyon
    dosyalarını otomatik okur."""
    gh = _get_github()
    result = await gh.analyze_architecture(owner, repo)
    return _to_json(result)


@mcp.tool()
async def analyze_dependencies(owner: str, repo: str) -> str:
    """Teknoloji yığınını ve modüller arası bağımlılık grafiğini çıkarır.

    Döndürür: dil dağılımı, bağımlılık manifest'leri (pyproject.toml,
    package.json vb.), harici kütüphaneler, iç modül import grafiği,
    altyapı bileşenleri (Docker, CI, Redis vb.) ve Mermaid diyagramı.
    En büyük 15 kaynak dosyanın import ifadelerini parse eder."""
    gh = _get_github()
    result = await gh.analyze_dependencies(owner, repo)
    return _to_json(result)


@mcp.tool()
async def detect_entry_points(owner: str, repo: str) -> str:
    """Projenin giriş noktalarını tespit eder.

    Döndürür: CLI komutları (pyproject.toml scripts, package.json bin),
    API rotaları (FastAPI/Flask/Express dekoratörleri), main dosyaları,
    Docker CMD/ENTRYPOINT komutları ve CI/CD tetikleyicileri.
    Projeye nereden başlanacağını anlamak için temel araç."""
    gh = _get_github()
    result = await gh.detect_entry_points(owner, repo)
    return _to_json(result)


@mcp.tool()
async def analyze_codebase_complexity(owner: str, repo: str) -> str:
    """Kod tabanının karmaşıklığını ve kritik dosyaları analiz eder.

    Döndürür: en büyük/kritik dosyalar, hotspot dizinler, tasarım desenleri
    (Decorator, Singleton, Factory, Strategy vb.), veri akışı haritası,
    1-10 arası karmaşıklık skoru ve Mermaid diyagramı.
    En büyük 5 kaynak dosyanın içeriğini okuyup desen analizi yapar."""
    gh = _get_github()
    result = await gh.analyze_codebase_complexity(owner, repo)
    return _to_json(result)


@mcp.tool()
async def analyze_commit_patterns(owner: str, repo: str) -> str:
    """Commit geçmişini derinlemesine analiz eder.

    Döndürür: commit frekansı (haftalık ortalama, en aktif gün),
    yazar dağılımı, mesaj kalitesi (conventional commits yüzdesi),
    burst tespiti (kopya vs gerçek emek), dosya churn analizi,
    geliştirme deseni ve orijinallik değerlendirmesi.
    Son 100 commit ve 5 örnek diff'i inceler."""
    gh = _get_github()
    result = await gh.analyze_commit_patterns(owner, repo)
    return _to_json(result)


# ══════════════════════════════════════════════════════════════════════
#  SUNUCU BAŞLATMA
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    """Senkron giriş noktası — pyproject.toml'daki console_scripts bunu çağırır.

    Varsayılan olarak stdio transport kullanır.
    SSE için: fastmcp run server.py:mcp --transport sse --port 8080
    """
    mcp.run()


if __name__ == "__main__":
    main()
