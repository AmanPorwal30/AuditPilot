# AuditPilot: Autonomous AI Technical SEO Audit Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AuditPilot** is an autonomous AI-powered technical SEO audit agent engineered for **Cynbit Technologies Private Limited**.

Give AuditPilot a website URL; it crawls the site using polite asynchronous workers, executes 27 deterministic SEO checks across On-Page, Technical, Content, and Performance categories, calculates an explainable composite audit score, and leverages Google Gemini / Groq free-tier LLMs to synthesize a prioritized, client-ready action plan with high-impact quick wins.

---

## Key Features

- **27 Deterministic SEO Checks:** Full coverage across on-page tags, headings, internal link graphs, robots.txt, sitemaps, structured data (JSON-LD), thin/duplicate content, readability, and Core Web Vitals.
- **Strict Fact Grounding:** Deterministic code uncovers the facts; the LLM only interprets and prioritizes. Zero hallucinated metrics.
- **Zero-Cost Free-Tier Architecture:** Optimized for Google Gemini 1.5/2.0 Flash (1,500 RPD free tier) and Groq (30 RPM free tier) with compact token summaries (<2,500 tokens/audit).
- **Security First:** Robust SSRF prevention blocking private networks, localhost, and cloud metadata endpoints.
- **Client-Ready Reports:** Exports to interactive single-file HTML reports and clean Markdown.
- **Interactive UI & CLI:** Modern Streamlit dashboard with score gauges and Plotly breakdowns, plus headless CLI.

---

## Quickstart

```bash
# Clone the repository
git clone <repo-url>
cd "Cynbit Project"

# Install dependencies using uv
uv sync

# Configure environment variables
cp .env.example .env
# Add your GEMINI_API_KEY or GROQ_API_KEY in .env

# Run CLI audit
python -m auditpilot.cli https://cynbit.in --max-pages 10

# Launch Streamlit dashboard
streamlit run app/streamlit_app.py
```

---

## Project Structure

```text
auditpilot/
├── SPEC.md                      # Complete system specification
├── GEMINI.md                    # Engineering protocols and guidelines
├── AGENTS.md                    # Multi-agent role roster and handshake contracts
├── pyproject.toml               # Python project configuration and dependencies
├── src/auditpilot/
│   ├── models.py                # Pydantic data schemas
│   ├── validators.py            # URL normalization & SSRF protection
│   ├── crawler.py               # Async crawler with robots.txt respect
│   ├── parsers.py               # HTML, heading, and JSON-LD parsers
│   ├── checks/                  # 27 deterministic checks & registry
│   ├── scoring.py               # 0-100 penalty scoring algorithm
│   ├── llm/                     # Gemini/Groq structured output analyzer
│   ├── report/                  # Jinja2 HTML & Markdown builders
│   └── cli.py                   # Headless CLI entrypoint
├── app/
│   └── streamlit_app.py         # Streamlit dashboard
├── tests/                       # Pytest unit & integration test suite
├── examples/                    # Pre-generated sample audits (cynbit.in)
└── docs/                        # Strategic & technical reports
```

