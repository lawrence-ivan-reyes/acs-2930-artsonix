import requests
import random
import json

def get_random_artwork():
    # (putting this as a fallback in case no matches are found)
    objects_url = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
    response = requests.get(objects_url)
    
    if response.status_code == 200:
        objects_data = response.json()
        total_objects = objects_data['total']
        object_ids = objects_data['objectIDs']
        
        random_id = random.choice(object_ids)
        object_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random_id}"
        object_response = requests.get(object_url)
        
        if object_response.status_code == 200:
            artwork = object_response.json()
            return artwork
    
    return None

def get_matching_artwork(user_preferences):
    search_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    
    # buildiong search query based on preferences
    search_terms = []
    if user_preferences.get('subjects'):
        search_terms.extend(user_preferences['subjects'])
    if user_preferences.get('culture'):
        search_terms.append(user_preferences['culture'])
    
    q = " ".join(search_terms)
    
    # making search request
    response = requests.get(search_url, params={'q': q})
    
    if response.status_code == 200:
        results = response.json()
        if results['total'] > 0:
            matching_id = random.choice(results['objectIDs'])
            object_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{matching_id}"
            object_response = requests.get(object_url)
            
            if object_response.status_code == 200:
                artwork = object_response.json()
                if user_preferences.get('time_period'):
                    if matches_time_period(artwork, user_preferences['time_period']):
                        return artwork
    
    # fallback 
    return get_random_artwork()

def matches_time_period(artwork, preferred_period):
    date = artwork.get('objectDate', '').lower()
    if preferred_period == 'modern' and any(x in date for x in ['20th', '21st', '1900', '2000']):
        return True
    elif preferred_period == 'ancient' and any(x in date for x in ['bc', 'bce', 'ancient']):
        return True
    return False

def process_form_responses(form_data):
    preferences = {}
    
    mood_to_subjects = {
        'peaceful': ['landscape', 'nature', 'floral'],
        'energetic': ['action', 'battle', 'dance'],
        'contemplative': ['religious', 'portrait', 'still life']
    }
    
    if form_data.get('mood'):
        preferences['subjects'] = mood_to_subjects.get(form_data['mood'], [])
    
    if form_data.get('time_period'):
        preferences['time_period'] = form_data['time_period']
    
    if form_data.get('culture'):
        preferences['culture'] = form_data['culture']
    
    return preferences

def display_artwork_info(artwork):
    if artwork:
        print("\nArtwork Information:")
        print(f"Title: {artwork.get('title', 'Unknown')}")
        print(f"Artist: {artwork.get('artistDisplayName', 'Unknown')}")
        print(f"Date: {artwork.get('objectDate', 'Unknown')}")
        print(f"Medium: {artwork.get('medium', 'Unknown')}")
        print(f"Department: {artwork.get('department', 'Unknown')}")
        if artwork.get('primaryImage'):
            print(f"Image URL: {artwork['primaryImage']}")
    else:
        print("Failed to retrieve artwork information")

def main():
    # testing - just example form data
    form_data = {
        'mood': 'peaceful',
        'time_period': 'modern',
        'culture': 'Japanese'
    }
    
    # processing form responses into preferences
    user_preferences = process_form_responses(form_data)
    
    # getting matching artwork
    artwork = get_matching_artwork(user_preferences)
    
    # displaying the result
    display_artwork_info(artwork)

if __name__ == "__main__":
    main()
