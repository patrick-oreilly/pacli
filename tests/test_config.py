import os
import tempfile
from pathlib import Path

from pacli.config import Config, load_config


def test_config_defaults():
    cfg = Config()
    assert cfg.provider == "ollama"
    assert cfg.base_url == "http://localhost:11434/v1"
    assert cfg.model == "llama3.2"
    assert cfg.loop_max_iterations == 20


def test_load_config_uses_defaults_when_no_file():
    cfg = load_config()
    assert cfg.provider == "ollama"
    assert cfg.base_url == "http://localhost:11434/v1"
    assert cfg.model == "llama3.2"
    assert cfg.loop_max_iterations == 20


def test_load_config_from_file(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / ".config" / "pacli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """\
loop_max_iterations = 50

[provider]
default = "ollama"

[provider.ollama]
base_url = "http://custom:1234/v1"
model = "codellama"
"""
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cfg = load_config()
    assert cfg.provider == "ollama"
    assert cfg.base_url == "http://custom:1234/v1"
    assert cfg.model == "codellama"
    assert cfg.loop_max_iterations == 50


def test_env_vars_override_config_file(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / ".config" / "pacli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """\
[provider]
default = "ollama"

[provider.ollama]
base_url = "http://file-url:1234/v1"
model = "file-model"
"""
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("PACLI_PROVIDER", "openai")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-url:9999/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "env-model")

    cfg = load_config()
    assert cfg.provider == "openai"
    assert cfg.base_url == "http://env-url:9999/v1"
    assert cfg.model == "env-model"


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("PACLI_PROVIDER", "openai")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env:9999/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "gpt-4")

    cfg = load_config()
    assert cfg.provider == "openai"
    assert cfg.base_url == "http://env:9999/v1"
    assert cfg.model == "gpt-4"


def test_partial_env_override(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "custom-model")

    cfg = load_config()
    assert cfg.provider == "ollama"
    assert cfg.base_url == "http://localhost:11434/v1"
    assert cfg.model == "custom-model"


def test_load_system_prompt():
    cfg = Config()
    prompt = cfg.load_system_prompt()
    assert "pacli" in prompt.lower()
    assert "tool" in prompt.lower()
