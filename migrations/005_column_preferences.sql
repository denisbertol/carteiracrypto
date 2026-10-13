ALTER TABLE portfolio_private.portfolios
    ADD COLUMN IF NOT EXISTS hidden_columns JSONB NOT NULL DEFAULT '[]'::jsonb;
