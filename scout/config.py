"""Wczytywanie konfiguracji z config.yaml."""
from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass
class ScoutConfig:
    roles: list
    model: str = "gemini-3.5-flash"
    max_tokens: int = 32000
    recency_hours: int = 24
    reports_dir: str = "reports"
    seen_file: str = "data/seen.json"
    logs_dir: str = "logs"


def load_config(path) -> ScoutConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("roles"):
        raise ValueError("config.yaml: pole 'roles' jest wymagane i nie może być puste")
    known = {f.name for f in fields(ScoutConfig)}
    return ScoutConfig(**{k: v for k, v in data.items() if k in known})
