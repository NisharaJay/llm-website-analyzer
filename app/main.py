from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator

from app.cache_manager import (
    generate_cache_key,
    get_cached_result,
    set_cache
)
from app.crawler import crawl_website
from app.analyzer import analyze_website_content

app = FastAPI(
    title="LLM Website Content Analyzer",
    description="Crawls a website, analyzes content with an LLM, and returns structured improvement recommendations.",
    version="1.0.0"
)


class AnalyzeRequest(BaseModel):
    url: HttpUrl
    crawl_depth: int = 1
    max_pages: int = 5

    @field_validator("crawl_depth")
    @classmethod
    def validate_depth(cls, v):
        if v < 0 or v > 5:
            raise ValueError("crawl_depth must be between 0 and 5")
        return v

    @field_validator("max_pages")
    @classmethod
    def validate_pages(cls, v):
        if v < 1 or v > 50:
            raise ValueError("max_pages must be between 1 and 50")
        return v


def _build_response(url: str, data: dict, source: str) -> dict:
    """Ensure a consistent response shape regardless of cache or fresh."""
    return {
        "source": source,
        "url": url,
        "pages_crawled": data.get("pages_crawled", []),
        "page_count": data.get("page_count", 0),
        "skipped_pages": data.get("skipped_pages", []),
        "analysis": data.get("analysis", {})
    }


@app.post("/analyze")
def analyze_website(request: AnalyzeRequest):
    url_str = str(request.url)

    try:
        cache_key = generate_cache_key(url_str, request.crawl_depth, request.max_pages)
        cached = get_cached_result(cache_key, request.max_pages)

        if cached:
            return _build_response(url_str, cached, source="cache")

        pages, skipped_pages = crawl_website(
            start_url=url_str,
            max_pages=request.max_pages,
            max_depth=request.crawl_depth
        )

        if not pages:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "No content could be extracted from the website.",
                    "skipped_pages": skipped_pages
                }
            )

        analysis = analyze_website_content(pages)

        result = {
            "pages_crawled": list(pages.keys()),
            "page_count": len(pages),
            "skipped_pages": skipped_pages,
            "analysis": analysis
        }

        set_cache(cache_key, result)

        return _build_response(url_str, result, source="fresh")

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/health")
def health_check():
    return {"status": "ok"}