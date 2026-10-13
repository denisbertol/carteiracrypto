-- Daily USD price per asset (UTC day) feeding the portfolio evolution chart.
-- 'live' rows come from monitoring cycles; 'backfill' rows from a one-time
-- CoinGecko history import. The latest quoted_at of a day is its close.
CREATE TABLE IF NOT EXISTS portfolio_private.asset_daily_prices (
    portfolio_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    day DATE NOT NULL,
    price_usd NUMERIC(38, 18) NOT NULL
        CHECK (price_usd > 0 AND price_usd < 'Infinity'::numeric),
    quoted_at TIMESTAMPTZ NOT NULL,
    source VARCHAR(20) NOT NULL CHECK (source IN ('live', 'backfill')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (portfolio_id, asset_id, day),
    FOREIGN KEY (portfolio_id, asset_id)
        REFERENCES portfolio_private.assets (portfolio_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_asset_daily_prices_day
    ON portfolio_private.asset_daily_prices (portfolio_id, day);

-- One row per asset: a completed import is never repeated for the same coin id.
CREATE TABLE IF NOT EXISTS portfolio_private.price_history_backfills (
    portfolio_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    provider_coin_id VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    lease_until TIMESTAMPTZ,
    first_day DATE,
    last_day DATE,
    point_count INTEGER NOT NULL DEFAULT 0 CHECK (point_count >= 0),
    error_code VARCHAR(80),
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (portfolio_id, asset_id),
    FOREIGN KEY (portfolio_id, asset_id)
        REFERENCES portfolio_private.assets (portfolio_id, id) ON DELETE CASCADE
);

DO $$
DECLARE
    table_name TEXT;
    app_role TEXT := 'carteira_app';
    history_tables TEXT[] := ARRAY['asset_daily_prices', 'price_history_backfills'];
    owner_expression TEXT := 'EXISTS (
        SELECT 1 FROM portfolio_private.portfolios p
        WHERE p.owner_id = NULLIF(current_setting(''app.current_user_id'', true), '''')::UUID
    )';
BEGIN
    FOREACH table_name IN ARRAY history_tables LOOP
        EXECUTE format('ALTER TABLE portfolio_private.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE portfolio_private.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s ON portfolio_private.%I', table_name, table_name);
        EXECUTE format(
            'CREATE POLICY rls_%s ON portfolio_private.%I USING (%s) WITH CHECK (%s)',
            table_name, table_name, owner_expression, owner_expression
        );
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE portfolio_private.%I FROM PUBLIC', table_name);
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE portfolio_private.%I FROM anon', table_name);
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE portfolio_private.%I FROM authenticated', table_name);
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE portfolio_private.%I TO %I', table_name, app_role);
        END IF;
    END LOOP;
END $$;
