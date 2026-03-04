from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from app.chat.schemas import ChatRequest, ChatResponse, VideoRecommendationResponse
from app.chat.service import ChatService
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
    return await ChatService.recommend_products(
        message=payload.message,
        user_id=current_user.id,
    )


@router.post("/recommend/image", response_model=ChatResponse)
async def recommend_products_by_image(
    image: UploadFile = File(...),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user),
):
    return await ChatService.recommend_products_by_image(
        image=image,
        user_id=current_user.id,
        language=language,
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
    current_user: User = Depends(get_current_user),
):
    return await ChatService.recommend_products_by_video(
        video=video,
        user_id=current_user.id,
        language=language,
    )
