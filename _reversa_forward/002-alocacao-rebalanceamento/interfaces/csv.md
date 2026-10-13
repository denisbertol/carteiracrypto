# Contrato CSV de Alocação e Rebalanceamento

Rota: `GET /api/v1/exports/allocations.csv`  
Autenticação: Bearer JWT do proprietário.

---

## Estrutura do Arquivo

- **Encoding:** UTF-8
- **Delimitador:** Vírgula (`,`)
- **Quebra de linha:** CRLF (`\r\n`)
- **Headers:** `Content-Disposition: attachment; filename="allocations.csv"`, `X-Allocation-Version: <version>`

### Colunas:
`symbol,name,target_percent,current_value_usd,ideal_value_usd,adjustment_usd,deviation_percent`

Proteção contra injeção de fórmulas habilitada em todos os campos de texto.
