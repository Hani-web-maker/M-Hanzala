#!/usr/bin/env python3
"""
Blog Audit Script — CustomGPT.ai
=================================
Audits blog URLs using Claude API with a comprehensive scoring prompt.

Setup:
    pip install anthropic requests beautifulsoup4

Usage:
    1. Create urls.txt  — one URL per line
    2. Run: python audit.py
    3. Results → audit_results.csv   (appended after every batch)
    4. Progress → audit_progress.json (auto-resume on restart)
"""

import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

# ── Configuration ─────────────────────────────────────────────────────────────
# Set your key here OR export ANTHROPIC_API_KEY=sk-ant-... before running
API_KEY            = os.environ.get("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")
MODEL              = "claude-sonnet-4-20250514"
BATCH_SIZE         = 5
URLS_FILE          = "urls.txt"
RESULTS_FILE       = "audit_results.csv"
PROGRESS_FILE      = "audit_progress.json"
MAX_BODY_WORDS     = 2500   # truncate body to stay within context
SLEEP_BETWEEN      = 15     # seconds between batches
FETCH_TIMEOUT      = 20     # seconds per URL fetch
MAX_TOKENS         = 16000  # Claude output budget

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── Full Audit Prompt ─────────────────────────────────────────────────────────
AUDIT_PROMPT = r'''<?xml version="1.0" encoding="UTF-8"?>
<identity>
  <role>Senior Blog Audit Engineer + Conversion Intelligence Analyst</role>
  <capability_stack>
    Content strategy | Technical SEO | Conversion rate optimisation |
    RAG/AI product marketing | Editorial quality control |
    Portfolio deduplication | Trial-funnel architecture analysis
  </capability_stack>
  <prime_directive>
    EXECUTE THIS AUDIT AS A DETERMINISTIC SCORING ENGINE.
    Rules of operation — non-negotiable:
    R01 CRAWL EVERY URL FULLY. Strip nav/header/footer/sidebar/cookie banners.
        Read complete body. Cache all sub-elements per EXECUTION PROTOCOL below.
    R02 MERGE crawled data with pre-loaded Screaming Frog + GSC data.
        Pre-loaded SF values (word count, Flesch, inlinks, meta chars,
        grammar/spelling) are AUTHORITATIVE. When SF/GSC data is
        DATA_UNAVAILABLE, use DATA_UNAVAILABLE for those fields and estimate
        what you can from the crawled content alone.
    R03 SCORE using ONLY formulas defined in PARAMETER REGISTRY. No substitutions.
    R04 DATA_UNAVAILABLE rule: if required data cannot be accessed, score = 0,
        flag = DATA_UNAVAILABLE, explain in corrective action. Never invent scores.
    R05 FLAG_RULE is independent of threshold. A PASS can still TRIGGER a flag.
        Both results must appear in every parameter column.
    R06 SCORE COMPRESSION IS FABRICATION. Each URL earns its score independently
        from page evidence.
    R07 Context values locked in PHASE 3 cannot change during parameter scoring.
    R08 Factual accuracy (A3): only flag claims you are GENUINELY CONFIDENT are
        wrong or seriously outdated. Mark UNVERIFIED — not FLAG — for uncertain.
    R09 ICP classification: Off-ICP = affiliate marketing, YouTube tutorials,
        SEO tactics, general internet content unrelated to AI/business/knowledge.
    R10 Composite below 40: always emit CRITICAL_REMOVAL in escalation block.
    R11 OUTPUT FORMAT: Emit ONE pipe-delimited data row per URL. All columns
        flattened into a single row. ONE header row followed by ONE data row
        per URL. No multiple tables. No markdown. No asterisks. No bold.
    R12 All scores 0.0–10.0 (one decimal). Category scores 0.00–10.00 (two decimals).
        Composite_100: 0.0–100.0 (one decimal). Grade: A+ | A | B | C | D | F.
  </prime_directive>
</identity>

<product_context>
  <brand>CustomGPT.ai</brand>
  <url>https://customgpt.ai</url>
  <tagline>Trusted Business AI. No Hallucinations. Your Knowledge. Your Rules.</tagline>
  <what_it_is>
    No-code platform for building private RAG AI chatbot agents trained on a
    business's own documents, website, and data sources. Agents answer ONLY
    from approved knowledge — no made-up facts. Third-party verified #1 for
    anti-hallucination accuracy vs OpenAI and Google. Supports 1,400+ file types.
    100+ one-click integrations. SOC-2 Type II + GDPR compliant. 100% uptime SLA.
    Deployable on web, helpdesk, mobile, API. Live in 15 minutes, zero engineering.
  </what_it_is>
  <icp>
    PRIMARY: Support teams — ticket deflection, agent assist, self-serve KB
    SECONDARY: Manufacturing companies — SOP/technical doc search, field service
    TERTIARY: Mid-market SaaS companies — internal knowledge search, onboarding
    ALSO SERVES: Professional services, education, government, legal, healthcare
    COMPANY SIZE: 100–5,000 employees with budget for $89+/mo commitment
  </icp>
  <use_cases>
    UC1 Helpdesk Ticket Deflection — deflect up to 93% of support tickets
    UC2 Internal Knowledge Search (Enterprise RAG) — employees get fast answers
    UC3 AI Site Search / Generative Answers — replace keyword search on websites
    UC4 Knowledge-as-a-Service — monetise expertise behind paywall
    UC5 Agent Assist — AI drafts replies for human agents to approve
  </use_cases>
  <key_differentiators>
    DIFF1 Anti-hallucination: answers ONLY from uploaded data, never invented
    DIFF2 #1 accuracy (third-party verified vs OpenAI + Google)
    DIFF3 Clickable citations with every answer
    DIFF4 No-code: live in 15 minutes, zero engineering
    DIFF5 Data privacy: RAG architecture = no training on your data
    DIFF6 Predictable pricing: no surprise dev costs
  </key_differentiators>
  <competitors>
    Chatbase | Botpress | Intercom Fin | SiteGPT | Wonderchat | Drift |
    LivePerson | Ada | Forethought | Glean | Notion AI | DocsBot AI | Botsonic
  </competitors>
  <brand_voice>
    TONE: Very casual yet professional. Conversational, direct, no buzzword fluff.
    PERSON: First-person "I", speaks to "you" (the reader) naturally.
    PARAGRAPH: Short — 1 to 2 sentences max.
    CLAIMS: Specific with numbers. Real examples. No vague "many businesses" statements.
    BANNED_WORDS: delve | tapestry | landscape | realm | nuanced | multifaceted |
      "it is worth noting" | "in conclusion" | leverage (as verb) | "in today's world" |
      "let's dive in" | game-changer | revolutionise | cutting-edge |
      "at the end of the day" | "in summary" | to summarize | Furthermore |
      Moreover | Additionally (as paragraph openers)
  </brand_voice>
</product_context>

<execution_protocol>
  <phase id="3" name="CONTEXT_LOCK">
    Lock FOCUS_KEYWORD, POST_TIER, FUNNEL_STAGE, CONTENT_SILO, ICP_FIT,
    FUNNEL_CONVERSION_ROLE, READER_AWARENESS_STAGE, ONE_LINE_SUMMARY,
    CORE_THEME, READER_PROMISE from slug + H1 + body first 200 words.
  </phase>
  <phase id="4" name="PARAMETER_EVALUATION">
    Run all parameters A1–G3–NEW1–NEW4. For each:
    4a. Apply FORMULA from PARAMETER REGISTRY
    4b. Map raw output to SCORE (0.0–10.0)
    4c. Compare vs THRESHOLD → PASS or FAIL
    4d. Evaluate FLAG_RULE → TRIGGERED or CLEAR
    4e. Record: raw evidence | score | PASS/FAIL | flag status | corrective action
  </phase>
  <phase id="5" name="CATEGORY_AGGREGATION">
    Cat_X = Weighted average of parameter scores in category. Round to 2 decimals.
  </phase>
  <phase id="6" name="COMPOSITE_SCORE">
    Composite_100 = (
      (Cat_A × 0.25) + (Cat_B × 0.20) + (Cat_C × 0.20) +
      (Cat_D × 0.10) + (Cat_E × 0.07) + (Cat_F × 0.05) +
      (Cat_G × 0.04) + (Cat_H × 0.09)
    ) × 10
    Cat_H = average of NEW1, NEW2, NEW3, NEW4.
  </phase>
</execution_protocol>

<parameter_registry>
  <!-- CATEGORY A: Content Quality (weight 0.25) -->
  <!-- A1 Information Gain — A2 Answer Quality — A3 Factual Accuracy -->
  <!-- A4 Content Freshness — A5 Word Count vs Topic Depth -->
  <!-- A6 Heading Architecture — A7 Readability Score -->
  <!-- A8 AI Writing Contamination — A9 Evidence and Citation Quality -->
  <!-- A10 Topic Coverage Completeness — A11 Content Duplication Risk -->

  <!-- CATEGORY B: On-Page SEO (weight 0.20) -->
  <!-- B1 Focus Keyword ID — B2 Keyword in H1 — B3 Keyword in Intro -->
  <!-- B4 Keyword in Subheadings — B5 Meta Title — B6 Meta Description -->
  <!-- B7 URL Slug Quality — B8 Keyword Cannibalization -->

  <!-- CATEGORY C: Conversion Intelligence (weight 0.20) -->
  <!-- C1 CTA Architecture — C2 Product-Content Alignment -->
  <!-- C3 Funnel Stage Correctness — C4 Commercial Intent Score -->
  <!-- C5 Intent-to-Conversion Fit -->

  <!-- CATEGORY D: Authority and Trust (weight 0.10) -->
  <!-- D1 Brand Voice Authenticity — D2 Specificity Ratio -->
  <!-- D3 EEAT Signals — D4 External Citation Authority -->

  <!-- CATEGORY E: Internal Linking (weight 0.07) -->
  <!-- E1 Outbound Internal Links — E2 Inbound Link Signal -->
  <!-- E3 Anchor Text Quality -->

  <!-- CATEGORY F: Technical On-Page (weight 0.05) -->
  <!-- F1 Schema and Structured Data — F2 Image Alt Text Coverage -->
  <!-- F3 Canonical and Meta Robots -->

  <!-- CATEGORY G: Strategic Fit (weight 0.04) -->
  <!-- G1 ICP Alignment Score — G2 Anti-Hallucination Positioning -->
  <!-- G3 Competitive Differentiation -->

  <!-- CATEGORY H: Conversion Proof Layer (weight 0.09) -->
  <!-- NEW1 Product Proof Strength — NEW2 CTA Naturalness -->
  <!-- NEW3 SERP Replaceability — NEW4 Signup Friction Reduction -->
</parameter_registry>

<n8n_output_format>
  <critical_rules>
    OUTPUT EXACTLY TWO BLOCKS:
    BLOCK 1: One header row with all column names, pipe-delimited.
    BLOCK 2: One data row per URL, pipe-delimited.
    Then ESCALATION rows.
    NO prose. NO commentary. NO additional tables. NO markdown. NO asterisks.
    NO bold. NO backticks. Every cell must be populated.
    Use DATA_UNAVAILABLE if genuinely missing. Pipe delimiter only.
    Never use pipe character inside cell content — replace with semicolons.
    Never leave a cell empty.
  </critical_rules>
  <column_map>
    URL_ID|Blog_URL|URL_Slug|Focus_Keyword|Post_Tier|Funnel_Stage|Content_Silo|ICP_Fit|Funnel_Conversion_Role|Reader_Awareness_Stage|One_Line_Summary|Core_Theme|Reader_Promise|Word_Count|Flesch_Score|Avg_Words_Per_Sentence|Unique_Inlinks|Spelling_Errors|Grammar_Errors|GSC_Clicks|GSC_Impressions|GSC_CTR|GSC_Position|Last_Modified|Meta_Title_Text|Meta_Title_Chars|Meta_Desc_Text|Meta_Desc_Chars|H1_Text|H1_Chars|A1_Score|A1_Flag|A1_Evidence|A1_Fix|A2_Score|A2_Flag|A2_Evidence|A2_Fix|A3_Score|A3_Flag|A3_Flagged_Claims|A3_Fix|A4_Score|A4_Flag|A4_Stale_Claims|A4_Fix|A5_Score|A5_Flag|A5_Ideal_WC|A5_Fluff_Ratio|A5_Fix|A6_Score|A6_Flag|A6_Violations|A6_Fix|A7_Score|A7_Flag|A7_Fix|A8_Score|A8_Flag|A8_Banned_Words_Found|A8_Fix|A9_Score|A9_Flag|A9_External_Domains|A9_Fix|A10_Score|A10_Flag|A10_Missing_Subtopics|A10_Fix|A11_Score|A11_Flag|A11_Duplication_Note|A11_Fix|Cat_A_Score|Cat_A_Pass_Fail|B1_Score|B1_Flag|B1_Evidence|B1_Fix|B2_Score|B2_Flag|B2_H1_Match_Type|B2_Fix|B3_Score|B3_Flag|B3_KW_Position_Words|B3_First_Sentence|B3_Fix|B4_Score|B4_Flag|B4_KH_Count|B4_All_H2_Headings|B4_Fix|B5_Score|B5_Flag|B5_KW_In_Title|B5_Power_Word|B5_Fix|B6_Score|B6_Flag|B6_CTA_Verb_Found|B6_KW_In_Desc|B6_Fix|B7_Score|B7_Flag|B7_Slug|B7_Slug_Issues|B7_Fix|B8_Score|B8_Flag|B8_Cannibal_URLs|B8_Fix|Cat_B_Score|Cat_B_Pass_Fail|C1_Score|C1_Flag|C1_CTA_Text_Found|C1_CTA_Position|C1_Stage_Match|C1_CTA_Naturalness_Raw|C1_Fix|C2_Score|C2_Flag|C2_Product_Mentions|C2_First_Mention_Position|C2_Problem_Match|C2_Pitch_Quality|C2_Fix|C3_Score|C3_Flag|C3_Format_Match|C3_Fix|C4_Score|C4_Flag|C4_Problem_Frames|C4_Urgency_Signals|C4_Trial_Relevance|C4_Fix|C5_Score|C5_Flag|C5_Conversion_Role_Fit|C5_Organic_Path|C5_Fix|Cat_C_Score|Cat_C_Pass_Fail|Recommended_CTA_Text|Recommended_CTA_Placement|Funnel_Gap|Trial_Potential|D1_Score|D1_Flag|D1_Best_Sentence|D1_Worst_Sentence|D1_Fix|D2_Score|D2_Flag|D2_Specificity_Rate|D2_Worst_Vague_Para|D2_Fix|D3_Score|D3_Flag|D3_Author_Bio|D3_Date_Visible|D3_Case_Study_Ref|D3_Fix|D4_Score|D4_Flag|D4_Domain_List|D4_Fix|Cat_D_Score|Cat_D_Pass_Fail|E1_Score|E1_Flag|E1_Total_Internal|E1_Product_Page_Links|E1_All_Internal_Links|E1_BOF_Handoff_Quality|E1_Fix|E2_Score|E2_Flag|E2_Orphan_Flag|E2_Fix|E3_Score|E3_Flag|E3_Descriptive_Rate|E3_Generic_Anchors_List|E3_Fix|Cat_E_Score|Cat_E_Pass_Fail|Orphan_Status|Suggested_Internal_Links|F1_Score|F1_Flag|F1_Schema_Types_Present|F1_Orphan_FAQ|F1_Fix|F2_Score|F2_Flag|F2_Total_Images|F2_Alt_Coverage_Rate|F2_Missing_Alt_Imgs|F2_Fix|F3_Score|F3_Flag|F3_Canonical_URL|F3_Canonical_Correct|F3_Fix|Cat_F_Score|Cat_F_Pass_Fail|G1_Score|G1_Flag|G1_ICP_Signals_Found|G1_Off_ICP_Reason|G1_Fix|G2_Score|G2_Flag|G2_AH_Mentions|G2_Differentiator_Pitch|G2_Fix|G3_Score|G3_Flag|G3_Competitor_Mentions|G3_Unique_Angle|G3_Fix|Cat_G_Score|Cat_G_Pass_Fail|NEW1_Score|NEW1_Flag|NEW1_Proof_Signals_Found|NEW1_Proprietary_Knowledge|NEW1_Fix|NEW2_Score|NEW2_Flag|NEW2_Setup_Present|NEW2_Fix|NEW3_Score|NEW3_Flag|NEW3_Replaceability_Label|NEW3_Unique_Signals_Found|NEW3_Fix|NEW4_Score|NEW4_Flag|NEW4_SFQ_Answered|NEW4_SFQ_Missing|NEW4_Fix|Cat_H_Score|Cat_H_Pass_Fail|Product_Proof_Gap|Composite_100|Grade|Rank_Tier|Strategic_Decision|Decision_Reason|Urgency|Flags_Count|Params_Failed|Priority_Action|SERP_Replaceability_Label|Portfolio_Uniqueness|Can_It_Drive_Trial|Why_Or_Why_Not|Removal_Recommendation|Removal_Reason|SEO_Quick_Win|Technical_Quick_Win|Top_Fix_Action_1|Top_Fix_Action_2|Top_Fix_Action_3|AC_Primary_Keyword|AD_Est_Volume|AE_Blog_Intent|AF_Slug_Content_Match|AG_Grammar_Issues|AH_Spelling_Issues|AI_Factual_Accuracy|AJ_Answer_Quality_1to5|AK_Relevance_1to5|AL_Intent_Alignment_1to5|AM_Auditor_Notes|LSI_Keywords_Found|LSI_Keywords_Missing|Entity_Coverage|Schema_Types_Present|FAQ_Schema|Featured_Snippet_Eligible|Cannibalization_Risk|Keyword_Focus_Quality|Topic_Drift_Present|Heading_Keyword_Density|All_H3_Headings|External_Links_Count|External_Domains_List|Competitor_Links_Found|Shared_Focus_Keyword_With|Shared_Core_Theme_With|Overlap_Type|Merge_Recommended_Action|Merge_Destination|Content_To_Preserve
  </column_map>
  <escalation_suffix>
    After all data rows emit:
    MERGE_CANDIDATES|[cannibal URL_ID pairs]
    COMMODITY_CONTENT|[URL_IDs where NEW3 less than 4]
    TRIAL_DEAD_ZONES|[URL_IDs where Cat_C + Cat_H combined less than 5.0]
    ICP_VIOLATIONS|[URL_IDs where ICP_FIT = OFF_ICP]
    SYSTEMIC_FLAGS|[flag type triggered in 3+ URLs]
    CRITICAL_REMOVALS|[URL_IDs with Composite less than 40]
    TOP_QUICK_WINS|[Top 5 actions by effort/impact]
    AUDIT_COMPLETE|[N URLs processed; total flags: N; parameters scored: N]
  </escalation_suffix>
</n8n_output_format>'''


