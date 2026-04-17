from .telegram import TelegramNotifier
from .whatsapp import WhatsappNotifier

NOTIFIERS = {
    "telegram":  TelegramNotifier,
    "whatsapp":  WhatsappNotifier,
}
