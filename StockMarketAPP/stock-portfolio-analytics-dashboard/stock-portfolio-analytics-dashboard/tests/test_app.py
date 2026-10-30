"""
Whole-page tests.

Streamlit has a test tool (AppTest) that opens the real page, clicks and types
like a user would, and lets us check what appeared. Prices come from the
simulated demo data or from a fake Yahoo, so no internet is needed.

Each test is one situation: normal use, messy input, or something going wrong.

Run all tests from the project folder with:   python -m pytest
"""
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

import config
import data_ingestion
import demo_data
import processing

APP_FILE = str(Path(__file__).resolve().parents[1] / "app.py")


# ---------- helpers ----------

def start_app(use_demo=True):
    """Open the page. With use_demo=True the 'simulated data' box is already ticked."""
    app = AppTest.from_file(APP_FILE, default_timeout=90)
    if use_demo:
        app.session_state["use_demo"] = True
    app.run()
    return app


def has_message(elements, text):
    """True if any message on the page (error, warning, info, caption) contains the text."""
    for element in elements:
        if text in element.value:
            return True
    return False


def metric_value(app, label):
    """The big number shown on the card with this label (as text)."""
    for card in app.metric:
        if card.label == label:
            return card.value
    return None


def set_portfolio(monkeypatch, rows):
    """Replace the starting portfolio, so the page opens with the table we want to test."""
    monkeypatch.setattr(config, "DEFAULT_PORTFOLIO", rows)


def fake_yahoo(monkeypatch, replacement):
    """Replace the real Yahoo download with our own function."""
    monkeypatch.setattr(data_ingestion, "get_history", replacement)


def assert_page_is_healthy(app):
    """The page drew everything: no crash, no red error box, 5 tabs, 8 number cards."""
    assert not app.exception
    assert len(app.error) == 0
    assert len(app.tabs) == 5
    assert len(app.metric) >= 8


# ---------- normal use ----------

def test_page_opens_with_the_default_portfolio():
    app = start_app()

    assert_page_is_healthy(app)
    assert has_message(app.warning, "Simulated data is switched on")


def test_every_period_preset_works():
    app = start_app()

    for name in config.RANGE_OPTIONS:
        app.sidebar.selectbox(key="period").select(name).run()
        assert_page_is_healthy(app)


def test_every_benchmark_works():
    app = start_app()

    for label in config.BENCHMARKS:
        app.sidebar.selectbox(key="benchmark").select(label).run()
        assert_page_is_healthy(app)


def test_both_rebalancing_methods_work():
    app = start_app()

    for method in config.REBALANCE_OPTIONS:
        app.sidebar.selectbox(key="rebalance").select(method).run()
        assert_page_is_healthy(app)


def test_extreme_assumptions_work():
    app = start_app()

    app.sidebar.number_input(key="start_value").set_value(100)
    app.sidebar.number_input(key="risk_free").set_value(15.0)
    app.run()
    assert_page_is_healthy(app)

    app.sidebar.number_input(key="start_value").set_value(1000000)
    app.sidebar.number_input(key="risk_free").set_value(0.0)
    app.run()
    assert_page_is_healthy(app)


def test_custom_date_range():
    app = start_app()
    app.sidebar.selectbox(key="period").select("Custom").run()

    app.sidebar.date_input(key="start_date").set_value(date(2024, 1, 2))
    app.sidebar.date_input(key="end_date").set_value(date(2024, 12, 31))
    app.run()

    assert_page_is_healthy(app)


def test_price_explorer_with_odd_moving_average_settings():
    app = start_app()

    app.slider(key="short_window").set_value(50)
    app.slider(key="long_window").set_value(20)
    app.run()

    assert not app.exception
    assert has_message(app.warning, "short average should be smaller")


# ---------- awkward input ----------

def test_start_date_after_end_date_shows_a_message():
    app = start_app()
    app.sidebar.selectbox(key="period").select("Custom").run()

    app.sidebar.date_input(key="start_date").set_value(date(2024, 6, 1))
    app.sidebar.date_input(key="end_date").set_value(date(2024, 1, 1))
    app.run()

    assert not app.exception
    assert has_message(app.error, "start date has to be before the end date")


def test_a_period_that_is_too_short_shows_a_message():
    app = start_app()
    app.sidebar.selectbox(key="period").select("Custom").run()

    app.sidebar.date_input(key="start_date").set_value(date(2024, 12, 2))
    app.sidebar.date_input(key="end_date").set_value(date(2024, 12, 20))
    app.run()

    assert not app.exception
    assert has_message(app.error, "shared trading days")


