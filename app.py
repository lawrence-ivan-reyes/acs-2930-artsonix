from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

app = Flask(__name__)

def get_spotify_token():
    """Request an access token from Spotify API using Client Credentials Flow."""
    url = "https://accounts.spotify.com/api/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET
    }

    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        return None

def search_spotify_artist(query):
    """Search for an artist on Spotify."""
    token = get_spotify_token()
    if not token:
        return {"error": "Failed to fetch Spotify token"}

    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "type": "artist", "limit": 10}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()["artists"]["items"]
    else:
        return {"error": "Failed to fetch data from Spotify"}

BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

user_data = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/error')
def error():
    return render_template('error.html')

@app.route('/submit', methods=['POST'])
def submit():
    global user_data  # Ensure we use the global dictionary
    data = request.json  # Get data from the frontend

    # Store user input
    user_data['music_genre'] = data.get('music_genre', '')
    user_data['art_style'] = data.get('art_style', '')

    # Redirect to the results page
    return redirect(url_for('results'))

@app.route('/results')
def results():
    # Retrieve stored user input
    music_genre = user_data.get('music_genre', 'No genre selected')
    art_style = user_data.get('art_style', 'No art style selected')

    # Sample recommendations (replace with actual API calls later)
    recommendations = {
        "music": [
            {"name": "Example Song 1", "artist": "Example Artist"},
            {"name": "Example Song 2", "artist": "Example Artist"}
        ],
        "art": [
            {"title": "Example Artwork 1", "artist": "Example Painter", "image": "https://via.placeholder.com/150"},
            {"title": "Example Artwork 2", "artist": "Example Painter", "image": "https://via.placeholder.com/150"}
        ]
    }

    return render_template('results.html', music_genre=music_genre, art_style=art_style, recommendations=recommendations)

if __name__ == '__main__':
    app.run(debug=True, port=3000)
