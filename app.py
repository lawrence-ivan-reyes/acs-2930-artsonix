# combined_flask_quart_app.py

from flask import Flask as FlaskApp, render_template as flask_render_template, request as flask_request, jsonify as flask_jsonify
from quart import Quart as QuartApp, request as quart_request, render_template as quart_render_template, jsonify as quart_jsonify
import os, random, time, aiohttp, logging, asyncio, requests, html
from dotenv import load_dotenv
from urllib.parse import quote_plus
from nsfw_filter import is_safe_content, is_safe_image

# Load environment variables
load_dotenv()

# ✅ Flask (Met Museum)
flask_app = FlaskApp(__name__)
BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

# ✅ Quart (Spotify)
quart_app = QuartApp(__name__)
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_API_URL = "https://api.spotify.com/v1/search"

TOKEN_CACHE = {"access_token": None, "expires_at": 0}

# ✅ Flask Routes (Met Museum)
@flask_app.route('/')
def flask_index():
    return flask_render_template('index.html')

def flask_remove_duplicates(results):
    """
    Remove duplicate artworks based on title, artist, and object date.

    This function ensures that no duplicate results are shown and each artwork is unique.
    """
    seen_artworks = set()  # Set to track seen artwork IDs
    unique_results = [] # List to store unique results

    for result in results:
        title = result.get("title")
        artist = result.get("artistDisplayName")
        object_date = result.get("objectDate")
        artwork_id = (title, artist, object_date)

        if artwork_id not in seen_artworks:
            unique_results.append(result)
            seen_artworks.add(artwork_id)
    return unique_results

def flask_fetch_random_image():
    """
    Fetch a random image from the collection.

    This function is used to fetch random artwork to ensure there are at least 9 unique results.
    """
    try:
        response = requests.get(f"{BASE_URL}/search", params={"q": "art"}).json()
        object_ids = response.get("objectIDs", [])
        random.shuffle(object_ids) # Shuffle object IDs to get a random selection
        for obj_id in object_ids[:5]:  
            obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
            if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response:
                return obj_response
    except Exception as e:
        logging.error(f"Error fetching random image: {str(e)}")
    return None


def flask_fetch_results_based_on_moods(moods, limit=3):
    """
    Fetch artworks based on a list of moods.

    For each mood, the function retrieves associated artwork using relevant keywords and returns 
    a list of unique artworks.
    """
    results = []
    seen_artworks = set()

    try:
        for mood in moods:
            keywords = mood_keywords.get(mood, [])
            random.shuffle(keywords)  # Shuffle the keywords

            for keyword in keywords:
                response = requests.get(f"{BASE_URL}/search", params={"q": keyword}).json()
                object_ids = response.get("objectIDs", [])

                for obj_id in object_ids[:5]:  # Further increased limit for initial fetch
                    obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
                    title = obj_response.get("title")
                    artist = obj_response.get("artistDisplayName")
                    object_date = obj_response.get("objectDate")
                    artwork_id = (title, artist, object_date)

                    if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response and artwork_id not in seen_artworks:
                        results.append(obj_response)
                        seen_artworks.add(artwork_id)

                    if len(results) >= limit: 
                        break 
            if len(results) >= limit:
                break
    except Exception as e:
        logging.error(f"Error fetching results for moods: {str(e)}")
    return results


def flask_fetch_results_based_on_art_styles(art_styles, limit=3):
    """
    Fetch artworks based on given art styles.

    This function fetches artwork based on specific art styles 
    instead of moods, ensuring a variety of results based on the provided styles.
    """
    results = []
    seen_artworks = set()

    try:
        for style in art_styles:
            keywords = art_style_keywords.get(style, [])
            random.shuffle(keywords)  # Shuffle the keywords

            for keyword in keywords:
                response = requests.get(f"{BASE_URL}/search", params={"q": keyword}).json()
                object_ids = response.get("objectIDs", [])

                for obj_id in object_ids[:5]:  # Further increased limit for initial fetch
                    obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
                    title = obj_response.get("title")
                    artist = obj_response.get("artistDisplayName")
                    object_date = obj_response.get("objectDate")
                    artwork_id = (title, artist, object_date)
                    
                    if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response and artwork_id not in seen_artworks:
                        results.append(obj_response)
                        seen_artworks.add(artwork_id)
                    if len(results) >= limit:
                        break
            if len(results) >= limit:
                break
    except Exception as e:
        logging.error(f"Error fetching results for art styles: {str(e)}")
    return results


