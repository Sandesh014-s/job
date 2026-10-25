#!/usr/bin/env python3
"""Fresher job alerts -> Telegram. Pulls ONLY from companies' own career systems
(Greenhouse, Lever, Workday), so every alert links to the real company posting.
No third-party dependencies."""
import json, os, re, sys, urllib.request, urllib.parse

# ---------- EDIT THIS SECTION ----------
# Open the company's careers page; if the URL looks like one of the patterns
# below, copy the name out of it.
GREENHOUSE = []   # boards.greenhouse.io/<name>      e.g. ["postman"]
LEVER      = []   # jobs.lever.co/<name>             e.g. ["paytm"]
WORKDAY = [
    # {"name": "Company", "host": "xyz.wd3.myworkdayjobs.com",
    #  "tenant": "xyz", "site": "SiteName"}
    # Find these in the careers URL: https://<host>/<site>/...
]
LOCATIONS = ["pune", "hyderabad", "bengaluru", "bangalore", "nagpur", "remote", "india"]
INCLUDE   = ["fresher", "graduate", "trainee", "associate", "entry", "campus",
             "software engineer", "developer", "analyst", "engineer i", "l1", "2025", "2026"]
EXCLUDE   = ["senior", "sr.", "lead", "manager", "principal", "architect",
             "director", "staff", "5+ years", "3+ years"]
# ---------------------------------------

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
SEEN_FILE = "seen.json"


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def greenhouse(name):
    for j in get(f"https://boards-api.greenhouse.io/v1/boards/{name}/jobs")["jobs"]:
        yield name, j["title"], j.get("location", {}).get("name", ""), j["absolute_url"], str(j["id"])


def lever(name):
    for j in get(f"https://api.lever.co/v0/postings/{name}?mode=json"):
        yield name, j["text"], j.get("categories", {}).get("location", ""), j["hostedUrl"], j["id"]


def workday(c):
    base = f"https://{c['host']}/wday/cxs/{c['tenant']}/{c['site']}/jobs"
    offset = 0
    while offset < 200:
        body = json.dumps({"limit": 20, "offset": offset, "searchText": "fresher"}).encode()
        d = get(base, body)
        posts = d.get("jobPostings", [])
        if not posts:
            break
        for p in posts:
            url = f"https://{c['host']}/{c['site']}{p['externalPath']}"
            yield c["name"], p["title"], p.get("locationsText", ""), url, p["externalPath"]
        offset += 20


def matches(title, loc):
    t, l = title.lower(), loc.lower()
    if any(x in t for x in EXCLUDE):
        return False
    if not any(x in t for x in INCLUDE):
        return False
    return not LOCATIONS or not l or any(x in l for x in LOCATIONS)


def notify(text):
    if not TOKEN or not CHAT:
        print(text)
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text,
                                   "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30)


def main():
    seen = set(json.load(open(SEEN_FILE))) if os.path.exists(SEEN_FILE) else set()
    first_run = not seen
    sources = ([(greenhouse, n) for n in GREENHOUSE] + [(lever, n) for n in LEVER]
               + [(workday, c) for c in WORKDAY])
    new = []
    for fn, arg in sources:
        try:
            for company, title, loc, url, jid in fn(arg):
                key = f"{company}:{jid}"
                if key in seen:
                    continue
                seen.add(key)
                if matches(title, loc):
                    new.append((company, title, loc, url))
        except Exception as e:
            print(f"[warn] {fn.__name__} {arg}: {e}", file=sys.stderr)
    if not first_run:  # first run just records existing jobs, no spam
        for company, title, loc, url in new:
            notify(f"New opening: {title}\n{company} | {loc}\nApply (official page): {url}")
    else:
        print(f"First run: recorded {len(seen)} existing jobs. Alerts start from the next run.")
    json.dump(sorted(seen), open(SEEN_FILE, "w"))


if __name__ == "__main__":
    main()
