import asyncio
import httpx
import pytest
from backend import providers

@pytest.mark.parametrize("mode", ["connect", "stream", "httpx_timeout", "unauthorized", "success"])
def test_provider_deadline_and_safe_errors(monkeypatch, mode):
    closed = []
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            if mode == "stream":
                while True:
                    await asyncio.sleep(.005)
                    yield b" "
            yield b'{"ok": true}'
        async def aclose(self):
            closed.append(True)
    async def handler(request):
        if mode == "connect": await asyncio.sleep(10)
        if mode == "httpx_timeout": raise httpx.ReadTimeout("secret must not escape")
        return httpx.Response(401 if mode == "unauthorized" else 200, stream=Stream())
    client_class = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(providers, "PROVIDER_DEADLINE_SECONDS", .04)
    async def run():
        if mode == "success":
            assert await providers.provider_request("GET", "https://synthetic.invalid") == {"ok": True}
        else:
            with pytest.raises(providers.ProviderError) as error:
                await providers.provider_request("GET", "https://synthetic.invalid")
            assert error.value.code == ("reconnect_required" if mode == "unauthorized" else "provider_timeout")
    asyncio.run(asyncio.wait_for(run(), 1))
    if mode in {"stream", "unauthorized", "success"}: assert closed


def test_calendar_deadline_keeps_outcome_unknown(monkeypatch):
    from types import SimpleNamespace
    from backend import google_calendar_transport as calendar
    async def handler(request):
        await asyncio.sleep(10)
    client_class = httpx.AsyncClient
    monkeypatch.setattr(calendar.httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(calendar, "PROVIDER_DEADLINE_SECONDS", .04)
    adapter = calendar.GoogleCalendarTransport(SimpleNamespace(id="synthetic", config={}), {"access_token": "synthetic-only"})
    async def run():
        with pytest.raises(providers.ProviderError, match="^provider_outcome_unknown$"):
            await adapter.request("POST", json={})
    asyncio.run(asyncio.wait_for(run(), 1))
