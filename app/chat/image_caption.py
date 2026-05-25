import asyncio
import base64
import hashlib
import re
import time
import unicodedata
from collections import OrderedDict
from typing import Dict, Optional

from fastapi import UploadFile
import httpx
from mistralai import Mistral

from app.config import settings

# Singleton Mistral client — one SSL connection, reused for every caption request
_MISTRAL_CLIENT: Optional[Mistral] = None

def _get_mistral_client() -> Mistral:
    global _MISTRAL_CLIENT
    if _MISTRAL_CLIENT is None:
        _MISTRAL_CLIENT = Mistral(api_key=settings.MISTRAL_API_KEY)
    return _MISTRAL_CLIENT


_CAPTION_CACHE_TTL_SECONDS = 300
_CAPTION_CACHE_MAX_ITEMS = 512
_CAPTION_CACHE: "OrderedDict[str, tuple[float, Dict[str, object]]]" = OrderedDict()
_CAPTION_CACHE_LOCK = asyncio.Lock()
_CAPTION_INFLIGHT: Dict[str, asyncio.Future] = {}


def _build_caption_cache_key(
    image_bytes: bytes,
    content_type: str,
    language: str,
) -> str:
    digest = hashlib.sha256(image_bytes).hexdigest()
    content_type_key = content_type or ""
    model_key = settings.MISTRAL_VISION_MODEL
    return f"{language}:{content_type_key}:{model_key}:{digest}"


def _get_cached_caption(cache_key: str, now: float) -> Optional[Dict[str, object]]:
    if _CAPTION_CACHE_TTL_SECONDS <= 0:
        return None
    cached = _CAPTION_CACHE.get(cache_key)
    if not cached:
        return None
    expires_at, value = cached
    if expires_at <= now:
        _CAPTION_CACHE.pop(cache_key, None)
        return None
    _CAPTION_CACHE.move_to_end(cache_key)
    return value


