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

# Moods dictionary - focusing on emotional or psychological states
mood_keywords = {
    "Inspired": ["inspiration", "creativity", "genius"],
    "Creative": ["creativity", "innovation", "imagination"],
    "Calm": ["serene", "peaceful", "tranquil"],
    "Energetic": ["dynamic", "vibrant", "lively"],
    "Adventurous": ["exploration", "adventure", "journey"],
    "Happy": ["joy", "happiness", "bliss"],
    "Sad": ["melancholy", "sadness", "sorrow"],
    "Romantic": ["romance", "love", "passion"],
    "Focused": ["concentration", "focus", "meditation"],
    "Upbeat": ["cheerful", "optimistic", "positive"],
    "Rebellious": ["rebellion", "protest", "revolt"],
    "Dark": ["darkness", "mystery", "gothic"],
    "Nostalgic": ["nostalgia", "memory", "reminiscence"],
    "Trippy": ["psychedelic", "abstract", "surreal"],
    "Party": ["celebration", "festivity", "party"],
    "Epic": ["heroic", "epic", "legend"],
    "Quirky": ["quirky", "eccentric", "whimsical"],
    "Emotional": ["emotion", "feeling", "expression"],
    "Open": ["inspired", "creative", "calm", "energetic", "adventurous", "happy", "sad", "romantic", "focused", "upbeat", "rebellious", "dark", "nostalgic", "trippy", "party", "epic", "quirky", "emotional"]
}

# Subjects dictionary - focusing on artwork topics
subject_keywords = {
    "Human Stories": ["portrait", "daily life", "figure", "people"],
    "Nature & Landscapes": ["landscape", "scenery", "garden"],
    "Religious & Mythological": ["religion", "mythology", "spiritual"],
    "Historical Events": ["history", "event", "historical", "war"],
    "Abstract & Decorative": ["abstract", "decorative", "pattern"],
    "Open": ["human stories", "nature & landscapes", "religious & mythological", "historical events", "abstract & decorative"]
}

# Art Styles dictionary - focusing on movements and artistic techniques
art_style_keywords = {
    "Cubism": ["cubist", "Picasso", "Braque"],
    "Abstract": ["abstract", "Kandinsky", "color field"],
    "Impressionism": ["impressionist", "Renoir", "brushstrokes"],
    "Baroque": ["baroque", "Rubens", "dramatic"],
    "Romanticism": ["romantic", "Delacroix", "emotion"],
    "Pre-Raphaelite": ["pre-raphaelite", "Rossetti", "detailed"],
    "Op Art": ["op art", "Riley", "illusion"],
    "Futurism": ["futurist", "Boccioni", "movement"],
    "Tonalism": ["tonalist", "Whistler", "Inness", "mood"],
    "Open": ["cubism", "abstract", "impressionism", "baroque", "romanticism", "pre-raphaelite", "op art", "futurism", "tonalism"]
}

# ✅ Quart (Spotify)
quart_app = QuartApp(__name__)
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_API_URL = "https://api.spotify.com/v1/search"

TOKEN_CACHE = {"access_token": None, "expires_at": 0}
RETRY_ATTEMPTS = 3  # Retries if rate-limited

