"""
Smart query understanding layer.

Pre-processes messy, mixed-language, or vague user input BEFORE it enters
the existing analyze_multimodal_query() pipeline.

Public API:
    await smart_rewrite_query(text, language) -> {"queries": List[str], "joined": str}

Integration (routes.py — before ChatService call):

    from app.chat.smart_query import smart_rewrite_query

    result = await smart_rewrite_query(payload.message, payload.language)
    enriched_message = result["joined"]

    return await ChatService.recommend_products(
        message=enriched_message,
        user_id=current_user.id,
        language=payload.language,
    )

The existing pipeline (analyze_multimodal_query → search → group) is unchanged.
smart_rewrite_query only cleans the raw string before it arrives there.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List

from app.chat.mistral_decision import (
    _ABBREVIATIONS,
    _get_mistral_client,
    _split_query_text,
    _strip_accents,
    normalize_fr_to_en,
)
from app.config import settings

logger = logging.getLogger(__name__)

# LRU cache: avoids calling Mistral twice for the same input
_REWRITE_CACHE: Dict[str, Dict[str, Any]] = {}
_REWRITE_CACHE_MAX = 512

# ---------------------------------------------------------------------------
# Filler-phrase patterns to strip after rewrite (both languages)
# ---------------------------------------------------------------------------
_FILLER_EN = re.compile(
    r"^\s*(?:"
    r"i\s+(?:also\s+)?(?:want|need|would\s+like|'d\s+like)\s+(?:to\s+(?:buy|get)\s+)?|"
    r"(?:can\s+you\s+)?(?:please\s+)?(?:give|show|find|get)\s+me\s+|"
    r"i(?:'m|\s+am)\s+looking\s+for\s+|"
    r"looking\s+for\s+"
    r")",
    re.IGNORECASE,
)
_FILLER_FR = re.compile(
    r"^\s*(?:"
    r"je\s+(?:veux|voudrais|cherche|recherche|desire|souhaite|aimerais)\s+(?:aussi\s+)?(?:un[e]?\s+|l[ae]\s+|les\s+|du\s+|de\s+la\s+|de\s+l.?\s+)?|"
    r"j.?aimerais\s+(?:aussi\s+)?(?:un[e]?\s+)?|"
    r"j.?ai\s+besoin\s+d.?\s*(?:un[e]?\s+)?|"
    r"il\s+me\s+faut\s+(?:un[e]?\s+)?|"
    r"(?:donnez|montrez|trouvez|cherchez)[- ]moi\s+(?:aussi\s+)?(?:un[e]?\s+)?|"
    r"(?:donne|montre|trouve|cherche)[- ]moi\s+(?:aussi\s+)?(?:un[e]?\s+)?"
    r")",
    re.IGNORECASE,
)
# Bare leading articles left after filler strip
_LEADING_ARTICLE = re.compile(
    r"^(?:un[e]?|le|la|les|des|du|de\s+la|de\s+l.?|a|an|the)\s+",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Step 1 — raw normalisation
# ---------------------------------------------------------------------------

def _normalize_raw_input(text: str) -> str:
    """Lowercase, collapse whitespace, unify separators."""
    text = text.strip()
    # Normalize Unicode apostrophes/quotes
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    # Collapse runs of whitespace
    text = re.sub(r"\s+", " ", text)
    # Slash → comma (so "phone/laptop" splits like "phone, laptop")
    text = re.sub(r"\s*/\s*", ", ", text)
    # Spaced dash → comma  (avoids consuming brand hyphens like "HP-15")
    text = re.sub(r"(?<=\w)\s+-\s+(?=\w)", ", ", text)
    # Ensure comma is always followed by a space
    text = re.sub(r",(?!\s)", ", ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Step 2 — abbreviation expansion
# ---------------------------------------------------------------------------

def _expand_abbreviations(text: str) -> str:
    """Expand known abbreviations token-by-token using the shared dict."""
    tokens = text.split()
    expanded = [
        _ABBREVIATIONS.get(_strip_accents(tok.lower()), tok)
        for tok in tokens
    ]
    return " ".join(expanded)


# ---------------------------------------------------------------------------
# Step 3 — Mistral intent extraction rewrite
# ---------------------------------------------------------------------------

_MISTRAL_REWRITE_PROMPT = """\
You are an intent extraction engine for a shopping assistant.

Your task is to extract all product requests from the user input.

Rules:
- Identify every product mentioned
- Each product must be separate
- Do not merge different products
- Do not drop any product
- Remove unnecessary words
- Keep descriptions short and useful for search
- Use commas to separate different products
- Output must be in the same language as the user input (English or French)
- Do NOT explain anything

Input language: {language}
Input: {input}

