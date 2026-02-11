import os
import json
import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sharp Golf")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Config ───────────────────────────────────────────────────
DG_API_KEY = os.environ.get("DG_API_KEY", "")
DG_BASE = "https://feeds.datagolf.com"

# Simple in-memory cache (key -> {data, timestamp})
_cache = {}
CACHE_TTL = timedelta(minutes=15)


def get_cached(key):
    if key in _cache:
        entry = _cache[key]
        if datetime.now() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]
    return None


def set_cached(key, data):
    _cache[key] = {"data": data, "timestamp": datetime.now()}


async def dg_fetch(endpoint: str, params: dict = None):
    """Fetch from Data Golf API with caching."""
    if not DG_API_KEY:
        raise HTTPException(status_code=500, detail="DG_API_KEY not configured")

    params = params or {}
    params["key"] = DG_API_KEY
    params["file_format"] = "json"

    cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    url = f"{DG_BASE}/{endpoint}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Data Golf API error: {resp.text[:200]}"
            )
        data = resp.json()
        set_cached(cache_key, data)
        return data


# ─── API Routes ───────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "api_key_set": bool(DG_API_KEY)}


@app.get("/api/field")
async def get_field(tour: str = "pga"):
    """Get this week's field with tee times and DFS salaries."""
    return await dg_fetch("field-updates", {"tour": tour})


@app.get("/api/schedule")
async def get_schedule(tour: str = "all", season: str = "2026"):
    """Get tour schedule."""
    return await dg_fetch("get-schedule", {"tour": tour, "season": season})


@app.get("/api/rankings")
async def get_rankings():
    """Get DG top 500 rankings."""
    return await dg_fetch("preds/get-dg-rankings")


@app.get("/api/predictions")
async def get_predictions(tour: str = "pga"):
    """Get pre-tournament predictions with probabilities."""
    return await dg_fetch("preds/pre-tournament", {
        "tour": tour,
        "dead_heat": "yes",
        "odds_format": "decimal",
    })


@app.get("/api/decompositions")
async def get_decompositions(tour: str = "pga"):
    """Get player skill decompositions for this week."""
    return await dg_fetch("preds/player-decompositions", {"tour": tour})


@app.get("/api/skill-ratings")
async def get_skill_ratings():
    """Get player skill ratings."""
    return await dg_fetch("preds/skill-ratings", {"display": "value"})


@app.get("/api/approach-skill")
async def get_approach_skill(period: str = "l24"):
    """Get detailed approach skill data."""
    return await dg_fetch("preds/approach-skill", {"period": period})


@app.get("/api/outrights")
async def get_outrights(tour: str = "pga", market: str = "win"):
    """Get outright odds from all sportsbooks vs DG model."""
    return await dg_fetch("betting-tools/outrights", {
        "tour": tour,
        "market": market,
        "odds_format": "decimal",
    })


@app.get("/api/matchups")
async def get_matchups(tour: str = "pga", market: str = "tournament_matchups"):
    """Get matchup & 3-ball odds."""
    return await dg_fetch("betting-tools/matchups", {
        "tour": tour,
        "market": market,
        "odds_format": "decimal",
    })


@app.get("/api/matchups-all")
async def get_matchups_all(tour: str = "pga"):
    """Get DG matchup odds for all pairings."""
    return await dg_fetch("betting-tools/matchups-all-pairings", {
        "tour": tour,
        "odds_format": "decimal",
    })


@app.get("/api/live")
async def get_live(tour: str = "pga"):
    """Get live in-play predictions."""
    return await dg_fetch("preds/in-play", {
        "tour": tour,
        "dead_heat": "yes",
        "odds_format": "decimal",
    })


@app.get("/api/live-stats")
async def get_live_stats(round: str = "event_avg"):
    """Get live tournament stats."""
    return await dg_fetch("preds/live-tournament-stats", {
        "stats": "sg_putt,sg_arg,sg_app,sg_ott,sg_t2g,sg_total,distance,accuracy,gir,prox_fw,scrambling",
        "round": round,
        "display": "value",
    })


@app.get("/api/live-hole-stats")
async def get_live_hole_stats(tour: str = "pga"):
    """Get live hole scoring distributions."""
    return await dg_fetch("preds/live-hole-stats", {"tour": tour})


@app.get("/api/historical-outrights")
async def get_historical_outrights(
    tour: str = "pga",
    event_id: str = "all",
    year: str = "2025",
    market: str = "win",
    book: str = "draftkings",
):
    """Get historical outright odds."""
    return await dg_fetch("historical-odds/outrights", {
        "tour": tour,
        "event_id": event_id,
        "year": year,
        "market": market,
        "book": book,
        "odds_format": "decimal",
    })


@app.get("/api/historical-matchups")
async def get_historical_matchups(
    tour: str = "pga",
    event_id: str = "all",
    year: str = "2025",
    book: str = "draftkings",
):
    """Get historical matchup odds."""
    return await dg_fetch("historical-odds/matchups", {
        "tour": tour,
        "event_id": event_id,
        "year": year,
        "book": book,
        "odds_format": "decimal",
    })


@app.get("/api/players")
async def get_players():
    """Get player list with IDs."""
    return await dg_fetch("get-player-list")


# ─── Serve Frontend ──────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_app():
    return FileResponse("static/index.html")
