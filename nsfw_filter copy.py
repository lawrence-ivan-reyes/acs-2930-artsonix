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
    "best", "anime", "edit", "dark", "phonk", "bass drop", "remix", r"(\b?:best songs\b)", "remixes", "shoujo", "shonen", "seinen", "josei", "hardstyle", "hardcore", "dubstep", "trap", "trance", "EDM", "electronic", "electro", "house", "techno", "rave", "rave music", "rave playlist", "Christmas", "Christmas music", "Christmas playlist", "Christmas songs", "Christmas carols", "Christmas vibes", "Christmas lofi", "Christmas chill", "Christmas rage", "Christmas rap", "Christmas hip hop", "Christmas EDM", "Christmas dubstep", "Christmas trap", "Christmas techno", "Christmas house", "Christmas electronic",
    "weekly updates", "top anime song", "OST", "opening", "gym", "workout", "study", "chill", "relax", "lofi", "vibes", "vibe", "nostalgiacore", "nostalgia", "nostalgic", "nostalgic music", "nostalgic playlist", "nostalgic songs", "nostalgic song", "nostalgic vibes", "nostalgic vibe", "nostalgic lofi", "nostalgic chill", "nostalgic rage", "nostalgic rap", "nostalgic hip hop", "nostalgic EDM", "nostalgic dubstep", "nostalgic trap", "nostalgic techno", "nostalgic house", "nostalgic electronic", "nostalgic playlist", "nostalgic music playlist", "nostalgic songs playlist", "nostalgic song playlist", "nostalgic vibes playlist", "nostalgic vibe playlist", "nostalgic lofi playlist", "nostalgic chill playlist", "nostalgic rage playlist", "nostalgic rap playlist", "nostalgic hip hop playlist", "nostalgic EDM playlist", "nostalgic dubstep playlist",
    "ending", "BGM", "OP", "ED", "JJk", "One Piece", "MHA", "soundtrack", "soundtracks", "music", "songs", "song", "playlist", "playlists", "whimsigothic", 
    "Demon Slayer", "SNK", "Naruto", "Chainsaw Man", "Yoasobi", "gym", "gym anime", "gym rage", "gym workout", "gym music", "gym playlist", "phonk", "phonk playlist",
    "DBZ", "HXH", "Jojo", "Tokyo Ghoul", "Attack on Titan", "rage", "rage music", "rage playlist", "anime rage", "anime rage music", "anime rage playlist",
    "My Hero Academia", "main character", "boss battle", "Walter White", "chill", "sleep", "study", "hoe (tool)", "rap (music genre)", r"(\b?:play|playing\b)", r"(\b(?:y2k)\b)", "y2k", "y2k music", "birthday", "birthday music", "birthday playlist",
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

# ✅ NSFW Image Check (Google Vision + OpenAI in Parallel)
async def is_safe_image(image_url: str) -> str:
    """Runs Google Vision first; if flagged, checks OpenAI before blocking."""
    if not image_url:
        return "/static/images/censored-image.png"  # ✅ Default to censored image if URL is missing

    # ✅ Check Cache First
    if image_url in NSFW_IMAGE_CACHE:
        return NSFW_IMAGE_CACHE[image_url]

    # ✅ Run Google Vision First
    google_safe = await google_cloud_nsfw_check(image_url)

    if google_safe:
        NSFW_IMAGE_CACHE[image_url] = image_url  # ✅ Mark as safe
        return image_url  

    # ❌ Google Vision flagged → Run OpenAI Check
    logging.warning(f"⚠️ Google flagged {image_url}. Running OpenAI check...")

    openai_safe = await openai_nsfw_image_check(image_url)

    result = image_url if openai_safe else "/static/images/censored-image.png"
    NSFW_IMAGE_CACHE[image_url] = result  # ✅ Cache result
    return result

async def google_cloud_nsfw_check(image_url: str) -> bool:
    """Runs Google Cloud Vision NSFW detection."""
    try:
        image = vision.Image()
        image.source.image_uri = image_url
        response = GOOGLE_CLOUD_VISION_CLIENT.safe_search_detection(image=image)
        annotations = response.safe_search_annotation

        # ✅ Define Risk Levels
        risk_levels = {"POSSIBLE", "LIKELY", "VERY_LIKELY"}
        return annotations.adult.name not in risk_levels and annotations.violence.name not in risk_levels
    except Exception as e:
        logging.error(f"❌ Google Cloud Vision API Error: {e}")
        return False  # Assume unsafe if Vision API fails

async def openai_nsfw_image_check(image_url: str) -> bool:
    """Runs OpenAI NSFW Image Moderation."""
    payload = {
        "model": "omni-moderation-latest",
        "input": [{"type": "image_url", "image_url": {"url": image_url}}],
    }

    session = await get_session()
    try:
        async with session.post(
            OPENAI_MODERATION_API_URL, json=payload, headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
        ) as response:
            data = await response.json()
            return not any(result.get("flagged", False) for result in data.get("results", []))
    except Exception as e:
        logging.error(f"❌ OpenAI Image Moderation Error: {e}")
        return False  # Assume unsafe if OpenAI API fails