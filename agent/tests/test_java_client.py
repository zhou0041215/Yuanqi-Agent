from uuid import uuid4

import httpx
import pytest

from yuanqi_agent.errors import JavaApiError
from yuanqi_agent.java_client import JavaApiClient
from yuanqi_agent.runtime import RequestRuntime


@pytest.mark.asyncio
async def test_java_client_rejects_oversized_response_before_json_parsing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, content=b"x" * 2_048)

    async with httpx.AsyncClient(
        base_url="http://java.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        java = JavaApiClient(client, max_response_bytes=1_024)
        with pytest.raises(JavaApiError) as captured:
            await java.request(
                "GET",
                "/api/v1/customers",
                runtime=RequestRuntime("Bearer token", "trace-limit-001", uuid4()),
            )

    assert captured.value.code == "JAVA_RESPONSE_TOO_LARGE"


@pytest.mark.asyncio
async def test_agent_audit_uses_phase_specific_idempotency_and_no_arguments() -> None:
    captured: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(
            201,
            json={"code": "OK", "message": "Success", "data": {"id": 1}},
        )

    thread_id = uuid4()
    async with httpx.AsyncClient(
        base_url="http://java.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        java = JavaApiClient(client)
        await java.record_agent_audit(
            runtime=RequestRuntime("Bearer token", "trace-audit-001", thread_id),
            tool_name="create_prescription",
            phase="WAITING_APPROVAL",
            outcome="PENDING",
            risk_level="critical",
            fingerprint="a" * 64,
        )

    assert captured is not None
    assert captured.headers["Idempotency-Key"].startswith("agent-audit-")
    payload = captured.content.decode()
    assert "targetParameters" not in payload
    assert str(thread_id) in payload