# ✅ Mood-to-Genre Mapping
MOOD_GENRE_MAP = {
    "Inspired": ["Orchestral", "Epic Soundtrack", "Power Metal", "Synthwave", "Post-Rock", "Neoclassical", "Chamber Music", "Heroic Fantasy", "Gregorian Chant"],
    "Creative": ["Lo-fi", "Jazz", "Indie Folk", "Dream Pop", "Experimental", "Math Rock", "Glitch", "Postmodern Classical", "Sound Collage", "Avant-Garde"],
    "Calm": ["Ambient", "New Age", "Chillout", "Bossa Nova", "Soft Piano", "Downtempo", "Lounge", "Drone", "Smooth Jazz", "Harp Meditation"],
    "Energetic": ["EDM", "House", "Trance", "Drum & Bass", "Speedcore", "Big Room House", "Melodic Dubstep", "UK Garage", "Future Bounce", "Hardstyle"],
    "Adventurous": ["Prog Rock", "Folk", "Cyberpunk", "World Music", "Dungeon Synth", "Pirate Metal", "Celtic", "Mongolian Throat Singing", "Medieval Folk", "Viking Metal"],
    "Happy": ["Pop", "Disco", "Funk", "Kawaii Future Bass", "Afrobeats", "Nu-Disco", "Electro Swing", "Sunshine Pop", "Tropical House", "Bubblegum Dance"],
    "Sad": ["Indie", "Acoustic", "Slowcore", "Sadcore", "Shoegaze", "Emo", "Depressive Black Metal", "Chamber Pop", "Post-Punk", "Dark Cabaret"],
    "Romantic": ["R&B", "Soul", "Jazz", "Classical", "City Pop", "Lovers Rock", "Chillhop", "French Chanson", "Flamenco", "Bolero"],
    "Focused": ["Instrumental", "Classical", "Lo-fi", "Synthwave", "IDM", "Minimal Techno", "Piano Solos", "Study Beats", "Binaural Beats", "Meditation Music"],
    "Upbeat": ["Dance", "Pop", "Funk", "Ska", "Jersey Club", "Baile Funk", "Boogie", "Eurodance", "Charanga", "Future Funk"],
    "Rebellious": ["Punk", "Hardcore", "Grunge", "Riot Grrrl", "Cybergrind", "Post-Hardcore", "Industrial Punk", "Anarcho-Punk", "Crust Punk", "Speed Metal"],
    "Dark": ["Gothic Rock", "Darkwave", "Industrial", "Black Metal", "Witch House", "Horrorcore", "Noir Jazz", "Martial Industrial", "Doom Jazz", "Post-Industrial"],
    "Nostalgic": ["Classic Rock", "80s Pop", "Mallsoft", "Plunderphonics", "Y2K Pop", "Vaporwave", "Dreampunk", "New Romantic", "Chillwave", "Vintage Jazz"],
    "Trippy": ["Psytrance", "Trip-Hop", "Neo-Psychedelia", "Space Rock", "Deep Dub", "Freak Folk", "Acid Jazz", "Dub Techno", "Experimental Hip-Hop", "Glitch Hop"],
    "Party": ["Hip-Hop", "EDM", "Reggaeton", "Moombahton", "Jungle", "Baltimore Club", "Trap", "Twerk", "Dancehall", "Hardbass"],
    "Epic": ["Orchestral", "Cinematic", "Power Metal", "Film Score", "Trailer Music", "Battle Music", "Neo-Classical Metal", "War Drums", "Epic Choir", "Fantasy Metal"],
    "Quirky": ["Webcore", "Dariacore", "Hyperpop", "Electro Swing", "8-Bit", "Bitpop", "Toytronica", "Chiptune", "Nintendocore", "Bubblegum Bass"],
    "Emotional": ["Indie Folk", "Shoegaze", "Post-Rock", "Sadcore", "Ethereal Wave", "Slowcore", "Doom Metal", "Baroque Pop", "Neo-Folk", "Alt-R&B"]
}

# ✅ Categorize genres into different tiers for weighted randomness
MAINSTREAM_GENRES = [
    "Pop", "Rock", "Hip-Hop", "EDM", "R&B", "Jazz", "Classical", "Indie", "Reggaeton"
]

NICHE_GENRES = [
    "Dungeon Synth", "Cybergrind", "Witch House", "Plunderphonics", "Dariacore", 
    "Mallsoft", "Darkwave", "Vaporwave", "Synthwave", "Hardstyle"
]

