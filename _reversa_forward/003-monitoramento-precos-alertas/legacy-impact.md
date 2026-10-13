# Impacto da entrega — monitoramento de preços e alertas

**Data:** 2026-10-03 (America/Sao_Paulo)  
**Feature:** `003-monitoramento-precos-alertas`  
**Cenário:** Feature greenfield, sem legado pré-existente. Âncora: prd.md + specs SDD.  
**Política de edição:** `allowLegacyEdits: true`; `allowedPaths: []` (edição irrestrita).

> A extração não contém `architecture.md` e `domain.md`, então a regra do `reversa-coding` classifica esta entrega como greenfield. O workspace já possuía código e adendos das features 001/002; os módulos de carteira e alocação listados abaixo foram integrados ao novo contrato, mas não há regras 🟢 da extração legada para classificar como alteradas ou preservadas.

## Arquivos e componentes

| Arquivo afetado | Componente/spec | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `app/auth.py`; `tests/test_auth.py` | Sessão Supabase e autorização (`monitoramento-precos-alertas.md`, segurança) | `componente-novo` | N/A | JWT e identidade proprietária protegem os novos endpoints. |
| `app/config.py`; `.env.example`; `tests/test_monitoring_config.py` | Configuração do provedor e quota | `componente-novo` | N/A | Modo seguro indisponível, janela da chave, limite e segredo do CoinGecko. |
| `migrations/003_price_monitoring.sql`; `tests/test_monitoring_db.py` | Entidades de ciclo, cotação, alvo, avaliação, notificação, quota e RLS | `componente-novo` | N/A | Persistência isolada por carteira e retenção. Testes de banco ainda não executados. |
| `app/domain/monitoring.py`; `tests/test_monitoring_domain.py` | Distância decimal e classificação de alvo | `componente-novo` | N/A | Fórmula e borda de proximidade sem arredondamento prematuro. |
| `app/services/coingecko.py`; `tests/test_coingecko.py` | Adaptador HTTP CoinGecko | `componente-novo` | N/A | Lotes, timeout, parse decimal e erro por ativo. |
| `app/services/provider_budget.py`; `tests/test_provider_budget.py` | Reserva compartilhada de quota | `componente-novo` | N/A | Consumo persistente, cooldown e coordenação de chamadas. |
| `app/services/price_mappings.py`; `tests/test_price_mappings.py` | Catálogo e mapeamento ativo/provedor | `componente-novo` | N/A | Cobertura explícita e preservação do identificador do ativo. |
| `app/services/price_targets.py`; `tests/test_price_targets.py` | Alvos, versões, settings, idempotência e auditoria | `componente-novo` | N/A | Múltiplos alvos e limite global versionado. |
| `app/services/monitoring.py`; `tests/test_monitoring_cycles.py`; `tests/test_monitoring_execution.py` | Reserva e execução de ciclos | `componente-novo` | N/A | Deduplicação, lease e validação de snapshot antes da gravação. |
| `app/services/monitoring_recovery.py`; `tests/test_monitoring_recovery.py` | Reconciliação de ciclos interrompidos | `componente-novo` | N/A | Recuperação no startup e a cada 60 segundos, sem HTTP externo. |
| `app/services/notifications.py`; `tests/test_notifications.py` | Histórico, exibição, leitura e ACK | `componente-novo` | N/A | Entrega identificada por notificação, paginação e expiração em 30 dias. |
| `app/services/retention.py`; `tests/test_monitoring_retention.py` | Limpeza de histórico | `componente-novo` | N/A | Lotes limitados e preservação de cotação e cadastros. Integração PostgreSQL pendente. |
| `app/services/quotes.py`; `app/services/portfolio.py`; `tests/test_quotes.py`; `tests/test_transactions.py` | Posição e cache de cotações (`operacoes-posicao-carteira.md`) | `componente-novo` | N/A | Leitura local do cache, estado de frescor e valor indicativo antigo. |
| `app/services/allocation.py`; `tests/test_allocation_api.py` | Alocação e rebalanceamento (`alocacao-rebalanceamento.md`) | `componente-novo` | N/A | Reutilização do mesmo resumo da carteira e do mesmo mapa de preços. |
| `app/services/exports.py`; `app/routes/exports.py`; `tests/test_exports.py`; `tests/test_exports_routes.py` | Exportações CSV | `componente-novo` | N/A | Snapshot individual e download autenticado pelo navegador. |
| `app/db.py`; `tests/test_dashboard_snapshot.py` | Transação de leitura `REPEATABLE READ` | `componente-novo` | N/A | Snapshot do painel protegido contra divergência entre posição e alocação. Concorrência PostgreSQL pendente. |
| `app/routes/dashboard.py`; `app/routes/monitoring.py`; `tests/test_monitoring_routes.py`; `tests/test_main_shell.py` | Contratos autenticados de painel, alvos, ciclos e notificações | `componente-novo` | N/A | Rotas autenticadas, `no-store`, paginação e controle de versão. |
| `app/main.py`; `app/templates/shell.html`; `app/templates/index.html` | Shell público e ciclo de vida do servidor (`painel-movel-carteira.md`) | `componente-novo` | N/A | Shell sem valores privados; manutenção de recuperação antes da retenção. |
| `app/static/auth.js`; `app/static/portfolio.js`; `app/static/targets.js`; `app/static/monitoring.js`; `app/static/style.css`; `tests/browser_monitoring.cjs` | Interface móvel e sessão autenticada | `componente-novo` | N/A | Login em memória, painel agregado, formulários versionados, scheduler, central e layout responsivo. Oito cenários passaram no Chrome headless com API simulada, inclusive 360 px, duas abas e lacunas de cobertura; sessão e banco reais pendentes. |
| `app/logging.py`; `tests/test_monitoring_logs.py` | Sanitização de logs | `componente-novo` | N/A | Redação de tokens, chaves, campos financeiros e texto de exceção. Dois testes de sanitização passaram em 2026-10-03. |
| `README.md` | Operação, quota, atribuição e rollback | `componente-novo` | N/A | Documentação sem segredo; detalha quota, cobertura, interrupções e rollback que mantém autenticação, com projeção de consumo corrigida. |

