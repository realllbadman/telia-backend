import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter, OrderedDict
from typing import Any, Dict, List, Optional

import httpx
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.chat.image_caption import ImageCaptionService
from app.chat.mistral_decision import (
    analyze_multimodal_query,
    resolve_multimodal_intent,
    normalize_fr_to_en,
    detect_query_language,
    _fast_ignore_check,
    _split_query_text,
)
from app.chat.unified_query_ai_service import UnifiedQueryAIService
from app.chat.schemas import (
    ChatResponse,
    MediaRecommendationResponse,
    ProductGroup,
    ProductRecommendation,
    VideoRecommendationResponse,
)

logger = logging.getLogger(__name__)

# Persistent Magento HTTP client — one connection pool, reused across all requests
_MAGENTO_HTTP_CLIENT: Optional[httpx.AsyncClient] = None

def _get_magento_http_client() -> httpx.AsyncClient:
    global _MAGENTO_HTTP_CLIENT
    if _MAGENTO_HTTP_CLIENT is None or _MAGENTO_HTTP_CLIENT.is_closed:
        timeout = httpx.Timeout(
            connect=settings.MAGENTO_TIMEOUT,
            read=settings.MAGENTO_TIMEOUT,
            write=settings.MAGENTO_TIMEOUT,
            pool=settings.MAGENTO_TIMEOUT,
        )
        _MAGENTO_HTTP_CLIENT = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {settings.MAGENTO_ACCESS_TOKEN}",
                "Accept": "application/json",
            },
            verify=False,
            timeout=timeout,
            trust_env=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _MAGENTO_HTTP_CLIENT


_MAGENTO_CACHE: "OrderedDict[str, tuple[float, List[Dict[str, Any]]]]" = OrderedDict()
_VIDEO_CAPTION_CACHE: "OrderedDict[str, tuple[float, str, int]]" = OrderedDict()
_VIDEO_CAPTION_CACHE_TTL_SECONDS = 300
_VIDEO_CAPTION_CACHE_MAX_ITEMS = 64

SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/x-flac",
}

SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".mp4",
    ".m4a",
    ".wav",
    ".webm",
    ".ogg",
    ".flac",
}

MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024

SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/heic",
    "image/heif",
}

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}

SUPPORTED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
}

SUPPORTED_VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
}

MAX_VIDEO_SIZE_BYTES = 100 * 1024 * 1024
VIDEO_MIN_FRAMES = 8
VIDEO_MAX_FRAMES = 24
VIDEO_TARGET_FPS = 0.5
VIDEO_AUDIO_CHANNELS = 1
VIDEO_AUDIO_SAMPLE_RATE = 16000
VIDEO_AUDIO_BITRATE = "64k"
VIDEO_AUDIO_EXTRACTION_TIMEOUT_SECONDS = 45
VIDEO_ADDITIONAL_PRODUCT_MARKERS = (
    "also visible products:",
    "produits visibles:",
)
GENERIC_WEAK_QUERY_TERMS = {
    "powerful", "puissant", "budget", "cheap", "affordable", "quality",
    "student", "etudiant", "education", "gaming", "business", "premium",
    "low", "high", "good", "best", "strong",
}
CATEGORY_PRIMARY_TERMS: Dict[str, set[str]] = {
    "laptop": {"laptop", "notebook", "ultrabook", "macbook", "thinkpad", "ideapad", "ordinateur portable"},
    "ordinateur portable": {"laptop", "notebook", "ultrabook", "macbook", "thinkpad", "ideapad", "ordinateur portable"},
    "smartphone": {"smartphone", "phone", "mobile", "android", "iphone", "telephone"},
    "telephone": {"smartphone", "phone", "mobile", "android", "iphone", "telephone"},
    "phone": {"smartphone", "phone", "mobile", "android", "iphone", "telephone"},
    "fan": {"fan", "ventilator", "air cooler", "aircooler", "ventilateur"},
    "ventilateur": {"fan", "ventilator", "air cooler", "aircooler", "ventilateur"},
    "headphones": {"headphone", "headset", "casque", "earbud", "earphone"},
    "casque": {"headphone", "headset", "casque", "earbud", "earphone"},
    "tablet": {"tablet", "tablette", "ipad"},
    "tablette": {"tablet", "tablette", "ipad"},
    "television": {"television", "tv", "smart tv", "oled", "qled"},
}
CATEGORY_CORE_QUERY_TERMS: Dict[str, List[str]] = {
    "laptop": ["laptop", "ordinateur portable", "notebook"],
    "ordinateur portable": ["ordinateur portable", "laptop", "notebook"],
    "smartphone": ["smartphone", "mobile phone", "mobile"],
    "telephone": ["telephone portable", "smartphone", "mobile"],
    "phone": ["smartphone", "mobile phone", "mobile"],
    "fan": ["fan", "ventilateur", "air cooler", "ventilator"],
    "ventilateur": ["ventilateur", "fan", "air cooler", "ventilator"],
    "headphones": ["headphone", "casque", "headset"],
    "casque": ["casque", "headphone", "headset"],
    "tablet": ["tablet", "tablette"],
    "tablette": ["tablette", "tablet"],
    "television": ["television", "tv", "smart tv"],
}
CATEGORY_EXCLUDED_TERMS: Dict[str, set[str]] = {
    "laptop": {
        "sticker", "autocollant", "backpack", "sac", "pouch", "cover", "case",
        "protector", "sleeve", "skin", "bag", "projector", "airpod", "clipper",
        "jam", "powder", "oil", "detergent", "gas cooker", "cuisiniere",
        "disk", "drive", "hard drive", "external", "speaker", "router",
        "mouse", "keyboard", "charger", "chargeur", "cable", "adapter", "adaptateur",
        "hub", "accessory", "accessories", "ssd externe", "magsafe", "power adapter",
    },
    "ordinateur portable": {
        "sticker", "autocollant", "backpack", "sac", "pouch", "cover", "case",
        "protector", "sleeve", "skin", "bag", "projector", "airpod", "clipper",
        "jam", "powder", "oil", "detergent", "gas cooker", "cuisiniere",
        "disque", "disque dur", "externe", "enceinte", "routeur",
        "souris", "clavier", "chargeur", "charger", "cable", "adaptateur", "hub",
        "accessoire", "accessoires", "magsafe",
    },
    # Prevent landlines, VoIP desk phones, and phone accessories from appearing
    "smartphone": {
        # Landlines / VoIP
        "landline", "wired", "corded", "cordless", "dect", "ip phone", "ip station",
        "ip 6102", "ip 6104", "gxp", "yealink", "grandstream", "gigaset", "sip",
        "voip", "poe", "desk phone", "filaire", "fixe", "telephone filaire",
        "telephone de bureau", "telephone fixe", "open stage",
        # Phone accessories (not the phone itself)
        "stylet", "stylus", "stylo", "pen", "pencil",
        "coque", "case", "cover", "etui", "housse", "bumper", "skin",
        "chargeur", "charger", "cable", "adaptateur", "adapter",
        "verre trempe", "screen protector", "protecteur",
        "support", "stand", "holder", "bras",
        "ecouteur", "earphone", "airpod", "earpiece",
        "batterie externe", "power bank", "powerbank",
    },
    "telephone": {
        "landline", "wired", "corded", "cordless", "dect", "ip phone", "ip station",
        "gxp", "yealink", "grandstream", "gigaset", "sip", "voip", "poe",
        "filaire", "fixe", "telephone filaire", "telephone de bureau", "open stage",
        "stylet", "stylus", "stylo", "coque", "case", "etui", "housse",
        "chargeur", "charger", "cable", "verre trempe", "screen protector",
        "batterie externe", "power bank", "ecouteur", "airpod",
    },
}
MAX_RECOMMENDATIONS = 200
MAX_RECOMMENDATIONS_PER_GROUP = 20   # cap per category in grouped multi-intent results
CATALOG_FALLBACK_PAGE_SIZE = 40
PRODUCT_CAPTION_MAX_WORDS = 15
PRODUCT_SEARCH_ATTRIBUTE_CODES = {
    "brand",
    "color",
    "description",
    "feature",
    "features",
    "manufacturer",
    "material",
    "memory",
    "meta_description",
    "meta_keyword",
    "meta_title",
    "model",
    "processor",
    "ram",
    "screen_size",
    "series",
    "short_description",
    "size",
    "storage",
    "style",
    "type",
    "warranty",
}
PRODUCT_CATEGORY_HINTS: Dict[str, set[str]] = {
    "laptop": {"laptop", "notebook", "ultrabook", "ordinateur portable", "macbook"},
    "phone": {"phone", "smartphone", "mobile", "iphone", "telephone", "android"},
    "fan": {"fan", "ventilator", "ventilateur", "air cooler", "aircooler"},
    "tablet": {"tablet", "ipad", "tablette"},
    "headphones": {"headphone", "headphones", "earbud", "earbuds", "headset", "casque"},
    "television": {"tv", "television", "smart tv", "oled", "qled"},
}
PRODUCT_CAPTION_BENEFITS = {
    "en": {
        "laptop": "for smooth work and study",
        "phone": "for fast daily use",
        "fan": "for cooler rooms fast",
        "tablet": "for portable everyday entertainment",
        "headphones": "for clear everyday audio",
        "television": "for immersive home viewing",
    },
    "fr": {
        "laptop": "pour travail et etudes fluides",
        "phone": "pour un usage quotidien fluide",
        "fan": "pour rafraichir la piece vite",
        "tablet": "pour le divertissement partout",
        "headphones": "pour un son clair au quotidien",
        "television": "pour une image immersive a la maison",
    },
}

# ------------------------
# Helpers
# ------------------------

