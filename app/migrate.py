"""Utilitário de execução de migrações SQL."""

import os
import sys
from pathlib import Path
from app.config import get_settings


def run_migrations(dsn: str | None = None) -> None:
    settings = get_settings()
    migration_dsn = dsn or settings.migration_database_url or settings.database_url

    print("Iniciando processo de migração do banco de dados...")
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    if not migrations_dir.exists():
        print(f"Diretório de migrações não encontrado: {migrations_dir}")
        return

    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        print("Nenhum arquivo SQL de migração encontrado.")
        return

    try:
        import psycopg
    except ImportError:
        print("Driver psycopg não instalado. Para aplicar migrações, instale psycopg.")
        sys.exit(1)

    with psycopg.connect(migration_dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            # Tabela de controle de versão das migrações
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS portfolio_private;
                CREATE TABLE IF NOT EXISTS portfolio_private.schema_migrations (
                    version VARCHAR(100) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            conn.commit()

            cur.execute("SELECT version FROM portfolio_private.schema_migrations;")
            applied_versions = {row[0] for row in cur.fetchall()}

            for sql_file in sql_files:
                version = sql_file.name
                if version in applied_versions:
                    print(f"Migração já aplicada: {version}")
                    continue

                print(f"Aplicando migração: {version}...")
                sql_content = sql_file.read_text(encoding="utf-8")
                cur.execute(sql_content)
                cur.execute(
                    "INSERT INTO portfolio_private.schema_migrations (version) VALUES (%s);",
                    (version,),
                )
                conn.commit()
                print(f"Migração concluída com sucesso: {version}")

    print("Todas as migrações foram aplicadas com sucesso.")


if __name__ == "__main__":
    run_migrations()
