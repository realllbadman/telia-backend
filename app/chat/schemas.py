from pydantic import BaseModel, Field
from typing import List, Optional


class ChatRequest(BaseModel):
    message: str
    language: str = "en"


class ProductRecommendation(BaseModel):
    id: str
    name: str
    sku: str
    price: float
    image: Optional[str] = None
    image_url: Optional[str] = None
    caption: Optional[str] = None
    relevance_score: Optional[float] = None


class ProductGroup(BaseModel):
    """One category slice returned from a grouped multi-intent search."""
    category: str
    products: List[ProductRecommendation] = Field(default_factory=list)


class ChatResponse(BaseModel):
    message: str
    recommendations: List[ProductRecommendation] = Field(default_factory=list)
    caption: Optional[str] = None
    # Grouped results for multi-intent queries (image + text).
    # Each entry is one query's results in search order.
    # Empty list when only a single query was run.
    groups: List["ProductGroup"] = Field(default_factory=list)


class VideoRecommendationResponse(BaseModel):
    ok: bool = True
    language: str
    source: str = "video"
    caption: str
    frames_used: int
    products: List[ProductRecommendation] = Field(default_factory=list)


class MediaRecommendationResponse(BaseModel):
    source: str
    message: str = ""
    recommendations: List[ProductRecommendation] = Field(default_factory=list)
    caption: Optional[str] = None
    frames_used: Optional[int] = None
