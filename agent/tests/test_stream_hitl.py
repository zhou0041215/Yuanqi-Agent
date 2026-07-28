import asyncio
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from yuanqi_agent.graph import build_agent_graph
from yuanqi_agent.models import (
    AgentRunRequest,
    ApprovalDecision,
    DataScope,
    ToolCall,
    VerifiedUserContext,
)
from yuanqi_agent.service import AgentService
from yuanqi_agent.tools import ToolRegistry


class MedicalJavaClient:
    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    async def get_user_context(self, authorization: str, trace_id: str) -> VerifiedUserContext:
        return VerifiedUserContext(
            user_id=1001,
            tenant_id=1,
            username="doctor",
            data_scope=DataScope.ALL,
            department_ids=[10],
            permissions=["prescription:write"],
        )

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        self.writes.append({"method": method, "path": path, **kwargs})
        return {"id": 99, "status": "PENDING"}


class UnusedSandbox:
    async def execute(self, source: str, input_data: list[dict[str, Any]]) -> Any:
        raise AssertionError("sandbox must not run")


class UnusedPlanner:
    async def plan(self, *args: Any, **kwargs: Any) -> ToolCall:
        raise AssertionError("explicit tool call must bypass planning")

    async def stream_response(self, history: list[dict[str, Any]]):
        if False:
            yield ""


def build_service() -> tuple[AgentService, MedicalJavaClient]:
    java = MedicalJavaClient()
    registry = ToolRegistry(java, UnusedSandbox())  # type: ignore[arg-type]
    graph = build_agent_graph(registry, InMemorySaver())
    return (
        AgentService(graph, java, planner=UnusedPlanner(), tool_registry=registry),  # type: ignore[arg-type]
        java,
    )


def prescription_request(thread_id) -> AgentRunRequest:
    return AgentRunRequest(
        thread_id=thread_id,
        message="开具处方",
        tool_call=ToolCall(
            name="create_prescription",
            arguments={
                "patient_id": 1,
                "doctor_name": "测试医生",
                "diagnosis": "测试",
                "drugs": "[]",
                "total_amount": 1,
            },
        ),
    )


@pytest.mark.asyncio
async def test_stream_closes_after_approval_and_reject_resume_does_not_write() -> None:
    service, java = build_service()
    thread_id = uuid4()

    initial = await asyncio.wait_for(
        collect(service.run_loop(
            prescription_request(thread_id),
            "Bearer token",
            "trace-stream-hitl-001",
        )),
        timeout=2,
    )

    assert b"event: approval" in initial
    assert java.writes == []

    resumed = await collect(service.resume_loop(
        thread_id,
        ApprovalDecision(approved=False, comment="reject"),
        "Bearer token",
        "trace-stream-hitl-002",
    ))

    assert b'"status":"rejected"' in resumed
    assert java.writes == []


@pytest.mark.asyncio
async def test_approved_resume_executes_the_persisted_write_once() -> None:
    service, java = build_service()
    thread_id = uuid4()
    await collect(service.run_loop(
        prescription_request(thread_id),
        "Bearer token",
        "trace-stream-hitl-003",
    ))

    resumed = await collect(service.resume_loop(
        thread_id,
        ApprovalDecision(approved=True, comment="approve"),
        "Bearer token",
        "trace-stream-hitl-004",
    ))

    assert b'"status":"completed"' in resumed
    assert len(java.writes) == 1
    assert java.writes[0]["method"] == "POST"
    assert java.writes[0]["path"] == "/api/v1/prescriptions"


async def collect(iterator) -> bytes:
    return b"".join([chunk async for chunk in iterator])