# ── URL Fetching ──────────────────────────────────────────────────────────────
def fetch_url(url: str) -> dict:
    """Fetch URL and extract structured content."""
    result = {
        "url": url,
        "status_code": None,
        "error": None,
        "meta_title": "",
        "meta_title_chars": 0,
        "meta_desc": "",
        "meta_desc_chars": 0,
        "h1": "",
        "h1_chars": 0,
        "headings": [],
        "body_text": "",
        "word_count": 0,
        "internal_links": [],
        "external_links": [],
        "images": [],
        "schema_blocks": [],
        "canonical": "",
        "meta_robots": "",
        "pub_date": "",
        "author": "",
        "customgpt_mentions": 0,
    }

    try:
        resp = requests.get(url, headers=FETCH_HEADERS, timeout=FETCH_TIMEOUT)
        result["status_code"] = resp.status_code

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip noise elements
        for tag in soup.select(
            "nav, header, footer, aside, .sidebar, .widget, "
            "[class*='cookie'], [id*='cookie'], [class*='banner'], "
            "[class*='popup'], [class*='modal'], script, style, noscript, "
            ".nav, .navigation, .menu, .comments, #comments"
        ):
            tag.decompose()

        # Meta title
        title_tag = soup.find("title")
        if title_tag:
            result["meta_title"] = title_tag.get_text(strip=True)
            result["meta_title_chars"] = len(result["meta_title"])

        # Meta description
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            result["meta_desc"] = md["content"].strip()
            result["meta_desc_chars"] = len(result["meta_desc"])

        # Canonical
        canon = soup.find("link", rel="canonical")
        if canon:
            result["canonical"] = canon.get("href", "")

        # Meta robots
        robots = soup.find("meta", attrs={"name": "robots"})
        if robots:
            result["meta_robots"] = robots.get("content", "")

        # H1
        h1 = soup.find("h1")
        if h1:
            result["h1"] = h1.get_text(strip=True)
            result["h1_chars"] = len(result["h1"])

        # All headings H1–H4
        for h in soup.find_all(["h1", "h2", "h3", "h4"]):
            result["headings"].append({
                "level": h.name.upper(),
                "text": h.get_text(strip=True)
            })

        # Schema blocks
        for schema in soup.find_all("script", type="application/ld+json"):
            result["schema_blocks"].append(schema.get_text(strip=True)[:500])

        # Publication date
        for sel in ["time[datetime]", ".date", ".post-date", "[itemprop='datePublished']"]:
            el = soup.select_one(sel)
            if el:
                result["pub_date"] = el.get("datetime", el.get_text(strip=True))
                break

        # Author
        for sel in [".author", "[rel='author']", "[itemprop='author']", ".byline"]:
            el = soup.select_one(sel)
            if el:
                result["author"] = el.get_text(strip=True)[:100]
                break

        # Images
        for img in soup.find_all("img"):
            result["images"].append({
                "src": img.get("src", ""),
                "alt": img.get("alt", "")
            })

        # Extract main content area
        main_el = (
            soup.find("article") or
            soup.find("main") or
            soup.find(class_=lambda c: c and any(
                x in c for x in ["post-content", "entry-content", "article-body", "blog-content"]
            )) or
            soup.find("body")
        )
        body_text = main_el.get_text(separator=" ", strip=True) if main_el else ""
        words = body_text.split()
        result["word_count"] = len(words)
        result["body_text"] = " ".join(words[:MAX_BODY_WORDS])

        # Count CustomGPT mentions
        full_lower = body_text.lower()
        result["customgpt_mentions"] = full_lower.count("customgpt")

        # Links
        base_domain = url.split("/")[2] if "/" in url else ""
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            anchor = a.get_text(strip=True)
            if not href or href.startswith("#") or href.startswith("mailto:"):
                continue
            if base_domain and base_domain in href:
                result["internal_links"].append({"href": href, "anchor": anchor})
            elif href.startswith("/"):
                result["internal_links"].append({"href": href, "anchor": anchor})
            elif href.startswith("http"):
                result["external_links"].append({"href": href, "anchor": anchor})

    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
        result["status_code"] = 0
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error: {str(e)[:100]}"
        result["status_code"] = 0
    except Exception as e:
        result["error"] = str(e)[:200]
        result["status_code"] = 0

    return result


