import os
import subprocess

import pytest

from yuanqi_agent.config import Settings
from yuanqi_agent.sandbox.docker_runner import DockerSandbox

pytestmark = pytest.mark.skipif(
    os.environ.get("YUANQI_RUN_DOCKER_TESTS") != "1",
    reason="set YUANQI_RUN_DOCKER_TESTS=1 when a Docker daemon is available",
)


@pytest.mark.asyncio
async def test_real_sandbox_executes_validated_pandas_without_network_mounts() -> None:
    sandbox = DockerSandbox(Settings(sandbox_timeout_seconds=60))
    output = await sandbox.execute(
        """
import pandas as pd

frame = pd.DataFrame(input_data)
result = {"total": float(frame["amount"].sum()), "rows": int(len(frame))}
chart = {"title": "Sandbox verified", "xAxis": ["total"], "series": [{"data": [result["total"]]}]}
""",
        [{"amount": 10.5}, {"amount": 20.0}],
    )

    assert output.result == {"total": 30.5, "rows": 2}
    assert output.chart == {
        "title": "Sandbox verified",
        "xAxis": ["total"],
        "series": [{"data": [30.5]}],
    }


def test_real_sandbox_network_namespace_cannot_reach_external_address() -> None:
    completed = subprocess.run(
        [
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
            "--entrypoint",
            "python",
            "yuanqi-agent-sandbox:local",
            "-I",
            "-c",
            "import socket; socket.create_connection(('1.1.1.1', 53), timeout=1)",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode != 0