Return ONLY the cleaned query string."""


async def _mistral_rewrite(text: str, language: str) -> str:
    """
    Ask Mistral to extract all product intents and return them comma-separated.

    Failsafe: if Mistral returns empty or collapses multiple intents that were
    present in the original text into a single one, the original text is
    returned so the downstream deterministic splitter can recover them.
    """
    lang_label = "French" if language == "fr" else "English"
    prompt = _MISTRAL_REWRITE_PROMPT.format(language=lang_label, input=text)
    client = _get_mistral_client()
    try:
        response = await asyncio.wait_for(
            client.chat.complete_async(
                model=settings.MISTRAL_TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=100,
            ),
            timeout=3.0,
        )
        result = response.choices[0].message.content.strip().strip("\"'")

        # ── Failsafe 1: Mistral returned empty ───────────────────────────────
        if not result:
            logger.debug("smart_rewrite_query: Mistral returned empty — using original")
            return text

        # ── Failsafe 2: Mistral collapsed multiple intents into one ──────────
        # Compare how many segments the original vs. Mistral output would produce.
        # If the original splits into more parts, Mistral dropped something — revert.
        original_split_count = len(_split_query_text(text, language))
        rewritten_split_count = len(_split_query_text(result, language))
        if original_split_count > 1 and rewritten_split_count < original_split_count:
            logger.debug(
                "smart_rewrite_query: Mistral collapsed %d intents → %d — using original",
                original_split_count,
                rewritten_split_count,
            )
            return text

        # ── Hallucination guard: reject wildly different lengths ──────────────
        if not (0.2 <= len(result) / max(len(text), 1) <= 6.0):
            return text

        return result

    except Exception as exc:
        logger.debug("smart_rewrite_query: Mistral rewrite skipped (%s)", exc)
        return text


# ---------------------------------------------------------------------------
# Step 4 — filler strip
# ---------------------------------------------------------------------------

def _strip_filler(text: str) -> str:
    """Remove intent preambles from the full rewritten string."""
    text = _FILLER_EN.sub("", text).strip()
    text = _FILLER_FR.sub("", text).strip()
    text = _LEADING_ARTICLE.sub("", text).strip()
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def smart_rewrite_query(text: str, language: str) -> Dict[str, Any]:
    """
    Intelligent pre-processing layer for user queries.

    Converts messy, mixed-language, or vague input into a clean list of
    product search queries.  Must be called BEFORE analyze_multimodal_query().

    Pipeline (in order):
        1. Normalize raw input   — lowercase, separators
        2. Expand abbreviations  — lptp→laptop, ordi→ordinateur, tel→telephone
        3. Mistral rewrite       — fix structure, remove filler (NOT splitting)
        4. Strip filler phrases  — regex safety net
        5. Deterministic split   — comma / "and" / "et" (existing logic)
        6. FR→EN normalization   — per segment (existing logic)
        7. Filter empty results

    Args:
        text:     Raw user message.
        language: "en" or "fr" (hint — actual language auto-detected).

    Returns:
        {
            "queries": List[str],   # individual clean product queries
            "joined":  str,         # comma-joined string ready for the pipeline
        }

    Examples:
        "phone,lptp, charger,headphones"  → {"queries": ["phone","laptop","charger","headphones"], "joined": "phone, laptop, charger, headphones"}
        "je veux un tel et un ordi"       → {"queries": ["phone","laptop"],                        "joined": "phone, laptop"}
        "ventilateur and laptop"          → {"queries": ["fan","laptop"],                          "joined": "fan, laptop"}
        "fan black quiet for bedroom"     → {"queries": ["quiet black fan for bedroom"],           "joined": "quiet black fan for bedroom"}
    """
    text = (text or "").strip()
    if not text:
        return {"queries": [], "joined": ""}

    # Cache hit
    cache_key = f"{language}:{text}"
    if cache_key in _REWRITE_CACHE:
        return _REWRITE_CACHE[cache_key]

    # ── Step 1: normalize raw input ──────────────────────────────────────────
    normalized = _normalize_raw_input(text)
    if not normalized:
        return {"queries": [text], "joined": text}

    # ── Step 2: expand abbreviations ─────────────────────────────────────────
    expanded = _expand_abbreviations(normalized)

    # ── Step 3: Mistral intent extraction ────────────────────────────────────
    # Mistral identifies every product intent, removes filler, and returns them
    # comma-separated in the user's language. Step 5 does the actual splitting.
    # Failsafe inside _mistral_rewrite reverts to `expanded` if Mistral drops intents.
    rewritten = await _mistral_rewrite(expanded, language)

    # ── Step 4: filler strip (regex safety net post-rewrite) ─────────────────
    cleaned = _strip_filler(rewritten)
    if not cleaned:
        cleaned = rewritten  # fallback — never return empty

    # ── Steps 5+6: deterministic split + FR→EN (reuses existing pipeline) ────
    splits = _split_query_text(cleaned, language)
    queries = [normalize_fr_to_en(q.strip()) for q in splits if q.strip()]

    # ── Step 7: filter empty results and remove duplicates (order preserved) ───
    seen: set = set()
    deduped: List[str] = []
    for q in queries:
        if len(q) < 2:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
    queries = deduped

    if not queries:
        queries = [normalize_fr_to_en(cleaned)]

    result: Dict[str, Any] = {
        "queries": queries,
        "joined": ", ".join(queries),
    }

    # Store in cache (LRU eviction)
    if len(_REWRITE_CACHE) >= _REWRITE_CACHE_MAX:
        _REWRITE_CACHE.pop(next(iter(_REWRITE_CACHE)))
    _REWRITE_CACHE[cache_key] = result

    return result
