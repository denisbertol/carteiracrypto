# Impacto Arquitetural: Alocação e rebalanceamento

> Identificador: `002-alocacao-rebalanceamento`  
> Data: `2026-09-27`  
> Política de edição: `allowLegacyEdits: true`, `allowedPaths: []` (liberação irrestrita)  
> Contexto: **Feature de alocação e rebalanceamento da carteira baseada em `_reversa_sdd/sdd/alocacao-rebalanceamento.md`.**

---

## 1. Mapeamento de arquivos criados e modificados

| Arquivo afetado | Componente (`_reversa_sdd/sdd/`) | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `migrations/002_allocation_targets.sql` | alocacao-rebalanceamento.md | `componente-novo` | HIGH | Tabelas `allocation_targets` e `allocation_target_items`, índices únicos e RLS |
| `app/domain/allocation.py` | alocacao-rebalanceamento.md | `componente-novo` | HIGH | Motor de domínio com validação de soma 100%, algoritmo de Maior Resto e cálculo de desvios |
| `app/services/allocation.py` | alocacao-rebalanceamento.md | `componente-novo` | HIGH | Serviço transacional com ativação atômica da versão vigente e arquivamento de anteriores |
| `app/routes/allocations.py` | alocacao-rebalanceamento.md | `componente-novo` | HIGH | Endpoints REST `/api/v1/allocations`, `/api/v1/allocations/history` e validação de payload |
| `app/routes/exports.py` | alocacao-rebalanceamento.md | `modificado` | LOW | Nova rota `/api/v1/exports/allocations.csv` para exportação de dados de rebalanceamento |
| `app/services/exports.py` | alocacao-rebalanceamento.md | `modificado` | LOW | Função `export_allocations_csv` com higienização contra injeção de fórmulas |
| `app/templates/index.html` | painel-movel-carteira.md | `modificado` | MEDIUM | Inclusão de tabela comparativa de rebalanceamento e formulário de orientação de alocação |
| `app/main.py` | alocacao-rebalanceamento.md | `modificado` | LOW | Registro do router de alocações na aplicação FastAPI |
| `tests/test_allocation.py` | alocacao-rebalanceamento.md | `componente-novo` | HIGH | Testes unitários do motor cobrindo CA-01 a CA-06 e reconciliação centesimal |
| `tests/test_allocation_api.py` | alocacao-rebalanceamento.md | `componente-novo` | MEDIUM | Testes de integração de endpoints de alocação e idempotência |
| `scripts/seed_allocation.py` | alocacao-rebalanceamento.md | `componente-novo` | LOW | Script utilitário para cadastrar a recomendação de alocação inicial (BTC, ETH, USDT) |
| `README.md` | alocacao-rebalanceamento.md | `modificado` | LOW | Documentação dos novos comandos, endpoints e regras de alocação |

---

## 2. Diff conceitual por componente

### Alocação e rebalanceamento (`alocacao-rebalanceamento.md`)
- **Regra de Soma Estrita:** Validação de que a soma dos percentuais recomendados atinge exatamente `100,00%`.
- **Inclusão do Caixa em USDT:** O caixa USDT é considerado explicitamente como ativo da alocação recomendada, compondo os 100,00%.
- **Vigência Imediata e Arquivamento:** Toda nova recomendação cadastrada assume vigência imediata, inativando e arquivando atômica e irreversivelmente a versão anterior para fins de histórico e auditoria.
- **Reconciliação Centesimal (Maior Resto):** A distribuição dos valores ideais em USD utiliza o método de Hamilton (Largest Remainder) para assegurar que a soma dos valores ideais coincida rigorosamente com o patrimônio total da carteira em dólares até o último centavo.
- **Transparência de Desinvestimento e Aquisição:** Ativos mantidos que recebem meta 0,00% permanecem visíveis com ajuste negativo equivalente a 100% de sua posição (desinvestimento total); ativos recomendados sem posição mantida exibem valor atual USD 0,00 e ajuste positivo (aquisição total).

### Painel móvel da carteira (`painel-movel-carteira.md`)
- Adicionada seção de rebalanceamento com badges visuais para desvios em excesso (vermelho), em falta (verde) ou alinhados (cinza neutro).

---

## 3. Preservadas
- Isolamento por `owner_user_id` e RLS na camada de dados.
- Não geração de ordens automáticas de compra/venda (a aplicação apenas exibe desvios numéricos para suporte à decisão manual externa de Denis).
- Uso incondicional de alta precisão decimal `Decimal` (80 casas decimais) sem resíduos de ponto flutuante.

---

## 4. Modificadas
*Nenhuma quebra de contrato prévio com a Feature 001. Todas as extensões foram aditivas.*
