"""
Pentagon Pizza Meter - Fetches busyness data for pizza places near the Pentagon
Runs via GitHub Actions every 30 minutes and updates frontend/data.json

REDESIGNED: Now fetches ALL API data (OpenSky, Weather, Polymarket, News, etc.)
Frontend only reads the JSON - no direct API calls from browser
"""

import json
import os
import re
import time
import ssl
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

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


PIZZA_PLACES = [
    {"name": "Wiseguy Pizza", "url": "https://maps.app.goo.gl/hZ6KsS8HFs3J8Ti28"},
    {"name": "California Pizza Kitchen", "url": "https://maps.app.goo.gl/Rvov6ZvDfoX2MCC98"},
    {"name": "Extreme Pizza", "url": "https://maps.app.goo.gl/1uZxG2mZshD9Pp9A6"},
    {"name": "We, The Pizza", "url": "https://maps.app.goo.gl/5GyfTt45vcy9zAG47"},
    {"name": "District Pizza Palace", "url": "https://maps.app.goo.gl/ZQMPqGXedazt7Beg6"},
]

# Output file configuration
OUTPUT_FILE = "frontend/data.json"


def _scrape_live_busyness_batch(places):
    """
    Scrape live busyness from Google Maps using Selenium headless Chrome.
    Opens each place's Google Maps short URL and reads the "Currently X% busy,
    usually Y% busy" aria-label from the popular-times bar chart.

    Returns dict of {place_name: {"current": int, "usual": int}} for places
    with live data. Places that are closed or have no live reading are omitted.
    """
    import uuid

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
    except ImportError:
        print("  selenium not installed, skipping live scrape")
        return {}

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    chrome_options.add_argument(f"--user-data-dir=/tmp/selenium_{uuid.uuid4()}")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    results = {}
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'},
        )
    except Exception as e:
        print(f"  Chrome driver init failed: {e}")
        return {}

    try:
        for place in places:
            name = place["name"]
            url = place["url"]
            print(f"    {name}...", end=" ", flush=True)
            try:
                driver.get(url)
                time.sleep(8)

                found = False
                all_aria = driver.find_elements(By.XPATH, "//*[@aria-label]")
                for el in all_aria:
                    label = el.get_attribute("aria-label") or ""
                    m = re.search(r"Currently\s+(\d+)%.*usually\s+(\d+)%", label)
                    if m:
                        results[name] = {"current": int(m.group(1)), "usual": int(m.group(2))}
                        print(f"{m.group(1)}% (usually {m.group(2)}%)")
                        found = True
                        break
                    m = re.search(r"כרגע תפוסה של %(\d+).*תפוסה של %(\d+)", label)
                    if m:
                        results[name] = {"current": int(m.group(1)), "usual": int(m.group(2))}
                        print(f"{m.group(1)}% (usually {m.group(2)}%)")
                        found = True
                        break
                if not found:
                    print("no live data")
            except Exception as e:
                print(f"error ({e})")
    finally:
        driver.quit()

    return results


