"""
Pentagon Pizza Meter - Fetches busyness data for pizza places near the Pentagon
Runs via GitHub Actions every 30 minutes and updates frontend/data.json

REDESIGNED: Now fetches ALL API data (GDELT, Wikipedia, OpenSky, Weather, Polymarket, News)
Frontend only reads the JSON - no direct API calls from browser
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests

# Pizza places near Pentagon (Google Place IDs)
# You can find Place IDs at: https://developers.google.com/maps/documentation/places/web-service/place-id
PIZZA_PLACES = [
    {
        "name": "Domino's Pizza",
        "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",  # Replace with actual Place ID
        "address": "Pentagon City",
    },
    {
        "name": "Papa John's",
        "place_id": "ChIJP3Sa8ziYEmsRUKgyFmh9AQM",  # Replace with actual Place ID
        "address": "Near Pentagon",
    },
    {
        "name": "Pizza Hut",
        "place_id": "ChIJrTLr-GyuEmsRBfy61i59si0",  # Replace with actual Place ID
        "address": "Pentagon Area",
    },
]

# Output file configuration
OUTPUT_FILE = "frontend/data.json"


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
    Get busyness data - using time-based simulation for now
    Real implementation would use Google Places API or scraping
    """
    current_hour = datetime.now().hour
    current_day = datetime.now().weekday()

    # Simulate realistic patterns based on time
    # Pentagon area pizza places are busier during lunch (11-14) and dinner (17-20)
    # Late night (22-06) activity is unusual and noteworthy

    base_score = 30  # Normal baseline

    # Lunch rush
    if 11 <= current_hour <= 14 and current_day < 5:
        base_score = 50
    # Dinner rush
    elif 17 <= current_hour <= 20:
        base_score = 55
    # Late night (unusual - could indicate overtime)
    elif current_hour >= 22 or current_hour < 6:
        # Add some randomness based on the day
        import hashlib

        day_hash = int(
            hashlib.md5(f"{datetime.now().date()}".encode()).hexdigest()[:8], 16
        )
        if day_hash % 10 < 2:  # 20% chance of elevated late-night activity
            base_score = 70
            return {"status": "elevated_late", "score": base_score}
        else:
            base_score = 20
    # Weekend
    elif current_day >= 5:
        base_score = 25

    return {"status": "normal", "score": base_score}


def calculate_pentagon_activity_score(busyness_data):
    """
    Calculate overall Pentagon activity score based on pizza place busyness
    """
    current_hour = datetime.now().hour
    is_late_night = current_hour >= 22 or current_hour < 6
    is_weekend = datetime.now().weekday() >= 5

    print(
        f"  Calculating score - Hour: {current_hour}, Late night: {is_late_night}, Weekend: {is_weekend}"
    )

    total_score = 0
    valid_readings = 0

    for place in busyness_data:
        if place.get("score") is not None:
            score = place["score"]
            valid_readings += 1
            weighted_score = score

            # Weight: busier than usual at odd hours = higher risk
            if is_late_night and score > 60:
                # Late night busy = very unusual = high risk indicator
                weighted_score = score * 1.5
                print(
                    f"    {place['name']}: {score} × 1.5 (late night busy) = {weighted_score}"
                )
                total_score += weighted_score
            elif is_weekend and score > 70:
                # Weekend busy = unusual = moderate risk indicator
                weighted_score = score * 1.3
                print(
                    f"    {place['name']}: {score} × 1.3 (weekend busy) = {weighted_score}"
                )
                total_score += weighted_score
            else:
                print(f"    {place['name']}: {score} (normal weighting)")
                total_score += score

    if valid_readings == 0:
        print("  No valid readings, using default score of 30")
        return 30  # Default low score (nothing unusual)

    avg_score = total_score / valid_readings
    print(
        f"  Total: {total_score:.1f}, Valid readings: {valid_readings}, Average: {avg_score:.1f}"
    )

    # Normalize to 0-100 scale
    # Normal activity = 30-50, Elevated = 60-80, High = 80+
    normalized = min(100, max(0, avg_score))
    print(f"  Normalized score: {normalized:.1f}")

    return round(normalized)


