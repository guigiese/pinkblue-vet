import os
import requests
from .base import Notifier


class TelegramNotifier(Notifier):

    def __init__(self):
        self._token   = os.environ.get("TELEGRAM_TOKEN",  "8704375512:AAFs8ICnxKAphbFscOK9NKNbpzWwyYTB4tA")
        self._chat_id = os.environ.get("TELEGRAM_CHATID", "8658992577")

    def enviar(self, mensagem: str) -> None:
        try:
            requests.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={"chat_id": self._chat_id, "text": mensagem, "parse_mode": "HTML"},
                timeout=15,
            )
        except Exception as e:
            print(f"[Telegram] Erro: {e}")
