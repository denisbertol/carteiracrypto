# Inventário — carteira-crypto

> Gerado pelo Scout em 2026-11-01. Contagem da aplicação, sem `.agents/`, `.reversa/`, `_reversa_sdd/`, `_reversa_forward/` e caches.

## Superfície

Aplicação web pessoal de carteira crypto. O servidor é Python (FastAPI). O navegador recebe um shell HTML e scripts estáticos. O estado fica em PostgreSQL.

Arquivos de produto contados: 108. Linguagem principal: Python (63 arquivos `.py`).

| Extensão | Arquivos | Papel |
|---|---|---|
| `.py` | 63 | Servidor, domínio, testes e scripts |
| `.js` | 8 | Interface no navegador |
| `.sql` | 6 | Migrações |
| `.svg` | 12 | Ícones de ativos |
| `.html` | 2 | Shell da página |
| `.css` | 1 | Estilo |
| `.cjs` | 1 | Teste de navegador |
| `.png` | 1 | Ícone da aplicação |
| `.mp4` | 1 | Vídeo de abertura |

Há também a árvore do framework Reversa (`.agents/`, `.reversa/`, `_reversa_forward/`, `_reversa_sdd/`). Ela não faz parte do runtime da carteira.

## Árvore da aplicação

```
app/
  main.py                 entrada FastAPI, manutenção e página inicial
  config.py               configuração e segredos
  auth.py                 verificação do token
  db.py                   pool PostgreSQL
  logging.py
  migrate.py              aplicação das migrações
  domain/
    ledger.py             lançamentos e posição
    allocation.py         alocação
    monitoring.py         alvos e distância
  routes/
    api.py                carteira e lançamentos
    auth.py               sessão
    allocations.py        alocação
    monitoring.py         alvos, ciclos e notificações
    dashboard.py          painel agregado
    history.py            evolução
    exports.py            CSV
    ai.py                 leitura com Gemini
  services/               regras de aplicação e clientes externos
  templates/
    index.html
    shell.html
  static/                 scripts, estilo, ícones, ícone e vídeo de abertura
migrations/               001 a 006
scripts/
  entrypoint.sh
  seed_demo.py
  seed_holdings.py
  seed_allocation.py
tests/                    28 módulos test_*.py e browser_monitoring.cjs
```

## Módulos identificados

| Módulo | Onde está |
|---|---|
| auth | `app/auth.py`, `app/routes/auth.py`, `app/static/auth.js` |
| ledger | `app/domain/ledger.py`, `app/routes/api.py`, `app/services/portfolio.py`, `app/static/operations.js` |
| allocation | `app/domain/allocation.py`, `app/routes/allocations.py`, `app/services/allocation.py` |
| monitoring | `app/domain/monitoring.py`, `app/routes/monitoring.py`, serviços de cotação, ciclo, notificação e retenção, `app/static/monitoring.js`, `app/static/targets.js` |
| history | `app/routes/history.py`, `app/services/price_history.py` |
| ai | `app/routes/ai.py`, `app/services/ai_import.py`, `app/static/ai.js` |
| exports | `app/routes/exports.py`, `app/services/exports.py` |
| painel | `app/routes/dashboard.py`, `app/templates/`, `app/static/portfolio.js`, `app/static/charts.js`, `app/static/splash.js` |

## Pontos de entrada

| Caminho | Tipo |
|---|---|
| `app/main.py` | Aplicação FastAPI. Monta `/static`, inclui os oito routers e serve `GET /`. |
| `scripts/entrypoint.sh` | Comando do container: migra e sobe o Uvicorn. |
| `app/migrate.py` | Runner das migrações SQL. |

Routers incluídos em `app/main.py`: carteira (`/api/v1`), exportação, alocação, monitoramento, dashboard, histórico, IA e autenticação.

## Configuração

- `.env.example` — variáveis públicas de exemplo. O `.env` real não entra no inventário.
- `app/config.py` — leitura da configuração. `QUOTE_MODE` aceita `unavailable`, `coingecko`, `cryptoprices`, `fixture` e `mock_stale`.
- `pyproject.toml` e `requirements.txt` — dependências.
- `Dockerfile` — imagem Python 3.12, usuário não-root, porta 8000. Não há `docker-compose.yml`.
- Não há workflow em `.github/workflows/`, nem `Jenkinsfile`, nem `.gitlab-ci.yml`.

## Banco de dados

Migrações SQL em `migrations/`, aplicadas em ordem:

1. `001_initial.sql`
2. `002_allocation_targets.sql`
3. `003_price_monitoring.sql`
4. `004_price_history.sql`
5. `005_column_preferences.sql`
6. `006_ai_settings.sql`

O cliente é psycopg 3, com pool. A análise detalhada do esquema fica com o Data Master.

## Testes

- 28 arquivos `tests/test_*.py`. O código de teste usa `unittest`. O `pyproject.toml` também declara pytest como dependência opcional de desenvolvimento.
- 1 script de navegador: `tests/browser_monitoring.cjs`.
- Não há relatório de cobertura no repositório. A estimativa é a contagem de arquivos, não um percentual.

## Integrações externas

| Integração | Uso |
|---|---|
| PostgreSQL / Supabase | Dados da carteira e autenticação |
| Google OAuth | Configurado em `.env.example` e `app/config.py` |
| CoinGecko | Cotações e histórico, quando `QUOTE_MODE=coingecko` |
| cryptoprices.cc | Cotação ao vivo, quando `QUOTE_MODE=cryptoprices` |
| Gemini | Leitura de lançamentos e alvos a partir de texto, CSV ou imagem |
