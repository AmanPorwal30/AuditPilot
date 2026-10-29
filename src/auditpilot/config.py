"""Configuration module for AuditPilot.

Loads configuration from environment variables and .env file.
Exclusively uses free LLM providers (Groq and Google Gemini).
"""

from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for AuditPilot."""

    # Free LLM Settings ('groq' or 'gemini')
    LLM_PROVIDER: Literal["groq", "gemini"] = "groq"

    # Groq Free API (Default: 30 RPM, Llama 3.3 70B)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Google Gemini Free API (15 RPM, 1M TPM, 1,500 RPD)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Performance APIs (Optional free Google PageSpeed API)
    PAGESPEED_API_KEY: str = ""

    # Crawler Defaults
    MAX_PAGES_DEFAULT: int = 25
    MAX_PAGES_CAP: int = 50
    CRAWLER_CONCURRENCY: int = 5
    REQUEST_DELAY_SECONDS: float = 0.4
    REQUEST_TIMEOUT_SECONDS: float = 10.0
    USER_AGENT: str = "AuditPilotBot/0.1 (+https://cynbit.in/bot)"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Scoring thresholds. Every number the scoring engine compares against lives here.
AUDIT_THRESHOLDS: dict[str, Any] = {
    "availability": {
        "response_time_ok_ms": 5000.0,  # AV05: full points at or below
        "response_time_slow_ms": 10000.0,  # AV05: half points at or below
    },
    "seo": {
        "title_min_chars": 30,
        "title_max_chars": 60,
        "meta_desc_min_chars": 70,
        "meta_desc_max_chars": 160,
        "og_required_tags": ["og:title", "og:description", "og:image"],
        "min_internal_links": 3,  # SE09 single-page detection / UX01
    },
    "performance": {
        "response_excellent_ms": 800.0,  # PF01
        "response_good_ms": 1800.0,
        "response_poor_ms": 3000.0,
        "image_dimension_ratio_ok": 0.9,  # PF03
        "image_modern_ratio_ok": 0.5,  # PF05
        "render_blocking_ok": 0,  # PF06 avg blocking scripts per page
        "render_blocking_partial": 2,
        "html_weight_good_kb": 200.0,  # PF07
        "html_weight_max_kb": 1024.0,
        "compression_encodings": ["gzip", "br", "zstd", "deflate"],
    },
    "ui_ux": {
        "min_navigation_links": 4,
        "template_similarity_ok": 0.7,  # UX06
        "words_per_heading_good": 200,  # UX07
        "words_per_heading_ok": 400,
        "min_words_for_readability": 100,
        "broken_link_ratio_ok": 0.1,  # UX04
        "min_ctas_full": 2,  # UX05
    },
    "content": {
        "min_words_excellent": 300,  # CT01
        "min_words_good": 150,
        "min_words_minimal": 50,
        "thin_page_words": 150,  # CT02
        "duplicate_similarity": 0.85,  # CT05
        "min_words_for_duplicate": 50,
        "flesch_good": 50.0,  # CT04
        "flesch_ok": 30.0,
        "placeholder_site_share": 0.5,  # share of pages that makes it site-wide
    },
    "functionality": {
        "redirect_chain_max": 2,  # FN01
        "form_validation_ratio_ok": 0.7,  # FN02
        "dead_link_ratio_good": 0.05,  # FN03
        "dead_link_ratio_ok": 0.1,
        "unsafe_blank_links_ok": 3,  # FN04
    },
    "security": {
        "security_headers": [
            "strict-transport-security",
            "content-security-policy",
            "x-content-type-options",
            "x-frame-options",
        ],
    },
    "accessibility": {},
    "caps": {
        "unreachable_cap": 0.0,
        "homepage_404_cap": 10.0,
        "homepage_5xx_cap": 20.0,
        "placeholder_content_cap": 30.0,
        "broken_pages_cap": 40.0,
        "broken_pages_min_count": 2,
        "broken_pages_min_share": 0.25,
        "broken_navigation_cap": 50.0,
        "shallow_site_cap": 50.0,
        "shallow_site_words": 100,
        "shallow_site_max_pages": 2,
        "insecure_http_cap": 60.0,
        "missing_viewport_cap": 65.0,
    },
}
