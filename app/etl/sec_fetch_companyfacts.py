"""EDGAR companyfacts fetch + annual USD extractor.

Why this exists
---------------
`ops.run_backfill` calls `fetch_companyfacts(cik)` then
`extract_annual_usd_facts(companyfacts, tag)` to pull annual values for a
preferred XBRL tag (e.g., revenue, net income). If you saw
"wrote 0 year(s)", the usual culprit is **CIK not zero-padded to 10 digits**
(which yields a 404 on the SEC endpoint) or a tag/unit mismatch.

This module fixes both:
- Correctly formats the URL with `CIK{cik:010d}.json`.
- Extracts annual values from the preferred unit (USD for money; shares for
  share counts), filtering to fiscal-year (`fp == 'FY'`).

Usage
-----
from app.etl.sec_fetch_companyfacts import fetch_companyfacts, extract_annual_usd_facts

cf = fetch_companyfacts(320193)  # Apple Inc.
series = extract_annual_usd_facts(cf, 'SalesRevenueNet')

Implementation notes
--------------------
- Be polite: send a descriptive User-Agent (configured in .env via
  SEC_USER_AGENT). The requests here use a Session with that header.
- We add simple retry/backoff on transient HTTP codes (429/5xx).
- For each tag's `units`, we pick the first matching unit from `UNIT_PRIORITY`.
- We only keep entries where `fp == 'FY'` and `fy` exists (annual statements).
- If multiple entries share the same year, we keep the **latest** by `end`.
"""
from __future__ import annotations

from typing import Dict, List, Any, Optional
from http.client import RemoteDisconnected
import time
import datetime as dt
import math

import requests
from app.core.config import settings
from requests.exceptions import ConnectionError, ReadTimeout, ChunkedEncodingError

# -----------------------------
# HTTP session with SEC User-Agent
# -----------------------------
_session = requests.Session()
_session.headers.update({
    "User-Agent": settings.sec_user_agent or "watchTower/0.1 (unknown@unknown)",
    "Accept": "application/json",
})

BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Preferred unit per tag class; fallback order if unknown
UNIT_PRIORITY = {
    "_money": ["USD"],
    "_shares": ["shares"],
}

# If you want per-tag unit preferences, add here (optional overrides)
UNIT_BY_TAG = {
    # Shares outstanding / diluted shares
    "WeightedAverageNumberOfDilutedSharesOutstanding": ["shares"],
    "WeightedAverageNumberOfSharesOutstandingDiluted": ["shares"],
}

# -----------------------------
# Fetcher with retry/backoff
# -----------------------------

# add near the top with other imports
import time
from http.client import RemoteDisconnected
import urllib3
import requests
from requests.exceptions import ConnectionError, ReadTimeout, ChunkedEncodingError

def fetch_companyfacts(cik: int, max_retries: int = 4, timeout: int = 30) -> Dict[str, Any]:
    """Download companyfacts JSON for a CIK (CIK will be zero-padded).
    Returns {} on hard 404; retries on transient network errors and 5xx/429.
    """
    url = BASE_URL.format(cik=int(cik))  # zero-pads via :010d
    delay = 0.5  # base backoff
    for attempt in range(max_retries + 1):
        try:
            r = _session.get(url, timeout=timeout)
        except (ConnectionError, ReadTimeout, ChunkedEncodingError,
                urllib3.exceptions.ProtocolError, RemoteDisconnected) as e:
            # transient connection issue — backoff and retry
            time.sleep(delay)
            delay = min(delay * 2, 8.0)
            continue

        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return {}  # bad/unknown CIK
        if r.status_code in (429, 500, 502, 503, 504):
            ra = r.headers.get("Retry-After")
            sleep_s = float(ra) if ra and ra.isdigit() else delay
            time.sleep(sleep_s)
            delay = min(delay * 2, 8.0)
            continue

        # other codes → raise
        r.raise_for_status()

    # give up
    return {}


# -----------------------------
# Extraction helpers
# -----------------------------

def _pick_unit(tag: str, units: Dict[str, List[dict]]) -> Optional[str]:
    """Choose the best unit key for a tag from the available units dict."""
    # explicit per-tag override first
    if tag in UNIT_BY_TAG:
        for u in UNIT_BY_TAG[tag]:
            if u in units:
                return u
    # heuristic: share-like tags
    share_like = ("Share" in tag) or ("Shares" in tag) or ("shares" in tag)
    pri = UNIT_PRIORITY["_shares" if share_like else "_money"]
    for u in pri:
        if u in units:
            return u
    # fallback: pick any unit with numeric-like values
    for u, arr in units.items():
        if isinstance(arr, list) and arr:
            return u
    return None


def extract_annual_usd_facts(cf: Dict[str, Any], tag: str) -> List[dict]:
    """Extract annual observations for a given us-gaap tag.

    Returns a list of dicts: [{"fy": int, "val": float, "end": "YYYY-MM-DD"}, ...]
    Sorted ascending by fiscal year.
    """
    if not cf or "facts" not in cf:
        return []

    usgaap = cf.get("facts", {}).get("us-gaap", {})
    node = usgaap.get(tag)
    if not node:
        return []

    units = node.get("units", {})
    unit_key = _pick_unit(tag, units)
    if not unit_key or unit_key not in units:
        return []

    out: Dict[int, dict] = {}
    for obs in units[unit_key]:
        try:
            fy = int(obs.get("fy")) if obs.get("fy") is not None else None
            fp = obs.get("fp")
            end = obs.get("end")
            val = obs.get("val")
        except Exception:
            continue
        if fy is None or fp != "FY" or val is None:
            continue
        # keep the latest by report end date for a given fiscal year
        prev = out.get(fy)
        if (prev is None) or (end and prev.get("end") and end > prev["end"]):
            out[fy] = {"fy": fy, "val": float(val), "end": end}

    # return sorted by year
    return [out[y] for y in sorted(out.keys())]


# -----------------------------
# (Optional) quick tag discovery helper for debugging
# -----------------------------

def list_available_tags(cf: Dict[str, Any]) -> List[str]:
    """List available us-gaap tag names present in companyfacts."""
    return sorted((cf.get("facts", {}) or {}).get("us-gaap", {}).keys())
