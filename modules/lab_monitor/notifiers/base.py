from abc import ABC, abstractmethod


class Notifier(ABC):

    @abstractmethod
    def enviar(self, mensagem: str) -> None:
        """Envia uma mensagem de notificação."""
