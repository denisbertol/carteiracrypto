-- Migration 001_initial.sql
-- Schema e estrutura inicial para carteira-crypto (portfolio_private)

CREATE SCHEMA IF NOT EXISTS portfolio_private;

-- Tabela de Carteiras
CREATE TABLE IF NOT EXISTS portfolio_private.portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_portfolio_owner UNIQUE (owner_id)
);

-- Tabela de Ativos Cadastrados
CREATE TABLE IF NOT EXISTS portfolio_private.assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    external_id VARCHAR(200) NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    name VARCHAR(120) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_assets_external UNIQUE (portfolio_id, external_id)
);

-- Tabela de Operações do Histórico
CREATE TABLE IF NOT EXISTS portfolio_private.operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES portfolio_private.assets(id),
    kind VARCHAR(20) NOT NULL CHECK (kind IN ('buy', 'sell', 'deposit', 'withdrawal', 'transfer', 'fee')),
    occurred_at TIMESTAMPTZ NOT NULL,
    order_index BIGINT NOT NULL DEFAULT 0,
    quantity NUMERIC(38, 18) NOT NULL CHECK (quantity > 0),
    unit_price_usd NUMERIC(38, 18) CHECK (unit_price_usd IS NULL OR unit_price_usd > 0),
    fee_usdt NUMERIC(38, 18) NOT NULL DEFAULT 0 CHECK (fee_usdt >= 0),
    transfer_ref VARCHAR(200),
    source_label VARCHAR(200),
    destination_label VARCHAR(200),
    note VARCHAR(2000),
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_operations_ordering 
ON portfolio_private.operations (portfolio_id, occurred_at, order_index, id) 
WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_operations_transfer_ref 
ON portfolio_private.operations (portfolio_id, transfer_ref) 
WHERE deleted_at IS NULL AND transfer_ref IS NOT NULL;

-- Projeções de Posição por Ativo
CREATE TABLE IF NOT EXISTS portfolio_private.position_projections (
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES portfolio_private.assets(id),
    quantity NUMERIC(38, 18) NOT NULL DEFAULT 0,
    remaining_cost_usd NUMERIC(38, 18) NOT NULL DEFAULT 0,
    realized_sales_usd NUMERIC(38, 18) NOT NULL DEFAULT 0,
    revision BIGINT NOT NULL,
    PRIMARY KEY (portfolio_id, asset_id)
);

-- Projeção Consolidada da Carteira
CREATE TABLE IF NOT EXISTS portfolio_private.portfolio_projection (
    portfolio_id UUID PRIMARY KEY REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    cash_usdt NUMERIC(38, 18) NOT NULL DEFAULT 0,
    deposits_usdt NUMERIC(38, 18) NOT NULL DEFAULT 0,
    withdrawals_usdt NUMERIC(38, 18) NOT NULL DEFAULT 0,
    standalone_expenses_usdt NUMERIC(38, 18) NOT NULL DEFAULT 0,
    realized_sales_usd NUMERIC(38, 18) NOT NULL DEFAULT 0,
    revision BIGINT NOT NULL
);

-- Auditoria de Operações
CREATE TABLE IF NOT EXISTS portfolio_private.operation_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    operation_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('insert', 'update', 'delete', 'reorder')),
    actor_id UUID NOT NULL,
    before_data JSONB,
    after_data JSONB,
    revision BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Recibos de Idempotência
CREATE TABLE IF NOT EXISTS portfolio_private.mutation_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    key UUID NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_status INTEGER NOT NULL,
    response_body JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mutation_receipt UNIQUE (portfolio_id, key)
);

-- Configuração de Row Level Security (RLS)
ALTER TABLE portfolio_private.portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.portfolios FORCE ROW LEVEL SECURITY;

ALTER TABLE portfolio_private.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.assets FORCE ROW LEVEL SECURITY;

ALTER TABLE portfolio_private.operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.operations FORCE ROW LEVEL SECURITY;

ALTER TABLE portfolio_private.position_projections ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.position_projections FORCE ROW LEVEL SECURITY;

ALTER TABLE portfolio_private.portfolio_projection ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.portfolio_projection FORCE ROW LEVEL SECURITY;

ALTER TABLE portfolio_private.operation_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.operation_audit FORCE ROW LEVEL SECURITY;

ALTER TABLE portfolio_private.mutation_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.mutation_receipts FORCE ROW LEVEL SECURITY;

-- Políticas de RLS baseadas em app.current_user_id
DO $$
BEGIN
    DROP POLICY IF EXISTS rls_portfolios ON portfolio_private.portfolios;
    CREATE POLICY rls_portfolios ON portfolio_private.portfolios
        USING (owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID)
        WITH CHECK (owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);

    DROP POLICY IF EXISTS rls_assets ON portfolio_private.assets;
    CREATE POLICY rls_assets ON portfolio_private.assets
        USING (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        WITH CHECK (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID));

    DROP POLICY IF EXISTS rls_operations ON portfolio_private.operations;
    CREATE POLICY rls_operations ON portfolio_private.operations
        USING (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        WITH CHECK (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID));

    DROP POLICY IF EXISTS rls_pos_proj ON portfolio_private.position_projections;
    CREATE POLICY rls_pos_proj ON portfolio_private.position_projections
        USING (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        WITH CHECK (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID));

    DROP POLICY IF EXISTS rls_port_proj ON portfolio_private.portfolio_projection;
    CREATE POLICY rls_port_proj ON portfolio_private.portfolio_projection
        USING (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        WITH CHECK (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID));

    DROP POLICY IF EXISTS rls_audit ON portfolio_private.operation_audit;
    CREATE POLICY rls_audit ON portfolio_private.operation_audit
        USING (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        WITH CHECK (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID));

    DROP POLICY IF EXISTS rls_receipts ON portfolio_private.mutation_receipts;
    CREATE POLICY rls_receipts ON portfolio_private.mutation_receipts
        USING (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        WITH CHECK (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID));
END $$;
