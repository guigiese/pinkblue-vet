import os
from datetime import datetime

import requests

from pb_platform.storage import store

from .base import Notifier


def get_users() -> list[dict]:
    """Returns list of user dicts: chat_id, name, username, subscribed_at."""
    return store.list_telegram_users()


def get_user_ids() -> list[str]:
    """Returns list of chat_ids only, for sending notifications."""
    return [u["chat_id"] for u in get_users()]


def add_user(chat_id: str, name: str = "", username: str = "") -> bool:
    """Add user. Returns True if newly added, False if already existed (updates name)."""
    return store.add_telegram_user(
        str(chat_id),
        name=name,
        username=username,
        subscribed_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )


def remove_user(chat_id: str) -> bool:
    """Remove user by chat_id. Returns True if removed."""
    return store.remove_telegram_user(str(chat_id))


class TelegramNotifier(Notifier):
    def __init__(self):
        self._token = os.environ.get("TELEGRAM_TOKEN", "8704375512:AAFs8ICnxKAphbFscOK9NKNbpzWwyYTB4tA")

    def _send_to_chat(self, chat_id: str, mensagem: str, *, timeout: int = 15) -> None:
        r = requests.post(
            f"https://api.telegram.org/bot{self._token}/sendMessage",
            json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"},
            timeout=timeout,
        )
        resp = r.json()
        if not resp.get("ok"):
            raise RuntimeError(resp.get("description") or "Falha ao enviar mensagem.")

    def enviar(self, mensagem: str) -> None:
        for chat_id in get_user_ids():
            try:
                self._send_to_chat(chat_id, mensagem, timeout=15)
                print(f"[Telegram] Enviado para {chat_id}")
            except Exception as e:
                print(f"[Telegram] Erro ao enviar para {chat_id}: {e}")

    def send_test(self, mensagem: str) -> None:
        user_ids = get_user_ids()
        if not user_ids:
            raise ValueError("Nenhum usuário Telegram inscrito para receber o teste.")
        self._send_to_chat(user_ids[0], mensagem, timeout=8)
