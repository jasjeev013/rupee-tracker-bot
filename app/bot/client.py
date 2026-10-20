import httpx


class BackendError(Exception):
    def __init__(self, status: int):
        super().__init__(f"backend returned {status}")
        self.status = status


class BackendClient:
    def __init__(self, base_url: str, secret: str, transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Bot-Secret": secret},
            timeout=10,
            transport=transport,
        )

    async def _request(self, method: str, path: str, **kw):
        try:
            r = await self._http.request(method, path, **kw)
        except httpx.HTTPError:
            raise BackendError(0)
        if r.status_code >= 300:
            raise BackendError(r.status_code)
        return r.json()

    async def add_expense(self, user_id: int, description: str, amount_paise: int) -> dict:
        return await self._request(
            "POST", "/expenses",
            json={"user_id": user_id, "description": description, "amount_paise": amount_paise},
        )

    async def assign_category(self, user_id: int, expense_id: int, category_id: int) -> dict:
        return await self._request(
            "POST", f"/expenses/{expense_id}/category",
            json={"user_id": user_id, "category_id": category_id},
        )

    async def categories(self, user_id: int) -> list[dict]:
        return await self._request("GET", "/categories", params={"user_id": user_id})

    async def create_category(self, user_id: int, name: str) -> dict:
        return await self._request("POST", "/categories", json={"user_id": user_id, "name": name})

    async def today(self, user_id: int) -> dict:
        return await self._request("GET", "/today", params={"user_id": user_id})

    async def stats(self, user_id: int, period: str) -> dict:
        return await self._request("GET", "/stats", params={"user_id": user_id, "period": period})

    async def feedback(self, user_id: int, message: str) -> dict:
        return await self._request("POST", "/feedback", json={"user_id": user_id, "message": message})
