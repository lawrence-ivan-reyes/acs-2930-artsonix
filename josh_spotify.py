from flask import Flask, request, render_template, redirect, url_for, jsonify
import os, random, time, aiohttp, logging, asyncio
from dotenv import load_dotenv
from urllib.parse import quote_plus
from nsfw_filter import is_safe_content, is_safe_url, is_safe_image
import requests
import os
import html

# Load environment variables
load_dotenv()

# Retrieve API keys
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
GOOGLE_SAFE_BROWSING_API_KEY = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")

# Validate API keys
if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise ValueError("Missing Spotify API credentials in .env file!")
if not GOOGLE_SAFE_BROWSING_API_KEY:
    raise ValueError("Missing Google Safe Browsing API key in .env file!")

# Flask app setup
app = Flask(__name__)

# Token caching with lock
TOKEN_CACHE = {"access_token": None, "expires_at": 0}

# Config settings
SPOTIFY_API_URL = "https://api.spotify.com/v1/search"
RETRY_ATTEMPTS = 3  # Retries if rate-limited

# ✅ Mood-to-Genre Mapping
MOOD_GENRE_MAP = {
    "Inspired": ["Orchestral", "Epic Soundtrack", "Power Metal", "Synthwave", "Post-Rock"],
    "Creative": ["Lo-fi", "Jazz", "Indie Folk", "Dream Pop", "Experimental"],
    "Calm": ["Ambient", "New Age", "Chillout", "Bossa Nova", "Soft Piano"],
    "Energetic": ["EDM", "House", "Trance", "Drum & Bass", "Speedcore"],
    "Adventurous": ["Prog Rock", "Folk", "Cyberpunk", "World Music", "Dungeon Synth"],
    "Happy": ["Pop", "Disco", "Funk", "Kawaii Future Bass", "Afrobeats"],
    "Sad": ["Indie", "Acoustic", "Slowcore", "Sadcore", "Shoegaze"],
    "Romantic": ["R&B", "Soul", "Jazz", "Classical", "City Pop"],
    "Focused": ["Instrumental", "Classical", "Lo-fi", "Synthwave", "IDM"],
    "Upbeat": ["Dance", "Pop", "Funk", "Ska", "Jersey Club"],
    "Rebellious": ["Punk", "Hardcore", "Grunge", "Riot Grrrl", "Cybergrind"],
    "Dark": ["Gothic Rock", "Darkwave", "Industrial", "Black Metal", "Witch House"],
    "Nostalgic": ["Classic Rock", "80s Pop", "Mallsoft", "Plunderphonics", "Y2K Pop"],
    "Trippy": ["Psytrance", "Trip-Hop", "Neo-Psychedelia", "Space Rock", "Deep Dub"],
    "Party": ["Hip-Hop", "EDM", "Reggaeton", "Moombahton", "Jungle"],
    "Epic": ["Orchestral", "Cinematic", "Power Metal", "Film Score", "Trailer Music"],
    "Quirky": ["Webcore", "Dariacore", "Hyperpop", "Electro Swing", "8-Bit"],
    "Emotional": ["Indie Folk", "Shoegaze", "Post-Rock", "Sadcore", "Ethereal Wave"]
}


# ✅ Async function to get Spotify access token with lock
async def get_access_token():
        current_time = time.time()
        if TOKEN_CACHE["access_token"] and current_time < TOKEN_CACHE["expires_at"]:
            return TOKEN_CACHE["access_token"]

        url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials", "client_id": SPOTIFY_CLIENT_ID, "client_secret": SPOTIFY_CLIENT_SECRET}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, data=data, timeout=5) as response:
                    response.raise_for_status()
                    token_data = await response.json()
                    TOKEN_CACHE["access_token"] = token_data["access_token"]
                    TOKEN_CACHE["expires_at"] = current_time + token_data.get("expires_in", 3600)
                    return TOKEN_CACHE["access_token"]
            except Exception as e:
                logging.error(f"❌ Token error: {e}")
                return None

