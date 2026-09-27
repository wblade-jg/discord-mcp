import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self, token):
        self.bot_token = token


def load_config():
    token = os.getenv("TOKEN")

    if not token:
        raise ValueError("La variable de entorno 'TOKEN' no está configurada.")

    return Config(token)
