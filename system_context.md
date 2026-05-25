# Telia AI Shopping Assistant — System Context

## Stack

| Component      | Role                                                       |
|----------------|------------------------------------------------------------|
| FastAPI        | Backend API framework                                      |
| Magento 2      | Product catalog (EN + FR store views)                      |
| Typesense      | Optional fast search cache (indexes Magento products)      |
| Mistral Small  | Text LLM: spell-correction, query routing, intent parsing  |
| Pixtral Large  | Vision LLM: image and video-frame captioning               |
| AssemblyAI     | Speech-to-text for audio input                             |
| OpenCV         | Video frame extraction                                     |
| SQLite + JWT   | User auth                                                  |

---

## API Endpoints

| Route                         | Input               | Handler                              |
|-------------------------------|---------------------|--------------------------------------|
| POST /chat/recommend          | text query          | ChatService.recommend_products       |
| POST /chat/recommend/image    | image + text hint   | ChatService.recommend_products_by_image |
| POST /chat/recommend/audio    | audio file          | ChatService.recommend_products_by_audio |
| POST /chat/recommend/video    | video file          | ChatService.recommend_products_by_video |
| POST /chat/recommend/media    | any file (auto)     | ChatService.recommend_products_by_media |
| POST /chat/typesense/sync     | —                   | sync Magento → Typesense             |
| GET  /chat/typesense/status   | —                   | Typesense health check               |

---

## Core Pipeline (Text Query)

```
User message
    │
    ▼
1. Language detection       (detect_query_language — regex signal matching)
    │
    ▼
2. analyze_multimodal_query()    [mistral_decision.py]
    │   a. Spell-correct via Mistral (cached, 3s timeout)
    │   b. Abbreviation expansion (lptp→laptop, ordi→ordinateur, etc.)
    │   c. FR→EN normalization (normalize_fr_to_en — regex, NOT Mistral)
    │   d. Deterministic split (comma / slash / "and" / "et" / "ainsi que")
    │   e. Preamble stripping ("je veux un", "i want a", etc.)
    │      → returns: { use_media: bool, queries: ["q1","q2"...] }
    │
    ▼
3. Single query → _run_single_text_query()
   Multi query  → parallel _run_single_text_query() per query
    │
    ▼
4. _run_single_text_query()   [service.py]
    │   a. UnifiedQueryAIService.process_raw_query()  [Mistral JSON structured analysis]
    │      → category, keywords, attributes, budget, use_case, user_type, price_class
    │   b. Expand keywords bilingual
    │   c. Search Typesense (if configured) OR Magento API
    │   d. Rank products by term-match score
    │   e. Apply budget filter
    │
    ▼
5. Sort → cap → return ChatResponse
    - Single query:  { recommendations, groups=[] }
    - Multi query:   { recommendations (flat, deduped), groups (per query) }
```

---

## Core Pipeline (Image + Text)

```
Image upload + optional user_hint
    │
    ▼
1. Caption both EN + FR in parallel (pixtral-large, cached by image hash)
    │
    ▼
2. Extract image_intent from caption (normalized category)
    │
    ▼
3. Check "ignore image" from user_hint  ← REGEX ONLY, no AI
    │
    ▼
4. Split user_hint into text_queries  ← deterministic (same as text pipeline)
    │
    ▼
5. Build final_queries (DETERMINISTIC):
    │   if user_ignore_image:  final_queries = text_queries
    │   else:                  final_queries = [image_intent] + text_queries
    │                          (image ALWAYS first, duplicates removed)
    │
    ▼
6. Parallel _run_single_text_query() per query
    │
    ▼
7. Group results (one ProductGroup per query)
   Flat recommendations (deduped, image-group first)
    │
    ▼
8. Return ChatResponse { recommendations, caption, groups }
```

---

## analyze_multimodal_query — Decision Tree

