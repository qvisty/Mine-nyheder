# Mine Nyheder - Personlig Nyhedsside

En webbaseret platform der samler nyheder fra danske medier og praesenterer dem i et personligt feed baseret paa dine interesser.

## Funktioner

- **Nyhedsindsamling** fra 5 danske kilder (DR, TV2, Politiken, Boersen, Ingenioeren)
- **Kategorisering** af artikler (Teknologi, Politik, Sport, Oekonomi, Underholdning, Videnskab)
- **Personalisering** - vaelg dine interesser og faa relevante nyheder foerst
- **Filtrering** efter kategori
- **Responsivt design** - virker paa baade desktop og mobil
- **Automatisk opdatering** af nyheder hvert 15. minut

## Kom i gang

### Krav

- Python 3.10+
- pip

### Installation

```bash
pip install -r requirements.txt
```

### Koer serveren

```bash
python3 app.py
```

Aaben derefter [http://localhost:5000](http://localhost:5000) i din browser.

## Projektstruktur

```
Mine-nyheder/
  app.py              # Flask backend - RSS proxy og API
  requirements.txt    # Python-afhængigheder
  static/
    index.html        # Hovedside
    style.css         # Styling (responsivt)
    app.js            # Frontend-logik
```

## API-endpoints

| Endpoint | Metode | Beskrivelse |
|----------|--------|-------------|
| `/` | GET | Serverer hovedsiden |
| `/api/articles` | GET | Henter alle artikler som JSON |
| `/api/categories` | GET | Henter tilgaengelige kategorier |
| `/api/refresh` | POST | Tvinger opdatering af nyhedsfeeds |

## Deploy paa Render (anbefalet)

Den nemmeste maade at faa appen live - gratis, fuld RSS-adgang, auto-deploy.

1. Push projektet til GitHub
2. Gaa til [render.com](https://render.com) og opret en gratis konto
3. Klik **New** -> **Web Service**
4. Forbind dit GitHub-repo (`qvisty/Mine-nyheder`)
5. Render finder automatisk `render.yaml` og konfigurerer alt
6. Klik **Deploy**

Din side er live paa `https://mine-nyheder.onrender.com` (eller lignende).

Feeds opdateres automatisk i baggrunden hvert 15. minut.

> **Bemærk**: Render's gratis tier sover efter 15 min uden trafik. Foerste besog efter sleep tager ~30 sek.

### Hold appen vaagen + daglig opdatering

Render's gratis tier sover naar der ikke er trafik. For at sikre daglig (eller hyppigere) opdatering kan du bruge en gratis ekstern cron-tjeneste:

**Med [cron-job.org](https://cron-job.org) (gratis):**

1. Opret en gratis konto paa [cron-job.org](https://cron-job.org)
2. Opret et nyt cron job:
   - **URL**: `https://mine-nyheder.onrender.com/api/refresh`
   - **Tidsplan**: Vaelg fx "Hver time" eller "Hver dag kl. 07:00"
   - **Metode**: GET
3. Gem - ferdig!

Dette holder appen vaagen og sikrer friske nyheder.

**Andre gratis cron-tjenester der ogsaa virker:**
- [UptimeRobot](https://uptimerobot.com) - ping hvert 5. minut (holder appen permanent vaagen)
- [Easycron](https://www.easycron.com) - gratis cron med fleksible tidsplaner

## Deploy paa PythonAnywhere

### 1. Opret konto

Gaa til [pythonanywhere.com](https://www.pythonanywhere.com) og opret en gratis konto.

### 2. Upload projektet

Aaben en **Bash console** paa PythonAnywhere og koer:

```bash
git clone https://github.com/qvisty/Mine-nyheder.git mine-nyheder
cd mine-nyheder
pip install --user -r requirements.txt
```

### 3. Opsaet web app

1. Gaa til **Web** tab
2. Klik **Add a new web app**
3. Vaelg **Manual configuration** og **Python 3.10** (eller nyere)
4. Ret **Source code** til: `/home/<dit-brugernavn>/mine-nyheder`
5. Ret **WSGI configuration file** - klik paa linket og erstat indholdet med:

```python
import sys
import os

project_path = '/home/<dit-brugernavn>/mine-nyheder'
if project_path not in sys.path:
    sys.path.insert(0, project_path)
os.chdir(project_path)

from app import app as application
```

6. Under **Static files**, tilfoej:
   - URL: `/static/` -> Directory: `/home/<dit-brugernavn>/mine-nyheder/static`

7. Klik **Reload** paa web-appen

### 4. Opsaet automatisk opdatering (valgfrit)

1. Gaa til **Tasks** tab
2. Tilfoej en scheduled task:
   ```
   python3 /home/<dit-brugernavn>/mine-nyheder/update_feeds.py
   ```
3. Ret `APP_URL` i `update_feeds.py` til din PythonAnywhere-URL

Din side er nu live paa `https://<dit-brugernavn>.pythonanywhere.com`!

## Teknologi

- **Backend**: Python / Flask
- **Frontend**: Vanilla HTML, CSS, JavaScript
- **Datakilder**: RSS-feeds fra danske medier
- **Lagring**: localStorage (brugerpraefrencer), in-memory cache (artikler)
