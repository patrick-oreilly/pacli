from pacli.tools.execute_shell import ExecuteShellTool


class _StubSandbox:
    async def read_file(self, path: str) -> str:
        return ""
    async def execute_command(self, command: str) -> str:
        return f"output: {command}"


async def test_execute_shell_tool_delegates_to_sandbox():
    sandbox = _StubSandbox()
    tool = ExecuteShellTool(sandbox=sandbox)
    result = await tool(command="echo hi")
    assert result == "output: echo hi"
