"""
Tests for the processing layer (the math).

Most tests use tiny made-up numbers that you can check by hand, so we know the
math is right without needing the internet.

Run all tests from the project folder with:   python -m pytest
"""
from datetime import date

import numpy as np
import pandas as pd

import demo_data
import processing


def make_series(numbers):
    """Helper: turn a list of numbers into a Series with one date per number."""
    dates = pd.date_range("2024-01-01", periods=len(numbers), freq="D")
    return pd.Series(numbers, index=dates, dtype=float)


def make_history(close_numbers):
    """Helper: a history table with only a Close column, like the real data has."""
    dates = pd.bdate_range("2024-01-01", periods=len(close_numbers))
    return pd.DataFrame({"Close": close_numbers}, index=dates)


def make_demo_inputs(tickers):
    """Helper: aligned stock prices and benchmark prices built from the simulated data."""
    histories = {}
    for ticker in tickers:
        histories[ticker] = demo_data.make_demo_history(ticker, date(2023, 1, 2), date(2024, 12, 31))
    benchmark = demo_data.make_demo_history("SPY", date(2023, 1, 2), date(2024, 12, 31))
    return processing.align_prices(histories, benchmark)


# ---------- cleaning the user's input ----------

def test_clean_weight_table_fixes_messy_input():
    table = pd.DataFrame({
        "Ticker": ["aapl", "AAPL", None, "  msft ", ""],
        "Weight (%)": [10, 5, 50, None, 20],
    })
    weights = processing.clean_weight_table(table)

    assert weights == {"AAPL": 15.0, "MSFT": 0.0}  # duplicates added, blanks skipped, missing weight is 0


def test_clean_weight_table_treats_negative_weight_as_zero():
    table = pd.DataFrame({"Ticker": ["AAPL"], "Weight (%)": [-30]})

    assert processing.clean_weight_table(table) == {"AAPL": 0.0}


def test_clean_weight_table_handles_an_empty_table():
    table = pd.DataFrame({"Ticker": [], "Weight (%)": []})

    assert processing.clean_weight_table(table) == {}


def test_limit_tickers_keeps_the_first_ones_in_order():
    weights = {"A": 1, "B": 2, "C": 3, "D": 4}

    assert processing.limit_tickers(weights, 2) == {"A": 1, "B": 2}
    assert processing.limit_tickers(weights, 10) == weights


def test_normalize_weights_adds_up_to_one():
    scaled = processing.normalize_weights({"A": 30, "B": 10}, ["A", "B"])

    assert scaled == {"A": 0.75, "B": 0.25}


def test_normalize_weights_equal_when_all_zero():
    scaled = processing.normalize_weights({}, ["A", "B"])

    assert scaled == {"A": 0.5, "B": 0.5}


def test_normalize_weights_ignores_tickers_that_did_not_load():
    scaled = processing.normalize_weights({"A": 50, "C": 50}, ["A"])

    assert scaled == {"A": 1.0}


# ---------- lining up the data ----------

def test_align_prices_keeps_only_shared_dates():
    long_history = pd.DataFrame({"Close": [1.0, 2.0, 3.0, 4.0]}, index=pd.date_range("2024-01-01", periods=4))
    short_history = pd.DataFrame({"Close": [10.0, 20.0]}, index=pd.date_range("2024-01-03", periods=2))

    stock_prices, benchmark_prices = processing.align_prices({"LONG": long_history}, short_history)

    assert len(stock_prices) == 2
    assert len(benchmark_prices) == 2
    assert list(stock_prices.columns) == ["LONG"]


def test_align_prices_drops_days_with_zero_or_negative_prices():
    stock = make_history([10.0, 0.0, 12.0, -1.0, 14.0])
    benchmark = make_history([100.0, 101.0, 102.0, 103.0, 104.0])

    stock_prices, _ = processing.align_prices({"BAD": stock}, benchmark)

    assert len(stock_prices) == 3
    assert (stock_prices["BAD"] > 0).all()


