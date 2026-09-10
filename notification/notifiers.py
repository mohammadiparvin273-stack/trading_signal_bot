"""
Modular Notification Layer.

Telegram here is used ONLY to send text messages via a bot token — this
has zero trading permission by nature (Telegram bots cannot place
exchange orders). Add more channels by implementing `Notifier`.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from config.settings import SETTINGS

logger = logging.getLogger("signal_bot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(SETTINGS.notification.log_file)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    logger.addHandler(fh)


class Notifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        ...


class ConsoleNotifier(Notifier):
    def send(self, message: str) -> None:
        print(message)
        print("-" * 60)


class LogNotifier(Notifier):
    def send(self, message: str) -> None:
        logger.info(message.replace("\n", " | "))


class TelegramNotifier(Notifier):
    """Sends a plain text message via the Telegram Bot API. Read/send only —
    the bot token used here has NO exchange access whatsoever."""

    def __init__(self):
        import telegram  # python-telegram-bot
        self.bot = telegram.Bot(token=SETTINGS.notification.telegram_token)
        self.chat_id = SETTINGS.notification.telegram_chat_id

    def send(self, message: str) -> None:
        import asyncio
        asyncio.run(self.bot.send_message(chat_id=self.chat_id, text=message))


def build_notifiers() -> List[Notifier]:
    notifiers: List[Notifier] = []
    if SETTINGS.notification.console:
        notifiers.append(ConsoleNotifier())
    if SETTINGS.notification.log_file:
        notifiers.append(LogNotifier())
    if SETTINGS.notification.telegram_enabled:
        try:
            notifiers.append(TelegramNotifier())
        except Exception as e:
            print(f"[warn] Telegram notifier disabled (setup issue): {e}")
    return notifiers


def notify_all(message: str) -> None:
    for n in build_notifiers():
        try:
            n.send(message)
        except Exception as e:
            print(f"[warn] notifier {n.__class__.__name__} failed: {e}")
