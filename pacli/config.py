import importlib.resources
import os
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

    def load_system_prompt(self) -> str:
        path = importlib.resources.files("pacli") / "prompts" / "system.md"
        return path.read_text(encoding="utf-8")


def _load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)
    result: dict[str, Any] = {}
    provider_cfg = data.get("provider", {})
    ollama_cfg: dict[str, Any] = {}
    if isinstance(provider_cfg, dict):
        result["provider"] = provider_cfg.get("default", "ollama")
        ollama_cfg = provider_cfg.get("ollama", {})
        if isinstance(ollama_cfg, dict):
            result["base_url"] = ollama_cfg.get("base_url", "http://localhost:11434/v1")
            result["model"] = ollama_cfg.get("model", "llama3.2")
    loop_max = data.get("loop_max_iterations")
    if not isinstance(loop_max, int):
        loop_max = ollama_cfg.get("loop_max_iterations") if isinstance(ollama_cfg, dict) else None
    if isinstance(loop_max, int):
        result["loop_max_iterations"] = loop_max
    return result


def _load_env_overrides() -> dict[str, Any]:
    result: dict[str, Any] = {}
    if provider := os.environ.get("PACLI_PROVIDER"):
        result["provider"] = provider
    if base_url := os.environ.get("OLLAMA_BASE_URL"):
        result["base_url"] = base_url
    if model := os.environ.get("OLLAMA_MODEL"):
        result["model"] = model
    return result


def load_config() -> Config:
    cfg = Config()
    config_path = Path.home() / ".config" / "pacli" / "config.toml"
    file_overrides = _load_config_file(config_path)
    env_overrides = _load_env_overrides()

    for key, value in {**file_overrides, **env_overrides}.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)

    return cfg
