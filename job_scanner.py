"""
Web3 Job Scanner → Telegram Bot
Scans 13 crypto job boards using Claude AI web search,
filters for growth/content/video/community roles,
and sends matching jobs to your Telegram channel.

Setup:
1. Create a Telegram bot via @BotFather → get BOT_TOKEN
2. Create a channel → add bot as admin → get CHANNEL_ID
3. Get an Anthropic API key from console.anthropic.com
4. Set environment variables (or edit the values below)

Run manually:
    python job_scanner.py

Automate via cron (every day at 9 AM):
    0 9 * * * cd /path/to/folder && python3 job_scanner.py >> job_scan.log 2>&1

Or use GitHub Actions (see .github/workflows/job-scan.yml)
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

# Your profile keywords — edit these to match your skills
ROLE_KEYWORDS = [
    "growth marketing", "content marketing", "video content",
    "community lead", "TikTok", "short-form video",
    "content strategist", "content creator", "community manager",
    "growth lead", "social media manager", "content lead",
    "marketing manager", "video editor", "video producer"
]

INDUSTRY_KEYWORDS = ["crypto", "web3", "blockchain", "defi", "nft"]

EXCLUDE_KEYWORDS = [
    "solidity developer", "smart contract developer",
    "backend engineer", "frontend developer", "devops"
]

# Job boards to scan
SOURCES = [
    "web3.career/content-marketing-jobs",
    "web3.career/growth-jobs",
    "web3.career/marketing+remote-jobs",
    "web3.career/remote+video-jobs",
    "web3.career/community-manager-jobs",
    "cryptojobslist.com/marketing",
    "cryptojobslist.com/remote_marketing",
    "cryptocurrencyjobs.co/marketing/",
    "hireweb3.io",
    "wellfound.com/role/crypto-marketing",
    "remoteok.com/remote-crypto-jobs",
    "crypto.jobs",
    "cryptojobs.com/web3",
]

# ━━━ SCANNER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_jobs():
    """Use Claude with web search to find matching jobs."""
    
    role_str = ", ".join(ROLE_KEYWORDS)
    source_str = "\n".join(f"- {s}" for s in SOURCES)
    
    prompt = f"""You are a job search assistant. Search for NEW Web3/crypto job listings 
posted in the last 3 days across these job boards:

{source_str}

Look for roles matching these keywords: {role_str}
The roles MUST be in the crypto/web3/blockchain space.
Remote roles preferred. Exclude pure developer/engineering roles.

For each job found, extract:
- title: Job title
- company: Company name  
- salary: Salary range (or "Not listed")
- location: Location (or "Remote")
- url: Direct link to apply
- source: Which job board it was found on

IMPORTANT: Return ONLY a valid JSON array. No markdown, no explanation, no code fences.
Just the raw JSON array like: [{{"title":"...","company":"...","salary":"...","location":"...","url":"...","source":"..."}}]

If you find no new jobs, return an empty array: []"""

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
                    {
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }
                ],
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=120
        )
        
        resp.raise_for_status()
        data = resp.json()
        
        # Extract text from response blocks
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        
        full_text = " ".join(text_parts).strip()
        
        # Clean up potential markdown fences
        if "```" in full_text:
            full_text = full_text.split("```json")[-1].split("```")[0].strip()
        
        # Find JSON array in response
        start = full_text.find("[")
        end = full_text.rfind("]") + 1
        if start >= 0 and end > start:
            json_str = full_text[start:end]
            jobs = json.loads(json_str)
            return jobs
        
        print(f"No JSON array found in response: {full_text[:200]}")
        return []
        
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}")
        print(f"Raw text: {full_text[:500]}")
        return []


def filter_jobs(jobs):
    """Filter out irrelevant jobs."""
    filtered = []
    for job in jobs:
        title_lower = job.get("title", "").lower()
        
        # Skip excluded roles
        if any(exc in title_lower for exc in EXCLUDE_KEYWORDS):
            continue
        
        filtered.append(job)
    
    return filtered


def format_telegram_message(job):
    """Format a job as a Telegram message."""
    title = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown")
    salary = job.get("salary", "Not listed")
    location = job.get("location", "Remote")
    url = job.get("url", "#")
    source = job.get("source", "")
    
    msg = (
        f"🚀 *{escape_md(title)}*\n"
        f"🏢 {escape_md(company)}\n"
        f"💰 {escape_md(salary)}\n"
        f"📍 {escape_md(location)}\n"
    )
    
    if source:
        msg += f"📡 {escape_md(source)}\n"
    
    msg += f"\n🔗 [Apply Now]({url})"
    
    return msg


def escape_md(text):
    """Escape markdown special characters for Telegram."""
    for char in ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]:
        text = text.replace(char, f"\\{char}")
    return text


def send_to_telegram(message):
    """Send a message to the Telegram channel."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        resp = requests.post(url, json={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True
        })
        
        if resp.status_code != 200:
            # Fallback: send without markdown
            resp = requests.post(url, json={
                "chat_id": CHANNEL_ID,
                "text": message.replace("\\", "").replace("*", "").replace("_", ""),
                "disable_web_page_preview": True
            })
        
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram send failed: {e}")
        return False


def send_summary(total_found, total_sent):
    """Send a daily summary message."""
    now = datetime.now().strftime("%B %d, %Y %I:%M %p")
    msg = (
        f"📊 *Daily Job Scan Summary*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {escape_md(now)}\n"
        f"🔍 Sources scanned: {len(SOURCES)}\n"
        f"📋 Jobs found: {total_found}\n"
        f"✅ Jobs sent: {total_sent}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    send_to_telegram(msg)


# ━━━ MAIN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print(f"[{datetime.now()}] Starting Web3 job scan...")
    print(f"Scanning {len(SOURCES)} sources...")
    
    # Search
    jobs = search_jobs()
    print(f"Found {len(jobs)} raw jobs")
    
    # Filter
    jobs = filter_jobs(jobs)
    print(f"After filtering: {len(jobs)} matching jobs")
    
    # Send to Telegram
    sent = 0
    for job in jobs:
        msg = format_telegram_message(job)
        if send_to_telegram(msg):
            sent += 1
            print(f"  ✅ Sent: {job.get('title', 'Unknown')}")
        else:
            print(f"  ❌ Failed: {job.get('title', 'Unknown')}")
        time.sleep(1.5)  # Rate limit
    
    # Send summary
    send_summary(len(jobs), sent)
    
    print(f"\nDone! Sent {sent}/{len(jobs)} jobs to Telegram.")


if __name__ == "__main__":
    main()
