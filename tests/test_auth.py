"""test_auth.py — Kimlik doğrulama modülü testleri.

Kapsam: PAT auth, OAuth akışı, token doğrulama, izin (scope) kontrolü.
Tüm testler respx kullanır — gerçek HTTP çağrısı yapılmaz.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_github_advanced.auth import (
    AuthManager,
    AuthSettings,
    OAuthFlow,
    check_token_scopes,
    get_auth_headers,
    validate_token,
)


# ══════════════════════════════════════════════════════════════════════
#  AuthSettings — Kimlik doğrulama ayarları
# ══════════════════════════════════════════════════════════════════════

class TestAuthSettings:
    def test_acik_degerlerle(self):
        """Açık değerlerle oluşturulan ayarlar doğru çalışmalı."""
        s = AuthSettings(
            github_token="ghp_test",
            github_client_id="cid",
            github_client_secret="csec",
        )
        assert s.has_pat is True
        assert s.has_oauth is True

    def test_ortam_degiskeninden(self, monkeypatch):
        """Ortam değişkeninden token yüklenmeli."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_env")
        s = AuthSettings()
        assert s.github_token == "ghp_from_env"
        assert s.has_pat is True

    def test_token_yok(self, monkeypatch):
        """Hiçbir token yoksa has_pat ve has_oauth False olmalı."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        s = AuthSettings()
        assert s.has_pat is False
        assert s.has_oauth is False


# ══════════════════════════════════════════════════════════════════════
#  get_auth_headers — Kimlik doğrulama header'ları
# ══════════════════════════════════════════════════════════════════════

class TestGetAuthHeaders:
    def test_versiyonlu_headerlar_iceriyor(self):
        """Header'lar versiyonlu Accept ve API version içermeli."""
        headers = get_auth_headers("ghp_test")
        assert headers["Authorization"] == "Bearer ghp_test"
        assert headers["Accept"] == "application/vnd.github+json"
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"


# ══════════════════════════════════════════════════════════════════════
#  validate_token — Token doğrulama
# ══════════════════════════════════════════════════════════════════════

class TestValidateToken:
    @respx.mock
    async def test_gecerli_token(self):
        """Geçerli token ile kullanıcı bilgisi dönmeli."""
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={
                "login": "testuser",
                "id": 12345,
            })
        )
        user = await validate_token("ghp_valid")
        assert user["login"] == "testuser"

    @respx.mock
    async def test_gecersiz_token(self):
        """Geçersiz token ile HTTP hatası fırlatmalı."""
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(401, json={"message": "Bad credentials"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await validate_token("ghp_invalid")


# ══════════════════════════════════════════════════════════════════════
#  check_token_scopes — Token izinleri kontrolü
# ══════════════════════════════════════════════════════════════════════

class TestCheckTokenScopes:
    @respx.mock
    async def test_izinleri_dondurur(self):
        """Token izinleri (scope) doğru şekilde dönmeli."""
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(
                200,
                json={"login": "testuser"},
                headers={"X-OAuth-Scopes": "repo, read:user, write:org"},
            )
        )
        scopes = await check_token_scopes("ghp_scoped")
        assert "repo" in scopes
        assert "read:user" in scopes
        assert "write:org" in scopes

    @respx.mock
    async def test_izin_headeri_yok(self):
        """Scope header'ı yoksa boş set dönmeli."""
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "testuser"})
        )
        scopes = await check_token_scopes("ghp_no_scopes")
        assert scopes == set()


# ══════════════════════════════════════════════════════════════════════
#  AuthManager — Kimlik doğrulama yöneticisi
# ══════════════════════════════════════════════════════════════════════

class TestAuthManager:
    def test_pat_token(self, auth_settings):
        """PAT token doğru döndürülmeli."""
        manager = AuthManager(auth_settings)
        assert manager.get_token() == "ghp_test_token_1234567890"

    def test_oauth_token_tercih_edilir(self, auth_settings):
        """OAuth token varsa PAT yerine tercih edilmeli."""
        manager = AuthManager(auth_settings)
        manager.set_oauth_token("oauth_token_xyz")
        assert manager.get_token() == "oauth_token_xyz"

    def test_token_yoksa_hata_firlatir(self, monkeypatch):
        """Hiçbir token yoksa RuntimeError fırlatmalı."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        settings = AuthSettings(
            github_token=None,
            github_client_id=None,
            github_client_secret=None,
        )
        manager = AuthManager(settings)
        with pytest.raises(RuntimeError, match="GitHub token"):
            manager.get_token()

    def test_headerlari_getir(self, auth_settings):
        """get_headers() doğru header'ları döndürmeli."""
        manager = AuthManager(auth_settings)
        headers = manager.get_headers()
        assert "Authorization" in headers
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"


# ══════════════════════════════════════════════════════════════════════
#  OAuthFlow — OAuth 2.0 akışı
# ══════════════════════════════════════════════════════════════════════

class TestOAuthFlow:
    def test_client_bilgileri_gerektirir(self):
        """OAuth için client_id ve client_secret zorunlu olmalı."""
        settings = AuthSettings(github_token="ghp_test")
        settings.github_client_id = None
        settings.github_client_secret = None
        with pytest.raises(ValueError, match="OAuth"):
            OAuthFlow(settings)

    def test_yetkilendirme_url(self, auth_settings):
        """Yetkilendirme URL'si doğru parametreleri içermeli."""
        flow = OAuthFlow(auth_settings)
        url = flow.get_authorization_url()
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=Ov23test_client_id" in url
        assert "scope=repo,read:user" in url
        assert flow.state is not None

    def test_state_uyusmazligi_hata_firlatir(self, auth_settings):
        """Yanlış state parametresi CSRF hatası fırlatmalı."""
        flow = OAuthFlow(auth_settings)
        flow.get_authorization_url()
        with pytest.raises(ValueError, match="state"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                flow.exchange_code("code", "yanlis_state")
            )

    @respx.mock
    async def test_kod_degisimi_basarili(self, auth_settings):
        """Başarılı yetkilendirme kodu değişimi erişim token'ı döndürmeli."""
        flow = OAuthFlow(auth_settings)
        flow.get_authorization_url()
        state = flow.state

        respx.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "gho_oauth_token_abc",
                "token_type": "bearer",
                "scope": "repo,read:user",
            })
        )

        token = await flow.exchange_code("auth_code_123", state)
        assert token == "gho_oauth_token_abc"

    @respx.mock
    async def test_kod_degisimi_hata(self, auth_settings):
        """Geçersiz yetkilendirme kodu OAuth hatası fırlatmalı."""
        flow = OAuthFlow(auth_settings)
        flow.get_authorization_url()
        state = flow.state

        respx.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(200, json={
                "error": "bad_verification_code",
                "error_description": "The code passed is incorrect or expired.",
            })
        )

        with pytest.raises(ValueError, match="OAuth"):
            await flow.exchange_code("gecersiz_kod", state)
