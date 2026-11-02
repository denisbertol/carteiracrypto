"""Aplicação principal FastAPI carteira-crypto."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings, is_telegram_configured
from app.db import close_db_pool, get_db_connection, init_db_pool
from app.routes.api import router as api_router
from app.routes.exports import router as exports_router
from app.routes.allocations import router as allocations_router
from app.routes.monitoring import router as monitoring_router
from app.routes.dashboard import router as dashboard_router
from app.routes.history import router as history_router
from app.routes.ai import router as ai_router
from app.routes.auth import router as auth_router
from app.services.monitoring_recovery import reconcile_expired_cycles
from app.services.retention import cleanup_retained_history
from app.services.telegram_poll import telegram_polling_loop

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = logging.getLogger(__name__)


async def _maintenance_loop(owner_id, stop_event: asyncio.Event) -> None:
    """Reconcile every minute; run retention only after a successful recovery."""
    last_cleanup: datetime | None = None
    while not stop_event.is_set():
        try:
            recovery = await asyncio.to_thread(reconcile_expired_cycles, owner_id)
        except Exception:
            logger.error("monitoring maintenance failed; task=recovery")
            recovery = None
        now = datetime.now(timezone.utc)
        if recovery is not None and recovery.get("state") == "completed" and (
            last_cleanup is None or now - last_cleanup >= timedelta(hours=1)
        ):
            try:
                await asyncio.to_thread(cleanup_retained_history, owner_id)
                last_cleanup = now
            except Exception:
                logger.error("monitoring maintenance failed; task=retention")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização do pool de conexões no startup
    init_db_pool()
    stop_event = asyncio.Event()
    settings = get_settings()
    maintenance_task = asyncio.create_task(
        _maintenance_loop(settings.owner_user_id, stop_event)
    )
    telegram_task = None
    if is_telegram_configured(settings):
        telegram_task = asyncio.create_task(
            telegram_polling_loop(settings.owner_user_id, stop_event)
        )
    try:
        yield
    finally:
        stop_event.set()
        await maintenance_task
        if telegram_task:
            await telegram_task
    # Encerramento gracioso do pool de conexões no shutdown
    close_db_pool()


app = FastAPI(
    title="Carteira Crypto",
    description="Serviço pessoal para gerenciamento de carteira crypto, preço médio ponderado e posições ideais.",
    version="0.1.0",
    lifespan=lifespan,
)

# Monta arquivos estáticos
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Inclui rotas de API e exportação
app.include_router(api_router)
app.include_router(exports_router)
app.include_router(allocations_router)
app.include_router(monitoring_router)
app.include_router(dashboard_router)
app.include_router(history_router)
app.include_router(ai_router)
app.include_router(auth_router)


@app.get("/health/live", tags=["health"])
def health_live():
    """Health check de liveness (público)."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def health_ready():
    """Health check de readiness (verifica conexão com banco)."""
    settings = get_settings()
    try:
        with get_db_connection(settings.owner_user_id) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "error": "database_unavailable"},
        )


@app.get("/", response_class=HTMLResponse, tags=["web"])
def home(request: Request):
    """Serve only the public shell; authenticated clients fetch private data."""
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            # Supabase URL and publishable key are public client configuration,
            # never service-role credentials or user/session tokens.
            "supabase_url": get_settings().supabase_url.rstrip("/"),
            "supabase_publishable_key": get_settings().supabase_publishable_key,
            "google_client_id": get_settings().google_client_id,
            "dev_login": (
                {"email": get_settings().owner_email, "password": "denis123"}
                if get_settings().app_env == "development"
                else None
            ),
            "asset_version": max(
                (path.stat().st_mtime_ns for path in (BASE_DIR / "static").glob("*") if path.is_file()),
                default=0,
            ),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response