def _pentagon_eastern_time():
    """Return current time in US Eastern (Pentagon local), accounting for DST."""
    from datetime import timezone

    utc_now = datetime.now(timezone.utc)
    # US Eastern: UTC-5, EDT: UTC-4. Approximate DST (Mar second Sun – Nov first Sun).
    month = utc_now.month
    is_dst = 3 < month < 11 or (
        month == 3 and utc_now.day >= 8
    ) or (
        month == 11 and utc_now.day < 1
    )
    offset = timedelta(hours=-4 if is_dst else -5)
    return utc_now + offset


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
        keyword_risk = pow(alert_ratio, 2) * 85

        # Zero-shot classification for military escalation
        avg_escalation = 0.0
        escalation_available = False
        ESCALATION_LABELS = [
            "military escalation",
            "diplomatic negotiation",
            "routine operations",
            "economic sanctions",
            "unrelated",
        ]
        try:
            from transformers import pipeline as hf_pipeline
            titles = [a["title"] for a in unique_articles if a["title"]]
            if titles:
                print("  Running zero-shot escalation classification...")
                classifier = hf_pipeline(
                    "zero-shot-classification",
                    model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                    device=-1,
                )
                results = classifier(titles, candidate_labels=ESCALATION_LABELS, batch_size=8)
                esc_scores = []
                for i, result in enumerate(results):
                    score_map = {l: s for l, s in zip(result["labels"], result["scores"])}
                    esc = score_map.get("military escalation", 0.0)
                    esc_scores.append(esc)
                    unique_articles[i]["escalation"] = round(esc, 3)
                avg_escalation = sum(esc_scores) / len(esc_scores)
                escalation_available = True
                print(f"  Avg escalation: {avg_escalation:.3f} ({sum(1 for s in esc_scores if s > 0.5)}/{len(esc_scores)} above 0.5)")
        except Exception as e:
            print(f"  Zero-shot classification unavailable: {e}")

        if escalation_available:
            escalation_risk = avg_escalation * 100
            risk = max(3, round(keyword_risk * 0.4 + escalation_risk * 0.6))
        else:
            risk = max(3, round(keyword_risk))

        print(f"✓ Result: Risk {risk}%")

        return {
            "articles": unique_articles,
            "total_count": len(unique_articles),
            "alert_count": alert_count,
            "avg_escalation": round(avg_escalation, 3),
            "escalation_available": escalation_available,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"News Intel error: {e}")
        import traceback

        traceback.print_exc()
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


# =============================================
# MILITARY BUILDUP SCORING CONSTANTS
# =============================================

SHIP_POINTS = {
    "CVN": 25, "LHA": 12, "LHD": 12, "CG": 6, "DDG": 4,
    "LPD": 3, "LCS": 2, "SSN": 8, "SSGN": 8,
    "T-AOE": 1, "T-AO": 1, "T-AKE": 1, "WAGB": 0,
}

HIGH_RELEVANCE_REGIONS = [
    "arabian sea", "north arabian sea",
    "persian gulf", "gulf of oman",
    "red sea", "gulf of aden", "strait of hormuz",
]

CONDITIONAL_MEDIUM_REGIONS = ["mediterranean", "atlantic", "caribbean", "adriatic"]

TRANSIT_KEYWORDS_RE = [
    r"ordered to.*(?:middle east|central command|centcom|5th fleet)",
    r"heading to.*(?:middle east|central command|centcom)",
    r"en route to.*(?:middle east|central command)",
    r"deployed to.*(?:central command|5th fleet|centcom)",
    r"now been ordered to the middle east",
    r"sailing to.*(?:middle east|central command)",
]

STATION_KEYWORDS = ["rota", "fdnf", "forward deployed"]

HULL_PATTERN = (
    r"(?:USS|USNS|USCGC)\s+([\w\s.]+?)\s*"
    r"\(((?:CVN|DDG|CG|LHA|LHD|LPD|LCS|SSN|SSGN|T-AOE|T-AO|T-AKE|WAGB)-?\d+)\)"
)

BUILDUP_BASELINE_POINTS = 35
BUILDUP_MAX_POINTS = 120

AIR_PLATFORM_POINTS = {
    "b-2": ("Stealth Bomber", 15),
    "b-52": ("Strategic Bomber", 12),
    "b-1": ("Bomber", 12),
    "f-22": ("Air Superiority Fighter", 10),
    "f-35": ("5th Gen Fighter", 8),
    "f-15e": ("Strike Eagle", 6),
    "awacs": ("Early Warning", 6),
    "e-3": ("Early Warning", 6),
    "a-10": ("Ground Attack", 4),
    "rc-135": ("Reconnaissance", 4),
    "global hawk": ("ISR UAV", 4),
    "rq-4": ("ISR UAV", 4),
    "p-8": ("Maritime Patrol", 4),
    "typhoon": ("Allied Fighter", 5),
    "rafale": ("Allied Fighter", 5),
}

AIR_BASE_POINTS = {
    "diego garcia": 5,
    "al udeid": 4, "qatar": 4,
    "al dhafra": 4, "uae": 3,
    "lakenheath": 2, "fairford": 2,
    "akrotiri": 3, "cyprus": 3,
    "souda bay": 3, "crete": 3,
}

