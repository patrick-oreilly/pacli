import asyncio
import subprocess
from pathlib import Path


class LocalSandbox:
    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    async def read_file(self, path: str) -> str:
        if not path:
            raise PermissionError("Access denied: empty path")
        resolved = (self._workspace_root / path).resolve()
        if not (self._workspace_root in resolved.parents or resolved == self._workspace_root):
            raise PermissionError(f"Access denied: {path}")
        return resolved.read_text(encoding="utf-8")

    async def execute_command(self, command: str, max_output_bytes: int = 10 * 1024 * 1024) -> str:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self._workspace_root,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
            raise RuntimeError(
                f"Command timed out after 300s: {command[:100]}"
            )
        stdout_text = stdout.decode()
        if len(stdout_text) > max_output_bytes:
            raise RuntimeError(
                f"Command output exceeded {max_output_bytes} bytes: {command[:100]}"
            )
        if proc.returncode != 0:
            stderr_text = stderr.decode().strip()
            raise RuntimeError(
                stderr_text or f"Command failed with exit code {proc.returncode}"
            )
        return stdout_text
