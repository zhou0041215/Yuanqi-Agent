import json

import httpx
import pytest

from yuanqi_agent.errors import AgentError
from yuanqi_agent.planner import HttpIntentPlanner, OllamaIntentPlanner


def available_tools() -> list[dict]:
    return [
        {
            "name": "list_patients",
            "description": "List accessible patients",
            "access": "read",
            "riskLevel": "low",
            "requiredPermission": "patient:read",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]


@pytest.mark.asyncio
async def test_http_planner_receives_schemas_without_user_jwt() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer planner-service-key"
        assert "user-secret-jwt" not in request.content.decode()
        payload = json.loads(request.content)
        assert payload["tools"][0]["name"] == "list_patients"
        assert payload["responseSchema"]["properties"]["toolCall"]
        return httpx.Response(
            200,
            json={"toolCall": {"name": "list_patients", "arguments": {}}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        planner = HttpIntentPlanner(
            client,
            "http://planner.internal/v1/plan",
            "planner-service-key",
        )
        call = await planner.plan("List patients", available_tools())

    assert call.name == "list_patients"


@pytest.mark.asyncio
async def test_http_planner_cannot_select_tool_outside_permission_filtered_list() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={"toolCall": {"name": "change_customer_owner", "arguments": {}}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        planner = HttpIntentPlanner(client, "http://planner.internal/v1/plan")
        with pytest.raises(AgentError, match="unavailable to this user") as captured:
            await planner.plan("Change owner", available_tools())

    assert captured.value.status_code == 403


@pytest.mark.asyncio
async def test_ollama_planner_uses_permission_filtered_native_tool_calling() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "http://localhost:11434/api/chat"
        assert "user-secret-jwt" not in request.content.decode()
        assert payload["model"] == "qwen3:8b"
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["options"]["temperature"] == 0
        assert payload["tools"][0]["function"]["name"] == "list_patients"
        assert payload["tools"][0]["function"]["parameters"]["type"] == "object"
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "index": 0,
                                    "name": "list_patients",
                                "arguments": {"page": 0, "size": 20},
                            },
                        }
                    ],
                },
                "done": True,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        planner = OllamaIntentPlanner(
            client,
            "http://localhost:11434/api/chat",
            "qwen3:8b",
        )
        call = await planner.plan("列出我能访问的客户", available_tools())

    assert call.name == "list_patients"
    assert call.arguments == {"page": 0, "size": 20}


@pytest.mark.asyncio
async def test_ollama_planner_rejects_a_response_without_exactly_one_tool() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "No call", "tool_calls": []}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        planner = OllamaIntentPlanner(
            client,
            "http://localhost:11434/api/chat",
            "qwen3:8b",
        )
        with pytest.raises(AgentError) as captured:
            await planner.plan("列出客户", available_tools())

    assert captured.value.code == "INTENT_PLANNER_UNAVAILABLE"
