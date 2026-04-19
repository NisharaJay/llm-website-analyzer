import os
import json
import time
import hashlib
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = "data/cache.json"
CACHE_TTL = int(os.getenv("CACHE_TTL", 86400))  # 24 hours


def _init_cache():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w") as f:
            json.dump({}, f)


def generate_cache_key(url: str, crawl_depth: int) -> str:
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
    if time.time() - entry["created_at"] > CACHE_TTL:
        # expired - remove
        del cache[cache_key]
        _save_cache(cache)
        return None
    
    data = entry["data"]

    pages = data.get("pages_crawled", [])

    # If cache has enough pages - slice
    if len(pages) >= max_pages:
        sliced = dict(data)
        sliced["pages_crawled"] = pages[:max_pages]
        sliced["page_count"] = max_pages
        return sliced

    return None


def set_cache(cache_key: str, data: dict):
    cache = _load_cache()

    new_pages = len(data.get("pages_crawled", []))

    if cache_key in cache:
        existing_pages = len(cache[cache_key]["data"].get("pages_crawled", []))

        # keep the bigger dataset
        if existing_pages >= new_pages:
            return

    cache[cache_key] = {
        "data": data,
        "created_at": time.time()
    }

    _save_cache(cache)



def clear_cache():
    _save_cache({})