"""Testes do controle de acesso, vínculo de primeira conta e whitelist do Telegram (T006)."""

from uuid import uuid4
import pytest

from app.services.telegram_access import (
    TelegramAccessManager,
    AccessCheckResult,
)


class FakeAccessCursor:
    def __init__(self):
        self.accounts = {}

    def execute(self, sql, params=None):
        if "SELECT" in sql and "telegram_accounts" in sql:
            pid = str(params[0])
            user_id = self.accounts.get(pid)
            self._row = (user_id,) if user_id is not None else None
        elif "INSERT INTO" in sql and "telegram_accounts" in sql:
            pid = str(params[0])
            uid = int(params[1])
            self.accounts[pid] = uid
            self._row = None

    def fetchone(self):
        return getattr(self, "_row", None)


def test_first_account_links_automatically():
    cur = FakeAccessCursor()
    portfolio_id = uuid4()
    manager = TelegramAccessManager()

    # Primeira mensagem da conta pessoal (ex: Denis com id 123456789)
    res = manager.verify_or_link_account(cur, portfolio_id, telegram_user_id=123456789)
    assert res == AccessCheckResult.AUTHORIZED_LINKED

    # Mesma conta enviando mensagem seguinte
    res2 = manager.verify_or_link_account(cur, portfolio_id, telegram_user_id=123456789)
    assert res2 == AccessCheckResult.AUTHORIZED_EXISTING


def test_different_account_is_rejected():
    cur = FakeAccessCursor()
    portfolio_id = uuid4()
    manager = TelegramAccessManager()

    # Primeira conta se vincula
    manager.verify_or_link_account(cur, portfolio_id, telegram_user_id=123456789)

    # Conta desconhecida tentando acessar a mesma carteira
    res = manager.verify_or_link_account(cur, portfolio_id, telegram_user_id=999999999)
    assert res == AccessCheckResult.REJECTED_DIFFERENT_ACCOUNT


def test_whitelist_filter_when_configured():
    cur = FakeAccessCursor()
    portfolio_id = uuid4()
    # Whitelist configurada para apenas o ID 123456789
    manager = TelegramAccessManager(allowed_users_raw="123456789, 555555555")

    # Conta que não está na whitelist nem vincula
    res = manager.verify_or_link_account(cur, portfolio_id, telegram_user_id=888888888)
    assert res == AccessCheckResult.REJECTED_NOT_WHITELISTED