def _flatten_search_criteria(prefix: str, obj: Any, out: Dict[str, Any]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten_search_criteria(f"{prefix}[{k}]", v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten_search_criteria(f"{prefix}[{i}]", v, out)
    else:
        out[prefix] = obj


def _build_magento_media_url(path: str) -> Optional[str]:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    media_base = settings.MAGENTO_MEDIA_BASE_URL or settings.MAGENTO_BASE_URL
    if not media_base:
        return None
    normalized = path.strip()
    if not normalized:
        return None
    normalized = normalized if normalized.startswith("/") else f"/{normalized}"
    media_prefix = "/media/catalog/product/"
    if normalized.lower().startswith(media_prefix):
        normalized = "/" + normalized[len(media_prefix):]
    if settings.MAGENTO_MEDIA_BASE_URL:
        return f"{media_base.rstrip('/')}{normalized}"
    return f"{media_base.rstrip('/')}/media/catalog/product{normalized}"


def _extract_image_url(product: Dict[str, Any]) -> Optional[str]:
    direct_image_url = str(product.get("image_url") or "").strip()
    if direct_image_url:
        return _build_magento_media_url(direct_image_url)

    media_entries = product.get("media_gallery_entries") or []
    if isinstance(media_entries, list):
        for entry in media_entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("disabled"):
                continue
            if (entry.get("media_type") or "").lower() not in {"image", ""}:
                continue
            file_path = str(entry.get("file") or "").strip()
            url = _build_magento_media_url(file_path)
            if url:
                return url

    custom_attributes = product.get("custom_attributes") or []
    if isinstance(custom_attributes, list):
        for entry in custom_attributes:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get("attribute_code") or "").lower()
            if code not in {"image", "small_image", "thumbnail"}:
                continue
            value = str(entry.get("value") or "").strip()
            if not value or value == "no_selection":
                continue
            url = _build_magento_media_url(value)
            if url:
                return url
    elif isinstance(custom_attributes, dict):
        for code in ("image", "small_image", "thumbnail"):
            value = str(custom_attributes.get(code) or "").strip()
            if not value or value == "no_selection":
                continue
            url = _build_magento_media_url(value)
            if url:
                return url

    for code in ("image", "small_image", "thumbnail"):
        direct_image = str(product.get(code) or "").strip()
        if direct_image and direct_image != "no_selection":
            return _build_magento_media_url(direct_image)

    return None


def _limit_words(text: str, max_words: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip(" ,.;"))
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned
    return " ".join(words[:max_words]).strip(" ,.;")


def _iter_custom_attribute_pairs(product: Dict[str, Any]):
    custom_attributes = product.get("custom_attributes") or []
    if isinstance(custom_attributes, list):
        for entry in custom_attributes:
            if not isinstance(entry, dict):
                continue
            yield str(entry.get("attribute_code") or "").lower(), entry.get("value")
        return

    if isinstance(custom_attributes, dict):
        for code, value in custom_attributes.items():
            yield str(code or "").lower(), value


def _collect_product_text_fields(product: Dict[str, Any], name: str) -> List[str]:
    text_parts = [name, str(product.get("sku") or "").strip()]

    direct_description = product.get("description")
    if direct_description is not None:
        text_parts.append(str(direct_description))

    for code, value in _iter_custom_attribute_pairs(product):
        if code not in PRODUCT_SEARCH_ATTRIBUTE_CODES:
            continue
        string_value = re.sub(r"\s+", " ", str(value or "").strip())
        if not string_value:
            continue
        text_parts.append(string_value)

    return text_parts


def _extract_product_category_key(product: Dict[str, Any], name: str) -> str:
    haystack = _extract_search_haystack(product, name)
    if not haystack:
        return ""

    for category, hints in PRODUCT_CATEGORY_HINTS.items():
        if any(term in haystack for term in hints):
            return category
    return ""


def _extract_product_spec_fragments(text: str) -> List[str]:
    patterns = [
        r"\b\d+(?:\.\d+)?\s?(?:gb|tb)\s?(?:ram|rom|ssd|hdd)?\b",
        r"\b\d+(?:\.\d+)?\s?(?:mp|mah|w|hz)\b",
        r"\b\d+(?:\.\d+)?\s?(?:inch|in)\b",
        r"\b\d+(?:\.\d+)?\"",
        r"\b(?:ssd|hdd|fhd|4k|oled|qled|wifi|bluetooth)\b",
        r"\b(?:black|white|silver|gray|grey|blue|red|green|argent|gris|blanc|noir|bleu|rouge|vert)\b",
    ]
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return []

    found: List[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, flags=re.IGNORECASE):
            fragment = re.sub(r"\s+", " ", match.group(0).strip(" ,.;"))
            normalized = fragment.lower()
            if not fragment or normalized in seen:
                continue
            seen.add(normalized)
            found.append(fragment)
            if len(found) >= 3:
                return found
    return found


def _build_product_caption(product: Dict[str, Any], name: str, language: str) -> str:
    language = _validate_language(language)
    cleaned_name = re.sub(r"\s+", " ", str(name or "").replace(" - ", " ").strip(" ,.;"))
    if not cleaned_name:
        return ""

    name_words = cleaned_name.split()
    anchor = _limit_words(" ".join(name_words[:6]), 6)
    text_signal = " ".join(_collect_product_text_fields(product, name))
    specs = _extract_product_spec_fragments(text_signal)
    category_key = _extract_product_category_key(product, name)
    benefit = PRODUCT_CAPTION_BENEFITS.get(language, {}).get(category_key, "")

    parts = [anchor]
    parts.extend(specs[:2])
    if benefit:
        parts.append(benefit)

    caption = ", ".join(part for part in parts if part)
    return _limit_words(caption, PRODUCT_CAPTION_MAX_WORDS)


def _build_media_caption_cache_key(media_bytes: bytes, language: str) -> str:
    digest = hashlib.sha256(media_bytes).hexdigest()
    return f"{language}:{digest}"


def _video_caption_cache_get(cache_key: str) -> Optional[tuple[str, int]]:
    if _VIDEO_CAPTION_CACHE_TTL_SECONDS <= 0:
        return None
    cached = _VIDEO_CAPTION_CACHE.get(cache_key)
    if not cached:
        return None
    timestamp, caption, frames_used = cached
    if (time.monotonic() - timestamp) > _VIDEO_CAPTION_CACHE_TTL_SECONDS:
        _VIDEO_CAPTION_CACHE.pop(cache_key, None)
        return None
    _VIDEO_CAPTION_CACHE.move_to_end(cache_key)
    return caption, frames_used


def _video_caption_cache_set(cache_key: str, caption: str, frames_used: int) -> None:
    if _VIDEO_CAPTION_CACHE_TTL_SECONDS <= 0:
        return
    _VIDEO_CAPTION_CACHE[cache_key] = (time.monotonic(), caption, frames_used)
    _VIDEO_CAPTION_CACHE.move_to_end(cache_key)
    while len(_VIDEO_CAPTION_CACHE) > _VIDEO_CAPTION_CACHE_MAX_ITEMS:
        _VIDEO_CAPTION_CACHE.popitem(last=False)


def _extract_product_data(product: Dict[str, Any], language: str = "en") -> Optional[Dict[str, Any]]:
    try:
        prod_id = product.get("id")
        sku = str(product.get("sku") or "").strip()
        name = str(product.get("name") or "").strip()
        price = float(product.get("price") or 0)
    except Exception:
        return None

    if not prod_id or not sku or not name:
        return None

    image_url = _extract_image_url(product)
    caption = _build_product_caption(product, name, language)
    return {
        "id": str(prod_id),
        "name": name,
        "sku": sku,
        "price": price,
        "image": image_url,
        "image_url": image_url,
        "caption": caption or None,
    }


def _is_image_quality_poor(image: UploadFile, image_bytes: bytes) -> Optional[str]:
    if not image_bytes or len(image_bytes) < 3_000:
        return "The image is too small or blurry. Please upload a clearer photo."

    if not image.content_type or not image.content_type.startswith("image/"):
        return "The uploaded file is not a valid image."

    return None


def _validate_language(language: str) -> str:
    normalized = language.strip().lower()
    if normalized not in {"en", "fr"}:
        raise HTTPException(
            status_code=422,
            detail="language must be one of: en, fr",
        )
    return normalized


def _detect_upload_type(upload: UploadFile) -> str:
    filename = (upload.filename or "").strip().lower()
    extension = os.path.splitext(filename)[1]
    content_type = (upload.content_type or "").strip().lower()

    if (
        content_type in SUPPORTED_IMAGE_MIME_TYPES
        or content_type.startswith("image/")
        or extension in SUPPORTED_IMAGE_EXTENSIONS
    ):
        return "image"

    if (
        content_type in SUPPORTED_VIDEO_MIME_TYPES
        or content_type.startswith("video/")
        or extension in SUPPORTED_VIDEO_EXTENSIONS
    ):
        return "video"

    if (
        content_type in SUPPORTED_AUDIO_MIME_TYPES
        or content_type.startswith("audio/")
        or extension in SUPPORTED_AUDIO_EXTENSIONS
    ):
        return "audio"

    return "unknown"


def _validate_audio_upload(audio: UploadFile, audio_bytes: bytes) -> None:
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Audio file is too large. Maximum supported size is 25 MB",
        )

    filename = (audio.filename or "").strip()
    extension = os.path.splitext(filename)[1].lower() if filename else ""
    content_type = (audio.content_type or "").lower()

    is_supported_extension = extension in SUPPORTED_AUDIO_EXTENSIONS
    is_supported_content_type = (
        content_type in SUPPORTED_AUDIO_MIME_TYPES
        or content_type.startswith("audio/")
    )

    if not (is_supported_extension or is_supported_content_type):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported audio format. Supported: mp3, mp4, m4a, wav, webm, ogg, flac"
            ),
        )


def _validate_video_upload(video: UploadFile, video_bytes: bytes) -> str:
    if not video_bytes:
        raise HTTPException(status_code=400, detail="Uploaded video file is empty")

    if len(video_bytes) > MAX_VIDEO_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Video file is too large. Maximum supported size is 100 MB",
        )

    filename = (video.filename or "").strip()
    extension = os.path.splitext(filename)[1].lower() if filename else ""
    content_type = (video.content_type or "").lower()

    is_supported_extension = extension in SUPPORTED_VIDEO_EXTENSIONS
    is_supported_content_type = (
        content_type in SUPPORTED_VIDEO_MIME_TYPES
        or content_type.startswith("video/")
    )

    if not (is_supported_extension or is_supported_content_type):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported video format. Supported: mp4, mov, avi, mkv, webm, m4v, mpeg, mpg"
            ),
        )

    return extension or ".mp4"


def _save_temp_video_file(video_bytes: bytes, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(video_bytes)
        return tmp_file.name


def _compute_target_video_frames(duration_seconds: float) -> int:
    if duration_seconds <= 0:
        return VIDEO_MIN_FRAMES

    target = int(round(duration_seconds * VIDEO_TARGET_FPS))
    return max(VIDEO_MIN_FRAMES, min(VIDEO_MAX_FRAMES, target))


def _extract_additional_products_from_caption(caption: str) -> List[str]:
    if not caption:
        return []

    lowered = caption.lower()
    marker_index = -1
    marker_len = 0
    for marker in VIDEO_ADDITIONAL_PRODUCT_MARKERS:
        idx = lowered.find(marker)
        if idx == -1:
            continue
        if marker_index == -1 or idx < marker_index:
            marker_index = idx
            marker_len = len(marker)

    if marker_index == -1:
        return []

    tail = caption[marker_index + marker_len:]
    parts = [re.sub(r"\s+", " ", p).strip(" ,.;") for p in re.split(r"[;,]", tail)]
    products: List[str] = []
    seen: set[str] = set()
    for value in parts:
        if not value:
            continue
        if value in {"none", "n a", "n/a", "aucun", "aucune"}:
            continue
        if value in seen:
            continue
        seen.add(value)
        products.append(value)
    return products[:6]


def _strip_additional_products_from_caption(caption: str) -> str:
    if not caption:
        return ""

    lowered = caption.lower()
    marker_index = -1
    for marker in VIDEO_ADDITIONAL_PRODUCT_MARKERS:
        idx = lowered.find(marker)
        if idx == -1:
            continue
        if marker_index == -1 or idx < marker_index:
            marker_index = idx

    primary = caption if marker_index == -1 else caption[:marker_index]
    return re.sub(r"\s+", " ", primary).strip(" ,.;")


def extract_frames_from_video(
    video_path: str,
    max_frames: int = VIDEO_MAX_FRAMES,
) -> List[bytes]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for video recommendations. Install opencv-python-headless."
        ) from exc

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError("Uploaded video could not be opened")

    frame_bytes: List[bytes] = []

    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 30.0

        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_seconds = (total_frames / fps) if total_frames > 0 else 0.0
        target_frames = min(max_frames, _compute_target_video_frames(duration_seconds))

        if total_frames > 0:
            target_frames = max(1, min(target_frames, total_frames))
            if target_frames == 1:
                frame_positions = [0]
            else:
                frame_positions = [
                    int(round(i * (total_frames - 1) / (target_frames - 1)))
                    for i in range(target_frames)
                ]

            for position in frame_positions:
                capture.set(cv2.CAP_PROP_POS_FRAMES, position)
                ok, frame = capture.read()
                if not ok:
                    continue

                encoded_ok, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 85],
                )
                if encoded_ok:
                    frame_bytes.append(encoded.tobytes())

        if not frame_bytes:
            # Fallback for containers where frame seeking metadata is missing.
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_step = max(1, int(round(fps * 2.0)))
            frame_index = 0
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                if frame_index % frame_step == 0:
                    encoded_ok, encoded = cv2.imencode(
                        ".jpg",
                        frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 85],
                    )
                    if encoded_ok:
                        frame_bytes.append(encoded.tobytes())
                    if len(frame_bytes) >= target_frames:
                        break
                frame_index += 1
    finally:
        capture.release()

    return frame_bytes


