"""server.py — 14 GitHub aracını MCP protokolü üzerinden sunan ana sunucu.

Low-level mcp.server.Server kullanır (FastMCP DEĞİL), stdio transport ile çalışır.
Her araç list_tools() içinde tanımlanır ve call_tool() üzerinden yönlendirilir.

Araçlar şu şekilde gruplandırılmıştır:
  📁 Repo:    get_repo_info, get_file_content, list_repo_files, search_code
  📝 Commit:  list_commits, get_commit_diff, get_contributor_stats
  🔀 PR:      list_pull_requests, get_pr_diff, create_pr_review
  🐛 Issue:   list_issues, create_issue
  ⚙️ CI/CD:   get_workflow_runs, get_workflow_logs
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from mcp_github_advanced.auth import AuthManager, AuthSettings
from mcp_github_advanced.cache import RedisCache
from mcp_github_advanced.github import GitHubClient

load_dotenv()

# ── Loglama ayarları ─────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,  # MCP stdio kullandığı için loglar stderr'e yazılır
)
logger = logging.getLogger(__name__)

# ── Sunucu örneği ────────────────────────────────────────────────────
server_name = os.getenv("MCP_SERVER_NAME", "mcp-github-advanced")
app = Server(server_name)  # Low-level MCP Server (FastMCP değil)

# ── Paylaşılan durum (main içinde başlatılır) ────────────────────────
_github: GitHubClient | None = None


def _get_github() -> GitHubClient:
    """GitHub istemcisini döndürür. Başlatılmamışsa hata fırlatır."""
    assert _github is not None, "GitHubClient henüz başlatılmadı"
    return _github


# ══════════════════════════════════════════════════════════════════════
#  ARAÇ TANIMLARI — 14 MCP Aracı
#  Her araç: name (isim), description (açıklama), inputSchema (giriş şeması)
# ══════════════════════════════════════════════════════════════════════
TOOLS: list[Tool] = [

    # ──────────────────────────────────────────────────────────────────
    #  📁 REPO ARAÇLARI — Repo bilgisi, dosya içeriği, dizin ağacı, kod arama
    # ──────────────────────────────────────────────────────────────────
    Tool(
        name="get_repo_info",
        description="Repo meta verilerini getirir: yıldız, fork, dil, boyut, konular",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi (kullanıcı veya organizasyon)"},
                "repo": {"type": "string", "description": "Repo adı"},
            },
            "required": ["owner", "repo"],
        },
    ),
    Tool(
        name="get_file_content",
        description="Repodaki bir dosyanın içeriğini getirir",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "path": {"type": "string", "description": "Repodaki dosya yolu (örn: src/main.py)"},
                "ref": {"type": "string", "description": "Git referansı (dal/etiket/sha), opsiyonel"},
            },
            "required": ["owner", "repo", "path"],
        },
    ),
    Tool(
        name="list_repo_files",
        description="Repodaki tüm dosyaları listeler (dizin ağacı)",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "ref": {"type": "string", "description": "Git referansı (dal/etiket/sha), opsiyonel"},
            },
            "required": ["owner", "repo"],
        },
    ),
    Tool(
        name="search_code",
        description="Repo içinde kod veya metin arar",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "query": {"type": "string", "description": "Aranacak metin veya kod parçası"},
            },
            "required": ["owner", "repo", "query"],
        },
    ),

    # ──────────────────────────────────────────────────────────────────
    #  📝 COMMIT ARAÇLARI — Commit geçmişi, diff, katkıda bulunan istatistikleri
    # ──────────────────────────────────────────────────────────────────
    Tool(
        name="list_commits",
        description="Commit geçmişini mesajları ve yazarlarıyla birlikte listeler",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "per_page": {
                    "type": "integer",
                    "description": "Kaç commit getirileceği (varsayılan: 30)",
                    "default": 30,
                },
                "sha": {
                    "type": "string",
                    "description": "Başlangıç dal adı veya commit SHA değeri",
                },
            },
            "required": ["owner", "repo"],
        },
    ),
    Tool(
        name="get_commit_diff",
        description="Tek bir commit'in tüm değişikliklerini (diff) getirir",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "sha": {"type": "string", "description": "Tam commit SHA değeri"},
            },
            "required": ["owner", "repo", "sha"],
        },
    ),
    Tool(
        name="get_contributor_stats",
        description="Katkıda bulunan istatistiklerini getirir — kim ne kadar katkı yaptı",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
            },
            "required": ["owner", "repo"],
        },
    ),

    # ──────────────────────────────────────────────────────────────────
    #  🔀 PR ARAÇLARI — Pull request listesi, diff, AI review
    # ──────────────────────────────────────────────────────────────────
    Tool(
        name="list_pull_requests",
        description="Açık/kapalı pull request'leri listeler",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "state": {
                    "type": "string",
                    "description": "PR durumu: open (açık), closed (kapalı), all (hepsi). Varsayılan: open",
                    "default": "open",
                    "enum": ["open", "closed", "all"],
                },
                "per_page": {
                    "type": "integer",
                    "description": "Kaç PR getirileceği (varsayılan: 30)",
                    "default": 30,
                },
            },
            "required": ["owner", "repo"],
        },
    ),
    Tool(
        name="get_pr_diff",
        description="Bir pull request'in tüm değişikliklerini ve değişen dosyaları getirir",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "pr_number": {"type": "integer", "description": "Pull request numarası"},
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="create_pr_review",
        description="Bir pull request'e AI review yorumu yazar",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "pr_number": {"type": "integer", "description": "Pull request numarası"},
                "body": {"type": "string", "description": "Review yorum içeriği"},
                "event": {
                    "type": "string",
                    "description": "Review türü: COMMENT (yorum), APPROVE (onayla), REQUEST_CHANGES (değişiklik iste)",
                    "default": "COMMENT",
                    "enum": ["COMMENT", "APPROVE", "REQUEST_CHANGES"],
                },
            },
            "required": ["owner", "repo", "pr_number", "body"],
        },
    ),

    # ──────────────────────────────────────────────────────────────────
    #  🐛 ISSUE ARAÇLARI — Issue listesi, yeni issue oluşturma
    # ──────────────────────────────────────────────────────────────────
    Tool(
        name="list_issues",
        description="Repodaki issue'ları etiketleriyle birlikte listeler",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "state": {
                    "type": "string",
                    "description": "Issue durumu: open (açık), closed (kapalı), all (hepsi). Varsayılan: open",
                    "default": "open",
                    "enum": ["open", "closed", "all"],
                },
                "per_page": {
                    "type": "integer",
                    "description": "Kaç issue getirileceği (varsayılan: 30)",
                    "default": 30,
                },
            },
            "required": ["owner", "repo"],
        },
    ),
    Tool(
        name="create_issue",
        description="Repoda yeni bir issue açar",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "title": {"type": "string", "description": "Issue başlığı"},
                "body": {"type": "string", "description": "Issue içeriği (markdown destekler)"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Eklenecek etiketler (örn: bug, enhancement)",
                },
                "assignees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Atanacak kullanıcılar",
                },
            },
            "required": ["owner", "repo", "title"],
        },
    ),

    # ──────────────────────────────────────────────────────────────────
    #  ⚙️ CI/CD ARAÇLARI — GitHub Actions iş akışları ve loglar
    # ──────────────────────────────────────────────────────────────────
    Tool(
        name="get_workflow_runs",
        description="CI/CD iş akışı çalıştırmalarını listeler — durum, sonuç, dal bilgisi",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "per_page": {
                    "type": "integer",
                    "description": "Kaç çalıştırma getirileceği (varsayılan: 10)",
                    "default": 10,
                },
            },
            "required": ["owner", "repo"],
        },
    ),
    Tool(
        name="get_workflow_logs",
        description="Bir iş akışı çalıştırmasının iş detaylarını ve adım loglarını getirir",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo sahibi"},
                "repo": {"type": "string", "description": "Repo adı"},
                "run_id": {"type": "integer", "description": "İş akışı çalıştırma ID'si"},
            },
            "required": ["owner", "repo", "run_id"],
        },
    ),
]

# Hızlı araç ismi kontrolü için set
_TOOL_NAMES = {t.name for t in TOOLS}


# ══════════════════════════════════════════════════════════════════════
#  İSTEK YÖNLENDİRİCİLER (Handlers)
# ══════════════════════════════════════════════════════════════════════

@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Tüm 14 MCP aracını döndürür.

    MCP istemcisi (örn: Claude Desktop, Cursor) bu fonksiyonu çağırarak
    hangi araçların mevcut olduğunu öğrenir.
    """
    return TOOLS


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Araç çağrılarını GitHubClient'a yönlendirir.

    Bu fonksiyon MCP istemcisi bir araç çağırdığında tetiklenir.
    1. Araç adını kontrol eder
    2. _dispatch() ile doğru GitHubClient metoduna yönlendirir
    3. Sonucu JSON olarak döner
    4. Hata durumunda hata mesajı döner (çökmez)
    5. Çıktı 30.000 karakteri aşarsa keser (Gemini 8192 token limiti)
    """
    if name not in _TOOL_NAMES:
        return [TextContent(type="text", text=f"Bilinmeyen araç: {name}")]

    gh = _get_github()

    try:
        result = await _dispatch(gh, name, arguments)
        text = json.dumps(result, indent=2, ensure_ascii=False, default=str)

        # Son güvenlik — Gemini 8192 token limiti için çıktıyı kes
        if len(text) > 30_000:
            text = text[:30_000] + "\n\n... [kesildi — 8192 token limitini aşıyor]"
        return [TextContent(type="text", text=text)]

    except Exception as exc:
        logger.exception("Araç %s başarısız oldu", name)
        return [TextContent(type="text", text=f"Hata: {exc}")]


async def _dispatch(gh: GitHubClient, name: str, args: dict) -> object:
    """Araç adını ilgili GitHubClient metoduna yönlendirir.

    Python match-case yapısı kullanarak her araç adını
    karşılık gelen github.py metoduna eşler.
    """
    owner = args.get("owner", "")
    repo = args.get("repo", "")

    match name:
        # ── 📁 Repo Araçları ──
        case "get_repo_info":
            return await gh.get_repo_info(owner, repo)
        case "get_file_content":
            return await gh.get_file_content(owner, repo, args["path"], args.get("ref"))
        case "list_repo_files":
            return await gh.list_repo_files(owner, repo, args.get("ref"))
        case "search_code":
            return await gh.search_code(owner, repo, args["query"])

        # ── 📝 Commit Araçları ──
        case "list_commits":
            return await gh.list_commits(
                owner, repo, args.get("per_page", 30), args.get("sha"),
            )
        case "get_commit_diff":
            return await gh.get_commit_diff(owner, repo, args["sha"])
        case "get_contributor_stats":
            return await gh.get_contributor_stats(owner, repo)

        # ── 🔀 PR Araçları ──
        case "list_pull_requests":
            return await gh.list_pull_requests(
                owner, repo, args.get("state", "open"), args.get("per_page", 30),
            )
        case "get_pr_diff":
            return await gh.get_pr_diff(owner, repo, args["pr_number"])
        case "create_pr_review":
            return await gh.create_pr_review(
                owner, repo, args["pr_number"], args["body"], args.get("event", "COMMENT"),
            )

        # ── 🐛 Issue Araçları ──
        case "list_issues":
            return await gh.list_issues(
                owner, repo, args.get("state", "open"), args.get("per_page", 30),
            )
        case "create_issue":
            return await gh.create_issue(
                owner,
                repo,
                args["title"],
                args.get("body"),
                args.get("labels"),
                args.get("assignees"),
            )

        # ── ⚙️ CI/CD Araçları ──
        case "get_workflow_runs":
            return await gh.get_workflow_runs(owner, repo, args.get("per_page", 10))
        case "get_workflow_logs":
            return await gh.get_workflow_logs(owner, repo, args["run_id"])

        # ── Bilinmeyen araç ──
        case _:
            return {"hata": f"Bilinmeyen araç: {name}"}


# ══════════════════════════════════════════════════════════════════════
#  SUNUCU BAŞLATMA
# ══════════════════════════════════════════════════════════════════════

async def _run() -> None:
    """MCP sunucusunu stdio transport ile başlatır.

    Başlatma sırası:
    1. AuthSettings — .env'den token bilgilerini yükler
    2. AuthManager  — PAT veya OAuth token'ı yönetir
    3. RedisCache   — Redis bağlantısı kurar (yoksa devre dışı kalır)
    4. GitHubClient — HTTP istemcisini başlatır
    5. stdio_server — stdin/stdout üzerinden MCP protokolünü dinler
    """
    global _github

    # Kimlik doğrulama ayarlarını yükle
    settings = AuthSettings()
    auth = AuthManager(settings)

    # Redis cache'i başlat (bağlanamazsa sessizce devre dışı kalır)
    cache = RedisCache()

    # GitHub API istemcisini oluştur ve başlat
    _github = GitHubClient(auth=auth, cache=cache)
    await _github.start()

    logger.info("%s sunucusu %d araçla başlatılıyor", server_name, len(TOOLS))

    try:
        # stdio üzerinden MCP protokolünü dinle
        # read_stream: istemciden gelen istekler (stdin)
        # write_stream: istemciye gönderilen yanıtlar (stdout)
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    finally:
        # Sunucu kapanırken bağlantıları temizle
        await _github.close()


def main() -> None:
    """Senkron giriş noktası — pyproject.toml'daki console_scripts bunu çağırır.

    pyproject.toml'da şu satır bu fonksiyona işaret eder:
        mcp-github-advanced = "mcp_github_advanced.server:main"
    """
    asyncio.run(_run())


if __name__ == "__main__":
    main()