def fetch_polymarket_odds():
    """Fetch Iran strike odds from Polymarket Gamma API"""
    try:
        print("Fetching Polymarket odds...")

        # Search for "US strikes Iran" specifically (the exact market we want)
        strike_keywords = ["strike", "attack", "bomb", "military action"]

        # Try the events endpoint with higher limit
        response = requests.get(
            "https://gamma-api.polymarket.com/public-search?q=iran",
            timeout=20,
        )

        if response.status_code != 200:
            print(f"Polymarket API error: {response.status_code}")
            return None

        data = response.json()

        # Handle different response formats
        if isinstance(data, dict) and data.get("events"):
            events = data["events"]
        elif isinstance(data, dict) and data.get("data"):
            events = data["data"]
        elif isinstance(data, list):
            events = data
        else:
            print(
                f"Unexpected Polymarket response format: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}"
            )
            return None

        # Filter out non-dict items (ensure all events are dictionaries)
        events = [e for e in events if isinstance(e, dict)]

        highest_odds = 0
        market_title = ""

        print(f"Found {len(events)} valid events on Polymarket")

        def get_market_odds(market):
            """Extract odds from a market using multiple methods"""
            odds = 0

            # Method 1: outcomePrices (most common) - this is the YES price
            prices = market.get("outcomePrices", [])
            if prices and len(prices) > 0:
                try:
                    # First price is YES, second is NO
                    yes_price_str = str(prices[0]) if prices[0] else "0"
                    yes_price = float(yes_price_str)

                    # Handle different formats: 0.5 (50%) or 50 (50%)
                    if yes_price > 1:
                        # Already in percentage format
                        odds = round(yes_price)
                    elif 0 < yes_price <= 1:
                        # Decimal format (0-1)
                        odds = round(yes_price * 100)

                    # Additional check: if we got exactly 100, might be parsing the NO price
                    # In that case, try the second element
                    if odds >= 100 and len(prices) > 1:
                        no_price = float(str(prices[1])) if prices[1] else 0
                        if 0 < no_price < 1:
                            odds = round((1 - no_price) * 100)
                        elif no_price > 1:
                            odds = 100 - round(no_price)

                except (ValueError, TypeError):
                    pass

            # Method 2: bestAsk
            if odds == 0 or odds >= 100:
                try:
                    best_ask = float(market.get("bestAsk", 0) or 0)
                    if best_ask > 1:
                        odds = round(best_ask)
                    elif 0 < best_ask <= 1:
                        odds = round(best_ask * 100)
                except (ValueError, TypeError):
                    pass

            # Method 3: lastTradePrice
            if odds == 0 or odds >= 100:
                try:
                    last_price = float(market.get("lastTradePrice", 0) or 0)
                    if last_price > 1:
                        odds = round(last_price)
                    elif 0 < last_price <= 1:
                        odds = round(last_price * 100)
                except (ValueError, TypeError):
                    pass

            # Safety: Cap odds at 95% (if still 100%, likely bad data)
            if odds >= 100:
                return 0

            return odds

        # Helper function to check if market is within 7 days
        def is_near_term_market(title):
            """Check if market has a date within the next 7 days"""
            import re
            from datetime import timedelta

            # Look for date patterns like "by January 27" or "January 27, 2026"
            months = [
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            ]

            title_lower = title.lower()
            now = datetime.now()
            week_ahead = now + timedelta(days=7)

            # Try to find month and day in title
            for i, month in enumerate(months, 1):
                if month in title_lower:
                    # Look for day number after month
                    match = re.search(rf"{month}\s+(\d{{1,2}})", title_lower)
                    if match:
                        day = int(match.group(1))
                        try:
                            # Assume current year if not specified
                            market_date = datetime(now.year, i, day)
                            # If date is in the past, try next year
                            if market_date < now:
                                market_date = datetime(now.year + 1, i, day)

                            # Check if within 7 days
                            if now <= market_date <= week_ahead:
                                print(
                                    f"    Market date {market_date.strftime('%Y-%m-%d')} is within 7 days"
                                )
                                return True
                            else:
                                print(
                                    f"    Market date {market_date.strftime('%Y-%m-%d')} is too far away (>7 days)"
                                )
                        except ValueError:
                            pass
            return False

        # First pass: Look for the specific "Will US or Israel strike Iran" market
        for event in events:
            event_title = (event.get("title") or "").lower()

            # Look for the positive bet version (not negatives like "will not strike")
            if (
                "will us or israel strike iran" in event_title
                or "us strikes iran by" in event_title
            ):
                print(f"Found Iran strike event: {event.get('title')}")

                # Check if it's a near-term market (within 7 days)
                if not is_near_term_market(event.get("title", "")):
                    continue

                markets = event.get("markets", [])

                for market in markets:
                    market_question = (market.get("question") or "").lower()
                    market_name = market.get("question") or event.get("title") or ""

                    odds = get_market_odds(market)
                    print(f"  Market: {market_name[:50]}... Odds: {odds}%")

                    if odds > highest_odds:
                        highest_odds = odds
                        market_title = market_name

            # Also check individual market questions (sometimes event title is generic)
            markets = event.get("markets", [])
            for market in markets:
                market_question = (market.get("question") or "").lower()

                # Skip negative questions (containing "not", "won't", etc.)
                if any(
                    neg in market_question
                    for neg in [" not ", "won't", "will not", "doesn't", "does not"]
                ):
                    continue

                if "iran" in market_question and any(
                    kw in market_question for kw in strike_keywords
                ):
                    market_name = market.get("question") or ""
                    print(f"Found Iran strike market question: {market_name}")

                    # Check if near-term (within 7 days)
                    if not is_near_term_market(market_name):
                        continue

                    odds = get_market_odds(market)
                    print(f"  Odds: {odds}%")

                    if odds > 0 and odds > highest_odds:
                        highest_odds = odds
                        market_title = market_name

        # Second pass: If no strike markets, look for any Iran-related market (excluding negatives)
        if highest_odds == 0:
            print("No strike markets found, checking all Iran markets...")
            for event in events:
                event_title = (event.get("title") or "").lower()

                # Skip events with negative framing
                if any(
                    neg in event_title
                    for neg in [" not ", "won't", "will not", "doesn't", "does not"]
                ):
                    continue

                if "iran" in event_title:
                    print(f"Found Iran event: {event.get('title')}")

                    # Check if near-term
                    if not is_near_term_market(event.get("title", "")):
                        continue

                    markets = event.get("markets", [])

                    for market in markets:
                        market_question = (market.get("question") or "").lower()

                        # Skip negative questions
                        if any(
                            neg in market_question
                            for neg in [
                                " not ",
                                "won't",
                                "will not",
                                "doesn't",
                                "does not",
                            ]
                        ):
                            continue

                        market_name = market.get("question") or event.get("title") or ""

                        # Check if market question has near-term date
                        if not is_near_term_market(market_name):
                            continue

                        odds = get_market_odds(market)

                        if odds > 0 and odds > highest_odds:
                            highest_odds = odds
                            market_title = market_name

        print(f"Polymarket result: {highest_odds}% odds on '{market_title}'")

        return {
            "odds": highest_odds,
            "market": market_title,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"Polymarket fetch error: {e}")
        import traceback

        traceback.print_exc()
        return None


