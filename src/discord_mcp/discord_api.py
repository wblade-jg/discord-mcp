import random
import time
from datetime import datetime

import requests

from discord_mcp.exceptions import DiscordApiError, RateLimitExceeded
from discord_mcp.models.discord_bot import Channel, Message, MessageBulk, Server


class DiscordApiClient:
    def __init__(self, base_url, headers):
        self.base_url = base_url
        session = requests.Session()
        session.headers.update(headers)
        self.http_client = ResilientClientWrapper(session)

    def get_servers(self) -> list[Server]:
        response = self.http_client.get(self.base_url + "/users/@me/guilds", timeout=4)
        return [Server(**server) for server in response.json()]

    def get_channels(self, server_id) -> list[Channel]:
        response = self.http_client.get(self.base_url + f"/guilds/{server_id}/channels")
        return [Channel(**channel) for channel in response.json()]

    def get_messages(self, channel_id):
        response = self.http_client.get(
            self.base_url + f"/channels/{channel_id}/messages"
        )
        return MessageBulk(
            messages=[Message(**message) for message in response.json()],
            fetched_at=datetime.now(),
        )


class ResilientClientWrapper:
    def __init__(self, client, max_retries=3, base_delay=0.5, max_delay=10):
        self.client = client
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def get(self, url, timeout=4):
        attempt = 0
        wait_time = 0.0

        while True:
            if wait_time > 0:
                if wait_time > self.max_delay:
                    raise RateLimitExceeded(wait_time)
                time.sleep(wait_time)

            try:
                response = self.client.get(url, timeout=timeout)
                response.raise_for_status()
                return response

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise DiscordApiError("Could not connect to Discord API") from e
                wait_time = self._get_delay_before_next_retry(
                    attempt, max_delay=self.max_delay
                )
                continue

            except requests.exceptions.HTTPError as e:
                response = getattr(e, "response", None)
                if response is None:
                    raise DiscordApiError("Could not connect to Discord API") from e
                status_code = response.status_code
                if status_code in (500, 502, 503, 504):
                    attempt += 1
                    if attempt > self.max_retries:
                        raise DiscordApiError("Could not connect to Discord API") from e
                    wait_time = self._get_delay_before_next_retry(
                        attempt, max_delay=self.max_delay
                    )
                    continue
                elif status_code == 429:
                    attempt += 1
                    wait_time = self._get_delay_before_next_retry(
                        attempt, max_delay=self.max_delay, response=response
                    )
                    if attempt > self.max_retries and wait_time <= self.max_delay:
                        raise DiscordApiError("Could not connect to Discord API") from e
                    continue
                raise DiscordApiError(f"Discord API error {status_code}") from e

    def _parse_retry_after(self, response) -> float | None:
        headers = getattr(response, "headers", {}) or {}
        retry_after = headers.get("Retry-After", headers.get("retry-after"))
        if retry_after is None:
            return None
        try:
            return float(retry_after)
        except (TypeError, ValueError):
            return None

    def _get_delay_before_next_retry(self, attempt, max_delay=10, response=None):
        if response is not None:
            retry_after = self._parse_retry_after(response)
            if retry_after is not None:
                return retry_after
        retry_after = random.uniform(0, min(self.base_delay * 2**attempt, max_delay))
        return retry_after
