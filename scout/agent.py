"""Ekstrakcja ofert z wyników wyszukiwania (DuckDuckGo) przez darmowy LLM na Groq."""
import logging
from dataclasses import dataclass

from scout.config import ScoutConfig
from scout.search import search_offers

logger = logging.getLogger(__name__)

_SENIORITY_FILTER = (
    '- SENIORITY: junior/entry to mid level ONLY — skip any posting whose title contains '
    '"Senior", "Staff", "Principal", or "Lead".'
)

_PROMPT = """You are a job-market research assistant. Below are web search results \
(DuckDuckGo, limited to the LAST 24 HOURS) for remote job openings for these roles:

{roles}

SEARCH RESULTS (numbered; each has TITLE / URL / SNIPPET):

{results}

From ONLY these results, extract real, fully remote job offers worldwide.

Constraints:
- Fully remote positions only. Skip onsite/hybrid. EXCLUDE offers restricted to US-based
candidates ("US only", "must be authorized to work in the US", US-timezone-only). Offers open
worldwide or to broad regions (EU, EMEA, APAC, LATAM) are in scope. Include offers from
China-based companies when the posting is in English.
- Use ONLY information present in the results. Do not invent companies, salaries, or URLs.
- "apply_url" must be copied VERBATIM from a result's URL field. Never construct or guess URLs.
- Skip ads, aggregator landing pages without a specific offer, and results that are clearly
not job postings for the listed roles.
{seniority}
- If salary is not stated in the snippet, use null. If publication time is not explicit, use null.

End your reply with EXACTLY ONE fenced code block labeled json:

```json
{{"findings": [
  {{
    "company": "company name",
    "project": "what the company/team builds (short, from the snippet)",
    "role": "job title",
    "salary": "salary as stated, else null",
    "apply_url": "exact URL copied from a result",
    "signal_type": "job_posting | linkedin_post | career_page | funding_news | recruiter_post",
    "source_url": "the result URL it came from",
    "location": "remote scope, e.g. 'Remote (worldwide)' or 'Remote (EMEA)'",
    "published_at": "ISO 8601 UTC if explicit in the result, else null"
  }}
]}}
```

Include up to 25 of the best findings. The JSON block must be the last thing in your reply."""


@dataclass
class ScanResult:
    text: str
    web_searches: int


def _format_results(results) -> str:
    blocks = [f"[{i}] TITLE: {r['title']}\nURL: {r['url']}\nSNIPPET: {r['body']}"
              for i, r in enumerate(results, start=1)]
    return "\n\n".join(blocks) or "(no results)"


def build_prompt(config: ScoutConfig, roles=None, junior_only=False, results=()) -> str:
    role_list = config.roles if roles is None else roles
    roles_text = "\n".join(f"- {role}" for role in role_list)
    return _PROMPT.format(roles=roles_text, results=_format_results(list(results)),
                          seniority=_SENIORITY_FILTER if junior_only else "")


def run_scan(client, config: ScoutConfig, roles=None, junior_only=False, search_fn=None) -> ScanResult:
    role_list = config.roles if roles is None else roles
    results, query_count = search_offers(role_list, search_fn=search_fn)
    prompt = build_prompt(config, roles=role_list, junior_only=junior_only, results=results)
    completion = client.chat.completions.create(
        model=config.model,
        max_tokens=config.max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = completion.choices[0].message.content or ""
    return ScanResult(text=text, web_searches=query_count)