def test_empty_portfolio_asks_for_a_ticker(monkeypatch):
    set_portfolio(monkeypatch, [{"Ticker": "", "Weight (%)": float("nan")}])
    app = start_app()

    assert not app.exception
    assert has_message(app.info, "Add at least one ticker")


def test_single_ticker_portfolio(monkeypatch):
    set_portfolio(monkeypatch, [{"Ticker": "AAPL", "Weight (%)": 100.0}])
    app = start_app()

    assert_page_is_healthy(app)


def test_messy_tickers_and_duplicates(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": " aapl ", "Weight (%)": 50.0},
        {"Ticker": "AAPL", "Weight (%)": 50.0},
        {"Ticker": "msft", "Weight (%)": 0.0},
        {"Ticker": "", "Weight (%)": 30.0},
    ])
    app = start_app()

    assert_page_is_healthy(app)


def test_all_weights_zero_falls_back_to_equal_weights(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "AAPL", "Weight (%)": 0.0},
        {"Ticker": "MSFT", "Weight (%)": 0.0},
    ])
    app = start_app()

    assert_page_is_healthy(app)
    assert has_message(app.sidebar.caption, "equal share")


def test_weights_that_do_not_add_up_to_100_are_scaled(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "AAPL", "Weight (%)": 10.0},
        {"Ticker": "MSFT", "Weight (%)": 10.0},
    ])
    app = start_app()

    assert_page_is_healthy(app)
    assert has_message(app.sidebar.caption, "add up to 20.0%")


def test_the_benchmark_can_also_be_in_the_portfolio(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "SPY", "Weight (%)": 50.0},
        {"Ticker": "AAPL", "Weight (%)": 50.0},
    ])
    app = start_app()

    assert_page_is_healthy(app)


def test_too_many_tickers_are_trimmed(monkeypatch):
    rows = []
    for number in range(20):
        rows.append({"Ticker": f"T{number:02d}", "Weight (%)": 5.0})
    set_portfolio(monkeypatch, rows)
    app = start_app()

    assert_page_is_healthy(app)
    assert has_message(app.sidebar.warning, "Only the first 15 tickers")


def test_simulated_data_with_a_period_that_has_no_business_days():
    app = start_app()
    app.sidebar.selectbox(key="period").select("Custom").run()

    app.sidebar.date_input(key="start_date").set_value(date(2024, 6, 1))   # a Saturday
    app.sidebar.date_input(key="end_date").set_value(date(2024, 6, 2))     # a Sunday
    app.run()

    assert not app.exception
    assert has_message(app.error, "No prices could be created")


def test_a_portfolio_that_never_moves_shows_n_a_instead_of_crashing(monkeypatch):
    set_portfolio(monkeypatch, [{"Ticker": "FLAT", "Weight (%)": 100.0}])

    def flat_stock(ticker, start, end):
        history = demo_data.make_demo_history(ticker, start, end)
        if ticker == "FLAT":
            history["Open"] = 100.0
            history["High"] = 100.0
            history["Low"] = 100.0
            history["Close"] = 100.0
        return history

    fake_yahoo(monkeypatch, flat_stock)
    app = start_app(use_demo=False)

    assert_page_is_healthy(app)
    assert metric_value(app, "Correlation") == "n/a"   # a flat line has no correlation
    assert metric_value(app, "Volatility") == "0.0%"


def test_a_calculation_error_shows_a_friendly_message(monkeypatch):
    def broken(*arguments):
        raise ValueError("something unexpected happened inside the math")

    monkeypatch.setattr(processing, "run_analysis", broken)
    app = start_app()

    assert not app.exception
    assert has_message(app.error, "The numbers could not be calculated")


def test_a_data_alignment_error_shows_a_friendly_message(monkeypatch):
    def broken(*arguments):
        raise ValueError("the price tables could not be combined")

    monkeypatch.setattr(processing, "align_prices", broken)
    app = start_app()

    assert not app.exception
    assert has_message(app.error, "The numbers could not be calculated")


# ---------- Yahoo problems ----------

def test_yahoo_down_shows_a_message_and_the_demo_button_fixes_it(monkeypatch):
    def always_fails(ticker, start, end):
        raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")

    fake_yahoo(monkeypatch, always_fails)
    app = start_app(use_demo=False)

    assert not app.exception
    assert has_message(app.error, "No prices could be loaded")
    assert len(app.button) == 1

    app.button[0].click().run()   # the "Use simulated data instead" button

    assert_page_is_healthy(app)
    assert app.sidebar.checkbox(key="use_demo").value is True


