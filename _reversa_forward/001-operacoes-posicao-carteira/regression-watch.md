# Regression Watch: Operações e posição da carteira

> Identificador: `001-operacoes-posicao-carteira`  
> Data: `2026-09-27`  
> Contexto: **Feature greenfield. Sem regras legadas pré-existentes.**

---

## 1. Regras vigiadas (Watch Principal)

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| - | - | *Nenhuma regra legada sob vigilância direta nesta entrega inicial.* | - | - |

---

## 2. Histórico de re-extrações

*Esta seção será preenchida automaticamente pelo agente de engenharia reversa quando `/reversa` for executado sobre o código implementado.*

---

## 3. Arquivadas

*Nenhuma regra arquivada.*

---

## 4. Observações: Requisitos Funcionais Implementados

Os requisitos abaixo foram entregues nesta feature e passarão a constituir as regras vigiadas de regressão (🟢) após a primeira extração formal:

- **RF-01:** Cadastro e ativação de ativos cripto com símbolos e identificadores únicos.
- **RF-02:** Registro de operações atômicas nos tipos `buy`, `sell`, `deposit`, `withdrawal`, `transfer` e `fee`.
- **RF-03:** Cálculo contínuo do preço médio ponderado nas compras com acréscimo de taxas em USDT ao custo.
- **RF-04:** Apuração de lucros e perdas realizados nas vendas com baixa proporcional de custo e zeramento no encerramento de posição.
- **RF-05:** Dedução de taxas avulsas e taxas de transferência como despesas realizadas da carteira em USDT.
- **RF-06:** Transferência entre locais próprios sem alteração de saldo global ou de custo contábil da posição.
- **RF-07:** Ordenação temporal estrita por data/hora e desempate por ordem sequencial de cadastro ajustável.
- **RF-08:** Validação estrita de saldo não negativo para caixa e posições de ativos com rejeição de déficits.
- **RF-09:** Projeção consolidada de saldo total em USD, caixa USDT e resultado a mercado não realizado.
- **RF-10:** Histórico auditável de operações e idempotência nas requisições de mutação.
- **RF-11:** Exportação de dados em CSV higienizado contra formula injection.
- **RF-12:** Autenticação e isolamento de acesso via Supabase Auth e RLS no PostgreSQL.
