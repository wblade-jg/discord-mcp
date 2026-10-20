import os

from dotenv import load_dotenv

from discord_mcp.exceptions import ConfigError

load_dotenv()


class Config:
    def __init__(self, token):
        self.bot_token = token


def load_config() -> Config:
    token = os.getenv("TOKEN")

    if not token:
        raise ConfigError("environment variable 'TOKEN' is not configured")

    return Config(token)
