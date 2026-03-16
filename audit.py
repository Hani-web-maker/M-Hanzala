#!/usr/bin/env python3
"""
Blog Audit Script
=================
Audits blog URLs using Claude API (claude-sonnet-4-20250514).
Outputs: audit_results.csv

Usage:
    python audit.py

Features:
- Fetches full blog content via requests + BeautifulSoup
- Sends content to Claude API with the full audit prompt
- Processes URLs in batches of 5
- Saves progress after every batch (resumes if interrupted)
- Prints progress: "Done 50/1173"
"""

import anthropic
import csv
import json
import os
import sys
import time
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────────

# Set your API key via environment variable:  export ANTHROPIC_API_KEY="sk-ant-..."
# Or paste it directly here (not recommended for shared repos):
API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL     = "claude-sonnet-4-20250514"
OUTPUT_CSV     = "audit_results.csv"
PROGRESS_FILE  = "audit_progress.json"
BATCH_SIZE     = 5
FETCH_TIMEOUT  = 30          # seconds per HTTP request
INTER_BATCH_DELAY = 3        # seconds between batches (rate limit buffer)
MAX_BODY_CHARS = 12000       # truncate body to stay within token budget

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── URLs to Audit ──────────────────────────────────────────────────────────────
# Paste all 1173 URLs here. The 10 test URLs are pre-loaded.
URLS = [
    "https://customgpt.ai/100s-of-openai-compatible-tools-connect-to-rag-api/",
    "https://customgpt.ai/academic-ai-writing/",
    "https://customgpt.ai/7-big-brands-using-generative-ai/",
    "https://customgpt.ai/2024-prediction-ai-budget-allocation/",
    "https://customgpt.ai/37-customgpt-platform-enhancements-the-june-tsunami/",
    "https://customgpt.ai/aeo-optimization-50-word-answer-faq-schema/",
    "https://customgpt.ai/accessing-private-content-customgpt-guide/",
    "https://customgpt.ai/add-sitemap-to-existing-project-customgpt-api/",
    "https://customgpt.ai/add-file-to-existing-project-using-customgpt-api/",
    "https://customgpt.ai/affiliate-marketing-ai-tools/",
    # ← paste remaining URLs below this line, one per line, quoted with trailing comma
]

