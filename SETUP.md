# How valuedagentreseller.com is set up

The site is the `site/` folder: one static page plus three JSON files. Nothing is built.

- **Code and archive:** GitHub, `kaleigh-png/valued-agent-index`.
- **Hosting:** Vercel, project `valuedagentreseller`, serving `site/` (see `vercel.json`).
- **Daily update:** the GitHub Action in `.github/workflows/daily.yml` runs the scraper at
  10:17 UTC, copies fresh data into `site/`, and commits. Vercel watches the repo and
  redeploys on every push to `main`, so the commit is what publishes.

## Run the update by hand
GitHub → the repo → **Actions → Daily agent index → Run workflow**. The site updates a
minute or two after the commit lands.

## Change the page
Edit `site/index.html`, commit, push. Vercel redeploys automatically. To preview locally:

```
python3 -m http.server 8765 --directory site
```
then open http://localhost:8765.

## Domain
`valuedagentreseller.com` and `www` are attached to the Vercel project. DNS lives at the
registrar; the records Vercel expects are shown under the project's **Settings → Domains**.

## Not connected yet
- **User reviews** show "Reviews open soon." They need a small database before launch.
- **Claim, Manage it for me and Pulse forms** accept input but send nothing. A form
  service (Formspree, Tally) or a tiny Vercel function can collect them.
- **Reddit** often blocks GitHub's servers, so expect GitHub + Hacker News as sources.
  The job uses `--min-sources 1` to keep the list full; raise it to 2 later and bump the
  rubric version.
