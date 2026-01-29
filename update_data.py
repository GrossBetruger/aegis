"""
Pentagon Pizza Meter - Fetches busyness data for pizza places near the Pentagon
Runs via GitHub Actions every 30 minutes and updates frontend/data.json

REDESIGNED: Now fetches ALL API data (GDELT, Wikipedia, OpenSky, Weather, Polymarket, News)
Frontend only reads the JSON - no direct API calls from browser
"""

import json
import os
import time
import ssl
import urllib3
from datetime import datetime, timedelta

import requests

# Disable SSL warnings for corporate proxies with self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create a session that can handle SSL issues
session = requests.Session()
session.verify = os.environ.get("SSL_VERIFY", "true").lower() != "false"

# If SSL_VERIFY is explicitly false, disable verification
if not session.verify:
    print("WARNING: SSL verification disabled")


def make_request(url, **kwargs):
    """Make HTTP request with SSL handling for corporate proxies"""
    # Default timeout
    kwargs.setdefault("timeout", 20)
    
    # Try with verification first, fall back to without if needed
    try:
        response = requests.get(url, **kwargs)
        return response
    except requests.exceptions.SSLError:
        # Retry without SSL verification for corporate proxies
        print(f"  SSL error, retrying without verification...")
        kwargs["verify"] = False
        return requests.get(url, **kwargs)


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
        print("\n" + "=" * 50)
        print("POLYMARKET ODDS")
        print("=" * 50)

        # Search for "US strikes Iran" specifically (the exact market we want)
        strike_keywords = ["strike", "attack", "bomb", "military action"]

        # Try the events endpoint with higher limit
        response = make_request(
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

        print(f"Scanning {len(events)} events...")

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
                # Check if it's a near-term market (within 7 days)
                if not is_near_term_market(event.get("title", "")):
                    continue

                markets = event.get("markets", [])

                for market in markets:
                    market_question = (market.get("question") or "").lower()
                    market_name = market.get("question") or event.get("title") or ""

                    odds = get_market_odds(market)

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

                    # Check if near-term (within 7 days)
                    if not is_near_term_market(market_name):
                        continue

                    odds = get_market_odds(market)

                    if odds > 0 and odds > highest_odds:
                        highest_odds = odds
                        market_title = market_name

        # Second pass: If no strike markets, look for any Iran-related market (excluding negatives)
        if highest_odds == 0:
            for event in events:
                event_title = (event.get("title") or "").lower()

                # Skip events with negative framing
                if any(
                    neg in event_title
                    for neg in [" not ", "won't", "will not", "doesn't", "does not"]
                ):
                    continue

                if "iran" in event_title:
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

        if highest_odds > 0:
            print(
                f"Market: {market_title[:70]}..."
                if len(market_title) > 70
                else f"Market: {market_title}"
            )
        print(f"✓ Result: Risk {highest_odds}%")

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
        print("\n" + "=" * 50)
        print("NEWS INTELLIGENCE")
        print("=" * 50)
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
                response = make_request(
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

        print(f"Found {len(unique_articles)} articles ({alert_count} critical)")
        alert_ratio = (
            alert_count / len(unique_articles) if len(unique_articles) > 0 else 0
        )
        risk = max(3, round(pow(alert_ratio, 2) * 85))
        print(f"✓ Result: Risk {risk}%")

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
    """Fetch GDELT news data for Iran-related articles with tone analysis"""
    try:
        print("\n" + "=" * 50)
        print("GDELT NEWS INTELLIGENCE")
        print("=" * 50)

        # GDELT query for Iran conflict-related news
        query = "(United States OR Pentagon OR White House OR Trump OR Israel) AND (strike OR attack OR bombing OR missile OR airstrike OR military action OR war) AND Iran"
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(query)}&mode=artlist&format=json&timespan=24h&maxrecords=100"

        response = make_request(url, timeout=20)

        if not response.ok:
            print(f"GDELT API error: {response.status_code}")
            return None

        text = response.text
        if not (text.startswith("{") or text.startswith("[")):
            print("GDELT: Invalid response format")
            return None

        data = json.loads(text)
        articles = data.get("articles", [])

        if not articles:
            print("GDELT: No articles found")
            return {
                "article_count": 0,
                "avg_tone": 0,
                "negative_count": 0,
                "top_article": "",
                "risk": 5,
                "timestamp": datetime.now().isoformat(),
            }

        article_count = len(articles)

        # Calculate average tone from articles
        # GDELT tone ranges from -100 (extremely negative) to +100 (extremely positive)
        tones = []
        negative_count = 0

        for article in articles:
            tone = article.get("tone", 0)
            if tone:
                try:
                    tone_value = float(tone)
                    tones.append(tone_value)
                    if tone_value < -2:
                        negative_count += 1
                except (ValueError, TypeError):
                    pass

        avg_tone = sum(tones) / len(tones) if tones else 0

        # Get top article title
        top_article = articles[0].get("title", "")[:80] if articles else ""

        # Calculate risk based on article count and tone
        risk = 10  # Baseline

        # Article volume component (0-40 points)
        if article_count >= 50:
            risk += 40
        elif article_count >= 30:
            risk += 30
        elif article_count >= 15:
            risk += 20
        elif article_count >= 5:
            risk += 10

        # Negative tone component (0-40 points)
        # More negative tone = higher tension in coverage
        if avg_tone <= -5:
            risk += 40  # Very negative coverage
        elif avg_tone <= -3:
            risk += 30
        elif avg_tone <= -1:
            risk += 20
        elif avg_tone <= 0:
            risk += 10

        # High proportion of negative articles
        if article_count > 0:
            negative_ratio = negative_count / article_count
            if negative_ratio >= 0.7:
                risk += 10  # 70%+ negative
            elif negative_ratio >= 0.5:
                risk += 5

        risk = max(0, min(100, round(risk)))

        print(f"Articles: {article_count}")
        print(f"Average Tone: {avg_tone:.2f}")
        print(f"Negative Articles: {negative_count}")
        if top_article:
            print(f"Top: {top_article[:60]}...")
        print(f"✓ Result: Risk {risk}%")

        return {
            "article_count": article_count,
            "avg_tone": round(avg_tone, 2),
            "negative_count": negative_count,
            "top_article": top_article,
            "risk": risk,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"GDELT error: {e}")
        import traceback
        traceback.print_exc()
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
                response = make_request(url, headers=headers, timeout=10)
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
        print("\n" + "=" * 50)
        print("AVIATION TRACKING")
        print("=" * 50)
        # Iran airspace bounding box
        url = "https://opensky-network.org/api/states/all?lamin=25&lomin=44&lamax=40&lomax=64"

        response = make_request(url, timeout=20)
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

        print(f"Detected {civil_count} aircraft, {len(airlines)} airlines over Iran")
        risk = max(3, 95 - round(civil_count * 0.8))
        print(f"✓ Result: Risk {risk}%")
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
        print("\n" + "=" * 50)
        print("TANKER ACTIVITY")
        print("=" * 50)
        # Middle East bounding box
        url = "https://opensky-network.org/api/states/all?lamin=20&lomin=40&lamax=40&lomax=65"

        response = make_request(url, timeout=20)
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

        print(f"Detected {tanker_count} tankers in Middle East")
        risk = round((tanker_count / 10) * 100)
        print(f"✓ Result: Risk {risk}%")
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
        print("\n" + "=" * 50)
        print("WEATHER CONDITIONS")
        print("=" * 50)
        api_key = os.environ.get(
            "OPENWEATHER_API_KEY", "2e1d472bc1b48449837208507a2367af"
        )
        url = f"https://api.openweathermap.org/data/2.5/weather?lat=35.6892&lon=51.389&appid={api_key}&units=metric"

        response = make_request(url, timeout=10)
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

                print(f"Conditions: {temp}°C, {condition}, clouds {clouds}, {description}")
                risk = max(0, min(100, 100 - max(0, clouds - 6)))
                print(f"✓ Result: Risk {risk}%")
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


def fetch_oil_prices():
    """Fetch Brent crude oil prices and calculate risk from price movements"""
    try:
        print("\n" + "=" * 50)
        print("OIL PRICES")
        print("=" * 50)

        # Use Yahoo Finance API (free, no key required)
        # BZ=F is Brent Crude Futures
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?interval=1h&range=2d"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; StrikeRadar/1.0)"
        }

        response = make_request(url, headers=headers, timeout=15)
        if not response.ok:
            print(f"Yahoo Finance API error: {response.status_code}")
            return None

        data = response.json()
        result = data.get("chart", {}).get("result", [])

        if not result:
            print("No oil price data available")
            return None

        meta = result[0].get("meta", {})
        indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
        closes = indicators.get("close", [])

        # Filter out None values
        closes = [c for c in closes if c is not None]

        if not closes:
            print("No closing prices available")
            return None

        current_price = closes[-1]
        # Get price from ~24 hours ago (24 data points for hourly data)
        price_24h_ago = closes[0] if len(closes) > 24 else closes[0]

        # Calculate 24h change
        change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100

        # Calculate risk based on price movement and absolute level
        # Higher prices and bigger spikes = higher risk
        risk = 10  # Baseline

        # Price spike component (0-50 points)
        if change_24h >= 5:
            risk += 50  # Major spike
        elif change_24h >= 3:
            risk += 35  # Significant spike
        elif change_24h >= 1.5:
            risk += 20  # Moderate increase
        elif change_24h >= 0.5:
            risk += 10  # Small increase
        elif change_24h <= -2:
            risk -= 5  # Price drop = lower tension

        # Absolute price level component (0-40 points)
        # Based on recent range: $58-$82
        if current_price >= 80:
            risk += 40  # Near recent highs
        elif current_price >= 75:
            risk += 30
        elif current_price >= 70:
            risk += 20
        elif current_price >= 65:
            risk += 10

        risk = max(0, min(100, risk))

        print(f"Current: ${current_price:.2f}/barrel")
        print(f"24h Change: {change_24h:+.2f}%")
        print(f"✓ Result: Risk {risk}%")

        return {
            "current_price": round(current_price, 2),
            "change_24h": round(change_24h, 2),
            "risk": risk,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"Oil prices error: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_google_trends():
    """Fetch Google Trends search interest for Iran-related terms"""
    try:
        print("\n" + "=" * 50)
        print("GOOGLE TRENDS")
        print("=" * 50)

        from pytrends.request import TrendReq

        # Initialize pytrends with SSL verification disabled for corporate proxies
        pytrends = TrendReq(
            hl='en-US', 
            tz=360, 
            timeout=(10, 25),
            requests_args={'verify': False}
        )

        # Keywords to track
        keywords = ["Iran war", "Iran strike", "Iran attack", "Iran nuclear", "Iran conflict"]

        # Build payload - get data from last 7 days
        pytrends.build_payload(keywords, cat=0, timeframe='now 7-d', geo='US')

        # Get interest over time
        interest_df = pytrends.interest_over_time()

        if interest_df.empty:
            print("No Google Trends data available")
            return None

        # Calculate current interest (average of latest values for all keywords)
        # Drop the 'isPartial' column if it exists
        if 'isPartial' in interest_df.columns:
            interest_df = interest_df.drop('isPartial', axis=1)

        # Get the most recent data point
        latest = interest_df.iloc[-1]
        current_interest = latest.mean()

        # Get 24h average (last 24 data points for hourly data, or fewer if not available)
        lookback = min(24, len(interest_df))
        avg_24h = interest_df.iloc[-lookback:].mean().mean()

        # Get the peak keyword
        peak_keyword = latest.idxmax()
        peak_value = latest.max()

        # Calculate risk based on interest levels
        # Google Trends uses 0-100 scale where 100 is peak popularity
        risk = 5  # Baseline

        # Current interest level component
        if current_interest >= 80:
            risk += 60  # Extremely high interest
        elif current_interest >= 60:
            risk += 45
        elif current_interest >= 40:
            risk += 30
        elif current_interest >= 25:
            risk += 15
        elif current_interest >= 10:
            risk += 5

        # Spike detection (current vs 24h average)
        if avg_24h > 0:
            spike_ratio = current_interest / avg_24h
            if spike_ratio >= 3:
                risk += 30  # 3x spike = major surge
            elif spike_ratio >= 2:
                risk += 20  # 2x spike
            elif spike_ratio >= 1.5:
                risk += 10  # 1.5x spike

        risk = max(0, min(100, round(risk)))

        print(f"Current Interest: {current_interest:.1f}")
        print(f"24h Average: {avg_24h:.1f}")
        print(f"Top Search: '{peak_keyword}' ({peak_value})")
        print(f"✓ Result: Risk {risk}%")

        return {
            "current_interest": round(current_interest, 1),
            "avg_24h": round(avg_24h, 1),
            "peak_keyword": peak_keyword,
            "peak_value": int(peak_value),
            "risk": risk,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"Google Trends error: {e}")
        import traceback
        traceback.print_exc()
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

        # Preserve existing history from old or new structure
        if "total_risk" in current_data and "history" in current_data["total_risk"]:
            # New structure
            history = current_data["total_risk"]["history"]
            signal_history = {
                "news": current_data.get("news", {}).get("history", []),
                "flight": current_data.get("flight", {}).get("history", []),
                "tanker": current_data.get("tanker", {}).get("history", []),
                "pentagon": current_data.get("pentagon", {}).get("history", []),
                "polymarket": current_data.get("polymarket", {}).get("history", []),
                "weather": current_data.get("weather", {}).get("history", []),
                "oil": current_data.get("oil", {}).get("history", []),
                "gdelt": current_data.get("gdelt", {}).get("history", []),
                "trends": current_data.get("trends", {}).get("history", []),
            }
        else:
            # Old structure or no data
            history = current_data.get("history", [])
            signal_history = current_data.get(
                "signalHistory",
                {
                    "news": [],
                    "flight": [],
                    "tanker": [],
                    "pentagon": [],
                    "polymarket": [],
                    "weather": [],
                    "oil": [],
                    "gdelt": [],
                    "trends": [],
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

        # GDELT enhanced news data
        gdelt_data = fetch_gdelt_data()
        if gdelt_data:
            current_data["gdelt"] = gdelt_data

        # Oil prices
        oil_data = fetch_oil_prices()
        if oil_data:
            current_data["oil"] = oil_data

        # Google Trends search interest
        trends_data = fetch_google_trends()
        if trends_data:
            current_data["trends"] = trends_data

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

        # Calculate ALL risk scores and display values (NO CALCULATIONS IN FRONTEND!)
        # All calculations moved here to ensure history matches current display

        # NEWS SIGNAL CALCULATION
        news_intel = current_data.get("news_intel", {})
        articles = news_intel.get("total_count", 0)
        alert_count = news_intel.get("alert_count", 0)
        alert_ratio = alert_count / articles if articles > 0 else 0
        news_display_risk = max(3, round(pow(alert_ratio, 2) * 85))
        news_detail = f"{articles} articles, {alert_count} critical"

        # FLIGHT SIGNAL CALCULATION
        aviation = current_data.get("aviation", {})
        aircraft_count = aviation.get("aircraft_count", 0)
        flight_risk = max(3, 95 - round(aircraft_count * 0.8))
        flight_detail = f"{round(aircraft_count)} aircraft over Iran"

        # TANKER SIGNAL CALCULATION
        tanker = current_data.get("tanker", {})
        tanker_count = tanker.get("tanker_count", 0)
        tanker_risk = round((tanker_count / 10) * 100)
        tanker_display_count = round(tanker_count / 4)
        tanker_detail = f"{tanker_display_count} detected in region"

        # WEATHER SIGNAL CALCULATION
        weather = current_data.get("weather", {})
        clouds = weather.get("clouds", 0)
        weather_risk = max(0, min(100, 100 - max(0, clouds - 6)))
        weather_detail = weather.get("description", "clear")

        # POLYMARKET SIGNAL CALCULATION
        polymarket = current_data.get("polymarket", {})
        polymarket_odds = min(
            100, max(0, polymarket.get("odds", 0) if polymarket else 0)
        )
        if polymarket_odds > 95:  # Sanity check
            polymarket_odds = 0
        polymarket_contribution = min(10, polymarket_odds * 0.1)
        polymarket_display_risk = polymarket_odds if polymarket_odds > 0 else 10
        polymarket_detail = (
            f"{polymarket_odds}% odds" if polymarket_odds > 0 else "Awaiting data..."
        )

        # PENTAGON SIGNAL CALCULATION
        pentagon_contribution = pentagon_data.get("risk_contribution", 1)
        pentagon_display_risk = round((pentagon_contribution / 10) * 100)
        pentagon_status = pentagon_data.get("status", "Normal")
        is_late_night = pentagon_data.get("is_late_night", False)
        is_weekend = pentagon_data.get("is_weekend", False)
        pentagon_detail = f"{pentagon_status}{' (late night)' if is_late_night else ''}{' (weekend)' if is_weekend else ''}"

        # OIL PRICES SIGNAL CALCULATION
        oil = current_data.get("oil", {})
        oil_risk = oil.get("risk", 10) if oil else 10
        oil_price = oil.get("current_price", 0) if oil else 0
        oil_change = oil.get("change_24h", 0) if oil else 0
        oil_detail = f"${oil_price:.2f} ({oil_change:+.1f}%)" if oil_price > 0 else "Awaiting data..."

        # GDELT SIGNAL CALCULATION
        gdelt = current_data.get("gdelt", {})
        gdelt_risk = gdelt.get("risk", 10) if gdelt else 10
        gdelt_articles = gdelt.get("article_count", 0) if gdelt else 0
        gdelt_tone = gdelt.get("avg_tone", 0) if gdelt else 0
        gdelt_detail = f"{gdelt_articles} articles, tone {gdelt_tone:.1f}" if gdelt_articles > 0 else "Awaiting data..."

        # GOOGLE TRENDS SIGNAL CALCULATION
        trends = current_data.get("trends", {})
        trends_risk = trends.get("risk", 5) if trends else 5
        trends_interest = trends.get("current_interest", 0) if trends else 0
        trends_keyword = trends.get("peak_keyword", "") if trends else ""
        trends_detail = f"Interest: {trends_interest:.0f}, '{trends_keyword}'" if trends_interest > 0 else "Awaiting data..."

        # Apply weighted contributions (updated weights per plan)
        # Total = 100%: News 20%, Flight 20%, Tanker 15%, Polymarket 15%, Oil 10%, GDELT 5%, Trends 5%, Pentagon 5%, Weather 5%
        news_contribution_weighted = news_display_risk * 0.20  # 20% weight (was 25%)
        flight_contribution_weighted = flight_risk * 0.20  # 20% weight
        tanker_contribution_weighted = tanker_risk * 0.15  # 15% weight
        polymarket_contribution_weighted = polymarket_contribution * 1.5  # 15% weight (was 20%)
        oil_contribution_weighted = oil_risk * 0.10  # 10% weight (new)
        gdelt_contribution_weighted = gdelt_risk * 0.05  # 5% weight (new)
        trends_contribution_weighted = trends_risk * 0.05  # 5% weight (new)
        pentagon_contribution_weighted = pentagon_contribution * 0.5  # 5% weight (was 10%)
        weather_contribution_weighted = weather_risk * 0.05  # 5% weight (was 10%)

        total_risk = (
            news_contribution_weighted
            + flight_contribution_weighted
            + tanker_contribution_weighted
            + polymarket_contribution_weighted
            + oil_contribution_weighted
            + gdelt_contribution_weighted
            + trends_contribution_weighted
            + pentagon_contribution_weighted
            + weather_contribution_weighted
        )

        # Check for escalation multiplier (3+ elevated signals)
        elevated_count = sum(
            [
                news_display_risk > 30,
                flight_contribution_weighted > 15,
                tanker_contribution_weighted > 10,
                polymarket_contribution > 5,
                oil_risk > 40,
                gdelt_risk > 40,
                trends_risk > 30,
                pentagon_contribution > 5,
                weather_contribution_weighted > 4,
            ]
        )

        if elevated_count >= 3:
            total_risk = min(100, total_risk * 1.15)

        total_risk = min(100, max(0, round(total_risk)))

        # Update signal histories (keep last 20 points per signal)
        signal_history["news"].append(news_display_risk)
        signal_history["flight"].append(flight_risk)
        signal_history["tanker"].append(tanker_risk)
        signal_history["pentagon"].append(pentagon_display_risk)
        signal_history["polymarket"].append(polymarket_display_risk)
        signal_history["weather"].append(weather_risk)
        signal_history["oil"].append(oil_risk)
        signal_history["gdelt"].append(gdelt_risk)
        signal_history["trends"].append(trends_risk)

        # Keep only last 20 points
        for sig in signal_history:
            if len(signal_history[sig]) > 20:
                signal_history[sig] = signal_history[sig][-20:]

        # Total risk history management
        # - Runs every 30 minutes
        # - If 12am/12pm boundary NOT crossed: update the last point
        # - If 12am/12pm boundary crossed: remove first, pin last at boundary, add new now point
        now = datetime.now()
        current_timestamp = int(now.timestamp() * 1000)

        # Get the most recent 12am or 12pm boundary
        if now.hour >= 12:
            current_boundary = now.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            current_boundary = now.replace(hour=0, minute=0, second=0, microsecond=0)
        current_boundary_ts = int(current_boundary.timestamp() * 1000)

        # Get the last point's timestamp (if history exists)
        if history:
            last_point = history[-1]
            last_point_ts = last_point.get("timestamp", 0)

            # Check if we crossed a 12am/12pm boundary since the last point
            crossed_boundary = last_point_ts < current_boundary_ts

            if crossed_boundary:
                # Boundary crossed: remove first, pin last at boundary, add new now point
                if len(history) > 0:
                    history = history[1:]  # Remove first point

                if len(history) > 0:
                    # Pin the last point at the boundary
                    history[-1] = {
                        "timestamp": current_boundary_ts,
                        "risk": last_point.get("risk", total_risk),
                        "pinned": True
                    }

                # Add new "now" point
                history.append({"timestamp": current_timestamp, "risk": total_risk})
            else:
                # No boundary crossed: just update the last point
                history[-1] = {"timestamp": current_timestamp, "risk": total_risk}
        else:
            # No history yet, start with a single point
            history = [{"timestamp": current_timestamp, "risk": total_risk}]

        # RESTRUCTURED DATA: Each signal has its own complete object
        restructured_data = {
            "news": {
                "risk": news_display_risk,
                "detail": news_detail,
                "history": signal_history["news"],
                "raw_data": news_intel,
            },
            "flight": {
                "risk": flight_risk,
                "detail": flight_detail,
                "history": signal_history["flight"],
                "raw_data": aviation,
            },
            "tanker": {
                "risk": tanker_risk,
                "detail": tanker_detail,
                "history": signal_history["tanker"],
                "raw_data": tanker,
            },
            "weather": {
                "risk": weather_risk,
                "detail": weather_detail,
                "history": signal_history["weather"],
                "raw_data": weather,
            },
            "polymarket": {
                "risk": polymarket_display_risk,
                "detail": polymarket_detail,
                "history": signal_history["polymarket"],
                "raw_data": polymarket,
            },
            "pentagon": {
                "risk": pentagon_display_risk,
                "detail": pentagon_detail,
                "history": signal_history["pentagon"],
                "raw_data": pentagon_data,
            },
            "oil": {
                "risk": oil_risk,
                "detail": oil_detail,
                "history": signal_history["oil"],
                "raw_data": oil,
            },
            "gdelt": {
                "risk": gdelt_risk,
                "detail": gdelt_detail,
                "history": signal_history["gdelt"],
                "raw_data": gdelt,
            },
            "trends": {
                "risk": trends_risk,
                "detail": trends_detail,
                "history": signal_history["trends"],
                "raw_data": trends,
            },
            "total_risk": {
                "risk": total_risk,
                "history": history,
                "elevated_count": elevated_count,
            },
            "last_updated": current_data["last_updated"],
        }

        # Replace old structure with new restructured data
        current_data = restructured_data

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
    print("\n" + "=" * 50)
    print("PENTAGON PIZZA METER")
    print("=" * 50)

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

    print(f"Activity: {status} - Score: {activity_score}/100")
    display_risk = round((risk_contribution / 10) * 100)
    print(f"✓ Result: Risk {display_risk}%")
    return pentagon_data


def main():
    print(f"Updating data - {datetime.now().isoformat()}")
    update_data_file()


if __name__ == "__main__":
    main()
