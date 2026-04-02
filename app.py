"""
Personlig Nyhedsside - Backend
Flask server that proxies RSS feeds, stores articles in SQLite,
and serves the frontend.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from flask import Flask, jsonify, request, send_from_directory
import hashlib
import os
import re
import requests
import sqlite3

# Resolve paths relative to app.py location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "nyheder.db")

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


# --- Database ---

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            description TEXT,
            source TEXT,
            pub_date TEXT,
            timestamp REAL,
            category TEXT,
            image_url TEXT,
            saved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_articles_timestamp ON articles(timestamp);
        CREATE INDEX IF NOT EXISTS idx_articles_saved ON articles(saved);
        CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
    """)
    conn.commit()
    conn.close()


def upsert_articles(articles):
    """Insert or update articles in the database."""
    conn = get_db()
    for a in articles:
        conn.execute("""
            INSERT INTO articles (id, title, link, description, source, pub_date, timestamp, category, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                source=excluded.source,
                pub_date=excluded.pub_date,
                timestamp=excluded.timestamp,
                category=excluded.category,
                image_url=excluded.image_url
        """, (a["id"], a["title"], a["link"], a["description"], a["source"],
              a["pubDate"], a["timestamp"], a["category"], a["imageUrl"]))
    conn.commit()
    conn.close()


def cleanup_old_articles():
    """Delete articles older than 90 days that are not saved."""
    cutoff = datetime.now().timestamp() - (90 * 24 * 3600)
    conn = get_db()
    conn.execute("DELETE FROM articles WHERE timestamp < ? AND timestamp > 0 AND saved = 0", (cutoff,))
    conn.commit()
    conn.close()


