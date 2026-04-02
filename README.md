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

## Teknologi

- **Backend**: Python / Flask
- **Frontend**: Vanilla HTML, CSS, JavaScript
- **Datakilder**: RSS-feeds fra danske medier
- **Lagring**: localStorage (brugerpraefrencer), in-memory cache (artikler)