# ── Build Claude message ──────────────────────────────────────────────────────
def build_url_block(uid: int, data: dict) -> str:
    """Serialize a single URL's fetched data into a text block for Claude."""
    if data["error"] or (data["status_code"] and data["status_code"] != 200):
        return (
            f"URL_ID: {uid}\n"
            f"URL: {data['url']}\n"
            f"STATUS_CODE: {data['status_code'] or 0}\n"
            f"ERROR: {data['error']}\n"
            f"NOTE: Skip this URL — not indexable or fetch failed.\n"
        )

    headings_fmt = "\n".join(
        f"  {h['level']}: {h['text']}" for h in data["headings"]
    ) or "  NONE"

    internal_fmt = "; ".join(
        f"{l['anchor']!r} -> {l['href']}" for l in data["internal_links"][:25]
    ) or "NONE"

    external_fmt = "; ".join(
        f"{l['anchor']!r} -> {l['href']}" for l in data["external_links"][:20]
    ) or "NONE"

    images_fmt = "; ".join(
        f"alt={l['alt']!r}" for l in data["images"][:20]
    ) or "NONE"

    schema_fmt = " | ".join(data["schema_blocks"][:3]) or "NONE"

    return f"""--- BEGIN URL_ID {uid} ---
URL_ID: {uid}
URL: {data['url']}
STATUS_CODE: 200
META_TITLE: {data['meta_title']}
META_TITLE_CHARS: {data['meta_title_chars']}
META_DESC: {data['meta_desc']}
META_DESC_CHARS: {data['meta_desc_chars']}
CANONICAL: {data['canonical']}
META_ROBOTS: {data['meta_robots'] or 'index,follow'}
H1: {data['h1']}
H1_CHARS: {data['h1_chars']}
WORD_COUNT_CRAWLED: {data['word_count']}
PUB_DATE_VISIBLE: {data['pub_date'] or 'NOT FOUND'}
AUTHOR: {data['author'] or 'NOT FOUND'}
CUSTOMGPT_MENTIONS: {data['customgpt_mentions']}
SCHEMA_BLOCKS: {schema_fmt}

HEADINGS (H1-H4 in DOM order):
{headings_fmt}

INTERNAL_LINKS (first 25): {internal_fmt}
EXTERNAL_LINKS (first 20): {external_fmt}
IMAGES (first 20 alt texts): {images_fmt}

BODY_TEXT (first {MAX_BODY_WORDS} words):
{data['body_text']}
--- END URL_ID {uid} ---
"""


