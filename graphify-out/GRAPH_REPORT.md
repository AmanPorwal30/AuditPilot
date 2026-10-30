# Graph Report - Cynbit Project  (2026-10-31)

## Corpus Check
- 38 files · ~37,514 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 6, .example 1, .j2 1)

## Summary
- 464 nodes · 790 edges · 29 communities (26 shown, 3 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d939fdb7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- analyzer.py
- 4. Detailed Discrete Tasks: Phase 1 through Phase 8
- crawler.py
- Website Audit Scoring Engine
- SEO Audit Agent: Build Specification for Claude Code
- SEO Audit Agent: Build Specification for Claude Code
- PageData
- registry.py
- Finding
- AsyncCrawler
- 2. Agent Roster & Domain Specializations
- builder.py
- ._crawl_with_client
- scoring.py
- normalize_url
- cli.py
- models.py
- is_safe_url
- onpage.py
- GEMINI.md
- TestAsyncCrawlerExecution
- .generate_structured
- render_category_bars
- AuditPilot: Autonomous AI Technical SEO Audit Agent
- get_mock_cynbit_results
- Settings
- auditpilot/__init__.py
- tests/__init__.py
- auditpilot

## God Nodes (most connected - your core abstractions)
1. `PageData` - 47 edges
2. `Finding` - 31 edges
3. `AsyncCrawler` - 21 edges
4. `SEOAnalyzer` - 21 edges
5. `normalize_url()` - 21 edges
6. `compute_audit_score_with_caps()` - 20 edges
7. `SEO Audit Agent: Build Specification for Claude Code` - 20 edges
8. `SEO Audit Agent: Build Specification for Claude Code` - 20 edges
9. `is_safe_url()` - 18 edges
10. `main()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `TASK-P2-02: Pluggable Check Registry Architecture` --references--> `Finding`  [INFERRED]
  TODO.md → src/auditpilot/models.py
- `TASK-P4-02: Structured Prompt Engineering & Token Budget Summarization` --references--> `LLMReport`  [INFERRED]
  TODO.md → src/auditpilot/models.py
- `Gate G0: Schema & Configuration Lock` --references--> `Settings`  [INFERRED]
  TODO.md → src/auditpilot/config.py
- `TASK-P4-03: SEO Analyzer, Cache, Validation Retry, Grounding & Fallback` --references--> `SEOAnalyzer`  [INFERRED]
  TODO.md → src/auditpilot/llm/analyzer.py
- `Gate G0: Schema & Configuration Lock` --references--> `PageData`  [INFERRED]
  TODO.md → src/auditpilot/models.py

## Import Cycles
- None detected.

## Communities (29 total, 3 thin omitted)

### Community 0 - "analyzer.py"
Cohesion: 0.05
Nodes (49): ABC, AuditPilot: Streamlit Web Dashboard. Provides interactive URL input, live crawl…, google, google_genai, Groq, json, logging, os (+41 more)

### Community 1 - "4. Detailed Discrete Tasks: Phase 1 through Phase 8"
Cohesion: 0.04
Nodes (47): AuditResult, Complete container for an end-to-end audit run., 1.1 High-Level Progress Tracker Across Phases 1 through 8, 1.2 Visual Mermaid Workflow: Sequential Gates & Parallelizable Tracks, 1. Master Execution Architecture, 2.1 Comprehensive Matrix of Touched Files Across All 8 Phases, 2.2 Strict File Ownership & Concurrency Bound Rules, 2. Collision Prevention & Concurrency Rules (+39 more)

### Community 2 - "crawler.py"
Cohesion: 0.09
Nodes (25): bs4, collections, collections_abc, httpx, ipaddress, pytest, re, socket (+17 more)

### Community 3 - "Website Audit Scoring Engine"
Cohesion: 0.07
Nodes (29): 10. Rating bands, 11. Testing and calibration, 12. Engineering and operational requirements, 13. Implementation plan for the coding agent, 14. Definition of done, 1. Core requirements, 2. Proposed audit pipeline, 3.1 Availability and reliability --- 10 points (+21 more)

### Community 4 - "SEO Audit Agent: Build Specification for Claude Code"
Cohesion: 0.07
Nodes (27): 10. Repository Structure, 11. Build Phases and Claude Code Prompts, 12. Testing and Evaluation, 13. Deliverables and Report Outlines, 14. Deployment, 15. Suggested Git Commit Plan, 16. Risks and Mitigations, 17. Demo Script (2 to 3 minutes) (+19 more)

### Community 5 - "SEO Audit Agent: Build Specification for Claude Code"
Cohesion: 0.07
Nodes (27): 10. Repository Structure, 11. Build Phases and Claude Code Prompts, 12. Testing and Evaluation, 13. Deliverables and Report Outlines, 14. Deployment, 15. Suggested Git Commit Plan, 16. Risks and Mitigations, 17. Demo Script (2 to 3 minutes) (+19 more)

### Community 6 - "PageData"
Cohesion: 0.15
Nodes (21): PageData, Raw and parsed data extracted from a single crawled URL., compute_audit_score_with_caps(), evaluate_checks_and_caps(), Execute evidence-based checks and apply critical issue caps to produce verified…, Execute evidence-based checks across the 8 categories and detect critical issue…, Tests for evidence-based scoring engine and critical issue caps., Verify that a 404 homepage hard-caps score to at most 10.0. (+13 more)

### Community 7 - "registry.py"
Cohesion: 0.13
Nodes (15): Content SEO Checks (CT01 - CT04). CT01: Thin content (word count < 300)…, Execute all content SEO checks (CT01 to CT04)., run_content_checks(), SEO Check Engine for AuditPilot. Contains 27 deterministic checks across On-…, Performance SEO Checks (PF01 - PF03). PF01: Server response time / TTFB (>1.5s…, Execute all performance and speed checks (PF01 to PF03)., run_performance_checks(), CheckRegistry (+7 more)

### Community 8 - "Finding"
Cohesion: 0.18
Nodes (16): main(), Streamlit Application Entrypoint., Any, Deterministic rule-based report generator when LLM API is unavailable., Orchestrates LLM analysis with retry, grounding verification, and fallback., Run token-budgeted analysis with grounding validation and fallback., Verify that all URLs cited by the LLM exist in the crawled dataset., SEOAnalyzer (+8 more)

### Community 9 - "AsyncCrawler"
Cohesion: 0.16
Nodes (11): Execute live async crawler with interactive Streamlit progress updates., run_live_crawl(), AsyncCrawler, _get_root_domain(), Extract same-domain hyperlinks from HTML payload., Extract root domain without external network lookups., Async crawler with concurrency throttling and robots.txt support., Initialize crawler parameters. (+3 more)

### Community 10 - "2. Agent Roster & Domain Specializations"
Cohesion: 0.13
Nodes (14): 1. Multi-Agent Framework Overview, 2.1 Lead Architect Agent (`@architect`), 2.2 Backend Engineering Agent (`@backend`), 2.3 Frontend Engineering Agent (`@frontend`), 2.4 AI/ML & Prompt Engineering Agent (`@aiml`), 2.5 QA & Reliability Engineering Agent (`@qa`), 2.6 DevOps & Release Engineering Agent (`@devops`), 2. Agent Roster & Domain Specializations (+6 more)

### Community 11 - "builder.py"
Cohesion: 0.14
Nodes (9): Path, pathlib, Report builder generating Markdown and standalone single-file HTML reports., Generates agency-quality Markdown and HTML reports from AuditResult., Render report as clean Markdown string., Render report as standalone single-file styled HTML string., Save both Markdown and HTML reports to disk. Returns: Tuple of (md_path,…, ReportBuilder (+1 more)

### Community 12 - "._crawl_with_client"
Cohesion: 0.19
Nodes (8): AsyncClient, deque, Fetch and parse XML sitemaps (including sitemap index)., Check if robots.txt allows fetching this URL., Fetch a single page with retries, timeout, and timing metrics., Perform breadth-first crawl yielding PageData objects. Args: client: Optional…, Internal crawl execution with given active client., Fetch and parse robots.txt for the domain.

### Community 13 - "scoring.py"
Cohesion: 0.20
Nodes (11): calculate_scores(), _get_letter_grade(), _get_rating_band(), Evidence-based scoring engine for AuditPilot. Implements the 100-point…, Calculate audit scores with backward compatibility for legacy and 8-category…, Map numeric 0-100 score to quality rating band., Map numeric score to traditional letter grade., Verify penalty deductions reduce scores according to category weights. (+3 more)

### Community 14 - "normalize_url"
Cohesion: 0.27
Nodes (4): normalize_url(), Normalize input URL (adds scheme if missing, strips fragments, cleans path).…, Test suite for normalize_url., TestNormalizeUrl

### Community 15 - "cli.py"
Cohesion: 0.24
Nodes (10): argparse, Namespace, main(), parse_args(), Command Line Interface (CLI) for AuditPilot. Usage: python -m auditpilot.cli…, CLI main entry point., Parse command line arguments., Execute end-to-end audit from CLI. (+2 more)

### Community 16 - "models.py"
Cohesion: 0.25
Nodes (10): BaseModel, ActionItem, AuditScore, CategoryScore, Data models for AuditPilot. Defines Pydantic schemas for crawled pages,…, Overall and category scoring breakdown with caps and confidence., A prioritized, actionable fix generated by the LLM analysis layer., Score summary for an individual audit category. (+2 more)

### Community 17 - "is_safe_url"
Cohesion: 0.29
Nodes (4): is_safe_url(), Validate URL for SSRF vulnerabilities before any network request. Rejects: -…, Test suite for SSRF protection in is_safe_url., TestIsSafeUrl

### Community 18 - "onpage.py"
Cohesion: 0.22
Nodes (8): On-Page SEO Checks (OP01 - OP11). OP01: Title present (Critical) OP02: Title…, Execute all on-page checks (OP01 to OP11) against the crawled page set., run_onpage_checks(), Tests for SEO checks and check registry., Verify onpage checks detect missing title and multiple H1s., Verify registry executes checks across all categories., test_onpage_checks_detect_violations(), test_registry_runs_all_categories()

### Community 19 - "GEMINI.md"
Cohesion: 0.25
Nodes (7): Agent workflow, Browser agent, Gemini API usage, GEMINI.md, Priority, Style, Terminal and safety

### Community 20 - "TestAsyncCrawlerExecution"
Cohesion: 0.29
Nodes (3): asyncio, Integration-style tests for crawler lifecycle with mocked transport., TestAsyncCrawlerExecution

### Community 21 - ".generate_structured"
Cohesion: 0.29
Nodes (5): Client, retry, T, Lazy initialization of Gemini Client., Generate structured Pydantic object via Gemini API. Args: system_prompt: System…

### Community 22 - "render_category_bars"
Cohesion: 0.40
Nodes (5): Render circular Plotly score gauge., Render horizontal category score comparison chart for the 8 core categories., render_category_bars(), render_score_gauge(), Figure

### Community 23 - "AuditPilot: Autonomous AI Technical SEO Audit Agent"
Cohesion: 0.40
Nodes (4): AuditPilot: Autonomous AI Technical SEO Audit Agent, Key Features, Project Structure, Quickstart

### Community 24 - "get_mock_cynbit_results"
Cohesion: 0.67
Nodes (3): get_mock_cynbit_results(), Any, Pre-computed verified sample audit data for cynbit.in demo mode.

### Community 25 - "Settings"
Cohesion: 0.67
Nodes (3): BaseSettings, Application settings for AuditPilot., Settings

## Knowledge Gaps
- **122 isolated node(s):** `auditpilot`, `Key Features`, `Quickstart`, `Project Structure`, `1. Project Summary` (+117 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 274 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PageData` connect `PageData` to `analyzer.py`, `4. Detailed Discrete Tasks: Phase 1 through Phase 8`, `crawler.py`, `registry.py`, `Finding`, `AsyncCrawler`, `._crawl_with_client`, `scoring.py`, `models.py`, `onpage.py`, `TestAsyncCrawlerExecution`, `get_mock_cynbit_results`?**
  _High betweenness centrality (0.163) - this node is a cross-community bridge._
- **Why does `Finding` connect `Finding` to `analyzer.py`, `4. Detailed Discrete Tasks: Phase 1 through Phase 8`, `crawler.py`, `PageData`, `registry.py`, `scoring.py`, `models.py`, `onpage.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `main()` connect `Finding` to `analyzer.py`, `PageData`, `AsyncCrawler`, `normalize_url`, `models.py`, `is_safe_url`, `render_category_bars`, `get_mock_cynbit_results`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `PageData` (e.g. with `get_mock_cynbit_results()` and `main()`) actually correct?**
  _`PageData` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `Finding` (e.g. with `main()` and `CheckRegistry`) actually correct?**
  _`Finding` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `AsyncCrawler` (e.g. with `run_live_crawl()` and `PageData`) actually correct?**
  _`AsyncCrawler` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `SEOAnalyzer` (e.g. with `main()` and `BaseLLMClient`) actually correct?**
  _`SEOAnalyzer` has 11 INFERRED edges - model-reasoned connections that need verification._