```
Has media (image/video)?
│
├─ NO → spell-correct → split text → normalize FR→EN → return queries
│
└─ YES
    ├─ User said "ignore image" (regex) → return text-only queries
    ├─ No user text → return [caption] as single query
    ├─ Short text (≤3 words, no multi-product pattern) → single query (refinement)
    ├─ Multi-intent detected by _split_query_text → BYPASS Mistral, return splits
    └─ Single complex query → Mistral decides (JSON: use_media + queries)
```

**Critical rule:** Multi-intent is ALWAYS resolved deterministically. Mistral is only called
for single-product queries when image+text conflict resolution is needed.

---

## FR→EN Normalization (normalize_fr_to_en)

Two passes — pure Python, no AI:
1. Exact substring match (longest-match first, accent-insensitive)
2. Fuzzy single-word token match (cutoff 0.82, difflib)

Examples: `ventilateur→fan`, `ordinateur portable→laptop`, `téléphone→smartphone`

Applied: before splitting AND on each split segment individually.

---

## Grouping Rules

- Multi-intent queries produce one `ProductGroup` per query
- Each group is sorted and capped at `MAX_RECOMMENDATIONS_PER_GROUP = 20`
- Flat `recommendations` list is produced by merging groups in order, deduped
- Image group always appears first in both `groups` and flat `recommendations`
- Single-query responses: `groups = []`, only `recommendations` populated

---

## Response Schema

```json
{
  "message": "string",
  "recommendations": [ProductRecommendation],
  "caption": "string | null",
  "groups": [
    { "category": "fan", "products": [ProductRecommendation] },
    { "category": "phone", "products": [ProductRecommendation] }
  ]
}
```

`groups` is empty for single-query searches (backward-compatible).

---

## Mistral Usage (Strict Scope)

| Use case                          | Model         | When called                                      |
|-----------------------------------|---------------|--------------------------------------------------|
| Image captioning                  | pixtral-large | Every image upload (cached by image hash)        |
| Spell-correction                  | mistral-small | Before query splitting (3s timeout, cached LRU)  |
| Structured query analysis         | mistral-small | Per single query in _run_single_text_query       |
| Image+text conflict resolution    | mistral-small | Single-query + media, ambiguous refinement only  |

**Mistral is NEVER called for:**
- Query splitting (always deterministic regex)
- FR→EN normalization (always regex)
- Multi-intent routing (bypassed when >1 query detected)

---

## Caching Summary

| Cache                  | TTL      | Size | Key                                    |
|------------------------|----------|------|----------------------------------------|
| Image captions         | 5 min    | 512  | sha256(image_bytes) + language + model |
| Magento products       | 5 min    | 512  | search criteria hash                   |
| Video captions         | 5 min    | 64   | sha256(video_bytes) + language         |
| Query intent (Mistral) | LRU      | 256  | sha256(all inputs)                     |
| Spell-correction       | LRU      | 512  | language + text                        |
| UnifiedQueryAI         | LRU      | 256  | language + text                        |

---

## Key Constants (service.py)

- `MAX_RECOMMENDATIONS = 200` — global flat list cap
- `MAX_RECOMMENDATIONS_PER_GROUP = 20` — per-category cap in grouped results
- Safety cap: max 3 parallel queries (enforced in `_parse_decision_response`)

---

## File Map

| File                                  | Purpose                                          |
|---------------------------------------|--------------------------------------------------|
| app/chat/mistral_decision.py          | Query routing, splitting, FR→EN, spell-correct   |
| app/chat/unified_query_ai_service.py  | Structured query analysis via Mistral            |
| app/chat/service.py                   | ChatService, product search, ranking, grouping   |
| app/chat/image_caption.py             | Image captioning via Pixtral                     |
| app/chat/routes.py                    | FastAPI route definitions                        |
| app/chat/schemas.py                   | Pydantic models (ChatRequest, ChatResponse, etc) |
| app/config.py                         | Settings (env-based)                             |
| app/typesense_client.py               | Typesense connection                             |
| app/typesense_sync.py                 | Magento → Typesense sync                         |
| main.py                               | App entry, CORS, router registration             |
