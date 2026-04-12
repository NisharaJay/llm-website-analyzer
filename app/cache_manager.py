import os
import json
import time
import hashlib

CACHE_FILE = "data/cache.json"
CACHE_TTL = int(os.getenv("CACHE_TTL", 86400))  # default: 24 hours


def _init_cache():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w") as f:
            json.dump({}, f)


def generate_cache_key(url: str, crawl_depth: int, max_pages: int) -> str:
    raw = f"{url}|{crawl_depth}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _load_cache() -> dict:
    _init_cache()
    with open(CACHE_FILE, "r") as f:
        return json.load(f)


def _save_cache(cache_data: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache_data, f, indent=2)


def get_cached_result(cache_key: str, max_pages: int):
    cache = _load_cache()

    if cache_key not in cache:
        return None

    entry = cache[cache_key]
    age = time.time() - entry["created_at"]

    if age > CACHE_TTL:
        return None

    cached_page_count = entry["data"].get("page_count", 0)
    if cached_page_count < max_pages:
        print(f"[CACHE MISS] cached {cached_page_count} pages < requested {max_pages}")
        return None

    # Slice down to requested max_pages
    data = entry["data"]
    if cached_page_count > max_pages:
        sliced_pages = data["pages_crawled"][:max_pages]
        sliced_results = {
            k: v for k, v in data["analysis"]["results"].items()
            if k in sliced_pages
        }
        all_issues = []
        for page in sliced_results.values():
            all_issues.extend(page.get("improvements", []))

        return {
            "pages_crawled": sliced_pages,
            "page_count": max_pages,
            "skipped_pages": data.get("skipped_pages", []),
            "analysis": {
                **data["analysis"],
                "total_pages": max_pages,
                "global_summary": {
                    "total_issues": len(all_issues),
                    "high_priority": len([i for i in all_issues if i.get("priority") == "high"]),
                    "medium_priority": len([i for i in all_issues if i.get("priority") == "medium"]),
                    "low_priority": len([i for i in all_issues if i.get("priority") == "low"]),
                },
                "results": sliced_results
            }
        }

    return data


def set_cache(cache_key: str, data: dict):
    """Store data in the cache with the current timestamp."""
    cache = _load_cache()
    cache[cache_key] = {
        "data": data,
        "created_at": time.time()
    }
    _save_cache(cache)
    print(f"[CACHE SET] key={cache_key[:12]}...")


def clear_cache():
    """Utility: wipe all cached entries."""
    _save_cache({})
    print("[CACHE CLEARED]")