## Diff conceitual por componente

- **Monitoramento:** acrescenta domínio decimal, mapeamento explícito, quota persistente, ciclos deduplicados, recuperação, notificações e retenção.
- **Carteira e alocação:** passam a consumir o cache local e o snapshot autenticado; nenhuma leitura normal da carteira chama o provedor.
- **HTTP e sessão:** `/` fornece apenas configuração pública e formulário; os dados financeiros e CSVs exigem Bearer. O cliente mantém tokens apenas na memória da aba.
- **Interface:** posição e alocação carregam juntas; formulários têm versões/idempotência, o acompanhamento respeita os horários do servidor e as interrupções não fabricam alertas.
- **Operação:** a chave do provedor permanece no servidor, a atribuição é visível e o rollback desativa o provedor sem reverter a autenticação nem remover histórico.

## Preservadas

Não há regras 🟢 extraídas em `architecture.md`/`domain.md` para registrar nesta classificação greenfield. A validação contábil das features anteriores continua referenciada nos artefatos SDD e nos testes existentes.

## Modificadas

Nenhuma regra legada foi classificada como alterada/removida pela âncora greenfield. A integração com carteira e alocação está documentada como novo componente, e ainda requer a validação integrada listada em `validation.md`.

## Atualização de evidências — 2026-10-03

A implementação continua greenfield e os componentes de retenção e dashboard permanecem classificados como `componente-novo`. A execução desta rodada confirmou 8/8 cenários de navegador com API simulada e 5/5 testes puros de retenção; as verificações PostgreSQL de T018/T036, o catálogo real de T032 e os seis ciclos reais de T033 continuam pendentes. Nenhuma regra legada foi criada ou alterada por esta rodada.

## Retomada de coding — 2026-10-03

Não houve novo arquivo de produto ou mudança de classificação nesta tentativa. O Chrome repetiu 8/8 cenários simulados; PostgreSQL, sessão real, provedor e ciclos reais continuam pendentes.
