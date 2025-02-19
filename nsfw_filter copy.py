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
    "Drake", "Eminem", "Kanye West", "Beyoncé", "Aimer", "Yoasobi", "Ariana Grande", "Fleetwood Mac", 
    "Taylor Swift", "The Weeknd", "Bruno Mars", "Billie Eilish", "Doja Cat",
    "Kenshi Yonezu", "Lisa", "Radwimps", "King Gnu", "Vaundy", "Eagles", "Queen", "The Beatles", "Led Zeppelin", "Pink Floyd", "The Rolling Stones", "The Who", "The Doors", "Jimi Hendrix", "Bob Dylan", "David Bowie", "Elton John", "Prince", "Michael Jackson", "Madonna", "Whitney Houston", "Mariah Carey", "Janet Jackson", "Stevie Wonder", "Bob Marley", "James Brown", "Aretha Franklin", "Ray Charles", "Sam Cooke", "Otis Redding", "Marvin Gaye", "Al Green", "Smokey Robinson", "Stevie Wonder", "Earth, Wind & Fire", "The Temptations", "The Supremes", "The Four Tops", "The Jackson 5", "The Isley Brothers", "The O'Jays", "The Commodores", "The Bee Gees", "The Eagles", "The Doobie Brothers", "The Allman Brothers Band", "The Grateful Dead", "The Band", "The Byrds", "The Velvet Underground", "The Doors", "The Who", "The Rolling Stones", "The Beatles",
    "The Beach Boys", "The Supremes", "The Ronettes", "The Shirelles", "The Crystals", "The Chiffons", "The Marvelettes", "The Shangri-Las", "The Angels", "The Cookies", "The Shirelles", "The Chantels", "The Shangri-Las", 
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

# ✅ **🔹 Keyword-Based NSFW Filtering (Lightweight)**
async def keyword_filter(text: str) -> bool:
    """First-pass keyword filtering using exact match blocklist, allowing whitelisted content."""
    if not text:
        return True  # Empty text is safe

    text = html.unescape(text).strip().lower()

    # ✅ Allow Whitelisted Artists (Bypass Filtering)
    if any(artist.lower() in text for artist in WHITELIST_ARTISTS):
        logging.info(f"✅ Whitelisted Artist Allowed: {text}")
        return True

    # ✅ Strict Blocklist Check (Exact Matches Only)
    if any(term in text for term in BLOCKLIST_TERMS):
        logging.warning(f"❌ Blocked by Keyword Filter: {text}")
        return False  

    return None  # Not sure → Needs API check

# ✅ **🔹 OpenAI NSFW Check (Final Pass)**
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
                OPENAI_MODERATION_API_URL, json=payload,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            ) as response:
                data = await response.json()
                flagged = any(result.get("flagged", False) for result in data.get("results", []))
                
                if flagged:
                    logging.warning(f"❌ Blocked by OpenAI: {text}")
                else:
                    logging.info(f"✅ Passed OpenAI: {text}")

                return not flagged
        except Exception as e:
            logging.error(f"❌ OpenAI API Error: {e}")
            return True  # Assume safe if API fails

# ✅ **🔹 Multi-Pass NSFW Text Filter**
async def is_safe_content(text: str) -> bool:
    """Applies keyword filtering first, then OpenAI NSFW check if needed."""
    keyword_check = await keyword_filter(text)

    if keyword_check is None:  # ✅ Not sure → Ask OpenAI
        return await openai_nsfw_filter(text)
    
    return keyword_check  # ✅ If keyword filter is sure, use its result

# ✅ **🔹 Google Cloud Vision NSFW Check**
async def google_cloud_nsfw_check(image_url: str) -> bool:
    """Runs Google Cloud Vision NSFW detection with stricter thresholds."""
    try:
        image = vision.Image()
        image.source.image_uri = image_url
        response = GOOGLE_CLOUD_VISION_CLIENT.safe_search_detection(image=image)
        annotations = response.safe_search_annotation

        # ✅ Define Stricter Risk Levels
        high_risk_levels = {"VERY_LIKELY"}
        unknown_risk_levels = {"UNKNOWN"}

        if (
            annotations.adult.name in high_risk_levels or
            annotations.violence.name in unknown_risk_levels or
            annotations.racy.name in unknown_risk_levels
        ):
            return False  # ❌ Flag as unsafe

        return True  # ✅ Safe image
    except Exception as e:
        logging.error(f"❌ Google Cloud Vision API Error: {e}")
        return False  # Assume unsafe if Vision API fails

# ✅ **🔹 OpenAI NSFW Image Check**
async def openai_nsfw_image_check(image_url: str) -> bool:
    """Runs OpenAI NSFW Image Moderation with a focus on sexual & violent content."""
    payload = {
        "model": "omni-moderation-latest",
        "input": [{"type": "image_url", "image_url": {"url": image_url}}],
        "thresholds": {
            "sexual/minors": 0.0001,  # Extremely strict for minors
        }
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                OPENAI_MODERATION_API_URL, json=payload, headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
            ) as response:
                data = await response.json()
                return not any(result.get("flagged", False) for result in data.get("results", []))
        except Exception as e:
            logging.error(f"❌ OpenAI Image Moderation Error: {e}")
            return False  # Assume unsafe if OpenAI API fails

# ✅ **🔹 NSFW Image Check (Google Vision + OpenAI)**
async def is_safe_image(image_url: str) -> str:
    """Google acts as primary filter; if Google flags, OpenAI decides. Favor Google if either flags."""
    if not image_url:
        return "/static/images/censored-image.png"

    if image_url in NSFW_IMAGE_CACHE:
        return NSFW_IMAGE_CACHE[image_url]

    # ✅ Check Google Vision first
    google_safe = await google_cloud_nsfw_check(image_url)

    # ✅ If Google allows → Safe
    if google_safe:
        NSFW_IMAGE_CACHE[image_url] = image_url
        return image_url

    # ❗ Google flagged → Check OpenAI
    openai_safe = await openai_nsfw_image_check(image_url)

    # ❌ Block if OpenAI also flags
    if not openai_safe:
        logging.warning(f"⚠️ NSFW Image Detected by Both: {image_url}")
        NSFW_IMAGE_CACHE[image_url] = "/static/images/censored-image.png"
        return "/static/images/censored-image.png"

    # ✅ Allow if OpenAI allows
    logging.info(f"✅ Allowed by OpenAI despite Google flag: {image_url}")
    NSFW_IMAGE_CACHE[image_url] = image_url
    return image_url