# ✅ Async function to get Spotify access token with lock
async def quart_get_access_token():
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
async def quart_fetch_spotify_data(session, url, headers, attempt=1):
    try:
        async with session.get(url, headers=headers, timeout=5) as response:
            if response.status == 401:
                logging.warning("⚠️ Token expired, refreshing...")
                headers["Authorization"] = f"Bearer {await quart_get_access_token()}"
                return await quart_fetch_spotify_data(session, url, headers, attempt + 1)

            if response.status == 429 and attempt < RETRY_ATTEMPTS:
                retry_after = int(response.headers.get("Retry-After", 2))
                logging.warning(f"⚠️ Rate limited! Retrying in {retry_after} sec...")
                await asyncio.sleep(retry_after)
                return await quart_fetch_spotify_data(session, url, headers, attempt + 1)

            response.raise_for_status()
            data = await response.json()
            return data if isinstance(data, dict) else None
    except Exception as e:
        logging.error(f"❌ Failed request: {e} (Attempt {attempt})")
        return None

async def quart_fetch_all_results(query, search_type):
    """Fetches diverse results while ensuring unique genres in playlist titles."""
    access_token = await quart_get_access_token()
    if not access_token:
        logging.error("❌ Failed to retrieve Spotify Access Token")
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    results = []
    offset, limit = 0, 50  # Fetch more items at once

    async with aiohttp.ClientSession() as session:
        while len(results) < 50:  # Increase total fetch count
            url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={search_type}&limit={limit}&offset={offset}"
            data = await quart_fetch_spotify_data(session, url, headers)
            
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
        results.sort(key=lambda x: x.get("followers", {}).get("total", 0) if isinstance(x.get("followers"), dict) else 0, reverse=True)
    else:
        results.sort(key=lambda x: x.get("popularity", 0) if isinstance(x, dict) else 0, reverse=True)

    # ✅ Shuffle after sorting to introduce randomness
    random.shuffle(results)

    return results[:20]

# ✅ Format search results
def quart_format_results(items, search_type):
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
            "type": search_type,  
        }

        # ✅ **Fix for artist image retrieval**
        if search_type == "artist":
            images = item.get("images", [])
            image_url = images[0]["url"] if images else "https://via.placeholder.com/300"
            data["image"] = image_url
            data["genres"] = ", ".join(item.get("genres", ["No genres available"]))
            data["popularity"] = item.get("popularity", "N/A")
            data["followers"] = item.get("followers", {}).get("total", 0)
        elif search_type == "playlist":
            data["image"] = item.get("images", [{}])[0].get("url", "https://via.placeholder.com/300")
            data["track_count"] = item.get("tracks", {}).get("total", 0)
            data["followers"] = item.get("followers", {}).get("total", 0)
        elif search_type == "album":
            data["image"] = item.get("images", [{}])[0].get("url", "https://via.placeholder.com/300")
            data["artist"] = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
            data["release_date"] = item.get("release_date", "Unknown Date")
            data["year"] = item.get("release_date", "").split("-")[0] if item.get("release_date") else "Unknown"
            data["popularity"] = item.get("popularity", 0)
        elif search_type == "track":
            data["image"] = item.get("album", {}).get("images", [{}])[0].get("url", "https://via.placeholder.com/300")
            data["artist"] = ", ".join([artist.get("name", "Unknown Artist") for artist in item.get("artists", [])])
            data["album"] = item.get("album", {}).get("name", "Unknown Album")
            data["preview_url"] = item.get("preview_url", None)
            data["year"] = item.get("album", {}).get("release_date", "").split("-")[0] if item.get("album") else "Unknown"
            data["popularity"] = item.get("popularity", 0)

        formatted_results.append(data)

    return formatted_results

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
        preferences = flask_request.json
        # Extract preferences
        moods = preferences.get('moods', [])
        art_styles = preferences.get('art_styles', [])
        subject = preferences.get('subject')

        # Fetch results using the updated method
        mood_results = flask_fetch_results_based_on_moods(moods, limit=3) or []
        art_style_results = flask_fetch_results_based_on_art_styles(art_styles, limit=3) or []
        subject_results = flask_fetch_results_based_on_subject(subject, limit=1) or []

        # Combine results
        combined_results = mood_results + art_style_results + subject_results
        # Remove duplicates
        unique_results = flask_remove_duplicates(combined_results)
        
        # Ensure there are at least 9 unique images
        if len(unique_results) < 9:
            while len(unique_results) < 9:
                random_image = flask_fetch_random_image()
                if random_image and random_image not in unique_results:
                    unique_results.append(random_image)
                else:
                    logging.warning("Could not fetch a valid random image to add.")
                    break
        
        # Limit to 9 results if there are still more than 9
        unique_results = unique_results[:9]
        return flask_jsonify(unique_results)
    except Exception as e:
        logging.error(f"Error processing preferences: {str(e)}")
        return flask_jsonify({"error":  str(e)}), 500

