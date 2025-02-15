import requests
import re
import random
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

# ✅ Required API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_SAFE_BROWSING_API_KEY = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")
OBLIVIOUS_HTTP_RELAY = os.getenv("OBLIVIOUS_HTTP_RELAY")

# ✅ Validate required environment variables
REQUIRED_ENV_VARS = [OPENAI_API_KEY, GOOGLE_SAFE_BROWSING_API_KEY, OBLIVIOUS_HTTP_RELAY]
if any(var is None for var in REQUIRED_ENV_VARS):
    raise ValueError("❌ Missing one or more required environment variables!")

# ✅ Google Cloud Vision Client
GOOGLE_CLOUD_VISION_CLIENT = vision.ImageAnnotatorClient()

# ✅ Configuration Constants
CACHE_EXPIRY = 6 * 3600  # 6 hours
CENSORED_IMAGE_URL = "/static/images/censored-image.png"
SAFE_BROWSING_API_URL = f"{OBLIVIOUS_HTTP_RELAY}/v4/threatMatches:find?key={GOOGLE_SAFE_BROWSING_API_KEY}"
OPENAI_MODERATION_API_URL = "https://api.openai.com/v1/moderations"

# ✅ Caching
NSFW_IMAGE_CACHE = TTLCache(maxsize=1000, ttl=1800)  # 30 minutes
NSFW_TEXT_CACHE = TTLCache(maxsize=5000, ttl=1800)  # 30 minutes

# ✅ Shared HTTP Session
SESSION = None

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
    "best", "anime", "edit", "dark", "phonk", "bass drop", "remix", r"(\b?:best songs\b)", "remixes", "shoujo", "shonen", "seinen", "josei",
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

async def get_session():
    """Ensure we reuse a single aiohttp session for efficiency."""
    global SESSION
    if SESSION is None:
        SESSION = aiohttp.ClientSession()
    return SESSION

# ✅ Exponential Backoff for API Calls
async def retry_api_call(call_func, retries=3):
    """Retries an API call with exponential backoff."""
    delay = 1  
    for attempt in range(retries):
        try:
            return await call_func()
        except Exception as e:
            logging.warning(f"⚠️ API Error: {e} (Retry {attempt + 1}/{retries})")
            await asyncio.sleep(delay)
            delay *= random.uniform(1.5, 2.5)  
    return False  

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
            "sexual/minors": 0.0001,  
            "harassment/threatening": 0.001,
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

# ✅ NSFW Image Check (Google Vision + OpenAI in Parallel)
async def is_safe_image(image_url: str) -> str:
    """Optimized NSFW check using Google Vision & OpenAI in parallel."""
    if not image_url:
        return CENSORED_IMAGE_URL

    if image_url in NSFW_IMAGE_CACHE:
        return NSFW_IMAGE_CACHE[image_url]

    # ✅ Run both checks in parallel
    google_task = google_cloud_nsfw_check(image_url)
    openai_task = openai_nsfw_image_check(image_url)
    
    google_safe, openai_safe = await asyncio.gather(google_task, openai_task)

    # ✅ Determine final safety status
    result = image_url if google_safe and openai_safe else CENSORED_IMAGE_URL
    NSFW_IMAGE_CACHE[image_url] = result  # ✅ Cache result
    return result

async def google_cloud_nsfw_check(image_url: str) -> bool:
    """Google Cloud Vision API NSFW detection with retries."""
    return await retry_api_call(lambda: _google_cloud_nsfw_check(image_url))

async def _google_cloud_nsfw_check(image_url: str) -> bool:
    """Google Vision NSFW detection logic."""
    try:
        image = vision.Image()
        image.source.image_uri = image_url
        response = GOOGLE_CLOUD_VISION_CLIENT.safe_search_detection(image=image)
        annotations = response.safe_search_annotation

        # ✅ Define Risk Levels
        risk_levels = {"POSSIBLE", "LIKELY", "VERY_LIKELY"}
        if annotations.adult.name in risk_levels or annotations.violence.name in risk_levels:
            return False  # 🚨 NSFW Detected

        return True  
    except Exception as e:
        logging.error(f"❌ Google Cloud Vision API Error: {e}")
        return False  

async def openai_nsfw_image_check(image_url: str) -> bool:
    """OpenAI NSFW Image Moderation with retries."""
    return await retry_api_call(lambda: _openai_nsfw_image_check(image_url))

async def _openai_nsfw_image_check(image_url: str) -> bool:
    """OpenAI NSFW Image Moderation API logic."""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "omni-moderation-latest",
        "input": [{"type": "image_url", "image_url": {"url": image_url}}],
    }

    session = await get_session()
    try:
        async with session.post(OPENAI_MODERATION_API_URL, json=payload, headers=headers) as response:
            data = await response.json()
            return not any(result.get("flagged", False) for result in data.get("results", []))
    except Exception as e:
        logging.error(f"❌ OpenAI Image Moderation Error: {e}")
        return False  