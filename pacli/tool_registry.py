from typing import Any

from pacli.tools import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        return [tool.schema for tool in self._tools.values()]

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        handler = self._tools.get(tool_name)
        if handler is None:
            raise KeyError(f"Unknown tool: {tool_name}")
        return await handler(**kwargs)
