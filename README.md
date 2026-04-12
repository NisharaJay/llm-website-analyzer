# LLM Website Content Analyzer

A backend system that crawls a website, analyzes its text content using an open-source LLM (Gemma via Google AI Studio), and returns structured recommendations for improving the site's content.

---

## Features

- BFS web crawler with configurable depth and page limit
- LLM-powered content analysis (clarity, grammar, tone, CTAs, structure, trust)
- Recommendations for both improving existing content and adding missing content
- Parallel processing — pages and chunks analyzed concurrently
- File-backed caching — repeat requests return instantly without re-crawling
- Graceful handling of failed, empty, duplicate, and inaccessible pages

---

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
GOOGLE_API_KEY=your_google_ai_studio_key_here
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

---

## Running the application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

Interactive API docs (Swagger UI): `http://127.0.0.1:8000/docs`

---

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

### `GET /health`

Returns `{"status": "ok"}`. Useful for checking the server is running.

---

## Assumptions

- The target website must be publicly accessible (no authentication required).
- Pages that render content via JavaScript only (SPAs without SSR) may return thin or empty content, as the crawler does not execute JavaScript.
- The crawler respects the `max_pages` and `crawl_depth` limits and stays within the same domain as the starting URL.
- Pages with fewer than 50 characters of extracted text are considered insufficient and skipped.
- The LLM (Gemma 3 4B Instruct via Google AI Studio) is assumed to be available and within API quota. Chunk-level failures are logged but do not abort the overall analysis.
- Each page's text is split into 3,000-character chunks, with a maximum of 9,000 characters (3 chunks) analyzed per page to stay within model limits.
- Cache is stored as a local JSON file (`data/cache.json`). This is suitable for development and single-instance deployments. For production, replace with database-backed cache.

---

## Known Limitations

- **JavaScript-rendered content**: Pages that rely on client-side JS to render their main content will not be analyzed correctly. Consider adding a Playwright/Selenium-based renderer for such sites.
- **Rate limiting**: The crawler does not implement rate limiting or `robots.txt` compliance. Aggressive crawling could get your IP blocked by some websites.
- **LLM accuracy**: Gemma 3 4B is a small model. Recommendations may occasionally be generic or hallucinated. Larger models will yield better results.
- **Cache is not invalidated automatically** beyond TTL expiry. If the website content changes, you must wait for the TTL to expire or delete `data/cache.json` manually.
- **No authentication support**: The crawler cannot access pages behind login walls.
- **Single-instance cache**: The file-based cache is not safe for concurrent multi-process deployments. Use a shared cache backend (e.g. Redis) for production.