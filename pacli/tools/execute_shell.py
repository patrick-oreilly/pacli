from pacli.sandbox import Sandbox


class ExecuteShellTool:
    name = "execute_shell"

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def __call__(self, command: str) -> str:
        return await self._sandbox.execute_command(command)
