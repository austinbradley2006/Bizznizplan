from unittest.mock import MagicMock

from robinhood_bot.messaging.commands import handle_message


def test_help_command():
    reply = handle_message(
        "help",
        bot=MagicMock(),
        config=MagicMock(),
        service=MagicMock(),
        journal=MagicMock(),
    )
    assert "STATUS" in reply
    assert "SCAN" in reply


def test_unknown_command():
    reply = handle_message(
        "foobar",
        bot=MagicMock(),
        config=MagicMock(),
        service=MagicMock(),
        journal=MagicMock(),
    )
    assert "Unknown command" in reply