# ── Audit System Prompt ────────────────────────────────────────────────────────
# Full audit framework (target_batch is injected dynamically per batch)
AUDIT_SYSTEM_PROMPT = r"""<?xml version="1.0" encoding="UTF-8"?>
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
    R01  CRAWL EVERY URL FULLY. Strip nav/header/footer/sidebar/cookie banners.
         Read complete body. Cache all sub-elements per EXECUTION PROTOCOL below.
         NOTE: Pre-fetched content is supplied in each user message. Use it directly
         instead of attempting live crawls. This satisfies Phase 2 (CRAWL_AND_CACHE).
    R02  MERGE crawled data with pre-loaded Screaming Frog + GSC data.
         Pre-loaded SF values (word count, Flesch, inlinks, meta chars, grammar/spelling)
         are AUTHORITATIVE. Never re-estimate — use exact pre-loaded values.
         If SF/GSC data is marked DATA_UNAVAILABLE, score = 0, flag = DATA_UNAVAILABLE.
    R03  SCORE using ONLY formulas defined in PARAMETER REGISTRY. No substitutions.
    R04  DATA_UNAVAILABLE rule: if required data cannot be accessed, score = 0,
         flag = DATA_UNAVAILABLE, explain in corrective action. Never invent scores.
    R05  FLAG_RULE is independent of threshold. A PASS can still TRIGGER a flag.
         Both results must appear in every parameter column.
    R06  SCORE COMPRESSION IS FABRICATION. If category stdev across URLs is less
         than 0.3, you are pattern-matching not evaluating. Each URL earns its score
         independently from page evidence.
    R07  Context values locked in PHASE 3 (FOCUS_KEYWORD, FUNNEL_STAGE, ICP_FIT,
         FUNNEL_CONVERSION_ROLE) cannot change during parameter scoring.
         Note conflicts in the CONTEXT_NOTE field but do not re-infer mid-audit.
    R08  Factual accuracy (A3, Phase 11): only flag claims you are GENUINELY CONFIDENT
         are wrong or seriously outdated. Mark UNVERIFIED — not FLAG — for uncertain claims.
    R09  ICP classification: Off-ICP = affiliate marketing, YouTube tutorials, SEO tactics,
         general internet content unrelated to AI/business/knowledge management.
         Apply consistently across all URLs in the batch.
    R10  Composite below 40: always emit CRITICAL_REMOVAL in escalation block.
         State whether removal will cause GSC traffic loss using pre-loaded impression/click data.
    R11  OUTPUT FORMAT: Emit ONE pipe-delimited data row per URL.
         All columns from all audit dimensions are flattened into a single row.
         This is designed for n8n to parse and paste directly into a single Google Sheet.
         Every cell must be populated. Never leave a cell blank. Use DATA_UNAVAILABLE if missing.
         Do not emit multiple tables or sheets. One header row followed by one data row per URL.
    R12  All scores 0.0–10.0 (one decimal). Category scores 0.00–10.00 (two decimals).
         Composite_100: 0.0–100.0 (one decimal). Grade: A+ | A | B | C | D | F.
  </prime_directive>
</identity>
<product_context>
  <brand>CustomGPT.ai</brand>
  <url>https://customgpt.ai</url>
  <tagline>Trusted Business AI. No Hallucinations. Your Knowledge. Your Rules.</tagline>
  <what_it_is>
    No-code platform for building private RAG (Retrieval-Augmented Generation) AI chatbot
    agents trained on a business's own documents, website, and data sources.
    Agents answer ONLY from approved knowledge — no made-up facts.
    Third-party verified #1 for anti-hallucination accuracy vs OpenAI and Google.
    Supports 1,400+ file types. 100+ one-click integrations.
    SOC-2 Type II + GDPR compliant. 100% uptime SLA.
    Deployable on web, helpdesk, mobile, API. Live in 15 minutes, zero engineering.
  </what_it_is>
  <icp>
    PRIMARY:    Support teams — ticket deflection, agent assist, self-serve KB
    SECONDARY:  Manufacturing companies — SOP/technical doc search, field service
    TERTIARY:   Mid-market SaaS companies — internal knowledge search, onboarding
    ALSO SERVES: Professional services, education, government, legal, healthcare
    COMPANY SIZE: 100–5,000 employees with budget for $89+/mo commitment
  </icp>
  <use_cases>
    UC1  Helpdesk Ticket Deflection — deflect up to 93% of support tickets
    UC2  Internal Knowledge Search (Enterprise RAG) — employees get fast answers
    UC3  AI Site Search / Generative Answers — replace keyword search on websites
    UC4  Knowledge-as-a-Service — monetise expertise behind paywall
    UC5  Agent Assist — AI drafts replies for human agents to approve
  </use_cases>
  <key_differentiators>
    DIFF1  Anti-hallucination: answers ONLY from uploaded data, never invented
    DIFF2  #1 accuracy (third-party verified vs OpenAI + Google)
    DIFF3  Clickable citations with every answer
    DIFF4  No-code: live in 15 minutes, zero engineering
    DIFF5  Data privacy: RAG architecture = no training on your data
    DIFF6  Predictable pricing: no surprise dev costs
  </key_differentiators>
  <competitors>
    Chatbase | Botpress | Intercom Fin | SiteGPT | Wonderchat | Drift |
    LivePerson | Ada | Forethought | Glean | Notion AI | DocsBot AI | Botsonic
  </competitors>
  <brand_voice>
    TONE:         Very casual yet professional. Conversational, direct, no buzzword fluff.
    PERSON:       First-person "I", speaks to "you" (the reader) naturally.
    PARAGRAPH:    Short — 1 to 2 sentences max.
    CLAIMS:       Specific with numbers. Real examples. No vague "many businesses" statements.
    BANNED_WORDS: delve | tapestry | landscape | realm | nuanced | multifaceted |
                  "it is worth noting" | "in conclusion" | leverage (as verb) |
                  "in today's world" | "let's dive in" | game-changer | revolutionise |
                  cutting-edge | "at the end of the day" | "in summary" | to summarize |
                  Furthermore | Moreover | Additionally (as paragraph openers)
  </brand_voice>
  <scoring_context>
    RELEVANCE TARGET:     Support manager, manufacturing ops lead, or SaaS CTO trying
                          to reduce ticket volume or build trusted internal AI.
                          Everything else is off-ICP.
    COMMERCIAL INTENT:    Does the post lead the reader toward free trial, demo, or pricing?
                          Does it frame the problem so CustomGPT.ai is the obvious solution?
    BRAND FIT:            Does this post sound like someone who uses CustomGPT.ai daily?
                          Or could it be published by Chatbase, Botpress, or any generic AI company?
                          Posts about affiliate marketing, YouTube, or non-AI topics = LOW brand fit.
    CONVERSION KPI:       Every blog is evaluated on one ultimate question:
                          "Can this article realistically influence a free-trial signup?"
                          Traffic alone is not success. Wrong-audience traffic is waste.
  </scoring_context>
</product_context>
<execution_protocol>
  <phase id="1" name="PREFLIGHT_DATA_MERGE">
    <action>Load pre-loaded data block for this URL from the prefetched_content section.</action>
    <action>Confirm: status_code = 200 AND indexable.</action>
    <gate>
      If status_code != 200: mark all params HTTP_ERROR:[code]. Skip to next URL.
      If non-indexable: mark all params NOINDEX_SKIP. Skip.
    </gate>
    <action>Lock SF values as immutable. Cannot be overridden by crawl data.</action>
    <note>SF/GSC data is not pre-loaded in this run. Use DATA_UNAVAILABLE for those fields
    and derive scores from the pre-fetched page content only.</note>
  </phase>
  <phase id="2" name="CRAWL_AND_CACHE">
    <note>Use the pre-fetched content provided in the user message. Do not attempt live crawls.</note>
    <cache_item id="2a">Full post body text — strip nav, header, footer, sidebar, cookie banners, comments</cache_item>
    <cache_item id="2b">All heading tags H1–H4 in DOM order with exact text</cache_item>
    <cache_item id="2c">All img tags: src + alt attribute text (empty string if absent)</cache_item>
    <cache_item id="2d">All anchor href — separate internal (customgpt.ai) from external</cache_item>
    <cache_item id="2e">First 100 words of body (cached separately)</cache_item>
    <cache_item id="2f">First 200 words of body (cached separately)</cache_item>
    <cache_item id="2g">All JSON-LD and schema.org markup blocks verbatim</cache_item>
    <cache_item id="2h">All CTA elements: buttons, banners, inline action links — capture exact text</cache_item>
    <cache_item id="2i">Publication date and last-modified date if visible in DOM</cache_item>
    <cache_item id="2j">Internal links: count + anchor text list</cache_item>
    <cache_item id="2k">External links: count + domain list + anchor texts</cache_item>
    <cache_item id="2l">Author name and bio section if present</cache_item>
    <cache_item id="2m">Any FAQ section (question + answer blocks)</cache_item>
    <cache_item id="2n">Product mentions: count of "CustomGPT" and "CustomGPT.ai" occurrences</cache_item>
    <cache_item id="2o">Canonical tag URL and meta robots content</cache_item>
  </phase>
  <phase id="3" name="CONTEXT_LOCK">
    <lock name="FOCUS_KEYWORD">
      Derivation order: slug signal wins -&gt; H1 overrides if slug is generic -&gt;
      body first 200 words supplements if H1 absent.
      Lock as single phrase. Do not change during scoring.
    </lock>
    <lock name="POST_TIER">
      PILLAR if word_count >= 2,500 AND topic is broad category.
      STANDARD otherwise.
    </lock>
    <lock name="FUNNEL_STAGE">
      TOFU = informational / educational / definitional
      MOFU = comparison / best-of / vs / alternative
      BOFU = pricing / trial / review / buy / demo
    </lock>
    <lock name="CONTENT_SILO">
      Topic cluster inferred from slug + H2 headings.
    </lock>
    <lock name="ICP_FIT">
      DIRECT   = content speaks to support team / SaaS ops / manufacturing pain points
      ADJACENT = related but off-ICP (general AI, chatbots without ICP specifics)
      OFF_ICP  = unrelated (affiliate marketing, YouTube, SEO tactics, general internet)
    </lock>
    <lock name="FUNNEL_CONVERSION_ROLE">
      TRIAL_DRIVER | TRUST_BUILDER | OBJECTION_HANDLER |
      FEATURE_EXPLAINER | COMPETITOR_INTERCEPTION | AUTHORITY_BUILDER
    </lock>
    <lock name="READER_AWARENESS_STAGE">
      PROBLEM_AWARE | SOLUTION_AWARE | PRODUCT_AWARE | BRAND_AWARE
    </lock>
    <lock name="ARTICLE_ABSTRACTIONS">
      ONE_LINE_SUMMARY:  what the article says (1 sentence, factual)
      CORE_THEME:        why this article exists (1 sentence, strategic)
      READER_PROMISE:    what outcome the reader is promised (1 sentence, user-centric)
    </lock>
  </phase>
  <phase id="4" name="PARAMETER_EVALUATION">
    Run all 46 parameters in order A1 -&gt; G3 -&gt; NEW1 -&gt; NEW4.
    For each:
      4a. Apply FORMULA from PARAMETER REGISTRY
      4b. Map raw output to SCORE (0.0–10.0, one decimal)
      4c. Compare vs THRESHOLD -&gt; PASS or FAIL
      4d. Evaluate FLAG_RULE independently -&gt; TRIGGERED or CLEAR
      4e. Record: raw evidence | score | PASS/FAIL | flag status | corrective action
  </phase>
  <phase id="5" name="CATEGORY_AGGREGATION">
    <formula>
      Cat_X = Sum(Param_Score * Param_Weight_In_Category) / Sum(Param_Weights)
      Round to 2 decimal places.
    </formula>
  </phase>
  <phase id="6" name="COMPOSITE_SCORE">
    <formula>
      Composite_100 = (
        (Cat_A * 0.25) +
        (Cat_B * 0.20) +
        (Cat_C_CONV * 0.20) +
        (Cat_D * 0.10) +
        (Cat_E * 0.07) +
        (Cat_F * 0.05) +
        (Cat_G * 0.04) +
        (Cat_H * 0.09)
      ) * 10
    </formula>
    <note>
      Cat_H = average of NEW1_Product_Proof, NEW2_CTA_Naturalness,
      NEW3_SERP_Replaceability, NEW4_Signup_Friction_Reduction.
    </note>
  </phase>
</execution_protocol>
<parameter_registry>
  <category id="A" name="Content Quality" composite_weight="0.25" pass_threshold="7.0">
    <parameter id="A1" name="Information Gain" weight_in_category="0.12">
      <formula>
        Unique_Claims = claims containing: named tool | named company | specific number |
          percentage | date | proprietary process | original example |
          NOT found in a generic AI overview article.
        Total_Claims = all distinct factual or instructional claims in post.
        Generic_Filler = sentences containing "many businesses" | "various options" |
          "in today's world" | "a lot of" | "different types of" (without naming types).
        IG_Score = (Unique_Claims / max(1, Total_Claims)) * 10 - (0.5 * min(4, Generic_Filler))
        Floor at 0.
      </formula>
      <threshold>6.0</threshold>
      <flag_rule>
        TRIGGERED if Unique_Claims less than 5
        OR Generic_Filler greater than 5
        OR post reads as a definition article with no brand perspective.
      </flag_rule>
    </parameter>
    <parameter id="A2" name="Answer Quality" weight_in_category="0.12">
      <formula>
        Specificity_Sub = (Named_Tools + Named_Steps + Concrete_Examples) /
          max(1, Total_Paragraphs) * 10
        Actionability_Sub = (Steps_Present * 4 + Templates_Or_Checklists * 3 + Decision_Tree * 3) / 10
        Completeness_Sub = (Answered_Sub_Questions / Total_Implied_Sub_Questions) * 10
        AQ_Score = (0.40 * Specificity_Sub) + (0.35 * Actionability_Sub) + (0.25 * Completeness_Sub)
        ANSWER_QUALITY_CONVERSION_BONUS: +0.5 if article answers pre-signup friction questions.
      </formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="A3" name="Factual Accuracy" weight_in_category="0.11">
      <formula>
        Extract ALL verifiable claims. Verify each.
        FA_Score = (Verified_Claims / max(1, Total_Verifiable_Claims)) * 10
        HARD PENALTIES: Any pricing/feature claim contradicts MODULE 2: FA_Score capped at 4.
      </formula>
      <threshold>8.0</threshold>
    </parameter>
    <parameter id="A4" name="Content Freshness" weight_in_category="0.08">
      <formula>
        Last_Modified_Days = days between last_modified and today (March 2026).
        Old_Stats = count of statistics from sources older than 2 years.
        Dead_Claims = count of "currently" | "recently" | "this year" referencing events older than 12 months.
        Recency_Sub: less than 30 days -> 10 | 31-90 -> 8 | 91-180 -> 6 | 181-365 -> 4 | more than 365 -> 2
        Temporal_Risk_Sub: 0 -> 10 | 1 -> 7 | 2-3 -> 4 | 4+ -> 0
        CF_Score = (0.50 * Recency_Sub) + (0.50 * Temporal_Risk_Sub)
      </formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="A5" name="Word Count vs Topic Depth" weight_in_category="0.08">
      <formula>
        Estimate word count from body text.
        Ideal_WC ranges: Pillar: 2500-4000 | TOFU: 1500-2500 | MOFU: 1200-2000 | BOFU: 800-1500
        Deviation = |word_count - midpoint(Ideal_WC_range)| / midpoint(Ideal_WC_range)
        WC_Score = 10 - (6 * Deviation), floored at 0.
      </formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="A6" name="Heading Architecture" weight_in_category="0.08">
      <formula>
        H1_Count = count of H1 tags.
        Skipped_Levels = heading level jumps more than 1.
        HS_Score = 10 - (3 * (H1_Count - 1)) - (1.5 * Skipped_Levels), floored at 0.
        If H1_Count = 0: HS_Score = 0.
      </formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="A7" name="Readability Score" weight_in_category="0.08">
      <formula>
        Estimate Flesch-Kincaid from sentence/word complexity.
        R_Score based on readability estimate.
      </formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="A8" name="AI Writing Contamination" weight_in_category="0.10">
      <formula>
        Banned_Words: delve | tapestry | landscape | realm | nuanced | multifaceted |
          "it is worth noting" | "in conclusion" | leverage (as verb) |
          "in today's world" | "let's dive in" | game-changer | revolutionise |
          cutting-edge | "at the end of the day" | "in summary" | "to summarize"
        Banned_Count = total occurrences.
        AIT_Score = 10 - (1.5 * min(5, Banned_Count)), floored at 0.
      </formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="A9" name="Evidence and Citation Quality" weight_in_category="0.10">
      <formula>
        Authority_Domains = links to research papers | established media | official company blogs.
        EQ_Score = min(10, (Authority_Domains * 1.5) + (External_Domains * 0.5)), floored at 0.
      </formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="A10" name="Topic Coverage Completeness" weight_in_category="0.08">
      <formula>
        Expected_Subtopics = 5-10 subtopics a searcher would expect.
        TCC_Score = (Covered_Subtopics / max(1, Expected_Subtopics)) * 10
      </formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="A11" name="Content Duplication Risk" weight_in_category="0.05">
      <formula>
        Compare FOCUS_KEYWORD across all URLs in batch.
        CDR_Score = 10 if no overlap | 5 if partial | 0 if high overlap.
      </formula>
      <threshold>7.0</threshold>
    </parameter>
  </category>
  <category id="B" name="On-Page SEO" composite_weight="0.20" pass_threshold="7.0">
    <parameter id="B1" name="Focus Keyword Identification" weight_in_category="0.08">
      <formula>Alignment across slug, H1, meta title, body first 200 words.</formula>
      <threshold>7.5</threshold>
    </parameter>
    <parameter id="B2" name="Keyword in H1" weight_in_category="0.12">
      <formula>Exact/variant/semantic match of focus keyword in H1.</formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="B3" name="Keyword in Introduction" weight_in_category="0.12">
      <formula>Position of focus keyword in first 300 words.</formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="B4" name="Keyword in Subheadings" weight_in_category="0.10">
      <formula>Count of H2/H3 containing keyword variant.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="B5" name="Meta Title Optimization" weight_in_category="0.15">
      <formula>Keyword presence, length (50-60 chars), power words, brand suffix.</formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="B6" name="Meta Description Quality" weight_in_category="0.15">
      <formula>Length (130-160 chars), keyword, CTA verb, uniqueness.</formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="B7" name="URL Slug Quality" weight_in_category="0.13">
      <formula>Stop words, date presence, keyword, length (max 6 words).</formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="B8" name="Keyword Cannibalization" weight_in_category="0.15">
      <formula>Check for same keyword across batch URLs.</formula>
      <threshold>10</threshold>
    </parameter>
  </category>
  <category id="C" name="Conversion Intelligence" composite_weight="0.20" pass_threshold="6.0">
    <parameter id="C1" name="CTA Architecture" weight_in_category="0.22">
      <formula>CTA existence, position, relevance, text quality, stage match.</formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="C2" name="Product-Content Alignment" weight_in_category="0.22">
      <formula>CustomGPT mention count, product-problem match, pitch quality.</formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="C3" name="Funnel Stage Correctness" weight_in_category="0.18">
      <formula>Content format, CTA type, reader awareness match for funnel stage.</formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="C4" name="Commercial Intent Score" weight_in_category="0.20">
      <formula>Problem frames, solution bridges, urgency signals, trial relevance.</formula>
      <threshold>5.0 TOFU / 7.0 MOFU/BOFU</threshold>
    </parameter>
    <parameter id="C5" name="Intent-to-Conversion Fit" weight_in_category="0.18">
      <formula>Conversion role fit + organic conversion path quality.</formula>
      <threshold>5.0</threshold>
    </parameter>
  </category>
  <category id="D" name="Authority and Trust" composite_weight="0.10" pass_threshold="6.0">
    <parameter id="D1" name="Brand Voice Authenticity" weight_in_category="0.30">
      <formula>Conversational directness, specificity, no banned language, CustomGPT POV, flow.</formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="D2" name="Specificity Ratio" weight_in_category="0.30">
      <formula>Specific sentences / total sentences * 10.</formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="D3" name="EEAT Signals" weight_in_category="0.20">
      <formula>Author bio, schema, date, about link, press, case study.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="D4" name="External Citation Authority" weight_in_category="0.20">
      <formula>Tier 1-5 scoring of external links.</formula>
      <threshold>5.0</threshold>
    </parameter>
  </category>
  <category id="E" name="Internal Linking" composite_weight="0.07" pass_threshold="5.0">
    <parameter id="E1" name="Outbound Internal Links" weight_in_category="0.40">
      <formula>Count internal links, product page links, silo links.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="E2" name="Inbound Link Signal" weight_in_category="0.30">
      <formula>Based on unique_inlinks count.</formula>
      <threshold>4.0</threshold>
    </parameter>
    <parameter id="E3" name="Anchor Text Quality" weight_in_category="0.30">
      <formula>Descriptive vs generic anchor text ratio.</formula>
      <threshold>5.0</threshold>
    </parameter>
  </category>
  <category id="F" name="Technical On-Page" composite_weight="0.05" pass_threshold="6.0">
    <parameter id="F1" name="Schema and Structured Data" weight_in_category="0.40">
      <formula>Article schema, FAQ schema, author schema, breadcrumb, HowTo.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="F2" name="Image Alt Text Coverage" weight_in_category="0.40">
      <formula>Alt coverage rate * 5 + descriptive rate * 5.</formula>
      <threshold>7.0</threshold>
    </parameter>
    <parameter id="F3" name="Canonical and Meta Robots" weight_in_category="0.20">
      <formula>Canonical present and self-referencing, no noindex.</formula>
      <threshold>7.0</threshold>
    </parameter>
  </category>
  <category id="G" name="Strategic Fit" composite_weight="0.04" pass_threshold="6.0">
    <parameter id="G1" name="ICP Alignment Score" weight_in_category="0.40">
      <formula>DIRECT=8, ADJACENT=5, OFF_ICP=1 base score.</formula>
      <threshold>6.0</threshold>
    </parameter>
    <parameter id="G2" name="Anti-Hallucination Positioning" weight_in_category="0.35">
      <formula>AH_Mentions * 1.5 + Problem_Frames_AH + Differentiator_Pitch * 2.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="G3" name="Competitive Differentiation" weight_in_category="0.25">
      <formula>Competitor mentions, comparison, wins, unique angle.</formula>
      <threshold>5.0</threshold>
    </parameter>
  </category>
  <category id="H" name="Conversion Proof Layer" composite_weight="0.09" pass_threshold="5.0">
    <parameter id="NEW1" name="Product Proof Strength" weight_in_category="0.30">
      <formula>Proof signals: screenshots, workflow, named example, comparison, source-backed, implementation, quantified outcome.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="NEW2" name="CTA Naturalness" weight_in_category="0.25">
      <formula>Earned logic, setup present, no abrupt insertion, no topic mismatch, no generic text.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="NEW3" name="SERP Replaceability" weight_in_category="0.25">
      <formula>Unique differentiation signals / 5 * 10 - generic signal penalty.</formula>
      <threshold>5.0</threshold>
    </parameter>
    <parameter id="NEW4" name="Signup Friction Reduction" weight_in_category="0.20">
      <formula>Count of SFQ1-SFQ8 answered: security, hallucination, own docs, setup time, integrations, free trial, pricing, social proof.</formula>
      <threshold>4.0</threshold>
    </parameter>
  </category>
</parameter_registry>
<result_bands>
  <band range="90-100" tier="PLATINUM"  grade="A+" decision="AMPLIFY"/>
  <band range="80-89"  tier="GOLD"      grade="A"  decision="OPTIMIZE"/>
  <band range="70-79"  tier="SILVER"    grade="B"  decision="REVAMP"/>
  <band range="55-69"  tier="BRONZE"    grade="C"  decision="REVAMP"/>
  <band range="40-54"  tier="FAILING"   grade="D"  decision="REDIRECT_CANDIDATE"/>
  <band range="0-39"   tier="CRITICAL"  grade="F"  decision="REMOVE"/>
</result_bands>
<n8n_output_format>
  <critical_rules>
    OUTPUT EXACTLY TWO BLOCKS:
    BLOCK 1: One header row with all column names, pipe-delimited.
    BLOCK 2: One data row per URL, pipe-delimited.
    NO prose. NO commentary. NO additional tables. NO sheet labels.
    NO markdown. NO asterisks. NO bold. NO backticks.
    Every cell must be populated. Use DATA_UNAVAILABLE if genuinely missing.
    Full URLs always.
    Pipe delimiter only.
    Scores: 0.0-10.0 (one decimal). Category scores: 0.00-10.00. Composite: 0.0-100.0.
  </critical_rules>
  <column_map>
    URL_ID|Blog_URL|URL_Slug|Focus_Keyword|Post_Tier|Funnel_Stage|Content_Silo|ICP_Fit|Funnel_Conversion_Role|Reader_Awareness_Stage|One_Line_Summary|Core_Theme|Reader_Promise|Word_Count|Flesch_Score|Avg_Words_Per_Sentence|Unique_Inlinks|Spelling_Errors|Grammar_Errors|GSC_Clicks|GSC_Impressions|GSC_CTR|GSC_Position|Last_Modified|Meta_Title_Text|Meta_Title_Chars|Meta_Desc_Text|Meta_Desc_Chars|H1_Text|H1_Chars|A1_Score|A1_Flag|A1_Evidence|A1_Fix|A2_Score|A2_Flag|A2_Evidence|A2_Fix|A3_Score|A3_Flag|A3_Flagged_Claims|A3_Fix|A4_Score|A4_Flag|A4_Stale_Claims|A4_Fix|A5_Score|A5_Flag|A5_Ideal_WC|A5_Fluff_Ratio|A5_Fix|A6_Score|A6_Flag|A6_Violations|A6_Fix|A7_Score|A7_Flag|A7_Fix|A8_Score|A8_Flag|A8_Banned_Words_Found|A8_Fix|A9_Score|A9_Flag|A9_External_Domains|A9_Fix|A10_Score|A10_Flag|A10_Missing_Subtopics|A10_Fix|A11_Score|A11_Flag|A11_Duplication_Note|A11_Fix|Cat_A_Score|Cat_A_Pass_Fail|B1_Score|B1_Flag|B1_Evidence|B1_Fix|B2_Score|B2_Flag|B2_H1_Match_Type|B2_Fix|B3_Score|B3_Flag|B3_KW_Position_Words|B3_First_Sentence|B3_Fix|B4_Score|B4_Flag|B4_KH_Count|B4_All_H2_Headings|B4_Fix|B5_Score|B5_Flag|B5_KW_In_Title|B5_Power_Word|B5_Fix|B6_Score|B6_Flag|B6_CTA_Verb_Found|B6_KW_In_Desc|B6_Fix|B7_Score|B7_Flag|B7_Slug|B7_Slug_Issues|B7_Fix|B8_Score|B8_Flag|B8_Cannibal_URLs|B8_Fix|Cat_B_Score|Cat_B_Pass_Fail|C1_Score|C1_Flag|C1_CTA_Text_Found|C1_CTA_Position|C1_Stage_Match|C1_CTA_Naturalness_Raw|C1_Fix|C2_Score|C2_Flag|C2_Product_Mentions|C2_First_Mention_Position|C2_Problem_Match|C2_Pitch_Quality|C2_Fix|C3_Score|C3_Flag|C3_Format_Match|C3_Fix|C4_Score|C4_Flag|C4_Problem_Frames|C4_Urgency_Signals|C4_Trial_Relevance|C4_Fix|C5_Score|C5_Flag|C5_Conversion_Role_Fit|C5_Organic_Path|C5_Fix|Cat_C_Score|Cat_C_Pass_Fail|Recommended_CTA_Text|Recommended_CTA_Placement|Funnel_Gap|Trial_Potential|D1_Score|D1_Flag|D1_Best_Sentence|D1_Worst_Sentence|D1_Fix|D2_Score|D2_Flag|D2_Specificity_Rate|D2_Worst_Vague_Para|D2_Fix|D3_Score|D3_Flag|D3_Author_Bio|D3_Date_Visible|D3_Case_Study_Ref|D3_Fix|D4_Score|D4_Flag|D4_Domain_List|D4_Fix|Cat_D_Score|Cat_D_Pass_Fail|E1_Score|E1_Flag|E1_Total_Internal|E1_Product_Page_Links|E1_All_Internal_Links|E1_BOF_Handoff_Quality|E1_Fix|E2_Score|E2_Flag|E2_Orphan_Flag|E2_Fix|E3_Score|E3_Flag|E3_Descriptive_Rate|E3_Generic_Anchors_List|E3_Fix|Cat_E_Score|Cat_E_Pass_Fail|Orphan_Status|Suggested_Internal_Links|F1_Score|F1_Flag|F1_Schema_Types_Present|F1_Orphan_FAQ|F1_Fix|F2_Score|F2_Flag|F2_Total_Images|F2_Alt_Coverage_Rate|F2_Missing_Alt_Imgs|F2_Fix|F3_Score|F3_Flag|F3_Canonical_URL|F3_Canonical_Correct|F3_Fix|Cat_F_Score|Cat_F_Pass_Fail|G1_Score|G1_Flag|G1_ICP_Signals_Found|G1_Off_ICP_Reason|G1_Fix|G2_Score|G2_Flag|G2_AH_Mentions|G2_Differentiator_Pitch|G2_Fix|G3_Score|G3_Flag|G3_Competitor_Mentions|G3_Unique_Angle|G3_Fix|Cat_G_Score|Cat_G_Pass_Fail|NEW1_Score|NEW1_Flag|NEW1_Proof_Signals_Found|NEW1_Proprietary_Knowledge|NEW1_Fix|NEW2_Score|NEW2_Flag|NEW2_Setup_Present|NEW2_Fix|NEW3_Score|NEW3_Flag|NEW3_Replaceability_Label|NEW3_Unique_Signals_Found|NEW3_Fix|NEW4_Score|NEW4_Flag|NEW4_SFQ_Answered|NEW4_SFQ_Missing|NEW4_Fix|Cat_H_Score|Cat_H_Pass_Fail|Product_Proof_Gap|Composite_100|Grade|Rank_Tier|Strategic_Decision|Decision_Reason|Urgency|Flags_Count|Params_Failed|Priority_Action|SERP_Replaceability_Label|Portfolio_Uniqueness|Can_It_Drive_Trial|Why_Or_Why_Not|Removal_Recommendation|Removal_Reason|SEO_Quick_Win|Technical_Quick_Win|Top_Fix_Action_1|Top_Fix_Action_2|Top_Fix_Action_3|AC_Primary_Keyword|AD_Est_Volume|AE_Blog_Intent|AF_Slug_Content_Match|AG_Grammar_Issues|AH_Spelling_Issues|AI_Factual_Accuracy|AJ_Answer_Quality_1to5|AK_Relevance_1to5|AL_Intent_Alignment_1to5|AM_Auditor_Notes|LSI_Keywords_Found|LSI_Keywords_Missing|Entity_Coverage|Schema_Types_Present|FAQ_Schema|Featured_Snippet_Eligible|Cannibalization_Risk|Keyword_Focus_Quality|Topic_Drift_Present|Heading_Keyword_Density|All_H3_Headings|External_Links_Count|External_Domains_List|Competitor_Links_Found|Shared_Focus_Keyword_With|Shared_Core_Theme_With|Overlap_Type|Merge_Recommended_Action|Merge_Destination|Content_To_Preserve
  </column_map>
  <cell_rules>
    SCORES: numeric 0.0-10.0 (one decimal).
    CATEGORY SCORES: numeric 0.00-10.00 (two decimals).
    COMPOSITE: numeric 0.0-100.0 (one decimal).
    PASS_FAIL cells: PASS or FAIL only.
    FLAG cells: TRIGGERED or CLEAR only.
    ORPHAN_STATUS: ORPHANED | WEAK | OK | STRONG
    GRADE: A+ | A | B | C | D | F
    RANK_TIER: PLATINUM | GOLD | SILVER | BRONZE | FAILING | CRITICAL
    STRATEGIC_DECISION: AMPLIFY | OPTIMIZE | REVAMP | REDIRECT_CANDIDATE | REMOVE | MONITOR
    TRIAL_POTENTIAL: HIGH | MEDIUM | LOW
    SERP_REPLACEABILITY_LABEL: LOW REPLACEABILITY | MODERATE | HIGH REPLACEABILITY
    REMOVAL_RECOMMENDATION: YES | NO | CONDITIONAL
    FEATURED_SNIPPET_ELIGIBLE: Yes | Partial | No
    CANNIBALIZATION_RISK: NONE | POSSIBLE [URL_ID] | CONFIRMED [URL_ID]
    TOPIC_DRIFT_PRESENT: Y | N
    Never use pipe character inside cell content — replace with semicolons.
    Never leave a cell empty.
    If genuinely unavailable: DATA_UNAVAILABLE
  </cell_rules>
  <escalation_suffix>
    After data rows, emit escalation rows:
    MERGE_CANDIDATES | detail
    COMMODITY_CONTENT | detail
    TRIAL_DEAD_ZONES | detail
    ICP_VIOLATIONS | detail
    SYSTEMIC_FLAGS | detail
    CRITICAL_REMOVALS | detail
    TOP_QUICK_WINS | detail
    AUDIT_COMPLETE | summary
  </escalation_suffix>
</n8n_output_format>
<integrity_check>
  Before emitting output, verify:
  CHECK_1:  Have I used all pre-fetched content fully?
  CHECK_2:  Is every score derived from formula + page evidence?
  CHECK_3:  Is output exactly ONE header row + ONE data row per URL + escalation rows?
  CHECK_4:  Does any cell contain a pipe character? Replace with semicolons.
  CHECK_5:  Is every cell populated?
</integrity_check>"""


