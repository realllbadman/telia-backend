import base64
from mistralai import Mistral
from app.config import settings
from fastapi import UploadFile


class ImageCaptionService:
    @staticmethod
    async def generate_caption(image: UploadFile) -> str:
        image_bytes = await image.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        response = client.chat.complete(
            model=settings.MISTRAL_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this product for e-commerce search"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image.content_type};base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=80,
        )

        return response.choices[0].message.content.strip()
