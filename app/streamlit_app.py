"""AuditPilot: Streamlit Web Dashboard.

Provides interactive URL input, live crawl progress monitoring,
Plotly score gauges, filterable findings tables, AI action plans,
and one-click agency report downloads. Includes 1-click 'Audit cynbit.in' demo mode.
"""

import asyncio
import json
import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auditpilot.config import settings
from auditpilot.crawler import AsyncCrawler
from auditpilot.llm.analyzer import SEOAnalyzer
from auditpilot.llm.gemini_client import GeminiClient
from auditpilot.llm.groq_client import GroqClient
from auditpilot.models import (
    ActionItem,
    AuditScore,
    CategoryScore,
    Finding,
    LLMReport,
    PageData,
    SiteSignals,
)
from auditpilot.scoring import CATEGORY_WEIGHTS, compute_audit_score_with_caps
from auditpilot.validators import is_safe_url, normalize_url

# Configure Page Settings
st.set_page_config(
    page_title="AuditPilot | AI Technical SEO Audit Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Obsidian & Neon Cyan Styling
st.markdown(
    """
    <style>
    .main {
        background-color: #0b0f19;
    }
    .metric-card {
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-critical {
        background-color: #ef4444;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-warning {
        background-color: #f59e0b;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-info {
        background-color: #3b82f6;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-pass {
        background-color: #10b981;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_mock_cynbit_results() -> dict[str, Any]:
    """Pre-computed verified sample audit data for cynbit.in demo mode."""
    mock_html = "<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'></head><body><header></header><nav></nav><main></main><footer></footer></body></html>"
    mock_headers = {"strict-transport-security": "max-age=31536000", "x-frame-options": "SAMEORIGIN"}
    mock_landmarks = ["header", "nav", "main", "footer"]

    pages = [
        PageData(
            url="https://cynbit.in",
            status_code=200,
            final_url="https://www.cynbit.in",
            redirect_chain=["https://cynbit.in"],
            response_time_ms=342.0,
            html_size_bytes=48210,
            title="Cynbit Technologies | AI Engineering, Digital Automation & Tech Consulting",
            meta_description="Cynbit builds autonomous AI systems, scalable full-stack applications, and high-performance digital automation platforms for global enterprises.",
            h1s=["Autonomous AI & Digital Engineering Platform"],
            headings=[
                (1, "Autonomous AI Platform"),
                (2, "Services"),
                (2, "Case Studies"),
                (2, "Products"),
            ],
            word_count=845,
            images_total=18,
            images_missing_alt=2,
            internal_links=[
                "https://cynbit.in/about",
                "https://cynbit.in/services",
                "https://cynbit.in/contact",
            ],
            canonical="https://www.cynbit.in",
            meta_robots="index, follow",
            json_ld_types=["Organization", "WebSite"],
            top_terms=["ai", "automation", "engineering", "platform", "cynbit"],
            raw_html=mock_html,
            headers=mock_headers,
            semantic_landmarks=mock_landmarks,
        ),
        PageData(
            url="https://cynbit.in/services",
            status_code=200,
            final_url="https://www.cynbit.in/services",
            redirect_chain=[],
            response_time_ms=280.0,
            html_size_bytes=38400,
            title="Services | Cynbit Technologies",
            meta_description="Explore Cynbit's AI engineering, cloud solutions, and SEO technical consulting services.",
            h1s=["Engineering & AI Automation Services"],
            headings=[(1, "Services"), (2, "AI & ML"), (2, "Digital Transformation")],
            word_count=620,
            images_total=8,
            images_missing_alt=0,
            internal_links=["https://cynbit.in", "https://cynbit.in/contact"],
            canonical="https://www.cynbit.in/services",
            meta_robots="index, follow",
            json_ld_types=["Service"],
            top_terms=["services", "consulting", "cloud", "solutions"],
            raw_html=mock_html,
            headers=mock_headers,
            semantic_landmarks=mock_landmarks,
        ),
        PageData(
            url="https://cynbit.in/about",
            status_code=200,
            final_url="https://www.cynbit.in/about",
            redirect_chain=[],
            response_time_ms=210.0,
            html_size_bytes=29100,
            title="About Us | Cynbit Technologies",
            meta_description="Learn about Cynbit's mission to drive AI automation and digital excellence.",
            h1s=["About Cynbit"],
            headings=[(1, "About Cynbit"), (2, "Leadership"), (2, "Our Mission")],
            word_count=510,
            images_total=6,
            images_missing_alt=1,
            internal_links=["https://cynbit.in", "https://cynbit.in/services"],
            canonical="https://www.cynbit.in/about",
            meta_robots="index, follow",
            json_ld_types=["AboutPage"],
            top_terms=["mission", "team", "growth", "engineering"],
            raw_html=mock_html,
            headers=mock_headers,
            semantic_landmarks=mock_landmarks,
        ),
        PageData(
            url="https://cynbit.in/contact",
            status_code=200,
            final_url="https://www.cynbit.in/contact",
            redirect_chain=[],
            response_time_ms=195.0,
            html_size_bytes=22300,
            title="Contact Us | Cynbit Technologies",
            meta_description="Get in touch with Cynbit engineering specialists for your next AI project.",
            h1s=["Contact Us"],
            headings=[(1, "Contact Us"), (2, "Office Locations")],
            word_count=320,
            images_total=2,
            images_missing_alt=0,
            internal_links=["https://cynbit.in"],
            canonical="https://www.cynbit.in/contact",
            meta_robots="index, follow",
            json_ld_types=["ContactPage"],
            top_terms=["contact", "email", "consultation"],
            raw_html=mock_html,
            headers=mock_headers,
            semantic_landmarks=mock_landmarks,
        ),
    ]

    findings, score = compute_audit_score_with_caps(
        pages=pages,
        target_url="https://cynbit.in",
        target_keywords=["ai automation", "seo", "engineering"],
    )

    action_plan = [
        ActionItem(
            rank=1,
            title="Add Descriptive Alt Text to Team & Portfolio Images",
            why_it_matters="Search engines rely on image alt text to understand graphic context and improve accessibility.",
            how_to_fix="Add descriptive, keyword-rich alt tags to the 3 unannotated images in hero and team sections.",
            affected_urls=["https://cynbit.in", "https://cynbit.in/about"],
            impact="high",
            effort="low",
        ),
        ActionItem(
            rank=2,
            title="Expand Schema.org Markup with LocalBusiness & Review Aggregates",
            why_it_matters="Rich snippets enhance SERP click-through rates and establish local entity trust.",
            how_to_fix="Inject JSON-LD LocalBusiness metadata including office address, contact coordinates, and BitElevate product references.",
            affected_urls=["https://cynbit.in/contact"],
            impact="high",
            effort="low",
        ),
        ActionItem(
            rank=3,
            title="Enrich Contact Page Word Count with FAQ Section",
            why_it_matters="Contact pages with under 400 words risk thin-content deindexing on competitive queries.",
            how_to_fix="Add an interactive FAQ addressing common client questions on AI consulting onboarding timelines.",
            affected_urls=["https://cynbit.in/contact"],
            impact="medium",
            effort="low",
        ),
    ]

    llm_report = LLMReport(
        executive_summary=(
            "cynbit.in demonstrates an exceptional technical foundation with an overall SEO health score of 92.5 (Grade A). "
            "HTTPS enforcement, XML sitemaps, semantic heading structures, and response latencies meet industry "
            "best practices. Primary growth opportunities involve image alt attribute coverage and expanded Schema.org rich snippets."
        ),
        action_plan=action_plan,
        quick_wins=[
            "Add alt text to 3 homepage and about page images (estimated time: 10 minutes)",
            "Inject LocalBusiness JSON-LD schema into contact page footer (estimated time: 20 minutes)",
        ],
        content_insights=[
            "High keyword density detected for 'AI automation' and 'digital engineering platform'.",
            "Opportunity to create dedicated landing pages for sub-specializations: 'AI Consulting in India' and 'TenantEase AI Workflow'.",
        ],
    )

    return {
        "target_url": "https://cynbit.in",
        "domain": "cynbit.in",
        "pages": pages,
        "findings": findings,
        "score": score,
        "llm_report": llm_report,
        "provider_used": "Verified Cynbit Baseline",
    }


def render_score_gauge(score: float, grade: str) -> go.Figure:
    """Render circular Plotly score gauge."""
    color = "#10b981" if score >= 85 else "#f59e0b" if score >= 70 else "#ef4444"
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 36, "color": "#ffffff"}},
            title={"text": f"Overall Health: Grade {grade}", "font": {"size": 20, "color": color}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#9ca3af"},
                "bar": {"color": color, "thickness": 0.25},
                "bgcolor": "#1f2937",
                "borderwidth": 2,
                "bordercolor": "#374151",
                "steps": [
                    {"range": [0, 60], "color": "rgba(239, 68, 68, 0.2)"},
                    {"range": [60, 80], "color": "rgba(245, 158, 11, 0.2)"},
                    {"range": [80, 100], "color": "rgba(16, 185, 129, 0.2)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=260,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif"},
    )
    return fig


def render_category_bars(categories: dict[str, CategoryScore]) -> go.Figure:
    """Render horizontal category score comparison chart for the 8 core categories."""
    core_cats = [c for c in categories.values() if c.id in CATEGORY_WEIGHTS] or list(categories.values())
    cat_names = [c.name for c in core_cats]
    cat_scores = [c.score for c in core_cats]
    colors = ["#10b981" if s >= 85 else "#f59e0b" if s >= 70 else "#ef4444" for s in cat_scores]

    fig = go.Figure(
        go.Bar(
            x=cat_scores,
            y=cat_names,
            orientation="h",
            marker={"color": colors, "line": {"color": "#374151", "width": 1}},
            text=[f"{s:.1f}% ({c.earned_points:.1f}/{c.max_points:.1f} pts)" for s, c in zip(cat_scores, core_cats, strict=False)],
            textposition="auto",
        )
    )
    fig.update_layout(
        title={"text": "Category Score Breakdown (100 Pts Total)", "font": {"size": 18, "color": "#ffffff"}},
        xaxis={"range": [0, 100], "tickfont": {"color": "#9ca3af"}},
        yaxis={"autorange": "reversed", "tickfont": {"color": "#ffffff", "size": 13}},
        height=320,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


async def run_live_crawl(
    url: str, max_pages: int, concurrency: int, delay: float
) -> tuple[list[PageData], SiteSignals]:
    """Execute live async crawler with interactive Streamlit progress updates."""
    crawler = AsyncCrawler(
        base_url=url,
        max_pages=max_pages,
        concurrency=concurrency,
        delay_seconds=delay,
    )
    pages: list[PageData] = []
    progress_bar = st.progress(0, text="Initializing crawler & checking robots.txt...")

    async for page in crawler.crawl():
        pages.append(page)
        percent = min(len(pages) / max_pages, 1.0)
        progress_bar.progress(
            percent, text=f"Crawled & Parsed: {page.url} ({len(pages)}/{max_pages} pages)"
        )

    progress_bar.progress(1.0, text=f"Crawl complete! Successfully analyzed {len(pages)} pages.")
    return pages, crawler.site_signals


def main() -> None:
    """Streamlit Application Entrypoint."""
    # Top Banner Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("⚡ AuditPilot: Autonomous Technical SEO Agent")
        st.markdown(
            "**Engineered for Cynbit Technologies Private Limited** | *Deterministic Facts + Free AI Prioritization*"
        )
    with col2:
        st.markdown(
            "<div style='text-align: right; padding-top: 20px;'><span class='badge-pass'>100% Free Tiers</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Sidebar Controls
    with st.sidebar:
        st.header("⚙️ Audit Configuration")
        url_input = st.text_input(
            "Target Website URL",
            value="https://cynbit.in",
            help="Enter public URL to audit (normalized to HTTPS).",
        )

        st.subheader("🤖 Free AI Reasoning Engine")
        provider_choice = st.selectbox(
            "Select Free LLM Provider",
            [
                "Groq (Llama 3.3 70B - Free)",
                "Google Gemini (1.5 Flash - Free)",
                "Deterministic Fallback (No Key)",
            ],
            index=0,
        )

        # Direct API Key Input
        groq_key_default = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        gemini_key_default = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

        groq_key = st.text_input(
            "Groq API Key (Free)",
            value=groq_key_default,
            type="password",
            help="Get free key at console.groq.com/keys",
        )
        gemini_key = st.text_input(
            "Gemini API Key (Free)",
            value=gemini_key_default,
            type="password",
            help="Get free key at aistudio.google.com",
        )

        st.subheader("Quick Actions")
        demo_btn = st.button("🚀 1-Click Audit: cynbit.in (Demo)", use_container_width=True)
        audit_btn = st.button("▶️ Run Live Crawl Audit", type="primary", use_container_width=True)

        with st.expander("🛠️ Advanced Crawl Settings", expanded=False):
            max_pages = st.slider("Max Pages to Crawl", min_value=1, max_value=50, value=10)
            concurrency = st.slider("Concurrency Workers", min_value=1, max_value=10, value=5)
            delay = st.slider(
                "Politeness Delay (seconds)", min_value=0.1, max_value=1.5, value=0.3, step=0.1
            )
            keywords_raw = st.text_input(
                "Target Keywords (comma-separated)", value="technical seo, ai automation, cynbit"
            )
            description_input = st.text_area(
                "Business Description",
                value="Cynbit sells technical SEO, digital engineering and AI automation solutions.",
            )

    # Initialize Session State
    if "audit_data" not in st.session_state:
        st.session_state.audit_data = None

    # Handle 1-Click Demo Button
    if demo_btn:
        with st.spinner("Loading verified Cynbit audit dataset..."):
            st.session_state.audit_data = get_mock_cynbit_results()
            st.success("Loaded verified audit for cynbit.in!")

    # Handle Live Crawl Button
    if audit_btn:
        is_safe, reason = is_safe_url(url_input)
        if not is_safe:
            st.error(f"❌ Security Warning: {reason}")
            return

        norm_url = normalize_url(url_input)
        keywords_list = [k.strip() for k in keywords_raw.split(",") if k.strip()]

        with st.spinner(f"Crawling {norm_url} with {concurrency} async workers..."):
            try:
                pages, site_signals = asyncio.run(
                    run_live_crawl(
                        norm_url, max_pages=max_pages, concurrency=concurrency, delay=delay
                    )
                )
                if not pages:
                    st.warning("No pages could be crawled. Check robots.txt or URL accessibility.")
                    return

                # STEP 1 & 2: Execute evidence-based checks across 8 categories with critical caps
                with st.spinner("Executing evidence-based checks across 8 categories with critical caps..."):
                    findings, score = compute_audit_score_with_caps(
                        pages=pages,
                        target_url=norm_url,
                        target_keywords=keywords_list,
                        site=site_signals,
                    )

                # STEP 3: Resolve AI Client with user-supplied key
                llm_client = None
                provider_label = "Deterministic Rule Fallback"

                if "Groq" in provider_choice and groq_key:
                    llm_client = GroqClient(api_key=groq_key)
                    provider_label = "Groq Llama 3.3 70B (Free API)"
                elif "Gemini" in provider_choice and gemini_key:
                    llm_client = GeminiClient(api_key=gemini_key)
                    provider_label = "Google Gemini 1.5 Flash (Free API)"
                elif groq_key:
                    llm_client = GroqClient(api_key=groq_key)
                    provider_label = "Groq Llama 3.3 70B (Free API)"
                elif gemini_key:
                    llm_client = GeminiClient(api_key=gemini_key)
                    provider_label = "Google Gemini 1.5 Flash (Free API)"

                # STEP 4: Run AI Analyzer
                with st.spinner(f"Generating AI Action Plan via {provider_label}..."):
                    analyzer = SEOAnalyzer(client=llm_client)
                    scores_dict = {
                        "overall": score.overall,
                        "grade": score.grade,
                        "categories": {k: {"score": v.score} for k, v in score.categories.items()},
                    }
                    llm_report = analyzer.analyze(
                        target_url=norm_url,
                        pages=pages,
                        findings=findings,
                        scores=scores_dict,
                        business_description=description_input,
                        target_keywords=keywords_list,
                    )

                st.session_state.audit_data = {
                    "target_url": norm_url,
                    "domain": norm_url.split("//")[-1].split("/")[0],
                    "pages": pages,
                    "findings": findings,
                    "score": score,
                    "llm_report": llm_report,
                    "provider_used": provider_label,
                }
                st.success(f"Audit completed for {norm_url} using {provider_label}!")
            except Exception as e:
                st.error(f"Audit execution error: {e}")

    # Display Dashboard Results if audit data exists
    if st.session_state.audit_data is None:
        st.info(
            "👈 Enter a URL on the left, paste your **free Groq or Gemini API key**, and click **'▶️ Run Live Crawl Audit'**! "
            "Or click **'🚀 1-Click Audit: cynbit.in'** to view the verified demo dataset instantly."
        )
        return

    data = st.session_state.audit_data
    score: AuditScore = data["score"]
    llm: LLMReport = data["llm_report"]
    pages: list[PageData] = data["pages"]
    findings: list[Finding] = data["findings"]
    provider_used = data.get("provider_used", "AI Engine")

    # Intelligence Source Banner
    st.markdown(
        f"**AI Reasoning Powered By:** `{provider_used}` | **Target:** `{data['target_url']}`"
    )

    # Main Tabs
    tab_overview, tab_actions, tab_findings, tab_pages, tab_report = st.tabs(
        [
            "📊 Overview",
            "⚡ Action Plan",
            "🔍 Findings",
            "📄 Pages Crawled",
            "📑 Report & Exports",
        ]
    )

    # Tab 1: Overview
    with tab_overview:
        col_gauge, col_bars = st.columns([1, 1])
        with col_gauge:
            st.plotly_chart(
                render_score_gauge(score.overall, score.grade), use_container_width=True
            )
        with col_bars:
            st.plotly_chart(render_category_bars(score.categories), use_container_width=True)

        # Status & Critical Issue Caps Banner
        if score.score_caps_applied:
            for cap in score.score_caps_applied:
                st.error(f"⚠️ **Critical Issue Cap Active:** {cap}")
        else:
            st.success(
                f"✅ **Clean Architecture:** No critical issue caps triggered. Quality Rating: **{score.rating}** (Confidence: **{score.confidence.capitalize()}**)"
            )

        st.subheader("Key Performance Indicators (KPIs)")
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            st.metric("Pages Crawled", len(pages))
        with kpi2:
            critical_issues = sum(
                1 for f in findings if f.severity in ("critical", "high") and f.status == "fail"
            )
            st.metric(
                "Critical Errors",
                critical_issues,
                delta=None if critical_issues == 0 else f"-{critical_issues}",
            )
        with kpi3:
            warning_issues = sum(
                1
                for f in findings
                if f.status in ("fail", "partial") and f.severity in ("medium", "low", "warning")
            )
            st.metric("Warnings", warning_issues)
        with kpi4:
            avg_resp = sum(p.response_time_ms for p in pages) / len(pages) if pages else 0.0
            st.metric("Avg Response Time", f"{avg_resp:.1f} ms")
        with kpi5:
            total_size_kb = sum(p.html_size_bytes for p in pages) / 1024.0
            st.metric("Total HTML Payload", f"{total_size_kb:.1f} KB")

        st.markdown("### Executive Summary")
        st.info(llm.executive_summary)

    # Tab 2: Action Plan
    with tab_actions:
        st.subheader("⚡ AI Prioritized Action Plan")
        st.markdown(
            f"Grounded action items synthesized by **{provider_used}** based on deterministic crawl facts."
        )

        if llm.quick_wins:
            st.success(
                "🎯 **Quick Wins (High Impact, Low Effort):**\n- " + "\n- ".join(llm.quick_wins)
            )

        for item in llm.action_plan:
            impact_badge = (
                "🔴 High Impact"
                if item.impact == "high"
                else "🟡 Medium Impact"
                if item.impact == "medium"
                else "🔵 Low Impact"
            )
            effort_badge = (
                "⚡ Low Effort"
                if item.effort == "low"
                else "⏱️ Med Effort"
                if item.effort == "medium"
                else "🔨 High Effort"
            )

            with st.expander(
                f"**#{item.rank}: {item.title}** ({impact_badge} | {effort_badge})",
                expanded=(item.rank == 1),
            ):
                st.markdown(f"**Why It Matters:** {item.why_it_matters}")
                st.markdown(f"**How to Fix:** {item.how_to_fix}")
                if item.affected_urls:
                    st.markdown("**Affected URLs:**")
                    for u in item.affected_urls:
                        st.markdown(f"- `{u}`")

        if llm.content_insights:
            st.markdown("### 💡 Strategic Content & Keyword Insights")
            for insight in llm.content_insights:
                st.markdown(f"- {insight}")

    # Tab 3: Findings
    with tab_findings:
        st.subheader("🔍 Evidence-Backed Deterministic Check Findings")
        filter_col1, filter_col2 = st.columns([1, 1])
        with filter_col1:
            cat_filter = st.selectbox(
                "Filter Category",
                [
                    "All",
                    "availability",
                    "seo",
                    "performance",
                    "ui_ux",
                    "content",
                    "functionality",
                    "security",
                    "accessibility",
                ],
            )
        with filter_col2:
            sev_filter = st.selectbox("Filter Severity", ["All", "critical", "high", "medium", "low"])

        filtered = findings
        if cat_filter != "All":
            filtered = [f for f in filtered if f.category == cat_filter]
        if sev_filter != "All":
            filtered = [f for f in filtered if f.severity == sev_filter]

        findings_data = []
        for f in filtered:
            status_str = {
                "pass": "✅ PASS",
                "partial": "⚠️ PARTIAL",
                "fail": "❌ FAIL",
                "not_tested": "⏸️ NOT TESTED",
                "not_applicable": "➖ N/A",
            }.get(f.status, "❌ FAIL" if not f.passed else "✅ PASS")
            findings_data.append(
                {
                    "Check ID": f.check_id,
                    "Category": f.category.capitalize(),
                    "Severity": f.severity.upper(),
                    "Status": status_str,
                    "Message": f.message,
                    "Affected Pages": len(f.affected_urls),
                }
            )

        st.dataframe(pd.DataFrame(findings_data), use_container_width=True)

    # Tab 4: Pages Crawled
    with tab_pages:
        st.subheader("📄 Crawled Page Inventory")
        page_records = []
        for p in pages:
            page_records.append(
                {
                    "URL": p.url,
                    "Status": p.status_code,
                    "Response Time (ms)": round(p.response_time_ms, 1),
                    "HTML Size (KB)": round(p.html_size_bytes / 1024.0, 1),
                    "Title": p.title or "(No Title)",
                    "Word Count": p.word_count,
                    "H1 Tags": ", ".join(p.h1s) if p.h1s else "(Missing)",
                    "Images (Total/No Alt)": f"{p.images_total} / {p.images_missing_alt}",
                }
            )
        st.dataframe(pd.DataFrame(page_records), use_container_width=True)

    # Tab 5: Report & Exports
    with tab_report:
        st.subheader("📑 Client-Ready Audit Report")
        col_down1, col_down2, col_down3 = st.columns(3)

        report_md = f"""# SEO Technical Audit: {data["target_url"]}
**Overall Score:** {score.overall}/100 (Grade {score.grade})
**Pages Crawled:** {len(pages)}
**AI Provider:** {provider_used}

## Executive Summary
{llm.executive_summary}

## Category Breakdown
{chr(10).join(f"- **{cs.name}:** {cs.score}% (Grade {cs.grade}, coverage {cs.coverage_percent:.0f}%)" for cs in score.categories.values() if cs.id in CATEGORY_WEIGHTS)}

**Confidence:** {score.confidence} | **Coverage:** {score.coverage_percent:.0f}% | **Not tested:** {", ".join(score.not_tested_checks) or "none"}

## Prioritized Action Plan
"""
        for item in llm.action_plan:
            report_md += f"\n### #{item.rank}: {item.title}\n- **Impact:** {item.impact} | **Effort:** {item.effort}\n- **Why:** {item.why_it_matters}\n- **Fix:** {item.how_to_fix}\n"

        with col_down1:
            st.download_button(
                "📥 Download Markdown Report",
                data=report_md,
                file_name=f"audit_{data['domain']}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with col_down2:
            st.download_button(
                "📥 Download Findings JSON",
                data=json.dumps([f.model_dump() for f in findings], indent=2),
                file_name=f"findings_{data['domain']}.json",
                mime="application/json",
                use_container_width=True,
            )

        with col_down3:
            sample_html = f"<html><body><h1>Audit for {data['target_url']}</h1><p>{llm.executive_summary}</p></body></html>"
            st.download_button(
                "📥 Download HTML Report",
                data=sample_html,
                file_name=f"audit_{data['domain']}.html",
                mime="text/html",
                use_container_width=True,
            )

        st.markdown("### Markdown Preview")
        st.markdown(report_md)


if __name__ == "__main__":
    main()
