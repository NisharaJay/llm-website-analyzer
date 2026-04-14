# LLM Website Content Analyzer

A backend system that crawls a website, analyzes its text content using an open-source LLM (Gemma via Google AI Studio), and returns structured recommendations for improving the site's content.


## Features

- BFS web crawler with configurable depth and page limit
- LLM-powered content analysis (clarity, grammar, tone, CTAs, structure, trust)
- Recommendations for improving existing content and adding missing content
- Parallel processing using thread pools for page and section-level analysis
- File-backed caching for faster repeat requests
- Graceful handling of failed, empty, duplicate, and inaccessible pages


## Setup

### 1. Prerequisites

- Python 3.10 or higher
- A Google AI Studio API key with access to Gemma models ([get one here](https://aistudio.google.com/app/apikey))

### 2. Clone the repository

```bash
git clone https://github.com/NisharaJay/llm-website-analyzer
cd llm-website-analyzer
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=google_ai_studio_key_here
CACHE_TTL=86400
```

`CACHE_TTL` is optional. It controls how long (in seconds) cached results are kept. Default is 86400 (24 hours).

### 5. Project structure

```
.
├── app/
│   ├── main.py           # FastAPI app and /analyze endpoint
│   ├── crawler.py        # Web crawler
│   ├── analyzer.py       # LLM analysis logic
│   └── cache_manager.py  # File-backed caching
├── data/
│   └── cache.json        # Auto-created on first run
├── requirements.txt
├── .env
└── README.md
```


## Running the application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

Interactive API docs (Swagger UI): `http://127.0.0.1:8000/docs`


## API Usage

### `POST /analyze`

Crawls and analyzes a website.

**Request body:**

```json
{
  "url": "https://example.com",
  "crawl_depth": 1,
  "max_pages": 5
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | string | required | The website URL to analyze |
| `crawl_depth` | integer | `1` | How many link-hops deep to crawl (0–5) |
| `max_pages` | integer | `5` | Maximum number of pages to crawl (1–50) |

**Example with curl:**

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "crawl_depth": 1, "max_pages": 5}'
```

**Response shape:**

```json
{
  "source": "fresh",
  "url": "https://example.com",
  "pages_crawled": ["https://example.com", "https://example.com/about"],
  "page_count": 2,
  "skipped_pages": [
    {"url": "https://example.com/login", "reason": "matched skip pattern"},
    {"url": "https://example.com/broken", "reason": "HTTP 404"}
  ],
  "analysis": {
    "status": "success",
    "total_pages": 2,
    "global_summary": {
      "total_issues": 12,
      "high_priority": 3,
      "medium_priority": 6,
      "low_priority": 3
    },
    "results": {
      "https://example.com": {
        "status": "success",
        "chunks_analyzed": 2,
        "summary": "...",
        "improvements": [
          {
            "category": "clarity",
            "priority": "high",
            "issue": "Vague headline",
            "evidence": "...",
            "suggested_change": "...",
            "reason": "...",
            "page": "https://example.com"
          }
        ],
        "new_content_suggestions": [
          {
            "missing_content": "FAQ section",
            "where_to_add": "Homepage",
            "suggested_version": "...",
            "reason": "...",
            "page": "https://example.com"
          }
        ],
        "text_length": 3200
      }
    }
  }
}
```

`"source"` will be `"fresh"` on first call and `"cache"` on repeat calls within the TTL window.

#### Cache behavior
First request → "source": "fresh"
Repeated request (within TTL) → "source": "cache"

Cache stored in: `"data/cache.json'`



### `GET /health`

Returns `{"status": "ok"}`. Useful for checking the server is running.



## Assumptions

- Website must be publicly accessible (no login/auth support)
- JavaScript-rendered pages may return incomplete content (no JS execution)
- Pages with < 50 characters of extracted text are skipped
- Each page is split into sections for parallel LLM analysis
- LLM used: Gemma 3 4B via Google AI Studio
- Cache is file-based and intended for single-instance development use



## Known Limitations

- No JavaScript rendering (no Playwright / Selenium)
- No robots.txt compliance or rate limiting
- Small LLM (Gemma 3 4B) may produce generic recommendations
- File based cache is not suitable for distributed systems
- No authentication support for protected pages
