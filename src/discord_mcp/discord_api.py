import requests

from discord_mcp.models import Channel, Server


class DiscordApiClient:
    def __init__(self, base_url, headers):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers = headers

    def get_servers(self) -> list[Server]:
        response = self.session.get(self.base_url + "/users/@me/guilds")
        return [Server(**server) for server in response.json()]

    def get_channels(self, server_id) -> list[Channel]:
        response = self.session.get(self.base_url + f"/guilds/{server_id}/channels")
        return [Channel(**channel) for channel in response.json()]
