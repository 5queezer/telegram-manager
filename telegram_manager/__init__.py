from .controller import (
    TelegramManager as _TelegramManager,
    AsyncTelegramManager as _AsyncTelegramManager,
)


class TelegramManager(_TelegramManager):
    def __init__(self):
        from .config import Config

        super().__init__(Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH, Config.TELEGRAM_PHONE_NUMBER)

class AsyncTelegramManager(_AsyncTelegramManager):
    def __init__(self):
        from .config import Config

        super().__init__(
            Config.TELEGRAM_API_ID,
            Config.TELEGRAM_API_HASH,
            Config.TELEGRAM_PHONE_NUMBER,
        )


__all__ = [
    "TelegramManager",
    "AsyncTelegramManager",
]