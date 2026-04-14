import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))



def clean_json_response(raw: str) -> str:
    if not raw:
        return ""

    raw = raw.strip()

    # remove code fences safely
    if "```" in raw:
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]

    raw = raw.replace("json", "", 1).strip()

    return raw


def call_llm_with_retry(prompt, retries=3):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemma-3-4b-it",
                contents=prompt,
            )
            return response.text or ""
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2 ** attempt)


def safe_json_parse(text: str):
    try:
        return json.loads(text), None
    except Exception as e:
        return None, str(e)



def build_prompt(url, text):
    return f"""
You are an expert website content optimization analyst.

Rules:
- Analyze ONLY given content
- Do NOT hallucinate
- Return ONLY valid JSON

Schema:
{{
  "summary": "short summary of content",
  "improvements": [
    {{
      "category": "clarity|grammar|tone|cta|structure|trust",
      "priority": "high|medium|low",
      "issue": "problem description",
      "evidence": "text snippet",
      "suggested_change": "improvement suggestion",
      "reason": "why this matters"
    }}
  ],
  "new_content_suggestions": [
    {{
      "missing_content": "what is missing",
      "where_to_add": "section",
      "suggested_version": "example content",
      "reason": "benefit"
    }}
  ]
}}

PAGE URL: {url}
CONTENT:
{text}
"""


def analyze_section(url: str, section: str, idx: int):
    try:
        prompt = build_prompt(url, section)
        raw = call_llm_with_retry(prompt)
        cleaned = clean_json_response(raw)

        parsed, error = safe_json_parse(cleaned)

        if error or not parsed:
            return {"success": False, "error": error, "section": idx}

        return {"success": True, "data": parsed}

    except Exception as e:
        return {"success": False, "error": str(e), "section": idx}


def analyze_page(url: str, page_data: dict):
    full_text = page_data.get("full_text", "")

    if not full_text or len(full_text.strip()) < 50:
        return {"status": "failed", "error": "Insufficient content"}

    sections = page_data.get("sections")

    # fallback: treat full page as one section
    if not sections or not isinstance(sections, list):
        sections = [{"content": full_text}]

    improvements = []
    suggestions = []
    summaries = []

    max_threads = min(5, len(sections)) or 1

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = []

        for i, sec in enumerate(sections):
            text = sec.get("content") if isinstance(sec, dict) else str(sec)
            if not text.strip():
                continue

            futures.append(executor.submit(analyze_section, url, text, i))

        for future in as_completed(futures):
            result = future.result()

            if not result.get("success"):
                continue

            data = result["data"]

            improvements.extend(data.get("improvements", []))
            suggestions.extend(data.get("new_content_suggestions", []))

            if data.get("summary"):
                summaries.append(data["summary"])

    print(f"[PAGE DONE] {url}")

    return {
        "status": "success",
        "summary": summaries[0] if summaries else "",
        "improvements": improvements,
        "new_content_suggestions": suggestions,
        "text_length": len(full_text)
    }


def analyze_website_content(pages: dict):
    if not pages:
        return {"status": "failed", "error": "No pages to analyze"}

    results = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(analyze_page, url, data): url
            for url, data in pages.items()
        }

        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception as e:
                results[url] = {"status": "failed", "error": str(e)}

    pages_output = []
    all_issues = []
    failed_pages = []

    for url, page in results.items():
        if page.get("status") != "success":
            failed_pages.append({"page": url, "error": page.get("error")})
            continue

        pages_output.append({
            "page": url,
            "summary": page.get("summary", ""),
            "improvements": page.get("improvements", []),
            "new_content_suggestions": page.get("new_content_suggestions", [])
        })

        all_issues.extend(page.get("improvements", []))

    return {
        "url": "analysis_result",
        "pages": pages_output,
        "failed_pages": failed_pages,
        "global_summary": {
            "total_issues": len(all_issues),
            "high": len([i for i in all_issues if i.get("priority") == "high"]),
            "medium": len([i for i in all_issues if i.get("priority") == "medium"]),
            "low": len([i for i in all_issues if i.get("priority") == "low"])
        }
    }