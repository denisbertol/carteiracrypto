# Roteiro de Teste e Onboarding: Alocação e Rebalanceamento

Roteiro para validação manual pós-coding da feature 002.

---

## 1. Preparação
1. Executar as migrações: `python -m app.migrate`.
2. Executar os testes automatizados: `python -m unittest discover tests`.
3. Iniciar o servidor local: `uvicorn app.main:app --reload`.

---

## 2. Roteiro de Validação Funcional

### Teste 1: Validação Estrita de Soma (Rejeição)
- Tentar cadastrar uma orientação com a soma de percentuais igual a 95%:
  - BTC: 50%
  - ETH: 30%
  - USDT: 15%
- **Resultado Esperado:** Requisição rejeitada com código 422 e mensagem clara informando que a soma é 95,00% e faltam 5,00% para 100,00%.

### Teste 2: Cadastro Válido e Cálculo da Posição Ideal
- Cadastrar orientação válida com 100%:
  - BTC: 50%
  - ETH: 30%
  - USDT: 20%
- Para uma carteira com saldo total de USD 10.000 (ex: 2.000 em caixa, 4.500 em BTC e 3.500 em ETH):
  - **Ideal BTC:** USD 5.000,00 -> **Ajuste:** +USD 500,00 (Desvio: -10,00%)
  - **Ideal ETH:** USD 3.000,00 -> **Ajuste:** -USD 500,00 (Desvio: +16,67%)
  - **Ideal USDT:** USD 2.000,00 -> **Ajuste:** USD 0,00 (Desvio: 0,00%)
- **Resultado Esperado:** Tabela de alocação no painel web exibe todas as colunas reconciliadas.

### Teste 3: Ativo Mantido com Meta Zero (Desinvestimento)
- Se a carteira possui USD 1.000 em SOL e a nova orientação não define meta para SOL (0%):
  - SOL aparece na tabela com meta de 0,00%, posição ideal de USD 0,00 e ajuste de -USD 1.000,00.

### Teste 4: Novo Ativo Recomendado sem Posição Atual (Aquisição)
- Se o consultor recomenda 10% em ADA para uma carteira sem saldo de ADA:
  - ADA aparece na tabela com atual USD 0,00, ideal de USD 1.000,00 e ajuste de +USD 1.000,00.

### Teste 5: Exportação em CSV
- Acessar `/api/v1/exports/allocations.csv` e verificar se os valores de posição ideal e desvios foram exportados sem formatação científica ou fórmulas.