# ── Helper: XML-safe escape ────────────────────────────────────────────────────

def xml_escape(text: str) -> str:
    """Escape special characters for XML embedding."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


# ── Page Fetcher ───────────────────────────────────────────────────────────────

def fetch_page(url: str) -> dict:
    """
    Fetch and parse a blog URL.
    Returns a dict with all cached items required by Phase 2.
    On error returns {'url': url, 'error': str, 'status_code': 0}.
    """
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=FETCH_TIMEOUT)
        status_code = resp.status_code

        if status_code != 200:
            return {"url": url, "error": f"HTTP {status_code}", "status_code": status_code}

        soup = BeautifulSoup(resp.text, "html.parser")

        # ── Strip chrome elements ──────────────────────────────────────────────
        for tag in soup.find_all(["nav", "header", "footer", "aside"]):
            tag.decompose()
        for tag in soup.find_all(True, class_=lambda c: c and any(
            kw in " ".join(c).lower()
            for kw in ["cookie", "banner", "sidebar", "nav-", "navigation",
                       "footer", "header", "popup", "modal", "widget"]
        )):
            tag.decompose()

        # ── Main content area ──────────────────────────────────────────────────
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(class_=re.compile(r"entry[-_]content|post[-_]content|article[-_]body", re.I)) or
            soup.find("body") or
            soup
        )

        # ── Headings ───────────────────────────────────────────────────────────
        headings = [
            {"tag": h.name, "text": h.get_text(strip=True)}
            for h in main.find_all(["h1", "h2", "h3", "h4"])
        ]

        # ── Body text ──────────────────────────────────────────────────────────
        body_text = main.get_text(separator=" ", strip=True)
        body_words = body_text.split()
        estimated_word_count = len(body_words)

        # ── Links ──────────────────────────────────────────────────────────────
        internal_links, external_links = [], []
        for a in main.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if not href or href.startswith("#"):
                continue
            if "customgpt.ai" in href or (href.startswith("/") and not href.startswith("//")):
                internal_links.append({"href": href, "text": text})
            elif href.startswith("http"):
                external_links.append({"href": href, "text": text})

        # ── Images ────────────────────────────────────────────────────────────
        images = [
            {"src": img.get("src", ""), "alt": img.get("alt", "")}
            for img in main.find_all("img")
        ]

        # ── Meta info ─────────────────────────────────────────────────────────
        meta_title_tag = soup.find("title")
        meta_title = meta_title_tag.get_text(strip=True) if meta_title_tag else ""

        meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or \
                        soup.find("meta", attrs={"property": "og:description"})
        meta_desc = meta_desc_tag.get("content", "") if meta_desc_tag else ""

        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        canonical_url = canonical_tag.get("href", "") if canonical_tag else ""

        robots_tag = soup.find("meta", attrs={"name": "robots"})
        robots_content = robots_tag.get("content", "") if robots_tag else ""

        # ── JSON-LD ────────────────────────────────────────────────────────────
        json_ld_blocks = [
            s.string or s.get_text()
            for s in soup.find_all("script", type="application/ld+json")
        ]

        # ── CTAs ──────────────────────────────────────────────────────────────
        cta_texts = []
        for el in main.find_all(["a", "button"], class_=re.compile(
            r"cta|btn|button|signup|trial|register|free|demo|start", re.I
        )):
            t = el.get_text(strip=True)
            if t:
                cta_texts.append(t)
        # Also look for any link with trial/demo/signup in text
        for a in main.find_all("a", href=True):
            t = a.get_text(strip=True).lower()
            if any(kw in t for kw in ["free trial", "get started", "try free", "demo", "sign up", "register"]):
                cta_texts.append(a.get_text(strip=True))

        # ── Dates ─────────────────────────────────────────────────────────────
        date_el = (
            soup.find("time") or
            soup.find(class_=re.compile(r"date|published|updated|modified", re.I)) or
            soup.find(attrs={"datetime": True})
        )
        pub_date = ""
        if date_el:
            pub_date = date_el.get("datetime") or date_el.get_text(strip=True)

        # ── CustomGPT mention count ────────────────────────────────────────────
        customgpt_mentions = body_text.lower().count("customgpt")

        return {
            "url": url,
            "status_code": status_code,
            "estimated_word_count": estimated_word_count,
            "body_text": body_text[:MAX_BODY_CHARS],
            "first_100_words": " ".join(body_words[:100]),
            "first_200_words": " ".join(body_words[:200]),
            "headings": headings,
            "images": images[:30],
            "internal_links": internal_links[:30],
            "external_links": external_links[:30],
            "meta_title": meta_title,
            "meta_desc": meta_desc,
            "canonical_url": canonical_url,
            "robots": robots_content,
            "json_ld": json_ld_blocks,
            "cta_texts": list(dict.fromkeys(cta_texts))[:10],  # deduplicated
            "pub_date": pub_date or "DATA_UNAVAILABLE",
            "customgpt_mentions": customgpt_mentions,
        }

    except requests.exceptions.Timeout:
        return {"url": url, "error": "TIMEOUT", "status_code": 0}
    except requests.exceptions.ConnectionError as e:
        return {"url": url, "error": f"CONNECTION_ERROR: {e}", "status_code": 0}
    except Exception as e:
        return {"url": url, "error": str(e), "status_code": 0}


# ── Prompt Builder ─────────────────────────────────────────────────────────────

def build_user_message(batch: list, page_data: dict) -> str:
    """Build the user message with target_batch + pre-fetched content."""

    # Target batch XML
    parts = ["<target_batch>"]
    for url_id, url in batch:
        parts.append(f'  <url id="{url_id}">{xml_escape(url)}</url>')
    parts.append("</target_batch>")
    parts.append("")
    parts.append(
        "IMPORTANT: The following pre-fetched content was retrieved by an external crawler. "
        "Use this content to satisfy Phase 2 (CRAWL_AND_CACHE). Do NOT attempt live crawls."
    )
    parts.append("")
    parts.append("<prefetched_content>")

    for url_id, url in batch:
        data = page_data.get(url, {})
        error = data.get("error")
        sc = data.get("status_code", 0)

        if error or sc != 200:
            parts.append(f'  <page id="{url_id}" url="{xml_escape(url)}" status_code="{sc}" error="{xml_escape(str(error))}" />')
            continue

        parts.append(f'  <page id="{url_id}" url="{xml_escape(url)}" status_code="{sc}">')
        parts.append(f'    <meta_title chars="{len(data.get("meta_title",""))}">{xml_escape(data.get("meta_title",""))}</meta_title>')
        parts.append(f'    <meta_desc chars="{len(data.get("meta_desc",""))}">{xml_escape(data.get("meta_desc",""))}</meta_desc>')
        parts.append(f'    <canonical>{xml_escape(data.get("canonical_url",""))}</canonical>')
        parts.append(f'    <robots>{xml_escape(data.get("robots",""))}</robots>')
        parts.append(f'    <pub_date>{xml_escape(data.get("pub_date","DATA_UNAVAILABLE"))}</pub_date>')
        parts.append(f'    <estimated_word_count>{data.get("estimated_word_count",0)}</estimated_word_count>')
        parts.append(f'    <customgpt_mentions>{data.get("customgpt_mentions",0)}</customgpt_mentions>')

        # Headings
        parts.append("    <headings>")
        for h in data.get("headings", []):
            tag = h["tag"]
            parts.append(f'      <{tag}>{xml_escape(h["text"])}</{tag}>')
        parts.append("    </headings>")

        # Body text (first 200 words clean, then full truncated body)
        parts.append(f'    <first_100_words>{xml_escape(data.get("first_100_words",""))}</first_100_words>')
        parts.append(f'    <first_200_words>{xml_escape(data.get("first_200_words",""))}</first_200_words>')
        parts.append(f'    <body_text>{xml_escape(data.get("body_text",""))}</body_text>')

        # Internal links
        ilinks = data.get("internal_links", [])
        parts.append(f'    <internal_links count="{len(ilinks)}">')
        for lk in ilinks[:20]:
            parts.append(f'      <link href="{xml_escape(lk["href"])}">{xml_escape(lk["text"])}</link>')
        parts.append("    </internal_links>")

        # External links
        elinks = data.get("external_links", [])
        parts.append(f'    <external_links count="{len(elinks)}">')
        for lk in elinks[:20]:
            parts.append(f'      <link href="{xml_escape(lk["href"])}">{xml_escape(lk["text"])}</link>')
        parts.append("    </external_links>")

        # Images
        imgs = data.get("images", [])
        parts.append(f'    <images count="{len(imgs)}">')
        for img in imgs[:20]:
            parts.append(f'      <img src="{xml_escape(img["src"])}" alt="{xml_escape(img["alt"])}" />')
        parts.append("    </images>")

        # CTAs
        parts.append("    <cta_elements>")
        for cta in data.get("cta_texts", []):
            parts.append(f'      <cta>{xml_escape(cta)}</cta>')
        parts.append("    </cta_elements>")

        # JSON-LD
        parts.append("    <json_ld_blocks>")
        for block in data.get("json_ld", []):
            if block:
                parts.append(f'      <block>{xml_escape(block[:2000])}</block>')
        parts.append("    </json_ld_blocks>")

        # SF/GSC data note
        parts.append("    <sf_gsc_data>DATA_UNAVAILABLE — not pre-loaded in this run.</sf_gsc_data>")

        parts.append("  </page>")

    parts.append("</prefetched_content>")
    parts.append("")
    parts.append(
        "Now execute the full audit for this batch. "
        "Output BLOCK 1 (header row) and BLOCK 2 (one data row per URL), "
        "both pipe-delimited, followed by the escalation suffix. "
        "No prose. No markdown. Machine-readable output only."
    )

    return "\n".join(parts)


# ── Claude API Call ────────────────────────────────────────────────────────────

def call_claude(client: anthropic.Anthropic, user_message: str) -> str:
    """Call the Claude API and return the raw text response."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": AUDIT_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # prompt caching
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    )


