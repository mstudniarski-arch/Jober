"""Entrypoint: jeden dzienny przebieg skanu."""
import logging
import sys
from datetime import date
from pathlib import Path

import os

from google import genai
from google.genai import errors as genai_errors

from scout.agent import run_scan
from scout.config import load_config
from scout.dedup import filter_new, finding_key, load_seen, save_seen
from scout.parsing import ParseError, extract_findings
from scout.report import render_report

logger = logging.getLogger("scout")


def _make_client() -> "genai.Client":
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Brak GEMINI_API_KEY — ustaw w pliku .env lub w sekretach GitHub Actions")
    return genai.Client(api_key=api_key)


def _setup_logging(logs_dir: str, report_date: date) -> None:
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path(logs_dir) / f"{report_date.isoformat()}.log", encoding="utf-8"),
        ],
        force=True,
    )


def run(config_path="config.yaml", client=None, report_date=None) -> int:
    config = load_config(config_path)
    report_date = report_date or date.today()
    _setup_logging(config.logs_dir, report_date)
    client = client or _make_client()
    reports_dir = Path(config.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Start skanu: %d ról, model %s", len(config.roles), config.model)
    result = run_scan(client, config)

    try:
        findings = extract_findings(result.text)
    except ParseError as e:
        logger.warning("Nieparsowalna odpowiedź (%s) — zapisuję raport awaryjny", e)
        raw_path = reports_dir / f"{report_date.isoformat()}-raw.md"
        raw_path.write_text(result.text, encoding="utf-8")
        logger.info("Raport awaryjny: %s", raw_path)
        return 0

    seen = load_seen(config.seen_file)
    new_findings = filter_new(findings, seen)
    duplicates = len(findings) - len(new_findings)

    report_path = reports_dir / f"{report_date.isoformat()}.md"
    report_path.write_text(
        render_report(new_findings, report_date, result.web_searches, duplicates),
        encoding="utf-8",
    )
    seen.update(finding_key(f) for f in new_findings)
    save_seen(config.seen_file, seen)
    logger.info("Raport: %s (%d nowych, %d duplikatów)", report_path, len(new_findings), duplicates)
    return 0


def main() -> int:
    try:
        return run()
    except genai_errors.ClientError as e:
        if e.code in (401, 403):
            logger.error("Błąd uwierzytelnienia — sprawdź GEMINI_API_KEY")
            return 2
        if e.code == 429:
            logger.error("Rate limit API — spróbuj później")
            return 3
        logger.error("Błąd API %s: %s", e.code, e.message)
        return 4
    except genai_errors.APIError as e:
        logger.error("Błąd API %s: %s", e.code, e.message)
        return 4


if __name__ == "__main__":
    sys.exit(main())
