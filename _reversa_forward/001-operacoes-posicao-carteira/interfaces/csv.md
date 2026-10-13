# Contrato de exportação CSV — proposto

GET `/api/v1/exports/assets.csv`, `operations.csv`, `results.csv`, autenticados conforme http.md. UTF-8, separador vírgula, aspas duplas com escape por duplicação, CRLF, `Content-Disposition: attachment`. Datas UTC ISO 8601, decimais com ponto e sem separador de milhar; não converter via float nem arredondar para duas casas os valores exportados. CSV não é backup completo do sistema.

- assets: id,external_id,symbol,name,active.
- operations: id,kind,asset_id,occurred_at,order_index,quantity,unit_price_usd,fee_usdt,transfer_ref,source_label,destination_label,note,created_at,updated_at. Apenas registros ativos; auditoria não é misturada ao histórico corrente.
- results: row_type,asset_id,revision,quantity,remaining_cost_usd,average_price_usd,realized_sales_usd,quote_usd,quote_at,quote_source,quote_status,current_value_usd,unrealized_usd,cash_usdt,expenses_usd,realized_net_usd,balance_usd,cash_percent,complete. Uma linha por posição e uma linha row_type=total; campos não aplicáveis vazios.

Snapshot consistente por arquivo. Cabeçalho X-Portfolio-Revision identifica revisão; para comparar arquivos, usuário confere mesma revisão ou repete exportação após cessar alterações. Campos textuais iniciados, após espaços, por =,+,-,@,tab ou CR são prefixados por apóstrofo contra execução de fórmulas; números gerados pelo servidor permanecem números. Indicar essa transformação no README.

Requisição de leitura idempotente, sem Idempotency-Key. Erros HTTP e timeout conforme http.md. Se streaming falhar após cabeçalhos, conexão encerra e usuário repete download; não apresentar arquivo parcial como concluído. Não armazenar arquivos exportados em diretório público.
