# Website Audit Scoring Engine

## Implementation Brief for the Coding Agent

**Objective:** Replace or improve the existing website scoring logic so
that scores reflect the actual quality, completeness, accessibility, and
functionality of a website. The current system over-scores weak
websites, including undeployed sites and sites consisting of only one
shallow page.

This document is an implementation specification. First inspect the
existing repository and architecture. Reuse working components where
appropriate; do not blindly introduce a new stack or rewrite unrelated
functionality.

------------------------------------------------------------------------

## 1. Core requirements

1.  A website must not receive a normal quality score if it cannot be
    meaningfully audited.
2.  Score evidence and quality, not merely the presence of HTML
    elements.
3.  Crawl and assess multiple pages where available.
4.  Do not automatically penalize legitimate single-page websites.
    Assess completeness relative to website type and purpose.
5.  Separate technical failures, missing evidence, and genuine quality
    problems.
6.  Every finding must include evidence, severity, impact, and a
    practical recommendation.
7.  Avoid double-counting the same underlying defect across multiple
    categories.
8.  Make scoring deterministic and explainable. AI may help classify or
    interpret content, but must not invent measurements or evidence.
9.  Keep category scores, raw score, penalties, caps, confidence, and
    final score separately available in the result.
10. Add tests using strong, average, weak, single-page, and unreachable
    sites.

## 2. Proposed audit pipeline

Implement the audit as distinct stages:

1.  **Input validation and URL normalization**
    -   Validate the URL and allow only supported schemes, normally HTTP
        and HTTPS.
    -   Normalize hostname, path, trailing slash, and canonical URL
        representations.
    -   Prevent SSRF: block loopback, private, link-local, multicast,
        reserved IP ranges, cloud metadata endpoints, and redirects to
        blocked destinations.
    -   Re-check DNS and destination IPs after redirects and before each
        connection to reduce DNS-rebinding risk.
    -   Apply request timeouts, response-size limits, redirect limits,
        concurrency limits, and per-domain rate limits.
2.  **Reachability and deployment checks**
    -   Resolve DNS and attempt a bounded HTTP(S) request.
    -   Record final URL, status code, redirect chain, TLS/certificate
        status, response time, and failure reason.
    -   Distinguish DNS failure, connection refusal, timeout, TLS error,
        HTTP 4xx, HTTP 5xx, robots restriction, authentication
        requirement, bot blocking, and parser failure.
    -   Do not automatically call every 403, 401, or timeout an
        undeployed website.
3.  **Website discovery and crawling**
    -   Start from the submitted URL.
    -   Discover same-origin internal links from the homepage and
        relevant navigation.
    -   Inspect `sitemap.xml` and `robots.txt` where available.
    -   Normalize and deduplicate URLs; remove fragments and tracking
        parameters where safe.
    -   Stay within the allowed origin by default. Treat subdomains as
        separate origins unless explicitly configured.
    -   Avoid logout, delete, purchase, submit, or other state-changing
        URLs and actions.
    -   Crawl a configurable limit, with a suggested default of 20
        pages.
    -   Store discovered, crawled, skipped, and failed URLs with
        reasons.
    -   Detect page types such as home, about, contact, service,
        product, pricing, blog/article, FAQ, and legal pages.
        Classification must allow unknown/custom types.
4.  **Page-level analysis**
    -   Parse HTML and inspect metadata, headings, content, images,
        links, forms, semantic structure, and scripts.
    -   Use a browser-based audit such as Lighthouse/Playwright when the
        existing infrastructure supports it for rendered content and
        interaction checks.
    -   Record evidence and measurement provenance for every check.
5.  **Site-level aggregation**
    -   Aggregate page-level findings without allowing one homepage to
        represent the entire site.
    -   Use page-type-aware expectations. A portfolio, campaign landing
        page, documentation site, e-commerce store, and SaaS site have
        different expected structures.
    -   Calculate coverage and confidence based on what was actually
        inspected.
6.  **Scoring and recommendations**
    -   Calculate category scores from verified checks.
    -   Apply critical issue caps only where justified.
    -   Return `not_assessable` or a provisional result when evidence is
        insufficient.
    -   Generate prioritized recommendations from findings.

------------------------------------------------------------------------

## 3. Scoring model (100 points)

Use the following initial weights. Make them configuration-driven so
they can be tuned without changing application code.

  Category                          Weight
  ------------------------------ ---------
  Availability and reliability          10
  SEO                                   15
  Performance                           15
  UI/UX and navigation                  15
  Content quality                       15
  Functionality                         15
  Security                               5
  Accessibility                         10
  **Total**                        **100**

### 3.1 Availability and reliability --- 10 points

Suggested checks:

  Check                                            Points
  ---------------------------------------------- --------
  DNS resolves to a valid public destination            2
  Main page responds successfully                       3
  HTTPS/TLS is valid when HTTPS is used                 2
  Main page does not return a server error              2
  Page can be fetched within configured limits          1

Do not award points merely because a request returned any response. A
404 page is not a successfully available website homepage. Keep
availability status distinct from quality score.

### 3.2 SEO --- 15 points

  Check                                               Points
  ------------------------------------------------- --------
  Unique, descriptive page title                           2
  Useful meta description                                  2
  Logical heading hierarchy                                2
  Appropriate image alt text                               2
  Sitemap availability and validity                        2
  Robots.txt availability and sensible directives          1
  Canonical URL correctness                                1
  Open Graph metadata                                      1
  Useful internal linking                                  2

Evaluate quality, relevance, uniqueness, and correctness. Do not award
full points simply because a tag exists. A sitemap or robots file being
absent is not always a critical SEO failure; interpret it in context.

### 3.3 Performance --- 15 points

  Check                                        Points
  ------------------------------------------ --------
  Largest Contentful Paint (LCP)                    4
  Interaction to Next Paint (INP)                   3
  Cumulative Layout Shift (CLS)                     2
  Overall loading performance                       2
  Image optimization                                1
  JavaScript/CSS delivery and optimization          1
  Resource size and caching                         2

Prefer measured field data when available. Otherwise use lab
measurements and label them clearly. Do not claim that a single lab run
represents real-user Core Web Vitals.

Good Core Web Vitals thresholds: - LCP: 2.5 seconds or less. - INP: 200
milliseconds or less. - CLS: 0.1 or less.

If INP field data is unavailable, mark it as unavailable rather than
pretending a lab metric is INP. Consider Total Blocking Time as a lab
diagnostic, not a direct replacement for INP.

### 3.4 UI/UX and navigation --- 15 points

  Check                                 Points
  ----------------------------------- --------
  Navigation clarity and structure           3
  Visual consistency                         2
  Responsive layout                          3
  Broken internal links                      2
  CTA clarity and usability                  2
  Consistency across page types              2
  Readability and general usability          1

Test links and responsive layouts where tooling permits. Do not award
full marks because a navigation bar or CTA element exists.

### 3.5 Content quality --- 15 points

  Check                                                    Points
  ------------------------------------------------------ --------
  Meaningful primary-page content                               3
  Completeness for the page's purpose                           3
  Relevance to the apparent site purpose                        2
  Grammar and readability                                       2
  Duplicate or near-duplicate content                           2
  Placeholder or unfinished content detection                   2
  Relevant trust/contact information where appropriate          1

Detect likely placeholder content such as "Lorem ipsum", "Coming soon",
"Test content", repeated boilerplate, empty sections, and generic
headings with no supporting information. Avoid treating short copy as
inherently poor: a focused landing page may be intentionally concise.

### 3.6 Functionality --- 15 points

  Check                                            Points
  ---------------------------------------------- --------
  Internal navigation works                             3
  Forms have sensible validation and behavior           3
  Buttons and CTAs perform their stated action          2
  External links work                                   2
  Interactive elements work                             2
  No major client-side errors                           2
  No critical broken functionality detected             1

Use safe, non-destructive interaction tests. Never submit real
purchases, send messages, create accounts, delete data, or trigger
irreversible actions. For actions that cannot safely be tested, report
"not tested" rather than "working".

### 3.7 Security --- 5 points

  Check                                        Points
  ------------------------------------------ --------
  HTTPS/TLS configuration                           1
  No mixed-content issues                           1
  Relevant security headers                         2
  No obvious unsafe configuration detected          1

Do not claim a comprehensive security audit. This is a limited external
configuration review, not penetration testing. Header expectations
should account for site architecture and deployment context.

### 3.8 Accessibility --- 10 points

  Check                                          Points
  -------------------------------------------- --------
  Appropriate image alternatives                      2
  Form controls have accessible names/labels          2
  Keyboard accessibility                              2
  Color contrast                                      2
  Semantic HTML and landmarks                         2

