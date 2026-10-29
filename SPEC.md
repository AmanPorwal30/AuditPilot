# SEO Audit Agent: Build Specification for Claude Code

Prepared for Aman Porwal | Cynbit AI/ML Engineer Intern Assessment | October 30, 2026

## 1. Project Summary

**Name:** AuditPilot (working title): an AI-powered technical SEO audit agent.

**One-line pitch:** Give it a URL; it crawls the site, runs deterministic SEO checks, and uses an LLM to prioritize fixes and write a client-ready report.

**Why this for Cynbit:** Cynbit sells technical SEO, funnel optimization and AI automation, and states a direction of moving from AI as a tool to automation built around AI. An audit agent automates a billable service they already offer. The demo audits **cynbit.in** itself.

**Core design principle:** Deterministic code finds the facts. The LLM only interprets, prioritizes and writes. The LLM never invents metrics. This keeps output trustworthy and is a key point for the Technical Approach Report.

## 2. How to Use This Document with Claude Code

1. Create the repo folder and run `git init`.
2. Save this document as `SPEC.md` in the repo root.
3. Create a short `CLAUDE.md` that says: Read SPEC.md first. Follow the build phases in order. Commit after each phase. Run tests before committing.
4. Start Claude Code in the folder and paste the phase prompts from Section 11 one at a time. Review the diff after each phase.

## 3. Goals and Non-Goals

**Goals**

- Working end-to-end demo: URL in, scored report out.
- 25+ reliable SEO checks across on-page, technical, content and performance.
- LLM-generated prioritized action plan with impact and effort ratings.
- Streamlit UI plus a CLI, with exportable Markdown and HTML reports.
- Clean code, tests, README and git history.

**Non-goals (list these as Phase 2 in the report)**

- Real traffic, rankings and backlink data (needs Search Console, GA4, Ahrefs or SEMrush).
- JavaScript rendering of SPAs (note as a limitation; optional Playwright flag later).
- Auto-fixing the client site.

## 4. Inputs

| Input | Required | Notes |
| --- | --- | --- |
| Website URL | Yes | Normalized to https, validated |
| Max pages to crawl | No | Default 25, cap 50 |
| Target keywords | No | Comma-separated; enables keyword-placement checks |
| Business description | No | One or two sentences; improves LLM recommendations |
| Competitor URLs | No | Up to 2; only homepage-level comparison |
| Target region or language | No | Used for hreflang and local SEO notes |
| LLM provider and key | Yes (env) | Set in .env, never in code |

In the UI, only the URL box is visible by default. Everything else sits in an Advanced expander.

## 5. Features

### 5.1 Crawler

- Start at the given URL, follow same-domain links breadth-first up to the page limit.
- Respect robots.txt and send a clear User-Agent such as AuditPilotBot/0.1.
- Politeness delay of 0.3 to 0.5 seconds between requests; request timeout of 10 seconds; retry once.
- Concurrency via `httpx` async with a small limit (5 workers).
- Skip non-HTML content (images, PDFs, files). Record status code, redirect chain, response time, content type and size for every URL.
- **Safety (SSRF protection):** reject localhost, private IP ranges and non-http(s) schemes. Mention this in the approach report.
- Fetch `/robots.txt` and `/sitemap.xml` (and sitemap index) separately.

### 5.2 Check Catalog

Each check has an ID, category, severity (critical, warning, info), scope (page or site) and a pass/fail result with evidence (the exact URL and value).

**On-page**

| ID | Check | Rule |
| --- | --- | --- |
| OP01 | Title present | Missing = critical |
| OP02 | Title length | 30 to 60 chars; outside = warning |
| OP03 | Duplicate titles | Same title on 2+ pages = warning |
| OP04 | Meta description present | Missing = warning |
| OP05 | Meta description length | 70 to 160 chars |
| OP06 | Duplicate meta descriptions | Warning |
| OP07 | Exactly one H1 | Zero or multiple = warning |
| OP08 | Heading hierarchy | No skipped levels (H2 to H4) = info |
| OP09 | Image alt text | Percent of images missing alt; over 20 percent = warning |
| OP10 | Internal link count | Pages with fewer than 2 internal links = info |
| OP11 | Keyword placement | If keywords given: in title, H1, first 100 words |

