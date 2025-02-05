from flask import Flask, render_template, request, jsonify
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
        return response.json()
    else:
        return {"error": "Failed to fetch token", "status": response.status_code}

BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/error')
def error():
    return render_template('error.html')

if __name__ == '__main__':
    app.run(debug=True, port=3000)
