# Hidden Job Scout

Agent AI, który raz dziennie skanuje internet (Claude Opus 4.8 + serwerowe
wyszukiwanie web Anthropic) w poszukiwaniu **zdalnych ofert pracy z całego
świata** i sygnałów tzw. ukrytego rynku pracy dla ról QA/SDET/test — i zapisuje
raport Markdown do `reports/`.

## Jak to działa

1. Jedno wywołanie API: `claude-opus-4-8` z narzędziem `web_search_20260209`
   (limit wyszukiwań w `config.yaml`). Model szuka: postów hiring managerów na
   LinkedIn, stron karier firm, newsów o finansowaniu/ekspansji, postów
   rekruterów i klasycznych ogłoszeń z bezpośrednim linkiem.
2. Znaleziska (firma, projekt, rola, zarobki, link do aplikowania) wracają jako
   JSON, są odfiltrowywane z duplikatów (`data/seen.json`) i renderowane do
   `reports/RRRR-MM-DD.md`.

## Konfiguracja

- **Role**: edytuj listę `roles` w [config.yaml](config.yaml) — dowolna rola,
  bez zmian w kodzie.
- **Budżet**: `max_web_searches` (domyślnie 20 ≈ $0.5–1/dzień).
- **Klucz API**: zmienna `ANTHROPIC_API_KEY` (lokalnie plik `.env`, w GitHub
  Actions sekret repo).

## Uruchomienie ręczne

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
bash scripts/run.sh
```

## Harmonogram — wybierz jedno

**GitHub Actions** (zalecane — działa bez włączonego komputera):
1. Wypchnij repo na GitHub (prywatne).
2. Settings → Secrets and variables → Actions → dodaj `ANTHROPIC_API_KEY`.
3. Workflow `daily-scan.yml` odpala się codziennie 07:00 UTC i commituje raport.

**Lokalnie (launchd, macOS)** — Mac musi być włączony o 08:00:
```bash
cp scripts/com.mski.hidden-job-scout.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mski.hidden-job-scout.plist
```

## Testy

```bash
.venv/bin/pytest
```
(28 testów, bez wywołań prawdziwego API)
