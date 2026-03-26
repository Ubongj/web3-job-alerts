"""
Web3 Job Scanner v3 → Telegram Bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs targeted searches across crypto job boards,
extracts real listings, and sends them to Telegram.

v3 fix: Instead of dumping 36 URLs into one prompt,
we run focused keyword searches that Claude's web search
can actually find — like a human googling for jobs.
Each batch = 1 API call = 1 focused search query.
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
# Each batch = one API call. Queries written like Google
# searches so web search returns actual job listings.

SEARCH_BATCHES = [
    {
        "name": "Web3.career — Marketing & Growth",
        "query": "site:web3.career content marketing OR growth marketing OR marketing manager OR growth lead remote"
    },
    {
        "name": "Web3.career — Video & Community",
        "query": "site:web3.career video OR community manager OR community lead OR social media remote"
    },
    {
        "name": "CryptoJobsList — All marketing",
        "query": "site:cryptojobslist.com marketing OR content OR community OR growth job remote"
    },
    {
        "name": "CryptocurrencyJobs.co",
        "query": "site:cryptocurrencyjobs.co marketing OR content OR community OR growth job"
    },
    {
        "name": "Crypto growth & content roles",
        "query": "web3 crypto \"growth lead\" OR \"content marketing manager\" OR \"content lead\" remote job 2026"
    },
    {
        "name": "Crypto video & TikTok roles",
        "query": "crypto blockchain \"video content\" OR \"TikTok\" OR \"video strategist\" OR \"creative producer\" remote job 2026"
    },
    {
        "name": "Crypto community & social roles",
        "query": "web3 crypto \"community lead\" OR \"community manager\" OR \"social media lead\" remote job 2026"
    },
    {
        "name": "LinkedIn & Wellfound",
        "query": "site:linkedin.com/jobs OR site:wellfound.com web3 crypto content OR marketing OR growth remote 2026"
    },
    {
        "name": "Greenhouse & Lever (direct company boards)",
        "query": "site:greenhouse.io OR site:lever.co crypto OR web3 OR blockchain marketing OR content OR community OR growth"
    },
    {
        "name": "Brand, partnerships & BD roles",
        "query": "web3 crypto \"brand evangelist\" OR \"partnerships manager\" OR \"business development\" OR \"country manager\" remote job 2026"
    },
]

# ━━━ SEARCH ENGINE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_batch(batch):
    """Run one targeted search via Claude web search."""

    prompt = f"""Search the web for: {batch['query']}

Find ACTUAL job postings from the results. For each real job listing:
- title: Exact job title
- company: Company name
- salary: Salary if shown, or "Not listed"
- location: Location or "Remote"
- url: Direct link to the job posting (NOT a homepage)
- source: Website domain (e.g. "web3.career")

CRITICAL RULES:
1. ONLY include real job postings you found in search results
2. Do NOT invent or guess jobs — only report what you actually see
3. Skip articles, guides, blog posts — only actual job listings
4. Skip engineering/developer/solidity roles
5. Max 10 jobs per search

Return ONLY a JSON array. No text. No markdown. No code fences.
Zero jobs = return exactly: []
Example: [{{"title":"Growth Lead","company":"Acme","salary":"$80k","location":"Remote","url":"https://web3.career/job/123","source":"web3.career"}}]"""

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
                "tools": [
                    {"type": "web_search_20250305", "name": "web_search"}
                ],
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=180
        )

        resp.raise_for_status()
        data = resp.json()

        # Extract text from response
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        full_text = " ".join(text_parts).strip()

        # Clean markdown fences
        if "```" in full_text:
            for part in full_text.split("```"):
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.startswith("["):
                    full_text = cleaned
                    break

        # Parse JSON array
        start = full_text.find("[")
        end = full_text.rfind("]") + 1
        if start >= 0 and end > start:
            jobs = json.loads(full_text[start:end])
            if isinstance(jobs, list):
                return jobs

        print(f"  ⚠ No JSON found in response")
        return []

    except requests.exceptions.Timeout:
        print(f"  ⏱ Timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ❌ API error: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        return []


def search_all():
    """Run all batches with delays between each."""
    all_jobs = []

    for i, batch in enumerate(SEARCH_BATCHES):
        print(f"\n[{i+1}/{len(SEARCH_BATCHES)}] 🔍 {batch['name']}")
        jobs = search_batch(batch)
        print(f"  → {len(jobs)} jobs found")
        all_jobs.extend(jobs)

        # 5s pause between calls to avoid rate limits
        if i < len(SEARCH_BATCHES) - 1:
            time.sleep(5)

    return all_jobs


# ━━━ PROCESSING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def deduplicate(jobs):
    """Remove duplicate jobs by title+company."""
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
    """Remove irrelevant or malformed entries."""
    filtered = []
    for job in jobs:
        title = job.get("title", "").lower()

        # Must have title and company
        if not job.get("title") or not job.get("company"):
            continue

        # Skip excluded roles
        if any(exc in title for exc in EXCLUDE_ROLES):
            continue

        filtered.append(job)
    return filtered


# ━━━ TELEGRAM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def send_telegram(message):
    """Send a message to Telegram channel."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        resp = requests.post(url, json={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        })

        if resp.status_code != 200:
            # Fallback: plain text (strip markdown)
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
    """Format a job for Telegram."""
    title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")
    salary = job.get("salary", "Not listed")
    location = job.get("location", "Remote")
    url = job.get("url", "#")
    source = job.get("source", "")

    lines = [
        f"🚀 *{title}*",
        f"🏢 {company}",
        f"💰 {salary}",
        f"📍 {location}",
    ]
    if source:
        lines.append(f"📡 {source}")
    lines.append(f"\n🔗 [Apply Now]({url})")

    return "\n".join(lines)


# ━━━ MAIN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    now = datetime.now()
    print(f"{'='*50}")
    print(f"Web3 Job Scanner v3")
    print(f"{now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{len(SEARCH_BATCHES)} targeted searches queued")
    print(f"{'='*50}")

    # Search
    all_jobs = search_all()
    raw_count = len(all_jobs)
    print(f"\n📋 Raw total: {raw_count}")

    # Deduplicate
    all_jobs = deduplicate(all_jobs)
    dedup_count = len(all_jobs)
    print(f"🧹 After dedup: {dedup_count}")

    # Filter
    all_jobs = filter_jobs(all_jobs)
    final_count = len(all_jobs)
    print(f"🎯 After filter: {final_count}")

    # No results
    if final_count == 0:
        print("\n😔 No matching jobs found.")
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

    # Send header
    send_telegram(
        f"🔔 *{final_count} Web3 Jobs Found!*\n"
        f"_{now.strftime('%b %d, %Y — %H:%M')} UTC_\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    time.sleep(1)

    # Send each job
    sent = 0
    for job in all_jobs:
        msg = format_job(job)
        if send_telegram(msg):
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
        f"📋 Raw → Dedup → Final: {raw_count} → {dedup_count} → {final_count}\n"
        f"✅ Sent: {sent}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    print(f"\n{'='*50}")
    print(f"Done! {sent}/{final_count} sent to Telegram.")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
