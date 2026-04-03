"""
Web3 Job Scanner v4 → Telegram Bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v4 fix: Claude's web search doesn't support site: operators well.
Now uses plain language queries + instructs Claude to run
multiple searches per batch to cast a wider net.
"""

import requests
import json
import time
import os
from datetime import datetime

# ━━━ CONFIGURATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@your_channel_name")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")

EXCLUDE_ROLES = [
    "solidity", "smart contract dev", "rust dev",
    "backend engineer", "frontend dev", "devops",
    "data engineer", "QA engineer", "security auditor",
    "machine learning", "quantitative", "infra engineer"
]

# ━━━ SEARCH BATCHES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEARCH_BATCHES = [
    {
        "name": "Growth & Marketing roles",
        "prompt": """Search for current Web3 and crypto growth marketing job openings. 
Run these searches:
1. "web3 growth marketing manager remote job"
2. "crypto marketing lead hiring remote"
3. "web3.career marketing jobs"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
    {
        "name": "Content Marketing roles",
        "prompt": """Search for current Web3 and crypto content marketing job openings.
Run these searches:
1. "crypto content marketing manager remote job"
2. "web3 content lead hiring 2026"
3. "cryptojobslist.com content marketing"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
    {
        "name": "Video & Creative roles",
        "prompt": """Search for current crypto and Web3 video content jobs.
Run these searches:
1. "crypto video content creator job remote"
2. "web3 TikTok content strategist hiring"
3. "blockchain video producer job 2026"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
    {
        "name": "Community Lead roles",
        "prompt": """Search for current Web3 and crypto community manager jobs.
Run these searches:
1. "web3 community lead remote job hiring"
2. "crypto community manager job 2026"
3. "cryptojobslist community manager remote"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
    {
        "name": "Social Media roles",
        "prompt": """Search for current Web3 and crypto social media jobs.
Run these searches:
1. "crypto social media manager remote job"
2. "web3 social media lead hiring"
3. "blockchain social media strategist job 2026"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
    {
        "name": "Web3.career latest listings",
        "prompt": """Go to web3.career and find the latest marketing, content, growth, community, and video jobs listed there.
Run these searches:
1. "web3.career content marketing jobs"
2. "web3.career growth remote jobs"  
3. "web3.career community manager jobs"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
    {
        "name": "CryptoJobsList latest",
        "prompt": """Find the latest marketing and community jobs on CryptoJobsList.
Run these searches:
1. "cryptojobslist.com marketing jobs remote"
2. "cryptojobslist.com community jobs"
3. "cryptojobslist remote marketing crypto"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
    {
        "name": "BD & Partnerships roles",
        "prompt": """Search for Web3 business development and partnerships jobs.
Run these searches:
1. "web3 business development manager remote job"
2. "crypto partnerships manager hiring 2026"
3. "blockchain brand evangelist job remote"

Find actual job postings with title, company, salary, location, and apply URL."""
    },
]

# ━━━ SEARCH ENGINE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_batch(batch):
    """Run one batch of searches via Claude."""

    system = """You are a job search assistant. Your ONLY job is to find real job postings and return them as JSON.

Rules:
- Search the web using the queries provided
- ONLY return jobs you actually found in search results
- Do NOT invent, guess, or hallucinate any jobs
- Skip engineering/developer/solidity roles
- Each job must have a real URL you found
- Return max 10 jobs per batch

Return format: A JSON array, nothing else. No explanation, no markdown, no code fences.
If zero jobs found, return exactly: []

Example:
[{"title":"Growth Lead","company":"Acme Protocol","salary":"$80k-$120k","location":"Remote","url":"https://web3.career/growth-lead-acme/12345","source":"web3.career"}]"""

    prompt = f"""{batch['prompt']}

For each REAL job posting you find, extract:
- title: Exact job title from the listing
- company: Company name
- salary: Salary if shown, otherwise "Not listed"
- location: Location or "Remote"
- url: The actual URL where you found this job
- source: Website name (e.g. "web3.career", "cryptojobslist.com")

Return ONLY the JSON array. Nothing else."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2024-01-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "system": system,
                "tools": [
                    {"type": "web_search_20250305", "name": "web_search"}
                ],
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=240
        )

        resp.raise_for_status()
        data = resp.json()

        # Extract all text blocks
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        full_text = " ".join(text_parts).strip()

        # Debug: print first bit of response
        preview = full_text[:150].replace('\n', ' ')
        print(f"  Response preview: {preview}")

        # Clean markdown fences
        if "```" in full_text:
            for part in full_text.split("```"):
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.startswith("["):
                    full_text = cleaned
                    break

        # Find JSON array
        start = full_text.find("[")
        end = full_text.rfind("]") + 1
        if start >= 0 and end > start:
            json_str = full_text[start:end]
            jobs = json.loads(json_str)
            if isinstance(jobs, list):
                return jobs

        print(f"  ⚠ Could not extract JSON from response")
        return []

    except requests.exceptions.Timeout:
        print(f"  ⏱ Timeout (240s)")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ❌ API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text[:300]}")
        return []
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        return []


def search_all():
    """Run all batches."""
    all_jobs = []

    for i, batch in enumerate(SEARCH_BATCHES):
        print(f"\n[{i+1}/{len(SEARCH_BATCHES)}] 🔍 {batch['name']}")
        jobs = search_batch(batch)
        count = len(jobs)
        print(f"  → {count} job{'s' if count != 1 else ''}")
        all_jobs.extend(jobs)

        if i < len(SEARCH_BATCHES) - 1:
            print(f"  ⏳ Waiting 5s...")
            time.sleep(5)

    return all_jobs


# ━━━ PROCESSING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def deduplicate(jobs):
    """Remove duplicates by title+company."""
    seen = set()
    unique = []
    for job in jobs:
        key = (
            job.get("title", "").lower().strip(),
            job.get("company", "").lower().strip()
        )
        if key not in seen and key != ("", ""):
            seen.add(key)
            unique.append(job)
    return unique


def filter_jobs(jobs):
    """Remove irrelevant entries."""
    filtered = []
    for job in jobs:
        title = job.get("title", "").lower()
        if not job.get("title") or not job.get("company"):
            continue
        if any(exc in title for exc in EXCLUDE_ROLES):
            continue
        filtered.append(job)
    return filtered


# ━━━ TELEGRAM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def send_telegram(message):
    """Send message to Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        })
        if resp.status_code != 200:
            # Fallback plain text
            plain = message.replace("*", "").replace("_", "")
            resp = requests.post(url, json={
                "chat_id": CHANNEL_ID,
                "text": plain,
                "disable_web_page_preview": True
            })
        return resp.status_code == 200
    except Exception as e:
        print(f"  Telegram error: {e}")
        return False


def format_job(job):
    """Format job for Telegram."""
    lines = [
        f"🚀 *{job.get('title', 'Unknown')}*",
        f"🏢 {job.get('company', 'Unknown')}",
        f"💰 {job.get('salary', 'Not listed')}",
        f"📍 {job.get('location', 'Remote')}",
    ]
    if job.get("source"):
        lines.append(f"📡 {job['source']}")
    lines.append(f"\n🔗 [Apply Now]({job.get('url', '#')})")
    return "\n".join(lines)


# ━━━ MAIN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    now = datetime.now()
    print(f"{'='*50}")
    print(f"Web3 Job Scanner v4")
    print(f"{now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{len(SEARCH_BATCHES)} search batches")
    print(f"{'='*50}")

    # Search
    all_jobs = search_all()
    raw_count = len(all_jobs)
    print(f"\n📋 Raw: {raw_count}")

    # Dedup
    all_jobs = deduplicate(all_jobs)
    dedup_count = len(all_jobs)
    print(f"🧹 Dedup: {dedup_count}")

    # Filter
    all_jobs = filter_jobs(all_jobs)
    final_count = len(all_jobs)
    print(f"🎯 Final: {final_count}")

    # No results
    if final_count == 0:
        print("\n😔 No matching jobs.")
        send_telegram(
            f"📊 *Job Scan — {now.strftime('%b %d, %H:%M')} UTC*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔍 Ran {len(SEARCH_BATCHES)} searches\n"
            f"📋 Raw results: {raw_count}\n"
            f"🎯 After filter: 0 matching jobs\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"_Next scan in ~12 hours._"
        )
        return

    # Header
    send_telegram(
        f"🔔 *{final_count} Web3 Jobs Found!*\n"
        f"_{now.strftime('%b %d, %Y — %H:%M')} UTC_\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    time.sleep(1)

    # Send jobs
    sent = 0
    for job in all_jobs:
        if send_telegram(format_job(job)):
            sent += 1
            print(f"  ✅ {job.get('title')} @ {job.get('company')}")
        else:
            print(f"  ❌ {job.get('title')}")
        time.sleep(1.5)

    # Summary
    time.sleep(1)
    send_telegram(
        f"📊 *Scan Complete*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 Searches: {len(SEARCH_BATCHES)}\n"
        f"📋 {raw_count} raw → {dedup_count} dedup → {final_count} final\n"
        f"✅ Sent: {sent}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    print(f"\nDone! {sent}/{final_count} sent.")


if __name__ == "__main__":
    main()
