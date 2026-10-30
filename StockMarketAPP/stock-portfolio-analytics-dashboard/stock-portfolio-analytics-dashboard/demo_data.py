"""
DEMO DATA (backup only)

Makes fake but realistic-looking prices, so the app still works when Yahoo
Finance is down or limiting requests. The app shows a warning banner whenever
this is switched on, so nobody mistakes it for real market data.

The same ticker and dates always give the same fake prices.
"""
import numpy as np
import pandas as pd

from config import BENCHMARKS

MARKET_SEED = 36  # same seed every time, so every ticker follows the same fake "market"


def ticker_to_number(ticker):
    """Turn the letters of a ticker into a number, so each ticker gets its own repeatable data."""
    number = 0
    for letter in ticker:
        number = (number * 31 + ord(letter)) % 1000003
    return number


def make_demo_history(ticker, start, end):
    """
    Make fake daily prices for one ticker.

    Takes:   ticker (text), start and end (date objects)
    Returns: a DataFrame with Open, High, Low, Close, Volume (same shape as the real data)
    """
    dates = pd.bdate_range(start=start, end=end)  # business days only (Monday to Friday)
    days = len(dates)
    if days < 2:
        raise ValueError("the date range is too short")

    # One shared "market" that every stock partly follows.
    # This is what makes the correlations and betas look realistic.
    market_random = np.random.default_rng(MARKET_SEED)
    market_returns = market_random.normal(0.0005, 0.0105, days)

    seed = ticker_to_number(ticker)
    own_random = np.random.default_rng(seed)

    if ticker in BENCHMARKS.values():
        daily_returns = market_returns
    else:
        market_sensitivity = 0.6 + (seed % 9) * 0.1  # between 0.6 and 1.4
        own_moves = own_random.normal(0.0002, 0.012, days)
        daily_returns = market_sensitivity * market_returns + own_moves

    start_price = 50 + (seed % 150)
    close = start_price * np.cumprod(1 + daily_returns)

    # Each day opens where the last day closed, then High and Low wiggle around it
    open_price = np.roll(close, 1)
    open_price[0] = start_price
    wiggle = np.abs(own_random.normal(0, 0.006, days))
    high = np.maximum(open_price, close) * (1 + wiggle)
    low = np.minimum(open_price, close) * (1 - wiggle)
    volume = own_random.integers(5_000_000, 50_000_000, days)

    history = pd.DataFrame(
        {"Open": open_price, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    history.index.name = "Date"
    return history
