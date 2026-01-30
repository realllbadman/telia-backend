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
