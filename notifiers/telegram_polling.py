"""
Polling loop para receber comandos do Telegram Bot.

Comandos reconhecidos:
  /start    — inscreve o usuário para receber notificações
  /assinar  — alias para /start
  /sair     — remove o usuário da lista
  /status   — informa se o usuário está inscrito
"""

import os
import time

import requests

from .telegram import add_user, get_users, remove_user

_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8704375512:AAFs8ICnxKAphbFscOK9NKNbpzWwyYTB4tA")


def _send(token: str, chat_id, text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[TelegramBot] Erro ao responder {chat_id}: {e}")


def _handle_update(token: str, update: dict):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip().lower()

    # Normaliza comandos (remove @botname se presente)
    if text.startswith("/"):
        text = text.split("@")[0]

    if text in ("/start", "/assinar", "/subscribe"):
        if add_user(chat_id):
            _send(token, chat_id,
                  "✅ <b>Inscrito com sucesso!</b>\n\n"
                  "Você passará a receber notificações quando novos exames forem detectados ou resultados ficarem prontos. 🔬\n\n"
                  "Para cancelar, envie /sair.")
        else:
            _send(token, chat_id,
                  "ℹ️ Você <b>já está inscrito</b> e receberá as notificações normalmente.\n\n"
                  "Para cancelar, envie /sair.")

    elif text in ("/sair", "/cancelar", "/unsubscribe"):
        if remove_user(chat_id):
            _send(token, chat_id,
                  "👋 Você foi <b>removido</b> da lista de notificações.\n\n"
                  "Para se inscrever novamente, envie /start.")
        else:
            _send(token, chat_id,
                  "ℹ️ Você não está na lista de notificações.")

    elif text == "/status":
        if chat_id in get_users():
            _send(token, chat_id, "✅ Você está inscrito e receberá notificações.")
        else:
            _send(token, chat_id, "❌ Você não está inscrito. Envie /start para se inscrever.")


def run_bot_polling(token: str | None = None):
    """Roda em background thread. Faz polling de updates e processa comandos."""
    token = token or _TOKEN
    if not token:
        print("[TelegramBot] Token não configurado — polling desativado.")
        return

    print("[TelegramBot] Polling iniciado.")
    offset = 0
    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                timeout=40,
            )
            if resp.ok:
                updates = resp.json().get("result", [])
                for update in updates:
                    _handle_update(token, update)
                    offset = update["update_id"] + 1
        except Exception as e:
            print(f"[TelegramBot] Erro no polling: {e}")
            time.sleep(5)