def call_claude_audit(batch_data: list[dict], batch_start_id: int) -> str:
    """Send batch to Claude API and return the raw pipe-delimited response."""
    client = anthropic.Anthropic(api_key=API_KEY)

    n = len(batch_data)
    url_blocks = "\n\n".join(
        build_url_block(batch_start_id + i + 1, d)
        for i, d in enumerate(batch_data)
    )

    user_message = f"""{AUDIT_PROMPT}

<crawled_content>
NOTE: Screaming Frog and GSC data are NOT available for this batch.
Use DATA_UNAVAILABLE for: Unique_Inlinks, Spelling_Errors, Grammar_Errors,
GSC_Clicks, GSC_Impressions, GSC_CTR, GSC_Position, Last_Modified (use pub date if visible).
For Word_Count: use WORD_COUNT_CRAWLED from each URL block.
For Flesch_Score and Avg_Words_Per_Sentence: estimate from crawled body text.

Process EXACTLY {n} URLs below. Emit EXACTLY {n} data rows (one per URL).

{url_blocks}
</crawled_content>

EXECUTE FULL AUDIT NOW.
Output: ONE pipe-delimited header row, then ONE pipe-delimited data row per URL (total {n} rows), then ESCALATION rows.
Zero markdown. Zero prose. Zero code fences. Pure pipe-delimited text only.
Never use the | character inside any cell value — replace with semicolons.
Every cell must be populated. Use DATA_UNAVAILABLE only when genuinely missing."""

    full_response = ""
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                print(text, end="", flush=True)
    except Exception:
        raise

    print()  # newline after stream ends
    return full_response


