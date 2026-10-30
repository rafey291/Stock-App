"""
UI LAYER: the page people see.

Job: collect the user's choices, call the other layers in order, show the results.

    sidebar inputs -> data_ingestion -> processing -> visualization -> screen

There is no finance math in this file and no download code. If a number looks
wrong, look in processing.py. If data is missing, look in data_ingestion.py.
If a chart looks wrong, look in visualization.py.

Run it with:   python -m streamlit run app.py
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import data_ingestion
import processing
import visualization
from config import (
    BENCHMARKS,
    DEFAULT_PORTFOLIO,
    DEFAULT_RANGE,
    MAX_TICKERS,
    MIN_TRADING_DAYS,
    PORTFOLIO_NAME,
    RANGE_OPTIONS,
    REBALANCE_OPTIONS,
    TICKER_COLUMN,
    WEIGHT_COLUMN,
)

st.set_page_config(page_title="Portfolio Analytics Dashboard", page_icon="📈", layout="wide")

# Shown in the "Data and method" tab. Idea first, then the formula in plain text.
METHOD_NOTES = """\
Daily return
  The percent change from one day to the next.
  daily return = today's price / yesterday's price - 1

Total return
  How much the value grew over the whole period.
  total return = last value / first value - 1

Annual return (CAGR)
  Total return converted to a yearly rate, so different periods can be compared.
  annual return = (last value / first value) ^ (252 / number of days) - 1

Volatility
  How much the value jumps around. Daily noise grows like a square root, so we scale by sqrt(252).
  volatility = standard deviation of daily returns * sqrt(252)

Sharpe ratio
  Return earned per unit of risk, above what a safe investment pays.
  sharpe = (average daily return - daily risk-free rate) / standard deviation of daily returns * sqrt(252)

Drawdown
  How far the value is below its highest point so far. Max drawdown is the worst one.
  drawdown = value / highest value so far - 1

Beta
  How strongly the asset moves with the benchmark (1.0 = same, 1.5 = 50% bigger moves).
  beta = covariance(asset returns, benchmark returns) / variance(benchmark returns)

Alpha
  Yearly return that the asset's beta does not explain.
  alpha = (average asset excess return - beta * average benchmark excess return) * 252

Correlation
  How closely two assets move together, from -1 (opposite) to +1 (identical).

Buy and hold vs rebalance daily
  Buy and hold: value = sum of (weight * price / first price) * starting amount
  Rebalance daily: daily portfolio return = sum of (weight * stock daily return), then compounded
