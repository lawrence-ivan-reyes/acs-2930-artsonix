#!/bin/zsh

BASE_URL="http://localhost:3000/results"

MOODS=(
  "happy" "sad" "energetic" "relaxed" "romantic" "melancholic" "focused" "upbeat" "rebellious" "mystical"
  "dark" "nostalgic" "trippy" "lofi" "party" "driving" "workout" "epic" "spiritual" "chill" "experimental"
  "video game" "anime" "gothic" "emotional" "gangster" "roadtrip" "latin vibes" "weird" "meme" "sleep"
  "rainy day" "summer" "winter"
)

# Function to URL encode moods with spaces (uses Perl for better portability)
urlencode() {
  echo -n "$1" | perl -MURI::Escape -ne 'print uri_escape($_)'
}

for MOOD in "${MOODS[@]}"; do
    ENCODED_MOOD=$(urlencode "$MOOD")
    echo "🎵 Testing mood: $MOOD"

    RESPONSE=$(curl -s -w "%{http_code}" -H "Accept: application/json" "${BASE_URL}?query=${ENCODED_MOOD}&rec_type=playlist")
    HTTP_STATUS="${RESPONSE: -3}"
    JSON_BODY="${RESPONSE:0:-3}"

    case "$HTTP_STATUS" in
        200)
            if jq -e . >/dev/null 2>&1 <<< "$JSON_BODY"; then
                echo "$JSON_BODY" | jq '.results // "⚠️ No results found!"'
            else
                echo "⚠️ Non-JSON response detected!"
            fi
            ;;
        400) echo "❌ Bad Request (400) - Check query parameters!" ;;
        500) echo "❌ Server Error (500) - API issue!" ;;
        *) echo "❌ API request failed with status: $HTTP_STATUS" ;;
    esac

    echo -e "\n-------------------------------\n"
done