def flask_fetch_results_based_on_subject(subject, limit=3):
    """
    Fetch artworks based on a given subject.

    This function retrieves artwork based on a specific subject provided by the user, 
    ensuring a variety of results based on the provided subject.
    """
    results = []
    seen_artworks = set()

    try:
        keywords = subject_keywords.get(subject, [])
        random.shuffle(keywords)  # Shuffle the keywords

        for keyword in keywords:
            response = requests.get(f"{BASE_URL}/search", params={"q": keyword}).json()
            object_ids = response.get("objectIDs", [])

            for obj_id in object_ids[:5]:  # Further increased limit for initial fetch
                obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
                title = obj_response.get("title")
                artist = obj_response.get("artistDisplayName")
                object_date = obj_response.get("objectDate")
                artwork_id = (title, artist, object_date)

                if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response and artwork_id not in seen_artworks:
                    results.append(obj_response)
                    seen_artworks.add(artwork_id)
                    
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break  
    except Exception as e:
        logging.error(f"Error fetching results for subject: {str(e)}")
    return results

@flask_app.route('/results', methods=['GET'])
def flask_results():
    return flask_render_template('results.html')

@flask_app.route('/process-preferences', methods=['POST'])
def flask_process_preferences():
    """
    Process user preferences and fetch artwork results.

    This route receives the user's preferences and fetches artwork based on those preferences.
    """
    try:
        preferences = request.json
        # Extract preferences
        moods = preferences.get('moods', [])
        art_styles = preferences.get('art_styles', [])
        subject = preferences.get('subject')

        # Fetch results using the updated method
        mood_results = fetch_results_based_on_moods(moods, limit=3) or []
        art_style_results = fetch_results_based_on_art_styles(art_styles, limit=3) or []
        subject_results = fetch_results_based_on_subject(subject, limit=1) or []

        # Combine results
        combined_results = mood_results + art_style_results + subject_results
        # Remove duplicates
        unique_results = remove_duplicates(combined_results)
        
        # Ensure there are at least 9 unique images
        if len(unique_results) < 9:
            while len(unique_results) < 9:
                random_image = fetch_random_image()
                if random_image and random_image not in unique_results:
                    unique_results.append(random_image)
                else:
                    logging.warning("Could not fetch a valid random image to add.")
                    break
        
        # Limit to 9 results if there are still more than 9
        unique_results = unique_results[:9]
        return jsonify(unique_results)
    except Exception as e:
        logging.error(f"Error processing preferences: {str(e)}")
        return jsonify({"error":  str(e)}), 500

@flask_app.route('/surprise-me', methods=['GET'])
def flask_surprise_me():
    return flask_jsonify({"message": "Surprise me (Met Museum)"})

# ✅ Quart Routes (Spotify)
@quart_app.route('/')
async def quart_index():
    return await quart_render_template('index.html')

