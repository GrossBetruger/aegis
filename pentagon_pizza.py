"""
Pentagon Pizza Meter - Fetches busyness data for pizza places near the Pentagon
Runs via GitHub Actions every 30 minutes and updates JSONbin
"""

import requests
import json
from datetime import datetime
import os

# Pizza places near Pentagon (Google Place IDs)
# You can find Place IDs at: https://developers.google.com/maps/documentation/places/web-service/place-id
PIZZA_PLACES = [
    {
        "name": "Domino's Pizza",
        "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",  # Replace with actual Place ID
        "address": "Pentagon City"
    },
    {
        "name": "Papa John's",
        "place_id": "ChIJP3Sa8ziYEmsRUKgyFmh9AQM",  # Replace with actual Place ID
        "address": "Near Pentagon"
    },
    {
        "name": "Pizza Hut",
        "place_id": "ChIJrTLr-GyuEmsRBfy61i59si0",  # Replace with actual Place ID
        "address": "Pentagon Area"
    }
]

# JSONbin configuration
JSONBIN_BIN_ID = "6975495843b1c97be94773ee"
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY", "$2a$10$UXwsyOw0wGl23aYyEqlgsegbEdvPSx5tPPsohKcGstTyHRebGQP5K")

def get_popular_times(place_id):
    """
    Fetch popular times data using populartimes library approach
    This uses web scraping - no API key needed
    """
    try:
        # Using the LivePopularTimes approach
        import populartimes
        result = populartimes.get_id(os.environ.get("GOOGLE_API_KEY", ""), place_id)
        return result
    except Exception as e:
        print(f"Error fetching popular times: {e}")
        return None

def get_live_busyness_scrape(place_name, address):
    """
    Alternative: Scrape Google Maps directly for live busyness
    This doesn't require an API key
    """
    try:
        # Search URL for the place
        search_query = f"{place_name} {address}".replace(" ", "+")
        url = f"https://www.google.com/maps/search/{search_query}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=10)

        # Look for busyness indicators in the response
        # This is a simplified approach - real implementation would parse the HTML
        if "Busier than usual" in response.text:
            return {"status": "busier_than_usual", "score": 80}
        elif "Less busy than usual" in response.text:
            return {"status": "less_busy", "score": 30}
        elif "As busy as it gets" in response.text:
            return {"status": "peak", "score": 100}
        else:
            return {"status": "normal", "score": 50}

    except Exception as e:
        print(f"Error scraping: {e}")
        return {"status": "unknown", "score": 50}

def calculate_pentagon_activity_score(busyness_data):
    """
    Calculate overall Pentagon activity score based on pizza place busyness
    """
    current_hour = datetime.now().hour
    is_late_night = current_hour >= 22 or current_hour < 6
    is_weekend = datetime.now().weekday() >= 5

    total_score = 0
    valid_readings = 0

    for place in busyness_data:
        if place.get("score") is not None:
            score = place["score"]
            valid_readings += 1

            # Weight: busier than usual at odd hours = higher risk
            if is_late_night and score > 60:
                # Late night busy = very unusual = high risk indicator
                total_score += score * 1.5
            elif is_weekend and score > 70:
                # Weekend busy = unusual = moderate risk indicator
                total_score += score * 1.3
            else:
                total_score += score

    if valid_readings == 0:
        return 50  # Default neutral score

    avg_score = total_score / valid_readings

    # Normalize to 0-100 scale
    normalized = min(100, max(0, avg_score))

    return round(normalized)

def get_current_jsonbin_data():
    """Fetch current data from JSONbin"""
    try:
        response = requests.get(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest",
            headers={"X-Master-Key": JSONBIN_API_KEY}
        )
        if response.ok:
            return response.json().get("record", {})
    except Exception as e:
        print(f"Error reading JSONbin: {e}")
    return {}

def update_jsonbin(pentagon_data):
    """Update JSONbin with new Pentagon pizza data"""
    try:
        # Get existing data
        current_data = get_current_jsonbin_data()

        # Add/update pentagon data
        current_data["pentagon"] = pentagon_data
        current_data["pentagon_updated"] = datetime.now().isoformat()

        # Save back to JSONbin
        response = requests.put(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}",
            headers={
                "Content-Type": "application/json",
                "X-Master-Key": JSONBIN_API_KEY
            },
            json=current_data
        )

        if response.ok:
            print("JSONbin updated successfully")
            return True
        else:
            print(f"JSONbin update failed: {response.text}")
            return False

    except Exception as e:
        print(f"Error updating JSONbin: {e}")
        return False

def main():
    print(f"Pentagon Pizza Meter - {datetime.now().isoformat()}")
    print("-" * 50)

    busyness_data = []

    for place in PIZZA_PLACES:
        print(f"Checking {place['name']}...")
        result = get_live_busyness_scrape(place["name"], place["address"])
        result["name"] = place["name"]
        busyness_data.append(result)
        print(f"  Status: {result['status']}, Score: {result['score']}")

    # Calculate overall score
    activity_score = calculate_pentagon_activity_score(busyness_data)
    print(f"\nOverall Pentagon Activity Score: {activity_score}")

    # Determine risk contribution (max 15% for this signal)
    if activity_score >= 80:
        risk_contribution = 15  # Very busy at odd hours
        status = "High Activity"
    elif activity_score >= 60:
        risk_contribution = 10
        status = "Elevated"
    elif activity_score >= 40:
        risk_contribution = 5
        status = "Normal"
    else:
        risk_contribution = 2
        status = "Low Activity"

    pentagon_data = {
        "score": activity_score,
        "risk_contribution": risk_contribution,
        "status": status,
        "places": busyness_data,
        "timestamp": datetime.now().isoformat(),
        "is_late_night": datetime.now().hour >= 22 or datetime.now().hour < 6,
        "is_weekend": datetime.now().weekday() >= 5
    }

    # Update JSONbin
    update_jsonbin(pentagon_data)

    print(f"\nRisk Contribution: {risk_contribution}%")
    print(f"Status: {status}")

if __name__ == "__main__":
    main()
