import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import orjson

from yuanqi_agent.config import Settings
from yuanqi_agent.errors import AgentError
from yuanqi_agent.security.ast_policy import AstSecurityChecker


@dataclass(frozen=True, slots=True)
class SandboxResult:
    result: Any
    chart: dict[str, Any] | None


class DockerSandbox:
    def __init__(self, settings: Settings, checker: AstSecurityChecker | None = None):
        self._settings = settings
        self._checker = checker or AstSecurityChecker()

    async def execute(self, source: str, input_data: list[dict[str, Any]]) -> SandboxResult:
        self._checker.validate(source)
        serialized_input = orjson.dumps(input_data)
        if len(serialized_input) > self._settings.sandbox_max_output_bytes:
            raise AgentError(
                "SANDBOX_INPUT_TOO_LARGE",
                "Sandbox input exceeds the configured limit",
                status_code=413,
            )

        with tempfile.TemporaryDirectory(prefix="yuanqi-sandbox-") as directory:
            workspace = Path(directory).resolve()
            (workspace / "analysis.py").write_text(source, encoding="utf-8")
            (workspace / "input.json").write_bytes(serialized_input)
            command = self.build_command(workspace)
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                raise AgentError(
                    "SANDBOX_UNAVAILABLE",
                    "Docker CLI is not available",
                    status_code=503,
                ) from exc
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._settings.sandbox_timeout_seconds,
                )
            except TimeoutError as exc:
                process.kill()
                await process.communicate()
                raise AgentError(
                    "SANDBOX_TIMEOUT",
                    "Sandbox execution exceeded the time limit",
                    status_code=422,
                ) from exc

        if len(stdout) > self._settings.sandbox_max_output_bytes:
            raise AgentError(
                "SANDBOX_OUTPUT_TOO_LARGE",
                "Sandbox output exceeds the configured limit",
                status_code=422,
            )
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="replace")[-4_000:]
            raise AgentError(
                "SANDBOX_EXECUTION_FAILED",
                "Sandbox execution failed",
                status_code=422,
                details=message,
            )
        try:
            payload = json.loads(stdout.decode("utf-8"))
            chart = payload.get("chart")
            if chart is not None and not isinstance(chart, dict):
                raise ValueError("chart must be an object")
            return SandboxResult(result=payload.get("result"), chart=chart)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise AgentError(
                "INVALID_SANDBOX_OUTPUT",
                "Sandbox returned an invalid result",
                status_code=502,
            ) from exc

    def build_command(self, workspace: Path) -> list[str]:
        mount = f"type=bind,source={workspace},target=/workspace,readonly"
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(self._settings.sandbox_max_pids),
            "--memory",
            self._settings.sandbox_memory,
            "--cpus",
            str(self._settings.sandbox_cpus),
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--user",
            "10001:10001",
            "--mount",
            mount,
            self._settings.sandbox_image,
        ]
