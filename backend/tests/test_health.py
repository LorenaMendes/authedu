"""Contract tests for the process liveness endpoint."""

import asyncio

from httpx import ASGITransport, AsyncClient, Response

from authedu_api.main import app


async def request_health() -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/health")


def test_health_reports_process_liveness_without_sensitive_data() -> None:
    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
