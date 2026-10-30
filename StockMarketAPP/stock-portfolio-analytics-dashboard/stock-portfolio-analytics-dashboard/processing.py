"""
PROCESSING LAYER

Job: all of the math, done with pandas. Prices go in, numbers come out.
This file never touches Streamlit or Plotly, so every function can be tested
on its own with tiny made-up data (see tests/test_processing.py).

Plain-English glossary
    return        how much a price changed, as a fraction (0.02 means +2%)
    volatility    how much the price jumps around (higher = riskier)
    drawdown      how far the value is below its highest point so far
    benchmark     the thing we compare against (for example the S&P 500)
"""
import numpy as np
import pandas as pd

from config import (
    BENCHMARK_COLUMN,
    PORTFOLIO_NAME,
    RETURN_COLUMN,
    ROLLING_WINDOW_DAYS,
    TICKER_COLUMN,
    TRADING_DAYS_PER_YEAR,
    VOLATILITY_COLUMN,
    WEIGHT_COLUMN,
)

# ======================================================================
# 1. CLEANING WHAT THE USER TYPED
# ======================================================================

def clean_weight_table(table):
    """
    Turn the table the user edited into a dictionary {ticker: weight}.

    - tickers are trimmed and made UPPERCASE ("  aapl " becomes "AAPL")
    - blank rows are skipped
    - a missing or negative weight counts as 0
    - a ticker typed twice has its weights added together
      (a dictionary does this for us: one key per ticker)
    """
    weights = {}

    for _, row in table.iterrows():
        raw_ticker = row[TICKER_COLUMN]
        if pd.isna(raw_ticker):
            continue

        ticker = str(raw_ticker).strip().upper()
        if ticker == "":
            continue

        weight = row[WEIGHT_COLUMN]
        if pd.isna(weight) or weight < 0:
            weight = 0.0

        weights[ticker] = weights.get(ticker, 0.0) + float(weight)

    return weights


def limit_tickers(weights, max_count):
    """Keep only the first 'max_count' tickers (dictionaries remember the order they were filled in)."""
    limited = {}
    for ticker in weights:
        if len(limited) < max_count:
            limited[ticker] = weights[ticker]
    return limited


def normalize_weights(weights, available_tickers):
    """
    Scale the weights so they add up to 1 (which means 100%).
    Only tickers whose data really loaded are used.
    If every weight is 0, we fall back to equal weights.

    Example: {"A": 30, "B": 10} becomes {"A": 0.75, "B": 0.25}
    """
    total = 0.0
    for ticker in available_tickers:
        total = total + weights.get(ticker, 0.0)

    scaled = {}
    for ticker in available_tickers:
        if total > 0:
            scaled[ticker] = weights.get(ticker, 0.0) / total
        else:
            scaled[ticker] = 1 / len(available_tickers)
    return scaled


# ======================================================================
# 2. PREPARING THE PRICE DATA
# ======================================================================

def align_prices(stock_histories, benchmark_history):
    """
    Put every Close price into one table and keep only the dates where
    EVERY asset has a price. That way all columns line up row by row.

    Takes:   stock_histories {ticker: DataFrame}, benchmark_history DataFrame
    Returns: (stock_prices, benchmark_prices)
             stock_prices:     DataFrame, one column per ticker
             benchmark_prices: Series
    """
    closes = {}
    for ticker in stock_histories:
        closes[ticker] = stock_histories[ticker]["Close"]
    closes[BENCHMARK_COLUMN] = benchmark_history["Close"]

    table = pd.DataFrame(closes)
    table = table.dropna()  # drop any date where at least one asset has no price
    table = table[(table > 0).all(axis=1)]  # bad data guard: a price of 0 or less is not real

    stock_prices = table.drop(columns=[BENCHMARK_COLUMN])
    benchmark_prices = table[BENCHMARK_COLUMN]
    return stock_prices, benchmark_prices


def data_coverage(histories):
    """A small table showing the first date, last date and number of days of data for each ticker."""
    rows = []
    for ticker in histories:
        close = histories[ticker]["Close"].dropna()
        if len(close) == 0:
            continue
        rows.append({
            "Ticker": ticker,
            "First date": close.index.min().date(),
            "Last date": close.index.max().date(),
            "Trading days": len(close),
        })
    return pd.DataFrame(rows)


def rebase_to_100(prices):
    """Divide by the first price and multiply by 100, so every line starts at 100 and can be compared."""
    return prices / prices.iloc[0] * 100


def moving_average(prices, window):
    """Average of the last 'window' prices, for every day. Smooths out the daily noise."""
    return prices.rolling(window).mean()


# ======================================================================
# 3. BUILDING THE WEIGHTED PORTFOLIO
# ======================================================================

def buy_and_hold_value(stock_prices, weights, start_value):
    """
    You buy once on day 1 and never trade again.

    Each stock's price is divided by its first price, so every stock starts at 1.
    Multiply by the weight and add everything up: that is the portfolio's growth.
    Winners grow into a bigger share of the portfolio over time.
    """
    growth = stock_prices / stock_prices.iloc[0]

    portfolio_growth = pd.Series(0.0, index=stock_prices.index)
    for ticker in weights:
        portfolio_growth = portfolio_growth + growth[ticker] * weights[ticker]

    return portfolio_growth * start_value


def rebalanced_value(stock_prices, weights, start_value):
    """
    Every day the portfolio is reset to the target weights.

    Each day's portfolio return is the weighted average of that day's stock returns.
    Then we compound those daily returns (cumprod) to get the value over time.
    """
    daily = stock_prices.pct_change().fillna(0.0)  # first day has no previous price, so 0

    portfolio_daily = pd.Series(0.0, index=stock_prices.index)
    for ticker in weights:
        portfolio_daily = portfolio_daily + daily[ticker] * weights[ticker]

    return (1 + portfolio_daily).cumprod() * start_value


def build_portfolio_value(stock_prices, weights, start_value, method):
    """Pick the right calculation. 'method' comes from the sidebar."""
    if method == "Rebalance daily":
        return rebalanced_value(stock_prices, weights, start_value)
    return buy_and_hold_value(stock_prices, weights, start_value)


# ======================================================================
# 4. SINGLE-NUMBER METRICS
# ======================================================================

def total_return(values):
    """How much the value grew over the whole period. 0.25 means +25%."""
    return values.iloc[-1] / values.iloc[0] - 1


def annualized_return(values):
    """
    Total return converted to a yearly rate (also called CAGR), so that
    different time periods can be compared fairly.
    """
    number_of_days = len(values) - 1
    if number_of_days < 1:
        return 0.0
    years = number_of_days / TRADING_DAYS_PER_YEAR
    growth = values.iloc[-1] / values.iloc[0]
    return growth ** (1 / years) - 1


def annualized_volatility(returns):
    """
    Standard deviation of the daily returns, scaled up to a year.
    Daily noise adds up like a square root, which is why we multiply by sqrt(252).
    """
    return returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def sharpe_ratio(returns, risk_free_rate):
    """
    Return earned per unit of risk, after subtracting what a "safe" investment pays.
    Higher is better. Around 1 is decent, above 2 is excellent.
    """
    daily_risk_free = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = returns - daily_risk_free
    if excess.std() == 0:
        return 0.0
    return excess.mean() / excess.std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def drawdown_series(values):
    """
    For every day: how far below the highest value so far are we?
    0 means "at a new high". -0.20 means "20% below the peak".
    """
    running_peak = values.cummax()
    return values / running_peak - 1


def max_drawdown(values):
    """The worst drawdown of the whole period (the deepest dip)."""
    return drawdown_series(values).min()


def beta(returns, benchmark_returns):
    """
    How strongly the asset moves with the benchmark.
    1.0 = moves the same, 1.5 = moves 50% more, 0.5 = moves half as much.
    """
    variance = benchmark_returns.var()
    if variance == 0:
        return float("nan")  # a benchmark that never moves has no beta
    return returns.cov(benchmark_returns) / variance


def alpha(returns, benchmark_returns, risk_free_rate):
    """
    Yearly return that beta does NOT explain.
    Positive alpha means the asset did better than its market exposure predicted.
    """
    daily_risk_free = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = returns - daily_risk_free
    benchmark_excess = benchmark_returns - daily_risk_free

    market_beta = beta(returns, benchmark_returns)
    daily_alpha = excess.mean() - market_beta * benchmark_excess.mean()
    return daily_alpha * TRADING_DAYS_PER_YEAR


# ======================================================================
# 5. PUTTING IT ALL TOGETHER
# ======================================================================

def correlation_table(returns_table):
    """
    Correlation of every column with every other column.
    A column that never moves has no correlation, so it shows up as n/a (NaN).
    """
    with np.errstate(invalid="ignore", divide="ignore"):
        return returns_table.corr()


def summarize(values, benchmark_values, risk_free_rate):
    """
    All the headline numbers for ONE asset (a stock, the portfolio or the benchmark),
    measured against the benchmark.

    Takes:   values (Series of prices or portfolio value), benchmark_values (Series)
    Returns: dictionary of numbers (returns are fractions, so 0.1 means 10%)
    """
    returns = values.pct_change().dropna()
    benchmark_returns = benchmark_values.pct_change().dropna()

    stats = {}
    stats["total_return"] = total_return(values)
    stats["annual_return"] = annualized_return(values)
    stats["volatility"] = annualized_volatility(returns)
    stats["sharpe"] = sharpe_ratio(returns, risk_free_rate)
    stats["max_drawdown"] = max_drawdown(values)
    stats["beta"] = beta(returns, benchmark_returns)
    stats["alpha"] = alpha(returns, benchmark_returns, risk_free_rate)
    with np.errstate(invalid="ignore", divide="ignore"):
        stats["correlation"] = returns.corr(benchmark_returns)
    return stats


def build_stats_table(all_stats):
    """
    Turn {name: stats dictionary} into one tidy table for the screen.
    Percent columns are multiplied by 100 and the column names say so.
    """
    rows = {}
    for name in all_stats:
        stats = all_stats[name]
        rows[name] = {
            "Total Return (%)": stats["total_return"] * 100,
            RETURN_COLUMN: stats["annual_return"] * 100,
            VOLATILITY_COLUMN: stats["volatility"] * 100,
            "Sharpe Ratio": stats["sharpe"],
            "Max Drawdown (%)": stats["max_drawdown"] * 100,
            "Beta": stats["beta"],
            "Correlation": stats["correlation"],
        }
    table = pd.DataFrame.from_dict(rows, orient="index")
    table.index.name = "Name"
    return table.round(2)


def rolling_volatility(returns):
    """Volatility measured over a sliding window, to see how risk changes over time."""
    rolling_std = returns.rolling(ROLLING_WINDOW_DAYS).std()
    return (rolling_std * np.sqrt(TRADING_DAYS_PER_YEAR)).dropna()


def run_analysis(stock_prices, benchmark_prices, weights, benchmark_name,
                 start_value, rebalance_method, risk_free_rate):
    """
    One call that does all the math and returns a dictionary of results.
    The app asks for this once, then hands the pieces to the chart functions.
    """
    portfolio_values = build_portfolio_value(stock_prices, weights, start_value, rebalance_method)
    benchmark_values = benchmark_prices / benchmark_prices.iloc[0] * start_value

    # One stats dictionary per asset. A dictionary of dictionaries.
    all_stats = {}
    all_stats[PORTFOLIO_NAME] = summarize(portfolio_values, benchmark_values, risk_free_rate)
    all_stats[benchmark_name] = summarize(benchmark_values, benchmark_values, risk_free_rate)
    for ticker in stock_prices.columns:
        all_stats[ticker] = summarize(stock_prices[ticker], benchmark_values, risk_free_rate)

    # Daily returns of every stock plus the benchmark, for the correlation heatmap
    stock_returns = stock_prices.pct_change().dropna()
    benchmark_returns = benchmark_values.pct_change().dropna()
    returns_table = stock_returns.copy()
    returns_table[benchmark_name] = benchmark_returns

    results = {
        "portfolio_values": portfolio_values,
        "benchmark_values": benchmark_values,
        "headline": all_stats[PORTFOLIO_NAME],
        "benchmark_headline": all_stats[benchmark_name],
        "stats": build_stats_table(all_stats),
        "rebased_stocks": rebase_to_100(stock_prices),
        "rebased_benchmark": rebase_to_100(benchmark_prices),
        "portfolio_drawdown": drawdown_series(portfolio_values),
        "benchmark_drawdown": drawdown_series(benchmark_values),
        "portfolio_rolling_vol": rolling_volatility(portfolio_values.pct_change().dropna()),
        "benchmark_rolling_vol": rolling_volatility(benchmark_returns),
        "correlation": correlation_table(returns_table),
    }
    return results
