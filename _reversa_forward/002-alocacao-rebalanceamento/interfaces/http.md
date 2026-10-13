# Contrato HTTP de Alocação e Rebalanceamento

Base: `/api/v1/allocations`.  
Autenticação: Bearer JWT do proprietário.

---

## 1. Endpoints

### `GET /api/v1/allocations`
Retorna a comparação detalhada de alocação vigente da carteira.

**Resposta (200 OK):**
```json
{
  "orientation_id": "<uuid>",
  "version": 1,
  "effective_at": "2026-09-27T12:00:00Z",
  "total_balance_usd": "10000.00",
  "complete": true,
  "items": [
    {
      "asset_id": "<uuid>",
      "symbol": "BTC",
      "name": "Bitcoin",
      "target_percent": "50.00",
      "current_value_usd": "4500.00",
      "ideal_value_usd": "5000.00",
      "adjustment_usd": "500.00",
      "deviation_percent": "-10.00"
    },
    {
      "asset_id": "<uuid>",
      "symbol": "USDT",
      "name": "Tether USD",
      "target_percent": "20.00",
      "current_value_usd": "2000.00",
      "ideal_value_usd": "2000.00",
      "adjustment_usd": "0.00",
      "deviation_percent": "0.00"
    }
  ]
}
```

---

### `POST /api/v1/allocations`
Cadastra uma nova versão de recomendação de alocação.

**Request Body:**
```json
{
  "items": [
    {"asset_id": "<uuid_btc>", "target_percent": "50.00"},
    {"asset_id": "<uuid_eth>", "target_percent": "30.00"},
    {"asset_id": "<uuid_usdt>", "target_percent": "20.00"}
  ]
}
```

**Respostas:**
- `201 Created`: Orientação salva e ativada imediatamente.
- `422 Unprocessable Entity`: Se a soma dos percentuais não for exatamente 100,00%. Retorna envelope com a soma atual e a diferença faltante ou excedente.

---

### `GET /api/v1/allocations/history`
Retorna as versões anteriores das orientações para histórico e auditoria.
