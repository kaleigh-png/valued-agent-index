"""Re-tag a published agents.json with jobs from data/jobs.json and refresh
site/jobs.json. Run after editing the job map so the live list matches it
without waiting for the next scrape.

    python tag_jobs.py            # tags data/agents.json and site/agents.json
"""
import json
import sys
from pathlib import Path

from jobmap import jobs_for, public_map

ROOT = Path(__file__).parent


def own_text(a):
    return " ".join([a.get("name") or "", a.get("description") or "",
                     ((a.get("why") or {}).get("job") or ""),
                     " ".join(m.get("title", "") for m in (a.get("mention_links") or [])[:3])])


def tag(path):
    if not path.exists():
        return 0
    rows = json.loads(path.read_text())
    for a in rows:
        a["jobs"] = jobs_for(own_text(a))
    path.write_text(json.dumps(rows, indent=1))
    return sum(1 for a in rows if a["jobs"])


if __name__ == "__main__":
    for p in [ROOT / "data" / "agents.json", ROOT / "site" / "agents.json", ROOT / "site" / "next" / "agents.json"]:
        n = tag(p)
        if p.exists():
            print(f"{p.relative_to(ROOT)}: {n} agents tagged", file=sys.stderr)
    (ROOT / "site" / "jobs.json").write_text(json.dumps(public_map(), indent=1))
    print("site/jobs.json written", file=sys.stderr)