# ── Parse pipe-delimited response ────────────────────────────────────────────
ESCALATION_PREFIXES = (
    "MERGE_CANDIDATES", "COMMODITY_CONTENT", "TRIAL_DEAD_ZONES",
    "ICP_VIOLATIONS", "SYSTEMIC_FLAGS", "CRITICAL_REMOVALS",
    "TOP_QUICK_WINS", "AUDIT_COMPLETE",
)

def parse_pipe_response(text: str) -> tuple:
    """
    Extract header row and data rows from Claude's pipe-delimited output.
    Returns (header: list[str] | None, rows: list[list[str]]).
    """
    # Strip any accidental markdown fences
    text = text.replace("```", "").strip()

    header = None
    data_rows = []

    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue

        # Skip escalation rows
        if any(line.startswith(p) for p in ESCALATION_PREFIXES):
            continue

        cells = [c.strip() for c in line.split("|")]

        # Identify header: first pipe line containing "URL_ID" or "Blog_URL"
        if header is None:
            if cells and any(c in ("URL_ID", "Blog_URL") for c in cells):
                header = cells
                continue

        # Identify data rows: first cell is a digit (URL_ID)
        if header is not None:
            first = cells[0] if cells else ""
            if first.isdigit():
                data_rows.append(cells)

    return header, data_rows


