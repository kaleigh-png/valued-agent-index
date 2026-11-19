# Valued Agent Reseller: trending agent index (prototype)

## What it does
1. **Finds trending agents.** It checks GitHub (agent repos ranked by stars gained), Hacker News and Reddit over the last 14 days. With the default `--min-sources 2`, an agent has to show up in at least 2 sources to be listed.
2. **Collects public evidence.** That means the README and SECURITY.md, plus the agent's own site: home, /pricing, /security, /trust, /privacy, /docs, /customers and /changelog. It respects robots.txt.
3. **Scores 12 yes/no checks with fixed rules (no AI).** A Yes needs a matching quote on a public page, and the quote and URL are saved. Unknown counts as No.
4. **Orders the list.** Score first, then mentions, then stars gained, then name A to Z. The same data always produces the same order.
5. **Finds "How to get it" details, which are not scored:** reseller or partner program, referral program, hosted version, marketplaces, and how to bring it to your platform (MCP, Claude Code, Docker, API…). `listed_resellers` is filled from claimed listings, never scraped.

## Run it
```
pip install requests
export GITHUB_TOKEN=ghp_...        # free personal token; raises rate limits
python scraper.py                  # writes data/agents.json, data/run.json, data/snapshots/
```
Schedule it daily with cron or a GitHub Action. After 7 days of snapshots, momentum changes from an estimate (stars ÷ repo age) to the real 7-day star gain.

## Archive
Each run saves `data/history/<date>.json` and rebuilds `data/history.json`. The site uses it for movement arrows (vs. 7 days ago) and the Last week / 1 month / 6 months / 1 year views. Tabs unlock automatically as history builds up. Nothing is back-filled, so keep the daily run going.

## Publish to the site
The `site/` folder is hosted on Vercel and attached to valuedagentreseller.com. The daily
GitHub Action copies `data/agents.json`, `data/run.json` and `data/history.json` into
`site/` and commits; Vercel redeploys on every push to `main`. See `SETUP.md`.

## Known limits (v1.0)
- Checks match text. Unusual wording can read as No, and an aside can occasionally read as Yes (example: "an audit log is not provided yet" in a long sentence). Review the top 10 by hand before each publish, and let claimed listings fix the rest.
- The first run came from a sandbox where only GitHub was reachable, so pricing, security-page and certification checks are low. They fill in once vendor sites are reachable.
- Product Hunt needs an API token. Add it as a fourth source when you have one.
- Industry tags use keywords and the first match wins. Change the list in `INDUSTRIES`.
- The forms (claim a listing, Agent Pulse) are not connected yet.
