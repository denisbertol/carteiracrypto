# Regression Watch: Alocação e rebalanceamento

> Identificador: `002-alocacao-rebalanceamento`  
> Data: `2026-09-27`  
> Contexto: **Feature 002. Regras e critérios de aceitação vigiados.**

---

## 1. Regras vigiadas (Watch Principal)

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| RW-002-01 | `alocacao-rebalanceamento.md` | O somatório das metas percentuais deve totalizar rigorosamente 100,00% na criação. | Teste unitário (`test_allocation.py`) | Rejeição com erro HTTP 400 ou exceção `InvalidAllocationSumError` |
| RW-002-02 | `alocacao-rebalanceamento.md` | USDT faz parte dos 100,00% da recomendação como ativo de caixa. | Teste unitário (`test_allocation.py`) | Falta de USDT no comparativo ou divergência de saldo |
| RW-002-03 | `alocacao-rebalanceamento.md` | Nova recomendação assume vigência imediata e arquiva versão anterior. | Teste de integração (`test_allocation_api.py`) | Múltiplas orientações com `active = true` para o mesmo `portfolio_id` |
| RW-002-04 | `alocacao-rebalanceamento.md` | Soma dos valores ideais em USD é igual ao patrimônio total em centavos exatos (Maior Resto). | Teste unitário (`test_allocation.py`) | Diferença entre `sum(ideal_value_usd)` e `total_balance_usd` maior que zero |
| RW-002-05 | `alocacao-rebalanceamento.md` | Ativo com meta 0% e posição > 0 exibe ajuste negativo total. | Teste unitário (`test_allocation.py`) | Ausência do ativo no comparativo de rebalanceamento |
| RW-002-06 | `alocacao-rebalanceamento.md` | Ativo recomendado sem posição mantida exibe atual USD 0,00 e ajuste positivo total. | Teste unitário (`test_allocation.py`) | Ativo ignorado no comparativo |

---

## 2. Histórico de re-extrações

*Esta seção será preenchida automaticamente pelo agente de engenharia reversa quando `/reversa` for executado sobre o código implementado.*

---

## 3. Arquivadas

*Nenhuma regra arquivada.*

---

## 4. Observações: Critérios de Aceitação Atendidos

- **CA-01:** Validação da soma exata de 100,00% com inclusão de caixa USDT.
- **CA-02:** Ativação atômica de nova orientação e arquivamento de versões anteriores para histórico.
- **CA-03:** Algoritmo do Maior Resto para distribuição de centavos sem perdas ou excedentes numéricos.
- **CA-04:** Suporte à exibição de ativos zerados na recomendação e novos ativos sem posição na carteira.
- **CA-05:** Endpoints da API REST documentados e validados por suíte de testes automatizados.
- **CA-06:** Exportação em CSV com sanitização de fórmulas maliciosas.
