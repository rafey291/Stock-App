"""
Tests for the data ingestion layer.

We replace the real yfinance with a fake one that returns whatever we want.
That lets us test messy situations (empty data, duplicate dates, timezones,
failures) without the internet and without Yahoo's rate limits.

Run all tests from the project folder with:   python -m pytest
"""
from datetime import date

import pandas as pd
import pytest

import data_ingestion


def make_fake_yfinance(frame, calls):
    """Build a stand-in for yf.Ticker that returns 'frame' and records how it was called."""

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, start, end, auto_adjust):
            calls.append({"symbol": self.symbol, "start": start, "end": end, "auto_adjust": auto_adjust})
            return frame.copy()

    return FakeTicker


def make_new_york_frame():
    """Prices the way Yahoo sends them: dates with a timezone, out of order, one date twice."""
    index = pd.DatetimeIndex(
        ["2024-01-03 00:00:00-05:00", "2024-01-02 00:00:00-05:00", "2024-01-03 00:00:00-05:00"]
    )
    return pd.DataFrame(
        {"Open": [1.0, 2.0, 3.0], "High": [1.0, 2.0, 3.0], "Low": [1.0, 2.0, 3.0],
         "Close": [11.0, 10.0, 12.0], "Volume": [100, 200, 300]},
        index=index,
    )


def test_download_history_cleans_the_data(monkeypatch):
    calls = []
    monkeypatch.setattr(data_ingestion.yf, "Ticker", make_fake_yfinance(make_new_york_frame(), calls))

    history = data_ingestion.download_history("AAPL", date(2024, 1, 1), date(2024, 1, 31))

    assert history.index.tz is None                         # timezone removed
    assert history.index.is_monotonic_increasing            # sorted
    assert history.index.is_unique                          # one row per date
    assert len(history) == 2
    assert history.loc[pd.Timestamp("2024-01-03"), "Close"] == 12.0  # the last duplicate wins


def test_download_history_asks_yahoo_for_adjusted_prices_and_includes_the_end_date(monkeypatch):
    calls = []
    monkeypatch.setattr(data_ingestion.yf, "Ticker", make_fake_yfinance(make_new_york_frame(), calls))

    data_ingestion.download_history("AAPL", date(2024, 1, 1), date(2024, 1, 31))

    assert calls[0]["symbol"] == "AAPL"
    assert calls[0]["start"] == "2024-01-01"
    assert calls[0]["end"] == "2024-02-01"   # one day later, because Yahoo's end date is exclusive
    assert calls[0]["auto_adjust"] is True


def test_download_history_rejects_empty_data(monkeypatch):
    monkeypatch.setattr(data_ingestion.yf, "Ticker", make_fake_yfinance(pd.DataFrame(), []))

    with pytest.raises(ValueError):
        data_ingestion.download_history("NOPE", date(2024, 1, 1), date(2024, 1, 31))


def test_download_history_rejects_data_without_a_close_column(monkeypatch):
    frame = pd.DataFrame({"Open": [1.0]}, index=pd.DatetimeIndex(["2024-01-02"]))
    monkeypatch.setattr(data_ingestion.yf, "Ticker", make_fake_yfinance(frame, []))

    with pytest.raises(ValueError):
        data_ingestion.download_history("ODD", date(2024, 1, 1), date(2024, 1, 31))


def test_download_history_accepts_dates_that_have_no_timezone(monkeypatch):
    frame = make_new_york_frame()
    frame.index = frame.index.tz_localize(None)
    monkeypatch.setattr(data_ingestion.yf, "Ticker", make_fake_yfinance(frame, []))

    history = data_ingestion.download_history("AAPL", date(2024, 1, 1), date(2024, 1, 31))

    assert history.index.tz is None


def test_load_histories_collects_failures_instead_of_crashing(monkeypatch):
    def fake_get_history(ticker, start, end):
        if ticker == "BAD":
            raise ValueError("Yahoo Finance returned no data for this symbol")
        if ticker == "LIMITED":
            raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")
        return pd.DataFrame({"Close": [1.0, 2.0]})

    monkeypatch.setattr(data_ingestion, "get_history", fake_get_history)

    histories, failed = data_ingestion.load_histories(
        ["GOOD", "BAD", "LIMITED"], date(2024, 1, 1), date(2024, 1, 31)
    )

    assert list(histories.keys()) == ["GOOD"]
    assert sorted(failed.keys()) == ["BAD", "LIMITED"]
    assert "Rate limited" in failed["LIMITED"]


def test_load_histories_uses_simulated_data_when_asked():
    histories, failed = data_ingestion.load_histories(
        ["AAA", "BBB"], date(2024, 1, 1), date(2024, 6, 30), use_demo=True
    )

    assert sorted(histories.keys()) == ["AAA", "BBB"]
    assert failed == {}


def test_load_histories_in_demo_mode_reports_a_date_range_that_is_too_short():
    # Saturday and Sunday only: there are no business days to make prices for
    histories, failed = data_ingestion.load_histories(
        ["AAA"], date(2024, 6, 1), date(2024, 6, 2), use_demo=True
    )

    assert histories == {}
    assert "AAA" in failed
