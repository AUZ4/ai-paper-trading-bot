"""Educational, paper-only 15-minute opening-range breakout simulator.

Uses Yahoo Finance via yfinance. Data availability/latency is not guaranteed.
No broker integration and no real orders are possible from this script.
"""
from __future__ import annotations
import csv, json, os
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "data" / "state.json"
TRADES_PATH = ROOT / "data" / "trades.csv"
TZ = ZoneInfo("America/New_York")
TICKERS = [s.strip().upper() for s in os.getenv("TICKERS", "PANW,BRBR,WMT").split(",") if s.strip()]
STARTING_CASH = float(os.getenv("PAPER_STARTING_CASH_USD", "10"))
RISK_FRACTION = float(os.getenv("RISK_PER_TRADE", "0.01"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS_USD", "0.30"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "2"))


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"cash": STARTING_CASH, "positions": {}, "trades_today": 0,
            "daily_pnl": 0.0, "session_date": "", "last_seen": {}}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def log_trade(row):
    TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    exists = TRADES_PATH.exists()
    with TRADES_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def fetch_bars(ticker):
    df = yf.Ticker(ticker).history(period="5d", interval="5m", prepost=False, auto_adjust=False)
    if df.empty:
        return df
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df.tz_convert(TZ)



def main():
    now = datetime.now(TZ)

    # Load and save state even when the market is closed.
    state = load_state()

    if now.weekday() >= 5 or not (time(9, 45) <= now.time() <= time(15, 55)):
        save_state(state)
        print(f"Outside the configured US regular-session monitoring window: {now.isoformat()}")
        print("Paper state saved.")
        return

    today = now.date().isoformat()
    if state.get("session_date") != today:
        state["session_date"] = today
        state["trades_today"] = 0
        state["daily_pnl"] = 0.0
        state["last_seen"] = {}

    print(f"PAPER ONLY | {now.isoformat()} | cash=${state['cash']:.2f} | tickers={','.join(TICKERS)}")

    for ticker in TICKERS:
        try:
            df = fetch_bars(ticker)
            if df.empty:
                print(f"{ticker}: no market data returned")
                continue

            today_df = df[df.index.date == now.date()].copy()
            if len(today_df) < 4:
                print(f"{ticker}: waiting for 15-minute opening range")
                continue

            latest = today_df.iloc[-1]
            candle_id = today_df.index[-1].isoformat()

            if state["last_seen"].get(ticker) == candle_id:
                continue

            state["last_seen"][ticker] = candle_id
            pos = state["positions"].get(ticker)

            if pos:
                stop_hit = float(latest.Low) <= pos["stop"]
                target_hit = float(latest.High) >= pos["target"]
                exit_price = pos["stop"] if stop_hit else (pos["target"] if target_hit else None)
                reason = "stop" if stop_hit else "target"

                if exit_price is None and now.time() >= time(15, 50):
                    exit_price = float(latest.Close)
                    reason = "end_of_day"

                if exit_price is not None:
                    pnl = (exit_price - pos["entry"]) * pos["shares"]
                    state["cash"] += pos["shares"] * exit_price
                    state["daily_pnl"] += pnl
                    log_trade({
                        "timestamp": candle_id, "ticker": ticker,
                        "side": "SELL_PAPER", "shares": round(pos["shares"], 6),
                        "price": round(exit_price, 4), "pnl_usd": round(pnl, 4),
                        "reason": reason
                    })
                    print(f"{ticker}: paper exit at ${exit_price:.2f}; P/L ${pnl:.2f} ({reason})")
                    del state["positions"][ticker]
                continue

            if state["daily_pnl"] <= -MAX_DAILY_LOSS or state["trades_today"] >= MAX_TRADES_PER_DAY:
                print(f"{ticker}: daily risk/trade limit reached")
                continue

            if now.time() > time(11, 0):
                print(f"{ticker}: entry window closed")
                continue

            opening = today_df.iloc[:3]
            or_high = float(opening.High.max())
            or_low = float(opening.Low.min())
            close = float(latest.Close)

            if close <= or_high or or_high <= or_low:
                print(f"{ticker}: no confirmed ORB breakout")
                continue

            prior_vol = today_df.Volume.iloc[3:-1].tail(12)
            avg_vol = float(prior_vol.mean()) if len(prior_vol) else 0.0
            vol = float(latest.Volume)

            if avg_vol > 0 and vol < avg_vol:
                print(f"{ticker}: breakout volume below recent average")
                continue

            entry = close
            stop = or_low
            per_share_risk = entry - stop
            risk_budget = min(
                state["cash"] * RISK_FRACTION,
                MAX_DAILY_LOSS + state["daily_pnl"]
            )

            if per_share_risk <= 0 or risk_budget <= 0 or state["cash"] <= 0:
                print(f"{ticker}: risk gate blocked entry")
                continue

            shares = min(risk_budget / per_share_risk, state["cash"] / entry)
            if shares <= 0:
                continue

            cost = shares * entry
            state["cash"] -= cost
            target = entry + 2 * per_share_risk
            state["positions"][ticker] = {
                "entry": entry, "stop": stop, "target": target,
                "shares": shares, "opened": candle_id
            }
            state["trades_today"] += 1

            log_trade({
                "timestamp": candle_id, "ticker": ticker,
                "side": "BUY_PAPER", "shares": round(shares, 6),
                "price": round(entry, 4), "pnl_usd": 0,
                "reason": "15m_ORB_breakout"
            })
            print(f"{ticker}: PAPER BUY {shares:.6f} @ ${entry:.2f}; stop ${stop:.2f}; target ${target:.2f}")

        except Exception as exc:
            print(f"{ticker}: data/processing error: {exc}")

    save_state(state)
    print(f"End of run: cash=${state['cash']:.2f}; daily realised P/L=${state['daily_pnl']:.2f}; open positions={len(state['positions'])}")


if __name__ == "__main__":
    main()
