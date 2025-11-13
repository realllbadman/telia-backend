from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="Glotelho API",
    description="AI-powered e-commerce backend with Gemini & Magento 2",
    version="1.0.0"
)

@app.get("/")
def home():
    return {
        "message": "Welcome, I\'m Telia"
    }