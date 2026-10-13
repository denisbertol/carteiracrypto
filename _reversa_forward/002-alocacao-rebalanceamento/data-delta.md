# Delta de Dados: Alocação e Rebalanceamento

Schema afetado: `portfolio_private`.  
Migração: `migrations/002_allocation_targets.sql`.

---

## 1. Novas Tabelas

### `portfolio_private.allocation_targets`
Armazena o cabeçalho de cada versão de recomendação de alocação.

| Campo | Tipo | Restrições | Descrição |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Identificador da orientação |
| `portfolio_id` | `UUID` | `NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE` | Carteira associada |
| `version` | `INTEGER` | `NOT NULL DEFAULT 1` | Número sequencial da versão |
| `effective_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | Início da vigência |
| `active` | `BOOLEAN` | `NOT NULL DEFAULT true` | Flag indicando se é a versão vigente |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | Data de criação do registro |

Índices e Restrições:
- `CREATE UNIQUE INDEX uq_portfolio_active_target ON portfolio_private.allocation_targets (portfolio_id) WHERE active = true;` (Garante que só há uma versão vigente por carteira).

---

### `portfolio_private.allocation_target_items`
Armazena os percentuais recomendados por ativo para uma dada orientação.

| Campo | Tipo | Restrições | Descrição |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Identificador do item |
| `orientation_id` | `UUID` | `NOT NULL REFERENCES allocation_targets(id) ON DELETE CASCADE` | Orientação pai |
| `asset_id` | `UUID` | `NOT NULL REFERENCES assets(id)` | Ativo alvo (incluindo USDT) |
| `target_percent` | `NUMERIC(5, 2)` | `NOT NULL CHECK (target_percent >= 0 AND target_percent <= 100)` | Percentual sugerido (0.00 a 100.00) |

Índices e Restrições:
- `CONSTRAINT uq_target_item UNIQUE (orientation_id, asset_id)` (Impede ativo duplicado na mesma orientação).

---

## 2. Row Level Security (RLS)

- Habilitar e forçar RLS em `allocation_targets` e `allocation_target_items`.
- Políticas verificando `owner_id` da carteira contra `app.current_user_id` da sessão local.
