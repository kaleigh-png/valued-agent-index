# Valued Agent Reseller

A neutral site for finding an AI agent by the job you want done, reading what it did for
people like you, and getting someone to run it. Operated by Brine AI, which is listed as a
provider like any other and gets no preference anywhere on the site.

## What's on it
- **Jobs.** The front page is a job box ("What job do you want off your plate?") over a
  fixed map of jobs grouped by function (`data/jobs.json`). Each agent is tagged with the
  jobs its own description names (`jobmap.py`). Typing a job filters the map; pressing
  "Find an agent" also records the job, anonymously, as a demand signal.
- **Agents.** The weekly list of most-discussed worker agents, each scored on twelve
  yes/no checks with a public quote for every Yes. "Most discussed" means exactly that.
- **Stories.** A job someone automated, the agent, how it runs, where, who helped, and who
  wrote it (customer, maker or consultant). A person approves each one on `/admin`.
  Anyone named can reply under it.
- **Providers.** `site/providers.json`. Help requests go only to the providers the person
  ticks. There is no default provider.
- **How it works.** Rules, checks, the public reject log and the corrections log.

## How the list is built
1. **Sources.** GitHub (agent topics plus job-themed searches), Hacker News, Reddit, Product
   Hunt (needs `PRODUCT_HUNT_TOKEN`) and `data/listings.json` (claimed listings approved by
   hand), over the last 14 days.
2. **Gate.** Fixed rules, no model anywhere: an agent names a job it does for someone
   (`JOB_RX`); developer tooling (`DEV_RX`), lists, frameworks, courses and infrastructure
   (`NOT_AGENT_RX`) are dropped; anything built to deceive or evade is blocked
   (`NEFARIOUS_RX`); articles count only as mentions. `tests/test_gate.py` runs 51 fixed
   cases before every scrape and stops the job if one flips. Every rejection goes to
   `data/rejects.json` with its reason and is published.
3. **Evidence.** README, SECURITY.md and the agent's own site pages, respecting robots.txt.
   Only agent and company data is stored, never people's names or handles.
4. **Checks and order.** Twelve yes/no checks; score, then mentions, then stars gained, then
   name. The same data always gives the same order.
5. **Weekly publish.** The scraper runs daily and writes a preview to `site/next/`; `/admin`
   shows what Monday would add or drop. Monday's run (or a manual run with "publish"
   ticked) copies the data into `site/`. `data/blocklist.json` pulls a listing with a
   published reason.

## Run it
```
pip install requests
export GITHUB_TOKEN=ghp_...        # free personal token; raises rate limits
python tests/test_gate.py
python scraper.py --min-sources 1  # writes data/agents.json, run.json, rejects.json, snapshots
python tag_jobs.py                 # re-tag a published list after editing data/jobs.json
```

## Storage and admin
Reviews, stories, job-box answers, help requests, claims, reports and corrections live in
an Upstash Redis store attached to the Vercel project, behind the functions in `api/`.
`/admin` (admin key = `ADMIN_KEY` on Vercel) approves stories, posts replies, publishes
corrections and shows every submission. See `SETUP.md`.

## Rules the code enforces
- No rank, routing or listing preference for Brine or anyone else.
- Help requests reach only the providers the person ticked.
- The job box keeps an email only when the person asks to be told when an agent exists.
- Stories and reviews never change a score and are labelled by who wrote them.
- Scraped text is escaped on the page; no model reads it; the scraper runs in GitHub
  Actions with a read-only GitHub token and no access to anything else.
