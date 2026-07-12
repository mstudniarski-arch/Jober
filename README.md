# Hidden Job Scout

Agent AI, który **raz dziennie** przeszukuje internet i wypisuje do repozytorium
raport ze **zdalnymi ofertami pracy z całego świata** oraz sygnałami tzw.
**ukrytego rynku pracy** (oferty nigdy niepublikowane na portalach) dla ról
QA / SDET / tester — w tym **AI tester, AI test engineer, AI SDET**.

Wyszukiwanie wykonuje model **Claude Opus 4.8** przez serwerowe narzędzie web
search Anthropic — nie potrzebujesz żadnego dodatkowego API do szukania ani
scrapera. Wystarczy klucz `ANTHROPIC_API_KEY`.

---

## Jak to działa

```
  config.yaml ──┐
  (role, limit) │
                ▼
        ┌───────────────────────────────────────────────┐
        │  Claude Opus 4.8  +  web_search_20260209        │
        │  Szuka wg strategii ukrytego rynku pracy:       │
        │   • posty hiring managerów na LinkedIn          │
        │   • strony karier firm (poza agregatorami)      │
        │   • newsy o finansowaniu / ekspansji → kariera  │
        │   • posty rekruterów / executive search         │
        │   • klasyczne ogłoszenia z linkiem do aplikacji │
        └───────────────────────────────────────────────┘
                │  zwraca JSON: firma, projekt, rola,
                │  zarobki, link do aplikowania, źródło
                ▼
        ┌──────────────────┐     porównanie z data/seen.json
        │  Deduplikacja     │◄─── (to, co już było w poprzednich
        └──────────────────┘      raportach, nie wraca)
                │  tylko nowe znaleziska
                ▼
        reports/RRRR-MM-DD.md   ← gotowy raport Markdown
```

Jeden przebieg = jedno wywołanie API. Skrypt:

1. czyta `config.yaml` (lista ról, limit wyszukiwań) i `data/seen.json` (historia),
2. każe modelowi wyszukać aktualne (≤ 30 dni) zdalne oferty dla podanych ról,
3. odbiera listę znalezisk w formacie JSON,
4. wyrzuca duplikaty względem poprzednich dni,
5. renderuje raport `reports/RRRR-MM-DD.md`, pogrupowany po typie sygnału,
6. dopisuje nowe pozycje do `data/seen.json`.

---

## Przykładowy raport

Tak wygląda wygenerowany plik `reports/2026-07-12.md` (tu z przykładowymi
danymi — realny przebieg wypełnia go tym, co znajdzie w sieci):

```markdown
# Hidden Job Scout — raport 2026-07-12

## Posty na LinkedIn

### Testly — Test Automation Engineer

- **Firma:** Testly
- **Projekt:** CI/CD testing SaaS
- **Rola:** Test Automation Engineer
- **Zarobki:** —
- **Lokalizacja:** Remote (EU)
- **Link do aplikowania:** https://linkedin.com/posts/jane-doe-hiring

## Strony karier firm

### Nimbus AI — AI SDET

- **Firma:** Nimbus AI
- **Projekt:** LLM eval platform
- **Rola:** AI SDET
- **Zarobki:** $140k-180k
- **Lokalizacja:** Remote (worldwide)
- **Link do aplikowania:** https://nimbus.ai/careers/ai-sdet
- **Źródło:** https://nimbus.ai/careers

---
*Wyszukiwań web: 18 · Nowe znaleziska: 2 · Odfiltrowane duplikaty: 4*
```

Każde znalezisko ma pola: **Firma**, **Projekt** (czym firma/zespół się zajmuje),
**Rola**, **Zarobki** (jeśli podane, inaczej `—`), **Lokalizacja**, **Link do
aplikowania** oraz — gdy inny niż link aplikacji — **Źródło**. Sekcje pogrupowane
po typie sygnału: *Posty na LinkedIn*, *Strony karier firm*, *Sygnały finansowania
i ekspansji*, *Rekruterzy*, *Ogłoszenia o pracę*, *Inne sygnały*.

---

## Struktura projektu

