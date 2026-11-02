# Investigação: Agente de consulta da carteira no Telegram

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`

## O que já existe

- O painel calcula patrimônio em `balance_usd` e resultado como ganho não realizado mais realizado líquido. Cotação incompleta deixa o total parcial. Fonte: `app/services/portfolio.py` e `app/static/portfolio.js`.
- O lançamento novo entra por `POST /api/v1/operations`, com chave de idempotência obrigatória e os tipos compra, venda, depósito, saque, transferência e taxa. Fonte: `app/routes/api.py`.
- O sinal Comprar, Vender ou Aguardar está na interface: Vender se o preço atinge o dobro do preço médio; Comprar se a participação está abaixo da ideal e o preço está no alvo de compra. Fonte: `app/static/portfolio.js`.
- Notificação de monitoramento guarda `read_at`. Fonte: `app/services/notifications.py`.
- A leitura com Gemini já existe para lançamentos e alvos do painel, com chave só no servidor. Fonte: `app/services/ai_import.py` e o adendo da feature 003.
- O cliente HTTP já usado para provedores externos é o httpx. Fonte: `_reversa_sdd/dependencies.md`.
- Não há cliente de Telegram no repositório. Fonte: `_reversa_sdd/inventory.md#integrações-externas`.

## Alternativas

| Caminho | Por que não |
|---------|-------------|
| Comandos fixos (`/patrimonio`, `/saldo`) | Denis escolheu linguagem natural, em texto ou voz. |
| Aviso espontâneo no Telegram | Denis escolheu resposta somente após mensagem. |
| Gravar o lançamento assim que a frase chegar | Campo faltante, exceto data e hora, precisa virar pergunta. |
| Marcar a notificação como lida ao responder | O pedido é devolver o alarme, não dispensá-lo no painel. |
| Novo fornecedor de fala | A carteira já tem leitura de material livre. Um segundo fornecedor aumenta segredo e falha sem mudar a regra. |
| Webhook obrigatório | Exige endereço público estável também no uso local. A busca com trava única atende o processo único já usado. |

## Padrão aplicado

O agente é um adaptador. Ele traduz a conversa para operações que o ledger, o snapshot e as notificações já sabem fazer. A regra financeira não muda de lugar.

## Fontes externas

- Bot API do Telegram, métodos de busca de atualização, envio de mensagem e obtenção de arquivo de voz: https://core.telegram.org/bots/api
- A leitura de intenção reutiliza o contrato já documentado em `interfaces/intencao.md`, sobre o mesmo provedor da leitura atual da carteira.
