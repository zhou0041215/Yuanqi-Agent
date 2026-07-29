from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequestRuntime:
    authorization: str
    trace_id: str
    thread_id: UUID
    user_id: int | None = None
    department_id: int | None = None
    operation_fingerprint: str | None = None

    @property
    def idempotency_key(self) -> str:
        suffix = (
            f"-{self.operation_fingerprint}"
            if self.operation_fingerprint is not None
            else ""
        )
        return f"agent-{self.thread_id}{suffix}"


_runtime: ContextVar[RequestRuntime | None] = ContextVar("yuanqi_request_runtime", default=None)


def set_runtime(runtime: RequestRuntime) -> Token[RequestRuntime | None]:
    return _runtime.set(runtime)


def reset_runtime(token: Token[RequestRuntime | None]) -> None:
    _runtime.reset(token)


def require_runtime() -> RequestRuntime:
    runtime = _runtime.get()
    if runtime is None:
        raise RuntimeError("Tool execution requires an active request runtime")
    return runtime
