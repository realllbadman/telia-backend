import asyncio
import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Optional

import httpx
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.chat.image_caption import ImageCaptionService
from app.chat.unified_query_ai_service import UnifiedQueryAIService
from app.chat.schemas import ProductRecommendation, ChatResponse, VideoRecommendationResponse

logger = logging.getLogger(__name__)

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
    "fan": {"fan", "ventilator", "air cooler", "aircooler", "ventilateur"},
    "ventilateur": {"fan", "ventilator", "air cooler", "aircooler", "ventilateur"},
}
CATEGORY_CORE_QUERY_TERMS: Dict[str, List[str]] = {
    "laptop": ["laptop", "ordinateur portable", "notebook"],
    "ordinateur portable": ["ordinateur portable", "laptop", "notebook"],
    "smartphone": ["smartphone", "phone", "telephone", "mobile"],
    "telephone": ["telephone", "phone", "smartphone", "mobile"],
    "fan": ["fan", "ventilateur", "air cooler", "ventilator"],
    "ventilateur": ["ventilateur", "fan", "air cooler", "ventilator"],
}
CATEGORY_EXCLUDED_TERMS: Dict[str, set[str]] = {
    "laptop": {
        "sticker", "autocollant", "backpack", "sac", "pouch", "cover", "case",
        "protector", "sleeve", "skin", "bag", "projector", "airpod", "clipper",
        "jam", "powder", "oil", "detergent", "gas cooker", "cuisiniere",
    },
    "ordinateur portable": {
        "sticker", "autocollant", "backpack", "sac", "pouch", "cover", "case",
        "protector", "sleeve", "skin", "bag", "projector", "airpod", "clipper",
        "jam", "powder", "oil", "detergent", "gas cooker", "cuisiniere",
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


def _extract_product_data(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        prod_id = product.get("id")
        sku = str(product.get("sku") or "").strip()
        name = str(product.get("name") or "").strip()
        price = float(product.get("price") or 0)
    except Exception:
        return None

    if not prod_id or not sku or not name:
        return None

    return {
        "id": str(prod_id),
        "name": name,
        "sku": sku,
        "price": price,
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
    text_parts = [name]

    direct_description = product.get("description")
    if direct_description is not None:
        text_parts.append(str(direct_description))

    custom_attributes = product.get("custom_attributes")
    if isinstance(custom_attributes, list):
        for attr in custom_attributes:
            if not isinstance(attr, dict):
                continue
            code = str(attr.get("attribute_code") or "").lower()
            if code in {"description", "short_description"}:
                value = attr.get("value")
                if value is not None:
                    text_parts.append(str(value))

    combined = " ".join(text_parts)
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
    if not isinstance(budget, dict):
        return None, None

    def _to_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    min_budget = _to_number(budget.get("min"))
    max_budget = _to_number(budget.get("max"))
    if min_budget is not None and max_budget is not None and min_budget > max_budget:
        min_budget, max_budget = max_budget, min_budget
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
    return filtered


def _to_normalized_tokens(value: str) -> List[str]:
    normalized = _normalize_text_for_keyword_matching(value)
    if not normalized:
        return []
    return [token for token in normalized.split() if len(token) > 1]


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

    return query_terms[:8]


def _score_candidate_product(
    haystack: str,
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

    primary_matches = sum(1 for term in primary_terms if term in haystack)
    if primary_terms and primary_matches == 0:
        return 0.0

    strong_matches = sum(1 for term in strong_terms if term in haystack)
    context_matches = sum(1 for term in context_terms if term in haystack)

    if primary_matches == 0 and strong_matches == 0 and context_matches == 0:
        return 0.0

    return round((primary_matches * 3.0) + (strong_matches * 2.0) + (context_matches * 1.0), 3)


def _rank_products_from_items(
    items: List[Dict[str, Any]],
    structured_query: Dict[str, Any],
    query_keywords: List[str],
) -> List[ProductRecommendation]:
    profile = _build_search_profile(structured_query, query_keywords)
    recommendations: List[ProductRecommendation] = []

    for product in items:
        extracted = _extract_product_data(product)
        if not extracted:
            continue

        haystack = _extract_search_haystack(product, extracted["name"])
        relevance = _score_candidate_product(haystack, profile)
        if relevance <= 0:
            continue
        recommendations.append(
            ProductRecommendation(**extracted, relevance_score=relevance)
        )

    recommendations.sort(
        key=lambda x: x.relevance_score or 0,
        reverse=True,
    )
    return recommendations


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
    )
    if ranked:
        return ranked

    # If no category is known, return loose fallback results instead of empty.
    if not str(structured_query.get("category") or "").strip():
        loose: List[ProductRecommendation] = []
        for product in items:
            extracted = _extract_product_data(product)
            if extracted:
                loose.append(ProductRecommendation(**extracted, relevance_score=None))
        return loose
    return []


async def _process_query_with_unified_ai(input_text: str, language: str) -> Dict[str, Any]:
    normalized_input = re.sub(r"\s+", " ", str(input_text or "").strip())
    if not normalized_input:
        return UnifiedQueryAIService.process_raw_query("", language)

    return await asyncio.to_thread(
        UnifiedQueryAIService.process_raw_query,
        normalized_input,
        language,
    )


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

    headers = {
        "Authorization": f"Bearer {settings.MAGENTO_ACCESS_TOKEN}",
        "Accept": "application/json",
    }

    items: List[Dict[str, Any]] = []

    timeout = httpx.Timeout(
        connect=settings.MAGENTO_TIMEOUT,
        read=settings.MAGENTO_TIMEOUT,
        write=settings.MAGENTO_TIMEOUT,
        pool=settings.MAGENTO_TIMEOUT,
    )

    try:
        async with httpx.AsyncClient(
            headers=headers,
            verify=False,
            timeout=timeout,
            trust_env=False,
        ) as client:
            for page in range(1, max_pages + 1):
                params = {
                    "searchCriteria[currentPage]": page,
                    "searchCriteria[pageSize]": page_size,
                }

                if search_criteria:
                    flat = {}
                    _flatten_search_criteria("searchCriteria", search_criteria, flat)
                    params.update(flat)

                resp = await _get_with_retry(
                    client=client,
                    endpoint=endpoint,
                    params=params,
                    retries=settings.MAGENTO_RETRIES,
                )
                resp.raise_for_status()
                data = resp.json()
                page_items = data.get("items", [])
                items.extend(page_items)

                if len(page_items) < page_size:
                    break
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.warning(
            "Magento product fetch skipped for endpoint %s due to upstream error: %s",
            endpoint,
            exc,
        )
        return []

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
        structured_query = await _process_query_with_unified_ai(
            input_text=message,
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

        recommendations: List[ProductRecommendation] = []
        if query_keywords:
            keyword_items: List[Dict[str, Any]] = []
            seen_product_ids: set[str] = set()
            for keyword in query_keywords:
                items = await fetch_magento_products(
                    search_criteria={
                        "filter_groups": [
                            {
                                "filters": [
                                    {
                                        "field": "name",
                                        "value": f"%{keyword}%",
                                        "condition_type": "like",
                                    }
                                ]
                            }
                        ]
                    },
                    page_size=20,
                    max_pages=1,
                    language=resolved_language,
                )
                for item in items:
                    dedupe_id = str(item.get("id") or item.get("sku") or "").strip()
                    if not dedupe_id or dedupe_id in seen_product_ids:
                        continue
                    seen_product_ids.add(dedupe_id)
                    keyword_items.append(item)

            recommendations = _rank_products_from_items(
                items=keyword_items,
                structured_query=structured_query,
                query_keywords=query_keywords,
            )

        if not recommendations and semantic_query:
            search_criteria = {
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "field": "name",
                                "value": f"%{semantic_query}%",
                                "condition_type": "like",
                            }
                        ]
                    }
                ]
            }
            items = await fetch_magento_products(
                search_criteria=search_criteria,
                page_size=10,
                max_pages=1,
                language=resolved_language,
            )
            if items:
                recommendations = _build_fallback_recommendations(
                    items=items,
                    structured_query=structured_query,
                    query_keywords=query_keywords,
                    semantic_query=semantic_query,
                    language=resolved_language,
                )

        recommendations = _apply_budget_filter(recommendations, structured_query)
        recommendations = _sort_recommendations_for_display(recommendations)

        return ChatResponse(
            message=_format_top_matches_message(
                recommendations=recommendations,
                language=resolved_language,
            ),
            recommendations=recommendations,
        )


    @staticmethod
    async def recommend_products_by_image(
        image: UploadFile,
        user_id: int,
        language: str = "en",
    ) -> ChatResponse:

        try:
            image_bytes = await image.read()
            language = language.strip().lower()

            quality_error = _is_image_quality_poor(image, image_bytes)
            if quality_error:
                return ChatResponse(message=quality_error, recommendations=[])

            # Caption matches catalog language
            if language == "fr":
                caption_data = await ImageCaptionService.generate_caption_fr_from_bytes(
                    image_bytes=image_bytes,
                    content_type=image.content_type,
                )
            else:
                caption_data = await ImageCaptionService.generate_caption_en_from_bytes(
                    image_bytes=image_bytes,
                    content_type=image.content_type,
                )

            if not caption_data["ok"]:
                return ChatResponse(
                    message=caption_data["reason"] or "Image could not be processed",
                    recommendations=[],
                )

            structured_query = await _process_query_with_unified_ai(
                input_text=caption_data["caption"],
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
            if not query_keywords:
                fallback = await ChatService.recommend_products(
                    message=semantic_query,
                    user_id=user_id,
                    language=resolved_language,
                )
                return ChatResponse(
                    message=_format_top_matches_message(
                        recommendations=fallback.recommendations,
                        language=resolved_language,
                        source_label="image",
                    ),
                    recommendations=fallback.recommendations,
                )

            keyword_items: List[Dict[str, Any]] = []
            seen_product_ids: set[str] = set()
            for keyword in query_keywords:
                items = await fetch_magento_products(
                    search_criteria={
                        "filter_groups": [
                            {
                                "filters": [
                                    {
                                        "field": "name",
                                        "value": f"%{keyword}%",
                                        "condition_type": "like",
                                    }
                                ]
                            }
                        ]
                    },
                    page_size=20,
                    max_pages=1,
                    language=resolved_language,
                )
                for item in items:
                    dedupe_id = str(item.get("id") or item.get("sku") or "").strip()
                    if not dedupe_id or dedupe_id in seen_product_ids:
                        continue
                    seen_product_ids.add(dedupe_id)
                    keyword_items.append(item)

            recommendations = _rank_products_from_items(
                items=keyword_items,
                structured_query=structured_query,
                query_keywords=query_keywords,
            )

            recommendations = _apply_budget_filter(recommendations, structured_query)

            if not recommendations:
                fallback = await ChatService.recommend_products(
                    message=semantic_query,
                    user_id=user_id,
                    language=resolved_language,
                )
                recommendations = fallback.recommendations
            recommendations = _sort_recommendations_for_display(recommendations)

            return ChatResponse(
                message=_format_top_matches_message(
                    recommendations=recommendations,
                    language=resolved_language,
                    source_label="image",
                ),
                recommendations=recommendations,
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
                keyword_items: List[Dict[str, Any]] = []
                seen_product_ids: set[str] = set()
                for keyword in query_keywords:
                    items = await fetch_magento_products(
                        search_criteria={
                            "filter_groups": [
                                {
                                    "filters": [
                                        {
                                            "field": "name",
                                            "value": f"%{keyword}%",
                                            "condition_type": "like",
                                        }
                                    ]
                                }
                            ]
                        },
                        page_size=20,
                        max_pages=1,
                        language=resolved_language,
                    )
                    for item in items:
                        dedupe_id = str(item.get("id") or item.get("sku") or "").strip()
                        if not dedupe_id or dedupe_id in seen_product_ids:
                            continue
                        seen_product_ids.add(dedupe_id)
                        keyword_items.append(item)

                recommendations = _rank_products_from_items(
                    items=keyword_items,
                    structured_query=structured_query,
                    query_keywords=query_keywords,
                )
                recommendations = _apply_budget_filter(recommendations, structured_query)
                recommendations = _sort_recommendations_for_display(recommendations)

                if recommendations:
                    return ChatResponse(
                        message=_format_top_matches_message(
                            recommendations=recommendations,
                            language=resolved_language,
                            source_label="audio",
                        ),
                        recommendations=recommendations,
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
    ) -> VideoRecommendationResponse:
        language = _validate_language(language)
        temp_video_path: Optional[str] = None

        try:
            video_bytes = await video.read()
            file_extension = _validate_video_upload(video, video_bytes)

            # Offload file I/O and frame extraction to worker threads.
            temp_video_path = await asyncio.to_thread(
                _save_temp_video_file,
                video_bytes,
                file_extension,
            )

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

            multimodal_query = _build_multimodal_video_query(
                visual_caption=merged_caption,
                audio_caption=audio_caption or None,
                language=language,
            )
            search_caption = multimodal_query["search_caption"]
            structured_query = await _process_query_with_unified_ai(
                input_text=search_caption,
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
                # Primary path: keyword search in Magento derived from the generated caption.
                # Run one query per keyword to broaden coverage and avoid over-constrained filters.
                keyword_items: List[Dict[str, Any]] = []
                seen_product_ids: set[str] = set()
                for keyword in query_keywords:
                    items = await fetch_magento_products(
                        search_criteria={
                            "filter_groups": [
                                {
                                    "filters": [
                                        {
                                            "field": "name",
                                            "value": f"%{keyword}%",
                                            "condition_type": "like",
                                        }
                                    ]
                                }
                            ]
                        },
                        page_size=20,
                        max_pages=1,
                        language=resolved_language,
                    )
                    for item in items:
                        dedupe_id = str(item.get("id") or item.get("sku") or "").strip()
                        if not dedupe_id or dedupe_id in seen_product_ids:
                            continue
                        seen_product_ids.add(dedupe_id)
                        keyword_items.append(item)

                recommendations = _rank_products_from_items(
                    items=keyword_items,
                    structured_query=structured_query,
                    query_keywords=query_keywords,
                )

                recommendations = _apply_budget_filter(recommendations, structured_query)

                # Fallback: phrase search if keyword search yields nothing.
                if not recommendations:
                    fallback = await ChatService.recommend_products(
                        message=semantic_query,
                        user_id=user_id,
                        language=resolved_language,
                    )
                    recommendations = fallback.recommendations
                recommendations = _sort_recommendations_for_display(recommendations)
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
                caption=semantic_query,
                frames_used=len(successful_captions),
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
