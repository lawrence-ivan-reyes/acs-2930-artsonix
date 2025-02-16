from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import random

load_dotenv()

app = Flask(__name__)
BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

# Dictionary mapping moods to relevant keywords for searching artworks
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
    "Open": ["inspired", "creative", "calm", "energetic", "adventurous", "happy", "sad", "romantic", "focused", "upbeat", "rebellious", "dark", "nostalgic", "trippy", "party", "epic", "quirky", "emotiona"]
}

# Dictionary defining date ranges for different historical periods
period_keywords = {
    "Ancient": {"dateBegin": -10000, "dateEnd": 500},
    "Medieval & Renaissance": {"dateBegin": 500, "dateEnd": 1500},
    "Early Modern": {"dateBegin": 1500, "dateEnd": 1800},
    "Modern": {"dateBegin": 1800, "dateEnd": 1945},
    "Contemporary": {"dateBegin": 1945, "dateEnd": 2023},
    "Open": {"ancient", "medieval & renaissance", "early modern", "modern", "contemporary"}
}

# Dictionary mapping subjects to relevant keywords for searching artworks
subject_keywords = {
    "Human Stories": ["portrait", "daily life", "figure"],
    "Nature & Landscapes": ["landscape", "nature", "scenery"],
    "Religious & Mythological": ["religion", "mythology", "spiritual"],
    "Historical Events": ["history", "event", "historical"],
    "Abstract & Decorative": ["abstract", "decorative"],
    "Open": ["human stories", "nature & landscapes", "religious & mythological", "historical events", "abstract & decorative" ]
}

@app.route('/')
def index():
    """
    Render the main index page.
    """
    return render_template('index.html')

@app.route('/process-preferences', methods=['POST'])
def process_preferences():
    """
    Process user preferences and fetch combined results based on moods, art styles, period, and subject.
    """
    try:
        preferences = request.json
        print("Preferences Received:", preferences)  # Logging
        moods = preferences.get('moods', [])
        art_styles = preferences.get('art_styles', [])
        period = preferences.get('period')
        subject = preferences.get('subject')

        mood_results = fetch_results_based_on_moods(moods, limit=3)
        art_style_results = fetch_results_based_on_art_styles(art_styles, limit=3)
        period_results = fetch_results_based_on_period(period, limit=1)
        subject_results = fetch_results_based_on_subject(subject, limit=1)

        combined_results = mood_results + art_style_results + period_results + subject_results
        combined_results = combined_results[:9]  # Limit to 9 results
        print("Combined Results:", combined_results)  # Logging
        return jsonify(combined_results)
    except Exception as e:
        print("Error Processing Preferences:", str(e))
        return jsonify({"error": str(e)}), 500


def fetch_results_based_on_moods(moods, limit=3):
    """
    Fetch artworks based on given moods.

    Args:
        moods (list): List of moods to search for.
        limit (int): Maximum number of results to return.

    Returns:
        list: List of fetched artwork results.
    """
    results = []
    try:
        for mood in moods:
            keywords = mood_keywords.get(mood, [])
            for keyword in keywords:
                response = requests.get(f"{BASE_URL}/search", params={"q": keyword}).json()
                object_ids = response.get("objectIDs", [])
                for obj_id in object_ids[:10]:
                    obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
                    if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response:
                        results.append(obj_response)
                    if len(results) >= limit:
                        break
            if len(results) >= limit:
                break
    except Exception as e:
        print("Error Fetching Results Based on Moods:", str(e))
    return results

def fetch_results_based_on_art_styles(art_styles, limit=3):
    """
    Fetch artworks based on given art styles.

    Args:
        art_styles (list): List of art styles to search for.
        limit (int): Maximum number of results to return.

    Returns:
        list: List of fetched artwork results.
    """
    results = []
    try:
        for style in art_styles:
            response = requests.get(f"{BASE_URL}/search", params={"q": style}).json()
            object_ids = response.get("objectIDs", [])
            for obj_id in object_ids[:10]:
                obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
                if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response:
                    results.append(obj_response)
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
    except Exception as e:
        print("Error Fetching Results Based on Art Styles:", str(e))
    return results

def fetch_results_based_on_period(period, limit=1):
    """
    Fetch artworks based on a given historical period.

    Args:
        period (str): The historical period to search for.
        limit (int): Maximum number of results to return.

    Returns:
        list: List of fetched artwork results.
    """
    results = []
    try:
        period_range = period_keywords.get(period, {})
        if period_range:
            response = requests.get(f"{BASE_URL}/search", params={"dateBegin": period_range["dateBegin"], "dateEnd": period_range["dateEnd"]}).json()
            object_ids = response.get("objectIDs", [])
            for obj_id in object_ids[:10]:
                obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
                if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response:
                    results.append(obj_response)
                if len(results) >= limit:
                    break
    except Exception as e:
        print("Error Fetching Results Based on Period:", str(e))
    return results

def fetch_results_based_on_subject(subject, limit=1):
    """
    Fetch artworks based on a given subject.

    Args:
        subject (str): The subject to search for.
        limit (int): Maximum number of results to return.

    Returns:
        list: List of fetched artwork results.
    """
    results = []
    try:
        keywords = subject_keywords.get(subject, [])
        for keyword in keywords:
            response = requests.get(f"{BASE_URL}/search", params={"q": keyword}).json()
            object_ids = response.get("objectIDs", [])
            for obj_id in object_ids[:10]:
                obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
                if obj_response.get("isPublicDomain") and "primaryImageSmall" in obj_response:
                    results.append(obj_response)
                if len(results) >= limit:
                    break
    except Exception as e:
        print("Error Fetching Results Based on Subject:", str(e))
    return results

@app.route('/surprise-me', methods=['GET'])
def fetch_surprise_me_results():
    """
    Fetch random artwork results based on randomly selected preferences.
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
        random_period = random.choice(list(period_keywords.keys()))  # Randomly pick a period
        random_subject = random.choice(list(subject_keywords.keys()))  # Randomly pick a subject

        # Fetch results based on random preferences
        mood_results = fetch_results_based_on_moods(random_moods, limit=3)
        art_style_results = fetch_results_based_on_art_styles(random_art_styles, limit=3)
        period_results = fetch_results_based_on_period(random_period, limit=1)
        subject_results = fetch_results_based_on_subject(random_subject, limit=1)

        combined_results = mood_results + art_style_results + period_results + subject_results
        combined_results = combined_results[:9]  # Limit to 9 results

        return jsonify(combined_results)
    except Exception as e:
        print("Error Fetching Surprise Me Results:", str(e))
        return jsonify({"error": str(e)}), 500

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

if __name__ == '__main__':
    app.run(debug=True, port=3005)