**Technical**

| ID | Check | Rule |
| --- | --- | --- |
| TC01 | HTTPS | Site served over HTTPS; http redirects to https |
| TC02 | Status codes | 4xx and 5xx pages = critical |
| TC03 | Broken internal links | Links pointing to 4xx/5xx = critical |
| TC04 | Redirect chains | More than 1 hop = warning |
| TC05 | robots.txt | Exists, not blocking all, lists sitemap |
| TC06 | sitemap.xml | Exists, valid, URLs return 200 |
| TC07 | Canonical tag | Present and self-consistent |
| TC08 | Meta robots noindex | Unexpected noindex = critical |
| TC09 | Viewport meta | Present for mobile |
| TC10 | Structured data | JSON-LD present and parses; flag missing Organization or LocalBusiness |
| TC11 | Open Graph and Twitter tags | og:title, og:description, og:image present |
| TC12 | hreflang | Valid if region or language given |
| TC13 | URL hygiene | Length, uppercase, underscores, query strings |
| TC14 | Favicon | Present = info |

**Content**

| ID | Check | Rule |
| --- | --- | --- |
| CT01 | Word count | Under 300 words = thin content warning |
| CT02 | Duplicate or near-duplicate content | Hash or shingle similarity above 85 percent |
| CT03 | Readability | Flesch score via `textstat`; info only |
| CT04 | Top terms | TF-IDF top keywords per page, fed to the LLM for topic-gap analysis |

**Performance**

| ID | Check | Rule |
| --- | --- | --- |
| PF01 | Response time | Over 1.5 s = warning |
| PF02 | Page size | Over 2 MB HTML = warning |
| PF03 | Core Web Vitals | Google PageSpeed Insights API (mobile) for homepage plus up to 2 key pages: LCP, CLS, INP, score |

### 5.3 Scoring

- Each category score is 0 to 100: start at 100 and subtract weighted penalties (critical 10, warning 4, info 1, scaled by share of affected pages and capped per check).
- **Overall score** weights: Technical 35 percent, On-page 30 percent, Content 20 percent, Performance 15 percent.
- Show a letter grade (A to F) next to the number.
- Keep the formula in `scoring.py` with docstrings so it is explainable in the report.

### 5.4 LLM Analysis Layer

Input to the LLM is a compact JSON summary of findings, never raw HTML. The LLM produces:

1. **Executive summary** (under 120 words, plain English, non-technical reader).
2. **Prioritized action plan:** top 10 fixes, each with title, why it matters, how to fix, affected URLs (from the evidence), impact (high, medium, low), effort (high, medium, low), and a priority rank.
3. **Quick wins:** items with high impact and low effort.
4. **Content and keyword insights** from TF-IDF terms plus business description (topic gaps, suggested page titles and meta descriptions for the 3 weakest pages).
5. **Competitor comparison** (only if competitor URLs were given).

Use structured output (Pydantic schema, JSON mode or tool-calling) and validate the response. On validation failure, retry once with the error message; if it fails again, fall back to a rule-based template report so the app never crashes.

**Provider abstraction:** a small `LLMClient` interface with `generate_structured(system, user, schema)`. Implement at least two providers so the project runs on a free tier:

- Anthropic (model `claude-sonnet-5-5`, or `claude-haiku-5-5` for cheaper runs)
- Groq or Gemini free tier as the no-cost option

Select via `LLM_PROVIDER` in `.env`.

### 5.5 Report Generation

- Markdown report and a styled single-file HTML report (Jinja2 template). PDF is optional.
- Sections: cover (site, date, overall score), executive summary, score breakdown, quick wins, prioritized action plan, detailed findings by category (with URLs as evidence), crawl statistics, methodology and limitations.
- Download buttons in the UI; CLI writes to `./reports/`.

### 5.6 Streamlit UI

- Sidebar or top: URL input, Advanced expander, Run Audit button.
- Live progress bar and status text during the crawl.
- Results tabs: **Overview** (score gauge, category bars via Plotly), **Action Plan**, **Findings** (filterable table by severity, category and URL), **Pages** (crawl table with status, title, word count, load time), **Report** (preview and download).
- Session caching so reruns on the same URL do not re-crawl.
- Clear error messages (invalid URL, blocked by robots, timeout, LLM failure).