Use automated checks where available, but clearly state that automated
scanning cannot prove full WCAG conformance. Manual keyboard and
screen-reader testing may be outside the automated audit scope.

------------------------------------------------------------------------

## 4. Page discovery and website completeness

A single-page website must not automatically receive a low score.
Instead, infer or classify the site's type and compare its structure
against relevant expectations.

Suggested page-type expectations:

  -----------------------------------------------------------------------
  Website type                        Common expected sections/pages
  ----------------------------------- -----------------------------------
  Portfolio                           Home, about/profile, projects/work,
                                      contact; these may all be sections
                                      on one page

  Campaign landing page               Clear offer, value proposition,
                                      CTA, supporting details, trust
                                      information

  Business website                    Home, about, services/products,
                                      contact

  E-commerce                          Product listing, product detail,
                                      cart, checkout, policies, support

  Blog/publication                    Article listing, article detail,
                                      categories/tags, about

  SaaS                                Product/features, pricing where
                                      relevant, documentation/help,
                                      contact, legal pages

  Documentation                       Getting started, reference/API
                                      sections, navigation/search,
                                      version information where relevant
  -----------------------------------------------------------------------

Implementation guidance: - Identify type using observable signals and
allow uncertainty. - Do not assume every site needs every page type. -
Count meaningful pages and sections, not just URLs. - Detect thin,
duplicate, empty, or template-only pages. - Evaluate navigation depth
and whether important pages are discoverable. - Report page coverage:
discovered, crawled, failed, skipped, and estimated expected pages. - If
site type confidence is low, use neutral generic checks and reduce
confidence rather than imposing an arbitrary structure penalty.

------------------------------------------------------------------------

## 5. Evidence-based scoring

A check must have a defined measurement method and evidence. Avoid
simplistic presence-only logic.

Bad:

``` python
if has_meta_description:
    score += 10
```

Better:

``` python
if not has_meta_description:
    score = 0
elif is_relevant(meta_description) and is_reasonable_length(meta_description):
    score = max_points
else:
    score = partial_points
```

Bad:

``` python
if has_navigation:
    score += 10
```

Better:

``` python
if total_navigation_links == 0:
    score = 0
else:
    working_ratio = working_navigation_links / total_navigation_links
    score = max_points * working_ratio
```

Every check should produce a structured result similar to:

``` json
{
  "check_id": "seo.meta_description",
  "category": "seo",
  "status": "pass",
  "points_earned": 1.5,
  "max_points": 2,
  "evidence": {
    "url": "https://example.com/",
    "observed_value": "A concise description of the service",
    "method": "HTML metadata inspection"
  },
  "finding": "Meta description is present and relevant, but could be more specific.",
  "severity": "low",
  "recommendation": "Describe the primary service and intended audience more precisely."
}
```

Use explicit statuses such as: - `pass` - `partial` - `fail` -
`not_applicable` - `not_tested` - `error`

Do not silently convert `not_tested`, `error`, or `not_applicable` into
zero. They have different meanings.

------------------------------------------------------------------------

## 6. Score calculation, missing data, and confidence

For each category, calculate earned points only from applicable checks
with valid evidence. The system must distinguish between: - a check that
failed, - a check that does not apply, - a check that could not be
tested, - a check that encountered an audit error.

Recommended approach:

1.  Keep each check's `earned_points` and `max_points`.
2.  Exclude genuinely non-applicable checks from the category
    denominator.
3.  Do not treat untested checks as passes.
4.  Calculate category coverage: tested applicable points divided by
    total applicable points.
5.  Calculate a provisional category score from tested checks, but
    expose coverage and confidence.
6.  If coverage is too low, mark the category or overall result
    `provisional` / `not_assessable` rather than presenting a misleading
    definitive score.
7.  Do not inflate scores by excluding failed checks. A failed check is
    tested and earns the points justified by its result.

Base weighted score:

``` python
raw_score = sum(
    category_weight * (category_earned_points / category_applicable_points)
    for category in categories
    if category_is_assessable
)
```

Normalize carefully if categories are legitimately not applicable, and
disclose any normalization. Do not normalize away a critical category
simply because it could not be tested.

