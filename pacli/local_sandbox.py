from pathlib import Path


class LocalSandbox:
    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    async def read_file(self, path: str) -> str:
        return (self._workspace_root / path).resolve().read_text(encoding="utf-8")
