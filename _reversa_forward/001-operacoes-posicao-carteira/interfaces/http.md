# Contrato HTTP da carteira — proposto

Base `/api/v1`, mesma origem da interface; HTTPS em produção. Todos os endpoints financeiros exigem `Authorization: Bearer <access_token>` validado e proprietário autorizado. IDs UUID, datas ISO 8601 com offset, decimais como strings, nunca floats JSON. Respostas financeiras `Cache-Control: no-store`; CORS fechado à origem configurada.

## Rotas

| Método e caminho | Request | Response |
|---|---|---|
| GET /assets | sem corpo | 200 {items:[{id,external_id,symbol,name,active}],revision} |
| POST /assets | {external_id,symbol,name} | 201 {asset,revision} |
| GET /operations | limit 1..100 default 50, cursor opaco opcional | 200 {items,next_cursor,revision}; cursor inclui revisão, alteração exige reiniciar paginação |
| POST /operations | operação abaixo | 201 {operation,revision} |
| PATCH /operations/{id} | campos editáveis da operação | 200 {operation,revision} |
| DELETE /operations/{id} | sem corpo | 200 {id,deleted:true,revision} |
| PUT /operations/order | {occurred_at,ordered_ids:[todos IDs ativos do instante]} | 200 {revision} |
| GET /portfolio | sem corpo | 200 {revision,positions,totals,quote_status} |
| GET /exports/{resource}.csv | resource assets/operations/results | 200 text/csv; contrato csv.md |

Operação: `{kind,asset_id,occurred_at,quantity,unit_price_usd?,fee_usdt?,transfer_ref?,source_label?,destination_label?,note?}`. kind buy/sell/deposit/withdrawal/transfer/fee. Regras de obrigatoriedade em data-delta.md. Nenhum owner_id, custo calculado ou resultado é aceito do cliente. Texto limitado: nome 120, símbolo 30, identificador 200, referência/rótulos 200, nota 2000 caracteres. Corpo máximo 64 KiB.

Toda mutação exige `Idempotency-Key: UUID` e `If-Match: "<revision>"`. O hash canônico inclui método, caminho, corpo normalizado e revisão original. Reenvio da mesma intenção mantém chave e revisão: recibo recuperado antes da validação de revisão. Nova intenção usa nova chave. Hash diferente com chave existente → 409. Resposta de replay conserva status/corpo e acrescenta Idempotency-Replayed:true. Chave não consumida em erro com rollback; cliente deve conferir estado em conflito.

Exemplo POST buy: `{"kind":"buy","asset_id":"<uuid>","occurred_at":"2026-09-01T12:00:00-03:00","quantity":"2","unit_price_usd":"100","fee_usdt":"10"}`. Retorna operação canônica com ID, order_index, timestamps UTC e revisão.

Posição: `{asset_id,quantity,remaining_cost_usd,average_price_usd,realized_sales_usd,quote_usd,quote_at,quote_source,quote_status,current_value_usd,unrealized_usd}`. Médias/valores desconhecidos null. Totais: `{cash_usdt,crypto_cost_usd,crypto_value_usd,balance_usd,cash_percent,realized_sales_usd,expenses_usd,realized_net_usd,unrealized_usd,complete}`. Preço ausente em posição positiva → totais de mercado null, complete=false; preservar totais históricos. Não somar USDT em crypto_value.

## Erros e limites

Envelope `{error:{code,message,field?,request_id}}`, sem stack trace, SQL ou secrets. 401 token ausente/inválido/expirado; 403 usuário não autorizado; 404 recurso ausente; 409 REVISION_CONFLICT/IDEMPOTENCY_CONFLICT/DUPLICATE_REFERENCE/CURSOR_STALE; 422 VALIDATION_ERROR/INSUFFICIENT_BALANCE/HISTORY_INVALID; 428 pré-condições ausentes; 503 banco indisponível/lock timeout; 504 tempo de operação excedido. Erro de histórico identifica operação ofensora apenas ao proprietário.

Pool até 3 conexões, espera 2 s; lock_timeout 2 s, statement_timeout 5 s; orçamento da requisição 10 s e cliente 15 s. Limites são propostas mensuráveis. Timeout depois de commit pode deixar resultado desconhecido para cliente: repetir mesma chave. GET pode repetir após falha; mutação nunca recebe chave nova automaticamente.

GET /health/live público retorna só {status:"ok"}; GET /health/ready retorna 200/503 sem detalhes e consulta curta de banco (1 s). Não consultar provedor de preços em health checks.
