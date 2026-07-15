# Hidden Job Scout

Agent AI, który **raz dziennie** przeszukuje internet i wypisuje do repozytorium
raport ze **zdalnymi ofertami pracy z całego świata** oraz sygnałami tzw.
**ukrytego rynku pracy** (oferty nigdy niepublikowane na portalach) dla ról
QA / SDET / tester — w tym **AI tester, AI test engineer, AI SDET**.
Do raportu trafiają tylko oferty opublikowane w ciągu ostatnich **24 godzin**,
bez ofert wyłącznie dla kandydatów z USA (oferty z Chin są uwzględniane, gdy
ogłoszenie jest po angielsku), posortowane **od najnowszych**.
Pod sekcją QA raport zawiera też sekcję **AI Jobs** — role juniorskie/entry AI
(Junior AI Engineer, AI Engineer, Junior Data Scientist/Analyst) z twardym
odrzucaniem ofert „Senior".

Wyszukiwanie robi **DuckDuckGo** (bez klucza), a analizę i ekstrakcję ofert
**darmowy model na Groq** (`llama-3.3-70b-versatile`, plan „forever free" bez
karty) — potrzebny tylko darmowy klucz `GROQ_API_KEY` z
[console.groq.com/keys](https://console.groq.com/keys).

---

## Jak to działa

```
  config.yaml ──┐
  (role, limit) │
                ▼
        ┌───────────────────────────────────────────────┐
        │  DuckDuckGo (wyniki ≤ 24 h)  →  Groq LLM        │
        │  (ekstrakcja)                                   │
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
        ┌──────────────────┐
        │  Weryfikacja      │  HTTP-check każdego linku:
        │  linków           │  404/410/wygasłe → odpadają
        └──────────────────┘
                │  tylko żywe oferty
                ▼
        reports/RRRR-MM-DD.md   ← gotowy raport Markdown
```

Jeden przebieg = dwa wywołania API: skan QA/SDET i skan AI Jobs (przy pustej liście `ai_roles` — jedno). Skrypt:

1. czyta `config.yaml` (lista ról) i `data/seen.json` (historia),
2. wykonuje zapytania DuckDuckGo — po jednym na rolę (filtr wyników z ostatnich
   24 h + filtr reklam); drugi, osobny skan robi to samo dla ról AI z config.yaml
   → sekcja AI Jobs (oferty z «Senior» w tytule odpadają),
3. darmowy LLM na Groq wyciąga oferty WYŁĄCZNIE z wyników wyszukiwania (URL
   kopiowany verbatim, bez zgadywania) — bez ofert wyłącznie dla kandydatów z USA;
   oferty z Chin są uwzględniane, gdy ogłoszenie jest po angielsku — i zwraca
   listę znalezisk w formacie JSON,
4. wyrzuca duplikaty względem poprzednich dni,
5. sprawdza każdy link HTTP-em i odrzuca oferty martwe lub wygasłe (404/410,
   nieosiągalne domeny, strony z komunikatem «no longer accepting applications»;
   blokady anty-botowe, np. LinkedIn, nie dyskwalifikują oferty),
6. renderuje raport `reports/RRRR-MM-DD.md`, posortowany **od najnowszych**
   (pole „Opublikowano"),
7. dopisuje nowe pozycje do `data/seen.json`.

---

## Przykładowy raport

Tak wygląda wygenerowany plik `reports/2026-07-12.md` (tu z przykładowymi
danymi — realny przebieg wypełnia go tym, co znajdzie w sieci):

```markdown
# Hidden Job Scout — raport 2026-07-12

Najświeższe zdalne oferty z całego świata, posortowane od najnowszych.

### Nimbus AI — AI SDET

- **Opublikowano:** 2026-07-12 09:30 UTC
- **Typ sygnału:** Strony karier firm
- **Firma:** Nimbus AI
- **Projekt:** LLM eval platform
- **Rola:** AI SDET
- **Zarobki:** $140k-180k
- **Lokalizacja:** Remote (worldwide)
- **Link do aplikowania:** https://nimbus.ai/careers/ai-sdet
- **Źródło:** https://nimbus.ai/careers

### Testly — Test Automation Engineer

- **Opublikowano:** 2026-07-12 06:15 UTC
- **Typ sygnału:** Posty na LinkedIn
- **Firma:** Testly
- **Projekt:** CI/CD testing SaaS
- **Rola:** Test Automation Engineer
- **Zarobki:** —
- **Lokalizacja:** Remote (EU)
- **Link do aplikowania:** https://linkedin.com/posts/jane-doe-hiring

---
*Wyszukiwań web: 18 · Nowe znaleziska: 2 · Odfiltrowane duplikaty: 4 · Martwe linki: 1*
```

Każde znalezisko ma pola: **Opublikowano** (czas publikacji oferty, UTC),
**Typ sygnału** (*Posty na LinkedIn*, *Strony karier firm*, *Sygnały finansowania
i ekspansji*, *Rekruterzy*, *Ogłoszenia o pracę*, *Inne sygnały*), **Firma**,
**Projekt** (czym firma/zespół się zajmuje), **Rola**, **Zarobki** (jeśli podane,
inaczej `—`), **Lokalizacja**, **Link do aplikowania** oraz — gdy inny niż link
aplikacji — **Źródło**.

---

## Struktura projektu

```
hidden-job-scout/
├── config.yaml                 # role, model — tu edytujesz
├── scout/
│   ├── main.py                 # entrypoint: orkiestracja przebiegu
│   ├── search.py               # zapytania DuckDuckGo (ddgs) — bez klucza
│   ├── agent.py                # ekstrakcja ofert z wyników przez LLM na Groq
│   ├── parsing.py              # wyciąganie znalezisk z JSON
│   ├── dedup.py                # deduplikacja (data/seen.json)
│   ├── report.py               # render raportu Markdown
│   └── config.py               # wczytanie config.yaml
├── data/seen.json              # historia (żeby oferty się nie powtarzały)
├── reports/                    # tu lądują dzienne raporty .md
├── tests/                      # 45 testów (bez wywołań prawdziwego API)
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
.venv/bin/pytest            # → 45 passed

# 3. Prawdziwy przebieg (potrzebuje klucza API)
echo 'GROQ_API_KEY=...' > .env
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
| `ai_roles` | Role sekcji „AI Jobs" (junior/entry; pusta lista wyłącza sekcję) | Junior AI Engineer, Junior AI, AI Engineer, Junior Data Scientist, Junior Data Analyst |
| `recency_hours` | Pomija oferty starsze niż tyle godzin | `24` |
| `model` | Model na Groq | `llama-3.3-70b-versatile` |

**Klucz API:** zmienna środowiskowa `GROQ_API_KEY` — darmowy klucz z
[console.groq.com/keys](https://console.groq.com/keys) (darmowe konto, bez karty).
Lokalnie w pliku `.env` (w `.gitignore`, nie trafia do repo), w GitHub Actions
jako sekret repozytorium.

---

## Harmonogram — wybierz jedno

**GitHub Actions** (zalecane — działa niezależnie od tego, czy Mac jest włączony):

1. Wypchnij repo na GitHub (prywatne).
2. Settings → Secrets and variables → Actions → dodaj sekret `GROQ_API_KEY`.
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

Całość jest **darmowa**: DuckDuckGo nie wymaga klucza, a Groq free tier daje
ok. 1000 zapytań do modelu dziennie — my robimy 2 (skan QA + skan AI Jobs).
Bez karty, bez billingu.

---

## Testy

```bash
.venv/bin/pytest
```

45 testów jednostkowych (wyszukiwanie DDG, parsowanie JSON, deduplikacja,
weryfikacja linków, render raportu, ponowienia przy 503/429, ścieżka błędu),
żaden nie wywołuje prawdziwego API — bezpieczne do uruchamiania w kółko.
