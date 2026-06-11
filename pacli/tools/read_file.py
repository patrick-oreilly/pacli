from pacli.sandbox import Sandbox


class ReadFileTool:
    name = "read_file"

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def __call__(self, path: str) -> str:
        return await self._sandbox.read_file(path)