# ── Progress helpers ──────────────────────────────────────────────────────────
def load_progress() -> int:
    if Path(PROGRESS_FILE).exists():
        try:
            return json.loads(Path(PROGRESS_FILE).read_text()).get("processed", 0)
        except Exception:
            return 0
    return 0


def save_progress(processed: int, total: int) -> None:
    Path(PROGRESS_FILE).write_text(
        json.dumps({"processed": processed, "total": total}, indent=2)
    )


# ── CSV helpers ───────────────────────────────────────────────────────────────
def write_header(header: list[str]) -> None:
    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(header)


def append_rows(rows: list[list[str]]) -> None:
    with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def save_raw_debug(batch_start: int, text: str) -> None:
    fname = f"debug_batch_{batch_start}.txt"
    Path(fname).write_text(text, encoding="utf-8")
    print(f"  [debug] Raw Claude response saved to {fname}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    # ── Read URL list ──────────────────────────────────────────────────────
    if not Path(URLS_FILE).exists():
        print(f"ERROR: {URLS_FILE} not found.")
        print("Create it with one URL per line, then rerun this script.")
        sys.exit(1)

    raw = Path(URLS_FILE).read_text(encoding="utf-8").splitlines()
    all_urls = [l.strip() for l in raw if l.strip() and not l.strip().startswith("#")]

    total = len(all_urls)
    if total == 0:
        print("No URLs found in urls.txt (blank or all lines are comments).")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"  CustomGPT Blog Audit — {total} URLs to process")
    print(f"  Model : {MODEL}")
    print(f"  Batch : {BATCH_SIZE} URLs per Claude call")
    print(f"  Output: {RESULTS_FILE}")
    print(f"{'='*60}\n")

    # ── Resume ────────────────────────────────────────────────────────────
    processed = load_progress()
    if processed >= total:
        print("All URLs already processed. Delete audit_progress.json to restart.")
        sys.exit(0)
    if processed > 0:
        print(f"Resuming from URL {processed + 1}/{total}\n")

    header_written = Path(RESULTS_FILE).exists() and processed > 0

    # ── Batch loop ────────────────────────────────────────────────────────
    for batch_start in range(processed, total, BATCH_SIZE):
        batch_urls  = all_urls[batch_start: batch_start + BATCH_SIZE]
        batch_end   = batch_start + len(batch_urls)
        batch_num   = batch_start // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n{'─'*60}")
        print(f"  Batch {batch_num}/{total_batches}  |  URLs {batch_start+1}–{batch_end} of {total}")
        print(f"{'─'*60}")

        # Step 1 — Fetch each URL
        batch_data = []
        for url in batch_urls:
            print(f"  Fetching  {url} ...", end=" ", flush=True)
            data = fetch_url(url)
            status = (
                f"HTTP {data['status_code']}" if data["status_code"]
                else f"FAIL: {data['error']}"
            )
            print(status)
            batch_data.append(data)

        # Step 2 — Send to Claude (with one retry on failure)
        print(f"\n  Sending to Claude ...\n")
        response_text = ""
        for attempt in (1, 2):
            try:
                response_text = call_claude_audit(batch_data, batch_start)
                break
            except anthropic.RateLimitError:
                wait = 60 * attempt
                print(f"  Rate limited. Waiting {wait}s before retry ...")
                time.sleep(wait)
            except Exception as exc:
                print(f"  Claude error (attempt {attempt}): {exc}")
                if attempt == 1:
                    print("  Retrying in 30s ...")
                    time.sleep(30)
                else:
                    traceback.print_exc()
                    print("  Skipping batch and saving progress.")
                    save_progress(batch_end, total)
                    break

        if not response_text:
            continue

        # Step 3 — Parse response
        header, rows = parse_pipe_response(response_text)

        if header and not header_written:
            write_header(header)
            header_written = True

        if rows:
            append_rows(rows)
            print(f"\n  ✓ {len(rows)} row(s) written to {RESULTS_FILE}")
        else:
            print("\n  ⚠ Could not parse data rows from Claude response.")
            save_raw_debug(batch_start, response_text)

        # Step 4 — Save progress
        save_progress(batch_end, total)
        print(f"\n  Done {batch_end}/{total}")

        # Step 5 — Rate-limit buffer
        if batch_end < total:
            print(f"  Waiting {SLEEP_BETWEEN}s before next batch ...")
            time.sleep(SLEEP_BETWEEN)

    print(f"\n{'='*60}")
    print(f"  Audit complete!")
    print(f"  Results : {RESULTS_FILE}")
    print(f"  Progress: {PROGRESS_FILE}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
