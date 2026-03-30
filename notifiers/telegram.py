import json
import os
from pathlib import Path

import requests

from .base import Notifier

USERS_FILE = Path(__file__).parent.parent / "telegram_users.json"


def _default_chat_id() -> str:
    return os.environ.get("TELEGRAM_CHATID", "8658992577")


def get_users() -> list[str]:
    """Retorna lista de chat_ids cadastrados. Cria o arquivo se não existir."""
    if not USERS_FILE.exists():
        default = _default_chat_id()
        _write_users([default] if default else [])
    try:
        users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return [str(u) for u in users if u]
    except Exception:
        return [_default_chat_id()]


def add_user(chat_id: str) -> bool:
    """Adiciona chat_id à lista. Retorna True se adicionado, False se já existia."""
    chat_id = str(chat_id)
    users = get_users()
    if chat_id in users:
        return False
    users.append(chat_id)
    _write_users(users)
    return True


def remove_user(chat_id: str) -> bool:
    """Remove chat_id da lista. Retorna True se removido."""
    chat_id = str(chat_id)
    users = get_users()
    if chat_id not in users:
        return False
    users.remove(chat_id)
    _write_users(users)
    return True


def _write_users(users: list[str]):
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


class TelegramNotifier(Notifier):

    def __init__(self):
        self._token = os.environ.get("TELEGRAM_TOKEN", "8704375512:AAFs8ICnxKAphbFscOK9NKNbpzWwyYTB4tA")

    def enviar(self, mensagem: str) -> None:
        for chat_id in get_users():
            try:
                requests.post(
                    f"https://api.telegram.org/bot{self._token}/sendMessage",
                    json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"},
                    timeout=15,
                )
            except Exception as e:
                print(f"[Telegram] Erro ao enviar para {chat_id}: {e}")
