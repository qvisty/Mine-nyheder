"""
Personlig Nyhedsside - Backend
Flask server that proxies RSS feeds and serves the frontend.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from flask import Flask, jsonify, send_from_directory
import hashlib
import requests
import re
import threading
import time

import os

# Resolve paths relative to app.py location (needed for PythonAnywhere WSGI)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))

# Danish news RSS feeds with category mappings
RSS_SOURCES = [
    {
        "name": "DR Nyheder",
        "url": "https://www.dr.dk/nyheder/service/feeds/allenyheder",
        "default_category": "generelt",
    },
    {
        "name": "TV2 Nyheder",
        "url": "https://feeds.tv2.dk/nyheder/rss",
        "default_category": "generelt",
    },
    {
        "name": "Politiken",
        "url": "https://politiken.dk/rss/senestenyt.rss",
        "default_category": "generelt",
    },
    {
        "name": "Børsen",
        "url": "https://borsen.dk/rss",
        "default_category": "økonomi",
    },
    {
        "name": "Ingeniøren",
        "url": "https://ing.dk/rss/nyheder",
        "default_category": "teknologi",
    },
]

# Keywords for category detection
CATEGORY_KEYWORDS = {
    "teknologi": [
        "teknologi", "tech", "it", "software", "hardware", "ai", "kunstig intelligens",
        "computer", "digital", "internet", "app", "robot", "cyber", "data", "streaming",
        "smartphone", "chip", "microsoft", "google", "apple", "meta",
    ],
    "politik": [
        "politik", "regering", "folketing", "minister", "valg", "parti", "lov",
        "demokrati", "statsminister", "kommunal", "europa", "eu", "nato",
        "venstre", "socialdemokrat", "konservativ", "liberal",
    ],
    "sport": [
        "sport", "fodbold", "håndbold", "tennis", "cykling", "ol", "vm", "em",
        "kamp", "turnering", "landshold", "superliga", "premier league",
        "atletik", "svømning", "badminton",
    ],
    "økonomi": [
        "økonomi", "finans", "aktie", "børs", "bank", "investering", "marked",
        "inflation", "rente", "vækst", "eksport", "import", "budget", "skat",
        "krone", "dollar", "euro", "virksomhed",
    ],
    "underholdning": [
        "underholdning", "film", "musik", "kunst", "kultur", "koncert", "teater",
        "tv", "serie", "bog", "festival", "celebrity", "reality", "streaming",
    ],
    "videnskab": [
        "videnskab", "forskning", "universitet", "studie", "klima", "miljø",
        "sundhed", "medicin", "rumfart", "biologi", "fysik", "kemi", "natur",
        "vaccine", "dna", "gener",
    ],
}

# In-memory article cache
articles_cache = []
cache_lock = threading.Lock()
last_fetch_time = None


def detect_category(title, description, default_category):
    """Detect article category based on keywords in title and description."""
    text = f"{title} {description}".lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return default_category


def generate_id(title, link):
    """Generate a unique ID for deduplication."""
    raw = f"{title}:{link}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def parse_rss(xml_text, source_name, default_category):
    """Parse RSS XML and return list of article dicts."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return articles

    # Handle both RSS 2.0 and Atom feeds
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }

    # Try RSS 2.0 format
    items = root.findall(".//item")
    if not items:
        # Try Atom format
        items = root.findall(".//atom:entry", namespaces)

    for item in items:
        title = ""
        link = ""
        description = ""
        pub_date = ""
        image_url = ""

        # RSS 2.0
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            title = title_el.text.strip()

        link_el = item.find("link")
        if link_el is not None:
            link = (link_el.text or "").strip()
            if not link:
                link = link_el.get("href", "").strip()

        # Atom link
        if not link:
            atom_link = item.find("atom:link", namespaces)
            if atom_link is not None:
                link = atom_link.get("href", "").strip()

        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            description = desc_el.text.strip()
            # Strip HTML tags
            description = re.sub(r"<[^>]+>", "", description).strip()

        if not description:
            content_el = item.find("content:encoded", namespaces)
            if content_el is not None and content_el.text:
                description = re.sub(r"<[^>]+>", "", content_el.text).strip()

        # Truncate long descriptions
        if len(description) > 300:
            description = description[:297] + "..."

        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            pub_date = pub_el.text.strip()

        if not pub_date:
            pub_el = item.find("atom:updated", namespaces)
            if pub_el is not None and pub_el.text:
                pub_date = pub_el.text.strip()

        # Try to find image
        media_el = item.find("media:content", namespaces)
        if media_el is not None:
            image_url = media_el.get("url", "")

        enclosure_el = item.find("enclosure")
        if not image_url and enclosure_el is not None:
            enc_type = enclosure_el.get("type", "")
            if "image" in enc_type:
                image_url = enclosure_el.get("url", "")

        if not title or not link:
            continue

        # Parse date for sorting
        timestamp = 0
        try:
            dt = parsedate_to_datetime(pub_date)
            timestamp = dt.timestamp()
        except Exception:
            try:
                dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                timestamp = dt.timestamp()
            except Exception:
                timestamp = 0

        category = detect_category(title, description, default_category)
        article_id = generate_id(title, link)

        articles.append({
            "id": article_id,
            "title": title,
            "link": link,
            "description": description,
            "source": source_name,
            "pubDate": pub_date,
            "timestamp": timestamp,
            "category": category,
            "imageUrl": image_url,
        })

    return articles


