"""Fixed cases the listing gate must get right. Runs before every scrape.
If one of these flips, the daily job stops and the site keeps yesterday's list."""
import re, sys
from pathlib import Path
from urllib.parse import urlparse

src = (Path(__file__).resolve().parent.parent / "scraper.py").read_text()
ns = {"re": re, "urlparse": urlparse}
exec(src[src.index("AGENT_RX = "):src.index("SKIP_DOMAINS = ")], ns)
why_not_agent, is_product_url, job_of = ns["why_not_agent"], ns["is_product_url"], ns["job_of"]

AGENTS = [  # must be accepted, and each names a job
    "Your personal trading agent",
    "AI assistant that triages your inbox and drafts replies",
    "Autonomous agent that files expense reports",
    "Agent that screens resumes against your hiring criteria",
    "An AI agent that drafts proposals from your past bids",
    "Assistant that plans meals and orders groceries every week",
    "Agent that answers customer support tickets in your help desk",
    "An on-device AI agent for Android that operates apps and the web to get things done",
    "Open source personal agent with its own computer. It chases invoices and books travel.",
]
DEV_TOOLS = [  # agents, but for developers: left out
    "Open-source coding agent for your terminal",
    "Coding agent with the IDE wired in",
    "Run agents like Hermes and Deep Agents more securely, in a sandbox",
    "A persistent self-improving workspace for development work",
]
NOT_AGENTS = [  # must be rejected
    "Awesome list of AI agents",
    "Agent framework for building agents",
    "Skills for Claude Code agents",
    "Microsoft's agent-framework PyPI package Compromised with Credential Stealer",
    "ComplexDiscovery is a technology blog highlighting legal discovery insights",
    "A sourced and ranked index of 975 agentic coding tools",
    "AI gateway: one endpoint, 375 providers",
    "The runtime your coding agents live on",
    "Best headless browser for AI agents",
    "Beginner tutorial on agent harness engineering, from 0 to 1",
    "Modern web guidance for developers",
    "Stealth Chromium that passes every bot detection test, built for AI agents",
    "Jailbreak any model with this autonomous agent",
    "Agent that posts fake reviews at scale",
    "Computer use CLI for AI agents",
    "One shared memory for every coding agent on your team",
    "Infrastructure for continually self-improving agents",
    "Execution rails for agents. Equip your AI to work with sensitive enterprise data",
    "AI autonomous penetration testing system",
    "Source-available agent platform for enterprises, wire up any agent",
    "The Open Source ERP Built for Agents",
    "European Business Magazine delivers the latest European business news and audit insight",
    "HELP WANTED: AI AGENTS. Real bounties, real money, every payout sends a receipt",
]
PRODUCT_URLS = ["https://tinyfish.ai", "https://github.com/foo/bar", "https://example.com/?utm=hn"]
ARTICLE_URLS = [
    "https://socket.dev/blog/microsoft-agent-framework-compromised",
    "https://www.anthropic.com/news/agent-memory",
    "https://github.com/foo/bar/issues/3",
    "https://example.com/2026/11/post",
    "https://news.site.com/story/harvard-researchers-find-ai-coding-agents-shifted-the-bottleneck",
]

failed = []
for t in AGENTS:
    r = why_not_agent(t)
    if r: failed.append(f"should accept: {t!r} ({r})")
    if not job_of(t): failed.append(f"should name a job: {t!r}")
for t in DEV_TOOLS:
    r = why_not_agent(t)
    if not r or not r.startswith("developer tooling"): failed.append(f"should reject as developer tooling: {t!r}")
for t in NOT_AGENTS:
    if not why_not_agent(t): failed.append(f"should reject: {t!r}")
for u in PRODUCT_URLS:
    if not is_product_url(u): failed.append(f"should be a product url: {u}")
for u in ARTICLE_URLS:
    if is_product_url(u): failed.append(f"should be an article: {u}")
# The job map: every pattern compiles, ids are unique, every function is declared,
# and a few plain sentences land on the job a person would expect.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobmap import load_jobs, jobs_for
JM = load_jobs()
ids = [j["id"] for j in JM["jobs"]]
if len(ids) != len(set(ids)): failed.append("job map: duplicate ids")
for j in JM["jobs"]:
    if j["function"] not in JM["functions"]: failed.append(f"job map: {j['id']} has unknown function {j['function']!r}")
JOB_CASES = [
    ("It chases overdue invoices and posts replies to QuickBooks", "invoices"),
    ("Screens resumes against your hiring criteria", "screen-applicants"),
    ("Finds RFPs on SAM.gov and tracks amendments", "rfps"),
    ("Answers customer support tickets in your help desk", "support-tickets"),
    ("Plans meals and orders groceries every week", "food"),
    ("Self-hosted CRM with native AI agents for teams that sell by chat", "crm"),
    ("Single-tenant customer service platform", "support-tickets"),
]
for text, want in JOB_CASES:
    got = jobs_for(text)
    if want not in got: failed.append(f"job map: {text!r} should map to {want}, got {got}")
if jobs_for("Single-tenant customer service platform") and "property" in jobs_for("Single-tenant customer service platform"):
    failed.append("job map: 'single-tenant' must not read as property management")

if failed:
    print("\n".join(failed)); sys.exit(1)
print(f"gate ok: {len(AGENTS)+len(DEV_TOOLS)+len(NOT_AGENTS)+len(PRODUCT_URLS)+len(ARTICLE_URLS)+len(JOB_CASES)} cases")