AIR_CAPABILITY_CATEGORIES = {
    "strategic_strike": ["b-2", "b-52", "b-1"],
    "air_superiority": ["f-22"],
    "multirole_strike": ["f-35", "f-15e"],
    "ground_attack": ["a-10"],
    "c2_isr": ["awacs", "e-3", "rc-135", "global hawk", "rq-4", "p-8"],
    "allied": ["typhoon", "rafale"],
}

CARRIER_SQUADRON_PATTERN = r"(?:VFA|VMFA)[-\s]*\d+"


def _get_hull_type(hull):
    """Extract the ship type prefix from a hull designation like DDG-119 or T-AKE-7."""
    if hull.startswith("T-"):
        parts = hull.split("-")
        return parts[0] + "-" + re.sub(r"\d+", "", parts[1])
    return hull.split("-")[0]


def score_naval_force(content_html):
    """
    Score naval force posture from USNI Fleet Tracker article HTML.
    Pure function: deterministic on the same input, no network calls.
    Returns dict with total_weighted_points, force_risk, type_counts, etc.
    """
    import re as _re

    soup = BeautifulSoup(content_html, "html.parser")
    h2s = soup.find_all("h2")
    all_ships = {}
    total_points = 0.0

    for h2 in h2s:
        region_name = h2.get_text(strip=True)
        region_lower = region_name.lower()
        if any(s in region_lower for s in ["ships underway", "search", "related"]):
            continue

        section_text = ""
        for sibling in h2.find_next_siblings():
            if sibling.name == "h2":
                break
            section_text += sibling.get_text(" ", strip=True) + " "
        section_lower = section_text.lower()

        relevance = "low"
        multiplier = 0.0
        for hr in HIGH_RELEVANCE_REGIONS:
            if hr in region_lower:
                relevance = "high"
                multiplier = 1.0
                break
        if relevance == "low":
            for cmr in CONDITIONAL_MEDIUM_REGIONS:
                if cmr in region_lower:
                    for tkw in TRANSIT_KEYWORDS_RE:
                        if _re.search(tkw, section_lower):
                            relevance = "medium-transit"
                            multiplier = 0.5
                            break
                    if relevance == "low":
                        for skw in STATION_KEYWORDS:
                            if skw in section_lower:
                                relevance = "medium-station"
                                multiplier = 0.4
                                break
                    break

        ships = _re.findall(HULL_PATTERN, section_text)
        seen = set()
        for name, hull in ships:
            if hull in seen:
                continue
            seen.add(hull)
            ht = _get_hull_type(hull)
            pts = SHIP_POINTS.get(ht, 1)
            weighted = round(pts * multiplier, 1)
            if hull in all_ships:
                if weighted <= all_ships[hull]["weighted"]:
                    continue
                total_points -= all_ships[hull]["weighted"]
            all_ships[hull] = {
                "name": name.strip(),
                "hull": hull,
                "type": ht,
                "base_points": pts,
                "weighted": weighted,
            }
            total_points += weighted

    total_points = round(total_points, 1)
    force_risk = min(
        100,
        max(0, round(
            ((total_points - BUILDUP_BASELINE_POINTS) /
             (BUILDUP_MAX_POINTS - BUILDUP_BASELINE_POINTS)) * 100
        )),
    )

    counted = [s for s in all_ships.values() if s["weighted"] > 0]
    type_counts = {}
    for s in counted:
        type_counts[s["type"]] = type_counts.get(s["type"], 0) + 1

    return {
        "total_weighted_points": total_points,
        "force_risk": force_risk,
        "total_ships_parsed": len(all_ships),
        "counted_ships": len(counted),
        "carriers_in_centcom": type_counts.get("CVN", 0),
        "destroyers_in_centcom": type_counts.get("DDG", 0),
        "type_counts": type_counts,
    }


