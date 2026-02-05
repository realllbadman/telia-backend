from mistralai import Mistral
from app.config import settings


class MistralService:
    def __init__(self):
        self.client = Mistral(api_key=settings.MISTRAL_API_KEY)

    def analyze_caption(self, caption: str) -> str:
        prompt = f"""
You are optimizing text for an e-commerce product search engine.

Original image description:
"{caption}"

Rewrite this into a short, precise, search-friendly product description.
Do NOT add new details. Do NOT guess.
"""

        response = self.client.chat.complete(
            model=settings.MISTRAL_TEXT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=60,
        )

        return response.choices[0].message.content.strip()