Suggested confidence labels: - High: broad page coverage and most
applicable checks tested. - Medium: some checks unavailable or crawl
coverage limited. - Low: only a small part of the site could be
inspected. - Not assessable: no meaningful audit could be completed.

Keep `raw_score`, `final_score`, `score_cap`, `penalties`, `coverage`,
and `confidence` as separate fields.

------------------------------------------------------------------------

## 7. Critical issue caps

Caps prevent severe failures from being hidden by high scores in
unrelated categories. These are initial policy values and must be
configurable and tested.

  -----------------------------------------------------------------------
  Condition                                       Suggested maximum score
  ------------------------------ ----------------------------------------
  Confirmed                          Not assessable, or 0 only if product
  undeployed/unreachable origin        policy explicitly requires numeric
  due to DNS or connection                                         scores
  failure                        

  Homepage returns HTTP 5xx                                            20
  consistently                   

  Submitted homepage returns                                           10
  HTTP 404                       

  Multiple critical user-facing                                        40
  pages are broken               

  Site consists primarily of                                           30
  placeholder/unfinished content 

  Major navigation is broken                                           50

  No usable mobile layout on a                                         65
  site expected to be responsive 

  Severe externally observable                                         60
  security issue                 
  -----------------------------------------------------------------------

Important safeguards: - A single transient timeout is not proof that a
site is undeployed. - A 401/403, bot challenge, geo restriction, or
robots restriction is not proof of non-deployment. - A site may
intentionally be a single-page experience. - Do not apply multiple caps
for the same root cause without justification. - Record the reason and
evidence for every cap. - Prefer `not_assessable` over a misleading zero
when the system cannot inspect the website.

------------------------------------------------------------------------

## 8. Recommendations and prioritization

Each recommendation should be linked to one or more failed/partial
checks and include: - concise issue title, - affected URL(s), -
evidence, - severity (`critical`, `high`, `medium`, `low`), -
user/business impact, - specific remediation, - category, - estimated
effort if it can be reasonably estimated.

Prioritize by severity and impact, not by how easy an issue is to
detect.

Example: \> **Missing homepage meta description**\
\> Evidence: The homepage has no `meta[name="description"]` element.\
\> Impact: Search engines may generate an uncontrolled snippet.\
\> Recommendation: Add a unique description that accurately summarizes
the page and its primary offering.

Avoid vague recommendations such as "Improve SEO", "Make UI better", or
"Optimize performance".

------------------------------------------------------------------------

## 9. Suggested output schema

Adapt this to the existing API response conventions rather than
introducing a breaking response format unnecessarily.

``` json
{
  "url": "https://example.com/",
  "audit_status": "completed",
  "website_status": "reachable",
  "website_type": {
    "value": "business",
    "confidence": 0.86
  },
  "score": {
    "raw": 72.5,
    "final": 62.5,
    "maximum_cap": 65,
    "rating": "Average",
    "confidence": "medium",
    "coverage_percent": 78
  },
  "categories": [
    {
      "id": "seo",
      "name": "SEO",
      "weight": 15,
      "earned_points": 10.5,
      "max_points": 15,
      "coverage_percent": 90,
      "status": "assessed"
    }
  ],
  "crawl": {
    "pages_discovered": 14,
    "pages_crawled": 10,
    "pages_failed": 2,
    "pages_skipped": 2,
    "page_limit": 20
  },
  "critical_issues": [],
  "recommendations": [],
  "limitations": [],
  "score_caps_applied": []
}
```

The example values are illustrative, not a target result. Ensure `final`
is derived from the documented scoring and cap rules; never hardcode it.

For an unreachable website, return an explicit audit status and failure
reason. Do not fabricate category results from a failed fetch.

------------------------------------------------------------------------

## 10. Rating bands

Suggested initial bands:

  Score     Rating
  --------- -------------------
  90--100   Excellent
  80--89    Very Good
  70--79    Good
  60--69    Average
  40--59    Needs Improvement
  20--39    Poor
  0--19     Critical

Use "Not assessable" as a status, not as a score band. These bands are
product choices, not externally certified standards.

------------------------------------------------------------------------

## 11. Testing and calibration

Create automated tests for scoring rules and integration tests for the
crawl/audit pipeline.

Minimum test matrix:

