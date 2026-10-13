# Multi-stage Dockerfile para Carteira Crypto (Otimizado para Koyeb)

# Estágio 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

COPY pyproject.toml README.md ./
COPY app/ ./app/
RUN pip install --no-cache-dir --user --no-deps .

# Estágio 2: Runtime enxuto e seguro
FROM python:3.12-slim AS runner

WORKDIR /app

# Variáveis para execução enxuta de Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    PORT=8000

# Criação de usuário não-root
RUN groupadd -g 10001 appgroup && \
    useradd -u 10000 -g appgroup -m -s /bin/bash appuser

# Copia dependências instaladas do builder
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local

# Copia código-fonte, scripts e migrações da aplicação
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup migrations/ ./migrations/
COPY --chown=appuser:appgroup scripts/ ./scripts/
COPY --chown=appuser:appgroup pyproject.toml README.md requirements.txt ./

# Permissão de execução para scripts
RUN chmod +x ./scripts/*.sh 2>/dev/null || true

USER appuser

EXPOSE 8000

# Executa migrações idempotentes e inicializa o Uvicorn
CMD ["sh", "/app/scripts/entrypoint.sh"]
