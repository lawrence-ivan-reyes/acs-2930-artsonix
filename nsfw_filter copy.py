import requests
import re
import os
import logging
import openai
import time
import asyncio
import aiohttp
import html
from dotenv import load_dotenv
from collections import deque
from cachetools import TTLCache
from google.cloud import vision
import urllib.parse
from rapidfuzz import fuzz

# Load environment variables
load_dotenv()

# API Keys and Configurations
OPENAI_MODERATION_API_URL = "https://api.openai.com/v1/moderations"
OBLIVIOUS_HTTP_RELAY = os.getenv("OBLIVIOUS_HTTP_RELAY")
GOOGLE_SAFE_BROWSING_API_KEY = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# ✅ Google Cloud Vision API Configuration
GOOGLE_CLOUD_VISION_CLIENT = vision.ImageAnnotatorClient()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
CACHE_EXPIRY = 6 * 3600  # Cache expiry in seconds (6 hours)
OPENAI_RATE_LIMIT = 500

# ✅ Rate Limits & Caching
OPENAI_REQUEST_COUNT = 0
LAST_OPENAI_RESET = time.time()
NSFW_IMAGE_CACHE = TTLCache(maxsize=1000, ttl=1800)  # 30 min cache

# ✅ Safe Browsing API Endpoint
SAFE_BROWSING_API_URL = f"{OBLIVIOUS_HTTP_RELAY}/v4/threatMatches:find?key={GOOGLE_SAFE_BROWSING_API_KEY}"

# ✅ Replacement Image for NSFW content
CENSORED_IMAGE_URL = "/static/images/censored-image.png"

# ✅ Rate limit tracker
REQUEST_LOG = deque(maxlen=500)

# ✅ **Likelihood Enum Mapping**
LIKELIHOOD_MAPPING = {
    vision.Likelihood.UNKNOWN: "UNKNOWN",
    vision.Likelihood.VERY_UNLIKELY: "VERY_UNLIKELY",
    vision.Likelihood.UNLIKELY: "UNLIKELY",
    vision.Likelihood.POSSIBLE: "POSSIBLE",
    vision.Likelihood.LIKELY: "LIKELY",
    vision.Likelihood.VERY_LIKELY: "VERY_LIKELY",
}

# ✅ Whitelisted Phrases (Allowed Content)
WHITELIST_TERMS = [
    "best", "anime", "edit", "dark", "phonk", "bass drop", "remix", r"(\b?:best songs\b)", "remixes", "shoujo"
    "weekly updates", "top anime song", "OST", "opening", "gym", "workout", "study", "chill", "relax", "lofi", "vibes", "vibe",
    "ending", "BGM", "OP", "ED", "JJk", "One Piece", "MHA", "soundtrack", "soundtracks", "music", "songs", "song", "playlist", "playlists",
    "Demon Slayer", "SNK", "Naruto", "Chainsaw Man", "Yoasobi", "gym", "gym anime", "gym rage", "gym workout", "gym music", "gym playlist", "phonk", "phonk playlist",
    "DBZ", "HXH", "Jojo", "Tokyo Ghoul", "Attack on Titan", "rage", "rage music", "rage playlist", "anime rage", "anime rage music", "anime rage playlist",
    "My Hero Academia", "main character", "boss battle", "Walter White", "chill", "sleep", "study", "hoe (tool)", "rap (music genre)", r"(\b?:play|playing\b)", 
]

WHITELIST_ARTISTS = {
    "Drake", "Eminem", "Kanye West", "Beyoncé", "Aimer", "Yoasobi", "Ariana Grande", 
    "Taylor Swift", "The Weeknd", "Bruno Mars", "Billie Eilish", "Doja Cat",
    "Kenshi Yonezu", "Lisa", "Radwimps", "King Gnu", "Vaundy"
}

# ✅ Expanded NSFW List (English + Japanese + Romanji)
BLOCKLIST_TERMS = [
    "badwords1", "badwords2",
]

BAD_PHRASES = { "badphrase1", "badphrase2", "badphrase3"}

