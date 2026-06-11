from pathlib import Path

from pacli.policy import Policy


async def test_policy_allows_path_within_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    policy = Policy(workspace_root=str(workspace))
    assert policy.check_read_file("test.txt") is True


async def test_policy_rejects_path_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    policy = Policy(workspace_root=str(workspace))
    assert policy.check_read_file("../secret.txt") is False


async def test_policy_rejects_empty_path(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    policy = Policy(workspace_root=str(workspace))
    assert policy.check_read_file("") is False
