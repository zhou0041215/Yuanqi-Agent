from typing import Any

import pytest

from yuanqi_agent.models import AgentRunRequest, DataScope, VerifiedUserContext
from yuanqi_agent.service import AgentService


class FakeJavaClient:
    async def get_user_context(
        self,
        authorization: str,
        trace_id: str,
    ) -> VerifiedUserContext:
        del authorization, trace_id
        return VerifiedUserContext(
            user_id=1001,
            username="doctor",
            data_scope=DataScope.ALL,
            department_ids=[10],
            display_name="测试医生",
            clinical_department_id=10,
            clinical_department_name="内分泌科",
            role_code="SYSTEM_ADMIN",
            permissions=["knowledge:read"],
        )


class ForbiddenGraph:
    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("report mode must not invoke the tool graph")


class ReportOnlyPlanner:
    async def plan(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("report mode must not plan a graph tool")

    async def stream_report_response(self, history: list[dict[str, Any]]):
        assert any("检查报告解读" in item["content"] for item in history)
        yield "仅依据报告回答。"


@pytest.mark.asyncio
async def test_report_mode_never_invokes_graph_tools() -> None:
    service = AgentService(
        ForbiddenGraph(),
        FakeJavaClient(),  # type: ignore[arg-type]
        planner=ReportOnlyPlanner(),  # type: ignore[arg-type]
        tool_registry=object(),  # type: ignore[arg-type]
    )
    request = AgentRunRequest(
        mode="report",
        message="白细胞为什么偏高？",
        history=[
            {
                "role": "assistant",
                "content": "## 检查报告解读\n\n白细胞计数偏高。",
            }
        ],
    )

    content = b"".join(
        [
            chunk
            async for chunk in service.run_loop(
                request,
                "Bearer token",
                "trace-report-mode",
            )
        ]
    ).decode()

    assert "仅依据报告回答" in content
    assert "search_disease" not in content
    assert "search_knowledge" not in content


@pytest.mark.asyncio
async def test_report_mode_without_report_does_not_fall_back_to_graph() -> None:
    service = AgentService(
        ForbiddenGraph(),
        FakeJavaClient(),  # type: ignore[arg-type]
        planner=ReportOnlyPlanner(),  # type: ignore[arg-type]
        tool_registry=object(),  # type: ignore[arg-type]
    )

    content = b"".join(
        [
            chunk
            async for chunk in service.run_loop(
                AgentRunRequest(mode="report", message="帮我解读"),
                "Bearer token",
                "trace-report-empty",
            )
        ]
    ).decode()

    assert "请先上传报告" in content
    assert "不会查询医学知识图谱" in content
