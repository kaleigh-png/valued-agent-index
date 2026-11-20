"""Map an agent's own words to the jobs in data/jobs.json.

Used by the scraper on every run and by tag_jobs.py to re-tag a published
list after the map changes. Matching is plain regex on the agent's own
description, so the same words always give the same jobs.
"""
import json
import re
from pathlib import Path

JOBS_FILE = Path(__file__).parent / "data" / "jobs.json"
_cache = None


def load_jobs():
    global _cache
    if _cache is None:
        d = json.loads(JOBS_FILE.read_text())
        for j in d["jobs"]:
            j["_rx"] = re.compile(r"\b(?:" + j["match"] + r")\b", re.I)
        _cache = d
    return _cache


def jobs_for(text, limit=3):
    """Job ids whose pattern appears in the text, earliest match first."""
    hits = []
    for j in load_jobs()["jobs"]:
        m = j["_rx"].search(text or "")
        if m:
            hits.append((m.start(), j["id"]))
    hits.sort()
    return [jid for _, jid in hits[:limit]]


def public_map():
    """The map without compiled patterns, for site/jobs.json."""
    d = load_jobs()
    return {"version": d["version"], "industries": d["industries"], "functions": d["functions"],
            "jobs": [{k: v for k, v in j.items() if not k.startswith("_")} for j in d["jobs"]]}
