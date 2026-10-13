# Multi-stage Dockerfile para Carteira Crypto (Otimizado para Koyeb)

# Estágio 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --user .

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

# Copia código-fonte da aplicação
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup migrations/ ./migrations/
COPY --chown=appuser:appgroup pyproject.toml ./

USER appuser

EXPOSE 8000

# Execução com 1 worker para consumo mínimo de memória (< 128 MB)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
