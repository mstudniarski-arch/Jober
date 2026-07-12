"""Entrypoint: jeden dzienny przebieg skanu."""
import logging
import sys
from datetime import date
from pathlib import Path

import anthropic

from scout.agent import run_scan
from scout.config import load_config
from scout.dedup import filter_new, finding_key, load_seen, save_seen
from scout.parsing import ParseError, extract_findings
from scout.report import render_report

logger = logging.getLogger("scout")


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
    client = client or anthropic.Anthropic()
    reports_dir = Path(config.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Start skanu: %d ról, limit wyszukiwań %d", len(config.roles), config.max_web_searches)
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
    except anthropic.AuthenticationError:
        logger.error("Błąd uwierzytelnienia — ustaw ANTHROPIC_API_KEY (env / .env / GitHub Secret)")
        return 2
    except anthropic.RateLimitError:
        logger.error("Rate limit API — spróbuj później")
        return 3
    except anthropic.APIStatusError as e:
        logger.error("Błąd API %s: %s", e.status_code, e.message)
        return 4
    except anthropic.APIConnectionError:
        logger.error("Błąd połączenia z API Anthropic")
        return 5


if __name__ == "__main__":
    sys.exit(main())