def _set_cached_caption(cache_key: str, value: Dict[str, object], now: float) -> None:
    if _CAPTION_CACHE_TTL_SECONDS <= 0:
        return
    expires_at = now + _CAPTION_CACHE_TTL_SECONDS
    _CAPTION_CACHE[cache_key] = (expires_at, value)
    _CAPTION_CACHE.move_to_end(cache_key)
    while len(_CAPTION_CACHE) > _CAPTION_CACHE_MAX_ITEMS:
        _CAPTION_CACHE.popitem(last=False)


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

        cache_key = _build_caption_cache_key(
            image_bytes=image_bytes,
            content_type=content_type,
            language=language,
        )
        loop = asyncio.get_running_loop()
        inflight_future: Optional[asyncio.Future] = None
        owner = False
        now = time.monotonic()
        async with _CAPTION_CACHE_LOCK:
            cached = _get_cached_caption(cache_key, now)
            if cached is not None:
                return cached
            inflight_future = _CAPTION_INFLIGHT.get(cache_key)
            if inflight_future is None or inflight_future.done():
                inflight_future = loop.create_future()
                _CAPTION_INFLIGHT[cache_key] = inflight_future
                owner = True

        if not owner and inflight_future is not None:
            return await inflight_future

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        client = _get_mistral_client()

        if language == "fr":
            prompt = """
Vous etes un assistant expert en identification de produits pour un moteur de recherche e-commerce.
Repondez uniquement en francais.

Analysez l'image et fournissez exactement ces champs :
QUALITE : BONNE
CATEGORIE : <categorie precise : smartphone, ordinateur portable, ventilateur, casque audio, tablette, television, appareil photo, chaussures, sac, chemise, ou autre>
TITRE : <marque + modele exact si visible + type de produit. Exemples: "Samsung Galaxy A15 smartphone noir", "Nike Air Max 270 chaussures running homme", "HP Pavilion 15 ordinateur portable", "ventilateur de table Rowenta silencieux 3 vitesses">
ATTRIBUTS : <toutes les specifications visibles et recherchables separees par des virgules. Exemples electronique: "noir, 128 Go, ecran AMOLED 6.5 pouces, double SIM, 5G". Exemples vetements: "blanc, coton, taille M, manches longues, homme". Exemples electromenager: "blanc, 40W, 3 vitesses, oscillation, minuterie, diametre 40cm">
PRODUITS_VISIBLES : <autres produits secondaires clairement visibles avec leurs caracteristiques, ou aucun>

Regles strictes :
- CATEGORIE et TITRE doivent correspondre exactement au produit principal (le plus centre, net ou mis en avant).
- Si la marque ET le modele sont clairement lisibles sur le produit, incluez-les tous les deux dans TITRE.
- ATTRIBUTS = toutes les specifications concretes et recherchables que vous pouvez voir, separees par des virgules. Plus c'est detaille, mieux c'est.
- Pour l'electronique : couleur, capacite stockage, taille ecran, connectivite, generation (4G/5G), caracteristiques speciales.
- Pour les vetements/chaussures : couleur, genre, taille, matiere, type (running, casual, formel), saison.
- Pour l'electromenager : couleur, puissance (W), dimensions, fonctionnalites, capacite.
- Ignorez les personnes et arriere-plans sauf s'ils SONT le produit.

Si l'image est floue, trop sombre ou le produit non identifiable :
QUALITE : MAUVAISE
RAISON : <raison courte>

NE DEVINEZ PAS. Fournissez exactement ces champs avec un maximum de detail.
"""
        else:
            prompt = """
You are an expert product identification assistant for an e-commerce search engine.
Respond only in English.

Analyze the image and provide exactly these fields:
QUALITY: GOOD
CATEGORY: <precise category: smartphone, laptop, fan, headphones, tablet, television, camera, shoes, bag, shirt, or other>
TITLE: <brand + exact model if visible + product type. Examples: "Samsung Galaxy A15 smartphone black", "Nike Air Max 270 running shoes men", "HP Pavilion 15 laptop", "Rowenta table fan 3-speed silent">
ATTRIBUTES: <all visible and searchable specifications separated by commas. Electronics examples: "black, 128GB, 6.5 inch AMOLED screen, dual SIM, 5G". Clothing examples: "white, cotton, size M, long sleeves, men". Appliance examples: "white, 40W, 3 speeds, oscillation, timer, 40cm diameter">
ALSO_VISIBLE_PRODUCTS: <other clearly visible secondary products with their characteristics, or none>

Strict rules:
- CATEGORY and TITLE must describe the primary product (most centered, sharpest, or most prominent).
- If brand AND model are clearly readable on the product, include both in TITLE.
- ATTRIBUTES = all concrete searchable specs you can see, separated by commas. More detail is better.
- For electronics: color, storage capacity, screen size, connectivity, generation (4G/5G), special features.
- For clothing/shoes: color, gender, size, material, type (running, casual, formal), season.
- For appliances: color, wattage, dimensions, features, capacity.
- Ignore people and backgrounds unless they ARE the product being sold.

If the image is blurry, too dark, or the product cannot be identified:
QUALITY: BAD
REASON: <short reason>

Do NOT guess. Provide exactly these fields with as much detail as possible.
"""

        def _strip_accents(value: str) -> str:
            return "".join(
                ch for ch in unicodedata.normalize("NFKD", value)
                if not unicodedata.combining(ch)
            )

        def _norm(value: str) -> str:
            return _strip_accents(value).upper().strip()

        def _normalize_product_list(value: str) -> str:
            cleaned = re.sub(r"\s+", " ", str(value or "").strip())
            if not cleaned:
                return ""

            if _norm(cleaned) in {"NONE", "N/A", "NA", "AUCUN", "AUCUNE", "RIEN"}:
                return ""

            parts = [
                re.sub(r"\s+", " ", part).strip(" ,.;")
                for part in re.split(r"[;,]", cleaned)
            ]
            deduped: list[str] = []
            seen: set[str] = set()
            for part in parts:
                if not part:
                    continue
                normalized_part = _norm(part)
                if normalized_part in {"NONE", "N/A", "NA", "AUCUN", "AUCUNE", "RIEN"}:
                    continue
                if normalized_part in seen:
                    continue
                seen.add(normalized_part)
                deduped.append(part)

            return ", ".join(deduped[:4])

        def _limit_caption_words(value: str, max_words: int = 15) -> str:
            cleaned = re.sub(r"\s+", " ", str(value or "").strip(" ,.;"))
            if not cleaned:
                return ""
            words = cleaned.split()
            if len(words) <= max_words:
                return cleaned
            return " ".join(words[:max_words]).strip(" ,.;")

        try:
            response = await _mistral_complete_with_retry(
                client=client,
                model=settings.MISTRAL_VISION_MODEL,
                prompt=prompt,
                content_type=content_type,
                image_b64=image_b64,
                retries=settings.MISTRAL_RETRIES,
            )

            content = response.choices[0].message.content.strip()

            is_bad = False
            reason = ""
            category = ""
            title = ""
            attributes = ""
            also_visible_products = ""

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
                elif key in {"CATEGORY", "CATEGORIE", "PRIMARY_CATEGORY", "CATEGORIE_PRINCIPALE"}:
                    category = value
                elif key in {"TITLE", "TITRE", "PRIMARY_TITLE", "TITRE_PRINCIPAL"}:
                    title = value
                elif key in {"ATTRIBUTES", "ATTRIBUTS", "PRIMARY_ATTRIBUTES", "ATTRIBUTS_PRINCIPAUX"}:
                    attributes = value
                elif key in {
                    "ALSO_VISIBLE_PRODUCTS",
                    "PRODUITS_VISIBLES",
                    "SECONDARY_PRODUCTS",
                    "AUTRES_PRODUITS",
                }:
                    also_visible_products = value
                elif key in {"REASON", "RAISON"}:
                    reason = value

            if is_bad:
                result = {
                    "ok": False,
                    "caption": None,
                    "reason": reason or "Image quality too low",
                    "category": None,
                    "title": None,
                    "attributes": None,
                    "also_visible_products": None,
                }
            elif not any([category, title, attributes]):
                result = {
                    "ok": False,
                    "caption": None,
                    "reason": "Caption could not be parsed",
                    "category": None,
                    "title": None,
                    "attributes": None,
                    "also_visible_products": None,
                }
            else:
                also_visible_products = _normalize_product_list(also_visible_products)
                caption_parts = [category, title, attributes]
                if also_visible_products:
                    caption_parts.append(also_visible_products)
                caption = " ".join(filter(None, caption_parts))
                caption = _limit_caption_words(caption, 60)

                result = {
                    "ok": True,
                    "caption": caption,
                    "reason": None,
                    "category": category,
                    "title": title,
                    "attributes": attributes,
                    "also_visible_products": also_visible_products or None,
                }

            if owner and inflight_future is not None:
                if result.get("ok"):
                    async with _CAPTION_CACHE_LOCK:
                        _set_cached_caption(cache_key, result, time.monotonic())
                inflight_future.set_result(result)
            return result
        except Exception as exc:
            if owner and inflight_future is not None and not inflight_future.done():
                inflight_future.set_exception(exc)
                _ = inflight_future.exception()
            raise
        finally:
            if owner and inflight_future is not None:
                async with _CAPTION_CACHE_LOCK:
                    if _CAPTION_INFLIGHT.get(cache_key) is inflight_future:
                        _CAPTION_INFLIGHT.pop(cache_key, None)

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
    messages = [
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
    ]
    for attempt in range(retries + 1):
        try:
            # Use native async API — no thread pool, no extra SSL handshake
            return await client.chat.complete_async(
                model=model,
                messages=messages,
                max_tokens=400,
            )
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            backoff = 0.5 * (2 ** attempt)
            await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc
