import hashlib
from typing import Any
from uuid import uuid4

import httpx
import orjson
from pydantic import ValidationError

from yuanqi_agent.errors import JavaApiError
from yuanqi_agent.models import JavaApiEnvelope, VerifiedUserContext
from yuanqi_agent.runtime import RequestRuntime


class JavaApiClient:
    def __init__(self, client: httpx.AsyncClient, max_response_bytes: int = 12_000_000):
        self._client = client
        self._max_response_bytes = max_response_bytes

    async def get_user_context(self, authorization: str, trace_id: str) -> VerifiedUserContext:
        data = await self.request(
            "GET",
            "/api/v1/auth/context",
            runtime=RequestRuntime(
                authorization=authorization,
                trace_id=trace_id,
                thread_id=uuid4(),
            ),
        )
        try:
            return VerifiedUserContext.model_validate_json(orjson.dumps(data))
        except ValidationError as exc:
            raise JavaApiError(
                "INVALID_JAVA_RESPONSE",
                "Java authentication context response is invalid",
                status_code=502,
                details=exc.errors(include_url=False),
            ) from exc

    async def request(
        self,
        method: str,
        path: str,
        *,
        runtime: RequestRuntime,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        write: bool = False,
        idempotency_key: str | None = None,
    ) -> Any:
        self._validate_path(path)
        headers = {
            "Authorization": runtime.authorization,
            "X-Trace-Id": runtime.trace_id,
        }
        if write:
            headers["Idempotency-Key"] = idempotency_key or runtime.idempotency_key
        try:
            response = await self._client.request(
                method,
                path,
                headers=headers,
                params=params,
                json=json,
            )
        except httpx.HTTPError as exc:
            raise JavaApiError(
                "JAVA_API_UNAVAILABLE",
                "Java business API is unavailable",
                status_code=502,
            ) from exc

        if len(response.content) > self._max_response_bytes:
            raise JavaApiError(
                "JAVA_RESPONSE_TOO_LARGE",
                "Java business API response exceeds the configured safety limit",
                status_code=502,
            )

        try:
            payload = JavaApiEnvelope.model_validate_json(response.content)
        except (ValueError, ValidationError) as exc:
            raise JavaApiError(
                "INVALID_JAVA_RESPONSE",
                "Java business API returned an invalid response",
                status_code=502,
            ) from exc
        if response.is_error or payload.code != "OK":
            raise JavaApiError(
                payload.code,
                payload.message,
                status_code=response.status_code,
                details=payload.data,
            )
        return payload.data

    async def record_agent_audit(
        self,
        *,
        runtime: RequestRuntime,
        tool_name: str,
        phase: str,
        outcome: str,
        risk_level: str,
        fingerprint: str | None = None,
    ) -> None:
        suffix = hashlib.sha256(
            f"{runtime.thread_id}:{tool_name}:{phase}:{outcome}".encode()
        ).hexdigest()[:24]
        await self.request(
            "POST",
            "/api/v1/agent-audit/events",
            runtime=runtime,
            json={
                "threadId": str(runtime.thread_id),
                "traceId": runtime.trace_id,
                "toolName": tool_name,
                "phase": phase,
                "outcome": outcome,
                "riskLevel": risk_level,
                "fingerprint": fingerprint,
            },
            write=True,
            idempotency_key=f"agent-audit-{suffix}",
        )

    def _validate_path(self, path: str) -> None:
        if not path.startswith("/api/v1/") or "://" in path or ".." in path or "\\" in path:
            raise JavaApiError(
                "INVALID_TOOL_ENDPOINT",
                "Tool endpoint is outside the Java API allowlist",
                status_code=500,
            )