### 5.7 Cynbit Self-Audit Demo Mode

- A one-click button: Audit cynbit.in. Also ship a pre-generated sample report in `/examples` so reviewers see results without running anything or needing API keys.
- Keep the demo respectful: low crawl rate, small page limit, and mention in the report that the audit used only public pages.

## 6. Architecture

```
URL + options
   |
   v
[Validator / SSRF guard] -> [Crawler (async)] -> raw pages + headers
   |
   v
[Parsers: HTML, robots, sitemap, JSON-LD]
   |
   v
[Check engine: 25+ checks] -> findings (evidence-backed)
   |                              |
   v                              v
[Scoring]                  [Summarizer: compact JSON]
   |                              |
   +------------> [LLM layer: structured output + fallback]
                          |
                          v
            [Report builder: MD / HTML] -> [Streamlit UI / CLI]
```

## 7. Data Models (Pydantic)

```python
class PageData(BaseModel):
    url: str
    status_code: int
    final_url: str
    redirect_chain: list[str]
    response_time_ms: float
    html_size_bytes: int
    title: str | None
    meta_description: str | None
    h1s: list[str]
    headings: list[tuple[int, str]]
    word_count: int
    images_total: int
    images_missing_alt: int
    internal_links: list[str]
    canonical: str | None
    meta_robots: str | None
    json_ld_types: list[str]
    top_terms: list[str]


class Finding(BaseModel):
    check_id: str
    category: Literal["onpage", "technical", "content", "performance"]
    severity: Literal["critical", "warning", "info"]
    passed: bool
    message: str
    affected_urls: list[str]
    evidence: dict


class ActionItem(BaseModel):
    rank: int
    title: str
    why_it_matters: str
    how_to_fix: str
    affected_urls: list[str]
    impact: Literal["high", "medium", "low"]
    effort: Literal["high", "medium", "low"]


class LLMReport(BaseModel):
    executive_summary: str
    action_plan: list[ActionItem]
    quick_wins: list[str]
    content_insights: list[str]
    competitor_notes: list[str] | None
```

## 8. Prompt Design

**System prompt (outline)**

- Role: senior technical SEO consultant writing for a business owner.
- Rules: use ONLY the findings provided; do not invent metrics, rankings or traffic; every recommendation must cite affected URLs from the input; if data is missing, say so; be concise and specific; avoid jargon or explain it in one phrase.
- Output: valid JSON matching the provided schema, nothing else.

**User prompt (outline)**

- Site summary (domain, pages crawled, overall and category scores).
- Findings grouped by check ID with counts and up to 5 example URLs each.
- Optional: business description, target keywords, region, top TF-IDF terms, competitor summary.
- Task: produce executive summary, top 10 prioritized actions, quick wins, content insights.

**Techniques to mention in the report:** schema-constrained output, grounding on structured evidence, token-budget control by summarizing findings (top N URLs per check), temperature 0.2, retry-on-validation-error, deterministic fallback, and a small groundedness check (verify every URL the LLM cites exists in the crawl data and drop any that do not).

## 9. Tech Stack and Configuration

- Python 3.11+, `httpx`, `beautifulsoup4` with `lxml`, `extruct` or `json` for JSON-LD, `textstat`, `scikit-learn` (TF-IDF, similarity), `pydantic`, `tldextract`, `jinja2`, `streamlit`, `plotly`, `pandas`, `python-dotenv`, `tenacity` (retries), `pytest`, `ruff`.
- LLM SDKs: `anthropic` and `groq` (or `google-genai`).

**.env.example**

```
LLM_PROVIDER=groq
ANTHROPIC_API_KEY=
GROQ_API_KEY=
PAGESPEED_API_KEY=
MAX_PAGES_DEFAULT=25
REQUEST_DELAY_SECONDS=0.4
```

## 10. Repository Structure