def test_align_prices_drops_days_with_missing_prices():
    stock = make_history([10.0, None, 12.0])
    benchmark = make_history([100.0, 101.0, 102.0])

    stock_prices, _ = processing.align_prices({"GAP": stock}, benchmark)

    assert len(stock_prices) == 2


def test_data_coverage_lists_every_ticker():
    histories = {"A": make_history([1.0, 2.0, 3.0]), "B": make_history([4.0, 5.0])}
    coverage = processing.data_coverage(histories)

    assert list(coverage["Ticker"]) == ["A", "B"]
    assert list(coverage["Trading days"]) == [3, 2]


# ---------- single-number metrics ----------

def test_total_return():
    assert round(processing.total_return(make_series([100, 110])), 6) == 0.10


def test_annualized_return_over_exactly_one_year():
    # 252 daily returns is exactly one trading year, so annual return equals total return
    values = make_series([100.0] * 252 + [121.0])

    assert round(processing.annualized_return(values), 6) == 0.21


def test_annualized_return_with_a_single_price_is_zero():
    assert processing.annualized_return(make_series([100.0])) == 0.0


def test_max_drawdown():
    # Peak is 120, the lowest point after it is 90, so the drop is 90 / 120 - 1 = -25%
    values = make_series([100, 120, 90, 110])

    assert round(processing.max_drawdown(values), 6) == -0.25


def test_max_drawdown_is_zero_when_prices_only_go_up():
    assert processing.max_drawdown(make_series([100, 101, 102, 103])) == 0.0


def test_asset_compared_with_itself_has_beta_and_correlation_of_one():
    values = make_series([100, 102, 101, 105, 103, 108, 107])
    stats = processing.summarize(values, values, 0.0)

    assert round(stats["beta"], 6) == 1.0
    assert round(stats["correlation"], 6) == 1.0
    assert round(stats["alpha"], 6) == 0.0


def test_beta_is_nan_when_the_benchmark_never_moves():
    asset = make_series([100, 102, 101, 105, 103])
    flat_benchmark = make_series([50, 50, 50, 50, 50])
    stats = processing.summarize(asset, flat_benchmark, 0.0)

    assert pd.isna(stats["beta"])  # no crash, no infinity


def test_a_flat_price_gives_zero_volatility_and_zero_sharpe():
    flat = make_series([100.0] * 10)
    benchmark = make_series([100, 101, 99, 102, 100, 103, 101, 104, 102, 105])
    stats = processing.summarize(flat, benchmark, 0.04)

    assert stats["volatility"] == 0.0
    assert stats["sharpe"] == 0.0
    assert stats["total_return"] == 0.0


def test_beta_and_alpha_match_a_straight_line_fit():
    # Beta is the slope and alpha is the intercept of the line that best fits
    # "asset excess return" against "benchmark excess return". numpy can fit that line
    # on its own, which gives us a second, independent way to get the same answer.
    stock_prices, benchmark_prices = make_demo_inputs(["AAA"])
    asset = stock_prices["AAA"]
    risk_free_rate = 0.04

    stats = processing.summarize(asset, benchmark_prices, risk_free_rate)

    daily_risk_free = risk_free_rate / 252
    asset_excess = asset.pct_change().dropna() - daily_risk_free
    benchmark_excess = benchmark_prices.pct_change().dropna() - daily_risk_free
    slope, intercept = np.polyfit(benchmark_excess, asset_excess, 1)

    assert abs(stats["beta"] - slope) < 1e-9
    assert abs(stats["alpha"] - intercept * 252) < 1e-9


def test_volatility_and_sharpe_match_a_manual_calculation():
    stock_prices, benchmark_prices = make_demo_inputs(["AAA"])
    asset = stock_prices["AAA"]
    returns = asset.pct_change().dropna()

    stats = processing.summarize(asset, benchmark_prices, 0.0)

    assert abs(stats["volatility"] - np.std(returns, ddof=1) * np.sqrt(252)) < 1e-9
    assert abs(stats["sharpe"] - np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252)) < 1e-9


# ---------- the weighted portfolio ----------

def make_two_stock_prices():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    return pd.DataFrame({"A": [100.0, 200.0, 100.0], "B": [100.0, 100.0, 100.0]}, index=dates)


def test_buy_and_hold_value():
    # A doubles then falls back, B never moves. You end exactly where you started.
    value = processing.buy_and_hold_value(make_two_stock_prices(), {"A": 0.5, "B": 0.5}, 10000)

    assert round(value.iloc[0], 2) == 10000.0
    assert round(value.iloc[-1], 2) == 10000.0


def test_rebalanced_value_is_different_from_buy_and_hold():
    # Day 1: A is +100% and B is 0%, so the portfolio is +50%.
    # Day 2: A is -50% and B is 0%, so the portfolio is -25%.
    # 10000 * 1.5 * 0.75 = 11250
    value = processing.rebalanced_value(make_two_stock_prices(), {"A": 0.5, "B": 0.5}, 10000)

    assert round(value.iloc[-1], 2) == 11250.0


def test_build_portfolio_value_picks_the_right_method():
    prices = make_two_stock_prices()
    weights = {"A": 0.5, "B": 0.5}

    hold = processing.build_portfolio_value(prices, weights, 10000, "Buy and hold")
    rebalanced = processing.build_portfolio_value(prices, weights, 10000, "Rebalance daily")

    assert round(hold.iloc[-1], 2) == 10000.0
    assert round(rebalanced.iloc[-1], 2) == 11250.0


def test_a_portfolio_with_all_the_weight_on_one_stock_matches_that_stock():
    prices = make_two_stock_prices()
    value = processing.buy_and_hold_value(prices, {"A": 1.0, "B": 0.0}, 10000)

    assert list(value.round(2)) == [10000.0, 20000.0, 10000.0]


# ---------- the full analysis ----------

def test_run_analysis_returns_everything_the_app_needs():
    stock_prices, benchmark_prices = make_demo_inputs(["AAA", "BBB"])
    weights = processing.normalize_weights({"AAA": 60, "BBB": 40}, ["AAA", "BBB"])

    results = processing.run_analysis(
        stock_prices, benchmark_prices, weights, "S&P 500", 10000, "Buy and hold", 0.04
    )

    assert round(results["portfolio_values"].iloc[0], 2) == 10000.0
    assert round(results["benchmark_values"].iloc[0], 2) == 10000.0
    assert list(results["stats"].index) == ["My Portfolio", "S&P 500", "AAA", "BBB"]
    assert results["correlation"].shape == (3, 3)  # two stocks plus the benchmark
    assert round(results["benchmark_headline"]["beta"], 6) == 1.0
    assert len(results["portfolio_rolling_vol"]) > 0


def test_run_analysis_works_with_a_single_stock():
    stock_prices, benchmark_prices = make_demo_inputs(["AAA"])

    results = processing.run_analysis(
        stock_prices, benchmark_prices, {"AAA": 1.0}, "S&P 500", 5000, "Rebalance daily", 0.0
    )

    assert list(results["stats"].index) == ["My Portfolio", "S&P 500", "AAA"]
    assert results["correlation"].shape == (2, 2)


def test_run_analysis_does_not_crash_on_a_flat_stock():
    flat = make_history([100.0] * 120)
    moving_numbers = []
    for number in range(120):
        moving_numbers.append(100.0 + (number % 7))
    moving = make_history(moving_numbers)
    stock_prices, benchmark_prices = processing.align_prices({"FLAT": flat, "MOVE": moving}, moving)

    results = processing.run_analysis(
        stock_prices, benchmark_prices, {"FLAT": 0.5, "MOVE": 0.5}, "Index", 10000, "Buy and hold", 0.04
    )

    assert results["stats"].loc["FLAT", "Volatility (%)"] == 0.0
    assert pd.isna(results["stats"].loc["FLAT", "Correlation"])
