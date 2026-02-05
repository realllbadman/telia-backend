import asyncio
import base64
import unicodedata
from typing import Dict, Optional

from fastapi import UploadFile
import httpx
from mistralai import Mistral

from app.config import settings


class ImageCaptionService:
    # -------------------------------
    # Internal shared engine
    # -------------------------------
    @staticmethod
    async def _generate_caption_internal(
        image_bytes: bytes,
        content_type: str,
        language: str,
    ) -> Dict[str, Optional[str]]:

        # Hard stop to prevent silent vision failures
        if not image_bytes:
            return {
                "ok": False,
                "caption": None,
                "reason": "Empty image data received",
            }

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        if language == "fr":
            prompt = """
Vous etes un assistant pour un moteur de recherche de commerce electronique.
Repondez uniquement en francais.

Fournissez toujours :
QUALITE : BONNE
CATEGORIE : <une categorie claire comme chaussures, telephone, sac, chemise, ventilateur>
TITRE : <titre descriptif court>
ATTRIBUTS : <couleur, materiau, sexe, type>

Si l'image est floue ou peu claire :
QUALITE : MAUVAISE
RAISON : <raison courte>

NE DEVINEZ PAS. Fournissez exactement ces champs.
"""
        else:
            prompt = """
You are an assistant for an e-commerce search engine.
Respond only in English.

Always provide:
QUALITY: GOOD
CATEGORY: <clear product category like shoes, phone, bag, shirt, fan>
TITLE: <short descriptive title>
ATTRIBUTES: <color, material, gender, type>

If the image is unclear:
QUALITY: BAD
REASON: <short reason>

Do NOT guess. Provide exactly these fields.
"""

        response = await _mistral_complete_with_retry(
            client=client,
            model=settings.MISTRAL_VISION_MODEL,
            prompt=prompt,
            content_type=content_type,
            image_b64=image_b64,
            retries=settings.MISTRAL_RETRIES,
        )

        content = response.choices[0].message.content.strip()

        def _strip_accents(value: str) -> str:
            return "".join(
                ch for ch in unicodedata.normalize("NFKD", value)
                if not unicodedata.combining(ch)
            )

        def _norm(value: str) -> str:
            return _strip_accents(value).upper().strip()

        is_bad = False
        reason = ""
        category = ""
        title = ""
        attributes = ""

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if ":" not in line:
                continue
            left, right = line.split(":", 1)
            key = _norm(left)
            value = right.strip()
            value_norm = _norm(value)

            if key in {"QUALITY", "QUALITE"}:
                if value_norm.startswith("BAD") or value_norm.startswith("MAUVAISE"):
                    is_bad = True
            elif key in {"CATEGORY", "CATEGORIE"}:
                category = value
            elif key in {"TITLE", "TITRE"}:
                title = value
            elif key in {"ATTRIBUTES", "ATTRIBUTS"}:
                attributes = value
            elif key in {"REASON", "RAISON"}:
                reason = value

        if is_bad:
            return {
                "ok": False,
                "caption": None,
                "reason": reason or "Image quality too low",
            }

        if not any([category, title, attributes]):
            return {
                "ok": False,
                "caption": None,
                "reason": "Caption could not be parsed",
            }

        caption = " ".join(filter(None, [category, title, attributes]))

        return {"ok": True, "caption": caption, "reason": None}

    # -------------------------------
    # Byte-based (recommended)
    # -------------------------------
    @staticmethod
    async def generate_caption_en_from_bytes(
        image_bytes: bytes,
        content_type: str,
    ):
        return await ImageCaptionService._generate_caption_internal(
            image_bytes=image_bytes,
            content_type=content_type,
            language="en",
        )

    @staticmethod
    async def generate_caption_fr_from_bytes(
        image_bytes: bytes,
        content_type: str,
    ):
        return await ImageCaptionService._generate_caption_internal(
            image_bytes=image_bytes,
            content_type=content_type,
            language="fr",
        )

    # -------------------------------
    # UploadFile wrappers (unsafe if reused)
    # -------------------------------
    @staticmethod
    async def generate_caption_en(image: UploadFile):
        image_bytes = await image.read()
        return await ImageCaptionService.generate_caption_en_from_bytes(
            image_bytes=image_bytes,
            content_type=image.content_type,
        )

    @staticmethod
    async def generate_caption_fr(image: UploadFile):
        image_bytes = await image.read()
        return await ImageCaptionService.generate_caption_fr_from_bytes(
            image_bytes=image_bytes,
            content_type=image.content_type,
        )


async def _mistral_complete_with_retry(
    client: Mistral,
    model: str,
    prompt: str,
    content_type: str,
    image_b64: str,
    retries: int,
):
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return client.chat.complete(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{image_b64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=120,
            )
        except (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ReadError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            backoff = 0.5 * (2 ** attempt)
            await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc
