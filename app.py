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

@flask_app.route('/process-preferences', methods=['POST'])
def flask_process_preferences():
    return flask_jsonify({"message": "Processed preferences (Met Museum)"})

@flask_app.route('/surprise-me', methods=['GET'])
def flask_surprise_me():
    return flask_jsonify({"message": "Surprise me (Met Museum)"})

# ✅ Quart Routes (Spotify)
@quart_app.route('/')
async def quart_index():
    return await quart_render_template('index.html')

@quart_app.route('/results', methods=['GET'])
async def quart_results():
    return quart_jsonify({"message": "Results (Spotify)"})

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
