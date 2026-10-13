"""Módulo de logging estruturado e mascaramento de dados sensíveis."""

import json
import logging
import re
import sys
from typing import Any, Dict

# Padrões para mascaramento de tokens, senhas e chaves
SENSITIVE_PATTERNS = [
    (re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]+)", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"password=([^\s&;]+)", re.IGNORECASE), "password=[REDACTED]"),
    (
        re.compile(
            r'''(?ix)(["']?(?:authorization|access[_-]?token|refresh[_-]?token|api[_-]?key|apikey|x-cg-demo-api-key|coingecko_demo_api_key|service[_-]?role[_-]?key|password|secret|private[_-]?key)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;&}]+)'''
        ),
        r'\1"[REDACTED]"',
    ),
    (
        re.compile(
            r'''(?ix)(["']?(?:balance(?:_usd)?|cash(?:_usdt)?|quantity|price_usd|quote_usd|target_price(?:_usd)?|strategy|orientation)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;&}]+)'''
        ),
        r'\1"[REDACTED]"',
    ),
    (re.compile(r"postgresql://([^:]+):([^@]+)@", re.IGNORECASE), r"postgresql://\1:[REDACTED]@"),
]


def redact_sensitive_text(text: str) -> str:
    """Aplica regex de redação para mascarar tokens e credenciais em logs."""
    for pattern, repl in SENSITIVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class JsonFormatter(logging.Formatter):
    """Formatador de log estruturado JSON para observabilidade no Koyeb/Docker."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": redact_sensitive_text(record.getMessage()),
        }
        if record.exc_info:
            log_entry["exception"] = redact_sensitive_text(self.formatException(record.exc_info))
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configura o logger raiz com o formatador JSON estruturado."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("carteira_crypto")
    logger.setLevel(level)
    logger.handlers = [handler]
    logger.propagate = False
    return logger