# ✅ Async function to fetch data from Spotify API with improved rate limit handling
async def fetch_spotify_data(session, url, headers, attempt=1):
    try:
        async with session.get(url, headers=headers, timeout=5) as response:
            if response.status == 401:
                logging.warning("⚠️ Token expired, refreshing...")
                headers["Authorization"] = f"Bearer {await get_access_token()}"
                return await fetch_spotify_data(session, url, headers, attempt + 1)

            if response.status == 429 and attempt < RETRY_ATTEMPTS:
                retry_after = int(response.headers.get("Retry-After", 2))
                logging.warning(f"⚠️ Rate limited! Retrying in {retry_after} sec...")
                await asyncio.sleep(retry_after)
                return await fetch_spotify_data(session, url, headers, attempt + 1)

            response.raise_for_status()
            data = await response.json()
            return data if isinstance(data, dict) else None
    except Exception as e:
        logging.error(f"❌ Failed request: {e} (Attempt {attempt})")
        return None

async def fetch_all_results(query, search_type):
    """Fetches diverse results while ensuring unique genres in playlist titles."""
    access_token = await get_access_token()
    if not access_token:
        logging.error("❌ Failed to retrieve Spotify Access Token")
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    results = []
    offset, limit = 0, 50  # Fetch more items at once

    async with aiohttp.ClientSession() as session:
        while len(results) < 50:  # Increase total fetch count
            url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={search_type}&limit={limit}&offset={offset}"
            data = await fetch_spotify_data(session, url, headers)
            
            if not data:
                logging.warning("⚠️ No data received from Spotify API")
                break  

            items = data.get(search_type + "s", {}).get("items", [])
            if not isinstance(items, list):  
                break  

            valid_items = [item for item in items if isinstance(item, dict)]
            results.extend(valid_items)

            offset += limit  
            if len(items) < limit:  # Stop if no more results
                break  

    if len(results) < 20:
        logging.warning(f"⚠️ Only {len(results)} results available from Spotify")

    # ✅ **Sorting by Followers (Playlists) or Popularity (Albums, Tracks, Artists)**
    if search_type == "playlist":
        results.sort(key=lambda x: x.get("followers", {}).get("total", 0), reverse=True)
    else:
        results.sort(key=lambda x: x.get("popularity", 0), reverse=True)

    # ✅ **Shuffle after sorting to introduce randomness**
    random.shuffle(results)

    # ✅ Ensure exactly 20 unique results
    return results[:20]

# ✅ Format search results
def format_results(items, search_type):
    """Formats Spotify API results into a readable structure with sorting applied."""
    if not items:
        return []  

    formatted_results = []
    for item in items[:20]:
        if not isinstance(item, dict) or not item.get("name"):
            continue  

        data = {
            "name": item.get("name", "Unknown"),
            "url": item.get("external_urls", {}).get("spotify", "#"),
            "image": item.get("images", [{}])[0].get("url", "https://via.placeholder.com/300"),
            "type": search_type,  
        }

        if search_type == "playlist":
            data["track_count"] = item.get("tracks", {}).get("total", 0)
            data["followers"] = item.get("followers", {}).get("total", 0)
        elif search_type == "artist":
            data["followers"] = item.get("followers", {}).get("total", 0)
            data["genres"] = item.get("genres", [])
            data["popularity"] = item.get("popularity", 0)
        elif search_type == "album":
            data["artist"] = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
            data["release_date"] = item.get("release_date", "Unknown Date")
            data["year"] = item.get("release_date", "").split("-")[0] if item.get("release_date") else "Unknown"
            data["popularity"] = item.get("popularity", 0)
        elif search_type == "track":
            data["artist"] = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
            data["album"] = item.get("album", {}).get("name", "Unknown Album")
            data["preview_url"] = item.get("preview_url", None)
            data["year"] = item.get("album", {}).get("release_date", "").split("-")[0] if item.get("album") else "Unknown"
            data["popularity"] = item.get("popularity", 0)

        formatted_results.append(data)

    return formatted_results

