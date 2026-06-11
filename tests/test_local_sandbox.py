from pathlib import Path

from pacli.local_sandbox import LocalSandbox


async def test_local_sandbox_reads_file_within_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "test.txt"
    test_file.write_text("hello world")

    sandbox = LocalSandbox(workspace_root=str(workspace))
    content = await sandbox.read_file("test.txt")
    assert content == "hello world"