def test_one_bad_ticker_is_skipped_and_the_rest_still_work(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "AAPL", "Weight (%)": 50.0},
        {"Ticker": "BADX", "Weight (%)": 25.0},
        {"Ticker": "MSFT", "Weight (%)": 25.0},
    ])

    def one_ticker_is_bad(ticker, start, end):
        if ticker == "BADX":
            raise ValueError("Yahoo Finance returned no data for this symbol")
        return demo_data.make_demo_history(ticker, start, end)

    fake_yahoo(monkeypatch, one_ticker_is_bad)
    app = start_app(use_demo=False)

    assert_page_is_healthy(app)
    assert has_message(app.warning, "BADX was skipped")


def test_every_stock_failing_while_the_benchmark_loads_shows_a_message(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "BADX", "Weight (%)": 60.0},
        {"Ticker": "BADY", "Weight (%)": 40.0},
    ])

    def only_the_benchmark_works(ticker, start, end):
        if ticker == "SPY":
            return demo_data.make_demo_history(ticker, start, end)
        raise ValueError("Yahoo Finance returned no data for this symbol")

    fake_yahoo(monkeypatch, only_the_benchmark_works)
    app = start_app(use_demo=False)

    assert not app.exception
    assert has_message(app.error, "None of your tickers could be loaded")


def test_a_missing_benchmark_shows_a_message(monkeypatch):
    def benchmark_is_missing(ticker, start, end):
        if ticker == "SPY":
            raise ValueError("Yahoo Finance returned no data for this symbol")
        return demo_data.make_demo_history(ticker, start, end)

    fake_yahoo(monkeypatch, benchmark_is_missing)
    app = start_app(use_demo=False)

    assert not app.exception
    assert has_message(app.error, "The benchmark SPY could not be loaded")


def test_a_stock_with_a_short_history_shortens_the_window(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "AAPL", "Weight (%)": 50.0},
        {"Ticker": "NEWCO", "Weight (%)": 50.0},
    ])

    def newco_is_a_recent_listing(ticker, start, end):
        history = demo_data.make_demo_history(ticker, start, end)
        if ticker == "NEWCO":
            history = history.iloc[300:]
        return history

    fake_yahoo(monkeypatch, newco_is_a_recent_listing)
    app = start_app(use_demo=False)

    assert_page_is_healthy(app)
    assert has_message(app.info, "Prices start on")


def test_a_stock_that_never_moves(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "AAPL", "Weight (%)": 50.0},
        {"Ticker": "FLAT", "Weight (%)": 50.0},
    ])

    def flat_stock(ticker, start, end):
        history = demo_data.make_demo_history(ticker, start, end)
        if ticker == "FLAT":
            history["Open"] = 100.0
            history["High"] = 100.0
            history["Low"] = 100.0
            history["Close"] = 100.0
        return history

    fake_yahoo(monkeypatch, flat_stock)
    app = start_app(use_demo=False)

    assert_page_is_healthy(app)


def test_bad_zero_prices_are_ignored(monkeypatch):
    def has_zero_prices(ticker, start, end):
        history = demo_data.make_demo_history(ticker, start, end)
        if ticker == "AAPL":
            history.iloc[10, history.columns.get_loc("Close")] = 0.0
            history.iloc[20, history.columns.get_loc("Close")] = 0.0
        return history

    fake_yahoo(monkeypatch, has_zero_prices)
    app = start_app(use_demo=False)

    assert_page_is_healthy(app)


def test_a_ticker_without_volume_data_still_loads(monkeypatch):
    set_portfolio(monkeypatch, [
        {"Ticker": "AAPL", "Weight (%)": 50.0},
        {"Ticker": "NOVOL", "Weight (%)": 50.0},
    ])

    def no_volume_column(ticker, start, end):
        history = demo_data.make_demo_history(ticker, start, end)
        if ticker == "NOVOL":
            history = history.drop(columns=["Volume"])
        return history

    fake_yahoo(monkeypatch, no_volume_column)
    app = start_app(use_demo=False)
    assert_page_is_healthy(app)

    app.selectbox(key="explorer_ticker").select("NOVOL").run()

    assert not app.exception
    assert has_message(app.info, "has no Volume data")
