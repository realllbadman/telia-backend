from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.chat.schemas import ChatRequest, ChatResponse
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
