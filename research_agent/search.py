import httpx

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveSearch:
    def __init__(self, api_key: str, client: httpx.Client | None = None, count: int = 8):
        self._key = api_key
        self._client = client or httpx.Client(timeout=15)
        self._count = count

    def search(self, query: str) -> list[str]:
        """Возвращает адреса из ответа Brave. При ошибке сети или ключа бросает исключение."""
        response = self._client.get(
            BRAVE_URL,
            params={"q": query, "count": self._count},
            headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
        )
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])
        return [r["url"] for r in results if r.get("url")]
