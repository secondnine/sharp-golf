import os
import json
import asyncio
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


# ─── Top 20 Picks ────────────────────────────────────────────

SPORTSBOOKS = [
    "draftkings", "fanduel", "betmgm", "caesars", "pinnacle",
    "bet365", "bovada", "circa", "betway", "williamhill", "betonline",
    "betcris", "skybet", "sportsbook", "unibet", "corale", "pointsbet",
]


def dec_to_american(dec: float) -> str | None:
    if not dec or dec <= 1:
        return None
    if dec >= 2:
        return f"+{round((dec - 1) * 100)}"
    return f"-{round(100 / (dec - 1))}"


async def safe_dg_fetch(endpoint: str, params: dict) -> dict:
    try:
        return await dg_fetch(endpoint, params)
    except Exception:
        return {}


@app.get("/api/top20-picks")
async def get_top20_picks(tour: str = "pga"):
    """Top 20 pick recommendations scored by Floor Score system."""
    predictions, outrights, decomps = await asyncio.gather(
        safe_dg_fetch("preds/pre-tournament", {"tour": tour, "odds_format": "decimal"}),
        safe_dg_fetch("betting-tools/outrights", {"tour": tour, "market": "top_20", "odds_format": "decimal"}),
        safe_dg_fetch("preds/player-decompositions", {"tour": tour}),
    )

    event_name = outrights.get("event_name", "") or predictions.get("event_name", "")

    # 1. Predictions lookup: dg_id -> top_20 probability
    pred_lookup: dict[int, float] = {}
    pred_list = predictions.get("baseline_history_fit", predictions.get("baseline", []))
    if not isinstance(pred_list, list):
        pred_list = []
    for p in pred_list:
        dg_id = p.get("dg_id")
        t20 = p.get("top_20", 0)
        if dg_id and t20 and t20 > 0:
            pred_lookup[dg_id] = 1.0 / t20  # decimal odds -> probability

    # 2. Outrights lookup: dg_id -> best sportsbook odds
    odds_list = outrights.get("odds", [])
    if not isinstance(odds_list, list):
        odds_list = []
    odds_lookup: dict[int, dict] = {}
    for p in odds_list:
        dg_id = p.get("dg_id")
        if not dg_id:
            continue
        best_dec = 0.0
        best_book = ""
        all_odds: dict[str, str] = {}
        for book in SPORTSBOOKS:
            val = p.get(book)
            if val and isinstance(val, (int, float)) and val > 1:
                am = dec_to_american(val)
                if am:
                    all_odds[book] = am
                if val > best_dec:
                    best_dec = val
                    best_book = book
        if best_dec > 0:
            odds_lookup[dg_id] = {
                "best_dec": best_dec,
                "best_american": dec_to_american(best_dec),
                "best_book": best_book,
                "all_odds": all_odds,
                "player_name": p.get("player_name", ""),
            }

    # 3. Decompositions lookup: dg_id -> skill data
    decomps_list = decomps.get("players", [])
    if not isinstance(decomps_list, list):
        decomps_list = []
    decomps_lookup: dict[int, dict] = {}
    for p in decomps_list:
        dg_id = p.get("dg_id")
        if dg_id:
            decomps_lookup[dg_id] = p

    # 4. Merge and filter by odds range (-200 to +500 = decimal 1.5 to 6.0)
    merged = []
    for dg_id, odds in odds_lookup.items():
        if odds["best_dec"] < 1.5 or odds["best_dec"] > 6.0:
            continue
        decomp = decomps_lookup.get(dg_id, {})
        merged.append({
            "dg_id": dg_id,
            "player_name": odds.get("player_name", decomp.get("player_name", "Unknown")),
            "dg_top20_prob": pred_lookup.get(dg_id, 0),
            "best_odds": odds["best_american"],
            "best_odds_dec": odds["best_dec"],
            "best_book": odds["best_book"],
            "all_odds": odds["all_odds"],
            "course_fit": (decomp.get("total_fit_adjustment") or 0) + (decomp.get("total_course_history_adjustment") or 0),
            "sg_short_game": decomp.get("cf_short_comp") or 0,
            "sg_approach": decomp.get("cf_approach_comp") or 0,
            "sg_total_predicted": decomp.get("final_pred") or decomp.get("baseline_pred") or 0,
            "std_deviation": decomp.get("std_deviation") or 3.0,
        })

    if not merged:
        return {"event_name": event_name, "picks": []}

    # 5. Normalize each factor to 0-100
    def normalize(vals: list[float]) -> list[float]:
        mn, mx = min(vals), max(vals)
        if mx == mn:
            return [50.0] * len(vals)
        return [(v - mn) / (mx - mn) * 100 for v in vals]

    n_prob = normalize([r["dg_top20_prob"] for r in merged])
    n_fit = normalize([r["course_fit"] for r in merged])
    n_short = normalize([r["sg_short_game"] for r in merged])
    n_app = normalize([r["sg_approach"] for r in merged])
    n_sg = normalize([r["sg_total_predicted"] for r in merged])
    n_form = normalize([r["sg_total_predicted"] / max(r["std_deviation"], 0.5) for r in merged])

    # 6. Calculate Floor Score and build response
    picks = []
    for i, raw in enumerate(merged):
        factors = {
            "model": round(n_prob[i], 1),
            "course": round(n_fit[i], 1),
            "short_game": round(n_short[i], 1),
            "approach": round(n_app[i], 1),
            "form": round(n_form[i], 1),
            "overall": round(n_sg[i], 1),
        }
        # Weights derived from logistic regression on 2,997 player-events
        # across 44 PGA Tour events (Feb 2025 - Feb 2026)
        fs = (
            factors["model"] * 0.269
            + factors["course"] * 0.133
            + factors["short_game"] * 0.059
            + factors["approach"] * 0.056
            + factors["form"] * 0.150
            + factors["overall"] * 0.333
        )
        if fs >= 85:
            conf = "LOCK"
        elif fs >= 75:
            conf = "HIGH"
        elif fs >= 65:
            conf = "SOLID"
        else:
            conf = "LEAN"

        picks.append({
            "player_name": raw["player_name"],
            "dg_id": raw["dg_id"],
            "floor_score": round(fs, 1),
            "dg_top20_prob": round(raw["dg_top20_prob"], 4),
            "best_odds": raw["best_odds"],
            "best_odds_dec": round(raw["best_odds_dec"], 4),
            "best_book": raw["best_book"],
            "all_odds": raw["all_odds"],
            "course_fit": round(raw["course_fit"], 4),
            "sg_short_game": round(raw["sg_short_game"], 4),
            "sg_approach": round(raw["sg_approach"], 4),
            "sg_total_predicted": round(raw["sg_total_predicted"], 4),
            "confidence": conf,
            "factors": factors,
        })

    picks.sort(key=lambda x: x["floor_score"], reverse=True)
    return {"event_name": event_name, "picks": picks[:30]}


# ─── Serve Frontend ──────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_app():
    return FileResponse("static/index.html")
