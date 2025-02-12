from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import requests
from dotenv import load_dotenv
import math

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
OPENAIBASE_URL = "https://api.openai.com/v1/moderations"

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/objects", methods=["GET"])
def get_objects():
    """Fetch all available object IDs from the Met Museum API."""
    response = requests.get(f"{BASE_URL}/objects")
    return jsonify(response.json())

@app.route("/object/<int:object_id>", methods=["GET"])
def get_object(object_id):
    """Fetch details of a specific artwork using its object ID."""
    response = requests.get(f"{BASE_URL}/objects/{object_id}")
    data = response.json()
    if "primaryImage" in data and data["primaryImage"]:
        return render_template("artwork.html", artwork=data)
    return jsonify(data)

@app.route('/results')
def results():
    art_style = request.args.get("art_style")

    if not art_style:
        return render_template('error.html', message="Art style is required")

    # Fetch artworks from The Met API based on art style
    response = requests.get(f"{BASE_URL}/search", params={"q": art_style})
    search_results = response.json()

    object_ids = search_results.get("objectIDs", [])

    artworks = []
    if object_ids:
        for obj_id in object_ids[:10]:  # Fetch details for the first 10 artworks
            obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
            if obj_response.get("isPublicDomain"): # Check if artwork is public domain
                if "primaryImageSmall" in obj_response and obj_response["primaryImageSmall"]:
                    artworks.append(obj_response)

    return render_template('results.html', artworks=artworks, has_results=bool(artworks))


@app.route("/search", methods=["GET"])
def search_objects():
    """Search for artworks with pagination, filtering, and sorting."""
    query = request.args.get("q")
    artist = request.args.get("artist")
    year = request.args.get("year")
    medium = request.args.get("medium")
    sort_by = request.args.get("sort", "title")  
    page = int(request.args.get("page", 1))
    per_page = 10  # Results per page

    if not query:
        return jsonify({"error": "Please provide a search query using ?q=keyword"}), 400

    response = requests.get(f"{BASE_URL}/search", params={"q": query})
    search_results = response.json()
    object_ids = search_results.get("objectIDs", [])

    total_results = len(object_ids)
    total_pages = math.ceil(total_results / per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_ids = object_ids[start_idx:end_idx]
    artworks = []

    for obj_id in paginated_ids:
        obj_response = requests.get(f"{BASE_URL}/objects/{obj_id}").json()
        # Apply additional filters (artist, year, medium)
        if artist and artist.lower() not in obj_response.get("artistDisplayName", "").lower():
            continue
        if year and str(year) not in obj_response.get("objectDate", ""):
            continue
        if medium and medium.lower() not in obj_response.get("medium", "").lower():
            continue
        if "primaryImageSmall" in obj_response and obj_response["primaryImageSmall"]:
            artworks.append(obj_response)

    # Sorting logic
    if sort_by == "title":
        artworks.sort(key=lambda x: x.get("title", "").lower())
    elif sort_by == "year":
        artworks.sort(key=lambda x: x.get("objectBeginDate", 0))

    return render_template(
        "results.html",
        artworks=artworks,
        query=query,
        sort_by=sort_by,
        page=page,
        total_pages=total_pages,
        has_results=bool(artworks)
    )

@app.route('/error')
def error():
    return render_template('error.html')

if __name__ == '__main__':
    app.run(debug=True, port=3000)
