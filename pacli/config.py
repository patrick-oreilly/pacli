import importlib.resources
import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Config:
    provider: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.2"
    loop_max_iterations: int = 20
    tools_enabled: bool = False
    approval_required_tools: list[str] = field(default_factory=lambda: ["execute_shell"])
    max_reflections: int = 3
    summary_model: str = ""
    max_chat_history_tokens: int = 64000

    def load_system_prompt(self) -> str:
        path = importlib.resources.files("pacli") / "prompts" / "system.md"
        return path.read_text(encoding="utf-8")


def _load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)
    result: dict[str, Any] = {}
    provider_cfg = data.get("provider")
    ollama_cfg: dict[str, Any] = {}
    if isinstance(provider_cfg, dict):
        result["provider"] = provider_cfg.get("default", "ollama")
        ollama_cfg = provider_cfg.get("ollama")
        if isinstance(ollama_cfg, dict):
            result["base_url"] = ollama_cfg.get("base_url", "http://localhost:11434/v1")
            result["model"] = ollama_cfg.get("model", "llama3.2")
    loop_max = data.get("loop_max_iterations")
    if not isinstance(loop_max, int):
        loop_max = ollama_cfg.get("loop_max_iterations") if isinstance(ollama_cfg, dict) else None
    if isinstance(loop_max, int):
        result["loop_max_iterations"] = loop_max

    if isinstance(data.get("max_reflections"), int):
        result["max_reflections"] = data["max_reflections"]
    if isinstance(data.get("summary_model"), str):
        result["summary_model"] = data["summary_model"]
    if isinstance(data.get("max_chat_history_tokens"), int):
        result["max_chat_history_tokens"] = data["max_chat_history_tokens"]
    
    policy_cfg = data.get("policy", {})
    if isinstance(policy_cfg, dict):
        if "requires_approval" in policy_cfg:
            result["approval_required_tools"] = policy_cfg["requires_approval"]
            
    return result


def _load_env_overrides() -> dict[str, Any]:
    result: dict[str, Any] = {}
    if provider := os.environ.get("PACLI_PROVIDER"):
        result["provider"] = provider
    if base_url := os.environ.get("OLLAMA_BASE_URL"):
        result["base_url"] = base_url
    if model := os.environ.get("OLLAMA_MODEL"):
        result["model"] = model
    if tools_approval := os.environ.get("PACLI_APPROVAL_REQUIRED"):
        result["approval_required_tools"] = [t.strip() for t in tools_approval.split(",")]
    if max_reflections := os.environ.get("PACLI_MAX_REFLECTIONS"):
        result["max_reflections"] = int(max_reflections)
    if summary_model := os.environ.get("PACLI_SUMMARY_MODEL"):
        result["summary_model"] = summary_model
    if max_chat_history_tokens := os.environ.get("PACLI_MAX_CHAT_HISTORY_TOKENS"):
        result["max_chat_history_tokens"] = int(max_chat_history_tokens)
    return result


def _git_root() -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (FileNotFoundError, OSError):
        pass
    return None


def load_config() -> Config:
    cfg = Config()

    global_path = Path.home() / ".config" / "pacli" / "config.toml"
    file_overrides: dict[str, Any] = {}
    file_overrides.update(_load_config_file(global_path))

    git_root = _git_root()
    if git_root is not None:
        repo_path = git_root / ".pacli.toml"
        file_overrides.update(_load_config_file(repo_path))

    local_path = Path.cwd() / ".pacli.toml"
    file_overrides.update(_load_config_file(local_path))

    env_overrides = _load_env_overrides()

    for key, value in {**file_overrides, **env_overrides}.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)

    return cfg
