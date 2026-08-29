from __future__ import annotations

import logging
import os

from flask import Flask, request
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from robinhood_bot.config import MessagingConfig
from robinhood_bot.messaging.commands import handle_message

logger = logging.getLogger(__name__)


def create_twilio_app(config: MessagingConfig, handler_context: dict) -> Flask:
    """Flask app that receives inbound SMS from Twilio."""
    twilio_cfg = config.twilio
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", twilio_cfg.account_sid)
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", twilio_cfg.auth_token)
    validator = RequestValidator(auth_token) if auth_token else None

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/sms")
    def sms():
        if validator and twilio_cfg.verify_signatures:
            signature = request.headers.get("X-Twilio-Signature", "")
            url = request.url
            if not validator.validate(url, request.form, signature):
                return "Unauthorized", 403

        from_number = request.form.get("From", "")
        body = request.form.get("Body", "")

        allowed = twilio_cfg.allowed_numbers or []
        if allowed and from_number not in allowed:
            response = MessagingResponse()
            response.message(
                f"Unauthorized number. Add {from_number} to messaging.twilio.allowed_numbers."
            )
            return str(response), 200, {"Content-Type": "text/xml"}

        try:
            reply = handle_message(body, **handler_context)
        except Exception as exc:
            logger.exception("SMS command failed")
            reply = f"Error: {exc}"

        response = MessagingResponse()
        for chunk in _split_sms(reply, 1500):
            response.message(chunk)
        return str(response), 200, {"Content-Type": "text/xml"}

    return app


def run_twilio_server(config: MessagingConfig, handler_context: dict) -> None:
    twilio_cfg = config.twilio
    if not twilio_cfg.enabled:
        raise RuntimeError("Twilio SMS not enabled in config.")

    app = create_twilio_app(config, handler_context)
    logger.info(
        "Twilio SMS server on port %s. Set webhook to https://YOUR_URL/sms",
        twilio_cfg.webhook_port,
    )
    app.run(host="0.0.0.0", port=twilio_cfg.webhook_port)


def _split_sms(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]
