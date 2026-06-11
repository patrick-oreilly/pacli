from pathlib import Path


class Policy:
    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def check_read_file(self, path: str) -> bool:
        if not path:
            return False
        resolved = (self._workspace_root / path).resolve()
        return self._workspace_root in resolved.parents or resolved == self._workspace_root