```
auditpilot/
  README.md
  SPEC.md
  CLAUDE.md
  pyproject.toml (or requirements.txt)
  .env.example
  .gitignore
  src/auditpilot/
    __init__.py
    config.py
    models.py
    validators.py        # URL normalization, SSRF guard
    crawler.py
    parsers.py
    checks/
      onpage.py
      technical.py
      content.py
      performance.py
      registry.py
    scoring.py
    llm/
      base.py
      anthropic_client.py
      groq_client.py
      prompts.py
      analyzer.py        # structured output, retry, fallback, grounding check
    report/
      builder.py
      templates/report.html.j2
    cli.py
  app/streamlit_app.py
  tests/
    fixtures/            # saved HTML samples
    test_checks.py
    test_scoring.py
    test_validators.py
    test_analyzer.py
  examples/
    cynbit_audit.md
    cynbit_audit.html
  docs/
    01_AI_Opportunity_Report.md
    02_Technical_Approach_Report.md
    architecture.png
  notebooks/demo.ipynb   # Colab-friendly walkthrough
```

## 11. Build Phases and Claude Code Prompts

Paste each prompt into Claude Code, review the diff, run tests, then commit.

**Phase 0: Scaffold**

> Read SPEC.md. Set up the repo structure from Section 10 with pyproject.toml, .gitignore, .env.example, config.py and empty modules with docstrings. Add ruff and pytest config. Do not implement logic yet.

**Phase 1: Models, validation, crawler**

> Implement models.py (Section 7), validators.py (URL normalization and SSRF guard) and crawler.py per Section 5.1: async httpx, robots.txt respect, politeness delay, page limit, redirect tracking, sitemap fetching. Add tests for the validators using mocked responses.

**Phase 2: Parsers and check engine**

> Implement parsers.py to turn HTML into PageData, and the checks package implementing every check ID in Section 5.2 with a registry. Each check returns Findings with evidence. Add fixture HTML files and unit tests covering pass and fail cases for at least 15 checks.

**Phase 3: Scoring and CLI**

> Implement scoring.py per Section 5.3 and cli.py so `python -m auditpilot.cli https://example.com --max-pages 10` prints scores and top findings without any LLM. Add tests for scoring.

**Phase 4: LLM layer**

> Implement the llm package per Sections 5.4 and 8: base interface, Anthropic and Groq clients, prompts, analyzer with Pydantic validation, one retry, rule-based fallback, and the URL groundedness check. Add tests using a fake LLM client (no network).

**Phase 5: Reports**

> Implement report/builder.py and the Jinja2 HTML template per Section 5.5. Make the CLI write Markdown and HTML into ./reports/. Generate a sample report from a saved fixture crawl.

**Phase 6: Streamlit app**

> Build app/streamlit\_app.py per Section 5.6 with progress updates, tabs, Plotly charts, filters, downloads, caching and friendly errors. Add the Audit cynbit.in demo button and a mode that loads the pre-generated example report when no API key is set.

**Phase 7: Real run and polish**

> Run the full audit on https://www.cynbit.in with a 25-page limit. Save outputs to examples/. Fix any bugs found. Write the README with setup, usage, architecture diagram, screenshots, limitations and roadmap.

**Phase 8: Reports and notebook**

> Using SPEC.md and the actual code, draft docs/01\_AI\_Opportunity\_Report.md and docs/02\_Technical\_Approach\_Report.md following Section 13. Create notebooks/demo.ipynb that runs a small audit end to end in Colab.

## 12. Testing and Evaluation

- **Unit tests:** every check has at least one passing and one failing fixture; scoring and validators tested; analyzer tested with a fake LLM.
- **Ground-truth validation:** run the tool on 3 sites and compare a few findings against a trusted tool (Screaming Frog free version, Google Lighthouse). Record agreement in the approach report.
- **LLM quality checks:** schema-validity rate, groundedness (percent of cited URLs found in crawl data), and a short manual rubric (specific, actionable, correct) on 10 recommendations.
- **Robustness:** test on a site with robots.txt blocking, a site with redirects, an invalid URL, a timeout, and an LLM failure (fallback triggers).

## 13. Deliverables and Report Outlines

**Deliverable 1: AI Opportunity Report** (`docs/01_AI_Opportunity_Report.md`)

1. Company snapshot: services, products (Cynbit Studio, TenantEase, Revio), BitElevate, tech stack.
2. Industry context: AI in SEO and digital marketing, agentic automation trends, India SMB market.
3. Opportunity long list (4 to 5): SEO audit agent, lead qualification and proposal agent, Cynbit Studio repo reviewer and skill-gap planner, Revio differentiation, voice agents.
4. Scoring matrix: business value, feasibility in one day, data availability, differentiation, alignment with Cynbit's direction.
5. Selected opportunity and why; expected impact (hours saved per audit, faster sales cycle, upsell path).
6. Risks and how they are mitigated.

