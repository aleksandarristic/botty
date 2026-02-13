import httpx

from botty.config import BottyConfig


def create_async_client(config: BottyConfig) -> httpx.AsyncClient:
    timeout = httpx.Timeout(config.gohome_timeout_seconds)
    return httpx.AsyncClient(timeout=timeout, headers={"Accept": "application/json"})
