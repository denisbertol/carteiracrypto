"""Módulo de autenticação e autorização Supabase Auth e JWT."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
from uuid import UUID
try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from app.config import get_settings

try:
    import jwt
    from jwt import PyJWKClient
except ImportError:
    jwt = None  # type: ignore
    PyJWKClient = None  # type: ignore


class AuthError(Exception):
    """Exceção levantada quando a autenticação falha."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class TokenVerifier:
    """Validador de JWT emitido pelo Supabase Auth."""

    SUPPORTED_ALGORITHMS = ("RS256", "ES256")

    def __init__(self, jwks_client: Optional[Any] = None) -> None:
        self.settings = get_settings()
        self.jwks_url = f"{self.settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        # Injection keeps tests deterministic; production always uses the remote JWKS.
        self._jwks_client: Optional[Any] = jwks_client

    @property
    def jwks_client(self) -> Any:
        if self._jwks_client is None and PyJWKClient is not None:
            self._jwks_client = PyJWKClient(self.jwks_url, cache_jwk_set=True, lifespan=600)
        return self._jwks_client

    def verify_token(self, token: str) -> UUID:
        """
        Valida a assinatura do token, emissor, audiência e autorização do proprietário.
        Retorna o UUID do usuário autenticado.
        """
        if not token:
            raise AuthError("Token de autorização não fornecido.", status_code=401)

        if jwt is None:
            raise AuthError("Biblioteca PyJWT não disponível no ambiente.", status_code=500)

        # The unverified header is used only to reject unsupported algorithms.
        try:
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg")
        except Exception:
            raise AuthError("Token JWT malformado.", status_code=401)

        if alg not in self.SUPPORTED_ALGORITHMS:
            # In particular, never use the public Supabase API key as an HS256 secret.
            raise AuthError("Algoritmo de assinatura JWT não permitido.", status_code=401)

        try:
            if self.jwks_client is None:
                raise AuthError("Verificador JWKS indisponível.", status_code=503)
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self.SUPPORTED_ALGORITHMS),
                audience="authenticated",
                issuer=f"{self.settings.supabase_url.rstrip('/')}/auth/v1",
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expirado. Efetue login novamente.", status_code=401)
        except AuthError:
            raise
        except jwt.InvalidTokenError:
            raise AuthError("Token inválido.", status_code=401)
        except Exception:
            # JWKS lookup/network failures fail closed without leaking token details.
            raise AuthError("Não foi possível validar a assinatura JWT.", status_code=503)

        sub = payload.get("sub")
        try:
            user_id = UUID(str(sub))
        except (TypeError, ValueError):
            raise AuthError("Token não contém um identificador de usuário válido.", status_code=401)

        # Only the configured portfolio owner may use this application.
        if user_id != self.settings.owner_user_id:
            raise AuthError("Acesso restrito ao proprietário desta carteira.", status_code=403)

        return user_id


async def login_with_password(email: str, password: str) -> Dict[str, Any]:
    """Autentica o usuário diretamente na API do Supabase Auth."""
    settings = get_settings()
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": settings.supabase_publishable_key,
        "Content-Type": "application/json",
    }
    payload = {"email": email, "password": password}

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise AuthError("Falha na autenticação: credenciais inválidas.", status_code=resp.status_code)
        return resp.json()
