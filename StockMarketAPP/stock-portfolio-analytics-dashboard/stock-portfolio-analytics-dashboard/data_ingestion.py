"""
DATA INGESTION LAYER

Job: get raw price data from Yahoo Finance (through the yfinance library).
This file does no math and draws no charts. It fetches data and hands it over.

(It imports Streamlit only for one thing: remembering downloads, see get_history.)
"""
from datetime import timedelta

import streamlit as st
import yfinance as yf

import demo_data


def download_history(ticker, start, end):
    """
    Ask Yahoo Finance for the daily prices of ONE ticker.

    Takes:   ticker (text like "AAPL"), start and end (date objects)
    Returns: a DataFrame with the columns Open, High, Low, Close, Volume
    Raises:  ValueError if Yahoo has no data for that ticker
    """
    # Yahoo treats the end date as "up to, but not including", so we add one day
    # to make sure the day the user picked is part of the data.
    start_text = start.strftime("%Y-%m-%d")
    end_text = (end + timedelta(days=1)).strftime("%Y-%m-%d")

    # auto_adjust=True fixes prices for stock splits and dividends.
    # Without it, a 4-for-1 split would look like a 75% crash.
    history = yf.Ticker(ticker).history(start=start_text, end=end_text, auto_adjust=True)

    if history.empty:
        raise ValueError("Yahoo Finance returned no data for this symbol")
    if "Close" not in history.columns:
        raise ValueError("Yahoo Finance returned prices without a Close column")

    # Yahoo gives dates with a timezone. Removing it lets tickers from different
    # countries (for example AAPL and RY.TO) line up by calendar date.
    history.index = history.index.tz_localize(None).normalize()

    # Safety: keep dates in order and keep only one row per date.
    history = history.sort_index()
    history = history[~history.index.duplicated(keep="last")]
    return history


@st.cache_data(ttl=3600, max_entries=200, show_spinner=False)
def get_history(ticker, start, end):
    """
    Same as download_history, but Streamlit remembers the answer for 1 hour.

    Streamlit re-runs the whole script on every click. Without this, every
    click would call Yahoo again, which is slow and gets us rate limited.
    Errors are not remembered, so a failed ticker is tried again next time.
    """
    return download_history(ticker, start, end)


def load_histories(tickers, start, end, use_demo=False):
    """
    Load a list of tickers, one by one.

    A bad ticker (typo, delisted, Yahoo hiccup) is recorded in 'failed' instead
    of crashing the app, so the other tickers still work.

    Takes:   tickers (list of text), start and end (dates), use_demo (True for fake data)
    Returns: (histories, failed)
             histories: dictionary {ticker: DataFrame}
             failed:    dictionary {ticker: reason it failed}
    """
    histories = {}
    failed = {}

    for ticker in tickers:
        try:
            if use_demo:
                histories[ticker] = demo_data.make_demo_history(ticker, start, end)
            else:
                histories[ticker] = get_history(ticker, start, end)
        except Exception as error:
            # We catch everything on purpose: network errors, rate limits and bad
            # symbols all end up here and are shown to the user as a message.
            failed[ticker] = str(error)

    return histories, failed
