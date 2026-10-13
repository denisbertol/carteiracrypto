# Roadmap: Alocação e rebalanceamento

> Identificador: `002-alocacao-rebalanceamento`  
> Data: `2026-09-27`  
> Requirements: `_reversa_forward/002-alocacao-rebalanceamento/requirements.md`  
> Confidência: 🟢 CONFIRMADO, 🟡 PROPOSTA TÉCNICA, 🔴 BLOQUEIO

---

## 1. Resumo da abordagem

🟡 Integrar o módulo de metas de alocação e cálculo de desvios sobre o núcleo financeiro entregue na feature 001. Criar as tabelas `allocation_targets` e `allocation_target_items` no schema `portfolio_private` com Row Level Security (RLS). Implementar motor puro de cálculo de alocação (`app/domain/allocation.py`) com aritmética `Decimal(80)`, garantindo validação estrita de soma 100,00% com inclusão obrigatória de USDT/caixa. No salvamento de nova recomendação, a transação inativa atomicamente a versão anterior e ativa a nova com vigência imediata. O cálculo de alocação reconcilia a união dos ativos recomendados com os ativos mantidos em carteira e apura os ajustes em USD e desvios percentuais.

---

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|---|---|---|
| 🟢 Uso pessoal e leve | Sem processos em background contínuos; recálculo sob demanda em memória rápida | respeita |
| 🟢 Infraestrutura indicada | Tabelas adicionadas via migração versionada no PostgreSQL/Supabase com RLS | respeita |
| 🟢 Política de escrita do Reversa | Permissões ativas em `.reversa/reversa-config.json` | respeita |

---

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|---|---|---|---|---|
| D-01 | Armazenar metas em tabelas versionadas (`allocation_targets` e `allocation_target_items`) | Preservar histórico imutável das orientações anteriores para auditoria | Sobrescrever metas em coluna de ativo | 🟢 |
| D-02 | Validação de soma 100,00% na aplicação e restrição transacional | Rejeitar inputs inválidos antes de tocar no estado ativo da carteira | Permitir somas aproximadas | 🟢 |
| D-03 | Inclusão de USDT nos 100,00% da recomendação | Manter reconciliação exata com o saldo total em caixa | Caixa tratado como reserva à parte | 🟢 |
| D-04 | Cálculo de união dos ativos recomendados + ativos mantidos | Ativos com meta zero recebem ajuste negativo (venda) e novos ativos recebem ajuste positivo (compra) | Ocultar ativos da carteira sem meta | 🟢 |
| D-05 | Reconciliação visual com tolerância de até USD 0,01 | Arredondamento centesimal determinístico na exibição | Truncamento cego gerando centavos fantasmas | 🟡 |
| D-06 | Endpoints `/api/v1/allocations` e exportação `/allocations.csv` | Acesso transparente aos dados tanto pela interface quanto para conferência offline | Misturar com endpoint de operações | 🟢 |

---

## 4. Premissas

- O saldo total em USD e o saldo em caixa USDT continuam sendo providos de forma atômica pelo `PortfolioService` da feature 001.
- Se algum ativo mantido estiver com cotação indisponível, a visualização de alocação sinaliza status incompleto, sem apresentar valores ideais distorcidos.

---

## 5. Delta arquitetural

| Componente | Arquivo de origem | Tipo | Resumo |
|---|---|---|---|
| Alocação e rebalanceamento | `_reversa_sdd/sdd/alocacao-rebalanceamento.md` | componente-novo | Motor de alocação, serviço de banco, versionamento de orientações e rotas REST/CSV |
| Painel móvel da carteira | `_reversa_sdd/sdd/painel-movel-carteira.md` | componente-alterado | Adição da tabela de alocação sugerida e modal de cadastro de nova orientação |

Arquivos previstos para criação/modificação:
- Criação: `migrations/002_allocation_targets.sql`, `app/domain/allocation.py`, `app/services/allocation.py`, `app/routes/allocations.py`, `tests/test_allocation.py`
- Modificação: `app/main.py` (registro do router de alocação), `app/templates/index.html` (tabela de rebalanceamento e formulário)

---

## 6. Delta no modelo de dados

Adicionar ao schema `portfolio_private`:
- Tabela `allocation_targets` (orientações versionadas)
- Tabela `allocation_target_items` (percentuais por ativo)
- RLS forçada e políticas associadas ao proprietário. Detalhes em `data-delta.md`.

---

## 7. Delta de contratos externos

- HTTP: `interfaces/http.md` (rotas `GET /api/v1/allocations`, `POST /api/v1/allocations`, `GET /api/v1/allocations/history`)
- CSV: `interfaces/csv.md` (rota `GET /api/v1/exports/allocations.csv`)

---

## 8. Plano de migração

1. Aplicar migração `002_allocation_targets.sql` via runner `python -m app.migrate`.
2. Validar que o ativo USDT é referenciável como item de alocação.
3. Cadastrar a orientação inicial baseada na planilha de referência (`Planilha sem título.xlsx`) com os percentuais ajustados para fechar 100,00% com USDT.

---

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|---|---|---|---|
| Soma dos percentuais não fechar 100% | Médio | Média | Validação estrita rejeita o cadastro e informa a diferença exata |
| Discrepância de arredondamento de centavos | Baixo | Média | Algoritmo determinístico de distribuição de resíduos centesimais (máx USD 0,01) |
| Cotações desatualizadas falseando alocação | Médio | Baixa | Status visual de incomplete/stale bloqueia suposições incorretas |

---

## 10. Critério de pronto

- [ ] Migração SQL criada e aplicada sem erros.
- [ ] Testes unitários do motor de alocação cobrindo CA-01 a CA-06 com 100% de sucesso.
- [ ] Validação estrita de soma 100,00% funcionando nos endpoints REST.
- [ ] Tabela comparativa e modal de recomendação integrados ao painel web.
- [ ] Exportação CSV disponível e higienizada contra injeção de fórmulas.
- [ ] Onboarding executado e validado com sucesso.

---

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Plano inicial da feature 002 | reversa-plan |