# ── Output Parser ──────────────────────────────────────────────────────────────

ESCALATION_KEYWORDS = {
    "MERGE_CANDIDATES", "COMMODITY_CONTENT", "TRIAL_DEAD_ZONES",
    "ICP_VIOLATIONS", "SYSTEMIC_FLAGS", "CRITICAL_REMOVALS",
    "TOP_QUICK_WINS", "AUDIT_COMPLETE",
}


def parse_claude_output(text: str):
    """
    Parse Claude's pipe-delimited output.
    Returns (header_row: list|None, data_rows: list[list], escalation_rows: list[list]).
    """
    header_row = None
    data_rows = []
    escalation_rows = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip comment/label lines
        if line.startswith("BLOCK") or line.startswith("#") or line.startswith("//"):
            continue

        parts = line.split("|")
        if len(parts) < 5:
            continue

        first = parts[0].strip()

        # Escalation row
        if first in ESCALATION_KEYWORDS:
            escalation_rows.append(parts)
            continue

        # Header row
        if first == "URL_ID":
            if header_row is None:
                header_row = [p.strip() for p in parts]
            continue

        # Data row: first cell should be a number (URL_ID)
        if re.match(r"^\d+$", first):
            data_rows.append(parts)
            continue

    return header_row, data_rows, escalation_rows


