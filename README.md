# Mine Nyheder - Personlig Nyhedsside

En webbaseret platform der samler nyheder fra danske medier og praesenterer dem i et personligt feed baseret paa dine interesser.

## Funktioner

- **Nyhedsindsamling** fra 5 danske kilder (DR, TV2, Politiken, Boersen, Ingenioeren)
- **Kategorisering** af artikler (Teknologi, Politik, Sport, Oekonomi, Underholdning, Videnskab)
- **Personalisering** - vaelg dine interesser og faa relevante nyheder foerst
- **Filtrering** efter kategori
- **Responsivt design** - virker paa baade desktop og mobil
- Nyheder hentes ved opstart og kan opdateres med "Opdater"-knappen

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

## Deploy paa Render

1. Push projektet til GitHub
2. Gaa til [render.com](https://render.com) og opret en gratis konto
3. Klik **New** -> **Web Service**
4. Forbind dit GitHub-repo (`qvisty/Mine-nyheder`)
5. Render finder automatisk `render.yaml` og konfigurerer alt
6. Klik **Deploy**

Din side er live paa `https://mine-nyheder.onrender.com` (eller lignende).

> **Bemærk**: Render's gratis tier sover efter 15 min uden trafik. Foerste besog efter sleep tager ~30 sek - nyheder hentes automatisk naar siden aabnes.

## Projektstruktur

```
Mine-nyheder/
  app.py              # Flask backend - RSS proxy og API
  render.yaml         # Render deploy-konfiguration
  requirements.txt    # Python-afhaengigheder
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

## Teknologi

- **Backend**: Python / Flask / Gunicorn
- **Frontend**: Vanilla HTML, CSS, JavaScript
- **Datakilder**: RSS-feeds fra danske medier
- **Lagring**: localStorage (brugerpraeferencer), in-memory cache (artikler)
