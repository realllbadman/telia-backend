from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="Glotelho API",
    description="AI-powered e-commerce backend with Gemini & Magento 2",
    version="1.0.0"
)

# Sample product model (like what Telia recommends!)
class ProductRecommendation(BaseModel):
    name: str
    price: float
    specs: dict
    reason: str
    in_stock: bool = True

@app.get("/")
def home():
    return {"message": "Welcome to Glotelho! Ask Telia for a phone under 100,000 FCFA 📱"}

@app.post("/recommend", response_model=ProductRecommendation)
def recommend_product(budget: float, use_case: str):
    # Mock AI logic (in real app: call Gemini!)
    if use_case.lower() == "content creator" and budget >= 95000:
        return ProductRecommendation(
            name="Tecno Camon 30",
            price=95000,
            specs={"camera": "64MP", "storage": "256GB"},
            reason="Great for vlogging & social media!"
        )
    return ProductRecommendation(
        name="Itel A70",
        price=45000,
        specs={"storage": "128GB", "battery": "5000mAh"},
        reason="Budget king for everyday use!"
    )