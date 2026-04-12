import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def clean_json_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    return raw


def call_llm_with_retry(prompt, retries=3):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemma-3-4b-it",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2 ** attempt)


def build_prompt(url, text):
    return f"""You are an expert UX content analyst.
Return ONLY valid JSON with no explanation, no markdown, no code fences.

{{
  "summary": "brief overall summary of this page section",
  "improvements": [
    {{
      "category": "clarity|grammar|tone|cta|structure|trust",
      "priority": "high|medium|low",
      "issue": "what is wrong",
      "evidence": "quote or example from the text",
      "suggested_change": "what to change",
      "reason": "why this matters"
    }}
  ],
  "new_content_suggestions": [
    {{
      "missing_content": "what is missing",
      "where_to_add": "page or section name",
      "suggested_version": "example content to add",
      "reason": "why adding this helps"
    }}
  ]
}}

PAGE URL: {url}
CONTENT: {text}"""


def analyze_single_chunk(url: str, chunk: str, chunk_index: int) -> dict:
    """Analyze one chunk — designed to run in parallel."""
    try:
        prompt = build_prompt(url, chunk)
        raw = call_llm_with_retry(prompt)
        cleaned = clean_json_response(raw)
        parsed = json.loads(cleaned)

        #Tag each item with its source page
        for item in parsed.get("improvements", []):
            item["page"] = url
        for item in parsed.get("new_content_suggestions", []):
            item["page"] = url

        return {"success": True, "data": parsed, "chunk_index": chunk_index}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse error: {e}", "chunk_index": chunk_index}
    except Exception as e:
        return {"success": False, "error": str(e), "chunk_index": chunk_index}


def analyze_page(url: str, page_data: dict) -> dict:
    full_text = page_data.get("full_text", "")

    if not full_text or len(full_text.strip()) < 50:
        return {"status": "failed", "error": "Insufficient content"}


    chunks = [full_text[i:i+3000] for i in range(0, min(len(full_text), 9000), 3000)]

    all_improvements = []
    all_suggestions = []
    summaries = []

    # Parallelize chunks within a page
    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {
            executor.submit(analyze_single_chunk, url, chunk, i): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            result = future.result()
            if result["success"]:
                data = result["data"]
                all_improvements.extend(data.get("improvements", []))
                all_suggestions.extend(data.get("new_content_suggestions", []))
                if data.get("summary"):
                    summaries.append(data["summary"])
            else:
                print(f"[CHUNK FAILED] {url} chunk {result['chunk_index']}: {result['error']}")

    return {
        "status": "success",
        "chunks_analyzed": len(chunks),
        "summary": " | ".join(summaries),
        "improvements": all_improvements,
        "new_content_suggestions": all_suggestions,
        "text_length": len(full_text)
    }


def analyze_website_content(pages: dict) -> dict:
    if not pages:
        return {"status": "failed", "error": "No pages to analyze"}

    results = {}

    #Parallelize across pages
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(analyze_page, url, page_data): url
            for url, page_data in pages.items()
        }
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
                print(f"[DONE] {url}")
            except Exception as e:
                results[url] = {"status": "failed", "error": str(e)}

    # Global summary
    all_issues = []
    for page in results.values():
        all_issues.extend(page.get("improvements", []))

    return {
        "status": "success",
        "total_pages": len(results),
        "global_summary": {
            "total_issues": len(all_issues),
            "high_priority": len([i for i in all_issues if i.get("priority") == "high"]),
            "medium_priority": len([i for i in all_issues if i.get("priority") == "medium"]),
            "low_priority": len([i for i in all_issues if i.get("priority") == "low"]),
        },
        "results": results
    }