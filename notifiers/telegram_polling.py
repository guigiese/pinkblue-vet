"""
Processamento de comandos do Telegram Bot.

Não faz polling — recebe updates via webhook (POST do Telegram para FastAPI).
O webhook é registrado automaticamente no startup da aplicação.

Comandos reconhecidos:
  /start    — boas-vindas e lista de comandos
  /ajuda    — alias de /start
  /assinar  — inscreve o usuário para receber notificações
  /sair     — remove o usuário da lista
  /status   — informa se o usuário está inscrito
  /testar   — envia ao usuário uma notificação de teste no formato real
"""

import os
import requests
from .telegram import add_user, get_user_ids, remove_user

_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8704375512:AAFs8ICnxKAphbFscOK9NKNbpzWwyYTB4tA")

WEBHOOK_SECRET_PATH = "tg_wh_pb"  # path component que autentica o webhook


def _send(chat_id, text: str, token: str | None = None):
    token = token or _TOKEN
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[TelegramBot] Erro ao responder {chat_id}: {e}")


def handle_update(update: dict, token: str | None = None):
    """Processa um update recebido via webhook. Cada update gera no máximo UMA resposta."""
    token = token or _TOKEN

    message = update.get("message")
    if not message:
        return  # ignora edited_message, channel_post, etc.

    chat_id = str(message["chat"]["id"])
    raw_text = (message.get("text") or "").strip()

    # Normaliza: lowercase, remove @botname
    text = raw_text.lower()
    if text.startswith("/"):
        text = text.split("@")[0]

    from_user = message.get("from", {})
    first_name = from_user.get("first_name", "")
    last_name  = from_user.get("last_name", "")
    name       = f"{first_name} {last_name}".strip()
    username   = from_user.get("username", "")

    # ── /start ou /ajuda ──────────────────────────────────────────────────────
    if text in ("/start", "/ajuda"):
        _send(chat_id,
              "👋 <b>Olá! Bem-vindo(a)!</b>\n\n"
              "Este bot envia notificações automáticas de resultados laboratoriais.\n\n"
              "📋 <b>Comandos disponíveis:</b>\n"
              "• /assinar — receber notificações\n"
              "• /sair — cancelar inscrição\n"
              "• /status — verificar sua situação\n"
              "• /testar — receber uma notificação de exemplo\n"
              "• /ajuda — exibir esta mensagem", token)

    # ── /assinar ──────────────────────────────────────────────────────────────
    elif text in ("/assinar", "/subscribe"):
        novo = add_user(chat_id, name=name, username=username)
        if novo:
            _send(chat_id,
                  "✅ <b>Inscrito com sucesso!</b>\n\n"
                  "Você receberá notificações quando um exame entrar no laboratorio "
                  "e quando resultados forem concluidos em lote.\n\n"
                  "Para cancelar, envie /sair.", token)
        else:
            _send(chat_id,
                  "ℹ️ Você <b>já está inscrito</b> e receberá as notificações normalmente.\n\n"
                  "Para cancelar, envie /sair.", token)

    # ── /sair ─────────────────────────────────────────────────────────────────
    elif text in ("/sair", "/cancelar", "/unsubscribe"):
        removed = remove_user(chat_id)
        if removed:
            _send(chat_id,
                  "👋 Você foi <b>removido</b> da lista de notificações.\n\n"
                  "Para se inscrever novamente, envie /assinar.", token)
        else:
            _send(chat_id,
                  "ℹ️ Você não está na lista de notificações.\n\n"
                  "Envie /assinar para se inscrever.", token)

    # ── /status ───────────────────────────────────────────────────────────────
    elif text == "/status":
        if chat_id in get_user_ids():
            _send(chat_id,
                  "✅ Você está <b>inscrito</b> e receberá notificações.\n\n"
                  "Para cancelar, envie /sair.", token)
        else:
            _send(chat_id,
                  "❌ Você <b>não está inscrito</b>.\n\n"
                  "Envie /assinar para se inscrever.", token)

    # ── /testar ───────────────────────────────────────────────────────────────
    elif text == "/testar":
        _send(chat_id,
              "✅ <b>Exames concluidos - BioAnálises (BitLab)</b>\n"
              "👤 Bolinha - Maria Silva\n"
              "📋 08-00012345 | 01/04/2026\n"
              "🔬 Liberados neste lote\n"
              "• Hemograma Completo\n"
              "• ALT\n\n"
              "<i>Esta é uma notificação de teste. Notificações reais "
              "chegam neste mesmo formato.</i>", token)

    # ── ignora qualquer outra coisa ───────────────────────────────────────────
    # (não responde a mensagens de texto livres — evita spam acidental)


def register_webhook(base_url: str, token: str | None = None):
    """Registra o webhook no Telegram. Chamado no startup da aplicação."""
    token = token or _TOKEN
    webhook_url = f"{base_url.rstrip('/')}/telegram/webhook/{WEBHOOK_SECRET_PATH}"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": ["message"],
                "drop_pending_updates": True,   # descarta updates acumulados offline
            },
            timeout=10,
        )
        result = r.json()
        if result.get("ok"):
            print(f"[TelegramBot] Webhook registrado: {webhook_url}")
        else:
            print(f"[TelegramBot] Falha ao registrar webhook: {result}")
    except Exception as e:
        print(f"[TelegramBot] Erro ao registrar webhook: {e}")


def delete_webhook(token: str | None = None):
    """Remove o webhook (útil para debugging local com polling)."""
    token = token or _TOKEN
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            json={"drop_pending_updates": True},
            timeout=10,
        )
        print("[TelegramBot] Webhook removido.")
    except Exception as e:
        print(f"[TelegramBot] Erro ao remover webhook: {e}")
