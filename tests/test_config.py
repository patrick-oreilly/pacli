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
    assert cfg.max_reflections == 3
    assert cfg.summary_model == ""
    assert cfg.max_chat_history_tokens == 64000


def test_load_config_uses_defaults_when_no_file():
    cfg = load_config()
    assert cfg.provider == "ollama"
    assert cfg.base_url == "http://localhost:11434/v1"
    assert cfg.model == "llama3.2"
    assert cfg.loop_max_iterations == 20
    assert cfg.max_reflections == 3
    assert cfg.summary_model == ""
    assert cfg.max_chat_history_tokens == 64000


def test_load_config_from_file(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / ".config" / "pacli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """\
loop_max_iterations = 50
max_reflections = 10
summary_model = "gpt-4o-mini"
max_chat_history_tokens = 32000

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
    assert cfg.max_reflections == 10
    assert cfg.summary_model == "gpt-4o-mini"
    assert cfg.max_chat_history_tokens == 32000


def test_env_vars_override_config_file(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / ".config" / "pacli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """\
max_reflections = 10
summary_model = "file-model"
max_chat_history_tokens = 32000

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
    monkeypatch.setenv("PACLI_MAX_REFLECTIONS", "5")
    monkeypatch.setenv("PACLI_SUMMARY_MODEL", "env-summary")
    monkeypatch.setenv("PACLI_MAX_CHAT_HISTORY_TOKENS", "128000")

    cfg = load_config()
    assert cfg.provider == "openai"
    assert cfg.base_url == "http://env-url:9999/v1"
    assert cfg.model == "env-model"
    assert cfg.max_reflections == 5
    assert cfg.summary_model == "env-summary"
    assert cfg.max_chat_history_tokens == 128000


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("PACLI_PROVIDER", "openai")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env:9999/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "gpt-4")
    monkeypatch.setenv("PACLI_MAX_REFLECTIONS", "7")

    cfg = load_config()
    assert cfg.provider == "openai"
    assert cfg.base_url == "http://env:9999/v1"
    assert cfg.model == "gpt-4"
    assert cfg.max_reflections == 7


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


def test_local_file_overrides_global(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / ".config" / "pacli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """\
max_reflections = 3
summary_model = "global-summary"
max_chat_history_tokens = 64000

[provider]
default = "ollama"

[provider.ollama]
model = "global-model"
"""
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    local_file = tmp_path / "cwd" / ".pacli.toml"
    local_file.parent.mkdir(parents=True)
    local_file.write_text(
        """\
max_reflections = 1

[provider]
default = "ollama"

[provider.ollama]
model = "local-model"
"""
    )
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path / "cwd")

    cfg = load_config()
    assert cfg.model == "local-model"
    assert cfg.max_reflections == 1
    assert cfg.summary_model == "global-summary"
    assert cfg.max_chat_history_tokens == 64000


def test_missing_files_silently_skipped(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent")
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path / "also_nonexistent")

    cfg = load_config()
    assert cfg.provider == "ollama"
    assert cfg.max_reflections == 3


def test_git_root_layer_merges(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / ".config" / "pacli"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        'max_reflections = 3\n\n[provider]\ndefault = "ollama"\n\n[provider.ollama]\nmodel = "global-model"\n'
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    git_root = tmp_path / "repo"
    git_root.mkdir()
    (git_root / ".pacli.toml").write_text(
        'max_chat_history_tokens = 10000\n\n[provider]\ndefault = "ollama"\n\n[provider.ollama]\nmodel = "repo-model"\n'
    )

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / ".pacli.toml").write_text(
        'max_reflections = 7\n'
    )
    monkeypatch.setattr(Path, "cwd", lambda: cwd)

    import pacli.config as config_module
    original_git_root = config_module._git_root
    monkeypatch.setattr(config_module, "_git_root", lambda: git_root)

    try:
        cfg = load_config()
        assert cfg.model == "repo-model"
        assert cfg.max_reflections == 7
        assert cfg.max_chat_history_tokens == 10000
    finally:
        config_module._git_root = original_git_root


def test_non_git_repo_skipped(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / ".config" / "pacli"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        'max_reflections = 3\n\n[provider]\ndefault = "ollama"\n\n[provider.ollama]\nmodel = "global-model"\n'
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(Path, "cwd", lambda: cwd)

    import pacli.config as config_module
    original_git_root = config_module._git_root
    monkeypatch.setattr(config_module, "_git_root", lambda: None)

    try:
        cfg = load_config()
        assert cfg.model == "global-model"
        assert cfg.max_reflections == 3
    finally:
        config_module._git_root = original_git_root