# Add this route to the combined_flask_quart_app.py file

@flask_app.route('/surprise-me', methods=['GET'])
def flask_surprise_me():
    """
    Generate random art and music recommendations.
    
    This function randomly selects preferences for both Met and Spotify,
    fetches results, and returns them for display on the results page.
    """
    try:
        # --- MET RANDOM SELECTIONS (existing code) ---
        # Randomly select preferences
        random_moods = random.sample(list(mood_keywords.keys()), 3)  # Select 3 random moods
        
        # List of specific art styles
        art_styles_list = [
            "Cubism", "Abstract", "Impressionism", "Modern", "Baroque",
            "Romanticism", "Pre-Raphaelite", "Op Art", "Futurism", "Tonalism"
        ]
        # Randomly select 3 art styles from the list
        random_art_styles = random.sample(art_styles_list, 3)
        
        random_subject = random.choice(list(subject_keywords.keys()))  # Randomly pick a subject
        
        # Fetch results based on random preferences for Met
        mood_results = flask_fetch_results_based_on_moods(random_moods, limit=3)
        art_style_results = flask_fetch_results_based_on_art_styles(random_art_styles, limit=3)
        subject_results = flask_fetch_results_based_on_subject(random_subject, limit=3)
        
        met_results = flask_remove_duplicates(mood_results + art_style_results + subject_results)
        met_results = met_results[:9]  # Limit to 9 results
        
        # --- SPOTIFY RANDOM SELECTIONS (new code) ---
        # Randomly select a recommendation type
        rec_types = ["playlist", "album", "artist", "track"]
        random_rec_type = random.choice(rec_types)
        
        # Create a random query based on random moods
        spotify_moods = random.sample(list(MOOD_GENRE_MAP.keys()), min(3, len(MOOD_GENRE_MAP)))
        selected_genres = []
        
        # Get genres from selected moods
        for mood in spotify_moods:
            if mood in MOOD_GENRE_MAP:
                # Select a few random genres from each mood
                mood_genres = random.sample(MOOD_GENRE_MAP[mood], min(2, len(MOOD_GENRE_MAP[mood])))
                selected_genres.extend(mood_genres)
        
        # If we somehow don't have enough genres, add some mainstream ones
        if len(selected_genres) < 3:
            selected_genres.extend(random.sample(MAINSTREAM_GENRES, min(3, len(MAINSTREAM_GENRES))))
        
        # Create the query string
        query = " OR ".join(selected_genres[:5])  # Limit to 5 terms for query length
        
        # Get Spotify token synchronously (for Flask route)
        spotify_results = []
        try:
            # Get Spotify API token
            spotify_token_url = "https://accounts.spotify.com/api/token"
            token_response = requests.post(
                spotify_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": SPOTIFY_CLIENT_ID,
                    "client_secret": SPOTIFY_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            
            if access_token:
                # Make Spotify API request
                search_url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={random_rec_type}&limit=20"
                search_response = requests.get(
                    search_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                search_data = search_response.json()
                
                # Extract items
                items = search_data.get(f"{random_rec_type}s", {}).get("items", [])
                
                # Remove any invalid items and format the results
                valid_items = [item for item in items if isinstance(item, dict) and "name" in item]
                
                # Apply some randomness to the results
                if valid_items:
                    random.shuffle(valid_items)
                    # Format the items properly
                    spotify_results = quart_format_results(valid_items[:9], random_rec_type)
                
                # If somehow we don't have enough results, try a different approach
                if len(spotify_results) < 3:
                    # Try with a broader search term
                    broader_query = " OR ".join(random.sample(MAINSTREAM_GENRES, min(3, len(MAINSTREAM_GENRES))))
                    search_url = f"{SPOTIFY_API_URL}?q={quote_plus(broader_query)}&type={random_rec_type}&limit=20"
                    search_response = requests.get(
                        search_url,
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    search_data = search_response.json()
                    items = search_data.get(f"{random_rec_type}s", {}).get("items", [])
                    valid_items = [item for item in items if isinstance(item, dict) and "name" in item]
                    
                    if valid_items:
                        random.shuffle(valid_items)
                        spotify_results = quart_format_results(valid_items[:9], random_rec_type)
        
        except Exception as e:
            logging.error(f"Error in Spotify random recommendation: {str(e)}")
            spotify_results = []
        
        # Combine both Met and Spotify results
        combined_results = {
            'met_results': met_results,
            'spotify_results': spotify_results
        }
        
        # Return the combined results as JSON
        return flask_jsonify(combined_results)
        
    except Exception as e:
        logging.error(f"Error in surprise-me route: {str(e)}")
        return flask_jsonify({"error": str(e)}), 500

# ✅ Quart Routes (Spotify)
@quart_app.route('/')
async def quart_index():
    return await quart_render_template('index.html')

@quart_app.route('/results', methods=['GET'])
async def quart_results():
    """Fetches Spotify results based on search query or mood selection."""

    rec_type = quart_request.args.get('rec_type', 'playlist')
    query = quart_request.args.get('query', '').strip()
    moods = quart_request.args.getlist('moods')

    logging.info(f"🔎 Searching Spotify for: {query} (Rec Type: {rec_type})")

    # ✅ Handle "I'm Open to Anything" mode
    if rec_type.lower() == "i’m open to anything":
        rec_type = random.choice(["playlist", "album", "artist", "track"])
        all_genres = sum(MOOD_GENRE_MAP.values(), [])
        query = " OR ".join(random.sample(all_genres, min(len(all_genres), 5)))

    # ✅ Use specific search query directly (From Old Code 1)
    if query:
        search_url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={rec_type}&limit=20"
        access_token = await quart_get_access_token()

        if not access_token:
            return await quart_render_template("error.html", message="Failed to fetch access token"), 500

        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers) as response:
                if response.status != 200:
                    return await quart_render_template("error.html", message="Failed to fetch data from Spotify"), response.status
                data = await response.json()

        items = data.get(rec_type + "s", {}).get("items", [])
        if not items:
            return await quart_render_template("error.html", message="No results found"), 404

        formatted_results = await process_results(items, rec_type)
        return await quart_render_template("results.html", results=formatted_results)

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
    access_token = await quart_get_access_token()
    if not access_token:
        return await quart_render_template("error.html", message="Failed to fetch access token"), 500

    headers = {"Authorization": f"Bearer {access_token}"}
    results = []
    offset, limit = 0, 50

    async with aiohttp.ClientSession() as session:
        while len(results) < 50:
            url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={rec_type}&limit={limit}&offset={offset}"
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return await quart_render_template("error.html", message="Failed to fetch data from Spotify"), response.status
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
        return await quart_render_template("error.html", message="No safe results found"), 404

    # ✅ Select 9 Random Results After Filtering
    final_results = random.sample(filtered_results, min(len(filtered_results), 9))

    return await quart_render_template("results.html", results=final_results)

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

@quart_app.route('/about')
async def quart_about():
    return await quart_render_template('about.html')

@quart_app.route('/error')
async def quart_error():
    return await quart_render_template('error.html')

@quart_app.route('/credits')
async def quart_credits():
    return await quart_render_template('credits.html')

@flask_app.route('/combined-results', methods=['POST'])
def combined_results():  
    try:
        # Get form data
        form_data = flask_request.form
        
        # Process Met data (synchronous)
        moods = form_data.getlist('moods')
        art_styles = form_data.getlist('art_styles') 
        subject = form_data.get('subject')
        
        # Get Met results using synchronous functions
        mood_results = flask_fetch_results_based_on_moods(moods, limit=3)
        art_style_results = flask_fetch_results_based_on_art_styles(art_styles, limit=3)
        subject_results = flask_fetch_results_based_on_subject(subject, limit=3)
        
        # Combine and deduplicate Met results
        met_results = flask_remove_duplicates(mood_results + art_style_results + subject_results)
        
        # Process Spotify data (synchronous version)
        rec_type = form_data.get('rec_type', 'playlist')
        query = form_data.get('query', '').strip()
        
        # Create search query from moods if no direct query
        if not query and moods:
            selected_genres = []
            for mood in moods:
                if mood in MOOD_GENRE_MAP:
                    selected_genres.extend(MOOD_GENRE_MAP[mood])
            query = " OR ".join(selected_genres[:5])  # Limit to 5 genres
        
        # Make synchronous request to Spotify
        spotify_results = []
        try:
            spotify_token_url = "https://accounts.spotify.com/api/token"
            token_response = requests.post(
                spotify_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": SPOTIFY_CLIENT_ID,
                    "client_secret": SPOTIFY_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            
            if access_token:
                search_url = f"{SPOTIFY_API_URL}?q={quote_plus(query)}&type={rec_type}&limit=9"
                search_response = requests.get(
                    search_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                search_data = search_response.json()
                
                items = search_data.get(f"{rec_type}s", {}).get("items", [])
                spotify_results = quart_format_results(items, rec_type)
        except Exception as e:
            logging.error(f"Spotify API error: {str(e)}")
            spotify_results = []
        
        # Combine results
        combined_results = {
            'met_results': met_results,
            'spotify_results': spotify_results
        }
        
        return flask_jsonify(combined_results)
    except Exception as e:
        logging.error(f"Error processing combined results: {str(e)}")
        return flask_jsonify({"error": str(e)}), 500

async def process_met_data(form_data):
    """Process Met API data and return results."""
    try:
        # Extract relevant data for Met API
        moods = form_data.getlist('moods')
        art_styles = form_data.getlist('art_styles')
        subject = form_data.get('subject')
        
        # Use your existing Met API functions
        mood_results = flask_fetch_results_based_on_moods(moods, limit=3)
        art_style_results = flask_fetch_results_based_on_art_styles(art_styles, limit=3)
        subject_results = flask_fetch_results_based_on_subject(subject, limit=3)
        
        return flask_remove_duplicates(mood_results + art_style_results + subject_results)
    except Exception as e:
        logging.error(f"Error processing Met data: {str(e)}")
        return []

async def process_spotify_data(form_data):
    """Process Spotify API data and return results."""
    try:
        # Extract relevant data for Spotify API
        rec_type = form_data.get('rec_type', 'playlist')
        query = form_data.get('query', '').strip()
        moods = form_data.getlist('moods')
        
        # Use your existing Spotify API functions
        access_token = await quart_get_access_token()
        if not access_token:
            return []
        
        results = await quart_fetch_all_results(query or ' '.join(moods), rec_type)
        return await process_results(results, rec_type)
    except Exception as e:
        logging.error(f"Error processing Spotify data: {str(e)}")
        return []

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
