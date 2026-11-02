"""Consumidor de atualizações em segundo plano (long-polling) da Bot API do Telegram.

Atende a D-01, D-02, D-07, RF-01 a RF-10 e padrão Sandeclaw (Prof. Sandeco):
- Single Consumer: trava única para impedir concorrência entre loops.
- Rastreabilidade estruturada quando VERBOSE=true:
  [INCOMING TELEGRAM], [AGENT LOOP], [TOOL EXECUTION], [OUTBOUND PAYLOAD].
- Whitelist e autorização estrita (nenhum vazamento a terceiros).
- Suporte a texto e voz (STT efêmero).
- Responde somente quando Denis envia mensagem (nunca espontaneamente).
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from app.config import get_settings, is_telegram_configured
from app.db import get_db_connection
from app.services.portfolio import PortfolioService
from app.services.notifications import NotificationService
from app.services.price_targets import PriceTargetService
from app.services.telegram_access import TelegramAccessManager, AccessCheckResult
from app.services.telegram_alarm import check_telegram_alarms
from app.services.telegram_draft import (
    get_draft,
    save_draft,
    clear_draft,
    is_update_already_applied,
    record_applied_update,
)
from app.services.telegram_intent import (
    TelegramIntentKind,
    classify_telegram_intent,
)
from app.services.telegram_launch import execute_telegram_launch
from app.services.telegram_reply import TelegramReplyComposer
from app.services.telegram_voice import process_telegram_voice

logger = logging.getLogger(__name__)

_poll_lock = asyncio.Lock()


def send_telegram_message(bot_token: str, chat_id: int, text: str) -> bool:
    """Envia mensagem para o Telegram via Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    for attempt in range(2):
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 400:
                    # Tenta sem Markdown se houver erro de formatação
                    payload.pop("parse_mode", None)
                    resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    return True
                logger.warning(f"Telegram sendMessage status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Tentativa {attempt+1} ao enviar mensagem Telegram para {chat_id} falhou: {e}")
    return False


def _get_active_assets(cur: Any, portfolio_id: UUID) -> List[Dict[str, Any]]:
    cur.execute(
        "SELECT id, symbol, name FROM portfolio_private.assets WHERE portfolio_id = %s;",
        (str(portfolio_id),),
    )
    return [{"id": str(r[0]), "symbol": str(r[1]), "name": str(r[2])} for r in cur.fetchall()]


def _get_allocations_map(cur: Any, portfolio_id: UUID) -> Dict[str, Any]:
    try:
        cur.execute(
            """
            SELECT a.symbol, i.target_percent
            FROM portfolio_private.allocation_targets t
            JOIN portfolio_private.allocation_target_items i ON i.orientation_id = t.id
            JOIN portfolio_private.assets a ON a.id = i.asset_id
            WHERE t.portfolio_id = %s AND t.active = true;
            """,
            (str(portfolio_id),),
        )
        return {str(r[0]).upper(): {"target_percent": r[1]} for r in cur.fetchall()}
    except Exception as e:
        logger.warning(f"Erro ao buscar alocações para alarmes: {e}")
        return {}


