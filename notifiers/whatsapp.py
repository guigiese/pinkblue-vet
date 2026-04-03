import os
import requests
from .base import Notifier


class WhatsappNotifier(Notifier):

    def __init__(self):
        self._phone  = os.environ.get("WHATSAPP_PHONE",   "555197529191")
        self._apikey = os.environ.get("CALLMEBOT_APIKEY", "4137541")

    def enviar(self, mensagem: str) -> None:
        try:
            requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": self._phone, "text": mensagem, "apikey": self._apikey},
                timeout=15,
            )
        except Exception as e:
            print(f"[WhatsApp] Erro: {e}")

    def send_test(self, mensagem: str) -> None:
        requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": self._phone, "text": mensagem, "apikey": self._apikey},
            timeout=8,
        )
