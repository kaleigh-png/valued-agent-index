#!/usr/bin/env python3
"""
Agent Index scraper  (rubric v1.0)

Finds trending AI agents, collects public evidence about each one, and scores
them with 12 yes/no checks. Every rule is deterministic: the same pages always
give the same score. A check is Yes only when a quote on a public page proves
it; no evidence means No.

Usage:
    pip install requests
    export GITHUB_TOKEN=...            # optional, raises GitHub rate limits
    python scraper.py                  # writes data/agents.json + data/run.json
    python scraper.py --min-sources 2  # the production trending gate

Run it once a day (cron, GitHub Actions, etc.). Each run saves a snapshot in
data/snapshots/, so star momentum becomes exact after 7 days of history.
"""
import argparse, datetime as dt, html as htmllib, json, os, re, sys, time
from pathlib import Path
from urllib.parse import urlparse

import requests

RUBRIC_VERSION = "1.0"
UA = "AgentIndexBot/1.0 (+public evidence only; respects robots.txt)"
TIMEOUT = 15
OUT = Path(__file__).parent / "data"

NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()

session = requests.Session()
session.headers["User-Agent"] = UA
GH_HEADERS = {"Accept": "application/vnd.github+json"}
if os.getenv("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

source_status = {}  # source -> "ok" | "unreachable: ..."


def get(url, **kw):
    try:
        r = session.get(url, timeout=TIMEOUT, **kw)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def days_ago(iso):
    if not iso:
        return None
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (NOW - t).total_seconds() / 86400


# ---------------------------------------------------------------- sources
GITHUB_QUERIES = [
    "topic:ai-agents", "topic:ai-agent", "topic:agentic-ai",
    "topic:llm-agent", "topic:autonomous-agents", "agent in:name,description topic:llm",
]


def src_github(window_days):
    """Agent repos active in the window, ranked by stars gained per day."""
    since = (NOW - dt.timedelta(days=window_days)).date().isoformat()
    created = (NOW - dt.timedelta(days=365)).date().isoformat()
    found = {}
    for q in GITHUB_QUERIES:
        url = ("https://api.github.com/search/repositories?q="
               f"{q} pushed:>={since} created:>={created} stars:>=200"
               "&sort=stars&order=desc&per_page=50")
        r = get(url, headers=GH_HEADERS)
        if r is None:
            source_status["github"] = "unreachable or rate-limited"
            continue
        for it in r.json().get("items", []):
            found[it["full_name"].lower()] = it
        time.sleep(2.2)  # search API: 30 requests / minute
    if found:
        source_status["github"] = "ok"
    mentions = []
    for full, it in found.items():
        mentions.append({
            "source": "github", "key": f"gh:{full}", "date": it["pushed_at"],
            "title": it["full_name"], "url": it["html_url"], "repo": it,
        })
    return mentions


def src_hackernews(window_days):
    ts = int((NOW - dt.timedelta(days=window_days)).timestamp())
    out = []
    for q in ["AI agent", "agents", "agentic"]:
        r = get("https://hn.algolia.com/api/v1/search_by_date",
                params={"query": q, "tags": "(story,show_hn)",
                        "numericFilters": f"created_at_i>{ts},points>20",
                        "hitsPerPage": 100})
        if r is None:
            source_status["hackernews"] = "unreachable"
            return out
        for h in r.json().get("hits", []):
            if h.get("url"):
                out.append({"source": "hackernews", "url": h["url"],
                            "date": h["created_at"], "title": h["title"],
                            "points": h.get("points", 0)})
    source_status["hackernews"] = "ok"
    return out


def src_reddit(window_days):
    out = []
    for sub in ["AI_Agents", "LocalLLaMA", "LLMDevs"]:
        r = get(f"https://www.reddit.com/r/{sub}/top.json",
                params={"t": "week" if window_days <= 7 else "month", "limit": 100})
        if r is None:
            source_status["reddit"] = "unreachable"
            return out
        for c in r.json()["data"]["children"]:
            d = c["data"]
            url = d.get("url_overridden_by_dest") or ""
            if url and "reddit.com" not in url:
                created = dt.datetime.fromtimestamp(d["created_utc"], dt.timezone.utc)
                if days_ago(created.isoformat()) <= window_days:
                    out.append({"source": "reddit", "url": url,
                                "date": created.isoformat(), "title": d["title"],
                                "points": d.get("score", 0)})
    source_status["reddit"] = "ok"
    return out


# ------------------------------------------------------- what counts
# An agent here is a worker: software that does a job on someone's behalf.
# Lists, frameworks, SDKs, courses, benchmarks and news articles are not.
AGENT_RX = re.compile(r"\b(agents?|agentic|assistant|copilot|autonomous|automates?|automation)\b", re.I)
NOT_AGENT_RX = re.compile(
    r"\b(awesome|curated|list of|collection|framework|sdk|library|toolkit|boilerplate|template|starter|"
    r"benchmark|leaderboard|dataset|eval(uation)?s?|paper|survey|course|tutorial|cheat ?sheet|guidance|guidelines|"
    r"skills?|prompts?|plugins? for|examples?|cookbook|workshop|roadmap|interview|study notes|"
    r"blog|newsletter|index(es)? (of|the)|directory|catalog|"
    r"gateway|router|proxy|runtime|harness|headless browser|mcp server|search engine|protocol|"
    r"orchestrat\w+|observability|tracing|memory layer|infrastructure|"
    r"(cli|server|tool|tools|memory|sandbox|workspace|dashboard|ui|interface|model router) for (every |your |any |all |ai |coding |llm )*agents?)\b", re.I)
# Agents built to deceive, evade or abuse are never listed, whatever their score.
NEFARIOUS_RX = re.compile(
    r"\b(stealth|undetectable|anti-?detect(ion)?|evade|evasion|bypass(es|ing)? (bot|captcha|detection|paywall|2fa|mfa|rate limit)|"
    r"captcha (solver|solving|bypass)|passes? (every|all) bot detection|jailbreaks?|malware|ransomware|keylogger|"
    r"credential (stealer|harvest\w*|dump\w*)|phishing|spam(ming|mer)?|fake (reviews?|followers|engagement|accounts?)|"
    r"account (farming|creation bot)|sockpuppets?|botnet|ddos|exploit kit|carding|scalper|sniper bot|"
    r"mass (dm|messag\w+)|auto-?(like|follow|comment)r?s?|cheat(s|ing)?|aimbot|crack(ed|ing)?)\b", re.I)
ARTICLE_RX = re.compile(r"/(blog|news|post|posts|p|article|articles|story|stories|changelog|releases?|docs?|"
                        r"research|press|newsroom|announc\w*|updates?|engineering|learn|guide|guides|"
                        r"\d{4})(/|$)", re.I)


REJECTS = []  # [{key, reason, text}] written to data/rejects.json after every run


def reject(key, reason, text=""):
    REJECTS.append({"key": key, "reason": reason, "text": (text or "")[:120]})


def why_not_agent(text):
    """None if the text describes an agent; otherwise the reason it does not."""
    text = text or ""
    n = NEFARIOUS_RX.search(text)
    if n:
        return f"safety: {n.group(0).lower()}"
    m = NOT_AGENT_RX.search(text)
    if m:
        return f"describes itself as a {m.group(0).lower()}, not a worker"
    if not AGENT_RX.search(text):
        return "never calls itself an agent, assistant or copilot"
    return None


def looks_like_agent(text):
    return why_not_agent(text) is None


def is_product_url(url):
    """A homepage or a GitHub repo, not an article or a deep page."""
    p = urlparse(url)
    if p.netloc.lower().removeprefix("www.") == "github.com":
        return len([x for x in p.path.split("/") if x]) == 2
    parts = [x for x in p.path.split("/") if x]
    return len(parts) <= 1 and not ARTICLE_RX.search(p.path)


SKIP_DOMAINS = {"youtube.com", "twitter.com", "x.com", "medium.com", "arxiv.org",
                "substack.com", "linkedin.com", "techcrunch.com", "theverge.com",
                "news.ycombinator.com", "huggingface.co", "docs.google.com"}


def key_for_url(url):
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("www.")
    if host == "github.com":
        parts = [x for x in p.path.split("/") if x]
        return f"gh:{parts[0].lower()}/{parts[1].lower()}" if len(parts) >= 2 else None
    if not host or any(host == d or host.endswith("." + d) for d in SKIP_DOMAINS):
        return None
    return "web:" + ".".join(host.split(".")[-2:])


def merge(mentions):
    agents, loose = {}, []
    for m in mentions:
        k = m.get("key") or key_for_url(m["url"])
        if not k:
            continue
        m["key"] = k
        if m.get("repo") is None:
            if not is_product_url(m["url"]):
                loose.append(m)      # an article: counts as a mention, never makes a candidate
                continue
            r = why_not_agent(m["title"])
            if r:
                loose.append(m); reject(k, r, m["title"])
                continue
        a = agents.setdefault(k, {"key": k, "mentions": [], "repo": None})
        a["mentions"].append(m)
        if m.get("repo"):
            a["repo"] = m["repo"]
    for m in loose:
        if m["key"] in agents:
            agents[m["key"]]["mentions"].append(m)
    # fold a website record into its GitHub record when the repo lists it as homepage
    for k, a in list(agents.items()):
        if a["repo"] and a["repo"].get("homepage"):
            wk = key_for_url(a["repo"]["homepage"])
            if wk and wk in agents and wk != k:
                a["mentions"] += agents.pop(wk)["mentions"]
    return agents


# ----------------------------------------------------------- evidence fetch
SITE_PATHS = ["", "/pricing", "/security", "/trust", "/privacy", "/docs",
              "/customers", "/case-studies", "/changelog"]


def strip_html(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = htmllib.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def robots_allows(base, path):
    r = get(base + "/robots.txt")
    if r is None:
        return True
    agent_all, disallowed = False, []
    for line in r.text.splitlines():
        line = line.split("#")[0].strip()
        if line.lower().startswith("user-agent:"):
            agent_all = line.split(":", 1)[1].strip() == "*"
        elif agent_all and line.lower().startswith("disallow:"):
            d = line.split(":", 1)[1].strip()
            if d:
                disallowed.append(d)
    return not any((path or "/").startswith(d) for d in disallowed)


def collect_pages(agent):
    """Return list of {url, text, kind} public pages for this agent."""
    pages = []
    repo = agent["repo"]
    if repo:
        full = repo["full_name"]
        branch = repo.get("default_branch", "main")
        for fname, kind in [("README.md", "readme"), ("SECURITY.md", "security")]:
            r = get(f"https://raw.githubusercontent.com/{full}/{branch}/{fname}")
            if r is not None:
                pages.append({"url": f"https://github.com/{full}/blob/{branch}/{fname}",
                              "text": r.text, "kind": kind})
    home = (repo or {}).get("homepage") or next(
        (m["url"] for m in agent["mentions"] if m["source"] != "github"), None)
    if home and "github.com" not in home:
        p = urlparse(home if home.startswith("http") else "https://" + home)
        base = f"{p.scheme}://{p.netloc}"
        reachable = True
        for path in SITE_PATHS:
            if not reachable:
                break
            if not robots_allows(base, path):
                continue
            r = get(base + path)
            if r is None:
                if path == "":
                    reachable = False
                continue
            kind = path.strip("/") or "home"
            if kind == "home":
                agent["_meta"] = page_meta(r.text)
            pages.append({"url": base + path, "text": strip_html(r.text), "kind": kind})
    return pages


def page_meta(html):
    """Site name and one-line description from a homepage, for agents without a repo."""
    def grab(rx):
        m = re.search(rx, html, re.I | re.S)
        return htmllib.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    name = grab(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)') \
        or grab(r"<title[^>]*>([^<|–—-]{2,60})")
    desc = grab(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)') \
        or grab(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)')
    return {"name": name.strip(), "description": desc[:200]}


# ------------------------------------------------------------ the 12 checks
def clean_quote(t):
    t = re.sub(r"<[^>]*>?", " ", t)                     # html tags
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)    # markdown links/images
    t = htmllib.unescape(t).replace("\xa0", " ")
    t = re.sub(r"[*#`|>_]{1,}|-{3,}|={3,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()


SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


def quote_around(text, s, e, pad=90, reach=150, cap=320):
    """Cut a readable quote around text[s:e]: start at the beginning of the
    sentence (if one starts within reach), otherwise at a word boundary with
    an ellipsis; same at the end. Never cuts inside a word."""
    lo = max(0, s - pad - reach)
    ends = [m.end() for m in SENTENCE_END.finditer(text, lo, s)]
    if ends:
        start, lead = ends[-1], ""
    elif s - pad <= 0:
        start, lead = 0, ""
    else:
        start = text.rfind(" ", lo, s - pad)
        start, lead = (start + 1, "…") if start != -1 else (s - pad, "…")
    hi = min(len(text), e + pad + reach)
    m = SENTENCE_END.search(text, e, hi)
    if m:
        end, tail = m.end(), ""
    elif e + pad >= len(text):
        end, tail = len(text), ""
    else:
        end = text.find(" ", e + pad, hi)
        end, tail = (end, "…") if end != -1 else (e + pad, "…")
    sentence_edge = bool(ends) or bool(m)
    if not sentence_edge and end - start > 120:          # menu or badge text with no sentences: keep it short
        start = text.rfind(" ", max(0, s - 45), s) + 1 or max(0, s - 45)
        end = text.find(" ", e, min(len(text), e + 45))
        end = end if end != -1 else min(len(text), e + 45)
    q = text[start:end].strip()
    if len(q) > cap:                                     # keep the match, trim the far side
        over = len(q) - cap
        if (s - start) > (end - e):
            cut = q.find(" ", over)
            q, lead = (q[cut + 1:] if cut != -1 else q[over:]), "…"
        else:
            cut = q.rfind(" ", 0, len(q) - over)
            q, tail = (q[:cut] if cut != -1 else q[:len(q) - over]), "…"
    return lead + q + tail


NEGATION = re.compile(r"\b(not|no|without|never|lacks?|missing|isn'?t|doesn'?t|don'?t)\b[^.|\n]{0,40}$", re.I)


def find(pages, pattern, kinds=None, negation_guard=True, accept=None):
    """First match on a public page. negation_guard skips matches like
    'no audit log'. accept(match_text) can reject a match (e.g. off-domain)."""
    rx = re.compile(pattern, re.I)
    for pg in pages:
        if kinds and pg["kind"] not in kinds:
            continue
        for m in rx.finditer(pg["text"]):
            before = pg["text"][max(0, m.start() - 60):m.start()]
            if negation_guard and NEGATION.search(before):
                continue
            if accept and not accept(m.group(0)):
                continue
            quote = clean_quote(quote_around(pg["text"], m.start(), m.end()))
            return {"answer": True, "url": pg["url"], "quote": quote}
    return None


def root(host):
    return ".".join(host.lower().removeprefix("www.").split(".")[-2:])


def no():
    return {"answer": False, "url": None, "quote": None}


OSI = {"mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause", "gpl-3.0", "agpl-3.0",
       "lgpl-3.0", "mpl-2.0", "gpl-2.0", "unlicense", "isc"}

CHECKS = [
    ("pricing", "Transparency", "Is pricing published?"),
    ("free", "Transparency", "Is there a free trial or free tier?"),
    ("docs", "Transparency", "Are the docs public?"),
    ("customer", "Proof", "Is there a named customer or case study?"),
    ("result", "Proof", "Is a measured result published?"),
    ("updated", "Proof", "Updated in the last 30 days?"),
    ("no_training", "Data & trust", "States it doesn't train on customer data?"),
    ("security_page", "Data & trust", "Is there a security page?"),
    ("certification", "Data & trust", "Third-party certification (SOC 2 Type II / ISO 27001)?"),
    ("your_env", "Data & trust", "Can it run in your environment?"),
    ("audit_logs", "Control", "Audit logs or activity history?"),
    ("human_approval", "Control", "Human approval step before it acts?"),
]


def run_checks(agent, pages):
    repo = agent["repo"] or {}
    r = {}
    r["pricing"] = find(pages, r"\$\s?\d[\d,.]*\s*(/|per\s)\s*(mo\b|month|user|seat|yr\b|year|run|task)") or no()

    lic = ((repo.get("license") or {}).get("spdx_id") or "").lower()
    if lic in OSI:
        r["free"] = {"answer": True, "url": repo["html_url"],
                     "quote": f"Open-source license: {lic.upper()} (free to use)"}
    else:
        r["free"] = find(pages, r"free (tier|plan|trial)|start(ed)? for free|try (it )?for free|\bfree forever") or no()

    home_root = root(urlparse(repo.get("homepage") or "").netloc or "none.invalid")
    full = (repo.get("full_name") or "").lower()
    own = lambda u: ("raw.githubusercontent" not in u
                     and not re.search(r"\.(png|jpe?g|gif|svg|webp)$", u, re.I)
                     and (root(urlparse(u).netloc) == home_root
                          or f"github.com/{full}/" in u.lower()))
    r["docs"] = find(pages, r"https?://[^\s)\]\"'<>]*docs?[./][^\s)\]\"'<>]*|https?://[^\s)\]\"'<>]*/docs\b", accept=own) \
        or next(({"answer": True, "url": p["url"], "quote": "Public documentation page"}
                  for p in pages if p["kind"] == "docs"), None) or no()

    r["customer"] = find(pages, r"case stud(y|ies)|customer stor(y|ies)|trusted by (\d[\d,+k]*|teams|companies|engineers|developers) (at|from|like|including)|used in production (by|at)|used by (teams|companies) (at|like)") or no()

    r["result"] = find(pages, r"\b\d+(\.\d+)?\s?(%|x|×)\s+(faster|cheaper|less|fewer|more accurate|reduction|improvement|savings|cost reduction|higher)|(reduc|cut|sav)\w*\s[\w\s]{0,30}\bby\s\d+(\.\d+)?\s?(%|x)") or no()

    pushed = repo.get("pushed_at")
    if pushed and days_ago(pushed) <= 30:
        r["updated"] = {"answer": True, "url": repo["html_url"],
                        "quote": f"Last code push {pushed[:10]}"}
    else:
        r["updated"] = find(pages, rf"\b({NOW.strftime('%B')}|{(NOW - dt.timedelta(days=30)).strftime('%B')})\s\d{{1,2}},?\s{NOW.year}\b", kinds={"changelog"}) or no()

    r["no_training"] = find(pages, r"(do not|don'?t|never|will not|won'?t|does not|doesn'?t)\s+(use|train)[^.]{0,60}(train|your data|customer data|model)|zero data retention", negation_guard=False) or no()

    r["security_page"] = next(({"answer": True, "url": p["url"], "quote": "Public security page / policy"}
                               for p in pages if p["kind"] in {"security", "trust"}), None) or no()

    r["certification"] = find(pages, r"SOC\s?2\s?Type\s?(II|2)|ISO(/IEC)?\s?27001") or no()

    r["your_env"] = find(pages, r"self[- ]host|on[- ]prem|run (it )?locally|docker (run|compose)|helm (install|chart)|your own (cloud|infrastructure|vpc|servers)|\bin your (vpc|cloud)") or no()

    r["audit_logs"] = find(pages, r"audit (log|trail)s?|activity (log|history)|execution (log|history)|run history|observability (dashboard|for every)") or no()

    r["human_approval"] = find(pages, r"human[- ]in[- ]the[- ]loop|human (approval|review|confirmation)|requires? (your |user )?approval|approve (each|before|the)|confirm before") or no()
    return r


# ------------------------------------------------- how to get it (not scored)
# These answer "who resells it / referral only / hosted on / bring it to my
# platform". They are shown on each agent page but NEVER change the score, so
# a reseller relationship can't buy rank.
MARKETPLACES = ["AWS Marketplace", "Azure Marketplace", "Google Cloud Marketplace",
                "Salesforce AppExchange", "Microsoft AppSource", "Hugging Face Spaces",
                "Slack Marketplace", "Zapier"]
ECOSYSTEMS = [("MCP server", r"\bMCP server|model context protocol"),
              ("Claude Code", r"claude code"), ("Cursor", r"\bcursor\b"),
              ("Codex", r"\bcodex\b"), ("OpenAI Agents SDK", r"openai agents sdk"),
              ("LangChain / LangGraph", r"langchain|langgraph"), ("n8n", r"\bn8n\b"),
              ("Docker", r"\bdocker\b"), ("REST API", r"\b(rest|http) api\b|api reference"),
              ("Python package", r"pip install"), ("npm package", r"npm (i|install)\b|npx ")]


def get_it(pages, checks, repo):
    g = {}
    g["reseller_program"] = find(pages, r"\b(reseller|resell|partner program|channel partner|become a partner)\b") or no()
    g["referral_program"] = find(pages, r"referral program|affiliate program|refer a (friend|customer)|earn \d+% (commission|referral)") or no()
    g["hosted_by_maker"] = find(pages, r"(cloud|hosted|managed) (version|service|offering|plan)|sign up (for free|free)|get started (for )?free|start free trial") or no()
    g["marketplaces"] = [mk for mk in MARKETPLACES if find(pages, re.escape(mk))]
    g["bring_your_own"] = [name for name, rx in ECOSYSTEMS if find(pages, rx)]
    g["self_host"] = checks["your_env"]["answer"]
    g["open_source"] = ((repo.get("license") or {}).get("spdx_id") or "").lower() in OSI
    g["listed_managers"] = []   # providers who run it for customers; from claimed listings
    g["listed_resellers"] = []  # filled from claimed listings, never scraped
    return g


# --------------------------------------------------------- classification
INDUSTRIES = [  # first match wins, checked in this order
    ("Security", r"\b(security|pentest|vulnerab|threat|soc analyst|red team|malware)"),
    ("Healthcare", r"\b(health|clinical|medical|patient|ehr)\b"),
    ("Finance", r"\b(financ|trading|stock|accounting|invoice|bookkeep|crypto)"),
    ("Legal", r"\b(legal|contract|law firm|compliance)"),
    ("Education", r"\b(education|teacher|student|tutor|classroom|course)\b"),
    ("HR & recruiting", r"\b(recruit|hiring|candidate|onboarding|payroll|\bhr\b)"),
    ("E-commerce", r"\b(e-?commerce|shopify|storefront|product catalog|retail)"),
    ("Real estate", r"\b(real estate|property manag|tenant|landlord)"),
    ("Manufacturing & logistics", r"\b(manufactur|supply chain|logistics|warehouse|fleet)"),
    ("Sales & marketing", r"\b(sales|marketing|seo|lead|outreach|crm|ads?\b)"),
    ("Customer support", r"\b(customer support|helpdesk|support ticket|customer service)"),
    ("Software engineering", r"\b(cod(e|ing)|developer|ide\b|terminal|pull request|software engineer|devops|github)"),
    ("Research & data", r"\b(research|data analys|analytics|sql|scrap|search)"),
    ("Browser & computer use", r"\b(browser|computer use|desktop|web automation)"),
    ("Operations & IT", r"\b(sysadmin|kubernetes|incident|on-call|it operations|itsm)"),
]
FRAMEWORK_RX = r"\b(framework|sdk|library|toolkit|platform for building|build(ing)? (ai )?agents)\b"


def classify(text):
    for name, rx in INDUSTRIES:
        if re.search(rx, text, re.I):
            return name
    return "General purpose"


# -------------------------------------------------------------- momentum
def load_snapshot(days_back):
    p = OUT / "snapshots" / f"{(NOW - dt.timedelta(days=days_back)).date().isoformat()}.json"
    return json.loads(p.read_text()) if p.exists() else None


# --------------------------------------------------------------- archive
def write_history(rows):
    """Save today's ranking and rebuild data/history.json from every saved day.
    The site uses it for movement (rank up/down/new) and the archive views.
    Only real runs are stored; nothing is back-filled or estimated."""
    hdir = OUT / "history"
    hdir.mkdir(parents=True, exist_ok=True)
    (hdir / f"{TODAY}.json").write_text(json.dumps(
        [{"id": x["id"], "name": x["name"], "rank": x["rank"], "score": x["score"],
          "stars": x["stars"], "industry": x["industry"]} for x in rows], separators=(",", ":")))
    days = {}
    for f in sorted(hdir.glob("*.json")):
        days[f.stem] = json.loads(f.read_text())
    (OUT / "history.json").write_text(json.dumps(
        {"first": min(days), "latest": max(days), "days": days}, separators=(",", ":")))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=14)
    ap.add_argument("--min-sources", type=int, default=2)
    ap.add_argument("--board-size", type=int, default=50)
    a = ap.parse_args()

    mentions = src_github(a.window) + src_hackernews(a.window) + src_reddit(a.window)
    agents = merge(mentions)
    live_sources = [s for s, v in source_status.items() if v == "ok"]
    # Never demand more sources than are reachable on this run.
    min_sources = min(a.min_sources, max(1, len(live_sources)))

    snap7 = load_snapshot(7) or {}
    rows = []
    for k, ag in agents.items():
        srcs = sorted({m["source"] for m in ag["mentions"]})
        if len(srcs) < min_sources:
            continue
        repo = ag["repo"] or {}
        if repo:
            blob = " ".join([repo.get("name") or "", repo.get("description") or "", " ".join(repo.get("topics", []))])
            r = why_not_agent(blob) or (re.search(FRAMEWORK_RX, blob, re.I) and "describes itself as a framework")
            if r:
                reject(k, r, blob); continue
            if (repo.get("stargazers_count") or 0) < 200 and not repo.get("homepage"):
                reject(k, "under 200 stars and no homepage", blob); continue
            ag["_why"] = {"kind": "GitHub repo", "matched": AGENT_RX.search(blob).group(0).lower(),
                          "topics": [t for t in repo.get("topics", []) if "agent" in t][:3]}
        else:
            title = next((m["title"] for m in ag["mentions"]), "")
            ag["_why"] = {"kind": "product site", "matched": (AGENT_RX.search(title) or AGENT_RX.search("agent")).group(0).lower(), "topics": []}
        stars = repo.get("stargazers_count")
        age = max(1.0, days_ago(repo["created_at"])) if repo.get("created_at") else None
        if stars is not None and k in snap7:
            star_gain_7d, momentum_basis = stars - snap7[k], "measured"
        elif stars is not None and age:
            star_gain_7d, momentum_basis = round(stars / age * 7), "estimated"
        else:
            star_gain_7d, momentum_basis = None, None
        ag["_stars"], ag["_gain"], ag["_basis"] = stars, star_gain_7d, momentum_basis
        ag["_srcs"] = srcs
        ag["_buzz"] = sum(1 for m in ag["mentions"] if m["source"] != "github") + len(srcs)
        rows.append(ag)

    # Trending board = top N by (buzz, star gain). Deterministic.
    rows.sort(key=lambda x: (-x["_buzz"], -(x["_gain"] or 0), x["key"]))
    rows = rows[: a.board_size]

    out = []
    for i, ag in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {ag['key']}", file=sys.stderr)
        repo = ag["repo"] or {}
        pages = collect_pages(ag)
        hit = next((h for h in (NEFARIOUS_RX.search(pg["text"][:6000]) for pg in pages if pg["kind"] in ("readme", "home")) if h), None)
        if hit:
            reject(ag["key"], f"safety: {hit.group(0).lower()} on its own page"); continue
        checks = run_checks(ag, pages)
        meta = ag.get("_meta") or {}
        desc = repo.get("description") or meta.get("description") or next((m["title"] for m in ag["mentions"]), "")
        name = repo.get("name") or meta.get("name") or ag["key"].split(":", 1)[1]
        if not repo and not pages:
            reject(ag["key"], "homepage could not be read"); continue
        if not repo and meta.get("description"):
            r = why_not_agent(" ".join([meta.get("name", ""), meta["description"], next((m["title"] for m in ag["mentions"]), "")]))
            if r and NOT_AGENT_RX.search(meta["description"]):
                reject(ag["key"], "its own homepage " + r, meta["description"]); continue
        blob = " ".join([desc, " ".join(repo.get("topics", []))])
        out.append({
            "id": re.sub(r"[^a-z0-9]+", "-", ag["key"].split(":", 1)[1].lower()).strip("-"),
            "name": name, "owner": repo.get("owner", {}).get("login"),
            "description": desc, "url": repo.get("homepage") or repo.get("html_url")
            or ag["mentions"][0]["url"],
            "repo_url": repo.get("html_url"), "license": (repo.get("license") or {}).get("spdx_id"),
            "industry": classify(blob),
            "type": "Agent",
            "stars": ag["_stars"], "star_gain_7d": ag["_gain"], "momentum_basis": ag["_basis"],
            "sources": ag["_srcs"], "mentions_14d": ag["_buzz"],
            "mention_links": [{"source": m["source"], "title": m["title"], "url": m["url"],
                               "date": m["date"][:10]} for m in ag["mentions"]][:8],
            "pages_checked": [p["url"] for p in pages],
            "why": ag.get("_why"),
            "checks": checks, "score": sum(1 for c in checks.values() if c["answer"]),
            "get_it": get_it(pages, checks, repo),
        })

    # Final order: score, then buzz, then star gain, then name.
    out.sort(key=lambda x: (-x["score"], -x["mentions_14d"], -(x["star_gain_7d"] or 0), x["name"].lower()))
    for i, x in enumerate(out, 1):
        x["rank"] = i

    OUT.mkdir(exist_ok=True)
    (OUT / "snapshots").mkdir(exist_ok=True)
    (OUT / "agents.json").write_text(json.dumps(out, indent=1))
    (OUT / "snapshots" / f"{TODAY}.json").write_text(json.dumps(
        {f"gh:{x['owner']}/{x['name']}".lower(): x["stars"] for x in out if x["stars"] is not None}))
    write_history(out)
    (OUT / "rejects.json").write_text(json.dumps(
        {"run_at": NOW.isoformat(timespec="minutes"), "rejected": REJECTS}, indent=1))
    (OUT / "run.json").write_text(json.dumps({
        "rubric_version": RUBRIC_VERSION, "run_at": NOW.isoformat(timespec="minutes"),
        "window_days": a.window, "min_sources_requested": a.min_sources,
        "min_sources_applied": min_sources, "sources": source_status,
        "industries": [n for n, _ in INDUSTRIES] + ["General purpose"],
        "checks": [{"id": c, "group": g, "question": q} for c, g, q in CHECKS],
        "agents": len(out)}, indent=1))
    print(json.dumps(source_status), file=sys.stderr)


if __name__ == "__main__":
    main()
