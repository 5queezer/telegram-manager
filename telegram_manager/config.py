import os

from dotenv import load_dotenv

load_dotenv()


def _raise(key):
    raise ValueError(f'Environment key "{key}" not found')


class Config:
    TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID') or _raise('TELEGRAM_API_ID'))
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH') or _raise('TELEGRAM_API_HASH')
    TELEGRAM_PHONE_NUMBER = os.getenv('TELEGRAM_PHONE_NUMBER') or _raise('TELEGRAM_PHONE_NUMBER')
