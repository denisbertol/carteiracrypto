# Actions: Operações e posição da carteira

> Identificador: `001-operacoes-posicao-carteira`
> Data: `2026-09-27`
> Roadmap: `_reversa_forward/001-operacoes-posicao-carteira/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 22 |
| Paralelizáveis (`[//]`) | 11 |
| Maior cadeia de dependência | 9 |

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Configurar manifesto do projeto Python com FastAPI, Uvicorn, psycopg 3 com pool, PyJWT, cryptography, pydantic, jinja2 e pytest | - | `[//]` | `pyproject.toml` | 🟡 | `[X]` |
| T002 | Criar arquivo de exemplo de variáveis de ambiente (.env.example) com configurações de PostgreSQL, Supabase Auth, porta e limites | - | `[//]` | `.env.example` | 🟢 | `[X]` |
| T003 | Implementar módulo de configuração centralizada e validação de variáveis de ambiente com Pydantic Settings | T001, T002 | - | `app/config.py` | 🟡 | `[X]` |
| T004 | Escrever script SQL de migração inicial com schema portfolio_private, tabelas, índices e políticas de RLS | - | `[//]` | `migrations/001_initial.sql` | 🟡 | `[X]` |
| T005 | Criar utilitário de execução de migrações SQL com papel administrativo dedicado | T001, T004 | - | `app/migrate.py` | 🟡 | `[X]` |
| T006 | Implementar pool de conexões psycopg 3 com suporte a transações serializadas, lock de carteira e injeção de contexto RLS | T003, T005 | - | `app/db.py` | 🟡 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existir antes ou logo após o núcleo. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T007 | Criar suíte de testes unitários para o motor contábil cobrindo os cenários de aceitação CA-01 a CA-16 | T001 | `[//]` | `tests/test_ledger.py` | 🟢 | `[X]` |
| T008 | Criar testes de integração de concorrência, idempotência e bloqueio de carteira no PostgreSQL | T006, T007 | - | `tests/test_transactions.py` | 🟡 | `[X]` |
| T009 | Criar testes de validação de autenticação Supabase Auth, verificação de JWT e aplicação de RLS | T006 | `[//]` | `tests/test_auth.py` | 🟡 | `[X]` |
| T010 | Criar testes de exportação CSV validando formato, precisão numérica e proteção contra injeção de fórmulas | T007 | `[//]` | `tests/test_exports.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central da feature. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T011 | Implementar motor contábil puro com aritmética Decimal(80), cálculo de preço médio, replay e validação de saldo não negativo | T007 | - | `app/domain/ledger.py` | 🟢 | `[X]` |
| T012 | Implementar autenticação e autorização Supabase JWT validando JWKS e checagem de sub == OWNER_USER_ID | T003, T009 | - | `app/auth.py` | 🟡 | `[X]` |
| T013 | Implementar porta QuoteReader para leitura de cotações com detecção de estado stale e fixture mock para desenvolvimento | T003 | `[//]` | `app/services/quotes.py` | 🟡 | `[X]` |
| T014 | Implementar serviço de carteira orquestrando lock de linha, validação de revisão, idempotência, replay e persistência atômica | T006, T011, T013 | - | `app/services/portfolio.py` | 🟡 | `[X]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, ganchos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T015 | Implementar rotas da API REST atendendo ao contrato HTTP (ativos, operações, ordenação e projeções) | T012, T014 | - | `app/routes/api.py` | 🟡 | `[X]` |
| T016 | Implementar serviço e rota de exportação CSV para ativos, operações e resultados com cabeçalho de revisão | T010, T014 | `[//]` | `app/routes/exports.py` | 🟢 | `[X]` |
| T017 | Construir templates HTML Jinja2 e CSS responsivo para visualização móvel da carteira e formulários de operação | T015 | - | `app/templates/index.html` | 🟡 | `[X]` |
| T018 | Configurar aplicação FastAPI agregando rotas de API, páginas web, health checks e handlers de erro | T015, T016, T017 | - | `app/main.py` | 🟡 | `[X]` |
| T019 | Criar script de população com dados sintéticos de demonstração para validação rápida local | T014 | `[//]` | `scripts/seed_demo.py` | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Logs, telemetria, mensagens de erro, documentação curta. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T020 | Criar Dockerfile multi-estágio não-root e .dockerignore para container leve pronto para Koyeb | T018 | - | `Dockerfile` | 🟡 | `[X]` |
| T021 | Configurar logging estruturado com mascaramento de dados sensíveis e auditoria de eventos | T018 | `[//]` | `app/logging.py` | 🟢 | `[X]` |
| T022 | Escrever documentação de operação e onboarding local/Koyeb com guia de migração e testes | T020 | `[//]` | `README.md` | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-27 | Versão inicial gerada por `/reversa-to-do` decompondo roadmap.md | reversa-to-do |
