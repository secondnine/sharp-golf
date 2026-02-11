# Sharp Golf — Beat the Books

A golf betting dashboard that uses the Data Golf API to find value bets across 11 sportsbooks.

## Features

- **Value Finder** — Compare DG model probabilities vs. sportsbook odds across Win, Top 5, Top 10, Top 20, Make Cut, and First Round Leader markets
- **Matchups** — Head-to-head tournament matchup value analysis
- **Skill Breakdown** — Strokes gained decomposition with course fit scores
- **Bet Tracker** — Log bets, mark W/L, track P/L and ROI over time
- Covers PGA Tour, DP World Tour, and Korn Ferry Tour
- Auto-refreshes every 15 minutes
- Mobile-friendly

## Deploy to Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select this repo
4. Add environment variable: `DG_API_KEY` = your Data Golf API key
5. Deploy — Railway will auto-detect Python and install dependencies

## Run Locally

```bash
pip install -r requirements.txt
export DG_API_KEY=your_api_key_here
uvicorn main:app --reload
```

Then open http://localhost:8000

## Tech Stack

- **Backend:** Python / FastAPI
- **Frontend:** Vanilla HTML/CSS/JS (no build step needed)
- **Data:** Data Golf API (Scratch Plus subscription required)
- **Hosting:** Railway

## Data Golf API Key

You need a [Data Golf Scratch Plus](https://datagolf.com/subscribe) subscription to get API access.
