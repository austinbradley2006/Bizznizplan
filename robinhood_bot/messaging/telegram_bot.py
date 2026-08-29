from __future__ import annotations

import logging
import os
import time

import requests

from robinhood_bot.config import MessagingConfig
from robinhood_bot.messaging.commands import handle_message

logger = logging.getLogger(__name__)


class TelegramBot:
    """Poll Telegram for messages and reply with bot commands."""

    def __init__(self, config: MessagingConfig, handler_context: dict) -> None:
        self.config = config.telegram
        self.context = handler_context
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", self.config.bot_token)
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._offset = 0

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled and self.token)

    def _allowed(self, chat_id: int) -> bool:
        if not self.config.allowed_chat_ids:
            return True
        return chat_id in self.config.allowed_chat_ids

    def send_message(self, chat_id: int, text: str) -> None:
        for chunk in _split_message(text, 4000):
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": chunk},
                timeout=30,
            )
            response.raise_for_status()

    def _process_update(self, update: dict) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")
        if chat_id is None or not text:
            return

        if not self._allowed(chat_id):
            self.send_message(
                chat_id,
                f"Unauthorized. Add chat ID {chat_id} to messaging.telegram.allowed_chat_ids in config.",
            )
            return

        if text.strip().lower() in {"/start", "start"}:
            self.send_message(
                chat_id,
                f"Robinhood Bot connected.\nYour chat ID: {chat_id}\n\n{handle_message('HELP', **self.context)}",
            )
            return

        if text.startswith("/"):
            text = text[1:]

        reply = handle_message(text, **self.context)
        self.send_message(chat_id, reply)

    def poll_forever(self) -> None:
        if not self.enabled:
            raise RuntimeError(
                "Telegram not configured. Set messaging.telegram.enabled=true and "
                "TELEGRAM_BOT_TOKEN in .env (get one from @BotFather on Telegram)."
            )

        logger.info("Telegram bot polling started. Text your bot or send HELP.")
        while True:
            try:
                response = requests.get(
                    f"{self.base_url}/getUpdates",
                    params={"timeout": 30, "offset": self._offset},
                    timeout=35,
                )
                response.raise_for_status()
                for update in response.json().get("result", []):
                    self._offset = update["update_id"] + 1
                    self._process_update(update)
            except Exception:
                logger.exception("Telegram poll error")
                time.sleep(5)


def _split_message(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks
