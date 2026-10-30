"""
Shared settings.

Every other file imports from here, so a label or a number only has to be
changed in one place.
"""

# ---------- Math settings ----------
TRADING_DAYS_PER_YEAR = 252  # days the stock market is open in a normal year
ROLLING_WINDOW_DAYS = 30     # window used for the rolling volatility chart
MIN_TRADING_DAYS = 60        # fewer shared days than this and the statistics are not reliable
MAX_TICKERS = 15             # keeps the app fast and avoids hammering Yahoo with requests

# ---------- Names used for labels and table columns ----------
PORTFOLIO_NAME = "My Portfolio"
BENCHMARK_COLUMN = "Benchmark"
TICKER_COLUMN = "Ticker"
WEIGHT_COLUMN = "Weight (%)"
VOLATILITY_COLUMN = "Volatility (%)"
RETURN_COLUMN = "Annual Return (%)"

# ---------- Choices shown in the sidebar ----------
# Benchmarks: label shown on screen -> Yahoo Finance symbol
BENCHMARKS = {
    "S&P 500 (SPY ETF)": "SPY",
    "S&P 500 (^GSPC index)": "^GSPC",
    "NASDAQ 100 (QQQ ETF)": "QQQ",
    "TSX Composite (^GSPTSE)": "^GSPTSE",
}

# Time range presets: label -> how many days back from today
RANGE_OPTIONS = {
    "1 year": 365,
    "3 years": 3 * 365,
    "5 years": 5 * 365,
    "10 years": 10 * 365,
}
DEFAULT_RANGE = "3 years"

REBALANCE_OPTIONS = ["Buy and hold", "Rebalance daily"]

# The portfolio shown when the app first opens
DEFAULT_PORTFOLIO = [
    {TICKER_COLUMN: "AAPL", WEIGHT_COLUMN: 30.0},
    {TICKER_COLUMN: "MSFT", WEIGHT_COLUMN: 25.0},
    {TICKER_COLUMN: "NVDA", WEIGHT_COLUMN: 20.0},
    {TICKER_COLUMN: "JPM", WEIGHT_COLUMN: 15.0},
    {TICKER_COLUMN: "XOM", WEIGHT_COLUMN: 10.0},
]