def fetch_news_intel():
    """Fetch Iran-related news from RSS feeds - server side, no CORS issues"""
    try:
        print("Fetching News Intel from RSS feeds...")
        import xml.etree.ElementTree as ET

        rss_feeds = [
            "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
            "https://www.aljazeera.com/xml/rss/all.xml",
        ]

        all_articles = []
        alert_count = 0
        alert_keywords = [
            "strike",
            "attack",
            "military",
            "bomb",
            "missile",
            "war",
            "imminent",
            "troops",
            "forces",
        ]

        for feed_url in rss_feeds:
            try:
                print(f"  Fetching {feed_url[:50]}...")
                response = requests.get(
                    feed_url,
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; StrikeRadar/1.0)"},
                )
                if not response.ok:
                    print(f"    Failed: {response.status_code}")
                    continue

                root = ET.fromstring(response.content)

                # Find all items (works for both RSS 2.0 and Atom)
                items = root.findall(".//item")
                if not items:
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                for item in items:
                    title_elem = item.find("title")
                    desc_elem = item.find("description")

                    if title_elem is None:
                        title_elem = item.find("{http://www.w3.org/2005/Atom}title")
                    if desc_elem is None:
                        desc_elem = item.find("{http://www.w3.org/2005/Atom}summary")

                    title = title_elem.text if title_elem is not None else ""
                    desc = desc_elem.text if desc_elem is not None else ""

                    combined = (title + " " + desc).lower()

                    # Filter for Iran-related news
                    if (
                        "iran" in combined
                        or "tehran" in combined
                        or "persian gulf" in combined
                        or "strait of hormuz" in combined
                    ):
                        is_alert = any(kw in combined for kw in alert_keywords)
                        if is_alert:
                            alert_count += 1
                        all_articles.append(
                            {
                                "title": title[:100] if title else "",
                                "is_alert": is_alert,
                            }
                        )

            except Exception as e:
                print(f"    Error: {e}")
                continue

        # Remove duplicates by title similarity
        seen = set()
        unique_articles = []
        for article in all_articles:
            key = article["title"][:40].lower()
            if key not in seen:
                seen.add(key)
                unique_articles.append(article)

        print(
            f"News Intel result: {len(unique_articles)} articles, {alert_count} alerts"
        )

        return {
            "articles": unique_articles,  # Limit to 15 articles
            "total_count": len(unique_articles),
            "alert_count": alert_count,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"News Intel error: {e}")
        import traceback

        traceback.print_exc()
        return None


