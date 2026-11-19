# GitHub Actions paper-trading starter

This is a small educational paper simulator, not a profitable or validated strategy and not a full port of the original Claude skill. It uses Yahoo Finance through `yfinance`, which is unofficial, may be delayed/incomplete, and is not suitable for execution decisions.

## What it does
- Runs on a GitHub Actions schedule (nominally every 5 minutes during a broad UTC window covering the US session; GitHub can delay scheduled jobs).
- Checks PANW, BRBR and WMT for a simple 15-minute opening-range breakout.
- Simulates fractional-share entries/exits, a 2R target and stop at the opening-range low.
- Stores simulated state and a CSV trade ledger in `data/`.
- Cannot connect to a broker or place real orders.

## Important limitations
- This is not AI and does not guarantee profitability.
- Yahoo Finance intraday data can be delayed, missing, revised or rate-limited. The bot skips when data is unavailable.
- GitHub Actions is not a real-time trading host; schedules can be delayed and jobs can fail.
- GitHub scheduled jobs can be delayed or skipped. If the end-of-day run is missed, an open simulated position may carry into the next session; this is a learning demo, not a production-grade simulator.
- Do not use the results to trade real money. No broker credentials or API keys are needed.

## Deploy from an iPhone
1. Create a new **public** GitHub repository (no personal details in the repo name).
2. Upload the contents of this ZIP directly to the repository root. Make sure `.github/workflows/paper-bot.yml` stays in that exact path (the `.github` folder may be hidden in some mobile file pickers).
3. Open the repository's **Actions** tab and enable workflows if GitHub prompts you.
4. Open **Paper trading bot** → **Run workflow** to test a manual run.
5. View run logs in Actions. The ledger is stored in `data/trades.csv`.

For a public repo, Actions has a free allowance. GitHub scheduled workflows are not guaranteed to run exactly on time. Review GitHub's current Actions usage limits before relying on it.
