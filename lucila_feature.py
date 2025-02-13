from flask import Flask, render_template, request, jsonify
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

@app.route('/')
def index():
    return render_template('index.html')

def search_artwork(title, artist=None):
    query_params = {"q": title}
    if artist:
        query_params["artistOrCulture"] = artist

    response = requests.get(f"{BASE_URL}/search", params=query_params)
    search_results = response.json()
    print(search_results) 
    return search_results.get("objectIDs", [])

def get_artwork_details(object_id):
    response = requests.get(f"{BASE_URL}/objects/{object_id}")
    data = response.json()
    print(data)  
    return data

@app.route('/results')
def results():
    art_styles = request.args.getlist("art_style")
    if not art_styles:
        return render_template('error.html', message="Art style is required")

    artworks = []
    seen_object_ids = set()

    for style in art_styles:
        response = requests.get(f"{BASE_URL}/search", params={"q": style})
        search_results = response.json()
        print(f"Search results for style '{style}': {search_results}")  # Detailed log

        object_ids = search_results.get("objectIDs", [])

        count = 0
        if object_ids:
            for obj_id in object_ids:
                if count >= 3:
                    break
                print(f"Processing object ID: {obj_id}")  # Detailed log
                if obj_id not in seen_object_ids:
                    obj_response = get_artwork_details(obj_id)
                    if obj_response.get("isPublicDomain"):
                        if "primaryImageSmall" in obj_response and obj_response["primaryImageSmall"]:
                            artworks.append(obj_response)
                            seen_object_ids.add(obj_id)
                            count += 1

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
    per_page = 9  # Results per page

    if not query:
        return jsonify({"error": "Please provide a search query using ?q=keyword"}), 400

    response = requests.get(f"{BASE_URL}/search", params={"q": query})
    search_results = response.json()
    print(f"Search results: {search_results}")  # Detailed log
    object_ids = search_results.get("objectIDs", [])

    total_results = len(object_ids)
    total_pages = math.ceil(total_results / per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_ids = object_ids[start_idx:end_idx]
    artworks = []

    for obj_id in paginated_ids:
        obj_response = get_artwork_details(obj_id)
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
