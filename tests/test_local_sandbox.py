from pathlib import Path

import pytest

from pacli.local_sandbox import LocalSandbox


async def test_local_sandbox_reads_file_within_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "test.txt"
    test_file.write_text("hello world")

    sandbox = LocalSandbox(workspace_root=str(workspace))
    content = await sandbox.read_file("test.txt")
    assert content == "hello world"


async def test_sandbox_rejects_path_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    sandbox = LocalSandbox(workspace_root=str(workspace))
    with pytest.raises(PermissionError, match="Access denied"):
        await sandbox.read_file("../secret.txt")


async def test_sandbox_rejects_empty_path(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    sandbox = LocalSandbox(workspace_root=str(workspace))
    with pytest.raises(PermissionError, match="Access denied"):
        await sandbox.read_file("")


async def test_local_sandbox_executes_command_and_returns_output(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    sandbox = LocalSandbox(workspace_root=str(workspace))
    output = await sandbox.execute_command("echo hello")
    assert output.strip() == "hello"
