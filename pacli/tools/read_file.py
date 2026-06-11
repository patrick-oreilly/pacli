from pacli.policy import Policy
from pacli.sandbox import Sandbox


class ReadFileTool:
    name = "read_file"

    def __init__(self, sandbox: Sandbox, policy: Policy) -> None:
        self._sandbox = sandbox
        self._policy = policy

    async def __call__(self, path: str) -> str:
        if not self._policy.check_read_file(path):
            raise PermissionError(f"Access denied: {path}")
        return await self._sandbox.read_file(path)
