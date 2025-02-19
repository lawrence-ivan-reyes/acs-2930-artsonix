import asyncio
import aiohttp
import logging
import os

# ✅ OpenAI Moderation API Configuration
OPENAI_MODERATION_API_URL = "https://api.openai.com/v1/moderations"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # 🔥 Replace with your actual API key
CENSORED_IMAGE_URL = "/static/images/censored-image.png"

# ✅ List of test images (Include a mix of safe & NSFW images)
TEST_IMAGES = [
    "https://example.com/safe_image.jpg",  # ✅ Completely safe image
    "https://example.com/borderline.jpg",  # ⚠️ Potentially NSFW
    "https://example.com/explicit.jpg",    # ❌ Explicit content
    "https://example.com/artistic.jpg",    # 🎨 Artistic nudity (edge case)
    "https://example.com/cartoon.jpg",     # 🎭 Animated content (edge case)
]

async def is_safe_image(image_url: str) -> str:
    """Uses OpenAI Moderation API for NSFW image filtering."""
    if not image_url:
        return CENSORED_IMAGE_URL  # ✅ Default to censored if no URL

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "omni-moderation-latest",
        "input": [{"type": "image_url", "image_url": {"url": image_url}}],
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(OPENAI_MODERATION_API_URL, json=payload, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()

                # ✅ If flagged, return the censored image
                if any(result.get("flagged", False) for result in data.get("results", [])):
                    logging.warning(f"❌ NSFW Image Blocked: {image_url}")
                    return CENSORED_IMAGE_URL
                
                return image_url  # ✅ Return original if safe

        except Exception as e:
            logging.error(f"❌ OpenAI Image Moderation Error: {e}")
            return CENSORED_IMAGE_URL  # 🔥 Default to censored if API call fails

async def test_openai_moderation():
    """Runs OpenAI moderation test on sample images."""
    results = await asyncio.gather(*(is_safe_image(url) for url in TEST_IMAGES))
    
    for img, result in zip(TEST_IMAGES, results):
        print(f"🔎 Image: {img}\n🛡️ Result: {result}\n{'-'*40}")

# ✅ Run Test
if __name__ == "__main__":
    asyncio.run(test_openai_moderation())