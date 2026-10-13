"""Rotas de autenticação nativa (Google OAuth e Senha)."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.auth import (
    AuthError,
    authenticate_with_password,
    authenticate_with_google,
    refresh_access_token,
)
from app.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginInput(BaseModel):
    email: str
    password: str


class GoogleAuthInput(BaseModel):
    code: str
    redirect_uri: str


class RefreshInput(BaseModel):
    refresh_token: str


@router.get("/google/url")
def get_google_auth_url(redirect_uri: str = Query(...)):
    """Retorna a URL oficial de consentimento do Google OAuth."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": "GOOGLE_CLIENT_ID não configurado no servidor."}},
        )
    params = [
        ("client_id", settings.google_client_id),
        ("redirect_uri", redirect_uri),
        ("response_type", "code"),
        ("scope", "openid email profile"),
        ("access_type", "online"),
        ("prompt", "select_account"),
    ]
    query = "&".join(f"{k}={v}" for k, v in params)
    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}"}


@router.post("/login")
def login(body: LoginInput, response: Response):
    """Login com e-mail e senha do proprietário."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return authenticate_with_password(body.email, body.password)
    except AuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": {"code": "AUTH_FAILED", "message": str(e)}},
        )


@router.post("/google")
async def google_login(body: GoogleAuthInput, response: Response):
    """Valida o código de autorização diretamente com o Google."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return await authenticate_with_google(body.code, body.redirect_uri)
    except AuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": {"code": "AUTH_FAILED", "message": str(e)}},
        )


@router.post("/refresh")
def refresh(body: RefreshInput, response: Response):
    """Atualiza o access_token utilizando o refresh_token nativo."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return refresh_access_token(body.refresh_token)
    except AuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": {"code": "AUTH_FAILED", "message": str(e)}},
        )
