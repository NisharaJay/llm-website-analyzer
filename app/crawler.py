import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import hashlib


SKIP_PATTERNS = ["login", "signup", "logout", "privacy", "terms", "cookie", "cart", "checkout"]


def normalize_url(url):
    parsed = urlparse(url)
    return parsed._replace(fragment="", query="").geturl().rstrip("/")


def is_valid_url(url, base_domain):
    try:
        parsed = urlparse(url)
        return (
            parsed.netloc == base_domain and
            parsed.scheme in ["http", "https"]
        )
    except Exception:
        return False


def extract_sections(soup):
    sections = []
    current_section = {"title": "intro", "content": ""}

    for tag in soup.find_all(["h1", "h2", "h3", "p"]):
        if tag.name in ["h1", "h2", "h3"]:
            if current_section["content"].strip():
                sections.append(current_section)
            current_section = {
                "title": tag.get_text(strip=True),
                "content": ""
            }
        else:
            current_section["content"] += " " + tag.get_text(strip=True)

    if current_section["content"].strip():
        sections.append(current_section)

    return sections


def extract_text_from_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()

        if "text/html" not in response.headers.get("Content-Type", ""):
            return "", None, "non-html content type"

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.extract()

        text = " ".join(soup.get_text(separator=" ").split())
        return text, soup, None

    except requests.exceptions.Timeout:
        return "", None, "timeout"
    except requests.exceptions.HTTPError as e:
        return "", None, f"HTTP {e.response.status_code}"
    except requests.exceptions.ConnectionError:
        return "", None, "connection error"
    except Exception as e:
        return "", None, str(e)


def crawl_website(start_url, max_pages=5, max_depth=1):
    """
    Crawls a website starting from start_url.

    Returns:
        pages (dict): URL -> {full_text, sections} for successfully crawled pages.
        skipped_pages (list): [{"url": ..., "reason": ...}] for pages that failed or were skipped.
    """
    visited = set()
    seen_content_hashes = set()

    start_url = normalize_url(start_url)
    queue = deque([(start_url, 0)])
    base_domain = urlparse(start_url).netloc

    pages = {}
    skipped_pages = []

    print(f"[CRAWL START] {start_url} | max_pages={max_pages} max_depth={max_depth}")

    while queue and len(pages) < max_pages:
        url, depth = queue.popleft()

        if url in visited:
            continue

        if depth > max_depth:
            skipped_pages.append({"url": url, "reason": f"exceeded max depth ({max_depth})"})
            continue

        visited.add(url)
        print(f"[CRAWLING] depth={depth} {url}")

        text, soup, error = extract_text_from_page(url)

        if error:
            print(f"[ERROR] {url}: {error}")
            skipped_pages.append({"url": url, "reason": error})
            continue

        if not text:
            print(f"[EMPTY] No content extracted: {url}")
            skipped_pages.append({"url": url, "reason": "no text content extracted"})
            continue

        if len(text.strip()) < 50:
            print(f"[THIN] Content too short: {url}")
            skipped_pages.append({"url": url, "reason": "insufficient content (< 50 chars)"})
            continue

        content_hash = hashlib.md5(text.encode()).hexdigest()

        if content_hash in seen_content_hashes:
            print(f"[DUPLICATE] Skipping duplicate content: {url}")
            skipped_pages.append({"url": url, "reason": "duplicate content"})
            continue

        seen_content_hashes.add(content_hash)
        sections = extract_sections(soup) if soup else []

        pages[url] = {
            "full_text": text,
            "sections": sections
        }

        print(f"[SAVED] {url} | {len(text)} chars | {len(sections)} sections")

        if soup and depth < max_depth:
            for link in soup.find_all("a", href=True):
                full_url = normalize_url(urljoin(url, link["href"]))

                if (
                    is_valid_url(full_url, base_domain)
                    and full_url not in visited
                    and not any(x in full_url.lower() for x in SKIP_PATTERNS)
                ):
                    queue.append((full_url, depth + 1))

    print(f"[CRAWL DONE] {len(pages)} pages collected | {len(skipped_pages)} skipped")
    return pages, skipped_pages