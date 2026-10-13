# Actions: Alocação e rebalanceamento

> Identificador: `002-alocacao-rebalanceamento`  
> Data: `2026-09-27`  
> Roadmap: `_reversa_forward/002-alocacao-rebalanceamento/roadmap.md`

## Resumo

| Métrica | Valor |
|---|---|
| Total de ações | 11 |
| Paralelizáveis (`[//]`) | 5 |
| Maior cadeia de dependência | 7 |

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T001 | Escrever script de migração SQL com tabelas allocation_targets e allocation_target_items, índices únicos e RLS | - | `[//]` | `migrations/002_allocation_targets.sql` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existir antes ou logo após o núcleo. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T002 | Criar suíte de testes unitários do motor de alocação cobrindo validação de soma 100%, posições ideais e desvios (CA-01 a CA-06) | - | `[//]` | `tests/test_allocation.py` | 🟢 | `[X]` |
| T003 | Criar testes de integração da API de alocação cobrindo GET/POST /api/v1/allocations e histórico | T001, T002 | - | `tests/test_allocation_api.py` | 🟡 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central da feature. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T004 | Implementar motor de domínio puro de alocação com validação de soma 100,00%, inclusão de USDT e reconciliação centesimal | T002 | - | `app/domain/allocation.py` | 🟢 | `[X]` |
| T005 | Implementar serviço de persistência de alocação com ativação atômica da versão vigente e arquivamento da anterior | T001, T004 | - | `app/services/allocation.py` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, ganchos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T006 | Implementar rotas da API REST de alocação atendendo ao contrato HTTP (GET, POST e histórico) | T005 | - | `app/routes/allocations.py` | 🟢 | `[X]` |
| T007 | Adicionar rota de exportação CSV de alocação em exports.py e função correspondente no serviço de exportação | T005 | `[//]` | `app/routes/exports.py` | 🟢 | `[X]` |
| T008 | Integrar tabela comparativa de rebalanceamento e formulário de cadastro de nova recomendação no painel móvel | T006 | - | `app/templates/index.html` | 🟡 | `[X]` |
| T009 | Registrar o router de alocações na aplicação FastAPI principal | T006, T008 | - | `app/main.py` | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Logs, telemetria, mensagens de erro, documentação curta. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T010 | Criar script utilitário de seed para registrar a recomendação de alocação inicial baseada na planilha de referência | T005 | `[//]` | `scripts/seed_allocation.py` | 🟢 | `[X]` |
| T011 | Atualizar README.md documentando a funcionalidade de metas de alocação, endpoints e novos comandos de teste | T009 | `[//]` | `README.md` | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Versão inicial gerada por `/reversa-to-do` decompondo roadmap.md | reversa-to-do |
