from .config import Config
from .controller import TelegramManager as _TelegramManager


class TelegramManager(_TelegramManager):
    def __init__(self):
        super().__init__(Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH, Config.TELEGRAM_PHONE_NUMBER)