**Deliverable 2: AI/ML Proof of Concept** The Streamlit app, CLI, notebook and example reports from this repo, with a live demo link if possible.

**Deliverable 3: Technical Approach Report** (`docs/02_Technical_Approach_Report.md`)

1. Problem and scope.
2. Architecture diagram and component description.
3. Data pipeline: crawl, parse, check, summarize, LLM, report.
4. Model choices: why a hybrid of deterministic checks plus LLM; provider comparison (quality, cost, latency, free tier); TF-IDF for content signals.
5. Prompt engineering: system prompt rules, schema-constrained output, grounding, temperature, retries, fallback.
6. Evaluation: results from Section 12.
7. Security and ethics: SSRF guard, robots.txt respect, rate limiting, no PII, API keys in env.
8. Limitations (no JS rendering, no traffic data, crawl cap).
9. Execution plan and roadmap (Section 18), with a 30, 60, 90-day view for productionizing inside Cynbit.

## 14. Deployment

- Push to a public GitHub repo (check that `.env` is gitignored and no keys were ever committed).
- Deploy the Streamlit app on **Streamlit Community Cloud**; add API keys under Secrets. Use a free-tier LLM and keep the default page limit low.
- If deployment fails, include screenshots and a 2 to 3 minute screen recording in the README, plus the pre-generated example reports.
- Add a Colab badge in the README linking to the notebook.

## 15. Suggested Git Commit Plan

Use small commits with clear messages, for example:

- `chore: scaffold project structure and config`
- `feat: add URL validation with SSRF protection`
- `feat: async crawler with robots.txt and sitemap support`
- `feat: on-page and technical SEO checks`
- `feat: content and performance checks`
- `feat: scoring engine and CLI`
- `feat: LLM analyzer with structured output and fallback`
- `feat: HTML and Markdown report builder`
- `feat: Streamlit dashboard`
- `docs: add sample Cynbit audit and README`
- `docs: add opportunity and technical approach reports`

## 16. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Site blocks crawlers or is slow | Respect limits, timeouts, partial results with a clear warning |
| LLM returns invalid JSON | Schema validation, one retry, rule-based fallback |
| LLM hallucinates URLs or metrics | Groundedness check against crawl data; strict system prompt |
| API cost or rate limits | Compact summaries, caching, free-tier provider option |
| One-day time limit | Build phases in order; Phases 0 to 5 are the must-have core; trim UI polish first |
| JS-rendered pages look empty | Detect near-empty HTML and flag it as a limitation |

## 17. Demo Script (2 to 3 minutes)

1. State the problem: manual SEO audits take hours and the output varies.
2. Click Audit cynbit.in; show the live crawl progress.
3. Show the score overview and the biggest critical findings.
4. Open the Action Plan: quick wins first, with impact and effort.
5. Download the HTML report.
6. Close with the architecture, the grounding approach and the roadmap.

## 18. Roadmap (Phase 2 and beyond)

- Google Search Console and GA4 integration for real queries, CTR and indexing status.
- Playwright rendering for JavaScript-heavy sites.
- Scheduled re-audits with change tracking and email or Slack alerts.
- Multi-agent workflow: auditor, content writer (drafts titles, meta, schema), and ticket creator (Jira or GitHub issues).
- White-label branded PDF reports and a client dashboard for Cynbit's agency workflow.
- Embeddings plus a vector store (Pinecone, already in Cynbit's stack) for semantic content-gap analysis against competitors.
- Feed audit leads into Cynbit's CRM automation as a lead-generation funnel (free audit in, qualified lead out).

## 19. Priority Checklist (if time runs short)

**Must have:** crawler, 20+ checks, scoring, LLM action plan with fallback, Streamlit app, Cynbit sample report, README, both written reports.

**Should have:** PageSpeed integration, HTML report, tests, notebook, live deployment.

**Nice to have:** competitor comparison, TF-IDF content insights, groundedness metrics, PDF export.
