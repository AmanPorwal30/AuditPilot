"""HTML and DOM parser for AuditPilot.

Extracts structured metadata, headings, links, images, JSON-LD schemas,
semantic landmarks, security indicators, and clean text from raw HTML responses.
"""

import json
import logging
import re
from collections import Counter
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from auditpilot.models import PageData
from auditpilot.validators import normalize_url

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she", "should",
    "so", "some", "such", "t", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "will", "with", "you", "your", "yours", "yourself", "yourselves",
}

PLACEHOLDER_PATTERNS = [
    re.compile(r"lorem\s+ipsum", re.I),
    re.compile(r"coming\s+soon", re.I),
    re.compile(r"under\s+construction", re.I),
    re.compile(r"sample\s+page", re.I),
    re.compile(r"default\s+welcome\s+msg", re.I),
]


CTA_PATTERN = re.compile(
    r"\b(get started|sign up|sign in|log in|buy|shop|order|subscribe|download|contact|book|"
    r"schedule|request|try|start|learn more|read more|view|explore|join|register|apply|call|"
    r"get a quote|free trial|demo)\b"
)


def _extract_top_terms(text: str, max_terms: int = 5) -> list[str]:
    """Extract top frequent significant keyword terms from text."""
    words = re.findall(r"\b[a-zA-Z]{3,20}\b", text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    if not filtered:
        return []
    counts = Counter(filtered)
    return [term for term, _ in counts.most_common(max_terms)]


def parse_page_html(
    url: str,
    html: str | None,
    status_code: int = 200,
    final_url: str | None = None,
    redirect_chain: list[str] | None = None,
    response_time_ms: float = 0.0,
    html_size_bytes: int = 0,
    headers: dict[str, str] | None = None,
) -> PageData:
    """Parse HTML and construct a fully populated PageData instance.

    Args:
        url: The original URL of the request.
        html: Raw HTML string content.
        status_code: HTTP response status code.
        final_url: Landed URL after redirects.
        redirect_chain: List of intermediate URLs.
        response_time_ms: Request elapsed time in ms.
        html_size_bytes: HTML byte payload weight.
        headers: HTTP response headers mapping.

    Returns:
        Populated PageData instance with real extracted metadata.
    """
    resolved_final_url = final_url or url
    size = html_size_bytes or (len(html.encode("utf-8")) if html else 0)
    parsed_headers = {k.lower(): v for k, v in (headers or {}).items()}

    if not html:
        return PageData(
            url=url,
            status_code=status_code,
            final_url=resolved_final_url,
            redirect_chain=redirect_chain or [],
            response_time_ms=response_time_ms,
            html_size_bytes=size,
            raw_html=None,
            headers=parsed_headers,
        )

    soup = BeautifulSoup(html, "lxml")

    # 1. Extract Title
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else None

    # 2. Extract Meta Description
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if not meta_desc_tag:
        meta_desc_tag = soup.find("meta", attrs={"property": re.compile(r"^og:description$", re.I)})
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None

    # 3. Extract Headings (H1s and full heading tree)
    h1s: list[str] = []
    headings: list[tuple[int, str]] = []

    for tag in soup.find_all(re.compile(r"^h[1-6]$", re.I)):
        level = int(tag.name[1])
        heading_text = tag.get_text().strip()
        if heading_text:
            headings.append((level, heading_text))
            if level == 1:
                h1s.append(heading_text)

    # 4. Extract JSON-LD Schemas (must run before decomposing script tags)
    json_ld_types: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, dict):
                if "@type" in data:
                    t = data["@type"]
                    if isinstance(t, list):
                        json_ld_types.extend(t)
                    else:
                        json_ld_types.append(str(t))
                if "@graph" in data and isinstance(data["@graph"], list):
                    for item in data["@graph"]:
                        if isinstance(item, dict) and "@type" in item:
                            json_ld_types.append(str(item["@type"]))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "@type" in item:
                        json_ld_types.append(str(item["@type"]))
        except Exception as e:
            logger.debug(f"JSON-LD parse error: {e}")

    json_ld_types = list(dict.fromkeys(json_ld_types))

    # 5. Extract Semantic Landmarks
    semantic_landmarks = []
    for tag_name in ["header", "nav", "main", "footer", "aside", "section", "article"]:
        if soup.find(tag_name):
            semantic_landmarks.append(tag_name)

    # 6. Extract Form Accessibility
    form_inputs_without_labels = 0
    for inp in soup.find_all(["input", "textarea", "select"]):
        inp_type = inp.get("type", "text").lower()
        if inp_type in ("hidden", "submit", "reset", "button", "image"):
            continue
        # Check label by id, parent label, or aria-label
        inp_id = inp.get("id")
        has_label = False
        if inp_id and soup.find("label", attrs={"for": inp_id}):
            has_label = True
        elif inp.find_parent("label"):
            has_label = True
        elif inp.get("aria-label") or inp.get("aria-labelledby"):
            has_label = True
        if not has_label:
            form_inputs_without_labels += 1

    # 6b. Document-level signals (must run before scripts are decomposed)
    html_tag = soup.find("html")
    html_lang = (html_tag.get("lang") or "").strip() or None if html_tag else None

    viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    viewport_content = viewport_tag.get("content", "").strip().lower() if viewport_tag else None

    open_graph_tags = sorted(
        {
            m.get("property", "").lower()
            for m in soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)})
            if m.get("content", "").strip()
        }
    )

    head = soup.find("head")
    render_blocking_scripts = 0
    if head:
        for script in head.find_all("script", src=True):
            if script.has_attr("async") or script.has_attr("defer"):
                continue
            if (script.get("type") or "").lower() == "module":
                continue
            render_blocking_scripts += 1

    mixed_content_urls: list[str] = []
    if resolved_final_url.lower().startswith("https://"):
        for tag in soup.find_all(["img", "script", "iframe", "source", "audio", "video"], src=True):
            if tag["src"].strip().lower().startswith("http://"):
                mixed_content_urls.append(tag["src"].strip())
        for link_tag in soup.find_all("link", href=True):
            rel = " ".join(link_tag.get("rel") or []).lower()
            if "stylesheet" in rel and link_tag["href"].strip().lower().startswith("http://"):
                mixed_content_urls.append(link_tag["href"].strip())
        mixed_content_urls = list(dict.fromkeys(mixed_content_urls))[:10]

    forms_count = len(soup.find_all("form"))
    form_inputs_total = 0
    form_inputs_validated = 0
    for inp in soup.find_all(["input", "textarea", "select"]):
        inp_type = (inp.get("type") or "text").lower()
        if inp_type in ("hidden", "submit", "reset", "button", "image"):
            continue
        form_inputs_total += 1
        if (
            inp.has_attr("required")
            or inp.has_attr("pattern")
            or inp.has_attr("minlength")
            or inp_type in ("email", "tel", "url", "number", "date")
        ):
            form_inputs_validated += 1

    anchors_total = 0
    dead_links = 0
    unsafe_blank_links = 0
    cta_count = 0
    has_contact_signal = False
    for a_tag in soup.find_all("a"):
        href = (a_tag.get("href") or "").strip()
        if not a_tag.has_attr("href"):
            continue
        anchors_total += 1
        href_lower = href.lower()
        if href in ("", "#") or href_lower.startswith("javascript:"):
            dead_links += 1
        if href_lower.startswith(("mailto:", "tel:")):
            has_contact_signal = True
        link_text = a_tag.get_text(" ", strip=True).lower()
        if re.search(r"\b(contact|about)\b", link_text) or re.search(
            r"/(contact|about)", href_lower
        ):
            has_contact_signal = True
        if (a_tag.get("target") or "").lower() == "_blank":
            rel = " ".join(a_tag.get("rel") or []).lower()
            if "noopener" not in rel and "noreferrer" not in rel:
                unsafe_blank_links += 1
        if link_text and len(link_text) <= 40 and CTA_PATTERN.search(link_text):
            cta_count += 1
    for button in soup.find_all("button"):
        btn_text = button.get_text(" ", strip=True).lower()
        if btn_text and len(btn_text) <= 40 and CTA_PATTERN.search(btn_text):
            cta_count += 1

    positive_tabindex_count = 0
    for el in soup.find_all(attrs={"tabindex": True}):
        try:
            if int(str(el["tabindex"]).strip()) > 0:
                positive_tabindex_count += 1
        except ValueError:
            continue

    # 7. Extract Text, Word Count & Placeholder Check
    # Check for placeholder text before decomposition
    raw_text_content = soup.get_text()
    has_placeholder = any(p.search(raw_text_content) for p in PLACEHOLDER_PATTERNS)

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    clean_text = soup.get_text(separator=" ", strip=True)
    words = re.findall(r"\b\w+\b", clean_text)
    word_count = len(words)

    # 8. Extract Images and Alt Coverage
    img_tags = soup.find_all("img")
    images_total = len(img_tags)
    images_missing_alt = sum(1 for img in img_tags if not img.has_attr("alt"))
    images_missing_dimensions = sum(
        1 for img in img_tags if not (img.get("width") and img.get("height"))
    )
    images_modern_or_lazy = sum(
        1
        for img in img_tags
        if (img.get("loading") or "").lower() == "lazy"
        or re.search(r"\.(webp|avif|svg)(\?|$)", (img.get("src") or "").lower())
    )

    # 9. Extract Links
    base_netloc = urlsplit(resolved_final_url).netloc.lower()
    internal_links: list[str] = []
    external_links: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        try:
            full_url = urljoin(resolved_final_url, href)
            norm_link = normalize_url(full_url)
            link_netloc = urlsplit(norm_link).netloc.lower()
            if link_netloc == base_netloc or link_netloc.endswith("." + base_netloc):
                internal_links.append(norm_link)
            else:
                external_links.append(norm_link)
        except Exception:
            continue

    internal_links = list(dict.fromkeys(internal_links))
    external_links = list(dict.fromkeys(external_links))

    # 10. Extract Canonical Tag
    canonical_tag = soup.find("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else None
    if canonical:
        try:
            canonical = urljoin(resolved_final_url, canonical)
            canonical = normalize_url(canonical)
        except Exception:
            pass

    # 11. Extract Meta Robots
    meta_robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    meta_robots = meta_robots_tag.get("content", "").strip().lower() if meta_robots_tag else None

    # 12. Extract Top Significant Terms
    top_terms = _extract_top_terms(clean_text, max_terms=5)

    return PageData(
        url=url,
        status_code=status_code,
        final_url=resolved_final_url,
        redirect_chain=redirect_chain or [],
        response_time_ms=response_time_ms,
        html_size_bytes=size,
        title=title,
        meta_description=meta_description,
        h1s=h1s,
        headings=headings,
        word_count=word_count,
        images_total=images_total,
        images_missing_alt=images_missing_alt,
        internal_links=internal_links,
        external_links=external_links,
        canonical=canonical,
        meta_robots=meta_robots,
        json_ld_types=json_ld_types,
        top_terms=top_terms,
        raw_html=html,
        headers=parsed_headers,
        semantic_landmarks=semantic_landmarks,
        has_placeholder_content=has_placeholder,
        form_inputs_without_labels=form_inputs_without_labels,
        open_graph_tags=open_graph_tags,
        html_lang=html_lang,
        viewport_content=viewport_content,
        images_missing_dimensions=images_missing_dimensions,
        images_modern_or_lazy=images_modern_or_lazy,
        render_blocking_scripts=render_blocking_scripts,
        forms_count=forms_count,
        form_inputs_total=form_inputs_total,
        form_inputs_validated=form_inputs_validated,
        dead_links=dead_links,
        anchors_total=anchors_total,
        unsafe_blank_links=unsafe_blank_links,
        positive_tabindex_count=positive_tabindex_count,
        cta_count=cta_count,
        has_contact_signal=has_contact_signal,
        mixed_content_urls=mixed_content_urls,
        clean_text=clean_text[:50000],
    )
