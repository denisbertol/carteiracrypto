# Delta de dados: Agente de consulta da carteira no Telegram

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`

Não existe modelo extraído em `_reversa_sdd/architecture.md`. O delta parte do schema `portfolio_private` já entregue nas migrações 001 a 006 e do adendo vigente da feature 001.

## O que não muda

- Ativo, operação, posição, revisão, alvo, avaliação e notificação.
- `read_at` da notificação. A consulta pelo Telegram não preenche esse campo.
- Chave de idempotência já usada em `mutation_receipts`. O lançamento vindo do Telegram continua passando por ela.

## O que entra

### Vínculo da conta

Um registro por carteira:

- identificador da carteira
- identificador da conta Telegram autorizada, gravado na primeira mensagem recebida com o bot configurado para essa carteira
- instante do vínculo

Não há lista de várias contas. Outra conta não cria vínculo.

### Rascunho de lançamento

No máximo um rascunho aberto por conta autorizada:

- tipo, ativo, quantidade, preço unitário, taxa e nota já entendidos
- campos ainda faltantes
- instante da mensagem que originou o pedido, usado como data da operação quando Denis não informar outra
- instante de atualização

O rascunho é apagado quando o lançamento é aceito ou quando Denis cancela. Não é uma operação e não entra no replay.

### Atualização aplicada

- identificador da atualização do Telegram
- instante
- resultado curto: consulta, pergunta, lançamento aceito, recusa ou falha de leitura

Serve para ignorar a mesma atualização se ela chegar de novo. Não guarda o texto financeiro completo em log.

## Migração

Uma migração nova, posterior à 006, cria somente essas três estruturas. Ela não altera linhas de operação, posição ou notificação. Aplicação repetida não duplica o vínculo.