def merge_captions(captions: List[str], language: str = "en") -> str:
    cleaned_original = [
        re.sub(r"\s+", " ", str(caption or "").strip())
        for caption in captions
        if str(caption or "").strip()
    ]
    if not cleaned_original:
        return ""

    cleaned_primary: List[str] = []
    for caption in cleaned_original:
        primary_caption = _strip_additional_products_from_caption(caption)
        if primary_caption:
            cleaned_primary.append(primary_caption)
    if not cleaned_primary:
        return ""

    # Normalize captions so near-duplicates collapse into one canonical phrase.
    normalized_pairs = [
        (_normalize_text_for_keyword_matching(caption), caption)
        for caption in cleaned_primary
    ]
    frequency = Counter(normalized for normalized, _ in normalized_pairs if normalized)

    canonical_caption: Dict[str, str] = {}
    for normalized, original in normalized_pairs:
        if normalized and normalized not in canonical_caption:
            canonical_caption[normalized] = original

    ranked = sorted(
        canonical_caption.keys(),
        key=lambda normalized: (-frequency.get(normalized, 0), -len(normalized)),
    )
    merged_main = " ".join(canonical_caption[key] for key in ranked[:4]).strip()
    merged_main = re.sub(r"\s+", " ", merged_main)

    additional_counter: Counter[str] = Counter()
    additional_canonical: Dict[str, str] = {}
    for caption in cleaned_original:
        for item in _extract_additional_products_from_caption(caption):
            normalized_item = _normalize_text_for_keyword_matching(item)
            if not normalized_item:
                continue
            additional_counter[normalized_item] += 1
            additional_canonical.setdefault(normalized_item, item)

    if not additional_counter:
        return merged_main

    ranked_additional = sorted(
        additional_counter.keys(),
        key=lambda normalized: (-additional_counter[normalized], -len(normalized)),
    )
    normalized_merged_main = _normalize_text_for_keyword_matching(merged_main)
    additional_items = [
        additional_canonical[key]
        for key in ranked_additional
        if key not in normalized_merged_main
    ][:4]

    if not additional_items:
        return merged_main

    if language == "fr":
        return f"{merged_main} Produits visibles: {', '.join(additional_items)}".strip()

    return f"{merged_main} Also visible products: {', '.join(additional_items)}".strip()