1.  Excellent multi-page business website.
2.  Average multi-page business website.
3.  Poor website with broken links and weak content.
4.  Undeployed domain / DNS failure.
5.  Connection refused.
6.  Homepage HTTP 404.
7.  Homepage HTTP 5xx.
8.  Site blocked by bot protection or returning 403.
9.  Authentication-protected site.
10. Legitimate single-page portfolio.
11. Single-page campaign landing page.
12. E-commerce site missing critical shopping flows.
13. Site with placeholder content.
14. Site with many pages but duplicated/thin content.
15. Site with a valid sitemap but inaccessible pages.
16. Site with redirect chains and canonical inconsistencies.
17. Site that times out intermittently.

For each fixture, assert: - correct audit status, - correct website
status, - category scores, - penalties/caps, - confidence and
coverage, - recommendation evidence, - no double-counted penalties.

Calibration process: - Compare automated results against a
human-reviewed sample. - Include strong, average, weak, single-page, and
inaccessible websites. - Investigate false positives and false
negatives. - Tune weights and thresholds from observed results. -
Version the scoring configuration so scores can be reproduced and
compared over time.

Do not optimize merely to make scores lower. Optimize for agreement with
defensible human evaluation.

------------------------------------------------------------------------

## 12. Engineering and operational requirements

-   Inspect the current codebase before implementation. Identify
    crawler, parser, scoring, persistence, API, and frontend/report
    components.
-   Preserve existing public API contracts where possible; document any
    required changes.
-   Keep scoring rules in a dedicated module/service and
    weights/thresholds in configuration.
-   Keep crawling, page analysis, scoring, and recommendation generation
    separate.
-   Make jobs bounded, cancellable, retry-safe, and observable.
-   Cache carefully with clear expiration and avoid reusing stale audit
    results as fresh results.
-   Persist raw evidence and scoring configuration version for
    reproducibility.
-   Log errors without storing secrets, credentials, or unnecessary
    personal data.
-   Respect robots directives and applicable site policies. Clearly
    label the audit's scope and limitations.
-   Add unit tests for each scoring check and integration tests for
    representative websites.
-   Do not add expensive third-party services unless the current
    architecture requires them and the trade-off is explained.

## 13. Implementation plan for the coding agent

Work in this order:

### Phase 1: Repository inspection

-   Identify the existing audit flow and scoring implementation.
-   Trace how URL input becomes crawl data, category scores, and report
    output.
-   Find why one-page or unreachable sites receive high scores.
-   Identify existing tests and API contracts.
-   Report the findings and proposed minimal-change implementation
    before broad refactoring.

### Phase 2: Correctness foundation

-   Implement robust reachability classification.
-   Add URL safety and SSRF protections.
-   Add crawl discovery, deduplication, and page limits.
-   Introduce evidence-backed check results and explicit statuses.
-   Separate score calculation from data collection.

### Phase 3: Scoring and completeness

-   Implement the configurable 100-point category model.
-   Add page-type-aware completeness evaluation.
-   Add category coverage and confidence.
-   Add justified caps and deduplicated root-cause handling.
-   Ensure single-page websites are evaluated by purpose, not page count
    alone.

### Phase 4: Reporting

-   Return evidence-backed findings and recommendations.
-   Expose crawl coverage, limitations, caps, and scoring version.
-   Update frontend/report display only as needed to communicate these
    fields accurately.

### Phase 5: Validation

-   Add the full test matrix.
-   Run tests and report results.
-   Compare scores on a curated sample of real sites.
-   Document known limitations and configuration tuning.

## 14. Definition of done

The work is complete only when:

-   An undeployed or genuinely unreachable site cannot receive a
    misleading high quality score.
-   A 404 or 5xx homepage is handled explicitly and consistently.
-   A legitimate single-page site is not automatically punished for
    having one page.
-   A multi-page site is assessed across more than its homepage when
    crawlable.
-   Element presence alone does not earn full points.
-   Every scored finding has traceable evidence or a clearly stated
    measurement method.
-   Untested checks are not silently treated as passing.
-   Critical caps are explainable, configurable, and tested.
-   Confidence and coverage are visible in the output.
-   Recommendations identify the actual issue and how to fix it.
-   Automated tests pass and the scoring behavior is documented.

**Instruction to the coding agent:** Start by inspecting the existing
implementation and identifying the root cause of score inflation. Do not
immediately rewrite the project. Make the smallest coherent
architectural changes that deliver the requirements above, preserve
existing behavior where it is correct, and report assumptions or
limitations explicitly.
