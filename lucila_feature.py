
from flask import Flask, render_template, request, jsonify
import requests
import random
import logging

app = Flask(__name__)

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

@app.route('/')
def index():
    """
    Render the main index page.
    """
    return render_template('index.html')

def remove_duplicates(results):
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

def fetch_random_image():
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


def fetch_results_based_on_moods(moods, limit=3):
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


def fetch_results_based_on_art_styles(art_styles, limit=3):
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


def fetch_results_based_on_subject(subject, limit=3):
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

@app.route('/results')
def results():
    """
    Render the results page where artworks will be displayed.
    """
    return render_template('results.html')

@app.route('/error')
def error():
    """
    Render the error page.
    """
    return render_template('error.html')

@app.route('/process-preferences', methods=['POST'])
def process_preferences():
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

@app.route('/surprise-me', methods=['GET'])
def fetch_surprise_me_results():
    """
    Fetch random artwork results based on randomly selected preferences.

    This function provides random artwork for the user by selecting random moods, 
    art styles, and a subject, and then fetching relevant artworks.
    """
    try:
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

        # Fetch results based on random preferences
        mood_results = fetch_results_based_on_moods(random_moods, limit=3)
        art_style_results = fetch_results_based_on_art_styles(random_art_styles, limit=3)
        subject_results = fetch_results_based_on_subject(random_subject, limit=1)

        combined_results = mood_results + art_style_results + subject_results
        combined_results = combined_results[:9]  # Limit to 9 results

        return jsonify(combined_results)
    except Exception as e:
        logging.error(f"Error fetching results: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=3000)