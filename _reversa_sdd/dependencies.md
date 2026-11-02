# Dependências — carteira-crypto

> Gerado pelo Scout em 2026-11-01. As versões são os mínimos declarados. Não há lockfile, então a versão instalada no ambiente pode ser mais nova.

## Gerenciadores

| Ferramenta | Evidência |
|---|---|
| pip | `requirements.txt`, copiado no `Dockerfile` |
| setuptools | `pyproject.toml`, `build-backend = setuptools.build_meta` |

Não há `package.json`, `poetry.lock`, `uv.lock` nem `Pipfile`.

## Runtime Python

Exigido: Python `>=3.11` (`pyproject.toml`). A imagem de produção usa `python:3.12-slim` (`Dockerfile`).

| Pacote | Mínimo | Origem | Papel |
|---|---|---|---|
| fastapi | 0.115.0 | `requirements.txt`, `pyproject.toml` | API HTTP e páginas |
| uvicorn[standard] | 0.30.0 | os dois arquivos | Servidor ASGI |
| pydantic | 2.8.0 | os dois arquivos | Modelos e validação |
| pydantic-settings | 2.4.0 | os dois arquivos | Configuração por ambiente |
| psycopg[binary,pool] | 3.2.0 | os dois arquivos | PostgreSQL |
| pyjwt[crypto] | 2.9.0 | os dois arquivos | Verificação de JWT |
| jinja2 | 3.1.4 | os dois arquivos | HTML do shell |
| python-multipart | 0.0.9 | os dois arquivos | Upload da leitura com IA |
| httpx | 0.27.0 | os dois arquivos | Clientes CoinGecko, cryptoprices e Gemini |

## Desenvolvimento

Declaradas só em `pyproject.toml`, grupo `dev`:

| Pacote | Mínimo | Papel |
|---|---|---|
| pytest | 8.3.0 | Executor opcional. Os testes atuais são classes `unittest`. |
| pytest-asyncio | 0.24.0 | Suporte assíncrono do pytest |

O teste de navegador (`tests/browser_monitoring.cjs`) é Node, sem `package.json` no projeto.

## Projeto

`pyproject.toml` nomeia o pacote `carteira-crypto`, versão `0.1.0`.
