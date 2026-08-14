from google import genai

from app.core.config import get_settings


settings = get_settings()

client = genai.Client(
    api_key=settings.gemini_api_key
)

response = client.models.generate_content(
    model=settings.gemini_model,
    contents=(
        "Return JSON containing "
        "the value 2 + 2."
    ),
)

print(
    response.text
)