def get_all_articles():
    """Get all articles from the database, sorted by timestamp descending."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_fetch_time():
    """Get the most recent article timestamp as a proxy for last fetch."""
    conn = get_db()
    row = conn.execute("SELECT MAX(created_at) as last FROM articles").fetchone()
    conn.close()
    if row and row["last"]:
        return row["last"]
    return None


# --- RSS Parsing ---

def detect_category(title, description, default_category):
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
    raw = f"{title}:{link}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def parse_rss(xml_text, source_name, default_category):
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return articles

    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//atom:entry", namespaces)

    for item in items:
        title = ""
        link = ""
        description = ""
        pub_date = ""
        image_url = ""

        title_el = item.find("title")
        if title_el is not None and title_el.text:
            title = title_el.text.strip()

        link_el = item.find("link")
        if link_el is not None:
            link = (link_el.text or "").strip()
            if not link:
                link = link_el.get("href", "").strip()

        if not link:
            atom_link = item.find("atom:link", namespaces)
            if atom_link is not None:
                link = atom_link.get("href", "").strip()

        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            description = desc_el.text.strip()
            description = re.sub(r"<[^>]+>", "", description).strip()

        if not description:
            content_el = item.find("content:encoded", namespaces)
            if content_el is not None and content_el.text:
                description = re.sub(r"<[^>]+>", "", content_el.text).strip()

        if len(description) > 300:
            description = description[:297] + "..."

        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            pub_date = pub_el.text.strip()

        if not pub_date:
            pub_el = item.find("atom:updated", namespaces)
            if pub_el is not None and pub_el.text:
                pub_date = pub_el.text.strip()

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
    now = datetime.now()
    base_ts = now.timestamp()
    demos = [
        {"title": "Ny AI-model kan oversaette dansk med rekordpraecision",
         "description": "Forskere fra DTU har udviklet en ny sprogmodel, der saetter nye standarder for maskinoversaettelse af dansk tekst til over 50 sprog.",
         "source": "Ingenioeren", "category": "teknologi", "link": "https://ing.dk/artikel/demo-ai-model"},
        {"title": "Folketinget vedtager ny klimaaftale",
         "description": "Et bredt flertal i Folketinget er blevet enige om en ny klimaaftale, der skal reducere Danmarks CO2-udledning med 70 procent inden 2030.",
         "source": "DR Nyheder", "category": "politik", "link": "https://www.dr.dk/nyheder/demo-klimaaftale"},
        {"title": "FC Koebenhavn vinder Superligaen efter dramatisk slutspil",
         "description": "Med en 3-2 sejr over Broendby IF sikrede FC Koebenhavn sig det danske mesterskab i en nervepirrende afgoerende kamp.",
         "source": "TV2 Nyheder", "category": "sport", "link": "https://nyheder.tv2.dk/demo-superliga"},
        {"title": "Nationalbanken hoever renten for foerste gang i to aar",
         "description": "Danmarks Nationalbank har besluttet at hoeve styringsrenten med 0,25 procentpoint som reaktion paa stigende inflation i eurozone.",
         "source": "Boersen", "category": "økonomi", "link": "https://borsen.dk/demo-rente"},
        {"title": "Dansk film vinder pris ved Cannes Film Festival",
         "description": "Instruktoeeren bag den danske film 'Graenselandet' modtog Guldpalmen ved dette aars Cannes Film Festival.",
         "source": "Politiken", "category": "underholdning", "link": "https://politiken.dk/demo-cannes"},
        {"title": "Ny forskning: Havvand kan rense sig selv for mikroplast",
         "description": "Forskere ved Koebenhavns Universitet har opdaget en naturlig proces, hvor bestemte bakterier i havvand kan nedbryde mikroplast.",
         "source": "DR Nyheder", "category": "videnskab", "link": "https://www.dr.dk/nyheder/demo-mikroplast"},
        {"title": "Regeringen praesenterer ny digitaliseringsstrategi",
         "description": "Den nye strategi fokuserer paa at goere Danmark til foregangsland inden for digitalisering af den offentlige sektor.",
         "source": "DR Nyheder", "category": "teknologi", "link": "https://www.dr.dk/nyheder/demo-digitalisering"},
        {"title": "Haandboldlandsholdet klar til VM-semifinale",
         "description": "De danske haandboldhelte besejrede Frankrig med 28-24 og er nu klar til VM-semifinalen mod Sverige.",
         "source": "TV2 Nyheder", "category": "sport", "link": "https://nyheder.tv2.dk/demo-haandbold"},
        {"title": "Danske startups tiltraekker rekordinvesteringer",
         "description": "Danske tech-startups har i foerste kvartal tiltrukket over 5 milliarder kroner i venturekapital, hvilket er ny rekord.",
         "source": "Boersen", "category": "økonomi", "link": "https://borsen.dk/demo-startups"},
        {"title": "Ny dansk TV-serie slaar seerrekord paa streaming",
         "description": "Dramaserien 'Broerne' har sat ny rekord som den mest sete danske serie nogensinde paa streaming-tjenesterne.",
         "source": "Politiken", "category": "underholdning", "link": "https://politiken.dk/demo-streaming"},
        {"title": "Klimaforskere advarer: Groenlands indlandsis smelter hurtigere end ventet",
         "description": "Nye satellitdata viser, at Groenlands indlandsis mister is tre gange hurtigere end forudset i tidligere modeller.",
         "source": "Ingenioeren", "category": "videnskab", "link": "https://ing.dk/artikel/demo-groenland"},
        {"title": "Opposition kraever ministerens afgang efter laekagesag",
         "description": "Flere oppositionspartier kraever ministerens afgang efter afsloering af laekede fortrolige dokumenter til pressen.",
         "source": "Politiken", "category": "politik", "link": "https://politiken.dk/demo-minister"},
    ]

    articles = []
    for i, demo in enumerate(demos):
        ts = base_ts - (i * 1800)
        dt = datetime.fromtimestamp(ts)
        article_id = generate_id(demo["title"], demo["link"])
        articles.append({
            "id": article_id, "title": demo["title"], "link": demo["link"],
            "description": demo["description"], "source": demo["source"],
            "pubDate": dt.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "timestamp": ts, "category": demo["category"], "imageUrl": "",
        })
    return articles


def fetch_all_feeds():
    """Fetch all RSS feeds and store in database."""
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

    if not all_articles:
        all_articles = get_demo_articles()
        print("No live feeds available - loaded demo articles")

    upsert_articles(all_articles)
    cleanup_old_articles()

    print(f"Fetched {len(all_articles)} articles from {len(RSS_SOURCES)} sources")


# --- Routes ---

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


@app.route("/api/articles")
def api_articles():
    rows = get_all_articles()
    articles = [{
        "id": r["id"],
        "title": r["title"],
        "link": r["link"],
        "description": r["description"] or "",
        "source": r["source"] or "",
        "pubDate": r["pub_date"] or "",
        "timestamp": r["timestamp"] or 0,
        "category": r["category"] or "",
        "imageUrl": r["image_url"] or "",
        "saved": bool(r["saved"]),
    } for r in rows]

    return jsonify({
        "articles": articles,
        "lastUpdated": get_last_fetch_time(),
        "totalCount": len(articles),
    })


@app.route("/api/categories")
def api_categories():
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


@app.route("/api/articles/<article_id>/save", methods=["POST"])
def save_article(article_id):
    conn = get_db()
    conn.execute("UPDATE articles SET saved = 1 WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "saved": True})


@app.route("/api/articles/<article_id>/unsave", methods=["POST"])
def unsave_article(article_id):
    conn = get_db()
    conn.execute("UPDATE articles SET saved = 0 WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "saved": False})


@app.route("/api/refresh", methods=["POST"])
def refresh_feeds():
    fetch_all_feeds()
    count = len(get_all_articles())
    return jsonify({"success": True, "articleCount": count})


# Initialize database and fetch feeds at startup
init_db()
fetch_all_feeds()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
