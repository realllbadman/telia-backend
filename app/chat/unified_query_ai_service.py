import asyncio
import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from mistralai import Mistral

from app.config import settings

logger = logging.getLogger(__name__)

# Singleton client — created once, reused for all requests (saves SSL handshake per call)
_mistral_client: Optional[Mistral] = None

# Limit concurrent Mistral calls to avoid hammering the rate limit when
# multiple parallel queries fire at the same time (e.g. multi-product search).
_MISTRAL_SEMAPHORE = asyncio.Semaphore(2)

def _get_mistral_client() -> Mistral:
    global _mistral_client
    if _mistral_client is None:
        _mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)
    return _mistral_client

# Simple query result cache — avoids calling Mistral for identical queries
_QUERY_CACHE: Dict[str, Any] = {}
_QUERY_CACHE_MAX = 256


class UnifiedQueryAIService:
    _GENERIC_CATEGORY_TOKENS = {
        "electronic", "electronics", "device", "devices", "gadget", "gadgets",
        "technology", "tech", "product", "products", "item", "items",
        "appliance", "appliances", "equipment", "equipement", "materiel",
        "produit", "produits", "article", "articles",
    }
    _EN_SYNONYMS = {
        "notebook": "laptop",
        "notebooks": "laptop",
        "ultrabook": "laptop",
        "ultrabooks": "laptop",
        "mobile": "phone",
        "mobiles": "phone",
        "smartphone": "phone",
        "smartphones": "phone",
        "cellphone": "phone",
        "cellphones": "phone",
        "ventilator": "fan",
        "ventilators": "fan",
        "cooler": "fan",
        "coolers": "fan",
    }
    _FR_SYNONYMS = {
        "notebook": "laptop",
        "ordinateur": "laptop",
        "portable": "laptop",
        "portables": "laptop",
        "telephone": "phone",
        "telephones": "phone",
        "mobile": "phone",
        "mobiles": "phone",
        "smartphone": "phone",
        "smartphones": "phone",
        "ventilateur": "fan",
        "ventilateurs": "fan",
        "ventilo": "fan",
    }
    _PHRASE_SYNONYMS = {
        "en": {
            "cell phone": "phone",
            "mobile phone": "phone",
            "notebook computer": "laptop",
        },
        "fr": {
            "telephone portable": "phone",
            "ordinateur portable": "laptop",
        },
    }
    _USER_TYPE_HINTS = {
        "student": {"student", "school", "college", "university", "study", "studies", "classe", "etudiant", "etudiante"},
        "gamer": {"gamer", "gaming", "game", "esports", "fps", "console"},
        "business": {"business", "office", "work", "professional", "enterprise", "bureau"},
        "creator": {"creator", "editing", "design", "video", "photo", "content"},
    }
    _CATEGORY_HINTS = {
        "smartphone": {"phone", "android", "iphone", "mobile", "smartphone", "gaming phone"},
        "laptop": {"laptop", "notebook", "ultrabook", "macbook", "computer"},
        "fan": {"fan", "ventilator", "cooler", "cooling", "cool", "room cooling"},
        "headphones": {"headphone", "headphones", "earbud", "earbuds", "headset"},
        "tablet": {"tablet", "ipad"},
        "television": {"tv", "television", "smarttv", "oled", "qled"},
    }
    _LANGUAGE_MARKERS_EN = {
        "i", "im", "i'm", "need", "want", "for", "with", "under", "cheap", "budget",
        "phone", "laptop", "fan", "gaming", "student", "room", "cool", "expensive",
    }
    _LANGUAGE_MARKERS_FR = {
        "je", "j", "suis", "besoin", "cherche", "pour", "avec", "moins", "cher", "budget",
        "telephone", "portable", "ventilateur", "etudiant", "chambre", "refroidir",
        "pas", "trop", "cher", "de",
    }
    _CATEGORY_LOCALIZATION = {
        "fr": {
            "smartphone": "telephone",
            "laptop": "ordinateur portable",
            "fan": "ventilateur",
            "headphones": "casque",
            "tablet": "tablette",
            "television": "television",
        },
    }
    _USE_CASE_LOCALIZATION = {
        "fr": {
            "education": "education",
            "room cooling": "refroidissement chambre",
            "gaming": "gaming",
            "business": "travail",
            "travel": "voyage",
        },
    }
    _USER_TYPE_LOCALIZATION = {
        "fr": {
            "student": "etudiant",
            "gamer": "gamer",
            "business": "professionnel",
            "creator": "createur",
        },
    }
    _PRICE_CLASS_LOCALIZATION = {
        "fr": {
            "budget": "budget",
            "low-budget": "petit budget",
            "mid-range": "milieu de gamme",
            "premium": "premium",
        },
    }
    _KEYWORD_LOCALIZATION = {
        "fr": {
            "smartphone": "telephone",
            "phone": "telephone",
            "laptop": "ordinateur portable",
            "fan": "ventilateur",
            "headphones": "casque",
            "tablet": "tablette",
            "television": "television",
            "student": "etudiant",
            "business": "professionnel",
            "budget": "budget",
            "student laptop": "ordinateur portable etudiant",
            "education laptop": "ordinateur portable education",
            "budget laptop": "ordinateur portable budget",
            "low-budget laptop": "ordinateur portable petit budget",
            "premium laptop": "ordinateur portable premium",
            "gaming phone": "telephone gaming",
            "budget smartphone": "telephone budget",
            "low-budget smartphone": "telephone petit budget",
            "premium smartphone": "telephone premium",
            "cooling appliance": "appareil de refroidissement",
            "room cooling": "refroidissement chambre",
        },
    }

    @staticmethod
    async def process_raw_query(input_text: str, language: str) -> Dict[str, Any]:
        preferred_language = UnifiedQueryAIService._normalize_language_hint(language)
        cleaned_text = UnifiedQueryAIService._normalize_whitespace(str(input_text or ""))
        if not cleaned_text:
            return UnifiedQueryAIService._empty_payload(preferred_language or "en")

        # Cache hit — skip Mistral entirely for repeated queries
        cache_key = f"{language}:{cleaned_text}"
        if cache_key in _QUERY_CACHE:
            return _QUERY_CACHE[cache_key]

        detected_language, is_mixed_language = UnifiedQueryAIService._detect_language(
            input_text=cleaned_text,
            preferred_language=preferred_language,
        )
        output_language = detected_language
        if is_mixed_language and preferred_language in {"en", "fr"}:
            output_language = preferred_language

        prompt = UnifiedQueryAIService._build_prompt(
            input_text=cleaned_text,
            output_language=output_language,
            detected_language=detected_language,
            is_mixed_language=is_mixed_language,
        )
        # Retry up to 3 times with exponential back-off for 429 rate-limit responses.
        # Other errors fall through immediately to the fallback.
        _MAX_RETRIES = 3
        _RETRY_DELAYS = [1.0, 2.0, 4.0]  # seconds between attempts

        messages = [
            {
                "role": "system",
                "content": (
                    "You are the intelligence layer of the Telia AI shopping assistant. "
                    "Your role is to understand user intent (even if vague, misspelled, or emotionally phrased), "
                    "rewrite it into clean, concrete product-focused search queries, and return strict JSON only. "
                    "NEVER return empty keywords — always make the best logical inference from context. "
                    "Always normalize product category names to English regardless of input language."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                client = _get_mistral_client()
                async with _MISTRAL_SEMAPHORE:
                    response = await client.chat.complete_async(
                        model=settings.MISTRAL_TEXT_MODEL,
                        messages=messages,
                        temperature=0,
                        max_tokens=420,
                    )
                raw_content = UnifiedQueryAIService._extract_content_text(response)
                parsed = UnifiedQueryAIService._parse_json_content(raw_content)
                result = UnifiedQueryAIService._coerce_payload(
                    payload=parsed,
                    language=output_language,
                    source_text=cleaned_text,
                )
                # Store in cache — evict oldest entry if full
                if len(_QUERY_CACHE) >= _QUERY_CACHE_MAX:
                    _QUERY_CACHE.pop(next(iter(_QUERY_CACHE)))
                _QUERY_CACHE[cache_key] = result
                return result
            except Exception as exc:
                last_exc = exc
                exc_str = str(exc)
                # Only retry on rate-limit (429); bail immediately on other errors
                is_rate_limit = "429" in exc_str or "capacity exceeded" in exc_str.lower()
                if not is_rate_limit or attempt >= _MAX_RETRIES - 1:
                    break
                wait = _RETRY_DELAYS[attempt]
                logger.warning(
                    "Mistral 429 rate-limit on attempt %d/%d — retrying in %.1fs",
                    attempt + 1, _MAX_RETRIES, wait,
                )
                await asyncio.sleep(wait)

        logger.warning("Unified query AI failed, using fallback normalization: %s", last_exc)
        return UnifiedQueryAIService._fallback_payload(cleaned_text, output_language)

    @staticmethod
    def _build_prompt(
        input_text: str,
        output_language: str,
        detected_language: str,
        is_mixed_language: bool,
    ) -> str:
        return f"""
You are the intelligence layer of the Telia AI shopping assistant.

Detected input language: {detected_language}
Mixed language input: {"yes" if is_mixed_language else "no"}
Required output language: {output_language}
Raw input: {input_text}

━━━ CORE RULES ━━━

1. UNDERSTAND — even vague, emotional, or poorly written requests.
2. REWRITE — turn messy input into clean, product-focused search terms.
3. NEVER LOSE MEANING — if the user mentions multiple needs, capture all of them in keywords.
4. NEVER RETURN EMPTY — always make a best logical guess from context.
5. NORMALIZE TO ENGLISH — category and keywords must be in English regardless of input language.

━━━ INTENT REWRITING EXAMPLES ━━━

"I need a laptop for my kid"
→ category: "laptop", keywords: ["student laptop", "budget laptop", "lightweight laptop"]

"something for office accounting"
→ category: "laptop", keywords: ["business laptop", "laptop SSD", "laptop 8GB RAM"]

"table for kids"
→ category: "desk", keywords: ["kids table", "study table", "children desk"]

"cheap phone with good battery"
→ category: "smartphone", keywords: ["budget smartphone", "long battery smartphone"]

"je cherche quelque chose pour refroidir ma chambre"
→ category: "fan", keywords: ["fan", "room fan", "cooling fan", "air cooler"]

"bon écran pour travailler"
→ category: "monitor", keywords: ["monitor", "work monitor", "office display"]

━━━ LANGUAGE HANDLING ━━━

Always output category and keywords in English.
French → English product mapping:
  "ordinateur portable" → "laptop"
  "ventilateur" → "fan"
  "téléphone" / "telephone" → "smartphone"
  "tablette" → "tablet"
  "écran" / "moniteur" → "monitor"
  "casque" → "headphones"
  "enceinte" → "speaker"
Mixed input: extract the category from whichever language signal is clearest.

━━━ BUDGET EXTRACTION ━━━

- "under X", "less than X", "below X", "moins de X", "maximum X", "max X" → budget.max = X
- "over X", "more than X", "at least X", "minimum X", "à partir de X" → budget.min = X
- "between X and Y", "entre X et Y" → budget.min = X, budget.max = Y
- Currency: XAF / FCFA / F CFA → "XAF"; otherwise leave empty
- "je veux un laptop de 200000" → budget.max = 200000 (shopping budget context)

━━━ TASKS ━━━

1. Identify the product category (laptop, smartphone, fan, headphones, tablet, monitor, speaker, etc.)
2. Extract all relevant search keywords — rewrite vague language into product-focused terms
3. Extract specs/attributes (color, storage, screen size, battery, RAM, etc.)
4. Infer use_case from context (gaming, education, business, travel, room cooling, etc.)
5. Infer user_type if mentioned (student, gamer, business professional, creator, etc.)
6. Extract budget constraints following the rules above
7. Output strict JSON only — no markdown, no explanation

Output schema (strict JSON):
{{
  "category": "<product category in English>",
  "keywords": ["<concrete product-focused search terms — rewritten from vague input>"],
  "attributes": ["<specs: color, storage, screen size, RAM, battery, etc.>"],
  "use_case": "<gaming|education|business|travel|room cooling|etc.>",
  "user_type": "<student|gamer|business|creator|etc.>",
  "price_class": "<budget|low-budget|mid-range|premium — only if indicated>",
  "budget": {{
    "min": null,
    "max": null,
    "currency": "<XAF|USD|EUR|etc. or empty>"
  }},
  "priority_terms": ["<2-4 most important search terms>"],
  "negative_terms": [],
  "language": "{output_language}",
  "confidence": 0.0
}}
""".strip()

    @staticmethod
    def _extract_content_text(response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except Exception:
            return ""

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(parts).strip()

        return str(content or "").strip()

    @staticmethod
    def _parse_json_content(text: str) -> Dict[str, Any]:
        cleaned = str(text or "").strip()
        if not cleaned:
            raise ValueError("Empty model response")

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in model response")

        json_blob = cleaned[start:end + 1]
        return json.loads(json_blob)

    @staticmethod
    def _coerce_payload(payload: Dict[str, Any], language: str, source_text: str) -> Dict[str, Any]:
        result = UnifiedQueryAIService._empty_payload(language)

        category = UnifiedQueryAIService._normalize_term(payload.get("category"), language)
        keywords = UnifiedQueryAIService._normalize_terms(payload.get("keywords"), language, limit=12)
        attributes = UnifiedQueryAIService._normalize_terms(payload.get("attributes"), language, limit=12)
        use_case = UnifiedQueryAIService._normalize_use_case(payload.get("use_case"))
        user_type = UnifiedQueryAIService._normalize_user_type(payload.get("user_type"))
        price_class = UnifiedQueryAIService._normalize_price_class(payload.get("price_class"))
        priority_terms = UnifiedQueryAIService._normalize_terms(payload.get("priority_terms"), language, limit=10)
        negative_terms = UnifiedQueryAIService._normalize_terms(payload.get("negative_terms"), language, limit=10)

        budget = UnifiedQueryAIService._coerce_budget(payload.get("budget"), source_text, language)
        inferred_use_case = use_case or UnifiedQueryAIService._infer_use_case(source_text, language)
        inferred_user_type = user_type or UnifiedQueryAIService._infer_user_type(source_text, language)

        if not category:
            category = UnifiedQueryAIService._infer_category(
                terms=keywords + attributes,
                source_text=source_text,
                language=language,
            )
        if not category or UnifiedQueryAIService._is_generic_category(category, language):
            contextual_category = UnifiedQueryAIService._infer_contextual_category(
                source_text=source_text,
                language=language,
                use_case=inferred_use_case,
                user_type=inferred_user_type,
                keywords=keywords,
                attributes=attributes,
            )
            if contextual_category:
                category = contextual_category

        if not keywords:
            keywords = UnifiedQueryAIService._keywords_from_text(source_text, language)

        if not price_class:
            price_class = UnifiedQueryAIService._infer_price_class(
                source_text=source_text,
                budget=budget,
                language=language,
            )

        keywords = UnifiedQueryAIService._expand_semantic_keywords(
            base_keywords=keywords,
            category=category,
            use_case=inferred_use_case,
            user_type=inferred_user_type,
            price_class=price_class,
            language=language,
        )

        if not priority_terms:
            priority_terms = keywords[:4]
        else:
            priority_terms = UnifiedQueryAIService._expand_semantic_keywords(
                base_keywords=priority_terms,
                category=category,
                use_case=inferred_use_case,
                user_type=inferred_user_type,
                price_class=price_class,
                language=language,
            )[:6]

        if not negative_terms:
            negative_terms = UnifiedQueryAIService._extract_negative_terms(source_text, language)

        category = UnifiedQueryAIService._localize_category(category, language)
        inferred_use_case = UnifiedQueryAIService._localize_use_case(inferred_use_case, language)
        inferred_user_type = UnifiedQueryAIService._localize_user_type(inferred_user_type, language)
        price_class = UnifiedQueryAIService._localize_price_class(price_class, language)
        keywords = UnifiedQueryAIService._localize_terms(keywords, language)
        attributes = UnifiedQueryAIService._localize_terms(attributes, language)
        priority_terms = UnifiedQueryAIService._localize_terms(priority_terms, language)
        negative_terms = UnifiedQueryAIService._localize_terms(negative_terms, language)

        confidence = UnifiedQueryAIService._coerce_confidence(payload.get("confidence"))
        if confidence is None:
            confidence = UnifiedQueryAIService._fallback_confidence(
                category=category,
                keywords=keywords,
                use_case=inferred_use_case,
            )

        result.update(
            {
                "category": category,
                "keywords": keywords[:8],
                "attributes": attributes[:8],
                "use_case": inferred_use_case,
                "user_type": inferred_user_type,
                "price_class": price_class,
                "budget": budget,
                "priority_terms": priority_terms[:6],
                "negative_terms": negative_terms[:6],
                "language": language,
                "confidence": confidence,
            }
        )
        return result

    @staticmethod
    def _fallback_payload(source_text: str, language: str) -> Dict[str, Any]:
        keywords = UnifiedQueryAIService._keywords_from_text(source_text, language)
        category = UnifiedQueryAIService._infer_category(
            terms=keywords,
            source_text=source_text,
            language=language,
        )
        user_type = UnifiedQueryAIService._infer_user_type(source_text, language)
        use_case = UnifiedQueryAIService._infer_use_case(source_text, language)
        if not category or UnifiedQueryAIService._is_generic_category(category, language):
            contextual_category = UnifiedQueryAIService._infer_contextual_category(
                source_text=source_text,
                language=language,
                use_case=use_case,
                user_type=user_type,
                keywords=keywords,
                attributes=[],
            )
            if contextual_category:
                category = contextual_category
        budget = UnifiedQueryAIService._extract_budget(source_text, language)
        price_class = UnifiedQueryAIService._infer_price_class(
            source_text=source_text,
            budget=budget,
            language=language,
        )
        keywords = UnifiedQueryAIService._expand_semantic_keywords(
            base_keywords=keywords,
            category=category,
            use_case=use_case,
            user_type=user_type,
            price_class=price_class,
            language=language,
        )
        negative_terms = UnifiedQueryAIService._extract_negative_terms(source_text, language)

        category = UnifiedQueryAIService._localize_category(category, language)
        use_case = UnifiedQueryAIService._localize_use_case(use_case, language)
        user_type = UnifiedQueryAIService._localize_user_type(user_type, language)
        price_class = UnifiedQueryAIService._localize_price_class(price_class, language)
        keywords = UnifiedQueryAIService._localize_terms(keywords, language)
        negative_terms = UnifiedQueryAIService._localize_terms(negative_terms, language)

        return {
            "category": category,
            "keywords": keywords[:8],
            "attributes": [],
            "use_case": use_case,
            "user_type": user_type,
            "price_class": price_class,
            "budget": budget,
            "priority_terms": keywords[:4],
            "negative_terms": negative_terms[:6],
            "language": language,
            "confidence": 0.42,
        }

    @staticmethod
    def _empty_payload(language: str) -> Dict[str, Any]:
        return {
            "category": "",
            "keywords": [],
            "attributes": [],
            "use_case": "",
            "user_type": "",
            "price_class": "",
            "budget": {"min": None, "max": None, "currency": ""},
            "priority_terms": [],
            "negative_terms": [],
            "language": language,
            "confidence": 0.0,
        }

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip())

    @staticmethod
    def _normalize_language_hint(language: Any) -> str:
        value = str(language or "").strip().lower()
        if value == "fr":
            return "fr"
        if value == "en":
            return "en"
        return ""

    @staticmethod
    def _detect_language(input_text: str, preferred_language: str) -> Tuple[str, bool]:
        lowered = str(input_text or "").lower()
        stripped = UnifiedQueryAIService._strip_accents(lowered)
        tokens = re.findall(r"[a-z']+", stripped)

        en_score = sum(1 for token in tokens if token in UnifiedQueryAIService._LANGUAGE_MARKERS_EN)
        fr_score = sum(1 for token in tokens if token in UnifiedQueryAIService._LANGUAGE_MARKERS_FR)

        if re.search(
            r"[\u00e0\u00e2\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00fb\u00f9\u00fc\u00ff\u0153\u00e6]",
            lowered,
        ):
            fr_score += 2

        if "'" in lowered:
            if any(marker in lowered for marker in ("j'", "l'", "d'", "qu'")):
                fr_score += 1
            if any(marker in lowered for marker in ("i'm", "don't", "can't", "it's")):
                en_score += 1

        mixed = en_score > 0 and fr_score > 0 and abs(en_score - fr_score) <= 2

        if en_score == fr_score:
            if preferred_language in {"en", "fr"}:
                return preferred_language, mixed
            return "en", mixed
        return ("fr", mixed) if fr_score > en_score else ("en", mixed)

    @staticmethod
    def _strip_accents(value: str) -> str:
        return "".join(
            ch
            for ch in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(ch)
        )

    @staticmethod
    def _normalize_text_value(value: Any) -> str:
        return UnifiedQueryAIService._normalize_whitespace(str(value or ""))

    @staticmethod
    def _normalize_for_matching(value: str, language: str) -> str:
        normalized = UnifiedQueryAIService._strip_accents(str(value or "")).lower()
        normalized = UnifiedQueryAIService._normalize_whitespace(normalized)

        phrase_map = UnifiedQueryAIService._PHRASE_SYNONYMS.get(language, {})
        for phrase, replacement in phrase_map.items():
            normalized = re.sub(
                rf"\b{re.escape(phrase)}\b",
                replacement,
                normalized,
            )

        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = UnifiedQueryAIService._normalize_whitespace(normalized)

        synonym_map = (
            UnifiedQueryAIService._FR_SYNONYMS
            if language == "fr"
            else UnifiedQueryAIService._EN_SYNONYMS
        )
        tokens = [synonym_map.get(token, token) for token in normalized.split()]
        return " ".join(tokens).strip()

    @staticmethod
    def _normalize_term(value: Any, language: str) -> str:
        raw = UnifiedQueryAIService._normalize_text_value(value)
        if not raw:
            return ""
        matched = UnifiedQueryAIService._normalize_for_matching(raw, language)
        return matched or raw

    @staticmethod
    def _normalize_terms(value: Any, language: str, limit: int) -> List[str]:
        if not isinstance(value, list):
            return []
        terms: List[str] = []
        seen: set[str] = set()
        for item in value:
            term = UnifiedQueryAIService._normalize_term(item, language)
            if not term:
                continue
            if term in seen:
                continue
            seen.add(term)
            terms.append(term)
            if len(terms) >= limit:
                break
        return terms

    @staticmethod
    def _normalize_user_type(value: Any) -> str:
        normalized = UnifiedQueryAIService._normalize_for_matching(
            UnifiedQueryAIService._normalize_text_value(value),
            "en",
        )
        if not normalized:
            return ""
        mapping = {
            "etudiant": "student",
            "etudiante": "student",
            "eleve": "student",
            "professionnel": "business",
        }
        normalized = mapping.get(normalized, normalized)
        if normalized in {"student", "gamer", "business", "creator"}:
            return normalized
        return normalized

    @staticmethod
    def _normalize_use_case(value: Any) -> str:
        normalized = UnifiedQueryAIService._normalize_text_value(value).lower()
        if not normalized:
            return ""
        mapping = {
            "study": "education",
            "education": "education",
            "school": "education",
            "student": "education",
            "etudiant": "education",
            "etudiante": "education",
            "room cool": "room cooling",
            "cooling": "room cooling",
            "room cooling": "room cooling",
            "gaming": "gaming",
            "game": "gaming",
            "business": "business",
            "work": "business",
            "travel": "travel",
        }
        return mapping.get(normalized, normalized)

    @staticmethod
    def _normalize_price_class(value: Any) -> str:
        normalized = UnifiedQueryAIService._normalize_text_value(value).lower()
        if not normalized:
            return ""
        mapping = {
            "budget": "budget",
            "low budget": "low-budget",
            "low-budget": "low-budget",
            "affordable": "budget",
            "cheap": "budget",
            "mid range": "mid-range",
            "mid-range": "mid-range",
            "premium": "premium",
            "high end": "premium",
            "high-end": "premium",
        }
        return mapping.get(normalized, normalized)

    @staticmethod
    def _localize_category(value: str, language: str) -> str:
        normalized = UnifiedQueryAIService._normalize_whitespace(str(value or "").lower())
        if not normalized:
            return ""
        localized = UnifiedQueryAIService._CATEGORY_LOCALIZATION.get(language, {}).get(normalized)
        return localized or normalized

    @staticmethod
    def _localize_use_case(value: str, language: str) -> str:
        normalized = UnifiedQueryAIService._normalize_whitespace(str(value or "").lower())
        if not normalized:
            return ""
        localized = UnifiedQueryAIService._USE_CASE_LOCALIZATION.get(language, {}).get(normalized)
        return localized or normalized

    @staticmethod
    def _localize_user_type(value: str, language: str) -> str:
        normalized = UnifiedQueryAIService._normalize_whitespace(str(value or "").lower())
        if not normalized:
            return ""
        localized = UnifiedQueryAIService._USER_TYPE_LOCALIZATION.get(language, {}).get(normalized)
        return localized or normalized

    @staticmethod
    def _localize_price_class(value: str, language: str) -> str:
        normalized = UnifiedQueryAIService._normalize_whitespace(str(value or "").lower())
        if not normalized:
            return ""
        localized = UnifiedQueryAIService._PRICE_CLASS_LOCALIZATION.get(language, {}).get(normalized)
        return localized or normalized

    @staticmethod
    def _localize_terms(values: List[str], language: str) -> List[str]:
        localized_values: List[str] = []
        seen: set[str] = set()
        for raw in values:
            normalized = UnifiedQueryAIService._normalize_whitespace(str(raw or ""))
            if not normalized:
                continue

            mapped = UnifiedQueryAIService._KEYWORD_LOCALIZATION.get(language, {}).get(
                normalized.lower(),
                normalized,
            )
            key = mapped.lower()
            if key in seen:
                continue
            seen.add(key)
            localized_values.append(mapped)
        return localized_values

    @staticmethod
    def _coerce_confidence(value: Any) -> Optional[float]:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return None
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return round(confidence, 3)

    @staticmethod
    def _fallback_confidence(category: str, keywords: List[str], use_case: str) -> float:
        base = 0.35
        if category:
            base += 0.2
        if keywords:
            base += min(0.3, len(keywords) * 0.05)
        if use_case:
            base += 0.1
        return round(min(0.95, base), 3)

    @staticmethod
    def _keywords_from_text(text: str, language: str) -> List[str]:
        normalized = UnifiedQueryAIService._normalize_for_matching(text, language)
        if not normalized:
            return []

        stopwords_en = {
            "the", "a", "an", "with", "and", "or", "in", "on", "for", "of", "to",
            "i", "you", "we", "they", "is", "are", "need", "want", "looking",
            "find", "show", "please", "product", "item",
        }
        stopwords_fr = {
            "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "pour",
            "je", "tu", "nous", "vous", "veux", "besoin", "cherche", "montre",
            "produit", "article",
        }
        stopwords = stopwords_fr if language == "fr" else stopwords_en

        terms: List[str] = []
        seen: set[str] = set()
        for token in normalized.split():
            if len(token) <= 2 or token in stopwords:
                continue
            if token in seen:
                continue
            seen.add(token)
            terms.append(token)
            if len(terms) >= 8:
                break
        return terms

    @staticmethod
    def _infer_category(terms: List[str], source_text: str, language: str) -> str:
        signal = " ".join(terms) + " " + source_text
        normalized_signal = UnifiedQueryAIService._normalize_for_matching(signal, language)
        best_category = ""
        best_score = 0

        for category, hints in UnifiedQueryAIService._CATEGORY_HINTS.items():
            score = sum(1 for hint in hints if hint in normalized_signal.split() or f" {hint} " in f" {normalized_signal} ")
            if score > best_score:
                best_score = score
                best_category = category
        return best_category

    @staticmethod
    def _infer_user_type(source_text: str, language: str) -> str:
        normalized_current = UnifiedQueryAIService._normalize_for_matching(source_text, language)
        normalized_en = UnifiedQueryAIService._normalize_for_matching(source_text, "en")
        normalized = f"{normalized_current} {normalized_en}".strip()
        for user_type, hints in UnifiedQueryAIService._USER_TYPE_HINTS.items():
            if any(hint in normalized.split() or f" {hint} " in f" {normalized} " for hint in hints):
                return user_type
        return ""

    @staticmethod
    def _infer_use_case(source_text: str, language: str) -> str:
        normalized = UnifiedQueryAIService._normalize_for_matching(source_text, language)
        if any(term in normalized for term in {"gaming", "gamer", "esports", "game"}):
            return "gaming"
        if any(term in normalized for term in {"cool", "cooling", "heat", "hot", "room cooling", "room"}):
            if any(term in normalized for term in {"cool", "cooling", "heat", "hot"}):
                return "room cooling"
        if any(term in normalized for term in {"study", "student", "school", "college", "university", "etude"}):
            return "education"
        if any(term in normalized for term in {"work", "office", "business", "professional", "bureau"}):
            return "business"
        if any(term in normalized for term in {"travel", "portable", "voyage"}):
            return "travel"
        return ""

    @staticmethod
    def _infer_price_class(source_text: str, budget: Dict[str, Any], language: str) -> str:
        normalized = UnifiedQueryAIService._normalize_for_matching(source_text, language)
        normalized_en = UnifiedQueryAIService._normalize_for_matching(source_text, "en")
        normalized = f"{normalized} {normalized_en}".strip()
        budget_min = UnifiedQueryAIService._safe_number((budget or {}).get("min"))
        budget_max = UnifiedQueryAIService._safe_number((budget or {}).get("max"))

        low_budget_tokens = {
            "cheap", "budget", "affordable", "economical", "low cost", "low-cost",
            "not too expensive", "inexpensive", "entry level", "entry-level",
        }
        premium_tokens = {"premium", "flagship", "high end", "high-end", "top tier", "top-tier"}

        if any(token in normalized for token in premium_tokens):
            return "premium"
        if any(token in normalized for token in low_budget_tokens):
            if "not too expensive" in normalized:
                return "low-budget"
            return "budget"

        if budget_max is not None:
            if budget_max <= 500:
                return "budget"
            if budget_max <= 900:
                return "low-budget"
            if budget_max <= 1400:
                return "mid-range"
            return "premium"

        if budget_min is not None and budget_min >= 1200:
            return "premium"

        return ""

    @staticmethod
    def _expand_semantic_keywords(
        base_keywords: List[str],
        category: str,
        use_case: str,
        user_type: str,
        price_class: str,
        language: str,
    ) -> List[str]:
        output: List[str] = []
        seen: set[str] = set()

        def add(value: str) -> None:
            normalized = UnifiedQueryAIService._normalize_whitespace(value)
            if not normalized:
                return
            key = normalized.lower()
            if key in seen:
                return
            seen.add(key)
            output.append(normalized)

        if category:
            add(category)
        if use_case:
            add(use_case)
        if user_type:
            add(user_type)

        if user_type == "student" and category == "laptop":
            add("student laptop")
        if use_case == "education" and category == "laptop":
            add("education laptop")
        if use_case == "room cooling" and category == "fan":
            add("fan")
            add("cooling appliance")
        if use_case == "gaming" and category == "smartphone":
            add("gaming phone")
        if use_case == "gaming" and category == "laptop":
            add("gaming laptop")

        if price_class in {"budget", "low-budget"} and category:
            if category == "smartphone":
                add("budget smartphone")
            else:
                add(f"budget {category}")
        if price_class == "low-budget" and category:
            if category == "smartphone":
                add("low-budget smartphone")
            else:
                add(f"low-budget {category}")
        if price_class == "premium" and category:
            if category == "smartphone":
                add("premium smartphone")
            else:
                add(f"premium {category}")

        for keyword in base_keywords:
            add(keyword)

        return output[:10]

    @staticmethod
    def _infer_contextual_category(
        source_text: str,
        language: str,
        use_case: str,
        user_type: str,
        keywords: List[str],
        attributes: List[str],
    ) -> str:
        if use_case not in {"education", "business"} and user_type not in {"student", "business"}:
            return ""

        normalized_current = UnifiedQueryAIService._normalize_for_matching(source_text, language)
        normalized_en = UnifiedQueryAIService._normalize_for_matching(source_text, "en")
        signal_parts = [normalized_current, normalized_en]
        signal_parts.extend(UnifiedQueryAIService._normalize_for_matching(k, language) for k in keywords)
        signal_parts.extend(UnifiedQueryAIService._normalize_for_matching(a, language) for a in attributes)
        signal = " ".join(part for part in signal_parts if part)

        non_laptop_markers = {
            "phone", "smartphone", "mobile", "iphone", "android", "telephone",
            "fan", "ventilator", "ventilateur", "cooler", "air cooler",
            "headphone", "headphones", "earbud", "earbuds", "headset", "casque",
            "tablet", "tablette", "tv", "television",
        }
        if any(
            marker in signal.split() or f" {marker} " in f" {signal} "
            for marker in non_laptop_markers
        ):
            return ""

        if user_type == "student" or use_case == "education":
            return "laptop"
        if user_type == "business" and use_case == "business":
            return "laptop"
        return ""

    @staticmethod
    def _is_generic_category(value: str, language: str) -> bool:
        normalized = UnifiedQueryAIService._normalize_for_matching(value, language)
        if not normalized:
            return False
        tokens = [token for token in normalized.split() if token]
        if not tokens:
            return False
        return all(
            token in UnifiedQueryAIService._GENERIC_CATEGORY_TOKENS
            for token in tokens
        )

    @staticmethod
    def _coerce_budget(value: Any, source_text: str, language: str) -> Dict[str, Any]:
        if isinstance(value, dict):
            min_value = UnifiedQueryAIService._safe_number(value.get("min"))
            max_value = UnifiedQueryAIService._safe_number(value.get("max"))
            currency = UnifiedQueryAIService._normalize_currency(value.get("currency"))
            if min_value is not None and max_value is not None and min_value > max_value:
                min_value, max_value = max_value, min_value
            if min_value is not None or max_value is not None or currency:
                return {"min": min_value, "max": max_value, "currency": currency}

        return UnifiedQueryAIService._extract_budget(source_text, language)

    @staticmethod
    def _extract_budget(source_text: str, language: str) -> Dict[str, Any]:
        text = UnifiedQueryAIService._strip_accents(str(source_text or "")).lower()
        text = re.sub(r"\s+", " ", text)
        currency = ""
        if any(token in text for token in {"xaf", "fcfa", "cfa"}):
            currency = "XAF"
        elif any(token in text for token in {"eur", "euro"}):
            currency = "EUR"
        elif any(token in text for token in {"usd", "$", "dollar", "dollars"}):
            currency = "USD"

        number_pattern = r"([0-9][0-9\s.,\u00a0]*)"

        range_match = re.search(
            rf"(?:between|entre|from|de)\s*{number_pattern}\s*(?:and|to|et|a|au|-\s*)\s*{number_pattern}",
            text,
        )
        if range_match:
            min_value = UnifiedQueryAIService._safe_number(range_match.group(1))
            max_value = UnifiedQueryAIService._safe_number(range_match.group(2))
            if min_value is not None and max_value is not None and min_value > max_value:
                min_value, max_value = max_value, min_value
            return {"min": min_value, "max": max_value, "currency": currency}

        max_match = re.search(
            rf"(?:under|below|less than|max(?:imum)?|up to|moins de|maximum|au plus|jusqu ?a)\s*{number_pattern}",
            text,
        )
        if max_match:
            max_value = UnifiedQueryAIService._safe_number(max_match.group(1))
            return {"min": None, "max": max_value, "currency": currency}

        min_match = re.search(
            rf"(?:over|above|more than|at least|min(?:imum)?|plus de|au moins|minimum)\s*{number_pattern}",
            text,
        )
        if min_match:
            min_value = UnifiedQueryAIService._safe_number(min_match.group(1))
            return {"min": min_value, "max": None, "currency": currency}

        if re.search(r"\b(budget|prix|price|cout|cost)\b", text):
            fallback_amounts = [
                UnifiedQueryAIService._safe_number(candidate)
                for candidate in re.findall(number_pattern, text)
            ]
            numeric_values = [
                value for value in fallback_amounts if value is not None and value > 1
            ]
            if numeric_values:
                return {
                    "min": None,
                    "max": max(numeric_values),
                    "currency": currency,
                }

        return {"min": None, "max": None, "currency": currency}

    @staticmethod
    def _safe_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        string_value = str(value).strip().replace("\u00a0", " ")
        string_value = re.sub(r"\s+", "", string_value)
        string_value = string_value.replace("'", "")
        if "," in string_value and "." not in string_value:
            integer_part, decimal_part = string_value.rsplit(",", 1)
            if len(decimal_part) == 3:
                string_value = string_value.replace(",", "")
            else:
                string_value = f"{integer_part}.{decimal_part}"
        else:
            string_value = string_value.replace(",", "")
        if not string_value:
            return None
        try:
            number = float(string_value)
        except ValueError:
            return None
        if number.is_integer():
            return float(int(number))
        return float(number)

    @staticmethod
    def _normalize_currency(value: Any) -> str:
        currency = str(value or "").strip().upper()
        if currency in {"USD", "EUR", "XAF", "GBP", "CAD"}:
            return currency
        return ""

    @staticmethod
    def _extract_negative_terms(source_text: str, language: str) -> List[str]:
        normalized = UnifiedQueryAIService._normalize_for_matching(source_text, language)
        patterns = [
            r"\bwithout\s+([a-z0-9]+)",
            r"\bno\s+([a-z0-9]+)",
            r"\bnot\s+([a-z0-9]+)",
            r"\bsans\s+([a-z0-9]+)",
            r"\bpas de\s+([a-z0-9]+)",
        ]
        negatives: List[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, normalized):
                token = match.group(1).strip()
                if not token or token in seen:
                    continue
                seen.add(token)
                negatives.append(token)
                if len(negatives) >= 6:
                    return negatives
        return negatives


