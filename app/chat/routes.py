from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from app.chat.schemas import (
    ChatRequest,
    ChatResponse,
    MediaRecommendationResponse,
    VideoRecommendationResponse,
)
from app.chat.service import ChatService
from app.chat.smart_query import smart_rewrite_query
from app.auth.dependencies import get_current_user
from app.models import User

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/recommend", response_model=ChatResponse)
async def recommend_products(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    result = await smart_rewrite_query(payload.message, payload.language)
    enriched_message = result["joined"]

    print("SMART QUERIES:", result["queries"])
    print("ENRICHED MESSAGE:", result["joined"])

    return await ChatService.recommend_products(
        message=enriched_message,
        user_id=current_user.id,
        language=payload.language,
    )


@router.post("/recommend/image", response_model=ChatResponse)
async def recommend_products_by_image(
    image: UploadFile = File(...),
    language: str = Form("en"),
    user_hint: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    return await ChatService.recommend_products_by_image(
        image=image,
        user_id=current_user.id,
        language=language,
        user_hint=user_hint,
    )


@router.post("/recommend/audio", response_model=ChatResponse)
async def recommend_products_by_audio(
    request: Request,
    audio: UploadFile = File(...),
    language: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    resolved_language = language or request.query_params.get("language")
    if not resolved_language:
        raise HTTPException(
            status_code=422,
            detail="language is required (en or fr)",
        )

    return await ChatService.recommend_products_by_audio(
        audio=audio,
        user_id=current_user.id,
        language=resolved_language,
    )


@router.post("/recommend/video", response_model=VideoRecommendationResponse)
async def recommend_products_by_video(
    video: UploadFile = File(...),
    language: str = Form(...),
    user_hint: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    return await ChatService.recommend_products_by_video(
        video=video,
        user_id=current_user.id,
        language=language,
        user_hint=user_hint,
    )


@router.post("/recommend/media", response_model=MediaRecommendationResponse)
async def recommend_products_by_media(
    media: UploadFile = File(...),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user),
):
    return await ChatService.recommend_products_by_media(
        media=media,
        user_id=current_user.id,
        language=language,
    )


@router.post("/typesense/sync")
async def sync_typesense_catalog(
    recreate: bool = False,
    _current_user: User = Depends(get_current_user),
):
    """
    Index all Magento products into Typesense for fast search.
    Call this once after setup, then periodically to keep the index fresh.
    Pass recreate=true to drop and rebuild the collection from scratch.
    """
    from app.typesense_sync import sync_all
    result = await sync_all(force_recreate=recreate)
    return result


@router.get("/typesense/status")
async def typesense_status(
    _current_user: User = Depends(get_current_user),
):
    """Check Typesense connectivity and collection document count."""
    from app.typesense_client import get_typesense_client
    from app.config import settings
    import asyncio

    client = get_typesense_client()
    if client is None:
        return {"status": "not_configured", "documents": 0}
    try:
        info = await asyncio.to_thread(
            client.collections[settings.TYPESENSE_COLLECTION].retrieve
        )
        return {
            "status": "ok",
            "documents": info.get("num_documents", 0),
            "collection": settings.TYPESENSE_COLLECTION,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "documents": 0}
