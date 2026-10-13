"""Módulo de autenticação e autorização nativa JWT e Google OAuth."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID
import httpx

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


def _get_secret() -> str:
    settings = get_settings()
    sec = settings.secret_key
    return sec.get_secret_value() if hasattr(sec, "get_secret_value") else str(sec)


def create_access_token(user_id: UUID, email: str, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=24))
    payload = {
        "sub": str(user_id),
        "email": email,
        "aud": "carteira-crypto",
        "iss": "carteira-crypto",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _get_secret(), algorithm="HS256")


def create_refresh_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=30))
    payload = {
        "sub": str(user_id),
        "aud": "carteira-crypto",
        "iss": "carteira-crypto",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_secret(), algorithm="HS256")


class TokenVerifier:
    """Validador de JWT nativo (HS256) e fallback Supabase (RS256/ES256)."""

    SUPPORTED_ALGORITHMS = ("HS256", "RS256", "ES256")

    def __init__(self, jwks_client: Optional[Any] = None) -> None:
        self.settings = get_settings()
        self.jwks_url = f"{self.settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
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

        try:
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg")
        except Exception:
            raise AuthError("Token JWT malformado.", status_code=401)

        if alg not in self.SUPPORTED_ALGORITHMS:
            raise AuthError("Algoritmo de assinatura JWT não permitido.", status_code=401)

        # 1. Validação de token nativo (HS256 com SECRET_KEY)
        if alg == "HS256":
            secret = _get_secret()
            try:
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience="carteira-crypto",
                    issuer="carteira-crypto",
                    options={"require": ["exp", "sub", "iss", "aud"]},
                )
            except jwt.ExpiredSignatureError:
                raise AuthError("Token expirado. Efetue login novamente.", status_code=401)
            except jwt.InvalidTokenError:
                raise AuthError("Token inválido.", status_code=401)

            if payload.get("type") != "access":
                raise AuthError("Tipo de token inválido para autorização.", status_code=401)

            sub = payload.get("sub")
            try:
                user_id = UUID(str(sub))
            except (TypeError, ValueError):
                raise AuthError("Token não contém um identificador de usuário válido.", status_code=401)

            if user_id != self.settings.owner_user_id:
                raise AuthError("Acesso restrito ao proprietário desta carteira.", status_code=403)

            return user_id

        # 2. Fallback: Validação via Supabase JWKS (RS256 / ES256)
        try:
            if self.jwks_client is None:
                raise AuthError("Verificador JWKS indisponível.", status_code=503)
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
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
            raise AuthError("Não foi possível validar a assinatura JWT.", status_code=503)

        sub = payload.get("sub")
        try:
            user_id = UUID(str(sub))
        except (TypeError, ValueError):
            raise AuthError("Token não contém um identificador de usuário válido.", status_code=401)

        if user_id != self.settings.owner_user_id:
            raise AuthError("Acesso restrito ao proprietário desta carteira.", status_code=403)

        return user_id


def authenticate_with_password(email: str, password: str) -> Dict[str, Any]:
    """Autentica o usuário pelo e-mail e senha cadastrados no sistema."""
    settings = get_settings()
    owner_pwd = (
        settings.owner_password.get_secret_value()
        if hasattr(settings.owner_password, "get_secret_value")
        else str(settings.owner_password)
    )
    if not email or not password:
        raise AuthError("E-mail e senha são obrigatórios.", status_code=400)

    if email.strip().lower() != settings.owner_email.strip().lower() or password != owner_pwd:
        raise AuthError("Credenciais inválidas.", status_code=401)

    access_token = create_access_token(settings.owner_user_id, settings.owner_email)
    refresh_token = create_refresh_token(settings.owner_user_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 86400,
        "user": {
            "id": str(settings.owner_user_id),
            "email": settings.owner_email,
        },
    }


async def authenticate_with_google(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Troca o authorization code diretamente com o Google OAuth sem intermediários."""
    settings = get_settings()
    client_id = settings.google_client_id
    client_secret = (
        settings.google_client_secret.get_secret_value()
        if hasattr(settings.google_client_secret, "get_secret_value")
        else str(settings.google_client_secret)
    )
    if not client_id or not client_secret:
        raise AuthError(
            "Google OAuth não configurado no servidor. Defina GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET.",
            status_code=500,
        )

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(token_url, data=token_data)
        if resp.status_code != 200:
            error_msg = "Falha ao validar código com o Google."
            try:
                err_json = resp.json()
                if "error_description" in err_json:
                    error_msg = f"Google OAuth: {err_json['error_description']}"
            except Exception:
                pass
            raise AuthError(error_msg, status_code=400)

        token_res = resp.json()
        google_access_token = token_res.get("access_token")

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {google_access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise AuthError("Não foi possível obter os dados da conta Google.", status_code=400)

        userinfo = userinfo_resp.json()

    user_email = userinfo.get("email", "").strip().lower()
    if not user_email:
        raise AuthError("E-mail não fornecido pelo Google.", status_code=400)

    if user_email != settings.owner_email.strip().lower():
        raise AuthError(
            f"Acesso negado: a conta Google '{user_email}' não é a proprietária autorizada desta carteira.",
            status_code=403,
        )

    access_token = create_access_token(settings.owner_user_id, user_email)
    refresh_token = create_refresh_token(settings.owner_user_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 86400,
        "user": {
            "id": str(settings.owner_user_id),
            "email": user_email,
            "name": userinfo.get("name"),
            "picture": userinfo.get("picture"),
        },
    }


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Gera um novo access_token a partir de um refresh_token válido."""
    settings = get_settings()
    secret = _get_secret()
    try:
        payload = jwt.decode(
            refresh_token,
            secret,
            algorithms=["HS256"],
            audience="carteira-crypto",
            issuer="carteira-crypto",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Sessão expirada. Efetue login novamente.", status_code=401)
    except jwt.InvalidTokenError:
        raise AuthError("Refresh token inválido.", status_code=401)

    if payload.get("type") != "refresh":
        raise AuthError("Token fornecido não é um refresh token.", status_code=401)

    sub = payload.get("sub")
    try:
        user_id = UUID(str(sub))
    except (TypeError, ValueError):
        raise AuthError("Token não contém um identificador válido.", status_code=401)

    if user_id != settings.owner_user_id:
        raise AuthError("Acesso restrito ao proprietário desta carteira.", status_code=403)

    new_access_token = create_access_token(settings.owner_user_id, settings.owner_email)
    new_refresh_token = create_refresh_token(settings.owner_user_id)
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "expires_in": 86400,
    }


async def login_with_password(email: str, password: str) -> Dict[str, Any]:
    """Mantido para compatibilidade com chamadas legado."""
    return authenticate_with_password(email, password)
