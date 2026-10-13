-- Migration 002_allocation_targets.sql
-- Tabelas de recomendação de alocação e percentuais de balanceamento

CREATE TABLE IF NOT EXISTS portfolio_private.allocation_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    effective_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_active_target 
ON portfolio_private.allocation_targets (portfolio_id) 
WHERE active = true;

CREATE TABLE IF NOT EXISTS portfolio_private.allocation_target_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    orientation_id UUID NOT NULL REFERENCES portfolio_private.allocation_targets(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES portfolio_private.assets(id),
    target_percent NUMERIC(5, 2) NOT NULL CHECK (target_percent >= 0 AND target_percent <= 100),
    CONSTRAINT uq_target_item UNIQUE (orientation_id, asset_id)
);

-- RLS
ALTER TABLE portfolio_private.allocation_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.allocation_targets FORCE ROW LEVEL SECURITY;

ALTER TABLE portfolio_private.allocation_target_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_private.allocation_target_items FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
    DROP POLICY IF EXISTS rls_alloc_targets ON portfolio_private.allocation_targets;
    CREATE POLICY rls_alloc_targets ON portfolio_private.allocation_targets
        USING (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        WITH CHECK (portfolio_id IN (SELECT id FROM portfolio_private.portfolios WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID));

    DROP POLICY IF EXISTS rls_alloc_items ON portfolio_private.allocation_target_items;
    CREATE POLICY rls_alloc_items ON portfolio_private.allocation_target_items
        USING (orientation_id IN (
            SELECT t.id FROM portfolio_private.allocation_targets t
            JOIN portfolio_private.portfolios p ON p.id = t.portfolio_id
            WHERE p.owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        ))
        WITH CHECK (orientation_id IN (
            SELECT t.id FROM portfolio_private.allocation_targets t
            JOIN portfolio_private.portfolios p ON p.id = t.portfolio_id
            WHERE p.owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        ));
END $$;
