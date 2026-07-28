from pathlib import Path

from yuanqi_agent.config import Settings
from yuanqi_agent.sandbox.docker_runner import DockerSandbox


def test_docker_command_enforces_physical_isolation(tmp_path: Path) -> None:
    command = DockerSandbox(Settings()).build_command(tmp_path.resolve())

    assert command[:3] == ["docker", "run", "--rm"]
    assert _option(command, "--network") == "none"
    assert "--read-only" in command
    assert _option(command, "--cap-drop") == "ALL"
    assert _option(command, "--security-opt") == "no-new-privileges"
    assert _option(command, "--pids-limit") == "64"
    assert _option(command, "--memory") == "512m"
    assert _option(command, "--user") == "10001:10001"
    assert "target=/workspace,readonly" in _option(command, "--mount")
    assert command[-1] == "yuanqi-agent-sandbox:local"


def _option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]
