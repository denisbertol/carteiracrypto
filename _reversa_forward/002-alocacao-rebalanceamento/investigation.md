# Investigação Técnica: Alocação e Rebalanceamento

Data: 2026-09-27. 🟢 Decisões confirmadas e padrões arquiteturais aplicados.

---

## 1. Evidências e Análise da Planilha de Referência

A planilha de apoio do consultor (`Planilha sem título.xlsx`, aba `Página1`, intervalo `F3:M15`) apresenta a seguinte lógica de cálculo:
- Colunas:
  1. `Ativo`
  2. `Alocação sugerida (%)`
  3. `Saldo ideal (USD)` = Saldo Total * Alocação %
  4. `Valor atual (USD)` = Quantidade * Cotação
  5. `Desvio (USD)` = Saldo Ideal - Valor Atual
  6. `Desvio (%)` = (Valor Atual / Saldo Ideal) - 1
  7. `Condição` / `Aporte/Venda`

### Inconsistência corrigida:
Na planilha de exemplo, a soma das alocações dos criptoativos fechava em 100% e USDT aparecia como mais 20% (totalizando 120%). Denis confirmou explicitamente que:
- USDT representa o caixa.
- USDT **deve fazer parte dos 100,00% da recomendação**.
- O saldo total sobre o qual a posição ideal é calculada inclui o caixa em USDT e o valor a mercado dos criptos.

---

## 2. Reconciliação Centesimal (Maior Resto de Hamilton/Hare)

Quando múltiplos ativos têm percentuais com frações decimais (ex: 33,33%, 33,33%, 33,34%), a multiplicação pelo saldo total pode gerar frações de centavos.
Para evitar que a soma das posições ideais arredondadas difira do saldo total exibido:
- Usamos o método do **Maior Resto** para distribuir a eventual diferença de centavos (típica de 1 centavo) para a posição com a maior fração residual, garantindo que `sum(posicoes_ideais_usd) == saldo_total_usd` exato a nível de centavos!

---

## 3. Modelo de Versionamento

- As orientações são registradas em cabeçalho (`allocation_targets`) e itens (`allocation_target_items`).
- Apenas uma orientação tem `active = true` por `portfolio_id` a qualquer momento.
- O cadastro de uma nova versão executa uma transação que marca a anterior como `active = false` e insere a nova como `active = true`, garantindo atomicidade estrita.