def _score_carrier_air(content_html, h2_regions_lower_relevant):
    """
    Score carrier air wing composition from USNI article HTML.
    Only counts squadrons within CENTCOM-relevant h2 sections.
    Returns dict with risk score and squadron counts.
    """
    soup = BeautifulSoup(content_html, "html.parser")
    total_air_pts = 0.0
    total_fighter_sq = 0
    total_ea_sq = 0
    total_ew_sq = 0

    for h2 in soup.find_all("h2"):
        region_lower = h2.get_text(strip=True).lower()
        multiplier = h2_regions_lower_relevant.get(region_lower, 0.0)
        if multiplier == 0.0:
            continue

        section_text = ""
        for sibling in h2.find_next_siblings():
            if sibling.name == "h2":
                break
            section_text += sibling.get_text(" ", strip=True) + " "

        vfa_squadrons = set(re.findall(r"VFA[-\s]*\d+", section_text))
        vmfa_squadrons = set(re.findall(r"VMFA[-\s]*\d+", section_text))
        vaq_squadrons = set(re.findall(r"VAQ[-\s]*\d+", section_text))
        vaw_squadrons = set(re.findall(r"VAW[-\s]*\d+", section_text))

        total_fighter_sq += len(vfa_squadrons) + len(vmfa_squadrons)
        total_ea_sq += len(vaq_squadrons)
        total_ew_sq += len(vaw_squadrons)

        pts = (
            len(vfa_squadrons) * 6
            + len(vmfa_squadrons) * 8
            + len(vaq_squadrons) * 4
            + len(vaw_squadrons) * 3
        )
        total_air_pts += pts * multiplier

    carrier_air_risk = min(100, round((total_air_pts / 50) * 100))
    return {
        "risk": carrier_air_risk,
        "fighter_squadrons": total_fighter_sq,
        "ea_squadrons": total_ea_sq,
        "ew_squadrons": total_ew_sq,
        "total_squadrons": total_fighter_sq + total_ea_sq + total_ew_sq,
    }


