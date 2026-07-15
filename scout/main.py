"""Entrypoint: jeden dzienny przebieg skanu."""
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path

import os

from google import genai
from google.genai import errors as genai_errors

from scout.agent import run_scan
from scout.config import load_config
from scout.dedup import filter_new, finding_key, load_seen, save_seen
from scout.parsing import ParseError, extract_findings
from scout.report import render_report
from scout.verify import verify_findings

logger = logging.getLogger("scout")

# Odstępy między ponowieniami przy przejściowych błędach API (503/429) — sekundy.
_RETRY_DELAYS = (60, 120, 240)


def _is_transient(error: genai_errors.APIError) -> bool:
    """5xx (przeciążenie po stronie Google) i 429 (rate limit) warto ponowić."""
    return isinstance(error, genai_errors.ServerError) or getattr(error, "code", None) == 429


def _scan_with_retry(client, config, sleep=time.sleep, **scan_kwargs):
    """run_scan() z ponowieniami: do 4 prób, odstępy 60/120/240 s.

    Ponawia wyłącznie błędy przejściowe; inne propaguje od razu.
    """
    for attempt, delay in enumerate([*_RETRY_DELAYS, None], start=1):
        try:
            return run_scan(client, config, **scan_kwargs)
        except genai_errors.APIError as e:
            if not _is_transient(e) or delay is None:
                raise
            logger.warning(
                "Przejściowy błąd API %s (próba %d/%d) — ponawiam za %d s",
                e.code, attempt, len(_RETRY_DELAYS) + 1, delay,
            )
            sleep(delay)


def _drop_senior(findings):
    kept = [f for f in findings if "senior" not in f.role.lower()]
    if len(kept) != len(findings):
        logger.info("Sekcja AI: odrzucono %d ofert z 'Senior' w tytule", len(findings) - len(kept))
    return kept


def _parse_section(text, reports_dir, report_date, label):
    """Zwraca (znaleziska, czy_był_błąd); przy błędzie zapisuje raport awaryjny."""
    try:
        return extract_findings(text), False
    except ParseError as e:
        logger.warning("Nieparsowalna odpowiedź sekcji %s (%s) — zapisuję raport awaryjny", label, e)
        suffix = "-raw.md" if label == "qa" else f"-{label}-raw.md"
        raw_path = reports_dir / f"{report_date.isoformat()}{suffix}"
        raw_path.write_text(text, encoding="utf-8")
        return [], True


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


def run(config_path="config.yaml", client=None, report_date=None, verify=None) -> int:
    config = load_config(config_path)
    report_date = report_date or date.today()
    _setup_logging(config.logs_dir, report_date)
    client = client or _make_client()
    verify = verify or verify_findings
    reports_dir = Path(config.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Start skanu: %d ról QA + %d ról AI, model %s",
                len(config.roles), len(config.ai_roles), config.model)
    result = _scan_with_retry(client, config)
    findings, qa_failed = _parse_section(result.text, reports_dir, report_date, "qa")
    web_searches = result.web_searches

    ai_failed = False
    if config.ai_roles:
        ai_result = _scan_with_retry(client, config, roles=config.ai_roles, junior_only=True)
        web_searches += ai_result.web_searches
        ai_findings, ai_failed = _parse_section(ai_result.text, reports_dir, report_date, "ai")
        ai_findings = _drop_senior(ai_findings)
        for finding in ai_findings:
            finding.section = "ai"
        findings += ai_findings

    if qa_failed and (not config.ai_roles or ai_failed):
        return 0

    seen = load_seen(config.seen_file)
    new_findings = filter_new(findings, seen)
    duplicates = len(findings) - len(new_findings)

    new_findings, dead_findings = verify(new_findings)
    if dead_findings:
        logger.info("Odrzucono %d ofert z martwymi/nieaktualnymi linkami", len(dead_findings))

    report_path = reports_dir / f"{report_date.isoformat()}.md"
    if report_path.exists():  # drugi przebieg tego samego dnia — nie nadpisuj
        report_path = reports_dir / f"{report_date.isoformat()}-{datetime.now().strftime('%H%M%S')}.md"
    report_path.write_text(
        render_report(new_findings, report_date, web_searches, duplicates, len(dead_findings)),
        encoding="utf-8",
    )
    seen.update(finding_key(f) for f in [*new_findings, *dead_findings])
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
            logger.error("Limit API lub wyczerpane środki: %s", e.message)
            return 3
        logger.error("Błąd API %s: %s", e.code, e.message)
        return 4
    except genai_errors.APIError as e:
        logger.error("Błąd API %s: %s", e.code, e.message)
        return 4


if __name__ == "__main__":
    sys.exit(main())