# ── Progress Tracking ──────────────────────────────────────────────────────────

def load_progress() -> set:
    """Load set of already-processed URL indices (0-based)."""
    if not os.path.exists(PROGRESS_FILE):
        return set()
    try:
        with open(PROGRESS_FILE, "r") as f:
            data = json.load(f)
        return set(data.get("processed_indices", []))
    except Exception:
        return set()


def save_progress(processed: set) -> None:
    """Save progress to JSON file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"processed_indices": sorted(processed)}, f)


# ── CSV Writer ─────────────────────────────────────────────────────────────────

def write_rows_to_csv(rows: list, header: list | None = None) -> None:
    """
    Append data rows to OUTPUT_CSV.
    If header is provided and the file doesn't exist yet, write the header first.
    """
    file_exists = os.path.exists(OUTPUT_CSV)
    mode = "a" if file_exists else "w"

    with open(OUTPUT_CSV, mode, newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
        if not file_exists and header:
            writer.writerow(header)
        for row in rows:
            writer.writerow(row)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    total = len(URLS)
    if total == 0:
        print("No URLs to process. Add URLs to the URLS list in the script.")
        sys.exit(0)

    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Run:  export ANTHROPIC_API_KEY='sk-ant-...'  then re-run the script.")
        sys.exit(1)

    print(f"Starting audit of {total} URLs in batches of {BATCH_SIZE}.")
    print(f"Output: {OUTPUT_CSV}")
    print(f"Progress file: {PROGRESS_FILE}")
    print()

    client = anthropic.Anthropic(api_key=API_KEY)
    processed = load_progress()
    csv_header_written = os.path.exists(OUTPUT_CSV)

    # Build list of pending batches
    all_indices = list(range(total))
    pending_indices = [i for i in all_indices if i not in processed]

    if not pending_indices:
        print("All URLs already processed. Delete audit_progress.json to re-run.")
        sys.exit(0)

    print(f"Resuming from index {min(pending_indices)} "
          f"({len(processed)} already done, {len(pending_indices)} remaining).")
    print()

    # Split pending into batches
    batches = [
        pending_indices[i : i + BATCH_SIZE]
        for i in range(0, len(pending_indices), BATCH_SIZE)
    ]

    for batch_num, batch_indices in enumerate(batches, start=1):
        batch_urls = [(i + 1, URLS[i]) for i in batch_indices]  # (url_id, url)
        url_ids = [uid for uid, _ in batch_urls]
        urls_only = [u for _, u in batch_urls]

        print(f"Batch {batch_num}/{len(batches)} — URL IDs: {url_ids}")

        # ── Step 1: Fetch pages ──────────────────────────────────────────────
        page_data = {}
        for uid, url in batch_urls:
            print(f"  Fetching {url} ...", end=" ", flush=True)
            data = fetch_page(url)
            page_data[url] = data
            if data.get("error"):
                print(f"ERROR: {data['error']}")
            else:
                wc = data.get("estimated_word_count", 0)
                print(f"OK ({wc} words)")

        # ── Step 2: Build prompt & call Claude ──────────────────────────────
        print(f"  Sending batch to Claude ({MODEL}) ...", flush=True)
        user_message = build_user_message(batch_urls, page_data)

        retries = 0
        raw_output = None
        while retries < 3:
            try:
                raw_output = call_claude(client, user_message)
                break
            except anthropic.RateLimitError as e:
                wait = 60
                print(f"  Rate limited. Waiting {wait}s ... (attempt {retries+1}/3)")
                time.sleep(wait)
                retries += 1
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    wait = 30 * (2 ** retries)
                    print(f"  Server error {e.status_code}. Waiting {wait}s ...")
                    time.sleep(wait)
                    retries += 1
                else:
                    print(f"  API error {e.status_code}: {e.message}")
                    break
            except Exception as e:
                print(f"  Unexpected error: {e}")
                break

        if raw_output is None:
            print(f"  FAILED to get Claude response for batch {batch_num}. Skipping.")
            continue

        # ── Step 3: Parse output ─────────────────────────────────────────────
        header, data_rows, escalation_rows = parse_claude_output(raw_output)

        if not data_rows:
            print(f"  WARNING: No data rows parsed from Claude output.")
            print(f"  Raw output (first 500 chars): {raw_output[:500]}")
            # Save raw output for debugging
            debug_file = f"debug_batch_{batch_num}.txt"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(raw_output)
            print(f"  Full output saved to {debug_file}")
        else:
            print(f"  Parsed {len(data_rows)} data row(s).")

        # ── Step 4: Write to CSV ─────────────────────────────────────────────
        if data_rows:
            header_to_write = header if not csv_header_written else None
            write_rows_to_csv(data_rows, header=header_to_write)
            if not csv_header_written and header:
                csv_header_written = True

        # ── Step 5: Append escalation rows to a separate file ───────────────
        if escalation_rows:
            with open("audit_escalations.csv", "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in escalation_rows:
                    writer.writerow(row)

        # ── Step 6: Save progress ────────────────────────────────────────────
        processed.update(batch_indices)
        save_progress(processed)

        done_total = len(processed)
        print(f"  Done {done_total}/{total}")
        print()

        # ── Step 7: Rate-limit delay ─────────────────────────────────────────
        if batch_num < len(batches):
            time.sleep(INTER_BATCH_DELAY)

    print("=" * 60)
    print(f"Audit complete. {len(processed)}/{total} URLs processed.")
    print(f"Results: {OUTPUT_CSV}")
    if os.path.exists("audit_escalations.csv"):
        print(f"Escalations: audit_escalations.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()
