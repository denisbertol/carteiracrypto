# Contrato: leitura da intenção

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`
> Provedor: API Gemini (`gemini-2.5-flash`) com fallback heurístico local. A chave não sai do servidor e não volta na resposta do Telegram.

## Entrada

- texto da mensagem, ou
- áudio já obtido do Telegram, transcrito para texto antes da classificação
- catálogo de símbolos ativos da carteira
- estado do rascunho de operação em aberto (se houver)

O pedido de classificação não recebe senha, token administrativo nem conexão do banco.

## Saída

Um objeto estruturado contendo:

- `intent`: `patrimonio`, `resultado`, `lista`, `saldo`, `lancamento`, `alarme`, `cancelar`, `conversa` ou `fora_de_escopo`
- `symbol`: símbolo do ativo quando aplicável (ex: BTC, ETH)
- `kind`: tipo do lançamento (`buy`, `sell`, `deposit`, `withdrawal`, `transfer`, `fee`)
- `quantity`: quantidade numérica
- `unit_price_usd`: preço unitário em USD
- `fee_usdt`: taxa em USDT
- `occurred_at`: data da operação (se ausente no texto, usa o instante da mensagem)
- `missing_fields`: lista de campos obrigatórios que faltam para concluir a operação
- `conversational_reply`: mensagem em linguagem natural gerada para Denis quando faltarem dados ou para saudações e dúvidas gerais
- `raw_text`: texto original da mensagem

## Regras de Negócio e Diálogo

1. **Lançamentos sem dados completos:** Quando o usuário solicita registro de operação sem parâmetros (ex.: "registrar nova operação", "comprei moeda"), o sistema gera `intent: lancamento`, preenche `missing_fields` com os campos faltantes e retorna uma pergunta amigável em `conversational_reply` guiando Denis.
2. **Preenchimento progressivo:** Respostas subsequentes completam o rascunho aberto na sessão.
3. **Conversação e Dúvidas:** Saudações ou mensagens informativas geram `intent: conversa` com respostas acolhedoras e orientações de uso, sem travar o bot.
4. **Resiliência:** Se a API do Gemini falhar por rede ou cota, o fallback heurístico local assume imediatamente.