@quart_app.route('/results', methods=['GET'])
async def quart_results():
    """Fetches Spotify results based on search query or mood selection."""

    rec_type = request.args.get('rec_type', 'playlist')
    query = request.args.get('query', '').strip()
    moods = request.args.getlist('moods')

    logging.info(f"🔎 Searching Spotify for: {query} (Rec Type: {rec_type})")

    # ✅ Handle "I'm Open to Anything" mode
    if rec_type.lower() == "i’m open to anything":
        rec_type = random.choice(["playlist", "album", "artist", "track"])
        all_genres = sum(MOOD_GENRE_MAP.values(), [])
        query = " OR ".join(random.sample(all_genres, min(len(all_genres), 5)))

    # ✅ Use specific search query directly (From Old Code 1)
    if query:
        search_url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={rec_type}&limit=20"
        access_token = await get_access_token()

        if not access_token:
            return await render_template("error.html", message="Failed to fetch access token"), 500

        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers) as response:
                if response.status != 200:
                    return await render_template("error.html", message="Failed to fetch data from Spotify"), response.status
                data = await response.json()

        items = data.get(rec_type + "s", {}).get("items", [])
        if not items:
            return await render_template("error.html", message="No results found"), 404

        formatted_results = await process_results(items, rec_type)
        return await render_template("results.html", results=formatted_results)

    # ✅ If no query is given, use mood-based search (From Old Code 2)
    selected_genres = [
        genre for mood in moods if mood in MOOD_GENRE_MAP for genre in MOOD_GENRE_MAP[mood]
    ]
    if not query and selected_genres:
        query = " OR ".join(selected_genres)

    # ✅ Enforce Query Length Limit (From Old Code 2)
    if len(query) > 250:
        query = " OR ".join(query.split(" OR ")[:5])  # Trim excess terms

    # ✅ Fetch results using Spotify API (From New Code)
    access_token = await get_access_token()
    if not access_token:
        return await render_template("error.html", message="Failed to fetch access token"), 500

    headers = {"Authorization": f"Bearer {access_token}"}
    results = []
    offset, limit = 0, 50

    async with aiohttp.ClientSession() as session:
        while len(results) < 50:
            url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={rec_type}&limit={limit}&offset={offset}"
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return await render_template("error.html", message="Failed to fetch data from Spotify"), response.status
                data = await response.json()

            items = data.get(rec_type + "s", {}).get("items", [])
            if not isinstance(items, list):
                break

            results.extend(items)
            offset += limit
            if len(items) < limit:
                break  # Stop if fewer items are returned

    # ✅ Move Filtering BEFORE Randomization (Fixing Old Code 2’s Issue)
    filtered_results = await process_results(results, rec_type)
    if not filtered_results:
        return await render_template("error.html", message="No safe results found"), 404

    # ✅ Select 9 Random Results After Filtering
    final_results = random.sample(filtered_results, min(len(filtered_results), 9))

    return await render_template("results.html", results=final_results)

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
    """Processes a single Spotify item, applying NSFW filtering and replacing unsafe images."""
    
    name = item.get("name", "Unknown")
    url = item.get("external_urls", {}).get("spotify", "#")
    # ✅ Fix IndexError by safely checking if "images" exist and have at least one entry
    image_url = (
        item.get("images", [{}])[0].get("url", "https://via.placeholder.com/300")
        if item.get("images") and isinstance(item.get("images"), list) and len(item["images"]) > 0
        else "https://via.placeholder.com/300"
    )

    # ✅ **Handle Based on Spotify Type**
    if rec_type == "playlist":
        creator = item.get("owner", {}).get("display_name", "Unknown Creator")
        description = html.unescape(item.get("description", "No description available."))
        track_count = item.get("tracks", {}).get("total", 0)
        popularity = item.get("popularity", 0)

    elif rec_type == "album":
        creator = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
        description = item.get("release_date", "Unknown Release Date")
        track_count = item.get("total_tracks", 0)
        popularity = item.get("popularity", 0)

    elif rec_type == "track":
        creator = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
        description = item.get("album", {}).get("name", "Unknown Album")
        track_count = None
        popularity = item.get("popularity", 0)

    elif rec_type == "artist":
        creator = None  
        description = ", ".join(item.get("genres", ["No genres available"]))
        track_count = None
        popularity = item.get("popularity", 0)

    else:
        logging.warning(f"⚠️ Unsupported Spotify Type: {rec_type}")
        return None  

    # ✅ **Run NSFW Filtering (Text & Image) in Parallel**
    safe_name, safe_description, safe_image_url = await asyncio.gather(
        is_safe_content(name), 
        is_safe_content(description),
        is_safe_image(image_url) if image_url else "/static/images/censored-image.png"
    )

    # ✅ **Filter out NSFW Content**
    if not safe_name or not safe_description:
        logging.warning(f"❌ NSFW Content Hidden: {name}")
        return None  

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

@quart_app.route('/surprise-me', methods=['GET'])
async def quart_surprise_me():
    return quart_jsonify({"message": "Surprise me (Spotify)"})

# ✅ Combined Runner
if __name__ == '__main__':
    import threading
    import uvicorn

    def run_flask():
        flask_app.run(port=3000)

    def run_quart():
        uvicorn.run("app:quart_app", host="127.0.0.1", port=3001, log_level="info")

    flask_thread = threading.Thread(target=run_flask)
    quart_thread = threading.Thread(target=run_quart)

    flask_thread.start()
    quart_thread.start()

    flask_thread.join()
    quart_thread.join()