```
hidden-job-scout/
├── config.yaml                 # role, limit wyszukiwań, model — tu edytujesz
├── scout/
│   ├── main.py                 # entrypoint: orkiestracja przebiegu
│   ├── agent.py                # wywołanie Opus 4.8 + web search
│   ├── parsing.py              # wyciąganie znalezisk z JSON
│   ├── dedup.py                # deduplikacja (data/seen.json)
│   ├── report.py               # render raportu Markdown
│   └── config.py               # wczytanie config.yaml
├── data/seen.json              # historia (żeby oferty się nie powtarzały)
├── reports/                    # tu lądują dzienne raporty .md
├── tests/                      # 28 testów (bez wywołań prawdziwego API)
├── .github/workflows/daily-scan.yml   # cron w chmurze
└── scripts/                    # uruchamianie lokalne (launchd + run.sh)
```

---

## Szybki start — jak przetestować

```bash
cd /Users/mski/Developer/hidden-job-scout

# 1. Środowisko (jednorazowo)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Testy jednostkowe — nie kosztują nic, nie ruszają sieci
.venv/bin/pytest            # → 28 passed

# 3. Prawdziwy przebieg (kosztuje ~$0.5–1, potrzebuje klucza API)
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
bash scripts/run.sh         # zapisze reports/<dzisiejsza-data>.md i zrobi commit
```

Po kroku 3 otwórz najnowszy plik w `reports/` i sprawdź znaleziska oraz linki.

> **Podgląd formatu bez kosztu API:** żeby zobaczyć, jak wygląda render raportu,
> bez wywołania modelu:
> ```bash
> .venv/bin/python -c "from datetime import date; from scout.parsing import Finding; from scout.report import render_report; print(render_report([Finding(company='Nimbus AI', role='AI SDET', apply_url='https://nimbus.ai/jobs/1', project='LLM eval', salary='\$150k', signal_type='career_page', location='Remote (worldwide)')], date.today(), 12, 0))"
> ```

---

## Konfiguracja

Wszystko w [`config.yaml`](config.yaml) — bez zmian w kodzie:

| Pole | Znaczenie | Domyślnie |
|------|-----------|-----------|
| `roles` | Lista wyszukiwanych ról — dopisz/zmień dowolną | SDET, QA, tester, …, AI tester, AI test engineer, AI SDET |
| `max_web_searches` | Limit wyszukiwań web na przebieg (steruje kosztem) | `20` |
| `recency_days` | Pomija oferty starsze niż tyle dni | `30` |
| `model` | Model Anthropic | `claude-opus-4-8` |

**Klucz API:** zmienna środowiskowa `ANTHROPIC_API_KEY` — lokalnie w pliku `.env`
(w `.gitignore`, nie trafia do repo), w GitHub Actions jako sekret repozytorium.

---

## Harmonogram — wybierz jedno

**GitHub Actions** (zalecane — działa niezależnie od tego, czy Mac jest włączony):

1. Wypchnij repo na GitHub (prywatne).
2. Settings → Secrets and variables → Actions → dodaj sekret `ANTHROPIC_API_KEY`.
3. Workflow [`daily-scan.yml`](.github/workflows/daily-scan.yml) odpala się codziennie
   o 07:00 UTC, robi skan i commituje raport do repo. Można też odpalić ręcznie
   z zakładki *Actions* (przycisk *Run workflow*).

**Lokalnie na Macu (launchd)** — Mac musi być włączony o 08:00:

```bash
cp scripts/com.mski.hidden-job-scout.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mski.hidden-job-scout.plist
```

---

## Koszt

Przy domyślnym limicie 20 wyszukiwań/dzień: szacunkowo **$0.5–1/dzień**
(~$15–30/mies.) — $10/1000 wyszukiwań web + tokeny Opus 4.8. Budżet zmniejszasz
lub zwiększasz jedną liczbą (`max_web_searches`).

---

## Testy

```bash
.venv/bin/pytest
```

28 testów jednostkowych (parsowanie JSON, deduplikacja, render raportu, obsługa
`pause_turn`, ścieżka błędu), żaden nie wywołuje prawdziwego API — bezpieczne do
uruchamiania w kółko.