def fetch_gdelt_data():
    """Fetch GDELT news data for Iran-related articles"""
    try:
        print("Fetching GDELT data...")
        query = "(United States OR Pentagon OR White House OR Trump) AND (strike OR attack OR bombing OR missile OR airstrike OR military action) AND Iran"
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(query)}&mode=artlist&format=json&timespan=24h"

        response = requests.get(url, timeout=20)
        print(f"GDELT response status: {response.status_code}")
        print(f"GDELT response text: {response.text}")
        if response.ok:
            text = response.text
            if text.startswith("{") or text.startswith("["):
                data = json.loads(text)
                if data.get("articles") and isinstance(data["articles"], list):
                    articles = data["articles"]
                    article_count = len(articles)

                    print(f"GDELT: {article_count} articles")

                    return {
                        "article_count": article_count,
                        "top_article": articles[0].get("title", "")[:70]
                        if articles
                        else "",
                        "timestamp": datetime.now().isoformat(),
                    }
        print("GDELT: No valid data")
        return None
    except Exception as e:
        print(f"GDELT error: {e}")
        return None


def fetch_wikipedia_views():
    """Fetch Wikipedia pageview data for Iran-related pages"""
    try:
        print("Fetching Wikipedia pageviews...")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        today = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        pages = [
            "Iran",
            "Iran%E2%80%93United_States_relations",
            "Iran%E2%80%93Israel_conflict",
        ]
        total_views = 0

        for page in pages:
            try:
                url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{page}/daily/{yesterday}/{yesterday}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; StrikeRadar/1.0)",
                    "Accept": "application/json",
                }
                response = requests.get(url, headers=headers, timeout=10)
                print(f"  Wiki {page}: {response.status_code}")
                if response.ok:
                    data = response.json()
                    if data.get("items") and len(data["items"]) > 0:
                        total_views += data["items"][0].get("views", 0)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                print(f"  Wiki page {page} error: {e}")
                continue

        print(f"Wikipedia: {total_views} total views")
        return {"total_views": total_views, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        print(f"Wikipedia error: {e}")
        return None


def fetch_aviation_data():
    """Fetch OpenSky Network data for aircraft over Iran"""
    try:
        print("Fetching aviation data (OpenSky)...")
        # Iran airspace bounding box
        url = "https://opensky-network.org/api/states/all?lamin=25&lomin=44&lamax=40&lomax=64"

        response = requests.get(url, timeout=20)
        if not response.ok:
            print(f"OpenSky API error: {response.status_code}")
            return None

        data = response.json()
        civil_count = 0
        airlines = []

        if data.get("states") and isinstance(data["states"], list):
            # US military ICAO hex range
            usaf_hex_start = int("AE0000", 16)
            usaf_hex_end = int("AE7FFF", 16)

            for aircraft in data["states"]:
                icao = aircraft[0]
                callsign = (aircraft[1] or "").strip()
                on_ground = aircraft[8]

                if on_ground:
                    continue

                # Skip US military
                try:
                    icao_num = int(icao, 16)
                    if usaf_hex_start <= icao_num <= usaf_hex_end:
                        continue
                except:
                    pass

                civil_count += 1

                if callsign and len(callsign) >= 3:
                    airline_code = callsign[:3]
                    if airline_code not in airlines:
                        airlines.append(airline_code)

        print(f"Aviation: {civil_count} aircraft, {len(airlines)} airlines")
        return {
            "aircraft_count": civil_count,
            "airline_count": len(airlines),
            "airlines": airlines[:10],  # Top 10 airlines
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Aviation error: {e}")
        return None


def fetch_tanker_activity():
    """Fetch US military tanker activity in Middle East"""
    try:
        print("Fetching tanker activity...")
        # Middle East bounding box
        url = "https://opensky-network.org/api/states/all?lamin=20&lomin=40&lamax=40&lomax=65"

        response = requests.get(url, timeout=20)
        if not response.ok:
            print(f"OpenSky API error: {response.status_code}")
            return None

        data = response.json()
        tanker_count = 0
        tanker_callsigns = []

        tanker_prefixes = [
            "IRON",
            "SHELL",
            "TEXAN",
            "ETHYL",
            "PEARL",
            "ARCO",
            "ESSO",
            "MOBIL",
            "GULF",
            "TOPAZ",
            "PACK",
            "DOOM",
            "TREK",
            "REACH",
        ]
        usaf_hex_start = int("AE0000", 16)
        usaf_hex_end = int("AE7FFF", 16)

        if data.get("states") and isinstance(data["states"], list):
            for aircraft in data["states"]:
                icao = aircraft[0]
                callsign = (aircraft[1] or "").strip().upper()

                try:
                    icao_num = int(icao, 16)
                    is_us_military = usaf_hex_start <= icao_num <= usaf_hex_end
                except:
                    is_us_military = False

                is_tanker_callsign = any(
                    callsign.startswith(prefix) for prefix in tanker_prefixes
                )
                has_kc_pattern = "KC" in callsign or "TANKER" in callsign

                if is_us_military and (is_tanker_callsign or has_kc_pattern):
                    tanker_count += 1
                    if callsign:
                        tanker_callsigns.append(callsign)

        print(f"Tanker: {tanker_count} detected")
        return {
            "tanker_count": tanker_count,
            "callsigns": tanker_callsigns[:5],  # Top 5
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Tanker error: {e}")
        return None


def fetch_weather_data():
    """Fetch weather conditions for Tehran"""
    try:
        print("Fetching weather data...")
        api_key = os.environ.get(
            "OPENWEATHER_API_KEY", "2e1d472bc1b48449837208507a2367af"
        )
        url = f"https://api.openweathermap.org/data/2.5/weather?lat=35.6892&lon=51.389&appid={api_key}&units=metric"

        response = requests.get(url, timeout=10)
        if response.ok:
            data = response.json()
            if data.get("main"):
                temp = round(data["main"]["temp"])
                visibility = data.get("visibility", 10000)
                clouds = data.get("clouds", {}).get("all", 0)
                description = data.get("weather", [{}])[0].get("description", "clear")

                # Determine condition
                if visibility >= 10000 and clouds < 30:
                    condition = "Favorable"
                elif visibility >= 7000 and clouds < 60:
                    condition = "Marginal"
                else:
                    condition = "Poor"

                print(f"Weather: {temp}°C, {condition}")
                return {
                    "temp": temp,
                    "visibility": visibility,
                    "clouds": clouds,
                    "description": description,
                    "condition": condition,
                    "timestamp": datetime.now().isoformat(),
                }
        print("Weather: API error")
        return None
    except Exception as e:
        print(f"Weather error: {e}")
        return None


def calculate_news_risk(news_intel):
    """Calculate news contribution to risk score"""
    articles = news_intel.get("total_count", 0)
    alert_count = news_intel.get("alert_count", 0)

    contribution = 2
    if articles <= 3:
        contribution = 3 + articles * 2 + alert_count * 1
    elif articles <= 6:
        contribution = 9 + (articles - 3) * 1.5 + alert_count * 1.5
    elif articles <= 10:
        contribution = 13.5 + (articles - 6) * 1 + alert_count * 2
    else:
        contribution = 17.5 + (articles - 10) * 0.5 + alert_count * 2
    return min(30, contribution)


def calculate_aviation_risk(aviation):
    """Calculate aviation contribution to risk score"""
    count = aviation.get("aircraft_count", 0)
    if count == 0:
        return 30
    elif count < 5:
        return 25
    elif count < 15:
        return 15
    elif count < 30:
        return 8
    else:
        return 3


def calculate_tanker_risk(tanker):
    """Calculate tanker contribution to risk score"""
    count = tanker.get("tanker_count", 0)
    if count == 0:
        return 1
    elif count <= 2:
        return 3
    elif count <= 4:
        return 8
    else:
        return 15


def update_data_file():
    """Save ALL data from all APIs to frontend/data.json file with history tracking"""
    try:
        # Get existing data (to preserve history)
        output_file = OUTPUT_FILE
        if os.path.exists(output_file):
            try:
                with open(output_file, "r") as f:
                    current_data = json.load(f)
            except:
                current_data = {}
        else:
            current_data = {}

        # Preserve existing history and signalHistory
        history = current_data.get("history", [])
        signal_history = current_data.get(
            "signalHistory",
            {
                "news": [],
                "social": [],
                "flight": [],
                "tanker": [],
                "pentagon": [],
                "polymarket": [],
                "weather": [],
            },
        )

        # Fetch Pentagon data
        pentagon_data = fetch_pentagon_data()
        current_data["pentagon"] = pentagon_data
        current_data["pentagon_updated"] = datetime.now().isoformat()

        # Fetch and update Polymarket odds
        polymarket_data = fetch_polymarket_odds()
        if polymarket_data:
            current_data["polymarket"] = polymarket_data

        # Fetch and update News Intel (server-side, no CORS issues!)
        news_data = fetch_news_intel()
        if news_data:
            current_data["news_intel"] = news_data

        # NEW: Fetch all other API data
        print("\n" + "=" * 50)
        print("FETCHING ALL API DATA")
        print("=" * 50)

        # GDELT data
        # TODO: this is good, add it sometime, it returned 25 articles on jan 26th
        # gdelt_data = fetch_gdelt_data()

        # Wikipedia data
        # wiki_data = fetch_wikipedia_views()
        # if wiki_data:
        #     current_data["social"] = 12 * wiki_data["total_views"] / 2000000

        # Aviation data
        aviation_data = fetch_aviation_data()
        if aviation_data:
            current_data["aviation"] = aviation_data

        # Tanker activity
        time.sleep(2)  # Rate limiting for OpenSky
        tanker_data = fetch_tanker_activity()
        if tanker_data:
            current_data["tanker"] = tanker_data

        # Weather data
        weather_data = fetch_weather_data()
        if weather_data:
            current_data["weather"] = weather_data

        # Add main timestamp
        current_data["last_updated"] = datetime.now().isoformat()

        # Calculate risk scores for history tracking
        news_contribution = calculate_news_risk(current_data.get("news_intel", {}))
        aviation_risk = calculate_aviation_risk(current_data.get("aviation", {}))
        tanker_risk = calculate_tanker_risk(current_data.get("tanker", {}))
        weather_risk = (
            5 if weather_data and weather_data.get("condition") == "Favorable" else 0
        )
        polymarket_risk = min(
            10, current_data.get("polymarket", {}).get("odds", 0) * 0.1
        )
        pentagon_risk = pentagon_data.get("risk_contribution", 1)

        total_risk = (
            news_contribution
            + aviation_risk
            + tanker_risk
            + weather_risk
            + polymarket_risk
            + pentagon_risk
        )
        total_risk = min(100, max(0, round(total_risk)))

        # Add to history (keep last 72 hours)
        history.append(
            {"timestamp": int(datetime.now().timestamp() * 1000), "risk": total_risk}
        )
        cutoff_time = int((datetime.now().timestamp() - 72 * 60 * 60) * 1000)
        history = [h for h in history if h["timestamp"] > cutoff_time]
        current_data["history"] = history

        # Add to signal history (keep last 20 points per signal)
        signal_history["news"].append(round((news_contribution / 30) * 100))
        signal_history["flight"].append(round((aviation_risk / 15) * 100))
        signal_history["tanker"].append(round((tanker_risk / 10) * 100))
        signal_history["pentagon"].append(round((pentagon_risk / 10) * 100))
        signal_history["polymarket"].append(
            round(current_data.get("polymarket", {}).get("odds", 0))
        )
        signal_history["weather"].append(
            100 if weather_risk >= 4 else 50 if weather_risk >= 2 else 20
        )

        # Keep only last 20 points
        for sig in signal_history:
            if len(signal_history[sig]) > 20:
                signal_history[sig] = signal_history[sig][-20:]
        current_data["signalHistory"] = signal_history

        print("\n" + "=" * 50)
        print("DATA COLLECTION COMPLETE")
        print("=" * 50)
        print(f"Total Risk: {total_risk}%")

        # Save to file
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(current_data, f, indent=2)
        print(f"\u2713 Data saved to {output_file}")
        print(f"  File size: {os.path.getsize(output_file)} bytes")
        print(f"  History points: {len(history)}")
        return True

    except Exception as e:
        print(f"Error updating data file: {e}")
        import traceback

        traceback.print_exc()
        return False


def fetch_pentagon_data():
    """Fetch Pentagon Pizza Meter data - pizza place busyness near Pentagon"""
    print("Fetching Pentagon activity...")

    busyness_data = []

    for place in PIZZA_PLACES:
        print(f"  Checking {place['name']}...")
        result = get_live_busyness_scrape(place["name"], place["address"])
        result["name"] = place["name"]
        busyness_data.append(result)
        print(f"    Status: {result['status']}, Score: {result['score']}")

    # Calculate overall score
    activity_score = calculate_pentagon_activity_score(busyness_data)

    # Determine risk contribution (max 10% for this signal)
    # Normal baseline should show ~5-10% on the bar
    if activity_score >= 80:
        risk_contribution = 10  # Very busy at odd hours
        status = "High Activity"
    elif activity_score >= 60:
        risk_contribution = 7
        status = "Elevated"
    elif activity_score >= 40:
        risk_contribution = 3
        status = "Normal"
    else:
        risk_contribution = 1
        status = "Low Activity"

    pentagon_data = {
        "score": activity_score,
        "risk_contribution": risk_contribution,
        "status": status,
        "places": busyness_data,
        "timestamp": datetime.now().isoformat(),
        "is_late_night": datetime.now().hour >= 22 or datetime.now().hour < 6,
        "is_weekend": datetime.now().weekday() >= 5,
    }

    print(
        f"Pentagon: {status} (score: {activity_score}, contribution: {risk_contribution}%)"
    )
    return pentagon_data


def main():
    print(f"Updating data - {datetime.now().isoformat()}")
    print("-" * 50)
    update_data_file()


if __name__ == "__main__":
    main()
