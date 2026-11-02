"""Testes da especificação de intenção estruturada do Agente Telegram (T003)."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.services.telegram_intent import (
    TelegramIntentKind,
    TelegramIntentResult,
    classify_telegram_intent,
)


@pytest.fixture
def mock_assets():
    return [
        {"id": "11111111-1111-1111-1111-111111111111", "symbol": "USDT", "name": "Tether USD"},
        {"id": "22222222-2222-2222-2222-222222222222", "symbol": "BTC", "name": "Bitcoin"},
        {"id": "33333333-3333-3333-3333-333333333333", "symbol": "ETH", "name": "Ethereum"},
        {"id": "44444444-4444-4444-4444-444444444444", "symbol": "SOL", "name": "Solana"},
    ]


def test_intent_patrimonio(mock_assets):
    msg_time = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("quanto está o patrimônio?", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.PATRIMONIO


def test_intent_resultado(mock_assets):
    msg_time = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("qual é o meu resultado atual?", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.RESULTADO


def test_intent_lista(mock_assets):
    msg_time = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("listar minhas criptomoedas", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.LISTA


def test_intent_saldo(mock_assets):
    msg_time = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("qual é o saldo de BTC?", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.SALDO
    assert res.symbol == "BTC"


def test_intent_saldo_ativo_nao_cadastrado(mock_assets):
    msg_time = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("qual o saldo de XYZ?", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.SALDO
    assert res.symbol == "XYZ"


def test_intent_alarme(mock_assets):
    msg_time = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("tem alarme de alvo de compra ou venda?", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.ALARME


def test_intent_fora_de_escopo(mock_assets):
    msg_time = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("compre 1 BTC na Binance agora", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.FORA_DE_ESCOPO


def test_intent_lancamento_completo_sem_data_usa_data_da_mensagem(mock_assets):
    msg_time = datetime(2026, 11, 1, 15, 30, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent(
        "comprei 0.5 BTC a 68000 taxa 2",
        mock_assets,
        message_time=msg_time,
    )
    assert res.intent == TelegramIntentKind.LANCAMENTO
    assert res.kind == "buy"
    assert res.symbol == "BTC"
    assert res.quantity == Decimal("0.5")
    assert res.unit_price_usd == Decimal("68000")
    assert res.fee_usdt == Decimal("2")
    assert res.occurred_at == msg_time
    assert res.missing_fields == []


def test_intent_lancamento_incompleto_gera_missing_fields(mock_assets):
    msg_time = datetime(2026, 11, 1, 15, 30, 0, tzinfo=timezone.utc)
    # Falta preço unitário e quantidade
    res = classify_telegram_intent(
        "comprei BTC",
        mock_assets,
        message_time=msg_time,
    )
    assert res.intent == TelegramIntentKind.LANCAMENTO
    assert res.kind == "buy"
    assert res.symbol == "BTC"
    assert "quantity" in res.missing_fields
    assert "unit_price_usd" in res.missing_fields


def test_intent_lancamento_completa_rascunho_existente(mock_assets):
    msg_time = datetime(2026, 11, 1, 15, 30, 0, tzinfo=timezone.utc)
    prior_draft = {
        "kind": "buy",
        "symbol": "BTC",
        "quantity": Decimal("0.1"),
        "unit_price_usd": None,
        "fee_usdt": Decimal("0"),
        "message_time": msg_time,
        "missing_fields": ["unit_price_usd"],
    }
    # Denis responde com o preço que faltava
    res = classify_telegram_intent(
        "o preço foi 65000",
        mock_assets,
        current_draft=prior_draft,
        message_time=msg_time,
    )
    assert res.intent == TelegramIntentKind.LANCAMENTO
    assert res.kind == "buy"
    assert res.symbol == "BTC"
    assert res.quantity == Decimal("0.1")
    assert res.unit_price_usd == Decimal("65000")
    assert res.missing_fields == []


def test_intent_cancelar_rascunho(mock_assets):
    msg_time = datetime(2026, 11, 1, 15, 30, 0, tzinfo=timezone.utc)
    prior_draft = {
        "kind": "buy",
        "symbol": "BTC",
        "quantity": Decimal("0.1"),
        "missing_fields": ["unit_price_usd"],
    }
    res = classify_telegram_intent("cancelar", mock_assets, current_draft=prior_draft, message_time=msg_time)
    assert res.intent == TelegramIntentKind.CANCELAR


def test_intent_registrar_nova_operacao_pergunta_detalhes(mock_assets):
    msg_time = datetime(2026, 11, 1, 15, 30, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("registrar nova operação", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.LANCAMENTO
    assert "kind" in res.missing_fields
    assert "symbol" in res.missing_fields
    assert "quantity" in res.missing_fields
    assert res.conversational_reply is not None
    assert "Compra ou Venda" in res.conversational_reply or "compra" in res.conversational_reply.lower()


def test_intent_conversa_saudacao(mock_assets):
    msg_time = datetime(2026, 11, 1, 15, 30, 0, tzinfo=timezone.utc)
    res = classify_telegram_intent("oi, tudo bem?", mock_assets, message_time=msg_time)
    assert res.intent == TelegramIntentKind.CONVERSA
    assert res.conversational_reply is not None
    assert "Denis" in res.conversational_reply


