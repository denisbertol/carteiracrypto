"""Módulo de conexão e gerenciamento do PostgreSQL com pool psycopg 3 e RLS."""

from contextlib import contextmanager
from typing import Generator, Any
from uuid import UUID
from app.config import get_settings

try:
    import psycopg
    from psycopg_pool import ConnectionPool
except ImportError:
    psycopg = None  # type: ignore
    ConnectionPool = None  # type: ignore

_pool: Any = None


def init_db_pool() -> Any:
    """Inicializa o pool de conexões psycopg 3."""
    global _pool
    if _pool is not None:
        return _pool

    if ConnectionPool is None:
        return None

    settings = get_settings()
    _pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        timeout=settings.pool_timeout_seconds,
        open=True,
    )
    return _pool


def close_db_pool() -> None:
    """Fecha o pool de conexões de forma graciosa."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_db_connection(
    user_id: UUID | None = None,
    *,
    isolation_level: str | None = None,
    read_only: bool = False,
) -> Generator[Any, None, None]:
    """
    Obtém uma conexão do pool configurada com timeouts e contexto RLS.
    Injeta o app.current_user_id como variável de sessão local da transação.
    """
    settings = get_settings()
    pool = init_db_pool()

    if pool is None:
        raise RuntimeError("Driver psycopg ou psycopg_pool não está disponível.")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            if isolation_level is not None and isolation_level.upper() not in {
                "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"
            }:
                raise ValueError("Nível de isolamento inválido.")
            if isolation_level is not None or read_only:
                mode = f" ISOLATION LEVEL {isolation_level.upper()}" if isolation_level else ""
                mode += " READ ONLY" if read_only else ""
                cur.execute("SET TRANSACTION" + mode + ";")
            # Configura timeouts para defesa contra contenção
            lock_ms = int(settings.lock_timeout_seconds * 1000)
            stmt_ms = int(settings.statement_timeout_seconds * 1000)
            cur.execute(f"SET lock_timeout = '{lock_ms}ms';")
            cur.execute(f"SET statement_timeout = '{stmt_ms}ms';")

            # Injeta identidade para Row Level Security
            if user_id is not None:
                cur.execute("SELECT set_config('app.current_user_id', %s, true);", (str(user_id),))

        yield conn


def lock_portfolio_for_update(cur: Any, portfolio_id: UUID) -> tuple[UUID, int]:
    """
    Adquire lock exclusivo na linha da carteira para serializar mutações.
    Retorna (portfolio_id, revision atual).
    """
    cur.execute(
        """
        SELECT id, revision 
        FROM portfolio_private.portfolios 
        WHERE id = %s 
        FOR UPDATE;
        """,
        (str(portfolio_id),),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Carteira não encontrada para ID: {portfolio_id}")
    return UUID(str(row[0])), int(row[1])