def process_single_telegram_update(
    update: Dict[str, Any],
    bot_token: str,
    owner_id: UUID,
    access_manager: TelegramAccessManager,
    verbose: bool = False,
) -> None:
    """Processa determinística e atomicamente uma única atualização do Telegram."""
    update_id = update.get("update_id")
    if not update_id:
        return

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    from_user = msg.get("from") or {}
    user_id = from_user.get("id")
    chat_id = msg.get("chat", {}).get("id")
    if not user_id or not chat_id:
        return

    msg_date_ts = msg.get("date")
    msg_time = datetime.fromtimestamp(msg_date_ts, tz=timezone.utc) if msg_date_ts else datetime.now(timezone.utc)

    # 1. Rastreabilidade Verbose (Sandeclaw)
    if verbose:
        logger.info(f"[INCOMING TELEGRAM] UpdateID={update_id} FromID={user_id} Date={msg_time}")

    try:
        with get_db_connection(owner_id) as conn:
            with conn.cursor() as cur:
                # 2. Idempotência: Se já processado, ignora
                if is_update_already_applied(cur, update_id):
                    if verbose:
                        logger.info(f"[AGENT LOOP] Update {update_id} já aplicado anteriormente. Ignorando.")
                    return

                portfolio_service = PortfolioService()
                portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, owner_id)

                # 3. Verificação de Acesso e Vínculo
                access_status = access_manager.verify_or_link_account(cur, portfolio_id, user_id)
                if access_status in (AccessCheckResult.REJECTED_NOT_WHITELISTED, AccessCheckResult.REJECTED_DIFFERENT_ACCOUNT):
                    if verbose:
                        logger.warning(f"[ACCESS CONTROL] Acesso recusado para Telegram ID {user_id}: {access_status}")
                    record_applied_update(cur, update_id, portfolio_id, "recusa_nao_autorizado")
                    conn.commit()
                    # Responde recusa sem revelar nenhum detalhe financeiro
                    reply = TelegramReplyComposer.format_unauthorized()
                    send_telegram_message(bot_token, chat_id, reply)
                    return

                conn.commit()

                # 4. Obtenção do texto (digitado ou por voz)
                text_content = msg.get("text")
                voice_obj = msg.get("voice") or msg.get("audio")

                if not text_content and voice_obj:
                    file_id = voice_obj.get("file_id")
                    if verbose:
                        logger.info(f"[TOOL EXECUTION] Transcrevendo áudio do Telegram FileID={file_id}")
                    text_content = process_telegram_voice(bot_token, file_id)

                if not text_content:
                    reply = TelegramReplyComposer.format_read_error()
                    record_applied_update(cur, update_id, portfolio_id, "falha_leitura")
                    conn.commit()
                    send_telegram_message(bot_token, chat_id, reply)
                    return

                if verbose:
                    logger.info(f"[AGENT LOOP] Mensagem processada: '{text_content}'")

                # 5. Configuração da IA e Interpretação da Intenção
                assets = _get_active_assets(cur, portfolio_id)
                current_draft = get_draft(cur, portfolio_id, user_id)

                cur.execute(
                    "SELECT gemini_api_key, gemini_model FROM portfolio_private.portfolios WHERE id = %s;",
                    (str(portfolio_id),),
                )
                ai_row = cur.fetchone()
                gemini_key = (ai_row[0] if ai_row and ai_row[0] else None) or os.getenv("GEMINI_API_KEY")
                gemini_model = (ai_row[1] if ai_row and ai_row[1] else "gemini-2.5-flash")

                intent_res = classify_telegram_intent(
                    text=text_content,
                    assets=assets,
                    current_draft=current_draft,
                    message_time=msg_time,
                    gemini_api_key=gemini_key,
                    gemini_model=gemini_model,
                )

                if verbose:
                    logger.info(f"[AGENT LOOP] Intenção detectada: {intent_res.intent} (LLM ativa: {bool(gemini_key)})")

                reply_text = ""

                # 6. Despacho por Intenção
                if intent_res.intent == TelegramIntentKind.CANCELAR:
                    clear_draft(cur, portfolio_id, user_id)
                    record_applied_update(cur, update_id, portfolio_id, "cancelamento")
                    conn.commit()
                    reply_text = intent_res.conversational_reply or TelegramReplyComposer.format_cancel_draft()

                elif intent_res.intent == TelegramIntentKind.CONVERSA:
                    record_applied_update(cur, update_id, portfolio_id, "conversa")
                    conn.commit()
                    reply_text = intent_res.conversational_reply or (
                        "Olá Denis! Sou seu assistente de carteira. Como posso ajudar com seus investimentos hoje?"
                    )

                elif intent_res.intent == TelegramIntentKind.FORA_DE_ESCOPO:
                    record_applied_update(cur, update_id, portfolio_id, "fora_de_escopo")
                    conn.commit()
                    reply_text = intent_res.conversational_reply or TelegramReplyComposer.format_out_of_scope()

                elif intent_res.intent == TelegramIntentKind.PATRIMONIO:
                    summary = portfolio_service.get_portfolio_summary(cur, portfolio_id)
                    record_applied_update(cur, update_id, portfolio_id, "consulta_patrimonio")
                    conn.commit()
                    reply_text = TelegramReplyComposer.format_patrimonio(summary)

                elif intent_res.intent == TelegramIntentKind.RESULTADO:
                    summary = portfolio_service.get_portfolio_summary(cur, portfolio_id)
                    record_applied_update(cur, update_id, portfolio_id, "consulta_resultado")
                    conn.commit()
                    reply_text = TelegramReplyComposer.format_resultado(summary)

                elif intent_res.intent == TelegramIntentKind.LISTA:
                    summary = portfolio_service.get_portfolio_summary(cur, portfolio_id)
                    record_applied_update(cur, update_id, portfolio_id, "consulta_lista")
                    conn.commit()
                    reply_text = TelegramReplyComposer.format_asset_list(summary)

                elif intent_res.intent == TelegramIntentKind.SALDO:
                    sym = intent_res.symbol or ""
                    summary = portfolio_service.get_portfolio_summary(cur, portfolio_id)
                    record_applied_update(cur, update_id, portfolio_id, "consulta_saldo")
                    conn.commit()
                    reply_text = TelegramReplyComposer.format_saldo(sym, summary)

                elif intent_res.intent == TelegramIntentKind.ALARME:
                    notif_svc = NotificationService()
                    unreads = notif_svc.list_history(cur, portfolio_id, limit=20).get("items", [])
                    unreads_filtered = [n for n in unreads if n.get("read_at") is None]

                    summary = portfolio_service.get_portfolio_summary(cur, portfolio_id)
                    target_svc = PriceTargetService()
                    targets = target_svc.list_targets(cur, portfolio_id).get("items", [])
                    allocations = _get_allocations_map(cur, portfolio_id)

                    alarms = check_telegram_alarms(
                        unread_notifications=unreads_filtered,
                        portfolio_summary=summary,
                        targets=targets,
                        allocations=allocations,
                    )
                    record_applied_update(cur, update_id, portfolio_id, "consulta_alarme")
                    conn.commit()
                    txt_lower = text_content.lower()
                    q_type = "compra" if ("compra" in txt_lower or "comprar" in txt_lower) else ("venda" if ("venda" in txt_lower or "vender" in txt_lower) else None)
                    reply_text = TelegramReplyComposer.format_alarms(alarms, query_type=q_type)

                elif intent_res.intent == TelegramIntentKind.LANCAMENTO:
                    if intent_res.missing_fields:
                        # Rascunho incompleto: salva para a próxima iteração
                        draft_payload = {
                            "kind": intent_res.kind,
                            "symbol": intent_res.symbol,
                            "quantity": intent_res.quantity,
                            "unit_price_usd": intent_res.unit_price_usd,
                            "fee_usdt": intent_res.fee_usdt,
                            "note": intent_res.note,
                            "missing_fields": intent_res.missing_fields,
                            "message_time": intent_res.occurred_at or msg_time,
                        }
                        save_draft(cur, portfolio_id, user_id, draft_payload)
                        record_applied_update(cur, update_id, portfolio_id, "pergunta_campo_faltante")
                        conn.commit()
                        reply_text = intent_res.conversational_reply or TelegramReplyComposer.format_missing_field_question(
                            intent_res.missing_fields, draft_payload
                        )
                    else:
                        # Lançamento completo: executa atomicamente no ledger
                        if verbose:
                            logger.info(f"[TOOL EXECUTION] Executando lançamento no Ledger: {intent_res.kind} {intent_res.quantity} {intent_res.symbol}")

                        success, msg_result, op_info = execute_telegram_launch(
                            cur=cur,
                            portfolio_id=portfolio_id,
                            owner_id=owner_id,
                            telegram_user_id=user_id,
                            update_id=update_id,
                            kind=intent_res.kind or "buy",
                            symbol=intent_res.symbol or "",
                            quantity=intent_res.quantity or 0,
                            unit_price_usd=intent_res.unit_price_usd,
                            fee_usdt=intent_res.fee_usdt,
                            occurred_at=intent_res.occurred_at or msg_time,
                            note=intent_res.note,
                        )
                        conn.commit()
                        if success and op_info:
                            reply_text = TelegramReplyComposer.format_launch_success(op_info)
                        else:
                            reply_text = TelegramReplyComposer.format_launch_failure(msg_result)

                if verbose:
                    logger.info(f"[OUTBOUND PAYLOAD] Enviando resposta para ChatID={chat_id}")

                send_telegram_message(bot_token, chat_id, reply_text)
    except Exception as e:
        logger.exception(f"Erro inesperado ao processar mensagem do Telegram update_id={update_id}: {e}")
        try:
            # Garante resposta a Denis para nunca deixá-lo no vácuo
            send_telegram_message(
                bot_token,
                chat_id,
                "⚠️ Ocorreu uma instabilidade ao consultar sua carteira. Por favor, tente novamente em instantes.",
            )
            with get_db_connection(owner_id) as conn:
                with conn.cursor() as cur:
                    record_applied_update(cur, update_id, None, "falha_inesperada")
                conn.commit()
        except Exception:
            pass