def get_demo_articles():
    """Return demo articles for when RSS feeds are unavailable."""
    now = datetime.now()
    base_ts = now.timestamp()
    demos = [
        {
            "title": "Ny AI-model kan oversaette dansk med rekordpraecision",
            "description": "Forskere fra DTU har udviklet en ny sprogmodel, der saetter nye standarder for maskinoversaettelse af dansk tekst til over 50 sprog.",
            "source": "Ingenioeren",
            "category": "teknologi",
            "link": "https://ing.dk/artikel/demo-ai-model",
        },
        {
            "title": "Folketinget vedtager ny klimaaftale",
            "description": "Et bredt flertal i Folketinget er blevet enige om en ny klimaaftale, der skal reducere Danmarks CO2-udledning med 70 procent inden 2030.",
            "source": "DR Nyheder",
            "category": "politik",
            "link": "https://www.dr.dk/nyheder/demo-klimaaftale",
        },
        {
            "title": "FC Koebenhavn vinder Superligaen efter dramatisk slutspil",
            "description": "Med en 3-2 sejr over Broendby IF sikrede FC Koebenhavn sig det danske mesterskab i en nervepirrende afgoerende kamp.",
            "source": "TV2 Nyheder",
            "category": "sport",
            "link": "https://nyheder.tv2.dk/demo-superliga",
        },
        {
            "title": "Nationalbanken hoever renten for foerste gang i to aar",
            "description": "Danmarks Nationalbank har besluttet at hoeve styringsrenten med 0,25 procentpoint som reaktion paa stigende inflation i eurozone.",
            "source": "Boersen",
            "category": "økonomi",
            "link": "https://borsen.dk/demo-rente",
        },
        {
            "title": "Dansk film vinder pris ved Cannes Film Festival",
            "description": "Instruktoeeren bag den danske film 'Graenselandet' modtog Guldpalmen ved dette aars Cannes Film Festival.",
            "source": "Politiken",
            "category": "underholdning",
            "link": "https://politiken.dk/demo-cannes",
        },
        {
            "title": "Ny forskning: Havvand kan rense sig selv for mikroplast",
            "description": "Forskere ved Koebenhavns Universitet har opdaget en naturlig proces, hvor bestemte bakterier i havvand kan nedbryde mikroplast.",
            "source": "DR Nyheder",
            "category": "videnskab",
            "link": "https://www.dr.dk/nyheder/demo-mikroplast",
        },
        {
            "title": "Regeringen praesenterer ny digitaliseringsstrategi",
            "description": "Den nye strategi fokuserer paa at goere Danmark til foregangsland inden for digitalisering af den offentlige sektor.",
            "source": "DR Nyheder",
            "category": "teknologi",
            "link": "https://www.dr.dk/nyheder/demo-digitalisering",
        },
        {
            "title": "Haandboldlandsholdet klar til VM-semifinale",
            "description": "De danske haandboldhelte besejrede Frankrig med 28-24 og er nu klar til VM-semifinalen mod Sverige.",
            "source": "TV2 Nyheder",
            "category": "sport",
            "link": "https://nyheder.tv2.dk/demo-haandbold",
        },
        {
            "title": "Danske startups tiltraekker rekordinvesteringer",
            "description": "Danske tech-startups har i foerste kvartal tiltrukket over 5 milliarder kroner i venturekapital, hvilket er ny rekord.",
            "source": "Boersen",
            "category": "økonomi",
            "link": "https://borsen.dk/demo-startups",
        },
        {
            "title": "Ny dansk TV-serie slaar seerrekord paa streaming",
            "description": "Dramaserien 'Broerne' har sat ny rekord som den mest sete danske serie nogensinde paa streaming-tjenesterne.",
            "source": "Politiken",
            "category": "underholdning",
            "link": "https://politiken.dk/demo-streaming",
        },
        {
            "title": "Klimaforskere advarer: Groenlands indlandsis smelter hurtigere end ventet",
            "description": "Nye satellitdata viser, at Groenlands indlandsis mister is tre gange hurtigere end forudset i tidligere modeller.",
            "source": "Ingenioeren",
            "category": "videnskab",
            "link": "https://ing.dk/artikel/demo-groenland",
        },
        {
            "title": "Opposition kraever ministerens afgang efter laekagesag",
            "description": "Flere oppositionspartier kraever ministerens afgang efter afsloering af laekede fortrolige dokumenter til pressen.",
            "source": "Politiken",
            "category": "politik",
            "link": "https://politiken.dk/demo-minister",
        },
    ]

    articles = []
    for i, demo in enumerate(demos):
        ts = base_ts - (i * 1800)  # 30 min apart
        dt = datetime.fromtimestamp(ts)
        article_id = generate_id(demo["title"], demo["link"])
        articles.append({
            "id": article_id,
            "title": demo["title"],
            "link": demo["link"],
            "description": demo["description"],
            "source": demo["source"],
            "pubDate": dt.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "timestamp": ts,
            "category": demo["category"],
            "imageUrl": "",
        })
    return articles