# ✅ Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/results', methods=['GET'])
def results():
    """Fetches Spotify results, applies NSFW filtering, and renders an HTML page."""
    
    rec_type = request.args.get('rec_type', 'playlist')
    mood = request.args.get('mood', 'anime')
    query = request.args.get('query', '')

    if not query:
        query = mood  # Use mood as default search if no query provided

    # ✅ Ensure a new event loop for Flask
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # ✅ Fetch Access Token
    access_token = loop.run_until_complete(get_access_token())
    if not access_token:
        return render_template("error.html", message="Failed to fetch access token"), 500

    headers = {"Authorization": f"Bearer {access_token}"}
    results = []
    offset, limit = 0, 50  

    while len(results) < 50:  # Fetch a max of 50 before randomizing selection
        params = {"q": query, "type": rec_type, "limit": limit, "offset": offset}
        response = requests.get(SPOTIFY_API_URL, headers=headers, params=params)

        if response.status_code != 200:
            return render_template("error.html", message="Failed to fetch data from Spotify"), response.status_code

        data = response.json()
        items = data.get(rec_type + "s", {}).get("items", [])
        if not isinstance(items, list):
            break  

        results.extend([item for item in items if isinstance(item, dict)])

        offset += limit  
        if len(items) < limit:  
            break  

    if len(results) < 9:
        logging.warning(f"⚠️ Only {len(results)} results available from Spotify")

    # ✅ Select 9 Random Results Before Filtering
    selected_results = random.sample(results, min(len(results), 9))

    # ✅ **Fix Event Loop Issue by Creating a New Loop**
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    filtered_results = loop.run_until_complete(process_results(selected_results, rec_type))

    if not filtered_results:
        return render_template("error.html", message="No safe results found"), 404

    return render_template("results.html", results=filtered_results)

# ✅ **Process Results with NSFW Filtering**
async def process_results(results, rec_type):
    """Processes Spotify results with NSFW filtering and image safety checks."""
    valid_results = [item for item in results if isinstance(item, dict) and "name" in item]  # ✅ Remove None & invalid items

    if not valid_results:
        logging.error("❌ No valid items to process after filtering!")
        return []

    tasks = [process_item(item, rec_type) for item in valid_results]
    processed_results = await asyncio.gather(*tasks)
    
    return [res for res in processed_results if res]  # ✅ Remove None (Blocked Items)

# ✅ **Process Each Item (Async)**
async def process_item(item, rec_type):
    """Processes a single Spotify item, applying NSFW filtering."""
    
    name = item.get("name", "Unknown")
    url = item.get("external_urls", {}).get("spotify", "#")
    image_url = item.get("images", [{}])[0].get("url", "https://via.placeholder.com/300")

    # ✅ **Handle Based on Spotify Type**
    if rec_type == "playlist":
        creator = item.get("owner", {}).get("display_name", "Unknown Creator")
        description = html.unescape(item.get("description", "No description available."))
        track_count = item.get("tracks", {}).get("total", 0)
        popularity = item.get("popularity", "N/A")

    elif rec_type == "album":
        creator = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
        description = item.get("release_date", "Unknown Release Date")
        track_count = item.get("total_tracks", 0)
        popularity = item.get("popularity", "N/A")

    elif rec_type == "track":
        creator = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
        description = item.get("album", {}).get("name", "Unknown Album")
        track_count = None
        popularity = item.get("popularity", "N/A")

    elif rec_type == "artist":
        creator = None  # No creator field for artists
        description = ", ".join(item.get("genres", ["No genres available"]))
        track_count = None
        popularity = item.get("popularity", "N/A")

    else:
        logging.warning(f"⚠️ Unsupported Spotify Type: {rec_type}")
        return None  # Ignore unsupported types

    # ✅ **NSFW Filtering**
    safe_name, safe_description = await asyncio.gather(
        is_safe_content(name), is_safe_content(description)
    )

    if not (safe_name and safe_description):
        logging.warning(f"❌ NSFW Content Hidden: {name}")
        return None  

    # ✅ **Image Safety Check**
    safe_image_url = await is_safe_image(image_url) if image_url else "https://via.placeholder.com/300"

    return {
        "name": name,
        "url": url,
        "image": safe_image_url,
        "type": rec_type,
        "creator": creator,
        "track_count": track_count,
        "description": description,
        "popularity": popularity
    }
    
@app.route('/credits')
def credits():
    return render_template('credits.html')

# ✅ Run Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(debug=True, port=port)