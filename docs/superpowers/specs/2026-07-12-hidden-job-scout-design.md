# Hidden Job Scout — specyfikacja projektu

Data: 2026-07-12
Status: zatwierdzone podejście nr 1 (samodzielny skrypt Python + Anthropic API)

## Cel

Agent AI, który **raz dziennie** skanuje internet w poszukiwaniu ofert pracy i sygnałów
rekrutacyjnych z tzw. ukrytego rynku pracy (hidden job market — oferty nigdy niepublikowane
na portalach, por. artykuł lockedinai.com) dla ról testerskich/QA, i zapisuje raport
Markdown do repozytorium git.

## Zakres

- **Role (domyślne, edytowalne w `config.yaml` — można wpisać dowolną rolę):**
  SDET, QA engineer, tester, test engineer, test automation engineer, test developer,
  test lead, test manager, **AI tester, AI test engineer, AI SDET**.
- **Zasięg geograficzny:** oferty w pełni zdalne z całego świata (global remote).
- **Źródła / typy sygnałów** (w duchu „hidden job market"):
  1. posty hiring managerów i pracowników na LinkedIn („we're hiring…", „DM me"),
  2. strony karier firm (oferty nieobecne na agregatorach),
  3. newsy o rundach finansowania / ekspansji / nowych biurach → firmy prawdopodobnie rekrutujące,
  4. posty i profile rekruterów / executive search,
  5. klasyczne ogłoszenia — tylko jako uzupełnienie, z bezpośrednim linkiem do aplikowania.

## Wymagania funkcjonalne

1. Jeden przebieg dziennie (harmonogram zewnętrzny — patrz „Harmonogram").
2. Wyszukiwanie wykonuje model **`claude-opus-4-8`** przez Anthropic API (klucz
   `ANTHROPIC_API_KEY` z env), z serwerowym narzędziem **`web_search_20260209`**
   (limit `max_uses` z configu, domyślnie 20) i adaptive thinking.
3. Każde znalezisko zawiera pola:
   - **firma** (company),
   - **projekt/produkt** (project — czym firma/zespół się zajmuje),
   - **rola** (role),
   - **zarobki** (salary — jeśli dostępne, inaczej `null`),
   - **link do aplikowania** (apply_url — bezpośredni link, gdzie można aplikować
     lub skontaktować się; jeśli sygnał pośredni, link do posta/źródła),
   - typ sygnału (signal_type: job_posting / linkedin_post / career_page /
     funding_news / recruiter_post),
   - źródło (source_url), lokalizacja/uwagi o zdalności, data znalezienia.
4. **Deduplikacja:** znaleziska z poprzednich dni (klucz: znormalizowany apply_url,
   fallback: firma+rola) trzymane w `data/seen.json`; powtórki nie trafiają do nowych raportów.
5. **Raport:** `reports/YYYY-MM-DD.md` — tabela/sekcje po typie sygnału, pola po polsku
   (Firma, Projekt, Rola, Zarobki, Link), na końcu krótkie podsumowanie przebiegu
   (liczba wyszukiwań, liczba nowych znalezisk, liczba odfiltrowanych duplikatów).
6. **Konfigurowalna rola:** lista `roles` w `config.yaml`; zmiana nie wymaga zmian w kodzie.

## Architektura

```
hidden-job-scout/
├── config.yaml              # role, limit wyszukiwań, model, ścieżki
├── scout/
│   ├── __init__.py
│   ├── main.py              # entrypoint: orchestracja przebiegu
│   ├── agent.py             # wywołanie Anthropic API (streaming, web search)
│   ├── parsing.py           # parsowanie JSON z odpowiedzi modelu (fenced block)
│   ├── dedup.py             # seen.json: load/filter/append
│   └── report.py            # render Markdown
├── data/seen.json           # stan deduplikacji (commitowany)
├── reports/                 # dzienne raporty .md
├── logs/                    # logi przebiegów (niecommitowane, .gitignore)
├── tests/                   # pytest: parsing, dedup, report (bez żywego API)
├── .github/workflows/daily-scan.yml  # cron 07:00 UTC + auto-commit raportu
├── scripts/com.mski.hidden-job-scout.plist  # launchd (alternatywa lokalna)
├── scripts/run.sh           # uruchom skan + git add/commit (dla launchd)
├── requirements.txt         # anthropic, pyyaml, pytest
└── README.md
```

### Przepływ jednego przebiegu

1. `main.py` czyta `config.yaml` + `data/seen.json`.
2. Buduje prompt: role, zakres (global remote), typy sygnałów, wymagany format
   odpowiedzi (fenced block ```json z tablicą `findings`), instrukcja pominięcia
   ofert starszych niż ~30 dni.
3. Wywołuje `client.messages.stream()` (model `claude-opus-4-8`,
   `thinking={"type": "adaptive"}`, `max_tokens=32000`,
   `tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": N}]`)
   → `get_final_message()`.
4. Parsuje JSON z ostatniego bloku tekstowego; walidacja pól.
5. Filtruje duplikaty względem `seen.json`.
6. Renderuje `reports/YYYY-MM-DD.md`; dopisuje nowe klucze do `seen.json`.
7. Commit raportu: w GitHub Actions robi to workflow; lokalnie `scripts/run.sh`.

### Format odpowiedzi modelu

Model kończy odpowiedź fenced blockiem ```json z obiektem
`{"findings": [...]}`. Świadomie **nie** używamy `output_config.format`
(structured outputs), bo web search dokleja cytowania do bloków tekstowych,
a wymuszony JSON-schema mógłby z nimi kolidować; parsowanie fenced blocku
z fallbackiem jest odporniejsze.

## Obsługa błędów

- Błędy sieci/429/5xx: automatyczne retry SDK (domyślnie 2), łańcuch wyjątków
  typowanych (RateLimitError → APIStatusError → APIConnectionError); niezerowy exit code.
- Nieparsowalny JSON: surowa odpowiedź zapisywana jako `reports/YYYY-MM-DD-raw.md`
  (raport awaryjny), exit code 0 z ostrzeżeniem w logu.
- `pause_turn` (serwerowy limit iteracji web search): kontynuacja pętli — ponowne
  wysłanie z doklejoną odpowiedzią asystenta, limit 5 kontynuacji.
- Log przebiegu: stdout + `logs/YYYY-MM-DD.log`.

## Harmonogram

- **GitHub Actions** (`daily-scan.yml`): cron `0 7 * * *`, klucz w Secrets
  (`ANTHROPIC_API_KEY`), po skanie `git commit` raportu + `seen.json` + push.
- **launchd** (alternatywa lokalna, macOS): plist uruchamia `scripts/run.sh`
  codziennie o 08:00 czasu lokalnego. Użytkownik włącza jedno z dwóch.

## Koszty i limity

- Domyślnie `max_web_searches: 20` → szacunkowo $0.5–1/dzień (~$15–30/mies.):
  $10/1000 wyszukiwań + tokeny Opus 4.8 ($5/$25 za 1M).
- Zmiana budżetu = zmiana jednej liczby w configu.

## Testy

- pytest, bez żywego API: `parsing` (poprawny/uszkodzony/brak JSON), `dedup`
  (normalizacja URL, fallback firma+rola, zapis stanu), `report` (render pól,
  puste znaleziska, brak zarobków → „—").

## Poza zakresem (świadomie)

- E-mail/dashboard (można dodać później).
- Scraping po stronie skryptu — całe wyszukiwanie robi serwerowe narzędzie Anthropic.
- Automatyczne aplikowanie na oferty.
