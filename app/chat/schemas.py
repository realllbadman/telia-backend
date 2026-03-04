from pydantic import BaseModel, Field
from typing import List, Optional


class ChatRequest(BaseModel):
    message: str


class ProductRecommendation(BaseModel):
    id: str
    name: str
    sku: str
    price: float
    relevance_score: Optional[float] = None


class ChatResponse(BaseModel):
    message: str
    recommendations: List[ProductRecommendation] = Field(default_factory=list)


class VideoRecommendationResponse(BaseModel):
    ok: bool = True
    language: str
    source: str = "video"
    caption: str
    frames_used: int
    products: List[ProductRecommendation] = Field(default_factory=list)
