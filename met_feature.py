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

# searches API for artworks matching user preferences
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

# checks if an artwork's date matches the user's preferred time period
def matches_time_period(artwork, preferred_period):
    date = artwork.get('objectDate', '').lower()
    if preferred_period == 'modern' and any(x in date for x in ['20th', '21st', '1900', '2000']):
        return True
    elif preferred_period == 'ancient' and any(x in date for x in ['bc', 'bce', 'ancient']):
        return True
    return False

# converts user form responses into search terms for the Met API
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

# adding to test hypothetical form responses - handles interactive questionnaire that collects user preferences
def get_user_input():
    print("\n--- Art Preference Questionnaire ---")
    
    # getting mood preference
    while True:
        print("\nHow are you feeling today?")
        print("1. Peaceful")
        print("2. Energetic")
        print("3. Contemplative")
        mood_choice = input("\nEnter the number of your choice: ")
        if mood_choice in ['1', '2', '3']:
            mood_map = {'1': 'peaceful', '2': 'energetic', '3': 'contemplative'}
            mood = mood_map[mood_choice]
            break
        else:
            print("\nInvalid choice! Please enter 1, 2, or 3.")
    
    # getting time period preference
    while True:
        print("\nWhat time period interests you?")
        print("1. Modern")
        print("2. Ancient")
        time_choice = input("\nEnter the number of your choice: ")
        if time_choice in ['1', '2']:
            time_map = {'1': 'modern', '2': 'ancient'}
            time_period = time_map[time_choice]
            break
        else:
            print("\nInvalid choice! Please enter 1 or 2.")
    
    # getting culture preference
    while True:
        print("\nWhich culture interests you?")
        print("1. Japanese")
        print("2. European")
        print("3. Egyptian")
        print("4. Chinese")
        culture_choice = input("\nEnter the number of your choice: ")
        if culture_choice in ['1', '2', '3', '4']:
            culture_map = {'1': 'Japanese', '2': 'European', '3': 'Egyptian', '4': 'Chinese'}
            culture = culture_map[culture_choice]
            break
        else:
            print("\nInvalid choice! Please enter 1, 2, 3, or 4.")
    
    return {
        'mood': mood,
        'time_period': time_period,
        'culture': culture
    }

# displays artwork info in a readable format
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
        print("\nFailed to retrieve artwork information")

def main():
    print("Welcome to the ArtSonix!")

    while True:

        form_data = get_user_input()

        # showing summary of choices
        print("\n--- Your Selected Preferences ---")
        print(f"Mood: {form_data['mood'].title()}")
        print(f"Time Period: {form_data['time_period'].title()}")
        print(f"Culture: {form_data['culture']}")

        # asking for confirmation
        confirm = input("\nAre you happy with these choices? (yes/no): ")
        if confirm.lower() == 'no':
            print("\nLet's try again!")
            continue
        
        # processing form responses into preferences
        user_preferences = process_form_responses(form_data)
        
        # getting matching artwork
        print("\nSearching for matching artwork...")
        artwork = get_matching_artwork(user_preferences)
        
        # displauying result
        display_artwork_info(artwork)
        
        # ask if user wants to try again
        again = input("\nWould you like to try again? (yes/no): ")
        if again.lower() != 'yes':
            break
    
    print("\nThank you for using ArtSonix!")

if __name__ == "__main__":
    main()
