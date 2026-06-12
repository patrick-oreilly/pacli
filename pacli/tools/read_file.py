from pacli.sandbox import Sandbox


class ReadFileTool:
    name = "read_file"
    schema = {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read",
                    }
                },
                "required": ["path"],
            },
        },
    }

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def __call__(self, path: str) -> str:
        return await self._sandbox.read_file(path)
