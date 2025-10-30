from fastapi import FastAPI, HTTPException, Query
import requests
import difflib
import os

app = FastAPI()

SEARCH_URL = "https://api.betterttv.net/3/emotes/shared/search"


def _score_name(candidate: str, needle: str) -> float:
    """Higher score = better match."""
    candidate_l = candidate.lower()
    needle_l = needle.lower()
    if candidate_l == needle_l:
        return 1.0  # exact match
    if candidate_l.startswith(needle_l):
        return 0.95  # strong prefix match
    return difflib.SequenceMatcher(None, candidate_l, needle_l).ratio()


def get_bttv_emote_urls(name: str, size: str = "3x", search_limit: int = 50, max_results: int = 5):
    """Return top BTTV emote URLs matching a name."""
    if len(name.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters long.")

    params = {"query": name, "offset": 0, "limit": max(1, min(search_limit, 100))}
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"BTTV API request failed: {e}")

    results = resp.json()
    if not results:
        raise HTTPException(status_code=404, detail=f"No BetterTTV emotes found for '{name}'")

    # Sort by similarity score
    scored = sorted(
        results,
        key=lambda item: _score_name(item.get("code") or item.get("name") or "", name),
        reverse=True,
    )

    emote_urls = []
    for item in scored[:max_results]:
        emote_id = item.get("id") or item.get("emote", {}).get("id")
        if not emote_id:
            continue
        emote_urls.append({
            "name": item.get("code") or item.get("name"),
            "url": f"https://cdn.betterttv.net/emote/{emote_id}/{size}"
        })

    return emote_urls


@app.get("/healthz")
def health_check():
    """Lightweight endpoint for uptime checks."""
    return {"ok": True}


@app.get("/bttv")
def search_bttv_emotes(
    q: str = Query(..., min_length=3, description="Emote name (min 3 characters)"),
    limit: int = Query(5, ge=1, le=50, description="Number of emote URLs to return"),
    size: str = Query("3x", pattern="^(1x|2x|3x)$", description="Emote image size"),
):
    """Search BetterTTV emotes and return top matches."""
    return get_bttv_emote_urls(q, size=size, max_results=limit)
