-- Migration 007_telegram_agent.sql
-- Estruturas de suporte ao Agente Telegram (vínculo de conta, rascunhos e controle de atualizações aplicadas)

CREATE SCHEMA IF NOT EXISTS portfolio_private;

CREATE TABLE IF NOT EXISTS portfolio_private.telegram_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    telegram_user_id BIGINT NOT NULL,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_telegram_portfolio UNIQUE (portfolio_id),
    CONSTRAINT uq_telegram_user UNIQUE (telegram_user_id)
);

CREATE TABLE IF NOT EXISTS portfolio_private.telegram_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    telegram_user_id BIGINT NOT NULL,
    kind VARCHAR(20),
    symbol VARCHAR(30),
    quantity NUMERIC(38, 18),
    unit_price_usd NUMERIC(38, 18),
    fee_usdt NUMERIC(38, 18) DEFAULT 0,
    note VARCHAR(2000),
    missing_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    message_time TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_telegram_draft_account UNIQUE (portfolio_id, telegram_user_id)
);

CREATE TABLE IF NOT EXISTS portfolio_private.telegram_updates (
    update_id BIGINT PRIMARY KEY,
    portfolio_id UUID REFERENCES portfolio_private.portfolios(id) ON DELETE CASCADE,
    result_summary VARCHAR(50) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

