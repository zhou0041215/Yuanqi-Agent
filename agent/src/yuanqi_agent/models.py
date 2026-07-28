from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, NotRequired, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )


class DataScope(StrEnum):
    ALL = "ALL"
    DEPARTMENT = "DEPARTMENT"
    SELF = "SELF"


class VerifiedUserContext(StrictModel):
    user_id: int = Field(gt=0)
    tenant_id: int = Field(gt=0)
    username: str = Field(min_length=1, max_length=200)
    data_scope: DataScope
    department_ids: list[int] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class ChatMessage(StrictModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str = Field(min_length=1, max_length=50_000)


class ToolCall(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    arguments: dict[str, Any]


class AgentRunRequest(StrictModel):
    thread_id: UUID | None = Field(default=None, strict=False)
    mode: Literal["knowledge", "report"] = "knowledge"
    message: str = Field(min_length=1, max_length=20_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    tool_call: ToolCall | None = None


class ApprovalDecision(StrictModel):
    approved: bool
    comment: str | None = Field(default=None, max_length=2_000)


class PendingTool(StrictModel):
    name: str
    arguments: dict[str, Any]
    action: str
    risk_level: Literal["low", "medium", "high", "critical"]
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class RunStatus(StrEnum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class AgentExecution(StrictModel):
    thread_id: UUID
    status: RunStatus
    result: Any | None = None
    pending_tool: PendingTool | None = None
    approval_comment: str | None = None
    tool_name: str | None = None


class AgentState(TypedDict):
    messages: list[dict[str, Any]]
    user_context: dict[str, Any]
    requested_tool: dict[str, Any]
    normalized_arguments: NotRequired[dict[str, Any]]
    tool_access: NotRequired[Literal["read", "write"]]
    pending_tool: NotRequired[dict[str, Any] | None]
    approval_status: NotRequired[Literal["not_required", "pending", "approved", "rejected"]]
    approval_comment: NotRequired[str | None]
    result: NotRequired[Any]
    error: NotRequired[str | None]


class JavaApiEnvelope(StrictModel):
    code: str
    message: str
    data: Any | None
    trace_id: str | None = None
    timestamp: datetime | None = None


class KnowledgeGraphOverviewNode(StrictModel):
    type: Literal["KnowledgeHub", "Department"]
    name: str = Field(min_length=1, max_length=200)
    desc: str = Field(default="", max_length=500)
    knowledge_status: Literal["PUBLISHED", "STANDARDIZED"]
    disease_count: int = Field(default=0, ge=0)
    published_disease_count: int = Field(default=0, ge=0)
    reference_disease_count: int = Field(default=0, ge=0)


class KnowledgeGraphOverviewLink(StrictModel):
    source: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=200)
    rel_type: Literal["HAS_DEPARTMENT"]
    evidence: Literal["PUBLISHED"]


class KnowledgeGraphOverviewResponse(StrictModel):
    nodes: list[KnowledgeGraphOverviewNode]
    links: list[KnowledgeGraphOverviewLink]
