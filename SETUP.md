# How valuedagentreseller.com is set up

The site is the `site/` folder: one static page, a private editor page, and JSON files.
Nothing is built. Small functions in `api/` handle everything people send in.

- **Code and archive:** GitHub, `kaleigh-png/valued-agent-index`.
- **Hosting:** Vercel, project `valuedagentreseller`, serving `site/` (see `vercel.json`).
- **Daily scrape, weekly publish:** `.github/workflows/daily.yml` runs at 10:17 UTC every
  day. Every run writes a preview to `site/next/`. Monday's run copies the data into
  `site/`, which is what the public sees. Vercel redeploys on every push to `main`.

## Publish early, or pull something
- GitHub → the repo → **Actions → Agent index → Run workflow**, tick **publish**.
- To keep an agent off the list, add it to `data/blocklist.json`:
  `[{"id": "agent-id", "reason": "why"}]`. The reason is published in the reject log.
- `/admin` → "Next publish" shows what Monday would add or drop.

## The editor page
`https://valuedagentreseller.com/admin` with the admin key (`ADMIN_KEY` on the Vercel
project; a copy is in the untracked `.env.local`). It shows pending stories (approve,
reject, add an editor's note), published stories (post a reply, unpublish), error reports
and replies (publish a correction and close), jobs people named, help requests with the
providers they chose, claims, Pulse subscribers, and the reject log.

Rules for the editor:
- Approve a story only after confirming the sender's email. Every story shows who wrote it.
- Only people who ticked "tell me when an agent exists" left an email in the job box, and
  it is for that message only. Nobody else may be contacted.
- Help requests go to the providers the person ticked, and only them.

## Change the page
Edit `site/index.html`, commit, push. To preview locally with the API working:

```
vercel dev --listen 3333
```
then open http://localhost:3333. (`vercel env pull .env.local` first if the store vars are
missing.) For the static page alone: `python3 -m http.server 8765 --directory site`.

## Domain
`valuedagentreseller.com` and `www` are attached to the Vercel project. DNS lives at the
registrar; the records Vercel expects are shown under the project's **Settings → Domains**.

## Storage
An Upstash Redis store on the Vercel project (`vercel integration add upstash`). Keys:
`reviews` (hash), `stories` and `stories:pending` (hashes), `jobs:named`, `reports`,
`corrections`, `submissions:<kind>` (lists), `pulse:emails` (set).

## Providers
`site/providers.json`, one entry per provider: slug, name, kinds (`managed`, `host`),
`operator: true` for the company that runs the site, `description` (one line), `icp` (who they
work with, one line), `url`, `contact`, `jobs` (ids from `data/jobs.json`), `agents` (ids of
listed agents they run) and `agents_run` (`{name, who, url}` for agents not on the list). Every
provider page has the same sections and nothing else: who they are, jobs they take on, agents
they run, and approved stories that name them as the provider. Edit the file by hand after
confirming a claim; it is never scraped.

## The job map
`data/jobs.json`: functions, industries (tags) and jobs, each with a regex that tags agents
from their own description. Edit it, run `python tests/test_gate.py`, then `python
tag_jobs.py` to re-tag the published list. Bump `version` when you change it. Jobs people
type into the box that match nothing are the backlog for the next version.

## The two knobs that grow the list
- **Product Hunt.** Set `PRODUCT_HUNT_TOKEN` on the GitHub repo (Settings → Secrets →
  Actions). A developer token is free at https://www.producthunt.com/v2/oauth/applications.
- **Claimed listings.** Approve a maker or provider claim by adding it to
  `data/listings.json`: `[{"url": "https://...", "title": "Name: what it does", "repo": "owner/name"}]`.
  It then goes through the same gate and checks as everything else.

## Not connected yet
- **Pulse emails** are collected but nothing sends them. That needs an email service.
- **Story pages are hash routes** (`/#story-id`), so search engines don't index them yet.
- **Reddit** often blocks GitHub's servers, so expect GitHub + Hacker News as sources.
