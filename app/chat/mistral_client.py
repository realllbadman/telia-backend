from mistralai import Mistral
from app.config import settings


class MistralService:
    def __init__(self):
        self.client = Mistral(api_key=settings.MISTRAL_API_KEY)

    def analyze_caption(self, caption: str) -> str:
        response = self.client.chat.completions.create(
            model=settings.MISTRAL_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "The following description was generated from an image:\n\n"
                        f"\"{caption}\"\n\n"
                        "Based on this, identify the product or object "
                        "and give a concise, useful search-friendly description."
                    ),
                }
            ],
            max_tokens=60,
        )

        return response.choices[0].message.content.strip()
