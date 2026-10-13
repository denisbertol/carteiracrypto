# Adendo: Alocação e rebalanceamento

> Identificador: `002-alocacao-rebalanceamento`  
> Data: `2026-09-27`  
> Cenário: `feature-forward`

---

## Vigência

Vigente desde 2026-09-27.

---

## Resumo da entrega

Implementação completa do módulo de Alocação e Rebalanceamento da carteira de criptoativos:
- Motor puro de alocação com validação de soma estrita em `100,00%` (incluindo USDT como caixa).
- Algoritmo do Maior Resto (Largest Remainder / Hamilton) para reconciliação centesimal exata sem sobras ou perdas no somatório dos valores ideais em USD.
- Versionamento e arquivamento atômico das orientações de consultoria: ativação imediata da nova recomendação e arquivamento das anteriores para auditoria e histórico.
- Endpoints REST `/api/v1/allocations`, `/api/v1/allocations/history` e exportação CSV em `/api/v1/exports/allocations.csv`.
- Painel móvel estendido com tabela comparativa de rebalanceamento e formulário de orientação de alocação.
- Script de seed demonstrativo `scripts/seed_allocation.py` com alocação inicial baseada na planilha de referência (BTC 50%, ETH 30%, USDT 20%).
- Total de 11 ações concluídas (100% do plano de ação) e 23 testes automatizados aprovados na suíte.

---

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|---|---|---|---|
| `_reversa_sdd/prd.md` | 3. Requisitos Funcionais | `modificado` | RF-09 e metas de alocação e desvios totalmente integrados. |
| `_reversa_sdd/sdd/alocacao-rebalanceamento.md` | Especificação Técnica | `componente-novo` | Motor de domínio `app/domain/allocation.py`, persistência `app/services/allocation.py` e rotas `app/routes/allocations.py`. |
| `_reversa_sdd/sdd/alocacao-rebalanceamento.md` | Modelo de Dados | `delta-de-dados` | Tabelas `allocation_targets` e `allocation_target_items` criadas em `migrations/002_allocation_targets.sql`. |
| `_reversa_sdd/sdd/painel-movel-carteira.md` | Interface Móvel | `modificado` | Tabela de rebalanceamento com badges visuais de desvio e formulário adicionados em `app/templates/index.html`. |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md` | Exportação de Dados | `modificado` | Adicionado endpoint de exportação `/api/v1/exports/allocations.csv`. |

---

## Regras sob vigilância

As regras e critérios de aceitação validados nesta entrega encontram-se registrados para vigilância de regressão em:
- [_reversa_forward/002-alocacao-rebalanceamento/regression-watch.md](file:///c:/Users/denis/Projetos/carteira-crypto/_reversa_forward/002-alocacao-rebalanceamento/regression-watch.md) (RW-002-01 a RW-002-06)

---

## Fontes

- `_reversa_forward/002-alocacao-rebalanceamento/requirements.md`
- `_reversa_forward/002-alocacao-rebalanceamento/roadmap.md`
- `_reversa_forward/002-alocacao-rebalanceamento/actions.md`
- `_reversa_forward/002-alocacao-rebalanceamento/legacy-impact.md`
- `_reversa_forward/002-alocacao-rebalanceamento/regression-watch.md`