"""


# ======================================================================
# SMALL HELPERS
# ======================================================================

def percent_text(value):
    """0.123 becomes '12.3%'. Shows 'n/a' when the number could not be calculated."""
    if pd.isna(value):
        return "n/a"
    return f"{value:.1%}"


def number_text(value):
    """1.234 becomes '1.23'. Shows 'n/a' when the number could not be calculated."""
    if pd.isna(value):
        return "n/a"
    return f"{value:.2f}"


def short_reason(message):
    """Keep only the first sentence of an error message so the page stays readable."""
    first_sentence = message.split(". ")[0]
    return first_sentence[:120]


def metric_card(column, label, value, help_text, benchmark_value=None, kind="percent", lower_is_better=False):
    """
    One bordered number card.
    If benchmark_value is given, a small coloured line shows the difference to the benchmark.
    """
    if kind == "percent":
        value_text = percent_text(value)
    else:
        value_text = number_text(value)

    delta_text = None
    if benchmark_value is not None and not pd.isna(value) and not pd.isna(benchmark_value):
        difference = value - benchmark_value
        if kind == "percent":
            delta_text = f"{difference:+.1%} vs benchmark"
        else:
            delta_text = f"{difference:+.2f} vs benchmark"

    if lower_is_better:
        delta_color = "inverse"  # a smaller number is the good result, so show it green
    else:
        delta_color = "normal"

    with column:
        st.metric(
            label, value_text, delta=delta_text, delta_color=delta_color,
            help=help_text, border=True,
        )


def switch_on_demo():
    """Runs when the user clicks the 'simulated data' button (it ticks the sidebar checkbox for them)."""
    st.session_state["use_demo"] = True


def explain_load_problems(failed, requested_count, benchmark_ticker, use_demo):
    """
    Tell the user what did not load, in plain words.
    Stops the app when there is nothing useful left to show.
    """
    if len(failed) == 0:
        return

    first_reason = short_reason(list(failed.values())[0])

    # Case 1: nothing loaded at all
    if len(failed) == requested_count:
        if use_demo:
            st.error(f"No prices could be created ({first_reason}). Choose a longer period.")
        else:
            st.error(
                f"No prices could be loaded ({first_reason}). Check the symbols and the period first. "
                "If they are right, Yahoo Finance may be limiting requests: wait a minute and refresh."
            )
            st.button("Use simulated data instead", on_click=switch_on_demo)
        st.stop()

    # Case 2: only the benchmark is missing
    if benchmark_ticker in failed:
        st.error(
            f"The benchmark {benchmark_ticker} could not be loaded ({short_reason(failed[benchmark_ticker])}). "
            "Pick another benchmark in the sidebar, or try again in a minute."
        )
        st.stop()

    # Case 3: some stocks are missing. Carry on without them.
    for ticker in failed:
        st.warning(f"{ticker} was skipped ({short_reason(failed[ticker])}). Check the symbol in the sidebar.")


def stop_with_calculation_error(error):
    """Last safety net: show a friendly message instead of a wall of red code."""
    st.error(
        f"The numbers could not be calculated ({short_reason(str(error))}). "
        "Try a different period or different tickers."
    )
    st.stop()


# ======================================================================
# SIDEBAR: everything the user can change
# ======================================================================

def sidebar_inputs():
    """Draw the sidebar and return everything the user chose as one dictionary."""
    st.sidebar.title("Settings")

    # 1. Portfolio table
    st.sidebar.subheader("Portfolio")
    st.sidebar.caption("Edit the table. Add a row at the bottom for a new ticker.")
    table = st.sidebar.data_editor(
        pd.DataFrame(DEFAULT_PORTFOLIO),
        num_rows="dynamic",
        hide_index=True,
        key="portfolio_table",
        column_config={
            TICKER_COLUMN: st.column_config.TextColumn(
                "Ticker", help="Yahoo Finance symbol, for example AAPL, TSLA or RY.TO", max_chars=12
            ),
            WEIGHT_COLUMN: st.column_config.NumberColumn(
                "Weight (%)", min_value=0, max_value=100, step=1, format="%.1f"
            ),
        },
    )
    all_weights = processing.clean_weight_table(table)
    weights = processing.limit_tickers(all_weights, MAX_TICKERS)
    if len(all_weights) > len(weights):
        st.sidebar.warning(f"Only the first {MAX_TICKERS} tickers are used.")

    if len(weights) > 0:
        weight_total = sum(weights.values())
        if weight_total == 0:
            st.sidebar.caption("All weights are 0, so every ticker gets an equal share.")
        elif abs(weight_total - 100) > 0.01:
            st.sidebar.caption(f"Weights add up to {weight_total:.1f}%. They are scaled to 100% automatically.")

    # 2. Time range
    st.sidebar.subheader("Time range")
    range_names = list(RANGE_OPTIONS.keys())
    range_names.append("Custom")
    choice = st.sidebar.selectbox("Period", range_names, index=range_names.index(DEFAULT_RANGE), key="period")

    today = date.today()
    if choice == "Custom":
        earliest = date(2000, 1, 1)
        start = st.sidebar.date_input(
            "Start date", value=today - timedelta(days=365), min_value=earliest, max_value=today, key="start_date"
        )
        end = st.sidebar.date_input("End date", value=today, min_value=earliest, max_value=today, key="end_date")
        if start is None:  # the user cleared the box
            start = today - timedelta(days=365)
        if end is None:
            end = today
    else:
        start = today - timedelta(days=RANGE_OPTIONS[choice])
        end = today

    # 3. Benchmark
    st.sidebar.subheader("Benchmark")
    benchmark_label = st.sidebar.selectbox(
        "Compare against",
        list(BENCHMARKS.keys()),
        key="benchmark",
        help="The SPY ETF includes dividends, like the adjusted stock prices do, so it is the fairest S&P 500 comparison.",
    )

    # 4. Assumptions
    st.sidebar.subheader("Assumptions")
    start_value = st.sidebar.number_input(
        "Starting investment ($)", min_value=100, value=10000, step=1000, key="start_value"
    )
    rebalance = st.sidebar.selectbox(
        "Rebalancing",
        REBALANCE_OPTIONS,
        key="rebalance",
        help="Buy and hold: buy once, never trade. Rebalance daily: reset to your target weights every day.",
    )
    risk_free_percent = st.sidebar.number_input(
        "Risk-free rate (% per year)",
        min_value=0.0, max_value=15.0, value=4.0, step=0.25, key="risk_free",
        help="Used for the Sharpe ratio and alpha. Use the current yield on short-term US government bills.",
    )
    if start_value is None:  # the user cleared the box
        start_value = 10000
    if risk_free_percent is None:
        risk_free_percent = 4.0

    # 5. Backup data
    st.sidebar.divider()
    use_demo = st.sidebar.checkbox(
        "Use simulated data (offline demo)",
        key="use_demo",
        help="Backup for when Yahoo Finance is slow or blocking requests. The prices are made up.",
    )
    st.sidebar.caption("Data: Yahoo Finance through yfinance. For learning only, not financial advice.")

    return {
        "weights": weights,
        "start": start,
        "end": end,
        "benchmark_label": benchmark_label,
        "start_value": start_value,
        "rebalance": rebalance,
        "risk_free_rate": risk_free_percent / 100,
        "use_demo": use_demo,
    }


# ======================================================================
# THE HEADLINE NUMBERS (always visible above the tabs)
# ======================================================================

def show_headline_metrics(results):
    me = results["headline"]
    bench = results["benchmark_headline"]
    columns = st.columns(4)

    metric_card(
        columns[0], "Total return", me["total_return"],
        "How much the portfolio grew over the whole period.",
        bench["total_return"],
    )
    metric_card(
        columns[1], "Annual return", me["annual_return"],
        "Total return converted to a yearly rate (CAGR), so different periods can be compared.",
        bench["annual_return"],
    )
    metric_card(
        columns[2], "Sharpe ratio", me["sharpe"],
        "Return earned per unit of risk, above the risk-free rate. Around 1 is decent, above 2 is excellent.",
        bench["sharpe"], kind="number",
    )
    metric_card(
        columns[3], "Max drawdown", me["max_drawdown"],
        "The worst fall from a peak to a low point. It shows how painful the bad stretch was.",
        bench["max_drawdown"],
    )


# ======================================================================
# TABS
# ======================================================================

def show_portfolio_tab(results, used_weights, settings, benchmark_name):
    left, right = st.columns([2, 1])
    with left:
        st.plotly_chart(visualization.growth_chart(
            results["portfolio_values"], results["benchmark_values"], benchmark_name, settings["start_value"]
        ))
    with right:
        st.plotly_chart(visualization.allocation_chart(used_weights))

    me = results["headline"]
    bench = results["benchmark_headline"]
    columns = st.columns(4)
    metric_card(
        columns[0], "Volatility", me["volatility"],
        "How much the value jumps around each year. Lower means a smoother ride.",
        bench["volatility"], lower_is_better=True,
    )
    metric_card(
        columns[1], "Beta", me["beta"],
        "Sensitivity to the benchmark. 1.0 moves with it, above 1 moves more, below 1 moves less.",
        kind="number",
    )
    metric_card(
        columns[2], "Alpha (per year)", me["alpha"],
        "Yearly return that the beta does not explain. Positive means it did better than its market exposure predicted.",
    )
    metric_card(
        columns[3], "Correlation", me["correlation"],
        "How closely the portfolio moves with the benchmark. 1.0 is identical, 0 is unrelated.",
        kind="number",
    )

    st.subheader("Scorecard")
    st.dataframe(results["stats"].loc[[PORTFOLIO_NAME, benchmark_name]])

    if settings["rebalance"] == "Rebalance daily":
        st.caption("Rebalance daily: the portfolio is reset to your target weights every day.")
    else:
        st.caption("Buy and hold: you buy once at the start and never trade, so winners grow into a bigger share.")


def show_compare_tab(results, benchmark_name):
    st.plotly_chart(visualization.comparison_chart(
        results["rebased_stocks"], results["rebased_benchmark"], benchmark_name
    ))
    st.subheader("Statistics for every asset")
    st.dataframe(results["stats"])
    st.plotly_chart(visualization.risk_return_chart(results["stats"], benchmark_name))


def show_risk_tab(results, benchmark_name):
    left, right = st.columns(2)
    with left:
        st.plotly_chart(visualization.drawdown_chart(
            results["portfolio_drawdown"], results["benchmark_drawdown"], benchmark_name
        ))
    with right:
        st.plotly_chart(visualization.rolling_volatility_chart(
            results["portfolio_rolling_vol"], results["benchmark_rolling_vol"], benchmark_name
        ))
    st.plotly_chart(visualization.correlation_chart(results["correlation"]))


def show_explorer_tab(stock_histories):
    ticker = st.selectbox("Ticker", list(stock_histories.keys()), key="explorer_ticker")

    left, right = st.columns(2)
    short_window = left.slider("Short moving average (days)", 5, 50, 20, key="short_window")
    long_window = right.slider("Long moving average (days)", 20, 200, 50, key="long_window")
    if short_window >= long_window:
        st.warning("The short average should be smaller than the long average.")

    history = stock_histories[ticker]
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column not in history.columns:
            st.info(f"{ticker} has no {column} data from Yahoo Finance, so the candlestick chart is not available.")
            return

    short_average = processing.moving_average(history["Close"], short_window)
    long_average = processing.moving_average(history["Close"], long_window)

    st.plotly_chart(visualization.candlestick_chart(
        history, short_average, long_average, ticker, short_window, long_window
    ))


def show_data_tab(stock_prices, benchmark_prices, benchmark_name, stock_histories):
    st.subheader("Data coverage")
    st.caption("Only dates where every asset has a price are used, so everything lines up.")
    st.dataframe(processing.data_coverage(stock_histories), hide_index=True)

    st.subheader("Prices used in the analysis")
    prices = stock_prices.copy()
    prices[benchmark_name] = benchmark_prices
    st.dataframe(prices.round(2))
    st.download_button(
        "Download prices (CSV)", data=prices.to_csv().encode("utf-8"),
        file_name="prices.csv", mime="text/csv",
    )

    with st.expander("How the numbers are calculated"):
        st.code(METHOD_NOTES, language=None)


# ======================================================================
# MAIN: the order things happen in
# ======================================================================

def main():
    st.title("Portfolio Analytics Dashboard")
    st.caption("Build a weighted portfolio, compare it with a benchmark, and see the risk behind the returns.")

    settings = sidebar_inputs()
    weights = settings["weights"]
    benchmark_name = settings["benchmark_label"]
    benchmark_ticker = BENCHMARKS[benchmark_name]

    # --- Check the input before doing any work ---
    if len(weights) == 0:
        st.info("Add at least one ticker in the sidebar to get started.")
        st.stop()
    if settings["start"] >= settings["end"]:
        st.error("The start date has to be before the end date. Change the dates in the sidebar.")
        st.stop()
    if settings["use_demo"]:
        st.warning("Simulated data is switched on. These prices are made up for demo purposes and are not real market data.")

    # --- Layer 1: data ingestion ---
    tickers_to_download = list(weights.keys())
    if benchmark_ticker not in tickers_to_download:
        tickers_to_download.append(benchmark_ticker)

    with st.spinner("Downloading prices from Yahoo Finance..."):
        histories, failed = data_ingestion.load_histories(
            tickers_to_download, settings["start"], settings["end"], settings["use_demo"]
        )
    explain_load_problems(failed, len(tickers_to_download), benchmark_ticker, settings["use_demo"])

    stock_histories = {}
    for ticker in weights:
        if ticker in histories:
            stock_histories[ticker] = histories[ticker]
    if len(stock_histories) == 0:
        st.error("None of your tickers could be loaded. Check the symbols in the sidebar.")
        st.stop()

    # --- Layer 2: processing ---
    try:
        stock_prices, benchmark_prices = processing.align_prices(stock_histories, histories[benchmark_ticker])
    except Exception as error:
        stop_with_calculation_error(error)

    if len(stock_prices) < MIN_TRADING_DAYS:
        st.error(
            f"Only {len(stock_prices)} shared trading days were found, and at least {MIN_TRADING_DAYS} are needed. "
            "Choose a longer period or remove tickers with a short price history."
        )
        st.stop()

    first_day = stock_prices.index[0].date()
    last_day = stock_prices.index[-1].date()
    if first_day > settings["start"] + timedelta(days=10):
        st.info(f"Prices start on {first_day:%b %d, %Y}, the earliest date where every asset has data.")

    used_weights = processing.normalize_weights(weights, list(stock_prices.columns))
    try:
        results = processing.run_analysis(
            stock_prices, benchmark_prices, used_weights, benchmark_name,
            settings["start_value"], settings["rebalance"], settings["risk_free_rate"],
        )
    except Exception as error:
        stop_with_calculation_error(error)

    # --- Layer 3: visualization, shown on the page ---
    st.caption(
        f"Analysis window: {first_day:%b %d, %Y} to {last_day:%b %d, %Y} "
        f"({len(stock_prices)} trading days). Benchmark: {benchmark_name}."
    )
    show_headline_metrics(results)

    tab_names = ["Portfolio vs benchmark", "Compare stocks", "Risk", "Price explorer", "Data and method"]
    tab_portfolio, tab_compare, tab_risk, tab_explorer, tab_data = st.tabs(tab_names)

    with tab_portfolio:
        show_portfolio_tab(results, used_weights, settings, benchmark_name)
    with tab_compare:
        show_compare_tab(results, benchmark_name)
    with tab_risk:
        show_risk_tab(results, benchmark_name)
    with tab_explorer:
        show_explorer_tab(stock_histories)
    with tab_data:
        show_data_tab(stock_prices, benchmark_prices, benchmark_name, stock_histories)


main()