def fetch_all_feeds():
    """Fetch all RSS feeds and update the cache."""
    global articles_cache, last_fetch_time
    all_articles = []
    seen_ids = set()

    for source in RSS_SOURCES:
        try:
            resp = requests.get(source["url"], timeout=10, headers={
                "User-Agent": "MineNyheder/1.0"
            })
            resp.raise_for_status()
            articles = parse_rss(resp.text, source["name"], source["default_category"])
            for article in articles:
                if article["id"] not in seen_ids:
                    seen_ids.add(article["id"])
                    all_articles.append(article)
        except Exception as e:
            print(f"Error fetching {source['name']}: {e}")

    # Sort by timestamp descending
    all_articles.sort(key=lambda a: a["timestamp"], reverse=True)

    # If no articles were fetched, load demo data so the app is usable
    if not all_articles:
        all_articles = get_demo_articles()
        print("No live feeds available - loaded demo articles")

    with cache_lock:
        articles_cache = all_articles
        last_fetch_time = datetime.now()

    print(f"Fetched {len(all_articles)} articles from {len(RSS_SOURCES)} sources")


def background_fetcher():
    """Background thread that refreshes feeds every 15 minutes."""
    while True:
        fetch_all_feeds()
        time.sleep(900)  # 15 minutes


# Routes
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


@app.route("/api/articles")
def get_articles():
    # Lazy-load feeds on first request (needed for PythonAnywhere where
    # background threads are not available in WSGI mode)
    with cache_lock:
        if not articles_cache:
            cache_lock.release()
            fetch_all_feeds()
            cache_lock.acquire()
        return jsonify({
            "articles": articles_cache,
            "lastUpdated": last_fetch_time.isoformat() if last_fetch_time else None,
            "totalCount": len(articles_cache),
        })


@app.route("/api/categories")
def get_categories():
    return jsonify({
        "categories": [
            {"id": "teknologi", "name": "Teknologi", "icon": "💻"},
            {"id": "politik", "name": "Politik", "icon": "🏛️"},
            {"id": "sport", "name": "Sport", "icon": "⚽"},
            {"id": "økonomi", "name": "Økonomi", "icon": "📈"},
            {"id": "underholdning", "name": "Underholdning", "icon": "🎬"},
            {"id": "videnskab", "name": "Videnskab", "icon": "🔬"},
        ]
    })


@app.route("/api/refresh", methods=["POST"])
def refresh_feeds():
    fetch_all_feeds()
    with cache_lock:
        return jsonify({
            "success": True,
            "articleCount": len(articles_cache),
        })


if __name__ == "__main__":
    # Initial fetch
    fetch_all_feeds()
    # Start background fetcher
    fetcher_thread = threading.Thread(target=background_fetcher, daemon=True)
    fetcher_thread.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
