# Humboldt County Jobs Aggregator

A Python-based job aggregator that scrapes local job listings from government agencies, educational institutions, and community job boards in Humboldt County, California.

## Features

- **3 Job Sources** (Phase 1):
  - NEOGOV: Government jobs from County of Humboldt, Eureka, Arcata, Fortuna, and Yurok Tribe
  - CSU Careers: Cal Poly Humboldt positions
  - EdJoin: Education jobs from local schools and districts

- **Standardized Categories**: All jobs are normalized into 8 categories (Government, Education, Healthcare, Administrative, Technical, Public Safety, Maintenance, Other)

- **REST API**: Full-featured API for accessing job data

- **Web Interface**: Browse jobs by category or employer with a modern, dark-themed UI

## Quick Start

### 1. Set up environment

```bash
cd "Humboldt Jobs"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the scrapers

```bash
# Scrape all sources
python main.py

# Scrape specific sources
python main.py --sources neogov
python main.py --sources csu edjoin
```

### 3. View job statistics

```bash
python main.py --stats
```

### 4. List recent jobs

```bash
# List all recent jobs
python main.py --list

# Filter by category
python main.py --list --category Education

# Filter by employer
python main.py --list --employer "Cal Poly"
```

### 5. Start the web server

```bash
python server.py
```

Then open http://localhost:8000 in your browser.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/jobs` | List all jobs (paginated) |
| `GET /api/jobs?category=Education` | Filter by category |
| `GET /api/jobs?employer=Cal+Poly` | Filter by employer |
| `GET /api/jobs?search=engineer` | Search job titles |
| `GET /api/jobs/{id}` | Get single job by ID |
| `GET /api/employers` | List employers with job counts |
| `GET /api/categories` | List categories with job counts |
| `GET /api/stats` | Get aggregation statistics |

Interactive API documentation is available at `/api/docs` when the server is running.

## Project Structure

```
humboldt_jobs/
├── scrapers/           # Job scrapers for each source
│   ├── base.py         # Base scraper class
│   ├── neogov.py       # Government RSS feeds
│   ├── csu_careers.py  # Cal Poly Humboldt
│   └── edjoin.py       # Education jobs
├── processing/         # Data processing
│   ├── normalizer.py   # Category standardization
│   └── deduplication.py
├── db/                 # Database layer
│   ├── models.py       # SQLAlchemy models
│   └── database.py     # Connection management
├── api/                # REST API
│   ├── app.py          # FastAPI application
│   ├── routes.py       # API endpoints
│   └── web_routes.py   # HTML page routes
├── web/templates/      # Jinja2 HTML templates
├── config.py           # Configuration
├── main.py             # CLI entry point
├── server.py           # Web server runner
└── requirements.txt
```

## Data Sources

### NEOGOV (Government Jobs)
- County of Humboldt
- City of Eureka
- City of Arcata
- City of Fortuna
- Yurok Tribe

### CSU Careers
- Cal Poly Humboldt (faculty, staff, student positions)

### EdJoin
- Humboldt County schools and districts

## Future Phases

Additional sources planned for Phase 2:
- Wiyot Tribe
- City of Rio Dell
- Lost Coast Outpost
- North Coast Journal
- College of the Redwoods

## License

MIT License
