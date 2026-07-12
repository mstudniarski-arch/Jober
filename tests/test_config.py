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
    assert config.max_web_searches == 20
    assert config.model == "claude-opus-4-8"
    assert config.max_tokens == 32000
    assert config.recency_days == 30
    assert config.seen_file == "data/seen.json"


def test_load_config_overrides_defaults(tmp_path):
    p = write_config(tmp_path, "roles: [QA]\nmax_web_searches: 5\nmodel: claude-haiku-4-5\n")
    config = load_config(p)
    assert config.max_web_searches == 5
    assert config.model == "claude-haiku-4-5"


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
