"""cache.py — GitHub API yanıtları için Redis önbellekleme katmanı.

AGENTS.md'de tanımlanan TTL stratejisini kullanır:
    get_repo_info      → 3600 sn  (1 saat)
    list_commits       →  300 sn  (5 dakika)
    get_pr_diff        →  600 sn  (10 dakika)
    get_workflow_logs  →   60 sn  (1 dakika)
    get_file_content   → 1800 sn  (30 dakika)

Önbellek anahtar formatı: github:{owner}:{repo}:{tool_name}
Redis kullanılamadığında sorunsuz şekilde devre dışı kalır.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── AGENTS.md'den TTL stratejisi ─────────────────────────────────────
TTL: dict[str, int] = {
    "get_repo_info": 3600,         # 1 saat
    "list_commits": 300,           # 5 dakika
    "get_pr_diff": 600,            # 10 dakika
    "get_workflow_logs": 60,       # 1 dakika
    "get_file_content": 1800,      # 30 dakika
    "list_repo_files": 1800,       # 30 dakika
    "search_code": 300,            # 5 dakika
    "get_commit_diff": 600,        # 10 dakika
    "get_contributor_stats": 3600, # 1 saat
    "list_pull_requests": 300,     # 5 dakika
    "create_pr_review": 0,         # önbellek yok — yazma işlemi
    "list_issues": 300,            # 5 dakika
    "create_issue": 0,             # önbellek yok — yazma işlemi
    "get_workflow_runs": 300,      # 5 dakika
    "list_user_repos": 3600,       # 1 saat
}

DEFAULT_TTL = 300  # 5 dakika varsayılan


def _build_key(owner: str, repo: str, tool_name: str, extra: str = "") -> str:
    """AGENTS.md formatına uygun Redis anahtarı oluşturur:

        github:{owner}:{repo}:{tool_name}[:extra]
    """
    key = f"github:{owner}:{repo}:{tool_name}"
    if extra:
        key += f":{extra}"
    return key


class RedisCache:
    """Async uyumlu Redis önbellek sarmalayıcısı.

    Sorunsuz çalışacak şekilde tasarlanmıştır — tüm public metodlar
    Redis hatalarını yakalar ve istisna fırlatmak yerine uyarı loglar.
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://localhost:6379/0"
        )
        self._client: Any = None  # Bağlandığında redis.asyncio.Redis olur

    async def connect(self) -> None:
        """Redis'e bağlanır. Redis kullanılamıyorsa sessizce başarısız olur."""
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            logger.info("Redis bağlantısı kuruldu: %s", self._redis_url)
        except Exception as exc:
            logger.warning("Redis kullanılamıyor, önbellekleme devre dışı: %s", exc)
            self._client = None

    async def close(self) -> None:
        """Açık olan Redis bağlantısını kapatır."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def is_connected(self) -> bool:
        """Redis bağlantısı açık mı?"""
        return self._client is not None

    async def get(
        self,
        owner: str,
        repo: str,
        tool_name: str,
        extra: str = "",
    ) -> Optional[Any]:
        """Önbellekten değer alır. Bulamazsa veya hata olursa None döner."""
        if not self._client:
            return None
        key = _build_key(owner, repo, tool_name, extra)
        try:
            raw = await self._client.get(key)
            if raw is not None:
                logger.debug("Önbellek İSABET: %s", key)
                return json.loads(raw)
            logger.debug("Önbellek ISKALAMA: %s", key)
        except Exception as exc:
            logger.warning("Önbellek okuma hatası: %s", exc)
        return None

    async def set(
        self,
        owner: str,
        repo: str,
        tool_name: str,
        value: Any,
        extra: str = "",
        ttl: Optional[int] = None,
    ) -> None:
        """Yapılandırılmış TTL ile önbelleğe değer yazar."""
        if not self._client:
            return
        # Yazma işlemleri için önbellekleme yapma
        resolved_ttl = ttl if ttl is not None else TTL.get(tool_name, DEFAULT_TTL)
        if resolved_ttl <= 0:
            return

        key = _build_key(owner, repo, tool_name, extra)
        try:
            await self._client.set(key, json.dumps(value), ex=resolved_ttl)
            logger.debug("Önbellek YAZMA: %s (TTL=%d sn)", key, resolved_ttl)
        except Exception as exc:
            logger.warning("Önbellek yazma hatası: %s", exc)

    async def invalidate(
        self,
        owner: str,
        repo: str,
        tool_name: str,
        extra: str = "",
    ) -> None:
        """Belirli bir anahtarı önbellekten siler."""
        if not self._client:
            return
        key = _build_key(owner, repo, tool_name, extra)
        try:
            await self._client.delete(key)
            logger.debug("Önbellek GEÇERSİZ KILMA: %s", key)
        except Exception as exc:
            logger.warning("Önbellek geçersiz kılma hatası: %s", exc)

    async def flush_repo(self, owner: str, repo: str) -> None:
        """Belirli bir repo için TÜM önbellek anahtarlarını siler."""
        if not self._client:
            return
        pattern = f"github:{owner}:{repo}:*"
        try:
            cursor = "0"
            while cursor:
                cursor, keys = await self._client.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._client.delete(*keys)
            logger.info("%s/%s için önbellek temizlendi", owner, repo)
        except Exception as exc:
            logger.warning("Önbellek temizleme hatası: %s", exc)
