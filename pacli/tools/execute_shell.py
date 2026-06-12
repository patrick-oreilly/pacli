from pacli.sandbox import Sandbox


class ExecuteShellTool:
    name = "execute_shell"
    schema = {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    }
                },
                "required": ["command"],
            },
        },
    }

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def __call__(self, command: str) -> str:
        return await self._sandbox.execute_command(command)
