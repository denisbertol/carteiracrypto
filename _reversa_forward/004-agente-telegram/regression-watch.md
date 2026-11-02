# Vigilância de Regressão: Agente Telegram

> Identificador: `004-agente-telegram`  
> Data: `2026-11-01`  
> Cenário: Greenfield ancorado em `prd.md` + specs SDD.

## Watch Principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|------------------------------|---------------------|-------------------|

## Observações

- **RF-01 (Linguagem Natural):** O agente responde em texto ou voz no Telegram pessoal de Denis somente após receber uma mensagem dele. Sem mensagem, o agente não envia aviso espontâneo.
- **RF-02 / RF-03 (Patrimônio e Resultado):** Retorna os totais consolidados idênticos ao painel web autenticado. Cotações ausentes geram aviso de visão parcial.
- **RF-04 / RF-05 (Lista e Saldo):** Lista os ativos cadastrados e seus saldos. Símbolo inexistente informa que não está na carteira, sem criá-lo.
- **RF-06 / RF-09 (Lançamento e Rascunho):** Data omitida usa o instante da mensagem do Telegram. Campo obrigatório faltante vira pergunta e não grava. Lançamento completo entra no ledger oficial com recálculo atômico da carteira.
- **RF-07 (Verificação de Alarme):** Consulta sob demanda de notificações não lidas e sinais Comprar/Vender (sinal Aguardar não entra). A consulta não preenche leitura (`read_at` continua intacto no painel).
- **RF-08 (Segurança e Whitelist):** Mensagem de remetente diferente da conta de Denis não expõe dados financeiros nem grava operações.
- **RF-10 (Fora de Escopo):** Não executa ordens a mercado em corretoras nem recomenda investimentos.

## Histórico de re-extrações

Nenhuma re-extração executada nesta rodada.

## Arquivadas

Nenhuma regra arquivada.

