"""auth.py — GitHub API için OAuth 2.0 + PAT kimlik doğrulama modülü.

İki kimlik doğrulama modunu destekler:
  1. Personal Access Token (PAT) — GITHUB_TOKEN ortam değişkeni ile
  2. OAuth 2.0 Uygulama Akışı — GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET ile

Tüm token'lar kullanılmadan önce gerekli izinler (scope) kontrol edilir.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── GitHub API sabitleri ──────────────────────────────────────────────
GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN = "https://github.com/login/oauth/access_token"

# Tam işlevsellik için gereken izinler (scope)
REQUIRED_SCOPES = {"repo", "read:user"}


# ── Ayarlar ───────────────────────────────────────────────────────────
@dataclass
class AuthSettings:
    """Ortam değişkenlerinden yüklenen merkezi kimlik doğrulama ayarları."""

    github_token: Optional[str] = field(default=None)
    github_client_id: Optional[str] = field(default=None)
    github_client_secret: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        self.github_token = self.github_token or os.getenv("GITHUB_TOKEN")
        self.github_client_id = self.github_client_id or os.getenv("GITHUB_CLIENT_ID")
        self.github_client_secret = self.github_client_secret or os.getenv(
            "GITHUB_CLIENT_SECRET"
        )

    @property
    def has_pat(self) -> bool:
        """PAT token tanımlı mı?"""
        return bool(self.github_token)

    @property
    def has_oauth(self) -> bool:
        """OAuth uygulama kimlik bilgileri tanımlı mı?"""
        return bool(self.github_client_id and self.github_client_secret)


# ── Token yardımcıları ────────────────────────────────────────────────
def get_auth_headers(token: str) -> dict[str, str]:
    """Versiyonlu Accept header'ı içeren standart GitHub API header'larını döndürür.

    AGENTS.md gereği her zaman X-GitHub-Api-Version dahil edilir.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def validate_token(token: str) -> dict:
    """Token'ı GitHub API'ye karşı doğrular ve kullanıcı bilgisini döndürür.

    Raises:
        httpx.HTTPStatusError: Token geçersizse (401).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API_BASE}/user",
            headers=get_auth_headers(token),
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()


async def check_token_scopes(token: str) -> set[str]:
    """Verilen token'a tanınmış OAuth izinlerini (scope) döndürür."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API_BASE}/user",
            headers=get_auth_headers(token),
            timeout=30.0,
        )
        resp.raise_for_status()
        scopes_header = resp.headers.get("X-OAuth-Scopes", "")
        return {s.strip() for s in scopes_header.split(",") if s.strip()}


# ── OAuth 2.0 Akışı ──────────────────────────────────────────────────
class OAuthFlow:
    """GitHub OAuth 2.0 yetkilendirme kodu akışını uygular.

    Kullanım:
        flow = OAuthFlow(settings)
        url = flow.get_authorization_url()
        # ... kullanıcı url'yi ziyaret eder, GitHub code + state ile geri yönlendirir ...
        token = await flow.exchange_code(code, state)
    """

    def __init__(self, settings: AuthSettings) -> None:
        if not settings.has_oauth:
            raise ValueError(
                "OAuth için GITHUB_CLIENT_ID ve GITHUB_CLIENT_SECRET gereklidir"
            )
        self.client_id = settings.github_client_id
        self.client_secret = settings.github_client_secret
        self._state: Optional[str] = None

    def get_authorization_url(
        self,
        scopes: str = "repo,read:user",
        redirect_uri: Optional[str] = None,
    ) -> str:
        """CSRF state token'ı ile GitHub OAuth yetkilendirme URL'si oluşturur."""
        self._state = secrets.token_urlsafe(32)
        url = (
            f"{GITHUB_OAUTH_AUTHORIZE}"
            f"?client_id={self.client_id}"
            f"&scope={scopes}"
            f"&state={self._state}"
        )
        if redirect_uri:
            url += f"&redirect_uri={redirect_uri}"
        return url

    @property
    def state(self) -> Optional[str]:
        return self._state

    async def exchange_code(self, code: str, state: str) -> str:
        """Yetkilendirme kodunu erişim token'ına dönüştürür.

        Args:
            code: GitHub callback'inden gelen yetkilendirme kodu.
            state: CSRF state token'ı — oluşturduğumuzla eşleşmeli.

        Returns:
            Erişim token'ı string'i.

        Raises:
            ValueError: State parametresi eşleşmiyorsa (CSRF koruması).
            httpx.HTTPStatusError: Token değişimi başarısız olursa.
        """
        if state != self._state:
            raise ValueError("OAuth state uyumsuzluğu — olası CSRF saldırısı")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GITHUB_OAUTH_TOKEN,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise ValueError(f"OAuth hatası: {data['error_description']}")

        token = data["access_token"]
        logger.info("OAuth token başarıyla alındı")
        return token


# ── Kimlik Doğrulama Yöneticisi ──────────────────────────────────────
class AuthManager:
    """Üst düzey kimlik doğrulama yöneticisi — aktif token'ı çözümler.

    OAuth token varsa onu tercih eder, yoksa PAT'a geri döner.
    """

    def __init__(self, settings: Optional[AuthSettings] = None) -> None:
        self.settings = settings or AuthSettings()
        self._oauth_token: Optional[str] = None

    def set_oauth_token(self, token: str) -> None:
        """OAuth akışı ile elde edilen token'ı saklar."""
        self._oauth_token = token

    def get_token(self) -> str:
        """Mevcut en iyi token'ı döndürür.

        Raises:
            RuntimeError: Hiçbir token yapılandırılmamışsa.
        """
        if self._oauth_token:
            return self._oauth_token
        if self.settings.has_pat:
            return self.settings.github_token  # type: ignore[return-value]
        raise RuntimeError(
            "GitHub token'ı yapılandırılmamış. "
            "GITHUB_TOKEN ortam değişkenini ayarlayın veya OAuth akışını tamamlayın."
        )

    def get_headers(self) -> dict[str, str]:
        """Kolaylık metodu — aktif token için kimlik doğrulama header'larını döndürür."""
        return get_auth_headers(self.get_token())
