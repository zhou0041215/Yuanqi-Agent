from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from yuanqi_agent.errors import AgentError
from yuanqi_agent.models import AgentState, ApprovalDecision, PendingTool
from yuanqi_agent.runtime import require_runtime
from yuanqi_agent.tools import ToolAccess, ToolRegistry


def build_agent_graph(registry: ToolRegistry, checkpointer: Any):
    async def validate_tool(state: AgentState) -> dict[str, Any]:
        call = state["requested_tool"]
        definition, arguments = registry.validate(call["name"], call["arguments"])
        permissions = set(state["user_context"].get("permissions", []))
        if definition.required_permission and definition.required_permission not in permissions:
            raise AgentError(
                "TOOL_PERMISSION_DENIED",
                f"Tool requires permission '{definition.required_permission}'",
                status_code=403,
            )
        normalized = arguments.model_dump(mode="json", by_alias=False)
        update: dict[str, Any] = {
            "normalized_arguments": normalized,
            "tool_access": definition.access.value,
            "approval_status": (
                "pending" if definition.access == ToolAccess.WRITE else "not_required"
            ),
        }
        pending = None
        if definition.access == ToolAccess.WRITE:
            pending = registry.pending_tool(definition, arguments)
            update["pending_tool"] = pending.model_dump(
                mode="json", by_alias=False
            )
        else:
            update["pending_tool"] = None
        await registry.audit(
            definition,
            require_runtime(),
            phase="WAITING_APPROVAL" if pending else "VALIDATED",
            outcome="PENDING" if pending else "ALLOWED",
            fingerprint=pending.fingerprint if pending else None,
        )
        return update

    def route_after_validation(state: AgentState) -> Literal["approval", "execute_tool"]:
        return "approval" if state["tool_access"] == ToolAccess.WRITE else "execute_tool"

    def approval(state: AgentState) -> Command[Literal["execute_tool", "reject_tool"]]:
        pending = PendingTool.model_validate(state["pending_tool"])
        decision_payload = interrupt(
            {
                "type": "approval_card",
                "tool": pending.name,
                "action": pending.action,
                "riskLevel": pending.risk_level,
                "targetParameters": pending.arguments,
                "fingerprint": pending.fingerprint,
            }
        )
        try:
            decision = ApprovalDecision.model_validate(decision_payload)
        except Exception as exc:
            raise AgentError(
                "INVALID_APPROVAL_DECISION",
                "Approval decision is invalid",
                status_code=422,
            ) from exc
        return Command(
            update={
                "approval_status": "approved" if decision.approved else "rejected",
                "approval_comment": decision.comment,
            },
            goto="execute_tool" if decision.approved else "reject_tool",
        )

    async def execute_tool(state: AgentState) -> dict[str, Any]:
        definition, _ = registry.validate(
            state["requested_tool"]["name"], state["normalized_arguments"]
        )
        if definition.access == ToolAccess.WRITE and state.get("approval_status") != "approved":
            raise AgentError(
                "WRITE_REQUIRES_APPROVAL",
                "Write tool execution was attempted without approval",
                status_code=409,
            )
        runtime = require_runtime()
        pending_raw = state.get("pending_tool")
        fingerprint = pending_raw.get("fingerprint") if isinstance(pending_raw, dict) else None
        await registry.audit(
            definition,
            runtime,
            phase="EXECUTION_STARTED",
            outcome="APPROVED" if definition.access == ToolAccess.WRITE else "RUNNING",
            fingerprint=fingerprint,
        )
        try:
            execution_runtime = (
                replace(runtime, operation_fingerprint=fingerprint)
                if definition.access == ToolAccess.WRITE and fingerprint
                else runtime
            )
            result = await registry.execute(
                definition,
                state["normalized_arguments"],
                execution_runtime,
            )
        except Exception:
            await registry.audit(
                definition,
                runtime,
                phase="EXECUTION_FINISHED",
                outcome="FAILED",
                fingerprint=fingerprint,
            )
            raise
        await registry.audit(
            definition,
            runtime,
            phase="EXECUTION_FINISHED",
            outcome="SUCCEEDED",
            fingerprint=fingerprint,
        )
        return {"result": result, "error": None}

    async def reject_tool(state: AgentState) -> dict[str, Any]:
        definition, _ = registry.validate(
            state["requested_tool"]["name"], state["normalized_arguments"]
        )
        pending_raw = state.get("pending_tool")
        fingerprint = pending_raw.get("fingerprint") if isinstance(pending_raw, dict) else None
        await registry.audit(
            definition,
            require_runtime(),
            phase="APPROVAL_FINISHED",
            outcome="REJECTED",
            fingerprint=fingerprint,
        )
        return {
            "result": {
                "approved": False,
                "message": "The proposed write operation was rejected",
                "comment": state.get("approval_comment"),
            },
            "error": None,
        }

    builder = StateGraph(AgentState)
    builder.add_node("validate_tool", validate_tool)
    builder.add_node("approval", approval)
    builder.add_node("execute_tool", execute_tool)
    builder.add_node("reject_tool", reject_tool)
    builder.add_edge(START, "validate_tool")
    builder.add_conditional_edges("validate_tool", route_after_validation)
    builder.add_edge("execute_tool", END)
    builder.add_edge("reject_tool", END)
    return builder.compile(checkpointer=checkpointer, name="yuanqi-agent")


def first_interrupt_value(result: Mapping[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__", ())
    if not interrupts:
        return None
    value = interrupts[0].value
    return value if isinstance(value, dict) else {"value": value}
