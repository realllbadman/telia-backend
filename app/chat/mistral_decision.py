"""
Smart conversational decision layer  +  multimodal intent resolver.

Two public functions:

  analyze_multimodal_query(...)
      → {"use_media": bool, "queries": ["q1", "q2"]}
      Detects explicit "ignore the image" phrases and multi-product splits.

  resolve_multimodal_intent(...)
      → "final search query string"
      Called when BOTH user text AND media are present.
      Applies strict priority rules: user text ALWAYS wins over image/video
      when they conflict.  Result is cached (hash-keyed, 256 entries).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from difflib import get_close_matches as _get_close_matches
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Singleton Mistral client (reuses the same SSL connection pool)
_MISTRAL_CLIENT = None


def _get_mistral_client():
    global _MISTRAL_CLIENT
    if _MISTRAL_CLIENT is None:
        from mistralai import Mistral
        from app.config import settings
        _MISTRAL_CLIENT = Mistral(api_key=settings.MISTRAL_API_KEY)
    return _MISTRAL_CLIENT


# ---------------------------------------------------------------------------
# French → English product term normalization
# Ordered longest-match first so "ordinateur portable" wins over "ordinateur".
# Only covers terms that bilingual expansion (_expand_keywords_bilingual) misses
# or where the short form is ambiguous (e.g. "téléphone" vs "téléphone portable").
# ---------------------------------------------------------------------------
_FR_TO_EN: List[tuple[str, str]] = [
    # Multi-word forms first (longest match wins)
    ("ordinateur portable", "laptop"),
    ("téléphone portable",  "smartphone"),
    ("téléphone mobile",    "smartphone"),
    ("casque audio",        "headphones"),
    ("montre connectée",    "smartwatch"),
    ("appareil photo",      "camera"),
    ("four micro-ondes",    "microwave"),
    ("machine à laver",     "washing machine"),
    ("fer à repasser",      "iron"),
    # Single-word forms
    ("ventilateur",         "fan"),
    ("tablette",            "tablet"),
    ("télévision",          "television"),
    ("téléviseur",          "television"),
    ("ordinateur",          "laptop"),    # "ordinateur" alone = laptop at Telia
    ("téléphone",           "smartphone"),
    ("casque",              "headphones"),
    ("écouteurs",           "earbuds"),
    ("enceinte",            "speaker"),
    ("chargeur",            "charger"),
    ("imprimante",          "printer"),
    ("clavier",             "keyboard"),
    ("souris",              "mouse"),
    ("réfrigérateur",       "refrigerator"),
    ("aspirateur",          "vacuum cleaner"),
    ("télé",                "television"),
    ("micro-ondes",         "microwave"),
    # Additional common terms
    ("écran",               "monitor"),
    ("moniteur",            "monitor"),
    ("batterie",            "battery"),
    ("disque dur",          "hard drive"),
    ("disque ssd",          "ssd"),
    ("webcam",              "webcam"),
    ("haut-parleur",        "speaker"),
    ("manette",             "gamepad"),
    ("routeur",             "router"),
    ("modem",               "modem"),
    ("câble",               "cable"),
    ("adaptateur",          "adapter"),
    ("hub usb",             "usb hub"),
]

# Accent-stripped versions for case/accent-insensitive matching
import unicodedata as _ud
def _strip_accents(s: str) -> str:
    return "".join(c for c in _ud.normalize("NFKD", s) if not _ud.combining(c))

_FR_TO_EN_NORMALIZED: List[tuple[str, str, str]] = [
    (_strip_accents(fr.lower()), en, fr)
    for fr, en in _FR_TO_EN
]

# Pre-built structures for fuzzy single-word matching (multi-word terms handled by exact pass)
_FR_NORM_TO_EN: Dict[str, str] = {fr: en for fr, en, _ in _FR_TO_EN_NORMALIZED}
_FR_NORM_SINGLE: List[str] = [fr for fr in _FR_NORM_TO_EN if " " not in fr]
_EN_PRODUCT_TERMS: set = {en for _, en, _ in _FR_TO_EN_NORMALIZED}

_ABBREVIATIONS: Dict[str, str] = {
    # English
    "lptp": "laptop",
    "lptop": "laptop",
    "labtop": "laptop",
    "fone": "phone",
    "phn": "phone",
    "phne": "phone",
    "tv": "television",
    "tvs": "television",
    "hdphn": "headphones",
    "hdphns": "headphones",
    # French — singular
    "tel": "telephone",
    "tele": "telephone",
    "ordi": "ordinateur",
    "pc": "ordinateur",
    "ecouteur": "casque",
    "ecouteurs": "casque",
    # French — plural variants
    "tels": "telephone",
    "ordis": "ordinateur",
    "pcs": "ordinateur",
}


def normalize_fr_to_en(text: str) -> str:
    """
    Replace French product category terms with English equivalents.
    Two passes:
      1. Exact substring match (longest-match ordered, accent-insensitive).
      2. Fuzzy token match — catches common misspellings (e.g. "telephonne" → "smartphone").
    Idempotent — safe to call on already-English text.
    """
    # Strip accents once upfront so all subsequent matching/replacement is reliable.
    result = _strip_accents(text)
    result_lower = result.lower()

    # Pass 1: exact substring matching (multi-word terms handled here)
    for fr_norm, en_term, _fr_orig in _FR_TO_EN_NORMALIZED:
        if fr_norm in result_lower:
            result = re.sub(re.escape(fr_norm), en_term, result, flags=re.IGNORECASE)
            result_lower = result.lower()

    # Pass 2: fuzzy single-word matching — catches misspellings not caught by exact match
    words = result.split()
    out: List[str] = []
    for word in words:
        w = word.lower()
        # Skip short tokens, English product terms already in place, and non-alpha tokens
        if len(w) < 4 or w in _EN_PRODUCT_TERMS or not w.isalpha():
            out.append(word)
            continue
        matches = _get_close_matches(w, _FR_NORM_SINGLE, n=1, cutoff=0.82)
        out.append(_FR_NORM_TO_EN[matches[0]] if matches else word)
    return " ".join(out)


# ---------------------------------------------------------------------------
# Language detection
# Overrides the declared language if the query text strongly signals the other.
# Used internally for choosing the right stopword set when splitting.
# ---------------------------------------------------------------------------
_FR_SIGNALS = {
    "ordinateur", "ventilateur", "telephone", "tablette", "bonjour",
    "je", "veux", "voudrais", "donnez", "montre", "cherche", "besoin",
    "voici", "aussi", "ainsi", "avec", "pour", "casque", "ecouteurs",
    "enceinte", "chargeur", "imprimante", "clavier", "souris", "aspirateur",
    # additional French-only signals
    "aimerais", "recherche", "faut", "trouvez", "cherchez", "montrez",
    "vouloir", "souhaite", "desire", "refrigerateur", "televiseur",
    "ecran", "moniteur", "batterie", "manette", "routeur", "adaptateur",
    "boite", "couleur", "noir", "blanc", "rouge", "bleu", "petit", "grand",
    "pas", "cher", "moins", "plus", "meilleur", "nouveau", "dernier",
}
_EN_SIGNALS = {
    "laptop", "smartphone", "tablet", "headphones", "earbuds", "speaker",
    "charger", "printer", "keyboard", "mouse", "television", "fan",
    "show", "find", "want", "need", "looking", "give",
}


def detect_query_language(text: str, declared_language: str) -> str:
    """
    Return 'fr' or 'en' based on the text content.
    Falls back to declared_language when no clear signal is found.
    """
    if not text:
        return declared_language
    normalized = _strip_accents(text.lower())
    tokens = set(re.findall(r"[a-z]+", normalized))
    fr_count = len(tokens & _FR_SIGNALS)
    en_count = len(tokens & _EN_SIGNALS)
    if fr_count > en_count:
        return "fr"
    if en_count > fr_count:
        return "en"
    return declared_language


# ---------------------------------------------------------------------------
# Multi-product splitting
# ---------------------------------------------------------------------------

# Intent preambles to strip from each segment after splitting so the
# remaining text is a clean product keyword for Magento / Typesense.
_PREAMBLE_EN = re.compile(
    r"^\s*(?:i\s+(?:also\s+)?(?:want|need|would\s+like|'d\s+like)\s+(?:a\s+|an\s+)?|"
    r"show\s+me\s+(?:a\s+|an\s+)?|find\s+(?:me\s+)?(?:a\s+|an\s+)?|"
    r"give\s+me\s+(?:a\s+|an\s+)?|looking\s+for\s+(?:a\s+|an\s+)?|"
    r"also\s+(?:a\s+|an\s+)?|a\s+|an\s+)\s*",
    re.IGNORECASE,
)
_PREAMBLE_FR = re.compile(
    r"^\s*(?:"
    # je + verb: veux, voudrais, cherche, recherche, desire, souhaite + optional article
    r"je\s+(?:veux|voudrais|cherche|recherche|desire|souhaite)\s+(?:aussi\s+)?(?:une?\s+|l[ae]\s+|les\s+|du\s+|de\s+la\s+|de\s+l.?\s+)?|"
    # j'aimerais / j'aurais besoin (handles ASCII ' and Unicode ' via .?)
    r"j.?aimerais\s+(?:aussi\s+)?(?:une?\s+|l[ae]\s+|les\s+)?|"
    # j'ai besoin de
    r"j.?ai\s+besoin\s+d.?\s*(?:une?\s+)?|"
    # il me faut
    r"il\s+me\s+faut\s+(?:une?\s+)?|"
    # imperative plural: donnez/montrez/trouvez/cherchez-moi
    r"(?:donnez|montrez|trouvez|cherchez)[- ]moi\s+(?:aussi\s+)?(?:une?\s+)?|"
    # imperative singular: donne/montre/trouve/cherche-moi
    r"(?:donne|montre|trouve|cherche)[- ]moi\s+(?:aussi\s+)?(?:une?\s+)?|"
    r"aussi\s+(?:une?\s+)?|"
    # bare articles / partitives at segment start
    r"une?\s+|l[ae]\s+|les\s+|du\s+|de\s+la\s+|de\s+l.?\s+|des\s+"
    r")\s*",
    re.IGNORECASE,
)


def _split_query_text(text: str, language: str) -> List[str]:
    """
    Split a multi-product query into individual product terms.

    Splits on:  ", "  |  " et "  |  " and "  |  " ainsi que "  |  " as well as "

    Strips intent preambles from each segment ("je veux un", "i want a", …).
    Returns the original text as a single-element list when no valid split found.

    Examples:
        "je veux un ordinateur et un ventilateur"  → ["ordinateur", "ventilateur"]
        "laptop and a fan"                         → ["laptop", "fan"]
        "téléphone, table"                         → ["téléphone", "table"]
        "Samsung Galaxy 256GB"                     → ["Samsung Galaxy 256GB"]  (no split)
    """
    # Detect actual language from text content so FR text with EN language param works
    effective_lang = detect_query_language(text, language)
    preamble = _PREAMBLE_FR if effective_lang == "fr" else _PREAMBLE_EN

    # Normalise apostrophe variants (mobile keyboards often emit U+2019) before matching
    text_norm = text.strip().replace('’', "'").replace('‘', "'")

    # Expand known abbreviations token-by-token before splitting
    text_norm = " ".join(
        _ABBREVIATIONS.get(_strip_accents(token.lower()), token)
        for token in text_norm.split()
    )

    # Normalize FR product terms to English before splitting
    text_norm = normalize_fr_to_en(text_norm)

    # \s* so "a,b" and "a, b" split; /\s* for slashes; \s+-\s+ for spaced dashes only
    parts = re.split(
        r",\s*|/\s*|\s+-\s+|\s+et\s+|\s+and\s+|\s+ainsi\s+que\s+|\s+as\s+well\s+as\s+",
        text_norm,
        flags=re.IGNORECASE,
    )

    def _strip_preamble(segment: str) -> str:
        return preamble.sub("", segment.strip()).strip()

    if len(parts) <= 1:
        # No conjunction found — still strip the preamble so the query is clean
        stripped = _strip_preamble(text_norm)
        return [stripped if len(stripped) >= 2 else text_norm]

    cleaned: List[str] = []
    for part in parts:
        part = _strip_preamble(part)
        if len(part) >= 2:
            cleaned.append(part)

    # Re-split any segment that survived with an embedded comma
    final: List[str] = []
    for segment in cleaned:
        if "," in segment:
            sub = [s.strip() for s in segment.split(",") if len(s.strip()) >= 2]
            final.extend(sub)
        else:
            final.append(segment)
    cleaned = final

    if len(cleaned) > 1:
        return cleaned

    # Split produced only 1 meaningful segment — return it preamble-stripped
    stripped = _strip_preamble(text_norm)
    return [stripped if len(stripped) >= 2 else text_norm]


# ---------------------------------------------------------------------------
# Intent resolution cache  (key = sha256 of all inputs, value = resolved query)
# ---------------------------------------------------------------------------
_INTENT_CACHE: Dict[str, str] = {}
_INTENT_CACHE_MAX = 256


def _intent_cache_key(
    user_text: str,
    image_caption: Optional[str],
    audio_text: Optional[str],
    video_caption: Optional[str],
    language: str,
) -> str:
    raw = f"{language}|{user_text}|{image_caption or ''}|{audio_text or ''}|{video_caption or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Public: resolve final search query from all multimodal inputs
# ---------------------------------------------------------------------------

async def resolve_multimodal_intent(
    user_text: str,
    image_caption: Optional[str],
    audio_text: Optional[str],
    video_caption: Optional[str],
    language: str,
) -> str:
    """
    Produce the FINAL search query that goes to Magento/Typesense.

    Priority rules applied by Mistral:
      1. User text has the HIGHEST priority.
      2. If user text requests different products than the image → ignore the image.
      3. If user text adds to / refines the image → combine both.
      4. If no user text → return the media caption as-is (caller handles this).

    Returns a concise keyword string, e.g. "laptop Samsung smartphone".
    Calls Mistral only when BOTH user_text AND some media caption are present.
    Repeated identical inputs hit the in-memory cache instantly.
    """
    user_text = (user_text or "").strip()
    image_caption = (image_caption or "").strip() or None
    audio_text = (audio_text or "").strip() or None
    video_caption = (video_caption or "").strip() or None

    # ---- Fast paths: only one signal present, no conflict to resolve
    has_media = bool(image_caption or video_caption or audio_text)
    if not has_media:
        return user_text                    # pure text — no Mistral needed

    if not user_text:
        # pure media — return caption directly; caller will run it through unified AI
        return image_caption or video_caption or audio_text or ""

    # ---- Both user text AND media present — check cache first
    cache_key = _intent_cache_key(user_text, image_caption, audio_text, video_caption, language)
    if cache_key in _INTENT_CACHE:
        return _INTENT_CACHE[cache_key]

    # ---- Mistral call: resolve conflicts and merge with text priority
    prompt = _build_intent_prompt(user_text, image_caption, audio_text, video_caption, language)
    client = _get_mistral_client()
    from app.config import settings

    try:
        response = await client.chat.complete_async(
            model=settings.MISTRAL_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=60,          # short query only — fast + cheap
        )
        resolved = response.choices[0].message.content.strip()
        # Strip any accidental label prefixes Mistral might add
        resolved = re.sub(
            r"^(output|query|search|result|reponse|requete)\s*[:\-]\s*",
            "", resolved, flags=re.IGNORECASE,
        ).strip(' "\'')

        if not resolved:
            resolved = user_text    # safe fallback

    except Exception as exc:
        logger.warning("resolve_multimodal_intent Mistral error (%s) — using user text", exc)
        resolved = user_text

    # Cache eviction + store
    if len(_INTENT_CACHE) >= _INTENT_CACHE_MAX:
        _INTENT_CACHE.pop(next(iter(_INTENT_CACHE)))
    _INTENT_CACHE[cache_key] = resolved
    return resolved


def _build_intent_prompt(
    user_text: str,
    image_caption: Optional[str],
    audio_text: Optional[str],
    video_caption: Optional[str],
    language: str,
) -> str:
    lang_label = "French" if language == "fr" else "English"
    lines: List[str] = [
        "You are an AI assistant for an e-commerce search system (Telia).",
        "Produce the FINAL search query by combining the inputs below.",
        "",
        "PRIORITY RULES:",
        "1. User text has the HIGHEST priority.",
        "2. If user text requests DIFFERENT products than the image/video → IGNORE the media, follow the text.",
        "3. If user text ADDS TO or REFINES what the image shows → combine both.",
        "4. If user text mentions a budget → always include it.",
        "5. Output the response language: " + lang_label + ".",
        "",
        "EXAMPLES:",
        'User text: "I also want a laptop and phone"  |  Image: "fan ventilateur"',
        "→ laptop smartphone",
        "",
        'User text: "sous 200000 FCFA"  |  Image: "Samsung Galaxy A54 smartphone noir"',
        "→ Samsung Galaxy smartphone budget 200000",
        "",
        'User text: "ignore the image, show me a table"  |  Image: "iPhone 15"',
        "→ table furniture",
        "",
        'User text: "je veux un ordinateur pas cher"  |  Image: "ventilateur Rowenta"',
        "→ ordinateur portable laptop pas cher",
        "",
        'User text: "black one with 256GB"  |  Image: "Apple iPhone 15 Pro"',
        "→ Apple iPhone 15 Pro 256GB black",
        "",
        "OUTPUT: only the search keywords. No explanation. No JSON. Max 12 words.",
        "",
    ]
    lines.append(f'User text: "{user_text}"')
    if image_caption:
        lines.append(f'Image: "{image_caption}"')
    if video_caption:
        lines.append(f'Video: "{video_caption}"')
    if audio_text:
        lines.append(f'Audio: "{audio_text}"')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phrases that mean "don't use the image/video I just uploaded"
# ---------------------------------------------------------------------------
_IGNORE_MEDIA_PATTERNS_EN = re.compile(
    r"\b(ignore|forget|skip|don'?t use|discard|not the|without)\s+"
    r"(the\s+)?(image|photo|picture|video|clip|frame|snapshot|attachment|file)\b",
    re.IGNORECASE,
)
_IGNORE_MEDIA_PATTERNS_FR = re.compile(
    r"\b(ignore[rz]?|oublie[rz]?|ne pas utiliser|sans|pas de|laisse[rz]? tomb[ae][rz]?)\s+"
    r"(l[a']?\s*)?(image|photo|vid[eé]o|photo|clip|fichier|pi[eè]ce)\b",
    re.IGNORECASE,
)

# Conjunctions that signal multiple product requests in one sentence
_MULTI_PRODUCT_SPLITTERS_EN = re.compile(
    r"\b(and\s+a|and\s+an|and\s+also|as\s+well\s+as|plus\s+a|plus\s+an|together\s+with|along\s+with)\b",
    re.IGNORECASE,
)
_MULTI_PRODUCT_SPLITTERS_FR = re.compile(
    r"\b(et\s+un[e]?|ainsi\s+qu[e']?|avec\s+un[e]?|en\s+plus\s+d[eu']n[e]?|accompagn[eé]\s+d[eu']n[e]?)\b",
    re.IGNORECASE,
)


def _fast_ignore_check(message: str, language: str) -> bool:
    """Return True if the message clearly says to ignore the media — no Mistral call needed."""
    if not message:
        return False
    if language == "fr":
        return bool(_IGNORE_MEDIA_PATTERNS_FR.search(message))
    return bool(_IGNORE_MEDIA_PATTERNS_EN.search(message))


def _fast_multi_product_check(message: str, language: str) -> bool:
    """Return True if the message clearly requests more than one distinct product."""
    if not message:
        return False
    # Use the splitter as the authoritative check — it covers both regex patterns
    # and bare "et"/"and" between nouns without articles.
    return len(_split_query_text(message, language)) > 1


# ---------------------------------------------------------------------------
# Spell-correction using Mistral (cached, short timeout so it never blocks)
# ---------------------------------------------------------------------------
_AUTOCORRECT_CACHE: Dict[str, str] = {}
_AUTOCORRECT_CACHE_MAX = 512


async def autocorrect_query(text: str, language: str) -> str:
    """
    Use Mistral to fix typos and spelling mistakes in the user's query.
    Handles both French and English. Returns the corrected text, or the
    original if Mistral is unavailable or too slow (3 s timeout).
    Result is cached so repeated identical queries are free.
    """
    text = text.strip()
    if not text or len(text) < 3:
        return text

    cache_key = f"{language}:{text.lower()}"
    if cache_key in _AUTOCORRECT_CACHE:
        return _AUTOCORRECT_CACHE[cache_key]

    lang_hint = "French or English" if language == "fr" else "English or French"
    prompt = (
        f"You are a spell-checker for an e-commerce product search chatbot.\n"
        f"Fix any typos or spelling mistakes in the {lang_hint} query below.\n"
        f"Rules:\n"
        f"- Preserve brand names, model numbers, and prices exactly.\n"
        f"- If the query is already correct, return it unchanged.\n"
        f"- Return ONLY the corrected query text — no explanation, no punctuation around it.\n\n"
        f"Query: {text}"
    )

    client = _get_mistral_client()
    from app.config import settings

    try:
        response = await asyncio.wait_for(
            client.chat.complete_async(
                model=settings.MISTRAL_TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=120,
            ),
            timeout=3.0,
        )
        corrected = response.choices[0].message.content.strip().strip('"\'')
        corrected = re.sub(r'^(?:query|corrected)[:\s]+', '', corrected, flags=re.IGNORECASE).strip()
        # Sanity check: reject if wildly different length
        result = corrected if corrected and 0.4 <= len(corrected) / max(len(text), 1) <= 3.0 else text
    except Exception as exc:
        logger.debug("autocorrect_query skipped (%s)", exc)
        result = text

    if len(_AUTOCORRECT_CACHE) >= _AUTOCORRECT_CACHE_MAX:
        _AUTOCORRECT_CACHE.pop(next(iter(_AUTOCORRECT_CACHE)))
    _AUTOCORRECT_CACHE[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

async def analyze_multimodal_query(
    message: str,
    image_caption: Optional[str],
    audio_transcription: Optional[str],
    video_caption: Optional[str],
    language: str,
) -> Dict[str, Any]:
    """
    Decide how to route the user's request.

    Returns::

        {
            "use_media": bool,          # False → ignore image/video caption
            "queries": ["q1", "q2"],    # One entry per distinct product to search for
        }

    The fast path handles obvious cases (regex match) without a Mistral call.
    Ambiguous or complex cases are sent to Mistral.
    """
    message = (message or "").strip()
    has_media = bool(image_caption or video_caption)

    # ---- Spell-correction: fix typos before any splitting or normalization
    if message:
        message = await autocorrect_query(message, language)

    # ---- Fast path: no media → split for multi-product, normalize FR terms
    if not has_media and not audio_transcription:
        if not message:
            return {"use_media": False, "queries": []}
        splits = _split_query_text(message, language)
        # Normalize each split segment: FR product terms → EN equivalents so
        # Typesense/Magento keyword expansion works on both stores.
        queries = [normalize_fr_to_en(q) for q in splits]
        return {"use_media": False, "queries": queries}

    # ---- Fast path: explicit "ignore image" detected by regex
    if has_media and _fast_ignore_check(message, language):
        return {"use_media": False, "queries": [message] if message else []}

    word_count = len(message.split()) if message else 0
    has_multi = _fast_multi_product_check(message, language)

    # ---- Fast path: no user text at all → pure media, single query from caption
    if not message:
        caption = image_caption or video_caption or audio_transcription or ""
        return {"use_media": True, "queries": [caption]}

    # ---- Fast path: very short additive hint (≤3 words, no multi-product pattern)
    # e.g. "black one", "256GB", "pas cher" — clearly refines the image, no conflict
    if not has_multi and word_count <= 3:
        return {"use_media": True, "queries": [message]}

    # ---- Deterministic multi-intent override: bypass Mistral when split is unambiguous
    # Handles: comma, slash, spaced dash, "and", "et" — plus FR→EN normalization.
    # "phone and laptop"       → ["phone", "laptop"]
    # "téléphone et ordinateur" → ["smartphone", "laptop"]
    # "fan, phone, laptop"     → ["fan", "phone", "laptop"]
    raw_splits = _split_query_text(message, language)
    if len(raw_splits) > 1:
        return {"use_media": has_media, "queries": raw_splits}

    # ---- Single-product query: send to Mistral for semantic rewriting / media conflict
    return await _mistral_decide(
        message=message,
        image_caption=image_caption,
        audio_transcription=audio_transcription,
        video_caption=video_caption,
        language=language,
        has_media=has_media,
    )


def _build_combined_query(
    message: str,
    image_caption: Optional[str],
    audio_transcription: Optional[str],
    video_caption: Optional[str],
    language: str,
) -> str:
    """Merge all signals into a single search string."""
    parts: List[str] = []
    if image_caption:
        parts.append(image_caption)
    if video_caption:
        parts.append(video_caption)
    if audio_transcription:
        parts.append(audio_transcription)
    if message:
        parts.append(message)
    return " ".join(filter(None, parts)).strip()


async def _mistral_decide(
    message: str,
    image_caption: Optional[str],
    audio_transcription: Optional[str],
    video_caption: Optional[str],
    language: str,
    has_media: bool,
) -> Dict[str, Any]:
    """Call Mistral to reason about complex multimodal queries."""
    prompt = _build_decision_prompt(
        message=message,
        image_caption=image_caption,
        audio_transcription=audio_transcription,
        video_caption=video_caption,
        language=language,
        has_media=has_media,
    )

    client = _get_mistral_client()
    from app.config import settings

    try:
        response = await client.chat.complete_async(
            model=settings.MISTRAL_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_decision_response(raw, message, image_caption, video_caption, has_media)
    except Exception as exc:
        logger.warning("mistral_decision fallback (Mistral error: %s)", exc)
        # Safe fallback: use all available context as one query
        combined = _build_combined_query(message, image_caption, audio_transcription, video_caption, language)
        splits = _split_query_text(combined, language) if combined else [message]
        queries = [normalize_fr_to_en(q) for q in splits]
        return {"use_media": has_media, "queries": queries}


def _build_decision_prompt(
    message: str,
    image_caption: Optional[str],
    audio_transcription: Optional[str],
    video_caption: Optional[str],
    language: str,
    has_media: bool,
) -> str:
    lines: List[str] = [
        "You are a routing assistant for an e-commerce chatbot.",
        "Decide two things:",
        "  1. use_media: should the image/video be used as a search signal?",
        "  2. queries: list of distinct product search phrases the user wants.",
        "",
        "Reply ONLY with valid JSON:",
        '  {"use_media": true, "queries": ["query1", "query2"]}',
        "",
        "RULES for use_media:",
        '- false  if user explicitly says to ignore the media ("ignore the image", "oublie la photo").',
        "- false  if user text asks for COMPLETELY DIFFERENT products than the image/video.",
        "         Example: image=fan, user_text='I want a laptop and a phone' → use_media=false",
        "- true   if user text refines, adds budget/color to the image, or mentions no other product.",
        "         Example: image=iPhone, user_text='under 200000 FCFA' → use_media=true",
        "",
        "RULES for queries:",
        "- Split ONLY when the user clearly wants TWO OR MORE different product CATEGORIES.",
        '  Example: "I want a samsung phone and a table" → ["samsung phone", "table"]',
        "- One query for a single product (even with attributes or budget).",
        "- Each query is a concise search phrase in the user's language.",
        "- No explanations. Output JSON only.",
        "",
        "EXAMPLES:",
        'user_text="I also want a laptop and phone", image="fan"',
        '→ {"use_media": false, "queries": ["laptop", "smartphone"]}',
        "",
        'user_text="black 256GB version", image="Apple iPhone 15 Pro"',
        '→ {"use_media": true, "queries": ["Apple iPhone 15 Pro 256GB black"]}',
        "",
        'user_text="ignore the image, show me a table", image="phone"',
        '→ {"use_media": false, "queries": ["table"]}',
        "",
    ]

    if message:
        lines.append(f'user_text="{message}"')
    if image_caption:
        lines.append(f'image="{image_caption}"')
    if video_caption:
        lines.append(f'video="{video_caption}"')
    if audio_transcription:
        lines.append(f'audio="{audio_transcription}"')
    if not has_media:
        lines.append("No media uploaded.")
    lines.append(f"Language: {language}")

    return "\n".join(lines)


def _parse_decision_response(
    raw: str,
    message: str,
    image_caption: Optional[str],
    video_caption: Optional[str],
    has_media: bool,
) -> Dict[str, Any]:
    """Parse Mistral's JSON reply and apply safety guards."""
    # Extract the first JSON object from the response
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not json_match:
        logger.warning("mistral_decision: no JSON found in response: %s", raw[:200])
        return _safe_fallback(message, image_caption, video_caption, has_media)

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        logger.warning("mistral_decision: JSON parse error: %s", raw[:200])
        return _safe_fallback(message, image_caption, video_caption, has_media)

    use_media = bool(data.get("use_media", has_media))
    queries_raw = data.get("queries") or []

    # Sanitise: must be a non-empty list of non-empty strings
    queries = [str(q).strip() for q in queries_raw if str(q).strip()]
    if not queries:
        queries = [message] if message else [""]

    # Safety: don't allow more than 3 parallel searches (prevents abuse)
    queries = queries[:3]

    return {"use_media": use_media, "queries": queries}


def _safe_fallback(
    message: str,
    image_caption: Optional[str],
    video_caption: Optional[str],
    has_media: bool,
) -> Dict[str, Any]:
    return {"use_media": has_media, "queries": [message] if message else [""]}
