-- Feature 003: monitoring, price cache, targets, notifications, and provider budget.
-- This migration is additive and safe to apply repeatedly.

CREATE SCHEMA IF NOT EXISTS portfolio_private;

-- A composite key lets every monitoring row prove that its asset belongs to
-- the same portfolio, rather than merely referencing an asset UUID.
CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_portfolio_id_id
    ON portfolio_private.assets (portfolio_id, id);

CREATE TABLE IF NOT EXISTS portfolio_private.monitoring_settings (
    portfolio_id UUID PRIMARY KEY
        REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    proximity_percent NUMERIC(5, 2) NOT NULL DEFAULT 10.00
        CHECK (proximity_percent >= 0 AND proximity_percent <= 100),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS portfolio_private.asset_price_mappings (
    portfolio_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    provider VARCHAR(40) NOT NULL DEFAULT 'coingecko',
    provider_coin_id VARCHAR(200),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'valid', 'unsupported')),
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (portfolio_id, asset_id),
    FOREIGN KEY (portfolio_id, asset_id)
        REFERENCES portfolio_private.assets (portfolio_id, id) ON DELETE CASCADE,
    CHECK (status <> 'valid' OR NULLIF(btrim(provider_coin_id), '') IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS portfolio_private.price_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    kind VARCHAR(10) NOT NULL CHECK (kind IN ('buy', 'sell')),
    price_usd NUMERIC(38, 18) NOT NULL
        CHECK (price_usd > 0 AND price_usd < 'Infinity'::numeric),
    active BOOLEAN NOT NULL DEFAULT true,
    orientation VARCHAR(1000),
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (portfolio_id, id),
    FOREIGN KEY (portfolio_id, asset_id)
        REFERENCES portfolio_private.assets (portfolio_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_targets_active
    ON portfolio_private.price_targets (portfolio_id, asset_id, active, id);

CREATE TABLE IF NOT EXISTS portfolio_private.monitoring_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL
        REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    entity_kind VARCHAR(20) NOT NULL
        CHECK (entity_kind IN ('settings', 'target', 'mapping')),
    entity_id UUID NOT NULL,
    old_value JSONB,
    new_value JSONB,
    actor_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (portfolio_id, id)
);

CREATE INDEX IF NOT EXISTS idx_monitoring_changes_history
    ON portfolio_private.monitoring_changes (portfolio_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS portfolio_private.monitoring_cycles (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL
        REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved', 'running', 'completed', 'partial', 'failed')),
    lease_token UUID NOT NULL DEFAULT gen_random_uuid(),
    error_code VARCHAR(80),
    settings_revision BIGINT NOT NULL DEFAULT 1 CHECK (settings_revision > 0),
    provider_key_fingerprint CHAR(64),
    reserved_request_count INTEGER NOT NULL DEFAULT 0 CHECK (reserved_request_count >= 0),
    provider_window_start TIMESTAMPTZ,
    provider_window_end TIMESTAMPTZ,
    provider_call_limit INTEGER CHECK (provider_call_limit IS NULL OR provider_call_limit > 0),
    PRIMARY KEY (id),
    UNIQUE (portfolio_id, id),
    CHECK ((status IN ('reserved', 'running') AND completed_at IS NULL)
        OR (status IN ('completed', 'partial', 'failed') AND completed_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_monitoring_cycles_history
    ON portfolio_private.monitoring_cycles (portfolio_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_monitoring_cycles_lease
    ON portfolio_private.monitoring_cycles (status, started_at, id)
    WHERE status IN ('reserved', 'running');

CREATE TABLE IF NOT EXISTS portfolio_private.monitoring_state (
    portfolio_id UUID PRIMARY KEY
        REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    next_due_at TIMESTAMPTZ,
    current_cycle_id UUID,
    lease_until TIMESTAMPTZ,
    last_cleanup_at TIMESTAMPTZ,
    FOREIGN KEY (portfolio_id, current_cycle_id)
        REFERENCES portfolio_private.monitoring_cycles (portfolio_id, id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS portfolio_private.latest_quotes (
    portfolio_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    price_usd NUMERIC(38, 18) NOT NULL
        CHECK (price_usd > 0 AND price_usd < 'Infinity'::numeric),
    quoted_at TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    provider VARCHAR(40) NOT NULL,
    source_cycle_id UUID,
    last_attempt_at TIMESTAMPTZ,
    last_error VARCHAR(80),
    PRIMARY KEY (portfolio_id, asset_id),
    FOREIGN KEY (portfolio_id, asset_id)
        REFERENCES portfolio_private.assets (portfolio_id, id) ON DELETE CASCADE,
    FOREIGN KEY (portfolio_id, source_cycle_id)
        REFERENCES portfolio_private.monitoring_cycles (portfolio_id, id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_latest_quotes_freshness
    ON portfolio_private.latest_quotes (portfolio_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_private.price_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL,
    cycle_id UUID NOT NULL,
    target_id UUID NOT NULL,
    target_version BIGINT NOT NULL,
    target_price_usd NUMERIC(38, 18) NOT NULL
        CHECK (target_price_usd > 0 AND target_price_usd < 'Infinity'::numeric),
    target_kind VARCHAR(10) NOT NULL CHECK (target_kind IN ('buy', 'sell')),
    target_orientation VARCHAR(1000),
    proximity_percent NUMERIC(5, 2) NOT NULL
        CHECK (proximity_percent >= 0 AND proximity_percent <= 100),
    price_usd NUMERIC(38, 18)
        CHECK (price_usd IS NULL OR (price_usd > 0 AND price_usd < 'Infinity'::numeric)),
    quoted_at TIMESTAMPTZ,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    distance_percent NUMERIC
        CHECK (distance_percent IS NULL OR (distance_percent >= 0 AND distance_percent < 'Infinity'::numeric)),
    result VARCHAR(20) NOT NULL
        CHECK (result IN ('inside', 'outside', 'error', 'superseded')),
    error_code VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (portfolio_id, cycle_id, target_id),
    UNIQUE (portfolio_id, id),
    FOREIGN KEY (portfolio_id, cycle_id)
        REFERENCES portfolio_private.monitoring_cycles (portfolio_id, id) ON DELETE CASCADE,
    FOREIGN KEY (portfolio_id, target_id)
        REFERENCES portfolio_private.price_targets (portfolio_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_evaluations_history
    ON portfolio_private.price_evaluations (portfolio_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_price_evaluations_target_history
    ON portfolio_private.price_evaluations (portfolio_id, target_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS portfolio_private.price_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL,
    evaluation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    displayed_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    UNIQUE (evaluation_id),
    FOREIGN KEY (portfolio_id, evaluation_id)
        REFERENCES portfolio_private.price_evaluations (portfolio_id, id) ON DELETE CASCADE,
    CHECK (read_at IS NULL OR displayed_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_price_notifications_history
    ON portfolio_private.price_notifications (portfolio_id, created_at DESC, id DESC);

-- Provider budget and catalog are private shared service state. Their RLS
-- policy still requires a validated owner transaction before access.
CREATE TABLE IF NOT EXISTS portfolio_private.provider_budget (
    provider VARCHAR(40) NOT NULL,
    key_fingerprint CHAR(64) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    configured_limit INTEGER NOT NULL CHECK (configured_limit > 0),
    cooldown_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, key_fingerprint),
    CHECK (window_start < window_end)
);

CREATE TABLE IF NOT EXISTS portfolio_private.provider_catalog (
    provider VARCHAR(40) PRIMARY KEY,
    payload JSONB NOT NULL DEFAULT '[]'::jsonb,
    fetched_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    version BIGINT NOT NULL DEFAULT 0 CHECK (version >= 0),
    refresh_token UUID,
    refresh_lease_until TIMESTAMPTZ,
    last_error VARCHAR(80),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((refresh_token IS NULL) = (refresh_lease_until IS NULL))
);

-- Force RLS even for table owners. Runtime queries set app.current_user_id
-- only after TokenVerifier has validated the JWT and owner identity.
DO $$
DECLARE
    table_name TEXT;
    user_scoped_tables TEXT[] := ARRAY[
        'monitoring_settings', 'asset_price_mappings', 'price_targets',
        'monitoring_changes', 'monitoring_cycles', 'monitoring_state',
        'latest_quotes', 'price_evaluations', 'price_notifications',
        'provider_budget', 'provider_catalog'
    ];
    owner_expression TEXT := 'EXISTS (
        SELECT 1 FROM portfolio_private.portfolios p
        WHERE p.owner_id = NULLIF(current_setting(''app.current_user_id'', true), '''')::UUID
    )';
BEGIN
    FOREACH table_name IN ARRAY user_scoped_tables LOOP
        EXECUTE format('ALTER TABLE portfolio_private.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE portfolio_private.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s ON portfolio_private.%I', table_name, table_name);
        EXECUTE format(
            'CREATE POLICY rls_%s ON portfolio_private.%I USING (%s) WITH CHECK (%s)',
            table_name, table_name, owner_expression, owner_expression
        );
    END LOOP;
END $$;

-- Runtime receives only row-level DML on these new tables. No PUBLIC or
-- Supabase Data API role can access monitoring data directly.
DO $$
DECLARE
    table_name TEXT;
    app_role TEXT := 'carteira_app';
    app_tables TEXT[] := ARRAY[
        'monitoring_settings', 'asset_price_mappings', 'price_targets',
        'monitoring_changes', 'monitoring_cycles', 'monitoring_state',
        'latest_quotes', 'price_evaluations', 'price_notifications',
        'provider_budget', 'provider_catalog'
    ];
BEGIN
    FOREACH table_name IN ARRAY app_tables LOOP
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE portfolio_private.%I FROM PUBLIC', table_name);
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon', 'authenticated')) THEN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE portfolio_private.%I FROM anon', table_name);
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE portfolio_private.%I FROM authenticated', table_name);
            END IF;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE portfolio_private.%I TO %I', table_name, app_role);
        END IF;
    END LOOP;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
        EXECUTE format('GRANT USAGE ON SCHEMA portfolio_private TO %I', app_role);
    END IF;
END $$;
