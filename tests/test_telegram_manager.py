import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
@patch('telegram_manager.controller.TelegramClient')  # ✅ Correct
def telegram_manager(mock_client):
    from telegram_manager.controller import TelegramManager
    manager = TelegramManager(api_id=12345, api_hash='fakehash', phone_number='+1234567890')
    manager.client = MagicMock()
    manager.client.is_connected.return_value = True
    manager.client.is_user_authorized.return_value = True
    return manager


def test_connect_already_connected(telegram_manager):
    telegram_manager.connect()
    telegram_manager.client.connect.assert_not_called()


def test_connect_not_connected(telegram_manager):
    telegram_manager.client.is_connected.return_value = False
    telegram_manager.connect()
    telegram_manager.client.connect.assert_called_once()


def test_resolve_chat_identifier_url(telegram_manager):
    identifier = "https://t.me/examplechat"
    result = telegram_manager._resolve_chat_identifier(identifier)
    assert result == "examplechat"


def test_resolve_chat_identifier_username(telegram_manager):
    identifier = "@examplechat"
    result = telegram_manager._resolve_chat_identifier(identifier)
    assert result == "@examplechat"


@patch('telegram_manager.controller.TelegramManager._get_chat_dialog')
def test_resolve_chat_identifier_name(mock_get_dialog, telegram_manager):
    mock_get_dialog.return_value.name = "Example Chat"
    identifier = "Example Chat"
    result = telegram_manager._resolve_chat_identifier(identifier)
    assert result == "Example Chat"


@patch('telegram_manager.controller.TelegramManager._get_chat_dialog')
def test_resolve_chat_identifier_not_found(mock_get_dialog, telegram_manager):
    mock_get_dialog.side_effect = ValueError("Chat 'Nonexistent' not found")
    with pytest.raises(ValueError):
        telegram_manager._resolve_chat_identifier("Nonexistent")
