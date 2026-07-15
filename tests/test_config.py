from pathlib import Path

import pytest

from scout.config import ScoutConfig, load_config


def write_config(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_config_reads_roles_and_defaults(tmp_path):
    p = write_config(tmp_path, "roles:\n  - AI SDET\n  - tester\n")
    config = load_config(p)
    assert config.roles == ["AI SDET", "tester"]
    assert config.model == "llama-3.3-70b-versatile"
    assert config.max_tokens == 4096
    assert config.recency_hours == 24
    assert config.seen_file == "data/seen.json"
    assert config.ai_roles == []


def test_load_config_overrides_defaults(tmp_path):
    p = write_config(tmp_path, "roles: [QA]\nrecency_hours: 12\nmodel: gemini-2.5-pro\n")
    config = load_config(p)
    assert config.recency_hours == 12
    assert config.model == "gemini-2.5-pro"


def test_load_config_requires_roles(tmp_path):
    p = write_config(tmp_path, "max_web_searches: 5\n")
    with pytest.raises(ValueError):
        load_config(p)


def test_load_config_ignores_unknown_keys(tmp_path):
    p = write_config(tmp_path, "roles: [QA]\nfuture_option: 42\n")
    config = load_config(p)
    assert isinstance(config, ScoutConfig)


def test_repo_config_yaml_is_valid():
    config = load_config(Path(__file__).parent.parent / "config.yaml")
    assert "SDET" in config.roles
    assert "AI SDET" in config.roles
    assert "AI tester" in config.roles
    assert "AI test engineer" in config.roles
    assert "AI Engineer" in config.ai_roles
    assert "Junior AI Engineer" in config.ai_roles


def test_ai_roles_loaded_from_yaml(tmp_path):
    p = write_config(tmp_path, "roles: [QA]\nai_roles:\n  - AI Engineer\n  - Junior AI\n")
    config = load_config(p)
    assert config.ai_roles == ["AI Engineer", "Junior AI"]