# ✅ **🔹 Safe URL Check (Google Safe Browsing)**
async def is_safe_url(url: str) -> bool:
    """Uses Google Safe Browsing API to check if a URL is malicious."""
    if not GOOGLE_SAFE_BROWSING_API_KEY or not url:
        return True  # Assume safe if API key is missing

    payload = {
        "client": {"clientId": "nsfw-filter", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(SAFE_BROWSING_API_URL, json=payload) as response:
                data = await response.json()
                return "matches" not in data  # ✅ Safe if no matches found
        except Exception:
            return True  # Assume safe if API fails

# ✅ **🔹 Keyword-Based NSFW Filtering (Titles & Descriptions Only)**
async def keyword_filter(text: str) -> bool:
    """First-pass keyword filtering against a predefined blocklist."""
    if not text:
        return True  

    text = html.unescape(text).strip().lower()

    # ✅ **Blocklist Check**
    if any(word in text for word in BLOCKLIST_TERMS) or any(phrase in text for phrase in BAD_PHRASES):
        return False  

    return True  

# ✅ **🔹 OpenAI NSFW Check (Second-Pass)**
async def openai_nsfw_filter(text: str) -> bool:
    """Uses OpenAI Moderation API as the final NSFW text check."""
    payload = {
        "model": "omni-moderation-latest",
        "input": [{"type": "text", "text": text}],
        "thresholds": {  
            "sexual": 0.001,  
            "child_exploitation": 0.0001,  
            "non_consensual": 0.001,
        }
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://api.openai.com/v1/moderations",
                json=payload,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            ) as response:
                data = await response.json()
                return not any(result.get("flagged", False) for result in data.get("results", []))
        except Exception:
            return True  # Assume safe if API fails

# ✅ **🔹 Final Multi-Pass NSFW Text Filter**
async def is_safe_content(text: str) -> bool:
    """Applies keyword filtering first, then OpenAI NSFW check."""
    if not await keyword_filter(text):
        return False  
    return await openai_nsfw_filter(text)

# ✅ **Google Cloud Vision NSFW Check**
async def is_safe_image(image_url: str) -> str:
    """Uses Google Cloud Vision API first, then OpenAI for NSFW image detection."""
    if not image_url:
        return CENSORED_IMAGE_URL  

    # ✅ **Check Cache First**
    if image_url in NSFW_IMAGE_CACHE:
        return NSFW_IMAGE_CACHE[image_url]

    # ✅ **First Pass: Google Cloud Vision API**
    if await google_cloud_nsfw_check(image_url):
        NSFW_IMAGE_CACHE[image_url] = image_url
        return image_url  # ✅ Safe image
    else:
        logging.warning(f"⚠️ NSFW Image Detected by Google Cloud Vision: {image_url}")

    # ✅ **Second Pass: OpenAI (If Google Vision flags or fails)**
    if await openai_nsfw_image_check(image_url):
        NSFW_IMAGE_CACHE[image_url] = image_url
        return image_url  # ✅ Safe after both checks
    else:
        logging.warning(f"⚠️ NSFW Image Detected by OpenAI: {image_url}")

    # ✅ **Blocked Image**
    NSFW_IMAGE_CACHE[image_url] = CENSORED_IMAGE_URL
    return CENSORED_IMAGE_URL

# ✅ **Google Cloud Vision NSFW Check**
async def google_cloud_nsfw_check(image_url: str) -> bool:
    """Uses Google Cloud Vision API to detect explicit content in images."""
    try:
        image = vision.Image()
        image.source.image_uri = image_url
        response = GOOGLE_CLOUD_VISION_CLIENT.safe_search_detection(image=image)
        annotations = response.safe_search_annotation

        # ✅ Convert Enum Values to Readable Text
        adult_likelihood = LIKELIHOOD_MAPPING.get(annotations.adult, "POSSIBLE")
        violence_likelihood = LIKELIHOOD_MAPPING.get(annotations.violence, "UNKNOWN")
        racy_likelihood = LIKELIHOOD_MAPPING.get(annotations.racy, "POSSIBLE")

        logging.info(f"🔎 Google Vision Results -> Adult: {adult_likelihood}, Violence: {violence_likelihood}, Racy: {racy_likelihood}")

        # ✅ Define Risk Thresholds
        risk_levels = {"POSSIBLE", "LIKELY", "VERY_LIKELY"}
        if adult_likelihood in risk_levels or violence_likelihood in risk_levels or racy_likelihood in risk_levels:
            return False  # 🚨 Flagged as NSFW

        return True  # ✅ Safe

    except Exception as e:
        logging.error(f"❌ Google Cloud Vision API Error: {e}")
        return True  # ✅ Assume safe if API fails

# ✅ **OpenAI NSFW Image Check**
async def openai_nsfw_image_check(image_url: str) -> bool:
    """Uses OpenAI Omni Moderation API to detect explicit content in an image."""
    if not image_url:
        return True  # Assume safe if no image URL

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    # ✅ Encode URL to avoid bad requests
    encoded_url = urllib.parse.quote(image_url, safe=':/')

    payload = {
        "model": "omni-moderation-latest",
        "input": [
            {
                "type": "image_url",
                "image_url": {
                    "url": encoded_url  # ✅ Ensure URL is properly formatted
                }
            }
        ],
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(OPENAI_MODERATION_API_URL, json=payload, headers=headers) as response:
                if response.status == 400:
                    logging.error(f"❌ OpenAI Bad Request: Check Payload Structure! URL: {image_url}")
                    return True  # Assume safe if API fails due to bad request

                response.raise_for_status()
                data = await response.json()

                # ✅ Check if NSFW detected
                if any(result.get("flagged", False) for result in data.get("results", [])):
                    logging.warning(f"❌ NSFW Image Blocked by OpenAI: {image_url}")
                    return False  # NSFW Detected

                return True  # ✅ Safe Image

        except Exception as e:
            logging.error(f"❌ OpenAI Image Moderation Error: {e}")
            return True  # Assume safe if API fails