def fetch_military_buildup(previous_data=None):
    """
    Fetch military buildup data from USNI Fleet Tracker RSS and Google News RSS.
    Returns combined risk from naval force posture, air presence, and deployment news.
    """
    try:
        print("\n" + "=" * 50)
        print("MILITARY BUILDUP")
        print("=" * 50)

        naval_result = None
        carrier_air_risk = 0
        carrier_air_squadrons = 0
        article_title = None
        article_date = None
        content_html = None

        # --- Source 1: USNI Fleet Tracker RSS ---
        print("  Fetching USNI Fleet Tracker RSS...")
        try:
            usni_resp = make_request(
                "https://news.usni.org/feed", timeout=25
            )
            if usni_resp and usni_resp.ok:
                root = ET.fromstring(usni_resp.text)
                ns_content = "{http://purl.org/rss/1.0/modules/content/}encoded"
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    if title_elem is None or title_elem.text is None:
                        continue
                    t = title_elem.text
                    if "fleet" in t.lower() and "tracker" in t.lower():
                        content_elem = item.find(ns_content)
                        if content_elem is not None and content_elem.text:
                            content_html = content_elem.text
                            article_title = t
                            pub_elem = item.find("pubDate")
                            article_date = pub_elem.text if pub_elem is not None else None
                        break

                if content_html:
                    naval_result = score_naval_force(content_html)
                    print(f"    Article: {article_title}")
                    print(f"    Ships: {naval_result['total_ships_parsed']} parsed, {naval_result['counted_ships']} in CENTCOM")
                    print(f"    Points: {naval_result['total_weighted_points']}, Force Risk: {naval_result['force_risk']}%")

                    # Build region multiplier map for carrier air scoring
                    region_mults = {}
                    soup_tmp = BeautifulSoup(content_html, "html.parser")
                    for h2 in soup_tmp.find_all("h2"):
                        rn = h2.get_text(strip=True).lower()
                        if any(s in rn for s in ["ships underway", "search", "related"]):
                            continue
                        sec = ""
                        for sib in h2.find_next_siblings():
                            if sib.name == "h2":
                                break
                            sec += sib.get_text(" ", strip=True) + " "
                        sl = sec.lower()
                        m = 0.0
                        for hr in HIGH_RELEVANCE_REGIONS:
                            if hr in rn:
                                m = 1.0
                                break
                        if m == 0.0:
                            for cmr in CONDITIONAL_MEDIUM_REGIONS:
                                if cmr in rn:
                                    for tkw in TRANSIT_KEYWORDS_RE:
                                        if re.search(tkw, sl):
                                            m = 0.5
                                            break
                                    if m == 0.0:
                                        for skw in STATION_KEYWORDS:
                                            if skw in sl:
                                                m = 0.4
                                                break
                                    break
                        if m > 0:
                            region_mults[rn] = m

                    carrier_air_result = _score_carrier_air(content_html, region_mults)
                    carrier_air_risk = carrier_air_result["risk"]
                    carrier_air_squadrons = carrier_air_result["total_squadrons"]
                    print(f"    Carrier Air Risk: {carrier_air_risk}% ({carrier_air_result['fighter_squadrons']} fighter, {carrier_air_result['ea_squadrons']} EA, {carrier_air_result['ew_squadrons']} EW squadrons)")
                else:
                    print("    No fleet tracker article found in RSS")
            else:
                print(f"    USNI RSS fetch failed: {usni_resp.status_code if usni_resp else 'no response'}")
        except Exception as e:
            print(f"    USNI RSS error: {e}")

        # Use previous data as fallback for naval scoring
        if naval_result is None and previous_data:
            naval_result = previous_data.get("force_posture")
            carrier_air_risk = previous_data.get("carrier_air_risk", 0)
            carrier_air_squadrons = previous_data.get("carrier_air_squadrons", 0)
            print("    Using cached naval data from previous run")

        naval_force_risk = naval_result["force_risk"] if naval_result else 5

        # --- Source 2: Google News RSS (air assets) ---
        print("  Fetching air asset news...")
        land_air_risk = 5
        air_data = {"platforms": {}, "bases": {}, "categories_present": 0}
        try:
            air_query = (
                "%22F-35%22+OR+%22F-22%22+OR+%22B-52%22+OR+%22B-1%22+OR+%22B-2%22"
                "+OR+%22AWACS%22+OR+%22E-3%22+OR+%22F-15E%22+OR+%22A-10%22"
                "+%22Middle+East%22+OR+Iran+OR+Qatar+OR+UAE"
                "+OR+%22Diego+Garcia%22+OR+%22Al+Udeid%22+OR+%22Al+Dhafra%22"
                "+deploy+OR+arrive+OR+send"
            )
            air_url = f"https://news.google.com/rss/search?q={air_query}&hl=en-US&gl=US&ceid=US:en"
            air_resp = make_request(air_url, timeout=15)
            if air_resp and air_resp.ok:
                air_root = ET.fromstring(air_resp.text)
                detected_platforms = {}
                detected_bases = {}

                for ni in air_root.findall(".//item")[:50]:
                    te = ni.find("title")
                    if te is None or te.text is None:
                        continue
                    tl = te.text.lower()
                    for pkey, (pname, ppts) in AIR_PLATFORM_POINTS.items():
                        if pkey in tl and pkey not in detected_platforms:
                            detected_platforms[pkey] = {"name": pname, "points": ppts}
                    for bkey, bpts in AIR_BASE_POINTS.items():
                        if bkey in tl:
                            detected_bases[bkey] = detected_bases.get(bkey, 0) + 1

                categories_present = 0
                categories_active = []
                cat_labels = {
                    "strategic_strike": "bombers",
                    "air_superiority": "air superiority",
                    "multirole_strike": "strike fighters",
                    "ground_attack": "ground attack",
                    "c2_isr": "C2/ISR",
                    "allied": "allied",
                }
                for cat_name, cat_platforms in AIR_CAPABILITY_CATEGORIES.items():
                    if any(p in detected_platforms for p in cat_platforms):
                        categories_present += 1
                        categories_active.append(cat_labels.get(cat_name, cat_name))

                if categories_present >= 5:
                    land_air_risk = 90
                elif categories_present >= 4:
                    land_air_risk = 70
                elif categories_present >= 3:
                    land_air_risk = 50
                elif categories_present >= 2:
                    land_air_risk = 25
                elif categories_present >= 1:
                    land_air_risk = 15
                else:
                    land_air_risk = 5

                base_bonus = min(15, sum(min(v, 3) for v in detected_bases.values()))
                land_air_risk = min(100, land_air_risk + base_bonus)

                air_data = {
                    "platforms": {k: v["name"] for k, v in detected_platforms.items()},
                    "bases": detected_bases,
                    "categories_present": categories_present,
                    "categories_active": categories_active,
                }
                print(f"    Platforms: {len(detected_platforms)}, Categories: {categories_present}/6, Land Air Risk: {land_air_risk}%")
            else:
                print(f"    Air news fetch failed")
        except Exception as e:
            print(f"    Air news error: {e}")

        air_presence_risk = round(carrier_air_risk * 0.4 + land_air_risk * 0.6)

        # --- Source 3: Google News RSS (deployment news intensity) ---
        print("  Fetching deployment news...")
        deployment_news_risk = 0
        news_data = {"article_count": 0, "escalation_matches": 0, "deployment_matches": 0, "sample_headlines": []}
        try:
            news_query = (
                "%22US+Navy%22+OR+%22military+buildup%22+OR+%22strike+group%22"
                "+OR+%22carrier%22+Iran+OR+%22Middle+East%22+OR+CENTCOM"
            )
            news_url = f"https://news.google.com/rss/search?q={news_query}&hl=en-US&gl=US&ceid=US:en"
            news_resp = make_request(news_url, timeout=15)
            if news_resp and news_resp.ok:
                news_root = ET.fromstring(news_resp.text)
                escalation_kw = ["buildup", "build-up", "strike option", "deadline", "warns", "critical level", "armada", "tensions"]
                deployment_kw = ["deploy", "carrier", "arrives", "heading", "sailing", "ordered to", "strike group"]
                article_count = 0
                esc_count = 0
                dep_count = 0
                headlines = []

                for ni in news_root.findall(".//item")[:50]:
                    te = ni.find("title")
                    if te is None or te.text is None:
                        continue
                    title_text = te.text
                    tl = title_text.lower()
                    article_count += 1
                    if len(headlines) < 5:
                        headlines.append(title_text)
                    for kw in escalation_kw:
                        if kw in tl:
                            esc_count += 1
                            break
                    for kw in deployment_kw:
                        if kw in tl:
                            dep_count += 1
                            break

                deployment_news_risk = min(40, article_count * 3)
                deployment_news_risk += min(36, esc_count * 6)
                deployment_news_risk += min(24, dep_count * 3)
                deployment_news_risk = min(100, deployment_news_risk)

                news_data = {
                    "article_count": article_count,
                    "escalation_matches": esc_count,
                    "deployment_matches": dep_count,
                    "sample_headlines": headlines,
                }
                print(f"    Articles: {article_count}, Escalation: {esc_count}, Deployment: {dep_count}, News Risk: {deployment_news_risk}%")
            else:
                print(f"    Deployment news fetch failed")
        except Exception as e:
            print(f"    Deployment news error: {e}")

        # --- Combined buildup risk ---
        buildup_risk = round(
            naval_force_risk * 0.55
            + air_presence_risk * 0.30
            + deployment_news_risk * 0.15
        )
        buildup_risk = min(100, max(0, buildup_risk))

        carriers = naval_result.get("carriers_in_centcom", 0) if naval_result else 0
        destroyers = naval_result.get("destroyers_in_centcom", 0) if naval_result else 0
        points = naval_result.get("total_weighted_points", 0) if naval_result else 0
        cats = air_data.get("categories_present", 0)
        cat_names = air_data.get("categories_active", [])

        ship_parts = []
        if carriers:
            ship_parts.append(f"{carriers} carrier{'s' if carriers > 1 else ''}")
        if destroyers:
            ship_parts.append(f"{destroyers} destroyer{'s' if destroyers > 1 else ''}")
        ships_text = ", ".join(ship_parts) if ship_parts else "No major combatants"

        land_platforms = len(air_data.get("platforms", {}))
        air_parts = []
        if carrier_air_squadrons:
            air_parts.append(f"{carrier_air_squadrons} carrier sq")
        if land_platforms:
            air_parts.append(f"{land_platforms} land types")
        if cat_names:
            air_parts.append(f"{cats}/6 categories ({', '.join(cat_names)})")

        if air_parts:
            air_text = "Air: " + ", ".join(air_parts)
        else:
            air_text = "No air assets detected"

        detail = f"{ships_text} near CENTCOM ({points:.0f} pts) | {air_text}"

        print(f"  Naval: {naval_force_risk}% x 0.55 = {naval_force_risk * 0.55:.1f}")
        print(f"  Air:   {air_presence_risk}% x 0.30 = {air_presence_risk * 0.30:.1f}")
        print(f"  News:  {deployment_news_risk}% x 0.15 = {deployment_news_risk * 0.15:.1f}")
        print(f"  Combined Buildup Risk: {buildup_risk}%")

        result = {
            "risk": buildup_risk,
            "detail": detail,
            "force_posture": naval_result,
            "carrier_air_risk": carrier_air_risk,
            "carrier_air_squadrons": carrier_air_squadrons,
            "air_presence": air_data,
            "deployment_news": news_data,
            "source_article": article_title,
            "source_date": article_date,
            "timestamp": datetime.now().isoformat(),
        }

        print(f"✓ Result: Risk {buildup_risk}%")
        return result

    except Exception as e:
        print(f"Military buildup error: {e}")
        import traceback
        traceback.print_exc()
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

        if closes:
            current_price = closes[-1]
            price_24h_ago = closes[0] if len(closes) > 24 else closes[0]
        elif meta.get("regularMarketPrice"):
            current_price = meta["regularMarketPrice"]
            price_24h_ago = meta.get("chartPreviousClose", current_price)
            print(f"  Using meta prices (market closed): ${current_price:.2f}")
        else:
            print("No oil price data available")
            return None

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
                "trends": current_data.get("trends", {}).get("history", []),
                "buildup": current_data.get("buildup", {}).get("history", []),
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
                    "trends": [],
                    "buildup": [],
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

        # Military Buildup (USNI Fleet Tracker + Google News)
        previous_buildup = current_data.get("buildup", {}).get("raw_data")
        buildup_data = fetch_military_buildup(previous_data=previous_buildup)
        if buildup_data:
            current_data["buildup_raw"] = buildup_data

        # Add main timestamp
        current_data["last_updated"] = datetime.now().isoformat()

        # Calculate ALL risk scores and display values (NO CALCULATIONS IN FRONTEND!)
        # All calculations moved here to ensure history matches current display

        # NEWS SIGNAL CALCULATION
        news_intel = current_data.get("news_intel", {})
        articles = news_intel.get("total_count", 0)
        alert_count = news_intel.get("alert_count", 0)
        alert_ratio = alert_count / articles if articles > 0 else 0
        keyword_risk = pow(alert_ratio, 2) * 85
        escalation_available = news_intel.get("escalation_available", False)
        avg_escalation = news_intel.get("avg_escalation", 0.0)
        if escalation_available:
            escalation_risk = avg_escalation * 100
            news_display_risk = max(3, round(keyword_risk * 0.4 + escalation_risk * 0.6))
            news_detail = f"{articles} articles, {alert_count} critical, escalation: {avg_escalation:.2f}"
        else:
            news_display_risk = max(3, round(keyword_risk))
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
        pentagon_detail = pentagon_data.get("detail_text", "Awaiting data...")

        # OIL PRICES SIGNAL CALCULATION
        oil = current_data.get("oil", {})
        oil_risk = oil.get("risk", 10) if oil else 10
        oil_price = oil.get("current_price", 0) if oil else 0
        oil_change = oil.get("change_24h", 0) if oil else 0
        oil_detail = f"${oil_price:.2f} ({oil_change:+.1f}%)" if oil_price > 0 else "Awaiting data..."

        # GOOGLE TRENDS SIGNAL CALCULATION
        trends = current_data.get("trends", {})
        trends_risk = trends.get("risk", 5) if trends else 5
        trends_interest = trends.get("current_interest", 0) if trends else 0
        trends_keyword = trends.get("peak_keyword", "") if trends else ""
        trends_detail = f"Interest: {trends_interest:.0f}, '{trends_keyword}'" if trends_interest > 0 else "Awaiting data..."

        # BUILDUP SIGNAL CALCULATION
        buildup_raw = current_data.get("buildup_raw", {})
        buildup_risk = buildup_raw.get("risk", 5) if buildup_raw else 5
        buildup_detail = buildup_raw.get("detail", "Awaiting data...") if buildup_raw else "Awaiting data..."

        # Apply weighted contributions
        # Total = 100%: Buildup 15%, News 20%, Flight 20%, Tanker 13%, Polymarket 14%, Oil 10%, Trends 4%, Pentagon 4%
        buildup_contribution_weighted = buildup_risk * 0.15  # 15% weight
        news_contribution_weighted = news_display_risk * 0.20  # 20% weight
        flight_contribution_weighted = flight_risk * 0.20  # 20% weight
        tanker_contribution_weighted = tanker_risk * 0.13  # 13% weight
        polymarket_contribution_weighted = polymarket_contribution * 1.4  # 14% weight
        oil_contribution_weighted = oil_risk * 0.10  # 10% weight
        trends_contribution_weighted = trends_risk * 0.04  # 4% weight
        pentagon_contribution_weighted = pentagon_contribution * 0.4  # 4% weight

        total_risk = (
            buildup_contribution_weighted
            + news_contribution_weighted
            + flight_contribution_weighted
            + tanker_contribution_weighted
            + polymarket_contribution_weighted
            + oil_contribution_weighted
            + trends_contribution_weighted
            + pentagon_contribution_weighted
        )

        # Check for escalation multiplier (3+ elevated signals)
        elevated_count = sum(
            [
                buildup_risk > 40,
                news_display_risk > 30,
                flight_contribution_weighted > 15,
                tanker_contribution_weighted > 10,
                polymarket_contribution > 5,
                oil_risk > 40,
                trends_risk > 30,
                pentagon_contribution > 5,
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
        signal_history["trends"].append(trends_risk)
        signal_history["buildup"].append(buildup_risk)

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
            "trends": {
                "risk": trends_risk,
                "detail": trends_detail,
                "history": signal_history["trends"],
                "raw_data": trends,
            },
            "buildup": {
                "risk": buildup_risk,
                "detail": buildup_detail,
                "history": signal_history["buildup"],
                "raw_data": buildup_raw,
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
    """Fetch live pizza-place busyness near the Pentagon via Selenium scraping."""
    print("\n" + "=" * 50)
    print("PENTAGON PIZZA METER")
    print("=" * 50)

    et = _pentagon_eastern_time()
    hour = et.hour
    is_late_night = hour >= 22 or hour < 6
    is_weekend = et.weekday() >= 5

    print(f"  Scraping {len(PIZZA_PLACES)} pizza places via Google Maps...")
    scraped = _scrape_live_busyness_batch(PIZZA_PLACES)

    live_scores = {}
    for name, data in scraped.items():
        live_scores[name] = data["current"]
        usual = data["usual"]
        print(f"    {name}: {data['current']}% busy (usually {usual}%)")

    is_live = len(live_scores) > 0

    if is_live:
        avg_busyness = sum(live_scores.values()) / len(live_scores)

        if is_late_night and avg_busyness > 40:
            score = min(100, round(avg_busyness * 1.4))
        elif is_weekend and avg_busyness > 50:
            score = min(100, round(avg_busyness * 1.2))
        else:
            score = round(avg_busyness)

        parts = [f"{n} {v}%" for n, v in live_scores.items()]
        detail_text = ", ".join(parts) + " (live)"
        source = "live"
    else:
        score = 0
        detail_text = "No data available"
        source = "none"

    if score >= 70:
        risk_contribution = 10
        status = "High Activity"
    elif score >= 50:
        risk_contribution = 7
        status = "Elevated"
    elif score >= 30:
        risk_contribution = 3
        status = "Normal"
    else:
        risk_contribution = 0
        status = "No Data" if source == "none" else "Low Activity"

    pentagon_data = {
        "score": score,
        "risk_contribution": risk_contribution,
        "status": status,
        "detail_text": detail_text,
        "source": source,
        "live_scores": live_scores if is_live else None,
        "hour_et": hour,
        "timestamp": datetime.now().isoformat(),
        "is_late_night": is_late_night,
        "is_weekend": is_weekend,
    }

    print(f"  Source: {source} | Score: {score}/100 | {status}")
    display_risk = round((risk_contribution / 10) * 100)
    print(f"✓ Result: Risk {display_risk}%")
    return pentagon_data


def main():
    print(f"Updating data - {datetime.now().isoformat()}")
    update_data_file()


if __name__ == "__main__":
    main()
