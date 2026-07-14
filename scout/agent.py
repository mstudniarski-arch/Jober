"""Wywołanie Gemini API: 2.5 Flash + grounding w Google Search."""
import logging
from dataclasses import dataclass

from google.genai import types

from scout.config import ScoutConfig

logger = logging.getLogger(__name__)

_PROMPT = """You are a job-market research agent. Find CURRENT, fully remote job \
opportunities and hidden-job-market hiring signals, worldwide, for these roles:

{roles}

Search strategy — cover ALL of these angles, not just job boards:
1. LinkedIn posts by hiring managers, team leads, and employees announcing open roles \
("we're hiring", "join my team", "DM me").
2. Company career pages with relevant openings (prefer postings NOT syndicated to big aggregators).
3. Recent funding rounds, product launches, or expansion news implying the company is hiring \
QA/test engineers — then check their careers page.
4. Recruiter and executive-search posts looking for candidates for these roles.
5. Classic job postings as a supplement — only with a direct application link.

Constraints:
- Fully remote positions only (worldwide or broad-region remote). Skip onsite/hybrid.
- Only opportunities that appear posted or active within the last {recency_days} days.
- Prefer primary sources (the company's own page, the original LinkedIn post) over aggregators.
- Do not invent anything. Every finding must come from a page you actually found via search. \
If salary is not stated, use null.

After your research, end your reply with EXACTLY ONE fenced code block labeled json:

```json
{{"findings": [
  {{
    "company": "company name",
    "project": "what the company/team builds (short)",
    "role": "job title",
    "salary": "salary or range as stated, else null",
    "apply_url": "direct URL to apply or make contact",
    "signal_type": "job_posting | linkedin_post | career_page | funding_news | recruiter_post",
    "source_url": "URL where you found the signal",
    "location": "remote scope, e.g. 'Remote (worldwide)' or 'Remote (US only)'"
  }}
]}}
```

Include up to 25 of the best findings. The JSON block must be the last thing in your reply."""


@dataclass
class ScanResult:
    text: str
    web_searches: int


def build_prompt(config: ScoutConfig) -> str:
    roles = "\n".join(f"- {role}" for role in config.roles)
    return _PROMPT.format(roles=roles, recency_days=config.recency_days)


def _count_search_queries(response) -> int:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return 0
    metadata = getattr(candidates[0], "grounding_metadata", None)
    queries = getattr(metadata, "web_search_queries", None) if metadata else None
    return len(queries or [])


def run_scan(client, config: ScoutConfig) -> ScanResult:
    response = client.models.generate_content(
        model=config.model,
        contents=build_prompt(config),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            max_output_tokens=config.max_tokens,
        ),
    )
    return ScanResult(text=response.text or "", web_searches=_count_search_queries(response))
