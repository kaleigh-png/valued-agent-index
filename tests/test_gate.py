"""Fixed cases the listing gate must get right. Runs before every scrape.
If one of these flips, the daily job stops and the site keeps yesterday's list."""
import re, sys
from pathlib import Path
from urllib.parse import urlparse

src = (Path(__file__).resolve().parent.parent / "scraper.py").read_text()
ns = {"re": re, "urlparse": urlparse}
exec(src[src.index("AGENT_RX = "):src.index("SKIP_DOMAINS = ")], ns)
why_not_agent, is_product_url = ns["why_not_agent"], ns["is_product_url"]

AGENTS = [  # must be accepted
    "Open-source coding agent for your terminal",
    "Your personal trading agent",
    "AI assistant that triages your inbox and drafts replies",
    "Autonomous agent that files expense reports",
    "Clone any viral video with AI agents",
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
for t in NOT_AGENTS:
    if not why_not_agent(t): failed.append(f"should reject: {t!r}")
for u in PRODUCT_URLS:
    if not is_product_url(u): failed.append(f"should be a product url: {u}")
for u in ARTICLE_URLS:
    if is_product_url(u): failed.append(f"should be an article: {u}")
if failed:
    print("\n".join(failed)); sys.exit(1)
print(f"gate ok: {len(AGENTS)+len(NOT_AGENTS)+len(PRODUCT_URLS)+len(ARTICLE_URLS)} cases")