async def telegram_polling_loop(owner_id: UUID, stop_event: asyncio.Event) -> None:
    """Loop contínuo de polling com proteção de trava única (Single Consumer)."""
    settings = get_settings()
    if not is_telegram_configured(settings):
        logger.info("Agente Telegram desligado (TELEGRAM_BOT_TOKEN não configurado).")
        return

    bot_token = settings.telegram_bot_token.get_secret_value()
    access_manager = TelegramAccessManager(settings.telegram_allowed_users)
    offset = 0

    logger.info("Iniciando consumidor de mensagens do Telegram (long-polling)...")

    async with _poll_lock:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while not stop_event.is_set():
                try:
                    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                    params = {"offset": offset, "timeout": 20}
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        for update in updates:
                            up_id = update.get("update_id")
                            if up_id:
                                offset = max(offset, up_id + 1)
                            # Processa em thread pool para operações síncronas de banco
                            await asyncio.to_thread(
                                process_single_telegram_update,
                                update=update,
                                bot_token=bot_token,
                                owner_id=owner_id,
                                access_manager=access_manager,
                                verbose=settings.verbose,
                            )
                    elif resp.status_code == 401:
                        logger.error("Token do Telegram inválido. Encerrando consumidor.")
                        break
                    else:
                        await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Exceção no ciclo de polling do Telegram: {e}")
                    await asyncio.sleep(5)

