from flask import Flask, request, render_template, redirect, url_for, jsonify
import os, random, time, aiohttp, logging, asyncio
from dotenv import load_dotenv
from urllib.parse import quote
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
TOKEN_LOCK = asyncio.Lock()

# Config settings
SPOTIFY_API_URL = "https://api.spotify.com/v1/search"
RETRY_ATTEMPTS = 3  # Retries if rate-limited

# ✅ Async function to get Spotify access token with lock
async def get_access_token():
    async with TOKEN_LOCK:
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
            if response.status == 401:  # Token expired → Refresh
                logging.warning("⚠️ Token expired, refreshing...")
                headers["Authorization"] = f"Bearer {await get_access_token()}"
                return await fetch_spotify_data(session, url, headers, attempt + 1)

            if response.status == 429 and attempt < RETRY_ATTEMPTS:  # Rate limit hit
                retry_after = int(response.headers.get("Retry-After", 2))
                logging.warning(f"⚠️ Rate limited! Retrying in {retry_after} sec...")
                await asyncio.sleep(retry_after)
                return await fetch_spotify_data(session, url, headers, attempt + 1)

            response.raise_for_status()
            data = await response.json()
            if not isinstance(data, dict):
                logging.error(f"❌ Unexpected API response: {data}")
                return None

            return data
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
            url = f"{SPOTIFY_API_URL}?q={quote(query)}&type={search_type}&limit={limit}&offset={offset}"
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

    # ✅ Shuffle results globally
    random.shuffle(results)

    # ✅ Ensure exactly 20 unique results
    return results[:20]

# ✅ Format search results
def format_results(items, search_type):
    """Formats Spotify API results into a readable structure."""
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
            "type": search_type,  # ✅ Ensuring item.type is present
        }

        if search_type == "playlist":
            data["track_count"] = item.get("tracks", {}).get("total", 0)
        elif search_type == "artist":
            data["followers"] = item.get("followers", {}).get("total", 0)
            data["genres"] = item.get("genres", [])
        elif search_type == "album":
            data["artist"] = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
            data["release_date"] = item.get("release_date", "Unknown Date")
            data["year"] = item.get("release_date", "").split("-")[0] if item.get("release_date") else "Unknown"
        elif search_type == "track":
            data["artist"] = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
            data["album"] = item.get("album", {}).get("name", "Unknown Album")
            data["preview_url"] = item.get("preview_url", None)
            data["year"] = item.get("album", {}).get("release_date", "").split("-")[0] if item.get("album") else "Unknown"

        formatted_results.append(data)

    return formatted_results

# ✅ Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/results', methods=['GET'])
def results():
    """Fetches Spotify results, applies NSFW filtering, and renders an HTML page."""

    rec_type = request.args.get('rec_type', 'playlist')
    mood = request.args.get('mood', 'anime')
    query = request.args.get('query', '')

    if not query:
        query = mood  # Use mood as default search if no query provided

    # ✅ Fetch Access Token (Asynchronous Handling)
    access_token = asyncio.run(get_access_token())
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

    # ✅ Filter Results Asynchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    filtered_results = loop.run_until_complete(process_results(selected_results, rec_type))

    if not filtered_results:
        return render_template("error.html", message="No safe results found"), 404

    return render_template("results.html", results=filtered_results)

# ✅ **Process Results with NSFW Filtering**
async def process_results(results, rec_type):
    """Processes Spotify results with NSFW filtering and image safety checks."""
    tasks = [process_item(item, rec_type) for item in results]
    processed_results = await asyncio.gather(*tasks)
    return [res for res in processed_results if res]  # ✅ Remove None (Blocked Items)

# ✅ **Process Each Item (Async)**
async def process_item(item, rec_type):
    """Processes a single Spotify item, applying NSFW filtering."""
    name = item.get("name", "Unknown")
    url = item.get("external_urls", {}).get("spotify", "#")
    image_url = item["images"][0]["url"] if item.get("images") else None
    creator = item.get("owner", {}).get("display_name", "Unknown Creator") if rec_type == "playlist" else None
    description = html.unescape(item.get("description", "No description available.")) if rec_type == "playlist" else None
    track_count = item.get("tracks", {}).get("total", 0) if rec_type == "playlist" else None
    popularity = item.get("popularity", "N/A")

    # ✅ **Asynchronous NSFW Filtering**
    safe_name, safe_description = await asyncio.gather(
        is_safe_content(name), is_safe_content(description)
    )

    if not (safe_name and safe_description):
        logging.warning(f"❌ NSFW Playlist Hidden: {name}")
        return None  

    if track_count and track_count < 5:
        logging.warning(f"⚠️ Low-Track Playlist Hidden: {name} (Tracks: {track_count})")
        return None  

    # ✅ **Image Safety Check (API4AI)**
    safe_image_url = await is_safe_image(image_url) if image_url else "/static/images/censored-image.png"

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

@app.route('/results_test', methods=['GET'])
def results_test():
    """Fetches ALL possible Spotify results while applying NSFW filtering."""
    
    rec_type = request.args.get('rec_type', 'playlist')
    mood = request.args.get('mood', 'anime')
    query = request.args.get('query', '')

    search_query = query if query else mood  
    access_token = asyncio.run(get_access_token())
    if not access_token:
        return jsonify({"error": "Failed to fetch access token"}), 500

    headers = {"Authorization": f"Bearer {access_token}"}
    results = []
    offset = 0  
    limit = 50  # Spotify max per request

    while True:
        params = {"q": search_query, "type": rec_type, "limit": limit, "offset": offset}
        response = requests.get(SPOTIFY_API_URL, headers=headers, params=params)

        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch data from Spotify"}), response.status_code

        data = response.json()
        items = data.get(f"{rec_type}s", {}).get("items", [])

        if not items:  
            break  # No more items to fetch, stop requesting

        results.extend(items)
        offset += limit  # Move to next batch

    logging.info(f"✅ Retrieved {len(results)} {rec_type}(s) from Spotify")

    # ✅ Format results
    formatted_results = []
    for item in results:  
        name = item.get("name", "Unknown")
        url = item.get("external_urls", {}).get("spotify", "#")
        image_url = item["images"][0]["url"] if item.get("images") else None
        creator = item.get("owner", {}).get("display_name", "Unknown Creator") if rec_type == "playlist" else None
        description = html.unescape(item.get("description", "No description available.")) if rec_type == "playlist" else None
        track_count = item.get("tracks", {}).get("total", 0) if rec_type == "playlist" else None
        popularity = item.get("popularity", "N/A")

        # ✅ NSFW Filtering
        safe_name = asyncio.run(is_safe_content(name))
        safe_creator = asyncio.run(is_safe_content(creator))
        safe_description = asyncio.run(is_safe_content(description))

        if not (safe_name and safe_creator and safe_description):
            logging.warning(f"❌ NSFW Playlist Hidden: {name} | Creator: {creator}")
            continue  

        # ✅ Image Safety Check
        if image_url:
            safe_image = asyncio.run(is_safe_url(image_url)) and asyncio.run(is_safe_image(image_url))
            if not safe_image:
                logging.warning(f"❌ NSFW Image Blocked: {image_url}")
                image_url = "https://via.placeholder.com/300"

        formatted_results.append({
            "name": name,
            "url": url,
            "image": image_url,
            "type": rec_type,
            "creator": creator,
            "track_count": track_count,
            "description": description,
            "popularity": popularity
        })

    logging.info(f"✅ Final Results Count: {len(formatted_results)}")

    return jsonify({"results": formatted_results}), 200

# ✅ Run Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(debug=True, port=port)