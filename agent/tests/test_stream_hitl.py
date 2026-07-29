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
    PatientContext,
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
            username="doctor",
            data_scope=DataScope.ALL,
            department_ids=[10],
            display_name="测试医生",
            clinical_department_id=10,
            clinical_department_name="内分泌科",
            role_code="SYSTEM_ADMIN",
            permissions=[
                "prescription:write",
                "patient:write",
                "medical-record:write",
            ],
        )

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        self.writes.append({"method": method, "path": path, **kwargs})
        if path == "/api/v1/patients":
            payload = kwargs["json"]
            return {
                "id": 100,
                "patientNo": "P-SERVER-100",
                "name": payload["name"],
                "status": "ACTIVE",
            }
        if path == "/api/v1/medical-records":
            return {
                "id": 101,
                "recordNo": "MR-SERVER-101",
                "status": "ACTIVE",
            }
        return {
            "id": 99,
            "prescriptionNo": "RX-SERVER-99",
            "status": "PENDING",
        }


class UnusedSandbox:
    async def execute(self, source: str, input_data: list[dict[str, Any]]) -> Any:
        raise AssertionError("sandbox must not run")


class UnusedPlanner:
    async def plan(self, *args: Any, **kwargs: Any) -> ToolCall:
        raise AssertionError("explicit tool call must bypass planning")

    async def stream_response(self, history: list[dict[str, Any]]):
        if False:
            yield ""


class HallucinatingPatientPlanner:
    async def plan(self, *args: Any, **kwargs: Any) -> ToolCall:
        return ToolCall(
            name="create_patient",
            arguments={
                "name": "李四",
                "gender": "MALE",
                "birth_date": "1990-01-01",
                "phone": "13800138000",
                "id_card": "110101199001011234",
            },
        )

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


def build_natural_service() -> tuple[AgentService, MedicalJavaClient]:
    java = MedicalJavaClient()
    registry = ToolRegistry(java, UnusedSandbox())  # type: ignore[arg-type]
    graph = build_agent_graph(registry, InMemorySaver())
    return (
        AgentService(
            graph,
            java,
            planner=HallucinatingPatientPlanner(),  # type: ignore[arg-type]
            tool_registry=registry,
        ),
        java,
    )


def prescription_request(thread_id) -> AgentRunRequest:
    return AgentRunRequest(
        thread_id=thread_id,
        message="开具处方",
        patient_context=patient_context(),
        tool_call=ToolCall(
            name="create_prescription",
            arguments={
                "diagnosis": "测试",
                "drugs": "[]",
                "total_amount": 1,
            },
        ),
    )


def patient_request(thread_id) -> AgentRunRequest:
    return AgentRunRequest(
        thread_id=thread_id,
        message="创建患者李四",
        tool_call=ToolCall(
            name="create_patient",
            arguments={
                "name": "李四",
                "gender": "UNKNOWN",
            },
        ),
    )


def medical_record_request(thread_id) -> AgentRunRequest:
    return AgentRunRequest(
        thread_id=thread_id,
        message="创建病历",
        patient_context=patient_context(),
        tool_call=ToolCall(
            name="create_medical_record",
            arguments={
                "visit_date": "2026-07-30",
                "diagnosis": "高血压",
            },
        ),
    )


def patient_context() -> PatientContext:
    return PatientContext(patient_id=1, patient_no="P-0001", name="张三")


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

    assert b"event: uiData" in initial
    assert b'"type":"approval_card"' in initial
    assert "成功".encode() not in initial
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
async def test_patient_write_without_verified_workspace_context_is_rejected() -> None:
    service, java = build_service()

    initial = await collect(service.run_loop(
        AgentRunRequest(
            message="开具处方",
            tool_call=ToolCall(
                name="create_prescription",
                arguments={
                    "patient_id": 999,
                    "diagnosis": "测试",
                    "drugs": "演示药品",
                    "total_amount": 1,
                },
            ),
        ),
        "Bearer token",
        "trace-stream-hitl-no-patient",
    ))

    assert b"PATIENT_CONTEXT_REQUIRED" in initial
    assert b"event: uiData" not in initial
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
    assert resumed.count("处方开具成功".encode()) == 1
    assert len(java.writes) == 1
    assert java.writes[0]["method"] == "POST"
    assert java.writes[0]["path"] == "/api/v1/prescriptions"


@pytest.mark.asyncio
async def test_different_writes_in_one_thread_use_distinct_idempotency_keys() -> None:
    service, java = build_service()
    thread_id = uuid4()

    await collect(service.run_loop(
        prescription_request(thread_id),
        "Bearer token",
        "trace-stream-hitl-005",
    ))
    await collect(service.resume_loop(
        thread_id,
        ApprovalDecision(approved=True, comment="approve prescription"),
        "Bearer token",
        "trace-stream-hitl-006",
    ))

    await collect(service.run_loop(
        patient_request(thread_id),
        "Bearer token",
        "trace-stream-hitl-007",
    ))
    resumed = await collect(service.resume_loop(
        thread_id,
        ApprovalDecision(approved=True, comment="approve patient"),
        "Bearer token",
        "trace-stream-hitl-008",
    ))

    assert len(java.writes) == 2
    first_runtime = java.writes[0]["runtime"]
    second_runtime = java.writes[1]["runtime"]
    assert first_runtime.idempotency_key != second_runtime.idempotency_key
    assert resumed.count("患者创建成功".encode()) == 1
    assert "李四".encode() in resumed


@pytest.mark.asyncio
async def test_natural_patient_write_removes_hallucinated_fields_before_approval() -> None:
    service, java = build_natural_service()
    initial = await collect(service.run_loop(
        AgentRunRequest(message="给我创建患者李四"),
        "Bearer token",
        "trace-stream-hitl-009",
    ))

    assert b"event: uiData" in initial
    assert b'"name":"\xe6\x9d\x8e\xe5\x9b\x9b"' in initial
    assert b'"gender":"UNKNOWN"' in initial
    assert b'"birth_date":null' in initial
    assert b'"phone":null' in initial
    assert b'"id_card":null' in initial
    assert b"13800138000" not in initial
    assert b"110101199001011234" not in initial
    assert "成功".encode() not in initial
    assert java.writes == []


@pytest.mark.asyncio
async def test_approved_medical_record_returns_one_confirmed_success() -> None:
    service, java = build_service()
    thread_id = uuid4()
    initial = await collect(service.run_loop(
        medical_record_request(thread_id),
        "Bearer token",
        "trace-stream-hitl-010",
    ))

    assert b"event: uiData" in initial
    assert java.writes == []

    resumed = await collect(service.resume_loop(
        thread_id,
        ApprovalDecision(approved=True, comment="approve record"),
        "Bearer token",
        "trace-stream-hitl-011",
    ))

    assert len(java.writes) == 1
    assert java.writes[0]["path"] == "/api/v1/medical-records"
    assert resumed.count("病历创建成功".encode()) == 1
    assert b'"status":"completed"' in resumed


async def collect(iterator) -> bytes:
    return b"".join([chunk async for chunk in iterator])
