#!/bin/sh
set -e

echo "=== Iniciando Carteira Crypto ==="

# Executa migrações de forma idempotente se RUN_MIGRATIONS não for 'false'
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Verificando e aplicando migrações do banco de dados (app.migrate)..."
    python -m app.migrate || echo "Aviso: Migrações automáticas não puderam ser concluídas no startup. Prosseguindo..."
fi

echo "Iniciando Uvicorn na porta ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