def _extract_audio_from_video(video_path: str) -> Optional[bytes]:
    ffmpeg_executable = shutil.which("ffmpeg")
    if not ffmpeg_executable:
        logger.info("ffmpeg is not available; skipping video audio extraction")
        return None

    command = [
        ffmpeg_executable,
        "-v",
        "error",
        "-i",
        video_path,
        "-vn",
        "-ac",
        str(VIDEO_AUDIO_CHANNELS),
        "-ar",
        str(VIDEO_AUDIO_SAMPLE_RATE),
        "-b:a",
        VIDEO_AUDIO_BITRATE,
        "-f",
        "mp3",
        "pipe:1",
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=VIDEO_AUDIO_EXTRACTION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Video audio extraction timed out")
        return None
    except Exception as exc:
        logger.warning("Video audio extraction failed before ffmpeg completion: %s", exc)
        return None

    if completed.returncode != 0 or not completed.stdout:
        stderr_text = completed.stderr.decode("utf-8", errors="ignore").lower()
        no_audio_markers = (
            "does not contain any stream",
            "matches no streams",
            "stream map",
            "output file #0 does not contain any stream",
        )
        if any(marker in stderr_text for marker in no_audio_markers):
            return None

        logger.warning(
            "ffmpeg audio extraction failed (exit=%s): %s",
            completed.returncode,
            stderr_text[:300],
        )
        return None

    return completed.stdout


def _build_audio_caption_from_transcript(transcript: str, language: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(transcript or "").strip())
    if not cleaned:
        return ""

    keywords = _extract_keywords(cleaned, language)
    if not keywords:
        return cleaned[:240]

    terms = ", ".join(keywords[:8])
    if language == "fr":
        return f"Intention audio: {terms}"
    return f"Audio intent: {terms}"


def _build_multimodal_video_query(
    visual_caption: str,
    audio_caption: Optional[str],
    language: str,
) -> Dict[str, Any]:
    visual_keywords = _extract_keywords(visual_caption, language)
    audio_keywords = _extract_keywords(audio_caption or "", language)

    audio_set = set(audio_keywords)
    shared_keywords = [kw for kw in visual_keywords if kw in audio_set]

    if shared_keywords:
        search_keywords = shared_keywords[:8]
    else:
        search_keywords: List[str] = []
        seen: set[str] = set()
        for keyword in visual_keywords + audio_keywords:
            if keyword in seen:
                continue
            seen.add(keyword)
            search_keywords.append(keyword)
            if len(search_keywords) >= 8:
                break

    if not search_keywords:
        search_keywords = visual_keywords[:8]

    if not audio_caption:
        return {
            "search_caption": visual_caption,
            "search_keywords": search_keywords,
            "shared_keywords": [],
        }

    if shared_keywords:
        if language == "fr":
            search_caption = (
                f"{visual_caption} Indice audio: {audio_caption}. "
                f"Correspondances audio-video: {', '.join(shared_keywords[:6])}"
            )
        else:
            search_caption = (
                f"{visual_caption} Audio cue: {audio_caption}. "
                f"Audio-video matches: {', '.join(shared_keywords[:6])}"
            )
    else:
        if language == "fr":
            search_caption = f"{visual_caption} Indice audio: {audio_caption}"
        else:
            search_caption = f"{visual_caption} Audio cue: {audio_caption}"

    return {
        "search_caption": re.sub(r"\s+", " ", search_caption).strip(),
        "search_keywords": search_keywords,
        "shared_keywords": shared_keywords[:8],
    }


async def _upload_audio_to_assemblyai(audio_bytes: bytes) -> str:
    if not settings.ASSEMBLYAI_API_KEY:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not configured")

    headers = {
        "Authorization": settings.ASSEMBLYAI_API_KEY,
        "Content-Type": "application/octet-stream",
    }
    timeout = httpx.Timeout(connect=15.0, read=90.0, write=90.0, pool=30.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                content=audio_bytes,
            )
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach AssemblyAI upload endpoint") from exc

    if resp.status_code >= 400:
        logger.error("AssemblyAI upload failed: %s - %s", resp.status_code, resp.text)
        raise RuntimeError("Audio upload to AssemblyAI failed")

    try:
        payload = resp.json()
    except ValueError as exc:
        raise RuntimeError("Invalid response from AssemblyAI upload endpoint") from exc

    upload_url = str(payload.get("upload_url") or "").strip()
    if not upload_url:
        raise RuntimeError("AssemblyAI upload response did not include upload_url")
    return upload_url


async def _start_assemblyai_transcription(upload_url: str, language: str) -> str:
    headers = {
        "Authorization": settings.ASSEMBLYAI_API_KEY,
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(connect=15.0, read=60.0, write=60.0, pool=30.0)
    speech_models = [
        model.strip()
        for model in settings.ASSEMBLYAI_SPEECH_MODELS.split(",")
        if model.strip()
    ]
    if not speech_models:
        speech_models = ["universal-2"]

    language_map = {
        "en": "en_us",
        "fr": "fr",
    }
    payload: Dict[str, Any] = {
        "audio_url": upload_url,
        "speech_models": speech_models,
    }
    language_code = language_map.get(language)
    if language_code:
        payload["language_code"] = language_code
    else:
        payload["language_detection"] = True

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.assemblyai.com/v2/transcript",
                headers=headers,
                json=payload,
            )
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach AssemblyAI transcription endpoint") from exc

    if resp.status_code >= 400:
        logger.error(
            "AssemblyAI transcript creation failed: %s - %s",
            resp.status_code,
            resp.text,
        )
        api_error = ""
        try:
            api_error = str(resp.json().get("error") or "").strip()
        except ValueError:
            api_error = ""
        if api_error:
            raise RuntimeError(f"AssemblyAI transcription request failed: {api_error}")
        raise RuntimeError("AssemblyAI transcription request failed")

    try:
        body = resp.json()
    except ValueError as exc:
        raise RuntimeError("Invalid response from AssemblyAI transcription endpoint") from exc

    transcript_id = str(body.get("id") or "").strip()
    if not transcript_id:
        raise RuntimeError("AssemblyAI transcription response did not include id")
    return transcript_id


async def _poll_assemblyai_transcript(transcript_id: str) -> str:
    headers = {
        "Authorization": settings.ASSEMBLYAI_API_KEY,
    }
    timeout = httpx.Timeout(connect=15.0, read=60.0, write=60.0, pool=30.0)
    poll_interval = max(0.5, float(settings.ASSEMBLYAI_POLL_INTERVAL_SECONDS))
    poll_timeout = max(30, int(settings.ASSEMBLYAI_POLL_TIMEOUT_SECONDS))
    endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"

    async def _poll_once(client: httpx.AsyncClient) -> str:
        while True:
            try:
                resp = await client.get(endpoint, headers=headers)
            except httpx.RequestError as exc:
                raise RuntimeError("Could not poll AssemblyAI transcription status") from exc

            if resp.status_code >= 400:
                logger.error(
                    "AssemblyAI transcript polling failed: %s - %s",
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError("AssemblyAI transcript polling failed")

            try:
                payload = resp.json()
            except ValueError as exc:
                raise RuntimeError("Invalid response while polling AssemblyAI transcript") from exc

            status = str(payload.get("status") or "").lower()
            if status == "completed":
                text = str(payload.get("text") or "").strip()
                if not text:
                    raise RuntimeError("No speech detected in the audio")
                return text
            if status == "error":
                api_error = str(payload.get("error") or "").strip()
                raise RuntimeError(api_error or "AssemblyAI transcription failed")
            if status not in {"queued", "processing"}:
                raise RuntimeError(f"Unexpected AssemblyAI transcription status: {status}")

            await asyncio.sleep(poll_interval)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await asyncio.wait_for(_poll_once(client), timeout=poll_timeout)
    except asyncio.TimeoutError as exc:
        raise RuntimeError("Timed out waiting for AssemblyAI transcription") from exc


async def _transcribe_audio_with_assemblyai(
    audio_bytes: bytes,
    language: str,
) -> str:
    upload_url = await _upload_audio_to_assemblyai(audio_bytes=audio_bytes)
    transcript_id = await _start_assemblyai_transcription(
        upload_url=upload_url,
        language=language,
    )
    return await _poll_assemblyai_transcript(transcript_id=transcript_id)


def _extract_keywords(text: str, language: str) -> List[str]:
    normalized_text = _normalize_text_for_keyword_matching(text)
    if not normalized_text:
        return []

    stopwords_en = {
        "the", "a", "an", "with", "and", "or", "in", "on", "for", "of",
        "this", "that", "is", "are", "to", "from", "as", "at", "it",
        "i", "me", "my", "mine", "you", "your", "want", "need", "looking",
        "please", "show", "find", "get", "give", "something", "some",
        "uh", "um", "hmm", "like", "just", "kind", "sort", "thing",
        "product", "products", "item", "items", "photo", "image", "picture",
        "person", "wearing", "background",
    }

    stopwords_fr = {
        "le", "la", "les", "un", "une", "des", "de", "du", "d",
        "que", "qui", "avec", "pour", "sur", "et", "dans", "au", "aux",
        "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
        "veux", "voudrais", "besoin", "cherche", "montre", "trouve",
        "svp", "stp", "euh", "heu", "hum", "genre", "juste", "truc",
        "produit", "produits", "article", "articles", "photo", "image",
        "personne", "arriere",
    }

    stopwords = stopwords_fr if language == "fr" else stopwords_en

    words = normalized_text.split()
    keywords = []
    for word in words:
        if word in stopwords:
            continue
        normalized_word = _normalize_keyword_token(word, language=language)
        if len(normalized_word) <= 2 or normalized_word in stopwords:
            continue
        keywords.append(normalized_word)

    seen = set()
    result = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            result.append(w)

    return result[:8]


def _compact_caption_for_search(caption: str, language: str) -> str:
    if not caption:
        return ""
    primary = _strip_additional_products_from_caption(caption)
    normalized = _normalize_text_for_keyword_matching(primary)
    if not normalized:
        return ""
    keywords = _extract_keywords(primary, language)
    if len(keywords) < 10:
        short_stopwords = {
            "an", "of", "to", "in", "on", "at", "by", "or",
            "et", "de", "du", "la", "le", "les", "un", "une", "des", "au", "aux",
        }
        for token in normalized.split():
            if len(token) != 2:
                continue
            if token in short_stopwords:
                continue
            if token not in keywords:
                keywords.append(token)
            if len(keywords) >= 10:
                break
    return " ".join(keywords[:10])


def _is_complex_query(input_text: str, language: str) -> bool:
    if not input_text:
        return False
    normalized = _normalize_text_for_keyword_matching(input_text)
    if not normalized:
        return False
    tokens = normalized.split()
    if len(tokens) >= 4:
        return True

    lowered = input_text.lower()
    if re.search(r"(\d+\s*(fcfa|xaf|usd|eur|ngn|ksh|usd|gbp|€|\$|£))", lowered):
        return True
    if re.search(r"[<>]=?|\b\d+\s*-\s*\d+\b", lowered):
        return True

    comparison_terms_en = {"vs", "versus", "compare", "better", "best", "than"}
    comparison_terms_fr = {"vs", "versus", "compar", "meilleur", "meilleure"}
    price_terms_en = {"budget", "cheap", "cheapest", "under", "below", "less", "over", "more", "between", "range", "max", "min"}
    price_terms_fr = {"budget", "pas", "cher", "moins", "plus", "entre", "autour", "maximum", "minimum"}

    token_set = set(tokens)
    if language == "fr":
        if token_set.intersection(comparison_terms_fr):
            return True
        if token_set.intersection(price_terms_fr) and re.search(r"\d", lowered):
            return True
    else:
        if token_set.intersection(comparison_terms_en):
            return True
        if token_set.intersection(price_terms_en) and re.search(r"\d", lowered):
            return True

    return False


def _normalize_text_for_keyword_matching(text: str) -> str:
    value = str(text or "")
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = without_accents.lower()
    alnum = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", alnum).strip()


def _normalize_keyword_token(token: str, language: str) -> str:
    normalized = token.strip()
    if len(normalized) <= 3:
        return normalized

    if language == "en":
        if normalized.endswith("ies") and len(normalized) > 4:
            return normalized[:-3] + "y"
        if normalized.endswith("es") and len(normalized) > 4:
            return normalized[:-2]
        if normalized.endswith("s") and len(normalized) > 3:
            return normalized[:-1]
    else:
        if normalized.endswith("es") and len(normalized) > 4:
            return normalized[:-2]
        if normalized.endswith("s") and len(normalized) > 3:
            return normalized[:-1]

    return normalized


def _extract_search_haystack(product: Dict[str, Any], name: str) -> str:
    combined = " ".join(_collect_product_text_fields(product, name))
    # Magento descriptions are often HTML; strip tags before keyword matching.
    without_html = re.sub(r"<[^>]+>", " ", combined)
    return _normalize_text_for_keyword_matching(without_html)


def _normalize_list_of_terms(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    result: List[str] = []
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value or "").strip())
        if normalized:
            result.append(normalized)
    return result


def _build_semantic_query_text(structured_query: Dict[str, Any]) -> str:
    parts: List[str] = []

    category = re.sub(r"\s+", " ", str(structured_query.get("category") or "").strip())
    use_case = re.sub(r"\s+", " ", str(structured_query.get("use_case") or "").strip())
    user_type = re.sub(r"\s+", " ", str(structured_query.get("user_type") or "").strip())
    price_class = re.sub(r"\s+", " ", str(structured_query.get("price_class") or "").strip())

    if category:
        parts.append(category)
    if use_case:
        parts.append(use_case)
    if user_type:
        parts.append(user_type)
    if price_class:
        parts.append(price_class)

    for field in ("attributes", "priority_terms", "keywords"):
        values = _normalize_list_of_terms(structured_query.get(field))
        if values:
            parts.append(" ".join(values))

    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _build_keywords_from_structured_query(
    structured_query: Dict[str, Any],
    language: str,
) -> List[str]:
    candidates: List[str] = []
    for field in ("priority_terms", "keywords", "attributes"):
        candidates.extend(_normalize_list_of_terms(structured_query.get(field)))

    category = str(structured_query.get("category") or "").strip()
    use_case = str(structured_query.get("use_case") or "").strip()
    user_type = str(structured_query.get("user_type") or "").strip()
    price_class = str(structured_query.get("price_class") or "").strip()
    if category:
        candidates.append(category)
    if use_case:
        candidates.append(use_case)
    if user_type:
        candidates.append(user_type)
    if price_class:
        candidates.append(price_class)

    merged_candidates = " ".join(candidates).strip()
    return _extract_keywords(merged_candidates, language) if merged_candidates else []


def _extract_budget_range(structured_query: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    budget = structured_query.get("budget")

    def _to_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        s = str(value).replace(",", "").replace(" ", "").strip()
        if not s or s.lower() in {"null", "none", ""}:
            return None
        try:
            return float(s)
        except (TypeError, ValueError):
            return None

    # Mistral may return budget as a plain number, or as {min, max} dict
    if isinstance(budget, (int, float)):
        return None, float(budget)

    if not isinstance(budget, dict):
        return None, None

    min_budget = _to_number(budget.get("min"))
    max_budget = _to_number(budget.get("max"))

    # Sanity check: swap if inverted
    if min_budget is not None and max_budget is not None and min_budget > max_budget:
        min_budget, max_budget = max_budget, min_budget

    # If only min provided and it's a typical "de X" shopping budget, treat as max
    if min_budget is not None and max_budget is None and min_budget > 1000:
        # "je veux un laptop de 200000" — "de" means budget ceiling not floor
        # But "I want a laptop over 200000" means min. We trust Mistral's assignment here.
        pass

    return min_budget, max_budget


def _apply_budget_filter(
    recommendations: List[ProductRecommendation],
    structured_query: Dict[str, Any],
) -> List[ProductRecommendation]:
    min_budget, max_budget = _extract_budget_range(structured_query)
    if min_budget is None and max_budget is None:
        return recommendations

    filtered: List[ProductRecommendation] = []
    for product in recommendations:
        if min_budget is not None and product.price < min_budget:
            continue
        if max_budget is not None and product.price > max_budget:
            continue
        filtered.append(product)

    # If budget filter removes everything (e.g. catalog has no products under that price),
    # return the original list sorted by closest price rather than nothing.
    if not filtered and recommendations:
        target = max_budget or min_budget or 0
        return sorted(recommendations, key=lambda r: abs((r.price or 0) - target))

    return filtered


def _to_normalized_tokens(value: str) -> List[str]:
    normalized = _normalize_text_for_keyword_matching(value)
    if not normalized:
        return []
    return [token for token in normalized.split() if len(token) > 1]


def _compute_term_match_score(
    term: str,
    haystack: str,
    haystack_tokens: set[str],
) -> float:
    normalized_term = _normalize_text_for_keyword_matching(term)
    if not normalized_term:
        return 0.0

    term_tokens = [token for token in normalized_term.split() if token]
    if not term_tokens:
        return 0.0

    if len(term_tokens) == 1:
        # Single-word term: require an exact whole-word match to avoid
        # "fan" matching inside "enfants", "elephant", "infant", etc.
        token = term_tokens[0]
        if token in haystack_tokens:
            return 1.0
        # Allow prefix match for longer tokens (e.g. "samsung" matches "samsung123")
        if len(token) >= 4 and any(
            candidate.startswith(token) or token.startswith(candidate)
            for candidate in haystack_tokens
        ):
            return 0.7
        return 0.0

    # Multi-word phrase: substring match is fine ("air cooler" in haystack)
    if normalized_term in haystack:
        return 1.0

    matched = 0.0
    for token in term_tokens:
        if token in haystack_tokens:
            matched += 1.0
            continue
        if len(token) >= 4 and any(
            candidate.startswith(token) or token.startswith(candidate)
            for candidate in haystack_tokens
        ):
            matched += 0.7

    score = matched / len(term_tokens)
    if score < 0.5:
        return 0.0
    return round(score, 3)


def _build_search_profile(
    structured_query: Dict[str, Any],
    keywords: List[str],
) -> Dict[str, Any]:
    category_value = str(structured_query.get("category") or "").strip()
    normalized_category = _normalize_text_for_keyword_matching(category_value)

    primary_terms = set(
        CATEGORY_PRIMARY_TERMS.get(normalized_category, set())
    )
    if not primary_terms and normalized_category:
        primary_terms.update(_to_normalized_tokens(normalized_category))

    excluded_terms = set(CATEGORY_EXCLUDED_TERMS.get(normalized_category, set()))

    negative_terms = set()
    for term in _normalize_list_of_terms(structured_query.get("negative_terms")):
        normalized_term = _normalize_text_for_keyword_matching(term)
        if normalized_term:
            negative_terms.add(normalized_term)

    strong_terms = set()
    for term in keywords:
        normalized_term = _normalize_text_for_keyword_matching(term)
        if not normalized_term:
            continue
        if normalized_term in GENERIC_WEAK_QUERY_TERMS:
            continue
        strong_terms.add(normalized_term)

    context_terms = set()
    for field in ("use_case", "user_type", "price_class"):
        normalized_term = _normalize_text_for_keyword_matching(
            str(structured_query.get(field) or "")
        )
        if normalized_term and normalized_term not in GENERIC_WEAK_QUERY_TERMS:
            context_terms.add(normalized_term)

    priority_terms = []
    seen_priority: set[str] = set()
    for term in _normalize_list_of_terms(structured_query.get("priority_terms")):
        normalized_term = _normalize_text_for_keyword_matching(term)
        if not normalized_term:
            continue
        if normalized_term in seen_priority:
            continue
        seen_priority.add(normalized_term)
        priority_terms.append(normalized_term)

    return {
        "primary_terms": primary_terms,
        "excluded_terms": excluded_terms,
        "negative_terms": negative_terms,
        "strong_terms": strong_terms,
        "context_terms": context_terms,
        "priority_terms": priority_terms,
    }


_MAGENTO_KEYWORD_STOPWORDS = {
    # French stopwords that would match unrelated products via LIKE %word%
    "sur", "de", "du", "la", "le", "les", "un", "une", "des", "au", "aux",
    "et", "ou", "en", "par", "pour", "avec", "dans", "son", "ses", "pied",
    "the", "and", "for", "with", "from",
}


def _build_query_keywords_for_magento(
    keywords: List[str],
    structured_query: Dict[str, Any],
) -> List[str]:
    profile = _build_search_profile(structured_query, keywords)
    normalized_category = _normalize_text_for_keyword_matching(
        str(structured_query.get("category") or "")
    )
    query_terms: List[str] = []
    seen: set[str] = set()

    def _add_term(raw_term: str, allow_generic: bool = False) -> None:
        normalized_term = _normalize_text_for_keyword_matching(raw_term)
        if not normalized_term:
            return
        if len(normalized_term) <= 2:
            return
        if normalized_term in _MAGENTO_KEYWORD_STOPWORDS:
            return
        if not allow_generic and normalized_term in GENERIC_WEAK_QUERY_TERMS:
            return
        if normalized_term in seen:
            return
        seen.add(normalized_term)
        query_terms.append(normalized_term)

    # Force category anchors first so multilingual product names still match.
    for term in CATEGORY_CORE_QUERY_TERMS.get(normalized_category, []):
        _add_term(term, allow_generic=True)

    if normalized_category:
        _add_term(normalized_category, allow_generic=True)

    for term in sorted(
        profile["primary_terms"],
        key=lambda value: (len(value.split()) > 1, len(value)),
    ):
        _add_term(term, allow_generic=True)

    for term in profile["priority_terms"]:
        # Long intent phrases are usually poor Magento name filters.
        if len(term.split()) > 3 and term not in profile["primary_terms"]:
            continue
        _add_term(term)

    for term in keywords:
        _add_term(term)

    if not query_terms:
        for term in keywords:
            normalized_term = _normalize_text_for_keyword_matching(term)
            if not normalized_term:
                continue
            _add_term(normalized_term, allow_generic=True)

    return query_terms[:5]


def _score_candidate_product(
    haystack: str,
    haystack_tokens: set[str],
    profile: Dict[str, Any],
) -> float:
    primary_terms: set[str] = profile.get("primary_terms", set())
    excluded_terms: set[str] = profile.get("excluded_terms", set())
    negative_terms: set[str] = profile.get("negative_terms", set())
    strong_terms: set[str] = profile.get("strong_terms", set())
    context_terms: set[str] = profile.get("context_terms", set())

    if negative_terms and any(term in haystack for term in negative_terms):
        return 0.0
    if excluded_terms and any(term in haystack for term in excluded_terms):
        return 0.0

    primary_score = sum(
        _compute_term_match_score(term, haystack, haystack_tokens)
        for term in primary_terms
    )
    strong_score = sum(
        _compute_term_match_score(term, haystack, haystack_tokens)
        for term in strong_terms
    )
    context_score = sum(
        _compute_term_match_score(term, haystack, haystack_tokens)
        for term in context_terms
    )

    # When category is known, product MUST match at least one category term.
    # This prevents wrong-category products from scoring via color/spec matches alone.
    if primary_terms and primary_score == 0:
        return 0.0

    # When no category known (generic text query), require at least some keyword match
    if not primary_terms and strong_score == 0 and context_score == 0:
        return 0.0

    return round((primary_score * 3.0) + (strong_score * 2.0) + (context_score * 1.0), 3)


def _compute_explicit_score(
    name: str,
    haystack: str,
    haystack_tokens: set[str],
    query_keywords: List[str],
    image_caption_keywords: Optional[List[str]] = None,
) -> float:
    """
    Explicit match bonuses added on top of the profile-based score.

    Per query keyword:
      +5  exact whole-word match in the product NAME  (e.g. "iphone" in "Apple iPhone 14")
      +3  keyword found anywhere in the product NAME (multi-word phrase or prefix)
      +1  keyword found in the full haystack (description / attributes) but not in the name

    Image-caption bonus (image searches only):
      +3  per image-caption keyword that matches anywhere in the haystack
    """
    if not query_keywords:
        return 0.0

    name_norm = _normalize_text_for_keyword_matching(name)
    name_tokens = set(name_norm.split())
    bonus = 0.0

    for kw in query_keywords:
        kw_norm = _normalize_text_for_keyword_matching(kw)
        if not kw_norm or len(kw_norm) <= 1:
            continue
        kw_parts = kw_norm.split()

        if len(kw_parts) == 1:
            # Single token: require exact whole-word boundary in name for top score
            if kw_norm in name_tokens:
                bonus += 5.0
            elif kw_norm in haystack_tokens:
                bonus += 1.0
        else:
            # Multi-word phrase: substring match inside name is a strong signal
            if kw_norm in name_norm:
                bonus += 3.0
            elif kw_norm in haystack:
                bonus += 1.0

    # Image caption keywords — products matching the uploaded image get a lift
    if image_caption_keywords:
        for kw in image_caption_keywords:
            kw_norm = _normalize_text_for_keyword_matching(kw)
            if not kw_norm or len(kw_norm) <= 1:
                continue
            if kw_norm in name_tokens or kw_norm in haystack_tokens:
                bonus += 3.0

    return round(bonus, 3)


def _rank_products_from_items(
    items: List[Dict[str, Any]],
    structured_query: Dict[str, Any],
    query_keywords: List[str],
    language: str,
) -> List[ProductRecommendation]:
    profile = _build_search_profile(structured_query, query_keywords)
    # Optional image-caption keywords injected by the image search path
    image_caption_keywords: List[str] = structured_query.get("_image_caption_keywords") or []
    recommendations: List[ProductRecommendation] = []

    for product in items:
        extracted = _extract_product_data(product, language=language)
        if not extracted:
            continue

        haystack = _extract_search_haystack(product, extracted["name"])
        haystack_tokens = set(haystack.split())
        relevance = _score_candidate_product(haystack, haystack_tokens, profile)
        if relevance <= 0:
            continue

        # Explicit name / brand / image bonus — stacked on top of profile score
        explicit_bonus = _compute_explicit_score(
            name=extracted["name"],
            haystack=haystack,
            haystack_tokens=haystack_tokens,
            query_keywords=query_keywords,
            image_caption_keywords=image_caption_keywords,
        )
        recommendations.append(
            ProductRecommendation(
                **extracted,
                relevance_score=round(relevance + explicit_bonus, 3),
            )
        )

    recommendations.sort(
        key=lambda x: x.relevance_score or 0,
        reverse=True,
    )
    return recommendations


def _rank_products_loose(
    items: List[Dict[str, Any]],
    structured_query: Dict[str, Any],
    query_terms: List[str],
    language: str,
) -> List[ProductRecommendation]:
    profile = _build_search_profile(structured_query, query_terms)
    primary_terms: set[str] = profile.get("primary_terms", set())
    excluded_terms: set[str] = profile.get("excluded_terms", set())
    negative_terms: set[str] = profile.get("negative_terms", set())

    normalized_terms = [
        _normalize_text_for_keyword_matching(term)
        for term in query_terms
    ]
    normalized_terms = [
        term for term in normalized_terms
        if term and term not in GENERIC_WEAK_QUERY_TERMS
    ]
    if not normalized_terms:
        return []

    scored: List[tuple[float, ProductRecommendation]] = []
    for product in items:
        extracted = _extract_product_data(product, language=language)
        if not extracted:
            continue

        haystack = _extract_search_haystack(product, extracted["name"])
        haystack_tokens = set(haystack.split())
        if negative_terms and any(term in haystack for term in negative_terms):
            continue
        if excluded_terms and any(term in haystack for term in excluded_terms):
            continue

        primary_score = sum(
            _compute_term_match_score(term, haystack, haystack_tokens)
            for term in primary_terms
        )
        if primary_terms and primary_score <= 0:
            continue

        overlap = 0.0
        for term in normalized_terms:
            overlap += _compute_term_match_score(term, haystack, haystack_tokens)

        if overlap <= 0:
            continue

        scored.append(
            (
                (primary_score * 1.5) + overlap,
                ProductRecommendation(**extracted, relevance_score=None),
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    return [recommendation for _, recommendation in scored]


def _limit_recommendations(
    recommendations: List[ProductRecommendation],
) -> List[ProductRecommendation]:
    return recommendations[:MAX_RECOMMENDATIONS]


def _sort_recommendations_for_display(
    recommendations: List[ProductRecommendation],
) -> List[ProductRecommendation]:
    return sorted(
        recommendations,
        key=lambda rec: (
            rec.relevance_score is not None,
            rec.relevance_score if rec.relevance_score is not None else -1.0,
        ),
        reverse=True,
    )


def _format_top_matches_message(
    recommendations: List[ProductRecommendation],
    language: str,
    source_label: str = "",
) -> str:
    language = _validate_language(language)
    total = len(recommendations)
    if total == 0:
        if language == "fr":
            return "Aucun produit pertinent trouve. Precisez le type de produit (ex: ordinateur portable, telephone)."
        return "No relevant products found. Please specify the product type (for example: laptop, phone)."

    if all(rec.relevance_score is None for rec in recommendations):
        if language == "fr":
            return "Aucune correspondance exacte trouvee. Voici des produits similaires populaires."
        return "No exact match found. Here are similar popular products."

    perfect_count = min(3, total)
    alternatives_count = max(0, total - perfect_count)
    source_suffix = f" using {source_label}" if source_label and language == "en" else ""
    if language == "fr":
        source_suffix = f" via {source_label}" if source_label else ""
        if alternatives_count > 0:
            return (
                f"Ces {perfect_count} produits correspondent parfaitement a votre demande{source_suffix}. "
                f"{alternatives_count} autre(s) alternative(s) sont aussi proposees."
            )
        return f"Ces {perfect_count} produits correspondent parfaitement a votre demande{source_suffix}."

    if alternatives_count > 0:
        return (
            f"These {perfect_count} products match your request perfectly{source_suffix}. "
            f"I also included {alternatives_count} alternative option(s)."
        )
    return f"These {perfect_count} products match your request perfectly{source_suffix}."


def _build_magento_keyword_search_criteria(query_keywords: List[str]) -> Optional[Dict[str, Any]]:
    if not query_keywords:
        return None
    return {
        "filter_groups": [
            {
                "filters": [
                    {
                        "field": "name",
                        "value": f"%{keyword}%",
                        "condition_type": "like",
                    }
                    for keyword in query_keywords
                ]
            }
        ]
    }


def _build_magento_cache_key(
    endpoint: str,
    language: str,
    page_size: int,
    max_pages: int,
    search_criteria: Optional[Dict[str, Any]],
) -> str:
    flat_criteria: Dict[str, Any] = {}
    if search_criteria:
        _flatten_search_criteria("searchCriteria", search_criteria, flat_criteria)
    payload = {
        "endpoint": endpoint,
        "language": language,
        "page_size": page_size,
        "max_pages": max_pages,
        "criteria": flat_criteria,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _magento_cache_get(cache_key: str) -> Optional[List[Dict[str, Any]]]:
    if settings.MAGENTO_CACHE_TTL_SECONDS <= 0:
        return None
    cached = _MAGENTO_CACHE.get(cache_key)
    if not cached:
        return None
    inserted_at, items = cached
    if time.monotonic() - inserted_at > settings.MAGENTO_CACHE_TTL_SECONDS:
        _MAGENTO_CACHE.pop(cache_key, None)
        return None
    _MAGENTO_CACHE.move_to_end(cache_key)
    return list(items)


def _magento_cache_set(cache_key: str, items: List[Dict[str, Any]]) -> None:
    if settings.MAGENTO_CACHE_TTL_SECONDS <= 0 or settings.MAGENTO_CACHE_MAX_ITEMS <= 0:
        return
    _MAGENTO_CACHE[cache_key] = (time.monotonic(), list(items))
    _MAGENTO_CACHE.move_to_end(cache_key)
    while len(_MAGENTO_CACHE) > settings.MAGENTO_CACHE_MAX_ITEMS:
        _MAGENTO_CACHE.popitem(last=False)


def _build_fallback_recommendations(
    items: List[Dict[str, Any]],
    structured_query: Dict[str, Any],
    query_keywords: List[str],
    semantic_query: str,
    language: str,
) -> List[ProductRecommendation]:
    ranking_keywords = query_keywords or _extract_keywords(semantic_query, language)
    ranked = _rank_products_from_items(
        items=items,
        structured_query=structured_query,
        query_keywords=ranking_keywords,
        language=language,
    )
    if ranked:
        return _limit_recommendations(ranked)

    loose_terms = ranking_keywords or _extract_keywords(semantic_query, language)
    loose_ranked = _rank_products_loose(
        items=items,
        structured_query=structured_query,
        query_terms=loose_terms,
        language=language,
    )
    if loose_ranked:
        return _limit_recommendations(loose_ranked)

    if str(structured_query.get("category") or "").strip():
        return []

    fallback: List[ProductRecommendation] = []
    for product in items:
        extracted = _extract_product_data(product, language=language)
        if extracted:
            fallback.append(ProductRecommendation(**extracted, relevance_score=None))
    return _limit_recommendations(fallback)


async def _fetch_catalog_fallback_items(language: str) -> List[Dict[str, Any]]:
    return await fetch_magento_products(
        search_criteria=None,
        page_size=CATALOG_FALLBACK_PAGE_SIZE,
        max_pages=1,
        language=language,
    )


def _structured_query_from_caption(
    caption_data: Dict[str, Any],
    language: str,
    user_hint: str = "",
) -> Dict[str, Any]:
    """Build a structured query directly from caption fields — no Mistral API call needed."""
    category_raw = str(caption_data.get("category") or "").strip().lower()
    title = str(caption_data.get("title") or "").strip()
    attributes_raw = str(caption_data.get("attributes") or "").strip()
    also_visible = str(caption_data.get("also_visible_products") or "").strip()

    # Normalise category to a known key
    _cat_map = [
        ({"smartphone", "phone", "mobile", "iphone", "android", "téléphone"}, "smartphone"),
        ({"laptop", "notebook", "ordinateur", "macbook", "ultrabook"}, "laptop"),
        ({"fan", "ventilateur", "ventilator", "air cooler"}, "fan"),
        ({"tablet", "tablette", "ipad"}, "tablet"),
        ({"headphones", "headset", "casque", "earbuds", "earbud"}, "headphones"),
        ({"television", "tv", "smart tv", "télévision"}, "television"),
    ]
    category = category_raw
    for triggers, canonical in _cat_map:
        if any(t in category_raw for t in triggers):
            category = canonical
            break

    # Title words (most specific — brand + model)
    title_keywords = [w for w in re.split(r"\s+", title) if len(w) > 1]

    # Attribute tokens (color, storage, etc.)
    attr_keywords = [
        a.strip() for a in re.split(r"[,;]", attributes_raw) if a.strip()
    ]

    # Also-visible secondary products
    secondary_keywords: List[str] = []
    if also_visible:
        secondary_keywords = [
            a.strip() for a in re.split(r"[,;]", also_visible) if a.strip()
        ]

    # User hint words
    hint_keywords = re.split(r"\s+", user_hint.strip()) if user_hint.strip() else []
    hint_keywords = [w for w in hint_keywords if len(w) > 2]

    priority_terms = title_keywords[:4]
    keywords = list(dict.fromkeys(
        title_keywords + attr_keywords + hint_keywords + secondary_keywords
    ))

    return {
        "category": category,
        "keywords": keywords,
        "attributes": attr_keywords,
        "priority_terms": priority_terms,
        "negative_terms": [],
        "language": language,
        "confidence": 0.88,
        "budget": {"min": None, "max": None, "currency": "FCFA"},
        "use_case": "",
        "user_type": "",
        "price_class": "",
    }


async def _run_single_text_query(
    query_text: str,
    language: str,
) -> List[ProductRecommendation]:
    """
    Execute one text search query end-to-end and return ranked recommendations.
    Used by the multi-query path so each query runs through Mistral independently.
    """
    structured_query = await _process_query_with_unified_ai(
        input_text=query_text,
        language=language,
    )
    resolved_language = _validate_language(
        str(structured_query.get("language") or language)
    )
    semantic_query = _build_semantic_query_text(structured_query=structured_query)
    keywords = _build_keywords_from_structured_query(
        structured_query=structured_query,
        language=resolved_language,
    )
    query_keywords = _build_query_keywords_for_magento(keywords, structured_query)
    bilingual_kw = _expand_keywords_bilingual(query_keywords) if query_keywords else []
    if not bilingual_kw and semantic_query:
        bilingual_kw = _expand_keywords_bilingual(
            [w for w in semantic_query.split() if len(w) > 2][:5]
        )

    items = await _fetch_bilingual_products(
        search_criteria=_build_magento_keyword_search_criteria(bilingual_kw) if bilingual_kw else None,
        page_size=100,
        max_pages=1,
        keywords=bilingual_kw,
    )

    recommendations = _rank_products_from_items(
        items=items,
        structured_query=structured_query,
        query_keywords=bilingual_kw,
        language=resolved_language,
    )

    if not recommendations and items:
        recommendations = _build_fallback_recommendations(
            items=items,
            structured_query=structured_query,
            query_keywords=bilingual_kw,
            semantic_query=semantic_query or query_text,
            language=resolved_language,
        )

    budget_filtered = _apply_budget_filter(recommendations, structured_query)
    if budget_filtered:
        recommendations = budget_filtered

    return recommendations


def _merge_recommendations_deduped(
    lists: List[List[ProductRecommendation]],
) -> List[ProductRecommendation]:
    """Merge multiple ranked recommendation lists, deduplicating by SKU."""
    seen_skus: set[str] = set()
    merged: List[ProductRecommendation] = []
    for recs in lists:
        for rec in recs:
            if rec.sku in seen_skus:
                continue
            seen_skus.add(rec.sku)
            merged.append(rec)
    return merged


async def _process_query_with_unified_ai(input_text: str, language: str) -> Dict[str, Any]:
    normalized_input = re.sub(r"\s+", " ", str(input_text or "").strip())
    if not normalized_input:
        return UnifiedQueryAIService._fallback_payload("", language)

    # Single-word queries: fast path — Mistral not needed, keyword extraction sufficient
    if len(normalized_input.split()) == 1:
        return UnifiedQueryAIService._fallback_payload(normalized_input, language)

    # All multi-word queries always go through Mistral — handles EN, FR, and mixed naturally.
    # The query cache makes repeat calls instant (0ms hit after first call).
    return await UnifiedQueryAIService.process_raw_query(normalized_input, language)


# Cross-language term pairs so a French caption finds English-named products and vice-versa
_CROSS_LANG_SYNONYMS: List[tuple[str, str]] = [
    ("ventilateur", "fan"),
    ("ordinateur portable", "laptop"),
    ("smartphone", "téléphone portable"),
    ("casque", "headphones"),
    ("tablette", "tablet"),
    ("télévision", "television"),
    ("écouteurs", "earbuds"),
    ("chargeur", "charger"),
    ("enceinte", "speaker"),
]


def _expand_keywords_bilingual(keywords: List[str]) -> List[str]:
    """Add cross-language equivalents so one search finds products in both stores."""
    expanded = list(keywords)
    seen = {k.lower() for k in keywords}
    for fr_term, en_term in _CROSS_LANG_SYNONYMS:
        if fr_term in seen and en_term not in seen:
            expanded.append(en_term)
            seen.add(en_term)
        elif en_term in seen and fr_term not in seen:
            expanded.append(fr_term)
            seen.add(fr_term)
    # Cap at 8 — more LIKE conditions = slower Magento SQL
    return expanded[:8]


async def _search_typesense(keywords: List[str], per_page: int = 250) -> List[Dict[str, Any]]:
    """
    Search Typesense with the given keywords and return raw Magento-format product dicts.
    Returns an empty list if Typesense is not configured, unreachable, or returns no hits.
    """
    if not keywords:
        return []

    try:
        from app.typesense_client import get_typesense_client
        from app.config import settings as _settings
    except Exception:
        return []

    client = get_typesense_client()
    if client is None:
        return []

    query = " ".join(k for k in keywords[:15] if k)

    try:
        results = await asyncio.to_thread(
            client.collections[_settings.TYPESENSE_COLLECTION].documents.search,
            {
                "q": query,
                "query_by": "name,description_text,brand,category_name",
                "per_page": min(per_page, 250),
                "num_typos": 2,
                "drop_tokens_threshold": 2,
            },
        )
        hits = results.get("hits") or []
        products: List[Dict[str, Any]] = []
        seen_skus: set[str] = set()
        for hit in hits:
            doc = hit.get("document") or {}
            raw = doc.get("raw_json")
            if not raw:
                continue
            try:
                product = json.loads(raw)
            except Exception:
                continue
            sku = str(product.get("sku") or "").strip()
            if not sku or sku in seen_skus:
                continue
            seen_skus.add(sku)
            products.append(product)
        logger.debug("Typesense returned %d products for query: %s", len(products), query)
        return products
    except Exception as exc:
        logger.warning("Typesense search failed (%s) — falling back to Magento", exc)
        return []


async def _fetch_bilingual_products(
    search_criteria: Optional[Dict[str, Any]],
    page_size: int,
    max_pages: int,
    keywords: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Fast path: search Typesense if available.
    Fallback: fetch from both EN and FR Magento stores in parallel and merge by SKU.
    """
    # Try Typesense first — typically <100 ms vs 2-10 s for Magento
    if keywords:
        ts_results = await _search_typesense(keywords)
        if ts_results:
            return ts_results

    # Magento fallback
    items_en, items_fr = await asyncio.gather(
        fetch_magento_products(search_criteria, page_size, max_pages, language="en"),
        fetch_magento_products(search_criteria, page_size, max_pages, language="fr"),
    )
    seen_skus: set[str] = set()
    merged: List[Dict[str, Any]] = []
    for item in items_fr + items_en:   # FR first — respects user's language choice
        sku = str(item.get("sku") or "").strip()
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)
        merged.append(item)
    return merged


# ------------------------
# Magento Fetch (language-aware)
# ------------------------

async def fetch_magento_products(
    search_criteria: Optional[Dict[str, Any]] = None,
    page_size: int = 20,
    max_pages: int = 2,
    language: str = "en",
) -> List[Dict[str, Any]]:

    if not settings.MAGENTO_BASE_URL or not settings.MAGENTO_ACCESS_TOKEN:
        return []

    language = language.strip().lower()
    store_view = (
        settings.MAGENTO_STORE_VIEW_FR
        if language == "fr"
        else settings.MAGENTO_STORE_VIEW_EN
    )

    endpoint = (
        settings.MAGENTO_BASE_URL.rstrip("/")
        + f"/rest/{store_view}/V1/products"
    )

    cache_key = _build_magento_cache_key(
        endpoint=endpoint,
        language=language,
        page_size=page_size,
        max_pages=max_pages,
        search_criteria=search_criteria,
    )
    cached = _magento_cache_get(cache_key)
    if cached is not None:
        return cached

    items: List[Dict[str, Any]] = []

    # Build params for every page upfront
    base_flat: Dict[str, Any] = {}
    if search_criteria:
        _flatten_search_criteria("searchCriteria", search_criteria, base_flat)

    def _page_params(page: int) -> Dict[str, Any]:
        p = {
            "searchCriteria[currentPage]": page,
            "searchCriteria[pageSize]": page_size,
        }
        p.update(base_flat)
        return p

    client = _get_magento_http_client()

    async def _fetch_page(page: int) -> List[Dict[str, Any]]:
        try:
            resp = await _get_with_retry(
                client=client,
                endpoint=endpoint,
                params=_page_params(page),
                retries=settings.MAGENTO_RETRIES,
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception:
            return []

    try:
        if max_pages == 1:
            items = await _fetch_page(1)
        else:
            # Fetch all pages concurrently — cuts time from N×T to max(T)
            page_results = await asyncio.gather(
                *[_fetch_page(p) for p in range(1, max_pages + 1)]
            )
            for page_items in page_results:
                items.extend(page_items)

    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.warning(
            "Magento product fetch skipped for endpoint %s due to upstream error: %s",
            endpoint,
            exc,
        )
        return []

    _magento_cache_set(cache_key, items)
    return items


async def _get_with_retry(
    client: httpx.AsyncClient,
    endpoint: str,
    params: Dict[str, Any],
    retries: int,
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return await client.get(endpoint, params=params)
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            httpx.ProxyError,
        ) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            backoff = 0.5 * (2 ** attempt)
            await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc


# ------------------------
# Chat Service
# ------------------------

class ChatService:

    @staticmethod
    async def fetch_products_by_sku(sku: str, language: str = "en") -> List[Dict[str, Any]]:
        search_criteria = {
            "filter_groups": [
                {
                    "filters": [
                        {"field": "sku", "value": sku, "condition_type": "eq"}
                    ]
                }
            ]
        }

        try:
            return await fetch_magento_products(
                search_criteria=search_criteria,
                language=language,
            )
        except Exception as e:
            logger.error("SKU fetch failed: %s", e, exc_info=True)
            return []


    @staticmethod
    async def recommend_products(
        message: str,
        user_id: int,
        language: str = "en",
    ) -> ChatResponse:
        language = _validate_language(language)
        # Auto-correct language if the query text strongly signals the other language
        # (e.g. frontend says "en" but user typed in French)
        language = detect_query_language(message, language)

        # --- Decision layer: split multi-product queries + normalize FR→EN
        decision = await analyze_multimodal_query(
            message=message,
            image_caption=None,
            audio_transcription=None,
            video_caption=None,
            language=language,
        )
        queries = decision.get("queries") or [message]
        if not queries or queries == [""]:
            queries = [message]

        if len(queries) == 1:
            # Fast path — single query, no grouping needed
            recommendations = await _run_single_text_query(queries[0], language)
            recommendations = _sort_recommendations_for_display(recommendations)
            recommendations = _limit_recommendations(recommendations)
            return ChatResponse(
                message=_format_top_matches_message(
                    recommendations=recommendations,
                    language=language,
                ),
                recommendations=recommendations,
                caption=None,
            )

        # Multi-product: run each query independently in parallel
        multi_results = await asyncio.gather(
            *[_run_single_text_query(q, language) for q in queries]
        )

        # Build one group per query (same structure as image+text search)
        groups: List[ProductGroup] = []
        for q, recs in zip(queries, multi_results):
            sorted_recs = _sort_recommendations_for_display(recs)
            groups.append(ProductGroup(
                category=q,
                products=sorted_recs[:MAX_RECOMMENDATIONS_PER_GROUP],
            ))

        # Flat list for backward compatibility — order matches groups (first query first)
        recommendations = _merge_recommendations_deduped([g.products for g in groups])
        recommendations = _sort_recommendations_for_display(recommendations)
        recommendations = _limit_recommendations(recommendations)

        return ChatResponse(
            message=_format_top_matches_message(
                recommendations=recommendations,
                language=language,
            ),
            recommendations=recommendations,
            caption=None,
            groups=groups,
        )


    @staticmethod
    async def recommend_products_by_media(
        media: UploadFile,
        user_id: int,
        language: str = "en",
    ) -> MediaRecommendationResponse:
        resolved_language = _validate_language(language)
        media_type = _detect_upload_type(media)

        if media_type == "image":
            image_response = await ChatService.recommend_products_by_image(
                image=media,
                user_id=user_id,
                language=resolved_language,
            )
            return MediaRecommendationResponse(
                source="image",
                message=image_response.message,
                recommendations=image_response.recommendations,
            )

        if media_type == "video":
            video_response = await ChatService.recommend_products_by_video(
                video=media,
                user_id=user_id,
                language=resolved_language,
            )
            return MediaRecommendationResponse(
                source="video",
                message=_format_top_matches_message(
                    recommendations=video_response.products,
                    language=video_response.language,
                    source_label="video",
                ),
                recommendations=video_response.products,
                caption=video_response.caption,
                frames_used=video_response.frames_used,
            )

        if media_type == "audio":
            audio_response = await ChatService.recommend_products_by_audio(
                audio=media,
                user_id=user_id,
                language=resolved_language,
            )
            return MediaRecommendationResponse(
                source="audio",
                message=audio_response.message,
                recommendations=audio_response.recommendations,
            )

        raise HTTPException(
            status_code=415,
            detail="Unsupported media format. Upload image, video, or audio.",
        )


    @staticmethod
    async def recommend_products_by_image(
        image: UploadFile,
        user_id: int,
        language: str = "en",
        user_hint: str = "",
    ) -> ChatResponse:

        try:
            image_bytes = await image.read()
            language = language.strip().lower()

            quality_error = _is_image_quality_poor(image, image_bytes)
            if quality_error:
                return ChatResponse(message=quality_error, recommendations=[], caption=None)

            # Generate both language captions in parallel so switching language is instant
            # (both get cached by image hash — second upload in either language = 0ms)
            caption_en_task = ImageCaptionService.generate_caption_en_from_bytes(
                image_bytes=image_bytes, content_type=image.content_type,
            )
            caption_fr_task = ImageCaptionService.generate_caption_fr_from_bytes(
                image_bytes=image_bytes, content_type=image.content_type,
            )
            caption_en, caption_fr = await asyncio.gather(caption_en_task, caption_fr_task)
            caption_data = caption_fr if language == "fr" else caption_en

            if not caption_data["ok"]:
                return ChatResponse(
                    message=caption_data["reason"] or "Image could not be processed",
                    recommendations=[],
                    caption=None,
                )

            hint_clean = user_hint.strip() if user_hint else ""
            search_caption = caption_data.get("caption") or ""

            # resolved_language safe default — always set before the if/else branches
            resolved_language = language

            # ------------------------------------------------------------------
            # Image+text merge logic
            #
            # Rule: image intent is ALWAYS included in the search unless the user
            # explicitly says "ignore the image".  Text queries are added AFTER
            # the image intent so image results appear first in the output.
            #
            # Examples:
            #   image=fan  + text=""                  → ["fan"]
            #   image=fan  + text="laptop and phone"  → ["fan", "laptop", "phone"]
            #   image=fan  + text="ignore the image, show laptop" → ["laptop"]
            #   image=fan  + text="black one"          → single path (refinement)
            # ------------------------------------------------------------------

            # ── Step 1: Extract image intent ──────────────────────────────────────
            # _structured_query_from_caption has _cat_map that normalises:
            #   "Electric fan" / "ventilateur" / "Ventilateur de table" → "fan"
            #   "ordinateur portable" / "MacBook" → "laptop"
            # Caption-word fallback ensures we always get something when Mistral
            # returns an unparsed description instead of a labelled CATEGORY field.
            _sq = _structured_query_from_caption(
                caption_data=caption_data, language=language, user_hint=""
            )
            image_intent: Optional[str] = _sq.get("category") or None
            if not image_intent and search_caption:
                _cap_words = [w for w in search_caption.lower().split() if len(w) > 2]
                if _cap_words:
                    image_intent = normalize_fr_to_en(_cap_words[0])

            # ── Step 2: Detect explicit "ignore image" instruction ────────────
            # Only suppressed when the user explicitly asks. Never suppressed by AI.
            user_ignore_image = _fast_ignore_check(hint_clean, language) if hint_clean else False

            # ── Step 3: Split text into individual product queries ────────────
            # Splits on conjunctions: "and" / "et" / ","
            # Normalises French product terms → English.
            raw_splits: List[str] = []
            text_queries: List[str] = []
            if hint_clean:
                raw_splits = _split_query_text(hint_clean, language)
                text_queries = [normalize_fr_to_en(q) for q in raw_splits]

            logger.info(
                "[DEBUG] image_intent=%r  user_ignore_image=%r  "
                "raw_splits=%r  text_queries=%r",
                image_intent, user_ignore_image, raw_splits, text_queries,
            )

            # ── Branch logic ──────────────────────────────────────────────────
            #
            #   PURE IMAGE  — no text typed at all
            #   MERGE       — image + text → ALWAYS combined (image first)
            #   TEXT ONLY   — user explicitly said "ignore the image"
            #
            # There is NO intent classification, NO refinement detection,
            # and NO AI deciding which modality wins. The merge is deterministic.

            if not hint_clean:
                # ── Pure image: fast structured-caption path, no Mistral ──────
                structured_query = _structured_query_from_caption(
                    caption_data=caption_data,
                    language=language,
                    user_hint="",
                )
                if search_caption:
                    structured_query["_image_caption_keywords"] = _extract_keywords(
                        search_caption, resolved_language
                    )
                resolved_language = _validate_language(
                    str(structured_query.get("language") or language)
                )
                semantic_query = _build_semantic_query_text(structured_query=structured_query)
                keywords = _build_keywords_from_structured_query(
                    structured_query=structured_query, language=resolved_language
                )
                query_keywords = _build_query_keywords_for_magento(keywords, structured_query)
                bilingual_keywords = _expand_keywords_bilingual(query_keywords) if query_keywords else []
                if not bilingual_keywords and semantic_query:
                    bilingual_keywords = _expand_keywords_bilingual(
                        [w for w in semantic_query.split() if len(w) > 2][:5]
                    )
                items = await _fetch_bilingual_products(
                    search_criteria=_build_magento_keyword_search_criteria(bilingual_keywords)
                    if bilingual_keywords else None,
                    page_size=100,
                    max_pages=1,
                    keywords=bilingual_keywords,
                )
                recommendations = _rank_products_from_items(
                    items=items,
                    structured_query=structured_query,
                    query_keywords=bilingual_keywords,
                    language=resolved_language,
                )
                if not recommendations and items:
                    recommendations = _build_fallback_recommendations(
                        items=items,
                        structured_query=structured_query,
                        query_keywords=bilingual_keywords,
                        semantic_query=semantic_query,
                        language=resolved_language,
                    )
                budget_filtered = _apply_budget_filter(recommendations, structured_query)
                if budget_filtered:
                    recommendations = budget_filtered

            else:
                # ── Image + text (or text-only ignore) ───────────────────────
                # Build query list deterministically — no AI classification.
                #
                #   image_intent first (unless user said "ignore image")
                #   then all text_queries in order
                #   duplicates removed (case-insensitive)
                final_queries: List[str] = []
                seen_q: set[str] = set()

                if image_intent and not user_ignore_image:
                    final_queries.append(image_intent)
                    seen_q.add(image_intent.lower())

                for q in text_queries:
                    if q.lower() not in seen_q:
                        final_queries.append(q)
                        seen_q.add(q.lower())

                # Fallback: if nothing resolved use the raw caption.
                if not final_queries and search_caption:
                    final_queries = [search_caption]

                logger.info("[DEBUG] FINAL QUERIES: %r", final_queries)

                # Run each query independently in parallel; order preserved.
                multi_results = await asyncio.gather(
                    *[_run_single_text_query(q, language) for q in final_queries]
                )

                for i, q in enumerate(final_queries):
                    logger.info("[DEBUG] QUERY %r → %d results", q, len(multi_results[i]))

                # ── Build grouped results (one slice per query) ───────────────
                # Each group is sorted and capped independently so no single
                # category can crowd out the others.
                groups: List[ProductGroup] = []
                for q, recs in zip(final_queries, multi_results):
                    sorted_recs = _sort_recommendations_for_display(recs)
                    groups.append(ProductGroup(
                        category=q,
                        products=sorted_recs[:MAX_RECOMMENDATIONS_PER_GROUP],
                    ))

                # ── Flat recommendations list (backward-compat) ───────────────
                # Produced from the grouped results in order so the flat list
                # also respects image-first priority, then deduplicates.
                recommendations = _merge_recommendations_deduped(
                    [g.products for g in groups]
                )
                logger.info("[DEBUG] groups=%d  flat=%d", len(groups), len(recommendations))

                recommendations = _sort_recommendations_for_display(recommendations)
                recommendations = _limit_recommendations(recommendations)

                return ChatResponse(
                    message=_format_top_matches_message(
                        recommendations=recommendations,
                        language=resolved_language,
                        source_label="image",
                    ),
                    recommendations=recommendations,
                    caption=search_caption,
                    groups=groups,
                )

            # ── Single-query path return (pure image) ────────────────────────
            recommendations = _sort_recommendations_for_display(recommendations)
            recommendations = _limit_recommendations(recommendations)

            return ChatResponse(
                message=_format_top_matches_message(
                    recommendations=recommendations,
                    language=resolved_language,
                    source_label="image",
                ),
                recommendations=recommendations,
                caption=search_caption,
            )

        except Exception as e:
            logger.error("Image-based recommendation failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Image-based product recommendation failed",
            )


    @staticmethod
    async def recommend_products_by_audio(
        audio: UploadFile,
        user_id: int,
        language: str,
    ) -> ChatResponse:
        language = _validate_language(language)

        try:
            audio_bytes = await audio.read()
            _validate_audio_upload(audio, audio_bytes)

            transcription = await _transcribe_audio_with_assemblyai(
                audio_bytes=audio_bytes,
                language=language,
            )

            structured_query = await _process_query_with_unified_ai(
                input_text=transcription,
                language=language,
            )
            resolved_language = _validate_language(
                str(structured_query.get("language") or language)
            )
            semantic_query = _build_semantic_query_text(
                structured_query=structured_query,
            )
            keywords = _build_keywords_from_structured_query(
                structured_query=structured_query,
                language=resolved_language,
            )
            query_keywords = _build_query_keywords_for_magento(keywords, structured_query)
            if query_keywords:
                items = await fetch_magento_products(
                    search_criteria=_build_magento_keyword_search_criteria(query_keywords),
                    page_size=20,
                    max_pages=1,
                    language=resolved_language,
                )

                recommendations = _rank_products_from_items(
                    items=items,
                    structured_query=structured_query,
                    query_keywords=query_keywords,
                    language=resolved_language,
                )
                budget_filtered = _apply_budget_filter(recommendations, structured_query)
                if budget_filtered:
                    recommendations = budget_filtered
                recommendations = _sort_recommendations_for_display(recommendations)
                recommendations = _limit_recommendations(recommendations)

                if recommendations:
                    return ChatResponse(
                        message=_format_top_matches_message(
                            recommendations=recommendations,
                            language=resolved_language,
                            source_label="audio",
                        ),
                        recommendations=recommendations,
                        caption=_build_audio_caption_from_transcript(
                            transcript=transcription,
                            language=resolved_language,
                        ),
                    )

            # Fallback to exact phrase matching when keyword search returns nothing.
            fallback = await ChatService.recommend_products(
                message=semantic_query,
                user_id=user_id,
                language=resolved_language,
            )
            return ChatResponse(
                message=_format_top_matches_message(
                    recommendations=fallback.recommendations,
                    language=resolved_language,
                    source_label="audio",
                ),
                recommendations=fallback.recommendations,
                caption=_build_audio_caption_from_transcript(
                    transcript=transcription,
                    language=resolved_language,
                ),
            )
        except HTTPException:
            raise
        except RuntimeError as exc:
            logger.error("Audio transcription failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=str(exc),
            )
        except Exception as exc:
            logger.error("Audio-based recommendation failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Audio-based product recommendation failed",
            )

    @staticmethod
    async def recommend_products_by_video(
        video: UploadFile,
        user_id: int,
        language: str,
        user_hint: str = "",
    ) -> VideoRecommendationResponse:
        language = _validate_language(language)
        temp_video_path: Optional[str] = None

        try:
            video_bytes = await video.read()
            file_extension = _validate_video_upload(video, video_bytes)
            caption_cache_key = _build_media_caption_cache_key(video_bytes, language)
            cached_caption_entry = _video_caption_cache_get(caption_cache_key)
            cached_caption = cached_caption_entry[0] if cached_caption_entry else None
            cached_frames_used = cached_caption_entry[1] if cached_caption_entry else 0

            # Offload file I/O and frame extraction to worker threads.
            temp_video_path = await asyncio.to_thread(
                _save_temp_video_file,
                video_bytes,
                file_extension,
            )

            extracted_video_audio: Optional[bytes] = None
            frames_used = cached_frames_used
            if cached_caption:
                merged_caption = cached_caption
                extracted_video_audio = await asyncio.to_thread(
                    _extract_audio_from_video,
                    temp_video_path,
                )
            else:
                frame_task = asyncio.to_thread(
                    extract_frames_from_video,
                    temp_video_path,
                )
                audio_task = asyncio.to_thread(
                    _extract_audio_from_video,
                    temp_video_path,
                )
                frame_bytes_list, extracted_video_audio = await asyncio.gather(
                    frame_task,
                    audio_task,
                )
                if not frame_bytes_list:
                    raise HTTPException(
                        status_code=422,
                        detail="No frames could be extracted from the uploaded video",
                    )

                unique_frame_bytes: List[bytes] = []
                seen_hashes: set[str] = set()
                for frame_bytes in frame_bytes_list:
                    frame_hash = hashlib.sha256(frame_bytes).hexdigest()
                    if frame_hash in seen_hashes:
                        continue
                    seen_hashes.add(frame_hash)
                    unique_frame_bytes.append(frame_bytes)
                frame_bytes_list = unique_frame_bytes

                caption_fn = (
                    ImageCaptionService.generate_caption_fr_from_bytes
                    if language == "fr"
                    else ImageCaptionService.generate_caption_en_from_bytes
                )
                # Caption each sampled frame with existing language-specific caption service.
                caption_tasks = [
                    caption_fn(image_bytes=frame_bytes, content_type="image/jpeg")
                    for frame_bytes in frame_bytes_list
                ]
                caption_results = await asyncio.gather(*caption_tasks, return_exceptions=True)

                successful_captions: List[str] = []
                for result in caption_results:
                    if isinstance(result, Exception):
                        logger.warning("Video frame captioning failed: %s", result)
                        continue
                    if not isinstance(result, dict) or not result.get("ok"):
                        continue

                    caption = str(result.get("caption") or "").strip()
                    if caption:
                        successful_captions.append(caption)

                if not successful_captions:
                    raise HTTPException(
                        status_code=502,
                        detail="Failed to generate captions from extracted video frames",
                    )

                merged_caption = merge_captions(successful_captions, language=language)
                if not merged_caption:
                    raise HTTPException(
                        status_code=502,
                        detail="Failed to build a search query from video captions",
                    )
                frames_used = len(successful_captions)
                _video_caption_cache_set(caption_cache_key, merged_caption, frames_used)

            recommendations: List[ProductRecommendation] = []
            audio_caption = ""
            if extracted_video_audio:
                if len(extracted_video_audio) <= MAX_AUDIO_SIZE_BYTES:
                    try:
                        transcription = await _transcribe_audio_with_assemblyai(
                            audio_bytes=extracted_video_audio,
                            language=language,
                        )
                        audio_caption = _build_audio_caption_from_transcript(
                            transcript=transcription,
                            language=language,
                        )
                    except RuntimeError as exc:
                        logger.warning(
                            "Video audio transcription failed; continuing with visual-only search: %s",
                            exc,
                        )
                else:
                    logger.warning(
                        "Extracted video audio exceeds max supported size (%s bytes); skipping audio fusion",
                        len(extracted_video_audio),
                    )

            visual_caption = _compact_caption_for_search(merged_caption, language)
            if not visual_caption:
                visual_caption = merged_caption
            multimodal_query = _build_multimodal_video_query(
                visual_caption=visual_caption,
                audio_caption=audio_caption or None,
                language=language,
            )
            search_caption = multimodal_query["search_caption"]
            # Merge user's optional text hint with the visual+audio caption.
            # resolve_multimodal_intent applies TEXT-PRIORITY rules so user text
            # about different products correctly overrides the video caption.
            hint_clean = user_hint.strip() if user_hint else ""
            if hint_clean:
                input_for_ai = await resolve_multimodal_intent(
                    user_text=hint_clean,
                    image_caption=None,
                    audio_text=audio_caption or None,
                    video_caption=search_caption,
                    language=language,
                )
            else:
                input_for_ai = search_caption
            structured_query = await _process_query_with_unified_ai(
                input_text=input_for_ai,
                language=language,
            )
            resolved_language = _validate_language(
                str(structured_query.get("language") or language)
            )
            semantic_query = _build_semantic_query_text(
                structured_query=structured_query,
            )
            keywords = _build_keywords_from_structured_query(
                structured_query=structured_query,
                language=resolved_language,
            )
            query_keywords = _build_query_keywords_for_magento(keywords, structured_query)

            try:
                # Primary path: bilingual keyword search in both EN and FR Magento stores.
                bilingual_keywords = _expand_keywords_bilingual(query_keywords)
                items = await _fetch_bilingual_products(
                    search_criteria=_build_magento_keyword_search_criteria(bilingual_keywords),
                    page_size=150,
                    max_pages=2,
                    keywords=bilingual_keywords,
                )

                recommendations = _rank_products_from_items(
                    items=items,
                    structured_query=structured_query,
                    query_keywords=bilingual_keywords,
                    language=resolved_language,
                )

                budget_filtered = _apply_budget_filter(recommendations, structured_query)
                if budget_filtered:
                    recommendations = budget_filtered

                # Fallback: phrase search if keyword search yields nothing.
                if not recommendations:
                    fallback = await ChatService.recommend_products(
                        message=semantic_query,
                        user_id=user_id,
                        language=resolved_language,
                    )
                    recommendations = fallback.recommendations
                recommendations = _sort_recommendations_for_display(recommendations)
                recommendations = _limit_recommendations(recommendations)
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.error(
                    "Magento product search failed for video recommendation: %s",
                    exc,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Magento product search failed",
                ) from exc

            return VideoRecommendationResponse(
                ok=True,
                language=resolved_language,
                source="video",
                caption=search_caption,
                frames_used=frames_used,
                 products=recommendations,
            )
        except HTTPException:
            raise
        except RuntimeError as exc:
            logger.error("Video processing failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            logger.error("Video-based recommendation failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Video-based product recommendation failed",
            ) from exc
        finally:
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                except OSError:
                    logger.warning(
                        "Could not remove temporary video file: %s",
                        temp_video_path,
                    )
